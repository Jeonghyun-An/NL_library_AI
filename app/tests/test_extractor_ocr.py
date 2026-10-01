"""extract_text OCR — VLM 잘림 다듬기(4-1), 문서 안 동시 요청·렌더 잠금·데드라인·OCR 실패 폴백(4-2)."""
import asyncio
import time

import fitz
import httpx
import pytest

from services.ingestion import extractor
from services.ingestion.extractor import ExtractionResult, PageResult, VlmDegenerateOutput

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


# ── 4-2 ──────────────────────────────────────────────────────


def _blank_pdf(n_pages: int) -> bytes:
    """텍스트 층이 없는 쪽만 — fitz 0자라 전부 OCR 로 간다."""
    doc = fitz.open()
    for _ in range(n_pages):
        doc.new_page(width=200, height=300)
    data = doc.tobytes()
    doc.close()
    return data


def _odl_default(n: int) -> str:
    return f"ODL 대체 {n}"


def _patch(monkeypatch, n_pages: int, fake_vlm=None, *, concurrency: int = 2, odl_text=_odl_default) -> None:
    """ODL 은 목(쪽마다 odl_text(n)), fake_vlm 이 None 이면 실제 _extract_with_vlm 을 그대로 쓴다."""
    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None):
        res = ExtractionResult(book_id=book_id, total_pages=n_pages)
        res.pages = [PageResult(n, odl_text(n), "opendataloader", 0.95) for n in range(n_pages)]
        return res

    monkeypatch.setattr(extractor, "extract_text_opendataloader", fake_odl)
    if fake_vlm is not None:
        monkeypatch.setattr(extractor, "_extract_with_vlm", fake_vlm)
    monkeypatch.setattr(extractor.cfg, "OCR_ENGINE", "vlm")
    monkeypatch.setattr(extractor.cfg, "VLM_PAGE_CONCURRENCY", concurrency)


def _extract(n_pages: int, **kwargs) -> ExtractionResult:
    return asyncio.run(extractor.extract_text(None, "T_OCR", file_bytes=_blank_pdf(n_pages), **kwargs))


def test_render_happens_inside_render_lock(monkeypatch):
    seen: list[bool] = []

    async def go() -> PageResult:
        lock = asyncio.Lock()

        def fake_render(page):
            seen.append(lock.locked())
            return "QUJD"

        monkeypatch.setattr(extractor, "_render_png_b64", fake_render)

        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": "본문"}, "finish_reason": "stop"}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await extractor._extract_with_vlm(_Page(), client, render_lock=lock)

    assert asyncio.run(go()).text == "본문"
    assert seen == [True]


def test_ocr_runs_concurrently_up_to_limit_and_keeps_page_order(monkeypatch):
    state = {"now": 0, "max": 0}

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        state["now"] += 1
        state["max"] = max(state["max"], state["now"])
        await asyncio.sleep(0.01 * (6 - page.number))  # 앞쪽이 더 늦게 끝난다
        state["now"] -= 1
        return PageResult(page.number, f"VLM {page.number}", "vlm", 0.9)

    _patch(monkeypatch, 6, fake_vlm, concurrency=2)
    result = _extract(6)
    assert state["max"] == 2
    assert [p.text for p in result.pages] == [f"VLM {n}" for n in range(6)]


def test_all_pages_share_one_render_lock(monkeypatch):
    locks = []

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        locks.append(render_lock)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 3, fake_vlm)
    _extract(3)
    assert len(locks) == 3
    assert isinstance(locks[0], asyncio.Lock)
    assert all(lock is locks[0] for lock in locks)


def test_degenerate_and_failed_pages_fall_back_to_odl(monkeypatch):
    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        if page.number == 0:
            raise VlmDegenerateOutput("p.0 VLM 퇴화 출력(finish=length)")
        if page.number == 1:
            raise httpx.ConnectError("VLM 연결 실패")
        return PageResult(page.number, "VLM 본문", "vlm", 0.9, truncated=True)

    _patch(monkeypatch, 3, fake_vlm)
    result = _extract(3)
    assert [p.text for p in result.pages] == ["ODL 대체 0", "ODL 대체 1", "VLM 본문"]
    assert result.vlm_truncated == 2  # 퇴화로 버린 쪽 1 + 꼬리를 걷어 내고 채택한 쪽 1
    assert result.ocr_errors == 1     # 퇴화 출력은 OCR 오류로 세지 않는다
    assert result.render_errors == 0


def test_request_error_with_empty_message_keeps_exception_name(monkeypatch):
    """httpx.ReadTimeout 은 메시지가 빈 채로 오기도 한다 — 오류 기록에 예외 이름을 남겨 타임아웃·연결 실패·HTTP 오류를 가른다."""
    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        raise httpx.ReadTimeout("")

    _patch(monkeypatch, 1, fake_vlm)
    result = _extract(1)
    assert result.ocr_errors == 1
    assert "p.0 OCR(vlm): ReadTimeout" in result.errors


def test_deadline_adopts_odl_for_pages_not_done(monkeypatch):
    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        if page.number > 0:
            await asyncio.sleep(5)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 4, fake_vlm, concurrency=4)
    monkeypatch.setattr(extractor.cfg, "INGEST_EXTRACT_DEADLINE", 0.5)
    t0 = time.monotonic()
    result = _extract(4)
    assert time.monotonic() - t0 < 3
    assert result.deadline_hit
    assert [p.text for p in result.pages] == ["VLM 본문", "ODL 대체 1", "ODL 대체 2", "ODL 대체 3"]
    assert result.ocr_errors == 0


def test_vlm_page_cap_still_applies(monkeypatch):
    calls = []

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        calls.append(page.number)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 4, fake_vlm)
    monkeypatch.setattr(extractor.cfg, "VLM_MAX_PAGES_PER_DOC", 2)
    result = _extract(4)
    assert sorted(calls) == [0, 1]
    assert result.vlm_capped
    assert [p.method for p in result.pages] == ["vlm", "vlm", "opendataloader", "opendataloader"]


def test_render_failure_is_counted_apart_from_ocr_errors(monkeypatch):
    """fitz 가 쪽 이미지를 못 만들면(get_pixmap 예외 — FzErrorLimit 류) 다시 해도 같다 — VLM 요청 실패(ocr_errors)가
    아니라 render_errors 로 세고 그 쪽은 ODL 결과를 쓴다(섹션 0개 문서가 vlm_error 재시도로 헛돌지 않게)."""
    real_get_pixmap = fitz.Page.get_pixmap

    def get_pixmap(self, *args, **kwargs):
        if self.number == 1:
            raise RuntimeError("FzErrorLimit: pixmap too large")
        return real_get_pixmap(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_pixmap", get_pixmap)
    monkeypatch.setattr(extractor.cfg, "FITZ_DPI", 36)
    requests: list[httpx.Request] = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "VLM 본문"}, "finish_reason": "stop"}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        extractor.httpx, "AsyncClient", lambda *a, **kw: real_client(transport=httpx.MockTransport(handler))
    )
    _patch(monkeypatch, 3)  # 실제 _extract_with_vlm — 렌더링도 실제(쪽 1 만 실패)
    result = _extract(3)
    assert [p.text for p in result.pages] == ["VLM 본문", "ODL 대체 1", "VLM 본문"]
    assert len(requests) == 2  # 렌더링에 실패한 쪽은 요청을 보내지 않는다
    assert (result.render_errors, result.ocr_errors) == (1, 0)
    assert any("p.1" in e and "FzErrorLimit" in e for e in result.errors)


def _figure_grid(n: int) -> str:
    # [그림] 사이 <br> 는 2개씩이라 ODL 의 첫 정제로는 안 줄고, 마커를 지운 뒤에야 긴 <br> 연속이 된다
    return "[그림]<br><br>[그림]<br><br>[그림]\n" + f"ODL 대체 {n}"


def test_every_odl_fallback_strips_figure_markers(monkeypatch):
    """OCR 결과 없이 ODL 결과를 쓰는 쪽(요청 실패·퇴화 출력·데드라인·VLM 쪽수 상한)도 채택 때처럼 [그림] 을
    지우고 <br> 연속을 다시 줄인다."""
    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        if page.number == 0:
            raise httpx.ReadTimeout("VLM 응답 없음")
        if page.number == 1:
            raise VlmDegenerateOutput("p.1 VLM 퇴화 출력(finish=length)")
        if page.number == 2:
            await asyncio.sleep(5)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 5, fake_vlm, concurrency=4, odl_text=_figure_grid)
    monkeypatch.setattr(extractor.cfg, "VLM_MAX_PAGES_PER_DOC", 4)
    monkeypatch.setattr(extractor.cfg, "INGEST_EXTRACT_DEADLINE", 0.5)
    result = _extract(5)
    stripped = [f"<br>\nODL 대체 {n}" for n in range(5)]
    assert [p.text for p in result.pages] == [stripped[0], stripped[1], stripped[2], "VLM 본문", stripped[4]]
    assert (result.ocr_errors, result.vlm_truncated, result.deadline_hit, result.vlm_capped) == (1, 1, True, True)


def test_deadline_s_replaces_configured_deadline(monkeypatch):
    """섹션 0개 재추출은 첫 추출의 남은 시간을 deadline_s 로 넘긴다 — 설정값 대신 그 값으로 끊는다."""
    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        await asyncio.sleep(5)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 2, fake_vlm)
    monkeypatch.setattr(extractor.cfg, "INGEST_EXTRACT_DEADLINE", 2700)
    t0 = time.monotonic()
    result = _extract(2, deadline_s=0.3)
    assert time.monotonic() - t0 < 3
    assert result.deadline_hit
    assert [p.text for p in result.pages] == ["ODL 대체 0", "ODL 대체 1"]


def test_no_time_left_sends_no_ocr_request(monkeypatch):
    """1티어·판정만으로 데드라인을 다 썼으면 OCR 요청을 하나도 보내지 않고(렌더링도 안 한다) ODL 결과를 쓴다."""
    calls = []

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        calls.append(page.number)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 3, fake_vlm)
    result = _extract(3, deadline_s=0)
    assert calls == []
    assert result.deadline_hit
    assert [p.text for p in result.pages] == ["ODL 대체 0", "ODL 대체 1", "ODL 대체 2"]


def test_outer_cancellation_is_not_swallowed(monkeypatch):
    """바깥에서 취소하면(상위 타임아웃 등) 진행 중인 요청을 끊고 CancelledError 를 그대로 올린다 — 남는 태스크가 없다."""
    started: list[int] = []
    cancelled: list[int] = []

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        started.append(page.number)
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(page.number)
            raise
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 4, fake_vlm, concurrency=2)

    async def go() -> list:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(extractor.extract_text(None, "T_OCR", file_bytes=_blank_pdf(4)), 0.3)
        return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    t0 = time.monotonic()
    assert asyncio.run(go()) == []
    assert time.monotonic() - t0 < 3
    assert sorted(started) == [0, 1]
    assert sorted(cancelled) == [0, 1]


def test_page_concurrency_below_one_is_treated_as_one(monkeypatch):
    """VLM_PAGE_CONCURRENCY 를 0 으로 잘못 넣어도 세마포어가 막혀 데드라인까지 OCR 을 못 하는 일이 없다."""
    state = {"now": 0, "max": 0}

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        state["now"] += 1
        state["max"] = max(state["max"], state["now"])
        await asyncio.sleep(0.01)
        state["now"] -= 1
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 3, fake_vlm, concurrency=0)
    monkeypatch.setattr(extractor.cfg, "INGEST_EXTRACT_DEADLINE", 2)
    result = _extract(3)
    assert not result.deadline_hit
    assert state["max"] == 1
    assert [p.method for p in result.pages] == ["vlm"] * 3
