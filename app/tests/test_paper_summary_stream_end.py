"""test_paper_summary_stream_end.py — 논문 스트림 셋(services/search/paper_summary)의 끝.

논문 검색 AI 요약(stream_paper_summary)·관련 논문 비교 사유(stream_related_reason)·논문 상세 AI 요약(stream_paper_reason)
은 LLM 호출이 실패하면(httpx 연결·읽기 오류, 4xx·5xx 응답 등) [DONE] 바로 앞에 {error: <문구>} 를 보낸다 — 소장자료
추천 이유 스트림(pipeline.stream_book_reason 의 REASON_STREAM_ERROR)과 같은 꼴. 전에는 '…오류가 발생했습니다.' 를 보통
{text} 로 흘려 화면이 정상 답처럼 이어 붙이고, 논문 상세 sessionStorage 캐시·논문 검색 기록(ai)에 그대로 저장했다.

글 일부가 이미 나간 뒤 실패해도 {error} 를 보낸다(받은 글은 그대로 둔다). 정상으로 끝난 스트림에는 {error} 가 없다.
LLM 이 글 조각 없이(공백뿐 포함) [DONE] 으로 끝난 빈 답도 같은 {error} 로 끝낸다.
오류는 늘 [DONE] 바로 앞, 마지막 이벤트다. 요약 스트림의 출처(sources)는 LLM 이 아니라 넘겨받은 논문으로 만들어 실패해도
그대로 맞다 — 오류 앞에 보내 화면 오른쪽 참고 논문 칸이 비지 않게 한다(화면은 {error} 에서 읽기를 그만둔다).
"""
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from llm_stream_stub import DONE, delta, events, fake_llm
from services.search import paper_summary

PAPERS = [{"book_id": "KCI_1", "title": "노인 우울 연구", "authors": "김철수", "best_chunk_text": "노인 300명을 조사했다."}]
SOURCES = {"sources": [{"num": 1, "book_id": "KCI_1", "title": "노인 우울 연구", "authors": "김철수"}]}


def _paper():
    return SimpleNamespace(keyword="우울; 노년", themes=None, subject=None, summary=None, title="노인 우울 연구",
                           personal_author="김철수", corporate_author=None, pub_date="2019", publisher=None,
                           series_title=None, grade=None, abstract="노인 우울과 사회적 지지의 관계를 본다.",
                           introduction=None)


def _collect(gen) -> list[str]:
    async def run():
        return [chunk async for chunk in gen]
    return asyncio.run(run())


# (스트림 이름, 부르는 법, 실패 문구 상수, 글보다 먼저 오는 이벤트, 글 뒤·오류 앞에 오는 이벤트)
STREAMS = [
    ("summary", lambda: paper_summary.stream_paper_summary("노인 우울", PAPERS), "SUMMARY_STREAM_ERROR", [], [SOURCES]),
    ("related", lambda: paper_summary.stream_related_reason("원 논문", "초록 가", "연관 논문", "초록 나"),
     "RELATED_REASON_STREAM_ERROR", [], []),
    ("reason", lambda: paper_summary.stream_paper_reason("노인 우울", _paper()), "PAPER_REASON_STREAM_ERROR",
     [{"keywords": ["우울", "노년"]}], []),
]
IDS = [s[0] for s in STREAMS]


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_the_error_phrase_is_a_short_non_empty_constant(name, run, const, lead, tail):
    message = getattr(paper_summary, const)
    assert isinstance(message, str) and message.strip()
    assert "오류가 발생했습니다" not in message


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_a_failed_connection_sends_an_error_event_before_done(monkeypatch, name, run, const, lead, tail):
    fake_llm(monkeypatch, paper_summary, [], open_error=httpx.ConnectError("vLLM 연결 실패"))

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    # 오류 글을 {text} 로 흘리지 않는다
    assert events(chunks) == [*lead, *tail, {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_an_error_status_sends_an_error_event_before_done(monkeypatch, name, run, const, lead, tail):
    # vLLM 이 503 을 돌려주면 본문은 SSE 가 아닌 오류 JSON 이다
    fake_llm(monkeypatch, paper_summary, ['{"object": "error", "message": "Service Unavailable", "code": 503}'],
             status=503)

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [*lead, *tail, {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_a_read_error_after_some_text_keeps_the_text_then_sends_the_error(monkeypatch, name, run, const, lead, tail):
    fake_llm(monkeypatch, paper_summary, [delta("노인 우울은 "), delta("사회적 지지와")],
             read_error=httpx.ReadTimeout("읽기 시간 초과"))

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    got = events(chunks)
    assert got == [*lead, {"text": "노인 우울은 "}, {"text": "사회적 지지와"}, *tail,
                   {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_a_finished_stream_has_no_error_event(monkeypatch, name, run, const, lead, tail):
    fake_llm(monkeypatch, paper_summary, [delta("두 논문은 "), delta("노인 우울을 다룬다."), "data: [DONE]"])

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    got = events(chunks)
    assert not any("error" in e for e in got)
    assert "".join(e.get("text", "") for e in got) == "두 논문은 노인 우울을 다룬다."


def test_a_finished_summary_still_ends_with_its_sources(monkeypatch):
    fake_llm(monkeypatch, paper_summary, [delta("요약 [1]"), "data: [DONE]"])

    got = events(_collect(paper_summary.stream_paper_summary("노인 우울", PAPERS)))

    assert got == [{"text": "요약 [1]"}, SOURCES]


# vLLM 이 생성 도중 실패하면(엔진 오류 등) HTTP 200 스트림 안에 {"error": {...}}(옛 판은 {"object": "error", ...}) 를 보내고
# 이어 [DONE] 을 보낸다 — 이것도 실패다. 전에는 choices 가 없어 난 KeyError 를 삼키고 [DONE] 에서 정상으로 끝나, 받다 만 글이
# 화면 캐시·검색 기록에 완성본으로 저장됐다
ENGINE_ERRORS = [
    'data: {"error": {"object": "error", "message": "EngineDeadError", "type": "InternalServerError", "code": 500}}',
    'data: {"object": "error", "message": "EngineDeadError", "type": "InternalServerError", "code": 500}',
]


@pytest.mark.parametrize("engine_error", ENGINE_ERRORS, ids=["wrapped", "bare"])
@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_an_error_inside_the_stream_sends_an_error_event(monkeypatch, name, run, const, lead, tail, engine_error):
    fake_llm(monkeypatch, paper_summary, [delta("부분 "), engine_error, "data: [DONE]"])

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [*lead, {"text": "부분 "}, *tail, {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_a_stream_closed_without_done_is_a_failure(monkeypatch, name, run, const, lead, tail):
    # 위쪽이 [DONE] 없이 깨끗이 닫아도 끝까지 받은 것이 아니다
    fake_llm(monkeypatch, paper_summary, [delta("부분 ")])

    chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [*lead, {"text": "부분 "}, *tail, {"error": getattr(paper_summary, const)}]


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_the_failure_log_names_the_exception_type_and_the_text_already_sent(monkeypatch, caplog, name, run, const,
                                                                           lead, tail):
    # httpx.ReadTimeout 은 str(e) 가 빈 글일 때가 많다 — 예외 종류와 이미 보낸 글 길이로 원인·시점을 남긴다
    fake_llm(monkeypatch, paper_summary, [delta("노인 우울은 ")], read_error=httpx.ReadTimeout(""))

    with caplog.at_level("ERROR", logger=paper_summary.log.name):
        _collect(run())

    messages = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    assert len(messages) == 1
    assert "ReadTimeout" in messages[0]
    assert "보낸 글 7자" in messages[0]


# LLM 이 글 조각 없이(공백뿐 포함) [DONE] 으로 끝난 빈 답 — 호출은 성공했지만 정상 답으로 끝내지 않고 그 스트림의 같은
# {error} 로 끝낸다(DeepRead 대화의 empty_answer 와 같은 판별). 전에는 [DONE] 만 와 화면이 빈 글을 끝까지 받은 답으로 읽었다
EMPTY_ANSWERS = [
    pytest.param(["data: [DONE]"], id="no-text"),
    # vLLM 의 첫 조각은 역할만 싣고 content 가 빈 글이다 — sse_deltas 가 건너뛴다
    pytest.param(['data: {"choices": [{"delta": {"role": "assistant", "content": ""}}]}', "data: [DONE]"],
                 id="role-only"),
    pytest.param([delta(" "), delta("\n\n"), "data: [DONE]"], id="whitespace-only"),
]


@pytest.mark.parametrize("lines", EMPTY_ANSWERS)
@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_an_empty_answer_ends_with_the_error_event(monkeypatch, caplog, name, run, const, lead, tail, lines):
    fake_llm(monkeypatch, paper_summary, lines)

    with caplog.at_level("WARNING", logger=paper_summary.log.name):
        chunks = _collect(run())

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    got = events(chunks)
    # 받은 공백 조각은 그대로 두고, 그 밖의 이벤트 차례는 실패 때와 같다 — 오류는 [DONE] 바로 앞, 한 번
    assert [e for e in got if "text" not in e] == [*lead, *tail, {"error": getattr(paper_summary, const)}]
    assert "".join(e.get("text", "") for e in got).strip() == ""
    # 연결·응답 실패(ERROR)가 아니라 빈 답 경고로 남긴다
    records = [r for r in caplog.records if r.name == paper_summary.log.name]
    assert [r.levelname for r in records] == ["WARNING"] and "빈 답" in records[0].getMessage()


def _paper_without_content():
    # 초록·요약·해제가 모두 없다 — LLM 에 줄 내용이 없다
    paper = _paper()
    paper.abstract = None
    paper.summary = None
    paper.introduction = None
    return paper


def test_a_paper_without_content_ends_with_the_error_event_without_calling_the_llm(monkeypatch, caplog):
    # 전에는 '논문 내용 정보가 부족하여 분석을 생성할 수 없습니다.' 를 {text} + [DONE] 으로 보내 논문 상세가 정상 요약처럼
    # 그리고 sessionStorage 캐시에 담았다 — 이제 이 스트림의 실패 이벤트로 끝나 화면이 실패로 읽고 담지 않는다
    payloads = fake_llm(monkeypatch, paper_summary, [delta("불리면 안 된다"), "data: [DONE]"])

    with caplog.at_level("WARNING", logger=paper_summary.log.name):
        chunks = _collect(paper_summary.stream_paper_reason("노인 우울", _paper_without_content()))

    assert chunks[-1] == DONE and chunks.count(DONE) == 1
    assert events(chunks) == [{"keywords": ["우울", "노년"]}, {"error": paper_summary.PAPER_REASON_STREAM_ERROR}]
    # LLM 은 부르지 않는다
    assert payloads == []
    # 연결·응답 실패(ERROR)가 아니라 경고로 남긴다
    records = [r for r in caplog.records if r.name == paper_summary.log.name]
    assert [r.levelname for r in records] == ["WARNING"]


@pytest.mark.parametrize("name, run, const, lead, tail", STREAMS, ids=IDS)
def test_leading_whitespace_before_the_text_is_not_an_empty_answer(monkeypatch, name, run, const, lead, tail):
    fake_llm(monkeypatch, paper_summary, [delta("\n"), delta("두 논문은 노인 우울을 다룬다."), delta("\n"), "data: [DONE]"])

    got = events(_collect(run()))

    assert not any("error" in e for e in got)
    assert [e for e in got if "text" not in e] == [*lead, *tail]
