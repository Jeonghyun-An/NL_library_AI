"""종합 프롬프트 yaml 을 갈아 끼워 실제 synthesize 코드로 gemma 재생성 + 형식 점검.

사용: python run_prompt.py <yaml 경로> <태그 630e|d60a|both> <회수> <출력 json>
- 운영 보고서 JSON → ResearchState 는 rebuild.py(같은 폴더)의 state_of 를 쓴다(코드는 SYNTH_AB_APP, 기본 저장소 app/).
- services.prompts.get_prompt 대신 synthesizer 모듈 안의 get_prompt 이름을 바꿔 끼운다
  (synthesizer 는 `from services.prompts import get_prompt` 로 이름을 가져오므로 syn.get_prompt 를 덮어야 한다).
- gemma 호출의 원문을 절마다 남기고, 파싱 형식(키·자료형·summaries 번호·[E#] 자리표시자)을 센다.
- 동시 요청: 잡 하나 안에서 절은 순서대로 부르므로 동시 요청 수 = 동시에 도는 잡 수. MAX_CONCURRENT 로 4 이하.
운영 DB 에 쓰지 않는다.
"""
import asyncio
import contextvars
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # rebuild.py(같은 폴더)

import httpx  # noqa: E402
from rebuild import state_of  # noqa: E402  (SYNTH_AB_APP 또는 저장소 app/ 를 sys.path 에 넣는다)
import services.research.synthesizer as syn  # noqa: E402
from services.prompts import _load_template  # noqa: E402
from services.research.llm_json import extract_json  # noqa: E402

URL = os.environ.get("SYNTH_AB_LLM_URL", "http://192.168.12.57:18080/v1/chat/completions")  # gemma-3-12b(vLLM)
MAX_CONCURRENT = 4

yaml_path = str(Path(sys.argv[1]).resolve())
tag_arg, runs, out = sys.argv[2], int(sys.argv[3]), sys.argv[4]
tags = ("630e", "d60a") if tag_arg == "both" else (tag_arg,)


def _swap_prompt(name, doc_type=None):
    assert name == "research_synthesize", name
    return _load_template(yaml_path, name)


syn.get_prompt = _swap_prompt

client = httpx.AsyncClient()
sem = asyncio.Semaphore(MAX_CONCURRENT)
calls_var: contextvars.ContextVar[list] = contextvars.ContextVar("calls")
_SUBQ = re.compile(r"^하위질문: (.*)$", re.M)


async def gemma_chat(messages, *, params=None, timeout=None):
    async with sem:
        resp = await client.post(URL, json={"model": "gemma-3-12b", "messages": messages, **(params or {})},
                                 timeout=timeout or 300)
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    m = _SUBQ.search(messages[1]["content"])
    calls_var.get().append({"subquestion": m.group(1) if m else "", "raw": raw})
    return raw


syn.chat = gemma_chat


def check_raw(raw: str, paper_ids: list[str]) -> list[str]:
    """한 호출 원문의 형식 문제. 빈 목록이면 synthesizer 가 그대로 받는 모양이다."""
    data = extract_json(raw)
    if data is None:
        return ["JSON 파싱 실패"]
    issues = []
    intro = data.get("intro")
    if not (isinstance(intro, str) or (isinstance(intro, list) and all(isinstance(v, str) for v in intro))):
        issues.append(f"intro 자료형 {type(intro).__name__}")
    summ = data.get("summaries")
    if not isinstance(summ, dict):
        issues.append(f"summaries 자료형 {type(summ).__name__}")
    else:
        keys = {syn._eid_key(str(k)) for k in summ}
        missing = [e for e in paper_ids if e not in keys]
        extra = [k for k in keys if k not in paper_ids]
        if missing:
            issues.append(f"summaries 빠진 번호 {missing}")
        if extra:
            issues.append(f"summaries 남는 번호 {extra}")
        if any(not isinstance(v, str) or not v.strip() for v in summ.values()):
            issues.append("summaries 빈 값/문자열 아님")
    fut = data.get("future")
    if not isinstance(fut, list):
        issues.append(f"future 자료형 {type(fut).__name__}")
    elif not all(isinstance(f, dict) and isinstance(f.get("text"), str) or isinstance(f, str) for f in fut):
        issues.append("future 항목 모양")
    if syn._PLACEHOLDER in raw:
        issues.append("[E#] 자리표시자 그대로")
    return issues


async def one(tag, run):
    calls_var.set([])
    j, st = state_of(tag)
    report = await syn.synthesize(st)
    ids_by_subq = {sq.text: syn.section_paper_ids(st, sq) for sq in st.subquestions}
    calls = calls_var.get()
    for c in calls:
        c["issues"] = check_raw(c["raw"], ids_by_subq.get(c["subquestion"], []))
    return {"tag": tag, "run": run, "variant": Path(yaml_path).stem, "sections": report["sections"],
            "limitations": report["limitations"], "calls": calls}


_FIRST = re.compile(r"^.*?[.!?。](?=\s|$)", re.S)


def summarize(r):
    secs = [s for s in r["sections"]]
    n_sec = len([s for s in secs])
    calls = r["calls"]
    bad = [c for c in calls if c["issues"]]
    retried = len(calls) - n_sec
    introless = sum(1 for s in secs if not s["intro"])
    first_unmarked = sum(1 for s in secs if s["intro"] and "[E" not in (_FIRST.match(s["intro"]) or [s["intro"]])[0])
    unsumm = sum(1 for s in secs for p in s["papers"] if not p["summary"])
    hapnida = sum(1 for s in secs for t in [s["intro"], *(p["summary"] for p in s["papers"]),
                                             *(f["text"] for f in s["future"])]
                  if re.search(r"(습니다|입니다|합니다)[.\s]", t + " "))
    print(f"[{r['variant']} {r['tag']} run{r['run']}] 절 {n_sec} 호출 {len(calls)}(재시도 {retried}) "
          f"형식문제 호출 {len(bad)} 도입없음 {introless} 첫문장무표기 {first_unmarked} 요약빈칸 {unsumm} "
          f"합니다체 필드 {hapnida} future {[len(s['future']) for s in secs]}")
    for c in bad:
        print("   형식:", c["subquestion"][:40], c["issues"], c["raw"][:200].replace("\n", " "))
    for x in r["limitations"]:
        if "근거 표기" in x or "인용 표기" in x or "생성하지 못한" in x:
            print("   한계:", x)


async def main():
    tasks = [one(tag, r) for tag in tags for r in range(runs)]
    res = await asyncio.gather(*tasks, return_exceptions=True)
    ok = [r for r in res if isinstance(r, dict)]
    for r in res:
        if not isinstance(r, dict):
            print("ERR", repr(r))
    json.dump(ok, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", len(ok), "→", out)
    for r in ok:
        summarize(r)
    await client.aclose()


asyncio.run(main())
