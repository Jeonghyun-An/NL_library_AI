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
)

from core.config import get_settings
from services.ingestion.chunker import Chunk

log = logging.getLogger(__name__)
cfg = get_settings()

COLLECTION = cfg.MILVUS_COLLECTION
DIM = cfg.EMBEDDING_DIM

# 메타데이터 필드: MARC/MODS 파싱 결과를 스칼라로 저장 → expression filter에 사용
_META_FIELDS = {"publisher", "corporate_author", "pub_date", "kdc"}


def _connect():
    if not connections.has_connection("default"):
        connections.connect(
            alias="default",
            host=cfg.MILVUS_HOST,
            port=cfg.MILVUS_PORT,
        )


def _build_schema() -> CollectionSchema:
    return CollectionSchema(
        fields=[
            FieldSchema("chunk_id",          DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema("book_id",            DataType.VARCHAR, max_length=64),
            FieldSchema("chunk_idx",          DataType.INT16),
            FieldSchema("section_idx",        DataType.INT16),
            FieldSchema("text",               DataType.VARCHAR, max_length=16384),
            FieldSchema("page_start",         DataType.INT16),
            FieldSchema("page_end",           DataType.INT16),
            # ── MARC/MODS 메타데이터 스칼라 필드 ──────────────
            FieldSchema("publisher",          DataType.VARCHAR, max_length=512),
            FieldSchema("corporate_author",   DataType.VARCHAR, max_length=512),
            FieldSchema("pub_date",           DataType.VARCHAR, max_length=32),
            FieldSchema("kdc",                DataType.VARCHAR, max_length=32),
            # ─────────────────────────────────────────────────
            FieldSchema("embedding",          DataType.FLOAT_VECTOR, dim=DIM),
        ],
        description="NL-Lib 도서 청크 임베딩 (MARC/MODS 메타 포함)",
    )


def ensure_collection() -> Collection:
    """
    컬렉션 없으면 생성, 있으면 반환.
    메타데이터 필드(_META_FIELDS)가 없는 구 스키마면 자동으로 재생성(→ 재인덱싱 필요).
    """
    _connect()

    if utility.has_collection(COLLECTION):
        col = Collection(COLLECTION)
        existing_fields = {f.name for f in col.schema.fields}
        if _META_FIELDS.issubset(existing_fields):
            col.load()
            return col
        # 구 스키마 → 메타 필드 없음 → 재생성
        utility.drop_collection(COLLECTION)
        log.warning(
            f"컬렉션 '{COLLECTION}' 스키마에 메타데이터 필드 없음 → 재생성. "
            "도서를 다시 인덱싱하세요."
        )

    col = Collection(name=COLLECTION, schema=_build_schema())
    col.create_index(
        field_name="embedding",
        index_params={
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 256},
        },
    )
    col.load()
    log.info(f"컬렉션 '{COLLECTION}' 생성 완료 (메타데이터 필드 포함)")
    return col


# ── 도서 메타데이터 DTO ────────────────────────────────────────
@dataclass
class BookMeta:
    """인덱싱 시 Milvus에 함께 저장할 MARC/MODS 메타데이터"""
    publisher:        str = ""
    corporate_author: str = ""
    pub_date:         str = ""
    kdc:              str = ""


@dataclass
class IndexResult:
    book_id: str
    chunks_indexed: int
    errors: list[str] = field(default_factory=list)


def index_chunks(
    book_id: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    *,
    book_meta: BookMeta | None = None,
) -> IndexResult:
    """
    청크 + 임베딩을 Milvus에 저장.
    book_meta 를 전달하면 MARC/MODS 메타데이터를 스칼라 필드로 함께 저장.
    """
    col = ensure_collection()
    errors: list[str] = []
    meta = book_meta or BookMeta()

    # 기존 데이터 삭제 (재수집 시)
    col.delete(expr=f'book_id == "{book_id}"')

    data = [
        [f"{book_id}__{c.chunk_idx:04d}" for c in chunks],  # chunk_id
        [book_id] * len(chunks),                             # book_id
        [c.chunk_idx for c in chunks],                       # chunk_idx
        [c.section_idx or 0 for c in chunks],                # section_idx
        [c.text[:16000] for c in chunks],                    # text
        [c.page_start or 0 for c in chunks],                 # page_start
        [c.page_end or 0 for c in chunks],                   # page_end
        [meta.publisher[:511]]        * len(chunks),         # publisher
        [meta.corporate_author[:511]] * len(chunks),         # corporate_author
        [meta.pub_date[:31]]          * len(chunks),         # pub_date
        [meta.kdc[:31]]               * len(chunks),         # kdc
        embeddings,                                          # embedding
    ]

    try:
        col.insert(data)
        col.flush()
        log.info(f"[{book_id}] {len(chunks)}개 청크 인덱싱 완료 (meta: {meta})")
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
    query_embedding: list[float],
    top_k: int = 20,
    *,
    book_filter: str | None = None,
    meta_expr: str | None = None,
) -> list[SearchHit]:
    """
    청크 단위 벡터 검색.

    meta_expr: Milvus boolean expression (MARC/MODS 메타 필드 기반 필터)
               예) 'corporate_author like "%조달청%" || publisher like "%조달청%"'
    """
    col = ensure_collection()
    if col.num_entities == 0:
        return []

    search_params = {"metric_type": "COSINE", "params": {"nprobe": 32}}

    if meta_expr:
        expr = meta_expr
    elif book_filter:
        expr = f'book_id == "{book_filter}"'
    else:
        expr = None

    results = col.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=[
            "book_id", "chunk_idx", "section_idx",
            "text", "page_start", "page_end", "pub_date",
        ],
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
    query_embedding: list[float],
    top_k_chunks: int = 20,
    top_k_books: int = 5,
    *,
    meta_expr: str | None = None,
) -> dict[str, list[SearchHit]]:
    """
    청크 검색 후 도서 단위로 집계.

    Returns:
        {book_id: [관련 청크들]} — 상위 top_k_books 도서 (벡터 점수 기준)
    """
    hits = search_chunks(query_embedding, top_k=top_k_chunks, meta_expr=meta_expr)

    book_hits: dict[str, list[SearchHit]] = defaultdict(list)
    book_max_score: dict[str, float] = {}

    for hit in hits:
        book_hits[hit.book_id].append(hit)
        if hit.book_id not in book_max_score or hit.score > book_max_score[hit.book_id]:
            book_max_score[hit.book_id] = hit.score

    sorted_books = sorted(book_max_score, key=book_max_score.get, reverse=True)[:top_k_books]
    return {bid: book_hits[bid] for bid in sorted_books}
