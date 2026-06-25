"""
paper_enricher.py — 논문 전용 보강 파이프라인

run_embed_index 에서 paper doc_type 시 호출:
  1. 초록(abstract)   — 헤더 패턴 매칭으로 추출
  2. 참고문헌(references) — 항목 패턴 기반 추출 (연속 비매칭 N줄 → stop)
  3. 키워드(keywords)  — 헤더 파싱 추출, 없으면 LLM 생성
  4. 목차(toc)        — 헤더 파싱 추출, 없으면 None (생성 안 함)
  5. 표              — 원본 마크다운 청크 + LLM 전체 서술 청크 (2개 per 표)
  6. 그림 설명         — MinIO figure bytes → VLM → [그림 설명] 청크

결과:
  - book.abstract / book.keyword / book.extra["references","toc"] → DB 저장 (호출자 책임)
  - MinIO artifacts/{book_id}/enrichment.json.gz
  - 반환 PaperEnrichment (보강 청크 리스트 포함)
"""
import asyncio
import base64
import gzip
import io
import json
import logging
import re
from dataclasses import dataclass, field

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)
cfg = get_settings()

# ── 초록 헤더 ────────────────────────────────────────────────
# VLM이 마크다운(## / **) 포함해서 추출하는 경우도 처리
_ABSTRACT_HEADER = re.compile(
    r'(?m)^\s*(?:[#*\-]+\s*)?'
    r'(?:초\s*록|Abstract|ABSTRACT'
    r'|요\s*약|국문\s*(?:초록|요약|abstract)'
    r'|영문\s*(?:초록|요약|abstract)'
    r'|한국어\s*(?:초록|요약)'
    r'|Korean\s*Abstract|English\s*Abstract'
    r'|Summary|SUMMARY)'
    r'\s*[:#*_\s]*$',
    re.IGNORECASE,
)

# 초록 끝 감지 — 다음 섹션 헤더
_ABSTRACT_END = re.compile(
    r'\n\s*(?:\d+[\.\)]\s+|[IVXivx]+\.\s+)?(?:서\s*론|Introduction|INTRODUCTION|'
    r'연구\s*(?:방법|배경|문제|목적)|Methods?|Background|결\s*론|Conclusion)',
    re.IGNORECASE,
)

# ── 참고문헌 헤더 ─────────────────────────────────────────────
_REF_HEADER = re.compile(
    r'(?m)^\s*(?:참\s*고\s*문\s*헌|References?|REFERENCES?|Bibliography|참\s*고\s*자\s*료)\s*$',
    re.IGNORECASE,
)

# 참고문헌 이후 종료 패턴 (저자정보·부록·감사·연락처)
_REF_STOP = re.compile(
    r'(?m)^\s*(?:저\s*자\s*(?:정보|소개)?|Author\s*(?:Information|s)?|AUTHOR|'
    r'부\s*록|Appendix|APPENDIX|감\s*사|Acknowledgment|연\s*락\s*처|Contact)',
    re.IGNORECASE,
)

# 참고문헌 항목 시작 패턴
_REF_ENTRY = re.compile(
    r'^(?:'
    r'\[\d+\]'                         # [1]
    r'|\d{1,3}\.'                       # 1.
    r'|[가-힣A-Z][가-힣A-Za-z\s,\-]{2,}\.\s+\(?(?:19|20)\d{2}\)?'  # 저자(연도)
    r'|[가-힣A-Z][가-힣A-Za-z\s,\-]{2,},\s+(?:19|20)\d{2}[,.]'     # 저자, 연도.
    r')'
)

# ── 키워드 헤더 ──────────────────────────────────────────────
# 인라인: "Keywords: A, B, C" 또는 블록(헤더만 있고 다음 줄에 키워드)
# VLM 마크다운 prefix (**Keywords:**, ## Keywords) 도 처리
_KW_INLINE = re.compile(
    r'(?m)^\s*(?:[#*\-]+\s*)?(?:Keywords?|KEYWORDS?|핵심어|주요어|핵심\s*어|주요\s*어|색인어|Key\s*Words?)\s*[*_]*\s*[:：]\s*[*_]*\s*(.+)$',
    re.IGNORECASE,
)
_KW_BLOCK_HEADER = re.compile(
    r'(?m)^\s*(?:[#*\-]+\s*)?(?:Keywords?|KEYWORDS?|핵심어|주요어|핵심\s*어|주요\s*어|색인어|Key\s*Words?)\s*[*_]*\s*[:：]?\s*[*_]*\s*$',
    re.IGNORECASE,
)

# ── 목차 헤더 ────────────────────────────────────────────────
_TOC_HEADER = re.compile(
    r'(?m)^\s*(?:목\s*차|차\s*례|Contents?|CONTENTS?|Table\s+of\s+Contents?)\s*$',
    re.IGNORECASE,
)
# 목차 항목 — 번호·로마자·한글 순번으로 시작하거나 점선 포함
_TOC_ENTRY = re.compile(
    r'^(?:\d+[\.\)]|[IVXivxⅠ-Ⅸ가-힣]+[\.\)]\s|[\.\·\-]{3,}|.+(?:[\.\·\-]{3,}|\s{2,})\d+\s*$)',
)
_TOC_MAX_LINES = 60   # 목차가 이보다 길면 이상한 매칭 → stop

# ── 마크다운 표 ──────────────────────────────────────────────
_MD_TABLE = re.compile(
    r'(\|[^\n]+\|\n\s*\|[-:| ]+\|\n(?:\|[^\n]+\|\n?)+)',
    re.MULTILINE,
)

_MIN_TABLE_ROWS = 2   # 헤더·구분자 제외 최소 데이터 행
_MIN_TABLE_COLS = 2   # 최소 열 수

# 참고문헌 연속 비매칭 → stop 기준
_REF_MAX_CONSECUTIVE_NONMATCH = 4


# ── 데이터클래스 ─────────────────────────────────────────────

@dataclass
class TableChunk:
    context: str            # 표 앞 200자 맥락 (섹션 위치 파악용)
    table_md: str           # 원본 마크다운 (수치 손실 없이 그대로)
    description: str = ""   # LLM 전체 서술 (의미 기반 검색용, 실패 시 빈 문자열)


@dataclass
class FigureChunk:
    minio_key: str   # figures/{book_id}/p{N}_i{M}.jpg
    description: str  # VLM 설명


@dataclass
class PaperEnrichment:
    abstract: str | None = None
    keywords: list[str] = field(default_factory=list)   # 추출 or LLM 생성
    toc: list[str] = field(default_factory=list)         # 목차 항목 (없으면 빈 리스트)
    references: list[str] = field(default_factory=list)
    table_chunks: list[TableChunk] = field(default_factory=list)
    figure_chunks: list[FigureChunk] = field(default_factory=list)


# ── 1. 초록 추출 ─────────────────────────────────────────────

def extract_abstract(full_text: str) -> str | None:
    """헤더 매칭 후 다음 섹션 전까지 추출. 최대 2000자."""
    m = _ABSTRACT_HEADER.search(full_text)
    if not m:
        return None

    rest = full_text[m.end():]
    end_m = _ABSTRACT_END.search(rest)
    end = end_m.start() if end_m else min(len(rest), 2000)
    text = rest[:end].strip()

    if len(text) < 50:
        return None
    return text[:2000]


# ── 2. 키워드 추출 ───────────────────────────────────────────

def _split_keywords(raw: str) -> list[str]:
    """쉼표·세미콜론·슬래시로 분리, 빈 항목 제거."""
    return [kw.strip() for kw in re.split(r'[,;/，；]', raw) if kw.strip()]


def extract_keywords(full_text: str) -> list[str] | None:
    """Keywords:/핵심어: 헤더에서 추출. 인라인 형식 우선, 없으면 블록 형식."""
    # 인라인: "Keywords: A, B, C"
    m = _KW_INLINE.search(full_text)
    if m:
        kws = _split_keywords(m.group(1))
        return kws if kws else None

    # 블록: 헤더 다음 줄에 키워드
    m = _KW_BLOCK_HEADER.search(full_text)
    if not m:
        return None

    rest = full_text[m.end():]
    # 공백 줄 하나를 허용하고 첫 번째 비어있지 않은 줄 또는 연속된 키워드 줄 수집
    lines = rest.splitlines()
    kw_lines: list[str] = []
    for line in lines[:5]:  # 블록 키워드는 최대 5줄
        stripped = line.strip()
        if not stripped:
            if kw_lines:  # 이미 수집 중이면 종료
                break
            continue
        # 새 섹션 헤더처럼 보이면 중단
        if re.match(r'^(?:\d+[\.\)]|[A-Z가-힣]{2,}[\.\)]\s)', stripped):
            break
        kw_lines.append(stripped)

    if not kw_lines:
        return None
    raw = " ".join(kw_lines)
    kws = _split_keywords(raw)
    return kws if kws else None


# ── 3. 목차 추출 ─────────────────────────────────────────────

def extract_toc(full_text: str) -> list[str] | None:
    """목차/Contents 헤더 이후 항목 추출. 없거나 너무 짧으면 None."""
    m = _TOC_HEADER.search(full_text)
    if not m:
        return None

    rest = full_text[m.end():]
    lines = rest.splitlines()
    entries: list[str] = []
    consecutive_blank = 0

    for line in lines[:_TOC_MAX_LINES + 20]:
        stripped = line.strip()
        if not stripped:
            consecutive_blank += 1
            if consecutive_blank >= 3:
                break
            continue
        consecutive_blank = 0

        # 목차 항목인지 확인 — 점선·숫자·로마자 시작 또는 끝에 페이지 번호
        if (
            _TOC_ENTRY.match(stripped)
            or re.search(r'\.{3,}\s*\d+\s*$', stripped)   # "제목 ........ 5"
            or re.match(r'.+\s{3,}\d+\s*$', stripped)      # "제목         5"
        ):
            entries.append(stripped)
            if len(entries) >= _TOC_MAX_LINES:
                break
        else:
            # 목차가 아닌 본문 줄이 3줄 이상 연속이면 목차 끝
            if entries:
                break

    return entries if len(entries) >= 3 else None


# ── 4. 참고문헌 추출 ─────────────────────────────────────────

def extract_references(full_text: str) -> list[str]:
    """패턴 기반 항목 추출. 연속 비매칭 4줄 또는 종료 패턴 → stop."""
    m = _REF_HEADER.search(full_text)
    if not m:
        return []

    rest = full_text[m.end():]
    stop_m = _REF_STOP.search(rest)
    if stop_m:
        rest = rest[:stop_m.start()]

    lines = rest.splitlines()
    refs: list[str] = []
    current: list[str] = []
    consecutive_nonmatch = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if current:
                consecutive_nonmatch += 1
                if consecutive_nonmatch >= _REF_MAX_CONSECUTIVE_NONMATCH:
                    refs.append(" ".join(current))
                    current = []
                    break
            continue

        if _REF_ENTRY.match(stripped):
            if current:
                refs.append(" ".join(current))
            current = [stripped]
            consecutive_nonmatch = 0
        elif current:
            current.append(stripped)
            consecutive_nonmatch = 0
        else:
            consecutive_nonmatch += 1
            if consecutive_nonmatch >= _REF_MAX_CONSECUTIVE_NONMATCH:
                break

    if current:
        refs.append(" ".join(current))

    return refs[:200]


# ── 3. 마크다운 표 추출 (원본 그대로) ────────────────────────

def _extract_tables(full_text: str) -> list[tuple[str, str]]:
    """(context_before, table_md) 리스트 반환. 최소 크기 필터 적용."""
    results = []
    for m in _MD_TABLE.finditer(full_text):
        table_md = m.group(0).strip()
        lines = [ln for ln in table_md.split("\n") if ln.strip()]
        data_rows = sum(1 for ln in lines if ln.strip().startswith("|") and "---" not in ln) - 1
        if data_rows < _MIN_TABLE_ROWS:
            continue
        cols = len(lines[0].split("|")) - 2
        if cols < _MIN_TABLE_COLS:
            continue
        context = full_text[max(0, m.start() - 200):m.start()].strip()
        results.append((context, table_md))
    return results


# ── 4. LLM 표 전체 서술 ──────────────────────────────────────

async def _llm_chat(system: str, user: str, params: dict, timeout: float) -> str:
    payload = {
        "model": cfg.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **params,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{cfg.LLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def generate_keywords(title: str, text: str) -> list[str]:
    """추출 실패 시 LLM으로 키워드 생성. 쉼표 구분 문자열 반환 후 분리."""
    from services.prompts import get_prompt
    snippet = text[:800]  # abstract 또는 도입부 앞부분만
    tpl = get_prompt("paper_keywords")
    system, user, params = tpl.render(title=title, text=snippet)
    raw = await _llm_chat(system, user, params, timeout=cfg.PAPER_TABLE_INTERP_TIMEOUT)
    raw = re.sub(r'[#*`_\[\]>]+', '', raw)  # LLM 마크다운 제거
    return _split_keywords(raw)


async def interpret_table(title: str, context: str, table_md: str) -> str:
    from services.prompts import get_prompt
    tpl = get_prompt("paper_table_interp")
    system, user, params = tpl.render(title=title, context=context, table_markdown=table_md)
    return await _llm_chat(system, user, params, timeout=cfg.PAPER_TABLE_INTERP_TIMEOUT)


# ── 5. VLM 그림 설명 ─────────────────────────────────────────

async def describe_figure(title: str, img_bytes: bytes, img_fmt: str = "jpeg") -> str:
    img_b64 = base64.b64encode(img_bytes).decode()
    prompt = (
        f"학술논문 '{title}'의 그림입니다.\n"
        "이 그림이 보여주는 내용, 주요 수치, 패턴을 2-3문장으로 간결하게 설명하세요."
    )
    payload = {
        "model": cfg.VLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{img_fmt};base64,{img_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 256,
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=float(cfg.PAPER_FIGURE_VLM_TIMEOUT)) as client:
        resp = await client.post(f"{cfg.VLM_BASE_URL}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# ── 6. MinIO 그림 목록 / 로드 ────────────────────────────────

def _list_figure_keys(book_id: str, minio_client) -> list[str]:
    try:
        objs = minio_client.list_objects(
            cfg.MINIO_BUCKET,
            prefix=f"figures/{book_id}/",
            recursive=True,
        )
        return sorted(o.object_name for o in objs)
    except Exception as e:
        log.warning(f"[{book_id}] MinIO 그림 목록 조회 실패: {e}")
        return []


def _load_figure_bytes(key: str, minio_client) -> bytes | None:
    try:
        resp = minio_client.get_object(cfg.MINIO_BUCKET, key)
        data = resp.read()
        resp.close()
        resp.release_conn()
        return data
    except Exception as e:
        log.warning(f"MinIO 그림 로드 실패 {key}: {e}")
        return None


# ── 7. MinIO 아티팩트 저장 ──────────────────────────────────

def save_enrichment_artifact(book_id: str, enrichment: PaperEnrichment, minio_client) -> None:
    payload = {
        "abstract": enrichment.abstract,
        "keywords": enrichment.keywords,
        "toc": enrichment.toc,
        "references": enrichment.references,
        "table_chunks": [
            {"context": t.context, "table_md": t.table_md, "description": t.description}
            for t in enrichment.table_chunks
        ],
        "figure_chunks": [
            {"minio_key": f.minio_key, "description": f.description}
            for f in enrichment.figure_chunks
        ],
    }
    data = gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    try:
        minio_client.put_object(
            cfg.MINIO_BUCKET,
            f"artifacts/{book_id}/enrichment.json.gz",
            io.BytesIO(data),
            length=len(data),
            content_type="application/gzip",
        )
    except Exception as e:
        log.warning(f"[{book_id}] enrichment 아티팩트 MinIO 저장 실패: {e}")


# ── 8. 메인 엔트리 ─────────────────────────────────────────

async def enrich_paper(
    book_id: str,
    title: str,
    full_text: str,
    minio_client,
) -> PaperEnrichment:
    """논문 보강 파이프라인 — 초록·참고문헌·표·그림 처리."""
    if not full_text or len(full_text) < 200:
        return PaperEnrichment()

    abstract = extract_abstract(full_text)
    references = extract_references(full_text)
    toc = extract_toc(full_text)

    # 키워드: 추출 우선, 없으면 LLM 생성 (abstract 또는 본문 앞부분 사용)
    keywords = extract_keywords(full_text)
    kw_source = "추출"
    if not keywords:
        kw_source = "LLM"
        try:
            seed_text = abstract or full_text[:800]
            keywords = await generate_keywords(title, seed_text)
        except Exception as e:
            log.warning(f"[{book_id}] 키워드 LLM 생성 실패: {e}")
            keywords = []

    log.info(
        f"[{book_id}] paper enrichment — 초록: {'있음' if abstract else '없음'}, "
        f"키워드: {len(keywords)}개 ({kw_source}), "
        f"목차: {'있음' if toc else '없음'}, 참고문헌: {len(references)}건"
    )

    # 표 — 원본 마크다운 + LLM 전체 서술 병렬 생성
    tables = _extract_tables(full_text)[: cfg.PAPER_MAX_TABLES_PER_DOC]
    table_chunks: list[TableChunk] = []
    if tables:
        sem = asyncio.Semaphore(cfg.LLM_SECTION_CONCURRENCY)

        async def _build_table_chunk(ctx: str, md: str) -> TableChunk:
            async with sem:
                try:
                    desc = await interpret_table(title, ctx, md)
                except Exception as e:
                    log.warning(f"[{book_id}] 표 LLM 서술 실패 (원본만 유지): {e}")
                    desc = ""
            return TableChunk(context=ctx, table_md=md, description=desc)

        table_chunks = list(await asyncio.gather(*[_build_table_chunk(c, t) for c, t in tables]))
        ok = sum(1 for tc in table_chunks if tc.description)
        log.info(f"[{book_id}] 표 처리: {len(table_chunks)}건 (LLM 서술 성공 {ok}건)")

    # 그림 설명 (VLM, 최대 PAPER_MAX_FIGURES_PER_DOC)
    figure_chunks: list[FigureChunk] = []
    fig_keys = _list_figure_keys(book_id, minio_client)[: cfg.PAPER_MAX_FIGURES_PER_DOC]
    if fig_keys:
        async def _describe(key: str) -> FigureChunk | None:
            img_bytes = await asyncio.get_event_loop().run_in_executor(
                None, _load_figure_bytes, key, minio_client
            )
            if not img_bytes:
                return None
            ext = key.rsplit(".", 1)[-1].lower()
            fmt = "png" if ext == "png" else "jpeg"
            try:
                desc = await describe_figure(title, img_bytes, fmt)
                return FigureChunk(minio_key=key, description=desc)
            except Exception as e:
                log.warning(f"[{book_id}] 그림 설명 실패 {key}: {e}")
                return None

        fig_results = await asyncio.gather(*[_describe(k) for k in fig_keys])
        figure_chunks = [r for r in fig_results if r is not None]
        log.info(f"[{book_id}] 그림 설명: {len(figure_chunks)}/{len(fig_keys)}건 성공")

    return PaperEnrichment(
        abstract=abstract,
        keywords=keywords,
        toc=toc or [],
        references=references,
        table_chunks=table_chunks,
        figure_chunks=figure_chunks,
    )
