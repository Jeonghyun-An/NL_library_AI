"""core/errors.py — 화면에 닿는 API 오류 응답의 공통 꼴.

화면(프론트)이 읽는 계약:
- 라우트가 잡지 않은 예외 → 500 {"detail": INTERNAL_ERROR_DETAIL, "code": "internal_error"}. 스택은 로그에만 남긴다 —
  전에는 Starlette 기본 응답 'Internal Server Error'(JSON 아닌 글)가 그대로 화면에 갔다.
- 검색 기반(Milvus·gRPC·연결/시간 초과) 장애 → 503 {"detail": SEARCH_UNAVAILABLE_DETAIL, "code": "search_unavailable"}
- 원문 저장소(MinIO) 연결 장애 → 503 {"detail": STORAGE_UNAVAILABLE_DETAIL, "code": "storage_unavailable"}
- 작업 큐(Celery 브로커)에 넣지 못함 → 503 {"detail": QUEUE_UNAVAILABLE_DETAIL} — 딥리서치(api/research.py
  _broker_unavailable)와 같은 문구·꼴이다.
HTTPException·RequestValidationError 는 FastAPI 기본 처리 그대로다(ApiError 만 code 를 더 싣는다).

장애 판별은 일시적인 연결·시간 초과·저장소/검색 서버 예외만 본다 — 코드 버그(TypeError·KeyError 등)까지 503 으로
덮으면 '잠시 뒤 다시'가 영영 낫지 않는 오류를 가린다. 그런 것은 500(internal_error)으로 간다.
pymilvus·grpc·urllib3·minio·kombu·redis 는 판별할 때만 함수 안에서 import 한다 — 이 모듈은 main.py·라우터가 머리에서
읽으므로 무거운(또는 로컬 venv 에 없는) 모듈을 끌어오면 안 된다(recurring-gotchas 13번과 같은 이유).
"""
import logging
from contextlib import contextmanager
from typing import Iterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

INTERNAL_ERROR_DETAIL = "서버에서 문제가 생겼습니다. 잠시 뒤 다시 시도하세요"
SEARCH_UNAVAILABLE_DETAIL = "검색 서버가 잠시 응답하지 않습니다. 잠시 뒤 다시 시도하세요"
STORAGE_UNAVAILABLE_DETAIL = "원문 저장소가 잠시 응답하지 않습니다. 잠시 뒤 다시 시도하세요"
QUEUE_UNAVAILABLE_DETAIL = "작업 큐에 연결하지 못했습니다 — 잠시 후 다시 시도하세요"


class ApiError(HTTPException):
    """detail 에 기계가 읽는 code 를 더한 HTTPException. install_error_handlers 를 건 앱에서는 {"detail", "code"} 로,
    걸지 않은 앱(라우터만 올린 테스트 앱)에서는 HTTPException 처럼 {"detail"} 로 나간다 — 상태 코드·문구는 같다."""

    def __init__(self, status_code: int, detail: str, code: str):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def search_unavailable() -> ApiError:
    return ApiError(503, SEARCH_UNAVAILABLE_DETAIL, "search_unavailable")


def storage_unavailable() -> ApiError:
    return ApiError(503, STORAGE_UNAVAILABLE_DETAIL, "storage_unavailable")


def queue_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail=QUEUE_UNAVAILABLE_DETAIL)


# ── 장애 판별 ─────────────────────────────────────────────
def _types(*loaders) -> tuple[type, ...]:
    """설치돼 있는 예외 타입만 모은다. 로컬 테스트는 pymilvus 등을 MagicMock 으로 갈아 끼우기도 해서(pipeline_stub)
    import 가 되더라도 타입이 아닌 것은 뺀다 — isinstance 에 넘기면 TypeError 다."""
    found: list[type] = []
    for load in loaders:
        try:
            t = load()
        except ImportError:
            continue
        if isinstance(t, type) and issubclass(t, BaseException):
            found.append(t)
    return tuple(found)


def _milvus_exception():
    from pymilvus.exceptions import MilvusException
    return MilvusException


def _milvus_param_error():
    from pymilvus.exceptions import ParamError
    return ParamError


def _grpc_error():
    import grpc
    return grpc.RpcError


def is_search_outage(exc: BaseException) -> bool:
    """검색 기반의 일시 장애인가 — 연결 거부·시간 초과(내장 ConnectionError·TimeoutError, httpx 전송 오류), Milvus 가
    돌려준 오류(MilvusException — 연결 실패도 이것이다), gRPC 오류(pymilvus 는 기한 초과를 날 grpc.RpcError 로 다시
    던진다 — research_work/membership.py). pymilvus 의 ParamError 는 클라이언트가 인자를 거른 것(코드 버그)이라 뺀다."""
    if isinstance(exc, (ConnectionError, TimeoutError, httpx.TransportError)):
        return True
    if isinstance(exc, _types(_milvus_param_error)):
        return False
    return isinstance(exc, _types(_milvus_exception, _grpc_error))


def _urllib3_error():
    from urllib3.exceptions import HTTPError
    return HTTPError


def _minio_server_error():
    from minio.error import ServerError
    return ServerError


def _minio_invalid_response():
    from minio.error import InvalidResponseError
    return InvalidResponseError


def is_storage_outage(exc: BaseException) -> bool:
    """원문 저장소(MinIO)의 일시 장애인가 — MinIO 가 꺼져 있으면 minio 클라이언트는 urllib3 재시도(약 6초) 끝에
    urllib3.exceptions.MaxRetryError 를 던진다(운영 이미지 minio 7.2.8 에서 확인). 5xx 응답은 ServerError,
    XML 이 아닌 응답(게이트웨이 HTML 등)은 InvalidResponseError 다. 객체가 없는 것(S3Error)은 장애가 아니다 — 404."""
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    return isinstance(exc, _types(_urllib3_error, _minio_server_error, _minio_invalid_response))


def _kombu_operational_error():
    from kombu.exceptions import OperationalError
    return OperationalError


def _redis_connection_error():
    from redis.exceptions import ConnectionError as RedisConnectionError
    return RedisConnectionError


def _redis_timeout_error():
    from redis.exceptions import TimeoutError as RedisTimeoutError
    return RedisTimeoutError


def is_broker_outage(exc: BaseException) -> bool:
    """작업 큐(Celery 브로커 Redis)에 닿지 못했는가 — .delay()·control.revoke() 는 브로커가 꺼져 있으면 kombu 재시도
    끝에 kombu.exceptions.OperationalError 를 던진다(운영 이미지 celery 5.4·kombu 5.6 에서 확인, 딥리서치 _enqueue 가
    잡는 것과 같다). redis·내장 연결 오류는 kombu 가 감싸지 못한 경로를 위한 것이다."""
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    return isinstance(exc, _types(_kombu_operational_error, _redis_connection_error, _redis_timeout_error))


# ── 라우트에서 쓰는 가드 ──────────────────────────────────
@contextmanager
def search_outage_as_503(where: str) -> Iterator[None]:
    """블록 안의 검색 기반 장애를 503(search_unavailable)으로 바꾼다. 그 밖의 예외(HTTPException·코드 버그)는 그대로
    올린다 — 코드 버그는 전역 처리기가 500 으로 낸다."""
    try:
        yield
    except Exception as e:
        if not is_search_outage(e):
            raise
        log.warning("[%s] 검색 기반 장애 → 503: %s: %s", where, type(e).__name__, e, exc_info=True)
        raise search_unavailable() from e


@contextmanager
def storage_outage_as_503(where: str) -> Iterator[None]:
    """블록 안의 원문 저장소(MinIO) 장애를 503(storage_unavailable)으로 바꾼다."""
    try:
        yield
    except Exception as e:
        if not is_storage_outage(e):
            raise
        log.warning("[%s] 원문 저장소 장애 → 503: %s: %s", where, type(e).__name__, e)
        raise storage_unavailable() from e


@contextmanager
def broker_outage_as_503(where: str) -> Iterator[None]:
    """블록 안의 작업 큐(브로커) 연결 실패를 503 으로 바꾼다. 여러 건을 차례로 넣는 루프에서는 앞서 넣은 것은 이미
    큐에 들어가 있다 — 로그에 남긴다."""
    try:
        yield
    except Exception as e:
        if not is_broker_outage(e):
            raise
        log.error("[%s] 작업 큐 전달 실패 → 503: %s: %s", where, type(e).__name__, e)
        raise queue_unavailable() from e


# ── 앱 처리기 ─────────────────────────────────────────────
async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Starlette 의 ServerErrorMiddleware 는 이 응답을 보낸 뒤에도 예외를 다시 올려 uvicorn 도 스택을 남긴다 — 여기서는
    # 어느 요청이었는지(메서드·경로)를 함께 남긴다. 쿼리 문자열은 남기지 않는다(검색어 등 사용자 입력)
    log.error("처리하지 못한 예외 → 500: %s %s — %s: %s", request.method, request.url.path,
              type(exc).__name__, exc, exc_info=exc)
    return JSONResponse({"detail": INTERNAL_ERROR_DETAIL, "code": "internal_error"}, status_code=500)


def install_error_handlers(app: FastAPI) -> None:
    """ApiError → {"detail", "code"}, 잡지 않은 예외 → 500 internal_error. HTTPException·RequestValidationError 의 기본
    처리기는 건드리지 않는다 — ApiError 처리기는 하위 클래스라 Starlette 가 MRO 순으로 먼저 고른다."""
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
