import re
import httpx
from core.config import get_settings

# "X 같은 책", "X처럼", "X와 비슷한 책" 등 유사도 검색 패턴
_SIMILAR_RE = re.compile(
    r"[\"']?(.+?)[\"']?\s*(?:같은|처럼|과\s*비슷한|와\s*비슷한|과\s*유사한|와\s*유사한)\s*책"
)

_REWRITE_SYSTEM = """당신은 도서관 검색 전문가입니다.
사용자의 검색 의도를 정확히 파악하여 의미 기반 벡터 검색에 최적화된 쿼리로 변환하세요.

[변환 규칙]
1. 비유적·감정적 표현 → 구체적 주제·테마 키워드로 변환
2. "X 같은 책", "X처럼", "X와 비슷한" 등 유사도 검색일 때:
   - 제목·저자명은 쿼리에 절대 포함하지 마세요 (그 자체를 찾는 게 아님)
   - 해당 작품의 핵심 주제의식, 심리적 요소, 서사 분위기, 사회적 맥락을 추출하세요
   - 표층 장르명(현대문학, 소설, 시)보다 구체적 테마를 우선하세요
3. 특정 도서를 직접 찾는 경우에만 제목·저자를 포함하세요

[유사도 검색 예시]
- "한강의 채식주의자 같은 책" → "인간 내면의 욕망과 억압, 사회 규범에 대한 파격적 저항, 여성 신체와 자기결정권, 심리적 붕괴와 내면 폭력성, 실존적 반항"
- "카프카 변신 같은 책" → "존재 소외와 자아 상실, 부조리한 현실 속 인간 소외, 가족과 사회의 폭력적 시선, 실존주의적 불안"
- "무라카미 하루키처럼 몽환적인 소설" → "현실과 환상의 경계, 도시 고독과 상실감, 내면 탐색과 정체성 혼란, 초현실적 서사"

변환된 쿼리만 출력하세요. 한국어로 작성하세요."""


async def rewrite_query(query: str, db=None) -> str:
    # 유사도 쿼리("X 같은 책")이고 DB에 해당 도서의 테마가 있으면 바로 사용
    if db:
        enriched = await _enrich_from_db(query, db)
        if enriched:
            return enriched

    cfg = get_settings()
    payload = {
        "model": cfg.VLLM_MODEL,
        "messages": [
            {"role": "system", "content": _REWRITE_SYSTEM},
            {"role": "user", "content": f"원본 쿼리: {query}"},
        ],
        "max_tokens": 256,
        "temperature": 0.0,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{cfg.VLLM_BASE_URL}/chat/completions", json=payload)
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
