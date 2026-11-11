"""
check_embedding_backend.py — 공용 bge-m3(http, vLLM)가 프로세스 안 FlagEmbedding(local)과 같은 값을 내는지 운영 데이터로 본다.

언제: EMBEDDING_BACKEND 를 http 로 바꾸기 전, 그리고 공용 서버의 vLLM 이미지나 실행 옵션을 바꾼 뒤.

무엇을 보나:
  1) 저장 벡터 — Milvus 의 메타 청크(chunk_idx=-1) N개. 적재 때 FlagEmbedding(fp16, GPU)이 만들어 저장한 dense·sparse 와,
     같은 텍스트를 지금 local·http 로 다시 낸 값을 비교한다. local 대 저장값이 '원래 생기는 차이'의 기준이다.
  2) 검색 — 예시 질의와 표본 자료의 제목으로 local·http 질의 벡터를 각각 만들어 같은 하이브리드 검색(search_chunks,
     상위 10)을 돌리고 결과가 얼마나 겹치는지, 제목 질의가 자기 자료를 찾는지 본다.

판정 기준 — 2026-11-11 이 PC(CPU, fp32·fp16)에서 잰 차이(dense 코사인 ≥ 0.999998, sparse 토큰 집합 일치, 가중치 차 ≤ 0.0006)
보다 넉넉하게 잡았다: dense 코사인 최저 ≥ 0.999, sparse 토큰 집합 일치율(Jaccard) 평균 ≥ 0.99, 검색 상위 10 겹침 평균 ≥ 0.9.
기준을 넘지 못해도 바로 실패는 아니다 — 숫자를 보고 사람이 판단한다(local 대 저장값 차이와 견준다).

실행(컨테이너 안 — EMBEDDING_BACKEND 값과 상관없이 두 갈래를 모두 부른다):
  docker exec -w /app nl-lib-fastapi python -m scripts.check_embedding_backend --n 50
local 갈래는 이 프로세스에 bge-m3 를 한 벌 더 올린다(GPU 약 2~3GB, 스크립트가 끝나면 내려간다).
"""
import argparse
import math
import random
import statistics
import time

from core.config import get_settings
from services.ingestion import embedder
from services.ingestion.indexer import ensure_collection, search_chunks

cfg = get_settings()

EXAMPLE_QUERIES = [
    "노인 사회적 지지 우울",
    "독거노인의 사회적 고립과 우울",
    "청소년 스마트폰 과의존과 학업 성취",
    "지방재정 건전성 평가",
    "기후변화 적응 정책",
    "다문화 가정 아동의 언어 발달",
    "공공도서관 이용 만족도",
    "한국 현대시의 서정성",
]
DENSE_MIN_COS = 0.999
SPARSE_MIN_JACCARD = 0.99
SEARCH_MIN_OVERLAP = 0.9
TOP_K = 10


def _cos(a, b) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else float("nan")


def _as_sparse(s) -> dict[int, float]:
    return {int(k): float(v) for k, v in dict(s).items()}


def _sparse_diff(a, b) -> tuple[float, float]:
    """(토큰 집합 Jaccard, 겹치는 토큰의 가중치 최대 차)."""
    a, b = _as_sparse(a), _as_sparse(b)
    union = set(a) | set(b)
    inter = set(a) & set(b)
    jac = len(inter) / len(union) if union else 1.0
    return jac, max((abs(a[k] - b[k]) for k in inter), default=0.0)


def _summary(name: str, values: list[float], fmt: str = ".6f") -> str:
    if not values:
        return f"{name}: (없음)"
    return (f"{name}: 최저 {min(values):{fmt}} · 평균 {statistics.fmean(values):{fmt}} · "
            f"중앙 {statistics.median(values):{fmt}} (n={len(values)})")


def _meta_rows(n: int, seed: int) -> tuple[list[dict], bool]:
    """메타 청크 N개 — 저장 sparse 를 꺼낼 수 없는 판이면 dense 만."""
    col = ensure_collection()
    offset = random.Random(seed).randrange(0, 5000)
    fields = ["book_id", "text", "embedding", "sparse_embedding"]
    try:
        rows = col.query(expr="chunk_idx == -1", output_fields=fields, offset=offset, limit=n)
        return rows, True
    except Exception as e:   # 저장 sparse 를 돌려주지 않는 판 — dense 만 비교한다
        print(f"(저장 sparse 를 꺼내지 못해 dense 만 비교: {type(e).__name__}: {e})")
        rows = col.query(expr="chunk_idx == -1", output_fields=fields[:3], offset=offset, limit=n)
        return rows, False


def _title(meta_text: str) -> str | None:
    """메타 청크 텍스트('제목: … | 기관: … | …', stages.run_embed_index)의 제목."""
    head = meta_text.split(" | ", 1)[0]
    if not head.startswith("제목: "):
        return None
    return head[len("제목: "):].strip() or None


def _hits(dense, sparse) -> list[tuple[str, str]]:
    """상위 TOP_K 의 (chunk_id, book_id)."""
    return [(h.chunk_id, h.book_id) for h in search_chunks(dense, sparse, top_k=TOP_K)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=50, help="비교할 메타 청크 수(기본 50)")
    ap.add_argument("--seed", type=int, default=11, help="표본 위치를 고르는 씨앗")
    args = ap.parse_args()

    print(f"공용 서버: dense {cfg.EMBEDDING_DENSE_URL} · sparse {cfg.EMBEDDING_SPARSE_URL} · "
          f"모델 {cfg.EMBEDDING_MODEL_NAME} · max_length {cfg.EMBEDDING_MAX_LENGTH} · 지금 갈래 {cfg.EMBEDDING_BACKEND}")

    # ── 1) 저장 벡터 ────────────────────────────────────
    rows, has_sparse = _meta_rows(args.n, args.seed)
    texts = [r["text"] for r in rows]
    print(f"\n[1] 저장 벡터 — 메타 청크 {len(rows)}개")
    t = time.perf_counter()
    d_http, s_http = embedder._embed_http(texts, need_sparse=True)
    t_http = time.perf_counter() - t
    t = time.perf_counter()
    d_local, s_local = embedder._embed_local(texts)
    t_local = time.perf_counter() - t
    print(f"  걸린 시간: http {t_http:.2f}s · local {t_local:.2f}s(첫 호출은 모델 올리는 시간 포함)")
    cos_http = [_cos(r["embedding"], d) for r, d in zip(rows, d_http)]
    cos_local = [_cos(r["embedding"], d) for r, d in zip(rows, d_local)]
    print("  " + _summary("dense 코사인 저장↔http ", cos_http))
    print("  " + _summary("dense 코사인 저장↔local", cos_local))
    if has_sparse:
        sp_http = [_sparse_diff(r["sparse_embedding"], s) for r, s in zip(rows, s_http)]
        sp_local = [_sparse_diff(r["sparse_embedding"], s) for r, s in zip(rows, s_local)]
        print("  " + _summary("sparse 토큰 일치 저장↔http ", [j for j, _ in sp_http], ".4f"))
        print("  " + _summary("sparse 토큰 일치 저장↔local", [j for j, _ in sp_local], ".4f"))
        print("  " + _summary("sparse 가중치 최대 차 저장↔http ", [m for _, m in sp_http], ".4f"))
        print("  " + _summary("sparse 가중치 최대 차 저장↔local", [m for _, m in sp_local], ".4f"))

    # ── 2) 검색 ────────────────────────────────────────
    titles = [x for x in (_title(r["text"]) for r in rows) if x]
    queries = EXAMPLE_QUERIES + titles
    owner = {_title(r["text"]): r["book_id"] for r in rows if _title(r["text"])}
    print(f"\n[2] 검색 — 질의 {len(queries)}개(예시 {len(EXAMPLE_QUERIES)} + 제목 {len(titles)}), 상위 {TOP_K}")
    qd_http, qs_http = embedder._embed_http(queries, need_sparse=True)
    qd_local, qs_local = embedder._embed_local(queries)
    q_cos = [_cos(a, b) for a, b in zip(qd_local, qd_http)]
    q_jac = [_sparse_diff(a, b)[0] for a, b in zip(qs_local, qs_http)]
    overlaps, same_top1, found_local, found_http = [], 0, 0, 0
    worst: list[tuple[float, str]] = []
    for q, dl, sl, dh, sh in zip(queries, qd_local, qs_local, qd_http, qs_http):
        hits_local = _hits(dl, _as_sparse(sl))
        hits_http = _hits(dh, sh)
        overlap = len(set(hits_local) & set(hits_http)) / TOP_K
        overlaps.append(overlap)
        worst.append((overlap, q))
        same_top1 += bool(hits_local and hits_http and hits_local[0] == hits_http[0])
        if q in owner:
            found_local += owner[q] in {b for _, b in hits_local}
            found_http += owner[q] in {b for _, b in hits_http}
    print("  " + _summary("질의 dense 코사인 local↔http", q_cos))
    print("  " + _summary("질의 sparse 토큰 일치 local↔http", q_jac, ".4f"))
    print("  " + _summary(f"검색 상위 {TOP_K} 겹침", overlaps, ".2f"))
    print(f"  1위 같음: {same_top1}/{len(queries)} · 제목 질의가 자기 자료를 상위 {TOP_K} 안에 찾음: "
          f"local {found_local}/{len(owner)} · http {found_http}/{len(owner)}")
    for overlap, q in sorted(worst)[:5]:
        if overlap < 1.0:
            print(f"    겹침 {overlap:.1f}: {q[:60]}")

    # ── 판정 ──────────────────────────────────────────
    checks = [
        ("dense 코사인(저장↔http) 최저", min(cos_http, default=float("nan")) >= DENSE_MIN_COS),
        ("질의 dense 코사인 최저", min(q_cos, default=float("nan")) >= DENSE_MIN_COS),
        ("질의 sparse 토큰 일치 평균", statistics.fmean(q_jac) >= SPARSE_MIN_JACCARD if q_jac else False),
        ("검색 상위 10 겹침 평균", statistics.fmean(overlaps) >= SEARCH_MIN_OVERLAP if overlaps else False),
    ]
    if has_sparse:
        checks.insert(1, ("sparse 토큰 일치(저장↔http) 평균",
                          statistics.fmean(j for j, _ in sp_http) >= SPARSE_MIN_JACCARD if sp_http else False))
    print("\n판정")
    for name, ok in checks:
        print(f"  {'통과' if ok else '확인 필요'} — {name}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
