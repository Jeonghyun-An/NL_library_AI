"""restore_cover_keys.py — MinIO covers/ 리스팅 → library_catalog.cover_image_key 재매핑

배경:
  2026-09-14 library_catalog 이 통째로 비워지면서(고아 72,601건) cover_image_key 가
  전부 날아갔다. 표지 이미지 파일 자체는 MinIO 에 그대로 남아있고, 키 규칙이
  `covers/{cnts_id}.jpg` 로 결정론적이라(services/ingestion/cover_generator.py) 무손실 재매핑이 가능하다.

전제:
  카탈로그 재적재가 끝나 library_catalog 에 행이 존재해야 한다. 행이 없으면 아무것도 갱신되지 않는다.

실행 (앱 이미지에 scripts/ 가 없으므로 호스트 바인드 마운트 /app/data 를 경유):
  cp restore_cover_keys.py /data/nl-lib/data/recovery/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/restore_cover_keys.py           # dry-run
  docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/restore_cover_keys.py --apply   # 실제 반영

PYTHONPATH=/app 이 필요한 이유: 스크립트 파일로 실행하면 sys.path[0] 이 스크립트 디렉터리로
잡혀 /app 의 앱 모듈(core, db, domains...)을 못 찾는다. python -c 로 돌릴 때와 다르다.
"""
import sys

from minio import Minio
from sqlalchemy import text

from core.config import get_settings
from db.postgres import SyncSessionLocal

BATCH = 2000
PREFIX = "covers/"
SUFFIX = ".jpg"


def list_cover_ids(cfg) -> list[str]:
    client = Minio(
        cfg.MINIO_ENDPOINT,
        access_key=cfg.MINIO_ACCESS_KEY,
        secret_key=cfg.MINIO_SECRET_KEY,
        secure=cfg.MINIO_SECURE,
    )
    ids = []
    for obj in client.list_objects(cfg.MINIO_BUCKET, prefix=PREFIX, recursive=True):
        key = obj.object_name
        if key.startswith(PREFIX) and key.endswith(SUFFIX):
            ids.append(key[len(PREFIX):-len(SUFFIX)])
    return ids


def main(apply: bool) -> None:
    cfg = get_settings()

    cover_ids = list_cover_ids(cfg)
    print(f"MinIO {PREFIX} 표지 파일: {len(cover_ids):,}개")
    if not cover_ids:
        return

    db = SyncSessionLocal()
    try:
        matched = missing = updated = 0
        for i in range(0, len(cover_ids), BATCH):
            chunk = cover_ids[i:i + BATCH]

            # 카탈로그에 행이 있는 것만 대상. 없는 건 아직 재적재 안 된 고아.
            present = {
                r[0] for r in db.execute(
                    text("SELECT cnts_id FROM library_catalog WHERE cnts_id = ANY(:ids)"),
                    {"ids": chunk},
                )
            }
            matched += len(present)
            missing += len(chunk) - len(present)

            if apply and present:
                # 이미 값이 있으면 건드리지 않는다 (재적재분이 채운 값 보호)
                res = db.execute(
                    text(
                        "UPDATE library_catalog "
                        "SET cover_image_key = 'covers/' || cnts_id || '.jpg' "
                        "WHERE cnts_id = ANY(:ids) AND cover_image_key IS NULL"
                    ),
                    {"ids": list(present)},
                )
                updated += res.rowcount or 0
                db.commit()

        print(f"카탈로그에 존재: {matched:,}건 / 카탈로그에 없음(고아): {missing:,}건")
        if apply:
            print(f"cover_image_key 갱신: {updated:,}건 (이미 채워진 행은 건너뜀)")
        else:
            print("dry-run — 아무것도 쓰지 않았다. 반영하려면 --apply")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
