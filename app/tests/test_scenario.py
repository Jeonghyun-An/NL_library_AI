"""test_scenario.py — 시나리오 추천 단위 테스트."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from services.search.scenario import _parse_scenario_result, recommend_books


# ── _parse_scenario_result ───────────────────────────────────────

def test_parse_clean_json():
    """정상 JSON 파싱."""
    content = json.dumps({
        "items": [
            {"book_id": "B001", "reason": "내면의 기강 바로잡기", "quote": "재앙은 언제나 느닷없이 찾아온다."},
            {"book_id": "B002", "reason": "무기력증 깨부수기", "quote": "네 안의 불꽃은 꺼지지 않았어."},
        ]
    })
    result = _parse_scenario_result(content)
    assert result is not None
    assert len(result["items"]) == 2
    assert result["items"][0]["reason"] == "내면의 기강 바로잡기"
    assert result["items"][1]["quote"] == "네 안의 불꽃은 꺼지지 않았어."


def test_parse_json_fenced():
    """```json 코드 블록 감싸인 출력 파싱."""
    content = '```json\n{"items": [{"book_id": "X", "reason": "r", "quote": "q"}]}\n```'
    result = _parse_scenario_result(content)
    assert result is not None
    assert result["items"][0]["book_id"] == "X"


def test_parse_missing_book_id_skipped():
    """book_id 없는 item 제외."""
    content = json.dumps({
        "items": [
            {"reason": "book_id 없음", "quote": "q"},
            {"book_id": "B001", "reason": "r", "quote": "q"},
        ]
    })
    result = _parse_scenario_result(content)
    assert result is not None
    assert len(result["items"]) == 1
    assert result["items"][0]["book_id"] == "B001"


def test_parse_invalid_json_returns_none():
    assert _parse_scenario_result("유효하지 않은 텍스트") is None


def test_parse_missing_reason_and_quote_default_empty():
    """reason/quote 없으면 빈 문자열 기본값."""
    content = json.dumps({"items": [{"book_id": "B001"}]})
    result = _parse_scenario_result(content)
    assert result is not None
    assert result["items"][0]["reason"] == ""
    assert result["items"][0]["quote"] == ""


# ── recommend_books ──────────────────────────────────────────────

def _make_book(cnts_id, title="책 제목", summary="요약", plot="줄거리",
               read_effect="읽고 난 후", themes="주제"):
    book = MagicMock()
    book.cnts_id = cnts_id
    book.title = title
    book.personal_author = "저자명"
    book.corporate_author = None
    book.summary = summary
    book.plot = plot
    book.read_effect = read_effect
    book.themes = themes
    return book


def _mock_resp(content: str):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def test_recommend_books_returns_reason_and_quote():
    """정상 LLM 응답 → reason + quote 반환."""
    books = [_make_book("B001"), _make_book("B002")]
    llm_output = json.dumps({
        "items": [
            {"book_id": "B001", "reason": "태그라인1", "quote": "인용구1"},
            {"book_id": "B002", "reason": "태그라인2", "quote": "인용구2"},
        ]
    })

    async def _run():
        with patch("services.search.scenario.httpx.AsyncClient") as MockClient:
            mc = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mc
            mc.post = AsyncMock(return_value=_mock_resp(llm_output))
            return await recommend_books("힘들어", books)

    result = asyncio.run(_run())
    assert len(result["items"]) == 2
    assert result["items"][0]["reason"] == "태그라인1"
    assert result["items"][0]["quote"] == "인용구1"


def test_recommend_books_fallback_on_parse_error():
    """JSON 파싱 실패 → reason/quote 빈 fallback."""
    books = [_make_book("B001")]

    async def _run():
        with patch("services.search.scenario.httpx.AsyncClient") as MockClient:
            mc = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mc
            mc.post = AsyncMock(return_value=_mock_resp("JSON 아님"))
            return await recommend_books("힘들어", books)

    result = asyncio.run(_run())
    assert result["items"][0]["book_id"] == "B001"
    assert result["items"][0]["reason"] == ""
    assert result["items"][0]["quote"] == ""


def test_recommend_books_context_includes_read_effect():
    """recommend_books 컨텍스트에 read_effect가 포함된다."""
    book = _make_book("B001", read_effect="읽으면 위로가 됩니다")

    async def _run():
        captured = {}
        with patch("services.search.scenario.httpx.AsyncClient") as MockClient:
            mc = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mc

            async def _capture(url, json=None, **kwargs):
                captured["payload"] = json
                return _mock_resp('{"items":[{"book_id":"B001","reason":"r","quote":"q"}]}')

            mc.post = _capture
            await recommend_books("힘들어", [book])
        return captured

    captured = asyncio.run(_run())
    user_msg = captured["payload"]["messages"][1]["content"]
    assert "읽으면 위로가 됩니다" in user_msg


def test_recommend_books_fallback_on_http_error():
    """HTTP 오류 → fallback 반환, 예외 없음."""
    books = [_make_book("B001"), _make_book("B002")]

    async def _run():
        with patch("services.search.scenario.httpx.AsyncClient") as MockClient:
            mc = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mc
            mc.post = AsyncMock(side_effect=Exception("connection error"))
            return await recommend_books("힘들어", books)

    result = asyncio.run(_run())
    assert len(result["items"]) == 2
    assert all(item["reason"] == "" for item in result["items"])
