"""run_queue.py — 딥리서치 대기 순번 (Redis ZSET research:run_queue)

research_jobs 에는 승인 시각 칼럼이 없다. 실행 큐에 들어간 순서를 ZSET(member = 잡 id,
score = 넣은 시각)으로 따로 들고, 순번 = running 잡 수 + ZSET 에서 내 앞 원소 수로 센다.

- 넣기: approve·retry 가 전이에 성공한 뒤, 브로커에 넣기 **전**(넣은 뒤면 바로 집은 워커가
  먼저 빼고 그 뒤에 들어가 줄에 영영 남는다). 브로커에 못 넣으면 뺀다.
- 빼기: 워커가 집기를 시도한 직후(집었든 못 집었든), 취소, 회수기가 failed 로 둔 잡.
- ZSET 이 비었으면(Redis 재기동) 호출부가 created_at 순으로 근사한다.

Redis 실패는 삼킨다 — 순번은 안내일 뿐이라 승인·조회·실행을 막으면 안 된다.
redis 는 함수 안에서 import 한다(로컬 venv·테스트 수집에 redis 가 없다 — 함정 13).
비동기 클라이언트는 호출마다 만들고 닫는다(relay.publish 와 같은 까닭 — Celery 태스크는
잡마다 asyncio.run 으로 이벤트 루프를 새로 연다).
"""
import logging
import statistics
import time

from core.config import get_settings

log = logging.getLogger(__name__)

RUN_QUEUE_KEY = "research:run_queue"

# 응답 없는 Redis 는 예외가 아니라 무기한 대기다. 잡 조회(GET)·승인이 거기 묶이지 않게
# 소켓 타임아웃을 건다. URL 에 이미 있는 값은 redis-py 가 키워드 인자보다 앞세운다.
REDIS_TIMEOUT = 2.0


def _now() -> float:
    return time.time()


def _async_client():
    import redis.asyncio as aioredis

    return aioredis.from_url(
        get_settings().REDIS_URL,
        socket_connect_timeout=REDIS_TIMEOUT, socket_timeout=REDIS_TIMEOUT,
    )


def _sync_client():
    import redis

    return redis.Redis.from_url(
        get_settings().REDIS_URL,
        socket_connect_timeout=REDIS_TIMEOUT, socket_timeout=REDIS_TIMEOUT,
    )


async def mark_waiting(job_id) -> None:
    """줄 끝에 넣는다. NX — 이미 있으면 처음 넣은 시각(자리)을 지킨다."""
    try:
        client = _async_client()
        try:
            await client.zadd(RUN_QUEUE_KEY, {str(job_id): _now()}, nx=True)
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:run_queue] 대기 줄에 넣지 못했다 job=%s: %s", job_id, e)


async def unmark(job_id) -> None:
    try:
        client = _async_client()
        try:
            await client.zrem(RUN_QUEUE_KEY, str(job_id))
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:run_queue] 대기 줄에서 빼지 못했다 job=%s: %s", job_id, e)


async def rank_of(job_id) -> int | None:
    """줄에서 내 앞 원소 수(0 부터). 줄에 없거나 Redis 가 실패하면 None."""
    try:
        client = _async_client()
        try:
            rank = await client.zrank(RUN_QUEUE_KEY, str(job_id))
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:run_queue] 순번을 읽지 못했다 job=%s: %s", job_id, e)
        return None
    return int(rank) if rank is not None else None


def unmark_many_sync(job_ids: list[str]) -> None:
    """회수기(동기 Celery 태스크)용 — 회수해 failed 로 둔 잡을 한 번에 뺀다."""
    if not job_ids:
        return
    try:
        client = _sync_client()
        try:
            client.zrem(RUN_QUEUE_KEY, *[str(j) for j in job_ids])
        finally:
            client.close()
    except Exception as e:
        log.warning("[research:run_queue] 회수한 잡을 대기 줄에서 빼지 못했다 n=%d: %s",
                    len(job_ids), e)


def waiting_ahead(running: int, rank: int | None, fallback_ahead: int) -> int:
    """앞에 있는 잡 수 = running + (ZSET 순위, 없으면 created_at 순 근사)."""
    return max(0, running) + max(0, rank if rank is not None else fallback_ahead)


def eta_seconds(ahead: int, median_run_seconds: float | None) -> int | None:
    """시작까지 기다리는 시간 = ahead × 중앙값(화면 문구 '앞에 N건 · 약 M분' 은 기다리는 시간이다).
    중앙값이 없으면 None. 반올림 int."""
    if median_run_seconds is None:
        return None
    return int(round(ahead * median_run_seconds))


def median_seconds(durations: list[float]) -> float | None:
    """소요 시간 중앙값. 음수(시계가 어긋난 행)는 버리고, 남은 것이 없으면 None."""
    values = [d for d in durations if d >= 0]
    if not values:
        return None
    return float(statistics.median(values))
