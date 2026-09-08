import json
import re
import subprocess
import sys
import tempfile
import os
import fitz

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = r"C:\Users\LANDSOFT\AppData\Local\Temp\claude\C--Users-LANDSOFT-mygit-NL-library-AI\323fbef6-9ad8-4ae4-be15-9845224f185e\scratchpad\tessdata"
DPI = 300  # extractor.py FITZ_DPI 와 동일 조건
MAX_PAGES = 15  # VLM 쪽과 동일한 페이지 범위로 맞춤

def _clean_text(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != '':
            lines.append('')
    text = '\n'.join(lines)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

def ocr_page(png_path):
    result = subprocess.run(
        [TESSERACT_EXE, png_path, "stdout", "-l", "kor+eng", "--tessdata-dir", TESSDATA_DIR],
        capture_output=True, timeout=120,
    )
    return result.stdout.decode("utf-8", errors="replace")

def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    n = min(len(doc), MAX_PAGES)
    pages = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(n):
            page = doc[i]
            pix = page.get_pixmap(dpi=DPI)
            png_path = os.path.join(tmpdir, f"p{i+1}.png")
            pix.save(png_path)
            raw = ocr_page(png_path)
            text = _clean_text(raw)
            pages.append({"page": i + 1, "tess_len": len(text)})
            print(f"  p.{i+1}/{n}: {len(text)}자", file=sys.stderr)
    doc.close()
    return pages

def main():
    out_path = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/tesseract_lengths_result.json"
    results = []
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            results = json.load(f)
    done_paths = {r["path"] for r in results}
    for pdf_path in sys.argv[1:]:
        if pdf_path in done_paths:
            print(f"[skip, 이미 완료] {pdf_path}", file=sys.stderr)
            continue
        print(f"[tesseract] {pdf_path}", file=sys.stderr)
        pages = process_pdf(pdf_path)
        results.append({"path": pdf_path, "pages": pages})
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"저장: {out_path}")

if __name__ == "__main__":
    main()
