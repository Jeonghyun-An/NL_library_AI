"""run_extract — 섹션 0개를 추출 성공으로 넘기지 않는다: 강제 OCR 재추출 → no_text / vlm_error.

강제 OCR(force_ocr_short_pages)이 바꾸는 것은 '원래 짧은 쪽'으로 ODL 결과를 채택한 쪽(short_kept)뿐이라, 그런 쪽이
없으면 다시 추출하지 않고 바로 no_text 다. 다시 추출할 때는 첫 추출이 남긴 시간만 데드라인으로 넘겨 두 추출을 합쳐도
INGEST_EXTRACT_DEADLINE 안에 든다(stale 판정 3600초 아래).
"""
import asyncio
from types import SimpleNamespace
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
    odl_fallback: str | None = None,
    odl_seconds: float = 0.0,
    ocr_rejected: int = 0,
    errors: list[str] | None = None,
):
    res = ExtractionResult(book_id="KCI_T", total_pages=3)
    res.pages = [PageResult(n, text, "opendataloader", 0.95) for n in range(3)]
    res.ocr_errors = ocr_errors
    res.deadline_hit = deadline_hit
    res.vlm_truncated = vlm_truncated
    res.short_kept = short_kept
    res.render_errors = render_errors
    res.odl_fallback = odl_fallback
    res.odl_seconds = odl_seconds
    res.ocr_rejected = ocr_rejected
    res.errors = list(errors or [])
    return res


REJECTED = "p.0 OCR(vlm): HTTPStatusError: Client error '400 Bad Request'"


def _empty_extraction(**kwargs) -> ExtractionResult:
    """쪽이 하나도 남지 않은 추출 — ODL 이 아무 쪽도 내지 않았고 OCR 결과도 없다."""
    res = _extraction("", **kwargs)
    res.pages = []
    return res


@pytest.fixture
def run_extract_with(monkeypatch):
    """extract_text 가 차례로 돌려줄 결과를 받아 run_extract 를 돌린다 → (meta, 호출 기록, 저장된 추출).

    호출 기록은 (force_ocr_short_pages, deadline_s) 다. first_delay 초만큼 첫 추출이 걸린 것으로 한다 — stages 의
    시계를 가짜로 바꿔 그만큼만 흐르게 한다(Windows monotonic 은 15.6ms 단위라 실제 sleep 으로 재면 흔들린다).
    _run.meta_budgets 에 카탈로그 row 보장(PDF 메타 추출)에 넘긴 time_budget 을 쌓는다.
    """
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(stages, "time", SimpleNamespace(monotonic=lambda: clock.now))
    calls: list[tuple[bool, float | None]] = []
    saved: list[ExtractionResult] = []
    meta_budgets: list[float | None] = []

    def fake_ensure_book(ctx, path, *, time_budget=None):
        meta_budgets.append(time_budget)
        return "paper"

    def _run(*results: ExtractionResult, first_delay: float = 0.0) -> dict:
        queue = list(results)

        async def fake_extract_text(
            file_path, book_id, *, file_bytes=None, force_ocr_short_pages=False, deadline_s=None
        ):
            calls.append((force_ocr_short_pages, deadline_s))
            if len(calls) == 1:
                clock.now += first_delay
            return queue.pop(0)

        def fake_split(pages):
            if not any(p.text for p in pages):
                return []
            return [{"section_idx": 0, "text": "본문", "page_start": 0, "page_end": 2, "token_count": 10}]

        monkeypatch.setattr(extractor, "extract_text", fake_extract_text)
        monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())
        monkeypatch.setattr(stages, "split_into_sections", fake_split)
        monkeypatch.setattr(stages, "_ensure_book_and_doc_type", fake_ensure_book)
        monkeypatch.setattr(stages, "SyncSessionLocal", lambda: MagicMock())
        monkeypatch.setattr(stages, "save_extraction_artifact", lambda book_id, ext, client: saved.append(ext))
        return stages.run_extract(StageContext(book_id="KCI_T", file_path="C:/nowhere/KCI_T.pdf"))

    _run.meta_budgets = meta_budgets
    return _run, calls, saved


def test_sections_on_first_pass_do_not_reextract(run_extract_with):
    run, calls, _ = run_extract_with
    meta = run(_extraction("본문"))
    assert calls == [(False, None)]
    assert meta["sections"] == 1
    assert (
        meta["forced_ocr"], meta["vlm_truncated"], meta["extract_deadline_hit"], meta["ocr_errors"], meta["render_errors"]
    ) == (False, 0, False, 0, 0)


def test_meta_reports_odl_fallback_and_time(run_extract_with):
    # 카나리·본 잡에서 ODL 폴백을 탄 문서와 변환 시간을 아이템 meta 로 센다
    run, _, _ = run_extract_with
    meta = run(_extraction("본문", odl_fallback="resaved", odl_seconds=12.345))
    assert (meta["odl_fallback"], meta["odl_seconds"]) == ("resaved", 12.3)
    meta = run(_extraction("본문"))
    assert (meta["odl_fallback"], meta["odl_seconds"]) == (None, 0.0)


def test_meta_odl_fields_come_from_the_forced_reextract(run_extract_with):
    run, _, _ = run_extract_with
    meta = run(_extraction("", short_kept=1, odl_fallback="fitz", odl_seconds=40.0),
               _extraction("VLM 본문", odl_seconds=7.06))
    assert (meta["odl_fallback"], meta["odl_seconds"]) == (None, 7.1)


def test_meta_reports_rejected_ocr_requests_next_to_ocr_errors(run_extract_with):
    run, _, _ = run_extract_with
    meta = run(_extraction("본문", ocr_errors=1, ocr_rejected=3))
    assert (meta["ocr_errors"], meta["ocr_rejected"]) == (1, 3)


@pytest.mark.parametrize("results, cause", [
    ((_extraction("", ocr_rejected=4, errors=[REJECTED]),), "VLM 거절 4쪽"),
    ((_extraction("", short_kept=1), _extraction("", ocr_rejected=2, errors=[REJECTED])), "VLM 거절 2쪽"),
], ids=["first_pass", "forced_reextract"])
def test_rejected_ocr_alone_ends_as_no_text(run_extract_with, results, cause):
    """VLM 이 거절한 쪽뿐이면(다시 보내도 같다) 섹션 0개는 vlm_error(재시도)가 아니라 no_text 규칙을 따른다. 실패한
    아이템은 meta 가 없어 사유가 last_error 에만 남는다 — 거절 수와 오류를 싣는다(VLM·DPI·max-model-len 을 바꾼 뒤
    last_error 에 '거절' 이 든 no_text 를 다시 보낸다)."""
    run, _, _ = run_extract_with
    with pytest.raises(StageError) as exc:
        run(*results)
    assert exc.value.error_group == "no_text"
    assert f" · {cause}: " in str(exc.value) and REJECTED in str(exc.value) and "거절" in str(exc.value)


def test_no_text_message_carries_rejection_and_render_failure_together(run_extract_with):
    run, _, _ = run_extract_with
    with pytest.raises(StageError) as exc:
        run(_extraction("", ocr_rejected=1, render_errors=2, errors=["e1", "e2", "e3", "e4"]))
    assert str(exc.value) == (
        "섹션 0개 — 본문 없음(3쪽, 강제 OCR 로 바뀔 쪽 없음) · VLM 거절 1쪽·렌더링 실패 2쪽: ['e1', 'e2', 'e3']"
    )


@pytest.mark.parametrize("kwargs, group", [
    ({"ocr_rejected": 3, "errors": [REJECTED]}, "no_text"),           # 거절뿐 — 다시 해도 같다
    ({"render_errors": 2}, "no_text"),
    ({"ocr_rejected": 3, "ocr_errors": 1}, "extract_empty"),          # 다시 하면 달라질 수 있는 실패가 섞였다
    ({"ocr_rejected": 3, "deadline_hit": True}, "extract_empty"),
    ({}, "extract_empty"),
], ids=["rejected", "render", "with_ocr_error", "with_deadline", "nothing"])
def test_no_pages_at_all_with_only_deterministic_ocr_failures_is_no_text(run_extract_with, kwargs, group):
    run, calls, _ = run_extract_with
    with pytest.raises(StageError) as exc:
        run(_empty_extraction(**kwargs))
    assert exc.value.error_group == group
    assert calls == [(False, None)]
    if group == "no_text":
        assert str(exc.value).startswith("텍스트 추출 실패 — 본문 없음(3쪽) · ")


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
    assert str(exc.value) == "섹션 0개 — 본문 없음(3쪽, 강제 OCR 로 바뀔 쪽 없음)"   # 거절·렌더링 실패가 없으면 사유를 붙이지 않는다
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
    assert f" · 렌더링 실패 {results[-1].render_errors}쪽: " in str(exc.value)


def test_forced_reextract_gets_time_left_by_first_pass(run_extract_with, monkeypatch):
    """두 추출을 합쳐 INGEST_EXTRACT_DEADLINE 안에 들게 — 강제 재추출의 데드라인은 설정값 − 첫 추출 경과."""
    run, calls, _ = run_extract_with
    monkeypatch.setattr(stages.cfg, "INGEST_EXTRACT_DEADLINE", 100)
    run(_extraction("", short_kept=1), _extraction("VLM 본문"), first_delay=0.2)
    (_, first_deadline), (_, forced_deadline) = calls
    assert first_deadline is None  # 첫 추출은 설정값 그대로
    assert forced_deadline == pytest.approx(100 - 0.2)


# ── PDF 메타 추출(카탈로그 row 가 없을 때) — ODL 을 한 번 더 돌리므로 추출 데드라인 안에서 ────────────


def test_meta_extraction_gets_the_time_left_by_the_extract_deadline(run_extract_with, monkeypatch):
    run, _, _ = run_extract_with
    monkeypatch.setattr(stages.cfg, "INGEST_EXTRACT_DEADLINE", 100)
    run(_extraction("본문"), first_delay=0.2)
    (budget,) = run.meta_budgets
    assert budget == pytest.approx(100 - 0.2)


def test_meta_extraction_budget_has_the_odl_minimum_as_floor(run_extract_with, monkeypatch):
    run, _, _ = run_extract_with
    monkeypatch.setattr(stages.cfg, "INGEST_EXTRACT_DEADLINE", 0.1)
    run(_extraction("본문"), first_delay=0.2)
    assert run.meta_budgets == [extractor._ODL_MIN_ATTEMPT_SECONDS]


def test_ensure_book_passes_the_budget_to_pdf_meta_extraction(monkeypatch):
    from services.ingestion import pdf_meta_extractor

    seen = []

    async def fake_meta(file_path, *, time_budget=None):
        seen.append((file_path, time_budget))
        return {"title": "자동 제목"}

    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None   # 카탈로그 row 없음
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)
    monkeypatch.setattr(pdf_meta_extractor, "extract_pdf_metadata", fake_meta)

    doc_type = stages._ensure_book_and_doc_type(
        StageContext(book_id="KCI_T", params={"doc_type": "paper"}), "C:/nowhere/KCI_T.pdf", time_budget=42.0)

    assert doc_type == "paper"
    assert seen == [("C:/nowhere/KCI_T.pdf", 42.0)]


@pytest.mark.parametrize("kwargs, budget", [({"time_budget": 7.5}, 7.5), ({}, None)], ids=["budget", "other_callers"])
def test_pdf_meta_extraction_bounds_its_odl_conversion(monkeypatch, kwargs, budget):
    from services.ingestion import pdf_meta_extractor

    seen = []

    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None, time_budget=None):
        seen.append((max_pages, time_budget))
        return ExtractionResult(book_id=book_id, total_pages=0)                 # 본문 없음 → LLM 없이 {}

    monkeypatch.setattr(extractor, "extract_text_opendataloader", fake_odl)

    assert asyncio.run(pdf_meta_extractor.extract_pdf_metadata("C:/nowhere/x.pdf", **kwargs)) == {}
    assert seen == [(2, budget)]


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
    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None, time_budget=None):
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
