"""services/research/bibliography.py — 논문 끝 참고문헌 목록 조각 판정.

운영 근거 청크(fixtures/bibliography_chunks.json)로 걸러야 하는 꼴(한국어 APA·영문 APA·IEEE·밴쿠버·머리)과 남겨야 하는
본문(본문 속 인용·각주·초록 접수일·표·목차)을 고정한다. 아래 합성 본문은 운영 표본에 없던 꼴 가운데 서지 꼴 한 가지만
되풀이되는 것 — 이것을 거르면 본문 대목을 잃는다.
"""
import pytest

from bibliography_chunks import CASES
from services.research.bibliography import looks_like_bibliography


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


@pytest.mark.parametrize(
    "text",
    [MASTHEAD_NO_ABSTRACT, MASTHEAD_EN_ABSTRACT, MASTHEAD_HOW_TO_CITE, FIGURE_SOURCE, SOURCE_THEN_METHOD,
     FOOTNOTE_DATES, SHORT_CITES_LIST, RECEIVED_DATES],
    ids=["masthead-no-abstract", "masthead-en-abstract", "masthead-how-to-cite", "figure-source",
         "source-then-method", "footnote-dates", "short-cites-list", "received-dates"])
def test_short_or_abstract_headed_body_is_kept(text):
    assert not looks_like_bibliography(text)


@pytest.mark.parametrize("head", ["참고문헌", "### 참고문헌", "References", "5. 참고문헌"])
def test_head_at_chunk_start_followed_by_entries_is_bibliography(head):
    """머리 낱말 뒤에 바로 서지 항목(저자 이름 + 마침표·괄호)이 이으면 머리다 — 머리를 좁혀도 이 꼴은 잡는다."""
    text = (f"{head} 김철수 (2010). 공공도서관 서비스 품질 연구. 한국문헌정보학회지, 44(2), 101-120. "
            "이영희 (2015). 독서진흥 정책의 평가. 도서관연구, 12(1), 5-22. "
            "국립중앙도서관 (2019). 2019 도서관 연감. 서울: 국립중앙도서관.")
    assert looks_like_bibliography(text)


def test_empty_text_is_not_a_bibliography():
    assert not looks_like_bibliography("")
