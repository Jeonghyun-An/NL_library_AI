# round07 적재 파이프라인 보강 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영 적재(`kci-full-236k`, 남은 약 11.3만 건)의 병목 두 곳(embed 1칸 안의 보강 LLM 대기·VLM 페이지 순차)을 풀고, 데이터를 잃거나 버리는 결함과 중복 체인이 논문 본문을 덮는 경로를 고친다 — spec `docs/superpowers/specs/2026-10-01-round07-ingest-pipeline-fix-design.md` 의 18개 항목.

**Architecture:** 단계 구조(extract → summarize → embed_index → finalize, Celery 체인)는 그대로 둔다. 보강 LLM 을 summarize 단계로 옮기고, 추출의 페이지 판정을 순수 함수 모듈(`page_routing.py`)로 빼서 테스트하고, 디스패처가 체인마다 실행 토큰을 붙여 옛 체인을 끊는다. 기존 테이블 칼럼은 바꾸지 않는다(상태는 `ingest_job_items.meta` JSON).

**Tech Stack:** Python 3.11, Celery(Redis), SQLAlchemy(Postgres), httpx, PyMuPDF(fitz), opendataloader(ODL), vLLM(gemma-3-12b · qwen3-vl-8b), pytest.

---

## 실행 전 알아 둘 것

- **작업 위치:** `C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07` (브랜치 `feat/round07-ingest-pipeline-fix`). 저장소 루트 폴더(round05a 세션)는 건드리지 않는다.
- **테스트 실행:** `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/<파일> -q`. PATH 의 `python`(시스템 venv)에 pytest·sqlalchemy·httpx·fitz 가 있다. torch·FlagEmbedding·pymilvus·openpyxl 은 없다 — 그것들을 끌어오는 모듈(`embedder`·`reranker`·`indexer`·`search.pipeline`)은 함수 안에서 import 한다(함정 13). 전체: `python -m pytest -q --continue-on-collection-errors` — 이 PC 에서는 `test_book_chat`·`test_build_manifest`·`test_loaders` 3개가 수집 단계에서 오류가 난다(FlagEmbedding·openpyxl 미설치, 원래 상태와 같음). 기준선: 890 passed + 수집 오류 3.
- **커밋:** `[Fix]`·`[Feat]`·`[Refactor]`·`[Chore]`·`[Docs]` 접두어, 한국어 본문, `Co-Authored-By` 트레일러 금지.
- **운영:** 본 잡은 paused·in-flight 0. 코드 배포는 마지막 작업의 절차대로 사용자가 한다. 이 계획의 어떤 단계도 운영에 쓰기 요청을 보내지 않는다.
- **함정:** `docs/ops/recurring-gotchas.md` 12·13·14·15·16·17·19·20번.

## 공통 계약 (모든 작업이 이 이름을 쓴다)

**설정 키** — `app/core/config.py` 에 Task 0 이 한꺼번에 더하고, `docker-compose.yml` 의 `x-common-env` 에 `${이름:-기본값}` 으로 선언한다(Portainer 는 선언 없는 env 를 무시한다).

| 키 | 타입·기본값 | 쓰는 곳 |
|---|---|---|
| `VLM_PAGE_CONCURRENCY` | int 2 | 추출: 문서 안 OCR 동시 요청 수 |
| `INGEST_EXTRACT_DEADLINE` | int 2700 | 추출 전체 asyncio 데드라인(초) |
| `INGEST_STAGE_TIMEOUT_EXTRACT` | int 3600 (config 기본 1800 → 3600, compose 기본 14400 → 3600) | stale 판정 |
| `INGEST_RETRY_BACKOFF_SECONDS` | str "120,600" | 자동 재시도 백오프(attempt 1 → 120초, 2 → 600초) |
| `LLM_RETRY_ATTEMPTS` | int 3 | `llm_client` 재시도 횟수(첫 시도 포함) |
| `LLM_RETRY_BACKOFF_SECONDS` | str "2,8" | `llm_client` 재시도 간격 |
| `SCAN_REPEAT_LINE_RATIO` | float 0.6 | 머리말·꼬리말·스탬프 판정: 쪽의 60% 이상에 되풀이되는 줄 |
| `SCAN_SHORT_PAGE_RATIO` | float 0.5 | 짧은 쪽 비율이 이보다 크면 문서 단위 스캔본 |
| `SCAN_MIN_PAGES` | int 3 | 문서 단위 스캔 판정 최소 쪽수 |
| `ODL_TIMEOUT_BASE_SECONDS` | float 10.0 (처음 5.0 — Task 5 실행 메모) | ODL 타임아웃 = max(기본, 쪽수 × 쪽당), 시도마다 추출 데드라인까지 남은 시간을 넘지 않는다 |
| `ODL_TIMEOUT_PER_PAGE_SECONDS` | float 1.5 (처음 0.5) | 위 |
| `ODL_IMAGE_OUTPUT` | str "off" — `off`·`embedded`·`external` 만(설정을 읽을 때 검증) | ODL `image_output` |

(쪽 면적 이미지 규칙과 `SCAN_IMAGE_AREA_RATIO` 는 쓰지 않는다 — 이미지 표지를 다시 VLM 으로 보내 d85df93 의 표지 수정을 되돌린다. spec 7번.)

**`ingest_job_items.meta` 키**

| 키 | 값 | 쓰는 곳 |
|---|---|---|
| `run_token` | str(uuid4 hex) | 디스패처가 체인마다 새로 적음 → `_run_stage` 가 대조 |
| `stage_running` | str 단계 이름 또는 null | `_run_stage` 시작 때 적고 끝날 때 null |
| `stage_started_at` | ISO8601 UTC 문자열 | 위 |
| `vlm_truncated` | int | 추출: length 로 끝난 OCR 쪽 수 — 되풀이 꼬리를 걷어 내고 채택했거나 퇴화 출력이라 버리고 ODL 결과를 쓴 쪽 |
| `extract_deadline_hit` | bool | 추출 데드라인에 걸림 |
| `forced_ocr` | bool | 섹션 0개로 강제 OCR 재추출을 했음 |
| `ocr_errors` | int | VLM 요청 실패 수(연결·타임아웃·5xx, 400·413·422 밖의 4xx — 다시 하면 달라질 수 있거나 401·403·404 처럼 서버 전체 설정 문제인 것). 퇴화 출력(`vlm_truncated`)·렌더링 실패(`render_errors`)·거절(`ocr_rejected`)은 세지 않는다 |
| `ocr_rejected` | int | VLM 이 HTTP 400·413·422 로 거절한 쪽 수(그 쪽만의 문제 — 쪽 이미지가 `max-model-len` 을 넘는 등) — 다시 보내지 않고, 섹션 0개 판정에서 `vlm_error` 로 보내지 않는다. 거절로 섹션 0개·빈 본문이면 `no_text` 이고 `last_error` 에 `거절` 이 남는다 (최종 리뷰 반영) |
| `render_errors` | int | 쪽 이미지 렌더링 실패 수(fitz `get_pixmap` 예외 — 다시 해도 같다) |
| `odl_fallback` | str 또는 null | 추출: `resaved`(원본 ODL 실패, fitz 재저장본으로 변환)·`fitz`(둘 다 실패, fitz 텍스트) — 정상이면 null (Task 5 실행 메모) |
| `odl_seconds` | float | 추출: ODL 시도를 모두 더한 시간(0.1초) |
| `enrich_source` | str | embed: `artifact`(요약 단계의 보강을 읽음)·`inline`(embed 가 보강 LLM 을 다시 돌림)·`none`(논문 아님·보강 꺼짐) (Task 6) |
| `reduce_levels`·`reduce_groups`·`reduce_fallback` | int·int·bool | 마무리: 계층 요약 단계 수(0 = 합치기만)·묶음 수·균등 샘플링으로 돌아감 (Task 8) |

**오류 그룹(`error_group`)**: 기존 `not_found`·`extract_empty`·`llm_error`·`llm_timeout`·`milvus_error`·`minio_error`·`vlm_error`·`stale`·`artifact_missing`·`empty_body`·`unknown` 에 더해 `no_text`(결정적 — 자동 재시도 안 함).

**함수·시그니처**

```python
# app/services/llm_client.py  (Task 1)
@dataclass
class LLMResult:
    content: str
    finish_reason: str | None

async def chat_full(messages: list[dict], *, params: dict | None = None, timeout: float = 120.0) -> LLMResult: ...
async def chat(messages: list[dict], *, params: dict | None = None, timeout: float = 120.0) -> str:  # = (await chat_full(...)).content
    ...

# app/services/ingestion/page_routing.py  (Task 3 — 새 파일, fitz·httpx import 금지)
def body_len(text: str) -> int: ...                       # [그림]·<br>·구조 문자 뺀 글자 수
def collapse_br_runs(text: str) -> str: ...               # <br> 3개 이상 연속 → <br> 하나(줄바꿈으로 바꾸면 표 행이 쪼개진다 — Task 3 리뷰)
def repeated_lines(page_texts: list[str], ratio: float, max_len: int = 40) -> set[str]: ...
def strip_lines(text: str, lines: set[str]) -> str: ...
def is_scan_document(short_flags: list[bool], *, min_pages: int, ratio: float) -> bool: ...
def short_page_needs_ocr(*, fitz_len_stripped: int, fitz_len_raw: int, doc_is_scan: bool, force: bool, min_chars: int) -> tuple[bool, str]: ...  # fitz_len_raw 0 이면 지금처럼 OCR
def trim_repetition(text: str) -> tuple[str, bool]: ...   # (다듬은 텍스트, 퇴화 출력인가)

# app/services/ingestion/extractor.py  (Task 3·4·5)
async def extract_text(file_path, book_id, *, file_bytes=None, force_ocr_short_pages: bool = False, deadline_s: float | None = None) -> ExtractionResult: ...
# deadline_s: 추출 전체 데드라인(초, None 이면 INGEST_EXTRACT_DEADLINE) — 섹션 0개 강제 재추출은 첫 추출이 남긴 시간(하한 60초)을 넘긴다
# ExtractionResult 에 필드 추가: vlm_truncated: int = 0, deadline_hit: bool = False, ocr_errors: int = 0,
#   render_errors: int = 0, short_kept: int = 0 (원래 짧은 쪽으로 ODL 결과를 채택한 쪽 수 — 0 이면 섹션 0개 재추출을 해도 같다),
#   odl_fallback: str | None = None ("resaved"·"fitz"), odl_seconds: float = 0.0 (Task 5 실행 메모)

# app/services/ingestion/paper_enricher.py  (Task 6)
async def enrich_paper(book_id, title, full_text, minio_client, *, sem: asyncio.Semaphore | None = None) -> PaperEnrichment: ...
def save_enrichment_artifact(book_id: str, enrichment: PaperEnrichment, minio_client, *, run_token: str | None = None) -> None: ...
def load_enrichment_artifact(book_id: str, minio_client, *, run_token: str | None = None) -> PaperEnrichment | None: ...  # 토큰이 양쪽에 다 있는데 다르면 None
def delete_enrichment_artifact(book_id: str, minio_client) -> None: ...  # run_summarize 가 보강 전에 옛 아티팩트를 지움
def trim_to_last_sentence(text: str) -> str: ...

# app/services/ingestion/stages.py
@dataclass
class StageContext:  # 필드 추가 (Task 2)
    ...
    item_meta: dict = field(default_factory=dict)

# app/services/ingestion/summarizer.py  (Task 8)
async def reduce_section_summaries(title: str, author: str, section_summaries: list[str], doc_type: str = "book", *, stats: ReduceStats | None = None) -> str: ...

# app/workers/job_runtime.py  (Task 2)
def build_item_chain(item_stage: str, item_id: int, run_token: str | None = None): ...
def _run_stage(stage_name: str, item_id: int, celery_task_id: str | None, run_token: str | None = None) -> dict: ...
# 단계 태스크: def stage_extract(self, item_id: int, run_token: str | None = None) — 나머지 셋도 같음
```

## 파일 구조

| 파일 | 맡는 일 | 작업 |
|---|---|---|
| `app/core/config.py` | 새 설정 키 | 0 |
| `docker-compose.yml` | env 선언, `celery-control` 추가, `celery-cpu` 큐에서 `q_control` 제거, 추출 타임아웃 기본값 | 0 |
| `app/workers/celery_app.py` | beat `expires` | 0 |
| `app/services/llm_client.py` | `chat_full`·재시도 | 1 |
| `app/workers/job_runtime.py` | 실행 토큰·체인 정지·stale 판정 분리·백오프·재시도 불가 그룹·체크포인트 되돌림 | 2 |
| `app/services/ingestion/stages.py` | `StageContext.item_meta`, 추출 섹션 0 처리, embed 아티팩트 가드, 보강 이동, 마무리 병렬·표지 끄기 | 2·4·6·8 |
| `app/services/ingestion/page_routing.py` (새) | 페이지 판정 순수 함수 | 3 |
| `app/services/ingestion/extractor.py` | 라우팅 적용·`<br>`·강제 OCR·VLM 잘림·페이지 병렬·데드라인·ODL 타임아웃 | 3·4·5 |
| `app/services/ingestion/paper_enricher.py` | 세마포어 인자·아티팩트 로더·표 해석 잘림 다듬기 | 6 |
| `app/domains/nl_library/prompts/paper_table_interp.yaml` | 표 해석 프롬프트·max_tokens | 6 |
| `app/services/ingestion/chunker.py` | 문장 5개 이하 분기 상한·줄바꿈 폴백 | 7 |
| `app/services/ingestion/summarizer.py` | 계층 요약 | 8 |
| `app/domains/nl_library/prompts/section_group_summary.yaml` (새) | 중간 요약 프롬프트 | 8 |
| `app/api/ingest_jobs.py` | ETA 24시간·paused·영구 실패 제외, 실패 그룹 대표 메시지 | 9 |
| `scripts/bulk_ingest/select_near_empty_items.py` (새) | 빈 본문 완료 아이템 선정(읽기 전용) | 10 |
| `scripts/bulk_ingest/build_canary_manifest.py` (새) | 카나리 매니페스트 | 10 |
| `research/round07-ingest-regression/` (새) | 실제 PDF 라우팅 회귀(1회성) | 11 |
| `docs/ops/bulk_ingest_runbook.md`·`docs/ops/recurring-gotchas.md`·`docs/roadmap/00_status.md` | 배포·카나리·재처리 절차, 함정 갱신 | 12 |

## 작업 순서

0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12. 0 이 설정 키를 먼저 만들고, 1 의 `chat_full` 을 6 이 쓰고, 3 의 `page_routing` 을 4·5·11 이 쓴다. 같은 파일을 고치는 작업(2·4·6·8 의 `stages.py`, 3·4·5 의 `extractor.py`)은 앞 작업이 커밋된 뒤에 시작한다.

## 작업

### Task 0: 설정 키·compose·beat

> **실행 메모(2026-10-02, Task 5 리뷰 반영):** compose 에서 ODL 을 돌리는 `fastapi`·`celery-worker`·`celery-cpu` 에 `init: true` 를 더했고(97ca88c), `ODL_IMAGE_OUTPUT` 은 `Literal["off", "embedded", "external"]` 로 검증한다(1a56e93). 아래 블록의 ODL 타임아웃 기본값(5.0·0.5)은 첫 구현 값이다 — 사용자 결정(2026-10-02)으로 10.0·1.5 로 올렸다(9cc502d, config·compose — Task 5 실행 메모). 공통 계약 표는 지금 값이다.

**왜:** 다른 작업이 쓸 설정 키를 먼저 한꺼번에 만든다(공통 계약 표). Portainer 는 compose 에 `${이름:-기본값}` 선언이 없는 스택 env 를 무시하므로 `x-common-env` 선언도 같이 한다. 제어 큐(`q_control`: 디스패치·정리·딥리서치 회수)를 추출 워커에서 떼어 새 경량 워커가 받고, beat 틱에 `expires` 를 둔다(spec 6번). 추출 stale 판정은 3600초로 맞춘다(spec 16번 — 추출 데드라인 2700초 위, Celery `visibility_timeout` 7200초 아래).

**Files:**
- Modify: `app/core/config.py` (LLM 묶음 `LLM_SECTION_CONCURRENCY` 아래, 대량 인덱싱 잡 묶음 `INGEST_STAGE_TIMEOUT_EXTRACT`, 텍스트 추출 묶음 `VLM_MAX_PAGES_PER_DOC` 아래)
- Modify: `docker-compose.yml` (`x-common-env` 의 LLM·텍스트 추출·대량 인덱싱 잡 묶음, `gemma` 의 `--max-num-seqs` 위 주석, `celery-cpu` 의 `command`, 새 서비스 `celery-control`, `celery-llm` 머리 주석)
- Modify: `app/workers/celery_app.py` (`beat_schedule`)
- Create: `app/tests/test_ingest_settings.py`
- Create: `app/tests/test_celery_schedule.py`

**알아 둘 것:**
- 새 키는 공통 계약 표의 11개다. `SCAN_IMAGE_AREA_RATIO` 는 만들지 않는다 — 쪽 면적 이미지 규칙을 쓰지 않는다(spec 7번, 표지 되돌림 방지).
- 문자열 키(`INGEST_RETRY_BACKOFF_SECONDS` "120,600"·`LLM_RETRY_BACKOFF_SECONDS` "2,8")는 config 에서 `str` 로 둔다. 쉼표를 나누는 일은 쓰는 쪽(Task 1·2)이 한다. compose 의 `${LLM_RETRY_BACKOFF_SECONDS:-2,8}` 은 블록 매핑의 평문 값이라 쉼표가 그대로 문자열에 남는다(`docker compose config` 로 `'2,8'` 확인).
- `celery-control` 은 `celery-cpu` 를 본떴다. 같은 이미지·`x-common-env`·네트워크. GPU 예약·`shm_size`·`extra_hosts`·모델 캐시는 없다. 볼륨은 `/data/nl-lib/data:/app/data:rw` 하나다 — `cleanup_temp_files` 가 `/app/data/downloads` 를 지운다. 같은 정리 태스크의 Milvus flush 는 네트워크만 쓴다.
- `app/workers/job_runtime.py:55` 의 "visibility_timeout 의 2배" 주석(spec 16번)은 이 작업에서 고치지 않는다 — 그 파일은 Task 2 가 고친다.
- 기존 파일은 **Edit 도구로** 고친다. 이 worktree 의 파일은 CRLF 다(`core.autocrlf=true`). Edit 도구는 원래 줄바꿈을 지킨다. 새 파일의 줄바꿈은 커밋 때 git 이 맞춘다.
- `x-common-env` 를 고치면 그것을 물고 있는 앱 서비스가 배포 때 전부 재생성된다(함정 16번). 배포는 Task 12 의 런북 §9 절차로 사용자가 한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_ingest_settings.py` (새 파일, 전체):

```python
"""round07 적재 설정 — config 기본값과 docker-compose.yml 선언·워커 큐.

Portainer 는 compose 에 `${이름:-기본값}` 선언이 없는 스택 env 를 무시한다. 그래서 새 설정은
config 와 x-common-env 양쪽에 같은 기본값으로 있어야 한다.
"""
import re
from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

# 공통 계약의 설정 키 — 이름·타입·기본값
ROUND07_DEFAULTS = {
    "VLM_PAGE_CONCURRENCY": 2,
    "INGEST_EXTRACT_DEADLINE": 2700,
    "INGEST_STAGE_TIMEOUT_EXTRACT": 3600,
    "INGEST_RETRY_BACKOFF_SECONDS": "120,600",
    "LLM_RETRY_ATTEMPTS": 3,
    "LLM_RETRY_BACKOFF_SECONDS": "2,8",
    "SCAN_REPEAT_LINE_RATIO": 0.6,
    "SCAN_SHORT_PAGE_RATIO": 0.5,
    "SCAN_MIN_PAGES": 3,
    "ODL_TIMEOUT_BASE_SECONDS": 5.0,
    "ODL_TIMEOUT_PER_PAGE_SECONDS": 0.5,
    "ODL_IMAGE_OUTPUT": "off",
}


def _fresh_settings(monkeypatch):
    from core.config import Settings

    for key in ROUND07_DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    return Settings(_env_file=None)


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _queues(command) -> set[str]:
    if not isinstance(command, str):
        return set()
    args = command.split()
    return set(args[args.index("-Q") + 1].split(",")) if "-Q" in args else set()


def test_round07_settings_have_contract_defaults(monkeypatch):
    s = _fresh_settings(monkeypatch)
    for key, expected in ROUND07_DEFAULTS.items():
        value = getattr(s, key)
        assert value == expected and type(value) is type(expected), f"{key}={value!r}"


def test_extract_deadline_ends_before_stale_timeout(monkeypatch):
    # 추출은 데드라인에서 스스로 멈추고 결과를 남긴다 — stale 판정이 그보다 먼저 오면 안 된다
    s = _fresh_settings(monkeypatch)
    assert s.INGEST_EXTRACT_DEADLINE < s.INGEST_STAGE_TIMEOUT_EXTRACT


def test_common_env_declares_round07_keys_with_config_defaults():
    env = _compose()["x-common-env"]
    for key, default in ROUND07_DEFAULTS.items():
        value = str(env.get(key))
        m = re.fullmatch(r"\$\{" + key + r":-(.*)\}", value)
        assert m, f"{key}: x-common-env 에 ${{{key}:-기본값}} 으로 선언해야 한다 (지금 {value!r})"
        assert type(default)(m.group(1)) == default, f"{key}: compose 기본값 {m.group(1)!r}"


def test_control_worker_takes_q_control_without_gpu():
    services = _compose()["services"]
    ctl = services["celery-control"]
    cpu = services["celery-cpu"]
    assert ctl["container_name"] == "nl-lib-celery-control"
    assert ctl["image"] == cpu["image"]
    assert ctl["networks"] == cpu["networks"]
    assert ctl["command"] == "celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q q_control"
    assert "deploy" not in ctl  # GPU 예약 없음
    # 정리 태스크(cleanup_temp_files)가 /app/data/downloads 를 지운다 — 데이터 볼륨만 단다
    assert ctl["volumes"] == ["/data/nl-lib/data:/app/data:rw"]
    assert ctl["environment"]["PYTHONPATH"] == "/app"
    assert ctl["environment"]["DB_HOST"] == "postgres"  # x-common-env 를 물고 있다


def test_q_control_has_a_single_consumer():
    services = _compose()["services"]
    consumers = [name for name, svc in services.items() if "q_control" in _queues(svc.get("command"))]
    assert consumers == ["celery-control"]
    assert _queues(services["celery-cpu"]["command"]) == {"q_cpu"}
```

`app/tests/test_celery_schedule.py` (새 파일, 전체):

```python
"""workers/celery_app.py — beat 일정의 expires 와 visibility_timeout.

celery 는 로컬 venv 에 없다. 더미 Celery 로 celery_app 을 새로 import 해 conf 만 본다
(test_research_tasks.py 와 같은 방식 — 함정 13번).
"""
import importlib
import re
import sys
import types
from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

# 각 주기보다 짧게 — 늦게 받은 옛 틱은 버린다
EXPECTED_EXPIRES = {
    "dispatch-job-items": 25,
    "cleanup-temp-files": 3000,
    "reap-stale-research": 500,
}


class _FakeConf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _FakeCelery:
    def __init__(self, *a, **kw):
        self.conf = _FakeConf()

    def task(self, *a, **kw):
        def _decorator(fn):
            return fn
        return _decorator


@pytest.fixture
def conf(monkeypatch):
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _FakeCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)
    # 앞 테스트가 다른 더미로 import 해 둔 celery_app 을 물려받지 않는다 — 끝나면 원래대로 되돌린다
    monkeypatch.setattr(importlib.import_module("workers"), "celery_app", None, raising=False)
    monkeypatch.setitem(sys.modules, "workers.celery_app", None)
    del sys.modules["workers.celery_app"]
    return importlib.import_module("workers.celery_app").celery_app.conf


def test_beat_ticks_expire_before_the_next_tick(conf):
    schedule = conf.beat_schedule
    assert set(schedule) == set(EXPECTED_EXPIRES)
    for name, entry in schedule.items():
        expires = entry["options"]["expires"]
        assert expires == EXPECTED_EXPIRES[name], name
        assert 0 < expires < entry["schedule"], name


def test_compose_extract_stale_timeout_is_inside_visibility_timeout(conf):
    # 실행 중인 추출 메시지는 visibility_timeout 이 지나면 재전달된다 — stale 판정이 그 안쪽이어야 한다
    env = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["x-common-env"]
    m = re.fullmatch(r"\$\{INGEST_STAGE_TIMEOUT_EXTRACT:-(\d+)\}", env["INGEST_STAGE_TIMEOUT_EXTRACT"])
    assert int(m.group(1)) < conf.broker_transport_options["visibility_timeout"]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_ingest_settings.py tests/test_celery_schedule.py -q`

Expected: `7 failed`. 이유:
- `test_round07_settings_have_contract_defaults` — `AttributeError: 'Settings' object has no attribute 'VLM_PAGE_CONCURRENCY'`
- `test_extract_deadline_ends_before_stale_timeout` — `AttributeError: 'Settings' object has no attribute 'INGEST_EXTRACT_DEADLINE'`
- `test_common_env_declares_round07_keys_with_config_defaults` — `AssertionError: VLM_PAGE_CONCURRENCY: x-common-env 에 ${VLM_PAGE_CONCURRENCY:-기본값} 으로 선언해야 한다 (지금 'None')`
- `test_control_worker_takes_q_control_without_gpu` — `KeyError: 'celery-control'`
- `test_q_control_has_a_single_consumer` — `assert ['celery-cpu'] == ['celery-control']`
- `test_beat_ticks_expire_before_the_next_tick` — `KeyError: 'options'`
- `test_compose_extract_stale_timeout_is_inside_visibility_timeout` — `assert 14400 < 7200`

- [ ] **Step 3: `app/core/config.py` — 새 키**

`app/core/config.py` — 교체 전:

```python
    # 섹션 요약 등 태스크 내부 동시 LLM 호출 수
    # (글로벌 동시 LLM = celery-llm concurrency × 이 값 ≤ vLLM max-num-seqs)
    LLM_SECTION_CONCURRENCY: int = 4
```

교체 후:

```python
    # 섹션 요약 등 태스크 내부 동시 LLM 호출 수
    # (글로벌 동시 LLM = celery-llm concurrency × 이 값 ≤ vLLM max-num-seqs)
    # 요약 단계는 섹션 요약과 논문 보강(표 해석 등)의 LLM 호출이 이 세마포어 하나를 나눠 쓴다.
    LLM_SECTION_CONCURRENCY: int = 4
    # llm_client 재시도 — 횟수는 첫 시도 포함, 간격은 쉼표로 이은 초(n번째 실패 뒤 n번째 값)
    LLM_RETRY_ATTEMPTS: int = 3
    LLM_RETRY_BACKOFF_SECONDS: str = "2,8"
```

`app/core/config.py` — 교체 전:

```python
    # 단계별 타임아웃(초) — 초과 시 stale 판정 후 재디스패치
    INGEST_STAGE_TIMEOUT_EXTRACT: int = 1800
```

교체 후:

```python
    # 자동 재시도 백오프(초, 쉼표로 이음) — attempt 1 이면 첫 값, 2 면 둘째 값만큼 지난 뒤 다시 집는다
    INGEST_RETRY_BACKOFF_SECONDS: str = "120,600"
    # 추출 전체 asyncio 데드라인(초) — 넘으면 남은 쪽은 ODL 결과로 채택한다
    INGEST_EXTRACT_DEADLINE: int = 2700
    # 단계별 타임아웃(초) — 초과 시 stale 판정 후 재디스패치.
    # 추출은 데드라인(INGEST_EXTRACT_DEADLINE) 위, Celery visibility_timeout(7200) 아래.
    INGEST_STAGE_TIMEOUT_EXTRACT: int = 3600
```

`app/core/config.py` — 교체 전:

```python
    VLM_MAX_PAGES_PER_DOC: int = 60
```

교체 후:

```python
    VLM_MAX_PAGES_PER_DOC: int = 60
    # 문서 하나 안에서 동시에 보내는 OCR 요청 수 (추출 워커 4 × 2 = VLM max-num-seqs 8)
    VLM_PAGE_CONCURRENCY: int = 2
    # 스캔본 판정(문서 단위만 — 쪽 단위 규칙은 표지·간지를 다시 VLM 으로 보낸다).
    # 머리말·꼬리말·스탬프 = 문서 쪽의 이 비율 이상에 되풀이되는 짧은 줄 — fitz 쪽 길이에서 뺀다
    SCAN_REPEAT_LINE_RATIO: float = 0.6
    # 짧은 쪽 비율이 이보다 크면 스캔본 (SCAN_MIN_PAGES 쪽 이상 문서만)
    SCAN_SHORT_PAGE_RATIO: float = 0.5
    SCAN_MIN_PAGES: int = 3
    # ODL 타임아웃(초) = max(기본, 쪽수 × 쪽당)
    ODL_TIMEOUT_BASE_SECONDS: float = 5.0
    ODL_TIMEOUT_PER_PAGE_SECONDS: float = 0.5
    # ODL image_output — 운영 적재의 그림 저장이 0건이었다(2026-10-01 실측). 쓰이지 않는 인코딩을 끈다
    ODL_IMAGE_OUTPUT: str = "off"
```

- [ ] **Step 4: `docker-compose.yml` — env 선언·추출 stale 판정·제어 워커**

① LLM 재시도, ② 문서 안 OCR 병렬·스캔본 판정·ODL, ③ 재시도 백오프·추출 데드라인·추출 stale 판정(옛 주석 교체), ④ gemma 동시성 주석, ⑤ `celery-cpu` 는 `q_cpu` 만, ⑥ `celery-cpu` 바로 뒤에 `celery-control` 을 넣고 `celery-llm` 머리 주석을 고친다.

`docker-compose.yml` — 교체 전:

```yaml
  LLM_SECTION_CONCURRENCY: ${LLM_SECTION_CONCURRENCY:-4}
```

교체 후:

```yaml
  LLM_SECTION_CONCURRENCY: ${LLM_SECTION_CONCURRENCY:-4}
  # llm_client 재시도(첫 시도 포함 횟수, 실패 뒤 기다릴 초를 쉼표로)
  LLM_RETRY_ATTEMPTS: ${LLM_RETRY_ATTEMPTS:-3}
  LLM_RETRY_BACKOFF_SECONDS: ${LLM_RETRY_BACKOFF_SECONDS:-2,8}
```

`docker-compose.yml` — 교체 전:

```yaml
  VLM_TIMEOUT: ${VLM_TIMEOUT:-120}
```

교체 후:

```yaml
  VLM_TIMEOUT: ${VLM_TIMEOUT:-120}
  # 문서 안 OCR 동시 요청 — celery-cpu 4 × 2 = vllm --max-num-seqs 8
  VLM_PAGE_CONCURRENCY: ${VLM_PAGE_CONCURRENCY:-2}
  # 문서 단위 스캔본 판정(머리말·꼬리말·스탬프 줄 비율, 짧은 쪽 비율, 최소 쪽수)
  SCAN_REPEAT_LINE_RATIO: ${SCAN_REPEAT_LINE_RATIO:-0.6}
  SCAN_SHORT_PAGE_RATIO: ${SCAN_SHORT_PAGE_RATIO:-0.5}
  SCAN_MIN_PAGES: ${SCAN_MIN_PAGES:-3}
  # ODL 타임아웃 = max(기본, 쪽수 × 쪽당) 초, 이미지 출력(off = 인코딩 안 함)
  ODL_TIMEOUT_BASE_SECONDS: ${ODL_TIMEOUT_BASE_SECONDS:-5.0}
  ODL_TIMEOUT_PER_PAGE_SECONDS: ${ODL_TIMEOUT_PER_PAGE_SECONDS:-0.5}
  ODL_IMAGE_OUTPUT: ${ODL_IMAGE_OUTPUT:-off}
```

`docker-compose.yml` — 교체 전:

```yaml
  INGEST_MAX_ATTEMPTS: ${INGEST_MAX_ATTEMPTS:-3}
  # 30분 기본값은 대형 스캔 문서(632p 실측 210분)보다 짧아 정상 작업을 stale 로 오판,
  # 같은 문서를 3회까지 중복 실행시켰다(파일럿 2026-08-06). 실측 최악값 위로 올림.
  INGEST_STAGE_TIMEOUT_EXTRACT: ${INGEST_STAGE_TIMEOUT_EXTRACT:-14400}
```

교체 후:

```yaml
  INGEST_MAX_ATTEMPTS: ${INGEST_MAX_ATTEMPTS:-3}
  # 자동 재시도 백오프 — attempt 1 이면 120초, 2 면 600초 지난 뒤 다시 집는다
  INGEST_RETRY_BACKOFF_SECONDS: ${INGEST_RETRY_BACKOFF_SECONDS:-120,600}
  # 추출 전체 데드라인(초) — 넘으면 남은 쪽은 ODL 결과로 채택하고 meta.extract_deadline_hit 를 남긴다
  INGEST_EXTRACT_DEADLINE: ${INGEST_EXTRACT_DEADLINE:-2700}
  # 추출 stale 판정(초). 14400 은 문서당 VLM 상한(VLM_MAX_PAGES_PER_DOC 60)이 없던 파일럿
  # (2026-08-06, 632쪽 스캔본 210분)에 맞춘 값이었다. 상한 뒤 관측 최대 추출은 2785초(표본
  # 27,000건)이고 추출은 데드라인(2700초)에서 스스로 멈춘다. Celery visibility_timeout(7200초)
  # 안쪽이라 실행 중인 추출 메시지가 재전달되지 않는다.
  INGEST_STAGE_TIMEOUT_EXTRACT: ${INGEST_STAGE_TIMEOUT_EXTRACT:-3600}
```

`docker-compose.yml` — 교체 전:

```yaml
      # 대량 인덱싱 동시 LLM(celery-llm 4 × LLM_SECTION_CONCURRENCY 4 = 16) 수용
```

교체 후:

```yaml
      # 대량 인덱싱 동시 LLM(celery-llm 4 × LLM_SECTION_CONCURRENCY 4 = 16) 수용 — 요약 단계는
      # 섹션 요약과 논문 보강(표 해석 등)의 LLM 호출이 세마포어 하나를 나눠 쓴다
```

`docker-compose.yml` — 교체 전:

```yaml
    command: celery -A workers.celery_app worker --loglevel=info --concurrency=4 -Q q_cpu,q_control --max-tasks-per-child=50
```

교체 후:

```yaml
    command: celery -A workers.celery_app worker --loglevel=info --concurrency=4 -Q q_cpu --max-tasks-per-child=50
```

`docker-compose.yml` — 교체 전:

```yaml
  # ── Celery LLM Worker (배치 잡: 섹션 요약·문서 요약/소개 — 외부 vLLM HTTP) ──
  # 글로벌 동시 LLM = concurrency(4) × LLM_SECTION_CONCURRENCY(4) ≤ vLLM max-num-seqs(16)
```

교체 후:

```yaml
  # ── Celery Control Worker (제어 큐 q_control: 디스패치 30s·정리 1h·딥리서치 회수 10m) ──
  # 추출 워커(celery-cpu)에서 뗐다. 같이 있으면 추출 4칸이 다 찼을 때 디스패치 틱이 그 뒤에
  # 쌓였다가 칸이 비면 여럿이 한꺼번에 돌아, in-flight 를 같이 읽고 상한을 넘겨 보낼 수 있다.
  # concurrency=1 이라 디스패처는 한 번에 하나만 돈다(beat 일정의 expires 가 밀린 틱을 버린다).
  # GPU·모델 캐시는 필요 없다. 정리 태스크가 /app/data/downloads 를 지우므로 데이터 볼륨만 단다.
  celery-control:
    image: landsoftdocker/nl-lib-fastapi:latest
    container_name: nl-lib-celery-control
    <<: *nl-lib-net
    working_dir: /app
    command: celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q q_control
    environment:
      <<: *common-env
      PYTHONPATH: /app
    volumes:
      - /data/nl-lib/data:/app/data:rw
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped

  # ── Celery LLM Worker (배치 잡: 섹션 요약·논문 보강·문서 요약/소개 — 외부 vLLM HTTP) ──
  # 글로벌 동시 LLM = concurrency(4) × LLM_SECTION_CONCURRENCY(4) ≤ vLLM max-num-seqs(16).
  # 요약 단계는 섹션 요약과 논문 보강의 LLM 호출이 세마포어 하나(LLM_SECTION_CONCURRENCY)를 나눠 쓴다.
```

- [ ] **Step 5: `app/workers/celery_app.py` — beat `expires`**

`app/workers/celery_app.py` — 교체 전:

```python
    beat_schedule={
        "dispatch-job-items": {
            "task": "tasks.dispatch_job_items",
            "schedule": 30.0,
        },
        "cleanup-temp-files": {
            "task": "tasks.cleanup_temp_files",
            "schedule": 3600.0,
        },
        # 워커가 죽으면 잡이 running 인 채 영원히 남는다 — 하드 리밋을 넘긴 것만 회수한다
        # (research_tasks.STALE_MINUTES)
        "reap-stale-research": {
            "task": "tasks.reap_stale_research",
            "schedule": 600.0,
        },
    },
```

교체 후:

```python
    # expires: 제어 워커가 늦게 받은 옛 틱은 버린다. 밀린 디스패치 틱이 한꺼번에 돌면 in-flight 를
    # 같이 읽고 상한을 넘겨 보낸다 — 그래서 각 주기보다 짧게 둔다.
    beat_schedule={
        "dispatch-job-items": {
            "task": "tasks.dispatch_job_items",
            "schedule": 30.0,
            "options": {"expires": 25},
        },
        "cleanup-temp-files": {
            "task": "tasks.cleanup_temp_files",
            "schedule": 3600.0,
            "options": {"expires": 3000},
        },
        # 워커가 죽으면 잡이 running 인 채 영원히 남는다 — 하드 리밋을 넘긴 것만 회수한다
        # (research_tasks.STALE_MINUTES)
        "reap-stale-research": {
            "task": "tasks.reap_stale_research",
            "schedule": 600.0,
            "options": {"expires": 500},
        },
    },
```

- [ ] **Step 6: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_ingest_settings.py tests/test_celery_schedule.py -q`

Expected: `7 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && docker compose -f docker-compose.yml config -q; echo exit=$?`

Expected: 마지막 줄 `exit=0`. 그 위의 `The "POSTGRES_DB" variable is not set` 같은 경고는 로컬에 운영 env 가 없어서 나는 것이라 무시한다(docker 가 없는 환경이면 이 확인은 건너뛴다 — 위 pytest 가 같은 내용을 yaml 로 본다).

- [ ] **Step 7: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`

Expected: `897 passed, 2 warnings, 3 errors` (기준선 890 + 이 작업 7). `3 errors` 는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 실패하는 기존 파일 셋(`test_book_chat.py`·`test_build_manifest.py`·`test_loaders.py`)이다 — `--continue-on-collection-errors` 없이 돌리면 `Interrupted: 3 errors during collection` 으로 세션이 멈춘다.

- [ ] **Step 8: 커밋**

작업 트리에는 이 계획서·spec 처럼 이 작업 것이 아닌 변경이 있을 수 있다. `git add -A` 를 쓰지 말고 아래 파일만 올린다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && git add app/core/config.py docker-compose.yml app/workers/celery_app.py app/tests/test_ingest_settings.py app/tests/test_celery_schedule.py && git status --short && git commit -m "[Chore] round07 — 설정 키·compose·beat: 공통 계약의 새 설정 11개(문서 안 OCR 병렬·추출 데드라인·자동 재시도 백오프·LLM 재시도·문서 단위 스캔본 판정·ODL 타임아웃·ODL 이미지 출력)를 config 와 x-common-env 에 같은 기본값으로 선언하고, 추출 stale 판정 기본값을 3600초로 맞춘다(config 1800·compose 14400 → 3600 — 데드라인 2700 위, visibility_timeout 7200 아래). 제어 큐 q_control 은 새 경량 워커 celery-control(동시 1, GPU 없음)이 받고 celery-cpu 는 q_cpu 만 받는다. beat 틱마다 expires(25·3000·500초)를 둬 늦게 받은 옛 틱을 버린다"
```

---

### Task 1: llm_client 재시도와 finish_reason

> **실행 메모(2026-10-02, 리뷰 반영 7f5a4f5·a53c3b0):** 아래 '재시도 대상'·'최악 시간'과 Step 4 의 `22 passed` 는 첫 구현(d9c5135) 기준이다. 구현은 `httpx.NetworkError`(Connect·Read·Write·CloseError — gemma 재기동 때 처리 중이던 요청은 `ReadError` 로 끊긴다)·`httpx.TimeoutException`·`httpx.RemoteProtocolError` 와 429·5xx 를 재시도하고, 재시도 전체를 호출자의 timeout 안에 묶는다 — 시작 시각 + timeout 이 deadline 이고 시도마다 남은 시간만 쓰며, 남은 시간이 다음 백오프 + 1초 이하이면 더 시도하지 않는다(spec 9). 그래서 최악 시간은 '3 × timeout + 10초'가 아니라 timeout + 연결 대기(10초 이하)다 — httpx 는 연결과 읽기를 따로 재고 읽기 timeout 은 연결 전에 정해지므로 시도 하나가 남은 시간에 연결 몫까지 쓸 수 있다(1f4954b docstring). 다듬기(a53c3b0)에서 시도마다 연결 timeout 을 10초로 묶어(`_CONNECT_TIMEOUT_SECONDS` — 읽기 timeout 은 남은 시간 그대로) vLLM 재기동 중의 연결 대기도 남은 시간 안에서 재시도되게 했고, 더 시도하지 않는 마지막 실패는 ERROR 로 까닭(시도 횟수 소진·남은 시간 부족)과 함께 남긴다. 테스트도 리뷰 반영으로 늘었다.

spec 9번. 지금 `chat()` 은 실패를 바로 올리고(LLM 장애 때 `llm_error` 264건이 영구 실패) `finish_reason` 을 버린다(잘린 응답을 모른다). `chat_full()` 을 더해 `LLMResult(content, finish_reason)` 를 돌려주고, 비스트리밍 호출을 재시도한다. `chat()` 은 시그니처를 그대로 두고 `chat_full()` 의 `content` 만 돌려준다 — 기존 호출부(`summarizer`·`paper_enricher`·`cover_generator`·`pdf_meta_extractor`·`research/critic`·`planner`·`synthesizer`)는 고치지 않는다. `chat_stream()` 은 그대로 둔다(재시도 없음).

- **설정:** Task 0 이 `app/core/config.py`·`docker-compose.yml` 에 더한 `LLM_RETRY_ATTEMPTS`(int 3, 첫 시도 포함)·`LLM_RETRY_BACKOFF_SECONDS`(str `"2,8"`)를 쓴다. 이 작업은 config 를 고치지 않는다 — 두 키가 없으면 Task 0 이 아직 안 된 것이다.
- **재시도 대상:** `httpx.ConnectError`·`httpx.TimeoutException`(연결·읽기·쓰기·풀)·`httpx.RemoteProtocolError`, 그리고 `httpx.HTTPStatusError` 중 429·5xx. 그 밖의 4xx 는 요청 자체 문제라 바로 올린다. 마지막 시도의 예외를 그대로 올리므로 `job_runtime.classify_error` 의 `llm_timeout`·`llm_error` 분류는 바뀌지 않는다.
- **간격:** n 번째 재시도 앞에 `LLM_RETRY_BACKOFF_SECONDS` 의 n 번째 값만큼 기다린다. 값이 모자라면 마지막 값을 되풀이하고("2,8" → 2초, 8초, 8초…), 숫자가 아닌 칸은 건너뛴다.
- **잘림:** openai 호환 경로는 `choices[0].finish_reason`, ollama 경로는 응답의 `done_reason`(없으면 `None`). `"length"` 면 모델 이름과 `max_tokens` 를 경고로 남긴다. 잘린 응답을 어떻게 다룰지는 호출부가 정한다(표 해석은 Task 6).
- **최악 시간:** 한 호출이 `3 × timeout + 10초`까지 늘어난다. 연결 거부는 즉시 실패하므로 보통은 백오프 10초만 더해진다. 타임아웃이 이어지는 장애에서는 요약 단계가 길어진다 — 단계 타임아웃(요약 1,200초)은 이 작업에서 바꾸지 않는다.

**Files:**
- Modify: `app/services/llm_client.py` (193be93 기준 모듈 docstring 7-9행, import 15-23행, `chat()` 52-82행)
- Create: `app/tests/test_llm_client.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

실제 LLM 은 부르지 않는다. `llm_client` 가 만드는 `httpx.AsyncClient` 에 `httpx.MockTransport` 를 끼워 응답(또는 예외)을 순서대로 돌려주고, `asyncio.sleep` 을 기록용 가짜로 바꿔 백오프를 실제로 기다리지 않고 잰다. 재시도 실패 사례는 람다로 받아 시도마다 새 객체를 만든다(같은 응답 객체를 두 번 돌려주지 않게). `app/tests/test_llm_client.py`:

```python
"""llm_client.chat_full — 재시도·백오프·finish_reason 단위 테스트.

실제 LLM 은 부르지 않는다. llm_client 가 만드는 httpx.AsyncClient 에 MockTransport 를
끼워 응답(또는 예외)을 순서대로 돌려주고, asyncio.sleep 을 기록용 가짜로 바꿔 백오프
간격을 실제로 기다리지 않고 확인한다.
"""
import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from services import llm_client


def _ok(content: str = "응답", finish_reason: str | None = "stop") -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
    })


@pytest.fixture
def cfg(monkeypatch):
    """openai 호환 경로 + 재시도 3회(첫 시도 포함)·백오프 2초→8초 (Task 0 이 더한 키)."""
    settings = llm_client.get_settings()
    monkeypatch.setattr(settings, "LLM_API_STYLE", "openai")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemma-test")
    monkeypatch.setattr(settings, "LLM_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LLM_RETRY_BACKOFF_SECONDS", "2,8")
    return settings


@pytest.fixture
def server(monkeypatch):
    """queue 에 넣은 응답·예외를 요청마다 하나씩 꺼낸다. calls 에 (url, body) 를 쌓는다."""
    state = SimpleNamespace(queue=[], calls=[])

    def handler(request: httpx.Request) -> httpx.Response:
        state.calls.append((str(request.url), json.loads(request.content)))
        item = state.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    real_client = httpx.AsyncClient

    def client_with_mock_transport(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(llm_client.httpx, "AsyncClient", client_with_mock_transport)
    return state


@pytest.fixture
def sleeps(monkeypatch):
    waited: list[float] = []

    async def fake_sleep(seconds):
        waited.append(seconds)

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)
    return waited


MESSAGES = [{"role": "user", "content": "안녕"}]


def test_chat_full_returns_content_and_finish_reason(cfg, server, sleeps):
    server.queue.append(_ok("  요약 결과  ", "stop"))

    result = asyncio.run(llm_client.chat_full(MESSAGES, params={"max_tokens": 50}))

    assert result == llm_client.LLMResult(content="요약 결과", finish_reason="stop")
    url, body = server.calls[0]
    assert url == "http://llm.test/v1/chat/completions"
    assert body["model"] == "gemma-test" and body["max_tokens"] == 50
    assert sleeps == []


def test_chat_keeps_signature_and_returns_content_only(cfg, server, sleeps):
    server.queue.append(_ok("본문", "length"))

    assert asyncio.run(llm_client.chat(MESSAGES, params={"max_tokens": 10})) == "본문"


def test_length_finish_reason_logs_model_and_max_tokens(cfg, server, sleeps, caplog):
    server.queue.append(_ok("잘린 응답", "length"))

    with caplog.at_level(logging.WARNING, logger=llm_client.log.name):
        result = asyncio.run(llm_client.chat_full(MESSAGES, params={"max_tokens": 600}))

    assert result.finish_reason == "length"
    warned = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("gemma-test" in m and "600" in m for m in warned)


def test_ollama_path_reads_done_reason(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_API_STYLE", "ollama")
    server.queue.append(httpx.Response(200, json={
        "message": {"content": "올라마 응답"}, "done": True, "done_reason": "length",
    }))
    server.queue.append(httpx.Response(200, json={"message": {"content": "옛 응답"}, "done": True}))

    first = asyncio.run(llm_client.chat_full(MESSAGES))
    second = asyncio.run(llm_client.chat_full(MESSAGES))

    assert first == llm_client.LLMResult(content="올라마 응답", finish_reason="length")
    assert second == llm_client.LLMResult(content="옛 응답", finish_reason=None)
    assert server.calls[0][0] == "http://llm.test/api/chat"


@pytest.mark.parametrize("make_failure", [
    lambda: httpx.ConnectError("연결 거부"),
    lambda: httpx.ReadTimeout("읽기 시간 초과"),
    lambda: httpx.RemoteProtocolError("서버가 연결을 끊음"),
    lambda: httpx.Response(429, text="too many"),
    lambda: httpx.Response(503, text="busy"),
], ids=["connect", "timeout", "protocol", "429", "503"])
def test_transient_failures_are_retried_with_backoff(cfg, server, sleeps, make_failure):
    server.queue.extend([make_failure(), make_failure(), _ok("세 번째에 성공")])

    result = asyncio.run(llm_client.chat_full(MESSAGES))

    assert result.content == "세 번째에 성공"
    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]


def test_gives_up_after_attempts_and_raises_last_error(cfg, server, sleeps):
    server.queue.extend([httpx.ConnectError("1"), httpx.ConnectError("2"), httpx.ReadTimeout("3")])

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert len(server.calls) == 3
    assert sleeps == [2.0, 8.0]          # 마지막 실패 뒤에는 기다리지 않는다


@pytest.mark.parametrize("status", [400, 401, 404, 422])
def test_other_4xx_raise_immediately(cfg, server, sleeps, status):
    server.queue.append(httpx.Response(status, text="bad request"))

    with pytest.raises(httpx.HTTPStatusError) as exc:
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert exc.value.response.status_code == status
    assert len(server.calls) == 1
    assert sleeps == []


def test_backoff_repeats_last_value_when_schedule_is_short(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_RETRY_ATTEMPTS", 4)
    server.queue.extend([httpx.Response(502), httpx.Response(502), httpx.Response(502), _ok()])

    asyncio.run(llm_client.chat_full(MESSAGES))

    assert sleeps == [2.0, 8.0, 8.0]


def test_single_attempt_means_no_retry(cfg, server, sleeps, monkeypatch):
    monkeypatch.setattr(cfg, "LLM_RETRY_ATTEMPTS", 1)
    server.queue.append(httpx.ConnectError("연결 거부"))

    with pytest.raises(httpx.ConnectError):
        asyncio.run(llm_client.chat_full(MESSAGES))

    assert len(server.calls) == 1 and sleeps == []


@pytest.mark.parametrize("schedule, retry_no, expected", [
    ("2,8", 1, 2.0),
    ("2,8", 2, 8.0),
    ("2,8", 5, 8.0),
    (" 5 ", 3, 5.0),
    ("", 1, 0.0),
    ("x,3", 1, 3.0),
])
def test_backoff_delay_parsing(schedule, retry_no, expected):
    assert llm_client._backoff_delay(schedule, retry_no) == expected
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_llm_client.py -q`
Expected: `6 failed, 16 errors` — 6 failed 는 `AttributeError: module 'services.llm_client' has no attribute '_backoff_delay'`, 16 errors 는 `sleeps` 픽스처의 `AttributeError: module 'services.llm_client' has no attribute 'asyncio'`.

- [ ] **Step 3: 구현한다**

`app/services/llm_client.py` 를 세 군데 바꾼다.

① 모듈 docstring. old:

```python
Ollama 의 OpenAI 호환(/v1) 엔드포인트는 think 파라미터를 무시하므로, thinking 을
끄려면 반드시 네이티브 /api/chat + think:false 를 써야 한다.
호출부는 chat() / chat_stream() 만 사용하고, 스타일 분기는 여기서 처리한다.
```

new:

```python
Ollama 의 OpenAI 호환(/v1) 엔드포인트는 think 파라미터를 무시하므로, thinking 을
끄려면 반드시 네이티브 /api/chat + think:false 를 써야 한다.
호출부는 chat() / chat_full() / chat_stream() 만 사용하고, 스타일 분기는 여기서 처리한다.

  chat_full() → LLMResult(content, finish_reason). 잘림(finish_reason == "length")을
  호출부가 처리해야 할 때 쓴다. chat() 은 그 content 만 돌려준다.
  비스트리밍 호출은 연결 오류·타임아웃·연결 끊김·429·5xx 를 LLM_RETRY_ATTEMPTS(첫 시도
  포함)까지 LLM_RETRY_BACKOFF_SECONDS("2,8" — 모자라면 마지막 값 반복) 간격으로 다시
  보낸다. 그 밖의 4xx 는 요청 자체 문제라 바로 올린다. chat_stream() 은 재시도하지 않는다.
```

② import 와 모듈 상단 — `LLMResult`·재시도 대상·백오프 계산을 더한다. old:

```python
import json
import logging
from typing import AsyncGenerator

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)
```

new:

```python
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx

from core.config import get_settings

log = logging.getLogger(__name__)

# 다시 보내면 나을 수 있는 실패 — 연결 거부·타임아웃(연결·읽기·쓰기·풀)·응답 도중 끊김.
_RETRYABLE_ERRORS = (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError)


@dataclass
class LLMResult:
    content: str
    finish_reason: str | None   # openai: choices[0].finish_reason / ollama: done_reason (없으면 None)


def _is_retryable_status(code: int) -> bool:
    """429(과부하)·5xx(서버 쪽 일시 문제)만 재시도 — 그 밖의 4xx 는 다시 보내도 같다."""
    return code == 429 or 500 <= code < 600


def _backoff_delay(schedule: str, retry_no: int) -> float:
    """retry_no 번째 재시도 전 대기(초). "2,8" → 1번째 2초, 2번째부터 8초(마지막 값 반복).

    숫자가 아닌 칸은 건너뛰고, 쓸 값이 하나도 없으면 기다리지 않는다.
    """
    delays: list[float] = []
    for tok in str(schedule).split(","):
        try:
            delays.append(max(0.0, float(tok)))
        except ValueError:
            continue
    if not delays:
        return 0.0
    return delays[min(retry_no, len(delays)) - 1]
```

③ `chat()` 전체를 `_request_once()`(한 번 보내고 `LLMResult` 로 바꿈)·`chat_full()`(재시도)·`chat()`(content 만) 으로 바꾼다. 바로 아래 `chat_stream()` 은 그대로 둔다. old:

```python
async def chat(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """비스트리밍 chat 완성 → 최종 content 문자열."""
    cfg = get_settings()
    params = params or {}
    try:
        if cfg.LLM_API_STYLE == "ollama":
            url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
            body = _ollama_body(messages, params, stream=False)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                return (resp.json()["message"]["content"] or "").strip()

        # openai 호환 (vLLM 등)
        url = f"{cfg.LLM_BASE_URL}/chat/completions"
        body = {"model": cfg.LLM_MODEL, "messages": messages, **params}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        log.error(
            f"[llm_client:{cfg.LLM_API_STYLE}] {e.response.status_code} — "
            f"{e.response.text[:400]}"
        )
        raise
```

new:

```python
async def _request_once(messages: list[dict], params: dict, timeout: float) -> LLMResult:
    """한 번 보내고 응답을 LLMResult 로 바꾼다 (재시도는 chat_full 이 한다)."""
    cfg = get_settings()
    if cfg.LLM_API_STYLE == "ollama":
        url = f"{_ollama_root(cfg.LLM_BASE_URL)}/api/chat"
        body = _ollama_body(messages, params, stream=False)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
        return LLMResult(
            content=((data.get("message") or {}).get("content") or "").strip(),
            finish_reason=data.get("done_reason"),
        )

    # openai 호환 (vLLM 등)
    url = f"{cfg.LLM_BASE_URL}/chat/completions"
    body = {"model": cfg.LLM_MODEL, "messages": messages, **params}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    choice = data["choices"][0]
    return LLMResult(
        content=(choice["message"]["content"] or "").strip(),
        finish_reason=choice.get("finish_reason"),
    )


async def chat_full(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> LLMResult:
    """비스트리밍 chat 완성 → LLMResult(content, finish_reason). 일시적 실패는 재시도한다."""
    cfg = get_settings()
    params = params or {}
    attempts = max(1, int(cfg.LLM_RETRY_ATTEMPTS))
    attempt = 1
    while True:
        try:
            result = await _request_once(messages, params, timeout)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            log.error(
                f"[llm_client:{cfg.LLM_API_STYLE}] {code} ({attempt}/{attempts}회차) — "
                f"{e.response.text[:400]}"
            )
            if not _is_retryable_status(code) or attempt >= attempts:
                raise
        except _RETRYABLE_ERRORS as e:
            log.warning(
                f"[llm_client:{cfg.LLM_API_STYLE}] {type(e).__name__} ({attempt}/{attempts}회차) — {e}"
            )
            if attempt >= attempts:
                raise
        else:
            if result.finish_reason == "length":
                log.warning(
                    f"[llm_client:{cfg.LLM_API_STYLE}] 응답이 max_tokens 에서 잘렸다 — "
                    f"model={cfg.LLM_MODEL} max_tokens={params.get('max_tokens')}"
                )
            return result
        await asyncio.sleep(_backoff_delay(cfg.LLM_RETRY_BACKOFF_SECONDS, attempt))
        attempt += 1


async def chat(
    messages: list[dict],
    *,
    params: dict | None = None,
    timeout: float = 120.0,
) -> str:
    """비스트리밍 chat 완성 → 최종 content 문자열 (= chat_full 의 content)."""
    return (await chat_full(messages, params=params, timeout=timeout)).content
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_llm_client.py -q`
Expected: `22 passed`

`chat` 을 쓰는 호출부의 기존 테스트(research 셋은 모듈 최상단에서 `chat` 을 import 하고, 테스트가 그 이름을 대역으로 바꾼다):

Run: `python -m pytest tests/test_summarizer.py tests/test_research_critic.py tests/test_research_planner.py tests/test_research_synthesizer.py -q`
Expected: 실패 0 (사본에서 `200 passed`)

전체:

Run: `python -m pytest -q --continue-on-collection-errors`
Expected: 실패 0. `ERROR tests/test_book_chat.py`·`ERROR tests/test_build_manifest.py`·`ERROR tests/test_loaders.py` 3건은 로컬 venv 에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 나는 것으로 작업 전에도 같다. 이 플래그 없이 돌리면 `Interrupted: 3 errors during collection` 으로 한 건도 돌지 않는다.

- [ ] **Step 5: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/llm_client.py app/tests/test_llm_client.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Feat] round07 — LLM 호출 재시도와 잘림 감지: chat_full() 이 LLMResult(content, finish_reason)를 돌려주고, 연결 오류·타임아웃·연결 끊김·429·5xx 는 LLM_RETRY_ATTEMPTS(첫 시도 포함)까지 LLM_RETRY_BACKOFF_SECONDS 간격(2초→8초, 모자라면 마지막 값)으로 다시 보낸다. 그 밖의 4xx 는 바로 올리고, length 로 끝나면 모델·max_tokens 를 경고로 남긴다. chat() 은 시그니처 그대로 content 만 돌려줘 호출부는 바뀌지 않는다"
```

---

---

### Task 2: 실행 토큰·체인 정지·stale 판정 분리·재시도 백오프

spec 항목 18 전부, 항목 8 의 재시도 부분(결정적 실패 제외·추출부터 다시·백오프), 항목 16 의 `job_runtime.py:55` 주석. 함정 16번의 근본 원인 넷 — 단계 래퍼가 `done`·체크포인트를 보지 않음, stale 복구가 옛 체인을 끊지 않음, 락 경합 뒤에도 체인이 다음 단계로 감, 큐 대기를 실행 시간으로 셈 — 을 닫는다.

**전제:** Task 0 이 `INGEST_RETRY_BACKOFF_SECONDS`(str, 기본 `"120,600"`)를 `app/core/config.py` 에 더해 커밋했다. 이 작업의 테스트 하네스가 그 키를 monkeypatch 하므로, 키가 없으면 모든 `test_job_runtime.py` 테스트가 `AttributeError` 로 바로 드러난다.

**Files:**
- Modify: `app/services/ingestion/stages.py` — `StageContext.item_meta`, `run_embed_index` 의 아티팩트 로드 직후(2-1). 논문 보강 블록(`# ── [paper] 보강 청크`)은 Task 6 몫이라 건드리지 않는다.
- Modify: `app/workers/job_runtime.py` — 2-2 ~ 2-4
- Create: `app/tests/test_job_runtime.py` — 2-2 에서 만들고 2-3·2-4 에서 끝에 덧붙인다
- Modify: `app/tests/test_embed_index_guard.py` — 테스트 2개 추가(기존 4개는 손대지 않고 그대로 통과)
- Modify: `app/tests/test_backfill_summary.py` — 모듈 맨 위 celery 더미에 `celery.exceptions` 추가(2-2)

**전체 스위트 명령:** 로컬 venv 에는 `FlagEmbedding`·`openpyxl` 이 없어 `test_book_chat.py`·`test_build_manifest.py`·`test_loaders.py` 가 수집 단계에서 죽고, 그대로 `python -m pytest -q` 를 돌리면 세션이 `Interrupted: 3 errors during collection` 으로 0건이 된다. 이 작업은 지난 라운드(round03~04c) 계획·완료노트와 같은 명령을 쓴다(기준 890 passed).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```

아래 "검증 사본" 수치는 이 계획의 코드를 원본 worktree 사본(Task 0 의 설정 키만 임시로 더함, 기준 890)에 2-1 → 2-4 순서로 그대로 적용해 돌린 값이다. Task 0·1 이 테스트를 더했으면 전체 수는 그만큼 크다 — 늘어난 수(+2·+19·+11·+6)와 실패 0 을 본다.

#### 설계 메모 (구현 전에 읽는다)

**① `Ignore` 가 체인을 멈추는 근거 — Celery 5.4.0(`app/requirements.txt:18`)**

- 체인의 남은 단계는 첫 태스크 메시지 안에 실려 간다. `celery/canvas.py` 의 `_chain.run` 이 `prepare_steps` 로 남은 서명 목록을 만들고 `_prepare_chain_from_options` 로 `chain` 옵션에 넣은 뒤 첫 태스크만 `apply_async` 한다. 워커에서는 그 목록이 `task_request.chain` 이다.
- 다음 단계는 성공했을 때만 보낸다. `celery/app/trace.py` 의 `build_tracer` → `trace_task` 는 태스크 함수를 부른 뒤 `except Reject`·`except Ignore`·`except Retry`·`except Exception` 으로 나누고, `task_request.chain` 에서 다음 서명을 `pop()` 해 `apply_async` 하는 코드는 예외가 없을 때의 `else:` 분기에만 있다. `Ignore` 분기는 상태를 `IGNORED` 로 두고 `handle_ignore`(INFO 로그 "ignored")만 부른다. link 콜백(`task.request.callbacks`)도 같은 `else:` 안이라 link 로 묶인 체인도 멈춘다.
- `IGNORED` 는 `IGNORE_STATES` 에 들어 있어 결과 백엔드에 상태를 남기지 않고 `after_return` 도 부르지 않는다.
- 메시지는 ack 된다. `celery/worker/request.py` 의 `Request.on_failure` 가 예외가 `Ignore` 면 `acknowledge()` 를 부른다 — `acks_late=True` 여도 재전달되지 않는다. Celery 문서(Tasks › Semipredicates › Ignore)도 상태는 남지 않고 메시지는 ack 된다고 적는다.
- 주의: `Ignore` 는 `TaskPredicate` → `CeleryError` → `Exception` 의 하위다. `_run_stage` 의 `except Exception` 안에서 던지면 실패(`failed`·attempt+1)로 기록되므로, 실행 판단은 모두 그 `try` 밖에서 한다.
- 로컬 venv 에는 celery 가 없어 "체인이 멈춘다"는 단위 테스트로 재현하지 않는다. 테스트는 "Ignore 를 던지고 아이템을 바꾸지 않는다"까지 보고, 체인 정지는 카나리에서 워커 로그로 본다(⑦).

**② `_run_stage` 가 실행하지 않는 경우**

모두 `Ignore` 를 던지고 아이템 행과 `library_catalog.ingest_state` 를 바꾸지 않는다. 로그는 WARNING `[book_id] item=N <단계> 실행 안 함 — <이유> → 체인 정지`.

| 순서 | 조건 | 이유 문구 | 지금 |
|---|---|---|---|
| 1 | 아이템 없음 | `아이템 없음` | dict 반환 → 체인이 다음 단계로 |
| 2 | 아이템 `canceled` 또는 잡 `canceled` | `취소됨` | dict 반환 → 체인이 다음 단계로 |
| 3 | 메시지에 토큰이 있고 `meta.run_token` 과 다르다 | `실행 토큰 불일치(…) — 옛 체인` | (토큰 없음) 실행 |
| 4 | 메시지에 토큰이 없는데(배포 전 메시지) `meta.run_token` 이 있다 | `토큰 없는 옛 메시지인데 …` | 실행 |
| 5 | `status == "done"` | `이미 완료(done)` | 실행 |
| 6 | 단계가 `CHECKPOINT_TO_REMAINING[item.stage]` 에 없다(이미 지남) | `이미 지난 단계(체크포인트 …)` | 실행 |
| 7 | `BookLock` 획득 실패 | `락 경합` | `pending` 으로 되돌리고 dict 반환 → 체인이 다음 단계로 |

토큰 없는 메시지가 토큰 없는 아이템(배포 전 아이템)에 오면 1·2·5·6·7 만 보고 예전처럼 실행한다. 1(아이템 없음)은 spec 18 에 없지만 같은 이유(실행하지 않는 단계는 체인도 멈춘다)로 넣었다.

**③ 토큰 커밋 순서 — 첫 읽기는 `FOR UPDATE`**

디스패처는 `SELECT … FOR UPDATE SKIP LOCKED` 로 집은 행에 토큰을 적고 메시지를 보낸 뒤 루프 끝에서 한 번 커밋한다. 큐가 비어 있으면 워커가 그 커밋보다 먼저 첫 단계를 받을 수 있다. 이때 아이템을 그냥 읽으면 커밋 전 값(옛 토큰 또는 토큰 없음)을 보고 새 체인을 3번으로 멈춘다 — 아이템은 `dispatched` 로 4시간 남는다. 그래서 `_run_stage` 의 첫 읽기를 `with_for_update()` 로 해, 디스패처의 행 잠금이 풀릴 때(커밋)까지 기다렸다가 새 토큰을 읽는다. 잠금은 읽은 뒤 세션을 바로 닫아 놓는다(`_update_item` 은 별도 세션). 메시지를 보낸 뒤 브로커 오류로 디스패처 트랜잭션이 롤백되면 토큰도 롤백되므로, 이미 나간 메시지는 3번으로 멈추고 아이템은 다음 틱에 새 토큰으로 다시 나간다(지금은 나간 메시지와 재디스패치가 둘 다 돈다). SQLite 는 잠금을 그리지 않으므로 테스트는 같은 문장을 Postgres 로 컴파일해 `FOR UPDATE` 를 확인한다.

**④ 락 경합 때 `pending` 으로 되돌리지 않는 이유**

spec 18 은 "락 경합으로 pending 으로 되돌렸다"를 멈출 조건으로 적었지만, 이 계획은 체인만 멈추고 상태는 그대로 둔다. 락 경합은 같은 `book_id` 를 다른 체인(대개 stale 복구 전의 옛 체인)이나 단건 흐름이 쥐고 있다는 뜻이다. `pending` 으로 되돌리면 디스패처가 30초 안에 새 토큰으로 다시 보내고, 그 토큰이 락을 쥐고 일하는 체인의 다음 단계를 3번으로 끊으며, 쥔 쪽이 끝날 때까지 경합을 되풀이한다. 그래서 이 체인만 멈춘다. 쥔 쪽이 단계를 끝내면 체크포인트는 앞으로 가지만 그 체인의 다음 단계도 토큰이 달라 멈추므로, 아이템은 `dispatched`(또는 단계 사이의 `running`)로 남았다가 stale 복구(`DISPATCH_STALE_SECONDS` 4시간) 뒤 체크포인트부터 다시 나간다. 느리지만 중복 실행은 없다. 같은 `book_id` 가 두 잡에서 동시에 도는 것도 이 경로다 — 카나리 잡과 본 잡을 동시에 `running` 으로 두지 않는다(Task 12 런북).

**⑤ 재시도 규칙**

- 결정적 실패 `no_text`(Task 4 가 던진다): 실패를 기록할 때 attempt 를 `max_attempts`(잡 params, 없으면 `cfg.INGEST_MAX_ATTEMPTS`)까지 올린다. 디스패처의 `attempt < max_attempts` 조건에서 빠지고 `_maybe_complete` 도 기다리지 않는다. 수동 retry(attempt 0 리셋)로만 다시 돈다.
- 추출부터 다시: `failed` 를 자동 재시도로 집을 때 `error_group == "vlm_error"` 이거나, `not_found` 이면서 `last_error` 에 `섹션 없음`(`run_summarize` 의 문구)이 있으면 `stage` 를 `pending` 으로 되돌린 뒤 체인을 만든다. 이미 `pending` 이면(추출에서 난 `vlm_error`) 그대로다. 수동 retry 로 `pending` 이 된 아이템은 `retry_items` 가 `error_group`·`last_error` 를 지우므로 해당하지 않는다 — `reset_stage` 로 정한다. `artifact_missing` 은 넣지 않는다. `load_extraction_artifact` 가 MinIO 일시 오류도 이 그룹으로 감싸므로 같은 체크포인트에서 다시 하는 게 맞고, 진짜 아티팩트 없음(완료 문서 재임베딩)은 운영자가 정할 일이다.
- 백오프: `attempt` 번째 실패 뒤 `steps[attempt-1]` 초가 `updated_at`(실패를 기록한 시각)부터 지나야 집는다. `"120,600"` → 1회 실패 뒤 120초, 2회 이상 600초(값이 모자라면 마지막 값 반복). `pending` 과 `attempt < 1` 인 실패는 기다리지 않는다. 조건은 SQL 에 넣는다 — `limit(need)` 뒤 파이썬에서 거르면 id 가 앞선 백오프 중 실패가 limit 을 채워 뒤의 pending 을 막는다. id 순서는 그대로다. stale 복구도 attempt 를 올리고 `updated_at` 을 찍으므로 같은 백오프를 탄다. 설정값에 정수가 아닌 칸이 있으면 경고하고 건너뛴다(디스패처가 30초마다 죽지 않게).

**⑥ stale 판정**

| 상태 | 기준 시각 | 상한 |
|---|---|---|
| `running` + `meta.stage_running` = 단계 이름 | `meta.stage_started_at`(없으면 `updated_at`) | 그 단계 타임아웃(`INGEST_STAGE_TIMEOUT_*`) |
| `running` + `stage_running` 없음·null(단계를 끝내고 다음 단계 큐를 기다림, 배포 전 아이템 포함) | `updated_at` | `DISPATCH_STALE_SECONDS`(기본 14400) |
| `dispatched` | `updated_at` → `dispatched_at` → `created_at` | `DISPATCH_STALE_SECONDS` — 지금 그대로 |

`_run_stage` 는 시작 때 `meta.stage_running`(단계 이름)·`stage_started_at`(UTC ISO)을 적고 성공·실패 때 `stage_running` 을 null 로 지운다(`stage_started_at` 은 마지막 시작 시각으로 남긴다). `_update_item` 의 meta 필터는 지금도 `type(None)` 을 통과시키고 `if meta_update:` 는 `{"stage_running": None}` 을 참으로 보므로 null 기록에 로직 변경은 없다 — 주석만 단다. `last_error` 는 `… (stale 복구, embed_index 실행 중 | 다음 단계 대기 | 디스패치 대기)` 라 함정 16번의 조회(`LIKE '%stale 복구%'`)가 그대로 걸린다. 55행 주석: `DISPATCH_STALE_SECONDS` 14400초가 broker `visibility_timeout` 7200초(`workers/celery_app.py`)의 2배라는 숫자는 맞다. 고칠 것은 쓰임(단계 사이 대기에도 쓴다)과 까닭(받은 채 죽은 메시지가 7200초 뒤 재전달돼 다시 집힐 때까지 기다린다)이다.

**⑦ 옛 메시지 호환과 배포**

- 배포 직전 in-flight 0(spec §6)이면 배포 전 체인 메시지는 없어야 한다. 다만 DB 의 in-flight 0 이 브로커가 비었다는 증명은 아니다 — 받은 채 끊긴 메시지는 kombu 의 `unacked` 해시에 남았다가 visibility_timeout(7200초) 뒤 원래 큐로 돌아온다. 그런 메시지는 토큰 인자가 없다(`stage_x(item_id)` → `run_token=None`).
  - 그 아이템이 배포 뒤 한 번이라도 디스패치됐으면 토큰이 있어 4번으로 멈춘다.
  - 아니면 예전처럼 돌되, 5·6 번이 끝난 아이템과 지난 단계를 막고 2-1 의 가드가 PDF 문서의 초록 덮어쓰기를 막는다.
  - Task 12 런북의 배포 직전 확인(읽기 전용)에 `docker exec nl-lib-redis redis-cli HLEN unacked` 와 `LLEN q_cpu`·`LLEN q_llm`·`LLEN q_embed` 를 더하기를 권한다.
- 카나리 확인(spec §5 "중복 체인이 없는가"): 워커 로그의 `실행 안 함 —` 줄을 이유별로 센다. `실행 토큰 불일치`·`토큰 없는 옛 메시지` 는 0 이어야 한다. Celery 자체 로그에는 같은 태스크가 `ignored` 로 찍힌다.
- 완료 문서를 `reset_stage: "summarized"` 등으로 다시 임베딩하면 이제 `artifact_missing` 으로 실패한다(지금은 초록으로 덮는다). spec §3 의 "run_embed_index 를 다시 돌리는 방식은 쓸 수 없다"와 같은 결론이다.

---

#### 2-1. 추출 아티팩트 가드 — `StageContext.item_meta` (stages.py)

PDF 가 있던 문서(추출이 남긴 `meta.pages > 0`)인데 추출 아티팩트가 없으면 초록으로 색인하지 않고 멈춘다. PDF 없는 메타데이터 전용 논문(`pages` 없음·0)은 지금처럼 초록으로 색인한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `app/tests/test_embed_index_guard.py` 끝에 덧붙인다. 기존 4개와 `_patch_common` 은 그대로 둔다.

```python
def _stub_indexing(monkeypatch) -> tuple[list, list]:
    """청킹·임베딩·인덱싱을 대역으로 바꾸고 (청킹에 들어간 텍스트, index_chunks 호출) 기록을 돌려준다.

    test_paper_falls_back_to_abstract_… 와 같은 이유로 모듈을 직접 import 해 patch 한다.
    보강(PAPER_ENRICH_ENABLED)은 끈다 — 켜 두면 LLM 에 접속을 시도한다.
    """
    import services.ingestion.chunker as chunker_mod
    import services.ingestion.embedder as embedder_mod
    import services.ingestion.indexer as indexer_mod

    chunked: list = []
    indexed: list = []
    monkeypatch.setattr(stages.cfg, "PAPER_ENRICH_ENABLED", False)
    monkeypatch.setattr(
        chunker_mod, "semantic_chunk",
        lambda text, embed_fn, **kw: chunked.append(text)
        or [chunker_mod.Chunk(chunk_idx=0, text=text, section_idx=None)],
    )
    monkeypatch.setattr(
        embedder_mod, "embed_texts",
        lambda texts, *a, **kw: ([[0.0] for _ in texts], [{} for _ in texts]),
    )
    fake_result = MagicMock(errors=[], chunks_indexed=1)
    monkeypatch.setattr(
        indexer_mod, "index_chunks",
        lambda *a, **kw: indexed.append(True) or fake_result,
    )
    return chunked, indexed


def test_paper_with_pdf_and_missing_artifact_is_not_indexed_from_abstract(monkeypatch):
    """추출이 쪽수를 남긴 문서(PDF 가 있었다)인데 아티팩트가 없다 — 마무리가 아티팩트를 지운 뒤
    옛 체인의 embed_index 가 돌면 여기로 온다(함정 16). 초록으로 진행하면 index_chunks 가 본문
    청크를 지우고 초록 청크로 덮으므로, 인덱스를 건드리기 전에 artifact_missing 으로 멈춘다."""
    book = MagicMock(doc_type="paper", abstract="이 논문은 강화학습 보상 설계를 다룬다.",
                     title="논문 제목", personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book)   # 기본 로더 = 아티팩트 없음
    chunked, indexed = _stub_indexing(monkeypatch)

    with pytest.raises(StageError) as exc:
        stages.run_embed_index(StageContext(book_id="KCI_FI000000003", item_meta={"pages": 12}))

    assert exc.value.error_group == "artifact_missing"
    assert chunked == [] and indexed == [], "초록으로 본문 청크를 덮으면 안 된다"


def test_metadata_only_paper_without_pages_still_uses_abstract(monkeypatch):
    """PDF 없는 메타데이터 전용 논문(meta.pages 가 없거나 0)은 지금처럼 초록으로 색인한다."""
    book = MagicMock(doc_type="paper", abstract="이 논문은 강화학습 보상 설계를 다룬다.",
                     title="논문 제목", personal_author=None, corporate_author=None,
                     series_title=None, subject=None, keyword=None)
    _patch_common(monkeypatch, book)   # 기본 로더 = 아티팩트 없음
    chunked, indexed = _stub_indexing(monkeypatch)

    for meta in ({}, {"pages": 0}):
        chunked.clear()
        result = stages.run_embed_index(StageContext(book_id="KCI_FI000000004", item_meta=meta))
        assert result["indexed"] == 1
        assert chunked == ["이 논문은 강화학습 보상 설계를 다룬다."], meta
    assert indexed == [True, True]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_embed_index_guard.py -q`
Expected: `2 failed, 4 passed` — 새 두 테스트가 `TypeError: StageContext.__init__() got an unexpected keyword argument 'item_meta'`.

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/stages.py`

`StageContext` — old:
```python
    job_item_id: int | None = None   # 잡 아이템 (단건 흐름이면 None)
    params: dict = field(default_factory=dict)  # {"skip_cover": true, "doc_type": "paper", ...}
```
new:
```python
    job_item_id: int | None = None   # 잡 아이템 (단건 흐름이면 None)
    params: dict = field(default_factory=dict)  # {"skip_cover": true, "doc_type": "paper", ...}
    # 잡 아이템 meta 사본 — 앞 단계가 남긴 값(예: 추출의 pages). 단건 흐름이면 빈 dict
    item_meta: dict = field(default_factory=dict)
```

`run_embed_index` 의 아티팩트 로드 직후 — old:
```python
    except StageError as _se:
        if _se.error_group != "artifact_missing":
            raise
        # PDF 없는 메타데이터 전용 논문 — abstract를 임베딩 텍스트로 사용
        full_text = ""
        page_map = {}
```
new (이 아래의 논문 초록 폴백·`empty_body` 가드·보강 블록은 그대로):
```python
    except StageError as _se:
        if _se.error_group != "artifact_missing":
            raise
        # 추출이 쪽수를 남긴 문서는 PDF 가 있었다. 아티팩트가 없는 것은 마무리가 이미 지웠거나
        # (옛 체인의 재실행 — 함정 16) 읽지 못한 것이다. 초록으로 진행하면 index_chunks 가 본문
        # 청크를 지우고 초록 청크로 덮으므로 인덱스를 건드리기 전에 멈춘다
        pages = ctx.item_meta.get("pages")
        if isinstance(pages, (int, float)) and pages > 0:
            raise StageError(
                "artifact_missing",
                f"PDF 가 있던 문서(pages={pages})라 초록으로 대체하지 않는다 — {_se}",
            ) from _se
        # PDF 없는 메타데이터 전용 논문 — abstract를 임베딩 텍스트로 사용
        full_text = ""
        page_map = {}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_embed_index_guard.py -q`
Expected: `6 passed`

Run: 전체 스위트(위 명령) — Expected: 시작 전 수 +2, 실패 0 (검증 사본 `892 passed`).

기존 4개 테스트를 고치지 않아도 되는 이유: 모두 `StageContext(book_id=…)` 로 만들어 `item_meta` 가 빈 dict 다 — PDF 없는 메타데이터 전용 논문과 같은 경로를 탄다.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/services/ingestion/stages.py app/tests/test_embed_index_guard.py
git commit -m "[Fix] round07 — 추출 아티팩트가 없을 때 PDF 가 있던 문서(meta.pages > 0)는 초록으로 색인하지 않고 artifact_missing 으로 멈춘다(마무리가 아티팩트를 지운 뒤 옛 체인의 embed 가 본문 청크를 초록으로 덮던 경로, 함정 16). PDF 없는 메타데이터 전용 논문은 지금처럼 초록으로 색인한다. 단계에 아이템 meta 를 넘기도록 StageContext 에 item_meta 를 더한다"
```

---

#### 2-2. 실행 토큰·체인 정지·`stage_running` (job_runtime.py)

- [ ] **Step 1: 실패하는 테스트를 쓴다** — 새 파일 `app/tests/test_job_runtime.py`

```python
"""test_job_runtime.py — 배치 잡 레이어: 실행 토큰·체인 정지·재시도·stale 판정

`workers.job_runtime` 은 celery(태스크 데코레이터·chain)와 redis(core.lock)를 물고 온다.
둘 다 로컬 venv 에 없어 최상단에서 import 하면 pytest 가 collection 단계에서 세션 전체를
죽인다(`docs/ops/recurring-gotchas.md` 13번). 그래서 test_research_tasks.py 처럼 더미를
꽂고 함수 안에서 import 한다. celery 는 설치돼 있어도 늘 이 파일의 더미를 쓴다 — `.si()`
로 만든 서명과 `Ignore` 를 단언해야 해서다.

DB 는 SQLite 다(history_sqlite.py 와 같은 방식 — JSONB 를 JSON 으로 그리고 '::jsonb' 서버
기본값을 뺀다). 디스패처가 내는 조건(백오프 시각 비교·상태·attempt 한도)을 실제 엔진이
판정해야 조건이 빠진 회귀를 잡는다.

`Ignore` 가 체인을 멈추는 것은 Celery 의 동작이라 여기서는 "Ignore 를 던지고 아이템을
바꾸지 않는다"까지만 본다. 근거: celery 5.4 `celery/app/trace.py` 는 체인의 다음 태스크를
성공 분기(`else:`)에서만 보내고, `celery/worker/request.py` 는 Ignore 를 ack 한다.
"""
import datetime as _dt
import importlib
import sys
import types
import uuid
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import history_sqlite  # noqa: F401 — JSONB 를 SQLite 에서 JSON 으로 그리는 컴파일 규칙
from models.ingest_job import IngestJob, IngestJobItem
from services.ingestion.stages import StageError

_CACHED = ("workers.job_runtime", "workers.celery_app", "core.lock")
NOW = _dt.datetime(2026, 10, 1, 12, 0, 0, tzinfo=_dt.timezone.utc)
STAGES = ("extract", "summarize", "embed_index", "finalize")


def _ago(seconds: float) -> _dt.datetime:
    return NOW - _dt.timedelta(seconds=seconds)


# ── celery 대역 ────────────────────────────────────────────────────────
class _Ignore(Exception):
    """celery.exceptions.Ignore 대역 — 진짜처럼 Exception 의 하위다(그래서 except Exception 밖에서 던져야 한다)."""


class _Sig:
    def __init__(self, task_name: str, args: tuple):
        self.task_name = task_name
        self.args = args


class _Chain:
    """celery.chain 대역 — 받은 서명을 남기고 apply_async 는 태스크 id 만 돌려준다."""

    def __init__(self, *sigs):
        self.sigs = list(sigs)

    def apply_async(self):
        return types.SimpleNamespace(id=f"celery-{uuid.uuid4().hex[:8]}")


class _Task:
    def __init__(self, fn, name: str):
        self.fn = fn
        self.name = name

    def __call__(self, *a, **kw):
        return self.fn(*a, **kw)

    def si(self, *args):
        return _Sig(self.name, args)


class _Conf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _Celery:
    def __init__(self, *a, **kw):
        self.conf = _Conf()

    def task(self, *a, **kw):
        def _decorator(fn):
            return _Task(fn, kw.get("name"))
        return _decorator


def _stub_missing(monkeypatch, name: str) -> None:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())


def _forget_on_teardown(monkeypatch, names: tuple[str, ...]) -> None:
    """names 를 sys.modules 와 부모 패키지 속성에서 빼고, 테스트가 끝나면 import 전 그대로 되돌린다
    (test_research_tasks.py 의 같은 이름 함수 주석 참고)."""
    for name in names:
        parent, _, child = name.rpartition(".")
        monkeypatch.setattr(importlib.import_module(parent), child, None, raising=False)
        monkeypatch.setitem(sys.modules, name, None)
        del sys.modules[name]


def _load_runtime(monkeypatch, ingest_states: list):
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _Celery
    celery_mod.chain = _Chain
    celery_exc = types.ModuleType("celery.exceptions")
    celery_exc.Ignore = _Ignore
    celery_exc.SoftTimeLimitExceeded = type("SoftTimeLimitExceeded", (Exception,), {})
    monkeypatch.setitem(sys.modules, "celery", celery_mod)
    monkeypatch.setitem(sys.modules, "celery.exceptions", celery_exc)
    _stub_missing(monkeypatch, "redis")
    # _run_stage 가 함수 안에서 import 하는 workers.tasks — 진짜는 적재 태스크 전부를 끌고 온다
    tasks_mod = types.ModuleType("workers.tasks")
    tasks_mod._set_ingest_state = lambda book_id, state, **kw: ingest_states.append((book_id, state))
    monkeypatch.setitem(sys.modules, "workers.tasks", tasks_mod)
    _forget_on_teardown(monkeypatch, _CACHED)
    return importlib.import_module("workers.job_runtime")


# ── DB ─────────────────────────────────────────────────────────────────
def _make_engine() -> sa.Engine:
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    metadata = sa.MetaData()
    for table in (IngestJob.__table__, IngestJobItem.__table__):
        copy = table.to_metadata(metadata)
        for col in copy.columns:
            default = col.server_default
            if default is not None and "::" in str(getattr(default, "arg", "")):
                col.server_default = None
    metadata.create_all(engine)
    return engine


def _snapshot(row) -> dict:
    return {
        "stage": row.stage, "status": row.status, "attempt": row.attempt,
        "meta": dict(row.meta or {}), "error_group": row.error_group,
        "last_error": row.last_error, "celery_task_id": row.celery_task_id,
        "updated_at": row.updated_at,
    }


class _Env:
    """잡 하나 + 아이템들 + 대역(락·단계 함수). 행은 매번 새 세션으로 읽는다 — 코드가 커밋한 값만 보인다."""

    def __init__(self, monkeypatch):
        self.ingest_states: list[tuple] = []
        self.rt = _load_runtime(monkeypatch, self.ingest_states)
        self.engine = _make_engine()
        self.Session = sessionmaker(bind=self.engine, autoflush=False)
        self.job_id = uuid.uuid4()
        with self.Session() as s:
            s.add(IngestJob(id=self.job_id, name="kci-test", status="running", params={},
                            total_items=0))
            s.commit()

        rt = self.rt
        monkeypatch.setattr(rt, "SyncSessionLocal", self.Session)
        monkeypatch.setattr(rt, "_now", lambda: NOW)
        monkeypatch.setattr(rt.cfg, "INGEST_MAX_ATTEMPTS", 3)
        monkeypatch.setattr(rt.cfg, "INGEST_HIGH_WATER", 32)
        monkeypatch.setattr(rt.cfg, "INGEST_RETRY_BACKOFF_SECONDS", "120,600")
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_EXTRACT", 3600)
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_SUMMARIZE", 1200)
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_EMBED", 1200)
        monkeypatch.setattr(rt.cfg, "INGEST_STAGE_TIMEOUT_FINALIZE", 900)
        monkeypatch.setattr(rt, "DISPATCH_STALE_SECONDS", 14400)

        # 락 대역 — lock_free=False 면 다른 워커가 쥐고 있는 것처럼 acquire 가 실패한다
        self.lock_free = True
        self.locks: list = []
        env = self

        class _Lock:
            def __init__(self, book_id, ttl=None):
                self.book_id, self.ttl, self.released = book_id, ttl, False
                env.locks.append(self)

            def acquire(self):
                return env.lock_free

            def release(self):
                self.released = True
                return True

        monkeypatch.setattr(rt, "BookLock", _Lock)

        # 단계 함수 대역 — 호출(ctx)과, 호출 순간 DB 에 적혀 있던 meta 를 남긴다
        self.calls: list[tuple[str, object]] = []
        self.meta_during: list[dict] = []
        self.results: dict[str, dict] = {}
        self.errors: dict[str, Exception] = {}

        def _make(name):
            def _fn(ctx):
                env.calls.append((name, ctx))
                env.meta_during.append(dict(env.item(ctx.job_item_id).meta or {}))
                if name in env.errors:
                    raise env.errors[name]
                return dict(env.results.get(name, {}))
            return _fn

        monkeypatch.setattr(rt, "STAGE_FUNCS", {s: _make(s) for s in STAGES})

        # 디스패처가 보낸 체인 — (체크포인트, item_id, 토큰, 서명들)
        self.sent: list[types.SimpleNamespace] = []
        real_build = rt.build_item_chain

        def _record(item_stage, item_id, run_token=None):
            sig = real_build(item_stage, item_id, run_token)
            if sig is not None:
                self.sent.append(types.SimpleNamespace(
                    stage=item_stage, item_id=item_id, token=run_token, sigs=sig.sigs))
            return sig

        monkeypatch.setattr(rt, "build_item_chain", _record)

    def add_item(self, item_id, *, stage="pending", status="pending", attempt=0, meta=None,
                 error_group=None, last_error=None, updated_at=None):
        with self.Session() as s:
            s.add(IngestJobItem(
                id=item_id, job_id=self.job_id, book_id=f"KCI_{item_id:04d}",
                source_key=f"originals/KCI_{item_id:04d}.pdf", stage=stage, status=status,
                attempt=attempt, meta=dict(meta or {}), stage_timings={},
                error_group=error_group, last_error=last_error,
                updated_at=updated_at or _ago(3600),
            ))
            s.commit()

    def item(self, item_id):
        with self.Session() as s:
            return s.get(IngestJobItem, item_id)

    def set_job(self, **values):
        with self.Session() as s:
            job = s.get(IngestJob, self.job_id)
            for key, value in values.items():
                setattr(job, key, value)
            s.commit()

    def dispatch(self) -> int:
        with self.Session() as s:
            return self.rt._dispatch_for_job(s, s.get(IngestJob, self.job_id))

    def recover_stale(self) -> int:
        with self.Session() as s:
            return self.rt._recover_stale(s, s.get(IngestJob, self.job_id))


@pytest.fixture
def env(monkeypatch):
    return _Env(monkeypatch)


# ── _run_stage: 실행하지 않고 체인을 멈추는 경우 ─────────────────────────
class TestStopsChain:
    """옛 체인·재전달 메시지·이미 끝난 단계는 Ignore 로 체인을 멈추고 아이템을 건드리지 않는다.

    dict 를 돌려주면 Celery 는 성공으로 보고 체인의 다음 단계를 보낸다 — 함정 16번에서
    재전달된 옛 체인의 embed_index 가 아티팩트 없이 돌아 논문 본문을 초록으로 덮은 경로다.
    """

    def _assert_stopped(self, env, item_id, before):
        assert env.calls == [], "단계 함수가 돌면 안 된다"
        assert _snapshot(env.item(item_id)) == before, "아이템 상태를 바꾸면 안 된다"
        assert env.ingest_states == []

    def test_token_mismatch(self, env):
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "new"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-old", "old")

        self._assert_stopped(env, 1, before)

    def test_old_message_without_token_on_tokened_item(self, env):
        # 배포 전에 보낸 메시지는 토큰 인자가 없다 — 아이템에 토큰이 있으면 새 체인이 떴다는 뜻이다
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "new"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-legacy", None)

        self._assert_stopped(env, 1, before)

    def test_stage_already_passed(self, env):
        # 체크포인트가 summarized — 같은 토큰이어도 요약을 다시 돌리지 않는다(재전달)
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_finalized_item(self, env):
        env.add_item(1, stage="finalized", status="done", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_done_status_even_if_stage_remains(self, env):
        env.add_item(1, stage="indexed", status="done", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("finalize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_canceled_item(self, env):
        env.add_item(1, stage="extracted", status="canceled", meta={"run_token": "t"})
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_canceled_job(self, env):
        env.add_item(1, stage="extracted", status="running", meta={"run_token": "t"})
        env.set_job(status="canceled")
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)

    def test_lock_contention_keeps_status(self, env):
        # 예전에는 pending 으로 되돌리고 dict 를 돌려줘 체인이 다음 단계로 갔다. pending 으로
        # 되돌리면 디스패처가 새 토큰으로 또 보내, 락을 쥐고 일하는 체인을 끊고 경합을 되풀이한다
        env.add_item(1, stage="extracted", status="dispatched", meta={"run_token": "t"})
        env.lock_free = False
        before = _snapshot(env.item(1))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        self._assert_stopped(env, 1, before)
        assert env.locks and not env.locks[0].released, "쥐지 못한 락은 풀지 않는다"

    def test_missing_item(self, env):
        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("extract", 999, "celery-1", "t")
        assert env.calls == []

    def test_item_is_read_with_row_lock(self, env):
        """디스패처는 메시지를 보낸 뒤 루프 끝에서 토큰을 커밋한다. 워커가 그 전에 아이템을 읽으면
        옛 토큰을 보고 새 체인을 멈춘다 — 그래서 첫 읽기는 FOR UPDATE 로 디스패처의 행 잠금
        (SELECT … FOR UPDATE SKIP LOCKED)이 풀릴 때까지 기다린다. SQLite 는 잠금을 그리지
        않으므로 같은 문장을 Postgres 로 컴파일해 본다."""
        env.add_item(1, stage="summarized", status="running", meta={"run_token": "new"})
        selects: list[str] = []

        @event.listens_for(env.Session, "do_orm_execute")
        def _record(state):
            if state.is_select:
                selects.append(str(state.statement.compile(dialect=postgresql.dialect())))

        with pytest.raises(env.rt.Ignore):
            env.rt._run_stage("embed_index", 1, "celery-old", "old")

        item_reads = [s for s in selects if "FROM ingest_job_items" in s]
        assert item_reads and "FOR UPDATE" in item_reads[0]


# ── _run_stage: 실행 ─────────────────────────────────────────────────────
class TestRunsStage:
    def test_matching_token_runs_and_marks_stage_running(self, env):
        env.add_item(1, stage="extracted", status="dispatched",
                     meta={"run_token": "t", "pages": 12})
        env.results["summarize"] = {"sections_total": 3}

        out = env.rt._run_stage("summarize", 1, "celery-1", "t")

        assert out["stage"] == "summarize"
        # 단계가 도는 동안에는 이름과 시작 시각이 적혀 있다 — stale 판정이 이것으로 실행 시간을 잰다
        during = env.meta_during[0]
        assert during["stage_running"] == "summarize"
        assert _dt.datetime.fromisoformat(during["stage_started_at"]) == NOW
        row = env.item(1)
        assert row.stage == "summarized" and row.status == "running"
        assert row.meta["stage_running"] is None, "끝나면 지운다 — 남아 있으면 대기를 실행으로 잰다"
        assert row.meta["stage_started_at"] == NOW.isoformat()
        assert row.meta["sections_total"] == 3 and row.meta["run_token"] == "t"
        assert env.locks[0].released

    def test_stage_context_carries_item_meta(self, env):
        env.add_item(1, stage="summarized", status="dispatched",
                     meta={"run_token": "t", "pages": 12})

        env.rt._run_stage("embed_index", 1, "celery-1", "t")

        _, ctx = env.calls[0]
        assert ctx.item_meta["pages"] == 12, "embed 가드가 PDF 가 있던 문서인지 meta.pages 로 판단한다"

    def test_old_message_runs_on_item_without_token(self, env):
        # 배포 전 아이템(토큰 없음)의 옛 메시지는 예전처럼 돈다
        env.add_item(1, stage="pending", status="dispatched", meta={})

        env.rt._run_stage("extract", 1, "celery-legacy", None)

        assert [c[0] for c in env.calls] == ["extract"]
        assert env.item(1).stage == "extracted"

    def test_finalize_marks_done_and_clears_stage_running(self, env):
        env.add_item(1, stage="indexed", status="running", meta={"run_token": "t"})

        env.rt._run_stage("finalize", 1, "celery-1", "t")

        row = env.item(1)
        assert row.status == "done" and row.stage == "finalized"
        assert row.meta["stage_running"] is None
        assert env.ingest_states == [("KCI_0001", "embedded")]

    def test_failure_clears_stage_running_and_bumps_attempt(self, env):
        env.add_item(1, stage="extracted", status="dispatched", attempt=0,
                     meta={"run_token": "t"})
        env.errors["summarize"] = StageError("llm_error", "섹션 요약 전체 실패 (3건)")

        with pytest.raises(StageError):
            env.rt._run_stage("summarize", 1, "celery-1", "t")

        row = env.item(1)
        assert row.status == "failed" and row.error_group == "llm_error"
        assert row.attempt == 1 and row.stage == "extracted"
        assert row.meta["stage_running"] is None
        assert env.locks[0].released


# ── 단계 태스크·체인 ───────────────────────────────────────────────────
class TestTasksAndChain:
    def test_build_item_chain(self, monkeypatch):
        rt = _load_runtime(monkeypatch, [])

        sig = rt.build_item_chain("summarized", 9, "tok")

        assert [s.task_name for s in sig.sigs] == ["tasks.stage_embed_index", "tasks.stage_finalize"]
        assert all(s.args == (9, "tok") for s in sig.sigs)
        assert rt.build_item_chain("finalized", 9, "tok") is None

    def test_stage_tasks_pass_token_and_accept_old_messages(self, monkeypatch):
        rt = _load_runtime(monkeypatch, [])
        seen = []
        monkeypatch.setattr(rt, "_run_stage", lambda *a: seen.append(a) or {})
        task_self = types.SimpleNamespace(request=types.SimpleNamespace(id="celery-9"))

        rt.stage_embed_index.fn(task_self, 9, "tok")
        rt.stage_finalize.fn(task_self, 9)   # 배포 전 메시지 — 토큰 인자가 없다

        assert seen == [("embed_index", 9, "celery-9", "tok"), ("finalize", 9, "celery-9", None)]


# ── 디스패처: 실행 토큰 ────────────────────────────────────────────────
class TestDispatchToken:
    def test_each_chain_gets_a_fresh_token(self, env):
        env.add_item(1, meta={"pages": 4})
        env.add_item(2)

        assert env.dispatch() == 2

        tokens = {s.item_id: s.token for s in env.sent}
        assert len(set(tokens.values())) == 2 and all(tokens.values())
        for s in env.sent:
            assert all(sig.args == (s.item_id, s.token) for sig in s.sigs)
            row = env.item(s.item_id)
            assert row.meta["run_token"] == s.token and row.status == "dispatched"
        assert env.item(1).meta["pages"] == 4, "다른 meta 키는 그대로 둔다"

    def test_redispatch_replaces_token(self, env):
        env.add_item(1, stage="extracted", status="failed", attempt=1,
                     error_group="stale", meta={"run_token": "old"}, updated_at=_ago(1000))

        env.dispatch()

        assert env.sent[0].token != "old"
        assert env.item(1).meta["run_token"] == env.sent[0].token
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_job_runtime.py -q`
Expected: `19 failed` — `AttributeError: module 'workers.job_runtime' has no attribute 'Ignore'`, `TypeError: _run_stage() takes 3 positional arguments but 4 were given`, `TypeError: build_item_chain() takes 2 positional arguments but 3 were given`, `TypeError: stage_embed_index() takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: 최소 구현** — `app/workers/job_runtime.py`

(a) 모듈 docstring 의 핵심 규칙 — old:
```python
  - item.status = 실행 상태. 자동 재시도: failed && attempt < max_attempts 인 아이템을
    디스패처가 다시 픽업 (수동 재시도 API는 status='pending' + attempt 리셋)
"""
```
new:
```python
  - item.status = 실행 상태. 자동 재시도: failed && attempt < max_attempts 인 아이템을
    디스패처가 다시 픽업 (수동 재시도 API는 status='pending' + attempt 리셋)
  - 실행 토큰: 디스패처가 체인을 보낼 때마다 새 meta.run_token 을 적고 모든 단계에 넘긴다.
    단계 래퍼는 토큰이 다르거나·이미 지난 단계거나·락 경합이면 Ignore 로 체인을 멈춘다
    (stale 복구 전의 옛 체인·재전달 메시지가 같은 아이템을 다시 돌지 못하게 — 함정 16)
"""
```

(b) import — old:
```python
import time

from celery import chain

from core.config import get_settings
```
new:
```python
import time
import uuid

from celery import chain
from celery.exceptions import Ignore

from core.config import get_settings
```

(c) `_run_stage` 를 지우고 그 자리에 아래를 넣는다 — 새 함수 `_skip_reason` + 바뀐 `_run_stage`(시그니처에 `run_token`, 실행 판단은 모두 `try` 밖, 첫 읽기 `FOR UPDATE`, 락 경합은 상태를 두고 `Ignore`, `stage_running`·`stage_started_at` 기록과 해제, `StageContext(item_meta=…)`):
```python
def _skip_reason(stage_name: str, item, job, run_token: str | None) -> str | None:
    """이 단계 메시지를 실행하지 않을 이유. 이유가 있으면 _run_stage 가 체인을 멈춘다."""
    if item is None:
        return "아이템 없음"
    if item.status == "canceled" or (job is not None and job.status == "canceled"):
        return "취소됨"
    current = (item.meta or {}).get("run_token")
    if run_token is not None and run_token != current:
        return f"실행 토큰 불일치(메시지 {run_token[:8]}, 아이템 {str(current)[:8]}) — 옛 체인"
    if run_token is None and current:
        return "토큰 없는 옛 메시지인데 아이템에는 실행 토큰이 있다 — 새 체인이 떴다"
    if item.status == "done":
        return "이미 완료(done)"
    if stage_name not in CHECKPOINT_TO_REMAINING.get(item.stage, list(STAGE_CHECKPOINT)):
        return f"이미 지난 단계(체크포인트 {item.stage})"
    return None


def _run_stage(
    stage_name: str, item_id: int, celery_task_id: str | None, run_token: str | None = None,
) -> dict:
    """단계 하나를 실행한다. 실행하지 않을 때는 Ignore 를 던져 체인을 멈춘다.

    Ignore 는 Exception 의 하위라 아래 except Exception 안에서 던지면 실패로 기록된다 —
    그래서 실행 판단은 모두 그 try 밖에서 한다. Celery 는 Ignore 를 던진 태스크의 상태를
    남기지 않고 메시지를 ack 하며, 체인의 다음 단계는 성공했을 때만 보낸다.
    """
    from workers.tasks import _set_ingest_state

    db = SyncSessionLocal()
    try:
        # FOR UPDATE: 디스패처는 메시지를 보낸 뒤 루프 끝에서 토큰을 커밋한다. 그 전에 읽으면
        # 옛 토큰을 보고 새 체인을 멈추므로, 디스패처의 행 잠금이 풀릴 때까지 기다렸다 읽는다
        item = db.query(IngestJobItem).filter_by(id=item_id).with_for_update().first()
        job = db.query(IngestJob).filter_by(id=item.job_id).first() if item else None
        reason = _skip_reason(stage_name, item, job, run_token)
        if reason:
            book = item.book_id if item else "-"
            log.warning(f"[{book}] item={item_id} {stage_name} 실행 안 함 — {reason} → 체인 정지")
            raise Ignore(reason)
        book_id = item.book_id
        source_key = item.source_key
        params = dict(job.params or {}) if job else {}
        item_meta = dict(item.meta or {})
    finally:
        db.close()

    timeout = _stage_timeout(stage_name)
    lock = BookLock(book_id, ttl=timeout)
    if not lock.acquire():
        # 다른 워커가 이 문서를 처리 중이다. pending 으로 되돌리면 디스패처가 새 토큰으로 다시
        # 보내 락을 쥔 체인의 다음 단계를 끊고 경합을 되풀이한다 — 상태는 그대로 두고 이 체인만
        # 멈춘다. 아이템이 그대로 멈춰 있으면 stale 복구가 회수한다
        log.warning(f"[{book_id}] item={item_id} {stage_name} 실행 안 함 — 락 경합 → 체인 정지")
        raise Ignore("락 경합")

    t0 = time.monotonic()
    _update_item(
        item_id,
        status="running",
        celery_task_id=celery_task_id,
        set_started=True,
        # stale 판정이 실행 시간을 이 시각부터 잰다 — 끝나면 stage_running 을 지운다
        meta_update={"stage_running": stage_name, "stage_started_at": _now().isoformat()},
    )
    if stage_name == "extract":
        _set_ingest_state(book_id, "processing", task_id=celery_task_id)

    try:
        ctx = StageContext(
            book_id=book_id,
            source_key=source_key,
            job_item_id=item_id,
            params=params,
            item_meta=item_meta,
        )
        result = STAGE_FUNCS[stage_name](ctx) or {}
        elapsed = round(time.monotonic() - t0, 1)

        is_final = stage_name == "finalize"
        _update_item(
            item_id,
            stage=STAGE_CHECKPOINT[stage_name],
            status="done" if is_final else "running",
            timing=(stage_name, elapsed),
            meta_update={**result, "stage_running": None},
            set_finished=is_final,
        )
        if is_final:
            _set_ingest_state(book_id, "embedded", task_id=celery_task_id)
        return {"item_id": item_id, "stage": stage_name, "elapsed_s": elapsed}
    except Exception as e:
        group = classify_error(e)
        log.exception(f"[{book_id}] item={item_id} {stage_name} 실패 ({group}): {e}")
        _update_item(
            item_id,
            status="failed",
            error_group=group,
            last_error=str(e)[:2000],
            bump_attempt=True,
            timing=(stage_name, round(time.monotonic() - t0, 1)),
            meta_update={"stage_running": None},
        )
        _set_ingest_state(book_id, "failed", task_id=celery_task_id, error=str(e))
        raise  # 체인 중단 (남은 단계 실행 안 함)
    finally:
        lock.release()
```

(d) `_update_item` 의 meta 주석 — old:
```python
            # JSON 직렬화 가능한 값만 기록
```
new:
```python
            # JSON 직렬화 가능한 값만 기록 (None 도 기록한다 — stage_running 을 지울 때 쓴다)
```

(e) 단계 태스크 넷(`@celery_app.task(name="tasks.stage_extract", …)` 부터 `stage_finalize` 끝까지)을 아래로 바꾼다:
```python
# run_token 기본값 None: 배포 전에 보낸 메시지(인자 item_id 하나)도 받는다 — _skip_reason 참고
@celery_app.task(name="tasks.stage_extract", bind=True, acks_late=True)
def stage_extract(self, item_id: int, run_token: str | None = None):
    return _run_stage("extract", item_id, self.request.id, run_token)


@celery_app.task(name="tasks.stage_summarize", bind=True, acks_late=True)
def stage_summarize(self, item_id: int, run_token: str | None = None):
    return _run_stage("summarize", item_id, self.request.id, run_token)


@celery_app.task(name="tasks.stage_embed_index", bind=True, acks_late=True)
def stage_embed_index(self, item_id: int, run_token: str | None = None):
    return _run_stage("embed_index", item_id, self.request.id, run_token)


@celery_app.task(name="tasks.stage_finalize", bind=True, acks_late=True)
def stage_finalize(self, item_id: int, run_token: str | None = None):
    return _run_stage("finalize", item_id, self.request.id, run_token)
```

(f) `build_item_chain` 을 아래로 바꾼다:
```python
def build_item_chain(item_stage: str, item_id: int, run_token: str | None = None):
    """체크포인트 기준 남은 단계 체인 구성. 남은 단계 없으면 None.

    모든 단계에 같은 실행 토큰을 싣는다 — 단계 래퍼가 아이템의 현재 토큰과 대조해 옛 체인을 멈춘다.
    """
    remaining = CHECKPOINT_TO_REMAINING.get(item_stage, list(STAGE_CHECKPOINT))
    if not remaining:
        return None
    return chain(*[_STAGE_TASKS[s].si(item_id, run_token) for s in remaining])
```

(g) `_dispatch_for_job` 의 루프 앞부분 — old:
```python
    dispatched = 0
    now = _now()
    for item in items:
        sig = build_item_chain(item.stage, item.id)
        if sig is None:
            item.status = "done"
            item.finished_at = now
            item.updated_at = now
            continue
        res = sig.apply_async()
```
new:
```python
    dispatched = 0
    now = _now()
    for item in items:
        # 체인마다 새 토큰 — 이 아이템의 옛 체인(stale 복구 전 체인·재전달 메시지)은 단계 래퍼가
        # 멈춘다. 토큰은 루프 끝 commit 에 보이고, 단계 래퍼의 첫 읽기(FOR UPDATE)가 그 commit 을
        # 기다린다(이 SELECT … FOR UPDATE 가 행을 잠그고 있다)
        run_token = uuid.uuid4().hex
        sig = build_item_chain(item.stage, item.id, run_token)
        if sig is None:
            item.status = "done"
            item.finished_at = now
            item.updated_at = now
            continue
        item.meta = {**(item.meta or {}), "run_token": run_token}
        res = sig.apply_async()
```

(h) `app/tests/test_backfill_summary.py` — 이 파일은 모듈 맨 위에서 `celery` 를 패키지가 아닌 MagicMock 으로 꽂는다. 이제 `workers.tasks` → `workers.job_runtime` 의 `from celery.exceptions import Ignore` 에서 수집이 죽는다(`ModuleNotFoundError: No module named 'celery.exceptions'; 'celery' is not a package` — 전체 스위트가 `Interrupted: 1 error during collection`). 그 파일의 기존 방식대로, 설치 안 된 경우에만 하위 모듈 더미를 꽂는다.

import — old:
```python
import importlib
import sys
from unittest.mock import MagicMock
```
new:
```python
import importlib
import sys
import types
from unittest.mock import MagicMock
```

더미 — old:
```python
    mod = MagicMock()
    mod.Celery = _FakeCeleryApp
    return mod


_stub_missing_module("celery", _make_fake_celery_module)
_stub_missing_module("redis", MagicMock)
```
new:
```python
    mod = MagicMock()
    mod.Celery = _FakeCeleryApp
    return mod


def _make_fake_celery_exceptions_module():
    # workers.job_runtime 이 `from celery.exceptions import Ignore` 를 한다. 위 더미 celery 는
    # 패키지가 아니라 하위 모듈을 찾지 못하므로 따로 꽂는다. except 절·raise 에 쓰이니 진짜 예외 클래스다
    mod = types.ModuleType("celery.exceptions")
    mod.Ignore = type("Ignore", (Exception,), {})
    mod.SoftTimeLimitExceeded = type("SoftTimeLimitExceeded", (Exception,), {})
    return mod


_stub_missing_module("celery", _make_fake_celery_module)
_stub_missing_module("celery.exceptions", _make_fake_celery_exceptions_module)
_stub_missing_module("redis", MagicMock)
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_job_runtime.py tests/test_backfill_summary.py -q`
Expected: `22 passed` (job_runtime 19 + backfill 3)

Run: 전체 스위트 — Expected: 2-1 뒤 수 +19, 실패 0 (검증 사본 `911 passed`).

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/workers/job_runtime.py app/tests/test_job_runtime.py app/tests/test_backfill_summary.py
git commit -m "[Fix] round07 — 실행 토큰: 디스패처가 체인을 보낼 때마다 meta.run_token 을 새로 적어 모든 단계에 넘기고, 단계 래퍼는 토큰 불일치·토큰 없는 옛 메시지·이미 지난 단계·done·취소·락 경합이면 Ignore 로 체인을 멈춘다(락 경합에 pending 으로 되돌리지 않는다 — 새 토큰이 락을 쥔 체인을 끊고 경합을 되풀이한다). 첫 읽기는 FOR UPDATE 로 디스패처의 토큰 커밋을 기다리고, 단계가 도는 동안 meta.stage_running·stage_started_at 을 적는다. backfill 테스트의 celery 더미에 celery.exceptions 를 더한다"
```

---

#### 2-3. 재시도 — 결정적 실패 제외·추출부터 다시·백오프 (job_runtime.py)

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `app/tests/test_job_runtime.py` 끝에 덧붙인다.

```python
# ── 재시도: 결정적 실패 제외·추출부터 다시·백오프 ─────────────────────
class TestRetryPolicy:
    def test_no_text_exhausts_attempts(self, env):
        """같은 코드로 다시 해도 결과가 같은 실패 — 자동 재시도에서 뺀다."""
        env.add_item(1, stage="pending", status="dispatched", attempt=0, meta={"run_token": "t"})
        env.errors["extract"] = StageError("no_text", "강제 OCR 뒤에도 섹션 0개")

        with pytest.raises(StageError):
            env.rt._run_stage("extract", 1, "celery-1", "t")

        assert env.item(1).attempt == 3   # cfg.INGEST_MAX_ATTEMPTS

    def test_no_text_uses_job_max_attempts(self, env):
        env.set_job(params={"max_attempts": 5})
        env.add_item(1, stage="pending", status="dispatched", attempt=1, meta={"run_token": "t"})
        env.errors["extract"] = StageError("no_text", "강제 OCR 뒤에도 섹션 0개")

        with pytest.raises(StageError):
            env.rt._run_stage("extract", 1, "celery-1", "t")

        assert env.item(1).attempt == 5

    def test_no_text_item_is_not_picked_again(self, env, monkeypatch):
        env.add_item(1, stage="pending", status="dispatched", attempt=0, meta={"run_token": "t"})
        env.errors["extract"] = StageError("no_text", "강제 OCR 뒤에도 섹션 0개")
        with pytest.raises(StageError):
            env.rt._run_stage("extract", 1, "celery-1", "t")
        monkeypatch.setattr(env.rt, "_now", lambda: NOW + _dt.timedelta(days=1))   # 백오프는 한참 지났다

        assert env.dispatch() == 0
        assert env.item(1).status == "failed"

    def test_section_missing_failure_restarts_from_extract(self, env):
        # 옛 코드가 섹션 0개를 추출 성공으로 넘겨 요약에서 실패한 아이템 — 요약부터 다시 하면 같은 실패다
        env.add_item(1, stage="extracted", status="failed", attempt=1, error_group="not_found",
                     last_error="섹션 없음 — extract 단계부터 재실행 필요", updated_at=_ago(1000))

        env.dispatch()

        assert env.item(1).stage == "pending"
        assert env.sent[0].sigs[0].task_name == "tasks.stage_extract"

    def test_vlm_error_restarts_from_extract(self, env):
        env.add_item(1, stage="extracted", status="failed", attempt=1, error_group="vlm_error",
                     last_error="VLM 호출 실패", updated_at=_ago(1000))

        env.dispatch()

        assert env.item(1).stage == "pending"
        assert env.sent[0].sigs[0].task_name == "tasks.stage_extract"

    def test_other_failures_keep_checkpoint(self, env):
        env.add_item(1, stage="extracted", status="failed", attempt=1, error_group="not_found",
                     last_error="카탈로그 row 없음 — extract 단계부터 재실행 필요", updated_at=_ago(1000))
        env.add_item(2, stage="extracted", status="failed", attempt=1, error_group="llm_error",
                     last_error="섹션 요약 전체 실패 (3건)", updated_at=_ago(1000))

        env.dispatch()

        assert env.item(1).stage == "extracted" and env.item(2).stage == "extracted"
        assert {s.sigs[0].task_name for s in env.sent} == {"tasks.stage_summarize"}

    def test_backoff_by_attempt(self, env):
        env.set_job(params={"max_attempts": 5})
        env.add_item(1, status="failed", attempt=1, updated_at=_ago(100))   # 120초 전 — 대기
        env.add_item(2, status="failed", attempt=1, updated_at=_ago(120))   # 딱 120초 — 집는다
        env.add_item(3, status="failed", attempt=2, updated_at=_ago(500))   # 600초 전 — 대기
        env.add_item(4, status="failed", attempt=2, updated_at=_ago(700))
        env.add_item(5, status="failed", attempt=3, updated_at=_ago(500))   # 값이 모자라면 마지막(600) 반복
        env.add_item(6, status="failed", attempt=3, updated_at=_ago(700))
        env.add_item(7, status="pending", attempt=0, updated_at=NOW)        # pending 은 백오프 없음

        env.dispatch()

        assert sorted(s.item_id for s in env.sent) == [2, 4, 6, 7]
        assert env.item(1).status == "failed" and env.item(3).status == "failed"

    def test_items_in_backoff_do_not_block_pending(self, env):
        env.set_job(params={"high_water": 2})
        for item_id in range(1, 6):   # id 가 앞선 실패 5건이 모두 백오프 중
            env.add_item(item_id, status="failed", attempt=1, updated_at=_ago(10))
        env.add_item(6)
        env.add_item(7)
        env.add_item(8)

        assert env.dispatch() == 2

        assert [s.item_id for s in env.sent] == [6, 7], "id 순서는 지키고 백오프 중인 실패는 건너뛴다"

    def test_exhausted_attempts_not_picked(self, env):
        env.add_item(1, status="failed", attempt=3, updated_at=_ago(100000))

        assert env.dispatch() == 0

    def test_backoff_setting_parsing(self, env, monkeypatch):
        # 디스패처는 30초마다 이 값을 읽는다 — 잘못된 칸 하나로 디스패처가 죽으면 적재가 멈춘다
        for raw, want in {"120,600": [120, 600], " 30 , x ,90": [30, 90], "": []}.items():
            monkeypatch.setattr(env.rt.cfg, "INGEST_RETRY_BACKOFF_SECONDS", raw)
            assert env.rt._retry_backoff_steps() == want, raw

    def test_empty_backoff_setting_means_no_wait(self, env, monkeypatch):
        monkeypatch.setattr(env.rt.cfg, "INGEST_RETRY_BACKOFF_SECONDS", "")
        env.add_item(1, status="failed", attempt=1, updated_at=_ago(10))

        assert env.dispatch() == 1
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_job_runtime.py -q`
Expected: `8 failed, 22 passed` — `assert 1 == 3`·`assert 2 == 5`(no_text 의 attempt), `assert 1 == 0`(no_text 를 다시 집음), `AssertionError: assert 'extracted' == 'pending'`(둘), `assert [1, 2, 3, 4, 5, 6, ...] == [2, 4, 6, 7]`, `assert [1, 2] == [6, 7]`, `AttributeError: module 'workers.job_runtime' has no attribute '_retry_backoff_steps'`. `test_other_failures_keep_checkpoint`·`test_exhausted_attempts_not_picked`·`test_empty_backoff_setting_means_no_wait` 는 지금 동작(또는 백오프 없음)을 지키는 테스트라 이미 통과한다.

- [ ] **Step 3: 최소 구현** — `app/workers/job_runtime.py`

(a) docstring — old:
```python
    디스패처가 다시 픽업 (수동 재시도 API는 status='pending' + attempt 리셋)
```
new:
```python
    디스패처가 다시 픽업 (수동 재시도 API는 status='pending' + attempt 리셋).
    attempt 번째 실패 뒤에는 INGEST_RETRY_BACKOFF_SECONDS 만큼 기다렸다 집는다
```

(b) import — old:
```python
from celery.exceptions import Ignore

from core.config import get_settings
```
new:
```python
from celery.exceptions import Ignore
from sqlalchemy import and_, or_, true

from core.config import get_settings
```

(c) 재시도 불가 그룹 상수 — old:
```python
DISPATCH_STALE_SECONDS = cfg.DISPATCH_STALE_SECONDS
```
new:
```python
DISPATCH_STALE_SECONDS = cfg.DISPATCH_STALE_SECONDS

# 같은 코드로 다시 해도 결과가 같은 실패 — 자동 재시도하지 않는다(attempt 를 한도로 올린다)
NO_RETRY_GROUPS = frozenset({"no_text"})
```

(d) `_update_item` 시그니처 — old:
```python
    bump_attempt: bool = False,
    set_started: bool = False,
```
new:
```python
    bump_attempt: bool = False,
    min_attempt: int | None = None,
    set_started: bool = False,
```

본문 — old:
```python
        if bump_attempt:
            item.attempt = (item.attempt or 0) + 1
```
new:
```python
        if bump_attempt:
            item.attempt = (item.attempt or 0) + 1
        if min_attempt is not None:
            # 재시도 불가 실패 — 자동 재시도 조건(attempt < max_attempts)에서 빠지도록 올린다
            item.attempt = max(item.attempt or 0, min_attempt)
```

(e) `_run_stage` 두 곳 — old:
```python
    timeout = _stage_timeout(stage_name)
    lock = BookLock(book_id, ttl=timeout)
```
new:
```python
    max_attempts = int(params.get("max_attempts") or cfg.INGEST_MAX_ATTEMPTS)
    timeout = _stage_timeout(stage_name)
    lock = BookLock(book_id, ttl=timeout)
```

old:
```python
            bump_attempt=True,
            timing=(stage_name, round(time.monotonic() - t0, 1)),
```
new:
```python
            bump_attempt=True,
            # 결정적 실패는 다시 해도 같다 — attempt 를 한도로 올려 자동 재시도에서 뺀다
            min_attempt=max_attempts if group in NO_RETRY_GROUPS else None,
            timing=(stage_name, round(time.monotonic() - t0, 1)),
```

(f) `_dispatch_for_job` 를 지우고 그 자리에 아래를 넣는다 — 새 함수 `_retry_backoff_steps`·`_retry_ready`·`_needs_reextract` + 바뀐 `_dispatch_for_job`(`now` 를 쿼리 전에 잡고, 백오프 조건을 SQL 에, 집은 실패가 추출부터 다시 할 실패면 `stage = "pending"`):
```python
def _retry_backoff_steps() -> list[int]:
    """INGEST_RETRY_BACKOFF_SECONDS("120,600") → [120, 600]. 정수가 아닌 칸은 경고하고 건너뛴다."""
    steps: list[int] = []
    for part in str(cfg.INGEST_RETRY_BACKOFF_SECONDS or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            steps.append(max(0, int(part)))
        except ValueError:
            log.warning(f"INGEST_RETRY_BACKOFF_SECONDS 의 '{part}' 는 초(정수)가 아니다 — 건너뜀")
    return steps


def _retry_ready(now: _dt.datetime):
    """failed 아이템 가운데 백오프가 지난 것 — attempt 번째 실패 뒤 steps[attempt-1] 초를
    updated_at(실패를 기록한 시각)부터 기다린다. 값이 모자라면 마지막 값을 되풀이한다."""
    steps = _retry_backoff_steps()
    if not steps:
        return true()
    conds = [IngestJobItem.attempt < 1]
    for n, wait in enumerate(steps, start=1):
        same = IngestJobItem.attempt >= n if n == len(steps) else IngestJobItem.attempt == n
        conds.append(and_(same, IngestJobItem.updated_at <= now - _dt.timedelta(seconds=wait)))
    return or_(*conds)


def _needs_reextract(item) -> bool:
    """자동 재시도를 추출부터 다시 해야 하는 실패인가.

    vlm_error: OCR 이 VLM 장애로 실패했다 — 추출을 다시 해야 본문이 생긴다.
    not_found '섹션 없음': 옛 코드가 섹션 0개를 추출 성공으로 넘겨 요약에서 실패했다.
    체크포인트(extracted)부터 다시 하면 같은 실패를 되풀이해 시도만 다 쓴다.
    """
    if item.error_group == "vlm_error":
        return True
    return item.error_group == "not_found" and "섹션 없음" in (item.last_error or "")


def _dispatch_for_job(db, job) -> int:
    params = dict(job.params or {})
    high_water = int(params.get("high_water") or cfg.INGEST_HIGH_WATER)
    max_attempts = int(params.get("max_attempts") or cfg.INGEST_MAX_ATTEMPTS)
    now = _now()

    in_flight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        .count()
    )
    need = high_water - in_flight
    if need <= 0:
        return 0

    # pending(신규/수동 재시도) + failed(자동 재시도, attempt < max, 백오프 지남).
    # 백오프를 SQL 조건으로 거른다 — limit 뒤 파이썬에서 거르면 id 가 앞선 백오프 중 실패가
    # limit 을 채워 뒤의 pending 을 막는다
    items = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.attempt < max_attempts,
            or_(
                IngestJobItem.status == "pending",
                and_(IngestJobItem.status == "failed", _retry_ready(now)),
            ),
        )
        .order_by(IngestJobItem.id)
        .limit(need)
        .with_for_update(skip_locked=True)
        .all()
    )

    dispatched = 0
    for item in items:
        if item.status == "failed" and item.stage != "pending" and _needs_reextract(item):
            log.info(
                f"[{item.book_id}] item={item.id} {item.error_group} 재시도 — "
                f"체크포인트 {item.stage} → pending (추출부터)"
            )
            item.stage = "pending"
        # 체인마다 새 토큰 — 이 아이템의 옛 체인(stale 복구 전 체인·재전달 메시지)은 단계 래퍼가
        # 멈춘다. 토큰은 루프 끝 commit 에 보이고, 단계 래퍼의 첫 읽기(FOR UPDATE)가 그 commit 을
        # 기다린다(이 SELECT … FOR UPDATE 가 행을 잠그고 있다)
        run_token = uuid.uuid4().hex
        sig = build_item_chain(item.stage, item.id, run_token)
        if sig is None:
            item.status = "done"
            item.finished_at = now
            item.updated_at = now
            continue
        item.meta = {**(item.meta or {}), "run_token": run_token}
        res = sig.apply_async()
        item.status = "dispatched"
        item.dispatched_at = now
        item.updated_at = now
        item.celery_task_id = res.id
        dispatched += 1
    db.commit()
    return dispatched
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_job_runtime.py -q`
Expected: `30 passed`

Run: 전체 스위트 — Expected: 2-2 뒤 수 +11, 실패 0 (검증 사본 `922 passed`).

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/workers/job_runtime.py app/tests/test_job_runtime.py
git commit -m "[Fix] round07 — 자동 재시도: 결정적 실패(no_text)는 attempt 를 한도로 올려 자동 재시도에서 빼고, vlm_error 와 '섹션 없음' 실패는 체크포인트를 pending 으로 되돌려 추출부터 다시 한다. 실패 재시도는 attempt 별 백오프(INGEST_RETRY_BACKOFF_SECONDS, 기본 120초·600초)가 지난 뒤에만 집고, 그 조건을 SQL 에 넣어 백오프 중인 실패가 뒤의 pending 을 막지 않게 한다"
```

---

#### 2-4. stale 판정 분리 + `DISPATCH_STALE_SECONDS` 주석 (job_runtime.py)

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `app/tests/test_job_runtime.py` 끝에 덧붙인다.

```python
# ── stale 판정: 실행 중 vs 다음 단계 대기 ────────────────────────────────
class TestRecoverStale:
    def test_running_stage_is_timed_from_its_start(self, env):
        env.add_item(1, stage="summarized", status="running", updated_at=_ago(5),
                     meta={"stage_running": "embed_index", "stage_started_at": _ago(1300).isoformat()})

        assert env.recover_stale() == 1

        row = env.item(1)
        assert row.status == "failed" and row.error_group == "stale" and row.attempt == 1
        assert "stale 복구" in row.last_error and "embed_index" in row.last_error

    def test_running_stage_within_timeout(self, env):
        env.add_item(1, stage="pending", status="running", updated_at=_ago(3500),
                     meta={"stage_running": "extract", "stage_started_at": _ago(3500).isoformat()})

        assert env.recover_stale() == 0
        assert env.item(1).status == "running"

    def test_waiting_for_next_stage_is_not_execution(self, env):
        # 임베딩을 끝내고 마무리(q_llm) 큐에서 2000초째 기다린다 — 예전에는 마무리 타임아웃
        # 900초로 재서 stale 로 오판하고 중복 체인을 열었다
        env.add_item(1, stage="indexed", status="running", updated_at=_ago(2000),
                     meta={"stage_running": None, "stage_started_at": _ago(2300).isoformat()})

        assert env.recover_stale() == 0
        assert env.item(1).status == "running"

    def test_waiting_beyond_dispatch_window(self, env):
        env.add_item(1, stage="indexed", status="running", updated_at=_ago(14500),
                     meta={"stage_running": None})

        assert env.recover_stale() == 1
        assert "다음 단계 대기" in env.item(1).last_error

    def test_item_without_stage_running_key_counts_as_waiting(self, env):
        # 배포 전에 마지막 단계를 끝낸 아이템은 meta 에 stage_running 키가 없다
        env.add_item(1, stage="indexed", status="running", updated_at=_ago(2000), meta={})

        assert env.recover_stale() == 0

    def test_dispatched_unchanged(self, env):
        env.add_item(1, stage="pending", status="dispatched", updated_at=_ago(2000))
        env.add_item(2, stage="pending", status="dispatched", updated_at=_ago(14500))

        assert env.recover_stale() == 1
        assert env.item(1).status == "dispatched" and env.item(2).status == "failed"
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_job_runtime.py -q`
Expected: `4 failed, 32 passed` — `test_running_stage_is_timed_from_its_start`(`assert 0 == 1` — 지금은 `updated_at` 부터 잰다), `test_waiting_for_next_stage_is_not_execution`·`test_item_without_stage_running_key_counts_as_waiting`(`assert 1 == 0` — 마무리 타임아웃 900초로 잰다), `test_waiting_beyond_dispatch_window`(`assert '다음 단계 대기' in '900s 무응답 — 워커 중단 추정 (stale 복구)'`). 나머지 둘은 지금 동작을 지키는 테스트다.

- [ ] **Step 3: 최소 구현** — `app/workers/job_runtime.py`

(a) 주석 — old:
```python
# 디스패치 후 워커가 잡기까지의 허용 대기 (큐 적체 고려 — visibility_timeout 의 2배)
```
new:
```python
# 큐에서 기다리는 아이템의 stale 상한(초) — 디스패치 뒤 첫 단계를 기다리는 dispatched 와,
# 한 단계를 끝내고 다음 단계 큐를 기다리는 running(meta.stage_running 없음)에 쓴다. 실행 중인
# 단계는 _stage_timeout 으로 따로 잰다. 기본 14400초(4시간)는 broker visibility_timeout
# 7200초(workers/celery_app.py)의 2배다 — 워커가 받은 채 죽어 ack 되지 않은 메시지가 7200초 뒤
# 재전달돼 다시 집힐 때까지 기다린다.
```

(b) `_recover_stale` 를 지우고 그 자리에 아래를 넣는다 — 새 함수 `_parse_iso`·`_stale_window` + 바뀐 `_recover_stale`:
```python
def _parse_iso(value) -> _dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return _dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _stale_window(item) -> tuple[int, _dt.datetime | None, str]:
    """(타임아웃 초, 재기 시작한 시각, 설명) — 실행 중인 단계와 큐 대기를 나눠 잰다."""
    meta = item.meta or {}
    running = meta.get("stage_running") if item.status == "running" else None
    if isinstance(running, str) and running in STAGE_CHECKPOINT:
        started = _parse_iso(meta.get("stage_started_at"))
        return _stage_timeout(running), started or item.updated_at, f"{running} 실행 중"
    what = "디스패치 대기" if item.status == "dispatched" else "다음 단계 대기"
    return DISPATCH_STALE_SECONDS, item.updated_at or item.dispatched_at or item.created_at, what


def _recover_stale(db, job) -> int:
    """워커 사망 등으로 멈춘 아이템 → failed(stale) 전이 (자동 재시도 대상이 됨).

    실행 중인 단계(meta.stage_running)는 그 단계 타임아웃을 단계 시작 시각부터 잰다. 디스패치된
    뒤 아직 안 집혔거나 단계 사이에서 다음 단계 큐를 기다리는 아이템은 DISPATCH_STALE_SECONDS 를
    마지막 갱신 시각부터 잰다 — 큐 대기를 실행 시간으로 세면 바쁜 큐 뒤의 아이템이 stale 로
    오판돼 중복 체인이 열린다(함정 16).
    """
    now = _now()
    recovered = 0
    inflight = (
        db.query(IngestJobItem)
        .filter(
            IngestJobItem.job_id == job.id,
            IngestJobItem.status.in_(("dispatched", "running")),
        )
        .all()
    )
    for item in inflight:
        timeout, ref, what = _stale_window(item)
        if ref is None:
            continue
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=_dt.timezone.utc)
        if (now - ref).total_seconds() > timeout:
            item.status = "failed"
            item.error_group = "stale"
            item.last_error = f"{timeout}s 무응답 — 워커 중단 추정 (stale 복구, {what})"
            item.attempt = (item.attempt or 0) + 1
            item.updated_at = now
            recovered += 1
            log.warning(f"[{item.book_id}] item={item.id} stale 복구 (stage={item.stage}, {what})")
    if recovered:
        db.commit()
    return recovered
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_job_runtime.py tests/test_embed_index_guard.py tests/test_backfill_summary.py -q`
Expected: `45 passed` (job_runtime 36 + embed 가드 6 + backfill 3)

Run: 전체 스위트 — Expected: 2-3 뒤 수 +6, 실패 0 (검증 사본 `928 passed`). 같은 사본에서 `python -m pytest tests -q --continue-on-collection-errors` 는 `928 passed, 3 errors`(로컬 미설치 모듈 3개 — 기존과 같다).

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/workers/job_runtime.py app/tests/test_job_runtime.py
git commit -m "[Fix] round07 — stale 판정을 실행 중(meta.stage_running — 그 단계 타임아웃을 단계 시작 시각부터)과 큐 대기(DISPATCH_STALE_SECONDS 를 updated_at 부터)로 나눠, 다음 단계를 기다리는 아이템을 실행 타임아웃으로 오판해 중복 체인을 여는 경로를 닫는다. DISPATCH_STALE_SECONDS 주석에 실제 값(14400초 = visibility_timeout 7200초의 2배)과 쓰임·까닭을 적는다"
```

---

#### Task 2 가 다른 작업과 맞물리는 곳

- **Task 4(추출 섹션 0):** `StageError("no_text", …)`·`StageError("vlm_error", …)` 를 이 이름 그대로 던져야 2-3 의 규칙이 걸린다. `run_summarize` 의 `"섹션 없음 — extract 단계부터 재실행 필요"` 문구에서 `섹션 없음` 을 바꾸면 옛 실패 545건이 추출부터 다시 하지 않는다. Task 4 가 run_extract 결과에 더하는 meta 키(`forced_ocr`·`ocr_errors`·`vlm_truncated`·`extract_deadline_hit`)는 `_update_item` 이 스칼라만 남기므로 int·bool 로 돌려준다.
- **Task 6(보강을 요약 단계로):** 보강 예외를 단계 밖으로 내보내면, 메시지에 `vlm` 이 든 예외(그림 설명 VLM)는 `classify_error` 가 `vlm_error` 로 분류하고 2-3 규칙이 체크포인트를 `pending` 으로 되돌려 추출부터 다시 한다. 보강 실패는 지금처럼 단계 안에서 삼키거나 다른 그룹으로 던진다. 2-1 의 가드는 `run_embed_index` 의 아티팩트 로드 직후에만 있고 보강 블록은 건드리지 않았다. 보강 아티팩트 유무 판단에 `ctx.item_meta` 를 쓸 수 있다.
- **Task 9(ETA·실패 표시):** `no_text` 아이템은 attempt 가 한도라 "영구 실패"로 세어 남은 수에서 빠진다. 백오프 중인 `failed` 는 아직 남은 수다.
- **Task 12(문서):** 함정 16번의 "근본 원인 … 인덱싱이 끝난 뒤의 과제" 문단과 런북 §8 의 "타임아웃은 `updated_at` 부터 재고" 서술을 이 작업 기준으로 고친다. 카나리 지표에 `실행 안 함 —` 로그 집계를, 배포 직전 확인에 `redis-cli HLEN unacked`·큐 `LLEN` 을, 그리고 "카나리 잡과 본 잡을 동시에 running 으로 두지 않는다"(④)를 넣는다.
- **계획서 머리말:** "전체: `python -m pytest -q`" 는 로컬에서 수집 오류 3개로 0건이 된다 — 위 `--ignore` 명령으로 맞춘다.
- **테스트 더미:** `test_job_runtime.py` 의 celery 더미는 `Celery`·`chain`·`celery.exceptions.Ignore/SoftTimeLimitExceeded` 만 준다. Task 0 이 `celery_app.py` 에 새 celery import(예: `celery.schedules`)를 더하면 이 더미와 `test_backfill_summary.py` 의 더미에도 더한다. `ingest_jobs`·`ingest_job_items` 의 SQLite 엔진(`_make_engine`)은 Task 9 테스트가 같은 것이 필요하면 `history_sqlite.py` 로 옮겨 함께 쓴다.

---

### Task 3: 페이지 판정 순수 모듈과 스캔본 문서 단위 라우팅·`<br>`

#### 조각 D 머리말 (Task 공통 메모·근거)

> **실행 메모(2026-10-02, opendataloader-pdf 버전):** 아래 실제 PDF 관찰과 Task 5 의 ODL 근거는 이 PC 의 opendataloader-pdf 2.5.0 으로 돌린 것이다. 운영이 적재해 온 버전은 2.5.9 라(사용자가 `docker exec nl-lib-celery-cpu pip show opendataloader-pdf` 로 확인) `app/requirements.txt` 를 2.5.9 로 고정했다(fe1be0c). round07 의 ODL 동작(`image_output=off`·json 의 그림 요소로 빈 쪽 남기기·`convert` 호출 방식)은 2.5.9 에서 다시 확인했다(2026-10-02, `research/round07-odl-259-recheck`). 표본 45건(실패 블록·2005년 이전·앞쪽 짧은 쪽·디지털 본문·이름 붙은 사례·`<br>` 격자)을 이 PC 에서 두 버전으로 돌려 쪽 수·표 충전율·OCR 로 보낸 쪽·오류를 비교했다. 1차(1f4954b — 이스케이프 되돌리기 전)는 넷 모두 45건 같고 본문이 같은 문서는 26건이었다 — 본문 차이는 대부분 2.5.1+(#637)의 markdown HTML 이스케이프(`&lt; &gt; &amp;`, 123쪽)였다. 2차(405eaf5 — 되돌리기 399ee25·힙 상한 3g 뒤)는 쪽 수·충전율·OCR 판정 45건 같고 본문이 같은 문서가 35건(남은 차이는 목록 기호·공백 1~2글자), 오류가 다른 1건은 병리 문서가 시간 초과 대신 힙 상한으로 일찍 끝난 것이다(둘 다 fitz 텍스트). 운영 이미지(Linux, OpenJDK 17)로도 45건이 Windows 2.5.9 결과와 같았고 killpg·SIGALRM·tini 가 java 를 거뒀다.

##### 계획 조각 D — Task 3·4·5·11 (추출: 짧은 쪽 라우팅·`<br>`·VLM 잘림·페이지 병렬·추출 데드라인·섹션 0·ODL 타임아웃·이미지 끄기·실제 PDF 회귀)

> 머리말·공통 계약은 `docs/superpowers/plans/2026-10-01-round07-ingest-pipeline-fix.md` 를 따른다. 아래 코드·테스트·기대 출력은 모두 `app/` 사본(`scratchpad/draft_D/app` — Task 0 의 설정 키만 임시로 넣은 상태)에 실제로 적용해 묶음마다 '고치기 전 실패 → 고친 뒤 통과'를 확인한 것이다. 운영 서버에는 아무 요청도 보내지 않았다(실제 PDF 관찰은 이 PC 의 `D:/SKOVIX/KCI/pdf` 와 이 PC 의 자바로 돈 ODL 만 썼다).

##### 머리말·공통 계약에 반영할 것

1. **`short_page_needs_ocr` 시그니처(조정자 결정)** — `def short_page_needs_ocr(*, fitz_len_stripped: int, fitz_len_raw: int, doc_is_scan: bool, force: bool, min_chars: int) -> tuple[bool, str]`. 쪽 면적 이미지 인자(`image_area_ratio`·`image_ratio_threshold`)는 없다.
2. **`SCAN_IMAGE_AREA_RATIO` — 쓰지 않음.** Task 0 의 설정 표·compose 선언에서 뺀다.
3. **extractor 에 새로 생기는 이름**(계약 밖, 이 조각만 쓴다): `PageResult.truncated: bool = False`, `VlmDegenerateOutput`, `_render_png_b64`, `_render_page`, `_ocr_pages`, `_ODL_CHILD`, `_kill_process_group`, `_odl_convert`, `_run_odl`, `_fitz_text_pages`. `_body_len` 은 없어진다(`page_routing.body_len`).
4. **`run_extract` 의 섹션 0개** — 계약대로 강제 OCR 재추출 → `no_text`/`vlm_error` 이되, **첫 추출에서 이미 OCR 오류나 데드라인이 있었으면 강제 재추출 없이 `vlm_error`**(이유는 Task 4 설계 메모). Task 2 는 `no_text` 를 재시도 불가 그룹, `vlm_error` 를 체크포인트 `pending`·백오프 재시도로 다룬다.
5. **전체 테스트 명령** — `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`. 이 PC 기준선은 `890 passed` + 수집 오류 3(`test_book_chat`·`test_build_manifest`·`test_loaders` — PATH 의 python 에 FlagEmbedding·openpyxl 이 없다). 맨 `python -m pytest -q` 는 수집 오류에서 멈춘다. 이 조각의 새 테스트는 64개다(사본: 890 → 929 → 944 → 954).
6. **함정 갱신 후보(Task 12)** — ① `opendataloader_pdf.convert` 는 java 를 timeout 없는 `subprocess.run` 으로 띄워 스레드 `wait_for` 로는 못 끊는다(자식 프로세스 그룹으로 끈다), ② ODL `image_output=off` 면 그림만 있는 쪽이 markdown 에서 통째로 빠진다(json 그림 요소로 빈 쪽을 남긴다), ③ 자식을 끈 뒤 그 stderr 파이프를 손자가 쥐고 있으면 이벤트 루프가 읽기를 기다린다(파일로 받는다), ④ 표 칸 그림을 embedded 로 인코딩하면 `<br>` 격자 수십만 개가 생긴다.

##### 실제 PDF 관찰 (근거)

관찰 방법: 같은 PDF 를 ① 옛 함수(지금 운영 코드 — ODL `embedded`·타임아웃 없음·옛 라우팅), ② 새 함수(`ODL_IMAGE_OUTPUT=off`·타임아웃·새 라우팅), ③ 새 함수 + `embedded` 로 돌리고, VLM 은 쪽 번호만 적는 목으로 바꿔 어느 쪽이 OCR 로 가는지 셌다. ODL 은 이 PC 의 자바(opendataloader-pdf 2.5.0)로 실제로 돌렸다. 표본 186건: 10-01 '섹션 없음' 블록(item id 126,398~ 의 281건) 무작위 40 · 2015년 이후 무작위 40 · 2005~2014 무작위 40 · 2004년 이전 무작위 40 · 2005년 이후 중 첫 두 쪽에 짧은 쪽(표지·간지)이 있는 문서 25 · `<br>` 격자 문서 1(KCI_FI001930485). 스크립트·원자료는 `scratchpad/draft_D/obs/`(route_real.py·full_final.json).

**① 실패 블록의 '남은 글자'는 DBPIA 스탬프다.** KCI_FI002025246(14쪽)은 쪽마다 fitz 텍스트가 `Copyright (C) 2002 Nuri Media Co., Ltd.` 한 줄(body_len 33)이고, ODL json 요소는 쪽마다 그림 2개(쪽 전체를 덮는 스캔 이미지 + 스탬프 이미지)뿐, ODL embedded markdown 은 쪽마다 `[그림]\n\n[그림]` 이다. 옛 규칙은 `0 < 33 < 50` 이라 14쪽 모두 '원래 짧은 쪽'으로 채택해 섹션 0개가 됐다. 새 규칙: 되풀이 줄 키 `Copyright (C) # Nuri Media Co., Ltd.`(36자 ≤ 40)를 빼면 fitz 0자 → 짧은 쪽 14/14 → 스캔본 → 14쪽 모두 OCR. 표본 40건 전부 같은 모양이었고(옛 OCR 0/850쪽 → 새 844/850쪽, 남은 6쪽은 66쪽 문서의 VLM 60쪽 상한), 3쪽 미만 문서는 없었다.

**② 묶음별 결과(실제 ODL)**

| 묶음 | 문서 | 쪽 | 옛 OCR 쪽 | 새 OCR 쪽 | 새로 OCR | OCR 에서 빠짐 | 스캔본 판정 | VLM 타는 문서(옛→새) |
|---|---|---|---|---|---|---|---|---|
| 실패 블록 | 40 | 850 | 0 | 844 | 844 | 0 | 40 | 0 → 40 |
| 2015년 이후 | 40 | 848 | 7 | 32 | 25 | 0 | 1 | 6 → 6 |
| 2005~2014 | 40 | 961 | 82 | 160 | 78 | 0 | 6 | 11 → 11 |
| 2004년 이전 | 40 | 736 | 351 | 438 | 87 | 0 | 21 | 27 → 27 |
| 표지·간지 문서 | 25 | 1,673 | 110 | 109 | 0 | 1 | 0 | 14 → 14 |
| `<br>` 격자(KCI_FI001930485) | 1 | 37 | 0 | 0 | 0 | 0 | 0 | 0 → 0 |

- 새로 OCR 로 간 쪽의 사유: 스캔본 문서 983쪽, 텍스트 층 없음 49쪽, ODL 글자 유실 의심 2쪽. 뒤의 51쪽은 옛 규칙에서 'ODL 본문 50자 이상'으로 채택되던 쪽이다 — 옛 `_body_len` 은 `<br>` 를 4자씩 셌고, 표 칸이 그림 요소로 차 있으면 표 셀 충전율도 1.0 이라 어느 규칙도 못 잡았다(확인한 예: KCI_FI000897237 7·9·10쪽, 쪽마다 `[그림]<br><br>[그림]` 격자 1,000자 안팎·`<br>` 28~136개).
- 2005년 이후 무작위 80건 중 스캔본 판정 7건(KCI_FI002517336·KCI_FI001147574·KCI_FI001667680·KCI_FI001001873·KCI_FI000972623·KCI_FI001172688·KCI_FI001187224)은 모두 텍스트 층이 사실상 없는 문서다(쪽마다 fitz 0~30자 — 예: KCI_FI002517336 은 26쪽 모두 머리말 `한국유아교육연구 제#권 제#호` 15자뿐). 지금은 fitz 0자 쪽만 OCR 하고 나머지는 빈 쪽·`<br>` 쓰레기로 채택하던 '빈·부분 본문 완료' 유형이다.
- **스캔본이 아닌 문서 118건에서 쪽 판정이 바뀐 문서는 2건뿐**이고 표지(0쪽) 판정은 한 건도 바뀌지 않았다: KCI_FI001343547 2·13쪽(`<br>` 를 빼니 ODL 본문이 줄어 CMap 2배 분기 → OCR), KCI_FI001141801 4쪽(fitz 51자 중 쪽 번호 줄을 빼면 48자 → 이제 '원래 짧은 쪽'으로 ODL 채택 — 같은 것끼리 견주기의 경계 사례). 표지·간지 문서 25건은 표지 OCR 1건 → 1건, 첫 두 쪽 OCR 7건 → 7건으로 그대로다. 이미지 표지 디지털 논문(KCI_FI002252358 — 316쪽, 0쪽을 쪽 전체 이미지가 덮고 글자 24자)도 표지는 옛·새 모두 ODL 채택이다.
- 비용: 무작위 묶음에서 'VLM 을 타는 문서' 수는 그대로이고(스캔형 문서는 fitz 0자 쪽 때문에 이미 일부 쪽을 OCR 하고 있었다), OCR 쪽 비율이 오른다 — 2015년 이후 0.8% → 3.8%, 2005~2014 8.5% → 16.6%, 2004년 이전 47.7% → 59.5%. 2005년 이후 무작위 80건 기준 문서당 +1.3쪽이다. Task 11 하네스(ODL 근사, 무작위 200건씩)로는 2005년 이후 문서당 +0.36쪽(OCR 쪽 비율 5.3% → 6.8%), 2004년 이전 +1.63쪽(50.9% → 59.8%)이다 — 근사는 `<br>` 격자 쪽을 못 보므로 실제는 두 값 사이로 본다. **spec 의 '총 처리 시간 +2~4%' 추정보다 클 수 있다** — 카나리와 재개 1~2시간 실측으로 다시 잰다. 늘어나는 쪽은 모두 지금 빈·부분 본문으로 완료되던 스캔형 문서의 쪽이다. 하네스에서 옛 규칙으로는 OCR 0쪽이던 스캔본(실패 블록과 같은 모양)이 2005년 이후 200건 중 3건(KCI_FI001314298·KCI_FI001030932·KCI_FI001107507), 2004년 이전 200건 중 10건 나왔다 — 남은 pending 에도 같은 실패가 흩어져 있다는 spec 의 추정과 맞는다.

**③ ODL 시간과 쪽수 비례 타임아웃(새 함수, off, 자식 프로세스 포함).** 186건에서 '걸린 시간 ÷ 상한' 중앙값 0.119, 90분위 0.264. 0.5 를 넘은 것은 KCI_FI001930485(37쪽 14.4초 / 18.5초 = 0.78)·KCI_FI000858331(6쪽 2.82/5.0)·KCI_FI001410528(13쪽 3.44/6.5)이다. 쪽당 시간 중앙값 0.06초. 같은 문서들의 옛 함수(embedded·같은 프로세스) 중앙값 1.96초 → 새 함수(off·자식 프로세스) 1.46초. **이 PC 기준이라 부하가 걸린 운영 서버에서는 표가 많은 문서(KCI_FI001930485 류)가 상한에 닿을 수 있다** — 닿으면 재저장본 재시도까지 두 배 시간을 쓴 뒤 fitz 텍스트(표 구조 없음)로 떨어진다. 카나리에서 `ODL 실패(원본)` 오류 수를 본다.

**④ 타임아웃이 실제로 막는 문서.** KCI_FI001238691(26쪽, 15.9MB, 2008년 Distiller 산출 — 텍스트 층 0자)은 옛 함수의 ODL 이 877초가 지나도 끝나지 않았다(java 상주 메모리 8.9GB, CPU 928초 — 관찰을 이어 가려고 내가 java 를 껐다). 새 함수는 원본 13초 초과 → 재저장본 13초 초과 → fitz 폴백으로 32.8초에 끝났고, 텍스트 층이 없어 26쪽 모두 OCR 로 갔다(옛 경로가 ODL 실패로 맞는 결과와 같다). 운영 관측 최대 추출 2,785초도 이런 문서일 수 있다. 또 KCI_FI000858284(14쪽)는 embedded 로는 13.4초(상한 7초 초과)인데 off 로는 1.85초다 — 그림 인코딩이 시간을 쓰고 있었다.

**⑤ `<br>` 격자의 출처.** KCI_FI001930485(섹션 196개 중 172개가 `<br>` 반복)는 옛 함수(embedded) markdown 이 2,039,820자·`<br>` 324,402개였는데 off 로는 `<br>` 104개다. 표 칸에 박힌 그림 인코딩이 격자를 만들고 있었다 — 이미지 끄기만으로 이 문서의 쓰레기 섹션 원천이 사라진다(`collapse_br_runs` 는 남는 경우를 막는 두 번째 그물이다).

**⑥ 이미지 끄기 전후 비교(새 함수 off vs 옛 함수 embedded, 같은 문서 186건).** 쪽 목록 같음 185/186(다른 1건은 ④ 의 타임아웃 문서), 표 셀 충전율 같음 186/186, **새 함수의 off·embedded OCR 판정 같음 186/186**. 쪽 텍스트가 다른 58건을 같은 새 함수로 off/embedded 만 바꿔 다시 비교하면 차이 쪽 225개는 모두 그림이 든 표 칸의 빈칸·`<br>` 모양(`||` ↔ `| |`, `<br><br>① …` ↔ `① …`)이고, 실질 본문 길이(body_len)가 다른 쪽 15개는 embedded 쪽이 시간 상한을 넘겨 fitz 로 폴백된 경우였다(KCI_FI000858284 14쪽 — ④, KCI_FI001177531 1쪽 — 다른 작업과 겹쳐 돌린 회차에서만 넘었고 다시 돌리면 두 모드가 같다). 그림만 있는 쪽을 json 그림 요소로 남기지 않으면 off 에서 실패 블록 스캔본은 markdown 에 쪽이 하나도 없다(embedded 14쪽 → off 0쪽) — 5-2 의 보존이 있어 위 판정이 같다.

**⑦ 참고 — CMap 2배 분기와 머리말·꼬리말.** 186건에서 CMap 2배 분기에 걸린 쪽 70개 가운데 되풀이 줄을 빼면 2배 안쪽으로 들어오는 쪽(머리말·꼬리말 때문에 걸린 쪽)은 0개였다. 조건대로 이 분기는 원래 fitz 길이를 쓰고 바꾸지 않는다.

**⑧ VLM 반복 꼬리(`trim_repetition`).** VLM 으로 추출한 문서 392건의 섹션 미리보기 6,124개(`scratchpad/vlmlen/vlm_secs.json`, 미리보기 200자)에서, 앞선 검증의 반복 탐지기로 잡힌 31개 중 30개의 꼬리를 찾았다. 그 탐지기에 안 잡혔는데 꼬리로 잡은 5개는 빈 표 칸 `| | | |` 줄 4개와 목차 점선 1개였다 — 실제 본문을 잘못 자른 사례는 없었다. 8,000자 최악 입력('a'×8000)도 0.07초다.

**⑨ 자식 프로세스 ODL.** 실제 PDF 6건(실패 블록·디지털·`<br>` 격자 포함)을 예전 방식(같은 프로세스 `convert`)과 새 방식(`_odl_convert`)으로 돌려 markdown·json 의 sha256 이 6/6 같았다. 새 방식이 평균 0.057초 더 든다. 리눅스(WSL Ubuntu, 파이썬 3.12)에서 2초 상한 → 2.0초에 `TimeoutError`, 손자 프로세스 사라짐. FastAPI(uvloop) 쪽 호출은 관리자 디버그 API(`api/admin.py`)뿐이고 이 PC 에서는 uvloop 로 돌려 보지 못했다.

**⑩ 운영 고정 버전.** 사본 venv 에 PyMuPDF 1.24.10·httpx 0.27.2·pydantic 2.8.2·pydantic-settings 2.4.0·SQLAlchemy 2.0.36(requirements 고정 버전)을 깔고 이 조각의 새 테스트 64개를 돌려 모두 통과했다. 이 PC 의 PATH python 은 PyMuPDF 1.28.0 이다.

**Files:**
- Create: `app/services/ingestion/page_routing.py`
- Modify: `app/services/ingestion/extractor.py` (import, `_clean_text`, `_STRUCT_CHARS`·`_body_len` 삭제, 모듈 docstring (c), `extract_text`)
- Test: `app/tests/test_page_routing.py`(새), `app/tests/test_extractor_routing.py`(새)

**이 작업이 지키는 것(조정자 조건).** d85df93·0df3001·8b1511a 의 fitz 교차검증 구조를 그대로 둔다 — 표 셀 충전율 < 0.30 → OCR, ODL 50자 이상이면 **원래 fitz 길이**로 CMap 손상 2배 비교, ODL 50자 미만이면 fitz 로 '원래 짧은 쪽'과 'ODL 이 놓친 쪽'을 가르고 fitz 0자는 텍스트 층 없음 → OCR, ODL 누락 쪽 → OCR, VLM 60쪽 상한. 바뀌는 곳은 `:424` 짧은 쪽 분기 하나다.
- 같은 것끼리 견준다: ODL 은 json header/footer 로 머리말·꼬리말을 지운 길이라, 짧은 쪽 분기의 fitz 길이도 문서 전체 쪽의 60% 이상에 되풀이되는 40자 이하 줄(머리말·꼬리말·스탬프·쪽 번호)을 뺀 값으로 잰다. 뺀 뒤 50자 이상이면 'ODL 이 놓친 본문' → OCR.
- 쪽 단위 규칙은 더하지 않는다. 쪽 면적 이미지 규칙도, '되풀이 줄을 빼면 0자인 쪽만 OCR' 도 쓰지 않는다 — 디지털 논문의 이미지 표지(큰 이미지 + 매 쪽 스탬프)가 다시 VLM 을 타기 때문이다(d85df93 이 고친 것).
- 문서 단위로만 스캔본을 본다: 쪽마다 '짧음' = ODL `body_len` < 50 **이고** 되풀이 줄을 뺀 fitz 길이 < 50. 3쪽(`SCAN_MIN_PAGES`) 이상 문서에서 짧은 쪽 비율이 0.5(`SCAN_SHORT_PAGE_RATIO`)를 넘으면 스캔본 → 짧은 쪽을 모두 OCR. 스캔본이 아니면 지금 동작 그대로.
- `body_len` 은 `<br>` 태그를 세지 않는다(지금은 4자로 셈). `_clean_text` 는 3개 이상 이어진 `<br>` 를 줄바꿈 하나로 줄인다.
- `extract_text(..., force_ocr_short_pages=True)` 면 ODL 50자 미만 쪽은 판정 없이 전부 OCR(Task 4-3 이 섹션 0개일 때 쓴다).
- `SCAN_IMAGE_AREA_RATIO` 는 쓰지 않는다.

#### 묶음 3-1: `page_routing.py` 순수 함수

- [ ] **Step 1: 실패하는 테스트 작성** — `app/tests/test_page_routing.py`

```python
"""page_routing 순수 함수 단위 테스트 — 추출 2티어 라우팅의 짧은 쪽 판정·VLM 반복 꼬리."""
from services.ingestion.page_routing import (
    body_len,
    collapse_br_runs,
    is_scan_document,
    repeated_lines,
    short_page_needs_ocr,
    strip_lines,
    trim_repetition,
)

STAMP = "Copyright (C) 2002 Nuri Media Co., Ltd."


class TestBodyLen:
    def test_br_tags_do_not_count(self):
        assert body_len("|<br>|<br/>|<BR >|" * 20) == 0

    def test_figure_markers_and_table_structure_do_not_count(self):
        assert body_len("[그림]\n| --- | :-: |\n|  |  |") == 0

    def test_cell_text_counts(self):
        assert body_len("| 본문 | 12.5 |<br>") == len("본문12.5")

    def test_empty(self):
        assert body_len("") == 0


class TestCollapseBrRuns:
    def test_three_or_more_become_one_newline(self):
        assert collapse_br_runs("가<br><br><br>나") == "가\n나"
        assert collapse_br_runs("가" + "<br> " * 500 + "나") == "가\n나"

    def test_one_or_two_are_kept(self):
        assert collapse_br_runs("셀<br>안<br><br>줄") == "셀<br>안<br><br>줄"


class TestRepeatedLines:
    def test_stamp_and_running_header_with_page_numbers(self):
        pages = [f"한국문학연구 제3집 {227 + i}\n{body}\n{STAMP}" for i, body in enumerate(
            ["고려가요의 계통을 살핀다", "향가와의 관계를 본다", "속요의 형식을 논한다", "결론을 맺는다"])]
        keys = repeated_lines(pages, 0.6)
        assert strip_lines(pages[1], keys) == "향가와의 관계를 본다"

    def test_bare_page_numbers_are_repeated_lines(self):
        pages = [f"{n}\n본문 내용 {chr(0xAC00 + n)}" for n in range(10, 15)]
        assert strip_lines(pages[0], repeated_lines(pages, 0.6)) == "본문 내용 " + chr(0xAC00 + 10)

    def test_below_ratio_is_not_repeated(self):
        pages = [STAMP] * 3 + [f"다른 쪽 {chr(0xAC00 + i)}" for i in range(7)]
        assert repeated_lines(pages, 0.6) == set()

    def test_long_line_is_not_a_candidate(self):
        long_line = "가" * 41
        assert repeated_lines([long_line] * 5, 0.6) == set()

    def test_duplicates_inside_one_page_count_once(self):
        pages = ["\n".join([STAMP] * 3)] + [f"본문 {chr(0xAC00 + i)}" for i in range(4)]
        assert repeated_lines(pages, 0.6) == set()

    def test_single_page_has_no_repeated_lines(self):
        assert repeated_lines([STAMP], 0.6) == set()

    def test_strip_lines_with_empty_set_keeps_text(self):
        assert strip_lines("a\nb", set()) == "a\nb"


class TestIsScanDocument:
    def test_majority_short_with_enough_pages(self):
        assert is_scan_document([True, True, True], min_pages=3, ratio=0.5)
        assert is_scan_document([True, True, True, False], min_pages=3, ratio=0.5)

    def test_too_few_pages(self):
        assert not is_scan_document([True, True], min_pages=3, ratio=0.5)

    def test_half_is_not_more_than_half(self):
        assert not is_scan_document([True, True, False, False], min_pages=3, ratio=0.5)


class TestShortPageNeedsOcr:
    def _call(self, *, stripped, raw, scan=False, force=False):
        return short_page_needs_ocr(
            fitz_len_stripped=stripped, fitz_len_raw=raw, doc_is_scan=scan, force=force, min_chars=50,
        )

    def test_force(self):
        assert self._call(stripped=7, raw=7, force=True)[0]

    def test_no_text_layer(self):
        need, why = self._call(stripped=0, raw=0)
        assert need and "텍스트 층 없음" in why

    def test_odl_missed_body(self):
        need, why = self._call(stripped=120, raw=150)
        assert need and "놓친" in why

    def test_stamp_only_page_in_digital_document_is_kept(self):
        # 이미지 표지에 매 쪽 반복 스탬프만 있는 쪽 — 쪽 단위로는 OCR 하지 않는다
        assert self._call(stripped=0, raw=33) == (False, "원래 짧은 쪽")

    def test_stamp_only_page_in_scan_document_goes_to_ocr(self):
        need, why = self._call(stripped=0, raw=33, scan=True)
        assert need and "스캔본" in why

    def test_genuine_short_page_is_kept(self):
        assert self._call(stripped=7, raw=7) == (False, "원래 짧은 쪽")


class TestTrimRepetition:
    LEAD = "이 논문은 북위 조정의 관직 수여 기록을 분석하고 그 의미를 살핀다. "

    def test_tail_loop_is_cut_to_one_copy(self):
        text = self.LEAD + "고위직을 내려주고, 이후 " * 300 + "고위직을 내"
        trimmed, degenerate = trim_repetition(text)
        assert trimmed.startswith(self.LEAD.strip())
        assert trimmed.count("고위직을 내려주고") == 1
        assert not degenerate

    def test_whole_output_loop_is_degenerate(self):
        trimmed, degenerate = trim_repetition("ti [VP " * 500)
        assert degenerate

    def test_empty_table_rows_are_degenerate(self):
        assert trim_repetition("| | | |\n" * 400)[1]

    def test_normal_text_is_unchanged(self):
        text = "\n".join(f"{chr(0xAC00 + i * 37)}{chr(0xAC00 + i * 53)} 문장 {i}번째 내용입니다." for i in range(60))
        assert trim_repetition(text) == (text, False)

    def test_short_trailing_dots_are_kept(self):
        text = self.LEAD + "그 결과는 다음과 같다..."
        assert trim_repetition(text) == (text, False)

    def test_mostly_duplicate_lines_are_degenerate(self):
        lines = ["첫째 줄에 같은 내용이 반복된다"] * 4 + ["둘째 줄도 다시 나온다"] * 3 + ["마지막 줄은 한 번"]
        order = [lines[0], lines[4], lines[1], lines[5], lines[2], lines[6], lines[3], lines[7]]
        assert trim_repetition("\n".join(order))[1]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_page_routing.py -q`
Expected: 수집 단계에서 `ModuleNotFoundError: No module named 'services.ingestion.page_routing'` (`1 error`)

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/page_routing.py` 새 파일(fitz·httpx import 금지)

`trim_repetition` 은 Task 4-1 이 쓰지만 순수 함수라 여기서 정의한다. 반복 꼬리 판정은 VLM 섹션 미리보기 실측(위 근거 ⑧)으로 정했다.

```python
"""추출 2티어 라우팅의 페이지 판정 — 순수 함수만 둔다.

fitz·httpx 를 import 하지 않는다. extractor.extract_text 가 fitz 로 구한 쪽별 텍스트를
넘기고, 여기서는 ODL 본문이 짧은 쪽을 OCR 로 보낼지만 정한다.
"""
import math
import re
from collections import Counter

_STRUCT_CHARS = str.maketrans("", "", "|-: \t\n\r")
_BR_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BR_RUN = re.compile(r"(?:<br\s*/?>[ \t]*){3,}", re.IGNORECASE)
_WS = re.compile(r"\s+")
_DIGITS = re.compile(r"\d+")


def body_len(text: str) -> int:
    """[그림] 마커·<br> 태그·표 구조 문자·공백을 뺀 실질 본문 글자 수."""
    if not text:
        return 0
    return len(_BR_TAG.sub("", text.replace("[그림]", "")).translate(_STRUCT_CHARS))


def collapse_br_runs(text: str) -> str:
    """3개 이상 이어진 <br> 를 줄바꿈 하나로 줄인다(1~2개는 표 셀 안 줄바꿈이라 둔다)."""
    return _BR_RUN.sub("\n", text)


def _line_key(line: str) -> str:
    # 쪽 번호·연도만 다른 머리말·꼬리말을 같은 줄로 보려고 숫자 묶음을 '#' 하나로 접는다.
    return _DIGITS.sub("#", _WS.sub(" ", line).strip())


def repeated_lines(page_texts: list[str], ratio: float, max_len: int = 40) -> set[str]:
    """문서 쪽의 ratio 이상에 되풀이되는 max_len 자 이하 줄의 키(_line_key) 집합.

    한 쪽 안의 중복은 한 번으로 센다. 쪽이 하나뿐이면 되풀이를 판단할 수 없어 빈 집합이다.
    """
    if len(page_texts) < 2:
        return set()
    counts: Counter[str] = Counter()
    for text in page_texts:
        keys = {_line_key(line) for line in text.split("\n")}
        counts.update(k for k in keys if k and len(k) <= max_len)
    need = max(2, math.ceil(len(page_texts) * ratio))
    return {k for k, c in counts.items() if c >= need}


def strip_lines(text: str, lines: set[str]) -> str:
    """repeated_lines 가 돌려준 키에 해당하는 줄을 뺀다."""
    if not lines:
        return text
    return "\n".join(line for line in text.split("\n") if _line_key(line) not in lines)


def is_scan_document(short_flags: list[bool], *, min_pages: int, ratio: float) -> bool:
    """min_pages 쪽 이상 문서에서 짧은 쪽 비율이 ratio 를 넘으면 문서 단위 스캔본이다."""
    if len(short_flags) < min_pages:
        return False
    return sum(short_flags) / len(short_flags) > ratio


def short_page_needs_ocr(
    *,
    fitz_len_stripped: int,
    fitz_len_raw: int,
    doc_is_scan: bool,
    force: bool,
    min_chars: int,
) -> tuple[bool, str]:
    """ODL 본문이 min_chars 미만인 쪽을 OCR 로 보낼지와 그 사유.

    ODL 은 머리말·꼬리말을 지운 길이라, fitz 도 되풀이 줄을 뺀 길이(fitz_len_stripped)로 견준다.
    fitz_len_raw == 0 은 텍스트 층 자체가 없는 쪽이다. 되풀이 줄만 남은 쪽(이미지 표지의
    스탬프 등)은 문서 전체가 스캔본일 때만 OCR 로 보낸다 — 쪽 단위로 보내면 디지털 논문의
    표지·간지가 다시 VLM 을 탄다.
    """
    if force:
        return True, "강제 OCR(섹션 0개 재추출)"
    if fitz_len_raw == 0:
        return True, "텍스트 층 없음(fitz 0자)"
    if fitz_len_stripped >= min_chars:
        return True, f"ODL 이 놓친 본문(되풀이 줄 뺀 fitz {fitz_len_stripped}자)"
    if doc_is_scan:
        return True, "스캔본 문서(짧은 쪽 과반)"
    return False, "원래 짧은 쪽"


def _tail_period(text: str, *, max_unit: int, min_repeats: int, min_span: int) -> tuple[int, int] | None:
    # 끝에서부터 text[i] == text[i + p] 가 이어지는 가장 앞 자리를 주기 p 마다 찾는다.
    # 마지막 반복이 중간에 잘려 있어도(max_tokens 소진) 주기 비교는 그대로 맞는다.
    n = len(text)
    best: tuple[int, int] | None = None
    for p in range(1, min(max_unit, n // min_repeats) + 1):
        i = n - p - 1
        while i >= 0 and text[i] == text[i + p]:
            i -= 1
        start = i + 1
        if n - start >= max(p * min_repeats, min_span) and text[start:start + p].strip():
            if best is None or start < best[0]:
                best = (start, p)
    return best


def trim_repetition(text: str) -> tuple[str, bool]:
    """VLM 이 max_tokens 까지 같은 줄·구절을 되풀이한 꼬리를 걷어 낸다.

    returns (다듬은 텍스트, 퇴화 출력인가). 되풀이는 한 번만 남긴다. 다듬은 뒤 실질 본문이
    20자 미만이거나, 남은 줄(5줄 이상)의 절반 이상이 앞 줄의 되풀이면 퇴화 출력이다.
    """
    found = _tail_period(text, max_unit=200, min_repeats=3, min_span=60)
    trimmed = text[: found[0] + found[1]].rstrip() if found else text.rstrip()
    if body_len(trimmed) < 20:
        return trimmed, True
    lines = [line.strip() for line in trimmed.split("\n") if line.strip()]
    if len(lines) >= 5 and (len(lines) - len(set(lines))) / len(lines) >= 0.5:
        return trimmed, True
    return trimmed, False
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_page_routing.py -q`
Expected: `28 passed`

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/page_routing.py app/tests/test_page_routing.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Feat] round07 — 추출 라우팅 판정 순수 모듈(page_routing): <br>·[그림]·표 구조 문자를 뺀 본문 길이, <br> 3개 이상 연속을 줄바꿈 하나로, 문서 쪽 60% 이상에 되풀이되는 40자 이하 줄(숫자는 접어 쪽 번호·연도 차이를 무시)과 그 줄 빼기, 3쪽 이상·짧은 쪽 과반이면 문서 단위 스캔본, ODL 이 짧은 쪽의 OCR 여부(강제·텍스트 층 없음·ODL 이 놓친 본문·스캔본 문서), VLM 반복 꼬리 걷어 내기와 퇴화 판정"
```

#### 묶음 3-2: `extract_text` 짧은 쪽 분기·`<br>`

- [ ] **Step 1: 실패하는 테스트 작성** — `app/tests/test_extractor_routing.py`

PDF 는 fitz 로 메모리에서 만든다(텍스트 쪽·스탬프만 있는 쪽·큰 이미지 쪽). ODL(`extract_text_opendataloader`)과 `_extract_with_vlm` 은 목이다. 목 VLM 은 `**_kw` 를 받아 Task 4-2 가 더하는 `render_lock` 인자에도 그대로 맞는다. 회귀 테스트 다섯(CMap 손상 의심 → VLM, 진짜 짧은 간지 → ODL, fitz 0자 → VLM, 이미지 표지 → ODL, ODL 누락 → OCR)은 고치기 전에도 통과한다.

```python
"""extract_text 2티어 라우팅 — 어느 쪽이 OCR 로 가는지 (ODL·VLM 은 목, PDF 는 fitz 로 메모리에서 만든다).

ODL 은 json header/footer 로 머리말·꼬리말을 지운 본문을 돌려주므로, 목 ODL 텍스트에는 스탬프를 넣지 않는다.
"""
import asyncio

import fitz

from services.ingestion import extractor
from services.ingestion.extractor import ExtractionResult, PageResult

STAMP = "Copyright (C) 2002 Nuri Media Co., Ltd."
BODIES = [
    ["Alpha chapter reviews the archival record of royal court", "appointments and the ranks given to envoys from abroad."],
    ["Bravo chapter compares the ritual songs with older folk", "ballads and traces how their refrains were borrowed."],
    ["Charlie chapter reads the land registers kept by county", "offices and estimates how much farmland was taxed."],
    ["Delta chapter sums up the findings and lists the open", "questions that later studies should take up again."],
    ["Echo chapter maps the trade routes that carried paper", "and ink between the capital and the southern ports."],
]


def _pdf(pages: list[list[str]], *, stamp: bool = True, image_pages: tuple[int, ...] = ()) -> bytes:
    doc = fitz.open()
    for n, lines in enumerate(pages):
        page = doc.new_page(width=420, height=595)
        if n in image_pages:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), False)
            pix.clear_with(180)
            page.insert_image(page.rect, pixmap=pix)
        for i, line in enumerate(lines):
            page.insert_text((36, 60 + 14 * i), line, fontsize=9)
        if stamp:
            page.insert_text((36, 580), STAMP, fontsize=6)
    data = doc.tobytes()
    doc.close()
    return data


def _run(monkeypatch, pdf: bytes, odl_texts: dict[int, str], **kwargs) -> tuple[list[int], ExtractionResult]:
    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None):
        res = ExtractionResult(book_id=book_id, total_pages=len(odl_texts))
        res.pages = [PageResult(n, t, "opendataloader", 0.95) for n, t in sorted(odl_texts.items())]
        return res

    ocr_calls: list[int] = []

    async def fake_vlm(page, client, *, prompt_type="ocr", **_kw):
        ocr_calls.append(page.number)
        return PageResult(page.number, f"VLM 본문 {page.number}", "vlm", 0.9)

    monkeypatch.setattr(extractor, "extract_text_opendataloader", fake_odl)
    monkeypatch.setattr(extractor, "_extract_with_vlm", fake_vlm)
    monkeypatch.setattr(extractor.cfg, "OCR_ENGINE", "vlm")
    result = asyncio.run(extractor.extract_text(None, "T_ROUTE", file_bytes=pdf, **kwargs))
    return sorted(ocr_calls), result


def _body_text(n: int) -> str:
    return " ".join(BODIES[n])


def test_digital_paper_with_image_cover_keeps_cover_from_odl(monkeypatch):
    """표지 쪽 텍스트가 매 쪽 반복 스탬프뿐인 이미지 표지 → 쪽 단위로 OCR 하지 않는다."""
    pdf = _pdf([[]] + BODIES[:4], image_pages=(0,))
    odl = {0: "[그림]", **{n + 1: _body_text(n) for n in range(4)}}
    ocr, result = _run(monkeypatch, pdf, odl)
    assert ocr == []
    assert [p.page_num for p in result.pages] == [0, 1, 2, 3, 4]
    assert result.pages[0].text == ""


def test_scan_document_with_stamp_only_pages_goes_to_ocr(monkeypatch):
    """모든 쪽이 이미지 + 스탬프뿐인 스캔본(「한국문학연구」 실패 블록) → 짧은 쪽 전부 OCR."""
    pdf = _pdf([[]] * 4, image_pages=(0, 1, 2, 3))
    ocr, result = _run(monkeypatch, pdf, {n: "[그림]\n\n[그림]" for n in range(4)})
    assert ocr == [0, 1, 2, 3]
    assert [p.method for p in result.pages] == ["vlm"] * 4


def test_two_page_scan_is_below_document_rule(monkeypatch):
    """3쪽 미만은 문서 단위 판정을 하지 않는다 — 섹션 0개 강제 재추출(run_extract)이 맡는다."""
    pdf = _pdf([[]] * 2, image_pages=(0, 1))
    ocr, _ = _run(monkeypatch, pdf, {0: "[그림]", 1: "[그림]"})
    assert ocr == []


def test_genuine_short_divider_page_keeps_odl(monkeypatch):
    """디지털 문서의 진짜 짧은 간지(실제 글자 몇 개) → ODL 채택."""
    pdf = _pdf(BODIES[:4] + [["Part Two"]])
    odl = {**{n: _body_text(n) for n in range(4)}, 4: "Part Two"}
    ocr, result = _run(monkeypatch, pdf, odl)
    assert ocr == []
    assert result.pages[4].text == "Part Two"


def test_cmap_loss_suspect_page_goes_to_vlm(monkeypatch):
    """회귀: ODL 50자 이상인데 fitz(원래 길이)가 2배 넘게 길면 CMap 손상 의심 → VLM."""
    long_page = BODIES[0] + BODIES[1] + BODIES[2]
    pdf = _pdf([long_page, BODIES[3], BODIES[4]])
    odl = {0: BODIES[0][0], 1: _body_text(3), 2: _body_text(4)}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [0]


def test_page_without_text_layer_goes_to_vlm(monkeypatch):
    """회귀: fitz 0자(텍스트 층 없음) → VLM. 스탬프도 없는 이미지 쪽."""
    pdf = _pdf(BODIES[:3] + [[]], stamp=False, image_pages=(3,))
    odl = {**{n: _body_text(n) for n in range(3)}, 3: "[그림]"}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [3]


def test_empty_br_grid_is_not_counted_as_body(monkeypatch):
    """ODL 이 빈 표 격자를 <br> 로 채운 쪽 — <br> 를 본문으로 세지 않아 fitz 0자 → VLM."""
    pdf = _pdf(BODIES[:3] + [[]], stamp=False)
    odl = {**{n: _body_text(n) for n in range(3)}, 3: "|<br>|<br>|" * 30}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [3]


def test_header_footer_only_page_is_compared_without_repeated_lines(monkeypatch):
    """fitz 원래 길이는 머리말+꼬리말로 50자를 넘지만 되풀이 줄을 빼면 0 — 디지털 문서에선 ODL 채택."""
    header = "Journal of Archival Studies 3"
    pages = [[header] + BODIES[n] for n in range(4)] + [[header]]
    pdf = _pdf(pages)
    odl = {**{n: _body_text(n) for n in range(4)}, 4: ""}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == []


def test_figure_heavy_document_counts_as_scan(monkeypatch):
    """3쪽 이상에서 짧은 쪽이 절반을 넘으면 문서 단위 스캔본 → 짧은 쪽만 OCR, 본문 쪽은 ODL."""
    pdf = _pdf([["Plate one"], ["Plate two"], ["Plate three"], BODIES[0]])
    odl = {0: "Plate one", 1: "Plate two", 2: "Plate three", 3: _body_text(0)}
    ocr, result = _run(monkeypatch, pdf, odl)
    assert ocr == [0, 1, 2]
    assert result.pages[3].method == "opendataloader"


def test_force_sends_every_short_page_to_ocr(monkeypatch):
    pdf = _pdf(BODIES[:4] + [["Part Two"]])
    odl = {**{n: _body_text(n) for n in range(4)}, 4: "Part Two"}
    ocr, _ = _run(monkeypatch, pdf, odl, force_ocr_short_pages=True)
    assert ocr == [4]


def test_page_missing_from_odl_still_goes_to_ocr(monkeypatch):
    """회귀: ODL 결과에 없는 쪽은 예전처럼 판정 없이 OCR."""
    pdf = _pdf(BODIES[:3] + [["Part Two"]])
    odl = {n: _body_text(n) for n in range(3)}
    ocr, _ = _run(monkeypatch, pdf, odl)
    assert ocr == [3]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_routing.py -q`
Expected: `5 failed, 6 passed` — 실패는 `test_scan_document_with_stamp_only_pages_goes_to_ocr`(OCR `[]`), `test_empty_br_grid_is_not_counted_as_body`, `test_header_footer_only_page_is_compared_without_repeated_lines`(지금은 머리말+꼬리말 58자로 OCR), `test_figure_heavy_document_counts_as_scan`, `test_force_sends_every_short_page_to_ocr`(`TypeError: ... unexpected keyword argument 'force_ocr_short_pages'`)

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/extractor.py`

(1) import 에 한 줄 더한다.

```python
# old
from core.config import get_settings

log = logging.getLogger(__name__)
# new
from core.config import get_settings
from services.ingestion import page_routing

log = logging.getLogger(__name__)
```

(2) `_clean_text` 첫머리(`import re` 바로 다음)에 두 줄을 더한다.

```python
# old
    import re
    if strip_lines:
# new
    import re
    # 빈 표 격자의 <br> 수천 개가 섹션 본문을 채우지 않게 줄바꿈 하나로 줄인다.
    text = page_routing.collapse_br_runs(text)
    if strip_lines:
```

(3) `# 마크다운 표 구조 문자 + 공백 — 실질 본문 길이 계산에서 제외` 주석부터 `_body_len` 함수 끝까지(지금 `extractor.py:70-82`)를 지운다 — `page_routing.body_len` 이 대신한다.

(4) 모듈 docstring 의 (c) 항목 끝에 세 줄을 더한다.

```python
# old
                                페이지이므로 VLM 없이 ODL 결과를 그대로 채택한다
# new
                                페이지이므로 VLM 없이 ODL 결과를 그대로 채택한다.
                                fitz 는 문서 전체에 되풀이되는 줄(머리말·꼬리말·스탬프)을
                                뺀 길이로 견주고, 3쪽 이상 문서에서 이런 짧은 쪽이 절반을
                                넘으면 스캔본으로 보고 짧은 쪽을 모두 OCR 한다(page_routing.py)
```

(5) `extract_text` 를 아래 전체로 바꾼다(바뀐 곳: 시그니처의 `force_ocr_short_pages`, 라우팅 전 문서 단위 계산 블록, `page_routing.body_len`, `fitz_check_len = fitz_raw_lens[page_num]`, 짧은 쪽 분기의 `short_page_needs_ocr`. 나머지 줄은 그대로다).

```python
async def extract_text(
    file_path: str | Path,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    force_ocr_short_pages: bool = False,
) -> ExtractionResult:
    """2티어 라우팅 파이프라인.

    force_ocr_short_pages: ODL 본문이 짧은 쪽을 판정 없이 모두 OCR 한다(섹션 0개 재추출용).

    1티어: OpenDataLoader로 전체 PDF 마크다운+json 추출
    2티어: 본문 부족 / CMap 손상 의심 / 표 셀 충전율 낮음 중 하나라도 해당하는
           페이지만 VLM 보완 (판단 기준은 파일 상단 docstring 참고)
    """
    result = ExtractionResult(book_id=book_id, total_pages=0)

    # ── 1티어: OpenDataLoader 전체 추출 ──────────────────
    odl_result = await extract_text_opendataloader(
        file_path, book_id, file_bytes=file_bytes
    )
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

    result.total_pages = len(doc)
    log.info(
        f"[{book_id}] {result.total_pages}p — 1티어 ODL 완료 "
        f"({len(odl_result.pages)}p 추출), 2티어 라우팅 시작"
    )

    # 짧은 쪽은 같은 것끼리 견준다 — ODL 은 머리말·꼬리말을 지운 길이라 fitz 도 문서 전체에
    # 되풀이되는 줄을 뺀 길이로 잰다. CMap 손상 2배 비교는 예전처럼 원래 fitz 길이를 쓴다.
    fitz_texts = [_clean_text(p.get_text()) for p in doc]
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

    vlm_pages_used = 0
    vlm_cap = cfg.VLM_MAX_PAGES_PER_DOC
    vlm_cap_hit = False

    async with httpx.AsyncClient() as client:
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
                            odl_page.text = _strip_figure_markers(odl_page.text)
                            result.pages.append(odl_page)
                            continue
                        trigger = f"ODL 글자 유실 의심(ODL {body_len}자 vs 원본 추정 {fitz_check_len}자)"
                    else:
                        need_ocr, why = page_routing.short_page_needs_ocr(
                            fitz_len_stripped=fitz_stripped_lens[page_num],
                            fitz_len_raw=fitz_check_len,
                            doc_is_scan=doc_is_scan,
                            force=force_ocr_short_pages,
                            min_chars=MIN_CHARS_PER_PAGE,
                        )
                        if not need_ocr:
                            # 원래 짧은 쪽(표지·간지 등) — ODL 결과 그대로 채택.
                            odl_page.text = _strip_figure_markers(odl_page.text)
                            result.pages.append(odl_page)
                            continue
                        trigger = f"{why}(ODL {body_len}자 vs 원본 추정 {fitz_check_len}자)"

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

            # 2티어: 1티어 결과를 못 믿는 페이지 OCR 보완 (엔진은 OCR_ENGINE 플래그로 선택).
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_routing.py tests/test_page_routing.py -q`
Expected: `39 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: 이 작업 직전 수 + 39 passed, 수집 오류 3(사본 측정: 890 → 929)

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/extractor.py app/tests/test_extractor_routing.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Fix] round07 — 텍스트 층에 스탬프만 남은 스캔본이 VLM 을 건너뛰던 :424 분기를 표적 수정: 짧은 쪽은 fitz 도 문서 전체에 되풀이되는 줄(머리말·꼬리말·스탬프)을 뺀 길이로 견주고, 3쪽 이상 문서에서 짧은 쪽이 과반이면 스캔본으로 보고 짧은 쪽을 OCR 한다(쪽 단위 규칙은 더하지 않아 디지털 논문의 이미지 표지·간지는 그대로 ODL 채택). CMap 2배·표 셀 충전율·fitz 0자·ODL 누락 판정은 그대로. 본문 길이에서 <br> 를 빼고 _clean_text 가 <br> 3개 이상 연속을 줄바꿈 하나로 줄인다. extract_text 에 force_ocr_short_pages"
```

---

### Task 4: VLM 잘림·페이지 병렬·추출 데드라인·섹션 0 처리

> **실행 메모(2026-10-02, Task 3 리뷰 반영 뒤):** 아래 4-2 의 `extract_text` "전체로 바꾼다" 블록은 Task 3 첫 구현(0487057) 기준이다. 그 뒤 Task 3 리뷰 수정 5b3be2e·18e72e0 이 `extract_text` 를 바꿨다 — 짧은 쪽 판정 순서(force → fitz 원래 길이 0 → 스캔본 → 원래 길이 ≥ 50 → 채택, 되풀이 줄 뺀 길이는 스캔 판정에만), 쪽별 `get_text` try/except(실패 쪽 "" + errors), `_strip_figure_markers` 뒤 `<br>` 재축약. 그래서 이 블록을 통째로 붙이지 말고 현재 코드에 병합한다(위 세 가지를 보존). 추가로: OCR 폴백·VLM 상한 경로의 채택 텍스트도 `_strip_figure_markers`(재축약 포함)를 거친다. 렌더링 실패(fitz `get_pixmap` 예외 — 예: FzErrorLimit)는 다시 해도 같은 결정적 실패라 `ocr_errors` 로 세지 않고 `render_errors` 로 따로 센다 — `ocr_errors` 는 다시 하면 결과가 달라질 수 있는 VLM 요청 실패(연결·타임아웃·HTTP 오류)만 센다 — 퇴화 출력은 아래 설계 메모대로 `vlm_truncated` 로만 세고 ODL 로 폴백한다(다시 해도 대개 같다). 그래야 섹션 0개 문서가 렌더링 실패 때문에 `vlm_error`(자동 재시도)로 헛돌지 않고 `no_text` 로 간다.

**Files:**
- Modify: `app/services/ingestion/extractor.py` (`PageResult`·`ExtractionResult` 필드, `VlmDegenerateOutput`, `_render_png_b64`·`_render_page`, `_extract_with_vlm`, `_extract_with_surya`, `_ocr_pages`(새), `extract_text`)
- Modify: `app/services/ingestion/stages.py` (`run_extract`)
- Test: `app/tests/test_extractor_ocr.py`(새), `app/tests/test_run_extract_sections.py`(새)

**설계 메모.**
- 렌더링(`page.get_pixmap`)은 이벤트 루프 스레드에서 동기로 한다. PyMuPDF 는 다중 스레드를 지원하지 않으므로 `to_thread` 로 빼지 않는다. `asyncio.Lock` 은 동시에 도는 OCR 코루틴이 한 번에 한 쪽만 렌더하도록 지키는 자리이고, 요청(`client.post`)만 `asyncio.Semaphore(VLM_PAGE_CONCURRENCY)` 안에서 동시에 나간다. 결과는 `{쪽 번호: PageResult}` 로 모아 쪽 순서로 조립한다.
- 판정(fitz 교차검증)은 지금처럼 쪽 순서대로 하고, OCR 이 필요한 쪽만 모은다. VLM 60쪽 상한은 모으는 단계에서 센다(넘는 쪽은 ODL 채택 — 예전과 같다).
- 데드라인: `extract_text` 시작 시각부터 `INGEST_EXTRACT_DEADLINE` 초. OCR 묶음 전체를 `asyncio.timeout(남은 시간)` 으로 감싸고, 넘으면 끝나지 않은 쪽은 ODL 결과로 채택하고 `deadline_hit=True`. `asyncio.timeout` 은 await 지점에서 취소하므로 코루틴 안에서 확실히 잡힌다(함정 19 — Celery 소프트 리밋에 맡기지 않는다).
- VLM 잘림: 비추론 모드에서도 `finish_reason == "length"` 면 `trim_repetition` 으로 되풀이 꼬리를 걷어 내고 `PageResult.truncated=True`. 걷어 내도 퇴화면 `VlmDegenerateOutput` 을 던져 호출부가 ODL 결과로 채택한다. 둘 다 `vlm_truncated` 로 센다. 퇴화는 `ocr_errors` 에 넣지 않는다(같은 페이지는 다시 해도 대개 같아서, 섹션 0개일 때 `vlm_error` 로 재시도할 거리가 아니다).
- 섹션 0개(4-3): 강제 OCR(`force_ocr_short_pages=True`)로 한 번 더 추출 → 그래도 0개면 OCR 오류·데드라인이 있었으면 `StageError("vlm_error")`, 없었으면 `StageError("no_text")`. **첫 추출에서 이미 OCR 오류나 데드라인이 있었으면 강제 재추출 없이 바로 `vlm_error`** 다(계약보다 한 걸음 더 — 이유: 첫 추출이 데드라인 2,700초를 다 쓴 뒤 두 번째 추출이 또 2,700초를 쓰면 단계가 stale 판정 3,600초를 넘어 중복 체인이 열린다. VLM 장애 중의 강제 OCR 은 같은 실패를 되풀이할 뿐이고, `vlm_error` 는 Task 2 의 백오프 재시도가 추출부터 다시 한다).
- 반환 meta 키: `forced_ocr`·`vlm_truncated`·`extract_deadline_hit`·`ocr_errors`(공통 계약).

#### 묶음 4-1: VLM `finish_reason == "length"` 다듬기

- [ ] **Step 1: 실패하는 테스트 작성** — `app/tests/test_extractor_ocr.py`

```python
"""extract_text OCR — VLM 잘림 다듬기(4-1), 문서 안 동시 요청·렌더 잠금·데드라인·OCR 실패 폴백(4-2)."""
import asyncio

import httpx
import pytest

from services.ingestion import extractor
from services.ingestion.extractor import PageResult, VlmDegenerateOutput

LEAD = "이 논문은 북위 조정의 관직 수여 기록을 분석하고 그 의미를 살핀다. "


class _Page:
    number = 4


def _vlm(monkeypatch, content: str, finish: str) -> PageResult:
    """실제 _extract_with_vlm 을 목 HTTP 응답으로 부른다(렌더링은 목)."""
    monkeypatch.setattr(extractor, "_render_png_b64", lambda page: "QUJD")

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})

    async def go() -> PageResult:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await extractor._extract_with_vlm(_Page(), client)

    return asyncio.run(go())


def test_length_finish_trims_repeated_tail(monkeypatch):
    page = _vlm(monkeypatch, LEAD + "고위직을 내려주고, 이후 " * 300, "length")
    assert page.truncated
    assert page.text.startswith(LEAD.strip())
    assert page.text.count("고위직을 내려주고") == 1


def test_degenerate_length_output_raises(monkeypatch):
    with pytest.raises(VlmDegenerateOutput):
        _vlm(monkeypatch, "| | | |\n" * 400, "length")


def test_stop_finish_is_not_trimmed(monkeypatch):
    content = LEAD + "같은 문장이 반복된다. " * 10
    page = _vlm(monkeypatch, content, "stop")
    assert page.text == content.strip()
    assert not page.truncated
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_ocr.py -q`
Expected: 수집 단계에서 `ImportError: cannot import name 'VlmDegenerateOutput' from 'services.ingestion.extractor'` (`1 error`)

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/extractor.py`

(1) `PageResult` 에 필드 하나를 더한다.

```python
@dataclass
class PageResult:
    page_num: int
    text: str
    method: str          # "fitz" | "vlm"
    confidence: float
    truncated: bool = False  # VLM 응답이 max_tokens 로 끝나 되풀이 꼬리를 걷어 냈다
```

(2) `_extract_with_vlm` 바로 위에 예외와 렌더 함수를 두고, `_extract_with_vlm` 을 아래 전체로 바꾼다(렌더를 `_render_png_b64` 로 빼고, 마지막 `_ask` 뒤에 length 다듬기).

```python
class VlmDegenerateOutput(Exception):
    """VLM 이 같은 구절을 되풀이하다 max_tokens 로 끝나, 꼬리를 걷어 내도 쓸 본문이 없다."""


def _render_png_b64(page: fitz.Page) -> str:
    import base64

    return base64.b64encode(page.get_pixmap(dpi=cfg.FITZ_DPI).tobytes("png")).decode()


async def _extract_with_vlm(
    page: fitz.Page,
    client: httpx.AsyncClient,
    *,
    prompt_type: str = "ocr",  # "ocr" | "diagram"
) -> PageResult:
    img_b64 = _render_png_b64(page)

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
```

(3) `_extract_with_surya` 의 렌더 세 줄(`import base64` · `pix = page.get_pixmap(...)` · `img_b64 = base64.b64encode(...)`)을 `img_b64 = _render_png_b64(page)` 한 줄로 바꾼다.

이 상태에서 퇴화 출력은 기존 순차 루프의 `except Exception` 이 받아 ODL 결과로 채택한다(세는 것은 4-2).

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_ocr.py tests/test_extractor_routing.py tests/test_page_routing.py -q`
Expected: `42 passed`

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/extractor.py app/tests/test_extractor_ocr.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Fix] round07 — VLM 이 max_tokens 로 끝난 쪽(finish_reason=length)을 비추론 모드에서도 본다: 같은 구절을 되풀이한 꼬리를 한 번만 남기고 걷어 내 truncated 로 표시하고, 걷어 내도 본문이 없거나 줄 절반 이상이 되풀이면 VlmDegenerateOutput 으로 ODL 결과를 쓰게 한다. 렌더링은 _render_png_b64 로 뺀다"
```

#### 묶음 4-2: 문서 안 OCR 병렬·렌더 잠금·추출 데드라인

- [ ] **Step 1: 실패하는 테스트 작성** — `app/tests/test_extractor_ocr.py` 를 아래 전체로 바꾼다(4-1 의 세 테스트를 그대로 담는다)

```python
"""extract_text OCR — VLM 잘림 다듬기(4-1), 문서 안 동시 요청·렌더 잠금·데드라인·OCR 실패 폴백(4-2)."""
import asyncio
import time

import fitz
import httpx
import pytest

from services.ingestion import extractor
from services.ingestion.extractor import ExtractionResult, PageResult, VlmDegenerateOutput

LEAD = "이 논문은 북위 조정의 관직 수여 기록을 분석하고 그 의미를 살핀다. "


class _Page:
    number = 4


def _vlm(monkeypatch, content: str, finish: str) -> PageResult:
    """실제 _extract_with_vlm 을 목 HTTP 응답으로 부른다(렌더링은 목)."""
    monkeypatch.setattr(extractor, "_render_png_b64", lambda page: "QUJD")

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})

    async def go() -> PageResult:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await extractor._extract_with_vlm(_Page(), client)

    return asyncio.run(go())


def test_length_finish_trims_repeated_tail(monkeypatch):
    page = _vlm(monkeypatch, LEAD + "고위직을 내려주고, 이후 " * 300, "length")
    assert page.truncated
    assert page.text.startswith(LEAD.strip())
    assert page.text.count("고위직을 내려주고") == 1


def test_degenerate_length_output_raises(monkeypatch):
    with pytest.raises(VlmDegenerateOutput):
        _vlm(monkeypatch, "| | | |\n" * 400, "length")


def test_stop_finish_is_not_trimmed(monkeypatch):
    content = LEAD + "같은 문장이 반복된다. " * 10
    page = _vlm(monkeypatch, content, "stop")
    assert page.text == content.strip()
    assert not page.truncated


# ── 4-2 ──────────────────────────────────────────────────────


def _blank_pdf(n_pages: int) -> bytes:
    """텍스트 층이 없는 쪽만 — fitz 0자라 전부 OCR 로 간다."""
    doc = fitz.open()
    for _ in range(n_pages):
        doc.new_page(width=200, height=300)
    data = doc.tobytes()
    doc.close()
    return data


def _patch(monkeypatch, n_pages: int, fake_vlm, *, concurrency: int = 2) -> None:
    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None):
        res = ExtractionResult(book_id=book_id, total_pages=n_pages)
        res.pages = [PageResult(n, f"ODL 대체 {n}", "opendataloader", 0.95) for n in range(n_pages)]
        return res

    monkeypatch.setattr(extractor, "extract_text_opendataloader", fake_odl)
    monkeypatch.setattr(extractor, "_extract_with_vlm", fake_vlm)
    monkeypatch.setattr(extractor.cfg, "OCR_ENGINE", "vlm")
    monkeypatch.setattr(extractor.cfg, "VLM_PAGE_CONCURRENCY", concurrency)


def _extract(n_pages: int, **kwargs) -> ExtractionResult:
    return asyncio.run(extractor.extract_text(None, "T_OCR", file_bytes=_blank_pdf(n_pages), **kwargs))


def test_render_happens_inside_render_lock(monkeypatch):
    seen: list[bool] = []

    async def go() -> PageResult:
        lock = asyncio.Lock()

        def fake_render(page):
            seen.append(lock.locked())
            return "QUJD"

        monkeypatch.setattr(extractor, "_render_png_b64", fake_render)

        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": "본문"}, "finish_reason": "stop"}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await extractor._extract_with_vlm(_Page(), client, render_lock=lock)

    assert asyncio.run(go()).text == "본문"
    assert seen == [True]


def test_ocr_runs_concurrently_up_to_limit_and_keeps_page_order(monkeypatch):
    state = {"now": 0, "max": 0}

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        state["now"] += 1
        state["max"] = max(state["max"], state["now"])
        await asyncio.sleep(0.01 * (6 - page.number))  # 앞쪽이 더 늦게 끝난다
        state["now"] -= 1
        return PageResult(page.number, f"VLM {page.number}", "vlm", 0.9)

    _patch(monkeypatch, 6, fake_vlm, concurrency=2)
    result = _extract(6)
    assert state["max"] == 2
    assert [p.text for p in result.pages] == [f"VLM {n}" for n in range(6)]


def test_all_pages_share_one_render_lock(monkeypatch):
    locks = []

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        locks.append(render_lock)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 3, fake_vlm)
    _extract(3)
    assert len(locks) == 3
    assert isinstance(locks[0], asyncio.Lock)
    assert all(lock is locks[0] for lock in locks)


def test_degenerate_and_failed_pages_fall_back_to_odl(monkeypatch):
    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        if page.number == 0:
            raise VlmDegenerateOutput("p.0 VLM 퇴화 출력(finish=length)")
        if page.number == 1:
            raise httpx.ConnectError("VLM 연결 실패")
        return PageResult(page.number, "VLM 본문", "vlm", 0.9, truncated=True)

    _patch(monkeypatch, 3, fake_vlm)
    result = _extract(3)
    assert [p.text for p in result.pages] == ["ODL 대체 0", "ODL 대체 1", "VLM 본문"]
    assert result.vlm_truncated == 2  # 퇴화로 버린 쪽 1 + 꼬리를 걷어 내고 채택한 쪽 1
    assert result.ocr_errors == 1     # 퇴화 출력은 OCR 오류로 세지 않는다


def test_deadline_adopts_odl_for_pages_not_done(monkeypatch):
    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        if page.number > 0:
            await asyncio.sleep(5)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 4, fake_vlm, concurrency=4)
    monkeypatch.setattr(extractor.cfg, "INGEST_EXTRACT_DEADLINE", 0.5)
    t0 = time.monotonic()
    result = _extract(4)
    assert time.monotonic() - t0 < 3
    assert result.deadline_hit
    assert [p.text for p in result.pages] == ["VLM 본문", "ODL 대체 1", "ODL 대체 2", "ODL 대체 3"]
    assert result.ocr_errors == 0


def test_vlm_page_cap_still_applies(monkeypatch):
    calls = []

    async def fake_vlm(page, client, *, prompt_type="ocr", render_lock=None):
        calls.append(page.number)
        return PageResult(page.number, "VLM 본문", "vlm", 0.9)

    _patch(monkeypatch, 4, fake_vlm)
    monkeypatch.setattr(extractor.cfg, "VLM_MAX_PAGES_PER_DOC", 2)
    result = _extract(4)
    assert sorted(calls) == [0, 1]
    assert result.vlm_capped
    assert [p.method for p in result.pages] == ["vlm", "vlm", "opendataloader", "opendataloader"]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_ocr.py -q`
Expected: `5 failed, 4 passed` — 실패: `test_render_happens_inside_render_lock`(`TypeError: _extract_with_vlm() got an unexpected keyword argument 'render_lock'`), `test_ocr_runs_concurrently_up_to_limit_and_keeps_page_order`(`assert 1 == 2` — 순차), `test_all_pages_share_one_render_lock`(`isinstance(None, asyncio.Lock)`), `test_degenerate_and_failed_pages_fall_back_to_odl`(`AttributeError: ... 'vlm_truncated'`), `test_deadline_adopts_odl_for_pages_not_done`(순차라 약 15초 뒤 실패). 4-1 의 세 테스트와 `test_vlm_page_cap_still_applies`(회귀)는 통과한다.

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/extractor.py`

(1) import 에 `asyncio`·`time` 을 더한다.

```python
# old
import io
import logging
from pathlib import Path
# new
import asyncio
import io
import logging
import time
from pathlib import Path
```

(2) `ExtractionResult` 에 공통 계약의 세 필드를 더한다(`table_fill_ratios` 다음).

```python
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
    deadline_hit: bool = False  # INGEST_EXTRACT_DEADLINE 에 걸려 남은 쪽을 ODL 결과로 채택했다
    ocr_errors: int = 0         # OCR 호출 예외 수(퇴화 출력은 세지 않는다)

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
```

(3) `_render_png_b64` 다음에 `_render_page` 를 두고, `_extract_with_vlm`·`_extract_with_surya` 를 아래 전체로 바꾼다(키워드 인자 `render_lock` 을 받아 `_render_page` 로 렌더).

```python
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
```

(4) `extract_text` 바로 위에 `_ocr_pages` 를 두고, `extract_text` 를 아래 전체로 바꾼다(라우팅 루프는 Task 3 그대로 두되 채택은 `adopted`, OCR 대상은 `ocr_jobs` 로 모은다).

```python
async def _ocr_pages(
    doc: fitz.Document,
    jobs: list[tuple[int, PageResult | None, str]],
    result: ExtractionResult,
    book_id: str,
    remaining: float,
) -> dict[int, PageResult]:
    """OCR 이 필요한 쪽을 VLM_PAGE_CONCURRENCY 건씩 동시에 보내고 {쪽 번호: 채택 결과} 를 돌려준다.

    실패·퇴화 출력·데드라인 초과로 OCR 결과가 없는 쪽은 ODL 결과(있으면)로 채운다.
    """
    done: dict[int, PageResult] = {}
    if not jobs:
        return done
    engine = cfg.OCR_ENGINE.lower()
    sem = asyncio.Semaphore(cfg.VLM_PAGE_CONCURRENCY)
    render_lock = asyncio.Lock()

    async with httpx.AsyncClient() as client:
        async def _one(page_num: int, odl_page: PageResult | None, trigger: str) -> None:
            async with sem:
                log.info(f"[{book_id}] p.{page_num} → OCR 보완 ({trigger}, engine={engine})")
                page = doc.load_page(page_num)
                try:
                    if engine == "surya":
                        ocr_page = await _extract_with_surya(page, client, render_lock=render_lock)
                    else:
                        ocr_page = await _extract_with_vlm(
                            page, client, prompt_type="ocr", render_lock=render_lock
                        )
                except VlmDegenerateOutput as e:
                    log.warning(f"[{book_id}] {e} — ODL 결과 채택")
                    result.errors.append(f"{e} — ODL 결과 채택")
                    result.vlm_truncated += 1
                    ocr_page = odl_page
                except Exception as e:
                    log.error(f"[{book_id}] p.{page_num} OCR({engine}) 실패: {e}")
                    result.errors.append(f"p.{page_num} OCR({engine}): {e}")
                    result.ocr_errors += 1
                    ocr_page = odl_page  # OCR 실패 시 ODL 결과라도 살리기
                else:
                    if ocr_page.truncated:
                        result.vlm_truncated += 1
                if ocr_page is not None:
                    done[page_num] = ocr_page

        tasks = [asyncio.create_task(_one(*job)) for job in jobs]
        try:
            # Celery 소프트 리밋은 코루틴 안에서 믿을 수 없다(함정 19) — 자체 데드라인으로 끊는다.
            async with asyncio.timeout(max(remaining, 0.0)):
                await asyncio.gather(*tasks)
        except TimeoutError:
            await asyncio.gather(*tasks, return_exceptions=True)
            left = [n for n, _, _ in jobs if n not in done]
            result.deadline_hit = True
            log.warning(
                f"[{book_id}] 추출 데드라인({cfg.INGEST_EXTRACT_DEADLINE}s) 초과 — "
                f"OCR 못 한 {len(left)}쪽은 ODL 결과로 채택"
            )
            result.errors.append(f"추출 데드라인 초과 — {len(left)}쪽 ODL 결과 채택")
            for page_num, odl_page, _ in jobs:
                if page_num not in done and odl_page is not None:
                    done[page_num] = odl_page
    return done


async def extract_text(
    file_path: str | Path,
    book_id: str,
    *,
    file_bytes: bytes | None = None,
    force_ocr_short_pages: bool = False,
) -> ExtractionResult:
    """2티어 라우팅 파이프라인.

    force_ocr_short_pages: ODL 본문이 짧은 쪽을 판정 없이 모두 OCR 한다(섹션 0개 재추출용).

    1티어: OpenDataLoader로 전체 PDF 마크다운+json 추출
    2티어: 본문 부족 / CMap 손상 의심 / 표 셀 충전율 낮음 중 하나라도 해당하는
           페이지만 VLM 보완 (판단 기준은 파일 상단 docstring 참고). 판정은 쪽 순서대로 하고,
           OCR 은 문서 안에서 VLM_PAGE_CONCURRENCY 건씩 동시에 보내 결과를 쪽 순서로 조립한다.
           추출 전체가 INGEST_EXTRACT_DEADLINE 을 넘으면 남은 쪽은 ODL 결과로 채택한다.
    """
    t_start = time.monotonic()
    result = ExtractionResult(book_id=book_id, total_pages=0)

    # ── 1티어: OpenDataLoader 전체 추출 ──────────────────
    odl_result = await extract_text_opendataloader(
        file_path, book_id, file_bytes=file_bytes
    )
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

    result.total_pages = len(doc)
    log.info(
        f"[{book_id}] {result.total_pages}p — 1티어 ODL 완료 "
        f"({len(odl_result.pages)}p 추출), 2티어 라우팅 시작"
    )

    # 짧은 쪽은 같은 것끼리 견준다 — ODL 은 머리말·꼬리말을 지운 길이라 fitz 도 문서 전체에
    # 되풀이되는 줄을 뺀 길이로 잰다. CMap 손상 2배 비교는 예전처럼 원래 fitz 길이를 쓴다.
    fitz_texts = [_clean_text(p.get_text()) for p in doc]
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
    adopted: dict[int, PageResult] = {}
    ocr_jobs: list[tuple[int, PageResult | None, str]] = []

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
                        odl_page.text = _strip_figure_markers(odl_page.text)
                        adopted[page_num] = odl_page
                        continue
                    trigger = f"ODL 글자 유실 의심(ODL {body_len}자 vs 원본 추정 {fitz_check_len}자)"
                else:
                    need_ocr, why = page_routing.short_page_needs_ocr(
                        fitz_len_stripped=fitz_stripped_lens[page_num],
                        fitz_len_raw=fitz_check_len,
                        doc_is_scan=doc_is_scan,
                        force=force_ocr_short_pages,
                        min_chars=MIN_CHARS_PER_PAGE,
                    )
                    if not need_ocr:
                        # 원래 짧은 쪽(표지·간지 등) — ODL 결과 그대로 채택.
                        odl_page.text = _strip_figure_markers(odl_page.text)
                        adopted[page_num] = odl_page
                        continue
                    trigger = f"{why}(ODL {body_len}자 vs 원본 추정 {fitz_check_len}자)"

        # 문서당 VLM 보완 페이지 수 상한 — 완전 스캔본 대형 문서가 잡 전체를 지연시키는
        # 것을 방지. 초과분은 ODL 결과(비어있거나 부실해도) 그대로 채택하고 VLM은 스킵한다.
        if len(ocr_jobs) >= vlm_cap:
            if not result.vlm_capped:
                result.vlm_capped = True
                log.warning(f"[{book_id}] VLM 페이지 상한({vlm_cap}) 도달 — 이후 저텍스트 페이지는 ODL로 대체")
            if odl_page:
                adopted[page_num] = odl_page
            continue
        ocr_jobs.append((page_num, odl_page, trigger))

    remaining = cfg.INGEST_EXTRACT_DEADLINE - (time.monotonic() - t_start)
    ocr_done = await _ocr_pages(doc, ocr_jobs, result, book_id, remaining)
    doc.close()

    for page_num in range(result.total_pages):
        page_result = adopted.get(page_num) or ocr_done.get(page_num)
        if page_result is not None:
            result.pages.append(page_result)

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
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_ocr.py tests/test_extractor_routing.py tests/test_page_routing.py -q`
Expected: `48 passed`

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/extractor.py app/tests/test_extractor_ocr.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Feat] round07 — 스캔본 OCR 을 문서 안에서 VLM_PAGE_CONCURRENCY 건씩 동시에 보낸다: 판정은 쪽 순서대로, 렌더링은 asyncio.Lock 안에서 한 쪽씩(이벤트 루프 스레드), 결과는 쪽 순서로 조립. 추출 전체에 INGEST_EXTRACT_DEADLINE asyncio 데드라인을 두어 넘으면 남은 쪽은 ODL 결과로 채택하고 deadline_hit 를 남긴다(함정 19). OCR 실패 수(ocr_errors)·length 로 끝난 쪽 수(vlm_truncated)를 센다. VLM 60쪽 상한·OCR 실패 시 ODL 폴백은 그대로"
```

#### 묶음 4-3: `run_extract` 섹션 0개 — 강제 OCR 재추출 → `no_text` / `vlm_error`

- [ ] **Step 1: 실패하는 테스트 작성** — `app/tests/test_run_extract_sections.py`

`split_into_sections` 는 embedder(FlagEmbedding)를 끌어오므로 목으로 바꾼다(함정 13). DB·MinIO·doc_type 판별도 목이다.

```python
"""run_extract — 섹션 0개를 추출 성공으로 넘기지 않는다: 강제 OCR 재추출 → no_text / vlm_error."""
from unittest.mock import MagicMock

import pytest

from services.ingestion import extractor, stages
from services.ingestion.extractor import ExtractionResult, PageResult
from services.ingestion.stages import StageContext, StageError


def _extraction(text: str, *, ocr_errors: int = 0, deadline_hit: bool = False, vlm_truncated: int = 0):
    res = ExtractionResult(book_id="KCI_T", total_pages=3)
    res.pages = [PageResult(n, text, "opendataloader", 0.95) for n in range(3)]
    res.ocr_errors = ocr_errors
    res.deadline_hit = deadline_hit
    res.vlm_truncated = vlm_truncated
    return res


@pytest.fixture
def run_extract_with(monkeypatch):
    """extract_text 가 차례로 돌려줄 결과를 받아 run_extract 를 돌린다 → (meta, force 인자 기록, 저장된 추출)."""
    calls: list[bool] = []
    saved: list[ExtractionResult] = []

    def _run(*results: ExtractionResult) -> dict:
        queue = list(results)

        async def fake_extract_text(file_path, book_id, *, file_bytes=None, force_ocr_short_pages=False):
            calls.append(force_ocr_short_pages)
            return queue.pop(0)

        def fake_split(pages):
            if not any(p.text for p in pages):
                return []
            return [{"section_idx": 0, "text": "본문", "page_start": 0, "page_end": 2, "token_count": 10}]

        monkeypatch.setattr(extractor, "extract_text", fake_extract_text)
        monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())
        monkeypatch.setattr(stages, "split_into_sections", fake_split)
        monkeypatch.setattr(stages, "_ensure_book_and_doc_type", lambda ctx, path: "paper")
        monkeypatch.setattr(stages, "SyncSessionLocal", lambda: MagicMock())
        monkeypatch.setattr(stages, "save_extraction_artifact", lambda book_id, ext, client: saved.append(ext))
        return stages.run_extract(StageContext(book_id="KCI_T", file_path="C:/nowhere/KCI_T.pdf"))

    return _run, calls, saved


def test_sections_on_first_pass_do_not_reextract(run_extract_with):
    run, calls, _ = run_extract_with
    meta = run(_extraction("본문"))
    assert calls == [False]
    assert meta["sections"] == 1
    assert (meta["forced_ocr"], meta["vlm_truncated"], meta["extract_deadline_hit"], meta["ocr_errors"]) == (
        False, 0, False, 0)


def test_zero_sections_reextracts_with_forced_ocr(run_extract_with):
    run, calls, saved = run_extract_with
    second = _extraction("VLM 본문", vlm_truncated=1)
    meta = run(_extraction(""), second)
    assert calls == [False, True]
    assert meta["forced_ocr"] is True
    assert meta["vlm_truncated"] == 1
    assert saved == [second]


def test_zero_sections_after_forced_ocr_is_no_text(run_extract_with):
    run, calls, saved = run_extract_with
    with pytest.raises(StageError) as exc:
        run(_extraction(""), _extraction(""))
    assert exc.value.error_group == "no_text"
    assert calls == [False, True]
    assert saved == []


def test_zero_sections_after_forced_ocr_with_ocr_errors_is_vlm_error(run_extract_with):
    run, _, _ = run_extract_with
    with pytest.raises(StageError) as exc:
        run(_extraction(""), _extraction("", ocr_errors=2))
    assert exc.value.error_group == "vlm_error"


@pytest.mark.parametrize("first", [_extraction("", ocr_errors=3), _extraction("", deadline_hit=True)])
def test_ocr_trouble_on_first_pass_skips_forced_ocr(run_extract_with, first):
    run, calls, _ = run_extract_with
    with pytest.raises(StageError) as exc:
        run(first)
    assert exc.value.error_group == "vlm_error"
    assert calls == [False]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_run_extract_sections.py -q`
Expected: `6 failed` — `KeyError: 'forced_ocr'`, `assert [False] == [False, True]`, `Failed: DID NOT RAISE <class 'services.ingestion.stages.StageError'>` ×4

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/stages.py` 의 `run_extract` 두 곳(다른 작업이 같은 파일의 다른 함수를 고치므로 블록 단위로 바꾼다)

(1) 섹션 분할을 그림 저장 앞으로 올리고 섹션 0개를 처리한다.

```python
# old
        log.info(f"[{book_id}] 추출 완료: {extraction.stats}")

        if extraction.figures:
            n_figs = save_figures(book_id, extraction.figures, client)
            log.info(f"[{book_id}] 그림 {n_figs}개 저장 완료")

        sections = split_into_sections(extraction.pages)
        log.info(f"[{book_id}] 섹션 {len(sections)}개 분할 완료")
# new
        log.info(f"[{book_id}] 추출 완료: {extraction.stats}")

        sections = split_into_sections(extraction.pages)
        forced_ocr = False
        if not sections:
            # 첫 추출에서 OCR 이 실패했거나 데드라인에 걸렸으면 지금 다시 해도 같다 — 추출부터
            # 재시도하도록 넘긴다(두 번째 추출까지 돌면 단계 시간이 stale 판정 3600초를 넘을 수 있다).
            if extraction.ocr_errors or extraction.deadline_hit:
                raise StageError(
                    "vlm_error",
                    f"섹션 0개 — OCR 오류 {extraction.ocr_errors}건·데드라인 {extraction.deadline_hit}: "
                    f"{extraction.errors[:3]}",
                )
            log.warning(f"[{book_id}] 섹션 0개 — 짧은 쪽을 모두 OCR 로 보내 다시 추출")
            forced_ocr = True
            extraction = run_async(extract_text(local_path, book_id, force_ocr_short_pages=True))
            sections = split_into_sections(extraction.pages) if extraction.pages else []
            if not sections:
                if extraction.ocr_errors or extraction.deadline_hit:
                    raise StageError(
                        "vlm_error",
                        f"섹션 0개(강제 OCR) — OCR 오류 {extraction.ocr_errors}건·데드라인 "
                        f"{extraction.deadline_hit}: {extraction.errors[:3]}",
                    )
                raise StageError(
                    "no_text",
                    f"섹션 0개 — 강제 OCR 재추출로도 본문 없음({extraction.total_pages}쪽)",
                )
        log.info(f"[{book_id}] 섹션 {len(sections)}개 분할 완료")

        if extraction.figures:
            n_figs = save_figures(book_id, extraction.figures, client)
            log.info(f"[{book_id}] 그림 {n_figs}개 저장 완료")
```

(2) 반환 meta 에 공통 계약의 네 키를 더한다.

```python
# old
            "doc_type": doc_type,
            "vlm_capped": extraction.vlm_capped,
# new
            "doc_type": doc_type,
            "vlm_capped": extraction.vlm_capped,
            "forced_ocr": forced_ocr,
            "vlm_truncated": extraction.vlm_truncated,
            "extract_deadline_hit": extraction.deadline_hit,
            "ocr_errors": extraction.ocr_errors,
```

`_run_stage` 는 성공한 단계의 반환 dict 만 `meta_update` 로 적는다 — `no_text`·`vlm_error` 로 끝난 추출은 이 네 키가 남지 않고 `error_group`·`last_error` 로만 보인다(Task 2 가 실패 meta 를 따로 적지 않는 한).

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_run_extract_sections.py tests/test_embed_index_guard.py -q`
Expected: `10 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: Task 3 뒤 수 + 15 passed, 수집 오류 3(사본 측정: 929 → 944)

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/stages.py app/tests/test_run_extract_sections.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Fix] round07 — 섹션 0개를 추출 성공으로 넘기지 않는다: 짧은 쪽을 모두 OCR 로 보내 한 번 더 추출하고, 그래도 0개면 OCR 오류·데드라인이 있었으면 vlm_error(추출부터 재시도), 없었으면 no_text(결정적 — 재시도 안 함). 첫 추출에서 이미 OCR 이 실패했거나 데드라인에 걸렸으면 강제 재추출 없이 vlm_error(두 번째 추출까지 돌면 stale 판정 3600초를 넘을 수 있다). meta 에 forced_ocr·vlm_truncated·extract_deadline_hit·ocr_errors"
```

---

### Task 5: ODL 타임아웃·fitz 재저장 재시도·fitz 폴백과 이미지 끄기

> **실행 메모(2026-10-02, Task 5 리뷰 반영):** 근거 ③(이 PC 에서 표 많은 문서가 상한의 78%)은 한 건씩 변환한 값이다. 리뷰가 24스레드 PC 에서 동시 변환을 재 보니 KCI_FI001930485(37쪽, 상한 18.5초)가 혼자 12초, 4건 동시 28초, 8건 동시 47초였다 — `celery-cpu` 4칸이 함께 변환하면 상한을 넘어 재저장본 재시도 뒤 fitz 텍스트(표 구조·머리말 제거 없음)로 떨어진다. 그래서 사용자 결정(2026-10-02)으로 기본값을 `ODL_TIMEOUT_BASE_SECONDS` 10.0·`ODL_TIMEOUT_PER_PAGE_SECONDS` 1.5 로 올렸다(9cc502d — 쪽당 1.5초면 4건 동시 상한의 0.51, 8건 동시 0.84, 기본 10초는 JVM 기동 몫). 상한이 길어진 만큼 ODL 을 추출 데드라인에 묶었다: `extract_text` 가 `time_budget`(데드라인 − 경과)을 `extract_text_opendataloader` 에 넘기고, 시도마다 상한은 min(쪽수 상한, 남은 시간), 2초(`_ODL_MIN_ATTEMPT_SECONDS`)도 안 남으면 그 시도를 띄우지 않는다(`ODL 실패(…): 추출 데드라인까지 N초 — 변환하지 않음` 뒤 fitz 텍스트). 시간 초과 사유(`N초 초과`)와 INFO 로그의 상한은 그 시도가 실제로 쓴 값이다. 그래서 섹션 0개 강제 재추출의 ODL 까지 남은 추출 시간 안에서 돌아 추출 단계가 stale 판정 3600초 아래에 든다. 아래 본문의 5초·0.5초와 근거 ③ 의 78% 는 첫 구현 기준이다. 리뷰 뒤 더한 것: `fastapi`·`celery-worker`·`celery-cpu` 에 `init: true`(97ca88c — 시간 초과로 끈 자식의 고아 java 를 PID 1 이 거둔다), `ODL_IMAGE_OUTPUT` 을 `off`·`embedded`·`external` 로 검증(1a56e93 — 오타가 모든 문서를 조용히 fitz 텍스트로 바꾸지 않고 앱이 뜨지 않게), `run_extract` 의 meta 에 `odl_fallback`(`resaved`·`fitz`·null)·`odl_seconds` 와 시도마다 `ODL {초}초 / 상한 {초}초` INFO 로그(3ccaaf5), 실패 메시지에 원인 줄(6294130), ODL 자식이 상한 + 5초에 SIGALRM 으로 자기 프로세스 그룹(java 포함)을 끈다(8bfe4a6 — 부모 풀 자식이 먼저 끊겨도 끝없이 돌지 않게). 카나리에서 보는 법은 `docs/ops/bulk_ingest_runbook.md` §9-7 ⑩. 아래 '패키지 실제 구현 근거'는 이 PC 의 opendataloader-pdf 2.5.0 을 읽은 것이다 — 운영·고정 버전은 2.5.9(fe1be0c)이고, 2.5.9 에서 다시 확인하는 중이다(조각 D 머리말 실행 메모).

**Files:**
- Modify: `app/services/ingestion/extractor.py` (import, `_ODL_CHILD`·`_kill_process_group`·`_odl_convert`·`_run_odl`·`_fitz_text_pages`(새), `extract_text_opendataloader`)
- Test: `app/tests/test_extractor_odl.py`(새)

**이 작업이 지키는 것(조정자 조건).** SKOVIX 의 저수준 로더 호출을 그대로 둔다 — `opendataloader_pdf.convert(format=["markdown","json"], table_method="cluster", markdown_page_separator=…, keep_line_breaks=False, quiet=True)` 한 번으로 markdown·json 을 함께 받고, json 으로 `table_fill_ratios`·`page_headers_footers` 를 만드는 코드(4e10275·ac0a213·7cdf27b·8b1511a)는 한 줄도 바꾸지 않는다. nanet 의 고수준 `OpenDataLoaderPDFLoader` 로 되돌리지 않는다. 그 위에 타임아웃·재저장 재시도·fitz 폴백만 얹는다.

**자바 프로세스를 남기지 않는 방법 — 패키지 실제 구현 근거.** 이 PC 설치본 `opendataloader-pdf 2.5.0`(`C:/Users/LANDSOFT/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages/opendataloader_pdf/`):
- `convert_generated.py` 의 `convert(...)` 는 인자를 CLI 옵션 목록으로 바꿔 `run_jar(args, quiet)` 를 부를 뿐이다.
- `runner.py` 의 `run_jar` 는 `quiet=True` 일 때 `subprocess.run(["java", "-Djava.awt.headless=true", "-Dapple.awt.UIElement=true", "-jar", <패키지 jar/opendataloader-pdf-cli.jar>, *args], stdout=PIPE, stderr=PIPE, check=True, …)` — **timeout 인자가 없고 Popen 핸들도 밖으로 내주지 않는다.** `start_new_session` 도 쓰지 않으므로 java 는 부른 프로세스와 같은 프로세스 그룹에 들어간다.
- 그래서 지금처럼(또 nanet 5f8fb80 처럼) `run_in_executor` 를 `wait_for` 로 감싸면, 시간이 지나도 스레드는 `subprocess.run` 안에서 계속 막혀 있고 java 도 끝까지 돈다. nanet 5f8fb80 의 주석이 이 한계를 그대로 적어 두었다("run_in_executor 스레드 자체는 Python에서 강제 종료할 수 없어 백그라운드에서 계속 돌 수 있음"). **nanet 에는 프로세스를 끄는 구현이 없다** — 가져올 것이 없어 새로 둔다.
- 방법: `convert(**kwargs)` 를 자식 파이썬(`sys.executable -c …`)에서 부르고 `start_new_session=True` 로 새 세션(그룹 id = 자식 pid)에 둔다. 시간을 넘기면 `os.killpg(pid, SIGKILL)` 로 자식 파이썬과 java 손자를 함께 끈다. 셀러리 prefork 워커는 데몬 프로세스라 `multiprocessing` 자식을 둘 수 없어서 `create_subprocess_exec` 를 쓴다. convert 의 인자→CLI 변환은 패키지에 그대로 맡긴다(requirements 가 버전을 고정하지 않아, jar 경로·CLI 옵션을 우리가 베끼면 패키지 업데이트 때 깨진다).
- stderr 는 파이프가 아니라 임시 파일로 받는다. 파이프로 받으면 자식을 끈 뒤에도 그 파이프 끝을 쥔 손자가 살아 있는 동안 이벤트 루프가 읽기를 기다린다(사본에서 Windows 20초 대기로 확인 — 리눅스는 killpg 로 손자가 죽어 문제가 없지만 두 OS 에서 같게 둔다).
- 확인: WSL Ubuntu(파이썬 3.12)에서 `_odl_convert` 소스만 떼어 '손자를 띄우고 잠드는 자식'을 2초 상한으로 돌리면 2.0초에 `TimeoutError`, 손자 프로세스는 사라졌다(`/proc/<pid>` 없음). 실제 PDF 6건을 예전 방식(같은 프로세스 `convert`)과 자식 방식으로 돌려 markdown·json 의 sha256 이 6/6 같았고, 자식 방식이 평균 0.057초 더 걸렸다.

**재시도·폴백 순서와 손상 판정의 뜻.**
1. fitz 로 쪽수를 센다 → 타임아웃 = max(`ODL_TIMEOUT_BASE_SECONDS`, 쪽수 × `ODL_TIMEOUT_PER_PAGE_SECONDS`).
2. 원본으로 ODL. 시간 초과·비정상 종료·markdown 없음이면 → 3.
3. fitz 로 다시 저장한(`garbage=4, clean=True, deflate=True`, nanet 5f8fb80 — xref 손상 문서 15분 → 3분) PDF 로 ODL 한 번 더. 그래도 안 되면 → 4.
4. fitz 텍스트를 1티어 결과로 쓴다(쪽 method `"fitz"`, 글자 없는 쪽은 넣지 않음).
- fitz 로도 열리지 않는 파일(쪽수 0 포함 손상): 원본 ODL 한 번만(기본 타임아웃) 시도하고 재저장·fitz 폴백은 하지 않는다. ODL 도 실패하면 결과가 비고, `extract_text` 의 fitz 열기도 실패해 `run_extract` 는 지금처럼 `extract_empty` 다.
- 폴백 경로에서도 교차검증의 뜻은 흐려지지 않는다: 1티어가 fitz 텍스트이므로 CMap 2배 비교는 fitz 대 fitz(비율 1)라 걸리지 않는다 — 'ODL 이 글자를 잃었나'를 물을 ODL 이 없고, fitz 는 그 비교의 기준(손상에 관대한 쪽)이다. 짧은 쪽 분기는 그대로 돈다: fitz 0자 쪽은 폴백 결과에 넣지 않아 'ODL 누락' → OCR(= 텍스트 층 없음 → OCR), 글자가 조금 있는 쪽은 Task 3 의 문서 단위 판정을 그대로 탄다. 잃는 것은 머리말·꼬리말 제거(json 이 없다)와 표 구조뿐이다.

**이미지 끄기(`image_output` → `cfg.ODL_IMAGE_OUTPUT`, 기본 `"off"`)에 기대는 코드 점검 — 하나씩.**
- `FigureData`·`figures` 생성: `extract_text_opendataloader` 만 만들고, `extract_text` 는 `odl_result.figures` 를 결과로 옮기지 않는다 → `run_extract` 의 `if extraction.figures:`(stages.py:289) 는 늘 거짓이라 `save_figures` 가 돌지 않고, `paper_enricher` 의 그림 설명은 MinIO `figures/{id}/` 를 읽는데 거기 쓰는 곳은 `save_figures` 뿐이다(운영 그림 저장 0건과 일치). `api/book.py` 비교 API 와 `pdf_meta_extractor` 는 `pages` 만 쓴다 → 영향 없음.
- `[그림]` 마커 정리(`_strip_figure_markers`·`body_len`): off 면 마커가 아예 생기지 않을 뿐이다. 라우팅 주석의 '워터마크가 [그림]으로 잡힘'은 이미 길이에서 빼고 있던 것이라 판정이 같다.
- `table_fill_ratios`·머리말/꼬리말 제거: 둘 다 json 에서 만든다. json 에는 off 에서도 `image` 요소가 그대로 있다. 실제 PDF 비교는 위 근거 ⑥.
- **영향이 있는 곳 하나 — 그림만 있는 쪽.** embedded 에서는 그 쪽 markdown 이 `[그림]` 이라 'ODL 이 본 빈 쪽'(본문 0자 → fitz 교차검증)인데, off 에서는 markdown 에서 쪽이 통째로 빠져 `extract_text` 가 'ODL 누락'(판정 없이 OCR)으로 본다 — 실패 블록 스캔본에서 확인했다(embedded 14쪽 모두 `[그림]\n\n[그림]`, off 0쪽). 그대로 두면 그림만 있는 쪽(디지털 논문의 그림 쪽 포함)이 fitz 교차검증 없이 모두 VLM 을 탄다. 그래서 json 에 그림 요소가 있는데 markdown 에 없는 쪽을 빈 텍스트 쪽으로 남긴다(5-2). 이렇게 하면 라우팅 판정이 embedded 와 같다(근거 ⑥).
- VLM 실패 시 ODL 폴백 텍스트: embedded 에서는 그림 쪽 폴백이 `[그림]\n\n[그림]` 을 그대로 본문으로 남겼고(`_strip_figure_markers` 를 거치지 않음), off 에서는 빈 쪽이다 — 나아지는 쪽이다.
- 덤: KCI_FI001930485(섹션 196개 중 172개가 `<br>` 반복)는 embedded markdown 파일이 107MB(그림 base64 포함)·`<br>` 324,402개, off 는 83KB·`<br>` 104개였다 — 표 칸에 박힌 그림 인코딩이 `<br>` 격자를 만들고 있었다(근거 ⑤). 그림 인코딩이 큰 문서는 off 가 훨씬 빠르다(KCI_FI000858284 14쪽: embedded 13.4초 → off 1.85초, 근거 ④).
- 쪽수 비례 상한(0.5초/쪽)은 이 PC 에서 표가 많은 문서가 상한의 78%까지 썼다(근거 ③). 운영에서 `embedded` 로 되돌리면 그림 인코딩 시간 때문에 상한에 자주 닿는다 — `ODL_IMAGE_OUTPUT` 를 바꿀 때는 `ODL_TIMEOUT_PER_PAGE_SECONDS` 도 함께 본다.

#### 묶음 5-1: 자식 프로세스 변환·쪽수 비례 타임아웃·재저장 재시도·fitz 폴백

- [ ] **Step 1: 실패하는 테스트 작성** — `app/tests/test_extractor_odl.py`

`_odl_convert` 를 목으로 바꿔 산출물을 직접 써 넣는다. 패키지가 없는 환경에서도 돌게 `opendataloader_pdf` 를 빈 모듈로 꽂는다. 마지막 두 테스트는 실제 하위 프로세스로 끄기·종료 코드를 확인한다(손자 확인은 리눅스에서만).

```python
"""extract_text_opendataloader — 쪽수 비례 타임아웃 → fitz 재저장본 재시도 → fitz 텍스트 폴백(5-1), 이미지 끄기(5-2).

ODL 변환(_odl_convert)은 목으로 바꾸고 산출물(markdown·json)을 직접 써 넣는다. 자식 프로세스를
끄는 동작만 실제 하위 프로세스로 확인한다.
"""
import asyncio
import json
import os
import sys
import time
import types
from pathlib import Path

import fitz
import pytest

from services.ingestion import extractor

SEP = "\n<<<ODL_PAGE_BREAK_%page-number%>>>\n"


@pytest.fixture(autouse=True)
def _odl_package(monkeypatch):
    """설치 확인용 import 만 통과시킨다 — 변환은 _odl_convert 목이 하므로 패키지가 없어도 된다."""
    monkeypatch.setitem(sys.modules, "opendataloader_pdf", types.ModuleType("opendataloader_pdf"))


def _pdf(texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in texts:
        page = doc.new_page(width=300, height=400)
        if text:
            page.insert_text((36, 60), text, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def _write_outputs(out_dir: str, pages: dict[int, str], json_kids: list[dict] | None = None) -> None:
    md = "".join(SEP.replace("%page-number%", str(n)) + text for n, text in sorted(pages.items()))
    Path(out_dir, "doc.md").write_text(md, encoding="utf-8")
    Path(out_dir, "doc.json").write_text(json.dumps({"kids": json_kids or []}), encoding="utf-8")


def _patch_convert(monkeypatch, behaviours: list) -> list[dict]:
    """behaviours[i] — i 번째 변환에서 던질 예외, 또는 써 넣을 {쪽: 텍스트} / ({쪽: 텍스트}, json kids)."""
    calls: list[dict] = []

    async def fake_convert(kwargs, timeout):
        calls.append({**kwargs, "timeout": timeout, "input_exists": os.path.exists(kwargs["input_path"])})
        b = behaviours[len(calls) - 1]
        if isinstance(b, BaseException):
            raise b
        pages, kids = b if isinstance(b, tuple) else (b, None)
        _write_outputs(kwargs["output_dir"], pages, kids)

    monkeypatch.setattr(extractor, "_odl_convert", fake_convert)
    return calls


def _run(pdf: bytes, **kwargs):
    return asyncio.run(extractor.extract_text_opendataloader(None, "T_ODL", file_bytes=pdf, **kwargs))


def test_convert_writes_markdown_and_json_with_page_scaled_timeout(monkeypatch):
    calls = _patch_convert(monkeypatch, [{1: "첫 쪽 본문", 2: "둘째 쪽 본문"}])
    result = _run(_pdf(["a"] * 30))
    assert calls[0]["format"] == ["markdown", "json"]
    assert calls[0]["timeout"] == 15.0  # max(5, 30 × 0.5)
    assert [(p.page_num, p.text, p.method) for p in result.pages] == [
        (0, "첫 쪽 본문", "opendataloader"), (1, "둘째 쪽 본문", "opendataloader")]
    assert result.errors == []


def test_short_document_gets_base_timeout(monkeypatch):
    calls = _patch_convert(monkeypatch, [{1: "본문"}])
    _run(_pdf(["a"] * 4))
    assert calls[0]["timeout"] == 5.0


def test_timeout_retries_once_with_fitz_resaved_pdf(monkeypatch):
    calls = _patch_convert(monkeypatch, [TimeoutError(), {1: "재저장본 본문"}])
    result = _run(_pdf(["a", "b"]))
    assert len(calls) == 2
    assert calls[1]["input_path"] != calls[0]["input_path"]
    assert calls[1]["input_exists"]
    assert not os.path.exists(calls[1]["input_path"])  # 재저장 임시 파일은 지운다
    assert [p.text for p in result.pages] == ["재저장본 본문"]
    assert any("ODL 실패(원본)" in e for e in result.errors)


def test_both_attempts_fail_falls_back_to_fitz_text(monkeypatch):
    _patch_convert(monkeypatch, [RuntimeError("ODL 변환 실패(exit 1)"), TimeoutError()])
    result = _run(_pdf(["First page body", "", "Third page body"]))
    assert [(p.page_num, p.text, p.method) for p in result.pages] == [
        (0, "First page body", "fitz"), (2, "Third page body", "fitz")]
    assert "ODL 실패 — fitz 텍스트로 대체" in result.errors


def test_unopenable_file_gets_no_resave_or_fitz_fallback(monkeypatch):
    calls = _patch_convert(monkeypatch, [RuntimeError("ODL 변환 실패(exit 1)")])
    result = _run(bytes(range(256)) * 40)
    assert len(calls) == 1
    assert calls[0]["timeout"] == 5.0
    assert result.pages == []
    assert any("ODL 실패(원본)" in e for e in result.errors)


def test_nonzero_exit_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(extractor, "_ODL_CHILD", "import sys; sys.stderr.write('boom'); sys.exit(3)")
    with pytest.raises(RuntimeError, match="exit 3"):
        asyncio.run(extractor._odl_convert({}, 30))


def test_timeout_kills_child_process_group(monkeypatch, tmp_path):
    """시간을 넘기면 자식(파이썬)과 그 자식(java 자리)을 함께 끈다. 손자 확인은 killpg 가 있는 리눅스에서만."""
    pid_file = tmp_path / "grandchild.pid"
    script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(20)\n"
    )
    monkeypatch.setattr(extractor, "_ODL_CHILD", script)
    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(extractor._odl_convert({}, 2.0))
    assert time.monotonic() - t0 < 10
    if sys.platform == "win32":
        return
    grandchild = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        with open(f"/proc/{grandchild}/stat") as f:  # 회수 전 좀비(Z)면 끝난 것으로 본다
            if f.read().split()[2] == "Z":
                break
        time.sleep(0.1)
    else:
        pytest.fail("timeout 뒤에도 손자 프로세스가 살아 있다")
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_odl.py -q`
Expected: `7 failed` — `AttributeError: <module 'services.ingestion.extractor' ...> has no attribute '_odl_convert'`(5), `... has no attribute '_ODL_CHILD'`(2)

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/extractor.py`

(1) import 를 아래로 바꾼다.

```python
# old
import asyncio
import io
import logging
import time
from pathlib import Path
# new
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
```

(2) `async def extract_text_opendataloader(` 부터 파일 끝까지를 아래로 바꾼다. 변환 인자·json 파싱·markdown 쪽 나누기·그림 추출 코드는 지금 것 그대로이고(`image_output` 은 이 묶음에서는 `"embedded"` 그대로), 바뀐 곳은 변환을 `_run_odl` 로 부르는 부분과 실패 시 재저장·폴백, 정리(`finally`)다.

```python
# opendataloader_pdf.convert → runner.run_jar 는 java 를 subprocess.run(timeout 없음)으로 띄우고 끝날
# 때까지 막는다. 같은 프로세스의 스레드에서 돌리면 wait_for 가 시간을 넘겨도 스레드와 java 는 계속
# 돈다(nanet 5f8fb80 주석도 같은 한계를 적어 두었다). 그래서 convert 를 자식 파이썬에서 부르고,
# 새 세션(프로세스 그룹)으로 떼어 두었다가 시간을 넘기면 그룹째 끈다 — java 손자까지 함께 죽는다.
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
            "image_output": "embedded",  # 이미지 base64 인라인 (없으면 그림 흔적조차 안 남음)
            "image_format": "jpeg",      # base64 크기 절감
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
    """ODL 이 끝내 실패한 문서 — fitz 텍스트를 1티어 결과로 쓴다(표·머리말 구조 없음).

    글자가 없는 쪽은 넣지 않는다 — ODL 이 빈 쪽을 내지 않는 것과 같게 두어 extract_text 가
    'ODL 누락'으로 OCR 하게 한다.
    """
    pages: list[PageResult] = []
    with fitz.open(path) as doc:
        for page in doc:
            if max_pages and page.number >= max_pages:
                break
            raw = page.get_text("text").strip()
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
        except RuntimeError as e:
            page_count = None
            log.warning(f"[{book_id}] fitz 로 열리지 않는 PDF — ODL 만 한 번 시도: {e}")
        odl_timeout = max(
            cfg.ODL_TIMEOUT_BASE_SECONDS, (page_count or 0) * cfg.ODL_TIMEOUT_PER_PAGE_SECONDS
        )

        out_dir = tempfile.mkdtemp()
        md_file: Path | None = None
        try:
            md_file = await _run_odl(load_path, out_dir, _PAGE_SEP, odl_timeout)
        except (TimeoutError, RuntimeError, OSError) as e:
            reason = f"{odl_timeout:.0f}초 초과" if isinstance(e, TimeoutError) else str(e)
            log.warning(f"[{book_id}] ODL 실패({reason}) — fitz 재저장본으로 한 번 더")
            result.errors.append(f"ODL 실패(원본): {reason}")
            if page_count is not None:
                # xref 손상 문서에서 ODL(Java)이 브루트포스 복구로 수십 배 느려지는 문제 대응(nanet 5f8fb80)
                try:
                    fd, resaved_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(fd)
                    with fitz.open(load_path) as src:
                        src.save(resaved_path, garbage=4, clean=True, deflate=True)
                    shutil.rmtree(out_dir, ignore_errors=True)
                    out_dir = tempfile.mkdtemp()
                    md_file = await _run_odl(resaved_path, out_dir, _PAGE_SEP, odl_timeout)
                except (TimeoutError, RuntimeError, ValueError, OSError) as e2:
                    reason2 = f"{odl_timeout:.0f}초 초과" if isinstance(e2, TimeoutError) else str(e2)
                    result.errors.append(f"ODL 실패(fitz 재저장본): {reason2}")

        if md_file is None:
            if page_count is not None:
                result.pages = _fitz_text_pages(load_path, max_pages)
                result.total_pages = len(result.pages)
                result.errors.append("ODL 실패 — fitz 텍스트로 대체")
                log.warning(f"[{book_id}] ODL 실패 — fitz 텍스트 {len(result.pages)}쪽으로 대체")
            return result

        out_path = Path(out_dir)
        json_files = list(out_path.glob("*.json"))

        # ── JSON → 페이지별 표 셀 충전율(라우팅 신호) + 머리말/쪽번호 텍스트 ──
        page_headers_footers: dict[int, set[str]] = {}
        if json_files:
            try:
                with open(json_files[0], encoding="utf-8") as f:
                    jdata = json.load(f)
                by_page: dict[int, list] = defaultdict(list)
                for el in jdata.get("kids", []):
                    by_page[el.get("page number", 1)].append(el)
                for pnum, elements in by_page.items():
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
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_odl.py tests/test_extractor_ocr.py tests/test_extractor_routing.py -q`
Expected: `27 passed` (타임아웃 테스트가 약 2초)

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/extractor.py app/tests/test_extractor_odl.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Fix] round07 — ODL 변환에 쪽수 비례 타임아웃 max(ODL_TIMEOUT_BASE_SECONDS, 쪽수×ODL_TIMEOUT_PER_PAGE_SECONDS) 을 두고, 넘거나 실패하면 fitz 로 다시 저장한 PDF 로 한 번 더, 그래도 안 되면 fitz 텍스트로 대신한다(nanet 5f8fb80). convert 는 java 를 timeout 없는 subprocess.run 으로 띄워 스레드 wait_for 로는 못 끊으므로 자식 파이썬의 새 세션에서 부르고 넘으면 프로세스 그룹째 끈다. convert(markdown+json) 호출과 json 기반 표 셀 충전율·머리말 제거는 그대로. fitz 로도 안 열리는 파일은 재저장·폴백 없이 지금처럼 extract_empty"
```

#### 묶음 5-2: `image_output` 끄기와 그림만 있는 쪽 보존

- [ ] **Step 1: 실패하는 테스트 추가** — `app/tests/test_extractor_odl.py` 끝에 덧붙인다

```python
# ── 5-2 ──────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["off", "embedded"])
def test_convert_uses_image_output_setting(monkeypatch, mode):
    calls = _patch_convert(monkeypatch, [{1: "본문"}])
    monkeypatch.setattr(extractor.cfg, "ODL_IMAGE_OUTPUT", mode)
    _run(_pdf(["a"]))
    assert calls[0]["image_output"] == mode


def test_image_only_page_stays_as_empty_odl_page(monkeypatch):
    """image_output=off 면 그림만 있는 쪽이 markdown 에서 빠진다 — json 의 그림 요소로 빈 쪽을 남긴다."""
    kids = [{"type": "paragraph", "page number": 1, "content": "첫 쪽"},
            {"type": "image", "page number": 2},
            {"type": "paragraph", "page number": 3, "content": "셋째 쪽"}]
    _patch_convert(monkeypatch, [({1: "첫 쪽", 3: "셋째 쪽"}, kids)])
    result = _run(_pdf(["a", "b", "c"]))
    assert [(p.page_num, p.text) for p in result.pages] == [(0, "첫 쪽"), (1, ""), (2, "셋째 쪽")]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_odl.py -q`
Expected: `2 failed, 8 passed` — `test_convert_uses_image_output_setting[off]`(`'embedded' == 'off'`), `test_image_only_page_stays_as_empty_odl_page`(쪽 1 없음)

- [ ] **Step 3: 최소 구현** — `app/services/ingestion/extractor.py`

(1) `_run_odl` 의 이미지 두 줄:

```python
# old
            "image_output": "embedded",  # 이미지 base64 인라인 (없으면 그림 흔적조차 안 남음)
            "image_format": "jpeg",      # base64 크기 절감
# new
            "image_output": cfg.ODL_IMAGE_OUTPUT,  # 그림 저장은 운영 0건 — 기본 off 로 인코딩을 아낀다
            "image_format": "jpeg",
```

(2) json 파싱에서 그림 요소가 있는 쪽을 모은다.

```python
# old
        page_headers_footers: dict[int, set[str]] = {}
# new
        page_headers_footers: dict[int, set[str]] = {}
        image_pages: set[int] = set()  # 1-based — 그림 요소가 있는 쪽
```

```python
# old
                for pnum, elements in by_page.items():
                    hf_lines: set[str] = set()
# new
                for pnum, elements in by_page.items():
                    if any(el.get("type") == "image" for el in elements):
                        image_pages.add(pnum)
                    hf_lines: set[str] = set()
```

(3) markdown 쪽 목록을 만든 바로 다음(`if max_pages:` 앞)에 그림만 있는 쪽을 빈 쪽으로 넣는다.

```python
        # image_output=off 면 그림만 있는 쪽이 markdown 에서 통째로 빠진다. embedded 일 때처럼
        # 'ODL 이 본 빈 쪽'으로 남겨야 extract_text 가 'ODL 누락'(판정 없이 OCR) 대신 fitz 교차검증을 탄다.
        seen = {pnum for pnum, _ in documents}
        documents.extend((pnum, "") for pnum in image_pages if pnum not in seen)
        documents.sort(key=lambda d: d[0])
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_extractor_odl.py -q`
Expected: `10 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: Task 4 뒤 수 + 10 passed, 수집 오류 3(사본 측정: 944 → 954)

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/extractor.py app/tests/test_extractor_odl.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Fix] round07 — ODL image_output 을 ODL_IMAGE_OUTPUT(기본 off)으로: 추출 결과의 그림은 저장되지 않아(운영 0건) base64 인코딩만 비용이었다. off 면 그림만 있는 쪽이 markdown 에서 빠져 'ODL 누락'(판정 없이 OCR)이 되므로, json 에 그림 요소가 있는 쪽은 빈 쪽으로 남겨 라우팅 판정을 embedded 와 같게 둔다. 표 칸 그림 인코딩이 만들던 <br> 격자도 사라진다"
```

---

### Task 6: 논문 보강을 요약 단계로, 단계 세마포어, 표 해석 잘림

spec 1·5·10번. embed 칸(`celery-embed` 동시 1) 시간의 46~59%가 그 안의 논문 보강 LLM 대기다. 보강(`enrich_paper` — 키워드·참고문헌 LLM 폴백·표 해석·그림 설명)을 요약 단계(`q_llm`, `celery-llm`)로 옮겨 섹션 요약과 같은 asyncio 루프에서 돌리고, embed 단계는 보강 아티팩트(`artifacts/{id}/enrichment.json.gz`)로 청크만 만든다.

- **세마포어 하나:** 요약 단계 안에서 섹션 요약과 표 해석이 함께 돈다. 세마포어를 따로 두면 프로세스당 4 + 4 = 8, `celery-llm` 4개 합계 32 로 gemma 16석을 넘는다. 그래서 `run_summarize` 가 `LLM_SECTION_CONCURRENCY` 세마포어 하나를 만들어 섹션 요약과 보강의 모든 gemma 호출(키워드·참고문헌 폴백·표 해석)이 나눠 쓴다. `celery-llm` 은 프로세스당 태스크 1개라 단계 세마포어 = 프로세스 상한이다. `run_async` 가 단계마다 새 이벤트 루프를 만들므로(`stages.py` `run_async`) 세마포어는 그 루프 안에서 만든다 — 모듈 전역 세마포어는 쓰지 않는다. 그림 설명(VLM)은 다른 서버라 세마포어 밖에 그대로 둔다.
- **아티팩트가 없을 때:** 배포 전 체크포인트에 머문 아이템이나 요약 단계가 보강을 만들지 못한 아이템은 embed 가 예전처럼 직접 보강한다(드문 경로). `enrich_paper` 는 httpx·MinIO 만 쓰고 torch 를 쓰지 않아 GPU 없는 `celery-llm` 에서 돈다(함정 17).
- **DB:** 요약 단계는 LLM 을 다 기다린 뒤에 세션을 연다(함정 18) — 섹션 요약 저장(기존)과 보강 반영(`_persist_enrichment`)이 각자 짧게 열고 닫는다.
- **표 해석:** 상한 600 은 그대로 둔다(올려도 임베딩 창 512토큰이 같은 자리를 자른다). 표 원본 청크가 따로 색인되므로 프롬프트를 '모든 행·열' 대신 '핵심 비교·경향 몇 문장'으로 바꾸고, 개수 예시는 쓰지 않는다(함정 15). `finish_reason == "length"` 면 마지막으로 끝난 문장까지만 남긴다(Task 1 의 `chat_full`).
- **옛 보강 아티팩트를 막는다.** 마무리 단계는 추출 아티팩트만 지우고 보강 아티팩트는 남긴다. 그래서 재처리 문서(빈 본문 완료분·실패분)에는 이전 실행의 `enrichment.json.gz` 가 남아 있고, 이번 요약 단계의 보강이 실패하면 embed 가 그것을 읽는다. 다음 두 가지를 함께 쓴다.
  - **run_token:** `save_enrichment_artifact(..., run_token=)` 이 페이로드에 이 체인의 실행 토큰(`ctx.item_meta["run_token"]`, 없으면 `None`)을 남긴다. `load_enrichment_artifact(..., run_token=)` 는 호출 쪽과 저장 쪽에 모두 토큰이 있는데 서로 다르면 `None` 을 돌려준다(다른 실행이 남긴 것). 토큰 없이 저장된 배포 전 아티팩트와 토큰 없는 호출(단건 흐름 `process_book_file`)은 그대로 읽는다 — 배포 전 체크포인트 호환.
  - **요약 단계 시작 때 삭제:** `run_summarize` 가 논문 보강을 시작하기 전에 `delete_enrichment_artifact` 로 옛 아티팩트를 지운다(best-effort — 실패해도 경고만).
  - **왜 둘 다인가:** 토큰만으로는 모자라다. 호환 규칙 때문에 토큰 없는 배포 전 아티팩트는 비교를 통과하는데, 이번 재처리 대상의 남은 아티팩트가 전부 그것이다(배포 전 embed 가 남겼다). 지우기 한 번이면 '요약이 돈 체인에서 embed 가 보는 아티팩트는 이번 요약이 쓴 것뿐'이 토큰과 상관없이 성립하고, 비용은 논문당 MinIO 삭제 1회다. 토큰은 삭제가 실패했을 때 남은 '토큰 붙은' 옛 아티팩트를 한 번 더 거른다. 남는 틈은 삭제 실패와 보강·저장 실패가 겹치고 남은 것이 배포 전 아티팩트인 경우뿐이다(MinIO 장애가 겹쳐야 한다).
  - **대가:** 토큰은 체인마다 새로 만들어진다. 그래서 같은 추출에서 나온 정상 아티팩트도 embed 부터 다시 도는 체인(`milvus_error` 재시도·stale 복구·락 경합 뒤 재디스패치)에서는 토큰이 달라 embed 가 보강을 다시 만든다. 드문 경로라 받아들인다.
- **결과물이 달라지는 곳(알고 넘어갈 것):** 요약 단계가 카탈로그의 빈 초록·키워드를 먼저 채우므로, 카탈로그에 초록·키워드가 없던 논문은 embed 의 메타 청크(`chunk_idx=-1`)에 보강 초록·키워드가 처음부터 들어간다(지금은 그 논문을 다시 embed 할 때만 들어간다).
- **Task 2 와의 경계:** `ctx.item_meta` 는 Task 2 가 `StageContext` 에 더한 필드다(`_run_stage` 가 `item.meta` 를 넘기고, 그 안에 `run_token` 이 있다). 이 작업은 그 필드를 읽기만 하고 `(ctx.item_meta or {}).get("run_token")` 으로 읽는다. `run_embed_index` 의 앞부분(추출 아티팩트 로드·초록 폴백·빈 본문 가드)은 Task 2 가 고친다 — 이 작업은 보강 블록만 바꾼다. `run_summarize` 도 '섹션 없음' 검사 아래('재시도 시 이미 요약된 섹션은 건너뛰기')부터만 바꾼다. Task 2·4 가 먼저 `stages.py` 를 고치므로 줄 번호가 아니라 old 블록의 글자로 찾는다.

**Files:**
- Modify: `app/services/ingestion/paper_enricher.py` (193be93 기준 docstring 4행, `_llm_chat` 470-477행, `interpret_table` 502-506행, 7절 567-607행, `enrich_paper` 621-650행)
- Modify: `app/domains/nl_library/prompts/paper_table_interp.yaml` (전체)
- Modify: `app/services/ingestion/stages.py` (193be93 기준 docstring 6-7행, import 20-27행, 383행 앞에 헬퍼 3개, `run_summarize` 414-445·470-473행, `run_embed_index` 보강 블록 582-654행)
- Modify: `app/tests/test_paper_enricher.py`, `app/tests/test_prompts.py`
- Create: `app/tests/test_stage_enrichment.py`
- 전제(고치지 않음): Task 2 가 더한 `StageContext.item_meta`(`_run_stage` 가 `item.meta` 를 넘긴다 — `run_token` 포함)

#### 6-1. paper_enricher — 세마포어 인자·아티팩트 로더(run_token)·삭제·표 해석 잘림 다듬기

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`app/tests/test_paper_enricher.py` 의 import 를 바꾼다. old:

```python
import pytest

from services.ingestion.paper_enricher import (
    extract_abstract,
    extract_references,
)
```

new:

```python
import asyncio
import gzip
import json
import logging

import pytest

from services.ingestion import paper_enricher
from services.ingestion.paper_enricher import (
    FigureChunk,
    PaperEnrichment,
    TableChunk,
    delete_enrichment_artifact,
    enrich_paper,
    extract_abstract,
    extract_references,
    interpret_table,
    load_enrichment_artifact,
    save_enrichment_artifact,
    trim_to_last_sentence,
)
```

같은 파일 맨 끝(`test_intext_citation_not_entry_start` 뒤)에 빈 줄 둘을 두고 덧붙인다. `TestEnrichPaperSemaphore` 는 LLM 함수 셋(`generate_keywords`·`generate_references`·`interpret_table`)을 동시 진입 수를 재는 대역으로 바꾼다 — `sem=asyncio.Semaphore(1)` 을 주고 `LLM_SECTION_CONCURRENCY=4` 로 두면, 표 해석이 세마포어를 따로 만들 경우 peak 가 4 가 되어 잡힌다. 아티팩트 테스트의 `_FakeMinio` 는 없는 키에 `code = "NoSuchKey"` 인 예외를 던지고(minio `S3Error` 와 같은 속성), `remove_object` 는 없는 키도 성공한다(S3 와 같다). 토큰 세 경우(같음 → 읽음, 다름 → None, 토큰 없는 호출 → 읽음)와 토큰 키가 없는 배포 전 페이로드(→ 읽음)를 따로 본다. `TestInterpretTable` 은 `chat_full` 만 대역으로 바꾸고 실제 `paper_table_interp.yaml` 을 렌더한다.

```python
# ── 표 해석 잘림 다듬기 ──────────────────────────────────────

class TestTrimToLastSentence:
    def test_cuts_unfinished_tail(self):
        text = "표 1은 집단별 평균을 보여 준다. 실험군이 대조군보다 높았다. 반면 남성 집단의 경우"
        assert trim_to_last_sentence(text) == "표 1은 집단별 평균을 보여 준다. 실험군이 대조군보다 높았다."

    def test_korean_endings_and_other_marks(self):
        assert trim_to_last_sentence("차이가 컸어요. 그런데 이") == "차이가 컸어요."
        assert trim_to_last_sentence("유의한가? 그렇다! 그러나 표본이") == "유의한가? 그렇다!"
        assert trim_to_last_sentence("增加了。 然后") == "增加了。"

    def test_decimal_point_is_not_a_sentence_end(self):
        assert trim_to_last_sentence("평균은 3.5점이다. 표준편차는 1.2") == "평균은 3.5점이다."

    def test_finished_text_is_kept(self):
        assert trim_to_last_sentence("두 집단의 차이는 유의했다.\n") == "두 집단의 차이는 유의했다."

    def test_no_finished_sentence_returns_original(self):
        text = "남성 45.2, 여성 52"
        assert trim_to_last_sentence(text) == text


class TestInterpretTable:
    TABLE = "| 집단 | 평균 |\n|---|---|\n| A | 1 |\n| B | 2 |"

    def _patch_chat_full(self, monkeypatch, content, finish_reason):
        from services import llm_client

        seen = {}

        async def fake_chat_full(messages, *, params=None, timeout=120.0):
            seen["messages"] = messages
            seen["params"] = params
            return llm_client.LLMResult(content=content, finish_reason=finish_reason)

        monkeypatch.setattr(llm_client, "chat_full", fake_chat_full)
        return seen

    def test_length_trims_to_last_finished_sentence(self, monkeypatch):
        seen = self._patch_chat_full(monkeypatch, "A 집단의 평균이 더 높다. B 집단은", "length")

        out = asyncio.run(interpret_table("논문", "표 앞 맥락", self.TABLE))

        assert out == "A 집단의 평균이 더 높다."
        assert seen["params"]["max_tokens"] == 600           # 상한은 올리지 않는다
        assert self.TABLE in seen["messages"][1]["content"]

    def test_stop_keeps_whole_text(self, monkeypatch):
        self._patch_chat_full(monkeypatch, "A 집단의 평균이 더 높다. B 집단은", "stop")

        out = asyncio.run(interpret_table("논문", "표 앞 맥락", self.TABLE))

        assert out == "A 집단의 평균이 더 높다. B 집단은"


# ── 단계 세마포어 ─────────────────────────────────────────────

class _Gauge:
    """동시에 몇 개가 LLM 을 부르고 있는지 잰다."""

    def __init__(self):
        self.active = 0
        self.peak = 0
        self.calls: list[str] = []

    async def hold(self, name: str):
        self.calls.append(name)
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1


def _paper_text(n_tables: int) -> str:
    """키워드 줄·참고문헌 헤더가 없어 둘 다 LLM 폴백을 타는 본문 + 표 n_tables 개."""
    parts = ["서론 문단이다. " * 30]
    for i in range(n_tables):
        parts.append(f"표 {i + 1} 앞 문단이다.\n| 집단 | 평균 |\n|---|---|\n| A | {i} |\n| B | {i + 1} |\n")
    return "\n\n".join(parts)


def _patch_enrich_llm(monkeypatch) -> _Gauge:
    gauge = _Gauge()

    async def fake_keywords(title, text):
        await gauge.hold("kw")
        return ["가", "나"]

    async def fake_references(text):
        await gauge.hold("ref")
        return ["r1", "r2", "r3"]

    async def fake_table(title, ctx, md):
        await gauge.hold("table")
        return "A 가 더 높다."

    monkeypatch.setattr(paper_enricher, "generate_keywords", fake_keywords)
    monkeypatch.setattr(paper_enricher, "generate_references", fake_references)
    monkeypatch.setattr(paper_enricher, "interpret_table", fake_table)
    monkeypatch.setattr(paper_enricher, "_list_figure_keys", lambda book_id, client: [])
    return gauge


class TestEnrichPaperSemaphore:
    def test_given_semaphore_caps_every_llm_call(self, monkeypatch):
        """sem 을 주면 표 해석도 그 세마포어만 쓴다 — 표용 세마포어를 따로 만들면 peak 가 4 가 된다."""
        gauge = _patch_enrich_llm(monkeypatch)
        monkeypatch.setattr(paper_enricher.cfg, "LLM_SECTION_CONCURRENCY", 4)

        async def run():
            return await enrich_paper("B1", "제목", _paper_text(5), None, sem=asyncio.Semaphore(1))

        result = asyncio.run(run())

        assert gauge.peak == 1
        assert gauge.calls.count("table") == 5 and "kw" in gauge.calls and "ref" in gauge.calls
        assert len(result.table_chunks) == 5
        assert all(tc.description == "A 가 더 높다." for tc in result.table_chunks)

    def test_without_semaphore_uses_section_concurrency(self, monkeypatch):
        gauge = _patch_enrich_llm(monkeypatch)
        monkeypatch.setattr(paper_enricher.cfg, "LLM_SECTION_CONCURRENCY", 2)

        asyncio.run(enrich_paper("B1", "제목", _paper_text(5), None))

        assert gauge.peak == 2

    def test_keyword_and_reference_fallbacks_wait_for_the_semaphore(self, monkeypatch):
        """섹션 요약이 자리를 모두 쥐고 있으면 키워드·참고문헌 LLM 폴백도 기다린다."""
        gauge = _patch_enrich_llm(monkeypatch)

        async def scenario():
            sem = asyncio.Semaphore(1)
            await sem.acquire()
            task = asyncio.create_task(enrich_paper("B1", "제목", _paper_text(0), None, sem=sem))
            for _ in range(5):
                await asyncio.sleep(0)
            started_while_held = list(gauge.calls)
            sem.release()
            await task
            return started_while_held

        assert asyncio.run(scenario()) == []
        assert gauge.calls == ["kw", "ref"]


# ── 보강 아티팩트 ─────────────────────────────────────────────

class _NoSuchKey(Exception):
    code = "NoSuchKey"     # minio S3Error 와 같은 속성


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        pass

    def release_conn(self):
        pass


class _FakeMinio:
    def __init__(self, fail_remove: bool = False):
        self.objects: dict[str, bytes] = {}
        self.fail_remove = fail_remove

    def put_object(self, bucket, key, data, length, content_type=None):
        self.objects[key] = data.read()

    def get_object(self, bucket, key):
        if key not in self.objects:
            raise _NoSuchKey(key)
        return _FakeResp(self.objects[key])

    def remove_object(self, bucket, key):
        if self.fail_remove:
            raise ConnectionError("minio down")
        self.objects.pop(key, None)        # S3 처럼 없는 키를 지워도 성공


class TestEnrichmentArtifact:
    def test_save_then_load_round_trips(self):
        client = _FakeMinio()
        enrichment = PaperEnrichment(
            abstract="초록 본문",
            keywords=["가", "나"],
            toc=["1. 서론", "2. 방법", "3. 결론"],
            references=["[1] 김. (2020).", "[2] 이. (2021)."],
            table_chunks=[TableChunk(context="맥락", table_md="| a | b |", description="설명."),
                          TableChunk(context="", table_md="| c | d |", description="")],
            figure_chunks=[FigureChunk(minio_key="figures/B1/p1_i0.jpg", description="그림 설명.")],
        )

        save_enrichment_artifact("B1", enrichment, client)

        assert list(client.objects) == ["artifacts/B1/enrichment.json.gz"]
        assert load_enrichment_artifact("B1", client) == enrichment

    def test_run_token_must_match_when_both_sides_have_one(self):
        client = _FakeMinio()
        enrichment = PaperEnrichment(abstract="이번 실행의 초록")
        save_enrichment_artifact("B1", enrichment, client, run_token="T1")

        assert load_enrichment_artifact("B1", client, run_token="T1") == enrichment
        assert load_enrichment_artifact("B1", client, run_token="T2") is None   # 다른 실행이 남긴 것
        assert load_enrichment_artifact("B1", client) == enrichment             # 토큰 없는 호출(단건 흐름)

    def test_pre_deploy_payload_without_token_is_still_used(self):
        """배포 전 embed 가 남긴 아티팩트(run_token 키 없음)는 토큰이 있는 호출에서도 쓴다."""
        client = _FakeMinio()
        old_payload = {"abstract": "옛 초록", "keywords": [], "toc": [], "references": [],
                       "table_chunks": [], "figure_chunks": []}
        client.objects["artifacts/B1/enrichment.json.gz"] = gzip.compress(
            json.dumps(old_payload, ensure_ascii=False).encode("utf-8"))

        assert load_enrichment_artifact("B1", client, run_token="T1") == PaperEnrichment(abstract="옛 초록")

    def test_delete_removes_artifact_and_never_raises(self, caplog):
        client = _FakeMinio()
        save_enrichment_artifact("B1", PaperEnrichment(abstract="초록"), client, run_token="T1")

        delete_enrichment_artifact("B1", client)
        delete_enrichment_artifact("B1", client)          # 없는 키도 조용히

        assert client.objects == {}
        with caplog.at_level(logging.WARNING, logger=paper_enricher.log.name):
            delete_enrichment_artifact("B1", _FakeMinio(fail_remove=True))
        assert [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_missing_artifact_returns_none_quietly(self, caplog):
        with caplog.at_level(logging.WARNING, logger=paper_enricher.log.name):
            assert load_enrichment_artifact("B1", _FakeMinio()) is None
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    @pytest.mark.parametrize("raw", [
        b"not gzip",
        gzip.compress(b"{not json"),
        gzip.compress(b"[1, 2]"),
    ], ids=["not-gzip", "not-json", "not-object"])
    def test_broken_artifact_returns_none_with_warning(self, caplog, raw):
        client = _FakeMinio()
        client.objects["artifacts/B1/enrichment.json.gz"] = raw

        with caplog.at_level(logging.WARNING, logger=paper_enricher.log.name):
            assert load_enrichment_artifact("B1", client) is None
        assert [r for r in caplog.records if r.levelno == logging.WARNING]
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_paper_enricher.py -q`
Expected: 수집 단계 `1 error` — `ImportError: cannot import name 'delete_enrichment_artifact' from 'services.ingestion.paper_enricher'`

- [ ] **Step 3: 구현한다**

`app/services/ingestion/paper_enricher.py` 를 일곱 군데 바꾼다.

① 모듈 docstring 첫 줄 — 호출 위치가 바뀐다. old:

```python
run_embed_index 에서 paper doc_type 시 호출:
```

new:

```python
run_summarize 가 paper doc_type 일 때 섹션 요약과 같은 루프·같은 세마포어로 호출하고,
결과 아티팩트를 run_embed_index 가 읽는다(아티팩트가 없을 때만 run_embed_index 가 직접 호출):
```

② `_llm_chat` — 메시지 조립을 `_messages()` 로 빼서 표 해석도 쓴다. old:

```python
async def _llm_chat(system: str, user: str, params: dict, timeout: float) -> str:
    # LLM 호출은 llm_client 어댑터로 통일 (OpenAI vLLM / Ollama 네이티브 겸용).
    from services.llm_client import chat
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await chat(messages, params=params, timeout=timeout)
```

new:

```python
def _messages(system: str, user: str) -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def _llm_chat(system: str, user: str, params: dict, timeout: float) -> str:
    # LLM 호출은 llm_client 어댑터로 통일 (OpenAI vLLM / Ollama 네이티브 겸용).
    from services.llm_client import chat
    return await chat(_messages(system, user), params=params, timeout=timeout)
```

③ `interpret_table` — `chat_full` 을 쓰고 length 면 다듬는다. `trim_to_last_sentence` 는 `. ! ? 。` 뒤에 공백이나 글 끝이 오는 자리를 문장 끝으로 본다('…다.'·'…요.' 포함, 소수점 `3.5` 는 뒤에 숫자가 와서 제외). 끝난 문장이 없으면 원문 그대로다. old:

```python
async def interpret_table(title: str, context: str, table_md: str) -> str:
    from services.prompts import get_prompt
    tpl = get_prompt("paper_table_interp")
    system, user, params = tpl.render(title=title, context=context, table_markdown=table_md)
    return await _llm_chat(system, user, params, timeout=cfg.PAPER_TABLE_INTERP_TIMEOUT)
```

new:

```python
# 문장 끝 — . ! ? 。 뒤에 공백이나 글 끝이 오는 자리('…다.'·'…요.' 포함). 소수점(3.5)은 제외된다.
_SENTENCE_END = re.compile(r'[.!?。](?=\s|$)')


def trim_to_last_sentence(text: str) -> str:
    """마지막으로 끝난 문장까지만 남긴다 — max_tokens 에서 잘린 응답의 끊긴 꼬리를 걷어 낸다.

    끝난 문장이 하나도 없으면 원문을 그대로 돌려준다.
    """
    ends = list(_SENTENCE_END.finditer(text))
    if not ends:
        return text
    return text[: ends[-1].end()].rstrip()


async def interpret_table(title: str, context: str, table_md: str) -> str:
    """표 해석 LLM — 상한(600토큰)에서 잘리면 마지막으로 끝난 문장까지만 쓴다."""
    from services.llm_client import chat_full
    from services.prompts import get_prompt
    tpl = get_prompt("paper_table_interp")
    system, user, params = tpl.render(title=title, context=context, table_markdown=table_md)
    result = await chat_full(_messages(system, user), params=params, timeout=cfg.PAPER_TABLE_INTERP_TIMEOUT)
    if result.finish_reason == "length":
        return trim_to_last_sentence(result.content)
    return result.content
```

④ 7절(아티팩트) 전체와 `enrich_paper` 머리 — 7절 머리부터 `enrich_paper` 의 `return PaperEnrichment()` 까지를 바꾼다. 바뀌는 것:
- 아티팩트 키를 `_enrichment_key()` 한 곳에 둔다.
- `save_enrichment_artifact` 가 키워드 인자 `run_token` 을 받아 페이로드 맨 앞에 `"run_token"` 으로 남긴다.
- `load_enrichment_artifact(book_id, minio_client, *, run_token=None)` 를 더한다. 없는 객체(`NoSuchKey`)면 조용히 `None`, 그 밖의 읽기 실패·깨진 내용이면 `None` 과 경고다 — 보강은 다시 만들 수 있으니 색인을 막지 않는다. 해석 실패는 실제로 나는 타입만 잡는다(함정 19 의 교훈 — 폴백이 제어 예외까지 삼키지 않게). 호출 쪽과 저장 쪽에 모두 토큰이 있는데 다르면 `None`(info 로그) — 토큰 없는 배포 전 페이로드와 토큰 없는 호출은 그대로 읽는다.
- `delete_enrichment_artifact(book_id, minio_client)` 를 더한다(best-effort — S3 는 없는 키 삭제도 성공, 실패는 경고만).
- `enrich_paper` 에 키워드 전용 인자 `sem` 을 더하고, 없으면 `LLM_SECTION_CONCURRENCY` 로 하나 만든다.

old:

```python
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
    if not full_text:
        return PaperEnrichment()
```

new:

```python
# ── 7. MinIO 아티팩트 저장·로드 ─────────────────────────────

def _enrichment_key(book_id: str) -> str:
    return f"artifacts/{book_id}/enrichment.json.gz"


def save_enrichment_artifact(
    book_id: str, enrichment: PaperEnrichment, minio_client, *, run_token: str | None = None,
) -> None:
    """보강 결과 → MinIO artifacts/{book_id}/enrichment.json.gz.

    run_token: 이 보강을 만든 체인의 실행 토큰(ingest_job_items.meta.run_token — Task 2).
    embed 단계가 같은 실행의 아티팩트인지 가린다. 단건 흐름은 None.
    """
    payload = {
        "run_token": run_token,
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
            _enrichment_key(book_id),
            io.BytesIO(data),
            length=len(data),
            content_type="application/gzip",
        )
    except Exception as e:
        log.warning(f"[{book_id}] enrichment 아티팩트 MinIO 저장 실패: {e}")


def load_enrichment_artifact(
    book_id: str, minio_client, *, run_token: str | None = None,
) -> PaperEnrichment | None:
    """save_enrichment_artifact 의 역 — 요약 단계가 남긴 보강 결과를 embed 단계가 읽는다.

    없으면 None(embed 가 보강을 직접 돌린다). 읽기·해석에 실패해도 None 과 경고 —
    보강은 다시 만들 수 있으니 색인을 막지 않는다.
    run_token 을 주면 저장된 토큰과 다를 때 None — 다른 실행이 남긴 옛 보강으로 본다.
    토큰 없이 저장된 배포 전 아티팩트와 토큰 없는 호출(단건 흐름)은 그대로 읽는다.
    """
    try:
        resp = minio_client.get_object(cfg.MINIO_BUCKET, _enrichment_key(book_id))
        try:
            raw = resp.read()
        finally:
            resp.close()
            resp.release_conn()
    except Exception as e:
        if getattr(e, "code", None) != "NoSuchKey":   # minio S3Error — 없는 객체는 조용히 None
            log.warning(f"[{book_id}] enrichment 아티팩트 읽기 실패 — 보강을 다시 만든다: {e}")
        return None
    try:
        data = json.loads(gzip.decompress(raw).decode("utf-8"))
        stored_token = data.get("run_token")
        if run_token is not None and stored_token is not None and stored_token != run_token:
            log.info(f"[{book_id}] enrichment 아티팩트가 다른 실행({stored_token})의 것 — 쓰지 않는다")
            return None
        return PaperEnrichment(
            abstract=data.get("abstract"),
            keywords=list(data.get("keywords") or []),
            toc=list(data.get("toc") or []),
            references=list(data.get("references") or []),
            table_chunks=[
                TableChunk(context=t["context"], table_md=t["table_md"], description=t.get("description") or "")
                for t in data.get("table_chunks") or []
            ],
            figure_chunks=[
                FigureChunk(minio_key=f["minio_key"], description=f["description"])
                for f in data.get("figure_chunks") or []
            ],
        )
    except (OSError, EOFError, ValueError, KeyError, TypeError, AttributeError) as e:
        log.warning(f"[{book_id}] enrichment 아티팩트가 깨졌다 — 보강을 다시 만든다: {e}")
        return None


def delete_enrichment_artifact(book_id: str, minio_client) -> None:
    """옛 보강 아티팩트를 지운다(best-effort) — 요약 단계가 보강을 새로 만들기 전에 부른다.

    없는 객체를 지우는 것은 S3 에서 성공이다. 실패해도 경고만 남긴다 — 남은 아티팩트가
    토큰이 붙은 것이면 embed 의 run_token 비교가 한 번 더 거른다.
    """
    try:
        minio_client.remove_object(cfg.MINIO_BUCKET, _enrichment_key(book_id))
    except Exception as e:
        log.warning(f"[{book_id}] 옛 enrichment 아티팩트 삭제 실패: {e}")


# ── 8. 메인 엔트리 ─────────────────────────────────────────

async def enrich_paper(
    book_id: str,
    title: str,
    full_text: str,
    minio_client,
    *,
    sem: asyncio.Semaphore | None = None,
) -> PaperEnrichment:
    """논문 보강 파이프라인 — 초록·참고문헌·표·그림 처리.

    sem: 키워드·참고문헌 LLM 폴백과 표 해석이 함께 쓰는 동시 호출 상한. 요약 단계가
    섹션 요약과 같은 세마포어를 넘긴다(단계 하나 = 프로세스 하나의 LLM 상한). 없으면
    LLM_SECTION_CONCURRENCY 로 새로 만든다. 그림 설명(VLM)은 다른 서버라 세마포어 밖이다.
    """
    if not full_text:
        return PaperEnrichment()
    if sem is None:
        sem = asyncio.Semaphore(cfg.LLM_SECTION_CONCURRENCY)
```

⑤ 키워드 LLM 폴백을 세마포어 안으로. old:

```python
        try:
            seed_text = abstract or full_text[:800]
            keywords = await generate_keywords(title, seed_text)
```

new:

```python
        try:
            seed_text = abstract or full_text[:800]
            async with sem:
                keywords = await generate_keywords(title, seed_text)
```

⑥ 참고문헌 LLM 폴백을 세마포어 안으로. old:

```python
        try:
            references = await generate_references(full_text)
```

new:

```python
        try:
            async with sem:
                references = await generate_references(full_text)
```

⑦ 표 해석용 세마포어를 따로 만들지 않는다(④에서 정한 `sem` 을 그대로 쓴다). old:

```python
    if tables:
        sem = asyncio.Semaphore(cfg.LLM_SECTION_CONCURRENCY)

        async def _build_table_chunk(ctx: str, md: str) -> TableChunk:
```

new:

```python
    if tables:
        async def _build_table_chunk(ctx: str, md: str) -> TableChunk:
```

- [ ] **Step 4: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_paper_enricher.py -q`
Expected: `43 passed` (기존 25 + 새 18)

- [ ] **Step 5: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/paper_enricher.py app/tests/test_paper_enricher.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Feat] round07 — 논문 보강: enrich_paper 가 단계 세마포어(sem)를 받아 키워드·참고문헌 LLM 폴백과 표 해석이 함께 쓴다(없으면 LLM_SECTION_CONCURRENCY 로 새로 만든다). 보강 아티팩트에 만든 체인의 run_token 을 남기고, 로더(load_enrichment_artifact)는 토큰이 다르면 다른 실행의 옛 보강으로 보고 None 을 돌려준다(토큰 없는 배포 전 아티팩트는 그대로 읽는다). 옛 아티팩트 삭제(delete_enrichment_artifact)를 더하고, 표 해석이 600토큰에서 잘리면(finish_reason=length) 마지막으로 끝난 문장까지만 남긴다"
```

#### 6-2. 표 해석 프롬프트

- [ ] **Step 6: 실패하는 테스트를 쓴다**

`app/tests/test_prompts.py` 의 import 에 `re` 를 더한다. old:

```python
import textwrap
from pathlib import Path
```

new:

```python
import re
import textwrap
from pathlib import Path
```

같은 파일 맨 끝(`test_nl_library_prompts_exist_and_render` 뒤)에 빈 줄 둘을 두고 덧붙인다:

```python
def test_paper_table_interp_asks_for_key_findings_not_every_row():
    """표 원본 마크다운 청크가 따로 색인되므로 표 해석은 핵심 비교·경향만 짧게 쓴다.

    상한(600)은 그대로 — 올려도 임베딩 창(512토큰)이 같은 자리를 자른다. 개수 예시
    ("3문장")는 모델이 베끼므로 쓰지 않는다(함정 15).
    """
    real_dir = Path(__file__).resolve().parents[1] / "domains" / "nl_library" / "prompts"
    system, user, params = PromptLibrary(real_dir).get("paper_table_interp").render(
        title="논문", context="표 앞 맥락", table_markdown="| 집단 | 평균 |\n|---|---|\n| A | 1 |")

    assert params["max_tokens"] == 600
    assert "핵심" in system and "경향" in system
    assert "빠짐없이" not in system + user
    assert not re.search(r"\d+\s*(?:문장|줄|개)", system + user)
    assert "| 집단 | 평균 |" in user
```

- [ ] **Step 7: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_prompts.py -q`
Expected: `1 failed, 6 passed` — `test_paper_table_interp_asks_for_key_findings_not_every_row` 가 `assert "핵심" in system and "경향" in system` 에서 실패한다(지금 프롬프트는 모든 행과 열을 빠짐없이 쓰라고 한다).

- [ ] **Step 8: 프롬프트를 바꾼다**

`app/domains/nl_library/prompts/paper_table_interp.yaml` 전체를 다음으로 바꾼다. `max_tokens: 600` 은 그대로다.

```yaml
parser: plain
params:
  max_tokens: 600
  temperature: 0.1
system: |-
  당신은 학술논문의 표(Table)를 해석하는 전문가입니다.
  표 원본은 따로 저장되므로 모든 행과 열을 옮겨 적지 마세요.
  표가 보여 주는 핵심 비교와 경향을 몇 문장의 자연어로 설명하세요.

  규칙:
  - 집단·조건 간 차이, 가장 크거나 작은 값, 증가·감소 같은 핵심만 짚으세요.
  - 근거로 드는 수치는 표에 적힌 그대로 쓰세요.
  - 행을 하나씩 나열하지 마세요.
  - 표에 없는 내용은 절대 추가하지 마세요.
  - 마지막 문장까지 끝맺으세요.
user: |-
  논문: {{ title }}
  위치: {{ context }}

  {{ table_markdown }}

  이 표가 보여 주는 핵심 비교와 경향을 설명하세요.
```

- [ ] **Step 9: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_prompts.py tests/test_paper_enricher.py -q`
Expected: `50 passed` (`TestInterpretTable` 이 새 프롬프트를 실제로 렌더한다)

- [ ] **Step 10: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/domains/nl_library/prompts/paper_table_interp.yaml app/tests/test_prompts.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Fix] round07 — 표 해석 프롬프트: 표 원본 마크다운 청크가 따로 색인되므로 모든 행·열을 옮기지 않고 표가 보여 주는 핵심 비교·경향을 몇 문장으로 쓰게 한다. 개수 예시는 두지 않고(함정 15) 상한 600 은 유지한다"
```

#### 6-3. stages — 보강을 요약 단계로, embed 는 이번 실행의 아티팩트로 청크만

- [ ] **Step 11: 실패하는 테스트를 쓴다**

대역: DB 세션은 `MagicMock`(`filter_by().first()` 가 book, `filter_by().order_by().all()` 이 섹션 행). `summarize_section`·`enrich_paper`·`delete_enrichment_artifact`·`save_enrichment_artifact` 는 `run_summarize`·`run_embed_index` 가 함수 안에서 import 하므로 모듈 속성(`summarizer.summarize_section`·`paper_enricher.enrich_paper` 등)을 바꾼다. 요약 테스트의 MinIO 는 문자열 `"MINIO"` 이고(보강 함수가 전부 대역), 삭제와 보강의 순서(`events`)와 저장 때 넘긴 `run_token` 을 기록한다. `test_section_summaries_and_enrichment_share_one_semaphore` 만 진짜 `enrich_paper` 를 쓰고 그 안의 LLM 함수를 동시 진입 수를 재는 대역으로 바꾼다 — 섹션 6개 + 표 4개를 `LLM_SECTION_CONCURRENCY=2` 로 돌려 peak 가 2 를 넘지 않는지 본다. embed 테스트는 MinIO 대역(`_FakeMinio`)에 진짜 `save_enrichment_artifact` 가 쓴 바이트(또는 토큰 키가 없는 배포 전 페이로드)를 넣고 진짜 `load_enrichment_artifact` 로 읽게 해서, 토큰 같음 → 아티팩트 사용 / 다름 → 인라인 보강 / 토큰 없는 옛 페이로드 → 사용 / 없음 → 인라인 보강을 본다. 미설치 `pymilvus`·`FlagEmbedding` 만 `test_embed_index_guard.py` 와 같은 방식으로 더미로 꽂는다(함정 13). `StageContext(..., item_meta={"run_token": ...})` 는 Task 2 가 더한 필드를 쓴다. `_persist_enrichment` 테스트는 DB 없이 만든 `Book` 객체(transient)를 써서 `flag_modified` 까지 실제로 거친다. `app/tests/test_stage_enrichment.py`:

```python
"""논문 보강을 요약 단계로 옮긴 흐름 — run_summarize·run_embed_index·헬퍼 단위 테스트.

요약 단계가 섹션 요약과 같은 루프·같은 세마포어로 enrich_paper 를 돌려 아티팩트와 DB 에
남기고, embed 단계는 그 아티팩트로 보강 청크만 만든다(없거나 다른 실행의 것이면 직접 보강).
아티팩트에는 만든 체인의 run_token 이 붙는다. DB·MinIO·LLM 은 전부 대역이다.
"""
import asyncio
import gzip
import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from models.book import Book
from services.ingestion import paper_enricher, stages, summarizer
from services.ingestion.paper_enricher import FigureChunk, PaperEnrichment, TableChunk
from services.ingestion.stages import StageContext, StageError

ARTIFACT_TEXT = "추출 본문 문장이다. " * 40
_REAL_ENRICH_PAPER = paper_enricher.enrich_paper   # 대역으로 바꾸기 전의 진짜 함수


def _enrichment() -> PaperEnrichment:
    return PaperEnrichment(
        abstract="초록 본문",
        keywords=["가", "나"],
        references=["r1", "r2", "r3"],
        table_chunks=[TableChunk(context="맥락", table_md="| a | b |", description="설명.")],
    )


def _session(book, section_rows=()):
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = book
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = list(section_rows)
    return session


# ── run_summarize ────────────────────────────────────────────


def _patch_summarize(monkeypatch, *, doc_type="paper", n_sections=3, artifact=ARTIFACT_TEXT, enrich=None):
    """요약 단계 대역 — 섹션 n 개(요약 없음), 추출 아티팩트, 보강 삭제·저장 기록."""
    rows = [SimpleNamespace(section_idx=i, full_text=f"섹션 {i} 본문", summary=None) for i in range(n_sections)]
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: _session(SimpleNamespace(title="논문 제목", doc_type=doc_type), rows))
    monkeypatch.setattr(stages, "minio_client", lambda: "MINIO")
    monkeypatch.setattr(stages.cfg, "PAPER_ENRICH_ENABLED", True)

    rec = SimpleNamespace(loaded=[], enrich_calls=[], saved=[], persisted=[], sections=[], events=[])

    def fake_load(book_id, client):
        rec.loaded.append(book_id)
        if artifact is None:
            raise StageError("artifact_missing", "아티팩트 없음")
        return artifact, {}

    async def fake_section(title, text, doc_type="book"):
        rec.sections.append(text)
        return "요약", ["테마"]

    async def fake_enrich(book_id, title, full_text, minio_client, *, sem=None):
        rec.events.append("enrich")
        rec.enrich_calls.append((book_id, title, full_text, minio_client, sem))
        if isinstance(enrich, Exception):
            raise enrich
        return enrich or _enrichment()

    def fake_save(book_id, e, client, *, run_token=None):
        rec.saved.append((book_id, e, client, run_token))

    monkeypatch.setattr(stages, "load_extraction_artifact", fake_load)
    monkeypatch.setattr(summarizer, "summarize_section", fake_section)
    monkeypatch.setattr(paper_enricher, "enrich_paper", fake_enrich)
    monkeypatch.setattr(paper_enricher, "delete_enrichment_artifact",
                        lambda book_id, client: rec.events.append("delete"))
    monkeypatch.setattr(paper_enricher, "save_enrichment_artifact", fake_save)
    monkeypatch.setattr(stages, "_persist_enrichment", lambda book_id, e: rec.persisted.append((book_id, e)))
    return rec


def test_summarize_paper_enriches_from_extraction_text_and_stores_result(monkeypatch):
    enrichment = _enrichment()
    rec = _patch_summarize(monkeypatch, enrich=enrichment)

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.events == ["delete", "enrich"]           # 옛 아티팩트를 먼저 지운다
    book_id, title, full_text, client, sem = rec.enrich_calls[0]
    assert (book_id, title, full_text, client) == ("KCI_1", "논문 제목", ARTIFACT_TEXT, "MINIO")
    assert isinstance(sem, asyncio.Semaphore)
    assert rec.saved == [("KCI_1", enrichment, "MINIO", "T1")]   # 이번 실행 토큰을 붙여 저장
    assert rec.persisted == [("KCI_1", enrichment)]
    assert result["sections_summarized"] == 3
    assert {k: result[k] for k in ("enriched", "has_abstract", "n_keywords", "n_references",
                                   "n_tables", "n_figures", "n_toc")} == {
        "enriched": True, "has_abstract": True, "n_keywords": 2, "n_references": 3,
        "n_tables": 1, "n_figures": 0, "n_toc": 0,
    }


def test_summarize_paper_without_extraction_artifact_leaves_enrichment_to_embed(monkeypatch):
    rec = _patch_summarize(monkeypatch, artifact=None)

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.loaded == ["KCI_1"]
    assert rec.events == ["delete"]                     # 옛 보강은 남기지 않는다
    assert rec.enrich_calls == [] and rec.saved == [] and rec.persisted == []
    assert "enriched" not in result
    assert result["sections_summarized"] == 3


def test_summarize_non_paper_does_not_touch_enrichment(monkeypatch):
    rec = _patch_summarize(monkeypatch, doc_type="book")

    result = stages.run_summarize(StageContext(book_id="WS_1", item_meta={"run_token": "T1"}))

    assert rec.loaded == [] and rec.events == []
    assert "enriched" not in result


def test_summarize_enrichment_failure_keeps_section_summaries(monkeypatch):
    """보강이 실패하면 옛 아티팩트는 이미 지워졌고 새로 쓰지 않는다 — embed 가 다시 만든다."""
    rec = _patch_summarize(monkeypatch, enrich=RuntimeError("표 파싱 폭주"))

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert result["sections_summarized"] == 3
    assert result["enriched"] is False and "표 파싱 폭주" in result["enrich_error"]
    assert rec.events == ["delete", "enrich"]
    assert rec.saved == [] and rec.persisted == []


def test_summarize_without_run_token_saves_none(monkeypatch):
    """단건 흐름(process_book_file)은 item_meta 가 비어 있다 — 토큰 없이 저장한다."""
    rec = _patch_summarize(monkeypatch)

    stages.run_summarize(StageContext(book_id="KCI_1"))

    assert [s[3] for s in rec.saved] == [None]


def test_summarize_still_retries_failed_sections_once(monkeypatch):
    rec = _patch_summarize(monkeypatch)
    failed_once: set[str] = set()

    async def flaky_section(title, text, doc_type="book"):
        rec.sections.append(text)
        if text == "섹션 1 본문" and text not in failed_once:
            failed_once.add(text)
            raise RuntimeError("일시 실패")
        return "요약", ["테마"]

    monkeypatch.setattr(summarizer, "summarize_section", flaky_section)

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert result["sections_summarized"] == 3 and result["sections_failed"] == 0
    assert rec.sections.count("섹션 1 본문") == 2


def test_section_summaries_and_enrichment_share_one_semaphore(monkeypatch):
    """섹션 요약과 표 해석이 같은 세마포어를 나눠 쓴다 — 동시 LLM 호출이 상한을 넘지 않는다."""
    rec = _patch_summarize(monkeypatch, n_sections=6)
    monkeypatch.setattr(stages.cfg, "LLM_SECTION_CONCURRENCY", 2)
    tables = "\n\n".join(
        f"표 {i} 앞 문단.\n| 집단 | 평균 |\n|---|---|\n| A | {i} |\n| B | {i + 1} |\n" for i in range(4)
    )
    monkeypatch.setattr(stages, "load_extraction_artifact",
                        lambda book_id, client: (ARTIFACT_TEXT + "\n\n" + tables, {}))
    gauge = SimpleNamespace(active=0, peak=0, kinds=[])

    async def hold(kind):
        gauge.kinds.append(kind)
        gauge.active += 1
        gauge.peak = max(gauge.peak, gauge.active)
        await asyncio.sleep(0.01)
        gauge.active -= 1

    async def fake_section(title, text, doc_type="book"):
        await hold("section")
        return "요약", ["테마"]

    async def fake_table(title, ctx, md):
        await hold("table")
        return "설명."

    async def fake_keywords(title, text):
        await hold("keywords")
        return ["가"]

    async def fake_references(text):
        await hold("references")
        return ["r1", "r2", "r3"]

    monkeypatch.setattr(summarizer, "summarize_section", fake_section)
    monkeypatch.setattr(paper_enricher, "enrich_paper", _REAL_ENRICH_PAPER)   # 진짜 보강 경로
    monkeypatch.setattr(paper_enricher, "interpret_table", fake_table)
    monkeypatch.setattr(paper_enricher, "generate_keywords", fake_keywords)
    monkeypatch.setattr(paper_enricher, "generate_references", fake_references)
    monkeypatch.setattr(paper_enricher, "_list_figure_keys", lambda book_id, client: [])

    result = stages.run_summarize(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert gauge.peak == 2
    assert gauge.kinds.count("section") == 6 and gauge.kinds.count("table") == 4
    assert result["n_tables"] == 4 and len(rec.saved) == 1


# ── _persist_enrichment ──────────────────────────────────────


def test_persist_enrichment_fills_only_empty_catalog_fields(monkeypatch):
    book = Book(cnts_id="KCI_1", abstract=None, keyword="기존 키워드", extra={"plot": "유지"})
    session = _session(book)
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)
    enrichment = PaperEnrichment(abstract="보강 초록", keywords=["가", "나"],
                                 toc=["1. 서론", "2. 방법", "3. 결론"], references=["r1"])

    stages._persist_enrichment("KCI_1", enrichment)

    assert book.abstract == "보강 초록"
    assert book.keyword == "기존 키워드"            # 이미 있으면 덮지 않는다
    assert book.extra == {"plot": "유지", "references": ["r1"],
                          "toc": ["1. 서론", "2. 방법", "3. 결론"], "keywords": ["가", "나"]}
    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_persist_enrichment_skips_db_when_nothing_to_store(monkeypatch):
    opened = []
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: opened.append(True) or MagicMock())

    stages._persist_enrichment("KCI_1", PaperEnrichment())

    assert opened == []


# ── _build_enriched_chunks ───────────────────────────────────


def test_build_enriched_chunks_keeps_order_text_and_indices():
    enrichment = PaperEnrichment(
        abstract="초록 본문",
        keywords=["가", "나"],
        table_chunks=[TableChunk(context="맥락", table_md="| a | b |", description="설명."),
                      TableChunk(context="", table_md="| c | d |", description="")],
        figure_chunks=[FigureChunk(minio_key="figures/X/p1_i0.jpg", description="그림.")],
    )

    chunks = stages._build_enriched_chunks(enrichment, base_idx=5)

    assert [(c.chunk_idx, c.text) for c in chunks] == [
        (5, "[초록] 초록 본문"),
        (6, "[키워드] 가, 나"),
        (7, "[표]\n맥락\n\n| a | b |"),
        (8, "[표 설명] 설명."),
        (9, "[표]\n| c | d |"),
        (10, "[그림 설명] 그림."),
    ]
    assert all(c.section_idx is None for c in chunks)


def test_build_enriched_chunks_caps_table_bytes(monkeypatch):
    monkeypatch.setattr(stages.cfg, "MAX_CHUNK_BYTES", 20)
    enrichment = PaperEnrichment(table_chunks=[TableChunk(context="", table_md="| 가나다라마바사 |")])

    (chunk,) = stages._build_enriched_chunks(enrichment, base_idx=0)

    assert len(chunk.text.encode("utf-8")) <= 20


# ── run_embed_index 의 보강 블록 ──────────────────────────────

ENRICH_KEY = "artifacts/KCI_1/enrichment.json.gz"


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        pass

    def release_conn(self):
        pass


class _NoSuchKey(Exception):
    code = "NoSuchKey"     # minio S3Error 와 같은 속성


class _FakeMinio:
    """보강 아티팩트만 담는 MinIO 대역 — 진짜 save/load_enrichment_artifact 가 이걸 쓴다."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, bucket, key, data, length, content_type=None):
        self.objects[key] = data.read()

    def get_object(self, bucket, key):
        if key not in self.objects:
            raise _NoSuchKey(key)
        return _FakeResp(self.objects[key])


def _stored(enrichment: PaperEnrichment, run_token: str | None) -> bytes:
    """진짜 save_enrichment_artifact 가 쓰는 바이트 그대로."""
    client = _FakeMinio()
    paper_enricher.save_enrichment_artifact("KCI_1", enrichment, client, run_token=run_token)
    return client.objects[ENRICH_KEY]


def _stub_missing_module(monkeypatch, name: str, cache_clear: tuple[str, ...] = ()) -> None:
    """설치 안 된 모듈만 더미로 꽂는다(test_embed_index_guard.py 와 같은 기법)."""
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        monkeypatch.setitem(sys.modules, name, MagicMock())
        for mod in cache_clear:
            monkeypatch.delitem(sys.modules, mod, raising=False)


def _patch_embed(monkeypatch, *, stored: bytes | None):
    """embed 단계 대역 — 추출 본문 있음, 논문, MinIO 에 보강 아티팩트 stored(없으면 None)."""
    _stub_missing_module(monkeypatch, "pymilvus", cache_clear=("services.ingestion.indexer",))
    _stub_missing_module(monkeypatch, "FlagEmbedding", cache_clear=("services.ingestion.embedder",))
    import services.ingestion.chunker as chunker_mod
    import services.ingestion.embedder as embedder_mod
    import services.ingestion.indexer as indexer_mod

    book = MagicMock(doc_type="paper", abstract="카탈로그 초록", title="논문 제목",
                     personal_author=None, corporate_author=None, series_title=None,
                     subject=None, keyword=None)
    minio = _FakeMinio()
    if stored is not None:
        minio.objects[ENRICH_KEY] = stored
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: _session(book))
    monkeypatch.setattr(stages, "minio_client", lambda: minio)
    monkeypatch.setattr(stages, "load_extraction_artifact", lambda book_id, client: (ARTIFACT_TEXT, {}))
    monkeypatch.setattr(stages.cfg, "PAPER_ENRICH_ENABLED", True)
    monkeypatch.setattr(chunker_mod, "semantic_chunk",
                        lambda text, embed_fn, **kw: [chunker_mod.Chunk(chunk_idx=0, text=text, section_idx=None)])
    monkeypatch.setattr(embedder_mod, "embed_texts",
                        lambda texts, *a, **kw: ([[0.0] for _ in texts], [{} for _ in texts]))

    rec = SimpleNamespace(indexed=None, enrich_calls=[], persisted=[], minio=minio)

    def fake_index(book_id, chunks, dense, sparse, scalar_meta=None):
        rec.indexed = chunks
        return MagicMock(errors=[], chunks_indexed=len(chunks))

    async def fake_enrich(book_id, title, full_text, minio_client, *, sem=None):
        rec.enrich_calls.append(full_text)
        return PaperEnrichment(abstract="인라인 초록")

    monkeypatch.setattr(indexer_mod, "index_chunks", fake_index)
    monkeypatch.setattr(paper_enricher, "enrich_paper", fake_enrich)
    monkeypatch.setattr(stages, "_persist_enrichment", lambda book_id, e: rec.persisted.append(e))
    return rec


def test_embed_uses_artifact_written_by_this_run(monkeypatch):
    rec = _patch_embed(monkeypatch, stored=_stored(_enrichment(), run_token="T1"))

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.enrich_calls == [] and rec.persisted == []
    texts = [c.text for c in rec.indexed]
    assert "[초록] 초록 본문" in texts and "[표 설명] 설명." in texts
    assert result["enriched"] is True and result["n_tables"] == 1


def test_embed_rebuilds_inline_when_artifact_is_from_another_run(monkeypatch):
    rec = _patch_embed(monkeypatch, stored=_stored(_enrichment(), run_token="T0"))

    stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.enrich_calls == [ARTIFACT_TEXT] and len(rec.persisted) == 1
    texts = [c.text for c in rec.indexed]
    assert "[초록] 인라인 초록" in texts and "[초록] 초록 본문" not in texts
    # 새로 만든 보강을 이번 실행 토큰으로 덮어 저장했다
    assert paper_enricher.load_enrichment_artifact("KCI_1", rec.minio, run_token="T1") == \
        PaperEnrichment(abstract="인라인 초록")


def test_embed_uses_pre_deploy_artifact_without_token(monkeypatch):
    """배포 전 embed 가 남긴 아티팩트(run_token 키 없음)는 그대로 쓴다 — 배포 전 체크포인트 호환."""
    old = {"abstract": "배포 전 초록", "keywords": [], "toc": [], "references": [],
           "table_chunks": [], "figure_chunks": []}
    rec = _patch_embed(monkeypatch, stored=gzip.compress(json.dumps(old, ensure_ascii=False).encode("utf-8")))

    stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.enrich_calls == []
    assert "[초록] 배포 전 초록" in [c.text for c in rec.indexed]


def test_embed_enriches_inline_when_artifact_is_missing(monkeypatch):
    rec = _patch_embed(monkeypatch, stored=None)

    result = stages.run_embed_index(StageContext(book_id="KCI_1", item_meta={"run_token": "T1"}))

    assert rec.enrich_calls == [ARTIFACT_TEXT] and len(rec.persisted) == 1
    assert "[초록] 인라인 초록" in [c.text for c in rec.indexed]
    assert result["enriched"] is True and result["has_abstract"] is True
```

- [ ] **Step 12: 실패를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_stage_enrichment.py -q`
Expected: `15 failed` — `AttributeError: ... has no attribute '_persist_enrichment'` 13건, `AttributeError: module 'services.ingestion.stages' has no attribute '_build_enriched_chunks'` 2건. (`TypeError: StageContext.__init__() got an unexpected keyword argument 'item_meta'` 가 보이면 Task 2 가 아직 안 된 것이다.)

- [ ] **Step 13: 구현한다**

`app/services/ingestion/stages.py` 를 여섯 군데 바꾼다.

① 모듈 docstring. old:

```python
  run_summarize   : 섹션 요약/테마 LLM → book_sections UPDATE (doc_type 판별·영속화 포함)
  run_embed_index : 아티팩트 + 섹션 요약 로드 → 청킹 → 임베딩 → Milvus delete+insert
```

new:

```python
  run_summarize   : 섹션 요약/테마 LLM → book_sections UPDATE (doc_type 판별·영속화 포함)
                    + [paper] 보강 LLM(섹션 요약과 같은 세마포어) → enrichment.json.gz·카탈로그
  run_embed_index : 아티팩트 + 섹션 요약 로드 → 청킹 → 임베딩 → Milvus delete+insert
                    ([paper] 보강 아티팩트로 보강 청크 — 없거나 다른 실행의 것이면 여기서 보강 LLM)
```

② import — 헬퍼의 타입 표기용. 실행 시 import 는 지금처럼 함수 안에서 한다(함정 13 관례). old:

```python
from dataclasses import dataclass, field

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book
from models.section import BookSection

log = logging.getLogger(__name__)
```

new:

```python
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.config import get_settings
from db.postgres import SyncSessionLocal
from models.book import Book
from models.section import BookSection

if TYPE_CHECKING:   # 실행 시에는 함수 안에서 import 한다 (기존 관례)
    from services.ingestion.chunker import Chunk
    from services.ingestion.paper_enricher import PaperEnrichment

log = logging.getLogger(__name__)
```

③ `# ── 단계 ② 섹션 요약` 머리 바로 앞에 보강 헬퍼 셋을 둔다 — `_enrichment_coverage`(meta 커버리지), `_persist_enrichment`(지금 `run_embed_index` 안의 초록·키워드·extra 갱신 코드를 그대로 옮김), `_build_enriched_chunks`(지금 `run_embed_index` 안의 보강 청크 조립 코드를 그대로 옮김 — 텍스트 모양·순서·`MAX_CHUNK_BYTES` 절단 동일). old:

```python
# ── 단계 ② 섹션 요약 ─────────────────────────────────────────
```

new:

```python
# ── [paper] 보강 — 요약 단계가 만들고 embed 단계가 청크로 쓴다 ──────


def _enrichment_coverage(enrichment: "PaperEnrichment") -> dict:
    """보강 커버리지 — item.meta 로 노출 (전부 0이면 PDF 추출 품질 의심)."""
    return {
        "enriched": True,
        "has_abstract": bool(enrichment.abstract),
        "n_keywords": len(enrichment.keywords),
        "n_references": len(enrichment.references),
        "n_tables": len(enrichment.table_chunks),
        "n_figures": len(enrichment.figure_chunks),
        "n_toc": len(enrichment.toc),
    }


def _persist_enrichment(book_id: str, enrichment: "PaperEnrichment") -> None:
    """보강 결과를 카탈로그에 반영 — 초록·키워드는 비어 있을 때만 채우고 extra 에 참고문헌·목차·키워드.

    LLM 을 다 기다린 뒤에 세션을 연다(함정 18). 실패해도 경고만 — 보강이 색인을 막지 않는다.
    """
    if not (enrichment.abstract or enrichment.references or enrichment.keywords or enrichment.toc):
        return
    from sqlalchemy.orm.attributes import flag_modified

    db = SyncSessionLocal()
    try:
        book_row = db.query(Book).filter_by(cnts_id=book_id).first()
        if book_row:
            if enrichment.abstract and not book_row.abstract:
                book_row.abstract = enrichment.abstract
            if enrichment.keywords and not book_row.keyword:
                book_row.keyword = ", ".join(enrichment.keywords)
            extra = dict(book_row.extra or {})
            extra["references"] = enrichment.references
            if enrichment.toc:
                extra["toc"] = enrichment.toc
            if enrichment.keywords:
                extra["keywords"] = enrichment.keywords
            book_row.extra = extra
            flag_modified(book_row, "extra")
            db.commit()
    except Exception as e:
        log.warning(f"[{book_id}] enrichment DB 저장 실패: {e}")
        db.rollback()
    finally:
        db.close()


def _build_enriched_chunks(enrichment: "PaperEnrichment", base_idx: int) -> "list[Chunk]":
    """보강 결과 → 색인 청크(초록·키워드·표 원본·표 설명·그림 설명). chunk_idx 는 base_idx 부터 잇는다.

    표 원본은 수치 질문용, 표 설명은 해석·의미 검색용이다(설명이 비면 생략).
    """
    from services.ingestion.chunker import Chunk

    texts: list[str] = []
    if enrichment.abstract:
        texts.append(f"[초록] {enrichment.abstract}")
    if enrichment.keywords:
        texts.append(f"[키워드] {', '.join(enrichment.keywords)}")
    for tc in enrichment.table_chunks:
        table_text = f"[표]\n{tc.context}\n\n{tc.table_md}" if tc.context else f"[표]\n{tc.table_md}"
        texts.append(table_text.encode("utf-8")[: cfg.MAX_CHUNK_BYTES].decode("utf-8", errors="ignore"))
        if tc.description:
            texts.append(f"[표 설명] {tc.description}")
    for fc in enrichment.figure_chunks:
        texts.append(f"[그림 설명] {fc.description}")
    return [Chunk(chunk_idx=base_idx + i, text=t, section_idx=None) for i, t in enumerate(texts)]


# ── 단계 ② 섹션 요약 ─────────────────────────────────────────
```

④ `run_summarize` — 논문이면 먼저 옛 보강 아티팩트를 지우고(`delete_enrichment_artifact`, 추출 아티팩트가 없어 보강을 건너뛰는 경우에도), 추출 아티팩트에서 본문을 읽는다(없으면 경고 로그만 남기고 보강은 embed 에 맡긴다, 공백뿐이면 건너뛴다). 그다음 섹션 요약과 `enrich_paper` 를 `asyncio.gather` 로 함께 돌린다. 둘 다 `_run_llm()` 이 루프 안에서 만든 세마포어 하나를 쓴다. 보강 예외는 `_enrich()` 가 잡아 섹션 요약을 막지 않는다. 섹션 요약 실패분 한 번 재시도는 그대로다(같은 세마포어로). `run_token` 은 `(ctx.item_meta or {}).get("run_token")` 으로 읽는다. old:

```python
    # 재시도 시 이미 요약된 섹션은 건너뛰기 (기본 동작 — 전체 재생성은 resume_summaries=false)
    resume = ctx.params.get("resume_summaries", True)
    targets = [s for s in section_data if not (resume and s["summary"])]

    async def _summarize_batch(items: list[dict]) -> list[tuple[str, list[str]] | None]:
        sem = asyncio.Semaphore(cfg.LLM_SECTION_CONCURRENCY)

        async def _one(text: str):
            async with sem:
                try:
                    return await summarize_section(title, text, doc_type)
                except Exception as e:
                    log.warning(f"[{book_id}] 섹션 요약 실패: {e}")
                    return None

        return await asyncio.gather(*[_one(s["text"]) for s in items])

    async def _summarize_with_retry() -> list[tuple[str, list[str]] | None]:
        results = await _summarize_batch(targets)
        # 일부만 실패해도 stage 전체는 성공 처리되어 그 섹션 summary가 영구 NULL로
        # 남는 문제 방지 — 실패분만 한 번 더 재시도 (타임아웃/부하로 인한 일시적
        # 실패가 대부분이라 재시도로 대부분 복구됨).
        failed_idx = [i for i, r in enumerate(results) if r is None]
        if failed_idx:
            log.warning(f"[{book_id}] 섹션 요약 실패 {len(failed_idx)}건 재시도")
            retry_results = await _summarize_batch([targets[i] for i in failed_idx])
            for i, r in zip(failed_idx, retry_results):
                results[i] = r
        return results

    results = run_async(_summarize_with_retry()) if targets else []
    ok = sum(1 for r in results if r)
```

new:

```python
    # 재시도 시 이미 요약된 섹션은 건너뛰기 (기본 동작 — 전체 재생성은 resume_summaries=false)
    resume = ctx.params.get("resume_summaries", True)
    targets = [s for s in section_data if not (resume and s["summary"])]

    # [paper] 보강(키워드·참고문헌 폴백·표 해석·그림 설명)을 섹션 요약과 같은 루프에서 돌린다 —
    # embed 단계(celery-embed 1칸)가 LLM 을 기다리지 않게 결과를 아티팩트로 넘긴다.
    # 아티팩트에는 이 체인의 run_token 을 붙이고, 시작 전에 옛 아티팩트를 지운다 — 재처리
    # 문서에는 이전 실행이 남긴 보강이 있고(마무리는 지우지 않는다) 배포 전 것은 토큰이 없어,
    # 이번 보강이 실패하면 embed 가 그것을 읽게 되기 때문이다.
    run_token = (ctx.item_meta or {}).get("run_token")
    client = None
    enrich_text: str | None = None
    if doc_type == "paper" and cfg.PAPER_ENRICH_ENABLED:
        from services.ingestion.paper_enricher import delete_enrichment_artifact

        client = minio_client()
        delete_enrichment_artifact(book_id, client)
        try:
            enrich_text, _ = load_extraction_artifact(book_id, client)
        except StageError as e:
            if e.error_group != "artifact_missing":
                raise
            log.warning(f"[{book_id}] 추출 아티팩트 없음 — 보강은 embed 단계가 맡는다")
        if enrich_text is not None and not enrich_text.strip():
            enrich_text = None

    async def _summarize_batch(items: list[dict], sem: asyncio.Semaphore) -> list[tuple[str, list[str]] | None]:
        async def _one(text: str):
            async with sem:
                try:
                    return await summarize_section(title, text, doc_type)
                except Exception as e:
                    log.warning(f"[{book_id}] 섹션 요약 실패: {e}")
                    return None

        return await asyncio.gather(*[_one(s["text"]) for s in items])

    async def _summarize_with_retry(sem: asyncio.Semaphore) -> list[tuple[str, list[str]] | None]:
        results = await _summarize_batch(targets, sem)
        # 일부만 실패해도 stage 전체는 성공 처리되어 그 섹션 summary가 영구 NULL로
        # 남는 문제 방지 — 실패분만 한 번 더 재시도 (타임아웃/부하로 인한 일시적
        # 실패가 대부분이라 재시도로 대부분 복구됨).
        failed_idx = [i for i, r in enumerate(results) if r is None]
        if failed_idx:
            log.warning(f"[{book_id}] 섹션 요약 실패 {len(failed_idx)}건 재시도")
            retry_results = await _summarize_batch([targets[i] for i in failed_idx], sem)
            for i, r in zip(failed_idx, retry_results):
                results[i] = r
        return results

    async def _enrich(sem: asyncio.Semaphore):
        from services.ingestion.paper_enricher import enrich_paper

        try:
            return await enrich_paper(book_id, title, enrich_text, client, sem=sem), None
        except Exception as e:
            log.warning(f"[{book_id}] paper enrichment 실패 — 섹션 요약은 계속: {e}")
            return None, e

    async def _run_llm():
        # 섹션 요약과 보강의 LLM 호출이 세마포어 하나를 나눠 쓴다 — celery-llm 은 프로세스당
        # 태스크 1개라 이것이 프로세스의 동시 LLM 상한이다. run_async 가 단계마다 새 루프를
        # 만들므로 세마포어도 이 루프 안에서 만든다(모듈 전역 금지).
        sem = asyncio.Semaphore(cfg.LLM_SECTION_CONCURRENCY)
        if enrich_text is None:
            return await _summarize_with_retry(sem), (None, None)
        summaries, enriched = await asyncio.gather(_summarize_with_retry(sem), _enrich(sem))
        return summaries, enriched

    if targets or enrich_text is not None:
        results, (enrichment, enrich_error) = run_async(_run_llm())
    else:
        results, enrichment, enrich_error = [], None, None
    ok = sum(1 for r in results if r)
```

⑤ `run_summarize` 끝 — 섹션 요약을 저장한 뒤(기존 코드 그대로) 보강을 이번 실행 토큰을 붙여 아티팩트로 남기고(`run_token=run_token`) 카탈로그에 반영하고, 커버리지를 반환 meta 에 싣는다. 보강이 실패했으면 `enriched: false`·`enrich_error` 를 싣는다 — 옛 아티팩트는 ④에서 이미 지웠으니 embed 가 아티팩트 없음을 보고 다시 만든다. 섹션 요약이 전부 실패해 `llm_error` 로 끝나는 경우는 이 앞에서 올라가므로 보강도 저장하지 않는다 — 재시도 때 다시 만든다. old:

```python
    failed_section_idxs = [sec["section_idx"] for sec, r in zip(targets, results) if not r]
    return {"sections_total": len(section_data), "sections_summarized": ok,
            "sections_failed": len(targets) - ok,
            "failed_section_idxs": failed_section_idxs}
```

new:

```python
    # 보강 결과 저장 — 아티팩트(embed 단계가 읽는다) + 카탈로그(초록·키워드·extra)
    enrich_meta: dict = {}
    if enrichment is not None:
        from services.ingestion.paper_enricher import save_enrichment_artifact

        save_enrichment_artifact(book_id, enrichment, client, run_token=run_token)
        _persist_enrichment(book_id, enrichment)
        enrich_meta = _enrichment_coverage(enrichment)
    elif enrich_error is not None:
        enrich_meta = {"enriched": False, "enrich_error": str(enrich_error)[:500]}

    failed_section_idxs = [sec["section_idx"] for sec, r in zip(targets, results) if not r]
    return {"sections_total": len(section_data), "sections_summarized": ok,
            "sections_failed": len(targets) - ok,
            "failed_section_idxs": failed_section_idxs, **enrich_meta}
```

⑥ `run_embed_index` 의 보강 블록 — 이번 실행 토큰으로 아티팩트를 읽고(`load_enrichment_artifact(..., run_token=)`), `None` 이면(없음·다른 실행의 것·깨짐) 예전처럼 `enrich_paper` 를 돌려 이번 토큰으로 저장하고 카탈로그에 반영한다(드문 경로). 청크 조립은 ③의 헬퍼로. 블록 앞(아티팩트 로드·초록 폴백·빈 본문 가드 — Task 2 영역)과 뒤의 `except` 절·메타 청크·임베딩은 건드리지 않는다. old:

```python
    # ── [paper] 보강 청크 ────────────────────────────────────
    enriched_chunks: list[ChunkType] = []
    enrich_meta: dict = {}   # enrichment 커버리지 — 검증/모니터링용 (item.meta 로 노출)
    if doc_type == "paper" and cfg.PAPER_ENRICH_ENABLED:
        try:
            from services.ingestion.paper_enricher import enrich_paper, save_enrichment_artifact
            from sqlalchemy.orm.attributes import flag_modified as _flag_modified

            enrichment = run_async(enrich_paper(book_id, title, full_text, client))
            save_enrichment_artifact(book_id, enrichment, client)

            # 추출이 조용히 실패해도 보이도록 커버리지 기록 (전부 0이면 PDF 추출 품질 의심)
            enrich_meta = {
                "enriched": True,
                "has_abstract": bool(enrichment.abstract),
                "n_keywords": len(enrichment.keywords),
                "n_references": len(enrichment.references),
                "n_tables": len(enrichment.table_chunks),
                "n_figures": len(enrichment.figure_chunks),
                "n_toc": len(enrichment.toc),
            }

            if enrichment.abstract or enrichment.references or enrichment.keywords or enrichment.toc:
                db2 = SyncSessionLocal()
                try:
                    book_row = db2.query(Book).filter_by(cnts_id=book_id).first()
                    if book_row:
                        if enrichment.abstract and not book_row.abstract:
                            book_row.abstract = enrichment.abstract
                        if enrichment.keywords and not book_row.keyword:
                            book_row.keyword = ", ".join(enrichment.keywords)
                        extra = dict(book_row.extra or {})
                        extra["references"] = enrichment.references
                        if enrichment.toc:
                            extra["toc"] = enrichment.toc
                        if enrichment.keywords:
                            extra["keywords"] = enrichment.keywords
                        book_row.extra = extra
                        _flag_modified(book_row, "extra")
                        db2.commit()
                except Exception as _e:
                    log.warning(f"[{book_id}] enrichment DB 저장 실패: {_e}")
                    db2.rollback()
                finally:
                    db2.close()

            base_idx = len(chunks)
            if enrichment.abstract:
                enriched_chunks.append(ChunkType(
                    chunk_idx=base_idx, text=f"[초록] {enrichment.abstract}", section_idx=None,
                ))
                base_idx += 1
            if enrichment.keywords:
                kw_text = f"[키워드] {', '.join(enrichment.keywords)}"
                enriched_chunks.append(ChunkType(chunk_idx=base_idx, text=kw_text, section_idx=None))
                base_idx += 1
            for tc in enrichment.table_chunks:
                # ① 원본 마크다운 청크 — 수치 질문용
                table_text = f"[표]\n{tc.context}\n\n{tc.table_md}" if tc.context else f"[표]\n{tc.table_md}"
                table_text = table_text.encode("utf-8")[: cfg.MAX_CHUNK_BYTES].decode("utf-8", errors="ignore")
                enriched_chunks.append(ChunkType(chunk_idx=base_idx, text=table_text, section_idx=None))
                base_idx += 1
                # ② LLM 서술 청크 — 해석·의미 검색용 (실패 시 생략)
                if tc.description:
                    enriched_chunks.append(ChunkType(
                        chunk_idx=base_idx, text=f"[표 설명] {tc.description}", section_idx=None,
                    ))
                    base_idx += 1
            for i, fc in enumerate(enrichment.figure_chunks):
                enriched_chunks.append(ChunkType(
                    chunk_idx=base_idx + i, text=f"[그림 설명] {fc.description}", section_idx=None,
                ))
        except Exception as _e:
```

new:

```python
    # ── [paper] 보강 청크 ────────────────────────────────────
    # 보강 LLM 은 요약 단계가 돌려 아티팩트로 남겼다 — 여기서는 청크만 만든다. 아티팩트가
    # 없거나 다른 실행(run_token)의 것이면(요약 단계가 보강을 못 한 아이템, 배포 전
    # 체크포인트, embed 부터 다시 도는 체인) 예전처럼 여기서 돌린다.
    enriched_chunks: list[ChunkType] = []
    enrich_meta: dict = {}   # enrichment 커버리지 — 검증/모니터링용 (item.meta 로 노출)
    if doc_type == "paper" and cfg.PAPER_ENRICH_ENABLED:
        try:
            from services.ingestion.paper_enricher import (
                enrich_paper,
                load_enrichment_artifact,
                save_enrichment_artifact,
            )

            run_token = (ctx.item_meta or {}).get("run_token")
            enrichment = load_enrichment_artifact(book_id, client, run_token=run_token)
            if enrichment is None:
                log.info(f"[{book_id}] 이번 실행의 보강 아티팩트 없음 — embed 단계에서 보강을 돌린다")
                enrichment = run_async(enrich_paper(book_id, title, full_text, client))
                save_enrichment_artifact(book_id, enrichment, client, run_token=run_token)
                _persist_enrichment(book_id, enrichment)

            # 추출이 조용히 실패해도 보이도록 커버리지 기록 (전부 0이면 PDF 추출 품질 의심)
            enrich_meta = _enrichment_coverage(enrichment)
            enriched_chunks = _build_enriched_chunks(enrichment, base_idx=len(chunks))
        except Exception as _e:
```

- [ ] **Step 14: 통과를 확인한다**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_stage_enrichment.py -q`
Expected: `15 passed`

보강·요약·embed 가드·프롬프트·LLM 클라이언트의 기존 테스트:

Run: `python -m pytest tests/test_embed_index_guard.py tests/test_paper_enricher.py tests/test_prompts.py tests/test_summarizer.py tests/test_llm_client.py -q`
Expected: 실패 0

전체:

Run: `python -m pytest -q --continue-on-collection-errors`
Expected: 실패 0 (수집 오류 3건은 Task 1 Step 4 와 같은 환경 문제)

- [ ] **Step 15: 커밋한다**

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add app/services/ingestion/stages.py app/tests/test_stage_enrichment.py
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Feat] round07 — 논문 보강을 요약 단계로: run_summarize 가 옛 보강 아티팩트를 지운 뒤 섹션 요약과 같은 루프에서 세마포어 하나를 나눠 쓰며 enrich_paper 를 함께 돌리고(asyncio.gather), 결과를 이번 실행 토큰을 붙인 보강 아티팩트와 카탈로그(_persist_enrichment)에 남기고 커버리지를 meta 에 싣는다. run_embed_index 는 이번 실행의 아티팩트로 보강 청크(_build_enriched_chunks)만 만들고, 아티팩트가 없거나 다른 실행의 것일 때만 예전처럼 직접 보강한다 — embed 칸이 LLM 을 기다리지 않고, 재처리 문서가 이전 실행의 옛 보강을 색인하지 않는다"
```

---

### Task 7: 청킹 — 문장 5개 이하 분기 크기 상한·줄바꿈 폴백 (spec 12)

nanet 7128e09(문장 5개 이하 분기에도 크기 상한)와 493f760(줄바꿈 폴백·`_split_by_chars`·이어 붙인 텍스트로 크기 추정)을 SKOVIX 코드에 맞게 옮긴다. 두 묶음으로 커밋한다 — 7-1 은 데이터를 버리는 크기 무제한 분기를 막고, 7-2 는 표의 행 경계로 나누는 줄바꿈 폴백을 더한다. kss 는 설치하지 않는다.

**지금 무엇이 깨지나.** `semantic_chunk` 는 문장이 5개 이하면 크기를 보지 않고 본문 전체를 청크 하나로 낸다(`chunker.py:316-322`). 마침표가 거의 없는 표·통계는 정규화(`_normalize_linebreaks` 가 홑줄바꿈을 공백으로 바꾼다) 뒤 '문장' 1개가 되므로 14만 자 표가 섹션 하나가 되고, 섹션 요약은 앞 12,000자(`SUMMARIZER_MAX_SECTION_CHARS`)만 읽는다.

**SKOVIX 에 맞춘 점 (nanet 과 다른 곳)**

| 무엇 | nanet | 여기 | 까닭 |
|---|---|---|---|
| 줄바꿈 폴백을 보는 텍스트 | `_split_sentences` 안 — 정규화 **뒤** | `semantic_chunk` 에서 정규화 **전** 원문을 줄로 나눈다(줄 안의 연속 공백만 정리) | 정규화가 홑줄바꿈을 먼저 지워, 그대로 옮기면 표의 행이 아니라 빈 줄(쪽·단락) 단위로만 나뉜다 |
| 5자 이하 줄 | 버린다 | 다음 줄과 묶는다(끝에 남으면 앞 단위에) | 표에서는 셀 하나·합계 같은 짧은 줄도 데이터다 |
| 폴백 조건 | 문장 ≤ 5 또는 평균 > 500자 | 같은 기준 + 본문이 그 호출의 `max_tokens` 를 넘을 때만 | 상한 안의 짧은 초록·작은 표는 지금처럼 정규화한 한 덩어리로 둔다 |
| 줄 모드 청크를 잇는 문자 | 공백 | 줄바꿈 | 섹션·청크 안에서 표의 행이 보존된다 |
| 줄 위치 | — | 원문 기준 | `page_map`(원문 글자 위치 → 쪽)과 맞아 줄 모드 섹션에도 쪽 범위가 붙는다 |
| 크기 분할 규칙 | 어디서나 `_split_by_chars` + 합친 텍스트 추정 | `_split_oversized(mode=…)` — 의미 경계 청크(문장 모드)는 `"legacy"`(지금 규칙 그대로), 문장 5개 이하 분기는 `"sentence"`, 줄 모드는 `"line"` | 아래 '정상 문서 무변경' |
| 분할 뒤 자투리 재병합(SKOVIX 5a7613b) | 없음 | 그대로 둔다 | 소제목 고아 섹션 방지 |

**정상 문서 무변경 — 실제 논문으로 확인한 결과.** 검증 사본(앞 작업 미적용)에서 이 PC 의 `D:\SKOVIX\KCI\pdf` 무작위 표본 두 벌(143편·488편, 합 631편)을 fitz 로 쪽마다 읽어 `split_into_sections` 처럼 이은 뒤, 옛/새 `semantic_chunk` 를 같은 결정적 임베딩으로 돌려 섹션(800/5,000)·검색 청크(128/1,024) 지문을 견줬다. 운영 추출은 ODL 마크다운이라 근사다.
- 처음 초안은 493f760 처럼 의미 경계 청크의 크기 분할까지 `_split_by_chars`·합친 텍스트 추정으로 바꿨다. 섹션은 그대로였지만 **검색 청크가 143편 중 12편, 488편 중 45편에서 달라졌다.** 모두 정상 논문이다. 본문 안의 표·참고문헌이 마침표 없이 이어져 정규화 뒤 1,536자(검색 청크 상한)를 넘는 '문장' 하나가 되는데, 그 문장을 자르는 자리가 바뀌면 같은 청크 안에서 그 뒤 문장들의 묶음까지 밀린다. 의도한 변화(줄바꿈 폴백·문장 5개 이하 분기 상한)가 아니라 **회귀**다.
- 그래서 의미 경계 청크의 크기 분할은 지금 규칙(`mode="legacy"`: 글자 수 지점 절단, 문장별 추정치 합산)을 그대로 두고, 새 규칙은 지금까지 크기를 안 보던 문장 5개 이하 분기(`"sentence"`)와 줄 모드(`"line"`)에만 쓴다. 고친 뒤 631편 중 **섹션 624편·검색 청크 622편이 바꾸기 전과 같다.**
- 달라지는 것은 줄바꿈 폴백이 켜진 문서뿐이다(섹션 7편·검색 청크 9편 — 검색 청크는 상한이 작아 2편 더 걸린다). 모두 텍스트 층이 문장부호로 나뉘지 않는 문서이고 대부분 깨진 텍스트 층이다: 마침표·숫자가 빠졌거나(KCI_FI001028670·KCI_FI001022938), 낱말 사이 공백이 없거나(KCI_FI001499134·KCI_FI001177945), 공백 자리에 제어 문자 `\x01` 이 들어갔거나(KCI_FI002767541·KCI_FI002535097), 숫자·깨진 글리프만 있거나(KCI_FI001251264·KCI_FI000872204), 그리스어 낱말이 줄마다 하나씩 뽑혔다(KCI_FI001041823). 지금은 '문장'이 5개 이하이거나 평균 700자~5만 자로 뭉치던 문서들이라 줄 단위가 더 나은 경계다.
- 문장 5개 이하이면서 섹션 상한을 넘는 문서는 488편 중 3편이었고 셋 다 줄바꿈이 있어 줄 모드로 갔다. 줄바꿈조차 없는 거대 덩어리(VLM 이 한 줄로 낸 판독문 등)는 `"sentence"` 모드가 받는다.
- 이 회귀를 테스트로 묶었다: 회귀 지문 테스트에 '표가 낀 일반 본문'의 검색 청크(`_GOLDEN_TABLE_SEARCH`)를 넣었고, 본 경로를 `"sentence"` 로 바꾸면 이 테스트가 실패하는 것을 사본에서 확인했다.

알아 둘 한계(둘 다 지금 동작이고 손대지 않는다): 의미 경계가 하나도 안 나는 최악의 경우(같은 줄 반복 등) 크기 분할 뒤 5a7613b 재병합이 상한을 `2 × min_tokens` 까지 넘길 수 있다 — `_merge_small_chunks` 의 앞으로 가는 병합에서 `min_tokens` 미만 조각이 상한 크기 조각을 흡수하고(< `max_tokens + min_tokens`), 끝에 남은 `min_tokens` 미만 조각을 다시 그 앞에 붙이면 `max_tokens + 2·min_tokens` 다(섹션 ≤ 약 6,600토큰 ≈ 9,900자 — 섹션 요약 입력 상한 12,000자 아래). 아래 회귀 테스트의 `max + min` 단언은 그 표본에서 맞는 값이고 일반 상한은 아니다. 일반 본문도 문장별 추정치 합산 때문에 상한을 2% 안팎 넘는 섹션이 나온다(회귀 지문의 7,663자 = 5,108토큰).

**Files:**
- Modify: `app/services/ingestion/chunker.py` — `_split_sentences`(66-74) 뒤에 폴백 도구, `_split_oversized`(196-239) 교체와 `_split_by_chars` 추가, `semantic_chunk` 의 문장 분리·5개 이하 분기(308-322)·청크 잇기(340)·크기 분할 호출(357)
- Create: `app/tests/test_chunker.py`

#### 7-1: 문장 5개 이하 분기에도 크기 상한 (nanet 7128e09 + `_split_by_chars`)

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_chunker.py` 를 새로 만든다. 가짜 임베딩 셋(md5·주제어 one-hot·전부 같은 벡터)과 문서 생성기(일반 논문 본문·표가 낀 본문·마침표 없는 통계표)를 두고, 일반 본문 지문은 **고치기 전 코드로 뽑은 값**을 박아 둔다.

```python
"""chunker.semantic_chunk — 문장 5개 이하 분기 크기 상한·줄바꿈 폴백 (round07 Task 7).

임베딩 모델 없이 돈다. embed_fn 자리에 결정적인 가짜 임베딩을 넣는다.
- _hash_embed: 문장마다 md5 로 만든 벡터 — 실제 모델처럼 이웃 유사도가 제각각이라 경계가 고르게 난다.
- _topic_embed: 문장에 든 주제어로 정한 one-hot — 같은 주제 안은 유사도가 똑같아 주제가 바뀌는 곳에서만 경계가 난다.
- _flat_embed: 모든 문장이 같은 벡터 — 의미 경계가 하나도 안 나는 최악의 경우.
"""
import hashlib

import numpy as np

from services.ingestion import chunker
from services.ingestion.chunker import MAX_CHUNK_BYTES, semantic_chunk

SECTION = dict(min_tokens=800, max_tokens=5000, apply_byte_guard=False)   # stages.split_into_sections 와 같은 값
SEARCH = dict(min_tokens=128, max_tokens=1024, apply_byte_guard=True)     # stages.run_embed_index(검색 청크) 기본값


def _hash_embed(sentences):
    return np.array([[b - 127.5 for b in hashlib.md5(s.encode("utf-8")).digest()] for s in sentences])


_TOPICS = ("서론", "선행연구", "연구방법", "분석결과", "논의", "결론")


def _topic_embed(sentences):
    vecs = []
    for s in sentences:
        v = [0.0] * (len(_TOPICS) + 1)
        v[next((i for i, t in enumerate(_TOPICS) if t in s), len(_TOPICS))] = 1.0
        vecs.append(v)
    return np.array(vecs)


def _flat_embed(sentences):
    return np.ones((len(sentences), 8))


def _page_map(pages):
    """stages.split_into_sections 와 같은 방식: 쪽 텍스트를 "\\n\\n" 으로 잇고 글자 위치 → 쪽 번호."""
    page_map, cursor = {}, 0
    for no, t in enumerate(pages, start=1):
        for i in range(len(t)):
            page_map[cursor + i] = no
        cursor += len(t) + 2
    return "\n\n".join(pages), page_map


def _wrap(text, width=48):
    """PDF 컬럼 줄넘김 흉내 — 단락 안을 width 글자마다 홑줄바꿈으로 끊는다."""
    return "\n".join(text[i:i + width] for i in range(0, len(text), width))


def _prose_document(table_rows=0):
    """마침표가 충분한 일반 논문 본문 — 주제 6개, 제목 줄, 단락 구분(빈 줄), PDF 줄넘김(홑줄바꿈), 10쪽.
    '분석결과' 는 섹션 상한(7,500자)을 넘게 길어 섹션·검색 청크 모두 크기 분할을 탄다.
    table_rows 를 주면 '분석결과' 단락 사이에 마침표 없는 표(행은 홑줄바꿈)를 끼운다 — 정규화하면
    검색 청크 상한(1,536자)을 넘는 '문장' 하나가 된다. 실제 논문의 표·참고문헌 덩어리가 이렇다."""
    sizes = {"서론": 30, "선행연구": 40, "연구방법": 25, "분석결과": 200, "논의": 35, "결론": 15}
    numerals = ("Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ")
    paragraphs = []
    for numeral, topic in zip(numerals, _TOPICS):
        sents = []
        for k in range(sizes[topic]):
            n, d = (k * 37) % 500 + 20, (k * 7) % 30 + 1
            sents.append((
                f"{topic}에서는 {k}번째 쟁점으로 표본 {n}명의 응답 분포를 정리하였다.",
                f"{topic}의 {k}번째 관찰은 집단 간 차이가 {d}점 수준으로 나타났다는 점이다.",
                f"이와 관련하여 {topic} {k}항은 측정 도구의 신뢰도와 타당도를 함께 점검하였다.",
                f"{topic} {k}항에서는 조사 대상 기관 {n}곳의 운영 자료를 연도별로 비교하고, "
                f"그 변화가 정책 환경과 어떻게 맞물리는지 검토하였다.",
            )[k % 4])
        paragraphs.append(f"{numeral}. {topic}")
        for i in range(0, len(sents), 5):
            paragraphs.append(_wrap(" ".join(sents[i:i + 5])))
            if topic == "분석결과" and table_rows and i == 10:
                paragraphs.append("분석결과 표 3 지역별 응답 분포\n" + "\n".join(
                    f"지역{r:03d} {r * 13 % 97} {r * 7 % 89} {r * 5 % 83}" for r in range(table_rows)))
    pages, cur = [], []
    for p in paragraphs:
        cur.append(p)
        if sum(len(x) for x in cur) > 1800:
            pages.append("\n\n".join(cur))
            cur = []
    if cur:
        pages.append("\n\n".join(cur))
    return _page_map(pages)


def _stat_table_document(n_pages=100, rows_per_page=50):
    """마침표 없는 통계표 약 14만 자 — 쪽마다 표 제목 줄 + 행(홑줄바꿈), 쪽 사이는 빈 줄.
    소수점(56.7)은 있지만 뒤에 공백이 없어 문장 분리에 안 걸린다 — 정규화 뒤 '문장' 1개."""
    pages, rows = [], []
    for p in range(n_pages):
        page_rows = [
            f"|{p * rows_per_page + r:05d}|지역{(p * 7 + r) % 17:02d}|{2000 + r % 20}"
            f"|{(p * 31 + r * 17) % 9973}|{(r * 13) % 101}.{p % 10}|"
            for r in range(rows_per_page)
        ]
        rows += page_rows
        pages.append("\n".join([f"표 {p + 1} 지역별 연도별 통계 (단위 천 명)"] + page_rows))
    text, page_map = _page_map(pages)
    return text, page_map, rows


def _fingerprint(chunks):
    """(청크마다 (글자 수, 시작 쪽, 끝 쪽), 전체 텍스트 sha1 앞 16자리)"""
    return (
        [(len(c.text), c.page_start, c.page_end) for c in chunks],
        hashlib.sha1("\x1e".join(c.text for c in chunks).encode("utf-8")).hexdigest()[:16],
    )


# ── 일반 본문: 고치기 전과 같은 경계 (회귀) ──────────────────────────────
# Task 7 적용 전 chunker.py(5a7613b)로 뽑은 지문이다. 고치기 전에도 통과하고(현재 동작 고정)
# 고친 뒤에도 그대로 통과해야 한다. '분석결과' 섹션(7,663자 = 5,108토큰)이 상한을 조금 넘는
# 것도 지금 동작이다 — 문장마다 내림한 추정치를 더하는 묶기 규칙 때문이고 손대지 않는다.
_GOLDEN_TOPIC_SECTION = (
    [(1460, 1, 1), (2063, 1, 2), (1233, 2, 3), (7663, 3, 8), (2817, 3, 8), (2413, 8, 10)],
    "579b8cef380708da",
)
_GOLDEN_TOPIC_SEARCH = (
    [(1460, 1, 1), (1572, 1, 2), (490, 1, 2), (1233, 2, 3), (1569, 3, 8), (1573, 3, 8),
     (1579, 3, 8), (1544, 3, 8), (1560, 3, 8), (1521, 3, 8), (1129, 3, 8), (1578, 8, 9),
     (834, 8, 10)],
    "f1c7ea92096c1a29",
)
_GOLDEN_HASH_SECTION = (
    [(1219, 1, 1), (1889, 1, 2), (1441, 2, 3), (1316, 3, 3), (1751, 4, 4), (2069, 4, 5),
     (1213, 5, 6), (1307, 6, 7), (1476, 7, 7), (1979, 7, 9), (1984, 9, 10)],
    "c71aec9d5c8fc4ef",
)
# 표가 낀 본문의 검색 청크 — 상한을 넘는 '문장'(표 1,850자)을 지금처럼 글자 수 지점(1,536자)에서
# 자르는지 본다. 그 자리를 경계 찾기(_split_by_chars)로 바꾸면 뒤 문장들의 묶음까지 밀려
# (1536, 1559) → (1534, 1561) 처럼 일반 본문 경계가 달라진다. 실제 KCI 논문 488편 중 45편이 그랬다.
_GOLDEN_TABLE_SEARCH = (
    [(1460, 1, 1), (1572, 1, 2), (490, 1, 2), (1233, 2, 3), (784, 3, 9), (1536, 3, 9),
     (1559, 3, 9), (1579, 3, 9), (1569, 3, 9), (1565, 3, 9), (1552, 3, 9), (1561, 3, 9),
     (544, 3, 9), (1578, 9, 10), (834, 9, 10)],
    "0b572f5a680e59be",
)


def test_prose_boundaries_unchanged():
    text, page_map = _prose_document()
    assert _fingerprint(semantic_chunk(text, _topic_embed, page_map=page_map, **SECTION)) == _GOLDEN_TOPIC_SECTION
    assert _fingerprint(semantic_chunk(text, _topic_embed, page_map=page_map, **SEARCH)) == _GOLDEN_TOPIC_SEARCH
    assert _fingerprint(semantic_chunk(text, _hash_embed, page_map=page_map, **SECTION)) == _GOLDEN_HASH_SECTION
    text, page_map = _prose_document(table_rows=120)
    assert _fingerprint(semantic_chunk(text, _topic_embed, page_map=page_map, **SEARCH)) == _GOLDEN_TABLE_SEARCH


# ── 문장 5개 이하 분기에도 크기 상한 (nanet 7128e09) ─────────────────────


def test_few_giant_sentences_are_capped():
    """문장 3개짜리 12만 자(줄바꿈 없음) — 지금은 문장 5개 이하 분기가 크기를 안 보고 한 덩어리로
    내보낸다(섹션 하나 = 8만 토큰). 바이트 가드를 켜든 끄든 상한 이하로 나뉘고 내용은 그대로여야 한다."""
    def sentence(k):
        return f"제{k}판독문 " + " ".join(f"항목{k}{i:05d} 수치 {i * 7 % 997}" for i in range(2600)) + "로 기록되었다."

    text = " ".join(sentence(k) for k in range(3))
    for params in (SECTION, SEARCH):
        out = semantic_chunk(text, _hash_embed, page_map={}, **params)
        assert len(out) > 1
        assert max(c.token_count for c in out) <= params["max_tokens"]
        assert [c.chunk_idx for c in out] == list(range(len(out)))
        assert "".join(c.text for c in out).replace(" ", "") == text.replace(" ", "")   # 버린 글자 없음
    search = semantic_chunk(text, _hash_embed, page_map={}, **SEARCH)
    assert max(len(c.text.encode("utf-8")) for c in search) <= MAX_CHUNK_BYTES


def test_period_free_table_is_capped():
    """마침표 없는 표·통계 14만 자 — 지금은 '문장' 1개로 잡혀 섹션 하나(약 9.4만 토큰)가 되고,
    섹션 요약이 앞 12,000자(SUMMARIZER_MAX_SECTION_CHARS)만 읽는다. 상한 이하 여러 개여야 한다."""
    text, page_map, _ = _stat_table_document()
    assert len(text) > 140_000
    sections = semantic_chunk(text, _hash_embed, page_map=page_map, **SECTION)
    assert len(sections) > 1
    assert max(c.token_count for c in sections) <= SECTION["max_tokens"]
    chunks = semantic_chunk(text, _hash_embed, page_map=page_map, **SEARCH)
    assert max(c.token_count for c in chunks) <= SEARCH["max_tokens"]
    # 의미 경계가 하나도 안 나는 최악의 경우 — 크기 분할 뒤 자투리 재병합(5a7613b)이 끝 조각을
    # 앞 조각에 붙이면 상한을 min_tokens 만큼까지 넘을 수 있다. 그래도 섹션 요약 입력 상한 아래다.
    worst = semantic_chunk(text, _flat_embed, page_map=page_map, **SECTION)
    assert len(worst) > 1
    assert max(c.token_count for c in worst) <= SECTION["max_tokens"] + SECTION["min_tokens"]
    assert max(len(c.text) for c in worst) <= 12_000


def test_split_by_chars_prefers_boundaries_and_loses_nothing():
    s = "가나다라 " * 1000                      # 5,000자, 공백 경계만 있음
    parts = chunker._split_by_chars(s, 700)
    assert "".join(parts) == s
    assert all(len(p) <= 700 for p in parts)
    assert all(p.endswith(" ") for p in parts[:-1])   # 글자 중간이 아니라 공백에서 끊었다
    assert chunker._split_by_chars("가" * 1500, 700) == ["가" * 700, "가" * 700, "가" * 100]   # 경계가 없으면 글자 수에서
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_chunker.py -q`
Expected: `3 failed, 1 passed`
- `test_few_giant_sentences_are_capped` — `assert 1 > 1` (문장 3개 12만 자가 청크 하나)
- `test_period_free_table_is_capped` — `assert 1 > 1` (표 14만 자가 섹션 하나, 약 9.4만 토큰)
- `test_split_by_chars_prefers_boundaries_and_loses_nothing` — `AttributeError: module 'services.ingestion.chunker' has no attribute '_split_by_chars'`
- `test_prose_boundaries_unchanged` 는 **지금도 통과해야 한다** — 바꾸기 전 동작을 고정하는 테스트다. 여기서 실패하면 지문을 뽑은 코드와 지금 코드가 다르다는 뜻이니 멈추고 확인한다. 지문은 설정 기본값(`SIMILARITY_WINDOW` 3·`BREAKPOINT_PERCENTILE` 25) 기준이라, 셸에 이 환경변수가 걸려 있으면 달라진다.

- [ ] **Step 3: 구현**

`app/services/ingestion/chunker.py` 의 `_split_oversized` 함수 전체(196-239행)

```python
def _split_oversized(chunk: Chunk, max_tokens: int = MAX_CHUNK_TOKENS) -> list[Chunk]:
    """max_tokens 초과 청크를 문장 경계에서 분할"""
    if chunk.token_count <= max_tokens:
        return [chunk]

    # 표·OCR 덩어리처럼 문장 종결부호가 없는 텍스트는 '한 문장'이 max_tokens 를 넘길 수
    # 있고, 그러면 아래 루프가 쪼개지 못해 거대한 청크가 그대로 남는다(LLM 컨텍스트 초과).
    # → 문장 자체가 상한을 넘으면 글자 단위로 강제 분할한다.
    max_chars = int(max_tokens * 1.5)
    sentences: list[str] = []
    for s in _split_sentences(chunk.text):
        if _estimate_tokens(s) > max_tokens:
            sentences.extend(s[i:i + max_chars] for i in range(0, len(s), max_chars))
        else:
            sentences.append(s)

    sub_chunks = []
    current_text = ""
    current_tokens = 0

    for sent in sentences:
        sent_tokens = _estimate_tokens(sent)
        if current_tokens + sent_tokens > max_tokens and current_text:
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
```

를 아래 두 함수로 바꾼다. 의미 경계 청크가 부르는 기본값 `mode="legacy"` 는 지금과 똑같이 동작한다.

```python
def _split_by_chars(s: str, max_chars: int) -> list[str]:
    """줄바꿈/문장부호/공백 경계를 우선해 글자 수 기준으로 강제 분할 (nanet 493f760).

    문장(또는 줄) 하나가 상한을 넘을 때의 최후 수단. 조각마다 뒤쪽 절반 안에서 경계를
    찾고, 못 찾으면 max_chars 지점에서 자른다. 조각을 이어 붙이면 원문 그대로다(손실 없음)."""
    parts = []
    cursor = 0
    n = len(s)
    while cursor < n:
        end = min(n, cursor + max_chars)
        if end < n:  # 마지막 조각이면 경계 탐색 불필요
            for break_char in ("\n", ". ", "。", "! ", "? ", " "):
                idx = s.rfind(break_char, cursor + max_chars // 2, end)
                if idx > cursor:
                    end = idx + len(break_char)
                    break
        parts.append(s[cursor:end])
        cursor = end
    return parts


def _split_oversized(
    chunk: Chunk, max_tokens: int = MAX_CHUNK_TOKENS, *, mode: str = "legacy",
) -> list[Chunk]:
    """max_tokens 초과 청크를 문장 경계에서 분할.

    mode — 부르는 자리마다 자르는 규칙이 다르다.
      "legacy"   의미 경계로 만든 청크. 지금까지의 규칙 그대로 — 상한을 넘는 문장은 글자 수
                 지점에서 자르고, 문장별 추정치를 더해 묶는다. 이 자리를 바꾸면 그 뒤 문장들의
                 묶음까지 밀려 마침표가 충분한 일반 본문의 청크 경계가 달라지므로 그대로 둔다.
      "sentence" 문장 5개 이하 분기(nanet 7128e09 — 지금까지 크기를 안 보던 곳). 상한을 넘는 문장은
                 줄바꿈·문장부호·공백 경계에서 자르고(_split_by_chars), 이어 붙인 텍스트로 잰다.
    """
    if chunk.token_count <= max_tokens:
        return [chunk]

    legacy = mode == "legacy"
    # 표·OCR 덩어리처럼 문장 종결부호가 없는 텍스트는 '한 문장'이 max_tokens 를 넘길 수
    # 있고, 그러면 아래 루프가 쪼개지 못해 거대한 청크가 그대로 남는다(LLM 컨텍스트 초과).
    # → 문장 자체가 상한을 넘으면 강제 분할한다.
    max_chars = int(max_tokens * 1.5)
    sentences: list[str] = []
    for s in _split_sentences(chunk.text):
        if _estimate_tokens(s) <= max_tokens:
            sentences.append(s)
        elif legacy:
            sentences.extend(s[i:i + max_chars] for i in range(0, len(s), max_chars))
        else:
            sentences.extend(_split_by_chars(s, max_chars))

    sub_chunks = []
    current_text = ""
    current_tokens = 0

    for sent in sentences:
        sent_tokens = _estimate_tokens(sent)
        if legacy:
            over = bool(current_text) and current_tokens + sent_tokens > max_tokens
        else:
            # 짧은 조각을 많이 이을 때 조각마다 내림한 추정치를 더하면 구분자 몫과 내림 오차가
            # 쌓여 상한을 넘는다 → 이어 붙인 텍스트로 잰다(nanet 493f760).
            over = bool(current_text) and _estimate_tokens(f"{current_text} {sent}") > max_tokens
        if over:
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
```

`semantic_chunk` 의 문장 5개 이하 분기(316-322행)

```python
    # 문장 수가 적으면 그냥 하나로 (바이트 가드는 마지막에 일괄 적용)
    if len(sentences) <= 5:
        single = Chunk(chunk_idx=0, text=text)
        parts = _split_by_bytes(single) if apply_byte_guard else [single]
        for i, c in enumerate(parts):
            c.chunk_idx = i
        return parts
```

를 아래로 바꾼다. 바이트 가드를 켜든 끄든(섹션은 끈다) 크기 상한을 먼저 건다.

```python
    # 문장 수가 적으면 의미 경계 탐지는 생략하지만 크기 상한(max_tokens)은 그대로 적용한다
    # (nanet 7128e09) — 문장부호가 적은 텍스트는 "문장" 5개 이하로 잡혀도 수만~십만 자일 수
    # 있고, 상한 없이 한 덩어리로 나가면 섹션 요약 입력 상한(SUMMARIZER_MAX_SECTION_CHARS)에서
    # 뒷부분이 통째로 잘린다. 바이트 가드는 그 뒤에 따로 건다.
    if len(sentences) <= 5:
        parts = _split_oversized(Chunk(chunk_idx=0, text=text), max_tokens=max_tokens, mode="sentence")
        if apply_byte_guard:
            parts = [g for c in parts for g in _split_by_bytes(c)]
        for i, c in enumerate(parts):
            c.chunk_idx = i
        return parts
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_chunker.py -q`
Expected: `4 passed`

- [ ] **Step 5: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: `failed` 0, 수집 오류 3(`test_book_chat`·`test_build_manifest`·`test_loaders` — 기존). passed 가 직전 커밋보다 4 늘어난다(앞 작업 미적용 사본에서 890 → 894).

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/services/ingestion/chunker.py app/tests/test_chunker.py
git commit -m "[Fix] round07 — 청킹: 문장 5개 이하 분기에도 크기 상한(nanet 7128e09). 마침표가 거의 없는 표·통계는 정규화 뒤 '문장' 몇 개로 잡혀 섹션 하나(수만~십만 자)로 나가고 섹션 요약이 앞 12,000자만 읽었다. 이 분기는 상한을 넘는 문장을 줄바꿈·문장부호·공백 경계에서 자르고(_split_by_chars, nanet 493f760) 이어 붙인 텍스트로 잰다. 의미 경계 청크의 크기 분할은 지금 규칙(legacy) 그대로 — 실제 KCI 논문에서 그 자리를 바꾸면 표·참고문헌 덩어리 뒤 일반 본문의 검색 청크가 밀렸다(143편 중 12편, 488편 중 45편)"
```

#### 7-2: 줄바꿈 폴백 — 정규화 전 원문을 줄 단위로 (nanet 493f760 을 SKOVIX 정규화 순서에 맞게)

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_chunker.py` 맨 위 import

```python
import hashlib

import numpy as np

from services.ingestion import chunker
from services.ingestion.chunker import MAX_CHUNK_BYTES, semantic_chunk
```

를 아래로 바꾼다.

```python
import collections
import hashlib

import numpy as np

from services.ingestion import chunker
from services.ingestion.chunker import MAX_CHUNK_BYTES, _normalize_linebreaks, semantic_chunk
```

그리고 파일 끝에 붙인다.

```python
# ── 줄바꿈 폴백 — 정규화 전 원문을 줄 단위로 (nanet 493f760 을 SKOVIX 정규화 순서에 맞게) ──


def test_line_split_keeps_table_rows_whole():
    """마침표 없는 표는 줄(행) 단위로 나뉜다 — 섹션·청크의 줄 하나하나가 표의 온전한 행이고, 모든 행이
    정확히 한 번 나온다. 정규화 뒤에 나누면 홑줄바꿈이 공백이 돼 한 쪽의 행이 한 줄로 뭉치고 행 중간에서 끊긴다."""
    text, page_map, rows = _stat_table_document()
    for embed in (_hash_embed, _flat_embed):
        for params in (SECTION, SEARCH):
            seen = collections.Counter()
            for c in semantic_chunk(text, embed, page_map=page_map, **params):
                for line in c.text.split("\n"):
                    if not line.startswith("표 "):        # 쪽마다 붙은 표 제목 줄은 빼고 센다
                        seen[line] += 1
            assert seen == collections.Counter(rows), (embed.__name__, params["max_tokens"])


def test_line_mode_resolves_pages():
    """줄 단위 위치는 원문 기준이라 page_map 과 맞는다 — 섹션마다 쪽 범위가 붙고 1쪽부터 100쪽까지 순서대로 이어진다."""
    text, page_map, _ = _stat_table_document()
    pages = [(c.page_start, c.page_end) for c in semantic_chunk(text, _hash_embed, page_map=page_map, **SECTION)]
    assert all(s is not None and s <= e for s, e in pages)
    assert pages[0][0] == 1 and pages[-1][1] == 100
    assert [s for s, _ in pages] == sorted(s for s, _ in pages)


def test_split_lines_keeps_short_lines_with_raw_offsets():
    """5자 이하 줄(합계·셀 하나)은 버리지 않고 다음 줄과 묶고, 끝에 남으면 앞 단위에 붙인다.
    줄 안의 연속 공백만 줄이고, start/end 는 원문 위치다."""
    raw = "합계\n|001|가|\n\n  |002|  나|  \n12"
    units = chunker._split_lines_with_offsets(raw)
    assert units == [
        {"text": "합계\n|001|가|", "start": 0, "end": 10},
        {"text": "|002| 나|\n12", "start": 12, "end": 28},
    ]
    assert raw[0:10] == "합계\n|001|가|" and raw[12:28] == "  |002|  나|  \n12"


def test_line_fallback_skips_text_within_cap():
    """상한 안에 드는 짧은 본문(문장 5개 이하 초록·작은 표)은 줄바꿈 폴백 없이 지금처럼 정규화한 한 덩어리다."""
    abstract = "본 연구는 지역 도서관의\n이용 실태를 조사하였다. 표본은 전국 30개 관\n이다. 그 결과 이용률이 높아졌다."
    small_table = "\n".join(f"|{r:03d}|지역{r % 5}|{r * 3}|" for r in range(20))
    for t in (abstract, small_table):
        for params in (SECTION, SEARCH):
            out = semantic_chunk(t, _hash_embed, page_map={}, **params)
            assert [c.text for c in out] == [_normalize_linebreaks(t)]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_chunker.py -q`
Expected: `3 failed, 5 passed`
- `test_line_split_keeps_table_rows_whole` — `assert Counter(...) == Counter(...)`: 정규화 뒤 한 쪽의 행 50개가 공백으로 이어진 한 줄이 된다
- `test_line_mode_resolves_pages` — `assert False`: 문장 5개 이하 분기는 쪽 범위가 없다(`None`)
- `test_split_lines_keeps_short_lines_with_raw_offsets` — `AttributeError: ... no attribute '_split_lines_with_offsets'`
- `test_line_fallback_skips_text_within_cap` 은 지금도 통과한다 — 상한 안의 짧은 본문은 바뀌지 않아야 한다는 가드다.

- [ ] **Step 3: 구현** (7-1 이 끝난 `chunker.py` 에)

1. 모듈 docstring 의 `1) 문장 단위 분할` 줄을 `1) 문장 단위 분할 (문장부호가 거의 없는 표·통계는 줄 단위 — 줄바꿈 폴백)` 로 바꾼다.
2. `_split_sentences` 함수 바로 뒤(`return [s.strip() for s in sentences if len(s.strip()) > 5]` 다음, `_compute_embeddings` 앞)에 넣는다.

```python
# 줄바꿈 폴백 기준(nanet 493f760 과 같은 값) — 문장부호로 나눈 결과가 이 개수 이하이거나
# 평균 길이가 이보다 길면, 문장부호가 거의 없는 본문(표·통계·양식)이 뭉친 것으로 본다.
_LINE_FALLBACK_MAX_SENTENCES = 5
_LINE_FALLBACK_AVG_CHARS = 500


def _split_lines_with_offsets(text: str) -> list[dict]:
    """정규화 **전** 원문을 줄 단위로 나눈다 — 표·통계의 행 경계(홑줄바꿈)를 살리는 줄바꿈 폴백.

    _normalize_linebreaks 는 홑줄바꿈을 공백으로 바꾸므로, 정규화한 뒤에 줄로 나누면 표의
    행이 아니라 빈 줄(쪽·단락) 단위로만 나뉜다. 그래서 원문에서 나누고 줄 안의 연속 공백만
    줄인다. 5자 이하 줄(셀 하나·합계·쪽 번호)은 버리지 않고 다음 줄과 이어 한 단위로
    묶는다 — 문장 분리는 5자 이하 조각을 버리지만, 표에서는 짧은 줄도 데이터다.
    start/end 는 원문 기준 위치라 page_map(원문 글자 위치 → 쪽)과 그대로 맞는다.
    """
    units: list[dict] = []
    buf: list[str] = []
    buf_start = buf_end = 0
    pos = 0
    for raw_line in text.split("\n"):
        line_start, pos = pos, pos + len(raw_line) + 1
        line = re.sub(r"  +", " ", raw_line).strip()
        if not line:
            continue
        if not buf:
            buf_start = line_start
        buf.append(line)
        buf_end = line_start + len(raw_line)
        joined = "\n".join(buf)
        if len(joined) > 5:
            units.append({"text": joined, "start": buf_start, "end": buf_end})
            buf = []
    if buf:  # 끝에 남은 짧은 줄 — 앞 단위에 붙인다(앞 단위가 없으면 그대로 한 단위)
        tail = "\n".join(buf)
        if units:
            units[-1]["text"] += "\n" + tail
            units[-1]["end"] = buf_end
        else:
            units.append({"text": tail, "start": buf_start, "end": buf_end})
    return units


def _needs_line_fallback(sentences: list[dict], text: str, max_tokens: int) -> bool:
    """문장부호 분리가 사실상 실패했는가 — 줄바꿈 폴백을 검토할지 정한다.

    본문이 max_tokens 안에 들면 폴백하지 않는다(짧은 초록·작은 표는 지금처럼 한 덩어리).
    넘으면 문장이 5개 이하이거나 평균 문장 길이가 500자를 넘을 때 폴백을 검토한다.
    마침표가 충분한 일반 본문(문장 수십~수백 개, 평균 수십~백여 자)은 어느 쪽에도 걸리지 않는다.
    """
    if _estimate_tokens(text) <= max_tokens:
        return False
    if len(sentences) <= _LINE_FALLBACK_MAX_SENTENCES:
        return True
    avg_len = sum(len(s["text"]) for s in sentences) / len(sentences)
    return avg_len > _LINE_FALLBACK_AVG_CHARS
```

3. 7-1 에서 쓴 `_split_oversized` 함수 전체를 아래로 바꾼다(`"line"` 모드를 더한다 — `"legacy"`·`"sentence"` 동작은 그대로다).

```python
def _split_oversized(
    chunk: Chunk, max_tokens: int = MAX_CHUNK_TOKENS, *, mode: str = "legacy",
) -> list[Chunk]:
    """max_tokens 초과 청크를 문장 경계(줄 모드면 줄 경계)에서 분할.

    mode — 부르는 자리마다 자르는 규칙이 다르다.
      "legacy"   의미 경계로 만든 청크. 지금까지의 규칙 그대로 — 상한을 넘는 문장은 글자 수
                 지점에서 자르고, 문장별 추정치를 더해 묶는다. 이 자리를 바꾸면 그 뒤 문장들의
                 묶음까지 밀려 마침표가 충분한 일반 본문의 청크 경계가 달라지므로 그대로 둔다.
      "sentence" 문장 5개 이하 분기(nanet 7128e09 — 지금까지 크기를 안 보던 곳). 상한을 넘는 문장은
                 줄바꿈·문장부호·공백 경계에서 자르고(_split_by_chars), 이어 붙인 텍스트로 잰다.
      "line"     줄바꿈 폴백. 정규화 전 줄 단위로 나눈 청크를 줄 단위로 다시 나누고 줄바꿈으로
                 잇는다(표의 행 보존). 자르는 규칙은 "sentence" 와 같다.
    """
    if chunk.token_count <= max_tokens:
        return [chunk]

    legacy = mode == "legacy"
    # 표·OCR 덩어리처럼 문장 종결부호가 없는 텍스트는 '한 문장'이 max_tokens 를 넘길 수
    # 있고, 그러면 아래 루프가 쪼개지 못해 거대한 청크가 그대로 남는다(LLM 컨텍스트 초과).
    # → 문장 자체가 상한을 넘으면 강제 분할한다.
    max_chars = int(max_tokens * 1.5)
    units = (
        [u["text"] for u in _split_lines_with_offsets(chunk.text)] if mode == "line"
        else _split_sentences(chunk.text)
    )
    sentences: list[str] = []
    for s in units:
        if _estimate_tokens(s) <= max_tokens:
            sentences.append(s)
        elif legacy:
            sentences.extend(s[i:i + max_chars] for i in range(0, len(s), max_chars))
        else:
            sentences.extend(_split_by_chars(s, max_chars))

    sep = "\n" if mode == "line" else " "
    sub_chunks = []
    current_text = ""
    current_tokens = 0

    for sent in sentences:
        sent_tokens = _estimate_tokens(sent)
        if legacy:
            over = bool(current_text) and current_tokens + sent_tokens > max_tokens
        else:
            # 짧은 조각을 많이 이을 때 조각마다 내림한 추정치를 더하면 구분자 몫과 내림 오차가
            # 쌓여 상한을 넘는다 → 이어 붙인 텍스트로 잰다(nanet 493f760).
            over = bool(current_text) and _estimate_tokens(current_text + sep + sent) > max_tokens
        if over:
            sub_chunks.append(Chunk(
                chunk_idx=0,  # 나중에 재번호
                text=current_text.strip(),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
            ))
            current_text = sent
            current_tokens = sent_tokens
        else:
            current_text = current_text + sep + sent if current_text else sent
            current_tokens += sent_tokens

    if current_text.strip():
        sub_chunks.append(Chunk(
            chunk_idx=0,
            text=current_text.strip(),
            page_start=chunk.page_start,
            page_end=chunk.page_end,
        ))

    return sub_chunks
```

4. `semantic_chunk` 의 문장 분리부터 문장 5개 이하 분기까지

```python
    # 1. 줄바꿈 정규화 후 문장 분리
    text = _normalize_linebreaks(text)
    sentences = _split_sentences_with_offsets(text)
    if not sentences:
        return []

    log.info(f"문장 {len(sentences)}개 분리 완료")

    # 문장 수가 적으면 의미 경계 탐지는 생략하지만 크기 상한(max_tokens)은 그대로 적용한다
    # (nanet 7128e09) — 문장부호가 적은 텍스트는 "문장" 5개 이하로 잡혀도 수만~십만 자일 수
    # 있고, 상한 없이 한 덩어리로 나가면 섹션 요약 입력 상한(SUMMARIZER_MAX_SECTION_CHARS)에서
    # 뒷부분이 통째로 잘린다. 바이트 가드는 그 뒤에 따로 건다.
    if len(sentences) <= 5:
        parts = _split_oversized(Chunk(chunk_idx=0, text=text), max_tokens=max_tokens, mode="sentence")
        if apply_byte_guard:
            parts = [g for c in parts for g in _split_by_bytes(c)]
        for i, c in enumerate(parts):
            c.chunk_idx = i
        return parts
```

를 아래로 바꾼다.

```python
    # 1. 줄바꿈 정규화 후 문장 분리
    raw_text = text
    text = _normalize_linebreaks(raw_text)
    sentences = _split_sentences_with_offsets(text)

    # 1-1. 줄바꿈 폴백 — 표·통계처럼 문장부호가 거의 없는 본문은 거대한 '문장' 몇 개로 뭉쳐
    #      의미 경계 탐지가 비교할 단위를 못 받는다. 정규화가 홑줄바꿈(표의 행 경계)을 이미
    #      공백으로 지웠으므로 정규화 전 원문을 줄 단위로 나눠 문장 대신 쓰고(줄 안만 정규화),
    #      청크 안의 줄은 줄바꿈으로 이어 행을 보존한다. 줄로 나눈 쪽이 더 잘게 나뉠 때만 쓴다.
    line_mode = False
    if _needs_line_fallback(sentences, text, max_tokens):
        lines = _split_lines_with_offsets(raw_text)
        if len(lines) > len(sentences):
            sentences, line_mode = lines, True
    sep = "\n" if line_mode else " "
    if not sentences:
        return []

    log.info(f"{'줄' if line_mode else '문장'} {len(sentences)}개 분리 완료")

    # 문장 수가 적으면 의미 경계 탐지는 생략하지만 크기 상한(max_tokens)은 그대로 적용한다
    # (nanet 7128e09) — 문장부호가 적은 텍스트는 "문장" 5개 이하로 잡혀도 수만~십만 자일 수
    # 있고, 상한 없이 한 덩어리로 나가면 섹션 요약 입력 상한(SUMMARIZER_MAX_SECTION_CHARS)에서
    # 뒷부분이 통째로 잘린다. 바이트 가드는 그 뒤에 따로 건다.
    if len(sentences) <= 5:
        body = sep.join(s["text"] for s in sentences) if line_mode else text
        parts = _split_oversized(
            Chunk(chunk_idx=0, text=body), max_tokens=max_tokens,
            mode="line" if line_mode else "sentence",
        )
        if apply_byte_guard:
            parts = [g for c in parts for g in _split_by_bytes(c)]
        for i, c in enumerate(parts):
            c.chunk_idx = i
        return parts
```

5. 같은 함수에서 의미 경계로 청크를 만드는 줄 `chunk_text = " ".join(s["text"] for s in current_sentences)` 를 `chunk_text = sep.join(s["text"] for s in current_sentences)` 로 바꾼다.
6. 크기 분할 호출 `final_chunks.extend(_split_oversized(chunk, max_tokens=max_tokens))` 를 아래로 바꾼다.

```python
        final_chunks.extend(_split_oversized(
            chunk, max_tokens=max_tokens, mode="line" if line_mode else "legacy",
        ))
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_chunker.py -q`
Expected: `8 passed`

- [ ] **Step 5: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: `failed` 0, 수집 오류 3(기존). passed 가 직전 커밋보다 4 늘어난다(사본에서 894 → 898).

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/services/ingestion/chunker.py app/tests/test_chunker.py
git commit -m "[Fix] round07 — 청킹: 줄바꿈 폴백. 문장부호로 거의 안 나뉘고(문장 5개 이하, 평균 500자 초과) 상한을 넘는 본문은 정규화 전 원문을 줄 단위로 나눠(줄 안만 공백 정리) 의미 경계를 찾고 줄바꿈으로 이어 표의 행을 보존한다 — 493f760 을 그대로 옮기면 _normalize_linebreaks 가 홑줄바꿈을 먼저 지워 쪽 단위로만 나뉜다. 5자 이하 줄은 버리지 않고 묶고, 줄 위치가 원문 기준이라 쪽 범위가 붙는다. 실제 KCI 논문 631편 중 바뀌는 것은 텍스트 층이 깨진 문서(섹션 7편, 검색 청크 9편)뿐"
```

---

### Task 8: 계층 요약·마무리 병렬·논문 표지 끄기 (spec 3·4·13)

세 묶음으로 커밋한다 — 8-1 계층 요약 함수와 중간 요약 프롬프트, 8-2 생성 함수 네 개의 `combined_text` 인자, 8-3 `run_finalize` 의 동시 호출과 논문 표지 끄기.

**설계 (nanet 746744e 와 다른 곳)**
- 공통 계약대로 `reduce_section_summaries(title, author, section_summaries, doc_type="book") -> str` — 프롬프트에 그대로 넣을 **텍스트**를 돌려준다(nanet 은 요약 목록). 이어 붙인 길이가 `SUMMARIZER_MAX_INPUT_CHARS` 이하면 `_combine_sections` 와 한 글자도 다르지 않은 텍스트다(LLM 호출 없음). 넘으면 중간 요약을 `[섹션 1~12] …` 처럼 덮는 범위를 붙여 잇는다.
- 묶음 나누기는 nanet `_group_for_reduce` 그대로(누적 분량 n 등분, 묶음당 최소 3,000자, 중간 요약 예상 1,500자) + **블록 수 ÷ 2 를 넘지 않게** 하나를 더했다. 섹션 요약이 커서 고르게 나누면 블록 하나짜리 묶음만 생길 때, 하나짜리는 다시 요약해도 줄지 않아 2단계 뒤 샘플링으로 떨어지기 때문이다(`test_reduce_pairs_up_large_summaries`, 이 항을 빼면 실패하는 것을 사본에서 확인).
- 최대 2단계(nanet 3회). 중간 요약이 하나라도 실패하거나(예외·빈 응답) 2단계 뒤에도 넘으면 지금의 균등 샘플링(`_combine_sections`)으로 돌아간다 — nanet 은 실패한 묶음만 원본으로 두지만, 여기는 지시대로 통째로 지금 동작을 쓴다.
- 중간 요약은 묶음끼리 동시에, `asyncio.Semaphore(LLM_SECTION_CONCURRENCY)` 안에서 부른다. 이벤트 루프가 `run_async` 마다 새로 생기므로 세마포어는 호출 안에서 만든다(모듈 전역 금지 — spec 5).
- 프롬프트 `section_group_summary.yaml` 은 nanet 프롬프트에 저자 줄과 "소제목·번호·글머리표·`[섹션 …]` 표시 없이" 를 더했다. 개수 예시는 넣지 않는다(함정 15) — 테스트가 `N개`·`N가지` 를 막는다. 길이 목표 "1,000자 내외" 는 묶음 수 계산(`_INTERMEDIATE_EXPECTED_CHARS`)과 맞물려 남긴다. doc_type 변형 없이 기본 파일 하나를 쓴다.
- 실제 설정값(상한 14,000자, 섹션 요약 330자, 중간 요약 1,000자)으로 사본에서 돌린 결과: 섹션 40개(13,589자)는 호출 없이 그대로 / 43개 → 묶음 4개, 최종 입력 4,049자 / 80개 → 9개, 9,113자 / 400개 → 10개, 10,142자 / 1,000개 → 1단계 25개(25,368자) → 2단계 8개, 8,117자. 중간 요약을 1,400자로 넘겨 써도 80개는 12,713자로 1단계에서 끝난다. 상한을 살짝 넘은 문서(43개)는 입력이 13.6천 자 → 4천 자로 주는 대신 버리는 섹션이 없다(spec 13 의 결정 — 지금은 마지막 섹션부터 버린다).
- `run_finalize` 는 `run_async` 한 번 안에서 계층 요약 → 문서 요약·소개글(도서류는 줄거리·독후 효과도)을 `asyncio.gather(…, return_exceptions=True)` 로 동시에 보낸다. 동시 호출은 `LLM_SECTION_CONCURRENCY` 까지 — compose 주석의 "글로벌 동시 LLM = celery-llm 4 × LLM_SECTION_CONCURRENCY 4 ≤ 16" 예산을 마무리 단계도 지킨다(기본값 4 면 도서 4개가 한꺼번에 간다). 계층 요약이 예외를 내면 `combined_text=None` 으로 넘겨 각 함수가 지금처럼 합친다. 생성 실패는 지금처럼 하나씩 경고(문구 그대로) 후 `None`.
- 논문(`doc_type == "paper"`)은 `skip_cover` 와 상관없이 표지를 건너뛴다(사용자 결정 2026-10-01). 도서는 지금처럼 `skip_cover` 를 따른다.
- 백필 태스크(`app/workers/tasks.py` 의 `backfill_plot`·`backfill_read_effect`·`backfill_summary`)는 키워드 인자로 부르고 `combined_text` 를 넘기지 않으므로 그대로 `_combine_sections` 를 쓴다. 바꾸지 않는다(`test_backfill_summary.py` 통과로 확인).

**Files:**
- Modify: `app/services/ingestion/summarizer.py` — import(7행), `_combine_sections`(126-149) 자리에 계층 요약, 생성 함수 4개(152·176·199·223행)에 `combined_text`
- Create: `app/domains/nl_library/prompts/section_group_summary.yaml`
- Modify: `app/services/ingestion/stages.py` — 모듈 docstring 8-9행, `run_finalize` 의 import(689-694)와 생성 블록·표지 조건(722-760)
- Test: `app/tests/test_summarizer.py`(덧붙임), `app/tests/test_prompts.py`(덧붙임), Create: `app/tests/test_run_finalize.py`

#### 8-1: 계층 요약 `reduce_section_summaries` 와 중간 요약 프롬프트

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_summarizer.py` 맨 위 `import asyncio` 다음 줄에 `import re` 를 넣고, 파일 끝에 붙인다.

```python
# ── reduce_section_summaries (2단계 계층 요약 — round07 Task 8) ─────────────
# 섹션 요약을 이어 붙인 길이가 상한을 넘으면 _combine_sections 는 균등 샘플링으로 일부 섹션을
# 버린다(마지막 섹션이 늘 빠진다). 그 전에 연속 섹션끼리 묶어 중간 요약으로 줄인다.
class _ReduceCfg:
    def __init__(self, cap, concurrency=4):
        self.SUMMARIZER_MAX_INPUT_CHARS = cap
        self.SUMMARIZER_BOOK_TIMEOUT = 240
        self.LLM_SECTION_CONCURRENCY = concurrency


def _patch_reduce(monkeypatch, cap, fake_chat, concurrency=4):
    captured = {"prompt_names": [], "render_kw": []}

    class _Tpl:
        parser = "plain"
        params = {"max_tokens": 2048}

        def render(self, **kw):
            captured["render_kw"].append(kw)
            return ("sys", f"user::{kw['section_summaries']}", dict(self.params))

    def fake_get_prompt(name, doc_type=None):
        captured["prompt_names"].append(name)
        return _Tpl()

    monkeypatch.setattr(summarizer, "get_settings", lambda: _ReduceCfg(cap, concurrency))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", fake_get_prompt)
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)
    return captured


def _items(n, filler=80):
    return [f"섹션요약{i:03d} " + "가" * filler for i in range(n)]


def _ranges(text):
    return [(int(a), int(b)) for a, b in re.findall(r"\[섹션 (\d+)~(\d+)\]", text)]


def test_reduce_under_cap_is_combine_sections_without_llm(monkeypatch):
    """상한 이하면 LLM 없이 지금 _combine_sections 와 같은 텍스트 — 대부분 문서는 그대로."""
    async def fake_chat(*a, **kw):
        raise AssertionError("상한 이하인데 LLM 호출됨")

    _patch_reduce(monkeypatch, 10000, fake_chat)
    items = ["가나다", "", "라마바"]
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))
    assert out == summarizer._combine_sections(items) == "[섹션 1] 가나다\n\n[섹션 2] 라마바"
    assert asyncio.run(summarizer.reduce_section_summaries("제목", "저자", [])) == ""


def test_reduce_over_cap_covers_every_section_in_order(monkeypatch):
    """넘으면 연속한 섹션끼리 묶어 중간 요약 — 버리는 섹션 없이(마지막 섹션 포함) 순서대로 한 번씩."""
    prompts = []

    async def fake_chat(system, user, params, timeout):
        prompts.append(user)
        return f"중간요약{len(prompts):02d}"

    captured = _patch_reduce(monkeypatch, 1000, fake_chat)
    items = _items(40)                                   # 40 × 약 100자 ≈ 4,400자 > 1,000
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))

    assert set(captured["prompt_names"]) == {"section_group_summary"}
    assert all(kw["title"] == "제목" and kw["author"] == "저자" for kw in captured["render_kw"])
    for i in range(40):                                  # 모든 섹션이 정확히 한 묶음에 한 번씩
        assert sum(f"섹션요약{i:03d}" in p for p in prompts) == 1, i
    for p in prompts:                                    # 묶음 하나는 이어진 섹션들
        nums = [int(n) for n in re.findall(r"섹션요약(\d{3})", p)]
        assert nums == list(range(nums[0], nums[0] + len(nums)))
    assert len(out) <= 1000
    ranges = _ranges(out)
    assert ranges[0][0] == 1 and ranges[-1][1] == 40     # 첫 섹션부터 마지막 섹션까지
    assert all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))   # 빈틈없이 이어진다


def test_reduce_second_level_when_intermediates_still_over_cap(monkeypatch):
    """중간 요약을 이어 붙여도 넘으면 중간 요약끼리 한 단계 더 묶는다(2단계)."""
    prompts = []

    async def fake_chat(system, user, params, timeout):
        prompts.append(user)
        return "요" * 200

    _patch_reduce(monkeypatch, 1000, fake_chat)
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", _items(60, filler=90)))

    assert any(re.search(r"\[섹션 \d+~\d+\]", p) for p in prompts)   # 2단계 입력 = 1단계 중간 요약
    assert len(out) <= 1000
    assert _ranges(out)[0][0] == 1 and _ranges(out)[-1][1] == 60


def test_reduce_falls_back_to_sampling_when_a_group_fails(monkeypatch):
    """중간 요약이 하나라도 실패하면(예외·빈 응답) 지금의 균등 샘플링으로 돌아간다."""
    items = _items(40)

    async def raising(system, user, params, timeout):
        if "섹션요약000" in user:
            raise RuntimeError("LLM 다운")
        return "중간요약"

    _patch_reduce(monkeypatch, 1000, raising)
    assert asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items)) == summarizer._combine_sections(items)

    async def blank(system, user, params, timeout):
        return "  " if "섹션요약039" in user else "중간요약"

    _patch_reduce(monkeypatch, 1000, blank)
    assert asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items)) == summarizer._combine_sections(items)


def test_reduce_falls_back_when_still_over_cap_after_two_levels(monkeypatch):
    """중간 요약이 줄지 않아 2단계 뒤에도 넘으면 균등 샘플링(상한 준수)으로 돌아간다."""
    async def fake_chat(system, user, params, timeout):
        return "요" * 900

    _patch_reduce(monkeypatch, 1000, fake_chat)
    items = _items(60, filler=90)
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))
    assert out == summarizer._combine_sections(items)
    assert len(out) <= 1000


def test_reduce_runs_groups_concurrently_within_semaphore(monkeypatch):
    """중간 요약은 묶음끼리 동시에 부르되 LLM_SECTION_CONCURRENCY 를 넘지 않는다."""
    state = {"active": 0, "peak": 0}

    async def fake_chat(system, user, params, timeout):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.02)
        state["active"] -= 1
        return "중간"

    _patch_reduce(monkeypatch, 1000, fake_chat, concurrency=2)
    asyncio.run(summarizer.reduce_section_summaries("제목", "저자", _items(60)))
    assert state["peak"] == 2


def test_reduce_pairs_up_large_summaries(monkeypatch):
    """섹션 요약이 커서 고르게 나누면 하나짜리 묶음만 생길 때도 둘 이상씩 묶어 실제로 줄인다
    (하나짜리 묶음은 다시 요약해도 줄지 않아, 그대로 두면 2단계 뒤 균등 샘플링으로 떨어진다)."""
    async def fake_chat(system, user, params, timeout):
        return "중" * 1000

    _patch_reduce(monkeypatch, 14000, fake_chat)
    items = ["가" * 6000, "나" * 6000, "다" * 6000]         # 18,000자 > 14,000
    groups = summarizer._group_for_reduce([(i + 1, i + 1, s) for i, s in enumerate(items)], 14000)
    assert any(len(g) >= 2 for g in groups)
    out = asyncio.run(summarizer.reduce_section_summaries("제목", "저자", items))
    assert len(out) <= 14000 and "중" * 1000 in out
    assert out != summarizer._combine_sections(items)      # 샘플링으로 떨어지지 않았다
```

`app/tests/test_prompts.py` 맨 위 `import textwrap` 앞 줄에 `import re` 를 넣고(이미 있으면 그대로), 파일 끝에 붙인다.

```python
def test_section_group_summary_prompt_renders_without_count_examples():
    """계층 요약 중간 요약 프롬프트(round07 Task 8) — doc_type 변형 없이 기본 파일 하나를 쓰고,
    StrictUndefined 렌더가 호출부 변수(title·author·section_summaries)와 맞는다.
    함정 15(LLM 은 프롬프트 예시의 개수를 베낀다) — 'N개'·'N가지' 같은 개수 예시를 넣지 않는다."""
    real_dir = Path(__file__).resolve().parents[1] / "domains" / "nl_library" / "prompts"
    lib = PromptLibrary(real_dir)
    for dt in (None, "paper", "book", "literature", "policy"):
        tpl = lib.get("section_group_summary", doc_type=dt)
        system, user, params = tpl.render(
            title="제목", author="저자", section_summaries="[섹션 1] 묶음내용\n\n[섹션 2] 다음내용")
        assert "제목" in user and "저자" in user and "묶음내용" in user and "다음내용" in user
        assert tpl.parser == "plain" and params.get("max_tokens")
        assert not re.search(r"\d+\s*(개|가지)", system + user)
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_summarizer.py tests/test_prompts.py -q`
Expected: `8 failed, 17 passed` — 새 `test_reduce_*` 7개가 `AttributeError: module 'services.ingestion.summarizer' has no attribute 'reduce_section_summaries'`(1개는 `'_group_for_reduce'`), 프롬프트 테스트가 `FileNotFoundError: 프롬프트 템플릿 없음 … section_group_summary.yaml`. 기존 17개는 통과.

- [ ] **Step 3: 구현**

`app/domains/nl_library/prompts/section_group_summary.yaml` 을 새로 만든다.

```yaml
parser: plain
params:
  max_tokens: 2048
  temperature: 0.1
system: |-
  당신은 문헌 요약 전문가입니다.
  한 자료의 연속된 섹션 요약들을 하나의 중간 요약으로 통합하세요.
  이 중간 요약은 다른 구간의 중간 요약들과 함께 자료 전체 요약의 입력으로 쓰입니다.
  - 섹션의 원래 순서와 흐름을 유지하세요
  - 각 섹션의 핵심 주제·주장·결과를 빠뜨리지 말고, 겹치는 내용은 합치세요
  - 주요 수치·통계·고유명사·핵심 용어는 가능한 한 그대로 남기세요
  - 원문에 없는 내용, 감상·평가·홍보성 표현은 넣지 마세요
  - 소제목·번호·글머리표나 [섹션 …] 같은 표시 없이 이어지는 문단으로 쓰세요
  1,000자 내외로 작성하고, 요약 외 다른 말은 하지 마세요.
user: |-
  자료명: {{ title }}
  저자/기관: {{ author }}

  [연속된 섹션 요약]
  {{ section_summaries }}

  위 섹션 요약들을 하나의 중간 요약으로 통합하세요.
```

`app/services/ingestion/summarizer.py` 맨 위 import 의 `import logging` 앞 줄에 `import asyncio` 를 넣는다. 그리고 `_combine_sections` 함수 전체(126-149행)

```python
def _combine_sections(section_summaries: list[str]) -> str:
    """섹션 요약들을 합친다. 상한 초과 시 앞부분만 자르지 않고 책 전체에 걸쳐
    균등 샘플링하여(앞·중간·뒤 고루) 전체 맥락을 보존한다.
    """
    items = [s for s in section_summaries if s]
    if not items:
        return ""

    def _join(seq: list[str]) -> str:
        return "\n\n".join(f"[섹션 {i + 1}] {s}" for i, s in enumerate(seq))

    full = _join(items)
    cap = get_settings().SUMMARIZER_MAX_INPUT_CHARS
    if not cap or len(full) <= cap:
        return full

    # 초과 → 균등 간격으로 섹션 샘플링 (순서 유지). 앞에서 자르면 후반부가 통째로 누락됨.
    avg = max(1, len(full) // len(items))
    keep = max(1, cap // avg)
    if keep >= len(items):
        return full[:cap]
    step = len(items) / keep
    picked = [items[min(len(items) - 1, int(i * step))] for i in range(keep)]
    return _join(picked)[:cap]  # 최종 안전 가드
```

를 아래로 바꾼다(`_combine_sections` 의 동작은 그대로 — 안쪽 `_join` 을 `_join_sections` 로 꺼냈을 뿐이다).

```python
def _join_sections(seq: list[str]) -> str:
    return "\n\n".join(f"[섹션 {i + 1}] {s}" for i, s in enumerate(seq))


def _combine_sections(section_summaries: list[str]) -> str:
    """섹션 요약들을 합친다. 상한 초과 시 앞부분만 자르지 않고 책 전체에 걸쳐
    균등 샘플링하여(앞·중간·뒤 고루) 전체 맥락을 보존한다.
    (샘플링은 버려지는 섹션이 생긴다 — 마무리 단계는 reduce_section_summaries 로 상한 안까지
    줄인 입력을 쓰고, 여기 샘플링은 그것마저 실패했을 때의 최후 가드다.)
    """
    items = [s for s in section_summaries if s]
    if not items:
        return ""

    full = _join_sections(items)
    cap = get_settings().SUMMARIZER_MAX_INPUT_CHARS
    if not cap or len(full) <= cap:
        return full

    # 초과 → 균등 간격으로 섹션 샘플링 (순서 유지). 앞에서 자르면 후반부가 통째로 누락됨.
    avg = max(1, len(full) // len(items))
    keep = max(1, cap // avg)
    if keep >= len(items):
        return full[:cap]
    step = len(items) / keep
    picked = [items[min(len(items) - 1, int(i * step))] for i in range(keep)]
    return _join_sections(picked)[:cap]  # 최종 안전 가드


# ── 계층 요약 (nanet 746744e 이식) ──────────────────────────────
# 섹션 요약을 이어 붙인 길이가 SUMMARIZER_MAX_INPUT_CHARS 를 넘으면 _combine_sections 는 균등
# 샘플링으로 일부 섹션을 버린다(마지막 섹션이 늘 빠진다). 그 전에 연속한 섹션 요약을 묶어
# 묶음마다 중간 요약을 만들고, 중간 요약을 이어 붙여 문서 요약·소개글의 입력으로 쓴다.
_REDUCE_MAX_LEVELS = 2
# 중간 요약 1개의 예상 분량(글자). 프롬프트 목표는 1,000자 내외지만 넘겨 쓰는 경우가 있어
# 여유를 둔다 — 묶음 수 × 이 값이 상한을 넘지 않게 묶음 수를 정한다.
_INTERMEDIATE_EXPECTED_CHARS = 1500
# 묶음 1개의 최소 입력 분량(글자, 섹션 요약 열 개 남짓). 이보다 잘게 나누면 중간 요약이
# 입력과 길이가 비슷해져 줄지 않고 LLM 호출만 는다.
_MIN_GROUP_CHARS = 3000
# "[섹션 123~456] " 라벨과 블록 사이 빈 줄 몫(묶음 수 계산용 여유분)
_BLOCK_OVERHEAD = 18


def _block_label(first: int, last: int) -> str:
    return f"섹션 {first}" if first == last else f"섹션 {first}~{last}"


def _join_blocks(blocks: list[tuple[int, int, str]]) -> str:
    """(첫 섹션 번호, 끝 섹션 번호, 요약) 블록을 "[섹션 3] …" / "[섹션 1~12] …" 로 빈 줄을 두고 잇는다.
    섹션 하나짜리 블록만 있으면 _join_sections 와 같은 텍스트다."""
    return "\n\n".join(f"[{_block_label(a, b)}] {s}" for a, b, s in blocks)


def _group_for_reduce(
    blocks: list[tuple[int, int, str]], cap: int,
) -> list[list[tuple[int, int, str]]]:
    """연속한 블록을 이어 붙인 길이가 cap 이하인 묶음으로 나눈다 — 필요한 만큼만 압축한다.

    묶음을 적게 만들면(예: 2개) 상한을 살짝 넘은 문서도 최종 입력이 확 줄어 요약이 빈약해진다.
    그래서 중간 요약들을 이어 붙여도 cap 안에 드는 범위에서 묶음을 되도록 많이 만들되, 묶음당
    최소 분량과 블록 2개 이상(하나짜리는 다시 요약해도 줄지 않는다)을 지킨다. 누적 분량을 n 등분해
    블록 가운데 지점이 떨어지는 구간에 배정하므로(순서 유지) 마지막 묶음만 자투리가 되지 않는다.
    """
    sizes = [len(_join_blocks([b])) + 2 for b in blocks]    # + 블록 사이 "\n\n"
    total = sum(sizes)
    n_needed = -(-total // cap)                              # 묶음 하나가 cap 을 넘지 않을 최소 개수
    n_fit = cap // (_INTERMEDIATE_EXPECTED_CHARS + _BLOCK_OVERHEAD)
    n_groups = max(n_needed, min(n_fit, total // _MIN_GROUP_CHARS, len(blocks) // 2), 1)

    buckets: list[list[tuple[tuple[int, int, str], int]]] = [[] for _ in range(n_groups)]
    cum = 0
    for b, size in zip(blocks, sizes):
        buckets[min(n_groups - 1, int((cum + size / 2) * n_groups / total))].append((b, size))
        cum += size

    # 블록 길이가 들쭉날쭉해 cap 을 넘은 묶음(드물다)은 그 묶음만 cap 단위로 한 번 더 나눈다.
    groups: list[list[tuple[int, int, str]]] = []
    for bucket in buckets:
        cur: list[tuple[int, int, str]] = []
        cur_len = 0
        for b, size in bucket:
            if cur and cur_len + size > cap:
                groups.append(cur)
                cur, cur_len = [], 0
            cur.append(b)
            cur_len += size
        if cur:
            groups.append(cur)
    return groups


async def reduce_section_summaries(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
) -> str:
    """문서 요약·소개글·줄거리·독후 효과가 함께 쓸 섹션 요약 입력을 만든다 (2단계 계층 요약).

    - 이어 붙인 길이가 SUMMARIZER_MAX_INPUT_CHARS 이하면 LLM 호출 없이 _combine_sections 와
      같은 텍스트를 돌려준다 — 대부분의 문서는 지금과 같다.
    - 넘으면 섹션 요약을 순서대로 상한 안의 묶음으로 나눠 묶음마다 중간 요약(section_group_summary
      프롬프트)을 만들고 "[섹션 1~12] …" 처럼 이어 붙인다. 묶음끼리는 동시에 부르되 동시 호출은
      LLM_SECTION_CONCURRENCY 까지다. 이어 붙여도 넘으면 한 단계 더 묶는다(최대 2단계).
    - 2단계 뒤에도 넘거나 중간 요약이 하나라도 실패하면(예외·빈 응답) 지금의 균등 샘플링
      (_combine_sections)으로 돌아간다.
    """
    items = [s for s in section_summaries if s]
    if not items:
        return ""
    cfg = get_settings()
    cap = cfg.SUMMARIZER_MAX_INPUT_CHARS
    blocks = [(i + 1, i + 1, s) for i, s in enumerate(items)]
    if not cap or len(_join_blocks(blocks)) <= cap:
        return _combine_sections(items)

    tpl = get_prompt("section_group_summary", _normalize_doc_type(doc_type))
    sem = asyncio.Semaphore(max(1, cfg.LLM_SECTION_CONCURRENCY))

    async def _reduce_group(group: list[tuple[int, int, str]]) -> tuple[int, int, str] | None:
        first, last = group[0][0], group[-1][1]
        if len(group) == 1:          # 하나짜리는 다시 요약해도 줄 게 없다 — 그대로 둔다
            return group[0]
        system, user, params = tpl.render(
            title=title, author=author or "미상", section_summaries=_join_blocks(group),
        )
        try:
            async with sem:
                raw = await _chat_completion(
                    system, user, params, timeout=cfg.SUMMARIZER_BOOK_TIMEOUT,
                )
        except Exception as e:
            log.warning(f"[{title[:40]}] 중간 요약 실패({_block_label(first, last)}): "
                        f"{str(e) or type(e).__name__}")
            return None
        summary = (_parse_llm_output(tpl, raw)[0] or "").strip()
        if not summary:
            log.warning(f"[{title[:40]}] 중간 요약 빈 응답({_block_label(first, last)})")
            return None
        return first, last, summary

    for level in range(1, _REDUCE_MAX_LEVELS + 1):
        before = len(_join_blocks(blocks))
        groups = _group_for_reduce(blocks, cap)
        results = await asyncio.gather(*(_reduce_group(g) for g in groups))
        if any(r is None for r in results):
            log.warning(f"[{title[:40]}] 중간 요약 {level}단계 실패 — 균등 샘플링으로 대신한다")
            return _combine_sections(items)
        blocks = list(results)
        joined = _join_blocks(blocks)
        log.info(f"[{title[:40]}] 중간 요약 {level}단계: 묶음 {len(groups)}개, "
                 f"{before}자 → {len(joined)}자 (상한 {cap}자)")
        if len(joined) <= cap:
            return joined
    log.warning(f"[{title[:40]}] 중간 요약 {_REDUCE_MAX_LEVELS}단계 뒤에도 상한 {cap}자 초과 — "
                f"균등 샘플링으로 대신한다")
    return _combine_sections(items)
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_summarizer.py tests/test_prompts.py -q`
Expected: `25 passed`

- [ ] **Step 5: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: `failed` 0, 수집 오류 3(기존). passed 가 직전 커밋보다 8 늘어난다(사본에서 898 → 906).

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/services/ingestion/summarizer.py app/domains/nl_library/prompts/section_group_summary.yaml app/tests/test_summarizer.py app/tests/test_prompts.py
git commit -m "[Feat] round07 — 계층 요약 reduce_section_summaries(nanet 746744e 이식): 섹션 요약을 이어 붙여 SUMMARIZER_MAX_INPUT_CHARS 를 넘으면 균등 샘플링으로 섹션을 버리는 대신 연속 섹션을 묶어 중간 요약(section_group_summary 프롬프트, 개수 예시 없음)을 묶음끼리 동시에(LLM_SECTION_CONCURRENCY) 만들고 '[섹션 1~12] …' 로 잇는다. 넘으면 한 단계 더(최대 2단계), 그래도 넘거나 중간 요약이 실패하면 지금의 균등 샘플링. 상한 이하는 _combine_sections 와 같은 텍스트. 묶음은 블록 둘 이상씩 — 하나짜리는 줄지 않는다"
```

#### 8-2: 생성 함수 네 개에 `combined_text` — 미리 합친 입력을 받는다

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_summarizer.py` 끝에 붙인다.

```python
# ── combined_text — 마무리 단계가 한 번 만든 입력을 넷이 같이 쓴다 (round07 Task 8) ──────
class _AllCfg(_FakeCfg):
    def __init__(self, cap):
        super().__init__(cap)
        self.SUMMARIZER_BOOK_TIMEOUT = 120
        self.SUMMARIZER_INTRO_TIMEOUT = 120


def test_generators_use_given_combined_text(monkeypatch):
    """combined_text 를 주면 _combine_sections 를 다시 부르지 않고 그 입력을 프롬프트에 넣는다."""
    users = []

    async def fake_chat(system, user, params, timeout):
        users.append(user)
        return "본문"

    def no_combine(_):
        raise AssertionError("combined_text 가 있는데 _combine_sections 를 불렀다")

    monkeypatch.setattr(summarizer, "get_settings", lambda: _AllCfg(10000))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", lambda name, doc_type=None: _FakeTpl())
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)
    monkeypatch.setattr(summarizer, "_combine_sections", no_combine)

    given = "[섹션 1~40] 미리 합친 입력"
    sums = ["섹션 요약"]
    asyncio.run(summarizer.summarize_book_from_sections("제목", "저자", sums, "book", combined_text=given))
    asyncio.run(summarizer.generate_book_introduction("제목", "저자", "출판사", "2020", sums, "book", combined_text=given))
    asyncio.run(summarizer.generate_book_plot("제목", "저자", sums, "book", combined_text=given))
    asyncio.run(summarizer.generate_read_effect("제목", "저자", sums, "book", combined_text=given))
    assert len(users) == 4 and all(given in u for u in users)


def test_generators_without_combined_text_still_combine(monkeypatch):
    """combined_text 없이 부르는 기존 호출(백필 태스크)은 지금처럼 _combine_sections 로 합친다."""
    users = []

    async def fake_chat(system, user, params, timeout):
        users.append(user)
        return "본문"

    monkeypatch.setattr(summarizer, "get_settings", lambda: _AllCfg(10000))
    monkeypatch.setattr(summarizer, "_normalize_doc_type", lambda d: d or "book")
    monkeypatch.setattr(summarizer, "get_prompt", lambda name, doc_type=None: _FakeTpl())
    monkeypatch.setattr(summarizer, "_chat_completion", fake_chat)

    asyncio.run(summarizer.generate_book_introduction(
        title="제목", author="저자", publisher="출판사", pub_date="2020",
        section_summaries=["가나다", "라마바"], doc_type="book",
    ))
    asyncio.run(summarizer.summarize_book_from_sections(
        title="제목", author="저자", section_summaries=["가나다", "라마바"], doc_type="book",
    ))
    assert users == ["user::[섹션 1] 가나다\n\n[섹션 2] 라마바"] * 2
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_summarizer.py -q`
Expected: `1 failed, 19 passed` — `test_generators_use_given_combined_text` 가 `TypeError: summarize_book_from_sections() got an unexpected keyword argument 'combined_text'`. `test_generators_without_combined_text_still_combine` 는 지금도 통과한다(백필 같은 기존 호출을 지키는 가드).

- [ ] **Step 3: 구현** (`app/services/ingestion/summarizer.py` — 8-1 이 끝난 상태에서 함수 머리 네 곳)

`generate_book_introduction`:

```python
async def generate_book_introduction(
    title: str,
    author: str,
    publisher: str,
    pub_date: str,
    section_summaries: list[str],
    doc_type: str = "book",
) -> str | None:
    """도서/논문 소개글 생성 (doc_type별 프롬프트 — paper는 학술 톤). 실패 시 None 반환."""
    if not section_summaries:
        return None
    combined = _combine_sections(section_summaries)
```

→

```python
async def generate_book_introduction(
    title: str,
    author: str,
    publisher: str,
    pub_date: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> str | None:
    """도서/논문 소개글 생성 (doc_type별 프롬프트 — paper는 학술 톤). 실패 시 None 반환.

    combined_text 를 주면(마무리 단계가 reduce_section_summaries 로 한 번 만든 입력) 그대로 쓰고,
    없으면 section_summaries 를 _combine_sections 로 합친다(백필 등 기존 호출).
    """
    if not section_summaries and not combined_text:
        return None
    combined = combined_text or _combine_sections(section_summaries)
```

`generate_read_effect`:

```python
async def generate_read_effect(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
) -> str | None:
    """독후 효과(read_effect) 생성 — 인덱싱 시 사전 저장용. 실패 시 None 반환.

    doc_type 별 프롬프트(read_effect.{doc_type}.yaml)로 분기한다.
    """
    if not section_summaries:
        return None
    combined = _combine_sections(section_summaries)
```

→

```python
async def generate_read_effect(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> str | None:
    """독후 효과(read_effect) 생성 — 인덱싱 시 사전 저장용. 실패 시 None 반환.

    doc_type 별 프롬프트(read_effect.{doc_type}.yaml)로 분기한다.
    combined_text 를 주면 _combine_sections 대신 그 입력을 쓴다(generate_book_introduction 참고).
    """
    if not section_summaries and not combined_text:
        return None
    combined = combined_text or _combine_sections(section_summaries)
```

`generate_book_plot`:

```python
async def generate_book_plot(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
) -> str | None:
    """도서 줄거리(plot) 생성 — 인덱싱 시 사전 저장용. 실패 시 None 반환.

    doc_type 별 프롬프트(plot.{doc_type}.yaml)로 분기한다.
    introduction 과 동일하게 균등 샘플링된 섹션 요약을 입력으로 받는다.
    """
    if not section_summaries:
        return None
    combined = _combine_sections(section_summaries)
```

→

```python
async def generate_book_plot(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> str | None:
    """도서 줄거리(plot) 생성 — 인덱싱 시 사전 저장용. 실패 시 None 반환.

    doc_type 별 프롬프트(plot.{doc_type}.yaml)로 분기한다.
    introduction 과 같은 입력을 받는다 — combined_text 가 있으면 그것, 없으면 _combine_sections.
    """
    if not section_summaries and not combined_text:
        return None
    combined = combined_text or _combine_sections(section_summaries)
```

`summarize_book_from_sections`:

```python
async def summarize_book_from_sections(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
) -> tuple[str, list[str]]:
    """전체 도서 요약 + 테마 키워드 생성. returns (summary, themes)."""
    combined = _combine_sections(section_summaries)
```

→

```python
async def summarize_book_from_sections(
    title: str,
    author: str,
    section_summaries: list[str],
    doc_type: str = "book",
    *,
    combined_text: str | None = None,
) -> tuple[str, list[str]]:
    """전체 도서 요약 + 테마 키워드 생성. returns (summary, themes).

    combined_text 를 주면 _combine_sections 대신 그 입력을 쓴다(generate_book_introduction 참고).
    """
    combined = combined_text or _combine_sections(section_summaries)
```

각 함수의 나머지(프롬프트 렌더·LLM 호출)는 그대로다.

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_summarizer.py tests/test_backfill_summary.py -q`
Expected: `23 passed`

- [ ] **Step 5: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: `failed` 0, 수집 오류 3(기존). passed 가 직전 커밋보다 2 늘어난다(사본에서 906 → 908).

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/services/ingestion/summarizer.py app/tests/test_summarizer.py
git commit -m "[Feat] round07 — 문서 요약·소개글·줄거리·독후 효과 생성 함수에 combined_text 키워드 인자: 마무리 단계가 한 번 만든 계층 요약 입력을 넷이 같이 쓴다. 없으면 지금처럼 _combine_sections(백필 태스크 등 기존 호출은 그대로)"
```

#### 8-3: `run_finalize` — 계층 요약 입력 공유·동시 호출·논문 표지 끄기

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_run_finalize.py` 를 새로 만든다.

```python
"""stages.run_finalize — 계층 요약 입력 공유·LLM 동시 호출·논문 표지 끄기 (round07 Task 8).

DB 세션·MinIO·LLM 생성 함수를 대역으로 바꿔 마무리 단계의 흐름만 본다.
생성 함수는 run_finalize 가 함수 안에서 import 하므로 summarizer 모듈 속성을 바꿔 둔다.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import services.ingestion.cover_generator as cover_generator
from services.ingestion import stages, summarizer
from services.ingestion.stages import StageContext

COMBINED = "[섹션 1~3] 계층 요약으로 합친 입력"
SUMMARIES = ["섹션1 요약", "섹션2 요약", "섹션3 요약"]


def _book(doc_type):
    return SimpleNamespace(
        cnts_id="B1", title="제목", personal_author="저자", corporate_author=None,
        publisher="출판사", pub_date="2020", kdc="800", doc_type=doc_type, extra={},
        summary=None, themes=None, introduction=None, cover_image_key=None, cover_prompt=None,
        is_embedded=False,
    )


def _patch(monkeypatch, book, *, concurrency=4, fail=(), reduce_error=None):
    """DB·MinIO·생성 함수 대역. state 에 호출 이름·받은 combined_text·최대 동시 실행 수를 모은다."""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = book
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
        (s,) for s in SUMMARIES
    ]
    monkeypatch.setattr(stages, "SyncSessionLocal", lambda: session)
    monkeypatch.setattr(stages, "minio_client", lambda: MagicMock())
    monkeypatch.setattr(stages, "delete_artifact", lambda book_id, client: None)
    monkeypatch.setattr("sqlalchemy.orm.attributes.flag_modified", lambda obj, key: None)
    monkeypatch.setattr(stages.cfg, "LLM_SECTION_CONCURRENCY", concurrency)

    state = {"active": 0, "peak": 0, "calls": [], "combined": [], "cover": 0}

    async def _run(name, combined_text, value):
        state["calls"].append(name)
        state["combined"].append(combined_text)
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.05)
        state["active"] -= 1
        if name in fail:
            raise RuntimeError(f"{name} LLM 실패")
        return value

    async def fake_reduce(title, author, section_summaries, doc_type="book"):
        state["reduce_args"] = (title, author, list(section_summaries), doc_type)
        if reduce_error:
            raise reduce_error
        return COMBINED

    async def fake_summary(title, author, section_summaries, doc_type="book", *, combined_text=None):
        return await _run("summary", combined_text, ("문서 요약", ["테마1", "테마2"]))

    async def fake_intro(title, author, publisher, pub_date, section_summaries, doc_type="book", *,
                         combined_text=None):
        return await _run("introduction", combined_text, "소개글")

    async def fake_plot(title, author, section_summaries, doc_type="book", *, combined_text=None):
        return await _run("plot", combined_text, "줄거리")

    async def fake_read_effect(title, author, section_summaries, doc_type="book", *, combined_text=None):
        return await _run("read_effect", combined_text, "독후 효과")

    async def fake_cover(**kw):
        state["cover"] += 1
        return "covers/B1.jpg", "cover prompt"

    monkeypatch.setattr(summarizer, "reduce_section_summaries", fake_reduce, raising=False)
    monkeypatch.setattr(summarizer, "summarize_book_from_sections", fake_summary)
    monkeypatch.setattr(summarizer, "generate_book_introduction", fake_intro)
    monkeypatch.setattr(summarizer, "generate_book_plot", fake_plot)
    monkeypatch.setattr(summarizer, "generate_read_effect", fake_read_effect)
    monkeypatch.setattr(cover_generator, "generate_and_store_cover", fake_cover)
    return state


def test_book_texts_share_reduced_input_and_run_concurrently(monkeypatch):
    """도서: 계층 요약을 한 번 만들고, 요약·소개글·줄거리·독후 효과 넷이 그 입력으로 동시에 돈다."""
    book = _book("book")
    state = _patch(monkeypatch, book)

    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))

    assert state["reduce_args"] == ("제목", "저자", SUMMARIES, "book")
    assert sorted(state["calls"]) == ["introduction", "plot", "read_effect", "summary"]
    assert state["combined"] == [COMBINED] * 4
    assert state["peak"] == 4                                   # 차례로가 아니라 동시에
    assert book.summary == "문서 요약" and book.themes == "테마1, 테마2"
    assert book.introduction == "소개글"
    assert book.extra == {"plot": "줄거리", "read_effect": "독후 효과"}
    assert result == {"summary": True, "plot": True, "read_effect": True, "introduction": True, "cover": False}


def test_concurrency_stays_within_llm_section_concurrency(monkeypatch):
    """동시 호출은 요약 단계와 같은 LLM_SECTION_CONCURRENCY 까지 — gemma 자리 예산(celery-llm 4 × 4)."""
    state = _patch(monkeypatch, _book("book"), concurrency=2)
    stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["peak"] == 2 and len(state["calls"]) == 4


def test_paper_runs_summary_and_introduction_only(monkeypatch):
    """논문: 줄거리·독후 효과는 만들지 않고 요약·소개글 둘이 동시에 돈다."""
    state = _patch(monkeypatch, _book("paper"))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert sorted(state["calls"]) == ["introduction", "summary"]
    assert state["peak"] == 2
    assert result["plot"] is False and result["read_effect"] is False


def test_one_failed_call_does_not_drop_the_others(monkeypatch):
    """하나가 실패해도(경고 후 None) 나머지 결과는 그대로 저장한다 — 지금의 개별 try 와 같다."""
    book = _book("book")
    _patch(monkeypatch, book, fail=("introduction",))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert book.introduction is None
    assert book.summary == "문서 요약"
    assert book.extra == {"plot": "줄거리", "read_effect": "독후 효과"}
    assert result["introduction"] is False and result["summary"] is True


def test_reduce_failure_falls_back_to_each_generators_own_combine(monkeypatch):
    """계층 요약이 예외를 내면 combined_text=None 으로 넘겨 각 함수가 지금처럼 _combine_sections 로 합친다."""
    state = _patch(monkeypatch, _book("paper"), reduce_error=RuntimeError("프롬프트 없음"))
    result = stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["combined"] == [None, None]
    assert result["summary"] is True and result["introduction"] is True


def test_paper_skips_cover_even_without_skip_cover_param(monkeypatch):
    """논문은 잡 params 에 skip_cover 가 없어도 표지(프롬프트 LLM + FLUX)를 만들지 않는다(사용자 결정 2026-10-01)."""
    state = _patch(monkeypatch, _book("paper"))
    result = stages.run_finalize(StageContext(book_id="B1", params={}))
    assert state["cover"] == 0 and result["cover"] is False


def test_book_cover_follows_skip_cover_param(monkeypatch):
    """도서는 지금처럼 skip_cover 가 없으면 표지를 만들고, 있으면 건너뛴다."""
    book = _book("book")
    state = _patch(monkeypatch, book)
    result = stages.run_finalize(StageContext(book_id="B1", params={}))
    assert state["cover"] == 1 and result["cover"] is True
    assert book.cover_image_key == "covers/B1.jpg" and book.cover_prompt == "cover prompt"

    state = _patch(monkeypatch, _book("book"))
    stages.run_finalize(StageContext(book_id="B1", params={"skip_cover": True}))
    assert state["cover"] == 0
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_run_finalize.py -q`
Expected: `4 failed, 3 passed`
- `test_book_texts_share_reduced_input_and_run_concurrently` — `KeyError: 'reduce_args'`(계층 요약을 안 부른다)
- `test_concurrency_stays_within_llm_section_concurrency`·`test_paper_runs_summary_and_introduction_only` — `assert (1 == 2)`/`assert 1 == 2`(차례로 돌아 동시 실행이 1)
- `test_paper_skips_cover_even_without_skip_cover_param` — `assert (1 == 0)`(논문인데 표지를 부른다)
- 통과하는 3개(하나 실패해도 나머지 저장·계층 요약 실패 폴백·도서 표지 규칙)는 지금 동작을 지키는 가드다.

- [ ] **Step 3: 구현** (`app/services/ingestion/stages.py`)

모듈 docstring(8-9행)

```python
  run_finalize    : 문서 요약/소개글 LLM → library_catalog UPDATE
                    (skip_cover 파라미터로 FLUX 생략 — 썸네일은 API가 온디맨드 생성)
```

→

```python
  run_finalize    : 계층 요약 입력 1회 → 문서 요약/소개글(도서류는 줄거리·독후 효과도) LLM 동시 호출
                    → library_catalog UPDATE (skip_cover 파라미터 또는 논문이면 FLUX 표지 생략 —
                    썸네일은 API가 온디맨드 생성)
```

`run_finalize` 안의 import(689-694행)

```python
    from services.ingestion.summarizer import (
        summarize_book_from_sections,
        generate_book_introduction,
        generate_book_plot,
        generate_read_effect,
    )
```

→

```python
    from services.ingestion.summarizer import (
        reduce_section_summaries,
        summarize_book_from_sections,
        generate_book_introduction,
        generate_book_plot,
        generate_read_effect,
    )
```

생성 블록부터 표지 조건까지(722-760행)

```python
    book_summary = book_themes = book_introduction = book_plot = book_read_effect = None
    if valid_summaries:
        try:
            book_summary, themes_list = run_async(summarize_book_from_sections(
                title=title, author=author,
                section_summaries=valid_summaries, doc_type=doc_type,
            ))
            book_themes = ", ".join(themes_list) if themes_list else None
        except Exception as e:
            log.warning(f"[{book_id}] 도서 요약 생성 실패: {e}")

        try:
            book_introduction = run_async(generate_book_introduction(
                title=title, author=author, publisher=publisher,
                pub_date=pub_date, section_summaries=valid_summaries, doc_type=doc_type,
            ))
        except Exception as e:
            log.warning(f"[{book_id}] 도서 소개글 생성 실패: {e}")

        if doc_type in _GENERATE_EXTRA_DOC_TYPES:
            try:
                book_plot = run_async(generate_book_plot(
                    title=title, author=author,
                    section_summaries=valid_summaries, doc_type=doc_type,
                ))
            except Exception as e:
                log.warning(f"[{book_id}] 도서 줄거리 생성 실패: {e}")

            try:
                book_read_effect = run_async(generate_read_effect(
                    title=title, author=author,
                    section_summaries=valid_summaries, doc_type=doc_type,
                ))
            except Exception as e:
                log.warning(f"[{book_id}] 독후 효과 생성 실패: {e}")

    # 표지 생성 — 대량 논문 인덱싱에서는 skip_cover=true 로 생략 (썸네일 폴백 사용)
    cover_key = cover_prompt = None
    if not ctx.params.get("skip_cover"):
```

를 아래로 바꾼다. 표지 생성 본문(`try: … generate_and_store_cover …`)과 그 뒤 DB 저장·아티팩트 정리·반환값은 그대로다. `asyncio` 는 파일 맨 위에서 이미 import 한다.

```python
    async def _generate_texts() -> dict:
        # 계층 요약 입력을 한 번 만들어 넷이 같이 쓴다. 만들다 실패하면 None — 각 생성 함수가
        # 지금처럼 _combine_sections(균등 샘플링)로 합친다.
        try:
            combined = await reduce_section_summaries(title, author, valid_summaries, doc_type)
        except Exception as e:
            log.warning(f"[{book_id}] 계층 요약 실패 — 균등 샘플링 입력으로 진행: {e}")
            combined = None
        calls = {
            "summary": summarize_book_from_sections(
                title=title, author=author, section_summaries=valid_summaries,
                doc_type=doc_type, combined_text=combined,
            ),
            "introduction": generate_book_introduction(
                title=title, author=author, publisher=publisher, pub_date=pub_date,
                section_summaries=valid_summaries, doc_type=doc_type, combined_text=combined,
            ),
        }
        if doc_type in _GENERATE_EXTRA_DOC_TYPES:
            calls["plot"] = generate_book_plot(
                title=title, author=author, section_summaries=valid_summaries,
                doc_type=doc_type, combined_text=combined,
            )
            calls["read_effect"] = generate_read_effect(
                title=title, author=author, section_summaries=valid_summaries,
                doc_type=doc_type, combined_text=combined,
            )
        # 서로 기다릴 이유가 없는 호출들이라 한 이벤트 루프에서 동시에 보낸다(프로세스당 LLM 동시
        # 호출은 요약 단계와 같은 LLM_SECTION_CONCURRENCY 까지). 하나가 실패해도 나머지는 그대로
        # 받는다(return_exceptions) — 실패한 것만 아래에서 경고 후 None.
        sem = asyncio.Semaphore(max(1, cfg.LLM_SECTION_CONCURRENCY))

        async def _bounded(coro):
            async with sem:
                return await coro

        results = await asyncio.gather(*(_bounded(c) for c in calls.values()), return_exceptions=True)
        return dict(zip(calls, results))

    _FAILURE_LABELS = {
        "summary": "도서 요약", "introduction": "도서 소개글",
        "plot": "도서 줄거리", "read_effect": "독후 효과",
    }
    book_summary = book_themes = book_introduction = book_plot = book_read_effect = None
    if valid_summaries:
        texts = run_async(_generate_texts())
        for key, value in texts.items():
            if isinstance(value, BaseException):
                log.warning(f"[{book_id}] {_FAILURE_LABELS[key]} 생성 실패: {value}")
                texts[key] = None
        if texts["summary"] is not None:
            book_summary, themes_list = texts["summary"]
            book_themes = ", ".join(themes_list) if themes_list else None
        book_introduction = texts["introduction"]
        book_plot = texts.get("plot")
        book_read_effect = texts.get("read_effect")

    # 표지 생성 — skip_cover=true 이거나 논문이면 생략한다(썸네일 폴백 사용).
    # 논문은 표지를 만들지 않는다(사용자 결정 2026-10-01): 잡 params 에 skip_cover 가 빠져도
    # 논문마다 표지 프롬프트 LLM(+FLUX)을 부르지 않도록 doc_type 으로도 막는다.
    cover_key = cover_prompt = None
    if not ctx.params.get("skip_cover") and doc_type != "paper":
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_run_finalize.py tests/test_summarizer.py tests/test_embed_index_guard.py -q`
Expected: `31 passed`

- [ ] **Step 5: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`
Expected: `failed` 0, 수집 오류 3(기존). passed 가 직전 커밋보다 7 늘어난다(사본에서 908 → 915).

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07
git add app/services/ingestion/stages.py app/tests/test_run_finalize.py
git commit -m "[Feat] round07 — 마무리 병렬·논문 표지 끄기: run_finalize 가 계층 요약 입력을 한 번 만들고 문서 요약·소개글(도서류는 줄거리·독후 효과도)을 한 run_async 안에서 asyncio.gather 로 동시에 보낸다(LLM_SECTION_CONCURRENCY 까지, 실패는 하나씩 경고 후 None, 계층 요약 실패 시 각자 균등 샘플링). 논문은 skip_cover 가 없어도 표지(프롬프트 LLM + FLUX)를 만들지 않는다(사용자 결정 2026-10-01)"
```

### Task 7·8 이 다른 작업과 겹치는 곳

- `stages.py` 는 Task 2·4·6 도 고친다. 8-3 은 모듈 docstring 의 run_finalize 두 줄과 `run_finalize` 안만 바꾼다. 앞 작업이 docstring 의 같은 줄을 고쳤으면 위 old 블록 대신 그 줄의 지금 내용에 같은 뜻(계층 요약 1회·동시 호출·논문 표지 생략)을 반영한다. `StageContext.item_meta`(Task 2)는 기본값이 있어 테스트의 `StageContext(book_id=…, params=…)` 가 그대로 돈다.
- `LLM_SECTION_CONCURRENCY`: Task 6 이 요약 단계에서 섹션 요약과 보강이 나눠 쓰는 단계 세마포어를 만든다. 마무리는 따로 도는 태스크라 같은 값으로 자기 세마포어를 만든다 — 프로세스당 동시 LLM 상한이 두 단계에서 같다.
- `llm_client`(Task 1): 요약 쪽은 `_chat_completion` → `chat()` 만 쓴다. Task 1 의 재시도는 그대로 혜택을 받는다. 중간 요약이 `length` 로 잘려도 앞부분은 쓸모가 있어 `chat_full` 로 따로 다루지 않는다.
- `test_prompts.py`·`test_summarizer.py` 의 `import re`: 다른 작업(예: Task 6 의 표 해석 프롬프트 테스트)이 이미 넣었으면 다시 넣지 않는다.
- Task 4(섹션 0개 → 강제 OCR 재추출): 줄 모드는 본문이 상한(섹션 7,500자)을 넘을 때만 켜지므로, 지금 섹션 0개인 본문이 7-2 로 섹션을 얻는 경우는 '5자 이하 조각만 7,500자 넘게 있는 본문'뿐이다. 그 밖의 0개 판정은 그대로다.
- Task 11(실제 PDF 회귀): Task 7 근거의 비교(옛/새 `semantic_chunk` 지문, 631편)는 검증 사본에서 한 것이다. 같은 방식을 Task 11 의 research 스크립트에 넣으면 숫자를 다시 잴 수 있다.

---

### Task 9: 잡 조회 ETA·실패 대표 메시지

**왜:** spec 17번. 잡 조회의 ETA 는 최근 1시간 처리량으로 재서 48시간 기준의 0.73~5.7배로 출렁였고(진단 때 856시간), paused 잡도 ETA 를 냈으며(554시간), 남은 수에 다시는 처리되지 않는 영구 실패가 섞였다. `/failures` 의 대표 메시지는 `max(last_error)`(사전순 최댓값)라 `not_found` 545건('섹션 없음')이 15건뿐인 '카탈로그 row 없음'으로 보였다.

**Files:**
- Modify: `app/api/ingest_jobs.py` (모듈 머리 설명, import, 새 함수 `compute_eta`·`_done_since`·`_permanently_failed`·`_failure_groups`, `get_job`, `list_failures`)
- Create: `app/tests/test_ingest_jobs_api.py`

**알아 둘 것:**
- 응답은 키를 더하기만 한다. `rate_per_hour`(최근 1시간)는 그대로 두고 `rate_per_hour_24h`(최근 24시간 ÷ 24)와 `permanently_failed` 를 더한다. `remaining` 은 영구 실패를 뺀 값이 된다 — 그래서 `permanently_failed` 를 같이 내야 `done_total + remaining` 이 `total_items` 와 맞지 않는 까닭이 보인다.
- 영구 실패 = `status == 'failed'` 이고 `attempt >= max_attempts`(잡 `params.max_attempts`, 없으면 `INGEST_MAX_ATTEMPTS`). 디스패처(`_dispatch_for_job`)가 다시 집지 않는 조건과 같다. Task 2 가 `no_text` 를 시도 한도로 올리므로 그것도 여기 든다.
- ETA 는 `compute_eta(remaining, done_last_24h, status)` — paused 면 None, 남은 게 없으면 0.0, 24시간 처리량이 0 이면 None, 그 밖에는 `remaining × 24 ÷ done_last_24h`(시간, 소수 한 자리).
- 대표 메시지는 PostgreSQL `mode() WITHIN GROUP (ORDER BY last_error)`(`func.mode().within_group(...)`) — NULL 은 세지 않는다. 계획 작성 때 로컬 일회용 Postgres 16 컨테이너에 같은 표를 만들어 돌려 `not_found` 그룹이 '섹션 없음'을 대표로 내는 것을 봤다.
- 대시보드(`frontend/pages/admin/jobs.vue`)는 바꾸지 않는다. `remaining`·`eta_hours` 칸이 같은 키로 새 값을 보이고, "건/시간 (최근 1h)" 칸도 그대로 맞다.
- Postgres 가 로컬에 없다. 문장은 postgresql 방언으로 컴파일한 문자열로 확인하고, 엔드포인트는 문장을 SQL 로 구별해 정해 둔 값을 돌려주는 대역 세션으로 돌린다(코루틴을 `asyncio.run` 으로 직접 부른다).
- 기존 파일은 Edit 도구로 고친다(CRLF 유지).

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_ingest_jobs_api.py` (새 파일, 전체):

```python
"""api/ingest_jobs.py — 잡 조회의 처리량·ETA·남은 수, 실패 그룹의 대표 메시지.

Postgres 가 로컬에 없다. 문장은 postgresql 방언으로 컴파일한 문자열로 확인하고, 엔드포인트는
문장을 SQL 로 구별해 정해 둔 값을 돌려주는 대역 세션으로 돌린다.
"""
import asyncio
import datetime as _dt
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from api import ingest_jobs

JOB_ID = "1ca22f59-1e50-4dd1-81f5-2d3c79126825"


def _compiled(stmt):
    return stmt.compile(dialect=postgresql.dialect())


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return self._rows


class _FakeDB:
    """get_job·list_failures 가 보내는 문장을 SQL 로 구별해 정해 둔 값을 돌려준다."""

    def __init__(self, job=None, *, status_counts=None, done_1h=0, done_24h=0,
                 permanently_failed=0, failure_rows=None):
        self.job = job
        self.status_counts = status_counts or {}
        self.done_1h = done_1h
        self.done_24h = done_24h
        self.permanently_failed = permanently_failed
        self.failure_rows = failure_rows or []
        self.sql: list[str] = []
        self.attempt_limits: list[int] = []

    async def execute(self, stmt):
        compiled = _compiled(stmt)
        sql = str(compiled)
        self.sql.append(sql)
        if "FROM ingest_jobs" in sql:
            return _Result(scalar=self.job)
        if "WITHIN GROUP" in sql:
            return _Result(rows=self.failure_rows)
        if "GROUP BY ingest_job_items.status" in sql:
            return _Result(rows=list(self.status_counts.items()))
        if "GROUP BY ingest_job_items.stage" in sql or "extract_method" in sql:
            return _Result(rows=[])
        if "ingest_job_items.attempt >=" in sql:
            self.attempt_limits.append(compiled.params["attempt_1"])
            return _Result(scalar=self.permanently_failed)
        if "ingest_job_items.finished_at >=" in sql:
            since = compiled.params["finished_at_1"]
            hours = (_dt.datetime.now(_dt.timezone.utc) - since).total_seconds() / 3600
            return _Result(scalar=self.done_1h if hours < 2 else self.done_24h)
        raise AssertionError(f"대역이 모르는 문장: {sql}")


def _job(status="running", total_items=1000, params=None):
    return SimpleNamespace(
        id=uuid.UUID(JOB_ID), name="kci-full-236k", kind="paper_bulk", status=status,
        manifest_key="manifests/full/manifest.jsonl", params=params or {"reembed": True},
        total_items=total_items, validation_report=None,
        created_at=None, started_at=None, finished_at=None,
    )


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(
        ingest_jobs, "get_settings", lambda: SimpleNamespace(INGEST_MAX_ATTEMPTS=3), raising=False,
    )


class TestComputeEta:
    def test_uses_24h_throughput(self):
        # 24시간 480건 = 시간당 20건 → 남은 360건은 18시간
        assert ingest_jobs.compute_eta(360, 480, "running") == 18.0

    def test_paused_job_has_no_eta(self):
        assert ingest_jobs.compute_eta(360, 480, "paused") is None

    def test_no_throughput_has_no_eta(self):
        assert ingest_jobs.compute_eta(360, 0, "running") is None

    def test_nothing_left_is_zero(self):
        assert ingest_jobs.compute_eta(0, 0, "running") == 0.0


class TestJobDetail:
    def _get(self, db):
        return asyncio.run(ingest_jobs.get_job(JOB_ID, db=db))

    def test_rates_eta_and_remaining(self):
        db = _FakeDB(
            _job(total_items=1000),
            status_counts={"done": 600, "failed": 50, "pending": 350},
            done_1h=10, done_24h=480, permanently_failed=40,
        )
        out = self._get(db)
        assert out["rate_per_hour"] == 10          # 1시간 창은 그대로 둔다
        assert out["rate_per_hour_24h"] == 20.0
        assert out["permanently_failed"] == 40
        assert out["remaining"] == 1000 - 600 - 40  # 영구 실패는 더 처리되지 않는다
        assert out["eta_hours"] == 18.0             # 360 ÷ 20

    def test_paused_job_keeps_rates_but_no_eta(self):
        db = _FakeDB(_job(status="paused"), status_counts={"done": 600}, done_1h=10, done_24h=480)
        out = self._get(db)
        assert out["eta_hours"] is None
        assert out["rate_per_hour_24h"] == 20.0

    def test_permanent_failures_use_job_max_attempts(self):
        db = _FakeDB(_job(params={"reembed": True, "max_attempts": 5}), status_counts={"done": 1})
        self._get(db)
        assert db.attempt_limits == [5]

    def test_permanent_failures_default_to_setting(self):
        db = _FakeDB(_job(params={"reembed": True}), status_counts={"done": 1})
        self._get(db)
        assert db.attempt_limits == [3]


class TestFailureGroups:
    def test_sample_is_the_most_common_message(self):
        sql = str(_compiled(ingest_jobs._failure_groups(JOB_ID)))
        assert "mode() WITHIN GROUP (ORDER BY ingest_job_items.last_error)" in sql
        assert "max(" not in sql

    def test_endpoint_returns_groups(self):
        db = _FakeDB(failure_rows=[
            ("not_found", 560, "섹션 없음 — extract 단계부터 재실행 필요"),
            (None, 2, None),
        ])
        out = asyncio.run(ingest_jobs.list_failures(JOB_ID, db=db))
        assert out == {"groups": [
            {"error_group": "not_found", "count": 560, "sample_error": "섹션 없음 — extract 단계부터 재실행 필요"},
            {"error_group": "unknown", "count": 2, "sample_error": ""},
        ]}
        assert "mode() WITHIN GROUP" in db.sql[0]
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_ingest_jobs_api.py -q`

Expected: `10 failed`. 이유:
- `TestComputeEta` 4개 — `AttributeError: module 'api.ingest_jobs' has no attribute 'compute_eta'`
- `test_rates_eta_and_remaining` — `KeyError: 'rate_per_hour_24h'`
- `test_paused_job_keeps_rates_but_no_eta` — `assert 40.0 is None`(옛 코드는 1시간 창으로 ETA 를 낸다)
- `test_permanent_failures_use_job_max_attempts`·`test_permanent_failures_default_to_setting` — `assert [] == [5]`·`assert [] == [3]`(영구 실패를 세지 않는다)
- `test_sample_is_the_most_common_message` — `AttributeError: … no attribute '_failure_groups'`
- `test_endpoint_returns_groups` — `AssertionError: 대역이 모르는 문장: SELECT … max(ingest_job_items.last_error) …`

- [ ] **Step 3: `app/api/ingest_jobs.py` 구현**

`app/api/ingest_jobs.py` — 교체 전:

```python
GET    /api/admin/ingest-jobs/{id}       잡 상세 (stage/status 카운트, 처리율, ETA)
```

교체 후:

```python
GET    /api/admin/ingest-jobs/{id}       잡 상세 (stage/status 카운트, 처리율 1h·24h, ETA)
```

`app/api/ingest_jobs.py` — 교체 전:

```python
from core.deps import get_db
from models.ingest_job import IngestJob, IngestJobItem
```

교체 후:

```python
from core.config import get_settings
from core.deps import get_db
from models.ingest_job import IngestJob, IngestJobItem
```

`app/api/ingest_jobs.py` — 교체 전:

```python
# ── 상세 (카운트 + 처리율 + ETA) ──────────────────────────────
@router.get("/{job_id}")
```

교체 후:

```python
# ── 상세 (카운트 + 처리율 + ETA) ──────────────────────────────
def compute_eta(remaining: int, done_last_24h: int, status: str) -> float | None:
    """남은 건수 ÷ 최근 24시간의 시간당 처리량(시간). 멈춘 잡·처리량 0 이면 None.

    1시간 창은 스캔본(VLM)이 몰리면 처리량이 몇 분의 1로 떨어져 ETA 가 48시간 기준의
    0.73~5.7배로 출렁였다. 24시간 창은 두 구간(ODL·스캔본)이 섞여 덜 흔들린다.
    """
    if status == "paused":
        return None
    if remaining <= 0:
        return 0.0
    if done_last_24h <= 0:
        return None
    return round(remaining * 24 / done_last_24h, 1)


def _done_since(job_id: str, since: _dt.datetime):
    return select(func.count()).where(
        IngestJobItem.job_id == job_id,
        IngestJobItem.status == "done",
        IngestJobItem.finished_at >= since,
    )


def _permanently_failed(job_id: str, max_attempts: int):
    """자동 재시도 한도에 닿은 failed — 디스패처가 다시 집지 않는다(수동 retry 전까지)."""
    return select(func.count()).where(
        IngestJobItem.job_id == job_id,
        IngestJobItem.status == "failed",
        IngestJobItem.attempt >= max_attempts,
    )


@router.get("/{job_id}")
```

`app/api/ingest_jobs.py` — 교체 전:

```python
    # 처리율: 최근 1시간 done 건수 → 시간당 처리율
    one_hour_ago = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=1)
    done_last_hour = (await db.execute(
        select(func.count())
        .where(
            IngestJobItem.job_id == job_id,
            IngestJobItem.status == "done",
            IngestJobItem.finished_at >= one_hour_ago,
        )
    )).scalar() or 0

    done_total = status_counts.get("done", 0)
    remaining = job.total_items - done_total
    rate_per_hour = done_last_hour
    eta_hours = round(remaining / rate_per_hour, 1) if rate_per_hour > 0 else None
```

교체 후:

```python
    # 처리율: 최근 1시간·24시간 done 건수. ETA 는 24시간 기준(compute_eta)
    now = _dt.datetime.now(_dt.timezone.utc)
    done_last_hour = (await db.execute(
        _done_since(job_id, now - _dt.timedelta(hours=1))
    )).scalar() or 0
    done_last_24h = (await db.execute(
        _done_since(job_id, now - _dt.timedelta(hours=24))
    )).scalar() or 0

    # 영구 실패는 더 처리되지 않으므로 남은 수에서 뺀다
    params = dict(job.params or {})
    max_attempts = int(params.get("max_attempts") or get_settings().INGEST_MAX_ATTEMPTS)
    permanently_failed = (await db.execute(
        _permanently_failed(job_id, max_attempts)
    )).scalar() or 0

    done_total = status_counts.get("done", 0)
    remaining = job.total_items - done_total - permanently_failed
    rate_per_hour = done_last_hour
    rate_per_hour_24h = round(done_last_24h / 24, 1)
    eta_hours = compute_eta(remaining, done_last_24h, job.status)
```

`app/api/ingest_jobs.py` — 교체 전:

```python
        "done_total": done_total,
        "remaining": remaining,
        "rate_per_hour": rate_per_hour,
        "eta_hours": eta_hours,
```

교체 후:

```python
        "done_total": done_total,
        "permanently_failed": permanently_failed,
        "remaining": remaining,
        "rate_per_hour": rate_per_hour,
        "rate_per_hour_24h": rate_per_hour_24h,
        "eta_hours": eta_hours,
```

`app/api/ingest_jobs.py` — 교체 전:

```python
# ── 실패 그룹 집계 ────────────────────────────────────────────
@router.get("/{job_id}/failures")
async def list_failures(job_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            IngestJobItem.error_group,
            func.count(),
            func.max(IngestJobItem.last_error),
        )
        .where(IngestJobItem.job_id == job_id, IngestJobItem.status == "failed")
        .group_by(IngestJobItem.error_group)
        .order_by(func.count().desc())
    )).all()
```

교체 후:

```python
# ── 실패 그룹 집계 ────────────────────────────────────────────
def _failure_groups(job_id: str):
    # 대표 메시지는 그룹 안에서 가장 흔한 것(mode). max() 는 사전순 최댓값이라
    # not_found 545건('섹션 없음')이 15건뿐인 '카탈로그 row 없음'으로 보였다.
    return (
        select(
            IngestJobItem.error_group,
            func.count(),
            func.mode().within_group(IngestJobItem.last_error),
        )
        .where(IngestJobItem.job_id == job_id, IngestJobItem.status == "failed")
        .group_by(IngestJobItem.error_group)
        .order_by(func.count().desc())
    )


@router.get("/{job_id}/failures")
async def list_failures(job_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(_failure_groups(job_id))).all()
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_ingest_jobs_api.py -q`

Expected: `10 passed`

- [ ] **Step 5: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`

Expected: failed 0, errors 는 기존 수집 오류 3 그대로. passed 수는 앞 작업들이 더한 테스트에 따라 다르다 — Task 0 직후(897)에서 이 작업만 더하면 `907 passed, 2 warnings, 3 errors`.

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && git add app/api/ingest_jobs.py app/tests/test_ingest_jobs_api.py && git status --short && git commit -m "[Fix] round07 — 잡 조회 ETA·실패 대표 메시지: ETA 를 최근 24시간 처리량으로 계산하고(rate_per_hour 는 1시간 그대로 두고 rate_per_hour_24h 를 더한다) paused 잡은 ETA 를 내지 않는다. 남은 수에서 영구 실패(시도 한도에 닿은 failed)를 빼고 그 수를 permanently_failed 로 낸다. /failures 의 대표 메시지는 max(last_error) 대신 그룹 안에서 가장 흔한 메시지(mode() WITHIN GROUP)로 — not_found 545건 '섹션 없음'이 15건뿐인 '카탈로그 row 없음'으로 보이던 것"
```

---

### Task 10: 재처리·카나리 스크립트

**왜:** spec §4·§5. 배포 직후 빈 본문으로 완료된 문서(약 900건 추정)를 골라 추출부터 다시 돌리고, 본 잡을 재개하기 전에 문제 유형별 카나리 잡을 돌린다. 둘 다 서버에서 사람이 돌리는 운영 도구라 `scripts/bulk_ingest/` 에 둔다(CLAUDE.md §1 — 재실행되는 운영 도구).

**Files:**
- Create: `scripts/bulk_ingest/select_near_empty_items.py`
- Create: `scripts/bulk_ingest/build_canary_manifest.py`
- Modify: `scripts/bulk_ingest/README.md` (끝에 `## 5)` 절)
- Create: `app/tests/test_select_near_empty_items.py`
- Create: `app/tests/test_build_canary_manifest.py`

**읽고 맞춘 관례:**
- 실행: 앱 이미지에 `scripts/` 가 없다. 서버의 `/data/nl-lib/data/<디렉터리>/`(컨테이너 `/app/data/…`)에 복사해 `docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/…` 로 돌린다 — 경로로 실행하면 `sys.path[0]` 이 스크립트 디렉터리라 `PYTHONPATH=/app` 이 있어야 앱 모듈이 보인다(함정 4번, `scripts/recovery/*.py` 머리말과 같다).
- DB: `from db.postgres import SyncSessionLocal` + `sqlalchemy.text`. 앱 모듈은 **함수 안에서** import 한다 — 로컬 테스트는 `scripts/bulk_ingest` 를 `sys.path` 에 넣고 순수 함수만 import 한다(`test_build_manifest.py` 와 같은 방식). 트랜잭션 첫 문장을 `SET TRANSACTION READ ONLY` 로 둬 쓰기를 DB 가 막는다.
- 인자: `argparse`(`build_manifest.py` 와 같다).
- 매니페스트: `build_manifest.py` 와 같은 JSONL 한 줄 = 한 문서. 잡 생성(`job_manager._load_manifest` → `build_job_plan`)은 `book_id`·`object_key` 만 읽는다.
- SQL: 바인드 뒤 `::` 캐스트를 쓰지 않는다(함정 7번 — `CAST(:p AS type)`). `meta ->> 'x'` 의 숫자 캐스트는 `CASE WHEN jsonb_typeof(meta -> 'x') = 'number' THEN … END` 로 감싼다(문자열 값이 섞여도 캐스트 오류가 안 난다). 표본은 id 순 앞부분이 아니다(함정 11번 — seed 해시 순).
- 운영에 쓰지 않는다: MinIO 업로드·잡 생성·시작·retry 는 명령만 출력한다.

**선정 규칙:**
- `select_near_empty_items.py` — done 이고 `meta.pages >= 8` 이며 쪽당 본문 글자 수(`book_sections.full_text` 의 `length()` 합 ÷ `pages`)가 150 미만. 청크 수 기준은 쓰지 않는다(표 하나짜리 정상 문서가 섞인다). `length()` 는 TOAST 된 본문을 풀어야 해서, 풀지 않고 크기를 아는 `octet_length()`(바이트)로 먼저 거른다 — UTF-8 한 글자는 1~4바이트라 바이트가 쪽당 기준 × 4 이상이면 글자가 기준 미만일 수 없다. `--finished-before`(시간대 필수)로 배포 전에 끝난 것만 고른다. 출력은 CSV(사람이 본다)와 retry API 본문 그대로인 JSON(`{"item_ids": […], "reset_stage": "pending"}`), 요약(건수·UTC 완료 날짜별 건수).
- `build_canary_manifest.py` — 범주와 몫, 앞선 범주가 우선: `scan_no_sections` 20(failed·`not_found`·`last_error` 가 '섹션 없음'으로 시작), `many_tables` 10(done·`n_tables >= 5`), `dense_chunks` 5(done·`chunks / pages > 6`), `many_sections` 5(done·`sections_total > 40`), `normal` 10(done·나머지). 범주 안에서는 `md5(book_id || seed)` 순 — SQL 이 같은 순서로 범주마다 몫 × `--oversample`(기본 20)건까지만 읽고, 순수 함수 `pick_canary` 가 같은 키로 다시 정렬해 고른다. 같은 seed 면 다시 돌려도 같은 50건이다. `object_key` 는 본 잡 아이템의 `source_key` 를 그대로 쓴다(본 잡을 만들 때 MinIO 에 있음을 확인한 키). 출력하는 다음 명령은 MinIO 업로드(`nl-lib-fastapi` 안의 `minio_client().fput_object`), 잡 생성(`params: {"reembed": true, "skip_cover": true}` — 완료분도 다시 돌리므로 `reembed`), 시작.
- 두 SQL 은 계획 작성 때 로컬 일회용 Postgres 16 에 같은 표(`ingest_jobs`·`ingest_job_items`·`book_sections`)를 만들어 돌려 봤다 — 문자열 `pages` 는 CASE 가 걸렀고, `CAST(:before AS timestamptz)` 가 NULL·시각 둘 다 됐고, SQL 의 `md5()` 가 `order_key` 와 같은 값을 냈다.

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_select_near_empty_items.py` (새 파일, 전체):

```python
"""scripts/bulk_ingest/select_near_empty_items.py — 빈 본문 완료 아이템 선정 규칙·출력."""
import csv
import datetime as _dt
import json
import re
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "bulk_ingest"
sys.path.insert(0, str(SCRIPTS_DIR))

UTC = _dt.timezone.utc
KST = _dt.timezone(_dt.timedelta(hours=9))


def _row(item_id, pages, body_chars, finished_at=None):
    return {
        "item_id": item_id, "book_id": f"KCI_FI{item_id:09d}", "pages": pages,
        "body_chars": body_chars,
        "finished_at": finished_at or _dt.datetime(2026, 9, 3, 4, 0, tzinfo=UTC),
    }


def test_selects_long_documents_below_threshold():
    from select_near_empty_items import select_near_empty

    rows = [
        _row(1, pages=10, body_chars=1000),   # 100자/쪽 — 고른다
        _row(2, pages=10, body_chars=1500),   # 150자/쪽 — 기준과 같으면 고르지 않는다
        _row(3, pages=7, body_chars=0),       # 8쪽 미만은 대상이 아니다
        _row(4, pages=8, body_chars=0),       # 본문 0 — 고른다
    ]
    picked = select_near_empty(rows, min_pages=8, max_chars_per_page=150)
    assert [r["item_id"] for r in picked] == [4, 1]       # 쪽당 글자 수 오름차순
    assert [r["chars_per_page"] for r in picked] == [0.0, 100.0]


def test_chars_per_page_is_rounded():
    from select_near_empty_items import select_near_empty

    [picked] = select_near_empty([_row(1, pages=30, body_chars=1001)], min_pages=8, max_chars_per_page=150)
    assert picked["chars_per_page"] == 33.4


def test_finished_by_day_uses_utc_dates():
    from select_near_empty_items import finished_by_day

    rows = [
        _row(1, 10, 0, _dt.datetime(2026, 9, 3, 8, 30, tzinfo=KST)),   # UTC 09-02 23:30
        _row(2, 10, 0, _dt.datetime(2026, 9, 3, 2, 0, tzinfo=UTC)),
        _row(3, 10, 0, _dt.datetime(2026, 9, 3, 7, 59, tzinfo=UTC)),
    ]
    assert finished_by_day(rows) == [("2026-09-02", 1), ("2026-09-03", 2)]


def test_retry_body_is_what_the_retry_api_takes():
    from select_near_empty_items import retry_body

    assert retry_body([_row(7, 10, 0), _row(3, 10, 0)]) == {"item_ids": [7, 3], "reset_stage": "pending"}


def test_write_outputs(tmp_path):
    from select_near_empty_items import retry_body, select_near_empty, write_outputs

    picked = select_near_empty([_row(5, pages=12, body_chars=120)], min_pages=8, max_chars_per_page=150)
    csv_path, json_path = write_outputs(tmp_path / "out", picked)

    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [{
        "item_id": "5", "book_id": "KCI_FI000000005", "pages": "12", "body_chars": "120",
        "chars_per_page": "10.0", "finished_at": "2026-09-03T04:00:00+00:00",
    }]
    assert json.loads(json_path.read_text(encoding="utf-8")) == retry_body(picked)


def test_candidate_sql_binds_and_avoids_param_cast():
    from select_near_empty_items import CANDIDATES_SQL

    assert set(text(CANDIDATES_SQL).compile().params) == {"job", "before", "min_pages", "max_cpp"}
    # `:param::type` 는 SQLAlchemy 가 바인딩하지 못한다(함정 7번) — CAST(:p AS type) 로 쓴다
    assert re.search(r":\w+::", CANDIDATES_SQL) is None
    # 완료 12만 건의 본문을 다 풀지 않게, 크기만 보는 octet_length 로 먼저 거른다
    assert "octet_length" in CANDIDATES_SQL


def test_finished_before_needs_a_timezone():
    from select_near_empty_items import parse_args

    args = parse_args(["--job", "j", "--out", "o", "--finished-before", "2026-10-02T03:00:00+00:00"])
    assert args.finished_before == "2026-10-02T03:00:00+00:00"
    with pytest.raises(SystemExit):
        parse_args(["--job", "j", "--out", "o", "--finished-before", "2026-10-02T03:00:00"])
```

`app/tests/test_build_canary_manifest.py` (새 파일, 전체):

```python
"""scripts/bulk_ingest/build_canary_manifest.py — 카나리 범주 판정·선정·매니페스트."""
import hashlib
import json
import random
import sys
from pathlib import Path

from sqlalchemy import text

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "bulk_ingest"
sys.path.insert(0, str(SCRIPTS_DIR))

NO_SECTIONS = "섹션 없음 — extract 단계부터 재실행 필요"


def _item(item_id, status="done", error_group=None, last_error=None, **meta):
    return {
        "id": item_id, "book_id": f"KCI_FI{item_id:09d}",
        "source_key": f"originals/KCI_FI{item_id:09d}/KCI_FI{item_id:09d}.pdf",
        "status": status, "error_group": error_group, "last_error": last_error, "meta": meta,
    }


def _pool():
    """범주마다 몫보다 넉넉한 후보 — 스캔 30·표 15·쪼개짐 8·섹션 8·보통 40."""
    rows, n = [], 0
    for _ in range(30):
        n += 1
        rows.append(_item(n, "failed", "not_found", NO_SECTIONS, pages=12))
    for _ in range(15):
        n += 1
        rows.append(_item(n, pages=12, chunks=20, n_tables=7, sections_total=6))
    for _ in range(8):
        n += 1
        rows.append(_item(n, pages=10, chunks=80, n_tables=0, sections_total=9))
    for _ in range(8):
        n += 1
        rows.append(_item(n, pages=40, chunks=90, n_tables=1, sections_total=55))
    for _ in range(40):
        n += 1
        rows.append(_item(n, pages=14, chunks=30, n_tables=1, sections_total=8))
    return rows


class TestClassify:
    def test_failed_without_sections_is_scan_candidate(self):
        from build_canary_manifest import classify

        assert classify(_item(1, "failed", "not_found", NO_SECTIONS)) == "scan_no_sections"

    def test_other_failures_are_not_picked(self):
        from build_canary_manifest import classify

        # '카탈로그 row 없음' 은 카탈로그 문제다 — 카나리로 볼 것이 없다
        assert classify(_item(1, "failed", "not_found", "카탈로그 row 없음")) is None
        assert classify(_item(2, "failed", "extract_empty", "텍스트 추출 실패: []")) is None
        assert classify(_item(3, "pending")) is None

    def test_done_categories(self):
        from build_canary_manifest import classify

        assert classify(_item(1, n_tables=5, pages=10, chunks=10)) == "many_tables"
        assert classify(_item(2, pages=10, chunks=61)) == "dense_chunks"      # 쪽당 6.1
        assert classify(_item(3, pages=10, chunks=60)) == "normal"            # 쪽당 6 은 초과가 아니다
        assert classify(_item(4, pages=10, chunks=20, sections_total=41)) == "many_sections"
        assert classify(_item(5)) == "normal"                                 # meta 가 비어도 보통

    def test_earlier_category_wins(self):
        from build_canary_manifest import classify

        assert classify(_item(1, n_tables=6, pages=10, chunks=90, sections_total=50)) == "many_tables"
        assert classify(_item(2, pages=10, chunks=90, sections_total=50)) == "dense_chunks"


class TestPick:
    def test_quotas_are_filled(self):
        from build_canary_manifest import QUOTAS, pick_canary

        picked = pick_canary(_pool())
        counts = {c: sum(1 for r in picked if r["category"] == c) for c in QUOTAS}
        assert counts == QUOTAS
        assert len({r["book_id"] for r in picked}) == sum(QUOTAS.values()) == 50

    def test_same_seed_same_pick_whatever_the_row_order(self):
        from build_canary_manifest import pick_canary

        rows = _pool()
        shuffled = rows[:]
        random.Random(1).shuffle(shuffled)
        assert pick_canary(rows, seed="s1") == pick_canary(shuffled, seed="s1")

    def test_pick_follows_the_seed_hash_not_the_id_order(self):
        from build_canary_manifest import order_key, pick_canary

        rows = _pool()
        scans = [r for r in rows if r["status"] == "failed"]
        expected = sorted(scans, key=lambda r: order_key(r["book_id"], "s1"))[:20]
        picked = [r for r in pick_canary(rows, seed="s1") if r["category"] == "scan_no_sections"]
        assert [r["id"] for r in picked] == [r["id"] for r in expected]
        assert {r["id"] for r in picked} != {r["id"] for r in scans[:20]}  # id 순 앞 20건이 아니다

    def test_order_key_matches_the_sql_md5(self):
        from build_canary_manifest import order_key

        # SQL 은 md5(book_id || :seed) 순으로 후보를 자른다 — 같은 순서여야 한다
        assert order_key("KCI_FI001", "round07") == hashlib.md5(b"KCI_FI001round07").hexdigest()

    def test_shortfalls(self):
        from build_canary_manifest import pick_canary, shortfalls

        rows = [r for r in _pool() if r["meta"].get("chunks") != 80]
        rows += [_item(900 + i, pages=10, chunks=80) for i in range(3)]
        assert shortfalls(pick_canary(rows)) == {"dense_chunks": 2}


class TestManifest:
    def test_rows_use_the_job_items_source_key(self):
        from build_canary_manifest import manifest_rows, pick_canary

        row = manifest_rows(pick_canary(_pool()))[0]
        assert set(row) == {"book_id", "object_key", "category", "item_id"}
        assert row["object_key"] == f"originals/{row['book_id']}/{row['book_id']}.pdf"

    def test_job_manager_accepts_the_manifest(self, tmp_path):
        from build_canary_manifest import manifest_rows, pick_canary, write_manifest
        from services.ingestion.job_manager import build_job_plan

        path = tmp_path / "manifest.jsonl"
        write_manifest(path, manifest_rows(pick_canary(_pool())))
        manifest = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        keys = {r["object_key"] for r in manifest}
        ids = {r["book_id"] for r in manifest}
        # 완료분도 다시 돌리므로 reembed=True — 이미 임베딩된 문서도 빼지 않는다
        items, report = build_job_plan(manifest, keys, ids, ids, reembed=True)
        assert report["to_ingest"] == 50 and not report["missing_object"] and not report["missing_meta"]
        assert {it["source_key"] for it in items} == keys

    def test_next_steps_print_upload_create_and_start(self):
        from build_canary_manifest import next_steps

        steps = "\n".join(next_steps("/app/data/round07/canary/manifest.jsonl", "round07-canary"))
        assert "'manifests/round07-canary/manifest.jsonl', '/app/data/round07/canary/manifest.jsonl'" in steps
        assert '"manifest_key":"manifests/round07-canary/manifest.jsonl"' in steps
        assert '"params":{"reembed":true,"skip_cover":true}' in steps
        assert "/start" in steps


def test_candidate_sql_binds():
    from build_canary_manifest import CATEGORY_FILTERS, QUOTAS, candidate_sql

    assert set(CATEGORY_FILTERS) == set(QUOTAS)
    for category in QUOTAS:
        sql = candidate_sql(category)
        assert "md5(book_id || :seed)" in sql
        assert set(text(sql).compile().params) <= {"job", "seed", "cap", "pat"}
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_select_near_empty_items.py tests/test_build_canary_manifest.py -q`

Expected: `20 failed` — 모두 `ModuleNotFoundError: No module named 'select_near_empty_items'`(7개)·`No module named 'build_canary_manifest'`(13개).

- [ ] **Step 3: `scripts/bulk_ingest/select_near_empty_items.py` 작성**

`scripts/bulk_ingest/select_near_empty_items.py` (새 파일, 전체):

```python
r"""select_near_empty_items.py — 본문이 거의 빈 채 완료된 아이템 고르기 (읽기 전용)

배경 (round07, 2026-10-01 진단):
  kci-full-236k 완료분 가운데 8쪽 이상인데 본문이 거의 없는 문서가 있다(가중 추정 약 907건).
  원인은 09-03 02~08 UTC 의 일시 코드(약 458, 이미 고침)·VLM 실패 뒤 ODL 폴백·빈 표 격자·
  부분 본문 등이다. round07 코드로 추출부터 다시 돌릴 대상만 고른다.

기준 — 쪽당 본문 글자 수:
  book_sections.full_text 길이(글자) 합 ÷ meta.pages 가 기준(기본 150자) 미만인 done 아이템.
  청크 수 기준은 쓰지 않는다 — 표 하나짜리 정상 문서(예: 표 2,980토큰이 청크 1개)가 섞인다.
  length() 는 TOAST 된 본문을 풀어야 해서 완료 12만 건에 다 돌리면 본문 전체를 읽는다. 그래서
  풀지 않고 크기를 아는 octet_length()(바이트)로 먼저 거른다. UTF-8 한 글자는 1~4바이트라
  바이트가 쪽당 기준×4 이상이면 글자가 기준 미만일 수 없다.

읽기만 한다: 트랜잭션을 READ ONLY 로 연다. 재처리는 사람이 CSV 를 본 뒤 JSON 으로 retry API 를 부른다
(docs/ops/bulk_ingest_runbook.md §9).

실행 (서버 — scripts/ 는 앱 이미지에 없어 데이터 바인드 마운트로 넣는다):
  mkdir -p /data/nl-lib/data/round07
  cp select_near_empty_items.py /data/nl-lib/data/round07/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi \
    python /app/data/round07/select_near_empty_items.py \
      --job 1ca22f59-1e50-4dd1-81f5-2d3c79126825 --out /app/data/round07 \
      --finished-before 2026-10-02T03:00:00+00:00

  --finished-before 에는 round07 배포 시각을 시간대까지 붙여 준다. 배포 뒤 새 코드로 끝난 문서는
  다시 돌려도 결과가 같다.
  PYTHONPATH=/app 이 필요한 이유: 스크립트를 경로로 실행하면 sys.path[0] 이 스크립트 디렉터리로
  잡혀 /app 의 앱 모듈(db.postgres)을 못 찾는다(docs/ops/recurring-gotchas.md 4번).

출력 (--out 아래, 호스트에서는 /data/nl-lib/data/round07/):
  near_empty_items.csv   item_id,book_id,pages,body_chars,chars_per_page,finished_at — 사람이 본다
  near_empty_retry.json  {"item_ids": [...], "reset_stage": "pending"} — retry API 본문 그대로
"""
import argparse
import csv
import datetime as _dt
import json
from collections import Counter
from pathlib import Path

CSV_NAME = "near_empty_items.csv"
JSON_NAME = "near_empty_retry.json"
CSV_FIELDS = ["item_id", "book_id", "pages", "body_chars", "chars_per_page", "finished_at"]

# :before 가 NULL 이면 완료 시각으로 거르지 않는다. 바인드 뒤 `::` 캐스트는 쓰지 않는다(함정 7번).
CANDIDATES_SQL = """
WITH done AS (
    SELECT id, book_id, finished_at,
           CASE WHEN jsonb_typeof(meta -> 'pages') = 'number'
                THEN (meta ->> 'pages')::numeric END AS pages
    FROM ingest_job_items
    WHERE job_id = :job AND status = 'done'
      AND (CAST(:before AS timestamptz) IS NULL OR finished_at < CAST(:before AS timestamptz))
), sized AS (
    SELECT d.id, d.book_id, d.finished_at, d.pages,
           coalesce(sum(octet_length(s.full_text)), 0) AS body_bytes
    FROM done d
    LEFT JOIN book_sections s ON s.book_id = d.book_id
    WHERE d.pages >= :min_pages
    GROUP BY d.id, d.book_id, d.finished_at, d.pages
)
SELECT z.id AS item_id, z.book_id, z.pages::int AS pages, z.finished_at,
       (SELECT coalesce(sum(length(s.full_text)), 0)
          FROM book_sections s WHERE s.book_id = z.book_id) AS body_chars
FROM sized z
WHERE z.body_bytes < 4 * :max_cpp * z.pages
"""


def select_near_empty(rows: list[dict], *, min_pages: int, max_chars_per_page: float) -> list[dict]:
    """쪽수 min_pages 이상이고 쪽당 글자 수가 기준 미만인 행 — 쪽당 글자 수 오름차순."""
    picked = []
    for row in rows:
        if row["pages"] < min_pages:
            continue
        cpp = row["body_chars"] / row["pages"]
        if cpp < max_chars_per_page:
            picked.append({**row, "chars_per_page": round(cpp, 1)})
    return sorted(picked, key=lambda r: (r["chars_per_page"], r["item_id"]))


def finished_by_day(rows: list[dict]) -> list[tuple[str, int]]:
    """완료 날짜(UTC)별 건수 — 09-03 일시 코드분처럼 몰린 날을 본다."""
    days = Counter(r["finished_at"].astimezone(_dt.timezone.utc).strftime("%Y-%m-%d") for r in rows)
    return sorted(days.items())


def retry_body(rows: list[dict]) -> dict:
    return {"item_ids": [r["item_id"] for r in rows], "reset_stage": "pending"}


def write_outputs(out_dir: Path, rows: list[dict]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / CSV_NAME
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({**{k: r[k] for k in CSV_FIELDS}, "finished_at": r["finished_at"].isoformat()})
    json_path = out_dir / JSON_NAME
    json_path.write_text(json.dumps(retry_body(rows), ensure_ascii=False), encoding="utf-8")
    return csv_path, json_path


def fetch_candidates(job_id: str, *, min_pages: int, max_chars_per_page: float,
                     finished_before: str | None) -> list[dict]:
    from sqlalchemy import text as sa_text

    from db.postgres import SyncSessionLocal

    db = SyncSessionLocal()
    try:
        db.execute(sa_text("SET TRANSACTION READ ONLY"))
        result = db.execute(sa_text(CANDIDATES_SQL), {
            "job": job_id, "before": finished_before,
            "min_pages": min_pages, "max_cpp": max_chars_per_page,
        })
        return [dict(r._mapping) for r in result]
    finally:
        db.rollback()
        db.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="빈 본문 완료 아이템 선정 (읽기 전용)")
    ap.add_argument("--job", required=True, help="잡 id (ingest_jobs.id)")
    ap.add_argument("--out", required=True, help="CSV·JSON 을 쓸 디렉터리")
    ap.add_argument("--min-pages", type=int, default=8)
    ap.add_argument("--max-chars-per-page", type=float, default=150.0)
    ap.add_argument("--finished-before", default=None,
                    help="이 시각 전에 끝난 것만 (ISO8601, 시간대 필수 — 예: 2026-10-02T03:00:00+00:00)")
    args = ap.parse_args(argv)
    if args.finished_before:
        try:
            when = _dt.datetime.fromisoformat(args.finished_before)
        except ValueError:
            ap.error(f"--finished-before 형식이 틀렸다: {args.finished_before}")
        if when.tzinfo is None:
            ap.error("--finished-before 에 시간대를 붙인다(예: +00:00) — 없으면 DB 세션 시간대로 읽힌다")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    rows = fetch_candidates(
        args.job, min_pages=args.min_pages, max_chars_per_page=args.max_chars_per_page,
        finished_before=args.finished_before,
    )
    picked = select_near_empty(rows, min_pages=args.min_pages, max_chars_per_page=args.max_chars_per_page)
    csv_path, json_path = write_outputs(Path(args.out), picked)

    print(f"── 쪽당 본문 {args.max_chars_per_page:g}자 미만 ({args.min_pages}쪽 이상 done) ──")
    print(f"  후보(크기로 거른 뒤) {len(rows)}건 → 선정 {len(picked)}건")
    print("  완료 날짜(UTC)별:")
    for day, n in finished_by_day(picked):
        print(f"    {day}  {n}")
    print(f"\n→ {csv_path}")
    print(f"→ {json_path}")
    print("\n목록을 본 뒤 재처리(지울 행은 JSON 의 item_ids 에서도 뺀다):")
    print(f"  docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/{args.job}/retry "
          f"-H 'Content-Type: application/json' -d @{json_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: `scripts/bulk_ingest/build_canary_manifest.py` 작성**

`scripts/bulk_ingest/build_canary_manifest.py` (새 파일, 전체):

```python
r"""build_canary_manifest.py — 카나리 잡 매니페스트 만들기 (DB 읽기 전용, 파일만 쓴다)

배포 뒤 본 잡을 재개하기 전에, 문제 유형별 약 50건으로 소량 잡을 돌려 새 코드를 본다
(round07 spec §5 카나리). 본 잡(kci-full-236k)의 아이템에서 범주별로 고른다.

  scan_no_sections  20  failed · not_found · '섹션 없음' — 텍스트 층에 몇 글자만 남은 스캔본(함정 21번)
  many_tables       10  done · meta.n_tables ≥ 5 — 요약 단계로 옮긴 표 해석
  dense_chunks       5  done · 쪽당 청크 > 6 — <br> 껍데기처럼 잘게 쪼개진 본문 의심
  many_sections      5  done · meta.sections_total > 40 — 계층 요약
  normal            10  done · 위 어디에도 들지 않는 것

한 아이템이 여러 범주에 들면 위 순서에서 앞선 범주로 센다. 범주 안에서는 seed 해시 순으로 고른다 —
id 순 앞부분은 표본이 아니고(docs/ops/recurring-gotchas.md 11번), 같은 seed 면 다시 돌려도 같은
50건이 나온다. 후보는 SQL 이 범주마다 같은 해시 순으로 (몫 × --oversample)건까지만 읽는다.

DB 는 읽기만 하고(READ ONLY 트랜잭션) 매니페스트는 로컬 파일로만 쓴다. MinIO 업로드·잡 생성·시작은
하지 않고 명령만 출력한다 — 운영에 쓰는 일은 사람이 한다(docs/ops/bulk_ingest_runbook.md §9).

매니페스트 형식: build_manifest.py 와 같은 JSONL, 한 줄 = 한 문서. 잡 생성(job_manager.build_job_plan)은
book_id·object_key 만 읽는다. object_key 는 본 잡 아이템의 source_key(본 잡을 만들 때 MinIO 에 있음을
확인한 키)를 그대로 쓴다. category·item_id(본 잡 아이템 id)는 사람이 보는 기록이다.

실행 (서버 — scripts/ 는 앱 이미지에 없어 데이터 바인드 마운트로 넣는다. 함정 4번):
  mkdir -p /data/nl-lib/data/round07
  cp build_canary_manifest.py /data/nl-lib/data/round07/
  docker exec -e PYTHONPATH=/app nl-lib-fastapi \
    python /app/data/round07/build_canary_manifest.py \
      --job 1ca22f59-1e50-4dd1-81f5-2d3c79126825 --out /app/data/round07/canary
"""
import argparse
import hashlib
import json
from pathlib import Path

# 범주와 몫 — 순서가 우선순위다
QUOTAS = {
    "scan_no_sections": 20,
    "many_tables": 10,
    "dense_chunks": 5,
    "many_sections": 5,
    "normal": 10,
}
DEFAULT_SEED = "round07"
MANIFEST_NAME = "manifest.jsonl"
NO_SECTIONS_PREFIX = "섹션 없음"   # stages.run_summarize 의 StageError("not_found", "섹션 없음 — …")


def _num(meta: dict, key: str) -> float:
    return float(meta.get(key) or 0)


def classify(row: dict) -> str | None:
    """아이템 한 줄 → 범주. 어느 범주도 아니면 None."""
    if row["status"] == "failed":
        if row.get("error_group") == "not_found" and (row.get("last_error") or "").startswith(NO_SECTIONS_PREFIX):
            return "scan_no_sections"
        return None
    if row["status"] != "done":
        return None
    meta = row.get("meta") or {}
    pages = _num(meta, "pages")
    if _num(meta, "n_tables") >= 5:
        return "many_tables"
    if pages > 0 and _num(meta, "chunks") / pages > 6:
        return "dense_chunks"
    if _num(meta, "sections_total") > 40:
        return "many_sections"
    return "normal"


def order_key(book_id: str, seed: str) -> str:
    """SQL 의 md5(book_id || :seed) 와 같은 값 — 후보를 자르는 순서와 고르는 순서를 맞춘다."""
    return hashlib.md5(f"{book_id}{seed}".encode("utf-8")).hexdigest()


def pick_canary(rows: list[dict], quotas: dict[str, int] = QUOTAS, seed: str = DEFAULT_SEED) -> list[dict]:
    """범주마다 seed 해시 순으로 몫만큼. 같은 아이템이 후보에 여러 번 와도 한 번만 센다."""
    by_category: dict[str, list[dict]] = {c: [] for c in quotas}
    seen: set[int] = set()
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        category = classify(row)
        if category in by_category:
            by_category[category].append(row)
    picked = []
    for category, n in quotas.items():
        pool = sorted(by_category[category], key=lambda r: (order_key(r["book_id"], seed), r["id"]))
        picked += [{**r, "category": category} for r in pool[:n]]
    return picked


def shortfalls(picked: list[dict], quotas: dict[str, int] = QUOTAS) -> dict[str, int]:
    """몫을 못 채운 범주 → 모자란 수."""
    got = {c: sum(1 for r in picked if r["category"] == c) for c in quotas}
    return {c: quotas[c] - got[c] for c in quotas if got[c] < quotas[c]}


def manifest_rows(picked: list[dict]) -> list[dict]:
    return [
        {"book_id": r["book_id"], "object_key": r["source_key"], "category": r["category"], "item_id": r["id"]}
        for r in picked
    ]


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def next_steps(manifest_path: str, name: str) -> list[str]:
    """사람이 차례로 돌릴 명령 — MinIO 업로드, 잡 생성(dry-run 검증 → ready), 시작."""
    key = f"manifests/{name}/manifest.jsonl"
    body = json.dumps(
        {"name": name, "manifest_key": key, "params": {"reembed": True, "skip_cover": True}},
        separators=(",", ":"),
    )
    upload = (
        "from core.config import get_settings; from services.ingestion.stages import minio_client; "
        f"minio_client().fput_object(get_settings().MINIO_BUCKET, '{key}', '{manifest_path}'); print('uploaded')"
    )
    return [
        f'docker exec -e PYTHONPATH=/app nl-lib-fastapi python -c "{upload}"',
        "docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs "
        f"-H 'Content-Type: application/json' -d '{body}'",
        "docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/<canary_job_id>/start",
    ]


# 범주별 후보 조건 — classify 와 같은 규칙을 SQL 로(우선순위 정리는 classify 가 한다)
def _meta_num(key: str) -> str:
    return f"CASE WHEN jsonb_typeof(meta -> '{key}') = 'number' THEN (meta ->> '{key}')::numeric END"


CATEGORY_FILTERS = {
    "scan_no_sections": "status = 'failed' AND error_group = 'not_found' AND last_error LIKE :pat",
    "many_tables": f"status = 'done' AND {_meta_num('n_tables')} >= 5",
    "dense_chunks": f"status = 'done' AND {_meta_num('pages')} > 0 AND {_meta_num('chunks')} > 6 * {_meta_num('pages')}",
    "many_sections": f"status = 'done' AND {_meta_num('sections_total')} > 40",
    "normal": "status = 'done'",
}


def candidate_sql(category: str) -> str:
    return (
        "SELECT id, book_id, source_key, status, error_group, last_error, meta "
        "FROM ingest_job_items "
        f"WHERE job_id = :job AND {CATEGORY_FILTERS[category]} "
        "ORDER BY md5(book_id || :seed) LIMIT :cap"
    )


def fetch_candidates(job_id: str, seed: str, oversample: int) -> list[dict]:
    from sqlalchemy import text as sa_text

    from db.postgres import SyncSessionLocal

    db = SyncSessionLocal()
    try:
        db.execute(sa_text("SET TRANSACTION READ ONLY"))
        rows: list[dict] = []
        for category, quota in QUOTAS.items():
            params = {"job": job_id, "seed": seed, "cap": quota * oversample}
            if category == "scan_no_sections":
                params["pat"] = NO_SECTIONS_PREFIX + "%"
            rows += [dict(r._mapping) for r in db.execute(sa_text(candidate_sql(category)), params)]
        return rows
    finally:
        db.rollback()
        db.close()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="카나리 잡 매니페스트 (DB 읽기 전용)")
    ap.add_argument("--job", required=True, help="고를 아이템이 있는 잡 id (본 잡)")
    ap.add_argument("--out", required=True, help="manifest.jsonl 을 쓸 디렉터리")
    ap.add_argument("--name", default="round07-canary", help="카나리 잡 이름 = MinIO manifests/<name>/")
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--oversample", type=int, default=20, help="범주마다 몫의 몇 배까지 후보를 읽을지")
    args = ap.parse_args(argv)

    picked = pick_canary(fetch_candidates(args.job, args.seed, args.oversample), seed=args.seed)
    path = Path(args.out) / MANIFEST_NAME
    write_manifest(path, manifest_rows(picked))

    print("── 범주별 (몫 / 고른 수) ──")
    for category, quota in QUOTAS.items():
        got = sum(1 for r in picked if r["category"] == category)
        print(f"  {category:<17} {quota:>3} / {got}")
    short = shortfalls(picked)
    if short:
        print(f"  모자람: {short} — --oversample 을 늘려 다시 돌리거나 그대로 쓴다")
    print(f"\n→ {path} ({len(picked)}건)")
    print("\n다음은 사람이 차례로 한다 (이 스크립트는 운영에 쓰지 않는다):")
    for i, cmd in enumerate(next_steps(str(path), args.name), 1):
        print(f"  {i}) {cmd}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: `scripts/bulk_ingest/README.md` — 새 도구 절**

`scripts/bulk_ingest/README.md` — 교체 전:

```markdown
진행 현황은 `/admin/jobs` 대시보드 또는 `GET /api/admin/ingest-jobs/{id}`로 확인합니다.
```

교체 후:

```markdown
진행 현황은 `/admin/jobs` 대시보드 또는 `GET /api/admin/ingest-jobs/{id}`로 확인합니다.

## 5) 재처리·카나리 도구 (서버에서, DB 읽기 전용)

둘 다 앱 모듈(`db.postgres`)을 쓰므로 서버의 `/data/nl-lib/data/round07/` 에 복사해 `nl-lib-fastapi` 안에서
`docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round07/<스크립트> …` 로 돌린다
(`docs/ops/recurring-gotchas.md` 4번). 인자·출력은 각 파일 머리말, 배포 순서 안의 쓰임은
`docs/ops/bulk_ingest_runbook.md` §9.

| 스크립트 | 하는 일 | 쓰는 것 |
|---|---|---|
| `select_near_empty_items.py` | done 이고 8쪽 이상인데 쪽당 본문 글자 수가 150자 미만인 아이템 | CSV(사람이 본다) + retry API 본문 JSON |
| `build_canary_manifest.py` | 본 잡에서 문제 유형별 50건(스캔본 20·표 10·잘게 쪼개짐 5·섹션 40개 초과 5·보통 10) | 매니페스트 JSONL — 업로드·잡 생성·시작 명령은 출력만 |
```

- [ ] **Step 6: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest tests/test_select_near_empty_items.py tests/test_build_canary_manifest.py -q`

Expected: `20 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && python scripts/bulk_ingest/select_near_empty_items.py --help && python scripts/bulk_ingest/build_canary_manifest.py --help`

Expected: 두 스크립트의 usage 가 나온다(`usage: select_near_empty_items.py [-h] --job JOB --out OUT …`, `usage: build_canary_manifest.py [-h] --job JOB --out OUT …`) — 모듈 최상단이 앱 모듈을 import 하지 않는다는 확인이다.

- [ ] **Step 7: 전체 테스트**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07/app && python -m pytest -q --continue-on-collection-errors`

Expected: failed 0, errors 는 기존 수집 오류 3 그대로 — Task 0 직후(897)에서 이 작업만 더하면 `917 passed, 2 warnings, 3 errors`.

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && git add scripts/bulk_ingest/select_near_empty_items.py scripts/bulk_ingest/build_canary_manifest.py scripts/bulk_ingest/README.md app/tests/test_select_near_empty_items.py app/tests/test_build_canary_manifest.py && git status --short && git commit -m "[Feat] round07 — 재처리·카나리 도구(서버에서 사람이 돌리는 읽기 전용 스크립트): select_near_empty_items 는 done·8쪽 이상인데 쪽당 본문 글자 수가 150자 미만인 아이템을 골라 CSV 와 retry API 본문 JSON 으로 쓴다(청크 수 기준은 표 하나짜리 정상 문서가 섞여 쓰지 않는다, octet_length 로 먼저 걸러 본문을 다 풀지 않는다, 배포 전에 끝난 것만). build_canary_manifest 는 본 잡에서 스캔본 '섹션 없음' 20·표 많은 문서 10·쪽당 청크 6 초과 5·섹션 40개 초과 5·보통 10 을 seed 해시 순으로 골라 기존 매니페스트와 같은 JSONL 로 쓰고, MinIO 업로드·잡 생성·시작 명령은 출력만 한다"
```

---

### Task 11: 실제 PDF 라우팅 회귀 하네스 (`research/round07-ingest-regression/`, 1회성)

> **실행 메모(2026-10-02, 실행 470a5ee·리뷰 통과):** 아래 Step 1 코드와 Step 2 표는 Task 3 첫 구현(0487057 — 'ODL 이 놓친 쪽'을 되풀이 줄 뺀 fitz 길이로 판정) 기준으로 썼다. 리뷰 수정 5b3be2e 뒤로 그 판정은 원래 fitz 길이로 한다(spec 7). 그래서 비스캔 'OCR 에서 빠짐' 2·2·11쪽이 OCR 에 남아 0 이 되고(원래 길이 때문에 OCR 에 남는 쪽 — short_front 는 4건 11쪽), Step 2 표는 실제 실행값으로 고쳤다(pre2005 새 OCR 2194 → 2196, digital 318 → 320, short_front 38 → 49). 옛 규칙의 출처는 d85df93 이 아니라 0df3001 의 `extractor.py:416-434` 다(dev 분기점 9798f46 과 같은 운영 코드 — d85df93 에는 `0 <` 하한이 없다). 실제 구현은 이름 오른 경계 사례 8건(`named_cases` — 다른 묶음과 5건 겹치므로 합산하지 않는다)을 더하고, 8워커 병렬(캐시 없이 511초, 다시 돌리면 약 60초)로 돌며, 검사 41개가 틀리면 exit 1 이다. 검사는 이 시드의 묶음 합계를 고정하지 않아 스캔 판정 비율을 0.9 로 바꾸는 변이는 못 잡는다 — 그 경계는 `test_page_routing.py` 가 고정한다. 결과 표·근사 한계는 `research/round07-ingest-regression/README.md` 에 있다.

**Files:**
- Create: `research/round07-ingest-regression/route_compare.py`
- Create(실행 산출물): `research/round07-ingest-regression/pages.csv`·`docs.csv`·`summary.json`

이 PC 의 `D:/SKOVIX/KCI/pdf` 로 옛 규칙과 새 규칙의 쪽별 판정(OCR 로 가는 쪽 수)을 비교한다. **VLM·ODL 은 부르지 않는다.** ODL 본문은 'fitz 텍스트에서 문서 전체에 되풀이되는 줄을 뺀 `body_len`' 으로 근사하고, 근사가 놓치는 것(CMap 손상·`<br>` 격자·표 셀 충전율·ODL 누락)을 스크립트 docstring 에 적는다. 그래서 이 결과는 '짧은 쪽 분기'의 차이만 보여 준다 — 실제 ODL 을 돌린 관찰은 위 근거 ①~⑥ 이다. 새 규칙은 `page_routing` 의 실제 함수를 부르고, 옛 규칙은 0df3001 의 `extractor.py:416-434` 분기를 그대로 옮겼다(위 실행 메모).

묶음: `fail_block`(metadata.csv 의 「한국문학연구」 2002년 이전 — 10-01 '섹션 없음' 281건이 모두 이 안에 있다, 이 PC 에 318건), `pre2005`(2004년 이전 다른 학술지 무작위), `digital`(2005년 이후 무작위), `short_front`(2005년 이후 중 첫 두 쪽에 짧은 쪽이 있는 문서 — 이미지 표지 포함), `br_grid`(ODL embedded 에서 `<br>` 빈 격자가 나왔던 KCI_FI001930485·KCI_FI000897237).

- [ ] **Step 1: 스크립트 작성** — `research/round07-ingest-regression/route_compare.py`

```python
"""route_compare.py — round07 짧은 쪽 라우팅, 옛 규칙 vs 새 규칙 실제 PDF 회귀 (1회성)

VLM·ODL 을 부르지 않는다. 이 PC 의 D:/SKOVIX/KCI/pdf 를 fitz 로만 읽어, extract_text 의
'ODL 본문이 짧은 쪽' 판정을 옛 규칙(0df3001 의 extractor.py:424 분기)과 새 규칙
(page_routing.short_page_needs_ocr + is_scan_document)으로 각각 내리고 OCR 로 가는 쪽을 센다.

ODL 본문 근사 — ODL 은 json header/footer 로 머리말·꼬리말을 지운 markdown 을 낸다. 여기서는 그 길이를
'fitz 텍스트에서 문서 전체에 되풀이되는 줄(repeated_lines)을 뺀 body_len' 으로 둔다. 근사가 놓치는 것:
  - ODL 이 fitz 보다 글자를 잃는 쪽(CMap 손상) — 근사에선 ODL ≈ fitz 라 CMap 2배 분기는 머리말·꼬리말이
    길 때만 걸린다(cmap_by_header 로 따로 센다 — 실제 ODL 에서도 그 쪽이 걸리는지는 알 수 없다)
  - ODL 의 <br> 빈 표 격자·[그림] 마커 — 근사 텍스트엔 없다. br_grid 묶음은 fitz 쪽 판정이 바뀌지 않는지만 본다
  - 표 셀 충전율(json) 판정과 'ODL 누락' 쪽 — 쓰지 않는다
그래서 이 결과는 '짧은 쪽 분기' 의 차이만 보여 준다. 두 규칙 모두 VLM 60쪽 상한을 적용한다.

묶음:
  fail_block  — metadata.csv 의 「한국문학연구」 2002년 이전(10-01 '섹션 없음' 281건이 모두 이 안에 있다)
  pre2005     — 2004년 이전 다른 학술지 무작위
  digital     — 2005년 이후 무작위
  short_front — 2005년 이후 문서 중 첫 두 쪽 안에 짧은 쪽(표지·간지, 이미지 표지 포함)이 있는 문서(digital 다음 순서에서 최대 25건)
  br_grid     — ODL embedded 에서 <br> 빈 격자가 나왔던 문서

산출물(이 폴더): pages.csv(쪽별 판정)·docs.csv(문서별)·summary.json(묶음별 합계)
사용법: python research/round07-ingest-regression/route_compare.py [--per-group 200] [--seed 20261001]
"""
import argparse
import csv
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))

import fitz  # noqa: E402

from services.ingestion import page_routing as pr  # noqa: E402
from services.ingestion.extractor import _clean_text  # noqa: E402

PDF_DIR = Path("D:/SKOVIX/KCI/pdf")
META = Path("D:/SKOVIX/KCI/metadata.csv")
MIN_CHARS = 50
VLM_CAP = 60
REPEAT_RATIO = 0.6
SHORT_RATIO = 0.5
SCAN_MIN_PAGES = 3
BR_GRID = ["KCI_FI001930485", "KCI_FI000897237"]
FRONT_TARGET = 25


def old_decision(odl_len: int, raw: int) -> tuple[bool, str]:
    if odl_len >= MIN_CHARS:
        return (True, "CMap 의심") if raw > odl_len * 2 else (False, "본문 충분")
    if 0 < raw < MIN_CHARS:
        return False, "원래 짧은 쪽"
    return True, "본문 텍스트 부족"


def new_decision(odl_len: int, raw: int, stripped: int, doc_is_scan: bool) -> tuple[bool, str]:
    if odl_len >= MIN_CHARS:
        return (True, "CMap 의심") if raw > odl_len * 2 else (False, "본문 충분")
    return pr.short_page_needs_ocr(
        fitz_len_stripped=stripped, fitz_len_raw=raw, doc_is_scan=doc_is_scan, force=False, min_chars=MIN_CHARS,
    )


def _cap(flags: list[bool]) -> list[bool]:
    out, used = [], 0
    for f in flags:
        out.append(f and used < VLM_CAP)
        used += f
    return out


def analyze(pid: str, group: str) -> tuple[dict, list[dict]] | None:
    try:
        with fitz.open(PDF_DIR / f"{pid}.pdf") as doc:
            texts = [_clean_text(p.get_text()) for p in doc]
    except RuntimeError:
        return None
    if not texts:
        return None
    rep = pr.repeated_lines(texts, REPEAT_RATIO)
    raw = [pr.body_len(t) for t in texts]
    stripped = [pr.body_len(pr.strip_lines(t, rep)) for t in texts]
    odl = stripped  # ODL 본문 근사(위 docstring)
    short = [odl[n] < MIN_CHARS and stripped[n] < MIN_CHARS for n in range(len(texts))]
    scan = pr.is_scan_document(short, min_pages=SCAN_MIN_PAGES, ratio=SHORT_RATIO)
    old = [old_decision(odl[n], raw[n]) for n in range(len(texts))]
    new = [new_decision(odl[n], raw[n], stripped[n], scan) for n in range(len(texts))]
    old_ocr, new_ocr = _cap([o for o, _ in old]), _cap([o for o, _ in new])
    pages = [
        {"id": pid, "group": group, "page": n, "fitz_raw": raw[n], "fitz_stripped": stripped[n],
         "odl_approx": odl[n], "short": short[n], "old_ocr": old_ocr[n], "old_reason": old[n][1],
         "new_ocr": new_ocr[n], "new_reason": new[n][1]}
        for n in range(len(texts))
    ]
    cmap = [n for n in range(len(texts)) if odl[n] >= MIN_CHARS and raw[n] > odl[n] * 2]
    doc_row = {
        "id": pid, "group": group, "pages": len(texts), "short_pages": sum(short), "doc_is_scan": scan,
        "old_ocr": sum(old_ocr), "new_ocr": sum(new_ocr),
        "newly_ocr": sum(n and not o for o, n in zip(old_ocr, new_ocr)),
        "no_longer_ocr": sum(o and not n for o, n in zip(old_ocr, new_ocr)),
        "cover_old": old_ocr[0], "cover_new": new_ocr[0], "cmap_by_header": len(cmap),
        "repeated": " / ".join(sorted(rep)[:3]),
    }
    return doc_row, pages


def pick(per_group: int, seed: int) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    rows = list(csv.DictReader(open(META, encoding="utf-8-sig")))

    def year(r):
        return int(r["year_month"][:4]) if r["year_month"][:4].isdigit() else None

    # 26만 파일 폴더라 파일마다 exists() 를 부르면 수십 분 걸린다 — 목록을 한 번만 읽는다.
    local = {e.name[:-4] for e in os.scandir(PDF_DIR) if e.name.endswith(".pdf")}

    def ids(cond) -> list[str]:  # metadata.csv 에 같은 id 가 두 번 있는 행이 있다
        return list(dict.fromkeys(r["kci_fi_id"] for r in rows if cond(r) and r["kci_fi_id"] in local))

    fail = ids(lambda r: r["journal"] == "한국문학연구" and year(r) and year(r) <= 2002)
    fail_set = set(fail)
    pre = ids(lambda r: year(r) and year(r) < 2005 and r["kci_fi_id"] not in fail_set)
    digital = ids(lambda r: year(r) and year(r) >= 2005)
    rng.shuffle(pre)
    rng.shuffle(digital)
    out = [(p, "fail_block") for p in fail]
    out += [(p, "pre2005") for p in pre[:per_group]]
    out += [(p, "digital") for p in digital[:per_group]]
    front = []
    for p in digital[per_group:per_group * 20]:
        try:
            with fitz.open(PDF_DIR / f"{p}.pdf") as doc:
                if len(doc) < SCAN_MIN_PAGES:
                    continue
                texts = [_clean_text(pg.get_text()) for pg in doc]
        except RuntimeError:
            continue
        rep = pr.repeated_lines(texts, REPEAT_RATIO)
        s = [pr.body_len(pr.strip_lines(t, rep)) for t in texts]
        if any(pr.body_len(texts[n]) > 0 and s[n] < MIN_CHARS for n in (0, 1)) and sum(x >= MIN_CHARS for x in s) >= len(s) * 0.6:
            front.append(p)
        if len(front) >= FRONT_TARGET:
            break
    out += [(p, "short_front") for p in front]
    out += [(p, "br_grid") for p in BR_GRID if p in local]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261001)
    args = ap.parse_args()
    fitz.TOOLS.mupdf_display_errors(False)

    docs, pages = [], []
    for pid, group in pick(args.per_group, args.seed):
        got = analyze(pid, group)
        if got:
            docs.append(got[0])
            pages.extend(got[1])

    for name, rows in (("docs.csv", docs), ("pages.csv", pages)):
        with open(HERE / name, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    summary: dict = defaultdict(lambda: defaultdict(int))
    for d in docs:
        s = summary[d["group"]]
        s["docs"] += 1
        s["pages"] += d["pages"]
        s["old_ocr_pages"] += d["old_ocr"]
        s["new_ocr_pages"] += d["new_ocr"]
        s["newly_ocr_pages"] += d["newly_ocr"]
        s["no_longer_ocr_pages"] += d["no_longer_ocr"]
        s["docs_changed"] += bool(d["newly_ocr"] or d["no_longer_ocr"])
        s["scan_docs"] += d["doc_is_scan"]
        s["missed_scan_docs"] += d["old_ocr"] == 0 and d["doc_is_scan"]  # 옛 규칙으론 OCR 0쪽이던 스캔본
        s["cmap_by_header_pages"] += d["cmap_by_header"]
        key = "scan" if d["doc_is_scan"] else "nonscan"
        s[f"{key}_newly_ocr_pages"] += d["newly_ocr"]
        s[f"{key}_no_longer_ocr_pages"] += d["no_longer_ocr"]
        s[f"{key}_cover_old_ocr"] += d["cover_old"]
        s[f"{key}_cover_new_ocr"] += d["cover_new"]
    out = {g: dict(v) for g, v in summary.items()}
    (HERE / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실행**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && python research/round07-ingest-regression/route_compare.py --per-group 200`
Expected — `summary.json` 이 아래와 같다(470a5ee 실행 값 — 위 실행 메모. 같은 시드·같은 PDF 폴더면 같은 표본. 8워커로 캐시 없이 511초, 다시 돌리면 약 60초 — 표본 약 750건과 표지·간지 후보 수천 건을 fitz 로 읽는다):

| 묶음 | 문서 | 쪽 | 옛 OCR 쪽 | 새 OCR 쪽 | 스캔본 | 옛 0쪽→스캔본 | 새로 OCR(스캔본) | 새로 OCR(비스캔) | OCR 에서 빠짐(비스캔) | 표지 OCR 옛(비스캔) | 표지 OCR 새(비스캔) | cmap_by_header |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fail_block | 318 | 6862 | 0 | 6837 | 318 | 318 | 6837 | 0 | 0 | 0 | 0 | 0 |
| pre2005 | 200 | 3673 | 1870 | 2196 | 102 | 10 | 326 | 0 | 0 | 4 | 4 | 11 |
| digital | 200 | 4701 | 248 | 320 | 13 | 3 | 72 | 0 | 0 | 0 | 0 | 0 |
| short_front | 24 | 1828 | 49 | 49 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| br_grid | 2 | 54 | 16 | 17 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| (named_cases — 겹침, 합산 금지) | 8 | 475 | 51 | 66 | 2 | 1 | 15 | 0 | 0 | 0 | 0 | 1 |

- [ ] **Step 3: 결과 확인 — 통과 기준**
  - `fail_block`: `scan_docs == docs` 이고 `missed_scan_docs == docs`(옛 규칙에서 OCR 0쪽이던 문서가 모두 스캔본으로 잡힌다). `new_ocr_pages` 가 `pages` 보다 적은 25쪽은 VLM 상한 7쪽(66·61쪽 문서)과 텍스트 층이 50자 이상이라 ODL 을 채택한 18쪽(18건에 1쪽씩)이다.
  - 스캔본이 아닌 문서: `nonscan_newly_ocr_pages == 0` 이고 `nonscan_cover_new_ocr <= nonscan_cover_old_ocr` 다 — 디지털 논문의 표지·간지가 새로 OCR 로 가지 않는다. (근사에서는 ODL 길이 = 되풀이 줄 뺀 fitz 길이라 비스캔 문서가 새로 OCR 로 갈 길은 없다. 0 이 아니면 근사나 규칙 구현이 틀린 것이다.)
  - `nonscan_no_longer_ocr_pages == 0` 이다 — 'ODL 이 놓친 쪽'을 원래 fitz 길이로 판정하므로(spec 7, 5b3be2e) 스캔본이 아닌 문서는 옛 규칙과 칸마다 같다. 첫 구현(되풀이 줄 뺀 길이로 판정)에서 빠지던 2·2·11쪽은 원래 길이 때문에 OCR 에 남는다. short_front 는 4건(KCI_FI001667569 3·KCI_FI003011274 4·KCI_FI001158431 3·KCI_FI001141801 1)으로, 예컨대 KCI_FI003011274(2023년 디지털 논문) 1·2·8·9쪽은 fitz 60자 중 머리말 `#년#월스마트미디어저널`·쪽 번호를 빼면 42자인 그림 쪽이다 — 뺀 길이로 판정하면 이 쪽을 '원래 짧은 쪽'으로 채택해 이미지로만 있는 본문을 잃는다. 0 이 아니면 `pages.csv` 에서 그 쪽의 판정 사유를 보고 규칙 구현을 의심한다.
  - `br_grid`: KCI_FI001930485 는 판정이 바뀌지 않는다(근사로는 `<br>` 가 안 보인다 — 근거 ⑤). KCI_FI000897237 은 스캔본이라 짧은 쪽이 OCR 로 간다.

- [ ] **Step 4: 커밋** — `*.csv` 는 `.gitignore` 4행 대상이라 CSV 두 개는 `-f` 로 더한다(research/ 는 산출물을 스크립트와 함께 둔다 — CLAUDE.md §1).

```bash
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add research/round07-ingest-regression/route_compare.py research/round07-ingest-regression/summary.json
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 add -f research/round07-ingest-regression/pages.csv research/round07-ingest-regression/docs.csv
git -C C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 commit -m "[Chore] round07 — 실제 PDF 라우팅 회귀(1회성): 이 PC 의 KCI PDF 로 「한국문학연구」 실패 블록·2005년 이전·디지털 논문·표지/간지 문서·<br> 격자 문서의 짧은 쪽 판정을 옛 규칙과 새 규칙으로 내려 쪽별 CSV·문서별 CSV·묶음 요약을 남긴다. VLM·ODL 은 부르지 않고 ODL 본문은 되풀이 줄을 뺀 fitz 길이로 근사한다(근사가 놓치는 것은 스크립트 docstring)"
```

---

### Task 12: 문서 — 런북 배포 절차·함정·현재 상태

> **실행 메모(2026-10-02 — 코드가 정본):** 아래 초안은 계획 때 쓴 것이고, 커밋한 런북 §9·함정 16·21·`00_status.md` 는 HEAD 코드에 맞춰 고쳤다. 초안과 다른 곳: ① 락 경합은 `pending` 으로 되돌리지 않고 아이템을 둔 채 체인만 멈춘다(진행 상한 한 칸을 쥔 채 `DISPATCH_STALE_SECONDS` 뒤 stale 복구) — 함정 16 의 '락 경합' 줄과 spec 18 을 고쳤다. ② 스키마가 다를 때 컬렉션을 지울 수 있는 것은 fastapi 기동만이 아니라 `ensure_collection()` 을 부르는 모든 프로세스(검색·색인·제어 워커의 1시간 flush)다 — 모두 `x-common-env` 라 `printenv` 하나로 본다. ③ stale 확인은 `last_error LIKE '%stale 복구%'`(성공 뒤에도 남는다)와 제어 워커 로그의 `stale 복구 (stage=` 로 센다. ④ 9-7 ② 에 `ocr_errors`·`render_errors`·`extract_deadline_hit` 를 더했다. ⑤ 9-3 의 옮길 목록은 `git diff 9798f46 -- docker-compose.yml` 그대로다(Task 5 리뷰의 `init: true`, ODL 타임아웃 기본값 10.0·1.5 포함). ⑥ 9-8 은 다시 돌릴 그룹을 `for` 하나로 보내고 `no_text` 는 보내지 않는다. ⑦ 배포 규칙(한 번에·모든 워커 새 이미지·두 잡 동시 `running` 금지·되돌리기), 9-1 의 `unacked`·문서 락·jsonb 확인, 9-6 의 `CANARY` 자동 받기, 9-7 ⑧~⑬(단계 꼬리·겹쳐 쓴 흔적·ODL·보강·계층 요약·나중에 다시 돌릴 목록), 9-9 의 '다시 돌린 아이템이 먼저 나감', 9-10 의 인덱스 확인·선정 수 견주기를 더했다. ⑧ 함정 21 의 '남은 글자'는 DBPIA 스탬프로 확인된 것(조각 D 근거 ①)으로, 섹션 0개 처리는 faf0fac 의 갈래(첫 추출 OCR 실패·데드라인 → `vlm_error`, `short_kept` 0 → `no_text`)대로 적었다. ⑨ 날짜는 2026-10-02, round07 상태는 '구현·리뷰 마무리, 배포 대기'.

**왜:** 배포·카나리·재처리를 사용자가 운영 서버에서 순서대로 따라 할 수 있게 런북에 적고(spec §6), 고친 함정(16번)과 새 함정(21번)을 기록하고, 현재 상태에 round07 진행·적재 진단·round06 기획 중단을 적는다.

**Files:**
- Modify: `docs/ops/bulk_ingest_runbook.md` (§2 기동 명령 두 줄, `## 롤백` 바로 앞에 새 §9)
- Modify: `docs/ops/recurring-gotchas.md` (16번의 "근본 원인" 줄, 16번 "재발 방지" 앞에 "근본 수정", 파일 끝에 21번)
- Modify: `docs/roadmap/00_status.md` (최종 갱신 줄, 현재 상태에 round06·round07·적재 진단, 다음 할 일 맨 앞 두 항목, `[적재] kci-full-236k 완주 뒤` 의 끝 문장, 라운드 이력 두 줄)

**알아 둘 것:**
- 런북 §9 의 명령은 런북의 기존 형식을 따른다 — 관리 API 는 `docker exec nl-lib-fastapi curl … localhost:8000/api/admin/…`(§5-a), DB 는 `docker exec nl-lib-postgres psql -U <user> -d <db> …`(§8, `<user>`·`<db>` 는 운영 값). §9 의 psql 명령(실패분 id 목록·카탈로그 목록·카나리 지표 SQL)은 계획 작성 때 로컬 일회용 Postgres 16 에 같은 표를 만들어 돌려 봤다.
- 런북 §9 는 저장소 compose 를 Portainer 에 통째로 붙이지 말고 바뀐 곳만 옮기라고 쓴다 — 운영 스택은 `flux` 를 주석 처리한 별도 정의다(round04a 완료노트 §8). 통째로 붙이면 FLUX 가 켜진다.
- 9-7 ⑦ 의 로그 확인(`grep -cE '실행 안 함 — (실행 토큰 불일치|토큰 없는 옛 메시지)'`)은 Task 2 의 `_run_stage` 가 체인을 멈출 때 남기는 WARNING 문구(`[book_id] item=N <단계> 실행 안 함 — <이유> → 체인 정지`, 이유가 `실행 토큰 불일치(…)` 또는 `토큰 없는 옛 메시지…`)를 센다.
- 런북 §9 에서 heredoc(`python - <<'PY'`)이 든 코드 블록은 목록 안에 들이지 않고 줄 맨 앞에 둔다 — 원문을 그대로 복사해도 들여쓰기가 섞이지 않는다.
- 문서 파일도 CRLF 다 — Edit 도구로 고친다. `docs/roadmap/00_status.md` 는 다른 세션(round05a 등)도 고치는 파일이라 dev 머지 때 충돌할 수 있다. 충돌하면 양쪽 항목을 다 남긴다.
- 수치는 spec(§1·§2·§4·§6)에서 가져왔다 — 281건(10-01 06:43~07:04 UTC)·「한국문학연구」(1980~2002)·2005년 이전 발행분 표본 6.3%·실패 1,099건(not_found 560 = 섹션 없음 545 + 카탈로그 15, extract_empty 275, llm_error 264)·빈 본문 약 907건(09-03 일시 코드분 약 458)·하루 5,755건·10/19~24.

- [ ] **Step 1: 런북 §2 — 제어 워커 기동**

`docs/ops/bulk_ingest_runbook.md` — 교체 전:

```bash
docker compose up -d celery-cpu celery-llm celery-embed celery-beat
docker compose ps      # 5개 워커 + beat 가 Up 인지 확인
```

교체 후:

```bash
docker compose up -d celery-control celery-cpu celery-llm celery-embed celery-beat
docker compose ps      # 워커(제어·추출·요약·임베딩) + beat 가 Up 인지 확인 — 제어 큐(q_control)는 celery-control 만 받는다
```

- [ ] **Step 2: 런북 §9 — round07 배포 절차 (`## 롤백` 바로 앞)**

`docs/ops/bulk_ingest_runbook.md` — 교체 전:

````markdown
## 롤백
````

교체 후:

````markdown
## 9. round07 배포 — 적재 파이프라인 보강 (2026-10)

round07(spec `docs/superpowers/specs/2026-10-01-round07-ingest-pipeline-fix-design.md`)은 compose 를 바꾼다. `x-common-env` 에 새 설정 11개를 선언하고 추출 stale 판정 기본값을 14400 → 3600초로 줄이며, 제어 큐 `q_control` 은 새 워커 `celery-control`(동시 1, GPU 없음)이 받고 `celery-cpu` 는 `q_cpu` 만 받는다. `x-common-env` 를 물고 있는 앱 서비스가 전부 재생성되므로 적재를 비운 뒤 한 번에 한다(§8, 함정 16번). 아래 명령은 서버의 같은 셸에서 이어 쓴다 — `JOB` 은 본 잡 `kci-full-236k` 다.

> **FLUX 를 켜지 않는다.** 저장소 compose 에는 `flux` 서비스가 살아 있지만 운영 스택은 주석 처리해 두었다(스택 정의와 저장소 compose 가 다르다 — `round04a-완료노트.md` §8). 스택 편집기에 저장소 compose 를 통째로 붙이면 FLUX.1-dev 가 GPU 0 에 올라와 VLM·gemma·임베딩과 GPU 를 나눠 쓴다. round07 전 코드는 논문마다 마무리 단계에서 표지를 만들려 한다(FLUX 가 꺼져 있어 지금은 즉시 실패한다). round07 은 논문 표지를 건너뛰지만, 적재가 도는 동안 FLUX 를 켤 이유는 없다. 그래서 9-3 은 바뀐 곳만 옮긴다.

### 9-1. 비었는지 확인

본 잡은 2026-10-01 에 pause 했다(§8).

```bash
JOB=1ca22f59-1e50-4dd1-81f5-2d3c79126825
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs          # status 가 running 인 잡이 없어야 한다 — 있으면 §8 대로 pause
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$JOB     # "status":"paused", status_counts 에 dispatched·running 이 없다
for q in q_cpu q_llm q_embed; do docker exec nl-lib-redis redis-cli LLEN $q; done   # 셋 다 0
docker exec nl-lib-postgres psql -U <user> -d <db> -c \
  "SELECT id, status FROM research_jobs WHERE status IN ('approved','queued','planning','running')"   # 0행 — celery-research 도 재생성된다
```

### 9-2. 이미지 빌드·받기

운영 스택은 `:latest` 를 쓴다(함정 3번). Portainer 에 pull 을 맡기지 않는다(함정 12번) — pull 만으로는 아무것도 재시작되지 않는다. round07 은 화면을 고치지 않으므로 nuxt 이미지는 그대로다.

```bash
# 개발 PC — 리뷰를 마친 round07 커밋에서
NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
# 서버
docker pull landsoftdocker/nl-lib-fastapi:latest
```

### 9-3. Portainer 스택 업데이트

- 스택 편집기에서 저장소 `docker-compose.yml` 과 견주어 **바뀐 곳만** 옮긴다.
  - `x-common-env`: LLM 묶음에 `LLM_RETRY_ATTEMPTS`·`LLM_RETRY_BACKOFF_SECONDS`, 텍스트 추출 묶음에 `VLM_PAGE_CONCURRENCY`·`SCAN_REPEAT_LINE_RATIO`·`SCAN_SHORT_PAGE_RATIO`·`SCAN_MIN_PAGES`·`ODL_TIMEOUT_BASE_SECONDS`·`ODL_TIMEOUT_PER_PAGE_SECONDS`·`ODL_IMAGE_OUTPUT`, 대량 인덱싱 잡 묶음에 `INGEST_RETRY_BACKOFF_SECONDS`·`INGEST_EXTRACT_DEADLINE`. 그리고 `INGEST_STAGE_TIMEOUT_EXTRACT` 기본값 `14400` → `3600`(위 주석 포함). 새 키는 compose 에 `${이름:-기본값}` 으로 선언돼 있어야 스택 env 로 바꿀 수 있다 — 선언이 없으면 Portainer 가 스택 env 를 무시한다.
  - `celery-cpu` 의 `command`: `-Q q_cpu,q_control` → `-Q q_cpu`.
  - 새 서비스 `celery-control` 블록 전체(바로 위 주석 포함).
  - 주석만 바뀐 곳: `gemma` 의 `--max-num-seqs` 위, `celery-llm` 머리.
- 스택 env(Environment variables)를 본다. `INGEST_STAGE_TIMEOUT_EXTRACT` 가 있으면 지운다 — 있으면 새 기본값 대신 그 값이 들어간다. `MILVUS_RECREATE_ON_MISMATCH` 는 없거나 `false` 여야 한다(fastapi 기동의 `ensure_collection` 이 스키마가 다르면 컬렉션을 지운다 — 함정 16번).
- **"Re-pull image" 토글을 끄고** Update the stack 을 누른다(함정 12번). 500 이 나면 다시 누르기 전에 `docker ps -a --format '{{.Names}}\t{{.CreatedAt}}'` 로 무엇이 바뀌었는지부터 본다.

```bash
docker ps --format '{{.Names}}\t{{.Status}}' | grep nl-lib-celery              # nl-lib-celery-control 이 Up
docker inspect nl-lib-celery-cpu --format '{{join .Config.Cmd " "}}'         # … -Q q_cpu --max-tasks-per-child=50 (q_control 없음)
docker exec nl-lib-celery-control printenv INGEST_STAGE_TIMEOUT_EXTRACT INGEST_EXTRACT_DEADLINE VLM_PAGE_CONCURRENCY   # 3600 / 2700 / 2
docker logs --since 2m nl-lib-celery-control 2>&1 | grep -c dispatch_job_items   # 0 이 아니다 — 30초마다 디스패치 틱을 받는다
```

### 9-4. 게이트웨이 reload

fastapi 가 재생성됐다(함정 20번).

```bash
docker exec nl-lib-gateway nginx -s reload
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health     # 200
```

### 9-5. `MILVUS_RECREATE_ON_MISMATCH` 확인

스택 env 로 본 값이 컨테이너에 들어갔는지 본다(함정 16번).

```bash
docker exec nl-lib-fastapi printenv MILVUS_RECREATE_ON_MISMATCH     # false
```

### 9-6. 카나리 잡

본 잡은 paused 로 둔다. 개발 PC 의 `scripts/bulk_ingest/` 에서 `build_canary_manifest.py`·`select_near_empty_items.py` 를 서버의 `/data/nl-lib/data/round07/` 로 옮긴다(scp 등 — `scripts/` 는 앱 이미지에 없다, 함정 4번).

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round07/build_canary_manifest.py \
  --job $JOB --out /app/data/round07/canary
```

- 범주별 몫·고른 수와 다음 명령 셋(MinIO 업로드 → 잡 생성 → 시작)을 출력한다. 모자란 범주가 있으면 그대로 써도 된다.
- 시작하기 직전에 gemma 완료 사유 카운터를 적어 둔다(9-7 ⑤의 기준).

```bash
docker exec nl-lib-fastapi curl -s gemma:8000/metrics | grep -E '^vllm:request_success_total.*finished_reason="(stop|length)"'
```

- 출력된 명령을 차례로 돌린다. 잡 생성 응답의 `job_id` 를 `CANARY` 에 넣는다 — `CANARY=<잡 생성 응답의 job_id>`.
- `docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$CANARY` 의 `status` 가 `completed`·`completed_with_errors` 가 될 때까지 기다린다.

### 9-7. 카나리 지표

spec §5 의 확인 목록이다.

① 결과와 실패 그룹.

```bash
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$CANARY
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$CANARY/failures
```

② 스캔본이 VLM 으로 가고 섹션이 생겼는가 — 본 잡에서 '섹션 없음'으로 실패했던 문서만 본다. 대부분 `done`·`vlm`·`with_sections` 여야 한다. `no_text` 로 남은 문서는 강제 OCR 까지 해도 글자가 없는 것이다(자동 재시도하지 않는다 — 목록만 남긴다). `vlm_error` 가 많으면 VLM 상태부터 본다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT c.status, c.error_group, c.meta->>'extract_method' AS method, count(*) AS n, count(*) FILTER (WHERE (c.meta->>'sections')::int > 0) AS with_sections, count(*) FILTER (WHERE (c.meta->>'forced_ocr')::boolean) AS forced_ocr, sum((c.meta->>'vlm_truncated')::int) AS vlm_truncated FROM ingest_job_items c JOIN ingest_job_items m ON m.book_id = c.book_id AND m.job_id = '$JOB' WHERE c.job_id = '$CANARY' AND m.status = 'failed' AND m.last_error LIKE '섹션 없음%' GROUP BY 1, 2, 3 ORDER BY 4 DESC"
```

③ embed 단계가 GPU 일만 남아 줄었는가 — 같은 문서의 본 잡(옛 코드) 시간과 견준다. 표 5개 이상 문서의 `embed_after` 가 크게 줄고(진단 때 표 9개 이상 문서의 embed 중앙 24.6초) 그만큼 `summarize_after` 가 는다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT coalesce((m.meta->>'n_tables')::int, 0) >= 5 AS tables_5plus, count(*) AS n, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (m.stage_timings->>'embed_index_s')::float)::numeric, 1) AS embed_before, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (c.stage_timings->>'embed_index_s')::float)::numeric, 1) AS embed_after, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (m.stage_timings->>'summarize_s')::float)::numeric, 1) AS summarize_before, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (c.stage_timings->>'summarize_s')::float)::numeric, 1) AS summarize_after FROM ingest_job_items c JOIN ingest_job_items m ON m.book_id = c.book_id AND m.job_id = '$JOB' WHERE c.job_id = '$CANARY' AND c.status = 'done' AND m.status = 'done' GROUP BY 1 ORDER BY 1"
```

④ 문서 안 VLM 병렬이 도는가 — 스캔본을 추출하는 동안 여러 번 본다. `num_requests_running` 이 2 이상으로 오른다. 4 를 넘으면 문서 안 병렬이 도는 것이다(옛 코드는 추출 4칸이 한 쪽씩이라 4 가 최대였다. 지금은 4 × `VLM_PAGE_CONCURRENCY` 2 = 8 까지).

```bash
docker exec nl-lib-fastapi curl -s vllm:8000/metrics | grep -E '^vllm:num_requests_(running|waiting)'
```

⑤ gemma 잘림 비율 — 9-6 에서 적은 값과의 차이로 (length 증가분) ÷ (stop 증가분 + length 증가분) 을 구한다. 진단 때 5.3%(대부분 표 해석)보다 낮아야 한다.

```bash
docker exec nl-lib-fastapi curl -s gemma:8000/metrics | grep -E '^vllm:request_success_total.*finished_reason="(stop|length)"'
```

⑥ 표 설명이 문장으로 끝나는가 — 카나리 문서의 보강 아티팩트(`artifacts/{book_id}/enrichment.json.gz`)를 본다. `그 밖` 이 0 에 가까워야 한다(잘린 해석은 마지막으로 끝난 문장까지만 남긴다). `python -`(stdin)은 `/app` 에서 돌아 앱 모듈이 보인다(함정 4번).

```bash
docker exec -i nl-lib-fastapi python - <<'PY'
import gzip, json
from core.config import get_settings
from services.ingestion.stages import minio_client
cfg, client = get_settings(), minio_client()
ends = {"문장": 0, "그 밖": 0}
for line in open("/app/data/round07/canary/manifest.jsonl", encoding="utf-8"):
    book_id = json.loads(line)["book_id"]
    try:
        resp = client.get_object(cfg.MINIO_BUCKET, f"artifacts/{book_id}/enrichment.json.gz")
        data = json.loads(gzip.decompress(resp.read()))
        resp.close()
        resp.release_conn()
    except Exception:
        continue
    for table in data["table_chunks"]:
        desc = (table["description"] or "").rstrip()
        if desc:
            ends["문장" if desc.endswith((".", "!", "?", "다")) else "그 밖"] += 1
print(ends)
PY
```

⑦ 중복 체인이 없는가 — 워커 로그에 실행 토큰이 달라 체인을 멈춘 경고(`실행 안 함 — 실행 토큰 불일치` 또는 `실행 안 함 — 토큰 없는 옛 메시지` 줄)가 0건이고, 카나리 아이템에 stale 복구가 없어야 한다. 9-3 에서 워커가 재생성됐으므로 로그는 배포 뒤 것뿐이다.

```bash
for c in nl-lib-celery-cpu nl-lib-celery-llm nl-lib-celery-embed; do echo "$c $(docker logs $c 2>&1 | grep -cE '실행 안 함 — (실행 토큰 불일치|토큰 없는 옛 메시지)')"; done
docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT count(*) FROM ingest_job_items WHERE job_id = '$CANARY' AND (error_group = 'stale' OR last_error LIKE '%stale%')"
```

### 9-8. 본 잡 실패분 재시도

추출부터 다시 돌린다(`reset_stage: "pending"`, spec §4). 먼저 그룹을 본다.

```bash
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$JOB/failures
```

- `not_found` 는 '섹션 없음'만 `item_ids` 로 보낸다. '카탈로그 row 없음'(진단 때 15건)은 카탈로그 문제라 재시도하지 않고 목록만 남긴다 — 행이 지금도 없으면 추출 단계가 PDF 메타 자동추출로 카탈로그 행을 새로 만들고 `doc_type` 이 어긋날 수 있다(§5-b).
- 나머지 그룹은 `error_group` 별로 보낸다. `/failures` 에 다른 그룹(`stale`·`vlm_error` 등)이 보이면 같은 형태로 `error_group` 만 바꿔 보낸다. 응답 `retried` 의 합은 진단 때 기준 545 + 275 + 264 = 1,084건 안팎이다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT id, book_id, last_error FROM ingest_job_items WHERE job_id = '$JOB' AND status = 'failed' AND error_group = 'not_found' AND last_error LIKE '카탈로그 row 없음%'" \
  > /data/nl-lib/data/round07/catalog_missing.txt
IDS=$(docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT coalesce(json_agg(id ORDER BY id), '[]') FROM ingest_job_items WHERE job_id = '$JOB' AND status = 'failed' AND error_group = 'not_found' AND last_error LIKE '섹션 없음%'")
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
  -H 'Content-Type: application/json' -d "{\"item_ids\": $IDS, \"reset_stage\": \"pending\"}"
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
  -H 'Content-Type: application/json' -d '{"error_group": "extract_empty", "reset_stage": "pending"}'
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
  -H 'Content-Type: application/json' -d '{"error_group": "llm_error", "reset_stage": "pending"}'
```

### 9-9. 본 잡 재개

```bash
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/resume
```

- 1~2시간 뒤 `GET …/ingest-jobs/$JOB` 의 `rate_per_hour`(최근 1시간)로 처리량을 잰다. 기대치(추정, spec §2.1)는 ODL 문서 약 340~390건/h, 스캔본 약 80~100건/h 다.
- `rate_per_hour_24h`·`eta_hours`(24시간 기준)는 재개 직후엔 멈춰 있던 시간이 창에 섞여 처리량은 낮게, ETA 는 길게 나온다 — 재개 하루 뒤부터 본다.

### 9-10. 빈 본문 완료분 재처리

본 잡이 도는 동안 해도 된다. `--finished-before` 에는 9-3(스택 업데이트) 시각을 시간대까지 붙여 준다 — 새 코드로 끝난 문서는 다시 돌려도 결과가 같다.

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round07/select_near_empty_items.py \
  --job $JOB --out /app/data/round07 --finished-before <9-3 시각, 예: 2026-10-02T03:00:00+00:00>
```

- 서버의 `/data/nl-lib/data/round07/near_empty_items.csv` 를 사람이 본다(진단 추정 약 900건, 그중 09-03 일시 코드분 약 458건). 뺄 문서가 있으면 `near_empty_retry.json` 의 `item_ids` 에서도 뺀다.
- 재처리는 대부분 VLM 으로 가서 약 1만 쪽·약 10시간(추정)이 든다.

```bash
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
  -H 'Content-Type: application/json' -d @/app/data/round07/near_empty_retry.json
```

## 롤백
````

- [ ] **Step 3: 함정 16번 — 근본 수정**

`docs/ops/recurring-gotchas.md` — 교체 전:

```markdown
  - 근본 원인(단계 래퍼가 `done` 을 보지 않음, stale 복구가 옛 태스크를 revoke 하지 않음)은 적재 코드에 있다. 인덱싱 잡이 도는 동안에는 적재 코드를 고치지 않으므로, 인덱싱이 끝난 뒤의 과제로 남긴다.
```

교체 후:

```markdown
  - 근본 원인(단계 래퍼가 `done` 을 보지 않음, stale 복구가 옛 태스크를 revoke 하지 않음)은 적재 코드에 있다. 인덱싱 잡이 도는 동안에는 적재 코드를 고치지 않으므로 인덱싱이 끝난 뒤의 과제로 남겼다가, round07 에서 적재를 멈추고 고쳤다(아래 **근본 수정**).
```

`docs/ops/recurring-gotchas.md` — 교체 전:

```markdown
- **재발 방지**: 배포 전에 "지금 도는 적재 잡이 있는가"와 "이 배포가 어느 컨테이너를 재생성하는가"를 먼저 본다. 적재 워커를 재생성해야 하면 pause → in-flight 0 확인 → 재생성 → resume 순서로 한다(`bulk_ingest_runbook.md` §8). fastapi 를 재시작하면 lifespan 의 `ALTER TABLE library_catalog` 가 배타 잠금을 기다리는 동안 그 뒤 조회·쓰기가 줄 선다(18번). `MILVUS_RECREATE_ON_MISMATCH` 는 반드시 `false` 인지 확인한다 — fastapi 기동의 `ensure_collection` 이 스키마 불일치 때 컬렉션을 지우는 유일한 경로다.
```

교체 후:

```markdown
- **근본 수정 — round07 (2026-10)**: 위 경로를 적재 코드에서 닫았다(`app/workers/job_runtime.py`).
  - **실행 토큰**: 디스패처가 체인을 보낼 때마다 새 `run_token` 을 아이템 `meta.run_token` 에 적고 단계 태스크 인자로 넘긴다. `_run_stage` 는 토큰이 아이템의 지금 토큰과 다르면(stale 복구로 새 체인이 떴거나 재전달된 옛 메시지) 실행하지 않고 체인을 멈춘다(`celery.exceptions.Ignore`). 토큰 없이 온 배포 전 메시지는 아이템에도 토큰이 없을 때만 돈다.
  - **체크포인트 확인**: 아이템 체크포인트가 이미 그 단계를 지났거나 `done` 이면 멈춘다 — 위 ②의 재전달된 요약·`embed_index` 가 여기서 멈춘다.
  - **락 경합 시 체인 정지**: 락 경합으로 `pending` 으로 되돌린 뒤에도 `skipped` 를 돌려줘 체인이 다음 단계로 가던 것을 멈춘다.
  - **stale 판정 분리**: `_run_stage` 가 시작할 때 `meta.stage_running`·`stage_started_at` 을 적고 끝날 때 지운다. 실행 중이면 그 단계 타임아웃으로, 다음 단계를 기다리는 중이면 대기 상한(`DISPATCH_STALE_SECONDS`)으로 잰다 — 큐 대기를 실행 시간으로 세던 오판(위 '컨테이너를 끊지 않아도 같은 경로가 열린다')이 없어진다.
  - PDF 가 있던 논문(`meta.pages > 0`)인데 추출 아티팩트가 없으면 초록으로 색인하지 않고 `artifact_missing` 으로 멈춘다. 초록 대체는 PDF 없는 메타데이터 전용 논문만 쓴다.
  - **배포 규칙은 그대로다.** 재생성은 여전히 도는 태스크를 끊는다 — 중복 체인은 멈추지만 끊긴 일은 다시 해야 한다. 적재 워커를 재생성할 땐 pause → in-flight 0 → 재생성 → resume 순서로 한다(`bulk_ingest_runbook.md` §8·§9).
- **재발 방지**: 배포 전에 "지금 도는 적재 잡이 있는가"와 "이 배포가 어느 컨테이너를 재생성하는가"를 먼저 본다. 적재 워커를 재생성해야 하면 pause → in-flight 0 확인 → 재생성 → resume 순서로 한다(`bulk_ingest_runbook.md` §8). fastapi 를 재시작하면 lifespan 의 `ALTER TABLE library_catalog` 가 배타 잠금을 기다리는 동안 그 뒤 조회·쓰기가 줄 선다(18번). `MILVUS_RECREATE_ON_MISMATCH` 는 반드시 `false` 인지 확인한다 — fastapi 기동의 `ensure_collection` 이 스키마 불일치 때 컬렉션을 지우는 유일한 경로다.
```

- [ ] **Step 4: 함정 21번 — 새 함정**

`docs/ops/recurring-gotchas.md` 끝에 붙인다(파일 끝 줄바꿈 뒤에 그대로):

```markdown

## 21. 텍스트 층에 몇 글자만 남은 스캔본이 VLM 을 건너뛴다 — ODL 은 머리말·꼬리말을 지우고 fitz 는 그 글자를 센다

- **날짜**: 2026-10-01 (round07)
- **증상**: 2026-10-01 06:43~07:04 UTC 에 섹션 0개로 실패한 아이템 281건이 몰렸다(`not_found` "섹션 없음 — extract 단계부터 재실행 필요"). 전부 「한국문학연구」(1980~2002) 한 블록이었고, 블록이 끝나자 멈췄다 — 고쳐진 게 아니다. 재시도 두 번도 요약 단계에서 같은 실패를 내 1~2분 만에 시도 한도(3)를 다 썼고, 영구 실패로 남았다.
- **원인**:
  - round07 전 쪽 라우팅(`app/services/ingestion/extractor.py` 의 `0 < fitz_check_len < 50` 분기)은 ODL 본문이 짧아도 fitz 도 짧으면 '원래 짧은 쪽'(표지·간지)으로 보고 ODL 결과를 채택했다. 스캔본은 ODL 이 json 의 header/footer 로 머리말·꼬리말을 지워 본문이 "" 인데, fitz 는 텍스트 층에 남은 스탬프·머리말 같은 몇 글자를 세어 0 이 아니게 되고, 그래서 VLM 을 건너뛴다. 남은 글자가 무엇인지는 확인하지 못했다. 두 추출기가 같은 것을 세지 않는 교차검증이었다.
  - 섹션 0개를 추출 성공으로 넘겼다(`run_extract`). 요약이 "섹션 없음"으로 실패하면 체크포인트가 `extracted` 라 재시도가 추출을 다시 하지 않는다.
- **해결 (round07)**:
  - **문서 단위로만 판정한다.** 각 쪽의 짧음은 ODL 본문 길이와, fitz 텍스트에서 문서 쪽의 60% 이상(`SCAN_REPEAT_LINE_RATIO`)에 되풀이되는 짧은 줄(머리말·꼬리말·스탬프)을 뺀 길이로 센다 — ODL 이 지우는 줄을 fitz 쪽에서도 지워야 같은 것끼리 비교가 된다. 3쪽 이상(`SCAN_MIN_PAGES`) 문서에서 짧은 쪽이 절반(`SCAN_SHORT_PAGE_RATIO`)을 넘으면 스캔본으로 보고 짧은 쪽을 OCR 로 보낸다(`app/services/ingestion/page_routing.py`). 「한국문학연구」 블록은 모든 쪽이 짧은 쪽이라 여기서 잡힌다.
  - **쪽 단위 이미지 규칙은 쓰지 않는다(표지 되돌림 방지).** 쪽 하나만 보면 '스탬프만 남은 스캔 본문 쪽'과 '스탬프만 남은 이미지 표지'를 구분할 수 없다. 쪽 면적 이미지 규칙처럼 쪽마다 OCR 로 보내면 표지·간지를 다시 VLM 으로 보내 d85df93 의 수정(50자 미만 트리거가 VLM 호출의 90% 이상이던 것을 fitz 교차검증으로 고친 것)을 되돌린다. 스캔본이 아닌 문서는 전과 같다 — 원래 짧은 쪽은 ODL 을 채택하고, CMap 손상 2배 판정·fitz 0자 → OCR·표 셀 충전율 판정도 그대로다.
  - 그래도 섹션이 0개면 짧은 쪽을 전부 OCR 로 보내 한 번 더 추출한다. 그래도 0개이고 OCR 오류가 없었으면 `no_text`(결정적 — 자동 재시도하지 않는다), OCR 오류가 있었으면 `vlm_error`(추출부터 자동 재시도)다.
  - 이미 실패한 아이템은 배포 뒤 `reset_stage: "pending"` 으로 추출부터 다시 돌린다(`bulk_ingest_runbook.md` §9-8).
- **재발 방지**: 서로 다른 추출기로 교차검증할 땐 둘이 같은 것을 세는지(머리말·꼬리말을 누가 지우는지)부터 맞춘다. 표지와 스캔 쪽처럼 쪽 하나로는 가를 수 없는 판정은 문서 단위 신호로 한다. 섹션 0개처럼 같은 입력에 같은 결과가 나오는 실패는 재시도할 그룹과 나눠, 재시도가 같은 일을 되풀이하며 한도를 태우지 않게 한다. 남은 pending 의 2005년 이전 발행분(표본 6.3%)에서 같은 제작 방식의 학술지가 또 나올 수 있다(수백 건 추정) — 카나리의 `scan_no_sections` 범주와 `/failures` 의 `no_text` 로 본다.
```

- [ ] **Step 5: `docs/roadmap/00_status.md`**

`docs/roadmap/00_status.md` — 교체 전:

```markdown
최종 갱신: 2026-10-01 (round04b·round04c 종료 — `dev`·`main` 머지와 `origin` push. round05a 진행 중)
```

교체 후:

```markdown
최종 갱신: 2026-10-01 (round04b·round04c 종료 — `dev`·`main` 머지와 `origin` push. round05a·round07 진행 중, round06 기획 중단)
```

`docs/roadmap/00_status.md` — 교체 전:

```markdown
- **적재 현황(2026-09-29)** — `kci-full-236k` 47%: done 111,658 / pending 123,979 / failed 782. 항목 번호(옛 논문) 순으로 돌아 딥리서치 코퍼스가 아직 2013년까지다. 하루 약 5,200건 → **10월 23일쯤 완료 예상(목표 10월 28일)**. 최신순 재배열은 하지 않기로 했다.
```

교체 후:

```markdown
- **round06 — 기획 중단** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색 → 주제 후보·읽기 목록 → 연구계획서형 초안)으로 넓히는 브레인스토밍. 브랜치 `feat/round06-paper-agent`(dev `138a467` 에서 분기, worktree `.worktrees/round06`). 2026-10-01 기술 구조(설계 ③)와 검증 기준까지 승인된 상태에서 적재 수정(round07)을 먼저 하려고 멈췄다 — 일정(④)이 남았고, spec 은 아직 쓰지 않았다.
- **round07 — 진행 중** — 적재 파이프라인 보강. 브랜치 `feat/round07-ingest-pipeline-fix`(dev `9798f46` 에서 분기, worktree `.worktrees/round07`), 설계 `docs/superpowers/specs/2026-10-01-round07-ingest-pipeline-fix-design.md`, 계획 `docs/superpowers/plans/2026-10-01-round07-ingest-pipeline-fix.md`. 본 잡 `kci-full-236k` 는 2026-10-01 사용자가 pause 했다(in-flight 0, 08:11 UTC 확인) — 배포(`bulk_ingest_runbook.md` §9) 전까지 그대로 둔다.
- **적재 현황(2026-09-29)** — `kci-full-236k` 47%: done 111,658 / pending 123,979 / failed 782. 항목 번호(옛 논문) 순으로 돌아 딥리서치 코퍼스가 아직 2013년까지다. 하루 약 5,200건 → **10월 23일쯤 완료 예상(목표 10월 28일)**. 최신순 재배열은 하지 않기로 했다.
- **적재 진단(2026-10-01, round07 착수 근거)** — 48시간 완료 11,510건(하루 5,755건). 병목 두 곳이 번갈아 막는다. 일반 PDF(ODL) 문서는 `celery-embed` 1칸 안에서 논문 보강 LLM 을 기다리는 시간(embed 의 46~59%) 때문에 약 300건/h, 스캔본은 쪽을 하나씩 OCR 하는 추출 4칸 때문에 약 50건/h 다. GPU 서버는 여유가 있다(gemma 평균 5~8/16석, VLM 1.9/8석). 결함도 여럿이다 — 텍스트 층에 몇 글자만 남은 스캔본이 VLM 을 건너뛰어 섹션 0개로 영구 실패하고(10-01 281건, 함정 21번), 문서 요약 입력의 균등 샘플링이 마지막 섹션을 빼고, LLM·VLM 잘림을 감지하지 않으며(gemma 응답 5.3%·VLM 3.8%), 빈 본문으로 완료된 문서가 약 900건(추정)이고, 중복 체인이 논문 본문을 초록으로 덮는 경로(함정 16번)가 열려 있다. 고칠 것 18개는 spec §2, 재처리는 실패 1,099건과 빈 본문 완료분만 배포 직후에 한다. 지금 설정이면 남은 약 11.3만 건은 10/19~24 완료로 추정했다(잡 API 의 ETA 856시간은 스캔본이 몰린 1시간 창 값이었다).
```

`docs/roadmap/00_status.md` — 교체 전:

```markdown
## 다음 할 일
```

교체 후:

```markdown
## 다음 할 일
- **round07 진행** — `feat/round07-ingest-pipeline-fix` 에서 계획의 Task 0~12 구현 → 리뷰 → 배포(`bulk_ingest_runbook.md` §9: 비움 확인 → 이미지 pull → 스택 업데이트 → 카나리 → 실패분 retry → 본 잡 resume → 빈 본문 목록 retry). 그때까지 본 잡은 paused 로 둔다. 스택을 업데이트할 때 **FLUX 를 켜지 않는다**(§9). 이번에 하지 않기로 한 것(임베딩 512 절단 등)은 spec §3.
- **round06 재개** — round07 배포와 본 잡 재개 뒤 `.worktrees/round06` 에서 브레인스토밍 일정(④)부터 이어 spec 을 쓴다.
```

`docs/roadmap/00_status.md` — 교체 전:

```markdown
- **[적재] `kci-full-236k` 완주 뒤** — ① 추가 수집: 메타 없는 PDF 28,074편, 연도별 1만 건 상한 뒤 나머지(수집기가 KCI 검색 200쪽 상한을 봇 탐지로 오인한다) ② 모델 교체: Qwen3.6-35B-A3B-FP8 로 OCR·텍스트 통합 검토. 둘 다 적재가 끝난 뒤 한다. 적재 코드의 근본 원인(단계 래퍼가 `done` 을 보지 않음·stale 복구가 옛 태스크를 revoke 하지 않음 — 함정 16번)도 그때 고친다.
```

교체 후:

```markdown
- **[적재] `kci-full-236k` 완주 뒤** — ① 추가 수집: 메타 없는 PDF 28,074편, 연도별 1만 건 상한 뒤 나머지(수집기가 KCI 검색 200쪽 상한을 봇 탐지로 오인한다) ② 모델 교체: Qwen3.6-35B-A3B-FP8 로 OCR·텍스트 통합 검토. 둘 다 적재가 끝난 뒤 한다. 적재 코드의 근본 원인(단계 래퍼가 `done` 을 보지 않음·stale 복구가 옛 태스크를 revoke 하지 않음 — 함정 16번)은 round07 에서 고친다.
```

`docs/roadmap/00_status.md` — 교체 전:

```markdown
| round05a | 논문 상세 재구현(돌아가기·주소·보던 위치 복원) | 진행 중 (`feat/round05a-paper-detail`) |
```

교체 후:

```markdown
| round05a | 논문 상세 재구현(돌아가기·주소·보던 위치 복원) | 진행 중 (`feat/round05a-paper-detail`) |
| round06 | 논문 에이전트 플랫폼(딥리서치 → 주제 후보·읽기 목록·계획서 초안) | 기획 중단 (`feat/round06-paper-agent`, 브레인스토밍 ③까지 승인) |
| round07 | 적재 파이프라인 보강(병목 두 곳·스캔본 라우팅·중복 체인 차단) | 진행 중 (`feat/round07-ingest-pipeline-fix`) |
```

- [ ] **Step 6: 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && grep -n "^## 9\. \|^### 9-\|^## 롤백" docs/ops/bulk_ingest_runbook.md`

Expected (12줄):
```
201:## 9. round07 배포 — 적재 파이프라인 보강 (2026-10)
207:### 9-1. 비었는지 확인
220:### 9-2. 이미지 빌드·받기
231:### 9-3. Portainer 스택 업데이트
248:### 9-4. 게이트웨이 reload
257:### 9-5. `MILVUS_RECREATE_ON_MISMATCH` 확인
265:### 9-6. 카나리 잡
284:### 9-7. 카나리 지표
353:### 9-8. 본 잡 실패분 재시도
378:### 9-9. 본 잡 재개
387:### 9-10. 빈 본문 완료분 재처리
404:## 롤백
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && grep -c "근본 수정" docs/ops/recurring-gotchas.md && grep -n "^## 2[01]\." docs/ops/recurring-gotchas.md`

Expected:
```
2
191:## 20. 컨테이너를 개별 Recreate 하면 nginx 게이트웨이가 옛 IP 로 보내 502 가 난다
214:## 21. 텍스트 층에 몇 글자만 남은 스캔본이 VLM 을 건너뛴다 — ODL 은 머리말·꼬리말을 지우고 fitz 는 그 글자를 센다
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && grep -c "round07" docs/roadmap/00_status.md && grep -n "^| round0[67] " docs/roadmap/00_status.md`

Expected:
```
8
61:| round06 | 논문 에이전트 플랫폼(딥리서치 → 주제 후보·읽기 목록·계획서 초안) | 기획 중단 (`feat/round06-paper-agent`, 브레인스토밍 ③까지 승인) |
62:| round07 | 적재 파이프라인 보강(병목 두 곳·스캔본 라우팅·중복 체인 차단) | 진행 중 (`feat/round07-ingest-pipeline-fix`) |
```

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && git diff --stat -- docs/ops/bulk_ingest_runbook.md docs/ops/recurring-gotchas.md docs/roadmap/00_status.md`

Expected: 이 세 파일만 나온다.

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/.worktrees/round07 && git add docs/ops/bulk_ingest_runbook.md docs/ops/recurring-gotchas.md docs/roadmap/00_status.md && git status --short && git commit -m "[Docs] round07 — 배포·카나리·재처리 런북(§9: 비움 확인 → 이미지 pull → Portainer 스택은 바뀐 곳만 옮겨 Re-pull 끄고 업데이트(FLUX 를 켜지 않는다) → nginx reload → MILVUS_RECREATE_ON_MISMATCH=false 확인 → 카나리 잡과 지표 일곱 가지 → 실패분을 error_group 별로 reset_stage pending 재시도('카탈로그 row 없음'은 목록만) → 본 잡 resume → 빈 본문 목록 재처리)과 §2 기동 명령에 celery-control. 함정 16번에 round07 근본 수정(실행 토큰·체크포인트 확인·락 경합 시 체인 정지·stale 판정 분리·아티팩트 없는 논문 정지), 새 함정 21번(텍스트 층에 몇 글자만 남은 스캔본이 VLM 을 건너뛴다 — 문서 단위로만 판정하고 쪽 단위 이미지 규칙은 쓰지 않는다). 00_status 에 round07 진행·적재 진단·round06 기획 중단"
```
