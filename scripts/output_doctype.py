"""output_doctype.py — SKOVIX/output 200건의 운영 doc_type 분류.

MARC/MODS 메타데이터에서 KDC 분류기호와 장르를 뽑아, 운영 코드
app/domains/nl_library/doc_types.py 의 detect_doc_type() 과 동일한 규칙으로 유형을 정한다.
"""
import csv, glob, io, json, os, re, sys
csv.field_size_limit(10**9)

META = "C:/Users/LANDSOFT/Desktop/SKOVIX/도서정보/"
PDFS = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
OUT = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/output_doctype.json"

def load_meta():
    m = {}
    for f in sorted(glob.glob(META + "marc_mods-*.csv")):
        if os.path.basename(f).startswith("~$"):
            continue
        with io.open(f, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                # 파일마다 헤더가 다르다: 제어번호/MODS 와 CONTENTS_ID/CONTENTS_XML.
                cid = (row.get("제어번호") or row.get("CONTENTS_ID") or "").strip()
                if cid:
                    m[cid] = (row.get("MARC") or "",
                              row.get("MODS") or row.get("CONTENTS_XML") or "")
    return m

def kdc_of(mods, marc):
    for pat in (r'<classification[^>]*authority="KDC"[^>]*>([^<]+)<',
                r'<classification[^>]*>([\d.]+)<'):
        g = re.search(pat, mods)
        if g:
            return g.group(1).strip()
    g = re.search(r'\x1f' + r'a([\d.]+)', marc)
    return g.group(1).strip() if g else ""

def genre_of(mods):
    return " ".join(re.findall(r'<genre[^>]*>([^<]+)<', mods))

def detect(kdc, genre):
    """운영 detect_doc_type() 과 동일한 판정 순서."""
    if any(k in genre for k in ("학위논문", "논문", "학술", "보고서", "연구")):
        return "paper"
    try:
        head = int(float(kdc))
    except ValueError:
        return "book"
    if 800 <= head <= 899:
        return "literature"
    if 320 <= head <= 359:
        return "policy"
    return "book"

def main():
    meta = load_meta()
    print("메타데이터 %d건 로드" % len(meta), file=sys.stderr)
    rows = []
    for p in sorted(glob.glob(PDFS + "*/*.pdf")):
        cid = os.path.splitext(os.path.basename(p))[0].rstrip("_")
        marc, mods = meta.get(cid, ("", ""))
        kdc, genre = kdc_of(mods, marc), genre_of(mods)
        rows.append({"file": os.path.basename(p), "cid": cid, "kdc": kdc,
                     "genre": genre, "doc_type": detect(kdc, genre),
                     "meta_found": bool(marc or mods)})
    json.dump(rows, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    print("\n메타데이터 매칭: %d/%d건" % (sum(r["meta_found"] for r in rows), len(rows)))
    print("\ndoc_type 분포:")
    for t, c in Counter(r["doc_type"] for r in rows).most_common():
        print("  %-12s %3d건" % (t, c))
    print("\nKDC 상위 분포:")
    for k, c in Counter((r["kdc"] or "(없음)")[:3] for r in rows).most_common(10):
        print("  %-8s %3d건" % (k, c))
    print("\n장르 분포:")
    for g, c in Counter(r["genre"] or "(없음)" for r in rows).most_common(8):
        print("  %-24s %3d건" % (g[:24], c))

if __name__ == "__main__":
    main()
