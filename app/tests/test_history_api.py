"""test_history_api.py — 기록 API 엔드포인트

요청은 TestClient 로 실제 라우팅을 거친다(헤더 400·경로 422·본문 검증은 라우팅을 거쳐야
드러난다). DB 는 history_sqlite 의 SQLite 다 — 요청마다 세션을 새로 연다.

세션 대역은 get_db 의 마무리 커밋에 기대지 않는다 — 요청이 끝나면 늘 되돌리므로 핸들러가
응답 전에 직접 커밋한 것만 남는다. 마무리 커밋이 대신 남겨 주면, 핸들러의 커밋이 빠져
운영에서 마무리 커밋이 실패할 때(화면은 이미 성공 응답을 받아 outbox 에 다시 넣지 않는다)
기록이 조용히 사라지는 것을 여기서 잡지 못한다.
"""
import ast
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import (
    SID_A, SID_B, AsyncSessionOverSync, add_generation, add_research_job, add_work, make_engine,
    raw_row,
)

A = {"x-session-id": str(SID_A)}
B = {"x-session-id": str(SID_B)}


class _Api:
    def __init__(self, client, engine):
        self.client = client
        self.engine = engine

    def put(self, item_id, headers=A, **body):
        return self.client.put(f"/api/history/{item_id}", headers=headers,
                               json={"kind": "book", "title": "독서 격차", **body})


@pytest.fixture
def api():
    from api.history import router
    from core.deps import get_db

    engine = make_engine()

    async def _db():
        db = AsyncSessionOverSync(engine)
        try:
            yield db
        finally:
            # 성공해도 되돌린다 — 핸들러가 직접 커밋한 쓰기만 남아야 한다
            await db.rollback()
            await db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _db
    return _Api(TestClient(app), engine)


def _ids(res) -> list[str]:
    return [i["id"] for i in res.json()["items"]]


class TestBrowserIdHeader:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/history"),
        ("get", f"/api/history/{uuid.uuid4()}"),
        ("delete", f"/api/history/{uuid.uuid4()}"),
        ("delete", "/api/history?kind=book"),
    ])
    def test_missing_header_is_400(self, api, method, path):
        res = getattr(api.client, method)(path)
        assert res.status_code == 400
        assert res.json()["detail"] == "x-session-id 헤더가 필요하다"

    def test_put_without_header_is_400_and_saves_nothing(self, api):
        item_id = uuid.uuid4()
        assert api.put(item_id, headers={}).status_code == 400
        assert raw_row(api.engine, item_id) is None

    def test_import_without_header_is_400(self, api):
        res = api.client.post("/api/history/import", json={"items": []})
        assert res.status_code == 400


class TestPut:
    def test_repeat_is_safe(self, api):
        item_id = uuid.uuid4()
        assert api.put(item_id).status_code == 200
        res = api.put(item_id, title="독서 격차 해소")
        assert res.status_code == 200 and res.json()["title"] == "독서 격차 해소"
        assert _ids(api.client.get("/api/history", headers=A)) == [str(item_id)]

    def test_response_shape(self, api):
        item_id = uuid.uuid4()
        body = api.put(item_id, params={"grade": "KCI"}, snapshot={"papers": []}).json()
        assert body["id"] == str(item_id)
        assert body["snapshot"] == {"papers": []} and body["has_snapshot"] is True
        assert body["ai"] is None and body["has_ai"] is False
        assert body["research"] is None and body["ref_id"] is None
        assert {"created_at", "updated_at"} <= body.keys()

    def test_research_without_ref_id_is_422(self, api):
        res = api.put(uuid.uuid4(), kind="research", title="독서 격차 연구")
        assert res.status_code == 422

    def test_malformed_item_id_is_422(self, api):
        assert api.client.get("/api/history/not-a-uuid", headers=A).status_code == 422


class TestOwnership:
    """남의 기록은 읽기·쓰기·삭제 모두 404 — 존재 여부도 드러내지 않는다."""

    @pytest.fixture
    def item_id(self, api):
        item_id = uuid.uuid4()
        api.put(item_id, title="A 의 검색", snapshot={"books": [1]})
        return item_id

    def test_read_is_404(self, api, item_id):
        res = api.client.get(f"/api/history/{item_id}", headers=B)
        assert res.status_code == 404
        assert res.json()["detail"] == "기록을 찾을 수 없다"

    def test_put_is_404_and_does_not_overwrite(self, api, item_id):
        assert api.put(item_id, headers=B, title="덮어쓰기").status_code == 404
        assert raw_row(api.engine, item_id).title == "A 의 검색"

    def test_patch_is_404(self, api, item_id):
        res = api.client.patch(f"/api/history/{item_id}", headers=B, json={"title": "바꿈"})
        assert res.status_code == 404
        assert raw_row(api.engine, item_id).title == "A 의 검색"

    def test_delete_is_404(self, api, item_id):
        assert api.client.delete(f"/api/history/{item_id}", headers=B).status_code == 404
        assert raw_row(api.engine, item_id).deleted_at is None

    def test_other_browser_list_is_empty(self, api, item_id):
        assert api.client.get("/api/history", headers=B).json() == {"items": [], "next_cursor": None}

    def test_missing_item_is_same_404(self, api):
        assert api.client.get(f"/api/history/{uuid.uuid4()}", headers=A).status_code == 404


class TestPatch:
    def test_partial_update(self, api):
        item_id = uuid.uuid4()
        api.put(item_id, snapshot={"books": [1]})
        res = api.client.patch(f"/api/history/{item_id}", headers=A,
                               json={"ai": {"intro": "요약", "items": []}})
        assert res.status_code == 200
        body = res.json()
        assert body["ai"] == {"intro": "요약", "items": []} and body["snapshot"] == {"books": [1]}
        # 응답은 RETURNING 값이라 커밋이 빠져도 맞다 — 다음 요청에서 다시 읽어야 드러난다
        again = api.client.get(f"/api/history/{item_id}", headers=A).json()
        assert again["ai"] == {"intro": "요약", "items": []}

    def test_null_title_is_422(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        res = api.client.patch(f"/api/history/{item_id}", headers=A, json={"title": None})
        assert res.status_code == 422


class TestDelete:
    def test_soft_delete(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        res = api.client.delete(f"/api/history/{item_id}", headers=A)
        assert res.status_code == 204 and res.content == b""
        assert api.client.get(f"/api/history/{item_id}", headers=A).status_code == 404
        assert _ids(api.client.get("/api/history", headers=A)) == []
        # 행은 남는다 — 사용자 삭제는 데이터 삭제가 아니다
        assert raw_row(api.engine, item_id).deleted_at is not None

    def test_repeat_delete_is_204(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        api.client.delete(f"/api/history/{item_id}", headers=A)
        assert api.client.delete(f"/api/history/{item_id}", headers=A).status_code == 204

    def test_delete_kind(self, api):
        book, paper = uuid.uuid4(), uuid.uuid4()
        api.put(book, kind="book")
        api.put(paper, kind="paper")
        assert api.client.delete("/api/history?kind=book", headers=A).status_code == 204
        assert _ids(api.client.get("/api/history", headers=A)) == [str(paper)]
        assert raw_row(api.engine, book).deleted_at is not None

    def test_delete_without_kind_is_422(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        assert api.client.delete("/api/history", headers=A).status_code == 422
        assert raw_row(api.engine, item_id).deleted_at is None


class TestList:
    def test_kind_filter_and_limit_bounds(self, api):
        api.put(uuid.uuid4(), kind="book")
        paper = uuid.uuid4()
        api.put(paper, kind="paper")
        assert _ids(api.client.get("/api/history?kind=paper", headers=A)) == [str(paper)]
        assert api.client.get("/api/history?kind=chat", headers=A).status_code == 422
        assert api.client.get("/api/history?limit=0", headers=A).status_code == 422
        assert api.client.get("/api/history?limit=101", headers=A).status_code == 422

    def test_cursor_paging(self, api):
        items = [
            {"legacy_id": f"172700000000{n}", "kind": "book", "title": f"검색 {n}",
             "created_at": f"2026-09-0{n + 1}T09:00:00+00:00"}
            for n in range(3)
        ]
        api.client.post("/api/history/import", headers=A, json={"items": items})
        first = api.client.get("/api/history?limit=2", headers=A).json()
        assert [i["title"] for i in first["items"]] == ["검색 2", "검색 1"]
        second = api.client.get("/api/history", headers=A,
                                params={"limit": 2, "before": first["next_cursor"]}).json()
        assert [i["title"] for i in second["items"]] == ["검색 0"]
        assert second["next_cursor"] is None

    def test_malformed_cursor_is_400(self, api):
        res = api.client.get("/api/history?before=garbage", headers=A)
        assert res.status_code == 400


def _sized(size: int) -> dict:
    # {"b": "xxx…"} 의 직렬화 길이가 정확히 size 바이트가 되게 맞춘다
    return {"b": "x" * (size - len('{"b": ""}'))}


class TestSnapshotLimit:
    def test_at_limit_is_accepted(self, api):
        assert api.put(uuid.uuid4(), snapshot=_sized(200 * 1024)).status_code == 200

    def test_put_over_limit_is_413(self, api):
        item_id = uuid.uuid4()
        assert api.put(item_id, snapshot=_sized(200 * 1024 + 1)).status_code == 413
        assert raw_row(api.engine, item_id) is None

    def test_patch_over_limit_is_413(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        res = api.client.patch(f"/api/history/{item_id}", headers=A,
                               json={"snapshot": _sized(200 * 1024 + 1)})
        assert res.status_code == 413
        assert raw_row(api.engine, item_id).snapshot is None

    def test_limit_counts_utf8_bytes(self, api):
        # 한글 한 글자는 3바이트 — 글자 수로 세면 상한이 세 배로 느슨해진다
        snapshot = {"b": "가" * (70 * 1024)}
        assert api.put(uuid.uuid4(), snapshot=snapshot).status_code == 413

    def test_limit_is_not_ascii_escaped_length(self, api):
        # 반대쪽 퇴행 — ensure_ascii 로 재면 한글 한 글자가 가 6바이트가 되어 상한이 절반으로 엄격해진다.
        # UTF-8 로 약 180KB(상한 아래), ASCII 이스케이프로 약 360KB(상한 위)인 결과는 받아야 한다
        snapshot = {"b": "가" * (60 * 1024)}
        assert api.put(uuid.uuid4(), snapshot=snapshot).status_code == 200

    def test_import_drops_only_the_oversized_snapshot(self, api):
        res = api.client.post("/api/history/import", headers=A, json={"items": [
            {"legacy_id": "1727000000000", "kind": "book", "title": "큰 결과",
             "snapshot": _sized(200 * 1024 + 1)},
            {"legacy_id": "1727000000001", "kind": "book", "title": "작은 결과",
             "snapshot": {"books": [1]}},
        ]})
        assert res.status_code == 200 and res.json()["imported"] == 2
        by_title = {i["title"]: i for i in api.client.get("/api/history", headers=A).json()["items"]}
        assert by_title["큰 결과"]["has_snapshot"] is False
        assert by_title["작은 결과"]["has_snapshot"] is True


class TestParamsAndAiLimits:
    """snapshot 만 재면 params·ai 로 상한을 우회해, 인증 없는 요청이 행마다 수십 MB 를 쌓을 수 있다."""

    LIMITS = [("params", 8 * 1024), ("ai", 64 * 1024)]

    @pytest.mark.parametrize("field,limit", LIMITS)
    def test_at_limit_is_accepted(self, api, field, limit):
        assert api.put(uuid.uuid4(), **{field: _sized(limit)}).status_code == 200

    @pytest.mark.parametrize("field,limit", LIMITS)
    def test_put_over_limit_is_413(self, api, field, limit):
        item_id = uuid.uuid4()
        res = api.put(item_id, **{field: _sized(limit + 1)})
        assert res.status_code == 413 and field in res.json()["detail"]
        assert raw_row(api.engine, item_id) is None

    @pytest.mark.parametrize("field,limit", LIMITS)
    def test_patch_over_limit_is_413(self, api, field, limit):
        item_id = uuid.uuid4()
        api.put(item_id, params={"grade": "KCI"}, ai={"intro": "요약", "items": []})
        res = api.client.patch(f"/api/history/{item_id}", headers=A, json={field: _sized(limit + 1)})
        assert res.status_code == 413
        row = raw_row(api.engine, item_id)
        assert (row.params, row.ai) == ({"grade": "KCI"}, {"intro": "요약", "items": []})

    @pytest.mark.parametrize("field,limit", LIMITS)
    def test_limit_counts_utf8_bytes(self, api, field, limit):
        # 한글 한 글자는 3바이트 — 글자 수는 상한의 절반이어도 바이트로는 넘는다
        assert api.put(uuid.uuid4(), **{field: {"b": "가" * (limit // 2)}}).status_code == 413

    def test_import_drops_only_the_oversized_field(self, api):
        res = api.client.post("/api/history/import", headers=A, json={"items": [
            {"legacy_id": "1727000000000", "kind": "book", "title": "큰 조건",
             "params": _sized(8 * 1024 + 1), "ai": {"intro": "요약", "items": []}},
            {"legacy_id": "1727000000001", "kind": "paper", "title": "큰 요약",
             "params": {"grade": "KCI"}, "ai": _sized(64 * 1024 + 1)},
        ]})
        assert res.status_code == 200 and res.json()["imported"] == 2
        id_map = res.json()["id_map"]
        big_params = api.client.get(f"/api/history/{id_map['1727000000000']}", headers=A).json()
        # params 는 NOT NULL 칸이라 null 이 아니라 빈 조건으로 옮긴다
        assert big_params["params"] == {} and big_params["ai"] == {"intro": "요약", "items": []}
        big_ai = api.client.get(f"/api/history/{id_map['1727000000001']}", headers=A).json()
        assert big_ai["ai"] is None and big_ai["params"] == {"grade": "KCI"}


class TestImport:
    ITEMS = [
        {"legacy_id": "1727000000000", "kind": "book", "title": "도서 검색",
         "created_at": "2026-09-01T09:00:00Z", "ai": {"intro": "요약", "items": []}},
        {"legacy_id": "1727000000001", "kind": "paper", "title": "논문 검색",
         "params": {"grade": "KCI"}, "created_at": "2026-09-02T09:00:00Z"},
    ]

    def test_import_then_repeat(self, api):
        first = api.client.post("/api/history/import", headers=A, json={"items": self.ITEMS})
        assert first.status_code == 200
        body = first.json()
        assert (body["imported"], body["skipped"]) == (2, 0)
        assert set(body["id_map"]) == {"1727000000000", "1727000000001"}

        second = api.client.post("/api/history/import", headers=A, json={"items": self.ITEMS}).json()
        assert (second["imported"], second["skipped"]) == (0, 2)
        assert second["id_map"] == body["id_map"]

        # 옛 ?restore=<v1id> 는 id_map 으로 찾은 새 id 로 열린다
        restored = api.client.get(f"/api/history/{body['id_map']['1727000000000']}", headers=A)
        assert restored.status_code == 200
        assert restored.json()["ai"] == {"intro": "요약", "items": []}

    def test_more_than_100_is_422(self, api):
        items = [{"legacy_id": str(n), "kind": "book", "title": "검색"} for n in range(101)]
        res = api.client.post("/api/history/import", headers=A, json={"items": items})
        assert res.status_code == 422


class TestResearchStatus:
    _NOT_CONTINUED = {"phase": None, "progress": None, "generating": False}

    def test_list_and_detail_carry_job_status(self, api):
        job_id = add_research_job(api.engine, status="awaiting_approval", stage="planned")
        res = api.put(job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        assert res.json()["research"] == {
            "status": "awaiting_approval", "stage": "planned", **self._NOT_CONTINUED,
        }
        (item,) = api.client.get("/api/history?kind=research", headers=A).json()["items"]
        assert item["research"] == {
            "status": "awaiting_approval", "stage": "planned", **self._NOT_CONTINUED,
        }
        assert item["ref_id"] == str(job_id)

    def test_continued_research_carries_phase_and_open_generation(self, api):
        job_id = add_research_job(api.engine, status="completed", stage="synthesized")
        add_work(api.engine, job_id, owner_sid=str(SID_A))
        add_generation(api.engine, job_id, status="running")
        api.put(job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))

        (item,) = api.client.get("/api/history?kind=research", headers=A).json()["items"]

        assert item["research"] == {
            "status": "completed", "stage": "synthesized",
            "phase": "topics", "progress": {}, "generating": True,
        }


class TestAppWiring:
    def test_main_includes_history_router(self):
        # 테스트는 라우터를 직접 붙인다 — main.py 등록을 빠뜨려도 위 테스트는 모두 통과한다
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        imported = {
            (node.module, alias.name, alias.asname)
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        included = {
            node.args[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "include_router"
        }
        assert ("api.history", "router", "history_router") in imported
        assert "history_router" in included
