"""운영 prior.g2(연구 d60a5dc1, gen 102) 입력으로 gemma 를 N 회 불러 프롬프트 바꾸기 전·뒤의 수치 칩 새는 비율을 견준다.

LLM 에 POST(chat/completions)를 보내므로 사람이 직접 돌린다(세션 규칙: 운영은 GET 만).
    cd <worktree>/app
    python <이 파일> --base-url http://<gemma>/v1 --model <gemma 모델 이름> -n 8
입력: 같은 폴더의 proposal.json(GET /proposal)·src_g2.json(GET /sections/prior.g2/sources?gen=102)·prior_before.yaml
(1c0b0a6 의 research_section_prior.yaml). 결과: 같은 폴더 measure_g2.json 과 화면 요약.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import httpx
import yaml
from jinja2 import Environment, StrictUndefined

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.cwd()))     # app 폴더에서 돌린다

from services.prompts import get_prompt                                   # noqa: E402
from services.research_work.section import EXECUTOR, paragraph_range      # noqa: E402
from services.research_work.section_input import evidence_block, figure_block, section_figures  # noqa: E402

LOOSE_F = re.compile(r"\[F\d+\](?![가-힣])")
ANY_F = re.compile(r"\[F\d+\]")
SELF = re.compile(r"(?:본|이)\s*(?:연구|논문)")


def section_input() -> dict:
    prop = json.loads((HERE / "proposal.json").read_text(encoding="utf-8"))
    src = json.loads((HERE / "src_g2.json").read_text(encoding="utf-8"))
    sec = prop["sections"]["prior.g2"]
    outline = prop["outline"]
    papers = []
    for eid, cnts in sec["evidence"].items():
        book = (prop.get("papers") or {}).get(cnts) or {}
        s = src.get(eid) or {}
        papers.append({"eid": eid, "cnts_id": cnts, "title": book.get("title") or cnts,
                       "year": int(str(book.get("pub_date") or "0")[:4]) or None,
                       "abstract": s.get("abstract") or "", "excerpt": s.get("excerpt")})
    return {"key": "prior.g2", "kind": "prior", "question": outline.get("question") or "",
            "topic": outline.get("topic") or {}, "research_question": outline.get("question") or "",
            "group": {"name": "사회적 지지"}, "seeds": [], "papers": papers, "figures": sec["figures"],
            "basis": sec.get("basis") or {}}


def messages_before(inp: dict) -> tuple[list[dict], dict]:
    tpl = yaml.safe_load((HERE / "prior_before.yaml").read_text(encoding="utf-8"))
    env = Environment(undefined=StrictUndefined)
    vars = {"question": inp["question"], "topic_title": inp["topic"].get("title") or "",
            "research_question": inp["research_question"], "group_name": inp["group"]["name"],
            "evidence_block": evidence_block(inp["papers"]), "figure_list": figure_block(inp["figures"])}
    return ([{"role": "system", "content": env.from_string(tpl["system"]).render(**vars)},
             {"role": "user", "content": env.from_string(tpl["user"]).render(**vars)}], tpl["params"])


def call(base_url: str, model: str, messages: list[dict], params: dict) -> str:
    r = httpx.post(f"{base_url.rstrip('/')}/chat/completions", timeout=300,
                   json={"model": model, "messages": messages, **params})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


def score(raw: str, inp: dict) -> dict:
    bound = EXECUTOR.bind(EXECUTOR.parse(raw) or {"paragraphs": []}, inp)
    stored = [p["text"] for p in bound["paragraphs"]]
    return {"raw_paragraphs": len([b for b in re.split(r"\n\s*\n", raw) if b.strip()]),
            "raw_any_f": len(ANY_F.findall(raw)), "raw_loose_f": len(LOOSE_F.findall(raw)),
            "raw_self": len(SELF.findall(raw)),
            "stored_paragraphs": len(stored), "stored_loose_f": sum(len(LOOSE_F.findall(t)) for t in stored),
            "stored_self": sum(len(SELF.findall(t)) for t in stored),
            "dropped_f": sum(p["checks"]["dropped_f"] for p in bound["paragraphs"]),
            "check_ok": EXECUTOR.check(bound), "raw": raw, "stored": stored}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("-n", type=int, default=8)
    args = ap.parse_args()
    inp = section_input()
    # 고친 뒤 입력은 수치가 근거 논문의 편수·연도뿐이다(780bf13 — 소장 KCI 적재분 F3 을 뺐다)
    inp_after = {**inp, "figures": section_figures([p["year"] for p in inp["papers"] if p["year"]],
                                                   len(inp["papers"]))}
    variants = {"before": (messages_before(inp), inp), "after": (EXECUTOR.build(inp_after), inp_after)}
    assert "쓸 문단 수: " + paragraph_range(len(inp["papers"])) in variants["after"][0][0][1]["content"]
    assert "적재분" not in variants["after"][0][0][1]["content"]
    out = {}
    for name, ((messages, params), vinp) in variants.items():
        runs = [score(call(args.base_url, args.model, messages, params), vinp) for _ in range(args.n)]
        out[name] = runs
        def rate(key: str) -> str:
            return f"{sum(1 for r in runs if r[key]) }/{len(runs)}"
        print(f"{name}: 원문 [F#] 있음 {rate('raw_any_f')} · 원문 떨어진 [F#] {rate('raw_loose_f')} · "
              f"원문 본/이 연구 {rate('raw_self')} · 저장 떨어진 [F#] {rate('stored_loose_f')} · "
              f"저장 본/이 연구 {rate('stored_self')} · 검사 통과 {rate('check_ok')} · "
              f"원문 문단 수 {[r['raw_paragraphs'] for r in runs]} · 저장 문단 수 {[r['stored_paragraphs'] for r in runs]}")
    (HERE / "measure_g2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
