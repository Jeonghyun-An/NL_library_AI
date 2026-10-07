"""research_work.py — 연구 어시스턴트(round06) 테이블.

딥리서치를 [이 연구 이어가기] 로 이어간 연구 한 건과 그 산출물. 연구 id = 출발 딥리서치 잡 id.
기존 테이블은 건드리지 않는다. create_all 이 만들고 alembic 은 0007 로 stamp 한다(함정 14).
create_all 은 있는 테이블에 칼럼·인덱스를 더하지 못한다 — 바뀌는 모양은 아래 JSONB 안에 둔다.

JSONB 칼럼의 모양(06b — 상수·키는 services/research_work/shapes.py, 만드는 곳은 그 모듈들):

  research_works.concepts         [str]                                             (06a)
  research_works.concept_members  {개념: [cnts_id …]}  — 코사인 ≥ MEMBER_THRESHOLD, 높은 순. 개념이 바뀌면 {}(06a 규칙)
  research_works.progress         {"topics": int, "reading": int, "sections": int, "sections_total": 6}
  research_works.corpus_snapshot  {"n_papers": int, "from": str, "to": str, "at": iso} | null
                                  — 출발 잡 report.range + 잡 finished_at(이어가기 때)
  research_works.topic_id         고른 주제(research_topics.id) | null
  research_topics.seed            {"key": "future:2:0"|"insufficient:3", "kind": "future"|"insufficient",
                                   "section_idx": int|null, "subq_idx": int|null, "heading": str, "text": str,
                                   "papers": [cnts_id], "adopted": int|null}         — user 카드는 {}
  research_topics.card            Card | {}
  research_topics.corpus_snapshot research_works.corpus_snapshot 과 같은 모양
  research_reading.origin_ref     evidence: {"subq_idx": [int], "rank": {"0": int}, "chunks": {"0": [chunk_id]},
                                             "chunk_scores": {"0": {chunk_id: float}}, "verdict": {"0": str},
                                             "first_round": {"0": int}}  (06a)
                                  revived:  {"subq_idx": int, "round": int|null, "note": str}
                                  user:     {}
  research_proposals.outline      Outline | {}
  research_proposals.sections     {절 키: Section}  — 06b 키는 prior.g1~g4·gap

  Figure    = {"id": "F1", "label": str, "value": str}
  Card      = {"title": str, "question": str, "evidence": [cnts_id], "figure_sentence": str|null,
               "figures": [Figure], "latest_year": int|null, "edited": bool,
               "checks": {"numbers": [str], "softened": int, "recovered": int}, "gen_id": int|null}
  Outline   = {"topic": {"id": int, "title": str, "question": str}, "basis": "concept"|"subq",
               "concepts": [str],                                    — 목차를 만들 때의 핵심 개념
               "groups": [{"key": "prior.g1", "name": str, "hint": str, "papers": [cnts_id]}],
               "questions": [str], "question": str|null, "method": str,
               "state": "draft"|"approved", "gen_id": int|null, "approved_at": iso|null}
  Section   = {"key": str, "gen_id": int, "evidence": {"E1": cnts_id}, "figures": [Figure],
               "basis": {"topic_id": int|null, "papers": [cnts_id]}, "note": str|null,
               "paragraphs": [Paragraph], "model": str|null, "updated_at": iso}
  Paragraph = {"id": "p1", "text": str, "state": "proposed"|"accepted"|"edited"|"authored",
               "cites": [cnts_id], "checks": ParagraphChecks, "gen_id": int|null}
  ParagraphChecks = {"dropped": int, "dropped_f": int, "unmarked": int, "numbers": [str], "softened": int}

  사용자 카드(직접 쓰기)는 evidence·figures 가 비고 figure_sentence·latest_year·gen_id 가 null 이다.
  '다시 맞춤 필요'(stale)는 저장하지 않고 조회 때 계산한다(services/research_work/proposal_views.stale_flags).
  research_generations.input·output 의 모양은 kind 별 실행기 모듈(services/research_work/<kind>.py)에 있다.
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, SmallInteger, String,
    Text, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

WORK_PHASES = ("topics", "reading", "proposal", "done")
GEN_KINDS = ("concepts", "topic_card", "refine", "facet", "outline", "section", "paragraph")
GEN_STATUSES = ("queued", "running", "done", "failed", "canceled")
GEN_OPEN_STATUSES = ("queued", "running")
PRIORITY_USER = 10          # 사용자가 누른 생성
PRIORITY_BACKGROUND = 0     # 배경 특징 추출(06c)
TOPIC_ORIGINS = ("report_seed", "grid_seed", "other", "refine", "user")
TOPIC_STATES = ("candidate", "picked", "folded", "insufficient")
READING_STATES = ("candidate", "in", "out")
READING_ORIGINS = ("evidence", "revived", "broaden", "related", "user")
FACET_SCHEMA_VER = 1


class ResearchWork(Base):
    __tablename__ = "research_works"
    __table_args__ = (
        Index(
            "ix_research_works_owner_created", "owner_sid", text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
    id              = Column(UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="CASCADE"),
                             primary_key=True)
    owner_sid       = Column(String(64))
    user_id         = Column(String(64))
    share_token     = Column(String(64))
    phase           = Column(String(16), nullable=False, server_default=text("'topics'"))
    concepts        = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    concept_members = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    topic_id        = Column(BigInteger)
    progress        = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    corpus_snapshot = Column(JSONB(none_as_null=True))
    memo            = Column(Text)
    is_example      = Column(Boolean, nullable=False, server_default=text("false"))
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                             onupdate=func.now())
    deleted_at      = Column(DateTime(timezone=True))


class ResearchGeneration(Base):
    __tablename__ = "research_generations"
    __table_args__ = (
        # 연구마다 도는 생성은 1건 — 전역 1건 디스패처(§6-3)의 이중 안전장치.
        # sqlite_where 를 함께 두지 않으면 SQLite 테스트에서 전체 유니크가 된다
        Index(
            "ux_research_generations_running", "work_id", unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
        # 정렬 키 priority DESC → created_at → id — pick_next·queue_position(services/research_work/dispatch.py)·
        # 0007 의 같은 인덱스가 함께 바뀐다
        Index(
            "ix_research_generations_queued", text("priority DESC"), "created_at", "id",
            postgresql_where=text("status = 'queued'"),
        ),
    )
    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    work_id     = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    kind        = Column(String(16), nullable=False)
    target      = Column(String(64))
    priority    = Column(SmallInteger, nullable=False, server_default=text("0"))
    status      = Column(String(16), nullable=False, server_default=text("'queued'"))
    model       = Column(String(64))
    input       = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    output      = Column(JSONB(none_as_null=True))
    error       = Column(Text)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at  = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    updated_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                         onupdate=func.now())


class ResearchTopic(Base):
    __tablename__ = "research_topics"
    __table_args__ = (
        # 처음 4장의 자리(1~4)는 연구마다 유일 — 4번째 격자 카드 자리가 이미 차 있으면 자동 생성하지 않는다(§5-2)
        Index(
            "ux_research_topics_slot", "work_id", "slot", unique=True,
            postgresql_where=text("slot IS NOT NULL"),
            sqlite_where=text("slot IS NOT NULL"),
        ),
    )
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    work_id         = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    # 자기 참조 FK(ON DELETE CASCADE) — 부모를 지울 때 자식을 찾는 조회가 테이블을 훑지 않게 인덱스를 둔다
    parent_id       = Column(BigInteger, ForeignKey("research_topics.id", ondelete="CASCADE"), index=True)
    slot            = Column(SmallInteger)
    origin          = Column(String(16), nullable=False)
    seed            = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    card            = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    state           = Column(String(16), nullable=False, server_default=text("'candidate'"))
    corpus_snapshot = Column(JSONB(none_as_null=True))
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                             onupdate=func.now())


class ResearchGapCheck(Base):
    __tablename__ = "research_gap_checks"
    __table_args__ = (Index("ix_research_gap_checks_work_cell", "work_id", "cell_key"),)
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    work_id         = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                             nullable=False)
    cell_key        = Column(String(128), nullable=False)
    query           = Column(Text, nullable=False)
    results         = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    m               = Column(Integer, nullable=False)
    verdict         = Column(String(16), nullable=False)
    corpus_snapshot = Column(JSONB(none_as_null=True))
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchReading(Base):
    __tablename__ = "research_reading"
    work_id     = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                         primary_key=True)
    cnts_id     = Column(String(64), primary_key=True)
    state       = Column(String(16), nullable=False, server_default=text("'candidate'"))
    origin      = Column(String(16), nullable=False)
    origin_ref  = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    group_label = Column(Text)
    position    = Column(Integer)
    note        = Column(Text)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                         onupdate=func.now())


class PaperFacet(Base):
    __tablename__ = "paper_facets"
    cnts_id    = Column(String(64), primary_key=True)
    schema_ver = Column(SmallInteger, primary_key=True)
    facets     = Column(JSONB, nullable=False)
    model      = Column(String(64))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResearchProposal(Base):
    __tablename__ = "research_proposals"
    work_id    = Column(UUID(as_uuid=True), ForeignKey("research_works.id", ondelete="CASCADE"),
                        primary_key=True)
    version    = Column(Integer, nullable=False, server_default=text("1"))
    outline    = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sections   = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                        onupdate=func.now())
