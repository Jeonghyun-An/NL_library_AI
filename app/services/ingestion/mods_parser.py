"""
MODS XML 파서
"""
from xml.etree import ElementTree as ET

NS = {"mods": "http://www.loc.gov/mods/v3"}


def _find(root: ET.Element, path: str) -> str | None:
    el = root.find(path, NS)
    return el.text.strip() if el is not None and el.text else None


def _findall(root: ET.Element, path: str) -> list[str]:
    return [el.text.strip() for el in root.findall(path, NS) if el.text]


def parse(mods_xml: str) -> dict:
    """
    MODS XML 문자열 → DB 저장용 딕셔너리 (MARC 컬럼 기준)
    """
    try:
        root = ET.fromstring(mods_xml.strip())
    except ET.ParseError as e:
        raise ValueError(f"MODS XML 파싱 실패: {e}")

    # 저자 — personal/corporate 구분
    personal_authors, corporate_authors = [], []
    for name in root.findall("mods:name", NS):
        name_type = name.get("type", "")
        part = name.find("mods:namePart", NS)
        if part is None or not part.text:
            continue
        if name_type == "personal":
            personal_authors.append(part.text.strip())
        elif name_type == "corporate":
            corporate_authors.append(part.text.strip())
        else:
            personal_authors.append(part.text.strip())

    # 발행지 — type="text" 우선
    pub_place = None
    for place in root.findall("mods:originInfo/mods:place/mods:placeTerm", NS):
        if place.get("type") == "text" and place.text:
            pub_place = place.text.strip()
            break

    # KDC 분류
    kdc = None
    for cl in root.findall("mods:classification", NS):
        if cl.get("authority", "").upper().startswith("KDC") and cl.text:
            kdc = cl.text.strip()
            break

    # record_id — CNTS 식별자
    record_id = None
    for ident in root.findall("mods:recordInfo/mods:recordIdentifier", NS):
        if ident.text and ident.text.startswith("CNTS"):
            record_id = ident.text.strip()
            break
    # KMO 등 다른 식별자도 fallback
    if not record_id:
        record_id = _find(root, "mods:relatedItem/mods:recordInfo/mods:recordIdentifier")

    # 주제어
    subjects = _findall(root, "mods:subject/mods:topic")

    # UCI
    uci = None
    for ident in root.findall("mods:identifier", NS):
        if ident.get("type") == "uci" and ident.text:
            uci = ident.text.strip()
            break

    # 날짜 정제 (201205-- → 2012)
    pub_date_raw = _find(root, "mods:originInfo/mods:dateIssued")
    pub_date = pub_date_raw[:4] if pub_date_raw else None

    return {
        "record_id":          record_id,
        "last_modified":      _find(root, "mods:recordInfo/mods:recordChangeDate"),
        "title":              _find(root, "mods:titleInfo/mods:title"),
        "title_remainder":    _find(root, "mods:titleInfo/mods:subTitle"),
        "title_responsibility": None,                          # MODS에 없음
        "personal_author":    " | ".join(personal_authors) if personal_authors else None,
        "corporate_author":   " | ".join(corporate_authors) if corporate_authors else None,
        "publisher":          _find(root, "mods:originInfo/mods:publisher"),
        "pub_place":          pub_place,
        "pub_date":           pub_date,
        "extent":             _find(root, "mods:physicalDescription/mods:extent"),
        "kdc":                kdc,
        "language":           _find(root, "mods:language/mods:languageTerm"),
        "subject":            " | ".join(subjects) if subjects else None,
        "material_type":      _find(root, "mods:typeOfResource"),
        "genre":              _find(root, "mods:genre"),
        "abstract":           _find(root, "mods:abstract"),
        "url":                _find(root, "mods:location/mods:url"),
        "uci":                uci,
        "media_type":         _find(root, "mods:physicalDescription/mods:internetMediaType"),
        "access_condition":   _find(root, "mods:accessCondition/mods:licenseType"),
        "target_audience":    _find(root, "mods:targetAudience"),
        "digital_origin":     _find(root, "mods:physicalDescription/mods:digitalOrigin"),
        "source_format":      "MODS",
    }