"""
MARC21 파서

1차: pymarc (제어문자 복원 후 시도)
2차: 정규식 (엑셀에서 제어문자 소실된 경우 직접 파싱)
"""
import re
import logging
from pymarc import Record

log = logging.getLogger(__name__)


def _restore_control_chars(text: str) -> str:
    """엑셀 이스케이프 제어문자를 원래 바이트로 복원"""
    return re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), text)


# ── pymarc 기반 파싱 ─────────────────────────────────────
def _get(record: Record, tag: str, sub: str) -> str | None:
    field = record.get(tag)
    if not field:
        return None
    return field.get(sub)


def _get_all(record: Record, tag: str, sub: str) -> list[str]:
    return [f.get(sub) for f in record.get_fields(tag) if f.get(sub)]


def _parse_pymarc(marc_raw: str) -> dict | None:
    """pymarc로 파싱 시도"""
    restored = _restore_control_chars(marc_raw.strip())

    for encoding in ["utf-8", "euc-kr", "latin-1"]:
        try:
            record = Record(data=restored.encode(encoding))
            if record.get("245"):
                f008 = record.get("008")
                language = f008.data[35:38].strip() if f008 and len(f008.data) >= 38 else None
                subjects = _get_all(record, "650", "a")
                keywords = _get_all(record, "653", "a")

                return {
                    "record_id":            record.get("001").data.strip() if record.get("001") else None,
                    "last_modified":        record.get("005").data.strip() if record.get("005") else None,
                    "isbn":                 _get(record, "020", "a"),
                    "holdings":             _get(record, "049", "a"),
                    "kdc":                  _get(record, "056", "a"),
                    "ddc":                  _get(record, "082", "a"),
                    "personal_author":      _get(record, "100", "a"),
                    "title":                _get(record, "245", "a"),
                    "title_remainder":      _get(record, "245", "b"),
                    "title_responsibility": _get(record, "245", "d"),
                    "pub_place":            _get(record, "260", "a"),
                    "publisher":            _get(record, "260", "b"),
                    "pub_date":             _get(record, "260", "c"),
                    "extent":               _get(record, "300", "a"),
                    "series_title":         _get(record, "440", "a"),
                    "note":                 _get(record, "500", "a"),
                    "bibliography_note":    _get(record, "504", "a"),
                    "subject":              " | ".join(subjects) if subjects else None,
                    "keyword":              " | ".join(keywords) if keywords else None,
                    "corporate_author":     _get(record, "710", "a"),
                    "price":                _get(record, "950", "a"),
                    "language":             language,
                    "source_format":        "MARC",
                }
        except Exception:
            continue
    return None


# ── 정규식 기반 fallback 파싱 ─────────────────────────────
def _extract_field(text: str, tag: str, sub: str) -> str | None:
    """
    MARC 태그+서브필드를 정규식으로 추출
    예: tag="245", sub="a" → "245...a대외불안 요인과 한국경제/" 에서 "대외불안 요인과 한국경제/"
    """
    # 패턴: 태그 뒤에 서브필드 코드가 나오는 구간 추출
    # 서브필드는 소문자 알파벳 한 글자 + 내용
    pattern = rf'{tag}\d{{0,10}}.*?{sub}([^a-z\d].*?)(?=[a-z]\S|$|\d{{3}})'
    match = re.search(pattern, text)
    if match:
        val = match.group(1).strip()
        # 다음 서브필드나 태그 전까지 자르기
        val = re.split(r'(?<=[^\s])[a-z](?=[A-Z가-힣\d])', val)[0].strip()
        return val if val else None
    return None


def _parse_regex(marc_raw: str) -> dict:
    """제어문자 소실된 MARC 데이터를 정규식으로 파싱"""
    text = marc_raw.strip()

    # record_id: KMO 또는 KMO 패턴
    record_id = None
    m = re.search(r'(KMO\d+)', text)
    if m:
        record_id = m.group(1)

    # 245$a: 제목 — "00a" 또는 "10a" 뒤의 내용, "/" 또는 다음 서브필드 전까지
    title = None
    m = re.search(r'245.{0,20}?[0-9]{0,2}a(.+?)(?:/|$)', text)
    if m:
        title = m.group(1).strip()

    # 245$d: 책임표시 — "/" 뒤
    title_resp = None
    m = re.search(r'245.+?/d?(.+?)(?=\d{3}|260|$)', text)
    if m:
        val = m.group(1).strip()
        if len(val) > 2:
            title_resp = val

    # 260$a: 발행지
    pub_place = None
    m = re.search(r'260.{0,10}?a(.+?):', text)
    if m:
        pub_place = m.group(1).strip()

    # 260$b: 출판사
    publisher = None
    m = re.search(r'260.+?b(.+?),', text)
    if m:
        publisher = m.group(1).strip()

    # 260$c: 발행년
    pub_date = None
    m = re.search(r'260.+?c(\d{4})', text)
    if m:
        pub_date = m.group(1)

    # 056$a: KDC
    kdc = None
    m = re.search(r'056.{0,10}?a([\d.]+)', text)
    if m:
        kdc = m.group(1)

    # 082$a: DDC
    ddc = None
    m = re.search(r'082.{0,10}?a([\d.]+)', text)
    if m:
        ddc = m.group(1)

    # 100$a: 개인 저자
    personal_author = None
    m = re.search(r'100.{0,10}?a(.+?)(?:,|0K|\d{3}|$)', text)
    if m:
        personal_author = m.group(1).strip()

    # 710$a: 단체 저자
    corporate_author = None
    m = re.search(r'710.{0,10}?a(.+?)(?:0K|\d{3}|$)', text)
    if m:
        corporate_author = m.group(1).strip()

    # 020$a: ISBN
    isbn = None
    m = re.search(r'020.{0,10}?a([\d-X]+)', text)
    if m:
        isbn = m.group(1)

    # 650$a: 주제어 (여러 개)
    subjects = re.findall(r'650.{0,10}?(?:\d+)?a(.+?)(?:0K|$|\d{3})', text)
    subjects = [s.strip().rstrip('[]') for s in subjects if s.strip()]

    # 300$a: 형태사항
    extent = None
    m = re.search(r'300.{0,10}?a(.+?)(?:;|b|$)', text)
    if m:
        extent = m.group(1).strip()

    # 언어: 008 영역에서 kor/eng 등 추출
    language = None
    m = re.search(r'\b(kor|eng|jpn|chi)\b', text)
    if m:
        language = m.group(1)

    return {
        "record_id":            record_id,
        "title":                title,
        "title_responsibility": title_resp,
        "personal_author":      personal_author,
        "corporate_author":     corporate_author,
        "publisher":            publisher,
        "pub_place":            pub_place,
        "pub_date":             pub_date,
        "extent":               extent,
        "kdc":                  kdc,
        "ddc":                  ddc,
        "isbn":                 isbn,
        "subject":              " | ".join(subjects) if subjects else None,
        "language":             language,
        "source_format":        "MARC",
    }


# ── 메인 파싱 함수 ───────────────────────────────────────
def parse(marc_raw: str) -> dict:
    """MARC 문자열 파싱 (pymarc → 정규식 fallback)"""
    if not marc_raw or not marc_raw.strip():
        return {}

    # 1차: pymarc
    result = _parse_pymarc(marc_raw)
    if result and result.get("title"):
        return result

    # 2차: 정규식 fallback
    log.info("pymarc 실패, 정규식 fallback 파싱")
    return _parse_regex(marc_raw)