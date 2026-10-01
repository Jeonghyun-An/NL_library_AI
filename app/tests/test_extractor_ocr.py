"""extract_text OCR — VLM 잘림 다듬기(4-1), 문서 안 동시 요청·렌더 잠금·데드라인·OCR 실패 폴백(4-2)."""
import asyncio

import httpx
import pytest

from services.ingestion import extractor
from services.ingestion.extractor import PageResult, VlmDegenerateOutput

LEAD = "이 논문은 북위 조정의 관직 수여 기록을 분석하고 그 의미를 살핀다. "


class _Page:
    number = 4


def _vlm(monkeypatch, content: str, finish: str) -> PageResult:
    """실제 _extract_with_vlm 을 목 HTTP 응답으로 부른다(렌더링은 목)."""
    monkeypatch.setattr(extractor, "_render_png_b64", lambda page: "QUJD")

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})

    async def go() -> PageResult:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await extractor._extract_with_vlm(_Page(), client)

    return asyncio.run(go())


def test_length_finish_trims_repeated_tail(monkeypatch):
    page = _vlm(monkeypatch, LEAD + "고위직을 내려주고, 이후 " * 300, "length")
    assert page.truncated
    assert page.text.startswith(LEAD.strip())
    assert page.text.count("고위직을 내려주고") == 1


def test_degenerate_length_output_raises(monkeypatch):
    with pytest.raises(VlmDegenerateOutput):
        _vlm(monkeypatch, "| | | |\n" * 400, "length")


def test_stop_finish_is_not_trimmed(monkeypatch):
    content = LEAD + "같은 문장이 반복된다. " * 10
    page = _vlm(monkeypatch, content, "stop")
    assert page.text == content.strip()
    assert not page.truncated
