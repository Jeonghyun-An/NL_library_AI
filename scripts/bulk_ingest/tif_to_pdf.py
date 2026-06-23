"""
tif_to_pdf.py — TIF 스캔 폴더 → PDF 일괄 변환

국중앙도서관 납품 포맷:
  input/  CNTS-XXXXXXXXXX_/          ← 폴더명 끝에 _ 있음
            00000001.tif
            00000002.TIF
            ...
            count.txt

  output/ CNTS-XXXXXXXXXX/            ← 끝 _ 제거 → MinIO originals/ 폴더 구조와 일치
            CNTS-XXXXXXXXXX.pdf

사용:
  python tif_to_pdf.py
  python tif_to_pdf.py --input "D:/다른경로" --output "D:/pdfs" --workers 4
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp"}

DEFAULT_INPUT  = r"D:\260623_국중요청자료\output\output"
DEFAULT_OUTPUT = r"D:\260623_국중요청자료\pdfs"


def _normalize(folder_name: str) -> str:
    """폴더명 끝 '_' 제거 → CONTENTS_ID (build_manifest normalize_book_id 와 동일)."""
    return folder_name.strip().rstrip("_").strip()


def _convert_one(folder: Path, out_dir: Path) -> tuple[str, str, int]:
    """폴더 1개 → PDF. (book_id, status, page_count) 반환."""
    book_id  = _normalize(folder.name)
    book_dir = out_dir / book_id
    pdf_path = book_dir / f"{book_id}.pdf"

    if pdf_path.exists():
        return book_id, "skip", 0

    image_files = sorted(
        f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS
    )
    if not image_files:
        return book_id, "no_images", 0

    book_dir.mkdir(parents=True, exist_ok=True)
    images: list[Image.Image] = []
    try:
        for img_path in image_files:
            img = Image.open(img_path)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            else:
                img = img.copy()
            images.append(img)

        images[0].save(
            pdf_path,
            format="PDF",
            save_all=True,
            append_images=images[1:],
        )
        return book_id, "ok", len(images)

    except Exception as e:
        # 실패한 불완전 PDF 제거
        if pdf_path.exists():
            pdf_path.unlink(missing_ok=True)
        return book_id, f"error: {e}", 0

    finally:
        for img in images:
            try:
                img.close()
            except Exception:
                pass


def main() -> None:
    ap = argparse.ArgumentParser(description="TIF 스캔 폴더 → PDF 일괄 변환")
    ap.add_argument("--input",   default=DEFAULT_INPUT,  help="CNTS-XXXX_/ 폴더가 있는 루트")
    ap.add_argument("--output",  default=DEFAULT_OUTPUT, help="PDF 저장 디렉토리")
    ap.add_argument("--workers", type=int, default=6,    help="병렬 워커 수 (기본 6)")
    args = ap.parse_args()

    in_dir  = Path(args.input)
    out_dir = Path(args.output)

    if not in_dir.exists():
        print(f"입력 경로 없음: {in_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    folders = sorted(d for d in in_dir.iterdir() if d.is_dir())
    total   = len(folders)
    if not total:
        print(f"변환할 폴더 없음: {in_dir}")
        sys.exit(0)

    print(f"대상: {total}권  |  출력: {out_dir}  |  워커: {args.workers}\n")

    ok = skip = err = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_convert_one, f, out_dir): f.name for f in folders}
        for i, fut in enumerate(as_completed(futures), 1):
            book_id, status, pages = fut.result()
            if status == "ok":
                ok += 1
                print(f"[{i:>4}/{total}] ✓  {book_id}.pdf  ({pages}p)")
            elif status == "skip":
                skip += 1
                print(f"[{i:>4}/{total}] —  {book_id}.pdf  (건너뜀)")
            else:
                err += 1
                print(f"[{i:>4}/{total}] ✗  {book_id}  ← {status}", file=sys.stderr)

    print(f"\n완료  성공 {ok}  건너뜀 {skip}  오류 {err}")
    print(f"PDF 위치: {out_dir}")


if __name__ == "__main__":
    main()
