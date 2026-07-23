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
    # dense 벡터 인덱스 파라미터.
    # 소량/현행: IVF_FLAT, nlist 256, nprobe 32 (기본값)
    # 30만건(≈1,500만 벡터) 대량 인덱싱: env 로 아래 값 권장 후 컬렉션 재생성
    #   MILVUS_INDEX_TYPE=IVF_SQ8  MILVUS_NLIST=16384  MILVUS_NPROBE=64
    #   (raw float32 ~60GB → SQ8 ~15GB, recall 손실은 리랭커가 흡수)
    MILVUS_INDEX_TYPE: str = "IVF_FLAT"
    MILVUS_NLIST: int = 256
    MILVUS_NPROBE: int = 32

    # ── OCR 엔진 선택 (2티어 보완) ────────────────────
    # "vlm"   : 범용 VLM(Qwen3-VL) — /chat/completions HTTP
    # "surya" : 전용 OCR(Surya) 별도 컨테이너 — /ocr HTTP (경량·CJK 강함)
    OCR_ENGINE: str = "vlm"
    SURYA_BASE_URL: str = "http://surya:8000"

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

    # ── LLM API 스타일 (OpenAI 호환 vLLM / Ollama 네이티브) ──
    # "openai" → {LLM_BASE_URL}/chat/completions (기본, 운영 vLLM — 무영향)
    # "ollama" → {LLM_BASE_URL의 /v1 제거}/api/chat (Ollama, think 제어용)
    LLM_API_STYLE: str = "openai"
    # think 토글: None=필드 미전송(비-thinking 모델 안전), True/False=그 값 전송.
    # Ollama gemma4 요약은 false (추론 비용 제거). gemma3 등은 None 유지.
    LLM_THINK: bool | None = None
    # Ollama 컨텍스트 길이 — 기본 4096 이면 긴 섹션 요약 입력이 잘림
    OLLAMA_NUM_CTX: int = 8192

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
    DISPATCH_STALE_SECONDS: int = 14400  # 디스패치 후 워커 무응답 stale 판정(초)

    # ── 시맨틱 청킹 ──────────────────────────────────
    MIN_CHUNK_TOKENS: int = 128
    MAX_CHUNK_TOKENS: int = 1024
    MAX_CHUNK_BYTES: int = 15500          # Milvus VARCHAR 바이트 가드
    SIMILARITY_WINDOW: int = 3            # 문장 그룹 슬라이딩 윈도우
    BREAKPOINT_PERCENTILE: int = 25       # 의미 경계 판정 하위 백분위

    # ── 섹션 분할 ─────────────────────────────────────
    # 1단계(extract)에서 chunker.semantic_chunk()로 의미 경계 기반 분할.
    # 의미 경계 근처에서 이 MIN/MAX 범위 안에 들어오도록 병합·분할된다.
    SECTION_MIN_TOKENS: int = 800   # 미만이면 인접 섹션에 병합
    SECTION_MAX_TOKENS: int = 5000  # 초과하면 문장 경계에서 강제 분할
    DOWNLOAD_DIR: str = "/app/data/downloads"

    # ── 텍스트 추출 / VLM OCR ─────────────────────────
    EXTRACT_MIN_CHARS_PER_PAGE: int = 50  # 이 미만이면 VLM 보완 트리거
    FITZ_DPI: int = 300                   # 페이지 렌더링 해상도
    VLM_MAX_TOKENS: int = 4096
    VLM_TEMPERATURE: float = 0.1
    VLM_TIMEOUT: int = 120

    # ── PDF 메타 자동추출 ─────────────────────────────
    PDF_META_MAX_CHARS: int = 3000
    PDF_META_MAX_TOKENS: int = 1024
    PDF_META_TEMPERATURE: float = 0.1
    PDF_META_TIMEOUT: int = 60

    # ── 요약 LLM 타임아웃(초) ─────────────────────────
    SUMMARIZER_SECTION_TIMEOUT: int = 60
    SUMMARIZER_BOOK_TIMEOUT: int = 120
    SUMMARIZER_INTRO_TIMEOUT: int = 120
    SUMMARIZER_PLOT_TIMEOUT: int = 120
    SUMMARIZER_READ_EFFECT_TIMEOUT: int = 120
    # 도서 요약/소개 입력(섹션요약 묶음) 최대 글자 수 — 컨텍스트 오버플로 방지.
    # 14000자 ≈ 27k 토큰, + 출력 4096 + 시스템 ≈ 31k < 32768(gemma max-model-len).
    SUMMARIZER_MAX_INPUT_CHARS: int = 14000

    # ── FLUX 표지 생성 ────────────────────────────────
    FLUX_WIDTH: int = 768
    FLUX_HEIGHT: int = 1152
    FLUX_STEPS: int = 28
    FLUX_GUIDANCE: float = 3.5
    COVER_PROMPT_TIMEOUT: int = 60

    # ── Milvus sparse / RRF ───────────────────────────
    MILVUS_SPARSE_DROP_RATIO_BUILD: float = 0.2
    MILVUS_SPARSE_DROP_RATIO_SEARCH: float = 0.2
    RRF_RANKER_K: int = 60

    # ── 컨텍스트 확장 ─────────────────────────────────
    CONTEXT_BUDGET_TOKENS: int = 100000
    EXPAND_SECTIONS: int = 2

    # ── 검색 후보 풀 배수 / 표시 한도 ─────────────────
    CHUNK_MODE_FETCH_MULTIPLIER: int = 4
    BOOK_MODE_FETCH_MULTIPLIER_SORT: int = 4   # 날짜 정렬 시
    BOOK_MODE_FETCH_MULTIPLIER: int = 3        # 일반
    HYBRID_SEARCH_CHUNK_LIMIT_MULT: int = 10
    MARC_KEYWORDS_LIMIT: int = 5
    KEYWORDS_MAX_COUNT: int = 5

    # ── 추천 이유 / 답변 생성 LLM ─────────────────────
    REASON_CHUNKS_DISPLAY_LIMIT: int = 15
    REASON_MAX_TOKENS: int = 650
    REASON_TEMPERATURE: float = 0.4
    REASON_TIMEOUT: int = 60
    RECOMMENDATION_MAX_TOKENS: int = 1500  # 추천이유(5~7문장) + 독후효과(3~4문장) + 여유

    # ── 큐레이션 리포트 LLM ────────────────────────────
    CURATION_TOP_K: int = 20          # 컬렉션 최대 도서 수 (프론트 선택: 3/5/10/20)
    CURATION_MAX_TOKENS: int = 1200   # 기본값. 도서 수에 따라 curator에서 동적 확장
    CURATION_TEMPERATURE: float = 0.3
    CURATION_TIMEOUT: int = 60
    ANSWER_EXTENDED_MAX_TOKENS: int = 4096
    ANSWER_EXTENDED_TEMPERATURE: float = 0.3
    ANSWER_EXTENDED_TIMEOUT: int = 120
    ANSWER_BASE_CHUNKS_LIMIT: int = 5
    ANSWER_BASE_MAX_TOKENS: int = 2048
    ANSWER_BASE_TEMPERATURE: float = 0.3
    ANSWER_BASE_TIMEOUT: int = 60

    # ── 도서 대화 (book_chat) ─────────────────────────
    BOOK_CHAT_SEARCH_TOP_K: int = 6
    BOOK_CHAT_HISTORY_MESSAGES: int = 20   # 최근 메시지 수 (20=10턴)
    BOOK_CHAT_TIMEOUT: int = 90
    # 히스토리 기반 질의 재구성 (대명사·생략 질의의 청크 검색 recall 향상)
    BOOK_CHAT_QUERY_REWRITE: bool = True
    BOOK_CHAT_QUERY_REWRITE_HISTORY: int = 6   # 재구성에 참고할 최근 메시지 수
    BOOK_CHAT_QUERY_REWRITE_TIMEOUT: int = 20

    # ── 쿼리 전처리 LLM 타임아웃(초) ──────────────────
    QUERY_REWRITE_TIMEOUT: int = 30
    METADATA_FILTER_TIMEOUT: int = 15

    # ── 논문 핵심 요약 (paper_summary) ──────────────────────────
    PAPER_SUMMARY_TIMEOUT: int = 120          # 핵심 요약 LLM 스트리밍 타임아웃(초)
    PAPER_SUMMARY_TOP_K: int = 5              # 요약에 사용할 최대 논문 수

    # ── 논문 보강 (paper_enricher) ───────────────────────────
    PAPER_ENRICH_ENABLED: bool = True
    PAPER_MAX_TABLES_PER_DOC: int = 10      # 표 청크 최대 개수
    PAPER_MAX_FIGURES_PER_DOC: int = 8      # 그림 설명 최대 개수
    PAPER_TABLE_INTERP_TIMEOUT: int = 60    # 표 LLM 서술 타임아웃(초)
    PAPER_FIGURE_VLM_TIMEOUT: int = 90      # 그림 설명 VLM 타임아웃(초)

    # ── 배치/락 ───────────────────────────────────────
    JOB_MANAGER_CHUNK_SIZE: int = 5000     # ID 조회 IN 청크
    JOB_MANAGER_BATCH_SIZE: int = 1000     # 잡 아이템 bulk insert 배치
    CATALOG_BULK_BATCH_SIZE: int = 1000    # 카탈로그 upsert 배치
    BOOK_LOCK_TTL: int = 3600              # Redis 인덱싱 락 TTL(초)

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()