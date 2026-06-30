import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from core.config import get_settings
from core.deps import get_db
from schemas.book import (
    SearchRequest,
    ChunkSearchResponse,
    BookSearchResponse,
    BookOut,
)
from repositories.book import BookRepository
from services.search.pipeline import search

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/papers", tags=["papers"])


class PaperSummaryItem(BaseModel):
    book_id: str
    title: str
    authors: str = ""
    best_chunk_text: str = ""


class PaperSummaryRequest(BaseModel):
    query: str
    papers: list[PaperSummaryItem]


class RelatedPaperResult(BaseModel):
    book_id: str
    score: float
    book_info: Optional[BookOut] = None


class RelatedPapersResponse(BaseModel):
    source_id: str
    results: list[RelatedPaperResult]


class CitationResponse(BaseModel):
    book_id: str
    korean: str
    english: str


class RelatedReasonRequest(BaseModel):
    source_id: str
    related_id: str


class PaperReasonRequest(BaseModel):
    paper_id: str
    query: str
    rewritten_query: str = ""


@router.post(
    "/search",
    response_model=ChunkSearchResponse | BookSearchResponse,
)
async def search_papers(
    req: SearchRequest,
    session_id: str | None = Header(None, alias="x-session-id"),
    db: AsyncSession = Depends(get_db),
):
    if not session_id or session_id == "null":
        session_id = str(uuid4())

    result = await search(
        req.query,
        mode=req.mode,
        top_k=req.top_k,
        use_rewrite=req.use_rewrite,
        use_rerank=req.use_rerank,
        doc_scope="paper",
        db=db,
    )

    if isinstance(result, BookSearchResponse):
        repo = BookRepository(db)
        for bg in result.books:
            book = await repo.get_by_cnts_id(bg.book_id)
            if book:
                bg.book_info = BookOut.model_validate(book)

    return result


@router.post("/summary/stream")
async def stream_paper_summary(req: PaperSummaryRequest):
    """논문 검색 결과 핵심 요약 SSE 스트리밍.

    프론트엔드는 POST /api/papers/search 와 병렬로 이 엔드포인트를 호출한다.
    text 토큰 이벤트를 스트리밍하고 마지막에 sources 이벤트를 전송한다.
    """
    from services.search.paper_summary import stream_paper_summary as _stream

    papers_dicts = [p.model_dump() for p in req.papers]
    return StreamingResponse(
        _stream(req.query, papers_dicts),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{cnts_id}/related",
    response_model=RelatedPapersResponse,
)
async def get_related_papers(
    cnts_id: str,
    top_k: int = 4,
    db: AsyncSession = Depends(get_db),
):
    """현재 논문과 유사한 KCI 논문 추천 (최대 top_k 개, 기본 4).

    제목 + 초록을 BGE-M3로 임베딩해 Milvus 하이브리드 검색을 수행한다.
    """
    from services.search.paper_related import find_related_papers

    if top_k < 1 or top_k > 10:
        raise HTTPException(400, "top_k는 1~10 사이여야 합니다.")

    hits = await find_related_papers(cnts_id, db, top_k=top_k)

    # book_info 일괄 조회
    repo = BookRepository(db)
    book_ids = [h["book_id"] for h in hits if h.get("book_id")]
    book_map = await repo.get_by_cnts_ids(book_ids)

    results = []
    for h in hits:
        r = RelatedPaperResult(**h)
        r.book_info = book_map.get(h.get("book_id"))
        results.append(r)

    return RelatedPapersResponse(source_id=cnts_id, results=results)


@router.get(
    "/{cnts_id}/citation",
    response_model=CitationResponse,
)
async def get_paper_citation(
    cnts_id: str,
    db: AsyncSession = Depends(get_db),
):
    """논문 출처 인용 국문/영문 반환.

    메타데이터(저자, 연도, 제목, 학술지, 권호, UCI)로 KCI 스타일 인용문을 구성한다.
    LLM 호출 없이 즉시 응답한다.
    """
    from services.search.paper_citation import build_citation

    repo = BookRepository(db)
    book = await repo.get_by_cnts_id(cnts_id)
    if not book:
        raise HTTPException(404, f"논문 없음: {cnts_id}")

    citation = build_citation(book)
    return CitationResponse(book_id=cnts_id, **citation)


@router.post("/related-reason/stream")
async def stream_related_reason(
    req: RelatedReasonRequest,
    db: AsyncSession = Depends(get_db),
):
    """두 논문의 유사성 이유 SSE 스트리밍.

    source_id: 현재 보고 있는 논문 ID
    related_id: 사용자가 선택한 연관 논문 ID
    """
    from services.search.paper_summary import stream_related_reason as _stream

    repo = BookRepository(db)
    src = await repo.get_by_cnts_id(req.source_id)
    rel = await repo.get_by_cnts_id(req.related_id)

    def _get_abstract(book) -> str:
        if not book:
            return ""
        extra = book.extra or {}
        return (
            extra.get("abstract")
            or getattr(book, "abstract", None)
            or book.summary
            or book.introduction
            or ""
        )

    src_title = src.title if src else req.source_id
    src_abstract = _get_abstract(src)
    rel_title = rel.title if rel else req.related_id
    rel_abstract = _get_abstract(rel)

    return StreamingResponse(
        _stream(src_title, src_abstract, rel_title, rel_abstract),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/reason/stream")
async def stream_paper_reason(
    req: PaperReasonRequest,
    db: AsyncSession = Depends(get_db),
):
    """논문 단건 AI 분석 이유 SSE 스트리밍.

    검색 의도 + 논문의 인덱싱 데이터(abstract / summary / introduction)를
    바탕으로 이 논문이 검색 의도와 어떻게 연관되는지 사실 기반으로 분석한다.
    """
    from services.search.paper_summary import stream_paper_reason as _stream

    repo = BookRepository(db)
    paper = await repo.get_by_cnts_id(req.paper_id)
    if not paper:
        raise HTTPException(404, f"논문 없음: {req.paper_id}")

    return StreamingResponse(
        _stream(req.query, paper, req.rewritten_query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/catalog/load")
async def load_kci_catalog(file: UploadFile = File(...)):
    """KCI 논문 메타데이터 xlsx 업로드 → Celery 비동기 처리.

    업로드 파일은 fastapi/워커가 공유하는 /app/data 볼륨에 저장해야
    별도 컨테이너인 워커가 읽을 수 있다 (tempfile은 컨테이너 간 비공유).
    """
    content = await file.read()
    suffix = os.path.splitext(file.filename or "kci.xlsx")[1] or ".xlsx"
    upload_dir = "/app/data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, f"{uuid4().hex}{suffix}")
    with open(save_path, "wb") as f:
        f.write(content)

    from workers.tasks import load_kci_catalog_xlsx
    task = load_kci_catalog_xlsx.delay(save_path)
    return {"task_id": task.id, "filename": file.filename}
