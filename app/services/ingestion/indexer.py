import logging
from collections import defaultdict
from dataclasses import dataclass, field

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
    AnnSearchRequest,
    RRFRanker,
)

from core.config import get_settings
from services.ingestion.chunker import Chunk

log = logging.getLogger(__name__)
cfg = get_settings()

COLLECTION = cfg.MILVUS_COLLECTION
DIM = cfg.EMBEDDING_DIM

# 코어 스칼라 필드 (모든 도메인 공통) — doc_type/pub_date 코어 승격
_CORE_SCALAR = {
    "doc_type": 16,
    "pub_date": 32,
}


def _profile_scalar_fields() -> list:
    """활성 도메인 프로파일의 Milvus 스칼라 필드 (pub_date는 코어로 승격, 중복 제거)."""
    from domains import get_active_profile

    return [f for f in get_active_profile().milvus_scalar_fields if f.name not in _CORE_SCALAR]


def _scalar_field_specs() -> list[tuple[str, int]]:
    """(필드명, max_length) — 코어 + 프로파일 스칼라. 스키마/인덱싱/검증 공통 소스."""
    specs = list(_CORE_SCALAR.items())
    specs += [(f.name, f.max_length) for f in _profile_scalar_fields()]
    return specs


def _required_fields() -> set[str]:
    """스키마 재생성 트리거 — 이 필드 중 하나라도 없으면 구 스키마."""
    return {"sparse_embedding", *(name for name, _ in _scalar_field_specs())}


def _connect():
    if not connections.has_connection("default"):
        connections.connect(
            alias="default",
            host=cfg.MILVUS_HOST,
            port=cfg.MILVUS_PORT,
        )


def _build_schema() -> CollectionSchema:
    scalar_fields = [
        FieldSchema(name, DataType.VARCHAR, max_length=max_len)
        for name, max_len in _scalar_field_specs()
    ]
    return CollectionSchema(
        fields=[
            FieldSchema("chunk_id",          DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema("book_id",            DataType.VARCHAR, max_length=64),
            FieldSchema("chunk_idx",          DataType.INT16),
            FieldSchema("section_idx",        DataType.INT16),
            FieldSchema("text",               DataType.VARCHAR, max_length=16384),
            FieldSchema("page_start",         DataType.INT16),
            FieldSchema("page_end",           DataType.INT16),
            # ── 코어(doc_type, pub_date) + 도메인 스칼라 필터 필드 ──
            *scalar_fields,
            # ─────────────────────────────────────────────────
            FieldSchema("embedding",          DataType.FLOAT_VECTOR, dim=DIM),
            FieldSchema("sparse_embedding",   DataType.SPARSE_FLOAT_VECTOR),
        ],
        description="NL-Lib 청크 임베딩 (BGE-M3 dense+sparse + 코어/도메인 스칼라)",
    )


_collection_cache: Collection | None = None


def ensure_collection() -> Collection:
    """
    컬렉션 없으면 생성, 있으면 반환 (모듈 레벨 캐시).
    스키마 불일치 시: MILVUS_RECREATE_ON_MISMATCH=true 일 때만 재생성,
    기본은 RuntimeError로 중단 (대량 인덱스 무단 삭제 방지).
    """
    global _collection_cache
    if _collection_cache is not None:
        return _collection_cache

    _connect()

    if utility.has_collection(COLLECTION):
        col = Collection(COLLECTION)
        existing_fields = {f.name for f in col.schema.fields}
        required = _required_fields()
        if required.issubset(existing_fields):
            col.load()
            _collection_cache = col
            return col
        missing = required - existing_fields
        if not cfg.MILVUS_RECREATE_ON_MISMATCH:
            raise RuntimeError(
                f"컬렉션 '{COLLECTION}' 스키마 불일치 (누락 필드: {missing}). "
                "기존 인덱스를 보호하기 위해 중단합니다. 재생성하려면 "
                "MILVUS_RECREATE_ON_MISMATCH=true 로 설정하세요 (전체 재인덱싱 필요)."
            )
        utility.drop_collection(COLLECTION)
        log.warning(
            f"컬렉션 '{COLLECTION}' 스키마 변경 감지 → 재생성 (누락 필드: {missing}). "
            "도서를 다시 인덱싱하세요."
        )

    col = Collection(name=COLLECTION, schema=_build_schema())

    # dense 벡터 인덱스 (코사인 유사도)
    col.create_index(
        field_name="embedding",
        index_params={
            "metric_type": "COSINE",
            "index_type": cfg.MILVUS_INDEX_TYPE,
            "params": {"nlist": cfg.MILVUS_NLIST},
        },
    )
    # sparse 벡터 인덱스 (내적, lexical weights)
    col.create_index(
        field_name="sparse_embedding",
        index_params={
            "metric_type": "IP",
            "index_type": "SPARSE_INVERTED_INDEX",
            "params": {"drop_ratio_build": 0.2},
        },
    )

    col.load()
    log.info(f"컬렉션 '{COLLECTION}' 생성 완료 (dense + sparse + MARC/MODS 메타)")
    _collection_cache = col
    return col


# ── 도서 메타데이터 DTO ────────────────────────────────────────
@dataclass
class BookMeta:
    """[deprecated] 단건 흐름 호환용. 신규 코드는 scalar_meta dict 를 직접 전달.

    build_scalar_meta(book, profile.milvus_scalar_fields) 사용 권장.
    """
    publisher:        str = ""
    corporate_author: str = ""
    pub_date:         str = ""
    kdc:              str = ""

    def as_scalar_meta(self) -> dict[str, str]:
        return {
            "publisher": self.publisher or "",
            "corporate_author": self.corporate_author or "",
            "pub_date": self.pub_date or "",
            "kdc": self.kdc or "",
        }


@dataclass
class IndexResult:
    book_id: str
    chunks_indexed: int
    errors: list[str] = field(default_factory=list)


def _truncate_bytes(s: str, max_bytes: int, *, field: str = "") -> str:
    """Milvus VARCHAR는 max_length가 바이트 단위. UTF-8 멀티바이트 경계에서 안전하게 자른다.

    청킹 단계에서 바이트 가드가 작동하면 정상적으로는 발동하지 않아야 한다.
    호출되면 데이터 손실이 발생했다는 뜻이므로 경고 로그를 남긴다.
    """
    if not s:
        return s
    encoded = s.encode("utf-8")
    if len(encoded) <= max_bytes:
        return s
    cut = encoded[:max_bytes]
    while cut and (cut[-1] & 0xC0) == 0x80:
        cut = cut[:-1]
    truncated = cut.decode("utf-8", errors="ignore")
    log.warning(
        f"Milvus VARCHAR 바이트 초과 — field={field or 'unknown'}, "
        f"원본 {len(encoded)}바이트 → {len(cut)}바이트로 잘림. "
        "청킹 단계 바이트 가드가 누락된 경우입니다."
    )
    return truncated


def index_chunks(
    book_id: str,
    chunks: list[Chunk],
    dense_embeddings: list[list[float]],
    sparse_embeddings: list[dict[int, float]],
    *,
    scalar_meta: dict[str, str] | None = None,
    book_meta: BookMeta | None = None,
) -> IndexResult:
    """
    청크 + dense/sparse 임베딩을 Milvus에 저장.
    scalar_meta: {필드명: 값} — 코어(doc_type/pub_date) + 도메인 스칼라 필터 필드.
    book_meta: [deprecated] 단건 흐름 호환 (내부에서 scalar_meta 로 변환).
    """
    col = ensure_collection()
    errors: list[str] = []
    meta = dict(scalar_meta or {})
    if book_meta is not None:
        for k, v in book_meta.as_scalar_meta().items():
            meta.setdefault(k, v)

    col.delete(expr=f'book_id == "{book_id}"')

    n = len(chunks)
    data = [
        [f"{book_id}__{c.chunk_idx:04d}" for c in chunks],            # chunk_id
        [book_id] * n,                                                 # book_id
        [c.chunk_idx for c in chunks],                                 # chunk_idx
        [c.section_idx or 0 for c in chunks],                          # section_idx
        [_truncate_bytes(c.text, 16000, field="text") for c in chunks],  # text
        [c.page_start or 0 for c in chunks],                           # page_start
        [c.page_end or 0 for c in chunks],                             # page_end
    ]
    # 코어 + 도메인 스칼라 필드 (스키마와 동일 순서)
    for name, max_len in _scalar_field_specs():
        val = _truncate_bytes(meta.get(name, "") or "", max(1, max_len - 1), field=name)
        data.append([val] * n)
    data.append(dense_embeddings)        # embedding (dense)
    data.append(sparse_embeddings)       # sparse_embedding

    try:
        col.insert(data)
        # flush()는 세그먼트 강제 봉인으로 비용이 큼 — Milvus auto-flush에 위임
        log.info(f"[{book_id}] {n}개 청크 인덱싱 완료 (dense+sparse, scalar: {meta})")
    except Exception as e:
        log.error(f"[{book_id}] 인덱싱 실패: {e}")
        errors.append(str(e))

    return IndexResult(
        book_id=book_id,
        chunks_indexed=len(chunks) - len(errors),
        errors=errors,
    )


# ── 검색 결과 DTO ─────────────────────────────────────────────
@dataclass
class SearchHit:
    """Milvus 검색 결과"""
    chunk_id:         str
    book_id:          str
    chunk_idx:        int
    section_idx:      int
    text:             str
    page_start:       int
    page_end:         int
    score:            float
    pub_date:         str = ""   # 날짜 기준 정렬에 사용


def search_chunks(
    query_dense: list[float],
    query_sparse: dict[int, float],
    top_k: int = 20,
    *,
    book_filter: str | None = None,
    meta_expr: str | None = None,
) -> list[SearchHit]:
    """
    BGE-M3 dense+sparse 하이브리드 검색 (RRF 리랭킹).

    meta_expr: Milvus boolean expression (MARC/MODS 스칼라 필드 기반 pre-filter)
               예) 'pub_date >= "2023" && pub_date < "2025"'
    """
    col = ensure_collection()
    if col.num_entities == 0:
        return []

    if meta_expr:
        expr = meta_expr
    elif book_filter:
        expr = f'book_id == "{book_filter}"'
    else:
        expr = None

    output_fields = [
        "book_id", "chunk_idx", "section_idx",
        "text", "page_start", "page_end", "pub_date",
    ]

    dense_req = AnnSearchRequest(
        data=[query_dense],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": cfg.MILVUS_NPROBE}},
        limit=top_k,
        expr=expr,
    )
    sparse_req = AnnSearchRequest(
        data=[query_sparse],
        anns_field="sparse_embedding",
        param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
        limit=top_k,
        expr=expr,
    )

    results = col.hybrid_search(
        reqs=[dense_req, sparse_req],
        rerank=RRFRanker(k=60),
        limit=top_k,
        output_fields=output_fields,
    )

    hits: list[SearchHit] = []
    for hit in results[0]:
        e = hit.entity
        hits.append(SearchHit(
            chunk_id=hit.id,
            book_id=e.get("book_id") or "",
            chunk_idx=e.get("chunk_idx") or 0,
            section_idx=e.get("section_idx") or 0,
            text=e.get("text") or "",
            page_start=e.get("page_start") or 0,
            page_end=e.get("page_end") or 0,
            score=hit.score,
            pub_date=e.get("pub_date") or "",
        ))

    return hits


def search_by_book(
    query_dense: list[float],
    query_sparse: dict[int, float],
    top_k_chunks: int = 20,
    top_k_books: int = 5,
    *,
    meta_expr: str | None = None,
) -> dict[str, list[SearchHit]]:
    """
    청크 하이브리드 검색 후 도서 단위로 집계.

    Returns:
        {book_id: [관련 청크들]} — 상위 top_k_books 도서 (RRF 점수 기준)
    """
    hits = search_chunks(
        query_dense, query_sparse,
        top_k=top_k_chunks,
        meta_expr=meta_expr,
    )

    book_hits: dict[str, list[SearchHit]] = defaultdict(list)
    book_max_score: dict[str, float] = {}

    for hit in hits:
        book_hits[hit.book_id].append(hit)
        if hit.book_id not in book_max_score or hit.score > book_max_score[hit.book_id]:
            book_max_score[hit.book_id] = hit.score

    sorted_books = sorted(book_max_score, key=book_max_score.get, reverse=True)[:top_k_books]
    return {bid: book_hits[bid] for bid in sorted_books}
