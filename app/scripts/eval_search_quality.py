"""eval_search_quality.py — 골든 쿼리 세트로 검색 품질을 수치화.

배경
----
청킹 방식·리랭커·라우팅 로직처럼 검색 결과에 영향을 주는 변경을 할 때마다
"품질이 좋아졌는지"를 감으로 판단해왔다. 이 스크립트는 build_golden_queries.py로
만든 "이 질의엔 이 책/논문이 나와야 한다" 쌍을 실제 검색 파이프라인
(services.search.pipeline.search, API 엔드포인트와 동일한 함수)에 그대로
통과시켜 Recall@1/5/10과 MRR(정답이 몇 번째 순위에 나왔는지의 역수 평균)을 낸다.

파이프라인 변경 전후로 같은 골든 세트에 대해 이 스크립트를 두 번 돌리고
--out 리포트 두 개를 비교하면 "실제로 좋아졌는지 나빠졌는지"가 숫자로 나온다.

읽기 전용이다. search()는 검색·리랭킹만 수행하고 DB에 쓰지 않는다.

사용법
------
    docker exec -w /app nl-lib-fastapi python -m scripts.eval_search_quality \
        --golden /app/data/golden_queries.json \
        --out /app/data/eval_report_$(date +%Y%m%d_%H%M).json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time

from db.postgres import AsyncSessionLocal
from services.search.pipeline import search

TOP_K_CUTOFFS = (1, 5, 10)


async def _eval_one(entry: dict, top_k: int, db) -> dict:
    t0 = time.perf_counter()
    try:
        resp = await search(
            entry["query"],
            mode="book",
            top_k=top_k,
            doc_scope=entry.get("doc_scope", "all"),
            db=db,
        )
    except Exception as e:
        return {**entry, "error": str(e)[:300], "rank": None, "elapsed_ms": None}

    rank = None
    for i, b in enumerate(resp.books, start=1):
        if b.book_id == entry["expected_book_id"]:
            rank = i
            break

    return {
        **entry,
        "rank": rank,
        "returned": len(resp.books),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


async def _eval_all(golden: list[dict], top_k: int, db) -> list[dict]:
    results = []
    for i, entry in enumerate(golden, 1):
        r = await _eval_one(entry, top_k, db)
        mark = f"rank={r['rank']}" if r.get("rank") else ("ERROR" if "error" in r else "not_found")
        ms = f" ({r['elapsed_ms']}ms)" if r.get("elapsed_ms") else ""
        print(f"[{i}/{len(golden)}] {entry['query'][:40]!r} → {mark}{ms}", flush=True)
        results.append(r)
    return results


def _recall_at(results: list[dict], k: int) -> float:
    hits = [r for r in results if r["rank"] is not None and r["rank"] <= k]
    return len(hits) / len(results) if results else 0.0


def _mrr(results: list[dict]) -> float:
    scores = [1 / r["rank"] if r["rank"] else 0.0 for r in results]
    return sum(scores) / len(scores) if scores else 0.0


def _print_report(results: list[dict], top_k: int) -> dict:
    ok = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]

    summary = {
        "n_queries": len(results),
        "n_errors": len(errored),
        **{f"recall_at_{k}": round(_recall_at(ok, k), 3) for k in TOP_K_CUTOFFS if k <= top_k},
        "mrr": round(_mrr(ok), 3),
        "avg_elapsed_ms": round(statistics.mean(r["elapsed_ms"] for r in ok), 1) if ok else None,
        "not_found": sum(1 for r in ok if r["rank"] is None),
    }

    by_type: dict[str, list[dict]] = {}
    for r in ok:
        by_type.setdefault(r.get("query_type", "unknown"), []).append(r)

    print(f"\n{'='*50}")
    print(f"전체 {summary['n_queries']}건 (오류 {summary['n_errors']}건)")
    for k in TOP_K_CUTOFFS:
        if k <= top_k:
            print(f"  Recall@{k}: {summary[f'recall_at_{k}']:.1%}")
    print(f"  MRR:       {summary['mrr']:.3f}")
    print(f"  미검출:     {summary['not_found']}/{len(ok)}건")
    print(f"  평균 응답:  {summary['avg_elapsed_ms']} ms")
    print(f"{'='*50}")
    print("유형별 Recall@10:")
    for qtype, rs in by_type.items():
        print(f"  {qtype:10s} (n={len(rs):3d})  {_recall_at(rs, min(10, top_k)):.1%}")

    if summary["not_found"]:
        print(f"\n미검출 질의 예시 (최대 5건):")
        for r in [r for r in ok if r["rank"] is None][:5]:
            print(f"  - \"{r['query']}\" → {r['expected_book_id']} ({r.get('title','')[:30]})")

    return summary


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default="/app/data/golden_queries.json")
    ap.add_argument("--out", default=None, help="상세 결과 JSON 저장 경로 (미지정 시 저장 안 함)")
    ap.add_argument("--top-k", type=int, default=10)
    args = ap.parse_args()

    with open(args.golden, encoding="utf-8") as f:
        golden = json.load(f)
    print(f"골든 쿼리 {len(golden)}건 로드: {args.golden}")

    async with AsyncSessionLocal() as db:
        results = await _eval_all(golden, args.top_k, db)

    summary = _print_report(results, args.top_k)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
        print(f"\n상세 리포트 저장: {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
