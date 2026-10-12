"""services/research/terms.py — 한국어 낱말 맞추기·검색어 합성(순수 함수, 06c).

넓히기 검사·검색어 합성·일반 틀 비율이 같은 규칙으로 낱말을 나누고 맞춘다. scripts/research_eval/score.py 는 app 을
import 하지 않아 contains 복사본을 두고, 06e 화면의 키워드 하이라이트도 같은 규칙을 쓸 수 있다 — 공용 고정 예제
frontend/tests/fixtures/term_checks.json 을 함께 읽는다. 한쪽 규칙을 바꾸려면 이 파일을 고쳐야 하고, 그러면 다른 쪽
테스트가 깨진다(marker_checks.json 과 같은 방식).
"""
import json
from pathlib import Path

import pytest

from services.research.terms import (
    PARTICLES, QUERY_FILLERS, QUESTION_WORDS, compose_query, contains, content_words, tokens,
)

SHARED_FIXTURE = (
    Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "term_checks.json"
)
SHARED = json.loads(SHARED_FIXTURE.read_text(encoding="utf-8"))


class TestSharedFixture:
    def test_fixture_keeps_the_cases_both_sides_must_agree_on(self):
        # 예제를 줄여 대조를 약하게 만들지 못하게 — 고정 5문항·문장부호·짧은 나머지·긴 조사 먼저·논문 버튼 꼴,
        # 순서대로 맞음과 순서가 바뀐 틀림·공백 무시·NFKC·빈 낱말
        texts = [c["text"] for c in SHARED["content_words"]]
        for fixed in ("컴퓨팅 자원에 대한", "공공도서관 서비스 품질 평가 연구가", "노인의 우울과 사회적 지지",
                      "다문화가정 아동의 언어 발달", "기업의 사회적 책임과 재무성과"):
            assert any(fixed in t for t in texts), fixed
        assert any(t.endswith("?") for t in texts)
        assert any("제도" in c["words"] for c in SHARED["content_words"])
        assert any("으로" in t for t in texts)
        assert any(t.startswith("「") and "」에서 출발해," in t for t in texts)
        assert any("알려주세요" in t for t in texts)          # 요청 꼴 — 처음 값의 활용 꼴도 질문 꼴 낱말이다
        pairs = {(c["text"], c["word"]): c["expected"] for c in SHARED["contains"]}
        assert pairs[("노인의 우울과 사회적 지지", "노인 우울")] is True
        assert pairs[("노인의 우울", "우울 노인")] is False
        assert pairs[("다문화 가정 아동", "다문화가정")] is True
        # 낱말을 공백 지운 글에서 차례로 찾는다 — 공백 있는 글에서 찾는 구현은 '다문화가정' 을 못 찾아 거짓이 된다
        assert pairs[("다문화 가정 아동의 언어 발달", "다문화가정 언어")] is True
        assert pairs[("ＣＳＲ과 재무성과", "csr")] is True
        assert any(c["word"] == "" and c["expected"] is False for c in SHARED["contains"])
        assert all(set(c) == {"text", "words", "note"} for c in SHARED["content_words"])
        assert all(set(c) == {"text", "word", "expected", "note"} for c in SHARED["contains"])

    @pytest.mark.parametrize("case", SHARED["content_words"], ids=[c["note"] for c in SHARED["content_words"]])
    def test_content_words_match_the_shared_fixture(self, case):
        assert content_words(case["text"]) == case["words"]

    @pytest.mark.parametrize("case", SHARED["contains"], ids=[c["note"] for c in SHARED["contains"]])
    def test_contains_matches_the_shared_fixture(self, case):
        assert contains(case["text"], case["word"]) is case["expected"]


class TestTokens:
    def test_words_are_split_on_spaces_and_punctuation_after_normalizing(self):
        # content_words 와 넓히기의 한 글자 어절 검사(framing)가 함께 쓰는 어절 나누기 — 조사는 떼지 않는다
        assert tokens("「ＣＳＲ·공시」에서, 노인의  우울?") == ["csr", "공시", "에서", "노인의", "우울"]
        assert tokens("") == [] and tokens(None) == []


class TestContentWords:
    def test_constants_start_from_the_spec_values(self):
        # spec §12-2 의 처음 값 — 운영 질문을 보고 늘릴 수는 있어도 조용히 바뀌면 넓히기 검사가 달라진다.
        # QUESTION_WORDS 끝 여덟은 처음 값의 활용 꼴(관한→관해·관하여, 대한→대해·대하여, 궁금해→궁금해요,
        # 알려줘→알려주세요, 찾아줘→찾아주세요, 연구→연구들)이다 — 없으면 '노인 우울에 대해 알려주세요' 를 넓힌 답이
        # 요청 말까지 글자 그대로 옮겨야만 낱말 검사를 지나간다(06c 최종 리뷰)
        assert PARTICLES == ("에서", "에게", "으로", "로", "의", "은", "는", "이", "가", "을", "를",
                             "와", "과", "에", "도", "만")
        assert QUESTION_WORDS == ("연구", "관한", "대한", "관련", "궁금해", "궁금합니다", "알려줘", "찾아줘",
                                  "무엇", "어떻게",
                                  "관해", "관하여", "대해", "대하여", "궁금해요", "알려주세요", "찾아주세요", "연구들")
        assert QUERY_FILLERS == ("국내 학술논문에서",)

    def test_one_trailing_particle_is_stripped_longest_first(self):
        assert content_words("학교에서 가정으로 아동에게") == ["학교", "가정", "아동"]
        # 하나만 뗀다 — '평가에서도' 는 '도' 하나를 떼고 '평가에서' 로 남는다
        assert content_words("평가에서도") == ["평가에서"]

    def test_particle_is_kept_when_less_than_two_characters_remain(self):
        # '제도'·'남은'·'나이' 의 끝 글자는 조사 모양이지만 떼면 1자다
        assert content_words("제도 남은 나이") == ["제도", "남은", "나이"]

    def test_question_words_and_particle_only_tokens_are_dropped(self):
        assert content_words("무엇 어떻게 알려줘 찾아줘 궁금합니다 관련 연구는") == []
        # 「…」를 공백으로 바꾸면 남는 조사 어절('에서')은 내용어가 아니다
        assert content_words("「노인 우울」에서 출발해") == ["노인", "우울", "출발해"]

    def test_punctuation_splits_words(self):
        assert content_words("노인·우울, 지지(사회적)?") == ["노인", "우울", "지지", "사회적"]

    def test_words_are_normalized_and_kept_in_order_without_duplicates(self):
        # 전각·대문자는 NFKC·casefold 로 같은 낱말이 된다 — 처음 나온 자리에 한 번만
        assert content_words("ＣＳＲ과 공시, CSR 공시와 지배구조") == ["csr", "공시", "지배구조"]


class TestContains:
    def test_spaces_are_ignored_for_the_substring_match(self):
        assert contains("다문화 가정 아동", "다문화가정") is True
        assert contains("다문화가정 아동", "다문화 가정") is True

    def test_words_of_the_term_may_stand_apart_in_order(self):
        assert contains("노인이 겪는 우울과 사회적 지지", "노인 우울") is True

    def test_words_out_of_order_do_not_match(self):
        assert contains("노인이 겪는 우울", "우울 노인") is False

    def test_empty_word_never_matches(self):
        assert contains("컴퓨팅 자원", "") is False
        assert contains("컴퓨팅 자원", "   ") is False
        assert contains("", "컴퓨팅") is False


class TestComposeQuery:
    def test_fillers_are_removed_word_for_word_and_spaces_tidied(self):
        assert compose_query("국내 학술논문에서  공공도서관 서비스 품질 평가 방법", []) == "공공도서관 서비스 품질 평가 방법"
        # 글자 그대로만 지운다 — 띄어쓰기가 다르면 군더더기로 보지 않는다
        assert compose_query("국내학술논문에서 공공도서관", []) == "국내학술논문에서 공공도서관"

    def test_only_terms_missing_from_the_query_are_added_in_order(self):
        assert compose_query("컴퓨팅 자원 할당 방법", ["컴퓨팅 자원", "클라우드", "엣지 컴퓨팅"]) == (
            "컴퓨팅 자원 할당 방법 클라우드 엣지 컴퓨팅")

    def test_terms_are_tidied_and_empty_ones_skipped(self):
        # 06e·score.py 가 옮겨 쓰는 순수 함수라 입력을 믿지 않는다(정함 12) — 빈 용어를 붙이면 끝 공백이 남아 두 번
        # 거친 값이 달라진다(멱등이 깨진다)
        once = compose_query("자원 할당", ["", "   ", "클라우드  컴퓨팅"])
        assert once == "자원 할당 클라우드 컴퓨팅"
        assert compose_query(once, ["", "   ", "클라우드  컴퓨팅"]) == once

    def test_term_contained_in_an_added_term_is_not_added_again(self):
        # 이어 붙인 용어도 다음 비교에 든다 — '클라우드 컴퓨팅' 을 붙인 뒤 '클라우드' 는 이미 있다
        assert compose_query("자원 할당", ["클라우드 컴퓨팅", "클라우드"]) == "자원 할당 클라우드 컴퓨팅"

    def test_without_terms_only_fillers_are_removed(self):
        assert compose_query("국내 학술논문에서 노인 우울 측정 도구", []) == "노인 우울 측정 도구"
        assert compose_query("노인 우울 측정 도구", ()) == "노인 우울 측정 도구"

    def test_composing_twice_changes_nothing(self):
        terms = ["컴퓨팅 자원", "클라우드"]
        once = compose_query("국내 학술논문에서 컴퓨팅 자원 할당 방법", terms)
        assert once == "컴퓨팅 자원 할당 방법 클라우드"
        assert compose_query(once, terms) == once

    def test_query_left_empty_by_fillers_falls_back_to_the_text(self):
        assert compose_query(" 국내 학술논문에서 ", []) == "국내 학술논문에서"
