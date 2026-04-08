"""
MARC21 ISO 2709 파서 (pymarc 기반)
"""
from pymarc import Record


def _get(record: Record, tag: str, sub: str) -> str | None:
    field = record.get(tag)
    if not field:
        return None
    return field.get(sub)


def _get_all(record: Record, tag: str, sub: str) -> list[str]:
    return [
        f.get(sub)
        for f in record.get_fields(tag)
        if f.get(sub)
    ]


def parse(marc_raw: str) -> dict:
    """
    MARC21 ISO 2709 문자열 → DB 저장용 딕셔너리
    """
    if not marc_raw or not marc_raw.strip():
        return {}

    try:
        record = Record(data=marc_raw.strip().encode("utf-8"))
    except Exception as e:
        raise ValueError(f"MARC 파싱 실패: {e}")

    # 008 언어 (35-37번째 자리)
    f008 = record.get("008")
    language = f008.data[35:38].strip() if f008 and len(f008.data) >= 38 else None

    subjects = _get_all(record, "650", "a")
    keywords = _get_all(record, "653", "a")

    return {
        "record_id":              record.get("001").data.strip() if record.get("001") else None,
        "last_modified":          record.get("005").data.strip() if record.get("005") else None,
        "isbn":                   _get(record, "020", "a"),
        "holdings":               _get(record, "049", "a"),
        "kdc":                    _get(record, "056", "a"),
        "ddc":                    _get(record, "082", "a"),
        "personal_author":        _get(record, "100", "a"),
        "title":                  _get(record, "245", "a"),
        "title_remainder":        _get(record, "245", "b"),
        "title_responsibility":   _get(record, "245", "d"),
        "pub_place":              _get(record, "260", "a"),
        "publisher":              _get(record, "260", "b"),
        "pub_date":               _get(record, "260", "c"),
        "extent":                 _get(record, "300", "a"),
        "series_title":           _get(record, "440", "a"),
        "note":                   _get(record, "500", "a"),
        "bibliography_note":      _get(record, "504", "a"),
        "subject":                " | ".join(subjects) if subjects else None,
        "keyword":                " | ".join(keywords) if keywords else None,
        "corporate_author":       _get(record, "710", "a"),
        "price":                  _get(record, "950", "a"),
        "language":               language,
        "source_format":          "MARC",
    }