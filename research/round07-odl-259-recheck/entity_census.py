"""entity_census.py — 비교 실행이 남긴 ODL 원본 markdown(compare_runs/odl_out)에서 HTML 엔티티를 버전별로 센다(1회성)."""
import json, re, sys
from collections import Counter
from pathlib import Path
ENTITY = re.compile(r"&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);")
root = Path(sys.argv[1])
by_ver, docs_with = {}, {}
for d in sorted(root.iterdir()):
    if not d.is_dir():
        continue
    doc, ver, mode = d.name.split("__")[:3]
    if mode != "off":
        continue
    c = Counter()
    for md in d.rglob("*.md"):
        c.update(ENTITY.findall(md.read_text(encoding="utf-8", errors="replace")))
    by_ver.setdefault(ver, Counter()).update(c)
    for e in c:
        docs_with.setdefault(ver, Counter())[e] += 1
out = {v: {"entities": dict(by_ver[v].most_common()), "docs_with_entity": dict(docs_with.get(v, Counter()).most_common()),
           "docs": len({p.name.split('__')[0] for p in root.iterdir() if p.is_dir() and f'__{v}__off' in p.name})} for v in sorted(by_ver)}
print(json.dumps(out, ensure_ascii=False, indent=1))
