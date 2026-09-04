"""json_cell_stats2.py — JSON 출력 기준 표 셀 충전율을 전수(200건) 집계.

마크다운을 파싱해 추정한 충전율(0.973)과 JSON 에서 실측한 값(0.015)이 60배 달랐다.
평탄화된 형식에서는 파편·공백을 '내용 있음'으로 오인하기 때문이다.
JSON 에서는 'table cell' 객체의 kids 가 비었는지로 곧바로 판정된다.

JSON 원문은 페이지당 50KB 수준이라 저장하지 않고 실행 중에 통계만 남긴다.
"""
import io, json, os, sys
from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader

SAMPLE = "scripts/policy_sample200.txt"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
OUT = "scripts/json_cell_stats2.json"

def collect(o, acc):
    """타입별 개수와 표 셀 충전 상태를 모은다."""
    if isinstance(o, dict):
        t = o.get("type")
        if t:
            acc["types"][t] = acc["types"].get(t, 0) + 1
        if t == "table":
            # 운영 코드(extractor.py)는 페이지에 표가 여럿이면 min(충전율)을 쓴다.
            # 합산 충전율과 갈리므로 표 단위로 따로 센다.
            tot = fil = 0
            for row in o.get("rows", []):
                for cell in row.get("cells", []):
                    tot += 1
                    if cell.get("kids"):
                        fil += 1
            if tot:
                acc["tables"].append([tot, fil])
        if t == "table cell":
            acc["cells"] += 1
            kids = o.get("kids") or []
            if kids:
                acc["filled"] += 1
                buf = []
                text_of(kids, buf)
                acc["cell_chars"] += len("".join(buf).strip())
        for v in o.values():
            collect(v, acc)
    elif isinstance(o, list):
        for v in o:
            collect(v, acc)

def text_of(o, buf):
    if isinstance(o, dict):
        for k in ("text", "value", "content"):
            if isinstance(o.get(k), str):
                buf.append(o[k])
        for v in o.values():
            text_of(v, buf)
    elif isinstance(o, list):
        for v in o:
            text_of(v, buf)

def main():
    names = [l.strip() for l in io.open(SAMPLE, encoding="utf-8") if l.strip()]
    res = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for i, rel in enumerate(names, 1):
        if rel in res:
            continue
        try:
            docs = OpenDataLoaderPDFLoader(
                file_path=BASE + rel, format="json", image_output="off",
                table_method="cluster", split_pages=True,
                keep_line_breaks=False).load()
        except Exception as e:
            print("실패 %s: %s" % (rel, e), file=sys.stderr)
            res[rel] = []
            continue
        pages = []
        for d in docs:
            acc = {"types": {}, "cells": 0, "filled": 0, "cell_chars": 0, "tables": []}
            try:
                collect(json.loads(d.page_content), acc)
            except Exception:
                pass
            acc["page"] = d.metadata.get("page")
            pages.append(acc)
        res[rel] = pages
        json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
        print("[%d/%d] %s %d쪽" % (i, len(names), rel, len(pages)), file=sys.stderr)
    print("완료 %d문서" % len(res), file=sys.stderr)

if __name__ == "__main__":
    main()
