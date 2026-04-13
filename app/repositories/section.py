from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.section import BookSection


class SectionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_section(self, book_id: str, section_idx: int) -> BookSection | None:
        stmt = select(BookSection).where(
            and_(
                BookSection.book_id == book_id,
                BookSection.section_idx == section_idx,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_sections_range(
        self,
        book_id: str,
        start_idx: int,
        end_idx: int,
    ) -> list[BookSection]:
        """start_idx ~ end_idx 범위의 섹션들을 순서대로 반환"""
        stmt = (
            select(BookSection)
            .where(
                and_(
                    BookSection.book_id == book_id,
                    BookSection.section_idx >= start_idx,
                    BookSection.section_idx <= end_idx,
                )
            )
            .order_by(BookSection.section_idx)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_sections(self, book_id: str) -> list[BookSection]:
        """한 권의 모든 섹션을 순서대로 반환"""
        stmt = (
            select(BookSection)
            .where(BookSection.book_id == book_id)
            .order_by(BookSection.section_idx)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_total_sections(self, book_id: str) -> int:
        from sqlalchemy import func as sqlfunc
        stmt = select(sqlfunc.count()).where(BookSection.book_id == book_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0