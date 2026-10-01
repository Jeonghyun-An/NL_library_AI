"""extract_text 2티어 라우팅 — 어느 쪽이 OCR 로 가는지 (ODL·VLM 은 목, PDF 는 fitz 로 메모리에서 만든다).

ODL 은 json header/footer 로 머리말·꼬리말을 지운 본문을 돌려주므로, 목 ODL 텍스트에는 스탬프를 넣지 않는다.
"""
import asyncio

import fitz

from services.ingestion import extractor
from services.ingestion.extractor import ExtractionResult, PageResult

STAMP = "Copyright (C) 2002 Nuri Media Co., Ltd."
BODIES = [
    ["Alpha chapter reviews the archival record of royal court", "appointments and the ranks given to envoys from abroad."],
    ["Bravo chapter compares the ritual songs with older folk", "ballads and traces how their refrains were borrowed."],
    ["Charlie chapter reads the land registers kept by county", "offices and estimates how much farmland was taxed."],
    ["Delta chapter sums up the findings and lists the open", "questions that later studies should take up again."],
    ["Echo chapter maps the trade routes that carried paper", "and ink between the capital and the southern ports."],
]


def _pdf(pages: list[list[str]], *, stamp: bool = True, image_pages: tuple[int, ...] = ()) -> bytes:
    doc = fitz.open()
    for n, lines in enumerate(pages):
        page = doc.new_page(width=420, height=595)
        if n in image_pages:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), False)
            pix.clear_with(180)
            page.insert_image(page.rect, pixmap=pix)
        for i, line in enumerate(lines):
            page.insert_text((36, 60 + 14 * i), line, fontsize=9)
        if stamp:
            page.insert_text((36, 580), STAMP, fontsize=6)
    data = doc.tobytes()
    doc.close()
    return data


def _run(monkeypatch, pdf: bytes, odl_texts: dict[int, str], **kwargs) -> tuple[list[int], ExtractionResult]:
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
    result = asyncio.run(extractor.extract_text(None, "T_ROUTE", file_bytes=pdf, **kwargs))
    return sorted(ocr_calls), result


def _body_text(n: int) -> str:
    return " ".join(BODIES[n])


def test_digital_paper_with_image_cover_keeps_cover_from_odl(monkeypatch):
    """표지 쪽 텍스트가 매 쪽 반복 스탬프뿐인 이미지 표지 → 쪽 단위로 OCR 하지 않는다."""
    pdf = _pdf([[]] + BODIES[:4], image_pages=(0,))
    odl = {0: "[그림]", **{n + 1: _body_text(n) for n in range(4)}}
    ocr, result = _run(monkeypatch, pdf, odl)
    assert ocr == []
    assert [p.page_num for p in result.pages] == [0, 1, 2, 3, 4]
    assert result.pages[0].text == ""


def test_scan_document_with_stamp_only_pages_goes_to_ocr(monkeypatch):
    """모든 쪽이 이미지 + 스탬프뿐인 스캔본(「한국문학연구」 실패 블록) → 짧은 쪽 전부 OCR."""
    pdf = _pdf([[]] * 4, image_pages=(0, 1, 2, 3))
    ocr, result = _run(monkeypatch, pdf, {n: "[그림]\n\n[그림]" for n in range(4)})
    assert ocr == [0, 1, 2, 3]
    assert [p.method for p in result.pages] == ["vlm"] * 4


def test_two_page_scan_is_below_document_rule(monkeypatch):
    """3쪽 미만은 문서 단위 판정을 하지 않는다 — 섹션 0개 강제 재추출(run_extract)이 맡는다."""
    pdf = _pdf([[]] * 2, image_pages=(0, 1))
    ocr, _ = _run(monkeypatch, pdf, {0: "[그림]", 1: "[그림]"})
    assert ocr == []


def test_genuine_short_divider_page_keeps_odl(monkeypatch):
    """디지털 문서의 진짜 짧은 간지(실제 글자 몇 개) → ODL 채택."""
    pdf = _pdf(BODIES[:4] + [["Part Two"]])
    odl = {**{n: _body_text(n) for n in range(4)}, 4: "Part Two"}
    ocr, result = _run(monkeypatch, pdf, odl)
    assert ocr == []
    assert result.pages[4].text == "Part Two"


def test_cmap_loss_suspect_page_goes_to_vlm(monkeypatch):
    """회귀: ODL 50자 이상인데 fitz(원래 길이)가 2배 넘게 길면 CMap 손상 의심 → VLM."""
    long_page = BODIES[0] + BODIES[1] + BODIES[2]
    pdf = _pdf([long_page, BODIES[3], BODIES[4]])
    odl = {0: BODIES[0][0], 1: _body_text(3), 2: _body_text(4)}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [0]


def test_page_without_text_layer_goes_to_vlm(monkeypatch):
    """회귀: fitz 0자(텍스트 층 없음) → VLM. 스탬프도 없는 이미지 쪽."""
    pdf = _pdf(BODIES[:3] + [[]], stamp=False, image_pages=(3,))
    odl = {**{n: _body_text(n) for n in range(3)}, 3: "[그림]"}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [3]


def test_empty_br_grid_is_not_counted_as_body(monkeypatch):
    """ODL 이 빈 표 격자를 <br> 로 채운 쪽 — <br> 를 본문으로 세지 않아 fitz 0자 → VLM."""
    pdf = _pdf(BODIES[:3] + [[]], stamp=False)
    odl = {**{n: _body_text(n) for n in range(3)}, 3: "|<br>|<br>|" * 30}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [3]


def test_header_footer_only_page_is_compared_without_repeated_lines(monkeypatch):
    """fitz 원래 길이는 머리말+꼬리말로 50자를 넘지만 되풀이 줄을 빼면 0 — 디지털 문서에선 ODL 채택."""
    header = "Journal of Archival Studies 3"
    pages = [[header] + BODIES[n] for n in range(4)] + [[header]]
    pdf = _pdf(pages)
    odl = {**{n: _body_text(n) for n in range(4)}, 4: ""}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == []


def test_figure_heavy_document_counts_as_scan(monkeypatch):
    """3쪽 이상에서 짧은 쪽이 절반을 넘으면 문서 단위 스캔본 → 짧은 쪽만 OCR, 본문 쪽은 ODL."""
    pdf = _pdf([["Plate one"], ["Plate two"], ["Plate three"], BODIES[0]])
    odl = {0: "Plate one", 1: "Plate two", 2: "Plate three", 3: _body_text(0)}
    ocr, result = _run(monkeypatch, pdf, odl)
    assert ocr == [0, 1, 2]
    assert result.pages[3].method == "opendataloader"


def test_force_sends_every_short_page_to_ocr(monkeypatch):
    pdf = _pdf(BODIES[:4] + [["Part Two"]])
    odl = {**{n: _body_text(n) for n in range(4)}, 4: "Part Two"}
    ocr, _ = _run(monkeypatch, pdf, odl, force_ocr_short_pages=True)
    assert ocr == [4]


def test_page_missing_from_odl_still_goes_to_ocr(monkeypatch):
    """회귀: ODL 결과에 없는 쪽은 예전처럼 판정 없이 OCR."""
    pdf = _pdf(BODIES[:3] + [["Part Two"]])
    odl = {n: _body_text(n) for n in range(3)}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [3]
