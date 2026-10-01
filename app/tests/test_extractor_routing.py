"""extract_text 2티어 라우팅 — 어느 쪽이 OCR 로 가는지 (ODL·VLM 은 목, PDF 는 fitz 로 메모리에서 만든다).

ODL 은 json header/footer 로 머리말·꼬리말을 지운 본문을 돌려주므로, 목 ODL 텍스트에는 스탬프를 넣지 않는다.
"""
import asyncio

import fitz

from services.ingestion import extractor, page_routing, paper_enricher
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


def _run(
    monkeypatch,
    pdf: bytes,
    odl_texts: dict[int, str],
    *,
    fill_ratios: dict[int, float] | None = None,
    **kwargs,
) -> tuple[list[int], ExtractionResult]:
    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None):
        res = ExtractionResult(book_id=book_id, total_pages=len(odl_texts))
        res.pages = [PageResult(n, t, "opendataloader", 0.95) for n, t in sorted(odl_texts.items())]
        res.table_fill_ratios = dict(fill_ratios or {})
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


def test_header_footer_only_page_in_digital_document_goes_to_ocr(monkeypatch):
    """회귀(비스캔 문서): fitz 원래 길이가 머리말+꼬리말로 50자를 넘으면 되풀이 줄을 빼면 0이어도
    예전처럼 'ODL 이 놓친 쪽' → OCR. 되풀이 줄 뺀 길이는 문서 단위 스캔 판정(short_flags)에만 쓴다."""
    header = "Journal of Archival Studies 3"
    pages = [[header] + BODIES[n] for n in range(4)] + [[header]]
    pdf = _pdf(pages)
    odl = {**{n: _body_text(n) for n in range(4)}, 4: ""}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [4]


def _fitz_lens(pdf: bytes) -> tuple[list[int], list[int]]:
    """extract_text 가 쪽마다 재는 (fitz 원래 길이, 되풀이 줄 뺀 길이) — 시나리오 전제를 못 박는 용도."""
    doc = fitz.open(stream=pdf, filetype="pdf")
    texts = [extractor._clean_text(p.get_text()) for p in doc]
    doc.close()
    return _lens(texts)


def _lens(texts: list[str]) -> tuple[list[int], list[int]]:
    repeated = page_routing.repeated_lines(texts, extractor.cfg.SCAN_REPEAT_LINE_RATIO)
    raw = [page_routing.body_len(t) for t in texts]
    stripped = [page_routing.body_len(page_routing.strip_lines(t, repeated)) for t in texts]
    return raw, stripped


def test_non_scan_page_with_long_raw_but_short_stripped_goes_to_ocr(monkeypatch):
    """회귀(KCI_FI003011274 류): 이미지 본문 쪽에 머리말·꼬리말만 텍스트로 남아 ODL < 50, fitz 원래 길이 60,
    되풀이 줄 뺀 길이 42 — 비스캔 문서에서 옛 코드는 'ODL 이 놓친 쪽'으로 OCR 했다. ODL 채택하면 본문이 사라진다."""
    header = "Smart Media Journal 3"
    pages = [[header] + BODIES[n] for n in range(4)] + [[header, "Resonance peak shifts upward under heavier load."]]
    pdf = _pdf(pages, stamp=False)
    raw, stripped = _fitz_lens(pdf)
    assert (raw[4], stripped[4]) == (60, 42)
    odl = {**{n: _body_text(n) for n in range(4)}, 4: "[그림]"}
    ocr, result = _run(monkeypatch, pdf, odl)
    assert ocr == [4]
    assert result.pages[4].method == "vlm"


def test_scan_decision_counts_short_pages_without_repeated_lines(monkeypatch):
    """문서 단위 스캔 판정의 '짧은 쪽'은 되풀이 줄을 뺀 fitz 길이로 센다 — 머리말이 길어 원래 길이가 50자를
    넘는 쪽(0~2쪽)도 짧은 쪽이라 스캔본이 되고, 원래 길이 50자 미만의 간지(3·4쪽)까지 OCR 로 간다."""
    headers = ["Smart Media Journal Vol 3 No 2 pp 100", "Korea Society of Smart Media"]
    pages = [headers] * 3 + [["Part Two"], ["Part Three"]]
    pdf = _pdf(pages, stamp=False, image_pages=(0, 1, 2))
    raw, stripped = _fitz_lens(pdf)
    assert all(r >= 50 for r in raw[:3]) and all(s < 50 for s in stripped)
    odl = {0: "[그림]", 1: "[그림]", 2: "[그림]", 3: "Part Two", 4: "Part Three"}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [0, 1, 2, 3, 4]


def test_low_table_fill_ratio_goes_to_ocr_even_with_long_text(monkeypatch):
    """회귀: ODL 글자 수가 충분해도 표 셀 충전율 < 0.30 이면 OCR (경계 0.30 은 채택)."""
    pdf = _pdf(BODIES[:4])
    odl = {n: _body_text(n) for n in range(4)}
    ocr, result = _run(monkeypatch, pdf, odl, fill_ratios={1: 0.29, 2: 0.30, 3: 0.95})
    assert ocr == [1]
    assert [p.method for p in result.pages] == ["opendataloader", "vlm", "opendataloader", "opendataloader"]


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


# ── 결정표 전수 열거 ───────────────────────────────────────────────────────────
# 쪽 판정의 입력(ODL 본문 길이·fitz 원래 길이·되풀이 줄 뺀 길이·표 셀 충전율·문서 단위 스캔본 여부·강제)을
# 모든 조합으로 돌려, 비스캔·비강제 문서의 모든 칸이 옛 규칙과 같고 스캔본·강제일 때는 짧은 쪽만 OCR 가
# 더해지는지 본다. PDF 를 만들면 수천 칸을 못 돌므로 가짜 fitz 문서를 쓴다(ODL·VLM 도 목).

MIN_CHARS = 50


class _FakePage:
    def __init__(self, number: int, text: str = "", error: Exception | None = None):
        self.number = number
        self._text = text
        self._error = error

    def get_text(self, *_a, **_kw) -> str:
        if self._error is not None:
            raise self._error
        return self._text


class _FakeDoc:
    def __init__(self, pages: list[_FakePage]):
        self._pages = pages

    def __len__(self) -> int:
        return len(self._pages)

    def __iter__(self):
        return iter(self._pages)

    def __getitem__(self, i: int) -> _FakePage:
        return self._pages[i]

    def load_page(self, i: int) -> _FakePage:
        return self._pages[i]

    def close(self) -> None:
        pass


class _NullClient:
    """httpx.AsyncClient 대용 — 목 VLM 은 클라이언트를 안 쓰고, 진짜는 만들 때마다 TLS 컨텍스트를 읽어 느리다."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


def _patch_fakes(monkeypatch) -> dict:
    """extract_text 의 fitz 문서·ODL·VLM·httpx 를 목으로 바꾸고, 호출마다 채우는 상태 dict 를 돌려준다."""
    state: dict = {"pages": [], "odl": {}, "fill": {}, "ocr": []}

    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None):
        res = ExtractionResult(book_id=book_id, total_pages=len(state["odl"]))
        res.pages = [PageResult(n, t, "opendataloader", 0.95) for n, t in sorted(state["odl"].items())]
        res.table_fill_ratios = dict(state["fill"])
        return res

    async def fake_vlm(page, client, *, prompt_type="ocr", **_kw):
        state["ocr"].append(page.number)
        return PageResult(page.number, f"VLM 본문 {page.number}", "vlm", 0.9)

    monkeypatch.setattr(extractor, "extract_text_opendataloader", fake_odl)
    monkeypatch.setattr(extractor, "_extract_with_vlm", fake_vlm)
    monkeypatch.setattr(extractor.cfg, "OCR_ENGINE", "vlm")
    monkeypatch.setattr(extractor.fitz, "open", lambda *_a, **_kw: _FakeDoc(state["pages"]))
    monkeypatch.setattr(extractor.httpx, "AsyncClient", _NullClient)
    return state


def _legacy_sends_to_ocr(odl_len: int | None, raw: int, fill: float | None) -> bool:
    """이 작업 전 extract_text 의 쪽 분기를 그대로 옮긴 옛 판정(d85df93·0df3001·8b1511a 이후) — OCR 로 가는가."""
    if odl_len is None:  # ODL 누락
        return True
    if fill is not None and fill < 0.30:  # 표 셀 충전율 낮음
        return True
    if odl_len >= MIN_CHARS:  # CMap 손상 의심: fitz 원래 길이가 ODL 의 2배를 넘으면
        return raw > odl_len * 2
    return not 0 < raw < MIN_CHARS  # 원래 짧은 쪽(0 < fitz < 50)만 ODL 채택, fitz 0자·50자 이상은 OCR


def _expected_ocr(odl_len: int | None, raw: int, fill: float | None, *, scan: bool, force: bool) -> bool:
    if _legacy_sends_to_ocr(odl_len, raw, fill):
        return True
    # 옛 규칙이 ODL 을 채택하던 칸 — 짧은 쪽(ODL < 50)만 스캔본 문서·강제에서 OCR 로 바뀐다
    return odl_len < MIN_CHARS and (scan or force)


def _chunks(n: int, ch: str, width: int = 30) -> list[str]:
    """ch 를 n 글자 모은 줄들 — 한 줄이 40자 이하라야 되풀이 줄 후보가 된다."""
    return [ch * min(width, n - i) for i in range(0, n, width)]


def _build_case(
    state: dict, odl_len: int | None, raw: int, stripped: int, fill: float | None, *, scan: bool
) -> None:
    """쪽 0 이 검사 대상(ODL 길이 odl_len — None 이면 ODL 누락, fitz 원래 길이 raw, 되풀이 줄 뺀 길이 stripped).

    쪽 1~4 는 채움 쪽이다: 머리말(문서 전체에 되풀이되는 줄)을 만들고, scan 이면 짧은 쪽이 과반이 되게
    텍스트 층에는 되풀이 줄(머리말 + 쪽 0 에는 없는 60자 스탬프)뿐·ODL 은 그림뿐인 쪽으로 — fitz 원래
    길이는 50자를 넘어도 되풀이 줄을 빼면 0이라 짧은 쪽이다 — 아니면 본문이 충분한 쪽으로 채운다.
    """
    header = _chunks(raw - stripped, "나")
    stamp = _chunks(60, "라")
    pages = [_FakePage(0, "\n".join(_chunks(stripped, "가") + header))]
    odl: dict[int, str] = {}
    if odl_len is not None:
        odl[0] = "다" * odl_len if odl_len else "[그림]"
    for k in range(1, 5):
        if scan:
            pages.append(_FakePage(k, "\n".join(stamp + header)))
            odl[k] = "[그림]"
        else:
            body = chr(0xB300 + k)
            pages.append(_FakePage(k, "\n".join(_chunks(60, body) + header)))
            odl[k] = body * 60
    state["pages"] = pages
    state["odl"] = odl
    state["fill"] = {} if fill is None else {0: fill}


def test_decision_table_matches_legacy_rule_outside_scan_and_force(monkeypatch):
    """비스캔·비강제 문서의 모든 칸은 옛 규칙과 같고, 스캔본·강제 문서는 ODL < 50 인 짧은 쪽만 OCR 가 더해진다."""
    state = _patch_fakes(monkeypatch)
    odl_lens = [None, 0, 30, 49, 50, 60, 130]
    raws = [0, 1, 30, 49, 50, 51, 60, 100, 101, 120, 121, 260, 261]
    fills = [None, 0.29, 0.30]
    harness_errors: list[str] = []
    mismatches: list[str] = []
    checked = 0

    async def sweep() -> None:
        nonlocal checked
        for odl_len in odl_lens:
            for raw in raws:
                for stripped in sorted({0, min(raw, 42), raw}):
                    for fill in fills:
                        for scan in (False, True):
                            _build_case(state, odl_len, raw, stripped, fill, scan=scan)
                            # 시나리오 전제 확인 — 쪽 0 의 길이와 문서 단위 스캔본 여부가 의도대로 만들어졌는가
                            lens = _lens([extractor._clean_text(p.get_text()) for p in state["pages"]])
                            flags = [
                                page_routing.body_len(state["odl"].get(n, "")) < MIN_CHARS and lens[1][n] < MIN_CHARS
                                for n in range(5)
                            ]
                            is_scan = page_routing.is_scan_document(
                                flags, min_pages=extractor.cfg.SCAN_MIN_PAGES, ratio=extractor.cfg.SCAN_SHORT_PAGE_RATIO
                            )
                            if (lens[0][0], lens[1][0], is_scan) != (raw, stripped, scan):
                                harness_errors.append(
                                    f"odl={odl_len} raw={raw} stripped={stripped} scan={scan}: "
                                    f"만들어진 값 raw={lens[0][0]} stripped={lens[1][0]} scan={is_scan}"
                                )
                                continue
                            for force in (False, True):
                                state["ocr"] = []
                                await extractor.extract_text(
                                    None, "T_TABLE", file_bytes=b"x", force_ocr_short_pages=force
                                )
                                got = 0 in state["ocr"]
                                want = _expected_ocr(odl_len, raw, fill, scan=scan, force=force)
                                checked += 1
                                if got != want:
                                    mismatches.append(
                                        f"odl={odl_len} raw={raw} stripped={stripped} fill={fill} "
                                        f"scan={scan} force={force}: OCR {got}, 기대 {want}"
                                    )

    asyncio.run(sweep())
    assert not harness_errors, "\n".join(harness_errors[:10])
    assert checked > 2000
    assert not mismatches, f"{len(mismatches)}/{checked} 칸이 다르다:\n" + "\n".join(mismatches[:15])


# ── <br> 연속 처리 ─────────────────────────────────────────────────────────────

TABLE_A = (
    "| 구분 | 설명 |\n| --- | --- |\n"
    "| 가 | 첫째 문단<br><br><br>둘째 문단 |\n"
    "| 나 | 값<br><br><br><br><br>비고 |\n"
    "| 다 | 끝 |\n"
)
TABLE_B = "| 항목 | 값 |\n| --- | --- |\n| 라 | 하나<br><br><br>둘 |\n| 마 | 셋 |\n"


def test_clean_text_keeps_markdown_table_rows_whole():
    """<br> 연속을 줄바꿈으로 바꾸면 표 칸 안 문단 사이 <br><br><br> 가 행을 쪼개 paper_enricher 표 추출이 줄어든다
    (KCI_FI002990049 15→13개). <br> 하나로 줄이면 표 행 수도, 표 추출 개수도 그대로다."""
    raw = "서론 문단이다.\n\n" + TABLE_A + "\n본문 문단이다.\n\n" + TABLE_B
    cleaned = extractor._clean_text(raw)
    rows = [ln for ln in cleaned.split("\n") if ln.startswith("|") and ln.endswith("|")]
    assert len(rows) == 9  # 표 A 5행 + 표 B 4행이 온전한 한 줄씩 — 줄바꿈이 끼어 행이 쪼개지지 않는다
    assert "| 가 | 첫째 문단<br>둘째 문단 |" in rows
    assert "| 나 | 값<br>비고 |" in rows
    assert len(paper_enricher._extract_tables(raw)) == 2
    assert len(paper_enricher._extract_tables(cleaned)) == 2


def test_figure_br_grid_is_shortened_again_after_figure_markers_are_removed():
    """`[그림]<br><br>[그림]` 반복 격자는 [그림] 을 지우면 <br> 긴 연속이 된다 — 채택 때 <br> 하나로 줄인다."""
    row = "| " + "[그림]<br><br>" * 40 + "[그림] |"
    assert extractor._clean_text(row).count("<br>") == 80  # [그림] 사이 <br> 은 2개씩이라 첫 정제로는 안 줄어든다
    stripped = extractor._strip_figure_markers(row)
    assert stripped.replace(" ", "") == "|<br>|"  # 한 줄 그대로, <br> 하나만 남는다


def test_page_with_failing_get_text_does_not_break_the_whole_extraction(monkeypatch):
    """회귀: 쪽 하나의 fitz get_text 가 실패('too many nested graphics states')해도 문서 추출은 계속된다 —
    그 쪽은 텍스트 층이 없는 쪽으로 보고 errors 에 남긴다."""
    state = _patch_fakes(monkeypatch)
    boom = RuntimeError("too many nested graphics states")

    def doc_with_bad_page(bad_odl: str) -> None:
        state["pages"] = [
            _FakePage(n, "\n".join(BODIES[n]), error=boom if n == 2 else None) for n in range(5)
        ]
        state["odl"] = {n: _body_text(n) for n in range(5)}
        state["odl"][2] = bad_odl
        state["ocr"] = []

    # ODL 도 짧은 쪽 → 텍스트 층을 못 읽었으니 OCR
    doc_with_bad_page("[그림]")
    result = asyncio.run(extractor.extract_text(None, "T_ERR", file_bytes=b"x"))
    assert state["ocr"] == [2]
    assert [p.page_num for p in result.pages] == [0, 1, 2, 3, 4]
    assert any("p.2" in e and "too many nested graphics states" in e for e in result.errors)

    # ODL 본문이 충분한 쪽 → 그대로 채택, 오류만 남는다
    doc_with_bad_page(_body_text(2))
    result = asyncio.run(extractor.extract_text(None, "T_ERR", file_bytes=b"x"))
    assert state["ocr"] == []
    assert [p.method for p in result.pages] == ["opendataloader"] * 5
    assert any("p.2" in e and "too many nested graphics states" in e for e in result.errors)
