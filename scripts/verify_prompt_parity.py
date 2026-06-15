"""프롬프트 외부화 검증 — git HEAD 원본 상수 vs YAML 렌더 결과 비교 (1회성 검증 도구)."""
import ast
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from services.prompts import PromptLibrary  # noqa: E402

lib = PromptLibrary(APP / "domains" / "nl_library" / "prompts")


def old_constants(rel_path: str) -> dict:
    src = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return out


fails = []


def check(label: str, expected: str, actual: str):
    if expected != actual:
        fails.append(label)
        print(f"FAIL {label}")
        for i, (e, a) in enumerate(zip(expected.splitlines(), actual.splitlines())):
            if e != a:
                print(f"  line {i}: 원본={e!r}\n           렌더={a!r}")
                break
        if len(expected.splitlines()) != len(actual.splitlines()):
            print(f"  줄 수: 원본 {len(expected.splitlines())} vs 렌더 {len(actual.splitlines())}")
    else:
        print(f"OK   {label}")


summ = old_constants("app/services/ingestion/summarizer.py")
VARS = {"title": "T", "text": "X", "author": "A", "section_summaries": "S",
        "publisher": "P", "pub_date": "D"}

for dt in ("paper", "literature", "book", "policy"):
    s, u, p = lib.get("section_summary", dt).render(**VARS)
    check(f"section_summary.{dt}.system", summ["_SECTION_SYSTEMS"][dt], s)
    check(f"section_summary.{dt}.user",
          summ["_SECTION_PROMPT"].format(title="T", text="X"), u)
    assert p == {"max_tokens": 4000, "temperature": 0.1}, f"params {dt}"

    s, u, p = lib.get("book_summary", dt).render(**VARS)
    check(f"book_summary.{dt}.system", summ["_BOOK_FROM_SECTIONS_SYSTEMS"][dt], s)
    check(f"book_summary.{dt}.user",
          summ["_BOOK_FROM_SECTIONS_PROMPT"].format(title="T", author="A", section_summaries="S"), u)
    assert p == {"max_tokens": 5000, "temperature": 0.1}, f"params {dt}"

s, u, p = lib.get("introduction").render(**VARS)
check("introduction.system", summ["_INTRODUCTION_SYSTEM"], s)
check("introduction.user", summ["_INTRODUCTION_PROMPT"].format(
    title="T", author="A", publisher="P", pub_date="D", section_summaries="S"), u)
assert p == {"max_tokens": 5000, "temperature": 0.5}

qr = old_constants("app/services/search/query_rewriter.py")
s, u, p = lib.get("query_rewrite").render(query="Q")
check("query_rewrite.system", qr["_REWRITE_SYSTEM"], s)
check("query_rewrite.user", "원본 쿼리: Q", u)
assert p == {"max_tokens": 256, "temperature": 0.0}

mf = old_constants("app/services/search/metadata_filter.py")
s, u, p = lib.get("metadata_filter").render(today="2026-06-11", current_year=2026, query="Q")
check("metadata_filter.system", mf["_SYSTEM"], s)
check("metadata_filter.user", "오늘 날짜: 2026-06-11 (현재 연도: 2026)\n검색어: Q", u)
assert p == {"max_tokens": 128, "temperature": 0.0}

bc = old_constants("app/services/chat/book_chat.py")
s, _, p = lib.get("book_chat").render(title="T", author="A", pub_date=", D", summary="S", themes="TH")
check("book_chat.system", bc["_SYSTEM_TEMPLATE"].format(
    title="T", author="A", pub_date=", D", summary="S", themes="TH"), s)
assert p == {"max_tokens": 10000, "temperature": 0.3}

cg = old_constants("app/services/ingestion/cover_generator.py")
s, u, p = lib.get("cover_prompt").render(
    title="T", author="A", kdc="K", themes="TH", introduction="I", summary="S")
check("cover_prompt.system", cg["_COVER_PROMPT_SYSTEM"], s)
check("cover_prompt.user", cg["_COVER_PROMPT_USER"].format(
    title="T", author="A", kdc="K", themes="TH", introduction="I", summary="S"), u)
assert p == {"max_tokens": 400, "temperature": 0.7}

print()
if fails:
    print(f"불일치 {len(fails)}건: {fails}")
    sys.exit(1)
print("모든 프롬프트가 원본과 바이트 동일합니다.")
