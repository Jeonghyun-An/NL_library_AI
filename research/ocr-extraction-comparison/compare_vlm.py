"""
compare_vlm.py — Qwen3-VL(vllm) vs Gemma-3(gemma) OCR 품질 비교

로컬 PDF를 지정 페이지만 렌더링해서 base64로 인코딩한 뒤, 두 엔드포인트에
동일한 프롬프트(운영 extractor.py의 _VLM_PROMPT_OCR 그대로)로 요청을 보내
결과를 나란히 출력한다. 수동 이미지 업로드 없이 PDF 경로만 넘기면 된다.

사용법:
    python scripts/compare_vlm.py "C:/path/to/file.pdf" --page 3
    python scripts/compare_vlm.py "C:/path/to/file.pdf" --page 3 --dpi 300 \
        --vlm-url http://<server>:18081/v1 --vlm-model qwen3-vl-8b \
        --gemma-url http://<server>:18080/v1 --gemma-model gemma-3-12b

기본값은 운영 compose의 노출 포트(18081=vllm, 18080=gemma)를 그대로 가리킨다.
서버 밖(로컬 Windows)에서 실행할 거면 방화벽/네트워크 경로가 열려 있어야 한다.
막혀 있으면 서버에 SSH로 들어가서 이 스크립트를 직접 돌리면 된다
(그때는 --vlm-url http://localhost:18081/v1 등으로).
"""
import argparse
import base64
import sys
import time

import fitz  # PyMuPDF
import httpx

OCR_PROMPT = """\
이 페이지의 모든 텍스트를 정확히 추출하세요.

레이아웃 처리 규칙:
- 2단(두 칸) 구성이면: 반드시 왼쪽 단을 위에서 아래로 모두 읽은 뒤, 오른쪽 단을 위에서 아래로 읽으세요. 양쪽 단을 줄 단위로 섞지 마세요.
- 1단(전체 폭) 구성이면: 위에서 아래로 순서대로 읽으세요.
- 단 구분이 불명확하면 텍스트 흐름이 자연스러운 방향으로 읽으세요.

기타 규칙:
- 표가 있으면 마크다운 표(|---|)로 변환하세요.
- 그림·사진은 [그림: 한 줄 설명]으로 표기하세요.
- 마크다운 코드 블록(```)이나 부연 설명 없이 내용만 출력하세요.
- 이미지에 없는 내용은 추가하지 마세요."""


def render_page_b64(pdf_path: str, page_num: int, dpi: int) -> str:
    doc = fitz.open(pdf_path)
    if page_num < 0 or page_num >= len(doc):
        raise ValueError(f"페이지 {page_num}가 범위를 벗어남 (문서 총 {len(doc)}페이지, 0-indexed)")
    pix = doc[page_num].get_pixmap(dpi=dpi)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode()


def call_vlm(base_url: str, model: str, img_b64: str, max_tokens: int, timeout: float) -> tuple[str, float]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": OCR_PROMPT},
                ],
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    t0 = time.perf_counter()
    resp = httpx.post(f"{base_url}/chat/completions", json=payload, timeout=timeout)
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    return text, elapsed


def main():
    ap = argparse.ArgumentParser(description="Qwen3-VL vs Gemma-3 OCR 비교")
    ap.add_argument("pdf_path", help="로컬 PDF 파일 경로")
    ap.add_argument("--page", type=int, default=0, help="비교할 페이지 (0-indexed, 기본 0)")
    ap.add_argument("--dpi", type=int, default=300, help="렌더링 DPI (기본 300, FITZ_DPI와 동일)")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--vlm-url", default="http://localhost:18081/v1", help="Qwen3-VL(vllm) 엔드포인트")
    ap.add_argument("--vlm-model", default="qwen3-vl-8b")
    ap.add_argument("--gemma-url", default="http://localhost:18080/v1", help="Gemma-3 엔드포인트")
    ap.add_argument("--gemma-model", default="gemma-3-12b")
    ap.add_argument("--skip-vlm", action="store_true", help="Qwen3-VL 호출 생략")
    ap.add_argument("--skip-gemma", action="store_true", help="Gemma-3 호출 생략")
    args = ap.parse_args()

    print(f"[렌더링] {args.pdf_path} p.{args.page} @ {args.dpi}dpi ...")
    img_b64 = render_page_b64(args.pdf_path, args.page, args.dpi)
    print(f"[렌더링 완료] 이미지 크기: {len(img_b64) // 1024}KB (base64)\n")

    results: dict[str, tuple[str, float]] = {}

    if not args.skip_vlm:
        print(f"[호출] Qwen3-VL ({args.vlm_url}, {args.vlm_model}) ...")
        try:
            results["Qwen3-VL"] = call_vlm(args.vlm_url, args.vlm_model, img_b64, args.max_tokens, args.timeout)
        except Exception as e:
            print(f"  실패: {e}", file=sys.stderr)

    if not args.skip_gemma:
        print(f"[호출] Gemma-3 ({args.gemma_url}, {args.gemma_model}) ...")
        try:
            results["Gemma-3"] = call_vlm(args.gemma_url, args.gemma_model, img_b64, args.max_tokens, args.timeout)
        except Exception as e:
            print(f"  실패: {e}", file=sys.stderr)

    for name, (text, elapsed) in results.items():
        print(f"\n{'=' * 70}")
        print(f"■ {name}  ({elapsed:.1f}s, {len(text)}자)")
        print("=" * 70)
        print(text)

    if len(results) == 2:
        print(f"\n{'=' * 70}")
        print("■ 결과를 비교해서 Gemma-3가 Qwen3-VL 수준의 OCR 정확도를 내는지 확인하세요.")
        print("  (레이아웃 순서, 표 인식, 누락/환각 여부 위주로)")


if __name__ == "__main__":
    main()
