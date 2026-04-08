"""
xlsx_loader.py
엑셀 컬럼: CONTENTS_ID | TITLE_INFO | MARC | MODS

MARC 있음 → marc_parser
MARC 없음 → mods_parser
"""
import logging
from pathlib import Path
from openpyxl import load_workbook

from services.ingestion.marc_parser import parse as parse_marc
from services.ingestion.mods_parser import parse as parse_mods

log = logging.getLogger(__name__)


def load_xlsx(xlsx_path: str) -> list[dict]:
    """
    엑셀 파일 읽기 → 파싱된 레코드 리스트 반환
    """
    path = Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"엑셀 파일 없음: {xlsx_path}")

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    # 헤더 행 확인
    headers = [str(cell.value).strip().upper() if cell.value else "" for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    log.info(f"헤더: {headers}")

    try:
        idx_cnts = headers.index("CONTENTS_ID")
        idx_title = headers.index("TITLE_INFO")
        idx_marc = headers.index("MARC")
        idx_mods = headers.index("MODS")
    except ValueError as e:
        raise ValueError(f"필수 컬럼 없음: {e}")

    records = []
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        cnts_id   = str(row[idx_cnts]).strip()  if row[idx_cnts]  else ""
        title_raw = str(row[idx_title]).strip() if row[idx_title] else ""
        marc_raw  = str(row[idx_marc]).strip()  if row[idx_marc]  else ""
        mods_raw  = str(row[idx_mods]).strip()  if row[idx_mods]  else ""

        if not cnts_id:
            log.warning(f"[row {row_num}] CONTENTS_ID 없음, skip")
            continue

        try:
            if marc_raw:
                parsed = parse_marc(marc_raw)
                # 엑셀 제목이 더 정제된 경우 fallback
                parsed["title"] = parsed.get("title") or title_raw
                log.info(f"[{cnts_id}] MARC 파싱 완료")

            elif mods_raw:
                parsed = parse_mods(mods_raw)
                parsed["title"] = parsed.get("title") or title_raw
                log.info(f"[{cnts_id}] MODS 파싱 완료")

            else:
                # 둘 다 없는 경우 — title만 저장
                parsed = {"title": title_raw, "source_format": "NONE"}
                log.warning(f"[{cnts_id}] MARC/MODS 모두 없음 — title만 저장")

            parsed["cnts_id"] = cnts_id
            records.append(parsed)

        except Exception as e:
            log.error(f"[{cnts_id}] 파싱 실패: {e}")
            continue

    wb.close()

    marc_cnt = sum(1 for r in records if r.get("source_format") == "MARC")
    mods_cnt = sum(1 for r in records if r.get("source_format") == "MODS")
    none_cnt = sum(1 for r in records if r.get("source_format") == "NONE")
    log.info(f"총 {len(records)}건 — MARC: {marc_cnt}, MODS: {mods_cnt}, 없음: {none_cnt}")

    return records