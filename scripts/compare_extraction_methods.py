"""
compare_extraction_methods.py — 1단계(ODL) 추출과 대조군(fitz 단독) 추출 비교

VLM 단독 추출(extract_text_vlm_all)은 원격 서버(vllm 컨테이너)가 있어야 호출 가능해
로컬에서는 실행할 수 없다. 이 스크립트는 로컬에서 실행 가능한 두 가지만 비교한다:
  - 실험군: extractor.py 의 1단계 로직과 동일한 방식(OpenDataLoader, 이미지→[그림] 치환,
    _clean_text)으로 추출한 텍스트
  - 대조군 A: extractor.py 의 extract_text_fitz_all() 과 동일한 방식(fitz page.get_text
    ("text").strip(), 이후 동일한 _clean_text)으로 추출한 텍스트

두 방식 모두 같은 페이지에서 몇 글자를 뽑아내는지 페이지 단위로 비교해 JSON으로 저장한다.
VLM 단독 비교는 원격 서버에서 scripts/compare_vlm.py 를 직접 실행해 별도로 채워야 한다.

사용법 (프로젝트 .venv — langchain_opendataloader_pdf 필요):
    python scripts/compare_extraction_methods.py <pdf1> <pdf2> ...
"""
import json
import re
import sys

MIN_CHARS_PER_PAGE = 50

_IMG_ANY_PATTERN = re.compile(r'!\[[^\]]*\]\([^)]+\)')


def _clean_text(text: str) -> str:
    """extractor.py:29-49 과 동일."""
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


def odl_pages(pdf_path: str) -> list[dict]:
    """extractor.py 1단계와 동일한 절차로 페이지별 텍스트 길이를 뽑는다."""
    from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader

    loader = OpenDataLoaderPDFLoader(
        file_path=pdf_path,
        format="markdown",
        image_output="embedded",
        image_format="jpeg",
        table_method="cluster",
        split_pages=True,
        keep_line_breaks=False,
    )
    documents = loader.load()
    out = []
    for doc in documents:
        raw = doc.page_content
        stripped = _IMG_ANY_PATTERN.sub('[그림]', raw)
        text = _clean_text(stripped)
        out.append({"page": doc.metadata.get("page", "?"), "odl_len": len(text)})
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    results = []
    for pdf_path in sys.argv[1:]:
        print(f"[ODL] {pdf_path}", file=sys.stderr)
        try:
            pages = odl_pages(pdf_path)
        except Exception as e:
            print(f"  실패: {e}", file=sys.stderr)
            results.append({"path": pdf_path, "error": str(e)})
            continue
        results.append({"path": pdf_path, "pages": pages})

    out_path = "scripts/odl_lengths_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
