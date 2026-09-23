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
import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import redis.asyncio as aioredis

from core.config import get_settings
from models.research import STATUS_CANCELED

log = logging.getLogger(__name__)

# 종료 상태 → SSE 종료 이벤트 kind. 워커가 흘리는 종료 이벤트와 스트림
# 엔드포인트가 DB 를 보고 만드는 종료 프레임이 둘 다 terminal_event 를 거친다 —
# 연결 시점에 따라 모양이 갈리면(failed 를 done+status 로 받는 식) 프론트
# 분기가 조용히 빗나간다.
TERMINAL_KIND = {"completed": "done", "failed": "failed", STATUS_CANCELED: STATUS_CANCELED}

# 워커의 emit 경로에 있다. 응답 없는 Redis 는 예외가 아니라 무기한 대기라서
# publish 가 삼킬 기회조차 없이 잡이 소프트 리밋까지 멈춘다.
PUBLISH_TIMEOUT = 2.0


def channel(job_id: uuid.UUID | str) -> str:
    return f"research:{job_id}"


def terminal_event(status: str, error: str | None = None) -> dict:
    event = {"kind": TERMINAL_KIND[status], "status": status}
    if error:
        event["error"] = error[:200]
    return event


def _with_timeouts(url: str) -> str:
    """REDIS_URL 에 소켓 타임아웃을 얹는다. URL 에 이미 있는 값은 운영자 설정이라 그대로 둔다."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("socket_connect_timeout", str(PUBLISH_TIMEOUT))
    query.setdefault("socket_timeout", str(PUBLISH_TIMEOUT))
    return urlunsplit(parts._replace(query=urlencode(query)))


async def publish(job_id: uuid.UUID | str, kind: str, payload: dict) -> None:
    """중계 실패가 리서치를 죽이면 안 된다 — 삼키고 로그만 남긴다.

    클라이언트를 호출마다 새로 만든다. 모듈 전역에 하나 두면 첫 이벤트루프에
    묶이는데, Celery 태스크는 잡마다 `asyncio.run(...)` 으로 루프를 새로 열고
    닫으므로 두 번째 잡부터 전부 `Event loop is closed` 로 죽는다.
    한 잡에 수십 번 도는 정도라 연결 비용보다 이쪽이 싸다.
    """
    cfg = get_settings()
    try:
        client = aioredis.from_url(_with_timeouts(cfg.REDIS_URL))
        try:
            await client.publish(
                channel(job_id), json.dumps({"kind": kind, **payload}, ensure_ascii=False)
            )
        finally:
            await client.aclose()
    except Exception as e:
        log.warning("[research:relay] publish 실패 job=%s kind=%s: %s", job_id, kind, e)


async def publish_terminal(job_id: uuid.UUID | str, status: str, error: str | None = None) -> None:
    event = terminal_event(status, error)
    await publish(job_id, event.pop("kind"), event)


async def subscribe(
    job_id: uuid.UUID | str, *, idle_timeout: float = 15.0,
) -> AsyncIterator[dict | None]:
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
