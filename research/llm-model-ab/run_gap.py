"""이어가기 연구 공백(gap) 절 — 모델(팔) 비교 (1회성, 운영 DB·API 에 쓰지 않음).

입력은 ../gap-prompt-ab/inputs/*.json(운영 연구 9건의 절 입력을 GET 으로 다시 맞춘 것). 절 생성 코드(section._build·_parse·
_bind·_check)와 저장소 프롬프트(research_section_gap.yaml)를 그대로 쓰고, 보내는 곳만 팔의 주소·모델 이름이다. 생성기처럼
형식·인용이 맞지 않으면 세 번까지 다시 부른다.

    python run_gap.py --arms arms_aa.json [--repeats 2] [--concurrency 2] [--out gen_gap]
결과 <out>/<연구 앞 8자>/<팔>_r<회>.json · <out>/metrics.json
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
APP = HERE.parents[1] / "app"
sys.path.insert(0, str(APP))
sys.stdout.reconfigure(encoding="utf-8")

import services.research_work.section as section  # noqa: E402
from services.prompts import _load_template  # noqa: E402

GAP_YAML = str(APP / "domains" / "nl_library" / "prompts" / "research_section_gap.yaml")
section.get_prompt = lambda name, doc_type=None: _load_template(GAP_YAML, name)
INPUTS = HERE.parent / "gap-prompt-ab" / "inputs"
ATTEMPTS = 3
_NON_WORD = re.compile(r"[\W_]+")


def title_mentions(text: str, papers: list[dict]) -> int:
    body = _NON_WORD.sub("", text)
    return sum(1 for p in papers if len(key := _NON_WORD.sub("", p.get("title") or "")[:12]) >= 12 and key in body)


async def one(client, sem, arm_name: str, arm: dict, rec: dict, r: int, out: Path) -> dict:
    inp = rec["input"]
    messages, params = section._build(inp)
    body = {"model": arm["model"], "messages": messages, **params, **arm.get("extra", {})}
    attempts, bound = [], None
    for _ in range(ATTEMPTS):
        async with sem:
            t0 = time.time()   # 동시 칸을 기다린 시간은 빼고 잰다
            resp = await client.post(arm["url"], json=body, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        raw = msg.get("content")
        # reasoning parser 를 켠 모델(Gemma 4)은 답이 reasoning 칸으로 빠지면 content 가 None 이다 — 따로 남긴다
        attempts.append({"sec": round(time.time() - t0, 2), "finish": choice.get("finish_reason"),
                         "usage": data.get("usage"), "raw": raw,
                         "reasoning": msg.get("reasoning") or msg.get("reasoning_content")})
        parsed = section._parse(raw) if raw else None
        if parsed is None:
            continue
        bound = section._bind(parsed, inp)
        if section._check(bound):
            break
    paragraphs = (bound or {}).get("paragraphs") or []
    text = "\n\n".join(p["text"] for p in paragraphs)
    m = {"job": rec["job_id"][:8], "arm": arm_name, "model": arm["model"], "r": r, "attempts": len(attempts),
         "paragraphs": len(paragraphs),
         "unmarked": sum(p["checks"]["unmarked"] for p in paragraphs),
         "numbers": sum(len(p["checks"]["numbers"]) for p in paragraphs),
         "dropped": sum(p["checks"]["dropped"] for p in paragraphs),
         "titles": title_mentions(text, inp["papers"]),
         "reasoning_attempts": sum(1 for a in attempts if a["reasoning"]),
         "sec": round(sum(a["sec"] for a in attempts), 2),
         "completion_tokens": sum(((a["usage"] or {}).get("completion_tokens") or 0) for a in attempts)}
    (out / f"{arm_name}_r{r}.json").write_text(json.dumps(
        {"metrics": m, "attempts": attempts, "paragraphs": paragraphs}, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--out", default="gen_gap")
    args = ap.parse_args()
    arms = {k: v for k, v in json.loads(Path(args.arms).read_text(encoding="utf-8")).items() if not k.startswith("_")}
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(INPUTS.glob("*.json"))]
    out_root = HERE / args.out
    sem = asyncio.Semaphore(args.concurrency)
    tasks = []
    async with httpx.AsyncClient() as client:
        for r in range(args.repeats):
            for rec in recs:
                out = out_root / rec["job_id"][:8]
                out.mkdir(parents=True, exist_ok=True)
                for name, arm in arms.items():
                    tasks.append(one(client, sem, name, arm, rec, r, out))
        metrics = await asyncio.gather(*tasks, return_exceptions=True)
    ok = [m for m in metrics if isinstance(m, dict)]
    for e in (m for m in metrics if not isinstance(m, dict)):
        print("ERR", repr(e))
    (out_root / "metrics.json").write_text(json.dumps(ok, ensure_ascii=False, indent=1), encoding="utf-8")
    for name in arms:
        ms = [m for m in ok if m["arm"] == name]
        tot = {k: sum(m[k] for m in ms) for k in ("unmarked", "numbers", "dropped", "titles", "paragraphs", "attempts")}
        secs = sorted(m["sec"] for m in ms)
        print(name, len(ms), json.dumps(tot, ensure_ascii=False),
              "sec median", secs[len(secs) // 2] if secs else None)


if __name__ == "__main__":
    asyncio.run(main())
