"""판정 묶음 — 팔(모델) 이름을 가린 라벨을 붙이고 문장마다 번호를 매긴다 (1회성).

- 종합: judge_<tag>/synth/<보고서 태그>.json — 그 보고서의 출력 전부(팔 × 회)를 R1… 라벨로, 문장(절·부분·출처 논문)과 근거
  논문(제목·연도·대목 청크 — jobs/ 의 운영 보고서에서)을 싣는다. pairs 는 같은 회차의 두 팔을 섞은 라벨 짝이다.
- 공백 절: judge_<tag>/gap/<연구 앞 8자>.json — gap-prompt-ab/make_judge.py 와 같은 꼴(L1…, 문장 번호, evidence), pairs 는 회차별 짝.
- 열쇠(라벨 → 팔·회)는 judge_<tag>/key.json — 판정자에게 주지 않는다. 섞는 순서는 태그·연구 id 로 정한다.

    python make_packets.py --gen-synth gen_synth_aa --gen-gap gen_gap_aa --tag aa
"""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SENT = re.compile(r"(?<=[.!?])\s+")


def split(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split((text or "").strip()) if s.strip()]


def rng_for(key: str) -> random.Random:
    return random.Random(int(hashlib.sha256(key.encode()).hexdigest(), 16))


def synth_packets(gen: Path, out: Path, key: dict) -> None:
    jobs = json.loads((HERE / "jobs.json").read_text(encoding="utf-8"))
    files = sorted(gen.glob("*.json"))
    by_tag: dict[str, list[dict]] = {}
    for f in files:
        g = json.loads(f.read_text(encoding="utf-8"))
        by_tag.setdefault(g["tag"], []).append(g)
    out.mkdir(parents=True, exist_ok=True)
    for tag, outs in by_tag.items():
        job = json.loads((HERE / "jobs" / f"job_{jobs[tag]}.json").read_text(encoding="utf-8"))
        ev = job["report"]["evidence"]
        eid_of = {e["cnts_id"]: eid for eid, e in ev.items()}
        rng = rng_for(f"synth-{tag}")
        labels = [f"R{i}" for i in range(1, len(outs) + 1)]
        rng.shuffle(labels)
        packet_outs, used = {}, set()
        for label, g in zip(labels, outs):
            sentences, n = [], 0
            for si, s in enumerate(g.get("sections") or [], start=1):
                for t in split(s.get("intro", "")):
                    n += 1
                    sentences.append({"n": n, "section": si, "part": "intro", "text": t})
                for p in s.get("papers") or []:
                    eid = eid_of.get(p["cnts_id"])
                    used.add(eid)
                    for t in split(p.get("summary", "")):
                        n += 1
                        sentences.append({"n": n, "section": si, "part": "summary", "paper": eid, "text": t})
                for f in s.get("future") or []:
                    n += 1
                    sentences.append({"n": n, "section": si, "part": "future", "text": f.get("text", "")})
                used.update(s.get("evidence_chunks", {}).keys())
            packet_outs[label] = {"headings": [s["heading"] for s in g.get("sections") or []], "sentences": sentences,
                                  "error": g.get("error")}
            key.setdefault("synth", {}).setdefault(tag, {})[label] = {"arm": g["arm"], "run": g["run"]}
        pairs = []
        runs = sorted({g["run"] for g in outs})
        for r in runs:
            pair = [lab for lab, g in zip(labels, outs) if g["run"] == r]
            rng.shuffle(pair)
            pairs.append(pair)
        evidence = [{"eid": eid, "title": (ev[eid].get("meta") or {}).get("title"),
                     "year": (ev[eid].get("meta") or {}).get("pub_date"),
                     "chunks": [c["text"] for c in ev[eid].get("chunks") or []]}
                    for eid in sorted((e for e in used if e in ev), key=lambda e: int(e[1:]))]
        (out / f"{tag}.json").write_text(json.dumps(
            {"tag": tag, "question": job["question"], "outputs": dict(sorted(packet_outs.items())),
             "pairs": pairs, "evidence": evidence}, ensure_ascii=False, indent=1), encoding="utf-8")


def gap_packets(gen: Path, out: Path, key: dict) -> None:
    inputs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (HERE.parent / "gap-prompt-ab" / "inputs").glob("*.json")}
    out.mkdir(parents=True, exist_ok=True)
    for d in sorted(p for p in gen.iterdir() if p.is_dir()):
        inp = inputs[d.name]["input"]
        files = sorted(d.glob("*_r*.json"))
        rng = rng_for(f"gap-{d.name}")
        labels = [f"L{i}" for i in range(1, len(files) + 1)]
        rng.shuffle(labels)
        outputs, combos = {}, {}
        for label, f in zip(labels, files):
            g = json.loads(f.read_text(encoding="utf-8"))
            arm, run = g["metrics"]["arm"], g["metrics"]["r"]
            sentences = []
            for pi, p in enumerate(g["paragraphs"], start=1):
                for t in split(p["text"]):
                    sentences.append({"n": len(sentences) + 1, "paragraph": pi, "text": t})
            outputs[label] = {"sentences": sentences}
            combos[label] = (arm, run)
            key.setdefault("gap", {}).setdefault(d.name, {})[label] = {"arm": arm, "run": run}
        pairs = []
        for r in sorted({run for _, run in combos.values()}):
            pair = [lab for lab, (_, run) in combos.items() if run == r]
            rng.shuffle(pair)
            pairs.append(pair)
        (out / f"{d.name}.json").write_text(json.dumps({
            "job": d.name, "original_question": inp["question"], "topic_title": inp["topic"]["title"],
            "research_question": inp["research_question"], "gap_seeds": [s["text"] for s in inp["seeds"]],
            "evidence": [{"eid": p["eid"], "title": p["title"], "year": p["year"], "abstract": p["abstract"],
                          "excerpt": (p.get("excerpt") or {}).get("text") or ""} for p in inp["papers"]],
            "outputs": dict(sorted(outputs.items(), key=lambda kv: int(kv[0][1:]))), "pairs": pairs},
            ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-synth")
    ap.add_argument("--gen-gap")
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()
    root = HERE / f"judge_{args.tag}"
    key: dict = {}
    if args.gen_synth:
        synth_packets(HERE / args.gen_synth, root / "synth", key)
    if args.gen_gap:
        gap_packets(HERE / args.gen_gap, root / "gap", key)
    (root / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: len(v) for k, v in key.items()})


if __name__ == "__main__":
    main()
