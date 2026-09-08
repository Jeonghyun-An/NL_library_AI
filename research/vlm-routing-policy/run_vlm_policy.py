"""run_vlm_policy.py — 정책·재정 자료에서 재배정된 쪽에 대한 VLM 추출.

원시 길이 기반 판정이 "본문 충분"으로 오판해 1단계 출력을 그대로 쓴 쪽(재배정 쪽)에
VLM을 적용해, 규칙을 고쳤을 때 실제로 얼마를 회복하는지 측정한다. 비교 대조를 위해
같은 문서에서 두 규칙이 모두 "본문 충분"으로 일치 판정한 쪽도 함께 돌린다.

대상 페이지는 vlm_policy_selection.json 에서 읽는다(스크립트에 박아넣지 않는다):
    {"CNTS-xxx/CNTS-xxx.pdf": {"reroute": [44, 155], "control": [40, 42]}, ...}

반드시 원격 서버(vLLM 접근 가능한 곳)에서 실행할 것.

사용법:
    python run_vlm_policy.py <PDF 루트 폴더> [vlm_url] [vlm_model]
    예: python run_vlm_policy.py ./policy_pdfs
"""
import base64
import os
import re
import sys
import time

import fitz
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


def _clean_text(text):
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


def max_repeat_count(text):
    """정제된 텍스트에서 가장 많이 반복된 줄의 반복 횟수(빈 줄 제외) — 반복 루프 탐지용."""
    counts = {}
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        counts[line] = counts.get(line, 0) + 1
    return max(counts.values()) if counts else 0


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
    raw = resp.json()["choices"][0]["message"]["content"]
    return raw, elapsed




import json as _json

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    pdf_dir = sys.argv[1]
    vlm_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:18081/v1"
    vlm_model = sys.argv[3] if len(sys.argv) > 3 else "qwen3-vl-8b"

    sel_path = "vlm_policy_selection.json"
    out_path = "vlm_policy_result.json"
    raw_dir = "vlm_policy_raw"
    os.makedirs(raw_dir, exist_ok=True)

    with open(sel_path, encoding="utf-8") as f:
        selection = _json.load(f)

    results = []
    if os.path.exists(out_path):
        results = _json.load(open(out_path, encoding="utf-8"))
    done = {r["doc"] for r in results}

    total = len(selection)
    for i, (rel, groups) in enumerate(selection.items(), 1):
        if rel in done:
            print(f"[{i}/{total}] [skip] {rel}", file=sys.stderr)
            continue
        pdf_path = os.path.join(pdf_dir, rel)
        if not os.path.exists(pdf_path):
            print(f"[{i}/{total}] [파일없음] {pdf_path}", file=sys.stderr)
            continue

        todo = [(pg, kind) for kind in ("reroute", "control")
                for pg in groups.get(kind, [])]
        print(f"[{i}/{total}] {rel} ({len(todo)}쪽)", file=sys.stderr)
        doc = fitz.open(pdf_path)
        page_results = []
        for pg, kind in todo:
            if pg > len(doc):
                continue
            pix = doc[pg - 1].get_pixmap(dpi=300)
            img_b64 = base64.b64encode(pix.tobytes("png")).decode()
            try:
                raw, elapsed = call_vlm(vlm_url, vlm_model, img_b64, 4096, 180.0)
            except Exception as e:
                print(f"    p.{pg}({kind}): 실패 — {e}", file=sys.stderr)
                continue
            text = _clean_text(raw)
            rep = max_repeat_count(text)
            page_results.append({
                "page": pg, "kind": kind, "vlm_len": len(text),
                "elapsed_sec": round(elapsed, 2), "max_repeat_count": rep,
            })
            stem = rel.replace("/", "_").replace("\\", "_").replace(".pdf", "")
            with open(os.path.join(raw_dir, f"{stem}_p{pg}.txt"), "w",
                      encoding="utf-8") as f:
                f.write(raw)
            flag = f" [반복{rep}회 의심]" if rep >= 10 else ""
            print(f"    p.{pg}({kind}): {len(text)}자, {elapsed:.1f}s{flag}",
                  file=sys.stderr)
        doc.close()

        results.append({"doc": rel, "pages": page_results})
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"저장: {out_path}, 원문: {raw_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
