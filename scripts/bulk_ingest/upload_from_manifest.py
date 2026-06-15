"""
upload_from_manifest.py — manifest.jsonl 기반 PDF → MinIO 업로드

build_manifest.py 가 생성한 매니페스트의 각 행에서
  file (로컬 경로) → object_key (originals/{id}/{id}.pdf)
로 멀티스레드 업로드. 이미 존재하고 크기가 같으면 건너뛴다 (재개 가능).

평탄한 로컬 폴더(pdfs/{id}.pdf)를 rclone 없이 올바른 키 구조로 올릴 때 사용.
minio 패키지만 의존.

사용:
  python upload_from_manifest.py --manifest ./out/round1/manifest.jsonl \
         --endpoint <서버IP>:21000 --access-key X --secret-key Y \
         --bucket nl-lib-bucket --workers 16
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from minio import Minio
except ImportError:  # pragma: no cover
    print("minio 미설치 — pip install minio", file=sys.stderr)
    raise


def _load_manifest(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _upload_one(client: Minio, bucket: str, row: dict) -> tuple[str, str]:
    """returns (book_id, status). status: uploaded | skipped | error:..."""
    book_id = row["book_id"]
    key = row["object_key"]
    local = row["file"]
    try:
        try:
            st = client.stat_object(bucket, key)
            if st.size == row.get("size"):
                return book_id, "skipped"
        except Exception:
            pass
        client.fput_object(bucket, key, local, content_type="application/pdf")
        return book_id, "uploaded"
    except Exception as e:
        return book_id, f"error:{e}"


def main() -> None:
    ap = argparse.ArgumentParser(description="매니페스트 기반 PDF → MinIO 업로드")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--endpoint", required=True, help="예: 211.219.26.15:21000")
    ap.add_argument("--access-key", required=True)
    ap.add_argument("--secret-key", required=True)
    ap.add_argument("--bucket", default="nl-lib-bucket")
    ap.add_argument("--secure", action="store_true", help="HTTPS 사용")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    rows = _load_manifest(args.manifest)
    client = Minio(
        args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        secure=args.secure,
    )
    if not client.bucket_exists(args.bucket):
        client.make_bucket(args.bucket)

    uploaded = skipped = errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(_upload_one, client, args.bucket, r) for r in rows]
        for i, fut in enumerate(as_completed(futures), 1):
            book_id, status = fut.result()
            if status == "uploaded":
                uploaded += 1
            elif status == "skipped":
                skipped += 1
            else:
                errors += 1
                print(f"  [{book_id}] {status}", file=sys.stderr)
            if i % 500 == 0:
                print(f"  진행 {i}/{len(rows)} (업로드 {uploaded}, 스킵 {skipped}, 실패 {errors})")

    print(f"\n완료: 업로드 {uploaded}, 스킵 {skipped}, 실패 {errors} / 총 {len(rows)}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
