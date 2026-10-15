"""연구 공백(gap) 절 프롬프트 A/B — inputs/*.json 의 절 입력으로 변형마다 다시 쓴다 (1회성, 운영 DB·API 에 쓰지 않음).

절 생성 코드(services/research_work/section.py)의 _build·_parse·_bind·_check 를 그대로 쓰고, get_prompt 만 변형 yaml 로
갈아 끼운다. LLM 은 운영과 같은 vLLM(gemma-3-12b)에 직접 보낸다. 생성기(generate.Executor)처럼 응답이 형식에 맞지 않거나
유효한 인용이 하나도 없으면 세 번까지 다시 부른다.

    python run_ab.py [--repeats 2] [--variants base,cite,frame]   → gen/<id8>/<variant>_r<n>.json · metrics.json
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))

import services.research_work.section as section  # noqa: E402
from services.prompts import _load_template  # noqa: E402

URL = "http://192.168.12.57:18080/v1/chat/completions"   # gemma-3-12b(vLLM) — 운영 생성과 같은 서버
VARIANTS = {"base": HERE / "base.yaml", "cite": HERE / "variant_cite.yaml", "frame": HERE / "variant_frame.yaml",
            "cite2": HERE / "variant_cite2.yaml"}
ATTEMPTS = 3
MAX_CONCURRENT = 4
_NON_WORD = re.compile(r"[\W_]+")
_TITLE_PREFIX = 12
_SELF_REF = re.compile(r"(?:본|이)\s*(?:연구|논문)(?:는|은|에서|의|가|이)")


def build(inp: dict, variant: str) -> tuple[list[dict], dict]:
    path = str(VARIANTS[variant])
    section.get_prompt = lambda name, doc_type=None: _load_template(path, name)
    return section._build(inp)


def title_mentions(text: str, papers: list[dict]) -> list[str]:
    """본문에 쓴 근거 논문 제목(공백·기호를 뗀 앞 12자가 본문에 그대로 있음)의 E#."""
    body = _NON_WORD.sub("", text)
    out = []
    for p in papers:
        key = _NON_WORD.sub("", p.get("title") or "")[:_TITLE_PREFIX]
        if len(key) >= _TITLE_PREFIX and key in body:
            out.append(p["eid"])
    return out


async def one(client: httpx.AsyncClient, sem: asyncio.Semaphore, rec: dict, variant: str, r: int, out: Path,
              tag: str = "") -> dict:
    inp = rec["input"]
    messages, params = build(inp, variant)
    attempts, raw, parsed, bound = [], None, None, None
    for _ in range(ATTEMPTS):
        t0 = time.time()
        async with sem:
            resp = await client.post(URL, json={"model": "gemma-3-12b", "messages": messages, **params}, timeout=300)
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        raw = choice["message"]["content"]
        attempts.append({"sec": round(time.time() - t0, 1), "finish": choice.get("finish_reason")})
        parsed = section._parse(raw)
        if parsed is None:
            continue
        bound = section._bind(parsed, inp)
        if section._check(bound):
            break
    paragraphs = (bound or {}).get("paragraphs") or []
    text = "\n\n".join(p["text"] for p in paragraphs)
    m = {
        "job": rec["job_id"][:8], "variant": variant, "r": r, "attempts": len(attempts),
        "paragraphs": len(paragraphs),
        "unmarked": sum(p["checks"]["unmarked"] for p in paragraphs),
        "numbers": sum(len(p["checks"]["numbers"]) for p in paragraphs),
        "dropped": sum(p["checks"]["dropped"] for p in paragraphs),
        "dropped_f": sum(p["checks"]["dropped_f"] for p in paragraphs),
        "softened": sum(p["checks"]["softened"] for p in paragraphs),
        "titles": title_mentions(text, inp["papers"]),
        "self_ref": len(_SELF_REF.findall(text)),
        "cited_papers": sorted({c for p in paragraphs for c in p["cites"]}),
        "chars": len(text),
    }
    (out / f"{variant}{tag}_r{r}.json").write_text(json.dumps(
        {"metrics": m, "raw": raw, "attempts": attempts, "paragraphs": paragraphs,
         "params": params}, ensure_ascii=False, indent=1), encoding="utf-8")   # 프롬프트는 inputs + yaml 로 다시 만든다
    return m


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--variants", default="base,cite,frame")
    ap.add_argument("--tag", default="", help="출력 파일 이름 뒤에 붙일 회차 표시(2차는 r2 — 1차 파일을 덮지 않게)")
    ap.add_argument("--metrics", default="metrics.json")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((HERE / "inputs").glob("*.json"))]
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    jobs = []
    async with httpx.AsyncClient() as client:
        for rec in recs:
            out = HERE / "gen" / rec["job_id"][:8]
            out.mkdir(parents=True, exist_ok=True)
            for variant in args.variants.split(","):
                for r in range(args.repeats):
                    jobs.append(one(client, sem, rec, variant, r, out, args.tag))
        metrics = await asyncio.gather(*jobs)
    (HERE / args.metrics).write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    for v in args.variants.split(","):
        ms = [m for m in metrics if m["variant"] == v]
        tot = {k: sum(m[k] for m in ms) for k in ("unmarked", "numbers", "dropped", "dropped_f", "softened",
                                                   "self_ref", "paragraphs", "attempts", "chars")}
        tot["titles"] = sum(len(m["titles"]) for m in ms)
        tot["outputs_with_unmarked"] = sum(1 for m in ms if m["unmarked"])
        tot["empty"] = sum(1 for m in ms if not m["paragraphs"])
        print(v, len(ms), json.dumps(tot, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
