from functools import lru_cache
from FlagEmbedding import FlagModel
from core.config import get_settings


@lru_cache(maxsize=1)
def _load_model():
    cfg = get_settings()
    return FlagModel(
        cfg.EMBEDDING_MODEL_NAME,
        query_instruction_for_retrieval="Represent this sentence for searching relevant passages: ",
        use_fp16=True,
    )


def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    model = _load_model()
    vecs = model.encode_queries(texts) if is_query else model.encode(texts)
    return vecs.tolist()

