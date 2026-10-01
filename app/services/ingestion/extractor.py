"""
extractor.py — 텍스트 추출 (2티어 라우팅 파이프라인)

[1티어] OpenDataLoader v2  — 한컴·듀얼랩 하이브리드 엔진 (마크다운+json 동시 산출,
                            표·문서 구조 보존). extract_text_opendataloader()가
                            실제 운영 파이프라인의 1티어 진입점이다(아래 목록의
                            비교용 standalone 함수와는 별개).
[2티어] VLM(Qwen3-VL)      — 다음 중 하나라도 해당하면 페이지 단위로 보완:
                            (a) 표 셀 충전율이 낮음(<0.30) — 빈 표 격자가 글자 수만 채움
                            (b) 글자 수는 기준(EXTRACT_MIN_CHARS_PER_PAGE) 이상이어도
                                fitz 추정치의 절반 이하 — 폰트 CMap 손상으로 ODL이
                                글자를 유실했을 가능성
                            (c) 글자 수가 기준 미만 **이면서 fitz 추정치도 함께 미만**
                                — fitz까지 짧으면 표지·구분 페이지 등 원래 짧은
                                페이지이므로 VLM 없이 ODL 결과를 그대로 채택한다.
                                다만 3쪽 이상 문서에서, ODL 본문이 짧고 문서 전체에 되풀이되는
                                줄(머리말·꼬리말·스탬프)을 뺀 fitz 길이도 짧은 쪽이 절반을 넘으면
                                스캔본으로 보고 짧은 쪽을 모두 OCR 한다(page_routing.py)
                            (fitz는 페이지 이미지 렌더링뿐 아니라 (b)(c)의 교차검증에도 쓰인다)

비교 테스트용 standalone 함수(운영 경로 아님):
- extract_text_fitz_all()         : 모든 페이지 fitz로만
- extract_text_vlm_all()          : 모든 페이지 VLM으로만
"""
import asyncio
import io
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import httpx

from core.config import get_settings
from services.ingestion import page_routing

log = logging.getLogger(__name__)
cfg = get_settings()

MIN_CHARS_PER_PAGE = cfg.EXTRACT_MIN_CHARS_PER_PAGE


def _clean_text(text: str, strip_lines: set[str] | None = None) -> str:
    """추출된 텍스트 정제.

    strip_lines: ODL json에서 type이 header/footer인 요소의 실제 문자열(있으면) —
    정규식 추측 대신 구조적으로 확정된 머리말/쪽번호를 정확히 제거한다. 정규식은
    JSON 신호가 없는 경우(VLM 출력 등)를 위한 최후 수단으로 계속 둔다.
    """
    import re
    # 빈 표 격자의 <br> 수천 개가 섹션 본문을 채우지 않게 <br> 하나로 줄인다(줄바꿈으로 바꾸면 표 행이 쪼개진다).
    text = page_routing.collapse_br_runs(text)
    if strip_lines:
        text = "\n".join(
            line for line in text.split("\n") if line.strip() not in strip_lines
        )
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
    # 페이지 번호 패턴 제거 (- 1 -, 1/23, Page 1 등) — JSON 신호가 없을 때의 최후 수단
    text = re.sub(r'\n-\s*\d+\s*-\s*\n', '\n', text)
    text = re.sub(r'\n\d+\s*/\s*\d+\s*\n', '\n', text)
    text = re.sub(r'\nPage\s+\d+\s*\n', '\n', text, flags=re.IGNORECASE)
    return text.strip()


def _collect_content_strings(element: dict) -> list[str]:
    """ODL json 요소(및 표의 rows/cells, header/footer의 중첩 kids 등)에서
    실제 텍스트(content)를 재귀적으로 모두 모은다."""
    out = []
    content = element.get("content")
    if isinstance(content, str) and content.strip():
        out.append(content.strip())
    for kid in element.get("kids", []):
        out.extend(_collect_content_strings(kid))
    for row in element.get("rows", []):
        for cell in row.get("cells", []):
            out.extend(_collect_content_strings(cell))
    return out


def _strip_figure_markers(text: str) -> str:
    """본문 채택 페이지에 남은 단독 [그림] 마커(워터마크·삽화 흔적) 정리.

    그림 자체는 result.figures(base64)로 별도 저장되므로 인라인 마커는 노이즈일 뿐.
    다운스트림(요약·청킹·검색)에서 [그림] 인라인 마커를 신호로 쓰지 않는다.
    """
    import re
    text = text.replace("[그림]", "")
    # `[그림]<br><br>[그림]` 반복 격자는 마커를 지우면 <br> 긴 연속이 된다 — 한 번 더 줄인다.
    text = page_routing.collapse_br_runs(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _adopt_odl(odl_page: "PageResult") -> "PageResult":
    """ODL 결과를 그 쪽의 최종 결과로 쓴다 — 남은 [그림] 마커를 지우고 <br> 연속을 다시 줄인다.

    본문 채택·원래 짧은 쪽뿐 아니라 OCR 결과가 없는 쪽(VLM 쪽수 상한·요청 실패·퇴화 출력·렌더링 실패·
    데드라인)도 이 길로 채택한다.
    """
    odl_page.text = _strip_figure_markers(odl_page.text)
    return odl_page


@dataclass
class PageResult:
    page_num: int
    text: str
    method: str          # "fitz" | "vlm"
    confidence: float
    truncated: bool = False  # VLM 응답이 max_tokens 로 끝나 되풀이 꼬리를 걷어 냈다


@dataclass
class FigureData:
    page_num: int
    img_idx: int        # 페이지 내 순서 (0-based)
    img_bytes: bytes    # JPEG 바이너리
    before_context: str # 이미지 앞 300자 (제목·레이블 등)
    after_context: str  # 이미지 뒤 300자 (각주·출처 등)


@dataclass
class ExtractionResult:
    book_id: str
    total_pages: int
    pages: list[PageResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    page_map: dict[int, int] = field(default_factory=dict)
    figures: list[FigureData] = field(default_factory=list)
    vlm_capped: bool = False  # VLM_MAX_PAGES_PER_DOC 상한에 걸려 일부 페이지가 누락됐는지
    # 페이지별 표 셀 충전율(있는 페이지만) — 마크다운 평탄화로 사라지는 "셀 비었음"
    # 정보를 JSON 산출물에서 복원해 라우팅 판정에 쓴다. 0에 가까울수록 빈 격자.
    table_fill_ratios: dict[int, float] = field(default_factory=dict)
    vlm_truncated: int = 0      # finish_reason=length 로 끝난 OCR 쪽 수(꼬리를 걷어 냈거나 퇴화로 버림)
    deadline_hit: bool = False  # 추출 데드라인에 걸려 OCR 을 끝내지 못한 쪽을 ODL 결과로 채택했다
    # VLM 요청 실패 수(연결·타임아웃·HTTP 오류 등 다시 하면 달라질 수 있는 것) — 퇴화 출력·렌더링 실패는 세지 않는다
    ocr_errors: int = 0
    render_errors: int = 0      # 쪽 이미지 렌더링 실패 수(fitz get_pixmap 예외 — 다시 해도 같다)
    # ODL 본문이 짧은데 '원래 짧은 쪽'으로 ODL 결과를 채택한 쪽 수 — 강제 OCR(force_ocr_short_pages)이
    # 판정을 바꾸는 쪽은 이것뿐이라, 0 이면 섹션 0개 재추출을 해도 결과가 같다
    short_kept: int = 0
    # 원본 변환이 실패해 대신 쓴 것 — "resaved"(fitz 재저장본이 변환됐다)·"fitz"(둘 다 실패해 fitz 텍스트를
    # 썼다). None 이면 원본이 변환됐거나 폴백할 것이 없었다(fitz 로도 열리지 않는 파일)
    odl_fallback: str | None = None
    odl_seconds: float = 0.0    # ODL 변환 시도 전부의 벽시계 시간(초)

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


# ── VLM 프롬프트 ────────────────────────────────────────────
_VLM_PROMPT_DIAGRAM = """\
이 페이지에는 다이어그램, 인포그래픽, 또는 그림이 포함되어 있습니다.
내부 텍스트와 구조를 최대한 추출하세요. "[그림: 설명]" 한 줄로 대체하지 마세요.

추출 규칙:
1. 모든 텍스트 라벨·수치·제목·범례를 빠짐없이 추출하세요.
2. 다이어그램 유형에 맞는 구조로 표현하세요:
   - 순서도·프로세스 흐름 → 단계별 번호 리스트 또는 [A → B → C]
   - 인과관계도·루프 → [원인 → 결과] 관계 목록
   - 조직도·계층도 → 들여쓰기 계층 구조
   - 표·매트릭스 → 마크다운 표(|---|)
3. 화살표·연결선은 → 기호로 관계를 명시하세요.
4. 텍스트가 전혀 없는 순수 사진·삽화만 [그림: 한 줄 설명]으로 표기하세요.
5. 이미지에 없는 내용은 절대 추가하지 마세요.
6. 수치는 보이는 값 그대로만 적으세요. 원문에 없는 열(변화량·증감·차이·합계)을 만들거나
   계산하지 말고, 증감 방향(↑↓)도 원문에 표시된 경우에만 적으세요.
7. 막대·선·원 그래프는 마크다운 표로 변환하지 마세요(값이 엉뚱한 항목에 붙습니다).
   보이는 순서대로 "라벨: 값" 을 한 줄씩 나열하세요. 셀 경계가 그려진 진짜 표만 표로 옮기세요.
8. 수학 공식은 기호를 한 줄에 하나씩 찢어서 옮기지 말고 한 줄로 표현하거나
   "[수식: 역전파 오차 계산식]"처럼 요약하세요. 순서도가 표로 안 옮겨지면(빈 칸투성이) 대신
   "[순서도: A → B → C]"처럼 단계를 화살표로 이은 한 줄로 요약하세요.
마크다운 코드 블록(```)이나 부연 설명 없이 바로 내용만 출력하세요."""

_VLM_PROMPT_OCR = """\
이 페이지의 모든 텍스트를 정확히 추출하세요.

레이아웃 처리 규칙:
- 2단(두 칸) 구성이면: 반드시 왼쪽 단을 위에서 아래로 모두 읽은 뒤, 오른쪽 단을 위에서 아래로 읽으세요. 양쪽 단을 줄 단위로 섞지 마세요.
- 1단(전체 폭) 구성이면: 위에서 아래로 순서대로 읽으세요.
- 단 구분이 불명확하면 텍스트 흐름이 자연스러운 방향으로 읽으세요.

표·수치 규칙 (반드시 지킬 것):
- 표가 있으면 마크다운 표(|---|)로 변환하되, **이미지에 실제로 있는 행·열만** 옮기세요.
- 원문에 없는 열(변화량·증감·차이·합계 등)을 새로 만들지 마세요. 계산하지 마세요.
- 숫자는 보이는 값을 그대로 적으세요. 값을 다른 항목에 옮겨 붙이지 마세요.
- 증감 방향(↑↓, 증가·감소)은 원문에 그렇게 표시된 경우에만 적으세요. 추측하지 마세요.
- 그래프·차트(막대·선·원 그래프)는 **마크다운 표로 변환하지 마세요.** 표로 재구성하면
  값이 잘못된 항목에 배치되어 원문과 다른 데이터가 만들어집니다.
  대신 이미지에 보이는 순서대로 "라벨: 값" 을 한 줄씩 나열하세요.

수식·순서도 규칙:
- 수학 공식·수식은 기호를 한 줄에 하나씩 찢어서 옮기지 마세요. 수식 전체를 하나의 줄(또는
  LaTeX 유사 표기, 예: "δ = f'(net) × (t - o)")로 표현하거나, 표현이 어려우면
  "[수식: 역전파 오차 계산식]"처럼 한 줄로 요약하세요.
- 순서도·플로우차트는 빈 칸투성이 표로 만들지 마세요. "[순서도: 초기화 → 패턴설정 → 오차계산 → 종료판정]"
  처럼 단계를 화살표로 이은 한 줄로 요약하세요.

기타 규칙:
- 그림·사진은 [그림: 한 줄 설명]으로 표기하세요.
- 마크다운 코드 블록(```)이나 부연 설명 없이 내용만 출력하세요.
- 이미지에 없는 내용은 추가하지 마세요."""


def _strip_reasoning(text: str, thinking: bool) -> tuple[str, bool]:
    """추론 블록을 제거하고 실제 답변만 돌려준다. returns (본문, 정상종료)

    Qwen3 계열 chat template 은 프롬프트 끝에 `<think>` 를 미리 붙이므로, 모델 출력은
    여는 태그 없이 "추론… </think> 실제답변" 형태로 온다.
    thinking 을 켠 채 max_tokens 가 부족하면 `</think>` 를 내기도 전에 잘리는데,
    그 잘린 사고과정을 OCR 결과로 쓰면 본문이 오염된다(영문 혼잣말이 그대로 색인됨).
    → 닫는 태그가 없으면 실패로 처리해 호출부가 폴백/재시도하게 한다.
    """
    if "</think>" in text:
        return text.split("</think>")[-1].strip(), True
    if thinking:
        return "", False          # 추론 도중 잘림 — 답변 없음
    return text.strip(), True     # 비추론 모델 (태그 없음이 정상)


class VlmDegenerateOutput(Exception):
    """VLM 이 같은 구절을 되풀이하다 max_tokens 로 끝나, 꼬리를 걷어 내도 쓸 본문이 없다."""


class PageRenderError(Exception):
    """fitz 가 쪽 이미지를 만들지 못했다(get_pixmap 예외 — 예: FzErrorLimit). 다시 해도 같은 결정적 실패다."""


def _render_png_b64(page: fitz.Page) -> str:
    import base64

    try:
        png = page.get_pixmap(dpi=cfg.FITZ_DPI).tobytes("png")
    except Exception as e:
        raise PageRenderError(f"p.{page.number} 쪽 이미지 렌더링 실패: {e}") from e
    return base64.b64encode(png).decode()


async def _render_page(page: fitz.Page, render_lock: asyncio.Lock | None) -> str:
    # PyMuPDF 는 다중 스레드를 지원하지 않아 렌더링은 이벤트 루프 스레드에서 한다. 잠금은 동시에
    # 도는 OCR 코루틴이 한 번에 한 쪽만 렌더하도록 지키는 자리다 — 요청만 동시에 보낸다.
    if render_lock is None:
        return _render_png_b64(page)
    async with render_lock:
        return _render_png_b64(page)


async def _extract_with_vlm(
    page: fitz.Page,
    client: httpx.AsyncClient,
    *,
    prompt_type: str = "ocr",  # "ocr" | "diagram"
    render_lock: asyncio.Lock | None = None,
) -> PageResult:
    img_b64 = await _render_page(page, render_lock)

    prompt = _VLM_PROMPT_DIAGRAM if prompt_type == "diagram" else _VLM_PROMPT_OCR

    async def _ask(thinking: bool | None) -> tuple[str, bool, str | None]:
        """1회 호출 → (본문, 추론정상종료, finish_reason)"""
        payload = {
            "model": cfg.VLM_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": cfg.VLM_MAX_TOKENS,
            "temperature": cfg.VLM_TEMPERATURE,
        }
        # 추론형 VLM(Qwen3.5 등)은 사고과정을 본문에 쏟아내 OCR 결과를 오염시킨다.
        # vLLM 은 chat_template_kwargs 를 템플릿에 그대로 전달. None 이면 미전송(기존 동작).
        if thinking is not None:
            payload["chat_template_kwargs"] = {"enable_thinking": thinking}

        resp = await client.post(
            f"{cfg.VLM_BASE_URL}/chat/completions",
            json=payload,
            timeout=float(cfg.VLM_TIMEOUT),
        )
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        msg = choice.get("message", {})
        raw = (msg.get("content") or "").strip()
        if msg.get("reasoning_content"):
            # vLLM --reasoning-parser 사용 시 추론이 별 필드로 분리돼 content 는 이미 깨끗함
            return raw, True, choice.get("finish_reason")
        text, complete = _strip_reasoning(raw, thinking=bool(thinking))
        return text, complete, choice.get("finish_reason")

    # getattr: 구버전 config 가 섞여도 OCR 전체가 죽지 않도록 (미정의 시 미전송)
    vlm_think = getattr(cfg, "VLM_THINK", None)
    text, complete, finish = await _ask(vlm_think)

    # 추론이 수렴하지 않는 페이지가 있다(복잡한 도판에서 사고 루프 → max_tokens 소진).
    # 토큰을 더 줘도 해결되지 않으므로, thinking 을 끄고 한 번만 재시도한다.
    if not complete:
        log.warning(
            f"[p.{page.number}] 추론 미종료(finish={finish}, max_tokens={cfg.VLM_MAX_TOKENS}) "
            f"→ thinking 끄고 재시도"
        )
        text, complete, finish = await _ask(False)
        if not complete:
            raise RuntimeError(f"thinking off 재시도도 실패(finish={finish})")

    # 비추론 모드도 max_tokens 소진을 본다 — 대부분 같은 구절을 되풀이하다 잘린 출력이다.
    truncated = finish == "length"
    if truncated:
        text, degenerate = page_routing.trim_repetition(text)
        if degenerate:
            raise VlmDegenerateOutput(f"p.{page.number} VLM 퇴화 출력(finish=length)")
        log.warning(f"[p.{page.number}] VLM 응답이 max_tokens({cfg.VLM_MAX_TOKENS})에서 잘림 — 되풀이 꼬리 정리")

    return PageResult(
        page_num=page.number,
        text=text,
        method="vlm",
        confidence=0.9,
        truncated=truncated,
    )


async def _extract_with_surya(
    page: fitz.Page,
    client: httpx.AsyncClient,
    *,
    render_lock: asyncio.Lock | None = None,
) -> PageResult:
    """Surya 전용 OCR 서비스(별도 컨테이너)로 페이지 이미지 → 텍스트.

    Surya는 transformers 5.x 의존이라 본 이미지(transformers 4.44)와 충돌 →
    별도 컨테이너로 격리하고 HTTP(/ocr, base64 PNG)로 호출한다.
    """
    img_b64 = await _render_page(page, render_lock)

    resp = await client.post(
        f"{cfg.SURYA_BASE_URL}/ocr",
        json={"image_b64": img_b64},
        timeout=float(cfg.VLM_TIMEOUT),
    )
    resp.raise_for_status()
    text = resp.json().get("text", "").strip()

    return PageResult(
        page_num=page.number,
        text=text,
        method="surya",
        confidence=0.9,
    )


async def _ocr_pages(
    jobs: list[tuple[fitz.Page, PageResult | None, str]],
    result: ExtractionResult,
    book_id: str,
    remaining: float,
    deadline: float,
) -> dict[int, PageResult]:
    """OCR 이 필요한 쪽을 VLM_PAGE_CONCURRENCY 건씩 동시에 보내고 {쪽 번호: 채택 결과} 를 돌려준다.

    렌더링은 잠금 안에서 한 쪽씩(이벤트 루프 스레드), 요청만 동시에 나간다. OCR 결과가 없는 쪽(요청 실패·
    퇴화 출력·렌더링 실패·데드라인 초과)은 ODL 결과(있으면)를 채택 때처럼 다듬어 쓴다. remaining 초 안에
    끝나지 않으면 남은 요청을 끊고 deadline_hit 를 남긴다.
    """
    if not jobs:
        return {}
    engine = cfg.OCR_ENGINE.lower()
    ocr_done: dict[int, PageResult] = {}
    finished: set[int] = set()  # OCR 시도가 끝난 쪽(성공·실패) — 데드라인에 걸린 쪽과 가른다
    deadline_hit = remaining <= 0  # 1티어·판정에 시간을 다 썼으면 렌더링도 요청도 하지 않는다

    if not deadline_hit:
        # 0 이하 설정이면 세마포어가 막혀 데드라인까지 아무 쪽도 OCR 하지 못한다 — 최소 1건은 보낸다.
        sem = asyncio.Semaphore(max(1, cfg.VLM_PAGE_CONCURRENCY))
        render_lock = asyncio.Lock()

        async with httpx.AsyncClient() as client:
            async def _one(page: fitz.Page, trigger: str) -> None:
                page_num = page.number
                async with sem:
                    log.info(f"[{book_id}] p.{page_num} → OCR 보완 ({trigger}, engine={engine})")
                    try:
                        if engine == "surya":
                            ocr_page = await _extract_with_surya(page, client, render_lock=render_lock)
                        else:
                            ocr_page = await _extract_with_vlm(
                                page, client, prompt_type="ocr", render_lock=render_lock
                            )
                    except PageRenderError as e:
                        # 다시 해도 같은 결정적 실패 — VLM 요청 실패(ocr_errors)와 따로 센다.
                        log.warning(f"[{book_id}] {e} — ODL 결과 채택")
                        result.errors.append(f"{e} — ODL 결과 채택")
                        result.render_errors += 1
                    except VlmDegenerateOutput as e:
                        # 같은 쪽은 다시 해도 대개 같다 — ocr_errors 가 아니라 vlm_truncated 로만 센다.
                        log.warning(f"[{book_id}] {e} — ODL 결과 채택")
                        result.errors.append(f"{e} — ODL 결과 채택")
                        result.vlm_truncated += 1
                    except Exception as e:
                        # httpx.ReadTimeout 은 메시지가 빈 채로 오기도 한다 — 이름을 남겨 타임아웃·연결 실패·HTTP 오류를 가른다.
                        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                        log.error(f"[{book_id}] p.{page_num} OCR({engine}) 실패: {detail}")
                        result.errors.append(f"p.{page_num} OCR({engine}): {detail}")
                        result.ocr_errors += 1
                    else:
                        if ocr_page.truncated:
                            result.vlm_truncated += 1
                        ocr_done[page_num] = ocr_page
                    finished.add(page_num)

            tasks = [asyncio.create_task(_one(page, trigger)) for page, _, trigger in jobs]
            try:
                # Celery 소프트 리밋은 코루틴 안에서 믿을 수 없다(함정 19) — 자체 데드라인으로 끊는다.
                async with asyncio.timeout(remaining):
                    await asyncio.gather(*tasks)
            except TimeoutError:
                deadline_hit = True
            finally:
                # 데드라인·바깥 취소·예기치 못한 예외 어느 쪽이든 남은 요청을 끊고 회수한 뒤 클라이언트를
                # 닫는다. 바깥 취소의 CancelledError 는 잡지 않으므로 그대로 올라간다.
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    if deadline_hit:
        result.deadline_hit = True
        left = sum(1 for page, _, _ in jobs if page.number not in finished)
        log.warning(
            f"[{book_id}] 추출 데드라인({deadline:g}s) 초과 — OCR 못 한 {left}쪽은 ODL 결과로 채택"
        )
        result.errors.append(f"추출 데드라인 초과 — {left}쪽 ODL 결과 채택")

    adopted: dict[int, PageResult] = {}
    for page, odl_page, _ in jobs:
        if page.number in ocr_done:
            adopted[page.number] = ocr_done[page.number]
        elif odl_page is not None:  # OCR 결과가 없으면 ODL 결과라도 살리기
            adopted[page.number] = _adopt_odl(odl_page)
    return adopted


async def extract_text(
    file_path: str | Path,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    force_ocr_short_pages: bool = False,
    deadline_s: float | None = None,
) -> ExtractionResult:
    """2티어 라우팅 파이프라인.

    force_ocr_short_pages: ODL 본문이 짧은 쪽을 판정 없이 모두 OCR 한다(섹션 0개 재추출용).
    deadline_s: 추출 전체 데드라인(초, 이 함수 시작부터). None 이면 INGEST_EXTRACT_DEADLINE —
        섹션 0개 재추출은 첫 추출이 남긴 시간을 넘긴다.

    1티어: OpenDataLoader로 전체 PDF 마크다운+json 추출
    2티어: 본문 부족 / CMap 손상 의심 / 표 셀 충전율 낮음 중 하나라도 해당하는
           페이지만 VLM 보완 (판단 기준은 파일 상단 docstring 참고). 판정은 쪽 순서대로 하고,
           OCR 은 문서 안에서 VLM_PAGE_CONCURRENCY 건씩 동시에 보내 결과를 쪽 순서로 조립한다.
           데드라인을 넘으면 OCR 을 끝내지 못한 쪽은 ODL 결과로 채택한다(deadline_hit).
    """
    t_start = time.monotonic()
    deadline = float(cfg.INGEST_EXTRACT_DEADLINE if deadline_s is None else deadline_s)
    result = ExtractionResult(book_id=book_id, total_pages=0)

    # ── 1티어: OpenDataLoader 전체 추출 ──────────────────
    odl_result = await extract_text_opendataloader(
        file_path, book_id, file_bytes=file_bytes
    )
    result.odl_fallback, result.odl_seconds = odl_result.odl_fallback, odl_result.odl_seconds
    odl_pages_by_num: dict[int, PageResult] = {p.page_num: p for p in odl_result.pages}
    if odl_result.errors:
        result.errors.extend(odl_result.errors)

    # ── fitz로 페이지 열기 — VLM용 이미지 렌더링 + CMap 손상 교차검증(page.get_text())에 사용 ─
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

    try:
        result.total_pages = len(doc)
        log.info(
            f"[{book_id}] {result.total_pages}p — 1티어 ODL 완료 "
            f"({len(odl_result.pages)}p 추출), 2티어 라우팅 시작"
        )

        # 문서 단위 스캔본 판정(short_flags)의 '짧은 쪽'만 문서 전체에 되풀이되는 줄(머리말·꼬리말·스탬프)을
        # 뺀 fitz 길이로 센다. 쪽별 OCR 판정(CMap 손상 2배 비교·짧은 쪽 분기)은 예전처럼 원래 fitz 길이를 쓴다.
        fitz_texts: list[str] = []
        for p in doc:
            try:
                fitz_texts.append(_clean_text(p.get_text()))
            except Exception as e:
                # 쪽 하나의 파싱 실패('too many nested graphics states' 등)가 문서 전체 추출을 막지 않게 한다 —
                # 그 쪽은 텍스트 층이 없는 쪽으로 보고(ODL 도 짧으면 OCR) 오류만 남긴다.
                log.warning(f"[{book_id}] p.{p.number} fitz 텍스트 추출 실패(빈 쪽으로 처리): {e}")
                result.errors.append(f"p.{p.number} fitz 텍스트 추출 실패: {e}")
                fitz_texts.append("")
        repeated = page_routing.repeated_lines(fitz_texts, cfg.SCAN_REPEAT_LINE_RATIO)
        fitz_raw_lens = [page_routing.body_len(t) for t in fitz_texts]
        fitz_stripped_lens = [
            page_routing.body_len(page_routing.strip_lines(t, repeated)) for t in fitz_texts
        ]
        short_flags = [
            page_routing.body_len(odl_pages_by_num[n].text if n in odl_pages_by_num else "")
            < MIN_CHARS_PER_PAGE
            and fitz_stripped_lens[n] < MIN_CHARS_PER_PAGE
            for n in range(len(doc))
        ]
        doc_is_scan = page_routing.is_scan_document(
            short_flags, min_pages=cfg.SCAN_MIN_PAGES, ratio=cfg.SCAN_SHORT_PAGE_RATIO
        )
        if doc_is_scan:
            log.info(f"[{book_id}] 짧은 쪽 {sum(short_flags)}/{len(doc)} — 스캔본 문서로 보고 짧은 쪽을 OCR")

        vlm_cap = cfg.VLM_MAX_PAGES_PER_DOC
        # 판정은 쪽 순서대로 — ODL 결과를 쓰는 쪽은 adopted, OCR 할 쪽은 ocr_jobs 에 모아 아래에서 동시에 보낸다.
        adopted: dict[int, PageResult] = {}
        ocr_jobs: list[tuple[fitz.Page, PageResult | None, str]] = []

        for page in doc:
            page_num = page.number
            odl_page = odl_pages_by_num.get(page_num)

            # 라우팅 판단 — "그림 유무"가 아니라 "1티어 결과를 믿을 수 있는지"로 판정.
            # ① 표 셀 충전율 낮음(빈 표 격자가 글자 수만 채우는 경우) 최우선 체크,
            # ② 그 외에는 fitz 추정 길이와 교차검증 — 길이 기준 충족 페이지는 fitz가
            #    크게 더 길면(CMap 손상 의심) VLM, 길이 기준 미달 페이지는 fitz도
            #    같이 짧으면(원래 짧은 페이지) ODL 그대로 채택, fitz엔 더 있으면 VLM.
            # 셋 다 아니면 1티어 결과를 그대로 채택하고 VLM은 호출하지 않는다.
            # (KCI 논문 대부분은 페이지마다 워터마크가 [그림]으로 잡혀 예전엔 전 페이지가
            #  불필요하게 VLM으로 넘어갔음 — 본문 길이 기준으로 바꿔 텍스트 페이지는 스킵.
            #  다만 길이 기준 미달 분기는 fitz 교차검증이 없어 표지·구분 페이지처럼
            #  "원래 짧은 페이지"까지 전부 VLM으로 넘기고 있었다 — 아래에서 통일)
            if odl_page is None:
                body_len = 0
                trigger = "ODL 누락"
            else:
                body_len = page_routing.body_len(odl_page.text)
                fill_ratio = odl_result.table_fill_ratios.get(page_num)

                if fill_ratio is not None and fill_ratio < 0.30:
                    # 마크다운 글자수는 충분해도 표 셀 대부분이 비어있음 — 셀이 빈
                    # 격자 문자로 렌더링돼 글자수만 채우는 실패(사내 연구로 검증:
                    # 재현율 48.1%→90.4%, 오탐 비용 < 미탐의 영구 손실).
                    trigger = f"표 셀 충전율 낮음({fill_ratio:.2f})"
                else:
                    # ODL 결과가 충분해 보여도, 폰트 CMap 손상 등으로 ODL(veraPDF 기반)이
                    # 실제로는 글자 대부분을 유실했을 수 있다("Incorrect bfrange in
                    # toUnicode CMap" 경고가 뜨는 PDF에서 확인됨 — 워터마크가 아니라
                    # 폰트 문제였음). fitz는 이런 손상에 관대해서 원문 길이를 정확히
                    # 반영하므로, 길이 비교만으로 이상 여부를 감지한다(fitz 텍스트 자체는
                    # 띄어쓰기 소실·컬럼 순서 문제가 있어 채택하지 않고 감지 용도로만 사용).
                    # 길이 기준 미달 페이지도 동일하게 fitz로 "원래 짧은 페이지"인지
                    # "ODL이 놓친 페이지"인지 구분한다 — <50자 트리거가 전체 VLM
                    # 호출의 90% 이상을 차지해 표지·구분 페이지까지 휩쓸고 있었음.
                    fitz_check_len = fitz_raw_lens[page_num]
                    if body_len >= MIN_CHARS_PER_PAGE:
                        if fitz_check_len <= body_len * 2:
                            # 정상 — 1티어 결과 채택, VLM 호출 안 함. 잔여 [그림] 마커 정리.
                            adopted[page_num] = _adopt_odl(odl_page)
                            continue
                        trigger = f"ODL 글자 유실 의심(ODL {body_len}자 vs 원본 추정 {fitz_check_len}자)"
                    else:
                        # fitz 0자(텍스트 층 없음)는 '원래 짧은 쪽'이 아니다 — 스캔본 쪽은 fitz 도
                        # ODL 도 0자를 보고해 이 신호만으로는 못 가르므로 short_page_needs_ocr 가
                        # OCR 로 보낸다(오분류하면 스캔 문서 전체가 빈 텍스트로 채택돼 섹션이 0개가 된다).
                        need_ocr, why = page_routing.short_page_needs_ocr(
                            fitz_len_stripped=fitz_stripped_lens[page_num],
                            fitz_len_raw=fitz_check_len,
                            doc_is_scan=doc_is_scan,
                            force=force_ocr_short_pages,
                            min_chars=MIN_CHARS_PER_PAGE,
                        )
                        if not need_ocr:
                            # 원래 짧은 쪽(표지·간지 등) — ODL 결과 그대로 채택.
                            adopted[page_num] = _adopt_odl(odl_page)
                            result.short_kept += 1
                            continue
                        trigger = f"{why}(ODL {body_len}자 vs 원본 추정 {fitz_check_len}자)"

            # 문서당 VLM 보완 페이지 수 상한 — 완전 스캔본 대형 문서가 잡 전체를 지연시키는 것을
            # 방지. 초과분은 ODL 결과(비어있거나 부실해도) 그대로 채택하고 VLM은 스킵한다.
            # 실패해도 호출 시도 자체가 시간을 소모하므로 OCR 로 보낸 쪽은 모두 상한에 넣는다.
            if len(ocr_jobs) >= vlm_cap:
                if not result.vlm_capped:
                    result.vlm_capped = True
                    log.warning(f"[{book_id}] VLM 페이지 상한({vlm_cap}) 도달 — 이후 저텍스트 페이지는 ODL로 대체")
                if odl_page:
                    adopted[page_num] = _adopt_odl(odl_page)
                continue
            # 2티어: 1티어 결과를 못 믿는 페이지 OCR 보완 (엔진은 OCR_ENGINE 플래그로 선택).
            ocr_jobs.append((page, odl_page, trigger))

        remaining = deadline - (time.monotonic() - t_start)
        adopted.update(await _ocr_pages(ocr_jobs, result, book_id, remaining, deadline))
    finally:
        doc.close()

    # 결과는 쪽 순서로 조립한다(OCR 은 끝나는 순서가 뒤섞인다).
    result.pages = [adopted[n] for n in range(result.total_pages) if n in adopted]

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
    prompt_type: str = "ocr",  # "ocr" | "diagram"
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
                page_result = await _extract_with_vlm(page, client, prompt_type=prompt_type)
                result.pages.append(page_result)
            except Exception as e:
                log.error(f"[{book_id}] VLM p.{page.number} 실패: {e}")
                result.errors.append(f"p.{page.number}: {e}")

    doc.close()
    log.info(f"[{book_id}] VLM 전체 추출 완료 — {result.stats}")
    return result


# opendataloader_pdf.convert → runner.run_jar 는 java 를 subprocess.run(timeout 없음)으로 띄우고 끝날
# 때까지 막는다. 같은 프로세스의 스레드에서 돌리면 wait_for 가 시간을 넘겨도 스레드와 java 는 계속
# 돈다. 그래서 convert 를 자식 파이썬에서 부르고, 새 세션(프로세스 그룹)으로 떼어 두었다가 시간을
# 넘기면 그룹째 끈다 — java 손자까지 함께 죽는다.
_ODL_CHILD = (
    "import json, sys\n"
    "import opendataloader_pdf\n"
    "opendataloader_pdf.convert(**json.loads(sys.argv[1]))\n"
)


def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # start_new_session → pgid == pid
    except (AttributeError, ProcessLookupError, PermissionError):
        proc.kill()  # Windows(개발 PC)에는 killpg 가 없다 — 자식 파이썬만 끈다


async def _odl_convert(convert_kwargs: dict, timeout: float) -> None:
    """opendataloader_pdf.convert(**convert_kwargs) 를 자식 프로세스에서 timeout 초 안에 끝낸다.

    stderr 는 파이프가 아니라 임시 파일로 받는다 — 파이프면 끈 뒤에도 그 끝을 쥔 손자 프로세스가
    살아 있는 동안 이벤트 루프가 읽기를 기다린다(Windows 에서 20초 대기로 확인).
    """
    with tempfile.TemporaryFile() as err_file:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", _ODL_CHILD, json.dumps(convert_kwargs),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=err_file.fileno(),
            start_new_session=True,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout)
        except BaseException:
            _kill_process_group(proc)
            await proc.wait()
            raise
        if proc.returncode != 0:
            err_file.seek(0)
            tail = err_file.read().decode("utf-8", "replace").strip()[-300:]
            raise RuntimeError(f"ODL 변환 실패(exit {proc.returncode}): {tail}")


async def _run_odl(input_path: str, out_dir: str, page_sep: str, timeout: float) -> Path:
    """ODL 변환 1회 — markdown·json 을 한 번에 out_dir 에 쓰고 markdown 경로를 돌려준다."""
    await _odl_convert(
        {
            "input_path": input_path,
            "output_dir": out_dir,
            "format": ["markdown", "json"],
            "image_output": cfg.ODL_IMAGE_OUTPUT,  # 그림 저장은 운영 0건 — 기본 off 로 인코딩을 아낀다
            "image_format": "jpeg",
            "table_method": "cluster",   # 무경계/복잡 표까지 검출
            "markdown_page_separator": page_sep,
            "keep_line_breaks": False,
            "quiet": True,
        },
        timeout,
    )
    md_files = sorted(Path(out_dir).glob("*.md"))
    if not md_files:
        raise RuntimeError("markdown 출력 파일 없음")
    return md_files[0]


def _fitz_text_pages(path: str, max_pages: int | None) -> list[PageResult]:
    """ODL 이 끝내 실패한 문서 — fitz 텍스트를 1티어 결과로 쓴다(머리말·꼬리말 제거와 표 구조는 잃는다 — json 이 없다).

    extract_text 의 교차검증은 이 결과에서도 뜻이 흐려지지 않는다. CMap 2배 비교는 fitz 대 fitz(비율 1)라
    걸리지 않는데, 'ODL 이 글자를 잃었나'를 물을 ODL 이 없고 fitz 는 그 비교의 기준(손상에 관대한 쪽)이다.
    짧은 쪽 분기는 그대로 돈다 — 글자가 없는 쪽은 넣지 않아(ODL 이 빈 쪽을 내지 않는 것과 같게) 'ODL 누락'
    → OCR(= 텍스트 층 없음 → OCR), 글자가 조금 있는 쪽은 문서 단위 스캔 판정을 그대로 탄다.
    """
    pages: list[PageResult] = []
    with fitz.open(path) as doc:
        for page in doc:
            if max_pages and page.number >= max_pages:
                break
            try:
                raw = page.get_text("text").strip()
            except RuntimeError:  # 'too many nested graphics states' 등 — PyMuPDF 가 RuntimeError 로 올린다
                # 쪽 하나의 파싱 실패가 폴백 전체를 버리지 않게 그 쪽만 뺀다('ODL 누락' → OCR). 같은 쪽은
                # extract_text 가 fitz 텍스트를 미리 받을 때도 실패해 거기서 오류로 남는다.
                continue
            if raw:
                pages.append(PageResult(page_num=page.number, text=_clean_text(raw), method="fitz", confidence=0.5))
    return pages


async def extract_text_opendataloader(
    file_path: str | Path | None,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    max_pages: int | None = None,
) -> ExtractionResult:
    """OpenDataLoader PDF를 이용한 추출 — extract_text()가 호출하는 실제 1티어 진입점.

    설치: pip install opendataloader-pdf

    markdown·json을 한 번의 실행으로 함께 산출한다(추가 비용 없음). markdown은
    기존과 동일하게 본문으로 쓰고, json은 표 셀이 실제로 비어있는지를 구조
    그대로 담고 있어 라우팅 판정용 신호(table_fill_ratios)로만 사용한다.
    (마크다운 평탄화 과정에서 "빈 셀"과 "내용 있는 셀"이 똑같이 `| |` 격자
    문자로 변해 라우팅 신호가 사라지는 문제 — 사내 연구 결과 반영)

    변환은 max(ODL_TIMEOUT_BASE_SECONDS, 쪽수 × ODL_TIMEOUT_PER_PAGE_SECONDS) 초 안에 끝나야 한다.
    넘거나 실패하면 fitz 로 다시 저장한 PDF 로 한 번 더, 그래도 안 되면 fitz 텍스트로 대신한다
    (쪽 method "fitz"). fitz 로도 열리지 않는 파일은 재저장·fitz 폴백 없이 오류만 남긴다.
    """
    import json as _json
    from collections import defaultdict

    result = ExtractionResult(book_id=book_id, total_pages=0)

    try:
        import opendataloader_pdf  # noqa: F401 — 설치 확인. 변환은 자식 프로세스가 한다(_odl_convert)
    except ImportError:
        result.errors.append(
            "opendataloader-pdf 패키지 미설치 — pip install opendataloader-pdf"
        )
        return result

    _PAGE_SEP = "\n<<<ODL_PAGE_BREAK_%page-number%>>>\n"

    tmp_path = None
    resaved_path = None
    out_dir = None
    try:
        if file_bytes:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            load_path = tmp_path
        else:
            load_path = str(file_path)

        try:
            with fitz.open(load_path) as probe:
                page_count: int | None = len(probe)
        except RuntimeError as e:  # FileDataError·EmptyFileError·FileNotFoundError — PyMuPDF 1.24·1.28 모두 RuntimeError 하위
            page_count = None
            log.warning(f"[{book_id}] fitz 로 열리지 않는 PDF — ODL 만 한 번 시도: {e}")
        odl_timeout = max(
            cfg.ODL_TIMEOUT_BASE_SECONDS, (page_count or 0) * cfg.ODL_TIMEOUT_PER_PAGE_SECONDS
        )

        async def _convert(input_path: str, output_dir: str) -> Path:
            # 변환 한 번 — 실패해도 걸린 시간을 쌓고 상한과 함께 남긴다(상한을 정할 실측 자료)
            t0 = time.monotonic()
            try:
                return await _run_odl(input_path, output_dir, _PAGE_SEP, odl_timeout)
            finally:
                seconds = time.monotonic() - t0
                result.odl_seconds += seconds
                log.info(f"[{book_id}] ODL {seconds:.1f}초 / 상한 {odl_timeout:.0f}초")

        out_dir = tempfile.mkdtemp()
        md_file: Path | None = None
        try:
            md_file = await _convert(load_path, out_dir)
        except (TimeoutError, RuntimeError, OSError) as e:
            reason = f"{odl_timeout:.0f}초 초과" if isinstance(e, TimeoutError) else str(e)
            log.warning(f"[{book_id}] ODL 실패({reason}) — fitz 재저장본으로 한 번 더")
            result.errors.append(f"ODL 실패(원본): {reason}")
            if page_count is not None:
                # xref 손상 문서에서 ODL(Java)이 브루트포스 복구로 수십 배 느려지는 문제 대응 — fitz 로 다시
                # 저장하면 xref 를 새로 쓴다
                try:
                    fd, resaved_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(fd)
                    with fitz.open(load_path) as src:
                        src.save(resaved_path, garbage=4, clean=True, deflate=True)
                    shutil.rmtree(out_dir, ignore_errors=True)
                    out_dir = tempfile.mkdtemp()
                    md_file = await _convert(resaved_path, out_dir)
                    result.odl_fallback = "resaved"
                except (TimeoutError, RuntimeError, ValueError, OSError, fitz.mupdf.FzErrorBase) as e2:
                    # 손상 PDF 의 재저장은 mupdf FzErrorBase 로도 실패한다(RuntimeError 가 아니다 — PyMuPDF 1.24·1.28
                    # 모두 FzErrorArgument 'not a dict'). 그래도 아래 fitz 텍스트 폴백으로 간다.
                    reason2 = f"{odl_timeout:.0f}초 초과" if isinstance(e2, TimeoutError) else str(e2)
                    result.errors.append(f"ODL 실패(fitz 재저장본): {reason2}")

        if md_file is None:
            if page_count is not None:
                result.pages = _fitz_text_pages(load_path, max_pages)
                result.odl_fallback = "fitz"
                result.total_pages = len(result.pages)
                result.errors.append("ODL 실패 — fitz 텍스트로 대체")
                log.warning(f"[{book_id}] ODL 실패 — fitz 텍스트 {len(result.pages)}쪽으로 대체")
            return result

        out_path = Path(out_dir)
        json_files = list(out_path.glob("*.json"))

        # ── JSON → 페이지별 표 셀 충전율(라우팅 신호) + 머리말/쪽번호 텍스트 ──
        page_headers_footers: dict[int, set[str]] = {}
        image_pages: set[int] = set()  # 1-based — 그림 요소가 있는 쪽
        if json_files:
            try:
                with open(json_files[0], encoding="utf-8") as f:
                    jdata = _json.load(f)
                by_page: dict[int, list] = defaultdict(list)
                for el in jdata.get("kids", []):
                    by_page[el.get("page number", 1)].append(el)
                for pnum, elements in by_page.items():
                    if any(el.get("type") == "image" for el in elements):
                        image_pages.add(pnum)
                    hf_lines: set[str] = set()
                    for el in elements:
                        if el.get("type") in ("header", "footer"):
                            hf_lines.update(_collect_content_strings(el))
                    if hf_lines:
                        page_headers_footers[pnum - 1] = hf_lines  # 1-based → 0-based
                    # 표가 여럿이면 셀 수로 가중 합산(페이지 전체 셀 대비 빈 셀 비율).
                    # 표별 min()을 쓰면 레이아웃용 소형 빈 표(예: 1x2) 하나만으로
                    # 본표가 멀쩡해도 폴백이 발동한다 — 큰 표가 자연히 더 반영되도록
                    # 셀 단위로 합산(연구팀 측정 방식과 동일하게 맞춤).
                    total = empty = 0
                    for el in elements:
                        if el.get("type") != "table":
                            continue
                        for row in el.get("rows", []):
                            for cell in row.get("cells", []):
                                total += 1
                                if not cell.get("kids"):
                                    empty += 1
                    if total:
                        result.table_fill_ratios[pnum - 1] = 1 - empty / total  # 1-based → 0-based
            except Exception as e:
                log.warning(f"[{book_id}] 표 충전율 파싱 실패(무시하고 진행): {e}")

        # ── markdown → 페이지별 텍스트 ────────────────────────────
        with open(md_file, encoding="utf-8") as f:
            content = f.read()

        import re
        sep_pattern = re.escape(_PAGE_SEP).replace(re.escape("%page-number%"), r"(\d+)")
        parts = re.split(sep_pattern, content)

        documents: list[tuple[int, str]] = []  # (page_num 1-based, text)
        if parts[0].strip():
            documents.append((1, parts[0].strip()))
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts) and parts[i + 1].strip():
                documents.append((int(parts[i]), parts[i + 1].strip()))

        # image_output=off 면 그림만 있는 쪽이 markdown 에서 통째로 빠진다. embedded 일 때처럼
        # 'ODL 이 본 빈 쪽'으로 남겨야 extract_text 가 'ODL 누락'(판정 없이 OCR) 대신 fitz 교차검증을 탄다.
        seen = {pnum for pnum, _ in documents}
        documents.extend((pnum, "") for pnum in image_pages if pnum not in seen)
        documents.sort(key=lambda d: d[0])

        if max_pages:
            documents = documents[:max_pages]

        import base64 as _b64
        # base64 이미지 패턴 (embedded)
        img_b64_pattern = re.compile(
            r'!\[([^\]]*)\]\(data:image/[^;]+;base64,([^)]+)\)'
        )
        # 외부 경로 이미지 패턴 (비 base64)
        img_any_pattern = re.compile(r'!\[[^\]]*\]\([^)]+\)')

        result.total_pages = len(documents)
        for i, (doc_page_num, raw) in enumerate(documents):
            page_num = doc_page_num - 1  # OpenDataLoader는 1-based → 0-based

            # ── 그림 추출: base64 이미지마다 앞뒤 컨텍스트 보존 ──
            for img_idx, m in enumerate(img_b64_pattern.finditer(raw)):
                try:
                    img_bytes = _b64.b64decode(m.group(2))
                except Exception:
                    continue

                # 앞 300자: 다른 base64 이미지는 [그림]으로 치환 후 추출
                before_raw = raw[max(0, m.start() - 300):m.start()]
                before = img_b64_pattern.sub('[그림]', before_raw).strip()

                # 뒤 300자: 동일 처리
                after_raw = raw[m.end():m.end() + 300]
                after = img_b64_pattern.sub('[그림]', after_raw).strip()

                result.figures.append(FigureData(
                    page_num=page_num,
                    img_idx=img_idx,
                    img_bytes=img_bytes,
                    before_context=before,
                    after_context=after,
                ))

            img_count = len(img_b64_pattern.findall(raw))
            stripped = img_any_pattern.sub('[그림]', raw)
            text = _clean_text(stripped, strip_lines=page_headers_footers.get(page_num))
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
        for path in (tmp_path, resaved_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        if out_dir:
            shutil.rmtree(out_dir, ignore_errors=True)

    log.info(f"[{book_id}] OpenDataLoader 추출 완료 — {result.stats}, 표충전율={result.table_fill_ratios}")
    return result
