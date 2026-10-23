"""소장자료 검색이 도서를 못 채우는 원인 가르기 — 운영 API 를 재작성 끔으로 부른다 (1회성, 2026-10-23).

질의는 research/book-search-title-recall(fix/book-search-title-recall 브랜치)의 queries.json 을 그대로 쓰고, 날짜 필터
오작동을 보려는 질의(probe)를 더한다. 화면과 같은 인자(mode book · top_k 10 · rerank 켬, 재작성만 끔)로
POST /api/books/search 를 부르고, 응답에서 원인을 가를 숫자만 남긴다. 같은 날짜 필터를 쓰는 논문 검색
(POST /api/papers/search — 재작성은 늘 끔)도 몇 질의 부른다(kind paper).

- fallback: 응답이 전부 논문 — 도서 필터 검색이 0권이라 라우트가 doc_scope 없이 다시 찾은 것(api/book.py)
- chunks: 응답 청크 수. 도서 모드는 하이브리드 검색 청크 300개(top_k 10 × 3 × 10)를 책으로 묶고, 30권을 넘으면 30권에서
  자른다. 30권이 안 되는데 청크+메타 청크가 300 에 못 미치면 Milvus 필터 검색이 limit 를 못 채운 것이다.
- RRF 순위: 청크 점수는 Σ 1/(60+rank). 한 목록에만 든 청크는 1/점수−60 이 정수(그 목록의 순위)다. 같은 순위가 두 번 나오면
  dense·sparse 두 목록 모두 그 순위까지 결과가 있었다 — max_twice_rank 는 짧은 쪽 목록 길이의 하한이다.

    python measure.py          # raw/<번호>.json — 있으면 건너뛴다
    python measure.py --tally  # 표
"""
import collections
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://skovix.landsoft.co.kr"
SESSION = {"x-session-id": "00000000-0000-4000-8000-00000000f1a1"}
WINDOW = 300   # top_k 10 × BOOK_MODE_FETCH_MULTIPLIER 3 × HYBRID_SEARCH_CHUNK_LIMIT_MULT 10

# 날짜 필터(LLM)가 제목·주제의 낱말을 발행 연도·정렬 조건으로 읽는지 보는 질의 — 목표 도서 없음
PROBES = [
    "올리버", "트위스트", "올빼미", "올림픽", "올해의 소설",
    "1930년대 소설", "1930년대 세태소설 연구", "1920년대 신소설", "82년생 김지영", "1984",
    "최신 소설", "초기 근대소설", "처음 나온 한글 소설",
    "李光洙小說의 批評的 硏究",   # '1984' 가 찾은 1984년 학위논문의 제목 — 그 논문 청크가 몇 개 잡히나
]
# 논문 검색 — 위와 같은 날짜 필터 오작동이 있는지, 시연 질의는 괜찮은지
PAPER_PROBES = [
    "올리버 트위스트", "Oliver Twist", "올바른 양육 태도", "청소년의 올바른 인터넷 사용", "올레길 관광",
    "노인 사회적 지지와 우울", "노인의 사회적 지지가 우울에 미치는 영향", "2020년 이후 노인 우울 연구",
    "최근 3년 노인 우울", "작년 노인 우울 논문",
]


def queries() -> list[dict]:
    q = json.loads((HERE / "queries.json").read_text(encoding="utf-8"))
    out = []
    for kind in ("title_kr", "title_en_kr", "title_en", "title_in_question"):
        out += [{"kind": kind, "query": t, "targets": [i]} for t, i in q[kind]]
    out += [{"kind": "author", "query": t, "targets": ids} for t, ids in q["author"]]
    out += [{"kind": "probe", "query": t, "targets": []} for t in PROBES]
    out += [{"kind": "paper", "query": t, "targets": []} for t in PAPER_PROBES]
    return out


def call(query: str, endpoint: str = "books") -> dict:
    t0 = time.time()
    r = httpx.post(f"{BASE}/api/{endpoint}/search", headers=SESSION, timeout=180, json={
        "query": query, "mode": "book", "top_k": 10, "use_rewrite": False, "use_rerank": True})
    r.raise_for_status()
    d = r.json()
    books = []
    for b in d.get("books", []):
        info = b.get("book_info") or {}
        books.append({"book_id": b["book_id"], "doc_type": info.get("doc_type"), "pub_date": info.get("pub_date"),
                      "title": info.get("title"), "best": b.get("best_score"),
                      "rrf": [round(c["score"], 7) for c in b.get("chunks", [])]})
    return {"elapsed_ms": d.get("elapsed_ms"), "wall_s": round(time.time() - t0, 2), "books": books}


def is_paper(b: dict) -> bool:
    return b["book_id"].startswith("KCI_FI") or b.get("doc_type") == "paper"


def analyze(item: dict) -> dict:
    books = item["res"]["books"]
    rrf = [s for b in books for s in b["rrf"]]
    ranks = [1 / s - 60 for s in rrf if s > 0]
    single = collections.Counter(round(x) for x in ranks if abs(x - round(x)) < 1e-3)
    twice = [r for r, n in single.items() if n >= 2]
    ids = [b["book_id"] for b in books]
    hit = [ids.index(t) + 1 for t in item["targets"] if t in ids]
    return {
        "fallback": bool(books) and all(is_paper(b) for b in books),
        "n_books": len(books),
        "chunks": len(rrf),
        # 메타 청크(chunk_idx -1)는 응답에서 빠진다 — 책마다 하나까지라 창이 찼는지는 청크+책 수로 본다
        "window_full": len(books) >= 30 or len(rrf) + len(books) >= WINDOW,
        "max_single_rank": max(single) if single else None,
        "max_twice_rank": max(twice) if twice else None,
        "target_rank": min(hit) if hit else None,
        "years": sorted({(b.get("pub_date") or "")[:4] for b in books}),
        "top_chunks_share": max((len(b["rrf"]) for b in books), default=0) / max(1, len(rrf)),
    }


def one(i: int, item: dict) -> str:
    path = HERE / "raw" / f"{i:03d}.json"
    if path.exists():
        return f"skip {i}"
    res = call(item["query"], "papers" if item["kind"] == "paper" else "books")
    path.write_text(json.dumps({**item, "res": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    a = analyze({**item, "res": res})
    return f"done {i} {item['query']} books={a['n_books']} chunks={a['chunks']} fallback={a['fallback']}"


def tally() -> None:
    rows = []
    for p in sorted((HERE / "raw").glob("*.json")):
        item = json.loads(p.read_text(encoding="utf-8"))
        rows.append({**item, **analyze(item)})
    (HERE / "tally.json").write_text(json.dumps([{k: v for k, v in r.items() if k != "res"} for r in rows],
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    titled = [r for r in rows if r["kind"] not in ("probe", "paper")]
    print(f"제목·저자 질의 {len(titled)}개 (재작성 끔, top_k 10)")
    print(f"  응답 도서 10권 미만: {sum(r['n_books'] < 10 for r in titled)}")
    print(f"  전부 논문(도서 0건 → doc_scope 없이 재시도): {sum(r['fallback'] for r in titled)}")
    short = [r for r in titled if not r["window_full"] and not r["fallback"]]
    print(f"  후보 창(300청크) 못 채움 = 필터 검색이 limit 미달: {len(short)}")
    sat = [r for r in titled if r["window_full"] and r["n_books"] < 10 and not r["fallback"]]
    print(f"  창은 찼는데 10권 미만(긴 책 몇 권이 창을 차지): {len(sat)}")
    for r in sat:
        print(f"     {r['query']}: {r['n_books']}권, 1위 책이 청크 {r['top_chunks_share']:.0%}, 목표 {r['target_rank']}위")
    print(f"  max_twice_rank 최솟값(창 안에서 두 목록이 다 찬 순위): {min((r['max_twice_rank'] or 0) for r in titled if not r['fallback'])}")
    for kind in ("title_kr", "title_en_kr", "title_en", "title_in_question", "author"):
        rs = [r for r in titled if r["kind"] == kind]
        top1 = sum(r["target_rank"] == 1 for r in rs)
        top10 = sum((r["target_rank"] or 99) <= 10 for r in rs)
        print(f"  {kind}: 목표 1위 {top1}/{len(rs)}, 10위 안 {top10}/{len(rs)}")
    for r in rows:
        if r["kind"] != "paper" and (r["fallback"] or r["kind"] == "probe" or not r["window_full"]):
            top = r["res"]["books"][0] if r["res"]["books"] else {}
            print(f"   [{r['kind']}] {r['query']}: 책 {r['n_books']} 청크 {r['chunks']} 폴백 {r['fallback']} "
                  f"창 {'참' if r['window_full'] else '안 참'} 연도 {r['years'][:6]} 목표 {r['target_rank']} "
                  f"1위 {top.get('book_id')}({top.get('pub_date')}) 청크 {len(top.get('rrf', []))}")
    print("논문 검색 (POST /api/papers/search) — 결과 30편의 발행 연도")
    for r in rows:
        if r["kind"] == "paper":
            years = collections.Counter((b.get("pub_date") or "")[:4] for b in r["res"]["books"])
            print(f"   {r['query']}: {r['n_books']}편, 연도 {len(years)}가지 {min(years, default='')}~{max(years, default='')}")


def main() -> None:
    if "--tally" in sys.argv:
        tally()
        return
    (HERE / "raw").mkdir(exist_ok=True)
    items = queries()
    with cf.ThreadPoolExecutor(3) as ex:   # 운영 검색과 같은 서버라 동시 3 으로
        for msg in ex.map(lambda a: one(*a), enumerate(items)):
            print(msg)


if __name__ == "__main__":
    main()
