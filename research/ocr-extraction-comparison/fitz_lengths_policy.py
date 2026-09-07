"""fitz_lengths_lit.py — 정책·재정 자료 200건의 fitz 단독 추출량.

ODL은 프로젝트 .venv, fitz는 별도 환경에만 설치되어 있어 한 프로세스에서 함께 쓸 수 없다.
그래서 라우팅 감사(audit_routing_policy.py)와 분리해 실행하고, 분석 단계에서
(파일, 페이지) 기준으로 병합한다. 정제 로직은 감사 스크립트와 동일하다.

사용법:
    python scripts/fitz_lengths_policy.py
"""
import io
import json
import os
import re
import sys

import fitz

BASE = "C:/Users/LANDSOFT/Desktop/SKOVIX/output/"
SAMPLE = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/policy_sample200.txt"
OUT = "C:/Users/LANDSOFT/mygit/NL_library_AI/scripts/fitz_lengths_policy200.json"


def _clean_text(text: str) -> str:
    """audit_routing_policy.py 와 동일."""
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


def main():
    names = [l.strip() for l in io.open(SAMPLE, encoding="utf-8") if l.strip()]
    results = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    done = {r["file"] for r in results}

    for i, name in enumerate(names, 1):
        if name in done:
            continue
        try:
            d = fitz.open(BASE + name)
        except Exception as e:
            print(f"[{i}/{len(names)}] 실패 {name}: {e}", file=sys.stderr)
            results.append({"file": name, "error": str(e)})
            continue
        pages = [{"page": n, "fitz_len": len(_clean_text(p.get_text("text")))}
                 for n, p in enumerate(d, 1)]
        d.close()
        results.append({"file": name, "pdf_pages": len(pages), "pages": pages})
        print(f"[{i}/{len(names)}] {name} {len(pages)}쪽", file=sys.stderr)
        json.dump(results, io.open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    ok = [r for r in results if "pages" in r]
    print(f"\n완료: {len(ok)}건 {sum(r['pdf_pages'] for r in ok)}쪽", file=sys.stderr)


if __name__ == "__main__":
    main()
