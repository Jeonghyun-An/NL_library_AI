"""
MODS XML 파서

엑셀에 저장된 MODS XML은 제어문자가 _x001E_ 등으로 이스케이프되어 있고,
잘못된 XML 엔티티나 깨진 문자가 포함될 수 있으므로 정제 후 파싱한다.
"""
import re
from xml.etree import ElementTree as ET

NS = {"mods": "http://www.loc.gov/mods/v3"}


def _clean_xml(xml_str: str) -> str:
    """엑셀 이스케이프 복원 + XML 정제"""
    # 엑셀 이스케이프 제어문자 복원/제거
    text = re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), xml_str)

    # XML에서 허용되지 않는 제어문자 제거 (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # 잘못된 XML 엔티티 제거
    text = re.sub(r'&(?!(?:amp|lt|gt|apos|quot|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)

    return text.strip()


def _find(root: ET.Element, path: str) -> str | None:
    el = root.find(path, NS)
    return el.text.strip() if el is not None and el.text else None


def _findall(root: ET.Element, path: str) -> list[str]:
    return [el.text.strip() for el in root.findall(path, NS) if el.text]


def parse(mods_xml: str) -> dict:
    """MODS XML 문자열 → DB 저장용 딕셔너리"""
    cleaned = _clean_xml(mods_xml)

    try:
        root = ET.fromstring(cleaned)
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

    # 발행지
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

    # record_id
    record_id = None
    for ident in root.findall("mods:recordInfo/mods:recordIdentifier", NS):
        if ident.text and ident.text.startswith("CNTS"):
            record_id = ident.text.strip()
            break
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

    # 날짜 정제
    pub_date_raw = _find(root, "mods:originInfo/mods:dateIssued")
    pub_date = pub_date_raw[:4] if pub_date_raw else None

    return {
        "record_id":            record_id,
        "last_modified":        _find(root, "mods:recordInfo/mods:recordChangeDate"),
        "title":                _find(root, "mods:titleInfo/mods:title"),
        "title_remainder":      _find(root, "mods:titleInfo/mods:subTitle"),
        "title_responsibility": None,
        "personal_author":      " | ".join(personal_authors) if personal_authors else None,
        "corporate_author":     " | ".join(corporate_authors) if corporate_authors else None,
        "publisher":            _find(root, "mods:originInfo/mods:publisher"),
        "pub_place":            pub_place,
        "pub_date":             pub_date,
        "extent":               _find(root, "mods:physicalDescription/mods:extent"),
        "kdc":                  kdc,
        "language":             _find(root, "mods:language/mods:languageTerm"),
        "subject":              " | ".join(subjects) if subjects else None,
        "material_type":        _find(root, "mods:typeOfResource"),
        "genre":                _find(root, "mods:genre"),
        "abstract":             _find(root, "mods:abstract"),
        "url":                  _find(root, "mods:location/mods:url"),
        "uci":                  uci,
        "media_type":           _find(root, "mods:physicalDescription/mods:internetMediaType"),
        "access_condition":     _find(root, "mods:accessCondition/mods:licenseType"),
        "target_audience":      _find(root, "mods:targetAudience"),
        "digital_origin":       _find(root, "mods:physicalDescription/mods:digitalOrigin"),
        "source_format":        "MODS",
    }