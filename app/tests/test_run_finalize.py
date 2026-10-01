"""stages.run_finalize — 계층 요약 입력 공유·LLM 동시 호출·논문 표지 끄기 (round07 Task 8).

DB 세션·MinIO·LLM 생성 함수를 대역으로 바꿔 마무리 단계의 흐름만 본다.
생성 함수는 run_finalize 가 함수 안에서 import 하므로 summarizer 모듈 속성을 바꿔 둔다.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import services.ingestion.cover_generator as cover_generator
from services.ingestion import stages, summarizer
from services.ingestion.stages import StageContext

COMBINED = "[섹션 1~3] 계층 요약으로 합친 입력"
SUMMARIES = ["섹션1 요약", "섹션2 요약", "섹션3 요약"]


def _book(doc_type):
    return SimpleNamespace(
        cnts_id="B1", title="제목", personal_author="저자", corporate_author=None,
        publisher="출판사", pub_date="2020", kdc="800", doc_type=doc_type, extra={},
        summary=None, themes=None, introduction=None, cover_image_key=None, cover_prompt=None,
        is_embedded=False,
    )


def _patch(monkeypatch, book, *, concurrency=4, fail=(), reduce_error=None):
    """DB·MinIO·생성 함수 대역. state 에 호출 이름·받은 combined_text·최대 동시 실행 수를 모은다."""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = book
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
        (s,) for s in SUMMARIES
    ]
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)
    monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())
    monkeypatch.setattr(stages, "delete_artifact", lambda book_id, client: None)
    monkeypatch.setattr("sqlalchemy.orm.attributes.flag_modified", lambda obj, key: None)
    monkeypatch.setattr(stages.cfg, "LLM_SECTION_CONCURRENCY", concurrency)

    state = {"active": 0, "peak": 0, "calls": [], "combined": [], "cover": 0}

    async def _run(name, combined_text, value):
        state["calls"].append(name)
        state["combined"].append(combined_text)
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.05)
        state["active"] -= 1
        if name in fail:
            raise RuntimeError(f"{name} LLM 실패")
        return value

    async def fake_reduce(title, author, section_summaries, doc_type="book"):
        state["reduce_args"] = (title, author, list(section_summaries), doc_type)
        if reduce_error:
            raise reduce_error
        return COMBINED

    async def fake_summary(title, author, section_summaries, doc_type="book", *, combined_text=None):
        return await _run("summary", combined_text, ("문서 요약", ["테마1", "테마2"]))

    async def fake_intro(title, author, publisher, pub_date, section_summaries, doc_type="book", *,
                         combined_text=None):
        return await _run("introduction", combined_text, "소개글")

    async def fake_plot(title, author, section_summaries, doc_type="book", *, combined_text=None):
        return await _run("plot", combined_text, "줄거리")

    async def fake_read_effect(title, author, section_summaries, doc_type="book", *, combined_text=None):
        return await _run("read_effect", combined_text, "독후 효과")

    async def fake_cover(**kw):
        state["cover"] += 1
        return "covers/B1.jpg", "cover prompt"

    monkeypatch.setattr(summarizer, "reduce_section_summaries", fake_reduce, raising=False)
    monkeypatch.setattr(summarizer, "summarize_book_from_sections", fake_summary)
    monkeypatch.setattr(summarizer, "generate_book_introduction", fake_intro)
    monkeypatch.setattr(summarizer, "generate_book_plot", fake_plot)
    monkeypatch.setattr(summarizer, "generate_read_effect", fake_read_effect)
    monkeypatch.setattr(cover_generator, "generate_and_store_cover", fake_cover)
    return state


def test_book_texts_share_reduced_input_and_run_concurrently(monkeypatch):
    """도서: 계층 요약을 한 번 만들고, 요약·소개글·줄거리·독후 효과 넷이 그 입력으로 동시에 돈다."""
    book = _book("book")
    state = _patch(monkeypatch, book)

    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))

    assert state["reduce_args"] == ("제목", "저자", SUMMARIES, "book")
    assert sorted(state["calls"]) == ["introduction", "plot", "read_effect", "summary"]
    assert state["combined"] == [COMBINED] * 4
    assert state["peak"] == 4                                   # 차례로가 아니라 동시에
    assert book.summary == "문서 요약" and book.themes == "테마1, 테마2"
    assert book.introduction == "소개글"
    assert book.extra == {"plot": "줄거리", "read_effect": "독후 효과"}
    assert result == {"summary": True, "plot": True, "read_effect": True, "introduction": True, "cover": False}


def test_concurrency_stays_within_llm_section_concurrency(monkeypatch):
    """동시 호출은 요약 단계와 같은 LLM_SECTION_CONCURRENCY 까지 — gemma 자리 예산(celery-llm 4 × 4)."""
    state = _patch(monkeypatch, _book("book"), concurrency=2)
    stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["peak"] == 2 and len(state["calls"]) == 4


def test_paper_runs_summary_and_introduction_only(monkeypatch):
    """논문: 줄거리·독후 효과는 만들지 않고 요약·소개글 둘이 동시에 돈다."""
    state = _patch(monkeypatch, _book("paper"))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert sorted(state["calls"]) == ["introduction", "summary"]
    assert state["peak"] == 2
    assert result["plot"] is False and result["read_effect"] is False


def test_one_failed_call_does_not_drop_the_others(monkeypatch):
    """하나가 실패해도(경고 후 None) 나머지 결과는 그대로 저장한다 — 지금의 개별 try 와 같다."""
    book = _book("book")
    _patch(monkeypatch, book, fail=("introduction",))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert book.introduction is None
    assert book.summary == "문서 요약"
    assert book.extra == {"plot": "줄거리", "read_effect": "독후 효과"}
    assert result["introduction"] is False and result["summary"] is True


def test_reduce_failure_falls_back_to_each_generators_own_combine(monkeypatch):
    """계층 요약이 예외를 내면 combined_text=None 으로 넘겨 각 함수가 지금처럼 _combine_sections 로 합친다."""
    state = _patch(monkeypatch, _book("paper"), reduce_error=RuntimeError("프롬프트 없음"))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["combined"] == [None, None]
    assert result["summary"] is True and result["introduction"] is True


def test_paper_skips_cover_even_without_skip_cover_param(monkeypatch):
    """논문은 잡 params 에 skip_cover 가 없어도 표지(프롬프트 LLM + FLUX)를 만들지 않는다(사용자 결정 2026-10-01)."""
    state = _patch(monkeypatch, _book("paper"))
    result = stages.run_finalize(StageContext(book_id="B1", params={}))
    assert state["cover"] == 0 and result["cover"] is False


def test_book_cover_follows_skip_cover_param(monkeypatch):
    """도서는 지금처럼 skip_cover 가 없으면 표지를 만들고, 있으면 건너뛴다."""
    book = _book("book")
    state = _patch(monkeypatch, book)
    result = stages.run_finalize(StageContext(book_id="B1", params={}))
    assert state["cover"] == 1 and result["cover"] is True
    assert book.cover_image_key == "covers/B1.jpg" and book.cover_prompt == "cover prompt"

    state = _patch(monkeypatch, _book("book"))
    stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["cover"] == 0
