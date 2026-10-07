"""services/search/paper_citation.py — 논문 상세 인용(CitationModal)의 학술지 자리.

학술지 이름은 series_title 이다(KCI 논문의 publisher 는 학회 이름). series_title 이 없으면 학술지
자리를 비우고 publisher 로 물러나지 않는다. 국문 인용의 "저자 (연도). 제목. 학술지, 권호." 부분은
보고서 내보내기 참고문헌(frontend/utils/reportDocument.ts 의 referenceText)과 같은 글자여야 한다 —
그 글자는 프론트 테스트(frontend/tests/unit/reportDocument.test.ts)와 함께 읽는 공유 파일
frontend/tests/fixtures/citation_reference.json 에 있다.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from schemas.book import BookOut
from services.search.paper_citation import build_citation

UCI = "G704-000001.2019.57.3.001"
# spec §5-1 의 고정 예제(저자 3인·series_title·vol_issue·UCI). publisher 는 학회 이름이다
EXAMPLE = dict(
    personal_author="김철수; 이영희; 박민수",
    pub_date="2019-03",
    title="AI 윤리 교육",
    series_title="교육학연구",
    vol_issue="57(3)",
    publisher="한국교육학회",
    uci=UCI,
)
SHARED_FIXTURE = (
    Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "citation_reference.json"
)
SHARED_CASES = {c["name"]: c for c in json.loads(SHARED_FIXTURE.read_text(encoding="utf-8"))["cases"]}


def _paper(**over) -> BookOut:
    fields = dict(
        id=uuid.UUID("0b5f3a3e-1c2d-4e5f-8a9b-0c1d2e3f4a5b"),
        cnts_id="KCI_TEST_0001",
        created_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        **EXAMPLE,
    )
    fields.update(over)
    return BookOut(**fields)


def test_journal_is_series_title_not_publisher():
    citation = build_citation(_paper())

    assert citation["korean"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. 교육학연구, 57(3). UCI {UCI}"
    assert citation["english"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. 교육학연구, 57(3). UCI {UCI}"


@pytest.mark.parametrize("name, authors", [
    ("3-authors", "김철수; 이영희; 박민수"),     # 고정 예제 그대로
    ("2-authors", "김철수; 이영희"),
    ("pipe-authors", "윤기찬 | 이순철"),        # 원본 personal_author 의 세로줄 구분(06a 이월)
], ids=["3-authors", "2-authors", "pipe-authors"])
def test_korean_prefix_matches_report_reference(name, authors):
    # 프론트 테스트가 같은 파일의 같은 서지로 referenceText 의 글자를 고정한다. 공유 파일의 서지가
    # 고정 예제에서 저자만 다른지 먼저 본다 — 서지를 바꿔 이 대조를 약하게 만들지 못하게
    case = SHARED_CASES[name]
    assert case["meta"] == {**EXAMPLE, "personal_author": authors}

    korean = build_citation(_paper(**case["meta"]))["korean"]

    assert korean == f"{case['reference']} UCI {UCI}"


def test_missing_series_title_leaves_journal_empty():
    citation = build_citation(_paper(series_title=None))

    assert citation["korean"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. UCI {UCI}"
    assert "한국교육학회" not in citation["korean"]
    assert "한국교육학회" not in citation["english"]


def test_blank_series_title_is_treated_as_missing():
    citation = build_citation(_paper(series_title="  "))

    assert citation["korean"] == f"김철수, 이영희, 박민수 (2019). AI 윤리 교육. UCI {UCI}"


def test_other_parts_are_unchanged():
    # 저자 규칙(영문 4인 이상 et al.)·연도 없음(n.d.)·UCI 없을 때 URL 은 그대로다
    citation = build_citation(_paper(
        personal_author="Kim; Lee; Park; Choi", pub_date=None, uci=None,
        url="https://www.kci.go.kr/x",
    ))

    assert citation["korean"] == (
        "Kim, Lee, Park, Choi (n.d.). AI 윤리 교육. 교육학연구, 57(3). https://www.kci.go.kr/x"
    )
    assert citation["english"] == (
        "Kim et al. (n.d.). AI 윤리 교육. 교육학연구, 57(3). https://www.kci.go.kr/x"
    )


@pytest.mark.parametrize("raw", ["윤기찬 | 이순철", "윤기찬|이순철", "윤기찬·이순철", "윤기찬; 이순철", "윤기찬, 이순철"],
                         ids=["pipe-spaced", "pipe", "middle-dot", "semicolon", "comma"])
def test_author_separators_match_the_report_reference(raw):
    # 프론트 splitAuthors(frontend/utils/citations.ts)처럼 ;·|·· 를 먼저 나눈다 — 계획서 참고문헌(정함 8)과
    # 보고서 참고문헌이 같은 저자 글자를 쓴다. 쉼표는 지금처럼 나눈다
    citation = build_citation(_paper(personal_author=raw))

    assert citation["korean"].startswith("윤기찬, 이순철 (2019). ")
    assert citation["english"].startswith("윤기찬, 이순철 (2019). ")


def test_four_pipe_separated_authors_get_et_al_in_english():
    citation = build_citation(_paper(personal_author="Kim | Lee | Park | Choi"))

    assert citation["korean"].startswith("Kim, Lee, Park, Choi (2019). ")
    assert citation["english"].startswith("Kim et al. (2019). ")


def test_one_author_without_a_separator_is_kept_whole():
    citation = build_citation(_paper(personal_author="  홍길동  "))

    assert citation["korean"].startswith("홍길동 (2019). ")
