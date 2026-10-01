# app/tests/test_browser_id.py
import uuid

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.deps import get_browser_id, get_browser_id_optional

SID = "3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e"


class TestGetBrowserId:
    def test_valid_v4_is_returned_as_uuid(self):
        assert get_browser_id(SID) == uuid.UUID(SID)

    def test_uppercase_is_normalized(self):
        assert get_browser_id(SID.upper()) == uuid.UUID(SID)

    @pytest.mark.parametrize("raw", [
        None,
        "",
        "null",                                     # 옛 코드가 문자열 "null" 을 보낸 적이 있다
        "not-a-uuid",
        "00000000-0000-0000-0000-000000000000",     # 형식은 맞지만 v4 가 아니다
        "3f2b8c1e-4d5a-1b6c-8d7e-9f0a1b2c3d4e",     # v1
    ])
    def test_missing_or_malformed_is_400(self, raw):
        with pytest.raises(HTTPException) as e:
            get_browser_id(raw)
        assert e.value.status_code == 400
        assert e.value.detail == "x-session-id 헤더가 필요하다"


class TestGetBrowserIdOptional:
    def test_valid_is_returned(self):
        assert get_browser_id_optional(SID) == uuid.UUID(SID)

    @pytest.mark.parametrize("raw", [None, "", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
    def test_missing_or_malformed_is_none(self, raw):
        assert get_browser_id_optional(raw) is None


class TestHeaderWiring:
    """함수 직접 호출은 Header alias 를 거치지 않는다 — 라우팅을 거쳐 헤더 이름까지 본다."""

    @pytest.fixture
    def client(self):
        app = FastAPI()

        @app.get("/required")
        def required(browser_id: uuid.UUID = Depends(get_browser_id)):
            return {"browser_id": str(browser_id)}

        @app.get("/optional")
        def optional(browser_id: uuid.UUID | None = Depends(get_browser_id_optional)):
            return {"browser_id": str(browser_id) if browser_id else None}

        return TestClient(app)

    def test_header_is_read_case_insensitively(self, client):
        res = client.get("/required", headers={"X-Session-Id": SID})
        assert res.status_code == 200 and res.json() == {"browser_id": SID}

    def test_missing_header_is_400(self, client):
        res = client.get("/required")
        assert res.status_code == 400
        assert res.json()["detail"] == "x-session-id 헤더가 필요하다"

    def test_optional_without_header_is_none(self, client):
        res = client.get("/optional")
        assert res.status_code == 200 and res.json() == {"browser_id": None}
