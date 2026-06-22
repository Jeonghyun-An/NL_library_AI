"""test_curate_books.py — 큐레이션 리포트 단위 테스트."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.search.curator import _parse_curation_result, curate_books


# ── _parse_curation_result ───────────────────────────────────────

def test_parse_clean_json():
    """깔끔한 JSON 입력 파싱."""
    content = json.dumps({
        "intro": "세 권의 도서 소개.",
        "items": [
            {"book_id": "B001", "reason": "이유 1"},
            {"book_id": "B002", "reason": "이유 2"},
        ],
    })
    result = _parse_curation_result(content)
    assert result is not None
    assert result["intro"] == "세 권의 도서 소개."
    assert len(result["items"]) == 2
    assert result["items"][0]["book_id"] == "B001"


def test_parse_json_fenced():
    """```json 코드 블록으로 감싸인 출력 파싱."""
    content = '```json\n{"intro": "소개", "items": [{"book_id": "X", "reason": "r"}]}\n```'
    result = _parse_curation_result(content)
    assert result is not None
    assert result["intro"] == "소개"
    assert result["items"][0]["book_id"] == "X"


def test_parse_items_missing_book_id_skipped():
    """book_id 없는 item은 조용히 제외된다."""
    content = json.dumps({
        "intro": "소개",
        "items": [
            {"reason": "book_id 없음"},
            {"book_id": "B001", "reason": "이유"},
        ],
    })
    result = _parse_curation_result(content)
    assert result is not None
    assert len(result["items"]) == 1
    assert result["items"][0]["book_id"] == "B001"


def test_parse_invalid_json_returns_none():
    """유효하지 않은 JSON → None 반환."""
    assert _parse_curation_result("이건 JSON이 아닙니다") is None


def test_parse_empty_items():
    """items가 빈 배열이어도 오류 없이 파싱."""
    content = json.dumps({"intro": "소개만", "items": []})
    result = _parse_curation_result(content)
    assert result is not None
    assert result["intro"] == "소개만"
    assert result["items"] == []


def test_parse_missing_intro_defaults_empty():
    """intro 키 없으면 빈 문자열 기본값."""
    content = json.dumps({"items": [{"book_id": "B001", "reason": "r"}]})
    result = _parse_curation_result(content)
    assert result is not None
    assert result["intro"] == ""


# ── curate_books ─────────────────────────────────────────────────

def _make_book(cnts_id, title="테스트 책", summary="요약", plot="줄거리", themes="주제"):
    book = MagicMock()
    book.cnts_id = cnts_id
    book.title = title
    book.personal_author = "저자명"
    book.corporate_author = None
    book.summary = summary
    book.plot = plot
    book.themes = themes
    return book


def _mock_llm_response(content: str):
    """httpx POST 응답 mock 생성."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


def test_curate_books_returns_parsed_result():
    """정상 LLM 응답 → intro + items 반환."""
    books = [_make_book("B001"), _make_book("B002")]
    llm_output = json.dumps({
        "intro": "두 권의 큐레이션 소개.",
        "items": [
            {"book_id": "B001", "reason": "첫 번째 이유"},
            {"book_id": "B002", "reason": "두 번째 이유"},
        ],
    })

    async def _run():
        with patch("services.search.curator.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=_mock_llm_response(llm_output))
            return await curate_books("우울할 때 위로", "위로되는 책", books)

    result = asyncio.run(_run())
    assert result["intro"] == "두 권의 큐레이션 소개."
    assert len(result["items"]) == 2
    assert result["items"][0]["book_id"] == "B001"


def test_curate_books_fallback_on_json_error():
    """LLM이 JSON 아닌 텍스트 반환 → 빈 fallback 반환, 오류 없음."""
    books = [_make_book("B001")]

    async def _run():
        with patch("services.search.curator.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=_mock_llm_response("JSON 아닌 응답"))
            return await curate_books("의도", "질의", books)

    result = asyncio.run(_run())
    assert result["intro"] == ""
    assert result["items"][0]["book_id"] == "B001"
    assert result["items"][0]["reason"] == ""


def test_curate_books_fallback_on_http_error():
    """HTTP 오류 발생 → fallback 반환, 오류 없음."""
    books = [_make_book("B001"), _make_book("B002")]

    async def _run():
        with patch("services.search.curator.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(side_effect=Exception("connection failed"))
            return await curate_books("의도", "질의", books)

    result = asyncio.run(_run())
    assert result["intro"] == ""
    assert len(result["items"]) == 2


def test_curate_books_context_includes_plot_and_themes():
    """curate_books 컨텍스트 빌더가 plot과 themes를 포함한다.

    LLM 호출 인자를 캡처해 books_context에 줄거리/테마가 들어있는지 확인.
    """
    book = _make_book("B001", plot="줄거리 내용", themes="주제1,주제2")

    async def _run():
        captured = {}
        with patch("services.search.curator.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client

            async def _capture_post(url, json=None, **kwargs):
                captured["payload"] = json
                return _mock_llm_response('{"intro":"소개","items":[{"book_id":"B001","reason":"r"}]}')

            mock_client.post = _capture_post
            await curate_books("의도", "질의", [book])
        return captured

    captured = asyncio.run(_run())
    user_msg = captured["payload"]["messages"][1]["content"]
    assert "줄거리 내용" in user_msg
    assert "주제1,주제2" in user_msg
