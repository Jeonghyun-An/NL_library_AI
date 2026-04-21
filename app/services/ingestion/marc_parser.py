"""
MARC21 파서

1차: pymarc (제어문자 복원 후 시도)
2차: ISO 2709 직접 파싱 (제어문자 기반, 디렉토리 바이트 오프셋 무시)
      → pymarc가 실패하는 원인: 한글 등 다국어 문자가 디렉토리 바이트 오프셋과
        Python 문자열 위치 간 불일치를 일으킴. \x1E 위치 기반으로 우회.
3차: 정규식 (제어문자 소실된 경우 fallback)
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
    제어문자(0x00–0x1F)는 단일 바이트, 한글 등 다국어는 UTF-8 멀티바이트.
    """
    result = bytearray()
    for ch in text:
        cp = ord(ch)
        if cp <= 0x1F:
            result.append(cp)
        elif cp < 0x80:
            result.append(cp)
        else:
            result.extend(ch.encode("utf-8"))
    return bytes(result)


def _clean_sub(val: str | None) -> str | None:
    """MARC 관행상 붙는 후행 구두점 제거"""
    if not val:
        return None
    return val.strip().rstrip(' ,./;:')


def _clean_date(val: str | None) -> str | None:
    """발행년 필드에서 4자리 연도만 추출"""
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
        marc_bytes = _to_marc_bytes(restored)
        record = Record(data=marc_bytes)
        if not record.get("245"):
            return None

        f008 = record.get("008")
        language = f008.data[35:38].strip() if f008 and len(f008.data) >= 38 else None
        subjects = _get_all(record, "650", "a")
        keywords = _get_all(record, "653", "a")

        publisher = _clean_sub(_get(record, "260", "b") or _get(record, "264", "b"))
        pub_place  = _clean_sub(_get(record, "260", "a") or _get(record, "264", "a"))
        pub_date   = _clean_date(_get(record, "260", "c") or _get(record, "264", "c"))

        personal_authors: list[str] = []
        main_pa = _clean_sub(_get(record, "100", "a"))
        if main_pa:
            personal_authors.append(main_pa)
        for v in _get_all(record, "700", "a"):
            cleaned = _clean_sub(v)
            if cleaned:
                personal_authors.append(cleaned)

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
    except Exception as e:
        log.debug(f"pymarc 예외: {type(e).__name__}: {e}")
        return None


# ── ISO 2709 직접 파싱 (2차) ─────────────────────────────
def _parse_marc_direct(restored: str) -> dict | None:
    """
    제어문자(\x1E/\x1F)가 살아있는 경우 ISO 2709 레코드를 직접 파싱.

    pymarc 실패 원인 우회:
      pymarc는 디렉토리의 바이트 오프셋으로 필드 위치를 찾는데,
      한글 등 다국어 문자가 Python 문자열(1char) vs UTF-8(3bytes) 불일치를
      일으켜 오프셋이 틀어진다.
      → \x1E 위치로 직접 분리하면 이 문제를 완전히 우회할 수 있다.
    """
    if '\x1e' not in restored:
        return None

    if len(restored) < 25:
        return None

    leader = restored[:24]
    try:
        base_addr = int(leader[12:17])
    except (ValueError, IndexError):
        return None

    if base_addr >= len(restored):
        return None

    # 디렉토리에서 태그 목록 추출 (각 엔트리 12자: tag[3]+length[4]+offset[5])
    dir_str = restored[24:base_addr - 1]  # 마지막 \x1E 제외
    tags = [dir_str[i:i+3] for i in range(0, len(dir_str) - 11, 12)]

    # 필드 데이터를 \x1E로 분리 후 레코드 종결자(\x1D) 제거
    field_data = restored[base_addr:]
    parts = field_data.split('\x1e')
    parts = [p.rstrip('\x1d') for p in parts if p.rstrip('\x1d')]

    # 태그 수 ≠ 필드 수인 경우 최솟값 기준으로 처리
    n = min(len(tags), len(parts))
    if n == 0:
        return None
    tags, parts = tags[:n], parts[:n]

    # tag → [field_data, ...] 맵
    fields: dict[str, list[str]] = {}
    for tag, data in zip(tags, parts):
        fields.setdefault(tag, []).append(data)

    def sub(tag: str, code: str) -> str | None:
        """태그+서브필드 코드로 첫 번째 값 반환"""
        for fdata in fields.get(tag, []):
            if tag < '010':  # 제어 필드 (001, 005, 008): 서브필드 없음
                return fdata.strip() or None
            # 일반 필드: 앞 2자는 indicator, 이후 \x1F+code+value
            idx = fdata.find(f'\x1f{code}')
            if idx >= 0:
                s = idx + 2
                e = fdata.find('\x1f', s)
                v = (fdata[s:e] if e >= 0 else fdata[s:]).strip()
                return v or None
        return None

    def all_sub(tag: str, code: str) -> list[str]:
        """해당 태그의 모든 필드에서 서브필드 코드 값 전부 수집"""
        result = []
        for fdata in fields.get(tag, []):
            pos = 0
            while True:
                idx = fdata.find(f'\x1f{code}', pos)
                if idx < 0:
                    break
                s = idx + 2
                e = fdata.find('\x1f', s)
                v = (fdata[s:e] if e >= 0 else fdata[s:]).strip()
                if v:
                    result.append(v)
                pos = s + 1
        return result

    title = _clean_sub(sub('245', 'a'))
    if not title:
        return None

    # 언어 (008[35:38])
    f008 = sub('008', '')
    language = f008[35:38].strip() if f008 and len(f008) >= 38 else None

    # 출판 정보 (AACR2: 260, RDA: 264)
    publisher = _clean_sub(sub('260', 'b') or sub('264', 'b'))
    pub_place  = _clean_sub(sub('260', 'a') or sub('264', 'a'))
    pub_date   = _clean_date(sub('260', 'c') or sub('264', 'c'))

    # 개인 저자 (100 주 표목 + 700 추가 표목)
    personal_authors: list[str] = []
    v = _clean_sub(sub('100', 'a'))
    if v:
        personal_authors.append(v)
    for v in all_sub('700', 'a'):
        c = _clean_sub(v)
        if c:
            personal_authors.append(c)

    # 단체 저자 (110 주 표목 → 710 추가 표목)
    corporate_author = _clean_sub(sub('110', 'a') or sub('710', 'a'))

    subjects = all_sub('650', 'a')
    keywords = all_sub('653', 'a')

    record_id = sub('001', '')

    return {
        "record_id":            record_id.strip() if record_id else None,
        "last_modified":        (sub('005', '') or "").strip() or None,
        "isbn":                 _clean_sub(sub('020', 'a')),
        "holdings":             sub('049', 'a'),
        "kdc":                  _clean_sub(sub('056', 'a')),
        "ddc":                  _clean_sub(sub('082', 'a')),
        "personal_author":      " | ".join(personal_authors) if personal_authors else None,
        "title":                title,
        "title_remainder":      _clean_sub(sub('245', 'b')),
        "title_responsibility": sub('245', 'c') or sub('245', 'd'),
        "pub_place":            pub_place,
        "publisher":            publisher,
        "pub_date":             pub_date,
        "extent":               _clean_sub(sub('300', 'a')),
        "series_title":         _clean_sub(sub('440', 'a') or sub('490', 'a')),
        "note":                 sub('500', 'a'),
        "bibliography_note":    sub('504', 'a'),
        "subject":              " | ".join(subjects) if subjects else None,
        "keyword":              " | ".join(keywords) if keywords else None,
        "corporate_author":     corporate_author,
        "price":                sub('950', 'a'),
        "language":             language,
        "source_format":        "MARC",
    }


# ── 정규식 기반 fallback 파싱 (3차) ──────────────────────
def _extract_field(text: str, tag: str, sub: str) -> str | None:
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

    # 245$a: 제목
    title = None
    m = re.search(r'245.{0,20}?[0-9]{0,2}a(.+?)(?:/|$)', text)
    if m:
        title = m.group(1).strip().rstrip(' /')

    # 245$c: 책임표시
    title_resp = None
    m = re.search(r'245.+?/\s*(?:c)?(.+?)(?=\d{3}|260|264|$)', text)
    if m:
        val = m.group(1).strip()
        if len(val) > 2:
            title_resp = val

    # 260/264 $a: 발행지
    pub_place = None
    for tag in ('260', '264'):
        m = re.search(rf'{tag}.{{0,10}}?a(.+?):', text)
        if m:
            pub_place = m.group(1).strip()
            break

    # 260/264 $b: 출판사
    publisher = None
    for tag in ('260', '264'):
        m = re.search(rf'{tag}.+?b(.+?)(?:,|\d{{3}}|$)', text)
        if m:
            publisher = m.group(1).strip().rstrip(' ,')
            if publisher:
                break

    # 260/264 $c: 발행년
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

    # 100$a + 700$a: 개인 저자
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

    # 110/710$a: 단체 저자
    corporate_author = None
    for tag in ('110', '710'):
        m = re.search(rf'{tag}.{{0,10}}?a(.+?)(?:,|\d{{3}}|$)', text)
        if m:
            val = m.group(1).strip().rstrip(' ,')
            if val:
                corporate_author = val
                break

    # 020$a: ISBN
    isbn = None
    m = re.search(r'020.{0,10}?a([\dX-]+)', text)
    if m:
        isbn = m.group(1)

    # 650$a: 주제어
    subjects = re.findall(r'650.{0,10}?(?:\d+)?a(.+?)(?:0K|$|\d{3})', text)
    subjects = [s.strip().rstrip('[]') for s in subjects if s.strip()]

    # 300$a: 형태사항
    extent = None
    m = re.search(r'300.{0,10}?a(.+?)(?:;|b|$)', text)
    if m:
        extent = m.group(1).strip()

    # 언어
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
    """MARC 문자열 파싱 (pymarc → ISO 2709 직접 → 정규식 fallback)"""
    if not marc_raw or not marc_raw.strip():
        return {}

    restored = _restore_control_chars(marc_raw.strip())

    # 1차: pymarc
    result = _parse_pymarc(marc_raw)
    if result and result.get("title"):
        return result

    # 2차: ISO 2709 직접 파싱 (제어문자 \x1E가 살아있는 경우)
    if '\x1e' in restored:
        result = _parse_marc_direct(restored)
        if result and result.get("title"):
            log.info("ISO 2709 직접 파싱 성공")
            return result

    # 3차: 정규식 fallback (제어문자 소실)
    log.debug("MARC 정규식 fallback 파싱")
    return _parse_regex(marc_raw)
