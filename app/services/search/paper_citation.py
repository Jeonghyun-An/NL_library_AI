"""
paper_citation.py — 논문 출처 인용 포맷 생성

LLM 없이 BookOut 메타데이터로 국문/영문 인용문을 구성한다.

인용 형식 (KCI 스타일 · APA 기반):
  국문: 저자 (연도). 제목. 학술지명, 권(호), 시작쪽–끝쪽. UCI / URL
  영문: Author (Year). Title. Journal, Vol(Issue), Start–End. UCI / URL
학술지 자리의 권·호·쪽은 있는 것만 싣는다(_journal_part). 보고서 내보내기 참고문헌(frontend/utils/citations.ts
journalText)과 같은 규칙이다 — 두 쪽 테스트가 frontend/tests/fixtures/citation_reference.json 을 함께 읽는다.
"""
import re
from schemas.book import BookOut

# 권호(vol_issue) 운영 값 — 'V(N)'(권(호)), '-N'(권 없이 호만 — KCI 적재가 빈 권 자리를 비워 이은 꼴), 'V'(권만).
# 비었거나 기호뿐이면 없음, 그 밖의 꼴('특별호' 등)은 글 그대로(frontend/utils/citations.ts parseVolIssue 와 같다)
_VOL_ISSUE_BLANK = re.compile(r"^[-–—\s/.,]*$")
_VOL_AND_ISSUE = re.compile(r"^(\d+)\s*\(\s*(\d+)\s*\)$")
_ISSUE_ONLY = re.compile(r"^-\s*(\d+)$")
_VOL_ONLY = re.compile(r"^(\d+)$")
# 수록면(extent) — KCI 적재 값 'S~E'(또는 'S-E'·'S'). 다른 꼴(단행본 형태사항 '352 p.' 등)은 쪽으로 읽지 않는다
_PAGES = re.compile(r"^(\d+)\s*(?:[~\-–—]\s*(\d+))?$")


def _extract_year(pub_date: str) -> str:
    m = re.search(r"\d{4}", pub_date or "")
    return m.group(0) if m else "n.d."


def _reference_vol_issue(raw: str) -> str:
    """권호를 APA 꼴로 — '57(3)'·'(46)'(호만)·'57'(권만). 비었거나 기호뿐이면 빈 글."""
    value = raw.strip()
    if _VOL_ISSUE_BLANK.match(value):
        return ""
    if m := _VOL_AND_ISSUE.match(value):
        return f"{m.group(1)}({m.group(2)})"
    if m := _ISSUE_ONLY.match(value):
        return f"({m.group(1)})"
    if m := _VOL_ONLY.match(value):
        return m.group(1)
    return value


def _reference_pages(raw: str) -> str:
    """수록면을 '77–104'(같은 쪽이면 '23')로. 쪽으로 읽을 수 없으면 빈 글."""
    m = _PAGES.match(raw.strip())
    if not m:
        return ""
    start, end = m.group(1), m.group(2)
    return f"{start}–{end}" if end and end != start else start


def _journal_part(journal: str, vol_issue: str, extent: str) -> str:
    """'학술지, 권(호), 쪽' — 있는 칸만 쉼표로 잇는다. 학술지가 없으면 권·호·쪽도 싣지 않는다(빈 글)."""
    if not journal:
        return ""
    return ", ".join(p for p in (journal, _reference_vol_issue(vol_issue), _reference_pages(extent)) if p)


# 저자 구분자 — 세미콜론·세로줄·가운데점을 쉼표보다 먼저 나눈다. 원본 personal_author 에 '윤기찬 | 이순철' 처럼
# 세로줄로 적힌 논문이 있고, 보고서 참고문헌(frontend/utils/citations.ts splitAuthors)도 같은 셋을 먼저 나눈다
_AUTHOR_SEPARATORS = re.compile(r"[;|·]")


def _split_authors(raw: str) -> list[str]:
    """'A;B' · 'A | B' · 'A·B' · 'A, B' → ['A', 'B']. 세미콜론·세로줄·가운데점이 있으면 그것으로, 없으면 쉼표로."""
    pattern = _AUTHOR_SEPARATORS if _AUTHOR_SEPARATORS.search(raw) else ","
    return [n.strip() for n in re.split(pattern, raw) if n.strip()]


def _format_authors(raw: str) -> str:
    """
    'A;B;C' · 'A | B | C' · 'A·B·C' · 'A, B, C'  →  'A, B, C'
    3인 초과 시 한국어: '외', 영문: 'et al.'
    """
    names = _split_authors(raw)

    if not names:
        return raw.strip() or "저자 미상"
    return ", ".join(names)


def _format_authors_en(raw: str) -> str:
    names = _split_authors(raw)

    if not names:
        return raw.strip() or "Unknown Author"
    if len(names) > 3:
        return f"{names[0]} et al."
    return ", ".join(names)


def build_citation(book: BookOut) -> dict[str, str]:
    """
    국문·영문 인용 문자열을 딕셔너리로 반환.
    {"korean": "...", "english": "..."}
    """
    raw_authors = (book.personal_author or book.corporate_author or "").strip()
    year        = _extract_year(book.pub_date or "")
    title_ko    = (book.title or "").rstrip(".")
    title_en    = (book.title_remainder or book.title or "").rstrip(".")
    # 학술지 = series_title (KCI 논문의 publisher 는 학회 이름이다). 없으면 비운다 — publisher 로 물러나지 않는다
    journal     = _journal_part((book.series_title or "").strip(), book.vol_issue or "", book.extent or "")
    uci         = (book.uci or "").strip()
    url         = (book.url or "").strip()

    # 말미 식별자 (UCI 우선, 없으면 URL)
    identifier = f"UCI {uci}" if uci else url

    # ── 국문 인용 ──────────────────────────────────────
    authors_ko = _format_authors(raw_authors) if raw_authors else "저자 미상"
    ko_parts = [f"{authors_ko} ({year})."]
    ko_parts.append(f"{title_ko}.")
    if journal:
        ko_parts.append(f"{journal}.")
    if identifier:
        ko_parts.append(identifier)

    # ── 영문 인용 (APA) ─────────────────────────────────
    authors_en = _format_authors_en(raw_authors) if raw_authors else "Unknown Author"
    en_parts = [f"{authors_en} ({year})."]
    en_parts.append(f"{title_en}.")
    if journal:
        en_parts.append(f"{journal}.")
    if identifier:
        en_parts.append(identifier)

    return {
        "korean":  " ".join(ko_parts),
        "english": " ".join(en_parts),
    }
