from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID as PyUUID
from datetime import datetime


# ── 도서 CRUD ────────────────────────────────────────────────
class BookBase(BaseModel):
    nl_id: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    pub_year: Optional[int] = None
    isbn: Optional[str] = None
    call_no: Optional[str] = None
    subject: Optional[str] = None


class BookCreate(BookBase):
    raw_text: Optional[str] = None


class BookOut(BookBase):
    id: PyUUID
    summary: Optional[str] = None
    is_embedded: bool
    created_at: datetime

    class Config:
        from_attributes = True
        
        

# ── 검색 ─────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, examples=["한강의 채식주의자와 비슷한 책"])
    top_k: int = Field(default=5, ge=1, le=20)
    use_rerank: bool = True


class SearchResult(BaseModel):
    book: BookOut
    score: float
    reason: str


class SearchResponse(BaseModel):
    query: str
    rewritten_query: str
    results: list[SearchResult]
    elapsed_ms: float


# ── 수집 ─────────────────────────────────────────────────────
class IngestionRequest(BaseModel):
    nl_ids: list[str] = Field(..., description="국립도서관 도서 ID 목록")
    force_re_summarize: bool = False


class IngestionStatus(BaseModel):
    task_id: str
    status: str   # PENDING | STARTED | SUCCESS | FAILURE
    total: int
    done: int
    failed: int