"""run_extract — 섹션 0개를 추출 성공으로 넘기지 않는다: 강제 OCR 재추출 → no_text / vlm_error.

강제 OCR(force_ocr_short_pages)이 바꾸는 것은 '원래 짧은 쪽'으로 ODL 결과를 채택한 쪽(short_kept)뿐이라, 그런 쪽이
없으면 다시 추출하지 않고 바로 no_text 다. 다시 추출할 때는 첫 추출이 남긴 시간만 데드라인으로 넘겨 두 추출을 합쳐도
INGEST_EXTRACT_DEADLINE 안에 든다(stale 판정 3600초 아래).
"""
import asyncio
from unittest.mock import MagicMock

import fitz
import pytest

from services.ingestion import extractor, stages
from services.ingestion.extractor import ExtractionResult, PageResult
from services.ingestion.stages import StageContext, StageError


def _extraction(
    text: str,
    *,
    ocr_errors: int = 0,
    deadline_hit: bool = False,
    vlm_truncated: int = 0,
    short_kept: int = 0,
    render_errors: int = 0,
):
    res = ExtractionResult(book_id="KCI_T", total_pages=3)
    res.pages = [PageResult(n, text, "opendataloader", 0.95) for n in range(3)]
    res.ocr_errors = ocr_errors
    res.deadline_hit = deadline_hit
    res.vlm_truncated = vlm_truncated
    res.short_kept = short_kept
    res.render_errors = render_errors
    return res


@pytest.fixture
def run_extract_with(monkeypatch):
    """extract_text 가 차례로 돌려줄 결과를 받아 run_extract 를 돌린다 → (meta, 호출 기록, 저장된 추출).

    호출 기록은 (force_ocr_short_pages, deadline_s) 다. first_delay 초만큼 첫 추출이 걸린 것으로 한다.
    """
    calls: list[tuple[bool, float | None]] = []
    saved: list[ExtractionResult] = []

    def _run(*results: ExtractionResult, first_delay: float = 0.0) -> dict:
        queue = list(results)

        async def fake_extract_text(
            file_path, book_id, *, file_bytes=None, force_ocr_short_pages=False, deadline_s=None
        ):
            calls.append((force_ocr_short_pages, deadline_s))
            if len(calls) == 1 and first_delay:
                await asyncio.sleep(first_delay)
            return queue.pop(0)

        def fake_split(pages):
            if not any(p.text for p in pages):
                return []
            return [{"section_idx": 0, "text": "본문", "page_start": 0, "page_end": 2, "token_count": 10}]

        monkeypatch.setattr(extractor, "extract_text", fake_extract_text)
        monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())
        monkeypatch.setattr(stages, "split_into_sections", fake_split)
        monkeypatch.setattr(stages, "_ensure_book_and_doc_type", lambda ctx, path: "paper")
        monkeypatch.setattr(stages, "SyncSessionLocal", lambda: MagicMock())
        monkeypatch.setattr(stages, "save_extraction_artifact", lambda book_id, ext, client: saved.append(ext))
        return stages.run_extract(StageContext(book_id="KCI_T", file_path="C:/nowhere/KCI_T.pdf"))

    return _run, calls, saved


def test_sections_on_first_pass_do_not_reextract(run_extract_with):
    run, calls, _ = run_extract_with
    meta = run(_extraction("본문"))
    assert calls == [(False, None)]
    assert meta["sections"] == 1
    assert (
        meta["forced_ocr"], meta["vlm_truncated"], meta["extract_deadline_hit"], meta["ocr_errors"], meta["render_errors"]
    ) == (False, 0, False, 0, 0)


def test_zero_sections_reextracts_with_forced_ocr(run_extract_with):
    run, calls, saved = run_extract_with
    second = _extraction("VLM 본문", vlm_truncated=1)
    meta = run(_extraction("", short_kept=1), second)
    assert [force for force, _ in calls] == [False, True]
    assert meta["forced_ocr"] is True
    assert meta["vlm_truncated"] == 1
    assert saved == [second]


def test_zero_sections_after_forced_ocr_is_no_text(run_extract_with):
    run, calls, saved = run_extract_with
    with pytest.raises(StageError) as exc:
        run(_extraction("", short_kept=2), _extraction(""))
    assert exc.value.error_group == "no_text"
    assert [force for force, _ in calls] == [False, True]
    assert saved == []


@pytest.mark.parametrize("second", [_extraction("", ocr_errors=2), _extraction("", deadline_hit=True)])
def test_zero_sections_after_forced_ocr_with_ocr_trouble_is_vlm_error(run_extract_with, second):
    run, _, saved = run_extract_with
    with pytest.raises(StageError) as exc:
        run(_extraction("", short_kept=1), second)
    assert exc.value.error_group == "vlm_error"
    assert saved == []


@pytest.mark.parametrize(
    "first",
    [_extraction("", ocr_errors=3, short_kept=1), _extraction("", deadline_hit=True, short_kept=1)],
)
def test_ocr_trouble_on_first_pass_skips_forced_ocr(run_extract_with, first):
    run, calls, _ = run_extract_with
    with pytest.raises(StageError) as exc:
        run(first)
    assert exc.value.error_group == "vlm_error"
    assert calls == [(False, None)]


def test_zero_sections_without_kept_short_pages_is_no_text_at_once(run_extract_with):
    """짧은 쪽을 이미 다 OCR 했으면(스캔본) 강제 OCR 로 바뀔 쪽이 없다 — 다시 추출하지 않고 바로 no_text."""
    run, calls, saved = run_extract_with
    with pytest.raises(StageError) as exc:
        run(_extraction("", vlm_truncated=4))
    assert exc.value.error_group == "no_text"
    assert calls == [(False, None)]
    assert saved == []


@pytest.mark.parametrize(
    "results",
    [
        (_extraction("", render_errors=2),),
        (_extraction("", short_kept=1), _extraction("", render_errors=3)),
    ],
)
def test_render_errors_alone_end_as_no_text(run_extract_with, results):
    """렌더링 실패는 다시 해도 같다 — 섹션 0개의 사유가 그것뿐이면 vlm_error(재시도)가 아니라 no_text."""
    run, _, _ = run_extract_with
    with pytest.raises(StageError) as exc:
        run(*results)
    assert exc.value.error_group == "no_text"


def test_forced_reextract_gets_time_left_by_first_pass(run_extract_with, monkeypatch):
    """두 추출을 합쳐 INGEST_EXTRACT_DEADLINE 안에 들게 — 강제 재추출의 데드라인은 설정값 − 첫 추출 경과."""
    run, calls, _ = run_extract_with
    monkeypatch.setattr(stages.cfg, "INGEST_EXTRACT_DEADLINE", 100)
    run(_extraction("", short_kept=1), _extraction("VLM 본문"), first_delay=0.2)
    (_, first_deadline), (_, forced_deadline) = calls
    assert first_deadline is None  # 첫 추출은 설정값 그대로
    assert 99.0 < forced_deadline <= 99.8


def test_forced_reextract_deadline_has_a_floor(run_extract_with, monkeypatch):
    """첫 추출이 설정값을 거의(또는 다) 썼어도 강제 재추출에 하한(60초)은 준다."""
    run, calls, _ = run_extract_with
    monkeypatch.setattr(stages.cfg, "INGEST_EXTRACT_DEADLINE", 0.1)
    run(_extraction("", short_kept=1), _extraction("VLM 본문"), first_delay=0.2)
    assert calls[1] == (True, stages.FORCED_OCR_MIN_DEADLINE_SECONDS)
    assert stages.FORCED_OCR_MIN_DEADLINE_SECONDS == 60


# ── extract_text 의 short_kept ────────────────────────────────────────────────

BODIES = [
    ["Alpha chapter reviews the archival record of royal court", "appointments and the ranks given to envoys from abroad."],
    ["Bravo chapter compares the ritual songs with older folk", "ballads and traces how their refrains were borrowed."],
    ["Charlie chapter reads the land registers kept by county", "offices and estimates how much farmland was taxed."],
]


def _pdf(pages: list[list[str]]) -> bytes:
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page(width=420, height=595)
        for i, line in enumerate(lines):
            page.insert_text((36, 60 + 14 * i), line, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def _route(monkeypatch, pdf: bytes, odl_texts: dict[int, str], **kwargs) -> tuple[list[int], ExtractionResult]:
    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None):
        res = ExtractionResult(book_id=book_id, total_pages=len(odl_texts))
        res.pages = [PageResult(n, t, "opendataloader", 0.95) for n, t in sorted(odl_texts.items())]
        return res

    ocr_calls: list[int] = []

    async def fake_vlm(page, client, *, prompt_type="ocr", **_kw):
        ocr_calls.append(page.number)
        return PageResult(page.number, f"VLM 본문 {page.number}", "vlm", 0.9)

    monkeypatch.setattr(extractor, "extract_text_opendataloader", fake_odl)
    monkeypatch.setattr(extractor, "_extract_with_vlm", fake_vlm)
    monkeypatch.setattr(extractor.cfg, "OCR_ENGINE", "vlm")
    result = asyncio.run(extractor.extract_text(None, "T_KEPT", file_bytes=pdf, **kwargs))
    return sorted(ocr_calls), result


def test_short_kept_counts_exactly_the_pages_forced_ocr_changes(monkeypatch):
    """디지털 문서의 간지 2쪽(0 < fitz < 50)은 '원래 짧은 쪽'으로 ODL 채택 → short_kept 2. 강제 OCR 은 그 2쪽만 더 보낸다."""
    pdf = _pdf(BODIES + [["Part Two"], ["Part Three"]])
    odl = {**{n: " ".join(BODIES[n]) for n in range(3)}, 3: "Part Two", 4: "Part Three"}
    ocr, result = _route(monkeypatch, pdf, odl)
    assert (ocr, result.short_kept) == ([], 2)
    forced_ocr, forced = _route(monkeypatch, pdf, odl, force_ocr_short_pages=True)
    assert (forced_ocr, forced.short_kept) == ([3, 4], 0)


def test_scan_document_keeps_no_short_page(monkeypatch):
    """스캔본(텍스트 층 없음)은 짧은 쪽을 모두 OCR 로 보내 short_kept 0 — 강제 재추출이 바꿀 쪽이 없다."""
    pdf = _pdf([[]] * 4)
    ocr, result = _route(monkeypatch, pdf, {n: "[그림]" for n in range(4)})
    assert (ocr, result.short_kept) == ([0, 1, 2, 3], 0)
