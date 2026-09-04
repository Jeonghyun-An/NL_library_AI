"""
audit_routing_fix.py — 라우팅 규칙(구 vs 신) 다문서 비교 감사

extractor.py의 실제 1티어 추출 파이프라인(OpenDataLoader 호출 + 이미지→[그림]
치환 + _clean_text, extractor.py:493-549)을 그대로 재현한 뒤, 그 정제된 텍스트에
_body_len 로직(신, extractor.py:56-64)과 그 직전 커밋 a905cb4의 로직(구)을 각각
적용해 페이지별 재라우팅 여부와 글자 수 차이를 집계한다.
VLM/DB/MinIO는 전혀 건드리지 않는다 (순수 로컬 계산).

사용법:
    python scripts/audit_routing_fix.py <pdf1> <pdf2> ...
"""
import json
import re
import sys
from pathlib import Path

from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader

MIN_CHARS_PER_PAGE = 50
_STRUCT_CHARS = str.maketrans("", "", "|-: \t\n\r")

# extractor.py:511-517 과 동일
_IMG_B64_PATTERN = re.compile(r'!\[([^\]]*)\]\(data:image/[^;]+;base64,([^)]+)\)')
_IMG_ANY_PATTERN = re.compile(r'!\[[^\]]*\]\([^)]+\)')


def _clean_text(text: str) -> str:
    """extractor.py:29-49 과 동일한 정제 로직."""
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
    """a905cb4 시점 로직: [그림] 마커만 제거하고 양끝 공백만 정리."""
    return len(text.replace("[그림]", "").strip())


def new_body_len(text: str) -> int:
    """현재(9b68651) 로직: 표 구조 문자·모든 공백까지 제거 후 계산."""
    return len(text.replace("[그림]", "").translate(_STRUCT_CHARS))


def route(body_len: int) -> str:
    return "vlm" if body_len < MIN_CHARS_PER_PAGE else "stage1"


def audit_pdf(pdf_path: str) -> dict:
    loader = OpenDataLoaderPDFLoader(
        file_path=pdf_path,
        format="markdown",         # extractor.py:496 과 동일
        image_output="embedded",   # extractor.py:497 과 동일
        image_format="jpeg",       # extractor.py:498 과 동일
        table_method="cluster",    # extractor.py:499 과 동일
        split_pages=True,          # extractor.py:500 과 동일
        keep_line_breaks=False,    # extractor.py:501 과 동일
    )
    documents = loader.load()

    pages = []
    for doc in documents:
        raw = doc.page_content
        # extractor.py:548-549 과 동일 — 이미지(base64/외부경로 모두)를 [그림]으로
        # 치환한 뒤 정제해야, 실제 라우팅 판단에 쓰이는 것과 같은 텍스트가 된다.
        # (raw 그대로 쓰면 base64 이미지 데이터 수십만 자가 그대로 "본문"으로 잡혀버림)
        stripped = _IMG_ANY_PATTERN.sub('[그림]', raw)
        text = _clean_text(stripped)
        old_len = old_body_len(text)
        new_len = new_body_len(text)
        old_r = route(old_len)
        new_r = route(new_len)
        pages.append({
            "page": doc.metadata.get("page", "?"),
            "old_len": old_len,
            "new_len": new_len,
            "old_route": old_r,
            "new_route": new_r,
            "rerouted": old_r != new_r,
        })

    rerouted = [p for p in pages if p["rerouted"]]
    return {
        "path": pdf_path,
        "pages": len(pages),
        "rerouted_pages": len(rerouted),
        "rerouted_detail": rerouted,
        "old_stage1_pages": sum(1 for p in pages if p["old_route"] == "stage1"),
        "new_stage1_pages": sum(1 for p in pages if p["new_route"] == "stage1"),
        "all_pages": pages,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    results = []
    for pdf_path in sys.argv[1:]:
        print(f"[감사] {pdf_path}", file=sys.stderr)
        try:
            r = audit_pdf(pdf_path)
        except Exception as e:
            print(f"  실패: {e}", file=sys.stderr)
            r = {"path": pdf_path, "error": str(e)}
        results.append(r)
        if "error" not in r:
            print(f"  총 {r['pages']}p, 재라우팅 {r['rerouted_pages']}p", file=sys.stderr)

    total_pages = sum(r.get("pages", 0) for r in results if "error" not in r)
    total_rerouted = sum(r.get("rerouted_pages", 0) for r in results if "error" not in r)

    summary = {
        "documents": len(results),
        "total_pages": total_pages,
        "total_rerouted_pages": total_rerouted,
        "rerouted_ratio": round(total_rerouted / total_pages, 4) if total_pages else None,
        "per_document": results,
    }
    out_path = "scripts/audit_routing_fix_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== 요약 ===")
    print(f"문서 수: {summary['documents']}, 총 페이지: {total_pages}, 재라우팅: {total_rerouted} ({summary['rerouted_ratio']})")
    print(f"결과 저장: {out_path}")


if __name__ == "__main__":
    main()
