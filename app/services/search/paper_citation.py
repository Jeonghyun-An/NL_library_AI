"""
paper_citation.py — 논문 출처 인용 포맷 생성

LLM 없이 BookOut 메타데이터로 국문/영문 인용문을 구성한다.

인용 형식 (KCI 스타일 · APA 기반):
  국문: 저자 (연도). 제목. 학술지명, 권호. UCI / URL
  영문: Author (Year). Title. Journal, Vol(Issue). UCI / URL
"""
import re
from schemas.book import BookOut


def _extract_year(pub_date: str) -> str:
    m = re.search(r"\d{4}", pub_date or "")
    return m.group(0) if m else "n.d."


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
    journal     = (book.series_title or "").strip()
    vol_issue   = (book.vol_issue or "").strip()
    uci         = (book.uci or "").strip()
    url         = (book.url or "").strip()

    # 말미 식별자 (UCI 우선, 없으면 URL)
    identifier = f"UCI {uci}" if uci else url

    # ── 국문 인용 ──────────────────────────────────────
    authors_ko = _format_authors(raw_authors) if raw_authors else "저자 미상"
    ko_parts = [f"{authors_ko} ({year})."]
    ko_parts.append(f"{title_ko}.")
    if journal:
        ko_parts.append(f"{journal}{', ' + vol_issue if vol_issue else ''}.")
    if identifier:
        ko_parts.append(identifier)

    # ── 영문 인용 (APA) ─────────────────────────────────
    authors_en = _format_authors_en(raw_authors) if raw_authors else "Unknown Author"
    en_parts = [f"{authors_en} ({year})."]
    en_parts.append(f"{title_en}.")
    if journal:
        en_parts.append(f"{journal}{', ' + vol_issue if vol_issue else ''}.")
    if identifier:
        en_parts.append(identifier)

    return {
        "korean":  " ".join(ko_parts),
        "english": " ".join(en_parts),
    }
