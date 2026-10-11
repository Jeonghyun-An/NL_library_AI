"""framing.py — 시작 질문 넓히기(06c, 잡 파라미터 broaden) — spec §12-2

개념 하나짜리 짧은 질문은 계획 프롬프트의 측면 목록을 그대로 옮겨 일반 틀이 된다(06b 계획 30개 중 약 25개).
계획 전에 gemma 를 한 번 불러 질문을 계획하기 좋은 한 문장으로 넓히고, 연구 범위를 정하는 용어(terms — 검색어
합성 query_context 의 재료)를 뽑는다. 계획 프롬프트(research_plan.yaml)·parse_plan 은 그대로다 — make_plan 에 넘기는
질문만 바뀐다. planner.py 가 아니라 이 모듈에 두는 까닭: 계획 태스크 테스트가 planner 모듈을 통째로 바꿔치기한다.

넓힌 문장은 코드가 검사한다 — 원 질문의 내용어(terms.content_words)가 하나라도 넓힌 문장에 들어 있지 않거나
(terms.contains), 한 글자 어절(암·뇌·법 — content_words 의 2자 바닥에 걸린다, ONE_CHAR_FUNCTION_WORDS 는 빼고)이
하나라도 넓힌 문장에 어절로 있지 않으면(그 글자이거나 그 글자 + 조사 하나 — '방법'의 '법'은 아니다) 원 질문을
쓴다. 모델이 원 질문을 그대로 내도(함정 26) 정상이다 — 이미 구체적인 질문은 그대로 두라고 했다. 입력
이름표('질문:')째 옮겨 낸 답은 이름표를 떼고 본다(함정 26). 원 질문으로 물러나는 것은
FRAME_FAILURES(chat 의 전송·상태·JSON·응답 모양 오류)·빈 응답·검사 실패뿐이고, 그 밖의 예외는 올린다 — 코드 결함·
태스크 제어 예외(SoftTimeLimitExceeded)를 '원문'으로 숨기면 스위치를 켠 판정이 넓히기 없이 나온다(함정 19). 계획
태스크가 그 예외를 계획 실패로 닫는다. 물러날 때마다 [framing] 경고가 정확히 한 줄 남는다 — 판정 뒤 그 줄 수로 센다.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass

import httpx

from services.llm_client import chat
from services.prompts import get_prompt
from services.research.llm_json import extract_json
from services.research.terms import PARTICLES, QUESTION_WORDS, contains, content_words

log = logging.getLogger(__name__)

# 초 — chat 기본 120초를 쓰지 않는다(DeepRead 질의 재작성 BOOK_CHAT_QUERY_REWRITE_TIMEOUT=20 선례).
# chat 의 최악은 이 값 + 연결 10초다(llm_client.chat_full). 잡 데드라인과 섞이지 않게 asyncio.timeout 을 따로 걸지 않는다
BROADEN_TIMEOUT = 20
MAX_TERMS = 4
# 용어는 검색어에 붙는다 — 긴 문장이 용어로 들어오면 검색어가 망가진다
TERM_MAX_CHARS = 30
# api/research.py ResearchCreate.question 의 max_length 와 같다
FRAMED_QUESTION_MAX = 500
# chat 이 실제로 내는 실패 — 전송·상태(httpx.HTTPError), 응답 본문 JSON 해석(ValueError), 응답 모양(KeyError·IndexError)
FRAME_FAILURES = (httpx.HTTPError, ValueError, KeyError, IndexError)
# 넓히기 user 메시지의 이름표(research_frame.yaml '질문: {{ question }}') — 모델이 이름표째 옮겨 내면 낱말 검사를
# 통과하므로 떼고 본다(함정 26). 그대로 두면 계획 입력이 '질문: 질문: …' 이 되고 question_used 에도 실린다
_ECHO_LABEL = re.compile(r"^\s*질문\s*[:：]\s*")
# 한 글자 명사(암·뇌·법·꿈·물·돈)는 terms.content_words 의 2자 바닥에 걸려 내용어가 아니다 — 그대로 두면 '암 연구가
# 궁금해'(내용어 [])에 지어낸 주제를 내도, '암'을 '종양'으로 바꿔도 낱말 검사를 지나간다. 그래서 넓히기 검사만 한 글자
# 어절도 본다(content_words·contains 는 06e·score.py 복사본과 묶인 계약이라 그대로 둔다). 한 글자는 contains(부분
# 문자열)로 보지 않고 어절 경계로 본다 — _has_one_char_word. 아래는 주제가 아니라 문장을
# 잇는 한 글자 말이다 — 넓힌 문장이 다른 말로 바꾸거나('및' → '와') 빼도 주제가 바뀌지 않는다. 목록에 없는 한 글자 말이
# 빠져 원 질문으로 물러나는 것은 안전한 쪽이다(넓히지 않을 뿐이다)
ONE_CHAR_FUNCTION_WORDS: tuple[str, ...] = (
    "및", "등", "왜", "또", "즉", "더", "좀", "그", "각", "수", "것", "때", "중", "할", "한", "될", "된",
)
# terms.content_words 와 같은 어절 나누기 — 문장부호를 공백으로
_PUNCT = re.compile(r"[^\w\s]")


@dataclass(frozen=True)
class Framing:
    question: str        # make_plan 에 넘길 질문 — 넓힌 문장, 넓히지 않았으면 원문 그대로
    terms: list[str]     # 범위 용어(clean_terms) — 넓히지 않았으면 []


def unframed(question: str) -> Framing:
    """넓히지 않은 계획 입력 — 스위치 0·실패·검사 실패가 모두 이 모양이다."""
    return Framing(question, [])


def _squash(text: str) -> str:
    return " ".join(text.split())


def _tokens(text: str) -> list[str]:
    """terms.content_words 와 같은 어절 나누기 — NFKC·casefold 뒤 문장부호를 공백으로 바꿔 나눈다(조사는 떼지 않는다)."""
    return _PUNCT.sub(" ", unicodedata.normalize("NFKC", text or "").casefold()).split()


def _one_char_words(question: str) -> list[str]:
    """원 질문의 한 글자 어절 — _tokens 로 나눈 어절 가운데 한 글자인 것. 조사·질문 꼴 낱말·ONE_CHAR_FUNCTION_WORDS 는
    빼고, 처음 나온 순서대로 중복 없이.

    조사 떼기는 하지 않는다 — terms 는 떼고 남는 것이 2자 미만이면 떼지 않으므로('암이' 는 그대로 내용어다) 한 글자
    낱말은 늘 한 글자 어절 그대로다.
    """
    out: list[str] = []
    for token in _tokens(question):
        if len(token) != 1 or token in PARTICLES or token in QUESTION_WORDS or token in ONE_CHAR_FUNCTION_WORDS:
            continue
        if token not in out:
            out.append(token)
    return out


def _has_one_char_word(framed_tokens: list[str], char: str) -> bool:
    """넓힌 문장의 어절(_tokens) 가운데 char 그대로이거나 char + 조사 하나(PARTICLES — 암의·뇌를·암에서)인 것이 있는가.

    contains(공백 지운 부분 문자열)로 보면 다른 낱말 안에 낀 글자에도 맞는다 — '방법'·'기법'의 '법', '암호화'의 '암',
    '뇌물'의 '뇌' 때문에 지어낸 주제가 지나간다(특히 '법'은 넓힌 문장에 흔히 붙는 '방법'에 늘 들어 있다). 붙여 쓴
    꼴('암환자')·조사 둘('암에서의')은 맞지 않는다 — 원 질문으로 물러나는 안전한 쪽이다(넓히지 않을 뿐이다).
    """
    return any(token == char or (token[:1] == char and token[1:] in PARTICLES) for token in framed_tokens)


def clean_terms(raw: object) -> list[str]:
    """문자열만, NFKC, 공백 정리, 빈 것·TERM_MAX_CHARS 넘는 것 버림, casefold 기준 중복 제거, 앞에서 MAX_TERMS 개.

    개수는 모델에 맡기지 않고 코드가 자른다(함정 15).
    """
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        term = _squash(unicodedata.normalize("NFKC", item))
        if not term or len(term) > TERM_MAX_CHARS or term.casefold() in seen:
            continue
        seen.add(term.casefold())
        out.append(term)
    return out[:MAX_TERMS]


def parse_frame(raw: str | None, question: str) -> Framing | None:
    """넓히기 응답 → Framing. 쓸 수 없으면 None(호출 쪽이 원 질문으로 물러난다).

    JSON 객체를 읽지 못하거나, "question" 이 문자열이 아니거나, 입력 이름표를 떼고 공백 정리한 뒤 비었거나
    FRAMED_QUESTION_MAX 를 넘거나, 원 질문의 내용어가 하나라도 넓힌 문장에 contains 가 아니거나, 한 글자
    어절(_one_char_words)이 하나라도 넓힌 문장의 어절로 있지 않으면(_has_one_char_word) None 이다. 물러나는 까닭마다
    그 자리에서 [framing] 경고를 한 줄 남긴다(frame_question 은 다시 찍지 않는다) — 판정 뒤 낱말 검사에서 떨어진 수를 '[framing] 넓힌 질문이 원 질문 낱말' 줄 수로 센다(한 글자 어절도 같은 줄이다).
    """
    data = extract_json(raw or "")
    if data is None:
        log.warning("[framing] 응답에서 JSON 객체를 읽지 못해 원 질문을 쓴다 — %r", (raw or "")[:120])
        return None
    framed = data.get("question")
    if not isinstance(framed, str):
        log.warning("[framing] 응답의 question 이 없거나 문자열이 아니어서 원 질문을 쓴다 — %r", (raw or "")[:120])
        return None
    framed = _squash(_ECHO_LABEL.sub("", framed))
    if not framed or len(framed) > FRAMED_QUESTION_MAX:
        log.warning("[framing] 넓힌 질문이 비었거나 %d자를 넘어 원 질문을 쓴다", FRAMED_QUESTION_MAX)
        return None
    framed_tokens = _tokens(framed)
    missing = [word for word in content_words(question) if not contains(framed, word)]
    missing += [char for char in _one_char_words(question) if not _has_one_char_word(framed_tokens, char)]
    if missing:
        log.warning("[framing] 넓힌 질문이 원 질문 낱말 %s 를 빠뜨려 원 질문을 쓴다 — %r", missing, framed[:120])
        return None
    return Framing(framed, clean_terms(data.get("terms")))


async def frame_question(question: str) -> Framing:
    """gemma 한 번(모델 인자 없음 = LLM_BASE_URL·LLM_MODEL)으로 질문을 넓힌다. 실패하면 원 질문(unframed)."""
    system, user, llm_params = get_prompt("research_frame").render(question=question)
    try:
        raw = await chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            params=llm_params, timeout=BROADEN_TIMEOUT,
        )
    except FRAME_FAILURES as e:
        log.warning("[framing] 넓히기 호출 실패 — 원 질문으로 계획한다: %s: %s", type(e).__name__, e)
        return unframed(question)
    framed = parse_frame(raw, question)
    if framed is None:
        # 까닭은 parse_frame 이 그 자리에서 한 줄 남겼다 — 여기서 다시 찍으면 한 번 물러난 것이 두 줄로 세진다
        return unframed(question)
    return framed
