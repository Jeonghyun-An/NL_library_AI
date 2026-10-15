"""종합 프롬프트 A/B — 변형 yaml 여럿 × 운영 보고서 4건 × N회를 한 프로세스에서 실제 synthesize 코드로 gemma 재생성한다.

사용: PYTHONIOENCODING=utf-8 python run_ab.py <회수> [변형키 ...] [--out 폴더] [--yaml 변형키=경로 ...]
  변형키 = base focus attrib concise focus2 (기본은 1차의 넷). 결과는 <폴더>/<변형>_<태그>_r<회>.json(기본 폴더 gen_ab)
  — 이미 있으면 건너뛴다(이어 돌리기). --yaml 은 그 변형의 yaml 경로를 바꾼다(파일 이름의 변형 라벨은 그대로).
  2차(focus 대 focus2, 2026-10-14): python run_ab.py 2 focus focus2 --out gen_r2 --yaml focus=repo
    (repo = SYNTH_AB_APP 의 research_synthesize.yaml — 당시 fix-live worktree 의 채택된 focus 정본. variant_focus.yaml 과 바이트 단위로 같다)
  1차(base·focus·attrib·concise × 4건 × 2회): python run_ab.py 2 — 당시 사본 run_ab_r1.py 는 이 파일에서 code_head 기록·--out·--yaml 만 없던 것이라 넣지 않았다.
- 코드 = SYNTH_AB_APP(당시 fix-live worktree HEAD — pick_excerpts·drop_repeats 포함) 그대로. 바꾸는 것은 synthesizer 모듈 안의
  get_prompt 이름 하나(contextvar 로 잡마다 yaml 경로를 고른다)와 chat(gemma 직결 + 원문 기록)뿐이다.
- 기록용으로 pick_excerpts·drop_repeats·assemble_report 를 감싼다(동작은 원래 함수 그대로 — 반환값을 바꾸지 않는다).
- 동시 요청: 잡 하나 안에서 절은 순서대로 부르므로 동시 요청 = 동시에 도는 잡 수. 잡 세마포어 4 + 요청 세마포어 4.
운영 DB 에 쓰지 않는다(운영 API 도 부르지 않는다 — 입력은 jobs/job_*.json — rebuild.py 참고).
"""
import asyncio
import contextvars
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # rebuild.py(같은 폴더)

import httpx  # noqa: E402
import rebuild  # noqa: E402  (SYNTH_AB_APP 또는 저장소 app/ 를 sys.path 에 넣는다)
from rebuild import SD, state_of  # noqa: E402
import services.research.synthesizer as syn  # noqa: E402
from services.prompts import _load_template  # noqa: E402
from services.research.llm_json import extract_json  # noqa: E402

# 운영 GET 으로 받은 2건을 더한다(응답 꼴은 기존 2건과 같다)
rebuild.JOBS.update({
    "85d2": SD + "job_85d2bc0e-541d-4d27-a98f-c0b8fe262701.json",
    "9ba1": SD + "job_9ba10849-36e2-417a-bc59-abec8e002c2c.json",
})
TAGS = ("630e", "d60a", "85d2", "9ba1")
REPO_YAML = Path(rebuild.WT) / "domains" / "nl_library" / "prompts" / "research_synthesize.yaml"
VARIANTS = {
    "base": HERE / "base.yaml",
    "focus": HERE / "variant_focus.yaml",
    "attrib": HERE / "variant_attrib.yaml",
    "concise": HERE / "variant_concise.yaml",
    "focus2": HERE / "variant_focus2.yaml",
}
DEFAULT_VARIANTS = ["base", "focus", "attrib", "concise"]
URL = os.environ.get("SYNTH_AB_LLM_URL", "http://192.168.12.57:18080/v1/chat/completions")  # gemma-3-12b(vLLM)
MAX_CONCURRENT = 4
OUT = HERE / "gen_ab"


def _code_head() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "-C", rebuild.WT, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception as e:  # noqa: BLE001 — 기록용
        return f"? ({e})"


CODE_HEAD = _code_head()

yaml_var: contextvars.ContextVar[str] = contextvars.ContextVar("yaml")
rec_var: contextvars.ContextVar[dict] = contextvars.ContextVar("rec")


def _swap_prompt(name, doc_type=None):
    assert name == "research_synthesize", name
    return _load_template(yaml_var.get(), name)


syn.get_prompt = _swap_prompt

client = httpx.AsyncClient()
req_sem = asyncio.Semaphore(MAX_CONCURRENT)
_SUBQ = re.compile(r"^하위질문: (.*)$", re.M)


async def gemma_chat(messages, *, params=None, timeout=None):
    m = _SUBQ.search(messages[1]["content"])
    call = {"subquestion": m.group(1) if m else "", "raw": None, "finish": None, "error": None,
            "prompt_chars": sum(len(x["content"]) for x in messages)}
    rec_var.get()["calls"].append(call)
    t0 = time.time()
    try:
        async with req_sem:
            resp = await client.post(URL, json={"model": "gemma-3-12b", "messages": messages, **(params or {})},
                                     timeout=timeout or 300)
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
    except httpx.HTTPError as e:
        call["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        call["sec"] = round(time.time() - t0, 1)
    call["raw"] = choice["message"]["content"]
    call["finish"] = choice.get("finish_reason")
    return call["raw"]


syn.chat = gemma_chat

_real_pick = syn.pick_excerpts
_real_drop = syn.drop_repeats
_real_assemble = syn.assemble_report


def _spy_pick(state, sq, shown):
    picked = _real_pick(state, sq, shown)
    rec_var.get()["excerpts"][sq.text] = {
        eid: {"chunk_id": c.chunk_id, "text": syn.excerpt_text(c)} for eid, c in picked.items()}
    return picked


def _spy_drop(section, seen):
    out, kept = _real_drop(section, seen)
    before = syn._sentences(section.get("intro", ""))
    after = set(syn._sentences(out.get("intro", "")))
    fut_after = {f["text"] for f in out.get("future", [])}
    rec_var.get()["dropped"][section["heading"]] = {
        "intro_before": section.get("intro", ""),
        "future_before": [f["text"] for f in section.get("future", [])],
        "removed": [s for s in before if s not in after]
                   + [f["text"] for f in section.get("future", []) if f["text"] not in fut_after],
    }
    return out, kept


def _spy_assemble(state, sections, *, unmarked_total):
    rec_var.get()["pre_final"] = [{k: v for k, v in s.items() if k not in ("evidence_chunks", "chunk_scores")}
                                  for s in sections]
    return _real_assemble(state, sections, unmarked_total=unmarked_total)


syn.pick_excerpts = _spy_pick
syn.drop_repeats = _spy_drop
syn.assemble_report = _spy_assemble


def check_raw(raw: str | None, paper_ids: list[str]) -> list[str]:
    """한 호출 원문의 형식 문제(run_prompt.py 와 같은 기준). 빈 목록이면 synthesizer 가 그대로 받는 모양이다."""
    if raw is None:
        return ["전송 오류"]
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
    elif not all((isinstance(f, dict) and isinstance(f.get("text"), str)) or isinstance(f, str) for f in fut):
        issues.append("future 항목 모양")
    if syn._PLACEHOLDER in raw:
        issues.append("[E#] 자리표시자 그대로")
    return issues


job_sem = asyncio.Semaphore(MAX_CONCURRENT)


async def one(variant: str, tag: str, run: int) -> str:
    path = OUT / f"{variant}_{tag}_r{run}.json"
    if path.exists():
        return f"skip {path.name}"
    async with job_sem:
        yaml_var.set(str(VARIANTS[variant]))
        rec = {"calls": [], "excerpts": {}, "dropped": {}, "pre_final": None}
        rec_var.set(rec)
        j, st = state_of(tag)
        t0 = time.time()
        out = {"tag": tag, "job_id": j["job_id"], "question": j["question"], "run": run, "variant": variant,
               "yaml": str(VARIANTS[variant]), "code_head": CODE_HEAD}
        try:
            report = await syn.synthesize(st)
            out.update(sections=report["sections"], limitations=report["limitations"], error=None)
        except Exception as e:  # 전부 실패(ValueError) 등 — 기록하고 넘어간다
            out.update(sections=None, limitations=None, error=f"{type(e).__name__}: {e}")
        ids_by_subq = {sq.text: syn.section_paper_ids(st, sq) for sq in st.subquestions}
        for c in rec["calls"]:
            c["issues"] = check_raw(c["raw"], ids_by_subq.get(c["subquestion"], []))
        out.update(calls=rec["calls"], excerpts=rec["excerpts"], dropped=rec["dropped"], pre_final=rec["pre_final"],
                   elapsed=round(time.time() - t0, 1))
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        bad = sum(1 for c in rec["calls"] if c["issues"])
        n_sec = len(out["sections"] or [])
        return (f"done {path.name} {out['elapsed']}s 절 {n_sec} 호출 {len(rec['calls'])} 형식문제 {bad}"
                + (f" ERR {out['error']}" if out["error"] else ""))


def parse_args(argv: list[str]) -> tuple[int, list[str]]:
    """<회수> [변형키 ...] [--out 폴더] [--yaml 변형키=경로|repo ...] — OUT·VARIANTS 를 고친다."""
    global OUT
    pos, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            OUT = (HERE / argv[i + 1]).resolve()
            i += 2
        elif a == "--yaml":
            k, _, p = argv[i + 1].partition("=")
            VARIANTS[k] = REPO_YAML if p == "repo" else Path(p).resolve()
            i += 2
        else:
            pos.append(a)
            i += 1
    variants = pos[1:] or DEFAULT_VARIANTS
    for v in variants:
        assert v in VARIANTS and Path(VARIANTS[v]).is_file(), (v, VARIANTS.get(v))
    return int(pos[0]), variants


async def main():
    runs, variants = parse_args(sys.argv[1:])
    print("code", CODE_HEAD, "out", OUT, {v: str(VARIANTS[v]) for v in variants}, flush=True)
    OUT.mkdir(exist_ok=True)
    # 회차 → 보고서 → 변형 순으로 섞어 넣는다 — 변형마다 서버 부하 조건이 비슷해지게
    jobs = [one(v, t, r) for r in range(runs) for t in TAGS for v in variants]
    for fut in asyncio.as_completed(jobs):
        try:
            print(await fut, flush=True)
        except Exception as e:
            print("ERR", repr(e), flush=True)
    await client.aclose()


asyncio.run(main())
