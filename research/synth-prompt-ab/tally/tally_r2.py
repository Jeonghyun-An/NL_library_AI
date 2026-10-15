"""2차 판정 집계 — r2_key.json(짝→X/Y 변형) + votes_r2.json(판정자별 승자) → focus2 대 focus 승·패·비김.

판정자별·보고서별·위치별(focus2 가 X 였나 Y 였나)·다듬을 때 쓴 보고서 여부로 나눠 센다.
"""
import json
from collections import defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
key = json.loads((here.parent / "r2_key.json").read_text(encoding="utf-8"))
votes = json.loads((here / "votes_r2.json").read_text(encoding="utf-8"))
CAND, BASE = "focus2", "focus"
JUDGES = ("reader", "fact", "editor")
TUNED = {"630e", "9ba1"}  # focus2 를 다듬을 때 쓴 보고서


def outcome(pair, w):
    k = key[pair]
    assert {k["X"], k["Y"]} == {CAND, BASE}, (pair, k)
    if w == "tie":
        return "T"
    return "W" if k[w] == CAND else "L"


def new():
    return {"W": 0, "L": 0, "T": 0}


fmt = lambda d: f"{d['W']}-{d['L']}-{d['T']}"
by_judge = defaultdict(new)
by_report = defaultdict(new)
by_pos = defaultdict(new)
by_tuned = defaultdict(new)
by_judge_tuned = defaultdict(new)
total = new()
raw_xy = defaultdict(int)
for j in JUDGES:
    for pair, w in votes[j].items():
        r = outcome(pair, w)
        k = key[pair]
        pos = "X" if k["X"] == CAND else "Y"
        tuned = "다듬은 보고서(630e·9ba1)" if k["tag"] in TUNED else "안 본 보고서(d60a·85d2)"
        by_judge[j][r] += 1
        by_report[k["tag"]][r] += 1
        by_pos[pos][r] += 1
        by_tuned[tuned][r] += 1
        by_judge_tuned[(j, tuned)][r] += 1
        total[r] += 1
        raw_xy[w] += 1

print("== 짝별 (focus2 기준 W/L/T)")
for pair in sorted(key):
    k = key[pair]
    rs = [outcome(pair, votes[j][pair]) for j in JUDGES]
    print(f"{pair} {k['tag']} r{k['run']} X={k['X']:7s} Y={k['Y']:7s} " + " ".join(f"{j}={r}" for j, r in zip(JUDGES, rs)))
print("\n== 판정자별 (focus2 승-패-비김)")
print("  ".join(f"{j}={fmt(by_judge[j])}" for j in JUDGES) + f"  합계={fmt(total)}")
print("\n== 보고서별 (판정자 셋 합)")
print("  ".join(f"{t}={fmt(by_report[t])}" for t in ("630e", "d60a", "85d2", "9ba1")))
print("\n== 다듬을 때 쓴 보고서 여부 (판정자 셋 합 / 판정자별)")
for t in ("다듬은 보고서(630e·9ba1)", "안 본 보고서(d60a·85d2)"):
    print(f"{t}: {fmt(by_tuned[t])}  " + "  ".join(f"{j}={fmt(by_judge_tuned[(j, t)])}" for j in JUDGES))
print("\n== 위치별 (focus2 가 X 일 때 / Y 일 때)")
print(f"X={fmt(by_pos['X'])}  Y={fmt(by_pos['Y'])}")
print(f"판정자 고른 글자 수: X {raw_xy['X']} · Y {raw_xy['Y']} · 비김 {raw_xy['tie']}")
print("\n== 판정 기준: 승 > 패, 사실 검증자(fact)에게 패 > 승 아님")
f = by_judge["fact"]
ok = total["W"] > total["L"] and not (f["L"] > f["W"])
print(f"focus2 승{total['W']} 패{total['L']} 비{total['T']}  fact {fmt(f)}  → 판정 기준 {'통과' if ok else '미달'}")
