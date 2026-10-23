"""페르소나 책 17권 — 적재할 PDF 를 만든다 (1회성, 2026-10-23).

적재 파이프라인은 PDF 만 받는다(추출·원문 뷰어·표지 모두 PDF). books.json 의 kind 에 따라
- txt: 원문을 다듬어(잡음 줄 빼기·영어는 문단 안 줄 잇기) 표지 쪽 + 본문 PDF 로 그린다. 한국어 원문은 인쇄본을 옮긴 것이라
  낱말 중간에서 줄이 끊겨 있어 잇지 않고 줄을 그대로 둔다(이으면 낱말이 붙거나 갈린다). 섹션은 추출 뒤 의미 경계로 나뉘므로
  (stages.split_into_sections → semantic_chunk) 장 제목은 원문 뷰어에서 읽기 좋게 굵게만 한다.
- pdf: 고른 쪽만 옮긴다(금도끼는 2·3쪽이 위키문헌 라이선스라 1쪽만).
만든 PDF 는 다시 글자를 뽑아 원문과 맞춰 본다 — 원문 40자 조각 300개가 PDF 글자에 그대로 있는 비율(coverage), 길이 비율,
그리지 못한 글자(PUA 를 바꾼 □)를 out/report.json 에 남긴다. 결과물은 out/upload/ 에 모아(서버로 그대로 옮긴다) books.json·
stage_books.py 와 함께 둔다.

    python render_pdfs.py            # out/upload/pdf/<id>.pdf, out/upload/books.json, out/report.json
    python render_pdfs.py PSN-SONAGI # 한 권만
"""
import html
import io
import json
import random
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
UPLOAD = OUT / "upload"
FONT_DIR = "C:/Windows/Fonts"
MEDIABOX = fitz.paper_rect("a4")
WHERE = MEDIABOX + (60, 64, -60, -64)
sys.stdout.reconfigure(encoding="utf-8")

CSS = """
@font-face { font-family: body; src: url(malgun.ttf); }
@font-face { font-family: body; font-weight: bold; src: url(malgunbd.ttf); }
* { font-family: body; }
body { font-size: 10.5pt; line-height: 1.55; }
p { margin: 0 0 6pt 0; text-align: justify; }
h2 { font-size: 13pt; font-weight: bold; margin: 14pt 0 8pt 0; }
.t-title { font-size: 26pt; font-weight: bold; text-align: center; margin-top: 180pt; }
.t-orig { font-size: 13pt; text-align: center; margin-top: 10pt; }
.t-author { font-size: 14pt; text-align: center; margin-top: 36pt; }
.t-year { font-size: 12pt; text-align: center; margin-top: 6pt; }
.t-note { font-size: 9pt; text-align: center; margin-top: 160pt; color: #555555; }
"""
PUA = re.compile("[\ue000-\uf8ff]")
# \uae00\uaf34\uc5d0 \uc788\uc5b4\ub3c4 PDF \uc5d0\uc11c \ub2e4\uc2dc \ubf51\uc73c\uba74 NUL(0x00)\ub85c \ub098\uc624\ub294 \uae00\uc790 \u2014 \ub9cc\uc138\uc804\u00b7\ud5c8\uc0dd\uc804\uc758 \uac00\uc6b4\ub383\uc810 '\u2024'(U+2024). \ub300\ub7c9 \uc801\uc7ac\uc5d0\uc11c NUL \uc774 \ub4e0
# \ubcf8\ubb38\uc740 DB \uc800\uc7a5\uc774 \uc2e4\ud328\ud588\ub2e4('A string literal cannot contain NUL') \u2014 \uac19\uc740 \ub73b\uc758 \uae00\uc790\ub85c \ubc14\uafd4 \uadf8\ub9b0\ub2e4
FOLD = str.maketrans({"\u2024": "\u00b7"})
CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]")
HEADING = [re.compile(p) for p in (
    r"^(CHAPTER|Chapter|PART|Part|BOOK|Book|STAVE|LETTER|PREFACE|INTRODUCTION|PROLOGUE|EPILOGUE)\b.{0,80}$",
    r"^[IVXLC]{1,7}\.?$",
    r"^\d{1,3}\.?$",
    r"^제\s*\d+\s*[장단부편회절권].{0,40}$",
)]
ALLCAPS = re.compile(r"^(?=.*[A-Z])[^a-z]{3,80}$")
LIGATURES = re.compile("[\ufb00-\ufb06]")


def clean(text: str, book: dict) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if book.get("drop_until"):
        cut = next(i for i, line in enumerate(lines) if book["drop_until"] in line)
        lines = lines[cut + 1:]
    strips = [re.compile(p) for p in book.get("strip", [])]
    out, skipping = [], False
    for line in lines:
        if skipping:                      # 여러 줄짜리 [Illustration: …] 블록
            skipping = "]" not in line
            continue
        if re.match(r"^\s*\[Illustration", line) and "]" not in line:
            skipping = True
            continue
        if any(p.search(line) for p in strips):
            continue
        out.append(PUA.sub("□", line.rstrip()).translate(FOLD))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def is_heading(line: str, lang: str) -> bool:
    s = line.strip()
    if not s or len(s) > 90:
        return False
    if any(p.match(s) for p in HEADING):
        return True
    return lang == "eng" and bool(ALLCAPS.match(s))


def items(text: str, book: dict) -> list[tuple[str, str]]:
    """('h'|'p', 글) 목록. 영어는 문단(빈 줄로 나뉨) 안의 줄을 잇는다. 제목 후보가 셋 이상 잇따르면 목차라 본문으로 둔다."""
    out: list[tuple[str, str]] = []
    for para in text.split("\n\n"):
        lines = [line.strip() for line in para.split("\n") if line.strip()]
        if not lines:
            continue
        if book.get("join_wrapped"):
            if len(lines) == 1 and is_heading(lines[0], book["lang"]):
                out.append(("h", lines[0]))
            else:
                out.append(("p", " ".join(lines)))
            continue
        buf: list[str] = []
        for line in lines:
            if is_heading(line, book["lang"]):
                if buf:
                    out.append(("p", "\n".join(buf)))
                    buf = []
                out.append(("h", line))
            else:
                buf.append(line)
        if buf:
            out.append(("p", "\n".join(buf)))
    i = 0
    while i < len(out):                   # 목차: 제목 후보가 셋 이상 잇따르면 본문으로
        j = i
        while j < len(out) and out[j][0] == "h":
            j += 1
        if j - i >= 3:
            for k in range(i, j):
                out[k] = ("p", out[k][1])
        i = max(j, i + 1)
    return out


def esc(s: str) -> str:
    return html.escape(s).replace("\n", "<br/>")


def write_story(writer, story) -> int:
    pages, more = 0, True
    while more:
        dev = writer.begin_page(MEDIABOX)
        more, _ = story.place(WHERE)
        story.draw(dev)
        writer.end_page()
        pages += 1
    return pages


def render_txt(book: dict, src: Path, dst: Path) -> dict:
    text = clean(src.read_text(encoding="utf-8"), book)
    parts = items(text, book)
    archive = fitz.Archive(FONT_DIR)
    title_html = (f'<p class="t-title">{esc(book["title"])}</p>'
                  + (f'<p class="t-orig">{esc(book["title_remainder"])}</p>' if book.get("title_remainder") else "")
                  + f'<p class="t-author">{esc(book["author"])}</p>'
                  + (f'<p class="t-year">{esc(book["pub_date"])}</p>' if book.get("pub_date") else "")
                  + '<p class="t-note">SKOVIX 소장자료 원문 — 페르소나 에이전트 원문 보관본(2026-10-20)에서 옮김</p>')
    body_html = "".join(f"<h2>{esc(t)}</h2>" if k == "h" else f"<p>{esc(t)}</p>" for k, t in parts)
    buf = io.BytesIO()                     # 임시 파일 없이 — Windows 에서 쓰개가 파일을 쥐고 놓지 않았다
    writer = fitz.DocumentWriter(buf)
    write_story(writer, fitz.Story(html=title_html, user_css=CSS, archive=archive))
    write_story(writer, fitz.Story(html=body_html, user_css=CSS, archive=archive))
    writer.close()
    doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
    doc.set_metadata({"title": book["title"], "author": book["author"], "subject": book.get("title_remainder", ""),
                      "creator": "SKOVIX persona-books-ingest", "producer": "PyMuPDF"})
    try:
        doc.subset_fonts()
    except Exception as e:                 # fontTools 가 없으면 글꼴을 통째로 넣는다(파일만 커진다)
        print(f"  [{book['id']}] 글꼴 줄이기 건너뜀: {e}")
    doc.save(dst, garbage=3, deflate=True)
    doc.close()
    return {"source_chars": len(text), "headings": sum(1 for k, _ in parts if k == "h"), "pua_replaced": text.count("□"),
            "_text": text}


def render_pdf(book: dict, src: Path, dst: Path) -> dict:
    doc = fitz.open(src)
    pages = book.get("pages", "all")
    if pages != "all":
        doc.select([p - 1 for p in pages])
    meta = dict(doc.metadata or {})
    meta.update({"title": book["title"], "author": book["author"]})
    doc.set_metadata(meta)
    doc.save(dst, garbage=3, deflate=True)
    doc.close()
    return {}


def verify(dst: Path, info: dict, kind: str) -> dict:
    doc = fitz.open(dst)
    start = 1 if kind == "txt" else 0      # txt 는 1쪽이 표지
    pdf_text = "".join(doc[i].get_text() for i in range(start, doc.page_count))
    res = {"pages": doc.page_count, "pdf_chars": len(pdf_text), "ligatures": len(LIGATURES.findall(pdf_text)),
           "control_chars": len(CONTROL.findall(pdf_text)),
           "empty_pages": sum(1 for i in range(start, doc.page_count) if len(doc[i].get_text().strip()) < 20),
           "size_kb": round(dst.stat().st_size / 1024)}
    doc.close()
    if kind == "txt":
        norm = lambda s: re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))  # noqa: E731
        a, b = norm(info["_text"]), norm(pdf_text)
        rng = random.Random(len(a))
        n, hits = 300, 0
        for _ in range(n):
            i = rng.randrange(0, max(1, len(a) - 40))
            hits += a[i:i + 40] in b
        res.update(coverage=round(hits / n, 3), length_ratio=round(len(b) / max(1, len(a)), 3))
    return res


def main() -> None:
    cfg = json.loads((HERE / "books.json").read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    (UPLOAD / "pdf").mkdir(parents=True, exist_ok=True)
    report_path = OUT / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    for book in cfg["books"]:
        if only and book["id"] not in only:
            continue
        src = Path(cfg["src_root"][book["kind"]]) / book["src"]
        dst = UPLOAD / "pdf" / f"{book['id']}.pdf"
        info = render_txt(book, src, dst) if book["kind"] == "txt" else render_pdf(book, src, dst)
        res = {**{k: v for k, v in info.items() if not k.startswith("_")}, **verify(dst, info, book["kind"])}
        report[book["id"]] = res
        print(book["id"], json.dumps(res, ensure_ascii=False))
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy(HERE / "books.json", UPLOAD / "books.json")
    if (HERE / "stage_books.py").exists():
        shutil.copy(HERE / "stage_books.py", UPLOAD / "stage_books.py")


if __name__ == "__main__":
    main()
