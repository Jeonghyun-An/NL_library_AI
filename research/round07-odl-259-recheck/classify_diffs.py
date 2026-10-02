"""classify_diffs.py - one-off: classify 2.5.0 vs 2.5.9 ODL page-text differences from compare_runs/texts.

Peels off the known 2.5.9 output changes in order and reports which pages need which ones to become identical.
Writes classify_diffs.json next to this script.
"""
import collections
import difflib
import html
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
s = json.load(open(BASE / "compare_summary.json", encoding="utf-8"))
LIST_MARK = re.compile(r"(?m)^- [*※]+ ?")
SPACE_PUNCT = re.compile(r" +(?=[,(])")


def norm_list(t):
    return LIST_MARK.sub("- ", t)


def norm_space(t):
    return SPACE_PUNCT.sub("", t)


out = {"pages": {}, "counts": collections.Counter(), "docs": {}}
for d in s["docs_with_text_diff"]:
    a = json.load(open(BASE / f"compare_runs/texts/{d['id']}__2.5.0__off.json", encoding="utf-8"))["odl"]
    b = json.load(open(BASE / f"compare_runs/texts/{d['id']}__2.5.9__off.json", encoding="utf-8"))["odl"]
    doc_cats = collections.Counter()
    for p in d["diff_pages"]:
        x, y = a.get(str(p), ""), b.get(str(p), "")
        cats = []
        y1 = html.unescape(y)
        if y1 != y:
            cats.append("html-escape(&lt; &gt; &amp;)")
        if x != y1:
            x2, y2 = norm_list(x), norm_list(y1)
            if (x2, y2) != (x, y1):
                cats.append("list-item leading */※ marker dropped")
            if x2 != y2:
                x3, y3 = norm_space(x2), norm_space(y2)
                if (x3, y3) != (x2, y2):
                    cats.append("space before , or ( dropped")
                if x3 != y3:
                    ops = [(t, x3[i1:i2], y3[j1:j2]) for t, i1, i2, j1, j2 in
                           difflib.SequenceMatcher(None, x3, y3, autojunk=False).get_opcodes() if t != "equal"]
                    cats.append("other: " + "; ".join(f"{t} {u!r}->{v!r}" for t, u, v in ops[:5]))
        key = " + ".join(cats)
        out["pages"][f"{d['id']} p{p}"] = key
        out["counts"][key if not key.startswith("other") and "other:" not in key else "includes other"] += 1
        doc_cats.update(cats)
    out["docs"][d["id"]] = dict(doc_cats)
out["counts"] = dict(out["counts"])
json.dump(out, open(BASE / "classify_diffs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out["counts"], ensure_ascii=False, indent=1))
for k, v in out["pages"].items():
    if "other" in v:
        print(k, v)
