"""자동 지표 — 팔(모델)마다 형식·속도·모양 (판정 없이 생성 파일만 본다, 1회성).

종합(gen_synth_*): 호출 수·형식 문제(JSON 파싱 실패·모양)·전송 실패·reasoning 칸에 든 호출, 호출 시간 중앙값·90%, 생성 토큰/초(usage), 절 실패,
빈 요약·한 문장 요약, 도입 첫 문장 [E#] 비율, 향후 과제 줄의 '하위질문' 누출.
공백 절(gen_gap_*/metrics.json): 근거 표시 없는 문장·확인 필요 숫자·지운 [E#]·제목 언급·다시 부른 횟수·시간.

    python tally_auto.py --gen-synth gen_synth_aa --gen-gap gen_gap_aa
"""
import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
_SENT = re.compile(r"(?<=[.!?])\s+")
_CITE = re.compile(r"\[E\d+\]")


def pct(xs: list[float], q: float):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 1)


def synth(gen: Path) -> dict:
    out = defaultdict(lambda: defaultdict(float))
    secs, tps = defaultdict(list), defaultdict(list)
    for f in sorted(gen.glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        a = g["arm"]
        t = out[a]
        t["reports"] += 1
        t["report_errors"] += bool(g.get("error"))
        for c in g.get("calls") or []:
            t["calls"] += 1
            t["format_issues"] += bool(c.get("issues"))
            t["send_errors"] += bool(c.get("error"))
            t["reasoning_calls"] += bool(c.get("reasoning"))   # 답이나 생각이 reasoning 칸에 든 호출(Gemma 4)
            if c.get("sec") is not None:
                secs[a].append(c["sec"])
            ct = (c.get("usage") or {}).get("completion_tokens")
            if ct and c.get("sec"):
                tps[a].append(ct / c["sec"])
        for s in g.get("sections") or []:
            t["sections"] += 1
            t["failed_sections"] += bool(s.get("failed"))
            first = next(iter(_SENT.split((s.get("intro") or "").strip())), "")
            t["intro_first_cited"] += bool(_CITE.search(first))
            for p in s.get("papers") or []:
                t["summaries"] += 1
                sm = (p.get("summary") or "").strip()
                t["empty_summaries"] += not sm
                t["one_sentence_summaries"] += bool(sm) and len([x for x in _SENT.split(sm) if x.strip()]) == 1
            for fu in s.get("future") or []:
                t["future_lines"] += 1
                t["future_leaks"] += bool(re.search(r"하위\s*질문", fu.get("text", "")))
    res = {}
    for a, t in out.items():
        res[a] = {**{k: int(v) for k, v in t.items()},
                  "call_sec_median": pct(secs[a], 0.5), "call_sec_p90": pct(secs[a], 0.9),
                  "gen_tokens_per_sec_median": round(statistics.median(tps[a]), 1) if tps[a] else None}
    return res


def gap(gen: Path) -> dict:
    ms = json.loads((gen / "metrics.json").read_text(encoding="utf-8"))
    res = {}
    for a in sorted({m["arm"] for m in ms}):
        xs = [m for m in ms if m["arm"] == a]
        res[a] = {"outputs": len(xs), **{k: sum(m[k] for m in xs) for k in
                  ("paragraphs", "unmarked", "numbers", "dropped", "titles", "attempts", "completion_tokens")},
                  "outputs_with_unmarked": sum(1 for m in xs if m["unmarked"]),
                  "reasoning_attempts": sum(m.get("reasoning_attempts", 0) for m in xs),
                  "sec_median": pct([m["sec"] for m in xs], 0.5), "sec_p90": pct([m["sec"] for m in xs], 0.9)}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-synth")
    ap.add_argument("--gen-gap")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    res = {}
    if args.gen_synth:
        res["synth"] = synth(HERE / args.gen_synth)
    if args.gen_gap:
        res["gap"] = gap(HERE / args.gen_gap)
    text = json.dumps(res, ensure_ascii=False, indent=1)
    print(text)
    if args.out:
        (HERE / args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
