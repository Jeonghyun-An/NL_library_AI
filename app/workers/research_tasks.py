"""research_tasks.py — 딥리서치 Celery 태스크

동기 워커에서 async 파이프라인을 돌린다. 이 파일이 이 코드베이스에서 워커가
async 코드를 부르는 첫 자리다(`app/workers/` 에 기존 asyncio 사용 0건). 그래서
루프와 세션을 다루는 규칙을 여기서 못박아 둔다 — 아래 _job_engine 주석.

상태 쓰기 규칙: 워커는 job ORM 객체에 대입하지 않는다. 모든 상태 전이는
_transition 의 조건부 UPDATE 로만 한다. 취소는 API 프로세스가 찍으므로, 조건 없이
쓰면 워커의 마지막 쓰기가 취소를 덮어 취소한 잡이 completed 로 되살아난다.
"""
import asyncio
import datetime as _dt
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import insert, select, text as sa_text, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.research import (
    JOB_STAGES, RUNNABLE_STATUSES, STATUS_CANCELED, STEP_KINDS, TERMINAL_STATUSES,
    ResearchJob, ResearchStep,
)
from services.research.relay import publish, publish_terminal
from services.research.runner import explore_subquestion
from services.research.state import (
    ResearchState, SubQuestion, merge_params, research_stats, restore_state, snapshot_state,
)
from services.research.synthesizer import SynthesisCanceled, synthesize
from workers.celery_app import celery_app

log = logging.getLogger(__name__)

# 5~7분이 설계값이고 종합까지 10분을 안 넘긴다. 30분이면 멈춘 것이다.
# 상한이 없으면 응답 없는 LLM 호출 하나가 워커 슬롯을 영구 점유한다.
SOFT_LIMIT = 1800
HARD_LIMIT = 2100

# 잡 본문의 자체 상한. 소프트 리밋 신호는 LLM 응답을 await 하는 동안(메인 스레드가
# 이벤트 루프의 select 안) 오면 코루틴이 아니라 asyncio.run 밖으로 튀어나가, 코루틴
# 안의 정리 코드가 하나도 돌지 않는다. 데드라인은 await 지점에서 CancelledError 로
# 끊으므로 확실히 잡힌다 — 소프트 리밋은 데드라인이 못 끊은 경우의 백스톱이다.
JOB_DEADLINE = SOFT_LIMIT - 300

# 하드 리밋보다 길어야 한다. 짧으면 아직 살아서 쓰고 있는 워커의 잡을 회수하고,
# 그 뒤 retry 한 새 실행과 옛 실행이 같은 잡에서 부딪힌다.
STALE_MINUTES = 45

TIMEOUT_ERROR = "시간 상한 초과 — 워커를 회수했다"
EMPTY_PLAN_ERROR = "계획에 하위질문이 없어 탐색하지 않았다 — 새 잡을 만든다"
_IN_FLIGHT = ("planning", "running")


def _job_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
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
    쪽 변환에 기대는 부분도 생긴다. 경계에서 한 번 변환하고 안쪽은 UUID 만 쓴다.
    """
    return uuid.UUID(str(job_id))


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _stage(stage: str) -> str:
    """JOB_STAGES 를 실제로 강제하는 유일한 지점.

    stage 오타는 재개 분기(stage == "explored")를 조용히 빗나가게 만든다 —
    예외도 안 나고 그냥 탐색을 처음부터 다시 돌 뿐이라 알아채기 어렵다.
    """
    assert stage in JOB_STAGES, f"알 수 없는 stage: {stage}"
    return stage


async def _next_seq(db: AsyncSession, job_id: uuid.UUID) -> int:
    """이어붙일 seq. 1 부터 다시 시작하면 uq_research_steps_job_seq 를 위반한다.

    재시도·재개는 정상 경로다(워커 사망 복구, 종합만 재실행). 그때마다
    IntegrityError 로 죽으면 복구 기능 자체가 동작하지 않는다.
    """
    row = await db.execute(sa_text(
        "SELECT coalesce(max(seq), -1) + 1 FROM research_steps WHERE job_id = :j"
    ), {"j": job_id})
    return int(row.scalar_one())


@dataclass(frozen=True)
class _StepRef:
    """열린 step 의 id 와, 닫을 때 화면에 다시 알릴 머리 정보.

    ORM 객체를 들고 다니지 않는 이유: 예외 핸들러는 rollback 부터 하는데, rollback 은
    세션의 모든 인스턴스를 만료시켜 그 뒤 속성 접근이 async 세션에서 MissingGreenlet
    으로 터진다. 평범한 값 객체는 rollback 과 무관하다.
    """
    id: int
    job_id: uuid.UUID
    seq: int
    kind: str
    title: str
    subq_idx: int | None
    detail: str | None

    def event(self, status: str, result: dict | None = None) -> dict:
        # 이벤트 자체의 kind 와 겹치지 않게 step_kind 로 싣는다
        payload = {
            "seq": self.seq, "step_kind": self.kind, "subq_idx": self.subq_idx,
            "title": self.title, "detail": self.detail, "status": status,
        }
        if result is not None:
            payload["result"] = result
        return payload


async def _step(
    db: AsyncSession, job_id: uuid.UUID, seq: int, kind: str, title: str, *,
    subq_idx: int | None = None, detail: str | None = None,
) -> _StepRef:
    # STEP_KINDS 를 실제로 강제하는 유일한 지점. 상수만 정의하고 아무 데서도
    # 쓰지 않으면 장식이 되고, 오타난 kind 가 프론트 분기를 조용히 빗나간다.
    assert kind in STEP_KINDS, f"알 수 없는 kind: {kind}"
    step_id = (await db.execute(
        insert(ResearchStep).values(
            job_id=job_id, seq=seq, kind=kind, title=title,
            subq_idx=subq_idx, detail=detail, status="running",
        ).returning(ResearchStep.id)
    )).scalar_one()
    await db.commit()
    step = _StepRef(step_id, job_id, seq, kind, title, subq_idx, detail)
    # 커밋 뒤에 알린다. 먼저 알리면 그 틈에 재접속한 화면의 스냅샷에는 없는 단계가
    # 이벤트로만 도착한다.
    await publish(job_id, "step", step.event("running"))
    return step


async def _finish(
    db: AsyncSession, step: _StepRef, status: str, result: dict | None = None,
    event_result: dict | None = None,
) -> None:
    """단계를 닫는다. event_result 를 주면 알리는 step 이벤트에는 저장한 result 대신 그것을
    싣는다 — 종합 단계의 절 미리보기는 synth 이벤트가 절마다 이미 날랐다."""
    result = result or {}
    await db.execute(
        update(ResearchStep).where(ResearchStep.id == step.id)
        .values(status=status, result=result, finished_at=_now())
    )
    await db.commit()
    # event_result 가 없으면 저장한 result 를 그대로 싣는다 — 라이브로 본 장면과 다시 연 장면이
    # 같아야 한다. 종합 단계는 가벼운 값을 싣지만 빠진 절 내용은 synth 이벤트가 이미 날랐다.
    await publish(step.job_id, "step", step.event(
        status, result if event_result is None else event_result))


async def _save_progress(
    db: AsyncSession, step: _StepRef, result: dict, event_result: dict | None = None,
) -> None:
    """도는 중인 단계의 result 를 지금까지의 진행으로 덮어쓰고 알린다.

    단계를 닫을 때만 쓰면 탐색 중에 새로 연 화면·재접속한 화면이 그 단계의 앞 회차와
    카운터를 잃는다. 실패해도 탐색은 계속한다 — 이 기록은 화면 복원용이고, 단계를 닫을
    때 _finish 가 최종 결과를 다시 쓴다.

    event_result 를 주면 알리는 step 이벤트에는 그것을 싣는다. 종합 단계는 절이 쌓일수록
    result 가 커져, 전부를 매번 알리면 이미 보낸 절 내용을 절마다 다시 나른다.
    """
    try:
        await db.execute(
            update(ResearchStep).where(ResearchStep.id == step.id).values(result=result)
        )
        await db.commit()
    except SoftTimeLimitExceeded:
        raise
    except Exception:
        log.warning("[research] 진행 기록 실패 job=%s seq=%s", step.job_id, step.seq,
                    exc_info=True)
        # 깨진 트랜잭션을 되돌려 두지 않으면 다음 회차의 검색 조회가 여기서 터진다
        await db.rollback()
        return
    await publish(step.job_id, "step", step.event(
        "running", result if event_result is None else event_result))


def _search_progress(state: ResearchState, subq: SubQuestion) -> dict:
    # 목록을 복사한다 — 이어지는 회차가 같은 목록에 덧붙여도 저장한 값이 바뀌지 않게
    return {"rounds": list(subq.rounds), "counters": research_stats(state)}


def _round_emitter(
    db: AsyncSession, job_id: uuid.UUID, state: ResearchState, subq: SubQuestion,
    step: _StepRef,
) -> Callable[[str, dict], Awaitable[None]]:
    """러너 이벤트를 흘리고, 자기점검(회차의 끝)마다 진행을 단계 result 에 남긴다."""
    async def _emit(kind: str, payload: dict) -> None:
        await publish(job_id, kind, payload)
        if kind == "critique":
            await _save_progress(db, step, _search_progress(state, subq))
    return _emit


@dataclass
class _SynthProgress:
    """synthesize 의 on_section 콜백. 절 진행을 synth 이벤트로 흘리면서 종합 단계
    result 에 남길 값도 모은다 — 실패·취소로 끝나도 거기까지의 진행이 남는다.
    step 이 있으면 절이 바뀔 때마다 도는 중인 단계 result 에도 남긴다.

    다 쓴 절의 미리보기(section)와 그 근거(evidence)도 모은다. 작성 중 화면이 그것을 초안으로
    보여 주고, 새로고침·재접속한 화면은 단계 result 에서 이미 쓴 절을 되살린다."""
    job_id: uuid.UUID
    db: AsyncSession | None = None
    step: _StepRef | None = None
    total: int = 0
    statuses: dict[int, str] = field(default_factory=dict)
    headings: list[str] = field(default_factory=list)
    # 절 순번 → {subq_idx, heading, started_at, duration_ms, section}
    details: dict[int, dict] = field(default_factory=dict)
    evidence: dict[str, dict] = field(default_factory=dict)
    # 소요 시간은 단조 시계로 잰다 — 벽시계는 시각 보정으로 뒤로 갈 수 있다. 테스트가 바꿔 끼운다.
    clock: Callable[[], float] = time.monotonic
    _started: dict[int, float] = field(default_factory=dict, init=False, repr=False)

    async def __call__(self, idx: int, total: int, status: str, info: dict | None = None) -> None:
        self.total = total
        self.statuses[idx] = status
        payload = {"section_idx": idx, "total": total, "status": status}
        if info is not None:
            payload.update(self._record(idx, status, info))
        await publish(self.job_id, "synth", payload)
        if self.step is not None:
            # 저장에는 미리보기를 싣고 알림에서는 뺀다 — 절 내용은 위 synth 이벤트가 한 번만 나른다
            await _save_progress(self.db, self.step, self.result(),
                                 event_result=self.result(previews=False))

    def _record(self, idx: int, status: str, info: dict) -> dict:
        """info 를 절 기록에 남기고, synth 이벤트에 더할 값을 돌려준다."""
        self.headings = list(info.get("headings") or self.headings)
        extra = {"subq_idx": info.get("subq_idx"), "heading": info.get("heading"),
                 "headings": self.headings}
        detail = self.details.setdefault(idx, {})
        detail.update(subq_idx=extra["subq_idx"], heading=extra["heading"])
        if status == "running":
            self._started[idx] = self.clock()
            detail["started_at"] = extra["started_at"] = _now().isoformat()
            return extra
        started = self._started.get(idx)
        if started is not None:
            detail["duration_ms"] = extra["duration_ms"] = int((self.clock() - started) * 1000)
        if "section" in info:
            detail["section"] = extra["section"] = info["section"]
        if "evidence" in info:
            self._merge_evidence(info["evidence"])
            extra["evidence"] = info["evidence"]
        return extra

    def _merge_evidence(self, more: dict[str, dict]) -> None:
        """끝난 절들의 근거를 합친다. 한 논문이 두 절에 실리면 절마다 제 대목만 가져오므로
        대목을 chunk_id 로 합친다 — 덮어쓰면 앞 절 인용칩의 대목이 사라진다. 들고 있던 값을
        고치지 않고 새 dict 로 바꿔 넣는다 — 앞서 넘긴 result 가 뒤따라 바뀌지 않게."""
        for eid, ev in more.items():
            have = self.evidence.get(eid)
            if have is None:
                self.evidence[eid] = {**ev, "chunks": list(ev["chunks"])}
                continue
            seen = {c["chunk_id"] for c in have["chunks"]}
            chunks = have["chunks"] + [c for c in ev["chunks"] if c["chunk_id"] not in seen]
            self.evidence[eid] = {
                **have, "chunks": sorted(chunks, key=lambda c: c["score"], reverse=True)}

    def result(self, *, previews: bool = True, **extra: object) -> dict:
        """종합 단계 result. previews=False 면 절 미리보기(sections[].section)와 근거(evidence)를
        뺀다 — 알리는 step 이벤트와, 완료로 닫는 기록(최종 보고서와 중복)에 쓴다."""
        sections = []
        for i, status in sorted(self.statuses.items()):
            d = self.details.get(i, {})
            entry = {"idx": i, "status": status, "subq_idx": d.get("subq_idx"),
                     "heading": d.get("heading"), "started_at": d.get("started_at"),
                     "duration_ms": d.get("duration_ms")}
            if previews and "section" in d:
                entry["section"] = d["section"]
            sections.append(entry)
        out = {**extra, "sections_total": self.total, "headings": list(self.headings),
               "sections": sections}
        if previews and self.evidence:
            out["evidence"] = dict(self.evidence)
        return out


async def _announce(job_id: uuid.UUID, status: str, stage: str) -> None:
    """상태 전이를 알린다. 전이가 성공한 뒤에만 부른다 — 취소에 진 전이를 알리면
    화면이 취소된 잡을 진행 중으로 그린다. 종료 상태는 publish_terminal 이 알린다."""
    await publish(job_id, "status", {"status": status, "stage": stage})


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


async def _transition(
    db: AsyncSession, job_id: uuid.UUID, *, expect: tuple[str, ...], **values: object,
) -> bool:
    """조건부 상태 전이. 잡이 기대한 상태가 아니면(대개 취소) 아무것도 안 쓰고 False."""
    res = await db.execute(
        update(ResearchJob)
        .where(ResearchJob.id == job_id, ResearchJob.status.in_(expect))
        .values(**values)
    )
    await db.commit()
    return res.rowcount == 1


async def _claim(db: AsyncSession, job_id: uuid.UUID, *, allowed: tuple[str, ...], to: str) -> bool:
    """조건부 선점. 못 잡으면 False.

    Celery 는 at-least-once 다 — 워커가 ack 전에 죽으면 같은 잡이 다시 배달된다.
    무조건 status="running" 을 대입하면 그때 같은 잡이 두 벌 돌아 step 이 중복되고
    LLM 비용이 두 배가 되며, 두 실행이 같은 job 행을 서로 덮어쓴다.
    """
    return await _transition(db, job_id, expect=allowed, status=to, started_at=_now())


async def _current_status(db: AsyncSession, job_id: uuid.UUID) -> str | None:
    """DB 의 현재 상태. 읽고 바로 트랜잭션을 닫는다.

    이 조회는 LLM 호출 직전(절 사이·하위질문 사이)에 돈다. 트랜잭션을 열어 둔 채
    LLM 을 기다리면 그동안 잡은 잠금이 FastAPI 기동의 ALTER TABLE 을 막는다.
    """
    res = await db.execute(select(ResearchJob.status).where(ResearchJob.id == job_id))
    status = res.scalar_one_or_none()
    await db.commit()
    return status


async def _is_cancelled(db: AsyncSession, job_id: uuid.UUID) -> bool:
    return await _current_status(db, job_id) == STATUS_CANCELED


async def _stopped(db: AsyncSession, job_id: uuid.UUID) -> dict:
    """누가 먼저 상태를 바꿨다(대개 취소, 드물게 회수). 결과를 버리고 멈춘다."""
    status = await _current_status(db, job_id)
    log.info("[research] 잡 상태가 바뀌어 멈춘다 job=%s status=%s", job_id, status)
    if status in TERMINAL_STATUSES:
        await publish_terminal(job_id, status)
    return {"job_id": str(job_id), "status": status}


async def _end_failed(
    db: AsyncSession, job_id: uuid.UUID, error: str, *, expect: tuple[str, ...] = ("running",),
) -> dict:
    """stage·state_snapshot 은 건드리지 않는다 — retry 가 거기서 이어받는다."""
    if not await _transition(db, job_id, expect=expect, status="failed",
                             last_error=error[:1000], finished_at=_now()):
        return await _stopped(db, job_id)
    await publish_terminal(job_id, "failed", error)
    return {"job_id": str(job_id), "status": "failed"}


async def _close_orphan_steps(db: AsyncSession, job_id: uuid.UUID, error: str) -> None:
    """끝난 잡에 running 으로 남은 step 을 닫는다.

    잡이 아직 진행 중이면 건드리지 않는다 — 회수 뒤 retry 한 새 실행의 step 일 수 있다.

    result 는 바꾸지 않고 error 만 더한다(jsonb ||). 도는 단계에는 _save_progress 가
    쌓은 rounds·counters·sections 가 있다 — 통째로 바꾸면 라이브로 본 회차·절이 다시 연
    화면에서 사라진다. 회수기(reap_stale_research)도 같은 방식으로 합친다.
    """
    await db.execute(
        update(ResearchStep)
        .where(
            ResearchStep.job_id == job_id,
            ResearchStep.status == "running",
            select(ResearchJob.id).where(
                ResearchJob.id == job_id, ResearchJob.status.in_(TERMINAL_STATUSES),
            ).exists(),
        )
        .values(status="failed", result=ResearchStep.result.concat({"error": error[:500]}),
                finished_at=_now())
    )
    await db.commit()


async def _fail_open_job(
    Session: async_sessionmaker[AsyncSession], job_id: uuid.UUID, error: str,
) -> str | None:
    """새 세션으로 진행 중인 잡을 실패로 떨어뜨린다 — 원래 세션은 깨졌을 수 있다."""
    async with Session() as db:
        failed = await _transition(db, job_id, expect=_IN_FLIGHT, status="failed",
                                   last_error=error[:1000], finished_at=_now())
        await _close_orphan_steps(db, job_id, error)
        status = await _current_status(db, job_id)
    if failed:
        await publish_terminal(job_id, "failed", error)
    return status


async def _mark_timed_out(job_id: str) -> dict:
    """stage 는 건드리지 않는다 — 탐색까지 끝낸 뒤 종합에서 시간을 넘긴 잡은
    재시도가 스냅샷에서 이어받을 수 있어야 한다."""
    jid = _job_uuid(job_id)
    log.error("[research] 시간 상한 초과 job=%s", jid)
    engine, Session = _job_engine()
    try:
        status = await _fail_open_job(Session, jid, TIMEOUT_ERROR)
    finally:
        await engine.dispose()
    return {"job_id": str(jid), "status": status}


def _wiped_out(state: ResearchState) -> bool:
    """모든 하위질문이 오류로 끝났고 건진 근거도 없다 — 연구 결과가 아니라 장애다.

    근거를 하나라도 모은 채 실패한 하위질문은 전멸로 치지 않는다. synthesizer 가 그
    근거로 절을 쓰고 한계에 "오류로 중단"을 적는다 — 잡째 실패시키면 실재하는 근거를 버린다.
    """
    return all(sq.failed and not sq.evidence_ids for sq in state.subquestions)


async def _within_deadline(body: Callable[[str], Awaitable[dict]], job_id: str) -> dict:
    deadline = asyncio.timeout(JOB_DEADLINE)
    try:
        async with deadline:
            return await body(job_id)
    except TimeoutError:
        if not deadline.expired():
            raise
        return await _mark_timed_out(job_id)


def _run_job(body: Callable[[str], Awaitable[dict]], job_id: str) -> dict:
    """잡 전체를 이벤트 루프 하나로 돌린다. 단계마다 asyncio.run 을 부르지 않는
    이유는 _job_engine 주석에 있다."""
    try:
        return asyncio.run(_within_deadline(body, job_id))
    except SoftTimeLimitExceeded:
        # 루프가 이미 닫혔다 — 정리는 새 루프·새 엔진으로 한다
        return asyncio.run(_mark_timed_out(job_id))


@celery_app.task(name="tasks.plan_deep_research", queue=get_settings().RESEARCH_PLAN_QUEUE,
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def plan_deep_research(job_id: str) -> dict:
    """계획만 세우고 승인 대기 상태로 멈춘다."""
    return _run_job(_plan_deep_research, job_id)


async def _plan_deep_research(job_id: str) -> dict:
    from services.research.planner import make_plan

    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            if not await _claim(db, jid, allowed=("created",), to="planning"):
                log.warning("[research] 이미 계획 중이거나 계획된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            job = await db.get(ResearchJob, jid)
            question, params, stage = job.question, merge_params(job.params or {}), job.stage
            seq = await _next_seq(db, jid)
            await db.commit()      # 읽기 트랜잭션을 닫고 LLM 으로 간다
            await _announce(jid, "planning", stage)

            step = await _step(db, jid, seq, "plan", "연구 계획 수립",
                               detail="질문을 하위질문으로 분해하는 중입니다")
            try:
                plan = await make_plan(question, params=params)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                await _finish(db, step, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e), expect=("planning",))

            await _finish(db, step, "done", {"subquestions": plan})
            if not await _transition(db, jid, expect=("planning",), status="awaiting_approval",
                                     plan=plan, stage=_stage("planned")):
                return await _stopped(db, jid)
            await _announce(jid, "awaiting_approval", "planned")
            return {"job_id": str(jid), "status": "awaiting_approval"}

    except SoftTimeLimitExceeded:
        raise
    except Exception as e:
        log.exception("[research] 계획 태스크 오류 job=%s", jid)
        return {"job_id": str(jid), "status": await _fail_open_job(Session, jid, str(e))}
    finally:
        await engine.dispose()


@celery_app.task(name="tasks.run_deep_research", queue=get_settings().RESEARCH_QUEUE,
                 soft_time_limit=SOFT_LIMIT, time_limit=HARD_LIMIT)
def run_deep_research(job_id: str) -> dict:
    return _run_job(_run_deep_research, job_id)


async def _run_deep_research(job_id: str) -> dict:
    jid = _job_uuid(job_id)
    engine, Session = _job_engine()
    try:
        async with Session() as db:
            # 재개 가능한 상태만 받는다. running 인 잡을 다시 받으면 재배달이다.
            if not await _claim(db, jid, allowed=RUNNABLE_STATUSES, to="running"):
                log.warning("[research] 이미 처리 중이거나 처리된 잡 — 건너뛴다 job=%s", job_id)
                return {"job_id": job_id, "status": "skipped"}

            job = await db.get(ResearchJob, jid)
            stage, snapshot = job.stage, job.state_snapshot
            question, params, plan = job.question, job.params, job.plan
            seq = await _next_seq(db, jid)
            await db.commit()
            await _announce(jid, "running", stage)

            # ── 탐색: stage 가 이미 explored 면 건너뛰고 스냅샷을 되살린다 ──
            state = restore_state(str(jid), snapshot) if stage == "explored" and snapshot else None
            if state is not None and _wiped_out(state):
                # 전멸 가드가 생기기 전에 남은 스냅샷이다. 거기서 종합만 다시 하면
                # 절 0개짜리 보고서가 completed 로 남아 retry 도 막힌다.
                log.warning("[research] 전멸 스냅샷 — 탐색부터 다시 한다 job=%s", job_id)
                state = None
            if state is not None:
                log.info("[research] 탐색 건너뜀 — 스냅샷에서 재개 job=%s", job_id)
            else:
                state = ResearchState(
                    job_id=str(jid), question=question, params=merge_params(params or {}),
                )
                state.subquestions = [SubQuestion(idx=i, text=t) for i, t in enumerate(plan or [])]
                if not state.subquestions:
                    # 아래 전멸 판정(all)은 빈 목록에도 참이다. 여기서 끊지 않으면 계획이
                    # 빈 잡이 "탐색이 오류로 실패"로 남아 검색 장애로 오진된다.
                    return await _end_failed(db, jid, EMPTY_PLAN_ERROR)
                state.corpus_range = await _corpus_range(db)

                for subq in state.subquestions:
                    if await _is_cancelled(db, jid):
                        return await _stopped(db, jid)

                    step = await _step(
                        db, jid, seq, "search", subq.text, subq_idx=subq.idx,
                        detail=f"'{subq.text}' 관련 논문을 찾기 위해 검색 중입니다",
                    )
                    seq += 1
                    try:
                        await explore_subquestion(
                            state, subq, db=db,
                            emit=_round_emitter(db, jid, state, subq, step),
                        )
                    except SoftTimeLimitExceeded:
                        # except Exception 보다 먼저 와야 한다 — SoftTimeLimitExceeded 도
                        # Exception 이라 거기서 삼키면 남은 하위질문을 계속 돌다 하드 리밋에 죽는다.
                        raise
                    except Exception as e:
                        # 부분 실패는 전체 실패가 아니다 — 나머지 하위질문은 계속한다.
                        # 다만 failed 를 남겨야 보고서가 이걸 "근거 없음"(연구 결과)이
                        # 아니라 "오류로 확인 못함"(시스템 장애)으로 쓴다.
                        log.exception("[research] 하위질문 실패 job=%s idx=%s", jid, subq.idx)
                        await db.rollback()     # DB 오류면 트랜잭션이 깨져 있어 기록부터 터진다
                        subq.failed = True
                        await _finish(db, step, "failed", {
                            "error": str(e)[:500], **_search_progress(state, subq),
                        })
                    else:
                        await _finish(db, step, "done", {
                            "queries": subq.queries, "adopted": len(subq.evidence_ids),
                            "verdict": subq.verdict, "note": subq.note,
                            "parse_failed": subq.parse_failed, "capped": subq.capped,
                            **_search_progress(state, subq),
                        })

                # 전멸은 연구 결과가 아니라 장애다. 체크포인트를 남기면 retry 가 전부
                # 실패한 스냅샷으로 종합만 다시 해 빈 보고서를 completed 로 저장한다.
                if _wiped_out(state):
                    return await _end_failed(db, jid, "모든 하위질문 탐색이 오류로 실패했다")

                # 체크포인트. 여기까지가 비싼 구간이고, 종합은 다시 돌려도 싸다.
                if not await _transition(db, jid, expect=("running",), stage=_stage("explored"),
                                         state_snapshot=snapshot_state(state)):
                    return await _stopped(db, jid)
                await _announce(jid, "running", "explored")

            if await _is_cancelled(db, jid):
                return await _stopped(db, jid)

            # ── 종합 ──
            step = await _step(db, jid, seq, "synthesize", "보고서 종합")
            progress = _SynthProgress(jid, db=db, step=step)
            try:
                report = await synthesize(state, should_stop=lambda: _is_cancelled(db, jid),
                                          on_section=progress)
            except SynthesisCanceled:
                # 실패·취소로 닫을 때는 절 미리보기를 남긴다 — 멈춘 초안을 보여 주고 내려받는 원천이다
                await _finish(db, step, "failed", progress.result(error="취소됨"),
                              event_result=progress.result(error="취소됨", previews=False))
                return await _stopped(db, jid)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                # stage 는 explored 로 남는다 → POST /api/research/{job_id}/retry 가
                # 탐색을 건너뛰고 여기부터 다시 온다.
                log.exception("[research] 종합 실패 job=%s", jid)
                await db.rollback()
                error = str(e)[:500]
                await _finish(db, step, "failed", progress.result(error=error),
                              event_result=progress.result(error=error, previews=False))
                return await _end_failed(db, jid, str(e))

            # 보고서를 먼저 저장하고 단계를 닫는다. 단계를 먼저 done(미리보기 없음)으로 닫으면
            # 전이가 질 때 초안을 되살리려 한 번 더 닫아야 하고, 그 사이 데드라인에 걸리면 보고서도
            # 초안도 없다. 이 순서에서는 전이와 단계 닫기 사이 잠깐 잡은 completed·단계는 running
            # 으로 보인다 — 그 틈에 끊겨도 보고서는 저장됐고 _close_orphan_steps 가 단계를 닫는다.
            if not await _transition(db, jid, expect=("running",), status="completed",
                                     report=report, stage=_stage("synthesized"),
                                     finished_at=_now()):
                # 대개 마지막 절을 쓰는 도중에 들어온 취소다(synthesize 는 LLM 을 부르기 직전에만
                # 멈춤을 본다). 보고서가 버려지므로 미리보기를 남겨 멈춘 초안으로 닫는다.
                await _finish(db, step, "failed", progress.result(error="취소됨"),
                              event_result=progress.result(error="취소됨", previews=False))
                return await _stopped(db, jid)
            # 완료로 닫을 때는 미리보기를 지운다 — 최종 보고서(research_jobs.report)와 같은 내용이다
            await _finish(db, step, "done", progress.result(previews=False))
            await publish_terminal(jid, "completed")
            return {"job_id": str(jid), "status": "completed"}

    except SoftTimeLimitExceeded:
        raise
    except Exception as e:
        # 가드 밖 예외(스냅샷 복원·수록 범위·step 기록)로 태스크만 죽으면 잡이 running 에
        # 묶여 SSE 는 ping 만 보내고 사용자는 retry 도 못 한 채 회수기를 기다린다.
        log.exception("[research] 실행 태스크 오류 job=%s", jid)
        return {"job_id": str(jid), "status": await _fail_open_job(Session, jid, str(e))}
    finally:
        # 루프가 죽기 전에 커넥션을 닫는다. 빠뜨리면 다음 잡이 남은 커넥션을 만난다.
        await engine.dispose()


@celery_app.task(name="tasks.reap_stale_research", queue="q_control")
def reap_stale_research() -> dict:
    """멈춰버린 리서치를 실패로 떨어뜨린다.

    정상 잡은 JOB_DEADLINE 에서 스스로 실패를 남긴다. 그래도 planning·running 에
    남은 잡은 워커 프로세스가 죽은 것이다.

    approved·queued 는 회수하지 않는다 — 아직 워커가 집지 않은 정상 대기 상태다.
    """
    db = SyncSessionLocal()
    try:
        # coalesce 가 필요한 이유: planning 단계에서 워커가 죽으면 started_at 이 NULL
        # 일 수 있고, NULL 비교는 NULL 이라 조건이 참이 되지 않아 영원히 회수되지 않는다.
        # 회수한 잡의 running step 도 같은 문장에서 닫는다 — 따로 두면 잡은 failed 인데
        # 마지막 step 은 자기 updated_at 기준으로 한참 더 running 으로 보인다.
        n_jobs, n_job_steps = db.execute(sa_text(
            "WITH reaped AS ("
            "  UPDATE research_jobs SET status = 'failed', "
            "         last_error = 'stale — 워커 응답 없음', finished_at = now() "
            "  WHERE status IN ('planning', 'running') "
            "    AND coalesce(started_at, created_at) < now() - make_interval(mins => :m) "
            "  RETURNING id"
            "), closed AS ("
            "  UPDATE research_steps SET status = 'failed', "
            "         result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "         finished_at = now() "
            "  WHERE status = 'running' AND job_id IN (SELECT id FROM reaped) "
            "  RETURNING id"
            ") SELECT (SELECT count(*) FROM reaped), (SELECT count(*) FROM closed)"
        ), {"m": STALE_MINUTES}).one()

        steps = db.execute(sa_text(
            "UPDATE research_steps SET status = 'failed', "
            "       result = result || '{\"error\": \"stale — 워커 응답 없음\"}'::jsonb, "
            "       finished_at = now() "
            "WHERE status = 'running' "
            "  AND updated_at < now() - make_interval(mins => :m) "
            "RETURNING job_id"
        ), {"m": STALE_MINUTES}).fetchall()

        db.commit()
        return {"jobs": n_jobs, "steps": n_job_steps + len(steps)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
