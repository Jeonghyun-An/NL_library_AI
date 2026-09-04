"""run_surya_paddle_born.py — 텍스트 레이어가 온전한 120쪽에서 Surya·PaddleOCR 추출량 측정.

표 1과 같은 조건(같은 페이지, 같은 300dpi 렌더, 같은 정제 로직, fitz 정답지)으로 재야
비교가 성립한다. 이미 잰 값: ODL 1.01배, VLM 1.01배, easyocr 1.01배,
Tesseract psm3 1.28배 / psm11 1.60배.

두 서비스는 별도 컨테이너다.
  Surya  : POST /ocr  {"image_b64": ...} -> {"text": ...}
  Paddle : POST /ocr/page {"image_base64":..., "lang":"korean"} -> {"text": ...}

사용법 (두 컨테이너에 접근 가능한 서버에서):
    python run_surya_paddle_born.py <KCI PDF 폴더> \
        [surya_url] [paddle_url]
    예: python run_surya_paddle_born.py ./kci_pdfs \
            http://surya:8000 http://paddleocr:8000
"""
import base64, io, json, os, re, sys, time

import fitz
import httpx

SEL = "born_pages.json"
OUT = "surya_paddle_born_result.json"
DPI = 300
TIMEOUT = 180.0


def clean(t):
    """tesseract_born_psm11.py / run_easyocr_born.py 와 동일."""
    t = re.sub(r'\n{3,}', '\n\n', t)
    lines = []
    for line in t.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != '':
            lines.append('')
    return re.sub(r' {2,}', ' ', '\n'.join(lines)).strip()


def ask_surya(client, url, png_bytes):
    r = client.post(f"{url}/ocr",
                    json={"image_b64": base64.b64encode(png_bytes).decode()},
                    timeout=TIMEOUT)
    r.raise_for_status()
    return clean(r.json().get("text", ""))


def ask_paddle(client, url, png_bytes):
    """POST /ocr/page  {"image_base64":..., "lang":"korean"} -> {"text": ...}

    주의: 이 서비스의 OpenAPI 문서는 image_b64 로 적혀 있으나 실제 필드는
    image_base64 다(문서와 코드가 어긋나 있음).
    """
    r = client.post(f"{url}/ocr/page",
                    json={"image_base64": base64.b64encode(png_bytes).decode(),
                           "lang": "korean"},
                    timeout=TIMEOUT)
    r.raise_for_status()
    return clean(r.json().get("text", ""))


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    pdf_dir = sys.argv[1]
    surya_url = sys.argv[2] if len(sys.argv) > 2 else "http://surya:8000"
    paddle_url = sys.argv[3] if len(sys.argv) > 3 else "http://paddleocr:8000"

    sel = json.load(io.open(SEL, encoding="utf-8"))
    res = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    done = {r["doc"] for r in res}

    with httpx.Client() as client:
        for i, (name, pages) in enumerate(sel.items(), 1):
            if name in done:
                print(f"[{i}/{len(sel)}] skip {name}", file=sys.stderr); continue
            path = os.path.join(pdf_dir, name)
            if not os.path.exists(path):
                print(f"[{i}/{len(sel)}] [파일없음] {path}", file=sys.stderr); continue
            doc = fitz.open(path)
            out = []
            for pg in pages:
                if pg > len(doc):
                    continue
                page = doc[pg - 1]
                png = page.get_pixmap(dpi=DPI).tobytes("png")
                row = {"page": pg, "fitz_len": len(clean(page.get_text("text")))}
                for label, fn, url in (("surya", ask_surya, surya_url),
                                       ("paddle", ask_paddle, paddle_url)):
                    t0 = time.perf_counter()
                    try:
                        txt = fn(client, url, png)
                        row[f"{label}_len"] = len(txt)
                        row[f"{label}_sec"] = round(time.perf_counter() - t0, 2)
                    except httpx.HTTPStatusError as e:
                        # 422 등 검증 오류는 본문에 원인이 들어 있다
                        row[f"{label}_len"] = None
                        row[f"{label}_err"] = f"{e.response.status_code} {e.response.text[:200]}"
                    except Exception as e:
                        row[f"{label}_len"] = None
                        row[f"{label}_err"] = str(e)[:200]
                out.append(row)
                print(f"  {name} p.{pg}: fitz {row['fitz_len']} / "
                      f"surya {row.get('surya_len')} / paddle {row.get('paddle_len')}",
                      file=sys.stderr)
            doc.close()
            res.append({"doc": name, "pages": out})
            json.dump(res, io.open(OUT, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
    print("저장: " + OUT, file=sys.stderr)


if __name__ == "__main__":
    main()
