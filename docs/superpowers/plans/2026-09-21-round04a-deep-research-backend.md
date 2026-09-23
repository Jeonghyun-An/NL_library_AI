# 논문 딥리서치 에이전트 — 백엔드 구현 계획 (round04a)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 질문 하나를 받아 하위질문으로 분해하고, 하위질문별로 논문을 탐색·자기점검·재탐색한 뒤, 근거가 검증된 인용이 달린 보고서 JSON을 만들어 내는 비동기 백엔드를 구축한다.

**Architecture:** `app/services/research/` 패키지. 각 단계는 `ResearchState` 를 받아 갱신해 돌려주는 함수이고, 순수 계산(파싱·점수·인용 검증)과 I/O(LLM·Milvus·DB)를 파일 단위로 가른다. 실행은 Celery 태스크가 맡고 진행은 Redis pub/sub으로 중계한다. 굵은 단계는 `research_steps` 에 영속하고 잔이벤트는 Redis에만 흘린다.

**Tech Stack:** FastAPI · SQLAlchemy(async API / sync worker) · Celery · Redis pub/sub · Alembic · pytest

**설계 근거:** `docs/superpowers/specs/2026-09-21-deep-research-agent-design.md`

**범위:** 이 계획은 **백엔드만** 다룬다. 프론트(슬래시 진입 · 계획 승인 UI · 진행 패널 · 보고서 렌더 · 인용칩)는 round04b 별도 계획이다. 이 계획이 끝나면 `curl` 로 SSE와 보고서 JSON을 확인할 수 있다.

**실행 전 확인:** docker·비동기 작업 전 `docs/ops/recurring-gotchas.md` 를 읽는다. 특히 4번(스크립트 경로 실행 시 `PYTHONPATH=/app`), 7번(`text()` 안에서 `:param::type` 금지), 10번(jsonb `?` 는 키 존재만 본다).

**테스트 실행 명령 (이 프로젝트 공통):**

```bash
python -m pytest app/tests -q --ignore=app/tests/test_book_chat.py --ignore=app/tests/test_build_manifest.py --ignore=app/tests/test_loaders.py
```

제외한 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 collect 단계에서 실패한다. 이 계획과 무관하다. 착수 시점 기준선은 **134 passed** 다. 라운드 종료 시점(머지 전 리뷰와 그 반영 검수까지 끝난 뒤)은 **549 passed** 다(완료노트 §4).

---

## 이 계획의 코드 블록과 최종 코드

> **Task 절의 "완료본" 코드 블록은 최종 코드가 아니다.** 각 절은 그 Task 를 동기화한 시점의 저장소 파일과 일치했지만, 그 뒤에 두 번 더 바뀌었다 — 라이브 검증 중 고친 종합 버그(`b6360b8`, 2026-09-23)와 머지 전 리뷰 반영(2026-09-23, `docs/roadmap/round04a-완료노트.md` §머지 전 리뷰). 바뀐 절 머리에는 **이후 변경** 을 달아 커밋과 요지를 적었다. 코드 블록 자체는 다시 쓰지 않았다.
>
> **최종 코드는 저장소가 정본이다.** 교본(클론코딩)·재현은 이 블록이 아니라 저장소 파일에서 옮긴다. 블록을 그대로 옮기면 라이브에서 고친 "절 1개·논문 1편" 종합 버그와, 취소한 잡이 `completed` 로 되살아나는 결함이 그대로 재현된다. 설계가 어떻게 바뀌었는지는 spec 의 **구현 시 변경** 표기에 있다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `app/models/research.py` | `ResearchJob` · `ResearchStep` ORM |
| `app/alembic/versions/0005_research_jobs.py` | 테이블 2종 마이그레이션 |
| `app/services/research/state.py` | `ResearchState` · `SubQuestion` · `Evidence` · `Chunk` · 기본 params |
| `app/services/research/scoring.py` | 피인용 연차 정규화 · 점수 혼합 (순수) |
| `app/services/research/citations.py` | 근거 조립 · 마커 검증 (순수) |
| `app/services/research/planner.py` | 계획 파싱(순수) + LLM 호출 |
| `app/services/research/critic.py` | 판정 파싱(순수) + LLM 호출 |
| `app/services/research/explorer.py` | 하위질문 탐색 (검색·리랭킹·점수) |
| `app/services/research/synthesizer.py` | 보고서 조립(순수) + LLM 호출 |
| `app/services/research/runner.py` | 단계 오케스트레이션 |
| `app/services/research/relay.py` | Redis pub/sub 발행·구독 · 종료 이벤트 모양(`terminal_event`) |
| `app/services/research/llm_json.py` | LLM 응답에서 JSON 추출 — 계획·점검·종합 공용 (Task 5·6 리뷰에서 추가) |
| `app/domains/nl_library/prompts/research_plan.yaml` | 계획 수립 프롬프트 |
| `app/domains/nl_library/prompts/research_critique.yaml` | 자기점검 프롬프트 |
| `app/domains/nl_library/prompts/research_synthesize.yaml` | 종합 프롬프트 |
| `app/workers/research_tasks.py` | Celery 태스크 3종(계획·실행·정체 회수) |
| `app/api/research.py` | API 5종(생성·승인·재시도·취소·조회) + SSE |

표 밖에서 바뀐 기존 파일(최종 기준): `app/main.py`(라우터 등록) · `app/workers/celery_app.py`(태스크 라우팅·회수 beat) · `app/core/config.py`(`RESEARCH_QUEUE`, 기본 `q_llm` · `RESEARCH_PLAN_QUEUE`, 비우면 `RESEARCH_QUEUE`) · `app/services/search/pipeline.py`(`use_metadata_filter`·`chunk_filter` 인자, 리랭크 폴백 예외 좁힘 — 기본값은 기존 동작) · `app/services/search/reranker.py`(GPU 가 없으면 float32) · `docker-compose*.yml`(전용 워커 `celery-research`·계획 워커 `celery-research-plan`). 적재 코드(`app/services/ingestion/`·`workers/tasks.py`·`workers/job_runtime.py`)는 건드리지 않았다.

순수 계산을 `scoring.py`·`citations.py` 로 뽑아내는 이유는 **Milvus·LLM 없이 테스트하기 위해서**다. `scripts/recovery/rewrite_milvus_doc_type.py` 가 같은 구조로 16개 테스트를 돌린다.

---

## Task 1: 데이터 모델과 마이그레이션 — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - `f1ba3e1` — `research_jobs` 에 `stage`·`state_snapshot`·`last_error` 컬럼이 추가됐다(Task 10 재설계의 재개 체크포인트). 모델과 `0005` 둘 다 바뀌었는데 Task 10 절은 모델만 다시 싣는다 — **이 계획 어디에도 최종 `0005` 가 없다.** `app/alembic/versions/0005_research_jobs.py` 를 본다.
> - 머지 전 리뷰 — `models/research.py` 에 종료 상태 상수 `TERMINAL_STATUSES` 추가, `STEP_KINDS` 에서 `critique` 삭제 — 워커가 기록하지 않는 kind 라 프론트에 영원히 안 도는 분기를 만든다(자기점검은 `search` 행의 `verdict`·`note` 로 남는다). 아래 블록의 `STEP_KINDS` 에는 아직 있다. 둘 다 스키마 변화 없음.
>
> 구현·리뷰가 끝났다. 아래 코드는 **리뷰 반영이 끝난 Task 1 동기화 시점(`305a52b`)의 상태**이며 그때 저장소 파일과 일치했다
> (착수 시점 초안이 아니다). 커밋: `3973b9e` → `680af5c` → `a326203`.
>
> 착수 초안과 달라진 것: `(job_id, seq)` 를 인덱스가 아니라 **유일 제약**으로 걸었고(중복 step 이
> 조용히 쌓이는 것을 DB 가 막는다), 모델↔마이그레이션 정합·인덱스·유일제약을 실제로 대조하는
> 테스트를 붙였다. `app/alembic/env.py` 에 모델 등록 1줄도 추가했다 — 빠뜨리면 향후
> `autogenerate` 가 이 테이블들을 모르는 것으로 보고 `DROP TABLE` 마이그레이션을 만든다.

**Files:**
- Create: `app/models/research.py`
- Create: `app/alembic/versions/0005_research_jobs.py`
- Modify: `app/alembic/env.py` (모델 등록 1줄)
- Test: `app/tests/test_research_models.py`

- [x] **Step 1: 모델**

```python
# app/models/research.py
"""research.py — 딥리서치 잡 모델

research_jobs  : 리서치 1건 (질문 1개 = 잡 1개)
research_steps : 의미 있는 단계 (계획 · 하위질문별 탐색 · 점검 · 종합)

research_steps 는 진행 패널이자 보고서의 탐색 경로 섹션이다. 초당 갱신되는
잔이벤트(카운터 등)는 여기 쓰지 않고 Redis pub/sub 으로만 흘린다 — 입자가
다르고, 보고서에 남을 것과 몇 초 뒤 사라질 것을 한 테이블에 섞으면
보존 정책과 append/update 성격이 충돌한다.
"""
import uuid

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

JOB_STATUSES = (
    "created", "planning", "awaiting_approval",
    "running", "completed", "failed", "canceled",
)
STEP_KINDS = ("plan", "search", "critique", "synthesize")
STEP_STATUSES = ("pending", "running", "done", "failed")


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question    = Column(Text, nullable=False)
    status      = Column(String(24), nullable=False, default="created", index=True)
    params      = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    plan        = Column(JSONB)      # 사용자 수정이 반영된 하위질문 목록
    report      = Column(JSONB)
    last_error  = Column(Text)
    created_by  = Column(String(64))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    started_at  = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class ResearchStep(Base):
    __tablename__ = "research_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "seq", name="uq_research_steps_job_seq"),
        Index(
            "ix_research_steps_inflight", "updated_at",
            postgresql_where=text("status = 'running'"),
        ),
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id      = Column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq         = Column(Integer, nullable=False)
    kind        = Column(String(16), nullable=False)
    subq_idx    = Column(Integer)
    title       = Column(Text, nullable=False)
    detail      = Column(Text)
    status      = Column(String(16), nullable=False, default="pending")
    # kind 별 shape — API 가 가공 없이 프론트로 넘기고 프론트가 kind 로 분기한다.
    # plan:       {"subquestions": [...]}
    # search:     {"queries": [...], "adopted": n, "verdict": "...", "note": "..."}
    # synthesize: {"sections": n}
    # 실패 공통:   {"error": "..."}
    result      = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    updated_at  = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
```

- [x] **Step 2: 마이그레이션**

```python
# app/alembic/versions/0005_research_jobs.py
"""딥리서치 잡 테이블

research_jobs / research_steps — 질문 1건과 그 실행 단계.

Revision ID: 0005_research_jobs
Revises: 0004_doc_type_extra_ingest_jobs
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0005_research_jobs"
down_revision: Union[str, None] = "0004_doc_type_extra_ingest_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="created"),
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("plan", JSONB()),
        sa.Column("report", JSONB()),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_by", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_research_jobs_status", "research_jobs", ["status"])

    op.create_table(
        "research_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id", UUID(as_uuid=True),
            sa.ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("subq_idx", sa.Integer()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("result", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "seq", name="uq_research_steps_job_seq"),
    )
    op.create_index(
        "ix_research_steps_inflight", "research_steps", ["updated_at"],
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_table("research_steps")
    op.drop_table("research_jobs")
```

- [x] **Step 3: `app/alembic/env.py` 에 모델 등록**

다른 모델들을 임포트하는 자리에 한 줄을 더한다.

```python
from models import research as _research_mod  # noqa: F401, E402
```

- [x] **Step 4: 테스트**

`_run_migration_upgrade` 가 핵심이다. 로컬에 `alembic` 이 설치돼 있지 않아 `op` 를 스텁으로 갈아끼우고 `upgrade()` 를 실제로 실행한다. 캡처한 인자로 **진짜 `sa.Table` 을 만들어** introspection 하므로, 인자를 직접 파싱할 때 생기는 "캡처 로직 자체가 또 하나의 정합 리스크가 되는" 문제를 피한다.

```python
# app/tests/test_research_models.py
import sys
import types
from pathlib import Path

import sqlalchemy as sa

from models.research import JOB_STATUSES, STEP_KINDS, STEP_STATUSES, ResearchJob, ResearchStep

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0005_research_jobs.py"


def _column_signature(col, include_default=True):
    """(타입, nullable[, 기본값 유무]) — 컬럼 하나의 스키마 정합성 지문.

    PK 는 include_default=False 로 호출한다: 모델의 id 는 default=uuid.uuid4
    (ORM 레벨 생성)이고 마이그레이션에는 대응하는 server_default 가 없다 —
    UUID 를 만드는 주체가 DB 가 아니라 애플리케이션이라는 의도적 설계라
    기본값 유무를 비교 대상에서 뺀다. 타입·nullable 은 PK 도 계속 비교한다.
    """
    sig = [str(col.type), col.nullable]
    if include_default:
        sig.append(col.server_default is not None or col.default is not None)
    return tuple(sig)


def _table_signature(table):
    return {
        c.name: _column_signature(c, include_default=not c.primary_key)
        for c in table.columns
    }


def _model_index_signature(table):
    sig = {}
    for ix in table.indexes:
        where = ix.dialect_options["postgresql"].get("where")
        sig[ix.name] = {
            "name": ix.name,
            "table_name": table.name,
            "columns": [c.name for c in ix.columns],
            "postgresql_where": str(where) if where is not None else None,
        }
    return sig


def _run_migration_upgrade(monkeypatch, migration_path=MIGRATION_PATH):
    """0005 의 upgrade() 를 실제 alembic 없이 실행하고 create_table/create_index 호출을 캡처한다.

    로컬 venv 에 alembic 이 설치돼 있지 않아 (app/requirements.txt 에는 있으나 미설치)
    `from alembic import op` 를 만족시키는 최소 스텁만 넣는다 — upgrade() 는 op.create_table /
    op.create_index 만 호출하므로 그 둘만 흉내 내면 충분하다.

    create_table 은 넘어온 Column/UniqueConstraint 인자로 실제 sa.Table 을 만들어 바인딩한다
    (컬럼 이름만이 아니라 타입·nullable·기본값·제약까지 실제 SQLAlchemy introspection 으로
    읽기 위해서 — 인자를 훑어 직접 파싱하면 캡처 로직 자체가 또 하나의 정합 리스크가 된다).
    """
    import importlib.util as u

    tables = {}
    unique_constraints = {}
    indexes = []

    def fake_create_table(name, *args, **kwargs):
        table = sa.Table(name, sa.MetaData(), *args)
        tables[name] = _table_signature(table)
        unique_constraints[name] = {
            c.name: [col.name for col in c.columns]
            for c in table.constraints
            if isinstance(c, sa.UniqueConstraint)
        }

    def fake_create_index(name, table_name, columns, **kwargs):
        where = kwargs.get("postgresql_where")
        indexes.append({
            "name": name,
            "table_name": table_name,
            "columns": list(columns),
            "postgresql_where": str(where) if where is not None else None,
        })

    fake_op = types.ModuleType("alembic.op")
    fake_op.create_table = fake_create_table
    fake_op.create_index = fake_create_index

    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op

    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, "alembic.op", fake_op)

    spec = u.spec_from_file_location("_migration_0005", migration_path)
    module = u.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    return {"tables": tables, "unique_constraints": unique_constraints, "indexes": indexes}


class TestResearchModelShape:
    def test_job_table_columns(self):
        cols = set(ResearchJob.__table__.columns.keys())
        assert {"id", "question", "status", "params", "plan", "report"} <= cols

    def test_step_table_columns(self):
        cols = set(ResearchStep.__table__.columns.keys())
        assert {"job_id", "seq", "kind", "subq_idx", "title",
                "detail", "status", "result", "updated_at"} <= cols

    def test_step_has_job_seq_unique_constraint(self):
        uq = next(
            c for c in ResearchStep.__table__.constraints
            if getattr(c, "name", None) == "uq_research_steps_job_seq"
        )
        # 순서가 인덱스 활용 여부를 가른다 — job_id 선두가 아니면 job_id 단독 조회에
        # 이 유일 제약이 인덱스로 쓰이지 못한다.
        assert [c.name for c in uq.columns] == ["job_id", "seq"]

    def test_inflight_index_condition(self):
        idx = next(
            ix for ix in ResearchStep.__table__.indexes
            if ix.name == "ix_research_steps_inflight"
        )
        where_clause = idx.dialect_options["postgresql"]["where"]
        assert str(where_clause) == "status = 'running'"

    def test_step_job_fk_cascades_on_delete(self):
        fk = next(iter(ResearchStep.__table__.c.job_id.foreign_keys))
        assert fk.ondelete == "CASCADE"

    def test_job_status_default_is_valid_status(self):
        assert ResearchJob.__table__.c.status.default.arg in JOB_STATUSES

    def test_step_status_default_is_valid_status(self):
        assert ResearchStep.__table__.c.status.default.arg in STEP_STATUSES

    def test_job_statuses_fit_status_column(self):
        max_len = ResearchJob.__table__.c.status.type.length
        assert all(len(v) <= max_len for v in JOB_STATUSES)

    def test_step_kinds_and_statuses_fit_their_columns(self):
        kind_len = ResearchStep.__table__.c.kind.type.length
        status_len = ResearchStep.__table__.c.status.type.length
        assert all(len(v) <= kind_len for v in STEP_KINDS)
        assert all(len(v) <= status_len for v in STEP_STATUSES)


class TestMigrationMatchesModel:
    def test_upgrade_creates_columns_matching_orm(self, monkeypatch):
        captured = _run_migration_upgrade(monkeypatch)

        assert captured["tables"]["research_jobs"] == _table_signature(ResearchJob.__table__)
        assert captured["tables"]["research_steps"] == _table_signature(ResearchStep.__table__)

    def test_upgrade_unique_constraint_matches_orm(self, monkeypatch):
        captured = _run_migration_upgrade(monkeypatch)

        model_uq = {
            c.name: [col.name for col in c.columns]
            for c in ResearchStep.__table__.constraints
            if isinstance(c, sa.UniqueConstraint)
        }
        assert captured["unique_constraints"]["research_steps"] == model_uq

    def test_upgrade_indexes_match_orm(self, monkeypatch):
        captured = _run_migration_upgrade(monkeypatch)
        migration_indexes = {ix["name"]: ix for ix in captured["indexes"]}

        model_indexes = {}
        for table in (ResearchJob.__table__, ResearchStep.__table__):
            model_indexes.update(_model_index_signature(table))

        assert migration_indexes == model_indexes
```

- [x] **Step 5: 검증**

Run: `python -m pytest app/tests/test_research_models.py -q`
Actual: `12 passed`

Run: `python -m pytest app/tests -q --ignore=app/tests/test_book_chat.py --ignore=app/tests/test_build_manifest.py --ignore=app/tests/test_loaders.py`
Actual: `146 passed` (기준선 134 + 12)

정합 테스트가 실제로 무언가를 지키는지 되돌려 확인했다.

- 마이그레이션의 `kind` 를 `sa.String(16)` → `sa.String(8)` 로 축소 → `{'kind': ('VARCHAR(8)', False, False)} != {'kind': ('VARCHAR(16)', False, False)}` 로 실패
- `ix_research_steps_inflight` 의 `postgresql_where` 제거 → `postgresql_where: None` vs `"status = 'running'"` 로 실패

**되돌렸을 때 실패하지 않는 테스트는 아무것도 지키지 않는다.**

---

## Task 2: 상태 객체와 기본 파라미터 — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - `a29c9a7`·`f1ba3e1` — `SubQuestion.parse_failed`·`failed` 와 `snapshot_state`·`restore_state` 가 추가됐다. 그 시점 모양은 Task 10 절에 다시 실려 있다.
> - 머지 전 리뷰 — `SubQuestion` 에 `capped`(상한 때문에 못 실은 후보 수)·`evidence_chunks`(하위질문별 매칭 청크)·`chunk_scores`(그 하위질문 검색어로 받은 청크 점수) 추가, `evidence_ids` 는 하위질문 안 순위순. `snapshot_state` 는 `asdict` 로 전 필드를 담고, `restore_state` 는 모르는 키를 무시하고 없는 키는 기본값으로 채우며 params 를 기본값에 다시 얹는다(구버전 스냅샷 재개). `NaN`·무한대 파라미터 거부. 읽는 곳이 없던 `ResearchState.recheck_count` 제거.
>
> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 동기화 시점(`0971f21`·`3c138c6`, `rank_score` 는 `a168e1d`)의 상태**이며 그때 저장소 파일과 일치했다.

딥리서치 실행 중 상태를 담는 dataclass 들과 깊이 파라미터. 파이프라인의 각 단계는 `ResearchState` 를 받아 갱신해 돌려주므로 Celery·Redis·Milvus 없이 테스트된다.

리뷰 반영으로 초안과 달라진 것: `merge_params` 가 키뿐 아니라 **값의 타입·범위까지 검증**한다(`citation_weight: -0.2` 가 통과하면 영향력 높은 논문 점수를 깎아 순위가 조용히 뒤집힌다). `DEFAULT_PARAMS` 는 `MappingProxyType` 으로 잠갔고, `HitRow(TypedDict)` 와 `VERDICTS` 상수가 추가됐다. `HitRow.rank_score` 는 Task 7 리뷰에서 붙었다 — 순위용 혼합값을 화면에 나가는 생 유사도와 분리한다.

- [x] **`app/services/research/state.py`**

```python
# app/services/research/state.py
"""state.py — 딥리서치 실행 상태

각 단계는 ResearchState 를 받아 갱신해 돌려준다. Celery·Redis·Milvus 없이
테스트되고, 나중에 다른 오케스트레이션 런타임으로 옮겨도 그대로 쓴다.
"""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import NotRequired, TypedDict

# 깊이 파라미터 — research_jobs.params 로 덮어쓴다.
# 시연 직전에 값만 바꿔 짧게 돌릴 수 있어야 하므로 하드코딩하지 않는다.
# MappingProxyType 로 감싼 이유: 워커 프로세스가 이 모듈 전역을 한 번이라도
# 실수로 mutate 하면 그 오염이 프로세스 수명 내내 남는다.
DEFAULT_PARAMS: MappingProxyType[str, int | float] = MappingProxyType({
    "max_subquestions": 6,
    "max_recheck": 3,
    "max_evidence": 60,
    "per_subq_top_k": 12,
    "chunks_per_evidence": 2,
    "citation_weight": 0.2,
    "min_evidence_per_subq": 5,
})

# (타입, 하한, 상한). ResearchCreate.params: dict 가 값 타입을 검증하지
# 않으므로 여기가 유일한 검증 지점이다 — 상한이 없으면 per_subq_top_k 같은
# 값이 그대로 Milvus AnnSearchRequest(limit=...) 까지 흘러가 요청 하나로
# 워커를 묶는 자해 경로가 된다. 상한은 시연 현실치 기준.
_PARAM_BOUNDS: dict[str, tuple[type, int | float, int | float | None]] = {
    "max_subquestions": (int, 1, 12),
    "max_recheck": (int, 0, 10),
    "max_evidence": (int, 1, 200),
    "per_subq_top_k": (int, 1, 50),
    "chunks_per_evidence": (int, 1, 5),
    "citation_weight": (float, 0.0, 1.0),
    "min_evidence_per_subq": (int, 0, 50),
}


def merge_params(override: dict | None) -> dict:
    """기본값에 override 를 얹는다. 모르는 키·타입·범위를 벗어난 값은 거부한다."""
    merged = dict(DEFAULT_PARAMS)
    for key, value in (override or {}).items():
        if key not in DEFAULT_PARAMS:
            raise ValueError(f"알 수 없는 파라미터: {key}")
        _validate_param(key, value)
        merged[key] = value
    return merged


def _validate_param(key: str, value: object) -> None:
    expected_type, lo, hi = _PARAM_BOUNDS[key]
    # bool 은 int 의 서브클래스라 isinstance(value, int) 를 그냥 쓰면 True 가 통과해버린다.
    if isinstance(value, bool):
        raise ValueError(f"파라미터 {key} 에 bool 값은 쓸 수 없다: {value!r}")
    if expected_type is int and not isinstance(value, int):
        raise ValueError(f"파라미터 {key} 는 int 여야 한다: {value!r}")
    if expected_type is float and not isinstance(value, (int, float)):
        raise ValueError(f"파라미터 {key} 는 float 여야 한다: {value!r}")
    if value < lo or (hi is not None and value > hi):
        raise ValueError(f"파라미터 {key} 가 허용 범위({lo}~{hi})를 벗어났다: {value!r}")


class HitRow(TypedDict):
    """검색 결과 1건 — Milvus 검색 계층(explore)이 만들어 citations.build_evidence 로 넘긴다.

    score 와 rank_score 를 나눈 이유: 순위용 혼합값은 1.0 을 넘을 수 있어
    유사도로 표시하면 141% 같은 값이 나간다. score 는 생값 그대로 두고 순위는
    rank_score 로만 매긴다(explorer.rank_hits).
    """
    book_id: str
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float                      # 리랭킹(없으면 RRF) 생값 — 화면에 유사도로 나간다
    rank_score: NotRequired[float]    # 피인용을 얹은 정렬용 값 — rank_hits 가 채운다


@dataclass
class Chunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float


@dataclass
class Evidence:
    id: str                      # "E12" — 보고서 안에서만 유효한 지역 ID
    cnts_id: str
    meta: dict                   # 제목·저자·학술지·권호·연월·피인용·등재구분
    chunks: list[Chunk] = field(default_factory=list)


VERDICTS = ("pending", "sufficient", "insufficient")


@dataclass
class SubQuestion:
    idx: int
    text: str
    queries: list[str] = field(default_factory=list)   # 시도한 검색어 (재검색 이력)
    evidence_ids: list[str] = field(default_factory=list)
    verdict: str = "pending"
    note: str = ""                                      # 자기점검 판단 근거


@dataclass
class ResearchState:
    job_id: str
    question: str
    params: dict
    subquestions: list[SubQuestion] = field(default_factory=list)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    recheck_count: int = 0
    # 실행 시점의 수록 범위 — 코퍼스가 계속 자라므로 보고서에 고정 문구로
    # 박지 않고 매번 질의해 넣는다. {"from": "2002", "to": "2026", "n_papers": 72054}
    corpus_range: dict | None = None
    report: dict | None = None
```

- [x] **`app/tests/test_research_state.py`**

```python
# app/tests/test_research_state.py
import pytest

from services.research.state import (
    DEFAULT_PARAMS, VERDICTS, Chunk, Evidence, ResearchState, SubQuestion, merge_params,
)


class TestMergeParams:
    def test_empty_override_gives_defaults(self):
        assert merge_params({}) == DEFAULT_PARAMS

    def test_none_override_gives_defaults(self):
        assert merge_params(None) == DEFAULT_PARAMS

    def test_override_wins(self):
        assert merge_params({"max_recheck": 1})["max_recheck"] == 1

    def test_override_does_not_drop_other_keys(self):
        merged = merge_params({"max_recheck": 1})
        assert merged["max_subquestions"] == DEFAULT_PARAMS["max_subquestions"]

    def test_unknown_key_is_rejected(self):
        # 오타로 조용히 무시되는 파라미터가 생기면 시연 직전에 값을 바꿔도 안 먹는다
        with pytest.raises(ValueError, match="알 수 없는 파라미터"):
            merge_params({"max_rechecks": 1})

    def test_defaults_are_not_mutated(self):
        merge_params({"max_recheck": 9})
        assert DEFAULT_PARAMS["max_recheck"] == 3

    def test_default_params_key_set_is_fixed(self):
        # Task 7·9 가 params["per_subq_top_k"] 로 직접 인덱싱한다 — 이름이
        # 바뀌면 merge_params 가 옛 이름을 거부하는 쪽으로 실패해야 한다.
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
        }

    def test_negative_citation_weight_is_rejected(self):
        with pytest.raises(ValueError, match="citation_weight"):
            merge_params({"citation_weight": -0.2})

    def test_citation_weight_above_one_is_rejected(self):
        with pytest.raises(ValueError, match="citation_weight"):
            merge_params({"citation_weight": 1.5})

    def test_citation_weight_bounds_are_inclusive(self):
        assert merge_params({"citation_weight": 0.0})["citation_weight"] == 0.0
        assert merge_params({"citation_weight": 1.0})["citation_weight"] == 1.0

    def test_string_value_for_int_param_is_rejected(self):
        # JSON 본문에서 흔한 실수 — 그대로 두면 should_recheck 의 비교에서 TypeError 로 터진다
        with pytest.raises(ValueError, match="max_recheck"):
            merge_params({"max_recheck": "3"})

    def test_bool_value_for_int_param_is_rejected(self):
        # bool 은 int 의 서브클래스라 isinstance(True, int) 가 True 다
        with pytest.raises(ValueError, match="max_recheck"):
            merge_params({"max_recheck": True})

    def test_bool_value_for_float_param_is_rejected(self):
        with pytest.raises(ValueError, match="citation_weight"):
            merge_params({"citation_weight": True})

    def test_zero_chunks_per_evidence_is_rejected(self):
        # 0 이면 청크 없는 근거가 만들어져 인용칩 호버가 빈 상태가 된다
        with pytest.raises(ValueError, match="chunks_per_evidence"):
            merge_params({"chunks_per_evidence": 0})

    def test_negative_max_recheck_is_rejected(self):
        with pytest.raises(ValueError, match="max_recheck"):
            merge_params({"max_recheck": -1})

    def test_per_subq_top_k_upper_bound_is_rejected(self):
        # 상한 없이 그대로 두면 Milvus AnnSearchRequest(limit=...) 까지 흘러가
        # 요청 하나로 워커를 묶는 자해 경로가 된다
        with pytest.raises(ValueError, match="per_subq_top_k"):
            merge_params({"per_subq_top_k": 1_000_000})


class TestState:
    def test_new_state_has_no_subquestions(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.subquestions == []
        assert st.evidence == {}
        assert st.recheck_count == 0

    def test_subquestion_defaults_to_pending(self):
        sq = SubQuestion(idx=0, text="하위질문")
        assert sq.verdict == "pending"
        assert sq.verdict in VERDICTS
        assert sq.queries == []
        assert sq.evidence_ids == []

    def test_evidence_holds_chunks(self):
        ev = Evidence(
            id="E1", cnts_id="KCI_FI000000001", meta={"title": "제목"},
            chunks=[Chunk(chunk_id="c1", text="본문", page_start=3, page_end=3, score=0.9)],
        )
        assert ev.chunks[0].page_start == 3

    def test_corpus_range_defaults_to_none(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.corpus_range is None
```

- [x] **검증** — `20 passed`, 전체 회귀 202 passed

---

## Task 3: 피인용 연차 정규화와 점수 혼합 — **완료**

> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 최종 상태**이며 저장소의 실제 파일과 일치한다. 동기화(`0971f21`) 뒤로 `scoring.py` 는 바뀌지 않았다(2026-09-23 확인).

피인용을 생값으로 쓰면 오래된 논문이 항상 이긴다. 2002년 논문은 25년간 쌓았고 2024년 논문은 3년이다. 연간 피인용으로 정규화해야 "최근 동향" 질문에서 2000년대 초 논문만 올라오지 않는다. 화면에는 생값을 그대로 보여주고 정규화는 순위에만 쓴다.

- [x] **`app/services/research/scoring.py`**

```python
# app/services/research/scoring.py
"""scoring.py — 근거 순위 계산 (순수 함수)

피인용을 생값으로 쓰면 오래된 논문이 항상 이긴다. now_year 기준 2002년
논문은 25년간(+1, 발행연도 포함) 쌓았고 2024년 논문은 3년이다. 연간
피인용으로 정규화해야 "최근 동향" 질문에서 2000년대 초 논문만 올라오지
않는다.

화면에는 생값(피인용 41회)을 그대로 보여준다 — 정규화는 순위에만 쓴다.
"""
import math
import re

_YEAR = re.compile(r"(19|20)\d{2}")


def parse_pub_year(pub_date: str | None) -> int | None:
    """'2008-06' · '200806' · '2008' → 2008. 해석 불가면 None."""
    m = _YEAR.search(pub_date or "")
    return int(m.group(0)) if m else None


def impact_per_year(kci_citations: int | None, pub_year: int | None, *, now_year: int) -> float:
    """연간 피인용. 연도를 모르거나 피인용이 없으면 0."""
    if kci_citations is None or kci_citations <= 0 or pub_year is None:
        return 0.0
    years = max(1, now_year - pub_year + 1)
    return kci_citations / years


def blend_score(rerank_score: float, *, impact: float, weight: float) -> float:
    """리랭킹 점수를 주로 하고 영향력을 보조 가중으로 얹는다.

    log1p 로 감쇠시키는 이유: 영향력이 100배여도 점수가 100배가 되면
    의미 유사도가 의미를 잃고 "많이 인용된 논문 목록"이 되어버린다.
    """
    return rerank_score * (1.0 + weight * math.log1p(impact))
```

- [x] **`app/tests/test_research_scoring.py`**

```python
# app/tests/test_research_scoring.py
import pytest

from services.research.scoring import blend_score, impact_per_year, parse_pub_year


class TestParsePubYear:
    @pytest.mark.parametrize("raw,expected", [
        ("2008-06", 2008),
        ("2008", 2008),
        ("200806", 2008),
        ("", None),
        (None, None),
        ("연도미상", None),
    ])
    def test_parse(self, raw, expected):
        assert parse_pub_year(raw) == expected


class TestImpactPerYear:
    def test_zero_citations(self):
        assert impact_per_year(0, 2008, now_year=2026) == 0.0

    def test_missing_year_gives_zero(self):
        assert impact_per_year(50, None, now_year=2026) == 0.0

    def test_null_citations_gives_zero(self):
        """kci_citations 는 nullable 이다(server_default 없음, BookOut 도 Optional).
        None 검사가 비교 뒤로 밀리면 여기서 TypeError 가 난다."""
        assert impact_per_year(None, 2008, now_year=2026) == 0.0

    def test_same_year_does_not_divide_by_zero(self):
        assert impact_per_year(4, 2026, now_year=2026) == 4.0

    def test_normalization_flips_raw_order(self):
        """생피인용은 2002년 논문이 크지만 연간으로는 2024년 논문이 크다."""
        old = impact_per_year(50, 2002, now_year=2026)    # 50 / 25 = 2.0
        new = impact_per_year(40, 2024, now_year=2026)    # 40 / 3  = 13.3
        assert new > old

    def test_future_year_is_clamped(self):
        assert impact_per_year(10, 2030, now_year=2026) == 10.0


class TestBlendScore:
    def test_zero_weight_leaves_rerank_untouched(self):
        assert blend_score(0.8, impact=13.3, weight=0.0) == pytest.approx(0.8)

    def test_impact_raises_score(self):
        assert blend_score(0.8, impact=13.3, weight=0.2) > 0.8

    def test_zero_impact_leaves_score_untouched(self):
        assert blend_score(0.8, impact=0.0, weight=0.2) == pytest.approx(0.8)

    def test_growth_is_damped(self):
        """영향력 10배가 점수 10배가 되면 안 된다 — 의미 유사도가 주여야 한다."""
        low = blend_score(0.8, impact=1.0, weight=0.2)
        high = blend_score(0.8, impact=100.0, weight=0.2)
        assert high < low * 5
```

- [x] **검증** — `16 passed`(Task 7 리뷰에서 `kci_citations=None` 케이스 1건 추가), 작성 시점 전체 회귀 202 passed. 되돌림 확인: `impact_per_year` 의 가드를 `if pub_year is None or kci_citations <= 0 or kci_citations is None:` 으로 바꾸면 `test_null_citations_gives_zero` 가 `TypeError` 로 떨어진다.

---

## Task 4: 근거 조립과 마커 검증 — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - `b6360b8` — `strip_markers` 추가. 모델이 대표 논문 요약에 시키지 않은 `[E#]` 를 달았고, 요약은 `bind_markers` 를 거치지 않아 지어낸 번호가 검증 없이 나갈 수 있었다.
> - 머지 전 리뷰 — 마커를 괄호 단위로 해석한다(묶음 `[E1, E2]`·범위·전각 괄호·소문자·0패딩). 단일형 정규식만 보면 `[E2, E99]` 속 없는 번호가 검증도 제거도 안 된 채 실렸다. 읽을 수 없는 인용 표기는 `MarkerResult.unparsed` 로 따로 센다. 재사용 근거의 하위질문별 청크를 다루는 `chunks_for`·`link_chunks` 추가. 청크 점수도 하위질문별이다(`SubQuestion.chunk_scores`) — 한 청크를 두 하위질문이 매칭하면 `Chunk.score` 하나로는 뒤 하위질문의 재검색이 앞 하위질문의 점수로 비교해 더 나은 대목을 밀어냈다. `chunks_for` 는 그 하위질문 점수를 담은 사본을 준다.
>
> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 동기화 시점(`3c138c6`)의 상태**이며 그때 저장소 파일과 일치했다.

이 계층에서 가장 중요하다. 근거 표기가 틀린 리서치 도구는 안 쓰느니만 못하다. 모델이 없는 `[E99]` 를 뱉었을 때 칩이 만들어지지 않는 것이 인용 무결성의 마지막 방어선이다.

리뷰 반영으로 초안과 달라진 것 셋. (1) **근거 ID 번호 권한을 runner 로 넘겼다** — `build_evidence` 는 묶기만 하고 `id=""` 인 `list[Evidence]` 를 hits 등장 순서로 돌려준다. 초안은 `start_index` 로 번호를 붙였는데 runner 가 그걸 버리고 다시 붙여, 테스트가 버려지는 쪽만 덮고 있었다. (2) **공백 정리를 마커 주변으로 한정했다** — 전역 치환이 `"p < .05"` 같은 논문 통계 표기를 `"p <.05"` 로 훼손했다. (3) **`bind_markers` 가 `used` 를 함께 돌려준다** — 안 그러면 synthesizer 가 마커 정규식을 세 번째로 복제한다.

- [x] **`app/services/research/citations.py`**

```python
# app/services/research/citations.py
"""citations.py — 근거 조립과 인용 마커 검증 (순수 함수)

인용은 두 종류다.

구조적 인용 — `대표 논문 요약`은 불릿 하나가 논문 하나라, 그 논문의 근거만
넣고 생성하면 인용이 추론이 아니라 구조로 정해진다. 모델이 고를 일이 없다.

마커 인용 — `도입 문단`·`향후 과제`는 여러 논문을 가로지르므로 구조로 못
정한다. 모델이 [E3] 로 달게 하고 여기서 전수 검증한다. 해석 안 되는 마커는
조용히 통과시키지 않고 제거한 뒤 개수를 보고한다.

근거 ID(E1·E2·...) 는 runner 가 state.evidence 에 넣는 시점에 붙인다 —
evidence 네임스페이스를 소유한 쪽이 번호도 소유해야 한다. build_evidence
는 순서만 보장하고(hits 등장 순서) 번호는 매기지 않는다.
"""
import re
from typing import NamedTuple

from services.research.state import Chunk, Evidence, HitRow

_MARKER = re.compile(r"[ \t]*\[(E\d+)\]")
_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+")
# 마침표 뒤에 붙는 마커 묶음("문장이다. [E1] [E2]")을 셀 때만 통째로 문장
# 앞으로 당긴다 — LLM 이 마커를 문장 끝 마침표 뒤에 다는 게 흔해서, 그대로
# 세면 근거가 있는 문장이 무근거로 오분류된다. 마커 하나만 당기면 뒤에
# 남은 마커가 다음 문장 소속으로 잘못 잡혀 과소 계수된다. 계수용 사본에만
# 쓰므로 치환 뒤 공백이 지저분해도 무해하다. 반환 텍스트에는 적용하지 않는다.
_TRAILING_MARKER = re.compile(r"([.!?。])(\s+)((?:\[E\d+\][ \t]*)+)")


def evidence_id(index: int) -> str:
    return f"E{index + 1}"


def build_evidence(
    hits: list[HitRow],
    meta_by_id: dict[str, dict],
    *,
    chunks_per_evidence: int,
) -> list[Evidence]:
    """검색 결과를 논문 단위 근거로 묶는다.

    같은 논문의 청크 여러 개는 근거 하나가 되고, 점수 높은 순으로
    chunks_per_evidence 개만 남긴다(호버 팝업의 1/2 페이지네이션).
    카탈로그에 메타가 없는 청크는 버린다 — 서지를 못 보여주면 근거가 아니다.

    반환 순서는 hits 안에서 각 논문이 처음 등장한 순서다(hits 는 호출 전에
    점수 내림차순으로 정렬돼 들어온다는 전제). id 는 비워둔다 — runner 가
    state.evidence 에 넣으며 evidence_id() 로 채운다.
    """
    grouped: dict[str, list[HitRow]] = {}
    for hit in hits:
        cnts_id = hit["book_id"]
        if cnts_id not in meta_by_id:
            continue
        grouped.setdefault(cnts_id, []).append(hit)

    result: list[Evidence] = []
    for cnts_id, rows in grouped.items():
        rows.sort(key=lambda r: r["score"], reverse=True)
        result.append(Evidence(
            id="",
            cnts_id=cnts_id,
            meta=meta_by_id[cnts_id],
            chunks=[
                Chunk(
                    chunk_id=r["chunk_id"], text=r["text"],
                    page_start=r["page_start"], page_end=r["page_end"],
                    score=r["score"],
                )
                for r in rows[:chunks_per_evidence]
            ],
        ))
    return result


class MarkerResult(NamedTuple):
    text: str
    dropped: list[str]
    used: list[str]      # 등장 순서, 중복 제거 — 유효한 마커를 다시 정규식으로 훑지 않고 여기서 재사용한다
    unmarked: int


def bind_markers(text: str, valid_ids: set[str]) -> MarkerResult:
    """인용 마커를 검증한다.

    반환 본문은 유효하지 않은 마커(와 그 앞 공백)만 제거하고 나머지는
    바이트 단위로 보존한다 — "p < .05" 같은 논문 통계 표기를 건드리지 않는다.
    """
    dropped: list[str] = []
    used: list[str] = []

    def _check(m: re.Match) -> str:
        marker_id = m.group(1)
        if marker_id in valid_ids:
            if marker_id not in used:
                used.append(marker_id)
            return m.group(0)
        dropped.append(marker_id)
        return ""

    cleaned = _MARKER.sub(_check, text).strip()

    count_text = _TRAILING_MARKER.sub(r"\3\1\2", cleaned)
    sentences = [s for s in _SENT_SPLIT.split(count_text) if s.strip()]
    unmarked = sum(1 for s in sentences if not _MARKER.search(s))

    return MarkerResult(cleaned, dropped, used, unmarked)
```

- [x] **`app/tests/test_research_citations.py`**

```python
# app/tests/test_research_citations.py
from services.research.citations import MarkerResult, bind_markers, build_evidence, evidence_id


class TestEvidenceId:
    def test_format(self):
        assert evidence_id(0) == "E1"
        assert evidence_id(11) == "E12"


class TestBuildEvidence:
    def _hit(self, cnts_id, chunk_id, score, page=1):
        return {
            "book_id": cnts_id, "chunk_id": chunk_id, "text": f"본문 {chunk_id}",
            "page_start": page, "page_end": page, "score": score,
        }

    def _meta(self, *cnts_ids):
        return {cnts_id: {"title": f"제목 {cnts_id}", "kci_citations": 3} for cnts_id in cnts_ids}

    def test_one_paper_one_evidence(self):
        ev = build_evidence([self._hit("A", "c1", 0.9)], self._meta("A"), chunks_per_evidence=2)
        assert len(ev) == 1
        assert ev[0].cnts_id == "A"
        assert ev[0].id == ""  # 번호는 runner 가 붙인다 — 여기서는 미할당

    def test_chunks_of_same_paper_group_into_one_evidence(self):
        ev = build_evidence(
            [self._hit("A", "c1", 0.9), self._hit("A", "c2", 0.7)],
            self._meta("A"), chunks_per_evidence=2,
        )
        assert len(ev) == 1
        assert len(ev[0].chunks) == 2

    def test_chunks_per_evidence_caps_and_keeps_best(self):
        ev = build_evidence(
            [self._hit("A", "c1", 0.5), self._hit("A", "c2", 0.9),
             self._hit("A", "c3", 0.7)],
            self._meta("A"), chunks_per_evidence=2,
        )
        assert [c.chunk_id for c in ev[0].chunks] == ["c2", "c3"]

    def test_hit_without_metadata_is_dropped(self):
        """카탈로그에 없는 청크는 근거로 쓰지 않는다 — 서지를 못 보여준다."""
        ev = build_evidence([self._hit("GHOST", "c1", 0.9)], {}, chunks_per_evidence=2)
        assert ev == []

    def test_return_order_follows_hit_appearance_order(self):
        """점수가 아니라 hits 등장 순서를 따른다 — sorted() 가 몰래 끼어들면 이 테스트가 잡는다."""
        ev = build_evidence(
            [self._hit("B", "c1", 0.5), self._hit("A", "c2", 0.9)],
            self._meta("A", "B"), chunks_per_evidence=2,
        )
        assert [e.cnts_id for e in ev] == ["B", "A"]

    def test_empty_hits_gives_empty_list(self):
        assert build_evidence([], {}, chunks_per_evidence=2) == []

    def test_chunks_per_evidence_zero_gives_no_chunks(self):
        ev = build_evidence([self._hit("A", "c1", 0.9)], self._meta("A"), chunks_per_evidence=0)
        assert ev[0].chunks == []


class TestBindMarkers:
    def test_valid_marker_is_kept(self):
        res = bind_markers("근거가 있다 [E1].", {"E1"})
        assert "[E1]" in res.text
        assert res.dropped == []

    def test_unknown_marker_is_dropped(self):
        """모델이 없는 근거를 지어내면 칩을 만들지 않는다."""
        res = bind_markers("근거가 있다 [E99].", {"E1"})
        assert "[E99]" not in res.text
        assert res.dropped == ["E99"]

    def test_dropping_does_not_leave_double_space(self):
        res = bind_markers("앞 [E99] 뒤.", {"E1"})
        assert "  " not in res.text

    def test_sentence_without_marker_is_counted(self):
        res = bind_markers("근거 있다 [E1]. 근거 없다.", {"E1"})
        assert res.unmarked == 1

    def test_sentence_whose_only_marker_was_dropped_counts_as_unmarked(self):
        res = bind_markers("지어낸 근거다 [E99].", {"E1"})
        assert res.dropped == ["E99"]
        assert res.unmarked == 1

    def test_empty_text(self):
        assert bind_markers("", {"E1"}) == MarkerResult("", [], [], 0)

    def test_used_ids_are_reported_in_order(self):
        res = bind_markers("가 [E2]. 나 [E1].", {"E1", "E2"})
        assert res.used == ["E2", "E1"]
        assert res.dropped == []
        assert res.unmarked == 0

    def test_trailing_marker_after_period_attributes_to_next_sentence(self):
        """정규화가 없어도 총합(unmarked)은 1로 같다 — 어느 문장이 무근거로
        지목되는지만 바뀐다. 정규화 유무를 가르는 회귀 테스트가 아니다.
        (그 검증은 test_trailing_marker_at_end_of_text_counts_as_marked 가 한다.)
        """
        res = bind_markers("근거 있다. [E1] 다른 말이다.", {"E1"})
        assert res.unmarked == 1  # "다른 말이다." 만 무근거

    def test_trailing_marker_at_end_of_text_counts_as_marked(self):
        """정규화 유무로 실제 값이 갈리는 케이스 — 뒤 문장이 없어 마커를
        당기지 않으면 "근거 있다." 자체가 무근거로 잘못 잡힌다."""
        res = bind_markers("근거 있다. [E1]", {"E1"})
        assert res.unmarked == 0

    def test_consecutive_trailing_markers_all_attribute_to_previous_sentence(self):
        """마커가 여럿 쌓여 있으면(". [E1] [E2]") 전부 앞 문장 근거로 봐야
        한다 — 하나만 당기면 뒤 마커가 다음 문장 소속으로 잘못 잡혀 과소
        계수된다."""
        res = bind_markers("문장이다. [E1] [E2] 다음 문장이다.", {"E1", "E2"})
        assert res.unmarked == 1  # "다음 문장이다." 만 무근거

    def test_trailing_marker_normalization_does_not_change_returned_text(self):
        res = bind_markers("근거 있다. [E1] 다른 말이다.", {"E1"})
        assert res.text == "근거 있다. [E1] 다른 말이다."

    def test_statistic_notation_is_preserved(self):
        """p < .05 같은 사회과학 논문의 선행 0 생략 표기를 훼손하면 안 된다."""
        res = bind_markers("유의수준 p < .05 였다 [E1].", {"E1"})
        assert "p < .05" in res.text

    def test_newline_is_preserved(self):
        res = bind_markers("첫 줄 [E1].\n둘째 줄.", {"E1"})
        assert "\n" in res.text
```

- [x] **검증** — `21 passed`, 전체 회귀 202 passed

---

## Task 5: 계획 수립 (파싱 + 프롬프트) — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - 머지 전 리뷰 — 중복 판정 키를 `planner.query_key` 로 뺐다. 승인 때 사용자가 고친 계획의 중복 검사(API)와 재검색어 중복 제거(runner)가 같은 규칙("AI 윤리" = "ai  윤리")을 쓴다.
>
> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 동기화 시점(`38e6ed1`)의 상태**이며 그때 저장소 파일과 일치했다.

계획 파싱이 이 라운드에서 가장 잘 깨지는 자리다. 실패하면 `ValueError` 가 그대로 올라가 job 이 죽는데, 원인은 모델이 마크다운을 조금 다르게 쓴 것뿐이다.

리뷰 반영으로 초안과 달라진 것 셋.

**(1) 강조를 항목 매칭보다 먼저 벗긴다.** 초안은 `_ITEM` 으로 먼저 매칭하고 그 다음에 강조를 지웠다. 모델이 `**1. 청소년 진로상담**` 처럼 항목 전체를 굵게 쓰면 앞의 `*` 가 불릿으로 먹혀 `1. 청소년…**` 이 남거나 매칭 자체가 깨진다. 모든 줄이 탈락하면 `parse_plan` 이 `ValueError` 를 던지고 계획 수립이 통째로 실패한다 — 전부 아니면 전무인 실패다.

**(2) 줄 전체 강조와 내용 안 강조를 나눠 처리한다.** `_unwrap_line` 하나로 합치면 `* **가**` 에서 불릿 `*` 가 뒤쪽 강조 `*` 와 짝지어져 내용이 사라진다. 여는 표식 뒤가 공백이 아닐 것(`(?=\S)`)을 요구하면 불릿과 강조가 갈린다 — 불릿 뒤에는 공백이 오기 때문이다.

**(3) 전역 문자 제거를 쌍 매칭으로 바꿨다.** 초안의 `_EMPH.sub("", ...)` 는 별표·밑줄·역따옴표를 위치와 무관하게 전부 지워, `TF_IDF 가중치` 를 `TFIDF 가중치` 로 훼손한다. 논문 검색어에 밑줄이 들어간 식별자가 실제로 온다.

중복 제거 키도 원문 그대로가 아니라 `공백 접기 + casefold` 로 바꿨다. `AI 윤리` 와 `ai 윤리` 는 같은 검색을 두 번 돌린다.

- [x] **`app/services/research/planner.py`**

```python
"""planner.py — 질문을 하위질문으로 분해

파싱을 LLM 호출에서 분리한 이유: 모델이 번호 매김을 흐트러뜨리는 것은
흔한 일이고, 그 처리를 네트워크 없이 테스트할 수 있어야 한다.
"""
import logging
import re

from services.llm_client import chat
from services.prompts import get_prompt

log = logging.getLogger(__name__)

_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.+?)\s*$")
# 줄 전체를 감싼 강조. 여는 표식 뒤가 공백이 아닐 것을 요구해야 불릿과 구분된다 —
# "* **가**" 의 앞 "*" 는 불릿이지 강조가 아니다.
_WRAP = re.compile(r"^\s*(\*\*|__|\*|_)(?=\S)(.*?)\1\s*$", re.S)
# 쌍으로 감싼 강조만 벗긴다. 전역으로 [*_`] 를 지우면 TF_IDF → TFIDF 처럼
# 본문 중간 문자까지 훼손된다.
_PAIRED_EMPH = re.compile(r"(\*\*|__|\*|_|`)(?=\S)(.+?)\1")
_WS = re.compile(r"\s+")


def _unwrap_line(line: str) -> str:
    """`**1. 가**` 처럼 항목 전체를 감싼 강조를 벗긴다.

    이걸 항목 매칭보다 먼저 해야 한다. 안 그러면 앞의 `*` 가 불릿으로 먹혀
    매칭이 깨지고, 모든 줄이 탈락해 계획 수립이 통째로 실패한다.
    """
    m = _WRAP.match(line)
    return m.group(2) if m else line


def _strip_emphasis(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = _PAIRED_EMPH.sub(r"\2", text)
    return text


def parse_plan(raw: str, *, limit: int) -> list[str]:
    """번호/불릿 목록에서 하위질문을 뽑는다. 중복·공백 제거, limit 개까지.

    강조를 항목 매칭보다 먼저 벗기는 이유: 모델이 `**1. 주제**` 처럼 항목
    전체를 굵게 쓰면 앞의 `*` 가 불릿으로 먹혀 매칭이 깨진다. 그러면 모든
    줄이 탈락해 계획 수립이 통째로 실패하고 job 이 죽는다.
    """
    items: list[str] = []
    seen: set[str] = set()
    for line in (raw or "").splitlines():
        m = _ITEM.match(_unwrap_line(line))
        if not m:
            if line.strip():
                log.debug("[planner] 항목으로 해석되지 않은 줄 — %r", line.strip()[:80])
            continue
        text = _strip_emphasis(m.group(1)).strip()
        key = _WS.sub(" ", text).casefold()
        if text and key not in seen:
            seen.add(key)
            items.append(text)
    if not items:
        raise ValueError(f"계획을 해석하지 못했다: {(raw or '')[:120]!r}")
    return items[:limit]


async def make_plan(question: str, *, params: dict) -> list[str]:
    limit = params["max_subquestions"]
    system, user, llm_params = get_prompt("research_plan").render(
        question=question, limit=limit,
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params,
    )
    return parse_plan(raw, limit=limit)
```

- [x] **`app/domains/nl_library/prompts/research_plan.yaml`**

```yaml
parser: plain
params:
  max_tokens: 800
  temperature: 0.3
system: |-
  당신은 국내 학술논문 코퍼스를 다루는 연구 사서입니다.
  사용자의 질문을 검색 가능한 하위질문으로 분해합니다.

  규칙:
  - 하위질문은 최대 {{ limit }}개입니다.
  - 각 하위질문은 그 자체로 논문 검색어가 될 만큼 구체적이어야 합니다.
  - 서로 겹치지 않게 나눕니다.
  - 번호 목록으로만 출력합니다. 서론·설명·맺음말을 쓰지 마세요.
  - 한국어로 씁니다.
user: |-
  질문: {{ question }}
```

- [x] **`app/tests/test_research_planner.py`**

```python
import pytest

from services.research.planner import parse_plan


class TestParsePlan:
    def test_numbered_list(self):
        raw = "1. 첫째 주제\n2. 둘째 주제\n3. 셋째 주제"
        assert parse_plan(raw, limit=6) == ["첫째 주제", "둘째 주제", "셋째 주제"]

    def test_paren_numbering(self):
        assert parse_plan("1) 가\n2) 나", limit=6) == ["가", "나"]

    def test_bullet_list(self):
        assert parse_plan("- 가\n- 나", limit=6) == ["가", "나"]

    def test_preamble_is_dropped(self):
        raw = "다음과 같이 제안합니다.\n\n1. 가\n2. 나"
        assert parse_plan(raw, limit=6) == ["가", "나"]

    def test_limit_truncates(self):
        raw = "\n".join(f"{i}. 주제{i}" for i in range(1, 10))
        assert len(parse_plan(raw, limit=6)) == 6

    def test_blank_and_duplicate_removed(self):
        raw = "1. 가\n2.  \n3. 가\n4. 나"
        assert parse_plan(raw, limit=6) == ["가", "나"]

    def test_markdown_emphasis_stripped(self):
        assert parse_plan("1. **가** 주제", limit=6) == ["가 주제"]

    def test_fully_bolded_item_is_parsed(self):
        """모델이 항목 전체를 굵게 쓰면 앞의 * 가 불릿으로 먹혀 매칭이 깨진다.

        그러면 모든 줄이 탈락해 계획 수립이 통째로 실패하고 job 이 죽는다.
        강조를 항목 매칭보다 먼저 벗겨야 한다.
        """
        assert parse_plan("**1. 가**\n**2. 나**", limit=6) == ["가", "나"]

    def test_bolded_bullet_item_is_parsed(self):
        assert parse_plan("* **가**\n* **나**", limit=6) == ["가", "나"]

    def test_underscore_inside_word_is_preserved(self):
        """전역으로 [*_`] 를 지우면 TF_IDF → TFIDF 로 훼손된다."""
        assert parse_plan("1. TF_IDF 가중치 연구", limit=6) == ["TF_IDF 가중치 연구"]

    def test_duplicate_differing_only_in_whitespace_is_dropped(self):
        assert parse_plan("1. 가 주제\n2. 가  주제", limit=6) == ["가 주제"]

    def test_duplicate_differing_only_in_case_is_dropped(self):
        assert parse_plan("1. AI 윤리\n2. ai 윤리", limit=6) == ["AI 윤리"]

    def test_no_list_raises(self):
        with pytest.raises(ValueError, match="계획을 해석하지 못했다"):
            parse_plan("죄송하지만 답변할 수 없습니다.", limit=6)
```

- [x] **검증** — `13 passed`. 되돌림 확인: `_unwrap_line` 을 빼면 `parse_plan("**1. 가**", limit=6)` 이 `ValueError` 로 떨어진다.

---

## Task 6: 자기점검 — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - 머지 전 리뷰 — 판정 LLM 호출의 전송 오류(`httpx.HTTPError`: 타임아웃·5xx)도 파싱 실패와 같은 "판정 불가"(`parse_failed`)로 낮춘다. 올려 보내면 워커가 하위질문 전체를 `failed` 로 두어 이미 모은 근거가 절에서 빠졌다. 발췌는 runner 가 그 하위질문 몫 청크로 추려 넘긴다(`citations.chunks_for`).
>
> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 동기화 시점(`38e6ed1`)의 상태**이며 그때 저장소 파일과 일치했다.

자기점검은 꺼져도 티가 안 나는 기능이다. 판정을 못 읽으면 `sufficient` 로 떨어지는데(무한 재검색을 막으려면 그래야 한다), 그러면 "모델이 충분하다고 판단한 것"과 구분되지 않는다. 자기점검이 전부 실패해도 보고서는 "한계 없음"으로 보인다.

리뷰 반영으로 초안과 달라진 것 넷.

**(1) `parse_failed` 를 따로 들고 간다.** 초안은 실패를 `note` 문자열(`"판정 해석 실패 — …"`)로만 표시했다. 그 `note` 는 그대로 탐색 경로·진행 패널에 실리므로 모델 원문이 사용자 화면에 샌다. 반대로 보고서의 한계 섹션은 `verdict == "insufficient"` 만 세므로 실패를 못 본다 — 노출이 정확히 뒤집혀 있었다. 이제 원문은 로그에만 남기고(`_failed`), `note` 는 중립적인 `"자동 점검을 완료하지 못했다"` 로 두고, 세는 것은 Task 8 이 `parse_failed` 로 한다.

**(2) `new_queries` 가 리스트인지 확인한다.** 모델이 `"new_queries": "진로상담 앱 효과"` 를 보내면 초안의 리스트 컴프리헨션이 문자열을 순회해 `["진","로","상","담", …]` 이 된다. 한 글자짜리 검색어로 재검색이 한 라운드 낭비된다.

**(3) 근거 목록에 본문 발췌를 붙이고 정규화한다.** 제목·연도만으로는 "이 논문이 하위질문을 실제로 다루는가"를 모델이 판단할 수 없어 판정이 사실상 편수 세기가 된다. 발췌를 붙이되 자르기 전에 `" ".join(text.split())` 로 공백을 접는다 — 표 청크는 `[표]\n…\n{table_md}` 로 저장되므로 그대로 쓰면 한 항목이 여러 줄로 퍼져 어느 발췌가 어느 논문 것인지 흐려진다. 목록은 `_MAX_LISTED = 20` 으로 끊는다: 재검색 라운드마다 근거가 누적되는데 상한이 없으면 프롬프트가 컨텍스트를 넘고, 앞쪽부터 잘려 system 의 JSON 출력 지시가 사라진다 — 그러면 산문이 와서 판정이 또 실패하는 악순환이 된다.

**(4) JSON 추출을 `services/research/llm_json.py` 로 뺐다.** 초안의 `body[body.index("{"): body.rindex("}")+1]` 는 JSON 뒤에 `}` 를 포함한 산문(`… 참고: {예시}`)이 붙으면 그 끝까지 먹어 파싱이 깨진다. `json.JSONDecoder().raw_decode()` 는 첫 유효 JSON 에서 멈춘다. **Task 8 synthesizer 도 같은 일을 하므로 반드시 이걸 재사용한다** — 마커 정규식을 두 곳에 두면 갈라지는 것과 같은 이유다.

`state.py` 의 `LLM_VERDICTS` 도 이때 들어왔다. `VERDICTS[1:]` 로 쓰면 `VERDICTS` 순서만 바뀌어도 `sufficient` 가 빠져 **모든 정상 판정이** "알 수 없는 verdict" 로 떨어진다.

- [x] **`app/services/research/llm_json.py`** (신규 — 초안에 없던 파일)

```python
"""llm_json.py — LLM 이 산문에 섞어 내보낸 JSON 을 꺼낸다

critic 과 synthesizer 가 같은 일을 하므로 한 곳에 둔다. 마커 정규식을
두 곳에 두면 갈라지는 것과 같은 이유다.

raw_decode 를 쓰는 이유: `body[index("{"):rindex("}")+1]` 는 JSON 뒤에
`}` 를 포함한 산문이 붙으면 그 끝까지 먹어 파싱이 깨진다. raw_decode 는
첫 유효 JSON 에서 멈춘다.
"""
import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def extract_json(raw: str) -> dict | None:
    """첫 유효 JSON 객체를 반환한다. 못 찾으면 None."""
    body = raw or ""
    m = _FENCE.search(body)
    if m:
        body = m.group(1)

    start = body.find("{")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(body[start:])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
```

- [x] **`app/services/research/critic.py`**

```python
"""critic.py — 근거 충분성 자기점검

판정 결과는 내부 제어에만 쓰지 않는다. note 가 그대로 보고서의
"한계와 미확인 영역" 섹션이 된다 — 모른다고 말하는 것이 이 기능의 값이다.

판정을 못 읽었을 때는 parse_failed 로 표시한다. 그냥 sufficient 로만 두면
"모델이 충분하다고 판단한 것"과 구분되지 않아, 자기점검이 전부 꺼져도
보고서가 "한계 없음"으로 보인다.
"""
import logging
from dataclasses import dataclass, field

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research.state import Evidence, LLM_VERDICTS, SubQuestion

log = logging.getLogger(__name__)

_EXCERPT_LEN = 200
# 근거 목록 길이 상한. 재검색 라운드마다 evidence_ids 가 누적되므로 상한이
# 없으면 프롬프트가 컨텍스트를 넘고, 앞쪽부터 잘려 system 의 JSON 출력
# 지시가 사라진다 — 그러면 산문 응답이 와서 판정이 또 실패한다.
_MAX_LISTED = 20
_PARSE_FAILED_NOTE = "자동 점검을 완료하지 못했다"


@dataclass
class Verdict:
    verdict: str
    note: str = ""
    new_queries: list[str] = field(default_factory=list)
    parse_failed: bool = False


def _failed(reason: str, raw: str) -> Verdict:
    """모델 원문은 로그에만 남긴다 — note 는 사용자 화면(탐색 경로)에 실린다."""
    log.warning("[critic] %s — raw=%r", reason, (raw or "")[:200])
    return Verdict("sufficient", note=_PARSE_FAILED_NOTE, parse_failed=True)


def parse_verdict(raw: str) -> Verdict:
    """판정 JSON 을 읽는다. 못 읽으면 sufficient 로 떨어뜨려 루프를 끝낸다.

    해석 실패를 insufficient 로 두면 파싱이 깨질 때마다 재검색이 상한까지
    돌아 시간을 태운다. 실패가 루프가 되면 안 된다.
    """
    data = extract_json(raw)
    if data is None:
        return _failed("판정 JSON 파싱 실패", raw)

    verdict = data.get("verdict")
    if verdict not in LLM_VERDICTS:
        return _failed(f"알 수 없는 verdict 값 {verdict!r}", raw)

    raw_queries = data.get("new_queries")
    if not isinstance(raw_queries, list):
        # 문자열이 오면 순회 시 글자 단위로 쪼개져 "진" 한 글자로 재검색한다
        raw_queries = []
    queries = [q for q in raw_queries if isinstance(q, str) and q.strip()]
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries)


def should_recheck(subq: SubQuestion, *, recheck_count: int, max_recheck: int) -> bool:
    return subq.verdict == "insufficient" and recheck_count < max_recheck


def format_evidence_list(evidence: list[Evidence]) -> str:
    """근거를 critic 프롬프트용 목록 문자열로 만든다.

    제목·연도만으로는 "이 논문이 하위질문을 실제로 다루는가"를 모델이
    판단하기 어렵다 — 그 하위질문 검색에서 실제로 매칭된 본문(chunks[0])의
    앞부분을 붙여 직접적인 근거로 준다. 청크가 없는 근거는 제목+연도만
    남긴다 — 인덱스 오류로 이 계층 전체가 죽으면 안 된다.

    발췌는 자르기 전에 공백을 접는다. 표 청크는 `[표]\\n…\\n{table_md}` 로
    저장되고 본문 청크도 단락 개행을 보존하므로, 그대로 쓰면 한 항목이
    여러 줄로 퍼져 어느 발췌가 어느 논문 것인지 흐려진다.
    """
    lines: list[str] = []
    for e in evidence[:_MAX_LISTED]:
        title = e.meta.get("title") or "(제목 없음)"
        year = e.meta.get("pub_date") or "연도미상"
        if not e.chunks:
            lines.append(f"- {title} ({year})")
            continue
        flat = " ".join(e.chunks[0].text.split())
        excerpt = flat[:_EXCERPT_LEN]
        if len(flat) > _EXCERPT_LEN:
            excerpt += "…"
        lines.append(f"- {title} ({year}) — {excerpt}")

    hidden = len(evidence) - _MAX_LISTED
    if hidden > 0:
        lines.append(f"- …외 {hidden}편")
    return "\n".join(lines) or "(없음)"


async def critique(
    subq: SubQuestion, evidence: list[Evidence], *, params: dict,
) -> Verdict:
    system, user, llm_params = get_prompt("research_critique").render(
        subquestion=subq.text,
        evidence_count=len(evidence),
        evidence_list=format_evidence_list(evidence),
        min_evidence=params["min_evidence_per_subq"],
        tried_queries=", ".join(subq.queries) or "(없음)",
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params,
    )
    return parse_verdict(raw)
```

- [x] **`app/domains/nl_library/prompts/research_critique.yaml`**

초안의 `{"verdict": …}` 한 줄 예시는 JSON 이 아니라 설명문이었다(`"sufficient" 또는 "insufficient"`). 이 코드베이스의 `curation.yaml` 관례대로 **유효한 JSON 골격 + 플레이스홀더**로 바꿨다. 그리고 편수 기준이 필요조건으로 읽히던 문장을 신호 중 하나로 낮췄다 — 코퍼스가 2002–2009 에 쏠려 있어 `min_evidence` 를 못 채우는 하위질문이 정상적으로 나오는데, 그걸 전부 부족으로 판정하면 재검색이 상한까지 헛돈다.

```yaml
parser: plain
params:
  max_tokens: 600
  temperature: 0.2
system: |-
  당신은 연구 사서입니다. 하위질문 하나에 대해 모인 근거가 충분한지 판단합니다.

  판단 기준:
  - 각 근거에 붙은 본문 발췌를 보고, 제목만으로 짐작하지 말고 하위질문의 핵심 개념을 실제로 다루는지 판단하세요.
  - 하위질문의 핵심 개념을 다루지 않는 논문만 있으면 부족합니다.
  - 특정 시기에만 쏠려 있으면 부족합니다.
  - 근거가 {{ min_evidence }}편 미만이면 부족할 가능성이 높습니다.

  편수는 필요조건이 아니라 신호 중 하나입니다. 편수가 부족해도 핵심 개념을
  정면으로 다루는 근거가 있으면 충분으로 판정하세요. 반대로 편수가 많아도
  발췌가 하위질문과 겉돌면 부족으로 판정하세요.

  부족하다고 판단하면 이미 시도한 검색어와 다른 검색어를 최대 2개 제안하세요.
  같은 말을 바꿔 쓴 것이 아니라 다른 용어·다른 각도여야 합니다.

  반드시 아래 JSON 형식으로만 응답하세요. 설명이나 다른 텍스트는 출력하지 마세요.
  {
    "verdict": "<sufficient 또는 insufficient>",
    "note": "<판단 근거 한 문장>",
    "new_queries": ["<제안 검색어>", "<제안 검색어>"]
  }

  verdict 에는 sufficient 또는 insufficient 만 씁니다.
  new_queries 는 항상 배열입니다. 제안할 것이 없으면 빈 배열로 둡니다.
  note 는 사용자에게 그대로 보여집니다. 한국어로 구체적으로 쓰세요.
user: |-
  하위질문: {{ subquestion }}
  이미 시도한 검색어: {{ tried_queries }}
  모인 근거: {{ evidence_count }}편

  {{ evidence_list }}
```

- [x] **`app/tests/test_research_critic.py`**

```python
import logging

from services.research.critic import (
    _EXCERPT_LEN, _MAX_LISTED, Verdict, format_evidence_list, parse_verdict, should_recheck,
)
from services.research.state import Chunk, Evidence, LLM_VERDICTS, SubQuestion, VERDICTS


class TestParseVerdict:
    def test_sufficient(self):
        raw = '{"verdict": "sufficient", "note": "근거 충분", "new_queries": []}'
        v = parse_verdict(raw)
        assert v.verdict == "sufficient"
        assert v.new_queries == []

    def test_insufficient_with_queries(self):
        raw = ('{"verdict": "insufficient", "note": "3편뿐이다", '
               '"new_queries": ["진로상담 앱 효과", "온라인 진로지도 성과"]}')
        v = parse_verdict(raw)
        assert v.verdict == "insufficient"
        assert v.note == "3편뿐이다"
        assert len(v.new_queries) == 2

    def test_json_in_code_fence(self):
        raw = '```json\n{"verdict": "sufficient", "note": "n", "new_queries": []}\n```'
        assert parse_verdict(raw).verdict == "sufficient"

    def test_garbage_falls_back_to_sufficient(self):
        """판정을 못 읽으면 무한 재검색 대신 멈춘다 — 실패가 루프가 되면 안 된다."""
        v = parse_verdict("죄송합니다 판단할 수 없습니다")
        assert v.verdict == "sufficient"
        assert v.parse_failed is True

    def test_unknown_verdict_value_falls_back(self):
        v = parse_verdict('{"verdict": "maybe", "note": "n", "new_queries": []}')
        assert v.verdict == "sufficient"
        assert v.parse_failed is True

    def test_successful_parse_is_not_marked_failed(self):
        v = parse_verdict('{"verdict": "sufficient", "note": "n", "new_queries": []}')
        assert v.parse_failed is False

    def test_note_does_not_leak_model_output(self):
        """note 는 탐색 경로·진행 패널에 그대로 실린다 — 모델 원문을 담지 않는다."""
        v = parse_verdict("죄송합니다 판단할 수 없습니다")
        assert "죄송합니다" not in v.note

    def test_string_new_queries_does_not_become_characters(self):
        """문자열을 순회하면 "진" 한 글자로 재검색하는 쓰레기 쿼리가 된다."""
        raw = '{"verdict": "insufficient", "note": "n", "new_queries": "진로상담 앱 효과"}'
        assert parse_verdict(raw).new_queries == []

    def test_prose_after_json_does_not_break_parsing(self):
        """탐욕적 슬라이스는 뒤따르는 산문의 } 까지 먹어 파싱이 깨진다."""
        raw = '{"verdict": "sufficient", "note": "n", "new_queries": []} 참고: {예시}'
        assert parse_verdict(raw).verdict == "sufficient"

    def test_parse_failure_logs_raw_for_diagnosis(self, caplog):
        """로그가 자기점검이 꺼졌음을 아는 유일한 신호다 — 원문 없이는 프롬프트를 못 고친다."""
        with caplog.at_level(logging.WARNING):
            parse_verdict("죄송합니다 판단할 수 없습니다")
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings
        assert any("죄송합니다" in r.getMessage() for r in warnings)

    def test_unknown_verdict_logs_raw_for_diagnosis(self, caplog):
        with caplog.at_level(logging.WARNING):
            parse_verdict('{"verdict": "maybe", "note": "n", "new_queries": []}')
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings
        assert any("maybe" in r.getMessage() for r in warnings)


class TestShouldRecheck:
    def _sq(self, verdict):
        return SubQuestion(idx=0, text="q", verdict=verdict)

    def test_insufficient_under_limit(self):
        assert should_recheck(self._sq("insufficient"), recheck_count=0, max_recheck=3)

    def test_at_limit_stops(self):
        assert not should_recheck(self._sq("insufficient"), recheck_count=3, max_recheck=3)

    def test_sufficient_stops(self):
        assert not should_recheck(self._sq("sufficient"), recheck_count=0, max_recheck=3)

    def test_always_insufficient_critic_still_terminates(self):
        """항상 부족을 반환하는 critic 을 물려도 멈춘다."""
        sq = self._sq("insufficient")
        count = 0
        while should_recheck(sq, recheck_count=count, max_recheck=3):
            count += 1
            assert count <= 3
        assert count == 3


class TestLlmVerdicts:
    def test_llm_verdicts_exact(self):
        """부분집합 단언은 VERDICTS 순서가 바뀌어 sufficient 가 빠져도 통과한다."""
        assert LLM_VERDICTS == ("sufficient", "insufficient")

    def test_llm_verdicts_excludes_pending(self):
        assert "pending" not in LLM_VERDICTS
        assert set(LLM_VERDICTS) <= set(VERDICTS)


class TestFormatEvidenceList:
    def _evidence(self, title, year, chunk_text=None):
        chunks = []
        if chunk_text is not None:
            chunks.append(Chunk(chunk_id="c1", text=chunk_text, page_start=1, page_end=1, score=0.9))
        return Evidence(id="E1", cnts_id="cnts1", meta={"title": title, "pub_date": year}, chunks=chunks)

    def test_includes_excerpt_from_first_chunk(self):
        e = self._evidence("제목", "2020", "본문 발췌 내용")
        result = format_evidence_list([e])
        assert result == "- 제목 (2020) — 본문 발췌 내용"

    def test_excerpt_truncated(self):
        e = self._evidence("제목", "2020", "가" * 500)
        excerpt = format_evidence_list([e]).split(" — ", 1)[1]
        assert excerpt == "가" * _EXCERPT_LEN + "…"

    def test_short_excerpt_has_no_ellipsis(self):
        e = self._evidence("제목", "2020", "짧다")
        assert format_evidence_list([e]).endswith("짧다")

    def test_newlines_in_chunk_are_flattened(self):
        """표 청크에는 개행이 실재한다 — 그대로 쓰면 한 항목이 여러 줄로 퍼진다."""
        chunk_text = "[표]\n설명\n\n| a | b |\n| 1 | 2 |"
        e = self._evidence("제목", "2020", chunk_text)
        result = format_evidence_list([e])
        assert "\n" not in result
        assert result == "- 제목 (2020) — [표] 설명 | a | b | | 1 | 2 |"

    def test_list_is_capped_with_remainder_note(self):
        """상한이 없으면 재검색 누적분이 컨텍스트를 넘겨 system 지시가 잘려 나간다."""
        many = [self._evidence(f"제목{i}", "2020", "본문") for i in range(_MAX_LISTED + 5)]
        lines = format_evidence_list(many).splitlines()
        assert len(lines) == _MAX_LISTED + 1
        assert lines[-1] == "- …외 5편"

    def test_empty_meta_values_fall_back(self):
        """이 코드베이스는 빈 메타를 "" 로 표현한다 — get 의 기본값이 안 먹는다."""
        e = Evidence(id="E1", cnts_id="c", meta={"title": "", "pub_date": ""}, chunks=[])
        assert format_evidence_list([e]) == "- (제목 없음) (연도미상)"

    def test_evidence_without_chunks_falls_back_to_title_year(self):
        e = self._evidence("제목", "2020")
        assert format_evidence_list([e]) == "- 제목 (2020)"

    def test_mixed_evidence_does_not_crash(self):
        with_chunk = self._evidence("A", "2020", "본문")
        without_chunk = self._evidence("B", "2021")
        result = format_evidence_list([with_chunk, without_chunk])
        lines = result.splitlines()
        assert lines == ["- A (2020) — 본문", "- B (2021)"]

    def test_empty_list_gives_placeholder(self):
        assert format_evidence_list([]) == "(없음)"
```

- [x] **`app/tests/test_research_llm_json.py`**

```python
from services.research.llm_json import extract_json


class TestExtractJson:
    def test_plain_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_code_fence(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bare_fence(self):
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_preamble_prose(self):
        assert extract_json('다음과 같습니다.\n{"a": 1}') == {"a": 1}

    def test_trailing_prose_with_braces(self):
        """탐욕적 슬라이스는 뒤따르는 } 까지 먹어 파싱이 깨진다."""
        assert extract_json('{"a": 1} 참고: {예시}') == {"a": 1}

    def test_nested_object_is_preserved(self):
        assert extract_json('{"a": {"b": 2}} 끝') == {"a": {"b": 2}}

    def test_no_json_gives_none(self):
        assert extract_json("죄송합니다 판단할 수 없습니다") is None

    def test_broken_json_gives_none(self):
        assert extract_json('{"a": ') is None

    def test_array_at_top_level_gives_none(self):
        """호출부는 dict 를 기대한다 — 리스트를 넘기면 .get 에서 터진다."""
        assert extract_json("[1, 2, 3]") is None

    def test_empty_input(self):
        assert extract_json("") is None

    def test_none_input(self):
        assert extract_json(None) is None
```

- [x] **`app/tests/test_prompts.py` — 새 프롬프트 2종을 렌더 회귀에 추가**

`PromptLibrary` 는 `StrictUndefined` 라, 호출부와 템플릿의 변수명이 어긋나면 여기서 안 잡히고 **워커 런타임에서야** `UndefinedError` 로 터진다. 프롬프트를 추가하면 이 테스트도 함께 늘린다.

```python
    # 딥리서치 2종 — StrictUndefined 라 변수명이 호출부와 어긋나면
    # 여기서 안 잡히고 워커 런타임에서야 UndefinedError 로 터진다.
    rp_s, rp_u, _ = lib.get("research_plan").render(question="청소년 진로상담", limit=6)
    assert "연구 사서" in rp_s and "6" in rp_s and "청소년 진로상담" in rp_u

    rc_s, rc_u, _ = lib.get("research_critique").render(
        subquestion="하위질문", evidence_count=3, evidence_list="- 논문 (2008)",
        min_evidence=5, tried_queries="검색어")
    assert '"verdict"' in rc_s and "하위질문" in rc_u and "3편" in rc_u
```

- [x] **검증** — critic `26 passed`, llm_json `11 passed`. 되돌림 확인: `new_queries` 타입 검사를 빼면 문자열이 `['진','로','상','담', …]` 로 쪼개지고, 발췌 정규화를 빼면 한 항목이 `'- T (2020) — [표]\n설명\n\n| a |'` 로 퍼진다.

---

## Task 7: 하위질문 탐색 — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - 머지 전 리뷰 — `search()` 에 `use_metadata_filter=False` 를 넘긴다(db 를 넘기면 도서 검색용 날짜 필터 LLM 이 하위질문의 사건 연도를 발행연도 조건으로 걸었다). 메타청크 제외를 `explore` 의 사후 필터에서 `chunk_filter=is_source_passage` 로 옮겨 top_k 절단·리랭크 **전에** 거른다(사후에 거르면 걸러진 수만큼 `per_subq_top_k` 가 조용히 줄었다). 쪽수 0 인 보강 청크 `[초록]`·`[키워드]`·`[표 설명]`·`[그림 설명]` 도 뺀다. 그래서 `services/search/pipeline.py` 에 두 인자가 생겼고(기본값은 기존 동작), 리랭크 폴백의 `except Exception` 을 허용 목록으로 좁혔다(Celery 소프트 리밋을 삼키지 않게). `reranker.py` 는 GPU 가 없으면 float32 로 올린다.
> - 아래 "(보고서는 마지막에 근거 전체로 한 번 종합한다)" 류 서술은 옛 설계다 — 종합은 하위질문별 호출이다(Task 8 이후 변경).
>
> 구현·리뷰가 끝났다. 아래는 동기화 시점(`38e6ed1`·`a168e1d`)의 저장소 파일과 일치했다.

> **함정 — `pipeline` 을 최상단에서 import 하지 마라.** `pipeline.py` → `reranker.py` → `import torch` 인데 torch 는 로컬 venv 에 없다(Dockerfile 에서 CUDA 버전으로 설치). 최상단 import 를 쓰면 `pytest` 가 collection 단계에서 죽어 **세션 전체가 0건**이 된다. 함수 본문 안에서 import 하라 — `app/api/book.py:619` 가 이미 그렇게 한다. `docs/ops/recurring-gotchas.md` 13번.

초안과 달라진 것 여섯.

**(1) `from services.search.pipeline import search` 를 `explore()` 함수 본문으로 내렸다**(위 함정).

**(2) 서지 7개 필드를 방어 없이 직접 속성 접근으로 읽는다.** 초안은 `getattr(b, "series_title", None)` 이었다. `get_by_cnts_ids` 는 `dict[str, BookOut]` 을 돌려주고(`Book` ORM 이 아니다 — `BookRepository` 는 어느 메서드도 ORM 을 밖으로 내보내지 않는다, `docs/standards/coding-standard.md` 가 이 리포지토리를 준수 예로 든다) `BookOut` 에 일곱 필드가 모두 있다. `getattr` 기본값은 컬럼명이 바뀌어도 조용히 `None` 을 넣어 **순위가 틀어지는 쪽으로** 실패한다. 테스트가 실제 `BookOut` 을 만들어 이 이름들을 고정한다.

**(3) 검색만 시킨다 — 답변 생성과 쿼리 재작성을 둘 다 끈다.** 초안은 `search(mode="chunk", db=db)` 를 기본값 그대로 불렀다. 두 기본값이 각각 문제다.

`search` 는 청크 모드에서 **무조건** 답변을 만든다(`db` 가 있으면 `expand_context` + 생성, 없으면 생성). 끌 방법이 없었다. `explore` 는 `resp.chunks` 만 읽고 `resp.answer` 를 버리는데, 기본 파라미터(`max_subquestions=6`·`max_recheck=3`)면 한 잡에 6~24회 도므로 컨텍스트 예산 10만 토큰(`CONTEXT_BUDGET_TOKENS`)짜리 확장+생성이 그 횟수만큼 공유 GPU 를 물고 아무것도 남기지 않는다. 시연 예산이 잡당 5~7분이다. 그래서 `pipeline.search()` 에 `generate_answer: bool = True` 를 추가해 `_search_chunk_mode()` 까지 넘기고, `False` 면 확장과 생성을 둘 다 건너뛴다. 기본값이 `True` 라 기존 호출자(`api/book.py`·`api/paper.py`·`api/scenario.py`·`scripts/eval_*.py` — 어느 쪽도 이 인자를 넘기지 않는다)의 동작은 그대로다. 보고서는 마지막에 근거 전체로 한 번 종합한다(Task 8).

`use_rewrite` 기본값은 `True` 인데, `query_rewrite.yaml` 은 **도서 추천 전용** 프롬프트다 — 유사도 규칙이 "제목·저자명은 쿼리에 절대 포함하지 마세요"이고 예시가 채식주의자·카프카·하루키다. 하위질문("부르디외 문화자본론을 적용한 국내 독서격차 연구")을 통과시키면 고유명사가 떨어져 분위기 키워드로 바뀌어 Milvus 에 닿는 문자열이 하위질문이 아니게 된다. 더 나쁜 건 `_enrich_from_db` 가 `(.+?)(같은|비슷한)\s*책` 에 걸리면 쿼리를 그 책의 `themes` 로 통째로 갈아버리는 것이다. 계획 단계가 이미 검색어로 쓸 수 있는 문장을 내놓으므로(`research_plan.yaml`: "각 하위질문은 그 자체로 논문 검색어가 될 만큼 구체적이어야 합니다") 재작성이 보태는 게 없다. 기록도 이쪽이 맞다 — runner 는 검색 직전 문자열을 `subq.queries` 에 남기므로, 재작성이 켜져 있으면 사용자에게 보이는 탐색 경로와 `research_steps.result["queries"]` 가 둘 다 **실제로 보낸 적 없는 쿼리**를 기록해 0건 하위질문을 사후에 진단할 수 없다.

**(4) 근거가 될 수 없는 hit 을 `explore` 에서 떨군다.** 둘이다.

카탈로그 메타 청크(`chunk_idx == -1`, `제목: … | 기관: … | 저자: … | 초록: …`). `doc_type` 스칼라가 같아 `doc_scope="paper"` 를 통과하고, 제목과 초록을 품고 있어 주제형 하위질문에서 점수가 **오히려 잘 나온다**. 그대로 두면 보고서가 서지 덩어리를 "논문 발췌 (p.0-0)" 로 인용하고(`page_start=None` 이 인덱싱 때 0 이 된다) `critic.format_evidence_list` 도 그걸 발췌로 모델에 먹인다. 도서 모드는 이미 `h.chunk_idx != -1` 로 걸러낸다(`# 응답용 청크: 메타 청크 제외`). 청크 모드는 안 걸러내지만 **거기는 논문 검색 화면이 쓰는 라이브 경로라 건드리지 않고** `explore` 에서만 뺀다 — 청크 모드 자체를 바꾸는 건 별건이다.

서지를 못 찾은 청크. `build_evidence` 가 `meta_by_id` 에 없는 `book_id` 를 말없이 버리므로, 그대로 넘기면 근거 수가 조용히 모자라고 critic 이 `insufficient` 를 내 재검색이 상한까지 돌고도 로그에 흔적이 없다. Milvus 에는 있는데 `library_catalog` 행이 사라진 일이 실제로 있었다(`docs/ops/recurring-gotchas.md` 9번). `explorer.py` 는 `log` 를 만들어 두고 한 번도 쓰지 않았다 — 지금은 제외 건수와 `cnts_id` 를 `log.warning` 으로 남긴다.

**(5) 순위용 혼합값을 `score` 에 덮어쓰지 않고 `rank_score` 로 분리했다.** `scoring.py` 의 모듈 docstring 이 "화면에는 생값을 그대로 보여준다 — 정규화는 순위에만 쓴다" 인데, 초안의 `rank_hits` 는 혼합값을 `row["score"]` 에 써 넣고 `build_evidence` 가 그걸 `Chunk.score` 로 복사했다. 혼합값은 1.0 을 넘는다 — 리랭킹 0.92·피인용 40회·2024년·weight 0.2 면 `0.92 * (1 + 0.2*ln(14.33)) = 1.41` 이다. `Chunk.score` 를 0~1 유사도로 읽는 쪽은 141% 를 그리고, 생 리랭킹 점수는 되찾을 길이 없다. 이제 `score` 는 생값 그대로, 정렬은 `rank_score` 로 한다(`HitRow` 에 `rank_score: NotRequired[float]` 추가 — 검색 계층이 행을 만든 직후에는 없고 `rank_hits` 가 채운다). 한 논문 안에서 청크를 고르는 `build_evidence` 의 `score` 정렬은 그대로 둬도 된다 — 같은 논문이면 가중치가 같아 두 값의 순서가 같다.

**(6) `explore()` 에 테스트가 생겼다.** kwarg 이름·`resp.chunks` 모양·`rerank_score` 폴백·부분 응답이 전부 검증되지 않아, 파이프라인에서 `doc_scope=` 를 `scope=` 로 바꿔도 스위트는 초록불이고 워커가 시연 중에 `TypeError: search() got an unexpected keyword argument` 로 죽을 수 있었다(`docs/standards/coding-standard.md:44-45` 위반). 지연 import 덕에 `monkeypatch.setitem(sys.modules, "services.search.pipeline", 대역)` 으로 Milvus·GPU 없이 다 덮인다. 인자 이름이 파이프라인에 실재하는지는 `pipeline.py` 를 `ast` 로 읽어 확인한다 — 대역은 `**kwargs` 로 다 받아주므로 그것만으로는 rename 을 못 잡는다.

- [x] **`app/services/search/pipeline.py`** — `generate_answer` 스위치 (이 태스크에서 추가된 유일한 기존 파일 변경)

```python
async def search(
    query: str,
    *,
    mode: str = "book",
    top_k: int = 10,
    use_rewrite: bool = True,
    use_rerank: bool = True,
    doc_scope: str = "all",   # "paper" | "book" | "all"
    generate_answer: bool = True,   # chunk 모드 전용 — False 면 검색 결과만 돌려준다
    db=None,
) -> ChunkSearchResponse | BookSearchResponse:
    ...
    if mode == "chunk":
        return await _search_chunk_mode(
            query, rewritten, query_dense, query_sparse, top_k, use_rerank, elapsed, db,
            meta_expr=milvus_expr,
            generate_answer=generate_answer,
        )
```

```python
async def _search_chunk_mode(
    ...
    db=None,
    *,
    meta_expr: str | None = None,
    generate_answer: bool = True,
) -> ChunkSearchResponse:
    ...
    # 컨텍스트 확장: 청크 주변 원문 로드 (126K 활용)
    # generate_answer=False 면 확장·생성 둘 다 건너뛴다 — 확장이 먼저 컨텍스트
    # 예산(CONTEXT_BUDGET_TOKENS)만큼 원문을 끌어오므로, 답변을 버릴 호출자에게는
    # 생성뿐 아니라 확장도 순수 낭비다.
    answer = None
    if generate_answer:
        if db:
            try:
                expanded = await expand_context(chunks, db)
                answer = await _generate_answer_with_context(original, expanded)
            except Exception as e:
                log.warning(f"컨텍스트 확장 실패, 청크 텍스트로 fallback: {e}")
                answer = await _generate_answer(original, chunks)
        else:
            answer = await _generate_answer(original, chunks)
```

- [x] **`app/services/research/explorer.py`**

```python
"""explorer.py — 하위질문 1개를 탐색한다

기존 검색 파이프라인을 그대로 쓰고(논문 스코프), 그 위에 피인용 가중만
얹는다. 순위 계산은 rank_hits 로 빼서 Milvus 없이 테스트한다.
"""
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.book import BookRepository
from services.research.scoring import blend_score, impact_per_year, parse_pub_year
from services.research.state import HitRow

log = logging.getLogger(__name__)


def rank_hits(
    hits: list[HitRow], meta_by_id: dict[str, dict], *,
    citation_weight: float, now_year: int,
) -> list[HitRow]:
    """연간 피인용을 얹은 rank_score 로 다시 정렬한다. 입력은 건드리지 않는다.

    혼합값을 score 에 덮어쓰지 않는 이유: 혼합값은 1.0 을 넘는다. 리랭킹 0.92
    짜리 2024년 논문이 40회 인용됐으면 0.92 * (1 + 0.2*ln(14.33)) = 1.41 이다.
    score 를 유사도로 읽는 쪽은 그대로 "141%" 를 그리고, 생 리랭킹 점수는
    되찾을 길이 없어진다. 정렬은 rank_score 로, 표시는 score 로 한다.
    """
    ranked = []
    for hit in hits:
        meta = meta_by_id.get(hit["book_id"]) or {}
        impact = impact_per_year(
            meta.get("kci_citations"), parse_pub_year(meta.get("pub_date")),
            now_year=now_year,
        )
        row = dict(hit)
        row["rank_score"] = blend_score(hit["score"], impact=impact, weight=citation_weight)
        ranked.append(row)
    ranked.sort(key=lambda r: r["rank_score"], reverse=True)
    return ranked


async def explore(query: str, *, params: dict, db: AsyncSession) -> tuple[list[HitRow], dict[str, dict]]:
    """검색 → 서지 조회 → 피인용 가중 재정렬.

    returns (정렬된 hit 목록, cnts_id → 서지 메타)
    """
    # pipeline 은 reranker(torch) 를 물고 와 모듈 최상단에서 임포트하면 이 파일을
    # 단순히 열기만 해도(rank_hits 만 쓰는 테스트에서도) torch 가 있어야 한다.
    # 기존 코드베이스도 같은 이유로 지연 임포트한다(api/book.py·main.py 참고).
    from services.search.pipeline import search

    # generate_answer=False — 여기서 만든 답변은 전부 버려진다(resp.chunks 만 쓴다).
    # 보고서는 마지막에 근거 전체로 한 번 종합한다. 기본 파라미터로도 explore 는 한
    # 잡에 6~24회 도는데, 하위질문마다 생성하면 컨텍스트 예산 10만 토큰짜리 확장+생성이
    # 그 횟수만큼 공유 GPU 를 물고 아무것도 남기지 않는다.
    #
    # use_rewrite=False — 쿼리 재작성은 도서 추천 전용이다. query_rewrite.yaml 의
    # 유사도 규칙이 "제목·저자명은 쿼리에 절대 포함하지 마세요"이고 예시가
    # 채식주의자·카프카·하루키다. 하위질문("부르디외 문화자본론을 적용한 국내 독서격차
    # 연구")을 통과시키면 고유명사가 떨어져 분위기 키워드로 바뀌고, "X 같은 책" 패턴에
    # 걸리면 _enrich_from_db 가 쿼리를 그 책의 themes 로 통째로 갈아버린다. 계획
    # 단계가 이미 검색어로 쓸 수 있는 문장을 내놓는다(research_plan.yaml).
    # 기록도 이쪽이 맞다 — runner 는 검색 직전 문자열을 subq.queries 에 남기므로,
    # 재작성이 켜져 있으면 사용자에게 보이는 탐색 경로와 research_steps.result["queries"]
    # 가 둘 다 실제로 보낸 적 없는 쿼리를 기록해 0건 하위질문을 사후에 진단할 수 없다.
    resp = await search(
        query, mode="chunk", top_k=params["per_subq_top_k"],
        doc_scope="paper", generate_answer=False, use_rewrite=False, db=db,
    )
    # chunk_idx == -1 은 카탈로그 메타 청크다("제목: … | 기관: … | 초록: …").
    # doc_type 스칼라가 같아 doc_scope="paper" 를 통과하고 제목·초록을 품고 있어
    # 주제형 하위질문에서 점수가 오히려 잘 나온다. 그대로 두면 보고서가 서지 덩어리를
    # "논문 발췌 (p.0-0)" 로 인용하고(page_start 가 없어 인덱싱 때 0 이 된다)
    # critic 에게도 그게 발췌로 들어간다. chunk 모드는 논문 검색 화면이 쓰는 라이브
    # 경로라 파이프라인은 건드리지 않고 여기서만 걸러낸다(도서 모드는 이미 제외한다).
    hits: list[HitRow] = [
        {
            "book_id": c.book_id, "chunk_id": c.chunk_id, "text": c.text,
            "page_start": c.page_start, "page_end": c.page_end,
            "score": c.rerank_score if c.rerank_score is not None else c.score,
        }
        for c in resp.chunks
        if c.chunk_idx != -1
    ]
    if not hits:
        return [], {}

    repo = BookRepository(db)
    books = await repo.get_by_cnts_ids(list({h["book_id"] for h in hits}))
    meta_by_id = {
        cnts_id: {
            "title": b.title, "personal_author": b.personal_author,
            "series_title": b.series_title, "vol_issue": b.vol_issue,
            "pub_date": b.pub_date, "kci_citations": b.kci_citations,
            "grade": b.grade,
        }
        for cnts_id, b in books.items()
    }
    # 서지를 못 찾은 청크는 여기서 떨군다. build_evidence 가 meta_by_id 에 없는
    # book_id 를 말없이 버리기 때문에, 그대로 넘기면 근거 수가 조용히 모자라고
    # critic 이 insufficient 를 내 재검색이 상한까지 돌고도 로그에 흔적이 없다.
    # Milvus 에는 있는데 library_catalog 행이 사라진 일이 실제로 있었다
    # (docs/ops/recurring-gotchas.md 9번).
    kept = [h for h in hits if h["book_id"] in meta_by_id]
    if len(kept) < len(hits):
        orphans = sorted({h["book_id"] for h in hits if h["book_id"] not in meta_by_id})
        log.warning(
            "[explore] 서지 없는 청크 %d/%d 건 제외 — cnts_id %s",
            len(hits) - len(kept), len(hits), orphans[:5],
        )
    ranked = rank_hits(
        kept, meta_by_id,
        citation_weight=params["citation_weight"], now_year=datetime.now().year,
    )
    return ranked, meta_by_id
```

- [x] **`app/tests/test_research_explorer.py`**

```python
"""test_research_explorer.py — 하위질문 탐색.

explore() 는 Milvus·GPU 없이도 대역으로 검증한다. 실제 pipeline 을 import 하면
reranker → torch 가 필요해 수집 단계에서 세션이 통째로 죽으므로, explore 안의
지연 import 를 sys.modules 로 가로챈다.
"""
import ast
import asyncio
import logging
import sys
import types
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from schemas.book import BookOut, ChunkHit, ChunkSearchResponse
from services.research.explorer import explore, rank_hits
from services.research.state import merge_params

_DB = object()          # explore 가 그대로 흘려보내기만 하는 세션 자리


class TestRankHits:
    def _hit(self, book_id, score):
        return {"book_id": book_id, "chunk_id": f"{book_id}-c", "text": "t",
                "page_start": 1, "page_end": 1, "score": score}

    def _meta(self, pub_date, citations):
        return {"title": "t", "pub_date": pub_date, "kci_citations": citations}

    def test_empty_input(self):
        assert rank_hits([], {}, citation_weight=0.2, now_year=2026) == []

    def test_missing_metadata_scores_as_zero_impact(self):
        hits = [self._hit("A", 0.9)]
        ranked = rank_hits(hits, {}, citation_weight=0.2, now_year=2026)
        assert ranked[0]["rank_score"] == pytest.approx(0.9)

    def test_raw_score_is_kept_and_blend_goes_to_rank_score(self):
        """score 는 화면에 유사도로 나간다 — 혼합값을 덮어쓰면 141% 가 표시되고
        생 리랭킹 점수를 되찾을 길이 없어진다."""
        hits = [self._hit("A", 0.92)]
        ranked = rank_hits(hits, {"A": self._meta("2024-01", 40)},
                           citation_weight=0.2, now_year=2026)
        assert ranked[0]["score"] == pytest.approx(0.92)
        assert ranked[0]["rank_score"] > 1.0

    def test_impact_reorders_close_scores(self):
        hits = [self._hit("OLD", 0.81), self._hit("NEW", 0.80)]
        meta = {
            "OLD": self._meta("2002-01", 50),    # 50/25 = 2.0
            "NEW": self._meta("2024-01", 40),    # 40/3  = 13.3
        }
        ranked = rank_hits(hits, meta, citation_weight=0.2, now_year=2026)
        assert ranked[0]["book_id"] == "NEW"

    def test_zero_weight_preserves_rerank_order(self):
        hits = [self._hit("OLD", 0.81), self._hit("NEW", 0.80)]
        meta = {"OLD": self._meta("2002-01", 50), "NEW": self._meta("2024-01", 40)}
        ranked = rank_hits(hits, meta, citation_weight=0.0, now_year=2026)
        assert ranked[0]["book_id"] == "OLD"

    def test_null_citations_with_valid_year(self):
        """kci_citations 는 nullable 이다 — 한 편이 None 이라고 하위질문 전체가
        TypeError 로 죽으면 안 된다."""
        ranked = rank_hits([self._hit("A", 0.9)], {"A": self._meta("2008-06", None)},
                           citation_weight=0.2, now_year=2026)
        assert ranked[0]["rank_score"] == pytest.approx(0.9)

    def test_original_hits_are_not_mutated(self):
        hits = [self._hit("A", 0.9)]
        rank_hits(hits, {"A": self._meta("2008-01", 10)}, citation_weight=0.2, now_year=2026)
        assert hits[0]["score"] == pytest.approx(0.9)
        assert "rank_score" not in hits[0]


def _chunk(book_id, *, chunk_idx=4, text="본문", score=0.5, rerank_score=0.8):
    """실제 ChunkHit 을 쓴다 — explore 가 읽는 필드가 스키마에 실재하는지도 같이 본다."""
    return ChunkHit(
        chunk_id=f"{book_id}__{chunk_idx:04d}", book_id=book_id, chunk_idx=chunk_idx,
        text=text, page_start=3, page_end=4, score=score, rerank_score=rerank_score,
    )


def _book(cnts_id, *, title="논문 가", pub_date="2008-06", kci_citations=3):
    """실제 BookOut 을 쓴다 — explore 가 방어 없이 직접 속성 접근으로 읽는 7개
    필드(title·personal_author·series_title·vol_issue·pub_date·kci_citations·grade)가
    스키마에 실재하는지 여기서 고정된다."""
    return BookOut(
        id=uuid4(), cnts_id=cnts_id, title=title, created_at=datetime(2026, 1, 1),
        personal_author="저자", series_title="학술지", vol_issue="12(3)",
        pub_date=pub_date, kci_citations=kci_citations, grade="등재",
    )


class _FakeSearch:
    """pipeline.search 대역 — 호출 kwargs 를 그대로 붙잡아 둔다."""

    def __init__(self, chunks):
        self._chunks = chunks
        self.calls: list[dict] = []

    async def __call__(self, query, **kwargs):
        self.calls.append({"query": query, **kwargs})
        return ChunkSearchResponse(query=query, chunks=self._chunks, elapsed_ms=1.0)


class _FakeRepo:
    """BookRepository 대역. 클래스 자리에 인스턴스를 꽂아 `BookRepository(db)` 를 받는다."""

    def __init__(self, books):
        self._books = books
        self.requested: list[str] = []

    def __call__(self, db):
        return self

    async def get_by_cnts_ids(self, cnts_ids):
        # 실물처럼 찾은 것만 돌려준다 — 없는 cnts_id 는 키가 아예 빠진다.
        self.requested = list(cnts_ids)
        return {k: v for k, v in self._books.items() if k in cnts_ids}


def _pipeline_search_params() -> set[str]:
    """pipeline.search 의 인자 이름을 소스에서 읽는다.

    import 하면 torch 가 필요해 로컬에서 수집 단계가 죽는다. explore 가 넘기는
    kwarg 가 파이프라인에 실재하는지는 확인해야 하고(어긋나면 워커에서
    TypeError 로만 드러난다) 시그니처만 보면 되므로 ast 로 읽는다.
    """
    src = (Path(__file__).resolve().parents[1] / "services" / "search" / "pipeline.py")
    fn = next(
        node for node in ast.parse(src.read_text(encoding="utf-8")).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "search"
    )
    return {a.arg for a in fn.args.args + fn.args.kwonlyargs}


class TestExplore:
    def _run(self, monkeypatch, *, chunks, books, params=None):
        fake_search = _FakeSearch(chunks)
        module = types.ModuleType("services.search.pipeline")
        module.search = fake_search
        monkeypatch.setitem(sys.modules, "services.search.pipeline", module)
        fake_repo = _FakeRepo(books)
        monkeypatch.setattr("services.research.explorer.BookRepository", fake_repo)
        ranked, meta = asyncio.run(
            explore("하위질문", params=merge_params(params or {}), db=_DB)
        )
        return fake_search, fake_repo, ranked, meta

    def test_search_receives_retrieval_only_kwargs(self, monkeypatch):
        """딥리서치는 검색만 필요하다 — 답변 생성과 쿼리 재작성을 둘 다 끈다."""
        fake_search, _, _, _ = self._run(
            monkeypatch, chunks=[_chunk("A")], books={"A": _book("A")},
            params={"per_subq_top_k": 7},
        )
        assert fake_search.calls == [{
            "query": "하위질문", "mode": "chunk", "top_k": 7, "doc_scope": "paper",
            "generate_answer": False, "use_rewrite": False, "db": _DB,
        }]

    def test_every_kwarg_exists_on_the_real_pipeline(self, monkeypatch):
        """대역은 **kwargs 로 다 받는다 — 파이프라인에서 인자명이 바뀌어도 초록불이
        유지되고 워커가 TypeError 로 죽는다. 실제 시그니처와 맞춰 둔다."""
        fake_search, _, _, _ = self._run(
            monkeypatch, chunks=[_chunk("A")], books={"A": _book("A")},
        )
        assert set(fake_search.calls[0]) <= _pipeline_search_params()

    def test_rerank_zero_is_not_treated_as_missing(self, monkeypatch):
        """0.0 은 "리랭커가 이 청크를 버렸다"는 정보다. falsy 라고 벡터 점수로
        되돌리면 버려진 청크가 0.7 로 되살아난다."""
        _, _, ranked, _ = self._run(
            monkeypatch, chunks=[_chunk("A", score=0.7, rerank_score=0.0)],
            books={"A": _book("A")},
        )
        assert ranked[0]["score"] == pytest.approx(0.0)

    def test_rerank_none_falls_back_to_vector_score(self, monkeypatch):
        """리랭킹이 실패하면 rerank_score 가 없는 채로 내려온다."""
        _, _, ranked, _ = self._run(
            monkeypatch, chunks=[_chunk("A", score=0.42, rerank_score=None)],
            books={"A": _book("A")},
        )
        assert ranked[0]["score"] == pytest.approx(0.42)

    def test_metadata_chunk_is_excluded(self, monkeypatch):
        """chunk_idx=-1 은 카탈로그 서지 덩어리다 — 제목·초록을 품어 점수가 잘
        나오지만 발췌로 인용되면 "논문 발췌 (p.0-0)" 가 된다."""
        chunks = [
            _chunk("A", chunk_idx=-1, text="제목: 논문 가 | 기관: … | 초록: …", rerank_score=0.99),
            _chunk("A", chunk_idx=4, rerank_score=0.5),
        ]
        _, _, ranked, _ = self._run(monkeypatch, chunks=chunks, books={"A": _book("A")})
        assert [h["chunk_id"] for h in ranked] == ["A__0004"]

    def test_only_metadata_chunks_gives_no_hits(self, monkeypatch):
        _, fake_repo, ranked, meta = self._run(
            monkeypatch, chunks=[_chunk("A", chunk_idx=-1)], books={"A": _book("A")},
        )
        assert (ranked, meta) == ([], {})
        assert fake_repo.requested == []

    def test_hits_without_bibliography_are_dropped(self, monkeypatch):
        """서지를 못 찾으면 근거가 될 수 없다 — build_evidence 가 말없이 버리므로
        여기서 떨궈야 근거 수가 왜 모자란지 드러난다."""
        chunks = [_chunk("A"), _chunk("GONE")]
        _, _, ranked, meta = self._run(monkeypatch, chunks=chunks, books={"A": _book("A")})
        assert [h["book_id"] for h in ranked] == ["A"]
        assert set(meta) == {"A"}

    def test_dropped_hits_are_logged(self, monkeypatch, caplog):
        chunks = [_chunk("A"), _chunk("GONE")]
        with caplog.at_level(logging.WARNING, logger="services.research.explorer"):
            self._run(monkeypatch, chunks=chunks, books={"A": _book("A")})
        assert "GONE" in caplog.text

    def test_meta_carries_the_bibliography_fields(self, monkeypatch):
        _, _, _, meta = self._run(
            monkeypatch, chunks=[_chunk("A")], books={"A": _book("A")},
        )
        assert meta == {"A": {
            "title": "논문 가", "personal_author": "저자", "series_title": "학술지",
            "vol_issue": "12(3)", "pub_date": "2008-06", "kci_citations": 3,
            "grade": "등재",
        }}

    def test_no_chunks_returns_empty(self, monkeypatch):
        _, fake_repo, ranked, meta = self._run(monkeypatch, chunks=[], books={})
        assert (ranked, meta) == ([], {})
        assert fake_repo.requested == []
```

- [x] **`app/tests/test_search_chunk_answer_flag.py`** (신규 — 초안에 없던 파일)

```python
"""test_search_chunk_answer_flag.py — 청크 모드 답변 생성 스위치.

딥리서치 탐색은 resp.chunks 만 쓰고 answer 를 버린다. 하위질문마다 답변을
만들면 컨텍스트 예산 10만 토큰짜리 확장+생성이 한 잡에 6~24회 돌고 전부
폐기된다 — 그래서 generate_answer 를 받는다. 기본값은 True 라 기존
호출자(도서·논문 검색 API)의 동작은 그대로다.

pipeline 은 reranker(torch)·indexer(pymilvus) 를 물고 오므로, 미설치 환경에서만
더미를 꽂아 import 를 통과시킨다(test_embed_index_guard.py 와 같은 방식).
"""
import asyncio
import importlib
import sys
from unittest.mock import MagicMock

_HEAVY = ("torch", "transformers", "FlagEmbedding", "pymilvus")
# 더미를 꽂은 채 우리 쪽 모듈이 sys.modules 에 남으면 뒤에 도는 테스트가 Mock 을
# 물려받는다. monkeypatch.delitem 으로 지워 두면 테스트가 끝날 때 없는 상태로
# 복원되고 다음 사용자가 제대로 다시 import 한다.
_CACHED = ("services.search.pipeline", "services.search.reranker",
           "services.ingestion.embedder", "services.ingestion.indexer")


def _load_pipeline(monkeypatch):
    for name in _HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    for name in _CACHED:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("services.search.pipeline")


class _Hit:
    """indexer.search_chunks 가 돌려주는 행 대역."""

    chunk_id, book_id, chunk_idx = "A__0004", "A", 4
    text, page_start, page_end, score = "본문", 3, 4, 0.5


def _patch(monkeypatch, pipeline) -> list[str]:
    """Milvus 검색은 1건으로 고정하고, 확장·생성 3종은 호출 기록만 남긴다."""
    monkeypatch.setattr(pipeline, "search_chunks", lambda *a, **k: [_Hit()])
    called: list[str] = []

    async def _expand(chunks, db):
        called.append("expand")
        return []

    async def _with_context(query, contexts):
        called.append("with_context")
        return "확장 답변"

    async def _plain(query, chunks):
        called.append("plain")
        return "기본 답변"

    monkeypatch.setattr(pipeline, "expand_context", _expand)
    monkeypatch.setattr(pipeline, "_generate_answer_with_context", _with_context)
    monkeypatch.setattr(pipeline, "_generate_answer", _plain)
    return called


def _chunk_mode(pipeline, *, db, **kwargs):
    return asyncio.run(pipeline._search_chunk_mode(
        "질문", None, [0.1], {1: 0.2}, 3, False, 0.0, db, **kwargs,
    ))


def test_default_generates_with_expanded_context(monkeypatch):
    """기본값 True — 기존 호출자의 동작이 바뀌면 안 된다."""
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=MagicMock())
    assert resp.answer == "확장 답변"
    assert called == ["expand", "with_context"]


def test_false_skips_expansion_and_generation(monkeypatch):
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=MagicMock(), generate_answer=False)
    assert resp.answer is None
    assert called == []
    assert len(resp.chunks) == 1        # 검색 결과는 그대로 온다


def test_false_also_skips_the_no_db_path(monkeypatch):
    """db 가 없으면 예전 코드는 _generate_answer 로 답변을 만들었다 — 이쪽도 꺼진다."""
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    resp = _chunk_mode(pipeline, db=None, generate_answer=False)
    assert resp.answer is None
    assert called == []


def test_search_threads_the_flag_into_chunk_mode(monkeypatch):
    """search() 가 안 넘기면 explore 의 generate_answer=False 가 조용히 무시된다."""
    pipeline = _load_pipeline(monkeypatch)
    called = _patch(monkeypatch, pipeline)
    monkeypatch.setattr(pipeline, "embed_texts", lambda texts, is_query=False: ([[0.1]], [{1: 0.2}]))
    resp = asyncio.run(pipeline.search(
        "질문", mode="chunk", top_k=3, use_rewrite=False, use_rerank=False,
        doc_scope="paper", generate_answer=False, db=None,
    ))
    assert resp.answer is None
    assert called == []
```

- [x] **검증** — explorer `17 passed`, scoring `16 passed`, 청크 모드 플래그 `4 passed`, 전체 회귀 `295 passed`(Task 8 진행분 포함).

되돌림 확인(프로덕션 코드를 실제로 되돌려 실패를 본 것):

| 되돌린 것 | 떨어지는 테스트 |
|---|---|
| `explore` 가 `generate_answer=False` 를 안 넘김 | `test_search_receives_retrieval_only_kwargs` |
| `pipeline.search` 에서 `generate_answer` 인자 삭제 | `test_every_kwarg_exists_on_the_real_pipeline` |
| `if generate_answer:` 가드 제거(항상 생성) | `test_false_skips_expansion_and_generation` 외 2건 |
| `explore` 가 `use_rewrite=False` 를 안 넘김 | `test_search_receives_retrieval_only_kwargs` |
| `if c.chunk_idx != -1` 제거 | `test_metadata_chunk_is_excluded`·`test_only_metadata_chunks_gives_no_hits` |
| 혼합값을 `row["score"]` 에 덮어씀 | `test_raw_score_is_kept_and_blend_goes_to_rank_score` 외 3건 |
| `rank_hits` 에 `kept` 대신 `hits` 를 넘김 | `test_hits_without_bibliography_are_dropped` |
| `impact_per_year` 가드를 `pub_year is None or kci_citations <= 0 or kci_citations is None` 로 재배치 | `test_null_citations_gives_zero`·`test_null_citations_with_valid_year` (`TypeError`) |

## Task 8: 보고서 종합 — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 가장 크게 바뀐 절이다. 최종 코드는 저장소가 정본이다.**
> - `b6360b8` (라이브에서 발견한 버그) — 전체를 한 번에 맡기던 종합을 **하위질문별 호출**로 바꿨다. 절 구성은 코드가 정한다: `build_section`·`section_paper_ids`·`PAPERS_PER_SECTION = 5`·`_synthesize_section`. 한계에 "서술을 생성하지 못한 절 N개"(`failed_sections`)·"요약을 생성하지 못한 논문 N편"(`unsummarized_total`)을 더했고 요약 속 마커는 `strip_markers` 로 걷는다. 프롬프트는 `max_tokens: 4000`, 변수 `question`·`subquestion`·`evidence_block`·`paper_ids`, 출력 `{"intro", "summaries": {"E#": …}, "future"}` 다. **아래 YAML(`max_tokens: 8000`·`sections` 배열 예시·`evidence_blocks`)은 `recurring-gotchas.md` 15번의 원인이던 옛 프롬프트 그대로다** — 최종 파서와 섞으면 `StrictUndefined` 로 렌더부터 실패한다. 아래 테스트 블록에도 `TestBuildSection`·`TestSynthesize` 가 없다.
> - 머지 전 리뷰 — 절 단위 1회 재시도(전송 오류·JSON 해석 실패·서술 없는 응답, `_SECTION_ATTEMPTS = 2`) 후에도 실패한 절만 논문 목록으로 남기고 다른 절은 버리지 않는다. 성공 판정을 파싱 여부가 아니라 서술 유무(`_has_narrative`)로 한다. 마커 검증 집합을 **그 절에 준 번호**로 한정했다(전역 집합이면 지어낸 작은 번호가 통과). 모델 출력 필드 타입 정리(`_text` — 배열은 잇고 null·dict 는 버림). 취소 확인(`should_stop` → `SynthesisCanceled`). 보고서 청크에 `score` 포함(지금 어느 절이든 가리키는 청크만 점수순), 절별 `evidence_chunks`·`chunk_scores`, `trail` 에 `parse_failed`·`failed`·`capped`, 한계의 이중 계수 제거, 상한(`capped`)·탐색 오류(`failed`)를 "근거 없음"과 구분하는 문구.
> - 대표 논문 요약은 여전히 절의 논문 최대 5편을 한 호출에 넣고 번호별로 받는다 — spec §4-1 의 구조적 인용과의 차이는 spec §4-1 구현 시 변경.
>
> 구현·리뷰가 끝났다. 아래는 동기화 시점(`248b5e8`)의 저장소 파일과 일치했다.

인용 무결성의 마지막 층이다. 여기서 두 종류의 인용이 합쳐진다 — 구조로 정해진 것(대표 논문 요약)과 검증으로 지킨 것(도입·향후 과제).

초안과 달라진 것 셋.

**(1) 한계 섹션이 "마커 없는 서술"과 "지어낸 근거 번호"를 나눈다.** 초안은 `UNMARKED_THRESHOLD = 3` 하나로 둘을 묶었는데, 그러면 자기 테스트와 모순됐다 — `[E99]` 하나를 먹인 테스트가 한계 문장을 기대하는데 `1 >= 3` 이 거짓이다. 둘은 성격이 다르다. **마커 없는 문장**은 연결 문장일 수 있어 3건까지 관용한다(`"이 절에서는 …을 다룬다."`). **해석 안 되는 `[E99]`** 는 모델이 근거 번호를 지어낸 것이라 1건부터 보고한다. 하나로 합치면 무해한 쪽을 과다보고하고 심각한 쪽을 과소보고한다.

이 분리가 `MarkerResult.dropped` 를 살렸다. Task 4 에서 만들고 자기 테스트가 단언하는데 **소비하는 코드가 없었다** — 무결성 보장 옆의 죽은 데이터는 없는 것보다 나쁘다. 뭔가 검사하는 것처럼 읽히기 때문이다.

**(2) 근거 0편인 하위질문의 `note` 를 버리지 않는다.** 초안은 `if not sq.evidence_ids` 가 먼저 걸리고 `note` 는 `elif verdict == "insufficient"` 에만 붙어, **왜 아무것도 못 찾았는지가 가장 중요한 순간에** 정확히 그 설명을 버렸다.

**(3) `dropped_total` 을 기본값 없는 키워드 인자로 받는다.** 무결성 수치가 조용히 "없음"으로 기본값을 갖는 것이 이 결정이 막으려는 실패 그 자체다.

- [x] **`app/services/research/synthesizer.py`**

```python
"""synthesizer.py — 보고서 조립

인용을 두 갈래로 다룬다.
- 대표 논문 요약: 불릿 = 논문이므로 인용이 구조로 정해진다. 모델이 고르지 않는다.
- 도입·향후 과제: 모델이 [E3] 마커를 달고 여기서 전수 검증한다.

제목·저자·연도는 모델 출력에서 가져오지 않는다. evidence 의 meta 를 쓴다 —
라벨을 모델이 쓰게 두면 언젠가 없는 논문을 만들어낸다.
"""
import logging

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.citations import bind_markers
from services.research.llm_json import extract_json
from services.research.state import ResearchState

log = logging.getLogger(__name__)

UNMARKED_THRESHOLD = 3


def build_limitations(
    state: ResearchState, *, unmarked_total: int, dropped_total: int,
) -> list[str]:
    """자기점검 결과를 사용자에게 보이는 문장으로 바꾼다.

    판정 파싱이 실패한 하위질문(parse_failed)을 반드시 별도로 센다. 실패는
    verdict="sufficient" 로 떨어지므로 아래 insufficient 분기에 걸리지 않고,
    그대로 두면 자기점검이 전부 꺼져도 보고서가 "한계 없음"으로 보인다.

    없는 근거 번호(dropped)와 무근거 서술(unmarked)도 한 문장으로 합치지
    않는다. 종류가 다른 사건이다 — 마커 없는 문장은 "이 절에서는 …을 다룬다"
    같은 연결 문장일 때가 많아 몇 건은 넘긴다. 반면 없는 번호를 가리킨 표기는
    모델이 근거를 지어낸 것이니 1건부터 보고한다. 합치면 흔한 쪽을 과하게
    알리면서 정작 심각한 쪽을 임계값에 묻는다.
    """
    out: list[str] = []
    for sq in state.subquestions:
        # note 를 두 분기 모두에 붙인다. 근거가 0편인 하위질문은 아래
        # insufficient 분기에 닿지 못하는데, 정작 "왜 못 찾았는지"가 가장
        # 필요한 경우다 — 여기서 흘리면 critic 의 note 가 어디에도 안 실린다.
        note = f" — {sq.note}" if sq.note else ""
        # failed 를 evidence_ids 보다 먼저 본다. 탐색이 예외로 죽은 하위질문도
        # evidence_ids 가 비어 있어 아래 분기에 걸리는데, 그러면 시스템 장애가
        # "근거를 찾지 못했다"는 연구 결과로 둔갑한다. 코퍼스에 자료가 없는 것과
        # 우리 쪽이 터진 것은 사용자에게 완전히 다른 정보다.
        if sq.failed:
            out.append(f"'{sq.text}' 는 탐색 중 오류로 확인하지 못했다{note}")
        elif not sq.evidence_ids:
            out.append(f"'{sq.text}' 에 대해서는 근거를 찾지 못했다{note}")
        elif sq.verdict == "insufficient":
            out.append(
                f"'{sq.text}' 는 근거 {len(sq.evidence_ids)}편으로 결론이 약하다{note}"
            )

    unchecked = sum(1 for sq in state.subquestions if sq.parse_failed)
    if unchecked:
        out.append(
            f"자동 점검을 완료하지 못한 하위질문이 {unchecked}건 있다 — "
            f"그 부분의 근거 충분성은 확인되지 않았다."
        )

    if dropped_total:
        out.append(
            f"존재하지 않는 근거 번호를 가리킨 인용 표기 "
            f"{dropped_total}건을 본문에서 제거했다."
        )

    if unmarked_total >= UNMARKED_THRESHOLD:
        out.append(f"근거 표기가 없는 서술 {unmarked_total}건이 있다.")
    return out


def _serialize_evidence(state: ResearchState) -> dict:
    return {
        eid: {
            "cnts_id": ev.cnts_id,
            "meta": ev.meta,
            "chunks": [
                {"chunk_id": c.chunk_id, "text": c.text,
                 "page_start": c.page_start, "page_end": c.page_end}
                for c in ev.chunks
            ],
        }
        for eid, ev in state.evidence.items()
    }


def assemble_report(
    state: ResearchState, sections: list[dict], *, unmarked_total: int,
) -> dict:
    valid = set(state.evidence.keys())
    by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
    unmarked = unmarked_total
    # 마커 검증 결과는 bind_markers 호출마다 누적한다. 섹션마다 도입·향후
    # 과제로 여러 번 부르므로 한 번의 반환값만 읽으면 나머지 호출에서 지운
    # 표기가 조용히 사라진다. dropped 는 번호 종류가 아니라 본문에 박힌
    # 표기 수로 센다 — 사용자가 보는 단위가 그것이다.
    dropped = 0
    out_sections = []

    for sec in sections:
        intro = bind_markers(sec.get("intro", ""), valid)
        unmarked += intro.unmarked
        dropped += len(intro.dropped)

        papers = []
        for p in sec.get("papers", []):
            eid = by_cnts.get(p["cnts_id"])
            if eid is None:
                continue                      # 근거에 없는 논문은 싣지 않는다
            papers.append({
                "cnts_id": p["cnts_id"],
                "summary": p.get("summary", ""),
                "evidence": [eid],            # 구조적 인용 — 모델이 고르지 않는다
            })

        future = []
        for f in sec.get("future", []):
            res = bind_markers(f.get("text", ""), valid)
            unmarked += res.unmarked
            dropped += len(res.dropped)
            # used 를 bind_markers 가 돌려준다 — 여기서 정규식을 다시 쓰면
            # 마커 문법이 두 곳으로 갈라진다.
            future.append({"text": res.text, "evidence": res.used})

        out_sections.append({
            "heading": sec.get("heading", ""),
            "intro": intro.text, "papers": papers, "future": future,
        })

    return {
        "question": state.question,
        "range": state.corpus_range,
        "sections": out_sections,
        "evidence": _serialize_evidence(state),
        "trail": [
            {"subquestion": sq.text, "queries": sq.queries,
             "evidence_count": len(sq.evidence_ids),
             "verdict": sq.verdict, "note": sq.note}
            for sq in state.subquestions
        ],
        "limitations": build_limitations(
            state, unmarked_total=unmarked, dropped_total=dropped,
        ),
    }


async def synthesize(state: ResearchState) -> dict:
    blocks = []
    for sq in state.subquestions:
        lines = []
        for eid in sq.evidence_ids:
            ev = state.evidence[eid]
            excerpt = ev.chunks[0].text[:400] if ev.chunks else ""
            lines.append(
                f"[{eid}] {ev.meta.get('title')} "
                f"({ev.meta.get('pub_date')}, {ev.meta.get('series_title')}) "
                f"cnts_id={ev.cnts_id}\n{excerpt}"
            )
        blocks.append(f"## {sq.text}\n" + "\n\n".join(lines))

    system, user, llm_params = get_prompt("research_synthesize").render(
        question=state.question, evidence_blocks="\n\n".join(blocks),
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params, timeout=300.0,
    )
    # Task 6 에서 뺀 공용 추출기를 쓴다. 여기서 다시 구현하지 마라 —
    # body[index("{"):rindex("}")+1] 은 JSON 뒤에 } 를 포함한 산문이 붙으면
    # 그 끝까지 먹어 파싱이 깨진다.
    data = extract_json(raw)
    if data is None:
        log.error("[research] 종합 JSON 파싱 실패: %s", (raw or "")[:300])
        raise ValueError("보고서 종합 출력을 해석하지 못했다")
    sections = data.get("sections") or []

    return assemble_report(state, sections, unmarked_total=0)
```

- [x] **`app/domains/nl_library/prompts/research_synthesize.yaml`**

```yaml
parser: plain
params:
  max_tokens: 8000
  temperature: 0.3
system: |-
  당신은 국내 학술논문을 다루는 연구 사서입니다. 수집된 근거만으로 보고서를 씁니다.

  절대 규칙:
  - 제공된 근거에 없는 내용을 쓰지 마세요. 추측·일반상식·외부지식 금지.
  - 논문 제목·저자·연도를 본문에 쓰지 마세요. 시스템이 서지에서 직접 렌더합니다.
  - 근거를 인용할 때는 [E3] 형태의 마커만 씁니다. 없는 번호를 쓰지 마세요.
  - 한국어로 씁니다.

  JSON 하나만 출력하세요.
  {"sections": [
     {"heading": "하위질문을 소제목으로 다듬은 문장",
      "intro": "이 주제의 흐름을 설명하는 2~4문장. 문장마다 [E#] 를 답니다.",
      "papers": [{"cnts_id": "근거의 cnts_id", "summary": "이 논문이 무엇을 했고 무엇을 주장하는지 2~3문장"}],
      "future": [{"text": "남은 과제 한 문장 [E#]."}]}
  ]}

  papers 의 summary 에는 논문 제목을 쓰지 마세요. 내용만 씁니다.
user: |-
  연구 질문: {{ question }}

  {{ evidence_blocks }}
```

- [x] **`app/tests/test_research_synthesizer.py`**

```python
from services.research.state import Chunk, Evidence, ResearchState, SubQuestion, merge_params
from services.research.synthesizer import assemble_report, build_limitations


def _state():
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    st.subquestions = [
        SubQuestion(idx=0, text="하위1", evidence_ids=["E1"],
                    verdict="sufficient", note="충분하다"),
        SubQuestion(idx=1, text="하위2", evidence_ids=[],
                    verdict="insufficient", note="2015년 이후 자료가 없다"),
    ]
    st.evidence = {
        "E1": Evidence(id="E1", cnts_id="A", meta={"title": "논문 가", "pub_date": "2008-06"},
                       chunks=[Chunk("c1", "본문", 3, 3, 0.9)]),
    }
    return st


class TestBuildLimitations:
    def test_insufficient_subquestion_is_reported(self):
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=0)
        assert any("하위2" in x for x in lims)
        assert any("2015년 이후 자료가 없다" in x for x in lims)

    def test_sufficient_subquestion_is_not_reported(self):
        assert not any("하위1" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_no_evidence_subquestion_is_reported(self):
        assert any("근거를 찾지 못했다" in x
                   for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_failed_subquestion_is_not_reported_as_missing_evidence(self):
        """탐색이 예외로 죽은 하위질문을 "근거를 찾지 못했다"로 쓰면 안 된다.

        그건 연구 결과처럼 읽히는 시스템 장애다. 코퍼스에 자료가 없는 것과
        우리 쪽이 터진 것은 사용자에게 완전히 다른 정보이고, 이 기능의 값이
        "모른다고 정직하게 말하는 것"인데 장애를 발견으로 포장하면 무너진다.
        """
        st = _state()
        st.subquestions[1].failed = True
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert any("하위2" in x and "오류로 확인하지 못했다" in x for x in lims)
        assert not any("하위2" in x and "근거를 찾지 못했다" in x for x in lims)

    def test_failed_subquestion_with_evidence_is_still_reported(self):
        # 근거를 좀 모은 뒤 죽은 경우 — evidence_ids 가 비지 않아도 실패는 실패다
        st = _state()
        st.subquestions[0].failed = True
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert any("하위1" in x and "오류로 확인하지 못했다" in x for x in lims)

    def test_healthy_subquestion_is_not_reported_as_failed(self):
        assert not any("오류로 확인하지 못했다" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_unmarked_sentences_are_reported(self):
        lims = build_limitations(_state(), unmarked_total=4, dropped_total=0)
        assert any("근거 표기가 없는 서술 4건" in x for x in lims)

    def test_parse_failed_subquestion_is_reported(self):
        """판정 실패는 verdict=sufficient 로 떨어지므로 따로 세지 않으면 사라진다."""
        st = _state()
        st.subquestions[0].parse_failed = True
        lims = build_limitations(st, unmarked_total=0, dropped_total=0)
        assert any("자동 점검을 완료하지 못한 하위질문이 1건" in x for x in lims)

    def test_no_parse_failure_is_not_reported(self):
        assert not any("자동 점검을 완료하지 못한" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_zero_unmarked_is_not_reported(self):
        assert not any("근거 표기가 없는" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))

    def test_single_unmarked_sentence_is_tolerated(self):
        """마커 없는 문장은 연결 문장일 때가 많아 몇 건은 넘긴다.

        없는 번호를 가리킨 표기(dropped)와 한 문장으로 합치면 이 관용이
        사라지거나, 반대로 지어낸 번호가 임계값에 묻힌다.
        """
        assert not any("근거 표기가 없는" in x
                       for x in build_limitations(_state(), unmarked_total=1, dropped_total=0))

    def test_dropped_marker_is_reported_at_one(self):
        """지어낸 근거 번호는 1건부터 보고한다 — 인용 설계가 잡으려는 실패가 이것이다."""
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=1)
        assert any("존재하지 않는 근거 번호" in x and "1건" in x for x in lims)

    def test_zero_dropped_is_not_reported(self):
        assert not any("존재하지 않는 근거 번호" in x
                       for x in build_limitations(_state(), unmarked_total=0, dropped_total=0))


class TestAssembleReport:
    def test_sections_match_subquestions(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "하위1", "intro": "도입 [E1].",
                       "papers": [{"cnts_id": "A", "summary": "요약"}],
                       "future": [{"text": "과제 [E1]."}]}],
            unmarked_total=0,
        )
        assert len(report["sections"]) == 1
        assert report["sections"][0]["papers"][0]["evidence"] == ["E1"]

    def test_paper_bullet_evidence_is_structural(self):
        """대표 논문 요약의 인용은 모델이 고르는 게 아니라 cnts_id 로 정해진다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "papers": [{"cnts_id": "A", "summary": "s"}],
                       "future": []}],
            unmarked_total=0,
        )
        assert report["sections"][0]["papers"][0]["evidence"] == ["E1"]

    def test_unknown_marker_in_intro_is_stripped(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "지어냈다 [E99].", "papers": [], "future": []}],
            unmarked_total=0,
        )
        assert "[E99]" not in report["sections"][0]["intro"]
        assert any("존재하지 않는 근거 번호" in x and "1건" in x for x in report["limitations"])

    def test_unknown_marker_in_future_is_stripped(self):
        """향후 과제도 마커 인용이다 — 도입만 세면 이쪽이 조용히 빠져나간다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "", "papers": [],
                       "future": [{"text": "과제 [E99]."}]}],
            unmarked_total=0,
        )
        assert "[E99]" not in report["sections"][0]["future"][0]["text"]
        assert any("존재하지 않는 근거 번호" in x and "1건" in x for x in report["limitations"])

    def test_dropped_markers_accumulate_across_call_sites(self):
        """bind_markers 는 섹션마다 여러 번 불린다 — 한 번의 반환값만 읽으면 과소 계수된다."""
        report = assemble_report(
            _state(),
            sections=[
                {"heading": "h1", "intro": "가 [E98].", "papers": [], "future": []},
                {"heading": "h2", "intro": "", "papers": [],
                 "future": [{"text": "나 [E99]."}]},
            ],
            unmarked_total=0,
        )
        assert any("존재하지 않는 근거 번호" in x and "2건" in x for x in report["limitations"])

    def test_same_unknown_marker_twice_counts_twice(self):
        """사용자에게 보이는 단위는 본문의 표기 수다 — 서로 다른 번호의 수가 아니다."""
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "가 [E99]. 나 [E99].",
                       "papers": [], "future": []}],
            unmarked_total=0,
        )
        assert any("존재하지 않는 근거 번호" in x and "2건" in x for x in report["limitations"])

    def test_valid_markers_are_not_reported_as_dropped(self):
        report = assemble_report(
            _state(),
            sections=[{"heading": "h", "intro": "도입 [E1].", "papers": [],
                       "future": [{"text": "과제 [E1]."}]}],
            unmarked_total=0,
        )
        assert not any("존재하지 않는 근거 번호" in x for x in report["limitations"])

    def test_evidence_is_serialized(self):
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert report["evidence"]["E1"]["chunks"][0]["page_start"] == 3
        assert report["evidence"]["E1"]["cnts_id"] == "A"

    def test_trail_comes_from_subquestions(self):
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert [t["subquestion"] for t in report["trail"]] == ["하위1", "하위2"]

    def test_corpus_range_is_carried_into_report(self):
        """수록 범위는 고정 문구가 아니라 실행 시점 실측값이다."""
        st = _state()
        st.corpus_range = {"from": "2002", "to": "2026", "n_papers": 72054}
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert report["range"]["n_papers"] == 72054

    def test_missing_corpus_range_is_none(self):
        assert assemble_report(_state(), sections=[], unmarked_total=0)["range"] is None
```

- [x] **`app/tests/test_prompts.py`** — `research_synthesize` 렌더 가드 3줄 추가(딥리서치 2종 → 3종). `StrictUndefined` 라 변수명이 어긋나면 워커 런타임에서야 터진다.

- [x] **검증** — `21 passed`, 전체 278. 되돌림 9건 확인. 특히 두 `bind_markers` 호출 지점(도입·향후 과제)을 **각각** 깨봤고 양쪽 다 테스트가 잡았다. 임계값 두 개를 서로 바꿔치기하는 되돌림(G·H)도 각각 실패해, 두 경로가 다시 합쳐지지 않는 것이 고정됐다.

---

## Task 9: 오케스트레이션과 진행 중계 — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - 머지 전 리뷰 (runner) — `explore()` 직후 `db.commit()` 으로 읽기 트랜잭션을 끝낸다(critic LLM 을 기다리는 동안 `library_catalog` 공유 잠금을 쥐면 FastAPI 기동의 `ALTER TABLE` 이 막히고 그 뒤 조회가 줄 선다 — `recurring-gotchas.md` 18번). 근거 순서를 하위질문 안 순위로(`_rank_order`, 라운드별 1위 앞자리 보장). 재사용 근거에도 그 하위질문에서 매칭된 청크를 기록(`link_chunks`). `max_evidence` 상한은 `break` 가 아니라 `continue` 로 재사용 후보를 살리고, 못 실은 수를 `capped` 로 세고, 상한에 닿으면 재검색을 멈춘다. 이미 시도한 검색어는 다시 돌지 않는다(`_next_query`). `critique` 이벤트에 `parse_failed`·`capped`. 주입 인자 타입힌트.
> - 머지 전 리뷰 (relay) — 종료 이벤트 모양을 `terminal_event` 하나로 통일(워커 발행·엔드포인트 합성이 같은 모양), `publish_terminal` 추가, publish 소켓 타임아웃 2초(무응답 Redis 가 리서치를 멈추지 않게).
>
> 구현·리뷰가 끝났다. 아래는 동기화 시점(`248b5e8`)의 저장소 파일과 일치했다.

초안과 달라진 것 둘.

**(1) `subq.parse_failed = verdict.parse_failed` 를 추가했다 — 사슬의 중간이 비어 있었다.** `critic._failed()` 가 `Verdict.parse_failed` 를 쓰고, `synthesizer.build_limitations` 가 `sq.parse_failed` 를 읽는데, **둘을 잇는 코드가 저장소 어디에도 없었다**(유일한 대입이 테스트 픽스처 한 줄). 운영에서는 항상 `False` 라 자기점검이 전부 실패해도 보고서가 "한계 없음"으로 나온다 — Task 6 리뷰가 고쳤던 실패가 한 층 위에서 되살아나 있었다.

마지막 판정이 이기게 두는 것이 맞다. 파싱 실패는 `verdict="sufficient"` 를 내고 `should_recheck` 는 `"insufficient"` 만 재검색하므로, **파싱 실패는 언제나 루프의 마지막 라운드**다. 누적 OR 이 필요 없다.

**(2) `test_cap_reached_still_links_already_adopted_paper` 를 추가했다.** 초안의 `max_evidence` 상한 분기는 `break` 가 아니라 `continue` 여야 한다 — 상한에 닿은 뒤에도 "이미 있는 근거의 재사용"이 섞여 있고 그건 총량을 늘리지 않으므로, `break` 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다. 이 이유는 주석으로 길게 적혀 있었지만 **테스트가 없었다.** 초안의 `test_max_evidence_caps_growth` 는 `len(st.evidence) == 4` 만 보므로 `break` 로도 통과한다(직접 되돌려 확인). 주석이 혼자 일하고 있었다.

그 밖에 초안 테스트 두 건을 강화했다. `subq.note` 복사와 `state.recheck_count` 증가는 커버리지가 0이었고, `emit` 페이로드의 키 이름은 **Task 10 SSE 의 전선 계약**인데 아무것도 고정하지 않고 있었다.

- [x] **`app/services/research/runner.py`**

```python
"""runner.py — 단계 오케스트레이션

각 단계는 ResearchState 를 받아 갱신한다. explore_fn·critique_fn 을 인자로
받는 이유는 Milvus·LLM 없이 루프 자체를 테스트하기 위해서다.

진행 중계도 같은 이유로 emit 인자로 주입받는다. `services.research.relay` 를
여기서 import 하면 relay 가 물고 있는 `redis` 가 이 모듈을 여는 모든 곳에
필요해지고, 미설치 환경에서는 테스트 수집 단계가 통째로 죽는다
(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
import logging

from services.research.citations import build_evidence, evidence_id
from services.research.critic import critique as _critique
from services.research.critic import should_recheck
from services.research.explorer import explore as _explore
from services.research.state import ResearchState, SubQuestion

log = logging.getLogger(__name__)


async def _noop_emit(kind: str, payload: dict) -> None:
    return None


async def explore_subquestion(
    state: ResearchState,
    subq: SubQuestion,
    *,
    db,
    explore_fn=_explore,
    critique_fn=_critique,
    emit=None,
) -> SubQuestion:
    """한 하위질문을 탐색하고, 부족하면 쿼리를 바꿔 상한까지 재탐색한다."""
    emit = emit or _noop_emit
    params = state.params
    query = subq.text
    recheck = 0

    while True:
        subq.queries.append(query)
        hits, meta = await explore_fn(query, params=params, db=db)
        await emit("search", {
            "subq_idx": subq.idx, "query": query, "found": len(hits),
        })

        # 같은 논문이 여러 하위질문에서 나오면 근거를 새로 만들지 않고 재사용한다.
        # 안 그러면 한 논문이 E3 와 E17 로 갈라져 인용칩이 같은 출처를 다른
        # 번호로 가리킨다. 번호는 state.evidence 를 소유한 이쪽이 붙인다 —
        # build_evidence 는 묶기만 하고 id 를 비워 돌려준다.
        known_by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
        for cand in build_evidence(
            hits, meta, chunks_per_evidence=params["chunks_per_evidence"],
        ):
            existing = known_by_cnts.get(cand.cnts_id)
            if existing is not None:
                if existing not in subq.evidence_ids:
                    subq.evidence_ids.append(existing)
                continue
            # break 가 아니라 continue 다. 상한에 닿은 뒤에 나오는 후보 중에도
            # "이미 있는 근거의 재사용"이 섞여 있는데, 그건 총량을 늘리지 않는다.
            # break 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다.
            if len(state.evidence) >= params["max_evidence"]:
                continue
            eid = evidence_id(len(state.evidence))
            cand.id = eid
            state.evidence[eid] = cand
            known_by_cnts[cand.cnts_id] = eid
            subq.evidence_ids.append(eid)

        verdict = await critique_fn(
            subq, [state.evidence[e] for e in subq.evidence_ids], params=params,
        )
        subq.verdict = verdict.verdict
        subq.note = verdict.note
        # 판정을 못 읽었다는 표시를 여기서 옮기지 않으면 보고서까지 닿지 않는다 —
        # synthesizer.build_limitations 는 subq.parse_failed 만 보고 "자동 점검을
        # 완료하지 못한 하위질문"을 센다. 자기점검이 전부 실패해도 보고서가
        # "한계 없음"으로 보이는 게 정확히 critic 의 parse_failed 가 막으려던 실패다.
        #
        # 마지막 라운드 값으로 덮어써도 된다(OR 누적이 필요 없다): 파싱 실패는
        # verdict="sufficient" 로 떨어지고 should_recheck 는 "insufficient" 일 때만
        # True 이므로, 파싱 실패가 난 라운드가 항상 마지막 라운드다.
        subq.parse_failed = verdict.parse_failed
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
        })

        if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"]):
            break
        if not verdict.new_queries:
            break
        query = verdict.new_queries[0]
        recheck += 1
        state.recheck_count += 1

    return subq
```

- [x] **`app/services/research/relay.py`**

`publish` 가 호출마다 클라이언트를 새로 만드는 것은 낭비가 아니라 필요다 — Celery 태스크가 `asyncio.run` 으로 루프를 새로 만들므로, 모듈 최상단 클라이언트는 첫 루프에 묶여 이후 전부 `Event loop is closed` 가 된다. (Task 10 에서 잡당 루프 1개로 바뀌었으므로 지금은 무해한 여유분이다.)

`runner.py` 가 `relay` 를 임포트하지 않고 `emit` 을 주입받는 것도 설계다. `relay` → `redis` 인데 `redis` 는 `requirements.txt` 에만 있고 로컬 venv 에 없어, 최상단 임포트가 하나라도 생기면 `pytest` 가 수집 단계에서 죽어 **세션 전체가 0건**이 된다(`recurring-gotchas.md` 13번의 `redis` 판).

```python
"""relay.py — 진행 이벤트 중계 (Redis pub/sub)

잔이벤트는 여기로만 흐르고 Postgres 에 쓰지 않는다. 카운터가 째깍거리는
것 때문에 DB를 때릴 이유가 없고, 몇 초 뒤 아무도 안 본다.
재접속하면 research_steps 로 뼈대를 복원하고 그 이후를 여기서 받는다.

이 모듈은 `redis` 를 최상단에서 물고 온다. runner 나 테스트가 이걸 최상단에서
import 하면 `redis` 미설치 환경에서 수집 단계가 통째로 죽으므로, 주입은
호출자가 emit 인자로 넘기는 방식으로만 한다(runner.explore_subquestion 참고).
"""
import json
import logging

import redis.asyncio as aioredis

from core.config import get_settings

log = logging.getLogger(__name__)


def channel(job_id: str) -> str:
    return f"research:{job_id}"


async def publish(job_id: str, kind: str, payload: dict) -> None:
    """중계 실패가 리서치를 죽이면 안 된다 — 삼키고 로그만 남긴다.

    클라이언트를 호출마다 새로 만든다. 모듈 전역에 하나 두면 첫 이벤트루프에
    묶이는데, Celery 태스크는 잡마다 `asyncio.run(...)` 으로 루프를 새로 열고
    닫으므로 두 번째 잡부터 전부 `Event loop is closed` 로 죽는다.
    한 잡에 수십 번 도는 정도라 연결 비용보다 이쪽이 싸다.
    """
    cfg = get_settings()
    try:
        client = aioredis.from_url(cfg.REDIS_URL)
        try:
            await client.publish(
                channel(job_id), json.dumps({"kind": kind, **payload}, ensure_ascii=False)
            )
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:relay] publish 실패 job=%s kind=%s: %s", job_id, kind, e)


async def subscribe(job_id: str, *, idle_timeout: float = 15.0):
    """이벤트 dict 를 yield 한다. 유휴 구간에서는 None 을 yield 한다.

    None 은 "아직 살아있다" 신호다. 엔드포인트가 이때 SSE 주석 프레임을 흘려
    끊긴 소켓을 감지하고, 잡이 이미 끝났는지도 확인한다. listen() 만 쓰면
    트래픽이 없는 동안 영원히 블록하므로 클라이언트가 조용히 끊겨도 알 방법이
    없다 — 아무것도 쓰지 않으니 broken pipe 조차 나지 않는다.
    """
    cfg = get_settings()
    client = aioredis.from_url(cfg.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel(job_id))
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=idle_timeout,
            )
            yield json.loads(message["data"]) if message else None
    finally:
        await pubsub.unsubscribe(channel(job_id))
        await pubsub.aclose()
        await client.aclose()
```

- [x] **`app/tests/test_research_runner.py`**

```python
"""test_research_runner.py — 단계 오케스트레이션

async 테스트는 `asyncio.run` 으로 돈다. `@pytest.mark.asyncio` 를 쓰면 안
된다 — `pytest-asyncio` 가 이 저장소에 설치돼 있지 않고, 플러그인이 없으면
pytest 는 코루틴을 **실행하지 않고 경고만 남긴 뒤 통과로 처리한다.** 초록불인
채로 아무것도 검증하지 않는 테스트가 되므로 관례(`test_research_explorer.py`)
를 그대로 따른다.

relay 는 모듈 최상단에서 import 하지 않는다. `redis` 는 requirements 에만
있고 로컬 venv 에는 없어서, 최상단 import 는 수집 단계에서 세션을 통째로
죽인다(`docs/ops/recurring-gotchas.md` 13번의 torch 와 같은 함정).
"""
import asyncio
import importlib
import json
import sys
from unittest.mock import MagicMock

from services.research.critic import Verdict
from services.research.runner import explore_subquestion
from services.research.state import ResearchState, SubQuestion, merge_params


class _FakeCritic:
    """항상 부족을 반환하는 critic — 루프 상한을 검증한다."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("insufficient", note="부족", new_queries=["다른 검색어"])


class _ParseFailedCritic:
    """판정을 못 읽은 critic — `critic._failed()` 가 내는 형태 그대로다."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, subq, evidence, *, params):
        self.calls += 1
        return Verdict("sufficient", note="자동 점검을 완료하지 못했다", parse_failed=True)


def _hits(cnts_ids, *, query="q"):
    hits = [
        {"book_id": cid, "chunk_id": f"{cid}-c-{query}", "text": "본문",
         "page_start": 1, "page_end": 1, "score": 0.9}
        for cid in cnts_ids
    ]
    meta = {
        cid: {"title": f"논문 {cid}", "pub_date": "2008-06", "kci_citations": 3}
        for cid in cnts_ids
    }
    return hits, meta


async def _fake_explore(query, *, params, db):
    return _hits(["A"], query=query)


async def _empty_explore(query, *, params, db):
    return [], {}


class TestExploreSubquestion:
    def test_always_insufficient_stops_at_max_recheck(self):
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="하위질문")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore, critique_fn=critic, emit=None,
        ))
        assert critic.calls == 3            # 최초 1 + 재검색 2
        assert len(sq.queries) == 3
        assert sq.verdict == "insufficient"
        assert sq.note == "부족"            # note 가 그대로 보고서의 한계 문장이 된다
        assert st.recheck_count == 2        # 잡 전체 재검색 횟수 — 탐색 경로에 실린다

    def test_no_hits_records_no_evidence(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq = SubQuestion(idx=0, text="하위질문")
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_empty_explore,
            critique_fn=_FakeCritic(), emit=None,
        ))
        assert sq.evidence_ids == []

    def test_same_paper_in_two_subquestions_reuses_one_evidence(self):
        """한 논문이 두 하위질문에서 나와도 근거는 하나다.

        중복 생성하면 같은 출처가 E1 과 E2 로 갈라져 인용칩이 어긋난다.
        """
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        assert len(st.evidence) == 1
        assert sq1.evidence_ids == sq2.evidence_ids == ["E1"]
        assert len({ev.cnts_id for ev in st.evidence.values()}) == 1

    def test_recheck_does_not_duplicate_same_paper(self):
        """재검색에서 같은 논문이 또 나와도 evidence_ids 에 두 번 들어가지 않는다."""
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.evidence_ids == ["E1"]

    def test_max_evidence_caps_growth(self):
        async def _many(query, *, params, db):
            return _hits([f"B{i}" for i in range(10)], query=query)

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 4}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None,
            explore_fn=_many, critique_fn=_FakeCritic(), emit=None,
        ))
        assert len(st.evidence) == 4

    def test_cap_reached_still_links_already_adopted_paper(self):
        """상한에 닿은 뒤 나온 후보도 '이미 있는 근거'면 링크는 붙는다.

        상한 검사를 break 로 끊으면 그 뒤 후보를 아예 보지 못하고 지나가서,
        다른 하위질문에서 이미 채택된 논문인데도 이 하위질문만 링크를 잃는다.
        재사용은 총량을 늘리지 않으므로 상한과 무관한 손실이다.
        """
        by_query = {"가": ["A"], "나": ["B", "C", "A"]}

        async def _by_query(query, *, params, db):
            return _hits(by_query[query], query=query)

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 2}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(st, sq1, db=None, explore_fn=_by_query,
                                        critique_fn=critic, emit=None))
        asyncio.run(explore_subquestion(st, sq2, db=None, explore_fn=_by_query,
                                        critique_fn=critic, emit=None))
        assert sq1.evidence_ids == ["E1"]
        assert sq2.evidence_ids == ["E2", "E1"]     # B 는 새로, C 는 상한에 막히고, A 는 재사용
        assert len(st.evidence) == 2

    def test_parse_failed_verdict_propagates_to_subquestion(self):
        """판정 파싱 실패 표시가 하위질문까지 올라와야 한다.

        `synthesizer.build_limitations` 는 `sq.parse_failed` 만 본다. 여기서
        옮기지 않으면 자기점검이 전부 실패해도 보고서가 "한계 없음"이 된다.
        """
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="가")
        critic = _ParseFailedCritic()
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                        critique_fn=critic, emit=None))
        assert sq.parse_failed is True
        # 파싱 실패는 verdict="sufficient" 로 떨어지므로 루프가 한 바퀴에 끝난다 —
        # 그래서 마지막 라운드의 값만 옮겨도 표시가 유실되지 않는다.
        assert critic.calls == 1

    def test_emit_is_called_for_progress(self):
        events = []

        async def _emit(kind, payload):
            events.append((kind, payload))

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        asyncio.run(explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None, explore_fn=_fake_explore,
            critique_fn=_FakeCritic(), emit=_emit,
        ))
        kinds = [k for k, _ in events]
        assert "search" in kinds and "critique" in kinds
        by_kind = dict(events)
        assert by_kind["search"] == {"subq_idx": 0, "query": "가", "found": 1}
        assert by_kind["critique"]["verdict"] == "insufficient"
        assert by_kind["critique"]["adopted"] == 1


def _load_relay(monkeypatch):
    """`redis` 미설치 환경에서만 더미를 꽂아 relay import 를 통과시킨다.

    더미를 물린 relay 가 sys.modules 에 남으면 뒤에 도는 테스트가 Mock 을
    물려받으므로 monkeypatch.delitem 으로 지워 둔다
    (`test_embed_index_guard.py` 와 같은 방식).
    """
    for name in ("redis", "redis.asyncio"):
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    monkeypatch.delitem(sys.modules, "services.research.relay", raising=False)
    return importlib.import_module("services.research.relay")


class _FakeRedis:
    def __init__(self, publish_error=None):
        self.published = []
        self.closed = False
        self._publish_error = publish_error

    async def publish(self, channel, data):
        if self._publish_error is not None:
            raise self._publish_error
        self.published.append((channel, data))

    async def aclose(self):
        self.closed = True


class TestRelayPublish:
    def test_publishes_kind_and_payload_to_job_channel(self, monkeypatch):
        relay = _load_relay(monkeypatch)
        client = _FakeRedis()
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)

        asyncio.run(relay.publish("job-1", "search", {"subq_idx": 0, "query": "한글"}))

        channel, data = client.published[0]
        assert channel == "research:job-1"
        assert json.loads(data) == {"kind": "search", "subq_idx": 0, "query": "한글"}
        assert "한글" in data              # ensure_ascii=False — 로그·SSE 에서 읽혀야 한다
        assert client.closed is True

    def test_publish_error_is_swallowed_and_client_closed(self, monkeypatch):
        """중계는 장식이고 보고서는 아니다 — publish 실패가 잡을 죽이면 안 된다."""
        relay = _load_relay(monkeypatch)
        client = _FakeRedis(publish_error=RuntimeError("연결 끊김"))
        monkeypatch.setattr(relay.aioredis, "from_url", lambda url: client)

        assert asyncio.run(relay.publish("job-1", "search", {})) is None
        assert client.closed is True

    def test_connect_error_is_swallowed(self, monkeypatch):
        relay = _load_relay(monkeypatch)

        def _boom(url):
            raise OSError("redis 없음")

        monkeypatch.setattr(relay.aioredis, "from_url", _boom)
        assert asyncio.run(relay.publish("job-1", "done", {})) is None
```

- [x] **검증** — `11 passed`, 전체 306. `-W error::RuntimeWarning` 으로도 306 — 어디에서도 코루틴이 await 없이 버려지지 않는다.

---

## Task 10: Celery 태스크와 API — **완료**

> **이후 변경 — 아래 코드 블록은 최종 코드가 아니다. 최종 코드는 저장소가 정본이다.**
> - 머지 전 리뷰 (워커) — 워커는 job ORM 객체에 대입하지 않고 **모든 상태 전이를 조건부 UPDATE(`_transition`)** 로 한다. 아래 블록의 `job.status = …` 대입은 API 가 찍은 `canceled` 를 덮어 취소한 잡을 `completed`·`awaiting_approval` 로 되살렸다(리뷰의 high). 종합은 절마다 취소를 확인한다. 잡 본문을 자체 데드라인 `JOB_DEADLINE = SOFT_LIMIT - 300` 으로 감싼다 — 소프트 리밋 신호는 LLM 응답을 await 하는 동안 오면 코루틴의 `except` 를 우회한다(`recurring-gotchas.md` 19번). 전멸 가드(`_wiped_out`), 하위질문 예외 시 `rollback`, 가드 밖 예외는 새 세션으로 실패 처리(`_fail_open_job`), 계획 태스크는 LLM 을 부르기 전에 읽기 트랜잭션을 닫는다. 회수 임계 `STALE_MINUTES = 45`(하드 리밋보다 길게), 회수한 잡의 running step 도 같은 문장에서 닫는다. 태스크 큐는 `queue="q_llm"` 이 아니라 설정값이다 — 실행은 `get_settings().RESEARCH_QUEUE`, 계획은 `RESEARCH_PLAN_QUEUE`(아래 설정·배포).
> - 머지 전 리뷰 (모델) — `STEP_KINDS` 에서 `critique` 를 뺐다(Task 1 이후 변경). 아래 블록의 `models/research.py` 에는 아직 있다.
> - 머지 전 리뷰 (API) — 승인·재시도·취소 모두 조건부 UPDATE. 승인 본문 선택(`ResearchApprove | None`), 수정 계획 검증(`_validated_plan`: 항목 2~300자·`max_subquestions` 이하·중복 금지). 브로커 전달 실패 시 상태를 되돌리고 503(`_enqueue`). 경로의 UUID 를 표준형으로 바꿔 구독(비표준 표기면 이벤트를 하나도 못 받았다). 종료 프레임을 `relay.terminal_event` 로 통일. 취소는 없는 잡 404·끝난 잡 409 를 가른다. `RESEARCH_QUEUE` 가 적재 큐(기본값 `q_llm`)면 approve·retry 가 실행 슬롯 1개(`approved`·`queued`·`running`)를 넘을 때 429 다(`_to_run_queue` — 트랜잭션 잠금을 잡고 센다). 실행이 적재 요약 슬롯을 쥐어 적재 아이템을 stale 복구로 밀기 때문이다(`recurring-gotchas.md` 16번).
> - 머지 전 리뷰 (설정·배포) — `celery_app` 라우팅이 `RESEARCH_QUEUE` 를 따르고, 운영 compose 에 전용 워커 `celery-research`(GPU·`/data/models/.hf-cache:/models`·`-Q q_research`·concurrency 1)와 fastapi 의 `RESEARCH_QUEUE: q_research` 가 생겼다. 반영 검수에서 계획만 `RESEARCH_PLAN_QUEUE`·경량 워커 `celery-research-plan`(`-Q q_research_plan`)으로 나눴다 — 실행 슬롯이 하나라 계획이 다른 잡의 실행 뒤에 섰다. 전환 순서는 완료노트 §5.
>
> 구현·리뷰가 끝났다. 아래는 동기화 시점(`248b5e8`)의 저장소 파일과 일치했다.

이 절의 초안은 **당일 재설계본**이라 Tasks 1~9 보다 검증이 덜 된 상태로 들어갔고, 구현 중에 재설계본 자체의 결함이 셋 나왔다. 전부 "첫 실행에서 바로" 또는 "상한에 닿았을 때" 드러나는 것들이다.

**(1) `approve` 가 `status` 를 바꾸지 않았다.** 재설계본은 `create`·`approve`·`get` 을 "초안 그대로" 쓰라고 했는데, 초안의 `approve_plan` 은 잡을 `awaiting_approval` 에 둔 채 `{"status": "running"}` 을 반환한다. `_claim(allowed=("approved","queued"))` 가 **모든 잡에서 0행을 만나 영원히 `skipped`** 가 된다. 쓰는 쪽과 읽는 쪽이 안 맞는, 이 라운드에서 반복해 잡은 바로 그 결함이다.

문자열 리터럴로 맞추지 않고 구조로 묶었다 — `models/research.py` 가 `STATUS_APPROVED`·`STATUS_QUEUED`·`RUNNABLE_STATUSES` 를 내보내고, API 가 그 이름으로 쓰고, 워커가 그 이름으로 읽는다. `test_run_claims_only_statuses_the_api_writes` 가 워커가 실제로 넘기는 튜플을 단언한다.

**(2) `SoftTimeLimitExceeded` 는 `Exception` 의 서브클래스다.** 하위질문별 `except Exception` 과 종합의 `except Exception` 이 그걸 먼저 삼켜 바깥 핸들러에 도달하지 않는다. 워커는 탐색을 계속하다 하드 리밋에 프로세스째 죽고 **상태를 아무것도 안 남긴다** — 상한을 넣은 목적이 정확히 무효화된다. 두 자리 모두 앞에 `except SoftTimeLimitExceeded: … raise` 를 세웠다.

**(3) SSE 가 이미 닫힌 세션을 쓴다.** `Depends(get_db)` 세션은 핸들러가 반환할 때 닫히는데 `StreamingResponse` 의 제너레이터는 **그 뒤에** 돈다. 하트비트마다 짧은 세션을 새로 여는 `_terminal_status()` 로 바꿨다(API 프로세스는 장수 루프이므로 여기서는 풀링 엔진이 맞다).

그 밖에 `cancelled` → `canceled` 로 통일했다 — 기존 `models/ingest_job.py` 와 `JOB_STATUSES` 가 L 하나를 쓴다. 코드가 실제다.

**재개 경로를 열었다.** `stage`/`state_snapshot` 을 넣어도 종합 실패 후 `status="failed"` 라 `_claim` 이 못 집어, 체크포인트가 또 "쓰기만 하고 안 읽는 필드"가 될 뻔했다. `POST /{job_id}/retry` 가 `failed → queued` 로 되돌리되 `stage`·`state_snapshot` 은 건드리지 않는다. `plan` 이 비어 있으면 409 — 계획 수립 단계에서 실패한 잡을 `run_deep_research` 로 재시도하면 하위질문 0개를 탐색하고 **빈 보고서를 `completed` 로 저장**하는 조용한 성공이 된다.

- [x] **`app/models/research.py`**

```python
"""research.py — 딥리서치 잡 모델

research_jobs  : 리서치 1건 (질문 1개 = 잡 1개)
research_steps : 의미 있는 단계 (계획 · 하위질문별 탐색 · 점검 · 종합)

research_steps 는 진행 패널이자 보고서의 탐색 경로 섹션이다. 초당 갱신되는
잔이벤트(카운터 등)는 여기 쓰지 않고 Redis pub/sub 으로만 흘린다 — 입자가
다르고, 보고서에 남을 것과 몇 초 뒤 사라질 것을 한 테이블에 섞으면
보존 정책과 append/update 성격이 충돌한다.
"""
import uuid

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

JOB_STATUSES = (
    "created", "planning", "awaiting_approval",
    "approved", "queued", "running",
    "completed", "failed", "canceled",
)
# status 는 "지금 무슨 상태인가", stage 는 "어디까지 끝냈는가"다. 둘을 한 컬럼으로
# 합치면 실패했을 때 어디부터 다시 할지 알 수 없다 — failed 하나로는 계획에서
# 죽었는지 종합에서 죽었는지 구분되지 않아 5~7분짜리 탐색을 매번 다시 돌게 된다.
JOB_STAGES = ("created", "planned", "explored", "synthesized")

# run_deep_research 가 선점(_claim)할 수 있는 상태. API 의 approve·retry 가 여기
# 없는 값을 써 넣으면 워커가 그 잡을 영원히 건너뛰고, stage·state_snapshot 은
# 쓰기만 하고 아무도 안 읽는 컬럼이 된다. 양쪽이 같은 상수를 보게 묶어둔다.
STATUS_APPROVED = "approved"     # 사용자가 계획을 승인해 큐에 넣었다
STATUS_QUEUED = "queued"         # 실패한 잡을 재시도로 다시 큐에 넣었다
# 철자는 canceled(l 하나) 로 통일한다 — models/ingest_job.py 의 JOB_STATUSES·
# ITEM_STATUSES 가 이미 그 철자다. 두 잡 계열이 서로 다른 철자를 쓰면 상태
# 비교가 조용히 빗나간다.
STATUS_CANCELED = "canceled"
RUNNABLE_STATUSES = (STATUS_APPROVED, STATUS_QUEUED)

STEP_KINDS = ("plan", "search", "critique", "synthesize")
STEP_STATUSES = ("pending", "running", "done", "failed")


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question    = Column(Text, nullable=False)
    status      = Column(String(24), nullable=False, default="created", index=True)
    params      = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    plan        = Column(JSONB)      # 사용자 수정이 반영된 하위질문 목록
    report      = Column(JSONB)
    stage       = Column(String(16), nullable=False, server_default=text("'created'"))
    # 탐색이 끝난 시점의 ResearchState 스냅샷. 종합만 재실행하기 위한 체크포인트다.
    # 이게 없으면 종합 LLM 이 실패할 때 5~7분짜리 탐색을 통째로 다시 돌려야 한다.
    # 읽는 쪽은 workers/research_tasks.py 의 stage == "explored" 분기이고, 그
    # 분기에 닿는 유일한 경로가 POST /api/research/{job_id}/retry 다.
    state_snapshot = Column(JSONB)
    last_error  = Column(Text)
    created_by  = Column(String(64))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    started_at  = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class ResearchStep(Base):
    __tablename__ = "research_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "seq", name="uq_research_steps_job_seq"),
        Index(
            "ix_research_steps_inflight", "updated_at",
            postgresql_where=text("status = 'running'"),
        ),
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id      = Column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq         = Column(Integer, nullable=False)
    kind        = Column(String(16), nullable=False)
    subq_idx    = Column(Integer)
    title       = Column(Text, nullable=False)
    detail      = Column(Text)
    status      = Column(String(16), nullable=False, default="pending")
    # kind 별 shape — API 가 가공 없이 프론트로 넘기고 프론트가 kind 로 분기한다.
    # plan:       {"subquestions": [...]}
    # search:     {"queries": [...], "adopted": n, "verdict": "...", "note": "..."}
    # synthesize: {"sections": n}
    # 실패 공통:   {"error": "..."}
    result      = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    updated_at  = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
```

- [x] **`app/services/research/state.py`** — `SubQuestion.failed` 와 스냅샷 왕복

`failed` 를 `evidence_ids == []` 와 구분하는 이유: 구분이 없으면 보고서가 시스템 장애를 `"'…' 에 대해서는 근거를 찾지 못했다"` 로 써서 **연구 결과처럼 읽히게** 만든다. 코퍼스에 자료가 없는 것과 우리 쪽이 터진 것은 완전히 다른 정보이고, 이 기능의 값이 "모른다고 정직하게 말하는 것"이라 장애를 발견으로 포장하면 값이 무너진다.

```python
"""state.py — 딥리서치 실행 상태

각 단계는 ResearchState 를 받아 갱신해 돌려준다. Celery·Redis·Milvus 없이
테스트되고, 나중에 다른 오케스트레이션 런타임으로 옮겨도 그대로 쓴다.
"""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import NotRequired, TypedDict

# 깊이 파라미터 — research_jobs.params 로 덮어쓴다.
# 시연 직전에 값만 바꿔 짧게 돌릴 수 있어야 하므로 하드코딩하지 않는다.
# MappingProxyType 로 감싼 이유: 워커 프로세스가 이 모듈 전역을 한 번이라도
# 실수로 mutate 하면 그 오염이 프로세스 수명 내내 남는다.
DEFAULT_PARAMS: MappingProxyType[str, int | float] = MappingProxyType({
    "max_subquestions": 6,
    "max_recheck": 3,
    "max_evidence": 60,
    "per_subq_top_k": 12,
    "chunks_per_evidence": 2,
    "citation_weight": 0.2,
    "min_evidence_per_subq": 5,
})

# (타입, 하한, 상한). ResearchCreate.params: dict 가 값 타입을 검증하지
# 않으므로 여기가 유일한 검증 지점이다 — 상한이 없으면 per_subq_top_k 같은
# 값이 그대로 Milvus AnnSearchRequest(limit=...) 까지 흘러가 요청 하나로
# 워커를 묶는 자해 경로가 된다. 상한은 시연 현실치 기준.
_PARAM_BOUNDS: dict[str, tuple[type, int | float, int | float | None]] = {
    "max_subquestions": (int, 1, 12),
    "max_recheck": (int, 0, 10),
    "max_evidence": (int, 1, 200),
    "per_subq_top_k": (int, 1, 50),
    "chunks_per_evidence": (int, 1, 5),
    "citation_weight": (float, 0.0, 1.0),
    "min_evidence_per_subq": (int, 0, 50),
}


def merge_params(override: dict | None) -> dict:
    """기본값에 override 를 얹는다. 모르는 키·타입·범위를 벗어난 값은 거부한다."""
    merged = dict(DEFAULT_PARAMS)
    for key, value in (override or {}).items():
        if key not in DEFAULT_PARAMS:
            raise ValueError(f"알 수 없는 파라미터: {key}")
        _validate_param(key, value)
        merged[key] = value
    return merged


def _validate_param(key: str, value: object) -> None:
    expected_type, lo, hi = _PARAM_BOUNDS[key]
    # bool 은 int 의 서브클래스라 isinstance(value, int) 를 그냥 쓰면 True 가 통과해버린다.
    if isinstance(value, bool):
        raise ValueError(f"파라미터 {key} 에 bool 값은 쓸 수 없다: {value!r}")
    if expected_type is int and not isinstance(value, int):
        raise ValueError(f"파라미터 {key} 는 int 여야 한다: {value!r}")
    if expected_type is float and not isinstance(value, (int, float)):
        raise ValueError(f"파라미터 {key} 는 float 여야 한다: {value!r}")
    if value < lo or (hi is not None and value > hi):
        raise ValueError(f"파라미터 {key} 가 허용 범위({lo}~{hi})를 벗어났다: {value!r}")


class HitRow(TypedDict):
    """검색 결과 1건 — Milvus 검색 계층(explore)이 만들어 citations.build_evidence 로 넘긴다.

    score 와 rank_score 를 나눈 이유: 순위용 혼합값은 1.0 을 넘을 수 있어
    유사도로 표시하면 141% 같은 값이 나간다. score 는 생값 그대로 두고 순위는
    rank_score 로만 매긴다(explorer.rank_hits).
    """
    book_id: str
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float                      # 리랭킹(없으면 RRF) 생값 — 화면에 유사도로 나간다
    rank_score: NotRequired[float]    # 피인용을 얹은 정렬용 값 — rank_hits 가 채운다


@dataclass
class Chunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float


@dataclass
class Evidence:
    id: str                      # "E12" — 보고서 안에서만 유효한 지역 ID
    cnts_id: str
    meta: dict                   # 제목·저자·학술지·권호·연월·피인용·등재구분
    chunks: list[Chunk] = field(default_factory=list)


VERDICTS = ("pending", "sufficient", "insufficient")
# LLM 이 낼 수 있는 판정 — pending 은 초기상태 전용이라 제외.
# VERDICTS[1:] 로 쓰면 순서만 바뀌어도 sufficient 가 빠져 모든 정상 판정이
# "알 수 없는 verdict" 로 떨어진다.
LLM_VERDICTS = tuple(v for v in VERDICTS if v != "pending")


@dataclass
class SubQuestion:
    idx: int
    text: str
    queries: list[str] = field(default_factory=list)   # 시도한 검색어 (재검색 이력)
    evidence_ids: list[str] = field(default_factory=list)
    verdict: str = "pending"
    parse_failed: bool = False          # 판정을 못 읽어 점검이 사실상 건너뛰어진 경우
    # 탐색이 예외로 중단됨 — "근거 없음"(연구 결과)과 구분한다. 구분이 없으면
    # 보고서가 시스템 장애를 "…에 대해서는 근거를 찾지 못했다"로 써서, 우리 쪽이
    # 터진 것을 코퍼스에 자료가 없는 것처럼 보이게 만든다.
    failed: bool = False
    note: str = ""                                      # 자기점검 판단 근거


@dataclass
class ResearchState:
    job_id: str
    question: str
    params: dict
    subquestions: list[SubQuestion] = field(default_factory=list)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    recheck_count: int = 0
    # 실행 시점의 수록 범위 — 코퍼스가 계속 자라므로 보고서에 고정 문구로
    # 박지 않고 매번 질의해 넣는다. {"from": "2002", "to": "2026", "n_papers": 72054}
    corpus_range: dict | None = None
    # 보고서는 여기에 두지 않는다. synthesize() 가 반환값으로 넘기고 Celery
    # 태스크가 research_jobs.report 에 바로 쓴다. 항상 None 인 report 필드를
    # 남겨두면 화면을 붙이는 쪽이 그걸 집어들고 조용히 빈 보고서를 그린다.


def snapshot_state(state: ResearchState) -> dict:
    """탐색이 끝난 상태를 JSONB 에 넣을 수 있는 형태로 만든다.

    recheck_count 는 담지 않는다. 재탐색 상한을 세는 값이고 탐색이 끝난 뒤에는
    읽는 쪽이 없다 — 복원해 봐야 쓰이지 않는 값을 스냅샷에 넣지 않는다.
    """
    return {
        "question": state.question,
        "params": state.params,
        "corpus_range": state.corpus_range,
        "subquestions": [
            {"idx": s.idx, "text": s.text, "queries": s.queries,
             "evidence_ids": s.evidence_ids, "verdict": s.verdict,
             "parse_failed": s.parse_failed, "failed": s.failed, "note": s.note}
            for s in state.subquestions
        ],
        "evidence": {
            eid: {
                "cnts_id": ev.cnts_id, "meta": ev.meta,
                "chunks": [
                    {"chunk_id": c.chunk_id, "text": c.text,
                     "page_start": c.page_start, "page_end": c.page_end, "score": c.score}
                    for c in ev.chunks
                ],
            }
            for eid, ev in state.evidence.items()
        },
    }


def restore_state(job_id: str, snap: dict) -> ResearchState:
    """snapshot_state 의 역. 종합 단계부터 재개할 때 쓴다.

    parse_failed·failed 가 왕복에서 떨어지면 재개한 잡의 한계 섹션이 조용히
    비고, 보고서가 "한계 없음"으로 보인다 — Task 6·8·9 에서 세 번 고친 실패다.
    """
    st = ResearchState(
        job_id=job_id, question=snap["question"], params=snap["params"],
        corpus_range=snap.get("corpus_range"),
    )
    st.subquestions = [SubQuestion(**sq) for sq in snap["subquestions"]]
    st.evidence = {
        eid: Evidence(
            id=eid, cnts_id=e["cnts_id"], meta=e["meta"],
            chunks=[Chunk(**c) for c in e["chunks"]],
        )
        for eid, e in snap["evidence"].items()
    }
    return st
```

- [x] **`app/workers/research_tasks.py`**

```python
"""research_tasks.py — 딥리서치 Celery 태스크

동기 워커에서 async 파이프라인을 돌린다. 이 파일이 이 코드베이스에서 워커가
async 코드를 부르는 첫 자리다(`app/workers/` 에 기존 asyncio 사용 0건). 그래서
루프와 세션을 다루는 규칙을 여기서 못박아 둔다 — 아래 _job_engine 주석.
"""
import asyncio
import datetime as _dt
import logging
import uuid

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, text as sa_text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.research import (
    JOB_STAGES, RUNNABLE_STATUSES, STATUS_CANCELED, STEP_KINDS,
    ResearchJob, ResearchStep,
)
from services.research.relay import publish
from services.research.runner import explore_subquestion
from services.research.state import (
    ResearchState, SubQuestion, merge_params, restore_state, snapshot_state,
)
from services.research.synthesizer import synthesize
from workers.celery_app import celery_app

log = logging.getLogger(__name__)

# 5~7분이 설계값이고 종합까지 10분을 안 넘긴다. 30분이면 멈춘 것이다.
# 상한이 없으면 응답 없는 LLM 호출 하나가 q_llm 워커를 영구 점유한다.
SOFT_LIMIT = 1800
HARD_LIMIT = 2100

STALE_MINUTES = 30


def _job_engine():
    """잡 하나짜리 async 엔진.

    db/postgres.py 의 AsyncSessionLocal 을 쓰면 안 된다. 그건 pool_size=10 인
    풀링 엔진이고 FastAPI 의 장수 루프 하나를 전제한다. Celery 는 잡마다
    asyncio.run 으로 루프를 새로 만들고 닫는데, 풀은 닫힌 루프에 묶인
    asyncpg 커넥션을 그대로 들고 있다가 다음 잡에 건네준다 →
    "attached to a different loop". 첫 잡은 성공하므로 리허설을 통과한다.

    NullPool 대신 잡 단위 엔진을 쓰는 이유: 잡 안에서는 루프가 하나뿐이라
    풀이 안전하고, 5~7분 동안 수십 번 질의하는데 매번 새로 접속할 이유가 없다.
    끝에 dispose() 로 루프가 죽기 전에 커넥션을 정리한다.
    """
    cfg = get_settings()
    engine = create_async_engine(
        cfg.DATABASE_URL, pool_size=5, max_overflow=0, pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _job_uuid(job_id: str) -> uuid.UUID:
    """Celery 는 job_id 를 문자열로만 실어 나른다 — PK 타입으로 되돌린다.

    research_jobs.id 는 UUID(as_uuid=True) 라 문자열을 그대로 넘기면 identity
    map 키가 str 과 UUID 로 갈려 같은 잡을 두 객체로 들고 있게 되고, 드라이버
    쪽 변환에 기대는 부분도 생긴다. app/api 에도 UUID PK 선례가 없으므로
    여기서 규칙을 정한다 — 경계에서 한 번 변환하고 안쪽은 UUID 만 쓴다.
    """
    return uuid.UUID(str(job_id))


def _set_stage(job: ResearchJob, stage: str) -> None:
    """JOB_STAGES 를 실제로 강제하는 유일한 지점.

    stage 오타는 재개 분기(stage == "explored")를 조용히 빗나가게 만든다 —
    예외도 안 나고 그냥 탐색을 처음부터 다시 돌 뿐이라 알아채기 어렵다.
    """
    assert stage in JOB_STAGES, f"알 수 없는 stage: {stage}"
    job.stage = stage


async def _next_seq(db: AsyncSession, job_id: uuid.UUID) -> int:
    """이어붙일 seq. 1 부터 다시 시작하면 uq_research_steps_job_seq 를 위반한다.

    재시도·재개는 정상 경로다(워커 사망 복구, 종합만 재실행). 그때마다
    IntegrityError 로 죽으면 복구 기능 자체가 동작하지 않는다.
    """
    row = await db.execute(sa_text(
        "SELECT coalesce(max(seq), -1) + 1 FROM research_steps WHERE job_id = :j"
    ), {"j": job_id})
    return int(row.scalar_one())


async def _step(db: AsyncSession, job_id, seq, kind, title, *, subq_idx=None, detail=None):
    # STEP_KINDS 를 실제로 강제하는 유일한 지점. 상수만 정의하고 아무 데서도
    # 쓰지 않으면 장식이 되고, 오타난 kind 가 프론트 분기를 조용히 빗나간다.
    assert kind in STEP_KINDS, f"알 수 없는 kind: {kind}"
    row = ResearchStep(
        job_id=job_id, seq=seq, kind=kind, title=title,
        subq_idx=subq_idx, detail=detail, status="running",
    )
    db.add(row)
    await db.commit()
    return row


async def _finish(db: AsyncSession, row, status, result=None):
    row.status = status
    row.result = result or {}
    row.finished_at = _dt.datetime.now(_dt.timezone.utc)
    await db.commit()


async def _corpus_range(db: AsyncSession) -> dict:
    """실행 시점의 논문 수록 범위.

    인덱싱이 계속 도는 중이라 범위가 매주 달라진다. 보고서에 "2002~2009"
    같은 고정 문구를 박으면 곧 거짓말이 된다 — 매 실행마다 잰다.
    """
    row = (await db.execute(sa_text(
        "SELECT min(substring(pub_date, 1, 4)), max(substring(pub_date, 1, 4)), count(*) "
        "FROM library_catalog WHERE doc_type = 'paper' AND is_embedded"
    ))).first()
    return {"from": row[0], "to": row[1], "n_papers": row[2]}


async def _claim(db: AsyncSession, job_id, *, allowed: tuple[str, ...], to: str) -> bool:
    """조건부 선점. 못 잡으면 False.

    Celery 는 at-least-once 다 — 워커가 ack 전에 죽으면 같은 잡이 다시 배달된다.
    무조건 status="running" 을 대입하면 그때 같은 잡이 두 벌 돌아 step 이 중복되고
    LLM 비용이 두 배가 되며, 두 실행이 같은 job 행을 서로 덮어쓴다.
    """
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == job_id, ResearchJob.status.in_(allowed))
        .values(status=to, started_at=_dt.datetime.now(_dt.timezone.utc))
    )
    await db.commit()
    return res.rowcount == 1


async def _is_cancelled(db: AsyncSession, job_id) -> bool:
    """취소 여부를 DB 에서 다시 읽는다 — 취소는 API 프로세스에서 찍힌다."""
    await db.commit()          # 열린 트랜잭션의 스냅샷을 버려야 남의 커밋이 보인다
    res = await db.execute(select(ResearchJob.status).where(ResearchJob.id == job_id))
    return res.scalar_one_or_none() == STATUS_CANCELED


@celery_app.task(name="tasks.plan_deep_research", queue="q_llm",
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def plan_deep_research(job_id: str) -> dict:
    """계획만 세우고 승인 대기 상태로 멈춘다. 잡 전체를 이벤트 루프 하나로 돈다."""
    return asyncio.run(_plan_deep_research(job_id))


async def _plan_deep_research(job_id: str) -> dict:
    from services.research.planner import make_plan

    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            job = await db.get(ResearchJob, jid)
            if job is None:
                return {"error": "job not found", "job_id": job_id}

            if not await _claim(db, jid, allowed=("created",), to="planning"):
                log.warning("[research] 이미 계획 중이거나 계획된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            await db.refresh(job)
            seq = await _next_seq(db, jid)
            row = await _step(db, jid, seq, "plan", "연구 계획 수립",
                              detail="질문을 하위질문으로 분해하는 중입니다")
            try:
                params = merge_params(job.params or {})
                plan = await make_plan(job.question, params=params)
                job.plan = plan
                _set_stage(job, "planned")
                job.status = "awaiting_approval"
                await _finish(db, row, "done", {"subquestions": plan})
            except SoftTimeLimitExceeded:
                await _finish(db, row, "failed", {"error": "시간 상한 초과"})
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                job.status = "failed"
                job.last_error = str(e)[:1000]
                await _finish(db, row, "failed", {"error": str(e)[:500]})
            await db.commit()
            return {"job_id": str(jid), "status": job.status}

    except SoftTimeLimitExceeded:
        return await _mark_timed_out(Session, jid)
    finally:
        await engine.dispose()


@celery_app.task(name="tasks.run_deep_research", queue="q_llm",
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def run_deep_research(job_id: str) -> dict:
    """동기 Celery 진입점. 잡 전체를 이벤트 루프 하나로 돌린다.

    단계마다 asyncio.run 을 부르지 않는 이유는 _job_engine 주석에 있다.
    """
    return asyncio.run(_run_deep_research(job_id))


async def _run_deep_research(job_id: str) -> dict:
    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            job = await db.get(ResearchJob, jid)
            if job is None:
                return {"error": "job not found", "job_id": job_id}

            # 재개 가능한 상태만 받는다. running 인 잡을 다시 받으면 재배달이다.
            if not await _claim(db, jid, allowed=RUNNABLE_STATUSES, to="running"):
                log.warning("[research] 이미 처리 중이거나 처리된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            await db.refresh(job)
            seq = await _next_seq(db, jid)

            async def _emit(kind, payload):
                await publish(str(jid), kind, payload)

            # ── 탐색: stage 가 이미 explored 면 건너뛰고 스냅샷을 되살린다 ──
            if job.stage == "explored" and job.state_snapshot:
                state = restore_state(str(jid), job.state_snapshot)
                log.info("[research] 탐색 건너뜀 — 스냅샷에서 재개 job=%s", job_id)
            else:
                state = ResearchState(
                    job_id=str(jid), question=job.question,
                    params=merge_params(job.params or {}),
                )
                state.subquestions = [
                    SubQuestion(idx=i, text=t) for i, t in enumerate(job.plan or [])
                ]
                state.corpus_range = await _corpus_range(db)

                for subq in state.subquestions:
                    if await _is_cancelled(db, jid):
                        # 이벤트 kind 도 상태와 같은 철자를 쓴다 — api/research.py 의
                        # TERMINAL_KINDS 가 이 값으로 스트림을 끊는다.
                        await _emit(STATUS_CANCELED, {})
                        return {"job_id": job_id, "status": STATUS_CANCELED}

                    row = await _step(db, jid, seq, "search", subq.text,
                                      subq_idx=subq.idx,
                                      detail=f"'{subq.text}' 관련 논문을 찾기 위해 검색 중입니다")
                    seq += 1
                    try:
                        await explore_subquestion(state, subq, db=db, emit=_emit)
                        await _finish(db, row, "done", {
                            "queries": subq.queries, "adopted": len(subq.evidence_ids),
                            "verdict": subq.verdict, "note": subq.note,
                            "parse_failed": subq.parse_failed,
                        })
                    except SoftTimeLimitExceeded:
                        # 아래 except Exception 보다 먼저 와야 한다. SoftTimeLimitExceeded
                        # 도 Exception 이라 거기서 삼키면 남은 하위질문을 계속 돌다가
                        # 하드 리밋에 프로세스째 죽고, 잡은 running 에 묶여 흔적도 안 남는다.
                        await _finish(db, row, "failed", {"error": "시간 상한 초과"})
                        raise
                    except Exception as e:
                        # 부분 실패는 전체 실패가 아니다 — 나머지 하위질문은 계속한다.
                        # 다만 failed 를 남겨야 보고서가 이걸 "근거 없음"(연구 결과)이
                        # 아니라 "오류로 확인 못함"(시스템 장애)으로 쓴다.
                        log.exception("[research] 하위질문 실패 job=%s idx=%s", jid, subq.idx)
                        subq.failed = True
                        await _finish(db, row, "failed", {"error": str(e)[:500]})

                # 체크포인트. 여기까지가 비싼 구간이고, 종합은 다시 돌려도 싸다.
                _set_stage(job, "explored")
                job.state_snapshot = snapshot_state(state)
                await db.commit()

            # ── 종합 ──
            row = await _step(db, jid, seq, "synthesize", "보고서 종합")
            try:
                report = await synthesize(state)
                job.report = report
                _set_stage(job, "synthesized")
                job.status = "completed"
                await _finish(db, row, "done", {"sections": len(report["sections"])})
                await _emit("done", {"status": "completed"})
            except SoftTimeLimitExceeded:
                await _finish(db, row, "failed", {"error": "시간 상한 초과"})
                raise
            except Exception as e:
                # stage 는 explored 로 남는다 → 재시도가 탐색을 건너뛰고 여기부터 온다.
                # 그 재시도를 거는 곳이 POST /api/research/{job_id}/retry 다.
                log.exception("[research] 종합 실패 job=%s", jid)
                job.status = "failed"
                job.last_error = str(e)[:1000]
                await _finish(db, row, "failed", {"error": str(e)[:500]})
                await _emit("failed", {"error": str(e)[:200]})

            job.finished_at = _dt.datetime.now(_dt.timezone.utc)
            await db.commit()
            return {"job_id": str(jid), "status": job.status}

    except SoftTimeLimitExceeded:
        return await _mark_timed_out(Session, jid)
    finally:
        # 루프가 죽기 전에 커넥션을 닫는다. 빠뜨리면 다음 잡이 남은 커넥션을 만난다.
        await engine.dispose()


async def _mark_timed_out(Session, jid: uuid.UUID) -> dict:
    """하드 리밋에 죽으면 상태를 못 남긴다. 소프트에서 잡아 흔적을 남긴다.

    stage 는 건드리지 않는다 — 탐색까지 끝낸 뒤 종합에서 시간을 넘긴 잡은
    재시도가 스냅샷에서 이어받을 수 있어야 한다.
    """
    log.error("[research] 시간 상한 초과 job=%s", jid)
    async with Session() as db:
        await db.execute(
            update(ResearchJob).where(ResearchJob.id == jid).values(
                status="failed", last_error="시간 상한 초과 — 워커를 회수했다",
                finished_at=_dt.datetime.now(_dt.timezone.utc),
            )
        )
        await db.commit()
    return {"job_id": str(jid), "status": "failed"}


@celery_app.task(name="tasks.reap_stale_research", queue="q_control")
def reap_stale_research() -> dict:
    """멈춰버린 리서치를 실패로 떨어뜨린다.

    딥리서치는 한 번에 5~7분이고 종합이 길어도 10분을 안 넘는다.
    30분 넘게 running 이면 워커가 죽은 것이다.

    approved·queued 는 회수하지 않는다 — 아직 워커가 집지 않은 정상 대기 상태다.
    """
    db = SyncSessionLocal()
    try:
        steps = db.execute(sa_text(
            "UPDATE research_steps SET status = 'failed', "
            "       result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "       finished_at = now() "
            "WHERE status = 'running' "
            "  AND updated_at < now() - make_interval(mins => :m) "
            "RETURNING job_id"
        ), {"m": STALE_MINUTES}).fetchall()

        # coalesce 가 필요한 이유: started_at 은 선점 시점에 찍힌다. planning 단계에서
        # 워커가 죽으면 started_at 이 NULL 이고, NULL 비교는 NULL 이라 조건이 참이
        # 되지 않아 그 잡은 영원히 회수되지 않는다.
        jobs = db.execute(sa_text(
            "UPDATE research_jobs SET status = 'failed', "
            "       last_error = 'stale — 워커 응답 없음', finished_at = now() "
            "WHERE status IN ('planning', 'running') "
            "  AND coalesce(started_at, created_at) < now() - make_interval(mins => :m) "
            "RETURNING id"
        ), {"m": STALE_MINUTES}).fetchall()

        db.commit()
        return {"steps": len(steps), "jobs": len(jobs)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

- [x] **`app/api/research.py`**

```python
"""research.py — 딥리서치 API

실행은 Celery 가 맡고 진행은 SSE 로 중계한다. 탭을 닫아도 워커는 계속 돌고,
다시 열면 research_steps 로 지금까지를 복원한 뒤 이어서 받는다.

상태 전이:
    created ─plan─→ planning ─→ awaiting_approval ─approve─→ approved
    approved ─run─→ running ─→ completed | failed
    failed ─retry─→ queued ─run─→ running (stage=explored 면 종합부터)
    (거의 모든 상태) ─cancel─→ canceled
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from db.postgres import AsyncSessionLocal
from models.research import (
    STATUS_APPROVED, STATUS_CANCELED, STATUS_QUEUED, ResearchJob, ResearchStep,
)
from services.research.relay import subscribe
from services.research.state import merge_params

router = APIRouter(prefix="/api/research", tags=["research"])

# 중계를 끊어야 하는 이벤트 / 이미 끝난 잡의 상태.
# 이벤트 kind 도 상태와 같은 철자(canceled)를 쓴다 — 두 철자가 섞이면
# 프론트 분기가 조용히 빗나간다.
TERMINAL_KINDS = ("done", "failed", STATUS_CANCELED)
TERMINAL_STATUSES = ("completed", "failed", STATUS_CANCELED)

# 취소를 받아주는 상태. completed·failed·canceled 는 이미 끝난 잡이라 409 다.
CANCELLABLE_STATUSES = (
    "created", "planning", "awaiting_approval",
    STATUS_APPROVED, STATUS_QUEUED, "running",
)


class ResearchCreate(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    params: dict = Field(default_factory=dict)


class ResearchApprove(BaseModel):
    plan: list[str] | None = None      # 사용자가 수정한 계획. 없으면 제안대로.


def _job_uuid(job_id: str) -> uuid.UUID:
    """경로 파라미터를 PK 타입으로 바꾼다. 형식이 틀리면 422 — 500 이 아니다."""
    try:
        return uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="job_id 형식이 올바르지 않습니다")


async def _get_job(db: AsyncSession, job_id: str) -> ResearchJob:
    job = await db.get(ResearchJob, _job_uuid(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("")
async def create_research(req: ResearchCreate, db: AsyncSession = Depends(get_db)):
    try:
        params = merge_params(req.params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    job = ResearchJob(id=uuid.uuid4(), question=req.question, params=params)
    db.add(job)
    await db.commit()

    from workers.celery_app import celery_app
    celery_app.send_task("tasks.plan_deep_research", args=[str(job.id)])
    return {"job_id": str(job.id), "status": "created"}


@router.post("/{job_id}/approve")
async def approve_plan(
    job_id: str, req: ResearchApprove, db: AsyncSession = Depends(get_db),
):
    """계획을 확정하고 실행 큐에 넣는다.

    status 를 STATUS_APPROVED 로 바꾸는 것이 핵심이다. 상태를 그대로 두고
    태스크만 던지면 워커의 _claim(allowed=RUNNABLE_STATUSES) 이 0행을 잡아
    잡이 영원히 skipped 로 떨어진다 — 그래서 양쪽이 같은 상수를 본다.
    """
    job = await _get_job(db, job_id)
    if job.status != "awaiting_approval":
        raise HTTPException(
            status_code=409, detail=f"승인할 수 없는 상태다: {job.status}",
        )
    if req.plan is not None:
        if not req.plan:
            raise HTTPException(status_code=422, detail="계획이 비어 있다")
        job.plan = req.plan
    job.status = STATUS_APPROVED
    await db.commit()

    from workers.celery_app import celery_app
    celery_app.send_task("tasks.run_deep_research", args=[str(job.id)])
    return {"job_id": job_id, "status": job.status, "plan": job.plan}


@router.post("/{job_id}/retry")
async def retry_research(job_id: str, db: AsyncSession = Depends(get_db)):
    """실패한 잡을 다시 큐에 넣는다. **체크포인트에 닿는 유일한 경로다.**

    종합이 실패하면 워커는 status="failed" 로 두고 stage="explored" 와
    state_snapshot 을 남긴다. 그런데 _claim 은 approved·queued 만 받으므로
    failed 인 잡은 아무도 다시 집을 수 없다 — 이 엔드포인트가 없으면
    stage·state_snapshot 은 쓰기만 하고 아무도 안 읽는 컬럼이 되고,
    5~7분짜리 탐색을 지켜둔 의미가 사라진다.

    stage 와 state_snapshot 을 건드리지 않는 것이 이 엔드포인트의 전부다.
    둘을 초기화하면 재시도가 탐색부터 다시 돌아 체크포인트가 무의미해진다.

    계획 단계에서 실패한 잡(plan 이 비어 있음)은 받지 않는다. 그대로
    run_deep_research 에 넘기면 하위질문 0개로 탐색이 끝나고 빈 보고서를
    completed 로 저장한다 — 실패보다 나쁜 조용한 성공이다.
    """
    job = await _get_job(db, job_id)
    if job.status != "failed":
        raise HTTPException(
            status_code=409, detail=f"재시도할 수 없는 상태다: {job.status}",
        )
    if not job.plan:
        raise HTTPException(
            status_code=409, detail="계획이 없는 잡은 재시도할 수 없다 — 새 잡을 만든다",
        )

    job.status = STATUS_QUEUED
    job.last_error = None
    job.finished_at = None      # 큐에 들어간 잡이 종료시각을 들고 있으면 안 된다
    await db.commit()

    from workers.celery_app import celery_app
    celery_app.send_task("tasks.run_deep_research", args=[str(job.id)])
    return {"job_id": job_id, "status": job.status, "stage": job.stage}


@router.post("/{job_id}/cancel")
async def cancel_research(job_id: str, db: AsyncSession = Depends(get_db)):
    """탐색은 하위질문 경계에서 멈춘다 — 진행 중인 LLM 호출을 중간에 끊지는 않는다.

    5~7분짜리 GPU 작업을 멈출 방법이 없으면, 창을 닫은 사용자의 잡이 공유
    GPU 를 계속 먹는다. 시연 중에 이게 겹치면 다른 기능까지 느려진다.
    """
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == _job_uuid(job_id),
               ResearchJob.status.in_(CANCELLABLE_STATUSES))
        .values(status=STATUS_CANCELED, finished_at=func.now())
    )
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태입니다")
    return {"job_id": job_id, "status": STATUS_CANCELED}


@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, job_id)
    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    return {
        "job_id": job_id, "question": job.question, "status": job.status,
        "stage": job.stage, "plan": job.plan, "report": job.report,
        "last_error": job.last_error,
        "steps": [
            {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "title": s.title,
             "detail": s.detail, "status": s.status, "result": s.result}
            for s in rows
        ],
    }


@router.get("/{job_id}/stream")
async def stream_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, job_id)

    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    snapshot = [
        {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx,
         "title": s.title, "detail": s.detail, "status": s.status}
        for s in rows
    ]
    # 제너레이터는 요청 세션이 닫힌 뒤에 돈다 — ORM 객체를 들고 가지 않고
    # 필요한 값만 미리 꺼내 둔다.
    job_uuid = job.id
    job_status = job.status

    async def _gen():
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield f"data: {json.dumps({'kind': 'snapshot', 'steps': snapshot}, ensure_ascii=False)}\n\n"
        if job_status in TERMINAL_STATUSES:
            # 끝난 잡에 붙었다면 중계할 것이 없다. 구독하면 영원히 기다린다.
            yield f"data: {json.dumps({'kind': 'done', 'status': job_status}, ensure_ascii=False)}\n\n"
            return
        async for event in subscribe(job_id):
            if event is None:
                # 하트비트. 끊긴 소켓은 여기서 드러난다. 그리고 종료 이벤트를
                # 놓친 채 붙어 있는 경우를 대비해 상태를 한 번 더 확인한다.
                yield ": ping\n\n"
                st = await _terminal_status(job_uuid)
                if st is not None:
                    yield f"data: {json.dumps({'kind': 'done', 'status': st}, ensure_ascii=False)}\n\n"
                    return
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("kind") in TERMINAL_KINDS:
                return

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _terminal_status(job_uuid: uuid.UUID) -> str | None:
    """하트비트마다 짧은 세션을 새로 연다 — Depends(get_db) 세션을 쓰지 않는다.

    FastAPI 는 핸들러가 반환하면 yield 의존성을 닫는다. StreamingResponse 의
    제너레이터는 그 뒤에 도는데, 닫힌 세션을 계속 쓰면 유휴 SSE 하나가
    커넥션을 몇 분씩 쥐고 있게 되고 수명도 요청 수명을 벗어난다. 여기는
    FastAPI 의 장수 루프 안이라 풀링 엔진(AsyncSessionLocal)이 맞다.
    """
    async with AsyncSessionLocal() as db:
        st = (await db.execute(
            select(ResearchJob.status).where(ResearchJob.id == job_uuid)
        )).scalar_one_or_none()
    return st if st in TERMINAL_STATUSES else None
```

- [x] **`app/tests/test_research_tasks.py`**

```python
"""test_research_tasks.py — 딥리서치 Celery 태스크

`workers.research_tasks` 는 celery(태스크 데코레이터)와 redis(relay) 를 물고
온다. 둘 다 로컬 venv 에 없어서 최상단에서 import 하면 pytest 가 **collection
단계에서** 죽고 세션 전체가 0건이 된다(`docs/ops/recurring-gotchas.md` 13번).
그래서 미설치일 때만 더미를 꽂고 함수 안에서 import 한다
(test_embed_index_guard.py·test_search_chunk_answer_flag.py 와 같은 방식).

DB 는 대역으로 세운다. 여기서 확인하려는 것은 SQL 이 아니라 **분기**다 —
stage="explored" 로 다시 들어온 잡이 탐색을 건너뛰고 종합부터 가는가.
"""
import asyncio
import importlib
import sys
import types
import uuid
from unittest.mock import MagicMock

from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, snapshot_state,
)

_CACHED = ("workers.research_tasks", "workers.celery_app", "services.research.relay")


class _SoftTimeLimitExceeded(Exception):
    """celery 미설치 환경용 대역. MagicMock 을 except 절에 쓰면 TypeError 가 난다."""


def _stub_missing(monkeypatch, name: str, module=None) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, module or MagicMock())


def _load_tasks(monkeypatch):
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.SoftTimeLimitExceeded = _SoftTimeLimitExceeded
    _stub_missing(monkeypatch, "celery")
    _stub_missing(monkeypatch, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "redis")
    _stub_missing(monkeypatch, "redis.asyncio")
    # 더미를 문 채 sys.modules 에 남으면 뒤에 도는 테스트가 Mock 을 물려받는다.
    for mod in _CACHED:
        monkeypatch.delitem(sys.modules, mod, raising=False)
    return importlib.import_module("workers.research_tasks")


# ── DB 대역 ────────────────────────────────────────────────────────────
class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeSession:
    """execute 를 기록하고 정해진 값을 돌려주는 async 세션 대역."""

    def __init__(self, *, job=None, scalar=None):
        self.job = job
        self.scalar = scalar
        self.sql: list[str] = []
        self.params: list[dict] = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt, params=None):
        self.sql.append(str(stmt))
        self.params.append(params)
        return _Result(self.scalar)

    async def get(self, model, pk):
        return self.job

    async def refresh(self, obj):
        return None

    async def commit(self):
        self.commits += 1

    def add(self, obj):
        return None


class _FakeEngine:
    def __init__(self):
        self.disposed = 0

    async def dispose(self):
        self.disposed += 1


class _FakeJob:
    """ResearchJob 대역 — 태스크가 실제로 읽고 쓰는 필드만 가진다."""

    def __init__(self, *, stage, plan, state_snapshot=None):
        self.id = uuid.uuid4()
        self.question = "독서 격차 연구는 어디까지 왔나"
        self.params = {}
        self.plan = plan
        self.stage = stage
        self.state_snapshot = state_snapshot
        self.status = "running"
        self.report = None
        self.last_error = None
        self.finished_at = None


def _explored_snapshot() -> dict:
    st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
    st.subquestions = [
        SubQuestion(idx=0, text="스냅샷 하위1", queries=["q1"], evidence_ids=["E0"],
                    verdict="sufficient", note="충분"),
        SubQuestion(idx=1, text="스냅샷 하위2", failed=True),
    ]
    st.evidence = {
        "E0": Evidence(id="E0", cnts_id="A", meta={"title": "논문 가"},
                       chunks=[Chunk("c1", "본문", 3, 4, 0.8)]),
    }
    return snapshot_state(st)


def _patch_pipeline(monkeypatch, rt, *, job, explored: list, synthesized: list):
    """DB·Redis·LLM 을 전부 대역으로 바꾸고 호출만 기록한다."""
    session = _FakeSession(job=job, scalar=0)
    engine = _FakeEngine()
    monkeypatch.setattr(rt, "_job_engine", lambda: (engine, lambda: session))

    async def _claim(db, job_id, *, allowed, to):
        return True

    async def _next_seq(db, job_id):
        return 3

    async def _step(db, job_id, seq, kind, title, *, subq_idx=None, detail=None):
        return MagicMock()

    async def _finish(db, row, status, result=None):
        return None

    async def _corpus_range(db):
        return {"from": "2002", "to": "2026", "n_papers": 7}

    async def _is_cancelled(db, job_id):
        return False

    async def _publish(job_id, kind, payload):
        return None

    async def _explore(state, subq, *, db, emit=None):
        explored.append(subq.text)
        return subq

    async def _synthesize(state):
        synthesized.append(state)
        return {"sections": []}

    for name, fn in (
        ("_claim", _claim), ("_next_seq", _next_seq), ("_step", _step),
        ("_finish", _finish), ("_corpus_range", _corpus_range),
        ("_is_cancelled", _is_cancelled), ("publish", _publish),
        ("explore_subquestion", _explore), ("synthesize", _synthesize),
    ):
        monkeypatch.setattr(rt, name, fn)
    return engine


class TestNextSeq:
    """seq 를 1 로 되돌리면 uq_research_steps_job_seq 를 위반해 재시도가 죽는다."""

    def test_returns_value_from_db_not_a_constant(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=7)
        assert asyncio.run(rt._next_seq(db, uuid.uuid4())) == 7

    def test_empty_table_starts_at_zero(self, monkeypatch):
        # coalesce(max(seq), -1) + 1 — step 이 없는 잡은 0 에서 시작한다
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=0)
        assert asyncio.run(rt._next_seq(db, uuid.uuid4())) == 0

    def test_query_continues_from_max_for_this_job(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=5)
        jid = uuid.uuid4()
        asyncio.run(rt._next_seq(db, jid))
        assert "max(seq)" in db.sql[0]
        assert "job_id = :j" in db.sql[0]
        # UUID 로 넘긴다 — 문자열을 넘기면 드라이버 쪽 변환에 기대게 된다
        assert db.params[0] == {"j": jid}


class TestResumeFromSnapshot:
    """stage="explored" 로 다시 들어온 잡은 탐색을 건너뛰고 종합부터 간다.

    이 분기가 없으면 stage·state_snapshot 은 쓰기만 하고 아무도 안 읽는
    컬럼이 되고, 종합 실패가 5~7분짜리 탐색을 매번 버린다.
    """

    def test_explored_job_skips_exploration(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=_explored_snapshot())
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        out = asyncio.run(rt._run_deep_research(str(job.id)))

        # plan 을 일부러 채워 뒀다 — 재개 분기를 지우면 여기서 2건이 탐색된다
        assert explored == []
        assert len(synthesized) == 1
        assert out["status"] == "completed"
        assert job.stage == "synthesized"

    def test_resumed_state_comes_from_the_snapshot(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1", "계획 하위2"],
                       state_snapshot=_explored_snapshot())
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        asyncio.run(rt._run_deep_research(str(job.id)))

        state = synthesized[0]
        # plan 이 아니라 스냅샷에서 살아난 하위질문이어야 한다
        assert [sq.text for sq in state.subquestions] == ["스냅샷 하위1", "스냅샷 하위2"]
        assert state.subquestions[1].failed is True
        assert state.evidence["E0"].chunks[0].page_start == 3

    def test_planned_job_runs_the_exploration_loop(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1", "계획 하위2"])
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1", "계획 하위2"]
        assert job.stage == "synthesized"

    def test_exploration_writes_the_checkpoint(self, monkeypatch):
        """체크포인트를 안 쓰면 종합이 실패했을 때 되살릴 것이 없다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert job.state_snapshot is not None
        assert [sq["text"] for sq in job.state_snapshot["subquestions"]] == ["계획 하위1"]

    def test_stage_explored_without_snapshot_falls_back_to_exploration(self, monkeypatch):
        # 스냅샷이 비어 있으면 되살릴 것이 없다 — 빈 보고서를 completed 로 저장하느니
        # 탐색을 다시 도는 쪽이 맞다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1"], state_snapshot=None)
        explored = []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert explored == ["계획 하위1"]

    def test_engine_is_disposed(self, monkeypatch):
        # dispose 를 빠뜨리면 다음 잡이 닫힌 루프에 묶인 커넥션을 만난다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["계획 하위1"],
                       state_snapshot=_explored_snapshot())
        engine = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert engine.disposed == 1


class TestClaim:
    """Celery 는 at-least-once 다 — 선점에 실패한 재배달은 즉시 돌아서야 한다."""

    def test_unclaimed_job_is_skipped(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        explored, synthesized = [], []
        _patch_pipeline(monkeypatch, rt, job=job, explored=explored, synthesized=synthesized)

        async def _no_claim(db, job_id, *, allowed, to):
            return False

        monkeypatch.setattr(rt, "_claim", _no_claim)
        out = asyncio.run(rt._run_deep_research(str(job.id)))

        assert out["status"] == "skipped"
        assert explored == [] and synthesized == []

    def test_run_claims_only_statuses_the_api_writes(self, monkeypatch):
        """approve·retry 가 쓰는 상태를 워커가 받지 못하면 잡이 영원히 skipped 다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["계획 하위1"])
        _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])
        seen = {}

        async def _record(db, job_id, *, allowed, to):
            seen["allowed"], seen["to"] = allowed, to
            return True

        monkeypatch.setattr(rt, "_claim", _record)
        asyncio.run(rt._run_deep_research(str(job.id)))

        from models.research import STATUS_APPROVED, STATUS_QUEUED
        assert STATUS_APPROVED in seen["allowed"]
        assert STATUS_QUEUED in seen["allowed"]
        assert seen["to"] == "running"


class TestStageGuard:
    def test_unknown_stage_is_rejected(self, monkeypatch):
        # stage 오타는 재개 분기를 조용히 빗나가게 만든다 — 예외도 안 난다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=[])
        try:
            rt._set_stage(job, "explored_")
        except AssertionError:
            return
        raise AssertionError("알 수 없는 stage 가 통과했다")
```

- [x] **검증** — `12 passed`(태스크), state 28 · synthesizer 24 · models 17, 전체 **334**. 되돌림 4건 확인. 재개 분기 테스트는 가짜 잡에 **비어 있지 않은 `plan`** 을 함께 넣어야 물린다 — `plan=None` 이면 되돌린 코드도 똑같이 아무것도 탐색하지 않아 테스트가 공허하게 통과한다.

---

## Task 11: 운영 배포와 라이브 검증 — **완료 (재개 경로 미검증)**

> 2026-09-23 실행. Step 4~9 통과, Step 9 의 재개는 종합 실패가 자연발생하지 않아 미검증. Step 10 실측과 도중에 고친 종합 버그(`b6360b8`)는 `docs/roadmap/round04a-완료노트.md` §2·§3. 스탬프는 서버 `alembic_version` 이 `0005_research_jobs` 인 것으로 확인했다(2026-09-23) — Step 0-b·2 는 끝난 상태다. Step 0-a(백필 잔량)·Step 3(임포트·큐)은 실행 기록이 없다.
>
> **이 절은 딥리서치가 `q_llm`·`celery-llm` 에서 돌던 시점의 절차다.** 머지 전 리뷰 반영분을 다시 배포할 때는 전용 큐 전환 여부에 따라 Step 3 의 확인 대상이 달라진다(아래 Step 3). 배포 순서와 인덱싱 중 주의는 완료노트 §5·`recurring-gotchas.md` 16번. 이번 반영분은 스키마 변경이 없어 스탬프·마이그레이션이 필요 없다.

코드가 아니라 확인 절차다. `docs/ops/bulk_ingest_runbook.md` 의 배포 절차를 따른다. **이 절의 명령은 사용자가 서버에서 실행한다.**

> **초안의 Step 1 은 그대로는 실패한다.** 2026-09-22 실측: 서버의 `alembic_version` 이 `0003_widen_varchar_fields` 다 — `0004` 조차 찍혀 있지 않다. 반면 `0004` 가 만드는 객체는 **전부 실재한다**(10/10). 운영 스키마를 만들어온 것은 Alembic 이 아니라 `app/main.py:33` 의 `Base.metadata.create_all`(새 테이블)과 같은 lifespan 의 `ALTER TABLE … ADD COLUMN IF NOT EXISTS` 블록(`doc_type`·`extra`·인덱스)이기 때문이다. 이 상태에서 `alembic upgrade head` 를 돌리면 `0004` 의 `add_column` 이 `DuplicateColumn` 으로 죽는다. 상세: `recurring-gotchas.md` 14번.

- [ ] **Step 0-a: `0004` 의 데이터 백필 잔량 확인 (stamp 전에)** — 실행 기록 없음

`stamp` 는 DDL 뿐 아니라 마이그레이션 안의 `op.execute(UPDATE …)` 도 건너뛴다. `0004` 에는 KCI 논문 `doc_type` 백필이 들어 있다.

```bash
docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
select count(*) as kci_doc_type_null
from library_catalog where source_format = 'KCI' and doc_type is null;
SQL
```

`0` 이면 Step 0-b 로. `0` 이 아니면 먼저 손으로 돌린다:
`UPDATE library_catalog SET doc_type = 'paper' WHERE source_format = 'KCI' AND doc_type IS NULL;`

- [x] **Step 0-b: `0004` 스탬프** — 서버 `alembic_version` 이 `0005` 라 이 단계도 지났다(2026-09-23 확인)

객체 10종이 전부 존재함은 2026-09-22 에 확인했다(`ingest_jobs`·`ingest_job_items`·인덱스 6종·`library_catalog.doc_type`·`extra`).

```bash
docker exec -e PYTHONPATH=/app -w /app nl-lib-fastapi alembic stamp 0004_doc_type_extra_ingest_jobs
```

- [x] **Step 1: 이미지 빌드·배포**

`NL_LIB_FASTAPI_IMAGE` 를 `:latest` 로 맞춰 빌드한다(`recurring-gotchas.md` 3번 — `build_dev_images.sh` 는 `:dev` 만 만든다). 큰 이미지는 서버에서 `docker pull` 을 먼저 하고 Portainer 에서는 Redeploy 만 누른다(같은 문서 12번).

**round03 이월분이 함께 나간다** — 참고문헌 정규식 강화(`49b0274`)가 아직 배포되지 않았다. 인덱싱 재개 전에 이 이미지가 떠 있어야 한다.

- [x] **Step 2: `research_*` 테이블 확인 후 `0005` 스탬프** — `alembic_version = 0005_research_jobs` 확인(2026-09-23)

새 이미지의 API 가 뜨면 lifespan 의 `create_all` 이 **모델에서** `research_jobs`·`research_steps` 를 만든다. 그래서 `0005` 는 DDL 을 돌리지 않고 스탬프만 맞춘다 — 여기서 `upgrade head` 를 쓰면 `DuplicateTable` 이다.

```bash
docker exec -i nl-lib-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
\d research_jobs
\d research_steps
SQL
docker exec -e PYTHONPATH=/app -w /app nl-lib-fastapi alembic stamp 0005_research_jobs
```

**확인할 것**: `stage` 가 `not null default 'created'`, `params` 가 `not null default '{}'::jsonb`, `uq_research_steps_job_seq` 와 `ix_research_steps_inflight` 가 존재. `status` 는 `not null` 이되 DB 기본값이 **없다**(모델이 파이썬 측 `default=` 만 쓴다) — 앱 경로로는 항상 채워지므로 정상이며, 손으로 INSERT 할 때만 걸린다.

- [ ] **Step 3: 임포트·큐 확인** — 실행 기록 없음

> 초안은 `nl-lib-worker` 에서 확인했는데 **그런 컨테이너는 없다.** compose 의 워커는 `nl-lib-celery`(`-Q ingestion,default`)·`nl-lib-celery-cpu`·`nl-lib-celery-llm`(`-Q q_llm`)·`nl-lib-celery-embed`·`nl-lib-celery-beat`, 그리고 머지 전 리뷰 이후의 `nl-lib-celery-research`(`-Q q_research`)·`nl-lib-celery-research-plan`(`-Q q_research_plan`)이다. 딥리서치 태스크를 받는 워커는 fastapi 컨테이너의 `RESEARCH_QUEUE`(실행)·`RESEARCH_PLAN_QUEUE`(계획, 비우면 실행과 같은 큐)로 정해진다 — 값이 없으면(기본 `q_llm`) 둘 다 `nl-lib-celery-llm`, 전용 워커로 넘긴 뒤에는 실행은 `nl-lib-celery-research`, 계획은 `nl-lib-celery-research-plan`.

```bash
# 보내는 쪽이 어느 큐로 보내는지
docker exec nl-lib-fastapi python -c "from core.config import get_settings as g; print(g().RESEARCH_QUEUE, g().RESEARCH_PLAN_QUEUE)"
docker exec nl-lib-fastapi python -c "import api.research; print('OK')"

# RESEARCH_QUEUE 가 q_llm 이면
docker exec nl-lib-celery-llm python -c "import workers.research_tasks; print('OK')"
docker exec nl-lib-celery-llm celery -A workers.celery_app inspect active_queues | grep -c q_llm

# RESEARCH_QUEUE 가 q_research 이면
docker exec nl-lib-celery-research python -c "import workers.research_tasks; print('OK')"
docker exec nl-lib-celery-research celery -A workers.celery_app inspect active_queues | grep -c q_research
docker exec nl-lib-celery-research-plan celery -A workers.celery_app inspect active_queues | grep -c q_research_plan
```

마지막이 `0` 이면 **태스크가 큐에 쌓이기만 하고 아무도 소비하지 않는다.** fastapi 의 `RESEARCH_QUEUE`·`RESEARCH_PLAN_QUEUE` 와 워커의 `-Q` 가 같은지 확인한다.

- [x] **Step 4: 계획 수립**

컨테이너 내부에서 호출한다 — 게이트웨이 영향을 빼고 앱만 본다. (게이트웨이가 막는 것은 `/api/admin`·`/docs`·`/openapi.json` 이고 `/api/research` 는 열려 있다. 초안의 "관리 API 는 차단돼 있으므로"는 이 경로에 맞지 않는다.) 시연 전 리허설이므로 파라미터를 줄여 짧게 돈다.

```bash
docker exec nl-lib-fastapi curl -s -X POST http://localhost:8000/api/research -H 'Content-Type: application/json' -d '{"question":"공공도서관 서비스 품질 평가는 어떻게 연구되어 왔는가","params":{"max_subquestions":3,"max_recheck":1,"per_subq_top_k":8}}'
```

Expected: `{"job_id":"...","status":"created"}`

- [x] **Step 5: 계획 확인 후 승인**

```bash
docker exec nl-lib-fastapi curl -s http://localhost:8000/api/research/<job_id>
```

`status` 가 `awaiting_approval`, `stage` 가 `planned`, `plan` 에 하위질문 3개. 확인 후:

```bash
docker exec nl-lib-fastapi curl -s -X POST http://localhost:8000/api/research/<job_id>/approve -H 'Content-Type: application/json' -d '{}'
```

**반환 `status` 가 `approved` 여야 한다.** `awaiting_approval` 이 그대로 돌아오면 워커가 영원히 `skipped` 를 반환한다.

- [x] **Step 6: 진행 중계** — 앱 직결 경로만 검증했다

```bash
docker exec nl-lib-fastapi curl -N -s http://localhost:8000/api/research/<job_id>/stream
```

첫 줄에 `snapshot`, 이어서 `search`·`critique` 이벤트. 유휴 15초마다 `: ping` 주석 프레임이 와야 한다. 잡이 끝나면 `done` 이 오고 스트림이 **닫혀야** 한다.

> **이 명령은 게이트웨이(nginx)를 거치지 않는다** — fastapi 컨테이너 안에서 앱에 직접 붙는다. 여기서 ping 이 안 오면 nginx 가 아니라 앱·Redis 쪽 문제다(초안의 "nginx 가 버퍼링하는 것" 진단은 틀렸다). 브라우저가 쓸 게이트웨이 경로(`location /api/`, `proxy_read_timeout 120s`)는 이 절차로 검증되지 않았다 — 앱이 `X-Accel-Buffering: no` 를 보내고 ping(15초)이 타임아웃(120초)보다 짧아 동작할 가능성은 높지만, round04b 에서 게이트웨이 경유로 처음 확인한다:
>
> ```bash
> curl -N http://<서버>:92/api/research/<job_id>/stream
> ```

- [x] **Step 7: 보고서 검증 — 인용 무결성**

```bash
docker exec nl-lib-fastapi curl -s http://localhost:8000/api/research/<job_id> | python -c "import json,sys,re; d=json.load(sys.stdin); r=d['report']; ids=set(r['evidence']); used=set(); [used.update(re.findall(r'\[(E\d+)\]', s['intro'])) for s in r['sections']]; [used.update(re.findall(r'\[(E\d+)\]', f['text'])) for s in r['sections'] for f in s['future']]; print('근거', len(ids), '사용된 마커', len(used), '미해석', used-ids); print('한계', r['limitations'])"
```

**`미해석` 이 빈 집합이어야 한다.** 하나라도 남으면 `bind_markers` 가 새는 것이니 멈추고 원인을 찾는다.

> **2026-09-23 실측 — 위 검사만으로는 부족하다.** 미해석은 `set()` 이었는데 보고서는 하위질문 3개 중 **절 1개**, 근거 10편 중 **논문 1편**만 실었다. 한 번의 호출로 전체를 맡긴 종합이 프롬프트 예시 모양(섹션 1·논문 1·과제 1)을 gemma-3-12b 가 그대로 베낀 것이다. 종합을 하위질문별 호출로 바꾸고 절·논문 구성을 코드가 정하게 고쳤다(`synthesizer.build_section`). 같은 잡의 `state_snapshot` 으로 새 종합만 드라이런해 **절 3 · 논문으로 실린 근거 9/10 · 요약 12/12** 를 확인했다(10번째는 `PAPERS_PER_SECTION=5` 상한에 걸림). 그 드라이런에서 모델이 **대표 논문 요약에도 `[E#]` 를 달았다** — 요약은 `bind_markers` 를 안 거치므로 `strip_markers` 로 걷어낸다. 그래서 Step 7 은 아래 구성 검사를 함께 돈다.

```bash
docker exec nl-lib-fastapi curl -s "http://localhost:8000/api/research/$JOB" | python3 -c "
import json,sys,re; r=json.load(sys.stdin)['report']
cited={e for s in r['sections'] for p in s['papers'] for e in p['evidence']}
leak=[p['evidence'][0] for s in r['sections'] for p in s['papers'] if re.search(r'\[E\d+\]', p['summary'])]
print('절', len(r['sections']), '| 근거', len(r['evidence']), '| 논문으로 실린 근거', len(cited), '| 요약 속 마커', leak)"
```

**절 수 = 근거가 있는 하위질문 수, 요약 속 마커 = `[]`** 여야 한다.

- [x] **Step 8: 두 번째 잡 — 이벤트 루프 회귀**

**첫 잡만 돌려보고 넘어가면 안 된다.** 잡 단위 엔진과 `dispose()` 가 실제로 루프 간 커넥션 누수를 막는지는 두 번째 잡에서만 드러난다. Step 4~7 을 한 번 더 돌린다. `attached to a different loop` 가 나오면 `_job_engine` 이 제 일을 못 하는 것이다.

- [ ] **Step 9: 취소·재개 확인** — 취소 통과, 재개 미검증

```bash
# 취소 — running 중에
docker exec nl-lib-fastapi curl -s -X POST http://localhost:8000/api/research/<job_id>/cancel
```

진행 중이던 하위질문을 마친 뒤 멈추고 `canceled` 가 되어야 한다(진행 중인 LLM 호출을 중간에 끊지는 않는다).

> 2026-09-23 라이브 통과는 **탐색 중 취소**만 본 것이다. 리뷰에서 그 밖의 구간(마지막 하위질문·종합·계획 중 취소)은 워커의 무조건 대입이 `canceled` 를 `completed`·`awaiting_approval` 로 덮는 것이 드러나 고쳤다(머지 전 리뷰 반영 — 조건부 전이, 절마다 취소 확인). 그 구간은 단위 테스트로만 확인했다. 재배포 뒤 다시 확인한다면 종합 단계("보고서 종합" step 이 `running`)에서 취소하고, 잠시 뒤 잡이 `canceled` 로 남고 synthesize step 이 `failed`(`취소됨`)로 닫혔는지 본다.

재개는 종합이 실패한 잡에서만 확인할 수 있다. 자연발생하지 않으면 건너뛰고 완료노트에 미검증으로 남긴다 — **억지로 실패시키려 프로덕션 설정을 건드리지 않는다.**

- [x] **Step 10: 실측 기록** — 완료노트 §2. 기본 파라미터 실측·시연 파라미터 선정은 남았다

실행 소요 시간, 하위질문별 근거 수, 한계 섹션 내용을 완료노트에 적는다. 이 값으로 `params` 기본값(특히 `per_subq_top_k`·`min_evidence_per_subq`)을 조정한다. **시연용 파라미터도 여기서 정한다** — 5~7분이 설계값이지만 3분 시연에서는 미리 돌려둔 보고서를 여는 편이 안전하다.

---

## 이 계획에서 다루지 않는 것

- **프론트엔드 전부** — round04b
- **인용 그래프** — `extra["references"]` entity resolution, 대회 이후
- **PDF 내보내기 · AI 생성 다이어그램 · 도서 코퍼스 · 다국어**
- **시연 분야 우선 인덱싱** — 운영 작업이며 코드와 독립. spec §8
- `app/api/admin.py` Milvus expression injection — 기존 이월 유지
- **spec 에 있었지만 구현하지 않은 것** — `deep_read_top_n`("유망 논문은 본문까지 읽는다", spec §3-4), 대표 논문 요약의 논문별 호출(spec §4-1), 실패한 잡의 자동 재개·워커 사망 시 자동 재개(spec §6 — `POST /retry` 로 대체. 종합 LLM 의 1회 재시도는 절 단위로 구현했다). 상세는 spec 의 각 **구현 시 변경**, 이월은 완료노트 §8.

## 알려진 미확정

- ~~`BookRepository.get_by_cnts_ids` 반환형~~ — **해소됨(2026-09-21).** `dict[str, BookOut]` 이고 `BookOut(BookBase)` 가 `title`·`personal_author`·`series_title`·`vol_issue`·`pub_date`·`kci_citations`·`grade` 를 전부 갖는다. ORM 직접 조회로 바꿀 필요 없다.
- ~~`uci`·`url` 채움률~~ — **해소됨(2026-09-22 실측).** 논문 236,513편 **전부 0건**이다(인덱싱분 74,898편 포함, `source_format` 은 전량 KCI). 컬럼은 `BookBase` 에 실재하지만 값이 없다. 인용칩의 `원문 보기` 는 spec 원안대로 **자체 경로**로 보낸다.
  프론트는 이미 그렇게 동작한다 — `frontend/pages/papers/[id].vue:138` 이 `v-if="paper.url"` 로 외부 링크, `v-else` 로 PDF 모달인데 `url` 이 0건이라 **외부 링크 분기는 운영에서 죽은 코드**이고 전부 우리가 보관한 PDF 로 간다. KCI 랜딩 페이지보다 나은 목적지다(전문이 우리 쪽에 있다). round04b 의 인용칩도 여기에 맞춘다.
  경로는 `PdfViewer → /api/books/{cnts_id}/pdf → MinIO originals/{cnts_id}/` 다. MinIO 키를 직접 조립하지 말 것 — `_resolve_original_key` 가 폴더형/평탄형 두 적재 형식을 폴백으로 처리한다. 원본이 없는 논문에서 404 가 나는 문제는 미해결이며 round04b 몫이다. 상세: spec §4-3.
- ~~`pytest-asyncio` 설치 여부~~ — **해소됨(2026-09-22).** 설치돼 있지 않고 `app/tests` 전체에서 `@pytest.mark.asyncio` 사용이 0건이다. 관례는 `asyncio.run(...)`. 설치하지 않는다 — 플러그인이 없으면 pytest 가 코루틴을 실행하지 않고 **통과로 처리해** 테스트가 초록불로 빈다.
- ~~서버 `alembic_version`~~ — **해소됨(2026-09-22).** `0003_widen_varchar_fields` 다. `0004` 조차 안 찍혀 있는데 그 객체 10종은 전부 실재한다 — 운영 스키마는 `create_all`(새 테이블)과 lifespan 의 `ALTER TABLE … ADD COLUMN IF NOT EXISTS`(`doc_type`·`extra`·인덱스)가 만들어왔다. `recurring-gotchas.md` 14번, 배포 절차는 Task 11 Step 0. **2026-09-23 재확인: `0005_research_jobs`** — 스탬프까지 맞춰졌다.
- ~~Celery 워커가 `q_llm` 큐를 소비하도록 이미 떠 있는지~~ — **해소됨(2026-09-23).** `nl-lib-celery-llm`(`-Q q_llm`)이 소비한다. 라이브에서 같은 워커 프로세스(`ForkPoolWorker-2`)가 잡 2개를 처리했다(완료노트 §2). 전용 큐로 전환한 뒤에는 실행은 `nl-lib-celery-research`(`-Q q_research`), 계획은 `nl-lib-celery-research-plan`(`-Q q_research_plan`)이 소비자다 — Task 11 Step 3.
- ~~`redis.asyncio` 가 이미지에 포함돼 있는지~~ — **해소됨(2026-09-23).** 라이브에서 중계(`search`·`critique`·`done`)가 정상 동작했다. (초안이 가리킨 "Task 10 Step 7" 은 없다 — Task 10 은 Step 이 아니라 파일별 체크리스트다. 확인은 Task 11 Step 6 에서 됐다.)
