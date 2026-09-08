"""font_forensics.py — 실패 문서와 정상 문서의 폰트·ToUnicode CMap 비교.

veraPDF 는 다음 경고를 낸다:
  'Incorrect bfrange in toUnicode CMap: the last byte of the string incremented past 255'
bfrange 는 <시작코드> <끝코드> <시작유니코드> 형식으로 코드 구간을 매핑하는데,
끝코드까지 증가시키는 동안 목적지 문자열의 마지막 바이트가 255 를 넘으면
veraPDF 는 그 구간 전체를 버린다. 그 결과 해당 글리프가 유니코드로 매핑되지 않는다.

이 스크립트는 문서별로 (1) 폰트 종류·인코딩, (2) ToUnicode 유무,
(3) 위 오버플로 bfrange 개수를 센다.
"""
import io, json, re, sys
import fitz

BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
BFRANGE = re.compile(rb'beginbfrange(.*?)endbfrange', re.S)
TRIPLE = re.compile(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>')

def analyze_tounicode(stream):
    """오버플로 bfrange 수와 전체 bfrange 수를 센다."""
    total = bad = 0
    for blk in BFRANGE.findall(stream):
        for lo, hi, dst in TRIPLE.findall(blk):
            total += 1
            span = int(hi, 16) - int(lo, 16)
            if span <= 0:
                continue
            last = int(dst[-2:], 16)          # 목적지 문자열의 마지막 바이트
            if last + span > 0xFF:
                bad += 1
    return total, bad

def doc_report(path):
    d = fitz.open(path)
    fonts, seen = [], set()
    for pno in range(len(d)):
        for f in d.get_page_fonts(pno):
            xref, ext, ftype, basefont, name, enc = f[0], f[1], f[2], f[3], f[4], f[5]
            if xref in seen:
                continue
            seen.add(xref)
            obj = d.xref_object(xref)
            m = re.search(r'/ToUnicode\s+(\d+)\s+\d+\s+R', obj)
            total = bad = None
            if m:
                try:
                    total, bad = analyze_tounicode(d.xref_stream(int(m.group(1))))
                except Exception:
                    total, bad = -1, -1
            fonts.append({"basefont": basefont, "type": ftype, "encoding": enc,
                          "has_tounicode": bool(m), "bfranges": total, "overflow": bad})
    d.close()
    return fonts

def main():
    targets = json.load(io.open("scripts/font_targets.json", encoding="utf-8"))
    out = {}
    for label, rels in targets.items():
        for rel in rels:
            fonts = doc_report(BASE + rel)
            out[rel] = {"label": label, "fonts": fonts}
            ov = sum(f["overflow"] or 0 for f in fonts)
            nt = sum(1 for f in fonts if not f["has_tounicode"])
            print("[%s] %-26s 폰트 %2d개  ToUnicode없음 %d  오버플로 bfrange %d"
                  % (label, rel.split("/")[0][:26], len(fonts), nt, ov), file=sys.stderr)
    json.dump(out, io.open("scripts/font_forensics.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
