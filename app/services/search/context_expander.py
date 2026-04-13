import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.section import SectionRepository
from schemas.book import ChunkHit
from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

# 126K 중 답변 생성용 여유분을 빼고 컨텍스트에 사용할 토큰 예산
CONTEXT_BUDGET_TOKENS = 100_000
# 한 청크당 앞뒤로 확장할 섹션 수
EXPAND_SECTIONS = 2


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 1.5))


@dataclass
class ExpandedContext:
    """확장된 컨텍스트 결과"""
    book_id: str
    chunk_text: str           # 원래 히트된 청크 텍스트
    expanded_text: str        # 확장된 원문 (앞뒤 섹션 포함)
    section_range: tuple[int, int]  # (start_idx, end_idx)
    page_range: tuple[int, int]
    token_count: int


async def expand_context(
    chunks: list[ChunkHit],
    db: AsyncSession,
    *,
    budget_tokens: int = CONTEXT_BUDGET_TOKENS,
    expand_sections: int = EXPAND_SECTIONS,
) -> list[ExpandedContext]:
    """
    히트된 청크들의 주변 원문을 로드하여 확장된 컨텍스트 반환

    Args:
        chunks: 검색/리랭킹된 청크 리스트
        db: AsyncSession
        budget_tokens: 전체 토큰 예산
        expand_sections: 청크 앞뒤로 확장할 섹션 수

    Returns:
        ExpandedContext 리스트 (토큰 예산 내에서 최대한 채움)
    """
    repo = SectionRepository(db)
    contexts = []
    used_tokens = 0
    seen_sections: set[tuple[str, int]] = set()  # (book_id, section_idx) 중복 방지

    for chunk in chunks:
        if used_tokens >= budget_tokens:
            break

        book_id = chunk.book_id
        center_idx = chunk.section_idx

        # 앞뒤 섹션 범위 계산
        start_idx = max(0, center_idx - expand_sections)
        total = await repo.get_total_sections(book_id)
        end_idx = min(total - 1, center_idx + expand_sections) if total > 0 else center_idx

        # 이미 로드한 섹션은 스킵
        range_key = (book_id, center_idx)
        if range_key in seen_sections:
            continue
        seen_sections.add(range_key)

        # 섹션 로드
        sections = await repo.get_sections_range(book_id, start_idx, end_idx)
        if not sections:
            # 섹션이 없으면 청크 텍스트 그대로 사용
            contexts.append(ExpandedContext(
                book_id=book_id,
                chunk_text=chunk.text,
                expanded_text=chunk.text,
                section_range=(center_idx, center_idx),
                page_range=(chunk.page_start, chunk.page_end),
                token_count=_estimate_tokens(chunk.text),
            ))
            used_tokens += _estimate_tokens(chunk.text)
            continue

        # 토큰 예산 내에서 섹션 텍스트 조립
        expanded_parts = []
        section_tokens = 0
        actual_start = sections[0].section_idx
        actual_end = sections[-1].section_idx
        page_start = sections[0].page_start or chunk.page_start
        page_end = sections[-1].page_end or chunk.page_end

        for sec in sections:
            sec_tokens = sec.token_count or _estimate_tokens(sec.full_text)
            if used_tokens + section_tokens + sec_tokens > budget_tokens:
                break
            expanded_parts.append(sec.full_text)
            section_tokens += sec_tokens
            actual_end = sec.section_idx
            page_end = sec.page_end or page_end

        expanded_text = "\n\n".join(expanded_parts)
        used_tokens += section_tokens

        contexts.append(ExpandedContext(
            book_id=book_id,
            chunk_text=chunk.text,
            expanded_text=expanded_text,
            section_range=(actual_start, actual_end),
            page_range=(page_start, page_end),
            token_count=section_tokens,
        ))

        log.info(
            f"[{book_id}] 섹션 {actual_start}~{actual_end} 확장 "
            f"({section_tokens} tokens, 누적 {used_tokens}/{budget_tokens})"
        )

    return contexts