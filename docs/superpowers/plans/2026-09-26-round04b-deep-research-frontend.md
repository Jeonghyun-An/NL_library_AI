# round04b 딥리서치 화면·기록 세션 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** round04a 딥리서치 백엔드에 화면을 붙인다. 논문 입력창 앞 `+` 메뉴(또는 `/deep-research`)로 잡을 만들고, `/research/<job_id>` 에서 계획 승인 → 진행(회차 타임라인·자기점검 강조·카운터) → 보고서(인용칩)를 본다. 함께 사이드바 기록을 서버 테이블 `history_items` 정본 + 브라우저 캐시·보낼 편지함(outbox) 구조로 바꿔 spec §1-2 의 H1~M9 를 해소한다. 기존 테이블·데이터는 한 줄도 바꾸지 않는다.

**Architecture:** 백엔드는 새 테이블 하나(`history_items`)와 얇은 기록 API(`/api/history` — 소유 단위는 헤더 `x-session-id` 의 브라우저 ID)를 더한다. 딥리서치 워커·API 는 기존 JSONB 칸(`research_steps.result`·보고서 JSON)과 기존 컬럼만 써서 상태·단계·회차·카운터·절 진행을 SSE 로 흘리고 **같은 내용을 저장한다**(라이브로 볼 때와 다시 열 때 같은 장면). 프론트는 순수 로직(`utils/*.ts` — 기록 저장소·URL 규칙·SSE 리듀서·인용 분해·슬래시 파서)과 Nuxt 결합부(`composables/*`·컴포넌트·페이지)를 파일 단위로 갈라, 순수 부분만 Vitest 로 검증한다. 딥리서치 화면은 별도 컴포넌트·CSS(`components/research/*`·`assets/css/research.css`)로 두고 기존 입력창에는 `+` 컴포넌트 한 줄만 끼운다.

**Tech Stack:** FastAPI · SQLAlchemy 2(async · Core 문장) · Pydantic 2 · Alembic · Celery · Redis pub/sub · pytest / Nuxt 4 · Vue 3.5 · ofetch(`$fetch.create`) · EventSource · Vitest 3

**설계 근거:** `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md`(이하 spec). 선행 계획: `docs/superpowers/plans/2026-09-21-round04a-deep-research-backend.md`.

**실행 전 확인:** docker·비동기·배포 작업 전 `docs/ops/recurring-gotchas.md` 를 읽는다. 특히 13번(torch 를 끌어오는 모듈을 최상단에서 import 하지 않는다), 14번(운영 스키마는 lifespan `create_all` 이 만든다 — 배포 뒤 `alembic stamp`), 16번(앱 서비스가 모두 같은 `:latest` 이미지 — 스택 업데이트 금지, 컨테이너별 Recreate), 18번(DB 세션을 쥔 채 LLM 을 기다리지 않는다).

**계획 작성 시 검증:** 태스크 코드는 저장소 밖 사본에서 실제로 돌려 보고 옮겼다.
- 백엔드: 영역 A·B 를 합친 사본에서 전체 **728 passed**(기준선 549 + A 109 + B 70). 각 태스크의 "실패 확인" 출력도 사본 실측이다.
- 프론트 순수 모듈: 이 문서의 코드 블록을 그대로 꺼내 만든 사본에서 Vitest 3.2 로 **14파일 158 tests passed**, 영역 C2 순수 모듈은 엄격 옵션 `tsc` 오류 0.
- 영역 C2 컴포넌트·페이지는 C2 사본에서 `nuxi typecheck`(새 파일 오류 0)·`nuxt build`·가짜 API 브라우저 확인을 거쳤다. 통합 때 고친 세 곳(Task 29 의 사이드바 갱신, Task 31 의 `safeLocalStorage`, Task 34 의 `apiHeaders`)은 타입검사를 다시 돌리지 않았다.
- **영역 C1 의 사이드바·페이지 통합(Task 21~25)은 실행하지 않은 코드다.** 각 태스크의 grep·빌드·수동 확인과 Task 36 의 `nuxi typecheck` 가 방어선이다.

---

## 테스트 명령

**백엔드**(저장소 루트):

```bash
python -m pytest app/tests -q --ignore=app/tests/test_book_chat.py --ignore=app/tests/test_build_manifest.py --ignore=app/tests/test_loaders.py
```

기준선 **549 passed**. 제외한 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 실패한다(이 계획과 무관). 로컬에는 torch·redis·celery·Postgres·aiosqlite 가 없다 — 테스트는 대역과 표준 `sqlite3` 로 돈다. 비동기 코드는 `asyncio.run(...)` 으로 부른다(pytest-asyncio 없음). 경고 2건(Pydantic class-based config)은 기존 것이다.

**프론트**(Task 13 이후, 테스트 파일은 `frontend/tests/unit/`):

```bash
cd frontend && npx vitest run tests/unit/<이름>.test.ts   # 한 파일
cd frontend && npm test                                   # 전체
```

Nuxt 페이지·컴포넌트·composable 의 Nuxt 결합부는 단위 테스트하지 않는다 — `npm run build`·`npx nuxi typecheck`·grep·수동 화면 확인으로 본다. 테스트 대상 모듈은 `~/utils/…`·`~/types/…` 로 명시 import 한다(Nuxt 자동 import 에 기대지 않는다).

**누적 기대치** — 이 문서의 태스크 순서대로 적용했을 때의 값이다.

| 태스크 뒤 | 백엔드 passed | 태스크 뒤 | 프론트 파일 / tests |
|---|---|---|---|
| Task 1 | 560 | Task 13 | 1 / 4 |
| Task 2 | 576 | Task 15 | 2 / 15 |
| Task 3 | 624 | Task 16 | 3 / 22 |
| Task 4 | 658 | Task 17 | 4 / 54 |
| Task 5 | 669 | Task 18 | 5 / 71 |
| Task 6 | 680 | Task 19 | 6 / 81 |
| Task 7 | 685 | Task 20 | 7 / 92 |
| Task 8 | 696 | Task 27 | 9 / 113 |
| Task 9 | 702 | Task 28 | 10 / 137 |
| Task 10 | 716 | Task 29 | 12 / 149 |
| Task 11 | 719 | Task 31 | 13 / 153 |
| Task 12 | **728** | Task 34 | **14 / 158** |

## 커밋 규칙

- 메시지는 `[Feat] round04b — …` 처럼 대괄호 접두사(`[Feat]`·`[Fix]`·`[Refactor]`·`[Chore]`·`[Docs]`·`[Test]`)로 쓴다. 태스크 하나 = 커밋 하나.
- **`Co-Authored-By`·"Generated with Claude Code" 같은 트레일러를 절대 붙이지 않는다**(사용자 단독 저자).
- 코드 주석은 "왜"만, 한국어로 쓰고 태스크 번호를 적지 않는다(`docs/standards/coding-standard.md`).
- 작업 트리의 기존 파일은 CRLF 다(`core.autocrlf=true`). 기존 파일은 Edit 도구로 고쳐 줄바꿈을 유지한다. 새 파일은 LF 로 써도 커밋 때 정규화된다.
- 기존 파일을 고치는 Step 의 줄 번호는 **착수 시점(브랜치 `feat/round04b-deep-research-frontend`, `ae00bfd`) 기준 참고값**이다. 앞 태스크가 같은 파일을 고쳤으면 줄이 밀리므로 "교체 전" 코드 문자열로 찾는다.

---

## 파일 구조

| 파일 | 책임 | Task |
|---|---|---|
| `app/models/history.py` | `HistoryItem` ORM · `HISTORY_KINDS` | 1 |
| `app/alembic/versions/0006_history_items.py` | 테이블·부분 인덱스 마이그레이션 | 1 |
| `app/alembic/env.py` · `app/main.py` | 모델 등록(1) · 라우터 등록(4) | 1·4 |
| `app/core/deps.py` | `get_browser_id` · `get_browser_id_optional` | 2 |
| `app/schemas/history.py` | 기록 API 입출력 스키마 | 3 |
| `app/repositories/history.py` | `HistoryRepository` · `legacy_history_id` · 커서 | 3 |
| `app/api/history.py` | 얇은 라우터(`/api/history` — 400·404·413 매핑, 쓰기 후 커밋) | 4 |
| `app/services/research/state.py` | `ResearchState.seen_cnts` · `SubQuestion.rounds` · `research_stats()` | 5 |
| `app/services/research/runner.py` | 회차·새 논문·다음 검색어·`counters` 이벤트, 회차 이력 | 6 |
| `app/services/research/synthesizer.py` | `on_section` 콜백 · 보고서 `stats` | 7 |
| `app/workers/research_tasks.py` | `step`·`status` 이벤트(8), 단계 result 의 `rounds`·`sections`(9), 진행 중 result 갱신(12) | 8·9·12 |
| `app/models/research.py` | `ResearchStep.result` 모양 주석만 | 9·12 |
| `app/api/research.py` | 스냅샷 `result`·`job`, GET 시각·`params`, 승인·재시도 `status`, `created_by`(10), 하트비트 스냅샷 재전송(11), 스냅샷 `job.counters`(12) | 10·11·12 |
| `app/tests/history_sqlite.py` 외 `test_history_*.py`·`test_browser_id.py` | 기록 백엔드 테스트(동기 SQLite 를 감싼 AsyncSession 대역) | 1~4 |
| `app/tests/test_research_{state,runner,synthesizer,tasks,api}.py` | 딥리서치 보강 테스트(기존 파일에 추가) | 5~12 |
| `frontend/package.json` · `frontend/vitest.config.ts` · `frontend/tests/unit/helpers/*` | Vitest 도입(`include: tests/unit/**/*.test.ts`, 별칭 `~/`) | 13 |
| `frontend/types/history.ts` | 기록 타입 v2(유니온·축약 결과·서버 선 모양) | 14 |
| `frontend/utils/browserId.ts` · `composables/useBrowserId.ts` · `composables/useApi.ts` | 브라우저 ID 한 벌 · `x-session-id` 자동 첨부 | 15 |
| `frontend/utils/historySnapshot.ts` | 복원용 축약 결과(허용 필드 목록, 최대 20건) | 16 |
| `frontend/utils/historyStore.ts` | 서버·로컬·하이브리드 저장소, outbox, 쿼터, v1 이전, 10분 중복 판정 | 17·18 |
| `frontend/utils/historyRoute.ts` | 기록 ↔ URL 규칙(`?h=`·`restore` 별칭·v1 id) | 19 |
| `frontend/utils/historyState.ts` · `composables/useHistory.ts` | 목록 상태(순수) · 앱 싱글톤·탭 동기화·v1 이전 트리거 | 20 |
| `frontend/components/AppSidebar.vue` | 3탭·삭제·딥리서치 배지·라우트 강조(재작성) | 21 |
| `frontend/pages/index.vue` · `pages/papers/index.vue` | URL 복원·스트림 경합 해소(22·23), `+` 한 줄(35) | 22·23·35 |
| `pages/books/[cnts_id].vue` · `pages/papers/[id].vue` · `pages/recommend/[id].vue` · `components/BookChat.vue` · `components/CitationModal.vue` | 복원 분기 제거·헤더 첨부 | 24 |
| 삭제: `pages/search-classic.vue` · `components/ChatHistory.vue` · `composables/useSearch.ts` · `composables/useSearchHistory.ts` | 잔재 정리(M9) | 25 |
| `frontend/types/research.ts` | 딥리서치 API·보고서·SSE·화면 상태 타입 | 26 |
| `frontend/utils/citations.ts` · `utils/slashCommand.ts` | 인용 마커 분해·칩 라벨·쪽수 · `+` 메뉴 데이터·슬래시 파서 | 27 |
| `frontend/utils/researchEvents.ts` | SSE 리듀서(`initialResearchView`·`applyResearchEvent`) | 28 |
| `frontend/utils/researchErrors.ts` · `utils/researchInput.ts` · `composables/useResearch.ts` | 422·409·429·503 처리 · 입력 검증 · SSE 수명주기 | 29 |
| `frontend/nuxt.config.ts` | devProxy 대상 환경변수화(30) · `research.css` 등록(31) | 30·31 |
| `frontend/utils/researchLayout.ts` · `assets/css/research.css` · `components/research/ResearchHeader.vue` · `pages/research/[id].vue` | 배치 A/B · 전용 CSS · 머리 · 상태 기계 | 31 |
| `frontend/components/research/PlanCard.vue` | 계획 카드 | 32 |
| `frontend/components/research/ProgressPanel.vue` | 진행 패널 | 33 |
| `frontend/utils/researchReport.ts` · `components/research/{CitationChip,ReportView}.vue` · `components/PdfViewer.vue` | 보고서·인용칩·원문 쪽 열기(`page` prop) | 34 |
| `frontend/components/research/SearchPlusMenu.vue` | 입력창 `+` 메뉴 | 35 |
| `docs/roadmap/00_status.md` · 이 문서 | 상태 갱신·체크박스 | 38 |

적재 코드(`app/services/ingestion/`·`workers/tasks.py`·`workers/job_runtime.py`)와 기존 테이블(`search_history`·`search_sessions`·`library_catalog` 등)은 건드리지 않는다.

---

## 실행 단계

| 단계 | 태스크 | 내용 | 선행·병렬 |
|---|---|---|---|
| 1 | Task 1~4 (영역 A) · Task 5~12 (영역 B) | 기록 백엔드 · 딥리서치 이벤트 보강 | A 와 B 는 파일이 겹치지 않아 **병렬 가능**. 단 Task 10(`POST /api/research` 의 `created_by`)은 Task 2(`get_browser_id_optional`) 뒤. 영역 안은 번호 순 |
| 2 | Task 13~25 (영역 C1) | Vitest · 기록 타입·저장소·URL·`useHistory` · 사이드바 · 페이지 통합 · 잔재 삭제 | Task 13~20 은 단계 1 과 병렬 가능. Task 21 이후의 수동 확인은 기록 API(Task 4)가 필요하다. Task 13~21 은 기존 화면을 깨지 않고 Task 22~25 가 페이지를 옮긴다 |
| 3 | Task 26~35 (영역 C2) | 딥리서치 타입·순수 로직·composable·페이지·블록·`+` 메뉴 | Task 26~28 은 Task 13 뒤면 단계 2 와 병렬 가능. Task 29 이후는 Task 15·20 뒤, Task 35 는 Task 22·23 뒤(같은 페이지 파일). 화면이 온전히 움직이는 것은 영역 B 이후다 |
| 4 | Task 36~38 | 통합 검증 · 운영 배포와 라이브 검증 · 문서 갱신 | 전부 뒤. Task 37 은 **사용자 승인 뒤**에만 한다(공유 운영 서버) |

배포는 Task 37 에서 한 번에 한다(spec §10) — 중간 태스크에서 서버에 올리지 않는다.

---

## 영역 간 계약(최종)

영역 사이에서 주고받는 이름·모양의 정본이다. 태스크 코드는 이 표와 일치하도록 맞췄다.

### 기록 백엔드(영역 A → C1)

- 테이블 `history_items`: `id` UUID PK(브라우저가 만든 값 — ORM 기본값 없음) · `session_id` UUID NOT NULL · `user_id` VARCHAR(64) NULL(로그인 자리) · `kind` VARCHAR(16) · `title` TEXT · `params` JSONB NOT NULL DEFAULT `'{}'` · `snapshot`·`ai` JSONB NULL(`none_as_null`) · `ref_id` VARCHAR(64) NULL · `created_at`·`updated_at` TIMESTAMPTZ NOT NULL DEFAULT now() · `deleted_at` TIMESTAMPTZ NULL. 부분 인덱스 `ix_history_items_session_kind_created (session_id, kind, created_at DESC) WHERE deleted_at IS NULL`. Alembic `0006_history_items`(down `0005_research_jobs`).
- 의존성(`app/core/deps.py`): `get_browser_id` — 헤더 `x-session-id` 가 없거나 UUID **v4** 가 아니면 400 `"x-session-id 헤더가 필요하다"`. `get_browser_id_optional` — 같은 조건에서 `None`.
- 스키마(`app/schemas/history.py`): `HistoryKind = Literal["book","paper","research"]` · `HistoryItemIn{kind, title(공백 제거 후 1~500자), params={}, snapshot?, ai?, ref_id?(≤64)}` — `kind="research"` 면 `ref_id` 필수 · `HistoryItemPatch{title?, params?, snapshot?, ai?}`(`title`·`params` 에 null 금지) · `ResearchStatus{status, stage}` · `HistoryItemOut{id, kind, title, params, ref_id, created_at, updated_at, has_snapshot, has_ai, research}` · `HistoryItemDetail(+snapshot, ai)` · `HistoryListOut{items, next_cursor}` · `HistoryImportItem(HistoryItemIn + id?, legacy_id?, created_at?)` · `HistoryImportIn{items ≤100}` · `HistoryImportOut{imported, skipped, id_map}`.
- API(`/api/history`, 전부 헤더 필수):

  | 메서드·경로 | 성공 | 실패 |
  |---|---|---|
  | `GET ?kind=&limit=30&before=` | 200 `HistoryListOut` | 헤더·틀린 커서 400 · `kind`/`limit`(1~100) 422 |
  | `GET /{id}` | 200 `HistoryItemDetail` | 남의 것·없는 것·지운 것 404 · id 형식 422 |
  | `PUT /{id}` | 200 `HistoryItemDetail` | snapshot 200KB(UTF-8 204,800바이트) 초과 413 · 남의 것 404 · research 인데 `ref_id` 없음 422 |
  | `PATCH /{id}` | 200 | 413 · 404 · `title`/`params` null 422 |
  | `DELETE /{id}` | 204(이미 지운 내 것도 204) | 404 |
  | `DELETE ?kind=` | 204 | `kind` 없음 422 |
  | `POST /import` | 200 `HistoryImportOut` | 101건 이상 422. 200KB 넘는 snapshot 은 그 항목의 snapshot 만 버리고 옮긴다 |

- PUT 의미: 같은 id 재전송은 upsert — `created_at=now()` 로 **목록 맨 위로** 오고, 요청에 없는(null) `snapshot`·`ai`·`ref_id` 는 기존 값을 지키며, 지운 내 기록은 되살아난다. 비우려면 `PATCH {snapshot: null}`.
- 딥리서치 상태는 저장하지 않는다 — 조회할 때 한 쪽의 `ref_id` 를 모아 `research_jobs` 를 PK `IN` 으로 한 번 더 읽어 `research: {status, stage} | null` 로 붙인다(`ref_id = id::text` 조인은 PK 인덱스를 못 쓰고, `ref_id::uuid` 캐스팅 조인은 형식이 틀린 값 하나에 목록 전체가 실패한다).
- 커서 `"<created_at ISO>|<id>"` 를 `before` 로 그대로 되돌린다(`+` 가 들어 있으니 쿼리 인코딩 — 서버는 공백으로 풀린 `+` 도 받는다). v1 id → `legacy_history_id(v1) = uuid5(NAMESPACE_URL, "nl-lib-history-v1:" + v1)`, `id_map` 은 건너뛴 항목도 담는다. import id 우선순위 `id` > `legacy_id` > 서버 `uuid4`.

### 딥리서치 이벤트·저장(영역 B → C2)

| kind | payload | 발행처 |
|---|---|---|
| `snapshot` | `{steps:[{seq, kind, subq_idx, title, detail, status, result}], job:{status, stage, plan, counters?}}` — steps 는 `GET` 과 같은 모양(단계 종류 키 `kind`). `counters` 는 끝난 잡이면 `report.stats`, 도는 잡이면 단계 result 에 마지막으로 남은 값, 없으면 키가 없다 | API 스트림 연결 직후 · 스트림 하트비트(DB 상태·단계가 화면이 아는 값과 다르거나, 계획이 생겼는데 화면에 준 적이 없으면 다시 읽어 같은 모양으로 한 번 더) |
| `status` | `{status, stage}` — `planning`·`awaiting_approval`·`approved`·`queued`·`running`(stage `planned`/`explored`). 종료 상태는 내지 않는다 | 워커 · API(승인·재시도, 되돌린 승인). 스트림 하트비트는 놓친 전이를 status 가 아니라 snapshot 으로 되살린다(계획 원안까지 함께) |
| `step` | `{seq, step_kind, subq_idx, title, detail, status, result?}` — 열 때 `running`(result 없음), 탐색 중 회차가 끝날 때·종합 중 절이 바뀔 때 `running` + 지금까지의 result, 닫을 때 `done`/`failed` + 저장한 result 그대로 | 워커 |
| `search` | `{subq_idx, query, found, round(1부터), new_papers}` | 러너 |
| `counters` | `{papers_reviewed, evidence_adopted, rechecks}` — 잡 전체·고유 논문, 검색 결과를 근거로 묶은 직후 회차마다 | 러너 |
| `critique` | `{subq_idx, verdict, note, adopted, parse_failed, capped, round, next_query, will_recheck}` — `next_query` 는 다음 회차에 **실제로** 검색할 검색어(안 하면 null), `will_recheck = next_query != null` | 러너 |
| `synth` | `{section_idx(절 순번, 0부터), total(근거 있는 하위질문 수), status: running→done/failed}` | 워커(`synthesize` 의 `on_section`) |
| `done`·`failed`·`canceled` | 기존 종료 프레임 `{kind, status, error?}` — `stage`·보고서가 없으므로 화면은 받으면 `EventSource` 를 닫고 `GET` 으로 다시 읽는다 | 기존 그대로 |

- `research_steps.result`: search = `{queries, adopted, verdict, note, parse_failed, capped, rounds:[{round, query, found_chunks, new_papers, verdict, note, next_query}], counters}` (실패하면 `{error, rounds, counters}`) · synthesize = `{sections_total, sections:[{idx, status}]}` (실패·취소면 `error` 추가). 보강 전 잡은 search 에 `rounds` 가 없고(화면은 `report.trail` → `queries` 순으로 대체) synthesize 는 `{sections: <정수>}` 다.
- 보고서 JSON 에 `stats:{papers_reviewed, evidence_adopted, rechecks}` 추가(기존 키 무변경). `ResearchState.seen_cnts`(스냅샷 왕복, 옛 스냅샷은 채택 근거로 하한).
- `GET /api/research/{id}` += `params`·`created_at`·`started_at`·`finished_at`(ISO). `created_by` 는 싣지 않는다(소유 확인이 없는 응답에 남의 브라우저 ID 가 나가면 그걸로 그 사람의 기록을 읽을 수 있다). `POST /api/research` 는 `get_browser_id_optional` 로 `created_by` 를 채우고 헤더가 없어도 잡을 만든다.
- `synthesize(state, *, should_stop=None, on_section=None)` — `on_section(idx, total, status)` 는 async 콜백.

### 프론트 공통(영역 C1 → C2)

- `utils/browserId.ts`: `isUuidV4(s)` · `readOrCreateBrowserId(storage, gen)` · `generateUuidV4()` · `safeLocalStorage()` · `BROWSER_ID_KEY="sid"`. `composables/useBrowserId.ts`: `useBrowserId(): string`(서버 렌더에서는 `""`).
- `composables/useApi.ts`: `useApi()` = `$fetch.create({ baseURL: apiBase, onRequest: x-session-id 첨부 })` · `apiHeaders(extra?)` · `apiUrl(path)`. EventSource·PDF iframe 은 헤더를 달 수 없다 — 둘 다 소유 확인이 없는 엔드포인트라 무해하다.
- `types/history.ts`: `HistoryKind` · `HistoryBase{id, kind, title, createdAt, updatedAt?, params}` · `BookEntry`/`PaperEntry`/`ResearchEntry{refId, research?: HistoryResearchStatus}` · `HistoryEntry` · `HistoryEntryInput = DistributiveOmit<HistoryEntry, "id"|"createdAt">` · `HistoryPatch` · `LegacyHistoryEntry` · 서버 선 모양(`HistoryItemOut` 등, snake_case 그대로). 변환은 `utils/historyStore.ts` 의 `fromWire`/`toWire` 한 곳이다.
- `utils/historyStore.ts`: `HistoryStore{list, get, put, patch, remove, clear}` · `createServerStore(fetcher)`(+`importItems`) · `createLocalStore(storage)`(캐시 `skx_history_v2`·outbox `skx_history_outbox`) · `createHybridStore(server, local)`(+`flush`) · `convertLegacy` · `migrateLegacy(storage, server)`(성공하면 `skx_search_history` → `skx_search_history_backup_v1`, 대응표 `skx_history_v1_map`) · `readV1Map` · `findRecentDuplicate` · `errorStatus`. spec §4-5 의 `importLegacy` 는 `migrateLegacy` 로 갔다.
- `utils/historyRoute.ts`: `routeFor(entry)` · `readHistoryQuery(query, v1Map = {})` · `activeKindForPath(path)` · `activeIdFor(path, query, v1Map?)`.
- `composables/useHistory.ts`: `useHistory()` → `{ entries, byKind(kind), load(), refresh(kind?), add(input), patch(id, partial), remove(id), clear(kind), get(id), upsertResearch(jobId, question) }`. `add` 는 10분 중복 병합(같은 kind·정규화 제목·조건), 거절돼도 던지지 않고, 413 이면 snapshot 없이 다시 저장한다. `upsertResearch` 는 남의 잡이라 서버가 404 면 `null`.
- 딥리서치: `useResearchStarter().startResearch(question)` 가 `POST /api/research` → `upsertResearch` 를 부른다 — **잡을 만들 때만** 부른다(남의 잡 주소를 열 때 부르면 그 행은 만든 사람 소유라 PUT 이 404 이고, 주인 없는 잡이면 남의 잡이 내 사이드바에 들어온다). `useResearchJob` 은 종료 이벤트·승인·재시도·취소 뒤 `useHistory().refresh("research")` 로 사이드바 배지를 맞춘다.
- Nuxt 는 `utils/`·`composables/` 의 export 를 자동 import 한다 — 영역 사이에 같은 이름을 두지 않는다(아래 정합 결정 2·3번).

### 통합 때 바로잡은 정합 문제

| # | 문제 | 결정 | 반영 |
|---|---|---|---|
| 1 | Vitest 설정이 `tests/unit/**` + `~/` 별칭인데 딥리서치 테스트 7개는 `frontend/tests/*.test.ts` + 상대 import 라 **수집되지 않는다** | 7개를 `frontend/tests/unit/` 로 옮기고 import 를 `~/types/…`·`~/utils/…` 로 통일 | Task 27·28·29·31·34 |
| 2 | 자동 import 이름 충돌 — `errorStatus` 가 `utils/historyStore.ts`(`number\|null`)와 `utils/researchErrors.ts`(`number\|undefined`)에 둘 다 | 딥리서치 쪽을 `httpStatus` 로 개명 | Task 29 |
| 3 | 같은 일을 하는 함수 두 벌 — `researchLayout.browserStorage()` ≡ `browserId.safeLocalStorage()` | `browserStorage` 삭제, 페이지는 `safeLocalStorage` | Task 31 |
| 4 | 타입 이름 충돌 — `ResearchStatus` 가 `types/history.ts`(`{status, stage}`)와 `types/research.ts`(상태 문자열 유니온)에 | 기록 쪽을 `HistoryResearchStatus` 로 개명(백엔드 `schemas/history.py` 의 `ResearchStatus` 는 그대로) | Task 14 |
| 5 | `step` 이벤트의 `detail` 을 백엔드는 싣는데 화면 타입에 없고 리듀서가 버린다 | `StepEvent.detail?` 추가, `applyStep` 이 이벤트 값을 먼저 쓴다 | Task 26·28 |
| 6 | 탐색 중 재접속 복원 공백 — 백엔드는 단계 result 를 끝날 때만 쓰고 스냅샷에 카운터가 없어, 화면이 전제한 "탐색 중 새로고침해도 회차·강조 카드·카운터 복원"이 성립하지 않는다 | 회차·절마다 도는 단계 result 갱신 + `step`(running+result) 발행, 끝난 search result 에 `counters`, 스냅샷 `job.counters` | **Task 12 신설** |
| 7 | snapshot 200KB 초과 PUT 은 413 인데 기록 저장소는 4xx 를 재전송하지 않아 그 검색 기록이 통째로 사라진다(논문 20건 × 참고문헌 30개면 상한 근처) | `add` 가 413 이면 snapshot 없이 한 번 더 저장 | Task 20(테스트 +1) |
| 8 | 딥리서치가 끝나도 사이드바 배지는 30초 폴링까지 "진행 중" | 종료 이벤트·동작 성공 뒤 `refresh("research")` | Task 29 |
| 9 | 원문 PDF 존재 확인 요청이 native fetch 에 `x-session-id` 없이 간다(spec §4-2 "모든 `/api` 요청") | `apiHeaders()` 첨부 | Task 34 |
| 10 | 영역 B 의 누적 테스트 수가 영역 A 없이 센 값 | A 뒤 순서 기준으로 다시 매김(669~728) | Task 5~12 |
| 11 | 기록 영역 메모의 "가로채기는 `handleSearch` 의 `beginRun` 앞에" — 실제 `+` 메뉴는 캡처 단계 리스너로 가로채 페이지 스크립트를 고치지 않는다 | 메모 삭제, Task 35 는 Task 22·23 뒤 앵커 문자열로 찾게 명시 | Task 35 |
| 12 | 계약의 `ref_id = research_jobs.id::text` LEFT JOIN | PK `IN` 재조회(응답 모양 동일) | Task 3 |
| 13 | devProxy 가 `/api` 접두를 떼고 넘겨 기존 대상 `http://localhost:18002` 로는 모든 요청이 404(실측) | 기본값·환경변수 값 모두 `/api` 포함(`NUXT_DEV_API_TARGET=http://<서버>:92/api`) | Task 30 |

---

## 단계 1 — 백엔드(영역 A·B, 병렬 가능)

### 영역 A 개요 — 기록 백엔드 (`history_items` · `/api/history`)

**목표:** 사이드바 기록(도서 검색·논문 검색·딥리서치)을 서버에 저장한다. 새 테이블 `history_items` 하나만 추가하고 기존 테이블은 건드리지 않는다. 소유 단위는 브라우저 ID(`x-session-id`)다. 남의 기록은 읽기·쓰기·삭제 모두 404, 삭제는 소프트 삭제, v1 기록 이전은 결정론적 id 로 여러 번 해도 안전하게 만든다.

**설계 근거:** spec §4-2(식별자) · §4-3(테이블) · §4-4(API) · §9(테스트) · §10(데이터 안전).

**테스트 전략 — 이 영역 전체에 일관되게 적용한다.**
- 로컬에 Postgres 도 `aiosqlite` 도 없다(`asyncpg` 는 있지만 붙을 DB 가 없다). 그래서 **표준 라이브러리 `sqlite3` 위의 동기 `Session` 을 `AsyncSession` 모양으로 감싼 대역**(`app/tests/history_sqlite.py`)을 만든다. 대역은 `execute`·`commit`·`rollback`·`close` 만 넘긴다. 저장소가 내는 SQL(upsert 의 `ON CONFLICT … WHERE`, 커서 비교, 소프트 삭제 조건)은 **실제 SQL 엔진이 실행한다.** 대역이 SQL 을 흉내 내면 그 조건을 대역이 대신 판정하게 되어 저장소의 버그를 못 잡는다.
- 저장소는 ORM 객체를 한 번도 만들지 않고 Core 문장(`select`·`insert`·`update`)만 쓴다. 그래서 identity map 이 끼지 않고, SQLite 에서도 같은 문장이 돈다. 로컬 SQLAlchemy 2.0.36 의 SQLite 컴파일러는 `postgresql.insert(...).on_conflict_do_update/do_nothing(...).returning(...)` 을 그대로 그린다(로컬 sqlite 3.53 은 `ON CONFLICT`·`RETURNING` 지원). 계획 작성 중 스크래치 복사본에서 이 계획의 코드를 그대로 실행해 확인했다.
- SQLite 가 모르는 Postgres 표기는 **테스트 쪽에서만** 둘을 바꾼다: `JSONB` 타입 이름(`@compiles` 로 `JSON` 을 그린다)과 `'::jsonb'` 가 붙은 서버 기본값(테스트용 테이블 사본에서만 뺀다). 운영 모델·마이그레이션은 그대로다.
- 저장소 테스트(Task 3)는 `asyncio.run(...)` 으로 저장소를 직접 부른다. API 테스트(Task 4)는 `test_research_api.py` 처럼 TestClient + `dependency_overrides[get_db]` 이고, 요청마다 대역 세션을 새로 열어 `get_db` 처럼 끝나면 커밋·예외면 되돌린다.
- 모델↔마이그레이션 정합은 `test_research_models.py` 와 같은 방식이다. 로컬에 `alembic` 이 없어 `op` 를 스텁으로 갈아끼우고 `upgrade()` 를 실제로 실행한다.

**파일 구조**

| 파일 | 책임 | Task |
|---|---|---|
| `app/models/history.py` | `HistoryItem` ORM · `HISTORY_KINDS` | Task 1 |
| `app/alembic/versions/0006_history_items.py` | 테이블·부분 인덱스 마이그레이션 | Task 1 |
| `app/alembic/env.py` | 모델 등록 1줄 | Task 1 |
| `app/main.py` | lifespan 모델 import 1줄(Task 1) · 라우터 import·등록 2줄(Task 4) | Task 1·Task 4 |
| `app/core/deps.py` | `get_browser_id` · `get_browser_id_optional` | Task 2 |
| `app/schemas/history.py` | 입출력 스키마 | Task 3 |
| `app/repositories/history.py` | `HistoryRepository` · `legacy_history_id` · 커서 | Task 3 |
| `app/api/history.py` | 얇은 라우터(413·404·400 매핑, 쓰기 후 커밋) | Task 4 |
| `app/tests/history_sqlite.py` | 테스트용 DB(동기 SQLite 를 감싼 AsyncSession 대역) — 수집 대상 아님 | Task 3 |
| `app/tests/test_history_models.py` · `test_browser_id.py` · `test_history_repository.py` · `test_history_api.py` | 테스트 | Task 1~Task 4 |

**테스트 명령과 누적 기대치** — 저장소 루트에서 실행한다.

```bash
python -m pytest app/tests -q --ignore=app/tests/test_book_chat.py --ignore=app/tests/test_build_manifest.py --ignore=app/tests/test_loaders.py
```

기준선 549 passed. 이 영역만 순서대로 적용하면 Task 1 뒤 **560** → Task 2 뒤 **576** → Task 3 뒤 **624** → Task 4 뒤 **658** passed 다(각각 +11·+16·+48·+34). 다른 영역 태스크가 먼저 들어가 있으면 그만큼 더한다.

**줄바꿈:** 작업 트리의 기존 파일은 CRLF 다(`core.autocrlf=true`). 기존 파일은 Edit 도구로 고쳐 줄바꿈을 유지한다. 새 파일은 LF 로 써도 커밋 때 정규화된다.

---

### Task 1: 기록 테이블 `history_items` 모델과 `0006` 마이그레이션

**Files:**
- Create: `app/models/history.py`
- Create: `app/alembic/versions/0006_history_items.py`
- Modify: `app/alembic/env.py` (29행 `_research_mod` 등록 줄 바로 뒤 1줄)
- Modify: `app/main.py` (lifespan 안 30행 `import models.ingest_job` 바로 뒤 1줄)
- Test: `app/tests/test_history_models.py`

설계 메모(모델에 반영된 결정):
- `id` 는 브라우저가 만든 UUID 가 그대로 PK 라 **ORM 기본값을 두지 않는다**(`default=uuid.uuid4` 가 있으면 id 를 빠뜨린 저장이 조용히 새 행을 만들어 재전송이 중복을 쌓는다).
- `snapshot`·`ai` 는 `JSONB(none_as_null=True)` 다. 기본값(False)이면 파이썬 `None` 이 JSON `null` 로 저장돼 `snapshot IS NOT NULL`(has_snapshot)이 늘 참이 되고, upsert 의 `COALESCE` 도 동작하지 않는다(스크래치에서 이 설정을 빼면 저장소 테스트 4건이 실패함을 확인했다).
- `created_at`·`updated_at` 은 `NOT NULL`(계약은 `server_default now()` 만 명시). 목록 커서가 `created_at` 으로 정렬·비교하므로 NULL 이 끼면 쪽 경계가 깨진다.
- 인덱스는 `text("created_at DESC")` 를 쓴 부분 인덱스다. 조건식은 research 모델처럼 `text("deleted_at IS NULL")` 로 써서 모델과 마이그레이션의 문자열이 같게 한다.

- [ ] **Step 1: 실패하는 테스트**

```python
# app/tests/test_history_models.py
import ast
import sys
import types
from pathlib import Path

import sqlalchemy as sa

from models.history import HISTORY_KINDS, HistoryItem

APP_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = APP_DIR / "alembic" / "versions" / "0006_history_items.py"
INDEX_NAME = "ix_history_items_session_kind_created"


def _column_signature(col, include_default=True):
    """(타입, nullable[, 기본값 유무]) — 컬럼 하나의 스키마 정합성 지문.

    PK 는 기본값을 비교하지 않는다. id 는 브라우저가 만들어 보내는 값이라 모델에도
    마이그레이션에도 기본값이 없어야 하고, 그건 아래 전용 테스트가 따로 본다.
    """
    sig = [str(col.type), col.nullable]
    if include_default:
        sig.append(col.server_default is not None or col.default is not None)
    return tuple(sig)


def _table_signature(table):
    return {
        c.name: _column_signature(c, include_default=not c.primary_key)
        for c in table.columns
    }


def _index_parts(parts):
    """인덱스 구성요소를 이름 문자열로 — 컬럼은 이름, text("created_at DESC") 는 그 원문."""
    return [p.name if isinstance(p, sa.Column) else p if isinstance(p, str) else str(p) for p in parts]


def _model_indexes(table):
    sig = {}
    for ix in table.indexes:
        where = ix.dialect_options["postgresql"].get("where")
        sig[ix.name] = {
            "table_name": table.name,
            "parts": _index_parts(ix.expressions),
            "postgresql_where": str(where) if where is not None else None,
        }
    return sig


def _run_migration_upgrade(monkeypatch):
    """0006 의 upgrade() 를 alembic 없이 실행하고 create_table/create_index 호출을 캡처한다.

    로컬 venv 에 alembic 이 없어 op 를 스텁으로 갈아끼운다. create_table 인자로 진짜
    sa.Table 을 만들어 introspection 한다 — 인자를 직접 훑어 파싱하면 그 파싱이 또
    하나의 정합 리스크가 된다(test_research_models.py 와 같은 방식).
    """
    import importlib.util as u

    tables = {}
    indexes = {}

    def fake_create_table(name, *args, **kwargs):
        tables[name] = _table_signature(sa.Table(name, sa.MetaData(), *args))

    def fake_create_index(name, table_name, columns, **kwargs):
        where = kwargs.get("postgresql_where")
        indexes[name] = {
            "table_name": table_name,
            "parts": _index_parts(columns),
            "postgresql_where": str(where) if where is not None else None,
        }

    fake_op = types.ModuleType("alembic.op")
    fake_op.create_table = fake_create_table
    fake_op.create_index = fake_create_index
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.op = fake_op
    monkeypatch.setitem(sys.modules, "alembic", fake_alembic)
    monkeypatch.setitem(sys.modules, "alembic.op", fake_op)

    spec = u.spec_from_file_location("_migration_0006", MIGRATION_PATH)
    module = u.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    return module, tables, indexes


class TestHistoryModelShape:
    def test_columns(self):
        assert set(HistoryItem.__table__.columns.keys()) == {
            "id", "session_id", "user_id", "kind", "title", "params", "snapshot",
            "ai", "ref_id", "created_at", "updated_at", "deleted_at",
        }

    def test_id_has_no_default(self):
        # 기본값이 있으면 id 를 빠뜨린 저장이 조용히 새 행을 만든다 — 재전송이 중복을 쌓는다
        col = HistoryItem.__table__.c.id
        assert col.default is None and col.server_default is None

    def test_owner_is_required_and_user_is_placeholder(self):
        assert HistoryItem.__table__.c.session_id.nullable is False
        assert HistoryItem.__table__.c.user_id.nullable is True

    def test_kinds_fit_kind_column(self):
        assert HISTORY_KINDS == ("book", "paper", "research")
        max_len = HistoryItem.__table__.c.kind.type.length
        assert all(len(k) <= max_len for k in HISTORY_KINDS)

    def test_heavy_columns_store_none_as_sql_null(self):
        # JSON null 로 쓰면 has_snapshot(IS NOT NULL) 이 늘 참이 된다
        assert HistoryItem.__table__.c.snapshot.type.none_as_null is True
        assert HistoryItem.__table__.c.ai.type.none_as_null is True

    def test_list_index_is_partial_and_newest_first(self):
        ix = next(i for i in HistoryItem.__table__.indexes if i.name == INDEX_NAME)
        assert _index_parts(ix.expressions) == ["session_id", "kind", "created_at DESC"]
        assert str(ix.dialect_options["postgresql"]["where"]) == "deleted_at IS NULL"


class TestMigrationMatchesModel:
    def test_revision_chain(self, monkeypatch):
        module, _, _ = _run_migration_upgrade(monkeypatch)
        assert module.revision == "0006_history_items"
        assert module.down_revision == "0005_research_jobs"

    def test_upgrade_creates_columns_matching_orm(self, monkeypatch):
        _, tables, _ = _run_migration_upgrade(monkeypatch)
        assert tables == {"history_items": _table_signature(HistoryItem.__table__)}

    def test_upgrade_indexes_match_orm(self, monkeypatch):
        _, _, indexes = _run_migration_upgrade(monkeypatch)
        assert indexes == _model_indexes(HistoryItem.__table__)


def _imported_modules(path: Path) -> set[str]:
    """파일이 import 하는 모듈 이름 — `import a.b` 는 "a.b", `from a import b` 는 "a.b"."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


class TestModelRegistration:
    def test_alembic_env_registers_model(self):
        # 빠뜨리면 autogenerate 가 이 테이블을 모르는 것으로 보고 DROP TABLE 을 만든다
        assert "models.history" in _imported_modules(APP_DIR / "alembic" / "env.py")

    def test_lifespan_create_all_sees_model(self):
        # create_all 은 import 된 모델만 만든다 — 라우터 import 의 부수효과에 기대지 않는다
        assert "models.history" in _imported_modules(APP_DIR / "main.py")
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
python -m pytest app/tests/test_history_models.py -q
```

기대: 수집 단계 오류 `E   ModuleNotFoundError: No module named 'models.history'` (1 error).

- [ ] **Step 3: 모델**

```python
# app/models/history.py
"""history.py — 사이드바 기록(도서 검색·논문 검색·딥리서치)

소유 단위는 브라우저 ID(session_id)다. 로그인이 생기면 user_id 로 묶는다 — 지금은
자리만 두고 항상 NULL 이다. 사용자가 지워도 행은 남는다(deleted_at, 소프트 삭제).

딥리서치 진행 상태는 여기 두지 않는다. 조회할 때 research_jobs 에서 붙인다 — 두 곳에
두면 워커가 바꾼 상태와 기록의 상태가 어긋난다.
"""
from sqlalchemy import Column, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.book import Base

HISTORY_KINDS = ("book", "paper", "research")


class HistoryItem(Base):
    __tablename__ = "history_items"
    __table_args__ = (
        # 사이드바는 "이 브라우저의 이 종류, 최신순"만 읽는다. 지운 행을 인덱스에서
        # 빼 두면 소프트 삭제가 쌓여도 목록 조회가 느려지지 않는다.
        Index(
            "ix_history_items_session_kind_created",
            "session_id", "kind", text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # 브라우저가 만든 UUID 가 그대로 PK 다 — 서버 응답을 기다리지 않고 URL(?h=)에
    # 넣을 수 있어야 하고, 실패 뒤 재전송해도 같은 행이 된다. 그래서 ORM 기본값이 없다.
    id         = Column(UUID(as_uuid=True), primary_key=True)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    user_id    = Column(String(64))
    kind       = Column(String(16), nullable=False)
    title      = Column(Text, nullable=False)
    params     = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # none_as_null: 파이썬 None 을 JSON null 이 아니라 SQL NULL 로 쓴다. 이게 없으면
    # "snapshot IS NOT NULL" 로 계산하는 has_snapshot 이 늘 참이 되고, 재전송이
    # 빠뜨린 칸을 기존 값으로 채우는 COALESCE 도 동작하지 않는다.
    snapshot   = Column(JSONB(none_as_null=True))
    ai         = Column(JSONB(none_as_null=True))
    ref_id     = Column(String(64))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))
```

- [ ] **Step 4: 마이그레이션**

```python
# app/alembic/versions/0006_history_items.py
"""사이드바 기록 테이블

history_items — 브라우저 ID 별 도서·논문 검색과 딥리서치 기록. 기존 테이블은 건드리지 않는다.

Revision ID: 0006_history_items
Revises: 0005_research_jobs
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0006_history_items"
down_revision: Union[str, None] = "0005_research_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "history_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(64)),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("params", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("snapshot", JSONB()),
        sa.Column("ai", JSONB()),
        sa.Column("ref_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_history_items_session_kind_created", "history_items",
        ["session_id", "kind", sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("history_items")
```

- [ ] **Step 5: 실행 — 등록 테스트만 실패하는지 확인**

```bash
python -m pytest app/tests/test_history_models.py -q
```

기대: `2 failed, 9 passed` — `TestModelRegistration` 두 건(`env.py`·`main.py` 가 아직 `models.history` 를 import 하지 않음).

- [ ] **Step 6: `alembic/env.py` 와 `main.py` lifespan 에 모델 등록**

`app/alembic/env.py` 현재(24~29행):

```python
from models import book as _book_mod          # noqa: F401, E402
from models import section as _section_mod    # noqa: F401, E402
from models import figure as _figure_mod      # noqa: F401, E402
from models import search_history as _hist_mod  # noqa: F401, E402
from models import ingest_job as _job_mod     # noqa: F401, E402
from models import research as _research_mod  # noqa: F401, E402
```

29행 뒤에 한 줄을 더한다(나머지는 그대로):

```python
from models import research as _research_mod  # noqa: F401, E402
from models import history as _history_mod    # noqa: F401, E402
```

`app/main.py` lifespan 현재(25~31행):

```python
    from db.postgres import engine
    from models.book import Base
    import models.section
    import models.search_history
    import models.ingest_job
    from sqlalchemy import text
```

`import models.ingest_job` 뒤에 한 줄을 더한다:

```python
    import models.ingest_job
    import models.history
    from sqlalchemy import text
```

라우터 import 의 부수효과로도 테이블이 등록되지만(`api.history` → `repositories.history` → `models.history`), `create_all` 이 만들 테이블은 여기서 명시적으로 드러낸다 — 라우터 구성이 바뀌어도 테이블 생성이 조용히 빠지지 않게.

- [ ] **Step 7: 실행해 통과 확인**

```bash
python -m pytest app/tests/test_history_models.py -q
```

기대: `11 passed`.

전체 스위트(위 공통 명령) 기대: **560 passed**(기준선 549 + 11).

- [ ] **Step 8: 커밋**

```bash
git add app/models/history.py app/alembic/versions/0006_history_items.py app/alembic/env.py app/main.py app/tests/test_history_models.py
git commit -m "[Feat] round04b — 기록 테이블 history_items 모델·0006 마이그레이션"
```

---

### Task 2: 브라우저 ID 의존성 `get_browser_id` · `get_browser_id_optional`

**Files:**
- Modify: `app/core/deps.py` (전체 14행 — 파일 전체 교체)
- Test: `app/tests/test_browser_id.py`

규칙: 헤더 `x-session-id` 가 없거나, UUID 로 읽히지 않거나, **v4 가 아니면** 필수 버전은 400 `"x-session-id 헤더가 필요하다"`, 선택 버전은 `None`. 대문자·하이픈 없는 표기는 `uuid.UUID` 가 정규화한다. 브라우저 쪽 `sid` 는 이미 v4 다(`crypto.randomUUID` 또는 v4 형식 폴백 — `frontend/composables/useSearch.ts:10-20`), 프론트는 v4 가 아니면 새로 만든다(spec §4-2).

- [ ] **Step 1: 실패하는 테스트**

```python
# app/tests/test_browser_id.py
import uuid

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.deps import get_browser_id, get_browser_id_optional

SID = "3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e"


class TestGetBrowserId:
    def test_valid_v4_is_returned_as_uuid(self):
        assert get_browser_id(SID) == uuid.UUID(SID)

    def test_uppercase_is_normalized(self):
        assert get_browser_id(SID.upper()) == uuid.UUID(SID)

    @pytest.mark.parametrize("raw", [
        None,
        "",
        "null",                                     # 옛 코드가 문자열 "null" 을 보낸 적이 있다
        "not-a-uuid",
        "00000000-0000-0000-0000-000000000000",     # 형식은 맞지만 v4 가 아니다
        "3f2b8c1e-4d5a-1b6c-8d7e-9f0a1b2c3d4e",     # v1
    ])
    def test_missing_or_malformed_is_400(self, raw):
        with pytest.raises(HTTPException) as e:
            get_browser_id(raw)
        assert e.value.status_code == 400
        assert e.value.detail == "x-session-id 헤더가 필요하다"


class TestGetBrowserIdOptional:
    def test_valid_is_returned(self):
        assert get_browser_id_optional(SID) == uuid.UUID(SID)

    @pytest.mark.parametrize("raw", [None, "", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
    def test_missing_or_malformed_is_none(self, raw):
        assert get_browser_id_optional(raw) is None


class TestHeaderWiring:
    """함수 직접 호출은 Header alias 를 거치지 않는다 — 라우팅을 거쳐 헤더 이름까지 본다."""

    @pytest.fixture
    def client(self):
        app = FastAPI()

        @app.get("/required")
        def required(browser_id: uuid.UUID = Depends(get_browser_id)):
            return {"browser_id": str(browser_id)}

        @app.get("/optional")
        def optional(browser_id: uuid.UUID | None = Depends(get_browser_id_optional)):
            return {"browser_id": str(browser_id) if browser_id else None}

        return TestClient(app)

    def test_header_is_read_case_insensitively(self, client):
        res = client.get("/required", headers={"X-Session-Id": SID})
        assert res.status_code == 200 and res.json() == {"browser_id": SID}

    def test_missing_header_is_400(self, client):
        res = client.get("/required")
        assert res.status_code == 400
        assert res.json()["detail"] == "x-session-id 헤더가 필요하다"

    def test_optional_without_header_is_none(self, client):
        res = client.get("/optional")
        assert res.status_code == 200 and res.json() == {"browser_id": None}
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
python -m pytest app/tests/test_browser_id.py -q
```

기대: 수집 오류 `E   ImportError: cannot import name 'get_browser_id' from 'core.deps'`.

- [ ] **Step 3: 구현 — `app/core/deps.py` 전체 교체**

현재 파일 전체(1~14행):

```python
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from db.postgres import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성: 비동기 DB 세션 제공"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        
```

교체 후 전체(`get_db` 본문은 그대로, 쓰이지 않던 `async_sessionmaker`·`create_async_engine` import 는 뺀다 — `core.deps` 에서 가져가는 것은 저장소 전체에서 `get_db` 뿐임을 grep 으로 확인했다):

```python
# app/core/deps.py
import uuid
from typing import AsyncGenerator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.postgres import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성: 비동기 DB 세션 제공"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _parse_browser_id(raw: str | None) -> uuid.UUID | None:
    """x-session-id 값 → 브라우저 ID. v4 만 받는다 — 브라우저는 v4 가 아니면 새로 만든다."""
    if not raw:
        return None
    try:
        value = uuid.UUID(raw)
    except ValueError:
        return None
    return value if value.version == 4 else None


def get_browser_id(
    x_session_id: str | None = Header(None, alias="x-session-id"),
) -> uuid.UUID:
    """기록의 소유 단위. 브라우저 ID 는 URL 에 싣지 않는다 — nginx access log 에 남는다."""
    browser_id = _parse_browser_id(x_session_id)
    if browser_id is None:
        raise HTTPException(status_code=400, detail="x-session-id 헤더가 필요하다")
    return browser_id


def get_browser_id_optional(
    x_session_id: str | None = Header(None, alias="x-session-id"),
) -> uuid.UUID | None:
    """헤더가 없어도 동작해야 하는 엔드포인트용(딥리서치 생성의 created_by)."""
    return _parse_browser_id(x_session_id)
```

- [ ] **Step 4: 실행해 통과 확인**

```bash
python -m pytest app/tests/test_browser_id.py -q
```

기대: `16 passed`(경고 1건은 기존 `core/config.py` 의 Pydantic class-based config 경고).

전체 스위트 기대: **576 passed**.

- [ ] **Step 5: 커밋**

```bash
git add app/core/deps.py app/tests/test_browser_id.py
git commit -m "[Feat] round04b — x-session-id 브라우저 ID 의존성 get_browser_id"
```

---

### Task 3: 기록 스키마·저장소 (`legacy_history_id` · 커서 · upsert · 소프트 삭제 · 이전)

**Files:**
- Create: `app/schemas/history.py`
- Create: `app/repositories/history.py`
- Create: `app/tests/history_sqlite.py` (테스트용 DB 도우미 — `test_*.py` 가 아니라 수집되지 않는다)
- Test: `app/tests/test_history_repository.py`

저장소 동작 규칙(테스트가 고정하는 것):

| 메서드 | 규칙 |
|---|---|
| `upsert` | 새 id 면 INSERT. 같은 브라우저의 기존 id 면 `kind·title·params` 교체, `snapshot·ai·ref_id` 는 **요청에 없으면 기존 값 유지**(`COALESCE`), `created_at=now()`(목록 맨 위로 — spec §4-7 "갱신해 맨 위로"), `deleted_at=NULL`(되살림). **다른 브라우저의 id 면 아무것도 바꾸지 않고 `None`**(`ON CONFLICT … DO UPDATE … WHERE session_id = excluded.session_id` — 한 문장이라 동시 PUT 에도 안전) |
| `get` | 내 것·안 지운 것만. 아니면 `None` |
| `list` | 내 것·안 지운 것, `created_at DESC, id DESC`. `limit+1` 을 읽어 다음 쪽 유무를 안다. 커서 `"<created_at ISO>\|<id>"`, 비교는 `created_at < c OR (created_at = c AND id < i)` — 같은 시각 행이 쪽 경계에서 빠지거나 겹치지 않는다. 틀린 커서는 `InvalidCursor`(ValueError 하위) |
| `patch` | 보낸 칸만(`exclude_unset`) + `updated_at=now()`. `snapshot: null` 을 명시하면 비운다. 남의 것·지운 것이면 `None` |
| `soft_delete` | 내 것이면 `True`(이미 지운 것도 `True`, 첫 삭제 시각 유지 — 재전송된 삭제가 404 로 돌아오지 않게). 남의 것·없는 것이면 `False` |
| `soft_delete_kind` | 내 것 중 그 종류·안 지운 것만. 지운 개수 |
| `import_items` | id 우선순위 `id` > `legacy_history_id(legacy_id)` > `uuid4()`. `ON CONFLICT (id) DO NOTHING` — 이미 있는 id(지운 것·남의 것 포함)는 건너뛴다. 같은 묶음 안 중복은 첫 항목만. `skipped = 받은 수 − 넣은 수`. `id_map` 은 **건너뛴 항목까지** 담는다(두 번째 이전에서도 옛 `?restore=` 를 찾게) |
| 딥리서치 상태 | `kind == "research"` 인 행만. 한 쪽의 `ref_id` 를 UUID 로 모아 `research_jobs` 를 PK `IN` 으로 한 번 더 읽는다. 없는 잡·형식이 틀린 `ref_id` 는 `research=None` |

- [ ] **Step 1: 테스트용 DB 도우미**

```python
# app/tests/history_sqlite.py
"""history_sqlite.py — 기록 저장소·API 테스트가 함께 쓰는 DB.

로컬에 Postgres 도 aiosqlite 도 없다. 표준 라이브러리 sqlite3 위의 동기 Session 을
AsyncSession 모양으로 감싸, 저장소가 내는 SQL(upsert·커서·소프트 삭제 조건)을 실제
엔진이 실행하게 한다. 대역이 SQL 을 흉내 내면 그 조건을 대역이 대신 판정하게 되어
저장소의 버그를 못 잡는다.

SQLite 가 모르는 Postgres 표기 둘만 테스트 쪽에서 바꾼다 — JSONB 타입 이름(JSON 으로
그린다)과 '::jsonb' 가 붙은 서버 기본값(테스트 테이블에서만 뺀다. 저장소는 params 를
늘 채워 넣는다). 운영 모델·마이그레이션은 그대로다.
"""
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from models.history import HistoryItem
from models.research import ResearchJob

SID_A = uuid.UUID("3f2b8c1e-4d5a-4b6c-8d7e-9f0a1b2c3d4e")
SID_B = uuid.UUID("7a6b5c4d-3e2f-4a1b-9c8d-7e6f5a4b3c2d")


@compiles(JSONB, "sqlite")
def _jsonb_as_json(type_, compiler, **kw):
    return "JSON"


def make_engine() -> sa.Engine:
    # 인메모리 DB 는 연결마다 따로 생긴다 — StaticPool 로 한 연결을 모두가 쓴다.
    # TestClient 는 앱을 다른 스레드에서 돌리므로 스레드 검사도 끈다.
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    metadata = sa.MetaData()
    for table in (HistoryItem.__table__, ResearchJob.__table__):
        copy = table.to_metadata(metadata)
        for col in copy.columns:
            default = col.server_default
            if default is not None and "::" in str(getattr(default, "arg", "")):
                col.server_default = None
    metadata.create_all(engine)
    return engine


class AsyncSessionOverSync:
    """저장소·라우터가 쓰는 AsyncSession 메서드만 동기 Session 으로 넘긴다."""

    def __init__(self, engine: sa.Engine):
        self._session = Session(engine)

    async def execute(self, stmt, params=None):
        return self._session.execute(stmt, params)

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()

    async def close(self):
        self._session.close()


def add_research_job(engine: sa.Engine, *, status: str, stage: str) -> uuid.UUID:
    job_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(sa.insert(ResearchJob.__table__).values(
            id=job_id, question="독서 격차 연구", status=status, stage=stage, params={},
        ))
    return job_id


def raw_row(engine: sa.Engine, item_id: uuid.UUID):
    """소프트 삭제가 행을 남기는지처럼 API 가 보여 주지 않는 것을 확인할 때 쓴다."""
    with engine.connect() as conn:
        return conn.execute(
            sa.select(HistoryItem.__table__).where(HistoryItem.__table__.c.id == item_id)
        ).first()
```

`from history_sqlite import …` 는 pytest 기본 import 모드(prepend)가 `__init__.py` 없는 `app/tests` 를 `sys.path` 에 넣기 때문에 동작한다(이 저장소 설정 그대로 스크래치에서 확인).

- [ ] **Step 2: 실패하는 테스트**

```python
# app/tests/test_history_repository.py
"""test_history_repository.py — 기록 저장소

history_sqlite 의 SQLite 위에서 저장소가 내는 SQL 을 실제로 실행한다. 한 번의 _call 이
요청 하나다 — 세션을 열고, 끝나면 커밋하고 닫는다.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from history_sqlite import SID_A, SID_B, AsyncSessionOverSync, add_research_job, make_engine, raw_row
from repositories.history import (
    HistoryRepository, InvalidCursor, decode_cursor, encode_cursor, legacy_history_id,
)
from schemas.history import HistoryImportItem, HistoryItemIn, HistoryItemPatch

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    return make_engine()


def _call(engine, fn):
    async def _go():
        db = AsyncSessionOverSync(engine)
        try:
            result = await fn(HistoryRepository(db))
            await db.commit()
            return result
        finally:
            await db.close()
    return asyncio.run(_go())


def _put(engine, sid, item_id, **fields):
    data = HistoryItemIn(**{"kind": "book", "title": "독서 격차", **fields})
    return _call(engine, lambda r: r.upsert(sid, item_id, data))


def _import(engine, sid, *items):
    return _call(engine, lambda r: r.import_items(sid, [HistoryImportItem(**i) for i in items]))


def _list(engine, sid, kind=None, limit=30, before=None):
    return _call(engine, lambda r: r.list(sid, kind, limit, before))


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


class TestLegacyId:
    def test_is_deterministic_uuid5(self):
        expected = uuid.uuid5(uuid.NAMESPACE_URL, "nl-lib-history-v1:1727000000000")
        assert legacy_history_id("1727000000000") == expected
        assert legacy_history_id("1727000000000") == legacy_history_id("1727000000000")

    def test_different_v1_ids_differ(self):
        assert legacy_history_id("1727000000000") != legacy_history_id("1727000000001")


class TestCursor:
    def test_round_trip(self):
        item_id = uuid.uuid4()
        at = datetime(2026, 9, 26, 10, 0, 0, 123456, tzinfo=timezone.utc)
        assert decode_cursor(encode_cursor(at, item_id)) == (at, item_id)

    def test_plus_decoded_as_space_is_tolerated(self):
        # 프론트가 인코딩을 빠뜨리면 "+00:00" 이 " 00:00" 으로 도착한다
        item_id = uuid.uuid4()
        at = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
        cursor = encode_cursor(at, item_id).replace("+", " ")
        assert decode_cursor(cursor) == (at, item_id)

    @pytest.mark.parametrize("cursor", ["", "garbage", "2026-09-26T10:00:00|not-uuid", f"nope|{uuid.uuid4()}"])
    def test_malformed_raises(self, cursor):
        with pytest.raises(InvalidCursor):
            decode_cursor(cursor)


class TestSchemas:
    def test_research_needs_ref_id(self):
        with pytest.raises(ValidationError):
            HistoryItemIn(kind="research", title="독서 격차 연구")

    @pytest.mark.parametrize("title", ["", "   ", "가" * 501])
    def test_title_bounds(self, title):
        with pytest.raises(ValidationError):
            HistoryItemIn(kind="book", title=title)

    def test_unknown_kind_is_rejected(self):
        with pytest.raises(ValidationError):
            HistoryItemIn(kind="chat", title="대화")

    @pytest.mark.parametrize("field", ["title", "params"])
    def test_patch_cannot_null_required_columns(self, field):
        with pytest.raises(ValidationError):
            HistoryItemPatch(**{field: None})

    def test_import_naive_time_is_utc(self):
        item = HistoryImportItem(kind="book", title="독서", created_at="2026-09-01T09:00:00")
        assert item.created_at == T0


class TestUpsert:
    def test_creates_item(self, engine):
        item_id = uuid.uuid4()
        out = _put(engine, SID_A, item_id, params={"grade": "KCI"}, snapshot={"books": [1]})
        assert out.id == item_id and out.title == "독서 격차"
        assert out.params == {"grade": "KCI"} and out.snapshot == {"books": [1]}
        assert out.has_snapshot and not out.has_ai and out.research is None
        assert raw_row(engine, item_id).user_id is None

    def test_repeating_same_id_keeps_one_row(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _put(engine, SID_A, item_id, title="독서 격차 해소")
        items, _ = _list(engine, SID_A)
        assert [(i.id, i.title) for i in items] == [(item_id, "독서 격차 해소")]

    def test_other_browser_cannot_overwrite(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, title="원래 제목")
        assert _put(engine, SID_B, item_id, title="덮어쓰기") is None
        row = raw_row(engine, item_id)
        assert row.title == "원래 제목" and row.session_id == SID_A

    def test_omitted_heavy_fields_keep_previous_values(self, engine):
        # 중복 병합·재전송이 결과·AI 요약 없이 다시 보내도 이미 받은 것은 남는다
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, snapshot={"books": [1]}, ai={"intro": "요약", "items": []})
        out = _put(engine, SID_A, item_id)
        assert out.snapshot == {"books": [1]} and out.ai == {"intro": "요약", "items": []}

    def test_repeat_moves_item_to_top(self, engine):
        old, newer = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(timezone.utc)
        _import(engine, SID_A,
                {"id": old, "kind": "book", "title": "예전", "created_at": now - timedelta(hours=2)},
                {"id": newer, "kind": "book", "title": "최근", "created_at": now - timedelta(hours=1)})
        _put(engine, SID_A, old, title="예전")
        items, _ = _list(engine, SID_A)
        assert [i.id for i in items] == [old, newer]

    def test_revives_deleted_item(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        assert _put(engine, SID_A, item_id) is not None
        assert raw_row(engine, item_id).deleted_at is None


class TestGet:
    def test_own_item(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, ai={"intro": "요약", "items": []})
        out = _call(engine, lambda r: r.get(SID_A, item_id))
        assert out.ai == {"intro": "요약", "items": []} and out.has_ai

    def test_other_browser_sees_nothing(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        assert _call(engine, lambda r: r.get(SID_B, item_id)) is None

    def test_deleted_is_hidden(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        assert _call(engine, lambda r: r.get(SID_A, item_id)) is None


class TestList:
    def test_newest_first_own_live_items_only(self, engine):
        a, b, c, d = (uuid.uuid4() for _ in range(4))
        _import(engine, SID_A,
                {"id": a, "kind": "book", "title": "가", "created_at": _at(1)},
                {"id": b, "kind": "paper", "title": "나", "created_at": _at(2)},
                {"id": c, "kind": "book", "title": "다", "created_at": _at(3)})
        _import(engine, SID_B, {"id": d, "kind": "book", "title": "남의 것", "created_at": _at(4)})
        _call(engine, lambda r: r.soft_delete(SID_A, c))
        items, cursor = _list(engine, SID_A)
        assert [i.id for i in items] == [b, a] and cursor is None

    def test_kind_filter(self, engine):
        a, b = uuid.uuid4(), uuid.uuid4()
        _import(engine, SID_A,
                {"id": a, "kind": "book", "title": "가", "created_at": _at(1)},
                {"id": b, "kind": "paper", "title": "나", "created_at": _at(2)})
        items, _ = _list(engine, SID_A, kind="book")
        assert [i.id for i in items] == [a]

    def test_list_does_not_carry_heavy_fields(self, engine):
        _put(engine, SID_A, uuid.uuid4(), snapshot={"books": [1]})
        (item,), _ = _list(engine, SID_A)
        assert item.has_snapshot and not item.has_ai
        assert "snapshot" not in item.model_dump()

    def test_pages_do_not_skip_or_repeat(self, engine):
        ids = [uuid.uuid4() for _ in range(5)]
        # 두 행이 같은 시각이어도 쪽 경계에서 빠지거나 겹치지 않아야 한다
        times = [_at(1), _at(2), _at(2), _at(3), _at(4)]
        _import(engine, SID_A, *[
            {"id": i, "kind": "book", "title": f"검색 {n}", "created_at": t}
            for n, (i, t) in enumerate(zip(ids, times))
        ])
        seen, cursor = [], None
        for _ in range(3):
            items, cursor = _list(engine, SID_A, limit=2, before=cursor)
            seen += [i.id for i in items]
            if cursor is None:
                break
        assert len(seen) == 5 and set(seen) == set(ids)
        assert cursor is None

    def test_malformed_cursor_raises(self, engine):
        with pytest.raises(InvalidCursor):
            _list(engine, SID_A, before="garbage")


class TestResearchStatus:
    def test_status_comes_from_research_jobs(self, engine):
        job_id = add_research_job(engine, status="running", stage="planned")
        _put(engine, SID_A, job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research.model_dump() == {"status": "running", "stage": "planned"}
        detail = _call(engine, lambda r: r.get(SID_A, job_id))
        assert detail.research.status == "running"

    def test_missing_job_gives_none(self, engine):
        job_id = uuid.uuid4()
        _put(engine, SID_A, job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research is None

    def test_malformed_ref_id_does_not_break_the_list(self, engine):
        _put(engine, SID_A, uuid.uuid4(), kind="research", title="독서 격차 연구", ref_id="not-a-uuid")
        (item,), _ = _list(engine, SID_A)
        assert item.research is None

    def test_other_kinds_have_no_research(self, engine):
        job_id = add_research_job(engine, status="completed", stage="synthesized")
        _put(engine, SID_A, uuid.uuid4(), kind="book", ref_id=str(job_id))
        (item,), _ = _list(engine, SID_A)
        assert item.research is None


class TestPatch:
    def test_updates_only_given_fields(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, params={"grade": "KCI"}, snapshot={"books": [1]})
        out = _call(engine, lambda r: r.patch(SID_A, item_id, HistoryItemPatch(ai={"text": "요약", "refs": []})))
        assert out.ai == {"text": "요약", "refs": []}
        assert out.params == {"grade": "KCI"} and out.snapshot == {"books": [1]}

    def test_explicit_null_clears_snapshot(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id, snapshot={"books": [1]})
        out = _call(engine, lambda r: r.patch(SID_A, item_id, HistoryItemPatch(snapshot=None)))
        assert out.snapshot is None and not out.has_snapshot

    def test_other_browser_or_deleted_gives_none(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        patch = HistoryItemPatch(title="바꿈")
        assert _call(engine, lambda r: r.patch(SID_B, item_id, patch)) is None
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        assert _call(engine, lambda r: r.patch(SID_A, item_id, patch)) is None
        assert raw_row(engine, item_id).title == "독서 격차"


class TestSoftDelete:
    def test_row_remains_but_is_hidden(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        assert _call(engine, lambda r: r.soft_delete(SID_A, item_id)) is True
        assert raw_row(engine, item_id).deleted_at is not None
        assert _list(engine, SID_A) == ([], None)

    def test_repeat_is_true_and_keeps_first_time(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        _call(engine, lambda r: r.soft_delete(SID_A, item_id))
        first = raw_row(engine, item_id).deleted_at
        assert _call(engine, lambda r: r.soft_delete(SID_A, item_id)) is True
        assert raw_row(engine, item_id).deleted_at == first

    def test_other_browser_cannot_delete(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_A, item_id)
        assert _call(engine, lambda r: r.soft_delete(SID_B, item_id)) is False
        assert raw_row(engine, item_id).deleted_at is None

    def test_delete_kind_touches_only_that_kind_of_this_browser(self, engine):
        book, paper, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        _put(engine, SID_A, book, kind="book")
        _put(engine, SID_A, paper, kind="paper")
        _put(engine, SID_B, other, kind="book")
        assert _call(engine, lambda r: r.soft_delete_kind(SID_A, "book")) == 1
        assert [i.id for i in _list(engine, SID_A)[0]] == [paper]
        assert raw_row(engine, other).deleted_at is None


class TestImport:
    def test_legacy_items_get_deterministic_ids(self, engine):
        out = _import(engine, SID_A,
                      {"legacy_id": "1727000000000", "kind": "book", "title": "가", "created_at": _at(1)},
                      {"legacy_id": "1727000000001", "kind": "paper", "title": "나", "created_at": _at(2)})
        assert (out.imported, out.skipped) == (2, 0)
        assert out.id_map == {
            "1727000000000": str(legacy_history_id("1727000000000")),
            "1727000000001": str(legacy_history_id("1727000000001")),
        }
        items, _ = _list(engine, SID_A)
        # 옛 기록의 시각을 지켜 순서가 그대로다
        assert [i.title for i in items] == ["나", "가"]
        assert items[1].created_at.replace(tzinfo=timezone.utc) == _at(1)

    def test_second_import_skips_and_returns_same_map(self, engine):
        item = {"legacy_id": "1727000000000", "kind": "book", "title": "가"}
        first = _import(engine, SID_A, item)
        second = _import(engine, SID_A, item)
        assert (second.imported, second.skipped) == (0, 1)
        assert second.id_map == first.id_map
        assert len(_list(engine, SID_A)[0]) == 1

    def test_does_not_revive_deleted_items(self, engine):
        item = {"legacy_id": "1727000000000", "kind": "book", "title": "가"}
        _import(engine, SID_A, item)
        _call(engine, lambda r: r.soft_delete(SID_A, legacy_history_id("1727000000000")))
        assert _import(engine, SID_A, item).imported == 0
        assert _list(engine, SID_A) == ([], None)

    def test_does_not_touch_other_browsers_rows(self, engine):
        item_id = uuid.uuid4()
        _put(engine, SID_B, item_id, title="남의 것")
        out = _import(engine, SID_A, {"id": item_id, "kind": "book", "title": "내 것"})
        assert (out.imported, out.skipped) == (0, 1)
        assert raw_row(engine, item_id).title == "남의 것"

    def test_duplicates_in_one_batch_count_as_skipped(self, engine):
        item = {"legacy_id": "1727000000000", "kind": "book", "title": "가"}
        out = _import(engine, SID_A, item, item)
        assert (out.imported, out.skipped) == (1, 1)

    def test_explicit_id_wins(self, engine):
        item_id = uuid.uuid4()
        out = _import(engine, SID_A, {"id": item_id, "legacy_id": "1727000000000", "kind": "book", "title": "가"})
        assert out.id_map == {"1727000000000": str(item_id)}

    def test_empty_import(self, engine):
        out = _import(engine, SID_A)
        assert (out.imported, out.skipped, out.id_map) == (0, 0, {})
```

- [ ] **Step 3: 실행해 실패 확인**

```bash
python -m pytest app/tests/test_history_repository.py -q
```

기대: 수집 오류 `E   ModuleNotFoundError: No module named 'repositories.history'`.

- [ ] **Step 4: 스키마**

```python
# app/schemas/history.py
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

HistoryKind = Literal["book", "paper", "research"]

# 검색어·연구 질문. 딥리서치 질문 상한(api/research.py ResearchCreate)과 맞춘다.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
RefId = Annotated[str, StringConstraints(max_length=64)]

IMPORT_MAX_ITEMS = 100


class HistoryItemIn(BaseModel):
    kind: HistoryKind
    title: Title
    params: dict = Field(default_factory=dict)
    snapshot: dict | None = None
    ai: dict | None = None
    ref_id: RefId | None = None

    @model_validator(mode="after")
    def _research_needs_ref(self):
        # 딥리서치 기록은 ref_id(job_id)로 보고서를 연다. 없으면 사이드바에서 눌러도 갈 곳이 없다.
        if self.kind == "research" and not self.ref_id:
            raise ValueError("research 기록에는 ref_id 가 필요하다")
        return self


class HistoryItemPatch(BaseModel):
    title: Title | None = None
    params: dict | None = None
    snapshot: dict | None = None
    ai: dict | None = None

    @model_validator(mode="after")
    def _required_columns_stay_set(self):
        # snapshot·ai 는 null 로 비울 수 있지만 title·params 는 NOT NULL 칸이다
        for name in ("title", "params"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} 은 null 로 바꿀 수 없다")
        return self


class ResearchStatus(BaseModel):
    status: str
    stage: str


class HistoryItemOut(BaseModel):
    id: uuid.UUID
    kind: HistoryKind
    title: str
    params: dict
    ref_id: str | None = None
    created_at: datetime
    updated_at: datetime
    has_snapshot: bool
    has_ai: bool
    research: ResearchStatus | None = None


class HistoryItemDetail(HistoryItemOut):
    snapshot: dict | None = None
    ai: dict | None = None


class HistoryListOut(BaseModel):
    items: list[HistoryItemOut]
    next_cursor: str | None = None


class HistoryImportItem(HistoryItemIn):
    id: uuid.UUID | None = None
    legacy_id: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = None
    created_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def _assume_utc(cls, value: datetime | None) -> datetime | None:
        # 시간대 없는 시각을 timestamptz 에 넣으면 DB 세션 시간대로 읽혀 순서가 어긋난다
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class HistoryImportIn(BaseModel):
    items: list[HistoryImportItem] = Field(max_length=IMPORT_MAX_ITEMS)


class HistoryImportOut(BaseModel):
    imported: int
    skipped: int
    id_map: dict[str, str]
```

- [ ] **Step 5: 저장소**

메서드 이름 `list` 가 클래스 본문에서 내장 `list` 를 가린다. 그 뒤 메서드의 **주석(annotation)** 에 `list[...]` 를 쓰면 정의 시점에 `'function' object is not subscriptable` 로 import 가 깨진다 — 그래서 `import_items` 의 인자는 `Sequence[...]` 로 적는다(메서드 본문 안의 `list(...)` 호출은 클래스 스코프를 건너뛰므로 내장 그대로다).

```python
# app/repositories/history.py
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.history import HistoryItem
from models.research import ResearchJob
from schemas.history import (
    HistoryImportItem, HistoryImportOut, HistoryItemDetail, HistoryItemIn,
    HistoryItemOut, HistoryItemPatch, HistoryKind, ResearchStatus,
)

_LIST_COLUMNS = (
    HistoryItem.id, HistoryItem.kind, HistoryItem.title, HistoryItem.params,
    HistoryItem.ref_id, HistoryItem.created_at, HistoryItem.updated_at,
    # 목록은 무거운 칸을 읽지 않고 있는지만 본다
    HistoryItem.snapshot.is_not(None).label("has_snapshot"),
    HistoryItem.ai.is_not(None).label("has_ai"),
)
_DETAIL_COLUMNS = (*_LIST_COLUMNS, HistoryItem.snapshot, HistoryItem.ai)
_ITEM_FIELDS = {"kind", "title", "params", "snapshot", "ai", "ref_id"}


def legacy_history_id(v1: str) -> uuid.UUID:
    """v1 기록 id(Date.now 13자리) → v2 id. 이전을 몇 번 해도 같은 id 가 나와야 중복이 쌓이지 않는다."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"nl-lib-history-v1:{v1}")


class InvalidCursor(ValueError):
    pass


def encode_cursor(created_at: datetime, item_id: uuid.UUID) -> str:
    return f"{created_at.isoformat()}|{item_id}"


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    at, sep, raw_id = cursor.rpartition("|")
    if not sep:
        raise InvalidCursor(cursor)
    try:
        # 인코딩하지 않은 "+"(시간대 오프셋)는 쿼리스트링에서 공백으로 풀린다. ISO 시각에는 공백이 없다.
        return datetime.fromisoformat(at.replace(" ", "+")), uuid.UUID(raw_id)
    except ValueError as e:
        raise InvalidCursor(cursor) from e


def _as_uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


class HistoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self, session_id: uuid.UUID, kind: HistoryKind | None, limit: int, before: str | None,
    ) -> tuple[list[HistoryItemOut], str | None]:
        """최신순 한 쪽과 다음 쪽 커서. 커서가 틀리면 InvalidCursor."""
        stmt = select(*_LIST_COLUMNS).where(
            HistoryItem.session_id == session_id, HistoryItem.deleted_at.is_(None),
        )
        if kind is not None:
            stmt = stmt.where(HistoryItem.kind == kind)
        if before is not None:
            at, item_id = decode_cursor(before)
            # created_at 이 같은 행이 쪽 경계에 걸려도 빠지거나 겹치지 않게 id 로 한 번 더 가른다
            stmt = stmt.where(or_(
                HistoryItem.created_at < at,
                and_(HistoryItem.created_at == at, HistoryItem.id < item_id),
            ))
        stmt = stmt.order_by(HistoryItem.created_at.desc(), HistoryItem.id.desc()).limit(limit + 1)
        rows = (await self.db.execute(stmt)).all()
        page = rows[:limit]
        statuses = await self._research_statuses(r.ref_id for r in page if r.kind == "research")
        items = [
            HistoryItemOut.model_validate({**r._mapping, "research": self._research_of(r, statuses)})
            for r in page
        ]
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return items, next_cursor

    async def get(self, session_id: uuid.UUID, item_id: uuid.UUID) -> HistoryItemDetail | None:
        row = (await self.db.execute(
            select(*_DETAIL_COLUMNS).where(
                HistoryItem.id == item_id,
                HistoryItem.session_id == session_id,
                HistoryItem.deleted_at.is_(None),
            )
        )).first()
        if row is None:
            return None
        statuses = await self._research_statuses([row.ref_id] if row.kind == "research" else [])
        return HistoryItemDetail.model_validate(
            {**row._mapping, "research": self._research_of(row, statuses)}
        )

    async def upsert(
        self, session_id: uuid.UUID, item_id: uuid.UUID, data: HistoryItemIn,
    ) -> HistoryItemDetail | None:
        """다른 브라우저의 행이면 None — 덮어쓰지 않는다.

        같은 브라우저가 다시 보내면 목록 맨 위로 올린다(created_at 갱신). 지운 기록이면
        되살린다. 요청에 빠진 snapshot·ai·ref_id 는 기존 값을 지킨다 — 재전송이나 중복
        병합이 이미 받은 결과·AI 요약을 지우지 않게.
        """
        stmt = insert(HistoryItem).values(id=item_id, session_id=session_id, **data.model_dump())
        stmt = stmt.on_conflict_do_update(
            index_elements=[HistoryItem.id],
            set_={
                "kind": stmt.excluded.kind,
                "title": stmt.excluded.title,
                "params": stmt.excluded.params,
                "snapshot": func.coalesce(stmt.excluded.snapshot, HistoryItem.snapshot),
                "ai": func.coalesce(stmt.excluded.ai, HistoryItem.ai),
                "ref_id": func.coalesce(stmt.excluded.ref_id, HistoryItem.ref_id),
                "created_at": func.now(),
                "updated_at": func.now(),
                "deleted_at": None,
            },
            where=HistoryItem.session_id == stmt.excluded.session_id,
        ).returning(HistoryItem.id)
        if (await self.db.execute(stmt)).first() is None:
            return None
        return await self.get(session_id, item_id)

    async def patch(
        self, session_id: uuid.UUID, item_id: uuid.UUID, data: HistoryItemPatch,
    ) -> HistoryItemDetail | None:
        res = await self.db.execute(
            update(HistoryItem)
            .where(
                HistoryItem.id == item_id,
                HistoryItem.session_id == session_id,
                HistoryItem.deleted_at.is_(None),
            )
            .values(**data.model_dump(exclude_unset=True), updated_at=func.now())
        )
        if res.rowcount == 0:
            return None
        return await self.get(session_id, item_id)

    async def soft_delete(self, session_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        """이 브라우저의 행이면 True. 이미 지운 행도 True — 재전송된 삭제가 404 로 되돌아오지 않게."""
        res = await self.db.execute(
            update(HistoryItem)
            .where(HistoryItem.id == item_id, HistoryItem.session_id == session_id)
            # 처음 지운 시각을 지킨다
            .values(deleted_at=func.coalesce(HistoryItem.deleted_at, func.now()))
        )
        return res.rowcount == 1

    async def soft_delete_kind(self, session_id: uuid.UUID, kind: HistoryKind) -> int:
        res = await self.db.execute(
            update(HistoryItem)
            .where(
                HistoryItem.session_id == session_id,
                HistoryItem.kind == kind,
                HistoryItem.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        return res.rowcount

    async def import_items(
        self, session_id: uuid.UUID, items: Sequence[HistoryImportItem],
    ) -> HistoryImportOut:
        """이미 있는 id 는 건너뛴다 — 지운 기록을 되살리지도, 남의 기록을 덮지도 않는다.

        id_map 은 건너뛴 항목까지 담는다. 두 번째 이전에서도 옛 ?restore= 주소를 새 id 로
        찾아야 하기 때문이다.
        """
        rows: dict[uuid.UUID, dict] = {}
        id_map: dict[str, str] = {}
        now = datetime.now(timezone.utc)
        for item in items:
            if item.id is not None:
                item_id = item.id
            elif item.legacy_id is not None:
                item_id = legacy_history_id(item.legacy_id)
            else:
                item_id = uuid.uuid4()
            if item.legacy_id is not None:
                id_map[item.legacy_id] = str(item_id)
            created_at = item.created_at or now
            rows.setdefault(item_id, {
                "id": item_id, "session_id": session_id,
                **item.model_dump(include=_ITEM_FIELDS),
                "created_at": created_at, "updated_at": created_at,
            })
        if not rows:
            return HistoryImportOut(imported=0, skipped=0, id_map={})
        inserted = (await self.db.execute(
            insert(HistoryItem).values(list(rows.values()))
            .on_conflict_do_nothing(index_elements=[HistoryItem.id])
            .returning(HistoryItem.id)
        )).all()
        return HistoryImportOut(
            imported=len(inserted), skipped=len(items) - len(inserted), id_map=id_map,
        )

    async def _research_statuses(self, refs: Iterable[str | None]) -> dict[uuid.UUID, ResearchStatus]:
        # ref_id = research_jobs.id::text 로 조인하면 PK 인덱스를 못 쓰고, ref_id 를 uuid 로
        # 캐스팅해 조인하면 형식이 틀린 값 하나에 조회 전체가 실패한다. 한 쪽(최대 100건)의
        # job id 만 모아 PK 로 한 번 더 읽는다.
        job_ids = {jid for jid in map(_as_uuid, refs) if jid is not None}
        if not job_ids:
            return {}
        rows = (await self.db.execute(
            select(ResearchJob.id, ResearchJob.status, ResearchJob.stage)
            .where(ResearchJob.id.in_(job_ids))
        )).all()
        return {r.id: ResearchStatus(status=r.status, stage=r.stage) for r in rows}

    @staticmethod
    def _research_of(row, statuses: dict[uuid.UUID, ResearchStatus]) -> ResearchStatus | None:
        if row.kind != "research":
            return None
        job_id = _as_uuid(row.ref_id)
        return statuses.get(job_id) if job_id is not None else None
```

- [ ] **Step 6: 실행해 통과 확인**

```bash
python -m pytest app/tests/test_history_repository.py -q
```

기대: `48 passed`.

전체 스위트 기대: **624 passed**.

- [ ] **Step 7: 커밋**

```bash
git add app/schemas/history.py app/repositories/history.py app/tests/history_sqlite.py app/tests/test_history_repository.py
git commit -m "[Feat] round04b — 기록 스키마·저장소(upsert·커서·소프트 삭제·v1 이전)"
```

---

### Task 4: 기록 API `/api/history` 와 앱 등록

**Files:**
- Create: `app/api/history.py`
- Modify: `app/main.py` (13행 라우터 import 뒤 1줄, 파일 끝 87행 `include_router` 뒤 1줄)
- Test: `app/tests/test_history_api.py`

엔드포인트(spec §4-4 표 그대로):

| 메서드·경로 | 성공 | 실패 |
|---|---|---|
| `GET /api/history?kind=&limit=30&before=` | 200 `HistoryListOut` | 헤더 400 · 틀린 커서 400 · `kind`/`limit`(1~100) 422 |
| `GET /api/history/{id}` | 200 `HistoryItemDetail` | 남의 것·없는 것·지운 것 404 · id 형식 422 |
| `PUT /api/history/{id}` | 200 `HistoryItemDetail` | snapshot 200KB 초과 413 · 남의 것 404 · research 인데 `ref_id` 없음 422 |
| `PATCH /api/history/{id}` | 200 `HistoryItemDetail` | 413 · 404 · `title`/`params` 에 null 422 |
| `DELETE /api/history/{id}` | 204(이미 지운 내 것도 204) | 404 |
| `DELETE /api/history?kind=` | 204 | `kind` 없음 422(실수로 전체를 지우지 않게 필수) |
| `POST /api/history/import` | 200 `HistoryImportOut` | 101건 이상 422. **200KB 넘는 snapshot 은 413 대신 그 항목의 snapshot 만 버리고 옮긴다**(한 건 때문에 묶음 전체가 매번 실패해 영영 이전되지 않는 것을 막는다. 원본은 브라우저 백업 키에 남는다) |

- snapshot 크기는 `json.dumps(ensure_ascii=False)` 의 **UTF-8 바이트**로 잰다(한글 한 글자 3바이트 — 글자 수로 세면 상한이 세 배 느슨해진다). 200KB = 204,800바이트, 같으면 통과.
- 쓰기 엔드포인트는 응답 전에 `await db.commit()` 한다. `get_db` 의 마무리 커밋에 맡기면 커밋이 실패해도 화면은 성공 응답을 받아 outbox 에 다시 넣지 않는다.

- [ ] **Step 1: 실패하는 테스트**

```python
# app/tests/test_history_api.py
"""test_history_api.py — 기록 API 엔드포인트

요청은 TestClient 로 실제 라우팅을 거친다(헤더 400·경로 422·본문 검증은 라우팅을 거쳐야
드러난다). DB 는 history_sqlite 의 SQLite 다 — 요청마다 세션을 새로 열고 get_db 처럼
끝나면 커밋, 예외면 되돌린다.
"""
import ast
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from history_sqlite import SID_A, SID_B, AsyncSessionOverSync, add_research_job, make_engine, raw_row

A = {"x-session-id": str(SID_A)}
B = {"x-session-id": str(SID_B)}


class _Api:
    def __init__(self, client, engine):
        self.client = client
        self.engine = engine

    def put(self, item_id, headers=A, **body):
        return self.client.put(f"/api/history/{item_id}", headers=headers,
                               json={"kind": "book", "title": "독서 격차", **body})


@pytest.fixture
def api():
    from api.history import router
    from core.deps import get_db

    engine = make_engine()

    async def _db():
        db = AsyncSessionOverSync(engine)
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _db
    return _Api(TestClient(app), engine)


def _ids(res) -> list[str]:
    return [i["id"] for i in res.json()["items"]]


class TestBrowserIdHeader:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/history"),
        ("get", f"/api/history/{uuid.uuid4()}"),
        ("delete", f"/api/history/{uuid.uuid4()}"),
        ("delete", "/api/history?kind=book"),
    ])
    def test_missing_header_is_400(self, api, method, path):
        res = getattr(api.client, method)(path)
        assert res.status_code == 400
        assert res.json()["detail"] == "x-session-id 헤더가 필요하다"

    def test_put_without_header_is_400_and_saves_nothing(self, api):
        item_id = uuid.uuid4()
        assert api.put(item_id, headers={}).status_code == 400
        assert raw_row(api.engine, item_id) is None

    def test_import_without_header_is_400(self, api):
        res = api.client.post("/api/history/import", json={"items": []})
        assert res.status_code == 400


class TestPut:
    def test_repeat_is_safe(self, api):
        item_id = uuid.uuid4()
        assert api.put(item_id).status_code == 200
        res = api.put(item_id, title="독서 격차 해소")
        assert res.status_code == 200 and res.json()["title"] == "독서 격차 해소"
        assert _ids(api.client.get("/api/history", headers=A)) == [str(item_id)]

    def test_response_shape(self, api):
        item_id = uuid.uuid4()
        body = api.put(item_id, params={"grade": "KCI"}, snapshot={"papers": []}).json()
        assert body["id"] == str(item_id)
        assert body["snapshot"] == {"papers": []} and body["has_snapshot"] is True
        assert body["ai"] is None and body["has_ai"] is False
        assert body["research"] is None and body["ref_id"] is None
        assert {"created_at", "updated_at"} <= body.keys()

    def test_research_without_ref_id_is_422(self, api):
        res = api.put(uuid.uuid4(), kind="research", title="독서 격차 연구")
        assert res.status_code == 422

    def test_malformed_item_id_is_422(self, api):
        assert api.client.get("/api/history/not-a-uuid", headers=A).status_code == 422


class TestOwnership:
    """남의 기록은 읽기·쓰기·삭제 모두 404 — 존재 여부도 드러내지 않는다."""

    @pytest.fixture
    def item_id(self, api):
        item_id = uuid.uuid4()
        api.put(item_id, title="A 의 검색", snapshot={"books": [1]})
        return item_id

    def test_read_is_404(self, api, item_id):
        res = api.client.get(f"/api/history/{item_id}", headers=B)
        assert res.status_code == 404
        assert res.json()["detail"] == "기록을 찾을 수 없다"

    def test_put_is_404_and_does_not_overwrite(self, api, item_id):
        assert api.put(item_id, headers=B, title="덮어쓰기").status_code == 404
        assert raw_row(api.engine, item_id).title == "A 의 검색"

    def test_patch_is_404(self, api, item_id):
        res = api.client.patch(f"/api/history/{item_id}", headers=B, json={"title": "바꿈"})
        assert res.status_code == 404
        assert raw_row(api.engine, item_id).title == "A 의 검색"

    def test_delete_is_404(self, api, item_id):
        assert api.client.delete(f"/api/history/{item_id}", headers=B).status_code == 404
        assert raw_row(api.engine, item_id).deleted_at is None

    def test_other_browser_list_is_empty(self, api, item_id):
        assert api.client.get("/api/history", headers=B).json() == {"items": [], "next_cursor": None}

    def test_missing_item_is_same_404(self, api):
        assert api.client.get(f"/api/history/{uuid.uuid4()}", headers=A).status_code == 404


class TestPatch:
    def test_partial_update(self, api):
        item_id = uuid.uuid4()
        api.put(item_id, snapshot={"books": [1]})
        res = api.client.patch(f"/api/history/{item_id}", headers=A,
                               json={"ai": {"intro": "요약", "items": []}})
        assert res.status_code == 200
        body = res.json()
        assert body["ai"] == {"intro": "요약", "items": []} and body["snapshot"] == {"books": [1]}

    def test_null_title_is_422(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        res = api.client.patch(f"/api/history/{item_id}", headers=A, json={"title": None})
        assert res.status_code == 422


class TestDelete:
    def test_soft_delete(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        res = api.client.delete(f"/api/history/{item_id}", headers=A)
        assert res.status_code == 204 and res.content == b""
        assert api.client.get(f"/api/history/{item_id}", headers=A).status_code == 404
        assert _ids(api.client.get("/api/history", headers=A)) == []
        # 행은 남는다 — 사용자 삭제는 데이터 삭제가 아니다
        assert raw_row(api.engine, item_id).deleted_at is not None

    def test_repeat_delete_is_204(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        api.client.delete(f"/api/history/{item_id}", headers=A)
        assert api.client.delete(f"/api/history/{item_id}", headers=A).status_code == 204

    def test_delete_kind(self, api):
        book, paper = uuid.uuid4(), uuid.uuid4()
        api.put(book, kind="book")
        api.put(paper, kind="paper")
        assert api.client.delete("/api/history?kind=book", headers=A).status_code == 204
        assert _ids(api.client.get("/api/history", headers=A)) == [str(paper)]
        assert raw_row(api.engine, book).deleted_at is not None

    def test_delete_without_kind_is_422(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        assert api.client.delete("/api/history", headers=A).status_code == 422
        assert raw_row(api.engine, item_id).deleted_at is None


class TestList:
    def test_kind_filter_and_limit_bounds(self, api):
        api.put(uuid.uuid4(), kind="book")
        paper = uuid.uuid4()
        api.put(paper, kind="paper")
        assert _ids(api.client.get("/api/history?kind=paper", headers=A)) == [str(paper)]
        assert api.client.get("/api/history?kind=chat", headers=A).status_code == 422
        assert api.client.get("/api/history?limit=0", headers=A).status_code == 422
        assert api.client.get("/api/history?limit=101", headers=A).status_code == 422

    def test_cursor_paging(self, api):
        items = [
            {"legacy_id": f"172700000000{n}", "kind": "book", "title": f"검색 {n}",
             "created_at": f"2026-09-0{n + 1}T09:00:00+00:00"}
            for n in range(3)
        ]
        api.client.post("/api/history/import", headers=A, json={"items": items})
        first = api.client.get("/api/history?limit=2", headers=A).json()
        assert [i["title"] for i in first["items"]] == ["검색 2", "검색 1"]
        second = api.client.get("/api/history", headers=A,
                                params={"limit": 2, "before": first["next_cursor"]}).json()
        assert [i["title"] for i in second["items"]] == ["검색 0"]
        assert second["next_cursor"] is None

    def test_malformed_cursor_is_400(self, api):
        res = api.client.get("/api/history?before=garbage", headers=A)
        assert res.status_code == 400


class TestSnapshotLimit:
    @staticmethod
    def _snapshot(size: int) -> dict:
        # {"b":"xxx…"} 의 직렬화 길이가 정확히 size 바이트가 되게 맞춘다
        return {"b": "x" * (size - len('{"b": ""}'))}

    def test_at_limit_is_accepted(self, api):
        assert api.put(uuid.uuid4(), snapshot=self._snapshot(200 * 1024)).status_code == 200

    def test_put_over_limit_is_413(self, api):
        item_id = uuid.uuid4()
        assert api.put(item_id, snapshot=self._snapshot(200 * 1024 + 1)).status_code == 413
        assert raw_row(api.engine, item_id) is None

    def test_patch_over_limit_is_413(self, api):
        item_id = uuid.uuid4()
        api.put(item_id)
        res = api.client.patch(f"/api/history/{item_id}", headers=A,
                               json={"snapshot": self._snapshot(200 * 1024 + 1)})
        assert res.status_code == 413
        assert raw_row(api.engine, item_id).snapshot is None

    def test_limit_counts_utf8_bytes(self, api):
        # 한글 한 글자는 3바이트 — 글자 수로 세면 상한이 세 배로 느슨해진다
        snapshot = {"b": "가" * (70 * 1024)}
        assert api.put(uuid.uuid4(), snapshot=snapshot).status_code == 413

    def test_import_drops_only_the_oversized_snapshot(self, api):
        res = api.client.post("/api/history/import", headers=A, json={"items": [
            {"legacy_id": "1727000000000", "kind": "book", "title": "큰 결과",
             "snapshot": self._snapshot(200 * 1024 + 1)},
            {"legacy_id": "1727000000001", "kind": "book", "title": "작은 결과",
             "snapshot": {"books": [1]}},
        ]})
        assert res.status_code == 200 and res.json()["imported"] == 2
        by_title = {i["title"]: i for i in api.client.get("/api/history", headers=A).json()["items"]}
        assert by_title["큰 결과"]["has_snapshot"] is False
        assert by_title["작은 결과"]["has_snapshot"] is True


class TestImport:
    ITEMS = [
        {"legacy_id": "1727000000000", "kind": "book", "title": "도서 검색",
         "created_at": "2026-09-01T09:00:00Z", "ai": {"intro": "요약", "items": []}},
        {"legacy_id": "1727000000001", "kind": "paper", "title": "논문 검색",
         "params": {"grade": "KCI"}, "created_at": "2026-09-02T09:00:00Z"},
    ]

    def test_import_then_repeat(self, api):
        first = api.client.post("/api/history/import", headers=A, json={"items": self.ITEMS})
        assert first.status_code == 200
        body = first.json()
        assert (body["imported"], body["skipped"]) == (2, 0)
        assert set(body["id_map"]) == {"1727000000000", "1727000000001"}

        second = api.client.post("/api/history/import", headers=A, json={"items": self.ITEMS}).json()
        assert (second["imported"], second["skipped"]) == (0, 2)
        assert second["id_map"] == body["id_map"]

        # 옛 ?restore=<v1id> 는 id_map 으로 찾은 새 id 로 열린다
        restored = api.client.get(f"/api/history/{body['id_map']['1727000000000']}", headers=A)
        assert restored.status_code == 200
        assert restored.json()["ai"] == {"intro": "요약", "items": []}

    def test_more_than_100_is_422(self, api):
        items = [{"legacy_id": str(n), "kind": "book", "title": "검색"} for n in range(101)]
        res = api.client.post("/api/history/import", headers=A, json={"items": items})
        assert res.status_code == 422


class TestResearchStatus:
    def test_list_and_detail_carry_job_status(self, api):
        job_id = add_research_job(api.engine, status="awaiting_approval", stage="planned")
        res = api.put(job_id, kind="research", title="독서 격차 연구", ref_id=str(job_id))
        assert res.json()["research"] == {"status": "awaiting_approval", "stage": "planned"}
        (item,) = api.client.get("/api/history?kind=research", headers=A).json()["items"]
        assert item["research"] == {"status": "awaiting_approval", "stage": "planned"}
        assert item["ref_id"] == str(job_id)


class TestAppWiring:
    def test_main_includes_history_router(self):
        # 테스트는 라우터를 직접 붙인다 — main.py 등록을 빠뜨려도 위 테스트는 모두 통과한다
        tree = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
        imported = {
            (node.module, alias.name, alias.asname)
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        included = {
            node.args[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "include_router"
        }
        assert ("api.history", "router", "history_router") in imported
        assert "history_router" in included
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
python -m pytest app/tests/test_history_api.py -q
```

기대: `1 failed, 33 errors` — 33건은 픽스처의 `from api.history import router` 가 `ModuleNotFoundError: No module named 'api.history'`, 1건은 `TestAppWiring`(main.py 미등록).

- [ ] **Step 3: 라우터**

```python
# app/api/history.py
"""history.py — 사이드바 기록 API

모든 요청은 x-session-id(브라우저 ID)로 소유를 가른다. 남의 기록과 없는 기록은 똑같이
404 다 — 구분하면 id 만으로 남의 기록이 있는지 떠볼 수 있다.

쓰기는 응답 전에 커밋한다. get_db 의 마무리 커밋에 맡기면 커밋이 실패해도 화면은 이미
성공 응답을 받아 outbox 에 다시 넣지 않는다.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_browser_id, get_db
from repositories.history import HistoryRepository, InvalidCursor
from schemas.history import (
    HistoryImportIn, HistoryImportOut, HistoryItemDetail, HistoryItemIn,
    HistoryItemPatch, HistoryKind, HistoryListOut,
)

router = APIRouter(prefix="/api/history", tags=["history"])

# 목록 카드를 다시 그릴 만큼만 담는 칸이다. 결과 전체(청크 원문)를 넣으면 행 하나가
# 수 MB 가 되고, 사이드바를 여는 것만으로 그만큼을 읽게 된다.
SNAPSHOT_MAX_BYTES = 200 * 1024


def _snapshot_bytes(snapshot: dict | None) -> int:
    if snapshot is None:
        return 0
    return len(json.dumps(snapshot, ensure_ascii=False).encode("utf-8"))


def _reject_large_snapshot(snapshot: dict | None) -> None:
    if _snapshot_bytes(snapshot) > SNAPSHOT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="snapshot 은 200KB 까지다 — 목록 카드 필드만 담는다")


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="기록을 찾을 수 없다")


@router.get("", response_model=HistoryListOut)
async def list_history(
    kind: HistoryKind | None = None,
    limit: int = Query(30, ge=1, le=100),
    before: str | None = None,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        items, next_cursor = await HistoryRepository(db).list(browser_id, kind, limit, before)
    except InvalidCursor:
        raise HTTPException(status_code=400, detail="before 형식이 올바르지 않다")
    return HistoryListOut(items=items, next_cursor=next_cursor)


@router.post("/import", response_model=HistoryImportOut)
async def import_history(
    req: HistoryImportIn,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    # 이전은 한 건이라도 413 이면 묶음 전체가 매번 실패해 영영 옮겨지지 않는다. 큰 결과만
    # 버리고 기록(제목·검색 조건)은 옮긴다 — 원본은 브라우저의 백업 키에 남아 있다.
    items = [
        item.model_copy(update={"snapshot": None})
        if _snapshot_bytes(item.snapshot) > SNAPSHOT_MAX_BYTES else item
        for item in req.items
    ]
    out = await HistoryRepository(db).import_items(browser_id, items)
    await db.commit()
    return out


@router.get("/{item_id}", response_model=HistoryItemDetail)
async def get_history_item(
    item_id: uuid.UUID,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    item = await HistoryRepository(db).get(browser_id, item_id)
    if item is None:
        raise _not_found()
    return item


@router.put("/{item_id}", response_model=HistoryItemDetail)
async def put_history_item(
    item_id: uuid.UUID,
    req: HistoryItemIn,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    _reject_large_snapshot(req.snapshot)
    item = await HistoryRepository(db).upsert(browser_id, item_id, req)
    if item is None:
        raise _not_found()
    await db.commit()
    return item


@router.patch("/{item_id}", response_model=HistoryItemDetail)
async def patch_history_item(
    item_id: uuid.UUID,
    req: HistoryItemPatch,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    _reject_large_snapshot(req.snapshot)
    item = await HistoryRepository(db).patch(browser_id, item_id, req)
    if item is None:
        raise _not_found()
    await db.commit()
    return item


@router.delete("/{item_id}", status_code=204, response_class=Response)
async def delete_history_item(
    item_id: uuid.UUID,
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    if not await HistoryRepository(db).soft_delete(browser_id, item_id):
        raise _not_found()
    await db.commit()
    return Response(status_code=204)


@router.delete("", status_code=204, response_class=Response)
async def delete_history_kind(
    # 종류를 빠뜨린 요청이 기록 전체를 지우지 않게 필수로 둔다
    kind: HistoryKind = Query(...),
    browser_id: uuid.UUID = Depends(get_browser_id),
    db: AsyncSession = Depends(get_db),
):
    await HistoryRepository(db).soft_delete_kind(browser_id, kind)
    await db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: 실행 — 등록 테스트만 남는지 확인**

```bash
python -m pytest app/tests/test_history_api.py -q
```

기대: `1 failed, 33 passed` — `TestAppWiring::test_main_includes_history_router`.

- [ ] **Step 5: `app/main.py` 에 라우터 등록**

현재(12~13행):

```python
from api.scenario import router as scenario_router
from api.research import router as research_router
```

13행 뒤에 한 줄:

```python
from api.research import router as research_router
from api.history import router as history_router
```

현재 파일 끝(86~87행, 87행 뒤에 줄바꿈 없음):

```python
app.include_router(scenario_router)
app.include_router(research_router)
```

한 줄을 더한다:

```python
app.include_router(scenario_router)
app.include_router(research_router)
app.include_router(history_router)
```

- [ ] **Step 6: 실행해 통과 확인**

```bash
python -m pytest app/tests/test_history_api.py -q
```

기대: `34 passed`.

전체 스위트 기대: **658 passed**(기준선 549 + 11 + 16 + 48 + 34).

- [ ] **Step 7: 커밋**

```bash
git add app/api/history.py app/main.py app/tests/test_history_api.py
git commit -m "[Feat] round04b — 기록 API /api/history 와 앱 등록"
```

---

#### 영역 A 참고 메모

- **영역 B(딥리서치 보강)** 는 `app/core/deps.py` 를 고치지 않고 `get_browser_id_optional` 을 import 해 쓴다: `POST /api/research` 에 `browser_id: uuid.UUID | None = Depends(get_browser_id_optional)` 를 더하고 `created_by=str(browser_id) if browser_id else None`. 따라서 **Task 2 가 Task 10(`created_by`)보다 먼저** 들어가야 한다. B 는 `research_jobs` 의 `id`·`status`·`stage` 컬럼을 바꾸지 않는다(이 영역이 읽는다).
- **영역 C1(프론트 기록 저장소)** 는: 모든 `/api/history` 호출에 `x-session-id` 를 붙이고(`useApi`), `title` 을 공백 제거 후 1~500자로 맞추고(넘으면 422 — 4xx 라 outbox 가 재전송하지 않아 기록이 사라진다), import 를 100건 이하 묶음으로 나누고, snapshot 을 `slimBookResult`/`slimPaperResult` 로 줄여 보낸다. 413 이면 snapshot 없이 한 번 더 PUT 한다(Task 20 의 `add`). v1 `timestamp` 는 ISO 문자열로 바꿔 `created_at` 에 싣는다(시간대 없는 시각은 서버가 UTC 로 본다).
- **v1 id 충돌:** `legacy_history_id` 는 계약대로 v1 id 만으로 만든다(세션을 섞지 않는다). 서로 다른 브라우저가 같은 밀리초에 만든 v1 기록이 있으면 나중에 이전하는 쪽은 건너뛰어진다(`ON CONFLICT DO NOTHING` — 남의 행을 덮지 않는다). 확률은 무시할 만하고, 그 브라우저의 원본은 `skx_search_history_backup_v1` 에 남는다.
- **배포:** 테이블은 fastapi lifespan 의 `create_all` 이 만들고, 배포 뒤 `alembic stamp 0006_history_items` 로 맞춘다(spec §4-3, round04a `0005` 와 같은 절차). 배포 절차·운영 검증은 Task 37 에 있다.
- **로컬 환경:** SQLAlchemy 2.0.36 · FastAPI 0.133.1 · Pydantic 2.13.4 · sqlite 3.53.1 · Python `sqlite3` 표준 모듈. `alembic`·`aiosqlite`·Postgres 없음. SQLite 테스트는 SQLAlchemy 의 SQLite 컴파일러가 `postgresql.insert` 의 `ON CONFLICT` 절을 그리는 것에 기댄다 — SQLAlchemy 를 올려 이게 깨지면 **테스트만** 깨지고 운영 코드는 영향이 없다.
- **`app/main.py` 는 Task 1(lifespan 1줄)과 Task 4(import 1줄·include 1줄)가 고친다.** 다른 영역이 `main.py` 를 고친다면 같은 블록이 아니어서 충돌은 작다.
- **SQLite 의 시간 해상도:** `now()` 가 SQLite 에서는 초 단위 `CURRENT_TIMESTAMP` 다. 그래서 순서를 보는 테스트는 import 로 `created_at` 을 명시해 만든다(같은 초에 PUT 한 행끼리의 순서에 기대는 테스트는 두지 않았다). Postgres 는 마이크로초라 운영에서는 문제가 없다.
- 기존 `search_history`·`search_sessions` 테이블과 `GET /api/books/history/{session_id}` 는 읽지도 바꾸지도 않는다(spec §4-3·§11).

---

### 영역 B 개요 — 딥리서치 백엔드 이벤트 보강

> spec §5 (D8) — "이벤트로 흘려보내는 것은 전부 `research_steps.result` 에도 남긴다." DB 변경 없음(기존 JSONB 칸·기존 컬럼만).

**목표:** 진행 화면이 폴링 없이 SSE 만으로 상태·단계·회차·카운터·종합 진행을 그리고, 끝난 잡을 다시 열어도 같은 장면(자기점검 회차 이력·절 진행)을 재생할 수 있게 한다.

**검증 방식(작성 시점):** 이 영역의 모든 테스트·구현 코드는 저장소 사본(스크래치)에 그대로 적용해 돌려 확인했다. Step 2 의 실패 출력과 Step 4 의 통과 수는 그 실측값이다. 사본 기준 이 영역 테스트는 Task 5~Task 11 이 +61, Task 12 가 +9 다. 각 Task 의 전체 회귀 기대치는 영역 A(Task 1~4, 658 passed) 뒤 순서 기준으로 적었다 — 영역 A·B 를 합친 사본에서 마지막 값 728 passed 를 확인했다.

**테스트 명령(공통):**

```bash
python -m pytest app/tests -q --ignore=app/tests/test_book_chat.py --ignore=app/tests/test_build_manifest.py --ignore=app/tests/test_loaders.py
```

**이 영역이 만드는 이벤트 계약 한눈에 (C2 프론트가 읽는 모양):**

| kind | payload | 발행처 |
|---|---|---|
| `snapshot` | `{steps:[{seq, kind, subq_idx, title, detail, status, result}], job:{status, stage, plan, counters?}}` — steps 는 `GET` 의 steps 와 같은 모양(단계 종류 키는 `kind`). `counters` 는 Task 12 — 끝난 잡은 `report.stats`, 도는 잡은 단계 result 에 마지막으로 남은 값, 없으면 키가 없다 | API 스트림 연결 직후 · 스트림 하트비트(DB 상태·단계가 화면이 아는 값과 다르거나, 계획이 생겼는데 화면에 준 적이 없으면 다시 읽어 같은 모양으로 한 번 더) |
| `status` | `{status, stage}` | 워커(planning·awaiting_approval·running(planned/explored)), API(approved·queued·되돌린 awaiting_approval). 놓친 전이는 스트림 하트비트가 snapshot 으로 되살린다 |
| `step` | `{seq, step_kind, subq_idx, title, detail, status, result?}` — 열 때 `status:"running"`(result 없음), 탐색 중 회차가 끝날 때·종합 중 절이 바뀔 때 `running` + 지금까지의 result(Task 12), 닫을 때 `done`/`failed` + 저장한 result 그대로 | 워커 `_step`·`_save_progress`·`_finish` |
| `search` | 기존 `{subq_idx, query, found}` + `round`(1부터), `new_papers` | 러너 |
| `counters` | `{papers_reviewed, evidence_adopted, rechecks}` — 잡 전체·고유 논문 | 러너, 검색 결과를 근거로 묶은 직후(회차마다 1회) |
| `critique` | 기존 `{subq_idx, verdict, note, adopted, parse_failed, capped}` + `round`, `next_query`(다음 회차에 **실제로** 검색할 검색어, 재검색 안 하면 null), `will_recheck`(= next_query 가 null 이 아님) | 러너 |
| `synth` | `{section_idx, total, status}` — section_idx 는 **절 순번(0부터)**, total 은 근거 있는 하위질문 수, status 는 `running`→`done`/`failed` | 워커(`synthesize` 의 on_section) |
| `done`·`failed`·`canceled` | 변경 없음. **종료 상태는 status 이벤트를 따로 내지 않는다** — 종료 프레임의 `status` 필드가 그 역할이다 | 기존 그대로 |

상태 이벤트 순서(정상): `planning/created` → `awaiting_approval/planned` → `approved/planned` → `running/planned` → `running/explored`(종합 시작) → 종료 프레임. 재시도: `queued/<stage>` → `running/<stage>`.

---

### Task 5: 실행 상태에 검토 논문·회차 이력 보강

`ResearchState.seen_cnts`(검토한 고유 논문)·`SubQuestion.rounds`(회차 이력)를 추가하고 스냅샷 왕복에 태운다. 카운터와 보고서 서론이 같은 숫자를 쓰도록 `research_stats()` 를 둔다.

**Files:**
- Modify: `app/services/research/state.py` (SubQuestion 끝 `chunk_scores` 뒤 ~L135, ResearchState `evidence` 뒤 ~L144, `snapshot_state` ~L170-178, `restore_state` 끝 ~L220-221)
- Test: `app/tests/test_research_state.py` (import L5-8, 파일 끝에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_research_state.py` 상단 import 를 바꾼다.

교체 전:
```python
from services.research.state import (
    _PARAM_BOUNDS, DEFAULT_PARAMS, VERDICTS, Chunk, Evidence, ResearchState, SubQuestion,
    merge_params, restore_state, snapshot_state,
)
```
교체 후:
```python
from services.research.state import (
    _PARAM_BOUNDS, DEFAULT_PARAMS, VERDICTS, Chunk, Evidence, ResearchState, SubQuestion,
    merge_params, research_stats, restore_state, snapshot_state,
)
```

파일 끝(`TestSnapshotEvolution.test_params_are_refilled_with_defaults` 뒤)에 추가한다.

```python


_ROUNDS = [
    {"round": 1, "query": "q1", "found_chunks": 12, "new_papers": 7,
     "verdict": "insufficient", "note": "2015년 이후 자료가 없다", "next_query": "q2"},
    {"round": 2, "query": "q2", "found_chunks": 9, "new_papers": 3,
     "verdict": "sufficient", "note": "충분하다", "next_query": None},
]


class TestSeenPapers:
    """검토한 고유 논문은 진행 카운터와 보고서 서론의 원천이다 — 재개해도 같아야 한다."""

    def test_new_state_has_seen_nothing(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert st.seen_cnts == set()

    def test_subquestion_has_no_rounds_by_default(self):
        assert SubQuestion(idx=0, text="하위").rounds == []

    def test_seen_papers_survive_round_trip(self):
        st = _explored_state()
        st.seen_cnts = {"KCI_C", "KCI_A", "KCI_B"}
        snap = snapshot_state(st)
        # 집합은 JSONB 에 들어가지 않는다 — 정렬한 목록이라야 왕복 비교도 결정론적이다
        assert snap["seen_cnts"] == ["KCI_A", "KCI_B", "KCI_C"]
        assert restore_state("j1", snap).seen_cnts == {"KCI_A", "KCI_B", "KCI_C"}

    def test_old_snapshot_falls_back_to_adopted_papers(self):
        """보강 전 스냅샷에는 seen_cnts 가 없다. 빈 집합으로 두면 재개한 보고서가
        '논문 0편을 검토하고 1편을 근거로 삼았다'고 쓴다."""
        snap = snapshot_state(_explored_state())
        del snap["seen_cnts"]
        assert restore_state("j1", snap).seen_cnts == {"KCI_A"}

    def test_empty_seen_list_is_trusted(self):
        # 키가 있는 빈 목록까지 하한으로 바꾸면 왕복할 때마다 값이 달라진다
        snap = snapshot_state(_explored_state())
        assert snap["seen_cnts"] == []
        assert restore_state("j1", snap).seen_cnts == set()

    def test_rounds_survive_round_trip(self):
        st = _explored_state()
        st.subquestions[0].rounds = [dict(r) for r in _ROUNDS]
        back = restore_state("j1", snapshot_state(st))
        assert back.subquestions[0].rounds == _ROUNDS
        assert back.subquestions[1].rounds == []

    def test_old_snapshot_without_rounds_gets_empty_history(self):
        snap = snapshot_state(_explored_state())
        for sq in snap["subquestions"]:
            del sq["rounds"]
        assert [s.rounds for s in restore_state("j1", snap).subquestions] == [[], [], []]

    def test_snapshot_carries_every_state_field(self):
        """ResearchState 의 필드는 손으로 나열해 담는다 — 필드를 추가하고 여기에 빠뜨리면
        재개한 잡에서만 그 값이 기본값으로 돌아간다. job_id 는 컬럼이 따로 있다."""
        snap = snapshot_state(_explored_state())
        assert set(snap) == {f.name for f in fields(ResearchState)} - {"job_id"}


class TestResearchStats:
    def test_counts_unique_papers_adopted_evidence_and_rechecks(self):
        st = _explored_state()          # 검색어 이력: ["q1", "q2"], ["q3"], []
        st.seen_cnts = {"KCI_A", "KCI_B", "KCI_C"}
        assert research_stats(st) == {
            "papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 1,
        }

    def test_empty_state_is_all_zero(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert research_stats(st) == {
            "papers_reviewed": 0, "evidence_adopted": 0, "rechecks": 0,
        }

    def test_same_after_resume(self):
        st = _explored_state()
        st.seen_cnts = {"KCI_A", "KCI_B"}
        assert research_stats(restore_state("j1", snapshot_state(st))) == research_stats(st)
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_state.py -q`
Expected: 수집 단계 실패 — `ImportError: cannot import name 'research_stats' from 'services.research.state'`, `1 error during collection`

- [ ] **Step 3: 최소 구현**

`app/services/research/state.py` — `SubQuestion` 끝.

교체 전:
```python
    chunk_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ResearchState:
```
교체 후:
```python
    chunk_scores: dict[str, float] = field(default_factory=dict)
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query}].
    # verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다.
    rounds: list[dict] = field(default_factory=list)


@dataclass
class ResearchState:
```

`ResearchState` 의 `evidence` 뒤.

교체 전:
```python
    evidence: dict[str, Evidence] = field(default_factory=dict)
    # 실행 시점의 수록 범위 — 코퍼스가 계속 자라므로 보고서에 고정 문구로
```
교체 후:
```python
    evidence: dict[str, Evidence] = field(default_factory=dict)
    # 검색에서 본 고유 논문(cnts_id). 청크 수로 세면 한 논문의 여러 대목이 따로 세이고,
    # 하위질문마다 세면 재사용 논문이 겹친다 — "논문 N편을 검토"는 이 집합의 크기다.
    seen_cnts: set[str] = field(default_factory=set)
    # 실행 시점의 수록 범위 — 코퍼스가 계속 자라므로 보고서에 고정 문구로
```

`snapshot_state` 의 반환 dict 끝.

교체 전:
```python
        "subquestions": [asdict(s) for s in state.subquestions],
        "evidence": {
            eid: {
                "cnts_id": ev.cnts_id, "meta": ev.meta,
                "chunks": [asdict(c) for c in ev.chunks],
            }
            for eid, ev in state.evidence.items()
        },
    }
```
교체 후:
```python
        "subquestions": [asdict(s) for s in state.subquestions],
        "evidence": {
            eid: {
                "cnts_id": ev.cnts_id, "meta": ev.meta,
                "chunks": [asdict(c) for c in ev.chunks],
            }
            for eid, ev in state.evidence.items()
        },
        # 집합은 JSONB 에 들어가지 않는다. 정렬해 두면 왕복 비교도 결정론적이다.
        "seen_cnts": sorted(state.seen_cnts),
    }
```

`restore_state` 끝과 그 뒤(파일 끝)에 함수 둘을 추가한다.

교체 전:
```python
        for eid, e in snap["evidence"].items()
    }
    return st
```
교체 후:
```python
        for eid, e in snap["evidence"].items()
    }
    st.seen_cnts = _restored_seen_cnts(snap)
    return st


def _restored_seen_cnts(snap: dict) -> set[str]:
    """보강 전 스냅샷에는 seen_cnts 가 없다. 채택한 논문은 적어도 검토한 것이니 그걸
    하한으로 쓴다 — 빈 집합으로 두면 재개한 보고서가 "0편을 검토하고 11편을 근거로
    삼았다"고 쓴다. 키가 있으면 빈 목록이라도 그대로 믿는다."""
    if "seen_cnts" in snap:
        return set(snap["seen_cnts"])
    return {e["cnts_id"] for e in snap["evidence"].values()}


def research_stats(state: ResearchState) -> dict:
    """진행 카운터와 보고서 서론의 숫자. 둘이 같은 함수를 봐야 진행 중에 본 숫자와
    보고서의 숫자가 어긋나지 않는다.

    재검색 횟수는 따로 세지 않고 시도한 검색어 이력에서 얻는다 — 검색어는 이미
    스냅샷에 실리므로 재개한 잡에서도 같은 값이 나온다.
    """
    return {
        "papers_reviewed": len(state.seen_cnts),
        "evidence_adopted": len(state.evidence),
        "rechecks": sum(max(len(sq.queries) - 1, 0) for sq in state.subquestions),
    }
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_state.py -q`
Expected: `51 passed`
전체 회귀(공통 명령): **669 passed**(Task 4 뒤 658 + 11). 기존 `test_snapshot_carries_every_dataclass_field`·`test_round_trip_is_stable` 이 `rounds`·`seen_cnts` 추가 뒤에도 그대로 통과해야 한다.

- [ ] **Step 5: 커밋**

```bash
git add app/services/research/state.py app/tests/test_research_state.py
git commit -m "[Feat] round04b — 딥리서치 상태에 검토 논문·회차 이력 추가, 스냅샷 왕복·진행 통계"
```

---

### Task 6: 러너 — 회차·새 논문·다음 검색어·카운터 이벤트와 회차 이력

`search` 에 `round`·`new_papers`, `critique` 에 `round`·`next_query`·`will_recheck` 를 싣고, 검색 결과를 근거로 묶은 직후 `counters` 를 낸다. 같은 내용을 `subq.rounds` 에 남긴다(워커가 Task 9 에서 search 단계 result 에 쓴다). 재검색 판단을 `_recheck_query()` 로 뽑아 `critique` 이벤트가 **다음 회차에 실제로 검색할 검색어**를 싣게 한다.

**Files:**
- Modify: `app/services/research/runner.py` (import L22, `_as_seen_by` 뒤 L68-69 에 헬퍼 추가, `explore_subquestion` L72-170 교체)
- Test: `app/tests/test_research_runner.py` (L211 기존 단언 수정, `class TestReadTransaction:` L232 바로 위에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

`test_emit_is_called_for_progress` 의 search 단언을 바꾼다(검색 이벤트에 키가 늘어 정확 비교가 깨진다).

교체 전:
```python
        assert by_kind["search"] == {"subq_idx": 0, "query": "가", "found": 1}
```
교체 후:
```python
        assert by_kind["search"] == {
            "subq_idx": 0, "query": "가", "found": 1, "round": 1, "new_papers": 1,
        }
```

`class TestReadTransaction:` 바로 위에 추가한다.

```python
def _recorder():
    events: list[tuple[str, dict]] = []

    async def _emit(kind, payload):
        events.append((kind, payload))

    return events, _emit


def _of(events, kind):
    return [p for k, p in events if k == kind]


def _explore_table(table):
    async def _explore(query, *, params, db):
        return _hits(table[query], query=query)
    return _explore


class TestRoundEvents:
    """화면이 회차·새 논문·다음 검색어를 뒤이은 이벤트로 추론하지 않고 그대로 받는다."""

    def _run(self, st, *, explore, critic=None):
        events, emit = _recorder()
        for sq in st.subquestions:
            asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=explore,
                                            critique_fn=critic or _FakeCritic(), emit=emit))
        return events

    def _state(self, *texts, **params):
        st = ResearchState(job_id="j", question="q", params=merge_params(params))
        st.subquestions = [SubQuestion(idx=i, text=t) for i, t in enumerate(texts)]
        return st

    def test_search_carries_round_and_new_papers(self):
        st = self._state("가", max_recheck=1)
        events = self._run(st, explore=_explore_table(
            {"가": ["A", "B"], "다른 검색어 1": ["B", "C", "D"]}))
        assert [(s["round"], s["query"], s["found"], s["new_papers"])
                for s in _of(events, "search")] == [(1, "가", 2, 2), (2, "다른 검색어 1", 3, 2)]

    def test_paper_seen_in_an_earlier_subquestion_is_not_new(self):
        """재사용 근거를 새 논문으로 세면 카운터가 하위질문 수만큼 부풀려진다."""
        st = self._state("가", "나", max_recheck=0)
        events = self._run(st, explore=_fake_explore)
        assert [s["new_papers"] for s in _of(events, "search")] == [1, 0]
        assert st.seen_cnts == {"A"}

    def test_chunks_of_one_paper_count_once(self):
        async def _two_chunks(query, *, params, db):
            hits, meta = _hits(["A"], query=query)
            hits.append({**hits[0], "chunk_id": "A-c-2", "score": 0.5, "rank_score": 0.5})
            return hits, meta

        st = self._state("가", max_recheck=0)
        (search,) = _of(self._run(st, explore=_two_chunks), "search")
        assert (search["found"], search["new_papers"]) == (2, 1)

    def test_paper_without_catalog_meta_is_not_counted(self):
        # 서지가 없는 논문은 근거가 되지 못한다(build_evidence) — 검토한 논문으로 세면 숫자만 부풀린다
        async def _no_meta_for_b(query, *, params, db):
            hits, meta = _hits(["A", "B"], query=query)
            del meta["B"]
            return hits, meta

        st = self._state("가", max_recheck=0)
        (search,) = _of(self._run(st, explore=_no_meta_for_b), "search")
        assert search["new_papers"] == 1
        assert st.seen_cnts == {"A"}

    def test_critique_names_the_query_it_will_search_next(self):
        st = self._state("가", max_recheck=1)
        events = self._run(st, explore=_fake_explore)
        critiques = _of(events, "critique")
        assert [(c["round"], c["next_query"], c["will_recheck"]) for c in critiques] == [
            (1, "다른 검색어 1", True), (2, None, False)]
        assert _of(events, "search")[1]["query"] == critiques[0]["next_query"]

    def test_no_next_query_when_every_suggestion_was_tried(self):
        st = self._state("AI 윤리", max_recheck=3)
        (critique,) = _of(self._run(st, explore=_fake_explore,
                                    critic=_SuggestingCritic(["ai 윤리"])), "critique")
        assert critique["verdict"] == "insufficient"
        assert (critique["next_query"], critique["will_recheck"]) == (None, False)

    def test_no_recheck_once_the_evidence_cap_is_reached(self):
        st = self._state("가", max_recheck=3, max_evidence=1)
        (critique,) = _of(self._run(st, explore=_fake_explore), "critique")
        assert critique["will_recheck"] is False

    def test_counters_follow_each_search(self):
        st = self._state("가", max_recheck=1)
        events = self._run(st, explore=_explore_table(
            {"가": ["A", "B"], "다른 검색어 1": ["B", "C"]}))
        assert [k for k, _ in events] == [
            "search", "counters", "critique", "search", "counters", "critique"]
        assert _of(events, "counters") == [
            {"papers_reviewed": 2, "evidence_adopted": 2, "rechecks": 0},
            {"papers_reviewed": 3, "evidence_adopted": 3, "rechecks": 1},
        ]

    def test_counters_are_job_wide(self):
        st = self._state("가", "나", max_recheck=0)
        events = self._run(st, explore=_fake_explore)
        assert _of(events, "counters")[-1] == {
            "papers_reviewed": 1, "evidence_adopted": 1, "rechecks": 0,
        }


class TestRoundHistory:
    """이벤트로 흘린 장면은 subq.rounds 에도 남는다 — 워커가 그걸 search 단계 result 에 쓴다."""

    def _explore(self):
        return _explore_table({"가": ["A", "B"], "다른 검색어 1": ["B", "C", "D"]})

    def test_every_round_is_recorded_on_the_subquestion(self):
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        sq = SubQuestion(idx=0, text="가")
        st.subquestions = [sq]
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=self._explore(),
                                        critique_fn=_FakeCritic(), emit=None))
        assert sq.rounds == [
            {"round": 1, "query": "가", "found_chunks": 2, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1"},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None},
        ]

    def test_history_matches_what_was_streamed(self):
        """라이브로 본 장면과 끝난 뒤 다시 연 장면이 같아야 한다."""
        events, emit = _recorder()
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 1}))
        sq = SubQuestion(idx=0, text="가")
        st.subquestions = [sq]
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=self._explore(),
                                        critique_fn=_FakeCritic(), emit=emit))
        streamed = [
            {"round": s["round"], "query": s["query"], "found_chunks": s["found"],
             "new_papers": s["new_papers"], "verdict": c["verdict"], "note": c["note"],
             "next_query": c["next_query"]}
            for s, c in zip(_of(events, "search"), _of(events, "critique"))
        ]
        assert sq.rounds == streamed
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_runner.py -q`
Expected: `12 failed, 26 passed` — 수정한 `test_emit_is_called_for_progress` 1건 + `TestRoundEvents` 9건 + `TestRoundHistory` 2건. 메시지는 `KeyError: 'round'`·`KeyError: 'new_papers'`·`KeyError: 'next_query'`, counters 순서 단언의 `AssertionError`, 회차 이력의 `assert [] == [{'round': 1, ...}]`(Task 5 로 `rounds` 필드는 있지만 비어 있다)

- [ ] **Step 3: 최소 구현**

`app/services/research/runner.py` import.

교체 전:
```python
from services.research.state import Evidence, HitRow, ResearchState, SubQuestion
```
교체 후:
```python
from services.research.state import (
    Evidence, HitRow, ResearchState, SubQuestion, research_stats,
)
```

`_as_seen_by` 부터 `explore_subquestion` 끝(`return subq`)까지를 아래로 통째로 교체한다. 근거 연결 루프(`known_by_cnts` ~ `subq.capped = len(capped)`)와 critic 호출·parse_failed 주석은 기존 그대로다.

```python
def _as_seen_by(ev: Evidence, subq: SubQuestion) -> Evidence:
    return Evidence(id=ev.id, cnts_id=ev.cnts_id, meta=ev.meta, chunks=chunks_for(ev, subq))


def _mark_seen(state: ResearchState, hits: list[HitRow], meta: dict[str, dict]) -> int:
    """이번 검색에서 처음 본 논문 수. 하위질문을 건너 같은 논문을 다시 세지 않는다.

    서지가 없는 논문은 build_evidence 가 버린다 — 검토한 논문으로 세면 근거가 될 수
    없던 것까지 "검토"로 부풀린다.
    """
    fresh = {h["book_id"] for h in hits if h["book_id"] in meta} - state.seen_cnts
    state.seen_cnts |= fresh
    return len(fresh)


def _recheck_query(
    state: ResearchState, subq: SubQuestion, verdict: Verdict, *, recheck: int,
) -> str | None:
    """다음 회차에 검색할 검색어. 재검색하지 않으면 None."""
    params = state.params
    if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"]):
        return None
    # 상한에 닿으면 새 근거가 생길 수 없다 — 재검색은 검색·LLM 호출만 태운다.
    if len(state.evidence) >= params["max_evidence"]:
        return None
    return _next_query(verdict.new_queries, subq.queries)


async def explore_subquestion(
    state: ResearchState,
    subq: SubQuestion,
    *,
    db: AsyncSession | None,
    explore_fn: ExploreFn = _explore,
    critique_fn: CritiqueFn = _critique,
    emit: EmitFn | None = None,
) -> SubQuestion:
    """한 하위질문을 탐색하고, 부족하면 쿼리를 바꿔 상한까지 재탐색한다.

    회차마다 subq.rounds 에 한 줄을 남긴다 — 이벤트로 흘린 자기점검 장면을 끝난
    잡에서 다시 보여 주려면 저장된 이력이 있어야 한다.
    """
    emit = emit or _noop_emit
    params = state.params
    query = subq.text
    recheck = 0
    relevance: dict[str, float] = {}
    leaders: list[str] = []
    capped: set[str] = set()

    while True:
        round_no = recheck + 1
        subq.queries.append(query)
        hits, meta = await explore_fn(query, params=params, db=db)
        # 읽기 트랜잭션을 여기서 끝낸다. 이어지는 critic 은 LLM 을 수십 초 기다리는데,
        # 그동안 세션이 library_catalog 공유 잠금을 쥐고 있으면 FastAPI 기동 시
        # lifespan 의 ALTER TABLE library_catalog 가 막히고 그 뒤 모든 조회가 줄 선다.
        if db is not None:
            await db.commit()
        new_papers = _mark_seen(state, hits, meta)
        await emit("search", {
            "subq_idx": subq.idx, "query": query, "found": len(hits),
            "round": round_no, "new_papers": new_papers,
        })

        # 같은 논문이 여러 하위질문에서 나오면 근거를 새로 만들지 않고 재사용한다.
        # 안 그러면 한 논문이 E3 와 E17 로 갈라져 인용칩이 같은 출처를 다른
        # 번호로 가리킨다. 번호는 state.evidence 를 소유한 이쪽이 붙인다 —
        # build_evidence 는 묶기만 하고 id 를 비워 돌려준다.
        known_by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
        best = _best_rank(hits)
        before = set(subq.evidence_ids)
        linked: list[str] = []
        for cand in build_evidence(
            hits, meta, chunks_per_evidence=params["chunks_per_evidence"],
        ):
            eid = known_by_cnts.get(cand.cnts_id)
            if eid is None:
                # break 가 아니라 continue 다. 상한에 닿은 뒤에 나오는 후보 중에도
                # "이미 있는 근거의 재사용"이 섞여 있는데, 그건 총량을 늘리지 않는다.
                # break 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다.
                if len(state.evidence) >= params["max_evidence"]:
                    capped.add(cand.cnts_id)
                    continue
                eid = evidence_id(len(state.evidence))
                state.evidence[eid] = Evidence(id=eid, cnts_id=cand.cnts_id, meta=cand.meta)
                known_by_cnts[cand.cnts_id] = eid
            # 재사용이어도 이번 검색에서 매칭된 대목은 버리지 않는다 — 그 하위질문의
            # critic 발췌·절 요약·호버는 이 대목을 써야 한다.
            link_chunks(state.evidence[eid], subq, cand.chunks,
                        limit=params["chunks_per_evidence"])
            relevance[eid] = max(relevance.get(eid, float("-inf")), best[cand.cnts_id])
            if eid not in linked:
                linked.append(eid)

        fresh = [e for e in linked if e not in before]
        if fresh:
            leaders.append(fresh[0])
        subq.evidence_ids = _rank_order(subq.evidence_ids + fresh, relevance, leaders)
        subq.capped = len(capped)
        await emit("counters", research_stats(state))

        verdict = await critique_fn(
            subq, [_as_seen_by(state.evidence[e], subq) for e in subq.evidence_ids],
            params=params,
        )
        subq.verdict = verdict.verdict
        subq.note = verdict.note
        # 판정을 못 받았다는 표시를 여기서 옮기지 않으면 보고서까지 닿지 않는다 —
        # synthesizer.build_limitations 는 subq.parse_failed 만 보고 "자동 점검을
        # 완료하지 못한 하위질문"을 센다. 자기점검이 전부 실패해도 보고서가
        # "한계 없음"으로 보이는 게 정확히 critic 의 parse_failed 가 막으려던 실패다.
        #
        # 마지막 라운드 값으로 덮어써도 된다(OR 누적이 필요 없다): 판정 불가는
        # verdict="sufficient" 로 떨어지고 should_recheck 는 "insufficient" 일 때만
        # True 이므로, 판정 불가가 난 라운드가 항상 마지막 라운드다.
        subq.parse_failed = verdict.parse_failed
        next_query = _recheck_query(state, subq, verdict, recheck=recheck)
        subq.rounds.append({
            "round": round_no, "query": query, "found_chunks": len(hits),
            "new_papers": new_papers, "verdict": verdict.verdict,
            "note": verdict.note, "next_query": next_query,
        })
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
            "round": round_no, "next_query": next_query,
            "will_recheck": next_query is not None,
        })

        if next_query is None:
            break
        query = next_query
        recheck += 1

    return subq
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_runner.py app/tests/test_research_state.py -q`
Expected: `89 passed`
전체 회귀: **680 passed**. 기존 재검색 테스트(`TestRequery`·`TestEvidenceCap`·`TestEvidenceOrder`)가 그대로 통과해야 한다 — `_recheck_query` 가 기존 세 break 조건과 같은 순서로 판정하는지의 확인이다.

- [ ] **Step 5: 커밋**

```bash
git add app/services/research/runner.py app/tests/test_research_runner.py
git commit -m "[Feat] round04b — 딥리서치 러너가 회차·새 논문·다음 검색어·카운터를 이벤트로 흘리고 회차 이력을 남긴다"
```

---

### Task 7: 종합 — 절 진행 콜백과 보고서 통계

`synthesize(state, *, should_stop=None, on_section=None)` — 절마다 시작(`running`)·끝(`done`/`failed`)을 async 콜백으로 알린다. 보고서 JSON 에 `stats` 키를 **추가만** 한다(기존 키 무변경).

**Files:**
- Modify: `app/services/research/synthesizer.py` (import L28, `SynthesisCanceled` L45-46 주변, `assemble_report` 반환 L246-251, `synthesize` L389-415)
- Test: `app/tests/test_research_synthesizer.py` (파일 끝에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_research_synthesizer.py` 끝에 추가한다. `TestSynthesize._patch_chat` 은 self 를 쓰지 않으므로 인스턴스를 만들어 재사용한다.

```python


class TestSectionProgress:
    """절 진행을 콜백으로 알린다 — 워커가 synth 이벤트로 흘리고 종합 단계 result 에도 남긴다."""

    def _record(self):
        seen: list[tuple[int, int, str]] = []

        async def on_section(idx, total, status):
            seen.append((idx, total, status))

        return seen, on_section

    def test_each_section_reports_start_and_end(self, monkeypatch):
        reply = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [reply, reply])
        seen, on_section = self._record()
        asyncio.run(synthesize(_state_three(), on_section=on_section))
        # 근거 없는 하위3 은 절이 되지 않는다 — total 은 실제로 쓰는 절 수이고 idx 는 절 순번이다
        assert seen == [(0, 2, "running"), (0, 2, "done"), (1, 2, "running"), (1, 2, "done")]

    def test_section_without_narrative_reports_failed(self, monkeypatch):
        good = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [good, _timeout(), _timeout()])
        seen, on_section = self._record()
        asyncio.run(synthesize(_state_three(), on_section=on_section))
        assert seen[-1] == (1, 2, "failed")

    def test_canceled_section_is_never_reported_finished(self, monkeypatch):
        # 끝났다고 알리지 않는다 — 워커가 종합 단계를 failed 로 닫는다
        TestSynthesize()._patch_chat(monkeypatch, [])
        seen, on_section = self._record()

        async def stop():
            return True

        with pytest.raises(SynthesisCanceled):
            asyncio.run(synthesize(_state_three(), should_stop=stop, on_section=on_section))
        assert seen == [(0, 2, "running")]


class TestReportStats:
    """보고서 서론 한 줄("논문 N편을 검토하고 M편을 근거로")의 원천."""

    def test_report_carries_research_stats(self):
        st = _state()
        st.seen_cnts = {"A", "B", "C"}
        st.subquestions[0].queries = ["q1", "q2"]
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert report["stats"] == {"papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 1}

    def test_existing_keys_are_kept(self):
        # 키 추가만 한다 — 옛 보고서를 그리는 화면과 교본이 기존 키에 기대고 있다
        report = assemble_report(_state(), sections=[], unmarked_total=0)
        assert set(report) == {
            "question", "range", "sections", "evidence", "trail", "limitations", "stats",
        }
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_synthesizer.py -q`
Expected: `5 failed, 73 passed` — `TypeError: synthesize() got an unexpected keyword argument 'on_section'`, `KeyError: 'stats'`, `Extra items in the right set: 'stats'`

- [ ] **Step 3: 최소 구현**

`app/services/research/synthesizer.py` import.

교체 전:
```python
from services.research.state import Chunk, Evidence, ResearchState, SubQuestion
```
교체 후:
```python
from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, research_stats,
)
```

`SynthesisCanceled` 정의 주변.

교체 전:
```python
class SynthesisCanceled(Exception):
    """취소가 확인돼 종합을 멈췄다 — 실패가 아니라 사용자의 결정이다."""
```
교체 후:
```python
SectionFn = Callable[[int, int, str], Awaitable[None]]


class SynthesisCanceled(Exception):
    """취소가 확인돼 종합을 멈췄다 — 실패가 아니라 사용자의 결정이다."""


async def _no_progress(idx: int, total: int, status: str) -> None:
    return None
```

`assemble_report` 반환 dict 끝.

교체 전:
```python
        "limitations": build_limitations(
            state, unmarked_total=unmarked, dropped_total=dropped,
            failed_sections=failed_sections, unsummarized_total=unsummarized,
            unparsed_total=unparsed, introless_sections=introless,
        ),
    }
```
교체 후:
```python
        "limitations": build_limitations(
            state, unmarked_total=unmarked, dropped_total=dropped,
            failed_sections=failed_sections, unsummarized_total=unsummarized,
            unparsed_total=unparsed, introless_sections=introless,
        ),
        "stats": research_stats(state),
    }
```

`synthesize` 시그니처.

교체 전:
```python
async def synthesize(
    state: ResearchState, *, should_stop: Callable[[], Awaitable[bool]] | None = None,
) -> dict:
```
교체 후:
```python
async def synthesize(
    state: ResearchState, *, should_stop: Callable[[], Awaitable[bool]] | None = None,
    on_section: SectionFn | None = None,
) -> dict:
```

`synthesize` docstring 끝과 절 루프.

교체 전:
```python
    should_stop 은 LLM 을 부르기 직전마다 확인하고, True 면 SynthesisCanceled 를
    던진다 — 취소 뒤에도 남은 절을 다 부르면 GPU 를 비운다는 취소의 약속이 거짓이 된다.
    """
    targets = [sq for sq in state.subquestions if sq.evidence_ids]
    sections = []
    for sq in targets:
        section = await _synthesize_section(state, sq, should_stop=should_stop)
        sections.append(section)
        log.info("[research] 절 종합 job=%s idx=%s 논문=%d ok=%s",
                 state.job_id, sq.idx, len(section["papers"]), not section["failed"])
```
교체 후:
```python
    should_stop 은 LLM 을 부르기 직전마다 확인하고, True 면 SynthesisCanceled 를
    던진다 — 취소 뒤에도 남은 절을 다 부르면 GPU 를 비운다는 취소의 약속이 거짓이 된다.

    on_section(idx, total, status) 는 절을 쓰기 시작할 때 "running", 끝낼 때 "done"
    또는 "failed" 로 부른다. idx 는 절 순번(0부터)이지 하위질문 번호가 아니다 — 근거
    없는 하위질문은 절이 되지 않아 둘이 어긋나고, 화면의 "2/3" 은 절 순번으로 센다.
    """
    on_section = on_section or _no_progress
    targets = [sq for sq in state.subquestions if sq.evidence_ids]
    sections = []
    for i, sq in enumerate(targets):
        await on_section(i, len(targets), "running")
        section = await _synthesize_section(state, sq, should_stop=should_stop)
        sections.append(section)
        log.info("[research] 절 종합 job=%s idx=%s 논문=%d ok=%s",
                 state.job_id, sq.idx, len(section["papers"]), not section["failed"])
        await on_section(i, len(targets), "failed" if section["failed"] else "done")
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_synthesizer.py -q`
Expected: `78 passed`
전체 회귀: **685 passed**.

- [ ] **Step 5: 커밋**

```bash
git add app/services/research/synthesizer.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04b — 딥리서치 종합이 절 진행을 콜백으로 알리고 보고서에 검토 통계를 싣는다"
```

---

### Task 8: 워커 — step·status 이벤트

`_step` 이 id 대신 값 객체 `_StepRef` 를 돌려주고, 열 때(`running`)와 닫을 때(`_finish`, 저장한 result 그대로) `step` 이벤트를 낸다. 계획·실행 태스크의 **성공한** 상태 전이마다 `status` 이벤트를 낸다(계획 태스크 이벤트 0건 해소). 종료 상태는 기존 `publish_terminal` 이 알린다.

**Files:**
- Modify: `app/workers/research_tasks.py` (import L15, `_step`·`_finish` L115-143 교체 + `_announce` 추가, `_plan_deep_research` L312-332, `_run_deep_research` L362-366·L392-416·L424-426·L432-448 의 `step_id` → `step`)
- Test: `app/tests/test_research_tasks.py` (`class TestReaper:` L839 바로 위에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

`class TestReaper:` 바로 위에 추가한다. 파이프라인 하네스(`_patch_pipeline`)는 `_step`·`_finish` 를 대역으로 바꾸므로 step 이벤트는 두 함수를 직접 불러 검증하고, status 이벤트는 하네스가 잡는 `publish` 기록으로 검증한다.

```python
class _RecordingSession(_FakeSession):
    """실행한 문장 객체를 남긴다 — UPDATE 에 실제로 실은 값을 읽기 위해서다."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.stmts: list = []

    async def execute(self, stmt, params=None):
        self.stmts.append(stmt)
        return await super().execute(stmt, params)


def _update_values(stmt) -> dict:
    return {getattr(k, "key", k): (v.value if isinstance(v, BindParameter) else v)
            for k, v in stmt._values.items()}


class TestStepEvents:
    """단계가 열리고 닫힐 때 화면에 알린다. 닫을 때는 저장한 result 를 그대로 싣는다 —
    라이브로 본 장면과 끝난 뒤 다시 연 장면이 같아야 한다."""

    def _capture(self, monkeypatch, rt) -> list[tuple]:
        events: list[tuple] = []

        async def _publish(job_id, kind, payload):
            events.append((job_id, kind, payload))

        monkeypatch.setattr(rt, "publish", _publish)
        return events

    def test_opening_a_step_announces_it_running(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        jid = uuid.uuid4()

        step = asyncio.run(rt._step(_FakeSession(scalar=41), jid, 4, "search", "하위1",
                                    subq_idx=0, detail="검색 중"))

        assert step.id == 41
        assert events == [(jid, "step", {
            "seq": 4, "step_kind": "search", "subq_idx": 0, "title": "하위1",
            "detail": "검색 중", "status": "running",
        })]

    def test_step_is_announced_after_its_row_is_committed(self, monkeypatch):
        # 커밋 전에 알리면 그 틈에 재접속한 화면은 스냅샷에 없는 단계를 이벤트로만 받는다
        rt = _load_tasks(monkeypatch)
        db = _FakeSession(scalar=41)
        commits_at_publish = []

        async def _publish(job_id, kind, payload):
            commits_at_publish.append(db.commits)

        monkeypatch.setattr(rt, "publish", _publish)
        asyncio.run(rt._step(db, uuid.uuid4(), 0, "plan", "연구 계획 수립"))

        assert commits_at_publish == [1]

    def test_closing_a_step_streams_the_result_it_saved(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        jid = uuid.uuid4()
        db = _RecordingSession(scalar=41)
        step = asyncio.run(rt._step(db, jid, 4, "search", "하위1", subq_idx=0))
        result = {"queries": ["q1"], "rounds": [{"round": 1, "query": "q1"}]}

        asyncio.run(rt._finish(db, step, "done", result))

        saved = _update_values(db.stmts[-1])
        assert saved["status"] == "done" and saved["result"] == result
        assert events[-1] == (jid, "step", {
            "seq": 4, "step_kind": "search", "subq_idx": 0, "title": "하위1",
            "detail": None, "status": "done", "result": result,
        })

    def test_closing_without_result_streams_an_empty_result(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        db = _FakeSession(scalar=7)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 0, "synthesize", "보고서 종합"))

        asyncio.run(rt._finish(db, step, "failed"))

        assert events[-1][2]["status"] == "failed" and events[-1][2]["result"] == {}

    def test_unknown_step_kind_is_not_announced(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        with pytest.raises(AssertionError):
            asyncio.run(rt._step(_FakeSession(scalar=1), uuid.uuid4(), 0, "critique", "점검"))
        assert events == []


def _statuses(h: _Harness) -> list[dict]:
    return [e[1] for e in h.events if e[0] == "status"]


class TestStatusEvents:
    """상태·단계가 바뀔 때마다 알린다 — 스트림에 붙은 화면이 폴링 없이 따라온다.
    종료 상태는 기존 종료 프레임이 알리므로 status 로 따로 내지 않는다."""

    def test_run_announces_exploring_then_synthesizing(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert _statuses(h) == [
            {"status": "running", "stage": "planned"},
            {"status": "running", "stage": "explored"},
        ]
        assert h.events[-1] == ("terminal", "completed", None)

    def test_resumed_run_goes_straight_to_synthesis(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert _statuses(h) == [{"status": "running", "stage": "explored"}]

    def test_checkpoint_lost_to_cancel_is_not_announced(self, monkeypatch):
        # 취소에 진 전이를 알리면 화면이 취소된 잡을 "종합 중"으로 그린다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _cancel(state, subq):
            job.status = "canceled"

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_cancel)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert _statuses(h) == [{"status": "running", "stage": "planned"}]
        assert _terminals(h) == [("canceled", None)]

    def test_skipped_redelivery_announces_nothing(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"], status="running")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.events == []

    def test_plan_announces_planning_then_awaiting_approval(self, monkeypatch):
        """계획 단계에 붙은 스트림은 이 이벤트가 없으면 계획이 끝난 것을 모른다."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            return ["하위1", "하위2"]

        h = TestPlan()._patch(monkeypatch, rt, job, _plan)
        asyncio.run(rt._plan_deep_research(str(job.id)))

        assert _statuses(h) == [
            {"status": "planning", "stage": "created"},
            {"status": "awaiting_approval", "stage": "planned"},
        ]

    def test_failed_plan_announces_only_planning(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="created", plan=None, status="created")

        async def _plan(question, params):
            raise ValueError("계획을 해석하지 못했다")

        h = TestPlan()._patch(monkeypatch, rt, job, _plan)
        asyncio.run(rt._plan_deep_research(str(job.id)))

        assert _statuses(h) == [{"status": "planning", "stage": "created"}]
        assert [t[0] for t in _terminals(h)] == ["failed"]
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_tasks.py -q`
Expected: `9 failed, 45 passed` — `TestStepEvents` 4건(`AttributeError: 'int' object has no attribute 'id'`, `assert [] == [1]`, `IndexError: list index out of range`), `TestStatusEvents` 5건(`assert [] == [{'status': 'running', ...}]`). `test_unknown_step_kind_is_not_announced`·`test_skipped_redelivery_announces_nothing` 은 지금도 통과하는 가드 테스트다.

- [ ] **Step 3: 최소 구현**

`app/workers/research_tasks.py` import.

교체 전:
```python
import uuid
from collections.abc import Awaitable, Callable
```
교체 후:
```python
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
```

`_step`·`_finish` 두 함수(L115-143)를 아래로 교체한다(`_StepRef`·`_announce` 추가).

```python
@dataclass(frozen=True)
class _StepRef:
    """열린 step 의 id 와, 닫을 때 화면에 다시 알릴 머리 정보.

    ORM 객체를 들고 다니지 않는 이유: 예외 핸들러는 rollback 부터 하는데, rollback 은
    세션의 모든 인스턴스를 만료시켜 그 뒤 속성 접근이 async 세션에서 MissingGreenlet
    으로 터진다. 평범한 값 객체는 rollback 과 무관하다.
    """
    id: int
    job_id: uuid.UUID
    seq: int
    kind: str
    title: str
    subq_idx: int | None
    detail: str | None

    def event(self, status: str, result: dict | None = None) -> dict:
        # 이벤트 자체의 kind 와 겹치지 않게 step_kind 로 싣는다
        payload = {
            "seq": self.seq, "step_kind": self.kind, "subq_idx": self.subq_idx,
            "title": self.title, "detail": self.detail, "status": status,
        }
        if result is not None:
            payload["result"] = result
        return payload


async def _step(
    db: AsyncSession, job_id: uuid.UUID, seq: int, kind: str, title: str, *,
    subq_idx: int | None = None, detail: str | None = None,
) -> _StepRef:
    # STEP_KINDS 를 실제로 강제하는 유일한 지점. 상수만 정의하고 아무 데서도
    # 쓰지 않으면 장식이 되고, 오타난 kind 가 프론트 분기를 조용히 빗나간다.
    assert kind in STEP_KINDS, f"알 수 없는 kind: {kind}"
    step_id = (await db.execute(
        insert(ResearchStep).values(
            job_id=job_id, seq=seq, kind=kind, title=title,
            subq_idx=subq_idx, detail=detail, status="running",
        ).returning(ResearchStep.id)
    )).scalar_one()
    await db.commit()
    step = _StepRef(step_id, job_id, seq, kind, title, subq_idx, detail)
    # 커밋 뒤에 알린다. 먼저 알리면 그 틈에 재접속한 화면의 스냅샷에는 없는 단계가
    # 이벤트로만 도착한다.
    await publish(job_id, "step", step.event("running"))
    return step


async def _finish(db: AsyncSession, step: _StepRef, status: str, result: dict | None = None) -> None:
    result = result or {}
    await db.execute(
        update(ResearchStep).where(ResearchStep.id == step.id)
        .values(status=status, result=result, finished_at=_now())
    )
    await db.commit()
    # 저장한 result 를 그대로 싣는다 — 라이브로 본 장면과 다시 연 장면이 같아야 한다.
    await publish(step.job_id, "step", step.event(status, result))


async def _announce(job_id: uuid.UUID, status: str, stage: str) -> None:
    """상태 전이를 알린다. 전이가 성공한 뒤에만 부른다 — 취소에 진 전이를 알리면
    화면이 취소된 잡을 진행 중으로 그린다. 종료 상태는 publish_terminal 이 알린다."""
    await publish(job_id, "status", {"status": status, "stage": stage})
```

`_plan_deep_research` 본문(선점 성공 뒤, L312-332).

교체 전:
```python
            job = await db.get(ResearchJob, jid)
            question, params = job.question, merge_params(job.params or {})
            seq = await _next_seq(db, jid)
            await db.commit()      # 읽기 트랜잭션을 닫고 LLM 으로 간다

            step_id = await _step(db, jid, seq, "plan", "연구 계획 수립",
                                  detail="질문을 하위질문으로 분해하는 중입니다")
            try:
                plan = await make_plan(question, params=params)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                await _finish(db, step_id, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e), expect=("planning",))

            await _finish(db, step_id, "done", {"subquestions": plan})
            if not await _transition(db, jid, expect=("planning",), status="awaiting_approval",
                                     plan=plan, stage=_stage("planned")):
                return await _stopped(db, jid)
            return {"job_id": str(jid), "status": "awaiting_approval"}
```
교체 후:
```python
            job = await db.get(ResearchJob, jid)
            question, params, stage = job.question, merge_params(job.params or {}), job.stage
            seq = await _next_seq(db, jid)
            await db.commit()      # 읽기 트랜잭션을 닫고 LLM 으로 간다
            await _announce(jid, "planning", stage)

            step = await _step(db, jid, seq, "plan", "연구 계획 수립",
                               detail="질문을 하위질문으로 분해하는 중입니다")
            try:
                plan = await make_plan(question, params=params)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                log.exception("[research] 계획 수립 실패 job=%s", jid)
                await _finish(db, step, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e), expect=("planning",))

            await _finish(db, step, "done", {"subquestions": plan})
            if not await _transition(db, jid, expect=("planning",), status="awaiting_approval",
                                     plan=plan, stage=_stage("planned")):
                return await _stopped(db, jid)
            await _announce(jid, "awaiting_approval", "planned")
            return {"job_id": str(jid), "status": "awaiting_approval"}
```

`_run_deep_research` — 선점 직후(L362-366).

교체 전:
```python
            seq = await _next_seq(db, jid)
            await db.commit()

            async def _emit(kind: str, payload: dict) -> None:
```
교체 후:
```python
            seq = await _next_seq(db, jid)
            await db.commit()
            await _announce(jid, "running", stage)

            async def _emit(kind: str, payload: dict) -> None:
```

하위질문 루프의 step 변수(L392-416). 세 곳의 `step_id` 를 `step` 으로 바꾼다.

교체 전:
```python
                    step_id = await _step(
                        db, jid, seq, "search", subq.text, subq_idx=subq.idx,
```
교체 후:
```python
                    step = await _step(
                        db, jid, seq, "search", subq.text, subq_idx=subq.idx,
```

교체 전:
```python
                        await _finish(db, step_id, "failed", {"error": str(e)[:500]})
                    else:
                        await _finish(db, step_id, "done", {
```
교체 후:
```python
                        await _finish(db, step, "failed", {"error": str(e)[:500]})
                    else:
                        await _finish(db, step, "done", {
```

체크포인트 전이 직후(L424-426).

교체 전:
```python
                if not await _transition(db, jid, expect=("running",), stage=_stage("explored"),
                                         state_snapshot=snapshot_state(state)):
                    return await _stopped(db, jid)
```
교체 후:
```python
                if not await _transition(db, jid, expect=("running",), stage=_stage("explored"),
                                         state_snapshot=snapshot_state(state)):
                    return await _stopped(db, jid)
                await _announce(jid, "running", "explored")
```

종합 단계(L432-448)의 `step_id` 네 곳.

교체 전:
```python
            step_id = await _step(db, jid, seq, "synthesize", "보고서 종합")
            try:
                report = await synthesize(state, should_stop=lambda: _is_cancelled(db, jid))
            except SynthesisCanceled:
                await _finish(db, step_id, "failed", {"error": "취소됨"})
```
교체 후:
```python
            step = await _step(db, jid, seq, "synthesize", "보고서 종합")
            try:
                report = await synthesize(state, should_stop=lambda: _is_cancelled(db, jid))
            except SynthesisCanceled:
                await _finish(db, step, "failed", {"error": "취소됨"})
```

교체 전:
```python
                await db.rollback()
                await _finish(db, step_id, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e))

            await _finish(db, step_id, "done", {"sections": len(report["sections"])})
```
교체 후:
```python
                await db.rollback()
                await _finish(db, step, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e))

            await _finish(db, step, "done", {"sections": len(report["sections"])})
```

확인: `grep -n "step_id" app/workers/research_tasks.py` 가 `_step` 안의 두 줄(`step_id = (await db.execute(`·`_StepRef(step_id, …`)만 보여야 한다.

- [ ] **Step 4: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_tasks.py -q`
Expected: `54 passed`
전체 회귀: **696 passed**.

- [ ] **Step 5: 커밋**

```bash
git add app/workers/research_tasks.py app/tests/test_research_tasks.py
git commit -m "[Feat] round04b — 딥리서치 워커가 단계 열고 닫기와 상태 전이를 이벤트로 알린다"
```

---

### Task 9: 워커 — 단계 result 에 회차 이력·절 진행 저장

search 단계 result 에 `rounds`(실패해도 그때까지의 회차), synthesize 단계 result 에 `sections_total`·`sections:[{idx, status}]`(실패·취소도 그때까지의 진행)를 남긴다. 절 진행은 `_SynthProgress` 콜백이 `synth` 이벤트로 흘리면서 모은다. `models/research.py` 의 result 모양 주석을 맞춘다.

**Files:**
- Modify: `app/workers/research_tasks.py` (import, `_announce` 위에 `_SynthProgress` 추가, 하위질문 `_finish` 두 곳, 종합 블록)
- Modify: `app/models/research.py` (L98-103 주석만 — 스키마 변경 없음)
- Test: `app/tests/test_research_tasks.py` (`_Harness.__init__` L226-232, `_patch_pipeline` 의 `_synthesize` L272-274, `class TestReaper:` 바로 위에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

하네스가 `on_section` 을 받아 보관하게 한다(종합 대역이 워커가 넘긴 콜백을 부를 수 있게).

`_Harness.__init__`, 교체 전:
```python
        self.events: list[tuple] = []
        self.steps: list[tuple] = []
        self.finished: list[tuple] = []
```
교체 후:
```python
        self.events: list[tuple] = []
        self.steps: list[tuple] = []
        self.finished: list[tuple] = []
        self.on_section = None
```

`_patch_pipeline` 안의 `_synthesize`, 교체 전:
```python
    async def _synthesize(state, *, should_stop=None):
        assert not session.in_txn, "종합(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        synthesized.append(state)
```
교체 후:
```python
    async def _synthesize(state, *, should_stop=None, on_section=None):
        assert not session.in_txn, "종합(LLM) 직전에 읽기 트랜잭션이 열려 있다"
        synthesized.append(state)
        h.on_section = on_section
```

`class TestReaper:` 바로 위에 추가한다. 종합 대역은 `h` 를 클로저로 늦게 묶는다(하네스가 만들어진 뒤 호출되므로 `h.on_section` 이 채워져 있다).

```python
_ROUNDS = [
    {"round": 1, "query": "하위1", "found_chunks": 4, "new_papers": 3,
     "verdict": "insufficient", "note": "부족", "next_query": "보완 검색어"},
    {"round": 2, "query": "보완 검색어", "found_chunks": 2, "new_papers": 1,
     "verdict": "sufficient", "note": "충분", "next_query": None},
]


class TestStepResults:
    """이벤트로 흘린 것은 research_steps.result 에도 남는다 — 끝난 잡을 다시 열어도
    자기점검·종합 진행 장면을 재생할 수 있어야 한다."""

    def test_search_step_result_carries_round_history(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])

        async def _two_rounds(state, subq):
            subq.rounds = [dict(r) for r in _ROUNDS]

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_two_rounds)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.finished[0][2]["rounds"] == _ROUNDS

    def test_failed_search_step_keeps_the_rounds_done_so_far(self, monkeypatch):
        # 실패 화면의 "멈춘 지점"이 여기서 온다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _fails_in_round_two(state, subq):
            if subq.idx == 0:
                subq.rounds = [dict(_ROUNDS[0])]
                raise ConnectionError("재검색 중 끊김")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_fails_in_round_two)
        asyncio.run(rt._run_deep_research(str(job.id)))

        _, status, result, _ = h.finished[0]
        assert status == "failed"
        assert result["rounds"] == [_ROUNDS[0]] and "끊김" in result["error"]

    def test_synthesis_progress_is_streamed_and_saved(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _two_sections(state, should_stop):
            for idx, status in ((0, "running"), (0, "done"), (1, "running"), (1, "failed")):
                await h.on_section(idx, 2, status)
            return {"sections": [{}, {}]}

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_two_sections)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [e[1] for e in h.events if e[0] == "synth"] == [
            {"section_idx": 0, "total": 2, "status": "running"},
            {"section_idx": 0, "total": 2, "status": "done"},
            {"section_idx": 1, "total": 2, "status": "running"},
            {"section_idx": 1, "total": 2, "status": "failed"},
        ]
        _, status, result, _ = h.finished[-1]
        assert status == "done"
        assert result == {"sections_total": 2, "sections": [
            {"idx": 0, "status": "done"}, {"idx": 1, "status": "failed"}]}

    def test_failed_synthesis_keeps_the_sections_done_so_far(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _second_raises(state, should_stop):
            await h.on_section(0, 2, "running")
            await h.on_section(0, 2, "done")
            await h.on_section(1, 2, "running")
            raise ValueError("종합 호출 실패")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_second_raises)
        asyncio.run(rt._run_deep_research(str(job.id)))

        _, status, result, _ = h.finished[-1]
        assert status == "failed"
        assert result == {"error": "종합 호출 실패", "sections_total": 2, "sections": [
            {"idx": 0, "status": "done"}, {"idx": 1, "status": "running"}]}

    def test_canceled_synthesis_keeps_the_sections_done_so_far(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _canceled_after_first(state, should_stop):
            await h.on_section(0, 3, "running")
            await h.on_section(0, 3, "done")
            job.status = "canceled"
            raise rt.SynthesisCanceled()

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_canceled_after_first)
        asyncio.run(rt._run_deep_research(str(job.id)))

        _, status, result, _ = h.finished[-1]
        assert status == "failed"
        assert result == {"error": "취소됨", "sections_total": 3,
                          "sections": [{"idx": 0, "status": "done"}]}

    def test_report_without_sections_saves_zero_total(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[])

        asyncio.run(rt._run_deep_research(str(job.id)))

        assert h.finished[-1][2] == {"sections_total": 0, "sections": []}
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_tasks.py -q`
Expected: `6 failed, 54 passed` — `KeyError: 'rounds'` 2건, synth 이벤트 `assert [] == [...]`, `{'error': "'NoneType' object is not callable"}` (워커가 아직 on_section 을 넘기지 않아 `h.on_section` 이 None) 등

- [ ] **Step 3: 최소 구현**

`app/workers/research_tasks.py` import.

교체 전:
```python
from dataclasses import dataclass
```
교체 후:
```python
from dataclasses import dataclass, field
```

`_announce` 정의 바로 위에 추가한다.

```python
@dataclass
class _SynthProgress:
    """synthesize 의 on_section 콜백. 절 진행을 synth 이벤트로 흘리면서 종합 단계
    result 에 남길 값도 모은다 — 실패·취소로 끝나도 거기까지의 진행이 남는다."""
    job_id: uuid.UUID
    total: int = 0
    statuses: dict[int, str] = field(default_factory=dict)

    async def __call__(self, idx: int, total: int, status: str) -> None:
        self.total = total
        self.statuses[idx] = status
        await publish(self.job_id, "synth", {"section_idx": idx, "total": total, "status": status})

    def result(self, **extra: object) -> dict:
        return {
            **extra, "sections_total": self.total,
            "sections": [{"idx": i, "status": st} for i, st in sorted(self.statuses.items())],
        }
```

하위질문 단계를 닫는 두 곳.

교체 전:
```python
                        await _finish(db, step, "failed", {"error": str(e)[:500]})
                    else:
                        await _finish(db, step, "done", {
                            "queries": subq.queries, "adopted": len(subq.evidence_ids),
                            "verdict": subq.verdict, "note": subq.note,
                            "parse_failed": subq.parse_failed, "capped": subq.capped,
                        })
```
교체 후:
```python
                        await _finish(db, step, "failed",
                                      {"error": str(e)[:500], "rounds": subq.rounds})
                    else:
                        await _finish(db, step, "done", {
                            "queries": subq.queries, "adopted": len(subq.evidence_ids),
                            "verdict": subq.verdict, "note": subq.note,
                            "parse_failed": subq.parse_failed, "capped": subq.capped,
                            "rounds": subq.rounds,
                        })
```

종합 블록.

교체 전:
```python
            step = await _step(db, jid, seq, "synthesize", "보고서 종합")
            try:
                report = await synthesize(state, should_stop=lambda: _is_cancelled(db, jid))
            except SynthesisCanceled:
                await _finish(db, step, "failed", {"error": "취소됨"})
```
교체 후:
```python
            step = await _step(db, jid, seq, "synthesize", "보고서 종합")
            progress = _SynthProgress(jid)
            try:
                report = await synthesize(state, should_stop=lambda: _is_cancelled(db, jid),
                                          on_section=progress)
            except SynthesisCanceled:
                await _finish(db, step, "failed", progress.result(error="취소됨"))
```

교체 전:
```python
                await db.rollback()
                await _finish(db, step, "failed", {"error": str(e)[:500]})
                return await _end_failed(db, jid, str(e))

            await _finish(db, step, "done", {"sections": len(report["sections"])})
```
교체 후:
```python
                await db.rollback()
                await _finish(db, step, "failed", progress.result(error=str(e)[:500]))
                return await _end_failed(db, jid, str(e))

            await _finish(db, step, "done", progress.result())
```

`app/models/research.py` — `ResearchStep.result` 위 주석만 바꾼다(컬럼 정의 무변경 — DB 변경 없음).

교체 전:
```python
    # kind 별 shape — API 가 가공 없이 프론트로 넘기고 프론트가 kind 로 분기한다.
    # plan:       {"subquestions": [...]}                 LLM 원안 (승인본은 job.plan)
    # search:     {"queries": [...], "adopted": n, "verdict": "...", "note": "...",
    #              "parse_failed": bool, "capped": n}   verdict·note 는 마지막 라운드 값
    # synthesize: {"sections": n}
    # 실패 공통:   {"error": "..."}
```
교체 후:
```python
    # kind 별 shape — API 가 가공 없이 프론트로 넘기고 프론트가 kind 로 분기한다.
    # SSE step 이벤트가 같은 값을 싣는다(workers/research_tasks.py _finish).
    # plan:       {"subquestions": [...]}                 LLM 원안 (승인본은 job.plan)
    # search:     {"queries": [...], "adopted": n, "verdict": "...", "note": "...",
    #              "parse_failed": bool, "capped": n,
    #              "rounds": [{"round", "query", "found_chunks", "new_papers",
    #                          "verdict", "note", "next_query"}]}
    #             verdict·note 는 마지막 라운드 값, 회차별 값은 rounds.
    #             rounds 가 없는 행은 보강 전 잡이다 — 화면은 report.trail 로 대체한다.
    # synthesize: {"sections_total": n, "sections": [{"idx": i, "status": "..."}]}
    #             idx 는 절 순번. 보강 전 잡은 {"sections": n}(정수)이다.
    # 실패 공통:   {"error": "..."} — search·synthesize 는 그때까지의 rounds·sections 도 싣는다
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_tasks.py app/tests/test_research_models.py -q`
Expected: `78 passed` (tasks 60 + models 18)
전체 회귀: **702 passed**.

- [ ] **Step 5: 커밋**

```bash
git add app/workers/research_tasks.py app/models/research.py app/tests/test_research_tasks.py
git commit -m "[Feat] round04b — 딥리서치 단계 결과에 회차 이력과 절 진행을 남긴다"
```

---

### Task 10: API — 스냅샷·조회 보강, 승인·재시도 status, 생성자 기록

- 스냅샷에 `steps[].result` 와 `job:{status, stage, plan}` — steps 모양을 `GET` 과 한 함수(`_steps`)로 묶는다.
- `GET /{id}` 에 `params`·`created_at`·`started_at`·`finished_at`. **`created_by` 는 싣지 않는다**(소유 확인이 없는 조회에 남의 브라우저 ID 가 나가면 그걸로 그 사람의 기록 API 를 부를 수 있다).
- 승인·재시도는 전이 성공 직후, **큐에 넣기 전에** `status` 를 낸다. 브로커 실패로 되돌리면 승인은 `status(awaiting_approval)`, 재시도는 종료 프레임 `failed`(옛 오류)로 알린다.
- `POST /api/research` 가 `get_browser_id_optional`(영역 A) 로 `created_by` 를 채운다. 헤더가 없거나 틀려도 잡은 만든다.

**Files:**
- Modify: `app/api/research.py` (import L18-39, `_broker_unavailable` 위 L152, `create_research` L173-188, `approve_plan` L212-219, `retry_research` L251-258, `get_research` L281-296, `stream_research` L304-322)
- Test: `app/tests/test_research_api.py` (import L10-15, `_FakeDB.add_job`·`add` L83-107, `_Api` L150-156, `api` 픽스처 L196-213, `class TestLoaderIsolation:` L506 바로 위에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

import, 교체 전:
```python
import importlib
import json
import sys
import types
import uuid
from types import SimpleNamespace
```
교체 후:
```python
import importlib
import json
import sys
import types
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
```

`_FakeDB.add_job` 의 기본 행(GET 이 시각·생성자를 읽는다), 교체 전:
```python
            "stage": "created", "state_snapshot": None, "last_error": None,
            "finished_at": None,
        }
        row.update(fields)
```
교체 후:
```python
            "stage": "created", "state_snapshot": None, "last_error": None,
            "created_by": None, "created_at": None, "started_at": None, "finished_at": None,
        }
        row.update(fields)
```

`_FakeDB.add`, 교체 전:
```python
            "params": obj.params, "plan": None, "report": None, "stage": "created",
            "state_snapshot": None, "last_error": None, "finished_at": None,
        }
```
교체 후:
```python
            "params": obj.params, "plan": None, "report": None, "stage": "created",
            "state_snapshot": None, "last_error": None, "created_by": obj.created_by,
            "created_at": None, "started_at": None, "finished_at": None,
        }
```

`_Api`, 교체 전:
```python
class _Api:
    def __init__(self, client, db, celery, published, research):
        self.client = client
        self.db = db
        self.celery = celery
        self.published = published
        self.research = research
```
교체 후:
```python
class _Api:
    def __init__(self, client, db, celery, published, research, events):
        self.client = client
        self.db = db
        self.celery = celery
        self.published = published
        self.research = research
        self.events = events

    def announced(self) -> list[tuple[str, dict]]:
        return [(kind, payload) for _, kind, payload in self.events]
```

`api` 픽스처 끝, 교체 전:
```python
    monkeypatch.setattr(research, "publish_terminal", _publish_terminal)

    db = _FakeDB()
    app = FastAPI()
    app.include_router(research.router)
    app.dependency_overrides[get_db] = lambda: db
    return _Api(TestClient(app), db, celery, published, research)
```
교체 후:
```python
    monkeypatch.setattr(research, "publish_terminal", _publish_terminal)

    events: list[tuple] = []

    async def _publish(job_id, kind, payload):
        events.append((job_id, kind, payload))

    monkeypatch.setattr(research, "publish", _publish)

    db = _FakeDB()
    app = FastAPI()
    app.include_router(research.router)
    app.dependency_overrides[get_db] = lambda: db
    return _Api(TestClient(app), db, celery, published, research, events)
```

`class TestLoaderIsolation:` 바로 위에 추가한다. `get_browser_id_optional` 은 대역으로 바꾸지 않는다 — 헤더 해석까지 실제로 거친다.

```python
class TestCreatedBy:
    """잡에 브라우저 ID 를 남긴다(research_jobs.created_by) — 누가 만든 잡인지의 유일한 근거다."""

    def _row(self, api, res) -> dict:
        return api.db.jobs[uuid.UUID(res.json()["job_id"])]

    def test_browser_id_header_fills_created_by(self, api):
        sid = str(uuid.uuid4())
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"},
                              headers={"x-session-id": sid})
        assert res.status_code == 200
        assert self._row(api, res)["created_by"] == sid

    def test_missing_header_still_creates_the_job(self, api):
        # 기록 API 와 달리 필수가 아니다 — 헤더 없는 curl 시연·옛 화면이 그대로 돌아야 한다
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"})
        assert res.status_code == 200
        assert self._row(api, res)["created_by"] is None

    def test_malformed_header_is_ignored(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구"},
                              headers={"x-session-id": "not-a-uuid"})
        assert res.status_code == 200
        assert self._row(api, res)["created_by"] is None


class TestGetFields:
    _T0 = datetime(2026, 9, 26, 1, 2, 3, tzinfo=timezone.utc)

    def test_times_and_params_are_returned(self, api):
        jid = api.db.add_job(status="completed", params={"max_subquestions": 3},
                             created_at=self._T0, started_at=self._T0.replace(minute=3),
                             finished_at=self._T0.replace(minute=9))
        body = api.client.get(f"/api/research/{jid}").json()
        assert body["created_at"] == "2026-09-26T01:02:03+00:00"
        assert body["started_at"] == "2026-09-26T01:03:03+00:00"
        assert body["finished_at"] == "2026-09-26T01:09:03+00:00"
        assert body["params"] == {"max_subquestions": 3}

    def test_times_not_reached_yet_are_null(self, api):
        jid = api.db.add_job(status="created", created_at=self._T0)
        body = api.client.get(f"/api/research/{jid}").json()
        assert body["started_at"] is None and body["finished_at"] is None

    def test_creator_is_not_exposed(self, api):
        """조회에는 소유 확인이 없다 — 링크만 알면 누구나 여는 응답에 남의 브라우저 ID 가
        실리면 그걸 헤더에 넣어 그 사람의 기록을 읽을 수 있다."""
        jid = api.db.add_job(status="completed", created_by=str(uuid.uuid4()))
        assert "created_by" not in api.client.get(f"/api/research/{jid}").json()


_ROUNDS = [{"round": 1, "query": "가", "found_chunks": 4, "new_papers": 3,
            "verdict": "insufficient", "note": "부족", "next_query": "가 보완"}]


def _search_step():
    return SimpleNamespace(seq=1, kind="search", subq_idx=0, title="가", detail="검색 중",
                           status="done", result={"rounds": _ROUNDS})


class TestSnapshot:
    """재접속한 화면은 스냅샷만으로 지금까지의 장면을 복원한다."""

    def test_snapshot_carries_step_results_and_job_state(self, api):
        jid = api.db.add_job(status="completed", stage="synthesized", plan=["가"])
        api.db.steps = [_search_step()]

        snap = _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

        assert snap["job"] == {"status": "completed", "stage": "synthesized", "plan": ["가"]}
        assert snap["steps"][0]["result"] == {"rounds": _ROUNDS}

    def test_snapshot_steps_match_get(self, api):
        # 새로고침한 화면(GET)과 재접속한 화면(스냅샷)이 같은 모양을 받아야 한다
        jid = api.db.add_job(status="completed", stage="synthesized", plan=["가"])
        api.db.steps = [_search_step()]

        snap = _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

        assert snap["steps"] == api.client.get(f"/api/research/{jid}").json()["steps"]


class TestStatusEvents:
    """승인·재시도는 처리 즉시 status 를 발행한다 — 스트림에 붙은 화면이 폴링 없이 따라온다."""

    def test_approve_announces_approved(self, api):
        jid = api.db.add_job(status="awaiting_approval", stage="planned", plan=["가설 A"])
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 200
        assert api.announced() == [("status", {"status": "approved", "stage": "planned"})]

    def test_approve_is_announced_before_the_worker_can_claim(self, api):
        """큐에 넣은 뒤에 알리면 워커가 먼저 낸 running 뒤에 approved 가 도착해
        화면이 한 단계 뒤로 간다."""
        jid = api.db.add_job(status="awaiting_approval", stage="planned", plan=["가설 A"])
        at_send = []
        send = api.celery.send_task

        def _send(name, args=None, **kw):
            at_send.append(api.announced())
            return send(name, args, **kw)

        api.celery.send_task = _send
        api.client.post(f"/api/research/{jid}/approve")

        assert at_send == [[("status", {"status": "approved", "stage": "planned"})]]

    def test_broker_failure_announces_the_reverted_status(self, api):
        jid = api.db.add_job(status="awaiting_approval", stage="planned", plan=["가설 A"])
        api.celery.fail = True

        assert api.client.post(f"/api/research/{jid}/approve").status_code == 503
        assert api.announced() == [
            ("status", {"status": "approved", "stage": "planned"}),
            ("status", {"status": "awaiting_approval", "stage": "planned"}),
        ]

    def test_rejected_approve_announces_nothing(self, api):
        jid = api.db.add_job(status="planning")
        assert api.client.post(f"/api/research/{jid}/approve").status_code == 409
        assert api.events == []

    def test_retry_announces_queued_with_stage(self, api):
        # stage=explored 면 화면이 "종합부터 다시"로 그린다
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패")
        assert api.client.post(f"/api/research/{jid}/retry").status_code == 200
        assert api.announced() == [("status", {"status": "queued", "stage": "explored"})]

    def test_retry_broker_failure_ends_with_the_old_failure(self, api):
        """되돌린 상태는 종료 상태다 — status 가 아니라 종료 프레임으로 알려야 스트림이 닫힌다."""
        jid = api.db.add_job(status="failed", plan=["가"], stage="explored",
                             last_error="종합 실패")
        api.celery.fail = True

        assert api.client.post(f"/api/research/{jid}/retry").status_code == 503
        assert api.announced() == [("status", {"status": "queued", "stage": "explored"})]
        assert api.published == [(jid, "failed", "종합 실패")]
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_api.py -q`
Expected: `2 passed, 56 errors` — 픽스처에서 `AttributeError: <module 'api.research' ...> has no attribute 'publish'`(픽스처를 쓰지 않는 `TestLoaderIsolation` 2건만 통과). 영역 A 의 `core/deps.py` 가 아직 없으면 그보다 먼저 `ImportError: cannot import name 'get_browser_id_optional'` 이 난다 — 이 Task 는 Task 2 뒤에 돈다.

- [ ] **Step 3: 최소 구현**

`app/api/research.py` import 세 곳.

교체 전:
```python
from collections.abc import AsyncIterator
from typing import Annotated
```
교체 후:
```python
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated
```

교체 전:
```python
from core.deps import get_db
```
교체 후:
```python
from core.deps import get_browser_id_optional, get_db
```

교체 전:
```python
from services.research.relay import TERMINAL_KIND, publish_terminal, subscribe, terminal_event
```
교체 후:
```python
from services.research.relay import (
    TERMINAL_KIND, publish, publish_terminal, subscribe, terminal_event,
)
```

`_broker_unavailable` 바로 위에 추가한다.

```python
async def _announce(jid: uuid.UUID, status: str, stage: str) -> None:
    """상태 전이를 스트림에 알린다. 전이가 성공한 뒤에만 부른다. 종료 상태는
    publish_terminal 이 알린다 — status 로 내면 스트림이 닫히지 않는다."""
    await publish(jid, "status", {"status": status, "stage": stage})
```

`create_research`, 교체 전:
```python
@router.post("")
async def create_research(req: ResearchCreate, db: AsyncSession = Depends(get_db)):
    try:
        params = merge_params(req.params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    job = ResearchJob(id=uuid.uuid4(), question=req.question, params=params)
```
교체 후:
```python
@router.post("")
async def create_research(
    req: ResearchCreate, db: AsyncSession = Depends(get_db),
    browser_id: uuid.UUID | None = Depends(get_browser_id_optional),
):
    try:
        params = merge_params(req.params)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 헤더가 없거나 틀려도 잡은 만든다 — 기록 API 와 달리 헤더 없는 curl 시연과
    # 옛 화면이 그대로 돌아야 한다.
    job = ResearchJob(id=uuid.uuid4(), question=req.question, params=params,
                      created_by=str(browser_id) if browser_id else None)
```

`approve_plan` 전이 뒤, 교체 전:
```python
    if not await _to_run_queue(db, jid, expect=("awaiting_approval",),
                               status=STATUS_APPROVED, plan=plan):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_APPROVED,),
                          status="awaiting_approval", plan=old_plan)
        raise _broker_unavailable()
```
교체 후:
```python
    if not await _to_run_queue(db, jid, expect=("awaiting_approval",),
                               status=STATUS_APPROVED, plan=plan):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

    # 큐에 넣기 전에 알린다. 넣은 뒤에 알리면 워커가 먼저 집어 낸 running 뒤에
    # approved 가 도착해 화면이 한 단계 뒤로 간다.
    await _announce(jid, STATUS_APPROVED, job.stage)
    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_APPROVED,),
                          status="awaiting_approval", plan=old_plan)
        await _announce(jid, "awaiting_approval", job.stage)
        raise _broker_unavailable()
```

`retry_research` 전이 뒤, 교체 전:
```python
    if not await _to_run_queue(db, jid, expect=("failed",), status=STATUS_QUEUED,
                               last_error=None, finished_at=None):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_QUEUED,), status="failed",
                          last_error=old_error, finished_at=old_finished)
        raise _broker_unavailable()
```
교체 후:
```python
    if not await _to_run_queue(db, jid, expect=("failed",), status=STATUS_QUEUED,
                               last_error=None, finished_at=None):
        raise HTTPException(status_code=409, detail="그 사이 잡 상태가 바뀌었다")

    # 큐에 넣기 전에 알리는 이유는 approve 와 같다
    await _announce(jid, STATUS_QUEUED, job.stage)
    if not _enqueue("tasks.run_deep_research", jid):
        await _transition(db, jid, expect=(STATUS_QUEUED,), status="failed",
                          last_error=old_error, finished_at=old_finished)
        await publish_terminal(jid, "failed", old_error)
        raise _broker_unavailable()
```

`get_research` 전체(L281-296)를 교체한다.

교체 전:
```python
@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, _job_uuid(job_id))
    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    return {
        "job_id": str(job.id), "question": job.question, "status": job.status,
        "stage": job.stage, "plan": job.plan, "report": job.report,
        "last_error": job.last_error,
        "steps": [
            {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "title": s.title,
             "detail": s.detail, "status": s.status, "result": s.result}
            for s in rows
        ],
    }
```
교체 후:
```python
def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


async def _steps(db: AsyncSession, jid: uuid.UUID) -> list[dict]:
    """GET 과 스트림 스냅샷이 같은 모양을 쓴다 — 갈리면 새로고침한 화면과 재접속한
    화면이 같은 잡을 다르게 그린다."""
    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == jid).order_by(ResearchStep.seq)
    )).scalars().all()
    return [
        {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx, "title": s.title,
         "detail": s.detail, "status": s.status, "result": s.result}
        for s in rows
    ]


@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await _get_job(db, _job_uuid(job_id))
    # created_by 는 싣지 않는다. 이 조회에는 소유 확인이 없어 링크만 알면 누구나 여는데,
    # 남의 브라우저 ID 가 나가면 그걸 헤더에 넣어 그 사람의 기록을 읽을 수 있다.
    return {
        "job_id": str(job.id), "question": job.question, "status": job.status,
        "stage": job.stage, "plan": job.plan, "report": job.report,
        "last_error": job.last_error, "params": job.params,
        "created_at": _iso(job.created_at), "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
        "steps": await _steps(db, job.id),
    }
```

`stream_research` 앞부분, 교체 전:
```python
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)

    rows = (await db.execute(
        select(ResearchStep).where(ResearchStep.job_id == job.id).order_by(ResearchStep.seq)
    )).scalars().all()
    snapshot = [
        {"seq": s.seq, "kind": s.kind, "subq_idx": s.subq_idx,
         "title": s.title, "detail": s.detail, "status": s.status}
        for s in rows
    ]
    # 제너레이터는 요청 세션이 닫힌 뒤에 돈다 — ORM 객체를 들고 가지 않고
    # 필요한 값만 미리 꺼내 둔다.
    job_status, job_error = job.status, job.last_error

    async def _gen() -> AsyncIterator[str]:
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield _sse({"kind": "snapshot", "steps": snapshot})
```
교체 후:
```python
    jid = _job_uuid(job_id)
    job = await _get_job(db, jid)

    # 제너레이터는 요청 세션이 닫힌 뒤에 돈다 — ORM 객체를 들고 가지 않고
    # 필요한 값만 미리 꺼내 둔다.
    snapshot = {
        "kind": "snapshot", "steps": await _steps(db, job.id),
        "job": {"status": job.status, "stage": job.stage, "plan": job.plan},
    }
    job_status, job_error = job.status, job.last_error

    async def _gen() -> AsyncIterator[str]:
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield _sse(snapshot)
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_api.py -q`
Expected: `58 passed`
전체 회귀: **716 passed**.

- [ ] **Step 5: 커밋**

```bash
git add app/api/research.py app/tests/test_research_api.py
git commit -m "[Feat] round04b — 딥리서치 스냅샷·조회 보강, 승인·재시도 상태 알림, 잡 생성자 기록"
```

---

### Task 11: API — 하트비트가 놓친 status 를 되살린다

스트림은 스냅샷을 DB 에서 읽은 **뒤에** 구독을 붙인다(round04a 의 `stream_research` 순서 — 스냅샷 조회 뒤 구독). 그 틈에 나간 이벤트는 중계되지 않는다. 계획은 1초 안팎이라 `awaiting_approval` 이 이 틈에 빠지기 쉽고, 빠지면 화면은 승인 대기를 영영 모른다(대기 중엔 이벤트가 없다). 이미 15초마다 도는 하트비트의 DB 조회를 `(status, stage, last_error)` 로 넓혀, 마지막으로 보낸 상태와 다르면 `status` 를 한 번 낸다. 추가 조회 비용은 없다(같은 한 줄 조회).

**Files:**
- Modify: `app/api/research.py` (`stream_research` 의 `_gen`, `_terminal_status` → `_job_status`)
- Test: `app/tests/test_research_api.py` (`TestStream.test_heartbeat_detects_termination_with_same_shape` L490-503 수정, 그 뒤에 `TestHeartbeatStatus` 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

`test_heartbeat_detects_termination_with_same_shape` 를 새 조회 함수 이름·모양으로 바꾸고, 바로 뒤에 클래스를 추가한다.

교체 전:
```python
    def test_heartbeat_detects_termination_with_same_shape(self, api, monkeypatch):
        jid = api.db.add_job(status="running")

        async def _subscribe(job_id):
            yield None

        async def _terminal_status(job_uuid):
            return "canceled", None

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        monkeypatch.setattr(api.research, "_terminal_status", _terminal_status)
        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)

        assert frames[-1] == {"kind": "canceled", "status": "canceled"}
```
교체 후:
```python
    def test_heartbeat_detects_termination_with_same_shape(self, api, monkeypatch):
        jid = api.db.add_job(status="running")

        async def _subscribe(job_id):
            yield None

        async def _job_status(job_uuid):
            return "canceled", "planned", None

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        monkeypatch.setattr(api.research, "_job_status", _job_status)
        frames = _frames(api.client.get(f"/api/research/{jid}/stream").text)

        assert frames[-1] == {"kind": "canceled", "status": "canceled"}


class TestHeartbeatStatus:
    """스냅샷을 읽은 뒤 구독이 붙기 전에 나간 status 는 중계되지 않는다. 계획은 1초 안에
    끝나므로 그 틈에 빠진 화면은 승인 대기를 영영 모른다 — 하트비트가 DB 와 맞춘다."""

    def _stream(self, api, monkeypatch, *, live, db_status):
        jid = api.db.add_job(status="planning", stage="created")

        async def _subscribe(job_id):
            for event in live:
                yield event

        async def _job_status(job_uuid):
            return db_status

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        monkeypatch.setattr(api.research, "_job_status", _job_status)
        return _frames(api.client.get(f"/api/research/{jid}/stream").text)

    def test_missed_status_change_is_recovered_once(self, api, monkeypatch):
        frames = self._stream(
            api, monkeypatch,
            live=[None, None, {"kind": "canceled", "status": "canceled"}],
            db_status=("awaiting_approval", "planned", None),
        )
        assert [f["kind"] for f in frames] == ["snapshot", "status", "canceled"]
        assert frames[1] == {"kind": "status", "status": "awaiting_approval", "stage": "planned"}

    def test_unchanged_status_stays_quiet(self, api, monkeypatch):
        frames = self._stream(
            api, monkeypatch,
            live=[None, {"kind": "canceled", "status": "canceled"}],
            db_status=("planning", "created", None),
        )
        assert [f["kind"] for f in frames] == ["snapshot", "canceled"]

    def test_relayed_status_is_not_repeated(self, api, monkeypatch):
        frames = self._stream(
            api, monkeypatch,
            live=[{"kind": "status", "status": "awaiting_approval", "stage": "planned"},
                  None, {"kind": "canceled", "status": "canceled"}],
            db_status=("awaiting_approval", "planned", None),
        )
        assert [f["kind"] for f in frames] == ["snapshot", "status", "canceled"]
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_api.py -q`
Expected: `4 failed, 57 passed` — `AttributeError: <module 'api.research' ...> has no attribute '_job_status'`

- [ ] **Step 3: 최소 구현**

`stream_research` 의 값 꺼내기와 `_gen` 본문, 교체 전:
```python
    job_status, job_error = job.status, job.last_error

    async def _gen() -> AsyncIterator[str]:
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield _sse(snapshot)
        if job_status in TERMINAL_STATUSES:
            # 끝난 잡에 붙었다면 중계할 것이 없다. 구독하면 영원히 기다린다.
            yield _sse(terminal_event(job_status, job_error))
            return
        async for event in subscribe(str(jid)):
            if event is None:
                # 하트비트. 끊긴 소켓은 여기서 드러난다. 그리고 종료 이벤트를
                # 놓친 채 붙어 있는 경우(회수기가 끝낸 잡 등)를 대비해 상태를 확인한다.
                yield ": ping\n\n"
                ended = await _terminal_status(jid)
                if ended is not None:
                    yield _sse(terminal_event(*ended))
                    return
                continue
            yield _sse(event)
            if event.get("kind") in TERMINAL_KINDS:
                return
```
교체 후:
```python
    job_status, job_stage, job_error = job.status, job.stage, job.last_error

    async def _gen() -> AsyncIterator[str]:
        # 재접속 복원 — 뼈대를 먼저 보내고 그 뒤를 중계한다
        yield _sse(snapshot)
        if job_status in TERMINAL_STATUSES:
            # 끝난 잡에 붙었다면 중계할 것이 없다. 구독하면 영원히 기다린다.
            yield _sse(terminal_event(job_status, job_error))
            return
        last = (job_status, job_stage)
        async for event in subscribe(str(jid)):
            if event is None:
                # 하트비트. 끊긴 소켓은 여기서 드러난다. 그리고 DB 와 맞춰 본다 —
                # 종료 이벤트를 놓친 채 붙어 있는 경우(회수기가 끝낸 잡 등)와, 스냅샷을
                # 읽은 뒤 구독이 붙기 전에 나간 status 를 놓친 경우(계획이 그 틈에
                # 끝나면 화면이 승인 대기를 영영 모른다)를 여기서 되살린다.
                yield ": ping\n\n"
                current = await _job_status(jid)
                if current is None:
                    continue
                status, stage, error = current
                if status in TERMINAL_STATUSES:
                    yield _sse(terminal_event(status, error))
                    return
                if (status, stage) != last:
                    last = (status, stage)
                    yield _sse({"kind": "status", "status": status, "stage": stage})
                continue
            if event.get("kind") == "status":
                last = (event.get("status"), event.get("stage"))
            yield _sse(event)
            if event.get("kind") in TERMINAL_KINDS:
                return
```

파일 끝 `_terminal_status` 를 `_job_status` 로 바꾼다. docstring 둘째 문단(FastAPI yield 의존성·풀링 엔진 설명)은 그대로 둔다.

교체 전:
```python
async def _terminal_status(jid: uuid.UUID) -> tuple[str, str | None] | None:
    """끝난 잡이면 (status, last_error). 하트비트마다 짧은 세션을 새로 연다 —
    Depends(get_db) 세션을 쓰지 않는다.
```
교체 후:
```python
async def _job_status(jid: uuid.UUID) -> tuple[str, str, str | None] | None:
    """(status, stage, last_error). 하트비트마다 짧은 세션을 새로 연다 —
    Depends(get_db) 세션을 쓰지 않는다.
```

교체 전:
```python
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(ResearchJob.status, ResearchJob.last_error).where(ResearchJob.id == jid)
        )).first()
    if row is None or row[0] not in TERMINAL_STATUSES:
        return None
    return row[0], row[1]
```
교체 후:
```python
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(ResearchJob.status, ResearchJob.stage, ResearchJob.last_error)
            .where(ResearchJob.id == jid)
        )).first()
    return None if row is None else (row[0], row[1], row[2])
```

확인: `grep -n "_terminal_status" app/` 결과 0건.

- [ ] **Step 4: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_api.py -q`
Expected: `61 passed`
전체 회귀(공통 명령): **719 passed**(Task 10 뒤 716 + 3).

- [ ] **Step 5: 커밋**

```bash
git add app/api/research.py app/tests/test_research_api.py
git commit -m "[Feat] round04b — 딥리서치 스트림 하트비트가 놓친 상태 전이를 되살린다"
```

---

### Task 12: 진행 중 단계 결과 갱신 — 탐색·종합 중 재접속 복원

Task 8·9 는 단계를 **닫을 때만** result 를 쓴다. 그러면 탐색 중에 새로 연 화면·재접속한 화면은 스냅샷에서 지금 도는 하위질문의 앞 회차와 자기점검 강조 카드를 잃고, `counters` 이벤트는 저장되지 않아 카운터가 다음 회차까지 빈칸이다(spec §6-2 "연결이 끊기면 snapshot 으로 복원한다"). 기존 JSONB 칸만 쓴다 — DB 변경 없음.

- 자기점검(회차의 끝)마다 도는 search 단계 result 를 `{rounds, counters}` 로 덮어쓰고 `step`(status `running` + result)을 낸다. 끝난 search 단계 result 에도 `counters` 를 남긴다 — 다음 하위질문의 첫 회차 전까지 재접속한 화면의 카운터 원천이다.
- 절 진행이 바뀔 때마다 도는 synthesize 단계 result 를 `{sections_total, sections}` 로 덮어쓰고 `step` 을 낸다.
- 진행 기록이 실패해도 탐색·종합은 계속한다(롤백하고 경고 로그). 소프트 리밋은 삼키지 않는다.
- 스트림 스냅샷 `job` 에 `counters` — 끝난 잡은 `report.stats`, 도는 잡은 단계 result 에 마지막으로 남은 `counters`. 둘 다 없으면 키를 싣지 않는다(화면 리듀서는 키가 있을 때만 쓴다 — Task 28).

**Files:**
- Modify: `app/workers/research_tasks.py` (import, `_finish` 와 `_SynthProgress` 사이에 `_save_progress`·`_search_progress`·`_round_emitter` 추가, `_SynthProgress`, `_run_deep_research` 의 `_emit`·`explore_subquestion` 호출·하위질문 `_finish` 두 곳·`_SynthProgress(...)` 생성)
- Modify: `app/api/research.py` (`get_research` 바로 위에 `_live_counters`, `stream_research` 의 스냅샷 조립)
- Modify: `app/models/research.py` (`ResearchStep.result` 모양 주석만 — 스키마 변경 없음)
- Test: `app/tests/test_research_tasks.py` (`_Harness.__init__`, `_patch_pipeline` 의 `_explore`·`_synthesize` 앞·패치 목록, `class TestReaper:` 바로 위에 추가)
- Test: `app/tests/test_research_api.py` (`class TestStatusEvents:` 바로 위에 추가)

- [ ] **Step 1: 실패하는 테스트 작성**

파이프라인 하네스가 러너에 넘어간 `emit` 을 보관하고(`h.emit`), 진행 기록을 대역으로 받아 남기게(`h.progress`) 넓힌다. Task 9 의 종합 테스트가 `h.on_section` 을 부를 때 진짜 DB 쓰기로 가지 않게 하는 역할도 한다.

`_Harness.__init__`, 교체 전:
```python
        self.finished: list[tuple] = []
        self.on_section = None
```
교체 후:
```python
        self.finished: list[tuple] = []
        self.on_section = None
        self.emit = None
        self.progress: list[tuple] = []
```

`_patch_pipeline` 안의 `_explore`, 교체 전:
```python
        explored.append(subq.text)
        if explore is not None:
            await explore(state, subq)
        return subq
```
교체 후:
```python
        explored.append(subq.text)
        h.emit = emit
        if explore is not None:
            await explore(state, subq)
        return subq
```

`_patch_pipeline` 안의 `_synthesize` 정의 바로 앞에 대역을 추가한다. 교체 전:
```python
    async def _synthesize(state, *, should_stop=None, on_section=None):
```
교체 후:
```python
    async def _save_progress(db, step, result):
        h.progress.append((step, result))

    async def _synthesize(state, *, should_stop=None, on_section=None):
```

`_patch_pipeline` 의 패치 목록, 교체 전:
```python
        ("explore_subquestion", _explore), ("synthesize", _synthesize),
    ):
```
교체 후:
```python
        ("explore_subquestion", _explore), ("synthesize", _synthesize),
        ("_save_progress", _save_progress),
    ):
```

`class TestReaper:` 바로 위에 추가한다(Task 9 의 `_ROUNDS`·Task 8 의 `_RecordingSession`·`_update_values`·`TestStepEvents._capture` 를 쓴다).

```python
class _FailingUpdateSession(_FakeSession):
    """UPDATE 만 실패한다 — 진행 기록이 깨져도 탐색이 계속되는지 본다."""

    async def execute(self, stmt, params=None):
        if getattr(stmt, "is_update", False):
            raise ConnectionError("DB 연결 끊김")
        return await super().execute(stmt, params)


class TestSaveProgress:
    """도는 중인 단계의 result 를 지금까지의 진행으로 덮어쓰고 알린다 — 탐색 중에 새로
    연 화면이 스냅샷만으로 앞 회차를 되살린다."""

    def test_running_step_result_is_overwritten_and_announced(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        jid = uuid.uuid4()
        db = _RecordingSession(scalar=41)
        step = asyncio.run(rt._step(db, jid, 4, "search", "하위1", subq_idx=0))
        result = {"rounds": [dict(_ROUNDS[0])],
                  "counters": {"papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 0}}

        asyncio.run(rt._save_progress(db, step, result))

        # 단계를 닫지 않는다 — status·finished_at 은 _finish 몫이다
        assert _update_values(db.stmts[-1]) == {"result": result}
        assert db.commits == 2
        assert events[-1] == (jid, "step", {
            "seq": 4, "step_kind": "search", "subq_idx": 0, "title": "하위1",
            "detail": None, "status": "running", "result": result,
        })

    def test_db_failure_does_not_stop_exploration(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        db = _FailingUpdateSession(scalar=41)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 4, "search", "하위1", subq_idx=0))

        asyncio.run(rt._save_progress(db, step, {"rounds": []}))

        assert db.rollbacks == 1
        assert [e[2]["status"] for e in events] == ["running"]
        assert "result" not in events[-1][2]

    def test_time_limit_is_not_swallowed(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        TestStepEvents()._capture(monkeypatch, rt)
        db = _FakeSession(scalar=41)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 4, "search", "하위1", subq_idx=0))

        async def _limit(stmt, params=None):
            raise rt.SoftTimeLimitExceeded()

        db.execute = _limit
        with pytest.raises(rt.SoftTimeLimitExceeded):
            asyncio.run(rt._save_progress(db, step, {"rounds": []}))


class TestLiveProgress:
    """회차·절이 끝날 때마다 진행을 단계 result 에 남긴다 — 카운터와 회차 이력이 끝날
    때만 저장되면 탐색 중에 새로 연 화면은 다음 이벤트까지 빈칸이다."""

    def test_each_critique_saves_rounds_and_counters(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = None

        async def _two_rounds(state, subq):
            for r in _ROUNDS:
                subq.rounds.append(dict(r))
                state.seen_cnts.add(f"P{r['round']}")
                await h.emit("search", {"subq_idx": 0, "query": r["query"], "found": 1})
                await h.emit("critique", {"subq_idx": 0, "verdict": r["verdict"]})

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_two_rounds)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [([r["round"] for r in res["rounds"]], res["counters"]["papers_reviewed"])
                for _, res in h.progress] == [([1], 1), ([1, 2], 2)]
        # 진행을 남겨도 이벤트는 그대로 흐른다
        assert [e[0] for e in h.events if e[0] in ("search", "critique")] == [
            "search", "critique", "search", "critique"]

    def test_finished_search_step_keeps_counters(self, monkeypatch):
        # 다음 하위질문의 첫 회차 전까지 재접속한 화면은 이 값을 카운터로 쓴다
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1", "하위2"])

        async def _saw_papers(state, subq):
            state.seen_cnts.add(f"P{subq.idx}")
            if subq.idx == 1:
                raise ConnectionError("끊김")

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_saw_papers)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [f[2]["counters"]["papers_reviewed"] for f in h.finished[:2]] == [1, 2]

    def test_section_progress_is_saved_on_the_synthesis_step(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        h = None

        async def _one_section(state, should_stop):
            await h.on_section(0, 2, "running")
            await h.on_section(0, 2, "done")
            return {"sections": [{}]}

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            synthesize=_one_section)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [res for _, res in h.progress] == [
            {"sections_total": 2, "sections": [{"idx": 0, "status": "running"}]},
            {"sections_total": 2, "sections": [{"idx": 0, "status": "done"}]},
        ]
```

`app/tests/test_research_api.py` — `class TestStatusEvents:` 바로 위에 추가한다. 도는 잡은 스냅샷 뒤 구독으로 넘어가므로 구독을 대역으로 바꿔 종료 프레임 하나로 끝낸다.

```python
class TestSnapshotCounters:
    """카운터 이벤트는 저장되지 않는다 — 재접속한 화면은 스냅샷의 job.counters 로 채운다."""

    _EARLY = {"papers_reviewed": 5, "evidence_adopted": 2, "rechecks": 0}
    _LATE = {"papers_reviewed": 9, "evidence_adopted": 4, "rechecks": 1}

    @staticmethod
    def _step(seq, result):
        return SimpleNamespace(seq=seq, kind="search", subq_idx=seq, title="가", detail=None,
                               status="done", result=result)

    @staticmethod
    def _snapshot(api, monkeypatch, jid) -> dict:
        async def _subscribe(job_id):
            yield {"kind": "canceled", "status": "canceled"}

        monkeypatch.setattr(api.research, "subscribe", _subscribe)
        return _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

    def test_running_job_takes_the_latest_saved_counters(self, api, monkeypatch):
        jid = api.db.add_job(status="running", stage="planned", plan=["가", "나", "다"])
        api.db.steps = [self._step(1, {"counters": self._EARLY}),
                        self._step(2, {"counters": self._LATE}), self._step(3, {})]

        assert self._snapshot(api, monkeypatch, jid)["job"]["counters"] == self._LATE

    def test_finished_job_takes_report_stats(self, api):
        jid = api.db.add_job(status="completed", stage="synthesized", plan=["가"],
                             report={"stats": self._EARLY})
        api.db.steps = [self._step(1, {"counters": self._LATE})]

        snap = _frames(api.client.get(f"/api/research/{jid}/stream").text)[0]

        assert snap["job"]["counters"] == self._EARLY

    def test_no_counters_yet_leaves_the_key_out(self, api, monkeypatch):
        jid = api.db.add_job(status="running", stage="planned", plan=["가"])
        api.db.steps = [self._step(1, {})]

        assert "counters" not in self._snapshot(api, monkeypatch, jid)["job"]
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest app/tests/test_research_tasks.py app/tests/test_research_api.py -q`
Expected: `48 failed, 82 passed` — 하네스를 쓰는 테스트가 전부 `AttributeError: <module 'workers.research_tasks' ...> has no attribute '_save_progress'`(하네스가 아직 없는 함수를 바꾸려 한다), `TestSaveProgress` 3건도 같은 오류, `TestSnapshotCounters` 2건이 `KeyError: 'counters'`(`test_no_counters_yet_leaves_the_key_out` 은 지금도 통과한다).

- [ ] **Step 3: 최소 구현 — 워커**

`app/workers/research_tasks.py` import, 교체 전:
```python
from services.research.state import (
    ResearchState, SubQuestion, merge_params, restore_state, snapshot_state,
)
```
교체 후:
```python
from services.research.state import (
    ResearchState, SubQuestion, merge_params, research_stats, restore_state, snapshot_state,
)
```

`_finish` 끝부터 `_SynthProgress` 끝까지(Task 9 가 만든 모양), 교체 전:
```python
    # 저장한 result 를 그대로 싣는다 — 라이브로 본 장면과 다시 연 장면이 같아야 한다.
    await publish(step.job_id, "step", step.event(status, result))


@dataclass
class _SynthProgress:
    """synthesize 의 on_section 콜백. 절 진행을 synth 이벤트로 흘리면서 종합 단계
    result 에 남길 값도 모은다 — 실패·취소로 끝나도 거기까지의 진행이 남는다."""
    job_id: uuid.UUID
    total: int = 0
    statuses: dict[int, str] = field(default_factory=dict)

    async def __call__(self, idx: int, total: int, status: str) -> None:
        self.total = total
        self.statuses[idx] = status
        await publish(self.job_id, "synth", {"section_idx": idx, "total": total, "status": status})
```
교체 후:
```python
    # 저장한 result 를 그대로 싣는다 — 라이브로 본 장면과 다시 연 장면이 같아야 한다.
    await publish(step.job_id, "step", step.event(status, result))


async def _save_progress(db: AsyncSession, step: _StepRef, result: dict) -> None:
    """도는 중인 단계의 result 를 지금까지의 진행으로 덮어쓰고 알린다.

    단계를 닫을 때만 쓰면 탐색 중에 새로 연 화면·재접속한 화면이 그 단계의 앞 회차와
    카운터를 잃는다. 실패해도 탐색은 계속한다 — 이 기록은 화면 복원용이고, 단계를 닫을
    때 _finish 가 최종 결과를 다시 쓴다.
    """
    try:
        await db.execute(
            update(ResearchStep).where(ResearchStep.id == step.id).values(result=result)
        )
        await db.commit()
    except SoftTimeLimitExceeded:
        raise
    except Exception:
        log.warning("[research] 진행 기록 실패 job=%s seq=%s", step.job_id, step.seq,
                    exc_info=True)
        # 깨진 트랜잭션을 되돌려 두지 않으면 다음 회차의 검색 조회가 여기서 터진다
        await db.rollback()
        return
    await publish(step.job_id, "step", step.event("running", result))


def _search_progress(state: ResearchState, subq: SubQuestion) -> dict:
    # 목록을 복사한다 — 이어지는 회차가 같은 목록에 덧붙여도 저장한 값이 바뀌지 않게
    return {"rounds": list(subq.rounds), "counters": research_stats(state)}


def _round_emitter(
    db: AsyncSession, job_id: uuid.UUID, state: ResearchState, subq: SubQuestion,
    step: _StepRef,
) -> Callable[[str, dict], Awaitable[None]]:
    """러너 이벤트를 흘리고, 자기점검(회차의 끝)마다 진행을 단계 result 에 남긴다."""
    async def _emit(kind: str, payload: dict) -> None:
        await publish(job_id, kind, payload)
        if kind == "critique":
            await _save_progress(db, step, _search_progress(state, subq))
    return _emit


@dataclass
class _SynthProgress:
    """synthesize 의 on_section 콜백. 절 진행을 synth 이벤트로 흘리면서 종합 단계
    result 에 남길 값도 모은다 — 실패·취소로 끝나도 거기까지의 진행이 남는다.
    step 이 있으면 절이 바뀔 때마다 도는 중인 단계 result 에도 남긴다."""
    job_id: uuid.UUID
    db: AsyncSession | None = None
    step: _StepRef | None = None
    total: int = 0
    statuses: dict[int, str] = field(default_factory=dict)

    async def __call__(self, idx: int, total: int, status: str) -> None:
        self.total = total
        self.statuses[idx] = status
        await publish(self.job_id, "synth", {"section_idx": idx, "total": total, "status": status})
        if self.step is not None:
            await _save_progress(self.db, self.step, self.result())
```

`_run_deep_research` — 이제 쓰지 않는 `_emit` 을 지운다. 교체 전:
```python
            await _announce(jid, "running", stage)

            async def _emit(kind: str, payload: dict) -> None:
                await publish(jid, kind, payload)

```
교체 후:
```python
            await _announce(jid, "running", stage)

```

하위질문 탐색 호출, 교체 전:
```python
                    try:
                        await explore_subquestion(state, subq, db=db, emit=_emit)
```
교체 후:
```python
                    try:
                        await explore_subquestion(
                            state, subq, db=db,
                            emit=_round_emitter(db, jid, state, subq, step),
                        )
```

하위질문 단계를 닫는 두 곳(Task 9 가 만든 모양), 교체 전:
```python
                        await _finish(db, step, "failed",
                                      {"error": str(e)[:500], "rounds": subq.rounds})
```
교체 후:
```python
                        await _finish(db, step, "failed", {
                            "error": str(e)[:500], **_search_progress(state, subq),
                        })
```

교체 전:
```python
                            "parse_failed": subq.parse_failed, "capped": subq.capped,
                            "rounds": subq.rounds,
                        })
```
교체 후:
```python
                            "parse_failed": subq.parse_failed, "capped": subq.capped,
                            **_search_progress(state, subq),
                        })
```

종합 진행 콜백 생성, 교체 전:
```python
            progress = _SynthProgress(jid)
```
교체 후:
```python
            progress = _SynthProgress(jid, db=db, step=step)
```

- [ ] **Step 4: 최소 구현 — API 스냅샷**

`app/api/research.py` — `get_research` 바로 위(Task 10 의 `_steps` 뒤)에 추가한다. 교체 전:
```python
@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
```
교체 후:
```python
def _live_counters(steps: list[dict], report: dict | None) -> dict | None:
    """재접속한 화면의 카운터. 끝난 잡은 보고서의 stats, 도는 잡은 워커가 마지막으로
    단계 result 에 남긴 값이다 — counters 이벤트는 저장되지 않아, 이게 없으면 다음
    회차까지 카운터가 빈칸이다."""
    if report and report.get("stats"):
        return report["stats"]
    for step in reversed(steps):
        counters = (step["result"] or {}).get("counters")
        if counters:
            return counters
    return None


@router.get("/{job_id}")
async def get_research(job_id: str, db: AsyncSession = Depends(get_db)):
```

`stream_research` 의 스냅샷 조립(Task 10 이 만든 모양), 교체 전:
```python
    snapshot = {
        "kind": "snapshot", "steps": await _steps(db, job.id),
        "job": {"status": job.status, "stage": job.stage, "plan": job.plan},
    }
```
교체 후:
```python
    steps = await _steps(db, job.id)
    job_state = {"status": job.status, "stage": job.stage, "plan": job.plan}
    counters = _live_counters(steps, job.report)
    if counters is not None:
        job_state["counters"] = counters
    snapshot = {"kind": "snapshot", "steps": steps, "job": job_state}
```

`app/models/research.py` — `ResearchStep.result` 위 주석(Task 9 가 쓴 모양)의 search·synthesize 부분만 바꾼다. 교체 전:
```python
    # search:     {"queries": [...], "adopted": n, "verdict": "...", "note": "...",
    #              "parse_failed": bool, "capped": n,
    #              "rounds": [{"round", "query", "found_chunks", "new_papers",
    #                          "verdict", "note", "next_query"}]}
    #             verdict·note 는 마지막 라운드 값, 회차별 값은 rounds.
    #             rounds 가 없는 행은 보강 전 잡이다 — 화면은 report.trail 로 대체한다.
    # synthesize: {"sections_total": n, "sections": [{"idx": i, "status": "..."}]}
    #             idx 는 절 순번. 보강 전 잡은 {"sections": n}(정수)이다.
```
교체 후:
```python
    # search:     {"queries": [...], "adopted": n, "verdict": "...", "note": "...",
    #              "parse_failed": bool, "capped": n,
    #              "rounds": [{"round", "query", "found_chunks", "new_papers",
    #                          "verdict", "note", "next_query"}],
    #              "counters": {"papers_reviewed", "evidence_adopted", "rechecks"}}
    #             verdict·note 는 마지막 라운드 값, 회차별 값은 rounds.
    #             도는 중에는 회차가 끝날 때마다 {"rounds", "counters"} 로 갱신된다.
    #             rounds 가 없는 행은 보강 전 잡이다 — 화면은 report.trail 로 대체한다.
    # synthesize: {"sections_total": n, "sections": [{"idx": i, "status": "..."}]}
    #             idx 는 절 순번. 도는 중에는 절이 바뀔 때마다 갱신된다.
    #             보강 전 잡은 {"sections": n}(정수)이다.
```

- [ ] **Step 5: 실행해 통과 확인**

Run: `python -m pytest app/tests/test_research_tasks.py app/tests/test_research_api.py -q`
Expected: `130 passed`

전체 회귀(공통 명령): **728 passed**(Task 11 뒤 719 + 9). 기존 `TestStepResults`(Task 9)는 result 에 `counters` 키가 더해져도 키 단위로 단언하므로 그대로 통과해야 한다.

확인: `grep -n "_emit" app/workers/research_tasks.py` 가 네 줄 — `def _round_emitter(`·그 안의 `async def _emit(`·`return _emit`·호출부 `emit=_round_emitter(db, jid, state, subq, step),` — 만 보여야 한다(옛 `_emit` 클로저가 남으면 진행이 저장되지 않는다).

- [ ] **Step 6: 커밋**

```bash
git add app/workers/research_tasks.py app/api/research.py app/models/research.py app/tests/test_research_tasks.py app/tests/test_research_api.py
git commit -m "[Feat] round04b — 딥리서치 진행 중 단계 결과·스냅샷 카운터로 재접속 복원"
```

---

#### 영역 B 참고 메모

- **영역 A 선행(Task 10 만):** `app/core/deps.py` 에 계약대로 `get_browser_id_optional(x_session_id: str | None = Header(None, alias="x-session-id")) -> uuid.UUID | None` 이 있고, 형식이 틀리면 예외 없이 None 을 돌려준다. Task 10 테스트는 이 의존성을 대역으로 바꾸지 않고 헤더 해석까지 거친다. `created_by` 에는 `str(uuid)`(소문자 표준형)를 넣는다. Task 5~Task 9 는 영역 A 와 독립이라 먼저 진행해도 된다.
- **B 내부 순서:** Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10 → Task 11 → Task 12. Task 6·Task 7 은 Task 5 의 `research_stats` 를, Task 9 는 Task 7 의 `on_section` 과 Task 8 의 `_StepRef` 를 쓰고, Task 12 는 Task 8·Task 9·Task 10 이 만든 코드를 고친다.
- **DB 변경 없음:** `research_steps.result`(JSONB)·`research_jobs.created_by/created_at/started_at/finished_at/params`(기존 컬럼)만 쓴다. `models/research.py` 는 주석만 바뀐다 — 모델↔`0005` 정합 테스트(`test_research_models.py`)는 그대로 통과한다.
- **relay 무변경:** `services/research/relay.publish(job_id, kind, payload)` 는 kind 를 가리지 않는다. 새 이벤트는 전부 이 함수를 거친다. 잡 하나에 publish 가 수십 건 늘지만(단계 열고 닫기·카운터·절 진행) 호출마다 2초 타임아웃·예외 삼킴이 이미 있어 잡을 죽이지 않는다.
- **테스트 대역:** `test_research_tasks.py` 의 파이프라인 하네스는 `_step`·`_finish` 를 대역으로 바꾸므로 step 이벤트는 두 함수 단위 테스트로만 확인한다(Task 8). 하네스의 `_synthesize` 는 Task 9 에서 `on_section` 을 받아 `h.on_section` 에 보관하도록 넓힌다.
- **기존 테스트 수정은 두 건뿐:** `test_research_runner.py::test_emit_is_called_for_progress`(search 이벤트 정확 비교에 `round`·`new_papers` 추가), `test_research_api.py::test_heartbeat_detects_termination_with_same_shape`(`_terminal_status` → `_job_status`). 그 밖에는 픽스처·대역 확장(`_FakeDB` 기본 행, `_Api.events`, 하네스 `on_section`, Task 12 의 하네스 `emit`·`progress`·`_save_progress` 대역)이다.
- **옛 잡·옛 스냅샷 내성:** 보강 전 스냅샷은 `seen_cnts` 가 없으면 채택 근거의 cnts_id 로 하한을 채우고, `rounds` 가 없으면 빈 이력이 된다(`_known_fields` 가 기본값을 채움). 보강 전 잡을 retry 해도 보고서 `stats.papers_reviewed` 가 0 이 되지 않는다.
- **배포:** `nl-lib-fastapi`·`nl-lib-celery-research`·`nl-lib-celery-research-plan` 을 함께 Recreate(spec §5-3). 한쪽만 먼저 올라가도 이벤트는 추가뿐이라 깨지지 않는다 — 다만 워커만 새것이면 스냅샷에 result 가 없고, API 만 새것이면 새 이벤트가 오지 않는다. 기존 프론트는 딥리서치 스트림을 소비하지 않으므로 영향이 없다.
- **`created_by` 는 기록 목록의 원천이 아니다:** 사이드바 딥리서치 목록은 영역 A 의 `history_items`(PUT `/api/history/{job_id}`)가 정본이고, `created_by` 는 운영 추적용 기록이다(spec §4-4).

---

## 단계 2 — 기록 프론트(영역 C1)

### 영역 C1 개요 — 기록 프론트

**목표:** 사이드바 기록(도서·논문·딥리서치)을 서버 `history_items` 정본 + 브라우저 캐시·보낼 편지함(outbox) 구조로 바꾸고, 복원을 URL(`?h=`) 한 길로 모은다. spec §1-2 의 H1~M9 를 해소한다.

**설계 근거:** `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` §4 전부, §9(프론트 순수 로직 테스트).

**이 영역의 파일 구조**

| 파일 | 책임 |
|---|---|
| `frontend/vitest.config.ts` | Nuxt 없이 순수 로직만 도는 테스트 설정 |
| `frontend/types/history.ts` (v2 로 교체) | 기록 유니온·축약 결과·서버 선 모양 타입 |
| `frontend/utils/browserId.ts` | 브라우저 ID 검증·생성(비보안 컨텍스트 대비) |
| `frontend/composables/useBrowserId.ts` | 브라우저 ID 한 벌 |
| `frontend/composables/useApi.ts` | `$fetch` 래퍼(헤더 자동) · `apiHeaders` · `apiUrl` |
| `frontend/utils/historySnapshot.ts` | 복원용 축약 결과(허용 필드 목록) |
| `frontend/utils/historyStore.ts` | 서버·로컬·하이브리드 저장소, outbox, 쿼터, v1 이전, 중복 판정 |
| `frontend/utils/historyRoute.ts` | 기록 ↔ URL 규칙 |
| `frontend/utils/historyState.ts` | 기록 목록 상태(테스트 가능한 순수 부분) |
| `frontend/composables/useHistory.ts` | 앱 싱글톤·탭 동기화·v1 이전 트리거 |
| `frontend/components/AppSidebar.vue` (재작성) | 3탭·삭제·배지·라우트 강조 |
| `frontend/tests/unit/**` | Vitest 단위 테스트 |

기존 파일 수정: `pages/index.vue` · `pages/papers/index.vue` · `pages/books/[cnts_id].vue` · `pages/papers/[id].vue` · `pages/recommend/[id].vue` · `components/BookChat.vue` · `components/CitationModal.vue` · `package.json`(+lock). 삭제: `pages/search-classic.vue` · `components/ChatHistory.vue` · `composables/useSearch.ts` · `composables/useSearchHistory.ts`.

**프론트 테스트 명령:** `cd frontend && npx vitest run <파일>` (전체는 `npm test`). Nuxt 페이지·컴포넌트는 단위 테스트하지 않는다 — 페이지 태스크는 빌드(`npm run build`)·grep·수동 시나리오로 확인한다.

**순서와 중간 상태:** Task 13~Task 21 는 기존 화면을 깨지 않는다(페이지는 아직 옛 `useSearchHistory` 를 쓰고, 사이드바는 새 저장소를 읽는다). Task 22~Task 25 에서 페이지를 옮기고 옛 코드를 지운다. **배포는 Task 25 까지 끝난 뒤 영역 A(기록 API)와 함께** 한다. 빌드는 타입검사를 하지 않으므로 Task 14 이후 Task 25 전까지 옛 파일(`useSearchHistory.ts`·옛 페이지 복원 코드)에 IDE 타입 오류가 잠시 보인다 — Task 22~Task 25 에서 사라진다.

**수동 확인 시점:** Task 21~Task 24 의 "수동 확인" Step 은 기록 API(영역 A)가 떠 있는 서버와 `/api` 접두를 보존하는 개발 프록시(Task 30)가 필요하다. 로컬에는 DB 가 없으므로, 각 태스크에서는 grep·빌드·테스트까지 하고 수동 확인은 백엔드를 운영에 올린 뒤 Task 37 Step 8 에서 한꺼번에 한다(그때 이 체크박스를 채운다).

---

### Task 13: Vitest 테스트 인프라

**Files:**
- Modify: `frontend/package.json` (devDependencies·scripts), `frontend/package-lock.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tests/unit/helpers/memoryStorage.ts`
- Test: `frontend/tests/unit/memoryStorage.test.ts`

이후 모든 저장소 테스트가 `MemoryStorage` 의 쿼터 흉내에 기대므로, 헬퍼 자체가 브라우저처럼 `QuotaExceededError` DOMException 을 던지는지 먼저 고정한다.

- [ ] **Step 1: Vitest 설치**

Run: `cd frontend && npm install -D vitest@^3.2.4`

계획 작성 때 검증한 메이저(3.2)에 고정한다.
Expected: `added N packages` 후 `nuxt prepare` 가 오류 없이 끝난다. `package.json` 의 `devDependencies` 에 `"vitest"` 가 생긴다.

Run: `cd frontend && npx vitest --version`
Expected: `vitest/<버전>` 한 줄.

- [ ] **Step 2: 설정 파일과 스크립트**

```ts
// frontend/vitest.config.ts
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Nuxt 를 띄우지 않고 순수 로직만 돌린다 — 앱 코드의 "~/..." 경로만 맞춰 준다
const root = fileURLToPath(new URL("./", import.meta.url)).replace(/\\/g, "/");

export default defineConfig({
  resolve: {
    alias: [{ find: /^~\//, replacement: root }],
  },
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.ts"],
  },
});
```

`frontend/package.json` 의 `scripts` 에 한 줄을 더한다(나머지는 그대로).

```json
  "scripts": {
    "build": "nuxt build",
    "dev": "nuxt dev",
    "generate": "nuxt generate",
    "preview": "nuxt preview",
    "postinstall": "nuxt prepare",
    "test": "vitest run"
  },
```

- [ ] **Step 3: 실패하는 테스트**

```ts
// frontend/tests/unit/memoryStorage.test.ts
import { describe, expect, it } from "vitest";
import { MemoryStorage } from "./helpers/memoryStorage";

describe("MemoryStorage", () => {
  it("저장한 값을 돌려주고 지운다", () => {
    const s = new MemoryStorage();
    s.setItem("a", "1");
    s.setItem("b", "2");
    expect(s.getItem("a")).toBe("1");
    expect(s.length).toBe(2);
    expect(s.key(1)).toBe("b");
    s.removeItem("a");
    expect(s.getItem("a")).toBeNull();
  });

  it("용량을 넘기면 QuotaExceededError DOMException 을 던진다", () => {
    const s = new MemoryStorage(10);
    let caught: unknown;
    try {
      s.setItem("k", "x".repeat(20));
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(DOMException);
    expect((caught as DOMException).name).toBe("QuotaExceededError");
    expect(s.getItem("k")).toBeNull();
  });

  it("같은 키를 덮어쓸 때는 기존 값 크기를 빼고 계산한다", () => {
    const s = new MemoryStorage(12);
    s.setItem("k", "x".repeat(10));
    expect(() => s.setItem("k", "y".repeat(10))).not.toThrow();
    expect(s.getItem("k")).toBe("y".repeat(10));
  });

  it("failWith 가 있으면 그 오류를 던진다", () => {
    const s = new MemoryStorage();
    s.failWith = new DOMException("막힘", "SecurityError");
    expect(() => s.setItem("k", "v")).toThrow("막힘");
  });
});
```

- [ ] **Step 4: 실행해 실패 확인**

Run: `cd frontend && npx vitest run tests/unit/memoryStorage.test.ts`
Expected: FAIL — `./helpers/memoryStorage` 를 찾지 못해 수집 단계에서 실패(`Failed to load url ./helpers/memoryStorage … Does the file exist?`).

- [ ] **Step 5: 헬퍼 구현**

```ts
// frontend/tests/unit/helpers/memoryStorage.ts
/** 용량 상한을 흉내 내는 Storage — 브라우저 localStorage 의 쿼터 초과를 재현한다 */
export class MemoryStorage implements Storage {
  [key: string]: unknown;
  failWith: Error | null = null;
  private readonly data = new Map<string, string>();

  constructor(private readonly capacity = Number.POSITIVE_INFINITY) {}

  get length(): number {
    return this.data.size;
  }

  clear(): void {
    this.data.clear();
  }

  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }

  key(index: number): string | null {
    return [...this.data.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.data.delete(key);
  }

  setItem(key: string, value: string): void {
    if (this.failWith) throw this.failWith;
    const next = String(value);
    if (this.usedExcept(key) + key.length + next.length > this.capacity) {
      throw new DOMException("쿼터 초과", "QuotaExceededError");
    }
    this.data.set(key, next);
  }

  private usedExcept(skip: string): number {
    let total = 0;
    for (const [k, v] of this.data) if (k !== skip) total += k.length + v.length;
    return total;
  }
}
```

- [ ] **Step 6: 실행해 통과 확인**

Run: `cd frontend && npx vitest run tests/unit/memoryStorage.test.ts`
Expected: `Test Files  1 passed (1)` · `Tests  4 passed (4)`

Run: `cd frontend && npm test`
Expected: `Tests  4 passed (4)`

- [ ] **Step 7: 커밋**

```
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/tests/unit/helpers/memoryStorage.ts frontend/tests/unit/memoryStorage.test.ts
git commit -m "[Chore] round04b — 프론트 단위 테스트(Vitest) 도입"
```

---

### Task 14: 기록 타입 v2

**Files:**
- Modify(전체 교체): `frontend/types/history.ts` (현재 1~8행, v1 `HistoryEntry` 하나)

타입만 있는 파일이라 이 태스크 자체의 테스트는 없다. 이후 Task 16~Task 20 의 테스트가 이 타입으로 쓰인다. 딥리서치 기록의 상태 모양은 `HistoryResearchStatus` 로 부른다 — `types/research.ts`(Task 26)의 `ResearchStatus` 는 상태 문자열 유니온이라 같은 이름을 쓰면 import 할 때 헷갈린다(백엔드 `schemas/history.py` 의 `ResearchStatus` 는 그대로다).

- [ ] **Step 1: 파일 교체**

```ts
// frontend/types/history.ts
export type HistoryKind = "book" | "paper" | "research";

// 유니온에 그냥 Omit 을 쓰면 공통 키만 남아 snapshot·refId 같은 종류별 필드가 사라진다
export type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

export interface SnapshotBookInfo {
  cnts_id?: string;
  title?: string;
  personal_author?: string;
  corporate_author?: string;
  publisher?: string;
  pub_date?: string;
  themes?: string;
  keyword?: string;
  subject?: string;
  series_title?: string;
  grade?: string;
  kci_citations?: number;
  references?: string[];
}

export interface SnapshotItem {
  book_id: string;
  best_score: number;
  title_score?: number;
  content_score?: number;
  book_info?: SnapshotBookInfo;
  chunks: never[];
}

export interface BookSnapshot {
  query: string;
  rewritten_query?: string;
  books: SnapshotItem[];
}

export interface PaperSnapshot {
  query: string;
  books: SnapshotItem[];
}

export interface BookAi {
  intro: string;
  items: unknown[];
}

export interface PaperAi {
  text: string;
  refs: unknown[];
}

export interface HistoryResearchStatus {
  status: string;
  stage: string;
}

export interface HistoryBase {
  id: string;
  kind: HistoryKind;
  title: string;
  createdAt: string;
  updatedAt?: string;
  params: Record<string, unknown>;
}

export interface BookEntry extends HistoryBase {
  kind: "book";
  snapshot?: BookSnapshot;
  ai?: BookAi;
}

export interface PaperEntry extends HistoryBase {
  kind: "paper";
  snapshot?: PaperSnapshot;
  ai?: PaperAi;
}

export interface ResearchEntry extends HistoryBase {
  kind: "research";
  refId: string;
  research?: HistoryResearchStatus;
}

export type HistoryEntry = BookEntry | PaperEntry | ResearchEntry;

export type HistoryEntryInput = DistributiveOmit<HistoryEntry, "id" | "createdAt">;

export interface HistoryPatch {
  title?: string;
  params?: Record<string, unknown>;
  snapshot?: BookSnapshot | PaperSnapshot;
  ai?: BookAi | PaperAi;
}

/** v1(`skx_search_history`) 항목 — 서버로 옮길 때만 읽는다 */
export interface LegacyHistoryEntry {
  id: string;
  type: "book" | "paper";
  query: string;
  timestamp: number | string;
  result?: unknown;
  aiSummary?: string;
}

// 아래는 app/schemas/history.py 의 선 모양 — 서버가 주는 snake_case 를 그대로 받는다
export interface HistoryItemOut {
  id: string;
  kind: HistoryKind;
  title: string;
  params: Record<string, unknown>;
  ref_id: string | null;
  created_at: string;
  updated_at: string;
  has_snapshot: boolean;
  has_ai: boolean;
  research: HistoryResearchStatus | null;
}

export interface HistoryItemDetail extends HistoryItemOut {
  snapshot: BookSnapshot | PaperSnapshot | null;
  ai: BookAi | PaperAi | null;
}

export interface HistoryListOut {
  items: HistoryItemOut[];
  next_cursor: string | null;
}

export interface HistoryItemIn {
  kind: HistoryKind;
  title: string;
  params: Record<string, unknown>;
  snapshot: BookSnapshot | PaperSnapshot | null;
  ai: BookAi | PaperAi | null;
  ref_id: string | null;
}

export interface HistoryImportItem extends HistoryItemIn {
  id?: string | null;
  legacy_id?: string | null;
  created_at?: string | null;
}

export interface HistoryImportOut {
  imported: number;
  skipped: number;
  id_map: Record<string, string>;
}
```

- [ ] **Step 2: 기존 테스트 확인**

Run: `cd frontend && npm test`
Expected: `Tests  4 passed (4)` (타입만 바뀌어 런타임 영향 없음)

- [ ] **Step 3: 커밋**

```
git add frontend/types/history.ts
git commit -m "[Feat] round04b — 기록 타입 v2(kind 유니온·축약 결과·서버 선 모양)"
```

---

### Task 15: 브라우저 ID 단일화와 API 헤더 래퍼

**Files:**
- Create: `frontend/utils/browserId.ts`
- Create: `frontend/composables/useBrowserId.ts`
- Create: `frontend/composables/useApi.ts`
- Test: `frontend/tests/unit/browserId.test.ts`

운영 게이트웨이는 http 라 `crypto.randomUUID` 가 없는 비보안 컨텍스트다(기존 코드에 대체 구현이 있던 이유). 생성기는 `getRandomValues` → `Math.random` 순으로 물러선다. `useApi` 는 Nuxt API 라 단위 테스트하지 않는다(Task 22 의 수동 확인에서 헤더를 본다).

- [ ] **Step 1: 실패하는 테스트**

```ts
// frontend/tests/unit/browserId.test.ts
import { webcrypto } from "node:crypto";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BROWSER_ID_KEY,
  generateUuidV4,
  isUuidV4,
  readOrCreateBrowserId,
  safeLocalStorage,
} from "~/utils/browserId";
import { MemoryStorage } from "./helpers/memoryStorage";

const V4 = "3f2b8c1e-9d4a-4f6b-8a2c-1e5d7b9c0a12";

describe("isUuidV4", () => {
  it("소문자 표준형 v4 를 받는다", () => {
    expect(isUuidV4(V4)).toBe(true);
  });

  it("대문자·v1·v5·변형 비트가 틀린 값·형식 밖 값은 거절한다", () => {
    expect(isUuidV4(V4.toUpperCase())).toBe(false);
    expect(isUuidV4("3f2b8c1e-9d4a-1f6b-8a2c-1e5d7b9c0a12")).toBe(false);
    expect(isUuidV4("3f2b8c1e-9d4a-5f6b-8a2c-1e5d7b9c0a12")).toBe(false);
    expect(isUuidV4("3f2b8c1e-9d4a-4f6b-ca2c-1e5d7b9c0a12")).toBe(false);
    expect(isUuidV4("null")).toBe(false);
    expect(isUuidV4(null)).toBe(false);
    expect(isUuidV4(undefined)).toBe(false);
  });
});

describe("readOrCreateBrowserId", () => {
  it("저장된 값이 올바르면 그대로 쓴다", () => {
    const s = new MemoryStorage();
    s.setItem(BROWSER_ID_KEY, V4);
    const gen = vi.fn(() => "unused");
    expect(readOrCreateBrowserId(s, gen)).toBe(V4);
    expect(gen).not.toHaveBeenCalled();
  });

  it("형식이 틀리면 새로 만들어 저장한다", () => {
    const s = new MemoryStorage();
    s.setItem(BROWSER_ID_KEY, "null");
    const fresh = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    expect(readOrCreateBrowserId(s, () => fresh)).toBe(fresh);
    expect(s.getItem(BROWSER_ID_KEY)).toBe(fresh);
  });

  it("생성기가 대문자를 주면 소문자로 저장한다", () => {
    const s = new MemoryStorage();
    expect(readOrCreateBrowserId(s, () => V4.toUpperCase())).toBe(V4);
    expect(s.getItem(BROWSER_ID_KEY)).toBe(V4);
  });

  it("저장소가 없으면 만든 값을 돌려준다", () => {
    expect(readOrCreateBrowserId(null, () => V4)).toBe(V4);
  });

  it("읽기·쓰기가 막혀도 던지지 않는다", () => {
    const blocked = {
      getItem: () => {
        throw new DOMException("막힘", "SecurityError");
      },
      setItem: () => {
        throw new DOMException("막힘", "SecurityError");
      },
    } as unknown as Storage;
    expect(readOrCreateBrowserId(blocked, () => V4)).toBe(V4);
  });
});

describe("generateUuidV4", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("randomUUID 가 있으면 v4 를 만든다", () => {
    expect(isUuidV4(generateUuidV4())).toBe(true);
  });

  it("randomUUID 가 없는 비보안 컨텍스트에서도 서로 다른 v4 를 만든다", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: (a: Uint8Array<ArrayBuffer>) => webcrypto.getRandomValues(a),
    });
    const ids = new Set(Array.from({ length: 50 }, () => generateUuidV4()));
    expect([...ids].every((id) => isUuidV4(id))).toBe(true);
    expect(ids.size).toBe(50);
  });

  it("crypto 가 아예 없어도 v4 를 만든다", () => {
    vi.stubGlobal("crypto", undefined);
    expect(isUuidV4(generateUuidV4())).toBe(true);
  });
});

describe("safeLocalStorage", () => {
  it("window 가 없는 서버 렌더에서는 null", () => {
    expect(safeLocalStorage()).toBeNull();
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `cd frontend && npx vitest run tests/unit/browserId.test.ts`
Expected: FAIL — `~/utils/browserId` 를 불러오지 못해 수집 단계에서 실패.

- [ ] **Step 3: `utils/browserId.ts`**

```ts
// frontend/utils/browserId.ts
export const BROWSER_ID_KEY = "sid";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function isUuidV4(s: unknown): s is string {
  return typeof s === "string" && UUID_V4.test(s);
}

export function generateUuidV4(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  // randomUUID 는 https·localhost 에서만 있다 — 운영 게이트웨이(http)에서는 getRandomValues 로 만든다
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  const bytes = new Uint8Array(16);
  if (c && typeof c.getRandomValues === "function") {
    c.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function readOrCreateBrowserId(storage: Storage | null, gen: () => string): string {
  let stored: string | null = null;
  try {
    stored = storage ? storage.getItem(BROWSER_ID_KEY) : null;
  } catch {
    stored = null;
  }
  if (isUuidV4(stored)) return stored;
  const fresh = gen().toLowerCase();
  try {
    storage?.setItem(BROWSER_ID_KEY, fresh);
  } catch {
    // 막힌 저장소 — 이 페이지 수명 동안만 메모리 값으로 쓴다
  }
  return fresh;
}

export function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: `composables/useBrowserId.ts`**

```ts
// frontend/composables/useBrowserId.ts
import { generateUuidV4, readOrCreateBrowserId, safeLocalStorage } from "~/utils/browserId";

let cached: string | null = null;

export function useBrowserId(): string {
  // 서버 렌더에는 브라우저 ID 가 없다 — 빈 값이면 헤더를 붙이지 않는다
  if (import.meta.server) return "";
  if (!cached) cached = readOrCreateBrowserId(safeLocalStorage(), generateUuidV4);
  return cached;
}
```

- [ ] **Step 5: `composables/useApi.ts`**

```ts
// frontend/composables/useApi.ts
import { useBrowserId } from "./useBrowserId";

function apiBase(): string {
  return ((useRuntimeConfig().public.apiBase as string) || "/api").replace(/\/+$/, "");
}

export function apiUrl(path: string): string {
  return `${apiBase()}${path.startsWith("/") ? path : `/${path}`}`;
}

/** 스트림처럼 native fetch 를 써야 하는 곳용 — $fetch 는 useApi 가 붙인다 */
export function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const sid = useBrowserId();
  return sid ? { ...extra, "x-session-id": sid } : { ...extra };
}

export function useApi() {
  return $fetch.create({
    baseURL: apiBase(),
    onRequest({ options }) {
      const sid = useBrowserId();
      if (!sid) return;
      const headers = new Headers(options.headers);
      headers.set("x-session-id", sid);
      options.headers = headers;
    },
  });
}
```

- [ ] **Step 6: 실행해 통과 확인**

Run: `cd frontend && npx vitest run tests/unit/browserId.test.ts`
Expected: `Tests  11 passed (11)`

Run: `cd frontend && npm test`
Expected: `Tests  15 passed (15)`

- [ ] **Step 7: 커밋**

```
git add frontend/utils/browserId.ts frontend/composables/useBrowserId.ts frontend/composables/useApi.ts frontend/tests/unit/browserId.test.ts
git commit -m "[Feat] round04b — 브라우저 ID 단일화와 x-session-id 자동 첨부 래퍼"
```

---

### Task 16: 복원용 축약 결과(snapshot) — 허용 필드 목록

**Files:**
- Create: `frontend/utils/historySnapshot.ts`
- Test: `frontend/tests/unit/historySnapshot.test.ts`

지금은 빼는 필드를 나열해서(`pages/index.vue:964-983`, `pages/papers/index.vue:804-811`) 서버 필드가 늘면 저장량도 는다(M3). 목록 카드·인용 모달이 실제로 그리는 필드만 고른다. 논문 참고문헌은 인용 모달이 쓰지만 길어서 30개로 자른다(200KB 상한 여유).

- [ ] **Step 1: 실패하는 테스트**

```ts
// frontend/tests/unit/historySnapshot.test.ts
import { describe, expect, it } from "vitest";
import {
  SNAPSHOT_MAX_ITEMS,
  SNAPSHOT_MAX_REFERENCES,
  slimBookResult,
  slimPaperResult,
} from "~/utils/historySnapshot";

function serverBook(i: number) {
  return {
    book_id: `B${i}`,
    best_score: 0.9,
    title_score: 0.8,
    content_score: 0.7,
    reason: "이유",
    chunks: [{ chunk_id: "c1", text: "본문".repeat(200), page_start: 1, page_end: 2, score: 0.5 }],
    book_info: {
      cnts_id: `B${i}`,
      title: `책 ${i}`,
      personal_author: "홍길동",
      publisher: "출판사",
      pub_date: "20200101",
      themes: "경제,무역",
      summary: "요약".repeat(300),
      plot: "줄거리",
      introduction: "소개",
      read_effect: "효과",
      abstract: "초록",
      cover_prompt: "표지 프롬프트",
      references: ["참고1"],
      is_embedded: true,
      extracted_keywords: ["k"],
    },
  };
}

describe("slimBookResult", () => {
  it("목록 카드가 쓰는 필드만 남긴다", () => {
    const snap = slimBookResult({
      mode: "book",
      query: "경제",
      rewritten_query: "한국 경제",
      elapsed_ms: 10,
      books: [serverBook(1)],
    });
    expect(snap).toEqual({
      query: "경제",
      rewritten_query: "한국 경제",
      books: [
        {
          book_id: "B1",
          best_score: 0.9,
          title_score: 0.8,
          content_score: 0.7,
          chunks: [],
          book_info: {
            cnts_id: "B1",
            title: "책 1",
            personal_author: "홍길동",
            publisher: "출판사",
            pub_date: "20200101",
            themes: "경제,무역",
          },
        },
      ],
    });
  });

  it("서버가 새 필드를 보내도 저장하지 않는다", () => {
    const base = serverBook(1);
    const book = { ...base, new_field: "x", book_info: { ...base.book_info, brand_new: "y".repeat(1000) } };
    const snap = slimBookResult({ query: "q", books: [book] })!;
    expect(snap.books[0]).not.toHaveProperty("new_field");
    expect(snap.books[0]!.book_info).not.toHaveProperty("brand_new");
  });

  it(`최대 ${SNAPSHOT_MAX_ITEMS}건만 남긴다`, () => {
    const snap = slimBookResult({ query: "q", books: Array.from({ length: 25 }, (_, i) => serverBook(i)) })!;
    expect(snap.books).toHaveLength(SNAPSHOT_MAX_ITEMS);
    expect(snap.books[0]!.book_id).toBe("B0");
  });

  it("모양이 틀리면 null, book_id 없는 항목은 건너뛴다", () => {
    expect(slimBookResult(null)).toBeNull();
    expect(slimBookResult({ query: "q" })).toBeNull();
    expect(slimBookResult({ query: "q", books: "x" })).toBeNull();
    const snap = slimBookResult({ query: "q", books: [{ best_score: 1 }, serverBook(2)] })!;
    expect(snap.books.map((b) => b.book_id)).toEqual(["B2"]);
  });

  it("빈 값 필드는 싣지 않는다", () => {
    const b = serverBook(1);
    const snap = slimBookResult({
      query: "q",
      books: [{ ...b, book_info: { ...b.book_info, publisher: "", personal_author: null } }],
    })!;
    expect(snap.books[0]!.book_info).not.toHaveProperty("publisher");
    expect(snap.books[0]!.book_info).not.toHaveProperty("personal_author");
  });
});

describe("slimPaperResult", () => {
  it("논문 카드·인용 모달이 쓰는 필드만 남기고 참고문헌은 상한까지만", () => {
    const paper = {
      book_id: "P1",
      best_score: 0.7,
      title_score: 0.5,
      chunks: [{ text: "x" }],
      book_info: {
        cnts_id: "P1",
        title: "논문",
        personal_author: "김",
        corporate_author: "학회",
        pub_date: "2021.03",
        series_title: "학술지",
        grade: "KCI 등재",
        kci_citations: 12,
        abstract: "초록".repeat(500),
        summary: "요약",
        introduction: "소개",
        references: Array.from({ length: 40 }, (_, i) => `참고 ${i}`),
      },
    };
    const snap = slimPaperResult({ query: "딥러닝", books: [paper] })!;
    expect(snap.query).toBe("딥러닝");
    const item = snap.books[0]!;
    expect(item).not.toHaveProperty("title_score");
    expect(item.chunks).toEqual([]);
    expect(item.book_info).toMatchObject({
      title: "논문",
      grade: "KCI 등재",
      series_title: "학술지",
      kci_citations: 12,
      corporate_author: "학회",
    });
    expect(item.book_info).not.toHaveProperty("abstract");
    expect(item.book_info!.references).toHaveLength(SNAPSHOT_MAX_REFERENCES);
  });

  it("모양이 틀리면 null", () => {
    expect(slimPaperResult(undefined)).toBeNull();
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `cd frontend && npx vitest run tests/unit/historySnapshot.test.ts`
Expected: FAIL — `~/utils/historySnapshot` 를 불러오지 못해 수집 단계에서 실패.

- [ ] **Step 3: 구현**

```ts
// frontend/utils/historySnapshot.ts
import type { BookSnapshot, PaperSnapshot, SnapshotBookInfo, SnapshotItem } from "~/types/history";

export const SNAPSHOT_MAX_ITEMS = 20;
export const SNAPSHOT_MAX_REFERENCES = 30;

// 빼는 필드를 나열하면 서버가 필드를 늘릴 때 저장량도 따라 는다 — 카드가 그리는 필드만 고른다
const BOOK_INFO_FIELDS: readonly (keyof SnapshotBookInfo)[] = [
  "cnts_id",
  "title",
  "personal_author",
  "corporate_author",
  "publisher",
  "pub_date",
  "themes",
  "keyword",
  "subject",
];

const PAPER_INFO_FIELDS: readonly (keyof SnapshotBookInfo)[] = [
  "cnts_id",
  "title",
  "personal_author",
  "corporate_author",
  "pub_date",
  "series_title",
  "grade",
  "kci_citations",
  "references",
];

type Loose = Record<string, unknown>;

function isObject(v: unknown): v is Loose {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function pickInfo(info: unknown, fields: readonly (keyof SnapshotBookInfo)[]): SnapshotBookInfo | undefined {
  if (!isObject(info)) return undefined;
  const out: Loose = {};
  for (const field of fields) {
    const value = info[field];
    if (value === undefined || value === null || value === "") continue;
    out[field] =
      field === "references" && Array.isArray(value)
        ? value.filter((r) => typeof r === "string").slice(0, SNAPSHOT_MAX_REFERENCES)
        : value;
  }
  return out as SnapshotBookInfo;
}

function slimItems(
  result: unknown,
  fields: readonly (keyof SnapshotBookInfo)[],
  withScores: boolean,
): SnapshotItem[] | null {
  if (!isObject(result) || !Array.isArray(result.books)) return null;
  return result.books
    .filter(isObject)
    .filter((b) => typeof b.book_id === "string")
    .slice(0, SNAPSHOT_MAX_ITEMS)
    .map((b) => {
      const item: SnapshotItem = {
        book_id: b.book_id as string,
        best_score: typeof b.best_score === "number" ? b.best_score : 0,
        chunks: [],
      };
      if (withScores && typeof b.title_score === "number") item.title_score = b.title_score;
      if (withScores && typeof b.content_score === "number") item.content_score = b.content_score;
      const info = pickInfo(b.book_info, fields);
      if (info) item.book_info = info;
      return item;
    });
}

export function slimBookResult(result: unknown): BookSnapshot | null {
  const books = slimItems(result, BOOK_INFO_FIELDS, true);
  if (!books) return null;
  const r = result as Loose;
  const snap: BookSnapshot = { query: typeof r.query === "string" ? r.query : "", books };
  if (typeof r.rewritten_query === "string" && r.rewritten_query) snap.rewritten_query = r.rewritten_query;
  return snap;
}

export function slimPaperResult(result: unknown): PaperSnapshot | null {
  const books = slimItems(result, PAPER_INFO_FIELDS, false);
  if (!books) return null;
  const r = result as Loose;
  return { query: typeof r.query === "string" ? r.query : "", books };
}
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `cd frontend && npx vitest run tests/unit/historySnapshot.test.ts`
Expected: `Tests  7 passed (7)`

Run: `cd frontend && npm test`
Expected: `Tests  22 passed (22)`

- [ ] **Step 5: 커밋**

```
git add frontend/utils/historySnapshot.ts frontend/tests/unit/historySnapshot.test.ts
git commit -m "[Feat] round04b — 복원용 축약 결과를 허용 필드 목록으로"
```

---

### Task 17: 기록 저장소 — 서버 정본·로컬 캐시·보낼 편지함·하이브리드

**Files:**
- Create: `frontend/utils/historyStore.ts`
- Create: `frontend/tests/unit/helpers/fakeHistory.ts`
- Test: `frontend/tests/unit/historyStore.test.ts`

규칙(spec §4-5):
- 서버가 정본. 서버 실패(네트워크·408·429·5xx)면 브라우저 캐시에 먼저 쓰고 outbox 에 넣어 다음 목록 읽기·온라인 복귀 때 보낸다. 4xx 는 다시 보내도 같은 답이라 버린다.
- **outbox 가 비어 있지 않으면 새 변경도 서버로 바로 보내지 않고 줄 세운다** — 순서가 뒤집히면 서버에 아직 없는 기록에 PATCH 가 먼저 닿아 404 가 난다. 목록도 그동안은 캐시로 답한다(캐시에는 사용자의 최근 변경이 이미 반영돼 있다).
- 쿼터 초과(`QuotaExceededError` 만)는 가장 오래된 snapshot → ai 순으로 덜어 내고 목록은 남긴다. 쿼터가 아닌 쓰기 오류는 그 수명 동안 메모리로만 동작한다.
- 캐시는 매 동작마다 저장소를 다시 읽고 고쳐 쓴다 — 다른 탭이 쓴 outbox 를 덮어 지우지 않게(M4).

- [ ] **Step 1: 테스트 헬퍼**

```ts
// frontend/tests/unit/helpers/fakeHistory.ts
import { vi } from "vitest";
import type {
  BookEntry,
  HistoryEntry,
  HistoryKind,
  HistoryPatch,
  PaperEntry,
  ResearchEntry,
} from "~/types/history";
import type { HybridHistoryStore } from "~/utils/historyStore";

export const ID1 = "11111111-1111-4111-8111-111111111111";
export const ID2 = "22222222-2222-4222-8222-222222222222";
export const ID3 = "33333333-3333-4333-8333-333333333333";
export const T0 = "2026-09-26T01:00:00.000Z";

export function bookEntry(id: string, over: Partial<BookEntry> = {}): BookEntry {
  return { id, kind: "book", title: "한국 경제", createdAt: T0, params: {}, ...over };
}

export function paperEntry(id: string, over: Partial<PaperEntry> = {}): PaperEntry {
  return { id, kind: "paper", title: "딥러닝 자연어 처리", createdAt: T0, params: {}, ...over };
}

export function researchEntry(id: string, over: Partial<ResearchEntry> = {}): ResearchEntry {
  return { id, kind: "research", title: "국내 AI 규제 연구 동향", createdAt: T0, params: {}, refId: id, ...over };
}

export function httpError(status: number): Error & { status: number } {
  return Object.assign(new Error(`HTTP ${status}`), { status });
}

export function networkError(): TypeError {
  return new TypeError("fetch failed");
}

/** 서버를 흉내 내는 메모리 저장소. fail() 로 이후 모든 호출을 실패시킨다 */
export function fakeServer() {
  const rows = new Map<string, HistoryEntry>();
  let failure: unknown = null;
  const guard = () => {
    if (failure) throw failure;
  };
  const store = {
    rows,
    fail(e: unknown) {
      failure = e;
    },
    recover() {
      failure = null;
    },
    flush: vi.fn(async () => {}),
    list: vi.fn(async (kind?: HistoryKind) => {
      guard();
      return { items: [...rows.values()].filter((e) => !kind || e.kind === kind), nextCursor: null };
    }),
    get: vi.fn(async (id: string) => {
      guard();
      return rows.get(id) ?? null;
    }),
    put: vi.fn(async (entry: HistoryEntry) => {
      guard();
      rows.set(entry.id, entry);
      return entry;
    }),
    patch: vi.fn(async (id: string, partial: HistoryPatch) => {
      guard();
      const found = rows.get(id);
      if (!found) return null;
      const merged = { ...found, ...partial } as HistoryEntry;
      rows.set(id, merged);
      return merged;
    }),
    remove: vi.fn(async (id: string) => {
      guard();
      rows.delete(id);
    }),
    clear: vi.fn(async (kind: HistoryKind) => {
      guard();
      for (const [id, e] of rows) if (e.kind === kind) rows.delete(id);
    }),
  };
  return store satisfies HybridHistoryStore;
}
```

- [ ] **Step 2: 실패하는 테스트**

```ts
// frontend/tests/unit/historyStore.test.ts
import { describe, expect, it } from "vitest";
import type { HistoryItemDetail } from "~/types/history";
import {
  HISTORY_CACHE_KEY,
  HISTORY_OUTBOX_KEY,
  createHybridStore,
  createLocalStore,
  createServerStore,
  errorStatus,
  fromWire,
  isQuotaError,
  isRetryable,
  toWire,
  type HistoryFetchOptions,
  type HistoryFetcher,
} from "~/utils/historyStore";
import { MemoryStorage } from "./helpers/memoryStorage";
import {
  ID1,
  ID2,
  ID3,
  bookEntry,
  fakeServer,
  httpError,
  networkError,
  paperEntry,
  researchEntry,
} from "./helpers/fakeHistory";

const snap = { query: "한국 경제", books: [{ book_id: "B1", best_score: 0.9, chunks: [] as never[] }] };

function wire(over: Partial<HistoryItemDetail> = {}): HistoryItemDetail {
  return {
    id: ID1,
    kind: "book",
    title: "한국 경제",
    params: {},
    ref_id: null,
    created_at: "2026-09-26T01:00:00+00:00",
    updated_at: "2026-09-26T01:00:00+00:00",
    has_snapshot: false,
    has_ai: false,
    research: null,
    snapshot: null,
    ai: null,
    ...over,
  };
}

function fakeFetcher(respond: (path: string, opts?: HistoryFetchOptions) => unknown) {
  const calls: Array<{ path: string; opts?: HistoryFetchOptions }> = [];
  const fetcher: HistoryFetcher = async <T,>(path: string, opts?: HistoryFetchOptions) => {
    calls.push({ path, opts });
    return (await respond(path, opts)) as T;
  };
  return { fetcher, calls };
}

describe("오류 분류", () => {
  it("errorStatus 는 status·statusCode·response.status 를 읽는다", () => {
    expect(errorStatus(httpError(404))).toBe(404);
    expect(errorStatus({ statusCode: 503 })).toBe(503);
    expect(errorStatus({ response: { status: 500 } })).toBe(500);
    expect(errorStatus(networkError())).toBeNull();
  });

  it("네트워크·408·429·5xx 만 다시 보낸다", () => {
    expect(isRetryable(networkError())).toBe(true);
    expect(isRetryable(httpError(503))).toBe(true);
    expect(isRetryable(httpError(429))).toBe(true);
    expect(isRetryable(httpError(404))).toBe(false);
    expect(isRetryable(httpError(413))).toBe(false);
  });

  it("쿼터 초과만 쿼터 오류로 본다", () => {
    expect(isQuotaError(new DOMException("x", "QuotaExceededError"))).toBe(true);
    expect(isQuotaError(new DOMException("x", "SecurityError"))).toBe(false);
    expect(isQuotaError(new Error("QuotaExceededError"))).toBe(false);
  });
});

describe("선 모양 변환", () => {
  it("fromWire 는 종류별 필드를 옮긴다", () => {
    expect(fromWire(wire({ snapshot: snap, ai: { intro: "소개", items: [] } }))).toEqual({
      id: ID1,
      kind: "book",
      title: "한국 경제",
      params: {},
      createdAt: "2026-09-26T01:00:00+00:00",
      updatedAt: "2026-09-26T01:00:00+00:00",
      snapshot: snap,
      ai: { intro: "소개", items: [] },
    });
    expect(
      fromWire(wire({ id: ID2, kind: "research", ref_id: ID2, research: { status: "running", stage: "planned" } })),
    ).toMatchObject({ kind: "research", refId: ID2, research: { status: "running", stage: "planned" } });
  });

  it("toWire 는 딥리서치에 ref_id 를 싣고 snapshot·ai 는 비운다", () => {
    expect(toWire(researchEntry(ID3))).toEqual({
      kind: "research",
      title: "국내 AI 규제 연구 동향",
      params: {},
      snapshot: null,
      ai: null,
      ref_id: ID3,
    });
    expect(toWire(bookEntry(ID1, { snapshot: snap }))).toMatchObject({
      kind: "book",
      snapshot: snap,
      ai: null,
      ref_id: null,
    });
  });
});

describe("createServerStore", () => {
  it("list 는 kind·limit·before 를 쿼리로 보내고 항목을 바꿔 돌려준다", async () => {
    const { fetcher, calls } = fakeFetcher(() => ({ items: [wire()], next_cursor: "c1" }));
    const res = await createServerStore(fetcher).list("book", { limit: 10, before: "c0" });
    expect(calls[0]).toMatchObject({
      path: "/history",
      opts: { method: "GET", query: { kind: "book", limit: 10, before: "c0" } },
    });
    expect(res.nextCursor).toBe("c1");
    expect(res.items[0]).toMatchObject({ id: ID1, kind: "book" });
  });

  it("get 은 404 면 null, 다른 오류는 그대로 던진다", async () => {
    const notFound = fakeFetcher(() => {
      throw httpError(404);
    });
    expect(await createServerStore(notFound.fetcher).get(ID1)).toBeNull();
    const broken = fakeFetcher(() => {
      throw httpError(500);
    });
    await expect(createServerStore(broken.fetcher).get(ID1)).rejects.toMatchObject({ status: 500 });
  });

  it("put 은 PUT 본문에 선 모양을 싣는다", async () => {
    const { fetcher, calls } = fakeFetcher(() => wire({ snapshot: snap }));
    const saved = await createServerStore(fetcher).put(bookEntry(ID1, { snapshot: snap }));
    expect(calls[0]).toMatchObject({
      path: `/history/${ID1}`,
      opts: { method: "PUT", body: { kind: "book", title: "한국 경제", snapshot: snap } },
    });
    expect(saved).toMatchObject({ id: ID1, snapshot: snap });
  });

  it("patch 는 정의된 필드만 보내고 404 면 null", async () => {
    const { fetcher, calls } = fakeFetcher(() => {
      throw httpError(404);
    });
    const res = await createServerStore(fetcher).patch(ID1, { ai: { text: "요약", refs: [] }, title: undefined });
    expect(res).toBeNull();
    expect(calls[0]!.opts).toMatchObject({ method: "PATCH", body: { ai: { text: "요약", refs: [] } } });
    expect(calls[0]!.opts!.body).not.toHaveProperty("title");
  });

  it("remove 는 404 를 성공으로 본다", async () => {
    const { fetcher } = fakeFetcher(() => {
      throw httpError(404);
    });
    await expect(createServerStore(fetcher).remove(ID1)).resolves.toBeUndefined();
  });

  it("clear 는 kind 를 쿼리로 보낸다", async () => {
    const { fetcher, calls } = fakeFetcher(() => undefined);
    await createServerStore(fetcher).clear("paper");
    expect(calls[0]).toMatchObject({ path: "/history", opts: { method: "DELETE", query: { kind: "paper" } } });
  });

  it("importItems 는 items 를 POST 한다", async () => {
    const { fetcher, calls } = fakeFetcher(() => ({ imported: 1, skipped: 0, id_map: { "1727": ID1 } }));
    const res = await createServerStore(fetcher).importItems([
      { kind: "book", title: "a", params: {}, snapshot: null, ai: null, ref_id: null, legacy_id: "1727" },
    ]);
    expect(calls[0]).toMatchObject({ path: "/history/import", opts: { method: "POST" } });
    expect(res.id_map["1727"]).toBe(ID1);
  });
});

describe("createLocalStore", () => {
  it("종류별로 최신순 목록을 돌려준다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1, { createdAt: "2026-09-26T01:00:00.000Z" }));
    await local.put(bookEntry(ID2, { createdAt: "2026-09-26T02:00:00.000Z" }));
    await local.put(paperEntry(ID3));
    const { items } = await local.list("book");
    expect(items.map((e) => e.id)).toEqual([ID2, ID1]);
  });

  it("before 커서로 다음 쪽을 읽는다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1, { createdAt: "2026-09-26T01:00:00.000Z" }));
    await local.put(bookEntry(ID2, { createdAt: "2026-09-26T02:00:00.000Z" }));
    const first = await local.list("book", { limit: 1 });
    expect(first.items.map((e) => e.id)).toEqual([ID2]);
    const second = await local.list("book", { limit: 1, before: first.nextCursor! });
    expect(second.items.map((e) => e.id)).toEqual([ID1]);
    expect(second.nextCursor).toBeNull();
  });

  it("patch·remove·clear 가 캐시에 반영된다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1));
    await local.put(paperEntry(ID2));
    expect(await local.patch(ID1, { title: "새 제목" })).toMatchObject({ id: ID1, title: "새 제목" });
    expect(await local.patch(ID3, { title: "x" })).toBeNull();
    await local.remove(ID1);
    expect(await local.get(ID1)).toBeNull();
    await local.clear("paper");
    expect((await local.list()).items).toEqual([]);
  });

  it("같은 저장소를 여는 다른 인스턴스(다른 탭)가 같은 내용을 본다", async () => {
    const storage = new MemoryStorage();
    await createLocalStore(storage).put(bookEntry(ID1));
    expect(await createLocalStore(storage).get(ID1)).toMatchObject({ id: ID1 });
  });

  it("저장소가 없으면 메모리로 동작한다", async () => {
    const local = createLocalStore(null);
    await local.put(bookEntry(ID1));
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
  });

  it("쿼터에 걸리면 오래된 snapshot 부터 비우고 목록은 남긴다", async () => {
    const heavy = {
      query: "q",
      books: Array.from({ length: 20 }, (_, i) => ({
        book_id: `B${i}`,
        best_score: 0.5,
        chunks: [] as never[],
        book_info: { title: "제목".repeat(40) },
      })),
    };
    const oneSize = JSON.stringify([bookEntry(ID1, { snapshot: heavy })]).length;
    const storage = new MemoryStorage(Math.floor(oneSize * 1.6));
    const local = createLocalStore(storage);
    await local.put(bookEntry(ID1, { createdAt: "2026-09-26T01:00:00.000Z", snapshot: heavy }));
    await local.put(bookEntry(ID2, { createdAt: "2026-09-26T02:00:00.000Z", snapshot: heavy }));
    const cached = JSON.parse(storage.getItem(HISTORY_CACHE_KEY)!) as Array<{ id: string; snapshot?: unknown }>;
    expect(cached.map((e) => e.id).sort()).toEqual([ID1, ID2].sort());
    expect(cached.find((e) => e.id === ID1)!.snapshot).toBeUndefined();
    expect(cached.find((e) => e.id === ID2)!.snapshot).toEqual(heavy);
  });

  it("쿼터가 아닌 쓰기 오류는 던지지 않고 메모리로 넘어간다", async () => {
    const storage = new MemoryStorage();
    storage.failWith = new DOMException("막힘", "SecurityError");
    const local = createLocalStore(storage);
    await expect(local.put(bookEntry(ID1))).resolves.toMatchObject({ id: ID1 });
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
  });

  it("깨진 JSON 은 빈 목록으로 읽는다", async () => {
    const storage = new MemoryStorage();
    storage.setItem(HISTORY_CACHE_KEY, "{깨짐");
    expect((await createLocalStore(storage).list()).items).toEqual([]);
  });

  it("replaceKind 는 서버 목록으로 갈아 끼우되 캐시에 있던 snapshot 은 붙여 둔다", async () => {
    const local = createLocalStore(new MemoryStorage());
    await local.put(bookEntry(ID1, { snapshot: snap }));
    await local.put(bookEntry(ID2));
    await local.put(paperEntry(ID3));
    local.replaceKind("book", [bookEntry(ID1, { title: "서버 제목" })]);
    expect(await local.get(ID1)).toMatchObject({ title: "서버 제목", snapshot: snap });
    expect(await local.get(ID2)).toBeNull();
    expect(await local.get(ID3)).toMatchObject({ kind: "paper" });
  });

  it("outbox 는 넣은 순서대로 쌓이고 opId 로 뺀다", () => {
    const storage = new MemoryStorage();
    const local = createLocalStore(storage);
    local.enqueue({ op: "remove", id: ID1 });
    local.enqueue({ op: "clear", kind: "book" });
    const ops = local.readOutbox();
    expect(ops.map((o) => o.op)).toEqual(["remove", "clear"]);
    expect(storage.getItem(HISTORY_OUTBOX_KEY)).not.toBeNull();
    local.dropOutbox(ops[0]!.opId);
    expect(local.readOutbox().map((o) => o.op)).toEqual(["clear"]);
  });
});

describe("createHybridStore", () => {
  function setup() {
    const server = fakeServer();
    const local = createLocalStore(new MemoryStorage());
    return { server, local, store: createHybridStore(server, local) };
  }

  it("서버 저장이 되면 캐시에도 남긴다", async () => {
    const { server, local, store } = setup();
    await store.put(bookEntry(ID1, { snapshot: snap }));
    expect(server.rows.has(ID1)).toBe(true);
    expect(await local.get(ID1)).toMatchObject({ snapshot: snap });
    expect(local.readOutbox()).toEqual([]);
  });

  it("서버가 안 되면 브라우저에 먼저 저장하고 보낼 편지함에 넣는다", async () => {
    const { server, local, store } = setup();
    server.fail(networkError());
    const saved = await store.put(bookEntry(ID1));
    expect(saved.id).toBe(ID1);
    expect(await local.get(ID1)).toMatchObject({ id: ID1 });
    expect(local.readOutbox()).toMatchObject([{ op: "put", entry: { id: ID1 } }]);
  });

  it("다음 목록 읽기에서 편지함을 먼저 보내고 서버 목록을 쓴다", async () => {
    const { server, local, store } = setup();
    server.fail(httpError(503));
    await store.put(bookEntry(ID1));
    server.recover();
    const { items } = await store.list("book");
    expect(server.rows.has(ID1)).toBe(true);
    expect(items.map((e) => e.id)).toEqual([ID1]);
    expect(local.readOutbox()).toEqual([]);
  });

  it("편지함이 남아 있으면 목록은 캐시로 답한다", async () => {
    const { server, store } = setup();
    server.fail(networkError());
    await store.put(bookEntry(ID1));
    const { items } = await store.list("book");
    expect(items.map((e) => e.id)).toEqual([ID1]);
    expect(server.list).not.toHaveBeenCalled();
  });

  it("4xx 거절은 편지함에 넣지 않고 그대로 던진다", async () => {
    const { server, local, store } = setup();
    server.fail(httpError(422));
    await expect(store.put(bookEntry(ID1))).rejects.toMatchObject({ status: 422 });
    expect(local.readOutbox()).toEqual([]);
  });

  it("보낼 때 4xx 로 거절된 편지는 버리고 다음 편지를 보낸다", async () => {
    const { server, local, store } = setup();
    local.enqueue({ op: "patch", id: ID1, partial: { title: "x" } });
    local.enqueue({ op: "put", entry: bookEntry(ID2) });
    server.patch.mockRejectedValueOnce(httpError(422));
    await store.flush();
    expect(server.rows.has(ID2)).toBe(true);
    expect(local.readOutbox()).toEqual([]);
  });

  it("다시 보낼 만한 실패에서는 멈추고 순서를 지킨다", async () => {
    const { server, local, store } = setup();
    local.enqueue({ op: "put", entry: bookEntry(ID1) });
    local.enqueue({ op: "remove", id: ID1 });
    server.put.mockRejectedValueOnce(networkError());
    await store.flush();
    expect(server.remove).not.toHaveBeenCalled();
    expect(local.readOutbox().map((o) => o.op)).toEqual(["put", "remove"]);
  });

  it("편지함이 남아 있을 때의 수정은 서버로 바로 가지 않고 뒤에 줄 선다", async () => {
    const { server, local, store } = setup();
    server.fail(networkError());
    await store.put(bookEntry(ID1));
    server.recover();
    server.put.mockRejectedValueOnce(networkError());
    await store.patch(ID1, { ai: { intro: "소개", items: [] } });
    expect(server.patch).not.toHaveBeenCalled();
    expect(local.readOutbox().map((o) => o.op)).toEqual(["put", "patch"]);
    expect(await local.get(ID1)).toMatchObject({ ai: { intro: "소개", items: [] } });
  });

  it("서버에 없는 기록은 캐시에서도 지운다", async () => {
    const { local, store } = setup();
    await local.put(bookEntry(ID1));
    expect(await store.get(ID1)).toBeNull();
    expect(await local.get(ID1)).toBeNull();
  });

  it("서버가 안 되면 get 은 캐시로 답한다", async () => {
    const { server, local, store } = setup();
    await local.put(bookEntry(ID1, { snapshot: snap }));
    server.fail(networkError());
    expect(await store.get(ID1)).toMatchObject({ snapshot: snap });
  });
});
```

- [ ] **Step 3: 실행해 실패 확인**

Run: `cd frontend && npx vitest run tests/unit/historyStore.test.ts`
Expected: FAIL — `~/utils/historyStore` 를 불러오지 못해 수집 단계에서 실패.

- [ ] **Step 4: 구현**

```ts
// frontend/utils/historyStore.ts
import type {
  BookAi,
  BookSnapshot,
  DistributiveOmit,
  HistoryEntry,
  HistoryImportItem,
  HistoryImportOut,
  HistoryItemDetail,
  HistoryItemIn,
  HistoryItemOut,
  HistoryKind,
  HistoryListOut,
  HistoryPatch,
  PaperAi,
  PaperSnapshot,
} from "~/types/history";

export const HISTORY_CACHE_KEY = "skx_history_v2";
export const HISTORY_OUTBOX_KEY = "skx_history_outbox";
export const HISTORY_PING_KEY = "skx_history_ping";
export const HISTORY_PAGE_SIZE = 30;

const CACHE_LIMIT_PER_KIND = 100;
const OUTBOX_LIMIT = 200;
const REQUEST_TIMEOUT_MS = 10_000;

export interface ListOptions {
  limit?: number;
  before?: string;
}

export interface ListResult {
  items: HistoryEntry[];
  nextCursor: string | null;
}

export interface HistoryStore {
  list(kind?: HistoryKind, opts?: ListOptions): Promise<ListResult>;
  get(id: string): Promise<HistoryEntry | null>;
  put(entry: HistoryEntry): Promise<HistoryEntry>;
  patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(kind: HistoryKind): Promise<void>;
}

export interface ServerHistoryStore extends HistoryStore {
  importItems(items: HistoryImportItem[]): Promise<HistoryImportOut>;
}

export type OutboxOp =
  | { opId: string; op: "put"; entry: HistoryEntry }
  | { opId: string; op: "patch"; id: string; partial: HistoryPatch }
  | { opId: string; op: "remove"; id: string }
  | { opId: string; op: "clear"; kind: HistoryKind };

export type OutboxOpInput = DistributiveOmit<OutboxOp, "opId">;

export interface LocalHistoryStore extends HistoryStore {
  replaceKind(kind: HistoryKind | undefined, items: HistoryEntry[]): void;
  readOutbox(): OutboxOp[];
  enqueue(op: OutboxOpInput): void;
  dropOutbox(opId: string): void;
}

export interface HybridHistoryStore extends HistoryStore {
  flush(): Promise<void>;
}

export interface HistoryFetchOptions {
  method?: "GET" | "PUT" | "PATCH" | "DELETE" | "POST";
  query?: Record<string, string | number | undefined>;
  body?: Record<string, unknown>;
  timeout?: number;
}

export type HistoryFetcher = <T>(path: string, opts?: HistoryFetchOptions) => Promise<T>;

export function errorStatus(e: unknown): number | null {
  if (typeof e !== "object" || e === null) return null;
  const err = e as { status?: unknown; statusCode?: unknown; response?: { status?: unknown } };
  const status = err.status ?? err.statusCode ?? err.response?.status;
  return typeof status === "number" ? status : null;
}

/** 네트워크 단절·시간 초과·서버 오류만 다시 보낼 가치가 있다 — 4xx 는 다시 보내도 같은 답이다 */
export function isRetryable(e: unknown): boolean {
  const status = errorStatus(e);
  return status === null || status === 408 || status === 429 || status >= 500;
}

export function isQuotaError(e: unknown): boolean {
  if (typeof DOMException === "undefined" || !(e instanceof DOMException)) return false;
  return e.name === "QuotaExceededError" || e.name === "NS_ERROR_DOM_QUOTA_REACHED" || e.code === 22 || e.code === 1014;
}

export function fromWire(item: HistoryItemOut | HistoryItemDetail): HistoryEntry {
  const base = {
    id: item.id,
    title: item.title,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    params: item.params ?? {},
  };
  if (item.kind === "research") {
    return {
      ...base,
      kind: "research",
      refId: item.ref_id ?? item.id,
      ...(item.research ? { research: item.research } : {}),
    };
  }
  const { snapshot, ai } = item as Partial<HistoryItemDetail>;
  if (item.kind === "book") {
    return {
      ...base,
      kind: "book",
      ...(snapshot ? { snapshot: snapshot as BookSnapshot } : {}),
      ...(ai ? { ai: ai as BookAi } : {}),
    };
  }
  return {
    ...base,
    kind: "paper",
    ...(snapshot ? { snapshot: snapshot as PaperSnapshot } : {}),
    ...(ai ? { ai: ai as PaperAi } : {}),
  };
}

export function toWire(entry: HistoryEntry): HistoryItemIn {
  const research = entry.kind === "research";
  return {
    kind: entry.kind,
    title: entry.title.slice(0, 500),
    params: entry.params ?? {},
    snapshot: research ? null : (entry.snapshot ?? null),
    ai: research ? null : (entry.ai ?? null),
    ref_id: research ? entry.refId : null,
  };
}

function patchBody(partial: HistoryPatch): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(partial)) if (value !== undefined) body[key] = value;
  return body;
}

export function createServerStore(fetcher: HistoryFetcher): ServerHistoryStore {
  const at = (id: string) => `/history/${encodeURIComponent(id)}`;
  const timeout = REQUEST_TIMEOUT_MS;
  return {
    async list(kind, opts) {
      const res = await fetcher<HistoryListOut>("/history", {
        method: "GET",
        query: { kind, limit: opts?.limit ?? HISTORY_PAGE_SIZE, before: opts?.before },
        timeout,
      });
      return { items: res.items.map(fromWire), nextCursor: res.next_cursor };
    },
    async get(id) {
      try {
        return fromWire(await fetcher<HistoryItemDetail>(at(id), { method: "GET", timeout }));
      } catch (e) {
        if (errorStatus(e) === 404) return null;
        throw e;
      }
    },
    async put(entry) {
      return fromWire(
        await fetcher<HistoryItemDetail>(at(entry.id), { method: "PUT", body: { ...toWire(entry) }, timeout }),
      );
    },
    async patch(id, partial) {
      try {
        return fromWire(await fetcher<HistoryItemDetail>(at(id), { method: "PATCH", body: patchBody(partial), timeout }));
      } catch (e) {
        if (errorStatus(e) === 404) return null;
        throw e;
      }
    },
    async remove(id) {
      try {
        await fetcher<void>(at(id), { method: "DELETE", timeout });
      } catch (e) {
        if (errorStatus(e) !== 404) throw e;
      }
    },
    async clear(kind) {
      await fetcher<void>("/history", { method: "DELETE", query: { kind }, timeout });
    },
    async importItems(items) {
      return fetcher<HistoryImportOut>("/history/import", { method: "POST", body: { items }, timeout });
    },
  };
}

function timeOf(e: HistoryEntry): number {
  const t = Date.parse(e.createdAt);
  return Number.isNaN(t) ? 0 : t;
}

function newestFirst(a: HistoryEntry, b: HistoryEntry): number {
  return timeOf(b) - timeOf(a);
}

function cursorOf(e: HistoryEntry): string {
  return `${e.createdAt}|${e.id}`;
}

function withoutField(entry: HistoryEntry, field: "snapshot" | "ai"): HistoryEntry {
  if (entry.kind === "research") return entry;
  const copy = { ...entry };
  delete copy[field];
  return copy;
}

function capPerKind(list: HistoryEntry[]): HistoryEntry[] {
  const count: Partial<Record<HistoryKind, number>> = {};
  return [...list].sort(newestFirst).filter((e) => {
    count[e.kind] = (count[e.kind] ?? 0) + 1;
    return count[e.kind]! <= CACHE_LIMIT_PER_KIND;
  });
}

function newOpId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function createLocalStore(storage: Storage | null): LocalHistoryStore {
  // 저장소가 막히면(사생활 모드·쿼터 한계) 이 수명 동안은 메모리만 쓴다
  let memoryOnly = storage === null;
  let cacheMem: HistoryEntry[] = [];
  let outboxMem: OutboxOp[] = [];

  function read<T>(key: string, mem: T[]): T[] {
    if (memoryOnly || !storage) return mem;
    let raw: string | null;
    try {
      raw = storage.getItem(key);
    } catch {
      memoryOnly = true;
      return mem;
    }
    if (raw === null) return [];
    try {
      const parsed: unknown = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as T[]) : [];
    } catch {
      return [];
    }
  }

  function write<T>(key: string, list: T[], shed: (current: T[]) => T[] | null): T[] {
    if (memoryOnly || !storage) return list;
    let attempt = list;
    for (;;) {
      try {
        storage.setItem(key, JSON.stringify(attempt));
        return attempt;
      } catch (e) {
        const lighter = isQuotaError(e) ? shed(attempt) : null;
        if (!lighter) {
          memoryOnly = true;
          return attempt;
        }
        attempt = lighter;
      }
    }
  }

  function shedCache(list: HistoryEntry[]): HistoryEntry[] | null {
    const oldest = [...list].sort((a, b) => timeOf(a) - timeOf(b));
    for (const field of ["snapshot", "ai"] as const) {
      const victim = oldest.find((e) => e.kind !== "research" && e[field] !== undefined);
      if (victim) return list.map((e) => (e === victim ? withoutField(e, field) : e));
    }
    return null;
  }

  function shedOutbox(ops: OutboxOp[]): OutboxOp[] | null {
    const victim = ops.find((o) => o.op === "put" && o.entry.kind !== "research" && o.entry.snapshot !== undefined);
    if (!victim || victim.op !== "put") return null;
    return ops.map((o) => (o === victim ? { ...victim, entry: withoutField(victim.entry, "snapshot") } : o));
  }

  const readCache = () => read(HISTORY_CACHE_KEY, cacheMem);
  const writeCache = (list: HistoryEntry[]) => {
    cacheMem = write(HISTORY_CACHE_KEY, capPerKind(list), shedCache);
  };
  const readOutboxList = () => read(HISTORY_OUTBOX_KEY, outboxMem);
  const writeOutbox = (ops: OutboxOp[]) => {
    outboxMem = write(HISTORY_OUTBOX_KEY, ops.slice(-OUTBOX_LIMIT), shedOutbox);
  };

  return {
    async list(kind, opts) {
      const all = readCache()
        .filter((e) => !kind || e.kind === kind)
        .sort(newestFirst);
      const limit = opts?.limit ?? HISTORY_PAGE_SIZE;
      let start = 0;
      if (opts?.before) {
        const idx = all.findIndex((e) => cursorOf(e) === opts.before);
        start = idx < 0 ? all.length : idx + 1;
      }
      const items = all.slice(start, start + limit);
      const last = items[items.length - 1];
      return { items, nextCursor: last && start + limit < all.length ? cursorOf(last) : null };
    },
    async get(id) {
      return readCache().find((e) => e.id === id) ?? null;
    },
    async put(entry) {
      writeCache([entry, ...readCache().filter((e) => e.id !== entry.id)]);
      return entry;
    },
    async patch(id, partial) {
      const list = readCache();
      const found = list.find((e) => e.id === id);
      if (!found) return null;
      const merged = { ...found, ...patchBody(partial), updatedAt: new Date().toISOString() } as HistoryEntry;
      writeCache(list.map((e) => (e.id === id ? merged : e)));
      return merged;
    },
    async remove(id) {
      writeCache(readCache().filter((e) => e.id !== id));
    },
    async clear(kind) {
      writeCache(readCache().filter((e) => e.kind !== kind));
    },
    replaceKind(kind, items) {
      const current = readCache();
      const cached = new Map(current.map((e) => [e.id, e]));
      const merged = items.map((item) => {
        const prev = cached.get(item.id);
        if (!prev || prev.kind === "research" || item.kind === "research") return item;
        // 서버 목록에는 snapshot·ai 가 없다 — 오프라인 복원용으로 캐시에 있던 것을 붙여 둔다
        return {
          ...item,
          ...(prev.snapshot ? { snapshot: prev.snapshot } : {}),
          ...(prev.ai ? { ai: prev.ai } : {}),
        } as HistoryEntry;
      });
      const keep = kind ? current.filter((e) => e.kind !== kind) : [];
      writeCache([...merged, ...keep]);
    },
    readOutbox() {
      return readOutboxList();
    },
    enqueue(op) {
      writeOutbox([...readOutboxList(), { ...op, opId: newOpId() } as OutboxOp]);
    },
    dropOutbox(opId) {
      writeOutbox(readOutboxList().filter((o) => o.opId !== opId));
    },
  };
}

type Sent<T> = { ok: true; value: T } | { ok: false };

export function createHybridStore(server: HistoryStore, local: LocalHistoryStore): HybridHistoryStore {
  let flushing: Promise<void> | null = null;

  async function apply(op: OutboxOp): Promise<void> {
    switch (op.op) {
      case "put":
        await local.put(await server.put(op.entry));
        return;
      case "patch":
        await server.patch(op.id, op.partial);
        return;
      case "remove":
        await server.remove(op.id);
        return;
      case "clear":
        await server.clear(op.kind);
        return;
    }
  }

  async function drain(): Promise<void> {
    for (const op of local.readOutbox()) {
      try {
        await apply(op);
      } catch (e) {
        if (isRetryable(e)) return;
        // 4xx 는 다시 보내도 같은 거절이다 — 이 편지는 버리고 다음으로 넘어간다
      }
      local.dropOutbox(op.opId);
    }
  }

  function flush(): Promise<void> {
    if (!flushing) {
      flushing = drain().finally(() => {
        flushing = null;
      });
    }
    return flushing;
  }

  // 편지가 남아 있으면 서버로 바로 보내지 않는다 — 순서가 뒤집히면 아직 서버에 없는 기록에 수정이 먼저 닿는다
  async function direct<T>(send: () => Promise<T>): Promise<Sent<T>> {
    await flush();
    if (local.readOutbox().length) return { ok: false };
    try {
      return { ok: true, value: await send() };
    } catch (e) {
      if (!isRetryable(e)) throw e;
      return { ok: false };
    }
  }

  return {
    flush,
    async list(kind, opts) {
      const res = await direct(() => server.list(kind, opts));
      if (!res.ok) return local.list(kind, opts);
      if (!opts?.before) local.replaceKind(kind, res.value.items);
      return res.value;
    },
    async get(id) {
      const res = await direct(() => server.get(id));
      if (!res.ok) return local.get(id);
      if (res.value) {
        await local.put(res.value);
        return res.value;
      }
      await local.remove(id);
      return null;
    },
    async put(entry) {
      const res = await direct(() => server.put(entry));
      if (res.ok) {
        await local.put(res.value);
        return res.value;
      }
      await local.put(entry);
      local.enqueue({ op: "put", entry });
      return entry;
    },
    async patch(id, partial) {
      const res = await direct(() => server.patch(id, partial));
      if (res.ok) {
        if (res.value) await local.put(res.value);
        else await local.remove(id);
        return res.value;
      }
      const merged = await local.patch(id, partial);
      local.enqueue({ op: "patch", id, partial });
      return merged;
    },
    async remove(id) {
      await local.remove(id);
      const res = await direct(() => server.remove(id));
      if (!res.ok) local.enqueue({ op: "remove", id });
    },
    async clear(kind) {
      await local.clear(kind);
      const res = await direct(() => server.clear(kind));
      if (!res.ok) local.enqueue({ op: "clear", kind });
    },
  };
}
```

- [ ] **Step 5: 실행해 통과 확인**

Run: `cd frontend && npx vitest run tests/unit/historyStore.test.ts`
Expected: `Tests  32 passed (32)`

Run: `cd frontend && npm test`
Expected: `Tests  54 passed (54)`

- [ ] **Step 6: 커밋**

```
git add frontend/utils/historyStore.ts frontend/tests/unit/helpers/fakeHistory.ts frontend/tests/unit/historyStore.test.ts
git commit -m "[Feat] round04b — 기록 저장소(서버 정본·로컬 캐시·보낼 편지함)"
```

---

### Task 18: 옛 기록(v1) 이전과 10분 중복 판정

**Files:**
- Modify: `frontend/utils/historyStore.ts` (맨 위 import 한 줄 추가, 파일 끝에 함수 추가)
- Test: `frontend/tests/unit/historyLegacy.test.ts`

규칙(spec §4-2·§4-5·§4-7):
- v1 `skx_search_history` → `type→kind`, `query→title`, `timestamp→createdAt`, `aiSummary` JSON 파싱(도서 `{intro, items}`, 논문 `{text, refs}`; JSON 이 아니면 원문을 글로), 결과는 Task 16 축약으로. 읽을 수 없는 시각은 v1 id(`Date.now()` 문자열)로 대신한다.
- 서버가 받기 전에는 v1 을 건드리지 않는다. 받은 뒤에도 지우지 않고 `skx_search_history_backup_v1` 로 이름만 바꾼다. 이미 백업이 있으면 덮지 않고 시각 접미 키에 둔다(구버전 탭이 v1 을 다시 쓴 경우). 사본 둘 자리가 없으면(쿼터) 원본을 그대로 두고 `skx_history_v1_migrated` 표시만 남겨 다시 올리지 않는다.
- 대응표 `{v1id: 새 id}` 는 `skx_history_v1_map` 에 누적한다(서버가 uuid5 로 결정론 변환 — 브라우저에 uuid5 구현을 두지 않는다).
- 중복: 같은 kind · 정규화 제목 · 조건(키 순서·빈 값 무시)이 **최근 갱신 기준 10분 안**이면 같은 기록. 딥리서치는 잡 id 로 따로 묶이므로 대상이 아니다.

- [ ] **Step 1: 실패하는 테스트**

```ts
// frontend/tests/unit/historyLegacy.test.ts
import { describe, expect, it, vi } from "vitest";
import type { HistoryImportItem, HistoryImportOut, LegacyHistoryEntry } from "~/types/history";
import {
  LEGACY_BACKUP_KEY,
  LEGACY_HISTORY_KEY,
  LEGACY_MIGRATED_KEY,
  V1_MAP_KEY,
  convertLegacy,
  findRecentDuplicate,
  migrateLegacy,
  normalizeTitle,
  readV1Map,
} from "~/utils/historyStore";
import { MemoryStorage } from "./helpers/memoryStorage";
import { ID1, ID2, bookEntry, networkError, paperEntry, researchEntry } from "./helpers/fakeHistory";

const V1_BOOK = {
  id: "1727000000000",
  type: "book",
  query: "  한국 경제 책  ",
  timestamp: "2026-09-20T01:02:03.000Z",
  result: {
    mode: "book",
    query: "한국 경제 책",
    rewritten_query: "한국 경제",
    books: [
      {
        book_id: "B1",
        best_score: 0.8,
        chunks: [{ text: "본문" }],
        book_info: { title: "경제학", summary: "긴 요약" },
      },
    ],
  },
  aiSummary: JSON.stringify({ intro: "소개", items: [{ book_id: "B1", reason: "이유" }] }),
};

const V1_PAPER = {
  id: "1727000000001",
  type: "paper",
  query: "딥러닝",
  timestamp: 1727000000001,
  aiSummary: JSON.stringify({ text: "요약", refs: [{ num: 1 }] }),
};

function v1(n: number) {
  return Array.from({ length: n }, (_, i) => ({ ...V1_BOOK, id: String(1727000000000 + i) }));
}

function importer(fail?: unknown) {
  return {
    importItems: vi.fn(async (items: HistoryImportItem[]): Promise<HistoryImportOut> => {
      if (fail) throw fail;
      return {
        imported: items.length,
        skipped: 0,
        id_map: Object.fromEntries(items.map((i) => [i.legacy_id!, `uuid-${i.legacy_id}`])),
      };
    }),
  };
}

describe("convertLegacy", () => {
  it("type·query·timestamp·aiSummary 를 v2 로 옮기고 결과는 축약한다", () => {
    const [book] = convertLegacy([V1_BOOK] as LegacyHistoryEntry[]);
    expect(book).toMatchObject({
      legacy_id: "1727000000000",
      kind: "book",
      title: "한국 경제 책",
      params: {},
      ref_id: null,
      created_at: "2026-09-20T01:02:03.000Z",
      ai: { intro: "소개", items: [{ book_id: "B1", reason: "이유" }] },
    });
    expect(book!.snapshot).toEqual({
      query: "한국 경제 책",
      rewritten_query: "한국 경제",
      books: [{ book_id: "B1", best_score: 0.8, chunks: [], book_info: { title: "경제학" } }],
    });
  });

  it("논문 요약 JSON 과 JSON 이 아닌 옛 문자열을 모두 받는다", () => {
    const [paper, plainPaper, plainBook] = convertLegacy([
      V1_PAPER,
      { ...V1_PAPER, id: "2", aiSummary: "그냥 글" },
      { ...V1_BOOK, id: "3", aiSummary: "책 소개 글" },
    ] as LegacyHistoryEntry[]);
    expect(paper!.ai).toEqual({ text: "요약", refs: [{ num: 1 }] });
    expect(plainPaper!.ai).toEqual({ text: "그냥 글", refs: [] });
    expect(plainBook!.ai).toEqual({ intro: "책 소개 글", items: [] });
  });

  it("숫자 시각은 ISO 로, 읽을 수 없는 시각은 옛 id(Date.now)로 대신한다", () => {
    const [a, b] = convertLegacy([
      V1_PAPER,
      { ...V1_PAPER, id: "1727000000999", timestamp: "어제" },
    ] as LegacyHistoryEntry[]);
    expect(a!.created_at).toBe(new Date(1727000000001).toISOString());
    expect(a!.snapshot).toBeNull();
    expect(b!.created_at).toBe(new Date(1727000000999).toISOString());
  });

  it("형식이 틀린 항목은 건너뛰고 같은 옛 id 는 한 번만 올린다", () => {
    const out = convertLegacy([
      V1_BOOK,
      V1_BOOK,
      { id: "9", type: "chat", query: "x" },
      { id: "8", type: "book", query: "   " },
      null,
      "문자열",
    ] as unknown as LegacyHistoryEntry[]);
    expect(out.map((i) => i.legacy_id)).toEqual(["1727000000000"]);
  });

  it("제목은 500자로 자른다", () => {
    const [e] = convertLegacy([{ ...V1_BOOK, query: "가".repeat(600) }] as LegacyHistoryEntry[]);
    expect(e!.title).toHaveLength(500);
  });
});

describe("readV1Map", () => {
  it("대응표를 읽고 깨졌으면 빈 표", () => {
    const s = new MemoryStorage();
    expect(readV1Map(s)).toEqual({});
    s.setItem(V1_MAP_KEY, JSON.stringify({ "1727": ID1, bad: 3 }));
    expect(readV1Map(s)).toEqual({ "1727": ID1 });
    s.setItem(V1_MAP_KEY, "깨짐");
    expect(readV1Map(s)).toEqual({});
    expect(readV1Map(null)).toEqual({});
  });
});

describe("migrateLegacy", () => {
  it("v1 이 없으면 아무것도 하지 않는다", async () => {
    const server = importer();
    expect(await migrateLegacy(new MemoryStorage(), server)).toBeNull();
    expect(server.importItems).not.toHaveBeenCalled();
  });

  it("올린 뒤 원본을 백업 키로 옮기고 대응표를 남긴다", async () => {
    const s = new MemoryStorage();
    const raw = JSON.stringify(v1(2));
    s.setItem(LEGACY_HISTORY_KEY, raw);
    expect(await migrateLegacy(s, importer())).toEqual({ imported: 2 });
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBeNull();
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe(raw);
    expect(readV1Map(s)).toEqual({
      "1727000000000": "uuid-1727000000000",
      "1727000000001": "uuid-1727000000001",
    });
  });

  it("서버가 실패하면 v1 을 그대로 두고 null", async () => {
    const s = new MemoryStorage();
    const raw = JSON.stringify(v1(1));
    s.setItem(LEGACY_HISTORY_KEY, raw);
    expect(await migrateLegacy(s, importer(networkError()))).toBeNull();
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBe(raw);
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBeNull();
    expect(s.getItem(V1_MAP_KEY)).toBeNull();
  });

  it("100건씩 나눠 올린다", async () => {
    const s = new MemoryStorage();
    s.setItem(LEGACY_HISTORY_KEY, JSON.stringify(v1(101)));
    const server = importer();
    expect(await migrateLegacy(s, server)).toEqual({ imported: 101 });
    expect(server.importItems.mock.calls.map(([items]) => items.length)).toEqual([100, 1]);
  });

  it("이미 백업이 있으면 덮어쓰지 않고 새 키에 둔다", async () => {
    const s = new MemoryStorage();
    s.setItem(LEGACY_BACKUP_KEY, "옛 백업");
    s.setItem(LEGACY_HISTORY_KEY, JSON.stringify(v1(1)));
    await migrateLegacy(s, importer());
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe("옛 백업");
    const extra = Array.from({ length: s.length }, (_, i) => s.key(i)).filter((k) =>
      k?.startsWith(`${LEGACY_BACKUP_KEY}_`),
    );
    expect(extra).toHaveLength(1);
  });

  it("사본 둘 자리가 없으면 원본을 남기고 다시 올리지 않게 표시한다", async () => {
    const raw = JSON.stringify(v1(5));
    const s = new MemoryStorage(Math.floor(raw.length * 1.5));
    s.setItem(LEGACY_HISTORY_KEY, raw);
    const server = importer();
    expect(await migrateLegacy(s, server)).toEqual({ imported: 5 });
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBe(raw);
    expect(s.getItem(LEGACY_MIGRATED_KEY)).toBe("1");
    expect(await migrateLegacy(s, server)).toBeNull();
    expect(server.importItems).toHaveBeenCalledTimes(1);
  });

  it("깨진 v1 도 원문 그대로 백업으로 옮긴다", async () => {
    const s = new MemoryStorage();
    s.setItem(LEGACY_HISTORY_KEY, "[깨짐");
    const server = importer();
    expect(await migrateLegacy(s, server)).toEqual({ imported: 0 });
    expect(server.importItems).not.toHaveBeenCalled();
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe("[깨짐");
  });
});

describe("중복 판정", () => {
  const NOW = Date.parse("2026-09-26T03:00:00.000Z");
  const minutesAgo = (m: number) => new Date(NOW - m * 60_000).toISOString();

  it("normalizeTitle 은 앞뒤 공백·연속 공백·대소문자를 맞춘다", () => {
    expect(normalizeTitle("  Deep   Learning 연구 ")).toBe("deep learning 연구");
  });

  it("10분 안의 같은 종류·제목·조건이면 찾는다(조건 키 순서·빈 값 무시)", () => {
    const list = [
      paperEntry(ID1, { title: "딥러닝  연구", params: { grade: "KCI 등재", x: 1 }, createdAt: minutesAgo(5) }),
    ];
    const hit = findRecentDuplicate(
      list,
      { kind: "paper", title: "딥러닝 연구 ", params: { x: 1, grade: "KCI 등재", empty: "" } },
      NOW,
    );
    expect(hit?.id).toBe(ID1);
  });

  it("10분이 지났으면 새로 만든다 — 최근 갱신 시각 기준", () => {
    const old = [bookEntry(ID1, { createdAt: minutesAgo(30), updatedAt: minutesAgo(11) })];
    expect(findRecentDuplicate(old, { kind: "book", title: "한국 경제", params: {} }, NOW)).toBeNull();
    const touched = [bookEntry(ID1, { createdAt: minutesAgo(30), updatedAt: minutesAgo(2) })];
    expect(findRecentDuplicate(touched, { kind: "book", title: "한국 경제", params: {} }, NOW)?.id).toBe(ID1);
  });

  it("조건·종류가 다르거나 딥리서치면 찾지 않는다", () => {
    const list = [
      paperEntry(ID1, { params: { grade: "KCI 등재" }, createdAt: minutesAgo(1) }),
      researchEntry(ID2, { createdAt: minutesAgo(1) }),
    ];
    expect(findRecentDuplicate(list, { kind: "paper", title: "딥러닝 자연어 처리", params: {} }, NOW)).toBeNull();
    expect(
      findRecentDuplicate(list, { kind: "book", title: "딥러닝 자연어 처리", params: { grade: "KCI 등재" } }, NOW),
    ).toBeNull();
    expect(findRecentDuplicate(list, { kind: "research", title: "국내 AI 규제 연구 동향", params: {} }, NOW)).toBeNull();
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `cd frontend && npx vitest run tests/unit/historyLegacy.test.ts`
Expected: FAIL — 17개 모두 실패. `convertLegacy`·`migrateLegacy` 등이 아직 없어 `... is not a function` 류 TypeError(상수는 `undefined` 라 키 비교도 어긋난다).

- [ ] **Step 3: 구현 — import 추가**

`frontend/utils/historyStore.ts` 맨 위 `import type { ... } from "~/types/history";` 블록을 아래처럼 바꾼다(`LegacyHistoryEntry` 추가, 축약 함수 import 한 줄 추가).

```ts
import type {
  BookAi,
  BookSnapshot,
  DistributiveOmit,
  HistoryEntry,
  HistoryImportItem,
  HistoryImportOut,
  HistoryItemDetail,
  HistoryItemIn,
  HistoryItemOut,
  HistoryKind,
  HistoryListOut,
  HistoryPatch,
  LegacyHistoryEntry,
  PaperAi,
  PaperSnapshot,
} from "~/types/history";
import { slimBookResult, slimPaperResult } from "./historySnapshot";
```

- [ ] **Step 4: 구현 — 파일 끝에 추가**

`createHybridStore` 함수 뒤(파일 끝)에 그대로 붙인다.

```ts
export const LEGACY_HISTORY_KEY = "skx_search_history";
export const LEGACY_BACKUP_KEY = "skx_search_history_backup_v1";
export const LEGACY_MIGRATED_KEY = "skx_history_v1_migrated";
export const V1_MAP_KEY = "skx_history_v1_map";
export const DEDUPE_WINDOW_MS = 10 * 60 * 1000;

const IMPORT_BATCH = 100;

export function normalizeTitle(title: string): string {
  return title.normalize("NFC").trim().replace(/\s+/g, " ").toLowerCase();
}

function paramsKey(params: Record<string, unknown> | undefined): string {
  const entries = Object.entries(params ?? {})
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return JSON.stringify(entries);
}

export function findRecentDuplicate(
  list: readonly HistoryEntry[],
  input: { kind: HistoryKind; title: string; params?: Record<string, unknown> },
  nowMs: number,
  windowMs = DEDUPE_WINDOW_MS,
): HistoryEntry | null {
  if (input.kind === "research") return null;
  const title = normalizeTitle(input.title);
  const key = paramsKey(input.params);
  return (
    list.find((e) => {
      if (e.kind !== input.kind || normalizeTitle(e.title) !== title || paramsKey(e.params) !== key) return false;
      const at = Date.parse(e.updatedAt ?? e.createdAt);
      return !Number.isNaN(at) && nowMs - at <= windowMs;
    }) ?? null
  );
}

export function readV1Map(storage: Storage | null): Record<string, string> {
  if (!storage) return {};
  try {
    const parsed: unknown = JSON.parse(storage.getItem(V1_MAP_KEY) ?? "{}");
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter((kv): kv is [string, string] => typeof kv[1] === "string"),
    );
  } catch {
    return {};
  }
}

function legacyTime(ts: unknown): string | null {
  if (typeof ts !== "number" && typeof ts !== "string") return null;
  const value = typeof ts === "string" && /^\d+$/.test(ts) ? Number(ts) : ts;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function legacyAi(kind: "book" | "paper", raw: unknown): BookAi | PaperAi | null {
  if (typeof raw !== "string" || !raw.trim()) return null;
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = null;
  }
  const obj =
    typeof parsed === "object" && parsed !== null && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  if (kind === "book") {
    return obj
      ? { intro: typeof obj.intro === "string" ? obj.intro : "", items: Array.isArray(obj.items) ? obj.items : [] }
      : { intro: raw, items: [] };
  }
  return obj
    ? { text: typeof obj.text === "string" ? obj.text : "", refs: Array.isArray(obj.refs) ? obj.refs : [] }
    : { text: raw, refs: [] };
}

export function convertLegacy(v1: LegacyHistoryEntry[]): HistoryImportItem[] {
  const seen = new Set<string>();
  const out: HistoryImportItem[] = [];
  // 브라우저 저장소에서 온 값이라 타입을 믿지 않고 한 칸씩 확인한다
  for (const raw of v1 as unknown[]) {
    if (typeof raw !== "object" || raw === null) continue;
    const { id, type, query, timestamp, result, aiSummary } = raw as Partial<LegacyHistoryEntry>;
    if ((type !== "book" && type !== "paper") || typeof query !== "string" || !query.trim()) continue;
    const legacyId = String(id ?? "");
    if (!legacyId || seen.has(legacyId)) continue;
    seen.add(legacyId);
    out.push({
      legacy_id: legacyId,
      kind: type,
      title: query.trim().slice(0, 500),
      params: {},
      snapshot: type === "book" ? slimBookResult(result) : slimPaperResult(result),
      ai: legacyAi(type, aiSummary),
      ref_id: null,
      created_at: legacyTime(timestamp) ?? legacyTime(legacyId),
    });
  }
  return out;
}

export async function migrateLegacy(
  storage: Storage | null,
  server: Pick<ServerHistoryStore, "importItems">,
): Promise<{ imported: number } | null> {
  if (!storage) return null;
  let raw: string | null;
  try {
    if (storage.getItem(LEGACY_MIGRATED_KEY)) return null;
    raw = storage.getItem(LEGACY_HISTORY_KEY);
  } catch {
    return null;
  }
  if (raw === null) return null;

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = null;
  }
  const items = Array.isArray(parsed) ? convertLegacy(parsed as LegacyHistoryEntry[]) : [];

  const idMap = readV1Map(storage);
  let imported = 0;
  try {
    for (let i = 0; i < items.length; i += IMPORT_BATCH) {
      const res = await server.importItems(items.slice(i, i + IMPORT_BATCH));
      imported += res.imported;
      Object.assign(idMap, res.id_map);
    }
  } catch {
    // 서버가 받기 전에는 v1 을 건드리지 않는다 — 다음 로드에서 다시 시도한다
    return null;
  }

  try {
    storage.setItem(V1_MAP_KEY, JSON.stringify(idMap));
  } catch {
    // 대응표를 못 남기면 옛 ?restore= 주소만 새 id 를 못 찾는다 — 기록 자체는 이미 서버에 있다
  }
  try {
    const backupKey =
      storage.getItem(LEGACY_BACKUP_KEY) === null ? LEGACY_BACKUP_KEY : `${LEGACY_BACKUP_KEY}_${Date.now()}`;
    storage.setItem(backupKey, raw);
    storage.removeItem(LEGACY_HISTORY_KEY);
  } catch {
    // 사본 둘 자리가 없다 — 원본을 그대로 백업으로 남기고 다시 올리지 않게 표시만 한다
    try {
      storage.setItem(LEGACY_MIGRATED_KEY, "1");
    } catch {
      // 표시도 못 하면 다음 로드에 한 번 더 올린다 — 서버가 같은 id 를 건너뛴다
    }
  }
  return { imported };
}
```

- [ ] **Step 5: 실행해 통과 확인**

Run: `cd frontend && npx vitest run tests/unit/historyLegacy.test.ts`
Expected: `Tests  17 passed (17)`

Run: `cd frontend && npm test`
Expected: `Tests  71 passed (71)`

- [ ] **Step 6: 커밋**

```
git add frontend/utils/historyStore.ts frontend/tests/unit/historyLegacy.test.ts
git commit -m "[Feat] round04b — v1 기록 서버 이전(원본 백업 보존)과 10분 중복 판정"
```

---

### Task 19: 기록 URL 규칙 한 곳으로

**Files:**
- Create: `frontend/utils/historyRoute.ts`
- Test: `frontend/tests/unit/historyRoute.test.ts`

규칙(spec §4-6): 도서 `/?h=&q=`, 논문 `/papers?h=&q=&grade=`, 딥리서치 `/research/<job_id>`. `restore` 는 `h` 의 별칭(h 가 우선). v1 숫자 id 는 대응표로 새 id 를 찾고, 못 찾으면 버린다. UUID 형식이 아닌 `h` 는 버린다 — 서버 경로에 그대로 넣지 않게. 사이드바 탭은 경로로, 강조 항목은 경로(딥리서치) 또는 `h` 로 정한다.

- [ ] **Step 1: 실패하는 테스트**

```ts
// frontend/tests/unit/historyRoute.test.ts
import { describe, expect, it } from "vitest";
import { activeIdFor, activeKindForPath, readHistoryQuery, routeFor } from "~/utils/historyRoute";
import { ID1, ID2, bookEntry, paperEntry, researchEntry } from "./helpers/fakeHistory";

const MIXED = "AbCdEf01-2345-4789-abcd-0123456789ab";

describe("routeFor", () => {
  it("도서는 / 에 h·q 를 싣는다", () => {
    expect(routeFor(bookEntry(ID1))).toEqual({ path: "/", query: { h: ID1, q: "한국 경제" } });
  });

  it("논문은 /papers 에 등재구분이 있으면 grade 까지 싣는다", () => {
    expect(routeFor(paperEntry(ID1, { params: { grade: "KCI 등재" } }))).toEqual({
      path: "/papers",
      query: { h: ID1, q: "딥러닝 자연어 처리", grade: "KCI 등재" },
    });
    expect(routeFor(paperEntry(ID1))).toEqual({ path: "/papers", query: { h: ID1, q: "딥러닝 자연어 처리" } });
  });

  it("딥리서치는 잡 주소로 간다", () => {
    expect(routeFor(researchEntry(ID2))).toEqual({ path: `/research/${ID2}` });
  });
});

describe("readHistoryQuery", () => {
  it("h 와 q·grade 를 읽는다", () => {
    expect(readHistoryQuery({ h: ID1, q: " 경제 ", grade: "KCI 등재" })).toEqual({
      h: ID1,
      q: "경제",
      grade: "KCI 등재",
    });
  });

  it("옛 restore 를 h 의 별칭으로 받되 h 가 우선이다", () => {
    expect(readHistoryQuery({ restore: ID1 })).toEqual({ h: ID1 });
    expect(readHistoryQuery({ h: ID2, restore: ID1 })).toEqual({ h: ID2 });
  });

  it("v1 숫자 id 는 대응표로 새 id 를 찾고 못 찾으면 버린다", () => {
    expect(readHistoryQuery({ restore: "1727000000000" }, { "1727000000000": ID1 })).toEqual({ h: ID1 });
    expect(readHistoryQuery({ restore: "1727000000000", q: "경제" }, {})).toEqual({ q: "경제" });
  });

  it("형식이 틀린 id·빈 값은 버리고 배열은 첫 값을 쓴다", () => {
    expect(readHistoryQuery({ h: "../../admin", q: "   " })).toEqual({});
    expect(readHistoryQuery({ h: [ID1, ID2], q: ["a", "b"] })).toEqual({ h: ID1, q: "a" });
  });

  it("대문자 id 는 소문자로 맞춘다", () => {
    expect(readHistoryQuery({ h: MIXED })).toEqual({ h: MIXED.toLowerCase() });
  });
});

describe("activeKindForPath", () => {
  it("경로로 사이드바 탭을 정한다", () => {
    expect(activeKindForPath("/")).toBe("book");
    expect(activeKindForPath("/books/CNTS-1")).toBe("book");
    expect(activeKindForPath("/recommend/3")).toBe("book");
    expect(activeKindForPath("/papers")).toBe("paper");
    expect(activeKindForPath("/papers/CNTS-2")).toBe("paper");
    expect(activeKindForPath(`/research/${ID1}`)).toBe("research");
    expect(activeKindForPath("/papersX")).toBe("book");
  });
});

describe("activeIdFor", () => {
  it("딥리서치는 경로의 잡 id, 나머지는 쿼리의 h", () => {
    expect(activeIdFor(`/research/${ID1}`, {})).toBe(ID1);
    expect(activeIdFor("/papers/CNTS-2", { h: ID2 })).toBe(ID2);
    expect(activeIdFor("/", {})).toBeNull();
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `cd frontend && npx vitest run tests/unit/historyRoute.test.ts`
Expected: FAIL — `~/utils/historyRoute` 를 불러오지 못해 수집 단계에서 실패.

- [ ] **Step 3: 구현**

```ts
// frontend/utils/historyRoute.ts
import type { HistoryEntry, HistoryKind } from "~/types/history";

export interface HistoryRoute {
  path: string;
  query?: Record<string, string>;
}

export interface HistoryQuery {
  h?: string;
  q?: string;
  grade?: string;
}

// 서버 기록 id 는 브라우저 v4 · 잡 id v4 · v1 이전분 uuid5 가 섞여 있어 버전을 가리지 않는다
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const V1_ID = /^\d{10,16}$/;

function first(v: unknown): string | undefined {
  const s = Array.isArray(v) ? v[0] : v;
  return typeof s === "string" && s.trim() ? s.trim() : undefined;
}

export function routeFor(entry: HistoryEntry): HistoryRoute {
  if (entry.kind === "research") return { path: `/research/${entry.refId || entry.id}` };
  const query: Record<string, string> = { h: entry.id, q: entry.title };
  if (entry.kind === "book") return { path: "/", query };
  const grade = entry.params?.grade;
  if (typeof grade === "string" && grade) query.grade = grade;
  return { path: "/papers", query };
}

export function readHistoryQuery(
  query: Record<string, unknown>,
  v1Map: Record<string, string> = {},
): HistoryQuery {
  const out: HistoryQuery = {};
  const raw = first(query.h) ?? first(query.restore);
  if (raw && UUID.test(raw)) out.h = raw.toLowerCase();
  else if (raw && V1_ID.test(raw) && v1Map[raw]) out.h = v1Map[raw];
  const q = first(query.q);
  if (q) out.q = q;
  const grade = first(query.grade);
  if (grade) out.grade = grade;
  return out;
}

export function activeKindForPath(path: string): HistoryKind {
  if (path === "/research" || path.startsWith("/research/")) return "research";
  if (path === "/papers" || path.startsWith("/papers/")) return "paper";
  return "book";
}

export function activeIdFor(
  path: string,
  query: Record<string, unknown>,
  v1Map: Record<string, string> = {},
): string | null {
  const match = /^\/research\/([^/?#]+)/.exec(path);
  if (match) return decodeURIComponent(match[1]!);
  return readHistoryQuery(query, v1Map).h ?? null;
}
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `cd frontend && npx vitest run tests/unit/historyRoute.test.ts`
Expected: `Tests  10 passed (10)`

Run: `cd frontend && npm test`
Expected: `Tests  81 passed (81)`

- [ ] **Step 5: 커밋**

```
git add frontend/utils/historyRoute.ts frontend/tests/unit/historyRoute.test.ts
git commit -m "[Feat] round04b — 기록 URL 규칙 한 곳으로(?h=·restore 별칭·v1 id)"
```

---

### Task 20: useHistory — 싱글톤 상태·탭 동기화·중복 병합·딥리서치 기록

**Files:**
- Create: `frontend/utils/historyState.ts` (목록 상태 — Vue 반응성만 쓰는 순수 부분)
- Create: `frontend/composables/useHistory.ts` (앱 싱글톤·창 이벤트·v1 이전 트리거)
- Test: `frontend/tests/unit/historyState.test.ts`

`useHistory` 의 버그가 가장 잘 숨는 곳(중복 병합·실패 시 목록 정리·딥리서치 upsert)은 Nuxt 없이 돌도록 `createHistoryState` 로 떼어 테스트한다. 컴포저블은 저장소 조립·창 이벤트만 한다.

- 목록에는 snapshot·ai 를 두지 않는다(반응형 목록을 가볍게). 복원은 `get(id)` 로 상세를 읽는다.
- `add` 는 저장이 거절(4xx)돼도 던지지 않는다 — 검색 화면을 깨지 않고, 목록에서만 뺀다. 페이지는 돌려받은 id 로 URL 을 만든다(없는 id 면 복원이 `q` 재검색으로 물러선다).
- 413(축약 결과가 서버 상한 200KB 초과)이면 snapshot 없이 한 번 더 저장한다. 4xx 는 보낼 편지함이 다시 보내지 않으므로, 그대로 두면 그 검색 기록이 통째로 사라진다(논문 20건 × 참고문헌 30개면 상한 근처다).
- `upsertResearch` 는 목록에 있으면 요청 없이 돌려주고, 없으면 `get` → 없으면 `PUT`. 남의 잡(서버 404)이면 `null` — 보고서 페이지는 그대로 열리고 사이드바에만 없다(D7).
- 탭 동기화: 변경 뒤 `skx_history_ping` 을 바꿔 다른 탭의 `storage` 이벤트를 깨운다(값이 같으면 이벤트가 안 온다). 받은 탭은 300ms 모아 목록을 다시 읽는다. `online` 복귀도 같은 길로 outbox 를 보낸다.

- [ ] **Step 1: 실패하는 테스트**

```ts
// frontend/tests/unit/historyState.test.ts
import { describe, expect, it } from "vitest";
import { createHistoryState } from "~/utils/historyState";
import { ID1, ID2, ID3, bookEntry, fakeServer, httpError, paperEntry, researchEntry } from "./helpers/fakeHistory";

const NOW = Date.parse("2026-09-26T03:00:00.000Z");
const minutesAgo = (m: number) => new Date(NOW - m * 60_000).toISOString();
const snap = { query: "한국 경제", books: [] };

function setup() {
  const store = fakeServer();
  const ids = [ID1, ID2, ID3];
  let changes = 0;
  const state = createHistoryState(() => store, {
    now: () => NOW,
    genId: () => ids.shift()!,
    onChange: () => {
      changes += 1;
    },
    warn: () => {},
  });
  return { store, state, changes: () => changes };
}

describe("createHistoryState", () => {
  it("refresh 는 종류별 목록을 채우고 무거운 필드는 목록에 두지 않는다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1, { snapshot: snap }));
    store.rows.set(ID2, researchEntry(ID2, { research: { status: "running", stage: "planned" } }));
    await state.refresh();
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1]);
    expect(state.byKind("book").value[0]).not.toHaveProperty("snapshot");
    expect(state.byKind("research").value[0]).toMatchObject({ research: { status: "running" } });
  });

  it("add 는 새 id 로 맨 위에 넣고 서버에 저장한다", async () => {
    const { store, state, changes } = setup();
    store.rows.set(ID3, bookEntry(ID3, { title: "다른 검색", createdAt: minutesAgo(1) }));
    await state.refresh();
    const saved = await state.add({ kind: "book", title: "한국 경제", params: {}, snapshot: snap });
    expect(saved.id).toBe(ID1);
    expect(store.rows.get(ID1)).toMatchObject({
      title: "한국 경제",
      snapshot: snap,
      createdAt: new Date(NOW).toISOString(),
    });
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1, ID3]);
    expect(changes()).toBe(1);
  });

  it("10분 안의 같은 검색은 새로 만들지 않고 기존 기록을 갱신해 맨 위로 올린다", async () => {
    const { store, state } = setup();
    store.rows.set(ID2, paperEntry(ID2, { title: "다른 것", createdAt: minutesAgo(1) }));
    store.rows.set(ID3, paperEntry(ID3, { title: "딥러닝", createdAt: minutesAgo(5) }));
    await state.refresh();
    expect(state.byKind("paper").value.map((e) => e.id)).toEqual([ID2, ID3]);
    const saved = await state.add({ kind: "paper", title: " 딥러닝 ", params: {}, snapshot: { query: "딥러닝", books: [] } });
    expect(saved.id).toBe(ID3);
    expect(store.put).toHaveBeenCalledWith(
      expect.objectContaining({ id: ID3, createdAt: minutesAgo(5), updatedAt: new Date(NOW).toISOString() }),
    );
    expect(state.byKind("paper").value.map((e) => e.id)).toEqual([ID3, ID2]);
  });

  it("10분이 지난 같은 검색은 새 기록이다", async () => {
    const { store, state } = setup();
    store.rows.set(ID3, bookEntry(ID3, { createdAt: minutesAgo(11) }));
    await state.refresh();
    expect((await state.add({ kind: "book", title: "한국 경제", params: {} })).id).toBe(ID1);
  });

  it("서버가 거절하면 목록에서 빼되 던지지 않고 항목을 돌려준다", async () => {
    const { store, state } = setup();
    store.put.mockRejectedValueOnce(httpError(413));
    const entry = await state.add({ kind: "book", title: "한국 경제", params: {} });
    expect(entry.id).toBe(ID1);
    expect(state.entries.value).toEqual([]);
  });

  it("축약 결과가 커서 413 이면 결과 없이 다시 저장한다", async () => {
    const { store, state } = setup();
    store.put.mockRejectedValueOnce(httpError(413));
    const saved = await state.add({ kind: "book", title: "한국 경제", params: {}, snapshot: snap });
    expect(saved.id).toBe(ID1);
    expect(store.put).toHaveBeenCalledTimes(2);
    expect(store.rows.get(ID1)).not.toHaveProperty("snapshot");
    expect(state.byKind("book").value.map((e) => e.id)).toEqual([ID1]);
  });

  it("patch 대상이 사라졌으면 목록에서 정리한다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1));
    await state.refresh();
    store.rows.delete(ID1);
    expect(await state.patch(ID1, { ai: { intro: "", items: [] } })).toBeNull();
    expect(state.entries.value).toEqual([]);
  });

  it("remove·clear 는 목록에서 먼저 빼고 서버에 알린다", async () => {
    const { store, state } = setup();
    store.rows.set(ID1, bookEntry(ID1));
    store.rows.set(ID2, paperEntry(ID2));
    store.rows.set(ID3, paperEntry(ID3, { title: "다른 논문" }));
    await state.refresh();
    await state.remove(ID1);
    expect(store.remove).toHaveBeenCalledWith(ID1);
    await state.clear("paper");
    expect(store.clear).toHaveBeenCalledWith("paper");
    expect(state.entries.value).toEqual([]);
  });

  it("upsertResearch 는 이미 목록에 있으면 서버에 묻지 않는다", async () => {
    const { store, state } = setup();
    store.rows.set(ID2, researchEntry(ID2));
    await state.refresh();
    store.get.mockClear();
    store.put.mockClear();
    expect(await state.upsertResearch(ID2, "질문")).toMatchObject({ id: ID2 });
    expect(store.get).not.toHaveBeenCalled();
    expect(store.put).not.toHaveBeenCalled();
  });

  it("upsertResearch 는 없으면 잡 id 로 딥리서치 기록을 만든다", async () => {
    const { state } = setup();
    const saved = await state.upsertResearch(ID2, "  국내 AI 규제 연구 동향  ");
    expect(saved).toMatchObject({ id: ID2, kind: "research", refId: ID2, title: "국내 AI 규제 연구 동향" });
    expect(state.byKind("research").value.map((e) => e.id)).toEqual([ID2]);
  });

  it("upsertResearch 는 남의 잡이라 거절되면 null 을 돌려준다", async () => {
    const { store, state } = setup();
    store.put.mockRejectedValueOnce(httpError(404));
    expect(await state.upsertResearch(ID2, "질문")).toBeNull();
    expect(state.entries.value).toEqual([]);
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `cd frontend && npx vitest run tests/unit/historyState.test.ts`
Expected: FAIL — `~/utils/historyState` 를 불러오지 못해 수집 단계에서 실패.

- [ ] **Step 3: `utils/historyState.ts`**

```ts
// frontend/utils/historyState.ts
import { computed, ref, type ComputedRef, type Ref } from "vue";
import type {
  HistoryEntry,
  HistoryEntryInput,
  HistoryKind,
  HistoryPatch,
  ResearchEntry,
} from "~/types/history";
import { HISTORY_PAGE_SIZE, errorStatus, findRecentDuplicate, type HybridHistoryStore } from "./historyStore";

const KINDS: HistoryKind[] = ["book", "paper", "research"];

export interface HistoryStateOptions {
  genId: () => string;
  now?: () => number;
  onChange?: () => void;
  warn?: (message: string, err: unknown) => void;
}

export interface HistoryState {
  entries: Ref<HistoryEntry[]>;
  byKind(kind: HistoryKind): ComputedRef<HistoryEntry[]>;
  refresh(kind?: HistoryKind): Promise<void>;
  add(input: HistoryEntryInput): Promise<HistoryEntry>;
  patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(kind: HistoryKind): Promise<void>;
  get(id: string): Promise<HistoryEntry | null>;
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
}

/** 반응형 목록에는 무거운 필드를 두지 않는다 — 복원은 get(id) 로 상세를 읽는다 */
export function toListItem(entry: HistoryEntry): HistoryEntry {
  if (entry.kind === "research") return entry;
  const item = { ...entry };
  delete item.snapshot;
  delete item.ai;
  return item;
}

export function createHistoryState(store: () => HybridHistoryStore, opts: HistoryStateOptions): HistoryState {
  const now = opts.now ?? Date.now;
  const warn = opts.warn ?? ((message: string, err: unknown) => console.warn(`[history] ${message}`, err));
  const changed = () => opts.onChange?.();
  const entries = ref<HistoryEntry[]>([]);
  const kindViews = new Map<HistoryKind, ComputedRef<HistoryEntry[]>>();

  function place(entry: HistoryEntry, toTop: boolean): void {
    const item = toListItem(entry);
    const idx = entries.value.findIndex((e) => e.id === entry.id);
    if (toTop || idx < 0) {
      entries.value = [item, ...entries.value.filter((e) => e.id !== entry.id)];
      return;
    }
    const next = entries.value.slice();
    next[idx] = item;
    entries.value = next;
  }

  function drop(id: string): void {
    entries.value = entries.value.filter((e) => e.id !== id);
  }

  function byKind(kind: HistoryKind): ComputedRef<HistoryEntry[]> {
    let view = kindViews.get(kind);
    if (!view) {
      view = computed(() => entries.value.filter((e) => e.kind === kind));
      kindViews.set(kind, view);
    }
    return view;
  }

  async function refresh(kind?: HistoryKind): Promise<void> {
    const kinds = kind ? [kind] : KINDS;
    await Promise.all(
      kinds.map(async (k) => {
        try {
          const { items } = await store().list(k, { limit: HISTORY_PAGE_SIZE });
          entries.value = [...entries.value.filter((e) => e.kind !== k), ...items.map(toListItem)];
        } catch (e) {
          warn("목록을 읽지 못했다", e);
        }
      }),
    );
  }

  // 축약 결과가 서버 상한(200KB)을 넘으면 413 이다. 4xx 는 보낼 편지함이 다시 보내지 않아
  // 그대로 두면 기록이 사라진다 — 결과 없이라도 남긴다(복원은 q 재검색으로 물러선다).
  async function putEntry(entry: HistoryEntry): Promise<HistoryEntry> {
    try {
      return await store().put(entry);
    } catch (e) {
      if (errorStatus(e) !== 413 || entry.kind === "research" || !entry.snapshot) throw e;
      const lighter = { ...entry };
      delete lighter.snapshot;
      return store().put(lighter);
    }
  }

  async function add(input: HistoryEntryInput): Promise<HistoryEntry> {
    const nowMs = now();
    const iso = new Date(nowMs).toISOString();
    const dup = findRecentDuplicate(entries.value, input, nowMs);
    const entry = {
      ...input,
      id: dup?.id ?? opts.genId(),
      createdAt: dup?.createdAt ?? iso,
      updatedAt: iso,
    } as HistoryEntry;
    place(entry, true);
    try {
      const saved = await putEntry(entry);
      place(saved, true);
      changed();
      return saved;
    } catch (e) {
      warn("기록을 저장하지 못했다", e);
      if (!dup) drop(entry.id);
      return entry;
    }
  }

  async function patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null> {
    try {
      const saved = await store().patch(id, partial);
      if (!saved) drop(id);
      else if (entries.value.some((e) => e.id === id)) place(saved, false);
      changed();
      return saved;
    } catch (e) {
      warn("기록을 고치지 못했다", e);
      return null;
    }
  }

  async function remove(id: string): Promise<void> {
    drop(id);
    try {
      await store().remove(id);
      changed();
    } catch (e) {
      warn("기록을 지우지 못했다", e);
    }
  }

  async function clear(kind: HistoryKind): Promise<void> {
    entries.value = entries.value.filter((e) => e.kind !== kind);
    try {
      await store().clear(kind);
      changed();
    } catch (e) {
      warn("기록을 지우지 못했다", e);
    }
  }

  async function get(id: string): Promise<HistoryEntry | null> {
    try {
      return await store().get(id);
    } catch (e) {
      warn("기록을 읽지 못했다", e);
      return null;
    }
  }

  async function upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null> {
    const known = entries.value.find((e) => e.id === jobId);
    if (known) return known;
    const found = await get(jobId);
    if (found) {
      place(found, false);
      return found;
    }
    const iso = new Date(now()).toISOString();
    const entry: ResearchEntry = {
      id: jobId,
      kind: "research",
      title: question.trim().slice(0, 500),
      createdAt: iso,
      updatedAt: iso,
      params: {},
      refId: jobId,
    };
    try {
      const saved = await store().put(entry);
      place(saved, true);
      changed();
      return saved;
    } catch (e) {
      // 다른 브라우저가 만든 잡이면 서버가 404 로 막는다 — 보고서는 열리고 사이드바에만 없다
      warn("딥리서치 기록을 만들지 못했다", e);
      return null;
    }
  }

  return { entries, byKind, refresh, add, patch, remove, clear, get, upsertResearch };
}
```

- [ ] **Step 4: 실행해 통과 확인**

Run: `cd frontend && npx vitest run tests/unit/historyState.test.ts`
Expected: `Tests  11 passed (11)`

- [ ] **Step 5: `composables/useHistory.ts`**

```ts
// frontend/composables/useHistory.ts
import type { ComputedRef, Ref } from "vue";
import type { HistoryEntry, HistoryEntryInput, HistoryKind, HistoryPatch } from "~/types/history";
import { generateUuidV4, safeLocalStorage } from "~/utils/browserId";
import { createHistoryState, type HistoryState } from "~/utils/historyState";
import {
  HISTORY_PING_KEY,
  createHybridStore,
  createLocalStore,
  createServerStore,
  migrateLegacy,
  type HistoryFetcher,
  type HybridHistoryStore,
  type ServerHistoryStore,
} from "~/utils/historyStore";
import { useApi } from "./useApi";

// 앱 전체가 한 벌을 나눠 쓴다 — 사이드바와 페이지가 같은 목록을 보고, 창 이벤트도 한 번만 건다
let server: ServerHistoryStore | null = null;
let hybrid: HybridHistoryStore | null = null;
let state: HistoryState | null = null;
let loading: Promise<void> | null = null;
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

function stores(): { server: ServerHistoryStore; hybrid: HybridHistoryStore } {
  if (!server || !hybrid) {
    const api = useApi();
    const fetcher: HistoryFetcher = (path, opts) => api(path, opts);
    server = createServerStore(fetcher);
    hybrid = createHybridStore(server, createLocalStore(safeLocalStorage()));
  }
  return { server, hybrid };
}

function ping(): void {
  try {
    window.localStorage.setItem(HISTORY_PING_KEY, `${Date.now()}:${Math.random().toString(36).slice(2)}`);
  } catch {
    // 막힌 저장소 — 다른 탭 동기화만 포기한다
  }
}

function historyState(): HistoryState {
  if (!state) {
    state = createHistoryState(() => stores().hybrid, { genId: generateUuidV4, onChange: ping });
  }
  return state;
}

function scheduleRefresh(): void {
  if (refreshTimer) clearTimeout(refreshTimer);
  // 다른 탭이 연달아 고칠 때 목록을 한 번만 다시 읽는다
  refreshTimer = setTimeout(() => {
    refreshTimer = null;
    void historyState().refresh();
  }, 300);
}

function load(): Promise<void> {
  if (!import.meta.client) return Promise.resolve();
  if (!loading) {
    loading = (async () => {
      window.addEventListener("storage", (e) => {
        if (e.key === HISTORY_PING_KEY) scheduleRefresh();
      });
      window.addEventListener("online", scheduleRefresh);
      await migrateLegacy(safeLocalStorage(), stores().server);
      await historyState().refresh();
    })();
  }
  return loading;
}

export interface UseHistory {
  entries: Ref<HistoryEntry[]>;
  byKind(kind: HistoryKind): ComputedRef<HistoryEntry[]>;
  load(): Promise<void>;
  refresh(kind?: HistoryKind): Promise<void>;
  add(input: HistoryEntryInput): Promise<HistoryEntry>;
  patch(id: string, partial: HistoryPatch): Promise<HistoryEntry | null>;
  remove(id: string): Promise<void>;
  clear(kind: HistoryKind): Promise<void>;
  get(id: string): Promise<HistoryEntry | null>;
  upsertResearch(jobId: string, question: string): Promise<HistoryEntry | null>;
}

export function useHistory(): UseHistory {
  const s = historyState();
  return {
    entries: s.entries,
    byKind: s.byKind,
    load,
    refresh: (kind) => (import.meta.client ? s.refresh(kind) : Promise.resolve()),
    add: s.add,
    patch: s.patch,
    remove: s.remove,
    clear: s.clear,
    get: s.get,
    upsertResearch: s.upsertResearch,
  };
}
```

- [ ] **Step 6: 전체 테스트·빌드 확인**

Run: `cd frontend && npm test`
Expected: `Tests  92 passed (92)`

Run: `cd frontend && npm run build`
Expected: 오류 없이 끝나고 `.output/` 이 생긴다(아직 아무 화면도 `useHistory` 를 부르지 않는다 — 자동 import·모듈 해석만 확인).

- [ ] **Step 7: 커밋**

```
git add frontend/utils/historyState.ts frontend/composables/useHistory.ts frontend/tests/unit/historyState.test.ts
git commit -m "[Feat] round04b — useHistory 싱글톤·탭 동기화·중복 병합·딥리서치 기록"
```

---

### Task 21: 사이드바 재작성

**Files:**
- Modify(전체 교체): `frontend/components/AppSidebar.vue` (현재 1~133행)

사이드바가 `useHistory()` 를 직접 읽고 `routeFor` 로 직접 이동한다 — 페이지가 넘기던 `bookHistory`/`paperHistory`/`activeId`/`defaultTab` props 와 `@restore` 를 없앤다(M1·M6). 탭·강조는 라우트에서 정한다. 접힘은 `useState` 로 페이지 사이에 유지하고, 논문 채팅 때문에 접혔다가 채팅이 닫히면 원래 상태로 되돌린다. 목록은 `<ClientOnly>` 안에서만 그린다(하이드레이션 불일치 방지). 새 요소의 스타일은 `style_skovix.css` 끝에 덧붙이지 않고(충돌 위험 최고, D10) 이 컴포넌트의 scoped 블록에 둔다.

컴포넌트라 단위 테스트는 없다. 순수 로직(`routeFor`·`activeIdFor`·`activeKindForPath`)은 Task 19 에서 검증했다.

- [ ] **Step 1: 파일 교체**

```vue
<!-- frontend/components/AppSidebar.vue -->
<template>
  <aside :class="['skx-lnb', !open && 'is-lnb-collapsed']">
    <!-- 접힌 상태에서 펼치기 버튼 -->
    <button
      type="button"
      class="skx-lnb__expand"
      aria-label="사이드바 열기"
      @click="open = true"
    >
      <img src="/img/ico-arrow.svg" alt="" />
    </button>

    <!-- 로고 + 접기 버튼 -->
    <div class="skx-lnb__logo">
      <a class="skx-logo" href="/" aria-label="SKOVIX 메인으로 이동">
        <img class="skx-logo__mark" src="/img/logo-mark.svg" alt="" />
        <img class="skx-logo__word" src="/img/logo-word.svg" alt="SKOVIX" />
      </a>
      <button
        type="button"
        class="skx-icon-btn"
        aria-label="사이드바 접기"
        @click="open = false"
      >
        <img src="/img/ico-collapse.svg" alt="" />
      </button>
    </div>

    <!-- 새 채팅 -->
    <!-- <div class="skx-lnb__new">
      <button type="button" class="skx-newchat" @click="navigateTo('/')">
        <span class="skx-newchat__icon"><img src="/img/ico-newchat.svg" alt=""></span>
        <span class="skx-newchat__label">새 채팅</span>
      </button>
    </div> -->

    <!-- 메뉴 -->
    <nav class="skx-lnb__menu" aria-label="주요 메뉴">
      <!-- <button type="button" class="skx-menu-item" @click="emit('cart')">
        <span class="skx-menu-item__icon"
          ><img src="/img/ico-cart-menu.svg" alt=""
        /></span>
        <span class="skx-menu-item__label">대출 장바구니</span>
      </button> -->
      <button type="button" class="skx-menu-item" @click="emit('save')">
        <span class="skx-menu-item__icon"
          ><img src="/img/ico-bookmark-menu.svg" alt=""
        /></span>
        <span class="skx-menu-item__label">저장목록</span>
      </button>
    </nav>

    <!-- 검색기록 -->
    <div class="skx-history">
      <div class="skx-history__head">
        <p class="skx-history__title">검색기록</p>
        <ClientOnly>
          <button
            v-if="activeList.length"
            type="button"
            class="skx-history__clear"
            @click="confirmOpen = true"
          >
            전체 삭제
          </button>
        </ClientOnly>
      </div>
      <div class="skx-history__tabs" role="tablist" aria-label="검색기록 종류">
        <button
          v-for="t in TABS"
          :key="t.kind"
          type="button"
          role="tab"
          :aria-selected="historyTab === t.kind"
          :class="['skx-history__tab', historyTab === t.kind && 'is-active']"
          @click="selectTab(t.kind)"
        >
          {{ t.label }}
        </button>
      </div>

      <div v-if="confirmOpen" class="skx-history__confirm" role="alertdialog" aria-live="assertive">
        <p class="skx-history__confirm-text">{{ CLEAR_TEXT[historyTab] }}</p>
        <div class="skx-history__confirm-actions">
          <button type="button" class="skx-history__confirm-btn is-danger" @click="clearTab">
            지우기
          </button>
          <button type="button" class="skx-history__confirm-btn" @click="confirmOpen = false">
            취소
          </button>
        </div>
      </div>

      <ClientOnly>
        <p v-if="!activeList.length" class="skx-history__empty">{{ EMPTY_TEXT[historyTab] }}</p>
        <ul v-else class="skx-history__list">
          <li v-for="h in activeList" :key="h.id" class="skx-history__row">
            <button
              type="button"
              :class="['skx-history-item', h.id === activeId && 'is-active']"
              :aria-current="h.id === activeId ? 'page' : undefined"
              @click="go(h)"
            >
              <span class="skx-history-item__query">{{ h.title }}</span>
              <span class="skx-history-item__meta">
                <span
                  v-if="h.kind === 'research'"
                  :class="['skx-history-badge', `is-${badgeOf(h).tone}`]"
                  >{{ badgeOf(h).label }}</span
                >
                <span class="skx-history-item__time">{{ formatTime(h.updatedAt ?? h.createdAt) }}</span>
              </span>
            </button>
            <button
              type="button"
              class="skx-history-item__del"
              :aria-label="`'${h.title}' 기록 삭제`"
              @click="remove(h.id)"
            >
              <img src="/img/ico-delete.svg" alt="" />
            </button>
          </li>
        </ul>
      </ClientOnly>
    </div>

    <!-- 프로필 -->
    <div class="skx-profile">
      <img class="skx-profile__avatar" src="/img/ico-avatar.svg" alt="" />
      <span class="skx-profile__name">김랜드</span>
      <button type="button" class="skx-icon-btn" aria-label="설정">
        <img src="/img/ico-settings.svg" alt="" />
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { HistoryEntry, HistoryKind } from "~/types/history";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { readV1Map } from "~/utils/historyStore";
import { activeIdFor, activeKindForPath, routeFor } from "~/utils/historyRoute";

const props = defineProps<{ collapsed?: boolean }>();
const emit = defineEmits<{ cart: []; save: [] }>();

const TABS: Array<{ kind: HistoryKind; label: string }> = [
  { kind: "book", label: "도서" },
  { kind: "paper", label: "논문" },
  { kind: "research", label: "딥리서치" },
];
const EMPTY_TEXT: Record<HistoryKind, string> = {
  book: "도서 검색 기록이 없습니다.",
  paper: "논문 검색 기록이 없습니다.",
  research: "딥리서치 기록이 없습니다. 논문 검색창의 + 에서 시작해 보세요.",
};
const CLEAR_TEXT: Record<HistoryKind, string> = {
  book: "도서 검색 기록을 모두 지울까요?",
  paper: "논문 검색 기록을 모두 지울까요?",
  research: "딥리서치 기록을 모두 지울까요? 보고서 자체는 지워지지 않습니다.",
};
// 이 상태의 딥리서치가 있으면 배지가 바뀔 수 있다 — 승인 대기는 사용자가 움직여야 바뀌므로 뺀다
const LIVE_STATUSES = new Set(["created", "planning", "approved", "queued", "running"]);
const POLL_MS = 30_000;

const route = useRoute();
const router = useRouter();
const history = useHistory();

const open = useState<boolean>("skx:lnb-open", () => true);
const historyTab = ref<HistoryKind>(activeKindForPath(route.path));
const confirmOpen = ref(false);
const v1Map = ref<Record<string, string>>({});

const activeList = computed(() => history.byKind(historyTab.value).value);
const activeId = computed(() => activeIdFor(route.path, route.query, v1Map.value));
const hasLiveResearch = computed(() =>
  history
    .byKind("research")
    .value.some((h) => h.kind === "research" && !!h.research && LIVE_STATUSES.has(h.research.status)),
);

let openBeforeCollapse = true;
watch(
  () => props.collapsed,
  (val, old) => {
    if (val) {
      openBeforeCollapse = open.value;
      open.value = false;
    } else if (old) {
      open.value = openBeforeCollapse;
    }
  },
);

function selectTab(kind: HistoryKind) {
  historyTab.value = kind;
  confirmOpen.value = false;
}

function go(h: HistoryEntry) {
  router.push(routeFor(h));
}

function remove(id: string) {
  void history.remove(id);
}

async function clearTab() {
  confirmOpen.value = false;
  await history.clear(historyTab.value);
}

function badgeOf(h: HistoryEntry): { label: string; tone: string } {
  const status = h.kind === "research" ? h.research?.status : undefined;
  switch (status) {
    case "completed":
      return { label: "완료", tone: "done" };
    case "failed":
      return { label: "실패", tone: "failed" };
    case "canceled":
      return { label: "취소", tone: "canceled" };
    case "awaiting_approval":
      return { label: "승인 대기", tone: "waiting" };
    case undefined:
      return { label: "알 수 없음", tone: "unknown" };
    default:
      return { label: "진행 중", tone: "running" };
  }
}

function formatTime(ts: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

function pollOnce() {
  if (document.hidden || !open.value) return;
  void history.refresh("research");
}

function syncPolling() {
  if (hasLiveResearch.value && !pollTimer) pollTimer = setInterval(pollOnce, POLL_MS);
  if (!hasLiveResearch.value && pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function onVisibility() {
  if (!document.hidden && hasLiveResearch.value) pollOnce();
}

watch(hasLiveResearch, syncPolling);

onMounted(() => {
  v1Map.value = readV1Map(safeLocalStorage());
  void history.load();
  syncPolling();
  document.addEventListener("visibilitychange", onVisibility);
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
  document.removeEventListener("visibilitychange", onVisibility);
});
</script>

<style scoped>
.skx-history__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
}
.skx-history__clear {
  padding: 0.1rem 0.4rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  font-size: 0.6rem;
  color: var(--skx-gray-2);
  cursor: pointer;
}
.skx-history__clear:hover {
  color: var(--skx-primary);
  background: rgba(79, 70, 229, 0.06);
}
.skx-history__empty {
  margin: 0;
  padding: 0.8rem 0.4rem;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-gray-2);
}
.skx-history__row {
  position: relative;
}
.skx-history__row .skx-history-item {
  padding-right: 1.6rem;
}
.skx-history-item__meta {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  width: 100%;
}
.skx-history-item__meta .skx-history-item__time {
  width: auto;
}
.skx-history-item__del {
  position: absolute;
  top: 50%;
  right: 0.2rem;
  width: 1.2rem;
  height: 1.2rem;
  padding: 0.2rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  opacity: 0;
  transform: translateY(-50%);
  cursor: pointer;
  transition: opacity 0.15s;
}
.skx-history__row:hover .skx-history-item__del,
.skx-history-item__del:focus-visible {
  opacity: 1;
}
@media (hover: none) {
  .skx-history-item__del {
    opacity: 1;
  }
}
.skx-history-item__del img {
  width: 100%;
  height: 100%;
}
.skx-history-badge {
  flex: none;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  font-size: 0.5rem;
  font-weight: 600;
  line-height: 1.6;
  background: rgba(79, 70, 229, 0.1);
  color: var(--skx-primary);
}
.skx-history-badge.is-done {
  background: #e7f6ec;
  color: #1e7b3c;
}
.skx-history-badge.is-failed {
  background: #fdecec;
  color: #c62828;
}
.skx-history-badge.is-waiting {
  background: #fff5e0;
  color: #a56a00;
}
.skx-history-badge.is-canceled,
.skx-history-badge.is-unknown {
  background: #f0f0f0;
  color: var(--skx-gray-1);
}
.skx-history__confirm {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.6rem;
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  background: var(--skx-white);
}
.skx-history__confirm-text {
  margin: 0;
  font-size: 0.6rem;
  line-height: 1.5;
  color: var(--skx-ink);
}
.skx-history__confirm-actions {
  display: flex;
  gap: 0.3rem;
  justify-content: flex-end;
}
.skx-history__confirm-btn {
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
  background: var(--skx-white);
  font-size: 0.6rem;
  cursor: pointer;
}
.skx-history__confirm-btn.is-danger {
  border-color: #c62828;
  background: #c62828;
  color: var(--skx-white);
}
</style>
```

- [ ] **Step 2: 빌드·테스트 확인**

Run: `cd frontend && npm run build`
Expected: 오류 없이 끝난다.

Run: `cd frontend && npm test`
Expected: `Tests  92 passed (92)`

- [ ] **Step 3: 수동 확인 (dev 서버, `/api` 는 영역 A 의 기록 API 가 떠 있는 서버로 프록시 — spec §13 미확정 항목)**

Run: `cd frontend && npm run dev`
- 메인(`/`)·`/papers`·`/recommend` 어디서든 사이드바에 같은 기록이 보인다(M6). `/papers` 에서는 논문 탭이 처음 열린다.
- 항목 위에 올리면 × 가 보이고 누르면 즉시 사라진다. `DELETE /api/history/<id>` 204.
- 탭 전체 삭제 → 확인 상자 → 지우기 → 빈 상태 문구. 딥리서치 탭 확인 문구에 "보고서 자체는 지워지지 않습니다".
- 접기 → 다른 페이지로 이동 → 계속 접혀 있다.
- 브라우저 탭 두 개: 한쪽에서 항목을 지우면 다른 쪽 목록이 1초 안에 갱신된다(M4).
- (페이지 통합 전이므로) 페이지들이 옛 props 를 넘겨도 오류 없이 무시된다.

- [ ] **Step 4: 커밋**

```
git add frontend/components/AppSidebar.vue
git commit -m "[Feat] round04b — 사이드바 3탭·삭제·딥리서치 배지·라우트 강조"
```

---

### Task 22: 메인(도서) 페이지 통합 — `pages/index.vue`

**Files:**
- Modify: `frontend/pages/index.vue` — 3~10행(사이드바) · 655~659행(import) · 675~698행(세션 코드) · 775~778행(기록) · 835~841행(onMounted 머리) · 862~866행(onUnmounted) · 901~983행(handleSearch·슬림화) · 998~1023행(restoreSession) · 1100~1167행(fetchCuration) · 1205~1208행·1224~1228행(상세 이동)

해소: H1(큐레이션이 시작 때 기록 id 를 붙잡고 `AbortController` 로 끊긴다) · H2(검색 성공 시 `?q&h` 를 URL 에 싣고 `watch(route.query.h)` 로 복원) · M1(복원 분기 제거, 다른 종류면 `routeFor`) · M2(복원이 `mode` 를 book 으로) · M5(엔터 연타 가드·10분 병합) · M7(세션 ID 코드 삭제, 모든 호출에 헤더).

첫 복원을 `watch(..., {immediate: true})` 대신 `onMounted` 에서 하는 이유: setup 은 서버에서도 돌아 SSR 이 그린 랜딩과 클라이언트 상태가 어긋난다(하이드레이션). 이후 같은 경로의 쿼리 변화는 `watch` 가 받는다. 죽은 코드(`fetchPaperSummary`·`fetchReason`·`fetchRelated`·`readSSE`)는 spec §11 에 따라 건드리지 않는다 — 그래서 `config`·`apiBase` 는 남긴다.

- [ ] **Step 1: 사이드바 props 제거 (3~10행)**

현재:
```vue
    <AppSidebar
      :book-history="bookHistory"
      :paper-history="paperHistory"
      :active-id="currentHistoryId ?? undefined"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
      @restore="restoreSession"
    />
```
교체:
```vue
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />
```

- [ ] **Step 2: import (655~659행)**

현재:
```ts
<script setup lang="ts">
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import type { BookChunkGroup } from "~/types/search";
import type { HistoryEntry } from "~/types/history";
```
교체:
```ts
<script setup lang="ts">
import type { Ref } from "vue";
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { slimBookResult } from "~/utils/historySnapshot";
import { readV1Map } from "~/utils/historyStore";
import { readHistoryQuery, routeFor } from "~/utils/historyRoute";
import type { BookChunkGroup } from "~/types/search";
import type { BookEntry, BookSnapshot } from "~/types/history";
```

- [ ] **Step 3: 세션 ID 중복 코드 삭제 (675~698행)**

현재(`const config` 두 줄 뒤 `// ── 세션 ──` 부터 `getSessionId` 끝까지):
```ts
const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

// ── 세션 ──────────────────────────────────────────────────
function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getSessionId(): string {
  if (!process.client) return "";
  let sid = localStorage.getItem("sid");
  if (!sid) {
    sid = generateUUID();
    localStorage.setItem("sid", sid);
  }
  return sid;
}
```
교체:
```ts
const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;
const api = useApi();
const route = useRoute();
const router = useRouter();
```

- [ ] **Step 4: 기록 상태 (775~778행)**

현재:
```ts
// ── 검색 기록 ─────────────────────────────────────────────
const { bookHistory, paperHistory, addEntry, updateAiSummary, getById } =
  useSearchHistory();
const currentHistoryId = ref<string | null>(null);
```
교체:
```ts
// ── 검색 기록 ─────────────────────────────────────────────
const historyApi = useHistory();
const currentHistoryId = ref<string | null>(null);
// 검색·복원·큐레이션을 한 묶음으로 끊는다 — 새 검색이나 복원이 시작되면 이전 묶음의
// 응답·타이핑·저장이 새 화면과 새 기록을 덮지 못하게 한다
let runCtrl: AbortController | null = null;
function beginRun(): AbortSignal {
  runCtrl?.abort();
  runCtrl = new AbortController();
  return runCtrl.signal;
}
```

- [ ] **Step 5: onMounted 머리 (835~841행)**

현재:
```ts
onMounted(async () => {
  if (!process.client) return;
  const restoreId = (useRoute().query.restore as string) ?? null;
  if (restoreId) {
    const entry = getById(restoreId);
    if (entry) restoreSession(entry);
  }

  // Tab slider
```
교체:
```ts
onMounted(async () => {
  if (!process.client) return;
  // 첫 복원을 setup 이 아니라 마운트 뒤에 한다 — 서버가 그린 랜딩과 하이드레이션이 어긋나지 않게
  restoreFromQuery();

  // Tab slider
```

- [ ] **Step 6: onUnmounted (862~866행)**

현재:
```ts
onUnmounted(() => {
  window.removeEventListener("resize", updateTabSlider);
  document.removeEventListener("click", onDocClick);
  if (aiStageTimer) clearTimeout(aiStageTimer);
});
```
교체:
```ts
onUnmounted(() => {
  // 페이지를 떠나면 큐레이션 요청도 끊는다 — 안 끊으면 GPU 생성이 끝까지 돈다
  runCtrl?.abort();
  window.removeEventListener("resize", updateTabSlider);
  document.removeEventListener("click", onDocClick);
  if (aiStageTimer) clearTimeout(aiStageTimer);
});
```

- [ ] **Step 7: handleSearch 와 슬림화 (901~983행)**

`// ── 검색 ──` 주석(901행)부터 `slimResultForHistory` 함수 끝(983행)까지를 교체한다(`handleChip` 은 그대로 둔다).

현재(요지 — 901~960행 `handleSearch`, 962~983행 `slimResultForHistory`):
```ts
// ── 검색 ──────────────────────────────────────────────────
async function handleSearch(query: string) {
  if (!query.trim()) return;
  ...
      currentHistoryId.value = addEntry({
        type: "book",
        query,
        result: slimResultForHistory(data),
      });
      if (books.value.length) fetchCuration();
  ...
}

// 세션 저장용 결과 슬림화 — 청크 원문과 book_info의 대용량 생성 텍스트 제거
// (복원 시 목록 카드 렌더링에 필요 없는 필드. 상세 페이지는 자체 fetch)
function slimResultForHistory(data: any) {
  ...
}
```
교체:
```ts
// ── 검색 ──────────────────────────────────────────────────
async function handleSearch(query: string, reuse?: BookEntry) {
  if (!query.trim() || loading.value) return;

  // 논문 모드는 papers 전용 페이지로 이동 — 랜딩에서 고른 등재 필터를 유지해서 넘긴다
  if (mode.value === "paper") {
    const grade = activeFilters.value[0];
    const gradeParam = grade ? `&grade=${encodeURIComponent(grade)}` : "";
    navigateTo(`/papers?q=${encodeURIComponent(query.trim())}${gradeParam}`);
    return;
  }

  const signal = beginRun();
  currentQuery.value = query;
  currentHistoryId.value = null;
  loading.value = true;
  searchError.value = "";
  books.value = [];
  papers.value = [];
  curation.value = null;
  curationIntro.value = "";
  curationItems.value = [];
  curationLoading.value = false;
  curationTyping.value = false;
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
  paperSummaryText.value = "";
  keywordChips.value = [];
  view.value = "results";

  try {
    const data = await api<any>("/books/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        // 컬렉션 크기 + 더보기 목록용 여유분 확보 (백엔드 상한 20)
        top_k: Math.min(20, Math.max(collectionSize.value + 5, 10)),
        use_rewrite: true,
        use_rerank: true,
      },
      signal,
    });
    if (signal.aborted) return;
    if (data?.books) {
      books.value = data.books;
      rewrittenQuery.value = data.rewritten_query || query;
    }
    loading.value = false;

    // 기록 id 를 먼저 확정해 큐레이션에 넘긴다 — 끝난 뒤 저장이 그 사이 바뀐 화면의 기록을 덮지 않게
    const snapshot = slimBookResult(data) ?? undefined;
    const entry = reuse
      ? ((await historyApi.patch(reuse.id, { snapshot })) ?? reuse)
      : await historyApi.add({ kind: "book", title: query.trim(), params: {}, snapshot });
    if (signal.aborted) return;
    currentHistoryId.value = entry.id;
    router.replace({ query: { q: query, h: entry.id } });
    if (books.value.length) fetchCuration(entry.id, signal);
  } catch (e: any) {
    if (signal.aborted) return;
    searchError.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
  } finally {
    if (!signal.aborted) loading.value = false;
  }
}
```

- [ ] **Step 8: restoreSession → 주소 기준 복원 (998~1023행)**

현재:
```ts
function restoreSession(entry: HistoryEntry) {
  if (entry.type === "paper") {
    navigateTo(`/papers?restore=${entry.id}`);
    return;
  }
  currentQuery.value = entry.query;
  currentHistoryId.value = entry.id;
  view.value = "results";
  books.value = entry.result?.books ?? [];
  if (entry.aiSummary) {
    try {
      const ai = JSON.parse(entry.aiSummary);
      curationIntro.value = ai.intro ?? "";
      curationItems.value = ai.items ?? [];
    } catch {
      curationIntro.value = entry.aiSummary;
      curationItems.value = [];
    }
  } else {
    curationIntro.value = "";
    curationItems.value = [];
  }
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
}
```
교체:
```ts
// ── 기록 복원 ─────────────────────────────────────────────
// 주소(?h=)가 복원의 정본이다 — 사이드바·뒤로가기·새로고침이 모두 이 한 길로 들어온다
async function restoreFromQuery() {
  // 다른 페이지로 넘어가는 중에는 그 주소의 q 로 재검색하지 않는다
  if (route.path !== "/") return;
  const { h, q } = readHistoryQuery(route.query, readV1Map(safeLocalStorage()));
  if (!h) {
    if (q && q !== currentQuery.value) {
      mode.value = "book";
      await handleSearch(q);
    }
    return;
  }
  if (h === currentHistoryId.value) return;

  const signal = beginRun();
  loading.value = false;
  const entry = await historyApi.get(h);
  if (signal.aborted) return;
  if (entry && entry.kind !== "book") {
    // 다른 종류의 기록 id 가 이 주소로 왔다(옛 ?restore= 등) — 그 종류의 주소로 보낸다
    router.replace(routeFor(entry));
    return;
  }
  const book = entry?.kind === "book" ? entry : null;
  if (book?.snapshot) {
    applyBookEntry(book, signal);
    return;
  }
  // 없거나 남의 기록이면 검색어로 새로 찾는다(D7). 결과만 비어 있던 내 기록은 같은 id 를 채운다
  if (!book) void historyApi.refresh("book");
  const retryQuery = q ?? book?.title;
  if (retryQuery) {
    mode.value = "book";
    await handleSearch(retryQuery, book ?? undefined);
    return;
  }
  showToast("없는 기록입니다. 목록을 새로 고쳤습니다.");
}

function applyBookEntry(entry: BookEntry, signal: AbortSignal) {
  const snap = entry.snapshot as BookSnapshot;
  mode.value = "book";
  view.value = "results";
  loading.value = false;
  searchError.value = "";
  currentQuery.value = entry.title;
  currentHistoryId.value = entry.id;
  rewrittenQuery.value = snap.rewritten_query || entry.title;
  books.value = snap.books as unknown as BookChunkGroup[];
  papers.value = [];
  keywordChips.value = [];
  curation.value = null;
  curationLoading.value = false;
  curationTyping.value = false;
  curationIntro.value = entry.ai?.intro ?? "";
  curationItems.value = (entry.ai?.items ?? []) as Array<{ book_id: string; reason: string }>;
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
  if (route.query.h !== entry.id || route.query.q !== entry.title) {
    router.replace({ query: { q: entry.title, h: entry.id } });
  }
  // 큐레이션이 끝나기 전에 떠난 기록은 요약이 비어 있다 — 복원할 때 한 번 더 만든다
  if (!entry.ai && books.value.length) fetchCuration(entry.id, signal);
}

// 같은 경로에서 쿼리만 바뀌면(사이드바 클릭·뒤로가기) 페이지가 다시 마운트되지 않는다
watch(
  () => route.query.h ?? route.query.restore,
  () => {
    restoreFromQuery();
  },
);
```

- [ ] **Step 9: fetchCuration (1100~1167행)**

현재(`// ── 큐레이션 (도서) ── SSE 타이프라이터 스트리밍 ──` 부터 함수 끝까지 — 끝난 시점의 `currentHistoryId.value` 로 `updateAiSummary` 를 부르는 코드):
```ts
// ── 큐레이션 (도서) ── SSE 타이프라이터 스트리밍 ──────────────
async function fetchCuration() {
  ...
        if (currentHistoryId.value) {
          updateAiSummary(
            currentHistoryId.value,
  ...
}
```
교체:
```ts
function typeInto(target: Ref<string>, text: string, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    let i = 0;
    const step = () => {
      if (signal.aborted || i >= text.length) {
        resolve();
        return;
      }
      target.value += text.charAt(i++);
      setTimeout(step, 18);
    };
    step();
  });
}

// ── 큐레이션 (도서) ── 타이프라이터 출력 ──────────────────────
async function fetchCuration(historyId: string, signal: AbortSignal) {
  // 임계값을 넘는 도서만, 선택한 컬렉션 크기만큼 LLM 답변에 포함
  const topBooks = books.value
    .filter((b) => (b.best_score || 0) >= COLLECTION_SCORE_THRESHOLD)
    .slice(0, collectionSize.value);
  if (!topBooks.length) return;
  startAiStages();
  curationLoading.value = true;
  curationTyping.value = true;
  curationIntro.value = "";
  curationItems.value = [];
  try {
    const data = await api<any>("/books/curate", {
      method: "POST",
      body: {
        query: currentQuery.value,
        book_ids: topBooks.map((b) => b.book_id),
        scores: topBooks.map((b) => b.best_score || 0),
        rewritten_query: rewrittenQuery.value,
      },
      signal,
    });
    if (signal.aborted) return;
    curation.value = data;
    curationLoading.value = false;
    const intro: string = data?.intro || "";
    const items: Array<{ book_id: string; reason: string }> = (data?.items || []).map(
      (ci: { book_id: string; reason: string }) => ({ book_id: ci.book_id, reason: ci.reason }),
    );
    if (intro) {
      curationOpen.value = true;
      await typeInto(curationIntro, intro, signal);
      if (signal.aborted) return;
    }
    curationItems.value = items;
    curationTyping.value = false;
    await historyApi.patch(historyId, { ai: { intro, items } });
  } catch {
    /* 큐레이션 실패·중단 시 조용히 무시 */
  } finally {
    if (!signal.aborted) {
      curationLoading.value = false;
      curationTyping.value = false;
    }
  }
}
```

- [ ] **Step 10: 상세로 갈 때 `h` 전달 (1205~1208행, 1224~1228행)**

`openDetail` 의 도서 분기 — 현재:
```ts
  const params = new URLSearchParams({
    q: currentQuery.value,
    score: String(item.best_score || 0),
  });
  if (item.title_score !== undefined)
```
교체:
```ts
  const params = new URLSearchParams({
    q: currentQuery.value,
    score: String(item.best_score || 0),
  });
  // 상세에서도 사이드바가 이 기록을 강조하고, 뒤로가기가 재검색 없이 복원되게
  if (currentHistoryId.value) params.set("h", currentHistoryId.value);
  if (item.title_score !== undefined)
```

`openDetailWithChat` 의 도서 분기 — 현재:
```ts
  const params = new URLSearchParams({
    q: currentQuery.value,
    score: String(item.best_score || 0),
    chat: "1",
  });
```
교체:
```ts
  const params = new URLSearchParams({
    q: currentQuery.value,
    score: String(item.best_score || 0),
    chat: "1",
  });
  if (currentHistoryId.value) params.set("h", currentHistoryId.value);
```

- [ ] **Step 11: 잔재 grep·빌드**

Run: `cd frontend && grep -n "useSearchHistory\|getSessionId\|generateUUID\|restoreSession\|updateAiSummary\|addEntry\|getById\|slimResultForHistory\|bookHistory\|paperHistory" pages/index.vue`
Expected: 출력 없음(종료 코드 1).

Run: `cd frontend && npm run build`
Expected: 오류 없이 끝난다.

- [ ] **Step 12: 수동 확인 (dev 서버 + 기록 API 프록시)**

- 도서 검색 → 주소가 `/?q=…&h=<uuid>` 로 바뀌고 사이드바 도서 탭 맨 위에 생겨 강조된다.
- 큐레이션 타이핑 중 사이드바에서 다른 도서 기록 클릭 → 타이핑이 즉시 멈추고 클릭한 기록의 요약이 나온다. 원래 기록을 다시 열면 요약이 섞이지 않았다(H1). Network 에서 `/api/books/curate` 가 `(canceled)`.
- 결과에서 책 상세 → 상세 주소에 `h=` 가 있고 사이드바가 같은 항목을 강조 → 뒤로가기 → 스피너 없이 결과·요약 복원, `/api/books/search` 재호출 없음(H2). 새로고침도 같다.
- 랜딩에서 논문 탭을 고른 채 사이드바 도서 기록 클릭 → 도서 결과가 보인다(M2).
- 결과 화면 입력창 엔터 연타 → `/api/books/search` 한 번, 기록 하나(M5). 같은 검색어로 곧바로 다시 검색 → 새 항목 없이 기존 항목이 맨 위로.
- Network: `/api/books/search`·`/api/books/curate`·`/api/history*` 요청 헤더에 `x-session-id`.
- v1 기록이 있던 브라우저: 첫 로드 뒤 `localStorage` 에 `skx_search_history_backup_v1`·`skx_history_v1_map` 이 생기고 `skx_search_history` 는 없다. 옛 주소 `/?restore=<13자리 id>` → 이전된 기록으로 열리고 주소가 `?q&h` 로 바뀐다.
- 다른 브라우저 프로필에서 복사한 `/?h=…&q=…` → `q` 로 새로 검색된다(D7).

- [ ] **Step 13: 커밋**

```
git add frontend/pages/index.vue
git commit -m "[Feat] round04b — 도서 검색 기록 URL 복원·큐레이션 경합 해소"
```

---

### Task 23: 논문 결과 페이지 통합 — `pages/papers/index.vue`

**Files:**
- Modify: `frontend/pages/papers/index.vue` — 3~12행(사이드바) · 130~137행(참고 논문 제목 클릭) · 458~466행(DeepSearch 버튼) · 591~601행(script 머리) · 770~774행(goToDetail) · 776행 `// ── 검색 ──` ~ 917행(스크립트 끝까지)

해소: H1(요약 스트림이 시작 때 기록 id 를 붙잡고 끊긴다) · H2(돌아올 때 옛 `?q=` 로 재검색하던 것을 `h` 복원으로) · M1 · M5 · M7(논문 검색·요약 스트림에 헤더) · L3(복원 때 등재 필터도 되돌린다).

- [ ] **Step 1: 사이드바 props 제거 (3~12행)**

현재:
```vue
    <AppSidebar
      default-tab="paper"
      :collapsed="!!chatPaperId"
      :book-history="bookHistory"
      :paper-history="paperHistory"
      :active-id="currentHistoryId ?? undefined"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
      @restore="restoreSession"
    />
```
교체:
```vue
    <AppSidebar
      :collapsed="!!chatPaperId"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />
```

- [ ] **Step 2: 참고 논문 제목 클릭 (130~137행)**

현재:
```vue
                      <p
                        class="skx-pai-ref__title skx-pai-ref__title--link"
                        @click="
                          navigateTo(
                            `/papers/${ref.book_id}?q=${encodeURIComponent(currentQuery)}`,
                          )
                        "
                      >
```
교체:
```vue
                      <p
                        class="skx-pai-ref__title skx-pai-ref__title--link"
                        @click="navigateTo(detailUrl(ref.book_id))"
                      >
```

- [ ] **Step 3: DeepSearch 버튼 (458~466행)**

현재:
```vue
                  <button
                    type="button"
                    class="skx-btn-ptalk"
                    @click.stop="
                      navigateTo(
                        `/papers/${paper.book_id}?q=${encodeURIComponent(currentQuery)}&chat=1`,
                      )
                    "
                  >
```
교체:
```vue
                  <button
                    type="button"
                    class="skx-btn-ptalk"
                    @click.stop="navigateTo(detailUrl(paper.book_id, { chat: '1' }))"
                  >
```

- [ ] **Step 4: script 머리 (591~601행)**

현재:
```ts
<script setup lang="ts">
import { marked } from "marked";
import type { BookSearchResponse, BookChunkGroup } from "~/types/search";
import type { HistoryEntry } from "~/types/history";

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

const { bookHistory, paperHistory, addEntry, updateAiSummary, getById } =
  useSearchHistory();
const currentHistoryId = ref<string | null>(null);
```
교체:
```ts
<script setup lang="ts">
import { marked } from "marked";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { slimPaperResult } from "~/utils/historySnapshot";
import { readV1Map } from "~/utils/historyStore";
import { readHistoryQuery, routeFor } from "~/utils/historyRoute";
import type { BookSearchResponse, BookChunkGroup } from "~/types/search";
import type { PaperEntry, PaperSnapshot } from "~/types/history";

const api = useApi();
const route = useRoute();
const router = useRouter();

const historyApi = useHistory();
const currentHistoryId = ref<string | null>(null);
// 검색·복원·요약 스트림을 한 묶음으로 끊는다 — 새 검색이나 복원이 시작되면 이전 묶음의
// 응답·스트림·저장이 새 화면과 새 기록을 덮지 못하게 한다
let runCtrl: AbortController | null = null;
function beginRun(): AbortSignal {
  runCtrl?.abort();
  runCtrl = new AbortController();
  return runCtrl.signal;
}
```

- [ ] **Step 5: goToDetail (770~774행)**

현재:
```ts
function goToDetail(paper: any) {
  navigateTo(
    `/papers/${paper.book_id}?q=${encodeURIComponent(currentQuery.value)}`,
  );
}
```
교체:
```ts
// 상세로 갈 때 기록 id 를 넘긴다 — 상세에서도 사이드바가 이 기록을 강조하고, 뒤로가기가 재검색 없이 복원된다
function detailUrl(bookId: string, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams({ q: currentQuery.value, ...extra });
  if (currentHistoryId.value) params.set("h", currentHistoryId.value);
  return `/papers/${bookId}?${params}`;
}

function goToDetail(paper: any) {
  navigateTo(detailUrl(paper.book_id));
}
```

- [ ] **Step 6: 검색·복원·요약·마운트 (776행 `// ── 검색 ──` 부터 `</script>` 직전까지 전부 교체)**

현재(요지): `handleSearch`(776~823, 끝에 `addEntry` 후 `streamAiSummary(query, data.books)`), `restoreSession`(825~845, `entry.type === "book"` 분기), `streamAiSummary`(847~895, finally 에서 `currentHistoryId.value` 로 `updateAiSummary`), `onMounted`(897~915, `?restore=` → `getById`, 아니면 `?q=` 로 `handleSearch`), `watch(currentPage, …)`(917).

교체:
```ts
// ── 검색 ─────────────────────────────────────────────────────
async function handleSearch(q?: string, reuse?: PaperEntry) {
  const query = (q ?? currentQuery.value).trim();
  if (!query || loading.value) return;
  const signal = beginRun();
  currentQuery.value = query;
  currentHistoryId.value = null;
  loading.value = true;
  error.value = null;
  paperResult.value = null;
  aiText.value = "";
  aiRefs.value = [];
  aiLoading.value = false;
  aiExpanded.value = false;
  currentPage.value = 1;
  sortBy.value = "relevance";

  try {
    const data = await api<BookSearchResponse>("/papers/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 20,
        use_rewrite: true,
        use_rerank: true,
      },
      signal,
    });
    if (signal.aborted) return;
    paperResult.value = data;
    loading.value = false;

    // 기록 id 를 먼저 확정해 요약 스트림에 넘긴다 — 끝난 뒤 저장이 그 사이 바뀐 화면의 기록을 덮지 않게
    const grade = selectedGrade.value !== "all" ? selectedGrade.value : "";
    const snapshot = slimPaperResult(data) ?? undefined;
    const entry = reuse
      ? ((await historyApi.patch(reuse.id, { snapshot })) ?? reuse)
      : await historyApi.add({ kind: "paper", title: query, params: grade ? { grade } : {}, snapshot });
    if (signal.aborted) return;
    currentHistoryId.value = entry.id;
    router.replace({ query: { q: query, h: entry.id, ...(grade ? { grade } : {}) } });
    if (data.books?.length) streamAiSummary(entry.id, query, data.books, signal);
  } catch (e: any) {
    if (signal.aborted) return;
    error.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
    paperResult.value = { mode: "book", query, books: [], elapsed_ms: 0 };
  } finally {
    if (!signal.aborted) loading.value = false;
  }
}

// ── 기록 복원 ─────────────────────────────────────────────────
// 주소(?h=)가 복원의 정본이다 — 사이드바·뒤로가기·새로고침이 모두 이 한 길로 들어온다
async function restoreFromQuery() {
  // 다른 페이지로 넘어가는 중에는 그 주소의 q 로 재검색하지 않는다
  if (route.path !== "/papers") return;
  const { h, q, grade } = readHistoryQuery(route.query, readV1Map(safeLocalStorage()));
  if (!h) {
    if (q && q !== currentQuery.value) {
      selectedGrade.value = grade ?? "all";
      await handleSearch(q);
    }
    return;
  }
  if (h === currentHistoryId.value) return;

  const signal = beginRun();
  loading.value = false;
  const entry = await historyApi.get(h);
  if (signal.aborted) return;
  if (entry && entry.kind !== "paper") {
    // 다른 종류의 기록 id 가 이 주소로 왔다(옛 ?restore= 등) — 그 종류의 주소로 보낸다
    router.replace(routeFor(entry));
    return;
  }
  const paper = entry?.kind === "paper" ? entry : null;
  if (paper?.snapshot) {
    applyPaperEntry(paper, signal);
    return;
  }
  // 없거나 남의 기록이면 검색어로 새로 찾는다(D7). 결과만 비어 있던 내 기록은 같은 id 를 채운다
  if (!paper) void historyApi.refresh("paper");
  const retryQuery = q ?? paper?.title;
  if (retryQuery) {
    const savedGrade = typeof paper?.params.grade === "string" ? paper.params.grade : "";
    selectedGrade.value = savedGrade || grade || "all";
    await handleSearch(retryQuery, paper ?? undefined);
    return;
  }
  showToast("없는 기록입니다. 목록을 새로 고쳤습니다.");
}

function applyPaperEntry(entry: PaperEntry, signal: AbortSignal) {
  const snap = entry.snapshot as PaperSnapshot;
  const grade = typeof entry.params.grade === "string" ? entry.params.grade : "";
  loading.value = false;
  error.value = null;
  currentQuery.value = entry.title;
  currentHistoryId.value = entry.id;
  paperResult.value = {
    mode: "book",
    query: entry.title,
    books: snap.books as unknown as BookChunkGroup[],
    elapsed_ms: 0,
  };
  aiText.value = entry.ai?.text ?? "";
  aiRefs.value = (entry.ai?.refs ?? []) as typeof aiRefs.value;
  aiLoading.value = false;
  aiExpanded.value = true;
  currentPage.value = 1;
  sortBy.value = "relevance";
  selectedGrade.value = grade || "all";
  if (route.query.h !== entry.id || route.query.q !== entry.title) {
    router.replace({ query: { q: entry.title, h: entry.id, ...(grade ? { grade } : {}) } });
  }
  // 요약이 끝나기 전에 떠난 기록은 요약이 비어 있다 — 복원할 때 한 번 더 만든다
  if (!entry.ai && snap.books.length) streamAiSummary(entry.id, entry.title, snap.books, signal);
}

// ── AI 요약 SSE ───────────────────────────────────────────────
type SummarySource = {
  book_id: string;
  book_info?: { title?: string; personal_author?: string; corporate_author?: string };
};

async function streamAiSummary(
  historyId: string,
  query: string,
  books: SummarySource[],
  signal: AbortSignal,
) {
  aiLoading.value = true;
  const papers = books.slice(0, 5).map((b) => ({
    book_id: b.book_id,
    title: b.book_info?.title || "",
    authors:
      b.book_info?.personal_author || b.book_info?.corporate_author || "",
    best_chunk_text: "",
  }));
  let text = "";
  let refs: typeof aiRefs.value = [];
  try {
    const resp = await fetch(apiUrl("/papers/summary/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ query, papers }),
      signal,
    });
    if (!resp.ok || !resp.body) return;
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop()!;
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") return;
        try {
          const evt = JSON.parse(raw);
          if (evt.text) {
            text += evt.text;
            aiText.value = text;
          }
          if (evt.sources) {
            refs = evt.sources;
            aiRefs.value = refs;
          }
        } catch {}
      }
    }
  } catch {
    /* 중단·네트워크 오류 — 받은 데까지만 남긴다 */
  } finally {
    // 끊긴 묶음은 저장하지 않는다 — 화면과 기록은 이미 다음 묶음의 것이다
    if (!signal.aborted) {
      aiLoading.value = false;
      if (text) historyApi.patch(historyId, { ai: { text, refs } });
    }
  }
}

// ── 페이지당 개수 드롭다운 닫기 + 주소 기준 첫 복원 ─────────────
onMounted(() => {
  document.addEventListener("click", () => {
    perpageOpen.value = false;
  });
  // 첫 복원을 setup 이 아니라 마운트 뒤에 한다 — 서버가 그린 랜딩과 하이드레이션이 어긋나지 않게
  restoreFromQuery();
});

// 같은 경로에서 쿼리만 바뀌면(사이드바 클릭·뒤로가기) 페이지가 다시 마운트되지 않는다
watch(
  () => route.query.h ?? route.query.restore,
  () => {
    restoreFromQuery();
  },
);

// 페이지를 떠나면 요약 스트림도 끊는다 — 안 끊으면 GPU 생성이 끝까지 돈다
onBeforeUnmount(() => runCtrl?.abort());

watch(currentPage, () => window.scrollTo({ top: 0, behavior: "smooth" }));
```

- [ ] **Step 7: 잔재 grep·빌드**

Run: `cd frontend && grep -n "useSearchHistory\|restoreSession\|updateAiSummary\|addEntry\|getById\|bookHistory\|paperHistory\|apiBase" pages/papers/index.vue`
Expected: 출력 없음.

Run: `cd frontend && npm run build`
Expected: 오류 없이 끝난다.

- [ ] **Step 8: 수동 확인**

- 메인 논문 탭에서 등재 필터를 고르고 검색 → `/papers?q=…&grade=…` → 검색 뒤 주소에 `h=` 가 붙고 사이드바 논문 탭 맨 위에 강조.
- 요약 스트리밍 중 다른 논문 기록 클릭 → `/api/papers/summary/stream` 이 `(canceled)`, 클릭한 기록의 요약이 그대로 보이고 원래 기록 요약은 섞이지 않는다(H1).
- 논문 상세(주소에 `h=`) → 뒤로가기 → 재검색 없이 복원, 기록 수 그대로(H2). 새로고침도 같다. 등재 필터도 되돌아온다(L3).
- 사이드바 도서 기록 클릭 → `/` 로 가서 도서 결과(M1).
- 결과 검색바 엔터 연타 → 검색 한 번(M5).
- Network: `/api/papers/search`·`/api/papers/summary/stream` 요청 헤더에 `x-session-id`.

- [ ] **Step 9: 커밋**

```
git add frontend/pages/papers/index.vue
git commit -m "[Feat] round04b — 논문 검색 기록 URL 복원·요약 스트림 중단"
```

---

### Task 24: 상세·추천·부품의 기록 분기 제거와 헤더 첨부

**Files:**
- Modify: `frontend/pages/books/[cnts_id].vue` — 3~9행 · 521~545행 · 672행 · 687~696행 · 713~722행
- Modify: `frontend/pages/papers/[id].vue` — 3~10행 · 410~427행 · 576행 · 588~590행 · 610~614행 · 631~638행
- Modify: `frontend/pages/recommend/[id].vue` — 274~277행 · 388행
- Modify: `frontend/components/BookChat.vue` — 73~74행 · 101~102행 · 133~135행
- Modify: `frontend/components/CitationModal.vue` — 80행 · 88~89행 · 111~113행

상세 두 페이지의 복원 분기(M1 의 나머지 두 벌)와 사이드바 props 를 없애고, 모든 `/api` 호출에 `x-session-id` 를 붙인다(spec §4-2). 도서 상세의 연관도서 검색이 헤더 없이 주인 없는 `search_history` 행을 쌓던 문제가 완화된다(§4-9). 상세 페이지는 떠날 때 추천이유·연관이유 스트림을 끊는다. `pages/recommend/index.vue` 는 이미 props 없이 사이드바를 쓰므로 바꾸지 않는다. `pages/admin/jobs.vue` 는 게이트웨이가 외부 접근을 막는 관리 API 라 범위 밖이다.

- [ ] **Step 1: `pages/books/[cnts_id].vue` 사이드바 (3~9행)**

현재:
```vue
    <AppSidebar
      :book-history="bookHistory"
      :paper-history="paperHistory"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
      @restore="restoreSession"
    />
```
교체:
```vue
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />
```

- [ ] **Step 2: `pages/books/[cnts_id].vue` script 머리 (521~545행)**

현재:
```ts
<script setup lang="ts">
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { useSearchHistory } from "~/composables/useSearchHistory";
import type { BookInfo } from "~/types/search";
import type { HistoryEntry } from "~/types/history";

// ── 라우트 ─────────────────────────────────────────────────
const route = useRoute();
const cnts_id = route.params.cnts_id as string;
const searchQuery = (route.query.q as string) || "";

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

const { bookHistory, paperHistory } = useSearchHistory();

function restoreSession(entry: HistoryEntry) {
  if (entry.type === "book") {
    navigateTo(`/?restore=${entry.id}`);
  } else {
    navigateTo(`/papers?restore=${entry.id}`);
  }
}
```
교체:
```ts
<script setup lang="ts">
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";
import type { BookInfo } from "~/types/search";

// ── 라우트 ─────────────────────────────────────────────────
const route = useRoute();
const cnts_id = route.params.cnts_id as string;
const searchQuery = (route.query.q as string) || "";

const api = useApi();
// 페이지를 떠나면 추천 이유 스트림을 끊는다 — 안 끊으면 GPU 생성이 끝까지 돈다
const pageAbort = new AbortController();
onBeforeUnmount(() => pageAbort.abort());
```

- [ ] **Step 3: `pages/books/[cnts_id].vue` 호출 세 곳**

`fetchBook` (672행) — 현재:
```ts
    const data = await $fetch<BookInfo>(`${apiBase}/books/${cnts_id}`);
```
교체:
```ts
    const data = await api<BookInfo>(`/books/${cnts_id}`, { signal: pageAbort.signal });
```

`streamReason` (687~696행) — 현재:
```ts
    const resp = await fetch(`${apiBase}/books/reason/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: searchQuery,
        book_id: cnts_id,
        chunk_texts: [],
        rewritten_query: "",
      }),
    });
```
교체:
```ts
    const resp = await fetch(apiUrl("/books/reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        query: searchQuery,
        book_id: cnts_id,
        chunk_texts: [],
        rewritten_query: "",
      }),
      signal: pageAbort.signal,
    });
```

`fetchRelatedBooks` (713~722행) — 현재:
```ts
    const data = await $fetch<any>(`${apiBase}/books/search`, {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 6,
        use_rewrite: false,
        use_rerank: true,
      },
    });
```
교체:
```ts
    const data = await api<any>("/books/search", {
      method: "POST",
      body: {
        query,
        mode: "book",
        top_k: 6,
        use_rewrite: false,
        use_rerank: true,
      },
      signal: pageAbort.signal,
    });
```

- [ ] **Step 4: `pages/papers/[id].vue` 사이드바 (3~10행)**

현재:
```vue
    <AppSidebar
      default-tab="paper"
      :book-history="bookHistory"
      :paper-history="paperHistory"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
      @restore="restoreSession"
    />
```
교체:
```vue
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />
```

- [ ] **Step 5: `pages/papers/[id].vue` script 머리 (410~427행)**

현재:
```ts
<script setup lang="ts">
import { marked } from "marked";
import { useSearchHistory } from "~/composables/useSearchHistory";
import { useBookmark } from "~/composables/useBookmark";
import type { HistoryEntry } from "~/types/history";

const route = useRoute();
const config = useRuntimeConfig();

const { bookHistory, paperHistory } = useSearchHistory();
const { isBookmarked, toggleBookmark, bookmarkIcon } = useBookmark();

function restoreSession(entry: HistoryEntry) {
  if (entry.type === "book") {
    navigateTo(`/?restore=${entry.id}`);
  } else {
    navigateTo(`/papers?restore=${entry.id}`);
  }
}
const paperId = route.params.id as string;
```
교체:
```ts
<script setup lang="ts">
import { marked } from "marked";
import { useBookmark } from "~/composables/useBookmark";
import { apiHeaders, apiUrl, useApi } from "~/composables/useApi";

const route = useRoute();
const config = useRuntimeConfig();
const api = useApi();
// 페이지를 떠나면 추천 이유·연관 이유 스트림을 끊는다 — 연관 논문마다 동시에 도는 생성이 끝까지 돈다
const pageAbort = new AbortController();
onBeforeUnmount(() => pageAbort.abort());

const { isBookmarked, toggleBookmark, bookmarkIcon } = useBookmark();

const paperId = route.params.id as string;
```
(`config` 는 564행 `thumbnailUrl` 이 계속 쓴다.)

- [ ] **Step 6: `pages/papers/[id].vue` 호출 네 곳**

`fetchPaper` (576행) — 현재:
```ts
    const data = await $fetch<any>(`${config.public.apiBase}/books/${paperId}`);
```
교체:
```ts
    const data = await api<any>(`/books/${paperId}`, { signal: pageAbort.signal });
```

`fetchRelated` (588~590행) — 현재:
```ts
    const data = await $fetch<any>(
      `${config.public.apiBase}/papers/${paperId}/related`,
    );
```
교체:
```ts
    const data = await api<any>(`/papers/${paperId}/related`, {
      signal: pageAbort.signal,
    });
```

`streamPaperReason` (610~614행) — 현재:
```ts
    const resp = await fetch(`${config.public.apiBase}/papers/reason/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paper_id: paperId, query }),
    });
```
교체:
```ts
    const resp = await fetch(apiUrl("/papers/reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ paper_id: paperId, query }),
      signal: pageAbort.signal,
    });
```

`streamRelatedReason` (631~638행) — 현재:
```ts
    const resp = await fetch(
      `${config.public.apiBase}/papers/related-reason/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_id: paperId, related_id: relatedId }),
      },
    );
```
교체:
```ts
    const resp = await fetch(apiUrl("/papers/related-reason/stream"), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ source_id: paperId, related_id: relatedId }),
      signal: pageAbort.signal,
    });
```

- [ ] **Step 7: `pages/recommend/[id].vue` (274~277행, 388행)**

현재(274~277행):
```ts
<script setup lang="ts">
const route = useRoute();
const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;
```
교체:
```ts
<script setup lang="ts">
import { useApi } from "~/composables/useApi";

const route = useRoute();
const api = useApi();
```

현재(388행):
```ts
    const data = await $fetch<any>(`${apiBase}/scenario/recommend`, {
```
교체:
```ts
    const data = await api<any>("/scenario/recommend", {
```

- [ ] **Step 8: `components/BookChat.vue` (73~74행, 101~102행, 133~135행)**

현재(73~74행):
```ts
<script setup lang="ts">
import { marked } from "marked";
```
교체:
```ts
<script setup lang="ts">
import { marked } from "marked";
import { apiHeaders, apiUrl } from "~/composables/useApi";
```

현재(101~102행) — 두 줄 삭제:
```ts
const config = useRuntimeConfig();
const apiBase = (config.public.apiBase as string) || "";
```

현재(133~135행):
```ts
    const resp = await fetch(`${apiBase}/books/chat/${props.cntsId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
```
교체:
```ts
    const resp = await fetch(apiUrl(`/books/chat/${props.cntsId}`), {
      method: "POST",
      headers: apiHeaders({ "Content-Type": "application/json" }),
```

- [ ] **Step 9: `components/CitationModal.vue` (80행, 88~89행, 111~113행)**

현재(80행):
```ts
<script setup lang="ts">
```
교체:
```ts
<script setup lang="ts">
import { useApi } from "~/composables/useApi";

```

현재(88~89행):
```ts
const config = useRuntimeConfig();
const apiBase = (config.public.apiBase as string) || "";
```
교체:
```ts
const api = useApi();
```

현재(111~113행):
```ts
    citation.value = await $fetch<{ korean: string; english: string }>(
      `${apiBase}/papers/${props.bookId}/citation`,
    );
```
교체:
```ts
    citation.value = await api<{ korean: string; english: string }>(
      `/papers/${props.bookId}/citation`,
    );
```

- [ ] **Step 10: 잔재 grep·빌드**

Run: `cd frontend && grep -rn "useSearchHistory\|restoreSession\|HistoryEntry\b" "pages/books/[cnts_id].vue" "pages/papers/[id].vue"`
Expected: 출력 없음.

Run: `cd frontend && grep -rn "\$fetch\|fetch(\`\${\|config.public.apiBase" pages components --include=*.vue | grep -v "search-classic\|BookChat.legacy\|admin/jobs"`
Expected: 남는 것은 `pages/index.vue` 의 `const apiBase = config.public.apiBase` 선언과 죽은 코드 세 줄(`fetchPaperSummary`·`fetchReason`·`fetchRelated` — spec §11), `pages/papers/[id].vue` 의 `thumbnailUrl`(이미지 URL, 헤더 불필요)뿐.

Run: `cd frontend && npm run build`
Expected: 오류 없이 끝난다.

- [ ] **Step 11: 수동 확인**

- 도서·논문 상세에서 사이드바가 들어온 기록(`h=`)을 강조하고, 사이드바 클릭이 `/`·`/papers` 로 복원 이동한다.
- 상세를 떠날 때 추천이유·연관이유 스트림이 Network 에서 `(canceled)`.
- Network: `/api/books/<id>`·`/api/books/reason/stream`·`/api/books/search`(연관도서)·`/api/papers/<id>/related`·`/api/books/chat/<id>`·`/api/papers/<id>/citation`·`/api/scenario/recommend` 요청 헤더에 `x-session-id`.
- 추천 페이지(`/recommend`, `/recommend/<id>`)에서도 기록 목록이 보이고 클릭이 동작한다(M6).

- [ ] **Step 12: 커밋**

```
git add "frontend/pages/books/[cnts_id].vue" "frontend/pages/papers/[id].vue" "frontend/pages/recommend/[id].vue" frontend/components/BookChat.vue frontend/components/CitationModal.vue
git commit -m "[Feat] round04b — 상세·추천·부품 기록 분기 제거와 세션 헤더 첨부"
```

---

### Task 25: 잔재 정리

**Files:**
- Delete: `frontend/pages/search-classic.vue` (링크 없이 깨진 채 라우팅 — M9)
- Delete: `frontend/components/ChatHistory.vue` (search-classic 만 사용)
- Delete: `frontend/composables/useSearch.ts` (세션 ID 코드는 `useBrowserId` 로 옮겨짐, 호출부는 search-classic 뿐)
- Delete: `frontend/composables/useSearchHistory.ts` (`useHistory` 로 대체)

- [ ] **Step 1: 호출부 확인 (지우기 전)**

Run: `cd frontend && grep -rn "useSearch\b\|composables/useSearch\"" pages components composables`
Expected: `pages/search-classic.vue` 두 줄(import·호출)만.

Run: `cd frontend && grep -rn "ChatHistory" pages components`
Expected: `pages/search-classic.vue` 만(자기 파일 제외).

Run: `cd frontend && grep -rn "useSearchHistory" pages components composables`
Expected: `composables/useSearchHistory.ts` 자기 정의 한 줄뿐(Task 22~Task 24 로 호출부 0).

하나라도 예상 밖 호출부가 나오면 멈추고 그 호출부를 먼저 옮긴다.

- [ ] **Step 2: 삭제**

```
git rm frontend/pages/search-classic.vue frontend/components/ChatHistory.vue frontend/composables/useSearch.ts frontend/composables/useSearchHistory.ts
```

- [ ] **Step 3: 잔재 식별자·빌드·테스트**

Run: `cd frontend && grep -rn "useSearchHistory\|getSessionId\|restoreSession\|bookHistory\|paperHistory\|updateAiSummary\|skx_search_history\"" pages components composables`
Expected: 출력 없음. (`skx_search_history` 는 `utils/historyStore.ts` 의 이전 상수에만 남는다 — 검색 대상 밖.)

Run: `cd frontend && npm run build`
Expected: 오류 없이 끝난다. Nuxt 자동 import 가 사라진 식별자는 빌드가 아니라 런타임 `ReferenceError` 로 드러나므로 위 grep 이 실제 방어선이다.

Run: `cd frontend && npm test`
Expected: `Test Files  7 passed (7)` · `Tests  92 passed (92)`

- [ ] **Step 4: 수동 확인**

- `/search-classic` → Nuxt 404 페이지.
- 메인·논문·상세·추천을 한 번씩 열어 콘솔에 `ReferenceError` 가 없다.

- [ ] **Step 5: 커밋**

```
git commit -m "[Refactor] round04b — 깨진 search-classic·옛 기록 composable 삭제"
```

---

#### 영역 C1 참고 메모

- **영역 A(기록 API):** `apiBase="/api"` 아래 `/history`·`/history/{id}`·`/history/import` 로 계약 그대로다. `PUT`·`PATCH` 는 `HistoryItemDetail`(snapshot·ai·research 포함)을 돌려주고, `DELETE` 는 204, 없는(또는 남의) id 는 404 다. 프론트는 `DELETE` 404 를 성공으로, `GET`·`PATCH` 404 를 "없음"으로 본다. `import` 응답 `id_map` 의 키는 요청의 `legacy_id` 문자열이다. `limit=30` 을 받는다. `snapshot`·`ai` 는 임의 키의 dict 로 받는다. `{id}` 경로에 UUID 가 아닌 값이 오면 422 — 프론트는 `readHistoryQuery` 에서 걸러 보내지 않는다.
- **영역 A 의 배포:** 프론트(Task 22~Task 25)는 기록 API 가 없는 서버에서도 화면이 깨지지 않는다(`PUT` 404 → 저장만 빠지고 경고). 그래도 배포는 A 와 함께 한다 — 그 사이 v1 이전은 실패해 v1 이 그대로 남고 다음 로드에서 다시 시도한다.
- **영역 C2:** `SearchPlusMenu` 삽입(입력창 세 곳, Task 35)은 Task 22·Task 23 이 바꾼 뒤의 템플릿에 얹는다. 엔터·전송 가로채기는 컴포넌트가 입력 상자에 캡처 단계 리스너로 하므로 페이지의 `handleSearch` 는 고치지 않는다. `pages/index.vue` 논문 분기(`navigateTo('/papers?q=…')`)는 Task 22 에서 손대지 않았다. 딥리서치 기록은 잡을 만들 때만 `upsertResearch` 로 넣는다(남의 잡 주소를 열 때는 부르지 않는다 — 영역 간 계약 참고).
- **기존 코드:** Nuxt 4.4 클라이언트는 앱 인스턴스가 하나라 이벤트 핸들러 안에서도 `useRuntimeConfig()` 가 동작한다(`apiUrl`·`apiHeaders` 가 핸들러에서 불린다). ofetch 1.5 의 `onRequest` 에서 `options.headers` 는 `Headers` 로 정규화돼 있다(그래도 `new Headers(...)` 로 복사해 모양에 기대지 않는다). Nuxt 페이지의 `useRoute()` 는 다른 페이지로 넘어가는 전환 동안 이전 라우트를 유지한다 — 그래도 `restoreFromQuery` 첫 줄에 경로 확인을 두었다.
- **빌드는 타입검사를 하지 않는다**(`vue-tsc` 없음). Task 14~Task 21 커밋 사이에 옛 파일의 IDE 타입 오류가 잠시 남고 Task 25 에서 사라진다. Nuxt 자동 import 로 쓰던 식별자를 지우면 빌드가 아니라 런타임 `ReferenceError` 로 드러나므로 각 페이지 태스크의 grep 이 방어선이다.
- **운영 게이트웨이는 http(비보안 컨텍스트)** 라 `crypto.randomUUID` 가 없다고 보고 `generateUuidV4` 가 `getRandomValues` 로 물러선다. 기록 id 는 spec §4-2 대로 브라우저가 만든 UUID 가 그대로 서버 PK 다.
- **범위에서 뺀 것:** `components/SearchInput.vue` 는 search-classic 삭제 뒤 호출부 0 이 되지만 spec §4-9 삭제 목록에 없어 남겼다(다음 정리 후보). `pages/index.vue` 의 죽은 코드(`fetchPaperSummary`·`fetchReason`·`fetchRelated`·`readSSE`, 논문 분기)는 spec §11 에 따라 그대로 — 호출되지 않으므로 헤더가 없어도 무해하다. `pages/admin/jobs.vue` 는 게이트웨이가 외부 접근을 막는 관리 API 라 헤더를 붙이지 않았다. 도서 상세 → 연관도서 상세 이동은 `h` 를 넘기지 않는다(결과 → 상세만 넘긴다).
- **첫 복원 시점:** spec §4-6 의 `watch(..., {immediate: true})` 대신 첫 복원은 `onMounted`, 이후는 즉시 실행 없는 `watch` 로 했다. setup 은 SSR 에서도 돌아 서버가 그린 랜딩과 어긋나기 때문이다 — 동작(같은 경로 쿼리 변화 복원)은 같다.
- **중복 병합 시각:** 10분 창은 서버 `updated_at`(없으면 `created_at`)과 브라우저 시계를 비교한다. 두 시계가 10분 넘게 어긋나면 병합이 안 될 뿐 오동작은 없다.
- **목록 범위:** 사이드바는 종류마다 최근 30건(`HISTORY_PAGE_SIZE`)을 읽는다. spec 에 "더 보기"가 없어 `nextCursor` 를 쓰는 UI 는 두지 않았다. 로컬 캐시는 종류마다 100건까지 둔다.
- **Dockerfile:** 빌드 단계가 `npm ci` 로 devDependencies 를 설치하므로 vitest 가 빌드 이미지에만 추가된다. 실행 이미지는 `.output` 만 복사하므로 영향이 없다.

---

## 단계 3 — 딥리서치 화면(영역 C2)

### 영역 C2 개요 — 딥리서치 화면

> 이 영역은 spec §6(딥리서치 화면)과 §9 의 프론트 순수 로직 테스트를 구현한다. 모든 경로는 저장소 루트 기준이고, 명령은 `frontend/` 에서 돈다.

**이 영역 코드의 검증 상태 (계획 작성 시 저장소 밖 사본에서 확인, 2026-09-26)**

- 순수 모듈 7개와 테스트 7파일(66개)을 Vitest 3 으로 돌려 전부 통과했다. 통합하면서 테스트를 `tests/unit/` 로 옮기고 import 를 `~/` 별칭으로 바꾼 뒤(정합 1), 기록 영역 테스트와 합친 사본에서 다시 돌려 14파일 158개가 통과했다. 같은 파일을 Nuxt 4 tsconfig 와 같은 엄격 옵션(`strict`·`noUncheckedIndexedAccess`·`verbatimModuleSyntax`)의 `tsc` 로 검사해 오류 0 이다.
- 컴포넌트·페이지·composable 을 넣은 사본에서 `vue-tsc`(= `nuxi typecheck`) 새 파일 오류 0, `nuxt build` 통과. 페이지의 단계별 중간본(Task 31·Task 32·Task 33)도 각각 오류 0 이다.
- 가짜 API 로 개발 서버를 띄워 브라우저로 확인했다: 완료 보고서·인용칩 팝오버(절 대목·쪽수·1/2 넘기기·화면 끝 밀기)·원문 404 안내·탐색 중 라이브 이벤트(카운터·강조 카드·회차)·A/B 전환과 기억·계획 편집과 승인·`+` 메뉴 칩·슬래시 자동 칩·엔터로 잡 생성 후 이동·없는 잡 안내.

**공통 명령**

- 테스트(파일 지정): `cd frontend && npx vitest run tests/unit/<이름>.test.ts`. 테스트 파일은 Task 13 의 설정(`include: ["tests/unit/**/*.test.ts"]`, 별칭 `~/`)을 따라 `frontend/tests/unit/` 에 두고, 대상 모듈을 `~/utils/…`·`~/types/…` 로 import 한다. `utils/*.ts` 끼리는 상대 import(`../types/research`)를 그대로 쓴다 — 아래 `tsc` 단독 검사가 별칭을 모른다.
- 순수 모듈 타입 확인(Vitest 는 타입을 보지 않는다):

  ```bash
  cd frontend
  npx tsc --noEmit --strict --noUncheckedIndexedAccess --verbatimModuleSyntax --isolatedModules \
    --target es2022 --module esnext --moduleResolution bundler --lib es2022,dom --skipLibCheck \
    types/research.ts <utils 파일들>
  ```
  기대: 출력 없음, 종료 코드 0.

- 컴파일 확인(컴포넌트 태스크 끝마다):

  ```bash
  cd frontend
  npx nuxi typecheck 2>&1 | grep "error TS" | grep -v "pages/search-classic.vue"
  npm run build 2>&1 | tail -1
  ```
  기대: 첫 명령은 출력 없음, 둘째는 `└  ✨ Build complete!`.
  - `vue-tsc` 가 설치돼 있지 않아 `nuxi typecheck` 가 처음 한 번 npx 캐시에 내려받는다(package.json 은 바뀌지 않음, 약 15초). 착수 시점 기준선 오류는 `pages/search-classic.vue` 2건뿐이었고 Task 25 가 이 파일을 지웠으므로 이 단계에서는 출력이 없어야 한다(`grep -v` 는 남겨도 무해하다). 영역 C1 이 고친 페이지(Task 21~24)에서 오류가 나오면 그 태스크로 돌아가 고친다.
  - `[Vue] Resolve plugin path failed: vue-router/volar/sfc-route-blocks` 경고는 무해하다(grep 이 거른다).
  - `nuxt build` 는 타입을 보지 않는다(템플릿 컴파일·import 해석만). 기준선 빌드 약 25초.

**선행 조건**

- Task 27 부터: Task 13 이 Vitest 를 설치해 둔다.
- Task 29 부터: Task 15 의 `frontend/composables/useApi.ts`(`useApi`·`apiUrl`·`apiHeaders`)·`frontend/utils/browserId.ts`(`safeLocalStorage`)와 Task 20 의 `frontend/composables/useHistory.ts`(`upsertResearch`·`refresh`)가 있어야 컴파일된다.
- 백엔드 보강(B) 전에도 화면은 동작한다(보강 전 모양을 허용한다). 다만 B 전에는 계획 완료·단계 전이 이벤트가 없어, 승인 대기 전환 등은 새로고침해야 보인다.
- 수동 화면 확인(Task 30 Step 2, Task 35 Step 6)은 영역 A·B 가 올라간 서버가 필요하다. 로컬에는 DB 가 없으므로 운영에 백엔드를 올린 뒤 Task 37 Step 8 에서 한다.

**태스크 순서의 이유**: 타입 → 순수 로직(테스트 우선) → composable → 페이지 골격 → 블록(계획·진행·보고서)을 하나씩 끼움 → 마지막에 입력창 `+`. 입력창을 마지막에 두는 것은, 진입점을 열기 전에 도착지(`/research/<id>`)가 완성돼 있어야 눈으로 끝까지 확인할 수 있기 때문이다.

---

### Task 26: 딥리서치 타입 (`types/research.ts`)

API 응답(`app/api/research.py`)·보고서(`synthesizer.assemble_report`)·SSE 이벤트(spec §5)·화면 상태를 한 파일에 둔다. B 의 보강 키(`round`·`new_papers`·`rounds`·`stats`·`job` 등)는 선택 키로 둬서 보강 전 서버 응답도 타입에 맞는다.

**Files:**
- Create: `frontend/types/research.ts`

- [ ] **Step 1: 타입 파일 작성**

타입만 있는 파일이라 실패하는 테스트 단계는 없다 — 다음 태스크의 테스트가 이 타입을 쓴다.

```ts
// 서버 모양은 app/api/research.py · services/research/synthesizer.assemble_report 가 정본이다.
// 필드를 바꿀 때는 그쪽과 함께 바꾼다 — 한쪽만 바꾸면 화면 분기가 조용히 빗나간다.

export type ResearchStatus =
  | "created"
  | "planning"
  | "awaiting_approval"
  | "approved"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "canceled";
export type ResearchStage = "created" | "planned" | "explored" | "synthesized";
export type StepKind = "plan" | "search" | "synthesize";
export type StepStatus = "pending" | "running" | "done" | "failed";
export type Verdict = "pending" | "sufficient" | "insufficient";
export type SynthSectionStatus = "running" | "done" | "failed";
export type ResearchParams = Record<string, number>;

// ── research_steps.result ──────────────────────────────────
export interface SearchRoundResult {
  round: number;
  query: string;
  found_chunks?: number | null;
  new_papers?: number | null;
  verdict?: Verdict | null;
  note?: string | null;
  next_query?: string | null;
}

export interface SynthSectionResult {
  idx: number;
  status: SynthSectionStatus;
}

export interface StepResult {
  subquestions?: string[];
  queries?: string[];
  adopted?: number;
  verdict?: Verdict;
  note?: string;
  parse_failed?: boolean;
  capped?: number;
  // 보강 전 잡에는 없다 — 화면은 report.trail 이나 queries 로 대신 그린다
  rounds?: SearchRoundResult[];
  // 보강 전 잡은 절 수(number), 보강 후는 절별 상태 목록이다
  sections?: number | SynthSectionResult[];
  sections_total?: number;
  error?: string;
}

export interface ResearchStepRow {
  seq: number;
  kind: StepKind;
  subq_idx: number | null;
  title: string;
  detail?: string | null;
  status: StepStatus;
  // 보강 전 서버의 snapshot 행에는 result 가 없다
  result?: StepResult;
}

// ── 보고서 JSON ────────────────────────────────────────────
export interface ReportRange {
  from: string | null;
  to: string | null;
  n_papers: number;
}

export interface EvidenceMeta {
  title?: string | null;
  personal_author?: string | null;
  series_title?: string | null;
  vol_issue?: string | null;
  pub_date?: string | null;
  kci_citations?: number | null;
  grade?: string | null;
}

export interface ReportChunk {
  chunk_id: string;
  text: string;
  page_start: number;
  page_end: number;
  score: number;
}

export interface ReportEvidence {
  cnts_id: string;
  meta: EvidenceMeta;
  chunks: ReportChunk[];
}

export interface ReportPaper {
  cnts_id: string;
  summary: string;
  evidence: string[];
}

export interface ReportFuture {
  text: string;
  evidence: string[];
}

export interface ReportSection {
  heading: string;
  intro: string;
  papers: ReportPaper[];
  future: ReportFuture[];
  evidence_chunks: Record<string, string[]>;
  chunk_scores: Record<string, number>;
}

export interface TrailItem {
  subquestion: string;
  queries: string[];
  evidence_count: number;
  verdict: Verdict;
  note: string;
  parse_failed: boolean;
  failed: boolean;
  capped: number;
}

export interface CountersPayload {
  papers_reviewed: number;
  evidence_adopted: number;
  rechecks: number;
}

export interface ResearchReport {
  question: string;
  range: Partial<ReportRange> | null;
  sections: ReportSection[];
  evidence: Record<string, ReportEvidence>;
  trail: TrailItem[];
  limitations: string[];
  stats?: CountersPayload;
}

// ── API 응답 ───────────────────────────────────────────────
export interface ResearchJob {
  job_id: string;
  question: string;
  status: ResearchStatus;
  stage: ResearchStage;
  plan: string[] | null;
  report: ResearchReport | null;
  last_error: string | null;
  steps: ResearchStepRow[];
  params?: ResearchParams;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ResearchCreateResponse {
  job_id: string;
  status: "created";
}

export interface ResearchApproveResponse {
  job_id: string;
  status: "approved";
  plan: string[] | null;
}

export interface ResearchRetryResponse {
  job_id: string;
  status: "queued";
  stage: ResearchStage;
}

export interface ResearchCancelResponse {
  job_id: string;
  status: "canceled";
}

// ── SSE 이벤트 (data: 한 줄 JSON, kind 로 분기) ────────────
export interface SnapshotEvent {
  kind: "snapshot";
  steps: ResearchStepRow[];
  job?: {
    status: ResearchStatus;
    stage: ResearchStage;
    plan: string[] | null;
    counters?: CountersPayload;
  };
}

export interface StatusEvent {
  kind: "status";
  status: ResearchStatus;
  stage: ResearchStage;
}

export interface StepEvent {
  kind: "step";
  seq: number;
  step_kind: StepKind;
  subq_idx: number | null;
  title: string;
  detail?: string | null;
  status: StepStatus;
  result?: StepResult;
}

export interface SearchEvent {
  kind: "search";
  subq_idx: number;
  query: string;
  found: number;
  round?: number;
  new_papers?: number;
}

export interface CritiqueEvent {
  kind: "critique";
  subq_idx: number;
  verdict: Verdict;
  note: string;
  adopted: number;
  parse_failed: boolean;
  capped: number;
  round?: number;
  next_query?: string | null;
  will_recheck?: boolean;
}

export interface CountersEvent extends CountersPayload {
  kind: "counters";
}

export interface SynthEvent {
  kind: "synth";
  section_idx: number;
  total: number;
  status: SynthSectionStatus;
}

export interface DoneEvent {
  kind: "done";
  status: "completed";
}

export interface FailedEvent {
  kind: "failed";
  status: "failed";
  error?: string;
}

export interface CanceledEvent {
  kind: "canceled";
  status: "canceled";
}

export type ResearchEvent =
  | SnapshotEvent
  | StatusEvent
  | StepEvent
  | SearchEvent
  | CritiqueEvent
  | CountersEvent
  | SynthEvent
  | DoneEvent
  | FailedEvent
  | CanceledEvent;

// ── 화면 상태 ─────────────────────────────────────────────
export type RoundSource = "rounds" | "trail" | "queries" | "none";

export interface RoundView {
  round: number;
  query: string;
  foundChunks: number | null;
  newPapers: number | null;
  verdict: Verdict | null;
  note: string;
  nextQuery: string | null;
}

export interface SubqView {
  idx: number;
  title: string;
  seq: number | null;
  status: StepStatus;
  rounds: RoundView[];
  verdict: Verdict | null;
  note: string;
  adopted: number | null;
  parseFailed: boolean;
  error: string | null;
}

export interface CountersView {
  papersReviewed: number | null;
  evidenceAdopted: number | null;
  rechecks: number | null;
}

export interface HighlightView {
  subqIdx: number;
  round: number;
  note: string;
  nextQuery: string;
}

export interface SynthSectionView {
  idx: number;
  status: SynthSectionStatus;
}

export interface SynthView {
  seq: number | null;
  status: StepStatus | null;
  total: number;
  sections: SynthSectionView[];
}

export interface ResearchView {
  jobId: string;
  question: string;
  status: ResearchStatus;
  stage: ResearchStage;
  plan: string[];
  params: ResearchParams;
  report: ResearchReport | null;
  lastError: string | null;
  createdAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  steps: ResearchStepRow[];
  subqs: SubqView[];
  counters: CountersView;
  highlight: HighlightView | null;
  synth: SynthView;
  source: RoundSource;
}

export interface OpenPdfPayload {
  cntsId: string;
  title: string;
  page?: number;
}
```

- [ ] **Step 2: 타입 확인**

```bash
cd frontend
npx tsc --noEmit --strict --noUncheckedIndexedAccess --verbatimModuleSyntax --isolatedModules \
  --target es2022 --module esnext --moduleResolution bundler --lib es2022,dom --skipLibCheck \
  types/research.ts
```
기대: 출력 없음.

- [ ] **Step 3: 커밋**

```bash
git add frontend/types/research.ts
git commit -m "[Feat] round04b — 딥리서치 API·SSE·화면 상태 타입"
```

---

### Task 27: 인용 마커 분해·슬래시 파서 (`utils/citations.ts`·`utils/slashCommand.ts`)

보고서 글을 `v-html` 없이 그리기 위해(spec D9) `[E3]` 마커를 글 조각과 칩 조각으로 나눈다. 칩 라벨(`김 2019`)·팝오버 서지 한 줄·절별 대목 고르기·쪽수 표시도 여기 둔다. `+` 메뉴 항목 데이터(`id·label·description·icon·available(kind)` — spec §6-1)와 `/deep-research` 파서는 `slashCommand.ts` 에 둔다.

**Files:**
- Create: `frontend/utils/citations.ts`
- Create: `frontend/utils/slashCommand.ts`
- Test: `frontend/tests/unit/citations.test.ts`
- Test: `frontend/tests/unit/slashCommand.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
// frontend/tests/unit/citations.test.ts
import { describe, expect, it } from "vitest";
import type { ReportEvidence, ReportSection } from "~/types/research";
import { citeChunks, citeLabel, metaLine, pageLabel, pdfPage, splitAuthors, splitCitations } from "~/utils/citations";

function chunk(id: string, page = 3) {
  return { chunk_id: id, text: `본문 ${id}`, page_start: page, page_end: page, score: 0.5 };
}

const evidence: ReportEvidence = {
  cnts_id: "CNTS-1",
  meta: { title: "AI 윤리 교육", personal_author: "김철수; 이영희", pub_date: "2019-03" },
  chunks: [chunk("c1"), chunk("c2"), chunk("c3")],
};

function section(map: Record<string, string[]>): ReportSection {
  return { heading: "h", intro: "", papers: [], future: [], evidence_chunks: map, chunk_scores: {} };
}

describe("splitCitations", () => {
  it("마커를 칩 조각으로, 나머지를 글 조각으로 나눈다", () => {
    expect(splitCitations("효과가 있다 [E1] 반면[E2][E3].")).toEqual([
      { type: "text", text: "효과가 있다 " },
      { type: "cite", eid: "E1" },
      { type: "text", text: " 반면" },
      { type: "cite", eid: "E2" },
      { type: "cite", eid: "E3" },
      { type: "text", text: "." },
    ]);
  });

  it("마커가 없으면 글 한 조각, 빈 글이면 빈 배열이다", () => {
    expect(splitCitations("근거 없음")).toEqual([{ type: "text", text: "근거 없음" }]);
    expect(splitCitations("")).toEqual([]);
  });

  it("표준형이 아닌 괄호는 글자 그대로 둔다", () => {
    expect(splitCitations("[e1] [E 2] [표 1]")).toEqual([{ type: "text", text: "[e1] [E 2] [표 1]" }]);
  });

  it("글 속 HTML 은 해석하지 않고 글 조각으로 남긴다", () => {
    expect(splitCitations("<img src=x onerror=alert(1)>[E1]")).toEqual([
      { type: "text", text: "<img src=x onerror=alert(1)>" },
      { type: "cite", eid: "E1" },
    ]);
  });
});

describe("splitAuthors", () => {
  it("세미콜론, 또는 이름마다 쉼표로 가른 여러 저자를 나눈다", () => {
    expect(splitAuthors("김철수; 이영희")).toEqual(["김철수", "이영희"]);
    expect(splitAuthors("김철수, 이영희")).toEqual(["김철수", "이영희"]);
    expect(splitAuthors("John Smith, Jane Doe")).toEqual(["John Smith", "Jane Doe"]);
  });

  it("성·이름을 쉼표로 가른 한 사람은 나누지 않는다", () => {
    expect(splitAuthors("Smith, John")).toEqual(["Smith, John"]);
    expect(splitAuthors("")).toEqual([]);
    expect(splitAuthors(null)).toEqual([]);
  });
});

describe("citeLabel", () => {
  it("한글 이름은 성과 연도로 줄인다", () => {
    expect(citeLabel(evidence.meta, "E1")).toBe("김 2019");
  });

  it("영문 이름은 성(쉼표 앞 또는 마지막 낱말)을 쓴다", () => {
    expect(citeLabel({ personal_author: "Smith, John", pub_date: "2020" }, "E2")).toBe("Smith 2020");
    expect(citeLabel({ personal_author: "John Smith", pub_date: "2020" }, "E2")).toBe("Smith 2020");
  });

  it("저자가 없으면 근거 번호, 연도가 없으면 성만 쓴다", () => {
    expect(citeLabel({ pub_date: "2020" }, "E3")).toBe("E3");
    expect(citeLabel({ personal_author: "박민수 외 2인" }, "E4")).toBe("박");
    expect(citeLabel(undefined, "E5")).toBe("E5");
  });
});

describe("metaLine", () => {
  it("비어 있는 칸을 빼고 가운뎃점으로 잇는다", () => {
    expect(metaLine({
      personal_author: "김철수", series_title: "교육학연구", vol_issue: "12(3)",
      pub_date: "2019-03", kci_citations: 0, grade: "KCI등재",
    })).toBe("김철수 · 교육학연구 12(3) · 2019 · 피인용 0 · KCI등재");
    expect(metaLine({ title: "제목만" })).toBe("");
  });
});

describe("pageLabel·pdfPage", () => {
  it("0 쪽은 첫 쪽과 구분할 수 없어 쪽 정보 없음으로 둔다", () => {
    expect(pageLabel({ page_start: 0, page_end: 0 })).toBe("쪽 정보 없음");
    expect(pdfPage({ page_start: 0 })).toBeUndefined();
  });

  it("0부터 센 쪽수를 1부터 세어 보여 준다", () => {
    expect(pageLabel({ page_start: 4, page_end: 4 })).toBe("p.5");
    expect(pageLabel({ page_start: 4, page_end: 6 })).toBe("p.5–7");
    expect(pdfPage({ page_start: 4 })).toBe(5);
  });
});

describe("citeChunks", () => {
  it("그 절에서 매칭된 대목만 근거의 점수 순서대로 고른다", () => {
    expect(citeChunks(section({ E1: ["c3", "c1"] }), evidence, "E1").map((c) => c.chunk_id)).toEqual(["c1", "c3"]);
  });

  it("절 매핑이 없거나 모르는 대목만 가리키면 근거의 대목 전부를 쓴다", () => {
    expect(citeChunks(section({}), evidence, "E1")).toHaveLength(3);
    expect(citeChunks(section({ E1: ["zz"] }), evidence, "E1")).toHaveLength(3);
    expect(citeChunks(undefined, evidence, "E1")).toHaveLength(3);
  });

  it("근거가 없으면 빈 배열이다", () => {
    expect(citeChunks(section({ E9: ["c1"] }), undefined, "E9")).toEqual([]);
  });
});
```

```ts
// frontend/tests/unit/slashCommand.test.ts
import { describe, expect, it } from "vitest";
import { modesFor, parseSlash, shouldAutoChip } from "~/utils/slashCommand";

describe("parseSlash", () => {
  it("명령 뒤의 글을 질문으로 떼어 낸다", () => {
    expect(parseSlash("/deep-research AI 윤리 교육의 효과")).toEqual({ mode: "deep-research", text: "AI 윤리 교육의 효과" });
  });

  it("앞뒤 공백과 대소문자를 가리지 않는다", () => {
    expect(parseSlash("  /Deep-Research   질문")).toEqual({ mode: "deep-research", text: "질문" });
  });

  it("명령만 있으면 질문은 빈 글이다", () => {
    expect(parseSlash("/deep-research")).toEqual({ mode: "deep-research", text: "" });
  });

  it("명령 이름에 글자가 이어 붙거나 명령이 가운데 있으면 명령이 아니다", () => {
    expect(parseSlash("/deep-researcher x")).toEqual({ mode: null, text: "/deep-researcher x" });
    expect(parseSlash("AI /deep-research")).toEqual({ mode: null, text: "AI /deep-research" });
  });
});

describe("shouldAutoChip", () => {
  it("명령 뒤에 공백이나 글이 붙어야 칩으로 바꾼다", () => {
    expect(shouldAutoChip("/deep-research")).toBe(false);
    expect(shouldAutoChip("/deep-research ")).toBe(true);
    expect(shouldAutoChip("/deep-research 질문")).toBe(true);
    expect(shouldAutoChip("질문")).toBe(false);
  });
});

describe("modesFor", () => {
  it("딥리서치는 논문 입력창에만 있다", () => {
    expect(modesFor("paper").map((m) => m.id)).toEqual(["deep-research"]);
    expect(modesFor("book")).toEqual([]);
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd frontend && npx vitest run tests/unit/citations.test.ts tests/unit/slashCommand.test.ts
```
기대: 두 파일 모두 수집 단계에서 실패 —
`Error: Cannot find module '~/utils/citations' imported from '.../frontend/tests/unit/citations.test.ts'.`
(slashCommand 도 같은 모양), `Test Files  2 failed (2)`.

- [ ] **Step 3: 최소 구현**

```ts
// frontend/utils/citations.ts
import type { EvidenceMeta, ReportChunk, ReportEvidence, ReportSection } from "../types/research";

export type CitationPart = { type: "text"; text: string } | { type: "cite"; eid: string };

// 서버(services/research/citations.bind_markers)가 인식한 표기를 전부 [E3] 한 모양으로
// 다시 써서 보낸다 — 화면은 이 표준형만 칩으로 바꾸고 나머지는 글자 그대로 둔다.
const MARKER = /\[(E\d+)\]/g;
const YEAR = /(19|20)\d{2}/;
const HANGUL_NAME = /^[가-힣\s]+$/;

export function splitCitations(text: string): CitationPart[] {
  const parts: CitationPart[] = [];
  let last = 0;
  for (const m of text.matchAll(MARKER)) {
    const at = m.index ?? 0;
    if (at > last) parts.push({ type: "text", text: text.slice(last, at) });
    parts.push({ type: "cite", eid: m[1] ?? "" });
    last = at + m[0].length;
  }
  if (last < text.length) parts.push({ type: "text", text: text.slice(last) });
  return parts;
}

export function pubYear(pubDate: string | null | undefined): string | null {
  const m = YEAR.exec(pubDate ?? "");
  return m ? m[0] : null;
}

export function splitAuthors(personal: string | null | undefined): string[] {
  const raw = (personal ?? "").trim();
  if (!raw) return [];
  const bySemicolon = raw.split(/[;|·]/).map((s) => s.trim()).filter(Boolean);
  if (bySemicolon.length > 1) return bySemicolon;
  const byComma = raw.split(",").map((s) => s.trim()).filter(Boolean);
  // "Smith, John" 처럼 성과 이름을 쉼표로 가른 한 사람은 쪼개지 않는다 — 조각마다
  // 한글이 있거나 띄어 쓴 이름일 때만 여러 저자로 본다
  const allNames = byComma.every((s) => /[가-힣]/.test(s) || /\s/.test(s));
  return byComma.length > 1 && allNames ? byComma : [raw];
}

export function firstAuthorSurname(personal: string | null | undefined): string | null {
  const first = splitAuthors(personal)[0]?.replace(/\s*외\s*\d*\s*인?\s*$/, "").trim();
  if (!first) return null;
  if (HANGUL_NAME.test(first)) return first.replace(/\s/g, "").slice(0, 1);
  if (first.includes(",")) return first.split(",")[0]?.trim() || first;
  const tokens = first.split(/\s+/);
  return tokens[tokens.length - 1] ?? first;
}

export function citeLabel(meta: EvidenceMeta | undefined, eid: string): string {
  const who = firstAuthorSurname(meta?.personal_author);
  const year = pubYear(meta?.pub_date);
  if (who && year) return `${who} ${year}`;
  return who ?? eid;
}

export function metaLine(meta: EvidenceMeta | undefined): string {
  if (!meta) return "";
  const journal = [meta.series_title, meta.vol_issue].filter((s) => s && s.trim()).join(" ");
  const citations = meta.kci_citations != null ? `피인용 ${meta.kci_citations}` : "";
  return [meta.personal_author ?? "", journal, pubYear(meta.pub_date) ?? "", citations, meta.grade ?? ""]
    .map((s) => s.trim())
    .filter(Boolean)
    .join(" · ");
}

// 한 논문이 여러 절에 실리면 evidence.chunks 는 그 합집합이다 — 칩은 자기 절에서
// 매칭된 대목만 보여 줘야 절 내용과 맞는다. 매핑이 없으면(옛 보고서) 전부 보여 준다.
export function citeChunks(
  section: ReportSection | undefined,
  evidence: ReportEvidence | undefined,
  eid: string,
): ReportChunk[] {
  if (!evidence) return [];
  const ids = section?.evidence_chunks?.[eid];
  if (!ids || !ids.length) return evidence.chunks;
  const wanted = new Set(ids);
  const picked = evidence.chunks.filter((c) => wanted.has(c.chunk_id));
  return picked.length ? picked : evidence.chunks;
}

// 저장된 쪽수는 0부터 센다(ingestion/extractor). 0 은 "첫 쪽"과 "쪽 정보 없음"
// (indexer 의 `or 0`)이 겹쳐 구분할 수 없으므로 쪽을 표시하지 않는다.
export function pageLabel(chunk: Pick<ReportChunk, "page_start" | "page_end">): string {
  if (!chunk.page_start || chunk.page_start <= 0) return "쪽 정보 없음";
  const start = chunk.page_start + 1;
  const end = chunk.page_end + 1;
  return end > start ? `p.${start}–${end}` : `p.${start}`;
}

export function pdfPage(chunk: Pick<ReportChunk, "page_start">): number | undefined {
  return chunk.page_start > 0 ? chunk.page_start + 1 : undefined;
}
```

```ts
// frontend/utils/slashCommand.ts
export type SearchModeId = "deep-research";
export type SearchInputKind = "book" | "paper";

export interface SearchMode {
  id: SearchModeId;
  label: string;
  description: string;
  icon: string;
  slash: string;
  placeholder: string;
  available: (kind: SearchInputKind) => boolean;
}

// + 메뉴 항목의 정본. 새 모드는 여기 한 줄을 더하면 메뉴·칩·슬래시가 함께 생긴다.
export const SEARCH_MODES: readonly SearchMode[] = [
  {
    id: "deep-research",
    label: "딥리서치",
    description: "질문을 하위질문으로 나눠 논문을 찾고, 스스로 점검한 뒤 인용이 달린 보고서를 씁니다",
    icon: "/img/ico-ai-related.svg",
    slash: "/deep-research",
    placeholder: "연구 질문을 입력하세요",
    available: (kind) => kind === "paper",
  },
];

export function modesFor(kind: SearchInputKind): SearchMode[] {
  return SEARCH_MODES.filter((m) => m.available(kind));
}

export function parseSlash(input: string): { mode: SearchModeId | null; text: string } {
  const lead = input.trimStart();
  for (const m of SEARCH_MODES) {
    if (lead.slice(0, m.slash.length).toLowerCase() !== m.slash) continue;
    const rest = lead.slice(m.slash.length);
    if (rest !== "" && !/^\s/.test(rest)) continue;
    return { mode: m.id, text: rest.trimStart() };
  }
  return { mode: null, text: input };
}

// 명령 뒤에 공백이나 글이 붙었을 때만 칩으로 바꾼다 — "/deep-research" 까지만 친
// 순간 바꾸면 비슷한 이름의 다른 명령을 치는 중일 수 있다.
export function shouldAutoChip(input: string): boolean {
  const { mode, text } = parseSlash(input);
  return mode !== null && (text !== "" || /\s$/.test(input));
}
```

- [ ] **Step 4: 실행해 통과 확인**

```bash
cd frontend && npx vitest run tests/unit/citations.test.ts tests/unit/slashCommand.test.ts
```
기대: `Test Files  2 passed (2)`, `Tests  21 passed (21)`.

```bash
cd frontend
npx tsc --noEmit --strict --noUncheckedIndexedAccess --verbatimModuleSyntax --isolatedModules \
  --target es2022 --module esnext --moduleResolution bundler --lib es2022,dom --skipLibCheck \
  types/research.ts utils/citations.ts utils/slashCommand.ts
```
기대: 출력 없음.

- [ ] **Step 5: 커밋**

```bash
git add frontend/utils/citations.ts frontend/utils/slashCommand.ts frontend/tests/unit/citations.test.ts frontend/tests/unit/slashCommand.test.ts
git commit -m "[Feat] round04b — 인용 마커 분해·칩 라벨·슬래시 파서와 테스트"
```

---

### Task 28: SSE 이벤트 리듀서 (`utils/researchEvents.ts`)

`initialResearchView(job)` 로 GET 응답을 화면 상태로 바꾸고, `applyResearchEvent(view, event)` 가 이벤트 하나를 반영한 **새** 상태를 돌려준다(순수 함수 — 테스트가 쉽고 Vue 에서는 `shallowRef` 에 통째로 대입한다).

설계 요점:
- 진행 패널의 하위질문은 같은 `(kind, subq_idx)` 중 `seq` 가 가장 큰 행이 현재 시도다(round04a spec §2-3). 새 시도(seq 증가)가 오면 이전 시도의 라이브 회차를 버린다.
- 회차 출처 우선순위: 단계 결과의 `rounds`(보강 후) → `report.trail`(보강 전 완료 잡, spec §5-2) → 단계 결과의 `queries`(보강 전 실패 잡). 결과에 아직 없는 뒤 회차는 라이브로 받은 것을 남긴다.
- 재접속 snapshot 이 결과 없는 행(보강 전 서버)을 보내도 이미 아는 결과를 지우지 않는다. 종합 절 상태는 더 나아간 쪽(done·failed > running)을 남긴다.
- 강조 카드: `critique` 가 `will_recheck && next_query` 일 때. 탐색 중 다시 붙으면 저장된 회차에서 되살린다.
- `refreshView` 는 종료 이벤트·409 뒤 GET 으로 맞출 때 쓴다 — 보고서 없는 잡(실패·취소)은 서버가 카운터를 주지 않으므로 라이브 카운터를 지킨다.
- `researchPhase` 가 상태를 화면 단계로 바꾼다(spec §6-2 표). `running` 은 `stage=explored` 이거나 종합 단계가 도는 중이면 종합, 아니면 탐색.

**Files:**
- Create: `frontend/utils/researchEvents.ts`
- Test: `frontend/tests/unit/researchEvents.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
// frontend/tests/unit/researchEvents.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchEvent, ResearchJob, ResearchReport, ResearchStepRow } from "~/types/research";
import {
  applyResearchEvent,
  initialResearchView,
  isTerminalEvent,
  refreshView,
  researchPhase,
  subqStatusLabel,
  synthProgress,
  withPlan,
} from "~/utils/researchEvents";

function job(over: Partial<ResearchJob> = {}): ResearchJob {
  return {
    job_id: "11111111-1111-4111-8111-111111111111",
    question: "AI 윤리 교육의 효과",
    status: "running",
    stage: "planned",
    plan: ["효과 측정", "교사 인식"],
    report: null,
    last_error: null,
    steps: [],
    params: { max_subquestions: 6 },
    created_at: "2026-09-26T01:00:00Z",
    started_at: "2026-09-26T01:01:00Z",
    finished_at: null,
    ...over,
  };
}

function step(over: Partial<ResearchStepRow>): ResearchStepRow {
  return { seq: 0, kind: "plan", subq_idx: null, title: "연구 계획 수립", detail: null, status: "done", result: {}, ...over };
}

function run(events: ResearchEvent[], start = initialResearchView(job())) {
  return events.reduce((view, event) => applyResearchEvent(view, event), start);
}

function oldReport(over: Partial<ResearchReport> = {}): ResearchReport {
  return {
    question: "AI 윤리 교육의 효과",
    range: { from: "2002", to: "2026", n_papers: 100 },
    sections: [],
    evidence: {
      E1: { cnts_id: "C1", meta: { title: "t" }, chunks: [] },
    },
    trail: [{
      subquestion: "효과 측정", queries: ["효과 측정", "초등 효과"], evidence_count: 4,
      verdict: "sufficient", note: "충분하다", parse_failed: false, failed: false, capped: 0,
    }],
    limitations: [],
    ...over,
  };
}

const SEARCH_STARTED: ResearchEvent = {
  kind: "step", seq: 1, step_kind: "search", subq_idx: 0, title: "효과 측정", status: "running",
};

describe("initialResearchView", () => {
  it("승인 대기 잡은 계획을 대기 중인 하위질문으로 펼친다", () => {
    const v = initialResearchView(job({ status: "awaiting_approval", steps: [step({ result: { subquestions: ["효과 측정", "교사 인식"] } })] }));
    expect(researchPhase(v)).toBe("awaiting");
    expect(v.subqs.map((s) => [s.idx, s.title, s.status])).toEqual([[0, "효과 측정", "pending"], [1, "교사 인식", "pending"]]);
  });

  it("잡의 plan 이 비어 있으면 계획 단계 결과에서 읽는다", () => {
    const v = initialResearchView(job({ status: "awaiting_approval", plan: null, steps: [step({ result: { subquestions: ["가", "나"] } })] }));
    expect(v.plan).toEqual(["가", "나"]);
  });

  it("보고서 stats 가 있으면 카운터로 쓴다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized",
      report: oldReport({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 } }),
    }));
    expect(v.counters).toEqual({ papersReviewed: 38, evidenceAdopted: 11, rechecks: 2 });
  });
});

describe("applyResearchEvent — 탐색", () => {
  it("검색·점검 이벤트로 회차를 쌓고 재검색 장면을 강조한다", () => {
    const v = run([
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      {
        kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 3,
        parse_failed: false, capped: 0, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
      },
      { kind: "search", subq_idx: 0, query: "초등 AI 윤리 교육 효과", found: 9, round: 2, new_papers: 4 },
    ]);
    const sq = v.subqs[0]!;
    expect(sq.status).toBe("running");
    expect(sq.rounds).toEqual([
      { round: 1, query: "효과 측정", foundChunks: 12, newPapers: 5, verdict: "insufficient", note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과" },
      { round: 2, query: "초등 AI 윤리 교육 효과", foundChunks: 9, newPapers: 4, verdict: null, note: "", nextQuery: null },
    ]);
    expect(v.highlight).toEqual({ subqIdx: 0, round: 1, note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과" });
    expect(researchPhase(v)).toBe("exploring");
    expect(subqStatusLabel(sq)).toBe("탐색 중 · 2회차");
  });

  it("round 가 없는 이벤트(보강 전 서버)도 순서대로 회차를 매긴다", () => {
    const v = run([
      { kind: "search", subq_idx: 1, query: "교사 인식", found: 3 },
      { kind: "critique", subq_idx: 1, verdict: "insufficient", note: "", adopted: 1, parse_failed: false, capped: 0 },
      { kind: "search", subq_idx: 1, query: "교사 태도", found: 4 },
    ]);
    expect(v.subqs[1]!.rounds.map((r) => [r.round, r.query, r.verdict])).toEqual([[1, "교사 인식", "insufficient"], [2, "교사 태도", null]]);
  });

  it("재검색하지 않는 점검은 강조 카드를 만들지 않는다", () => {
    const v = run([
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      { kind: "critique", subq_idx: 0, verdict: "sufficient", note: "충분", adopted: 6, parse_failed: false, capped: 0, round: 1, next_query: null, will_recheck: false },
    ]);
    expect(v.highlight).toBeNull();
    expect(v.subqs[0]!.adopted).toBe(6);
  });

  it("counters 이벤트는 카운터를 통째로 바꾼다", () => {
    const v = run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]);
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 7, rechecks: 1 });
  });

  it("같은 하위질문의 새 시도는 이전 시도의 회차를 버린다", () => {
    const v = run([
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      { kind: "step", seq: 5, step_kind: "search", subq_idx: 0, title: "효과 측정", status: "running" },
    ]);
    expect(v.subqs[0]!.seq).toBe(5);
    expect(v.subqs[0]!.rounds).toEqual([]);
  });

  it("단계 결과의 rounds 가 라이브 회차보다 앞서고, 결과에 없는 뒤 회차는 남긴다", () => {
    const v = run([
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      { kind: "search", subq_idx: 0, query: "초등 효과", found: 9, round: 2, new_papers: 4 },
      {
        kind: "step", seq: 1, step_kind: "search", subq_idx: 0, title: "효과 측정", status: "running",
        result: { rounds: [{ round: 1, query: "효과 측정", found_chunks: 12, new_papers: 5, verdict: "insufficient", note: "저장본", next_query: "초등 효과" }] },
      },
    ]);
    expect(v.subqs[0]!.rounds.map((r) => [r.round, r.note])).toEqual([[1, "저장본"], [2, ""]]);
    expect(v.source).toBe("rounds");
  });
});

describe("applyResearchEvent — snapshot·상태", () => {
  it("snapshot 이 결과 없는 행(보강 전 서버)을 보내도 이미 아는 결과를 지우지 않는다", () => {
    const start = initialResearchView(job({
      steps: [step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "running", result: { rounds: [{ round: 1, query: "효과 측정" }] } })],
    }));
    const v = applyResearchEvent(start, {
      kind: "snapshot",
      steps: [{ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", detail: null, status: "running" }],
    });
    expect(v.subqs[0]!.rounds.map((r) => r.query)).toEqual(["효과 측정"]);
  });

  it("snapshot 의 job 으로 상태·계획·카운터를 맞춘다", () => {
    const v = applyResearchEvent(initialResearchView(job({ status: "planning", plan: null })), {
      kind: "snapshot",
      steps: [step({ result: { subquestions: ["가", "나", "다"] } })],
      job: { status: "awaiting_approval", stage: "planned", plan: ["가", "나", "다"], counters: { papers_reviewed: 0, evidence_adopted: 0, rechecks: 0 } },
    });
    expect(researchPhase(v)).toBe("awaiting");
    expect(v.subqs).toHaveLength(3);
    expect(v.counters.papersReviewed).toBe(0);
  });

  it("탐색 중 다시 붙으면 저장된 회차에서 강조 카드를 되살린다", () => {
    const v = applyResearchEvent(initialResearchView(job()), {
      kind: "snapshot",
      steps: [step({
        seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", status: "running",
        result: { rounds: [{ round: 1, query: "효과 측정", verdict: "insufficient", note: "부족", next_query: "초등 효과" }] },
      })],
    });
    expect(v.highlight).toEqual({ subqIdx: 0, round: 1, note: "부족", nextQuery: "초등 효과" });
  });

  it("status 이벤트는 상태·단계를 바꾸고, 다시 도는 잡이면 실패 사유를 지운다", () => {
    const failed = initialResearchView(job({ status: "failed", last_error: "종합 실패" }));
    const v = applyResearchEvent(failed, { kind: "status", status: "queued", stage: "explored" });
    expect(v.status).toBe("queued");
    expect(v.lastError).toBeNull();
    expect(researchPhase(v)).toBe("queued");
  });

  it("종료 이벤트는 상태를 끝내고 실패 사유를 남긴다", () => {
    const failed: ResearchEvent = { kind: "failed", status: "failed", error: "모든 하위질문 탐색이 오류로 실패했다" };
    const v = run([failed]);
    expect(v.status).toBe("failed");
    expect(v.lastError).toBe("모든 하위질문 탐색이 오류로 실패했다");
    expect(isTerminalEvent(failed)).toBe(true);
    expect(isTerminalEvent({ kind: "search" })).toBe(false);
  });

  it("모르는 이벤트는 그대로 둔다", () => {
    const start = initialResearchView(job());
    expect(applyResearchEvent(start, { kind: "ping" } as unknown as ResearchEvent)).toBe(start);
  });

  it("상태별 화면 단계", () => {
    const phase = (status: ResearchJob["status"], stage: ResearchJob["stage"] = "planned") =>
      researchPhase(initialResearchView(job({ status, stage })));
    expect(phase("created", "created")).toBe("planning");
    expect(phase("approved")).toBe("queued");
    expect(phase("running", "explored")).toBe("synthesizing");
    expect(phase("canceled")).toBe("canceled");
  });
});

describe("applyResearchEvent — 종합", () => {
  it("절 이벤트로 진행을 센다", () => {
    const v = run([
      { kind: "status", status: "running", stage: "explored" },
      { kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running" },
      { kind: "synth", section_idx: 0, total: 3, status: "running" },
      { kind: "synth", section_idx: 0, total: 3, status: "done" },
      { kind: "synth", section_idx: 1, total: 3, status: "running" },
    ]);
    expect(researchPhase(v)).toBe("synthesizing");
    expect(synthProgress(v)).toEqual({ current: 2, total: 3 });
  });

  it("다시 받은 snapshot 이 앞선 절 상태를 되돌리지 않는다", () => {
    const live = run([
      { kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running" },
      { kind: "synth", section_idx: 0, total: 2, status: "done" },
    ]);
    const v = applyResearchEvent(live, {
      kind: "snapshot",
      steps: [step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: { sections_total: 2, sections: [{ idx: 0, status: "running" }] } })],
    });
    expect(v.synth.sections).toEqual([{ idx: 0, status: "done" }]);
  });

  it("보강 전 종합 결과(절 수)도 완료로 센다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized",
      steps: [step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "done", result: { sections: 3 } })],
    }));
    expect(synthProgress(v)).toEqual({ current: 3, total: 3 });
  });
});

describe("보강 전 잡", () => {
  it("단계 결과에 rounds 가 없으면 report.trail 로 회차를 대신 보여 준다", () => {
    const v = initialResearchView(job({
      status: "completed", stage: "synthesized", plan: ["효과 측정"], report: oldReport(),
      steps: [
        step({ seq: 0, result: { subquestions: ["효과 측정"] } }),
        step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { queries: ["효과 측정", "초등 효과"], adopted: 4, verdict: "sufficient", note: "충분하다" } }),
      ],
    }));
    expect(v.source).toBe("trail");
    expect(v.subqs[0]!.rounds).toEqual([
      { round: 1, query: "효과 측정", foundChunks: null, newPapers: null, verdict: "insufficient", note: "", nextQuery: "초등 효과" },
      { round: 2, query: "초등 효과", foundChunks: null, newPapers: null, verdict: "sufficient", note: "충분하다", nextQuery: null },
    ]);
    expect(v.counters).toEqual({ papersReviewed: null, evidenceAdopted: 1, rechecks: 1 });
    expect(v.highlight).toBeNull();
  });

  it("보고서가 없는 옛 실패 잡은 단계 결과의 queries 로 회차를 만든다", () => {
    const v = initialResearchView(job({
      status: "failed", last_error: "x", plan: ["효과 측정"],
      steps: [step({ seq: 1, kind: "search", subq_idx: 0, title: "효과 측정", result: { queries: ["효과 측정"], verdict: "sufficient", note: "" } })],
    }));
    expect(v.source).toBe("queries");
    expect(v.subqs[0]!.rounds.map((r) => r.query)).toEqual(["효과 측정"]);
  });
});

describe("refreshView·withPlan", () => {
  it("GET 재조회는 보고서가 없을 때 라이브 카운터를 잃지 않는다", () => {
    const live = run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]);
    const v = refreshView(live, job({ status: "failed", last_error: "종합 실패" }));
    expect(v.status).toBe("failed");
    expect(v.counters.papersReviewed).toBe(20);
  });

  it("다른 잡의 응답이면 이전 화면을 섞지 않는다", () => {
    const live = run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]);
    const v = refreshView(live, job({ job_id: "22222222-2222-4222-8222-222222222222", status: "failed" }));
    expect(v.counters.papersReviewed).toBeNull();
  });

  it("승인한 계획으로 하위질문 제목을 바꾼다", () => {
    const v = withPlan(initialResearchView(job({ status: "awaiting_approval" })), ["새 질문 하나"]);
    expect(v.subqs.map((s) => s.title)).toEqual(["새 질문 하나"]);
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd frontend && npx vitest run tests/unit/researchEvents.test.ts
```
기대: `Error: Cannot find module '~/utils/researchEvents' imported from '.../frontend/tests/unit/researchEvents.test.ts'.`, `Test Files  1 failed (1)`.

- [ ] **Step 3: 최소 구현**

```ts
// frontend/utils/researchEvents.ts
import type {
  CountersPayload,
  CountersView,
  CritiqueEvent,
  HighlightView,
  ResearchEvent,
  ResearchJob,
  ResearchReport,
  ResearchStatus,
  ResearchStepRow,
  ResearchView,
  RoundSource,
  RoundView,
  SearchEvent,
  SearchRoundResult,
  SnapshotEvent,
  StepEvent,
  StepKind,
  StepResult,
  StepStatus,
  SubqView,
  SynthSectionStatus,
  SynthSectionView,
  SynthView,
  TrailItem,
  Verdict,
} from "../types/research";

export type ResearchPhase =
  | "planning"
  | "awaiting"
  | "queued"
  | "exploring"
  | "synthesizing"
  | "completed"
  | "failed"
  | "canceled";

export const TERMINAL_STATUSES: readonly ResearchStatus[] = ["completed", "failed", "canceled"];

const EMPTY_COUNTERS: CountersView = { papersReviewed: null, evidenceAdopted: null, rechecks: null };
const EMPTY_SYNTH: SynthView = { seq: null, status: null, total: 0, sections: [] };
// 끊겼다 다시 받은 snapshot 이 라이브로 받은 절 상태를 되돌리지 않게, 더 나아간 쪽을 남긴다
const SECTION_RANK: Record<SynthSectionStatus, number> = { running: 1, done: 2, failed: 2 };
const SOURCE_ORDER: readonly RoundSource[] = ["rounds", "trail", "queries"];

const PHASE_LABEL: Record<ResearchPhase, string> = {
  planning: "계획 수립 중",
  awaiting: "승인 대기",
  queued: "대기열",
  exploring: "탐색 중",
  synthesizing: "보고서 작성 중",
  completed: "완료",
  failed: "실패",
  canceled: "취소됨",
};

const VERDICT_LABEL: Record<Verdict, string> = {
  pending: "점검 중",
  sufficient: "근거 충분",
  insufficient: "근거 부족",
};

export function isTerminalStatus(status: ResearchStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function isTerminalEvent(event: { kind: string }): boolean {
  return event.kind === "done" || event.kind === "failed" || event.kind === "canceled";
}

export function researchPhase(view: ResearchView): ResearchPhase {
  switch (view.status) {
    case "created":
    case "planning":
      return "planning";
    case "awaiting_approval":
      return "awaiting";
    case "approved":
    case "queued":
      return "queued";
    case "running":
      // stage=explored 로 재시도한 잡은 종합 단계 행이 생기기 전부터 종합 중이다
      return view.stage === "explored" || view.synth.status === "running" ? "synthesizing" : "exploring";
    default:
      return view.status;
  }
}

export function phaseLabel(phase: ResearchPhase): string {
  return PHASE_LABEL[phase];
}

export function verdictLabel(verdict: Verdict): string {
  return VERDICT_LABEL[verdict];
}

export function subqStatusLabel(sq: SubqView): string {
  switch (sq.status) {
    case "pending":
      return "대기";
    case "running":
      return sq.rounds.length ? `탐색 중 · ${sq.rounds.length}회차` : "탐색 중";
    case "done":
      return sq.adopted !== null ? `완료 · 근거 ${sq.adopted}편` : "완료";
    case "failed":
      return "오류";
  }
}

export function synthProgress(view: ResearchView): { current: number; total: number } {
  const { total, sections, status } = view.synth;
  if (!total) return { current: 0, total: 0 };
  const finished = status === "done" && !sections.length
    ? total
    : sections.filter((s) => s.status !== "running").length;
  const running = sections.some((s) => s.status === "running") ? 1 : 0;
  return { current: Math.min(total, Math.max(1, finished + running)), total };
}

export function initialResearchView(job: ResearchJob): ResearchView {
  const steps = [...(job.steps ?? [])].sort(bySeq);
  const view = rebuild({
    jobId: job.job_id,
    question: job.question,
    status: job.status,
    stage: job.stage,
    plan: job.plan?.length ? job.plan : planFromSteps(steps),
    params: job.params ?? {},
    report: job.report ?? null,
    lastError: job.last_error ?? null,
    createdAt: job.created_at ?? null,
    startedAt: job.started_at ?? null,
    finishedAt: job.finished_at ?? null,
    steps,
    subqs: [],
    counters: countersFromReport(job.report ?? null),
    highlight: null,
    synth: { ...EMPTY_SYNTH },
    source: "none",
  });
  return view.status === "running" ? { ...view, highlight: latestHighlight(view.subqs) } : view;
}

// 종료 이벤트 뒤·409 뒤 GET 으로 다시 맞출 때 쓴다. 보고서가 없는 잡(실패·취소)은
// 서버가 카운터를 돌려주지 않으므로 라이브로 받은 값을 버리지 않는다.
export function refreshView(prev: ResearchView | null, job: ResearchJob): ResearchView {
  const fresh = initialResearchView(job);
  if (!prev || prev.jobId !== fresh.jobId) return fresh;
  const merged = rebuild({ ...fresh, subqs: prev.subqs, synth: prev.synth });
  const counters = fresh.counters.papersReviewed === null && prev.counters.papersReviewed !== null
    ? prev.counters
    : fresh.counters;
  const highlight = merged.status === "running" ? (prev.highlight ?? latestHighlight(merged.subqs)) : null;
  return { ...merged, counters, highlight };
}

export function withPlan(view: ResearchView, plan: string[]): ResearchView {
  return rebuild({ ...view, plan });
}

export function applyResearchEvent(view: ResearchView, event: ResearchEvent): ResearchView {
  switch (event.kind) {
    case "snapshot":
      return applySnapshot(view, event);
    case "status":
      return {
        ...view,
        status: event.status,
        stage: event.stage ?? view.stage,
        lastError: isTerminalStatus(event.status) ? view.lastError : null,
      };
    case "step":
      return applyStep(view, event);
    case "search":
      return applySearch(view, event);
    case "critique":
      return applyCritique(view, event);
    case "counters":
      return { ...view, counters: countersFromPayload(event) };
    case "synth":
      return {
        ...view,
        synth: {
          ...view.synth,
          status: view.synth.status ?? "running",
          total: Math.max(view.synth.total, event.total),
          sections: mergeSections(view.synth.sections, [{ idx: event.section_idx, status: event.status }]),
        },
      };
    case "done":
      return { ...view, status: "completed", highlight: null };
    case "failed":
      return { ...view, status: "failed", lastError: event.error ?? view.lastError, highlight: null };
    case "canceled":
      return { ...view, status: "canceled", highlight: null };
    default:
      return view;
  }
}

function applySnapshot(view: ResearchView, event: SnapshotEvent): ResearchView {
  const next: ResearchView = { ...view, steps: withKnownResults(view.steps, event.steps ?? []) };
  if (event.job) {
    next.status = event.job.status;
    next.stage = event.job.stage;
    if (event.job.plan?.length) next.plan = event.job.plan;
    if (event.job.counters) next.counters = countersFromPayload(event.job.counters);
  }
  if (!next.plan.length) next.plan = planFromSteps(next.steps);
  const rebuilt = rebuild(next);
  if (rebuilt.highlight || rebuilt.status !== "running") return rebuilt;
  return { ...rebuilt, highlight: latestHighlight(rebuilt.subqs) };
}

function applyStep(view: ResearchView, event: StepEvent): ResearchView {
  const prev = view.steps.find((s) => s.seq === event.seq);
  const row: ResearchStepRow = {
    seq: event.seq,
    kind: event.step_kind,
    subq_idx: event.subq_idx ?? null,
    title: event.title,
    detail: event.detail ?? prev?.detail ?? null,
    status: event.status,
    result: event.result ?? prev?.result ?? {},
  };
  const steps = [...view.steps.filter((s) => s.seq !== event.seq), row].sort(bySeq);
  const plan = view.plan.length ? view.plan : planFromSteps(steps);
  return rebuild({ ...view, steps, plan });
}

function applySearch(view: ResearchView, event: SearchEvent): ResearchView {
  return updateSubq(view, event.subq_idx, (sq) => {
    const round = event.round ?? (lastRound(sq.rounds) ?? 0) + 1;
    const existing = sq.rounds.find((r) => r.round === round);
    const entry: RoundView = {
      ...(existing ?? blankRound(round)),
      query: event.query,
      foundChunks: event.found,
      newPapers: event.new_papers ?? existing?.newPapers ?? null,
    };
    return { ...sq, status: "running", rounds: upsertRound(sq.rounds, entry) };
  });
}

function applyCritique(view: ResearchView, event: CritiqueEvent): ResearchView {
  const current = view.subqs.find((s) => s.idx === event.subq_idx);
  const round = event.round ?? lastRound(current?.rounds ?? []) ?? 1;
  const next = updateSubq(view, event.subq_idx, (sq) => {
    const existing = sq.rounds.find((r) => r.round === round);
    const entry: RoundView = {
      ...(existing ?? blankRound(round)),
      verdict: event.verdict,
      note: event.note,
      nextQuery: event.next_query ?? null,
    };
    return {
      ...sq,
      rounds: upsertRound(sq.rounds, entry),
      verdict: event.verdict,
      note: event.note,
      adopted: event.adopted,
      parseFailed: event.parse_failed,
    };
  });
  const highlight: HighlightView | null = event.will_recheck && event.next_query
    ? { subqIdx: event.subq_idx, round, note: event.note, nextQuery: event.next_query }
    : next.highlight;
  return { ...next, highlight };
}

function rebuild(view: ResearchView): ResearchView {
  const searchSteps = latestBySubq(view.steps, "search");
  const prior = new Map(view.subqs.map((s) => [s.idx, s]));
  const trail = view.report?.trail ?? [];
  const titles = view.plan.length ? view.plan : trail.map((t) => t.subquestion);
  const idxs = new Set<number>(titles.map((_, i) => i));
  for (const idx of searchSteps.keys()) idxs.add(idx);
  // 계획을 모를 때만 라이브로 받은 하위질문을 남긴다 — 알면 계획에서 지운 항목이 되살아난다
  if (!titles.length) for (const idx of prior.keys()) idxs.add(idx);

  const sources = new Set<RoundSource>();
  const subqs = [...idxs]
    .sort((a, b) => a - b)
    .map((idx) => {
      const built = buildSubq(idx, titles[idx], searchSteps.get(idx), prior.get(idx), trail[idx]);
      sources.add(built.source);
      return built.subq;
    });
  return {
    ...view,
    subqs,
    source: SOURCE_ORDER.find((s) => sources.has(s)) ?? "none",
    synth: synthFrom(view),
  };
}

function buildSubq(
  idx: number,
  title: string | undefined,
  step: ResearchStepRow | undefined,
  old: SubqView | undefined,
  trail: TrailItem | undefined,
): { subq: SubqView; source: RoundSource } {
  // 같은 하위질문의 새 시도(재시도)는 seq 가 커진다 — 이전 시도의 라이브 회차를 섞지 않는다
  const carry = old && (!step || old.seq === null || old.seq === step.seq) ? old : undefined;
  const r: StepResult = step?.result ?? {};
  let rounds: RoundView[] = [];
  let source: RoundSource = "none";
  if (Array.isArray(r.rounds)) {
    rounds = r.rounds.map(toRoundView);
    source = "rounds";
  } else if (trail?.queries.length) {
    rounds = roundsFromQueries(trail.queries, trail.verdict, trail.note);
    source = "trail";
  } else if (r.queries?.length) {
    rounds = roundsFromQueries(r.queries, r.verdict ?? null, r.note ?? "");
    source = "queries";
  }
  rounds = mergeRounds(rounds, carry?.rounds ?? []);
  if (source === "none" && rounds.length) source = "rounds";

  const fallbackStatus: StepStatus = trail ? (trail.failed ? "failed" : "done") : "pending";
  return {
    source,
    subq: {
      idx,
      title: title ?? step?.title ?? carry?.title ?? "",
      seq: step?.seq ?? carry?.seq ?? null,
      status: step?.status ?? carry?.status ?? fallbackStatus,
      rounds,
      verdict: r.verdict ?? carry?.verdict ?? trail?.verdict ?? null,
      note: r.note ?? carry?.note ?? trail?.note ?? "",
      adopted: r.adopted ?? carry?.adopted ?? trail?.evidence_count ?? null,
      parseFailed: r.parse_failed ?? carry?.parseFailed ?? trail?.parse_failed ?? false,
      error: r.error ?? null,
    },
  };
}

function synthFrom(view: ResearchView): SynthView {
  const step = latestOf(view.steps, "synthesize");
  if (!step) return view.synth;
  const r: StepResult = step.result ?? {};
  const listed: SynthSectionView[] = Array.isArray(r.sections)
    ? r.sections.map((s) => ({ idx: s.idx, status: s.status }))
    : [];
  const total = r.sections_total ?? (typeof r.sections === "number" ? r.sections : listed.length);
  const sameAttempt = view.synth.seq === null || view.synth.seq === step.seq;
  return {
    seq: step.seq,
    status: step.status,
    total: Math.max(total, sameAttempt ? view.synth.total : 0),
    sections: mergeSections(listed, sameAttempt ? view.synth.sections : []),
  };
}

// 재검색은 판정이 부족일 때만 일어난다(critic.should_recheck) — 마지막 전 회차는 모두 부족이다
function roundsFromQueries(queries: string[], verdict: Verdict | null, note: string): RoundView[] {
  const last = queries.length - 1;
  return queries.map((query, i) => ({
    round: i + 1,
    query,
    foundChunks: null,
    newPapers: null,
    verdict: i < last ? "insufficient" : verdict,
    note: i < last ? "" : note,
    nextQuery: i < last ? (queries[i + 1] ?? null) : null,
  }));
}

function toRoundView(r: SearchRoundResult): RoundView {
  return {
    round: r.round,
    query: r.query,
    foundChunks: r.found_chunks ?? null,
    newPapers: r.new_papers ?? null,
    verdict: r.verdict ?? null,
    note: r.note ?? "",
    nextQuery: r.next_query ?? null,
  };
}

function blankRound(round: number): RoundView {
  return { round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null };
}

function mergeRounds(base: RoundView[], live: RoundView[]): RoundView[] {
  const known = new Set(base.map((r) => r.round));
  return [...base, ...live.filter((r) => !known.has(r.round))].sort((a, b) => a.round - b.round);
}

function upsertRound(rounds: RoundView[], entry: RoundView): RoundView[] {
  return [...rounds.filter((r) => r.round !== entry.round), entry].sort((a, b) => a.round - b.round);
}

function lastRound(rounds: RoundView[]): number | null {
  return rounds.length ? Math.max(...rounds.map((r) => r.round)) : null;
}

function mergeSections(base: SynthSectionView[], extra: SynthSectionView[]): SynthSectionView[] {
  const out = new Map(base.map((s) => [s.idx, s]));
  for (const s of extra) {
    const cur = out.get(s.idx);
    if (!cur || SECTION_RANK[s.status] >= SECTION_RANK[cur.status]) out.set(s.idx, s);
  }
  return [...out.values()].sort((a, b) => a.idx - b.idx);
}

function updateSubq(view: ResearchView, idx: number, fn: (sq: SubqView) => SubqView): ResearchView {
  const list = view.subqs.some((s) => s.idx === idx)
    ? view.subqs
    : [...view.subqs, emptySubq(idx, view.plan[idx] ?? "")].sort((a, b) => a.idx - b.idx);
  return { ...view, subqs: list.map((s) => (s.idx === idx ? fn(s) : s)) };
}

function emptySubq(idx: number, title: string): SubqView {
  return {
    idx, title, seq: null, status: "pending", rounds: [],
    verdict: null, note: "", adopted: null, parseFailed: false, error: null,
  };
}

function latestHighlight(subqs: SubqView[]): HighlightView | null {
  for (const sq of [...subqs].reverse()) {
    if (sq.status !== "running") continue;
    const r = [...sq.rounds].reverse().find((x) => x.nextQuery);
    if (r?.nextQuery) return { subqIdx: sq.idx, round: r.round, note: r.note, nextQuery: r.nextQuery };
  }
  return null;
}

function withKnownResults(prev: ResearchStepRow[], incoming: ResearchStepRow[]): ResearchStepRow[] {
  const bySeqMap = new Map(prev.map((s) => [s.seq, s]));
  return incoming
    .map((s) => (s.result === undefined ? { ...s, result: bySeqMap.get(s.seq)?.result ?? {} } : s))
    .sort(bySeq);
}

function planFromSteps(steps: ResearchStepRow[]): string[] {
  return latestOf(steps, "plan")?.result?.subquestions ?? [];
}

function latestOf(steps: ResearchStepRow[], kind: StepKind): ResearchStepRow | undefined {
  let best: ResearchStepRow | undefined;
  for (const s of steps) if (s.kind === kind && (!best || s.seq > best.seq)) best = s;
  return best;
}

// 재시도가 끼면 같은 (kind, subq_idx) 행이 여럿 남는다 — seq 가 가장 큰 행이 현재 시도다
function latestBySubq(steps: ResearchStepRow[], kind: StepKind): Map<number, ResearchStepRow> {
  const out = new Map<number, ResearchStepRow>();
  for (const s of steps) {
    if (s.kind !== kind || s.subq_idx === null) continue;
    const cur = out.get(s.subq_idx);
    if (!cur || s.seq > cur.seq) out.set(s.subq_idx, s);
  }
  return out;
}

function countersFromPayload(p: CountersPayload): CountersView {
  return { papersReviewed: p.papers_reviewed, evidenceAdopted: p.evidence_adopted, rechecks: p.rechecks };
}

function countersFromReport(report: ResearchReport | null): CountersView {
  if (!report) return { ...EMPTY_COUNTERS };
  if (report.stats) return countersFromPayload(report.stats);
  // 보강 전 보고서 — 검토한 논문 수는 어디에도 남아 있지 않다
  return {
    papersReviewed: null,
    evidenceAdopted: Object.keys(report.evidence ?? {}).length,
    rechecks: report.trail.reduce((n, t) => n + Math.max(0, t.queries.length - 1), 0),
  };
}

function bySeq(a: ResearchStepRow, b: ResearchStepRow): number {
  return a.seq - b.seq;
}
```

- [ ] **Step 4: 실행해 통과 확인**

```bash
cd frontend && npx vitest run tests/unit/researchEvents.test.ts
```
기대: `Test Files  1 passed (1)`, `Tests  24 passed (24)`.

```bash
cd frontend
npx tsc --noEmit --strict --noUncheckedIndexedAccess --verbatimModuleSyntax --isolatedModules \
  --target es2022 --module esnext --moduleResolution bundler --lib es2022,dom --skipLibCheck \
  types/research.ts utils/researchEvents.ts
```
기대: 출력 없음.

- [ ] **Step 5: 커밋**

```bash
git add frontend/utils/researchEvents.ts frontend/tests/unit/researchEvents.test.ts
git commit -m "[Feat] round04b — 딥리서치 SSE 이벤트 리듀서와 테스트"
```

---

### Task 29: API 오류·입력 검증과 `useResearch` composable

- `utils/researchErrors.ts`: `$fetch` 오류에서 상태 코드를 읽고, 422 의 `detail` 두 모양(문자열·pydantic 배열)을 모두 처리하며, 429·503 은 "잠시 뒤 다시" 로 안내한다(spec §6-2).
- `utils/researchInput.ts`: 서버 검증과 같은 경계(질문 2~500자, 하위질문 2~300자·상한·중복)를 화면이 먼저 막는다 — 사용자가 영문 pydantic 메시지를 보지 않게.
- `composables/useResearch.ts`:
  - `useResearchApi()` — 생성·조회·승인·재시도·취소 호출(`useApi()` 를 거쳐 `x-session-id` 가 붙는다).
  - `useResearchStarter().startResearch(question)` — `POST /api/research` → `useHistory().upsertResearch` → job_id 반환. 기록 저장 실패는 삼킨다(잡은 이미 만들어졌다). `+` 메뉴와 "같은 질문으로 다시 시작" 이 같이 쓴다.
  - `useResearchJob(jobId)` — 마운트 때 GET → 끝나지 않은 잡이면 EventSource 연결. 종료 이벤트에 반드시 `close()` 한 뒤 GET 으로 보고서를 다시 읽는다(닫지 않으면 자동 재접속으로 snapshot·종료를 반복 수신 — spec §6-2). 브라우저가 스스로 재접속하는 동안(CONNECTING)은 서버가 snapshot 부터 다시 보내 복원되고, 브라우저가 포기하면(CLOSED) GET 후 2초부터 최대 30초 간격으로 직접 다시 붙인다. 승인·재시도·취소 중 409 는 GET 재조회로 화면을 맞춘다. 404·422(형식 오류) 조회는 "찾을 수 없는 연구". 주소의 잡 id 가 바뀌면(같은 페이지 인스턴스 재사용) 다시 읽고, 늦게 도착한 이전 응답은 세대 번호로 버린다. 종료 이벤트와 승인·재시도·취소 성공 뒤에는 `useHistory().refresh("research")` 로 사이드바 배지를 30초 폴링을 기다리지 않고 맞춘다.

**Files:**
- Create: `frontend/utils/researchErrors.ts`
- Create: `frontend/utils/researchInput.ts`
- Create: `frontend/composables/useResearch.ts`
- Test: `frontend/tests/unit/researchErrors.test.ts`
- Test: `frontend/tests/unit/researchInput.test.ts`

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
// frontend/tests/unit/researchErrors.test.ts
import { describe, expect, it } from "vitest";
import { detailMessage, httpStatus, researchErrorMessage } from "~/utils/researchErrors";

function fetchError(status: number, detail?: unknown) {
  return Object.assign(new Error(`HTTP ${status}`), { status, statusCode: status, data: detail === undefined ? undefined : { detail } });
}

describe("httpStatus", () => {
  it("$fetch 오류의 status·statusCode·response.status 를 읽는다", () => {
    expect(httpStatus({ status: 409 })).toBe(409);
    expect(httpStatus({ statusCode: 503 })).toBe(503);
    expect(httpStatus({ response: { status: 404 } })).toBe(404);
    expect(httpStatus(new Error("network"))).toBeUndefined();
    expect(httpStatus(null)).toBeUndefined();
  });
});

describe("detailMessage", () => {
  it("문자열 detail 은 그대로, 배열 detail 은 msg 를 모아 쓴다", () => {
    expect(detailMessage("하위질문은 6개까지다")).toBe("하위질문은 6개까지다");
    expect(detailMessage([{ loc: ["body", "question"], msg: "String should have at least 2 characters", type: "string_too_short" }]))
      .toBe("입력값이 올바르지 않습니다: String should have at least 2 characters");
    expect(detailMessage({ unexpected: true })).toBeNull();
    expect(detailMessage([])).toBeNull();
  });
});

describe("researchErrorMessage", () => {
  it("422 는 두 모양의 detail 을 모두 보여 준다", () => {
    expect(researchErrorMessage(fetchError(422, "중복된 하위질문이다: 가"), "실패")).toBe("중복된 하위질문이다: 가");
    expect(researchErrorMessage(fetchError(422, [{ msg: "too long" }]), "실패")).toBe("입력값이 올바르지 않습니다: too long");
  });

  it("429·503 은 잠시 뒤 다시 안내한다", () => {
    expect(researchErrorMessage(fetchError(429, "x"), "실패")).toBe("요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요");
    expect(researchErrorMessage(fetchError(503, "작업 큐"), "실패")).toBe("요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요");
  });

  it("409 는 서버 사유를, 사유가 없으면 대체 문구를 쓴다", () => {
    expect(researchErrorMessage(fetchError(409, "승인할 수 없는 상태다: running"), "실패")).toBe("승인할 수 없는 상태다: running");
    expect(researchErrorMessage(fetchError(409), "실패")).toBe("실패");
  });

  it("상태가 없으면 네트워크 문제로, 그 밖의 상태는 대체 문구로 둔다", () => {
    expect(researchErrorMessage(new Error("Failed to fetch"), "딥리서치를 시작하지 못했습니다"))
      .toBe("딥리서치를 시작하지 못했습니다 — 네트워크 연결을 확인하세요");
    expect(researchErrorMessage(fetchError(500, "Internal"), "실패")).toBe("실패");
  });
});
```

```ts
// frontend/tests/unit/researchInput.test.ts
import { describe, expect, it } from "vitest";
import { planKey, planProblem, questionProblem } from "~/utils/researchInput";

describe("questionProblem", () => {
  it("앞뒤 공백을 빼고 2~500자만 받는다", () => {
    expect(questionProblem(" 가 ")).toBe("연구 질문을 2자 이상 입력하세요");
    expect(questionProblem("가나")).toBeNull();
    expect(questionProblem("가".repeat(500))).toBeNull();
    expect(questionProblem("가".repeat(501))).toBe("연구 질문은 500자까지 입력할 수 있습니다");
  });

  it("글자 수는 코드포인트로 센다", () => {
    expect(questionProblem("😀")).toBe("연구 질문을 2자 이상 입력하세요");
  });
});

describe("planProblem", () => {
  it("정상 계획은 문제가 없다", () => {
    expect(planProblem(["효과 측정", "교사 인식"], 6)).toBeNull();
  });

  it("비었거나 상한을 넘으면 알린다", () => {
    expect(planProblem([], 6)).toBe("하위질문이 하나 이상 있어야 합니다");
    expect(planProblem(["가나", "다라", "마바"], 2)).toBe("하위질문은 2개까지입니다");
  });

  it("짧거나 긴 항목의 번호를 알린다", () => {
    expect(planProblem(["효과 측정", " 가 "], 6)).toBe("2번 하위질문을 2자 이상 입력하세요");
    expect(planProblem(["가".repeat(301)], 6)).toBe("1번 하위질문은 300자까지입니다");
  });

  it("공백·대소문자만 다른 항목은 중복이다", () => {
    expect(planKey("  AI   윤리 ")).toBe("ai 윤리");
    expect(planProblem(["AI 윤리", "ai  윤리"], 6)).toBe("2번 하위질문이 앞의 것과 같습니다");
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd frontend && npx vitest run tests/unit/researchErrors.test.ts tests/unit/researchInput.test.ts
```
기대: `Cannot find module '~/utils/researchErrors' …` · `Cannot find module '~/utils/researchInput' …`, `Test Files  2 failed (2)`.

- [ ] **Step 3: 최소 구현 — 순수 모듈**

```ts
// frontend/utils/researchErrors.ts
interface FetchLikeError {
  status?: number;
  statusCode?: number;
  response?: { status?: number };
  data?: unknown;
}

export function httpStatus(err: unknown): number | undefined {
  if (!err || typeof err !== "object") return undefined;
  const e = err as FetchLikeError;
  return e.status ?? e.statusCode ?? e.response?.status;
}

// FastAPI 는 HTTPException 이면 detail 을 문자열로, pydantic 검증 실패면
// [{loc, msg, type}] 배열로 준다. 한 모양만 읽으면 다른 쪽은 "[object Object]" 가 된다.
export function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail.trim() || null;
  if (!Array.isArray(detail)) return null;
  const msgs = detail
    .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
    .filter(Boolean);
  return msgs.length ? `입력값이 올바르지 않습니다: ${msgs.join(", ")}` : null;
}

export function researchErrorMessage(err: unknown, fallback: string): string {
  const status = httpStatus(err);
  if (status === 429 || status === 503) return "요청이 몰려 있습니다. 잠시 뒤 다시 시도하세요";
  if (status === 404) return "찾을 수 없는 연구입니다";
  const data = (err as FetchLikeError | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data
    ? detailMessage((data as { detail: unknown }).detail)
    : null;
  if (status === 409 || status === 422) return detail ?? fallback;
  if (status === undefined) return `${fallback} — 네트워크 연결을 확인하세요`;
  return fallback;
}
```

```ts
// frontend/utils/researchInput.ts
// 서버 검증(api/research.py 의 ResearchCreate·PlanItem)과 같은 경계. 여기서 먼저 막아
// 사용자가 422 의 영문 pydantic 메시지를 보지 않게 한다.
export const QUESTION_MIN = 2;
export const QUESTION_MAX = 500;
export const PLAN_ITEM_MIN = 2;
export const PLAN_ITEM_MAX = 300;
// 백엔드 state.DEFAULT_PARAMS 와 같은 값 — GET 응답에 params 가 없는 옛 API 대비
export const DEFAULT_MAX_SUBQUESTIONS = 6;

// 파이썬 len 은 코드포인트를 센다 — JS length(UTF-16)로 세면 이모지에서 어긋난다
function codepoints(text: string): number {
  return [...text].length;
}

export function questionProblem(question: string): string | null {
  const n = codepoints(question.trim());
  if (n < QUESTION_MIN) return `연구 질문을 ${QUESTION_MIN}자 이상 입력하세요`;
  if (n > QUESTION_MAX) return `연구 질문은 ${QUESTION_MAX}자까지 입력할 수 있습니다`;
  return null;
}

// planner.query_key 와 같은 규칙 — 서버가 중복으로 거절할 항목을 화면이 먼저 알린다
export function planKey(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

export function planProblem(items: string[], max: number): string | null {
  if (!items.length) return "하위질문이 하나 이상 있어야 합니다";
  if (items.length > max) return `하위질문은 ${max}개까지입니다`;
  const seen = new Set<string>();
  for (const [i, raw] of items.entries()) {
    const text = raw.trim();
    const n = codepoints(text);
    if (n < PLAN_ITEM_MIN) return `${i + 1}번 하위질문을 ${PLAN_ITEM_MIN}자 이상 입력하세요`;
    if (n > PLAN_ITEM_MAX) return `${i + 1}번 하위질문은 ${PLAN_ITEM_MAX}자까지입니다`;
    const key = planKey(text);
    if (seen.has(key)) return `${i + 1}번 하위질문이 앞의 것과 같습니다`;
    seen.add(key);
  }
  return null;
}
```

- [ ] **Step 4: 실행해 통과 확인**

```bash
cd frontend && npx vitest run tests/unit/researchErrors.test.ts tests/unit/researchInput.test.ts
```
기대: `Test Files  2 passed (2)`, `Tests  12 passed (12)`.

```bash
cd frontend
npx tsc --noEmit --strict --noUncheckedIndexedAccess --verbatimModuleSyntax --isolatedModules \
  --target es2022 --module esnext --moduleResolution bundler --lib es2022,dom --skipLibCheck \
  utils/researchErrors.ts utils/researchInput.ts
```
기대: 출력 없음.

- [ ] **Step 5: composable 작성**

Nuxt API(`useApi`·`useHistory`·`import.meta.client`)에 기대므로 순수 테스트 대상이 아니다 — 상태 전이 로직은 전부 앞 태스크의 리듀서에 있고, 여기는 수명주기만 맡는다.

```ts
// frontend/composables/useResearch.ts
import { getCurrentInstance, onBeforeUnmount, onMounted, ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from "vue";
import type {
  ResearchApproveResponse,
  ResearchCancelResponse,
  ResearchCreateResponse,
  ResearchEvent,
  ResearchJob,
  ResearchParams,
  ResearchRetryResponse,
  ResearchView,
} from "~/types/research";
import { applyResearchEvent, initialResearchView, isTerminalEvent, isTerminalStatus, refreshView, withPlan } from "~/utils/researchEvents";
import { httpStatus, researchErrorMessage } from "~/utils/researchErrors";
import { apiUrl, useApi } from "./useApi";
import { useHistory } from "./useHistory";

const RECONNECT_BASE_MS = 2000;
const RECONNECT_MAX_MS = 30000;

export function useResearchApi() {
  const api = useApi();
  return {
    create: (question: string, params: ResearchParams = {}) =>
      api<ResearchCreateResponse>("/research", { method: "POST", body: { question, params } }),
    get: (jobId: string) => api<ResearchJob>(`/research/${encodeURIComponent(jobId)}`),
    approve: (jobId: string, plan?: string[]) =>
      api<ResearchApproveResponse>(`/research/${encodeURIComponent(jobId)}/approve`, {
        method: "POST",
        body: plan ? { plan } : {},
      }),
    retry: (jobId: string) =>
      api<ResearchRetryResponse>(`/research/${encodeURIComponent(jobId)}/retry`, { method: "POST" }),
    cancel: (jobId: string) =>
      api<ResearchCancelResponse>(`/research/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }),
  };
}

export function useResearchStarter() {
  const research = useResearchApi();
  const history = useHistory();

  async function startResearch(question: string): Promise<string> {
    const { job_id } = await research.create(question);
    try {
      await history.upsertResearch(job_id, question);
    } catch (e) {
      // 잡은 이미 만들어졌다 — 기록 저장 실패로 멈추면 돌고 있는 잡의 주소를 잃는다
      console.warn("[research] 기록 저장 실패", e);
    }
    return job_id;
  }

  return { startResearch };
}

export function useResearchJob(jobId: MaybeRefOrGetter<string>) {
  const research = useResearchApi();
  const history = useHistory();
  const streamBase = apiUrl("/research");

  const view = shallowRef<ResearchView | null>(null);
  const loading = ref(false);
  const notFound = ref(false);
  const loadError = ref("");
  const actionError = ref("");
  const busy = ref(false);
  const connected = ref(false);

  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  // 주소의 잡이 바뀌거나 페이지를 떠난 뒤 도착한 이전 요청의 응답을 버린다
  let generation = 0;

  async function load(): Promise<void> {
    const gen = ++generation;
    disconnect();
    loading.value = true;
    notFound.value = false;
    loadError.value = "";
    actionError.value = "";
    try {
      const job = await research.get(toValue(jobId));
      if (gen !== generation) return;
      view.value = initialResearchView(job);
      connect();
    } catch (e) {
      if (gen !== generation) return;
      view.value = null;
      const status = httpStatus(e);
      if (status === 404 || status === 422) notFound.value = true;
      else loadError.value = researchErrorMessage(e, "연구를 불러오지 못했습니다");
    } finally {
      if (gen === generation) loading.value = false;
    }
  }

  async function refresh(): Promise<void> {
    const gen = generation;
    try {
      const job = await research.get(toValue(jobId));
      if (gen !== generation) return;
      view.value = refreshView(view.value, job);
      if (!isTerminalStatus(view.value.status)) connect();
    } catch (e) {
      if (gen !== generation) return;
      actionError.value = researchErrorMessage(e, "최신 상태를 불러오지 못했습니다");
      scheduleReconnect();
    }
  }

  function connect(): void {
    if (!import.meta.client || source || !view.value || isTerminalStatus(view.value.status)) return;
    clearReconnect();
    const gen = generation;
    const es = new EventSource(`${streamBase}/${encodeURIComponent(view.value.jobId)}/stream`);
    source = es;
    es.onopen = () => {
      connected.value = true;
      attempts = 0;
    };
    es.onmessage = (msg: MessageEvent<string>) => {
      if (gen !== generation || !view.value) return;
      let event: ResearchEvent;
      try {
        event = JSON.parse(msg.data) as ResearchEvent;
      } catch {
        return;
      }
      view.value = applyResearchEvent(view.value, event);
      if (isTerminalEvent(event)) {
        // 닫지 않으면 EventSource 가 스스로 다시 붙어 snapshot·종료를 끝없이 되받는다.
        // 종료 이벤트에는 보고서가 없으므로 GET 으로 다시 읽는다.
        disconnect();
        void refresh();
        // 사이드바 배지는 30초마다만 다시 읽는다 — 끝난 순간에 한 번 맞춘다
        void history.refresh("research");
      }
    };
    es.onerror = () => {
      connected.value = false;
      // CONNECTING 이면 브라우저가 다시 붙고 서버가 snapshot 부터 보내 화면이 복원된다.
      // CLOSED 는 브라우저가 포기한 경우(오류 응답 등)라 GET 으로 맞춘 뒤 직접 다시 붙인다.
      if (es.readyState !== EventSource.CLOSED) return;
      if (source === es) source = null;
      scheduleReconnect();
    };
  }

  function scheduleReconnect(): void {
    if (reconnectTimer || !import.meta.client) return;
    const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** attempts);
    attempts += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      void refresh();
    }, delay);
  }

  function clearReconnect(): void {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  function disconnect(): void {
    clearReconnect();
    source?.close();
    source = null;
    connected.value = false;
  }

  async function act<T>(run: () => Promise<T>, onOk: (res: T) => void, fallback: string): Promise<boolean> {
    if (busy.value || !view.value) return false;
    busy.value = true;
    actionError.value = "";
    try {
      onOk(await run());
      void history.refresh("research");
      return true;
    } catch (e) {
      if (httpStatus(e) === 409) {
        // 이미 진행·종료된 잡 — 사유를 보여 주기보다 화면을 서버 상태로 맞추는 게 답이다
        await refresh();
        actionError.value = "그 사이 상태가 바뀌어 최신 상태로 맞췄습니다";
      } else {
        actionError.value = researchErrorMessage(e, fallback);
      }
      return false;
    } finally {
      busy.value = false;
    }
  }

  const approve = (plan?: string[]) =>
    act(
      () => research.approve(toValue(jobId), plan),
      (res) => {
        if (!view.value) return;
        const planned = res.plan?.length ? withPlan(view.value, res.plan) : view.value;
        view.value = applyResearchEvent(planned, { kind: "status", status: res.status, stage: planned.stage });
        connect();
      },
      "계획을 승인하지 못했습니다",
    );

  const retry = () =>
    act(
      () => research.retry(toValue(jobId)),
      (res) => {
        if (!view.value) return;
        view.value = applyResearchEvent(view.value, { kind: "status", status: res.status, stage: res.stage });
        connect();
      },
      "다시 시도하지 못했습니다",
    );

  const cancel = () =>
    act(
      () => research.cancel(toValue(jobId)),
      () => {
        if (!view.value) return;
        view.value = applyResearchEvent(view.value, { kind: "canceled", status: "canceled" });
        disconnect();
      },
      "취소하지 못했습니다",
    );

  if (getCurrentInstance()) {
    onMounted(() => {
      void load();
    });
    onBeforeUnmount(() => {
      generation += 1;
      disconnect();
    });
  }

  watch(
    () => toValue(jobId),
    (id, old) => {
      if (import.meta.client && id !== old) void load();
    },
  );

  return { view, loading, notFound, loadError, actionError, busy, connected, load, refresh, connect, disconnect, approve, retry, cancel };
}
```

- [ ] **Step 6: 컴파일 확인**

```bash
cd frontend
npx nuxi typecheck 2>&1 | grep "error TS" | grep -v "pages/search-classic.vue"
npm run build 2>&1 | tail -1
```
기대: 첫 명령 출력 없음, 둘째 `└  ✨ Build complete!`. `useApi`·`useHistory` 를 못 찾는다는 오류가 나면 C1 의 composable 이 아직 없는 것이다(선행 조건).

- [ ] **Step 7: 커밋**

```bash
git add frontend/utils/researchErrors.ts frontend/utils/researchInput.ts frontend/composables/useResearch.ts frontend/tests/unit/researchErrors.test.ts frontend/tests/unit/researchInput.test.ts
git commit -m "[Feat] round04b — 딥리서치 API 오류·입력 검증과 SSE 수명주기 composable"
```

---

### Task 30: 개발 프록시 대상 환경변수화 (`nuxt.config.ts`)

spec §9 는 로컬 Nuxt 개발 서버의 API 를 운영 게이트웨이로 프록시해 화면을 확인한다. 대상 주소를 환경변수로 바꾼다.

**실측(2026-09-26, h3 1.15.11 + httpxy — Nitro devProxy 의 실제 구성)**: devProxy 는 `/api` 접두를 **떼고** 넘긴다. 대상이 `http://127.0.0.1:39101` 이면 `/api/research/abc/stream` 요청이 대상에 `/research/abc/stream` 으로 도착하고, 대상이 `http://127.0.0.1:39101/api` 이면 `/api/research/abc/stream` 으로 도착한다. FastAPI 라우트는 `/api/...` 접두를 쓰므로 지금 설정(`http://localhost:18002`)은 모든 요청이 404 다. 그래서 기본값과 환경변수 값 모두 `/api` 까지 포함한다(원래 설정 `http://localhost:18002` 와 다르다 — 영역 간 계약의 정합 결정 13번).

**Files:**
- Modify: `frontend/nuxt.config.ts` (`nitro.devProxy` 블록, 현재 24–31행)

- [ ] **Step 1: devProxy 대상 교체**

현재 코드(24–31행):

```ts
  nitro: {
    devProxy: {
      "/api": {
        target: "http://localhost:18002",
        changeOrigin: true,
      },
    },
  },
```

교체 코드:

```ts
  nitro: {
    devProxy: {
      "/api": {
        // devProxy 는 "/api" 접두를 떼고 넘긴다 — 대상 주소에 /api 를 붙여야 FastAPI 경로와 맞는다.
        // 로컬 화면을 운영 게이트웨이에 붙일 때는 NUXT_DEV_API_TARGET=http://<서버>:92/api 로 띄운다.
        target: process.env.NUXT_DEV_API_TARGET ?? "http://localhost:18002/api",
        changeOrigin: true,
      },
    },
  },
```

- [ ] **Step 2: 동작 확인**

운영 게이트웨이 주소를 아는 경우(spec §13 미확정 항목):

```bash
cd frontend
NUXT_DEV_API_TARGET=http://<서버>:92/api npm run dev
# 다른 터미널에서 — 존재하는 잡 id 로
curl -s http://localhost:3000/api/research/<job_id> | head -c 120
```
기대: `{"job_id":"<job_id>","question":...` 로 시작하는 JSON. `{"detail":"Not Found"}` 가 나오면 대상 주소에 `/api` 가 빠진 것이다.

게이트웨이 주소가 아직 없으면 이 단계는 Task 35 의 수동 화면 확인으로 미룬다. 빌드 확인: `npm run build 2>&1 | tail -1` → `└  ✨ Build complete!`.

- [ ] **Step 3: 커밋**

```bash
git add frontend/nuxt.config.ts
git commit -m "[Feat] round04b — 개발 프록시 대상 환경변수화(NUXT_DEV_API_TARGET, /api 접두 보존)"
```

---

### Task 31: 페이지 골격 — 상태 기계·배치 A/B·머리·전용 CSS

`/research/<job_id>` 를 만든다. 이 태스크에서는 블록 세 개(계획 카드·진행 패널·보고서) 자리에 간단한 자리표시를 두고, Task 32~Task 34 가 하나씩 진짜 블록으로 바꾼다 — 태스크마다 컴파일되고 화면으로 확인된다.

- 배치(spec §7): `.rs-body--A` 는 2단 그리드(본문 | 진행 패널, 패널은 sticky), `.rs-body--B` 는 본문 묶음을 `display: contents` 로 풀어 **계획 → 진행 → 보고서** 순서로 쌓는다. 같은 DOM 으로 두 배치를 모두 지원한다.
- 1200px 미만은 선택과 무관하게 B. 보기 선택은 localStorage `skx_research_layout` 에 기억한다(막힌 저장소면 이번 방문만). 저장소 접근은 Task 15 의 `safeLocalStorage()` 를 쓴다 — 같은 함수를 `utils/` 에 두 벌 두지 않는다. 기본 보기·기준 폭·전환 버튼 표시는 `utils/researchLayout.ts` 상수 셋으로, 기획자 결정(spec §7-3)이 나오면 값만 바꾼다.
- 서버 렌더에서는 폭을 모르므로 넓은 화면으로 두고 마운트 뒤 실제 폭으로 맞춘다. 잡 데이터는 마운트 뒤에만 읽으므로(기존 페이지 관례) 하이드레이션 불일치가 없다.
- `research.css` 는 이 화면·`+` 메뉴·인용칩 스타일 전부를 담는다(spec D10). `--skx-*` 토큰만 읽는다. `style_skovix.css` 는 건드리지 않는다.

**Files:**
- Create: `frontend/utils/researchLayout.ts`
- Test: `frontend/tests/unit/researchLayout.test.ts`
- Create: `frontend/assets/css/research.css`
- Modify: `frontend/nuxt.config.ts` (`css` 배열, 현재 13–16행)
- Create: `frontend/components/research/ResearchHeader.vue`
- Create: `frontend/pages/research/[id].vue`

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
// frontend/tests/unit/researchLayout.test.ts
import { describe, expect, it } from "vitest";
import { DEFAULT_LAYOUT, LAYOUT_KEY, effectiveLayout, readLayoutPref, writeLayoutPref } from "~/utils/researchLayout";

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(initial));
  return {
    get length() { return data.size; },
    clear: () => data.clear(),
    getItem: (k: string) => data.get(k) ?? null,
    key: (i: number) => [...data.keys()][i] ?? null,
    removeItem: (k: string) => { data.delete(k); },
    setItem: (k: string, v: string) => { data.set(k, v); },
  };
}

const blocked = {
  getItem: () => { throw new Error("SecurityError"); },
  setItem: () => { throw new Error("QuotaExceededError"); },
} as unknown as Storage;

describe("effectiveLayout", () => {
  it("넓은 화면은 고른 보기, 고른 적 없으면 기본 보기다", () => {
    expect(effectiveLayout(null, true)).toBe(DEFAULT_LAYOUT);
    expect(effectiveLayout("B", true)).toBe("B");
  });

  it("좁은 화면은 고른 보기와 무관하게 B 다", () => {
    expect(effectiveLayout("A", false)).toBe("B");
  });
});

describe("보기 선택 기억", () => {
  it("저장한 보기를 다시 읽는다", () => {
    const storage = memoryStorage();
    writeLayoutPref(storage, "B");
    expect(storage.getItem(LAYOUT_KEY)).toBe("B");
    expect(readLayoutPref(storage)).toBe("B");
  });

  it("모르는 값·없는 저장소·막힌 저장소는 기억 없음으로 본다", () => {
    expect(readLayoutPref(memoryStorage({ [LAYOUT_KEY]: "C" }))).toBeNull();
    expect(readLayoutPref(null)).toBeNull();
    expect(readLayoutPref(blocked)).toBeNull();
    writeLayoutPref(blocked, "A");
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd frontend && npx vitest run tests/unit/researchLayout.test.ts
```
기대: `Cannot find module '~/utils/researchLayout' …`, `Test Files  1 failed (1)`.

- [ ] **Step 3: 최소 구현**

```ts
// frontend/utils/researchLayout.ts
export type ResearchLayout = "A" | "B";

// 아래 셋은 화면 기획자가 정할 값이다. 정해지면 값만 바꾼다.
export const DEFAULT_LAYOUT: ResearchLayout = "A";
export const WIDE_MIN_PX = 1200;
export const SHOW_LAYOUT_TOGGLE = true;

export const LAYOUT_KEY = "skx_research_layout";

export function readLayoutPref(storage: Storage | null): ResearchLayout | null {
  try {
    const v = storage?.getItem(LAYOUT_KEY);
    return v === "A" || v === "B" ? v : null;
  } catch {
    return null;
  }
}

export function writeLayoutPref(storage: Storage | null, layout: ResearchLayout): void {
  try {
    storage?.setItem(LAYOUT_KEY, layout);
  } catch {
    // 막힌 저장소(사생활 보호 모드 등)면 이번 방문 동안만 기억한다
  }
}

// 2단은 폭이 모자라면 본문이 좁아져 읽을 수 없다 — 좁은 화면은 선택과 무관하게 B 다
export function effectiveLayout(pref: ResearchLayout | null, wide: boolean): ResearchLayout {
  if (!wide) return "B";
  return (SHOW_LAYOUT_TOGGLE ? pref : null) ?? DEFAULT_LAYOUT;
}
```

- [ ] **Step 4: 실행해 통과 확인**

```bash
cd frontend && npx vitest run tests/unit/researchLayout.test.ts
```
기대: `Test Files  1 passed (1)`, `Tests  4 passed (4)`.

```bash
cd frontend
npx tsc --noEmit --strict --noUncheckedIndexedAccess --verbatimModuleSyntax --isolatedModules \
  --target es2022 --module esnext --moduleResolution bundler --lib es2022,dom --skipLibCheck \
  utils/researchLayout.ts
```
기대: 출력 없음.

- [ ] **Step 5: 전용 CSS 작성**

```css
/* frontend/assets/css/research.css */
/* 딥리서치 화면 전용. 기획자 디자인이 나오면 이 파일만 갈아입힌다 —
   style_skovix.css 끝에 덧붙이면 화면 고도화 작업과 거의 확실히 충돌한다.
   색·모서리·그림자는 --skx-* 토큰만 읽는다. 1rem = 20px(style_skovix.css). */

/* ── 페이지 골격 ─────────────────────────────────────────── */
.rs-page {
  --rs-side-width: 17rem;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 1.2rem;
  min-width: 0;
  color: var(--skx-ink);
}
.rs-body {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}
.rs-col-main {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  min-width: 0;
}
/* A: 본문 + 진행 패널 2단 */
.rs-body--A {
  display: grid;
  grid-template-columns: minmax(0, 1fr) var(--rs-side-width);
  align-items: start;
}
.rs-body--A .rs-col-side {
  position: sticky;
  top: 1.2rem;
  max-height: calc(100vh - 2.4rem);
  overflow-y: auto;
}
/* B: 계획 → 탐색 과정 → 보고서가 한 줄로 쌓인다. 본문 묶음을 풀어 진행 패널을 가운데 끼운다 */
.rs-body--B .rs-col-main {
  display: contents;
}
.rs-body--B .rs-block--plan {
  order: 1;
}
.rs-body--B .rs-col-side {
  order: 2;
}
.rs-body--B .rs-block--report {
  order: 3;
}

/* ── 공통 부품 ───────────────────────────────────────────── */
.rs-card {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  padding: 1.2rem;
  background: var(--skx-white);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-shadow-lnb);
}
.rs-card__head {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.rs-card__title {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.rs-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.rs-card--wait {
  flex-direction: row;
  align-items: center;
  font-size: 0.75rem;
}
.rs-card--error {
  border: 1px solid var(--skx-line);
}
.rs-state {
  align-items: flex-start;
}
.rs-state__title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 700;
}
.rs-muted {
  margin: 0;
  font-size: 0.65rem;
  color: var(--skx-gray-1);
  line-height: 1.5;
}
.rs-alert {
  margin: 0;
  padding: 0.6rem 0.8rem;
  font-size: 0.65rem;
  color: var(--skx-ink);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c2);
  border-radius: var(--skx-radius-md);
}
.rs-spinner {
  width: 1.2rem;
  height: 1.2rem;
}
.rs-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  padding: 0.45rem 0.9rem;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-white);
  white-space: nowrap;
  text-decoration: none;
  background: var(--skx-primary);
  border: 1px solid var(--skx-primary);
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.rs-btn--ghost {
  color: var(--skx-primary);
  background: var(--skx-white);
  border-color: var(--skx-border-c1);
}
.rs-btn--small {
  padding: 0.3rem 0.6rem;
  font-size: 0.6rem;
}
.rs-icon-btn {
  width: 1.4rem;
  height: 1.4rem;
  padding: 0;
  font-size: 0.8rem;
  line-height: 1;
  color: var(--skx-gray-1);
  background: none;
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.rs-badge {
  flex-shrink: 0;
  padding: 0.1rem 0.45rem;
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--skx-gray-1);
  background: var(--skx-white);
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-pill);
}
.rs-badge--running {
  color: var(--skx-primary);
  border-color: var(--skx-border-c2);
}
.rs-badge--done {
  color: var(--skx-ink-2);
  border-color: var(--skx-border-c1);
}
.rs-badge--failed {
  color: var(--skx-ink);
  border-color: var(--skx-ink);
}

/* ── 머리 ────────────────────────────────────────────────── */
.rs-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 1.2rem;
  background: var(--skx-white);
  border-radius: var(--skx-radius-lg);
  box-shadow: var(--skx-shadow-lnb);
}
.rs-head__main {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  min-width: 0;
}
.rs-head__kicker {
  margin: 0;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-head__question {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.4;
  word-break: keep-all;
}
.rs-head__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.rs-status {
  align-self: flex-start;
  padding: 0.15rem 0.55rem;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-primary);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
.rs-status--completed {
  color: var(--skx-white);
  background: var(--skx-primary);
  border-color: var(--skx-primary);
}
.rs-status--failed,
.rs-status--canceled {
  color: var(--skx-gray-1);
  border-color: var(--skx-line);
}

/* ── 계획 카드 ───────────────────────────────────────────── */
.rs-plan__list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.rs-plan__item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.7rem;
}
.rs-plan__no {
  flex-shrink: 0;
  width: 1.2rem;
  font-weight: 700;
  color: var(--skx-primary);
  text-align: center;
}
.rs-plan__input {
  flex: 1;
  min-width: 0;
  padding: 0.45rem 0.6rem;
  font-family: inherit;
  font-size: 0.7rem;
  color: var(--skx-ink);
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
}
.rs-plan__input:focus {
  outline: none;
  border-color: var(--skx-primary);
}
.rs-plan__text {
  flex: 1;
  min-width: 0;
}
.rs-plan__add {
  align-self: flex-start;
}
.rs-plan__problem {
  margin: 0;
  font-size: 0.6rem;
  color: var(--skx-ink);
}

/* ── 진행 패널 ───────────────────────────────────────────── */
.rs-counters {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
  margin: 0;
}
.rs-counter {
  padding: 0.5rem;
  text-align: center;
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
}
.rs-counter dt {
  font-size: 0.55rem;
  color: var(--skx-gray-1);
}
.rs-counter dd {
  margin: 0.2rem 0 0;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.rs-highlight {
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--skx-border-c2);
  border-radius: var(--skx-radius-md);
  animation: rs-pulse 1.6s ease-out 2;
}
.rs-highlight__kicker {
  margin: 0;
  font-size: 0.55rem;
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-highlight__main {
  margin: 0.2rem 0 0;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.rs-highlight__note {
  margin: 0.2rem 0 0;
  font-size: 0.6rem;
  color: var(--skx-gray-1);
}
@keyframes rs-pulse {
  0% {
    box-shadow: 0 0 0 0 var(--skx-border-c1);
  }
  100% {
    box-shadow: 0 0 0 0.6rem transparent;
  }
}
@media (prefers-reduced-motion: reduce) {
  .rs-highlight {
    animation: none;
  }
}
.rs-progress__synth {
  margin: 0;
  font-size: 0.7rem;
  font-weight: 700;
}
.rs-timeline,
.rs-rounds {
  margin: 0;
  padding: 0;
  list-style: none;
}
.rs-timeline {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}
.rs-subq__head {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  font-size: 0.65rem;
}
.rs-subq__no {
  flex-shrink: 0;
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-subq__title {
  flex: 1;
  min-width: 0;
  font-weight: 700;
}
.rs-subq.is-pending .rs-subq__title {
  color: var(--skx-gray-2);
}
.rs-subq__stopped {
  margin: 0.3rem 0 0;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.rs-rounds {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 0.35rem 0 0 0.8rem;
  padding-left: 0.6rem;
  border-left: 2px solid var(--skx-border-c1);
}
.rs-round {
  font-size: 0.6rem;
  line-height: 1.5;
}
.rs-round p {
  margin: 0;
}
.rs-round__line {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.rs-round__no {
  font-weight: 700;
}
.rs-round__stat,
.rs-round__verdict {
  color: var(--skx-gray-1);
}
.rs-round__next {
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-round.is-recheck {
  padding-left: 0.3rem;
  border-left: 2px solid var(--skx-border-c2);
}

/* ── 보고서 ──────────────────────────────────────────────── */
.rs-report {
  gap: 1.2rem;
}
.rs-report__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
}
.rs-report__question {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.4;
}
.rs-report__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin: 0.3rem 0 0;
  font-size: 0.6rem;
  color: var(--skx-gray-1);
}
.rs-report__intro {
  margin: 0;
  padding: 0.6rem 0.8rem;
  font-size: 0.7rem;
  background: var(--skx-white);
  border-left: 3px solid var(--skx-primary);
}
.rs-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.rs-section__heading {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 700;
}
.rs-section__intro,
.rs-future li,
.rs-paper {
  font-size: 0.7rem;
  line-height: 1.7;
}
.rs-section__intro {
  margin: 0;
}
.rs-section__sub {
  margin: 0.3rem 0 0;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-gray-1);
}
.rs-papers,
.rs-future {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0;
  padding-left: 1rem;
}
.rs-paper__who {
  font-weight: 700;
}
.rs-paper__title {
  margin-left: 0.3rem;
  color: var(--skx-gray-1);
}
.rs-paper__title::before {
  content: "「";
}
.rs-paper__title::after {
  content: "」";
}
.rs-paper__summary::before {
  content: ": ";
}
.rs-limits {
  padding: 0.8rem 1rem;
  border: 1px solid var(--skx-border-c2);
  border-radius: var(--skx-radius-md);
}
.rs-limits__title {
  margin: 0 0 0.4rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--skx-primary);
}
.rs-limits ul {
  margin: 0;
  padding-left: 1rem;
  font-size: 0.65rem;
  line-height: 1.7;
}

/* ── 인용칩 ──────────────────────────────────────────────── */
.rs-cite {
  position: relative;
  display: inline-block;
  margin: 0 0.1rem;
}
.rs-cite__chip {
  padding: 0 0.4rem;
  font-family: inherit;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1.6;
  color: var(--skx-primary);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
  cursor: pointer;
}
.rs-cite__chip:hover,
.rs-cite__chip:focus-visible,
.rs-cite__chip[aria-expanded="true"] {
  border-color: var(--skx-primary);
  outline: none;
}
.rs-cite__pop {
  position: absolute;
  top: calc(100% + 0.3rem);
  left: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  width: min(24rem, 80vw);
  padding: 0.8rem;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-ink);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-banner);
}
.rs-cite__title {
  font-size: 0.65rem;
}
.rs-cite__meta {
  color: var(--skx-gray-1);
}
.rs-cite__quote {
  display: block;
  max-height: 8rem;
  padding-left: 0.5rem;
  overflow-y: auto;
  border-left: 2px solid var(--skx-border-c1);
}
.rs-cite__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--skx-gray-1);
}
.rs-cite__pager {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.rs-cite__pager button {
  padding: 0 0.3rem;
  background: none;
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-cite__actions {
  display: flex;
  gap: 0.4rem;
}

/* ── 입력창 + 메뉴 ───────────────────────────────────────── */
.rs-plus {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
/* 결과 검색바는 위치 기준이 없어 오류 문구가 엉뚱한 곳에 뜬다 */
.skx-rsearch:has(> .rs-plus) {
  position: relative;
}
.rs-plus__anchor {
  position: relative;
}
.rs-plus__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.6rem;
  height: 1.6rem;
  padding: 0;
  font-size: 0.9rem;
  line-height: 1;
  color: var(--skx-primary);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: 50%;
  cursor: pointer;
}
.rs-plus__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.rs-plus__menu {
  position: absolute;
  top: calc(100% + 0.3rem);
  left: 0;
  z-index: 40;
  min-width: 16rem;
  margin: 0;
  padding: 0.3rem;
  list-style: none;
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-banner);
}
.rs-plus__item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem;
  font-family: inherit;
  text-align: left;
  background: none;
  border: none;
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-plus__item:hover,
.rs-plus__item:focus-visible,
.rs-plus__item.is-selected {
  background: var(--skx-border-c1);
  outline: none;
}
.rs-plus__icon {
  width: 1rem;
  height: 1rem;
  margin-top: 0.1rem;
}
.rs-plus__text {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}
.rs-plus__label {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.rs-plus__desc {
  font-size: 0.55rem;
  color: var(--skx-gray-1);
  line-height: 1.4;
}
.rs-plus__chip {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0.15rem 0.3rem 0.15rem 0.55rem;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--skx-white);
  background: var(--skx-primary);
  border-radius: var(--skx-radius-pill);
}
.rs-plus__chip-x {
  padding: 0 0.2rem;
  font-size: 0.7rem;
  line-height: 1;
  color: var(--skx-white);
  background: none;
  border: none;
  cursor: pointer;
}
.rs-plus__error {
  position: absolute;
  top: calc(100% + 0.4rem);
  left: 0;
  margin: 0;
  font-size: 0.6rem;
  color: var(--skx-ink);
}
```

- [ ] **Step 6: `nuxt.config.ts` 에 CSS 등록**

현재 코드(13–16행):

```ts
  css: [
    resolve(__dirname, "assets/css/tailwind.css"),
    resolve(__dirname, "assets/css/style_skovix.css"),
  ],
```

교체 코드:

```ts
  css: [
    resolve(__dirname, "assets/css/tailwind.css"),
    resolve(__dirname, "assets/css/style_skovix.css"),
    resolve(__dirname, "assets/css/research.css"),
  ],
```

- [ ] **Step 7: 머리 컴포넌트 작성**

질문·상태 배지·보기 전환·링크 복사·취소·재시도·"같은 질문으로 다시 시작". 계획 없이 실패한 잡은 서버가 재시도를 409 로 거절하므로 재시작 버튼을 대신 보인다.

```vue
<!-- frontend/components/research/ResearchHeader.vue -->
<template>
  <header class="rs-head">
    <div class="rs-head__main">
      <p class="rs-head__kicker">딥리서치</p>
      <h1 class="rs-head__question">{{ question }}</h1>
      <span class="rs-status" :class="`rs-status--${phase}`">{{ phaseLabel(phase) }}</span>
    </div>
    <div class="rs-head__actions">
      <button v-if="canToggle" type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('toggle-layout')">
        {{ layout === "A" ? "문서형으로 보기" : "2단으로 보기" }}
      </button>
      <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('copy-link')">링크 복사</button>
      <button v-if="cancellable" type="button" class="rs-btn rs-btn--ghost rs-btn--small" :disabled="busy" @click="$emit('cancel')">
        취소
      </button>
      <button v-if="phase === 'failed' && canRetry" type="button" class="rs-btn rs-btn--small" :disabled="busy" @click="$emit('retry')">
        다시 시도
      </button>
      <button v-if="restartable" type="button" class="rs-btn rs-btn--small" :disabled="busy" @click="$emit('restart')">
        같은 질문으로 다시 시작
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { phaseLabel, type ResearchPhase } from "~/utils/researchEvents";
import type { ResearchLayout } from "~/utils/researchLayout";

const props = defineProps<{
  question: string;
  phase: ResearchPhase;
  layout: ResearchLayout;
  canToggle: boolean;
  canRetry: boolean;
  busy: boolean;
}>();
defineEmits<{ "toggle-layout": []; "copy-link": []; cancel: []; retry: []; restart: [] }>();

const ACTIVE_PHASES: readonly ResearchPhase[] = ["planning", "awaiting", "queued", "exploring", "synthesizing"];

const cancellable = computed(() => ACTIVE_PHASES.includes(props.phase));
// 계획 없이 실패한 잡은 서버가 재시도를 받지 않는다(409) — 새 잡으로 다시 시작한다
const restartable = computed(() => props.phase === "canceled" || (props.phase === "failed" && !props.canRetry));
</script>
```

- [ ] **Step 8: 페이지 작성 (블록 자리표시 포함)**

`AppSidebar` 는 기록 영역(C1) 개편 뒤 기록 props 없이 스스로 기록을 읽는다고 가정한다 — `cart`·`save` 이벤트만 받는다. 링크 복사는 운영 게이트웨이가 http(보안 컨텍스트 아님)라 clipboard API 가 없을 수 있어 `prompt` 로 대체한다.

```vue
<!-- frontend/pages/research/[id].vue -->
<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="rs-page">
      <div v-if="notFound" class="rs-card rs-state">
        <h1 class="rs-state__title">찾을 수 없는 연구입니다</h1>
        <p class="rs-muted">주소가 잘못됐거나 지워진 연구입니다.</p>
        <NuxtLink to="/papers" class="rs-btn">논문 검색으로 돌아가기</NuxtLink>
      </div>

      <div v-else-if="loadError" class="rs-card rs-state">
        <p>{{ loadError }}</p>
        <button type="button" class="rs-btn" @click="load">다시 불러오기</button>
      </div>

      <div v-else-if="!view || !phase" class="rs-card rs-state">
        <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
        <p class="rs-muted">연구를 불러오는 중입니다</p>
      </div>

      <template v-else>
        <ResearchHeader
          :question="view.question"
          :phase="phase"
          :layout="layout"
          :can-toggle="canToggle"
          :can-retry="canRetry"
          :busy="busy || restarting"
          @toggle-layout="toggleLayout"
          @copy-link="copyLink"
          @cancel="onCancel"
          @retry="retry"
          @restart="onRestart"
        />
        <p v-if="actionError || pageError" class="rs-alert" role="alert">{{ actionError || pageError }}</p>

        <div class="rs-body" :class="`rs-body--${layout}`">
          <div class="rs-col-main">
            <section v-if="phase !== 'completed'" class="rs-block rs-block--plan">
              <div v-if="phase === 'planning'" class="rs-card rs-card--wait">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <p>연구 계획을 세우는 중입니다</p>
              </div>
              <div v-else-if="phase === 'awaiting'" class="rs-card">
                <p class="rs-card__title">연구 계획 확인</p>
                <ol class="rs-plan__list">
                  <li v-for="(q, i) in view.plan" :key="i" class="rs-plan__item">
                    <span class="rs-plan__no">{{ i + 1 }}</span>
                    <span class="rs-plan__text">{{ q }}</span>
                  </li>
                </ol>
                <div class="rs-card__actions">
                  <button type="button" class="rs-btn" :disabled="busy" @click="approve()">승인하고 시작</button>
                  <button type="button" class="rs-btn rs-btn--ghost" :disabled="busy" @click="onCancel">취소</button>
                </div>
              </div>
              <div v-else-if="phase === 'queued'" class="rs-card rs-card--wait">
                <p>앞선 연구가 끝나면 시작합니다</p>
              </div>
              <div v-else-if="phase === 'exploring'" class="rs-card">
                <p class="rs-card__title">연구 계획</p>
                <ol class="rs-plan__list">
                  <li v-for="(q, i) in view.plan" :key="i" class="rs-plan__item">
                    <span class="rs-plan__no">{{ i + 1 }}</span>
                    <span class="rs-plan__text">{{ q }}</span>
                  </li>
                </ol>
              </div>
              <div v-else-if="phase === 'synthesizing'" class="rs-card rs-card--wait">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <p>{{ synthLine }}</p>
              </div>
              <div v-else-if="phase === 'failed'" class="rs-card rs-card--error">
                <p class="rs-card__title">연구가 도중에 멈췄습니다</p>
                <p v-if="view.lastError" class="rs-muted">{{ view.lastError }}</p>
                <div class="rs-card__actions">
                  <button v-if="canRetry" type="button" class="rs-btn" :disabled="busy" @click="retry">{{ retryLabel }}</button>
                  <button v-else type="button" class="rs-btn" :disabled="restarting" @click="onRestart">같은 질문으로 다시 시작</button>
                </div>
              </div>
              <div v-else-if="phase === 'canceled'" class="rs-card">
                <p class="rs-card__title">취소된 연구입니다</p>
                <div class="rs-card__actions">
                  <button type="button" class="rs-btn" :disabled="restarting" @click="onRestart">같은 질문으로 다시 시작</button>
                </div>
              </div>
            </section>

            <section v-if="phase === 'completed' && view.report" class="rs-block rs-block--report">
              <div class="rs-card">
                <p class="rs-card__title">보고서</p>
                <p class="rs-muted">절 {{ view.report.sections.length }}개</p>
              </div>
            </section>
          </div>

          <aside class="rs-col-side">
            <section class="rs-card">
              <h2 class="rs-card__title">진행</h2>
              <p class="rs-muted">{{ phaseLabel(phase) }}</p>
            </section>
          </aside>
        </div>
      </template>
    </main>

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
import { safeLocalStorage } from "~/utils/browserId";
import { phaseLabel, researchPhase, synthProgress } from "~/utils/researchEvents";
import { researchErrorMessage } from "~/utils/researchErrors";
import { DEFAULT_MAX_SUBQUESTIONS } from "~/utils/researchInput";
import {
  SHOW_LAYOUT_TOGGLE,
  WIDE_MIN_PX,
  effectiveLayout,
  readLayoutPref,
  writeLayoutPref,
  type ResearchLayout,
} from "~/utils/researchLayout";

const route = useRoute();
const { view, notFound, loadError, actionError, busy, load, approve, retry, cancel } = useResearchJob(
  () => String(route.params.id ?? ""),
);
const { startResearch } = useResearchStarter();

const phase = computed(() => (view.value ? researchPhase(view.value) : null));
const maxSubquestions = computed(() => Number(view.value?.params.max_subquestions) || DEFAULT_MAX_SUBQUESTIONS);
// 계획이 없는 잡의 재시도는 서버가 409 로 거절한다
const canRetry = computed(() => (view.value?.plan.length ?? 0) > 0);
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
const synthLine = computed(() => {
  if (!view.value) return "";
  const p = synthProgress(view.value);
  return p.total ? `보고서 작성 중 ${p.current}/${p.total}` : "보고서 작성 중";
});

useHead({ title: () => (view.value ? `${view.value.question} — 딥리서치` : "딥리서치") });

// ── 배치 A·B ──────────────────────────────────────────────
// 서버 렌더에는 폭을 모르므로 넓은 화면으로 두고, 마운트 뒤 실제 폭으로 맞춘다
const wide = ref(true);
const layoutPref = ref<ResearchLayout | null>(null);
const layout = computed(() => effectiveLayout(layoutPref.value, wide.value));
const canToggle = computed(() => SHOW_LAYOUT_TOGGLE && wide.value);
let media: MediaQueryList | null = null;

function onMediaChange(e: MediaQueryListEvent): void {
  wide.value = e.matches;
}

function toggleLayout(): void {
  const next: ResearchLayout = layout.value === "A" ? "B" : "A";
  layoutPref.value = next;
  writeLayoutPref(safeLocalStorage(), next);
}

onMounted(() => {
  layoutPref.value = readLayoutPref(safeLocalStorage());
  media = window.matchMedia(`(min-width: ${WIDE_MIN_PX}px)`);
  wide.value = media.matches;
  media.addEventListener("change", onMediaChange);
});

onBeforeUnmount(() => {
  media?.removeEventListener("change", onMediaChange);
});

// ── 동작 ──────────────────────────────────────────────────
const restarting = ref(false);
const pageError = ref("");

function onCancel(): void {
  if (window.confirm("이 연구를 취소할까요? 진행 중인 단계가 끝나는 대로 멈춥니다.")) void cancel();
}

async function onRestart(): Promise<void> {
  if (!view.value || restarting.value) return;
  restarting.value = true;
  pageError.value = "";
  try {
    const jobId = await startResearch(view.value.question);
    await navigateTo(`/research/${jobId}`);
  } catch (e) {
    pageError.value = researchErrorMessage(e, "새 연구를 시작하지 못했습니다");
  } finally {
    restarting.value = false;
  }
}

async function copyLink(): Promise<void> {
  const url = window.location.href;
  try {
    await navigator.clipboard.writeText(url);
    showToast("링크를 복사했습니다");
  } catch {
    // 운영 게이트웨이가 http 라 clipboard API 가 없을 수 있다(보안 컨텍스트 전용)
    window.prompt("아래 주소를 복사하세요", url);
  }
}

// ── 토스트 ────────────────────────────────────────────────
const toast = ref("");
let toastTimer: ReturnType<typeof setTimeout> | null = null;

function showToast(msg: string): void {
  toast.value = msg;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = "";
  }, 2400);
}
</script>
```

- [ ] **Step 9: 컴파일 확인**

```bash
cd frontend
npx nuxi typecheck 2>&1 | grep "error TS" | grep -v "pages/search-classic.vue"
npm run build 2>&1 | tail -1
```
기대: 첫 명령 출력 없음, 둘째 `└  ✨ Build complete!`.

- [ ] **Step 10: 커밋**

```bash
git add frontend/utils/researchLayout.ts frontend/tests/unit/researchLayout.test.ts frontend/assets/css/research.css frontend/nuxt.config.ts frontend/components/research/ResearchHeader.vue "frontend/pages/research/[id].vue"
git commit -m "[Feat] round04b — 딥리서치 페이지 골격(상태 기계·A/B 배치·머리)과 전용 CSS"
```

---

### Task 32: 계획 카드 (`PlanCard.vue`)

승인 대기에서는 하위질문을 바로 고치기·삭제·추가(상한 `max_subquestions` — GET 응답의 `params`, 없으면 6)하고 [승인하고 시작]·[취소]. 탐색 중에는 같은 카드가 읽기 전용으로 하위질문별 진행을 보인다(spec §6-2 표).

- 항목마다 고정 키를 줘서, 지운 항목 뒤의 입력칸이 앞 항목 글을 물려받지 않게 한다.
- snapshot 이 같은 계획을 새 배열로 다시 보내도 사용자가 고치던 내용을 덮지 않는다(내용이 같으면 무시).
- 검증은 `planProblem`(Task 29) — 문제가 있으면 승인 버튼을 막고 사유를 보인다.

**Files:**
- Create: `frontend/components/research/PlanCard.vue`
- Modify: `frontend/pages/research/[id].vue` (Task 31 에서 만든 자리표시 두 곳과 import)

- [ ] **Step 1: 계획 카드 작성**

```vue
<!-- frontend/components/research/PlanCard.vue -->
<template>
  <section class="rs-card rs-plan" :aria-busy="busy">
    <header class="rs-card__head">
      <h2 class="rs-card__title">{{ editable ? "연구 계획 확인" : "연구 계획" }}</h2>
      <p v-if="editable" class="rs-muted">하위질문을 고치거나 지우고 더할 수 있습니다. 최대 {{ max }}개까지입니다.</p>
    </header>

    <ol v-if="editable" ref="list" class="rs-plan__list">
      <li v-for="(_, i) in items" :key="keys[i]" class="rs-plan__item">
        <span class="rs-plan__no">{{ i + 1 }}</span>
        <input
          v-model="items[i]"
          class="rs-plan__input"
          type="text"
          :maxlength="PLAN_ITEM_MAX"
          :aria-label="`하위질문 ${i + 1}`"
          :disabled="busy"
        />
        <button
          type="button"
          class="rs-icon-btn"
          :aria-label="`하위질문 ${i + 1} 삭제`"
          :disabled="busy || items.length <= 1"
          @click="remove(i)"
        >
          ×
        </button>
      </li>
    </ol>
    <ol v-else class="rs-plan__list">
      <li v-for="sq in subqs" :key="sq.idx" class="rs-plan__item" :class="`is-${sq.status}`">
        <span class="rs-plan__no">{{ sq.idx + 1 }}</span>
        <span class="rs-plan__text">{{ sq.title }}</span>
        <span class="rs-badge" :class="`rs-badge--${sq.status}`">{{ subqStatusLabel(sq) }}</span>
      </li>
    </ol>

    <template v-if="editable">
      <button type="button" class="rs-btn rs-btn--ghost rs-plan__add" :disabled="busy || items.length >= max" @click="add">
        + 하위질문 추가
      </button>
      <p v-if="problem" class="rs-plan__problem" role="alert">{{ problem }}</p>
      <div class="rs-card__actions">
        <button type="button" class="rs-btn" :disabled="busy || !!problem" @click="approve">승인하고 시작</button>
        <button type="button" class="rs-btn rs-btn--ghost" :disabled="busy" @click="$emit('cancel')">취소</button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import type { SubqView } from "~/types/research";
import { subqStatusLabel } from "~/utils/researchEvents";
import { PLAN_ITEM_MAX, planProblem } from "~/utils/researchInput";

const props = withDefaults(
  defineProps<{ plan: string[]; max: number; editable?: boolean; busy?: boolean; subqs?: SubqView[] }>(),
  { editable: false, busy: false, subqs: () => [] },
);
const emit = defineEmits<{ approve: [plan: string[]]; cancel: [] }>();

const list = ref<HTMLOListElement | null>(null);
const items = ref<string[]>([]);
// 항목을 지우면 뒤 항목의 입력칸이 앞 항목의 글을 물려받지 않게 항목마다 고정 키를 준다
const keys = ref<number[]>([]);
let nextKey = 0;
let received: string[] = [];

const problem = computed(() => planProblem(items.value, props.max));

// snapshot 이 같은 계획을 새 배열로 다시 보내도 사용자가 고치던 내용을 덮지 않는다
watch(
  () => props.plan,
  (plan) => {
    if (plan.length === received.length && plan.every((t, i) => t === received[i])) return;
    received = [...plan];
    items.value = [...plan];
    keys.value = plan.map(() => nextKey++);
  },
  { immediate: true },
);

function remove(i: number): void {
  items.value.splice(i, 1);
  keys.value.splice(i, 1);
}

async function add(): Promise<void> {
  items.value.push("");
  keys.value.push(nextKey++);
  await nextTick();
  const inputs = list.value?.querySelectorAll<HTMLInputElement>("input");
  inputs?.[inputs.length - 1]?.focus();
}

function approve(): void {
  if (problem.value) return;
  emit("approve", items.value.map((t) => t.trim()));
}
</script>
```

- [ ] **Step 2: 페이지에 끼우기**

1) import 추가

찾을 코드:

```ts
import ResearchHeader from "~/components/research/ResearchHeader.vue";
```

바꿀 코드:

```ts
import PlanCard from "~/components/research/PlanCard.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
```

2) 승인 대기 자리표시 → 편집 가능한 계획 카드

찾을 코드:

```vue
              <div v-else-if="phase === 'awaiting'" class="rs-card">
                <p class="rs-card__title">연구 계획 확인</p>
                <ol class="rs-plan__list">
                  <li v-for="(q, i) in view.plan" :key="i" class="rs-plan__item">
                    <span class="rs-plan__no">{{ i + 1 }}</span>
                    <span class="rs-plan__text">{{ q }}</span>
                  </li>
                </ol>
                <div class="rs-card__actions">
                  <button type="button" class="rs-btn" :disabled="busy" @click="approve()">승인하고 시작</button>
                  <button type="button" class="rs-btn rs-btn--ghost" :disabled="busy" @click="onCancel">취소</button>
                </div>
              </div>
```

바꿀 코드:

```vue
              <PlanCard
                v-else-if="phase === 'awaiting'"
                :plan="view.plan"
                :max="maxSubquestions"
                editable
                :busy="busy"
                @approve="approve"
                @cancel="onCancel"
              />
```

3) 탐색 중 자리표시 → 읽기 전용 계획 카드

찾을 코드:

```vue
              <div v-else-if="phase === 'exploring'" class="rs-card">
                <p class="rs-card__title">연구 계획</p>
                <ol class="rs-plan__list">
                  <li v-for="(q, i) in view.plan" :key="i" class="rs-plan__item">
                    <span class="rs-plan__no">{{ i + 1 }}</span>
                    <span class="rs-plan__text">{{ q }}</span>
                  </li>
                </ol>
              </div>
```

바꿀 코드:

```vue
              <PlanCard v-else-if="phase === 'exploring'" :plan="view.plan" :max="maxSubquestions" :subqs="view.subqs" />
```


- [ ] **Step 3: 컴파일 확인**

```bash
cd frontend
npx nuxi typecheck 2>&1 | grep "error TS" | grep -v "pages/search-classic.vue"
npm run build 2>&1 | tail -1
```
기대: 첫 명령 출력 없음, 둘째 `└  ✨ Build complete!`.

- [ ] **Step 4: 커밋**

```bash
git add frontend/components/research/PlanCard.vue "frontend/pages/research/[id].vue"
git commit -m "[Feat] round04b — 딥리서치 계획 카드(고치기·삭제·추가·상한·승인·취소)"
```

---

### Task 33: 진행 패널 (`ProgressPanel.vue`)

- 탐색 이후 단계에서 카운터 3개(검토한 논문·채택한 근거·재검색 — 값을 모르면 `—`), 하위질문별 **회차 타임라인**(검색어·대목 수·새 논문 수·판정·사유·"→ '○○'(으)로 재검색"), 탐색 중에는 **자기점검 강조 카드**("근거 부족 → '○○'(으)로 재검색" — spec §6-2).
- 종합 중에는 "탐색 완료 요약" + "보고서 작성 중 2/3", 완료 뒤에는 같은 패널이 **탐색 경로**가 된다. 실패·취소는 "멈춘 지점"을 표시한다(도는 중이던·실패한 하위질문, 없으면 "보고서 작성 단계에서 멈췄습니다").
- 보강 전 잡(회차 출처가 trail·queries)은 "검색어 이력과 마지막 판정만" 이라고 알린다.
- 강조 정도(색·움직임)는 기획자 결정 항목(spec §7-3 5번) — 지금은 테두리 + 짧은 펄스 2회, `prefers-reduced-motion` 이면 멈춘다(CSS 는 Task 31 에서 이미 들어갔다).

**Files:**
- Create: `frontend/components/research/ProgressPanel.vue`
- Modify: `frontend/pages/research/[id].vue` (진행 패널 자리표시와 import)

- [ ] **Step 1: 진행 패널 작성**

```vue
<!-- frontend/components/research/ProgressPanel.vue -->
<template>
  <section class="rs-card rs-progress">
    <h2 class="rs-card__title">{{ title }}</h2>

    <p v-if="phase === 'planning'" class="rs-muted">계획이 확정되면 탐색 과정이 여기에 나타납니다.</p>
    <p v-else-if="phase === 'awaiting'" class="rs-muted">
      계획을 승인하면 하위질문마다 논문을 찾고, 근거가 부족하다고 판단하면 검색어를 바꿔 다시 찾습니다.
    </p>
    <p v-else-if="phase === 'queued'" class="rs-muted">대기열에 들어갔습니다. 앞선 연구가 끝나면 시작합니다.</p>

    <template v-else>
      <dl class="rs-counters">
        <div class="rs-counter">
          <dt>검토한 논문</dt>
          <dd>{{ shown(view.counters.papersReviewed) }}</dd>
        </div>
        <div class="rs-counter">
          <dt>채택한 근거</dt>
          <dd>{{ shown(view.counters.evidenceAdopted) }}</dd>
        </div>
        <div class="rs-counter">
          <dt>재검색</dt>
          <dd>{{ shown(view.counters.rechecks) }}</dd>
        </div>
      </dl>

      <div v-if="phase === 'exploring' && view.highlight" class="rs-highlight" role="status" aria-live="polite">
        <p class="rs-highlight__kicker">자기점검 · 하위질문 {{ view.highlight.subqIdx + 1 }} · {{ view.highlight.round }}회차</p>
        <p class="rs-highlight__main">근거 부족 → ‘{{ view.highlight.nextQuery }}’(으)로 재검색</p>
        <p v-if="view.highlight.note" class="rs-highlight__note">{{ view.highlight.note }}</p>
      </div>

      <p v-if="phase === 'synthesizing'" class="rs-progress__synth">{{ synthLine }}</p>
      <p v-if="view.source === 'trail' || view.source === 'queries'" class="rs-muted rs-progress__note">
        회차별 판정을 기록하기 전에 만든 연구라, 검색어 이력과 마지막 판정만 보여 줍니다.
      </p>

      <ol class="rs-timeline">
        <li
          v-for="sq in view.subqs"
          :key="sq.idx"
          class="rs-subq"
          :class="[`is-${sq.status}`, { 'is-stopped': stoppedIdx === sq.idx }]"
        >
          <div class="rs-subq__head">
            <span class="rs-subq__no">{{ sq.idx + 1 }}</span>
            <span class="rs-subq__title">{{ sq.title }}</span>
            <span class="rs-badge" :class="`rs-badge--${sq.status}`">{{ subqStatusLabel(sq) }}</span>
          </div>
          <p v-if="stoppedIdx === sq.idx" class="rs-subq__stopped">
            여기서 멈췄습니다<span v-if="sq.error"> — {{ sq.error }}</span>
          </p>
          <ol v-if="sq.rounds.length" class="rs-rounds">
            <li v-for="r in sq.rounds" :key="r.round" class="rs-round" :class="{ 'is-recheck': !!r.nextQuery }">
              <p class="rs-round__line">
                <span class="rs-round__no">{{ r.round }}회차</span>
                <span class="rs-round__query">‘{{ r.query }}’</span>
                <span v-if="r.foundChunks !== null" class="rs-round__stat">대목 {{ r.foundChunks }}개</span>
                <span v-if="r.newPapers !== null" class="rs-round__stat">새 논문 {{ r.newPapers }}편</span>
              </p>
              <p v-if="r.verdict" class="rs-round__verdict">
                {{ verdictLabel(r.verdict) }}<span v-if="r.note"> — {{ r.note }}</span>
              </p>
              <p v-if="r.nextQuery" class="rs-round__next">→ ‘{{ r.nextQuery }}’(으)로 재검색</p>
            </li>
          </ol>
        </li>
      </ol>
      <p v-if="stoppedAtSynth" class="rs-subq__stopped">보고서 작성 단계에서 멈췄습니다</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { ResearchView } from "~/types/research";
import { subqStatusLabel, synthProgress, verdictLabel, type ResearchPhase } from "~/utils/researchEvents";

const props = defineProps<{ view: ResearchView; phase: ResearchPhase }>();

const TITLES: Partial<Record<ResearchPhase, string>> = {
  synthesizing: "탐색 완료 요약",
  completed: "탐색 경로",
  failed: "멈춘 지점",
  canceled: "멈춘 지점",
};

const title = computed(() => TITLES[props.phase] ?? "진행");
const stopped = computed(() => props.phase === "failed" || props.phase === "canceled");
const stoppedIdx = computed(() => {
  if (!stopped.value) return null;
  return props.view.subqs.find((s) => s.status === "failed" || s.status === "running")?.idx ?? null;
});
const stoppedAtSynth = computed(
  () => stopped.value && stoppedIdx.value === null && (props.view.synth.status !== null || props.view.stage === "explored"),
);
const synthLine = computed(() => {
  const p = synthProgress(props.view);
  return p.total ? `보고서 작성 중 ${p.current}/${p.total}` : "보고서 작성 중";
});

function shown(n: number | null): string {
  return n === null ? "—" : n.toLocaleString("ko-KR");
}
</script>
```

- [ ] **Step 2: 페이지에 끼우기**

1) import 추가

찾을 코드:

```ts
import PlanCard from "~/components/research/PlanCard.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
```

바꿀 코드:

```ts
import PlanCard from "~/components/research/PlanCard.vue";
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
```

2) 쓰지 않게 된 `phaseLabel` import 제거

찾을 코드:

```ts
import { phaseLabel, researchPhase, synthProgress } from "~/utils/researchEvents";
```

바꿀 코드:

```ts
import { researchPhase, synthProgress } from "~/utils/researchEvents";
```

3) 진행 패널 자리표시 → `ProgressPanel`

찾을 코드:

```vue
            <section class="rs-card">
              <h2 class="rs-card__title">진행</h2>
              <p class="rs-muted">{{ phaseLabel(phase) }}</p>
            </section>
```

바꿀 코드:

```vue
            <ProgressPanel :view="view" :phase="phase" />
```


- [ ] **Step 3: 컴파일 확인**

```bash
cd frontend
npx nuxi typecheck 2>&1 | grep "error TS" | grep -v "pages/search-classic.vue"
npm run build 2>&1 | tail -1
```
기대: 첫 명령 출력 없음, 둘째 `└  ✨ Build complete!`.

- [ ] **Step 4: 커밋**

```bash
git add frontend/components/research/ProgressPanel.vue "frontend/pages/research/[id].vue"
git commit -m "[Feat] round04b — 딥리서치 진행 패널(카운터·회차 타임라인·자기점검 강조·탐색 경로)"
```

---

### Task 34: 보고서·인용칩·원문 보기

- `ReportView.vue`(spec §6-3): 머리(질문·수록 범위 "2002~2026 논문 N편 기준"·생성 시각·링크 복사), 서론 한 줄(화면이 `report.stats` 로 만든다), 절별 소제목·도입 문단(인용칩)·대표 논문(`저자 (연도) 「제목」: 요약` + 칩)·향후 과제, 눈에 띄는 **한계 섹션**(`limitations` 가공 없이). 모든 모델 글은 `splitCitations` 로 나눠 글자 보간(`{{ }}`)과 칩 컴포넌트로만 그린다 — `v-html` 없음(spec D9).
- `CitationChip.vue`: 칩 라벨 `김 2019`. 올리거나(150ms 지연 닫힘), 키보드 초점이 오거나, 누르면(고정) 팝오버 — 제목, 저자·학술지·권호·연도·피인용·등재구분, 그 절에서 매칭된 대목(`citeChunks`), 여러 개면 1/2 넘기기, 쪽수(0 이면 "쪽 정보 없음"), [원문 보기]·[논문 상세](`/papers/<cnts_id>`). Esc 로 닫고 칩으로 초점을 돌린다. 화면 오른쪽 끝의 칩은 팝오버를 넘친 만큼 왼쪽으로 민다. 팝오버는 `<p>` 안에 들어가므로 블록 요소 없이 `span` 으로만 짠다.
- 원문 보기: 페이지가 `GET /api/books/{cnts_id}/pdf` 로 먼저 확인하고(응답 머리만 받고 즉시 끊는다 — FastAPI GET 라우트는 HEAD 를 따로 받지 않는다), 404 면 "원문 파일이 없습니다" 토스트, 있으면 `PdfViewer` 를 해당 쪽으로 연다.
- `PdfViewer.vue` 에 선택 prop `page` — pdf.js 뷰어 해시 `#page=N`(1부터). 저장된 쪽수는 0부터 세므로(`ingestion/extractor.py` "1-based → 0-based") 칩은 `page_start + 1` 을 넘긴다.

**Files:**
- Create: `frontend/utils/researchReport.ts`
- Test: `frontend/tests/unit/researchReport.test.ts`
- Create: `frontend/components/research/CitationChip.vue`
- Create: `frontend/components/research/ReportView.vue`
- Modify: `frontend/components/PdfViewer.vue` (props 23–26행, `viewerUrl` 30–33행)
- Modify: `frontend/pages/research/[id].vue` (보고서 자리표시·PDF 뷰어·import)

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
// frontend/tests/unit/researchReport.test.ts
import { describe, expect, it } from "vitest";
import type { ResearchReport } from "~/types/research";
import { paperByline, rangeLabel, reportIntro } from "~/utils/researchReport";

function report(over: Partial<ResearchReport> = {}): ResearchReport {
  return {
    question: "q",
    range: { from: "2002", to: "2026", n_papers: 1234 },
    sections: [],
    evidence: {
      E1: { cnts_id: "C1", meta: {}, chunks: [] },
      E2: { cnts_id: "C2", meta: {}, chunks: [] },
    },
    trail: [
      { subquestion: "가", queries: ["가"], evidence_count: 1, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
      { subquestion: "나", queries: ["나"], evidence_count: 1, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
      { subquestion: "다", queries: ["다"], evidence_count: 0, verdict: "insufficient", note: "", parse_failed: false, failed: false, capped: 0 },
    ],
    limitations: [],
    ...over,
  };
}

describe("rangeLabel", () => {
  it("수록 범위를 연도와 편수로 쓴다", () => {
    expect(rangeLabel({ from: "2002", to: "2026", n_papers: 1234 })).toBe("2002~2026 논문 1,234편 기준");
    expect(rangeLabel({ from: "2019", to: "2019", n_papers: 3 })).toBe("2019년 논문 3편 기준");
    expect(rangeLabel({ from: null, to: null, n_papers: 3 })).toBe("논문 3편 기준");
  });

  it("범위를 모르면 쓰지 않는다", () => {
    expect(rangeLabel(null)).toBeNull();
    expect(rangeLabel({})).toBeNull();
  });
});

describe("reportIntro", () => {
  it("stats 가 있으면 검토·채택 수를 쓴다", () => {
    expect(reportIntro(report({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 } })))
      .toBe("하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
  });

  it("보강 전 보고서는 근거 수만 쓴다", () => {
    expect(reportIntro(report())).toBe("하위질문 3개로 나눠 논문 2편을 근거로 삼았다.");
  });
});

describe("paperByline", () => {
  it("첫 저자와 연도, 여럿이면 외를 붙인다", () => {
    expect(paperByline({ personal_author: "김철수; 이영희", pub_date: "2019-03" })).toBe("김철수 외 (2019)");
    expect(paperByline({ personal_author: "김철수" })).toBe("김철수");
    expect(paperByline({ personal_author: "Smith, John", pub_date: "2021" })).toBe("Smith, John (2021)");
    expect(paperByline(undefined)).toBe("저자 미상");
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd frontend && npx vitest run tests/unit/researchReport.test.ts
```
기대: `Cannot find module '~/utils/researchReport' …`, `Test Files  1 failed (1)`.

- [ ] **Step 3: 최소 구현**

```ts
// frontend/utils/researchReport.ts
import type { EvidenceMeta, ReportRange, ResearchReport } from "../types/research";
import { pubYear, splitAuthors } from "./citations";

export function rangeLabel(range: Partial<ReportRange> | null | undefined): string | null {
  if (!range?.n_papers) return null;
  const count = `논문 ${range.n_papers.toLocaleString("ko-KR")}편 기준`;
  if (!range.from || !range.to) return count;
  const years = range.from === range.to ? `${range.from}년` : `${range.from}~${range.to}`;
  return `${years} ${count}`;
}

// 서론 문장은 모델이 아니라 화면이 만든다 — 수치를 모델에게 쓰게 하면 틀린 숫자가 실린다
export function reportIntro(report: ResearchReport): string {
  const subqs = report.trail.length || report.sections.length;
  const s = report.stats;
  if (s) {
    return `하위질문 ${subqs}개로 나눠 논문 ${s.papers_reviewed}편을 검토하고 ${s.evidence_adopted}편을 근거로 삼았다.`;
  }
  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
}

export function paperByline(meta: EvidenceMeta | undefined): string {
  const authors = splitAuthors(meta?.personal_author);
  const who = authors.length > 1 ? `${authors[0]} 외` : (authors[0] ?? "저자 미상");
  const year = pubYear(meta?.pub_date);
  return year ? `${who} (${year})` : who;
}
```

- [ ] **Step 4: 실행해 통과 확인**

```bash
cd frontend && npx vitest run tests/unit/researchReport.test.ts
```
기대: `Test Files  1 passed (1)`, `Tests  5 passed (5)`.

```bash
cd frontend
npx tsc --noEmit --strict --noUncheckedIndexedAccess --verbatimModuleSyntax --isolatedModules \
  --target es2022 --module esnext --moduleResolution bundler --lib es2022,dom --skipLibCheck \
  types/research.ts utils/citations.ts utils/researchReport.ts
```
기대: 출력 없음.

- [ ] **Step 5: `PdfViewer.vue` 에 `page` prop 추가**

현재 코드(`<script setup>` 안, 23–33행):

```ts
const props = defineProps<{
  cntsId: string;
  title?: string;
}>();

defineEmits<{ close: [] }>();

const viewerUrl = computed(() => {
  const file = encodeURIComponent(`/api/books/${props.cntsId}/pdf`);
  return `/pdfjs/web/viewer.html?file=${file}`;
});
```

교체 코드:

```ts
const props = defineProps<{
  cntsId: string;
  title?: string;
  page?: number;
}>();

defineEmits<{ close: [] }>();

const viewerUrl = computed(() => {
  const file = encodeURIComponent(`/api/books/${props.cntsId}/pdf`);
  // pdf.js 뷰어는 해시의 page 로 첫 화면 쪽을 정한다(1부터 센다)
  const hash = props.page && props.page > 0 ? `#page=${props.page}` : "";
  return `/pdfjs/web/viewer.html?file=${file}${hash}`;
});
```

기존 호출부(`pages/books/[cnts_id].vue` 등)는 `page` 를 넘기지 않으므로 동작이 그대로다.

- [ ] **Step 6: 인용칩 작성**

```vue
<!-- frontend/components/research/CitationChip.vue -->
<template>
  <span
    ref="wrap"
    class="rs-cite"
    @mouseenter="show"
    @mouseleave="scheduleHide"
    @focusin="show"
    @focusout="onFocusOut"
    @keydown.escape.stop="close"
  >
    <button
      ref="chip"
      type="button"
      class="rs-cite__chip"
      :aria-expanded="open"
      :aria-controls="popId"
      :aria-label="`근거 ${eid}: ${title}`"
      @click="togglePin"
    >
      {{ label }}
    </button>
    <span
      v-if="open"
      :id="popId"
      ref="pop"
      class="rs-cite__pop"
      role="dialog"
      :aria-label="`${eid} 근거`"
      :style="shift ? { left: `${shift}px` } : undefined"
    >
      <strong class="rs-cite__title">{{ title }}</strong>
      <span v-if="meta" class="rs-cite__meta">{{ meta }}</span>
      <template v-if="current">
        <span class="rs-cite__quote">{{ current.text }}</span>
        <span class="rs-cite__foot">
          <span>{{ pageLabel(current) }}</span>
          <span v-if="chunks.length > 1" class="rs-cite__pager">
            <button type="button" aria-label="이전 대목" :disabled="index === 0" @click="index -= 1">‹</button>
            <span>{{ index + 1 }}/{{ chunks.length }}</span>
            <button type="button" aria-label="다음 대목" :disabled="index >= chunks.length - 1" @click="index += 1">›</button>
          </span>
        </span>
      </template>
      <span v-else class="rs-cite__quote rs-muted">이 절에서 매칭된 대목이 없습니다</span>
      <span v-if="evidence" class="rs-cite__actions">
        <button type="button" class="rs-btn rs-btn--small" @click="openPdf">원문 보기</button>
        <NuxtLink :to="`/papers/${evidence.cnts_id}`" class="rs-btn rs-btn--small rs-btn--ghost">논문 상세</NuxtLink>
      </span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import type { OpenPdfPayload, ReportChunk, ReportEvidence } from "~/types/research";
import { citeLabel, metaLine, pageLabel, pdfPage } from "~/utils/citations";

const props = defineProps<{ eid: string; evidence?: ReportEvidence; chunks: ReportChunk[] }>();
const emit = defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();

// 포인터가 칩에서 팝오버로 옮겨 가는 사이에 닫히지 않게 조금 기다린다
const HIDE_DELAY_MS = 150;
const EDGE_PX = 8;

const popId = useId();
const wrap = ref<HTMLElement | null>(null);
const chip = ref<HTMLButtonElement | null>(null);
const pop = ref<HTMLElement | null>(null);
const shift = ref(0);
const open = ref(false);
const pinned = ref(false);
const index = ref(0);
let hideTimer: ReturnType<typeof setTimeout> | null = null;

const label = computed(() => citeLabel(props.evidence?.meta, props.eid));
const title = computed(() => props.evidence?.meta.title || "근거 정보를 찾을 수 없습니다");
const meta = computed(() => metaLine(props.evidence?.meta));
const current = computed<ReportChunk | undefined>(() => props.chunks[index.value]);

watch(() => props.chunks, () => {
  index.value = 0;
});

// 화면 오른쪽 끝의 칩은 팝오버가 잘리고 가로 스크롤이 생긴다 — 넘친 만큼 왼쪽으로 민다
watch(open, async (isOpen) => {
  shift.value = 0;
  if (!isOpen) return;
  await nextTick();
  const rect = pop.value?.getBoundingClientRect();
  if (!rect) return;
  const overflow = rect.right - (window.innerWidth - EDGE_PX);
  if (overflow > 0) shift.value = -Math.min(overflow, Math.max(0, rect.left - EDGE_PX));
});

function cancelHide(): void {
  if (hideTimer) clearTimeout(hideTimer);
  hideTimer = null;
}

function show(): void {
  cancelHide();
  open.value = true;
}

function scheduleHide(): void {
  if (pinned.value) return;
  cancelHide();
  hideTimer = setTimeout(() => {
    open.value = false;
  }, HIDE_DELAY_MS);
}

function close(): void {
  cancelHide();
  pinned.value = false;
  open.value = false;
  chip.value?.focus();
}

function togglePin(): void {
  pinned.value = !pinned.value;
  open.value = true;
  if (pinned.value) document.addEventListener("click", onDocumentClick);
  else document.removeEventListener("click", onDocumentClick);
}

function onFocusOut(e: FocusEvent): void {
  if (e.relatedTarget instanceof Node && wrap.value?.contains(e.relatedTarget)) return;
  pinned.value = false;
  document.removeEventListener("click", onDocumentClick);
  scheduleHide();
}

function onDocumentClick(e: MouseEvent): void {
  if (e.target instanceof Node && wrap.value?.contains(e.target)) return;
  pinned.value = false;
  open.value = false;
  document.removeEventListener("click", onDocumentClick);
}

function openPdf(): void {
  if (!props.evidence) return;
  emit("open-pdf", {
    cntsId: props.evidence.cnts_id,
    title: title.value,
    page: current.value ? pdfPage(current.value) : undefined,
  });
}

onBeforeUnmount(() => {
  cancelHide();
  document.removeEventListener("click", onDocumentClick);
});
</script>
```

- [ ] **Step 7: 보고서 작성**

```vue
<!-- frontend/components/research/ReportView.vue -->
<template>
  <article class="rs-card rs-report">
    <header class="rs-report__head">
      <div>
        <h2 class="rs-report__question">{{ report.question }}</h2>
        <p class="rs-report__meta">
          <span v-if="range">{{ range }}</span>
          <span v-if="generated">{{ generated }} 생성</span>
        </p>
      </div>
      <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('copy-link')">링크 복사</button>
    </header>

    <p class="rs-report__intro">{{ intro }}</p>

    <section v-for="(sec, si) in report.sections" :key="si" class="rs-section">
      <h3 class="rs-section__heading">{{ si + 1 }}. {{ sec.heading }}</h3>
      <p v-if="sec.intro" class="rs-section__intro">
        <template v-for="(part, pi) in splitCitations(sec.intro)" :key="pi">
          <template v-if="part.type === 'text'">{{ part.text }}</template>
          <CitationChip
            v-else
            :eid="part.eid"
            :evidence="report.evidence[part.eid]"
            :chunks="citeChunks(sec, report.evidence[part.eid], part.eid)"
            @open-pdf="$emit('open-pdf', $event)"
          />
        </template>
      </p>
      <p v-else class="rs-muted">이 절은 도입 서술을 받지 못했습니다. 아래 논문 목록만 싣습니다.</p>

      <template v-if="sec.papers.length">
        <h4 class="rs-section__sub">대표 논문</h4>
        <ul class="rs-papers">
          <li v-for="p in sec.papers" :key="p.cnts_id" class="rs-paper">
            <span class="rs-paper__who">{{ paperByline(paperMeta(p)) }}</span>
            <span v-if="paperMeta(p)?.title" class="rs-paper__title">{{ paperMeta(p)?.title }}</span>
            <span class="rs-paper__summary">{{ p.summary || "요약을 받지 못했습니다." }}</span>
            <CitationChip
              v-for="eid in p.evidence"
              :key="eid"
              :eid="eid"
              :evidence="report.evidence[eid]"
              :chunks="citeChunks(sec, report.evidence[eid], eid)"
              @open-pdf="$emit('open-pdf', $event)"
            />
          </li>
        </ul>
      </template>

      <template v-if="sec.future.length">
        <h4 class="rs-section__sub">향후 과제</h4>
        <ul class="rs-future">
          <li v-for="(f, fi) in sec.future" :key="fi">
            <template v-for="(part, pi) in splitCitations(f.text)" :key="pi">
              <template v-if="part.type === 'text'">{{ part.text }}</template>
              <CitationChip
                v-else
                :eid="part.eid"
                :evidence="report.evidence[part.eid]"
                :chunks="citeChunks(sec, report.evidence[part.eid], part.eid)"
                @open-pdf="$emit('open-pdf', $event)"
              />
            </template>
          </li>
        </ul>
      </template>
    </section>

    <section class="rs-limits" aria-labelledby="rs-limits-title">
      <h3 id="rs-limits-title" class="rs-limits__title">이 보고서의 한계</h3>
      <ul v-if="report.limitations.length">
        <li v-for="(line, li) in report.limitations" :key="li">{{ line }}</li>
      </ul>
      <p v-else class="rs-muted">자동 점검에서 보고할 한계가 발견되지 않았습니다.</p>
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { EvidenceMeta, OpenPdfPayload, ReportPaper, ResearchReport } from "~/types/research";
import { citeChunks, splitCitations } from "~/utils/citations";
import { paperByline, rangeLabel, reportIntro } from "~/utils/researchReport";
import CitationChip from "./CitationChip.vue";

const props = defineProps<{ report: ResearchReport; generatedAt: string | null }>();
defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; "copy-link": [] }>();

const range = computed(() => rangeLabel(props.report.range));
const intro = computed(() => reportIntro(props.report));
const generated = computed(() => {
  if (!props.generatedAt) return "";
  const d = new Date(props.generatedAt);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
});

function paperMeta(p: ReportPaper): EvidenceMeta | undefined {
  return props.report.evidence[p.evidence[0] ?? ""]?.meta;
}
</script>
```

- [ ] **Step 8: 페이지에 끼우기**

1) import 교체(PDF 뷰어·보고서·`apiHeaders`·`apiUrl`·타입)

찾을 코드:

```ts
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import PlanCard from "~/components/research/PlanCard.vue";
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
```

바꿀 코드:

```ts
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import PdfViewer from "~/components/PdfViewer.vue";
import PlanCard from "~/components/research/PlanCard.vue";
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ReportView from "~/components/research/ReportView.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
import { apiHeaders, apiUrl } from "~/composables/useApi";
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
import type { OpenPdfPayload } from "~/types/research";
```

2) PDF 확인용 주소 준비(setup 중에 한 번)

찾을 코드:

```ts
const { startResearch } = useResearchStarter();
```

바꿀 코드:

```ts
const { startResearch } = useResearchStarter();
const pdfBase = apiUrl("/books");
```

3) 보고서 자리표시 → `ReportView`

찾을 코드:

```vue
              <div class="rs-card">
                <p class="rs-card__title">보고서</p>
                <p class="rs-muted">절 {{ view.report.sections.length }}개</p>
              </div>
```

바꿀 코드:

```vue
              <ReportView :report="view.report" :generated-at="view.finishedAt" @open-pdf="openPdf" @copy-link="copyLink" />
```

4) PDF 뷰어 템플릿 추가

찾을 코드:

```vue
    <Teleport to="body">
```

바꿀 코드:

```vue
    <PdfViewer v-if="pdf" :cnts-id="pdf.cntsId" :title="pdf.title" :page="pdf.page" @close="pdf = null" />

    <Teleport to="body">
```

5) 원문 보기 함수 추가(토스트 절 바로 앞)

찾을 코드:

```ts
// ── 토스트 ────────────────────────────────────────────────
```

바꿀 코드:

```ts
// ── 원문 보기 ─────────────────────────────────────────────
const pdf = ref<OpenPdfPayload | null>(null);

async function pdfExists(cntsId: string): Promise<boolean> {
  const ctrl = new AbortController();
  try {
    const res = await fetch(`${pdfBase}/${encodeURIComponent(cntsId)}/pdf`, { headers: apiHeaders(), signal: ctrl.signal });
    return res.ok;
  } catch {
    // 확인 요청 자체가 실패하면 판단하지 않고 뷰어가 직접 보여 주게 둔다
    return true;
  } finally {
    // 본문은 필요 없다 — 뷰어가 다시 받는다. 끊지 않으면 PDF 전체를 두 번 내려받는다
    ctrl.abort();
  }
}

async function openPdf(target: OpenPdfPayload): Promise<void> {
  if (await pdfExists(target.cntsId)) pdf.value = target;
  else showToast("원문 파일이 없습니다");
}

// ── 토스트 ────────────────────────────────────────────────
```


- [ ] **Step 9: 컴파일 확인**

```bash
cd frontend
npx nuxi typecheck 2>&1 | grep "error TS" | grep -v "pages/search-classic.vue"
npm run build 2>&1 | tail -1
grep -c "v-html" components/research/*.vue "pages/research/[id].vue"
```
기대: 첫 명령 출력 없음, 둘째 `└  ✨ Build complete!`, 셋째는 파일마다 `:0`(spec D9).

- [ ] **Step 10: 커밋**

```bash
git add frontend/utils/researchReport.ts frontend/tests/unit/researchReport.test.ts frontend/components/research/CitationChip.vue frontend/components/research/ReportView.vue frontend/components/PdfViewer.vue "frontend/pages/research/[id].vue"
git commit -m "[Feat] round04b — 딥리서치 보고서·인용칩 팝오버·원문 쪽 열기"
```

---

### Task 35: 입력창 `+` 메뉴 (`SearchPlusMenu.vue`)와 논문 입력창 세 곳

- 원형 `+` → 메뉴(`SEARCH_MODES` 데이터 — Task 27) → **딥리서치** → 입력창 안 `딥리서치 ×` 칩, 플레이스홀더 "연구 질문을 입력하세요". 입력이 `/deep-research ` 로 시작하면 자동으로 칩이 된다(spec §6-1).
- 엔터(또는 전송 버튼) → `POST /api/research` → `upsertResearch` → `navigateTo('/research/<id>')`. 실패하면 입력창 아래에 오류를 보이고 입력을 지우지 않는다. 한글 조합 중 엔터(`isComposing`)는 보내지 않는다. Shift+엔터(textarea)는 줄바꿈으로 둔다.
- **삽입을 한 줄로 끝내는 방법(spec D2)**: 컴포넌트가 부모 상자(`.skx-search__box` / `.skx-rsearch`)에 **캡처 단계** 리스너를 달아, 딥리서치 모드일 때만 엔터·전송 클릭을 가로채고 전파를 끊는다. 캡처 단계에서 `stopPropagation` 하면 입력창·전송 버튼에 달린 페이지의 `handleSearch` 까지 가지 않는다 — 페이지 스크립트(`handleSearch`)는 한 줄도 고치지 않는다. 딥리서치 모드가 아니면 아무것도 가로채지 않아 기존 논문 검색이 그대로다.
- 자동 등록 이름은 `ResearchSearchPlusMenu`(Nuxt 가 하위 폴더 이름을 접두로 붙인다) — 페이지에 import 줄을 더하지 않으려고 이 이름을 쓴다.
- 도서 입력창에는 넣지 않는다(딥리서치는 논문 전용, spec §6-1). `kind="book"` 이면 메뉴 항목이 없어 아무것도 그리지 않는다.

**Files:**
- Create: `frontend/components/research/SearchPlusMenu.vue`
- Modify: `frontend/pages/index.vue` (논문 패널 검색 상자 — 착수 시점 165–170행, Task 22 뒤에는 사이드바 props 가 줄어 약 4행 당겨진다)
- Modify: `frontend/pages/papers/index.vue` (랜딩 검색 상자 착수 시점 18–20행, 결과 검색바 49–50행 — Task 23 뒤에는 약 5행 당겨진다)

- [ ] **Step 1: 컴포넌트 작성**

```vue
<!-- frontend/components/research/SearchPlusMenu.vue -->
<template>
  <div v-if="modes.length" ref="root" class="rs-plus" :class="{ 'is-active': !!active }">
    <span class="rs-plus__anchor">
      <button
        type="button"
        class="rs-plus__btn"
        aria-haspopup="menu"
        :aria-expanded="menuOpen"
        aria-label="검색 모드 선택"
        :disabled="disabled || busy"
        @click="menuOpen = !menuOpen"
      >
        +
      </button>
      <ul v-if="menuOpen" class="rs-plus__menu" role="menu" @keydown.escape.stop="menuOpen = false">
        <li v-for="m in modes" :key="m.id" role="none">
          <button
            type="button"
            role="menuitem"
            class="rs-plus__item"
            :class="{ 'is-selected': active?.id === m.id }"
            @click="choose(m)"
          >
            <img class="rs-plus__icon" :src="m.icon" alt="" />
            <span class="rs-plus__text">
              <span class="rs-plus__label">{{ m.label }}</span>
              <span class="rs-plus__desc">{{ m.description }}</span>
            </span>
          </button>
        </li>
      </ul>
    </span>
    <span v-if="active" class="rs-plus__chip">
      {{ active.label }}
      <button type="button" class="rs-plus__chip-x" :aria-label="`${active.label} 해제`" @click="clear">×</button>
    </span>
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useResearchStarter } from "~/composables/useResearch";
import { researchErrorMessage } from "~/utils/researchErrors";
import { questionProblem } from "~/utils/researchInput";
import {
  modesFor,
  parseSlash,
  shouldAutoChip,
  type SearchInputKind,
  type SearchMode,
  type SearchModeId,
} from "~/utils/slashCommand";

const props = withDefaults(
  defineProps<{ modelValue: string; kind?: SearchInputKind; disabled?: boolean }>(),
  { kind: "paper", disabled: false },
);
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const { startResearch } = useResearchStarter();
const modes = computed(() => modesFor(props.kind));
const root = ref<HTMLElement | null>(null);
const menuOpen = ref(false);
const active = ref<SearchMode | null>(null);
const busy = ref(false);
const error = ref("");

let host: HTMLElement | null = null;
let field: HTMLTextAreaElement | HTMLInputElement | null = null;
let basePlaceholder = "";

function modeFor(id: SearchModeId | null): SearchMode | undefined {
  return modes.value.find((m) => m.id === id);
}

function currentText(): string {
  return field?.value ?? props.modelValue;
}

function activate(mode: SearchMode): void {
  active.value = mode;
  error.value = "";
  if (field) field.placeholder = mode.placeholder;
}

function choose(mode: SearchMode): void {
  menuOpen.value = false;
  activate(mode);
  const slash = parseSlash(props.modelValue);
  if (slash.mode) emit("update:modelValue", slash.text);
  field?.focus();
}

function clear(): void {
  active.value = null;
  error.value = "";
  if (field) field.placeholder = basePlaceholder;
  field?.focus();
}

watch(
  () => props.modelValue,
  (value) => {
    if (error.value && !busy.value) error.value = "";
    if (active.value || !shouldAutoChip(value)) return;
    const slash = parseSlash(value);
    const mode = modeFor(slash.mode);
    if (!mode) return;
    activate(mode);
    emit("update:modelValue", slash.text);
  },
);

function researchWanted(): boolean {
  return !!active.value || !!modeFor(parseSlash(currentText()).mode);
}

async function submit(): Promise<void> {
  if (busy.value || props.disabled) return;
  const slash = parseSlash(currentText());
  const mode = active.value ?? modeFor(slash.mode);
  if (!mode) return;
  if (!active.value) activate(mode);
  const question = (slash.mode ? slash.text : currentText()).trim();
  if (slash.mode) emit("update:modelValue", slash.text);
  const problem = questionProblem(question);
  if (problem) {
    error.value = problem;
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const jobId = await startResearch(question);
    await navigateTo(`/research/${jobId}`);
  } catch (e) {
    // 입력은 지우지 않는다 — 사용자가 고쳐서 다시 보낼 수 있어야 한다
    error.value = researchErrorMessage(e, "딥리서치를 시작하지 못했습니다");
  } finally {
    busy.value = false;
  }
}

// 페이지의 엔터 처리를 고치지 않고 한 줄 삽입으로 붙이려고(입력창은 화면 고도화와 가장
// 겹치는 곳이다) 부모 상자에서 캡처 단계로 엔터·전송 클릭을 가로챈다. 캡처 단계에서
// 전파를 끊으면 입력창·전송 버튼에 달린 페이지의 검색 핸들러까지 가지 않는다.
function onHostKeydown(e: KeyboardEvent): void {
  if (e.key !== "Enter" || e.target !== field || !researchWanted()) return;
  if (e.shiftKey && field instanceof HTMLTextAreaElement) return;
  e.preventDefault();
  e.stopPropagation();
  // 한글 조합 중의 엔터는 글자 확정용이다 — 여기서 보내면 마지막 글자가 빠지거나 두 번 간다
  if (e.isComposing) return;
  void submit();
}

function onHostClick(e: MouseEvent): void {
  const target = e.target instanceof Element ? e.target : null;
  if (!target?.closest(".skx-send") || !researchWanted()) return;
  e.preventDefault();
  e.stopPropagation();
  void submit();
}

function onDocumentClick(e: MouseEvent): void {
  if (menuOpen.value && root.value && e.target instanceof Node && !root.value.contains(e.target)) {
    menuOpen.value = false;
  }
}

onMounted(() => {
  host = root.value?.parentElement ?? null;
  field = host?.querySelector<HTMLTextAreaElement | HTMLInputElement>("textarea, input[type='text'], input:not([type])") ?? null;
  basePlaceholder = field?.placeholder ?? "";
  host?.addEventListener("keydown", onHostKeydown, true);
  host?.addEventListener("click", onHostClick, true);
  document.addEventListener("click", onDocumentClick);
});

onBeforeUnmount(() => {
  host?.removeEventListener("keydown", onHostKeydown, true);
  host?.removeEventListener("click", onHostClick, true);
  document.removeEventListener("click", onDocumentClick);
});
</script>
```

- [ ] **Step 2: 메인 논문 탭 입력창에 한 줄 삽입 (`pages/index.vue`)**

`skx-search__box` 가 도서 패널(79행)과 논문 패널(168행)에 둘 다 있다 — **논문 패널**에만 넣는다. 현재 코드(165–170행):

```vue
        <!-- 논문 패널 -->
        <div class="skx-panel" :hidden="mode !== 'paper'">
          <div class="skx-search">
            <div class="skx-search__box">
              <label class="skx-search__field">
                <span class="skx-sr-only">논문 검색어</span>
```

교체 코드:

```vue
        <!-- 논문 패널 -->
        <div class="skx-panel" :hidden="mode !== 'paper'">
          <div class="skx-search">
            <div class="skx-search__box">
              <ResearchSearchPlusMenu v-model="currentQuery" kind="paper" :disabled="loading" />
              <label class="skx-search__field">
                <span class="skx-sr-only">논문 검색어</span>
```

- [ ] **Step 3: `/papers` 랜딩·결과 검색바에 한 줄씩 삽입 (`pages/papers/index.vue`)**

랜딩 — 현재 코드(17–21행):

```vue
        <h1 class="skx-hero">논문 의미 기반 검색</h1>
        <div class="skx-search">
          <div class="skx-search__box">
            <label class="skx-search__field">
              <span class="skx-sr-only">논문 검색어</span>
```

교체 코드:

```vue
        <h1 class="skx-hero">논문 의미 기반 검색</h1>
        <div class="skx-search">
          <div class="skx-search__box">
            <ResearchSearchPlusMenu v-model="currentQuery" kind="paper" :disabled="loading" />
            <label class="skx-search__field">
              <span class="skx-sr-only">논문 검색어</span>
```

결과 검색바 — 현재 코드(48–53행):

```vue
      <!-- 검색바 -->
      <div class="skx-rsearch">
        <input
          type="text"
          class="skx-rsearch__input"
          v-model="currentQuery"
```

교체 코드:

```vue
      <!-- 검색바 -->
      <div class="skx-rsearch">
        <ResearchSearchPlusMenu v-model="currentQuery" kind="paper" />
        <input
          type="text"
          class="skx-rsearch__input"
          v-model="currentQuery"
```

Task 22·23 이 두 페이지를 먼저 고쳐 줄 번호가 달라졌다 — 위 앵커 문자열로 찾는다. 앵커 자체(`skx-search__box`·`skx-rsearch`·`currentQuery`·`loading`)는 Task 22·23 이 바꾸지 않는다.

- [ ] **Step 4: 컴파일 확인**

```bash
cd frontend
npx nuxi typecheck 2>&1 | grep "error TS" | grep -v "pages/search-classic.vue"
npm run build 2>&1 | tail -1
grep -c "ResearchSearchPlusMenu" .nuxt/components.d.ts
```
기대: 첫 명령 출력 없음, 둘째 `└  ✨ Build complete!`, 셋째 1 이상(자동 등록 이름 확인).

- [ ] **Step 5: 이 영역 테스트 전체 실행**

```bash
cd frontend && npx vitest run tests/unit/citations.test.ts tests/unit/slashCommand.test.ts tests/unit/researchEvents.test.ts tests/unit/researchErrors.test.ts tests/unit/researchInput.test.ts tests/unit/researchLayout.test.ts tests/unit/researchReport.test.ts
```
기대: `Test Files  7 passed (7)`, `Tests  66 passed (66)`.

```bash
cd frontend && npm test
```
기대: 기록 영역 테스트까지 `Test Files  14 passed (14)`, `Tests  158 passed (158)`.

- [ ] **Step 6: 화면 확인 (수동 — spec §9)**

```bash
cd frontend
NUXT_DEV_API_TARGET=http://<서버>:92/api npm run dev
```
딥리서치는 축소 파라미터로 몇 건만 돌린다(시연 파라미터는 `POST /api/research` 의 `params` — 화면은 기본값으로 보내므로, 축소 실행은 `curl` 로 잡을 만들고 `/research/<id>` 를 연다). 확인 목록:
1. `/papers` 랜딩 `+` → 딥리서치 칩 → 플레이스홀더 변경. `×` 로 해제하면 원래 플레이스홀더.
2. `/deep-research 질문` 입력 → 자동 칩, 입력창에는 "질문"만 남음.
3. 엔터 → `/research/<id>` 로 이동, 사이드바 딥리서치 탭에 항목(C1 이후).
4. 승인 대기: 하위질문 고치기·삭제·추가(상한에서 추가 버튼 비활성)·빈 항목이면 승인 비활성 → 승인하고 시작.
5. 탐색 중: 카운터가 오르고, 재검색이 일어나면 강조 카드가 뜬다. 새로고침해도 회차·강조 카드가 복원된다.
6. 완료: 보고서·서론 한 줄·한계 섹션. 칩에 마우스/Tab 초점 → 팝오버, 대목 1/2, 쪽 정보, [원문 보기](해당 쪽)·PDF 없는 논문은 "원문 파일이 없습니다".
7. 1200px 미만으로 줄이면 B 로 바뀌고, 넓은 화면에서 고른 보기가 새로고침 뒤에도 유지된다.
8. 뒤로가기로 `/papers` 에 돌아와도 딥리서치가 다시 만들어지지 않는다(잡 생성은 엔터 때만).
9. 네트워크 탭: `POST /api/research` 에 `x-session-id` 헤더, 스트림은 종료 이벤트 뒤 닫힘(재연결 반복 없음).
10. 존재하지 않는 id(`/research/00000000-0000-4000-8000-000000000000`) → "찾을 수 없는 연구입니다".

- [ ] **Step 7: 커밋**

```bash
git add frontend/components/research/SearchPlusMenu.vue frontend/pages/index.vue frontend/pages/papers/index.vue
git commit -m "[Feat] round04b — 입력창 + 메뉴(딥리서치 칩·슬래시 자동 칩)를 논문 입력창 세 곳에 삽입"
```

---

#### 영역 C2 참고 메모

- **실행 순서**: Task 13(Vitest) → Task 26~Task 28(다른 영역 없이 가능) → Task 15·20(`useApi`·`useHistory`) → Task 29~Task 35. 영역 B(Task 5~12)가 없어도 컴파일·동작한다.
- **보강 전 서버 허용**: `search.round`·`new_papers` 없음(순서대로 회차를 매김), snapshot 에 `result`·`job` 없음(이미 아는 결과 유지), synthesize 결과 `sections` 가 숫자(절 수로 완료 계산), search 결과에 `rounds` 없음(`report.trail` → `queries` 순으로 대체). GET 응답에 `params`·시각이 없으면 상한은 6 으로 두고 생성 시각은 싣지 않는다.
- **GET `/api/research/{id}` 의 `params`** 는 `merge_params` 를 거친 전체 사전이라 `max_subquestions` 가 늘 있다(`create_research` 가 병합본을 저장). `created_at` 등은 ISO 문자열.
- **쪽수는 0부터**(`app/services/ingestion/extractor.py` 의 "1-based → 0-based", `indexer.py` 의 `or 0`) — 화면·PDF 는 `+1`. 기존 `BookChat.vue` 는 원시값을 `p.N` 으로 보여 한 쪽 어긋나 있다(범위 밖, 불일치로 기록).
- **`PdfViewer.vue`** 는 `apiBase` 를 무시하고 `/api/books/...` 를 하드코딩한 채로 둔다(이번 범위는 `page` prop 만).
- **기존 페이지 템플릿 앵커**(`pages/index.vue` 논문 패널의 `skx-search__box`, `pages/papers/index.vue` 의 랜딩 `skx-search__box`·결과 `skx-rsearch`)와 `currentQuery`·`loading` 변수 이름은 C1 이 바꾸지 않는다.
- **`app.vue`** 의 `<NuxtPage />` 에 page-key 가 없어 `/research/a` → `/research/b` 이동 때 같은 페이지 인스턴스를 쓴다 — composable 이 잡 id 를 watch 해 다시 읽는다.
- **아이콘** `/img/ico-ai-related.svg`(메뉴)·`/img/ico-spinner.svg`(대기) 가 `frontend/public/img/` 에 있다(확인함).
- **운영 게이트웨이는 http** — 보안 컨텍스트가 아니라 clipboard API 가 없을 수 있어 링크 복사는 `prompt` 로 대체한다.
- **배치 기본값**(A·1200px·전환 버튼 표시·진행 패널 폭 17rem)은 기획자 결정 전 개발 기본값(spec §7-3) — `utils/researchLayout.ts` 상수와 `research.css` 의 `--rs-side-width` 만 바꾸면 된다.
- **`research.css` 의 `:has()`**(결과 검색바의 오류 문구 위치 기준)는 Chrome 105+·Firefox 121+ 에서 동작한다. 지원하지 않는 브라우저에서는 오류 문구 위치만 어긋난다.
- **검증 경계**: 질문 2~500자, 하위질문 2~300자·상한·중복(공백 정규화 + 소문자)은 `app/api/research.py` 의 `ResearchCreate`·`PlanItem`·`_validated_plan`·`planner.query_key` 와 같다고 본다. 서버가 바뀌면 `utils/researchInput.ts` 도 함께 바꾼다.

---

## 단계 4 — 통합 검증·배포·문서

### Task 36: 통합 검증

네 영역을 모두 넣은 상태에서 자동 검증을 한 번에 돌린다. 여기서 실패가 나오면 그 파일을 만든 태스크로 돌아가 고치고 `[Fix] round04b — …` 로 커밋한 뒤 이 태스크를 처음부터 다시 돌린다.

**Files:**
- 없음(검증만)

- [ ] **Step 1: 백엔드 전체 회귀**

Run: `python -m pytest app/tests -q --ignore=app/tests/test_book_chat.py --ignore=app/tests/test_build_manifest.py --ignore=app/tests/test_loaders.py`
Expected: `728 passed`(경고 2건은 기존 Pydantic class-based config 경고)

- [ ] **Step 2: 프론트 단위 테스트 전체**

Run: `cd frontend && npm test`
Expected: `Test Files  14 passed (14)` · `Tests  158 passed (158)`

- [ ] **Step 3: 타입 검사**

Run: `cd frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음. Task 25 가 `pages/search-classic.vue` 를 지워 기준선 오류(그 파일 2건)도 없다. 오류가 나오면 그 파일의 태스크로 돌아간다 — 특히 Task 21~24 는 계획 작성 때 타입검사를 돌리지 않았다. (`vue-tsc` 가 없으면 `nuxi typecheck` 가 npx 캐시에 한 번 내려받는다. `[Vue] Resolve plugin path failed: vue-router/volar/sfc-route-blocks` 경고는 무해하다.)

- [ ] **Step 4: 빌드와 자동 import 이름 충돌**

Run: `cd frontend && npm run build 2>&1 | tee /tmp/round04b-build.log | tail -1`
Expected: `└  ✨ Build complete!`

Run: `grep -i "duplicated imports" /tmp/round04b-build.log`
Expected: 출력 없음 — `utils/`·`composables/` 의 export 이름이 영역 사이에서 겹치지 않는다(겹치면 Nuxt 가 하나를 조용히 가린다).

- [ ] **Step 5: 안전·잔재·무변경 확인**

Run: `grep -rn "v-html" frontend/components/research "frontend/pages/research"`
Expected: 출력 없음(spec D9 — 모델 글은 조각과 칩으로만 그린다)

Run: `grep -rn "useSearchHistory\|getSessionId\|restoreSession\|bookHistory\|paperHistory" frontend/pages frontend/components frontend/composables`
Expected: 출력 없음

Run: `git diff --stat ae00bfd -- app/services/ingestion app/workers/tasks.py app/workers/job_runtime.py app/models/book.py app/models/search_history.py`
Expected: 출력 없음 — 적재 코드와 기존 테이블 모델은 바뀌지 않았다(spec §10)

- [ ] **Step 6: 기록**

실패 없이 끝났으면 커밋할 것이 없다. 수치(728 · 14/158)는 Task 38 에서 `00_status.md` 에 적는다.

---

### Task 37: 운영 배포와 라이브 검증

> **사용자 승인 뒤에만 한다.** 운영 서버는 동료와 공유한다. 재생성하는 컨테이너 네 개와 영향(fastapi 재시작 동안 조회가 잠시 줄 설 수 있다)을 알리고 명시적 승인을 받는다. 운영 스택(`nl-lib-*`)만 쓴다 — dev 스택은 쓰지 않는다.

순서가 중요하다: 백엔드를 먼저 올리고(기록 API·보강 이벤트), 그 서버로 프록시한 로컬 화면을 확인한 뒤(spec §9 화면), 프론트를 올린다. spec §5-3·§10 의 절차다.

**Files:**
- 없음(운영 조작). 게이트웨이 버퍼링 문제가 나올 때만 `infra/conf.d/default.conf` (Step 7 의 조건부 수정)

- [ ] **Step 1: 배포 전 확인**

서버에서 확인한다(psql 은 `docker exec -it nl-lib-postgres psql -U <DB 사용자> -d <DB 이름>`).

```sql
select version_num from alembic_version;                 -- 기대: 0005_research_jobs
select to_regclass('public.history_items');              -- 기대: 빈 값(NULL) — 아직 없다
select pid, state, xact_start, left(query, 80)
  from pg_stat_activity where state = 'idle in transaction';  -- 기대: 0행
```

```bash
docker exec nl-lib-fastapi printenv MILVUS_RECREATE_ON_MISMATCH   # 기대: false
```

`idle in transaction` 이 있으면 fastapi 재시작의 `ALTER TABLE library_catalog` 가 그 뒤에 줄 서고 모든 조회가 멈춘다(함정 18번) — 끝날 때까지 기다린다. 이 배포는 적재 워커를 재생성하지 않으므로 적재를 멈출 필요는 없다.

- [ ] **Step 2: 백엔드 이미지 빌드·푸시(로컬)**

```bash
NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
```

기본 태그는 `:dev` 다 — 태그를 덮어쓰지 않으면 운영 컨테이너에 새 코드가 들어가지 않는다(함정 3번).

- [ ] **Step 3: 서버에서 이미지 받기와 내용 확인**

```bash
docker pull landsoftdocker/nl-lib-fastapi:latest
docker run --rm --entrypoint ls landsoftdocker/nl-lib-fastapi:latest /app/api/history.py
docker run --rm --entrypoint grep landsoftdocker/nl-lib-fastapi:latest -c "_save_progress" /app/workers/research_tasks.py
```

Expected: 첫 명령 끝에 새 digest, 둘째 `/app/api/history.py`, 셋째 1 이상. Portainer 에 pull 을 맡기지 않는다(함정 12번).

- [ ] **Step 4: 컨테이너별 Recreate**

Portainer 에서 `nl-lib-fastapi` · `nl-lib-celery-research` · `nl-lib-celery-research-plan` 을 **하나씩** Recreate 한다("Re-pull image" 토글은 끈다). **스택 업데이트는 하지 않는다** — 같은 `:latest` 를 쓰는 적재 워커 다섯이 함께 재생성돼 도는 적재 아이템이 끊긴다(함정 16번).

```bash
docker ps --format '{{.Names}}\t{{.CreatedAt}}' | grep nl-lib-
docker logs nl-lib-fastapi --tail 20
```

Expected: 세 컨테이너만 방금 시각이고, fastapi 로그 끝에 `Application startup complete.`. Recreate 시각을 적어 둔다(Task 38).

- [ ] **Step 5: 스키마 확인과 스탬프**

lifespan 의 `create_all` 이 `history_items` 를 이미 만들었다. 그래서 `upgrade` 가 아니라 `stamp` 다 — `upgrade` 는 `DuplicateTable` 로 죽는다(함정 14번).

```sql
\d history_items
```

Expected: 컬럼 12개(`id` uuid PK · `session_id` uuid not null · `user_id` · `kind` · `title` · `params` jsonb not null default `'{}'` · `snapshot` · `ai` · `ref_id` · `created_at`·`updated_at` not null default now() · `deleted_at`)와 인덱스 `ix_history_items_session_kind_created ... (session_id, kind, created_at DESC) WHERE deleted_at IS NULL`.

```bash
docker exec nl-lib-fastapi alembic stamp 0006_history_items
```

```sql
select version_num from alembic_version;   -- 기대: 0006_history_items
```

- [ ] **Step 6: 기록 API 연기 확인(게이트웨이 경유)**

```bash
SID=$(python -c "import uuid; print(uuid.uuid4())")
curl -s -H "x-session-id: $SID" "http://<서버>:92/api/history?kind=book"
curl -s -o /dev/null -w "%{http_code}\n" "http://<서버>:92/api/history"
```

Expected: 첫 명령 `{"items":[],"next_cursor":null}`, 둘째 `400`.

- [ ] **Step 7: 게이트웨이 경유 SSE(round04a 에서 미검증)**

축소 파라미터로 잡을 만든다.

```bash
curl -s -X POST "http://<서버>:92/api/research" -H 'Content-Type: application/json' -H "x-session-id: $SID" \
  -d '{"question":"공공도서관 서비스 품질 평가는 어떻게 연구되어 왔는가","params":{"max_subquestions":2,"max_recheck":1,"per_subq_top_k":8}}'
curl -N "http://<서버>:92/api/research/<job_id>/stream"
```

Expected: 첫 줄 `data: {"kind": "snapshot", ... "job": {"status": ...` 가 곧바로 오고, 계획이 끝나면 `{"kind": "status", "status": "awaiting_approval", "stage": "planned"}` 가 **몰아 오지 않고 바로** 도착한다. 다른 터미널에서 승인한다.

```bash
curl -s -X POST "http://<서버>:92/api/research/<job_id>/approve" -H 'Content-Type: application/json' -d '{}'
```

Expected: 스트림에 `status`(approved → running/planned) → `step`(running) → `search`(`round`·`new_papers`) → `counters` → `critique`(`next_query`·`will_recheck`) → `step`(running + `result.rounds`) … → `status`(running/explored) → `synth` → `step`(done) → `done` 순서로 오고 스트림이 닫힌다. 끝난 뒤 `curl -s -H "x-session-id: $SID" "http://<서버>:92/api/history/<job_id>"` 는 아직 404 다(기록은 화면이 PUT 한다 — Step 8 에서 확인).

이벤트가 몰아서 오거나 끝나야 한꺼번에 오면 게이트웨이가 버퍼링하는 것이다. 응답 헤더 `X-Accel-Buffering: no` 는 이미 싣고 있으니, 그래도 막히면 `infra/conf.d/default.conf` 의 `location /api/` 에 한 줄을 더한다(spec §12). 교체 전:

```nginx
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
```

교체 후:

```nginx
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        # SSE(딥리서치 진행)가 버퍼에 묶이면 화면이 끝날 때까지 아무것도 받지 못한다
        proxy_buffering    off;
    }
```

서버의 `/data/nl-lib/nginx/conf.d/default.conf` 에 같은 줄을 넣고 `docker exec nl-lib-gateway nginx -s reload` 한 뒤 이 Step 을 다시 한다. 저장소 파일은 `git commit -m "[Fix] round04b — 게이트웨이 /api 응답 버퍼링 끔(SSE)"`.

- [ ] **Step 8: 로컬 화면 확인(운영 서버로 프록시)**

```bash
cd frontend
NUXT_DEV_API_TARGET=http://<서버>:92/api npm run dev
```

Task 21~24·35 의 수동 확인 목록을 이 환경에서 한 번씩 본다. 빠뜨리기 쉬운 것:
1. v1 기록이 있던 브라우저의 첫 로드 → `skx_search_history_backup_v1`·`skx_history_v1_map` 이 생기고 `skx_search_history` 는 없다. 사이드바에 옛 기록이 보이고 옛 주소 `/?restore=<13자리>` 가 열린다.
2. 도서·논문 검색 → 주소 `?q&h`, 스트림 중 다른 기록 클릭(H1 — 요약이 섞이지 않음), 상세 → 뒤로가기·새로고침(H2 — 재검색 없음), 엔터 연타(M5).
3. 논문 입력창 `+` → 딥리서치 → 엔터 → `/research/<id>`, 사이드바 딥리서치 탭에 "진행 중" 배지.
4. 승인 → 탐색 중 **새로고침** → 회차 타임라인·자기점검 강조 카드·카운터가 바로 복원된다(Task 12).
5. 완료 → 보고서·서론 한 줄·한계 섹션·인용칩 팝오버·[원문 보기](해당 쪽)·PDF 없는 논문은 "원문 파일이 없습니다". 사이드바 배지가 30초를 기다리지 않고 "완료"로 바뀐다(Task 29).
6. 항목 삭제·탭 전체 삭제(확인 창)·빈 상태 문구·브라우저 탭 두 개 동기화.
7. Network 탭: `/api` 요청 헤더에 `x-session-id`(EventSource·PDF iframe 은 헤더를 달 수 없어 예외), 스트림은 종료 이벤트 뒤 닫혀 재연결을 반복하지 않는다.

- [ ] **Step 9: 프론트 이미지 배포**

```bash
NL_LIB_NUXT_IMAGE=landsoftdocker/nl-lib-nuxt:latest bash scripts/build_dev_images.sh nuxt
```

서버에서 `docker pull landsoftdocker/nl-lib-nuxt:latest` 뒤 Portainer 에서 `nl-lib-nuxt` 만 Recreate 한다("Re-pull image" 끔).

- [ ] **Step 10: 운영 화면 전 과정 1회**

`http://<서버>:92/` 에서 Step 8 의 3~5 를 한 번 한다(spec §9 운영). 잡 id·걸린 시간·재검색 여부를 적어 둔다(Task 38).

---

### Task 38: 문서 갱신

**Files:**
- Modify: `docs/roadmap/00_status.md` (3행 "최종 갱신", "## 현재 상태" 의 round04a 항목 뒤, "## 다음 할 일" 의 round04b 항목, "## 라운드 이력" 표 끝)
- Modify: `docs/superpowers/plans/2026-09-26-round04b-deep-research-frontend.md` (이 문서 — 끝낸 Step 체크)

- [ ] **Step 1: "최종 갱신" 줄**

교체 전:
```markdown
최종 갱신: 2026-09-23 (round04a 종료 — 딥리서치 백엔드, dev→main 머지·push 완료)
```
교체 후(날짜는 이 커밋을 만드는 날):
```markdown
최종 갱신: 2026-MM-DD (round04b 구현 — 딥리서치 화면·기록 세션, 리뷰·머지 대기)
```

- [ ] **Step 2: "현재 상태" 에 round04b 항목**

round04a 항목(`- **round04a 종료** — …`) 바로 뒤에 한 줄을 더한다. 괄호 안 값은 Task 36·37 에서 적어 둔 실측으로 채운다(Task 37 을 아직 하지 않았으면 배포 문장을 "운영 배포 전"으로 쓴다).

```markdown
- **round04b 구현** — 딥리서치 화면(`+` 메뉴·`/deep-research` 진입, `/research/<job_id>` 계획 승인·진행 패널·보고서·인용칩, A/B 배치)과 기록 세션(새 테이블 `history_items` + `/api/history`, 브라우저 ID = `x-session-id`, 브라우저 캐시·outbox, URL `?h=` 복원, v1 기록 이전·백업 보존). 딥리서치 백엔드는 `status`·`step`·`counters`·`synth` 이벤트와 회차 이력·절 진행 저장, 진행 중 단계 결과 갱신을 더했다(DB 변경은 새 테이블 하나). 테스트 백엔드 728 passed · 프론트 Vitest 158. 운영 배포(재생성: fastapi·celery-research·celery-research-plan·nuxt, 시각), `alembic_version` = `0006_history_items`, 게이트웨이 경유 SSE 확인(잡 id). 계획: `docs/superpowers/plans/2026-09-26-round04b-deep-research-frontend.md`.
```

- [ ] **Step 3: "다음 할 일" 의 round04b 항목 교체**

교체 전:
```markdown
- **round04b** — 딥리서치 프론트(슬래시 진입·계획 승인·진행 패널·보고서·인용칩·재시도 버튼). 착수 전에 백엔드 보강 목록(SSE 단계 전이 중계·진행 카운터·자기점검 강조 데이터·잡 목록 API)을 보강할지 화면을 맞출지 정한다 — 완료노트 §8.
```
교체 후:
```markdown
- **round04b 마무리** — 머지 전 리뷰(`.claude/agents/code-reviewer.md`) → 완료노트 `round04b-완료노트.md`·교본 `docs/guides/round04b/` → `dev` 머지(사용자 승인) → `round-finish`. 화면 기획자의 결정(spec §7-3 — 기본 보기·전환 버튼·자동 전환 폭·패널 폭·강조 정도)이 나오면 `utils/researchLayout.ts` 상수와 `assets/css/research.css`·`components/research/*` 만 갈아입힌다. Figma 와이어프레임(spec §8)은 코드와 별도로 진행한다.
```

- [ ] **Step 4: "라운드 이력" 표에 행 추가**

표 끝(`| round04a | … |` 행) 뒤에:
```markdown
| round04b | 딥리서치 화면·기록 세션 — [spec](../superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md) · [계획](../superpowers/plans/2026-09-26-round04b-deep-research-frontend.md) | 구현 완료, 리뷰·머지 대기 |
```

- [ ] **Step 5: 계획 체크박스**

이 문서에서 끝낸 Step 을 `- [ ]` → `- [x]` 로 바꾼다. 구현하면서 계획과 달라진 것이 있으면 그 Task 머리에 `> **구현 시 변경:** …` 한 줄과 커밋 해시를 단다(round04a 계획의 관례).

- [ ] **Step 6: 커밋**

```bash
git add docs/roadmap/00_status.md docs/superpowers/plans/2026-09-26-round04b-deep-research-frontend.md
git commit -m "[Docs] round04b — 00_status 갱신·계획 체크"
```

---

## 이 계획에서 다루지 않는 것

- spec §11 범위 밖 전부 — 로그인·사용자 계정(`user_id` 는 자리만), 채팅 대화 기록의 서버 저장(`kind` 하나를 더하면 되도록 구조만), 기존 `search_history` 정리와 `GET /api/books/history/{session_id}` 폐기, 도서 입력창의 `+`·딥리서치 외 `+` 메뉴 항목, PDF 내보내기·인용 그래프·AI 다이어그램, `pages/index.vue` 의 죽은 코드, `app/api/admin.py` Milvus expression injection.
- Figma 와이어프레임(spec §8) — 코드와 무관하게 나란히 진행한다.
- 화면 기획자 결정(spec §7-3) — 개발 기본값(A 배치 · 1200px · 전환 버튼 표시 · 진행 패널 17rem · 강조 펄스 2회)으로 두었다.
- 라운드 완료노트·교본 — 라운드 종료 절차에서 따로 쓴다.
- 딥리서치 잡 목록 API — 사이드바 기록(`history_items`)이 그 역할을 한다.
- `components/SearchInput.vue` — `search-classic.vue` 삭제 뒤 호출부가 0 이지만 spec §4-9 삭제 목록에 없어 남긴다(다음 정리 후보).
- 기존 `BookChat.vue` 의 쪽수 표시(0부터 센 원시값을 `p.N` 으로 보여 한 쪽 어긋남) — 불일치로만 기록한다.
- 사이드바 "더 보기"(`next_cursor` UI) — 종류마다 최근 30건만 읽는다.

## 알려진 미확정

- 운영 게이트웨이 주소(`<서버>:92` — Task 30·37), 대회 일자, Figma `paradeigma` 팀 계정 공유 여부, PDF 유무(`has_pdf`)를 보고서에 미리 실을지, 하위질문별 근거 예산 — spec §13.
- 재시도가 탐색부터 다시 도는 잡(`stage=planned`)은 새 첫 회차가 끝나기 전까지 스냅샷 카운터가 이전 실행의 마지막 저장값일 수 있다(Task 12 의 `_live_counters` 는 seq 가 가장 큰 저장값을 쓴다). 첫 `counters` 이벤트가 곧 덮는다.
- 10분 중복 병합은 서버 `updated_at` 과 브라우저 시계를 비교한다 — 두 시계가 10분 넘게 어긋나면 병합만 안 될 뿐 오동작은 없다.
- `legacy_history_id` 는 v1 id 만으로 만든다 — 서로 다른 브라우저가 같은 밀리초에 만든 v1 기록이면 나중에 이전하는 쪽이 건너뛰어진다(남의 행을 덮지 않는다, 원본은 그 브라우저의 백업 키에 남는다).
