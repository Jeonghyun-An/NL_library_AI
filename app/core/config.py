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
    # 스키마 불일치 시 컬렉션 자동 재생성 허용 여부 (기본: 중단)
    MILVUS_RECREATE_ON_MISMATCH: bool = False
    # dense 벡터 인덱스 파라미터 (대량 인덱싱 시 IVF_SQ8 권장)
    MILVUS_INDEX_TYPE: str = "IVF_FLAT"
    MILVUS_NLIST: int = 256
    MILVUS_NPROBE: int = 32

    # ── VLM (멀티모달 OCR — 페이지 이미지 → 텍스트) ──
    VLM_BASE_URL: str = "http://vllm:8000/v1"
    VLM_MODEL: str = "qwen2.5-vl-7b"

    # ── LLM (텍스트 생성 — 요약/리라이트/추론) ───────
    LLM_BASE_URL: str = "http://host.docker.internal:18080/v1"
    LLM_MODEL: str = "gemma-3-12b"
    LLM_TIMEOUT: int = 120
    # 섹션 요약 등 태스크 내부 동시 LLM 호출 수
    # (글로벌 동시 LLM = celery-llm concurrency × 이 값 ≤ vLLM max-num-seqs)
    LLM_SECTION_CONCURRENCY: int = 4

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

    # ── 도메인 프로파일 ──────────────────────────────
    DOMAIN_PROFILE: str = "nl_library"

    # ── 대량 인덱싱 잡 ───────────────────────────────
    INGEST_HIGH_WATER: int = 32          # 잡당 동시 in-flight 아이템 수
    INGEST_MAX_ATTEMPTS: int = 3         # 아이템당 자동 재시도 한도
    # 단계별 타임아웃(초) — 초과 시 stale 판정 후 재디스패치
    INGEST_STAGE_TIMEOUT_EXTRACT: int = 1800
    INGEST_STAGE_TIMEOUT_SUMMARIZE: int = 1200
    INGEST_STAGE_TIMEOUT_EMBED: int = 1200
    INGEST_STAGE_TIMEOUT_FINALIZE: int = 900

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()