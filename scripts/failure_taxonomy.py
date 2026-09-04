"""failure_taxonomy.py — 실패 쪽마다 원인을 귀속시킨다 (페이지가 실제로 쓰는 폰트 기준).

문서 단위로는 판별되지 않았다 — 정상 문서도 오버플로 bfrange 를 1,200개 넘게 갖는다.
그래서 '그 페이지가 실제로 참조하는 폰트'에 조건이 걸리는지를 본다.

원인 후보:
  A. 폼 중첩   페이지 Resources 에 /Font 가 없고 /XObject 만 있다 (텍스트가 Form XObject 안)
  B. CMap 부재 그 쪽이 쓰는 폰트에 ToUnicode 가 없다
  C. CMap 결손 그 쪽이 쓰는 폰트의 ToUnicode 에 오버플로 bfrange 가 있다
     (veraPDF 가 'last byte incremented past 255' 로 버리는 구간)
"""
import io, json, re, sys
import fitz

BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
BFRANGE = re.compile(rb'beginbfrange(.*?)endbfrange', re.S)
TRIPLE = re.compile(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>')

def tounicode_state(d, xref, cache):
    """폰트 xref -> ('none'|'ok'|'overflow', 오버플로 구간 수)"""
    if xref in cache:
        return cache[xref]
    obj = d.xref_object(xref)
    m = re.search(r'/ToUnicode\s+(\d+)\s+\d+\s+R', obj)
    if not m:
        cache[xref] = ("none", 0); return cache[xref]
    try:
        s = d.xref_stream(int(m.group(1)))
    except Exception:
        cache[xref] = ("none", 0); return cache[xref]
    bad = 0
    for blk in BFRANGE.findall(s):
        for lo, hi, dst in TRIPLE.findall(blk):
            span = int(hi, 16) - int(lo, 16)
            if span > 0 and int(dst[-2:], 16) + span > 0xFF:
                bad += 1
    cache[xref] = (("overflow" if bad else "ok"), bad)
    return cache[xref]

def has_direct_font(d, pno):
    res = d.xref_get_key(d[pno].xref, "Resources")
    s = str(res[1]) if res and len(res) > 1 else ""
    if res and res[0] == "xref":
        m = re.match(r'(\d+) 0 R', str(res[1]))
        if m:
            s = d.xref_object(int(m.group(1)))
    return "/Font" in s

def classify(d, pno, cache):
    if not has_direct_font(d, pno):
        return "A 폼 중첩"
    states = [tounicode_state(d, f[0], cache)[0] for f in d.get_page_fonts(pno)]
    if not states:
        return "A 폼 중첩"
    if all(s == "none" for s in states):
        return "B CMap 부재"
    if any(s == "overflow" for s in states):
        return "C CMap 결손"
    if any(s == "none" for s in states):
        return "B CMap 부재"
    return "정상 폰트"

def main():
    fzns = json.load(io.open('scripts/fitz_nospace_policy.json', encoding='utf-8'))
    a = json.load(io.open('scripts/audit_routing_policy200.json', encoding='utf-8'))
    rows = []
    for r in a:
        if 'all_pages' not in r: continue
        rel = r['file']
        pm = {p['page']: p['fitz_ns'] for p in fzns.get(rel, [])}
        cand = [(p, pm.get(p['page'], 0)) for p in r['all_pages'] if pm.get(p['page'], 0) >= 200]
        if not cand: continue
        lab = [(p, f, 'fail' if p['new_len'] / f < 0.10 else 'ok') for p, f in cand]
        if not any(x[2] == 'fail' for x in lab):
            lab = lab[:4]
        try:
            d = fitz.open(BASE + rel)
        except Exception:
            continue
        cache = {}
        for p, f, kind in lab:
            rows.append({"doc": rel.split('/')[0], "page": p['page'], "kind": kind,
                         "cause": classify(d, p['page'] - 1, cache),
                         "odl": p['new_len'], "fitz": f,
                         "passed_fix": p['new_route'] == 'stage1'})
        d.close()
    json.dump(rows, io.open("scripts/failure_taxonomy.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    import collections
    for kind in ("fail", "ok"):
        g = [r for r in rows if r["kind"] == kind]
        c = collections.Counter(r["cause"] for r in g)
        print("\n[%s] %d쪽" % (kind, len(g)))
        for k, v in c.most_common():
            print("   %-12s %4d쪽 (%5.1f%%)" % (k, v, v / len(g) * 100))

if __name__ == "__main__":
    main()
