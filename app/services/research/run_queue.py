"""run_queue.py — 딥리서치 대기 순번 (Redis ZSET research:run_queue)

research_jobs 에는 승인 시각 칼럼이 없다. 실행 큐에 들어간 순서를 ZSET(member = 잡 id,
score = 넣은 시각)으로 따로 들고, 순번 = running 잡 수 + ZSET 에서 내 앞에 선 잡 중 지금
기다리는 잡 수로 센다.

- 넣기: approve·retry 가 전이에 성공한 뒤, 브로커에 넣기 **전**(넣은 뒤면 바로 집은 워커가
  먼저 빼고 그 뒤에 들어가 줄에 영영 남는다). 브로커에 못 넣으면 뺀다.
- 빼기: 워커가 집기를 시도한 직후(집었든 못 집었든), 취소, 회수기가 failed 로 둔 잡.
- ZSET 이 비었으면(Redis 재기동) 호출부가 created_at 순으로 근사한다.
- 빼기는 Redis 실패를 삼키므로 끝난 잡이 줄에 남을 수 있다(TTL·정리 경로 없음). 그래서
  순번은 ZSET 순위를 그대로 쓰지 않고, 내 앞 원소(members_ahead)를 받아 호출부가 DB 에서
  지금 기다리는(approved·queued) 잡만 센다. 남은 원소는 읽을 때 거를 뿐 지우지 않는다 —
  상태로 골라 지우면 그 사이 재시도로 다시 줄에 선 잡까지 지운다(계약 §10).

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
    """줄 끝에 넣는다. 이미 있으면 넣은 시각을 지금으로 바꾼다(NX 가 아니다).

    부르는 곳은 조건부 전이에 성공한 approve·retry 뿐이라 한 번 줄에 들어갈 때 한 번만
    불린다(재전송된 승인은 409). 그래도 원소가 이미 있다면 지난번 빼기가 실패해 남은
    것이다 — NX 로 그 옛 시각을 이어받으면 다시 줄에 선 잡이 줄 맨 앞으로 끼어든다.
    """
    try:
        client = _async_client()
        try:
            await client.zadd(RUN_QUEUE_KEY, {str(job_id): _now()})
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


async def members_ahead(job_id) -> list[str] | None:
    """줄에서 나보다 먼저 넣은 원소(잡 id 문자열). 줄에 없거나 Redis 가 실패하면 None.

    빼기에 실패해 남은 끝난 잡도 섞여 나온다 — 호출부가 DB 상태로 거른다. 순위(ZRANK)가
    아니라 내 점수보다 작은 점수로 자른다: 두 명령 사이에 앞 원소가 빠져도 내 자리 뒤의
    원소가 범위로 밀려 들어오지 않는다.
    """
    try:
        client = _async_client()
        try:
            score = await client.zscore(RUN_QUEUE_KEY, str(job_id))
            if score is None:
                return None
            members = await client.zrangebyscore(RUN_QUEUE_KEY, "-inf", f"({score!r}")
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:run_queue] 순번을 읽지 못했다 job=%s: %s", job_id, e)
        return None
    return [m.decode() if isinstance(m, bytes) else str(m) for m in members]


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


def waiting_ahead(running: int, in_line: int | None, fallback_ahead: int) -> int:
    """앞에 있는 잡 수 = running + (줄에서 내 앞의 기다리는 잡 수, 줄에 없으면 created_at 순 근사)."""
    return max(0, running) + max(0, in_line if in_line is not None else fallback_ahead)


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
