"""판정 집계 — judge_key.json(짝→X/Y 변형) + votes.json(판정자별 승자) → 변형별 승·패·비김."""
import json, sys
from collections import defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
key = json.loads((here.parent / "judge_key.json").read_text(encoding="utf-8"))
votes = json.loads((here / "votes.json").read_text(encoding="utf-8"))

def outcome(pair, w):
    k = key[pair]
    cand = k["candidate"]
    other = "Y" if k["X"] == cand else "X"
    assert k[other] == "base", (pair, k)
    if w == "tie":
        return cand, "T"
    return cand, ("W" if k[w] == cand else "L")

by_judge = defaultdict(lambda: defaultdict(lambda: {"W": 0, "L": 0, "T": 0}))
by_report = defaultdict(lambda: defaultdict(lambda: {"W": 0, "L": 0, "T": 0}))
total = defaultdict(lambda: {"W": 0, "L": 0, "T": 0})
rows = []
for judge, vs in votes.items():
    for pair, w in sorted(vs.items()):
        cand, r = outcome(pair, w)
        by_judge[cand][judge][r] += 1
        by_report[cand][key[pair]["tag"]][r] += 1
        total[cand][r] += 1
        rows.append((pair, key[pair]["tag"], cand, judge, w, r))

fmt = lambda d: f"{d['W']}-{d['L']}-{d['T']}"
print("== 짝별(후보 기준 W/L/T)")
for pair in sorted(key):
    k = key[pair]
    rs = [outcome(pair, votes[j][pair])[1] for j in ("reader", "fact", "editor")]
    print(f"{pair} {k['tag']} {k['candidate']:8s} X={k['X']:8s} Y={k['Y']:8s} reader={rs[0]} fact={rs[1]} editor={rs[2]}")
print("\n== 변형 × 판정자 (승-패-비김, 후보 vs base)")
for c in ("focus", "attrib", "concise"):
    print(f"{c:8s} " + "  ".join(f"{j}={fmt(by_judge[c][j])}" for j in ("reader", "fact", "editor")) + f"  합계={fmt(total[c])}")
print("\n== 변형 × 보고서 (판정자 셋 합)")
for c in ("focus", "attrib", "concise"):
    print(f"{c:8s} " + "  ".join(f"{t}={fmt(by_report[c][t])}" for t in ("630e", "d60a", "85d2", "9ba1")))
print("\n== base 쪽 기록(판정자 셋 합): ", end="")
b = {"W": sum(total[c]["L"] for c in total), "L": sum(total[c]["W"] for c in total), "T": sum(total[c]["T"] for c in total)}
print(fmt(b))
print("\n== 판정 기준: 승 >= 2*패, 사실 검증자(fact)에게 패 > 승 아님")
for c in ("focus", "attrib", "concise"):
    t = total[c]; f = by_judge[c]["fact"]
    ok = t["W"] >= 2 * t["L"] and not (f["L"] > f["W"])
    print(f"{c:8s} 승{t['W']} 패{t['L']} 비{t['T']}  fact {fmt(f)}  → 판정 기준 {'통과' if ok else '미달'}")
