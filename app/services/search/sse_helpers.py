"""
sse_helpers.py — SSE 스트림 처리 헬퍼

LLM 델타 스트림을 SSE 이벤트 딕셔너리로 변환한다.
pipeline.py에서 가져다 쓰고, 단위 테스트가 직접 임포트한다.
"""
import re
from typing import AsyncGenerator

from core.config import get_settings


EFFECT_DELIM = "###EFFECT###"
DELIM_LEN = len(EFFECT_DELIM)  # 12

# 모델이 본문 맨 앞에 출력하는 섹션 라벨 방어 — [추천 이유], [읽고 난 후], "추천 이유:" 등.
# 프롬프트로 1차 차단하지만 LLM이 비결정적이라 가끔 새므로 코드에서 한 번 더 제거한다.
_LABELS = r"추천\s*이유|읽고\s*난\s*후|읽은\s*후|독후\s*효과"
# 완성된 선두 라벨: "[ ... ]"  또는  "추천 이유:" 형태
_LABEL_LINE_RE = re.compile(rf"^\s*(?:\[[^\]\n]{{0,40}}\]|(?:{_LABELS})\s*[:：])\s*\n?")
# 라벨이 될 수도 있는 미완성 후보 (']' 또는 ':' 가 아직 안 온 상태 → 판별 보류)
_LABEL_PENDING_RE = re.compile(rf"^\s*(?:\[[^\]\n]*|(?:{_LABELS})\s*)$")


def _consume_label(buf: str) -> tuple[str, bool, bool]:
    """섹션 선두 라벨 제거. returns (buf, done, hold).
    done=True → 라벨 처리 종료(이후 그대로 통과) / hold=True → 판단 보류(델타 더 필요).
    개행을 기다리지 않고 ']' 또는 ':' 가 오는 즉시 판별 → 본문 스트리밍을 막지 않는다.
    """
    if not buf.strip():
        return buf, False, True                     # 아직 내용 없음 → 보류
    m = _LABEL_LINE_RE.match(buf)
    if m:
        return buf[m.end():], True, False           # 완성된 라벨 → 제거
    if _LABEL_PENDING_RE.match(buf):
        return buf, False, True                     # 라벨 후보 미완성 → 보류
    return buf, True, False                          # 라벨 아님 → 그대로 통과


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
    text_lead_done = False      # 추천이유 섹션 선두 라벨 제거 완료?
    effect_lead_done = False    # 독후효과 섹션 선두 라벨 제거 완료?

    async for delta in deltas:
        buf += delta

        # Phase 1: kw 파싱 — 첫 줄 완성 대기
        if not kw_parsed:
            if "\n" not in buf:
                continue
            first, rest = buf.split("\n", 1)
            first = first.strip()
            if first.startswith("#KW"):
                kws = [k.strip() for k in first[4:].split(",") if k.strip()]
                if kws:
                    yield {"keywords": kws[: cfg.KEYWORDS_MAX_COUNT]}
                buf = rest
            # else: 첫 줄이 #KW가 아니면 본문 — buf 그대로 두고 라벨 strip이 처리
            kw_parsed = True

        # Phase 2: 추천이유(text) — 섹션 선두 라벨 제거
        if not effect_started:
            if not text_lead_done:
                buf, text_lead_done, hold = _consume_label(buf)
                if hold:
                    continue
            if EFFECT_DELIM in buf:
                idx = buf.index(EFFECT_DELIM)
                pre = buf[:idx]
                post = buf[idx + DELIM_LEN :].lstrip("\n")
                if pre:
                    yield {"text": pre}
                effect_started = True
                buf = post
            else:
                # 구분자가 버퍼 끝에 걸쳐 올 수 있으므로 마지막 DELIM_LEN-1 자는 홀딩
                safe_len = len(buf) - (DELIM_LEN - 1)
                if safe_len > 0:
                    yield {"text": buf[:safe_len]}
                    buf = buf[safe_len:]
                continue

        # Phase 3: 독후효과(effect) — 섹션 선두 라벨 제거
        if effect_started:
            if not effect_lead_done:
                buf, effect_lead_done, hold = _consume_label(buf)
                if hold:
                    continue
            if buf:
                yield {"effect": buf}
                buf = ""

    # 잔여 버퍼 flush — 섹션 선두 라벨이 남아 있으면 한 번 더 제거
    if (not effect_started and not text_lead_done) or (effect_started and not effect_lead_done):
        buf = _LABEL_LINE_RE.sub("", buf, count=1)
    if buf.strip():
        yield {"effect" if effect_started else "text": buf}
