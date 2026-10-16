"""test_error_handlers.py — 화면에 닿는 API 오류 응답의 공통 꼴(core/errors.py).

- 라우트가 잡지 않은 예외 → 500 {"detail": "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요", "code": "internal_error"}.
  전에는 Starlette 기본 응답 'Internal Server Error'(JSON 아닌 영어 글)가 화면에 그대로 갔다. 스택은 로그에 남는다.
- HTTPException·RequestValidationError 는 그대로다(code 를 더하지 않는다).
- ApiError → {"detail", "code"}. 처리기를 걸지 않은 앱에서도 상태·문구는 HTTPException 처럼 같다.
- 장애 판별(검색·원문 저장소·작업 큐)은 일시 장애만 본다 — 코드 버그(TypeError 등)는 503 으로 가리지 않는다. 검색은
  연결 장애(Milvus 연결 실패, grpc UNAVAILABLE·DEADLINE_EXCEEDED, 연결·시간 초과)만 503 이고, 그 밖의 Milvus 오류(컬렉션
  없음·스키마·자료형 불일치 등)는 기다려도 낫지 않아 500 이다.
- main.py 가 install_error_handlers 를 실제로 건다(다른 테스트는 라우터만 올린 앱이라 빠뜨려도 통과한다).

예외 클래스는 운영 이미지(pymilvus 2.4.6·grpc·minio 7.2·urllib3 2·kombu 5.6·redis 5)의 실제 것을 쓴다 — Milvus·grpc 오류는
milvus_errors.py 가 실제 호출로 만든다. 로컬 venv 에 없으면 그 경우만 건너뛴다(importorskip). async 테스트 없음.
"""
import ast
import logging
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from core import errors
from core.errors import (
    INTERNAL_ERROR_DETAIL,
    QUEUE_UNAVAILABLE_DETAIL,
    SEARCH_UNAVAILABLE_DETAIL,
    STORAGE_UNAVAILABLE_DETAIL,
    ApiError,
    broker_outage_as_503,
    install_error_handlers,
    is_broker_outage,
    is_search_outage,
    is_storage_outage,
    search_outage_as_503,
    storage_outage_as_503,
)
from milvus_errors import milvus_connect_failure, milvus_retry_error, rpc_error


class _Body(BaseModel):
    n: int


def _app(*, handlers: bool = True) -> FastAPI:
    app = FastAPI()
    if handlers:
        install_error_handlers(app)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    @app.get("/missing")
    async def missing():
        raise HTTPException(404, "도서 없음: X")

    @app.post("/validate")
    async def validate(body: _Body):
        return {"n": body.n}

    @app.get("/search-down")
    async def search_down():
        with search_outage_as_503("테스트 검색"):
            raise ConnectionRefusedError(111, "Connection refused")

    @app.get("/search-bug")
    async def search_bug():
        with search_outage_as_503("테스트 검색"):
            raise TypeError("'NoneType' object is not subscriptable")

    @app.get("/api-error")
    async def api_error():
        raise ApiError(503, "잠시 뒤", "some_code")

    return app


def _client(app: FastAPI) -> TestClient:
    # ServerErrorMiddleware 는 처리기 응답을 보낸 뒤에도 예외를 다시 올린다(서버가 로그를 남기게) — 테스트 클라이언트가
    # 그것을 다시 던지지 않게 한다. 운영 uvicorn 은 응답을 보낸 뒤 그 예외를 로그에만 남긴다
    return TestClient(app, raise_server_exceptions=False)


# ── 전역 처리기 ───────────────────────────────────────────
class TestInternalError:
    def test_unhandled_exception_is_a_json_500_with_a_korean_message(self):
        resp = _client(_app()).get("/boom")
        assert resp.status_code == 500
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.json() == {"detail": INTERNAL_ERROR_DETAIL, "code": "internal_error"}
        assert INTERNAL_ERROR_DETAIL == "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요"

    def test_the_exception_text_does_not_reach_the_screen(self):
        assert "secret internal detail" not in _client(_app()).get("/boom").text

    def test_the_stack_and_the_route_go_to_the_log(self, caplog):
        with caplog.at_level(logging.ERROR, logger=errors.log.name):
            _client(_app()).get("/boom?q=사용자 검색어")
        records = [r for r in caplog.records if r.name == errors.log.name]
        assert len(records) == 1
        rec = records[0]
        assert rec.exc_info and rec.exc_info[0] is RuntimeError     # 스택이 남는다
        msg = rec.getMessage()
        assert "GET /boom" in msg and "RuntimeError" in msg
        assert "사용자 검색어" not in msg                              # 쿼리 문자열은 남기지 않는다

    def test_without_the_handlers_it_was_plain_text(self):
        # 바꾸기 전 모습 — 화면이 JSON 으로 읽지 못하던 응답
        resp = _client(_app(handlers=False)).get("/boom")
        assert resp.status_code == 500
        assert resp.text == "Internal Server Error"


class TestUnchangedHandlers:
    def test_http_exception_keeps_its_shape(self):
        resp = _client(_app()).get("/missing")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "도서 없음: X"}

    def test_validation_error_keeps_its_shape(self):
        resp = _client(_app()).post("/validate", json={"n": "숫자 아님"})
        assert resp.status_code == 422
        body = resp.json()
        assert set(body) == {"detail"} and isinstance(body["detail"], list)

    def test_unknown_route_is_still_404_not_found(self):
        resp = _client(_app()).get("/nope")
        assert resp.status_code == 404 and resp.json() == {"detail": "Not Found"}


class TestApiError:
    def test_api_error_carries_its_code(self):
        resp = _client(_app()).get("/api-error")
        assert resp.status_code == 503
        assert resp.json() == {"detail": "잠시 뒤", "code": "some_code"}

    def test_without_the_handlers_it_degrades_to_an_http_exception(self):
        # 라우터만 올린 앱(다른 테스트들)에서도 상태·문구는 같다 — code 만 빠진다
        resp = _client(_app(handlers=False)).get("/api-error")
        assert resp.status_code == 503
        assert resp.json() == {"detail": "잠시 뒤"}

    def test_the_factories_follow_the_contract(self):
        s, m, q = errors.search_unavailable(), errors.storage_unavailable(), errors.queue_unavailable()
        assert (s.status_code, s.detail, s.code) == (503, SEARCH_UNAVAILABLE_DETAIL, "search_unavailable")
        assert (m.status_code, m.detail, m.code) == (503, STORAGE_UNAVAILABLE_DETAIL, "storage_unavailable")
        assert (q.status_code, q.detail) == (503, QUEUE_UNAVAILABLE_DETAIL)
        assert not hasattr(q, "code")      # 딥리서치 _broker_unavailable 과 같은 꼴(detail 만)
        assert SEARCH_UNAVAILABLE_DETAIL == "검색 서버가 잠시 응답하지 않아요. 잠시 뒤 다시 시도해 주세요"
        assert STORAGE_UNAVAILABLE_DETAIL == "원문 저장소가 잠시 응답하지 않아요. 잠시 뒤 다시 시도해 주세요"
        assert QUEUE_UNAVAILABLE_DETAIL == "작업 큐에 연결하지 못했어요 — 잠시 뒤 다시 시도해 주세요"

    def test_queue_message_matches_deep_research(self):
        # api.research 는 redis·relay 를 물고 와 여기서 import 하지 않는다(test_research_api 가 대역 위에서 올린다) —
        # 그 503 문구가 같은 글자인지만 본다
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "api" / "research.py").read_text(encoding="utf-8")
        assert f'detail="{QUEUE_UNAVAILABLE_DETAIL}"' in source


# ── 가드 ─────────────────────────────────────────────────
class TestGuards:
    def test_search_outage_becomes_503_search_unavailable(self):
        resp = _client(_app()).get("/search-down")
        assert resp.status_code == 503
        assert resp.json() == {"detail": SEARCH_UNAVAILABLE_DETAIL, "code": "search_unavailable"}

    def test_a_code_bug_inside_the_search_guard_stays_500(self):
        resp = _client(_app()).get("/search-bug")
        assert resp.status_code == 500
        assert resp.json()["code"] == "internal_error"

    def test_a_permanent_milvus_error_inside_the_search_guard_is_500_and_logged(self, caplog):
        # 컬렉션이 없어진 것 같은 오류는 '잠시 뒤 다시'로 낫지 않는다 — 500 으로 내고, 어느 검색에서 난 Milvus 오류인지 남긴다
        exceptions = pytest.importorskip("pymilvus.exceptions")
        app = _app()

        @app.get("/search-milvus-broken")
        async def search_milvus_broken():
            with search_outage_as_503("테스트 검색"):
                raise exceptions.MilvusException(code=100, message="collection not found[collection=nl_lib_chunks]")

        with caplog.at_level(logging.ERROR, logger=errors.log.name):
            resp = _client(app).get("/search-milvus-broken")
        assert resp.status_code == 500
        assert resp.json() == {"detail": INTERNAL_ERROR_DETAIL, "code": "internal_error"}
        messages = [r.getMessage() for r in caplog.records if r.name == errors.log.name and r.levelname == "ERROR"]
        assert any("[테스트 검색]" in m and "MilvusException" in m and "일시 장애 아님" in m for m in messages)

    def test_a_milvus_outage_inside_the_search_guard_is_503(self):
        app = _app()
        down = milvus_connect_failure()

        @app.get("/search-milvus-down")
        async def search_milvus_down():
            with search_outage_as_503("테스트 검색"):
                raise down

        resp = _client(app).get("/search-milvus-down")
        assert resp.status_code == 503
        assert resp.json() == {"detail": SEARCH_UNAVAILABLE_DETAIL, "code": "search_unavailable"}

    def test_http_exception_passes_through_every_guard(self):
        for guard in (search_outage_as_503, storage_outage_as_503, broker_outage_as_503):
            with pytest.raises(HTTPException) as caught:
                with guard("테스트"):
                    raise HTTPException(404, "없음")
            assert caught.value.status_code == 404 and not isinstance(caught.value, ApiError)

    def test_storage_guard(self):
        with pytest.raises(ApiError) as caught:
            with storage_outage_as_503("테스트"):
                raise ConnectionResetError("reset")
        assert caught.value.code == "storage_unavailable"
        assert isinstance(caught.value.__cause__, ConnectionResetError)

    def test_broker_guard(self):
        with pytest.raises(HTTPException) as caught:
            with broker_outage_as_503("테스트"):
                raise ConnectionRefusedError(111, "Connection refused")
        assert caught.value.status_code == 503 and caught.value.detail == QUEUE_UNAVAILABLE_DETAIL

    def test_guards_let_code_bugs_through(self):
        for guard in (search_outage_as_503, storage_outage_as_503, broker_outage_as_503):
            with pytest.raises(KeyError):
                with guard("테스트"):
                    raise KeyError("choices")


# ── 장애 판별 ─────────────────────────────────────────────
_BUGS = [TypeError("x"), KeyError("x"), ValueError("x"), AttributeError("x"), IndexError("x"), RuntimeError("x")]


class TestSearchOutage:
    @pytest.mark.parametrize("exc", [
        ConnectionRefusedError(111, "Connection refused"),
        TimeoutError("timed out"),
        httpx.ConnectError("vLLM down"),
        httpx.ReadTimeout("slow"),
    ], ids=lambda e: type(e).__name__)
    def test_connection_and_timeout_are_outages(self, exc):
        assert is_search_outage(exc)

    @pytest.mark.parametrize("exc", _BUGS, ids=lambda e: type(e).__name__)
    def test_code_bugs_are_not(self, exc):
        assert not is_search_outage(exc)

    # ── Milvus·grpc — 운영 이미지 pymilvus 2.4.6·grpc 가 실제로 던지는 것(milvus_errors.py) ──
    def test_milvus_down_at_connect_is_an_outage(self):
        # Milvus 가 꺼져 있으면 connections.connect 는 채널 대기 끝에 code=2 의 MilvusException 을 던진다
        exceptions = pytest.importorskip("pymilvus.exceptions")
        exc = milvus_connect_failure()
        assert type(exc) is exceptions.MilvusException and exc.code == 2
        assert is_search_outage(exc)

    def test_milvus_unreachable_after_retries_is_an_outage(self):
        # 연결이 끊긴 채 부른 RPC — pymilvus 는 UNAVAILABLE 을 재시도하다 MilvusException 으로 감싸 던지고, code 에는
        # grpc 오류의 code 메서드가 부르지 않은 채 실린다
        grpc = pytest.importorskip("grpc")
        exceptions = pytest.importorskip("pymilvus.exceptions")
        exc = milvus_retry_error("UNAVAILABLE")
        assert type(exc) is exceptions.MilvusException and callable(exc.code)
        assert exc.code() == grpc.StatusCode.UNAVAILABLE
        assert is_search_outage(exc)

    @pytest.mark.parametrize("code_name", ["UNAVAILABLE", "DEADLINE_EXCEEDED"])
    def test_grpc_unavailable_and_deadline_are_outages(self, code_name):
        assert is_search_outage(rpc_error(code_name))

    def test_a_deadline_through_pymilvus_is_still_the_raw_grpc_error(self):
        # pymilvus 는 기한 초과를 재시도하지 않고 날 grpc.RpcError 로 다시 던진다
        grpc = pytest.importorskip("grpc")
        exc = milvus_retry_error("DEADLINE_EXCEEDED")
        assert isinstance(exc, grpc.RpcError) and exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED
        assert is_search_outage(exc)

    def test_milvus_connection_classes_are_outages(self):
        exceptions = pytest.importorskip("pymilvus.exceptions")
        assert is_search_outage(exceptions.MilvusUnavailableException(message="unavailable"))
        assert is_search_outage(exceptions.ConnectError(message="Connect server fail"))

    def test_grpc_channel_wait_timeout_is_an_outage(self):
        grpc = pytest.importorskip("grpc")
        assert is_search_outage(grpc.FutureTimeoutError())

    # 기다려도 낫지 않는 Milvus 오류 — 503('잠시 뒤 다시')으로 가리지 않는다
    @pytest.mark.parametrize("name, kwargs", [
        ("DataTypeNotMatchException", {"message": "The Input data type is inconsistent with defined schema"}),
        ("SchemaNotReadyException", {"message": "Collection 'nl_lib_chunks' not exist, or you can pass in schema"}),
        ("CollectionNotExistException", {"message": "collection not found"}),
        ("ConnectionNotExistException", {"message": "should create connection first."}),
        ("IndexNotExistException", {"message": "Index doesn't exist."}),
        ("DataNotMatchException", {"message": "The data fields number is not match with schema."}),
        ("ParamError", {"message": "wrong vector dim"}),
        # 서버가 돌려준 오류(check_status) — code 는 Milvus 오류 번호다. 100 = 컬렉션 없음
        ("MilvusException", {"code": 100, "message": "collection not found[collection=nl_lib_chunks]"}),
        # pymilvus 가 알 수 없는 예외를 감싼 것(decorators.error_handler) — code 1(UNEXPECTED_ERROR)
        ("MilvusException", {"message": "Unexpected error, message=<'NoneType' object is not subscriptable>"}),
    ], ids=lambda v: v if isinstance(v, str) else None)
    def test_permanent_milvus_errors_are_not_outages(self, name, kwargs):
        exceptions = pytest.importorskip("pymilvus.exceptions")
        assert not is_search_outage(getattr(exceptions, name)(**kwargs))

    @pytest.mark.parametrize("code_name", ["INVALID_ARGUMENT", "UNIMPLEMENTED", "PERMISSION_DENIED"])
    def test_other_grpc_statuses_are_not_outages(self, code_name):
        assert not is_search_outage(rpc_error(code_name))

    def test_a_retried_server_error_is_not_an_outage(self):
        # INTERNAL 도 pymilvus 가 재시도하다 MilvusException 으로 감싼다 — 꼴은 UNAVAILABLE 과 같지만 상태가 다르다
        exceptions = pytest.importorskip("pymilvus.exceptions")
        exc = milvus_retry_error("INTERNAL")
        assert type(exc) is exceptions.MilvusException and callable(exc.code)
        assert not is_search_outage(exc)

    def test_a_bare_grpc_error_without_a_status_is_not_an_outage(self):
        grpc = pytest.importorskip("grpc")
        assert not is_search_outage(grpc.RpcError())

    def test_stubbed_modules_do_not_break_the_check(self, monkeypatch):
        # 로컬 테스트는 pymilvus 를 MagicMock 으로 갈아 끼우기도 한다(pipeline_stub) — isinstance 가 터지면 안 된다
        import sys
        monkeypatch.setitem(sys.modules, "pymilvus", MagicMock())
        monkeypatch.setitem(sys.modules, "pymilvus.exceptions", MagicMock())
        monkeypatch.setitem(sys.modules, "grpc", MagicMock())
        assert not is_search_outage(TypeError("x"))
        assert is_search_outage(ConnectionRefusedError())


class TestStorageOutage:
    def test_minio_down_is_an_outage(self):
        # MinIO 가 꺼져 있으면 minio 7.2 는 urllib3 재시도 끝에 MaxRetryError 를 던진다(운영 이미지에서 확인)
        urllib3_exceptions = pytest.importorskip("urllib3.exceptions")
        exc = urllib3_exceptions.MaxRetryError(None, "/nl-lib-bucket", reason=ConnectionRefusedError(111, "refused"))
        assert is_storage_outage(exc)

    def test_minio_server_error_is_an_outage(self):
        minio_error = pytest.importorskip("minio.error")
        assert is_storage_outage(minio_error.ServerError("503 Service Unavailable", 503))

    def test_a_missing_object_is_not_an_outage(self):
        minio_error = pytest.importorskip("minio.error")
        exc = minio_error.S3Error("NoSuchKey", "The specified key does not exist.", "/b/k", "r", "h", None)
        assert not is_storage_outage(exc)

    @pytest.mark.parametrize("exc", _BUGS, ids=lambda e: type(e).__name__)
    def test_code_bugs_are_not(self, exc):
        assert not is_storage_outage(exc)


class TestBrokerOutage:
    def test_kombu_operational_error_is_an_outage(self):
        # .delay()·control.revoke() 가 브로커(Redis)에 닿지 못하면 던지는 것 — 운영 이미지 celery 5.4 에서 확인
        kombu_exceptions = pytest.importorskip("kombu.exceptions")
        assert is_broker_outage(kombu_exceptions.OperationalError("Error 111 connecting to redis:6379."))

    def test_redis_errors_are_outages(self):
        redis_exceptions = pytest.importorskip("redis.exceptions")
        assert is_broker_outage(redis_exceptions.ConnectionError("x"))
        assert is_broker_outage(redis_exceptions.TimeoutError("x"))

    @pytest.mark.parametrize("exc", _BUGS, ids=lambda e: type(e).__name__)
    def test_code_bugs_are_not(self, exc):
        assert not is_broker_outage(exc)


# ── main.py 연결 ──────────────────────────────────────────
class TestAppWiring:
    def test_main_installs_the_error_handlers_on_its_app(self):
        # 위 테스트는 처리기를 직접 건 앱을 쓰고, 다른 API 테스트는 라우터만 올린 앱을 쓴다 — main.py 가 처리기 등록을
        # 빠뜨려도 모두 통과한다. main 은 DB·라우터를 물고 오므로 import 하지 않고 소스를 읽는다
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        imported = {
            (node.module, alias.name, alias.asname)
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert ("core.errors", "install_error_handlers", None) in imported

        # 모듈 맨 위에서 app = FastAPI(...) 를 만든 뒤 그 app 에 건다(함수 안·다른 앱에 거는 것은 치지 않는다)
        app_line = next(
            node.lineno for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "app" for t in node.targets)
            and isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) == "FastAPI"
        )
        installs = [
            node for node in tree.body
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "install_error_handlers"
        ]
        assert len(installs) == 1
        call = installs[0].value
        assert [getattr(a, "id", None) for a in call.args] == ["app"]
        assert installs[0].lineno > app_line
