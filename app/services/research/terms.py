"""terms.py — 한국어 낱말 맞추기·검색어 합성(06c) — spec §12-2

넓히기 검사(framing)·검색어 합성(runner)·일반 틀 비율(scripts/research_eval/score.py)이 한국어 낱말을 같은
방식으로 나누고 맞춘다. 어절째 대조하면 '노인의'↔'노인' 같은 조사 차이로 넓히기가 거의 늘 원문으로 떨어진다.
06e 의 제목 키워드 일치(topic_card)도 이 contains 를 그대로 import 한다 — 같은 규칙을 따로 두지 않는다.
score.py 는 app 을 import 하지 않아 contains 복사본을 둔다. 복사본·06e 화면과 이 모듈은 공용 고정 예제
(frontend/tests/fixtures/term_checks.json)로 묶는다 — 규칙을 바꾸면 예제를 함께 고치고 양쪽 테스트가 통과해야 한다.

표준 라이브러리만 쓴다(순수 함수 — DB·LLM·설정 없음).
"""
import re
import unicodedata
from collections.abc import Sequence

# 어절 끝에서 떼는 조사(처음 값 — spec §12-2). 맞는 것 중 가장 긴 것 하나만 뗀다('으로'를 '로'보다 먼저)
PARTICLES: tuple[str, ...] = (
    "에서", "에게", "으로", "로", "의", "은", "는", "이", "가", "을", "를", "와", "과", "에", "도", "만",
)
# 질문 꼴 낱말 — 연구 주제가 아니라 묻는 말이라 내용어로 세지 않는다
QUESTION_WORDS: tuple[str, ...] = (
    "연구", "관한", "대한", "관련", "궁금해", "궁금합니다", "알려줘", "찾아줘", "무엇", "어떻게",
)
# 검색어에서 글자 그대로 지우는 군더더기. D18 계획 프롬프트가 하위질문에 붙이게 된 말이다(06b 이월 §7-12) —
# 하위질문 글(절 소제목)은 그대로 두고 검색어에서만 뗀다
QUERY_FILLERS: tuple[str, ...] = ("국내 학술논문에서",)

# 문장부호를 공백으로 — '궁금해?'·논문 버튼 꼴(「…」에서, 가·나 관련)이 어절째 원문으로 떨어지지 않게
_PUNCT = re.compile(r"[^\w\s]")
_BY_LENGTH = sorted(PARTICLES, key=len, reverse=True)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _strip_particle(token: str) -> str:
    """어절 끝 조사 하나를 뗀다. 떼고 남은 것이 2자 미만이면 떼지 않는다('제도'의 '도'는 조사가 아니다)."""
    for particle in _BY_LENGTH:
        if token.endswith(particle):
            stem = token[: -len(particle)]
            return stem if len(stem) >= 2 else token
    return token


def tokens(text: str) -> list[str]:
    """어절 나누기 — NFKC·casefold 뒤 문장부호를 공백으로 바꿔 공백으로 나눈다(조사는 떼지 않는다).

    content_words 와 넓히기의 한 글자 어절 검사(framing)가 같은 나누기를 쓴다 — 규칙을 한 곳에 둔다.
    """
    return _PUNCT.sub(" ", _normalize(text or "")).split()


def content_words(text: str) -> list[str]:
    """내용어 — NFKC·casefold, 문장부호는 공백(tokens), 어절 끝 조사 하나를 떼고, 2자 이상·질문 꼴 낱말 아님·
    조사만 남은 어절 아님. 처음 나온 순서대로 중복 없이."""
    out: list[str] = []
    for token in tokens(text):
        word = _strip_particle(token)
        if len(word) < 2 or word in QUESTION_WORDS or word in PARTICLES or word in out:
            continue
        out.append(word)
    return out


def contains(text: str, word: str) -> bool:
    """text 에 word 가 들어 있는가 — NFKC·casefold·공백 제거 뒤 부분 문자열이거나, word 의 낱말이 모두
    순서대로 들어 있으면 참. word 가 비면(공백 제거 뒤) 거짓.

    공백을 지우고 보므로 '다문화 가정'↔'다문화가정'·'재무 성과'↔'재무성과' 가 맞고, 낱말을 차례로 찾으므로
    '노인의 우울'에 '노인 우울'이 맞는다(조사가 사이에 끼어도 된다). 순서가 바뀌면 맞지 않는다.
    """
    pieces = _normalize(word or "").split()
    if not pieces:
        return False
    flat = "".join(_normalize(text or "").split())
    if "".join(pieces) in flat:
        return True
    pos = 0
    for piece in pieces:
        found = flat.find(piece, pos)
        if found < 0:
            return False
        pos = found + len(piece)
    return True


def compose_query(text: str, terms: Sequence[str]) -> str:
    """검색어 합성(잡 파라미터 query_context 1) — QUERY_FILLERS 를 글자 그대로 지우고 공백을 정리한 뒤, terms 가운데
    지금까지의 글에 contains 가 아닌 용어만 차례로 ' ' 로 이어 붙인다(이어 붙인 용어도 다음 비교에 든다).

    군더더기를 지우고 남는 것이 없으면 text 의 공백만 정리한 글로 물러난다. 제외할 뜻은 붙이지 않는다 — terms 만
    붙인다(dense 검색은 부정을 몰라 오히려 그 논문을 끌어온다). 합성한 글을 다시 넣어도 같은 글이 나온다(군더더기만으로
    된 글이 물러난 경우는 빼고) — 재검색 제안이 앞 검색어(이미 합성한 글)를 고쳐 쓴 것이어도 용어가 두 번 붙지 않는다.
    """
    query = text
    for filler in QUERY_FILLERS:
        query = query.replace(filler, " ")
    query = " ".join(query.split()) or " ".join(text.split())
    for term in terms:
        term = " ".join(term.split())
        if term and not contains(query, term):
            query = f"{query} {term}"
    return query
