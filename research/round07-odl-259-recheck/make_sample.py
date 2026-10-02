"""Build sample.json for the ODL 2.5.0 vs 2.5.9 comparison (one-off, scratch only)."""
import csv, json, os, random, sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "code", "research", "round07-ingest-regression", "docs.csv")
PDF = "D:/SKOVIX/KCI/pdf/{}.pdf"
MAX_PAGES = 120
BIG_OK = {"KCI_FI002252358"}

rows = list(csv.DictReader(open(DOCS, encoding="utf-8-sig")))
by_id = {}
for r in rows:
    by_id.setdefault(r["id"], r)  # first occurrence

rng = random.Random(20261002)
out, seen, skipped = [], set(), []


def exists(i):
    return os.path.isfile(PDF.format(i))


def pages_of(i):
    r = by_id.get(i)
    if r:
        return int(r["pages"])
    with fitz.open(PDF.format(i)) as d:
        return d.page_count


def add(i, group, why):
    if i in seen:
        return False
    if not exists(i):
        skipped.append((i, "missing"))
        return False
    p = pages_of(i)
    if p > MAX_PAGES and i not in BIG_OK:
        skipped.append((i, f"{p} pages"))
        return False
    r = by_id.get(i)
    scan = r["doc_is_scan"] if r else "?"
    out.append({"id": i, "group": group, "why": f"{why} [pages={p}, doc_is_scan={scan}]"})
    seen.add(i)
    return True


def fill(group, n, pred, why):
    pool = [r["id"] for r in rows if r["group"] == group and pred(r) and r["id"] not in seen]
    rng.shuffle(pool)
    k = 0
    for i in pool:
        if k >= n:
            break
        if add(i, group, why):
            k += 1


ip = lambda r, c: int(r[c])

# fail_block: 7 (scanned, stamp text only)
add("KCI_FI002029401", "fail_block", "named: 20 image-only pages, Nuri Media stamp only (old 0 OCR -> new 20)")
fill("fail_block", 6, lambda r: ip(r, "pages") <= 40, "scanned journal pre-2002, text layer = Nuri Media stamp only (old 0 OCR -> all pages OCR)")

# pre2005: 8 (4 scan / 4 non-scan)
add("KCI_FI000870623", "pre2005", "scan, old 0 OCR -> new 7 (stamp-only text layer), 6 image pages")
add("KCI_FI000895213", "pre2005", "scan, old 0 OCR -> new 14, no image pages")
add("KCI_FI000885711", "pre2005", "scan, partial: old 23 -> new 38 OCR pages")
add("KCI_FI001112773", "pre2005", "scan, 19/20 short pages, 8 image pages, OCR unchanged")
add("KCI_FI000937498", "pre2005", "non-scan, 5 CMap-2x pages (ODL < fitz)")
add("KCI_FI000954729", "pre2005", "non-scan, 1 page held by raw fitz length (image body + header text)")
add("KCI_FI001343434", "pre2005", "non-scan, 40 pages, 1 image page")
fill("pre2005", 1, lambda r: r["doc_is_scan"] == "False" and ip(r, "old_ocr") == 0 and ip(r, "pages") <= 40, "non-scan, random plain pre-2005 digital text")

# digital: 10
add("KCI_FI001314298", "digital", "scan after 2005, old 0 OCR -> new 31, 30 image pages")
add("KCI_FI001030932", "digital", "scan after 2005, old 0 OCR -> new 12")
add("KCI_FI001107507", "digital", "scan after 2005, old 0 OCR -> new 16")
add("KCI_FI001120928", "digital", "scan after 2005, old 18 -> new 22 OCR")
add("KCI_FI002961735", "digital", "non-scan, 3 image pages kept as ODL (no OCR)")
add("KCI_FI002309766", "digital", "non-scan, 1 image page, 1 OCR page")
add("KCI_FI001005886", "digital", "non-scan, 1 page held by raw fitz length")
add("KCI_FI002067020", "digital", "non-scan, 1 page held by raw fitz length")
fill("digital", 2, lambda r: r["doc_is_scan"] == "False" and ip(r, "old_ocr") == 0 and ip(r, "img_cover_pages") == 0 and ip(r, "pages") <= 40, "non-scan, random plain post-2005 digital paper")

# short_front: 8 (image covers / short front pages)
add("KCI_FI003145254", "short_front", "8 short pages, 1 image page, 4 OCR")
add("KCI_FI001618766", "short_front", "short front, 1 image cover page")
add("KCI_FI002675501", "short_front", "short front, 1 image cover page")
add("KCI_FI001127976", "short_front", "8 short pages, none OCR'd")
add("KCI_FI003315691", "short_front", "54 pages, 3 short, 2 OCR")
add("KCI_FI003274665", "short_front", "42 pages, 3 short, 2 OCR")
add("KCI_FI001827561", "short_front", "60 pages, short front, 1 OCR")
add("KCI_FI001037448", "short_front", "2 short front pages, none OCR'd")
fill("short_front", 8 - sum(1 for o in out if o["group"] == "short_front"), lambda r: True, "short front pages (random fill)")

# br_grid: 2
add("KCI_FI001930485", "br_grid", "named: 37 pages, table-heavy, <br> empty grid under ODL embedded")
add("KCI_FI000897237", "br_grid", "named: scan with table grid (<br> grid under ODL embedded)")

# named / known cases
add("KCI_FI000858284", "named_cases", "14 pages, many images")
add("KCI_FI002990049", "named_cases", "15 tables (table fill ratio path)")
add("KCI_FI003011274", "named_cases", "image-body pages with header text (held by raw fitz length)")
add("KCI_FI002252358", "named_cases", "316 pages, image cover (24 chars) must stay ODL")
add("KCI_FI001343547", "named_cases", "<br> CMap case (pages 2 and 13 go OCR via CMap 2x after <br> removal)")
add("KCI_FI001141801", "named_cases", "named case: short front, 1 image page, 1 held by raw")
add("KCI_FI001238691", "named_cases", "named case: scan document")
add("KCI_FI002025246", "named_cases", "named case in docs.csv: scan, 14/14 image pages")
add("KCI_FI001667569", "named_cases", "named case in docs.csv: 1 CMap page, 3 held by raw")
add("KCI_FI001158431", "named_cases", "named case in docs.csv: short front, 3 held by raw")

json.dump(out, open(os.path.join(HERE, "sample.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print("count", len(out), Counter(o["group"] for o in out))
print("total pages", sum(pages_of(o["id"]) for o in out))
print("skipped", skipped)
