# 딥리서치 보고서 품질 구현 계획 (round04c)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영 보고서("컴퓨팅 자원에 대한 연구가 궁금해")를 DBpia 답변과 비교해 드러난 내용 품질 문제를 고친다. 네 가지를 한다.
- A: 하위질문마다 근거 몫을 둔다(`max_evidence // 하위질문 수`, 기본 상한 60→90). 보고서 `evidence` 에는 절에 실린 근거만 싣는다.
- B: 자기점검(critic)이 무관한 근거의 번호를 돌려주면 러너가 그 하위질문에서 뺀다. 탐색 타임라인과 문서 부록에 "무관 N편 제외"를 보인다.
- C: 계획 프롬프트가 원 질문의 핵심 개념 안에서 하위질문을 나누게 한다.
- G: 종합 서술과 자기점검 note 를 '~다' 문어체로 맞춘다. 한계 문장은 두 상한을 구분하고, 주어 조사를 받침에 맞춘다.

**Architecture:**
- 백엔드는 `app/services/research/` 의 네 모듈과 프롬프트 yaml 3개를 고친다.
  - `state.py`: 새 필드는 `research_jobs.state_snapshot`(JSONB) 안에서만 는다. 옛 스냅샷은 기본값으로, 근거 번호는 가장 큰 번호로 되살린다.
  - `runner.py`: 예산, 무관 제외, `evidence_seq` 번호.
  - `critic.py`: 목록 번호와 `off_topic` 해석.
  - `synthesizer.py`: 한계 문장, 보고서 `evidence`, `trail`.
- DB 스키마·워커(`research_tasks.py`)·API 는 바꾸지 않는다. 워커는 `subq.rounds` 와 `critique` 이벤트 payload 를 그대로 저장·중계한다.
- 프론트는 타입과 이벤트 합치기가 새 필드 `excluded` 를 통과시킨다. 문구는 `excludedLabel` 한 곳에서 만들고, 진행 패널 회차 줄과 문서 부록이 같이 쓴다.
- 순수 로직은 pytest·Vitest 로 검증하고, 컴포넌트는 typecheck·build 로 본다.

**Tech Stack:** FastAPI · SQLAlchemy 2(async) · Celery · pytest / Nuxt 4 · Vue 3.5 · TypeScript(strict·`noUncheckedIndexedAccess`) · Vitest 3.2 · 프롬프트는 gemma 대상 Jinja yaml(`services.prompts.get_prompt`)

**설계 근거:** `docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md`(이하 spec) 전체(A·B·C·G). 화면 맥락은 round04b spec `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` 의 §6(진행 패널)·§7-4(인터랙티브함)·§14(문서 부록).

**실행 전 확인:**
- `docs/ops/recurring-gotchas.md` 13번: torch 를 끌어오는 모듈은 함수 안에서 import 한다(로컬 `app/.venv` 에 torch·DB·Redis 가 없다. 테스트는 대역으로 돈다).
- 같은 문서 15번: gemma 는 프롬프트 예시의 개수·분야를 베낀다. 그래서 새 규칙에 예시를 넣지 않고, `off_topic` 예시는 빈 배열만 보인다.
- 운영 배포와 운영 전후 비교(spec §7·§9)는 이 계획 밖이다. 공유 운영 서버라 **사용자 승인 뒤** 따로 한다.
- 인덱싱 코드(`app/services/ingestion/`, `app/workers/tasks.py`, `app/workers/job_runtime.py`)는 건드리지 않는다.

**계획 작성 시 검증:** 이 문서의 코드 블록을 저장소 밖 사본(`git archive 738bc07` 의 `app/`·`frontend/`·`scripts/`·spec)에 Task 1→12 순서로 기계적으로 적용하고, 각 Step 의 명령을 그대로 돌렸다.
- "교체 전" 문자열 117개는 모두 그 시점의 대상 파일에서 한 곳씩만 맞았다.
- 각 태스크의 "실패 확인"·"통과 확인" 출력은 이 사본의 실측이다. 백엔드는 780 → 837 passed, 프론트는 21파일 / 383 → 387 passed 다. `nuxi typecheck` 는 오류 0 이고(Task 10 Step 7 의 한 줄을 빼면 `TS2741` 이 나는 것도 확인했다), `npm run build` 는 `Build complete!` 다.
- 초안을 따로 쓴 두 태스크 묶음이 만나는 곳(Task 1 의 예산 ↔ Task 8 의 제외)은 이 순서로 적용해 검증했다. 조립 때 더한 것은 세 가지다. 모두 위 검증에 들어 있다.
  - Task 8: 막혔던 후보가 빈 자리에 실리면 막힌 수에서 뺀다(`discard`, 테스트 1개).
  - Task 10: 카운터 합치기(`reconcileCounters`)와 `roundsFromQueries` 의 주석.
  - Task 11: `queryPath` 의 주석.
- 검토 때 HEAD(`f8f8a3d`) 의 임시 git worktree 에 Task 1→12 를 다시 기계적으로 적용해 같은 결과를 얻었다. "교체 전" 117개가 모두 한 곳씩 맞고, 각 Step 의 실패·통과 수와 위 누적 기대치, 백엔드 837 passed · 프론트 21 / 387 passed · typecheck 오류 0 · `Build complete!` 가 같았다. 검토에서 고친 두 곳(Task 6 의 프롬프트 한 줄과 테스트 단언 하나, Task 10 의 카운터 주석 순서)도 같은 방법으로 다시 적용해 수치가 그대로임을 확인했다.
- 확인하지 못한 것: 실제 LLM(gemma)이 새 프롬프트 규칙을 따르는지, 운영 데이터에서 무관 제외가 얼마나 걸러내는지, 실제 화면. 운영 전후 비교(spec §7)가 방어선이다.

---

## 테스트 명령

**백엔드** — `app/` 에서 돈다.

```bash
cd app && python -m pytest tests/<파일> -q
cd app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```

- 로컬 `app/.venv` 에는 pytest 가 없어서 PATH 의 `python` 으로 돌린다.
- 전체 실행에서 뺀 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 실패한다(이 계획과 무관).
- 각 Step 의 명령은 서브에이전트의 작업 디렉터리가 매번 초기화되므로 절대 경로(`cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && …`)로 적었다.

**프론트** — `frontend/` 에서 돈다.

```bash
cd frontend && npx vitest run tests/unit/<이름>.test.ts   # 한 파일
cd frontend && npx vitest run                              # 전체
cd frontend && npx nuxi typecheck 2>&1 | grep "error TS"   # 출력이 없어야 한다
cd frontend && npm run build 2>&1 | tail -1                # └  ✨ Build complete!
```

- Vitest 는 `environment: "node"` 로 `tests/unit/**/*.test.ts` 만 돈다. 컴포넌트 마운트 도구는 없다. 컴포넌트는 typecheck·build 로 본다.
- `[Vue] Resolve plugin path failed …` 줄은 typecheck 의 기존 소음이다. `grep "error TS"` 에 걸리지 않는다.

**누적 기대치** — 기준선은 `738bc07` 에서 잰 값이다. 이 문서의 태스크 순서대로 적용했을 때의 값이다(`test_research_planner.py` 는 Task 5 에서 15 → 16, `test_research_tasks.py` 는 92 그대로).

| 태스크 뒤 | `test_research_state.py` | `test_research_runner.py` | `test_research_synthesizer.py` | `test_research_critic.py` | 백엔드 전체 | 프론트 파일 / tests |
|---|---|---|---|---|---|---|
| 기준선 | 51 | 38 | 91 | 29 | 780 | 21 / 383 |
| Task 1 | 53 | 47 | 91 | 29 | 791 | — |
| Task 2 | 53 | 47 | 101 | 29 | 801 | — |
| Task 3 | 53 | 47 | 103 | 29 | 803 | — |
| Task 4 | 53 | 47 | 105 | 30 | 806 | — |
| Task 5 | 53 | 47 | 105 | 30 | 807 | — |
| Task 6 | 53 | 47 | 105 | 41 | 818 | — |
| Task 7 | 60 | 48 | 105 | 41 | 826 | — |
| Task 8 | 60 | 56 | 105 | 43 | 836 | — |
| Task 9 | 60 | 56 | 106 | 43 | **837** | — |
| Task 10 | — | — | — | — | — | 21 / 386 |
| Task 11 | — | — | — | — | — | **21 / 387** |

## 커밋 규칙

- 메시지는 `[Feat] round04c — …` 처럼 대괄호 접두사(`[Feat]`·`[Fix]`·`[Test]`·`[Docs]`)와 한국어로 쓴다. 태스크 하나 = 커밋 하나다. 각 Step 의 `git commit -m "…"` 을 그대로 쓴다.
- **`Co-Authored-By`·"Generated with Claude Code" 같은 트레일러를 절대 붙이지 않는다**(사용자 단독 저자).
- `git add` 는 그 태스크의 파일만 적는다. 착수 때부터 수정돼 있던 `frontend/pages/research/[id].vue` 는 이 계획의 파일이 아니므로 add 하지 않는다.
- 파일 첫 줄의 경로 주석은 있는 파일이면 그대로 둔다. 코드 주석은 "왜"를 한국어로, 과하지 않게 쓰고 태스크 번호를 적지 않는다. 기존 이름을 재사용하고, 일어날 수 없는 상황을 방어하지 않는다(`docs/standards/coding-standard.md`).
- 줄바꿈은 파일마다 다르다(`core.autocrlf=true`). 작업 트리에서 `app/` 파일(yaml 포함)은 CRLF, `frontend/`·`docs/` 파일은 LF 다. 기존 파일은 **Edit 도구로 고쳐** 원래 줄바꿈을 유지한다.
- push·브랜치 전환·rebase·reset·stash·amend 는 하지 않는다.
- "교체 전" 코드는 착수 시점(`feat/round04c-research-quality`, `738bc07`)의 파일에서 그대로 복사했다. 앞 태스크가 같은 파일을 고쳤으면 줄이 밀리므로 줄 번호가 아니라 "교체 전" 문자열로 찾는다.

---

## 파일 구조

| 파일 | 책임 | Task |
|---|---|---|
| `app/services/research/state.py` | `max_evidence` 기본값 90 · `SubQuestion.budget_capped`(1) · `ResearchState.evidence_seq`·`SubQuestion.excluded_cnts`·스냅샷 저장/복원(7) · 회차 이력 주석(8) | 1·7·8 |
| `app/services/research/runner.py` | `subq_budget`·예산 적용·몫을 다 쓰면 재검색 중단(1) · `evidence_seq` 로 번호 매기기(7) · `_exclude_off_topic`·뺀 논문 건너뛰기·`excluded` 기록·이벤트(8) | 1·7·8 |
| `app/services/research/critic.py` | 목록 `[n]` 번호·`Verdict.off_topic`·`parse_verdict(listed)`·`_off_topic`(6) · `should_recheck(emptied)`(8) | 6·8 |
| `app/services/research/synthesizer.py` | `_topic`·`_capped_clause`·한계 문장(2) · `_cited`·보고서 `evidence` 는 절에 실린 근거만(3) · `trail[].excluded`(9) | 2·3·9 |
| `app/models/research.py` | step result 모양 주석만(스키마 그대로) | 8 |
| `app/domains/nl_library/prompts/research_synthesize.yaml` | '~다' 문어체 규칙, JSON 예시 문체 | 4 |
| `app/domains/nl_library/prompts/research_critique.yaml` | note 문체(4) · `off_topic` 예시·설명(6) | 4·6 |
| `app/domains/nl_library/prompts/research_plan.yaml` | 핵심 개념·측면·핵심어 규칙 | 5 |
| `app/tests/test_research_state.py` · `test_research_runner.py` · `test_research_synthesizer.py` · `test_research_critic.py` · `test_research_planner.py` | 백엔드 테스트(기존 파일에 추가) | 1~9 |
| `frontend/types/research.ts` | 회차 결과·`critique` 이벤트·`TrailItem` 의 `excluded?`, `RoundView.excluded` | 10 |
| `frontend/utils/researchEvents.ts` | `excludedLabel`, 회차 합치기가 `excluded` 통과, 카운터 합치기 주석 | 10 |
| `frontend/components/research/ProgressPanel.vue` | 회차 줄 "무관 N편 제외" | 10 |
| `frontend/utils/reportDocument.ts` | `DocTrailItem.excluded`, 부록 문구, 검색어 경로 주석 | 11 |
| `frontend/tests/unit/researchEvents.test.ts` · `reportDocument.test.ts` | 프론트 단위 테스트 | 10·11 |
| `docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md` | 머리 상태 줄 → 구현 완료(운영 배포 전) | 12 |

워커(`app/workers/research_tasks.py`)·fastapi(`app/api/research.py`)·DB 스키마는 건드리지 않는다. 워커는 `subq.rounds` 를 단계 result 에 복사하고 `critique` 이벤트 payload 를 그대로 중계하므로 `excluded` 가 저절로 실린다.

---

## 실행 순서

| 단계 | 태스크 | 선행·병렬 |
|---|---|---|
| 1 | Task 1 → 2 → 3 → 4 → 5 (예산·한계 문장·보고서·문체·계획) | Task 1→2→3 은 같은 파일을 차례로 고친다. Task 4·5 는 로직으로는 독립이지만 Task 4 가 `test_research_synthesizer.py` 를 같이 고치므로 번호 순으로 한다 |
| 2 | Task 6 → 7 → 8 → 9 (무관 제외 백엔드) | Task 8 은 Task 1 의 `subq_budget`·`made`·`own`, Task 6 의 `Verdict.off_topic`, Task 7 의 `excluded_cnts`·`evidence_seq` 를 쓴다 |
| 3 | Task 10 → 11 (화면) | 백엔드와 파일이 겹치지 않아 단계 1·2 와 **병렬 가능**. Task 11 은 Task 10 의 `excludedLabel`·`RoundView.excluded` 를 쓴다 |
| 4 | Task 12 (최종 확인) | 전부 뒤 |

**병렬로 돌릴 때(같은 작업 트리)**:
- 커밋은 한 번에 하나씩 한다. 커밋 직전에 `git status --short` 로 스테이징에 자기 파일만 있는지 본다.
- "누적 기대치"의 전체 수는 태스크 번호 순서대로 적용했을 때의 값이다. 병렬 중에는 다른 태스크가 테스트만 먼저 써 둔 상태가 섞여 전체 수가 다를 수 있다. 각 태스크는 자기 테스트 파일로 확인하고, 전체 수는 Task 12 에서 본다.
- `npm run build`·`npx nuxi typecheck` 는 `.nuxt`·`.output` 을 함께 쓴다. 두 태스크가 동시에 돌리지 않는다.

---

## 공유 계약 (정본)

태스크 사이에서 주고받는 이름·모양이다. 태스크 코드는 이 목록과 일치하도록 맞췄다.

### 백엔드

- `state.py`
  - `DEFAULT_PARAMS["max_evidence"] = 90`(`_PARAM_BOUNDS` 상한 200 그대로) — Task 1.
  - `SubQuestion.budget_capped: int = 0` — 하위질문당 몫 때문에 채택하지 못한 후보 수. 전체 상한 때문인 `capped` 와 따로 센다 — Task 1.
  - `SubQuestion.excluded_cnts: list[str] = field(default_factory=list)` — 자기점검이 무관하다고 뺀 논문(cnts_id) — Task 7.
  - `ResearchState.evidence_seq: int = 0` — 다음 근거 번호 인덱스. `evidence_id(evidence_seq)` 로 쓰고 1 늘린다 — Task 7.
  - 스냅샷: `budget_capped`·`excluded_cnts` 는 `asdict` 로 저절로 실리고 복원은 dataclass 기본값(0·[])이 채운다. `evidence_seq` 는 `snapshot_state` 에 손으로 싣고, 없는 옛 스냅샷은 `_restored_evidence_seq` 가 기존 근거 번호 최댓값(`E<n>` 의 n) 또는 0 으로 되살린다 — Task 7.
- `runner.py`
  - `def subq_budget(state: ResearchState) -> int` = `max(min_evidence_per_subq, max_evidence // max(1, len(subquestions)))` — Task 1.
  - 비공개: `_recheck_query(state, subq, verdict, *, recheck: int, own: int)` — `own` 은 이 하위질문이 만들었고 지금 `subq.evidence_ids` 에 남아 있는 근거 수(Task 1). `explore_subquestion` 의 지역 변수 `made: set[str]`(이 하위질문이 새로 만든 근거 id)·`budget_capped: set[str]`·`budget`(Task 1). 예산은 spec §3 대로 "지금 이 하위질문에 남아 있는, 이 하위질문이 만든 근거 수"로 센다 — 후보 루프는 회차 시작 때 `len(made & before)`, 재검색 검사는 `len(made.intersection(subq.evidence_ids))`.
  - 비공개: `_exclude_off_topic(state, subq, numbers: list[int]) -> int` — 뺀 수. 반드시 `_recheck_query` 호출 앞에서 `subq.evidence_ids` 를 줄인다. 그래야 비운 자리가 예산·전체 상한으로 돌아온다 — Task 8.
  - 회차 기록 `subq.rounds[]` 와 `critique` 이벤트에 `"excluded": int`(이번 회차에 뺀 수) — Task 8.
- `critic.py`
  - `Verdict.off_topic: list[int] = field(default_factory=list)` — 1부터 세는 목록 번호 — Task 6.
  - `format_evidence_list` 가 `"[1] 제목 (연도) — 발췌"` 로 번호를 붙인다. 잘린 나머지는 번호 없이 `"…외 N편"` — Task 6.
  - `parse_verdict(raw, *, listed: int = 0)` — `listed` 는 번호를 붙여 보인 근거 수. 비공개 `_off_topic(raw, listed) -> list[int]` — Task 6.
  - `should_recheck(subq, *, recheck_count, max_recheck, emptied: bool = False)` — 무관 근거를 빼고 0편이면 판정과 무관하게 재검색 대상 — Task 8.
  - 프롬프트 JSON 예시에 `"off_topic": []`(예시는 빈 배열만) — Task 6.
- `synthesizer.py`
  - `def _topic(text: str) -> str` — 한계 문장의 `'…' 는`/`'…' 은`/`'…' (은)는` 조각 — Task 2.
  - 비공개 `_capped_clause(state, sq, noun) -> str` — "하위질문당 근거 상한(N편)" 과 "전체 근거 상한(M편)" 을 따로 적는다 — Task 2.
  - 비공개 `_cited(state, section) -> list[str]` — 다듬은 절 하나가 인용한 근거 번호. `assemble_report` 의 `evidence` 는 절에 나온 근거만 담고 `section_evidence` 도 이 헬퍼를 쓴다 — Task 3.
  - `trail[]` 에 `"excluded": int`(하위질문에서 뺀 총수 = `len(sq.excluded_cnts)`) — Task 9.

### 프론트

- `types/research.ts`: `SearchRoundResult.excluded?`·`CritiqueEvent.excluded?`·`TrailItem.excluded?` 는 `number | null`, `RoundView.excluded: number | null`(필수 칸) — Task 10.
- `utils/researchEvents.ts`: `export function excludedLabel(n: number | null): string | null` — `n > 0` 이면 `"무관 N편 제외"`, 0·null 이면 `null` — Task 10.
- `components/research/ProgressPanel.vue`: 회차 줄 `rs-round__stat` 에 `excludedLabel(r.excluded)`(있을 때만) — Task 10.
- `utils/reportDocument.ts`: `DocTrailItem.excluded: number`(최종본은 `trail[].excluded ?? 0`, 초안은 회차 `excluded` 합). 부록은 `excludedLabel` 로 같은 문구를 쓴다 — Task 11.

---

## 단계 1 — 예산·한계 문장·보고서·문체·계획 (Task 1~5)

- 범위는 spec 의 A(하위질문별 근거 예산, 한계 문구에서 두 상한 구분), Q3(보고서 `evidence`), G(문체 규칙과 `_topic`), C(계획 프롬프트)다.
- Task 1 → 2 → 3 은 같은 파일을 차례로 고치므로 번호 순으로 한다. Task 4·5 는 로직으로는 따로 들어가도 된다.
- 근거 번호를 매기는 줄 `evidence_id(len(state.evidence))` 는 Task 1 에서 그대로 두고, Task 7 이 `evidence_seq` 로 바꾼다.

### Task 1: 하위질문별 근거 예산 — 기본값 90, budget_capped, subq_budget, 예산 적용, 재검색 중단

**계약 추가(비공개 이름, Task 8 과 맞물린다):**
- `runner._recheck_query(state, subq, verdict, *, recheck: int, own: int)`: `own` 은 이 하위질문이 만들었고 지금 `subq.evidence_ids` 에 남아 있는 근거 수다.
- `explore_subquestion` 안의 지역 변수 `made: set[str]` 에 이 하위질문이 새로 만든 근거 id 를 모은다.
- 예산은 spec §3 대로 "지금 이 하위질문에 남아 있는, 이 하위질문이 만든 근거 수"로 센다. 그래서 호출 시점에 `len(made.intersection(subq.evidence_ids))` 로 다시 계산한다.
- Task 8 의 무관 제외는 반드시 `_recheck_query` 호출 앞에서 `subq.evidence_ids` 를 줄여야 한다. 그래야 비운 자리가 예산으로 돌아온다.

**Files:**
- Modify: `app/services/research/state.py`
- Modify: `app/services/research/runner.py`
- Test: `app/tests/test_research_state.py`
- Test: `app/tests/test_research_runner.py`
- Test: `app/tests/test_research_synthesizer.py` — 기본값 변경에 따른 기대값 한 줄(60편 → 90편)

- [ ] **Step 1: 상태 쪽 실패 테스트 작성**

`app/tests/test_research_state.py` 의 `_explored_state` 픽스처를 고친다.

교체 전:
```python
                    verdict="sufficient", note="충분하다", capped=3,
```
교체 후:
```python
                    verdict="sufficient", note="충분하다", capped=3, budget_capped=2,
```

`app/tests/test_research_state.py` 의 `TestSnapshotRoundTrip` 에 테스트를 넣는다.

교체 전:
```python
    def test_chunk_scores_survive(self):
```
교체 후:
```python
    def test_budget_capped_survives(self):
        # 떨어지면 재개한 잡의 한계 문장이 하위질문당 몫에 막힌 후보를 잃는다
        back = restore_state("j1", snapshot_state(_explored_state()))
        assert [s.budget_capped for s in back.subquestions] == [2, 0, 0]

    def test_chunk_scores_survive(self):
```

`app/tests/test_research_state.py` 의 `TestSnapshotEvolution` 에 테스트를 넣는다.

교체 전:
```python
    def test_unknown_chunk_key_is_ignored(self):
```
교체 후:
```python
    def test_old_snapshot_without_budget_capped_gets_zero(self):
        # 몫이 생기기 전 스냅샷 — 그때는 전체 상한만 있었으니 몫에 막힌 후보는 0 이다
        snap = snapshot_state(_explored_state())
        for sq in snap["subquestions"]:
            del sq["budget_capped"]
        assert [s.budget_capped for s in restore_state("j1", snap).subquestions] == [0, 0, 0]

    def test_unknown_chunk_key_is_ignored(self):
```

`app/tests/test_research_synthesizer.py` 의 `test_capped_subquestion_is_not_reported_as_missing_evidence` 는 기본값을 90 으로 바꾸므로 기대값만 고친다.

교체 전:
```python
        assert "근거 상한(60편)" in line and "7편" in line
```
교체 후:
```python
        assert "근거 상한(90편)" in line and "7편" in line
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py -q
```
기대 출력: `TypeError: SubQuestion.__init__() got an unexpected keyword argument 'budget_capped'` 가 나오고 `25 failed, 28 passed` 로 끝난다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_synthesizer.py -q
```
기대 출력: `FAILED tests/test_research_synthesizer.py::TestBuildLimitations::test_capped_subquestion_is_not_reported_as_missing_evidence` 가 나오고 `1 failed, 90 passed` 로 끝난다.

- [ ] **Step 3: state.py 구현**

`app/services/research/state.py`

교체 전:
```python
    "max_evidence": 60,
```
교체 후:
```python
    # 하위질문 6개면 몫이 15편(runner.subq_budget) — 첫 검색(보통 8~10편) 뒤에도 재검색이 보탤 자리가 남는다
    "max_evidence": 90,
```

교체 전:
```python
    capped: int = 0
```
교체 후:
```python
    capped: int = 0
    # 하위질문당 몫(runner.subq_budget) 때문에 채택하지 못한 후보 논문 수. capped 와 따로 세는
    # 이유는 풀리는 방법이 달라서다 — 몫은 하위질문을 줄이면 커지고, 전체 상한은 max_evidence 를 올려야 풀린다.
    budget_capped: int = 0
```

`snapshot_state` 는 `asdict` 로 담고 `restore_state` 는 `_known_fields` 와 dataclass 기본값을 쓴다. 그래서 스냅샷 코드는 고치지 않는다.

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py tests/test_research_synthesizer.py -q
```
기대 출력: `144 passed` (state 53 + synthesizer 91).

- [ ] **Step 5: 러너 쪽 실패 테스트 작성**

`app/tests/test_research_runner.py` 의 import 를 고친다.

교체 전:
```python
from services.research.runner import explore_subquestion
```
교체 후:
```python
from services.research.runner import explore_subquestion, subq_budget
```

`app/tests/test_research_runner.py` 에서 `TestEvidenceCap` 뒤, relay 테스트 앞에 클래스 두 개를 넣는다.

교체 전:
```python
_RELAY = "services.research.relay"
```
교체 후:
```python
class TestSubqBudget:
    """하위질문 하나가 새로 만들 수 있는 근거 수 — 전체 상한을 하위질문 수로 나눈 몫."""

    def _state(self, n, **params):
        st = ResearchState(job_id="j", question="q", params=merge_params(params))
        st.subquestions = [SubQuestion(idx=i, text=f"하위{i}") for i in range(n)]
        return st

    def test_default_share_for_six_subquestions_is_fifteen(self):
        # 60 이면 10편씩이라 첫 검색(보통 8~10편)만으로 몫이 차 자기점검의 재검색이 헛돈다
        assert subq_budget(self._state(6)) == 15

    def test_share_is_floor_divided(self):
        assert subq_budget(self._state(12)) == 7

    def test_share_below_minimum_is_raised_to_minimum(self):
        assert subq_budget(self._state(12, max_evidence=50)) == 5

    def test_single_subquestion_gets_the_whole_pool(self):
        assert subq_budget(self._state(1)) == 90

    def test_dropping_subquestions_enlarges_the_rest(self):
        # 계획에서 하위질문을 지우면 남은 하위질문의 몫이 저절로 커진다
        assert subq_budget(self._state(3)) == 30


class TestEvidenceBudget:
    """하위질문은 제 몫까지만 근거를 새로 만든다 — 먼저 탐색한 하위질문이 풀을 독식하지 못한다."""

    def _state(self, *texts, **params):
        st = ResearchState(job_id="j", question="q",
                           params=merge_params({"max_recheck": 0, **params}))
        st.subquestions = [SubQuestion(idx=i, text=t) for i, t in enumerate(texts)]
        return st

    def _explore(self, table):
        async def _explore(query, *, params, db):
            return _hits(table.get(query, []), query=query)
        return _explore

    def _run(self, st, table):
        for sq in st.subquestions:
            asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=self._explore(table),
                                            critique_fn=_FakeCritic(), emit=None))

    def test_subquestion_stops_creating_at_its_share(self):
        # 운영에서 먼저 탐색한 HPC 가 60편 중 32편을 가져가 핵심 하위질문은 2편에 그쳤다
        st = self._state("가", "나", max_evidence=4, min_evidence_per_subq=1)
        self._run(st, {"가": ["A", "B", "C"], "나": ["D"]})
        first, second = st.subquestions
        assert len(first.evidence_ids) == 2
        assert (first.budget_capped, first.capped) == (1, 0)
        assert len(second.evidence_ids) == 1

    def test_reused_evidence_does_not_use_up_the_share(self):
        # 이미 있는 근거에 링크하는 것은 전체 풀을 늘리지 않는다
        st = self._state("가", "나", max_evidence=4, min_evidence_per_subq=1)
        self._run(st, {"가": ["A", "B"], "나": ["A", "B", "C", "D"]})
        second = st.subquestions[1]
        assert sorted(st.evidence[e].cnts_id for e in second.evidence_ids) == ["A", "B", "C", "D"]
        assert second.budget_capped == 0

    def test_share_and_global_cap_are_counted_apart(self):
        # 최솟값이 몫을 끌어올려 몫의 합이 전체 상한을 넘으면 전체 상한이 먼저 막는다
        st = self._state("가", "나", max_evidence=3, min_evidence_per_subq=2)
        self._run(st, {"가": ["A", "B", "C"], "나": ["D", "E", "F"]})
        first, second = st.subquestions
        assert (first.budget_capped, first.capped) == (1, 0)
        assert (second.budget_capped, second.capped) == (0, 2)

    def test_no_recheck_once_the_share_is_used_up(self):
        # 전체 풀은 남아 있어도 이 하위질문은 더 만들 수 없다 — 재검색은 검색·LLM 호출만 태운다
        st = self._state("가", "나", max_evidence=4, min_evidence_per_subq=1, max_recheck=3)
        critic = _FakeCritic()
        asyncio.run(explore_subquestion(
            st, st.subquestions[0], db=None, explore_fn=self._explore({"가": ["A", "B", "C"]}),
            critique_fn=critic, emit=None,
        ))
        assert critic.calls == 1
        assert st.subquestions[0].queries == ["가"]
        assert len(st.evidence) == 2


_RELAY = "services.research.relay"
```

- [ ] **Step 6: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_runner.py -q
```
기대 출력: `ImportError: cannot import name 'subq_budget' from 'services.research.runner'` 가 나오고 `1 error during collection` 으로 끝난다.

- [ ] **Step 7: runner.py 구현**

`app/services/research/runner.py`

교체 전:
```python
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
```
교체 후:
```python
def subq_budget(state: ResearchState) -> int:
    """하위질문 하나가 새로 만들 수 있는 근거 수.

    전체 상한을 선착순으로 쓰면 먼저 탐색한 하위질문이 풀을 독식한다(운영에서 HPC 가 60편 중
    32편, 질문의 핵심인 하위질문은 2편). 몫은 기존 두 파라미터로만 정한다 — 계획에서 하위질문을
    지우면 남은 하위질문의 몫이 저절로 커진다.
    """
    params = state.params
    return max(params["min_evidence_per_subq"],
               params["max_evidence"] // max(1, len(state.subquestions)))


def _recheck_query(
    state: ResearchState, subq: SubQuestion, verdict: Verdict, *, recheck: int, own: int,
) -> str | None:
    """다음 회차에 검색할 검색어. 재검색하지 않으면 None.

    own 은 이 하위질문이 만들어 지금 갖고 있는 근거 수다(몫을 쓰는 쪽).
    """
    params = state.params
    if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"]):
        return None
    # 전체 상한이나 이 하위질문의 몫에 닿으면 새 근거가 생길 수 없다 — 재검색은 검색·LLM 호출만 태운다.
    if len(state.evidence) >= params["max_evidence"] or own >= subq_budget(state):
        return None
    return _next_query(verdict.new_queries, subq.queries)
```

교체 전:
```python
    relevance: dict[str, float] = {}
    leaders: list[str] = []
    capped: set[str] = set()
```
교체 후:
```python
    relevance: dict[str, float] = {}
    leaders: list[str] = []
    capped: set[str] = set()
    budget_capped: set[str] = set()
    budget = subq_budget(state)
    # 이 하위질문이 새로 만든 근거. 몫은 이 중 지금 subq.evidence_ids 에 남은 것으로 센다 —
    # 재사용 링크는 전체 풀을 늘리지 않으니 몫을 쓰지 않고, 하위질문에서 빠진 근거는 자리를 돌려준다.
    made: set[str] = set()
```

교체 전:
```python
        before = set(subq.evidence_ids)
        linked: list[str] = []
```
교체 후:
```python
        before = set(subq.evidence_ids)
        own = len(made & before)
        linked: list[str] = []
```

교체 전:
```python
                # break 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다.
                if len(state.evidence) >= params["max_evidence"]:
                    capped.add(cand.cnts_id)
                    continue
                eid = evidence_id(len(state.evidence))
                state.evidence[eid] = Evidence(id=eid, cnts_id=cand.cnts_id, meta=cand.meta)
                known_by_cnts[cand.cnts_id] = eid
```
교체 후:
```python
                # break 로 끊으면 그 하위질문이 정당한 근거 링크를 잃는다.
                #
                # 몫을 전체 상한보다 먼저 본다. 몫을 다 쓴 하위질문은 풀이 남아 있어도 못 만드는데,
                # 그걸 전체 상한 탓으로 적으면 한계 문장이 max_evidence 를 올리라는 잘못된 신호가 된다.
                if own >= budget:
                    budget_capped.add(cand.cnts_id)
                    continue
                if len(state.evidence) >= params["max_evidence"]:
                    capped.add(cand.cnts_id)
                    continue
                eid = evidence_id(len(state.evidence))
                state.evidence[eid] = Evidence(id=eid, cnts_id=cand.cnts_id, meta=cand.meta)
                known_by_cnts[cand.cnts_id] = eid
                made.add(eid)
                own += 1
```

교체 전:
```python
        subq.capped = len(capped)
        await emit("counters", research_stats(state))
```
교체 후:
```python
        subq.capped = len(capped)
        subq.budget_capped = len(budget_capped)
        await emit("counters", research_stats(state))
```

교체 전:
```python
        next_query = _recheck_query(state, subq, verdict, recheck=recheck)
```
교체 후:
```python
        next_query = _recheck_query(state, subq, verdict, recheck=recheck,
                                    own=len(made.intersection(subq.evidence_ids)))
```

- [ ] **Step 8: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_runner.py tests/test_research_state.py tests/test_research_synthesizer.py -q
```
기대 출력: `191 passed` (runner 47 + state 53 + synthesizer 91).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `791 passed`.

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/state.py app/services/research/runner.py app/tests/test_research_state.py app/tests/test_research_runner.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04c — 하위질문별 근거 예산: 새 근거는 max_evidence // 하위질문 수(최소 min_evidence_per_subq)까지만 만들고 다른 하위질문 근거의 재사용 링크는 세지 않는다. 몫에 막힌 후보는 budget_capped 로 전체 상한(capped)과 따로 세고, 몫을 다 쓰면 재검색하지 않는다. max_evidence 기본값 60→90(6개 기준 15편씩) — 한계 문장 테스트의 기대값 '근거 상한(60편)' 은 기본값에 맞춰 90 으로만 고친다"
```

---

### Task 2: 한계 문장 — 두 상한 구분과 주제 조사(`_topic`)

**Files:**
- Modify: `app/services/research/synthesizer.py`
- Test: `app/tests/test_research_synthesizer.py`

- [ ] **Step 1: 실패 테스트 작성**

`app/tests/test_research_synthesizer.py` 의 import 를 고친다.

교체 전:
```python
from services.research.synthesizer import (
    PAPERS_PER_SECTION, SectionTally, SynthesisCanceled, assemble_report, build_limitations,
    build_section, finalize_section, section_evidence, synthesize,
)
```
교체 후:
```python
from services.research.synthesizer import (
    PAPERS_PER_SECTION, SectionTally, SynthesisCanceled, _topic, assemble_report,
    build_limitations, build_section, finalize_section, section_evidence, synthesize,
)
```

`app/tests/test_research_synthesizer.py` 의 `test_capped_subquestion_is_not_reported_as_missing_evidence` 에서 전체 상한 문구로 좁힌다.

교체 전:
```python
        assert "근거 상한(90편)" in line and "7편" in line
        assert "근거를 찾지 못했다" not in line and "관련 논문이 없다" not in line
```
교체 후:
```python
        assert "전체 근거 상한(90편)" in line and "7편" in line
        assert "하위질문당" not in line
        assert "근거를 찾지 못했다" not in line and "관련 논문이 없다" not in line
```

`app/tests/test_research_synthesizer.py` 의 `TestBuildLimitations` 에 테스트 3개를 넣는다.

교체 전:
```python
    def test_unchecked_subquestion_without_evidence_is_not_counted_twice(self):
```
교체 후:
```python
    def test_budget_capped_insufficient_subquestion_names_the_per_subquestion_cap(self):
        # 몫에 막힌 것을 전체 상한 탓으로 쓰면 max_evidence 를 올리라는 잘못된 신호가 된다
        st = _state()                       # 하위질문 2개 · 기본 90편 → 몫 45편
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].budget_capped = 3
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "하위1" in x)
        assert "(하위질문당 근거 상한(45편)에 닿아 후보 3편을 더 싣지 못했다)" in line
        assert "전체 근거 상한" not in line

    def test_both_caps_are_named_separately(self):
        st = _state()
        st.subquestions[0].verdict = "insufficient"
        st.subquestions[0].budget_capped = 2
        st.subquestions[0].capped = 1
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "하위1" in x)
        assert ("(하위질문당 근거 상한(45편)에 닿아 후보 2편을, "
                "전체 근거 상한(90편)에 닿아 후보 1편을 더 싣지 못했다)") in line

    def test_subquestion_starved_by_its_share_is_not_reported_as_missing_evidence(self):
        st = _state()
        st.subquestions[1].budget_capped = 4
        st.subquestions[1].note = "관련 논문이 없다"
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "하위2" in x)
        assert line == "'하위2' (은)는 하위질문당 근거 상한(45편)에 닿아 검색된 논문 4편을 싣지 못했다"

    def test_unchecked_subquestion_without_evidence_is_not_counted_twice(self):
```

`app/tests/test_research_synthesizer.py` 의 `TestAssembleReport` 앞에 클래스를 넣는다.

교체 전:
```python
class TestAssembleReport:
```
교체 후:
```python
class TestTopic:
    """한계 문장의 주어 조각 — 조사를 받침에 맞춘다. ' 는' 으로 고정하면 받침 있는 말에서 틀린다."""

    @pytest.mark.parametrize(("text", "expected"), [
        ("컴퓨팅 자원 관리", "'컴퓨팅 자원 관리' 는"),
        ("엣지 컴퓨팅의 자원 할당", "'엣지 컴퓨팅의 자원 할당' 은"),
    ])
    def test_particle_follows_the_final_consonant(self, text, expected):
        assert _topic(text) == expected

    @pytest.mark.parametrize("text", ["고성능 컴퓨팅 (HPC)", "클라우드 SLA", "IoT"])
    def test_non_hangul_ending_gets_both_particles(self, text):
        # 'HPC' 는 '는'(에이치피시)이지만 'LAN' 은 '은'(랜)이다 — 읽는 소리는 코드가 모른다
        assert _topic(text) == f"'{text}' (은)는"

    def test_limitation_sentence_uses_the_matching_particle(self):
        st = _state()
        st.subquestions[0].text = "자원 할당"
        st.subquestions[0].verdict = "insufficient"
        line = next(x for x in build_limitations(st, unmarked_total=0, dropped_total=0)
                    if "자원 할당" in x)
        assert line.startswith("'자원 할당' 은 근거 1편으로 결론이 약하다")

    def test_about_phrase_keeps_its_fixed_particle(self):
        # '에 대해서는' 은 받침과 무관하다 — 그대로 둔다
        lims = build_limitations(_state(), unmarked_total=0, dropped_total=0)
        assert any(x.startswith("'하위2' 에 대해서는 근거를 찾지 못했다") for x in lims)


class TestAssembleReport:
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_synthesizer.py -q
```
기대 출력: `ImportError: cannot import name '_topic' from 'services.research.synthesizer'` 가 나오고 `1 error during collection` 으로 끝난다.

- [ ] **Step 3: 구현**

`app/services/research/synthesizer.py` 에 import 를 넣는다. runner 는 synthesizer 를 import 하지 않으므로 순환 import 가 생기지 않는다.

교체 전:
```python
from services.research.llm_json import extract_json
```
교체 후:
```python
from services.research.llm_json import extract_json
from services.research.runner import subq_budget
```

교체 전:
```python
async def _no_progress(idx: int, total: int, status: str, info: dict | None = None) -> None:
    return None
```
교체 후:
```python
async def _no_progress(idx: int, total: int, status: str, info: dict | None = None) -> None:
    return None


def _topic(text: str) -> str:
    """한계 문장의 주어 조각. 조사는 마지막 글자의 받침에 맞춘다.

    한글로 끝나지 않으면(영문·괄호) 읽는 소리를 코드가 알 수 없다 — 'HPC' 는 '는'(에이치피시)이지만
    'LAN' 은 '은'(랜)이다. 틀린 조사보다 병기가 낫다.
    """
    last = text[-1:]
    if "가" <= last <= "힣":
        return f"'{text}' {'은' if (ord(last) - ord('가')) % 28 else '는'}"
    return f"'{text}' (은)는"


def _capped_clause(state: ResearchState, sq: SubQuestion, noun: str) -> str:
    """상한에 막힌 후보를 원인별로 적는다 — "…에 닿아 {noun} N편을" 을 쉼표로 잇는다.

    하위질문당 몫과 전체 상한을 한 수로 합치지 않는다. 풀리는 방법이 다르다 — 몫은 계획에서
    하위질문을 줄이면 커지고, 전체 상한은 max_evidence 를 올려야 풀린다.
    """
    parts = []
    if sq.budget_capped:
        parts.append(f"하위질문당 근거 상한({subq_budget(state)}편)에 닿아 "
                     f"{noun} {sq.budget_capped}편을")
    if sq.capped:
        parts.append(f"전체 근거 상한({state.params['max_evidence']}편)에 닿아 "
                     f"{noun} {sq.capped}편을")
    return ", ".join(parts)
```

교체 전:
```python
    out: list[str] = []
    max_evidence = state.params["max_evidence"]
    for sq in state.subquestions:
```
교체 후:
```python
    out: list[str] = []
    for sq in state.subquestions:
```

교체 전:
```python
        n = len(sq.evidence_ids)
        # failed·capped 를 "근거 없음"보다 먼저 본다. 시스템 장애나 우리 쪽 상한을
        # "근거를 찾지 못했다"로 쓰면 연구 결과(코퍼스 빈틈)로 둔갑한다.
        if sq.failed and n:
            out.append(
                f"'{sq.text}' 는 탐색이 오류로 중단돼 끝까지 확인하지 못했다"
                f"(중단 전까지 모은 근거 {n}편으로만 썼다){note}"
            )
        elif sq.failed:
            out.append(f"'{sq.text}' 는 탐색 중 오류로 확인하지 못했다{note}")
        elif not n and sq.capped:
            # 상한 때문에 0편이면 critic 은 "(없음)"을 보고 판정한다 — 그 note 는 오보다
            out.append(
                f"'{sq.text}' 는 근거 상한({max_evidence}편)에 닿아 "
                f"검색된 논문 {sq.capped}편을 싣지 못했다"
            )
        elif not n:
            out.append(f"'{sq.text}' 에 대해서는 근거를 찾지 못했다{note}")
        elif sq.verdict == "insufficient":
            cap = (f"(근거 상한({max_evidence}편)에 닿아 후보 {sq.capped}편을 더 싣지 못했다)"
                   if sq.capped else "")
            out.append(f"'{sq.text}' 는 근거 {n}편으로 결론이 약하다{cap}{note}")
```
교체 후:
```python
        n = len(sq.evidence_ids)
        topic = _topic(sq.text)
        blocked = sq.capped or sq.budget_capped
        # failed·상한을 "근거 없음"보다 먼저 본다. 시스템 장애나 우리 쪽 상한을
        # "근거를 찾지 못했다"로 쓰면 연구 결과(코퍼스 빈틈)로 둔갑한다.
        if sq.failed and n:
            out.append(
                f"{topic} 탐색이 오류로 중단돼 끝까지 확인하지 못했다"
                f"(중단 전까지 모은 근거 {n}편으로만 썼다){note}"
            )
        elif sq.failed:
            out.append(f"{topic} 탐색 중 오류로 확인하지 못했다{note}")
        elif not n and blocked:
            # 상한 때문에 0편이면 critic 은 "(없음)"을 보고 판정한다 — 그 note 는 오보다
            out.append(f"{topic} {_capped_clause(state, sq, '검색된 논문')} 싣지 못했다")
        elif not n:
            out.append(f"'{sq.text}' 에 대해서는 근거를 찾지 못했다{note}")
        elif sq.verdict == "insufficient":
            cap = f"({_capped_clause(state, sq, '후보')} 더 싣지 못했다)" if blocked else ""
            out.append(f"{topic} 근거 {n}편으로 결론이 약하다{cap}{note}")
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_synthesizer.py tests/test_research_runner.py -q
```
기대 출력: `148 passed` (synthesizer 101 + runner 47). 러너의 `test_starved_subquestion_is_reported_as_capped_not_missing` 는 "근거 상한(1편)" 이 "전체 근거 상한(1편)" 안에 들어 있어서 고치지 않아도 통과한다.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `801 passed`.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/synthesizer.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04c — 한계 문장이 상한 원인을 나눠 적는다: '하위질문당 근거 상한(N편)' 과 '전체 근거 상한(M편)'(둘 다면 둘 다), 근거 0편인 경우도 같은 규칙. 주어 조사는 _topic 이 마지막 글자의 받침으로 은/는을 고르고, 한글로 끝나지 않으면 읽는 소리를 알 수 없어 '(은)는' 으로 병기한다. '에 대해서는' 은 그대로 둔다"
```

---

### Task 3: 보고서 evidence 에는 절에 실린 근거만 담는다

**Files:**
- Modify: `app/services/research/synthesizer.py`
- Test: `app/tests/test_research_synthesizer.py`

- [ ] **Step 1: 소비처를 grep 으로 다시 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI && grep -rnE "report\.evidence|\.report\.evidence|report\[\"evidence\"\]|report\.get\(\"evidence\"\)" frontend/utils frontend/components frontend/pages frontend/composables app --include=*.ts --include=*.vue --include=*.py | grep -v "/tests/"
```

기대 출력은 아래 여덟 줄이다. `app/services/research/synthesizer.py` 에서 나오는 줄은 독스트링뿐이다(줄 번호는 Task 2 를 적용한 뒤의 값이다 — Task 10 이 먼저 들어갔으면 `researchEvents.ts` 줄 번호도 밀린다).
```
frontend/utils/reportDocument.ts:180:    evidence: report.evidence,
frontend/utils/reportDocument.ts:197:    evidence: draft.report.evidence,
frontend/utils/researchEvents.ts:699:    evidenceAdopted: Object.keys(report.evidence ?? {}).length,
frontend/utils/researchReport.ts:23:  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
frontend/components/research/ReportView.vue:34:      <ReportSectionBody v-if="row.sec" :sec="row.sec" :evidence="report.evidence" @open-pdf="$emit('open-pdf', $event)" />
app/services/research/synthesizer.py:170:    """report.evidence 한 항목의 모양. 청크는 점수순으로 싣는다.
app/services/research/synthesizer.py:205:    """다듬은 절(finalize_section) 하나가 인용한 근거만 report.evidence 와 같은 모양으로 만든다.
app/services/research/synthesizer.py:491:    빼면 실재하는 근거가 report.evidence 에만 고아로 남고, 한계에는 사실과 다른
```

판정: 새 보고서에 영향이 없다.
- `ReportView` → `ReportSectionBody` 와 `reportDocument` 의 참고문헌은 절에 달린 칩(eid)으로만 조회한다.
- `researchReport.ts:23` 과 `researchEvents.ts:699` 는 `stats` 가 없는 옛 보고서용 폴백이다. 새 보고서에는 `stats` 가 있고, 옛 보고서 JSON 은 바뀌지 않는다.
- 백엔드는 `api/research.py` 의 `_live_counters` 가 `report["stats"]` 만 읽는다.
- `synthesizer.py` 의 `synthesize` 독스트링("…고아로 남고…")은 Step 4 에서 고친다.

- [ ] **Step 2: 실패 테스트 작성과 기존 테스트 입력 조정**

`app/tests/test_research_synthesizer.py` 에 헬퍼를 넣는다(`_state()` 바로 뒤).

교체 전:
```python
class TestBuildLimitations:
```
교체 후:
```python
def _section_of(*cnts_ids):
    """cnts_ids 를 대표 논문으로 싣는 절 — 보고서 evidence 는 절에 실린 근거만 담는다."""
    return {"heading": "h", "intro": "", "future": [],
            "papers": [{"cnts_id": c, "summary": "s"} for c in cnts_ids]}


class TestBuildLimitations:
```

`sections=[]` 로 `report["evidence"]` 를 읽던 기존 테스트 다섯 건은 그 근거를 싣는 절을 넘기게 입력만 바꾼다. 단언은 그대로 둔다.

교체 전:
```python
    def test_evidence_is_serialized(self):
        report = assemble_report(_state(), sections=[], unmarked_total=0)
```
교체 후:
```python
    def test_evidence_is_serialized(self):
        report = assemble_report(_state(), sections=[_section_of("A")], unmarked_total=0)
```

교체 전:
```python
        # score 는 화면에 유사도로 나간다 — 프론트는 report 만 받으므로 여기서 빠지면 닿을 길이 없다
        report = assemble_report(_state(), sections=[], unmarked_total=0)
```
교체 후:
```python
        # score 는 화면에 유사도로 나간다 — 프론트는 report 만 받으므로 여기서 빠지면 닿을 길이 없다
        report = assemble_report(_state(), sections=[_section_of("A")], unmarked_total=0)
```

교체 전:
```python
    def test_chunk_no_section_points_to_is_not_served(self):
        report = assemble_report(self._replaced(), sections=[], unmarked_total=0)
```
교체 후:
```python
    def test_chunk_no_section_points_to_is_not_served(self):
        report = assemble_report(self._replaced(), sections=[_section_of("A")], unmarked_total=0)
```

교체 전:
```python
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        report = assemble_report(st, sections=[], unmarked_total=0)
        assert [c["chunk_id"] for c in report["evidence"]["E2"]["chunks"]] == ["c2b", "c2a"]
```
교체 후:
```python
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        report = assemble_report(st, sections=[_section_of("B")], unmarked_total=0)
        assert [c["chunk_id"] for c in report["evidence"]["E2"]["chunks"]] == ["c2b", "c2a"]
```

교체 전:
```python
        st.subquestions[0].evidence_chunks = {}
        report = assemble_report(st, sections=[], unmarked_total=0)
```
교체 후:
```python
        st.subquestions[0].evidence_chunks = {}
        report = assemble_report(st, sections=[_section_of("A")], unmarked_total=0)
```

교체 전:
```python
        assert ev == assemble_report(st, [], unmarked_total=0)["evidence"]["E3"]
```
교체 후:
```python
        assert ev == assemble_report(st, [_section_of("C")], unmarked_total=0)["evidence"]["E3"]
```

위에서 여섯 곳을 고쳤지만 `test_research_synthesizer.py` 의 테스트 건수로는 다섯이다. 마지막 곳은 `TestSectionEvidence.test_shape_matches_report_evidence` 이고, 나머지 다섯 곳 가운데 둘은 같은 `TestReportChunks` 클래스 안에 있다. 커밋 메시지는 조정한 테스트를 이 여섯 건 기준으로 센다.

`test_failed_subquestion_with_evidence_gets_a_section` 의 독스트링을 고친다. 이제 절에서 빠진 근거는 고아로 남지 않고 보고서에서 사라진다.

교체 전:
```python
        절에서 빼면 근거가 report.evidence 에만 고아로 남는다."""
```
교체 후:
```python
        절에서 빼면 그 근거가 보고서에서 사라진다(report.evidence 는 절에 실린 근거만 담는다)."""
```

새 테스트를 `TestReportStats` 앞에 넣는다.

교체 전:
```python
class TestReportStats:
```
교체 후:
```python
class TestReportEvidence:
    """보고서 evidence 는 절에 실린 근거만 담는다 — 채택 수는 stats 가 센다."""

    def test_evidence_beyond_the_section_papers_is_left_out(self):
        # 절은 하위질문마다 앞 5편만 싣는다 — 나머지까지 실으면 상한을 올릴수록 보고서 JSON 만 분다
        st = _state_three()
        ids = [f"E{i}" for i in range(1, 8)]
        for eid in ids:
            st.evidence.setdefault(eid, Evidence(id=eid, cnts_id=eid, meta={}))
        st.subquestions[0].evidence_ids = ids
        sections = [build_section(st, sq, {"intro": "도입."})
                    for sq in st.subquestions if sq.evidence_ids]
        report = assemble_report(st, sections, unmarked_total=0)
        assert list(report["evidence"]) == ["E1", "E2", "E3", "E4", "E5"]
        assert report["stats"]["evidence_adopted"] == 7

    def test_evidence_of_a_subquestion_without_a_section_is_left_out(self):
        st = _state_three()
        report = assemble_report(st, [build_section(st, st.subquestions[0], {"intro": "도입."})],
                                 unmarked_total=0)
        assert set(report["evidence"]) == {"E1", "E2"}


class TestReportStats:
```

- [ ] **Step 3: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_synthesizer.py -q
```
기대 출력: 아래 두 건이 실패하고 `2 failed, 101 passed` 로 끝난다(`Left contains 2 more items, first extra item: 'E6'` / `Extra items in the left set: 'E3'`).
- `FAILED ...TestReportEvidence::test_evidence_beyond_the_section_papers_is_left_out`
- `FAILED ...TestReportEvidence::test_evidence_of_a_subquestion_without_a_section_is_left_out`

- [ ] **Step 4: 구현**

`app/services/research/synthesizer.py`

교체 전:
```python
def _serialize_evidence(state: ResearchState) -> dict:
    """보고서의 근거 목록. 청크는 지금 어느 하위질문이든 가리키는 것만, 점수순으로 싣는다.

    Evidence.chunks 는
```
교체 후:
```python
def _cited(state: ResearchState, section: dict) -> list[str]:
    """다듬은 절(finalize_section) 하나가 인용한 근거 번호 — 대표 논문·도입·향후 과제의 칩 전부."""
    # 다듬은 도입에는 표준형 [E#] 만 남는다 — bind_markers 의 used 로 읽는다. 여기서 정규식을
    # 다시 쓰면 마커 문법이 두 곳으로 갈라진다.
    cited = list(bind_markers(section.get("intro", ""), set(state.evidence)).used)
    for item in (*section.get("papers", []), *section.get("future", [])):
        cited.extend(item.get("evidence", []))
    return cited


def _serialize_evidence(state: ResearchState, cited: set[str]) -> dict:
    """보고서의 근거 목록. 절에 실린(cited) 근거만, 청크는 지금 어느 하위질문이든 가리키는 것만
    점수순으로 싣는다.

    채택한 근거를 전부 싣지 않는 이유: 절은 하위질문마다 앞 5편만 쓰므로 나머지는 어느 칩도
    가리키지 않는다. 그대로 두면 상한을 올릴수록 보고서 JSON 만 분다. 채택 수는 stats 가 센다.

    Evidence.chunks 는
```
(교체 전 블록은 독스트링 셋째 줄 `Evidence.chunks 는` 까지다. 그 뒤 원문은 그대로 둔다.)

교체 전:
```python
    return {eid: _evidence_entry(ev, _shown(eid, ev)) for eid, ev in state.evidence.items()}
```
교체 후:
```python
    return {eid: _evidence_entry(ev, _shown(eid, ev))
            for eid, ev in state.evidence.items() if eid in cited}
```

`section_evidence` 도 같은 헬퍼를 쓰게 한다.

교체 전:
```python
    # 다듬은 도입에는 표준형 [E#] 만 남는다 — bind_markers 의 used 로 읽는다. 여기서 정규식을
    # 다시 쓰면 마커 문법이 두 곳으로 갈라진다.
    cited = list(bind_markers(section.get("intro", ""), set(state.evidence)).used)
    for item in (*section.get("papers", []), *section.get("future", [])):
        cited.extend(item.get("evidence", []))
    mapped = section.get("evidence_chunks", {})
    out: dict[str, dict] = {}
    for eid in cited:
```
교체 후:
```python
    mapped = section.get("evidence_chunks", {})
    out: dict[str, dict] = {}
    for eid in _cited(state, section):
```

교체 전:
```python
    tally = SectionTally(unmarked=unmarked_total)
    out_sections = []
    for sec in sections:
        section, counted = finalize_section(state, sec)
        out_sections.append(section)
        tally.add(counted)
```
교체 후:
```python
    tally = SectionTally(unmarked=unmarked_total)
    out_sections = []
    cited: set[str] = set()
    for sec in sections:
        section, counted = finalize_section(state, sec)
        out_sections.append(section)
        tally.add(counted)
        cited.update(_cited(state, section))
```

교체 전:
```python
        "evidence": _serialize_evidence(state),
```
교체 후:
```python
        "evidence": _serialize_evidence(state, cited),
```

`synthesize` 독스트링을 고친다.

교체 전:
```python
    빼면 실재하는 근거가 report.evidence 에만 고아로 남고, 한계에는 사실과 다른
    "확인하지 못했다"만 실린다.
```
교체 후:
```python
    빼면 실재하는 근거가 보고서에서 사라지고(report.evidence 는 절에 실린 근거만 담는다),
    한계에는 사실과 다른 "확인하지 못했다"만 실린다.
```

- [ ] **Step 5: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_synthesizer.py -q
```
기대 출력: `103 passed`.

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `803 passed`. 워커 테스트(`test_research_tasks.py`)는 `synthesize` 를 대역으로 두므로 영향이 없다.

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/synthesizer.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04c — 보고서 evidence 에 절(대표 논문·도입·향후 과제)이 인용한 근거만 싣는다 — 상한을 올려도 보고서 JSON 이 붇지 않게. 채택 수는 stats 가 그대로 센다. 절 인용 모으기를 _cited 로 떼어 section_evidence 와 함께 쓴다. 화면·문서는 절의 칩으로만 근거를 조회하고 stats 없는 옛 보고서 폴백만 전체 개수를 센다(grep 확인). sections=[] 로 report.evidence 를 읽던 기존 테스트 6건은 그 근거를 싣는 절을 넘기도록 입력만 바꾼다(단언은 같다)"
```

---

### Task 4: 문체 규칙 — 종합(intro·summaries·future)과 자기점검 note 를 '~다' 문어체로

**Files:**
- Modify: `app/domains/nl_library/prompts/research_synthesize.yaml`
- Modify: `app/domains/nl_library/prompts/research_critique.yaml`(note 줄만 고친다 — Task 6 의 `off_topic` 편집은 JSON 예시 블록과 new_queries 설명 줄이라 겹치지 않는다)
- Test: `app/tests/test_research_synthesizer.py`
- Test: `app/tests/test_research_critic.py`

- [ ] **Step 1: 실패 테스트 작성**

`app/tests/test_research_critic.py` 의 `TestCritique` 에 테스트를 넣는다.

교체 전:
```python
    def test_transport_error_is_reported_as_unchecked_not_raised(self, monkeypatch):
```
교체 후:
```python
    def test_prompt_asks_for_plain_written_style_note(self, monkeypatch):
        # note 는 보고서 한계 섹션에 그대로 실린다 — 서술은 '~다'인데 note 만 '~합니다'면 한 보고서에서 문체가 갈린다
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return '{"verdict": "sufficient", "note": "충분하다", "new_queries": []}'

        self._run(monkeypatch, fake_chat)
        system = seen[0][0]["content"]
        assert "'~다'로 끝나는 문어체 평서문" in system
        assert "'~합니다'·'~입니다' 금지" in system

    def test_transport_error_is_reported_as_unchecked_not_raised(self, monkeypatch):
```

`app/tests/test_research_synthesizer.py` 에서 프롬프트 예시를 베낀 출력을 흉내 내는 문자열을 바뀐 예시에 맞춘다(`test_template_placeholder_copy_is_not_taken_as_narrative`, 판정은 `[E#]` 로 하므로 결과는 같다).

교체 전:
```python
            "intro": "이 하위질문에 대한 연구 흐름을 설명하는 2~4문장. 문장마다 [E#] 를 답니다.",
```
교체 후:
```python
            "intro": "이 하위질문에 대한 연구 흐름을 설명하는 2~4문장. 문장마다 [E#] 를 단다.",
```

`app/tests/test_research_synthesizer.py` 의 `TestReportChunks` 앞에 클래스를 넣는다.

교체 전:
```python
class TestReportChunks:
```
교체 후:
```python
class TestSynthesizePrompt:
    """절 서술의 문체 — 운영 보고서에서 5절만 '~합니다' 체였다."""

    def _system(self, monkeypatch):
        systems = []

        async def fake_chat(messages, *, params=None, timeout=None):
            systems.append(messages[0]["content"])
            return json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})

        monkeypatch.setattr(synthesizer, "chat", fake_chat)
        asyncio.run(synthesize(_state_three()))
        return systems[0]

    def test_every_field_is_asked_in_plain_written_style(self, monkeypatch):
        system = self._system(monkeypatch)
        assert "'~다'로 끝나는 문어체 평서문" in system
        assert "'~합니다'·'~입니다' 금지" in system
        assert "intro·summaries·future 모두" in system

    def test_json_example_does_not_model_the_polite_style(self, monkeypatch):
        # gemma 는 예시를 견본으로 베낀다(recurring-gotchas 15번) — 예시 값이 '~ㅂ니다'로 끝나면 규칙과 싸운다
        system = self._system(monkeypatch)
        example = system.split("JSON 하나만 출력하세요.", 1)[1].split("summaries 에는", 1)[0]
        assert "니다" not in example


class TestReportChunks:
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py tests/test_research_synthesizer.py -q
```
기대 출력: 아래 세 건이 실패하고 `3 failed, 132 passed` 로 끝난다(critic 30 + synthesizer 105 중).
- `FAILED ...test_research_critic.py::TestCritique::test_prompt_asks_for_plain_written_style_note`
- `FAILED ...test_research_synthesizer.py::TestSynthesizePrompt::test_every_field_is_asked_in_plain_written_style`
- `FAILED ...::TestSynthesizePrompt::test_json_example_does_not_model_the_polite_style`

- [ ] **Step 3: 구현**

`app/domains/nl_library/prompts/research_synthesize.yaml`

교체 전:
```yaml
  - 한국어로 씁니다.

  JSON 하나만 출력하세요.
  {"intro": "이 하위질문에 대한 연구 흐름을 설명하는 2~4문장. 문장마다 [E#] 를 답니다.",
```
교체 후:
```yaml
  - 한국어로 씁니다.
  - 모든 문장은 '~다'로 끝나는 문어체 평서문으로 씁니다('~합니다'·'~입니다' 금지). intro·summaries·future 모두 같습니다.

  JSON 하나만 출력하세요.
  {"intro": "이 하위질문에 대한 연구 흐름을 설명하는 2~4문장. 문장마다 [E#] 를 단다.",
```

`app/domains/nl_library/prompts/research_critique.yaml`

교체 전:
```yaml
  note 는 사용자에게 그대로 보여집니다. 한국어로 구체적으로 쓰세요.
```
교체 후:
```yaml
  note 는 사용자에게 그대로 보여집니다(보고서의 한계 섹션에 실립니다). 한국어로 구체적으로, '~다'로 끝나는 문어체 평서문으로 쓰세요('~합니다'·'~입니다' 금지).
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py tests/test_research_synthesizer.py tests/test_prompts.py -q
```
기대 출력: `141 passed` (critic 30 + synthesizer 105 + prompts 6).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `806 passed`.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/domains/nl_library/prompts/research_synthesize.yaml app/domains/nl_library/prompts/research_critique.yaml app/tests/test_research_synthesizer.py app/tests/test_research_critic.py
git commit -m "[Feat] round04c — 종합·자기점검 프롬프트에 '~다' 문어체 평서문 규칙('~합니다'·'~입니다' 금지)을 넣는다 — 종합은 intro·summaries·future 모두, 자기점검은 한계 섹션에 그대로 실리는 note. 종합 JSON 예시의 '[E#] 를 답니다' 도 '단다' 로 바꿔 예시가 규칙과 싸우지 않게 하고(gemma 는 예시를 베낀다), 그 예시를 베낀 출력을 흉내 낸 테스트 문자열도 맞춘다. 모델이 섞어 쓴 문체를 코드로 고치지는 않는다"
```

---

### Task 5: 계획 프롬프트 — 원 질문의 핵심 개념 안에서, 측면으로, 핵심어 포함

**Files:**
- Modify: `app/domains/nl_library/prompts/research_plan.yaml`
- Test: `app/tests/test_research_planner.py`

- [ ] **Step 1: 실패 테스트 작성**

`app/tests/test_research_planner.py` 의 `TestMakePlan` 에 테스트를 넣는다(기존 `fake_chat` 대역 방식을 그대로 쓴다).

교체 전:
```python
        assert plan == ["가", "나"]
        assert "최대 2개" in seen[0][0]["content"]
        assert "청소년 진로상담" in seen[0][1]["content"]
```
교체 후:
```python
        assert plan == ["가", "나"]
        assert "최대 2개" in seen[0][0]["content"]
        assert "청소년 진로상담" in seen[0][1]["content"]

    def test_prompt_keeps_subquestions_inside_the_core_concept(self, monkeypatch):
        """운영에서 '컴퓨팅 자원' 질문이 HPC·클라우드·엣지처럼 이웃한 기술 목록으로 나뉘었다.

        예시는 넣지 않는다 — gemma 는 예시의 개수·분야를 베낀다(recurring-gotchas 15번).
        """
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return "1. 가"

        monkeypatch.setattr(planner, "chat", fake_chat)
        asyncio.run(planner.make_plan("컴퓨팅 자원에 대한 연구", params=merge_params({})))
        system = seen[0][0]["content"]
        assert "원 질문의 핵심 개념 안에 머뭅니다" in system
        assert "이웃한 기술·분야를 나열하는 식으로 나누지 마세요" in system
        assert "개념·정의, 방법·기법, 적용 분야, 성과·평가, 한계·과제 중 질문에 맞는 것만" in system
        assert "원 질문의 핵심어를 그대로 넣습니다" in system
        assert "최대 6개" in system and "더 적어도 됩니다" in system
        assert "예:" not in system and "예시" not in system
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_planner.py -q
```
기대 출력: `FAILED tests/test_research_planner.py::TestMakePlan::test_prompt_keeps_subquestions_inside_the_core_concept` 가 나오고 `1 failed, 15 passed` 로 끝난다.

- [ ] **Step 3: 구현**

`app/domains/nl_library/prompts/research_plan.yaml`

교체 전:
```yaml
  규칙:
  - 하위질문은 최대 {{ limit }}개입니다.
  - 각 하위질문은 그 자체로 논문 검색어가 될 만큼 구체적이어야 합니다.
```
교체 후:
```yaml
  규칙:
  - 하위질문은 최대 {{ limit }}개입니다. 질문의 핵심 개념이 좁으면 더 적어도 됩니다.
  - 모든 하위질문은 원 질문의 핵심 개념 안에 머뭅니다. 원 질문의 주제와 이웃한 기술·분야를 나열하는 식으로 나누지 마세요.
  - 질문이 넓으면 핵심 개념의 측면으로 나눕니다. 개념·정의, 방법·기법, 적용 분야, 성과·평가, 한계·과제 중 질문에 맞는 것만 고릅니다.
  - 각 하위질문에 원 질문의 핵심어를 그대로 넣습니다. 검색이 원 질문의 주제를 벗어나지 않게 하기 위해서입니다.
  - 각 하위질문은 그 자체로 논문 검색어가 될 만큼 구체적이어야 합니다.
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_planner.py tests/test_prompts.py -q
```
기대 출력: `22 passed` (planner 16 + prompts 6 — `test_prompts.py` 의 `"6" in rp_s` 도 그대로 통과한다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `807 passed`.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/domains/nl_library/prompts/research_plan.yaml app/tests/test_research_planner.py
git commit -m "[Feat] round04c — 계획 프롬프트: 하위질문은 원 질문의 핵심 개념 안에 머물고(이웃한 기술·분야 나열 금지), 넓으면 핵심 개념의 측면(개념·정의, 방법·기법, 적용 분야, 성과·평가, 한계·과제 중 맞는 것)으로 나누며, 각 하위질문에 원 질문의 핵심어를 그대로 넣는다. 핵심 개념이 좁으면 최대 개수보다 적어도 된다. 예시는 넣지 않는다 — gemma 가 예시의 개수·분야를 베낀다"
```

---

## 단계 2 — 무관한 근거 걸러내기, 백엔드 (Task 6~9)

- 단계 1 이 먼저 적용돼 있다고 본다. `runner.py` 에는 Task 1 의 `subq_budget(state)`·`made`·`own` 이 있고, 예산은 "지금 `subq.evidence_ids` 에 남아 있고 이 하위질문이 만든 근거 수"로 센다(후보 루프와 `_recheck_query` 모두).
- 이 단계의 "교체 전" 원문은 Task 1 이 건드리지 않는 한두 줄짜리 앵커로 골랐다.
  - 후보 루프: `eid = known_by_cnts.get(cand.cnts_id)`
  - 번호 매기기: `eid = evidence_id(len(state.evidence))`
  - 판정 반영: `subq.parse_failed = verdict.parse_failed`
  - 회차 기록: `"note": verdict.note, "next_query": next_query,`
  - critique 이벤트: `"round": round_no, "next_query": next_query,`
  - 재검색 검사: `_recheck_query` 안의 `if not should_recheck(...)` 두 줄
- Task 8 의 `test_freed_budget_lets_the_subquestion_search_again` 은 Task 1 의 예산과 이 단계의 제외를 함께 검증한다. 예산을 줄지 않는 누적 카운터로 세면 이 테스트가 실패해서 드러난다.
- 제외 뒤 0편이면 판정이 충분이어도 재검색 대상이지만(Task 8 의 `emptied`), 재검색어는 critic 이 제안한 `new_queries` 에서만 나온다(`_next_query`). 그런데 기존 critique 프롬프트는 "부족하다고 판단하면" 검색어를 제안하라고 해서 충분 판정에는 `new_queries` 가 비기 쉽고, 그러면 재검색이 일어나지 않는다. Task 6 이 off_topic 설명 뒤에 "모두 뺐으면 남는 근거가 없으니 검색어를 제안하라"는 한 줄을 더해 막는다(예시 없이 규칙만).
- spec 과 다르게 한 점: spec §4 는 제외할 때 순위 보조값 `relevance`·`leaders` 도 지우라고 한다. 그런데 `_rank_order` 는 `evidence_ids` 에 남은 id 만 보고, 번호를 다시 쓰지 않으므로(`evidence_seq`) 지워도 결과가 같다. 효과 없는 코드라 지우지 않는다(Task 8 의 `_exclude_off_topic` docstring 에 이유를 적는다).
- `evidence_adopted`(= `len(state.evidence)`)는 이제 줄 수 있다(무관 근거를 풀에서 지운다, spec §4). 라이브 경로는 critique 때 `_save_progress` 가 올리는 step 이벤트의 `result.counters` 를 프론트 `applyStep` 이 그대로 쓰므로 괜찮다. 재접속 때 카운터를 합치는 `reconcileCounters` 의 "카운터는 줄지 않는다" 주석은 Task 10 에서 고친다.

### Task 6: critic — 목록 번호, off_topic 해석, 프롬프트

**계약 추가:** `parse_verdict(raw, *, listed: int = 0)` 에 키워드 `listed` 를 더한다. 번호를 붙여 보인 근거 수이고, off_topic 은 이 범위의 번호만 받는다.

**Files:**
- Modify: `app/services/research/critic.py`
- Modify: `app/domains/nl_library/prompts/research_critique.yaml`
- Test: `app/tests/test_research_critic.py`

- [ ] **Step 1: 목록 번호 실패 테스트 작성**

`app/tests/test_research_critic.py` 의 기존 기대값을 번호 붙은 형태로 바꾸고, 번호 테스트 하나를 더한다.

교체 전:
```python
    def test_includes_excerpt_from_first_chunk(self):
        e = self._evidence("제목", "2020", "본문 발췌 내용")
        result = format_evidence_list([e])
        assert result == "- 제목 (2020) — 본문 발췌 내용"
```
교체 후:
```python
    def test_includes_excerpt_from_first_chunk(self):
        e = self._evidence("제목", "2020", "본문 발췌 내용")
        result = format_evidence_list([e])
        assert result == "[1] 제목 (2020) — 본문 발췌 내용"

    def test_items_are_numbered_from_one_in_given_order(self):
        """critic 은 이 번호로 무관한 근거를 가리키고, runner 는 넘긴 순서로 id 에 되돌린다."""
        evs = [self._evidence(f"제목{i}", "2020") for i in range(3)]
        assert format_evidence_list(evs).splitlines() == [
            "[1] 제목0 (2020)", "[2] 제목1 (2020)", "[3] 제목2 (2020)"]
```

교체 전:
```python
        assert "\n" not in result
        assert result == "- 제목 (2020) — [표] 설명 | a | b | | 1 | 2 |"
```
교체 후:
```python
        assert "\n" not in result
        assert result == "[1] 제목 (2020) — [표] 설명 | a | b | | 1 | 2 |"
```

교체 전:
```python
        lines = format_evidence_list(many).splitlines()
        assert len(lines) == _MAX_LISTED + 1
        assert lines[-1] == "- …외 5편"
```
교체 후:
```python
        lines = format_evidence_list(many).splitlines()
        assert len(lines) == _MAX_LISTED + 1
        assert lines[_MAX_LISTED - 1].startswith(f"[{_MAX_LISTED}] ")
        # 잘린 나머지에는 번호가 없다 — 발췌를 보지 못한 근거를 무관하다고 가리키게 두지 않는다
        assert lines[-1] == "…외 5편"
```

교체 전:
```python
        e = Evidence(id="E1", cnts_id="c", meta={"title": "", "pub_date": ""}, chunks=[])
        assert format_evidence_list([e]) == "- (제목 없음) (연도미상)"

    def test_evidence_without_chunks_falls_back_to_title_year(self):
        e = self._evidence("제목", "2020")
        assert format_evidence_list([e]) == "- 제목 (2020)"
```
교체 후:
```python
        e = Evidence(id="E1", cnts_id="c", meta={"title": "", "pub_date": ""}, chunks=[])
        assert format_evidence_list([e]) == "[1] (제목 없음) (연도미상)"

    def test_evidence_without_chunks_falls_back_to_title_year(self):
        e = self._evidence("제목", "2020")
        assert format_evidence_list([e]) == "[1] 제목 (2020)"
```

교체 전:
```python
        lines = result.splitlines()
        assert lines == ["- A (2020) — 본문", "- B (2021)"]
```
교체 후:
```python
        lines = result.splitlines()
        assert lines == ["[1] A (2020) — 본문", "[2] B (2021)"]
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py -q
```
기대 출력: 마지막 줄 `7 failed, 24 passed`. 실패 대상은 TestFormatEvidenceList 의 includes_excerpt, items_are_numbered, newlines, list_is_capped, empty_meta, without_chunks, mixed 이고, 모두 `AssertionError: assert '- 제목 (2020) …' == '[1] 제목 (2020) …'` 모양이다.

- [ ] **Step 3: 번호 붙이기 구현**

`app/services/research/critic.py`

교체 전:
```python
    evidence 는 하위질문 안 순위순이다 — 상한에서 잘리는 쪽이 순위 낮은 근거다.

    발췌는 자르기 전에 공백을 접는다. 표 청크는 `[표]\\n…\\n{table_md}` 로
    저장되고 본문 청크도 단락 개행을 보존하므로, 그대로 쓰면 한 항목이
    여러 줄로 퍼져 어느 발췌가 어느 논문 것인지 흐려진다.
    """
    lines: list[str] = []
    for e in evidence[:_MAX_LISTED]:
        title = e.meta.get("title") or "(제목 없음)"
        year = e.meta.get("pub_date") or "연도미상"
        if not e.chunks:
            lines.append(f"- {title} ({year})")
            continue
        flat = " ".join(e.chunks[0].text.split())
        excerpt = flat[:_EXCERPT_LEN]
        if len(flat) > _EXCERPT_LEN:
            excerpt += "…"
        lines.append(f"- {title} ({year}) — {excerpt}")

    hidden = len(evidence) - _MAX_LISTED
    if hidden > 0:
        lines.append(f"- …외 {hidden}편")
    return "\n".join(lines) or "(없음)"
```
교체 후:
```python
    evidence 는 하위질문 안 순위순이다 — 상한에서 잘리는 쪽이 순위 낮은 근거다.

    항목마다 [1]부터 번호를 붙인다. 모델은 이 번호로 무관한 근거를 가리키고(off_topic),
    runner 가 넘긴 순서로 근거 id 에 되돌린다. 잘린 나머지는 번호 없이 수만 적는다 —
    발췌를 보지 못한 근거를 무관하다고 가리키게 두지 않는다.

    발췌는 자르기 전에 공백을 접는다. 표 청크는 `[표]\\n…\\n{table_md}` 로
    저장되고 본문 청크도 단락 개행을 보존하므로, 그대로 쓰면 한 항목이
    여러 줄로 퍼져 어느 발췌가 어느 논문 것인지 흐려진다.
    """
    lines: list[str] = []
    for n, e in enumerate(evidence[:_MAX_LISTED], start=1):
        title = e.meta.get("title") or "(제목 없음)"
        year = e.meta.get("pub_date") or "연도미상"
        if not e.chunks:
            lines.append(f"[{n}] {title} ({year})")
            continue
        flat = " ".join(e.chunks[0].text.split())
        excerpt = flat[:_EXCERPT_LEN]
        if len(flat) > _EXCERPT_LEN:
            excerpt += "…"
        lines.append(f"[{n}] {title} ({year}) — {excerpt}")

    hidden = len(evidence) - _MAX_LISTED
    if hidden > 0:
        lines.append(f"…외 {hidden}편")
    return "\n".join(lines) or "(없음)"
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py -q
```
기대 출력: `31 passed`.

- [ ] **Step 5: off_topic 해석·프롬프트 실패 테스트 작성**

`app/tests/test_research_critic.py` 맨 위 import 를 고친다.

교체 전:
```python
import asyncio
import logging
```
교체 후:
```python
import asyncio
import json
import logging
```

TestShouldRecheck 앞에 클래스를 더한다.

교체 전:
```python
class TestShouldRecheck:
```
교체 후:
```python
class TestOffTopic:
    """무관 근거 번호 — 잘못 읽은 번호로 관련 있는 근거를 지우면 안 된다."""

    def _parse(self, off_topic, *, listed=5, verdict="insufficient"):
        raw = json.dumps({"verdict": verdict, "note": "n", "new_queries": [],
                          "off_topic": off_topic}, ensure_ascii=False)
        return parse_verdict(raw, listed=listed)

    def test_integer_numbers_are_read(self):
        assert self._parse([2, 4]).off_topic == [2, 4]

    def test_numeric_strings_are_read(self):
        assert self._parse(["3", " 1 "]).off_topic == [3, 1]

    def test_numbers_outside_the_list_are_dropped(self):
        assert self._parse([0, 1, 5, 6, -2], listed=5).off_topic == [1, 5]

    def test_duplicates_are_dropped(self):
        assert self._parse([2, "2", 2]).off_topic == [2]

    def test_non_numbers_are_dropped(self):
        # true 는 int 의 서브클래스라 그냥 두면 1번으로 읽힌다
        assert self._parse([1.0, "둘", None, True, {"n": 3}, "3"]).off_topic == [3]

    def test_non_list_gives_empty(self):
        assert self._parse("2, 3").off_topic == []
        assert self._parse(2).off_topic == []

    def test_missing_key_gives_empty(self):
        v = parse_verdict('{"verdict": "sufficient", "note": "n", "new_queries": []}', listed=5)
        assert v.off_topic == []

    def test_sufficient_verdict_may_still_name_off_topic(self):
        assert self._parse([1], verdict="sufficient").off_topic == [1]

    def test_unreadable_verdict_excludes_nothing(self):
        """판정을 못 읽었는데 근거를 지우면 안 된다."""
        raw = '{"verdict": "maybe", "note": "n", "new_queries": [], "off_topic": [1, 2]}'
        v = parse_verdict(raw, listed=5)
        assert v.parse_failed is True
        assert v.off_topic == []


class TestShouldRecheck:
```

TestCritique 끝(`test_http_status_error_is_reported_as_unchecked` 뒤)에 테스트를 더한다.

교체 전:
```python
        v = self._run(monkeypatch, fake_chat)
        assert v.parse_failed is True
```
교체 후:
```python
        v = self._run(monkeypatch, fake_chat)
        assert v.parse_failed is True

    def test_prompt_numbers_the_evidence_and_asks_for_off_topic(self, monkeypatch):
        seen = []

        async def fake_chat(messages, *, params=None, timeout=None):
            seen.append(messages)
            return ('{"verdict": "sufficient", "note": "n", "new_queries": [], '
                    '"off_topic": [1, 2]}')

        v = self._run(monkeypatch, fake_chat)
        system, user = seen[0][0]["content"], seen[0][1]["content"]
        assert '"off_topic": []' in system     # 예시는 빈 배열뿐 — gemma 는 예시의 개수를 베낀다
        # 모두 빼 0편이 되면 runner 가 다시 찾는데(should_recheck 의 emptied), 충분 판정에는 검색어를
        # 제안하지 않는 규칙만 있으면 찾을 검색어가 없다
        assert "남는 근거가 없으니 new_queries 에 다른 검색어를 제안하세요" in system
        assert "[1] 논문 가 (2008) — 본문 발췌" in user
        assert v.off_topic == [1]              # 근거 1편에 2번은 없다
```

- [ ] **Step 6: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py -q
```
기대 출력: 마지막 줄 `10 failed, 31 passed`.
- TestOffTopic 9개는 `TypeError: parse_verdict() got an unexpected keyword argument 'listed'`.
- `test_prompt_numbers_the_evidence_and_asks_for_off_topic` 는 `AssertionError`(system 에 `"off_topic": []` 없음).

- [ ] **Step 7: Verdict·parse_verdict·critique 구현**

`app/services/research/critic.py`

교체 전:
```python
@dataclass
class Verdict:
    verdict: str
    note: str = ""
    new_queries: list[str] = field(default_factory=list)
    parse_failed: bool = False
```
교체 후:
```python
@dataclass
class Verdict:
    verdict: str
    note: str = ""
    new_queries: list[str] = field(default_factory=list)
    parse_failed: bool = False
    # 발췌가 하위질문의 핵심 개념을 다루지 않는 근거의 목록 번호(1부터, format_evidence_list 의 [n]).
    # runner 가 그 하위질문에서 뺀다 — 같은 단어를 다른 뜻으로 쓴 논문을 걸러낼 수 있는 곳은
    # 발췌를 읽는 critic 뿐이다.
    off_topic: list[int] = field(default_factory=list)
```

교체 전:
```python
def parse_verdict(raw: str) -> Verdict:
    """판정 JSON 을 읽는다. 못 읽으면 sufficient 로 떨어뜨려 루프를 끝낸다.

    해석 실패를 insufficient 로 두면 파싱이 깨질 때마다 재검색이 상한까지
    돌아 시간을 태운다. 실패가 루프가 되면 안 된다.
    """
```
교체 후:
```python
def parse_verdict(raw: str, *, listed: int = 0) -> Verdict:
    """판정 JSON 을 읽는다. 못 읽으면 sufficient 로 떨어뜨려 루프를 끝낸다.

    해석 실패를 insufficient 로 두면 파싱이 깨질 때마다 재검색이 상한까지
    돌아 시간을 태운다. 실패가 루프가 되면 안 된다.

    listed 는 번호를 붙여 보인 근거 수다(format_evidence_list). 판정을 못 읽으면
    off_topic 도 비어 있다 — 판정을 못 읽었는데 근거를 지우면 안 된다.
    """
```

교체 전:
```python
    queries = [q for q in raw_queries if isinstance(q, str) and q.strip()]
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries)
```
교체 후:
```python
    queries = [q for q in raw_queries if isinstance(q, str) and q.strip()]
    return Verdict(verdict, note=str(data.get("note") or ""), new_queries=queries,
                   off_topic=_off_topic(data.get("off_topic"), listed))


def _off_topic(raw: object, listed: int) -> list[int]:
    """보인 목록 안의 번호만 순서대로·중복 없이 받는다. 배열이 아니거나 숫자로 읽히지 않는 값은
    버린다 — 잘못 읽은 번호로 관련 있는 근거를 지우느니 무관한 근거 하나를 남기는 편이 낫다."""
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for v in raw:
        if isinstance(v, str) and v.strip().isdecimal():
            v = int(v)
        # bool 은 int 의 서브클래스라 true 가 1번으로 읽힌다
        if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= listed and v not in out:
            out.append(v)
    return out
```

교체 전:
```python
    return parse_verdict(raw)
```
교체 후:
```python
    return parse_verdict(raw, listed=min(len(evidence), _MAX_LISTED))
```

`app/domains/nl_library/prompts/research_critique.yaml`(CRLF — Edit 도구). 교체는 두 곳이다. Task 4 가 고친 note 문체 줄은 건드리지 않는다.

교체 전:
```yaml
    "new_queries": ["<제안 검색어>", "<제안 검색어>"]
  }
```
교체 후:
```yaml
    "new_queries": ["<제안 검색어>", "<제안 검색어>"],
    "off_topic": []
  }
```

교체 전:
```yaml
  new_queries 는 항상 배열입니다. 제안할 것이 없으면 빈 배열로 둡니다.
```
교체 후:
```yaml
  new_queries 는 항상 배열입니다. 제안할 것이 없으면 빈 배열로 둡니다.
  off_topic 에는 발췌가 하위질문의 핵심 개념을 다루지 않는 근거(같은 단어를 다른 뜻으로 쓴 논문 포함)의 번호를 정수로 씁니다. 번호는 근거 목록 맨 앞 [ ] 안의 숫자입니다. 여기에 넣은 근거는 이 하위질문의 근거에서 빠집니다. 없으면 빈 배열로 둡니다.
  모든 근거를 off_topic 에 넣었다면 남는 근거가 없으니 new_queries 에 다른 검색어를 제안하세요.
```

- [ ] **Step 8: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py tests/test_prompts.py tests/test_research_runner.py -q
```
기대 출력: `94 passed` (critic 41 + prompts 6 + runner 47).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `818 passed`.

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/critic.py app/domains/nl_library/prompts/research_critique.yaml app/tests/test_research_critic.py
git commit -m "[Feat] round04c — 자기점검이 무관한 근거를 번호로 돌려준다: critic 목록에 [1]부터 번호를 붙이고(잘린 나머지는 번호 없이 수만), 응답 JSON 의 off_topic 을 보인 목록 안의 정수(또는 정수 문자열)만 순서대로·중복 없이 받는다. 배열이 아니거나 판정을 못 읽으면 비운다 — 판정을 못 읽었는데 근거를 지우면 안 된다. 프롬프트 예시는 빈 배열만 보인다(gemma 가 예시의 개수를 베낀다). 근거를 모두 무관으로 빼면 남는 근거가 없으니 검색어를 제안하라는 규칙도 더한다 — 빼고 0편이면 러너가 판정과 무관하게 다시 찾는데, 충분 판정에는 검색어를 제안하지 않아 찾을 검색어가 없게 된다"
```

---

### Task 7: 근거 번호 evidence_seq, 제외 목록 excluded_cnts, 스냅샷

**Files:**
- Modify: `app/services/research/state.py`
- Modify: `app/services/research/runner.py`
- Test: `app/tests/test_research_state.py`
- Test: `app/tests/test_research_runner.py`

- [ ] **Step 1: 상태 실패 테스트 작성**

`app/tests/test_research_state.py`

교체 전:
```python
class TestResearchStats:
```
교체 후:
```python
class TestEvidenceSeq:
    """근거 번호는 늘리기만 한다 — 무관 근거를 지운 뒤에도 새 번호가 남은 번호와 겹치지 않게."""

    def test_new_state_starts_numbering_at_zero(self):
        assert ResearchState(job_id="j1", question="질문", params=merge_params({})).evidence_seq == 0

    def test_evidence_seq_survives_round_trip(self):
        st = _explored_state()
        st.evidence_seq = 7
        snap = snapshot_state(st)
        assert snap["evidence_seq"] == 7
        assert restore_state("j1", snap).evidence_seq == 7

    def test_old_snapshot_resumes_after_the_largest_number(self):
        # 개수(2)로 되살리면 다음 근거가 E3 을 받아 남아 있는 E3 을 덮어쓴다
        snap = snapshot_state(_explored_state())
        del snap["evidence_seq"]
        ev = snap["evidence"].pop("E0")
        snap["evidence"] = {"E3": ev, "E9": dict(ev, cnts_id="KCI_B")}
        assert restore_state("j1", snap).evidence_seq == 9

    def test_old_snapshot_without_evidence_starts_at_zero(self):
        snap = snapshot_state(_explored_state())
        del snap["evidence_seq"]
        snap["evidence"] = {}
        assert restore_state("j1", snap).evidence_seq == 0


class TestExcludedPapers:
    """하위질문이 무관하다고 뺀 논문 — 재개해도 같아야 한다."""

    def test_subquestion_has_no_excluded_papers_by_default(self):
        assert SubQuestion(idx=0, text="하위").excluded_cnts == []

    def test_excluded_papers_survive_round_trip(self):
        st = _explored_state()
        st.subquestions[0].excluded_cnts = ["KCI_X", "KCI_Y"]
        back = restore_state("j1", snapshot_state(st))
        assert [s.excluded_cnts for s in back.subquestions] == [["KCI_X", "KCI_Y"], [], []]

    def test_old_snapshot_without_excluded_papers_gets_empty_list(self):
        snap = snapshot_state(_explored_state())
        for sq in snap["subquestions"]:
            del sq["excluded_cnts"]
        assert [s.excluded_cnts for s in restore_state("j1", snap).subquestions] == [[], [], []]


class TestResearchStats:
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py -q
```
기대 출력: 마지막 줄 `7 failed, 53 passed`. 새 7개가 `AttributeError: 'ResearchState' object has no attribute 'evidence_seq'`·`KeyError: 'evidence_seq'`·`AttributeError: 'SubQuestion' object has no attribute 'excluded_cnts'`·`KeyError: 'excluded_cnts'` 로 실패한다.

- [ ] **Step 3: 상태 구현**

`app/services/research/state.py`(CRLF — Edit 도구)

교체 전:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query}].
    # verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다.
    rounds: list[dict] = field(default_factory=list)
```
교체 후:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query}].
    # verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다.
    rounds: list[dict] = field(default_factory=list)
    # 자기점검이 무관하다고 뺀 논문(cnts_id). 같은 하위질문의 다음 회차 검색에 다시 걸려도 넣지
    # 않는다 — 넣으면 같은 논문을 또 판정받고 또 빼며 회차를 태운다. 다른 하위질문은 막지 않는다.
    excluded_cnts: list[str] = field(default_factory=list)
```

교체 전:
```python
    subquestions: list[SubQuestion] = field(default_factory=list)
    evidence: dict[str, Evidence] = field(default_factory=dict)
```
교체 후:
```python
    subquestions: list[SubQuestion] = field(default_factory=list)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    # 다음 근거 번호 — evidence_id(evidence_seq) 로 쓰고 1 늘린다. 근거 수로 매기면 무관 근거를
    # 지운 뒤 새 근거가 남아 있는 번호를 다시 받아 그 근거를 덮어쓴다.
    evidence_seq: int = 0
```

교체 전:
```python
            for eid, ev in state.evidence.items()
        },
        # 집합은 JSONB 에 들어가지 않는다. 정렬해 두면 왕복 비교도 결정론적이다.
        "seen_cnts": sorted(state.seen_cnts),
    }
```
교체 후:
```python
            for eid, ev in state.evidence.items()
        },
        "evidence_seq": state.evidence_seq,
        # 집합은 JSONB 에 들어가지 않는다. 정렬해 두면 왕복 비교도 결정론적이다.
        "seen_cnts": sorted(state.seen_cnts),
    }
```

교체 전:
```python
    st.seen_cnts = _restored_seen_cnts(snap)
    return st
```
교체 후:
```python
    st.evidence_seq = _restored_evidence_seq(snap)
    st.seen_cnts = _restored_seen_cnts(snap)
    return st
```

교체 전:
```python
    if "seen_cnts" in snap:
        return set(snap["seen_cnts"])
    return {e["cnts_id"] for e in snap["evidence"].values()}
```
교체 후:
```python
    if "seen_cnts" in snap:
        return set(snap["seen_cnts"])
    return {e["cnts_id"] for e in snap["evidence"].values()}


def _restored_evidence_seq(snap: dict) -> int:
    """보강 전 스냅샷에는 evidence_seq 가 없다. 근거 수가 아니라 가장 큰 번호(E<n> 의 n)로
    되살린다 — 다음 번호가 남아 있는 번호와 겹치면 인용칩이 다른 논문을 가리킨다."""
    if "evidence_seq" in snap:
        return snap["evidence_seq"]
    return max((int(eid[1:]) for eid in snap["evidence"]), default=0)
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py -q
```
기대 출력: `60 passed`. `test_snapshot_carries_every_state_field`·`test_snapshot_carries_every_dataclass_field` 도 통과한다.

- [ ] **Step 5: 러너 번호 실패 테스트 작성**

`app/tests/test_research_runner.py`

교체 전:
```python
from services.research.state import ResearchState, SubQuestion, merge_params
```
교체 후:
```python
from services.research.state import Evidence, ResearchState, SubQuestion, merge_params
```

교체 전:
```python
_RELAY = "services.research.relay"
```
교체 후:
```python
class TestEvidenceNumbering:
    def test_new_evidence_never_takes_a_number_still_in_use(self):
        """근거 수로 번호를 매기면 지운 자리가 있을 때 새 근거가 남아 있는 번호를 받아 덮어쓴다."""
        st = ResearchState(job_id="j", question="q", params=merge_params({"max_recheck": 0}))
        st.evidence = {"E2": Evidence(id="E2", cnts_id="OLD", meta={"title": "남은 논문"})}
        st.evidence_seq = 2
        sq = SubQuestion(idx=0, text="가")
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_fake_explore,
                                        critique_fn=_FakeCritic(), emit=None))
        assert st.evidence["E2"].cnts_id == "OLD"
        assert sq.evidence_ids == ["E3"] and st.evidence["E3"].cnts_id == "A"
        assert st.evidence_seq == 3


_RELAY = "services.research.relay"
```

- [ ] **Step 6: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_runner.py -q -k TestEvidenceNumbering
```
기대 출력: `1 failed, 47 deselected` — `AssertionError: assert 'A' == 'OLD'`(개수 1로 번호를 매겨 E2 를 덮어쓴다).

- [ ] **Step 7: 러너 번호 구현**

`app/services/research/runner.py`

교체 전:
```python
                eid = evidence_id(len(state.evidence))
```
교체 후:
```python
                eid = evidence_id(state.evidence_seq)
                state.evidence_seq += 1
```

- [ ] **Step 8: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_state.py tests/test_research_runner.py tests/test_research_tasks.py -q
```
기대 출력: `200 passed` (state 60 + runner 48 + tasks 92).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `826 passed`.

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/state.py app/services/research/runner.py app/tests/test_research_state.py app/tests/test_research_runner.py
git commit -m "[Feat] round04c — 근거 번호를 개수가 아니라 늘리기만 하는 evidence_seq 로 매긴다: 무관 근거를 풀에서 지운 뒤 새 근거가 남아 있는 번호를 받아 그 근거를 덮어쓰지 않게. 스냅샷에 싣고, 없는 옛 스냅샷은 근거 수가 아니라 가장 큰 번호로 되살린다. 하위질문이 무관하다고 뺀 논문 목록(excluded_cnts)도 상태에 둔다(옛 스냅샷은 빈 목록)"
```

---

### Task 8: 러너에서 무관한 근거 빼기

**계약 추가:** `should_recheck(subq, *, recheck_count, max_recheck, emptied: bool = False)` 에 키워드 `emptied` 를 더한다. 이 회차에 무관 근거를 빼고 나니 0편이면 판정과 무관하게 재검색 대상이다.

**전제:** Task 1(예산)·Task 6(`Verdict.off_topic`)·Task 7(`excluded_cnts`·`evidence_seq`)이 적용돼 있다.

**조립 때 정한 것:** 앞 회차에 전체 상한이나 몫에 막혔던 후보가 제외로 자리가 빈 뒤 다음 회차에 채택될 수 있다. 그 후보가 로컬 집합(`capped`·`budget_capped`)에 남아 있으면 막힌 수가 그만큼 부풀어, 한계 문장이 실린 후보까지 "싣지 못했다"고 쓴다. 그래서 새 근거를 만들 때 두 집합에서 `discard` 한다. 하위질문은 하나씩 돌므로 한 탐색 안에서 막혔던 후보가 재사용 링크로 들어오는 일은 없다 — `discard` 는 새로 만드는 쪽에만 둔다.

**Files:**
- Modify: `app/services/research/critic.py`
- Modify: `app/services/research/runner.py`
- Modify: `app/services/research/state.py`(회차 이력 주석)
- Modify: `app/models/research.py`(step result 모양 주석 — 스키마 변경 없음)
- Test: `app/tests/test_research_critic.py`
- Test: `app/tests/test_research_runner.py`

- [ ] **Step 1: should_recheck 실패 테스트 작성**

`app/tests/test_research_critic.py`

교체 전:
```python
    def test_sufficient_stops(self):
        assert not should_recheck(self._sq("sufficient"), recheck_count=0, max_recheck=3)
```
교체 후:
```python
    def test_sufficient_stops(self):
        assert not should_recheck(self._sq("sufficient"), recheck_count=0, max_recheck=3)

    def test_emptied_by_exclusion_rechecks_even_if_sufficient(self):
        """무관 근거를 빼고 0편이면 '충분' 판정은 뺀 근거까지 보고 내린 것이다."""
        assert should_recheck(self._sq("sufficient"), recheck_count=0, max_recheck=3,
                              emptied=True)

    def test_emptied_still_stops_at_limit(self):
        assert not should_recheck(self._sq("sufficient"), recheck_count=3, max_recheck=3,
                                  emptied=True)
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py -q -k TestShouldRecheck
```
기대 출력: `2 failed, 4 passed, 37 deselected` — `TypeError: should_recheck() got an unexpected keyword argument 'emptied'`.

- [ ] **Step 3: should_recheck 구현**

`app/services/research/critic.py`

교체 전:
```python
def should_recheck(subq: SubQuestion, *, recheck_count: int, max_recheck: int) -> bool:
    return subq.verdict == "insufficient" and recheck_count < max_recheck
```
교체 후:
```python
def should_recheck(
    subq: SubQuestion, *, recheck_count: int, max_recheck: int, emptied: bool = False,
) -> bool:
    """emptied — 이 회차에 무관 근거를 빼고 나니 0편이다. 그때는 판정이 충분이어도 다시 찾는다 —
    그 판정은 뺀 근거까지 보고 내린 것이고, 근거 없는 "충분"은 없다."""
    return (subq.verdict == "insufficient" or emptied) and recheck_count < max_recheck
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_critic.py -q
```
기대 출력: `43 passed`.

- [ ] **Step 5: 러너 제외 실패 테스트 작성**

`app/tests/test_research_runner.py` — 회차 기록 기대값에 `excluded` 를 더한다.

교체 전:
```python
        assert sq.rounds == [
            {"round": 1, "query": "가", "found_chunks": 2, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1"},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None},
        ]
```
교체 후:
```python
        assert sq.rounds == [
            {"round": 1, "query": "가", "found_chunks": 2, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": "다른 검색어 1",
             "excluded": 0},
            {"round": 2, "query": "다른 검색어 1", "found_chunks": 3, "new_papers": 2,
             "verdict": "insufficient", "note": "부족", "next_query": None, "excluded": 0},
        ]
```

교체 전:
```python
             "next_query": c["next_query"]}
```
교체 후:
```python
             "next_query": c["next_query"], "excluded": c["excluded"]}
```

Task 7 의 `TestEvidenceNumbering` 과 `_RELAY` 사이에 제외 테스트를 더한다.

교체 전:
```python
_RELAY = "services.research.relay"
```
교체 후:
```python
class _ScriptedCritic:
    """회차마다 정해 둔 (판정, 무관 번호, 제안 검색어)를 낸다. 받은 근거 목록도 남긴다."""

    def __init__(self, *turns):
        self._turns = list(turns)
        self.seen: list[list] = []

    async def __call__(self, subq, evidence, *, params):
        self.seen.append(evidence)
        verdict, off_topic, queries = self._turns.pop(0)
        return Verdict(verdict, note="점검", new_queries=list(queries), off_topic=list(off_topic))


class TestOffTopicExclusion:
    """자기점검이 무관하다고 가리킨 근거는 그 하위질문에서 빠진다 — 같은 단어를 다른 뜻으로 쓴
    논문이 절에 실리지 않게."""

    def _state(self, *texts, **params):
        st = ResearchState(job_id="j", question="q", params=merge_params(params))
        st.subquestions = [SubQuestion(idx=i, text=t) for i, t in enumerate(texts)]
        return st

    def _run(self, st, sq, table, critic, emit=None):
        asyncio.run(explore_subquestion(st, sq, db=None, explore_fn=_explore_table(table),
                                        critique_fn=critic, emit=emit))

    def _cnts(self, st, ids):
        return [st.evidence[e].cnts_id for e in ids]

    def test_off_topic_evidence_leaves_the_subquestion_and_the_pool(self):
        st = self._state("가", max_recheck=0)
        (sq,) = st.subquestions
        self._run(st, sq, {"가": ["A", "B", "C"]}, _ScriptedCritic(("sufficient", [2], [])))
        assert self._cnts(st, sq.evidence_ids) == ["A", "C"]
        # 어느 하위질문도 쓰지 않는 근거를 남기면 어느 절에도 실리지 않은 채 전체 상한만 차지한다
        assert "E2" not in st.evidence and len(st.evidence) == 2
        assert "E2" not in sq.evidence_chunks and "B-c-가" not in sq.chunk_scores
        assert sq.excluded_cnts == ["B"]

    def test_evidence_another_subquestion_uses_stays_in_the_pool(self):
        """같은 논문이 다른 하위질문에는 관련 있을 수 있다 — 그쪽 링크를 끊지 않는다."""
        st = self._state("가", "나", max_recheck=0)
        sq1, sq2 = st.subquestions
        table = {"가": ["A", "B"], "나": ["B", "C"]}
        self._run(st, sq1, table, _ScriptedCritic(("sufficient", [], [])))
        self._run(st, sq2, table, _ScriptedCritic(("sufficient", [1], [])))
        assert sq2.evidence_ids == ["E3"]
        assert sq1.evidence_ids == ["E1", "E2"] and st.evidence["E2"].cnts_id == "B"
        assert sq2.excluded_cnts == ["B"] and sq1.excluded_cnts == []

    def test_excluded_paper_is_not_taken_back_in_a_later_round(self):
        """다시 넣으면 같은 논문을 또 판정받고 또 빼며 회차를 태운다."""
        st = self._state("가", max_recheck=1)
        (sq,) = st.subquestions
        critic = _ScriptedCritic(("insufficient", [2], ["보완"]), ("sufficient", [], []))
        self._run(st, sq, {"가": ["A", "B"], "보완": ["B", "C"]}, critic)
        assert self._cnts(st, sq.evidence_ids) == ["A", "C"]
        assert [e.cnts_id for e in critic.seen[1]] == ["A", "C"]
        # 지운 E2 의 번호를 C 가 다시 받지 않는다
        assert sq.evidence_ids == ["E1", "E3"]

    def test_other_subquestion_may_still_adopt_the_paper(self):
        st = self._state("가", "나", max_recheck=0)
        sq1, sq2 = st.subquestions
        table = {"가": ["A", "B"], "나": ["B"]}
        self._run(st, sq1, table, _ScriptedCritic(("sufficient", [2], [])))
        self._run(st, sq2, table, _ScriptedCritic(("sufficient", [], [])))
        assert sq2.evidence_ids == ["E3"] and st.evidence["E3"].cnts_id == "B"

    def test_subquestion_emptied_by_exclusion_searches_again_even_if_judged_sufficient(self):
        """근거 없는 '충분'은 없다 — 그 판정은 뺀 근거까지 보고 내린 것이다."""
        st = self._state("가", max_recheck=1)
        (sq,) = st.subquestions
        # 모두 뺐으면 판정이 충분이어도 검색어를 제안하라고 프롬프트가 요구한다(research_critique.yaml)
        critic = _ScriptedCritic(("sufficient", [1], ["보완"]), ("sufficient", [], []))
        self._run(st, sq, {"가": ["A"], "보완": ["C"]}, critic)
        assert sq.queries == ["가", "보완"]
        assert self._cnts(st, sq.evidence_ids) == ["C"]

    def test_excluded_count_is_recorded_and_streamed(self):
        events, emit = _recorder()
        st = self._state("가", max_recheck=1)
        (sq,) = st.subquestions
        critic = _ScriptedCritic(("insufficient", [1, 3], ["보완"]), ("sufficient", [], []))
        self._run(st, sq, {"가": ["A", "B", "C"], "보완": ["D"]}, critic, emit=emit)
        assert [r["excluded"] for r in sq.rounds] == [2, 0]
        critiques = _of(events, "critique")
        assert [c["excluded"] for c in critiques] == [2, 0]
        # 뺀 뒤의 수다 — 화면의 채택 수와 한계 문장이 같은 값을 본다
        assert critiques[0]["adopted"] == 1

    def test_freed_budget_lets_the_subquestion_search_again(self):
        """예산은 지금 남아 있는 자기 근거로 센다 — 무관 제외로 자리가 비면 재검색이 새 근거를 만든다."""
        st = self._state("가", "나", max_recheck=1, max_evidence=4, min_evidence_per_subq=0)
        sq = st.subquestions[0]            # 예산 4 // 2 = 2 — A·B 를 만들고 C 는 막힌다
        critic = _ScriptedCritic(("insufficient", [1], ["보완"]), ("sufficient", [], []))
        self._run(st, sq, {"가": ["A", "B", "C"], "보완": ["A", "D"]}, critic)
        assert sq.queries == ["가", "보완"]
        assert set(self._cnts(st, sq.evidence_ids)) == {"B", "D"}

    def test_candidate_adopted_after_a_freed_seat_is_not_counted_as_blocked(self):
        """앞 회차에 몫에 막혔던 후보가 제외로 빈 자리에 실리면 '싣지 못한 후보'가 아니다 —
        그대로 세면 한계 문장이 실린 논문까지 싣지 못했다고 쓴다."""
        st = self._state("가", "나", max_recheck=1, max_evidence=4, min_evidence_per_subq=0)
        sq = st.subquestions[0]            # 예산 2 — 1회차에 A·B 를 만들고 C 는 막힌다
        critic = _ScriptedCritic(("insufficient", [1], ["보완"]), ("sufficient", [], []))
        self._run(st, sq, {"가": ["A", "B", "C"], "보완": ["C", "D"]}, critic)
        assert set(self._cnts(st, sq.evidence_ids)) == {"B", "C"}
        assert sq.budget_capped == 1       # 2회차에 막힌 D 뿐이다


_RELAY = "services.research.relay"
```

- [ ] **Step 6: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_runner.py -q -k "TestOffTopicExclusion or TestRoundHistory"
```
기대 출력: 마지막 줄 `10 failed, 46 deselected`.
- TestRoundHistory 2개: 기록에 `excluded` 가 없어 `AssertionError` 와 `KeyError: 'excluded'`.
- TestOffTopicExclusion 8개: 제외가 적용되지 않아 `AssertionError`, excluded 기록 테스트는 `KeyError: 'excluded'`.

- [ ] **Step 7: 러너 제외 구현**

`app/services/research/runner.py`(CRLF — Edit 도구)

`_mark_seen` 뒤에 제외 함수를 더한다.

교체 전:
```python
    fresh = {h["book_id"] for h in hits if h["book_id"] in meta} - state.seen_cnts
    state.seen_cnts |= fresh
    return len(fresh)
```
교체 후:
```python
    fresh = {h["book_id"] for h in hits if h["book_id"] in meta} - state.seen_cnts
    state.seen_cnts |= fresh
    return len(fresh)


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

`_recheck_query` 는 첫 검사만 바꾼다. Task 1 이 더한 예산 검사와 전체 상한 검사는 그대로 둔다. 제외가 먼저 끝나 있어서 두 검사 모두 줄어든 수를 본다.

교체 전:
```python
    params = state.params
    if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"]):
        return None
```
교체 후:
```python
    params = state.params
    # verdict.off_topic 이 있으면 이 회차에 그만큼 뺐다(_exclude_off_topic)
    emptied = bool(verdict.off_topic) and not subq.evidence_ids
    if not should_recheck(subq, recheck_count=recheck, max_recheck=params["max_recheck"],
                          emptied=emptied):
        return None
```

후보 루프에서 이 하위질문이 뺀 논문은 건너뛴다.

교체 전:
```python
        ):
            eid = known_by_cnts.get(cand.cnts_id)
```
교체 후:
```python
        ):
            if cand.cnts_id in subq.excluded_cnts:
                continue
            eid = known_by_cnts.get(cand.cnts_id)
```

새 근거를 만들면 앞 회차에 막혔던 기록에서 뺀다.

교체 전:
```python
                made.add(eid)
                own += 1
```
교체 후:
```python
                made.add(eid)
                own += 1
                # 앞 회차에 상한·몫에 막혔던 후보가 무관 제외로 빈 자리에 실렸다 — 막힌 수로 남기면
                # 한계 문장이 실린 논문까지 "싣지 못했다"고 쓴다
                capped.discard(cand.cnts_id)
                budget_capped.discard(cand.cnts_id)
```

판정 뒤, 재검색 결정 전에 뺀다.

교체 전:
```python
        # 마지막 라운드 값으로 덮어써도 된다(OR 누적이 필요 없다): 판정 불가는
        # verdict="sufficient" 로 떨어지고 should_recheck 는 "insufficient" 일 때만
        # True 이므로, 판정 불가가 난 라운드가 항상 마지막 라운드다.
        subq.parse_failed = verdict.parse_failed
```
교체 후:
```python
        # 마지막 라운드 값으로 덮어써도 된다(OR 누적이 필요 없다): 판정 불가는
        # verdict="sufficient" 에 무관 번호가 비어 있고, should_recheck 는 "insufficient"
        # 이거나 무관 근거를 빼 0편이 됐을 때만 True 이므로, 판정 불가가 난 라운드가 항상
        # 마지막 라운드다.
        subq.parse_failed = verdict.parse_failed
        excluded = _exclude_off_topic(state, subq, verdict.off_topic)
```

교체 전:
```python
            "note": verdict.note, "next_query": next_query,
        })
```
교체 후:
```python
            "note": verdict.note, "next_query": next_query, "excluded": excluded,
        })
```

교체 전:
```python
            "round": round_no, "next_query": next_query,
            "will_recheck": next_query is not None,
```
교체 후:
```python
            "round": round_no, "next_query": next_query, "excluded": excluded,
            "will_recheck": next_query is not None,
```

`app/services/research/state.py` — 회차 이력 주석을 고친다.

교체 전:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query}].
    # verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다.
```
교체 후:
```python
    # 회차 이력 — [{round, query, found_chunks, new_papers, verdict, note, next_query, excluded}].
    # verdict·note 는 마지막 회차 값만 남으므로, 이게 없으면 끝난 잡을 다시 열었을 때
    # "근거 부족 → 재검색" 장면을 보여 줄 원천이 없다. excluded(그 회차에 무관하다고 뺀 수)는
    # 보강 전 잡의 회차에는 없다.
```

`app/models/research.py` — step result 모양 주석만 고친다(컬럼·스키마는 그대로).

교체 전:
```python
    #              "rounds": [{"round", "query", "found_chunks", "new_papers",
    #                          "verdict", "note", "next_query"}],
```
교체 후:
```python
    #              "rounds": [{"round", "query", "found_chunks", "new_papers",
    #                          "verdict", "note", "next_query", "excluded"?}],
    #             excluded 는 그 회차 자기점검이 무관하다고 뺀 근거 수(보강 전 잡의 회차에는 없다).
```

- [ ] **Step 8: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `836 passed`(백엔드 전체).

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/critic.py app/services/research/runner.py app/services/research/state.py app/models/research.py app/tests/test_research_critic.py app/tests/test_research_runner.py
git commit -m "[Feat] round04c — 러너가 자기점검이 무관하다고 가리킨 근거를 그 하위질문에서 뺀다: 목록 번호를 evidence_ids 로 되돌려 링크·매칭 대목을 걷고, 다른 하위질문이 쓰지 않으면 풀에서도 지우며, 같은 하위질문의 다음 회차 검색에 다시 걸려도 넣지 않는다(다른 하위질문은 막지 않는다). 빼고 나니 0편이면 판정이 충분이어도 재검색 대상으로 본다 — 근거 없는 충분은 없다. 비운 자리만큼 하위질문 예산·전체 상한이 풀려 재검색이 새 근거를 만들고, 앞 회차에 막혔다가 그 자리에 실린 후보는 막힌 수에서 뺀다. 회차 기록과 critique 이벤트에 excluded(이번 회차에 뺀 수)를 싣는다"
```

---

### Task 9: 보고서 trail 에 excluded 싣기

**Files:**
- Modify: `app/services/research/synthesizer.py`
- Test: `app/tests/test_research_synthesizer.py`

- [ ] **Step 1: 실패 테스트 작성**

`app/tests/test_research_synthesizer.py`

교체 전:
```python
    def test_corpus_range_is_carried_into_report(self):
```
교체 후:
```python
    def test_trail_carries_excluded_count(self):
        """문서 부록과 옛 잡 타임라인의 '무관 N편 제외' 원천이다."""
        st = _state()
        st.subquestions[0].excluded_cnts = ["X", "Y"]
        trail = assemble_report(st, sections=[], unmarked_total=0)["trail"]
        assert [t["excluded"] for t in trail] == [2, 0]

    def test_corpus_range_is_carried_into_report(self):
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_synthesizer.py -q -k excluded
```
기대 출력: `1 failed, 105 deselected` — `KeyError: 'excluded'`.

- [ ] **Step 3: 구현**

`app/services/research/synthesizer.py`(CRLF — Edit 도구)

교체 전:
```python
             "parse_failed": sq.parse_failed, "failed": sq.failed, "capped": sq.capped}
```
교체 후:
```python
             "parse_failed": sq.parse_failed, "failed": sq.failed, "capped": sq.capped,
             # 자기점검이 이 하위질문에서 무관하다고 뺀 논문 수 — 한 번 뺀 논문은 다시 들지 않는다
             "excluded": len(sq.excluded_cnts)}
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests/test_research_synthesizer.py tests/test_research_tasks.py -q
```
기대 출력: `198 passed` (synthesizer 106 + tasks 92).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `837 passed`.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add app/services/research/synthesizer.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04c — 보고서 탐색 경로(trail)에 하위질문이 무관하다고 뺀 논문 수(excluded)를 싣는다: 문서 부록과 옛 잡 타임라인의 '무관 N편 제외' 원천. 한 번 뺀 논문은 같은 하위질문에 다시 들지 않으므로 제외 목록 길이가 곧 뺀 총수다"
```

---

## 단계 3 — 화면 (Task 10·11)

- 백엔드는 회차 dict(`subq.rounds[]`)와 `critique` 이벤트에는 `"excluded": int`(이번 회차에 뺀 수)를, `trail[]` 에는 `"excluded": int`(하위질문에서 뺀 총수)를 싣는다(Task 8·9). 이 단계는 그 두 이름을 그대로 읽는다.
- 제외 뒤 근거가 0편이 되어 재검색하는 경우(spec §4)에는 판정이 `sufficient` 인데도 재검색이 일어난다. 그러면 강조 카드는 기존 고정 문구 "근거 부족 → '…'(으)로 재검색"을 보이고, 회차 줄에는 "근거 충분 — note" 와 "→ 재검색", "무관 N편 제외"가 함께 보인다. 근거가 0편이라 뜻이 틀리지는 않아 이번 범위에서는 두었다.

### Task 10: 탐색 타임라인의 회차 줄에 "무관 N편 제외" 표시

**계약 추가:** `frontend/utils/researchEvents.ts` 에 `export function excludedLabel(n: number | null): string | null` 를 둔다. 타임라인 회차 줄과 문서 부록이 같은 문구를 쓰도록 문구 규칙을 이 함수 한 곳에 모은다. 반환값은 `n > 0` 이면 `"무관 N편 제외"`, 0 이거나 null 이면 `null` 이다. `verdictLabel` 과 같은 자리·같은 쓰임새다.

화면은 회차 결과(`SearchRoundResult`), `critique` 이벤트, `TrailItem` 의 `excluded` 를 통과시킨다. `RoundView.excluded` 는 필수 칸(`number | null`)이다. 이 필드가 없는 옛 잡은 null 이 되어 아무것도 표시하지 않는다(spec §4 화면). 컴포넌트는 단위 테스트하지 않는다(기존 방침). 문구와 "있을 때만" 규칙은 `excludedLabel` 테스트로 고정하고, 패널은 typecheck·build 로 확인한다.

**Files:**
- Modify: `frontend/types/research.ts`
- Modify: `frontend/utils/researchEvents.ts`
- Modify: `frontend/components/research/ProgressPanel.vue`
- Test: `frontend/tests/unit/researchEvents.test.ts`
- Modify: `frontend/tests/unit/reportDocument.test.ts` — `round()` 헬퍼 한 줄만 고친다. `RoundView` 에 필수 칸이 늘어 이 헬퍼에서 typecheck 가 깨지기 때문이다.

- [ ] **Step 1: 실패 테스트 작성 (`frontend/tests/unit/researchEvents.test.ts`)**

(1) import 에 `excludedLabel` 을 더한다.

교체 전:
```ts
  applyResearchEvent,
  initialResearchView,
```
교체 후:
```ts
  applyResearchEvent,
  excludedLabel,
  initialResearchView,
```

(2) 테스트 "검색·점검 이벤트로 회차를 쌓고 재검색 장면을 강조한다"(166~167행)의 기대값에 `excluded: null` 을 더한다. 이 테스트의 critique 이벤트는 excluded 를 싣지 않는다(옛 서버). 2회차는 점검 전이다.

교체 전:
```ts
      { round: 1, query: "효과 측정", foundChunks: 12, newPapers: 5, verdict: "insufficient", note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과" },
      { round: 2, query: "초등 AI 윤리 교육 효과", foundChunks: 9, newPapers: 4, verdict: null, note: "", nextQuery: null },
```
교체 후:
```ts
      { round: 1, query: "효과 측정", foundChunks: 12, newPapers: 5, verdict: "insufficient", note: "초등 대상 연구가 없다", nextQuery: "초등 AI 윤리 교육 효과", excluded: null },
      { round: 2, query: "초등 AI 윤리 교육 효과", foundChunks: 9, newPapers: 4, verdict: null, note: "", nextQuery: null, excluded: null },
```

(3) `describe("applyResearchEvent — 탐색")` 끝에 두 테스트를 붙이고, 그 뒤에 `describe("excludedLabel")` 를 더한다.

교체 전:
```ts
    expect(v.subqs[0]!.rounds.map((r) => [r.round, r.note])).toEqual([[1, "저장본"], [2, ""]]);
    expect(v.source).toBe("rounds");
  });
});
```
교체 후:
```ts
    expect(v.subqs[0]!.rounds.map((r) => [r.round, r.note])).toEqual([[1, "저장본"], [2, ""]]);
    expect(v.source).toBe("rounds");
  });

  it("점검 이벤트의 excluded(이번 회차에 무관하다고 뺀 근거 수)를 그 회차에 싣는다", () => {
    const v = run([
      SEARCH_STARTED,
      { kind: "search", subq_idx: 0, query: "효과 측정", found: 12, round: 1, new_papers: 5 },
      {
        kind: "critique", subq_idx: 0, verdict: "insufficient", note: "초등 대상 연구가 없다", adopted: 3,
        parse_failed: false, capped: 0, excluded: 2, round: 1, next_query: "초등 AI 윤리 교육 효과", will_recheck: true,
      },
      { kind: "search", subq_idx: 0, query: "초등 AI 윤리 교육 효과", found: 9, round: 2, new_papers: 4 },
    ]);
    // 2회차는 아직 점검 전이다
    expect(v.subqs[0]!.rounds.map((r) => [r.round, r.excluded])).toEqual([[1, 2], [2, null]]);
  });

  it("진행 저장본의 회차 excluded 를 다시 연 화면·재접속 snapshot 이 같게 받고, 필드가 없는 회차는 비워 둔다", () => {
    const saved = step({ ...SAVED_SEARCH_ROW, result: { rounds: [{ ...ROUND1, excluded: 2 }, ROUND2], counters: LIVE } });
    const opened = initialResearchView(job({ steps: [PLAN_ROW, saved] }));
    const snap = applyResearchEvent(initialResearchView(job()), { kind: "snapshot", steps: [PLAN_ROW, saved] });
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

(4) 테스트 "단계 결과에 rounds 가 없으면 report.trail 로 회차를 대신 보여 준다"(750~751행)의 기대값에도 `excluded: null` 을 더한다. 회차 기록이 없는 옛 잡은 무관 제외 기능보다 먼저 만들어졌다.

교체 전:
```ts
      { round: 1, query: "효과 측정", foundChunks: null, newPapers: null, verdict: "insufficient", note: "", nextQuery: "초등 효과" },
      { round: 2, query: "초등 효과", foundChunks: null, newPapers: null, verdict: "sufficient", note: "충분하다", nextQuery: null },
```
교체 후:
```ts
      { round: 1, query: "효과 측정", foundChunks: null, newPapers: null, verdict: "insufficient", note: "", nextQuery: "초등 효과", excluded: null },
      { round: 2, query: "초등 효과", foundChunks: null, newPapers: null, verdict: "sufficient", note: "충분하다", nextQuery: null, excluded: null },
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchEvents.test.ts
```
기대 출력: `Tests  5 failed | 76 passed (81)`. 실패하는 테스트는 다음 다섯이다.
- 검색·점검 이벤트로 회차를 쌓고 재검색 장면을 강조한다 — `expected [ …(2) ] to deeply equal [ …(2) ]`
- 점검 이벤트의 excluded(…)를 그 회차에 싣는다 — `expected [ [ 1, undefined ], [ 2, undefined ] ] to deeply equal [ [ 1, 2 ], [ 2, null ] ]`
- 진행 저장본의 회차 excluded 를 … 비워 둔다 — 위와 같은 메시지
- excludedLabel > … — `TypeError: (0 , excludedLabel) is not a function`
- 단계 결과에 rounds 가 없으면 report.trail 로 회차를 대신 보여 준다 — `expected [ …(2) ] to deeply equal [ …(2) ]`

- [ ] **Step 3: 타입 (`frontend/types/research.ts`)**

(1) `SearchRoundResult`

교체 전:
```ts
  note?: string | null;
  next_query?: string | null;
}
```
교체 후:
```ts
  note?: string | null;
  next_query?: string | null;
  // 자기점검이 무관하다고 보고 이 회차에 뺀 근거 수 — 무관 제외 전 잡의 회차에는 없다
  excluded?: number | null;
}
```

(2) `TrailItem`

교체 전:
```ts
  failed: boolean;
  capped: number;
}
```
교체 후:
```ts
  failed: boolean;
  capped: number;
  // 하위질문에서 무관하다고 뺀 근거 총수 — 무관 제외 전 보고서에는 없다
  excluded?: number | null;
}
```

(3) `CritiqueEvent`

교체 전:
```ts
  parse_failed: boolean;
  capped: number;
  round?: number;
```
교체 후:
```ts
  parse_failed: boolean;
  capped: number;
  // 이번 회차에 무관하다고 뺀 근거 수 — 무관 제외 전 워커는 보내지 않는다
  excluded?: number | null;
  round?: number;
```

(4) `RoundView`

교체 전:
```ts
  note: string;
  nextQuery: string | null;
}
```
교체 후:
```ts
  note: string;
  nextQuery: string | null;
  excluded: number | null;
}
```

- [ ] **Step 4: 이벤트 합치기 (`frontend/utils/researchEvents.ts`)**

(1) `verdictLabel` 바로 뒤에 `excludedLabel` 을 둔다.

교체 전:
```ts
export function verdictLabel(verdict: Verdict): string {
  return VERDICT_LABEL[verdict];
}
```
교체 후:
```ts
export function verdictLabel(verdict: Verdict): string {
  return VERDICT_LABEL[verdict];
}

// 자기점검이 하위질문의 핵심과 무관하다고 보고 뺀 근거 수 — 타임라인 회차 줄과 문서 부록이 같은
// 문구를 쓴다. 뺀 것이 없거나 무관 제외 전 잡(null)이면 적지 않는다
export function excludedLabel(n: number | null): string | null {
  return n ? `무관 ${n}편 제외` : null;
}
```

(2) `applyCritique` 는 이번 회차에 뺀 수를 그 회차에 싣는다.

교체 전:
```ts
      verdict: event.verdict,
      note: event.note,
      nextQuery: event.next_query ?? null,
    };
```
교체 후:
```ts
      verdict: event.verdict,
      note: event.note,
      nextQuery: event.next_query ?? null,
      excluded: event.excluded ?? null,
    };
```

(3) `roundsFromQueries` — 칸을 채우고, 주석이 가리키던 `should_recheck` 규칙이 이제 더 넓어졌으므로(무관 근거를 빼고 0편이면 충분 판정이어도 재검색한다) 이 함수가 받는 입력이 옛 잡뿐임을 적는다.

교체 전:
```ts
// 재검색은 판정이 부족일 때만 일어난다(critic.should_recheck) — 마지막 전 회차는 모두 부족이다
```
교체 후:
```ts
// 회차 기록이 없는 옛 잡에서 재검색은 판정이 부족일 때만 일어났다(무관 제외 전이다) — 마지막 전 회차는 모두 부족이다
```

교체 전:
```ts
    nextQuery: i < last ? (queries[i + 1] ?? null) : null,
  }));
```
교체 후:
```ts
    nextQuery: i < last ? (queries[i + 1] ?? null) : null,
    excluded: null,
  }));
```

(4) `toRoundView` 는 저장본(snapshot·GET·진행 저장 step)의 회차를 통과시킨다.

교체 전:
```ts
    note: r.note ?? "",
    nextQuery: r.next_query ?? null,
  };
}
```
교체 후:
```ts
    note: r.note ?? "",
    nextQuery: r.next_query ?? null,
    excluded: r.excluded ?? null,
  };
}
```

(5) `blankRound`

교체 전:
```ts
  return { round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null };
```
교체 후:
```ts
  return {
    round, query: "", foundChunks: null, newPapers: null, verdict: null, note: "", nextQuery: null, excluded: null,
  };
```

(6) `reconcileCounters` 의 주석을 고친다. 채택한 근거 수(`evidence_adopted = len(state.evidence)`)는 이제 무관 근거를 풀에서 지우면 준다. 합치는 규칙(필드별 큰 값)은 그대로 둔다 — 라이브 `counters`·`step` 이벤트는 받은 값을 그대로 쓰므로, 끊긴 사이의 잠깐 어긋남은 다음 이벤트가 바로잡는다. 새 두 줄은 기존 "다만 …" 두 줄 뒤에 둔다 — 앞에 두면 "다만" 이 가리키는 규칙(필드별 큰 값)과 떨어진다.

교체 전:
```ts
// 라이브 카운터와 저장본(스냅샷·GET) 카운터를 합친다. 한 시도 안에서 카운터는 줄지 않는다
// (research_stats 의 seen_cnts·evidence·queries 는 늘기만 한다). 저장본은 자기점검(LLM)이
// 끝나야 쓰여 점검을 기다리는 동안 검색 직후 받은 counters 이벤트보다 한 회차 뒤처지고,
// 반대로 스트림이 끊긴 사이에는 저장본이 앞선다 — 그래서 필드별로 큰 값을 남긴다.
// 다만 화면이 모르는 뒤 단계에서 나온 저장본은 그대로 쓴다. 탐색부터 다시 도는 재시도는
// 카운터를 0 부터 새로 세므로, 큰 값을 남기면 이전 시도의 숫자가 버티고 선다.
```
교체 후:
```ts
// 라이브 카운터와 저장본(스냅샷·GET) 카운터를 합친다. 한 시도 안에서 검토한 논문·재검색은
// 줄지 않는다(research_stats 의 seen_cnts·queries 는 늘기만 한다). 저장본은 자기점검(LLM)이
// 끝나야 쓰여 점검을 기다리는 동안 검색 직후 받은 counters 이벤트보다 한 회차 뒤처지고,
// 반대로 스트림이 끊긴 사이에는 저장본이 앞선다 — 그래서 필드별로 큰 값을 남긴다.
// 다만 화면이 모르는 뒤 단계에서 나온 저장본은 그대로 쓴다. 탐색부터 다시 도는 재시도는
// 카운터를 0 부터 새로 세므로, 큰 값을 남기면 이전 시도의 숫자가 버티고 선다.
// 채택한 근거는 자기점검이 무관 근거를 풀에서 지우면 준다. 끊긴 사이 저장본이 지운 뒤의 값이면
// 이 규칙이 지우기 전의 수를 잠시 남기지만, 다음 counters·step 이벤트가 받은 값으로 바로잡는다.
```

`applySearch` 는 `...(existing ?? blankRound(round))` 로 펼치기 때문에 점검에서 받은 excluded 를 지우지 않는다. `mergeRounds` 는 저장본을 먼저 쓰므로 저장본의 값이 이긴다. 두 곳 모두 고칠 것이 없다.

- [ ] **Step 5: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchEvents.test.ts
```
기대 출력: `Tests  81 passed (81)`

- [ ] **Step 6: 타임라인 회차 줄 (`frontend/components/research/ProgressPanel.vue`)**

(1) import

교체 전:
```ts
import { stopPoint, subqStatusLabel, synthProgress, verdictLabel, type ResearchPhase } from "~/utils/researchEvents";
```
교체 후:
```ts
import {
  excludedLabel,
  stopPoint,
  subqStatusLabel,
  synthProgress,
  verdictLabel,
  type ResearchPhase,
} from "~/utils/researchEvents";
```

(2) 회차 줄의 통계 칸(`rs-round__stat`) 뒤에 붙인다. critique 이벤트가 오는 순간 그 회차 줄에 나타나서, 자기점검이 걸러내는 장면이 실시간으로 보인다.

교체 전:
```vue
                <span v-if="r.newPapers !== null" class="rs-round__stat">새 논문 {{ r.newPapers }}편</span>
```
교체 후:
```vue
                <span v-if="r.newPapers !== null" class="rs-round__stat">새 논문 {{ r.newPapers }}편</span>
                <span v-if="excludedLabel(r.excluded)" class="rs-round__stat">{{ excludedLabel(r.excluded) }}</span>
```

CSS 는 바꾸지 않는다. 기존 `.rs-round__stat` 과 flex `gap` 을 그대로 쓴다.

- [ ] **Step 7: `round()` 헬퍼의 타입 맞추기 (`frontend/tests/unit/reportDocument.test.ts`)**

`RoundView` 에 필수 칸이 늘었기 때문에, 이 줄을 고치지 않으면 typecheck 가 다음 오류를 낸다: `tests/unit/reportDocument.test.ts(337,3): error TS2741: Property 'excluded' is missing in type … but required in type 'RoundView'.`

교체 전:
```ts
  return { round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null };
```
교체 후:
```ts
  return { round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null, excluded: null };
```

- [ ] **Step 8: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1
```
기대 출력:
- 첫 명령: `Test Files  21 passed (21)` · `Tests  386 passed (386)`(`738bc07` 의 383개에서 3개가 늘었다).
- 둘째 명령: 출력 없음.
- 셋째 명령: `└  ✨ Build complete!`

실제 화면은 운영 전후 비교(spec §7 ③)에서 확인한다. 엣지·HPC 하위질문의 회차 줄에 "무관 N편 제외"가 나오는지 본다.

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add frontend/types/research.ts frontend/utils/researchEvents.ts frontend/components/research/ProgressPanel.vue frontend/tests/unit/researchEvents.test.ts frontend/tests/unit/reportDocument.test.ts
git status --short
git commit -m "[Feat] round04c — 탐색 타임라인 회차 줄에 자기점검이 무관하다고 뺀 근거 수(\"무관 N편 제외\")를 보인다: 회차 결과·critique 이벤트·trail 의 excluded 를 타입과 이벤트 합치기가 통과시키고(옛 잡은 null 이라 적지 않는다), 문구는 타임라인과 문서 부록이 같이 쓸 excludedLabel 한 곳에서 만든다. 채택 수가 무관 제외로 줄 수 있게 된 것을 카운터 합치기 주석에 적는다"
```
`git status --short` 로 staged 목록에 위 5개만 있는지 확인한다. 착수 때부터 수정돼 있던 `frontend/pages/research/[id].vue` 는 이 작업의 파일이 아니므로 add 하지 않는다.

---

### Task 11: 문서(Word·PDF) 부록에 "무관 N편 제외"

**계약 추가:** `frontend/utils/reportDocument.ts` 의 `DocTrailItem` 에 `excluded: number` 를 더한다. 값의 출처는 다음과 같다.
- 최종본: `trail[].excluded ?? 0`
- 초안: 타임라인 회차의 `excluded` 합. 초안 부록은 원래 `view.subqs` 에서 만든다.

부록은 `excludedLabel` 을 거쳐 0 이면 적지 않는다. 그래서 옛 잡의 0 과 "뺀 것 없음"은 둘 다 표시되지 않는다. Task 10 의 `excludedLabel` 과 `RoundView.excluded` 가 먼저 있어야 한다.

**Files:**
- Modify: `frontend/utils/reportDocument.ts`
- Test: `frontend/tests/unit/reportDocument.test.ts`

- [ ] **Step 1: 실패 테스트 작성 (`frontend/tests/unit/reportDocument.test.ts`)**

(1) 구성 테스트의 부록 항목(101행)에 새 칸을 채운다. 출력 기대값은 그대로다.

교체 전:
```ts
          { subquestion: "규제 논의의 흐름", queries: ["AI 규제", "AI 규제 샌드박스"], verdict: "sufficient", evidenceCount: 1 },
```
교체 후:
```ts
          { subquestion: "규제 논의의 흐름", queries: ["AI 규제", "AI 규제 샌드박스"], verdict: "sufficient", evidenceCount: 1, excluded: 0 },
```

(2) "부록은 … 모르는 칸은 뺀다"(150~151행). 0 은 적지 않으므로 기대값은 그대로다.

교체 전:
```ts
          { subquestion: "가", queries: ["가"], verdict: "insufficient", evidenceCount: 0 },
          { subquestion: "나", queries: [], verdict: null, evidenceCount: null },
```
교체 후:
```ts
          { subquestion: "가", queries: ["가"], verdict: "insufficient", evidenceCount: 0, excluded: 0 },
          { subquestion: "나", queries: [], verdict: null, evidenceCount: null, excluded: 0 },
```

(3) 그 테스트 바로 뒤에 새 테스트를 넣는다.

교체 전:
```ts
      "heading2: 2. 나",
    ]);
  });

  it("탐색 경로가 없으면 부록을 싣지 않는다", () => {
```
교체 후:
```ts
      "heading2: 2. 나",
    ]);
  });

  it("부록은 자기점검이 무관하다고 뺀 근거 수를 탐색 타임라인과 같은 문구로 싣는다", () => {
    const doc = buildReportDocument(
      input({
        trail: [
          { subquestion: "엣지 컴퓨팅", queries: ["엣지 컴퓨팅", "엣지 컴퓨팅 자원 할당"], verdict: "sufficient", evidenceCount: 6, excluded: 3 },
        ],
      }),
      NOW,
    );
    const all = lines(doc);
    expect(all.slice(all.indexOf("heading1: 부록: 탐색 경로"))).toEqual([
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 엣지 컴퓨팅",
      "bullets: 검색어: ‘엣지 컴퓨팅’ → ‘엣지 컴퓨팅 자원 할당’ (재검색 1회) / 판정: 근거 충분 / 채택한 근거: 6편 / 무관 3편 제외",
    ]);
  });

  it("탐색 경로가 없으면 부록을 싣지 않는다", () => {
```

(4) 제어문자 테스트(186행)

교체 전:
```ts
        trail: [{ subquestion: "하위\u0002질문", queries: ["검색\u0003어"], verdict: null, evidenceCount: null }],
```
교체 후:
```ts
        trail: [{ subquestion: "하위\u0002질문", queries: ["검색\u0003어"], verdict: null, evidenceCount: null, excluded: 0 }],
```

(5) `docInputFromReport`: trail 의 excluded 를 통과시키고, 필드가 없는 옛 trail 은 0 으로 받는다.

교체 전:
```ts
        { subquestion: "가", queries: ["가", "가2"], evidence_count: 2, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
        { subquestion: "나", queries: ["나"], evidence_count: 0, verdict: "pending", note: "", parse_failed: false, failed: true, capped: 0 },
```
교체 후:
```ts
        { subquestion: "가", queries: ["가", "가2"], evidence_count: 2, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0, excluded: 3 },
        // 무관 제외 전 보고서의 trail 에는 excluded 가 없다
        { subquestion: "나", queries: ["나"], evidence_count: 0, verdict: "pending", note: "", parse_failed: false, failed: true, capped: 0 },
```
그리고

교체 전:
```ts
    // 오류로 끝난 하위질문은 판정을 싣지 않는다
    expect(got.trail).toEqual([
      { subquestion: "가", queries: ["가", "가2"], verdict: "sufficient", evidenceCount: 2 },
      { subquestion: "나", queries: ["나"], verdict: null, evidenceCount: 0 },
    ]);
```
교체 후:
```ts
    // 오류로 끝난 하위질문은 판정을 싣지 않는다
    expect(got.trail).toEqual([
      { subquestion: "가", queries: ["가", "가2"], verdict: "sufficient", evidenceCount: 2, excluded: 3 },
      { subquestion: "나", queries: ["나"], verdict: null, evidenceCount: 0, excluded: 0 },
    ]);
```

(6) `docInputFromDraft`: 초안은 회차마다 뺀 수를 더한다. `round()` 헬퍼는 Task 10 Step 7 모양 그대로 두고, 펼치기로 excluded 만 바꾼다.

교체 전:
```ts
    subq(0, { rounds: [round(1, "가"), round(2, "가 재검색")] }),
```
교체 후:
```ts
    subq(0, { rounds: [{ ...round(1, "가"), excluded: 2 }, { ...round(2, "가 재검색"), excluded: 1 }] }),
```
그리고

교체 전:
```ts
    // 오류로 멈춘 하위질문은 판정을 싣지 않고, 모르는 채택 수는 0 이 아니라 비워 둔다
    expect(got.trail).toEqual([
      { subquestion: "하위질문 1", queries: ["가", "가 재검색"], verdict: "sufficient", evidenceCount: 1 },
      { subquestion: "하위질문 2", queries: [], verdict: null, evidenceCount: null },
      { subquestion: "하위질문 3", queries: [], verdict: "sufficient", evidenceCount: 1 },
    ]);
```
교체 후:
```ts
    // 오류로 멈춘 하위질문은 판정을 싣지 않고, 모르는 채택 수는 0 이 아니라 비워 둔다.
    // 무관하다고 뺀 수는 회차마다 뺀 수의 합이다(최종본 trail 의 총수와 같다)
    expect(got.trail).toEqual([
      { subquestion: "하위질문 1", queries: ["가", "가 재검색"], verdict: "sufficient", evidenceCount: 1, excluded: 3 },
      { subquestion: "하위질문 2", queries: [], verdict: null, evidenceCount: null, excluded: 0 },
      { subquestion: "하위질문 3", queries: [], verdict: "sufficient", evidenceCount: 1, excluded: 0 },
    ]);
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/reportDocument.test.ts
```
기대 출력: `Tests  3 failed | 19 passed (22)`. 실패하는 테스트는 다음 셋이다.
- 부록은 자기점검이 무관하다고 뺀 근거 수를 … 싣는다 — `expected [ 'heading1: 부록: 탐색 경로', …(2) ] to deeply equal [ … ]`
- docInputFromReport > … — `expected [ { subquestion: '가', …(3) }, …(1) ] to deeply equal [ { subquestion: '가', …(4) }, …(1) ]`
- docInputFromDraft > 부록은 화면의 탐색 타임라인에서, … — `expected [ …(3) ] to deeply equal [ …(3) ]`

- [ ] **Step 3: 구현 (`frontend/utils/reportDocument.ts`)**

(1) import

교체 전:
```ts
import { verdictLabel } from "./researchEvents";
```
교체 후:
```ts
import { excludedLabel, verdictLabel } from "./researchEvents";
```

(2) `DocTrailItem`

교체 전:
```ts
  verdict: Verdict | null;
  evidenceCount: number | null;
}
```
교체 후:
```ts
  verdict: Verdict | null;
  evidenceCount: number | null;
  // 자기점검이 무관하다고 뺀 근거 수. 무관 제외 전 잡은 0 — 0 이면 적지 않는다
  excluded: number;
}
```

(3) `trailBlocks`: 채택 수 뒤에 적는다. 채택 수는 제외한 뒤의 수라서 "채택 6편 / 무관 3편 제외" 순서로 읽힌다.

교체 전:
```ts
    if (t.evidenceCount !== null) items.push([{ text: `채택한 근거: ${t.evidenceCount}편` }]);
```
교체 후:
```ts
    if (t.evidenceCount !== null) items.push([{ text: `채택한 근거: ${t.evidenceCount}편` }]);
    const excluded = excludedLabel(t.excluded);
    if (excluded) items.push([{ text: excluded }]);
```

(4) `queryPath` 의 주석 — 재검색은 이제 무관 근거를 빼고 0편이 됐을 때도 일어난다.

교체 전:
```ts
// 재검색은 근거가 부족하다고 판정했을 때만 일어난다 — 검색어가 바뀐 흐름이 곧 자기점검의 기록이다
```
교체 후:
```ts
// 재검색은 근거가 부족할 때만 일어난다(부족 판정, 또는 무관 근거를 빼고 0편이 됐을 때) — 검색어가 바뀐 흐름이 곧 자기점검의 기록이다
```

(5) `docTrailItem` (최종본)

교체 전:
```ts
    verdict: t.failed ? null : t.verdict,
    evidenceCount: t.evidence_count,
  };
```
교체 후:
```ts
    verdict: t.failed ? null : t.verdict,
    evidenceCount: t.evidence_count,
    excluded: t.excluded ?? 0,
  };
```

(6) `docTrailFromSubq` (초안)

교체 전:
```ts
    verdict: sq.status === "failed" ? null : sq.verdict,
    evidenceCount: sq.adopted,
  };
```
교체 후:
```ts
    verdict: sq.status === "failed" ? null : sq.verdict,
    evidenceCount: sq.adopted,
    // 초안에는 trail 이 없어 회차마다 뺀 수를 더한다 — 최종본 trail 의 총수와 같은 값이다
    excluded: sq.rounds.reduce((n, r) => n + (r.excluded ?? 0), 0),
  };
```

Word(`reportDocx.ts`)와 PDF(`ReportPrint.vue`)는 같은 블록 모델을 그리기 때문에 고칠 것이 없다.

- [ ] **Step 4: 통과 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/reportDocument.test.ts
```
기대 출력: `Tests  22 passed (22)`

- [ ] **Step 5: 전체 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1
```
기대 출력:
- 첫 명령: `Test Files  21 passed (21)` · `Tests  387 passed (387)`
- 둘째 명령: 출력 없음
- 셋째 명령: `└  ✨ Build complete!`

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add frontend/utils/reportDocument.ts frontend/tests/unit/reportDocument.test.ts
git status --short
git commit -m "[Feat] round04c — 문서(Word·PDF) 부록의 탐색 경로에 하위질문별 \"무관 N편 제외\"를 싣는다: 최종본은 trail 의 excluded, 초안은 타임라인 회차의 excluded 합을 쓰고, 0·옛 보고서는 적지 않는다. 검색어 경로 주석의 재검색 조건에 무관 근거를 빼고 0편이 된 경우를 더한다"
```

---

## 단계 4 — 최종 확인

### Task 12: 최종 확인과 spec 상태 갱신

**Files:**
- Modify: `docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md` (3행 머리 상태 줄)

- [ ] **Step 1: 백엔드 전체 테스트**

`app/` 에서 전체를 돈다. 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 죽는 3개 파일만 뺀다(이 계획과 무관 — 기준선 780 도 같은 명령으로 잰 값이다).

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `837 passed`(경고 2건은 기존 것). 대상 파일만 다시 보면 `test_research_state.py` 60, `test_research_runner.py` 56, `test_research_synthesizer.py` 106, `test_research_critic.py` 43, `test_research_planner.py` 16, `test_research_tasks.py` 92 다.

- [ ] **Step 2: 프론트 전체 테스트·타입검사·빌드**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck 2>&1 | grep "error TS"
cd C:/Users/LANDSOFT/mygit/NL_library_AI/frontend && npm run build 2>&1 | tail -1
```
기대 출력:
- vitest: `Test Files  21 passed (21)`, `Tests  387 passed (387)`.
- typecheck: 출력 없음.
- build: `└  ✨ Build complete!`.

- [ ] **Step 3: 커밋 저자·트레일러 확인**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git log --format='%h %an <%ae> %s' 738bc07..HEAD
git log --format=%B 738bc07..HEAD | grep -ciE "co-authored-by|generated with claude"
```
기대:
- 첫 명령: 계획 문서 커밋 2개(`[Docs] round04c — 딥리서치 품질 구현 계획`, `[Docs] round04c — 구현 계획 검토 반영`)와 Task 1~11 커밋 11개가 모두 저장소 사용자(`git config user.name` — Hyonii) 이름으로 나온다. 그 사이에 다른 커밋(수정 커밋 등)이 끼었으면 그것도 같은 저자여야 한다.
- 둘째 명령: `0`.
- 하나라도 트레일러가 나오면 멈추고 사용자에게 알린다. 이미 쌓인 커밋의 메시지를 고치려면 사용자 승인 아래 비대화형 rebase 가 필요하다.

- [ ] **Step 4: spec 머리 상태 줄 갱신**

`docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md` 3행을 Edit 도구로 고친다(원래 줄바꿈 LF 유지).

교체 전:
```markdown
> 상태: 설계 확정(2026-09-29, 사용자 승인) · 구현 전
```
교체 후:
```markdown
> 상태: 설계 확정(2026-09-29, 사용자 승인) · 구현 완료(운영 배포 전)
```

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/LANDSOFT/mygit/NL_library_AI
git add docs/superpowers/specs/2026-09-29-round04c-research-quality-design.md
git commit -m "[Docs] round04c — spec 상태를 구현 완료(운영 배포 전)로 고친다: 하위질문별 근거 예산·보고서 evidence 정리·무관 근거 제외와 타임라인·부록 표시·계획 프롬프트·문체와 한계 문장 조사 구현, 백엔드 전체 pytest·프론트 vitest·타입검사·빌드 통과"
```

- [ ] **Step 6: 남은 일 알리기(이 계획에서 실행하지 않는다)**

사용자에게 다음을 알린다.
- 운영 배포(spec §9): 도는 딥리서치 잡 확인 → fastapi 이미지 빌드·푸시 → `nl-lib-fastapi`·`nl-lib-celery-research`·`nl-lib-celery-research-plan` Recreate(적재 워커는 건드리지 않는다, fastapi 재시작 전 `idle in transaction` 세션 확인 — recurring-gotchas 18번) → nuxt 이미지 → `nl-lib-nuxt` Recreate → `docker exec nl-lib-gateway nginx -s reload`. 공유 운영 서버라 **사용자 승인 뒤** 한다.
- 배포 뒤 운영 전후 비교(spec §7): 같은 질문 "컴퓨팅 자원에 대한 연구가 궁금해"를 기본 파라미터로 다시 돌려 ① 계획의 측면 분해 ② 하위질문별 근거 15편 안 고른 분포 ③ 엣지·HPC 회차 줄의 "무관 N편 제외"와 절의 무관 논문 제거 ④ '~다' 문체 통일 ⑤ 걸린 시간을 본다.
- 라운드 마무리(완료노트·교본·dev 머지)는 라운드 종료 절차(`GIT_WORKFLOW.md`, `.claude/skills/round-finish/SKILL.md`)를 따른다.

---

## 이 계획에서 다루지 않는 것

- spec 의 D(핵심 요약·주제 종합)·E(이어서 물어보기)·F(화면 참고문헌) — 다음 묶음.
- 리랭커 점수 하한(무관 제외가 운영에서 얼마나 걸러내는지 본 뒤 정한다), 하위질문 사이 근거 재배분, 인덱싱 범위(spec §8).
- 운영 배포와 운영 전후 비교(spec §7·§9) — 사용자 승인 뒤 따로 한다.
- 제외할 때 순위 보조값 `relevance`·`leaders` 삭제(spec §4) — 효과가 없어 하지 않는다(단계 2 머리 참고).
- 제외 뒤 0편으로 재검색할 때 강조 카드의 "근거 부족 → …" 고정 문구(단계 3 머리 참고).
- 무관 제외로 근거가 0편이 된 채 끝난 하위질문(재검색 한도·상한에 닿았거나 제안 검색어가 없을 때)의 한계 문장. 지금 규칙대로 "'…' 에 대해서는 근거를 찾지 못했다 — note" 로 나오고, note 는 제외 전 목록을 보고 쓴 것이라 "충분하다"일 수도 있다. spec 에 문구가 없어 두고, 운영 전후 비교에서 이런 하위질문이 나오는지 본다.
- 모델이 섞어 쓴 '~합니다' 문체를 코드로 고치기(spec §6 — 뜻이 바뀔 수 있다).
- DB 구조·워커·fastapi 코드 변경.
