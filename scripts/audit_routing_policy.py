"""audit_routing_lit.py — 정책·재정 자료(정부간행물·경제연구보고서) 200건에 대한 라우팅 규칙 감사.

학술논문 100건(2,024쪽)에서 얻은 재배정률 0.30%가 자료 유형에 따라 어떻게 달라지는지
확인하기 위해, 동일한 절차를 표가 많은 정책·재정 자료 200건에 적용한다. 판정 공식·정제 로직은
audit_routing_fix.py 와 완전히 동일하며, fitz 추출량은 별도 패스(scripts/fitz_lengths_policy.py)에서 수집해 병합한다.

문서 단위로 중간저장하므로 중단 후 다시 실행하면 남은 문서만 처리한다.

사용법:
    python scripts/audit_routing_policy.py
"""
import io
import json
import os
import re
import sys
import time

from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader

BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
SAMPLE = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/policy_sample200.txt"
OUT = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/audit_routing_policy200.json"

MIN_CHARS_PER_PAGE = 50
_STRUCT_CHARS = str.maketrans("", "", "|-: \t\n\r")
_IMG_ANY_PATTERN = re.compile(r'!\[[^\]]*\]\([^)]+\)')


def _clean_text(text: str) -> str:
    """extractor.py 와 동일한 정제 로직."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != '':
            lines.append('')
    text = '\n'.join(lines)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n-\s*\d+\s*-\s*\n', '\n', text)
    text = re.sub(r'\n\d+\s*/\s*\d+\s*\n', '\n', text)
    text = re.sub(r'\nPage\s+\d+\s*\n', '\n', text, flags=re.IGNORECASE)
    return text.strip()


def old_body_len(text: str) -> int:
    """개선 전: 그림 마커만 제거."""
    return len(text.replace("[그림]", "").strip())


def new_body_len(text: str) -> int:
    """개선 후: 표 구조 문자·공백까지 제거."""
    return len(text.replace("[그림]", "").translate(_STRUCT_CHARS))


def route(n: int) -> str:
    return "vlm" if n < MIN_CHARS_PER_PAGE else "stage1"


def audit(name: str) -> dict:
    path = BASE + name   # name 은 "CNTS-xxx/CNTS-xxx.pdf" 형태의 상대경로
    loader = OpenDataLoaderPDFLoader(
        file_path=path, format="markdown", image_output="embedded",
        image_format="jpeg", table_method="cluster", split_pages=True,
        keep_line_breaks=False,
    )
    docs = loader.load()

    pages, rerouted = [], 0
    for doc in docs:
        pg = doc.metadata.get("page")
        text = _clean_text(_IMG_ANY_PATTERN.sub('[그림]', doc.page_content))
        o, n = old_body_len(text), new_body_len(text)
        ro, rn = route(o), route(n)
        if ro != rn:
            rerouted += 1
        pages.append({"page": pg, "old_len": o, "new_len": n,
                      "old_route": ro, "new_route": rn, "rerouted": ro != rn})
    return {"file": name, "odl_pages": len(pages),
            "rerouted_pages": rerouted, "all_pages": pages}


def main():
    names = [l.strip() for l in io.open(SAMPLE, encoding="utf-8") if l.strip()]
    results = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    done = {r["file"] for r in results}

    for i, name in enumerate(names, 1):
        if name in done:
            print(f"[{i}/{len(names)}] skip {name}", file=sys.stderr)
            continue
        t0 = time.perf_counter()
        try:
            res = audit(name)
        except Exception as e:
            print(f"[{i}/{len(names)}] 실패 {name}: {e}", file=sys.stderr)
            results.append({"file": name, "error": str(e)})
        else:
            results.append(res)
            print(f"[{i}/{len(names)}] {name} {res['odl_pages']}쪽 "
                  f"재배정 {res['rerouted_pages']}쪽 ({time.perf_counter()-t0:.0f}s)",
                  file=sys.stderr)
        json.dump(results, io.open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    ok = [r for r in results if "all_pages" in r]
    tot = sum(r["odl_pages"] for r in ok)
    rer = sum(r["rerouted_pages"] for r in ok)
    print(f"\n완료: {len(ok)}건 {tot}쪽, 재배정 {rer}쪽 "
          f"({rer/tot*100:.2f}%)" if tot else "완료", file=sys.stderr)


if __name__ == "__main__":
    main()
