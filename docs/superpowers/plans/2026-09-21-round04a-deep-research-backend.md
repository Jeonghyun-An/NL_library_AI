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

제외한 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 collect 단계에서 실패한다. 이 계획과 무관하다. 착수 시점 기준선은 **134 passed** 다.

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
| `app/services/research/relay.py` | Redis pub/sub 발행·구독 |
| `app/domains/nl_library/prompts/research_plan.yaml` | 계획 수립 프롬프트 |
| `app/domains/nl_library/prompts/research_critique.yaml` | 자기점검 프롬프트 |
| `app/domains/nl_library/prompts/research_synthesize.yaml` | 종합 프롬프트 |
| `app/workers/research_tasks.py` | Celery 태스크 |
| `app/api/research.py` | API 4종 + SSE |

순수 계산을 `scoring.py`·`citations.py` 로 뽑아내는 이유는 **Milvus·LLM 없이 테스트하기 위해서**다. `scripts/recovery/rewrite_milvus_doc_type.py` 가 같은 구조로 16개 테스트를 돌린다.

---

## Task 1: 데이터 모델과 마이그레이션 — **완료**

> 구현·리뷰가 끝났다. 아래 코드는 **리뷰 반영이 끝난 최종 상태**이며 저장소의 실제 파일과 일치한다
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

> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 최종 상태**이며 저장소의 실제 파일과 일치한다.

딥리서치 실행 중 상태를 담는 dataclass 들과 깊이 파라미터. 파이프라인의 각 단계는 `ResearchState` 를 받아 갱신해 돌려주므로 Celery·Redis·Milvus 없이 테스트된다.

리뷰 반영으로 초안과 달라진 것: `merge_params` 가 키뿐 아니라 **값의 타입·범위까지 검증**한다(`citation_weight: -0.2` 가 통과하면 영향력 높은 논문 점수를 깎아 순위가 조용히 뒤집힌다). `DEFAULT_PARAMS` 는 `MappingProxyType` 으로 잠갔고, `HitRow(TypedDict)` 와 `VERDICTS` 상수가 추가됐다.

- [x] **`app/services/research/state.py`**

```python
# app/services/research/state.py
"""state.py — 딥리서치 실행 상태

각 단계는 ResearchState 를 받아 갱신해 돌려준다. Celery·Redis·Milvus 없이
테스트되고, 나중에 다른 오케스트레이션 런타임으로 옮겨도 그대로 쓴다.
"""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypedDict

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
    """검색 결과 1건 — Milvus 검색 계층(explore)이 만들어 citations.build_evidence 로 넘긴다."""
    book_id: str
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    score: float


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

> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 최종 상태**이며 저장소의 실제 파일과 일치한다.

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

- [x] **검증** — `15 passed`, 전체 회귀 202 passed

---

## Task 4: 근거 조립과 마커 검증 — **완료**

> 구현·리뷰가 끝났다. 아래는 **리뷰 반영이 끝난 최종 상태**이며 저장소의 실제 파일과 일치한다.

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

## Task 5: 계획 수립 (파싱 + 프롬프트)

**Files:**
- Create: `app/services/research/planner.py`
- Create: `app/domains/nl_library/prompts/research_plan.yaml`
- Test: `app/tests/test_research_planner.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# app/tests/test_research_planner.py
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

    def test_no_list_raises(self):
        with pytest.raises(ValueError, match="계획을 해석하지 못했다"):
            parse_plan("죄송하지만 답변할 수 없습니다.", limit=6)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest app/tests/test_research_planner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.research.planner'`

- [ ] **Step 3: 구현**

```python
# app/services/research/planner.py
"""planner.py — 질문을 하위질문으로 분해

파싱을 LLM 호출에서 분리한 이유: 모델이 번호 매김을 흐트러뜨리는 것은
흔한 일이고, 그 처리를 네트워크 없이 테스트할 수 있어야 한다.
"""
import re

from services.llm_client import chat
from services.prompts import get_prompt

_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.+?)\s*$")
_EMPH = re.compile(r"[*_`]+")


def parse_plan(raw: str, *, limit: int) -> list[str]:
    """번호/불릿 목록에서 하위질문을 뽑는다. 중복·공백 제거, limit 개까지."""
    items: list[str] = []
    for line in (raw or "").splitlines():
        m = _ITEM.match(line)
        if not m:
            continue
        text = _EMPH.sub("", m.group(1)).strip()
        if text and text not in items:
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

- [ ] **Step 4: 프롬프트 작성**

```yaml
# app/domains/nl_library/prompts/research_plan.yaml
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

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest app/tests/test_research_planner.py -q`
Expected: PASS (8 passed)

- [ ] **Step 6: 프롬프트가 로드되는지 확인**

Run: `python -c "import sys; sys.path.insert(0,'app'); from services.prompts import get_prompt; s,u,p=get_prompt('research_plan').render(question='테스트', limit=6); print('OK', p)"`
Expected: `OK {'max_tokens': 800, 'temperature': 0.3}`

- [ ] **Step 7: 커밋**

```bash
git add app/services/research/planner.py app/domains/nl_library/prompts/research_plan.yaml app/tests/test_research_planner.py
git commit -m "[Feat] round04a — 연구 계획 수립"
```

---

## Task 6: 자기점검

**Files:**
- Create: `app/services/research/critic.py`
- Create: `app/domains/nl_library/prompts/research_critique.yaml`
- Test: `app/tests/test_research_critic.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# app/tests/test_research_critic.py
from services.research.critic import Verdict, parse_verdict, should_recheck
from services.research.state import SubQuestion


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
        assert "판정 해석 실패" in v.note

    def test_unknown_verdict_value_falls_back(self):
        v = parse_verdict('{"verdict": "maybe", "note": "n", "new_queries": []}')
        assert v.verdict == "sufficient"


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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest app/tests/test_research_critic.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.research.critic'`

- [ ] **Step 3: 구현**

```python
# app/services/research/critic.py
"""critic.py — 근거 충분성 자기점검

판정 결과는 내부 제어에만 쓰지 않는다. note 가 그대로 보고서의
"한계와 미확인 영역" 섹션이 된다 — 모른다고 말하는 것이 이 기능의 값이다.
"""
import json
import re
from dataclasses import dataclass, field

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.state import Evidence, SubQuestion

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
_VERDICTS = ("sufficient", "insufficient")


@dataclass
class Verdict:
    verdict: str
    note: str = ""
    new_queries: list[str] = field(default_factory=list)


def parse_verdict(raw: str) -> Verdict:
    """판정 JSON 을 읽는다. 못 읽으면 sufficient 로 떨어뜨려 루프를 끝낸다.

    해석 실패를 insufficient 로 두면 파싱이 깨질 때마다 재검색이 상한까지
    돌아 시간을 태운다. 실패가 루프가 되면 안 된다.
    """
    body = raw or ""
    m = _FENCE.search(body)
    if m:
        body = m.group(1)
    try:
        data = json.loads(body[body.index("{"): body.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return Verdict("sufficient", note=f"판정 해석 실패 — {(raw or '')[:80]}")

    verdict = data.get("verdict")
    if verdict not in _VERDICTS:
        return Verdict("sufficient", note=f"판정 해석 실패 — verdict={verdict!r}")

    queries = [q for q in (data.get("new_queries") or []) if isinstance(q, str) and q.strip()]
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries)


def should_recheck(subq: SubQuestion, *, recheck_count: int, max_recheck: int) -> bool:
    return subq.verdict == "insufficient" and recheck_count < max_recheck


async def critique(
    subq: SubQuestion, evidence: list[Evidence], *, params: dict,
) -> Verdict:
    lines = [
        f"- {e.meta.get('title', '(제목 없음)')} ({e.meta.get('pub_date', '연도미상')})"
        for e in evidence
    ]
    system, user, llm_params = get_prompt("research_critique").render(
        subquestion=subq.text,
        evidence_count=len(evidence),
        evidence_list="\n".join(lines) or "(없음)",
        min_evidence=params["min_evidence_per_subq"],
        tried_queries=", ".join(subq.queries),
    )
    raw = await chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        params=llm_params,
    )
    return parse_verdict(raw)
```

- [ ] **Step 4: 프롬프트 작성**

```yaml
# app/domains/nl_library/prompts/research_critique.yaml
parser: plain
params:
  max_tokens: 600
  temperature: 0.2
system: |-
  당신은 연구 사서입니다. 하위질문 하나에 대해 모인 근거가 충분한지 판단합니다.

  판단 기준:
  - 근거가 {{ min_evidence }}편 미만이면 대체로 부족합니다.
  - 특정 시기에만 쏠려 있으면 부족합니다.
  - 하위질문의 핵심 개념을 다루지 않는 논문만 있으면 부족합니다.

  부족하다고 판단하면 이미 시도한 검색어와 다른 검색어를 최대 2개 제안하세요.
  같은 말을 바꿔 쓴 것이 아니라 다른 용어·다른 각도여야 합니다.

  JSON 하나만 출력하세요. 다른 말을 덧붙이지 마세요.
  {"verdict": "sufficient" 또는 "insufficient", "note": "판단 근거 한 문장", "new_queries": ["...", "..."]}

  note 는 사용자에게 그대로 보여집니다. 한국어로 구체적으로 쓰세요.
user: |-
  하위질문: {{ subquestion }}
  이미 시도한 검색어: {{ tried_queries }}
  모인 근거: {{ evidence_count }}편

  {{ evidence_list }}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest app/tests/test_research_critic.py -q`
Expected: PASS (9 passed)

- [ ] **Step 6: 커밋**

```bash
git add app/services/research/critic.py app/domains/nl_library/prompts/research_critique.yaml app/tests/test_research_critic.py
git commit -m "[Feat] round04a — 근거 충분성 자기점검"
```

---

## Task 7: 하위질문 탐색

**Files:**
- Create: `app/services/research/explorer.py`
- Test: `app/tests/test_research_explorer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# app/tests/test_research_explorer.py
import pytest

from services.research.explorer import rank_hits


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
        assert ranked[0]["score"] == pytest.approx(0.9)

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

    def test_original_hits_are_not_mutated(self):
        hits = [self._hit("A", 0.9)]
        rank_hits(hits, {"A": self._meta("2008-01", 10)}, citation_weight=0.2, now_year=2026)
        assert hits[0]["score"] == pytest.approx(0.9)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest app/tests/test_research_explorer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.research.explorer'`

- [ ] **Step 3: 구현**

```python
# app/services/research/explorer.py
"""explorer.py — 하위질문 1개를 탐색한다

기존 검색 파이프라인을 그대로 쓰고(논문 스코프), 그 위에 피인용 가중만
얹는다. 순위 계산은 rank_hits 로 빼서 Milvus 없이 테스트한다.
"""
import logging
from datetime import datetime

from repositories.book import BookRepository
from services.research.scoring import blend_score, impact_per_year, parse_pub_year
from services.research.state import HitRow
from services.search.pipeline import search

log = logging.getLogger(__name__)


def rank_hits(
    hits: list[HitRow], meta_by_id: dict[str, dict], *,
    citation_weight: float, now_year: int,
) -> list[HitRow]:
    """리랭킹 점수에 연간 피인용을 얹어 다시 정렬한다. 입력은 건드리지 않는다."""
    ranked = []
    for hit in hits:
        meta = meta_by_id.get(hit["book_id"]) or {}
        impact = impact_per_year(
            meta.get("kci_citations"), parse_pub_year(meta.get("pub_date")),
            now_year=now_year,
        )
        row = dict(hit)
        row["score"] = blend_score(hit["score"], impact=impact, weight=citation_weight)
        ranked.append(row)
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


async def explore(query: str, *, params: dict, db) -> tuple[list[HitRow], dict[str, dict]]:
    """검색 → 서지 조회 → 피인용 가중 재정렬.

    returns (정렬된 hit 목록, cnts_id → 서지 메타)
    """
    resp = await search(
        query, mode="chunk", top_k=params["per_subq_top_k"],
        doc_scope="paper", db=db,
    )
    hits = [
        {
            "book_id": c.book_id, "chunk_id": c.chunk_id, "text": c.text,
            "page_start": c.page_start, "page_end": c.page_end,
            "score": c.rerank_score if c.rerank_score is not None else c.score,
        }
        for c in resp.chunks
    ]
    if not hits:
        return [], {}

    repo = BookRepository(db)
    books = await repo.get_by_cnts_ids(list({h["book_id"] for h in hits}))
    meta_by_id = {
        cnts_id: {
            "title": b.title, "personal_author": getattr(b, "personal_author", None),
            "series_title": getattr(b, "series_title", None),
            "vol_issue": getattr(b, "vol_issue", None),
            "pub_date": getattr(b, "pub_date", None),
            "kci_citations": getattr(b, "kci_citations", 0),
            "grade": getattr(b, "grade", None),
        }
        for cnts_id, b in books.items()
    }
    ranked = rank_hits(
        hits, meta_by_id,
        citation_weight=params["citation_weight"], now_year=datetime.now().year,
    )
    return ranked, meta_by_id
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest app/tests/test_research_explorer.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: `BookRepository.get_by_cnts_ids` 의 실제 반환형 확인**

Run: `grep -n "def get_by_cnts_ids" -A 12 app/repositories/book.py`

반환이 `dict[str, BookOut]` 이고 `BookOut` 에 `series_title`·`kci_citations`·`grade` 가 없으면, `explore()` 에서 `Book` ORM 을 직접 조회하도록 바꾼다. `BookOut` 에 필드를 추가하지 말 것 — 검색 응답 스키마가 커진다.

- [ ] **Step 6: 커밋**

```bash
git add app/services/research/explorer.py app/tests/test_research_explorer.py
git commit -m "[Feat] round04a — 하위질문 탐색과 피인용 가중 재정렬"
```

---

## Task 8: 보고서 종합

**Files:**
- Create: `app/services/research/synthesizer.py`
- Create: `app/domains/nl_library/prompts/research_synthesize.yaml`
- Test: `app/tests/test_research_synthesizer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# app/tests/test_research_synthesizer.py
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
        lims = build_limitations(_state(), unmarked_total=0)
        assert any("하위2" in x for x in lims)
        assert any("2015년 이후 자료가 없다" in x for x in lims)

    def test_sufficient_subquestion_is_not_reported(self):
        assert not any("하위1" in x for x in build_limitations(_state(), unmarked_total=0))

    def test_no_evidence_subquestion_is_reported(self):
        assert any("근거를 찾지 못했다" in x for x in build_limitations(_state(), unmarked_total=0))

    def test_unmarked_sentences_are_reported(self):
        lims = build_limitations(_state(), unmarked_total=4)
        assert any("근거 표기가 없는 서술 4건" in x for x in lims)

    def test_zero_unmarked_is_not_reported(self):
        assert not any("근거 표기가 없는" in x for x in build_limitations(_state(), unmarked_total=0))


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
        assert any("근거 표기가 없는 서술" in x for x in report["limitations"])

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

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest app/tests/test_research_synthesizer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.research.synthesizer'`

- [ ] **Step 3: 구현**

```python
# app/services/research/synthesizer.py
"""synthesizer.py — 보고서 조립

인용을 두 갈래로 다룬다.
- 대표 논문 요약: 불릿 = 논문이므로 인용이 구조로 정해진다. 모델이 고르지 않는다.
- 도입·향후 과제: 모델이 [E3] 마커를 달고 여기서 전수 검증한다.

제목·저자·연도는 모델 출력에서 가져오지 않는다. evidence 의 meta 를 쓴다 —
라벨을 모델이 쓰게 두면 언젠가 없는 논문을 만들어낸다.
"""
import json
import logging
import re

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.citations import bind_markers
from services.research.state import ResearchState

log = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
UNMARKED_THRESHOLD = 3


def build_limitations(state: ResearchState, *, unmarked_total: int) -> list[str]:
    """자기점검 결과를 사용자에게 보이는 문장으로 바꾼다."""
    out: list[str] = []
    for sq in state.subquestions:
        if not sq.evidence_ids:
            out.append(f"'{sq.text}' 에 대해서는 근거를 찾지 못했다.")
        elif sq.verdict == "insufficient":
            note = f" — {sq.note}" if sq.note else ""
            out.append(
                f"'{sq.text}' 는 근거 {len(sq.evidence_ids)}편으로 결론이 약하다{note}"
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
    out_sections = []

    for sec in sections:
        intro = bind_markers(sec.get("intro", ""), valid)
        unmarked += intro.unmarked

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
        "limitations": build_limitations(state, unmarked_total=unmarked),
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
    body = raw
    m = _FENCE.search(raw or "")
    if m:
        body = m.group(1)
    try:
        data = json.loads(body[body.index("{"): body.rindex("}") + 1])
        sections = data.get("sections") or []
    except (ValueError, json.JSONDecodeError):
        log.error("[research] 종합 JSON 파싱 실패: %s", (raw or "")[:300])
        raise ValueError("보고서 종합 출력을 해석하지 못했다")

    return assemble_report(state, sections, unmarked_total=0)
```

- [ ] **Step 4: 프롬프트 작성**

```yaml
# app/domains/nl_library/prompts/research_synthesize.yaml
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

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest app/tests/test_research_synthesizer.py -q`
Expected: PASS (10 passed)

- [ ] **Step 6: 커밋**

```bash
git add app/services/research/synthesizer.py app/domains/nl_library/prompts/research_synthesize.yaml app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04a — 보고서 종합과 한계 섹션"
```

---

## Task 9: 오케스트레이션과 진행 중계

**Files:**
- Create: `app/services/research/relay.py`
- Create: `app/services/research/runner.py`
- Test: `app/tests/test_research_runner.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# app/tests/test_research_runner.py
import pytest

from services.research.state import ResearchState, SubQuestion, merge_params
from services.research.runner import explore_subquestion


class _FakeCritic:
    """항상 부족을 반환하는 critic — 루프 상한을 검증한다."""
    def __init__(self):
        self.calls = 0

    async def __call__(self, subq, evidence, *, params):
        from services.research.critic import Verdict
        self.calls += 1
        return Verdict("insufficient", note="부족", new_queries=["다른 검색어"])


async def _fake_explore(query, *, params, db):
    hit = {"book_id": "A", "chunk_id": f"c-{query}", "text": "본문",
           "page_start": 1, "page_end": 1, "score": 0.9}
    return [hit], {"A": {"title": "논문 가", "pub_date": "2008-06", "kci_citations": 3}}


async def _empty_explore(query, *, params, db):
    return [], {}


@pytest.mark.asyncio
class TestExploreSubquestion:
    async def test_always_insufficient_stops_at_max_recheck(self):
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="하위질문")
        critic = _FakeCritic()
        await explore_subquestion(
            st, sq, db=None, explore_fn=_fake_explore, critique_fn=critic, emit=None,
        )
        assert critic.calls == 3            # 최초 1 + 재검색 2
        assert len(sq.queries) == 3
        assert sq.verdict == "insufficient"

    async def test_no_hits_records_no_evidence(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq = SubQuestion(idx=0, text="하위질문")
        await explore_subquestion(
            st, sq, db=None, explore_fn=_empty_explore,
            critique_fn=_FakeCritic(), emit=None,
        )
        assert sq.evidence_ids == []

    async def test_same_paper_in_two_subquestions_reuses_one_evidence(self):
        """한 논문이 두 하위질문에서 나와도 근거는 하나다.

        중복 생성하면 같은 출처가 E1 과 E2 로 갈라져 인용칩이 어긋난다.
        """
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        sq1, sq2 = SubQuestion(idx=0, text="가"), SubQuestion(idx=1, text="나")
        critic = _FakeCritic()
        await explore_subquestion(st, sq1, db=None, explore_fn=_fake_explore,
                                  critique_fn=critic, emit=None)
        await explore_subquestion(st, sq2, db=None, explore_fn=_fake_explore,
                                  critique_fn=critic, emit=None)
        assert len(st.evidence) == 1
        assert sq1.evidence_ids == sq2.evidence_ids == ["E1"]
        assert len({ev.cnts_id for ev in st.evidence.values()}) == 1

    async def test_recheck_does_not_duplicate_same_paper(self):
        """재검색에서 같은 논문이 또 나와도 evidence_ids 에 두 번 들어가지 않는다."""
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 2}))
        sq = SubQuestion(idx=0, text="가")
        await explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                  critique_fn=_FakeCritic(), emit=None)
        assert sq.evidence_ids == ["E1"]

    async def test_max_evidence_caps_growth(self):
        async def _many(query, *, params, db):
            hits = [
                {"book_id": f"B{i}", "chunk_id": f"c{i}", "text": "t",
                 "page_start": 1, "page_end": 1, "score": 0.9}
                for i in range(10)
            ]
            meta = {f"B{i}": {"title": f"t{i}", "pub_date": "2008-06",
                              "kci_citations": 1} for i in range(10)}
            return hits, meta

        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, "max_evidence": 4}))
        await explore_subquestion(st, SubQuestion(idx=0, text="가"), db=None,
                                  explore_fn=_many, critique_fn=_FakeCritic(), emit=None)
        assert len(st.evidence) == 4

    async def test_emit_is_called_for_progress(self):
        events = []

        async def _emit(kind, payload):
            events.append(kind)

        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        await explore_subquestion(
            st, SubQuestion(idx=0, text="가"), db=None, explore_fn=_fake_explore,
            critique_fn=_FakeCritic(), emit=_emit,
        )
        assert "search" in events and "critique" in events
```

`pytest-asyncio` 가 없으면 설치한다: `pip install pytest-asyncio`. `app/tests/test_scenario.py` 가 이미 async 테스트를 쓰는지 먼저 확인하고, 쓴다면 같은 방식을 따른다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest app/tests/test_research_runner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.research.runner'`

- [ ] **Step 3: 중계 구현**

```python
# app/services/research/relay.py
"""relay.py — 진행 이벤트 중계 (Redis pub/sub)

잔이벤트는 여기로만 흐르고 Postgres 에 쓰지 않는다. 카운터가 째깍거리는
것 때문에 DB를 때릴 이유가 없고, 몇 초 뒤 아무도 안 본다.
재접속하면 research_steps 로 뼈대를 복원하고 그 이후를 여기서 받는다.
"""
import json
import logging

import redis.asyncio as aioredis

from core.config import get_settings

log = logging.getLogger(__name__)


def channel(job_id: str) -> str:
    return f"research:{job_id}"


async def publish(job_id: str, kind: str, payload: dict) -> None:
    """중계 실패가 리서치를 죽이면 안 된다 — 삼키고 로그만 남긴다."""
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


async def subscribe(job_id: str):
    """SSE 엔드포인트가 쓴다. 이벤트 dict 를 yield 한다."""
    cfg = get_settings()
    client = aioredis.from_url(cfg.REDIS_URL)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel(job_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            yield json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(channel(job_id))
        await pubsub.aclose()
        await client.aclose()
```

- [ ] **Step 4: 오케스트레이션 구현**

```python
# app/services/research/runner.py
"""runner.py — 단계 오케스트레이션

각 단계는 ResearchState 를 받아 갱신한다. explore_fn·critique_fn 을 인자로
받는 이유는 Milvus·LLM 없이 루프 자체를 테스트하기 위해서다.
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

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest app/tests/test_research_runner.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: 커밋**

```bash
git add app/services/research/relay.py app/services/research/runner.py app/tests/test_research_runner.py
git commit -m "[Feat] round04a — 탐색 루프 오케스트레이션과 Redis 진행 중계"
```

---

## Task 10: Celery 태스크와 API

**Files:**
- Create: `app/workers/research_tasks.py`
- Create: `app/api/research.py`
- Modify: `app/workers/celery_app.py` (task_routes 에 항목 추가)
- Modify: `app/main.py` (라우터 등록)

**착수 전 주의 — 재실행과 유일 제약의 충돌.** Task 1 에서 `research_steps` 에 `(job_id, seq)` 유일 제약이 붙었다. 아래 `_step()` 은 seq 를 0/1..n 으로 **고정 생성**하므로, 같은 잡에 대해 `run_deep_research` 가 두 번 돌면(Celery 브로커 재배달, 수동 재큐) 중복 행 대신 `IntegrityError` 로 태스크가 죽고 잡이 `running` 에 묶인다. API 의 `approve` 중복은 409 로 막히지만 브로커 재배달은 막히지 않는다.

제약 자체는 옳다 — 중복이 조용히 쌓이는 것보다 낫다. 다만 이 Task 에서 재진입을 처리해야 한다. **`run_deep_research` 시작부에서 그 잡의 기존 step 을 지우고 새로 쓰거나**, seq 를 `max(existing) + 1` 로 이어붙여라. 전자가 단순하고, 재실행은 애초에 처음부터 다시 도는 것이므로 의미도 맞는다.

- [ ] **Step 1: Celery 태스크 작성**

```python
# app/workers/research_tasks.py
"""research_tasks.py — 딥리서치 실행 태스크

동기 워커에서 async 파이프라인을 돌린다(기존 stage 태스크와 같은 방식).
부분 실패는 전체 실패가 아니다 — 하위질문 하나가 실패해도 나머지는 계속한다.
"""
import asyncio
import datetime as _dt
import logging

from db.postgres import SyncSessionLocal
from models.research import STEP_KINDS, ResearchJob, ResearchStep
from services.research.relay import publish
from services.research.runner import explore_subquestion
from services.research.state import ResearchState, SubQuestion, merge_params
from services.research.synthesizer import synthesize
from workers.celery_app import celery_app

log = logging.getLogger(__name__)


def _step(db, job_id, seq, kind, title, *, subq_idx=None, detail=None):
    # STEP_KINDS 를 실제로 강제하는 유일한 지점. 상수만 정의하고 아무 데서도
    # 쓰지 않으면 장식이 되고, 오타난 kind 가 프론트 분기를 조용히 빗나간다.
    assert kind in STEP_KINDS, f"알 수 없는 kind: {kind}"
    row = ResearchStep(
        job_id=job_id, seq=seq, kind=kind, title=title,
        subq_idx=subq_idx, detail=detail, status="running",
    )
    db.add(row)
    db.commit()
    return row


def _finish(db, row, status, result=None):
    row.status = status
    row.result = result or {}
    row.finished_at = _dt.datetime.now(_dt.timezone.utc)
    db.commit()


def _corpus_range(db) -> dict:
    """실행 시점의 논문 수록 범위.

    인덱싱이 계속 도는 중이라 범위가 매주 달라진다. 보고서에 "2002~2009"
    같은 고정 문구를 박으면 곧 거짓말이 된다 — 매 실행마다 잰다.
    """
    from sqlalchemy import text as sa_text

    row = db.execute(sa_text(
        "SELECT min(substring(pub_date, 1, 4)), max(substring(pub_date, 1, 4)), count(*) "
        "FROM library_catalog WHERE doc_type = 'paper' AND is_embedded"
    )).first()
    return {"from": row[0], "to": row[1], "n_papers": row[2]}


@celery_app.task(name="tasks.run_deep_research", queue="q_llm")
def run_deep_research(job_id: str) -> dict:
    db = SyncSessionLocal()
    try:
        job = db.get(ResearchJob, job_id)
        if job is None:
            return {"error": "job not found", "job_id": job_id}

        job.status = "running"
        job.started_at = _dt.datetime.now(_dt.timezone.utc)
        db.commit()

        state = ResearchState(
            job_id=str(job.id), question=job.question,
            params=merge_params(job.params or {}),
        )
        state.subquestions = [
            SubQuestion(idx=i, text=t) for i, t in enumerate(job.plan or [])
        ]
        state.corpus_range = _corpus_range(db)

        async def _emit(kind, payload):
            await publish(str(job.id), kind, payload)

        seq = 1
        for subq in state.subquestions:
            row = _step(db, job.id, seq, "search", subq.text,
                        subq_idx=subq.idx,
                        detail=f"'{subq.text}' 관련 논문을 찾기 위해 검색 중입니다")
            seq += 1
            try:
                asyncio.run(explore_subquestion(state, subq, db=None, emit=_emit))
                _finish(db, row, "done", {
                    "queries": subq.queries, "adopted": len(subq.evidence_ids),
                    "verdict": subq.verdict, "note": subq.note,
                })
            except Exception as e:
                log.exception("[research] 하위질문 실패 job=%s idx=%s", job.id, subq.idx)
                _finish(db, row, "failed", {"error": str(e)[:500]})

        row = _step(db, job.id, seq, "synthesize", "보고서 종합")
        try:
            report = asyncio.run(synthesize(state))
            job.report = report
            job.status = "completed"
            _finish(db, row, "done", {"sections": len(report["sections"])})
        except Exception as e:
            log.exception("[research] 종합 실패 job=%s", job.id)
            job.status = "failed"
            job.last_error = str(e)[:1000]
            _finish(db, row, "failed", {"error": str(e)[:500]})

        job.finished_at = _dt.datetime.now(_dt.timezone.utc)
        db.commit()
        return {"job_id": str(job.id), "status": job.status}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

- [ ] **Step 2: 계획 수립 태스크 추가**

같은 파일 끝에 붙인다.

```python
@celery_app.task(name="tasks.plan_deep_research", queue="q_llm")
def plan_deep_research(job_id: str) -> dict:
    """계획만 세우고 승인 대기 상태로 멈춘다."""
    from services.research.planner import make_plan

    db = SyncSessionLocal()
    try:
        job = db.get(ResearchJob, job_id)
        if job is None:
            return {"error": "job not found", "job_id": job_id}

        job.status = "planning"
        db.commit()
        row = _step(db, job.id, 0, "plan", "연구 계획 수립",
                    detail="질문을 하위질문으로 분해하는 중입니다")
        try:
            params = merge_params(job.params or {})
            plan = asyncio.run(make_plan(job.question, params=params))
            job.plan = plan
            job.status = "awaiting_approval"
            _finish(db, row, "done", {"subquestions": plan})
        except Exception as e:
            log.exception("[research] 계획 수립 실패 job=%s", job.id)
            job.status = "failed"
            job.last_error = str(e)[:1000]
            _finish(db, row, "failed", {"error": str(e)[:500]})
        db.commit()
        return {"job_id": str(job.id), "status": job.status}
    finally:
        db.close()
```

- [ ] **Step 3: 큐 라우팅 등록**

`app/workers/celery_app.py` 의 `task_routes` 에 두 줄을 추가한다.

```python
        "tasks.plan_deep_research": {"queue": "q_llm"},
        "tasks.run_deep_research":  {"queue": "q_llm"},
```

같은 파일에서 `workers.tasks` 를 임포트하는 자리 옆에 `import workers.research_tasks  # noqa: F401` 를 추가해 태스크가 등록되게 한다. 기존 파일이 `app/workers/tasks.py` 끝에서 `import workers.job_runtime` 하는 방식을 따른다.

- [ ] **Step 3-b: 워커 사망 복구 태스크 추가**

워커가 죽으면 step 이 `running` 인 채로 영원히 남고 job 도 `running` 에 묶인다. `ingest_job_items` 와 같은 stale 감지를 붙인다. `research_steps.ix_research_steps_inflight` 인덱스가 이걸 위한 것이다.

`app/workers/research_tasks.py` 끝에 추가한다.

```python
STALE_MINUTES = 30


@celery_app.task(name="tasks.reap_stale_research", queue="q_control")
def reap_stale_research() -> dict:
    """멈춰버린 리서치를 실패로 떨어뜨린다.

    딥리서치는 한 번에 5~7분이고 종합이 길어도 10분을 안 넘는다.
    30분 넘게 running 이면 워커가 죽은 것이다.
    """
    from sqlalchemy import text as sa_text

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

        # coalesce 가 필요한 이유: started_at 은 run_deep_research 에서야 찍힌다.
        # planning 단계에서 워커가 죽으면 started_at 이 NULL 이고, NULL 비교는
        # NULL 이라 조건이 참이 되지 않아 그 잡은 영원히 회수되지 않는다.
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

`::jsonb` 캐스트는 바인드 파라미터 뒤가 아니라 리터럴 뒤에 붙으므로 문제없다 (`recurring-gotchas.md` 7번 — 금지되는 건 `:param::type` 이다).

Celery beat 스케줄에 10분 주기로 등록한다. `app/workers/celery_app.py` 에 `beat_schedule` 이 이미 있으면 항목만 추가하고, 없으면 일단 등록만 해두고 수동 호출로 검증한다.

- [ ] **Step 4: API 작성**

```python
# app/api/research.py
"""research.py — 딥리서치 API

실행은 Celery 가 맡고 진행은 SSE 로 중계한다. 탭을 닫아도 워커는 계속 돌고,
다시 열면 research_steps 로 지금까지를 복원한 뒤 이어서 받는다.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from models.research import ResearchJob, ResearchStep
from services.research.relay import subscribe
from services.research.state import merge_params

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchCreate(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    params: dict = Field(default_factory=dict)


class ResearchApprove(BaseModel):
    plan: list[str] | None = None      # 사용자가 수정한 계획. 없으면 제안대로.


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
    job = await db.get(ResearchJob, uuid.UUID(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != "awaiting_approval":
        raise HTTPException(
            status_code=409, detail=f"승인할 수 없는 상태다: {job.status}",
        )
    if req.plan is not None:
        if not req.plan:
            raise HTTPException(status_code=422, detail="계획이 비어 있다")
        job.plan = req.plan
    await db.commit()

    from workers.celery_app import celery_app
    celery_app.send_task("tasks.run_deep_research", args=[str(job.id)])
    return {"job_id": job_id, "status": "running", "plan": job.plan}


@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ResearchJob, uuid.UUID(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    return {
        "job_id": job_id, "question": job.question, "status": job.status,
        "plan": job.plan, "report": job.report, "last_error": job.last_error,
        "steps": [
            {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "title": s.title,
             "detail": s.detail, "status": s.status, "result": s.result}
            for s in rows
        ],
    }


@router.get("/{job_id}/stream")
async def stream_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ResearchJob, uuid.UUID(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    snapshot = [
        {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx,
         "title": s.title, "detail": s.detail, "status": s.status}
        for s in rows
    ]

    async def _gen():
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield f"data: {json.dumps({'kind': 'snapshot', 'steps': snapshot}, ensure_ascii=False)}\n\n"
        async for event in subscribe(job_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 5: 라우터 등록**

`app/main.py` 에서 다른 라우터를 `include_router` 하는 자리 옆에 추가한다.

```python
from api import research as research_api
app.include_router(research_api.router)
```

- [ ] **Step 6: 전체 테스트**

Run:
```bash
python -m pytest app/tests -q --ignore=app/tests/test_book_chat.py --ignore=app/tests/test_build_manifest.py --ignore=app/tests/test_loaders.py
```
Expected: PASS — 기준선 134 + 이 계획에서 추가한 테스트(약 79건)

- [ ] **Step 7: 임포트 검증**

Run: `python -c "import sys; sys.path.insert(0,'app'); import api.research, workers.research_tasks; print('OK')"`
Expected: `OK`

Celery·Redis 임포트에서 실패하면 해당 패키지가 로컬에 없는 것이다. 컨테이너 안에서 확인한다:

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python -c "import api.research, workers.research_tasks; print('OK')"
```

- [ ] **Step 8: 커밋**

```bash
git add app/workers/research_tasks.py app/api/research.py app/workers/celery_app.py app/main.py
git commit -m "[Feat] round04a — 딥리서치 Celery 태스크와 API"
```

---

## Task 11: 운영 배포와 라이브 검증

코드가 아니라 확인 절차다. `docs/ops/bulk_ingest_runbook.md` 의 배포 절차를 따른다.

**순서가 중요하다 — 마이그레이션이 이미지 배포보다 먼저다.** `app/main.py` 의 lifespan 이 `Base.metadata.create_all` 을 부르는데, Task 10 이 research 라우터를 등록하면 `models.research` 가 전이적으로 metadata 에 붙는다. 새 이미지를 먼저 띄우면 `create_all` 이 두 테이블을 만들어버리고, 그 뒤 `alembic upgrade head` 는 `DuplicateTable` 로 죽는다. 더 나쁜 건 `create_all` 이 만든 테이블에는 `server_default` 가 없어(모델은 `default=` 만 가진다) 마이그레이션이 만들었을 스키마와 미묘하게 다른 테이블이 운영에 남는다는 점이다.

- [ ] **Step 1: 마이그레이션 적용 (배포보다 먼저)**

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi alembic upgrade head
```

- [ ] **Step 2: 테이블 생성 확인**

```bash
docker exec nl-lib-postgres psql -U admin -d nl_lib -c "\d research_jobs" -c "\d research_steps"
```

- [ ] **Step 3: 이미지 빌드·배포**

`NL_LIB_FASTAPI_IMAGE` 를 `:latest` 로 맞춰 빌드한다(`recurring-gotchas.md` 3번 — `build_dev_images.sh` 는 `:dev` 만 만든다). 큰 이미지는 서버에서 `docker pull` 을 먼저 하고 Portainer 에서는 Redeploy 만 누른다(같은 문서 12번).

- [ ] **Step 4: 계획 수립 확인**

관리 API 는 게이트웨이에서 차단돼 있으므로 컨테이너 내부에서 호출한다(`bulk_ingest_runbook.md` §5-a).

```bash
docker exec nl-lib-fastapi curl -s -X POST http://localhost:8000/api/research -H 'Content-Type: application/json' -d '{"question":"공공도서관 서비스 품질 평가는 어떻게 연구되어 왔는가","params":{"max_subquestions":3,"max_recheck":1,"per_subq_top_k":8}}'
```

Expected: `{"job_id":"...","status":"created"}`

- [ ] **Step 5: 계획 확인 후 승인**

```bash
docker exec nl-lib-fastapi curl -s http://localhost:8000/api/research/<job_id>
```

`status` 가 `awaiting_approval` 이고 `plan` 에 하위질문 3개가 있어야 한다. 확인 후:

```bash
docker exec nl-lib-fastapi curl -s -X POST http://localhost:8000/api/research/<job_id>/approve -H 'Content-Type: application/json' -d '{}'
```

- [ ] **Step 6: 진행 중계 확인**

```bash
docker exec nl-lib-fastapi curl -N -s http://localhost:8000/api/research/<job_id>/stream
```

첫 줄에 `snapshot` 이 오고, 이어서 `search`·`critique` 이벤트가 흘러야 한다.

- [ ] **Step 7: 보고서 검증 — 인용 무결성**

```bash
docker exec nl-lib-fastapi curl -s http://localhost:8000/api/research/<job_id> | python -c "import json,sys,re; d=json.load(sys.stdin); r=d['report']; ids=set(r['evidence']); used=set(); [used.update(re.findall(r'\[(E\d+)\]', s['intro'])) for s in r['sections']]; [used.update(re.findall(r'\[(E\d+)\]', f['text'])) for s in r['sections'] for f in s['future']]; print('근거', len(ids), '사용된 마커', len(used), '미해석', used-ids); print('한계', r['limitations'])"
```

**`미해석` 이 빈 집합이어야 한다.** 하나라도 남으면 `bind_markers` 가 새는 것이니 멈추고 원인을 찾는다.

- [ ] **Step 8: 실측 기록**

실행 소요 시간, 하위질문별 근거 수, 한계 섹션 내용을 완료노트에 적는다. 이 값으로 `params` 기본값(특히 `per_subq_top_k`·`min_evidence_per_subq`)을 조정한다.

---

## 이 계획에서 다루지 않는 것

- **프론트엔드 전부** — round04b
- **인용 그래프** — `extra["references"]` entity resolution, 대회 이후
- **PDF 내보내기 · AI 생성 다이어그램 · 도서 코퍼스 · 다국어**
- **시연 분야 우선 인덱싱** — 운영 작업이며 코드와 독립. spec §8
- `app/api/admin.py` Milvus expression injection — 기존 이월 유지

## 알려진 미확정

- ~~`BookRepository.get_by_cnts_ids` 반환형~~ — **해소됨(2026-09-21).** `dict[str, BookOut]` 이고 `BookOut(BookBase)` 가 `title`·`personal_author`·`series_title`·`vol_issue`·`pub_date`·`kci_citations`·`grade` 를 전부 갖는다. ORM 직접 조회로 바꿀 필요 없다.
- **`uci`·`url` 컬럼이 `BookBase` 에 있다** — `extra` JSONB 에 없다고 외부 원문 링크가 불가능하다고 단정했던 것이 성급했다. 값이 채워져 있으면 인용 팝업의 `원문 보기` 를 자체 상세 페이지가 아니라 KCI 원문으로 보낼 수 있다. **실측 필요.**
- `pytest-asyncio` 설치 여부 미확인 (Task 9 Step 1)
- Celery 워커가 `q_llm` 큐를 소비하도록 이미 떠 있는지 확인 필요 — 안 떠 있으면 태스크가 큐에 쌓이기만 한다
- `redis.asyncio` 가 이미지에 포함돼 있는지 미확인 (Task 10 Step 7 에서 드러난다)
