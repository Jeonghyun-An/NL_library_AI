import re
import httpx
from core.config import get_settings
from services.prompts import get_prompt

# "X 같은 책", "X처럼", "X와 비슷한 책" 등 유사도 검색 패턴
_SIMILAR_RE = re.compile(
    r"[\"']?(.+?)[\"']?\s*(?:같은|처럼|과\s*비슷한|와\s*비슷한|과\s*유사한|와\s*유사한)\s*책"
)


async def rewrite_query(query: str, db=None) -> str:
    # 유사도 쿼리("X 같은 책")이고 DB에 해당 도서의 테마가 있으면 바로 사용
    if db:
        enriched = await _enrich_from_db(query, db)
        if enriched:
            return enriched

    cfg = get_settings()
    system, user, params = get_prompt("query_rewrite").render(query=query)
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **params,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def _enrich_from_db(query: str, db) -> str | None:
    """유사도 검색 패턴 감지 → 참조 도서의 저장된 themes로 쿼리 보강."""
    match = _SIMILAR_RE.search(query)
    if not match:
        return None
    ref_title = match.group(1).strip()
    try:
        from sqlalchemy import select
        from models.book import Book
        result = await db.execute(
            select(Book).where(Book.title.ilike(f"%{ref_title}%")).limit(1)
        )
        book = result.scalar_one_or_none()
        if book and book.themes:
            return book.themes
    except Exception:
        pass
    return None
