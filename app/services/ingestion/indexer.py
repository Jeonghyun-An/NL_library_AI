from pymilvus import (
    connections, Collection, CollectionSchema,
    FieldSchema, DataType, utility
)
from core.config import get_settings


def _connect():
    cfg = get_settings()
    connections.connect(host=cfg.MILVUS_HOST, port=cfg.MILVUS_PORT)


def ensure_collection() -> Collection:
    cfg = get_settings()
    _connect()
    name = cfg.MILVUS_COLLECTION

    if utility.has_collection(name):
        col = Collection(name)
        col.load()
        return col

    schema = CollectionSchema(fields=[
        FieldSchema("milvus_id", DataType.VARCHAR, max_length=64, is_primary=True, auto_id=False),
        FieldSchema("book_id",   DataType.VARCHAR, max_length=64),
        FieldSchema("cnts_id",   DataType.VARCHAR, max_length=64),
        FieldSchema("title",     DataType.VARCHAR, max_length=512),
        FieldSchema("subject",   DataType.VARCHAR, max_length=512),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=cfg.EMBEDDING_DIM),
    ], description="NL-Lib book embeddings")

    col = Collection(name, schema)
    col.create_index(
        field_name="embedding",
        index_params={"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}},
    )
    col.load()
    return col


def upsert_embeddings(records: list[dict]) -> None:
    col = ensure_collection()
    col.upsert([
        [r["milvus_id"] for r in records],
        [r["book_id"]   for r in records],
        [r["cnts_id"]     for r in records],
        [r["title"]     for r in records],
        [r["subject"]   for r in records],
        [r["embedding"] for r in records],
    ])


def search_similar(query_vec: list[float], top_k: int = 20) -> list[dict]:
    col = ensure_collection()
    results = col.search(
        data=[query_vec],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        output_fields=["book_id", "cnts_id", "title", "subject"],
    )
    return [
        {
            "milvus_id": h.id,
            "book_id":   h.entity.get("book_id"),
            "cnts_id":   h.entity.get("cnts_id"),
            "title":     h.entity.get("title"),
            "subject":   h.entity.get("subject"),
            "score":     h.distance,
        }
        for h in results[0]
    ]