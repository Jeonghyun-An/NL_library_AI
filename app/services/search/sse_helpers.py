"""
sse_helpers.py — SSE 스트림 처리 헬퍼

LLM 델타 스트림을 SSE 이벤트 딕셔너리로 변환한다.
pipeline.py에서 가져다 쓰고, 단위 테스트가 직접 임포트한다.
"""
from typing import AsyncGenerator

from core.config import get_settings


EFFECT_DELIM = "###EFFECT###"
DELIM_LEN = len(EFFECT_DELIM)  # 12


async def process_reason_deltas(
    deltas: AsyncGenerator[str, None],
    marc_keywords: list[str],
) -> AsyncGenerator[dict, None]:
    """
    LLM 델타 스트림 → SSE 이벤트 딕셔너리.

    이벤트 종류:
      {keywords: [...]}  — MARC 없을 때 LLM 첫 줄 #KW: 파싱
      {text: "..."}      — 추천 이유 (###EFFECT### 이전)
      {effect: "..."}    — 독후 효과 (###EFFECT### 이후)

    MARC 키워드가 있으면 kw 파싱을 건너뛰고 바로 text 상태로 진입한다.
    MARC keywords 이벤트는 호출자가 미리 emit하므로 이 함수는 emit하지 않는다.
    """
    cfg = get_settings()
    buf = ""
    kw_parsed = bool(marc_keywords)
    effect_started = False

    async for delta in deltas:
        buf += delta

        # Phase 1: kw 파싱 — 첫 줄 완성 대기
        if not kw_parsed:
            if "\n" not in buf:
                continue
            first, buf = buf.split("\n", 1)
            first = first.strip()
            if first.startswith("#KW:"):
                kws = [k.strip() for k in first[4:].split(",") if k.strip()]
                if kws:
                    yield {"keywords": kws[: cfg.KEYWORDS_MAX_COUNT]}
            elif first:
                yield {"text": first + "\n"}
            kw_parsed = True
            # buf = 첫 줄 이후 잔여 텍스트 → text/effect 블록으로 fall through

        # Phase 2/3: text / effect
        if not effect_started:
            if EFFECT_DELIM in buf:
                idx = buf.index(EFFECT_DELIM)
                pre = buf[:idx]
                post = buf[idx + DELIM_LEN :].lstrip("\n")
                if pre:
                    yield {"text": pre}
                effect_started = True
                buf = post
                if buf:
                    yield {"effect": buf}
                    buf = ""
            else:
                # 구분자가 버퍼 끝에 걸쳐 올 수 있으므로 마지막 DELIM_LEN-1 자는 홀딩
                safe_len = len(buf) - (DELIM_LEN - 1)
                if safe_len > 0:
                    yield {"text": buf[:safe_len]}
                    buf = buf[safe_len:]
        else:
            if buf:
                yield {"effect": buf}
                buf = ""

    # 잔여 버퍼 flush
    if buf.strip():
        yield {"effect" if effect_started else "text": buf}
