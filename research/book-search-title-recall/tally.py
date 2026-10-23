"""판정 집계 — 판정 질의마다 방식 CUR·A·AH 상위 10권의 관련도(판정자 셋 평균, 0~2)를 견준다 (1회성).

    python tally.py   # judge_result.json(판정 원자료)을 읽어 judge_tally.json 을 쓰고 요약을 찍는다
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
VARIANTS = ("CUR", "A", "AH")


def ndcg(rels: list[float], ideal: list[float], k: int = 10) -> float:
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels[:k]))
    idcg = sum(r / math.log2(i + 2) for i, r in enumerate(sorted(ideal, reverse=True)[:k]))
    return dcg / idcg if idcg else 0.0


def main() -> None:
    key = json.loads((HERE / "judge" / "key.json").read_text(encoding="utf-8"))
    res = json.loads((HERE / "judge_result.json").read_text(encoding="utf-8"))["results"]
    scores: dict[str, dict[str, list[int]]] = {}
    for r in res:
        for q in r["queries"]:
            for s in q["scores"]:
                scores.setdefault(q["qid"], {}).setdefault(s["label"], []).append(s["score"])
    rows, agg = [], {v: {"top10": 0.0, "top3": 0.0, "top1": 0.0, "ndcg": 0.0, "zeros_top10": 0} for v in VARIANTS}
    for qid, k in sorted(key.items()):
        mean = {lab: sum(v) / len(v) for lab, v in scores[qid].items()}
        ideal = list(mean.values())
        row = {"qid": qid, "query": k["query"]}
        for v in VARIANTS:
            rels = [mean[lab] for lab in k["ranks"][v]]
            m = {"top10": sum(rels[:10]), "top3": sum(rels[:3]), "top1": rels[0] if rels else 0.0,
                 "ndcg": ndcg(rels, ideal), "zeros_top10": sum(1 for x in rels[:10] if x < 0.5)}
            row[v] = {kk: round(vv, 3) for kk, vv in m.items()}
            for kk in agg[v]:
                agg[v][kk] += m[kk]
        rows.append(row)
    n = len(rows)
    summary = {v: {kk: round(vv / n, 3) for kk, vv in m.items()} for v, m in agg.items()}
    (HERE / "judge_tally.json").write_text(json.dumps({"summary": summary, "queries": rows}, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(f"판정 질의 {n}개 — 질의당 평균 (관련도 0~2, 판정자 셋 평균)")
    for v, m in summary.items():
        print(f"  {v:3} 상위10 합 {m['top10']:5.2f} · 상위3 합 {m['top3']:4.2f} · 1위 {m['top1']:4.2f} · nDCG@10 {m['ndcg']:.3f}"
              f" · 상위10 중 무관(평균<0.5) {m['zeros_top10']:.2f}")
    print("질의별 상위10 합 (CUR → A → AH):")
    for r in rows:
        print(f"  {r['qid']} {r['query'][:22]:22} {r['CUR']['top10']:5.2f} → {r['A']['top10']:5.2f} → {r['AH']['top10']:5.2f}"
              f" | 1위 {r['CUR']['top1']:.2f} → {r['A']['top1']:.2f} → {r['AH']['top1']:.2f}")


if __name__ == "__main__":
    main()
