"""test_backfill_summary.py — workers.tasks.backfill_summary 테스트.

LLM 생성기(summarizer)와 DB 세션을 목으로 대체해 백필 분기 로직만 검증한다.
celery·redis 는 로컬 환경에 미설치라 workers.tasks import 자체가 이들에 걸려있다 —
설치돼 있지 않은 경우에만 더미를 꽂아 import 를 통과시킨다(설치된 환경은 건드리지 않음).
"""
import importlib
import sys
from unittest.mock import MagicMock

import pytest


def _stub_missing_module(name: str, make_module) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        sys.modules[name] = make_module()


def _make_fake_celery_module():
    class _FakeCeleryApp:
        def __init__(self, *a, **kw):
            self.conf = MagicMock()

        def task(self, *a, **kw):
            # @celery_app.task(...) 는 원본 함수를 그대로 반환해야 실제 로직을 테스트할 수 있다
            def _decorator(fn):
                return fn
            return _decorator

    mod = MagicMock()
    mod.Celery = _FakeCeleryApp
    return mod


_stub_missing_module("celery", _make_fake_celery_module)
_stub_missing_module("redis", MagicMock)

import workers.tasks as tasks  # noqa: E402
from services.ingestion import summarizer  # noqa: E402
from models.book import Book  # noqa: E402


def _async_mock(return_value=None):
    """run_async(coro) 는 실제 이벤트 루프를 돌리므로 진짜 코루틴 함수가 필요하다 —
    호출 기록은 내부 MagicMock 으로 추적한다."""
    inner = MagicMock(return_value=return_value)

    async def _fn(*args, **kwargs):
        return inner(*args, **kwargs)

    _fn.mock = inner
    return _fn


def _make_session(books, section_summaries_by_book_id):
    """db.query(Book)/db.query(BookSection.summary) 두 체인을 인자 종류로 분기하는 세션 목.

    후보 필터(or_/filter) 자체의 SQL 은 실제 DB 없이 검증할 수 없어 대상으로 삼지 않는다
    — books 리스트를 그대로 반환해 이후의 파이썬 레벨 분기(요약·테마·소개글 조건)만 검증한다.
    """
    session = MagicMock()

    def _query(entity):
        m = MagicMock()
        if entity is Book:
            m.filter.return_value = m
            m.limit.return_value.all.return_value = books
        else:
            def _filter_by(**kw):
                chain = MagicMock()
                rows = [(s,) for s in section_summaries_by_book_id.get(kw.get("book_id"), [])]
                chain.order_by.return_value.all.return_value = rows
                return chain
            m.filter_by.side_effect = _filter_by
        return m

    session.query.side_effect = _query
    return session


def test_themes_only_gap_is_backfilled_without_overwriting_summary(monkeypatch):
    """summary·introduction 은 이미 있고 themes 만 비어있는 문서 → themes 만 채워지고
    기존 summary·introduction 은 덮지 않는다(요약 LLM 은 호출되지만 introduction LLM 은
    호출조차 되지 않아야 한다)."""
    book = MagicMock(
        cnts_id="B001", title="제목", personal_author="저자", corporate_author=None,
        doc_type="book", publisher="출판사", pub_date="2020",
        summary="기존 요약", themes=None, introduction="기존 소개글",
    )
    session = _make_session([book], {"B001": ["섹션1 요약", "섹션2 요약"]})
    monkeypatch.setattr(tasks, "SyncSessionLocal", lambda: session)

    fake_summarize = _async_mock(return_value=("새 요약", ["테마1", "테마2"]))
    fake_intro = _async_mock(return_value="새 소개글")
    monkeypatch.setattr(summarizer, "summarize_book_from_sections", fake_summarize)
    monkeypatch.setattr(summarizer, "generate_book_introduction", fake_intro)

    result = tasks.backfill_summary(limit=10, force=False)

    assert book.themes == "테마1, 테마2"
    assert book.summary == "기존 요약", "이미 채워진 summary 는 덮지 않아야 한다"
    fake_summarize.mock.assert_called_once()
    fake_intro.mock.assert_not_called()
    assert result == {"done": 1, "skipped": 0, "failed": 0}


def test_force_false_does_not_overwrite_fully_populated_book(monkeypatch):
    """summary·themes·introduction 이 모두 있으면 force=False 에서 LLM 호출 없이 그대로 둔다."""
    book = MagicMock(
        cnts_id="B002", title="제목", personal_author="저자", corporate_author=None,
        doc_type="book", publisher="출판사", pub_date="2020",
        summary="기존 요약", themes="기존 테마", introduction="기존 소개글",
    )
    session = _make_session([book], {"B002": ["섹션1 요약"]})
    monkeypatch.setattr(tasks, "SyncSessionLocal", lambda: session)

    fake_summarize = _async_mock(return_value=("새 요약", ["새 테마"]))
    fake_intro = _async_mock(return_value="새 소개글")
    monkeypatch.setattr(summarizer, "summarize_book_from_sections", fake_summarize)
    monkeypatch.setattr(summarizer, "generate_book_introduction", fake_intro)

    tasks.backfill_summary(limit=10, force=False)

    fake_summarize.mock.assert_not_called()
    fake_intro.mock.assert_not_called()
    assert book.summary == "기존 요약"
    assert book.themes == "기존 테마"
    assert book.introduction == "기존 소개글"


def test_book_without_section_summaries_is_skipped(monkeypatch):
    """섹션 요약이 전부 비어있는 문서는 LLM 호출 없이 skipped 로 처리된다."""
    book = MagicMock(
        cnts_id="B003", title="제목", personal_author="저자", corporate_author=None,
        doc_type="book", publisher="출판사", pub_date="2020",
        summary=None, themes=None, introduction=None,
    )
    session = _make_session([book], {"B003": [None, "", None]})
    monkeypatch.setattr(tasks, "SyncSessionLocal", lambda: session)

    fake_summarize = _async_mock(return_value=("무시됨", ["무시됨"]))
    fake_intro = _async_mock(return_value="무시됨")
    monkeypatch.setattr(summarizer, "summarize_book_from_sections", fake_summarize)
    monkeypatch.setattr(summarizer, "generate_book_introduction", fake_intro)

    result = tasks.backfill_summary(limit=10, force=False)

    assert result == {"done": 0, "skipped": 1, "failed": 0}
    fake_summarize.mock.assert_not_called()
    fake_intro.mock.assert_not_called()
