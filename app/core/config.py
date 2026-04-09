from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "NL-Lib Semantic Search"
    DEBUG: bool = False
    IS_DOCKER: bool = False

    # ── PostgreSQL ───────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "nl_lib"
    DB_USER: str = "admin"
    DB_PASSWORD: str = "password"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ── Redis ────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── MinIO ────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "nl-lib-bucket"

    # ── Milvus ───────────────────────────────────────
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "nl_lib_embeddings"

    # ── vLLM / EXAONE ────────────────────────────────
    VLLM_BASE_URL: str = "http://host.docker.internal:18080/v1"
    VLLM_MODEL: str = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"
    VLLM_MAX_TOKENS: int = 1024
    VLLM_TEMPERATURE: float = 0.1

    # ── Embedding ────────────────────────────────────
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DIM: int = 1024
    EMBEDDING_MAX_LENGTH: int = 512

    # ── RAG ──────────────────────────────────────────
    RETRIEVAL_TOP_K: int = 20
    RERANK_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.5
    
    # ── Reranker ─────────────────────────────────────
    RERANKER_MODEL_NAME: str = "jinaai/jina-reranker-v2-base-multilingual"
    RERANKER_BATCH_SIZE: int = 16
    RERANKER_MAX_LENGTH: int = 1024

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()