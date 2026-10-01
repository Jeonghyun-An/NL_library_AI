"""paper_enricher 초록·참고문헌 추출 단위 테스트.

실제 KCI 논문 PDF 추출 텍스트에서 관찰된 실패 패턴을 회귀 케이스로 고정:
  - 목차의 "Abstract …… 3" 줄을 초록 헤더로 오인
  - 본문 "요약하면, …" 문장을 초록 헤더로 오인
  - 참고문헌 항목 사이에 빈 줄이 없어 전체가 1개 덩어리로 뭉침
  - "**참고문헌**" 처럼 헤더 뒤 마크다운이 붙으면 헤더 인식 실패
"""
import asyncio
import gzip
import json
import logging

import pytest

from services.ingestion import paper_enricher
from services.ingestion.paper_enricher import (
    FigureChunk,
    PaperEnrichment,
    TableChunk,
    delete_enrichment_artifact,
    enrich_paper,
    extract_abstract,
    extract_references,
    interpret_table,
    load_enrichment_artifact,
    save_enrichment_artifact,
    trim_to_last_sentence,
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

    def test_angle_bracket_header(self):
        """'<한글 요약>' 꺾쇠로 감싼 헤더 (KCI 인문학 논문에 흔함)."""
        text = (
            "# 고대 그리스의 죽음과 영혼의 제의의 철학적 의미\n"
            "장 영 란(한국외대)\n"
            "<한글 요약>\n"
            "본 논문은 초기 그리스 사회에서 죽음과 영혼의 제의 및 죽음 이후의 "
            "영혼관과 처벌과 보상의 문제를 검토하여 철학적 의미를 밝혀내는 데 "
            "주목적이 있다. 이러한 논의는 그리스 철학의 영혼관을 이해하는 단초가 된다.\n\n"
            "## 서론\n본문 시작…"
        )
        result = extract_abstract(text)
        assert result is not None
        assert result.startswith("본 논문은")
        assert "서론" not in result

    def test_bracket_header(self):
        """'[초록]' 대괄호 헤더."""
        text = (
            "제목\n"
            "[초록]\n"
            "본 연구는 대괄호로 감싼 초록 헤더를 처리하는지 검증한다. 실험 결과 "
            "제안 방식이 유효함을 확인하였고 향후 확장 가능성도 논의하였다.\n\n"
            "1. 서론\n..."
        )
        result = extract_abstract(text)
        assert result is not None
        assert result.startswith("본 연구는")

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

    def test_glued_markdown_header_after_body_text(self):
        """레거시 VLM 텍스트 — '## 참고문헌'이 앞선 본문과 한 줄에 붙어 나온다 (KCI_FI000850832 관찰).

        구 라우팅 정책(모든 KCI 페이지를 VLM으로 처리)이 만든 텍스트는 마크다운 헤더가
        줄 시작이 아니라 본문 뒤에 이어 붙는다. 이 경우도 헤더로 인식해야 한다.
        """
        text = (
            "al Sciences, 59(7-A), 2456.\n"
            "- 거한 진로상담의 주요한 특징이라고 할 수 있다. ## 참 고 문 헌\n\n"
            "[1] 첫 번째 문헌. (2020). 학회지.\n"
            "[2] 두 번째 문헌. (2021). 학회지.\n"
            "[3] 세 번째 문헌. (2022). 학회지.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert refs[0].startswith("[1]")

    def test_single_korean_author_year_entry_start(self):
        """'박성수(1997).'처럼 쉼표 없이 이름에 바로 붙는 단독 저자+연도 항목 시작을 인식."""
        text = (
            "참고문헌\n"
            "박성수(1997). 천재성의 발달과정과 개발전략. 서울: 청소년대화의 광장.\n"
            "유현실(1998). 재능의 발달과정에 관한 연구. 서울대학교 대학원 석사학위 논문.\n"
            "Crites, J. (1969). Vocational psychology. New York: McGraw-Hill.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert refs[0].startswith("박성수")
        assert refs[1].startswith("유현실")

    def test_single_latin_surname_year_entry_start(self):
        """'Csikszentmihalyi(1965).'처럼 쉼표 없이 성에 바로 붙는 영문 단독 저자+연도 항목 시작을 인식."""
        text = (
            "References\n"
            "Csikszentmihalyi(1965). Artistic problems and their solution. Some Press.\n"
            "Crites, J. (1969). Vocational psychology. New York: McGraw-Hill.\n"
            "Csikszentmihalyi, M. (1975). Beyond boredom and anxiety. San Francisco: Jossey-Bass.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert refs[0].startswith("Csikszentmihalyi(1965)")

    def test_header_keyword_in_prose_not_matched(self):
        """문장 중간에 '참고문헌'이 포함돼도(줄 끝이 아니면) 헤더로 오인하지 않는다."""
        assert extract_references("앞선 연구의 참고문헌을 정리하면 다음과 같다.") == []

    def test_prose_with_parenthesized_year_not_entry_start(self):
        """본문 문장에 '(1999)'가 있어도 줄 시작이 저자명이 아니면 항목 시작으로 오인하지 않는다."""
        text = (
            "참고문헌\n"
            "박성수(1997). 천재성의 발달과정과 개발전략. 서울: 청소년대화의 광장.\n"
            "이 현상은 선행 연구(1999)에서도 보고되었다.\n"
            "유현실(1998). 재능의 발달과정에 관한 연구. 서울대학교 대학원 석사학위 논문.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 2
        assert "이 현상은 선행 연구" in refs[0]
        assert refs[1].startswith("유현실")

    def test_url_fragment_not_header(self):
        """URL 프래그먼트(#references)는 헤더가 아니다.

        헤더는 마지막 매칭을 기준으로 자르므로, 참고문헌 뒤의 가짜 헤더 하나가
        섹션 전체를 날린다. '#' 앞 공백 요구가 없으면 이 입력이 0건이 된다.
        """
        text = (
            "참고문헌\n"
            "[1] 첫 번째 문헌. (2020). 학회지.\n"
            "[2] 두 번째 문헌. (2021). 학회지.\n"
            "[3] 세 번째 문헌. (2022). 원문: https://example.org/doc#references\n"
        )
        refs = extract_references(text)
        assert len(refs) == 3
        assert refs[0].startswith("[1]")

    def test_intext_citation_not_entry_start(self):
        """참고문헌 구간 안의 본문 인용('김영희(2001)는')은 항목 시작이 아니다.

        연도 괄호 뒤 '.'·',' 요구가 없으면 조사가 붙은 인용도 새 항목으로 끊긴다.
        """
        text = (
            "참고문헌\n"
            "박성수(1997). 천재성의 발달과정과 개발전략. 서울: 청소년대화의 광장.\n"
            "김영희(2001)는 이 결과를 다르게 해석한다.\n"
            "유현실(1998). 재능의 발달과정에 관한 연구. 서울대학교 대학원 석사학위 논문.\n"
        )
        refs = extract_references(text)
        assert len(refs) == 2
        assert "김영희(2001)는" in refs[0]
        assert refs[1].startswith("유현실")


# ── 표 해석 잘림 다듬기 ──────────────────────────────────────

class TestTrimToLastSentence:
    def test_cuts_unfinished_tail(self):
        text = "표 1은 집단별 평균을 보여 준다. 실험군이 대조군보다 높았다. 반면 남성 집단의 경우"
        assert trim_to_last_sentence(text) == "표 1은 집단별 평균을 보여 준다. 실험군이 대조군보다 높았다."

    def test_korean_endings_and_other_marks(self):
        assert trim_to_last_sentence("차이가 컸어요. 그런데 이") == "차이가 컸어요."
        assert trim_to_last_sentence("유의한가? 그렇다! 그러나 표본이") == "유의한가? 그렇다!"
        assert trim_to_last_sentence("增加了。 然后") == "增加了。"

    def test_decimal_point_is_not_a_sentence_end(self):
        assert trim_to_last_sentence("평균은 3.5점이다. 표준편차는 1.2") == "평균은 3.5점이다."

    def test_finished_text_is_kept(self):
        assert trim_to_last_sentence("두 집단의 차이는 유의했다.\n") == "두 집단의 차이는 유의했다."

    def test_no_finished_sentence_returns_original(self):
        text = "남성 45.2, 여성 52"
        assert trim_to_last_sentence(text) == text


class TestInterpretTable:
    TABLE = "| 집단 | 평균 |\n|---|---|\n| A | 1 |\n| B | 2 |"

    def _patch_chat_full(self, monkeypatch, content, finish_reason):
        from services import llm_client

        seen = {}

        async def fake_chat_full(messages, *, params=None, timeout=120.0):
            seen["messages"] = messages
            seen["params"] = params
            return llm_client.LLMResult(content=content, finish_reason=finish_reason)

        monkeypatch.setattr(llm_client, "chat_full", fake_chat_full)
        return seen

    def test_length_trims_to_last_finished_sentence(self, monkeypatch):
        seen = self._patch_chat_full(monkeypatch, "A 집단의 평균이 더 높다. B 집단은", "length")

        out = asyncio.run(interpret_table("논문", "표 앞 맥락", self.TABLE))

        assert out == "A 집단의 평균이 더 높다."
        assert seen["params"]["max_tokens"] == 600           # 상한은 올리지 않는다
        assert self.TABLE in seen["messages"][1]["content"]

    def test_stop_keeps_whole_text(self, monkeypatch):
        self._patch_chat_full(monkeypatch, "A 집단의 평균이 더 높다. B 집단은", "stop")

        out = asyncio.run(interpret_table("논문", "표 앞 맥락", self.TABLE))

        assert out == "A 집단의 평균이 더 높다. B 집단은"


# ── 단계 세마포어 ─────────────────────────────────────────────

class _Gauge:
    """동시에 몇 개가 LLM 을 부르고 있는지 잰다."""

    def __init__(self):
        self.active = 0
        self.peak = 0
        self.calls: list[str] = []

    async def hold(self, name: str):
        self.calls.append(name)
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1


def _paper_text(n_tables: int) -> str:
    """키워드 줄·참고문헌 헤더가 없어 둘 다 LLM 폴백을 타는 본문 + 표 n_tables 개."""
    parts = ["서론 문단이다. " * 30]
    for i in range(n_tables):
        parts.append(f"표 {i + 1} 앞 문단이다.\n| 집단 | 평균 |\n|---|---|\n| A | {i} |\n| B | {i + 1} |\n")
    return "\n\n".join(parts)


def _patch_enrich_llm(monkeypatch) -> _Gauge:
    gauge = _Gauge()

    async def fake_keywords(title, text):
        await gauge.hold("kw")
        return ["가", "나"]

    async def fake_references(text):
        await gauge.hold("ref")
        return ["r1", "r2", "r3"]

    async def fake_table(title, ctx, md):
        await gauge.hold("table")
        return "A 가 더 높다."

    monkeypatch.setattr(paper_enricher, "generate_keywords", fake_keywords)
    monkeypatch.setattr(paper_enricher, "generate_references", fake_references)
    monkeypatch.setattr(paper_enricher, "interpret_table", fake_table)
    monkeypatch.setattr(paper_enricher, "_list_figure_keys", lambda book_id, client: [])
    return gauge


class TestEnrichPaperSemaphore:
    def test_given_semaphore_caps_every_llm_call(self, monkeypatch):
        """sem 을 주면 표 해석도 그 세마포어만 쓴다 — 표용 세마포어를 따로 만들면 peak 가 4 가 된다."""
        gauge = _patch_enrich_llm(monkeypatch)
        monkeypatch.setattr(paper_enricher.cfg, "LLM_SECTION_CONCURRENCY", 4)

        async def run():
            return await enrich_paper("B1", "제목", _paper_text(5), None, sem=asyncio.Semaphore(1))

        result = asyncio.run(run())

        assert gauge.peak == 1
        assert gauge.calls.count("table") == 5 and "kw" in gauge.calls and "ref" in gauge.calls
        assert len(result.table_chunks) == 5
        assert all(tc.description == "A 가 더 높다." for tc in result.table_chunks)

    def test_without_semaphore_uses_section_concurrency(self, monkeypatch):
        gauge = _patch_enrich_llm(monkeypatch)
        monkeypatch.setattr(paper_enricher.cfg, "LLM_SECTION_CONCURRENCY", 2)

        asyncio.run(enrich_paper("B1", "제목", _paper_text(5), None))

        assert gauge.peak == 2

    def test_keyword_and_reference_fallbacks_wait_for_the_semaphore(self, monkeypatch):
        """섹션 요약이 자리를 모두 쥐고 있으면 키워드·참고문헌 LLM 폴백도 기다린다."""
        gauge = _patch_enrich_llm(monkeypatch)

        async def scenario():
            sem = asyncio.Semaphore(1)
            await sem.acquire()
            task = asyncio.create_task(enrich_paper("B1", "제목", _paper_text(0), None, sem=sem))
            for _ in range(5):
                await asyncio.sleep(0)
            started_while_held = list(gauge.calls)
            sem.release()
            await task
            return started_while_held

        assert asyncio.run(scenario()) == []
        assert gauge.calls == ["kw", "ref"]


# ── 보강 아티팩트 ─────────────────────────────────────────────

class _NoSuchKey(Exception):
    code = "NoSuchKey"     # minio S3Error 와 같은 속성


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        pass

    def release_conn(self):
        pass


class _FakeMinio:
    def __init__(self, fail_remove: bool = False):
        self.objects: dict[str, bytes] = {}
        self.fail_remove = fail_remove

    def put_object(self, bucket, key, data, length, content_type=None):
        self.objects[key] = data.read()

    def get_object(self, bucket, key):
        if key not in self.objects:
            raise _NoSuchKey(key)
        return _FakeResp(self.objects[key])

    def remove_object(self, bucket, key):
        if self.fail_remove:
            raise ConnectionError("minio down")
        self.objects.pop(key, None)        # S3 처럼 없는 키를 지워도 성공


class TestEnrichmentArtifact:
    def test_save_then_load_round_trips(self):
        client = _FakeMinio()
        enrichment = PaperEnrichment(
            abstract="초록 본문",
            keywords=["가", "나"],
            toc=["1. 서론", "2. 방법", "3. 결론"],
            references=["[1] 김. (2020).", "[2] 이. (2021)."],
            table_chunks=[TableChunk(context="맥락", table_md="| a | b |", description="설명."),
                          TableChunk(context="", table_md="| c | d |", description="")],
            figure_chunks=[FigureChunk(minio_key="figures/B1/p1_i0.jpg", description="그림 설명.")],
        )

        save_enrichment_artifact("B1", enrichment, client)

        assert list(client.objects) == ["artifacts/B1/enrichment.json.gz"]
        assert load_enrichment_artifact("B1", client) == enrichment

    def test_run_token_must_match_when_both_sides_have_one(self):
        client = _FakeMinio()
        enrichment = PaperEnrichment(abstract="이번 실행의 초록")
        save_enrichment_artifact("B1", enrichment, client, run_token="T1")

        assert load_enrichment_artifact("B1", client, run_token="T1") == enrichment
        assert load_enrichment_artifact("B1", client, run_token="T2") is None   # 다른 실행이 남긴 것
        assert load_enrichment_artifact("B1", client) == enrichment             # 토큰 없는 호출(단건 흐름)

    def test_pre_deploy_payload_without_token_is_still_used(self):
        """배포 전 embed 가 남긴 아티팩트(run_token 키 없음)는 토큰이 있는 호출에서도 쓴다."""
        client = _FakeMinio()
        old_payload = {"abstract": "옛 초록", "keywords": [], "toc": [], "references": [],
                       "table_chunks": [], "figure_chunks": []}
        client.objects["artifacts/B1/enrichment.json.gz"] = gzip.compress(
            json.dumps(old_payload, ensure_ascii=False).encode("utf-8"))

        assert load_enrichment_artifact("B1", client, run_token="T1") == PaperEnrichment(abstract="옛 초록")

    def test_delete_removes_artifact_and_never_raises(self, caplog):
        client = _FakeMinio()
        save_enrichment_artifact("B1", PaperEnrichment(abstract="초록"), client, run_token="T1")

        delete_enrichment_artifact("B1", client)
        delete_enrichment_artifact("B1", client)          # 없는 키도 조용히

        assert client.objects == {}
        with caplog.at_level(logging.WARNING, logger=paper_enricher.log.name):
            delete_enrichment_artifact("B1", _FakeMinio(fail_remove=True))
        assert [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_missing_artifact_returns_none_quietly(self, caplog):
        with caplog.at_level(logging.WARNING, logger=paper_enricher.log.name):
            assert load_enrichment_artifact("B1", _FakeMinio()) is None
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    @pytest.mark.parametrize("raw", [
        b"not gzip",
        gzip.compress(b"{not json"),
        gzip.compress(b"[1, 2]"),
    ], ids=["not-gzip", "not-json", "not-object"])
    def test_broken_artifact_returns_none_with_warning(self, caplog, raw):
        client = _FakeMinio()
        client.objects["artifacts/B1/enrichment.json.gz"] = raw

        with caplog.at_level(logging.WARNING, logger=paper_enricher.log.name):
            assert load_enrichment_artifact("B1", client) is None
        assert [r for r in caplog.records if r.levelno == logging.WARNING]
