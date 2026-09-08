"""cell_fill_analysis.py — ODL 마크다운의 표 격자를 파싱해 셀 충전율을 잰다.

배경: MarkdownGenerator.writeTable() 은 탐지된 격자 크기만으로 구분자를 쓰므로
구조 문자 수 = (행+1)x(열+1) + 3x열 이며 내용과 무관하다. 따라서 글자 수 대신
격자를 세면 오판을 직접 탐지할 수 있다.

검증할 가설:
  H1. 재배정 페이지는 셀 충전율이 낮다.
  H2. 구조 문자를 제거하는 현재 수정안은 '셀마다 2~3자씩 남는 부분 디코딩'을 놓친다.
      셀당 문자 수가 낮으면 총합은 임계값을 넘어도 실제로는 파편이다.
"""
import io, json, re, statistics as st, sys

DUMP = "scripts/odl_text_dump.json"
AUDIT = "scripts/audit_routing_policy200.json"
_STRUCT = str.maketrans("", "", "|-: \t\n\r")

def parse_tables(md):
    """마크다운에서 표 블록을 찾아 (셀 수, 내용 있는 셀 수, 셀 문자 합)을 낸다."""
    cells = filled = cell_chars = 0
    for line in md.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        if set(s) <= set("|-: "):        # 구분행
            continue
        parts = s.split("|")[1:-1]       # 양끝 파이프 제외
        for c in parts:
            cells += 1
            t = c.strip()
            if t:
                filled += 1
                cell_chars += len(t)
    return cells, filled, cell_chars

def nontable_chars(md):
    return len("".join(l for l in md.split("\n")
                       if not l.strip().startswith("|")).translate(_STRUCT))

def main():
    dump = json.load(io.open(DUMP, encoding="utf-8"))
    a = json.load(io.open(AUDIT, encoding="utf-8"))
    aud = {(r["file"], p["page"]): p for r in a if "all_pages" in r for p in r["all_pages"]}

    rows = []
    for rel, grp in dump.items():
        for kind, pages in grp.items():
            for pg, md in pages.items():
                p = aud.get((rel, int(pg)))
                if p is None: continue
                cells, filled, cch = parse_tables(md)
                rows.append({
                    "doc": rel.split("/")[0], "page": int(pg), "kind": kind,
                    "odl_body": p["new_len"], "cells": cells, "filled": filled,
                    "fill_rate": filled/cells if cells else None,
                    "chars_per_filled": cch/filled if filled else None,
                    "cell_chars": cch, "nontable": nontable_chars(md)})

    json.dump(rows, io.open("scripts/cell_fill.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    tab = [r for r in rows if r["cells"]]
    print("문서 %d건 / 페이지 %d쪽 (표가 있는 쪽 %d)" % (len(dump), len(rows), len(tab)))

    print("\n[H1] 셀 충전율")
    for kind in ("reroute", "control"):
        g = [r for r in tab if r["kind"] == kind]
        if not g: continue
        print("  %-8s n=%3d  셀 수 중앙값 %4.0f  충전율 중앙값 %.3f  셀당 문자 %.1f" %
              (kind, len(g), st.median([r["cells"] for r in g]),
               st.median([r["fill_rate"] for r in g]),
               st.median([r["chars_per_filled"] or 0 for r in g])))

    print("\n[H2] 현재 수정안(본문>=50자)이 통과시킨 쪽 중 파편 의심")
    passed = [r for r in tab if r["odl_body"] >= 50 and r["cells"] >= 50]
    frag = [r for r in passed if (r["chars_per_filled"] or 99) < 4]
    print("  표 50셀 이상 + 본문 50자 이상 통과: %d쪽" % len(passed))
    print("  그중 셀당 문자 4자 미만(파편 의심):  %d쪽" % len(frag))
    for r in sorted(frag, key=lambda x: x["chars_per_filled"])[:10]:
        print("    %-22s p.%-4d 본문 %4d자  셀 %4d  충전 %.2f  셀당 %.1f자" %
              (r["doc"][:22], r["page"], r["odl_body"], r["cells"],
               r["fill_rate"], r["chars_per_filled"]))

if __name__ == "__main__":
    main()
