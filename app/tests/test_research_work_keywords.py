"""services/research_work/keywords.py — 제목 고르기의 키워드 후보(순수 함수, round06e D23).

LLM 후보와 채택 논문의 소장 키워드(문서 빈도)를 합치는 규칙 — 정리·일반어 거르기·순서·출처·편수·상한·미리 선택.
DB·LLM 을 쓰지 않는다. 서지는 BookRepository 가 돌려주는 BookOut 과 같은 이름의 속성만 가진 대역이다.
"""
from types import SimpleNamespace

import pytest

from services.research_work import keywords
from services.research_work.concepts import MAX_CONCEPT_LEN
from services.research_work.keywords import (
    GENERIC_KEYWORDS, KEYWORD_LEN_MAX, MAX_KEYWORD_CANDIDATES, MIN_PICKED_KEYWORDS, PAPER_KEYWORD_MIN_N,
    PAPER_KEYWORDS_INPUT_MAX, PRESELECT, clean_keyword, keyword_key, merge_candidates, paper_keyword_counts,
    preselect, split_catalog_keywords,
)


def _book(keyword: str | None = None, extracted: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(keyword=keyword, extracted_keywords=extracted or [])


class TestKeywordKey:
    def test_spaces_case_and_full_width_are_the_same_word(self):
        assert keyword_key("AI 윤리") == keyword_key("ai윤리") == keyword_key("ＡＩ　윤리") == "ai윤리"

    def test_different_words_stay_different(self):
        assert keyword_key("노인 우울") != keyword_key("우울 노인")


class TestCleanKeyword:
    def test_limits(self):
        assert (MAX_KEYWORD_CANDIDATES, PRESELECT, MIN_PICKED_KEYWORDS, PAPER_KEYWORDS_INPUT_MAX) == (10, 3, 2, 30)
        assert PAPER_KEYWORD_MIN_N in (1, 2)
        # 칩(research_works.concepts)과 같은 글자 상한 — 후보를 골라 PATCH 로 저장할 때 잘리지 않는다
        assert KEYWORD_LEN_MAX == MAX_CONCEPT_LEN == 40

    def test_tidies_spaces_and_normalizes(self):
        assert clean_keyword("  노인   우울 ") == "노인 우울"
        assert clean_keyword("ＡＩ　윤리") == "AI 윤리"

    @pytest.mark.parametrize("raw", [None, 3, ["노인 우울"], {"text": "노인 우울"}, "", "   ", "가" * 41])
    def test_non_strings_empty_and_too_long_give_none(self, raw):
        assert clean_keyword(raw) is None

    def test_forty_characters_pass(self):
        assert clean_keyword("가" * 40) == "가" * 40

    @pytest.mark.parametrize("raw", ["연구 성과", "국내 학술논문 코퍼스", "연구분야", "발전  방향", "측정 및 평가", "선행 연구"])
    def test_generic_words_are_dropped_whatever_the_spacing(self, raw):
        # 06b 운영 개념에 섞였던 말('측정 및 평가 · 연구 분야 · 발전 방향' — round06b-완료노트 :87)
        assert clean_keyword(raw) is None

    def test_the_generic_list_holds_the_words_seen_in_production(self):
        assert {"연구 성과", "국내 학술논문 코퍼스", "연구 분야", "발전 방향", "측정 및 평가"} <= GENERIC_KEYWORDS


class TestSplitCatalogKeywords:
    def test_semicolons_and_commas(self):
        assert split_catalog_keywords("노인 우울; 사회적 지지,가족 지지 ;") == ["노인 우울", "사회적 지지", "가족 지지"]

    def test_full_width_separators_are_normalized_first(self):
        assert split_catalog_keywords("노인 우울；사회적 지지，가족") == ["노인 우울", "사회적 지지", "가족"]

    def test_splits_the_marc_loader_pipe_join(self):
        # MARC·MARC+MODS 로더는 653 $a 를 ' | ' 로 잇는다(loaders/marc_parser.py) — MODS genre 가 thesis·report 면
        # doc_type paper 라 채택 논문이 될 수 있다. 나누지 않으면 한 조각이 가짜 후보 칩이 되거나(40자 이하) 통째로 빠진다
        assert split_catalog_keywords("노인 | 우울 | 사회적 지지") == ["노인", "우울", "사회적 지지"]
        assert split_catalog_keywords("노인｜우울; 가족") == ["노인", "우울", "가족"]   # 전각 세로줄도 NFKC 로 같다

    @pytest.mark.parametrize("raw", [None, "", " ; , "])
    def test_empty_values(self, raw):
        assert split_catalog_keywords(raw) == []


class TestPaperKeywordCounts:
    def test_counts_papers_not_mentions(self):
        # 한 논문 안에서 같은 말(653 과 추출 키워드에 둘 다, 띄어쓰기만 다름)은 한 번만 센다
        books = {"C1": _book("노인 우울; 노인우울", ["노인 우울"]), "C2": _book("노인 우울")}
        assert paper_keyword_counts(books) == [{"text": "노인 우울", "n": 2}]

    def test_catalog_and_extracted_keywords_are_joined(self):
        books = {"C1": _book("노인 우울", ["사회적 지지"]), "C2": _book(None, ["사회적 지지", "가족 지지"])}
        assert paper_keyword_counts(books) == [
            {"text": "사회적 지지", "n": 2}, {"text": "노인 우울", "n": 1}, {"text": "가족 지지", "n": 1}]

    def test_more_papers_first_then_the_order_they_came_in(self):
        books = {"C1": _book("가; 나"), "C2": _book("다; 나"), "C3": _book("다")}
        assert [k["text"] for k in paper_keyword_counts(books)] == ["나", "다", "가"]

    def test_generic_and_non_string_keywords_are_dropped(self):
        books = {"C1": _book("연구 동향; 노인 우울", ["선행연구", 3, None])}
        assert paper_keyword_counts(books) == [{"text": "노인 우울", "n": 1}]

    def test_keeps_the_first_thirty(self):
        books = {f"C{i}": _book(f"키워드{i}") for i in range(PAPER_KEYWORDS_INPUT_MAX + 5)}
        out = paper_keyword_counts(books)
        assert len(out) == PAPER_KEYWORDS_INPUT_MAX and out[0] == {"text": "키워드0", "n": 1}

    def test_no_books(self):
        assert paper_keyword_counts({}) == []


class TestMergeCandidates:
    def test_model_candidates_come_first_in_the_order_given(self):
        out = merge_candidates(["청소년", "독서 격차"], [{"text": "학교 도서관", "n": 9}])
        assert [(c["text"], c["source"]) for c in out] == [
            ("청소년", "llm"), ("독서 격차", "llm"), ("학교 도서관", "paper")]

    def test_paper_only_words_follow_by_paper_count(self):
        paper = [{"text": "가", "n": 1}, {"text": "나", "n": 3}, {"text": "다", "n": 3}]
        assert merge_candidates([], paper) == [
            {"text": "나", "source": "paper", "n": 3}, {"text": "다", "source": "paper", "n": 3},
            {"text": "가", "source": "paper", "n": 1}]

    def test_a_word_in_both_keeps_the_model_place_with_the_paper_count(self):
        out = merge_candidates(["청소년", "독서 격차"], [{"text": "독서격차", "n": 4}, {"text": "가정 환경", "n": 2}])
        assert out == [{"text": "청소년", "source": "llm", "n": 0}, {"text": "독서 격차", "source": "both", "n": 4},
                       {"text": "가정 환경", "source": "paper", "n": 2}]

    def test_at_most_ten(self):
        out = merge_candidates([f"모델{i}" for i in range(8)], [{"text": f"논문{i}", "n": 5} for i in range(8)])
        assert len(out) == MAX_KEYWORD_CANDIDATES
        assert [c["source"] for c in out] == ["llm"] * 8 + ["paper"] * 2

    def test_paper_words_below_the_minimum_count_are_dropped(self, monkeypatch):
        # 채움률이 낮으면(Task K1 판정 2) 논문에만 있는 말은 2편 이상 겹친 것만 — 모델과 겹친 말은 편수와 상관없이 남는다
        monkeypatch.setattr(keywords, "PAPER_KEYWORD_MIN_N", 2)
        out = merge_candidates(["독서 격차"], [{"text": "독서 격차", "n": 1}, {"text": "가", "n": 1}, {"text": "나", "n": 2}])
        assert out == [{"text": "독서 격차", "source": "both", "n": 1}, {"text": "나", "source": "paper", "n": 2}]

    def test_no_generic_words_and_no_repeats(self):
        out = merge_candidates(["연구 동향", "독서 격차", "독서격차", 3], [{"text": "발전 방향", "n": 9}])
        assert out == [{"text": "독서 격차", "source": "llm", "n": 0}]

    @pytest.mark.parametrize("bad", [None, "독서 격차", {"text": 3, "n": 2}, {"text": "가", "n": 0},
                                     {"text": "가", "n": "2"}, {"text": "가", "n": True}])
    def test_malformed_paper_entries_are_skipped(self, bad):
        assert merge_candidates([], [bad]) == []


class TestPreselect:
    def test_the_first_three(self):
        cands = merge_candidates(["가", "나", "다", "라"], [])
        assert preselect(cands) == ["가", "나", "다"]

    def test_fewer_than_three_are_all_picked(self):
        assert preselect(merge_candidates(["가"], [])) == ["가"]
        assert preselect([]) == []
