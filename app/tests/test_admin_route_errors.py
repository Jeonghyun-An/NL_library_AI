"""test_admin_route_errors.py — 운영자 화면 API 의 경로·잘못된 id 처리.

- DELETE /api/admin/embedding/all 이 /embedding/{cnts_id} 에 가려지던 경로 순서 버그. 전에는 'all' 이 cnts_id 로 잡혀
  전체 삭제 대신 'all' 이라는 도서 한 권의 임베딩 삭제가 돌았고 confirm 검사도 거치지 않았다.
- ingest_jobs 의 {job_id} 는 uuid 로 받는다 — uuid 가 아니면 422(전에는 Postgres uuid 칼럼 비교에서 500). 없는 잡의
  retry 는 404(전에는 0건 재시도 200).

DB 는 문장을 SQL 로 구별하는 대역 세션이다. async 테스트 없음.
"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from api import admin, ingest_jobs
from core.deps import get_db
from core.errors import install_error_handlers

JOB_ID = "1ca22f59-1e50-4dd1-81f5-2d3c79126825"


class _Result:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar


class _FakeDb:
    def __init__(self, job=None):
        self.job = job
        self.sql: list[str] = []
        self.params: list[dict] = []

    async def execute(self, stmt, params=None):
        compiled = stmt.compile(dialect=postgresql.dialect())
        self.sql.append(str(compiled))
        self.params.append(dict(compiled.params))
        if "FROM ingest_jobs" in str(compiled):
            return _Result(self.job)
        return _Result(0)

    async def commit(self):
        pass

    async def rollback(self):
        pass


def _client(*routers, db=None) -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    for r in routers:
        app.include_router(r)

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    return TestClient(app, raise_server_exceptions=False)


# ── /api/admin/embedding/all 경로 순서 ─────────────────────
class TestEmbeddingRoutes:
    def test_all_is_declared_before_the_single_book_route(self):
        paths = [r.path for r in admin.router.routes if "DELETE" in getattr(r, "methods", set())]
        assert paths.index("/api/admin/embedding/all") < paths.index("/api/admin/embedding/{cnts_id}")

    def test_delete_all_reaches_the_bulk_handler(self, monkeypatch):
        # 한 권 삭제 경로로 가면 confirm 을 묻지 않고 SyncSessionLocal 을 연다 — 불리면 실패로 본다
        monkeypatch.setattr(admin, "_delete_embedding", lambda *a: pytest.fail("한 권 삭제로 갔다"))
        client = _client(admin.router)
        no_confirm = client.delete("/api/admin/embedding/all")
        assert no_confirm.status_code == 422                     # confirm 쿼리가 필수다 — 전체 삭제 처리기다
        wrong = client.delete("/api/admin/embedding/all", params={"confirm": "no"})
        assert wrong.status_code == 400
        assert wrong.json() == {"detail": "confirm=yes 를 쿼리 파라미터로 전달하세요."}

    def test_a_single_book_still_reaches_its_handler(self, monkeypatch):
        seen = []
        monkeypatch.setattr(admin, "_delete_embedding", lambda cid, db: seen.append(cid) or {"cnts_id": cid})

        class _Session:
            def close(self):
                pass

        import db.postgres as postgres
        monkeypatch.setattr(postgres, "SyncSessionLocal", lambda: _Session())
        resp = _client(admin.router).delete("/api/admin/embedding/CNTS-1")
        assert resp.status_code == 200 and seen == ["CNTS-1"]


# ── ingest_jobs 의 잘못된 job_id ───────────────────────────
class TestIngestJobIds:
    @pytest.mark.parametrize("method, path", [
        ("get", "/api/admin/ingest-jobs/not-a-uuid"),
        ("get", "/api/admin/ingest-jobs/not-a-uuid/items"),
        ("get", "/api/admin/ingest-jobs/not-a-uuid/failures"),
        ("post", "/api/admin/ingest-jobs/not-a-uuid/start"),
        ("post", "/api/admin/ingest-jobs/not-a-uuid/pause"),
        ("post", "/api/admin/ingest-jobs/not-a-uuid/resume"),
        ("post", "/api/admin/ingest-jobs/not-a-uuid/cancel"),
        ("post", "/api/admin/ingest-jobs/not-a-uuid/retry"),
    ])
    def test_malformed_id_is_422_without_touching_the_db(self, method, path):
        db = _FakeDb()
        client = _client(ingest_jobs.router, db=db)
        kwargs = {"json": {"all_failed": True}} if path.endswith("/retry") else {}
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code == 422
        assert db.sql == []

    def test_missing_job_is_404(self):
        resp = _client(ingest_jobs.router, db=_FakeDb(job=None)).get(f"/api/admin/ingest-jobs/{JOB_ID}")
        assert resp.status_code == 404 and resp.json() == {"detail": "잡 없음"}

    def test_retry_of_a_missing_job_is_404_and_nothing_is_reset(self, monkeypatch):
        import services.ingestion.job_manager as job_manager
        called = []
        monkeypatch.setattr(job_manager, "retry_items", lambda *a, **kw: called.append(a) or 7)
        resp = _client(ingest_jobs.router, db=_FakeDb(job=None)).post(
            f"/api/admin/ingest-jobs/{JOB_ID}/retry", json={"all_failed": True})
        assert resp.status_code == 404 and resp.json() == {"detail": "잡 없음"}
        assert called == []

    def test_retry_of_an_existing_job_resets_its_items(self, monkeypatch):
        import services.ingestion.job_manager as job_manager
        called = []
        monkeypatch.setattr(job_manager, "retry_items",
                            lambda job_id, **kw: called.append((job_id, kw)) or 7)
        db = _FakeDb(job=uuid.UUID(JOB_ID))
        resp = _client(ingest_jobs.router, db=db).post(
            f"/api/admin/ingest-jobs/{JOB_ID}/retry", json={"all_failed": True})
        assert resp.status_code == 200 and resp.json() == {"id": JOB_ID, "retried": 7}
        assert called[0][0] == uuid.UUID(JOB_ID) and called[0][1]["all_failed"] is True
        assert db.params[0] == {"id_1": uuid.UUID(JOB_ID)}       # 잡 확인은 uuid 값으로 묻는다

    def test_status_change_answers_with_the_id_as_text(self):
        job = SimpleNamespace(status="paused")
        resp = _client(ingest_jobs.router, db=_FakeDb(job=job)).post(f"/api/admin/ingest-jobs/{JOB_ID}/resume")
        assert resp.status_code == 200 and resp.json() == {"id": JOB_ID, "status": "running"}
        assert job.status == "running"
