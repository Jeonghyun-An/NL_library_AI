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


def test_empty_text_is_not_a_bibliography():
    assert not looks_like_bibliography("")
