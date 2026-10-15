"""services/research/bibliography.py — 논문 끝 참고문헌 목록 조각 판정.

운영 근거 청크(fixtures/bibliography_chunks.json)로 걸러야 하는 꼴(한국어 APA·영문 APA·IEEE·밴쿠버·머리)과 남겨야 하는
본문(본문 속 인용·각주·초록 접수일·표·목차)을 고정한다. 아래 합성 본문은 운영 표본에 없던 꼴 가운데 서지 꼴 한 가지만
되풀이되는 것 — 이것을 거르면 본문 대목을 잃는다.
"""
import pytest

from bibliography_chunks import CASES, chunk
from services.research.bibliography import looks_like_bibliography, strip_reference_tail


@pytest.mark.parametrize("case", CASES, ids=[c["chunk_id"] for c in CASES])
def test_production_chunks(case):
    assert looks_like_bibliography(case["text"]) is (case["expect"] == "bibliography"), case["why"]


# 연혁 목록 — 날짜 '2006. 10. 4.' 는 서지의 '연도.' 가 아니고, '법률 제8029호' 한 가지 꼴만 남는다
LAW_TIMELINE = """### 2. 도서관법 개정 연혁
- 1963. 10. 28. 도서관법 제정(법률 제1424호)
- 1987. 11. 28. 도서관법 전부개정(법률 제3972호)
- 1991. 3. 8. 도서관진흥법 제정(법률 제4352호)
- 1994. 3. 24. 도서관및독서진흥법 제정(법률 제4746호)
- 2006. 10. 4. 도서관법 전부개정(법률 제8029호)
- 2021. 12. 7. 도서관법 전부개정(법률 제18547호)"""

# 번호 목록 — '- 1) 공공도서관' 은 밴쿠버 항목 '- 49) Camacho' 와 꼴이 같다. 물음표로 끝나 서술 종결로 세지 못한다
RESEARCH_QUESTIONS = """본 연구의 연구문제는 다음과 같다.
- 1) 공공도서관 이용자가 인식하는 서비스 품질 수준은 어떠한가?
- 2) 서비스 품질의 하위 차원은 이용자 만족에 어떤 영향을 미치는가?
- 3) 이용자 만족은 재이용 의도에 어떤 영향을 미치는가?
- 4) 이용자의 인구통계적 특성에 따라 서비스 품질 인식에 차이가 있는가?
- 5) 이용 빈도에 따라 이용자 만족에 차이가 있는가?"""

# 영문 본문의 번호 인용 — ' [3] ' 은 IEEE 항목 '- [30]' 과 꼴이 같다
IEEE_RELATED_WORK = (
    "Virtual network embedding has been studied extensively. Chowdhury et al. [3] proposed a coordinated node "
    "and link mapping algorithm, and Yu et al. [4] introduced path splitting and migration. [5] formulated the "
    "problem as an integer linear program, while [6] applied a genetic algorithm to reduce the embedding cost."
)

# 'Reference service'(참고봉사)로 시작하는 영문 본문 — 단수 'Reference' 는 참고문헌 머리가 아니다
REFERENCE_SERVICE = (
    "Reference service is a core function of public libraries. Its quality was first measured with SERVQUAL "
    "and later with LibQUAL+ (2004). Following Hernon, P. & Altman, E., the study evaluates reference "
    "transactions from the user's perspective."
)


@pytest.mark.parametrize("text", [LAW_TIMELINE, RESEARCH_QUESTIONS, IEEE_RELATED_WORK, REFERENCE_SERVICE],
                         ids=["law-timeline", "research-questions", "ieee-related-work", "reference-service"])
def test_body_repeating_one_entry_shape_is_kept(text):
    assert not looks_like_bibliography(text)


# 아래는 서지 꼴이 여러 가지 섞여 서술 종결을 세어야 본문으로 남는 꼴 — 선행연구 문단은 질의 주제어가 빽빽해 리랭크
# 상위에 오는 본문이라, 잘못 거르면 근거를 잃는다

# 한국어 논문에 가장 흔한 '…하였다(저자, 연도: 쪽-쪽).' — '다' 와 마침표 사이에 괄호 인용이 끼어 있다
PRIOR_WORK_PAREN_CITES = (
    "공공도서관 서비스 품질에 관한 국내 연구는 SERVQUAL 모형을 그대로 옮겨 쓰는 데서 출발하였다(김철수, 2005: 45-67). "
    "이후 도서관 환경에 맞게 차원을 다시 짠 척도가 제안되었고, 신뢰성과 응답성이 이용자 만족을 가장 잘 설명한다고 "
    "보고되었다(Hernon, P. & Altman, E., 1998, p. 12). 이용자 집단을 나누어 본 연구에서는 노인 이용자가 시설보다 직원의 "
    "태도를 더 중요하게 여긴다는 점이 드러났다(박민수, 2011: 23-41). 지역 규모에 따른 차이를 본 연구도 있었는데, 군 단위 "
    "도서관일수록 접근성 차원의 점수가 낮았다(정수진, 2013: 77-95). 전자자료 서비스가 늘면서 웹 서비스 품질을 따로 재는 "
    "척도가 개발되었다(Parasuraman et al., 1988, pp. 15-17). 그러나 대부분의 연구는 한 시점의 설문에 기대어 품질 인식의 "
    "변화를 보지 못하였다(한지민, 2017: 5-22). 최근에는 이용 기록과 설문을 함께 쓰는 연구가 시도되었다(오세훈, 2019: "
    "133-150). 이러한 흐름에도 불구하고 재이용 의도까지 이어지는 경로를 검증한 연구는 여전히 드물다(유하늘, 2021: 61-80)."
)

# 각주 번호 '…되었다.12)' 와 닫는 따옴표 '…하였다.”' 로 끝나는 문장 — 마침표 뒤가 공백이 아니다
PRIOR_WORK_FOOTNOTES = (
    "독서진흥 정책의 법적 근거는 1994년 도서관및독서진흥법에서 처음 마련되었다.12) 이 법은 독서진흥을 도서관의 책무로 "
    "규정하였으나 예산 조항을 두지 않았다.13) 김철수는 「공공도서관 독서진흥 사업의 평가」, 제35권 제2호에서 이 공백이 "
    "사업의 지속성을 떨어뜨렸다고 지적하였다.14) 이영희 역시 「지역 독서문화 진흥의 과제」, 제12권 제1호에서 같은 문제를 "
    "제기하며 “법이 선언에 그쳤다”고 평가하였다.” 2006년 독서문화진흥법이 따로 제정되면서 기본계획 수립이 의무가 "
    "되었다.15) 그러나 기본계획의 성과지표는 여전히 행사 횟수에 머물렀다.16)"
)

# 청크 첫머리의 절 제목 속 '참고문헌' — 문헌정보학 논문에 흔한 '참고문헌 분석' 절은 참고문헌 머리가 아니다
HEADING_REFERENCE_ANALYSIS = (
    "### 2.3 참고문헌 분석에 관한 선행연구\n"
    "참고문헌 분석은 학술지 논문이 인용한 문헌의 유형·연도·언어를 세어 그 분야의 지적 구조와 자료 이용 행태를 밝히는 "
    "방법으로, 국내 문헌정보학에서는 학위논문과 학술지를 대상으로 꾸준히 쓰여 왔다(김철수, 2012: 45-67; 이영희, 2015: "
    "112-130)."
)

# 'Bibliography instruction'(서지교육)·'References to …' 로 시작하는 영문 본문 — 머리 낱말 뒤에 소문자 낱말이 잇고 영어 서술이다
BIBLIOGRAPHY_INSTRUCTION = (
    "Bibliography instruction has long been a core service of academic libraries, as noted by Smith (2010). "
    "Recent studies extend this view to online environments (Jones, 2015, p. 23). We examine how students perceive "
    "these programs and whether participation is associated with the quality of their term papers."
)
REFERENCES_TO_LAW = (
    "References to the national library law appear in Kim (2015). and Lee (2018), pp. 12-15, which describe the "
    "revision process and the role of the national library in coordinating public libraries."
)

# 제목처럼 대문자로 이어 머리 낱말 검사를 지나도 영어 서술이 있으면 머리 갈래에서 본문으로 남긴다
BIBLIOGRAPHY_INSTRUCTION_TITLED = "Bibliography Instruction in Academic Libraries\n" + BIBLIOGRAPHY_INSTRUCTION


@pytest.mark.parametrize(
    "text",
    [PRIOR_WORK_PAREN_CITES, PRIOR_WORK_FOOTNOTES, HEADING_REFERENCE_ANALYSIS, BIBLIOGRAPHY_INSTRUCTION,
     REFERENCES_TO_LAW, BIBLIOGRAPHY_INSTRUCTION_TITLED],
    ids=["prior-work-paren-cites", "prior-work-footnotes", "heading-reference-analysis", "bibliography-instruction",
         "references-to-law", "bibliography-instruction-titled"])
def test_body_with_mixed_entry_shapes_is_kept(text):
    assert not looks_like_bibliography(text)


# 아래는 짧은 조각 갈래(300자 이하·서술 0·서지 꼴 두 종류가 떨어진 두 자리)와 서지 꼬리 + 영문 초록 갈래('Abstract' 줄 앞이
# 서술 없는 서지이고 첫 제목 줄 앞에 저자-연도 '(1996).')가 거르면 안 되는 본문 — 학술지 첫 쪽 머리·출처 줄·날짜 줄

# 초록이 잘린 학술지 첫 쪽 머리 — 서술이 없고 꼴이 셋('2010.'·'No. 2'·'pp. 1')이지만 한 줄에 몰려 있다
MASTHEAD_NO_ABSTRACT = (
    "교육의 이론과 실천\n\nTheory and practice of Education\n\n2010. 15, No. 2, pp. 1-24\n\n*\n\n"
    "# 다문화가정 아동의 언어교육지원 체계 구축을 위한 모형제안\n\n고 은(전남대학교)")

_EN_ABSTRACT = (
    "\n\nAbstract\n\nThis study was conducted to identify the effects of social support on depression among older "
    "adults. Data were collected from 359 adults aged 65 and over living in the community. Social support was "
    "negatively associated with depression, and resilience mediated the association. These findings suggest that "
    "community programs should strengthen both social support and resilience.")

# 영문 첫 쪽 머리의 '(2017).' 는 저자 이니셜 뒤가 아니라 학술지 권호 뒤다
MASTHEAD_EN_ABSTRACT = (
    "Journal of the Korea Convergence Society Vol. 10, No. 3 (2017). pp. 339-349\n\n"
    "# Effects of Social Support on Depression among Older Adults\n\nHong, G. D., Kim, C. S.\n\n"
    "Dept. of Nursing, Chodang University" + _EN_ABSTRACT)

# 첫 쪽의 인용 안내 줄 — 저자-연도 '(2017).' 가 있어도 논문 제목(첫 제목 줄) 뒤라 참고문헌 꼬리가 아니다
MASTHEAD_HOW_TO_CITE = (
    "Journal of the Korea Convergence Society Vol. 10, No. 3, pp. 339-349, 2017\n\n"
    "# Effects of Social Support on Depression among Older Adults\n\nHong, G. D., Kim, C. S.\n\n"
    "Citation: Hong, G. D., & Kim, C. S. (2017). Effects of social support on depression among older adults. "
    "Journal of the Korea Convergence Society, 10(3), 339-349." + _EN_ABSTRACT)

# 그림 출처 한 줄 — 꼴 둘('(2013).'·'p.74')이 붙어 한 자리다
FIGURE_SOURCE = "<그림 1> 사회정서적 선택이론 사회적 동기 변화 궤적\n자료: 정효채 등. (2013). p.74 재인용."

# 출처 줄 뒤에 다음 절 본문 — 서술이 있다
SOURCE_THEN_METHOD = (
    "자료: 김철수(2010). 공공도서관 연구. p. 23\n\n### 3. 연구방법\n\n"
    "본 연구는 공공도서관 이용자 359명을 대상으로 설문조사를 실시하였다. 자료는 SPSS 25.0 으로 분석하였다.")

# 각주 날짜·짧은 인용 나열·접수일 — 서지 꼴이 한 종류뿐이거나 없다
FOOTNOTE_DATES = "- 3) 서울경제, 2013년 7월 18일 참조. - 4) 국민일보, 2013년 1월 28일 참조."
SHORT_CITES_LIST = "선행연구: 김철수(2010), 이영희(2012), 박민수(2015), 정수진(2017)."
RECEIVED_DATES = "논문접수일: 2013. 10. 4. 심사완료일: 2013. 11. 2. 게재확정일: 2013. 12. 1."

# 쪽 경계에서 잘린 본문 조각 — 쪽 머리글의 학술지 권호('제45권 제2호'·'Vol. 45, No. 2')와 직접 인용의 'p. 23' 이 40자 넘게
# 떨어져 서지 꼴 두 종류·두 자리가 되지만, 권호는 쪽마다 찍히는 머리글이다. 문장이 잘려 서술 종결이 없다
RUNNING_HEADER_QUOTE = (
    "- 152 - 한국도서관·정보학회지(제45권 제2호) 공공도서관은 지역 주민 누구에게나 열려 있는 \"평생학습의 장\""
    "(김철수, 2010, p. 23)이라는 점에서 다문화가정 아동을 위한 서비스를 확대할 필요가 있으며, 이를 위해")
RUNNING_HEADER_EN_QUOTE = (
    "Journal of Korean Library and Information Science Society Vol. 45, No. 2 공공도서관은 지역 주민 누구에게나 "
    "열려 있는 \"평생학습의 장\"(Kim, 2010, p. 23)이라는 점에서 다문화가정 아동을 위한 서비스를 확대할 필요가 있으며")
RUNNING_HEADER_CITES = (
    "한국비블리아학회지 제26권 제2호 2015 다문화가정 아동을 위한 공공도서관 서비스 연구 59 이러한 관점에서 "
    "선행연구로는 김철수(2010), 이영희(2012) 등이 있으며 이들 연구에서는")

# 첫 쪽 인용 안내 줄이 논문 제목 줄보다 앞에 있거나 제목 줄('#')이 없는 첫 쪽 — 인용 안내의 '(2017).' 는 이 논문 자신의
# 서지라 참고문헌 꼬리가 아니고, 뒤의 영문 초록이 근거다
_CITE_LINE = ("Citation: Hong, G. D., & Kim, C. S. (2017). Vocabulary of children from multicultural families. "
              "Journal of Speech-Language & Hearing Disorders, 26(3), 1-12.\n")
_KO_ABSTRACT = (
    "ABSTRACT\nPurpose: The purpose of this study was to examine the receptive and expressive vocabulary of "
    "children from multicultural families. Methods: Forty children aged 5 to 6 years participated in the study. "
    "Results: Children from multicultural families showed lower scores than their peers. "
    "Conclusion: These findings suggest that early vocabulary support is needed.")
_JOURNAL_LINE = "Journal of Speech-Language & Hearing Disorders Vol. 26, No. 3, 1-12\n"
CITATION_BEFORE_TITLE = _JOURNAL_LINE + _CITE_LINE + "## 다문화가정 아동의 어휘 발달\n홍길동, 김철수\n" + _KO_ABSTRACT
CITATION_NO_HEADING = _JOURNAL_LINE + _CITE_LINE + "다문화가정 아동의 어휘 발달\n홍길동, 김철수\n" + _KO_ABSTRACT
HOW_TO_CITE_BEFORE_TITLE = CITATION_BEFORE_TITLE.replace("Citation:", "How to cite this article:")


@pytest.mark.parametrize(
    "text",
    [MASTHEAD_NO_ABSTRACT, MASTHEAD_EN_ABSTRACT, MASTHEAD_HOW_TO_CITE, FIGURE_SOURCE, SOURCE_THEN_METHOD,
     FOOTNOTE_DATES, SHORT_CITES_LIST, RECEIVED_DATES, RUNNING_HEADER_QUOTE, RUNNING_HEADER_EN_QUOTE,
     RUNNING_HEADER_CITES, CITATION_BEFORE_TITLE, CITATION_NO_HEADING, HOW_TO_CITE_BEFORE_TITLE],
    ids=["masthead-no-abstract", "masthead-en-abstract", "masthead-how-to-cite", "figure-source",
         "source-then-method", "footnote-dates", "short-cites-list", "received-dates", "running-header-quote",
         "running-header-en-quote", "running-header-cites", "citation-before-title", "citation-no-heading",
         "how-to-cite-before-title"])
def test_short_or_abstract_headed_body_is_kept(text):
    assert not looks_like_bibliography(text)


# 아래는 학위논문 꼴('석사학위논문.'·'박사학위논문, ○○대학교 대학원'·'thesis, ○○ University')이 서지 꼴이 된 뒤에도 남아야 하는
# 본문 — 학위논문을 다룬 서술 문장, 첫 쪽의 학위논문 사사 각주·저자 소속, 학위논문 표지

# 서술 문장 속 학위논문 — '석사학위논문,'·'대학원,' 과 직접 인용 '2012: 45-67' 이 떨어져 있어도 서술 종결이 있다
THESIS_STUDIES = (
    "국내 문헌정보학 학위논문을 분석한 연구에서는 석사학위논문, 박사학위논문 순으로 이용자 연구가 많았다(김철수, 2012: "
    "45-67). 이영희(2015)는 연세대학교 대학원, 이화여자대학교 대학원의 석사학위논문 120편을 분석하여 노인 이용자 연구가 "
    "늘었다고 보고하였다.")

# 서술 없는 첫 쪽 머리 — 사사 각주의 '석사학위논문을'(조사)·'석사학위논문, 「…」을'(쉼표 뒤가 대학이 아님)과 저자 소속
# '연세대학교 대학원,' 은 서지가 아니다. 쪽 머리 'pp. 101-120' 과 40자 넘게 떨어져 있다
_FIRST_PAGE_HEAD = ("한국문헌정보학회지 제44권 제2호 2010 pp. 101-120\n\n"
                    "# 공공도서관 노인 이용자의 정보요구에 관한 연구\n\n홍길동*, 김철수**\n\n")
THESIS_ACK_FOOTNOTE = (_FIRST_PAGE_HEAD + "* 이 논문은 제1저자의 석사학위논문을 수정·보완한 것임\n"
                       "* 연세대학교 대학원, 문헌정보학과 석사과정\n** 연세대학교 문헌정보학과 교수")
THESIS_ACK_COMMA = (_FIRST_PAGE_HEAD + "* 이 논문은 제1저자의 석사학위논문, 「공공도서관 노인 이용자의 정보요구」를 "
                    "요약한 것임\n** 연세대학교 문헌정보학과 교수")
# 영문 사사 각주 — 'thesis.' 뒤가 대학 이름이 아니다('44(2),'·'pp. 101' 은 한 자리에 몰려 있다)
EN_THESIS_ACK = (
    "Journal of the Korean Society for Library and Information Science, 44(2), pp. 101-120\n\n"
    "# Information Needs of Older Adults in Public Libraries\n\nGil-dong Hong*, Chul-soo Kim**\n\n"
    "* Based on the first author's master's thesis.\n** Dept. of Library and Information Science, Yonsei University")
# 학위논문 표지 — '석사학위논문'·'○○대학교 대학원' 뒤에 문장부호가 없다
THESIS_COVER = ("석사학위논문\n\n노인의 우울과 사회적 지지에 관한 연구\n\n지도교수 김철수\n\n"
                "이 논문을 사회복지학 석사학위논문으로 제출함\n\n2010년 2월\n\n서울대학교 대학원\n사회복지학과\n홍길동")


@pytest.mark.parametrize(
    "text", [THESIS_STUDIES, THESIS_ACK_FOOTNOTE, THESIS_ACK_COMMA, EN_THESIS_ACK, THESIS_COVER],
    ids=["thesis-studies", "thesis-ack-footnote", "thesis-ack-comma", "en-thesis-ack", "thesis-cover"])
def test_body_mentioning_theses_is_kept(text):
    assert not looks_like_bibliography(text)


# 학위논문 항목만 둘인 짧은 조각 — 한국어 APA '(석사학위논문). ○○대학교 대학원' 은 저자-연도 '(2010).' 한 꼴만 되풀이돼
# 학위논문 꼴이 없으면 서로 다른 꼴이 하나다
KO_THESIS_APA = ("홍길동 (2010). 노인의 우울과 사회적 지지에 관한 연구 (석사학위논문). 서울대학교 대학원, 서울.\n"
                 "김철수 (2012). 공공도서관 노인 서비스의 이용 행태 연구 (박사학위논문). 연세대학교 대학원, 서울.")


def test_short_thesis_entries_are_bibliography():
    assert looks_like_bibliography(KO_THESIS_APA)


@pytest.mark.parametrize("head", ["참고문헌", "### 참고문헌", "References", "5. 참고문헌"])
def test_head_at_chunk_start_followed_by_entries_is_bibliography(head):
    """머리 낱말 뒤에 바로 서지 항목(저자 이름 + 마침표·괄호)이 이으면 머리다 — 머리를 좁혀도 이 꼴은 잡는다."""
    text = (f"{head} 김철수 (2010). 공공도서관 서비스 품질 연구. 한국문헌정보학회지, 44(2), 101-120. "
            "이영희 (2015). 독서진흥 정책의 평가. 도서관연구, 12(1), 5-22. "
            "국립중앙도서관 (2019). 2019 도서관 연감. 서울: 국립중앙도서관.")
    assert looks_like_bibliography(text)


def test_empty_text_is_not_a_bibliography():
    assert not looks_like_bibliography("")


# ── 본문 끝 참고문헌 꼬리 ──────────────────────────────────────────────
# 본문 맺음 뒤에 참고문헌 머리와 첫 항목이 붙은 청크는 본문이라 근거로 남지만, 모델에 넘기는 대목에서는 머리 뒤를 뗀다 —
# 운영 c816c7b2 E4 의 212자 대목은 맺음 한 문장 뒤가 '참고문헌 고문희(2008), “노인우울증과 …”, 전남대학교 대학원
# 석사학위논문.' 이라 그 학위논문 제목이 이 논문 내용처럼 읽힌다


@pytest.mark.parametrize("chunk_id, last", [
    ("KCI_FI001407641__0037", "실험연구를 수행할 필요를 느낀다."),    # 맺음 문장과 같은 줄의 '참고문헌'
    ("KCI_FI001061014__0022", "강점평가척도의 개발에 대한 연구의 필요성을 시사한다."),  # '#### 참고문헌'
])
def test_reference_tail_after_the_body_is_cut(chunk_id, last):
    text = chunk(chunk_id)["text"]
    out = strip_reference_tail(text)
    assert out.endswith(last) and text.startswith(out)


# 절 번호가 붙은 머리('Ⅵ. 참고문헌'·'5. 참고문헌'·'VII. REFERENCES')는 번호까지 뗀다 — 번호 뒤 마침표에서 자르면 대목 끝에
# 'Ⅵ.' 이 매달린다
@pytest.mark.parametrize("head", ["참고문헌", "### 참 고 문 헌", "[참고문헌]", "&lt;참고문헌&gt;", "REFERENCES",
                                  "Ⅵ. 참고문헌", "5. 참고문헌", "VII. REFERENCES", "## 7. References"])
def test_head_on_its_own_line_after_the_body_is_cut(head):
    body = "본 연구는 공공도서관 노인 이용자 359명을 조사하였다. 사회적 지지가 우울을 낮추었다."
    text = f"{body}\n\n{head}\n\n김철수 (2010). 공공도서관 서비스 품질 연구. 한국문헌정보학회지, 44(2), 101-120."
    assert strip_reference_tail(text) == body


def test_english_references_after_br_are_cut():
    # 표 셀처럼 줄바꿈이 <br> 로 남은 영문 청크(운영 KCI_FI002267397__0016)
    body = "Community support systems for the isolated elderly should be established."
    text = (f"{body}<br>REFERENCES<br><br>[1] Statistics Korea, \"Population census 2016\", Web site.<br>"
            "[2] H. Oh, D. Kim, \"Research on the influential factors\", Health and Social Science, Vol. 3, 2013.")
    assert strip_reference_tail(text) == body


# 그대로 두는 것 — 머리 뒤가 서지가 아니거나(쪽 배치가 뒤섞여 머리 뒤에 본문·그림이 온 청크), 머리가 아니거나(본문 낱말·
# 각주 안내·목차), 머리 앞에 서술이 없다(청크 맨 앞의 머리 — 그런 청크는 looks_like_bibliography 가 거른다)
_BODY = "본 연구는 공공도서관 노인 이용자 359명을 조사하였다. "


@pytest.mark.parametrize("text", [
    # 운영 KCI_FI002782062__0044 — '##### 참고문헌' 뒤가 이 논문의 본문이다
    _BODY + "결론 및 제언\n\n##### 참고문헌\n\n본 연구는 노인의 사회적 지지와 우울에 대한 연구를 체계적으로 고찰하였다. "
    "그 결과 사회적 지지는 우울을 낮추는 요인으로 보고되었다(김철수, 2010: 45-67).",
    # 운영 KCI_FI001202853__0021 — '### 참고문헌' 뒤가 그림 설명과 본문이다
    _BODY + "### 참고문헌\n\n&lt;그림 12&gt;은 Small Job에서 퍼지로직 기반의 그리드 작업 스케줄링 모델이 Random 스케줄링 "
    "모델보다 처리 시간이 짧음을 보여준다",
    _BODY + "참고문헌 분석에 관한 선행연구는 인용 문헌의 유형을 세었다(김철수, 2012: 45-67).",
    _BODY + "〈참고문헌은 각주로 대신함〉\n\n- 129 -",
    "목 차\nⅠ. 서론\nⅡ. 이론적 배경\nⅤ. 결론\n참고문헌\n부록",
    "참고문헌\n김철수 (2010). 공공도서관 서비스 품질 연구. 한국문헌정보학회지, 44(2), 101-120.",
    _BODY + "Bibliography instruction (2010). was offered to students.",
    _BODY + "사회적 지지가 우울을 낮추었다.",
    # 문장 속 '참고문헌'·'References' — 머리 낱말 뒤에 같은 줄의 글이 이으면 머리가 아니다. 숫자·번호 인용이 이어 낱말 검사를
    # 지나고 뒤 200자에 서지 꼴('2010: 45-67'·'p. 45')이 있어도 그 뒤 본문을 잃으면 안 된다
    _BODY + "참고문헌 120편(국내 80편, 국외 40편)을 분석한 김철수(2010: 45-67)의 연구에 따르면 사회적 지지와 우울의 관계는 "
    "연령에 따라 달랐으며 이러한 경향은",
    "The results were similar. References [3] and [4] used the same scale (Kim, 2012, p. 45). Both studies reported "
    "higher scores among older adults.",
], ids=["body-after-head", "figure-after-head", "body-word", "footnote-notice", "table-of-contents",
        "head-at-start", "bibliography-instruction", "no-head", "head-word-then-count", "references-then-cite-numbers"])
def test_text_without_a_reference_tail_is_kept_whole(text):
    assert strip_reference_tail(text) == text
