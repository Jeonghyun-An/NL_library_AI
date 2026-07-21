"""검색 품질 평가 하니스 — known-item retrieval.

목적: 보고용 정량 수치(Recall@k, MRR)를 실제 운영 색인에서 측정한다.

방법:
  1) is_embedded=true 인 KCI 논문을 무작위 표본 추출 (재현 가능한 seed).
  2) 논문마다 2종 질의 생성:
       - 제목 질의  : 정확 제목 → 고유명사/known-item 매칭 측정
       - 초록 질의  : 초록 앞부분(제목 토큰 제거) → 의미검색 측정
  3) 각 질의를 pipeline.search()로 실행. 리랭커 off/on 두 조건.
     (use_rewrite=False, db=None → LLM 호출 없이 순수 검색 랭킹만 측정)
  4) 원본 논문이 결과 몇 위에 오는지로 Recall@1/5/10, MRR 집계.

실행 (서버, nl-lib 네트워크 위 컨테이너 안):
  docker cp scripts/eval_search.py nl-lib-fastapi:/app/eval_search.py
  docker exec -w /app nl-lib-fastapi python /app/eval_search.py --n 150

두 가지 실행 모드:
  (기본) in-process  : pipeline.search() 직접 호출. 제목점수 후보정 없는 순수
                       검색 랭킹 → 리랭커 delta 가 깨끗함. 단, docker exec 는
                       새 프로세스라 BGE-M3/리랭커를 새로 로드(GPU ~3.4GB 추가).
  --http             : 이미 떠 있는 서버의 /api/papers/search 호출. 로드된 모델
                       재사용(추가 GPU 0). GPU 여유 없을 때 사용. 단 엔드포인트가
                       제목 일치율 후보정을 적용하므로 제목질의 리랭커 delta 는
                       가려질 수 있음(초록질의 delta 는 유효).
"""
import argparse
import asyncio
import json
import re
import statistics
import sys
import time

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import get_settings
from services.search.pipeline import search
from services.ingestion.indexer import ensure_collection

cfg = get_settings()

# 운영 색인은 KCI 논문이 book_id 접두어 'KCI_FI%' 로 식별된다.
_PAPER_PRED = "cnts_id LIKE 'KCI_FI%'"

_COUNT_SQL = f"""
    SELECT count(*) FROM library_catalog
    WHERE is_embedded = true AND {_PAPER_PRED}
"""

_SAMPLE_SQL = f"""
    SELECT cnts_id,
           title,
           COALESCE(
               NULLIF(btrim(abstract),     ''),
               NULLIF(btrim(summary),      ''),
               NULLIF(btrim(introduction), '')
           ) AS semantic_src
    FROM library_catalog
    WHERE is_embedded = true
      AND {_PAPER_PRED}
      AND title IS NOT NULL AND length(btrim(title)) > 3
    ORDER BY random()
    LIMIT :n
"""


def make_title_query(title: str) -> str:
    """제목 질의 — 마크다운/공백 정리."""
    q = re.sub(r"^#+\s*", "", title or "").strip()
    return re.sub(r"\s+", " ", q)[:200]


def make_semantic_query(src: str, title: str) -> str:
    """의미검색 질의 — 초록/요약/소개 앞부분에서 제목 토큰을 제거해 제목 매칭으로 새지 않게 한다."""
    a = re.sub(r"\s+", " ", src or "").strip()
    if not a:
        return ""
    t = make_title_query(title)
    if t and t in a:
        a = a.replace(t, " ")
    # 한국어 문장 경계로 앞 1~2문장(약 120자 이상) 확보
    parts = re.split(r"(?<=다\.)\s|(?<=\.)\s|(?<=요\.)\s|(?<=음\.)\s", a)
    q = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        q = (q + " " + p).strip()
        if len(q) >= 120:
            break
    q = re.sub(r"\s+", " ", q)[:220].strip()
    return q if len(q) >= 20 else ""


def _rank_of(ids: list, target_id: str):
    try:
        return ids.index(target_id) + 1
    except ValueError:
        return None


async def run_inprocess(query: str, target_id: str, use_rerank: bool, _client=None):
    """단건 검색 (pipeline.search 직접) → (순위 or None, 지연 ms)."""
    t0 = time.perf_counter()
    resp = await search(
        query,
        mode="book",
        top_k=20,
        use_rewrite=False,
        use_rerank=use_rerank,
        doc_scope="paper",
        db=None,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    return _rank_of([b.book_id for b in resp.books], target_id), elapsed


async def run_http(query: str, target_id: str, use_rerank: bool, client: httpx.AsyncClient):
    """단건 검색 (HTTP /api/papers/search) → (순위 or None, 지연 ms)."""
    t0 = time.perf_counter()
    r = await client.post(
        "/api/papers/search",
        json={"query": query, "mode": "book", "top_k": 20,
              "use_rewrite": False, "use_rerank": use_rerank},
    )
    r.raise_for_status()
    elapsed = (time.perf_counter() - t0) * 1000
    books = r.json().get("books", [])
    return _rank_of([b["book_id"] for b in books], target_id), elapsed


def summarize(ranks: list, latencies: list) -> dict:
    n = len(ranks)
    hit = [r for r in ranks if r is not None]

    def recall_at(k: int) -> float:
        return sum(1 for r in hit if r <= k) / n if n else 0.0

    mrr = (sum(1.0 / r for r in hit) / n) if n else 0.0
    lat = sorted(latencies)

    def pct(p: float):
        if not lat:
            return None
        i = min(len(lat) - 1, int(round(p * (len(lat) - 1))))
        return round(lat[i], 1)

    return {
        "n": n,
        "hits": len(hit),
        "miss_rate": round((n - len(hit)) / n, 4) if n else 0.0,
        "R@1": round(recall_at(1), 4),
        "R@5": round(recall_at(5), 4),
        "R@10": round(recall_at(10), 4),
        "MRR": round(mrr, 4),
        "median_rank": statistics.median(hit) if hit else None,
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
    }


def _fmt(s: dict) -> str:
    return (
        f"n={s['n']:<4} "
        f"R@1={s['R@1']*100:5.1f}%  "
        f"R@5={s['R@5']*100:5.1f}%  "
        f"R@10={s['R@10']*100:5.1f}%  "
        f"MRR={s['MRR']:.3f}  "
        f"miss={s['miss_rate']*100:4.1f}%  "
        f"med_rank={s['median_rank']}  "
        f"p50={s['p50_ms']}ms p95={s['p95_ms']}ms"
    )


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="표본 논문 수")
    ap.add_argument("--seed", type=float, default=0.42, help="setseed 값 (재현용)")
    ap.add_argument("--out", type=str, default="/app/data/eval_search_result.json")
    ap.add_argument("--http", action="store_true",
                    help="in-process 대신 실행 중인 서버 HTTP 엔드포인트 호출 (GPU 재로드 회피)")
    ap.add_argument("--base-url", type=str, default="http://localhost:8000",
                    help="--http 모드의 서버 주소 (컨테이너 내부: http://localhost:8000)")
    args = ap.parse_args()

    # ── 코퍼스 규모 확인 ──────────────────────────────────
    col = ensure_collection()
    n_chunks = col.num_entities

    engine = create_async_engine(cfg.DATABASE_URL)
    async with engine.connect() as conn:
        total_papers = (await conn.execute(text(_COUNT_SQL))).scalar() or 0
        await conn.execute(text("SELECT setseed(:s)"), {"s": args.seed})
        rows = (await conn.execute(text(_SAMPLE_SQL), {"n": args.n})).fetchall()
    await engine.dispose()

    print("=" * 72)
    print("검색 품질 평가 (known-item retrieval)")
    print("=" * 72)
    print(f"Milvus 컬렉션      : {cfg.MILVUS_COLLECTION}")
    print(f"총 청크(벡터) 수   : {n_chunks:,}")
    print(f"임베딩된 논문 수   : {total_papers:,}  ← 이 안에서 원본을 찾아내는 문제")
    print(f"표본 질의 논문 수  : {len(rows)} (seed={args.seed})")
    print(f"실행 모드          : {'HTTP ' + args.base_url if args.http else 'in-process pipeline.search()'}")
    if total_papers < 200:
        print("⚠️  임베딩 논문이 200건 미만 — 후보 풀이 작아 수치가 과대평가됩니다.")
    print("-" * 72)
    if not rows:
        print("표본 없음. is_embedded 논문이 있는지 확인하세요.")
        sys.exit(1)

    # ── 질의 세트 구성 ────────────────────────────────────
    samples = []
    n_sem = 0
    for r in rows:
        tq = make_title_query(r.title)
        sq = make_semantic_query(r.semantic_src, r.title)
        if sq:
            n_sem += 1
        samples.append({"id": r.cnts_id, "title_q": tq, "abs_q": sq})
    print(f"의미검색 질의 가능   : {n_sem}/{len(rows)} (초록/요약/소개 보유)")
    print("-" * 72)

    # ── 평가 루프 ─────────────────────────────────────────
    # 조건: (질의종류 title/abstract) × (리랭커 off/on)
    results = {
        "title_norerank": {"ranks": [], "lat": []},
        "title_rerank":   {"ranks": [], "lat": []},
        "abs_norerank":   {"ranks": [], "lat": []},
        "abs_rerank":     {"ranks": [], "lat": []},
    }

    runner = run_http if args.http else run_inprocess
    client = (httpx.AsyncClient(base_url=args.base_url, timeout=120.0)
              if args.http else None)

    total_q = len(samples)
    try:
        for i, s in enumerate(samples, 1):
            for qkey, q in (("title", s["title_q"]), ("abs", s["abs_q"])):
                if not q:
                    continue
                for rr in (False, True):
                    try:
                        rank, lat = await runner(q, s["id"], rr, client)
                    except Exception as e:
                        print(f"  [경고] 질의 실패 ({s['id']}, {qkey}, rerank={rr}): {e}")
                        rank, lat = None, 0.0
                    bucket = f"{qkey}_{'rerank' if rr else 'norerank'}"
                    results[bucket]["ranks"].append(rank)
                    results[bucket]["lat"].append(lat)
            if i % 10 == 0 or i == total_q:
                print(f"  진행 {i}/{total_q} …")
    finally:
        if client is not None:
            await client.aclose()

    # ── 집계 ──────────────────────────────────────────────
    summary = {k: summarize(v["ranks"], v["lat"]) for k, v in results.items()}

    print("-" * 72)
    print("[제목 질의 — 고유명사/known-item 매칭]")
    print(f"  리랭커 OFF : {_fmt(summary['title_norerank'])}")
    print(f"  리랭커 ON  : {_fmt(summary['title_rerank'])}")
    print("[초록 질의 — 의미검색]")
    print(f"  리랭커 OFF : {_fmt(summary['abs_norerank'])}")
    print(f"  리랭커 ON  : {_fmt(summary['abs_rerank'])}")
    print("=" * 72)

    def delta(off, on, key):
        return f"{summary[off][key]*100:.1f}% → {summary[on][key]*100:.1f}%"

    print("보고서용 delta (리랭커 적용 효과):")
    print(f"  제목  Recall@5 : {delta('title_norerank','title_rerank','R@5')}")
    print(f"  초록  Recall@5 : {delta('abs_norerank','abs_rerank','R@5')}")
    print(f"  초록  Recall@10: {delta('abs_norerank','abs_rerank','R@10')}")
    print(f"  초록  MRR      : {summary['abs_norerank']['MRR']:.3f} → {summary['abs_rerank']['MRR']:.3f}")
    print("=" * 72)

    out = {
        "corpus": {"chunks": n_chunks, "embedded_papers": total_papers,
                   "sample": len(rows), "seed": args.seed},
        "summary": summary,
    }
    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"JSON 저장: {args.out}")
    except Exception as e:
        print(f"(JSON 저장 실패, stdout 로 충분: {e})")


if __name__ == "__main__":
    asyncio.run(main())
