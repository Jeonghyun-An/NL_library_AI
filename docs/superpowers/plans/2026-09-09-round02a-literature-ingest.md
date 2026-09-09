# round02a — 공공영역 문학 215권 자동 적재 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `skovix_literature_100.csv` + `skovix_literature_additional.csv`(합계 283행, 정제 후 215권)를 다운로드·PDF 변환·카탈로그 적재·임베딩까지 마쳐 NL-Lib 검색 데모에 노출한다.

**Architecture:** 신규 코드는 4개 로컬 스크립트(`scripts/literature_ingest/` — CSV 병합, 다운로드+PDF 렌더, 카탈로그 upsert, 매니페스트 생성)뿐이다. 핵심 파이프라인(`services/ingestion/extractor.py`·`stages.py`·`indexer.py`)과 기존 대량반입 도구(`scripts/bulk_ingest/upload_from_manifest.py`, admin 잡 API)는 무변경 재사용. Task 1~5는 고전적 TDD(pytest, 순수 함수 — 실제 코드에 네트워크·DB 의존 없음)로 진행하고, Task 6~12는 실제 배치를 실행·검증하는 운영 단계라 "Run: … Expected: …" 형식으로 진행한다(round01 Task 10~15와 동일한 패턴 — 파일을 만들어내는 실행이라 red-green TDD 대상이 아님).

**Tech Stack:** Python(표준 라이브러리 + `httpx`·`PyMuPDF`(`fitz`), 둘 다 `app/requirements.txt`에 이미 있음 — 신규 의존성 없음), pytest, PostgreSQL(`upsert_catalog_records`), MinIO, Celery(admin 잡 API 경유).

**선행 확인 사항:**
- spec: `docs/superpowers/specs/2026-09-09-round02a-literature-ingest-design.md` (§4 세부규칙·§6 데이터 정제 근거 — 이 plan의 모든 수치·정정값의 출처).
- 원본 CSV: `C:\Users\LANDSOFT\Downloads\skovix_literature_100.csv`(100행), `C:\Users\LANDSOFT\Downloads\skovix_literature_additional.csv`(183행). 두 파일 모두 로컬에 존재 확인됨.
- Task 5(카탈로그 upsert)은 `app/`의 `repositories.catalog_bulk`·`models.book`·`db.postgres`를 import하므로 **DB 접속이 가능한 환경(서버 또는 dev 스택 접속 가능한 환경)에서 실행**해야 한다 — `scripts/bulk_ingest/`의 기존 도구들과 달리 로컬 PC 단독으로는 실행 불가. 각 Task에 실행 위치를 명시한다.

---

### Task 1: `scripts/literature_ingest/merge_csvs.py` — CSV 병합 + 정제

**Files:**
- Create: `scripts/literature_ingest/merge_csvs.py`
- Create: `scripts/literature_ingest/tests/__init__.py`
- Create: `scripts/literature_ingest/tests/test_merge_csvs.py`

spec §6에서 확정된 4개 정정값(The Star Rover→1162, From the Earth to the Moon→83, Martin Eden→1056, Carmen→2465)과 Kafka `The Castle` 제외를 하드코딩하고, 두 CSV를 병합해 최종 215행을 만든다.

- [ ] **Step 1: 디렉토리 확인**

Run: `test -d scripts/literature_ingest && echo EXISTS || echo MISSING`
Expected: `MISSING`

- [ ] **Step 2: 실패하는 테스트 작성**

`scripts/literature_ingest/tests/__init__.py` (빈 파일):
```python
```

`scripts/literature_ingest/tests/test_merge_csvs.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from merge_csvs import (
    parse_ebook_id,
    compute_book_id,
    normalize_row,
    apply_corrections,
    merge_and_clean,
)


def test_parse_ebook_id_extracts_number():
    assert parse_ebook_id("https://www.gutenberg.org/ebooks/1342.epub3.images") == "1342"


def test_parse_ebook_id_none_for_non_gutenberg_url():
    assert parse_ebook_id("https://standardebooks.org/ebooks/foo/bar") is None


def test_compute_book_id_gutenberg():
    row = {"download_link": "https://www.gutenberg.org/ebooks/1342.epub3.images"}
    assert compute_book_id(row) == "LIT-GUTENBERG-1342"


def test_compute_book_id_standard_ebooks_falls_back_to_slug():
    row = {
        "download_link": "https://standardebooks.org/ebooks/foo/bar",
        "source_url": "https://standardebooks.org/ebooks/foo/bar",
    }
    assert compute_book_id(row) == "LIT-STDEBOOKS-foo-bar"


def test_normalize_row_maps_direct_epub3_url_to_download_link():
    raw = {
        "title": "Moby-Dick",
        "author": "Herman Melville",
        "source": "Project Gutenberg",
        "download_format": "EPUB3 / HTML / TXT",
        "copyright_status": "Project Gutenberg: U.S. public-domain basis; verify Korean use separately",
        "source_url": "https://www.gutenberg.org/ebooks/2701",
        "direct_epub3_url": "https://www.gutenberg.org/ebooks/2701.epub3.images",
    }
    row = normalize_row(raw)
    assert row["download_link"] == "https://www.gutenberg.org/ebooks/2701.epub3.images"


def test_normalize_row_keeps_download_link_when_already_present():
    raw = {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "source": "Project Gutenberg",
        "download_format": "EPUB3/TXT/HTML",
        "copyright_status": "Public domain (US)",
        "source_url": "https://www.gutenberg.org/ebooks/1342",
        "download_link": "https://www.gutenberg.org/ebooks/1342.epub3.images",
    }
    row = normalize_row(raw)
    assert row["download_link"] == "https://www.gutenberg.org/ebooks/1342.epub3.images"


def test_apply_corrections_fixes_known_wrong_links():
    rows = [
        {"title": "The Star Rover", "download_link": "https://www.gutenberg.org/ebooks/967.epub3.images"},
        {"title": "Nicholas Nickleby", "download_link": "https://www.gutenberg.org/ebooks/967.epub3.images"},
        {"title": "From the Earth to the Moon", "download_link": "https://www.gutenberg.org/ebooks/18857.epub3.images"},
        {"title": "Martin Eden", "download_link": "https://www.gutenberg.org/ebooks/910.epub3.images"},
        {"title": "Carmen", "download_link": "https://www.gutenberg.org/ebooks/2226.epub3.images"},
        {"title": "Untouched Book", "download_link": "https://www.gutenberg.org/ebooks/999.epub3.images"},
    ]
    fixed = apply_corrections(rows)
    by_title = {r["title"]: r["download_link"] for r in fixed}
    assert by_title["The Star Rover"] == "https://www.gutenberg.org/ebooks/1162.epub3.images"
    assert by_title["Nicholas Nickleby"] == "https://www.gutenberg.org/ebooks/967.epub3.images"
    assert by_title["From the Earth to the Moon"] == "https://www.gutenberg.org/ebooks/83.epub3.images"
    assert by_title["Martin Eden"] == "https://www.gutenberg.org/ebooks/910.epub3.images".replace("910", "1056")
    assert by_title["Carmen"] == "https://www.gutenberg.org/ebooks/2226.epub3.images".replace("2226", "2465")
    assert by_title["Untouched Book"] == "https://www.gutenberg.org/ebooks/999.epub3.images"


def test_merge_and_clean_excludes_castle_deduplicates_and_resolves_conflicts():
    original = [
        {"no": "1", "title": "Pride and Prejudice", "author": "Jane Austen", "source": "Project Gutenberg",
         "download_format": "EPUB3/TXT/HTML", "copyright_status": "Public domain (US)",
         "source_url": "https://www.gutenberg.org/ebooks/1342",
         "download_link": "https://www.gutenberg.org/ebooks/1342.epub3.images"},
        {"no": "2", "title": "The Trial", "author": "Franz Kafka", "source": "Project Gutenberg",
         "download_format": "EPUB3/TXT/HTML", "copyright_status": "Public domain (US)",
         "source_url": "https://www.gutenberg.org/ebooks/7849",
         "download_link": "https://www.gutenberg.org/ebooks/7849.epub3.images"},
        {"no": "3", "title": "The Castle", "author": "Franz Kafka", "source": "Project Gutenberg",
         "download_format": "EPUB3/TXT/HTML", "copyright_status": "Public domain (US)",
         "source_url": "https://www.gutenberg.org/ebooks/7849",
         "download_link": "https://www.gutenberg.org/ebooks/7849.epub3.images"},
    ]
    additional = [
        # 원본과 완전 중복 (교차중복) -> 스킵
        {"title": "Pride and Prejudice", "author": "Jane Austen", "source": "Project Gutenberg",
         "download_format": "EPUB3 / HTML / TXT", "copyright_status": "verify Korean use separately",
         "source_url": "https://www.gutenberg.org/ebooks/1342",
         "direct_epub3_url": "https://www.gutenberg.org/ebooks/1342.epub3.images"},
        # 내부 충돌 그룹(967) - 둘 다 원본과 안 겹치므로 정정 후 둘 다 추가돼야 함
        {"title": "Nicholas Nickleby", "author": "Charles Dickens", "source": "Project Gutenberg",
         "download_format": "EPUB3 / HTML / TXT", "copyright_status": "verify Korean use separately",
         "source_url": "https://www.gutenberg.org/ebooks/967",
         "direct_epub3_url": "https://www.gutenberg.org/ebooks/967.epub3.images"},
        {"title": "The Star Rover", "author": "Jack London", "source": "Project Gutenberg",
         "download_format": "EPUB3 / HTML / TXT", "copyright_status": "verify Korean use separately",
         "source_url": "https://www.gutenberg.org/ebooks/967",
         "direct_epub3_url": "https://www.gutenberg.org/ebooks/967.epub3.images"},
        # 신규 정상 항목
        {"title": "Moby-Dick; Or, The Whale", "author": "Herman Melville", "source": "Project Gutenberg",
         "download_format": "EPUB3 / HTML / TXT", "copyright_status": "verify Korean use separately",
         "source_url": "https://www.gutenberg.org/ebooks/2701",
         "direct_epub3_url": "https://www.gutenberg.org/ebooks/2701.epub3.images"},
    ]

    merged = merge_and_clean(original, additional)
    titles = {r["title"] for r in merged}

    assert "The Castle" not in titles
    # 원본 정리분(Pride and Prejudice, The Trial) 2건 + 추가행 중 원본과 안 겹치는
    # Nicholas Nickleby·The Star Rover·Moby-Dick 3건 = 5건 (Pride and Prejudice 중복 1건은 스킵)
    assert len(merged) == 5
    assert sum(1 for r in merged if r["title"] == "Pride and Prejudice") == 1
    star_rover = next(r for r in merged if r["title"] == "The Star Rover")
    assert "1162" in star_rover["download_link"]
    nickleby = next(r for r in merged if r["title"] == "Nicholas Nickleby")
    assert "967" in nickleby["download_link"]
    book_ids = [r["book_id"] for r in merged]
    assert len(book_ids) == len(set(book_ids))  # 전부 유일
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_merge_csvs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'merge_csvs'` (아직 구현 없음)

- [ ] **Step 4: 최소 구현 작성**

`scripts/literature_ingest/merge_csvs.py`:
```python
"""
merge_csvs.py — round02a 문학 CSV 2종 병합·정제

skovix_literature_100.csv(원본) + skovix_literature_additional.csv(추가)를
ebook ID 기준으로 병합해 중복·충돌을 제거한 최종 목록을 만든다.
정정값 출처: docs/superpowers/specs/2026-09-09-round02a-literature-ingest-design.md §6
[로컬 PC에서 실행] — 네트워크·DB 접속 불필요.
"""
import csv
import json
import re
from pathlib import Path

GUTENBERG_ID_RE = re.compile(r"/ebooks/(\d+)")

# spec §6.2 — 내부 충돌 5쌍 중 오답이었던 쪽만 정정. 정답이었던 쪽(Nicholas Nickleby=967,
# Journey to the Centre of the Earth=18857, White Fang=910, Kim=2226)은 원래 값 그대로라 여기 없음.
TITLE_ID_CORRECTIONS: dict[str, str] = {
    "The Star Rover": "1162",
    "From the Earth to the Moon": "83",
    "Martin Eden": "1056",
    "Carmen": "2465",
}

CASTLE_TITLE = "The Castle"


def parse_ebook_id(url: str) -> str | None:
    """Gutenberg URL에서 ebook ID 추출. Gutenberg가 아니면 None."""
    m = GUTENBERG_ID_RE.search(url or "")
    return m.group(1) if m else None


def compute_book_id(row: dict) -> str:
    """정규화된 row(download_link 확정 후) -> NL-Lib book_id(cnts_id)."""
    eid = parse_ebook_id(row.get("download_link", ""))
    if eid:
        return f"LIT-GUTENBERG-{eid}"
    # Standard Ebooks 등 비-Gutenberg 출처: URL 마지막 두 경로 세그먼트를 슬러그로
    url = row.get("source_url") or row.get("download_link") or ""
    parts = [p for p in url.rstrip("/").split("/") if p]
    slug = "-".join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else "unknown")
    return f"LIT-STDEBOOKS-{slug}"


def normalize_row(raw: dict) -> dict:
    """두 CSV의 스키마 차이(download_link vs direct_epub3_url) 통일."""
    row = dict(raw)
    if not row.get("download_link"):
        row["download_link"] = row.get("direct_epub3_url", "")
    return row


def apply_corrections(rows: list[dict]) -> list[dict]:
    """제목 기준으로 알려진 오류 ebook ID를 정정(spec §6.2)."""
    fixed = []
    for row in rows:
        row = dict(row)
        corrected_id = TITLE_ID_CORRECTIONS.get(row.get("title", ""))
        if corrected_id:
            row["download_link"] = f"https://www.gutenberg.org/ebooks/{corrected_id}.epub3.images"
        fixed.append(row)
    return fixed


def load_csv_normalized(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [normalize_row(r) for r in csv.DictReader(f)]


def merge_and_clean(original_rows: list[dict], additional_rows: list[dict]) -> list[dict]:
    """spec §6 전체 절차: Castle 제외 -> 추가행 정정 -> 교차중복 제거 -> book_id 부여.

    입력 행은 정규화 전(raw CSV DictReader 결과)이어도, 정규화 후(load_csv_normalized
    결과)여도 상관없다 — 아래서 normalize_row()를 다시 적용한다(멱등적이라 안전).
    """
    original_clean = [normalize_row(r) for r in original_rows if r.get("title") != CASTLE_TITLE]
    for row in original_clean:
        row["book_id"] = compute_book_id(row)
    original_ids = {parse_ebook_id(r["download_link"]) for r in original_clean} - {None}

    additional_fixed = apply_corrections([normalize_row(r) for r in additional_rows])

    seen_ids: set[str] = set()
    additional_clean: list[dict] = []
    for row in additional_fixed:
        eid = parse_ebook_id(row["download_link"])
        if eid and eid in original_ids:
            continue  # 원본과 교차중복(§6.3)
        if eid and eid in seen_ids:
            continue  # 정정 후에도 남은 내부 중복(안전장치 — 현재 데이터엔 없어야 함)
        if eid:
            seen_ids.add(eid)
        row["book_id"] = compute_book_id(row)
        additional_clean.append(row)

    return original_clean + additional_clean


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    original = load_csv_normalized(str(root / "skovix_literature_100.csv"))
    additional = load_csv_normalized(str(root / "skovix_literature_additional.csv"))

    merged = merge_and_clean(original, additional)

    out_dir = Path(__file__).resolve().parent / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "merged_books.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"원본 {len(original)}행 -> 최종 {len(merged)}권 -> {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_merge_csvs.py -v`
Expected: `8 passed`

- [ ] **Step 6: 커밋**

```bash
git add scripts/literature_ingest/merge_csvs.py scripts/literature_ingest/tests/__init__.py scripts/literature_ingest/tests/test_merge_csvs.py
git commit -m "[Feat] round02a — CSV 2종 병합·정제 스크립트(merge_csvs.py)"
```

---

### Task 2: `scripts/literature_ingest/render_pdf.py` — 구텐베르크 본문 정제 + PDF 렌더

**Files:**
- Create: `scripts/literature_ingest/render_pdf.py`
- Create: `scripts/literature_ingest/tests/test_render_pdf.py`

`strip_gutenberg_boilerplate()`(순수 함수, 텍스트 문자열만 다룸)와 `render_book_pdf()`(PyMuPDF로 텍스트 -> PDF 파일, 네트워크 없이 로컬에서 테스트 가능)를 TDD로 만든다. 실제 다운로드는 Task 3에서 별도 모듈로 분리.

- [ ] **Step 1: 실패하는 테스트 작성**

`scripts/literature_ingest/tests/test_render_pdf.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF — app/requirements.txt에 이미 있는 의존성
from render_pdf import strip_gutenberg_boilerplate, render_book_pdf


def test_strip_boilerplate_removes_header_and_footer():
    raw = (
        "The Project Gutenberg eBook of Foo\n"
        "This eBook is for the use of anyone...\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
        "Chapter 1\n"
        "It was a dark and stormy night.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
        "This file should be named foo.txt...\n"
    )
    body = strip_gutenberg_boilerplate(raw)
    assert "Project Gutenberg eBook of Foo" not in body
    assert "This file should be named" not in body
    assert "It was a dark and stormy night." in body


def test_strip_boilerplate_handles_start_of_this_variant():
    raw = (
        "header junk\n"
        "*** START OF THIS PROJECT GUTENBERG EBOOK BAR ***\n"
        "Body text here.\n"
        "*** END OF THIS PROJECT GUTENBERG EBOOK BAR ***\n"
        "footer junk\n"
    )
    body = strip_gutenberg_boilerplate(raw)
    assert body.strip() == "Body text here."


def test_strip_boilerplate_returns_original_if_markers_missing():
    raw = "Plain text with no Gutenberg markers at all."
    assert strip_gutenberg_boilerplate(raw) == raw


def test_render_book_pdf_creates_readable_pdf(tmp_path):
    out_path = tmp_path / "test.pdf"
    render_book_pdf(
        title="Test Book",
        author="Test Author",
        body_text="Paragraph one.\n\nParagraph two, a bit longer to check wrapping works.",
        out_path=str(out_path),
    )
    assert out_path.exists()
    assert out_path.stat().st_size > 0

    doc = fitz.open(str(out_path))
    assert doc.page_count >= 1
    full_text = "\n".join(page.get_text() for page in doc)
    assert "Test Book" in full_text
    assert "Test Author" in full_text
    assert "Paragraph one." in full_text
    doc.close()
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_render_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'render_pdf'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/literature_ingest/render_pdf.py`:
```python
"""
render_pdf.py — 구텐베르크 평문 정제 + 단순 PDF 렌더

PyMuPDF(fitz)만 사용 — app/requirements.txt에 이미 있는 의존성이라 신규 설치 불필요.
[로컬 PC에서 실행] — 네트워크·DB 접속 불필요(순수 텍스트/파일 처리).
"""
import re

import fitz  # PyMuPDF

_START_RE = re.compile(
    r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE,
)
_END_RE = re.compile(
    r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE,
)

PAGE_MARGIN = 54  # 포인트 (약 0.75인치)
FONT_SIZE = 11


def strip_gutenberg_boilerplate(raw_text: str) -> str:
    """구텐베르크 라이선스 머리말/꼬리말 제거. 마커 없으면 원문 그대로 반환."""
    start_m = _START_RE.search(raw_text)
    end_m = _END_RE.search(raw_text)
    if not start_m or not end_m or end_m.start() <= start_m.end():
        return raw_text
    return raw_text[start_m.end():end_m.start()].strip()


def _overflow(rect: "fitz.Rect", text: str, fontsize: int) -> float:
    """text를 rect에 넣었을 때 fitz의 overflow 값(>=0이면 다 들어감)을 실제로 그리지 않고 측정."""
    probe = fitz.open()
    page = probe.new_page(width=rect.width + 2 * PAGE_MARGIN, height=rect.height + 2 * PAGE_MARGIN)
    result = page.insert_textbox(rect, text, fontsize=fontsize)
    probe.close()
    return result


def _fit_length(rect: "fitz.Rect", text: str, fontsize: int) -> int:
    """이분 탐색으로 rect 하나에 들어가는 text의 최대 길이(문자 수)를 찾는다.
    단락 하나가 페이지 하나보다 긴 예외 상황에서만 쓰인다 — 그 경우 text는
    이미 문단 하나 크기(최대 수천 자)라 이분 탐색 비용이 낮다."""
    lo, hi = 1, len(text)
    best = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if _overflow(rect, text[:mid], fontsize) >= 0:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def render_book_pdf(title: str, author: str, body_text: str, out_path: str) -> None:
    """title/author/본문 -> 단순 단일 컬럼 PDF 파일 저장.

    문단(빈 줄 구분) 단위로 페이지에 그리디하게 채워 넣는다 — 페이지마다 "지금까지
    쌓인 것 + 다음 문단"이 들어가는지만 확인하므로 검사 대상 텍스트가 항상 페이지
    한 장 분량(수천 자)에 머문다. (남은 전체 텍스트 길이 기준으로 이분 탐색하면
    장편 소설(수백만 자)에서 페이지마다 그 큰 텍스트를 반복 측정해 매우 느려진다 —
    실측: War and Peace 분량(320만 자) 기준 안전장치 없이 하면 120초 넘게 걸렸으나,
    이 방식은 6.9초.)
    """
    doc = fitz.open()
    rect = fitz.paper_rect("a4")
    text_rect = fitz.Rect(
        PAGE_MARGIN, PAGE_MARGIN, rect.width - PAGE_MARGIN, rect.height - PAGE_MARGIN,
    )

    title_page = doc.new_page(width=rect.width, height=rect.height)
    title_page.insert_textbox(
        fitz.Rect(PAGE_MARGIN, rect.height / 3, rect.width - PAGE_MARGIN, rect.height / 2),
        title, fontsize=20, align=fitz.TEXT_ALIGN_CENTER,
    )
    title_page.insert_textbox(
        fitz.Rect(PAGE_MARGIN, rect.height / 2 + 30, rect.width - PAGE_MARGIN, rect.height / 2 + 60),
        author, fontsize=14, align=fitz.TEXT_ALIGN_CENTER,
    )

    paragraphs = [p for p in body_text.split("\n\n") if p.strip()]
    page = doc.new_page(width=rect.width, height=rect.height)
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if _overflow(text_rect, candidate, FONT_SIZE) >= 0:
            current = candidate
            continue

        # candidate가 안 들어감 -> 지금까지 쌓인 내용을 이 페이지에 확정
        if current:
            page.insert_textbox(text_rect, current, fontsize=FONT_SIZE)
        page = doc.new_page(width=rect.width, height=rect.height)

        if _overflow(text_rect, para, FONT_SIZE) >= 0:
            current = para
        else:
            # 문단 하나가 페이지 하나보다 긴 예외 상황 -> 문자 단위 강제 분할
            remaining_para = para
            while _overflow(text_rect, remaining_para, FONT_SIZE) < 0:
                fitted = _fit_length(text_rect, remaining_para, FONT_SIZE)
                page.insert_textbox(text_rect, remaining_para[:fitted], fontsize=FONT_SIZE)
                remaining_para = remaining_para[fitted:]
                page = doc.new_page(width=rect.width, height=rect.height)
            current = remaining_para

    if current:
        page.insert_textbox(text_rect, current, fontsize=FONT_SIZE)

    doc.save(out_path)
    doc.close()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_render_pdf.py -v`
Expected: `4 passed`

- [ ] **Step 5: 커밋**

```bash
git add scripts/literature_ingest/render_pdf.py scripts/literature_ingest/tests/test_render_pdf.py
git commit -m "[Feat] round02a — 구텐베르크 본문 정제 + 단순 PDF 렌더(render_pdf.py, PyMuPDF만 사용)"
```

---

### Task 3: `scripts/literature_ingest/fetch_and_render.py` — 다운로드 + 렌더 오케스트레이션

**Files:**
- Create: `scripts/literature_ingest/fetch_and_render.py`
- Create: `scripts/literature_ingest/tests/test_fetch_and_render.py`

`merged_books.json`을 읽어 각 권을 다운로드하고 Task 2의 함수로 PDF를 만든다. 네트워크 호출 부분은 `httpx.Client`를 인자로 주입해(의존성 주입) 테스트에서 가짜 클라이언트로 대체한다 — 실제 네트워크 없이 오케스트레이션 로직만 검증.

- [ ] **Step 1: 실패하는 테스트 작성**

`scripts/literature_ingest/tests/test_fetch_and_render.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fetch_and_render import gutenberg_txt_url, fetch_and_render_one, FetchResult


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(self, text: str, status_code: int = 200):
        self._text = text
        self._status_code = status_code
        self.requested_urls: list[str] = []

    def get(self, url: str, **kwargs):
        self.requested_urls.append(url)
        return _FakeResponse(self._text, self._status_code)


def test_gutenberg_txt_url_pattern():
    assert gutenberg_txt_url("1342") == "https://www.gutenberg.org/cache/epub/1342/pg1342.txt"


def test_fetch_and_render_one_success(tmp_path):
    book = {
        "book_id": "LIT-GUTENBERG-1342",
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "download_link": "https://www.gutenberg.org/ebooks/1342.epub3.images",
    }
    fake_text = (
        "header\n*** START OF THE PROJECT GUTENBERG EBOOK PRIDE AND PREJUDICE ***\n"
        "It is a truth universally acknowledged, that a single man in possession "
        "of a good fortune must be in want of a wife. However little known the "
        "feelings or views of such a man may be on his first entering a neighbourhood, "
        "this truth is so well fixed in the minds of the surrounding families.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK PRIDE AND PREJUDICE ***\nfooter\n"
    )
    client = _FakeClient(fake_text)

    result = fetch_and_render_one(book, out_dir=str(tmp_path), client=client)

    assert isinstance(result, FetchResult)
    assert result.ok is True
    assert Path(result.pdf_path).exists()
    assert client.requested_urls == ["https://www.gutenberg.org/cache/epub/1342/pg1342.txt"]


def test_fetch_and_render_one_reports_failure_without_raising(tmp_path):
    book = {
        "book_id": "LIT-GUTENBERG-999999",
        "title": "Nonexistent Book",
        "author": "Nobody",
        "download_link": "https://www.gutenberg.org/ebooks/999999.epub3.images",
    }
    client = _FakeClient("Not Found", status_code=404)

    result = fetch_and_render_one(book, out_dir=str(tmp_path), client=client)

    assert result.ok is False
    assert "999999" in (result.error or "") or "HTTP 404" in (result.error or "")
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_fetch_and_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fetch_and_render'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/literature_ingest/fetch_and_render.py`:
```python
"""
fetch_and_render.py — merged_books.json을 읽어 각 권을 다운로드하고 PDF로 렌더

[로컬 PC 또는 네트워크 접속 가능한 서버에서 실행] — Gutenberg에 대한 아웃바운드
HTTP 접속이 필요하다. DB 접속은 불필요(Task 5에서 별도 처리).
"""
import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from render_pdf import strip_gutenberg_boilerplate, render_book_pdf
from merge_csvs import parse_ebook_id

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    book_id: str
    ok: bool
    pdf_path: str = ""
    error: str | None = None


def gutenberg_txt_url(ebook_id: str) -> str:
    return f"https://www.gutenberg.org/cache/epub/{ebook_id}/pg{ebook_id}.txt"


def fetch_and_render_one(book: dict, out_dir: str, client) -> FetchResult:
    """book 1건 다운로드 -> 정제 -> PDF 렌더. 실패해도 예외를 던지지 않고 FetchResult로 보고."""
    book_id = book["book_id"]
    ebook_id = parse_ebook_id(book.get("download_link", ""))
    if not ebook_id:
        return FetchResult(book_id, ok=False, error=f"Gutenberg ebook ID 파싱 실패: {book.get('download_link')}")

    url = gutenberg_txt_url(ebook_id)
    try:
        resp = client.get(url, timeout=30.0)
        resp.raise_for_status()
    except Exception as e:
        return FetchResult(book_id, ok=False, error=f"다운로드 실패({url}): {e}")

    body = strip_gutenberg_boilerplate(resp.text)
    if len(body) < 200:
        return FetchResult(book_id, ok=False, error=f"본문이 너무 짧음({len(body)}자) — 추출 실패 의심")

    out_path = str(Path(out_dir) / f"{book_id}.pdf")
    render_book_pdf(title=book["title"], author=book.get("author", ""), body_text=body, out_path=out_path)
    return FetchResult(book_id, ok=True, pdf_path=out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--merged", default=str(Path(__file__).resolve().parent / "out" / "merged_books.json"))
    parser.add_argument("--out-dir", default=str(Path(__file__).resolve().parent / "out" / "pdfs"))
    parser.add_argument("--limit", type=int, default=None, help="스모크 테스트용 — 앞에서 N권만 처리")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    with open(args.merged, encoding="utf-8") as f:
        books = json.load(f)
    if args.limit:
        books = books[: args.limit]

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    ok_count = 0
    failures: list[FetchResult] = []
    with httpx.Client(follow_redirects=True) as client:
        for i, book in enumerate(books, 1):
            # 이미 렌더된 PDF는 건너뛰기(재시작 가능)
            existing = Path(args.out_dir) / f"{book['book_id']}.pdf"
            if existing.exists():
                log.info(f"[{i}/{len(books)}] {book['title']} — 이미 존재, 스킵")
                ok_count += 1
                continue
            result = fetch_and_render_one(book, args.out_dir, client)
            if result.ok:
                ok_count += 1
                log.info(f"[{i}/{len(books)}] {book['title']} — OK")
            else:
                failures.append(result)
                log.warning(f"[{i}/{len(books)}] {book['title']} — 실패: {result.error}")

    log.info(f"\n완료: {ok_count}/{len(books)} 성공, 실패 {len(failures)}건")
    if failures:
        fail_path = Path(args.out_dir).parent / "fetch_failures.json"
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump([f.__dict__ for f in failures], f, ensure_ascii=False, indent=2)
        log.warning(f"실패 목록: {fail_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_fetch_and_render.py -v`
Expected: `3 passed`

- [ ] **Step 5: 커밋**

```bash
git add scripts/literature_ingest/fetch_and_render.py scripts/literature_ingest/tests/test_fetch_and_render.py
git commit -m "[Feat] round02a — 다운로드+PDF 렌더 오케스트레이션(fetch_and_render.py, httpx 클라이언트 주입으로 테스트)"
```

---

### Task 4: `scripts/literature_ingest/build_manifest.py` — 매니페스트 생성

**Files:**
- Create: `scripts/literature_ingest/build_manifest.py`
- Create: `scripts/literature_ingest/tests/test_build_manifest.py`

`scripts/bulk_ingest/build_manifest.py`가 문서화한 스키마(`{book_id, file, object_key, size, title}`, `object_key`는 평탄 키 `originals/{id}.pdf`)를 그대로 따른다.

- [ ] **Step 1: 실패하는 테스트 작성**

`scripts/literature_ingest/tests/test_build_manifest.py`:
```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_manifest import build_manifest_lines


def test_build_manifest_lines_matches_bulk_ingest_schema(tmp_path):
    pdf1 = tmp_path / "LIT-GUTENBERG-1342.pdf"
    pdf1.write_bytes(b"%PDF-1.4 fake content")
    books = [
        {"book_id": "LIT-GUTENBERG-1342", "title": "Pride and Prejudice"},
        {"book_id": "LIT-GUTENBERG-9999", "title": "Missing PDF Book"},  # PDF 없음 -> 스킵
    ]

    lines, missing = build_manifest_lines(books, pdf_dir=str(tmp_path))

    assert len(lines) == 1
    assert missing == ["LIT-GUTENBERG-9999"]
    entry = json.loads(lines[0])
    assert entry["book_id"] == "LIT-GUTENBERG-1342"
    assert entry["object_key"] == "originals/LIT-GUTENBERG-1342.pdf"
    assert entry["file"] == str(pdf1)
    assert entry["size"] == pdf1.stat().st_size
    assert entry["title"] == "Pride and Prejudice"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_build_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_manifest'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/literature_ingest/build_manifest.py`:
```python
"""
build_manifest.py — merged_books.json + 렌더된 PDF들 -> manifest.jsonl

scripts/bulk_ingest/README.md 가 문서화한 스키마를 그대로 따른다:
  1행 = {book_id, file, object_key, size, title}, object_key는 평탄 키 originals/{id}.pdf.
[로컬 PC에서 실행] — 네트워크·DB 접속 불필요.
"""
import argparse
import json
from pathlib import Path


def build_manifest_lines(books: list[dict], pdf_dir: str) -> tuple[list[str], list[str]]:
    """반환: (manifest.jsonl 각 줄 문자열 리스트, PDF가 없어 스킵된 book_id 리스트)."""
    lines: list[str] = []
    missing: list[str] = []
    for book in books:
        pdf_path = Path(pdf_dir) / f"{book['book_id']}.pdf"
        if not pdf_path.exists():
            missing.append(book["book_id"])
            continue
        entry = {
            "book_id": book["book_id"],
            "file": str(pdf_path),
            "object_key": f"originals/{book['book_id']}.pdf",
            "size": pdf_path.stat().st_size,
            "title": book["title"],
        }
        lines.append(json.dumps(entry, ensure_ascii=False))
    return lines, missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--merged", default=str(Path(__file__).resolve().parent / "out" / "merged_books.json"))
    parser.add_argument("--pdf-dir", default=str(Path(__file__).resolve().parent / "out" / "pdfs"))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "out" / "manifest.jsonl"))
    args = parser.parse_args()

    with open(args.merged, encoding="utf-8") as f:
        books = json.load(f)

    lines, missing = build_manifest_lines(books, args.pdf_dir)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"매니페스트 {len(lines)}건 -> {args.out}")
    if missing:
        print(f"경고: PDF 없어 스킵된 book_id {len(missing)}건: {missing}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_build_manifest.py -v`
Expected: `1 passed`

- [ ] **Step 5: 커밋**

```bash
git add scripts/literature_ingest/build_manifest.py scripts/literature_ingest/tests/test_build_manifest.py
git commit -m "[Feat] round02a — 매니페스트 생성(build_manifest.py, bulk_ingest 스키마 그대로 재사용)"
```

---

### Task 5: `scripts/literature_ingest/upsert_catalog.py` — 카탈로그 upsert (서버 실행)

**Files:**
- Create: `scripts/literature_ingest/upsert_catalog.py`
- Create: `scripts/literature_ingest/tests/test_upsert_catalog.py`

`merged_books.json` 각 행을 `ParsedRecord`로 변환하는 순수 함수는 로컬에서 테스트하고(네트워크·DB 불필요), 실제 `upsert_catalog_records()` 호출은 `app/`이 import 가능하고 DB에 접속되는 환경에서만 동작하므로 **이 Task의 코드 자체는 로컬에서 작성·커밋**하되, **Task 11(실행)은 서버에서** 한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`scripts/literature_ingest/tests/test_upsert_catalog.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from upsert_catalog import book_to_parsed_record


def test_book_to_parsed_record_maps_core_and_extra_fields():
    book = {
        "book_id": "LIT-GUTENBERG-1342",
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "source": "Project Gutenberg",
        "download_format": "EPUB3/TXT/HTML",
        "copyright_status": "Public domain (US)",
        "source_url": "https://www.gutenberg.org/ebooks/1342",
        "download_link": "https://www.gutenberg.org/ebooks/1342.epub3.images",
    }

    rec = book_to_parsed_record(book)

    assert rec.source_id == "LIT-GUTENBERG-1342"
    assert rec.core["title"] == "Pride and Prejudice"
    assert rec.core["personal_author"] == "Jane Austen"
    assert rec.core["url"] == "https://www.gutenberg.org/ebooks/1342"
    assert rec.core["language"] == "eng"
    assert rec.core["doc_type"] == "literature"
    assert rec.core["source_format"] == "PD_TEXT"
    assert rec.source_format == "PD_TEXT"
    assert rec.extra["acquisition"] == {
        "source": "Project Gutenberg",
        "copyright_status": "Public domain (US)",
        "download_format": "EPUB3/TXT/HTML",
        "download_link": "https://www.gutenberg.org/ebooks/1342.epub3.images",
    }
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_upsert_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'upsert_catalog'`

- [ ] **Step 3: 최소 구현 작성**

`scripts/literature_ingest/upsert_catalog.py`:
```python
"""
upsert_catalog.py — merged_books.json -> library_catalog 카탈로그 upsert

book_to_parsed_record()는 순수 함수(네트워크·DB 불필요, 로컬에서 테스트 가능).
main()은 app/의 repositories.catalog_bulk·db.postgres를 import하므로
**app/ 이 PYTHONPATH에 있고 DB에 접속 가능한 환경(서버)에서만 실행 가능**하다.

[서버에서 실행]:
  cd app && PYTHONPATH=. python ../scripts/literature_ingest/upsert_catalog.py
"""
import argparse
import json
import sys
from pathlib import Path


def book_to_parsed_record(book: dict):
    """spec §4.2·§4.4 매핑을 그대로 따른다. app import는 호출 시점까지 지연."""
    from domains.base import ParsedRecord

    return ParsedRecord(
        source_id=book["book_id"],
        core={
            "title": book["title"],
            "personal_author": book.get("author", ""),
            "url": book.get("source_url", ""),
            "language": "eng",
            "doc_type": "literature",
            "source_format": "PD_TEXT",
        },
        extra={
            "acquisition": {
                "source": book.get("source", ""),
                "copyright_status": book.get("copyright_status", ""),
                "download_format": book.get("download_format", ""),
                "download_link": book.get("download_link", ""),
            }
        },
        source_format="PD_TEXT",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--merged", default=str(Path(__file__).resolve().parent / "out" / "merged_books.json"))
    args = parser.parse_args()

    try:
        from db.postgres import SyncSessionLocal
        from repositories.catalog_bulk import upsert_catalog_records
    except ImportError as e:
        sys.exit(
            "app/ 모듈을 import할 수 없습니다 — 이 스크립트는 app/ 이 PYTHONPATH에 있고 "
            f"DB 접속이 가능한 서버 환경에서 실행해야 합니다. (원인: {e})"
        )

    with open(args.merged, encoding="utf-8") as f:
        books = json.load(f)

    records = (book_to_parsed_record(b) for b in books)

    db = SyncSessionLocal()
    try:
        result = upsert_catalog_records(db, records)
    finally:
        db.close()

    print(f"카탈로그 upsert 완료: 신규 {result['created']}, 갱신 {result['updated']} / 총 {result['total']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `cd scripts/literature_ingest && python -m pytest tests/test_upsert_catalog.py -v`
Expected: `1 passed`

- [ ] **Step 5: 커밋**

```bash
git add scripts/literature_ingest/upsert_catalog.py scripts/literature_ingest/tests/test_upsert_catalog.py
git commit -m "[Feat] round02a — 카탈로그 upsert 스크립트(upsert_catalog.py, ParsedRecord 매핑은 로컬 테스트·실행은 서버 전용)"
```

---

### Task 6: `scripts/literature_ingest/README.md` — 실행 절차 문서화

**Files:**
- Create: `scripts/literature_ingest/README.md`

`scripts/bulk_ingest/README.md`와 동일한 관례([로컬 PC]/[서버] 구분, 단계별 명령)로 이 도구의 전체 실행 절차를 문서화한다.

- [ ] **Step 1: 작성**

```markdown
# 문학 작품 자동 적재 도구 (literature_ingest)

공공영역 문학 작품 CSV(제목·저자·구텐베르크 링크)를 다운로드·PDF 변환해
`scripts/bulk_ingest/`의 기존 대량반입 파이프라인에 태우는 도구.
설계: `docs/superpowers/specs/2026-09-09-round02a-literature-ingest-design.md`

## 전체 흐름

```
[로컬 PC]
  1) merge_csvs.py          두 CSV 병합·정제 -> out/merged_books.json (215권)
  2) fetch_and_render.py    구텐베르크 다운로드 + PDF 렌더 -> out/pdfs/{book_id}.pdf
  3) build_manifest.py      -> out/manifest.jsonl (scripts/bulk_ingest 스키마)
  4) upload_from_manifest.py(bulk_ingest 재사용)  PDF -> MinIO originals/{id}.pdf
[서버]
  5) upsert_catalog.py      merged_books.json -> library_catalog (doc_type=literature)
  6) 매니페스트를 MinIO manifests/round02a/ 에 업로드(mc cp)
  7) POST /api/admin/ingest-jobs (manifest_key 지정, params: doc_type=literature, skip_cover=true)
  8) POST /api/admin/ingest-jobs/{id}/start
  9) /admin/jobs 대시보드로 모니터링
```

## 1) CSV 병합

```bash
cd scripts/literature_ingest
python merge_csvs.py
```
출력: `out/merged_books.json` (215권). 콘솔에 "원본 N행 -> 최종 215권" 출력 확인.

## 2) 다운로드 + PDF 렌더

```bash
# 스모크 테스트(3권만)
python fetch_and_render.py --limit 3

# 전체 215권 (중단되면 같은 명령 재실행 — 이미 렌더된 PDF는 건너뜀)
python fetch_and_render.py
```
실패한 권은 `out/fetch_failures.json`에 기록됨 — 실행 후 반드시 확인.

## 3) 매니페스트 생성

```bash
python build_manifest.py
```
출력: `out/manifest.jsonl`. PDF가 없어 스킵된 book_id가 있으면 콘솔에 경고 출력 — 2)의 실패 목록과 대조.

## 4) MinIO 업로드 (bulk_ingest 도구 재사용)

```bash
cd ../bulk_ingest
python upload_from_manifest.py \
  --manifest ../literature_ingest/out/manifest.jsonl \
  --endpoint <서버IP>:21000 \
  --access-key <MINIO_ACCESS_KEY> --secret-key <MINIO_SECRET_KEY> \
  --bucket nl-lib-bucket --workers 16
```

## 5) 카탈로그 upsert (서버에서)

```bash
# 서버에서, app/ 이 있는 경로 기준
cd app && PYTHONPATH=. python ../scripts/literature_ingest/upsert_catalog.py --merged ../scripts/literature_ingest/out/merged_books.json
```

## 6~8) 매니페스트 업로드 + 잡 생성/시작

```bash
mc cp out/manifest.jsonl local/nl-lib-bucket/manifests/round02a/manifest.jsonl

curl -X POST http://<서버IP>/api/admin/ingest-jobs \
  -H "Content-Type: application/json" \
  -d '{
        "name": "literature-round02a",
        "manifest_key": "manifests/round02a/manifest.jsonl",
        "params": {"doc_type": "literature", "skip_cover": true}
      }'

curl -X POST http://<서버IP>/api/admin/ingest-jobs/<job_id>/start
```

## 9) 모니터링

`/admin/jobs` 대시보드 또는 `GET /api/admin/ingest-jobs/{id}`로 215/215 완료 확인.
```

- [ ] **Step 2: 검증**

Run: `test -f scripts/literature_ingest/README.md && echo EXISTS`
Expected: `EXISTS`

- [ ] **Step 3: 커밋**

```bash
git add scripts/literature_ingest/README.md
git commit -m "[Docs] round02a — literature_ingest 도구 실행 절차 README 추가"
```

---

### Task 7: CSV 병합 실행 + 검증

**이 Task부터는 실제 배치 실행 단계다 — TDD 대상 코드가 아니라 "Run: … Expected: …" 형식으로 진행한다(round01 Task 10~15와 동일 패턴).**

**Files:** 없음(스크립트 실행 산출물만)

- [ ] **Step 1: 병합 실행**

Run: `cd scripts/literature_ingest && python merge_csvs.py`
Expected: `원본 100행 -> 최종 215권 -> .../out/merged_books.json`

- [ ] **Step 2: 개수·정정값 검증**

Run:
```bash
python -c "
import json
books = json.load(open('out/merged_books.json', encoding='utf-8'))
print('총', len(books), '권')
print('The Castle 포함 여부:', any(b['title'] == 'The Castle' for b in books))
by_title = {b['title']: b['book_id'] for b in books}
for t in ['The Star Rover', 'From the Earth to the Moon', 'Martin Eden', 'Carmen', 'Nicholas Nickleby', 'Journey to the Centre of the Earth']:
    print(t, '->', by_title.get(t, 'NOT FOUND'))
ids = [b['book_id'] for b in books]
print('book_id 중복 없음:', len(ids) == len(set(ids)))
"
```
Expected:
```
총 215 권
The Castle 포함 여부: False
The Star Rover -> LIT-GUTENBERG-1162
From the Earth to the Moon -> LIT-GUTENBERG-83
Martin Eden -> LIT-GUTENBERG-1056
Carmen -> LIT-GUTENBERG-2465
Nicholas Nickleby -> LIT-GUTENBERG-967
Journey to the Centre of the Earth -> LIT-GUTENBERG-18857
book_id 중복 없음: True
```

- [ ] **Step 3: 커밋 (산출물은 .gitignore 대상 — out/ 디렉토리 자체를 커밋하지 않음, 검증 완료만 기록)**

`out/`는 로컬 산출물이라 커밋하지 않는다. `.gitignore`에 이미 없다면 추가한다.

Run: `grep -q "^scripts/literature_ingest/out/" .gitignore && echo ALREADY || echo NEED_ADD`

만약 `NEED_ADD`면:
```bash
echo "scripts/literature_ingest/out/" >> .gitignore
git add .gitignore
git commit -m "[Chore] round02a — literature_ingest 산출물 디렉토리 gitignore 추가"
```

---

### Task 8: 다운로드+PDF 렌더 스모크 테스트 (3권)

**Files:** 없음(산출물만)

- [ ] **Step 1: 3권만 스모크 실행**

Run: `python fetch_and_render.py --limit 3`
Expected: 3권 모두 "OK" 로그, `완료: 3/3 성공, 실패 0건`

- [ ] **Step 2: PDF 육안 확인**

Run: `python -c "import fitz; d = fitz.open('out/pdfs/LIT-GUTENBERG-1342.pdf'); print(d.page_count, '페이지'); print(d[1].get_text()[:200])"`
Expected: 페이지 수가 1보다 많고, 두 번째 페이지 텍스트가 실제 소설 본문처럼 보임(라이선스 문구가 아님).

- [ ] **Step 3: 인코딩 문제 확인 (한글 등 비ASCII 포함 여부는 무관 — 전부 영문이므로 깨진 문자(�) 없는지만 확인)**

Run: `python -c "
import fitz
for bid in ['LIT-GUTENBERG-1342']:
    d = fitz.open(f'out/pdfs/{bid}.pdf')
    text = ''.join(p.get_text() for p in d)
    print(bid, '깨진 문자 없음' if '\ufffd' not in text else '깨진 문자 발견!')
"`
Expected: `LIT-GUTENBERG-1342 깨진 문자 없음`

---

### Task 9: 다운로드+PDF 렌더 전체 실행 (215권)

**Files:** 없음(산출물만)

- [ ] **Step 1: 전체 실행**

Run: `python fetch_and_render.py`
Expected: 진행 로그 출력, 마지막 줄 `완료: N/215 성공, 실패 M건`(M은 0이 이상적이나, 네트워크 사정상 일부 실패는 `out/fetch_failures.json`에 기록되고 계속 진행됨).

- [ ] **Step 2: 실패 목록 확인**

Run: `test -f out/fetch_failures.json && python -c "import json; print(json.load(open('out/fetch_failures.json')))" || echo "실패 없음"`
Expected: 실패가 있다면 각 건의 `error` 메시지를 확인 — Gutenberg에 TXT가 없는 책이면 이월 처리(§ 스펙 이월 참고), 일시적 네트워크 오류면 `python fetch_and_render.py` 재실행(이미 성공한 건은 건너뜀).

- [ ] **Step 3: PDF 개수 검증**

Run: `ls out/pdfs/*.pdf | wc -l`
Expected: 215에서 §Step 2의 실패 건수를 뺀 수와 일치.

- [ ] **Step 4: 스팟체크 5~8권 (스펙 §5)**

Run:
```bash
python -c "
import fitz, random, json
books = json.load(open('out/merged_books.json', encoding='utf-8'))
sample = random.sample(books, 6)
for b in sample:
    try:
        d = fitz.open(f\"out/pdfs/{b['book_id']}.pdf\")
        text = ''.join(p.get_text() for p in d)
        print(b['title'], '-', len(text), '자,', d.page_count, '페이지,', '깨진문자' if '\ufffd' in text else 'OK')
    except Exception as e:
        print(b['title'], '- 열기 실패:', e)
"
```
Expected: 6권 모두 "OK"이고 페이지 수·글자 수가 책 분량에 비해 합리적(단편이 아닌 이상 페이지 수 두 자릿수 이상).

---

### Task 10: 매니페스트 생성 + 검증

**Files:** 없음(산출물만)

- [ ] **Step 1: 매니페스트 생성**

Run: `python build_manifest.py`
Expected: `매니페스트 N건 -> .../out/manifest.jsonl` (N은 Task 9에서 실제로 렌더 성공한 PDF 개수와 일치).

- [ ] **Step 2: 검증(bulk_ingest 스타일 — 중복·0바이트 확인)**

Run:
```bash
python -c "
import json
lines = [json.loads(l) for l in open('out/manifest.jsonl', encoding='utf-8') if l.strip()]
print('총', len(lines), '건')
ids = [l['book_id'] for l in lines]
print('book_id 중복 없음:', len(ids) == len(set(ids)))
zero_size = [l['book_id'] for l in lines if l['size'] == 0]
print('0바이트 파일:', zero_size or '없음')
"
```
Expected: `book_id 중복 없음: True`, `0바이트 파일: 없음`

---

### Task 11: MinIO 업로드 + 서버 카탈로그 upsert

**주의: 이 Task부터는 실제 운영 MinIO·PostgreSQL에 쓰기 작업이 발생한다. 진행 전 사용자에게 승인을 구한다.**

**Files:** 없음(운영 작업만)

- [ ] **Step 1: 사용자 승인 요청**

"Task 1~10 완료 — 215권(또는 다운로드 실패분을 제외한 실제 성공분) PDF·매니페스트 준비 완료. MinIO 업로드 + 카탈로그 upsert를 진행해도 될까요?" **승인 전 진행 금지.**

- [ ] **Step 2: 승인 후 MinIO 업로드 (bulk_ingest 도구 재사용)**

Run(실제 서버 접속 정보로 대체):
```bash
cd ../bulk_ingest
python upload_from_manifest.py \
  --manifest ../literature_ingest/out/manifest.jsonl \
  --endpoint <서버IP>:21000 \
  --access-key <MINIO_ACCESS_KEY> --secret-key <MINIO_SECRET_KEY> \
  --bucket nl-lib-bucket --workers 16
```
Expected: 업로드 완료 로그, 실패 0건.

- [ ] **Step 3: 서버에서 카탈로그 upsert**

Run(서버 접속 후):
```bash
cd app && PYTHONPATH=. python ../scripts/literature_ingest/upsert_catalog.py --merged ../scripts/literature_ingest/out/merged_books.json
```
Expected: `카탈로그 upsert 완료: 신규 N, 갱신 0 / 총 N` (N = Task 10의 매니페스트 건수와 일치해야 함 — 최초 실행이므로 갱신 0건이 정상).

- [ ] **Step 4: 카탈로그 반영 확인**

Run(서버 DB에서, 또는 admin API 경유):
```sql
SELECT count(*) FROM library_catalog WHERE cnts_id LIKE 'LIT-GUTENBERG-%' OR cnts_id LIKE 'LIT-STDEBOOKS-%';
SELECT count(*) FROM library_catalog WHERE doc_type = 'literature' AND source_format = 'PD_TEXT';
```
Expected: 두 쿼리 모두 Task 10의 매니페스트 건수와 일치.

---

### Task 12: 잡 생성·시작 + 최종 검증

**Files:** 없음(운영 작업만)

- [ ] **Step 1: 매니페스트를 MinIO에 업로드**

Run: `mc cp out/manifest.jsonl local/nl-lib-bucket/manifests/round02a/manifest.jsonl`
Expected: 업로드 성공.

- [ ] **Step 2: 잡 생성**

Run:
```bash
curl -X POST http://<서버IP>/api/admin/ingest-jobs \
  -H "Content-Type: application/json" \
  -d '{
        "name": "literature-round02a",
        "manifest_key": "manifests/round02a/manifest.jsonl",
        "params": {"doc_type": "literature", "skip_cover": true}
      }'
```
Expected: `{"status": "ready", ...}` 형태 응답(잡 ID 포함).

- [ ] **Step 3: 잡 시작**

Run: `curl -X POST http://<서버IP>/api/admin/ingest-jobs/<job_id>/start`
Expected: 시작 확인 응답.

- [ ] **Step 4: 대시보드 모니터링**

`/admin/jobs`에서 완료될 때까지 확인(수백 권 규모라 상당 시간 소요 예상 — LLM 요약·임베딩이 병목).
Expected: 최종적으로 성공 건수가 Task 10의 매니페스트 건수와 일치, 실패 0건(실패가 있으면 개별 사유 확인 후 `/api/books/{cnts_id}/retry`로 재시도).

- [ ] **Step 5: 검색 데모 스모크 (스펙 §5)**

프론트(또는 `/api/books/search`)에서 최소 2~3권(예: "Pride and Prejudice", "War and Peace") 검색해 제목·저자·요약·(PDF 1페이지 폴백) 표지가 정상 노출되는지 확인.

- [ ] **Step 6: 저작권 상태 집계 (스펙 §5·§7 — 나중에 정리 대비 사전 파악)**

Run(서버 DB에서):
```sql
SELECT extra->'acquisition'->>'copyright_status' AS status, count(*)
FROM library_catalog
WHERE doc_type = 'literature' AND source_format = 'PD_TEXT'
GROUP BY status
ORDER BY count(*) DESC;
```
Expected: 결과를 기록해두고, "Public domain (US)"가 아닌 상태(예: "Jurisdiction-specific", "verify Korean use separately" 등)가 몇 건인지 완료노트에 남긴다.

- [ ] **Step 7: 완료노트 작성**

`docs/roadmap/round02a-완료노트.md`를 `_ROUND_COMPLETE_TEMPLATE.md` 기준으로 작성(한 일·결정·이월 — Kafka The Castle 이월, 표지 백필 이월, 저작권 상태 재확인 필요 건수, round02b 계획만 하고 미착수 등). `docs/roadmap/00_status.md` 갱신. 이후 `dev` 머지 승인 요청 → round-finish 절차는 round01과 동일하게 진행(공유 체크아웃에서, `/round-finish` 스킬 직접 호출 금지, `.claude/skills/round-finish/SKILL.md` 수동 실행).
