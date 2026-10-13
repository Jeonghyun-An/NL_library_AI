"""test_book_chat_prompt.py — 딥리드 대화의 시스템 프롬프트 고르기(services/chat/book_chat.chat_prompt, round06e).

논문(doc_type paper)은 book_chat.paper.yaml, 그 밖(책·문학·정책·doc_type 없음)은 기본 book_chat.yaml 이다. 연구 화면의
오른쪽 딥리드(D24)가 논문에 책 문구('전담 독서 도우미'·'이 책에서는')를 내던 것을 고친다(spec §12-11 권고 채택). 참고문헌
의도 질문('인용'·'출처' 등)이 BookOut 에 없는 extra 를 읽어 끊기던 것도 고친다(_book_references) — 목록이 없으면 청크
검색으로 돌아간다. 두 갈음은 stream_book_chat 을 LLM(httpx)·청크 검색 대역 위에서 돌려 스트림 길에서도 고정한다.

book_chat 은 임베딩(FlagEmbedding)·Milvus(pymilvus)를 물고 오는 embedder·indexer 를 머리에서 import 한다 — 로컬 venv
에는 둘 다 없어(test_book_chat.py 는 그래서 수집 오류다) 미설치일 때만 더미를 꽂고 새로 import 한다. 더미와 새로 올린
모듈은 끝나면 import 전 그대로 되돌린다(test_search_chunk_answer_flag.py 의 _stubbed_pipeline 과 같은 방식) — 뒤에 도는
test_embed_index_guard.py 등이 더미에 묶인 embedder·indexer 를 물려받지 않게.
"""
import asyncio
import importlib
import json
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


def _fake_llm(monkeypatch, book_chat, reply):
    """LLM 스트리밍 대역 — book_chat.httpx.AsyncClient 를 갈아 stream() 이 받은 payload 를 적어 두고 reply 를 SSE 줄로
    흘려 준다. 적은 payload 목록을 돌려준다."""
    payloads = []

    class _Response:
        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            yield f"data: {json.dumps({'choices': [{'delta': {'content': reply}}]}, ensure_ascii=False)}"
            yield "data: [DONE]"

    class _Stream:
        async def __aenter__(self):
            return _Response()

        async def __aexit__(self, *exc):
            return False

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            payloads.append(kwargs["json"])
            return _Stream()

    monkeypatch.setattr(book_chat.httpx, "AsyncClient", _Client)
    return payloads


def _fake_search(monkeypatch, book_chat, hits):
    """청크 검색 대역 — 임베딩한 질의와 검색의 문서 거르기를 적어 두고 hits 를 돌려준다."""
    calls = SimpleNamespace(embedded=[], filters=[])

    def embed_texts(texts, is_query=False):
        calls.embedded.extend(texts)
        return [[0.0]], [{}]

    def search_chunks(dense, sparse, top_k, book_filter=None):
        calls.filters.append(book_filter)
        return hits

    monkeypatch.setattr(book_chat, "embed_texts", embed_texts)
    monkeypatch.setattr(book_chat, "search_chunks", search_chunks)
    return calls


def _stream(book_chat, *args, **kwargs) -> list[str]:
    async def collect():
        return [chunk async for chunk in book_chat.stream_book_chat(*args, **kwargs)]
    return asyncio.run(collect())


def _events(chunks: list[str]) -> list[dict]:
    return [json.loads(c[len("data: "):]) for c in chunks if c != "data: [DONE]\n\n"]


def _paper(**fields) -> BookOut:
    return BookOut(id=uuid.uuid4(), cnts_id="KCI_1", title="노인 우울 연구", personal_author="김철수", pub_date="2019",
                   created_at=datetime(2026, 10, 1, tzinfo=timezone.utc), doc_type="paper", **fields)


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


def test_a_reference_question_streams_with_the_paper_prompt_and_its_references(book_chat, monkeypatch):
    # stream_book_chat 안의 두 갈음(chat_prompt·_book_references)을 스트림 길에서 고정한다 — 옛 식은 논문에 책 문구를
    # 냈고, 참고문헌 의도 질문은 (book.extra or {}) 의 AttributeError 로 첫 조각 전에 끊었다. 목록이 있으면 청크 검색
    # (임베딩·Milvus)을 건너뛰고 목록을 [이 논문의 참고문헌 목록] 으로 넘긴다
    hit = book_chat.SearchHit(chunk_id="c1", book_id="KCI_1", chunk_idx=0, section_idx=0,
                              text="표본은 노인 300명이다.", page_start=3, page_end=4, score=0.9)
    searched = _fake_search(monkeypatch, book_chat, [hit])
    payloads = _fake_llm(monkeypatch, book_chat, "김(2019)과 이(2020)를 인용합니다.")

    chunks = _stream(book_chat, "KCI_1", "이 논문의 참고문헌은?", [], book=_paper(references=["김(2019)", "이(2020)"]))

    assert chunks[-1] == "data: [DONE]\n\n"
    assert _events(chunks) == [{"text": "김(2019)과 이(2020)를 인용합니다."}]   # 오류 글·출처 칩 없음
    system, user = payloads[0]["messages"][0], payloads[0]["messages"][-1]
    assert system["role"] == "system"
    assert system["content"].startswith('당신은 논문 "노인 우울 연구" (김철수, 2019) 의 전담 읽기 도우미입니다.')
    assert user == {"role": "user",
                    "content": "[이 논문의 참고문헌 목록]\n1. 김(2019)\n2. 이(2020)\n\n[질문]\n이 논문의 참고문헌은?"}
    # 이 길의 user 메시지에는 [참고 내용]·쪽이 없다 — 시스템 규칙이 이 블록 이름을 근거로 대야 '근거 없음'으로 답하지 않는다
    assert "[이 논문의 참고문헌 목록]" in system["content"]
    assert searched.embedded == [] and searched.filters == []


def test_a_reference_question_without_references_falls_back_to_the_chunk_search(book_chat, monkeypatch):
    # 참고문헌을 뽑지 못한 논문·책(목록이 늘 비어 있다)에 '출처'·'인용'이 든 질문 — 목록이 없으면 청크 검색으로 돌아가
    # [참고 내용] 을 근거로 답하고 출처 칩도 온다. 전에는 검색을 건너뛴 채 질문만 보내 근거도 출처 칩도 없는 답이 나왔다
    hit = book_chat.SearchHit(chunk_id="c1", book_id="KCI_1", chunk_idx=0, section_idx=0,
                              text="표본은 노인 300명이다.", page_start=3, page_end=4, score=0.9)
    searched = _fake_search(monkeypatch, book_chat, [hit])
    payloads = _fake_llm(monkeypatch, book_chat, "p.3–4 에 나옵니다.")

    chunks = _stream(book_chat, "KCI_1", "이 표본의 출처가 어디야?", [], book=_paper())

    assert searched.embedded == ["이 표본의 출처가 어디야?"] and searched.filters == ["KCI_1"]
    assert payloads[0]["messages"][-1]["content"] == (
        "[참고 내용]\n[p.3–4]\n표본은 노인 300명이다.\n\n[질문]\n이 표본의 출처가 어디야?")
    assert _events(chunks) == [
        {"text": "p.3–4 에 나옵니다."},
        {"sources": [{"page_start": 3, "page_end": 4, "text": "표본은 노인 300명이다."}]},
    ]


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
