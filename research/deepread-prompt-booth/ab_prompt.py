"""딥리드 답변 규칙 A/B — 옛 규칙(origin/dev) 대 새 규칙(이 브랜치)을 같은 문맥으로 운영 gemma 에 물어 견준다 (1회성, 2026-10-26).

부스 점검에서 나온 세 증상: ① 브로셔 질문 '이 연구논문에서 주장하고자 하는 바는?'에 "[참고 내용]만으로는 파악하기 어렵습니다"
로 얼버무림 ② 소나기 '마지막 부분은 어떻게 마무리되나요?'에 "자료에 포함되어 있지 않습니다"로 단정 ③ 답 글에 '[쪽 정보 없음]'·
'[표 4-2, 쪽 정보 없음]'. 새 규칙은 요약으로 답하기를 허락하고 안쪽 이름을 쓰지 않게 한다. 운영 Milvus 는 이 PC 에서 닿지 않아
문맥은 이렇게 만든다(ab_cases.json 에 그대로 남긴다):
- 회귀(R*): 운영 딥리드를 지금 규칙으로 한 번 불러 받은 출처 대목(sources — 답이 인용한 대목, 쪽 머리 그대로)으로.
- 증상(S*): 운영에서 본 실패를 흉내 — 결말·결론이 없는 앞쪽 대목 + 쪽 없는 서지·초록 청크(메타)·표 설명 청크.
시스템 프롬프트는 서비스와 같은 방식(jinja 렌더, 서지·요약·테마는 운영 /api/books/{id})이고 user 는 '[참고 내용]\\n…\\n\\n[질문]\\n…'.

    python ab_prompt.py            # 문맥 모으기(운영 딥리드 회귀 질문 수만큼) → 두 규칙 × 2회 → ab_results.json
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import fitz
import httpx
import yaml
from jinja2 import Template

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
API = "https://skovix.landsoft.co.kr/api"
LLM = "http://192.168.12.57:18080/v1/chat/completions"
MODEL = "gemma-3-12b"
H = {"x-session-id": "00000000-0000-4000-8000-0000000b0078"}
RUNS = 2
INTERNAL = re.compile(r"\[(참고 내용|자료 요약|논문 요약|핵심 주제|쪽 정보 없음)|쪽 정보 없음")
HEDGE = re.compile(r"다루지 않|포함되어 있지 않|명시되어 있지 않|파악하기 어렵|확인하지 못했|확인할 수 없")
CITE = re.compile(r"p\.\s*\d+")


def prompts() -> dict:
    out = {}
    for name in ("book_chat.yaml", "book_chat.paper.yaml"):
        rel = f"app/domains/nl_library/prompts/{name}"
        old = subprocess.run(["git", "show", f"origin/dev:{rel}"], cwd=REPO, capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
        new = (REPO / rel).read_text(encoding="utf-8")
        out[name] = {"old": yaml.safe_load(old)["system"], "new": yaml.safe_load(new)["system"]}
    return out


def book(cid: str) -> dict:
    return httpx.get(f"{API}/books/{cid}", timeout=30).json()


def live_sources(cid: str, q: str) -> list[dict]:
    raw = httpx.post(f"{API}/books/chat/{cid}", headers={**H, "Accept": "text/event-stream"},
                     json={"message": q, "history": []}, timeout=240).text
    ev = [json.loads(line[5:]) for line in raw.splitlines() if line.startswith("data:") and line[5:].strip().startswith("{")]
    return next((e["sources"] for e in ev if "sources" in e), [])


def label(ps: int, pe: int) -> str:
    """book_chat._context_label 과 같은 꼴 — 저장값(0부터) +1, 0 이면 쪽 정보 없음."""
    if ps <= 0:
        return "[쪽 정보 없음]"
    s, e = ps + 1, max(pe + 1, ps + 1)
    return f"[p.{s}–{e}]" if e > s else f"[p.{s}]"


def pdf_pages(cid: str, pages: list[int], width: int = 900) -> list[tuple[str, str]]:
    """PDF 쪽 글(1부터)을 대목처럼 잘라 [p.N] 머리를 단다."""
    d = fitz.open(stream=httpx.get(f"{API}/books/{cid}/pdf", timeout=120, follow_redirects=True).content, filetype="pdf")
    out = []
    for p in pages:
        t = re.sub(r"\s+", " ", d[p - 1].get_text())
        for i in range(0, len(t), width):
            out.append((f"[p.{p}]", t[i:i + width]))
    return out


def meta_chunk(b: dict) -> tuple[str, str]:
    parts = [f"제목: {b.get('title')}", f"저자: {b.get('personal_author')}" if b.get("personal_author") else None,
             f"발행년도: {b.get('pub_date')}" if b.get("pub_date") else None,
             f"초록: {b.get('abstract')}" if b.get("abstract") else None]
    return "[쪽 정보 없음]", " | ".join(p for p in parts if p)


CASES = [
    # 증상
    {"id": "S1", "cid": "KCI_FI000862072", "q": "이 연구논문에서 주장하고자 하는 바는 무엇인가요?", "kind": "symptom",
     "ctx": "pdf", "pages": [4, 5], "extra": "table"},
    {"id": "S2", "cid": "PSN-SONAGI", "q": "마지막 부분은 어떻게 마무리되나요?", "kind": "symptom", "ctx": "pdf", "pages": [2, 3]},
    {"id": "S3", "cid": "PSN-SONAGI", "q": "소녀는 죽기 전에 무슨 말을 남겼나요?", "kind": "symptom", "ctx": "pdf", "pages": [3, 4],
     "extra": "meta"},
    {"id": "S4", "cid": "PSN-SONAGI", "q": "이 자료가 말하고자 하는 바는 무엇인가요?", "kind": "symptom", "ctx": "pdf", "pages": [3, 4]},
    # 회귀 — 부스 시연 질문, 운영이 지금 잘 답하는 것
    {"id": "R1", "cid": "PSN-SONAGI", "q": "소녀가 소년에게 조약돌을 던지며 한 말은 무엇인가요?", "kind": "regress", "ctx": "live"},
    {"id": "R2", "cid": "PSN-BULFINCH", "q": "판도라의 상자에서 마지막에 남은 것은 무엇인가요?", "kind": "regress", "ctx": "live"},
    {"id": "R3", "cid": "PSN-DOG-FLANDERS", "q": "넬로가 그림 대회에 낸 그림은 무엇인가요?", "kind": "regress", "ctx": "live"},
    {"id": "R4", "cid": "KCI_FI002782062", "q": "어떤 사람에게서 받은 지지가 가장 효과적이었나요?", "kind": "regress", "ctx": "live"},
    {"id": "R5", "cid": "KCI_FI002161665", "q": "1차, 2차, 3차 예방 프로그램 중 어느 쪽 효과가 가장 컸나요?", "kind": "regress", "ctx": "live"},
    {"id": "R6", "cid": "KCI_FI000862072", "q": "이 논문의 핵심 주장은 무엇인가요?", "kind": "regress", "ctx": "live"},
]


def build_context(c: dict, b: dict) -> list[tuple[str, str]]:
    if c["ctx"] == "live":
        return [(label(s["page_start"], s["page_end"]), s["text"]) for s in live_sources(c["cid"], c["q"])]
    blocks = pdf_pages(c["cid"], c["pages"])[:5]
    if c.get("extra") == "meta":
        blocks.insert(0, meta_chunk(b))
    if c.get("extra") == "table":
        blocks.append(("[쪽 정보 없음]", "[표 4-2] 선행변수 요인분석 결과 — 광고 및 홍보 85.181%, 구전효과 70.610%, 헌신정도 89.093%, "
                                         "투자의지 82.035%. 요인들의 설명력은 모두 70% 이상으로 양호하다. SPSS WIN 7.5 로 요인분석을 했다."))
    return blocks


def ask(system: str, ctx: list[tuple[str, str]], q: str) -> str:
    user = "[참고 내용]\n" + "\n\n".join(f"{h}\n{t}" for h, t in ctx) + f"\n\n[질문]\n{q}" if ctx else q
    r = httpx.post(LLM, json={"model": MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                              "max_tokens": 1500, "temperature": 0.3}, timeout=180)
    return r.json()["choices"][0]["message"]["content"]


def main() -> None:
    ps = prompts()
    cases, results = [], []
    for c in CASES:
        b = book(c["cid"])
        ctx = build_context(c, b)
        name = "book_chat.paper.yaml" if b.get("doc_type") == "paper" else "book_chat.yaml"
        author = b.get("personal_author") or b.get("corporate_author") or "저자 미상"
        vars_ = {"title": b.get("title") or c["cid"], "author": author,
                 "pub_date": f", {b['pub_date']}" if b.get("pub_date") else "",
                 "summary": b.get("summary") or "요약 정보 없음", "themes": b.get("themes") or "테마 정보 없음"}
        cases.append({**c, "prompt": name, "context": ctx})
        for arm in ("old", "new"):
            # 새 쪽은 요약이 비면 초록을 싣는다(book_chat.stream_book_chat — 같은 브랜치의 코드 변경)
            summary = b.get("summary") or (b.get("abstract") if arm == "new" else None) or "요약 정보 없음"
            system = Template(ps[name][arm]).render(**{**vars_, "summary": summary})
            for run in range(RUNS):
                a = ask(system, ctx, c["q"])
                res = {"id": c["id"], "kind": c["kind"], "arm": arm, "run": run, "answer": a,
                       "internal": INTERNAL.findall(a), "hedge": bool(HEDGE.search(a)), "cites": CITE.findall(a)}
                results.append(res)
                print(f"{c['id']} {arm} r{run} 안쪽이름={len(res['internal'])} 얼버무림={res['hedge']} 쪽={res['cites'][:4]} | "
                      f"{a[:110].replace(chr(10), ' ')}", flush=True)
    (HERE / "ab_cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "ab_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for kind in ("symptom", "regress"):
        for arm in ("old", "new"):
            rs = [r for r in results if r["kind"] == kind and r["arm"] == arm]
            print(f"[{kind} {arm}] {len(rs)}답 · 안쪽 이름 {sum(bool(r['internal']) for r in rs)} · 얼버무림/없다 "
                  f"{sum(r['hedge'] for r in rs)} · 쪽 인용 있음 {sum(bool(r['cites']) for r in rs)}")


if __name__ == "__main__":
    main()
