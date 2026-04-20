"""
extractor.py — 텍스트 추출 (2단계 fallback)

1) fitz(PyMuPDF): 디지털 PDF 텍스트 추출
2) VLM(Gemma 4): 스캔본 OCR (멀티모달)
"""
import io
import logging
from pathlib import Path
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import httpx

from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

MIN_CHARS_PER_PAGE = 50


def _clean_text(text: str) -> str:
    """추출된 텍스트 정제"""
    import re
    # 연속 줄바꿈을 하나로
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 줄바꿈 + 공백 정리 (단락 구분은 유지)
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != '':
            lines.append('')
    text = '\n'.join(lines)
    # 연속 공백 제거
    text = re.sub(r' {2,}', ' ', text)
    # 페이지 번호 패턴 제거 (- 1 -, 1/23, Page 1 등)
    text = re.sub(r'\n-\s*\d+\s*-\s*\n', '\n', text)
    text = re.sub(r'\n\d+\s*/\s*\d+\s*\n', '\n', text)
    text = re.sub(r'\nPage\s+\d+\s*\n', '\n', text, flags=re.IGNORECASE)
    return text.strip()


@dataclass
class PageResult:
    page_num: int
    text: str
    method: str          # "fitz" | "vlm"
    confidence: float


@dataclass
class ExtractionResult:
    book_id: str
    total_pages: int
    pages: list[PageResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    page_map: dict[int, int] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)

    @property
    def stats(self) -> dict:
        methods = [p.method for p in self.pages]
        return {
            "total": self.total_pages,
            "fitz": methods.count("fitz"),
            "vlm": methods.count("vlm"),
            "errors": len(self.errors),
        }


def _extract_with_fitz(page: fitz.Page) -> PageResult | None:
    text = page.get_text("text").strip()
    if len(text) >= MIN_CHARS_PER_PAGE:
        return PageResult(
            page_num=page.number,
            text=_clean_text(text),
            method="fitz",
            confidence=1.0,
        )
    return None


async def _extract_with_vlm(
    page: fitz.Page,
    client: httpx.AsyncClient,
) -> PageResult:
    import base64

    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")
    img_b64 = base64.b64encode(img_bytes).decode()

    payload = {
        "model": cfg.VLLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "이 페이지의 모든 텍스트를 정확히 추출해주세요. "
                            "표가 있으면 마크다운 표로 변환하고, "
                            "그림이 있으면 [그림: 설명] 형태로 표기하세요. "
                            "원문의 순서와 구조를 최대한 유지하세요."
                        ),
                    },
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.1,
    }

    resp = await client.post(
        f"{cfg.VLLM_BASE_URL}/chat/completions",
        json=payload,
        timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()

    return PageResult(
        page_num=page.number,
        text=text,
        method="vlm",
        confidence=0.9,
    )


async def extract_text(
    file_path: str | Path,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
) -> ExtractionResult:
    result = ExtractionResult(book_id=book_id, total_pages=0)

    try:
        if file_bytes:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        else:
            doc = fitz.open(str(file_path))
    except Exception as e:
        result.errors.append(f"파일 열기 실패: {e}")
        return result

    result.total_pages = len(doc)
    log.info(f"[{book_id}] {result.total_pages}페이지 처리 시작")

    async with httpx.AsyncClient() as client:
        for page in doc:
            try:
                # 1단계: fitz
                page_result = _extract_with_fitz(page)
                if page_result:
                    result.pages.append(page_result)
                    continue

                # 2단계: VLM (Gemma 4 멀티모달)
                log.info(f"[{book_id}] p.{page.number} fitz 실패 → VLM OCR")
                page_result = await _extract_with_vlm(page, client)
                result.pages.append(page_result)

            except Exception as e:
                log.error(f"[{book_id}] p.{page.number} 추출 실패: {e}")
                result.errors.append(f"p.{page.number}: {e}")

    doc.close()
    # 페이지 번호 매핑 생성 (full_text와 동일하게 빈 페이지 제외)
    cursor = 0
    page_map = {}

    for p in result.pages:
        if not p.text:
            continue
        for i in range(len(p.text)):
            page_map[cursor + i] = p.page_num
        cursor += len(p.text) + 2  # "\n\n"

    result.page_map = page_map

    log.info(f"[{book_id}] page_map 생성 완료 (len={len(page_map)})")
    log.info(f"[{book_id}] 추출 완료 — {result.stats}")
    return result