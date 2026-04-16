"""
embedder.py — BGE-M3 dense + sparse 임베딩

embed_texts() → (dense_vecs, sparse_vecs) 튜플 반환
  dense_vecs : list[list[float]]       – Milvus FLOAT_VECTOR
  sparse_vecs: list[dict[int, float]]  – Milvus SPARSE_FLOAT_VECTOR (lexical weights)
"""
from functools import lru_cache
from typing import TypeAlias

from FlagEmbedding import BGEM3FlagModel
from core.config import get_settings

DenseVecs: TypeAlias = list[list[float]]
SparseVecs: TypeAlias = list[dict[int, float]]


@lru_cache(maxsize=1)
def _load_model() -> BGEM3FlagModel:
    cfg = get_settings()
    return BGEM3FlagModel(
        cfg.EMBEDDING_MODEL_NAME,
        use_fp16=True,
    )


def embed_texts(
    texts: list[str],
    is_query: bool = False,  # BGE-M3은 내부 처리 — API 호환용으로 유지
) -> tuple[DenseVecs, SparseVecs]:
    """
    texts 인코딩 → (dense_vecs, sparse_vecs) 반환.

    sparse_vecs 각 원소: {token_id(int): weight(float)}
    → Milvus SPARSE_FLOAT_VECTOR 에 직접 삽입 가능
    """
    _ = is_query  # BGE-M3은 query/passage 인코딩이 동일 — 호환성을 위해 파라미터 유지
    model = _load_model()
    output = model.encode(
        texts,
        batch_size=12,
        max_length=512,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense: DenseVecs = output["dense_vecs"].tolist()
    sparse: SparseVecs = output["lexical_weights"]  # list[dict[int, float]]
    return dense, sparse
