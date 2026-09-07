"""page_geometry_features.py — 정책 코퍼스 전수(11,473쪽)의 기하 특징.

오판 탐지 규칙을 코퍼스 전체에서 평가하기 위한 것. 벡터 선 수(표 테두리 밀도),
이미지 수, 폰트 수, 페이지 크기를 쪽마다 기록한다. ODL 재실행 없이 fitz 만 쓴다.
"""
import io, json, os, sys
import fitz

SAMPLE = "scripts/policy_sample200.txt"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
OUT = "scripts/page_geometry_policy.json"

def main():
    names = [l.strip() for l in io.open(SAMPLE, encoding="utf-8") if l.strip()]
    res = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for i, rel in enumerate(names, 1):
        if rel in res:
            continue
        try:
            d = fitz.open(BASE + rel)
        except Exception as e:
            print("실패 %s: %s" % (rel, e), file=sys.stderr); continue
        pages = []
        for n, pg in enumerate(d, 1):
            try:
                nd = len(pg.get_drawings())
            except Exception:
                nd = -1
            blocks = pg.get_text("dict")["blocks"]
            fonts = set(s["font"] for b in blocks if b.get("type") == 0
                        for l in b["lines"] for s in l["spans"])
            pages.append({"page": n, "drawings": nd, "images": len(pg.get_images()),
                          "fonts": len(fonts),
                          "w": round(pg.rect.width), "h": round(pg.rect.height)})
        d.close()
        res[rel] = pages
        if i % 10 == 0 or i == len(names):
            json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print("[%d/%d] %d문서 저장" % (i, len(names), len(res)), file=sys.stderr)
    json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("완료: %d문서 %d쪽" % (len(res), sum(len(v) for v in res.values())), file=sys.stderr)

if __name__ == "__main__":
    main()
