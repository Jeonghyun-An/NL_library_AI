"""
extractor.py — 텍스트 추출 (2티어 라우팅 파이프라인)

[1티어] OpenDataLoader v2  — 한컴·듀얼랩 하이브리드 엔진 (마크다운 + 표 + 문서 구조 보존)
[2티어] VLM(Qwen2.5-VL)   — [그림] 플레이스홀더 또는 글자 수 부족 페이지만 선별 보완
                            (fitz는 페이지 이미지 렌더링 용도로만 사용)

비교 테스트용 standalone 함수:
- extract_text_fitz_all()         : 모든 페이지 fitz로만
- extract_text_vlm_all()          : 모든 페이지 VLM으로만
- extract_text_opendataloader()   : 모든 페이지 OpenDataLoader로만
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
        from collections import Counter
        method_counts = Counter(p.method for p in self.pages)
        return {
            "total": self.total_pages,
            **method_counts,
            "errors": len(self.errors),
        }


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
    """2티어 라우팅 파이프라인.

    1티어: OpenDataLoader로 전체 PDF 마크다운 추출
    2티어: 페이지 텍스트에 `[그림]`이 있거나 글자수 < MIN_CHARS_PER_PAGE인 경우만 VLM 보완
    """
    result = ExtractionResult(book_id=book_id, total_pages=0)

    # ── 1티어: OpenDataLoader 전체 추출 ──────────────────
    odl_result = await extract_text_opendataloader(
        file_path, book_id, file_bytes=file_bytes
    )
    odl_pages_by_num: dict[int, PageResult] = {p.page_num: p for p in odl_result.pages}
    if odl_result.errors:
        result.errors.extend(odl_result.errors)

    # ── 2티어 라우팅을 위해 fitz로 페이지 이미지 렌더링 준비 ─
    try:
        if file_bytes:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        else:
            doc = fitz.open(str(file_path))
    except Exception as e:
        result.errors.append(f"파일 열기 실패: {e}")
        # OpenDataLoader 결과만이라도 반환
        result.pages = list(odl_result.pages)
        result.total_pages = len(result.pages)
        return result

    result.total_pages = len(doc)
    log.info(
        f"[{book_id}] {result.total_pages}p — 1티어 ODL 완료 "
        f"({len(odl_result.pages)}p 추출), 2티어 라우팅 시작"
    )

    async with httpx.AsyncClient() as client:
        for page in doc:
            page_num = page.number
            odl_page = odl_pages_by_num.get(page_num)

            # 라우팅 판단
            if odl_page is None:
                trigger = "ODL 누락"
            elif "[그림]" in odl_page.text:
                trigger = "[그림] 검출"
            elif len(odl_page.text) < MIN_CHARS_PER_PAGE:
                trigger = f"글자수 부족({len(odl_page.text)}자)"
            else:
                # 1티어 결과 채택 — VLM 호출 안 함
                result.pages.append(odl_page)
                continue

            # 2티어: VLM 보완
            try:
                log.info(f"[{book_id}] p.{page_num} → VLM 보완 ({trigger})")
                vlm_page = await _extract_with_vlm(page, client)
                result.pages.append(vlm_page)
            except Exception as e:
                log.error(f"[{book_id}] p.{page_num} VLM 실패: {e}")
                result.errors.append(f"p.{page_num} VLM: {e}")
                if odl_page:  # VLM 실패 시 ODL 결과라도 살리기
                    result.pages.append(odl_page)

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

    log.info(f"[{book_id}] 추출 완료 — {result.stats}, page_map={len(page_map)}")
    return result


def extract_text_fitz_all(
    file_path: str | Path | None,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    max_pages: int | None = None,
) -> ExtractionResult:
    """모든 페이지를 fitz로만 추출 (비교 테스트용, 동기)"""
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
    pages_to_process = list(doc)[:max_pages] if max_pages else list(doc)

    for page in pages_to_process:
        try:
            raw = page.get_text("text").strip()
            result.pages.append(PageResult(
                page_num=page.number,
                text=_clean_text(raw) if raw else "",
                method="fitz",
                confidence=1.0 if len(raw) >= MIN_CHARS_PER_PAGE else 0.3,
            ))
        except Exception as e:
            log.error(f"[{book_id}] fitz p.{page.number} 실패: {e}")
            result.errors.append(f"p.{page.number}: {e}")

    doc.close()
    log.info(f"[{book_id}] fitz 전체 추출 완료 — {result.stats}")
    return result


async def extract_text_vlm_all(
    file_path: str | Path | None,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    max_pages: int | None = None,
) -> ExtractionResult:
    """모든 페이지를 VLM으로 추출 (비교 테스트용)"""
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
    pages_to_process = list(doc)[:max_pages] if max_pages else list(doc)

    async with httpx.AsyncClient() as client:
        for page in pages_to_process:
            try:
                page_result = await _extract_with_vlm(page, client)
                result.pages.append(page_result)
            except Exception as e:
                log.error(f"[{book_id}] VLM p.{page.number} 실패: {e}")
                result.errors.append(f"p.{page.number}: {e}")

    doc.close()
    log.info(f"[{book_id}] VLM 전체 추출 완료 — {result.stats}")
    return result


async def extract_text_opendataloader(
    file_path: str | Path | None,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    max_pages: int | None = None,
) -> ExtractionResult:
    """OpenDataLoader PDF를 이용한 추출 (3단계, 비교 테스트용)

    설치: pip install open-data-loader
    """
    import asyncio
    import os
    import tempfile

    result = ExtractionResult(book_id=book_id, total_pages=0)

    try:
        from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader  # pip install langchain-opendataloader-pdf (Java 11+ 필요)
    except ImportError:
        result.errors.append(
            "langchain-opendataloader-pdf 패키지 미설치 — pip install langchain-opendataloader-pdf"
        )
        return result

    tmp_path = None
    try:
        if file_bytes:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            load_path = tmp_path
        else:
            load_path = str(file_path)

        def _load_sync() -> list:
            loader = OpenDataLoaderPDFLoader(
                file_path=load_path,
                format="markdown",        # 표 → markdown table, 그림 → ![]() 참조
                image_output="embedded",  # 이미지 base64 인라인 (없으면 그림 흔적조차 안 남음)
                image_format="jpeg",      # base64 크기 절감
                table_method="cluster",   # 무경계/복잡 표까지 검출
                split_pages=True,         # 페이지별 Document
                keep_line_breaks=False,
            )
            return loader.load()

        loop = asyncio.get_event_loop()
        documents = await loop.run_in_executor(None, _load_sync)

        if max_pages:
            documents = documents[:max_pages]

        import re
        # markdown 이미지 (base64 embedded 또는 외부 경로) → [그림] 마커로 치환
        img_pattern = re.compile(r'!\[[^\]]*\]\([^)]+\)')

        result.total_pages = len(documents)
        for i, doc in enumerate(documents):
            page_num = doc.metadata.get("page", i + 1) - 1  # OpenDataLoader는 1-based → 0-based
            raw = doc.page_content
            img_count = len(img_pattern.findall(raw))
            stripped = img_pattern.sub('[그림]', raw)
            text = _clean_text(stripped)
            if img_count:
                log.info(f"[{book_id}] p.{page_num} 그림 {img_count}개 검출")
            result.pages.append(PageResult(
                page_num=page_num,
                text=text,
                method="opendataloader",
                confidence=0.95,
            ))

    except Exception as e:
        log.error(f"[{book_id}] OpenDataLoader 추출 실패: {e}")
        result.errors.append(f"OpenDataLoader 추출 실패: {e}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    log.info(f"[{book_id}] OpenDataLoader 추출 완료 — {result.stats}")
    return result