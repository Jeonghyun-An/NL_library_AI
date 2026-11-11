"""참고문헌 꼬리 걷기(services/ingestion/reference_tail.clean_references) — 표본 모으기와 재기 (1회성, 2026-10-26).

    python measure.py collect   # 운영 논문 검색 25질의 × 상위 20편의 book_info.references → sample.json (읽기만)
    python measure.py           # sample.json 에 지금 규칙을 돌려 바뀐 편·버린 항목·빈 목록·남은 꼬리 흔적을 센다 → changed_rows.json

changed_rows.json(바뀐 논문의 before/after)은 표본 검토(review_round*.json — 서브에이전트가 나눠 읽고 진짜 참고문헌을 잃은
경우를 찾음)의 입력이었다.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))
sys.stdout.reconfigure(encoding="utf-8")

QUERIES = ["노인 우울", "학교폭력", "다문화 아동 언어", "독서 프로그램", "공공도서관 만족도", "청소년 스마트폰", "간호사 소진",
           "초등 수학 교육", "기업 회계 감사", "지역 축제 관광", "부동산 가격", "한국어 교육 외국인", "미술 치료", "사회복지 정책",
           "환경 교육", "디지털 리터러시", "대학생 진로", "노동 시장 청년", "의료 서비스 질", "문학 교육 시", "스포츠 심리",
           "유아 놀이", "법 해석 판례", "행정 혁신", "중국어 학습"]
TRACE = re.compile(r"(?<!Dissertation )(Abstract|ABSTRACT|국문\s*초록|논문\s*초록|(?i:key\s*words?)|주제어|키워드|접\s*수\s*일|"
                   r"게재\s*확정|투\s*고\s*일|심\s*사\s*일|정회원|E-?mail|전자우편)")


def collect() -> None:
    import httpx
    api, h = "https://skovix.landsoft.co.kr/api", {"x-session-id": "00000000-0000-4000-8000-0000000b0079"}
    papers = {}
    for q in QUERIES:
        d = httpx.post(f"{api}/papers/search", headers=h, timeout=120,
                       json={"query": q, "mode": "book", "top_k": 20, "use_rewrite": False, "use_rerank": True}).json()
        for b in d.get("books", []):
            bi = b.get("book_info") or {}
            papers[b["book_id"]] = {"title": bi.get("title"), "refs": bi.get("references") or []}
    (HERE / "sample.json").write_text(json.dumps(papers, ensure_ascii=False), encoding="utf-8")
    print(f"{len(papers)}편")


def measure() -> None:
    from services.ingestion.reference_tail import clean_references
    papers = json.loads((HERE / "sample.json").read_text(encoding="utf-8"))
    rows = []
    for k, v in papers.items():
        if not v["refs"]:
            continue
        before = [html.unescape(x).strip() for x in v["refs"] if (x or "").strip()]
        after = clean_references(v["refs"])
        if after != before:
            rows.append({"id": k, "title": v["title"], "before": before, "after": after})
    with_refs = sum(1 for v in papers.values() if v["refs"])
    trace_before = sum(1 for v in papers.values() if v["refs"] and TRACE.search(" ".join(v["refs"][-3:])))
    trace_after = sum(1 for v in papers.values() if v["refs"] and TRACE.search(" ".join(clean_references(v["refs"])[-3:])))
    print(f"표본 {len(papers)}편 · 참고문헌 있는 {with_refs}편 · 바뀐 {len(rows)}편({len(rows) * 100 / with_refs:.1f}%) · "
          f"버린 항목 {sum(len(r['before']) - len(r['after']) for r in rows)} · 빈 목록 {sum(1 for r in rows if not r['after'])}")
    print(f"끝 3항목에 꼬리 흔적: 정리 전 {trace_before}편 → 정리 뒤 {trace_after}편")
    (HERE / "changed_rows.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    collect() if sys.argv[1:] == ["collect"] else measure()
