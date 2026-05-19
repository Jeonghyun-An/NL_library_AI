"""
chunker.py — 시맨틱 청킹

1) 문장 단위 분할
2) 인접 문장 그룹의 임베딩 유사도 계산
3) 유사도 급감 지점을 의미 경계로 판정
4) 경계 기준 청크 생성 (min/max 토큰 제약)
"""
import re
import logging
from dataclasses import dataclass, field

import numpy as np

from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

# ── 설정 ────────────────────────────────────────────────
MIN_CHUNK_TOKENS = 128
MAX_CHUNK_TOKENS = 1024
# Milvus VARCHAR(16384 bytes) 한도. 의미 분할이 실패하는 케이스에서도 데이터 손실 없이
# 청크가 분할되도록 강제하는 최종 가드. 안전 마진 800바이트 확보.
MAX_CHUNK_BYTES = 15500
SIMILARITY_WINDOW = 3          # 문장 그룹 크기
BREAKPOINT_PERCENTILE = 25     # 유사도 하위 N% 지점을 경계로


@dataclass
class Chunk:
    chunk_idx: int
    text: str
    section_idx: int | None = None    # 소속 섹션 (원문 로드용 포인터)
    page_start: int | None = None
    page_end: int | None = None
    token_count: int = 0

    def __post_init__(self):
        if not self.token_count:
            self.token_count = _estimate_tokens(self.text)


def _estimate_tokens(text: str) -> int:
    """한국어 기준 대략적 토큰 수 추정 (글자 수 / 1.5)"""
    return max(1, int(len(text) / 1.5))


def _normalize_linebreaks(text: str) -> str:
    """PDF 추출 텍스트의 줄바꿈 아티팩트 정규화.

    단락 내 단순 줄 넘김(PDF 컬럼 래핑)은 공백으로 합치고,
    실제 단락 구분(빈 줄 / 두 번 이상 연속 줄바꿈)은 유지.
    """
    # 연속 줄바꿈(단락 구분)을 플레이스홀더로 임시 치환
    text = re.sub(r'\n{2,}', '\x00', text)
    # 단락 내 단일 줄바꿈 → 공백
    text = re.sub(r'\n', ' ', text)
    # 연속 공백 정리
    text = re.sub(r'  +', ' ', text)
    # 플레이스홀더 복원
    text = text.replace('\x00', '\n\n')
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    """한국어 문장 분리 (kss 사용 시도, 실패 시 정규식 fallback)"""
    try:
        import kss
        sentences = kss.split_sentences(text)
    except Exception:
        # fallback: 마침표/물음표/느낌표 + 공백 기준
        sentences = re.split(r'(?<=[.?!。])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def _compute_embeddings(sentences: list[str], embed_fn) -> np.ndarray:
    """문장 리스트 → 임베딩 행렬"""
    embeddings = embed_fn(sentences)
    if isinstance(embeddings, list):
        embeddings = np.array(embeddings)
    return embeddings


def _find_breakpoints(
    embeddings: np.ndarray,
    window: int = SIMILARITY_WINDOW,
    percentile: int = BREAKPOINT_PERCENTILE,
) -> list[int]:
    """
    슬라이딩 윈도우로 인접 그룹 간 코사인 유사도 계산,
    유사도가 급감하는 지점을 경계로 반환
    """
    if len(embeddings) < window * 2:
        return []

    similarities = []
    for i in range(window, len(embeddings) - window):
        left = embeddings[i - window : i].mean(axis=0)
        right = embeddings[i : i + window].mean(axis=0)

        cos_sim = np.dot(left, right) / (
            np.linalg.norm(left) * np.linalg.norm(right) + 1e-8
        )
        similarities.append((i, float(cos_sim)))

    if not similarities:
        return []

    # 유사도 하위 percentile을 경계로
    sim_values = [s[1] for s in similarities]
    threshold = np.percentile(sim_values, percentile)

    breakpoints = [idx for idx, sim in similarities if sim < threshold]
    return breakpoints


def _merge_small_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """MIN_CHUNK_TOKENS 미만 청크를 인접 청크에 병합"""
    if not chunks:
        return chunks

    merged = [chunks[0]]
    for chunk in chunks[1:]:
        if merged[-1].token_count < MIN_CHUNK_TOKENS:
            merged[-1].text += "\n" + chunk.text
            merged[-1].token_count = _estimate_tokens(merged[-1].text)
            merged[-1].page_start = min(
                p for p in [merged[-1].page_start, chunk.page_start] if p is not None
            ) if (merged[-1].page_start is not None or chunk.page_start is not None) else None

            merged[-1].page_end = max(
                p for p in [merged[-1].page_end, chunk.page_end] if p is not None
            ) if (merged[-1].page_end is not None or chunk.page_end is not None) else None
        else:
            merged.append(chunk)

    # 마지막 청크도 체크
    if len(merged) > 1 and merged[-1].token_count < MIN_CHUNK_TOKENS:
        merged[-2].text += "\n" + merged[-1].text
        merged[-2].token_count = _estimate_tokens(merged[-2].text)
    
        merged[-2].page_start = min(
            p for p in [merged[-2].page_start, merged[-1].page_start] if p is not None
        ) if (merged[-2].page_start is not None or merged[-1].page_start is not None) else None
    
        merged[-2].page_end = max(
            p for p in [merged[-2].page_end, merged[-1].page_end] if p is not None
        ) if (merged[-2].page_end is not None or merged[-1].page_end is not None) else None
    
        merged.pop()

    return merged


def _split_by_bytes(chunk: Chunk, max_bytes: int = MAX_CHUNK_BYTES) -> list[Chunk]:
    """문장 분할로 안 잘리는 초대형 청크를 바이트 한도 안에서 강제 분할.

    VLM이 마침표 없는 한 덩어리로 뽑은 페이지처럼 `_split_oversized`로 분할이
    안 되는 경우의 최후 가드. 의미 경계는 깨질 수 있지만 데이터는 손실 없이 유지.
    """
    text = chunk.text
    if len(text.encode("utf-8")) <= max_bytes:
        return [chunk]

    parts: list[Chunk] = []
    cursor = 0
    n = len(text)
    while cursor < n:
        # 한글 평균 3 bytes/char 가정해서 보수적으로 시작 위치를 잡고,
        # 정확한 바이트 길이가 max_bytes 안에 들어올 때까지 줄임
        end = min(n, cursor + max_bytes // 3)
        while end > cursor + 1 and len(text[cursor:end].encode("utf-8")) > max_bytes:
            end -= 1
        # 가능하면 공백/마침표에서 자르기 (자연스러운 경계)
        for break_char in (". ", "。 ", "? ", "! ", "\n", " "):
            idx = text.rfind(break_char, cursor + max_bytes // 6, end)
            if idx > cursor:
                end = idx + len(break_char)
                break
        parts.append(Chunk(
            chunk_idx=0,
            text=text[cursor:end].strip(),
            page_start=chunk.page_start,
            page_end=chunk.page_end,
        ))
        cursor = end

    log.warning(
        f"청크 바이트 가드 발동 — 원본 {len(text.encode('utf-8'))}바이트 → "
        f"{len(parts)}개로 강제 분할 (page={chunk.page_start}~{chunk.page_end})"
    )
    return parts


def _split_oversized(chunk: Chunk) -> list[Chunk]:
    """MAX_CHUNK_TOKENS 초과 청크를 문장 경계에서 분할"""
    if chunk.token_count <= MAX_CHUNK_TOKENS:
        return [chunk]

    sentences = _split_sentences(chunk.text)
    sub_chunks = []
    current_text = ""
    current_tokens = 0

    for sent in sentences:
        sent_tokens = _estimate_tokens(sent)
        if current_tokens + sent_tokens > MAX_CHUNK_TOKENS and current_text:
            sub_chunks.append(Chunk(
                chunk_idx=0,  # 나중에 재번호
                text=current_text.strip(),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
            ))
            current_text = sent
            current_tokens = sent_tokens
        else:
            current_text += " " + sent if current_text else sent
            current_tokens += sent_tokens

    if current_text.strip():
        sub_chunks.append(Chunk(
            chunk_idx=0,
            text=current_text.strip(),
            page_start=chunk.page_start,
            page_end=chunk.page_end,
        ))

    return sub_chunks

def _split_sentences_with_offsets(text: str):
    raw_sentences = _split_sentences(text)

    result = []
    cursor = 0

    for sent in raw_sentences:
        start = text.find(sent, cursor)
        if start == -1:
            continue
        end = start + len(sent)

        result.append({
            "text": sent,
            "start": start,
            "end": end,
        })

        cursor = end

    return result

def _resolve_pages(sentences, page_map):
    if not page_map:
        return None, None

    pages = []
    for s in sentences:
        for pos in (s["start"], s["end"] - 1):
            page = page_map.get(pos)
            if page is not None:
                pages.append(page)

    if not pages:
        return None, None

    return min(pages), max(pages)

# ── 메인 청킹 함수 ──────────────────────────────────────
def semantic_chunk(
    text: str,
    embed_fn,
    *,
    page_map: dict[int, int] | None = None,
) -> list[Chunk]:
    """
    시맨틱 청킹 메인

    Args:
        text: 전체 텍스트
        embed_fn: 문장 리스트 → 임베딩 ndarray 반환 함수
        page_map: {문자 위치 → 페이지 번호} 매핑 (선택)

    Returns:
        Chunk 리스트
    """
    # 1. 줄바꿈 정규화 후 문장 분리
    text = _normalize_linebreaks(text)
    sentences = _split_sentences_with_offsets(text)
    if not sentences:
        return []

    log.info(f"문장 {len(sentences)}개 분리 완료")

    # 문장 수가 적으면 그냥 하나로 (바이트 가드는 마지막에 일괄 적용)
    if len(sentences) <= 5:
        single = Chunk(chunk_idx=0, text=text)
        parts = _split_by_bytes(single)
        for i, c in enumerate(parts):
            c.chunk_idx = i
        return parts

    # 2. 임베딩 계산
    embeddings = _compute_embeddings([s["text"] for s in sentences], embed_fn)
    log.info(f"임베딩 계산 완료: shape={embeddings.shape}")

    # 3. 의미 경계 탐지
    breakpoints = _find_breakpoints(embeddings)
    log.info(f"의미 경계 {len(breakpoints)}개 감지")

    # 4. 경계 기준 청크 생성
    bp_set = set(breakpoints)
    chunks = []
    current_sentences = []

    for i, sent in enumerate(sentences):
        current_sentences.append(sent)
        if i in bp_set or i == len(sentences) - 1:
            chunk_text = " ".join(s["text"] for s in current_sentences)
            page_start, page_end = _resolve_pages(current_sentences, page_map)
            chunks.append(Chunk(
                chunk_idx=len(chunks),
                text=chunk_text,
                page_start=page_start,
                page_end=page_end,
            ))
            current_sentences = []

    # 5. 크기 제약 적용
    # 작은 청크 병합
    chunks = _merge_small_chunks(chunks)

    # 큰 청크 분할 (토큰 기준 의미 분할)
    final_chunks = []
    for chunk in chunks:
        final_chunks.extend(_split_oversized(chunk))

    # 최종 바이트 가드 — 의미 분할로 안 잡힌 초대형 청크를 강제 분할
    # (VLM 출력처럼 마침표 없는 한 덩어리, 단일 초대형 문장 등)
    guarded: list[Chunk] = []
    for chunk in final_chunks:
        guarded.extend(_split_by_bytes(chunk))
    final_chunks = guarded

    # 재번호
    for i, chunk in enumerate(final_chunks):
        chunk.chunk_idx = i

    log.info(
        f"최종 청크 {len(final_chunks)}개 "
        f"(토큰 범위: {min(c.token_count for c in final_chunks)}"
        f"~{max(c.token_count for c in final_chunks)})"
    )

    return final_chunks