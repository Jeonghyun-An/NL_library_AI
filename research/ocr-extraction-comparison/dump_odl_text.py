"""dump_odl_text.py — 재배정·대조 페이지의 ODL 산출 텍스트를 저장 (프로젝트 .venv 에서 실행).

fitz 와 한 프로세스에서 못 돌리므로, 텍스트만 뽑아두고 비교는 measure_glyph_loss.py 가 한다.
"""
import io, json, os, re, sys
from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader

AUDIT = "scripts/audit_routing_policy200.json"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
OUT = "scripts/odl_text_dump.json"
_IMG = re.compile(r'!\[[^\]]*\]\([^)]+\)')

def clean(t):
    t = re.sub(r'\n{3,}', '\n\n', t)
    return re.sub(r' {2,}', ' ', '\n'.join(l.strip() for l in t.split('\n'))).strip()

def main():
    a = json.load(io.open(AUDIT, encoding="utf-8"))
    targets = {}
    for r in a:
        if "all_pages" not in r: continue
        rer = [p["page"] for p in r["all_pages"] if p["rerouted"]]
        if not rer: continue
        ctl = [p["page"] for p in r["all_pages"]
               if p["old_route"] == "stage1" and p["new_route"] == "stage1"][:len(rer)]
        targets[r["file"]] = {"reroute": sorted(rer), "control": sorted(ctl)}

    res = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for i, (rel, grp) in enumerate(targets.items(), 1):
        if rel in res:
            continue
        docs = OpenDataLoaderPDFLoader(
            file_path=BASE + rel, format="markdown", image_output="embedded",
            image_format="jpeg", table_method="cluster", split_pages=True,
            keep_line_breaks=False).load()
        byp = {d.metadata.get("page"): clean(_IMG.sub('[그림]', d.page_content)) for d in docs}
        res[rel] = {k: {str(p): byp.get(p, "") for p in v} for k, v in grp.items()}
        json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
        print("[%d/%d] %s" % (i, len(targets), rel), file=sys.stderr)
    print("완료 %d문서" % len(res), file=sys.stderr)

if __name__ == "__main__":
    main()
