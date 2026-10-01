"""page_routing 순수 함수 단위 테스트 — 추출 2티어 라우팅의 짧은 쪽 판정·VLM 반복 꼬리."""
from services.ingestion.page_routing import (
    body_len,
    collapse_br_runs,
    is_scan_document,
    repeated_lines,
    short_page_needs_ocr,
    strip_lines,
    trim_repetition,
)

STAMP = "Copyright (C) 2002 Nuri Media Co., Ltd."


class TestBodyLen:
    def test_br_tags_do_not_count(self):
        assert body_len("|<br>|<br/>|<BR >|" * 20) == 0

    def test_figure_markers_and_table_structure_do_not_count(self):
        assert body_len("[그림]\n| --- | :-: |\n|  |  |") == 0

    def test_cell_text_counts(self):
        assert body_len("| 본문 | 12.5 |<br>") == len("본문12.5")

    def test_empty(self):
        assert body_len("") == 0


class TestCollapseBrRuns:
    def test_three_or_more_become_one_br(self):
        assert collapse_br_runs("가<br><br><br>나") == "가<br>나"
        assert collapse_br_runs("가" + "<br> " * 500 + "나") == "가<br>나"
        assert collapse_br_runs("가<br/><BR ><br>\t<br>나") == "가<br>나"

    def test_one_or_two_are_kept(self):
        assert collapse_br_runs("셀<br>안<br><br>줄") == "셀<br>안<br><br>줄"

    def test_never_adds_a_newline(self):
        # 줄바꿈이 들어가면 마크다운 표 행이 쪼개진다 — 표 칸 안 문단 사이의 <br> 연속도 <br> 로만 줄인다
        row = "| 가 | 첫째 문단<br><br><br>둘째 문단<br><br><br><br><br>셋째 |"
        assert collapse_br_runs(row) == "| 가 | 첫째 문단<br>둘째 문단<br>셋째 |"

    def test_is_idempotent(self):
        once = collapse_br_runs("가" + "<br>" * 9 + "나<br><br>다")
        assert once == "가<br>나<br><br>다"
        assert collapse_br_runs(once) == once


class TestRepeatedLines:
    def test_stamp_and_running_header_with_page_numbers(self):
        pages = [f"한국문학연구 제3집 {227 + i}\n{body}\n{STAMP}" for i, body in enumerate(
            ["고려가요의 계통을 살핀다", "향가와의 관계를 본다", "속요의 형식을 논한다", "결론을 맺는다"])]
        keys = repeated_lines(pages, 0.6)
        assert strip_lines(pages[1], keys) == "향가와의 관계를 본다"

    def test_bare_page_numbers_are_repeated_lines(self):
        pages = [f"{n}\n본문 내용 {chr(0xAC00 + n)}" for n in range(10, 15)]
        assert strip_lines(pages[0], repeated_lines(pages, 0.6)) == "본문 내용 " + chr(0xAC00 + 10)

    def test_below_ratio_is_not_repeated(self):
        pages = [STAMP] * 3 + [f"다른 쪽 {chr(0xAC00 + i)}" for i in range(7)]
        assert repeated_lines(pages, 0.6) == set()

    def test_long_line_is_not_a_candidate(self):
        long_line = "가" * 41
        assert repeated_lines([long_line] * 5, 0.6) == set()

    def test_duplicates_inside_one_page_count_once(self):
        pages = ["\n".join([STAMP] * 3)] + [f"본문 {chr(0xAC00 + i)}" for i in range(4)]
        assert repeated_lines(pages, 0.6) == set()

    def test_single_page_has_no_repeated_lines(self):
        assert repeated_lines([STAMP], 0.6) == set()

    def test_strip_lines_with_empty_set_keeps_text(self):
        assert strip_lines("a\nb", set()) == "a\nb"


class TestIsScanDocument:
    def test_majority_short_with_enough_pages(self):
        assert is_scan_document([True, True, True], min_pages=3, ratio=0.5)
        assert is_scan_document([True, True, True, False], min_pages=3, ratio=0.5)

    def test_too_few_pages(self):
        assert not is_scan_document([True, True], min_pages=3, ratio=0.5)

    def test_half_is_not_more_than_half(self):
        assert not is_scan_document([True, True, False, False], min_pages=3, ratio=0.5)

    def test_zero_pages_do_not_divide_by_zero(self):
        # 0쪽 문서 또는 min_pages <= 0 설정이어도 ZeroDivisionError 가 나면 안 된다
        assert not is_scan_document([], min_pages=3, ratio=0.5)
        assert not is_scan_document([], min_pages=0, ratio=0.5)
        assert not is_scan_document([], min_pages=-1, ratio=0.5)

    def test_non_positive_min_pages_still_apply_ratio(self):
        assert is_scan_document([True], min_pages=0, ratio=0.5)
        assert not is_scan_document([False], min_pages=0, ratio=0.5)


class TestShortPageNeedsOcr:
    def _call(self, *, stripped, raw, scan=False, force=False):
        return short_page_needs_ocr(
            fitz_len_stripped=stripped, fitz_len_raw=raw, doc_is_scan=scan, force=force, min_chars=50,
        )

    def test_force(self):
        assert self._call(stripped=7, raw=7, force=True)[0]

    def test_no_text_layer(self):
        need, why = self._call(stripped=0, raw=0)
        assert need and "텍스트 층 없음" in why

    def test_odl_missed_body(self):
        need, why = self._call(stripped=120, raw=150)
        assert need and "놓친" in why

    def test_stamp_only_page_in_digital_document_is_kept(self):
        # 이미지 표지에 매 쪽 반복 스탬프만 있는 쪽 — 쪽 단위로는 OCR 하지 않는다
        assert self._call(stripped=0, raw=33) == (False, "원래 짧은 쪽")

    def test_stamp_only_page_in_scan_document_goes_to_ocr(self):
        need, why = self._call(stripped=0, raw=33, scan=True)
        assert need and "스캔본" in why

    def test_genuine_short_page_is_kept(self):
        assert self._call(stripped=7, raw=7) == (False, "원래 짧은 쪽")

    def test_repeated_lines_do_not_hide_a_missed_body(self):
        # 비스캔 문서: 되풀이 줄을 빼면 짧아도(42) fitz 원래 길이가 50자 이상(60)이면 'ODL 이 놓친 쪽' → OCR.
        # 이미지 본문 쪽에 머리말·꼬리말만 텍스트로 남은 경우(KCI_FI003011274 1·2·8·9쪽)를 옛 규칙대로 구한다.
        need, why = self._call(stripped=42, raw=60)
        assert need and "놓친" in why

    def test_min_chars_boundary_uses_raw_length(self):
        assert self._call(stripped=0, raw=49) == (False, "원래 짧은 쪽")
        assert self._call(stripped=0, raw=50)[0]

    def test_decision_order(self):
        # 강제 → 텍스트 층 없음 → 스캔본 → 놓친 본문 → 원래 짧은 쪽
        assert "강제" in self._call(stripped=0, raw=0, scan=True, force=True)[1]
        assert "텍스트 층 없음" in self._call(stripped=0, raw=0, scan=True)[1]
        assert "스캔본" in self._call(stripped=0, raw=60, scan=True)[1]
        assert "놓친" in self._call(stripped=0, raw=60)[1]

    def test_non_scan_non_forced_matches_legacy_rule_for_every_length(self):
        # 옛 규칙(문서 단위 스캔본 판정을 넣기 전 extract_text): 0 < fitz 원래 길이 < min_chars 인 쪽만 ODL 채택, 나머지는 OCR.
        # 되풀이 줄 뺀 길이(stripped)는 이 판정에 쓰이지 않으므로 어떤 값이어도 결과가 같아야 한다.
        for raw in range(0, 131):
            for stripped in range(0, raw + 1):
                need, _ = self._call(stripped=stripped, raw=raw)
                assert need == (not 0 < raw < 50), (raw, stripped)

    def test_scan_or_force_always_sends_the_page_to_ocr(self):
        # 스캔본 문서·강제는 OCR 를 더할 뿐 빼지 않는다(짧은 쪽 분기에서는 모두 OCR)
        for raw in range(0, 131):
            for stripped in sorted({0, min(raw, 42), raw}):
                for scan, force in ((True, False), (False, True), (True, True)):
                    assert self._call(stripped=stripped, raw=raw, scan=scan, force=force)[0], (raw, stripped, scan, force)


class TestTrimRepetition:
    LEAD = "이 논문은 북위 조정의 관직 수여 기록을 분석하고 그 의미를 살핀다. "

    def test_tail_loop_is_cut_to_one_copy(self):
        text = self.LEAD + "고위직을 내려주고, 이후 " * 300 + "고위직을 내"
        trimmed, degenerate = trim_repetition(text)
        assert trimmed.startswith(self.LEAD.strip())
        assert trimmed.count("고위직을 내려주고") == 1
        assert not degenerate

    def test_whole_output_loop_is_degenerate(self):
        trimmed, degenerate = trim_repetition("ti [VP " * 500)
        assert degenerate

    def test_empty_table_rows_are_degenerate(self):
        assert trim_repetition("| | | |\n" * 400)[1]

    def test_normal_text_is_unchanged(self):
        text = "\n".join(f"{chr(0xAC00 + i * 37)}{chr(0xAC00 + i * 53)} 문장 {i}번째 내용입니다." for i in range(60))
        assert trim_repetition(text) == (text, False)

    def test_short_trailing_dots_are_kept(self):
        text = self.LEAD + "그 결과는 다음과 같다..."
        assert trim_repetition(text) == (text, False)

    def test_mostly_duplicate_lines_are_degenerate(self):
        lines = ["첫째 줄에 같은 내용이 반복된다"] * 4 + ["둘째 줄도 다시 나온다"] * 3 + ["마지막 줄은 한 번"]
        order = [lines[0], lines[4], lines[1], lines[5], lines[2], lines[6], lines[3], lines[7]]
        assert trim_repetition("\n".join(order))[1]
