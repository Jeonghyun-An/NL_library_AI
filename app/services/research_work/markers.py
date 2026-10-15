"""markers.py — 계획서·주제 카드 글의 마커·숫자·단정 표현 검사 (순수 함수, spec §5-5 '검증', 06b 계획 정함 3)

- [E#] 인용: 딥리서치 보고서와 같은 규칙(services/research/citations.bind_markers)으로 그 절의 입력 번호만
  남기고 cnts_id 로 바꿔 cites 에 싣는다. 근거 표시 없는 문장 수(unmarked)도 그 함수가 센다 — [F#] 만 있는
  문장도 '근거 표시 없음'이다.
- [F#] 수치: 코드가 센 값(figure)만 쓴다. [E#] 와 같은 괄호 문법(citations.normalize_markers — 묶음·범위·전각·
  소문자·0패딩)으로 읽어 입력에 있는 번호만 표준형 [F#] 로 남기고, 없는 번호·못 읽은 표기는 지운다(check_figures).
  괄호 안이 마커 문법으로만 된 것만 [F#] 로 본다 — '[F1-score]'·'[F1 점수 0.92]' 는 글로 남는다.
  생성 글(절·문단 다시 쓰기)은 그 뒤 [F#] 를 수치 자리 밖에 쓴 문장 — 단위·조사 없이 떨어졌거나 근거 표기 자리에
  붙었거나 [E#] 없이 수치 목록 이름표를 옮긴 문장 — 을 통째로 지운다(drop_misplaced_figures, 2026-10-14 운영).
  사용자가 고친 글은 아니다.
- [E#]·[F#] 밖에 쓴 숫자는 '확인 필요'로 센다(numbers_outside). 이름에 붙은 숫자(COVID-19·B2B·5G·WHO-5)는
  세지 않는다. 같은 규칙을 프론트 utils/figureMarkers.ts 가 쓰고, 두 쪽 테스트가 공용 고정 예제
  frontend/tests/fixtures/marker_checks.json 을 함께 읽는다.
- 소장 코퍼스 밖을 단정하는 표현('연구가 없다'·'전무하다'·'최초로')은 "소장 코퍼스에서 확인하지 못했다" 투로
  바꾼다(soften_claims) — 이 시스템은 소장 KCI 적재분만 보았다(spec §4 시연 정직성).
- 소장 코퍼스 범위를 말하는 문장('코퍼스'·'소장 논문/자료/문헌' 낱말이 든 문장)의 '…않음을 확인했다'·'…확인되었다'
  단정은 '…것으로 보인다(소장 코퍼스에서 확인하지 않은 공백 후보)' 투로 바꾼다(06e — 06b 이월 §7-13). 확인 검색을
  거치지 않은 공백이라 '확인했다' 고 쓸 수 없다. 인용한 발견('김(2015)[E1]은 … 확인되었다')은 문맥 낱말이 없어 그대로다
  — 위 규칙이 바꿔 넣은 '소장 코퍼스에서 확인…' 의 '코퍼스'는 문맥으로 보지 않는다. '않(았)음을/없(었)음을 확인' 밖의
  단정은 바로 앞이 결핍 말('부족함을'·'전무한 것으로'·'공백이'·'없음이')일 때만 바꾼다 — 코퍼스 문장의 긍정 단정('다수
  확인되었다')은 그대로. 결핍 말의 부정('부족하지 않은'·'적지 않음을')·'다르지 않음을'·'없' 으로 끝나는 합성어('다름없는'·
  '변함없음')도 결핍이 아니라 그대로다. 공백 후보 말(GAP_NOTE)을 이미 쓴 문장은 단정만 바꾸고 꼬리를 또 붙이지 않는다.
  남는 한계: 코퍼스 문장 안의 효과 없음 결과('소장 논문을 분석한 결과 성별 간 차이가 없음을 확인했다')는 결핍 단정과
  같은 꼴이라 공백 후보로 바뀐다 — 주어(연구·논문)로 좁히면 '다룬 것이 없음을'·'아직까지 없음을' 같은 결핍 단정을 놓친다.
"""
import re
from typing import NamedTuple

from services.research.citations import bind_markers, normalize_markers
from services.research_work.shapes import GAP_NOTE

FIGURE_MARKER = re.compile(r"\[F(\d+)\]")                    # 검사를 거친 표준형
_ANY_MARKER = re.compile(r"\[[EF]\d+\]")
_NUMBER = re.compile(r"(?<![A-Za-z0-9.\-])\d+(?:[.,]\d+)*(?![A-Za-z0-9])")

_ABSENT = r"(?:없다|없었다|없는 실정이다|없는 상황이다|전무하다|전무한 실정이다|전무한 상황이다)"
_ADVERBS = r"(?:(?:거의|아직|전혀)\s*)*"
# (정규식, 바꿀 말) — 앞에서부터 차례로 바꾼다. 바꾼 글에는 다시 걸리는 말이 없다(두 번 거쳐도 같다).
CLAIM_REWRITES: tuple[tuple[str, str], ...] = (
    # '…연구가 없다'·'…논의는 전무하다' — 대상을 살려 목적어로
    (rf"(\S*(?:연구|논의|검토))(?:가|는|도)\s*{_ADVERBS}{_ABSENT}", r"\1를 소장 코퍼스에서 확인하지 못했다"),
    # '…은 연구되지 않았다'·'다뤄지지 않았다'
    (rf"{_ADVERBS}(?:연구되지|다루어지지|다뤄지지|논의되지)\s*(?:않았다|않고 있다|않는다)",
     "소장 코퍼스에서 확인되지 않았다"),
    # 그 밖의 '전무하다'
    (rf"{_ADVERBS}전무(?:하다|한 실정이다|한 상황이다)", "소장 코퍼스에서 확인되지 않았다"),
    # '최초로'·'최초의'
    (r"최초로", "소장 코퍼스에서 확인한 범위에서 처음으로"),
    (r"최초의", "소장 코퍼스에서 확인한 범위에서 첫"),
)
_REWRITES = tuple((re.compile(pattern), repl) for pattern, repl in CLAIM_REWRITES)

# 연구 공백 단정(06e) — 이 낱말이 든 문장에서만 바꾼다. '분석한 결과·검토한 결과' 는 선행연구 요약에도 흔해 문맥으로 쓰지 않는다
GAP_CLAIM_CONTEXT = re.compile(r"(?:코퍼스|소장\s*(?:학술논문|논문|자료|문헌))")
GAP_CLAIM_TAIL = f"({GAP_NOTE})"
# 문장 끝 단정만 — 뒤에 한글이 이어지면('확인되었다는 점') 바꾸지 않는다
_CONFIRMED = r"(?:확인했다|확인하였다|확인할 수 있었다|알 수 있었다)(?![가-힣])"
# 결핍을 말하는 말 — ①② 는 그 자체가 부정('않음을'·'않았음을'·'없음을'·'없었음을')이지만 ③~⑤ 의 '함을 확인'·
# '것으로 확인되었다'·'확인되었다' 는 일반 서술어라, 단정 바로 앞이 이 말일 때만 바꾼다. 코퍼스 문장의 긍정 단정('연구는
# 다수 확인되었다'·'유의함을 확인하였다')과 대조 문장의 긍정 쪽('…드물고 도시 노인 연구가 주로 확인되었다')은 그대로다.
# '전무한 것으로 확인되었다'는 CLAIM_REWRITES 의 '전무하다'·'전무한 실정이다' 꼴이 아니라 여기서 잡는다
_LACK_STEMS = ("부족", "미흡", "미비", "불충분", "희소", "빈약", "미진")
_LACK_STEM = rf"(?:{'|'.join(_LACK_STEMS)})"
# '않음을'·'않은' 바로 앞이 결핍(·작음) 말의 부정이면 결핍이 아니다 — '부족하지 않은'·'적지 않음을' 은 넉넉하다는 말,
# '다르지 않음을' 은 같다는 말이다. 뒤보기는 고정 길이라 낱말마다 띄어 쓴 꼴·붙여 쓴 꼴을 따로 건다
_NEGATED_LACK = (*(f"{stem}하" for stem in _LACK_STEMS), "미미하", "희박하", "전무하", "제한적이", "불과하", "모자라",
                 "드물", "적", "작", "낮", "없", "어렵", "그치", "다르")
_NOT_NEGATED_LACK = "".join(rf"(?<!{word}지 )(?<!{word}지)" for word in _NEGATED_LACK)
# '없' 은 낱말 첫머리일 때만 결핍이다 — '다름없는'·'틀림없는'·'끊임없는'·'변함없음' 은 같다(·늘 그렇다)는 말
_NONE = r"(?<![가-힣])없"
_LACK_ADNOMINAL = (rf"(?:{_LACK_STEM}한|전무한|미미한|희박한|찾아보기\s*어려운|제한적인|드문|적은|{_NONE}는|"
                   rf"{_NOT_NEGATED_LACK}않은|불과한|그치는)")
_LACK_NOUN = rf"(?:공백|부재|결여|{_NONE}음|{_LACK_STEM}함?)"
# (정규식, 바꿀 말) — 앞에서부터 차례로. 바꾼 글('…것으로 보인다(…확인하지 않은 공백 후보)')에는 다시 걸리는 말이 없다
GAP_CLAIM_REWRITES: tuple[tuple[str, str], ...] = (
    (rf"{_NOT_NEGATED_LACK}않(?:았)?음을\s*{_CONFIRMED}", f"않은 것으로 보인다{GAP_CLAIM_TAIL}"),
    (rf"{_NONE}(?:었)?음을\s*{_CONFIRMED}", f"없는 것으로 보인다{GAP_CLAIM_TAIL}"),
    (rf"({_LACK_STEM})함을\s*{_CONFIRMED}", rf"\1한 것으로 보인다{GAP_CLAIM_TAIL}"),
    (rf"({_LACK_ADNOMINAL}\s*)것(?:으로|이)\s*확인(?:되었다|됐다)(?![가-힣])", rf"\1것으로 보인다{GAP_CLAIM_TAIL}"),
    (rf"({_LACK_NOUN}(?:이|가)\s*)확인(?:되었다|됐다)(?![가-힣])", rf"\1보인다{GAP_CLAIM_TAIL}"),
)
_GAP_REWRITES = tuple((re.compile(pattern), repl) for pattern, repl in GAP_CLAIM_REWRITES)
# 공백 후보 말(GAP_NOTE)을 이미 쓴 문장 — 연구 공백 프롬프트가 이 말로 쓰라고 시킨다. 단정만 바꾸고 꼬리는 붙이지 않는다
_GAP_REWRITES_NO_TAIL = tuple((pattern, repl.removesuffix(GAP_CLAIM_TAIL)) for pattern, repl in _GAP_REWRITES)
# 문장 경계 — 마침표·물음표·느낌표 뒤 공백(그 사이에 붙은 마커 묶음 '…했다.[E1] ' 도 경계에 넣는다), 또는 줄바꿈
# (문장부호 없이 끝난 줄). 나눈 자리는 그대로 다시 잇는다(split 의 잡는 괄호)
_SENTENCE_BREAK = re.compile(r"((?<=[.!?。])(?:\s*\[[EF]\d+\])*\s+|\s*\n\s*)")
# CLAIM_REWRITES 가 넣는 말 — 이 말의 '코퍼스'는 문맥으로 보지 않는다(인용 발견이 공백 후보로 바뀌지 않게, 두 번 거쳐도 같게)
_CLAIM_INSERTS = re.compile(r"소장 코퍼스에서 확인(?:하지 못했다|되지 않았다|한 범위에서)")
# drop_misplaced_figures 의 문장 경계 — _SENTENCE_BREAK 와 같되 마침표 뒤에서 앞 문장에 붙이는 마커는 [E#] 뿐이다.
# 인용은 앞 주장에 붙지만 [F#] 는 문장 안의 값이라, 마침표 뒤의 '[F1] 발행 연도는 …' 은 뒤 문장의 첫머리다
_FIGURE_SENTENCE_BREAK = re.compile(r"((?<=[.!?。])(?:\s*\[E\d+\])*\s+|\s*\n\s*)")
# 그 경계를 '앞 문장에 붙은 [E#] 묶음'과 '공백'으로 가른다
_BREAK_PARTS = re.compile(r"((?:\s*\[E\d+\])*)(\s*)")
# 수치 자리 밖의 [F#] — 바로 뒤에 한글(단위·조사)이 없다: 값이 문장에서 떨어졌거나('[F1] 발행 연도는')·근거 표기처럼
# 문장 끝에 붙었거나('…달한다 [F3].')·나열했다('[F1], [F2]')
_LOOSE_FIGURE = re.compile(r"\[F\d+\](?![가-힣])")
_CITATION = re.compile(r"\[E\d+\]")
# 수치 목록의 이름표 낱말 — 절 수치(section_input.section_figures: '이 절에 준 논문 수'·'발행 연도 범위')와 이전 입력의
# '소장 KCI 적재분 논문 수'. [E#] 없이 이 말과 [F#] 를 함께 쓴 문장은 목록을 옮긴 것이다('KCI 적재분 논문 수는 [F3]건에 달한다.')
_FIGURE_LABEL_WORDS = re.compile(r"이\s*절에\s*준|논문\s*수|적재분|발행\s*연도|연도\s*범위")


class FigureResult(NamedTuple):
    text: str
    used: list[str]          # 등장 순서·중복 제거한 유효 번호
    dropped: list[str]       # 입력에 없는 번호(나올 때마다)
    unparsed: list[str] = []  # 마커 문법으로만 됐지만 번호를 읽을 수 없는 괄호("[F1 F2]")


def figure(id: str, label: str, value) -> dict:
    """수치 하나 — 화면 칩·Word 가 [F#] 를 이 값 글자로 바꾼다."""
    return {"id": id, "label": label, "value": str(value)}


def check_figures(text: str, valid_ids: set[str]) -> FigureResult:
    """[F#] 를 검사한다 — bind_markers 의 [E#] 와 같은 괄호 문법이다. 묶음 [F1, F2]·범위 [F1-F2]·전각 ［F1］·
    소문자 [f1]·0패딩 [F01] 은 유효한 번호만 표준형 [F1] [F2] 로 다시 쓰고, 입력에 없는 번호와 읽지 못한 표기([F1 F2])는
    앞 공백과 함께 지운다. [E#]·[표 1] 같은 다른 괄호와 마커 문법 밖의 글이 섞인 괄호([F1-score]·[F2 세대])는 그대로
    둔다(세지 않는다)."""
    cleaned, used, dropped, unparsed = normalize_markers(text, valid_ids, "F")
    return FigureResult(cleaned, used, dropped, unparsed)


def numbers_outside(text: str) -> list[str]:
    """[E#]·[F#] 밖에 쓴 숫자(등장 순). 영문자·숫자·점·하이픈에 붙은 숫자는 이름의 일부로 보고 세지 않는다."""
    return _NUMBER.findall(_ANY_MARKER.sub("", text))


def soften_claims(text: str) -> tuple[str, int]:
    """소장 코퍼스 밖을 단정하는 표현을 바꾸고, 소장 코퍼스 범위를 말하는 문장의 연구 공백 단정을 공백 후보 투로
    바꾼다. (바꾼 글, 바꾼 수)."""
    total = 0
    for pattern, repl in _REWRITES:
        text, n = pattern.subn(repl, text)
        total += n
    parts = _SENTENCE_BREAK.split(text)
    for i in range(0, len(parts), 2):            # 짝수 자리가 문장, 홀수 자리가 나눈 공백
        # 문맥은 위에서 바꿔 넣은 말을 뺀 문장에서 본다 — 원문에 코퍼스 낱말이 있던 문장만 공백 단정으로 다룬다
        sentence = _CLAIM_INSERTS.sub("", parts[i])
        if not GAP_CLAIM_CONTEXT.search(sentence):
            continue
        # 공백 후보 말을 이미 쓴 문장에는 꼬리를 또 붙이지 않는다(한 문장에 같은 말이 두 번 서지 않게)
        rewrites = _GAP_REWRITES_NO_TAIL if GAP_NOTE in sentence else _GAP_REWRITES
        for pattern, repl in rewrites:
            parts[i], n = pattern.subn(repl, parts[i])
            total += n
    return "".join(parts), total


def drop_misplaced_figures(text: str) -> tuple[str, int]:
    """생성 글에서 [F#] 를 수치 자리 밖에 쓴 문장을 지운다 → (고친 글, 지운 문장에 있던 [F#] 수).

    ① [F#] 바로 뒤에 한글(단위·조사)이 없는 문장, ② [E#] 없이 수치 목록의 이름표('이 절에 준'·'논문 수'·'적재분'·
    '발행 연도'·'연도 범위')를 옮긴 문장을 마침표 뒤에 붙은 근거 표기('…편이다. [E2]' 의 [E2])와 함께 지운다.
    운영(2026-10-14)에서 논문 1편만 받은 절의 gemma 가 수치 목록('이 절에 준 논문 수: 1' 같은 시스템 수치)을 문장으로
    옮겨 '[F1] 발행 연도는 [F2]년이다'·'…[F3]건에 달한다 [F3].' 를 썼고, 화면은 그 자리에 값 칩을 그렸다.
    [E#] 만 빠뜨린 집계 문장('이 묶음의 선행연구 [F1]편은 [F2]년에 발표되었다.')은 프롬프트가 [F#] 를 쓰라는 바로 그
    자리라 지우지 않는다 — 근거 표시 없는 문장(unmarked)으로 셀 뿐이다. 받는 글은 검사(check_paragraph)를 거친
    표준형이다. 절 생성·문단 다시 쓰기(section.make_paragraph)만 쓴다 — 사용자가 고친 글(PUT)은 지우지 않는다.
    한계: '[F2] 사이'처럼 띄어 쓴 단위도 ①에 걸린다(프롬프트가 단위를 표기 바로 뒤에 붙이게 한다).
    """
    if not FIGURE_MARKER.search(text):
        return text, 0
    parts = _FIGURE_SENTENCE_BREAK.split(text)
    kept: list[str] = []
    removed = 0
    for i in range(0, len(parts), 2):            # 짝수 자리가 문장, 홀수 자리가 나눈 자리
        tail, space = _BREAK_PARTS.fullmatch(parts[i + 1]).groups() if i + 1 < len(parts) else ("", "")
        sentence = parts[i] + tail
        if FIGURE_MARKER.search(sentence) and (
                _LOOSE_FIGURE.search(sentence)
                or (not _CITATION.search(sentence) and _FIGURE_LABEL_WORDS.search(sentence))):
            removed += len(FIGURE_MARKER.findall(sentence))
            continue
        kept.append(sentence + space)
    if not removed:
        return text, 0
    return "".join(kept).strip(), removed


def check_paragraph(text: str, *, valid_e: set[str], valid_f: set[str],
                    evidence: dict[str, str]) -> tuple[str, list[str], dict]:
    """문단 하나를 검사한다 → (고친 글, cites, ParagraphChecks).

    bind_markers(틀린 [E#] 지우기) → check_figures(틀린 [F#] 지우기) → soften_claims 순. cites 는 남은 [E#] 의
    cnts_id(첫 등장 순, 중복 없이). ParagraphChecks = {"dropped": 지운 [E#](없는 번호 + 못 읽은 표기),
    "dropped_f": 지운 [F#](없는 번호 + 못 읽은 표기), "unmarked": 근거 표시 없는 문장 수, "numbers": [F#] 밖 숫자, "softened": 바꾼 표현 수}.
    """
    marked = bind_markers(text, valid_e)
    figures = check_figures(marked.text, valid_f)
    softened, n_softened = soften_claims(figures.text)
    cites: list[str] = []
    for eid in marked.used:
        cnts_id = evidence.get(eid)
        if cnts_id is not None and cnts_id not in cites:
            cites.append(cnts_id)
    checks = {
        "dropped": len(marked.dropped) + len(marked.unparsed),
        "dropped_f": len(figures.dropped) + len(figures.unparsed),
        "unmarked": marked.unmarked,
        "numbers": numbers_outside(softened),
        "softened": n_softened,
    }
    return softened, cites, checks
