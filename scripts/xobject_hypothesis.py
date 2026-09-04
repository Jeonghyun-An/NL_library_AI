"""xobject_hypothesis.py — '텍스트가 Form XObject 안에 있으면 ODL 이 못 읽는다' 가설 검증.

실패 쪽의 페이지 Resources 에 /Font 가 없고 /XObject 만 있는 것을 관찰했다.
텍스트가 폼 안에 중첩되어 있다는 뜻이다. fitz 는 폼을 따라 들어가 읽지만
veraPDF 는 그러지 못하는 것으로 보인다. 이를 라벨된 전체 쪽에서 확인한다.
"""
import io, json, re, sys
import fitz

BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"

def page_kind(d, pno):
    """페이지 Resources 에 폰트가 직접 있는지, 폼 XObject 만 있는지."""
    xref = d[pno].xref
    res = d.xref_get_key(xref, "Resources")
    s = str(res[1]) if res and len(res) > 1 else ""
    if res and res[0] == "xref":                       # 간접 참조면 따라간다
        m = re.match(r'(\d+) 0 R', str(res[1]))
        if m:
            s = d.xref_object(int(m.group(1)))
    has_font = "/Font" in s
    has_form = "/XObject" in s
    return has_font, has_form

def main():
    fzns = json.load(io.open('scripts/fitz_nospace_policy.json', encoding='utf-8'))
    a = json.load(io.open('scripts/audit_routing_policy200.json', encoding='utf-8'))
    rows = []
    for r in a:
        if 'all_pages' not in r: continue
        rel = r['file']
        pm = {p['page']: p['fitz_ns'] for p in fzns.get(rel, [])}
        # fitz 가 읽어낸 쪽만 대상 (스캔 쪽은 이 가설과 무관)
        cand = [(p, pm.get(p['page'], 0)) for p in r['all_pages'] if pm.get(p['page'], 0) >= 200]
        if not cand: continue
        lab = [(p, f, 'fail' if p['new_len']/f < 0.10 else 'ok') for p, f in cand]
        if not any(x[2] == 'fail' for x in lab):
            lab = lab[:3]                              # 정상 문서는 표본만
        try:
            d = fitz.open(BASE + rel)
        except Exception:
            continue
        for p, f, kind in lab:
            hf, hx = page_kind(d, p['page'] - 1)
            rows.append({"doc": rel.split('/')[0], "page": p['page'], "kind": kind,
                         "has_font": hf, "has_xobject": hx,
                         "odl": p['new_len'], "fitz": f})
        d.close()
    json.dump(rows, io.open("scripts/xobject_check.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    for kind in ("fail", "ok"):
        g = [r for r in rows if r["kind"] == kind]
        if not g: continue
        nofont = sum(1 for r in g if not r["has_font"])
        print("[%s] %4d쪽 | /Font 없음(폼 안에 텍스트) %4d쪽 = %5.1f%%"
              % (kind, len(g), nofont, nofont / len(g) * 100))

if __name__ == "__main__":
    main()
