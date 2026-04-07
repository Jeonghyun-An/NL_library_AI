from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from db.postgres import engine
from models.book import Base
from services.ingestion.indexer import ensure_collection
from api.book import router as book_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    ensure_collection()
    yield


cfg = get_settings()
app = FastAPI(title=cfg.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(book_router)


@app.get("/health")
async def health():
    return {"status": "ok"}