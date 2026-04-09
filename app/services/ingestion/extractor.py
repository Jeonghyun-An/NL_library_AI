"""
extractor.py — 텍스트 추출 (3단계 fallback)

1) fitz(PyMuPDF): 디지털 PDF 텍스트 추출
2) PaddleOCR: 스캔본 OCR
3) VLM(Gemma): PaddleOCR 저신뢰 페이지 재처리
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

# ── 설정 ────────────────────────────────────────────────
MIN_CHARS_PER_PAGE = 50          # 이 미만이면 스캔본으로 판정
PADDLE_CONFIDENCE_THRESHOLD = 0.7  # OCR 신뢰도 임계값


@dataclass
class PageResult:
    page_num: int
    text: str
    method: str          # "fitz" | "paddle" | "vlm"
    confidence: float    # 0.0 ~ 1.0
    is_table: bool = False
    is_figure: bool = False


@dataclass
class ExtractionResult:
    book_id: str
    total_pages: int
    pages: list[PageResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)

    @property
    def stats(self) -> dict:
        methods = [p.method for p in self.pages]
        return {
            "total": self.total_pages,
            "fitz": methods.count("fitz"),
            "paddle": methods.count("paddle"),
            "vlm": methods.count("vlm"),
            "errors": len(self.errors),
        }


# ── 1단계: fitz 텍스트 추출 ──────────────────────────────
def _extract_with_fitz(page: fitz.Page) -> PageResult | None:
    text = page.get_text("text").strip()
    if len(text) >= MIN_CHARS_PER_PAGE:
        return PageResult(
            page_num=page.number,
            text=text,
            method="fitz",
            confidence=1.0,
        )
    return None


# ── 2단계: PaddleOCR ─────────────────────────────────────
async def _extract_with_paddle(
    page: fitz.Page,
    client: httpx.AsyncClient,
) -> PageResult:
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")

    resp = await client.post(
        f"{cfg.PADDLEOCR_URL}/ocr",
        files={"file": ("page.png", img_bytes, "image/png")},
        timeout=60.0,
    )
    resp.raise_for_status()
    result = resp.json()

    texts = []
    confidences = []
    for item in result.get("results", []):
        texts.append(item.get("text", ""))
        confidences.append(item.get("confidence", 0.0))

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return PageResult(
        page_num=page.number,
        text="\n".join(texts),
        method="paddle",
        confidence=avg_conf,
    )


# ── 3단계: VLM(Gemma) 재처리 ────────────────────────────
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
        confidence=0.9,  # VLM은 신뢰도 고정
    )


# ── 메인 추출 함수 ───────────────────────────────────────
async def extract_text(
    file_path: str | Path,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
) -> ExtractionResult:
    """
    PDF/이미지 파일에서 텍스트 추출

    Args:
        file_path: 파일 경로 (또는 MinIO에서 다운로드한 경우 파일명)
        book_id: 도서 식별자
        file_bytes: 바이트로 직접 전달 시
    """
    result = ExtractionResult(book_id=book_id, total_pages=0)

    # PDF 열기
    try:
        if file_bytes:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        else:
            doc = fitz.open(str(file_path))
    except Exception as e:
        # 이미지 파일인 경우 단일 페이지 PDF로 변환
        try:
            if file_bytes:
                img = fitz.open(stream=file_bytes, filetype="png")
            else:
                img = fitz.open(str(file_path))
            doc = fitz.open()
            doc.insert_pdf(img)
        except Exception as e2:
            result.errors.append(f"파일 열기 실패: {e2}")
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

                # 2단계: PaddleOCR
                page_result = await _extract_with_paddle(page, client)

                # 신뢰도 체크 → 저신뢰 시 3단계 VLM
                if page_result.confidence < PADDLE_CONFIDENCE_THRESHOLD:
                    log.info(
                        f"[{book_id}] p.{page.number} PaddleOCR 신뢰도 "
                        f"{page_result.confidence:.2f} < {PADDLE_CONFIDENCE_THRESHOLD} → VLM 재처리"
                    )
                    try:
                        page_result = await _extract_with_vlm(page, client)
                    except Exception as vlm_err:
                        log.warning(f"[{book_id}] p.{page.number} VLM 실패, PaddleOCR 결과 사용: {vlm_err}")
                        # PaddleOCR 결과라도 사용

                result.pages.append(page_result)

            except Exception as e:
                log.error(f"[{book_id}] p.{page.number} 추출 실패: {e}")
                result.errors.append(f"p.{page.number}: {e}")

    doc.close()
    log.info(f"[{book_id}] 추출 완료 — {result.stats}")
    return result