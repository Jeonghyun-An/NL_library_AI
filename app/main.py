import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.config import get_settings
from api.book import router as book_router
from api.health import router as health_router
from api.admin import router as admin_router
from api.paper import router as paper_router
from api.ingest_jobs import router as ingest_jobs_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
cfg = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────
    log.info(f"{cfg.APP_NAME} 시작")

    # DB 테이블 생성
    from db.postgres import engine
    from models.book import Base
    import models.section
    import models.search_history
    import models.ingest_job
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 컬럼 추가 마이그레이션 (이미 존재하면 skip)
        await conn.execute(text(
            "ALTER TABLE book_sections ADD COLUMN IF NOT EXISTS summary TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE library_catalog ADD COLUMN IF NOT EXISTS part_number TEXT"
        ))
    log.info("DB 테이블 확인 완료")

    # 임베딩 모델 로드 (FlagEmbedding)
    from services.ingestion.embedder import embed_texts
    _ = embed_texts(["워밍업"])
    log.info("임베딩 모델 로드 완료")

    # 리랭커 모델 로드
    from services.search.reranker import warmup as reranker_warmup
    reranker_warmup()

    # Milvus 컬렉션 확인
    from services.ingestion.indexer import ensure_collection
    ensure_collection()

    log.info("모든 모델 로드 완료")

    yield

    # ── shutdown ─────────────────────────────────────
    from db.postgres import engine as _engine
    await _engine.dispose()
    log.info("STOP: DB 연결 종료")


app = FastAPI(
    title=cfg.APP_NAME,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(book_router)
app.include_router(admin_router)
app.include_router(paper_router)
app.include_router(ingest_jobs_router)