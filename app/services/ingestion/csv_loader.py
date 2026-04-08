"""
CSV 로더
컬럼: cnts_id | title | marc_data (없으면 빈 문자열)

MARC 있음 → marc_parser
MARC 없음 → mods_parser (MODS XML은 별도 엑셀/파일에서 로드)
"""
import csv
import logging
from pathlib import Path
from services.ingestion.marc_parser import parse as parse_marc
from services.ingestion.mods_parser import parse as parse_mods

log = logging.getLogger(__name__)


def load_csv(csv_path: str) -> list[dict]:
    """
    CSV 파일 읽기 → 파싱된 레코드 리스트 반환
    각 레코드에 cnts_id 포함
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV 파일 없음: {csv_path}")

    records = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter="\t")  # 탭 구분자 (샘플 기준)
        for row_num, row in enumerate(reader, start=1):
            if len(row) < 2:
                log.warning(f"[row {row_num}] 컬럼 부족, skip")
                continue

            cnts_id   = row[0].strip()
            title_raw = row[1].strip()
            marc_raw  = row[2].strip() if len(row) > 2 else ""

            if not cnts_id:
                log.warning(f"[row {row_num}] cnts_id 없음, skip")
                continue

            try:
                if marc_raw:
                    parsed = parse_marc(marc_raw)
                    parsed["title"] = parsed.get("title") or title_raw
                else:
                    # MARC 없음 → MODS XML은 별도 로드 필요
                    # 일단 title만 채우고 source_format 표시
                    parsed = {
                        "title": title_raw,
                        "source_format": "MODS",
                    }
                    log.info(f"[{cnts_id}] MARC 없음 — MODS 별도 로드 필요")

                parsed["cnts_id"] = cnts_id
                records.append(parsed)

            except Exception as e:
                log.error(f"[{cnts_id}] 파싱 실패: {e}")
                continue

    log.info(f"총 {len(records)}건 로드 완료 (MARC: {sum(1 for r in records if r.get('source_format') == 'MARC')}, MODS 대기: {sum(1 for r in records if r.get('source_format') == 'MODS')})")
    return records


def load_mods_excel(excel_path: str) -> dict[str, str]:
    """
    MODS XML이 담긴 엑셀 로드
    컬럼: cnts_id | mods_xml
    반환: {cnts_id: mods_xml_string}
    """
    import openpyxl
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"엑셀 파일 없음: {excel_path}")

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    result = {}

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0] or not row[1]:
            continue
        cnts_id  = str(row[0]).strip()
        mods_xml = str(row[1]).strip()
        result[cnts_id] = mods_xml

    log.info(f"MODS 엑셀 {len(result)}건 로드 완료")
    return result


def merge_mods(records: list[dict], mods_map: dict[str, str]) -> list[dict]:
    """
    MARC 없는 레코드에 MODS 파싱 결과 병합
    """
    merged = []
    for rec in records:
        if rec.get("source_format") == "MODS":
            cnts_id = rec["cnts_id"]
            mods_xml = mods_map.get(cnts_id)
            if mods_xml:
                try:
                    parsed = parse_mods(mods_xml)
                    parsed["cnts_id"] = cnts_id
                    parsed["title"]   = parsed.get("title") or rec["title"]
                    merged.append(parsed)
                except Exception as e:
                    log.error(f"[{cnts_id}] MODS 파싱 실패: {e}")
                    merged.append(rec)
            else:
                log.warning(f"[{cnts_id}] MODS XML 없음 — title만 저장")
                merged.append(rec)
        else:
            merged.append(rec)

    return merged