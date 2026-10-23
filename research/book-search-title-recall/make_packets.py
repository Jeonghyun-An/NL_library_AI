"""판정 묶음 — 판정 질의마다 방식 CUR·A·AH0 의 상위 10권을 합쳐 섞고, 도서 정보(운영 GET /api/books/{id})를 붙인다 (1회성).

판정자는 어느 방식에서 나온 책인지 모른다(라벨 B1… 은 질의마다 섞는다). 열쇠는 judge/key.json.

    python make_packets.py   # judge/q<번호>.json, judge/key.json
"""
import concurrent.futures as cf
import hashlib
import json
import random
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://skovix.landsoft.co.kr"
TOP = 10
VARIANTS = ("CUR", "A", "AH0")   # 판정 묶음을 만든 방식 — AH(지금 구현)는 tally 가 판정 범위 안에서 센다


def info(book_id: str) -> dict:
    r = httpx.get(f"{BASE}/api/books/{book_id}", timeout=30)
    if r.status_code != 200:
        return {"title": None}
    d = r.json()
    cut = lambda s, n: (s or "")[:n]  # noqa: E731
    return {"title": d.get("title"), "title_remainder": d.get("title_remainder"), "author": d.get("personal_author"),
            "doc_type": d.get("doc_type"), "year": d.get("pub_date"), "publisher": d.get("publisher"),
            "subject": d.get("subject"), "keyword": d.get("keyword"), "themes": d.get("themes"),
            "summary": cut(d.get("summary"), 500), "introduction": cut(d.get("introduction"), 300),
            "abstract": cut(d.get("abstract"), 300)}


def main() -> None:
    sim = [s for s in json.loads((HERE / "sim.json").read_text(encoding="utf-8")) if s["kind"] == "judged"]
    pools = []
    for s in sim:
        ids = []
        for v in VARIANTS:
            ids += [b["book_id"] for b in s["variants"][v][:TOP] if b["book_id"] not in ids]
        pools.append(ids)
    all_ids = sorted({i for p in pools for i in p})
    with cf.ThreadPoolExecutor(6) as ex:
        infos = dict(zip(all_ids, ex.map(info, all_ids)))
    out = HERE / "judge"
    out.mkdir(exist_ok=True)
    key = {}
    for n, (s, ids) in enumerate(zip(sim, pools)):
        rng = random.Random(int(hashlib.sha256(s["query"].encode()).hexdigest(), 16))
        order = ids[:]
        rng.shuffle(order)
        labels = {bid: f"B{i + 1}" for i, bid in enumerate(order)}
        key[f"q{n:02d}"] = {"query": s["query"], "labels": labels,
                            "ranks": {v: [labels[b["book_id"]] for b in s["variants"][v][:TOP]] for v in VARIANTS}}
        (out / f"q{n:02d}.json").write_text(json.dumps({
            "query": s["query"],
            "books": [{"label": labels[bid], **infos[bid]} for bid in order]}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(sim), "질의,", sum(len(p) for p in pools), "도서 칸,", len(all_ids), "권")


if __name__ == "__main__":
    main()
