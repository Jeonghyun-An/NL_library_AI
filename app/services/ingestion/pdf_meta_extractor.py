"""
pdf_meta_extractor.py — PDF 1-2페이지에서 LLM으로 메타데이터 자동 추출

xlsx 메타데이터 없이 업로드된 PDF(논문, 보고서 등)에 대해
OpenDataLoader로 첫 1-2페이지를 추출한 뒤 LLM으로 서지 정보를 구조화한다.

반환 dict 키는 Book 모델 컬럼명과 일치:
  title, personal_author, corporate_author, publisher,
  pub_date, abstract, keyword, language, url, genre
"""
import json
import logging
import re

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)

_MAX_CHARS = get_settings().PDF_META_MAX_CHARS  # LLM에 보낼 최대 텍스트 길이

_SYSTEM = """\
You are a bibliographic metadata extraction expert.
Extract structured metadata from the first 1-2 pages of a document.
Return ONLY valid JSON — no markdown fences, no explanation.

Required fields (use empty string "" if unknown):
{
  "title": "full document title",
  "personal_author": "comma-separated author names (Last, First or natural order)",
  "corporate_author": "organization/institution name (only if no personal authors)",
  "publisher": "journal name, conference name, or publisher",
  "pub_date": "4-digit publication year only (e.g. 2024)",
  "abstract": "abstract or executive summary, max 800 chars",
  "keyword": "comma-separated keywords or index terms",
  "language": "ISO 639-1 code: ko / en / ja / zh / fr / de / etc.",
  "url": "DOI URL (https://doi.org/...) or canonical URL if visible",
  "genre": "paper | thesis | report | manual | book | other"
}
"""


async def extract_pdf_metadata(file_path: str) -> dict:
    """
    PDF 파일의 1-2페이지를 OpenDataLoader로 추출 후 LLM으로 메타데이터 dict 반환.
    실패 시 빈 dict 반환 (호출부에서 title fallback 처리).
    """
    cfg = get_settings()

    # ── 1. OpenDataLoader로 페이지 1-2 텍스트 추출 ──────────────
    from services.ingestion.extractor import extract_text_opendataloader
    odl = await extract_text_opendataloader(file_path, book_id="__meta__", max_pages=2)
    raw_text = "\n\n".join(p.text for p in odl.pages if p.text).strip()

    if not raw_text:
        log.warning(f"[pdf_meta] 페이지 텍스트 비어있음: {file_path}")
        return {}

    text_for_llm = raw_text[:_MAX_CHARS]

    # ── 2. LLM 호출 ─────────────────────────────────────────────
    from services.llm_client import chat
    try:
        raw_output = await chat(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"Document text (first 1-2 pages):\n\n{text_for_llm}"},
            ],
            params={"max_tokens": cfg.PDF_META_MAX_TOKENS, "temperature": cfg.PDF_META_TEMPERATURE},
            timeout=cfg.PDF_META_TIMEOUT,
        )
    except Exception as e:
        log.warning(f"[pdf_meta] LLM 호출 실패: {e}")
        return {}

    # ── 3. JSON 파싱 ─────────────────────────────────────────────
    # 모델이 ```json ... ``` 감싸서 반환하는 경우 제거
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw_output).strip()
    try:
        meta = json.loads(cleaned)
    except json.JSONDecodeError:
        # 부분 매칭: 첫 번째 { ... } 블록 추출 시도
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                meta = json.loads(m.group())
            except json.JSONDecodeError:
                log.warning(f"[pdf_meta] JSON 파싱 실패. raw={raw_output[:300]}")
                return {}
        else:
            log.warning(f"[pdf_meta] JSON 블록 없음. raw={raw_output[:300]}")
            return {}

    if not isinstance(meta, dict):
        return {}

    # ── 4. 필드 정제 ─────────────────────────────────────────────
    def _str(key: str) -> str:
        v = meta.get(key, "")
        return str(v).strip() if v else ""

    return {
        "title":            _str("title"),
        "personal_author":  _str("personal_author"),
        "corporate_author": _str("corporate_author"),
        "publisher":        _str("publisher"),
        "pub_date":         _str("pub_date")[:4],   # 연도 4자리만
        "abstract":         _str("abstract")[:1000],
        "keyword":          _str("keyword"),
        "language":         _str("language")[:5],
        "url":              _str("url"),
        "genre":            _str("genre") or "other",
    }
