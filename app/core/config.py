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

    # ── VLM (멀티모달 OCR — 페이지 이미지 → 텍스트) ──
    VLM_BASE_URL: str = "http://vllm:8000/v1"
    VLM_MODEL: str = "qwen2.5-vl-7b"

    # ── LLM (텍스트 생성 — 요약/리라이트/추론) ───────
    LLM_BASE_URL: str = "http://host.docker.internal:18080/v1"
    LLM_MODEL: str = "gemma-3-12b"
    LLM_TIMEOUT: int = 30

    # ── FLUX (자동 표지 이미지 생성 — black-forest-labs/FLUX.1-dev) ──
    FLUX_BASE_URL: str = "http://flux:8000"
    FLUX_TIMEOUT: int = 300

    # ── PaddleOCR ────────────────────────────────────
    PADDLEOCR_URL: str = "http://paddleocr:8001"

    # ── Embedding ────────────────────────────────────
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DIM: int = 1024
    EMBEDDING_MAX_LENGTH: int = 512

    # ── Reranker ─────────────────────────────────────
    RERANKER_MODEL_NAME: str = "jinaai/jina-reranker-v2-base-multilingual"
    RERANKER_BATCH_SIZE: int = 16
    RERANKER_MAX_LENGTH: int = 1024

    # ── RAG ──────────────────────────────────────────
    RETRIEVAL_TOP_K: int = 20
    RERANK_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.5

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()