"""glyph_recovery_gap.py — ODL(veraPDF)과 fitz 의 글리프 복원 차이.

라우팅 정의와 무관한 기제 검증. 각 쪽에서 두 추출기가 낸 문자를 다중집합으로 비교해,
ODL 이 fitz 대비 무엇을 잃는지 본다. ODL 문자가 fitz 문자의 부분집합에 가깝다면
'표 셀 내용 누락'이 아니라 '글리프 매핑 실패'라는 진단이 지지된다.
"""
import collections, io, json, re, statistics as st
import fitz

DUMP = "scripts/odl_text_dump.json"
BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
_STRUCT = str.maketrans("", "", "|-: \t\n\r")

def main():
    dump = json.load(io.open(DUMP, encoding="utf-8"))
    rows = []
    for rel, grp in dump.items():
        d = fitz.open(BASE + rel)
        for kind, pages in grp.items():
            for pg, md in pages.items():
                n = int(pg)
                if n > len(d): continue
                oc = collections.Counter(md.replace("[그림]", "").translate(_STRUCT))
                fc = collections.Counter(re.sub(r'\s', '', d[n-1].get_text("text")))
                rows.append({
                    "doc": rel.split("/")[0], "page": n, "kind": kind,
                    "odl": sum(oc.values()), "fitz": sum(fc.values()),
                    "odl_only": sum((oc - fc).values()),
                    "fitz_only": sum((fc - oc).values())})
        d.close()
    json.dump(rows, io.open("scripts/glyph_gap.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("페이지 %d쪽\n" % len(rows))
    for kind in ("reroute", "control"):
        g = [r for r in rows if r["kind"] == kind]
        fz = [r for r in g if r["fitz"] >= 200]      # fitz 가 실제로 읽어낸 쪽만
        print("[%s] %d쪽 (그중 fitz 200자 이상 %d쪽)" % (kind, len(g), len(fz)))
        if not fz: continue
        print("    ODL %5.0f자  fitz %5.0f자   (중앙값)" %
              (st.median([r["odl"] for r in fz]), st.median([r["fitz"] for r in fz])))
        print("    fitz 에만 있는 문자(ODL 이 잃은 것) 중앙값 %5.0f자" %
              st.median([r["fitz_only"] for r in fz]))
        print("    ODL 에만 있는 문자(fitz 가 못 읽은 것) 중앙값 %5.0f자" %
              st.median([r["odl_only"] for r in fz]))
        rec = [r["odl"]/r["fitz"] for r in fz]
        print("    복원율 ODL/fitz 중앙값 %.2f\n" % st.median(rec))

    print("※ ODL 에만 있는 문자가 거의 없으면, ODL 출력은 fitz 출력의 부분집합이다")
    print("   = 표 셀 내용을 '놓친' 것이 아니라 글리프를 '못 읽은' 것이다.")

if __name__ == "__main__":
    main()
