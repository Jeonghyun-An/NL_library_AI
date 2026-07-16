"""paper_enricher 초록·참고문헌 추출 단위 테스트.

실제 KCI 논문 PDF 추출 텍스트에서 관찰된 실패 패턴을 회귀 케이스로 고정:
  - 목차의 "Abstract …… 3" 줄을 초록 헤더로 오인
  - 본문 "요약하면, …" 문장을 초록 헤더로 오인
  - 참고문헌 항목 사이에 빈 줄이 없어 전체가 1개 덩어리로 뭉침
  - "**참고문헌**" 처럼 헤더 뒤 마크다운이 붙으면 헤더 인식 실패
"""
import pytest

from services.ingestion.paper_enricher import (
    extract_abstract,
    extract_references,
)


# ── 초록 ─────────────────────────────────────────────────────

class TestExtractAbstract:
    def test_block_header(self):
        text = (
            "논문 제목\n\n"
            "초록\n"
            "본 연구는 대규모 언어모델을 활용한 문헌 검색 시스템의 설계와 구현을 다룬다. "
            "제안 기법은 기존 방식 대비 검색 정확도를 크게 개선하였다.\n\n"
            "1. 서론\n본문 시작…"
        )
        result = extract_abstract(text)
        assert result is not None
        assert result.startswith("본 연구는")
        assert "서론" not in result

    def test_inline_colon_header(self):
        text = (
            "Abstract: This paper presents a semantic search system for library "
            "collections using large language models and dense retrieval methods.\n\n"
            "Introduction\n..."
        )
        result = extract_abstract(text)
        assert result is not None
        assert result.startswith("This paper presents")

    def test_inline_strong_label_without_colon(self):
        text = (
            "초록 본 연구는 국회도서관 소장 자료의 의미 기반 검색을 위해 "
            "임베딩 파이프라인을 설계하고 실험을 통해 그 효과를 검증하였다.\n\n"
            "1. 서론\n..."
        )
        result = extract_abstract(text)
        assert result is not None
        assert result.startswith("본 연구는")

    def test_body_sentence_yoyak_not_matched(self):
        """'요약하면, …' 같은 본문 문장은 초록 헤더가 아니다."""
        text = (
            "1. 서론\n"
            "연구 배경을 설명한다.\n"
            "요약하면, 기존 연구들은 세 가지 한계를 보인다. 첫째로 데이터 규모가 "
            "작았고 둘째로 평가 지표가 일관되지 않았으며 셋째로 재현이 어려웠다.\n"
        )
        assert extract_abstract(text) is None

    def test_toc_entry_skipped_finds_real_abstract(self):
        """목차의 'Abstract …… 3' 줄은 건너뛰고 진짜 초록을 찾는다."""
        text = (
            "목차\n"
            "Abstract .......... 3\n"
            "서론 .......... 4\n"
            "결론 .......... 20\n\n"
            "Abstract\n"
            "This study proposes a retrieval-augmented summarization pipeline "
            "for parliamentary library documents and evaluates it on Korean corpora.\n\n"
            "Introduction\n..."
        )
        result = extract_abstract(text)
        assert result is not None
        assert result.startswith("This study proposes")

    def test_too_short_returns_none(self):
        text = "초록\n짧음.\n\n1. 서론\n..."
        assert extract_abstract(text) is None

    def test_headerless_abstract_via_keyword_anchor(self):
        """헤더 없이 시작하고 '주제어:'로 끝나는 KCI 레이아웃 초록 복원."""
        text = (
            "청소년상담연구\n"
            "2003, Vol. 11, No. 1, 56-67\n"
            "성과 성폭력 사건 개념의 인지적 표상\n"
            "김정인 도경수 이재호\n"
            "성균관대학교\n"
            "본 연구에서는 연상 어휘 및 태도 분석을 통하여 성과 성폭력에 대해서 "
            "사람들이 가지고 있는 인지적 표상의 구조를 확인하고자 하였다. 분석 결과 "
            "다양한 표상 구조가 관찰되었으며 남녀 간 지각 차이가 유의미하게 나타났다.\n"
            "주제어: 인지적 표상, 성, 강간, 성희롱\n"
            "오늘날 성에 대한 태도와 행동은 급격한 변화 양상을 보이고 있다.\n"
        )
        result = extract_abstract(text)
        assert result is not None
        assert result.startswith("본 연구에서는")
        assert "주제어" not in result
        assert "청소년상담연구" not in result  # 상단 서지 노이즈 제외

    def test_ends_at_keywords(self):
        text = (
            "초록\n"
            "본 연구는 의미 기반 검색 파이프라인을 제안한다. 실험 결과 제안 기법이 "
            "기존 대비 우수한 성능을 보였음을 확인하였다.\n"
            "주제어: 의미검색, 임베딩, 요약\n"
        )
        result = extract_abstract(text)
        assert result is not None
        assert "주제어" not in result


# ── 참고문헌 ─────────────────────────────────────────────────

class TestExtractReferences:
    def test_newline_separated_entries_no_blank_lines(self):
        """빈 줄 없이 줄바꿈만으로 이어지는 항목들을 개별 분리 (핵심 회귀 케이스)."""
        text = (
            "본문 끝.\n\n"
            "참고문헌\n"
            "[1] 김철수. (2020). 도서관 정보학 연구. 한국문헌정보학회지, 54(1), 1-20.\n"
            "[2] 이영희. (2021). 시맨틱 검색의 이해. 정보관리학회지, 38(2), 45-70.\n"
            "[3] Smith, J. (2019). Dense retrieval methods. ACM SIGIR, 100-110.\n"
            "[4] 박민수. (2022). 대규모 언어모델 개관. 인공지능연구, 10(3), 5-30.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 4
        assert refs[0].startswith("[1]")
        assert refs[3].startswith("[4]")

    def test_wrapped_lines_merged_into_entry(self):
        """항목 중간에 줄바꿈이 있으면 직전 항목에 병합."""
        text = (
            "참고문헌\n"
            "[1] 김철수. (2020). 아주 긴 제목의 논문으로 줄바꿈이\n"
            "발생하는 경우의 처리. 한국학회지, 1(1), 1-10.\n"
            "[2] 이영희. (2021). 두 번째 논문. 학회지, 2(2), 20-30.\n"
            "[3] 박민수. (2022). 세 번째 논문. 학회지, 3(3), 30-40.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert "발생하는 경우의 처리" in refs[0]

    def test_header_with_trailing_markdown(self):
        """'**참고문헌**' 형태 헤더 인식."""
        text = (
            "**참고문헌**\n"
            "[1] 첫 번째 문헌. (2020). 학회지.\n"
            "[2] 두 번째 문헌. (2021). 학회지.\n"
            "[3] 세 번째 문헌. (2022). 학회지.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3

    def test_blank_line_fallback(self):
        """항목 패턴이 안 잡히는 서식은 빈 줄 분리 폴백."""
        text = (
            "References\n"
            "some unusual citation format without numbering year one\n\n"
            "another unusual citation format entry two\n\n"
            "third unusual citation entry three\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3

    def test_page_marker_lines_removed(self):
        text = (
            "참고문헌\n"
            "[1] 첫 번째 문헌. (2020). 학회지.\n"
            "학술지명 / 171\n"
            "[2] 두 번째 문헌. (2021). 학회지.\n"
            "[3] 세 번째 문헌. (2022). 학회지.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert not any("171" in r for r in refs)

    def test_stops_at_author_info(self):
        text = (
            "참고문헌\n"
            "[1] 첫 번째 문헌. (2020). 학회지.\n"
            "[2] 두 번째 문헌. (2021). 학회지.\n"
            "[3] 세 번째 문헌. (2022). 학회지.\n"
            "저자정보\n"
            "홍길동 — OO대학교 교수\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert not any("홍길동" in r for r in refs)

    def test_no_header_returns_empty(self):
        assert extract_references("참고문헌 언급 없는 본문 텍스트") == []

    def test_last_header_used(self):
        """본문에서 '참고문헌'이 언급돼도 마지막(실제 섹션) 헤더를 사용."""
        text = (
            "서론에서 다룬다.\n"
            "참고문헌\n"
            "이 장에서는 관련 연구의 참고문헌 관리 기법을 검토한다. 상세한 논의는 "
            "다음 장에서 이어진다.\n"
            "본문이 길게 이어진다.\n\n"
            "참고문헌\n"
            "[1] 첫 번째 문헌. (2020). 학회지.\n"
            "[2] 두 번째 문헌. (2021). 학회지.\n"
            "[3] 세 번째 문헌. (2022). 학회지.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert refs[0].startswith("[1]")
