"""
reextract_vlm_raw_flagged.py — 추론 흔적 오염 의심 20쪽의 원시(raw) VLM 출력 재수집.

run_vlm_batch.py는 정제된 텍스트 길이만 저장해 <think> 태그를 포함한 원문이 남아있지
않다. 이 스크립트는 오염 의심으로 확인된 20개 (문서, 페이지) 쌍만 다시 VLM에 요청해,
후처리(정제) 전 원문 그대로를 페이지별 텍스트 파일로 저장한다.

반드시 원격 서버(vLLM 접근 가능한 곳)에서 실행할 것 — 로컬 PC에서는 vllm 호스트에
접근할 수 없다.

사용법:
    python scripts/reextract_vlm_raw_flagged.py <PDF가 있는 폴더 경로>
    예: python scripts/reextract_vlm_raw_flagged.py /data/kci/pdf
"""
import base64
import os
import sys
import time

import fitz
import httpx

# scripts/run_vlm_batch.py 와 동일한 프롬프트(운영 _VLM_PROMPT_OCR 그대로 복사)
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

# (파일명, 1-based 페이지번호, 이전 실행 elapsed_sec, 이전 실행 정제후 글자수) — 참고용
FLAGGED_PAGES = [
    ("KCI_FI002164241.pdf", 2, 28.11, 7946),
    ("KCI_FI001390783.pdf", 15, 28.09, 14136),
    ("KCI_FI001215202.pdf", 2, 28.19, 7389),
    ("KCI_FI001159328.pdf", 8, 28.18, 7967),
    ("KCI_FI001159328.pdf", 13, 28.2, 5731),
    ("KCI_FI002996514.pdf", 12, 31.69, 4425),
    ("KCI_FI000950943.pdf", 12, 28.16, 5803),
    ("KCI_FI001715647.pdf", 13, 26.16, 4923),
    ("KCI_FI002989221.pdf", 8, 28.24, 8254),
    ("KCI_FI002989221.pdf", 15, 28.21, 7053),
    ("KCI_FI002171174.pdf", 7, 28.02, 20269),
    ("KCI_FI001498048.pdf", 3, 27.46, 5688),
    ("KCI_FI001498048.pdf", 4, 28.43, 6252),
    ("KCI_FI001498048.pdf", 7, 27.48, 6147),
    ("KCI_FI003000034.pdf", 5, 26.8, 5655),
    ("KCI_FI002537654.pdf", 7, 28.22, 5806),
    ("KCI_FI002170660.pdf", 5, 27.3, 4383),
    ("KCI_FI001485990.pdf", 7, 27.66, 10816),
    ("KCI_FI001213772.pdf", 4, 27.1, 8370),
    ("KCI_FI001175853.pdf", 1, 28.27, 5733),
]


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
    # 후처리(정제) 없이 원문 그대로 반환 — <think> 태그 포함 여부 확인용
    raw = resp.json()["choices"][0]["message"]["content"]
    return raw, elapsed


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    pdf_dir = sys.argv[1]
    vlm_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:18081/v1"
    vlm_model = sys.argv[3] if len(sys.argv) > 3 else "qwen3-vl-8b"

    out_dir = "scripts/vlm_raw_flagged"
    os.makedirs(out_dir, exist_ok=True)

    for fname, page_num, old_elapsed, old_len in FLAGGED_PAGES:
        pdf_path = os.path.join(pdf_dir, fname)
        if not os.path.exists(pdf_path):
            print(f"[건너뜀] 파일 없음: {pdf_path}", file=sys.stderr)
            continue
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=300)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
        doc.close()

        print(f"[재요청] {fname} p.{page_num} (이전: {old_elapsed}s, {old_len}자)", file=sys.stderr)
        try:
            raw, elapsed = call_vlm(vlm_url, vlm_model, img_b64, 4096, 120.0)
        except Exception as e:
            print(f"  실패: {e}", file=sys.stderr)
            continue

        has_think_open = "<think>" in raw
        has_think_close = "</think>" in raw
        out_name = f"{fname.replace('.pdf','')}_p{page_num}.txt"
        with open(os.path.join(out_dir, out_name), "w", encoding="utf-8") as f:
            f.write(raw)
        print(f"  -> {out_name} ({len(raw)}자, {elapsed:.1f}s, "
              f"<think>={has_think_open}, </think>={has_think_close})", file=sys.stderr)

    print(f"저장 위치: {out_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
