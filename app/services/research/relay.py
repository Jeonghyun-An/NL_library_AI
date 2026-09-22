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
    묶이는데, Celery 태스크는 단계마다 `asyncio.run(...)` 으로 새 루프를 열고
    닫으므로 두 번째 publish 부터 전부 `Event loop is closed` 로 죽는다.
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
