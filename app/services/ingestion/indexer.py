import logging
from dataclasses import dataclass

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


def _connect():
    if not connections.has_connection("default"):
        connections.connect(
            alias="default",
            host=cfg.MILVUS_HOST,
            port=cfg.MILVUS_PORT,
        )


def ensure_collection() -> Collection:
    """컬렉션 없으면 생성, 있으면 반환"""
    _connect()

    if utility.has_collection(COLLECTION):
        col = Collection(COLLECTION)
        col.load()
        return col

    schema = CollectionSchema(
        fields=[
            FieldSchema("chunk_id", DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema("book_id", DataType.VARCHAR, max_length=64),
            FieldSchema("chunk_idx", DataType.INT16),
            FieldSchema("section_idx", DataType.INT16),
            FieldSchema("text", DataType.VARCHAR, max_length=8192),
            FieldSchema("page_start", DataType.INT16),
            FieldSchema("page_end", DataType.INT16),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=DIM),
        ],
        description="NL-Lib 도서 청크 임베딩",
    )

    col = Collection(name=COLLECTION, schema=schema)

    col.create_index(
        field_name="embedding",
        index_params={
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 256},
        },
    )
    col.load()
    log.info(f"컬렉션 '{COLLECTION}' 생성 완료")
    return col


@dataclass
class IndexResult:
    book_id: str
    chunks_indexed: int
    errors: list[str]


def index_chunks(
    book_id: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> IndexResult:
    """
    청크 + 임베딩을 Milvus에 저장

    Args:
        book_id: 도서 식별자
        chunks: Chunk 리스트
        embeddings: 청크별 임베딩 벡터 리스트
    """
    col = ensure_collection()
    errors = []

    # 기존 데이터 삭제 (재수집 시)
    col.delete(expr=f'book_id == "{book_id}"')

    # 배치 삽입
    data = [
        [f"{book_id}__{c.chunk_idx:04d}" for c in chunks],   # chunk_id
        [book_id] * len(chunks),                              # book_id
        [c.chunk_idx for c in chunks],                        # chunk_idx
        [c.section_idx or 0 for c in chunks],                 # section_idx
        [c.text[:8000] for c in chunks],                      # text (max 8192)
        [c.page_start or 0 for c in chunks],                  # page_start
        [c.page_end or 0 for c in chunks],                    # page_end
        embeddings,                                           # embedding
    ]

    try:
        col.insert(data)
        col.flush()
        log.info(f"[{book_id}] {len(chunks)}개 청크 인덱싱 완료")
    except Exception as e:
        log.error(f"[{book_id}] 인덱싱 실패: {e}")
        errors.append(str(e))

    return IndexResult(
        book_id=book_id,
        chunks_indexed=len(chunks) - len(errors),
        errors=errors,
    )


@dataclass
class SearchHit:
    """Milvus 검색 결과 — schemas.ChunkHit과 필드명 1:1 대응"""
    chunk_id: str
    book_id: str
    chunk_idx: int
    section_idx: int        # 원문 섹션 포인터
    text: str
    page_start: int
    page_end: int
    score: float


def search_chunks(
    query_embedding: list[float],
    top_k: int = 20,
    *,
    book_filter: str | None = None,
) -> list[SearchHit]:
    """청크 단위 벡터 검색"""
    col = ensure_collection()

    search_params = {"metric_type": "COSINE", "params": {"nprobe": 32}}

    expr = f'book_id == "{book_filter}"' if book_filter else None

    results = col.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=["book_id", "chunk_idx", "section_idx", "text", "page_start", "page_end"],
    )

    hits = []
    for hit in results[0]:
        hits.append(SearchHit(
            chunk_id=hit.id,
            book_id=hit.entity.get("book_id"),
            chunk_idx=hit.entity.get("chunk_idx"),
            section_idx=hit.entity.get("section_idx", 0),
            text=hit.entity.get("text"),
            page_start=hit.entity.get("page_start"),
            page_end=hit.entity.get("page_end"),
            score=hit.score,
        ))

    return hits


def search_by_book(
    query_embedding: list[float],
    top_k_chunks: int = 20,
    top_k_books: int = 5,
) -> dict[str, list[SearchHit]]:
    """
    청크 검색 후 도서 단위로 집계

    Returns:
        {book_id: [관련 청크들]} — 상위 top_k_books 도서
    """
    hits = search_chunks(query_embedding, top_k=top_k_chunks)

    # 도서별 그룹화 + 최고 점수 기준 정렬
    from collections import defaultdict
    book_hits: dict[str, list[SearchHit]] = defaultdict(list)
    book_max_score: dict[str, float] = {}

    for hit in hits:
        book_hits[hit.book_id].append(hit)
        if hit.book_id not in book_max_score or hit.score > book_max_score[hit.book_id]:
            book_max_score[hit.book_id] = hit.score

    # 도서별 최고 점수 기준 상위 N개
    sorted_books = sorted(book_max_score, key=book_max_score.get, reverse=True)[:top_k_books]

    return {bid: book_hits[bid] for bid in sorted_books}