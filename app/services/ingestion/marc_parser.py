"""
MARC21 텍스트 형식 파서
CSV의 세 번째 컬럼(MARC 문자열)을 받아 딕셔너리로 반환
"""
import re
from dataclasses import dataclass, field


@dataclass
class MarcField:
    tag: str
    indicator1: str
    indicator2: str
    subfields: dict[str, list[str]] = field(default_factory=dict)


def _parse_marc_text(marc_raw: str) -> dict[str, list[MarcField]]:
    """
    MARC 텍스트 문자열 → {tag: [MarcField, ...]} 딕셔너리
    """
    # 디렉토리 파싱: 각 필드는 태그(3) + 길이(4) + 시작위치(5) = 12자
    leader = marc_raw[:24]
    base_addr = int(marc_raw[12:17])
    directory = marc_raw[24:base_addr - 1]
    data = marc_raw[base_addr:]

    entries = []
    for i in range(0, len(directory), 12):
        chunk = directory[i:i+12]
        if len(chunk) < 12:
            break
        tag      = chunk[0:3]
        length   = int(chunk[3:7])
        start    = int(chunk[7:12])
        entries.append((tag, start, length))

    fields: dict[str, list[MarcField]] = {}
    for tag, start, length in entries:
        raw = data[start:start + length - 1]  # -1: field terminator 제거

        if tag < "010":
            # 제어 필드 (001, 003, 005 등) — 서브필드 없음
            mf = MarcField(tag=tag, indicator1=" ", indicator2=" ")
            mf.subfields["_"] = [raw]
        else:
            ind1 = raw[0] if len(raw) > 0 else " "
            ind2 = raw[1] if len(raw) > 1 else " "
            mf = MarcField(tag=tag, indicator1=ind1, indicator2=ind2)
            # 서브필드 분리 (구분자: \x1f + 코드)
            parts = re.split(r'\x1f', raw[2:])
            for part in parts:
                if not part:
                    continue
                code = part[0]
                value = part[1:]
                mf.subfields.setdefault(code, []).append(value)

        fields.setdefault(tag, []).append(mf)

    return fields


def _get(fields: dict, tag: str, sub: str, idx: int = 0) -> str | None:
    """특정 태그·서브필드 값 추출 (없으면 None)"""
    tag_fields = fields.get(tag, [])
    if idx >= len(tag_fields):
        return None
    return tag_fields[idx].subfields.get(sub, [None])[0]


def _get_all(fields: dict, tag: str, sub: str) -> list[str]:
    """특정 태그·서브필드 전체 값 리스트"""
    result = []
    for mf in fields.get(tag, []):
        result.extend(mf.subfields.get(sub, []))
    return result


def parse(marc_raw: str) -> dict:
    """
    MARC 텍스트 → DB 저장용 딕셔너리
    """
    if not marc_raw or not marc_raw.strip():
        return {}

    try:
        fields = _parse_marc_text(marc_raw.strip())
    except Exception as e:
        raise ValueError(f"MARC 파싱 실패: {e}")

    # 008 언어 (35-37번째 자리)
    f008 = _get(fields, "008", "_")
    language = f008[35:38].strip() if f008 and len(f008) >= 38 else None

    # 주제어 여러 개 합치기
    subjects = _get_all(fields, "650", "a")
    keywords = _get_all(fields, "653", "a")

    return {
        "record_id":          _get(fields, "001", "_"),
        "last_modified":      _get(fields, "005", "_"),
        "isbn":               _get(fields, "020", "a"),
        "holdings":           _get(fields, "049", "a"),
        "kdc":                _get(fields, "056", "a"),
        "ddc":                _get(fields, "082", "a"),
        "personal_author":    _get(fields, "100", "a"),
        "title":              _get(fields, "245", "a"),
        "title_remainder":    _get(fields, "245", "b"),
        "title_responsibility": _get(fields, "245", "d"),
        "pub_place":          _get(fields, "260", "a"),
        "publisher":          _get(fields, "260", "b"),
        "pub_date":           _get(fields, "260", "c"),
        "extent":             _get(fields, "300", "a"),
        "series_title":       _get(fields, "440", "a"),
        "note":               _get(fields, "500", "a"),
        "bibliography_note":  _get(fields, "504", "a"),
        "subject":            " | ".join(subjects) if subjects else None,
        "keyword":            " | ".join(keywords) if keywords else None,
        "corporate_author":   _get(fields, "710", "a"),
        "price":              _get(fields, "950", "a"),
        "language":           language,
        "source_format":      "MARC",
    }