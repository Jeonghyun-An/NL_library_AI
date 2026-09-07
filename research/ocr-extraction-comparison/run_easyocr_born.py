"""run_easyocr_born.py — 텍스트 레이어가 온전한 120쪽에서 easyocr 의 추출량 측정.

목적: "왜 OCR 계열(easyocr 등) 대신 레이아웃 보존 추출기를 썼는가" 를 논증이 아니라
실측으로 답한다. Tesseract 는 같은 표본에서 정답지(fitz 텍스트 레이어) 대비 중앙값
1.28배(psm 3)·1.60배(psm 11)를 산출했다. easyocr 도 같은 초과를 보이는지 확인한다.

정제 로직·렌더 해상도(300dpi)는 tesseract_born_psm11.py 와 동일하게 맞춘다.

반드시 GPU 서버에서 실행할 것 (easyocr 은 torch 필요, 첫 실행 시 모델 자동 다운로드).

사용법:
    python run_easyocr_born.py <KCI PDF 폴더>
"""
import io, json, os, re, sys, time

import fitz
import numpy as np
import easyocr

SEL = "born_pages.json"
OUT = "easyocr_born_result.json"
DPI = 300


def clean(t):
    """tesseract_born_psm11.py 와 동일."""
    t = re.sub(r'\n{3,}', '\n\n', t)
    lines = []
    for line in t.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != '':
            lines.append('')
    return re.sub(r' {2,}', ' ', '\n'.join(lines)).strip()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    pdf_dir = sys.argv[1]
    sel = json.load(io.open(SEL, encoding="utf-8"))
    reader = easyocr.Reader(['ko', 'en'], gpu=True)

    res = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    done = {r["doc"] for r in res}
    for i, (name, pages) in enumerate(sel.items(), 1):
        if name in done:
            print(f"[{i}/{len(sel)}] skip {name}", file=sys.stderr)
            continue
        path = os.path.join(pdf_dir, name)
        if not os.path.exists(path):
            print(f"[{i}/{len(sel)}] [파일없음] {path}", file=sys.stderr)
            continue
        doc = fitz.open(path)
        out = []
        for pg in pages:
            if pg > len(doc):
                continue
            page = doc[pg - 1]
            pix = page.get_pixmap(dpi=DPI)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            t0 = time.perf_counter()
            lines = reader.readtext(img, detail=0, paragraph=False)
            elapsed = time.perf_counter() - t0
            text = clean("\n".join(lines))
            out.append({"page": pg,
                        "fitz_len": len(clean(page.get_text("text"))),
                        "easyocr_len": len(text),
                        "elapsed_sec": round(elapsed, 2)})
            print(f"  {name} p.{pg}: fitz {out[-1]['fitz_len']} / easyocr "
                  f"{out[-1]['easyocr_len']} ({elapsed:.1f}s)", file=sys.stderr)
        doc.close()
        res.append({"doc": name, "pages": out})
        json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("저장: " + OUT, file=sys.stderr)


if __name__ == "__main__":
    main()
