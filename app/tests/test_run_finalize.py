"""stages.run_finalize — 계층 요약 입력 공유·LLM 동시 호출·논문 표지 끄기·시간 예산·실행 기록 (round07 Task 8).

DB 세션·MinIO·LLM 생성 함수를 대역으로 바꿔 마무리 단계의 흐름만 본다.
생성 함수는 run_finalize 가 함수 안에서 import 하므로 summarizer 모듈 속성을 바꿔 둔다.
"""
import asyncio
import logging
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

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


def _patch(monkeypatch, book, *, concurrency=4, fail=(), fail_exc=None, reduce_error=None,
           reduce_run=(1, 4), reduce_delay=0.0, summaries=SUMMARIES, real_reduce=False):
    """DB·MinIO·생성 함수 대역. state 에 호출 이름·받은 combined_text·최대 동시 실행 수를 모은다.

    reduce_run=(levels, groups): 가짜 계층 요약이 stats 에 남기는 실행 기록. reduce_delay: 가짜 계층 요약이
    끝나기까지 걸리는 시간(초). real_reduce=True 면 진짜 reduce_section_summaries 를 쓴다(호출부가 설정을 바꾼다).
    """
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = book
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
        (s,) for s in summaries
    ]
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)
    monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())
    monkeypatch.setattr(stages, "delete_artifact", lambda book_id, client: None)
    monkeypatch.setattr("sqlalchemy.orm.attributes.flag_modified", lambda obj, key: None)
    monkeypatch.setattr(stages.cfg, "LLM_SECTION_CONCURRENCY", concurrency)

    state = {"active": 0, "peak": 0, "calls": [], "combined": [], "cover": 0,
             "reduce_cancelled": False}

    async def _run(name, combined_text, value):
        state["calls"].append(name)
        state["combined"].append(combined_text)
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.05)
        state["active"] -= 1
        if name in fail:
            raise fail_exc if fail_exc is not None else RuntimeError(f"{name} LLM 실패")
        return value

    async def fake_reduce(title, author, section_summaries, doc_type="book", *, stats=None):
        state["reduce_args"] = (title, author, list(section_summaries), doc_type)
        if stats is not None:
            stats.levels, stats.groups = reduce_run
        if reduce_error:
            raise reduce_error
        if reduce_delay:
            try:
                await asyncio.sleep(reduce_delay)
            except asyncio.CancelledError:
                state["reduce_cancelled"] = True
                raise
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

    if not real_reduce:
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
    assert result == {
        "summary": True, "plot": True, "read_effect": True, "introduction": True, "cover": False,
        "reduce_levels": 1, "reduce_groups": 4, "reduce_fallback": False,
    }


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


def test_failure_warning_names_the_exception_type_when_message_is_empty(monkeypatch, caplog):
    """ReadTimeout 처럼 메시지가 빈 예외는 경고에 '생성 실패: ' 만 남지 않고 예외 이름이 찍힌다."""
    _patch(monkeypatch, _book("book"), fail=("introduction",), fail_exc=httpx.ReadTimeout(""),
           reduce_error=httpx.ReadTimeout(""))
    caplog.set_level(logging.WARNING, logger="services.ingestion.stages")
    stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    messages = [r.getMessage() for r in caplog.records]
    assert any("도서 소개글 생성 실패: ReadTimeout" in m for m in messages)
    assert any("계층 요약 실패" in m and m.rstrip().endswith("ReadTimeout") for m in messages)


def test_reduce_failure_falls_back_to_each_generators_own_combine(monkeypatch):
    """계층 요약이 예외를 내면 combined_text=None 으로 넘겨 각 함수가 지금처럼 _combine_sections 로 합친다."""
    state = _patch(monkeypatch, _book("paper"), reduce_error=RuntimeError("프롬프트 없음"), reduce_run=(0, 0))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["combined"] == [None, None]
    assert result["summary"] is True and result["introduction"] is True
    assert result["reduce_fallback"] is True                    # 샘플링으로 대신했다고 meta 에 남는다


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


# ── 계층 요약 시간 예산 (round07 Task 8 리뷰 반영) ────────────────────────────
# INGEST_STAGE_TIMEOUT_FINALIZE 는 시도별 하드 마감이다 — 넘으면 stale 복구가 토큰을 바꿔 늦은 성공이 버려지고
# 같은 일이 되풀이된다. 계층 요약이 그 안에서 끝나도록 최종 호출·표지·여유를 뺀 만큼만 쓰게 한다.
def _fix_timeouts(monkeypatch, *, finalize=900, book=120, intro=120, plot=120, read_effect=120,
                  cover_prompt=60, flux=300):
    for key, value in {
        "INGEST_STAGE_TIMEOUT_FINALIZE": finalize, "SUMMARIZER_BOOK_TIMEOUT": book,
        "SUMMARIZER_INTRO_TIMEOUT": intro, "SUMMARIZER_PLOT_TIMEOUT": plot,
        "SUMMARIZER_READ_EFFECT_TIMEOUT": read_effect, "COVER_PROMPT_TIMEOUT": cover_prompt,
        "FLUX_TIMEOUT": flux,
    }.items():
        monkeypatch.setattr(stages.cfg, key, value)


def test_reduce_budget_formula(monkeypatch):
    """예산 = 마무리 단계 타임아웃 − 최종 호출 몫 − 여유 60초(− 표지를 만들면 표지 프롬프트 LLM + FLUX), 하한 60초."""
    _fix_timeouts(monkeypatch)
    assert stages._reduce_budget_seconds(120, make_cover=False) == 900 - 120 - 60
    assert stages._reduce_budget_seconds(120, make_cover=True) == 900 - 120 - 60 - (60 + 300)
    monkeypatch.setattr(stages.cfg, "INGEST_STAGE_TIMEOUT_FINALIZE", 100)    # 몫이 마감을 넘으면 하한
    assert stages._reduce_budget_seconds(120, make_cover=False) == 60
    assert stages._reduce_budget_seconds(120, make_cover=True) == 60


def test_finalize_reserves_the_longest_final_call_and_the_cover(monkeypatch):
    """run_finalize 가 예산 계산에 넘기는 몫: 논문은 요약·소개글 중 긴 타임아웃에 표지 없음, 도서류는 줄거리·독후 효과까지
    보고(함께 나가는 호출 중 가장 긴 것), 표지를 만들 때만(skip_cover 없음) 표지 몫을 뺀다."""
    _fix_timeouts(monkeypatch, book=100, intro=110, plot=130, read_effect=90)
    seen = []
    real = stages._reduce_budget_seconds

    def spy(final_call_seconds, make_cover):
        seen.append((final_call_seconds, make_cover))
        return real(final_call_seconds, make_cover)

    monkeypatch.setattr(stages, "_reduce_budget_seconds", spy)

    _patch(monkeypatch, _book("paper"))
    stages.run_finalize(StageContext(book_id="B1", params={}))
    _patch(monkeypatch, _book("book"))
    stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    _patch(monkeypatch, _book("book"))
    stages.run_finalize(StageContext(book_id="B1", params={}))

    assert seen == [(110, False), (130, False), (130, True)]


def test_reduce_over_budget_falls_back_without_waiting(monkeypatch, caplog):
    """계층 요약이 시간 예산을 넘기면 끊고 combined_text=None(각자 균등 샘플링)으로 이어 간다 — 경고를 남기고,
    끊기기 전까지의 기록과 함께 reduce_fallback 이 meta 에 실린다."""
    monkeypatch.setattr(stages.cfg, "INGEST_STAGE_TIMEOUT_FINALIZE", 0)
    monkeypatch.setattr(stages, "_REDUCE_MIN_BUDGET_SECONDS", 0.2)          # 예산 = 하한 0.2초
    state = _patch(monkeypatch, _book("paper"), reduce_delay=30, reduce_run=(1, 4))
    caplog.set_level(logging.WARNING, logger="services.ingestion.stages")

    t0 = time.monotonic()
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))

    assert time.monotonic() - t0 < 10                                        # 30초 응답을 기다리지 않았다
    assert state["reduce_cancelled"] is True                                 # 계층 요약 호출은 끊겼다
    assert state["combined"] == [None, None]
    assert result["summary"] is True and result["introduction"] is True      # 마무리는 그대로 끝난다
    assert result["reduce_fallback"] is True
    assert (result["reduce_levels"], result["reduce_groups"]) == (1, 4)
    assert any("시간 예산" in r.getMessage() for r in caplog.records)


def test_reduce_within_budget_is_not_cut(monkeypatch):
    """예산 안에 끝나면 그대로 쓴다 — 느린 대역도 예산(여기서는 720초)보다 훨씬 짧으면 폴백하지 않는다."""
    _fix_timeouts(monkeypatch)
    state = _patch(monkeypatch, _book("paper"), reduce_delay=0.1)
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["combined"] == [COMBINED] * 2 and result["reduce_fallback"] is False
    assert state["reduce_cancelled"] is False


# ── 실행 기록(meta) — 카나리에서 섹션 40개 넘는 문서가 계층 요약을 탔는지 SQL 로 센다 ───────────────
def test_reduce_stats_are_returned_for_meta(monkeypatch):
    _patch(monkeypatch, _book("paper"), reduce_run=(2, 9))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert (result["reduce_levels"], result["reduce_groups"], result["reduce_fallback"]) == (2, 9, False)


def test_reduce_keys_are_always_present_even_without_summaries(monkeypatch):
    """섹션 요약이 없어 계층 요약을 안 불러도 키는 0·False 로 늘 실려, 이전 실행의 값이 meta 에 남지 않는다."""
    state = _patch(monkeypatch, _book("paper"), summaries=[])
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert "reduce_args" not in state and state["calls"] == []
    assert (result["reduce_levels"], result["reduce_groups"], result["reduce_fallback"]) == (0, 0, False)


def _real_reduce_setup(monkeypatch, chat, *, cap=1000):
    """진짜 reduce_section_summaries 를 거치도록 요약 모듈 설정·프롬프트·LLM 대역을 바꾼다."""
    class _Cfg:
        SUMMARIZER_MAX_INPUT_CHARS = cap
        SUMMARIZER_BOOK_TIMEOUT = 240
        LLM_SECTION_CONCURRENCY = 4

    class _Tpl:
        parser = "plain"
        params = {"max_tokens": 2048}

        def render(self, **kw):
            return ("sys", f"user::{kw['section_summaries']}", dict(self.params))

    monkeypatch.setattr(summarizer, "get_settings", lambda: _Cfg())
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", lambda name, doc_type=None: _Tpl())
    monkeypatch.setattr(summarizer, "_chat_completion", chat)


def test_real_reduce_stats_reach_the_returned_meta(monkeypatch):
    """가짜가 아니라 진짜 reduce_section_summaries 를 거쳐도 실행 기록이 반환 meta 까지 온다(상한을 넘은 문서)."""
    summaries = [f"섹션요약{i:03d} " + "가" * 80 for i in range(40)]

    async def chat(system, user, params, timeout):
        return "중간요약"

    state = _patch(monkeypatch, _book("paper"), summaries=summaries, real_reduce=True)
    _real_reduce_setup(monkeypatch, chat)
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))

    assert result["reduce_levels"] == 1 and result["reduce_groups"] >= 2 and result["reduce_fallback"] is False
    assert all(c.startswith("[섹션 1~") and "중간요약" in c for c in state["combined"])


def test_real_reduce_group_failure_is_reported_as_fallback(monkeypatch):
    """중간 요약 묶음이 실패해 reduce 안에서 균등 샘플링으로 돌아간 것도 reduce_fallback 으로 meta 에 남는다."""
    summaries = [f"섹션요약{i:03d} " + "가" * 80 for i in range(40)]

    async def chat(system, user, params, timeout):
        raise RuntimeError("LLM 다운")

    state = _patch(monkeypatch, _book("paper"), summaries=summaries, real_reduce=True)
    _real_reduce_setup(monkeypatch, chat)
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))

    assert result["reduce_fallback"] is True and result["reduce_levels"] == 1
    assert state["combined"] == [summarizer._combine_sections(summaries)] * 2    # 샘플링 입력으로 마무리했다
    assert result["summary"] is True and result["introduction"] is True


def test_real_reduce_over_budget_cancels_in_flight_llm_calls(monkeypatch):
    """느린 LLM 대역 + 짧은 예산: 진짜 reduce 를 시간 예산이 끊으면 나가 있던 중간 요약 호출이 모두 취소되고,
    마무리는 균등 샘플링 입력(None)으로 이어서 끝난다."""
    summaries = [f"섹션요약{i:03d} " + "가" * 80 for i in range(40)]
    llm = {"started": 0, "cancelled": 0}

    async def slow_chat(system, user, params, timeout):
        llm["started"] += 1
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            llm["cancelled"] += 1
            raise
        return "중간요약"

    monkeypatch.setattr(stages.cfg, "INGEST_STAGE_TIMEOUT_FINALIZE", 0)
    monkeypatch.setattr(stages, "_REDUCE_MIN_BUDGET_SECONDS", 0.2)             # 예산 = 하한 0.2초
    state = _patch(monkeypatch, _book("paper"), summaries=summaries, real_reduce=True)
    _real_reduce_setup(monkeypatch, slow_chat)

    t0 = time.monotonic()
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))

    assert time.monotonic() - t0 < 10                                          # 30초 응답을 기다리지 않았다
    assert llm["started"] > 0 and llm["cancelled"] == llm["started"]           # 나가 있던 호출은 모두 취소됐다
    assert state["combined"] == [None, None]
    assert result["reduce_fallback"] is True and result["reduce_levels"] == 1
    assert result["summary"] is True and result["introduction"] is True
