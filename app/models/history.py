"""history.py — 사이드바 기록(도서 검색·논문 검색·딥리서치)

소유 단위는 브라우저 ID(session_id)다. 로그인이 생기면 user_id 로 묶는다 — 지금은
자리만 두고 항상 NULL 이다. 사용자가 지워도 행은 남는다(deleted_at, 소프트 삭제).

딥리서치 진행 상태는 여기 두지 않는다. 조회할 때 research_jobs 에서 붙인다 — 두 곳에
두면 워커가 바꾼 상태와 기록의 상태가 어긋난다.
"""
from sqlalchemy import Column, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

HISTORY_KINDS = ("book", "paper", "research")


class HistoryItem(Base):
    __tablename__ = "history_items"
    __table_args__ = (
        # 사이드바는 "이 브라우저의 이 종류, 최신순"만 읽는다. 지운 행을 인덱스에서
        # 빼 두면 소프트 삭제가 쌓여도 목록 조회가 느려지지 않는다.
        Index(
            "ix_history_items_session_kind_created",
            "session_id", "kind", text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # 브라우저가 만든 UUID 가 그대로 PK 다 — 서버 응답을 기다리지 않고 URL(?h=)에
    # 넣을 수 있어야 하고, 실패 뒤 재전송해도 같은 행이 된다. 그래서 ORM 기본값이 없다.
    id         = Column(UUID(as_uuid=True), primary_key=True)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    user_id    = Column(String(64))
    kind       = Column(String(16), nullable=False)
    title      = Column(Text, nullable=False)
    params     = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # none_as_null: 파이썬 None 을 JSON null 이 아니라 SQL NULL 로 쓴다. 이게 없으면
    # "snapshot IS NOT NULL" 로 계산하는 has_snapshot 이 늘 참이 되고, 재전송이
    # 빠뜨린 칸을 기존 값으로 채우는 COALESCE 도 동작하지 않는다.
    snapshot   = Column(JSONB(none_as_null=True))
    ai         = Column(JSONB(none_as_null=True))
    ref_id     = Column(String(64))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))
