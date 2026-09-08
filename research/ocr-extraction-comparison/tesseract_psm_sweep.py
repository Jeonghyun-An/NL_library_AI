"""tesseract_psm_sweep.py — 폴백 발동 168쪽에 대해 --psm 모드별 Tesseract 추출량 비교.

기본값(psm 3)으로만 돌린 대조군이 불리하게 설정된 것 아니냐는 지적을 선제 대응하기 위해,
동일 페이지에 여러 페이지 분할 모드를 적용해 최댓값을 확인한다.
"""
import json, os, re, subprocess, sys, tempfile
import fitz

TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA = r"C:\Users\LANDSOFT\AppData\Local\Temp\claude\C--Users-LANDSOFT-mygit-NL-library-AI\323fbef6-9ad8-4ae4-be15-9845224f185e\scratchpad\tessdata"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/KCI/pdf"
SEL = "C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/323fbef6-9ad8-4ae4-be15-9845224f185e/scratchpad/trigger_pages.json"
OUT = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/tesseract_psm_sweep.json"
PSMS = ["3", "1", "4", "6", "11"]

def clean(t):
    t = re.sub(r'\n{3,}', '\n\n', t)
    lines = []
    for line in t.split('\n'):
        line = line.strip()
        if line: lines.append(line)
        elif lines and lines[-1] != '': lines.append('')
    return re.sub(r' {2,}', ' ', '\n'.join(lines)).strip()

def ocr(png, psm):
    r = subprocess.run([TESS, png, "stdout", "-l", "kor+eng",
                        "--tessdata-dir", TESSDATA, "--psm", psm],
                       capture_output=True, timeout=180)
    if r.returncode != 0:
        # 언어팩 누락 등으로 실패하면 0자가 아니라 예외로 드러나게 한다.
        raise RuntimeError(f"tesseract rc={r.returncode}: "
                           f"{r.stderr.decode('utf-8', errors='replace')[:200]}")
    return clean(r.stdout.decode("utf-8", errors="replace"))

def main():
    sel = json.load(open(SEL, encoding="utf-8"))
    res = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    done = {r["doc"] for r in res}
    for i, (name, pages) in enumerate(sel.items(), 1):
        if name in done:
            print(f"[{i}] skip {name}", file=sys.stderr); continue
        doc = fitz.open(os.path.join(BASE, name))
        out = []
        with tempfile.TemporaryDirectory() as td:
            for pg in pages:
                if pg > len(doc): continue
                png = os.path.join(td, f"p{pg}.png")
                doc[pg-1].get_pixmap(dpi=300).save(png)
                row = {"page": pg}
                for psm in PSMS:
                    try: row["psm"+psm] = len(ocr(png, psm))
                    except Exception as e: row["psm"+psm] = None
                out.append(row)
                print(f"  {name} p.{pg}: " + " ".join(f"psm{p}={row['psm'+p]}" for p in PSMS), file=sys.stderr)
        doc.close()
        res.append({"doc": name, "pages": out})
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved " + OUT, file=sys.stderr)

if __name__ == "__main__":
    main()
