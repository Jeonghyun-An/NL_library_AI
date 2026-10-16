"""test_book_chat_errors.py — DeepRead 대화 스트림(services/chat/book_chat.stream_book_chat)의 그 밖의 실패.

LLM 호출 실패({error: CHAT_STREAM_ERROR})는 test_book_chat_stream_end.py 가 본다. 여기는 같은 {error} 이벤트 꼴(문자열 error
키)에 code 를 더한 셋이다 — 모두 [DONE] 바로 앞, 마지막 이벤트다.
- not_found: 대화할 자료가 서지에 없다 → {"error": "자료를 찾을 수 없어요", "code": "not_found"}. 전에는 '도서를 찾을 수
  없습니다.' 를 보통 {text} 로 흘려 화면이 답처럼 대화에 남겼다.
- retrieval_failed: 청크 검색(임베딩·Milvus)이 실패했다 → {"error": "자료 내용을 읽지 못했어요. 잠시 뒤 다시 시도해 주세요",
  "code": "retrieval_failed"}. 전에는 로그만 남기고 근거 없이 질문만 LLM 에 보내 답을 지어냈다 — 이제 LLM 을 부르지 않는다.
- empty_answer: LLM 이 글 조각 없이 [DONE] 으로 끝났다 → {"error": "답을 만들지 못했어요", "code": "empty_answer"}. 전에는
  빈 답이 정상 답으로 남았다.

book_chat 을 더미 embedder·indexer 위에서 올리는 픽스처는 test_book_chat_prompt.py 의 것을 그대로 쓴다.
"""
import asyncio

import pytest

from llm_stream_stub import DONE, delta, events, fake_llm
from test_book_chat_prompt import _fake_search, _paper, book_chat  # noqa: F401 — book_chat 은 픽스처


def _stream(book_chat, message="이 논문의 대상은?", *, book="paper") -> list[str]:
    target = _paper() if book == "paper" else book

    async def collect():
        return [chunk async for chunk in book_chat.stream_book_chat("KCI_1", message, [], book=target)]
    return asyncio.run(collect())


@pytest.fixture
def hit(book_chat):
    return book_chat.SearchHit(chunk_id="c1", book_id="KCI_1", chunk_idx=0, section_idx=0,
                               text="표본은 노인 300명이다.", page_start=3, page_end=4, score=0.9)


def _failing_search(monkeypatch, book_chat, *, embed_error=None, search_error=None):
    calls = {"embed": 0, "search": 0}

    def embed_texts(texts, is_query=False):
        calls["embed"] += 1
        if embed_error is not None:
            raise embed_error
        return [[0.0]], [{}]

    def search_chunks(dense, sparse, top_k, book_filter=None):
        calls["search"] += 1
        if search_error is not None:
            raise search_error
        return []

    monkeypatch.setattr(book_chat, "embed_texts", embed_texts)
    monkeypatch.setattr(book_chat, "search_chunks", search_chunks)
    return calls


class TestNotFound:
    def test_missing_book_is_an_error_event_not_text(self, book_chat, monkeypatch):
        payloads = fake_llm(monkeypatch, book_chat, [delta("x"), "data: [DONE]"])
        chunks = _stream(book_chat, book=None)
        assert chunks[-1] == DONE and chunks.count(DONE) == 1
        assert events(chunks) == [{"error": "자료를 찾을 수 없어요", "code": "not_found"}]
        assert payloads == []                       # LLM 을 부르지 않는다


class TestRetrievalFailed:
    RETRIEVAL = {"error": "자료 내용을 읽지 못했어요. 잠시 뒤 다시 시도해 주세요", "code": "retrieval_failed"}

    def test_milvus_failure_ends_without_calling_the_llm(self, book_chat, monkeypatch):
        exceptions = pytest.importorskip("pymilvus.exceptions")
        calls = _failing_search(monkeypatch, book_chat,
                                search_error=exceptions.MilvusException(code=2, message="Fail connecting to server"))
        payloads = fake_llm(monkeypatch, book_chat, [delta("근거 없는 답"), "data: [DONE]"])

        chunks = _stream(book_chat)

        assert chunks[-1] == DONE and chunks.count(DONE) == 1
        assert events(chunks) == [self.RETRIEVAL]
        assert payloads == []                       # 근거 없이 답하지 않는다
        assert calls == {"embed": 1, "search": 1}

    @pytest.mark.parametrize("exc", [RuntimeError("CUDA out of memory"), ConnectionRefusedError(111, "refused")],
                             ids=lambda e: type(e).__name__)
    def test_embedding_failure_ends_the_same_way(self, book_chat, monkeypatch, exc):
        calls = _failing_search(monkeypatch, book_chat, embed_error=exc)
        payloads = fake_llm(monkeypatch, book_chat, [delta("근거 없는 답"), "data: [DONE]"])

        chunks = _stream(book_chat)

        assert events(chunks) == [self.RETRIEVAL]
        assert payloads == [] and calls == {"embed": 1, "search": 0}

    def test_the_failure_is_logged_with_its_stack(self, book_chat, monkeypatch, caplog):
        _failing_search(monkeypatch, book_chat, search_error=TimeoutError("deadline"))
        fake_llm(monkeypatch, book_chat, [])
        with caplog.at_level("ERROR", logger=book_chat.log.name):
            _stream(book_chat)
        records = [r for r in caplog.records if r.levelname == "ERROR" and r.name == book_chat.log.name]
        assert len(records) == 1 and records[0].exc_info is not None
        assert "TimeoutError" in records[0].getMessage()

    def test_a_search_with_no_chunks_is_not_a_failure(self, book_chat, monkeypatch):
        # 검색은 됐는데 청크가 0개(본문 미적재) — 지금처럼 서지·요약만으로 답한다
        _failing_search(monkeypatch, book_chat)
        payloads = fake_llm(monkeypatch, book_chat, [delta("요약에 따르면 노인 우울을 다룹니다."), "data: [DONE]"])

        chunks = _stream(book_chat)

        assert events(chunks) == [{"text": "요약에 따르면 노인 우울을 다룹니다."}]
        assert payloads[0]["messages"][-1]["content"] == "이 논문의 대상은?"

    def test_a_reference_question_with_references_skips_retrieval(self, book_chat, monkeypatch):
        # 참고문헌 목록으로 답하는 길은 청크 검색을 하지 않는다 — 검색 장애가 이 길을 막지 않는다
        calls = _failing_search(monkeypatch, book_chat, search_error=RuntimeError("Milvus down"))
        fake_llm(monkeypatch, book_chat, [delta("김(2019)을 인용합니다."), "data: [DONE]"])

        chunks = _stream(book_chat, "이 논문의 참고문헌은?", book=_paper(references=["김(2019)"]))

        assert events(chunks) == [{"text": "김(2019)을 인용합니다."}]
        assert calls == {"embed": 0, "search": 0}


class TestEmptyAnswer:
    EMPTY = {"error": "답을 만들지 못했어요", "code": "empty_answer"}

    def test_done_without_any_text_is_an_empty_answer(self, book_chat, monkeypatch, hit):
        _fake_search(monkeypatch, book_chat, [hit])
        fake_llm(monkeypatch, book_chat, ["data: [DONE]"])

        chunks = _stream(book_chat)

        assert chunks[-1] == DONE and chunks.count(DONE) == 1
        assert events(chunks) == [self.EMPTY]       # 출처 칩도 없다

    def test_whitespace_only_is_an_empty_answer(self, book_chat, monkeypatch, hit):
        _fake_search(monkeypatch, book_chat, [hit])
        fake_llm(monkeypatch, book_chat, [delta("\n"), delta("  "), "data: [DONE]"])

        chunks = _stream(book_chat)

        assert events(chunks)[-1] == self.EMPTY
        assert all("sources" not in e for e in events(chunks))

    def test_a_real_answer_is_not_flagged(self, book_chat, monkeypatch, hit):
        _fake_search(monkeypatch, book_chat, [hit])
        fake_llm(monkeypatch, book_chat, [delta("p.3–4 에 나옵니다."), "data: [DONE]"])

        chunks = _stream(book_chat)

        assert all("error" not in e for e in events(chunks))
