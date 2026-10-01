"""
job_runtime.py — 배치 잡 레이어 (단계 태스크 + 디스패처 + stale 복구)

구성:
  stage_extract / stage_summarize / stage_embed_index / stage_finalize
      : stages.run_* 의 thin wrapper — 아이템 상태 전이, 타이밍, error_group 기록
  dispatch_job_items (beat 30s)
      : running 잡마다 high_water 까지 pending 아이템을 단계 체인으로 디스패치
        + stale 아이템 복구 + 잡 완료 판정
  cleanup_temp_files (beat 1h)
      : 임시 다운로드/완료 잡 아티팩트 정리 + Milvus 주기 flush

핵심 규칙:
  - item.stage  = 마지막 완료된 체크포인트 → 재시도는 그 다음 단계부터 체인 구성
  - item.status = 실행 상태. 자동 재시도: failed && attempt < max_attempts 인 아이템을
    디스패처가 다시 픽업 (수동 재시도 API는 status='pending' + attempt 리셋).
    attempt 번째 실패 뒤에는 INGEST_RETRY_BACKOFF_SECONDS 만큼 기다렸다 집는다
  - 실행 토큰: 디스패처가 체인을 보낼 때마다 새 meta.run_token 을 적고 모든 단계에 넘긴다.
    단계 래퍼는 토큰이 다르거나·이미 지난 단계거나·락 경합이면 Ignore 로 체인을 멈춘다
    (stale 복구 전의 옛 체인·재전달 메시지가 같은 아이템을 다시 돌지 못하게 — 함정 16)
"""
import datetime as _dt
import functools
import logging
import os
import time
import uuid

from celery import chain
from celery.exceptions import Ignore
from sqlalchemy import and_, or_, true

from core.config import get_settings
from core.lock import BookLock
from db.postgres import SyncSessionLocal
from models.ingest_job import IngestJob, IngestJobItem
from services.ingestion.stages import (
    CHECKPOINT_TO_REMAINING,
    STAGE_CHECKPOINT,
    STAGE_FUNCS,
    StageContext,
    StageError,
)
from workers.celery_app import celery_app

log = logging.getLogger(__name__)
cfg = get_settings()


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _stage_timeout(stage_name: str) -> int:
    return {
        "extract": cfg.INGEST_STAGE_TIMEOUT_EXTRACT,
        "summarize": cfg.INGEST_STAGE_TIMEOUT_SUMMARIZE,
        "embed_index": cfg.INGEST_STAGE_TIMEOUT_EMBED,
        "finalize": cfg.INGEST_STAGE_TIMEOUT_FINALIZE,
    }[stage_name]


# 큐에서 기다리는 아이템의 stale 상한(초) — 디스패치 뒤 첫 단계를 기다리는 dispatched 와,
# 한 단계를 끝내고 다음 단계 큐를 기다리는 running(meta.stage_running 없음)에 쓴다. 실행 중인
# 단계는 _stage_timeout 으로 따로 잰다. 기본 14400초(4시간)는 broker visibility_timeout
# 7200초(workers/celery_app.py)의 2배다 — 워커가 받은 채 죽어 ack 되지 않은 메시지가 7200초 뒤
# 재전달돼 다시 집힐 때까지 기다린다.
DISPATCH_STALE_SECONDS = cfg.DISPATCH_STALE_SECONDS

# 같은 코드로 다시 해도 결과가 같은 실패 — 자동 재시도하지 않는다(attempt 를 한도로 올린다)
NO_RETRY_GROUPS = frozenset({"no_text"})


def classify_error(exc: BaseException) -> str:
    """예외 → error_group 분류 (대시보드의 실패 그룹/일괄 재시도 단위)."""
    if isinstance(exc, StageError):
        return exc.error_group
    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return "llm_timeout"
        if isinstance(exc, httpx.HTTPStatusError):
            return "llm_error"
        if isinstance(exc, httpx.HTTPError):
            return "llm_error"
    except ImportError:
        pass
    name = type(exc).__name__
    msg = str(exc).lower()
    if "milvus" in msg or name.lower().startswith("milvus"):
        return "milvus_error"
    if name == "S3Error" or "minio" in msg:
        return "minio_error"
    if "vlm" in msg:
        return "vlm_error"
    return "unknown"


# ── 단계 태스크 공통 래퍼 ─────────────────────────────────────


def _skip_reason(stage_name: str, item, job, run_token: str | None) -> str | None:
    """이 단계 메시지를 실행하지 않을 이유. 이유가 있으면 _run_stage 가 체인을 멈춘다."""
    if item is None:
        return "아이템 없음"
    if item.status == "canceled" or (job is not None and job.status == "canceled"):
        return "취소됨"
    current = (item.meta or {}).get("run_token")
    if run_token is not None and run_token != current:
        return f"실행 토큰 불일치(메시지 {run_token[:8]}, 아이템 {str(current)[:8]}) — 옛 체인"
    if run_token is None and current:
        return "토큰 없는 옛 메시지인데 아이템에는 실행 토큰이 있다 — 새 체인이 떴다"
    if item.status == "done":
        return "이미 완료(done)"
    if stage_name not in CHECKPOINT_TO_REMAINING.get(item.stage, list(STAGE_CHECKPOINT)):
        return f"이미 지난 단계(체크포인트 {item.stage})"
    return None


def _run_stage(
    stage_name: str, item_id: int, celery_task_id: str | None, run_token: str | None = None,
) -> dict:
    """단계 하나를 실행한다. 실행하지 않을 때는 Ignore 를 던져 체인을 멈춘다.

    Ignore 는 Exception 의 하위라 아래 except Exception 안에서 던지면 실패로 기록된다 —
    그래서 Ignore 는 모두 그 try 밖에서 던진다. Celery 는 Ignore 를 던진 태스크의 상태를
    남기지 않고 메시지를 ack 하며, 체인의 다음 단계는 성공했을 때만 보낸다.

    첫 읽기의 토큰 대조는 그 순간의 판단이다. 단계가 도는 동안 새 체인이 토큰을 바꿀 수 있어
    (디스패처의 재디스패치·stale 복구) 시작·성공·실패 기록마다 _update_item 이 토큰을 다시 대조한다.
    달라졌으면 아무것도 쓰지 않고, 시작 기록이면 실행 안 함, 성공 기록이면 체인 정지(Ignore),
    실패 기록이면 예외만 그대로 올린다. 토큰 없는 옛 메시지(run_token=None)는 대조 없이 쓴다.
    """
    from workers.tasks import _set_ingest_state

    db = SyncSessionLocal()
    try:
        # FOR UPDATE: 디스패처는 메시지를 보낸 뒤 루프 끝에서 토큰을 커밋한다. 그 전에 읽으면
        # 옛 토큰을 보고 새 체인을 멈추므로, 디스패처의 행 잠금이 풀릴 때까지 기다렸다 읽는다
        item = db.query(IngestJobItem).filter_by(id=item_id).with_for_update().first()
        job = db.query(IngestJob).filter_by(id=item.job_id).first() if item else None
        reason = _skip_reason(stage_name, item, job, run_token)
        if reason:
            book = item.book_id if item else "-"
            log.warning(f"[{book}] item={item_id} {stage_name} 실행 안 함 — {reason} → 체인 정지")
            raise Ignore(reason)
        book_id = item.book_id
        source_key = item.source_key
        params = dict(job.params or {}) if job else {}
        item_meta = dict(item.meta or {})
    finally:
        db.close()

    max_attempts = int(params.get("max_attempts") or cfg.INGEST_MAX_ATTEMPTS)
    timeout = _stage_timeout(stage_name)
    lock = BookLock(book_id, ttl=timeout)
    if not lock.acquire():
        # 다른 워커가 이 문서를 처리 중이다. pending 으로 되돌리면 디스패처가 새 토큰으로 다시
        # 보내 락을 쥔 체인의 다음 단계를 끊고 경합을 되풀이한다 — 상태는 그대로 두고 이 체인만
        # 멈춘다. 아이템이 그대로 멈춰 있으면 stale 복구가 회수한다
        log.warning(f"[{book_id}] item={item_id} {stage_name} 실행 안 함 — 락 경합 → 체인 정지")
        raise Ignore("락 경합")

    t0 = time.monotonic()
    started = _update_item(
        item_id,
        status="running",
        celery_task_id=celery_task_id,
        set_started=True,
        # stale 판정이 실행 시간을 이 시각부터 잰다 — 끝나면 stage_running 을 지운다
        meta_update={"stage_running": stage_name, "stage_started_at": _now().isoformat()},
        expect_token=run_token,
    )
    if not started:
        # 첫 읽기와 이 기록 사이에 새 체인이 토큰을 바꿨다 — 단계를 돌리지 않는다. 쥔 락은 풀어야
        # 새 체인의 같은 단계가 락 경합으로 막히지 않는다
        lock.release()
        log.warning(f"[{book_id}] item={item_id} {stage_name} 실행 안 함 — 실행 토큰 불일치(시작 기록) → 체인 정지")
        raise Ignore("실행 토큰 불일치(시작 기록)")
    if stage_name == "extract":
        _set_ingest_state(book_id, "processing", task_id=celery_task_id)

    try:
        ctx = StageContext(
            book_id=book_id,
            source_key=source_key,
            job_item_id=item_id,
            params=params,
            item_meta=item_meta,
        )
        result = STAGE_FUNCS[stage_name](ctx) or {}
        elapsed = round(time.monotonic() - t0, 1)

        is_final = stage_name == "finalize"
        recorded = _update_item(
            item_id,
            stage=STAGE_CHECKPOINT[stage_name],
            status="done" if is_final else "running",
            timing=(stage_name, elapsed),
            meta_update={**result, "stage_running": None},
            set_finished=is_final,
            expect_token=run_token,
        )
        if recorded and is_final:
            _set_ingest_state(book_id, "embedded", task_id=celery_task_id)
    except Exception as e:
        group = classify_error(e)
        log.exception(f"[{book_id}] item={item_id} {stage_name} 실패 ({group}): {e}")
        fail_recorded = _update_item(
            item_id,
            status="failed",
            error_group=group,
            last_error=str(e)[:2000],
            bump_attempt=True,
            # 결정적 실패는 다시 해도 같다 — attempt 를 한도로 올려 자동 재시도에서 뺀다
            min_attempt=max_attempts if group in NO_RETRY_GROUPS else None,
            timing=(stage_name, round(time.monotonic() - t0, 1)),
            meta_update={"stage_running": None},
            expect_token=run_token,
        )
        if fail_recorded:
            _set_ingest_state(book_id, "failed", task_id=celery_task_id, error=str(e))
        else:
            # 새 체인의 아이템·카탈로그 상태에 옛 체인의 실패를 찍지 않는다. 예외는 그대로 올린다
            log.warning(f"[{book_id}] item={item_id} {stage_name} 늦은 실패 기록 버림 — 새 체인이 있다")
        raise  # 체인 중단 (남은 단계 실행 안 함)
    finally:
        lock.release()

    if not recorded:
        # 단계는 끝났지만 그 사이 새 체인이 토큰을 바꿨다 — 결과를 쓰지 않고 이 체인의 다음 단계도
        # 보내지 않는다(Ignore). 위 try 안에서 던지면 except Exception 이 실패로 기록한다
        log.warning(f"[{book_id}] item={item_id} {stage_name} 늦은 성공 기록 버림 — 새 체인이 있다 → 체인 정지")
        raise Ignore("늦은 성공 기록 버림")
    return {"item_id": item_id, "stage": stage_name, "elapsed_s": elapsed}


def _update_item(
    item_id: int,
    *,
    stage: str | None = None,
    status: str | None = None,
    error_group: str | None = None,
    last_error: str | None = None,
    celery_task_id: str | None = None,
    timing: tuple[str, float] | None = None,
    meta_update: dict | None = None,
    bump_attempt: bool = False,
    min_attempt: int | None = None,
    set_started: bool = False,
    set_finished: bool = False,
    expect_token: str | None = None,
) -> bool:
    """아이템 상태를 기록한다. 기록해도 되는 아이템이면 True, 아니면 False(아무것도 쓰지 않았다).

    expect_token 이 주어지면 FOR UPDATE 로 읽은 아이템의 meta.run_token 과 같을 때만 쓴다. 단계가 도는
    동안 디스패처의 재디스패치나 stale 복구가 토큰을 바꿨으면 이 체인은 옛 체인이라 쓰면 안 된다.
    False 는 아이템이 없거나 토큰이 다른 경우뿐이다. DB 오류는 예전처럼 삼키고 경고만 남기며
    True 를 돌려준다 — 토큰 때문에 안 쓴 것이 아니라서 단계 흐름은 그대로다.
    """
    db = SyncSessionLocal()
    try:
        item = db.query(IngestJobItem).filter_by(id=item_id).with_for_update().first()
        if not item:
            return False
        if expect_token is not None and (item.meta or {}).get("run_token") != expect_token:
            return False   # 읽기만 했다 — finally 의 db.close() 가 행 잠금을 푼다
        if stage is not None:
            item.stage = stage
        if status is not None:
            item.status = status
            if status != "failed":
                item.error_group = None
        if error_group is not None:
            item.error_group = error_group
        if last_error is not None:
            item.last_error = last_error
        if celery_task_id is not None:
            item.celery_task_id = celery_task_id
        if timing is not None:
            item.stage_timings = {**(item.stage_timings or {}), f"{timing[0]}_s": timing[1]}
        if meta_update:
            # JSON 직렬화 가능한 값만 기록 (None 도 기록한다 — stage_running 을 지울 때 쓴다)
            safe = {k: v for k, v in meta_update.items()
                    if isinstance(v, (str, int, float, bool, type(None)))}
            item.meta = {**(item.meta or {}), **safe}
        if bump_attempt:
            item.attempt = (item.attempt or 0) + 1
        if min_attempt is not None:
            # 재시도 불가 실패 — 자동 재시도 조건(attempt < max_attempts)에서 빠지도록 올린다
            item.attempt = max(item.attempt or 0, min_attempt)
        now = _now()
        if set_started and item.started_at is None:
            item.started_at = now
        if set_finished:
            item.finished_at = now
        item.updated_at = now
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        log.warning(f"item={item_id} 상태 갱신 실패: {e}")
        return True
    finally:
        db.close()


# run_token 기본값 None: 배포 전에 보낸 메시지(인자 item_id 하나)도 받는다 — _skip_reason 참고
@celery_app.task(name="tasks.stage_extract", bind=True, acks_late=True)
def stage_extract(self, item_id: int, run_token: str | None = None):
    return _run_stage("extract", item_id, self.request.id, run_token)


@celery_app.task(name="tasks.stage_summarize", bind=True, acks_late=True)
def stage_summarize(self, item_id: int, run_token: str | None = None):
    return _run_stage("summarize", item_id, self.request.id, run_token)


@celery_app.task(name="tasks.stage_embed_index", bind=True, acks_late=True)
def stage_embed_index(self, item_id: int, run_token: str | None = None):
    return _run_stage("embed_index", item_id, self.request.id, run_token)


@celery_app.task(name="tasks.stage_finalize", bind=True, acks_late=True)
def stage_finalize(self, item_id: int, run_token: str | None = None):
    return _run_stage("finalize", item_id, self.request.id, run_token)


_STAGE_TASKS = {
    "extract": stage_extract,
    "summarize": stage_summarize,
    "embed_index": stage_embed_index,
    "finalize": stage_finalize,
}


def build_item_chain(item_stage: str, item_id: int, run_token: str | None = None):
    """체크포인트 기준 남은 단계 체인 구성. 남은 단계 없으면 None.

    모든 단계에 같은 실행 토큰을 싣는다 — 단계 래퍼가 아이템의 현재 토큰과 대조해 옛 체인을 멈춘다.
    """
    remaining = CHECKPOINT_TO_REMAINING.get(item_stage, list(STAGE_CHECKPOINT))
    if not remaining:
        return None
    return chain(*[_STAGE_TASKS[s].si(item_id, run_token) for s in remaining])


# ── 디스패처 (beat 30s) ───────────────────────────────────────


@celery_app.task(name="tasks.dispatch_job_items")
def dispatch_job_items():
    db = SyncSessionLocal()
    summary = {"dispatched": 0, "stale_recovered": 0, "completed_jobs": 0}
    try:
        jobs = db.query(IngestJob).filter(IngestJob.status == "running").all()
        for job in jobs:
            summary["stale_recovered"] += _recover_stale(db, job)
            summary["dispatched"] += _dispatch_for_job(db, job)
            if _maybe_complete(db, job):
                summary["completed_jobs"] += 1
        return summary
    finally:
        db.close()


def _parse_iso(value) -> _dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return _dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _stale_window(item) -> tuple[int, _dt.datetime | None, str]:
    """(타임아웃 초, 재기 시작한 시각, 설명) — 실행 중인 단계와 큐 대기를 나눠 잰다."""
    meta = item.meta or {}
    running = meta.get("stage_running") if item.status == "running" else None
    if isinstance(running, str) and running in STAGE_CHECKPOINT:
        started = _parse_iso(meta.get("stage_started_at"))
        return _stage_timeout(running), started or item.updated_at, f"{running} 실행 중"
    what = "디스패치 대기" if item.status == "dispatched" else "다음 단계 대기"
    return DISPATCH_STALE_SECONDS, item.updated_at or item.dispatched_at or item.created_at, what


def _recover_stale(db, job) -> int:
    """워커 사망 등으로 멈춘 아이템 → failed(stale) 전이 (자동 재시도 대상이 됨).

    실행 중인 단계(meta.stage_running)는 그 단계 타임아웃을 단계 시작 시각부터 잰다. 디스패치된
    뒤 아직 안 집혔거나 단계 사이에서 다음 단계 큐를 기다리는 아이템은 DISPATCH_STALE_SECONDS 를
    마지막 갱신 시각부터 잰다 — 큐 대기를 실행 시간으로 세면 바쁜 큐 뒤의 아이템이 stale 로
    오판돼 중복 체인이 열린다(함정 16).

    stale 로 찍을 때 meta.run_token 을 새 값으로 바꿔 옛 체인을 그 순간 끊는다 — 아직 도는 워커의
    기록은 토큰이 달라 버려지고(_update_item), 큐에 남은 옛 메시지는 _skip_reason 이 멈춘다.
    """
    now = _now()
    recovered = 0
    inflight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        # SKIP LOCKED: 워커가 같은 순간 단계 기록을 쓰는 중이면(그쪽 _update_item 이 행을 쥐고 있다)
        # 이번 틱은 건너뛴다 — 방금 끝난 단계의 기록을 failed 로 덮지 않는다. 다음 틱에 다시 본다
        .with_for_update(skip_locked=True)
        .all()
    )
    for item in inflight:
        timeout, ref, what = _stale_window(item)
        if ref is None:
            continue
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=_dt.timezone.utc)
        if (now - ref).total_seconds() > timeout:
            item.status = "failed"
            item.error_group = "stale"
            item.last_error = f"{timeout}s 무응답 — 워커 중단 추정 (stale 복구, {what})"
            item.attempt = (item.attempt or 0) + 1
            item.updated_at = now
            item.meta = {**(item.meta or {}), "run_token": uuid.uuid4().hex}
            recovered += 1
            log.warning(f"[{item.book_id}] item={item.id} stale 복구 (stage={item.stage}, {what})")
    if recovered:
        db.commit()
    else:
        # 위 조회가 쥔 행 잠금을 바로 놓는다 — 안 놓으면 이번 틱이 끝날 때까지 워커의 단계 기록과
        # 다음 단계의 첫 읽기(둘 다 FOR UPDATE)가 기다린다
        db.rollback()
    return recovered


@functools.lru_cache(maxsize=16)
def _parse_retry_backoff(schedule: str) -> tuple[int, ...]:
    """"120,600" → (120, 600). 정수가 아닌 칸은 건너뛰고 경고한다.

    디스패처가 30초마다 읽으므로 lru_cache 로 같은 설정 문자열은 한 번만 해석하고 경고한다
    (llm_client._parse_backoff_schedule 과 같은 방식). 빈 칸(끝 쉼표·빈 설정)은 조용히 건너뛴다.
    """
    steps: list[int] = []
    skipped: list[str] = []
    for part in schedule.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            steps.append(max(0, int(part)))
        except ValueError:
            skipped.append(part)
    if skipped:
        log.warning(
            f"INGEST_RETRY_BACKOFF_SECONDS={schedule!r} — 초(정수)가 아닌 칸 {skipped} 은 건너뜀"
        )
    return tuple(steps)


def _retry_backoff_steps() -> list[int]:
    """INGEST_RETRY_BACKOFF_SECONDS("120,600") → [120, 600]. 칸 해석·경고는 _parse_retry_backoff."""
    return list(_parse_retry_backoff(str(cfg.INGEST_RETRY_BACKOFF_SECONDS or "")))


def _retry_ready(now: _dt.datetime):
    """failed 아이템 가운데 백오프가 지난 것 — attempt 번째 실패 뒤 steps[attempt-1] 초를
    updated_at(실패를 기록한 시각)부터 기다린다. 값이 모자라면 마지막 값을 되풀이한다."""
    steps = _retry_backoff_steps()
    if not steps:
        return true()
    conds = [IngestJobItem.attempt < 1]
    for n, wait in enumerate(steps, start=1):
        same = IngestJobItem.attempt >= n if n == len(steps) else IngestJobItem.attempt == n
        conds.append(and_(same, IngestJobItem.updated_at <= now - _dt.timedelta(seconds=wait)))
    return or_(*conds)


def _needs_reextract(item) -> bool:
    """자동 재시도를 추출부터 다시 해야 하는 실패인가.

    vlm_error: OCR 이 VLM 장애로 실패했다 — 추출을 다시 해야 본문이 생긴다.
    not_found '섹션 없음': 옛 코드가 섹션 0개를 추출 성공으로 넘겨 요약에서 실패했다.
    체크포인트(extracted)부터 다시 하면 같은 실패를 되풀이해 시도만 다 쓴다.
    """
    if item.error_group == "vlm_error":
        return True
    return item.error_group == "not_found" and "섹션 없음" in (item.last_error or "")


def _dispatch_for_job(db, job) -> int:
    params = dict(job.params or {})
    high_water = int(params.get("high_water") or cfg.INGEST_HIGH_WATER)
    max_attempts = int(params.get("max_attempts") or cfg.INGEST_MAX_ATTEMPTS)
    now = _now()

    in_flight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        .count()
    )
    need = high_water - in_flight
    if need <= 0:
        return 0

    # pending(신규/수동 재시도) + failed(자동 재시도, attempt < max, 백오프 지남).
    # 백오프를 SQL 조건으로 거른다 — limit 뒤 파이썬에서 거르면 id 가 앞선 백오프 중 실패가
    # limit 을 채워 뒤의 pending 을 막는다
    items = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.attempt < max_attempts,
            or_(
                IngestJobItem.status == "pending",
                and_(IngestJobItem.status == "failed", _retry_ready(now)),
            ),
        )
        .order_by(IngestJobItem.id)
        .limit(need)
        # 워커의 첫 FOR UPDATE 읽기(_run_stage)가 새 토큰을 보는 것은 READ COMMITTED 와 이 행 잠금(커밋까지 유지)에 기댄다
        .with_for_update(skip_locked=True)
        .all()
    )

    dispatched = 0
    for item in items:
        if item.status == "failed" and item.stage != "pending" and _needs_reextract(item):
            log.info(
                f"[{item.book_id}] item={item.id} {item.error_group} 재시도 — "
                f"체크포인트 {item.stage} → pending (추출부터)"
            )
            item.stage = "pending"
        # 체인마다 새 토큰 — 이 아이템의 옛 체인(stale 복구 전 체인·재전달 메시지)은 단계 래퍼가
        # 멈춘다. 토큰은 루프 끝 commit 에 보이고, 단계 래퍼의 첫 읽기(FOR UPDATE)가 그 commit 을
        # 기다린다(이 SELECT … FOR UPDATE 가 행을 잠그고 있다)
        run_token = uuid.uuid4().hex
        sig = build_item_chain(item.stage, item.id, run_token)
        if sig is None:
            item.status = "done"
            item.finished_at = now
            item.updated_at = now
            continue
        item.meta = {**(item.meta or {}), "run_token": run_token}
        res = sig.apply_async()
        item.status = "dispatched"
        item.dispatched_at = now
        item.updated_at = now
        item.celery_task_id = res.id
        dispatched += 1
    db.commit()
    return dispatched


def _maybe_complete(db, job) -> bool:
    """더 처리할 아이템이 없으면 잡 완료 처리."""
    params = dict(job.params or {})
    max_attempts = int(params.get("max_attempts") or cfg.INGEST_MAX_ATTEMPTS)

    in_flight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        .count()
    )
    if in_flight:
        return False
    eligible = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("pending", "failed")),
            IngestJobItem.attempt < max_attempts,
        )
        .count()
    )
    if eligible:
        return False

    failed = (
        db.query(IngestJobItem)
        .filter(IngestJobItem.job_id == job.id, IngestJobItem.status == "failed")
        .count()
    )
    job.status = "completed_with_errors" if failed else "completed"
    job.finished_at = _now()
    db.commit()
    log.info(f"잡 '{job.name}' 완료 — status={job.status} (failed={failed})")
    return True


# ── 정리 태스크 (beat 1h) ─────────────────────────────────────

# 정리 태스크는 제어 워커(celery-control, 한 칸)에서 디스패치 틱과 같은 q_control 을 쓴다. 틱은 25초 뒤
# 만료되므로(workers/celery_app.py) 이 태스크가 붙잡는 동안의 틱은 모두 버려진다 — Milvus 가 응답하지 않아도
# 끝나도록 flush 에 타임아웃을 주고, 연결·컬렉션 로드처럼 타임아웃이 없는 호출까지 태스크 시간 제한으로 끊는다.
# flush 타임아웃은 정수로 준다 — pymilvus 는 timeout 이 int 일 때만 RPC 재시도 루프도 그 시간에서 끊는다.
_CLEANUP_FLUSH_TIMEOUT_SECONDS = 60
_CLEANUP_SOFT_TIME_LIMIT = 120      # SoftTimeLimitExceeded 는 Exception 이라 flush 의 except 가 경고로 받는다
_CLEANUP_HARD_TIME_LIMIT = 150      # 소프트 제한이 블로킹 호출을 못 끊으면 자식 프로세스째 끝낸다


@celery_app.task(
    name="tasks.cleanup_temp_files",
    soft_time_limit=_CLEANUP_SOFT_TIME_LIMIT,
    time_limit=_CLEANUP_HARD_TIME_LIMIT,
)
def cleanup_temp_files(max_age_hours: int = 24):
    """임시 다운로드 파일 정리 + Milvus 주기 flush (num_entities 최신화)."""
    download_dir = "/app/data/downloads"
    removed = 0
    cutoff = time.time() - max_age_hours * 3600
    if os.path.isdir(download_dir):
        for name in os.listdir(download_dir):
            path = os.path.join(download_dir, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue

    # 건당 flush 제거에 대한 보상 — 주기 flush 1회 (검색 num_entities 가드 최신화)
    try:
        from services.ingestion.indexer import ensure_collection
        ensure_collection().flush(timeout=_CLEANUP_FLUSH_TIMEOUT_SECONDS)
    except Exception as e:
        log.warning(f"주기 Milvus flush 실패: {str(e) or type(e).__name__}")

    log.info(f"cleanup_temp_files: 임시 파일 {removed}개 삭제")
    return {"removed": removed}
