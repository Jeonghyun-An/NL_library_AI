"""tesseract_born_psm11.py — 텍스트 레이어가 온전한 페이지에서 psm 11의 과다 추출 측정.

폴백 대상 168쪽에서 psm 11이 기본값보다 23.6% 많은 글자를 낸 것이 실제 내용인지
잡음인지 판별하기 위해, fitz가 온전한 텍스트 레이어를 읽어낸 페이지(정답지에 해당)에
같은 모드를 적용해 fitz 대비 비율을 잰다.
"""
import json, os, re, subprocess, sys, tempfile
import fitz

TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA = r"C:\Users\LANDSOFT\AppData\Local\Temp\claude\C--Users-LANDSOFT-mygit-NL-library-AI\323fbef6-9ad8-4ae4-be15-9845224f185e\scratchpad\tessdata"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/KCI/pdf"
SEL = "C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/323fbef6-9ad8-4ae4-be15-9845224f185e/scratchpad/born_pages.json"
OUT = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/tesseract_born_psm11.json"

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
        raise RuntimeError(f"rc={r.returncode}: {r.stderr.decode('utf-8', errors='replace')[:200]}")
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
                page = doc[pg-1]
                png = os.path.join(td, f"p{pg}.png")
                page.get_pixmap(dpi=300).save(png)
                out.append({"page": pg,
                            "fitz_len": len(clean(page.get_text("text"))),
                            "psm3": len(ocr(png, "3")),
                            "psm11": len(ocr(png, "11"))})
                print(f"  {name} p.{pg}: {out[-1]}", file=sys.stderr)
        doc.close()
        res.append({"doc": name, "pages": out})
        json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved " + OUT, file=sys.stderr)

if __name__ == "__main__":
    main()
