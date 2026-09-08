"""
run_vlm_batch.py — VLM 단독 추출(대조군 B) 일괄 실행. 원격 서버에서 실행할 것.

이 스크립트는 vLLM(Qwen3-VL) 엔드포인트에 실제로 접속해야 하므로, 로컬 Windows에서는
돌릴 수 없다(vllm 호스트가 서버 내부 docker 네트워크에만 존재). 서버에 SSH로 접속한
뒤 아래 절차로 실행한다.

절차:
1. 로컬의 대상 PDF 5건을 서버로 옮긴다 (scp 등).
2. 서버에서: python scripts/run_vlm_batch.py <pdf1> <pdf2> ...
   (엔드포인트가 기본값과 다르면 --vlm-url / --vlm-model 로 지정)
3. 생성된 scripts/vlm_lengths_result.json 을 로컬로 다시 가져와,
   compare_extraction_methods.py 가 만든 odl/fitz 결과와 합치면 3자 비교가 완성된다.

extractor.py 의 extract_text_vlm_all() / _extract_with_vlm() 과 동일한 방식으로
페이지를 이미지로 렌더링해 VLM에 전달하고, 페이지별 글자 수와 처리 시간을 기록한다.
프롬프트는 scripts/compare_vlm.py 에 있는, 운영 _VLM_PROMPT_OCR 그대로 복사한 것을 재사용한다.

사용법:
    python scripts/run_vlm_batch.py <pdf1> <pdf2> ... \\
        [--vlm-url http://localhost:18081/v1] [--vlm-model qwen3-vl-8b] \\
        [--dpi 300] [--max-tokens 4096] [--timeout 120] [--max-pages N]
"""
import argparse
import base64
import json
import re
import sys
import time

import fitz  # PyMuPDF
import httpx

# scripts/compare_vlm.py 의 OCR_PROMPT 와 동일 (운영 _VLM_PROMPT_OCR 그대로 복사한 것)
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


def _clean_text(text: str) -> str:
    """extractor.py:29-49 과 동일 — odl/fitz 쪽과 같은 정제를 거쳐야 글자 수가 공정하게 비교된다."""
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
    return text.strip()


def call_vlm(base_url, model, img_b64, max_tokens, timeout):
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": OCR_PROMPT},
            ],
        }],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    t0 = time.perf_counter()
    resp = httpx.post(f"{base_url}/chat/completions", json=payload, timeout=timeout)
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    return text, elapsed


def process_pdf(pdf_path, args):
    doc = fitz.open(pdf_path)
    pages = []
    n = len(doc) if not args.max_pages else min(len(doc), args.max_pages)
    for i in range(n):
        page = doc[i]
        pix = page.get_pixmap(dpi=args.dpi)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
        try:
            raw, elapsed = call_vlm(args.vlm_url, args.vlm_model, img_b64, args.max_tokens, args.timeout)
            text = _clean_text(raw)
            pages.append({"page": i + 1, "vlm_len": len(text), "elapsed_sec": round(elapsed, 2)})
            print(f"  p.{i+1}/{n}: {len(text)}자 ({elapsed:.1f}s)", file=sys.stderr)
        except Exception as e:
            pages.append({"page": i + 1, "error": str(e)})
            print(f"  p.{i+1}/{n}: 실패 — {e}", file=sys.stderr)
    doc.close()
    return pages


def main():
    ap = argparse.ArgumentParser(description="VLM 단독 추출 일괄 실행 (대조군 B)")
    ap.add_argument("pdfs", nargs="+", help="대상 PDF 경로들")
    ap.add_argument("--vlm-url", default="http://localhost:18081/v1")
    ap.add_argument("--vlm-model", default="qwen3-vl-8b")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--max-pages", type=int, default=None, help="문서당 처리할 최대 페이지 수(비용/시간 절약용)")
    args = ap.parse_args()

    results = []
    for pdf_path in args.pdfs:
        print(f"[VLM] {pdf_path}", file=sys.stderr)
        pages = process_pdf(pdf_path, args)
        results.append({"path": pdf_path, "pages": pages})

    out_path = "scripts/vlm_lengths_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
