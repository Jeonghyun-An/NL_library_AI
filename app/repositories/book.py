from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.book import Book
from schemas.book import BookCreate, BookOut


class BookRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: BookCreate) -> BookOut:
        book = Book(**payload.model_dump())
        self.db.add(book)
        await self.db.flush()
        await self.db.refresh(book)
        return BookOut.model_validate(book)

    async def get_by_cnts_id(self, cnts_id: str) -> BookOut | None:
        result = await self.db.execute(
            select(Book).where(Book.cnts_id == cnts_id)
        )
        book = result.scalar_one_or_none()
        return BookOut.model_validate(book) if book else None

    async def get_by_cnts_ids(self, cnts_ids: list[str]) -> dict[str, BookOut]:
        """cnts_id 목록 조회 → {cnts_id: BookOut}"""
        if not cnts_ids:
            return {}
        result = await self.db.execute(
            select(Book).where(Book.cnts_id.in_(cnts_ids))
        )
        return {
            book.cnts_id: BookOut.model_validate(book)
            for book in result.scalars().all()
        }

    async def get_not_embedded(self) -> list[BookOut]:
        """임베딩 안 된 도서 전체 조회"""
        result = await self.db.execute(
            select(Book).where(Book.is_embedded == False)
        )
        return [BookOut.model_validate(b) for b in result.scalars().all()]

    async def update_embedding_status(
        self, cnts_id: str, milvus_id: str, summary: str
    ) -> None:
        result = await self.db.execute(
            select(Book).where(Book.cnts_id == cnts_id)
        )
        book = result.scalar_one_or_none()
        if book:
            book.milvus_id   = milvus_id
            book.summary     = summary
            book.is_embedded = True
            await self.db.flush()
