# 딥리서치 품질 보완 구현 계획 (round04c §11)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 무관 제외(round04c B)로 결과가 줄어 보이지 않게 한다(spec §11). 세 가지를 한다.
- 걸러낸 논문을 버리지 않고 보인다. 회차 기록·`critique` 이벤트·보고서 `trail` 에 뺀 논문의 서지를 남기고, 탐색 타임라인("무관 N편 제외 ▾" 펼치기)·보고서(한계 뒤 접힌 섹션 "관련성이 낮아 제외한 논문 (N)")·내려받은 문서(부록 뒤 목록, 참고문헌 번호 없음)에 보인다.
- 카운터에 "제외"를 더한다. `research_stats.excluded` 를 counters 이벤트·단계 result·보고서 `stats` 가 같이 보고, 화면 카운터 4칸과 보고서 서론 "(무관한 N편은 걸러냈다)"가 그 값을 쓴다.
- 잡 파라미터 `exclude_off_topic`(0·1, 기본 1)으로 재배포 없이 끈다. 끈 잡은 빼지 않고 `flagged`(무관하다고 본 수)만 남기고, 화면은 "무관 의심 N편(제외 안 함)"으로 적는다.

**Architecture:**
- 백엔드는 `app/services/research/` 의 네 모듈을 고친다.
  - `runner.py`: `_exclude_off_topic` 이 뺀 논문의 서지 요약(`_paper_brief`)을 돌려주고, 회차 기록·`critique` 이벤트에 `excluded_papers` 를 싣는다. `exclude_off_topic=0` 이면 빼지 않고 `flagged` 만 센다.
  - `critic.py`: `parse_verdict(exclude_off_topic=)` — 끈 잡은 "보인 근거를 모두 무관하다면서 충분"을 부족으로 뒤집지 않는다.
  - `state.py`: 파라미터 기본값·검증 범위, `research_stats.excluded`(회차 기록의 `excluded` 합).
  - `synthesizer.py`: `trail[].excluded_papers`(`_excluded_papers`). 보고서 `stats` 는 `research_stats` 를 그대로 쓴다.
- 새 값은 모두 `research_jobs.state_snapshot`·`research_steps.result`·`report`(JSONB) 안에서만 는다. DB 스키마·워커(`research_tasks.py`)·API 코드는 바꾸지 않는다. 워커는 `subq.rounds` 를 단계 result 에 복사하고 `critique` 이벤트를 그대로 중계하며, 단계 result 의 counters 는 `research_stats` 로 만든다. API 는 잡 파라미터를 `merge_params` 로 검증·합쳐 저장한다.
- 프론트는 타입과 이벤트 합치기가 새 값을 뷰 모양(camelCase)으로 옮기고, 목록을 만드는 순수 함수(`excludedFromTrail`·`excludedFromSubqs`·`excludedPaperLine`)를 `researchReport.ts` 한 곳에 둔다. 타임라인·보고서 화면·문서가 같은 목록과 같은 한 줄 문구를 쓴다.
- 순수 로직은 pytest·Vitest 로 검증하고, 컴포넌트는 typecheck·build 로 본다.

**Tech Stack:** FastAPI · SQLAlchemy 2(async) · Celery · pytest / Nuxt 4 · Vue 3.5 · TypeScript(strict·`noUncheckedIndexedAccess`) · Vitest 3.2

**설계 근거:** `docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md`(이하 spec)의 **§11 전체**. 맥락은 같은 spec 의 §3~§7(A·B·C·G — 이미 구현됨, `git log 738bc07..b84ce41`)과 round04b spec `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` 의 §6(진행 패널)·§7-4(인터랙티브함 최우선)·§14(문서 부록).

**실행 전 확인:**
- `docs/ops/recurring-gotchas.md` 13번: torch 를 끌어오는 모듈은 함수 안에서 import 한다(로컬 `app/.venv` 에 torch·DB·Redis 가 없다. 테스트는 대역으로 돈다).
- 운영 배포와 운영 합격 기준 비교(spec §11-4)는 이 계획 밖이다. 공유 운영 서버라 **사용자 승인 뒤** 따로 한다. spec §11-3 대로 API 가 잡 파라미터를 합쳐 저장하므로 `nl-lib-fastapi` 도 새 이미지여야 한다.
- 인덱싱 코드(`app/services/ingestion/`, `app/workers/tasks.py`, `app/workers/job_runtime.py`)와 DB 스키마는 건드리지 않는다.

**계획 조립 때 정한 것:**
- 끈 잡(`exclude_off_topic=0`)에서는 `parse_verdict` 의 "모두 빼면 insufficient" 규칙을 쓰지 않는다(Task 3). 근거를 빼지 않으니 판정이 본 근거가 그대로 남고, 뒤집으면 끈 잡만 재검색을 더 돌아 켠 잡과 나란히 볼 기준(걸린 시간·근거 수)이 흐려진다. 테스트 3개(critic 2, runner 1)로 고정한다.
- `critique` 이벤트에도 `excluded_papers`·`flagged` 를 싣고(Task 1·3), 화면의 점검 이벤트 합치기가 그 값으로 회차를 바로 채운다(Task 4). 뒤따르는 진행 저장 step 이벤트(`result.rounds`)도 같은 값을 싣지만, 워커의 `_save_progress` 는 저장에 실패하면 step 이벤트를 보내지 않는다. 그러면 새로고침 전까지 목록을 펼칠 수 없게 된다.

**계획 작성 시 검증:** 이 문서의 코드 블록을 저장소 밖 사본(`b84ce41` 작업 트리의 `app/`·`frontend/`·`scripts/` 복사본, 줄바꿈 그대로)에 Task 1→7 순서로 기계적으로 적용하고, 각 Step 의 명령을 그대로 돌렸다.
- "교체 전" 문자열 108개는 모두 그 시점의 대상 파일에서 한 곳씩만 맞았다. `replace_all` 로 적은 세 곳(Task 4 Step 1)은 적은 대로 2·2·4곳이 맞았다.
- 각 태스크의 "실패 확인"·"통과 확인" 출력과 아래 "누적 기대치"는 이 사본의 실측이다. 백엔드는 865 → 888 passed, 프론트는 21파일 / 389 → 405 passed 다. `nuxi typecheck` 는 각 태스크 뒤 오류 0 이고(Task 7 Step 2 에서 페이지를 고치기 전에는 `TS2322` 가 나는 것도 확인했다), `npm run build` 는 `└  ✨ Build complete!` 다.
- 두 초안(백엔드·화면)이 만나는 곳은 조립 때 맞췄다. 화면 초안은 "점검 이벤트는 뺀 수만 싣는다"고 봤지만 백엔드는 `critique` 이벤트에 `excluded_papers`·`flagged` 를 싣는다. 그래서 Task 4 에 `CritiqueEvent` 의 두 칸, `applyCritique` 가 그 값으로 채우는 두 줄, 그 테스트(점검 이벤트만으로 채움·옛 워커는 빈 목록)를 넣고, Task 7 의 주석 한 줄을 맞췄다. 모두 위 검증에 들어 있다.
- 확인하지 못한 것: 실제 LLM(gemma)이 돌려주는 `off_topic` 으로 운영에서 얼마나 걸러내는지, 실제 화면(키보드·스크린리더). 운영 합격 기준(spec §11-4)과 Task 7 의 화면 확인 목록이 방어선이다.

---

## 테스트 명령

**백엔드** — `app/` 에서 돈다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/<파일> -q
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```

- 로컬 `app/.venv` 에는 pytest 가 없어서 PATH 의 `python` 으로 돌린다.
- 전체 실행에서 뺀 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 실패한다(이 계획과 무관).
- 서브에이전트의 작업 디렉터리는 매번 초기화되므로 각 Step 의 명령은 절대 경로로 적었다.

**프론트** — `frontend/` 에서 돈다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/<이름>.test.ts   # 한 파일
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run                              # 전체
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"   # 출력이 없어야 한다
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1                # └  ✨ Build complete!
```

- Vitest 는 `environment: "node"` 로 `tests/unit/**/*.test.ts` 만 돈다. 컴포넌트 마운트 도구(@vue/test-utils)는 없다. 컴포넌트는 typecheck·build 로 본다.
- `[Vue] Resolve plugin path failed …` 줄은 typecheck 의 기존 소음이다. `grep "error TS"` 에 걸리지 않는다.

**누적 기대치** — 기준선은 `b84ce41` 에서 잰 값이다. 이 문서의 태스크 순서대로 적용했을 때의 값이다.

| 태스크 뒤 | `test_research_state.py` | `test_research_runner.py` | `test_research_synthesizer.py` | `test_research_critic.py` | `test_research_tasks.py` | `test_research_api.py` | 백엔드 전체 | 프론트 파일 / tests |
|---|---|---|---|---|---|---|---|---|
| 기준선 | 60 | 65 | 108 | 60 | 92 | 66 | 865 | 21 / 389 |
| Task 1 | 60 | 67 | 110 | 60 | 92 | 66 | 869 | — |
| Task 2 | 62 | 68 | 110 | 60 | 93 | 66 | 873 | — |
| Task 3 | 70 | 71 | 110 | 62 | 93 | 68 | **888** | — |
| Task 4 | — | — | — | — | — | — | — | 21 / 395 |
| Task 5 | — | — | — | — | — | — | — | 21 / 401 |
| Task 6 | — | — | — | — | — | — | — | 21 / 405 |
| Task 7 | — | — | — | — | — | — | — | **21 / 405** |

## 커밋 규칙

- 메시지는 `[Feat] round04c — …` 처럼 대괄호 접두사(`[Feat]`·`[Fix]`·`[Test]`·`[Docs]`)와 한국어로 쓴다. 태스크 하나 = 커밋 하나다. 각 Step 의 `git commit -m "…"` 을 그대로 쓴다.
- **`Co-Authored-By`·"Generated with Claude Code" 같은 트레일러를 절대 붙이지 않는다**(사용자 단독 저자).
- `git add` 는 그 태스크의 파일만 적는다. 커밋 직전에 `git status --short` 로 스테이징에 자기 파일만 있는지 본다.
- 파일 첫 줄의 경로 주석은 있는 파일이면 그대로 둔다. 코드 주석은 "왜"를 한국어로, 과하지 않게 쓰고 태스크 번호를 적지 않는다. 기존 이름을 재사용하고, 일어날 수 없는 상황을 방어하지 않는다(`docs/standards/coding-standard.md`). `v-html` 은 쓰지 않는다.
- 줄바꿈은 파일마다 다르다(`core.autocrlf=true`). 작업 트리에서 `app/` 은 CRLF 가 대부분이지만 이 계획이 고치는 파일 중 `runner.py`·`critic.py`·`synthesizer.py`·`test_research_runner.py`·`test_research_critic.py` 는 LF 다. `frontend/`·`docs/` 는 LF 다. 기존 파일은 **Edit 도구로 고쳐** 원래 줄바꿈을 유지한다.
- push·브랜치 전환·rebase·reset·stash·amend 는 하지 않는다.
- "교체 전" 코드는 착수 시점(`feat/round04c-research-quality`, `b84ce41`)의 파일에서 그대로 복사했다. 앞 태스크가 같은 파일을 고쳤으면 그 결과를 반영한 원문이다("교체 전은 Task N 을 반영한 상태다"라고 적었다). 줄 번호가 아니라 "교체 전" 문자열로 찾는다.

---

## 파일 구조

| 파일 | 책임 | Task |
|---|---|---|
| `app/services/research/runner.py` | `_paper_brief`, `_exclude_off_topic` 이 뺀 논문 서지 목록을 돌려줌, 회차 기록·`critique` 이벤트의 `excluded_papers`(1) · `exclude_off_topic` 분기와 `flagged`(3) | 1·3 |
| `app/services/research/synthesizer.py` | `_excluded_papers`, `trail[].excluded_papers` | 1 |
| `app/services/research/state.py` | `SubQuestion.rounds` 주석(1·3) · `research_stats.excluded`(2) · `DEFAULT_PARAMS`·`_PARAM_BOUNDS` 의 `exclude_off_topic`(3) | 1·2·3 |
| `app/services/research/critic.py` | `parse_verdict(exclude_off_topic=)`, `critique` 가 잡 파라미터를 넘김 | 3 |
| `app/models/research.py` | step result 모양 주석만(스키마 그대로) | 1·2·3 |
| `app/tests/test_research_runner.py` · `test_research_synthesizer.py` | 서지 기록·trail(1) · counters·stats(2) · 끈 잡(3, runner) | 1·2·3 |
| `app/tests/test_research_state.py` · `test_research_tasks.py` · `test_research_critic.py` · `test_research_api.py` | stats(2, state·tasks) · 파라미터·판정(3, state·critic·api) | 2·3 |
| `frontend/types/research.ts` | `ExcludedPaper`·`ExcludedPaperView`, 회차·`critique` 이벤트·`TrailItem`·카운터의 새 칸 | 4 |
| `frontend/utils/researchEvents.ts` | `flaggedLabel`, `toExcludedPaperView`, 회차·점검 이벤트·카운터 합치기 | 4 |
| `frontend/utils/researchReport.ts` | 서론 걸러낸 수 문구, `ExcludedGroup`·`excludedFromTrail`·`excludedFromSubqs`·`excludedPaperLine`·`EXCLUDED_TITLE`·`EXCLUDED_WHY` | 5 |
| `frontend/utils/researchDraft.ts` | `DraftReport.excluded`, 초안 stats 의 제외 수 | 5 |
| `frontend/utils/reportDocument.ts` | `ReportDocInput.excluded`, 부록 뒤 "관련성이 낮아 제외한 논문" | 6 |
| `frontend/components/research/ProgressPanel.vue` | 카운터 제외 칸, 회차 "무관 N편 제외 ▾" 펼치기, 끈 잡 표시 | 7 |
| `frontend/components/research/ReportView.vue` | 한계 뒤 접힌 섹션 "관련성이 낮아 제외한 논문 (N)" | 7 |
| `frontend/pages/research/[id].vue` | 초안 목록을 `ReportView` 에 넘김 | 7 |
| `frontend/assets/css/research.css` | 카운터 칸 폭, 펼치기 버튼·목록·접힌 섹션, reduced-motion | 7 |
| `frontend/tests/unit/researchEvents.test.ts` | 이벤트 합치기 테스트 | 4 |
| `frontend/tests/unit/researchReport.test.ts` | 서론 문구·목록 함수 테스트 | 5 |
| `frontend/tests/unit/researchDraft.test.ts` | 뷰 리터럴 새 칸(4) · 초안 목록·stats(5) | 4·5 |
| `frontend/tests/unit/reportDocument.test.ts` | 뷰·초안 리터럴 새 칸(4·5) · 문서 부록(6) | 4·5·6 |
| `docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md` | 머리 상태 줄에 §11 구현 완료 | 8 |

워커(`app/workers/research_tasks.py`)·fastapi(`app/api/research.py`)·DB 스키마·`ReportSectionBody.vue` 는 건드리지 않는다. 워커는 `subq.rounds` 를 단계 result 에 복사하고(`_search_progress`), `critique` 이벤트 payload 를 그대로 중계하며, 단계 result 의 counters 를 `research_stats` 로 만든다. 그래서 새 키가 저절로 실린다(counters 쪽은 Task 2 의 워커 테스트가 고정한다).

---

## 실행 순서

| 단계 | 태스크 | 선행·병렬 |
|---|---|---|
| 1 | Task 1 → 2 → 3 (백엔드) | 같은 파일을 차례로 고친다. Task 3 의 "교체 전"은 Task 1 을 반영한 원문이다 |
| 2 | Task 4 → 5 → 6 → 7 (화면) | 백엔드와 파일이 겹치지 않아 단계 1 과 **병렬 가능**. Task 5 는 Task 4 의 타입·`toExcludedPaperView` 를, Task 6 은 Task 5 의 `ExcludedGroup`·목록 함수를, Task 7 은 넷 모두를 쓴다 |
| 3 | Task 8 (최종 확인) | 전부 뒤 |

**병렬로 돌릴 때(같은 작업 트리)**:
- 커밋은 한 번에 하나씩 한다. 커밋 직전에 `git status --short` 로 스테이징에 자기 파일만 있는지 본다.
- "누적 기대치"의 전체 수는 태스크 번호 순서대로 적용했을 때의 값이다. 병렬 중에는 다른 태스크가 테스트만 먼저 써 둔 상태가 섞여 전체 수가 다를 수 있다. 각 태스크는 자기 테스트 파일로 확인하고, 전체 수는 Task 8 에서 본다.
- `npm run build`·`npx nuxi typecheck` 는 `.nuxt`·`.output` 을 함께 쓴다. 두 태스크가 동시에 돌리지 않는다.

---

## 공유 계약 (정본)

태스크 사이에서 주고받는 이름·모양이다. 태스크 코드는 이 목록과 일치하도록 맞췄다.

### 백엔드

- `state.py`
  - `DEFAULT_PARAMS["exclude_off_topic"] = 1`, `_PARAM_BOUNDS["exclude_off_topic"] = (int, 0, 1)` — Task 3. `merge_params` 가 bool·문자열·실수·범위 밖을 거부하고(API 는 422), 키가 없는 옛 스냅샷 params 는 기본값 1 로 되살아난다.
  - `research_stats(state)` 에 `"excluded"` = 모든 하위질문 `rounds` 의 `excluded` 합(같은 논문을 두 하위질문이 뺐으면 두 번 센다, 보강 전 회차는 0) — Task 2.
  - 회차 기록 `SubQuestion.rounds[]` 키: `excluded_papers: [{cnts_id, title, personal_author, pub_date}]`(Task 1, title·personal_author·pub_date 는 null 일 수 있다), `flagged: int`(끈 잡에서 무관하다고 본 수, 켠 잡은 0 — Task 3).
- `runner.py`
  - 비공개 `_paper_brief(ev: Evidence) -> dict` — `{cnts_id, title, personal_author, pub_date}` — Task 1.
  - 비공개 `_exclude_off_topic(state, subq, numbers: list[int]) -> list[dict]` — 뺀 논문의 `_paper_brief` 목록(뺀 순서). 이전에는 뺀 수(int)를 돌려줬다. 호출부는 `excluded = len(excluded_papers)` — Task 1.
  - `critique` 이벤트 payload 에 `"excluded_papers"`(회차 기록과 같은 목록, Task 1)·`"flagged"`(Task 3).
  - `params["exclude_off_topic"]` 이 0 이면 `_exclude_off_topic` 을 부르지 않고 `excluded_papers=[]`, `flagged=len(verdict.off_topic)` — 근거·몫·막힌 수·판정은 그대로 — Task 3.
- `critic.py`
  - `parse_verdict(raw, *, listed: int = 0, exclude_off_topic: bool = True)` — False 면 "보인 근거를 모두 무관하다면서 충분"을 부족으로 뒤집지 않고 `off_topic` 을 그대로 돌려준다. `critique()` 가 `bool(params["exclude_off_topic"])` 을 넘긴다. 프롬프트는 바꾸지 않는다 — Task 3.
- `synthesizer.py`
  - 비공개 `_excluded_papers(sq: SubQuestion) -> list[dict]` — 회차 순으로 잇는다(`r.get("excluded_papers", [])`) — Task 1.
  - `assemble_report` 의 `trail[]` 에 `"excluded_papers"` — Task 1. `stats` 는 `research_stats` 그대로라 `excluded` 가 저절로 실린다 — Task 2.

### 프론트

- `types/research.ts` — Task 4
  - `export interface ExcludedPaper { cnts_id: string; title?: string | null; personal_author?: string | null; pub_date?: string | null }`(서버 모양)
  - `export interface ExcludedPaperView { cntsId: string; title: string; personalAuthor: string | null; pubDate: string | null }`(뷰 모양, 제목이 없으면 `""`)
  - `SearchRoundResult` 와 `CritiqueEvent` 에 `excluded_papers?: ExcludedPaper[] | null`, `flagged?: number | null`. `TrailItem.excluded_papers?: ExcludedPaper[] | null`. `CountersPayload.excluded?: number`.
  - `RoundView.excludedPapers: ExcludedPaperView[]`(목록을 기록하기 전 회차는 `[]`), `RoundView.flagged: number | null`, `CountersView.excluded: number | null`(필수 칸).
- `utils/researchEvents.ts` — Task 4
  - `export function flaggedLabel(n: number | null): string | null` — `n > 0` 이면 `"무관 의심 N편(제외 안 함)"`, 0·null 이면 `null`.
  - `export function toExcludedPaperView(p: ExcludedPaper): ExcludedPaperView` — 제목 앞뒤 공백을 뗀다.
  - 카운터 합치기(`reconcileCounters`)는 `excluded` 도 필드별 큰 값. 옛 잡은 `null`.
- `utils/researchReport.ts` — Task 5
  - `export interface ExcludedGroup { subqIdx: number; subquestion: string; papers: ExcludedPaperView[] }`
  - `export function excludedFromTrail(trail: TrailItem[]): ExcludedGroup[]`(최종본), `export function excludedFromSubqs(subqs: SubqView[]): ExcludedGroup[]`(초안 — 탐색 타임라인의 회차 기록), `export function excludedPaperLine(p: ExcludedPaperView): string`(`"저자 외 (연도) 「제목」"`).
  - `export const EXCLUDED_TITLE = "관련성이 낮아 제외한 논문"`, `export const EXCLUDED_WHY = "자기점검이 하위질문의 핵심 개념과 무관하다고 판단해 근거에서 뺀 논문입니다."`.
  - `reportIntro`·`draftIntro` 는 `stats.excluded` 가 있으면 `(무관한 N편은 걸러냈다)`·`(무관한 N편은 걸러냈습니다)` 를 덧붙인다.
- `utils/researchDraft.ts`: `DraftReport.excluded: ExcludedGroup[]` — Task 5.
- `utils/reportDocument.ts`: `ReportDocInput.excluded: ExcludedGroup[]` — Task 6.
- `components/research/ReportView.vue`: `draft` prop 이 `{ slots: DraftSlot[]; state: DraftState; excluded: ExcludedGroup[] } | null` — Task 7. CSS 클래스 `rs-round__toggle`·`rs-round__excluded`·`rs-round__why`·`rs-caret`·`rs-excluded-list`·`rs-excluded`(`__title`·`__toggle`·`__body`·`__group`) — Task 7.

---

## 단계 1 — 백엔드 (Task 1~3)

- Task 1 → 2 → 3 은 같은 파일(`runner.py`·`state.py`·`models/research.py`·`test_research_runner.py`·`test_research_synthesizer.py`)을 차례로 고치므로 번호 순으로 한다.
- 회차 기록의 새 키(`excluded_papers`·`flagged`)는 보강 전 잡에는 없다. 읽는 쪽(`_excluded_papers`, `research_stats`, 프론트)은 모두 `get`·`??` 로 빈 값으로 읽는다.

### Task 1: 제외한 논문의 서지를 회차 기록·critique 이벤트·보고서 trail에 남기기 (§11-1 백엔드)

**계약 추가:** `critique` 이벤트 payload에도 `excluded_papers`를 싣는다. 값은 그 회차 기록과 같은 목록이고, 원소는 `{cnts_id, title, personal_author, pub_date}`(snake_case, title·personal_author·pub_date는 null일 수 있음)다. 라이브 타임라인의 "무관 N편 제외 ▾" 목록이 이 값을 쓴다(Task 4 의 점검 이벤트 합치기). 비공개 헬퍼 `runner._paper_brief`, `synthesizer._excluded_papers`를 새로 둔다.

**Files:**
- Modify: `app/services/research/runner.py` (`_exclude_off_topic`, 새 `_paper_brief`, `explore_subquestion`)
- Modify: `app/services/research/synthesizer.py` (새 `_excluded_papers`, `assemble_report` trail)
- Modify: `app/services/research/state.py` (`SubQuestion.rounds` 주석)
- Modify: `app/models/research.py` (search result 모양 주석만 바꾼다. 스키마는 그대로)
- Test: `app/tests/test_research_runner.py`, `app/tests/test_research_synthesizer.py`

- [ ] **Step 1: 실패 테스트 — 러너 회차 기록·이벤트 (`app/tests/test_research_runner.py`)**

`app/tests/test_research_runner.py`의 `TestRoundHistory.test_every_round_is_recorded_on_the_subquestion`

교체 전:
```python
        assert sq.rounds == [
            {"round": 1, "query": "가", "found_chunks": 2, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1",
             "excluded": 0},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None, "excluded": 0},
        ]
```
교체 후:
```python
        assert sq.rounds == [
            {"round": 1, "query": "가", "found_chunks": 2, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1",
             "excluded": 0, "excluded_papers": []},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None, "excluded": 0,
             "excluded_papers": []},
        ]
```

`TestRoundHistory.test_history_matches_what_was_streamed`

교체 전:
```python
             "next_query": c["next_query"], "excluded": c["excluded"]}
```
교체 후:
```python
             "next_query": c["next_query"], "excluded": c["excluded"],
             "excluded_papers": c["excluded_papers"]}
```

`TestOffTopicExclusion.test_excluded_count_is_recorded_and_streamed`의 끝 두 줄 뒤에 테스트 두 개를 넣는다.

교체 전:
```python
        # 뺀 뒤의 수다 — 화면의 채택 수와 한계 문장이 같은 값을 본다
        assert critiques[0]["adopted"] == 1
```
교체 후:
```python
        # 뺀 뒤의 수다 — 화면의 채택 수와 한계 문장이 같은 값을 본다
        assert critiques[0]["adopted"] == 1

    def test_excluded_papers_keep_their_bibliography_after_leaving_the_pool(self):
        """풀에서 지우면 무엇을 뺐는지 알 길이 없다 — 회차 기록과 critique 이벤트에 서지를 남겨 타임라인·
        보고서가 걸러낸 논문을 보여 준다."""
        async def _with_author(query, *, params, db):
            hits, meta = _hits(["A", "B"], query=query)
            meta["B"]["personal_author"] = "홍길동"
            return hits, meta

        events, emit = _recorder()
        st = self._state("가", max_recheck=0)
        (sq,) = st.subquestions
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_with_author,
                                        critique_fn=_ScriptedCritic(("sufficient", [2], [])),
                                        emit=emit))
        paper = {"cnts_id": "B", "title": "논문 B", "personal_author": "홍길동", "pub_date": "2008-06"}
        assert "E2" not in st.evidence
        assert [r["excluded_papers"] for r in sq.rounds] == [[paper]]
        assert [c["excluded_papers"] for c in _of(events, "critique")] == [[paper]]

    def test_each_round_records_only_the_papers_it_excluded(self):
        st = self._state("가", max_recheck=2)
        (sq,) = st.subquestions
        critic = _ScriptedCritic(("insufficient", [2], ["보완"]), ("insufficient", [], ["추가"]),
                                 ("sufficient", [1], []))
        self._run(st, sq, {"가": ["A", "B"], "보완": ["C"], "추가": ["D"]}, critic)
        assert [[p["cnts_id"] for p in r["excluded_papers"]] for r in sq.rounds] == [["B"], [], ["A"]]
```

- [ ] **Step 2: 실패 테스트 — 보고서 trail (`app/tests/test_research_synthesizer.py`)**

`app/tests/test_research_synthesizer.py` import

교체 전:
```python
from services.research.state import Chunk, Evidence, ResearchState, SubQuestion, merge_params
```
교체 후:
```python
from services.research.state import (
    Chunk, Evidence, ResearchState, SubQuestion, merge_params, restore_state, snapshot_state,
)
```

`TestAssembleReport.test_trail_carries_excluded_count` 뒤에 추가한다.

교체 전:
```python
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded"] for t in trail] == [2, 0]
```
교체 후:
```python
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded"] for t in trail] == [2, 0]

    def test_trail_carries_the_excluded_papers_in_round_order(self):
        """보고서 '관련성이 낮아 제외한 논문'과 문서 부록의 원천 — 풀에서 지운 논문도 회차 기록의 서지로 남는다."""
        st = _state()
        edge = {"cnts_id": "X", "title": "의료영상 Edge method", "personal_author": "김",
                "pub_date": "2001"}
        mpeg = {"cnts_id": "Y", "title": "MPEG-7 Edge Histogram", "personal_author": None,
                "pub_date": "2003"}
        st.subquestions[0].excluded_cnts = ["X", "Y"]
        st.subquestions[0].rounds = [{"round": 1, "excluded": 1, "excluded_papers": [edge]},
                                     {"round": 2, "excluded": 0, "excluded_papers": []},
                                     {"round": 3, "excluded": 1, "excluded_papers": [mpeg]}]
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded_papers"] for t in trail] == [[edge, mpeg], []]

    def test_resumed_job_with_rounds_recorded_before_the_bibliography_has_no_excluded_papers(self):
        # 보강 전 회차 기록에는 excluded_papers 가 없다 — 그 스냅샷에서 종합만 다시 해도 보고서가 깨지지 않는다
        st = _state()
        st.subquestions[0].rounds = [{"round": 1, "query": "하위1", "found_chunks": 3,
                                      "new_papers": 1, "verdict": "sufficient", "note": "충분하다",
                                      "next_query": None, "excluded": 0}]
        back = restore_state("j1", snapshot_state(st))
        trail = assemble_report(back, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded_papers"] for t in trail] == [[], []]
```

- [ ] **Step 3: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_runner.py tests/test_research_synthesizer.py -q`
Expected: `6 failed, 171 passed`
- `test_every_round_is_recorded_on_the_subquestion`: AssertionError(dict 불일치)
- `test_history_matches_what_was_streamed`, `test_excluded_papers_keep_their_bibliography_after_leaving_the_pool`, `test_each_round_records_only_the_papers_it_excluded`, synthesizer 새 테스트 2개: `KeyError: 'excluded_papers'`

- [ ] **Step 4: 구현 — `app/services/research/runner.py`**

교체 전:
```python
def _exclude_off_topic(state: ResearchState, subq: SubQuestion, numbers: list[int]) -> int:
    """자기점검이 무관하다고 가리킨 근거(목록 번호, 1부터)를 이 하위질문에서 빼고 뺀 수를 돌려준다.

    번호는 critic 에게 넘긴 목록의 순서이고, 그 목록은 subq.evidence_ids 순서 그대로다.
    다른 하위질문이 링크하지 않은 근거는 풀에서도 지운다 — 남기면 어느 절에도 실리지 않을 논문이
    전체 상한만 차지한다. 다른 하위질문이 쓰는 근거는 둔다 — 그쪽에는 관련 있을 수 있다.
    순위 보조값(relevance·leaders)은 evidence_ids 에 남은 id 만 보므로(_rank_order) 건드리지 않는다.
    """
    off = [subq.evidence_ids[n - 1] for n in numbers]
    linked_elsewhere = {e for sq in state.subquestions if sq is not subq for e in sq.evidence_ids}
    for eid in off:
        subq.evidence_ids.remove(eid)
        for cid in subq.evidence_chunks.pop(eid):
            del subq.chunk_scores[cid]
        subq.excluded_cnts.append(state.evidence[eid].cnts_id)
        if eid not in linked_elsewhere:
            del state.evidence[eid]
    return len(off)
```
교체 후:
```python
def _paper_brief(ev: Evidence) -> dict:
    """뺀 논문의 서지 요약 — 회차 기록(excluded_papers)에 남는다. 풀에서 지운 뒤에는 이것 말고 무엇을
    뺐는지 알 길이 없다."""
    return {"cnts_id": ev.cnts_id, "title": ev.meta.get("title"),
            "personal_author": ev.meta.get("personal_author"), "pub_date": ev.meta.get("pub_date")}


def _exclude_off_topic(state: ResearchState, subq: SubQuestion, numbers: list[int]) -> list[dict]:
    """자기점검이 무관하다고 가리킨 근거(목록 번호, 1부터)를 이 하위질문에서 빼고, 뺀 논문의 서지 요약
    (_paper_brief)을 뺀 순서대로 돌려준다.

    번호는 critic 에게 넘긴 목록의 순서이고, 그 목록은 subq.evidence_ids 순서 그대로다.
    다른 하위질문이 링크하지 않은 근거는 풀에서도 지운다 — 남기면 어느 절에도 실리지 않을 논문이
    전체 상한만 차지한다. 다른 하위질문이 쓰는 근거는 둔다 — 그쪽에는 관련 있을 수 있다.
    순위 보조값(relevance·leaders)은 evidence_ids 에 남은 id 만 보므로(_rank_order) 건드리지 않는다.
    """
    off = [subq.evidence_ids[n - 1] for n in numbers]
    linked_elsewhere = {e for sq in state.subquestions if sq is not subq for e in sq.evidence_ids}
    papers = []
    for eid in off:
        subq.evidence_ids.remove(eid)
        for cid in subq.evidence_chunks.pop(eid):
            del subq.chunk_scores[cid]
        ev = state.evidence[eid]
        subq.excluded_cnts.append(ev.cnts_id)
        papers.append(_paper_brief(ev))
        if eid not in linked_elsewhere:
            del state.evidence[eid]
    return papers
```

`explore_subquestion`

교체 전:
```python
        excluded = _exclude_off_topic(state, subq, verdict.off_topic)
        own = len(made.intersection(subq.evidence_ids))
```
교체 후:
```python
        excluded_papers = _exclude_off_topic(state, subq, verdict.off_topic)
        excluded = len(excluded_papers)
        own = len(made.intersection(subq.evidence_ids))
```

교체 전:
```python
            "note": verdict.note, "next_query": next_query, "excluded": excluded,
        })
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
            "round": round_no, "next_query": next_query, "excluded": excluded,
            "will_recheck": next_query is not None,
        })
```
교체 후:
```python
            "note": verdict.note, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers,
        })
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
            "round": round_no, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers,
            "will_recheck": next_query is not None,
        })
```

- [ ] **Step 5: 구현 — `app/services/research/synthesizer.py`**

교체 전:
```python
def assemble_report(
    state: ResearchState, sections: list[dict], *, unmarked_total: int,
) -> dict:
```
교체 후:
```python
def _excluded_papers(sq: SubQuestion) -> list[dict]:
    """하위질문이 무관하다고 뺀 논문의 서지 요약을 회차 순으로 잇는다. 한 번 뺀 논문은 같은 하위질문에
    다시 들지 않으니(runner) 중복이 없다. 보강 전 회차 기록에는 excluded_papers 가 없다."""
    return [p for r in sq.rounds for p in r.get("excluded_papers", [])]


def assemble_report(
    state: ResearchState, sections: list[dict], *, unmarked_total: int,
) -> dict:
```

교체 전:
```python
             "excluded": len(sq.excluded_cnts)}
            for sq in state.subquestions
```
교체 후:
```python
             "excluded": len(sq.excluded_cnts),
             # 보고서의 '관련성이 낮아 제외한 논문'과 문서 부록 — 풀에서 지운 논문도 서지가 남는다
             "excluded_papers": _excluded_papers(sq)}
            for sq in state.subquestions
```

- [ ] **Step 6: 주석 — `app/services/research/state.py`·`app/models/research.py`**

`app/services/research/state.py`

교체 전:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query, excluded}].
    # verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다. excluded(그 회차에 무관하다고 뺀 수)는
    # 보강 전 잡의 회차에는 없다.
```
교체 후:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query, excluded,
    # excluded_papers}]. verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다. excluded(그 회차에 무관하다고 뺀 수)·excluded_papers
    # (뺀 논문의 서지 요약 — 풀에서 지운 뒤에도 무엇을 뺐는지 남는다)는 보강 전 잡의 회차에는 없다.
```

`app/models/research.py`

교체 전:
```python
    #                          "verdict", "note", "next_query", "excluded"?}],
    #             excluded 는 그 회차 자기점검이 무관하다고 뺀 근거 수(보강 전 잡의 회차에는 없다).
```
교체 후:
```python
    #                          "verdict", "note", "next_query", "excluded"?, "excluded_papers"?}],
    #             excluded 는 그 회차 자기점검이 무관하다고 뺀 근거 수, excluded_papers 는 뺀 논문의
    #             서지 요약 [{"cnts_id", "title", "personal_author", "pub_date"}](보강 전 잡의 회차에는 없다).
```

- [ ] **Step 7: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_runner.py tests/test_research_synthesizer.py -q`
Expected: `177 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py`
Expected: `869 passed`(경고 2건은 기존 것)

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/runner.py app/services/research/synthesizer.py app/services/research/state.py app/models/research.py app/tests/test_research_runner.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04c — 자기점검이 무관하다고 뺀 논문의 서지(cnts_id·제목·저자·연도)를 회차 기록과 critique 이벤트의 excluded_papers 에 남기고, 보고서 trail 에 하위질문별로 회차 순으로 잇는다: 풀에서 지운 뒤에도 무엇을 뺐는지 타임라인·보고서·문서가 보여 줄 원천이다. 한 번 뺀 논문은 같은 하위질문에 다시 들지 않아 중복이 없고, 보강 전 회차 기록은 빈 목록으로 읽는다"
```

---

### Task 2: `research_stats.excluded` — counters 이벤트·단계 result·보고서 stats (§11-2 백엔드)

**Files:**
- Modify: `app/services/research/state.py` (`research_stats`)
- Modify: `app/models/research.py` (counters 모양 주석만)
- Test: `app/tests/test_research_state.py`, `app/tests/test_research_runner.py`, `app/tests/test_research_synthesizer.py`, `app/tests/test_research_tasks.py`
- `app/workers/research_tasks.py`는 고치지 않는다. counters 이벤트(runner), 단계 result(`_search_progress`), 보고서 stats(`assemble_report`)가 모두 `research_stats` 한 함수를 보기 때문이다. 테스트로만 고정한다.

- [ ] **Step 1: 실패 테스트 — state (`app/tests/test_research_state.py`)**

`app/tests/test_research_state.py`

교체 전:
```python
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
교체 후:
```python
class TestResearchStats:
    def test_counts_unique_papers_adopted_evidence_and_rechecks(self):
        st = _explored_state()          # 검색어 이력: ["q1", "q2"], ["q3"], []
        st.seen_cnts = {"KCI_A", "KCI_B", "KCI_C"}
        assert research_stats(st) == {
            "papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 1, "excluded": 0,
        }

    def test_empty_state_is_all_zero(self):
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        assert research_stats(st) == {
            "papers_reviewed": 0, "evidence_adopted": 0, "rechecks": 0, "excluded": 0,
        }

    def test_excluded_sums_every_round_of_every_subquestion(self):
        # 하위질문별 판단의 수다 — 같은 논문을 두 하위질문이 뺐으면 두 번 센다
        st = _explored_state()
        st.subquestions[0].rounds = [{"round": 1, "excluded": 2}, {"round": 2, "excluded": 1}]
        st.subquestions[1].rounds = [{"round": 1, "excluded": 1}]
        assert research_stats(st)["excluded"] == 4

    def test_rounds_recorded_before_exclusion_count_as_zero(self):
        # 보강 전 회차 기록에는 excluded 가 없다
        st = _explored_state()
        st.subquestions[0].rounds = [dict(r) for r in _ROUNDS]
        assert research_stats(st)["excluded"] == 0

    def test_same_after_resume(self):
        st = _explored_state()
        st.seen_cnts = {"KCI_A", "KCI_B"}
        st.subquestions[0].rounds = [{"round": 1, "excluded": 2}]
        assert research_stats(restore_state("j1", snapshot_state(st))) == research_stats(st)
```

- [ ] **Step 2: 실패 테스트 — runner counters 이벤트 (`app/tests/test_research_runner.py`)**

`app/tests/test_research_runner.py`의 `TestRoundEvents`

교체 전:
```python
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
```
교체 후:
```python
        assert _of(events, "counters") == [
            {"papers_reviewed": 2, "evidence_adopted": 2, "rechecks": 0, "excluded": 0},
            {"papers_reviewed": 3, "evidence_adopted": 3, "rechecks": 1, "excluded": 0},
        ]

    def test_counters_are_job_wide(self):
        st = self._state("가", "나", max_recheck=0)
        events = self._run(st, explore=_fake_explore)
        assert _of(events, "counters")[-1] == {
            "papers_reviewed": 1, "evidence_adopted": 1, "rechecks": 0, "excluded": 0,
        }

    def test_counters_show_papers_excluded_in_earlier_rounds(self):
        """무관 제외로 채택 수가 줄 때 제외를 따로 보여야 결과가 준 것으로 읽히지 않는다. counters 는 검색
        직후에 나가 앞 회차까지 뺀 수다 — 이번 회차의 제외는 회차를 닫으며 저장하는 단계 result 가 싣는다."""
        st = self._state("가", max_recheck=1)
        events = self._run(st, explore=_explore_table({"가": ["A", "B"], "보완": ["C"]}),
                           critic=_ScriptedCritic(("insufficient", [2], ["보완"]),
                                                  ("sufficient", [], [])))
        assert _of(events, "counters") == [
            {"papers_reviewed": 2, "evidence_adopted": 2, "rechecks": 0, "excluded": 0},
            {"papers_reviewed": 3, "evidence_adopted": 2, "rechecks": 1, "excluded": 1},
        ]
```

- [ ] **Step 3: 실패 테스트 — 보고서 stats (`app/tests/test_research_synthesizer.py`)**

`app/tests/test_research_synthesizer.py`의 `TestReportStats`

교체 전:
```python
    def test_report_carries_research_stats(self):
        st = _state()
        st.seen_cnts = {"A", "B", "C"}
        st.subquestions[0].queries = ["q1", "q2"]
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert report["stats"] == {"papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 1}
```
교체 후:
```python
    def test_report_carries_research_stats(self):
        st = _state()
        st.seen_cnts = {"A", "B", "C"}
        st.subquestions[0].queries = ["q1", "q2"]
        st.subquestions[1].excluded_cnts = ["B", "C"]
        st.subquestions[1].rounds = [{"round": 1, "excluded": 2}]
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert report["stats"] == {"papers_reviewed": 3, "evidence_adopted": 1, "rechecks": 1,
                                   "excluded": 2}
```

- [ ] **Step 4: 실패 테스트 — 워커 단계 result (`app/tests/test_research_tasks.py`)**

`app/tests/test_research_tasks.py`의 `TestLiveProgress.test_finished_search_step_keeps_counters` 뒤에 추가한다.

교체 전:
```python
        assert [f[2]["counters"]["papers_reviewed"] for f in h.finished[:2]] == [1, 2]
```
교체 후:
```python
        assert [f[2]["counters"]["papers_reviewed"] for f in h.finished[:2]] == [1, 2]

    def test_saved_counters_include_papers_excluded_in_the_round(self, monkeypatch):
        """counters 이벤트는 검색 직후라 이번 회차의 제외를 모른다 — 회차를 닫으며 저장·알리는 단계 result
        와 닫힌 단계가 제외 수를 싣는다(재접속한 화면의 카운터 '제외' 칸 원천)."""
        rt = _load_tasks(monkeypatch)
        job = _FakeJob(stage="planned", plan=["하위1"])
        h = None

        async def _excluding_round(state, subq):
            subq.rounds.append({**_ROUNDS[0], "excluded": 2})
            await h.emit("critique", {"subq_idx": 0, "verdict": "insufficient", "excluded": 2})

        h = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                            explore=_excluding_round)
        asyncio.run(rt._run_deep_research(str(job.id)))

        assert [res["counters"]["excluded"] for _, res in h.progress] == [2]
        assert h.finished[0][2]["counters"]["excluded"] == 2
```

- [ ] **Step 5: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py tests/test_research_runner.py tests/test_research_synthesizer.py tests/test_research_tasks.py -q`
Expected: `9 failed, 324 passed`
- state 4건: dict 불일치 2건, `KeyError: 'excluded'` 2건. `test_same_after_resume`는 양쪽 다 키가 없어 통과한다.
- runner 3건: dict 불일치
- synthesizer 1건: dict 불일치
- tasks 1건: `KeyError: 'excluded'`

- [ ] **Step 6: 구현 — `app/services/research/state.py`**

교체 전:
```python
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
교체 후:
```python
def research_stats(state: ResearchState) -> dict:
    """진행 카운터와 보고서 서론의 숫자. 둘이 같은 함수를 봐야 진행 중에 본 숫자와
    보고서의 숫자가 어긋나지 않는다.

    재검색 횟수는 따로 세지 않고 시도한 검색어 이력에서 얻는다 — 검색어는 이미
    스냅샷에 실리므로 재개한 잡에서도 같은 값이 나온다. 제외 수도 같은 이유로 회차 기록에서 얻는다.

    excluded 는 하위질문별 판단의 수다 — 같은 논문을 두 하위질문이 뺐으면 두 번 센다. 채택 수만 보이면
    무관 제외로 줄어든 숫자가 결과가 준 것으로 읽힌다. 보강 전 회차에는 excluded 가 없다.
    """
    return {
        "papers_reviewed": len(state.seen_cnts),
        "evidence_adopted": len(state.evidence),
        "rechecks": sum(max(len(sq.queries) - 1, 0) for sq in state.subquestions),
        "excluded": sum(r.get("excluded", 0) for sq in state.subquestions for r in sq.rounds),
    }
```

- [ ] **Step 7: 주석 — `app/models/research.py`**

교체 전:
```python
    #              "counters": {"papers_reviewed", "evidence_adopted", "rechecks"}}
```
교체 후:
```python
    #              "counters": {"papers_reviewed", "evidence_adopted", "rechecks", "excluded"?}}
```

- [ ] **Step 8: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py tests/test_research_runner.py tests/test_research_synthesizer.py tests/test_research_tasks.py -q`
Expected: `333 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py`
Expected: `873 passed`

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/state.py app/models/research.py app/tests/test_research_state.py app/tests/test_research_runner.py app/tests/test_research_synthesizer.py app/tests/test_research_tasks.py
git commit -m "[Feat] round04c — 진행 카운터·단계 result·보고서 stats 에 제외 수(excluded)를 더한다: 모든 하위질문 회차 기록의 excluded 합이라 같은 논문을 두 하위질문이 뺐으면 두 번 센다(하위질문별 판단의 수). 채택 수만 보이면 무관 제외로 줄어든 숫자가 결과가 준 것으로 읽힌다. 세 곳이 research_stats 한 함수를 보고, 보강 전 회차는 0 으로 센다. counters 이벤트는 검색 직후라 앞 회차까지의 수이고 이번 회차의 제외는 회차를 닫는 단계 result 가 싣는다"
```

---

### Task 3: `exclude_off_topic` 파라미터 — 끈 잡은 빼지 않고 `flagged`만 기록 (§11-3 백엔드)

**끈 잡에서 판정을 어떻게 할지 정했다:** 끈 잡(`exclude_off_topic=0`)에서는 `parse_verdict`의 "보인 근거를 모두 무관하다고 하면서 충분이라는 답은 부족으로 읽는다" 규칙을 **적용하지 않는다**. 그 규칙은 "빼고 나면 남는 것은 0편이거나 목록 밖 근거뿐"이라는 전제에서만 맞다. 끈 잡은 근거를 빼지 않으므로 판정이 본 근거가 그대로 남는다. 또 끈 잡만 뒤집으면 재검색이 늘어, 켠 잡과 나란히 비교할 기준(걸린 시간·근거 수)이 흐려진다. `off_topic` 번호는 그대로 돌려주고 러너가 `flagged`로 센다. critic 프롬프트는 바꾸지 않는다(spec §11-3 "critic 은 그대로 번호를 돌려주지만").

**계약 추가:**
- `critic.parse_verdict(raw, *, listed=0, exclude_off_topic=True)`: 키워드 인자를 새로 둔다. `critique()`가 `params["exclude_off_topic"]`를 넘긴다.
- `critique` 이벤트 payload에도 `flagged: int`를 싣는다. 회차 기록과 같은 값이고, 켠 잡은 0이다.

**Files:**
- Modify: `app/services/research/state.py` (`DEFAULT_PARAMS`, `_PARAM_BOUNDS`, `SubQuestion.rounds` 주석)
- Modify: `app/services/research/critic.py` (`parse_verdict`, `critique`)
- Modify: `app/services/research/runner.py` (`explore_subquestion`)
- Modify: `app/models/research.py` (search result 모양 주석만)
- Test: `app/tests/test_research_state.py`, `app/tests/test_research_critic.py`, `app/tests/test_research_runner.py`, `app/tests/test_research_api.py`

- [ ] **Step 1: 실패 테스트 — 파라미터 검증 (`app/tests/test_research_state.py`, `app/tests/test_research_api.py`)**

`app/tests/test_research_state.py`

교체 전:
```python
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
        }
```
교체 후:
```python
        assert set(DEFAULT_PARAMS) == {
            "max_subquestions", "max_recheck", "max_evidence", "per_subq_top_k",
            "chunks_per_evidence", "citation_weight", "min_evidence_per_subq",
            "exclude_off_topic",
        }
```

교체 전:
```python
        with pytest.raises(ValueError, match="per_subq_top_k"):
            merge_params({"per_subq_top_k": 1_000_000})
```
교체 후:
```python
        with pytest.raises(ValueError, match="per_subq_top_k"):
            merge_params({"per_subq_top_k": 1_000_000})

    def test_off_topic_exclusion_is_on_by_default(self):
        assert DEFAULT_PARAMS["exclude_off_topic"] == 1

    @pytest.mark.parametrize("value", [0, 1])
    def test_off_topic_exclusion_takes_zero_or_one(self, value):
        # 운영에서 결과가 나쁘면 재배포 없이 잡 파라미터 0 으로 끈다
        assert merge_params({"exclude_off_topic": value})["exclude_off_topic"] == value

    @pytest.mark.parametrize("value", [2, -1, True, "0", 0.0])
    def test_off_topic_exclusion_rejects_anything_else(self, value):
        # True 는 int 의 서브클래스라 막지 않으면 1 로 통과한다
        with pytest.raises(ValueError, match="exclude_off_topic"):
            merge_params({"exclude_off_topic": value})
```

`app/tests/test_research_api.py`의 `TestCreate`. spec §11-3의 운영자 curl 경로다.

교체 전:
```python
        (row,) = api.db.jobs.values()
        assert row["status"] == "failed" and row["last_error"]
```
교체 후:
```python
        (row,) = api.db.jobs.values()
        assert row["status"] == "failed" and row["last_error"]

    def test_operator_can_turn_off_topic_exclusion_off_per_job(self, api):
        # 운영에서 결과가 나쁘면 재배포 없이 끈다(spec §11-3 의 curl) — 기본값에 합쳐 저장한다
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"exclude_off_topic": 0}})
        assert res.status_code == 200
        (row,) = api.db.jobs.values()
        assert row["params"]["exclude_off_topic"] == 0
        assert row["params"]["max_evidence"] == 90

    def test_off_topic_exclusion_other_than_zero_or_one_is_422(self, api):
        res = api.client.post("/api/research", json={"question": "독서 격차 연구",
                                                      "params": {"exclude_off_topic": 2}})
        assert res.status_code == 422
```

- [ ] **Step 2: 실패 테스트 — critic (`app/tests/test_research_critic.py`)**

`app/tests/test_research_critic.py`의 `TestOffTopic`

교체 전:
```python
    def test_sufficient_with_listed_evidence_left_is_trusted(self):
        v = self._parse([1], listed=2, verdict="sufficient")
        assert (v.verdict, v.note) == ("sufficient", "n")
```
교체 후:
```python
    def test_sufficient_with_listed_evidence_left_is_trusted(self):
        v = self._parse([1], listed=2, verdict="sufficient")
        assert (v.verdict, v.note) == ("sufficient", "n")

    def test_job_with_exclusion_off_keeps_a_sufficient_verdict(self):
        """무관 제외를 끈 잡은 근거를 빼지 않는다 — 판정이 본 근거가 그대로 남아 뒤집을 이유가 없고, 뒤집으면
        끈 잡만 재검색을 더 돌아 켠 잡과 나란히 볼 기준이 흐려진다. 번호는 러너가 flagged 로 세도록 남긴다."""
        raw = json.dumps({"verdict": "sufficient", "note": "n", "new_queries": [],
                          "off_topic": [2, 1]})
        v = parse_verdict(raw, listed=2, exclude_off_topic=False)
        assert (v.verdict, v.note, v.off_topic) == ("sufficient", "n", [2, 1])
```

`TestCritique`

교체 전:
```python
        v = self._run(monkeypatch, fake_chat, evidence=self._many())
        assert v.off_topic == [_MAX_LISTED]
```
교체 후:
```python
        v = self._run(monkeypatch, fake_chat, evidence=self._many())
        assert v.off_topic == [_MAX_LISTED]

    def test_job_with_exclusion_off_does_not_flip_the_verdict(self, monkeypatch):
        # 잡 파라미터가 parse_verdict 까지 닿아야 한다 — 끈 잡에서 뒤집으면 켠 잡과 같은 재검색을 돈다
        async def fake_chat(messages, *, params=None, timeout=None):
            return '{"verdict": "sufficient", "note": "충분하다", "new_queries": [], "off_topic": [1]}'

        monkeypatch.setattr(critic, "chat", fake_chat)
        v = asyncio.run(critic.critique(SubQuestion(idx=0, text="하위질문"), self._evidence(),
                                        params=merge_params({"exclude_off_topic": 0})))
        assert (v.verdict, v.note, v.off_topic) == ("sufficient", "충분하다", [1])
```

- [ ] **Step 3: 실패 테스트 — runner (`app/tests/test_research_runner.py`)**

`app/tests/test_research_runner.py`의 `TestRoundHistory.test_every_round_is_recorded_on_the_subquestion`. 교체 전은 Task 1을 반영한 상태다.

교체 전:
```python
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1",
             "excluded": 0, "excluded_papers": []},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None, "excluded": 0,
             "excluded_papers": []},
```
교체 후:
```python
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1",
             "excluded": 0, "excluded_papers": [], "flagged": 0},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None, "excluded": 0,
             "excluded_papers": [], "flagged": 0},
```

`test_history_matches_what_was_streamed`

교체 전:
```python
             "excluded_papers": c["excluded_papers"]}
```
교체 후:
```python
             "excluded_papers": c["excluded_papers"], "flagged": c["flagged"]}
```

`TestJudgedBeforeExclusion` 끝에 새 클래스를 붙인다.

교체 전:
```python
        assert "모인 근거: 3편" in seen[1]
        assert sq.verdict == "sufficient" and len(sq.evidence_ids) == 3
```
교체 후:
```python
        assert "모인 근거: 3편" in seen[1]
        assert sq.verdict == "sufficient" and len(sq.evidence_ids) == 3


class TestOffTopicExclusionOff:
    """exclude_off_topic=0 — 자기점검은 번호를 그대로 돌려주지만 러너는 빼지 않고 flagged 로만 센다.
    운영에서 무관 제외가 결과를 줄이면 재배포 없이 끄고, 켠 잡과 나란히 비교한다."""

    def _state(self, text, **params):
        st = ResearchState(job_id="j", question="q", params=merge_params(params))
        st.subquestions = [SubQuestion(idx=0, text=text)]
        return st

    def test_flagged_evidence_stays_in_the_subquestion_and_the_pool(self):
        events, emit = _recorder()
        st = self._state("가", max_recheck=0, exclude_off_topic=0)
        (sq,) = st.subquestions
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_explore_table({"가": ["A", "B", "C"]}),
            critique_fn=_ScriptedCritic(("sufficient", [1, 3], [])), emit=emit,
        ))
        assert [st.evidence[e].cnts_id for e in sq.evidence_ids] == ["A", "B", "C"]
        assert len(st.evidence) == 3 and sq.excluded_cnts == []
        assert [(r["excluded"], r["excluded_papers"], r["flagged"]) for r in sq.rounds] == [
            (0, [], 2)]
        (critique,) = _of(events, "critique")
        assert (critique["excluded"], critique["excluded_papers"], critique["flagged"]) == (0, [], 2)
        assert critique["adopted"] == 3

    def test_job_with_exclusion_on_records_no_flagged(self):
        # 켠 잡은 뺀 수가 excluded 에 있다 — flagged 는 끈 잡에서만 센다
        st = self._state("가", max_recheck=0)
        (sq,) = st.subquestions
        asyncio.run(explore_subquestion(
            st, sq, db=None, explore_fn=_explore_table({"가": ["A", "B"]}),
            critique_fn=_ScriptedCritic(("sufficient", [2], [])), emit=None,
        ))
        assert [(r["excluded"], r["flagged"]) for r in sq.rounds] == [(1, 0)]

    def test_every_listed_evidence_flagged_does_not_search_again(self, monkeypatch):
        """끈 잡은 판정을 뒤집지 않는다 — 근거가 그대로 남아 '충분'이 본 근거가 있다. 뒤집으면 끈 잡만
        재검색을 더 돌아 켠 잡과 비교할 기준(걸린 시간·근거 수)이 흐려진다. 실제 critique·parse_verdict 를 거친다."""
        async def fake_chat(messages, *, params=None, timeout=None):
            return json.dumps({"verdict": "sufficient", "note": "충분하다", "new_queries": ["보완"],
                               "off_topic": [1, 2]}, ensure_ascii=False)

        monkeypatch.setattr(critic_module, "chat", fake_chat)
        st = self._state("엣지 컴퓨팅 자원", max_recheck=3, exclude_off_topic=0)
        (sq,) = st.subquestions
        asyncio.run(explore_subquestion(
            st, sq, db=None,
            explore_fn=_explore_table({"엣지 컴퓨팅 자원": ["A", "B"], "보완": []}), emit=None,
        ))
        assert sq.queries == ["엣지 컴퓨팅 자원"]
        assert (sq.verdict, sq.note) == ("sufficient", "충분하다")
        assert len(sq.evidence_ids) == 2 and sq.rounds[0]["flagged"] == 2
```

- [ ] **Step 4: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_api.py -q`
Expected: `12 failed, 259 passed`
- state 4건: 키 집합 AssertionError, `KeyError: 'exclude_off_topic'`, `takes_zero_or_one[0]`·`[1]`의 ValueError "알 수 없는 파라미터". `rejects_anything_else`는 거부 메시지에 이름이 들어가 이미 통과한다.
- critic 2건: `TypeError: ... unexpected keyword argument 'exclude_off_topic'`, ValueError
- runner 5건: TestRoundHistory 2건(dict 불일치, `KeyError: 'flagged'`), 새 클래스 3건(ValueError 2, `KeyError: 'flagged'` 1)
- api 1건: `assert 422 == 200`

- [ ] **Step 5: 구현 — `app/services/research/state.py`**

교체 전:
```python
    "citation_weight": 0.2,
    "min_evidence_per_subq": 5,
})
```
교체 후:
```python
    "citation_weight": 0.2,
    "min_evidence_per_subq": 5,
    # 자기점검이 무관하다고 본 근거를 뺄지(1) 세기만 할지(0). 운영에서 결과가 줄면 재배포 없이 잡 파라미터로
    # 끄고, 끈 잡의 회차 기록 flagged 로 켠 잡과 나란히 비교한다
    "exclude_off_topic": 1,
})
```

교체 전:
```python
    "min_evidence_per_subq": (int, 0, 50),
}
```
교체 후:
```python
    "min_evidence_per_subq": (int, 0, 50),
    "exclude_off_topic": (int, 0, 1),
}
```

`SubQuestion.rounds` 주석. 교체 전은 Task 1을 반영한 상태다.

교체 전:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query, excluded,
    # excluded_papers}]. verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다. excluded(그 회차에 무관하다고 뺀 수)·excluded_papers
    # (뺀 논문의 서지 요약 — 풀에서 지운 뒤에도 무엇을 뺐는지 남는다)는 보강 전 잡의 회차에는 없다.
```
교체 후:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query, excluded,
    # excluded_papers, flagged}]. verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을
    # 때 "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다. excluded(그 회차에 무관하다고 뺀 수)·excluded_papers
    # (뺀 논문의 서지 요약 — 풀에서 지운 뒤에도 무엇을 뺐는지 남는다)·flagged(무관 제외를 끈 잡에서 무관하다고
    # 본 수, 켠 잡은 0)는 보강 전 잡의 회차에는 없다.
```

- [ ] **Step 6: 구현 — `app/services/research/critic.py`**

교체 전:
```python
def parse_verdict(raw: str, *, listed: int = 0) -> Verdict:
```
교체 후:
```python
def parse_verdict(raw: str, *, listed: int = 0, exclude_off_topic: bool = True) -> Verdict:
```

교체 전:
```python
    러너가 다시 찾지 않고 '충분·근거 0편'이나 판정받지 않은 근거로 절을 쓴다. note 는 뒤집은
    판정의 이유라 싣지 않는다.
    """
```
교체 후:
```python
    러너가 다시 찾지 않고 '충분·근거 0편'이나 판정받지 않은 근거로 절을 쓴다. note 는 뒤집은
    판정의 이유라 싣지 않는다.

    exclude_off_topic 이 False(무관 제외를 끈 잡)면 뒤집지 않는다. 러너가 근거를 빼지 않으니 판정이 본
    근거가 그대로 남는다 — 뒤집으면 끈 잡만 재검색을 더 돌아 켠 잡과 나란히 비교할 기준이 흐려진다.
    off_topic 은 그대로 돌려준다(러너가 flagged 로 센다).
    """
```

교체 전:
```python
    if verdict == "sufficient" and off_topic and len(off_topic) == listed:
```
교체 후:
```python
    if exclude_off_topic and verdict == "sufficient" and off_topic and len(off_topic) == listed:
```

교체 전:
```python
    verdict = parse_verdict(raw, listed=min(len(evidence), _MAX_LISTED))
```
교체 후:
```python
    verdict = parse_verdict(raw, listed=min(len(evidence), _MAX_LISTED),
                            exclude_off_topic=bool(params["exclude_off_topic"]))
```

- [ ] **Step 7: 구현 — `app/services/research/runner.py` 의 `explore_subquestion`**

교체 전은 Task 1을 반영한 상태다.

교체 전:
```python
        excluded_papers = _exclude_off_topic(state, subq, verdict.off_topic)
        excluded = len(excluded_papers)
        own = len(made.intersection(subq.evidence_ids))
```
교체 후:
```python
        if params["exclude_off_topic"]:
            excluded_papers, flagged = _exclude_off_topic(state, subq, verdict.off_topic), 0
        else:
            # 끈 잡은 빼지 않고 무관하다고 본 수만 남긴다 — 켠 잡과 나란히 볼 때 "끈 잡에서도 이만큼을
            # 무관하다고 봤다"를 알 수 있게. 근거·몫·막힌 수는 그대로다
            excluded_papers, flagged = [], len(verdict.off_topic)
        excluded = len(excluded_papers)
        own = len(made.intersection(subq.evidence_ids))
```

교체 전:
```python
            "note": verdict.note, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers,
        })
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
            "round": round_no, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers,
            "will_recheck": next_query is not None,
        })
```
교체 후:
```python
            "note": verdict.note, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers, "flagged": flagged,
        })
        await emit("critique", {
            "subq_idx": subq.idx, "verdict": verdict.verdict,
            "note": verdict.note, "adopted": len(subq.evidence_ids),
            "parse_failed": verdict.parse_failed, "capped": subq.capped,
            "round": round_no, "next_query": next_query, "excluded": excluded,
            "excluded_papers": excluded_papers, "flagged": flagged,
            "will_recheck": next_query is not None,
        })
```

- [ ] **Step 8: 주석 — `app/models/research.py`**

교체 전은 Task 1을 반영한 상태다.

교체 전:
```python
    #                          "verdict", "note", "next_query", "excluded"?, "excluded_papers"?}],
    #             excluded 는 그 회차 자기점검이 무관하다고 뺀 근거 수, excluded_papers 는 뺀 논문의
    #             서지 요약 [{"cnts_id", "title", "personal_author", "pub_date"}](보강 전 잡의 회차에는 없다).
```
교체 후:
```python
    #                          "verdict", "note", "next_query", "excluded"?, "excluded_papers"?,
    #                          "flagged"?}],
    #             excluded 는 그 회차 자기점검이 무관하다고 뺀 근거 수, excluded_papers 는 뺀 논문의
    #             서지 요약 [{"cnts_id", "title", "personal_author", "pub_date"}], flagged 는 무관 제외를
    #             끈 잡(params.exclude_off_topic=0)에서 무관하다고 본 수(켠 잡은 0). 보강 전 잡의 회차에는 없다.
```

- [ ] **Step 9: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py tests/test_research_critic.py tests/test_research_runner.py tests/test_research_api.py -q`
Expected: `271 passed`

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py`
Expected: `888 passed`. 옛 스냅샷 params에 키가 없으면 기본값 1로 되살아나는 것은 기존 `test_params_are_refilled_with_defaults`가 확인한다.

- [ ] **Step 10: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/state.py app/services/research/critic.py app/services/research/runner.py app/models/research.py app/tests/test_research_state.py app/tests/test_research_critic.py app/tests/test_research_runner.py app/tests/test_research_api.py
git commit -m "[Feat] round04c — 잡 파라미터 exclude_off_topic(0·1, 기본 1)으로 무관 제외를 재배포 없이 끈다: 끈 잡은 자기점검이 돌려준 번호로 근거를 빼지 않고 회차 기록·critique 이벤트의 flagged 에 무관하다고 본 수만 남겨(켠 잡은 0) 켠 잡과 나란히 비교한다. 보인 근거를 모두 무관하다면서 충분이라는 답을 부족으로 뒤집는 parse_verdict 규칙도 끈 잡에서는 쓰지 않는다 — 근거가 그대로 남아 판정이 본 근거가 있고, 뒤집으면 끈 잡만 재검색을 더 돌아 비교 기준(걸린 시간·근거 수)이 흐려진다. API 가 기본값에 합쳐 저장하므로 운영자는 params 로 0 만 넘긴다"
```

---

## 단계 2 — 화면 (Task 4~7)

- 백엔드 계약(단계 1): 회차 기록(`result.rounds[]`)과 `critique` 이벤트에 `excluded_papers`·`flagged`, `trail[]` 에 `excluded_papers`, counters·단계 result·보고서 `stats` 에 `excluded`. 이 단계는 그 이름을 그대로 읽는다. 백엔드와 파일이 겹치지 않아 단계 1 과 병렬로 돌릴 수 있다.
- 보강 전 잡·옛 워커는 새 칸을 보내지 않는다. 뷰는 빈 목록·`null` 로 받고, 화면은 그때 지금처럼 글자만("무관 N편 제외") 두거나 칸을 그리지 않는다.
- 문구는 한 곳에서 만든다. 회차 줄은 `excludedLabel`·`flaggedLabel`(researchEvents), 논문 한 줄은 `excludedPaperLine`, 섹션 제목·설명은 `EXCLUDED_TITLE`·`EXCLUDED_WHY`(researchReport). 타임라인·보고서·문서가 같이 쓴다.

### Task 4: 화면 타입·이벤트 합치기: 뺀 논문 서지, flagged, 카운터 제외 수

계약 추가: `types/research.ts` 에 `ExcludedPaper` 인터페이스(서버 모양 `{cnts_id, title?, personal_author?, pub_date?}`)와 `ExcludedPaperView` 인터페이스(뷰 모양 `{cntsId, title, personalAuthor, pubDate}`)를 둔다. `utils/researchEvents.ts` 에 `flaggedLabel(n)`·`toExcludedPaperView(p)` 를 둔다. `CritiqueEvent` 에 `excluded_papers?`·`flagged?` 를 더한다(Task 1·3 이 critique 이벤트에 싣는다). 점검 이벤트 합치기가 그 값으로 회차의 뺀 논문·flagged 를 바로 채우고, 뒤따르는 진행 저장 step 이벤트(`result.rounds`, `research_tasks._round_emitter`)가 같은 값으로 덮는다. 워커는 진행 저장에 실패하면 step 이벤트를 보내지 않으므로 점검 이벤트에서 바로 채워야 새로고침 전까지 목록을 펼칠 수 있다.

**Files:**
- Modify: `frontend/types/research.ts`
- Modify: `frontend/utils/researchEvents.ts`
- Test: `frontend/tests/unit/researchEvents.test.ts`
- Modify (새 필수 칸 때문에 typecheck 가 깨지는 곳만 고침): `frontend/tests/unit/researchDraft.test.ts`, `frontend/tests/unit/reportDocument.test.ts`

- [ ] **Step 1: 실패 테스트 작성, 기존 단언을 새 칸에 맞춤 (`frontend/tests/unit/researchEvents.test.ts`)**

타입 import 에 `CritiqueEvent` 를 더한다(점검 이벤트 테스트가 쓴다).

교체 전:
```ts
import type {
  ReportChunk,
```
교체 후:
```ts
import type {
  CritiqueEvent,
  ReportChunk,
```

import 에 `flaggedLabel` 를 더한다.

교체 전:
```ts
  excludedLabel,
  initialResearchView,
```
교체 후:
```ts
  excludedLabel,
  flaggedLabel,
  initialResearchView,
```

`LIVE_VIEW` 에 제외 칸을 더한다. 워커가 보낸 LIVE·SAVED 페이로드에는 excluded 가 없어서 null 이 된다.

교체 전:
```ts
const LIVE_VIEW = { papersReviewed: 26, evidenceAdopted: 7, rechecks: 1 };
```
교체 후:
```ts
const LIVE_VIEW = { papersReviewed: 26, evidenceAdopted: 7, rechecks: 1, excluded: null };
```

똑같은 줄이 두 곳 있다(127·149행). Edit 도구에서 `replace_all: true` 로 바꾼다.

교체 전:
```ts
    expect(v.counters).toEqual({ papersReviewed: 38, evidenceAdopted: 11, rechecks: 2 });
```
교체 후:
```ts
    expect(v.counters).toEqual({ papersReviewed: 38, evidenceAdopted: 11, rechecks: 2, excluded: null });
```

이 줄도 똑같은 것이 두 곳 있다(140·195행). `replace_all: true` 로 바꾼다.

교체 전:
```ts
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 7, rechecks: 1 });
```
교체 후:
```ts
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 7, rechecks: 1, excluded: null });
```

교체 전:
```ts
    expect(start.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 5, rechecks: 0 });
```
교체 후:
```ts
    expect(start.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 5, rechecks: 0, excluded: null });
```

교체 전:
```ts
    expect(v.counters).toEqual({ papersReviewed: 3, evidenceAdopted: 1, rechecks: 0 });
```
교체 후:
```ts
    expect(v.counters).toEqual({ papersReviewed: 3, evidenceAdopted: 1, rechecks: 0, excluded: null });
```

교체 전:
```ts
    expect(v.counters).toEqual({ papersReviewed: null, evidenceAdopted: 1, rechecks: 1 });
```
교체 후:
```ts
    expect(v.counters).toEqual({ papersReviewed: null, evidenceAdopted: 1, rechecks: 1, excluded: null });
```

교체 전:
```ts
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 5, rechecks: 0 });
```
교체 후:
```ts
    expect(v.counters).toEqual({ papersReviewed: 20, evidenceAdopted: 5, rechecks: 0, excluded: null });
```

교체 전:
```ts
    expect(v.counters).toEqual({ papersReviewed: 30, evidenceAdopted: 9, rechecks: 2 });
```
교체 후:
```ts
    expect(v.counters).toEqual({ papersReviewed: 30, evidenceAdopted: 9, rechecks: 2, excluded: null });
```

회차 전체를 비교하는 단언은 네 줄이다(167·168·782·783행). 모두 `excluded: null },` 로 끝나고 이 파일에서 이 네 곳에만 나온다. `replace_all: true` 로 바꾼다.

교체 전:
```ts
excluded: null },
```
교체 후:
```ts
excluded: null, excludedPapers: [], flagged: null },
```

counters 이벤트 테스트를 더한다. `it("counters 이벤트는 카운터를 통째로 바꾼다"` 바로 앞에 넣는다.

교체 전:
```ts
  it("counters 이벤트는 카운터를 통째로 바꾼다", () => {
```
교체 후:
```ts
  it("counters 이벤트의 excluded(모든 하위질문에서 뺀 수)를 싣고, 보내지 않는 옛 워커는 null 로 둔다", () => {
    expect(run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1, excluded: 3 }]).counters)
      .toEqual({ papersReviewed: 20, evidenceAdopted: 7, rechecks: 1, excluded: 3 });
    expect(run([{ kind: "counters", papers_reviewed: 20, evidence_adopted: 7, rechecks: 1 }]).counters.excluded).toBeNull();
  });

  it("counters 이벤트는 카운터를 통째로 바꾼다", () => {
```

회차 기록 테스트와 `flaggedLabel` 테스트를 더한다. "탐색" describe 끝과 `excludedLabel` describe 를 통째로 바꾼다.

교체 전:
```ts
    for (const v of [opened, snap]) {
      expect(v.subqs[0]!.rounds.map((r) => [r.round, r.excluded])).toEqual([[1, 2], [2, null]]);
    }
  });
});

describe("excludedLabel", () => {
  it("뺀 근거가 있을 때만 타임라인·문서 부록의 문구를 주고, 0·옛 잡(null)은 적지 않는다", () => {
    expect(excludedLabel(3)).toBe("무관 3편 제외");
    expect(excludedLabel(0)).toBeNull();
    expect(excludedLabel(null)).toBeNull();
  });
});
```
교체 후:
```ts
    for (const v of [opened, snap]) {
      expect(v.subqs[0]!.rounds.map((r) => [r.round, r.excluded])).toEqual([[1, 2], [2, null]]);
    }
  });

  // 자기점검이 무관하다고 뺀 논문의 서지(회차 기록) — 제목 앞뒤 공백은 화면에서 뗀다
  const EDGE_PAPER = { cnts_id: "C9", title: " CMOS 에지 검출 회로 ", personal_author: "박민수; 이영희", pub_date: "2008-05" };
  const EDGE_VIEW = { cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수; 이영희", pubDate: "2008-05" };

  it("진행 저장본 회차의 뺀 논문 서지·flagged 를 받고, 필드가 없는 옛 회차는 빈 목록·null 로 둔다", () => {
    const saved = step({
      ...SAVED_SEARCH_ROW,
      result: { rounds: [{ ...ROUND1, excluded: 1, flagged: 0, excluded_papers: [EDGE_PAPER] }, ROUND2], counters: LIVE },
    });
    const v = initialResearchView(job({ steps: [PLAN_ROW, saved] }));
    expect(v.subqs[0]!.rounds.map((r) => [r.round, r.excludedPapers, r.flagged])).toEqual([
      [1, [EDGE_VIEW], 0],
      [2, [], null],
    ]);
  });

  it("점검 이벤트가 이번 회차에 뺀 논문 서지·flagged 를 바로 싣고, 보내지 않는 옛 워커는 빈 목록·null 로 둔다", () => {
    // 점검 직후의 진행 저장이 실패하면 회차 기록을 실은 step 이벤트가 오지 않는다 — 점검 이벤트만으로 목록을 펼친다
    const searched: ResearchEvent[] = [
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
    ];
    const critique: CritiqueEvent = {
      kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 4,
      parse_failed: false, capped: 0, excluded: 1, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
    };
    const live = run([...searched, { ...critique, excluded_papers: [EDGE_PAPER], flagged: 0 }]);
    expect(live.subqs[0]!.rounds[0]).toMatchObject({ excluded: 1, excludedPapers: [EDGE_VIEW], flagged: 0 });
    // 뒤따르는 진행 저장 step 이벤트는 같은 회차 기록을 싣는다 — 받아도 그대로다
    const saved = applyResearchEvent(live, {
      ...SEARCH_STARTED,
      result: { rounds: [{ ...ROUND1, excluded: 1, flagged: 0, excluded_papers: [EDGE_PAPER] }], counters: SAVED },
    });
    expect(saved.subqs[0]!.rounds[0]).toMatchObject({ excluded: 1, excludedPapers: [EDGE_VIEW], flagged: 0 });
    expect(run([...searched, critique]).subqs[0]!.rounds[0]).toMatchObject({ excluded: 1, excludedPapers: [], flagged: null });
  });

  it("무관 제외를 끈 잡의 회차는 뺀 목록 없이 flagged(무관하다고만 본 수)를 싣는다", () => {
    const saved = step({
      ...SAVED_SEARCH_ROW,
      result: { rounds: [{ ...ROUND1, excluded: 0, flagged: 3, excluded_papers: [] }], counters: SAVED },
    });
    const r = initialResearchView(job({ steps: [PLAN_ROW, saved] })).subqs[0]!.rounds[0]!;
    expect([r.excluded, r.excludedPapers, r.flagged]).toEqual([0, [], 3]);
    expect(excludedLabel(r.excluded)).toBeNull();
    expect(flaggedLabel(r.flagged)).toBe("무관 의심 3편(제외 안 함)");
  });
});

describe("excludedLabel", () => {
  it("뺀 근거가 있을 때만 타임라인·문서 부록의 문구를 주고, 0·옛 잡(null)은 적지 않는다", () => {
    expect(excludedLabel(3)).toBe("무관 3편 제외");
    expect(excludedLabel(0)).toBeNull();
    expect(excludedLabel(null)).toBeNull();
  });
});

describe("flaggedLabel", () => {
  it("끈 잡이 무관하다고 본 수가 있을 때만 '제외 안 함'을 밝혀 적고, 0·옛 잡(null)은 적지 않는다", () => {
    expect(flaggedLabel(3)).toBe("무관 의심 3편(제외 안 함)");
    expect(flaggedLabel(0)).toBeNull();
    expect(flaggedLabel(null)).toBeNull();
  });
});
```

재접속 때 제외 수를 합치는 테스트를 더한다. `it("진행 저장 step 이벤트의 result.counters 로 뒤처진 카운터를 바로잡는다"` 바로 앞에 넣는다.

교체 전:
```ts
  it("진행 저장 step 이벤트의 result.counters 로 뒤처진 카운터를 바로잡는다", () => {
```
교체 후:
```ts
  it("탐색 중 재접속 — 제외 수는 줄지 않아 필드별 큰 값을 남긴다", () => {
    // 끊긴 사이 2회차 점검이 2편을 더 빼고 저장했다 — 검색 직후 받은 counters 는 1회차에 뺀 3편까지만 센다
    const live = run([...AWAITING_ROUND2_CRITIQUE.slice(0, -1), { kind: "counters", ...LIVE, excluded: 3 }]);
    const stored = { ...LIVE, evidence_adopted: 5, excluded: 5 };
    const v = applyResearchEvent(live, {
      kind: "snapshot",
      steps: [PLAN_ROW, step({ ...SAVED_SEARCH_ROW, result: { rounds: [ROUND1, ROUND2], counters: stored } })],
      job: { status: "running", stage: "planned", plan: ["효과 측정", "교사 인식"], counters: stored },
    });
    expect(v.counters.excluded).toBe(5);
  });

  it("진행 저장 step 이벤트의 result.counters 로 뒤처진 카운터를 바로잡는다", () => {
```

- [ ] **Step 2: 다른 테스트의 뷰 리터럴에 새 필수 칸을 더함 (typecheck)**

`frontend/tests/unit/researchDraft.test.ts`

교체 전:
```ts
      { counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 2 } },
```
교체 후:
```ts
      { counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 2, excluded: null } },
```
교체 전:
```ts
      { counters: { papersReviewed: null, evidenceAdopted: 3, rechecks: 0 } },
```
교체 후:
```ts
      { counters: { papersReviewed: null, evidenceAdopted: 3, rechecks: 0, excluded: null } },
```

`frontend/tests/unit/reportDocument.test.ts`

교체 전:
```ts
  return { round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null, excluded: null };
```
교체 후:
```ts
  return {
    round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null,
  };
```
교체 전:
```ts
    counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 1 },
```
교체 후:
```ts
    counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 1, excluded: null },
```

- [ ] **Step 3: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchEvents.test.ts`
Expected: FAIL — `Tests  21 failed | 68 passed (89)`. 새 테스트에서 `TypeError: (0 , flaggedLabel) is not a function` 가 나고 `excludedPapers`/`flagged` 가 undefined 로 어긋난다. 기존 카운터·회차 단언도 실제 값에 `excluded`·`excludedPapers`·`flagged` 칸이 없어서 toEqual 이 실패한다.

- [ ] **Step 4: 타입 (`frontend/types/research.ts`)**

교체 전:
```ts
  // 자기점검이 무관하다고 보고 이 회차에 뺀 근거 수 — 무관 제외 전 잡의 회차에는 없다
  excluded?: number | null;
}

// idx·status 뒤의 칸은
```
교체 후:
```ts
  // 자기점검이 무관하다고 보고 이 회차에 뺀 근거 수 — 무관 제외 전 잡의 회차에는 없다
  excluded?: number | null;
  // 이 회차에 뺀 논문의 서지 — 풀에서 지운 뒤에도 무엇을 뺐는지 남는다. 목록을 기록하기 전 잡에는 없다
  excluded_papers?: ExcludedPaper[] | null;
  // 무관 제외를 끈 잡(exclude_off_topic=0)이 빼지 않고 무관하다고만 본 수. 켠 잡은 0, 그 전 잡에는 없다
  flagged?: number | null;
}

// 자기점검이 무관하다고 보고 뺀 논문의 서지 요약(회차 기록·보고서 trail)
export interface ExcludedPaper {
  cnts_id: string;
  title?: string | null;
  personal_author?: string | null;
  pub_date?: string | null;
}

// idx·status 뒤의 칸은
```

교체 전:
```ts
  // 하위질문에서 무관하다고 뺀 근거 총수 — 무관 제외 전 보고서에는 없다
  excluded?: number | null;
}

export interface CountersPayload {
  papers_reviewed: number;
  evidence_adopted: number;
  rechecks: number;
}
```
교체 후:
```ts
  // 하위질문에서 무관하다고 뺀 근거 총수 — 무관 제외 전 보고서에는 없다
  excluded?: number | null;
  // 하위질문에서 뺀 논문 전체(회차 순·중복 없음) — 목록을 기록하기 전 보고서에는 없다
  excluded_papers?: ExcludedPaper[] | null;
}

export interface CountersPayload {
  papers_reviewed: number;
  evidence_adopted: number;
  rechecks: number;
  // 모든 하위질문에서 뺀 논문 수(두 하위질문이 같은 논문을 빼면 두 번 센다) — 무관 제외 전 잡에는 없다
  excluded?: number;
}
```

`CritiqueEvent` 에 회차 기록과 같은 두 칸을 더한다.

교체 전:
```ts
  // 이번 회차에 무관하다고 뺀 근거 수 — 무관 제외 전 워커는 보내지 않는다
  excluded?: number | null;
  round?: number;
```
교체 후:
```ts
  // 이번 회차에 무관하다고 뺀 근거 수 — 무관 제외 전 워커는 보내지 않는다
  excluded?: number | null;
  // 이번 회차에 뺀 논문의 서지와 무관 제외를 끈 잡이 무관하다고만 본 수 — 회차 기록(SearchRoundResult)과
  // 같은 값이다. 점검 직후 진행 저장이 실패해도 타임라인이 목록을 펼칠 수 있게 이벤트에도 싣는다
  excluded_papers?: ExcludedPaper[] | null;
  flagged?: number | null;
  round?: number;
```

교체 전:
```ts
  nextQuery: string | null;
  excluded: number | null;
}

export interface SubqView {
```
교체 후:
```ts
  nextQuery: string | null;
  excluded: number | null;
  // 뺀 논문 목록이 있는 회차만 타임라인에서 펼칠 수 있다 — 목록을 기록하기 전 회차는 빈 목록
  excludedPapers: ExcludedPaperView[];
  flagged: number | null;
}

export interface ExcludedPaperView {
  cntsId: string;
  // 제목이 없으면 빈 문자열
  title: string;
  personalAuthor: string | null;
  pubDate: string | null;
}

export interface SubqView {
```

교체 전:
```ts
export interface CountersView {
  papersReviewed: number | null;
  evidenceAdopted: number | null;
  rechecks: number | null;
}
```
교체 후:
```ts
export interface CountersView {
  papersReviewed: number | null;
  evidenceAdopted: number | null;
  rechecks: number | null;
  // 제외 수를 모르는 잡(무관 제외 전)은 null — 화면은 제외 칸을 그리지 않는다
  excluded: number | null;
}
```

- [ ] **Step 5: 이벤트 합치기 (`frontend/utils/researchEvents.ts`)**

교체 전:
```ts
  CritiqueEvent,
  HighlightView,
```
교체 후:
```ts
  CritiqueEvent,
  ExcludedPaper,
  ExcludedPaperView,
  HighlightView,
```

교체 전:
```ts
const EMPTY_COUNTERS: CountersView = { papersReviewed: null, evidenceAdopted: null, rechecks: null };
```
교체 후:
```ts
const EMPTY_COUNTERS: CountersView = { papersReviewed: null, evidenceAdopted: null, rechecks: null, excluded: null };
```

교체 전:
```ts
export function excludedLabel(n: number | null): string | null {
  return n ? `무관 ${n}편 제외` : null;
}
```
교체 후:
```ts
export function excludedLabel(n: number | null): string | null {
  return n ? `무관 ${n}편 제외` : null;
}

// 무관 제외를 끈 잡(exclude_off_topic=0)은 빼지 않고 무관하다고 본 수만 남긴다 — 켠 잡의 "제외"와
// 헷갈리지 않게 빼지 않았음을 문구에 밝힌다. 켠 잡(0)·그 전 잡(null)은 적지 않는다
export function flaggedLabel(n: number | null): string | null {
  return n ? `무관 의심 ${n}편(제외 안 함)` : null;
}
```

점검 이벤트가 싣는 목록·flagged 로 회차를 바로 채운다(`applyCritique`).

교체 전:
```ts
      nextQuery: event.next_query ?? null,
      excluded: event.excluded ?? null,
    };
```
교체 후:
```ts
      nextQuery: event.next_query ?? null,
      excluded: event.excluded ?? null,
      // 뒤따르는 진행 저장 step 이벤트의 회차 기록도 같은 값을 싣지만, 저장이 실패하면 오지 않는다 —
      // 점검 이벤트의 값으로 바로 채운다. 목록을 보내지 않는 옛 워커는 빈 목록·null
      excludedPapers: (event.excluded_papers ?? []).map(toExcludedPaperView),
      flagged: event.flagged ?? null,
    };
```

교체 전:
```ts
    nextQuery: i < last ? (queries[i + 1] ?? null) : null,
    excluded: null,
  }));
}
```
교체 후:
```ts
    nextQuery: i < last ? (queries[i + 1] ?? null) : null,
    excluded: null,
    excludedPapers: [],
    flagged: null,
  }));
}
```

교체 전:
```ts
function toRoundView(r: SearchRoundResult): RoundView {
  return {
    round: r.round,
    query: r.query,
    foundChunks: r.found_chunks ?? null,
    newPapers: r.new_papers ?? null,
    verdict: r.verdict ?? null,
    note: r.note ?? "",
    nextQuery: r.next_query ?? null,
    excluded: r.excluded ?? null,
  };
}

function blankRound(round: number): RoundView {
  return {
    round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null, excluded: null,
  };
}
```
교체 후:
```ts
// 뺀 논문의 서지 — 회차 기록(타임라인)과 보고서 trail(제외한 논문 섹션·문서 부록)이 같은 모양으로 받는다
export function toExcludedPaperView(p: ExcludedPaper): ExcludedPaperView {
  return {
    cntsId: p.cnts_id,
    title: p.title?.trim() ?? "",
    personalAuthor: p.personal_author ?? null,
    pubDate: p.pub_date ?? null,
  };
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
    excluded: r.excluded ?? null,
    excludedPapers: (r.excluded_papers ?? []).map(toExcludedPaperView),
    flagged: r.flagged ?? null,
  };
}

function blankRound(round: number): RoundView {
  return {
    round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null,
    excluded: null, excludedPapers: [], flagged: null,
  };
}
```

교체 전:
```ts
function countersFromPayload(p: CountersPayload): CountersView {
  return { papersReviewed: p.papers_reviewed, evidenceAdopted: p.evidence_adopted, rechecks: p.rechecks };
}
```
교체 후:
```ts
function countersFromPayload(p: CountersPayload): CountersView {
  return {
    papersReviewed: p.papers_reviewed,
    evidenceAdopted: p.evidence_adopted,
    rechecks: p.rechecks,
    excluded: p.excluded ?? null,
  };
}
```

교체 전:
```ts
// 라이브 카운터와 저장본(스냅샷·GET) 카운터를 합친다. 한 시도 안에서 검토한 논문·재검색은
// 줄지 않는다(research_stats 의 seen_cnts·queries 는 늘기만 한다). 저장본은 자기점검(LLM)이
```
교체 후:
```ts
// 라이브 카운터와 저장본(스냅샷·GET) 카운터를 합친다. 한 시도 안에서 검토한 논문·재검색·제외 수는
// 줄지 않는다(research_stats 의 seen_cnts·queries·회차 기록은 늘기만 한다). 저장본은 자기점검(LLM)이
```

교체 전:
```ts
    rechecks: larger(live.rechecks, stored.rechecks),
  };
}
```
교체 후:
```ts
    rechecks: larger(live.rechecks, stored.rechecks),
    excluded: larger(live.excluded, stored.excluded),
  };
}
```

교체 전:
```ts
    papersReviewed: null,
    evidenceAdopted: Object.keys(report.evidence ?? {}).length,
    rechecks: report.trail.reduce((n, t) => n + Math.max(0, t.queries.length - 1), 0),
  };
```
교체 후:
```ts
    papersReviewed: null,
    evidenceAdopted: Object.keys(report.evidence ?? {}).length,
    rechecks: report.trail.reduce((n, t) => n + Math.max(0, t.queries.length - 1), 0),
    excluded: null,
  };
```

- [ ] **Step 6: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: `Test Files  21 passed (21)`, `Tests  395 passed (395)`.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음.

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add frontend/types/research.ts frontend/utils/researchEvents.ts frontend/tests/unit/researchEvents.test.ts frontend/tests/unit/researchDraft.test.ts frontend/tests/unit/reportDocument.test.ts
git commit -m "[Feat] round04c — 화면이 회차의 뺀 논문 서지·끈 잡의 flagged·카운터의 제외 수를 받는다: 회차 기록과 점검 이벤트의 excluded_papers 를 뷰 모양(excludedPapers)으로 옮기고, 점검 이벤트가 싣는 값으로 회차를 바로 채워 진행 저장이 실패해도 목록을 펼칠 수 있게 한다. 카운터 합치기는 제외 수도 필드별 큰 값으로 남기고, 제외 수가 없는 옛 잡은 null 로 둔다"
```

---

### Task 5: 서론의 걸러낸 수 문구, 하위질문별 제외 목록 (최종본은 trail, 초안은 탐색 타임라인)

계약 추가: `utils/researchReport.ts` 에 `ExcludedGroup` 인터페이스(`{subqIdx, subquestion, papers: ExcludedPaperView[]}`), `excludedFromTrail(trail)`, `excludedFromSubqs(subqs)`, `excludedPaperLine(p)`, 상수 `EXCLUDED_TITLE`·`EXCLUDED_WHY` 를 둔다. `utils/researchDraft.ts` 의 `DraftReport` 에 `excluded: ExcludedGroup[]` 를 더한다.

**Files:**
- Modify: `frontend/utils/researchReport.ts`
- Modify: `frontend/utils/researchDraft.ts`
- Test: `frontend/tests/unit/researchReport.test.ts`, `frontend/tests/unit/researchDraft.test.ts`
- Modify (DraftReport 새 필수 칸 때문에 typecheck): `frontend/tests/unit/reportDocument.test.ts`

- [ ] **Step 1: 실패 테스트 작성 (`frontend/tests/unit/researchReport.test.ts`)**

교체 전:
```ts
import type { ResearchReport } from "~/types/research";
import type { DraftSlot } from "~/utils/researchDraft";
import {
  draftBadge,
  draftIntro,
  draftStateFor,
  hideOnPointerLeave,
```
교체 후:
```ts
import type { ExcludedPaperView, ResearchReport, RoundView, SubqView } from "~/types/research";
import type { DraftSlot } from "~/utils/researchDraft";
import {
  draftBadge,
  draftIntro,
  draftStateFor,
  excludedFromSubqs,
  excludedFromTrail,
  excludedPaperLine,
  hideOnPointerLeave,
```

교체 전:
```ts
  it("보강 전 보고서는 근거 수만 쓴다", () => {
```
교체 후:
```ts
  it("제외 수가 있으면 걸러낸 수를 덧붙이고, 0 이면(뺀 것 없음) 덧붙이지 않는다", () => {
    expect(reportIntro(report({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2, excluded: 5 } })))
      .toBe("하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다(무관한 5편은 걸러냈다).");
    expect(reportIntro(report({ stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2, excluded: 0 } })))
      .toBe("하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
  });

  it("보강 전 보고서는 근거 수만 쓴다", () => {
```

교체 전:
```ts
  it("멈춘 초안은 완성되지 않았음과 한계가 빠졌음을 알린다", () => {
```
교체 후:
```ts
  it("라이브 카운터에 제외 수가 있으면 걸러낸 수를 덧붙인다", () => {
    expect(draftIntro(slots, "writing", { ...stats, excluded: 4 }))
      .toBe("4개 절 중 2개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다. 지금까지 논문 38편을 검토하고 11편을 근거로 삼았습니다(무관한 4편은 걸러냈습니다).");
  });

  it("멈춘 초안은 완성되지 않았음과 한계가 빠졌음을 알린다", () => {
```

파일 끝(`describe("draftBadge", …)` 블록 뒤)에 더한다.

교체 전:
```ts
    expect(draftBadge("interrupted")).toEqual({ label: "완성되지 않은 초안", live: false });
  });
});
```
교체 후:
```ts
    expect(draftBadge("interrupted")).toEqual({ label: "완성되지 않은 초안", live: false });
  });
});

const C8: ExcludedPaperView = { cntsId: "C8", title: "의료영상 Edge method", personalAuthor: "최지훈", pubDate: "2011" };
const C9: ExcludedPaperView = { cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수; 이영희", pubDate: "2008-05" };

function round(n: number, papers: ExcludedPaperView[]): RoundView {
  return {
    round: n, query: `검색 ${n}`, foundChunks: 3, newPapers: 1, verdict: "insufficient", note: "", nextQuery: null,
    excluded: papers.length, excludedPapers: papers, flagged: 0,
  };
}

function subq(idx: number, title: string, rounds: RoundView[]): SubqView {
  return {
    idx, title, seq: idx + 1, status: "done", rounds,
    verdict: "sufficient", note: "", adopted: 3, parseFailed: false, error: null,
  };
}

describe("excludedFromTrail", () => {
  it("하위질문별로 뺀 논문을 묶고, 뺀 것이 없거나 목록을 기록하기 전인 하위질문은 뺀다", () => {
    const groups = excludedFromTrail([
      { subquestion: "가", queries: ["가"], evidence_count: 1, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0, excluded: 0, excluded_papers: [] },
      {
        subquestion: "엣지 컴퓨팅", queries: ["엣지 컴퓨팅"], evidence_count: 4, verdict: "sufficient", note: "",
        parse_failed: false, failed: false, capped: 0, excluded: 2,
        excluded_papers: [
          { cnts_id: "C8", title: "의료영상 Edge method", personal_author: "최지훈", pub_date: "2011" },
          { cnts_id: "C9", title: "CMOS 에지 검출 회로", personal_author: "박민수; 이영희", pub_date: "2008-05" },
        ],
      },
      // 무관 제외 전 보고서의 trail 에는 excluded_papers 가 없다
      { subquestion: "다", queries: ["다"], evidence_count: 0, verdict: "insufficient", note: "", parse_failed: false, failed: false, capped: 0 },
    ]);
    expect(groups).toEqual([{ subqIdx: 1, subquestion: "엣지 컴퓨팅", papers: [C8, C9] }]);
  });
});

describe("excludedFromSubqs", () => {
  it("초안은 탐색 타임라인의 회차 기록을 회차 순으로 이어 하위질문별로 묶고, 뺀 것이 없는 하위질문은 뺀다", () => {
    const groups = excludedFromSubqs([
      subq(0, "가", [round(1, [])]),
      subq(1, "엣지 컴퓨팅", [round(1, [C8]), round(2, []), round(3, [C9])]),
    ]);
    expect(groups).toEqual([{ subqIdx: 1, subquestion: "엣지 컴퓨팅", papers: [C8, C9] }]);
  });
});

describe("excludedPaperLine", () => {
  it("저자 외 (연도) 「제목」 으로 쓰고, 제목이 없으면 저자·연도만 쓴다", () => {
    expect(excludedPaperLine(C9)).toBe("박민수 외 (2008) 「CMOS 에지 검출 회로」");
    expect(excludedPaperLine({ cntsId: "C7", title: "", personalAuthor: null, pubDate: "2010" })).toBe("저자 미상 (2010)");
  });
});
```

- [ ] **Step 2: 실패 테스트 작성 (`frontend/tests/unit/researchDraft.test.ts`)**

교체 전:
```ts
  it("라이브 카운터가 하나라도 비면 stats 를 싣지 않는다", () => {
```
교체 후:
```ts
  it("초안의 제외한 논문은 탐색 타임라인(회차 기록)에서 만들고, stats 에는 라이브 카운터의 제외 수를 싣는다", () => {
    const explored = initialResearchView(job({
      steps: [{
        seq: 1, kind: "search", subq_idx: 1, title: "교사 인식", status: "done",
        result: {
          rounds: [{
            round: 1, query: "교사 인식", excluded: 1, flagged: 0,
            excluded_papers: [{ cnts_id: "C9", title: "CMOS 에지 검출 회로", personal_author: "박민수", pub_date: "2008" }],
          }],
        },
      }],
    }));
    const v = viewWith(
      { total: 1, sections: [sec(0, "done", { section: section("효과 측정") })] },
      { subqs: explored.subqs, counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 2, excluded: 1 } },
    );
    const d = draftReport(v)!;
    expect(d.excluded).toEqual([{
      subqIdx: 1,
      subquestion: "교사 인식",
      papers: [{ cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수", pubDate: "2008" }],
    }]);
    expect(d.report.stats).toEqual({ papers_reviewed: 38, evidence_adopted: 11, rechecks: 2, excluded: 1 });
  });

  it("라이브 카운터가 하나라도 비면 stats 를 싣지 않는다", () => {
```

- [ ] **Step 3: DraftReport 리터럴에 새 칸을 더함 (`frontend/tests/unit/reportDocument.test.ts`, typecheck)**

교체 전:
```ts
    done: 1,
    total: 3,
  };
  const v = view([
```
교체 후:
```ts
    done: 1,
    total: 3,
    excluded: [{
      subqIdx: 0,
      subquestion: "하위질문 1",
      papers: [{ cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수", pubDate: "2008" }],
    }],
  };
  const v = view([
```

- [ ] **Step 4: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchReport.test.ts tests/unit/researchDraft.test.ts`
Expected: FAIL — `Test Files  2 failed (2)`, `Tests  6 failed | 46 passed (52)`. `TypeError: (0 , excludedFromTrail) is not a function` 류 오류가 나고, 서론 문구에 `(무관한 5편은 걸러냈다)`·`(무관한 4편은 걸러냈습니다)` 가 붙지 않아 어긋난다. `d.excluded` 가 undefined 이고 `d.report.stats` 에 `excluded` 가 없다.

- [ ] **Step 5: 구현 (`frontend/utils/researchReport.ts`)**

교체 전:
```ts
import type { CountersPayload, EvidenceMeta, ReportRange, ResearchReport } from "../types/research";
import { pubYear, splitAuthors } from "./citations";
import type { DraftSlot } from "./researchDraft";
import type { ResearchPhase } from "./researchEvents";
```
교체 후:
```ts
import type {
  CountersPayload,
  EvidenceMeta,
  ExcludedPaperView,
  ReportRange,
  ResearchReport,
  SubqView,
  TrailItem,
} from "../types/research";
import { pubYear, splitAuthors } from "./citations";
import type { DraftSlot } from "./researchDraft";
import { toExcludedPaperView, type ResearchPhase } from "./researchEvents";
```

교체 전:
```ts
  if (s) {
    return `하위질문 ${subqs}개로 나눠 논문 ${s.papers_reviewed}편을 검토하고 ${s.evidence_adopted}편을 근거로 삼았다.`;
  }
  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
}
```
교체 후:
```ts
  if (s) {
    return `하위질문 ${subqs}개로 나눠 논문 ${s.papers_reviewed}편을 검토하고 ${s.evidence_adopted}편을 근거로 삼았다${droppedNote(s, "걸러냈다")}.`;
  }
  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
}

// 걸러낸 수를 서론에 덧붙인다 — 채택 수만 적으면 무관 제외로 결과가 줄어든 것처럼 읽힌다.
// 뺀 것이 없거나(0) 제외 수가 없는 잡(무관 제외 전)은 적지 않는다
function droppedNote(stats: CountersPayload, verb: string): string {
  return stats.excluded ? `(무관한 ${stats.excluded}편은 ${verb})` : "";
}
```

교체 전:
```ts
export const NO_LIMITS = "자동 점검에서 보고할 한계가 발견되지 않았습니다.";
```
교체 후:
```ts
export const NO_LIMITS = "자동 점검에서 보고할 한계가 발견되지 않았습니다.";
// 제외한 논문 목록의 제목·설명 — 보고서 화면의 접힌 섹션과 내려받은 문서의 부록이 같은 말을 쓴다
export const EXCLUDED_TITLE = "관련성이 낮아 제외한 논문";
export const EXCLUDED_WHY = "자기점검이 하위질문의 핵심 개념과 무관하다고 판단해 근거에서 뺀 논문입니다.";
```

교체 전:
```ts
  return `${head} ${upTo}논문 ${stats.papers_reviewed}편을 검토하고 ${stats.evidence_adopted}편을 근거로 삼았습니다.`;
```
교체 후:
```ts
  return `${head} ${upTo}논문 ${stats.papers_reviewed}편을 검토하고 ${stats.evidence_adopted}편을 근거로 삼았습니다${droppedNote(stats, "걸러냈습니다")}.`;
```

교체 전:
```ts
export function paperByline(meta: EvidenceMeta | undefined): string {
  const authors = splitAuthors(meta?.personal_author);
  const who = authors.length > 1 ? `${authors[0]} 외` : (authors[0] ?? "저자 미상");
  const year = pubYear(meta?.pub_date);
  return year ? `${who} (${year})` : who;
}
```
교체 후:
```ts
export function paperByline(meta: EvidenceMeta | undefined): string {
  const authors = splitAuthors(meta?.personal_author);
  const who = authors.length > 1 ? `${authors[0]} 외` : (authors[0] ?? "저자 미상");
  const year = pubYear(meta?.pub_date);
  return year ? `${who} (${year})` : who;
}

// 하위질문 하나에서 뺀 논문들. subqIdx 는 탐색 타임라인·부록의 하위질문 번호(0부터)다
export interface ExcludedGroup {
  subqIdx: number;
  subquestion: string;
  papers: ExcludedPaperView[];
}

// 최종본은 보고서 trail 에서 만든다. 뺀 논문이 없는 하위질문과 목록을 기록하기 전 보고서는 빠진다
export function excludedFromTrail(trail: TrailItem[]): ExcludedGroup[] {
  return trail
    .map((t, i) => ({
      subqIdx: i,
      subquestion: t.subquestion,
      papers: (t.excluded_papers ?? []).map(toExcludedPaperView),
    }))
    .filter((g) => g.papers.length > 0);
}

// 초안에는 trail 이 없다(종합이 끝나야 생긴다) — 탐색 타임라인의 회차 기록을 회차 순으로 이어 같은 목록을
// 만든다. 한 하위질문은 뺀 논문을 다시 넣지 않으므로 이어 붙여도 겹치지 않는다(최종본 trail 과 같다)
export function excludedFromSubqs(subqs: SubqView[]): ExcludedGroup[] {
  return subqs
    .map((sq) => ({ subqIdx: sq.idx, subquestion: sq.title, papers: sq.rounds.flatMap((r) => r.excludedPapers) }))
    .filter((g) => g.papers.length > 0);
}

// 뺀 논문 한 줄 — "저자 외 (연도) 「제목」". 타임라인·보고서·문서가 같이 쓴다
export function excludedPaperLine(p: ExcludedPaperView): string {
  const who = paperByline({ personal_author: p.personalAuthor, pub_date: p.pubDate });
  return p.title ? `${who} 「${p.title}」` : who;
}
```

- [ ] **Step 6: 구현 (`frontend/utils/researchDraft.ts`)**

교체 전:
```ts
import { isTerminalStatus } from "./researchEvents";
```
교체 후:
```ts
import { isTerminalStatus } from "./researchEvents";
import { excludedFromSubqs, type ExcludedGroup } from "./researchReport";
```

교체 전:
```ts
export interface DraftReport {
  report: ResearchReport;
  slots: DraftSlot[];
  done: number;
  total: number;
}
```
교체 후:
```ts
export interface DraftReport {
  report: ResearchReport;
  slots: DraftSlot[];
  done: number;
  total: number;
  // 하위질문별로 뺀 논문 — 초안에는 trail 이 없어 탐색 타임라인(회차 기록)에서 만든다
  excluded: ExcludedGroup[];
}
```

교체 전:
```ts
    done: sections.length,
    total: slots.length,
  };
}
```
교체 후:
```ts
    done: sections.length,
    total: slots.length,
    excluded: excludedFromSubqs(view.subqs),
  };
}
```

교체 전:
```ts
// 보고서 서론 한 줄(reportIntro)이 읽는 stats — 라이브 카운터가 셋 다 있을 때만 싣는다.
// 하나라도 비면(옛 잡) 서론은 근거 수만 쓰는 옛 문장으로 되돌아간다
function liveStats(c: CountersView): CountersPayload | null {
  if (c.papersReviewed === null || c.evidenceAdopted === null || c.rechecks === null) return null;
  return { papers_reviewed: c.papersReviewed, evidence_adopted: c.evidenceAdopted, rechecks: c.rechecks };
}
```
교체 후:
```ts
// 보고서 서론 한 줄(reportIntro)이 읽는 stats — 라이브 카운터가 셋 다 있을 때만 싣는다.
// 하나라도 비면(옛 잡) 서론은 근거 수만 쓰는 옛 문장으로 되돌아간다. 제외 수는 무관 제외 뒤 잡에만
// 있어 따로 붙인다 — 없으면 서론이 걸러낸 수를 적지 않는다
function liveStats(c: CountersView): CountersPayload | null {
  if (c.papersReviewed === null || c.evidenceAdopted === null || c.rechecks === null) return null;
  const stats: CountersPayload = { papers_reviewed: c.papersReviewed, evidence_adopted: c.evidenceAdopted, rechecks: c.rechecks };
  return c.excluded === null ? stats : { ...stats, excluded: c.excluded };
}
```

- [ ] **Step 7: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: `Test Files  21 passed (21)`, `Tests  401 passed (401)`.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음.

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add frontend/utils/researchReport.ts frontend/utils/researchDraft.ts frontend/tests/unit/researchReport.test.ts frontend/tests/unit/researchDraft.test.ts frontend/tests/unit/reportDocument.test.ts
git commit -m "[Feat] round04c — 보고서 서론에 걸러낸 수를 덧붙이고 제외한 논문 목록을 하위질문별로 묶는다: reportIntro·draftIntro 는 제외가 있으면 '(무관한 N편은 걸러냈다)'를 붙이고, 최종본은 trail 의 excluded_papers, 초안은 탐색 타임라인의 회차 기록에서 같은 목록(ExcludedGroup)을 만든다. 초안 stats 에 라이브 제외 수를 싣는다"
```

---

### Task 6: 내려받은 문서의 부록 뒤 "관련성이 낮아 제외한 논문" (참고문헌 번호 없음)

계약 추가: `utils/reportDocument.ts` 의 `ReportDocInput` 에 `excluded: ExcludedGroup[]` 를 더한다.

**Files:**
- Modify: `frontend/utils/reportDocument.ts`
- Test: `frontend/tests/unit/reportDocument.test.ts`

- [ ] **Step 1: 실패 테스트 작성 (`frontend/tests/unit/reportDocument.test.ts`)**

`input()` 헬퍼에 새 칸을 더한다.

교체 전:
```ts
    trail: [],
    draft: null,
    ...over,
```
교체 후:
```ts
    trail: [],
    excluded: [],
    draft: null,
    ...over,
```

교체 전:
```ts
  it("탐색 경로가 없으면 부록을 싣지 않는다", () => {
```
교체 후:
```ts
  it("제외한 논문은 탐색 경로 부록 뒤에 하위질문별로 싣고 참고문헌 번호를 매기지 않는다", () => {
    const doc = buildReportDocument(
      input({
        sections: [section({ heading: "엣지 컴퓨팅", intro: "자원을 나눈다 [E1]." })],
        evidence: { E1: ev("C1", { title: "엣지 자원 할당", personal_author: "김철수", pub_date: "2021" }) },
        trail: [{ subquestion: "엣지 컴퓨팅", queries: ["엣지 컴퓨팅"], verdict: "sufficient", evidenceCount: 1, excluded: 2 }],
        excluded: [{
          subqIdx: 0,
          subquestion: "엣지 컴퓨팅",
          papers: [
            { cntsId: "C8", title: "의료영상 Edge method", personalAuthor: "최지훈", pubDate: "2011" },
            { cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수; 이영희", pubDate: "2008-05" },
          ],
        }],
      }),
      NOW,
    );
    const all = lines(doc);
    expect(all.slice(all.indexOf("heading1: 부록: 탐색 경로"))).toEqual([
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 엣지 컴퓨팅",
      "bullets: 검색어: ‘엣지 컴퓨팅’ / 판정: 근거 충분 / 채택한 근거: 1편 / 무관 2편 제외",
      "heading1: 부록: 관련성이 낮아 제외한 논문",
      "para: 자기점검이 하위질문의 핵심 개념과 무관하다고 판단해 근거에서 뺀 논문입니다. 인용한 근거가 아니어서 참고문헌 번호를 매기지 않습니다.",
      "heading2: 1. 엣지 컴퓨팅",
      "bullets: 최지훈 (2011) 「의료영상 Edge method」 / 박민수 외 (2008) 「CMOS 에지 검출 회로」",
    ]);
    // 참고문헌은 본문이 인용한 근거뿐이다 — 뺀 논문은 글 조각으로만 적힌다
    expect(doc.references.map((r) => r.eid)).toEqual(["E1"]);
  });

  it("제외한 논문이 없으면 그 부록을 싣지 않는다", () => {
    const doc = buildReportDocument(
      input({ trail: [{ subquestion: "가", queries: ["가"], verdict: "sufficient", evidenceCount: 1, excluded: 0 }] }),
      NOW,
    );
    expect(lines(doc)).not.toContain("heading1: 부록: 관련성이 낮아 제외한 논문");
  });

  it("탐색 경로가 없으면 부록을 싣지 않는다", () => {
```

`docInputFromReport` describe 끝에 테스트를 더한다.

교체 전:
```ts
      limitations: ["한계"],
      draft: null,
    });
  });
});
```
교체 후:
```ts
      limitations: ["한계"],
      draft: null,
    });
  });

  it("제외한 논문은 보고서 trail 에서 하위질문별로 옮긴다", () => {
    const report: ResearchReport = {
      question: "q",
      range: null,
      sections: [],
      evidence: {},
      trail: [
        { subquestion: "가", queries: ["가"], evidence_count: 2, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0, excluded: 0, excluded_papers: [] },
        {
          subquestion: "엣지 컴퓨팅", queries: ["엣지 컴퓨팅"], evidence_count: 4, verdict: "sufficient", note: "",
          parse_failed: false, failed: false, capped: 0, excluded: 1,
          excluded_papers: [{ cnts_id: "C9", title: "CMOS 에지 검출 회로", personal_author: "박민수", pub_date: "2008" }],
        },
      ],
      limitations: [],
    };
    expect(docInputFromReport(report, { generatedAt: null, url: "" }).excluded).toEqual([
      { subqIdx: 1, subquestion: "엣지 컴퓨팅", papers: [{ cntsId: "C9", title: "CMOS 에지 검출 회로", personalAuthor: "박민수", pubDate: "2008" }] },
    ]);
  });
});
```

`docInputFromDraft` describe 에 테스트를 더한다.

교체 전:
```ts
  it("초안 문서는 제목·파일 이름에 초안임을 밝힌다", () => {
```
교체 후:
```ts
  it("제외한 논문은 화면의 초안과 같은 목록(탐색 타임라인에서 만든 draft.excluded)을 쓴다", () => {
    expect(docInputFromDraft(draft, v, "").excluded).toEqual(draft.excluded);
  });

  it("초안 문서는 제목·파일 이름에 초안임을 밝힌다", () => {
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/reportDocument.test.ts`
Expected: FAIL — `Tests  3 failed | 23 passed (26)`. `부록: 관련성이 낮아 제외한 논문` 블록이 없고, `docInputFromReport(...).excluded`·`docInputFromDraft(...).excluded` 가 undefined 다. 새 테스트 중 "제외한 논문이 없으면 그 부록을 싣지 않는다"는 아직 그 블록이 없어 이미 통과한다(구현 뒤에도 통과해야 하는 회귀 방지 테스트다).

- [ ] **Step 3: 구현 (`frontend/utils/reportDocument.ts`)**

교체 전:
```ts
import { INTROLESS, NO_LIMITS, NO_SUMMARY, paperByline, rangeLabel, reportIntro } from "./researchReport";
```
교체 후:
```ts
import {
  EXCLUDED_TITLE,
  EXCLUDED_WHY,
  INTROLESS,
  NO_LIMITS,
  NO_SUMMARY,
  excludedFromTrail,
  excludedPaperLine,
  paperByline,
  rangeLabel,
  reportIntro,
  type ExcludedGroup,
} from "./researchReport";
```

교체 전:
```ts
  trail: DocTrailItem[];
  draft: { done: number; total: number } | null;
}
```
교체 후:
```ts
  trail: DocTrailItem[];
  // 자기점검이 하위질문별로 뺀 논문 — 최종본은 report.trail, 초안은 화면과 같은 draft.excluded 에서 온다
  excluded: ExcludedGroup[];
  draft: { done: number; total: number } | null;
}
```

교체 전:
```ts
const DRAFT_LIMITS = "작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.";
const MISSING_EVIDENCE = "근거 정보를 찾을 수 없습니다";
```
교체 후:
```ts
const DRAFT_LIMITS = "작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.";
const MISSING_EVIDENCE = "근거 정보를 찾을 수 없습니다";
const EXCLUDED_NOT_CITED = "인용한 근거가 아니어서 참고문헌 번호를 매기지 않습니다.";
```

교체 전:
```ts
  blocks.push(...limitBlocks(input), ...trailBlocks(input.trail));
```
교체 후:
```ts
  blocks.push(...limitBlocks(input), ...trailBlocks(input.trail), ...excludedBlocks(input.excluded));
```

교체 전:
```ts
    trail: report.trail.map(docTrailItem),
    draft: null,
  };
}
```
교체 후:
```ts
    trail: report.trail.map(docTrailItem),
    excluded: excludedFromTrail(report.trail),
    draft: null,
  };
}
```

교체 전:
```ts
    trail: view.subqs.map(docTrailFromSubq),
    draft: { done: draft.done, total: draft.total },
```
교체 후:
```ts
    trail: view.subqs.map(docTrailFromSubq),
    excluded: draft.excluded,
    draft: { done: draft.done, total: draft.total },
```

교체 전:
```ts
    if (items.length) out.push({ type: "bullets", items });
  });
  return out;
}
```
교체 후:
```ts
    if (items.length) out.push({ type: "bullets", items });
  });
  return out;
}

// 탐색 경로 부록 뒤에 하위질문별로 싣는다. 인용이 아니라 글 조각으로만 적는다 — 참고문헌 번호가 붙으면
// 본문이 인용한 논문으로 읽힌다
function excludedBlocks(groups: ExcludedGroup[]): DocBlock[] {
  if (!groups.length) return [];
  const out: DocBlock[] = [
    { type: "heading", level: 1, text: `부록: ${EXCLUDED_TITLE}` },
    { type: "para", runs: [{ text: `${EXCLUDED_WHY} ${EXCLUDED_NOT_CITED}` }], muted: true },
  ];
  for (const g of groups) {
    out.push({ type: "heading", level: 2, text: `${g.subqIdx + 1}. ${g.subquestion}` });
    out.push({ type: "bullets", items: g.papers.map((p) => [{ text: excludedPaperLine(p) }]) });
  }
  return out;
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: `Test Files  21 passed (21)`, `Tests  405 passed (405)`. `reportDocx.test.ts`·`useReportExport.test.ts` 도 그대로 통과한다. 새 블록 종류가 없어서 Word·인쇄 렌더러는 바꾸지 않는다.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add frontend/utils/reportDocument.ts frontend/tests/unit/reportDocument.test.ts
git commit -m "[Feat] round04c — 내려받은 문서의 탐색 경로 부록 뒤에 '관련성이 낮아 제외한 논문'을 하위질문별로 싣는다: 인용한 근거가 아니라 글 조각으로만 적어 참고문헌 번호를 매기지 않는다. 최종본은 report.trail, 초안은 화면과 같은 draft.excluded 에서 만든다"
```

---

### Task 7: 화면: 타임라인 펼치기, 끈 잡 표시, 카운터 제외 칸, 보고서의 접힌 섹션

계약 추가: `ReportView` 의 `draft` prop 에 `excluded: ExcludedGroup[]` 를 더한다. CSS 클래스는 `rs-round__toggle`·`rs-round__excluded`·`rs-round__why`·`rs-caret`·`rs-excluded-list`·`rs-excluded`(`__title`·`__toggle`·`__body`·`__group`) 를 쓴다. 컴포넌트 단위 테스트 도구(@vue/test-utils)는 없다. vitest 환경이 node 이기 때문이다. 화면 로직은 Task 4~6 의 utils 테스트가 맡고, 이 태스크는 typecheck·build 로 검증한다.

**Files:**
- Modify: `frontend/components/research/ReportView.vue`
- Modify: `frontend/pages/research/[id].vue`
- Modify: `frontend/components/research/ProgressPanel.vue`
- Modify: `frontend/assets/css/research.css`

- [ ] **Step 1: ReportView 에 접힌 섹션 추가 (`frontend/components/research/ReportView.vue`)**

교체 전:
```vue
      <p v-else class="rs-muted">{{ NO_LIMITS }}</p>
    </section>
  </article>
</template>
```
교체 후:
```vue
      <p v-else class="rs-muted">{{ NO_LIMITS }}</p>
    </section>

    <!-- 자기점검이 걸러낸 논문을 버리지 않고 보인다 — 무엇을 왜 뺐는지 보여야 결과가 줄어든 것으로 읽히지 않는다.
         본문이 인용한 논문이 아니라 접어 둔다. 초안은 탐색 타임라인에서 같은 목록을 만든다 -->
    <section v-if="excluded.length" class="rs-excluded" aria-labelledby="rs-excluded-title">
      <h3 id="rs-excluded-title" class="rs-excluded__title">
        <button
          type="button"
          class="rs-excluded__toggle"
          :aria-expanded="excludedOpen"
          aria-controls="rs-excluded-body"
          @click="excludedOpen = !excludedOpen"
        >
          {{ EXCLUDED_TITLE }} ({{ excludedCount }})<span class="rs-caret" aria-hidden="true">▾</span>
        </button>
      </h3>
      <div v-show="excludedOpen" id="rs-excluded-body" class="rs-excluded__body">
        <p class="rs-muted">{{ EXCLUDED_WHY }}</p>
        <div v-for="g in excluded" :key="g.subqIdx" class="rs-excluded__group">
          <h4 class="rs-section__sub">{{ g.subqIdx + 1 }}. {{ g.subquestion }}</h4>
          <ul class="rs-excluded-list">
            <li v-for="p in g.papers" :key="p.cntsId">
              <a :href="`/papers/${p.cntsId}`" target="_blank" rel="noopener">
                {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </section>
  </article>
</template>
```

교체 전:
```ts
import { computed } from "vue";
import type { OpenPdfPayload, ReportSection, ResearchReport } from "~/types/research";
import type { DraftSlot, DraftSlotStatus } from "~/utils/researchDraft";
import { NO_LIMITS, draftBadge, draftIntro, rangeLabel, reportIntro, type DraftState } from "~/utils/researchReport";
```
교체 후:
```ts
import { computed, ref } from "vue";
import type { OpenPdfPayload, ReportSection, ResearchReport } from "~/types/research";
import type { DraftSlot, DraftSlotStatus } from "~/utils/researchDraft";
import {
  EXCLUDED_TITLE,
  EXCLUDED_WHY,
  NO_LIMITS,
  draftBadge,
  draftIntro,
  excludedFromTrail,
  excludedPaperLine,
  rangeLabel,
  reportIntro,
  type DraftState,
  type ExcludedGroup,
} from "~/utils/researchReport";
```

교체 전:
```ts
    draft?: { slots: DraftSlot[]; state: DraftState } | null;
```
교체 후:
```ts
    draft?: { slots: DraftSlot[]; state: DraftState; excluded: ExcludedGroup[] } | null;
```

교체 전:
```ts
    sec: slot.sectionIndex !== null ? (sections[slot.sectionIndex] ?? null) : null,
  }));
});
</script>
```
교체 후:
```ts
    sec: slot.sectionIndex !== null ? (sections[slot.sectionIndex] ?? null) : null,
  }));
});

// 최종본은 보고서 trail 에서, 초안은 탐색 타임라인에서 만든 목록이다(초안에는 trail 이 없다)
const excluded = computed<ExcludedGroup[]>(() =>
  props.draft ? props.draft.excluded : excludedFromTrail(props.report.trail),
);
const excludedCount = computed(() => excluded.value.reduce((n, g) => n + g.papers.length, 0));
// 초안이 같은 자리에서 최종본으로 바뀌어도 이 부품은 그대로라 펼친 상태가 이어진다
const excludedOpen = ref(false);
</script>
```

- [ ] **Step 2: 실패 확인 (페이지가 새 prop 을 넘기지 않음)**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: `pages/research/[id].vue` 의 `:draft="draftMode"` 자리에서 오류 한 줄 — `pages/research/[id].vue(104,20): error TS2322: Type '{ slots: DraftSlot[]; state: DraftState; } | null' is not assignable to type '{ slots: DraftSlot[]; state: DraftState; excluded: ExcludedGroup[]; } | null | undefined'.`

- [ ] **Step 3: 페이지가 초안 목록을 넘김 (`frontend/pages/research/[id].vue`)**

교체 전:
```ts
const draftMode = computed(() => {
  const state = draftState.value;
  return draft.value && state ? { slots: draft.value.slots, state } : null;
});
```
교체 후:
```ts
const draftMode = computed(() => {
  const state = draftState.value;
  return draft.value && state ? { slots: draft.value.slots, state, excluded: draft.value.excluded } : null;
});
```

- [ ] **Step 4: 진행 패널에 카운터 제외 칸, 회차 펼치기, 끈 잡 표시 추가 (`frontend/components/research/ProgressPanel.vue`)**

교체 전:
```vue
        <div class="rs-counter">
          <dt>채택한 근거</dt>
          <dd>{{ shown(view.counters.evidenceAdopted) }}</dd>
        </div>
```
교체 후:
```vue
        <div class="rs-counter">
          <dt>채택한 근거</dt>
          <dd>{{ shown(view.counters.evidenceAdopted) }}</dd>
        </div>
        <!-- 자기점검이 걸러낸 수 — 채택 수만 보이면 무관 제외로 결과가 줄어든 것처럼 읽힌다. 제외 수를 모르는 옛 잡은 칸을 그리지 않는다 -->
        <div v-if="view.counters.excluded !== null" class="rs-counter">
          <dt>제외</dt>
          <dd>{{ shown(view.counters.excluded) }}</dd>
        </div>
```

교체 전:
```vue
                <span v-if="excludedLabel(r.excluded)" class="rs-round__stat">{{ excludedLabel(r.excluded) }}</span>
              </p>
```
교체 후:
```vue
                <!-- 뺀 논문 목록이 있으면 눌러 펼친다. 목록 없이 수만 있는 회차(목록을 기록하기 전 잡)는 글자만 둔다 -->
                <button
                  v-if="r.excludedPapers.length"
                  type="button"
                  class="rs-round__toggle"
                  :aria-expanded="isOpen(sq.idx, r.round)"
                  :aria-controls="panelId(sq.idx, r.round)"
                  @click="toggleRound(sq.idx, r.round)"
                >
                  {{ excludedLabel(r.excludedPapers.length) }}<span class="rs-caret" aria-hidden="true">▾</span>
                </button>
                <span v-else-if="excludedLabel(r.excluded)" class="rs-round__stat">{{ excludedLabel(r.excluded) }}</span>
                <span v-if="flaggedLabel(r.flagged)" class="rs-round__stat">{{ flaggedLabel(r.flagged) }}</span>
              </p>
              <div
                v-if="r.excludedPapers.length"
                v-show="isOpen(sq.idx, r.round)"
                :id="panelId(sq.idx, r.round)"
                class="rs-round__excluded"
              >
                <p class="rs-round__why">
                  자기점검이 이 하위질문의 핵심 개념과 무관하다고 판단했습니다<span v-if="r.note"> — {{ r.note }}</span>
                </p>
                <ul class="rs-excluded-list">
                  <li v-for="p in r.excludedPapers" :key="p.cntsId">
                    <a :href="`/papers/${p.cntsId}`" target="_blank" rel="noopener">
                      {{ excludedPaperLine(p) }}<span class="rs-sr-only"> (새 창)</span>
                    </a>
                  </li>
                </ul>
              </div>
```

교체 전:
```ts
import { computed } from "vue";
import type { ResearchView } from "~/types/research";
import {
  excludedLabel,
  stopPoint,
```
교체 후:
```ts
import { computed, shallowRef, useId } from "vue";
import type { ResearchView } from "~/types/research";
import {
  excludedLabel,
  flaggedLabel,
  stopPoint,
```

교체 전:
```ts
  type ResearchPhase,
} from "~/utils/researchEvents";

const props = defineProps<{ view: ResearchView; phase: ResearchPhase }>();
```
교체 후:
```ts
  type ResearchPhase,
} from "~/utils/researchEvents";
import { excludedPaperLine } from "~/utils/researchReport";

const props = defineProps<{ view: ResearchView; phase: ResearchPhase }>();
```

교체 전:
```ts
function shown(n: number | null): string {
  return n === null ? "—" : n.toLocaleString("ko-KR");
}
</script>
```
교체 후:
```ts
function shown(n: number | null): string {
  return n === null ? "—" : n.toLocaleString("ko-KR");
}

// 펼친 회차("하위질문:회차"). 이벤트가 올 때마다 타임라인이 다시 그려져도 사용자가 펼친 회차는 펼친 채로 둔다.
// 집합을 통째로 바꿔 알리므로 깊은 반응성은 필요 없다
const openRounds = shallowRef(new Set<string>());
const uid = useId();

function roundKey(subqIdx: number, round: number): string {
  return `${subqIdx}:${round}`;
}

function isOpen(subqIdx: number, round: number): boolean {
  return openRounds.value.has(roundKey(subqIdx, round));
}

function toggleRound(subqIdx: number, round: number): void {
  const next = new Set(openRounds.value);
  const key = roundKey(subqIdx, round);
  if (!next.delete(key)) next.add(key);
  openRounds.value = next;
}

function panelId(subqIdx: number, round: number): string {
  return `${uid}-excluded-${subqIdx}-${round}`;
}
</script>
```

- [ ] **Step 5: 스타일 (`frontend/assets/css/research.css`)**

카운터 칸 수가 3~4 로 바뀌므로 있는 칸끼리 폭을 나눈다.

교체 전:
```css
.rs-counters {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
  margin: 0;
}
```
교체 후:
```css
.rs-counters {
  display: grid;
  /* 칸 수가 잡마다 다르다(제외 칸은 무관 제외 뒤 잡에만 있다) — 있는 칸끼리 폭을 똑같이 나눈다 */
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  gap: 0.4rem;
  margin: 0;
}
```

교체 전:
```css
.rs-counter dt {
  font-size: 0.55rem;
  color: var(--skx-gray-1);
}
```
교체 후:
```css
.rs-counter dt {
  font-size: 0.55rem;
  color: var(--skx-gray-1);
  /* 네 칸이면 좁은 진행 패널에서 "검토한 논문"이 줄바꿈된다 — 글자 중간이 아니라 띄어쓰기에서 끊는다 */
  word-break: keep-all;
}
```

"보고서 초안" 절의 reduced-motion 블록 바로 뒤에 새 절을 넣는다.

교체 전:
```css
  .rs-badge--live::before,
  .rs-report--draft .rs-section__body,
  .rs-skeleton__line {
    animation: none;
  }
}
```
교체 후:
```css
  .rs-badge--live::before,
  .rs-report--draft .rs-section__body,
  .rs-skeleton__line {
    animation: none;
  }
}

/* ── 무관 제외 ─────────────────────────────────────────── */
/* 회차 줄의 "무관 N편 제외 ▾"와 보고서의 접힌 섹션 머리. 눌러 펼친다는 게 보이게 글자색·밑줄로 버튼임을 드러낸다 */
.rs-round__toggle,
.rs-excluded__toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0;
  font-family: inherit;
  font-size: inherit;
  color: var(--skx-primary);
  background: none;
  border: none;
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-round__toggle {
  text-decoration: underline dotted;
  text-underline-offset: 0.15em;
}
.rs-round__toggle:focus-visible,
.rs-excluded__toggle:focus-visible {
  outline: 2px solid var(--skx-border-c2);
  outline-offset: 2px;
}
.rs-caret {
  display: inline-block;
  font-size: 0.8em;
  transition: transform 0.15s ease;
}
[aria-expanded="true"] > .rs-caret {
  transform: rotate(180deg);
}
.rs-round__excluded {
  margin-top: 0.25rem;
  padding: 0.4rem 0.5rem;
  background: color-mix(in srgb, var(--skx-border-c1) 35%, var(--skx-white));
  border-radius: var(--skx-radius-sm);
  animation: rs-reveal 0.2s ease-out;
}
.rs-round__why {
  color: var(--skx-gray-1);
}
.rs-excluded-list {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin: 0.3rem 0 0;
  padding-left: 1rem;
}
.rs-excluded-list a {
  color: var(--skx-ink);
  text-decoration: none;
}
.rs-excluded-list a:hover,
.rs-excluded-list a:focus-visible {
  color: var(--skx-primary);
  text-decoration: underline;
}
/* 한계 섹션(실선·강조색)과 구분되게 점선 — 본문이 인용한 논문이 아니다 */
.rs-excluded {
  padding: 0.8rem 1rem;
  border: 1px dashed var(--skx-line);
  border-radius: var(--skx-radius-md);
}
.rs-excluded__title {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 700;
}
.rs-excluded__toggle {
  font-weight: inherit;
  color: var(--skx-ink-2);
}
.rs-excluded__body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.5rem;
  animation: rs-reveal 0.25s ease-out;
}
.rs-excluded .rs-excluded-list {
  font-size: 0.65rem;
  line-height: 1.7;
}
@media (prefers-reduced-motion: reduce) {
  .rs-caret {
    transition: none;
  }
  .rs-round__excluded,
  .rs-excluded__body {
    animation: none;
  }
}
```

- [ ] **Step 6: 통과 확인**

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run`
Expected: `Test Files  21 passed (21)`, `Tests  405 passed (405)`(이 태스크는 테스트를 더하지 않는다).

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"`
Expected: 출력 없음.

Run: `cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1`
Expected: `└  ✨ Build complete!`

화면 확인(선택): 로컬은 운영 API 프록시(`NUXT_DEV_API_TARGET`)가 있어야 한다. 없으면 배포 뒤 운영 비교 잡(spec §11-4)에서 다음을 본다.
- 회차 줄 "무관 N편 제외 ▾" 가 Tab·Enter/Space 로 열리고 닫히는지, 스크린리더에 aria-expanded 가 읽히는지
- 논문을 누르면 새 창으로 `/papers/<cnts_id>` 가 열리는지
- `exclude_off_topic: 0` 잡에서 "무관 의심 N편(제외 안 함)" 으로 보이는지
- 카운터가 4칸인지
- 보고서 한계 뒤에 접힌 섹션이 있는지, 작성 중 초안에도 같은 섹션이 있는지

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add frontend/components/research/ReportView.vue "frontend/pages/research/[id].vue" frontend/components/research/ProgressPanel.vue frontend/assets/css/research.css
git commit -m "[Feat] round04c — 탐색 타임라인·보고서에서 제외한 논문을 펼쳐 본다: 회차 줄의 '무관 N편 제외 ▾' 버튼(aria-expanded)이 뺀 논문 목록(새 창 링크)과 그 회차의 판단을 펼치고, 끈 잡은 '무관 의심 N편(제외 안 함)'으로 적는다. 카운터에 제외 칸(옛 잡은 없음), 보고서 한계 뒤에 접힌 '관련성이 낮아 제외한 논문 (N)' 섹션(초안은 탐색 타임라인 데이터)을 두고, 펼침 움직임은 prefers-reduced-motion 이면 끈다"
```

---

## 단계 3 — 최종 확인

### Task 8: 최종 확인

**Files:**
- Modify: `docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md` (3행 머리 상태 줄)

- [ ] **Step 1: 백엔드 전체 테스트**

`app/` 에서 전체를 돈다. 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 죽는 3개 파일만 뺀다(이 계획과 무관 — 기준선도 같은 명령으로 잰 값이다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `888 passed`(경고 2건은 기존 것, 기준선 865). 대상 파일만 다시 보면 `test_research_state.py` 70, `test_research_runner.py` 71, `test_research_synthesizer.py` 110, `test_research_critic.py` 62, `test_research_tasks.py` 93, `test_research_api.py` 68 이다.

- [ ] **Step 2: 프론트 전체 테스트·타입검사·빌드**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1
```
기대 출력:
- vitest: `Test Files  21 passed (21)`, `Tests  405 passed (405)`(기준선 389).
- typecheck: 출력 없음.
- build: `└  ✨ Build complete!`. 빌드 로그 중간의 `[DEP0155] DeprecationWarning`(`@vue/shared` 의 exports 패턴)은 기존 소음이다.

- [ ] **Step 3: 커밋 저자·트레일러 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git log --format='%h %an <%ae> %s' b84ce41..HEAD
git log --format=%B b84ce41..HEAD | grep -ciE "co-authored-by|generated with claude"
```
기대:
- 첫 명령: 계획 문서 커밋(`[Docs] round04c — §11 보완 구현 계획`)과 Task 1~7 커밋 7개가 모두 저장소 사용자(`git config user.name` — Hyonii) 이름으로 나온다. 그 사이에 다른 커밋(리뷰 반영 수정 커밋 등)이 끼었으면 그것도 같은 저자여야 한다.
- 둘째 명령: `0`.
- 하나라도 트레일러가 나오면 멈추고 사용자에게 알린다. 이미 쌓인 커밋의 메시지를 고치려면 사용자 승인 아래 비대화형 rebase 가 필요하다(이 계획에서는 하지 않는다).

- [ ] **Step 4: spec 머리 상태 줄 갱신**

`docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md` 3행을 Edit 도구로 고친다(원래 줄바꿈 LF 유지). §11 은 상태 줄을 쓴 뒤에 더해져 지금 줄은 §11 까지 구현된 것으로 읽힌다.

교체 전:
```markdown
> 상태: 설계 확정(2026-09-29, 사용자 승인) · 구현 완료(운영 배포 전)
```
교체 후:
```markdown
> 상태: 설계 확정(2026-09-29, 사용자 승인) · 구현 완료(운영 배포 전) · §11 보완 구현 완료(운영 배포 전)
```

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md
git commit -m "[Docs] round04c — spec 상태에 §11 보완 구현 완료(운영 배포 전)를 적는다: 제외한 논문의 서지 기록과 타임라인·보고서·문서 표시, 카운터·서론의 제외 수, 잡 파라미터 exclude_off_topic(끈 잡은 flagged 만 기록) 구현, 백엔드 전체 pytest·프론트 vitest·타입검사·빌드 통과"
```

- [ ] **Step 6: 남은 일 알리기(이 계획에서 실행하지 않는다)**

사용자에게 다음을 알린다.
- 운영 배포(spec §9·§11-3): 도는 딥리서치 잡 확인 → fastapi 이미지 빌드·푸시 → `nl-lib-fastapi`(잡 파라미터를 합쳐 저장한다)·`nl-lib-celery-research`·`nl-lib-celery-research-plan` Recreate(적재 워커는 건드리지 않는다, fastapi 재시작 전 `idle in transaction` 세션 확인 — recurring-gotchas 18번) → nuxt 이미지 → `nl-lib-nuxt` Recreate → `docker exec nl-lib-gateway nginx -s reload`. 공유 운영 서버라 **사용자 승인 뒤** 한다.
- 배포 뒤 운영 합격 기준(spec §11-4): 기준 잡(2026-09-29 10:20, "컴퓨팅 자원에 대한 연구가 궁금해", 6절 27편)과 같은 질문을 기본 파라미터로, 가능하면 `exclude_off_topic: 0` 잡도 하나 돌려 셋을 나란히 본다 — 보고서 논문 27편 이상, 핵심 하위질문(자원 관리·할당) 근거가 2편보다 늘어남, 걸린 시간 1.5배 이내, 같은 단어·다른 뜻 논문이 절 본문에서 빠지고 "제외한 논문"에 보임. spec §11-4 의 비교 쿼리를 쓴다.
- 어긋나면 제외 기준 문구를 "명백히 무관한 것만"으로 좁히거나(`research_critique.yaml`) 잡 파라미터로 끈다(spec §11-3 의 curl).
- 라운드 마무리(완료노트·교본·dev 머지)는 라운드 종료 절차(`GIT_WORKFLOW.md`, `.claude/skills/round-finish/SKILL.md`)를 따른다.

---

## 이 계획에서 다루지 않는 것

- 운영 배포와 운영 합격 기준 비교(spec §9·§11-4) — 사용자 승인 뒤 따로 한다.
- 화면에서 `exclude_off_topic` 을 켜고 끄는 입력(spec §11-3 — 운영자가 API 로 끈다).
- critic 이 논문마다 제외 이유를 쓰게 하기(spec §11-1 — 출력 토큰·파싱 위험). 화면은 그 회차의 note 를 함께 보인다.
- 제외 기준 문구 조정(`research_critique.yaml`) — 운영 합격 기준에서 어긋날 때 한다.
- spec 의 D(핵심 요약·주제 종합)·E(이어서 물어보기)·F(화면 참고문헌), 리랭커 점수 하한, 하위질문 사이 근거 재배분(spec §8).
- DB 구조·워커·fastapi 코드 변경.
