"""test_storage_queue_errors.py — 원문 저장소(MinIO)·작업 큐(Celery 브로커) 장애의 오류 응답.

표지·원문 PDF(api/book.py):
- MinIO 연결 장애 → 503 {"detail": "원문 저장소가 잠시 응답하지 않습니다. 잠시 뒤 다시 시도하세요", "code": "storage_unavailable"}.
  전에는 _resolve_original_key 가 모든 예외를 '없음'으로 삼켜 404 가 되거나, 표지 ① 단계가 삼킨 뒤 다음 단계에서 500 이 났다.
- 원본이 없거나 깨져 표지를 못 그림 → 404(화면의 <img> 가 대체 표지로 바뀐다). 전에는 깨진 원본이 렌더 예외로 500 이었다.
- 원문 PDF 의 404 문구에 S3 오류 글(영문)을 싣지 않는다.

적재·업로드·취소·재시도·백필(api/book.py·api/admin.py): .delay()·control.revoke() 가 브로커에 닿지 못하면 503
{"detail": "작업 큐에 연결하지 못했습니다 — 잠시 후 다시 시도하세요"}(딥리서치 _enqueue 와 같은 문구). 코드 버그는 500.

MinIO·워커 모듈은 대역이다(workers.tasks·workers.celery_app 를 sys.modules 에 꽂는다). 예외는 운영 이미지의 실제 클래스
(urllib3 MaxRetryError·minio S3Error·kombu OperationalError·redis ConnectionError)를 쓴다. async 테스트 없음.
"""
import importlib
import io
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.errors import QUEUE_UNAVAILABLE_DETAIL, STORAGE_UNAVAILABLE_DETAIL, install_error_handlers
from pipeline_stub import stubbed_pipeline

_FORGET = ("api.book", "api.admin")
STORAGE_503 = {"detail": STORAGE_UNAVAILABLE_DETAIL, "code": "storage_unavailable"}
QUEUE_503 = {"detail": QUEUE_UNAVAILABLE_DETAIL}


def _minio_down():
    urllib3_exceptions = pytest.importorskip("urllib3.exceptions")
    # MinIO 가 꺼져 있을 때 minio 7.2 가 urllib3 재시도 끝에 던지는 것(운영 이미지에서 확인)
    return urllib3_exceptions.MaxRetryError(None, "/nl-lib-bucket", reason=ConnectionRefusedError(111, "refused"))


def _no_such_key():
    minio_error = pytest.importorskip("minio.error")
    return minio_error.S3Error("NoSuchKey", "The specified key does not exist.", "/nl-lib-bucket/k", "r", "h", None)


def _broker_down():
    kombu_exceptions = pytest.importorskip("kombu.exceptions")
    return kombu_exceptions.OperationalError("Error 111 connecting to redis:6379. Connection refused.")


class _Obj:
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)
        self.closed = False

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def close(self):
        self.closed = True

    def release_conn(self):
        pass


class _FakeMinio:
    """minio.Minio 대역 — objects 에 있는 키만 있다. down 이면 모든 호출이 그 예외를 던진다(get_down 은 get_object 만)."""

    def __init__(self, objects: dict[str, bytes] | None = None, *, down=None, get_down=None, missing=None):
        self.objects = dict(objects or {})
        self.down, self.get_down, self.missing = down, get_down, missing
        self.put: dict[str, bytes] = {}

    def _check(self):
        if self.down is not None:
            raise self.down

    def list_objects(self, bucket, prefix="", recursive=False):
        self._check()
        return [SimpleNamespace(object_name=k) for k in self.objects if k.startswith(prefix)]

    def stat_object(self, bucket, key):
        self._check()
        if key not in self.objects:
            raise self.missing
        return SimpleNamespace(size=len(self.objects[key]))

    def get_object(self, bucket, key):
        self._check()
        if self.get_down is not None:
            raise self.get_down
        if key not in self.objects:
            raise self.missing
        return _Obj(self.objects[key])

    def put_object(self, bucket, key, data, length, content_type=None):
        self._check()
        self.put[key] = data.read()


class _FakeDb:
    """표지의 cover_image_key 조회·취소/재시도의 library_catalog 조회에 정해 둔 행을 돌려준다. 실행한 SQL 을 적는다."""

    def __init__(self, row=None, scalar=0):
        self.row, self.scalar_value = row, scalar
        self.sql: list[str] = []
        self.commits = 0

    async def execute(self, stmt, params=None):
        try:
            self.sql.append(str(stmt))
        except Exception:   # 방언 없이 그리지 못하는 문장(백필 집계 등)은 이름만 적는다
            self.sql.append(type(stmt).__name__)
        row, scalar_value = self.row, self.scalar_value

        class _Result:
            def first(self):
                return row

            def scalar(self):
                return scalar_value

        return _Result()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


class _Task:
    """Celery 태스크 대역 — fail_after 건을 보낸 뒤부터 error 를 던진다(None 이면 처음부터)."""

    def __init__(self, error=None, fail_after: int = 0):
        self.error, self.fail_after = error, fail_after
        self.sent: list[tuple] = []

    def delay(self, *args, **kwargs):
        if self.error is not None and len(self.sent) >= self.fail_after:
            raise self.error
        self.sent.append((args, kwargs))
        return SimpleNamespace(id=f"task-{len(self.sent)}")


class _Env:
    def __init__(self, client, mods, monkeypatch, db):
        self.client, self.mods, self._mp, self.db = client, mods, monkeypatch, db
        self.minio = _FakeMinio(missing=_no_such_key())
        # _minio_client 는 매 요청에 부른다 — set_minio 로 바꾼 대역을 그때그때 돌려준다
        monkeypatch.setattr(mods["book"], "_minio_client", lambda: self.minio)

    def set_minio(self, **kw):
        kw.setdefault("missing", _no_such_key())
        self.minio = _FakeMinio(**kw)

    def tasks(self, **tasks: _Task) -> None:
        mod = types.ModuleType("workers.tasks")
        for name, task in tasks.items():
            setattr(mod, name, task)
        self._mp.setitem(sys.modules, "workers.tasks", mod)

    def celery(self, app) -> None:
        mod = types.ModuleType("workers.celery_app")
        mod.celery_app = app
        self._mp.setitem(sys.modules, "workers.celery_app", mod)


@pytest.fixture
def env(monkeypatch):
    gen = stubbed_pipeline(monkeypatch)
    next(gen)
    # api.book 은 pipeline 을 머리에서 import 한다 — 대역 위에서 새로 올리고 끝나면 import 전 그대로 되돌린다
    for name in _FORGET:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    mods = {name.rpartition(".")[2]: importlib.import_module(name) for name in _FORGET}
    from core.deps import get_db

    db = _FakeDb()

    async def _db():
        yield db

    app = FastAPI()
    install_error_handlers(app)
    for mod in mods.values():
        app.include_router(mod.router)
    app.dependency_overrides[get_db] = _db
    yield _Env(TestClient(app, raise_server_exceptions=False), mods, monkeypatch, db)
    for name in _FORGET:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)
    next(gen, None)


def _pdf(pages: int = 1) -> bytes:
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


# ── 원문 PDF ─────────────────────────────────────────────
class TestPdf:
    def test_storage_down_is_503(self, env):
        env.set_minio(down=_minio_down())
        resp = env.client.get("/api/books/CNTS-1/pdf")
        assert resp.status_code == 503 and resp.json() == STORAGE_503

    def test_missing_original_is_404(self, env):
        env.set_minio(objects={})
        resp = env.client.get("/api/books/CNTS-1/pdf")
        assert resp.status_code == 404 and resp.json() == {"detail": "PDF 없음"}

    def test_s3_error_text_does_not_reach_the_screen(self, env):
        # 폴더형 키는 목록에 있으나 그 객체를 읽지 못함 — 전에는 detail 이 'PDF 없음: S3 operation failed; code: …' 였다
        env.set_minio(objects={"originals/CNTS-1/a.pdf": b"%PDF"}, get_down=_no_such_key())
        resp = env.client.get("/api/books/CNTS-1/pdf")
        assert resp.status_code == 404 and resp.json() == {"detail": "PDF 없음"}

    def test_flat_key_original_streams(self, env):
        env.set_minio(objects={"originals/CNTS-1.pdf": b"%PDF-1.4 body"})
        resp = env.client.get("/api/books/CNTS-1/pdf")
        assert resp.status_code == 200 and resp.content == b"%PDF-1.4 body"
        assert resp.headers["content-type"] == "application/pdf"


class TestResolveOriginalKey:
    def test_missing_flat_key_is_none(self, env):
        assert env.mods["book"]._resolve_original_key(_FakeMinio(missing=_no_such_key()), "CNTS-1") is None

    def test_storage_failure_on_the_flat_key_is_not_swallowed(self, env):
        client = _FakeMinio(missing=_minio_down())   # 목록은 비었고 평탄형 확인에서 연결이 끊긴다
        with pytest.raises(Exception) as caught:
            env.mods["book"]._resolve_original_key(client, "CNTS-1")
        assert type(caught.value).__name__ == "MaxRetryError"


# ── 표지 ─────────────────────────────────────────────────
class TestThumbnail:
    def test_storage_down_is_503(self, env):
        env.set_minio(down=_minio_down())
        resp = env.client.get("/api/books/CNTS-1/thumbnail")
        assert resp.status_code == 503 and resp.json() == STORAGE_503

    def test_storage_down_on_the_cover_is_not_swallowed(self, env):
        # ① FLUX 표지 읽기에서 끊긴 것을 삼키고 다음 단계로 가면 같은 장애를 또 기다린다(재시도 약 6초씩)
        env.db.row = ("covers/CNTS-1.jpg",)
        env.set_minio(objects={"covers/CNTS-1.jpg": b"jpg"}, get_down=_minio_down())
        resp = env.client.get("/api/books/CNTS-1/thumbnail")
        assert resp.status_code == 503 and resp.json() == STORAGE_503

    def test_cover_image_is_served_first(self, env):
        env.db.row = ("covers/CNTS-1.jpg",)
        env.set_minio(objects={"covers/CNTS-1.jpg": b"cover-bytes", "thumbnails/CNTS-1.jpg": b"thumb"})
        resp = env.client.get("/api/books/CNTS-1/thumbnail")
        assert resp.status_code == 200 and resp.content == b"cover-bytes"

    def test_cached_thumbnail(self, env):
        env.set_minio(objects={"thumbnails/CNTS-1.jpg": b"thumb"})
        resp = env.client.get("/api/books/CNTS-1/thumbnail")
        assert resp.status_code == 200 and resp.content == b"thumb"

    def test_no_original_is_404(self, env):
        env.set_minio(objects={})
        resp = env.client.get("/api/books/CNTS-1/thumbnail")
        assert resp.status_code == 404

    @pytest.mark.parametrize("broken", [b"", b"not a pdf at all", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"],
                             ids=["empty", "not-pdf", "no-pages"])
    def test_broken_original_is_404_and_not_cached(self, env, broken):
        pytest.importorskip("fitz")
        env.set_minio(objects={"originals/CNTS-1/a.pdf": broken})
        resp = env.client.get("/api/books/CNTS-1/thumbnail")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "표지를 그리지 못했습니다: CNTS-1"}
        assert env.minio.put == {}

    def test_good_original_is_rendered_and_cached(self, env):
        env.set_minio(objects={"originals/CNTS-1/a.pdf": _pdf()})
        resp = env.client.get("/api/books/CNTS-1/thumbnail")
        assert resp.status_code == 200 and resp.headers["content-type"] == "image/jpeg"
        assert resp.content[:2] == b"\xff\xd8"                  # JPEG
        assert env.minio.put == {"thumbnails/CNTS-1.jpg": resp.content}


# ── 작업 큐 ──────────────────────────────────────────────
class TestQueue:
    def test_ingest_dispatch(self, env):
        task = _Task(_broker_down())
        env.tasks(ingest_books_batch=task)
        resp = env.client.post("/api/books/ingest", json={"cnts_ids": ["CNTS-1"]})
        assert resp.status_code == 503 and resp.json() == QUEUE_503

    def test_a_code_bug_in_dispatch_stays_500(self, env):
        env.tasks(ingest_books_batch=_Task(ValueError("bad args")))
        resp = env.client.post("/api/books/ingest", json={"cnts_ids": ["CNTS-1"]})
        assert resp.status_code == 500 and resp.json()["code"] == "internal_error"

    def test_batch_stops_at_the_first_failure(self, env):
        task = _Task(_broker_down(), fail_after=1)
        env.tasks(process_from_minio=task, process_book_file=_Task())
        resp = env.client.post("/api/books/ingest/batch", json={"files": [
            {"book_id": "A", "minio_key": "originals/A.pdf"}, {"book_id": "B", "minio_key": "originals/B.pdf"},
        ]})
        assert resp.status_code == 503 and resp.json() == QUEUE_503
        assert [a for a, _ in task.sent] == [("A", "originals/A.pdf")]

    def test_upload_storage_down_is_503_and_nothing_is_queued(self, env):
        task = _Task()
        env.tasks(process_from_minio=task)
        env.set_minio(down=_minio_down())
        resp = env.client.post("/api/books/ingest/upload", files={"file": ("CNTS-9.pdf", b"%PDF", "application/pdf")})
        assert resp.status_code == 503 and resp.json() == STORAGE_503
        assert task.sent == []

    def test_upload_queue_down_is_503(self, env):
        env.tasks(process_from_minio=_Task(_broker_down()))
        resp = env.client.post("/api/books/ingest/upload", files={"file": ("CNTS-9.pdf", b"%PDF", "application/pdf")})
        assert resp.status_code == 503 and resp.json() == QUEUE_503
        assert env.minio.put == {"originals/CNTS-9/CNTS-9.pdf": b"%PDF"}

    def test_retry_dispatch(self, env):
        env.db.row = ("failed", "originals/CNTS-1.pdf")
        env.tasks(process_from_minio=_Task(_broker_down()))
        resp = env.client.post("/api/books/CNTS-1/retry")
        assert resp.status_code == 503 and resp.json() == QUEUE_503

    def test_cancel_does_not_touch_lock_or_state_when_revoke_fails(self, env, monkeypatch):
        released = []
        monkeypatch.setattr("core.lock.force_release", lambda cid: released.append(cid) or True)

        class _Control:
            def revoke(self, *args, **kwargs):
                raise _broker_down()

        env.celery(SimpleNamespace(control=_Control()))
        env.db.row = ("CNTS-1",)
        resp = env.client.post("/api/books/ingest/task-1/cancel")
        assert resp.status_code == 503 and resp.json() == QUEUE_503
        assert released == []
        assert not any("UPDATE library_catalog" in s for s in env.db.sql) and env.db.commits == 0

    def test_task_status_backend_down_is_503(self, env):
        redis_exceptions = pytest.importorskip("redis.exceptions")

        class _Result:
            @property
            def status(self):
                raise redis_exceptions.ConnectionError("Error 111 connecting to redis:6379.")

        env.celery(SimpleNamespace(AsyncResult=lambda tid: _Result()))
        resp = env.client.get("/api/books/ingest/task-1")
        assert resp.status_code == 503 and resp.json() == QUEUE_503

    @pytest.mark.parametrize("path, task_name", [
        ("/api/admin/backfill/plot", "backfill_plot"),
        ("/api/admin/backfill/read-effect", "backfill_read_effect"),
        ("/api/admin/backfill/summary", "backfill_summary"),
    ])
    def test_admin_backfills(self, env, path, task_name):
        env.db.scalar_value = 3
        env.tasks(**{task_name: _Task(_broker_down())})
        resp = env.client.post(path)
        assert resp.status_code == 503 and resp.json() == QUEUE_503
