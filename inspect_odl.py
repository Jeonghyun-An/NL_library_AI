"""
inspect_odl.py — ODL raw 마크다운 출력 확인 스크립트

사용법:
    python inspect_odl.py <pdf_path> [max_pages]

예:
    python inspect_odl.py ./sample.pdf 5
    python inspect_odl.py ./sample.pdf        # 기본 10페이지
"""
import re
import sys
import json


def run(pdf_path: str, max_pages: int = 10):
    try:
        from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader
    except ImportError:
        print("langchain-opendataloader-pdf 미설치")
        sys.exit(1)

    print(f"[ODL] 로딩: {pdf_path} (최대 {max_pages}페이지)")

    loader = OpenDataLoaderPDFLoader(
        file_path=pdf_path,
        format="markdown",
        image_output="embedded",
        image_format="jpeg",
        table_method="cluster",
        split_pages=True,
        keep_line_breaks=True,
    )
    documents = loader.load()[:max_pages]

    img_b64_pattern = re.compile(r'(!\[[^\]]*\]\()data:image/[^;]+;base64,([^)]+)(\))')

    results = []
    for doc in documents:
        raw = doc.page_content
        page_num = doc.metadata.get("page", "?")

        # base64 이미지 목록 추출
        images = []
        for m in img_b64_pattern.finditer(raw):
            b64_data = m.group(2)
            # 이미지 앞뒤 컨텍스트 (±3줄)
            start = max(0, m.start() - 200)
            end = min(len(raw), m.end() + 300)
            context = raw[start:end]
            context_truncated = img_b64_pattern.sub(r'\1[BASE64_IMAGE]\3', context)
            images.append({
                "b64_size": len(b64_data),
                "context": context_truncated,
            })

        # base64 잘라낸 마크다운 (읽기용)
        display = img_b64_pattern.sub(r'\1[IMAGE_\2...]\3', raw)
        # base64 부분만 짧게
        display = re.sub(r'\[IMAGE_(.{20})[^\]]*\]', r'[IMAGE_\1...]', display)

        results.append({
            "page": page_num,
            "char_count": len(raw),
            "image_count": len(images),
            "images": images,
            "markdown": display,
        })

        # 콘솔 출력
        sep = "=" * 60
        print(f"\n{sep}")
        print(f"[PAGE {page_num}]  chars={len(raw)}  images={len(images)}")
        print(sep)
        print(display[:3000])
        if len(display) > 3000:
            print(f"... ({len(display) - 3000}자 생략)")

        if images:
            print(f"\n--- 이미지 컨텍스트 ({len(images)}개) ---")
            for i, img in enumerate(images):
                print(f"\n[이미지 {i+1}] base64 크기={img['b64_size']}bytes")
                print(img["context"])

    # JSON으로도 저장
    out_path = pdf_path.replace(".pdf", "_odl_raw.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n\n결과 저장: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf = sys.argv[1]
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    run(pdf, pages)
