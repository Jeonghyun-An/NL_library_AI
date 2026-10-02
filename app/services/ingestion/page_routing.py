"""추출 2티어 라우팅의 페이지 판정 — 순수 함수만 둔다.

fitz·httpx 를 import 하지 않는다. extractor.extract_text 가 fitz 로 구한 쪽별 텍스트를
넘기고, 여기서는 ODL 본문이 짧은 쪽을 OCR 로 보낼지만 정한다.
"""
import math
import re
from collections import Counter

_STRUCT_CHARS = str.maketrans("", "", "|-: \t\n\r")
_BR_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BR_RUN = re.compile(r"(?:<br\s*/?>[ \t]*){3,}", re.IGNORECASE)
_WS = re.compile(r"\s+")
_DIGITS = re.compile(r"\d+")


def body_len(text: str) -> int:
    """[그림] 마커·<br> 태그·표 구조 문자·공백을 뺀 실질 본문 글자 수."""
    if not text:
        return 0
    return len(_BR_TAG.sub("", text.replace("[그림]", "")).translate(_STRUCT_CHARS))


def collapse_br_runs(text: str) -> str:
    """3개 이상 이어진 <br> 를 <br> 하나로 줄인다(1~2개는 표 칸 안 줄바꿈이라 둔다).

    줄바꿈("\\n")으로 바꾸지 않는다 — 표 칸 안 문단 사이의 <br><br><br> 가 마크다운 표 행을 쪼개
    표 추출이 줄어든다(KCI_FI002990049 15→13개).
    """
    return _BR_RUN.sub("<br>", text)


def _line_key(line: str) -> str:
    # 쪽 번호·연도만 다른 머리말·꼬리말을 같은 줄로 보려고 숫자 묶음을 '#' 하나로 접는다.
    return _DIGITS.sub("#", _WS.sub(" ", line).strip())


def repeated_lines(page_texts: list[str], ratio: float, max_len: int = 40) -> set[str]:
    """문서 쪽의 ratio 이상에 되풀이되는 max_len 자 이하 줄의 키(_line_key) 집합.

    한 쪽 안의 중복은 한 번으로 센다. 쪽이 하나뿐이면 되풀이를 판단할 수 없어 빈 집합이다.
    """
    if len(page_texts) < 2:
        return set()
    counts: Counter[str] = Counter()
    for text in page_texts:
        keys = {_line_key(line) for line in text.split("\n")}
        counts.update(k for k in keys if k and len(k) <= max_len)
    need = max(2, math.ceil(len(page_texts) * ratio))
    return {k for k, c in counts.items() if c >= need}


def strip_lines(text: str, lines: set[str]) -> str:
    """repeated_lines 가 돌려준 키에 해당하는 줄을 뺀다."""
    if not lines:
        return text
    return "\n".join(line for line in text.split("\n") if _line_key(line) not in lines)


def is_scan_document(short_flags: list[bool], *, min_pages: int, ratio: float) -> bool:
    """min_pages 쪽 이상 문서에서 짧은 쪽 비율이 ratio 를 넘으면 문서 단위 스캔본이다.

    0쪽 문서나 min_pages <= 0 설정에서도 0 으로 나누지 않는다(쪽이 없으면 스캔본이 아니다).
    """
    if not short_flags or len(short_flags) < min_pages:
        return False
    return sum(short_flags) / len(short_flags) > ratio


def short_page_needs_ocr(
    *,
    fitz_len_stripped: int,
    fitz_len_raw: int,
    doc_is_scan: bool,
    force: bool,
    min_chars: int,
) -> tuple[bool, str]:
    """ODL 본문이 min_chars 미만인 쪽을 OCR 로 보낼지와 그 사유.

    판정 순서: 강제 → fitz 0자(텍스트 층 없음) → 문서 단위 스캔본 → fitz 원래 길이가 min_chars 이상
    (ODL 이 놓친 본문) → 그 밖에는 원래 짧은 쪽이라 ODL 채택.

    비스캔·비강제 문서에서는 옛 코드와 모든 칸이 같다 — 0 < fitz 원래 길이 < min_chars 인 쪽만 ODL 을
    채택하고 나머지는 OCR 한다. 문서 전체가 스캔본(또는 강제)일 때만 그 짧은 쪽도 OCR 로 보낸다 —
    쪽 단위로 보내면 디지털 논문의 이미지 표지·간지가 다시 VLM 을 탄다.

    fitz_len_stripped(되풀이 줄을 뺀 길이)는 문서 단위 스캔 판정(extract_text 의 short_flags)에서만
    쓰고 이 판정에는 쓰지 않는다. 되풀이 줄을 빼면 짧아도 fitz 원래 길이가 길면, ODL 이 이미지 본문 쪽의
    글자를 놓친 것일 수 있어(KCI_FI003011274 1·2·8·9쪽) 옛 규칙대로 OCR 한다. 시그니처만 유지한다.
    """
    if force:
        return True, "강제 OCR(섹션 0개 재추출)"
    if fitz_len_raw == 0:
        return True, "텍스트 층 없음(fitz 0자)"
    if doc_is_scan:
        return True, "스캔본 문서(짧은 쪽 과반)"
    if fitz_len_raw >= min_chars:
        return True, "ODL 이 놓친 본문"
    return False, "원래 짧은 쪽"


def _tail_period(text: str, *, max_unit: int, min_repeats: int, min_span: int) -> tuple[int, int] | None:
    # 끝에서부터 text[i] == text[i + p] 가 이어지는 가장 앞 자리를 주기 p 마다 찾는다.
    # 마지막 반복이 중간에 잘려 있어도(max_tokens 소진) 주기 비교는 그대로 맞는다.
    n = len(text)
    best: tuple[int, int] | None = None
    for p in range(1, min(max_unit, n // min_repeats) + 1):
        i = n - p - 1
        while i >= 0 and text[i] == text[i + p]:
            i -= 1
        start = i + 1
        if n - start >= max(p * min_repeats, min_span) and text[start:start + p].strip():
            if best is None or start < best[0]:
                best = (start, p)
    return best


def trim_repetition(text: str) -> tuple[str, bool]:
    """VLM 이 max_tokens 까지 같은 줄·구절을 되풀이한 꼬리를 걷어 낸다.

    returns (다듬은 텍스트, 퇴화 출력인가). 되풀이는 한 번만 남긴다. 다듬은 뒤 실질 본문이
    20자 미만이거나, 남은 줄(5줄 이상)의 절반 이상이 앞 줄의 되풀이면 퇴화 출력이다.
    """
    found = _tail_period(text, max_unit=200, min_repeats=3, min_span=60)
    trimmed = text[: found[0] + found[1]].rstrip() if found else text.rstrip()
    if body_len(trimmed) < 20:
        return trimmed, True
    lines = [line.strip() for line in trimmed.split("\n") if line.strip()]
    if len(lines) >= 5 and (len(lines) - len(set(lines))) / len(lines) >= 0.5:
        return trimmed, True
    return trimmed, False
