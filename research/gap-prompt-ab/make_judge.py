"""판정 묶음 만들기 — 연구마다 출력 9개(변형 3 × 3회)에 가린 라벨(L1~L9)을 붙이고 문장마다 번호를 매긴다 (1회성).

판정자는 judge/<id8>.json 만 읽는다. 라벨 → (변형, 회차) 는 judge_key.json(판정자에게 주지 않음)에 둔다.
섞는 순서는 연구 id 로 정한다(다시 돌려도 같다). triads 는 같은 회차의 세 변형을 섞은 라벨 묶음이다.

    python make_judge.py [--variants base,cite,frame] [--tag ""] [--out judge]   → <out>/<id8>.json · <out>_key.json
(1차: 기본값 — judge/·judge_key.json. 2차: --variants base,cite,cite2 --tag _2 --out judge_r2)
"""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPEATS = 3
# 문장 끝 — 마침표 뒤 공백(인용 표기는 마침표 앞에 온다: '…다 [E1].')
_SENT = re.compile(r"(?<=[.!?])\s+")


def sentences(paragraphs: list[dict]) -> list[dict]:
    out = []
    for pi, p in enumerate(paragraphs, start=1):
        for s in _SENT.split(p["text"].strip()):
            if s.strip():
                out.append({"n": len(out) + 1, "paragraph": pi, "text": s.strip()})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="base,cite,frame")
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default="judge")
    args = ap.parse_args()
    variants = tuple(args.variants.split(","))
    key: dict[str, dict] = {}
    (HERE / args.out).mkdir(exist_ok=True)
    for path in sorted((HERE / "inputs").glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        jid = rec["job_id"][:8]
        inp = rec["input"]
        rng = random.Random(int(hashlib.sha256(jid.encode()).hexdigest(), 16))
        combos = [(v, r) for r in range(REPEATS) for v in variants]
        labels = [f"L{i}" for i in range(1, len(combos) + 1)]
        rng.shuffle(labels)
        by_combo = dict(zip(combos, labels))
        outputs = {}
        for (v, r), label in by_combo.items():
            gen = json.loads((HERE / "gen" / jid / f"{v}{args.tag}_r{r}.json").read_text(encoding="utf-8"))
            outputs[label] = {"sentences": sentences(gen["paragraphs"])}
        triads = []
        for r in range(REPEATS):
            t = [by_combo[(v, r)] for v in variants]
            rng.shuffle(t)
            triads.append(t)
        packet = {
            "job": jid,
            "original_question": inp["question"],
            "topic_title": inp["topic"]["title"],
            "research_question": inp["research_question"],
            "gap_seeds": [s["text"] for s in inp["seeds"]],
            "evidence": [{"eid": p["eid"], "title": p["title"], "year": p["year"], "abstract": p["abstract"],
                          "excerpt": (p.get("excerpt") or {}).get("text") or ""} for p in inp["papers"]],
            "outputs": dict(sorted(outputs.items(), key=lambda kv: int(kv[0][1:]))),
            "triads": triads,
        }
        (HERE / args.out / f"{jid}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8")
        key[jid] = {label: {"variant": v, "r": r} for (v, r), label in by_combo.items()}
    (HERE / f"{args.out}_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    print("packets", len(key))


if __name__ == "__main__":
    main()
