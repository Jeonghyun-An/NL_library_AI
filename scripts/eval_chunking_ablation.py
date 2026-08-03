"""
eval_chunking_ablation.py — 고정 분할(종래) vs 의미 경계(본 발명) 대조 실험.

목적: 청킹 방식이 검색 성능(Recall@k, MRR)에 미치는 직접 효과를 정량화한다.
      특허 "발명의 효과" 근거 및 논문 ablation 자료로 사용.

방법 (통제 실험 — 청킹 방식만 다르고 나머지는 동일):
  1) book_sections.full_text 를 section_idx 순으로 이어붙여 문서 원문 복원
  2) 같은 원문에서 두 방식으로 청크 생성
       - semantic : semantic_chunk() (본 발명, BGE-M3 의미 경계)
       - fixed    : 같은 평균 크기의 고정 문자 윈도우 (의미·문장 경계 무시)
  3) 두 청크 집합을 각각 BGE-M3(dense)로 임베딩 → 인메모리 코사인 색인
  4) 동일 known-item 질의(제목/초록)로 원본 문서 순위 측정
  5) Recall@1/5/10, MRR 비교 (옵션: Jina 리랭커)

컨테이너 안에서 실행:
  docker cp scripts/eval_chunking_ablation.py nl-lib-fastapi:/app/eval_chunking_ablation.py
  docker exec -w /app nl-lib-fastapi python /app/eval_chunking_ablation.py --n 150
  # 리랭커까지:
  docker exec -w /app nl-lib-fastapi python /app/eval_chunking_ablation.py --n 150 --rerank

주의: 후보 풀 = 표본 N개 문서. N이 작으면 절대 수치는 높아지지만,
      두 방식 비교(delta)는 동일 조건이라 유효하다.
"""
import argparse
import asyncio
import json
import math
import re
import statistics

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import get_settings
from services.ingestion.embedder import embed_texts
from services.ingestion.chunker import semantic_chunk

cfg = get_settings()

_PAPER_PRED = "cnts_id LIKE 'KCI_FI%'"

_SAMPLE_SQL = f"""
    SELECT c.cnts_id,
           c.title,
           COALESCE(
               NULLIF(btrim(c.abstract),     ''),
               NULLIF(btrim(c.summary),      ''),
               NULLIF(btrim(c.introduction), '')
           ) AS semantic_src
    FROM library_catalog c
    WHERE c.is_embedded = true
      AND {_PAPER_PRED}
      AND c.title IS NOT NULL AND length(btrim(c.title)) > 3
      AND EXISTS (SELECT 1 FROM book_sections s WHERE s.book_id = c.cnts_id)
    ORDER BY md5(c.cnts_id || CAST(:seed AS text))
    LIMIT :n
"""
# setseed()+random() 은 random() 값을 힙 스캔 순서대로 배정하므로, 후보 집합이 같아도
# 행 UPDATE 로 힙 순서가 바뀌면 표본이 달라진다(실측: 30건 중 7건만 유지).
# id 해시 정렬은 힙 순서와 무관해 같은 후보 집합이면 항상 같은 표본을 준다.

_SECTIONS_SQL = """
    SELECT book_id, section_idx, full_text
    FROM book_sections
    WHERE book_id = ANY(:ids)
    ORDER BY book_id, section_idx
"""


# ── 질의 생성 (eval_search.py 와 동일 규칙) ──────────────────
def make_title_query(title: str) -> str:
    q = re.sub(r"^#+\s*", "", title or "").strip()
    return re.sub(r"\s+", " ", q)[:200]


def make_semantic_query(src: str, title: str) -> str:
    a = re.sub(r"\s+", " ", src or "").strip()
    if not a:
        return ""
    t = make_title_query(title)
    if t and t in a:
        a = a.replace(t, " ")
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


def make_body_query(full_text_: str) -> str:
    """문서 중간 본문에서 한 문장을 질의로 — 청킹의 문맥 보존력이 가장 잘 드러남."""
    a = re.sub(r"\s+", " ", full_text_ or "").strip()
    if len(a) < 200:
        return ""
    sents = re.split(r"(?<=다\.)\s|(?<=\.)\s|(?<=요\.)\s|(?<=음\.)\s", a)
    cand = [s.strip() for s in sents if 40 <= len(s.strip()) <= 200]
    if not cand:
        return ""
    return cand[len(cand) // 2]  # 중간 문장 (재현 가능)


# ── 청킹 ────────────────────────────────────────────────────
def _embed_dense(texts: list[str]) -> list[list[float]]:
    dense, _ = embed_texts(texts)
    return dense


def make_fixed_chunks(text_: str, size_chars: int, overlap_chars: int) -> list[str]:
    """의미·문장 경계를 무시한 고정 문자 윈도우 (종래 방식)."""
    t = re.sub(r"\s+\n", "\n", text_ or "").strip()
    if not t:
        return []
    step = max(1, size_chars - overlap_chars)
    out = []
    i = 0
    while i < len(t):
        seg = t[i:i + size_chars].strip()
        if seg:
            out.append(seg)
        i += step
    return out


def _normalize(mat: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(mat, axis=1, keepdims=True)
    n[n == 0] = 1e-8
    return mat / n


# ── 검색 & 지표 ─────────────────────────────────────────────
def build_index(chunk_texts: list[str], chunk_docids: list[str]):
    """청크 텍스트 → (정규화 임베딩 행렬, doc→청크인덱스 매핑)."""
    mat = _normalize(np.array(_embed_dense(chunk_texts), dtype=np.float32))
    doc_idx: dict[str, list[int]] = {}
    for i, d in enumerate(chunk_docids):
        doc_idx.setdefault(d, []).append(i)
    doc_idx = {d: np.array(v) for d, v in doc_idx.items()}
    return mat, doc_idx


def rank_of(sims: np.ndarray, doc_idx: dict, target: str) -> int | None:
    """청크 유사도 → 문서별 max 집계 → 원본 문서 순위."""
    scored = [(d, float(sims[idxs].max())) for d, idxs in doc_idx.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    for rank, (d, _) in enumerate(scored, 1):
        if d == target:
            return rank
    return None


def rank_of_rerank(sims: np.ndarray, chunk_texts, chunk_docids, target, query, rerank_fn, top_m=60):
    """상위 top_m 청크를 Jina 리랭커로 재정렬 후 문서별 max 집계."""
    top = np.argsort(-sims)[:top_m]
    texts = [chunk_texts[i] for i in top]
    ranked = rerank_fn(query, texts)
    doc_score: dict[str, float] = {}
    for r in ranked:
        ci = int(top[r.index])
        d = chunk_docids[ci]
        doc_score[d] = max(doc_score.get(d, -1e9), float(r.score))
    scored = sorted(doc_score.items(), key=lambda x: x[1], reverse=True)
    for rank, (d, _) in enumerate(scored, 1):
        if d == target:
            return rank
    return None


def summarize(ranks: list) -> dict:
    n = len(ranks)
    hit = [r for r in ranks if r is not None]

    def rec(k):
        return round(sum(1 for r in hit if r <= k) / n, 4) if n else 0.0

    return {
        "n": n,
        "R@1": rec(1), "R@5": rec(5), "R@10": rec(10),
        "MRR": round(sum(1.0 / r for r in hit) / n, 4) if n else 0.0,
        "miss": round((n - len(hit)) / n, 4) if n else 0.0,
        "median_rank": statistics.median(hit) if hit else None,
    }


def binom_two_sided(k: int, n: int) -> float:
    """양측 정확 이항검정 p (p0=0.5). scipy 없이 계산 — 컨테이너 의존성 추가 없음."""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def mcnemar(fixed_ranks: list, sem_ranks: list, k: int = 1) -> dict:
    """R@k 에 대한 McNemar 정확검정 — 동일 질의 쌍대비교라 대응표본이 맞다.

    집계값(R@1 97.0% vs 97.3%)만으로는 "차이 없음"을 주장할 수 없다.
    불일치 쌍(b, c)만이 정보를 가지므로 질의별 순위를 보존해야 계산할 수 있다.
    """
    def ok(r):
        return r is not None and r <= k

    b = sum(1 for f, s in zip(fixed_ranks, sem_ranks) if ok(f) and not ok(s))
    c = sum(1 for f, s in zip(fixed_ranks, sem_ranks) if ok(s) and not ok(f))
    return {"k": k, "fixed_only": b, "semantic_only": c, "discordant": b + c,
            "p_value": round(binom_two_sided(c, b + c), 4)}


def fmt(s: dict) -> str:
    return (f"n={s['n']:<4} R@1={s['R@1']*100:5.1f}%  R@5={s['R@5']*100:5.1f}%  "
            f"R@10={s['R@10']*100:5.1f}%  MRR={s['MRR']:.3f}  miss={s['miss']*100:4.1f}%  "
            f"med={s['median_rank']}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="표본 문서 수")
    ap.add_argument("--seed", type=float, default=0.42)
    ap.add_argument("--overlap-pct", type=float, default=0.0, help="고정 분할 오버랩 비율(0~0.5)")
    ap.add_argument("--rerank", action="store_true", help="Jina 리랭커 조건 추가")
    ap.add_argument("--out", type=str, default="/app/data/eval_chunking_ablation.json")
    args = ap.parse_args()

    # ── 표본 + 원문 로드 ──────────────────────────────────
    engine = create_async_engine(cfg.DATABASE_URL)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(_SAMPLE_SQL),
                                   {"n": args.n, "seed": str(args.seed)})).fetchall()
        ids = [r.cnts_id for r in rows]
        sec_rows = (await conn.execute(text(_SECTIONS_SQL), {"ids": ids})).fetchall()
    await engine.dispose()

    # 문서별 원문 복원 (section_idx 순 이어붙이기)
    doc_text: dict[str, list[str]] = {}
    for r in sec_rows:
        doc_text.setdefault(r.book_id, []).append(r.full_text or "")
    full_text = {bid: "\n\n".join(parts).strip() for bid, parts in doc_text.items()}

    print("=" * 74)
    print("청킹 방식 대조 실험 — 고정 분할(종래) vs 의미 경계(본 발명)")
    print("=" * 74)
    print(f"표본 문서 수 : {len(rows)} (seed={args.seed})")

    # ── 1) 의미 청킹 먼저 (평균 크기 산출용) ──────────────
    sem_texts, sem_docids, sem_lens = [], [], []
    usable = []
    for r in rows:
        ft = full_text.get(r.cnts_id, "")
        if len(ft) < 100:
            continue
        sem = semantic_chunk(ft, _embed_dense, page_map={},
                             min_tokens=cfg.MIN_CHUNK_TOKENS, max_tokens=cfg.MAX_CHUNK_TOKENS)
        chunks = [c.text for c in sem if c.text and c.text.strip()]
        if not chunks:
            continue
        usable.append(r)
        for ct in chunks:
            sem_texts.append(ct); sem_docids.append(r.cnts_id); sem_lens.append(len(ct))

    if not usable:
        print("사용 가능한 문서가 없습니다 (원문 부족).")
        return

    fixed_size = int(round(statistics.mean(sem_lens)))
    overlap = int(round(fixed_size * args.overlap_pct))
    print(f"사용 문서    : {len(usable)}  (원문 100자 이상 & 청크 생성 성공)")
    print(f"의미 청크    : {len(sem_texts)}개  (평균 {fixed_size}자/청크)")

    # ── 2) 고정 청킹 (의미 청크 평균 크기에 맞춤) ─────────
    fix_texts, fix_docids = [], []
    for r in usable:
        for ct in make_fixed_chunks(full_text[r.cnts_id], fixed_size, overlap):
            fix_texts.append(ct); fix_docids.append(r.cnts_id)
    print(f"고정 청크    : {len(fix_texts)}개  (윈도우 {fixed_size}자, 오버랩 {overlap}자)")
    print("-" * 74)

    # ── 3) 색인 (인메모리) ────────────────────────────────
    print("임베딩 중… (BGE-M3)")
    sem_mat, sem_doc_idx = build_index(sem_texts, sem_docids)
    fix_mat, fix_doc_idx = build_index(fix_texts, fix_docids)

    # ── 4) 질의 임베딩 ────────────────────────────────────
    queries = []  # (target_id, qtype, text)
    for r in usable:
        tq = make_title_query(r.title)
        if tq:
            queries.append((r.cnts_id, "title", tq))
        sq = make_semantic_query(r.semantic_src, r.title)
        if sq:
            queries.append((r.cnts_id, "abs", sq))
        bq = make_body_query(full_text.get(r.cnts_id, ""))
        if bq:
            queries.append((r.cnts_id, "body", bq))
    q_mat = _normalize(np.array(_embed_dense([q[2] for q in queries]), dtype=np.float32))

    rerank_fn = None
    if args.rerank:
        from services.search.reranker import rerank as rerank_fn

    # ── 5) 평가 ───────────────────────────────────────────
    qtypes = ("title", "abs", "body")
    buckets = {(s, q): [] for s in ("fixed", "semantic") for q in qtypes}
    buckets_rr = {k: [] for k in buckets} if args.rerank else None
    per_query = []  # 질의별 순위 원자료 — 유의성 검정·재분석의 전제

    for qi, (target, qtype, qtext) in enumerate(queries):
        qv = q_mat[qi]
        rec = {"id": target, "qtype": qtype, "query": qtext}
        for strat, mat, doc_idx, ctexts, cdocs in (
            ("fixed", fix_mat, fix_doc_idx, fix_texts, fix_docids),
            ("semantic", sem_mat, sem_doc_idx, sem_texts, sem_docids),
        ):
            sims = mat @ qv
            r = rank_of(sims, doc_idx, target)
            buckets[(strat, qtype)].append(r)
            rec[f"{strat}_rank"] = r
            if args.rerank:
                rr = rank_of_rerank(sims, ctexts, cdocs, target, qtext, rerank_fn)
                buckets_rr[(strat, qtype)].append(rr)
                rec[f"{strat}_rank_rerank"] = rr
        per_query.append(rec)
        if (qi + 1) % 50 == 0 or qi + 1 == len(queries):
            print(f"  질의 {qi+1}/{len(queries)} …")

    # ── 6) 출력 ───────────────────────────────────────────
    labels = {"title": "제목 질의", "abs": "초록 질의", "body": "본문 발췌 질의"}

    def report(bk, tag):
        print("-" * 74)
        print(f"[{tag}]  (후보 풀 = {len(usable)}개 문서)")
        stats = {}
        for qt in qtypes:
            fx = summarize(bk[("fixed", qt)])
            sm = summarize(bk[("semantic", qt)])
            mc1 = mcnemar(bk[("fixed", qt)], bk[("semantic", qt)], k=1)
            mc5 = mcnemar(bk[("fixed", qt)], bk[("semantic", qt)], k=5)
            print(f"  · {labels[qt]}")
            print(f"      고정 분할 : {fmt(fx)}")
            print(f"      의미 경계 : {fmt(sm)}")
            print(f"      Δ(의미-고정): R@1 {(sm['R@1']-fx['R@1'])*100:+.1f}%p  "
                  f"R@5 {(sm['R@5']-fx['R@5'])*100:+.1f}%p  MRR {sm['MRR']-fx['MRR']:+.3f}")
            print(f"      McNemar R@1: 의미만 맞음 {mc1['semantic_only']} / "
                  f"고정만 맞음 {mc1['fixed_only']} → p={mc1['p_value']}"
                  f"{'  (유의차 없음)' if mc1['p_value'] > 0.05 else '  (유의)'}")
            stats[f"fixed_{qt}"] = fx
            stats[f"semantic_{qt}"] = sm
            stats[f"mcnemar_{qt}"] = {"R@1": mc1, "R@5": mc5}
        return stats

    out = {"corpus": {"docs": len(usable), "sem_chunks": len(sem_texts),
                      "fixed_chunks": len(fix_texts), "fixed_size_chars": fixed_size,
                      "overlap_chars": overlap, "seed": args.seed,
                      "chunk_reduction_pct": round(
                          (len(fix_texts) - len(sem_texts)) / len(fix_texts) * 100, 2)
                      if fix_texts else None}}
    out["dense"] = report(buckets, "Dense 검색")
    if args.rerank:
        out["rerank"] = report(buckets_rr, "Dense + Jina 리랭커")
    out["per_query"] = per_query
    print("=" * 74)

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"JSON 저장: {args.out}")
    except Exception as e:
        print(f"(JSON 저장 실패: {e})")


if __name__ == "__main__":
    asyncio.run(main())
