"""milvus_errors.py — 검색 기반(pymilvus·grpc)이 실제로 던지는 예외를 만드는 테스트 도우미.

core/errors.is_search_outage 가 연결 장애(503)와 영구 오류(500)를 가르는 것은 예외의 꼴 — code 가 어디에 어떤 값으로
실리는지 — 에 달려 있다. 그래서 흉내 낸 클래스 대신 운영 이미지(pymilvus 2.4.6·grpc 1.x)가 실제로 만드는 것을 쓴다:
- rpc_error(code): 이 프로세스에 띄운 작은 grpc 서버가 그 상태로 끝낸 호출의 진짜 grpc.RpcError(_InactiveRpcError)
- milvus_retry_error(code): 같은 호출을 pymilvus.decorators.retry_on_rpc_failure 로 감싸 받은 것. 재시도하는 상태
  (UNAVAILABLE·INTERNAL 등)면 재시도 끝에 MilvusException 이 오는데, code 에 grpc 오류의 code 메서드가 부르지 않은 채
  실린다. 재시도하지 않는 상태(DEADLINE_EXCEEDED·INVALID_ARGUMENT 등)면 날 grpc.RpcError 가 그대로 온다
- milvus_connect_failure(): 닫힌 포트로 connections.connect 를 불러 받은 MilvusException(code=2, 'Fail connecting …')
pymilvus·grpc 가 없는 환경(로컬 venv)에서는 importorskip 으로 그 테스트를 건너뛴다.

쓰는 곳: test_error_handlers.py·test_search_outage_api.py.
"""
import socket
from concurrent import futures
from contextlib import contextmanager

import pytest

_SERVICE = "milvus.proto.milvus.MilvusService"


@contextmanager
def _server_ending_with(code_name: str):
    """Search 호출을 code_name 상태로 끝내는 grpc 서버를 띄우고 그 주소를 준다."""
    grpc = pytest.importorskip("grpc")
    code = getattr(grpc.StatusCode, code_name)

    def _search(request, context):
        context.abort(code, f"테스트 서버가 {code_name} 로 끝냈다")

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(
        _SERVICE, {"Search": grpc.unary_unary_rpc_method_handler(_search)}),))
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield f"127.0.0.1:{port}"
    finally:
        server.stop(None)


@contextmanager
def _search_call(code_name: str):
    grpc = pytest.importorskip("grpc")
    with _server_ending_with(code_name) as address:
        channel = grpc.insecure_channel(address)
        try:
            yield channel.unary_unary(f"/{_SERVICE}/Search")
        finally:
            channel.close()


def rpc_error(code_name: str) -> BaseException:
    """그 상태로 끝난 호출의 진짜 grpc.RpcError."""
    grpc = pytest.importorskip("grpc")
    with _search_call(code_name) as call:
        try:
            call(b"", timeout=5)
        except grpc.RpcError as e:
            return e
    pytest.fail(f"{code_name} 로 끝나야 할 호출이 성공했다")


def milvus_retry_error(code_name: str) -> BaseException:
    """pymilvus 의 재시도 데코레이터를 거친 호출이 그 상태로 끝났을 때 받는 예외."""
    decorators = pytest.importorskip("pymilvus.decorators")

    class _Handler:
        @decorators.retry_on_rpc_failure(retry_times=1, initial_back_off=0.001)
        def search(self, call):
            return call(b"", timeout=5)

    with _search_call(code_name) as call:
        try:
            _Handler().search(call)
        except Exception as e:      # noqa: BLE001 — 무엇이 오는지를 보려는 것이다
            return e
    pytest.fail(f"{code_name} 로 끝나야 할 호출이 성공했다")


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def milvus_connect_failure() -> BaseException:
    """Milvus 가 꺼져 있을 때 connections.connect 가 던지는 예외 — 채널이 기한 안에 열리지 않아 code=2 다."""
    pymilvus = pytest.importorskip("pymilvus")
    alias = "milvus-errors-probe"
    try:
        pymilvus.connections.connect(alias=alias, host="127.0.0.1", port=_closed_port(), timeout=0.3)
    except Exception as e:      # noqa: BLE001
        return e
    finally:
        pymilvus.connections.remove_connection(alias)
    pytest.fail("닫힌 포트에 연결됐다")
