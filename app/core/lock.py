"""
Redis 기반 분산 락 — 인덱싱 태스크 중복 실행 방지.

같은 book_id 로 동시 진행되는 두 개의 Celery 태스크가 Milvus 중복 삽입 /
PostgreSQL 섹션 레이스를 일으키는 것을 차단한다.

사용:
    lock = BookLock(book_id)
    if not lock.acquire():
        raise RuntimeError("이미 처리 중")
    try:
        ...
    finally:
        lock.release()
"""
import logging
import uuid
from contextlib import contextmanager

import redis

from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

_pool: redis.ConnectionPool | None = None


def _client() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(cfg.REDIS_URL, decode_responses=True)
    return redis.Redis(connection_pool=_pool)


# Lua: 토큰이 일치할 때만 삭제 (다른 워커의 락을 실수로 해제하지 않도록)
_UNLOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class BookLock:
    """book_id 단위 인덱싱 락. TTL이 지나면 자동 해제 (워커가 죽어도 영구 락 방지)."""

    def __init__(self, book_id: str, ttl: int | None = None):
        self.key = f"book_lock:{book_id}"
        self.token = uuid.uuid4().hex
        self.ttl = ttl if ttl is not None else cfg.BOOK_LOCK_TTL
        self.book_id = book_id

    def acquire(self) -> bool:
        """원자적 SET NX EX. 성공 시 True."""
        ok = _client().set(self.key, self.token, nx=True, ex=self.ttl)
        if ok:
            log.info(f"[{self.book_id}] 인덱싱 락 획득 (TTL {self.ttl}s)")
        else:
            log.warning(f"[{self.book_id}] 이미 다른 워커가 처리 중 — 락 획득 실패")
        return bool(ok)

    def release(self) -> bool:
        """토큰 검증 후 안전 해제."""
        try:
            result = _client().eval(_UNLOCK_SCRIPT, 1, self.key, self.token)
            released = bool(result)
            if released:
                log.info(f"[{self.book_id}] 인덱싱 락 해제")
            return released
        except Exception as e:
            log.warning(f"[{self.book_id}] 락 해제 실패: {e}")
            return False

    def refresh(self, ttl: int | None = None) -> bool:
        """장시간 태스크의 TTL 갱신."""
        try:
            return bool(_client().expire(self.key, ttl or self.ttl))
        except Exception:
            return False


@contextmanager
def book_lock(book_id: str, ttl: int | None = None):
    """컨텍스트 매니저 형태. 락 획득 실패 시 RuntimeError."""
    lock = BookLock(book_id, ttl=ttl)
    if not lock.acquire():
        raise RuntimeError(f"book_id={book_id} 인덱싱 락 획득 실패 (이미 처리 중)")
    try:
        yield lock
    finally:
        lock.release()


def force_release(book_id: str) -> bool:
    """관리자용 — 토큰 검증 없이 강제 해제 (cancel 엔드포인트에서 사용)."""
    try:
        return bool(_client().delete(f"book_lock:{book_id}"))
    except Exception as e:
        log.warning(f"[{book_id}] 강제 락 해제 실패: {e}")
        return False
