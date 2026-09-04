"""cluster_failures.py — 재배정(오판) 페이지의 실패 원인 군집화용 특징 추출.

ODL 이 '본문 충분'으로 오판한 페이지와, 같은 문서에서 두 규칙이 일치 판정한 대조
페이지를 같은 특징 집합으로 기술한다. ODL 재실행이 필요 없는 fitz 측 특징만 먼저 뽑는다.

특징:
  fitz_len      fitz 가 읽은 본문량 — 문서 결함(CMap 손상) 여부의 지표
  struct_chars  ODL 산출물의 구조 문자 수(원시 − 본문) — 오판을 일으킨 양
  w, h, ratio   페이지 기하 — 양면(2-up) 배치 여부
  drawings      벡터 도형 수 — 표 테두리 밀도
  images        이미지 수 — 스캔/도판 여부
  fonts         쪽에 쓰인 폰트 수
"""
import io, json, os, sys
import fitz

AUDIT = "scripts/audit_routing_policy200.json"
FITZ = "scripts/fitz_lengths_policy200.json"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
OUT = "scripts/failure_features.json"

def main():
    a = json.load(io.open(AUDIT, encoding="utf-8"))
    fl = {(r["file"], p["page"]): (p["fitz_len"] or 0)
          for r in json.load(io.open(FITZ, encoding="utf-8")) if "pages" in r
          for p in r["pages"]}

    # 처리군 = 재배정 쪽, 대조군 = 같은 문서에서 두 규칙 일치 + 본문 충분
    targets = {}
    for r in a:
        if "all_pages" not in r: continue
        rer = [p for p in r["all_pages"] if p["rerouted"]]
        if not rer: continue
        ctl = [p for p in r["all_pages"]
               if p["old_route"] == "stage1" and p["new_route"] == "stage1"][:len(rer)]
        targets[r["file"]] = [("reroute", p) for p in rer] + [("control", p) for p in ctl]

    rows = []
    for i, (rel, items) in enumerate(targets.items(), 1):
        try:
            doc = fitz.open(BASE + rel)
        except Exception as e:
            print("열기 실패 %s: %s" % (rel, e), file=sys.stderr); continue
        for kind, p in items:
            n = p["page"]
            if n > len(doc): continue
            pg = doc[n - 1]
            r = pg.rect
            txt = pg.get_text("text")
            rows.append({
                "doc": os.path.basename(rel), "page": n, "kind": kind,
                "fitz_len": fl.get((rel, n), 0),
                "odl_raw": p["old_len"], "odl_body": p["new_len"],
                "struct_chars": p["old_len"] - p["new_len"],
                "w": round(r.width), "h": round(r.height),
                "ratio": round(r.width / r.height, 2),
                "drawings": len(pg.get_drawings()),
                "images": len(pg.get_images()),
                "fonts": len(set(s["font"] for b in pg.get_text("dict")["blocks"]
                                 if b.get("type") == 0 for l in b["lines"] for s in l["spans"])),
                "pagenum_marks": txt.count("[ 1") + txt.count("[ 2"),
            })
        doc.close()
        print("[%d/%d] %s" % (i, len(targets), rel), file=sys.stderr)

    json.dump(rows, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("저장: %s (%d쪽)" % (OUT, len(rows)), file=sys.stderr)

if __name__ == "__main__":
    main()
