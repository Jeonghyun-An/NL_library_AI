"""test_book_chat_prompt.py — 딥리드 대화의 시스템 프롬프트 고르기(services/chat/book_chat.chat_prompt, round06e).

논문(doc_type paper)은 book_chat.paper.yaml, 그 밖(책·문학·정책·doc_type 없음)은 기본 book_chat.yaml 이다. 연구 화면의
오른쪽 딥리드(D24)가 논문에 책 문구('전담 독서 도우미'·'이 책에서는')를 내던 것을 고친다(spec §12-11 권고 채택). 참고문헌
의도 질문('인용'·'출처' 등)이 BookOut 에 없는 extra 를 읽어 끊기던 것도 고친다(_book_references).

book_chat 은 임베딩(FlagEmbedding)·Milvus(pymilvus)를 물고 오는 embedder·indexer 를 머리에서 import 한다 — 로컬 venv
에는 둘 다 없어(test_book_chat.py 는 그래서 수집 오류다) 미설치일 때만 더미를 꽂고 새로 import 한다. 더미와 새로 올린
모듈은 끝나면 import 전 그대로 되돌린다(test_search_chunk_answer_flag.py 의 _stubbed_pipeline 과 같은 방식) — 뒤에 도는
test_embed_index_guard.py 등이 더미에 묶인 embedder·indexer 를 물려받지 않게.
"""
import importlib
import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from schemas.book import BookOut

_HEAVY = ("FlagEmbedding", "pymilvus")
_CACHED = ("services.chat.book_chat", "services.ingestion.embedder", "services.ingestion.indexer")
VARS = {"title": "노인 우울 연구", "author": "김철수", "pub_date": ", 2019", "summary": "요약", "themes": "우울, 지지"}


def _stubbed_book_chat(monkeypatch):
    """더미 위에서 book_chat 을 새로 import 해 넘기고, 끝나면 import 전 그대로 되돌린다.

    monkeypatch.delitem 은 원래 없던 키를 되돌릴 목록에 올리지 않는다 — 여기서 새로 import 한 모듈(더미 pymilvus 에
    묶인 indexer 등)은 직접 빼고, 원래 있던 항목·부모 패키지 속성은 monkeypatch 가 되돌리게 둔다."""
    for name in _HEAVY:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            monkeypatch.setitem(sys.modules, name, MagicMock())
    for name in _CACHED:
        parent, _, child = name.rpartition(".")
        if hasattr(sys.modules.get(parent), child):
            monkeypatch.delattr(sys.modules[parent], child)
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield importlib.import_module("services.chat.book_chat")
    for name in _CACHED:
        module = sys.modules.pop(name, None)
        parent, _, child = name.rpartition(".")
        if module is not None and getattr(sys.modules.get(parent), child, None) is module:
            delattr(sys.modules[parent], child)


@pytest.fixture
def book_chat(monkeypatch):
    yield from _stubbed_book_chat(monkeypatch)


def test_a_paper_gets_the_paper_prompt(book_chat):
    system, user, params = book_chat.chat_prompt(SimpleNamespace(doc_type="paper")).render(**VARS)

    assert system.startswith('당신은 논문 "노인 우울 연구" (김철수, 2019) 의 전담 읽기 도우미입니다.')
    assert "[논문 요약]\n요약" in system and "이 논문에서는 다루지 않습니다" in system
    assert user == "" and params == {"max_tokens": 10000, "temperature": 0.3}


def test_a_book_or_a_missing_doc_type_gets_the_base_prompt(book_chat):
    base = book_chat.get_prompt("book_chat").render(**VARS)[0]
    assert "전담 독서 도우미" in base

    # 변형이 없는 종류(문학·정책)·빈 값·속성이 없는 객체(옛 호출부)는 모두 기본으로 물러난다
    for book in (SimpleNamespace(doc_type="book"), SimpleNamespace(doc_type="literature"),
                 SimpleNamespace(doc_type=None), SimpleNamespace(doc_type=""), SimpleNamespace()):
        assert book_chat.chat_prompt(book).render(**VARS)[0] == base


def test_book_references_reads_the_book_out_field(book_chat):
    # 참고문헌 의도('인용'·'출처' 등)일 때 읽는 목록 — 대화 엔드포인트가 넘기는 BookOut 에는 extra 가 없고 references 가
    # extra["references"] 를 싣는다. 옛 식 (book.extra or {}) 는 AttributeError 로 스트림을 끊었다
    at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    paper = BookOut(id=uuid.uuid4(), cnts_id="KCI_1", title="노인 우울 연구", created_at=at,
                    references=["김(2019)", "이(2020)"])
    assert book_chat._book_references(paper) == ["김(2019)", "이(2020)"]
    assert book_chat._book_references(BookOut(id=uuid.uuid4(), cnts_id="B1", title="책", created_at=at)) == []
    # 속성이 없거나 None 이어도 빈 목록이다
    assert book_chat._book_references(SimpleNamespace()) == []
    assert book_chat._book_references(SimpleNamespace(references=None)) == []


def test_loader_leaves_sys_modules_as_it_found_them():
    snapshot = {name: sys.modules.get(name) for name in _CACHED}
    with pytest.MonkeyPatch.context() as mp:
        loader = _stubbed_book_chat(mp)
        next(loader)
        next(loader, None)
    assert {name: sys.modules.get(name) for name in _CACHED} == snapshot


def test_book_out_carries_doc_type():
    # 대화 엔드포인트(api/book.py chat_with_book)는 BookRepository.get_by_cnts_id 의 BookOut 을 넘긴다 — ORM 의
    # doc_type 이 실려야 chat_prompt 가 고른다. 없으면 None(옛 서지)
    at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    row = SimpleNamespace(id=uuid.uuid4(), cnts_id="KCI_1", title="노인 우울 연구", created_at=at, doc_type="paper")
    assert BookOut.model_validate(row).doc_type == "paper"
    assert BookOut(id=uuid.uuid4(), cnts_id="B1", title="책", created_at=at).doc_type is None
