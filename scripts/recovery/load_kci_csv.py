"""load_kci_csv.py — KCI 논문 카탈로그 CSV 적재 (xlsx 전용 로더의 CSV 대체 경로)

배경:
  domains/nl_library/loaders/kci_xlsx.py 의 load_kci_xlsx() 는 openpyxl 직결이라
  .csv 를 못 읽는다(load_workbook 에서 예외). NL MARC/MODS 로더는 _read_rows() 로
  CSV 를 지원하는데 KCI 로더만 xlsx 전용이다.
  2026-09-14 카탈로그 유실 복구에 CSV 원본을 써야 해서, 이미지 재빌드 없이
  같은 매핑·같은 upsert 를 그대로 태우는 스트리밍 경로를 따로 둔다.

xlsx 로더와의 차이는 입력 형식뿐이다. 컬럼 매핑(_COL_MAP), extra 기록(_TRUE_NAMES),
숫자 필드 처리, title 폴백, doc_type/source_format 부여까지 전부 재사용한다.
전체를 메모리에 올리는 xlsx 로더와 달리 행 단위로 흘려보낸다.

실행 (앱 이미지에 scripts/ 가 없으므로 호스트 바인드 마운트 /app/data 경유):
  mkdir -p /data/nl-lib/data/recovery && cp load_kci_csv.py /data/nl-lib/data/recovery/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/load_kci_csv.py <csv경로>           # dry-run
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/load_kci_csv.py <csv경로> --apply

PYTHONPATH=/app 이 필요한 이유: 스크립트 파일로 실행하면 sys.path[0] 이 스크립트 디렉터리로
잡혀 /app 의 앱 모듈을 못 찾는다.
"""
import csv
import sys

from domains.base import ParsedRecord, split_core_extra
from domains.nl_library.loaders.kci_xlsx import _COL_MAP, _TRUE_NAMES
from db.postgres import SyncSessionLocal
from repositories.catalog_bulk import upsert_catalog_records

ENCODINGS = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
DELIMITERS = [",", "\t", "|"]

# 대용량 CSV 의 XML/초록 필드가 기본 상한(131072자)을 넘길 수 있다
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def sniff(path: str) -> tuple[str, str, list[str]]:
    """KCI_FI_ID 헤더가 나오는 (인코딩, 구분자) 조합을 찾는다."""
    for enc in ENCODINGS:
        for delim in DELIMITERS:
            try:
                with open(path, encoding=enc, newline="") as f:
                    row = next(csv.reader(f, delimiter=delim), None)
                if row and "KCI_FI_ID" in [c.strip().upper() for c in row]:
                    return enc, delim, [c.strip().upper() for c in row]
            except Exception:
                continue
    raise ValueError("KCI_FI_ID 헤더를 찾지 못했다 — 인코딩/구분자 조합 실패")


def iter_records(path: str, enc: str, delim: str, headers: list[str]):
    col_idx = {col: headers.index(col) for col in _COL_MAP if col in headers}
    id_idx = col_idx["KCI_FI_ID"]

    with open(path, encoding=enc, newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        next(reader, None)
        for row in reader:
            if len(row) <= id_idx:
                continue
            cnts_id = (row[id_idx] or "").strip()
            if not cnts_id:
                continue

            rec: dict = {"source_format": "KCI", "genre": "paper", "language": "ko"}
            true_names: dict = {}
            for col, field in _COL_MAP.items():
                idx = col_idx.get(col)
                if idx is None or len(row) <= idx:
                    continue
                val = (row[idx] or "").strip()
                if not val:
                    continue
                if field in ("kci_citations", "wos_citations"):
                    try:
                        rec[field] = int(val)
                    except ValueError:
                        rec[field] = 0
                else:
                    rec[field] = val
                if col in _TRUE_NAMES:
                    true_names[_TRUE_NAMES[col]] = val

            if not rec.get("title"):
                rec["title"] = cnts_id

            rec.pop("cnts_id", None)
            core, extra = split_core_extra(rec)
            core["cnts_id"] = cnts_id
            core["doc_type"] = "paper"
            extra.update(true_names)
            yield ParsedRecord(
                source_id=cnts_id, core=core, extra=extra, source_format="KCI",
            )


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    path = args[0]
    apply = "--apply" in sys.argv

    enc, delim, headers = sniff(path)
    print(f"인코딩={enc} 구분자={delim!r}")
    print(f"헤더: {headers[:13]}")

    if not apply:
        n = 0
        sample = None
        for rec in iter_records(path, enc, delim, headers):
            if sample is None:
                sample = rec
            n += 1
        print(f"파싱 가능 레코드: {n:,}건")
        if sample:
            print(f"샘플 source_id={sample.source_id} title={sample.core.get('title', '')[:60]}")
        print("dry-run — 아무것도 쓰지 않았다. 반영하려면 --apply")
        return

    db = SyncSessionLocal()
    try:
        result = upsert_catalog_records(db, iter_records(path, enc, delim, headers))
        print(f"적재 완료: 신규 {result['created']:,} / 갱신 {result['updated']:,} / 총 {result['total']:,}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
