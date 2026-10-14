"""세 질문 세트(A·B·C)를 합친 통합 분석 — 1회성 스크립트(결과는 results_pooled/ 에 같이 둔다).

입력: results/ (A, 시드 20261013) · results_v2/ (B, 20261014) · results_v3/ (C, 20261015). 서로 독립인 질문 세트다.
논문 질문만 qid 접두사로 합쳐 질의 단위 부트스트랩을 한 번에 돌린다(질문 450개). 세 세트 모두에서 잰 구성만 합친다 —
하이브리드·재작성 단독은 C 에 없고, 배포본 API(prod_api)는 C 에만 있어 합치지 않고 results_v3/ 표를 본다.

실행: python research/brochure-search-eval/pooled_analysis.py   (저장소 어디서든, 서버 불필요)
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))
from scripts import eval_brochure_search as ev  # noqa: E402

SETS = {"A": "results", "B": "results_v2", "C": "results_v3"}
POOL_ARMS = ("bm25_meta", "skovix_rerank", "skovix_norewrite", "skovix_full")
OUT = HERE / "results_pooled"
SEED = 20261014
BOOT = 5000


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def collect():
    queries, runs, judgments, metas = [], {}, {}, {}
    for tag, folder in SETS.items():
        d = HERE / folder
        q = load(d / "queries.json")
        metas[tag] = q["meta"]
        paper = [x for x in q["queries"] if x["scope"] == "paper" and x["qtype"] == "nl"]
        r = load(d / "runs.json")
        j = load(d / "judgments_vlm.json")
        for x in paper:
            qid = f"{tag}:{x['qid']}"
            queries.append({**x, "qid": qid})
            runs[qid] = {a: r[x["qid"]][a] for a in POOL_ARMS}
        for k, v in j.items():
            qid, doc = k.split("|", 1)
            judgments[f"{tag}:{qid}|{doc}"] = v
    return queries, runs, judgments, metas


def per_query(queries, runs, judgments, arm):
    out = {}
    for q in queries:
        m = ev._query_metrics(q, runs[q["qid"]][arm])
        otr = ev._query_otr(q["qid"], runs[q["qid"]][arm].get("ids", []), judgments)[0]
        out[q["qid"]] = {"r1": m["r1"], "r10": m["r10"], "ndcg": m["ndcg"], "otr": otr}
    return out


def ratio_ci(a: np.ndarray, b: np.ndarray, rng) -> tuple[float, float, float]:
    """평균(a)/평균(b) 와 질의 단위 짝 부트스트랩 95% 구간."""
    n = len(a)
    idx = rng.integers(0, n, size=(BOOT, n))
    ra = a[idx].mean(axis=1) / b[idx].mean(axis=1)
    return float(a.mean() / b.mean()), float(np.percentile(ra, 2.5)), float(np.percentile(ra, 97.5))


def main():
    OUT.mkdir(exist_ok=True)
    queries, runs, judgments, metas = collect()
    report = ev.build_report(queries, runs, judgments, seed=SEED)
    meta = {"created": "2026-10-14", "seed": "20261013·20261014·20261015",
            "corpus_docs": {"paper": "197,256~198,126"}, "question_model": metas["A"].get("question_model"),
            "report_seed": SEED}
    models = load(HERE / "results" / "judge_models.json")
    judge_info = {"judges": f"vlm={models['vlm']['label']}", "judge_names": ["vlm"],
                  "rater_check": "Claude 60쌍 일치율 81.7%, kappa 0.63 — 세트 A 의 Qwen(vlm) 판정 대상"}
    md = ev.render_markdown(report, meta, judge_info)
    md = md.replace("# 브로셔용 검색 품질 수치", "# 브로셔용 검색 품질 수치 — 세 세트 통합(논문 질문 450개)", 1)

    # 배수(구성 / 키워드) — 평균의 비, 질의 단위 짝 부트스트랩 구간
    rng = np.random.default_rng(SEED)
    pq = {a: per_query(queries, runs, judgments, a) for a in POOL_ARMS}
    ids = [q["qid"] for q in queries]
    lines = ["", "## 키워드 검색 대비 배수 (평균의 비, 질의 단위 짝 부트스트랩 95% 구간, 질문 450개)", "",
             "| 구성 | Recall@1 | Recall@10 | nDCG@10 | OTR@10 |", "|---|---|---|---|---|"]
    ratios = {}
    for arm in ("skovix_norewrite", "skovix_full"):
        cells = []
        for key in ("r1", "r10", "ndcg", "otr"):
            keep = [i for i in ids if pq[arm][i][key] is not None and pq["bm25_meta"][i][key] is not None]
            a = np.array([pq[arm][i][key] for i in keep], float)
            b = np.array([pq["bm25_meta"][i][key] for i in keep], float)
            r, lo, hi = ratio_ci(a, b, rng)
            ratios.setdefault(arm, {})[key] = {"ratio": r, "ci": [lo, hi], "n": len(keep)}
            cells.append(f"{r:.2f}배 [{lo:.2f}–{hi:.2f}]")
        lines.append(f"| {ev.ARM_LABEL[arm]} | " + " | ".join(cells) + " |")

    # 세트별 일관성
    lines += ["", "## 세트별 일관성 (논문 150문항씩)", "",
              "| 세트(시드) | 구성 | Recall@1 | Recall@10 | nDCG@10 | OTR@10 |", "|---|---|---|---|---|---|"]
    seeds = {"A": 20261013, "B": 20261014, "C": 20261015}
    for tag in SETS:
        qs = [q for q in queries if q["qid"].startswith(tag + ":")]
        g = ev.summarize_group(qs, runs, judgments, seed=SEED)
        for arm in POOL_ARMS:
            m = g["arms"][arm]
            lines.append(f"| {tag} ({seeds[tag]}) | {ev.ARM_LABEL[arm]} | {ev._pct(m['r1'])} | {ev._pct(m['r10'])} "
                         f"| {ev._dec(m['ndcg'])} | {ev._pct(m['otr'])} |")
    (OUT / "brochure_table_pooled.md").write_text(md + "\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "summary_pooled.json").write_text(
        json.dumps({"meta": meta, "judge": judge_info, "groups": report, "ratios": ratios}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print((OUT / "brochure_table_pooled.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
