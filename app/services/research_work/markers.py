"""markers.py — 계획서·주제 카드 글의 마커·숫자·단정 표현 검사 (순수 함수, spec §5-5 '검증', 06b 계획 정함 3)

- [E#] 인용: 딥리서치 보고서와 같은 규칙(services/research/citations.bind_markers)으로 그 절의 입력 번호만
  남기고 cnts_id 로 바꿔 cites 에 싣는다. 근거 표시 없는 문장 수(unmarked)도 그 함수가 센다 — [F#] 만 있는
  문장도 '근거 표시 없음'이다.
- [F#] 수치: 코드가 센 값(figure)만 쓴다. 입력에 없는 번호는 지운다(check_figures).
- [E#]·[F#] 밖에 쓴 숫자는 '확인 필요'로 센다(numbers_outside). 이름에 붙은 숫자(COVID-19·B2B·5G·WHO-5)는
  세지 않는다. 같은 규칙을 프론트 utils/figureMarkers.ts 가 쓰고, 두 쪽 테스트가 공용 고정 예제
  frontend/tests/fixtures/marker_checks.json 을 함께 읽는다.
- 소장 코퍼스 밖을 단정하는 표현('연구가 없다'·'전무하다'·'최초로')은 "소장 코퍼스에서 확인하지 못했다" 투로
  바꾼다(soften_claims) — 이 시스템은 소장 KCI 적재분만 보았다(spec §4 시연 정직성).
"""
import re
from typing import NamedTuple

from services.research.citations import bind_markers

FIGURE_MARKER = re.compile(r"\[F(\d+)\]")
_FIGURE_WITH_SPACE = re.compile(r"([ \t]*)\[F(\d+)\]")      # 지울 때는 앞 공백과 함께(bind_markers 와 같다)
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


class FigureResult(NamedTuple):
    text: str
    used: list[str]          # 등장 순서·중복 제거한 유효 번호
    dropped: list[str]       # 입력에 없는 번호(나올 때마다)


def figure(id: str, label: str, value) -> dict:
    """수치 하나 — 화면 칩·Word 가 [F#] 를 이 값 글자로 바꾼다."""
    return {"id": id, "label": label, "value": str(value)}


def check_figures(text: str, valid_ids: set[str]) -> FigureResult:
    """[F#] 를 검사한다. 0패딩은 정수로 읽어 표준형 [F#] 로, 입력에 없는 번호는 앞 공백과 함께 지운다."""
    used: list[str] = []
    dropped: list[str] = []

    def _check(m: re.Match) -> str:
        fid = f"F{int(m.group(2))}"
        if fid not in valid_ids:
            dropped.append(fid)
            return ""
        if fid not in used:
            used.append(fid)
        return f"{m.group(1)}[{fid}]"

    return FigureResult(_FIGURE_WITH_SPACE.sub(_check, text).strip(), used, dropped)


def numbers_outside(text: str) -> list[str]:
    """[E#]·[F#] 밖에 쓴 숫자(등장 순). 영문자·숫자·점·하이픈에 붙은 숫자는 이름의 일부로 보고 세지 않는다."""
    return _NUMBER.findall(_ANY_MARKER.sub("", text))


def soften_claims(text: str) -> tuple[str, int]:
    """소장 코퍼스 밖을 단정하는 표현을 바꾼다. (바꾼 글, 바꾼 수)."""
    total = 0
    for pattern, repl in _REWRITES:
        text, n = pattern.subn(repl, text)
        total += n
    return text, total


def check_paragraph(text: str, *, valid_e: set[str], valid_f: set[str],
                    evidence: dict[str, str]) -> tuple[str, list[str], dict]:
    """문단 하나를 검사한다 → (고친 글, cites, ParagraphChecks).

    bind_markers(틀린 [E#] 지우기) → check_figures(틀린 [F#] 지우기) → soften_claims 순. cites 는 남은 [E#] 의
    cnts_id(첫 등장 순, 중복 없이). ParagraphChecks = {"dropped": 지운 [E#](없는 번호 + 못 읽은 표기),
    "dropped_f": 지운 [F#], "unmarked": 근거 표시 없는 문장 수, "numbers": [F#] 밖 숫자, "softened": 바꾼 표현 수}.
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
        "dropped_f": len(figures.dropped),
        "unmarked": marked.unmarked,
        "numbers": numbers_outside(softened),
        "softened": n_softened,
    }
    return softened, cites, checks
