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

MIN_CHARS_PER_PAGE = cfg.EXTRACT_MIN_CHARS_PER_PAGE


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


# 마크다운 표 구조 문자 + 공백 — 실질 본문 길이 계산에서 제외
_STRUCT_CHARS = str.maketrans("", "", "|-: \t\n\r")


def _body_len(text: str) -> int:
    """실질 본문 길이. [그림] 마커와 빈 표 껍데기는 길이로 세지 않는다.

    OpenDataLoader 는 사진·도판 위주 페이지를 내용 없는 마크다운 표(`| | | |`)로
    내보내는데, 파이프 문자만으로 수백 자가 되어 VLM 라우팅 기준을 통과해버린다
    (→ 그 페이지는 OCR 없이 빈 표만 남아 내용이 유실됨).
    구조 문자를 뺀 뒤 재므로, 셀에 실제 내용이 있는 표는 그대로 본문으로 카운트된다.
    """
    return len(text.replace("[그림]", "").translate(_STRUCT_CHARS))


def _strip_figure_markers(text: str) -> str:
    """본문 채택 페이지에 남은 단독 [그림] 마커(워터마크·삽화 흔적) 정리.

    그림 자체는 result.figures(base64)로 별도 저장되므로 인라인 마커는 노이즈일 뿐.
    다운스트림(요약·청킹·검색)에서 [그림] 인라인 마커를 신호로 쓰지 않는다.
    """
    import re
    text = text.replace("[그림]", "")
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


@dataclass
class PageResult:
    page_num: int
    text: str
    method: str          # "fitz" | "vlm"
    confidence: float


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


async def _extract_with_vlm(
    page: fitz.Page,
    client: httpx.AsyncClient,
    *,
    prompt_type: str = "ocr",  # "ocr" | "diagram"
) -> PageResult:
    import base64

    pix = page.get_pixmap(dpi=cfg.FITZ_DPI)
    img_bytes = pix.tobytes("png")
    img_b64 = base64.b64encode(img_bytes).decode()

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

    return PageResult(
        page_num=page.number,
        text=text,
        method="vlm",
        confidence=0.9,
    )


async def _extract_with_surya(
    page: fitz.Page,
    client: httpx.AsyncClient,
) -> PageResult:
    """Surya 전용 OCR 서비스(별도 컨테이너)로 페이지 이미지 → 텍스트.

    Surya는 transformers 5.x 의존이라 본 이미지(transformers 4.44)와 충돌 →
    별도 컨테이너로 격리하고 HTTP(/ocr, base64 PNG)로 호출한다.
    """
    import base64

    pix = page.get_pixmap(dpi=cfg.FITZ_DPI)
    img_b64 = base64.b64encode(pix.tobytes("png")).decode()

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

    vlm_pages_used = 0
    vlm_cap = cfg.VLM_MAX_PAGES_PER_DOC
    vlm_cap_hit = False

    async with httpx.AsyncClient() as client:
        for page in doc:
            page_num = page.number
            odl_page = odl_pages_by_num.get(page_num)

            # 라우팅 판단 — "그림 유무"가 아니라 "본문 텍스트 충분 여부"로 판정.
            # [그림] 마커(워터마크·로고·삽화 흔적)를 뺀 실질 본문이 기준 미만이면
            # 텍스트 레이어가 없는(스캔·이미지) 페이지로 보고 VLM OCR로 보완한다.
            # (KCI 논문 대부분은 페이지마다 워터마크가 [그림]으로 잡혀 예전엔 전 페이지가
            #  불필요하게 VLM으로 넘어갔음 — 본문 길이 기준으로 바꿔 텍스트 페이지는 스킵)
            if odl_page is None:
                body_len = 0
                trigger = "ODL 누락"
            else:
                body_len = _body_len(odl_page.text)
                fill_ratio = odl_result.table_fill_ratios.get(page_num)
                if body_len >= MIN_CHARS_PER_PAGE and (fill_ratio is None or fill_ratio >= 0.30):
                    # ODL 결과가 충분해 보여도, 폰트 CMap 손상 등으로 ODL(veraPDF 기반)이
                    # 실제로는 글자 대부분을 유실했을 수 있다("Incorrect bfrange in
                    # toUnicode CMap" 경고가 뜨는 PDF에서 확인됨 — 워터마크가 아니라
                    # 폰트 문제였음). fitz는 이런 손상에 관대해서 원문 길이를 정확히
                    # 반영하므로, 길이 비교만으로 이상 여부를 감지한다(fitz 텍스트 자체는
                    # 띄어쓰기 소실·컬럼 순서 문제가 있어 채택하지 않고 감지 용도로만 사용).
                    fitz_check_len = _body_len(_clean_text(page.get_text()))
                    if fitz_check_len <= body_len * 2:
                        # 정상 — 1티어 결과 채택, VLM 호출 안 함. 잔여 [그림] 마커 정리.
                        odl_page.text = _strip_figure_markers(odl_page.text)
                        result.pages.append(odl_page)
                        continue
                    trigger = f"ODL 글자 유실 의심(ODL {body_len}자 vs 원본 추정 {fitz_check_len}자)"
                elif fill_ratio is not None and fill_ratio < 0.30:
                    # 마크다운 글자수는 충분해도 표 셀 대부분이 비어있음 — 셀이 빈
                    # 격자 문자로 렌더링돼 글자수만 채우는 실패(사내 연구로 검증:
                    # 재현율 48.1%→90.4%, 오탐 비용 < 미탐의 영구 손실).
                    trigger = f"표 셀 충전율 낮음({fill_ratio:.2f})"
                else:
                    trigger = f"본문 텍스트 부족({body_len}자)"

            # 문서당 VLM 보완 페이지 수 상한 — 완전 스캔본 대형 문서가 페이지마다
            # 순차 VLM 호출로 잡 전체를 지연시키는 것을 방지. 초과분은 ODL 결과
            # (비어있거나 부실해도) 그대로 채택하고 남은 페이지는 VLM을 스킵한다.
            if vlm_pages_used >= vlm_cap:
                if not vlm_cap_hit:
                    vlm_cap_hit = True
                    result.vlm_capped = True
                    log.warning(f"[{book_id}] VLM 페이지 상한({vlm_cap}) 도달 — 이후 저텍스트 페이지는 ODL로 대체")
                if odl_page:
                    result.pages.append(odl_page)
                continue

            # 2티어: 본문 없는 스캔·이미지 페이지 OCR 보완 (엔진은 OCR_ENGINE 플래그로 선택).
            ocr_engine = cfg.OCR_ENGINE.lower()
            vlm_pages_used += 1  # 실패해도 호출 시도 자체가 시간을 소모하므로 상한에 포함
            try:
                log.info(f"[{book_id}] p.{page_num} → OCR 보완 ({trigger}, engine={ocr_engine})")
                if ocr_engine == "surya":
                    ocr_page = await _extract_with_surya(page, client)
                else:
                    ocr_page = await _extract_with_vlm(page, client, prompt_type="ocr")
                result.pages.append(ocr_page)
            except Exception as e:
                log.error(f"[{book_id}] p.{page_num} OCR({ocr_engine}) 실패: {e}")
                result.errors.append(f"p.{page_num} OCR({ocr_engine}): {e}")
                if odl_page:  # OCR 실패 시 ODL 결과라도 살리기
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


async def extract_text_opendataloader(
    file_path: str | Path | None,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    max_pages: int | None = None,
) -> ExtractionResult:
    """OpenDataLoader PDF를 이용한 추출 (3단계, 비교 테스트용)

    설치: pip install open-data-loader

    markdown·json을 한 번의 실행으로 함께 산출한다(추가 비용 없음). markdown은
    기존과 동일하게 본문으로 쓰고, json은 표 셀이 실제로 비어있는지를 구조
    그대로 담고 있어 라우팅 판정용 신호(table_fill_ratios)로만 사용한다.
    (마크다운 평탄화 과정에서 "빈 셀"과 "내용 있는 셀"이 똑같이 `| |` 격자
    문자로 변해 라우팅 신호가 사라지는 문제 — 사내 연구 결과 반영)
    """
    import asyncio
    import json as _json
    import os
    import tempfile
    from collections import defaultdict
    from pathlib import Path as _Path

    result = ExtractionResult(book_id=book_id, total_pages=0)

    try:
        import opendataloader_pdf  # pip install opendataloader-pdf (Java 11+ 필요)
    except ImportError:
        result.errors.append(
            "opendataloader-pdf 패키지 미설치 — pip install opendataloader-pdf"
        )
        return result

    _PAGE_SEP = "\n<<<ODL_PAGE_BREAK_%page-number%>>>\n"

    tmp_path = None
    out_dir = None
    try:
        if file_bytes:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            load_path = tmp_path
        else:
            load_path = str(file_path)

        out_dir = tempfile.mkdtemp()

        def _convert_sync() -> None:
            opendataloader_pdf.convert(
                input_path=load_path,
                output_dir=out_dir,
                format=["markdown", "json"],
                image_output="embedded",  # 이미지 base64 인라인 (없으면 그림 흔적조차 안 남음)
                image_format="jpeg",      # base64 크기 절감
                table_method="cluster",   # 무경계/복잡 표까지 검출
                markdown_page_separator=_PAGE_SEP,
                keep_line_breaks=False,
                quiet=True,
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _convert_sync)

        out_path = _Path(out_dir)
        md_files = list(out_path.glob("*.md"))
        json_files = list(out_path.glob("*.json"))
        if not md_files:
            raise RuntimeError("markdown 출력 파일 없음")

        # ── JSON → 페이지별 표 셀 충전율 (라우팅 신호 전용) ──────────
        if json_files:
            try:
                with open(json_files[0], encoding="utf-8") as f:
                    jdata = _json.load(f)
                by_page: dict[int, list] = defaultdict(list)
                for el in jdata.get("kids", []):
                    by_page[el.get("page number", 1)].append(el)
                for pnum, elements in by_page.items():
                    ratios = []
                    for el in elements:
                        if el.get("type") != "table":
                            continue
                        total = empty = 0
                        for row in el.get("rows", []):
                            for cell in row.get("cells", []):
                                total += 1
                                if not cell.get("kids"):
                                    empty += 1
                        if total:
                            ratios.append(1 - empty / total)
                    if ratios:
                        result.table_fill_ratios[pnum - 1] = min(ratios)  # 1-based → 0-based
            except Exception as e:
                log.warning(f"[{book_id}] 표 충전율 파싱 실패(무시하고 진행): {e}")

        # ── markdown → 페이지별 텍스트 ────────────────────────────
        with open(md_files[0], encoding="utf-8") as f:
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
        if out_dir:
            import shutil
            try:
                shutil.rmtree(out_dir, ignore_errors=True)
            except OSError:
                pass

    log.info(f"[{book_id}] OpenDataLoader 추출 완료 — {result.stats}, 표충전율={result.table_fill_ratios}")
    return result