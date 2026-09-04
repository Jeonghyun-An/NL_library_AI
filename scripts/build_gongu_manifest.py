"""build_gongu_manifest.py — 공유마당(gongu.copyright.or.kr)에서 수동으로 받은
PDF를 upload_from_manifest.py가 바로 쓸 수 있는 manifest.jsonl로 정리한다.

공유마당 다운로드는 자동화가 안 된다 — 사이트의 다운로드가 레거시 위젯(DEXT5
계열) 팝업으로 열리는데 브라우저 자동화 환경에서 렌더링이 안 된다. 그래서
사람이 직접 사이트에서 내려받은 뒤, 이 스크립트는 그 파일을 book_id 규칙에
맞게 정리하고 manifest에 등록하는 것만 한다(위키문헌 스크립트의 fetch·PDF
변환 단계에 대응하는 부분이 없을 뿐, 나머지 구조는 동일).

사용 (구분자는 '|' — Windows 경로의 'C:'와 겹치지 않도록 ':' 대신 사용):
    python scripts/build_gongu_manifest.py --out-dir "<...>/gongu_new" \
        --add "C:/Users/LANDSOFT/Downloads/김유정-동백꽃-조광.pdf|GM_001|동백꽃|김유정"

    # 여러 건 한 번에
    python scripts/build_gongu_manifest.py --out-dir "<...>/gongu_new" \
        --add "파일1.pdf|GM_001|제목1|저자1" --add "파일2.pdf|GM_002|제목2|저자2"
"""
import argparse
import io
import json
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="PDF·manifest를 저장할 디렉토리")
    ap.add_argument(
        "--add", action="append", default=[],
        help="'원본PDF경로|book_id|제목|저자' 형식, 여러 번 지정 가능",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    pdf_dir = out_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / "manifest.jsonl"
    existing_rows = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    existing_rows[r["book_id"]] = r

    for spec in args.add:
        parts = spec.split("|", 3)
        if len(parts) != 4:
            print(f"형식 오류(건너뜀) — 'PDF경로|book_id|제목|저자' 형식이어야 함: {spec}")
            continue
        src_path, book_id, title, author = parts
        src = Path(src_path)
        if not src.is_file():
            print(f"[{book_id}] 파일 없음, 건너뜀: {src}")
            continue

        final_pdf = pdf_dir / f"{book_id}.pdf"
        shutil.copy2(src, final_pdf)
        size = final_pdf.stat().st_size

        existing_rows[book_id] = {
            "book_id": book_id,
            "file": str(final_pdf),
            "object_key": f"originals/{book_id}/{book_id}.pdf",
            "size": size,
            "title": title,
            "author": author,
            "source": "gongu.copyright.or.kr",
        }
        print(f"[{book_id}] {title} ({author}) 등록 완료 — {size:,} bytes")

    with open(manifest_path, "w", encoding="utf-8") as f:
        for r in existing_rows.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n전체 manifest {len(existing_rows)}건. manifest: {manifest_path}")


if __name__ == "__main__":
    main()
