"""추천 이유 프롬프트 — '책·도서' 단정을 '자료'로 바꾸기 전·후를 같은 입력으로 견준다 (1회성, 2026-10-23).

운영 API 로 자료 정보(GET /api/books/{id})와 검색이 고른 대목(POST /api/books/search, 화면과 같은 인자)을 받아
services/search/pipeline.stream_book_reason 과 같은 모양으로 입력을 만들고, 바꾸기 전(recommendation_before.yaml +
'[도서 요약]' 라벨)과 후(저장소 recommendation.yaml + '[자료 요약]' 라벨)를 운영 LLM(18080, 지금 Gemma 4)에 직접 보낸다.
출력에서 자료를 책·소설·작품·논문 등으로 부른 횟수를 센다.

    python compare_reason.py           # out.json (운영 LLM 을 부른다)
    python compare_reason.py --tally   # out.json 을 다시 세어 평균을 찍는다
"""
import json
import re
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))
sys.stdout.reconfigure(encoding="utf-8")
from services.prompts import _load_template  # noqa: E402

API = "https://skovix.landsoft.co.kr"
LLM = "http://192.168.12.57:18080/v1/chat/completions"
H = {"x-session-id": "00000000-0000-4000-8000-00000000d1a9"}
SAMPLES = [   # (질의, 자료 id, 종류)
    ("조선시대 고전소설을 연구한 자료 찾아줘", "CNTS-00052063539", "학위논문"),
    ("구운몽 줄거리가 궁금해", "CNTS-00052063078", "학위논문"),
    ("국가 재정 운용 계획은 어떻게 세워지나요?", "CNTS-00049655312", "정부 보고서"),
    ("구운몽", "WS_014", "고전소설"),
    ("김소월 시", "WS_002", "시집"),
    ("소녀의 성장 이야기", "LIT-GUTENBERG-514", "영어 소설"),
]
# '책'은 '정책'·'대책' 안의 글자를 세지 않는다
TERMS = {"책(이 자료를 책으로)": r"(?<![정대방])책(?:은|을|이|에서|의)?(?=[\s.,]|$)|이 책", "도서": r"도서(?!관)", "소설": r"소설",
         "작품": r"작품", "논문": r"논문", "이 자료": r"이 자료"}
VARIANTS = {
    "before": (HERE / "recommendation_before.yaml", "[도서 요약]", "[도서 줄거리]", "이 도서의", "도서 내용"),
    "after": (HERE.parents[1] / "app/domains/nl_library/prompts/recommendation.yaml", "[자료 요약]", "[자료 줄거리]", "이 자료의", "자료 내용"),
}


def count(text: str) -> dict:
    return {name: len(re.findall(rx, text)) for name, rx in TERMS.items()}


def tally() -> None:
    """out.json 을 다시 세어 자료 종류·방식별 평균을 찍는다(LLM 을 다시 부르지 않는다)."""
    out = json.loads((HERE / "out.json").read_text(encoding="utf-8"))
    rows = {}
    for o in out:
        o["counts"] = count(o["text"])
        r = rows.setdefault((o["kind"], o["variant"]), {k: 0 for k in TERMS} | {"n": 0, "형식": 0})
        r["n"] += 1
        r["형식"] += o["effect_marker"]
        for k, v in o["counts"].items():
            r[k] += v
    (HERE / "out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for (kind, variant), r in rows.items():
        n = r.pop("n")
        print(f"{kind:8} {variant:6} " + " · ".join(f"{k} {v / n:.1f}" for k, v in r.items()))


def inputs(query: str, book_id: str) -> dict:
    b = httpx.get(f"{API}/api/books/{book_id}", timeout=30).json()
    res = httpx.post(f"{API}/api/books/search", headers=H, timeout=120, json={
        "query": query, "mode": "book", "top_k": 10, "use_rewrite": True, "use_rerank": True}).json()
    hit = next((x for x in res["books"] if x["book_id"] == book_id), None)
    chunks = [c["text"] for c in (hit or {}).get("chunks", [])[:3]]
    meta = [f"제목: {b['title']}"]
    for label, key in (("저자/기관", "personal_author"), ("발행년도", "pub_date"), ("출판사", "publisher"),
                       ("KDC 분류", "kdc"), ("주제", "subject"), ("키워드", "keyword")):
        if b.get(key):
            meta.append(f"{label}: {b[key]}")
    return {"book": b, "meta": "\n".join(meta), "chunks": chunks, "rewritten": res.get("rewritten_query") or query,
            "found": hit is not None}


def render(variant: str, query: str, inp: dict):
    path, lab_sum, lab_plot, kw_this, kw_content = VARIANTS[variant]
    b = inp["book"]
    parts = []
    if b.get("summary"):
        parts.append(f"{lab_sum}\n{b['summary']}")
    if b.get("plot"):
        parts.append(f"{lab_plot}\n{b['plot']}")
    if inp["chunks"]:
        parts.append("[검색 매칭 구절]\n" + "\n\n".join(f"[관련 구절 {i + 1}]\n{t}" for i, t in enumerate(inp["chunks"])))
    has_kw = bool(b.get("keyword") or b.get("subject"))
    kw_instruction = "" if has_kw else (
        f"반드시 답변 첫 줄에 다음 형식으로 {kw_this} 핵심 테마 키워드 5개를 출력하세요.\n"
        f"키워드는 아래 독서 의도와 {kw_content}을 연결하는 개념으로 선택하세요:\n"
        "#KW: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5\n두 번째 줄부터 추천 이유 본문을 작성하세요.\n\n")
    return _load_template(str(path), "recommendation").render(
        kw_instruction=kw_instruction, intent=inp["rewritten"], query=query, book_meta=inp["meta"],
        context_text="\n\n".join(parts))


def main() -> None:
    out = []
    for query, book_id, kind in SAMPLES:
        inp = inputs(query, book_id)
        for variant in VARIANTS:
            for r in range(3):
                system, user, params = render(variant, query, inp)
                d = httpx.post(LLM, timeout=120, json={"model": "gemma-3-12b", "messages": [
                    {"role": "system", "content": system}, {"role": "user", "content": user}], **params}).json()
                text = d["choices"][0]["message"]["content"] or ""
                counts = count(text)
                out.append({"book_id": book_id, "kind": kind, "variant": variant, "run": r, "text": text,
                            "counts": counts, "effect_marker": "###EFFECT###" in text, "found": inp["found"]})
                print(book_id, kind, variant, r, {k: v for k, v in counts.items() if v}, "형식" if "###EFFECT###" in text else "형식X")
    (HERE / "out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    tally() if "--tally" in sys.argv else main()
