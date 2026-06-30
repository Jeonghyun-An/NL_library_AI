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


def _format_authors(raw: str) -> str:
    """
    'A;B;C'  또는  'A, B, C'  →  'A, B, C'
    3인 초과 시 한국어: '외', 영문: 'et al.'
    """
    # 세미콜론 분리 우선, 없으면 쉼표 분리
    if ";" in raw:
        names = [n.strip() for n in raw.split(";") if n.strip()]
    else:
        names = [n.strip() for n in raw.split(",") if n.strip()]

    if not names:
        return raw.strip() or "저자 미상"
    return ", ".join(names)


def _format_authors_en(raw: str) -> str:
    if ";" in raw:
        names = [n.strip() for n in raw.split(";") if n.strip()]
    else:
        names = [n.strip() for n in raw.split(",") if n.strip()]

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
    journal     = (book.publisher or "").strip()
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
