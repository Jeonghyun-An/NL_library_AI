"""cell_stats_full.py — 정책 코퍼스 전수(200건)의 페이지별 표 격자 통계.

H2 검증용: 구조 문자를 제거하는 현재 수정안이 통과시킨 쪽 가운데,
셀마다 파편만 남은 페이지가 있는지 보려면 통과한 쪽까지 전부 봐야 한다.
텍스트를 저장하지 않고 실행 중에 통계만 남긴다.
"""
import io, json, os, re, sys
from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader

SAMPLE = "scripts/policy_sample200.txt"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
OUT = "scripts/cell_stats_policy.json"
_IMG = re.compile(r'!\[[^\]]*\]\([^)]+\)')
_STRUCT = str.maketrans("", "", "|-: \t\n\r")

def clean(t):
    t = re.sub(r'\n{3,}', '\n\n', t)
    return re.sub(r' {2,}', ' ', '\n'.join(l.strip() for l in t.split('\n'))).strip()

def stats(md):
    cells = filled = cell_chars = 0
    tbl_lines = 0
    for line in md.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        tbl_lines += 1
        if set(s) <= set("|-: "):
            continue
        for c in s.split("|")[1:-1]:
            cells += 1
            t = c.strip()
            if t:
                filled += 1
                cell_chars += len(t)
    nontable = len("".join(l for l in md.split("\n")
                           if not l.strip().startswith("|")).translate(_STRUCT))
    body = len(md.replace("[그림]", "").translate(_STRUCT))
    return {"cells": cells, "filled": filled, "cell_chars": cell_chars,
            "table_lines": tbl_lines, "nontable": nontable, "body": body,
            "raw": len(md.replace("[그림]", "").strip())}

def main():
    names = [l.strip() for l in io.open(SAMPLE, encoding="utf-8") if l.strip()]
    res = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for i, rel in enumerate(names, 1):
        if rel in res:
            continue
        try:
            docs = OpenDataLoaderPDFLoader(
                file_path=BASE + rel, format="markdown", image_output="embedded",
                image_format="jpeg", table_method="cluster", split_pages=True,
                keep_line_breaks=False).load()
        except Exception as e:
            print("실패 %s: %s" % (rel, e), file=sys.stderr)
            res[rel] = []
            continue
        pages = []
        for d in docs:
            s = stats(clean(_IMG.sub('[그림]', d.page_content)))
            s["page"] = d.metadata.get("page")
            pages.append(s)
        res[rel] = pages
        json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
        print("[%d/%d] %s %d쪽" % (i, len(names), rel, len(pages)), file=sys.stderr)
    print("완료 %d문서 %d쪽" % (len(res), sum(len(v) for v in res.values())), file=sys.stderr)

if __name__ == "__main__":
    main()
