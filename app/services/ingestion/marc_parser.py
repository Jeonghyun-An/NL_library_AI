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


def _to_marc_bytes(text: str) -> bytes:
    """
    MARC ISO 2709 바이너리 인코딩.

    문제: .encode('utf-8')은 U+001E → 0xC2 0x9E (2바이트),
          U+001F → 0xC2 0x9F (2바이트)로 변환해
          pymarc가 필드/서브필드 경계를 인식하지 못함.

    해결: 제어문자(0x00–0x1F)는 단일 바이트 그대로 유지,
          한글 등 다국어 문자는 UTF-8 멀티바이트 인코딩.
    """
    result = bytearray()
    for ch in text:
        cp = ord(ch)
        if cp <= 0x1F:      # 제어문자: 단일 바이트 (0x1E=필드종결, 0x1F=서브필드구분)
            result.append(cp)
        elif cp < 0x80:     # ASCII: 단일 바이트
            result.append(cp)
        else:               # 한글 등 다국어: UTF-8 멀티바이트
            result.extend(ch.encode("utf-8"))
    return bytes(result)


def _clean_sub(val: str | None) -> str | None:
    """MARC 관행상 붙는 후행 구두점 제거 (예: '박학사,' → '박학사')"""
    if not val:
        return None
    return val.strip().rstrip(' ,./;:')


def _clean_date(val: str | None) -> str | None:
    """발행년 필드에서 4자리 연도만 추출 ('2020.' → '2020', '[2020]' → '2020')"""
    if not val:
        return None
    m = re.search(r'(\d{4})', val)
    return m.group(1) if m else val.strip()


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

    try:
        # 제어문자(U+001E/1F)를 단일 바이트로 올바르게 인코딩
        # .encode('utf-8')은 U+001E → 0xC2 0x9E(2바이트)로 변환해 pymarc가 실패함
        marc_bytes = _to_marc_bytes(restored)
        record = Record(data=marc_bytes)
        if not record.get("245"):
            return None

        f008 = record.get("008")
        language = f008.data[35:38].strip() if f008 and len(f008.data) >= 38 else None
        subjects = _get_all(record, "650", "a")
        keywords = _get_all(record, "653", "a")

        # ── 출판 정보: AACR2(260) 우선, 없으면 RDA(264) ──────────
        publisher = _clean_sub(_get(record, "260", "b") or _get(record, "264", "b"))
        pub_place = _clean_sub(_get(record, "260", "a") or _get(record, "264", "a"))
        pub_date  = _clean_date(_get(record, "260", "c") or _get(record, "264", "c"))

        # ── 개인 저자: 100(주 표목) + 700(추가 표목) 모두 수집 ──
        personal_authors: list[str] = []
        main_pa = _clean_sub(_get(record, "100", "a"))
        if main_pa:
            personal_authors.append(main_pa)
        for v in _get_all(record, "700", "a"):
            cleaned = _clean_sub(v)
            if cleaned:
                personal_authors.append(cleaned)

        # ── 단체 저자: 110(주 표목) 우선, 없으면 710(추가 표목) ──
        corporate_author = _clean_sub(
            _get(record, "110", "a") or _get(record, "710", "a")
        )

        return {
            "record_id":            record.get("001").data.strip() if record.get("001") else None,
            "last_modified":        record.get("005").data.strip() if record.get("005") else None,
            "isbn":                 _clean_sub(_get(record, "020", "a")),
            "holdings":             _get(record, "049", "a"),
            "kdc":                  _clean_sub(_get(record, "056", "a")),
            "ddc":                  _clean_sub(_get(record, "082", "a")),
            "personal_author":      " | ".join(personal_authors) if personal_authors else None,
            "title":                _clean_sub(_get(record, "245", "a")),
            "title_remainder":      _clean_sub(_get(record, "245", "b")),
            "title_responsibility": _get(record, "245", "c") or _get(record, "245", "d"),
            "pub_place":            pub_place,
            "publisher":            publisher,
            "pub_date":             pub_date,
            "extent":               _clean_sub(_get(record, "300", "a")),
            "series_title":         _clean_sub(
                                        _get(record, "440", "a") or _get(record, "490", "a")
                                    ),
            "note":                 _get(record, "500", "a"),
            "bibliography_note":    _get(record, "504", "a"),
            "subject":              " | ".join(subjects) if subjects else None,
            "keyword":              " | ".join(keywords) if keywords else None,
            "corporate_author":     corporate_author,
            "price":                _get(record, "950", "a"),
            "language":             language,
            "source_format":        "MARC",
        }
    except Exception:
        return None


# ── 정규식 기반 fallback 파싱 ─────────────────────────────
def _extract_field(text: str, tag: str, sub: str) -> str | None:
    """
    MARC 태그+서브필드를 정규식으로 추출
    예: tag="245", sub="a" → "245...a대외불안 요인과 한국경제/" 에서 "대외불안 요인과 한국경제/"
    """
    pattern = rf'{tag}\d{{0,10}}.*?{sub}([^a-z\d].*?)(?=[a-z]\S|$|\d{{3}})'
    match = re.search(pattern, text)
    if match:
        val = match.group(1).strip()
        val = re.split(r'(?<=[^\s])[a-z](?=[A-Z가-힣\d])', val)[0].strip()
        return val if val else None
    return None


def _parse_regex(marc_raw: str) -> dict:
    """제어문자 소실된 MARC 데이터를 정규식으로 파싱"""
    text = marc_raw.strip()

    # record_id: KMO 패턴
    record_id = None
    m = re.search(r'(KMO\d+)', text)
    if m:
        record_id = m.group(1)

    # 245$a: 제목 — "00a" 또는 "10a" 뒤의 내용, "/" 또는 다음 서브필드 전까지
    title = None
    m = re.search(r'245.{0,20}?[0-9]{0,2}a(.+?)(?:/|$)', text)
    if m:
        title = m.group(1).strip().rstrip(' /')

    # 245$c: 책임표시 (저자 표시) — "/" 뒤 내용
    # 주의: 구 코드는 $d 사용 오류 → $c 로 수정
    title_resp = None
    m = re.search(r'245.+?/\s*(?:c)?(.+?)(?=\d{3}|260|264|$)', text)
    if m:
        val = m.group(1).strip()
        if len(val) > 2:
            title_resp = val

    # 260 or 264 $a: 발행지 (AACR2 or RDA)
    pub_place = None
    for tag in ('260', '264'):
        m = re.search(rf'{tag}.{{0,10}}?a(.+?):', text)
        if m:
            pub_place = m.group(1).strip()
            break

    # 260 or 264 $b: 출판사
    publisher = None
    for tag in ('260', '264'):
        m = re.search(rf'{tag}.+?b(.+?)(?:,|\d{{3}}|$)', text)
        if m:
            publisher = m.group(1).strip().rstrip(' ,')
            if publisher:
                break

    # 260 or 264 $c: 발행년 (4자리 연도만 추출)
    pub_date = None
    for tag in ('260', '264'):
        m = re.search(rf'{tag}.+?c(\d{{4}})', text)
        if m:
            pub_date = m.group(1)
            break

    # 056$a: KDC
    kdc = None
    m = re.search(r'056.{0,10}?a([\d.]+)', text)
    if m:
        kdc = m.group(1).strip()

    # 082$a: DDC
    ddc = None
    m = re.search(r'082.{0,10}?a([\d.]+)', text)
    if m:
        ddc = m.group(1)

    # 100$a: 주 개인 저자 + 700$a: 추가 개인 저자 (여러 명 가능)
    personal_authors: list[str] = []
    m = re.search(r'100.{0,10}?a(.+?)(?:,\s*\d|\s*\d{3}|$)', text)
    if m:
        v = m.group(1).strip().rstrip(' ,')
        if v:
            personal_authors.append(v)
    for raw in re.findall(r'700.{0,10}?a(.+?)(?:,\s*\d|\d{3}|$)', text):
        v = raw.strip().rstrip(' ,')
        if v:
            personal_authors.append(v)
    personal_author = " | ".join(personal_authors) if personal_authors else None

    # 110$a (주 표목) 우선, 없으면 710$a (추가 표목): 단체 저자
    corporate_author = None
    for tag in ('110', '710'):
        m = re.search(rf'{tag}.{{0,10}}?a(.+?)(?:,|\d{{3}}|$)', text)
        if m:
            val = m.group(1).strip().rstrip(' ,')
            if val:
                corporate_author = val
                break

    # 020$a: ISBN  (하이픈을 끝에 배치해 character range 오류 방지)
    isbn = None
    m = re.search(r'020.{0,10}?a([\dX-]+)', text)
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