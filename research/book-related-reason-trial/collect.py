# 도서 관련 자료 비교 사유 시험 — 수집 단계(읽기 호출만).
# 화면과 같은 방식: 메인 자료 검색 = POST /api/books/search {mode:book, top_k:10, use_rewrite:true, use_rerank:true}
#                    1위 = 응답 순서의 첫 book_id (pickTopBook), 추천 패널은 best_score >= 0.4 (isRecommendable)
#                    도서 상세 관련 자료 = POST /api/books/search {query: 상세 title, top_k:6, use_rewrite:false, use_rerank:true}
#                                         → 자기 자신 제외 → 앞 4권
# 본문 후보는 app/api/paper.py _get_abstract 와 같은 순서(abstract or summary or introduction or "")
import json
import re
import sys
import time
from pathlib import Path

import requests

BASE = "http://192.168.12.57:92/api"
OUT = Path(__file__).resolve().parent / "collected.json"
HEADERS = {"Content-Type": "application/json", "x-session-id": "trial-book-related-20261013"}
QUERIES = [
    "조선시대 고전소설을 연구한 자료 찾아줘",
    "국가 재정 운용 계획에 관한 자료 찾아줘",
    "한국 현대시를 연구한 자료 찾아줘",
]
PAUSE_SEARCH = 4.0
PAUSE_GET = 1.0

# app/services/search/paper_summary.py 와 같은 전처리
_SUMMARY_PREFIX_RE = re.compile(r"^##\s*SUMMARY:\s*", re.IGNORECASE)
_CHUNK_META_RE = re.compile(
    r"^(초록|abstract|summary|요약|introduction|서론)\s*[\n\r]+\s*\*{0,2}SUMMARY:\s*",
    re.IGNORECASE,
)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def _clean_excerpt(text: str) -> str:
    if not text:
        return text
    text = _CHUNK_META_RE.sub("", text.strip())
    text = _SUMMARY_PREFIX_RE.sub("", text.strip())
    return text.strip()


def server_excerpt(book: dict) -> tuple[str, str]:
    """서버가 비교 사유 프롬프트에 넣을 '초록' 줄과 고른 필드 이름."""
    for field in ("abstract", "summary", "introduction"):
        v = book.get(field)
        if v:  # 파이썬 `or` 와 같이 빈 문자열만 건너뛴다
            return field, _truncate(_clean_excerpt(v), 400)
    return "none", "초록 없음"


def search(query: str, top_k: int, use_rewrite: bool) -> dict:
    body = {"query": query, "mode": "book", "top_k": top_k, "use_rewrite": use_rewrite, "use_rerank": True}
    t0 = time.time()
    r = requests.post(f"{BASE}/books/search", headers=HEADERS, json=body, timeout=180)
    r.raise_for_status()
    data = r.json()
    data["_elapsed_s"] = round(time.time() - t0, 2)
    data["_request"] = body
    return data


def get_book(cnts_id: str) -> dict:
    r = requests.get(f"{BASE}/books/{cnts_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def field_info(v) -> dict:
    s = v or ""
    return {"len": len(s), "len_stripped": len(s.strip()), "head400": s[:400]}


def describe(book: dict) -> dict:
    picked, excerpt = server_excerpt(book)
    card_desc = book.get("summary") or book.get("introduction") or ""
    return {
        "cnts_id": book.get("cnts_id"),
        "title": book.get("title"),
        "title_remainder": book.get("title_remainder"),
        "personal_author": book.get("personal_author"),
        "corporate_author": book.get("corporate_author"),
        "publisher": book.get("publisher"),
        "pub_date": book.get("pub_date"),
        "doc_type": book.get("doc_type"),
        "material_type": book.get("material_type"),
        "genre": book.get("genre"),
        "source_format": book.get("source_format"),
        "kdc": book.get("kdc"),
        "subject": book.get("subject"),
        "keyword": book.get("keyword"),
        "themes": book.get("themes"),
        "extracted_keywords": book.get("extracted_keywords"),
        "is_embedded": book.get("is_embedded"),
        "body_fields": {
            "abstract": field_info(book.get("abstract")),
            "summary": field_info(book.get("summary")),
            "introduction": field_info(book.get("introduction")),
        },
        "plot_len": len(book.get("plot") or ""),
        "read_effect_len": len(book.get("read_effect") or ""),
        "server_pick_field": picked,
        "server_excerpt": excerpt,
        "body_all_empty": picked == "none",
        "card_ai_summary_len": len(card_desc),  # 관련 카드의 'AI 요약'(summary || introduction)
    }


def brief(b: dict, rank: int) -> dict:
    info = b.get("book_info") or {}
    return {
        "api_rank": rank,
        "book_id": b.get("book_id"),
        "title": info.get("title"),
        "best_score": b.get("best_score"),
        "title_score": b.get("title_score"),
        "content_score": b.get("content_score"),
    }


def main() -> None:
    result = {"collected_at": time.strftime("%Y-%m-%d %H:%M:%S"), "queries": []}
    for qi, q in enumerate(QUERIES):
        if qi:
            time.sleep(PAUSE_SEARCH)
        print(f"[search] {q}", flush=True)
        data = search(q, top_k=10, use_rewrite=True)
        books = data.get("books") or []
        top = next((b for b in books if isinstance(b.get("book_id"), str) and b["book_id"]), None)
        entry = {
            "query": q,
            "search_api": {
                "method": "POST",
                "url": f"{BASE}/books/search",
                "body": data["_request"],
                "note": "frontend/pages/index.vue handleSearch 와 같은 본문. 스트리밍 아님(JSON 한 번에)",
                "elapsed_s": data["_elapsed_s"],
                "rewritten_query": data.get("rewritten_query"),
                "result_count": len(books),
                "results": [brief(b, i + 1) for i, b in enumerate(books)],
            },
        }
        if not top:
            entry["top1"] = None
            entry["related"] = []
            result["queries"].append(entry)
            continue
        top_score = top.get("best_score")
        time.sleep(PAUSE_GET)
        top_detail = get_book(top["book_id"])
        entry["top1"] = {
            **describe(top_detail),
            "best_score": top_score,
            "recommendable": isinstance(top_score, (int, float)) and top_score >= 0.4,
        }
        print(f"  top1 {top['book_id']} {top_detail.get('title')} score={top_score}", flush=True)

        time.sleep(PAUSE_SEARCH)
        rel_query = top_detail.get("title") or ""
        rdata = search(rel_query, top_k=6, use_rewrite=False)
        rbooks = rdata.get("books") or []
        entry["related_api"] = {
            "method": "POST",
            "url": f"{BASE}/books/search",
            "body": rdata["_request"],
            "note": "frontend/pages/books/[cnts_id].vue fetchRelatedBooks — 상세 title 로 검색, 자기 자신 제외, 앞 4권",
            "elapsed_s": rdata["_elapsed_s"],
            "result_count": len(rbooks),
            "results": [brief(b, i + 1) for i, b in enumerate(rbooks)],
        }
        picked = [(i + 1, b) for i, b in enumerate(rbooks) if b.get("book_id") != top["book_id"]][:4]
        related = []
        for disp, (api_rank, b) in enumerate(picked, start=1):
            time.sleep(PAUSE_GET)
            d = get_book(b["book_id"])
            related.append({
                **describe(d),
                "related_api_rank": api_rank,
                "display_rank": disp,
                "best_score": b.get("best_score"),
            })
            print(f"  rel{disp} (api#{api_rank}) {b['book_id']} {d.get('title')}", flush=True)
        entry["related"] = related
        result["queries"].append(entry)

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
