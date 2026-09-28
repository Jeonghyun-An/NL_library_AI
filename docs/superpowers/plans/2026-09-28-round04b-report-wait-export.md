# 보고서 작성 대기 화면·내보내기 구현 계획 (round04b §14)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 딥리서치가 보고서를 쓰는 동안(종합 단계) 다 쓴 절부터 최종본과 같은 모양의 초안으로 보여 주고, 절 목록·경과·남은 시간을 움직이는 "보고서 작성 현황" 카드로 보인다. 완성본은 [다운로드 ▾], 작성 중·멈춘 초안은 [초안 저장 ▾]로 Word(.docx)·PDF(브라우저 인쇄)로 내려받는다. 사용자 방침(spec §7-4) — **인터랙티브함이 매우 중요하다**: 진행이 눈에 보이는 움직임, 눌러서 옮겨 가는 요소, 실시간 갱신을 먼저 두고, `prefers-reduced-motion` 을 존중하며, 읽는 사람을 자동 스크롤로 끌고 가지 않는다.

**Architecture:** 백엔드는 `assemble_report` 의 절 단위 처리를 `finalize_section` 으로 떼어 초안과 최종본이 같은 코드로 다듬은 절을 쓰게 하고, 종합 진행 콜백 `on_section` 에 info(소제목·다듬은 절·그 절이 인용한 근거)를 싣는다. 워커의 `_SynthProgress` 는 그것을 `synth` 이벤트로 절마다 한 번 나르고 종합 단계 `result`(기존 JSONB)에 쌓아, 새로고침·재접속한 화면이 이미 쓴 절을 되살린다. 알리는 `step` 이벤트는 미리보기를 뺀 가벼운 값이고, 완료로 닫으면 미리보기를 지우며, 실패·취소로 닫으면 남긴다. DB 구조는 바꾸지 않는다. 프론트는 순수 로직(`utils/researchEvents.ts` 합치기 · `utils/researchDraft.ts` 초안·남은 시간 · `utils/synthCard.ts` 카드 문구·막대 · `utils/reportDocument.ts` 문서 모델 · `utils/reportDocx.ts` Word 구성)을 Vitest 로 검증하고, 컴포넌트(`SynthProgressCard`·`ReportView` 초안 모드·`ReportSectionBody`·`ReportDownloadMenu`·`ReportPrint`)와 페이지 배선은 typecheck·build·수동 확인으로 본다. Word 는 `docx` 를 내려받기를 누를 때 동적 import 하고, PDF 는 같은 문서 모델을 인쇄 전용 화면으로 body 에 붙여 `window.print()` 한다.

**Tech Stack:** FastAPI · SQLAlchemy 2(async) · Celery · Redis pub/sub · pytest / Nuxt 4 · Vue 3.5 · TypeScript(strict·`noUncheckedIndexedAccess`) · Vitest 3.2 · `docx` 9(테스트는 그 의존성 `jszip` 으로 압축을 풀어 본다)

**설계 근거:** `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md`(이하 spec)의 **§14 전체**와 **§7-4**. §5·§6 은 기존 이벤트·화면 맥락이다. 선행 계획: `docs/superpowers/plans/2026-09-26-round04b-deep-research-frontend.md`.

**실행 전 확인:** `docs/ops/recurring-gotchas.md` 13번 — pipeline·reranker·embedder 처럼 torch 를 끌어오는 모듈은 함수 안에서 import 한다(로컬 `app/.venv` 에 torch 가 없다). 운영 배포(spec §14-7)는 이 계획 밖이다 — 공유 운영 서버라 **사용자 승인 뒤** 따로 한다.

**계획 작성 시 검증:** 태스크 코드는 저장소 밖 사본에서 실제로 돌려 보고 옮겼다.
- 백엔드(Task 1~3): 코드 블록을 사본(`a6fd98c` 의 `app/`)에 그대로 적용해 돌렸다. 각 태스크의 "실패 확인"·"통과 확인" 출력은 사본 실측이다.
- 프론트 데이터(Task 4·5): 사본에서 구현 전 실패(Task 4 는 9 failed / 56 passed, Task 5 는 모듈 없음)와 구현 후 통과(65·18 passed), strict·`noUncheckedIndexedAccess` 의 `tsc` 통과를 확인했다.
- 초안 화면(Task 6·7): 계약대로 만든 임시 `researchDraft`·타입 위에서 `nuxi typecheck` 오류 0, `nuxt build` 성공, 가짜 뷰 하네스 페이지로 브라우저 동작을 봤다.
- 내보내기(Task 8~10): `reportDocument.test.ts` 20 passed, `reportDocx.test.ts` 3 passed, 엄격 옵션 `tsc` 오류 0. 앞 태스크를 계약 모양 대역으로 채운 사본 위에서 Task 10 의 `nuxi typecheck` 오류 0, `npm run build` 통과, docx 별도 청크 1개를 확인했다.
- **조립 때 태스크 사이를 잇느라 고친 곳**(아래 "조립 때 맞춘 것")은 사본에서 다시 돌리지 않았다. Task 11 의 전체 테스트·`nuxi typecheck`·`npm run build` 가 방어선이다.

---

## 테스트 명령

**백엔드** — `app/` 에서:

```bash
cd app && python -m pytest tests/<파일> -q
cd app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```

- 로컬 `app/.venv` 에는 pytest 가 없어서 PATH 의 `python`(pytest 9.1)으로 돌린다.
- 전체 실행에서 제외한 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 실패한다(이 계획과 무관).
- 경고 2건(Pydantic class-based config)은 기존 것이다.

**프론트** — `frontend/` 에서:

```bash
cd frontend && npx vitest run tests/unit/<이름>.test.ts   # 한 파일
cd frontend && npx vitest run                              # 전체(= npm test)
cd frontend && npx nuxi typecheck 2>&1 | grep "error TS"   # 출력이 없어야 한다
cd frontend && npm run build 2>&1 | tail -1                # └  ✨ Build complete!
```

- Vitest 는 `environment: "node"` 로 `tests/unit/**/*.test.ts` 만 돈다. 컴포넌트 마운트 도구는 없다 — 컴포넌트·페이지는 typecheck·build·grep·수동 화면 확인으로 본다.
- `[Vue] Resolve plugin path failed …` 줄은 typecheck 의 기존 소음이다. `grep "error TS"` 에 걸리지 않는다.

**누적 기대치** — 기준선은 HEAD `a6fd98c` 에서 잰 값이다(백엔드 745 passed, 프론트 16파일 / 277 tests). 이 문서의 태스크 순서대로 적용했을 때의 값이다.

| 태스크 뒤 | `test_research_synthesizer.py` | `test_research_tasks.py` | 백엔드 전체 | 프론트 파일 / tests |
|---|---|---|---|---|
| 기준선 | 78 | 70 | 745 | 16 / 277 |
| Task 1 | 88 | 70 | 755 | — |
| Task 2 | 91 | 70 | 758 | — |
| Task 3 | 91 | 82 | **770** | — |
| Task 4 | — | — | — | 16 / 286 |
| Task 5 | — | — | — | 17 / 304 |
| Task 6 | — | — | — | 18 / 322 |
| Task 7 | — | — | — | 18 / 325 |
| Task 8 | — | — | — | 19 / 345 |
| Task 9 | — | — | — | **20 / 348** |
| Task 10 | — | — | — | 20 / 348 |

## 커밋 규칙

- 메시지는 `[Feat] round04b — …` 처럼 대괄호 접두사(`[Feat]`·`[Fix]`·`[Test]`·`[Docs]`)와 한국어로 쓴다. 태스크 하나 = 커밋 하나(Task 11 은 문서 커밋 하나).
- **`Co-Authored-By`·"Generated with Claude Code" 같은 트레일러를 절대 붙이지 않는다**(사용자 단독 저자). 각 Step 의 `git commit -m "…"` 을 그대로 쓴다.
- 파일 첫 줄은 경로 주석이다. 코드 주석은 "왜"를 한국어로, 과하지 않게 쓰고 태스크 번호를 적지 않는다(`docs/standards/coding-standard.md`). 기존 이름을 재사용한다.
- 작업 트리의 기존 파일은 CRLF 다(`core.autocrlf=true`). 기존 파일은 **Edit 도구로 고쳐** 줄바꿈을 유지한다. 새 파일은 LF 로 써도 커밋 때 정규화된다.
- 기존 파일을 고치는 Step 의 줄 번호는 착수 시점(브랜치 `feat/round04b-deep-research-frontend`, `a6fd98c`) 기준 참고값이다. 앞 태스크가 같은 파일을 고쳤으면 줄이 밀리므로 "교체 전" 코드 문자열로 찾는다.

---

## 파일 구조

| 파일 | 책임 | Task |
|---|---|---|
| `app/services/research/synthesizer.py` | `SectionTally`·`finalize_section`·`section_evidence` 분리(`assemble_report` 출력 불변) · `on_section(idx, total, status, info)` | 1·2 |
| `app/workers/research_tasks.py` | `_SynthProgress` 확장(synth 이벤트에 소제목·시작 시각·소요 시간·절·근거, 단계 result 에 미리보기·근거 합집합) · `_finish`·`_save_progress` 의 `event_result` · 종합 단계 닫기 규칙 | 3 |
| `app/models/research.py` | `ResearchStep.result` 의 synthesize 모양 주석만 | 3 |
| `app/tests/test_research_synthesizer.py` · `app/tests/test_research_tasks.py` | 백엔드 테스트(기존 파일에 추가) | 1~3 |
| `frontend/types/research.ts` | `SynthSectionResult`·`StepResult`·`SynthEvent`·`SynthSectionView`·`SynthView` 확장 | 4 |
| `frontend/utils/researchEvents.ts` | synth 이벤트·단계 result 합치기(`applySynth`·`mergeSection`·`toSectionView`), `mergeEvidence` | 4 |
| `frontend/utils/researchDraft.ts` (신규) | `draftSlots`·`draftReport`·`synthEta`·`formatClock`·`formatRemaining` | 5 |
| `frontend/utils/synthCard.ts` (신규) | 카드 요약·항목 상태 문구·막대 비율·방금 끝난 절·스크린리더 알림 문구 | 6 |
| `frontend/composables/useNow.ts` (신규) | 켜져 있을 때만 1초마다 도는 화면 시계 | 6 |
| `frontend/components/research/SynthProgressCard.vue` (신규) | 보고서 작성 현황 카드(막대·절 목록·jump/hover·`actions` 슬롯·`aria-live`) | 6 |
| `frontend/utils/researchReport.ts` | `draftIntro` 추가 | 7 |
| `frontend/components/research/ReportSectionBody.vue` (신규) | 절 본문(도입·대표 논문·향후 과제) — 최종본과 초안이 같이 쓴다 | 7 |
| `frontend/components/research/ReportView.vue` | 초안 모드(`draft`·`highlightIdx`), 절 id `rs-sec-N`, 머리 `actions` 슬롯 | 7 |
| `frontend/pages/research/[id].vue` | 현황 카드·초안·강조·이동 배선(7), 내려받기 배선·인쇄 문서(10) | 7·10 |
| `frontend/assets/css/research.css` | 현황 카드(6) · 초안(7) · 내려받기 메뉴·인쇄(10) 절을 파일 끝에 차례로 덧붙인다 | 6·7·10 |
| `frontend/utils/reportDocument.ts` (신규) | 문서 모델(블록·인용 번호·참고문헌·부록·파일 이름), 입력 만들기 | 8 |
| `frontend/package.json` · `package-lock.json` · `frontend/utils/reportDocx.ts` (신규) | `docx` 의존성 · Word 구성(모듈 주입)·Blob·내려받기 | 9 |
| `frontend/components/research/ReportDownloadMenu.vue` · `ReportPrint.vue` · `frontend/composables/useReportExport.ts` (신규) | 내려받기 메뉴 · 인쇄 전용 화면 · Word·PDF 내보내기 상태 | 10 |
| `frontend/tests/unit/researchEvents.test.ts` · `researchDraft.test.ts` · `synthCard.test.ts` · `researchReport.test.ts` · `reportDocument.test.ts` · `reportDocx.test.ts` | 프론트 단위 테스트 | 4~9 |
| `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` | 머리 상태 줄의 §14 → 구현 완료(운영 배포 전) | 11 |

진행 패널(`ProgressPanel.vue`)·`useResearch.ts`·fastapi(`app/api/research.py`)는 건드리지 않는다 — fastapi 는 단계 result 를 그대로 전달한다.

---

## 실행 순서

| 단계 | 태스크 | 선행·병렬 |
|---|---|---|
| 1 | Task 1 → 2 → 3 (백엔드) | 번호 순. 프론트와 파일이 겹치지 않아 단계 2·3 과 **병렬 가능** |
| 2 | Task 4 → 5 (프론트 데이터) | Task 5 는 Task 4 의 `SynthView.headings·evidence` 를 쓴다 |
| 3 | Task 6 → 7 (초안 화면) · Task 8 → 9 (문서 모델·Word) | Task 6·8 은 Task 5 뒤. 6·7 과 8·9 는 파일이 겹치지 않아 병렬 가능 |
| 4 | Task 10 (내려받기 배선) | Task 7(`SynthProgressCard`·`ReportView` 슬롯, 페이지의 `draft`)과 Task 9 뒤. `research.css`·`[id].vue` 를 Task 7 다음에 고친다 |
| 5 | Task 11 (최종 확인) | 전부 뒤 |

화면이 온전히 움직이는 것(절 미리보기)은 워커(Task 1~3)가 운영에 배포된 뒤다. 새 필드가 없으면 화면은 옛 동작("보고서 작성 중 2/5" 에 해당하는 막대·절 목록)으로 되돌아간다.

---

## 공유 계약 (정본)

태스크 사이에서 주고받는 이름·모양이다. 태스크 코드는 이 목록과 일치하도록 맞췄다.

### 백엔드

- `synthesizer.py`
  - `@dataclass class SectionTally: unmarked:int=0; dropped:int=0; unparsed:int=0; unsummarized:int=0; failed:int=0; introless:int=0`, `def add(self, other) -> None`(제자리에서 더한다 — Task 1 추가).
  - `def finalize_section(state: ResearchState, sec: dict) -> tuple[dict, SectionTally]` — `assemble_report` 절 루프 본문을 옮긴 것. 반환 절 모양 = `report.sections[i]`(heading·intro·papers·future·evidence_chunks·chunk_scores). `assemble_report` 는 이 함수를 부르고 집계를 더한다 — 출력 불변.
  - `def section_evidence(state: ResearchState, section: dict) -> dict[str, dict]` — 다듬은 절이 인용한 근거만(papers[].evidence ∪ future[].evidence ∪ 도입의 마커 — `bind_markers(...).used`). 값 `{cnts_id, meta, chunks:[asdict(Chunk)]}`, chunks 는 `section["evidence_chunks"].get(eid)` 가 있으면 그 chunk_id 만, 없으면 전부, score 내림차순.
  - `SectionFn = Callable[..., Awaitable[None]]`, 호출 규약 `on_section(idx, total, status, info)`. info = `{"subq_idx": sq.idx, "heading": sq.text, "headings": [대상 절 heading 전부, 절 순서]}`, status 가 `"done"`/`"failed"` 면 `{"section": finalize 한 절, "evidence": section_evidence(...)}` 를 더한다. `_no_progress(idx, total, status, info=None)`.
- `research_tasks.py`
  - `_SynthProgress.__call__(self, idx, total, status, info: dict | None = None)` — info 없이도 동작(옛 3인자 호출). 비공개 추가(Task 3): 필드 `headings`·`details`·`evidence`, 생성 인자 `clock`(기본 `time.monotonic`), 메서드 `_record`·`_merge_evidence`.
  - synth 이벤트 payload: `{section_idx, total, status, subq_idx, heading, headings}` + running 이면 `started_at`(`_now().isoformat()`, ISO UTC), done/failed 면 `duration_ms`(워커가 그 절의 running 을 본 경우만, `time.monotonic` 으로 잰 int)·`section`·`evidence`. info 가 없으면 옛 `{section_idx, total, status}` 만.
  - `def result(self, *, previews: bool = True, **extra) -> dict` = `{**extra, "sections_total", "headings", "sections":[{idx, status, subq_idx, heading, started_at, duration_ms, section?}], "evidence"?}`. 모르는 칸은 `null`. previews=False 면 `sections[].section`·`evidence` 를 뺀다.
  - `_save_progress(db, step, result, event_result: dict | None = None)` / `_finish(db, step, status, result=None, event_result: dict | None = None)` — DB 에는 result, 알리는 step 이벤트에는 event_result(없으면 result).
  - 종합 단계: 진행 저장 = `result()` 저장 + `result(previews=False)` 알림. 완료로 닫을 때 `_finish(done, result(previews=False))`. 실패·취소로 닫을 때 `_finish(failed, result(error=…), event_result=result(error=…, previews=False))`. 시간 상한으로 닫히는 경로(`_close_orphan_steps`)는 기존대로 `jsonb ||` 로 합쳐 미리보기가 남는다.
  - 프론트가 기대할 사실: `failed` 절에도 `section` 이 있다(논문 목록만 있는 절). `evidence[E].chunks[].score` 는 `report.evidence` 와 같은 의미(`Chunk.score`)이고, 절별 점수는 `section.chunk_scores` 로 본다. 완료로 닫힌 종합 단계 result 에는 `section`·`evidence` 가 없다.

### 프론트 타입 (`types/research.ts`)

- `SynthSectionResult` = `{idx; status: SynthSectionStatus; subq_idx?: number; heading?: string; started_at?: string | null; duration_ms?: number | null; section?: ReportSection}`
- `StepResult` 에 `headings?: string[]`, `evidence?: Record<string, ReportEvidence>` 추가(기존 `sections_total`·`sections` 유지).
- `SynthEvent` = `{kind:"synth"; section_idx; total; status; subq_idx?; heading?; headings?: string[]; started_at?: string; duration_ms?: number; section?: ReportSection; evidence?: Record<string, ReportEvidence>}`
- `SynthSectionView` = `{idx; status; subqIdx: number | null; heading: string | null; startedAt: string | null; durationMs: number | null; section: ReportSection | null}`
- `SynthView` = `{seq; status; total; sections: SynthSectionView[]; headings: string[]; evidence: Record<string, ReportEvidence>}`
- 합치기 규칙(`utils/researchEvents.ts`): 절 상태는 기존 `SECTION_RANK`(더 나아간 쪽), 나머지 칸은 들어온 값이 null/undefined 가 아니면 그것, 아니면 기존 값(가벼운 step 이벤트가 section 을 지우지 않게). evidence 는 eid 별로 합치고 chunks 는 chunk_id 합집합(점수순). 새 시도(seq 변경)면 비운다. 내보내는 헬퍼 `mergeEvidence(a, b)`. `applySynth`·`mergeSection`·`toSectionView` 는 모듈 안에서만 쓴다.

### 프론트 순수 로직

- `utils/researchDraft.ts`
  - `type DraftSlotStatus = "done" | "failed" | "running" | "waiting"`
  - `interface DraftSlot { idx; heading: string; status: DraftSlotStatus; durationMs: number | null; startedAt: string | null; sectionIndex: number | null }` — sectionIndex 는 `DraftReport.report.sections` 안의 위치(내용을 받은 끝난 절만). heading 은 `synth.headings[idx]` → 이벤트의 `heading` → `section.heading` → `"절 N"`(빈 제목은 건너뛴다).
  - `interface DraftReport { report: ResearchReport; slots: DraftSlot[]; done: number; total: number }` — done 은 초안에 실린 절 수, total 은 `slots.length`.
  - `draftSlots(view)` — 절 수는 `max(total, headings.length, 받은 절 번호+1)`. 없는 절은 waiting. 종합 단계가 닫혔거나 잡이 끝났으면 running 절을 waiting 으로 본다.
  - `draftReport(view)` — 끝난(done·failed 이고 section 이 있는) 절이 없으면 null. report = `{question, range: null, sections: 끝난 절(슬롯 순), evidence: view.synth.evidence, trail: [], limitations: [], stats?: 라이브 카운터가 셋 다 있으면 {papers_reviewed, evidence_adopted, rechecks}}`.
  - `interface SynthEta { done; total; runningIdx: number | null; runningElapsedMs: number | null; remainingMs: number | null }`, `synthEta(view, nowMs)` — done 은 끝난 절(done+failed) 수. 남은 시간 = 끝난 절 걸린 시간 평균 × 대기 절 수 + max(0, 평균 − 쓰는 중 경과). 걸린 시간이 있는 끝난 절이 없으면 null. 경과는 음수가 되지 않게 자른다.
  - `formatClock(ms)`("0:38", "1:05", "12:03"; 음수·NaN 은 "0:00"), `formatRemaining(ms, done)`(done=0 → "첫 절을 쓰는 중", done>0 이고 null → "남은 시간 계산 중", 10초 미만 → "곧 끝납니다", 1분 미만 → "약 40초 남음", 1분 이상 → 10초 단위 반올림 "약 1분 30초 남음"/"약 2분 남음").
- `utils/synthCard.ts`(Task 6 추가): `synthSummary(eta)`, `slotStateLabel(slot, eta)`, `barFraction(eta)`(0~1), `newlyFinished(prev, slots)`, `finishedAnnouncement(slots, idxs)`.
- `utils/researchReport.ts`(Task 7 추가): `draftIntro(slots, interrupted, stats?)`.

### 프론트 컴포넌트·컴포저블

- `composables/useNow.ts`: `useNow(active: Ref<boolean> | ComputedRef<boolean>, intervalMs = 1000): Ref<number>` — active 일 때만 setInterval, 언마운트 시 정리.
- `components/research/SynthProgressCard.vue`: props `{slots: DraftSlot[]; eta: SynthEta; highlightIdx?: number | null}`, emits `{jump: [idx: number]; hover: [idx: number | null]}`, `<slot name="actions" />`(초안 저장 메뉴 자리). 절 완성 알림(`aria-live="polite"`)과 CSS `.rs-sr-only` 는 이 카드가 맡는다.
- `components/research/ReportSectionBody.vue`(Task 7 추가): props `{sec: ReportSection; evidence: Record<string, ReportEvidence>}`, emits `{"open-pdf": [payload: OpenPdfPayload]}`.
- `components/research/ReportView.vue`: 선택 props `draft?: { slots: DraftSlot[]; interrupted: boolean } | null`, `highlightIdx?: number | null`. 절 요소 id `rs-sec-<절 순번>`(최종본은 si, 초안은 slot.idx). 머리 [링크 복사] 옆 `<slot name="actions" />`. draft 면 한계 섹션 없음, "작성 중"(interrupted 면 "완성되지 않은 초안") 배지, 쓰는 중 절은 움직이는 회색 줄, 대기 절은 "작성 대기"(interrupted 면 "작성을 마치지 못한 절입니다").
- `components/research/ReportDownloadMenu.vue`: props `{label: string; disabled?: boolean; busy?: boolean}`, emits `{select: [format: ReportExportFormat]}`(= `"docx" | "pdf"`). 키보드는 `utils/menuNav.ts` 의 `menuStep`.
- `components/research/ReportPrint.vue`: props `{doc: ReportDoc}` — 인쇄 전용 렌더(body 로 Teleport).
- `composables/useReportExport.ts`: `useReportExport(): { exporting: Ref<boolean>; printDoc: ShallowRef<ReportDoc | null>; exportDocx(doc): Promise<void>; printPdf(doc): Promise<void> }` — printPdf 는 printDoc 설정 → nextTick → `document.title` 을 파일 이름(확장자 뺀)으로 → `window.print()` → `afterprint` 에서 제목 복구·printDoc 비움.
- 페이지(`pages/research/[id].vue`, Task 7): `slots`·`eta`·`draft`(= 초안이 보이는 단계에서만 `draftReport(view)`, 최종본이 오면 null)·`draftMode`·`hoverIdx`·`linkedIdx`·`jumpToSection`. Task 10 은 이 `draft` 를 [초안 저장]의 원천으로 쓴다.

### 문서 모델 (`utils/reportDocument.ts`, 순수)

- `interface DocTrailItem { subquestion: string; queries: string[]; verdict: Verdict | null; evidenceCount: number | null }`
- `interface ReportDocInput { question; range: Partial<ReportRange> | null; generatedAt: string | null; url: string; intro: string; sections: ReportSection[]; evidence: Record<string, ReportEvidence>; limitations: string[] | null; trail: DocTrailItem[]; draft: { done: number; total: number } | null }`
- `type DocRun = { text: string } | { cite: number }`, `type DocBlock = title | meta | heading(level 1|2) | para(runs, muted?) | bullets(items: DocRun[][])`, `interface DocReference { n; eid; text }`, `interface ReportDoc { fileName; blocks; references }` — 참고문헌은 blocks 뒤 references 로 따로(Word·인쇄가 각자 "참고문헌" 제목과 함께 그린다). 부록은 blocks 안에 heading + bullets.
- `buildReportDocument(input, now)`, `reportFileName(question, date, draft)`, `docInputFromReport(report, { generatedAt, url })`, `docInputFromDraft(draft, view, url)`. Task 8 추가: `docRunText(run)`(인용은 `[n]`), `type ReportExportFormat = "docx" | "pdf"`.
- `utils/reportDocx.ts`: `toDocxBlob(doc)`(docx 동적 import), `toDocxBuffer(doc)`(테스트용 `Uint8Array`), `downloadBlob(blob, fileName)`. Task 9 추가: `type DocxModule = typeof import("docx")`, `buildDocxDocument(docx, doc)`(모듈을 인자로 받는 순수 구성 함수).

### 조립 때 맞춘 것

영역별 초안을 한 문서로 합치며 고친 곳이다.
1. **선행 태스크 번호**: 초안 화면 초안이 `researchDraft.ts` 를 "Task 4", 타입 확장을 "Task 3" 으로 적었다. 이 문서 번호로 Task 5·Task 4 로 고쳤다(Task 6·7). 내보내기 초안의 "앞 태스크" 선행 설명도 Task 4·5·6·7·9 로, 초안 화면 초안의 "뒤 태스크(내보내기 배선)"도 Task 10 으로 적었다.
2. **[초안 저장]의 원천**: 내보내기 초안은 페이지에 `savableDraft = computed(() => draftReport(view))` 를 새로 두었다. Task 7 이 이미 같은 값을 `draft` 로 둔다(현황 카드가 보이는 종합 중, 멈춘 초안이 보이는 실패·취소에서 두 값이 같다). Task 10 은 `draft` 를 쓰고 `savableDraft` 와 `draftReport` import 단계를 뺐다.
3. **멈춘 초안의 메뉴 자리**: 내보내기 초안은 "`:draft="{ …, interrupted: true }"` 를 가진 별도 요소"를 가정했다. Task 7 은 작성 중·멈춘 초안을 `:draft="draftMode"` 인 요소 **하나**로 그린다. Task 10 은 그 요소에 `actions` 슬롯을 달고 `v-if="draftMode?.interrupted"` 로 멈춘 초안에서만 [초안 저장]을 보인다(spec §14-3 "작성 중 초안에는 [다운로드]가 없다"). 현황 카드·초안 요소의 교체 전·후를 Task 7 코드 그대로 적었다.
4. **초안의 서론**: 화면 초안(Task 7)은 `draftIntro`("4개 절 중 2개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다…")를, 초안 문서(Task 8)는 spec §14-4 3번대로 `reportIntro` 를 탐색한 하위질문 수(`view.subqs`)로 쓴다. spec 의 "화면과 같은 문장"은 완성본에 해당한다 — 완성본은 화면·문서 모두 `reportIntro` 다. "다 쓴 절부터 먼저 보여 드립니다"는 저장한 파일에서는 맞지 않는 말이고, 초안 문서는 제목("(초안 · N개 절 중 M개 작성)")과 한계 자리 안내로 초안임을 밝힌다. 그래서 둘을 한 문장으로 합치지 않았다.
5. **CSS 덧붙이는 자리**: Task 6·7·10 이 모두 `research.css` 끝에 덧붙인다. Task 10 의 자리를 "Task 7 이 덧붙인 줄임 동작 블록 뒤"로 못박았다.
6. **작업 메모 제외**: 초안에 섞인 스크래치 디렉터리 경로·검증 사본 사고 메모는 계획 본문이 아니라서 뺐다.

---

## 단계 1 — 백엔드: 절 미리보기 (Task 1~3)

### 공통 메모 (Task 1~3)

- **테스트 실행**: `cd app && python -m pytest tests/<파일> -q`. 로컬 `app/.venv` 에는 pytest 가 없어서 PATH 의 `python`(pytest 9.1)으로 돌린다. 계획을 쓰면서 확인했다.
- **전체 스위트**: `cd app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py`
- **기준선**(HEAD `a6fd98c`): `test_research_synthesizer.py` **78 passed**, `test_research_tasks.py` **70 passed**, 전체 **745 passed**.
- **누적 기대치**:

| 태스크 뒤 | synthesizer | tasks | 전체 |
|---|---|---|---|
| Task 1 | 88 | 70 | 755 |
| Task 2 | 91 | 70 | 758 |
| Task 3 | 91 | 82 | 770 |

- **검증 방식**: 이 계획의 코드 블록은 저장소 밖 사본(`a6fd98c` 의 `app/`)에 그대로 적용해 돌려 봤다. "실패 확인"·"통과 확인"에 적은 출력은 모두 그 사본에서 잰 값이다.
  - 사본에서는 `test_rewrite_milvus_doc_type.py` 16건이 실패했다. 사본에 저장소 루트의 `scripts/` 가 없어서이고 이 계획과는 무관하다. 저장소에서는 통과한다.
- **CRLF**: 기존 파일은 CRLF 다. **Edit 도구로 고쳐** 줄바꿈을 유지한다.
- **다른 태스크(프론트)에 넘기는 사실** — 공유 계약을 보충한다:
  - `synth` 이벤트의 키 유무:
    - `headings`·`subq_idx`·`heading` 은 info 가 있는 모든 이벤트에 실린다.
    - `started_at` 은 `running` 에만 실린다.
    - `duration_ms` 는 `done`/`failed` 중에서 워커가 그 절의 `running` 을 본 경우에만 실린다.
    - `section`·`evidence` 는 `done`/`failed` 에만 실린다. **`failed` 절에도 `section` 이 있다**(논문 목록만 있는 절).
  - 단계 `result.sections[]` 는 칸을 늘 싣는다. 모르는 값은 `null` 이다(`subq_idx`·`heading`·`started_at`·`duration_ms`). `section` 은 미리보기가 있을 때만, `evidence` 는 모은 근거가 있을 때만 있다.
  - `evidence[E].chunks[].score` 는 `report.evidence` 와 같은 의미다(`Chunk.score`, 매칭한 하위질문 중 최고값). 절별 점수는 `section.chunk_scores` 로 본다.
  - 완료로 닫힌 종합 단계 result 에는 `section`·`evidence` 가 없다. 실패·취소·시간 상한으로 닫힌 단계에는 남는다.

---

### Task 1: 절 단위 처리 분리 — `SectionTally`·`finalize_section`·`section_evidence`

`assemble_report` 의 절 루프 본문을 `finalize_section(state, sec) -> (절, SectionTally)` 로 떼어 낸다. `assemble_report` 는 이 함수를 부르고 집계를 더하기만 한다. **출력은 한 글자도 바뀌지 않는다.** 여기에 그 절이 인용한 근거만 모으는 `section_evidence` 를 더한다.

계약 추가: `SectionTally.add(other)` 는 제자리에서 더하고 `None` 을 돌려준다.

**Files:**
- Modify: `app/services/research/synthesizer.py`
  - import L20
  - `assemble_report` L170-241 — 함수 머리부터 절 루프 끝까지 교체
  - `build_limitations` 호출 L255-259
- Test: `app/tests/test_research_synthesizer.py`
  - import L9-12
  - 파일 끝(`TestReportStats.test_existing_keys_are_kept` 뒤)에 추가

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/test_research_synthesizer.py` 의 import 를 고친다.

교체 전:
```python
from services.research.synthesizer import (
    PAPERS_PER_SECTION, SynthesisCanceled, assemble_report, build_limitations, build_section,
    synthesize,
)
```
교체 후:
```python
from services.research.synthesizer import (
    PAPERS_PER_SECTION, SectionTally, SynthesisCanceled, assemble_report, build_limitations,
    build_section, finalize_section, section_evidence, synthesize,
)
```

파일 끝(`TestReportStats.test_existing_keys_are_kept` 뒤)에 추가한다.

```python


class TestFinalizeSection:
    """assemble_report 의 절 단위 처리를 떼어 낸 함수. 작성 중 초안(절 미리보기)과 최종본이
    이 함수 하나로 다듬은 절을 쓴다 — 둘이 갈리면 초안에서 읽은 글이 완성본에서 바뀐다."""

    def _sections(self):
        return [
            {"heading": "하위1", "intro": "도입 [E1] [E99]. 연결 문장.",
             "papers": [{"cnts_id": "A", "summary": "요약 [E1]."}, {"cnts_id": "B", "summary": ""}],
             "future": [{"text": "과제 [E2]."}, {"text": "[E7]"}],
             "evidence_chunks": {"E1": ["c1"], "E2": ["c2"]},
             "chunk_scores": {"c1": 0.9, "c2": 0.8}},
            {"heading": "하위2", "intro": "", "failed": True, "future": [],
             "papers": [{"cnts_id": "B", "summary": ""}, {"cnts_id": "C", "summary": ""}]},
        ]

    def test_section_equals_the_assembled_report_section(self):
        st = _state_three()
        sections = self._sections()
        report = assemble_report(st, sections, unmarked_total=0)
        assert [finalize_section(st, s)[0] for s in sections] == report["sections"]

    def test_tally_counts_one_section(self):
        # 도입의 [E99]·과제의 [E7] 은 이 절 근거(E1·E2)에 없다 → 삭제 2, "연결 문장." → 무표기 1,
        # 요약이 빈 B → 요약 누락 1
        _, tally = finalize_section(_state_three(), self._sections()[0])
        assert tally == SectionTally(unmarked=1, dropped=2, unsummarized=1)

    def test_failed_section_counts_only_as_failed(self):
        _, tally = finalize_section(_state_three(), self._sections()[1])
        assert tally == SectionTally(failed=1)

    def test_tallies_add_up_to_the_report_limitations(self):
        st = _state_three()
        total = SectionTally()
        for s in self._sections():
            total.add(finalize_section(st, s)[1])
        assert total == SectionTally(unmarked=1, dropped=2, unsummarized=1, failed=1)
        assert assemble_report(st, self._sections(), unmarked_total=0)["limitations"] == (
            build_limitations(st, unmarked_total=1, dropped_total=2, failed_sections=1,
                              unsummarized_total=1))


class TestSectionEvidence:
    """절 미리보기에 싣는 근거 — 그 절이 인용한 근거만, 대목은 그 절이 매칭한 것만."""

    def _state(self):
        st = _state_three()
        st.evidence["E2"].chunks = [Chunk("c2a", "하위1 대목", 1, 1, 0.4),
                                    Chunk("c2b", "하위2 대목", 2, 2, 0.8)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1"], "E2": ["c2a"]}
        st.subquestions[1].evidence_chunks = {"E2": ["c2b"], "E3": ["c3"]}
        return st

    def _finalized(self, st, i):
        return finalize_section(st, build_section(st, st.subquestions[i], {"intro": "도입 [E2]."}))[0]

    def test_only_cited_evidence_is_carried(self):
        st = self._state()
        # 하위1 절의 논문은 E1·E2 다 — E3 은 하위2 절의 근거라 싣지 않는다
        assert set(section_evidence(st, self._finalized(st, 0))) == {"E1", "E2"}

    def test_shape_matches_report_evidence(self):
        st = self._state()
        ev = section_evidence(st, self._finalized(st, 1))["E3"]
        assert ev == {"cnts_id": "C", "meta": {"title": "논문 C"}, "chunks": [
            {"chunk_id": "c3", "text": "본문", "page_start": 1, "page_end": 1, "score": 0.9}]}

    def test_chunks_are_limited_to_the_section(self):
        # 한 논문이 두 절에 실리면 Evidence.chunks 는 합집합이다 — 절 미리보기는 제 대목만 싣는다
        st = self._state()
        first = section_evidence(st, self._finalized(st, 0))["E2"]["chunks"]
        second = section_evidence(st, self._finalized(st, 1))["E2"]["chunks"]
        assert [c["chunk_id"] for c in first] == ["c2a"]
        assert [c["chunk_id"] for c in second] == ["c2b"]

    def test_chunks_are_best_first(self):
        st = self._state()
        st.evidence["E1"].chunks = [Chunk("c1a", "약한 대목", 1, 1, 0.3),
                                    Chunk("c1b", "강한 대목", 2, 2, 0.9)]
        st.subquestions[0].evidence_chunks = {"E1": ["c1a", "c1b"], "E2": ["c2a"]}
        chunks = section_evidence(st, self._finalized(st, 0))["E1"]["chunks"]
        assert [c["chunk_id"] for c in chunks] == ["c1b", "c1a"]

    def test_section_without_chunk_mapping_keeps_every_chunk(self):
        """매핑 없는 절(옛 모양)은 _serialize_evidence 처럼 전부 준다 — 거르면 대목이 0개가 된다."""
        st = self._state()
        sec, _ = finalize_section(st, {"heading": "h", "intro": "도입 [E1].", "future": [],
                                       "papers": [{"cnts_id": "A", "summary": "s"},
                                                  {"cnts_id": "B", "summary": "s"}]})
        assert [c["chunk_id"] for c in section_evidence(st, sec)["E2"]["chunks"]] == ["c2b", "c2a"]

    def test_markers_in_intro_and_future_are_cited_too(self):
        # 칩은 대표 논문만이 아니다 — 도입·향후 과제의 [E#] 도 팝오버를 연다
        st = self._state()
        sec = {"heading": "h", "intro": "도입 [E3].", "papers": [],
               "future": [{"text": "과제 [E2].", "evidence": ["E2"]}], "evidence_chunks": {}}
        assert set(section_evidence(st, sec)) == {"E2", "E3"}
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `cd app && python -m pytest tests/test_research_synthesizer.py -q`

Expected: 수집 단계에서 실패한다.
- `E   ImportError: cannot import name 'SectionTally' from 'services.research.synthesizer'`
- `1 error in …s`

- [ ] **Step 3: 최소 구현**

`app/services/research/synthesizer.py` import 를 고친다.

교체 전:
```python
from dataclasses import asdict
```
교체 후:
```python
from dataclasses import asdict, dataclass, fields
```

`assemble_report` 의 머리부터 절 루프 끝까지를 바꾼다. `section_evidence`·`SectionTally`·`finalize_section` 을 `_serialize_evidence` 와 `assemble_report` 사이에 두는 셈이다.

교체 전:
```python
def assemble_report(
    state: ResearchState, sections: list[dict], *, unmarked_total: int,
) -> dict:
    by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
    unmarked = unmarked_total
    # 마커 검증 결과는 bind_markers 호출마다 누적한다. 섹션마다 도입·향후
    # 과제로 여러 번 부르므로 한 번의 반환값만 읽으면 나머지 호출에서 지운
    # 표기가 조용히 사라진다. dropped 는 번호 종류가 아니라 본문에 박힌
    # 표기 수로 센다 — 사용자가 보는 단위가 그것이다.
    dropped = unparsed = 0
    unsummarized = failed_sections = introless = 0
    out_sections = []

    for sec in sections:
        failed = bool(sec.get("failed"))
        # 모델은 절마다 그 절의 논문만 받는다 — 검증도 그 번호로 한정한다. 근거
        # 번호가 E1..En 으로 연속 발급되므로 전역 집합으로 검증하면 모델이 지어낸
        # 작은 번호는 거의 다 통과하고, 본 적 없는 논문을 가리키는 칩이 생긴다.
        valid = {by_cnts[p["cnts_id"]] for p in sec.get("papers", []) if p["cnts_id"] in by_cnts}
        intro = bind_markers(sec.get("intro", ""), valid)
        unmarked += intro.unmarked
        dropped += len(intro.dropped)
        unparsed += len(intro.unparsed)
        # 칩만 남은 도입("[E1]")은 문장이 아니다 — 도입 없음으로 센다
        intro_text = intro.text if _prose(intro.text) else ""
        if failed:
            failed_sections += 1
        elif not intro_text:
            introless += 1

        papers = []
        for p in sec.get("papers", []):
            eid = by_cnts.get(p["cnts_id"])
            if eid is None:
                continue                      # 근거에 없는 논문은 싣지 않는다
            summary = strip_markers(p.get("summary", ""))
            if not _prose(summary):
                summary = ""                  # "[E1]." 에서 번호만 걷으면 마침표 하나가 남는다
            # 서술이 통째로 실패한 절은 위의 failed_sections 로 이미 보고한다 —
            # 그 절의 논문을 요약 누락으로 또 세면 실패가 두 건처럼 보인다.
            if not summary and not failed:
                unsummarized += 1
            papers.append({
                "cnts_id": p["cnts_id"],
                "summary": summary,
                "evidence": [eid],            # 구조적 인용 — 모델이 고르지 않는다
            })

        future = []
        for f in sec.get("future", []):
            res = bind_markers(f.get("text", ""), valid)
            unmarked += res.unmarked
            dropped += len(res.dropped)
            unparsed += len(res.unparsed)
            # 지운 번호는 위에서 이미 셌다. 마커만 있던 항목은 빈 불릿이나 칩 하나짜리
            # 불릿이 되므로 싣지 않는다.
            if not _prose(res.text):
                continue
            # used 를 bind_markers 가 돌려준다 — 여기서 정규식을 다시 쓰면
            # 마커 문법이 두 곳으로 갈라진다.
            future.append({"text": res.text, "evidence": res.used})

        out_sections.append({
            "heading": sec.get("heading", ""),
            "intro": intro_text, "papers": papers, "future": future,
            # 근거 ID → 이 절에서 매칭된 청크 ID. 한 논문이 여러 절에 실리면
            # evidence.chunks 는 그 합집합이라, 호버는 이걸로 그 절의 대목을 고른다.
            "evidence_chunks": sec.get("evidence_chunks", {}),
            # 청크 ID → 이 절의 하위질문 검색어로 받은 점수. 두 절이 한 청크를 쓰면
            # evidence.chunks[].score(최고값) 하나로는 한쪽 절에 남의 점수가 뜬다.
            "chunk_scores": sec.get("chunk_scores", {}),
        })

    return {
```
교체 후:
```python
def section_evidence(state: ResearchState, section: dict) -> dict[str, dict]:
    """다듬은 절(finalize_section) 하나가 인용한 근거만 report.evidence 와 같은 모양으로 만든다.

    작성 중 초안의 인용칩 팝오버가 쓴다. 근거 전체를 절마다 실으면 절이 쌓일수록 같은 대목을
    거듭 나른다. 대목은 이 절이 매칭한 것(evidence_chunks)만 점수순으로 싣고, 매핑이 없으면
    _serialize_evidence 와 같이 전부 싣는다.
    """
    # 다듬은 도입에는 표준형 [E#] 만 남는다 — bind_markers 의 used 로 읽는다. 여기서 정규식을
    # 다시 쓰면 마커 문법이 두 곳으로 갈라진다.
    cited = list(bind_markers(section.get("intro", ""), set(state.evidence)).used)
    for item in (*section.get("papers", []), *section.get("future", [])):
        cited.extend(item.get("evidence", []))
    mapped = section.get("evidence_chunks", {})
    out: dict[str, dict] = {}
    for eid in cited:
        ev = state.evidence.get(eid)
        if ev is None or eid in out:
            continue
        ids = set(mapped.get(eid) or [])
        keep = [c for c in ev.chunks if c.chunk_id in ids] if ids else ev.chunks
        out[eid] = {
            "cnts_id": ev.cnts_id,
            "meta": ev.meta,
            "chunks": [asdict(c) for c in sorted(keep, key=lambda c: c.score, reverse=True)],
        }
    return out


@dataclass
class SectionTally:
    """절 하나를 다듬으며 센 검증 결과. 보고서의 한계 문장은 이것을 절마다 더한 값이다."""
    unmarked: int = 0
    dropped: int = 0
    unparsed: int = 0
    unsummarized: int = 0
    failed: int = 0
    introless: int = 0

    def add(self, other: "SectionTally") -> None:
        # 칸을 손으로 나열하지 않는다 — 칸을 더하고 여기서 빠뜨리면 한계 문장이 조용히 준다
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))


def finalize_section(state: ResearchState, sec: dict) -> tuple[dict, SectionTally]:
    """모델 출력으로 만든 절(build_section)을 보고서에 싣는 모양으로 다듬는다 (순수 함수).

    작성 중 초안(절마다 워커가 미리 보여 준다)과 최종 보고서가 이 함수 하나를 쓴다 — 따로
    다듬으면 초안에서 읽은 글과 완성본의 글이 갈린다.

    마커 검증 결과는 bind_markers 호출마다 누적한다. 절마다 도입·향후 과제로 여러 번
    부르므로 한 번의 반환값만 읽으면 나머지 호출에서 지운 표기가 조용히 사라진다. dropped 는
    번호 종류가 아니라 본문에 박힌 표기 수로 센다 — 사용자가 보는 단위가 그것이다.
    """
    by_cnts = {ev.cnts_id: eid for eid, ev in state.evidence.items()}
    tally = SectionTally()
    failed = bool(sec.get("failed"))
    # 모델은 절마다 그 절의 논문만 받는다 — 검증도 그 번호로 한정한다. 근거
    # 번호가 E1..En 으로 연속 발급되므로 전역 집합으로 검증하면 모델이 지어낸
    # 작은 번호는 거의 다 통과하고, 본 적 없는 논문을 가리키는 칩이 생긴다.
    valid = {by_cnts[p["cnts_id"]] for p in sec.get("papers", []) if p["cnts_id"] in by_cnts}
    intro = bind_markers(sec.get("intro", ""), valid)
    tally.unmarked += intro.unmarked
    tally.dropped += len(intro.dropped)
    tally.unparsed += len(intro.unparsed)
    # 칩만 남은 도입("[E1]")은 문장이 아니다 — 도입 없음으로 센다
    intro_text = intro.text if _prose(intro.text) else ""
    if failed:
        tally.failed += 1
    elif not intro_text:
        tally.introless += 1

    papers = []
    for p in sec.get("papers", []):
        eid = by_cnts.get(p["cnts_id"])
        if eid is None:
            continue                      # 근거에 없는 논문은 싣지 않는다
        summary = strip_markers(p.get("summary", ""))
        if not _prose(summary):
            summary = ""                  # "[E1]." 에서 번호만 걷으면 마침표 하나가 남는다
        # 서술이 통째로 실패한 절은 위의 failed 로 이미 센다 —
        # 그 절의 논문을 요약 누락으로 또 세면 실패가 두 건처럼 보인다.
        if not summary and not failed:
            tally.unsummarized += 1
        papers.append({
            "cnts_id": p["cnts_id"],
            "summary": summary,
            "evidence": [eid],            # 구조적 인용 — 모델이 고르지 않는다
        })

    future = []
    for f in sec.get("future", []):
        res = bind_markers(f.get("text", ""), valid)
        tally.unmarked += res.unmarked
        tally.dropped += len(res.dropped)
        tally.unparsed += len(res.unparsed)
        # 지운 번호는 위에서 이미 셌다. 마커만 있던 항목은 빈 불릿이나 칩 하나짜리
        # 불릿이 되므로 싣지 않는다.
        if not _prose(res.text):
            continue
        # used 를 bind_markers 가 돌려준다 — 여기서 정규식을 다시 쓰면
        # 마커 문법이 두 곳으로 갈라진다.
        future.append({"text": res.text, "evidence": res.used})

    return {
        "heading": sec.get("heading", ""),
        "intro": intro_text, "papers": papers, "future": future,
        # 근거 ID → 이 절에서 매칭된 청크 ID. 한 논문이 여러 절에 실리면
        # evidence.chunks 는 그 합집합이라, 호버는 이걸로 그 절의 대목을 고른다.
        "evidence_chunks": sec.get("evidence_chunks", {}),
        # 청크 ID → 이 절의 하위질문 검색어로 받은 점수. 두 절이 한 청크를 쓰면
        # evidence.chunks[].score(최고값) 하나로는 한쪽 절에 남의 점수가 뜬다.
        "chunk_scores": sec.get("chunk_scores", {}),
    }, tally


def assemble_report(
    state: ResearchState, sections: list[dict], *, unmarked_total: int,
) -> dict:
    tally = SectionTally(unmarked=unmarked_total)
    out_sections = []
    for sec in sections:
        section, counted = finalize_section(state, sec)
        out_sections.append(section)
        tally.add(counted)

    return {
```

같은 함수의 반환문에서 `build_limitations` 호출을 고친다.

교체 전:
```python
        "limitations": build_limitations(
            state, unmarked_total=unmarked, dropped_total=dropped,
            failed_sections=failed_sections, unsummarized_total=unsummarized,
            unparsed_total=unparsed, introless_sections=introless,
        ),
```
교체 후:
```python
        "limitations": build_limitations(
            state, unmarked_total=tally.unmarked, dropped_total=tally.dropped,
            failed_sections=tally.failed, unsummarized_total=tally.unsummarized,
            unparsed_total=tally.unparsed, introless_sections=tally.introless,
        ),
```

- [ ] **Step 4: 통과 확인**

Run: `cd app && python -m pytest tests/test_research_synthesizer.py -q`
Expected: `88 passed` (기존 78건 그대로 통과 + 새 10건)

Run: `cd app && python -m pytest tests/test_research_tasks.py -q`
Expected: `70 passed`

- [ ] **Step 5: 커밋**

```bash
git add app/services/research/synthesizer.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04b — 보고서의 절 단위 처리(마커 검증·요약 정리)를 finalize_section 으로 떼고 절이 인용한 근거·대목만 모으는 section_evidence 를 더한다: 작성 중 초안과 최종본이 같은 코드로 다듬은 절을 쓰게 하고 assemble_report 출력은 그대로 둔다"
```

---

### Task 2: 종합 진행 콜백에 `info` — 소제목, 끝날 때 다듬은 절·근거

`on_section(idx, total, status, info)` 로 넓힌다.
- `info` 는 `{"subq_idx", "heading", "headings"}` 다.
- `done`/`failed` 때는 여기에 `{"section": finalize_section 한 절, "evidence": section_evidence(...)}` 를 더한다.
- 서술을 받지 못한 절(`failed`)도 논문 목록만 있는 절로 싣는다.

워커 하네스는 `synthesize` 를 대역으로 바꾸므로 `test_research_tasks.py` 는 이 태스크에서 바뀌지 않는다.

**Files:**
- Modify: `app/services/research/synthesizer.py`
  - `SectionFn` L47
  - `_no_progress` L54-55
  - `synthesize` 독스트링 끝·루프 L417-430 — Task 1 뒤라 줄이 밀렸으니 교체 전 문자열로 찾는다
- Test: `app/tests/test_research_synthesizer.py`
  - `TestSectionProgress._record` L683-689
  - `test_canceled_section_is_never_reported_finished` 뒤(L716)에 추가

- [ ] **Step 1: 실패하는 테스트 작성**

`TestSectionProgress._record` 가 info 를 **필수 인자**로 받게 한다. 그래야 `synthesize` 가 4인자로 부르지 않으면 기존 테스트도 실패한다.

교체 전:
```python
    def _record(self):
        seen: list[tuple[int, int, str]] = []

        async def on_section(idx, total, status):
            seen.append((idx, total, status))

        return seen, on_section
```
교체 후:
```python
    def _record(self, infos: list | None = None):
        seen: list[tuple[int, int, str]] = []

        async def on_section(idx, total, status, info):
            seen.append((idx, total, status))
            if infos is not None:
                infos.append(info)

        return seen, on_section
```

`test_canceled_section_is_never_reported_finished` 뒤에 추가한다.

교체 전:
```python
        with pytest.raises(SynthesisCanceled):
            asyncio.run(synthesize(_state_three(), should_stop=stop, on_section=on_section))
        assert seen == [(0, 2, "running")]
```
교체 후:
```python
        with pytest.raises(SynthesisCanceled):
            asyncio.run(synthesize(_state_three(), should_stop=stop, on_section=on_section))
        assert seen == [(0, 2, "running")]

    def test_start_carries_the_subquestion_and_every_heading(self, monkeypatch):
        # 절 순번과 하위질문 번호는 다르다 — 근거 없는 하위질문은 절이 되지 않는다
        st = _state_three()
        st.subquestions[0].evidence_ids = []
        reply = json.dumps({"intro": "도입 [E2].", "summaries": {}, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [reply])
        infos = []
        seen, on_section = self._record(infos)
        asyncio.run(synthesize(st, on_section=on_section))
        assert seen[0] == (0, 1, "running")
        assert infos[0] == {"subq_idx": 1, "heading": "하위2", "headings": ["하위2"]}

    def test_end_carries_the_finalized_section_and_its_evidence(self, monkeypatch):
        reply = json.dumps({"intro": "도입 [E1] [E2].", "summaries": {"E1": "요약 [E1]."},
                            "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [reply, reply])
        infos = []
        _, on_section = self._record(infos)
        report = asyncio.run(synthesize(_state_three(), on_section=on_section))
        assert "section" not in infos[0] and "evidence" not in infos[0]
        assert infos[1]["subq_idx"] == 0 and infos[1]["headings"] == ["하위1", "하위2"]
        # 초안의 절은 최종본의 절과 같다 — 같은 finalize_section 으로 다듬는다
        assert [infos[1]["section"], infos[3]["section"]] == report["sections"]
        assert set(infos[1]["evidence"]) == {"E1", "E2"}
        assert set(infos[3]["evidence"]) == {"E2", "E3"}
        assert infos[1]["evidence"]["E1"] == report["evidence"]["E1"]

    def test_failed_section_is_carried_with_its_paper_list(self, monkeypatch):
        # 서술을 끝내 받지 못한 절도 초안에 싣는다 — 최종본도 그 절을 논문 목록만으로 싣는다
        good = json.dumps({"intro": "도입 [E1].", "summaries": {}, "future": []})
        TestSynthesize()._patch_chat(monkeypatch, [good, _timeout(), _timeout()])
        infos = []
        seen, on_section = self._record(infos)
        report = asyncio.run(synthesize(_state_three(), on_section=on_section))
        assert seen[-1] == (1, 2, "failed")
        sec = infos[-1]["section"]
        assert sec == report["sections"][1]
        assert sec["intro"] == "" and sec["future"] == []
        assert [(p["cnts_id"], p["summary"]) for p in sec["papers"]] == [("B", ""), ("C", "")]
        assert set(infos[-1]["evidence"]) == {"E2", "E3"}
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `cd app && python -m pytest tests/test_research_synthesizer.py -q`

Expected: `6 failed, 85 passed`
- 실패한 6건은 `TestSectionProgress` 의 기존 3건과 새 3건이다.
- 메시지: `TypeError: TestSectionProgress._record.<locals>.on_section() missing 1 required positional argument: 'info'`

- [ ] **Step 3: 최소 구현**

`app/services/research/synthesizer.py` 를 고친다.

교체 전:
```python
SectionFn = Callable[[int, int, str], Awaitable[None]]
```
교체 후:
```python
# on_section(idx, total, status, info) — info 의 모양은 synthesize 독스트링에 있다. 인자 수를
# 타입에 못박지 않는 이유: 워커의 콜백은 info 를 선택 인자로 받는다(info 없는 호출과 호환).
SectionFn = Callable[..., Awaitable[None]]
```

교체 전:
```python
async def _no_progress(idx: int, total: int, status: str) -> None:
    return None
```
교체 후:
```python
async def _no_progress(idx: int, total: int, status: str, info: dict | None = None) -> None:
    return None
```

`synthesize` 의 독스트링 끝과 루프를 고친다.

교체 전:
```python
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
교체 후:
```python
    on_section(idx, total, status, info) 는 절을 쓰기 시작할 때 "running", 끝낼 때 "done"
    또는 "failed" 로 부른다. idx 는 절 순번(0부터)이지 하위질문 번호가 아니다 — 근거
    없는 하위질문은 절이 되지 않아 둘이 어긋나고, 화면의 "2/3" 은 절 순번으로 센다.
    info 는 {subq_idx, heading, headings(쓸 절 전부의 소제목, 절 순서)} 이고, 끝낼 때는
    finalize_section 으로 다듬은 절(section)과 그 절이 인용한 근거(evidence)를 더한다 —
    화면이 다 쓴 절부터 초안으로 보여 준다. 서술을 받지 못한 절(failed)도 최종본처럼
    논문 목록만 있는 절로 싣는다.
    """
    on_section = on_section or _no_progress
    targets = [sq for sq in state.subquestions if sq.evidence_ids]
    # 첫 절을 쓰는 동안에도 화면이 남은 절을 "작성 대기"로 그릴 수 있게 소제목을 전부 싣는다
    headings = [sq.text for sq in targets]
    sections = []
    for i, sq in enumerate(targets):
        info = {"subq_idx": sq.idx, "heading": sq.text, "headings": headings}
        await on_section(i, len(targets), "running", info)
        section = await _synthesize_section(state, sq, should_stop=should_stop)
        sections.append(section)
        log.info("[research] 절 종합 job=%s idx=%s 논문=%d ok=%s",
                 state.job_id, sq.idx, len(section["papers"]), not section["failed"])
        preview, _ = finalize_section(state, section)
        await on_section(i, len(targets), "failed" if section["failed"] else "done",
                         {**info, "section": preview,
                          "evidence": section_evidence(state, preview)})
```

- [ ] **Step 4: 통과 확인**

Run: `cd app && python -m pytest tests/test_research_synthesizer.py -q`
Expected: `91 passed`

Run: `cd app && python -m pytest tests/test_research_tasks.py -q`
Expected: `70 passed` — 하네스가 `synthesize` 를 대역으로 바꿔 영향이 없다.

- [ ] **Step 5: 커밋**

```bash
git add app/services/research/synthesizer.py app/tests/test_research_synthesizer.py
git commit -m "[Feat] round04b — 종합의 절 진행 콜백에 info(하위질문 번호·소제목·전체 소제목, 절을 끝낼 때 finalize_section 으로 다듬은 절과 그 절이 인용한 근거)를 실어 화면이 다 쓴 절부터 초안으로 보여 줄 수 있게 한다 — 서술을 받지 못한 절도 논문 목록만 있는 절로 싣는다"
```

---

### Task 3: 워커 — 절 미리보기 이벤트·저장, 가벼운 step 이벤트, 닫을 때 규칙

`_SynthProgress` 가 info 를 선택 인자로 받아 다음을 한다.
- `synth` 이벤트에 소제목·시작 시각·워커가 잰 소요 시간·절·근거를 싣는다.
- 단계 result 에 절 미리보기와 근거 합집합을 쌓는다.

알림과 저장은 이렇게 나눈다.
- 도는 동안의 `step` 이벤트와 완료로 닫는 기록에는 미리보기를 빼고 싣는다.
- 실패·취소로 닫을 때는 DB 에 남기고 이벤트에서만 뺀다.
- 시간 상한으로 닫히는 경로(`_close_orphan_steps`)는 기존대로 `jsonb ||` 로 합치므로 미리보기가 남는다.

계약 추가(비공개): `_SynthProgress` 에 다음을 더한다.
- 필드 `headings`·`details`·`evidence`
- 생성 인자 `clock`(기본 `time.monotonic`, 테스트가 바꿔 끼운다)
- 내부 메서드 `_record`·`_merge_evidence`

테스트 전용 이름: `_Harness.announced`, 도우미 `_bare`·`_synth_info`.

**Files:**
- Modify: `app/workers/research_tasks.py`
  - import L11-14
  - `_finish` L164-172
  - `_save_progress` L175-195
  - `_SynthProgress` L215-237
  - 종합 블록 L549-562
- Modify: `app/models/research.py` — `synthesize` result 모양 주석 L109-111
- Test: `app/tests/test_research_tasks.py`
  - import L13-18
  - `_Harness` L234-236
  - `_patch_pipeline` 의 `_finish` L258-260·`_save_progress` L279-280
  - `TestStepEvents` L932-934 뒤
  - `_ROUNDS` L1029-1034 뒤
  - `TestStepResults` 단언 4곳 L1093-1148
  - `TestSaveProgress` L1204-1206 뒤
  - `TestLiveProgress` L1266-1269 + 새 클래스
  - `TestOrphanStepsKeepProgress` L1409-1424

- [ ] **Step 1: 하네스가 `event_result` 를 받게**

`app/tests/test_research_tasks.py` import 를 고친다.

교체 전:
```python
import asyncio
import importlib
import sys
import types
import uuid
from unittest.mock import MagicMock
```
교체 후:
```python
import asyncio
import datetime as _dt
import importlib
import json
import sys
import types
import uuid
from unittest.mock import MagicMock
```

`_Harness.__init__` 을 고친다.

교체 전:
```python
        self.on_section = None
        self.emit = None
        self.progress: list[tuple] = []
```
교체 후:
```python
        self.on_section = None
        self.emit = None
        self.progress: list[tuple] = []
        # (단계, status, 알린 result) — _finish·_save_progress 가 step 이벤트로 흘리는 값
        self.announced: list[tuple] = []
```

`_patch_pipeline` 의 대역 두 개를 고친다. 기존 `h.finished`·`h.progress` 튜플 모양은 그대로 둔다. 기존 테스트가 4튜플로 풀어 쓰기 때문이다.

교체 전:
```python
    async def _finish(db, step_id, status, result=None):
        # 롤백 없이 쓰면 깨진 트랜잭션 위에서 다시 터진다 — 몇 번 롤백한 뒤였는지 남긴다
        h.finished.append((step_id, status, result, session.rollbacks))
```
교체 후:
```python
    async def _finish(db, step_id, status, result=None, event_result=None):
        # 롤백 없이 쓰면 깨진 트랜잭션 위에서 다시 터진다 — 몇 번 롤백한 뒤였는지 남긴다
        h.finished.append((step_id, status, result, session.rollbacks))
        h.announced.append((step_id, status, result if event_result is None else event_result))
```

교체 전:
```python
    async def _save_progress(db, step, result):
        h.progress.append((step, result))
```
교체 후:
```python
    async def _save_progress(db, step, result, event_result=None):
        h.progress.append((step, result))
        h.announced.append((step, "running", result if event_result is None else event_result))
```

- [ ] **Step 2: 도우미와, 옛 모양 단언을 새 모양으로**

`_ROUNDS` 뒤에 도우미를 추가한다.

교체 전:
```python
    {"round": 2, "query": "보완 검색어", "found_chunks": 2, "new_papers": 1,
     "verdict": "sufficient", "note": "충분", "next_query": None},
]
```
교체 후:
```python
    {"round": 2, "query": "보완 검색어", "found_chunks": 2, "new_papers": 1,
     "verdict": "sufficient", "note": "충분", "next_query": None},
]


def _bare(idx: int, status: str) -> dict:
    """info 없이 부른 절의 기록 — 절 머리·시각을 모른다."""
    return {"idx": idx, "status": status, "subq_idx": None, "heading": None,
            "started_at": None, "duration_ms": None}


def _synth_info(idx: int, *, done: bool = False) -> dict:
    """synthesize 가 on_section 에 넘기는 info 대역. 끝난 절이면 다듬은 절과 그 근거를 더한다."""
    info = {"subq_idx": idx, "heading": f"하위{idx + 1}", "headings": ["하위1", "하위2"]}
    if done:
        eid, chunk = f"E{idx}", f"c{idx}"
        info["section"] = {
            "heading": f"하위{idx + 1}", "intro": f"도입 [{eid}].", "future": [],
            "papers": [{"cnts_id": f"C{idx}", "summary": "요약", "evidence": [eid]}],
            "evidence_chunks": {eid: [chunk]}, "chunk_scores": {chunk: 0.9},
        }
        info["evidence"] = {eid: {
            "cnts_id": f"C{idx}", "meta": {"title": f"논문 {idx}"},
            "chunks": [{"chunk_id": chunk, "text": "대목", "page_start": 1, "page_end": 1,
                        "score": 0.9}],
        }}
    return info
```

`TestStepResults.test_synthesis_progress_is_streamed_and_saved` 를 고친다. 이 테스트는 3인자 호출 그대로 두어 **info 없는 호출과의 호환**을 계속 지킨다.

교체 전:
```python
        _, status, result, _ = h.finished[-1]
        assert status == "done"
        assert result == {"sections_total": 2, "sections": [
            {"idx": 0, "status": "done"}, {"idx": 1, "status": "failed"}]}
```
교체 후:
```python
        _, status, result, _ = h.finished[-1]
        assert status == "done"
        # info 없이 불러도(옛 호출) 이벤트는 옛 모양 그대로고, 기록은 모르는 칸을 비워 둔다
        assert result == {"sections_total": 2, "headings": [],
                          "sections": [_bare(0, "done"), _bare(1, "failed")]}
```

`test_failed_synthesis_keeps_the_sections_done_so_far` 를 고친다.

교체 전:
```python
        assert result == {"error": "종합 호출 실패", "sections_total": 2, "sections": [
            {"idx": 0, "status": "done"}, {"idx": 1, "status": "running"}]}
```
교체 후:
```python
        assert result == {"error": "종합 호출 실패", "sections_total": 2, "headings": [],
                          "sections": [_bare(0, "done"), _bare(1, "running")]}
```

`test_canceled_synthesis_keeps_the_sections_done_so_far` 를 고친다.

교체 전:
```python
        assert result == {"error": "취소됨", "sections_total": 3,
                          "sections": [{"idx": 0, "status": "done"}]}
```
교체 후:
```python
        assert result == {"error": "취소됨", "sections_total": 3, "headings": [],
                          "sections": [_bare(0, "done")]}
```

`test_report_without_sections_saves_zero_total` 를 고친다.

교체 전:
```python
        assert h.finished[-1][2] == {"sections_total": 0, "sections": []}
```
교체 후:
```python
        assert h.finished[-1][2] == {"sections_total": 0, "headings": [], "sections": []}
```

- [ ] **Step 3: `_finish`·`_save_progress` 의 `event_result` 테스트**

`TestStepEvents.test_closing_without_result_streams_an_empty_result` 뒤에 추가한다.

교체 전:
```python
        asyncio.run(rt._finish(db, step, "failed"))

        assert events[-1][2]["status"] == "failed" and events[-1][2]["result"] == {}
```
교체 후:
```python
        asyncio.run(rt._finish(db, step, "failed"))

        assert events[-1][2]["status"] == "failed" and events[-1][2]["result"] == {}

    def test_closing_can_announce_a_lighter_result(self, monkeypatch):
        # 종합 단계는 절 미리보기를 저장만 하고 알리지 않는다 — synth 이벤트가 이미 날랐다
        rt = _load_tasks(monkeypatch)
        events = self._capture(monkeypatch, rt)
        db = _RecordingSession(scalar=7)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 0, "synthesize", "보고서 종합"))
        saved = {"error": "취소됨", "sections": [{"idx": 0, "section": {"heading": "h"}}],
                 "evidence": {"E1": {}}}
        light = {"error": "취소됨", "sections": [{"idx": 0}]}

        asyncio.run(rt._finish(db, step, "failed", saved, event_result=light))

        assert _update_values(db.stmts[-1])["result"] == saved
        assert events[-1][2]["result"] == light
```

`TestSaveProgress.test_time_limit_is_not_swallowed` 뒤에 추가한다.

교체 전:
```python
        db.execute = _limit
        with pytest.raises(rt.SoftTimeLimitExceeded):
            asyncio.run(rt._save_progress(db, step, {"rounds": []}))
```
교체 후:
```python
        db.execute = _limit
        with pytest.raises(rt.SoftTimeLimitExceeded):
            asyncio.run(rt._save_progress(db, step, {"rounds": []}))

    def test_event_result_is_announced_instead_of_the_saved_result(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        db = _RecordingSession(scalar=41)
        step = asyncio.run(rt._step(db, uuid.uuid4(), 5, "synthesize", "보고서 종합"))
        saved = {"sections_total": 2, "sections": [{"idx": 0, "section": {"heading": "h"}}],
                 "evidence": {"E1": {}}}
        light = {"sections_total": 2, "sections": [{"idx": 0}]}

        asyncio.run(rt._save_progress(db, step, saved, event_result=light))

        assert _update_values(db.stmts[-1]) == {"result": saved}
        assert events[-1][2]["status"] == "running" and events[-1][2]["result"] == light
```

- [ ] **Step 4: 절 미리보기 테스트 — `TestLiveProgress` 단언 수정과 새 클래스, 시간 상한 경로**

`TestLiveProgress.test_section_progress_is_saved_on_the_synthesis_step` 의 단언을 새 모양으로 바꾸고, 그 뒤에 `TestSynthPreview` 를 추가한다.

교체 전:
```python
        assert [res for _, res in h.progress] == [
            {"sections_total": 2, "sections": [{"idx": 0, "status": "running"}]},
            {"sections_total": 2, "sections": [{"idx": 0, "status": "done"}]},
        ]
```
교체 후:
```python
        assert [res for _, res in h.progress] == [
            {"sections_total": 2, "headings": [], "sections": [_bare(0, "running")]},
            {"sections_total": 2, "headings": [], "sections": [_bare(0, "done")]},
        ]


class TestSynthPreview:
    """다 쓴 절을 작성 중 초안으로 보여 준다. synth 이벤트가 절 내용을 절마다 한 번 나르고, 단계
    result 가 그것을 들고 있어 새로고침·재접속한 화면이 되살린다. step 이벤트는 가볍게 둔다."""

    _T0 = _dt.datetime(2026, 9, 28, 1, 2, 3, tzinfo=_dt.timezone.utc)

    def _progress(self, monkeypatch, rt, ticks=(10.0, 12.5)):
        monkeypatch.setattr(rt, "_now", lambda: self._T0)
        clock = iter(ticks)
        return rt._SynthProgress(uuid.uuid4(), clock=lambda: next(clock))

    def test_running_event_carries_heading_and_start_time(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        progress = self._progress(monkeypatch, rt)

        asyncio.run(progress(0, 2, "running", _synth_info(0)))

        assert events[-1][1:] == ("synth", {
            "section_idx": 0, "total": 2, "status": "running", "subq_idx": 0,
            "heading": "하위1", "headings": ["하위1", "하위2"],
            "started_at": "2026-09-28T01:02:03+00:00",
        })

    def test_done_event_carries_duration_section_and_evidence(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        progress = self._progress(monkeypatch, rt)
        done = _synth_info(0, done=True)

        asyncio.run(progress(0, 2, "running", _synth_info(0)))
        asyncio.run(progress(0, 2, "done", done))

        # 소요 시간은 워커가 잰 값이다 — 화면 시계와 무관하다
        assert events[-1][1:] == ("synth", {
            "section_idx": 0, "total": 2, "status": "done", "subq_idx": 0,
            "heading": "하위1", "headings": ["하위1", "하위2"], "duration_ms": 2500,
            "section": done["section"], "evidence": done["evidence"],
        })

    def test_call_without_info_keeps_the_old_event(self, monkeypatch):
        # info 를 모르는 호출과 호환 — 이벤트는 옛 모양 그대로다
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        progress = rt._SynthProgress(uuid.uuid4())

        asyncio.run(progress(0, 1, "running"))

        assert events[-1][2] == {"section_idx": 0, "total": 1, "status": "running"}
        assert progress.result() == {"sections_total": 1, "headings": [],
                                     "sections": [_bare(0, "running")]}

    def test_result_keeps_previews_and_merges_evidence(self, monkeypatch):
        # 한 논문이 두 절에 실리면 절마다 제 대목만 온다 — 합쳐야 앞 절 칩의 대목이 남는다
        rt = _load_tasks(monkeypatch)
        TestStepEvents()._capture(monkeypatch, rt)
        progress = self._progress(monkeypatch, rt, ticks=(0.0, 1.0, 2.0, 4.0))
        first, second = _synth_info(0, done=True), _synth_info(1, done=True)
        second["evidence"]["E0"] = {**first["evidence"]["E0"], "chunks": [
            {"chunk_id": "c0b", "text": "하위2 대목", "page_start": 4, "page_end": 4,
             "score": 0.95}]}

        for idx, info in ((0, first), (1, second)):
            asyncio.run(progress(idx, 2, "running", _synth_info(idx)))
            asyncio.run(progress(idx, 2, "done", info))

        full = progress.result()
        assert [s["section"] for s in full["sections"]] == [first["section"], second["section"]]
        assert [s["duration_ms"] for s in full["sections"]] == [1000, 2000]
        assert set(full["evidence"]) == {"E0", "E1"}
        assert [c["chunk_id"] for c in full["evidence"]["E0"]["chunks"]] == ["c0b", "c0"]

        light = progress.result(previews=False)
        assert "evidence" not in light
        assert all("section" not in s for s in light["sections"])
        assert light["headings"] == ["하위1", "하위2"]
        assert light["sections"][0]["started_at"] == "2026-09-28T01:02:03+00:00"

    def test_result_handed_out_earlier_does_not_change(self, monkeypatch):
        # 저장·알림에 넘긴 값을 뒤따르는 절이 고치면 앞서 저장한 기록이 바뀐다
        rt = _load_tasks(monkeypatch)
        TestStepEvents()._capture(monkeypatch, rt)
        progress = rt._SynthProgress(uuid.uuid4())
        first, second = _synth_info(0, done=True), _synth_info(1, done=True)
        second["evidence"] = {"E0": {**first["evidence"]["E0"], "chunks": [
            {"chunk_id": "c0b", "text": "하위2 대목", "page_start": 4, "page_end": 4,
             "score": 0.95}]}}

        asyncio.run(progress(0, 2, "done", first))
        before = progress.result()
        asyncio.run(progress(1, 2, "done", second))

        assert [c["chunk_id"] for c in before["evidence"]["E0"]["chunks"]] == ["c0"]

    def _run(self, monkeypatch, rt, *, stop_with: Exception | None = None):
        """절 0 을 끝내고 절 1 을 쓰기 시작한다. stop_with 가 없으면 절 1 도 끝내고 완료한다."""
        job = _FakeJob(stage="explored", plan=["하위1"], state_snapshot=_explored_snapshot(),
                       status="queued")
        ref = {}

        async def _synth(state, should_stop):
            h = ref["h"]
            await h.on_section(0, 2, "running", _synth_info(0))
            await h.on_section(0, 2, "done", _synth_info(0, done=True))
            await h.on_section(1, 2, "running", _synth_info(1))
            if stop_with is not None:
                if isinstance(stop_with, rt.SynthesisCanceled):
                    job.status = "canceled"
                raise stop_with
            await h.on_section(1, 2, "done", _synth_info(1, done=True))
            return {"sections": [{}, {}]}

        ref["h"] = _patch_pipeline(monkeypatch, rt, job=job, explored=[], synthesized=[],
                                   synthesize=_synth)
        asyncio.run(rt._run_deep_research(str(job.id)))
        return ref["h"]

    def test_saved_progress_carries_previews_but_step_events_do_not(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt)

        # 새로고침한 화면은 저장된 result 에서 이미 쓴 절을 되살린다
        saved = h.progress[-1][1]
        assert [s["section"] for s in saved["sections"]] == [
            _synth_info(0, done=True)["section"], _synth_info(1, done=True)["section"]]
        assert set(saved["evidence"]) == {"E0", "E1"}
        # 절 내용은 synth 이벤트가 절마다 한 번만 나른다 — step 이벤트는 매번 가볍다
        assert ["section" in e[1] for e in h.events if e[0] == "synth"] == [
            False, True, False, True]
        assert len(h.announced) == 5          # 진행 저장 4번 + 닫기 1번
        for _, _, res in h.announced:
            assert "evidence" not in res
            assert all("section" not in s for s in res["sections"])

    def test_completed_step_drops_previews(self, monkeypatch):
        # 완료 뒤에는 최종 보고서가 같은 내용을 들고 있다 — 단계 result 에 두 벌 두지 않는다
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt)

        _, status, result, _ = h.finished[-1]
        assert status == "done"
        assert "evidence" not in result
        assert [(s["idx"], s["status"], s["heading"]) for s in result["sections"]] == [
            (0, "done", "하위1"), (1, "done", "하위2")]
        assert all("section" not in s for s in result["sections"])

    def test_failed_step_keeps_the_draft(self, monkeypatch):
        # 멈춘 초안을 보여 주고 내려받는 원천이다
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt, stop_with=ValueError("종합 호출 실패"))

        _, status, result, _ = h.finished[-1]
        assert status == "failed" and result["error"] == "종합 호출 실패"
        assert result["sections"][0]["section"] == _synth_info(0, done=True)["section"]
        assert "section" not in result["sections"][1]
        assert result["evidence"] == _synth_info(0, done=True)["evidence"]
        _, announced_status, announced = h.announced[-1]
        assert announced_status == "failed" and announced["error"] == "종합 호출 실패"
        assert "evidence" not in announced
        assert all("section" not in s for s in announced["sections"])

    def test_canceled_step_keeps_the_draft(self, monkeypatch):
        rt = _load_tasks(monkeypatch)
        h = self._run(monkeypatch, rt, stop_with=rt.SynthesisCanceled())

        _, status, result, _ = h.finished[-1]
        assert status == "failed" and result["error"] == "취소됨"
        assert result["sections"][0]["section"] == _synth_info(0, done=True)["section"]
        assert result["evidence"] == _synth_info(0, done=True)["evidence"]
        _, _, announced = h.announced[-1]
        assert announced["error"] == "취소됨" and "evidence" not in announced

    def test_six_sections_of_thirty_papers_stay_at_report_scale(self, monkeypatch):
        """대목 원문이 대부분이라 미리보기는 최종 보고서와 같은 규모여야 하고, 절마다 알리는
        step 이벤트는 대목 길이와 무관하게 작아야 한다(spec §14-2 크기)."""
        from services.research import synthesizer
        rt = _load_tasks(monkeypatch)
        events = TestStepEvents()._capture(monkeypatch, rt)
        st = ResearchState(job_id="j1", question="질문", params=merge_params({}))
        for i in range(6):
            eids = [f"E{i * 5 + k + 1}" for k in range(5)]
            st.subquestions.append(SubQuestion(idx=i, text=f"하위질문 {i + 1}", evidence_ids=eids))
            for eid in eids:
                # 청크 상한(MAX_CHUNK_TOKENS=1024)에 가까운 1,500자 대목 2개
                st.evidence[eid] = Evidence(
                    id=eid, cnts_id=f"C{eid}", meta={"title": f"논문 {eid}", "authors": "홍길동"},
                    chunks=[Chunk(f"{eid}-{j}", "가" * 1500, j, j, 0.9 - j / 10) for j in range(2)])
        reply = json.dumps({
            "intro": "이 절은 연구 흐름을 정리한다 [E1]. " * 3,
            "summaries": {f"E{n}": "무엇을 했고 무엇을 밝혔는지 요약한다. " * 3 for n in range(1, 31)},
            "future": [{"text": "남은 과제를 적는다."}],
        }, ensure_ascii=False)

        async def fake_chat(messages, *, params=None, timeout=None):
            return reply

        monkeypatch.setattr(synthesizer, "chat", fake_chat)
        progress = rt._SynthProgress(uuid.uuid4())
        report = asyncio.run(rt.synthesize(st, on_section=progress))

        def size(value) -> int:
            return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))

        # 대목 1,500자(4.5KB) × 2 × 30편 ≈ 270KB — 최종 보고서의 evidence 와 같은 규모
        assert size(progress.result()) < size(report) * 1.1
        assert size(progress.result()) < 400_000
        assert size(progress.result(previews=False)) < 3_000
        per_section = [size(e[2]) for e in events if e[1] == "synth" and e[2]["status"] == "done"]
        assert len(per_section) == 6 and max(per_section) < size(report) / 4
```

크기 테스트의 실측값(사본): 보고서 288,866B, `result()` 288,691B, `result(previews=False)` 1,010B, 절마다 `done` 이벤트 약 48,200B.

`TestOrphanStepsKeepProgress.test_deadline_keeps_sections_of_the_running_synthesis` 를 info 를 싣는 호출로 바꾼다. 시간 상한으로 닫혀도 초안이 남는지 확인하려는 것이다.

교체 전:
```python
        async def _one_section_then_hang(state, should_stop):
            await harness["h"].on_section(0, 2, "done")
            await harness["h"].on_section(1, 2, "running")
            await asyncio.sleep(5)      # 두 번째 절 LLM 이 늘어진다

        out, db = self._run_until_deadline(monkeypatch, rt, job, harness,
                                           synthesize=_one_section_then_hang)

        assert out["status"] == "failed" and job.status == "failed"
        (step,) = db.steps
        assert step.kind == "synthesize" and step.status == "failed"
        assert step.result == {
            "sections_total": 2,
            "sections": [{"idx": 0, "status": "done"}, {"idx": 1, "status": "running"}],
            "error": rt.TIMEOUT_ERROR,
        }
```
교체 후:
```python
        async def _one_section_then_hang(state, should_stop):
            await harness["h"].on_section(0, 2, "done", _synth_info(0, done=True))
            await harness["h"].on_section(1, 2, "running", _synth_info(1))
            await asyncio.sleep(5)      # 두 번째 절 LLM 이 늘어진다

        out, db = self._run_until_deadline(monkeypatch, rt, job, harness,
                                           synthesize=_one_section_then_hang)

        assert out["status"] == "failed" and job.status == "failed"
        (step,) = db.steps
        assert step.kind == "synthesize" and step.status == "failed"
        assert step.result["error"] == rt.TIMEOUT_ERROR
        assert [(s["idx"], s["status"]) for s in step.result["sections"]] == [
            (0, "done"), (1, "running")]
        # 시간 상한으로 닫혀도 멈춘 초안(다 쓴 절과 그 근거)이 남는다
        assert step.result["sections"][0]["section"] == _synth_info(0, done=True)["section"]
        assert step.result["evidence"] == _synth_info(0, done=True)["evidence"]
        assert step.result["sections"][1]["started_at"] is not None
```

- [ ] **Step 5: 실행해 실패 확인**

Run: `cd app && python -m pytest tests/test_research_tasks.py -q`

Expected: `18 failed, 64 passed`. 대표 메시지:
- `TypeError: _SynthProgress.__call__() takes 4 positional arguments but 5 were given`
- `clock`·`event_result` 인자를 모른다는 `TypeError`
- 새 모양(`headings`·빈 칸) 단언 불일치 `AssertionError`

- [ ] **Step 6: `_finish`·`_save_progress` 구현**

`app/workers/research_tasks.py` import 를 고친다.

교체 전:
```python
import logging
import uuid
```
교체 후:
```python
import logging
import time
import uuid
```

교체 전:
```python
async def _finish(db: AsyncSession, step: _StepRef, status: str, result: dict | None = None) -> None:
    result = result or {}
    await db.execute(
        update(ResearchStep).where(ResearchStep.id == step.id)
        .values(status=status, result=result, finished_at=_now())
    )
    await db.commit()
    # 저장한 result 를 그대로 싣는다 — 라이브로 본 장면과 다시 연 장면이 같아야 한다.
    await publish(step.job_id, "step", step.event(status, result))
```
교체 후:
```python
async def _finish(
    db: AsyncSession, step: _StepRef, status: str, result: dict | None = None,
    event_result: dict | None = None,
) -> None:
    """단계를 닫는다. event_result 를 주면 알리는 step 이벤트에는 저장한 result 대신 그것을
    싣는다 — 종합 단계의 절 미리보기는 synth 이벤트가 절마다 이미 날랐다."""
    result = result or {}
    await db.execute(
        update(ResearchStep).where(ResearchStep.id == step.id)
        .values(status=status, result=result, finished_at=_now())
    )
    await db.commit()
    # 저장한 result 를 싣는다 — 라이브로 본 장면과 다시 연 장면이 같아야 한다.
    await publish(step.job_id, "step", step.event(
        status, result if event_result is None else event_result))
```

교체 전:
```python
async def _save_progress(db: AsyncSession, step: _StepRef, result: dict) -> None:
    """도는 중인 단계의 result 를 지금까지의 진행으로 덮어쓰고 알린다.

    단계를 닫을 때만 쓰면 탐색 중에 새로 연 화면·재접속한 화면이 그 단계의 앞 회차와
    카운터를 잃는다. 실패해도 탐색은 계속한다 — 이 기록은 화면 복원용이고, 단계를 닫을
    때 _finish 가 최종 결과를 다시 쓴다.
    """
```
교체 후:
```python
async def _save_progress(
    db: AsyncSession, step: _StepRef, result: dict, event_result: dict | None = None,
) -> None:
    """도는 중인 단계의 result 를 지금까지의 진행으로 덮어쓰고 알린다.

    단계를 닫을 때만 쓰면 탐색 중에 새로 연 화면·재접속한 화면이 그 단계의 앞 회차와
    카운터를 잃는다. 실패해도 탐색은 계속한다 — 이 기록은 화면 복원용이고, 단계를 닫을
    때 _finish 가 최종 결과를 다시 쓴다.

    event_result 를 주면 알리는 step 이벤트에는 그것을 싣는다. 종합 단계는 절이 쌓일수록
    result 가 커져, 전부를 매번 알리면 이미 보낸 절 내용을 절마다 다시 나른다.
    """
```

같은 함수의 마지막 줄을 고친다.

교체 전:
```python
    await publish(step.job_id, "step", step.event("running", result))
```
교체 후:
```python
    await publish(step.job_id, "step", step.event(
        "running", result if event_result is None else event_result))
```

- [ ] **Step 7: `_SynthProgress` 구현**

교체 전:
```python
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

    def result(self, **extra: object) -> dict:
        return {
            **extra, "sections_total": self.total,
            "sections": [{"idx": i, "status": st} for i, st in sorted(self.statuses.items())],
        }
```
교체 후:
```python
@dataclass
class _SynthProgress:
    """synthesize 의 on_section 콜백. 절 진행을 synth 이벤트로 흘리면서 종합 단계
    result 에 남길 값도 모은다 — 실패·취소로 끝나도 거기까지의 진행이 남는다.
    step 이 있으면 절이 바뀔 때마다 도는 중인 단계 result 에도 남긴다.

    다 쓴 절의 미리보기(section)와 그 근거(evidence)도 모은다. 작성 중 화면이 그것을 초안으로
    보여 주고, 새로고침·재접속한 화면은 단계 result 에서 이미 쓴 절을 되살린다."""
    job_id: uuid.UUID
    db: AsyncSession | None = None
    step: _StepRef | None = None
    total: int = 0
    statuses: dict[int, str] = field(default_factory=dict)
    headings: list[str] = field(default_factory=list)
    # 절 순번 → {subq_idx, heading, started_at, duration_ms, section}
    details: dict[int, dict] = field(default_factory=dict)
    evidence: dict[str, dict] = field(default_factory=dict)
    # 소요 시간은 단조 시계로 잰다 — 벽시계는 시각 보정으로 뒤로 갈 수 있다. 테스트가 바꿔 끼운다.
    clock: Callable[[], float] = time.monotonic
    _started: dict[int, float] = field(default_factory=dict, init=False, repr=False)

    async def __call__(self, idx: int, total: int, status: str, info: dict | None = None) -> None:
        self.total = total
        self.statuses[idx] = status
        payload = {"section_idx": idx, "total": total, "status": status}
        if info is not None:
            payload.update(self._record(idx, status, info))
        await publish(self.job_id, "synth", payload)
        if self.step is not None:
            # 저장에는 미리보기를 싣고 알림에서는 뺀다 — 절 내용은 위 synth 이벤트가 한 번만 나른다
            await _save_progress(self.db, self.step, self.result(),
                                 event_result=self.result(previews=False))

    def _record(self, idx: int, status: str, info: dict) -> dict:
        """info 를 절 기록에 남기고, synth 이벤트에 더할 값을 돌려준다."""
        self.headings = list(info.get("headings") or self.headings)
        extra = {"subq_idx": info.get("subq_idx"), "heading": info.get("heading"),
                 "headings": self.headings}
        detail = self.details.setdefault(idx, {})
        detail.update(subq_idx=extra["subq_idx"], heading=extra["heading"])
        if status == "running":
            self._started[idx] = self.clock()
            detail["started_at"] = extra["started_at"] = _now().isoformat()
            return extra
        started = self._started.get(idx)
        if started is not None:
            detail["duration_ms"] = extra["duration_ms"] = int((self.clock() - started) * 1000)
        if "section" in info:
            detail["section"] = extra["section"] = info["section"]
        if "evidence" in info:
            self._merge_evidence(info["evidence"])
            extra["evidence"] = info["evidence"]
        return extra

    def _merge_evidence(self, more: dict[str, dict]) -> None:
        """끝난 절들의 근거를 합친다. 한 논문이 두 절에 실리면 절마다 제 대목만 가져오므로
        대목을 chunk_id 로 합친다 — 덮어쓰면 앞 절 인용칩의 대목이 사라진다. 들고 있던 값을
        고치지 않고 새 dict 로 바꿔 넣는다 — 앞서 넘긴 result 가 뒤따라 바뀌지 않게."""
        for eid, ev in more.items():
            have = self.evidence.get(eid)
            if have is None:
                self.evidence[eid] = {**ev, "chunks": list(ev["chunks"])}
                continue
            seen = {c["chunk_id"] for c in have["chunks"]}
            chunks = have["chunks"] + [c for c in ev["chunks"] if c["chunk_id"] not in seen]
            self.evidence[eid] = {
                **have, "chunks": sorted(chunks, key=lambda c: c["score"], reverse=True)}

    def result(self, *, previews: bool = True, **extra: object) -> dict:
        """종합 단계 result. previews=False 면 절 미리보기(sections[].section)와 근거(evidence)를
        뺀다 — 알리는 step 이벤트와, 완료로 닫는 기록(최종 보고서와 중복)에 쓴다."""
        sections = []
        for i, status in sorted(self.statuses.items()):
            d = self.details.get(i, {})
            entry = {"idx": i, "status": status, "subq_idx": d.get("subq_idx"),
                     "heading": d.get("heading"), "started_at": d.get("started_at"),
                     "duration_ms": d.get("duration_ms")}
            if previews and "section" in d:
                entry["section"] = d["section"]
            sections.append(entry)
        out = {**extra, "sections_total": self.total, "headings": list(self.headings),
               "sections": sections}
        if previews and self.evidence:
            out["evidence"] = dict(self.evidence)
        return out
```

(`Callable` 은 이 파일이 이미 `from collections.abc import Awaitable, Callable` 로 들여온다.)

- [ ] **Step 8: 종합 블록의 닫기 규칙과 모델 주석**

`_run_deep_research` 의 종합 블록을 고친다.

교체 전:
```python
            except SynthesisCanceled:
                await _finish(db, step, "failed", progress.result(error="취소됨"))
                return await _stopped(db, jid)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                # stage 는 explored 로 남는다 → POST /api/research/{job_id}/retry 가
                # 탐색을 건너뛰고 여기부터 다시 온다.
                log.exception("[research] 종합 실패 job=%s", jid)
                await db.rollback()
                await _finish(db, step, "failed", progress.result(error=str(e)[:500]))
                return await _end_failed(db, jid, str(e))

            await _finish(db, step, "done", progress.result())
```
교체 후:
```python
            except SynthesisCanceled:
                # 실패·취소로 닫을 때는 절 미리보기를 남긴다 — 멈춘 초안을 보여 주고 내려받는 원천이다
                await _finish(db, step, "failed", progress.result(error="취소됨"),
                              event_result=progress.result(error="취소됨", previews=False))
                return await _stopped(db, jid)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                # stage 는 explored 로 남는다 → POST /api/research/{job_id}/retry 가
                # 탐색을 건너뛰고 여기부터 다시 온다.
                log.exception("[research] 종합 실패 job=%s", jid)
                await db.rollback()
                error = str(e)[:500]
                await _finish(db, step, "failed", progress.result(error=error),
                              event_result=progress.result(error=error, previews=False))
                return await _end_failed(db, jid, str(e))

            # 완료로 닫을 때는 미리보기를 지운다 — 최종 보고서(research_jobs.report)와 같은 내용이다
            await _finish(db, step, "done", progress.result(previews=False))
```

`app/models/research.py` 의 `ResearchStep.result` 모양 주석을 고친다. 주석만 바꾼다.

교체 전:
```python
    # synthesize: {"sections_total": n, "sections": [{"idx": i, "status": "..."}]}
    #             idx 는 절 순번. 도는 중에는 절이 바뀔 때마다 갱신된다.
    #             보강 전 잡은 {"sections": n}(정수)이다.
```
교체 후:
```python
    # synthesize: {"sections_total": n, "headings": [...],
    #              "sections": [{"idx", "status", "subq_idx", "heading", "started_at",
    #                            "duration_ms", "section"?}],
    #              "evidence"?: {eid: {"cnts_id", "meta", "chunks"}}}
    #             idx 는 절 순번. 도는 중에는 절이 바뀔 때마다 갱신된다.
    #             section(다듬은 절)·evidence(끝난 절들의 근거 합집합)는 작성 중 초안의 원천이다.
    #             step 이벤트에는 싣지 않고(synth 이벤트가 절마다 나른다), 완료로 닫으면 지우며
    #             (최종 보고서와 중복), 실패·취소로 닫으면 남긴다(멈춘 초안).
    #             보강 전 잡은 {"sections": n}(정수)이고, 절 미리보기 보강 전 잡은
    #             sections[] 에 {"idx", "status"} 만 있다.
```

- [ ] **Step 9: 통과 확인**

Run: `cd app && python -m pytest tests/test_research_tasks.py -q`
Expected: `82 passed` (기존 70 + 새 12)

Run: `cd app && python -m pytest tests/test_research_synthesizer.py -q`
Expected: `91 passed`

Run: `cd app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py`
Expected: `770 passed` (기준선 745 + Task 1 10 + Task 2 3 + Task 3 12). 경고 2건은 기존 것이다.

- [ ] **Step 10: 커밋**

```bash
git add app/workers/research_tasks.py app/models/research.py app/tests/test_research_tasks.py
git commit -m "[Feat] round04b — 워커가 synth 이벤트에 소제목·시작 시각·워커가 잰 소요 시간·다듬은 절·근거를 싣고 종합 단계 result 에 절 미리보기와 근거 합집합을 쌓는다: 알리는 step 이벤트는 미리보기를 빼 가볍게 두고, 완료로 닫으면 지우며 실패·취소로 닫으면 멈춘 초안으로 남긴다"
```

---

## 단계 2 — 프론트 데이터 (Task 4·5)

### Task 4: 절 미리보기 데이터: 타입 확장, synth 이벤트와 단계 result 합치기

**계약 추가:** 없음. `mergeEvidence` 는 계약에 있는 이름이다. 새로 만드는 `applySynth`·`mergeSection`·`toSectionView` 는 모듈 안에서만 쓰고 내보내지 않는다.

**Files:**
- Modify: `frontend/types/research.ts`
  - `SynthSectionResult`(32–35행)
  - `StepResult` 의 `sections_total` 바로 뒤(49행 부근)
  - `SynthEvent`(237–242행)
  - `SynthSectionView`·`SynthView`(311–321행)
- Modify: `frontend/utils/researchEvents.ts`
  - import 목록(2–28행)
  - `EMPTY_SYNTH`(53행)
  - `applyResearchEvent` 의 `case "synth"`(235–244행)
  - `applyCritique` 바로 뒤에 `applySynth` 추가
  - `synthFrom`(405–420행)
  - `mergeSections`(465–472행) 교체, 그 뒤에 `mergeSection`·`toSectionView`·`mergeEvidence` 추가
- Test: `frontend/tests/unit/researchEvents.test.ts`
  - import(3–15행)
  - 기존 단언 1줄(336행)
  - `describe("보강 전 잡"` 바로 위에 새 describe 추가

- [ ] **Step 1: 실패하는 테스트 작성**

(1) import 를 넓힌다.

교체 전:
```ts
import type { ResearchEvent, ResearchJob, ResearchReport, ResearchStepRow } from "~/types/research";
import {
  applyApproval,
  applyResearchEvent,
  initialResearchView,
  isTerminalEvent,
  refreshView,
```
교체 후:
```ts
import type {
  ReportChunk,
  ReportEvidence,
  ReportSection,
  ResearchEvent,
  ResearchJob,
  ResearchReport,
  ResearchStepRow,
  StepEvent,
  StepResult,
  SynthEvent,
} from "~/types/research";
import {
  applyApproval,
  applyResearchEvent,
  initialResearchView,
  isTerminalEvent,
  mergeEvidence,
  refreshView,
```

(2) 기존 테스트 "다시 받은 snapshot 이 앞선 절 상태를 되돌리지 않는다" 의 단언을 고친다. 절 뷰에 null 칸이 새로 붙으면 옛 모양 비교가 깨지므로, 이 테스트가 원래 보던 idx·상태만 비교한다.

교체 전:
```ts
    expect(v.synth.sections).toEqual([{ idx: 0, status: "done" }]);
```
교체 후:
```ts
    expect(v.synth.sections.map((s) => [s.idx, s.status])).toEqual([[0, "done"]]);
```

(3) 새 describe 를 넣는다.

교체 전:
```ts
describe("보강 전 잡", () => {
```
교체 후:
```ts
// ── 절 미리보기(spec §14) ─────────────────────────────────
// 절 순번(section_idx)과 하위질문 번호(subq_idx)는 다르다 — 근거 없는 하위질문은 절이 되지 않는다.
// 워커는 절이 끝날 때 synth 이벤트로 다듬은 절·근거를 한 번만 보내고, 진행 저장본(DB)에는 남기되
// 알리는 step 이벤트에는 뺀다(가벼운 step 이벤트).
const T0 = "2026-09-28T01:00:00.123456+00:00";
const T1 = "2026-09-28T01:00:40.654321+00:00";
const HEADINGS = ["효과 측정", "정책 과제"];

function chunk(id: string, score: number): ReportChunk {
  return { chunk_id: id, text: `대목 ${id}`, page_start: 3, page_end: 3, score };
}

function evidence(cntsId: string, chunks: ReportChunk[]): ReportEvidence {
  return { cnts_id: cntsId, meta: { title: `논문 ${cntsId}` }, chunks };
}

const SEC0: ReportSection = {
  heading: "효과 측정",
  intro: "효과가 있었다 [E1]",
  papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1"] }],
  future: [],
  evidence_chunks: { E1: ["k1"] },
  chunk_scores: { k1: 0.9 },
};
const EV0 = { E1: evidence("C1", [chunk("k1", 0.9)]) };
const SYNTH_STEP: StepEvent = {
  kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running",
};
const S0_RUNNING: SynthEvent = {
  kind: "synth", section_idx: 0, total: 2, status: "running",
  subq_idx: 0, heading: "효과 측정", headings: HEADINGS, started_at: T0,
};
const S0_DONE: SynthEvent = {
  kind: "synth", section_idx: 0, total: 2, status: "done",
  subq_idx: 0, heading: "효과 측정", headings: HEADINGS, duration_ms: 38000, section: SEC0, evidence: EV0,
};
const S1_RUNNING: SynthEvent = {
  kind: "synth", section_idx: 1, total: 2, status: "running",
  subq_idx: 2, heading: "정책 과제", headings: HEADINGS, started_at: T1,
};
// 절 1 도 근거 E1 을 쓰지만 자기 절에서 매칭된 대목(k4·k1)만 싣는다
const S1_DONE: SynthEvent = {
  kind: "synth", section_idx: 1, total: 2, status: "done",
  subq_idx: 2, heading: "정책 과제", headings: HEADINGS, duration_ms: 52000,
  section: { ...SEC0, heading: "정책 과제", evidence_chunks: { E1: ["k4", "k1"], E2: ["k9"] } },
  evidence: { E1: evidence("C1", [chunk("k4", 0.95), chunk("k1", 0.9)]), E2: evidence("C2", [chunk("k9", 0.4)]) },
};
// 알리는 step 이벤트·완료로 닫힌 단계의 result — 절 내용(section)·근거(evidence)가 없다
const LIGHT_RESULT: StepResult = {
  sections_total: 2,
  headings: HEADINGS,
  sections: [
    { idx: 0, status: "done", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: 38000 },
    { idx: 1, status: "running", subq_idx: 2, heading: "정책 과제", started_at: T1, duration_ms: null },
  ],
};
// 진행 저장본(snapshot·GET 의 steps[].result) — 끝난 절의 내용과 근거 합집합이 있다
const SAVED_RESULT: StepResult = {
  sections_total: 2,
  headings: HEADINGS,
  sections: [
    { idx: 0, status: "done", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: 38000, section: SEC0 },
    { idx: 1, status: "running", subq_idx: 2, heading: "정책 과제", started_at: T1, duration_ms: null },
  ],
  evidence: EV0,
};
const SYNTH_ROW = step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: SAVED_RESULT });

describe("applyResearchEvent — 절 미리보기", () => {
  it("synth 이벤트로 절 제목·시작 시각·걸린 시간·다듬은 절·근거를 쌓는다", () => {
    const v = run([SYNTH_STEP, S0_RUNNING, S0_DONE, S1_RUNNING]);
    expect(v.synth.headings).toEqual(HEADINGS);
    expect(v.synth.sections).toEqual([
      // done 이벤트에는 started_at 이 없다 — running 때 받은 시작 시각을 지킨다
      { idx: 0, status: "done", subqIdx: 0, heading: "효과 측정", startedAt: T0, durationMs: 38000, section: SEC0 },
      { idx: 1, status: "running", subqIdx: 2, heading: "정책 과제", startedAt: T1, durationMs: null, section: null },
    ]);
    expect(v.synth.evidence).toEqual(EV0);
    expect(synthProgress(v)).toEqual({ current: 2, total: 2 });
  });

  it("진행 저장본(snapshot·GET)으로 다시 연 화면이 라이브로 본 화면과 같은 절을 받는다", () => {
    const live = run([SYNTH_STEP, S0_RUNNING, S0_DONE, S1_RUNNING]);
    const opened = initialResearchView(job({ status: "running", stage: "explored", steps: [PLAN_ROW, SYNTH_ROW] }));
    const snap = applyResearchEvent(initialResearchView(job({ status: "running", stage: "explored" })), {
      kind: "snapshot",
      steps: [PLAN_ROW, SYNTH_ROW],
    });
    for (const v of [opened, snap]) {
      expect(v.synth.sections).toEqual(live.synth.sections);
      expect(v.synth.headings).toEqual(HEADINGS);
      expect(v.synth.evidence).toEqual(EV0);
      expect(v.synth.total).toBe(2);
    }
  });

  it("가벼운 step 이벤트(절 내용·근거 없음)가 받은 절 내용을 지우지 않는다", () => {
    const v = run([SYNTH_STEP, S0_RUNNING, S0_DONE, { ...SYNTH_STEP, result: LIGHT_RESULT }]);
    expect(v.synth.sections.map((s) => [s.idx, s.status, s.section])).toEqual([[0, "done", SEC0], [1, "running", null]]);
    expect(v.synth.evidence).toEqual(EV0);
  });

  it("끊겼다 다시 받은 snapshot 이 뒤처져 있어도 라이브로 받은 절 상태·내용·걸린 시간을 지킨다", () => {
    const behind: StepResult = {
      sections_total: 2,
      headings: HEADINGS,
      sections: [{ idx: 0, status: "running", subq_idx: 0, heading: "효과 측정", started_at: T0, duration_ms: null }],
    };
    const v = applyResearchEvent(run([SYNTH_STEP, S0_RUNNING, S0_DONE]), {
      kind: "snapshot",
      steps: [PLAN_ROW, step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: behind })],
    });
    expect(v.synth.sections[0]).toEqual({
      idx: 0, status: "done", subqIdx: 0, heading: "효과 측정", startedAt: T0, durationMs: 38000, section: SEC0,
    });
    expect(v.synth.evidence).toEqual(EV0);
  });

  it("완료로 닫힌 단계(미리보기 없음)를 GET 으로 다시 맞춰도 받은 절 내용은 남는다", () => {
    // 완료 이벤트 뒤 보고서를 받는 동안·받기에 실패해 다시 시도하는 동안 초안을 그대로 보여 줄 원천
    const live = run([SYNTH_STEP, S0_RUNNING, S0_DONE, { kind: "done", status: "completed" }]);
    const got = job({
      status: "completed", stage: "synthesized",
      steps: [PLAN_ROW, step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "done", result: LIGHT_RESULT })],
    });
    const v = refreshView(live, got);
    expect(v.synth.status).toBe("done");
    expect(v.synth.sections[0]!.section).toEqual(SEC0);
    expect(v.synth.evidence).toEqual(EV0);
  });

  it("새 시도(종합 단계 seq 가 바뀜)면 이전 시도의 절·제목·근거를 비운다", () => {
    const v = run([
      SYNTH_STEP, S0_RUNNING, S0_DONE,
      { ...SYNTH_STEP, status: "failed", result: { ...LIGHT_RESULT, error: "취소됨" } },
      { kind: "status", status: "queued", stage: "explored" },
      { ...SYNTH_STEP, seq: 4 },
    ]);
    expect(v.synth.seq).toBe(4);
    expect(v.synth.sections).toEqual([]);
    expect(v.synth.headings).toEqual([]);
    expect(v.synth.evidence).toEqual({});
  });

  it("새 필드가 없는 옛 이벤트·옛 결과는 빈 칸으로 두고 진행만 센다", () => {
    const live = run([
      SYNTH_STEP,
      { kind: "synth", section_idx: 0, total: 3, status: "running" },
      { kind: "synth", section_idx: 0, total: 3, status: "done" },
    ]);
    expect(live.synth.sections).toEqual([
      { idx: 0, status: "done", subqIdx: null, heading: null, startedAt: null, durationMs: null, section: null },
    ]);
    expect(live.synth.headings).toEqual([]);
    expect(live.synth.evidence).toEqual({});
    expect(synthProgress(live)).toEqual({ current: 1, total: 3 });
    const opened = initialResearchView(job({
      status: "running", stage: "explored",
      steps: [step({ seq: 3, kind: "synthesize", title: "보고서 종합", status: "running", result: { sections_total: 3, sections: [{ idx: 0, status: "done" }] } })],
    }));
    expect(opened.synth.sections).toEqual(live.synth.sections);
    expect(opened.synth.headings).toEqual([]);
    expect(opened.synth.evidence).toEqual({});
  });

  it("같은 근거가 두 절에 나오면 대목을 chunk_id 로 합쳐 점수순으로 둔다", () => {
    const v = run([SYNTH_STEP, S0_RUNNING, S0_DONE, S1_RUNNING, S1_DONE]);
    expect(Object.keys(v.synth.evidence).sort()).toEqual(["E1", "E2"]);
    expect(v.synth.evidence.E1!.chunks.map((c) => c.chunk_id)).toEqual(["k4", "k1"]);
    expect(synthProgress(v)).toEqual({ current: 2, total: 2 });
  });

  it("mergeEvidence 는 원본을 바꾸지 않고 한쪽에만 있는 근거도 싣는다", () => {
    const a = { E1: evidence("C1", [chunk("k1", 0.9), chunk("k2", 0.5)]) };
    const b = { E1: evidence("C1", [chunk("k2", 0.5), chunk("k3", 0.7)]), E2: evidence("C2", [chunk("k9", 0.4)]) };
    const m = mergeEvidence(a, b);
    expect(m.E1!.chunks.map((c) => c.chunk_id)).toEqual(["k1", "k3", "k2"]);
    expect(m.E2).toEqual(b.E2);
    expect(a.E1.chunks.map((c) => c.chunk_id)).toEqual(["k1", "k2"]);
  });
});

describe("보강 전 잡", () => {
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchEvents.test.ts
```
기대 출력: `Tests  9 failed | 56 passed (65)`. 새 describe 의 9개만 FAIL 하고, 기존 56개는 PASS 한다(고친 336행 포함). 대표 메시지:
- `expected undefined to deeply equal [ '효과 측정', '정책 과제' ]`
- `expected [ { idx: +0, status: 'done' } ] to deeply equal [ { idx: +0, status: 'done', …(5) } ]`
- `TypeError: Cannot convert undefined or null to object`
- `TypeError: (0 , mergeEvidence) is not a function`

- [ ] **Step 3: 타입 확장 (`frontend/types/research.ts`)**

교체 전:
```ts
export interface SynthSectionResult {
  idx: number;
  status: SynthSectionStatus;
}
```
교체 후:
```ts
// idx·status 뒤의 칸은 절 미리보기(spec §14)를 싣는 워커만 남긴다 — 옛 결과에는 없다.
// section 은 진행 저장본(DB)에만 있고, 알리는 step 이벤트·완료로 닫힌 단계에서는 빠진다
export interface SynthSectionResult {
  idx: number;
  status: SynthSectionStatus;
  subq_idx?: number;
  heading?: string;
  started_at?: string | null;
  duration_ms?: number | null;
  section?: ReportSection;
}
```

교체 전:
```ts
  sections_total?: number;
  // search 단계가 회차 끝·종료 때 남기는 잡 전체 카운터 — 보강 전 잡에는 없다
  counters?: CountersPayload;
```
교체 후:
```ts
  sections_total?: number;
  // 종합 단계의 절 제목(절 순서)과 끝난 절들이 인용한 근거 합집합 — 보강 전 잡에는 없고,
  // evidence 는 알리는 step 이벤트·완료로 닫힌 단계에서도 빠진다
  headings?: string[];
  evidence?: Record<string, ReportEvidence>;
  // search 단계가 회차 끝·종료 때 남기는 잡 전체 카운터 — 보강 전 잡에는 없다
  counters?: CountersPayload;
```

교체 전:
```ts
export interface SynthEvent {
  kind: "synth";
  section_idx: number;
  total: number;
  status: SynthSectionStatus;
}
```
교체 후:
```ts
export interface SynthEvent {
  kind: "synth";
  section_idx: number;
  total: number;
  status: SynthSectionStatus;
  // 보강 전 워커는 위 셋만 보낸다. started_at 은 running 에, duration_ms·section·evidence 는
  // done·failed 에만 온다 — evidence 는 그 절이 인용한 근거·대목만이다
  subq_idx?: number;
  heading?: string;
  headings?: string[];
  started_at?: string;
  duration_ms?: number;
  section?: ReportSection;
  evidence?: Record<string, ReportEvidence>;
}
```

교체 전:
```ts
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
```
교체 후:
```ts
export interface SynthSectionView {
  idx: number;
  status: SynthSectionStatus;
  subqIdx: number | null;
  heading: string | null;
  startedAt: string | null;
  durationMs: number | null;
  // 최종본과 같은 코드(finalize_section)로 다듬은 절 — 끝난 절에만 있다
  section: ReportSection | null;
}

export interface SynthView {
  seq: number | null;
  status: StepStatus | null;
  total: number;
  sections: SynthSectionView[];
  // 절 순서의 제목 — 아직 쓰기 시작하지 않은 절도 이름을 보여 줄 수 있다
  headings: string[];
  // 끝난 절들이 인용한 근거 합집합 — 초안의 인용칩·내보내기가 읽는다
  evidence: Record<string, ReportEvidence>;
}
```

- [ ] **Step 4: 합치기 구현 (`frontend/utils/researchEvents.ts`)**

(1) import 에 이름 세 개를 더한다.

교체 전:
```ts
  HighlightView,
  ResearchEvent,
```
교체 후:
```ts
  HighlightView,
  ReportEvidence,
  ResearchEvent,
```
교체 전:
```ts
  SubqView,
  SynthSectionStatus,
```
교체 후:
```ts
  SubqView,
  SynthEvent,
  SynthSectionResult,
  SynthSectionStatus,
```

(2) `EMPTY_SYNTH`

교체 전:
```ts
const EMPTY_SYNTH: SynthView = { seq: null, status: null, total: 0, sections: [] };
```
교체 후:
```ts
const EMPTY_SYNTH: SynthView = { seq: null, status: null, total: 0, sections: [], headings: [], evidence: {} };
```

(3) `case "synth"`

교체 전:
```ts
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
```
교체 후:
```ts
    case "synth":
      return { ...view, synth: applySynth(view.synth, event) };
```

(4) `applyCritique` 끝에 `applySynth` 를 붙인다.

교체 전:
```ts
    : next.highlight;
  return { ...next, highlight };
}
```
교체 후:
```ts
    : next.highlight;
  return { ...next, highlight };
}

// 다듬은 절·근거는 절이 끝날 때 synth 이벤트로 한 번만 온다 — 알리는 step 이벤트는 그것을 뺀
// 가벼운 result 를 싣는다(spec §14-2). 보강 전 워커의 이벤트는 idx·total·status 뿐이라 나머지
// 칸은 null 로 남고, 화면은 "보고서 작성 중 2/5" 로 되돌아간다.
function applySynth(synth: SynthView, event: SynthEvent): SynthView {
  const entry = toSectionView({
    idx: event.section_idx,
    status: event.status,
    subq_idx: event.subq_idx,
    heading: event.heading,
    started_at: event.started_at,
    duration_ms: event.duration_ms,
    section: event.section,
  });
  return {
    ...synth,
    status: synth.status ?? "running",
    total: Math.max(synth.total, event.total),
    sections: mergeSections(synth.sections, [entry]),
    headings: event.headings?.length ? event.headings : synth.headings,
    evidence: event.evidence ? mergeEvidence(synth.evidence, event.evidence) : synth.evidence,
  };
}
```

(5) `synthFrom`

교체 전:
```ts
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
```
교체 후:
```ts
// 단계 result 는 진행 저장본(snapshot·GET — 절 내용·근거 포함)과 알리는 step 이벤트(가볍다 —
// 절 내용·근거 없음) 두 길로 온다. 어느 쪽이든 같은 모양으로 합치고 없는 칸이 받은 칸을 지우지
// 않게 한다. 재시도로 새 종합 단계가 열리면(seq 가 바뀜) 이전 시도의 절은 버린다.
function synthFrom(view: ResearchView): SynthView {
  const step = latestOf(view.steps, "synthesize");
  if (!step) return view.synth;
  const r: StepResult = step.result ?? {};
  const listed: SynthSectionView[] = Array.isArray(r.sections) ? r.sections.map(toSectionView) : [];
  const total = r.sections_total ?? (typeof r.sections === "number" ? r.sections : listed.length);
  const sameAttempt = view.synth.seq === null || view.synth.seq === step.seq;
  const prior = sameAttempt ? view.synth : EMPTY_SYNTH;
  return {
    seq: step.seq,
    status: step.status,
    total: Math.max(total, prior.total),
    sections: mergeSections(listed, prior.sections),
    headings: r.headings?.length ? r.headings : prior.headings,
    evidence: mergeEvidence(r.evidence ?? {}, prior.evidence),
  };
}
```

(6) `mergeSections` 를 바꾸고, 그 뒤에 도우미 함수를 붙인다.

교체 전:
```ts
function mergeSections(base: SynthSectionView[], extra: SynthSectionView[]): SynthSectionView[] {
  const out = new Map(base.map((s) => [s.idx, s]));
  for (const s of extra) {
    const cur = out.get(s.idx);
    if (!cur || SECTION_RANK[s.status] >= SECTION_RANK[cur.status]) out.set(s.idx, s);
  }
  return [...out.values()].sort((a, b) => a.idx - b.idx);
}
```
교체 후:
```ts
function mergeSections(base: SynthSectionView[], extra: SynthSectionView[]): SynthSectionView[] {
  const out = new Map(base.map((s) => [s.idx, s]));
  for (const s of extra) {
    const cur = out.get(s.idx);
    out.set(s.idx, cur ? mergeSection(cur, s) : s);
  }
  return [...out.values()].sort((a, b) => a.idx - b.idx);
}

// 상태는 더 나아간 쪽, 나머지 칸은 들어온 값이 있을 때만 바꾼다 — 가벼운 step 이벤트·뒤처진
// snapshot 이 이미 받은 절 내용·걸린 시간을 지우지 않게
function mergeSection(cur: SynthSectionView, s: SynthSectionView): SynthSectionView {
  return {
    idx: cur.idx,
    status: SECTION_RANK[s.status] >= SECTION_RANK[cur.status] ? s.status : cur.status,
    subqIdx: s.subqIdx ?? cur.subqIdx,
    heading: s.heading ?? cur.heading,
    startedAt: s.startedAt ?? cur.startedAt,
    durationMs: s.durationMs ?? cur.durationMs,
    section: s.section ?? cur.section,
  };
}

function toSectionView(s: SynthSectionResult): SynthSectionView {
  return {
    idx: s.idx,
    status: s.status,
    subqIdx: s.subq_idx ?? null,
    heading: s.heading ?? null,
    startedAt: s.started_at ?? null,
    durationMs: s.duration_ms ?? null,
    section: s.section ?? null,
  };
}

// 같은 근거가 여러 절에 나오면 절마다 자기 절이 쓴 대목만 온다(section_evidence) — 대목을
// chunk_id 로 합집합하고, 보고서의 evidence(_serialize_evidence)처럼 점수순으로 둔다
export function mergeEvidence(
  a: Record<string, ReportEvidence>,
  b: Record<string, ReportEvidence>,
): Record<string, ReportEvidence> {
  const out: Record<string, ReportEvidence> = { ...a };
  for (const [eid, ev] of Object.entries(b)) {
    const cur = out[eid];
    if (!cur) {
      out[eid] = ev;
      continue;
    }
    const known = new Set(cur.chunks.map((c) => c.chunk_id));
    const chunks = [...cur.chunks, ...ev.chunks.filter((c) => !known.has(c.chunk_id))]
      .sort((x, y) => y.score - x.score);
    out[eid] = { ...cur, chunks };
  }
  return out;
}
```

- [ ] **Step 5: 통과 확인 (대상 파일 → 전체)**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchEvents.test.ts
```
기대 출력: `Tests  65 passed (65)`. 기존 `synthProgress` 테스트 3개도 그대로 PASS 한다.

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run
```
기대 출력: 모든 Test Files passed, 실패 0(16파일 / 286 tests).

- [ ] **Step 6: 타입 검사**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck
```
기대 결과: 오류 없이 끝난다(exit 0). `SynthSectionView`·`SynthView` 를 직접 만드는 곳은 `researchEvents.ts` 뿐이다. `ProgressPanel.vue`·`pages/research/[id].vue` 는 `synthProgress` 만 쓴다.

- [ ] **Step 7: 커밋**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/types/research.ts frontend/utils/researchEvents.ts frontend/tests/unit/researchEvents.test.ts && git commit -m "[Feat] round04b — 종합 단계 절 미리보기 데이터: synth 이벤트·단계 result 의 절 제목·시작 시각·걸린 시간·다듬은 절·근거를 화면 상태에 합치고, 가벼운 step 이벤트·뒤처진 snapshot 이 받은 절 내용을 지우지 않게, 새 시도면 비운다"
```

---

### Task 5: 보고서 초안·남은 시간 순수 로직 (`utils/researchDraft.ts`)

**계약 보완** (새 공개 이름은 없다. 계약이 정하지 않았거나 모호한 동작만 정했다):
1. `formatRemaining(null, done>0)` 은 `"남은 시간 계산 중"` 을 돌려준다.
   - 계약 "null·done=0 → 첫 절을 쓰는 중" 에서 done=0 은 ms 와 상관없이 그대로 따른다.
   - 끝난 절이 있는데 걸린 시간이 없는 경우는 옛 워커 결과에서만 생긴다. 이때 "2/5 절 완료 · 첫 절을 쓰는 중" 처럼 앞뒤가 맞지 않는 문구가 나오지 않게 했다.
2. 남은 시간이 1분 이상이면 초 자리를 10초 단위로 반올림한다: 89초 → "약 1분 30초 남음", 124초 → "약 2분 남음". 1분 미만은 1초 단위로 쓴다(매초 줄어드는 카운트다운).
3. 종합 단계가 닫혔거나(`synth.status` 가 done·failed) 잡이 끝났으면(`isTerminalStatus`), `draftSlots` 는 running 절을 `"waiting"` 으로 돌려준다.
   - 따라서 `synthEta.runningIdx` 도 null 이 된다.
   - 멈춘 초안에서 움직이는 회색 줄이나 경과 시계가 돌지 않게 하려는 것이다. ReportView 는 `interrupted` 일 때 대기 절 문구만 고르면 된다.
4. `DraftReport.done` 은 초안에 실린 절 수(내용을 받은 끝난 절)이고, `total` 은 절 자리 수(`slots.length`)다.

**Files:**
- Create: `frontend/utils/researchDraft.ts`
- Test: `frontend/tests/unit/researchDraft.test.ts` (신규)
- 의존: Task 4 의 `SynthView.headings·evidence` 와 `SynthSectionView` 새 칸

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/tests/unit/researchDraft.test.ts` 를 새로 만든다.
```ts
// frontend/tests/unit/researchDraft.test.ts
import { describe, expect, it } from "vitest";
import type {
  ReportEvidence,
  ReportSection,
  ResearchEvent,
  ResearchJob,
  ResearchView,
  SynthSectionView,
  SynthView,
} from "~/types/research";
import { draftReport, draftSlots, formatClock, formatRemaining, synthEta } from "~/utils/researchDraft";
import { applyResearchEvent, initialResearchView } from "~/utils/researchEvents";

const NOW = Date.parse("2026-09-28T01:10:00Z");
const HEADINGS3 = ["효과 측정", "교사 인식", "정책 과제"];
const EV: Record<string, ReportEvidence> = {
  E1: {
    cnts_id: "C1", meta: { title: "논문 C1" },
    chunks: [{ chunk_id: "k1", text: "대목", page_start: 3, page_end: 3, score: 0.9 }],
  },
};

function job(over: Partial<ResearchJob> = {}): ResearchJob {
  return {
    job_id: "11111111-1111-4111-8111-111111111111",
    question: "AI 윤리 교육의 효과",
    status: "running",
    stage: "explored",
    plan: HEADINGS3,
    report: null,
    last_error: null,
    steps: [],
    ...over,
  };
}

function section(heading: string): ReportSection {
  return {
    heading,
    intro: `${heading} 도입 [E1]`,
    papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1"] }],
    future: [],
    evidence_chunks: { E1: ["k1"] },
    chunk_scores: { k1: 0.9 },
  };
}

function sec(idx: number, status: SynthSectionView["status"], over: Partial<SynthSectionView> = {}): SynthSectionView {
  return { idx, status, subqIdx: idx, heading: null, startedAt: null, durationMs: null, section: null, ...over };
}

function viewWith(synth: Partial<SynthView>, over: Partial<ResearchView> = {}): ResearchView {
  return {
    ...initialResearchView(job()),
    ...over,
    synth: { seq: 3, status: "running", total: 0, sections: [], headings: [], evidence: {}, ...synth },
  };
}

// 워커가 보내는 started_at 모양(UTC 오프셋 표기)으로 NOW 보다 ms 만큼 앞선 시각
function ago(ms: number): string {
  return new Date(NOW - ms).toISOString().replace("Z", "+00:00");
}

describe("draftSlots", () => {
  it("절 순서대로 끝남·작성 중·대기를 매기고, 내용을 받은 끝난 절에만 초안 위치를 준다", () => {
    const v = viewWith({
      total: 4,
      headings: [...HEADINGS3, "향후 방향"],
      sections: [
        sec(0, "done", { durationMs: 38000, section: section("효과 측정") }),
        sec(1, "failed", { durationMs: 61000, section: section("교사 인식") }),
        sec(2, "running", { startedAt: ago(12000) }),
      ],
    });
    expect(draftSlots(v)).toEqual([
      { idx: 0, heading: "효과 측정", status: "done", durationMs: 38000, startedAt: null, sectionIndex: 0 },
      { idx: 1, heading: "교사 인식", status: "failed", durationMs: 61000, startedAt: null, sectionIndex: 1 },
      { idx: 2, heading: "정책 과제", status: "running", durationMs: null, startedAt: ago(12000), sectionIndex: null },
      { idx: 3, heading: "향후 방향", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null },
    ]);
  });

  it("제목은 절 제목 목록 → 이벤트의 제목 → 다듬은 절의 제목 → '절 N' 순으로 고르고 빈 제목은 건너뛴다", () => {
    const v = viewWith({
      total: 4,
      headings: ["효과 측정", "  "],
      sections: [
        sec(0, "done", { heading: "이벤트 제목", section: section("절 제목") }),
        sec(1, "done", { heading: "교사 인식", section: section("절 제목") }),
        sec(2, "done", { section: section("정책 과제") }),
      ],
    });
    expect(draftSlots(v).map((s) => s.heading)).toEqual(["효과 측정", "교사 인식", "정책 과제", "절 4"]);
  });

  it("total 을 모르면 제목 목록·받은 절 번호로 센다", () => {
    const v = viewWith({ total: 0, sections: [sec(0, "done"), sec(2, "running")] });
    expect(draftSlots(v).map((s) => [s.idx, s.status])).toEqual([[0, "done"], [1, "waiting"], [2, "running"]]);
    expect(draftSlots(viewWith({ total: 0, headings: HEADINGS3 }))).toHaveLength(3);
  });

  it("끝났어도 절 내용이 없으면(옛 워커) 초안 위치가 없다", () => {
    const v = viewWith({ total: 2, sections: [sec(0, "done"), sec(1, "done", { section: section("교사 인식") })] });
    expect(draftSlots(v).map((s) => s.sectionIndex)).toEqual([null, 0]);
  });

  it("실패·취소로 멈춘 초안에서는 작성 중이던 절을 대기로 본다", () => {
    const v = viewWith(
      { status: "failed", total: 2, sections: [sec(0, "done", { section: section("효과 측정") }), sec(1, "running", { startedAt: ago(5000) })] },
      { status: "canceled" },
    );
    expect(draftSlots(v).map((s) => s.status)).toEqual(["done", "waiting"]);
    expect(synthEta(v, NOW).runningIdx).toBeNull();
  });
});

describe("draftReport", () => {
  it("끝난 절(내용 있음)이 없으면 null", () => {
    expect(draftReport(viewWith({ total: 2, sections: [sec(0, "running", { startedAt: ago(1000) })] }))).toBeNull();
    expect(draftReport(viewWith({ total: 2, sections: [sec(0, "done")] }))).toBeNull();
  });

  it("끝난 절을 절 순서대로 모아 보고서 모양으로 만든다 — 한계 없음, 근거는 합집합, stats 는 라이브 카운터", () => {
    const s0 = section("효과 측정");
    const s2 = section("정책 과제");
    const v = viewWith(
      {
        total: 3, headings: HEADINGS3, evidence: EV,
        sections: [sec(0, "done", { section: s0 }), sec(1, "running"), sec(2, "done", { section: s2 })],
      },
      { counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 2 } },
    );
    const d = draftReport(v)!;
    expect(d.report).toEqual({
      question: "AI 윤리 교육의 효과",
      range: null,
      sections: [s0, s2],
      evidence: EV,
      trail: [],
      limitations: [],
      stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 },
    });
    expect([d.done, d.total]).toEqual([2, 3]);
    expect(d.slots.map((s) => s.sectionIndex)).toEqual([0, null, 1]);
  });

  it("라이브 카운터가 하나라도 비면 stats 를 싣지 않는다", () => {
    const v = viewWith(
      { total: 1, sections: [sec(0, "done", { section: section("효과 측정") })] },
      { counters: { papersReviewed: null, evidenceAdopted: 3, rechecks: 0 } },
    );
    expect("stats" in draftReport(v)!.report).toBe(false);
  });

  it("synth 이벤트로 쌓은 화면에서 초안과 남은 시간을 만든다", () => {
    const s0 = section("효과 측정");
    const headings = ["효과 측정", "정책 과제"];
    const events: ResearchEvent[] = [
      { kind: "step", seq: 3, step_kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running" },
      { kind: "synth", section_idx: 0, total: 2, status: "running", subq_idx: 0, heading: "효과 측정", headings, started_at: ago(40000) },
      {
        kind: "synth", section_idx: 0, total: 2, status: "done", subq_idx: 0, heading: "효과 측정", headings,
        duration_ms: 38000, section: s0, evidence: EV,
      },
    ];
    const v = events.reduce((view, e) => applyResearchEvent(view, e), initialResearchView(job()));
    const d = draftReport(v)!;
    expect(d.report.sections).toEqual([s0]);
    expect(d.report.evidence).toEqual(EV);
    expect(d.slots.map((s) => [s.heading, s.status])).toEqual([["효과 측정", "done"], ["정책 과제", "waiting"]]);
    expect(synthEta(v, NOW)).toEqual({ done: 1, total: 2, runningIdx: null, runningElapsedMs: null, remainingMs: 38000 });
  });
});

describe("synthEta", () => {
  const twoFinished = (running: Partial<SynthSectionView>) => viewWith({
    total: 4,
    sections: [
      sec(0, "done", { durationMs: 30000, section: section("가") }),
      sec(1, "failed", { durationMs: 50000, section: section("나") }),
      sec(2, "running", running),
    ],
  });

  it("끝난 절이 없으면 남은 시간을 모른다 — '첫 절을 쓰는 중'", () => {
    const eta = synthEta(viewWith({ total: 3, headings: HEADINGS3, sections: [sec(0, "running", { startedAt: ago(12000) })] }), NOW);
    expect(eta).toEqual({ done: 0, total: 3, runningIdx: 0, runningElapsedMs: 12000, remainingMs: null });
    expect(formatRemaining(eta.remainingMs, eta.done)).toBe("첫 절을 쓰는 중");
  });

  it("끝난 절(실패 포함)의 평균 × 대기 절 수 + 쓰는 중인 절의 (평균 − 경과)", () => {
    // 평균 40초 · 대기 1절 40초 + 쓰는 중 40−10=30초
    expect(synthEta(twoFinished({ startedAt: ago(10000) }), NOW))
      .toEqual({ done: 2, total: 4, runningIdx: 2, runningElapsedMs: 10000, remainingMs: 70000 });
  });

  it("쓰는 중인 절이 평균보다 오래 걸리면 그 절 몫은 0 으로 자른다", () => {
    const eta = synthEta(twoFinished({ startedAt: ago(55000) }), NOW);
    expect(eta.runningElapsedMs).toBe(55000);
    expect(eta.remainingMs).toBe(40000);
  });

  it("started_at 이 화면 시계보다 미래여도(시계 차) 경과는 0 이다", () => {
    const eta = synthEta(twoFinished({ startedAt: new Date(NOW + 5000).toISOString() }), NOW);
    expect(eta.runningElapsedMs).toBe(0);
    expect(eta.remainingMs).toBe(80000);
  });

  it("워커가 보내는 마이크로초 ISO 시각도 읽는다", () => {
    const eta = synthEta(twoFinished({ startedAt: "2026-09-28T01:09:48.123456+00:00" }), NOW);
    expect(eta.runningElapsedMs).toBe(11877);
  });

  it("모든 절이 끝났으면 남은 시간은 0 — '곧 끝납니다'", () => {
    const eta = synthEta(viewWith({
      total: 2,
      sections: [sec(0, "done", { durationMs: 30000, section: section("가") }), sec(1, "done", { durationMs: 20000, section: section("나") })],
    }), NOW);
    expect(eta).toEqual({ done: 2, total: 2, runningIdx: null, runningElapsedMs: null, remainingMs: 0 });
    expect(formatRemaining(eta.remainingMs, eta.done)).toBe("곧 끝납니다");
  });

  it("걸린 시간이 없는 끝난 절(옛 워커)만 있으면 남은 시간을 모른다", () => {
    const eta = synthEta(viewWith({
      total: 2,
      sections: [sec(0, "done", { section: section("가") }), sec(1, "running", { startedAt: ago(3000) })],
    }), NOW);
    expect(eta.remainingMs).toBeNull();
    expect(formatRemaining(eta.remainingMs, eta.done)).toBe("남은 시간 계산 중");
  });
});

describe("formatClock", () => {
  it("분:초 로 쓰고 초는 버림, 음수·NaN 은 0:00", () => {
    expect(formatClock(38_000)).toBe("0:38");
    expect(formatClock(38_900)).toBe("0:38");
    expect(formatClock(65_000)).toBe("1:05");
    expect(formatClock(723_000)).toBe("12:03");
    expect(formatClock(-500)).toBe("0:00");
    expect(formatClock(Number.NaN)).toBe("0:00");
  });
});

describe("formatRemaining", () => {
  it("첫 절 전·10초 미만·1분 미만·1분 이상(10초 단위 반올림)을 나눠 쓴다", () => {
    expect(formatRemaining(null, 0)).toBe("첫 절을 쓰는 중");
    expect(formatRemaining(40_000, 0)).toBe("첫 절을 쓰는 중");
    expect(formatRemaining(9_400, 2)).toBe("곧 끝납니다");
    expect(formatRemaining(40_000, 2)).toBe("약 40초 남음");
    expect(formatRemaining(59_700, 1)).toBe("약 1분 남음");
    expect(formatRemaining(90_000, 2)).toBe("약 1분 30초 남음");
    expect(formatRemaining(124_000, 2)).toBe("약 2분 남음");
    expect(formatRemaining(null, 2)).toBe("남은 시간 계산 중");
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchDraft.test.ts
```
기대 출력:
- `FAIL  tests/unit/researchDraft.test.ts`
- `Error: Cannot find module '~/utils/researchDraft' imported from '.../tests/unit/researchDraft.test.ts'`
- `Test Files  1 failed (1)`, `Tests  no tests`

- [ ] **Step 3: 최소 구현**

`frontend/utils/researchDraft.ts` 를 새로 만든다.
```ts
// frontend/utils/researchDraft.ts
import type {
  CountersPayload,
  CountersView,
  ReportSection,
  ResearchReport,
  ResearchView,
  SynthSectionView,
} from "../types/research";
import { isTerminalStatus } from "./researchEvents";

export type DraftSlotStatus = "done" | "failed" | "running" | "waiting";

// 작성 현황 카드의 한 줄이자 초안의 절 자리 하나. idx 는 워커의 section_idx(절 순번)와 같다
export interface DraftSlot {
  idx: number;
  heading: string;
  status: DraftSlotStatus;
  durationMs: number | null;
  startedAt: string | null;
  // DraftReport.report.sections 안의 위치 — 내용을 받은 끝난 절에만 있다
  sectionIndex: number | null;
}

export interface DraftReport {
  report: ResearchReport;
  slots: DraftSlot[];
  done: number;
  total: number;
}

export interface SynthEta {
  done: number;
  total: number;
  runningIdx: number | null;
  runningElapsedMs: number | null;
  remainingMs: number | null;
}

export function draftSlots(view: ResearchView): DraftSlot[] {
  const byIdx = new Map(view.synth.sections.map((s) => [s.idx, s]));
  const stopped = isStopped(view);
  const slots: DraftSlot[] = [];
  let placed = 0;
  for (let idx = 0; idx < slotCount(view); idx++) {
    const s = byIdx.get(idx);
    const finished = s?.status === "done" || s?.status === "failed";
    slots.push({
      idx,
      heading: slotHeading(view, idx, s),
      status: slotStatus(s, stopped),
      durationMs: s?.durationMs ?? null,
      startedAt: s?.startedAt ?? null,
      sectionIndex: finished && s?.section ? placed++ : null,
    });
  }
  return slots;
}

// 끝난 절을 절 순서대로 모아 최종 보고서와 같은 모양으로 만든다 — ReportView·내보내기가 최종본과
// 같은 코드로 그리게. 한계는 보고서가 완성된 뒤에만 있으므로 비워 둔다.
export function draftReport(view: ResearchView): DraftReport | null {
  const slots = draftSlots(view);
  const byIdx = new Map(view.synth.sections.map((s) => [s.idx, s.section]));
  const sections = slots
    .filter((slot) => slot.sectionIndex !== null)
    .map((slot) => byIdx.get(slot.idx))
    .filter((sec): sec is ReportSection => !!sec);
  if (!sections.length) return null;
  const stats = liveStats(view.counters);
  return {
    report: {
      question: view.question,
      range: null,
      sections,
      evidence: view.synth.evidence,
      trail: [],
      limitations: [],
      ...(stats ? { stats } : {}),
    },
    slots,
    done: sections.length,
    total: slots.length,
  };
}

// 남은 시간 = 끝난 절들의 걸린 시간 평균 × 대기 절 수 + 쓰는 중인 절의 (평균 − 경과, 0 미만이면 0).
// 걸린 시간은 워커가 잰 값이라 화면 시계와 무관하다. 경과만 화면 시계(nowMs)와 서버의 started_at 을
// 견주므로, 두 시계가 어긋나 started_at 이 미래로 보여도 음수가 되지 않게 자른다.
export function synthEta(view: ResearchView, nowMs: number): SynthEta {
  const slots = draftSlots(view);
  const finished = slots.filter((s) => s.status === "done" || s.status === "failed");
  const running = slots.find((s) => s.status === "running");
  const runningElapsedMs = running ? elapsedSince(running.startedAt, nowMs) : null;
  const durations = finished.map((s) => s.durationMs).filter((d): d is number => d !== null && d >= 0);
  let remainingMs: number | null = null;
  if (durations.length) {
    const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length;
    const waiting = slots.filter((s) => s.status === "waiting").length;
    const current = running ? Math.max(0, avg - (runningElapsedMs ?? 0)) : 0;
    remainingMs = Math.round(avg * waiting + current);
  }
  return {
    done: finished.length,
    total: slots.length,
    runningIdx: running?.idx ?? null,
    runningElapsedMs,
    remainingMs,
  };
}

export function formatClock(ms: number): string {
  const total = Number.isFinite(ms) ? Math.max(0, Math.floor(ms / 1000)) : 0;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function formatRemaining(ms: number | null, done: number): string {
  if (done <= 0) return "첫 절을 쓰는 중";
  // 끝난 절은 있는데 걸린 시간을 모른다(옛 워커의 결과) — "첫 절을 쓰는 중"이라 적으면 틀린 말이 된다
  if (ms === null || !Number.isFinite(ms)) return "남은 시간 계산 중";
  const sec = Math.round(Math.max(0, ms) / 1000);
  if (sec < 10) return "곧 끝납니다";
  if (sec < 60) return `약 ${sec}초 남음`;
  // 1분을 넘으면 초 자리를 10초 단위로 반올림한다 — 긴 추정을 초 단위로 적으면 매초 흔들려 읽기 어렵다
  const rounded = Math.round(sec / 10) * 10;
  const m = Math.floor(rounded / 60);
  const s = rounded % 60;
  return s ? `약 ${m}분 ${s}초 남음` : `약 ${m}분 남음`;
}

// 절 수는 워커가 알린 total 이 정본이다. 모르면(옛 결과·첫 이벤트 전) 제목 목록·받은 절 번호로 센다
function slotCount(view: ResearchView): number {
  const { total, headings, sections } = view.synth;
  const known = sections.reduce((n, s) => Math.max(n, s.idx + 1), 0);
  return Math.max(total, headings.length, known);
}

function slotHeading(view: ResearchView, idx: number, s: SynthSectionView | undefined): string {
  const named = [view.synth.headings[idx], s?.heading, s?.section?.heading].find((h) => h?.trim());
  return named?.trim() || `절 ${idx + 1}`;
}

function slotStatus(s: SynthSectionView | undefined, stopped: boolean): DraftSlotStatus {
  if (!s) return "waiting";
  // 실패·취소로 멈춘 뒤의 "작성 중"은 더 쓰이지 않는다 — 움직이는 줄·경과 시계를 띄우지 않게 대기로 본다
  if (s.status === "running" && stopped) return "waiting";
  return s.status;
}

function isStopped(view: ResearchView): boolean {
  return view.synth.status === "done" || view.synth.status === "failed" || isTerminalStatus(view.status);
}

// 보고서 서론 한 줄(reportIntro)이 읽는 stats — 라이브 카운터가 셋 다 있을 때만 싣는다.
// 하나라도 비면(옛 잡) 서론은 근거 수만 쓰는 옛 문장으로 되돌아간다
function liveStats(c: CountersView): CountersPayload | null {
  if (c.papersReviewed === null || c.evidenceAdopted === null || c.rechecks === null) return null;
  return { papers_reviewed: c.papersReviewed, evidence_adopted: c.evidenceAdopted, rechecks: c.rechecks };
}

function elapsedSince(startedAt: string | null, nowMs: number): number | null {
  if (!startedAt) return null;
  const t = Date.parse(startedAt);
  return Number.isNaN(t) ? null : Math.max(0, nowMs - t);
}
```

- [ ] **Step 4: 통과 확인 (대상 파일 → 전체)**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run tests/unit/researchDraft.test.ts
```
기대 출력: `Tests  18 passed (18)`

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx vitest run
```
기대 출력: 모든 Test Files passed, 실패 0(17파일 / 304 tests).

- [ ] **Step 5: 타입 검사**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI/frontend && npx nuxi typecheck
```
기대 결과: 오류 없이 끝난다(exit 0). strict 와 `noUncheckedIndexedAccess` 에서 `headings[idx]` 는 `string | undefined` 로 처리했다.

- [ ] **Step 6: 커밋**

```bash
cd /c/Users/LANDSOFT/mygit/NL_library_AI && git add frontend/utils/researchDraft.ts frontend/tests/unit/researchDraft.test.ts && git commit -m "[Feat] round04b — 보고서 초안·남은 시간 순수 로직: 끝난 절을 절 순서대로 모은 초안(한계 없음·라이브 카운터 stats), 절 자리 목록(제목 폴백·total 모름·멈춘 초안의 작성 중은 대기), 끝난 절 평균으로 남은 시간(쓰는 중 절 경과 차감·시계 차 음수 방지)과 시계·남은 시간 문구"
```

> 검증 메모: Task 4·5 의 코드와 테스트는 저장소 밖 사본에서 실제로 돌려 확인했다.
> - 구현 전: Task 4 는 9 failed / 56 passed, Task 5 는 모듈을 찾지 못해 실패했다.
> - 구현 후: 65 passed, 18 passed.
> - strict·noUncheckedIndexedAccess 로 tsc 검사를 통과했다.

---

## 단계 3 — 초안 화면 (Task 6·7)

### Task 6: 보고서 작성 현황 카드 (`SynthProgressCard.vue`) · 화면 시계 (`useNow`)

**계약 추가:**
- `frontend/utils/synthCard.ts` (새 파일, 순수 함수). 카드에 들어가는 글과 계산을 Vitest 로 검증하려고 뺐다.
  - `synthSummary(eta: SynthEta): string`
  - `slotStateLabel(slot: DraftSlot, eta: SynthEta): string`
  - `barFraction(eta: SynthEta): number` (0~1)
  - `newlyFinished(prev: ReadonlyMap<number, DraftSlotStatus> | null, slots: readonly DraftSlot[]): number[]`
  - `finishedAnnouncement(slots: readonly DraftSlot[], idxs: readonly number[]): string`
- CSS 클래스 `.rs-sr-only` (화면에서는 숨기고 스크린리더만 읽는 글).
- 절 완성 알림(`aria-live="polite"`)은 이 카드가 맡는다. 카드는 첫 절이 끝나기 전부터 떠 있어서 알림 영역이 내용보다 먼저 생긴다. 초안 `ReportView` 는 첫 절이 끝나야 생기므로, 거기에 두면 첫 알림이 읽히지 않는다.

**선행:** Task 5 (`utils/researchDraft.ts`의 `DraftSlot`·`DraftSlotStatus`·`SynthEta`·`formatClock`·`formatRemaining`).
- `SynthEta.done` 은 끝난 절(done + failed) 수라는 Task 5 규칙을 전제로 한다.
- `remainingMs` 는 spec §14-3 식(평균 × 대기 절 + max(0, 평균 − 경과))을 전제로 한다.

**인터랙션 (spec §7-4, §14-3):**
- 진행 막대에는 쓰는 중인 절의 몫도 경과에 따라 채운다. 막대는 1초 linear transition 으로 끊김 없이 늘어나고, 쓰는 동안은 빛줄기가 지나간다.
- 쓰는 중인 절의 아이콘은 도는 링이다. 방금 끝난 절은 체크 표시가 0.9초 튀어 오른다. 처음 그릴 때(새로고침)는 튀어 오르지 않는다.
- 초안이 생긴 뒤(끝난 절 ≥ 1)에는 항목이 버튼이 된다. 누르면 `jump`, 포인터나 초점을 올리면 `hover(idx)`, 떠나면 `hover(null)`.
- `prefers-reduced-motion` 이면 transition·애니메이션을 모두 끈다.
- `actions` 슬롯은 비워 둔다. [초안 저장 ▾] 메뉴는 Task 10 이 끼운다.

**Files:**
- Create: `frontend/utils/synthCard.ts`
- Test: `frontend/tests/unit/synthCard.test.ts`
- Create: `frontend/composables/useNow.ts`
- Create: `frontend/components/research/SynthProgressCard.vue`
- Modify: `frontend/assets/css/research.css` (파일 끝의 `.rs-plus__error { … }` 블록 뒤에 "보고서 작성 현황" 절을 덧붙인다)

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/tests/unit/synthCard.test.ts`

```ts
// frontend/tests/unit/synthCard.test.ts
import { describe, expect, it } from "vitest";
import type { DraftSlot, DraftSlotStatus, SynthEta } from "~/utils/researchDraft";
import { formatClock, formatRemaining } from "~/utils/researchDraft";
import { barFraction, finishedAnnouncement, newlyFinished, slotStateLabel, synthSummary } from "~/utils/synthCard";

function eta(over: Partial<SynthEta> = {}): SynthEta {
  return { done: 0, total: 5, runningIdx: null, runningElapsedMs: null, remainingMs: null, ...over };
}

function slot(over: Partial<DraftSlot> = {}): DraftSlot {
  return { idx: 0, heading: "가", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null, ...over };
}

describe("synthSummary", () => {
  it("절 수를 모르면 준비 중이라고만 쓴다", () => {
    expect(synthSummary(eta({ total: 0 }))).toBe("보고서 작성을 준비하는 중");
  });

  it("끝난 절 수와 남은 시간을 쓴다", () => {
    expect(synthSummary(eta({ done: 2, remainingMs: 90_000 }))).toBe(`2/5 절 완료 · ${formatRemaining(90_000, 2)}`);
  });

  it("첫 절 전에는 남은 시간 대신 첫 절을 쓰는 중이라고 쓴다", () => {
    expect(synthSummary(eta({ runningIdx: 0, runningElapsedMs: 5_000 }))).toBe(`0/5 절 완료 · ${formatRemaining(null, 0)}`);
  });

  it("절마다 걸린 시간이 없는 옛 워커는 남은 시간을 빼고 쓴다", () => {
    expect(synthSummary(eta({ done: 2, remainingMs: null }))).toBe("2/5 절 완료");
  });

  it("모든 절을 썼으면 마무리 중이라고 쓴다", () => {
    expect(synthSummary(eta({ done: 5, remainingMs: 0 }))).toBe("5/5 절 완료 · 보고서를 마무리하는 중");
  });
});

describe("slotStateLabel", () => {
  it("끝난 절은 걸린 시간을, 모르면 완료만 쓴다", () => {
    expect(slotStateLabel(slot({ status: "done", durationMs: 38_000 }), eta())).toBe(`완료 ${formatClock(38_000)}`);
    expect(slotStateLabel(slot({ status: "done" }), eta())).toBe("완료");
  });

  it("쓰는 중인 절은 경과를 쓴다", () => {
    const e = eta({ runningIdx: 2, runningElapsedMs: 12_000 });
    expect(slotStateLabel(slot({ idx: 2, status: "running" }), e)).toBe(`작성 중 ${formatClock(12_000)}`);
    expect(slotStateLabel(slot({ idx: 3, status: "running" }), e)).toBe("작성 중");
  });

  it("실패·대기 절", () => {
    expect(slotStateLabel(slot({ status: "failed" }), eta())).toBe("서술 받지 못함");
    expect(slotStateLabel(slot({ status: "waiting" }), eta())).toBe("대기");
  });
});

describe("barFraction", () => {
  it("절 수를 모르면 0", () => {
    expect(barFraction(eta({ total: 0 }))).toBe(0);
  });

  it("쓰는 중인 절이 없으면 끝난 절의 비율이다", () => {
    expect(barFraction(eta({ done: 2 }))).toBeCloseTo(0.4);
  });

  it("쓰는 중인 절은 평균 대비 경과만큼 채운다", () => {
    // 평균 40초, 대기 2절, 경과 10초 → 남은 시간 40×2 + 30 = 110초
    expect(barFraction(eta({ done: 2, runningIdx: 2, runningElapsedMs: 10_000, remainingMs: 110_000 }))).toBeCloseTo(2.25 / 5);
  });

  it("평균을 넘겨도 쓰는 중인 절은 다 차지 않는다", () => {
    expect(barFraction(eta({ done: 2, runningIdx: 2, runningElapsedMs: 60_000, remainingMs: 80_000 }))).toBeCloseTo(2.9 / 5);
  });

  it("첫 절은 평균이 없어 30초마다 남은 거리의 절반씩 다가간다", () => {
    expect(barFraction(eta({ runningIdx: 0, runningElapsedMs: 30_000 }))).toBeCloseTo(0.45 / 5);
    expect(barFraction(eta({ runningIdx: 0, runningElapsedMs: 0 }))).toBe(0);
  });

  it("다 쓰면 1 이고 넘치지 않는다", () => {
    expect(barFraction(eta({ done: 5 }))).toBe(1);
    expect(barFraction(eta({ done: 7 }))).toBe(1);
  });
});

describe("newlyFinished", () => {
  const prev = new Map<number, DraftSlotStatus>([
    [0, "done"],
    [1, "running"],
    [2, "waiting"],
  ]);

  it("처음 그릴 때는 없다", () => {
    expect(newlyFinished(null, [slot({ idx: 0, status: "done" })])).toEqual([]);
  });

  it("직전에 끝나지 않았던 절 중 이번에 끝난 절", () => {
    const slots = [
      slot({ idx: 0, status: "done" }),
      slot({ idx: 1, status: "done" }),
      slot({ idx: 2, status: "failed" }),
      slot({ idx: 3, status: "running" }),
    ];
    expect(newlyFinished(prev, slots)).toEqual([1, 2]);
  });

  it("직전 목록에 없던 절이 끝난 채로 오면(재접속 snapshot) 끝난 것으로 본다", () => {
    expect(newlyFinished(new Map(), [slot({ idx: 0, status: "done" })])).toEqual([0]);
  });
});

describe("finishedAnnouncement", () => {
  it("끝난 절을 번호·제목으로 한 번에 알린다", () => {
    const slots = [slot({ idx: 0, heading: "가", status: "done" }), slot({ idx: 1, heading: "나", status: "failed" })];
    expect(finishedAnnouncement(slots, [0, 1])).toBe("절 1 작성 완료: 가. 절 2 서술 받지 못함, 논문 목록만 싣습니다: 나");
    expect(finishedAnnouncement(slots, [])).toBe("");
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd frontend && npx vitest run tests/unit/synthCard.test.ts
```
기대 출력:
```
Error: Cannot find module '~/utils/synthCard' imported from '…/frontend/tests/unit/synthCard.test.ts'.
Test Files  1 failed (1)
```

- [ ] **Step 3: 최소 구현**

`frontend/utils/synthCard.ts`

```ts
// frontend/utils/synthCard.ts
import type { DraftSlot, DraftSlotStatus, SynthEta } from "./researchDraft";
import { formatClock, formatRemaining } from "./researchDraft";

// 쓰는 중인 절이 끝나기 전에 막대가 다 차 보이면 멈춘 것처럼 읽힌다 — 끝날 때까지 이 비율 아래에 둔다
const RUNNING_CAP = 0.9;
// 첫 절은 평균이 없어 예상 소요를 모른다 — 30초마다 남은 거리의 절반씩 다가간다
const FIRST_HALF_LIFE_MS = 30_000;

const FINISHED: readonly DraftSlotStatus[] = ["done", "failed"];

export function synthSummary(eta: SynthEta): string {
  if (eta.total <= 0) return "보고서 작성을 준비하는 중";
  const head = `${Math.min(eta.done, eta.total)}/${eta.total} 절 완료`;
  if (eta.done >= eta.total) return `${head} · 보고서를 마무리하는 중`;
  // 절마다 걸린 시간을 주지 않는 옛 워커면 남은 시간을 셀 수 없다 — 모른다고 추측하지 않는다
  if (eta.done > 0 && eta.remainingMs === null) return head;
  return `${head} · ${formatRemaining(eta.remainingMs, eta.done)}`;
}

export function slotStateLabel(slot: DraftSlot, eta: SynthEta): string {
  switch (slot.status) {
    case "done":
      return slot.durationMs !== null ? `완료 ${formatClock(slot.durationMs)}` : "완료";
    case "running":
      return slot.idx === eta.runningIdx && eta.runningElapsedMs !== null
        ? `작성 중 ${formatClock(eta.runningElapsedMs)}`
        : "작성 중";
    case "failed":
      return "서술 받지 못함";
    case "waiting":
      return "대기";
  }
}

// 막대는 끝난 절 + 쓰는 중인 절의 몫이다. 절 하나가 수십 초라 끝날 때만 늘면 막대가 서 있는 것처럼 보인다.
// 몫 = 경과 ÷ 예상 소요, 예상 소요 = (남은 시간 + 경과) ÷ 남은 절 수. synthEta 의 남은 시간은
// 평균 × 대기 절 + max(0, 평균 − 경과) 라, 경과가 평균보다 짧으면 예상 소요가 정확히 평균이 된다.
export function barFraction(eta: SynthEta): number {
  if (eta.total <= 0) return 0;
  const done = Math.min(Math.max(eta.done, 0), eta.total);
  const left = eta.total - done;
  let part = 0;
  if (left > 0 && eta.runningIdx !== null && eta.runningElapsedMs !== null) {
    const elapsed = Math.max(0, eta.runningElapsedMs);
    if (eta.remainingMs !== null) {
      const expected = (eta.remainingMs + elapsed) / left;
      part = expected > 0 ? Math.min(RUNNING_CAP, elapsed / expected) : RUNNING_CAP;
    } else {
      part = RUNNING_CAP * (1 - 0.5 ** (elapsed / FIRST_HALF_LIFE_MS));
    }
  }
  return Math.min(1, (done + part) / eta.total);
}

// 직전 목록과 비교해 이번에 끝난 절. 처음 그릴 때(prev 가 null)는 없다 — 새로고침한 화면에서
// 이미 끝난 절이 한꺼번에 튀어 오르거나 스크린리더가 몰아 읽지 않게
export function newlyFinished(prev: ReadonlyMap<number, DraftSlotStatus> | null, slots: readonly DraftSlot[]): number[] {
  if (!prev) return [];
  return slots
    .filter((s) => FINISHED.includes(s.status) && !FINISHED.includes(prev.get(s.idx) ?? "waiting"))
    .map((s) => s.idx);
}

export function finishedAnnouncement(slots: readonly DraftSlot[], idxs: readonly number[]): string {
  return idxs
    .map((idx) => slots.find((s) => s.idx === idx))
    .filter((s): s is DraftSlot => s !== undefined)
    .map((s) =>
      s.status === "failed"
        ? `절 ${s.idx + 1} 서술 받지 못함, 논문 목록만 싣습니다: ${s.heading}`
        : `절 ${s.idx + 1} 작성 완료: ${s.heading}`,
    )
    .join(". ");
}
```

- [ ] **Step 4: 통과 확인**

```bash
cd frontend && npx vitest run tests/unit/synthCard.test.ts
```
기대 출력: `Tests  18 passed (18)`.

- [ ] **Step 5: 화면 시계 `useNow`**

`frontend/composables/useNow.ts`

```ts
// frontend/composables/useNow.ts
import { getCurrentInstance, onBeforeUnmount, ref, watch, type ComputedRef, type Ref } from "vue";

// 화면 시계. 보고서를 쓰는 동안만 돌린다 — 늘 돌리면 시계를 읽는 화면 전체가 1초마다 다시 그려진다
export function useNow(active: Ref<boolean> | ComputedRef<boolean>, intervalMs = 1000): Ref<number> {
  const now = ref(Date.now());
  let timer: ReturnType<typeof setInterval> | null = null;

  function stop(): void {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function start(): void {
    // 서버 렌더에서 타이머를 걸면 요청이 끝나도 풀리지 않는다
    if (timer || !import.meta.client) return;
    now.value = Date.now();
    timer = setInterval(() => {
      now.value = Date.now();
    }, intervalMs);
  }

  watch(active, (on) => (on ? start() : stop()), { immediate: true });
  if (getCurrentInstance()) onBeforeUnmount(stop);
  return now;
}
```

- [ ] **Step 6: 카드 컴포넌트**

`frontend/components/research/SynthProgressCard.vue`

```vue
<!-- frontend/components/research/SynthProgressCard.vue -->
<template>
  <section class="rs-card rs-synth" aria-labelledby="rs-synth-title">
    <header class="rs-synth__head">
      <div class="rs-card__head">
        <h2 id="rs-synth-title" class="rs-card__title">보고서 작성 현황</h2>
        <p class="rs-synth__summary">{{ summary }}</p>
      </div>
      <div class="rs-synth__actions">
        <slot name="actions" />
      </div>
    </header>

    <div
      class="rs-synth__bar"
      role="progressbar"
      aria-label="보고서 작성 진행"
      aria-valuemin="0"
      :aria-valuemax="eta.total || 1"
      :aria-valuenow="Math.min(eta.done, eta.total)"
      :aria-valuetext="summary"
    >
      <span class="rs-synth__fill" :class="{ 'is-running': eta.runningIdx !== null }" :style="{ width: `${percent}%` }" />
    </div>

    <ol v-if="slots.length" class="rs-synth__list">
      <li v-for="slot in slots" :key="slot.idx">
        <!-- 초안이 생기기 전(끝난 절이 없을 때)에는 옮겨 갈 곳이 없어 누를 수 없는 줄로 그린다 -->
        <component
          :is="canJump ? 'button' : 'div'"
          :type="canJump ? 'button' : undefined"
          class="rs-synth__item"
          :class="[`is-${slot.status}`, { 'is-linked': highlightIdx === slot.idx }]"
          :title="canJump ? '초안의 이 절로 이동' : undefined"
          @click="jump(slot.idx)"
          @mouseenter="hover(slot.idx)"
          @mouseleave="hover(null)"
          @focus="hover(slot.idx)"
          @blur="hover(null)"
        >
          <span class="rs-synth__icon" :class="{ 'is-fresh': fresh.includes(slot.idx) }" aria-hidden="true">{{ ICONS[slot.status] }}</span>
          <span class="rs-synth__name">{{ slot.idx + 1 }}. {{ slot.heading }}</span>
          <span class="rs-synth__state">{{ slotStateLabel(slot, eta) }}</span>
        </component>
      </li>
    </ol>

    <!-- 절이 끝날 때 한 번만 읽힌다. 카드는 첫 절 전부터 떠 있어 알림 영역이 내용보다 먼저 생긴다 -->
    <p class="rs-sr-only" role="status" aria-live="polite">{{ announcement }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { DraftSlot, DraftSlotStatus, SynthEta } from "~/utils/researchDraft";
import { barFraction, finishedAnnouncement, newlyFinished, slotStateLabel, synthSummary } from "~/utils/synthCard";

const props = withDefaults(defineProps<{ slots: DraftSlot[]; eta: SynthEta; highlightIdx?: number | null }>(), {
  highlightIdx: null,
});
const emit = defineEmits<{ jump: [idx: number]; hover: [idx: number | null] }>();

const ICONS: Record<DraftSlotStatus, string> = { done: "✓", running: "", waiting: "·", failed: "✕" };
// 체크 표시가 튀어 오르는 시간(research.css 의 rs-pop 과 맞춘다)
const FRESH_MS = 900;

const summary = computed(() => synthSummary(props.eta));
const percent = computed(() => Math.round(barFraction(props.eta) * 1000) / 10);
const canJump = computed(() => props.slots.some((s) => s.sectionIndex !== null));

const fresh = ref<number[]>([]);
const announcement = ref("");
let prev: Map<number, DraftSlotStatus> | null = null;
let freshTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => props.slots,
  (slots) => {
    const idxs = newlyFinished(prev, slots);
    prev = new Map(slots.map((s) => [s.idx, s.status]));
    if (!idxs.length) return;
    fresh.value = idxs;
    announcement.value = finishedAnnouncement(slots, idxs);
    if (freshTimer) clearTimeout(freshTimer);
    freshTimer = setTimeout(() => {
      fresh.value = [];
    }, FRESH_MS);
  },
  { immediate: true },
);

function jump(idx: number): void {
  if (canJump.value) emit("jump", idx);
}

function hover(idx: number | null): void {
  if (canJump.value) emit("hover", idx);
}

onBeforeUnmount(() => {
  if (freshTimer) clearTimeout(freshTimer);
});
</script>
```

- [ ] **Step 7: 카드 CSS**

`frontend/assets/css/research.css`

찾을 코드 (파일 끝):

```css
.rs-plus__error {
  position: absolute;
  top: calc(100% + 0.4rem);
  left: 0;
  margin: 0;
  font-size: 0.6rem;
  color: var(--skx-ink);
}
```

바꿀 코드:

```css
.rs-plus__error {
  position: absolute;
  top: calc(100% + 0.4rem);
  left: 0;
  margin: 0;
  font-size: 0.6rem;
  color: var(--skx-ink);
}

/* ── 보고서 작성 현황 ────────────────────────────────────── */
.rs-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
.rs-synth__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.6rem;
}
.rs-synth__summary {
  margin: 0;
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.rs-synth__actions:empty {
  display: none;
}
.rs-synth__bar {
  position: relative;
  height: 0.4rem;
  overflow: hidden;
  background: var(--skx-border-c1);
  border-radius: var(--skx-radius-pill);
}
.rs-synth__fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 0;
  overflow: hidden;
  background: var(--skx-primary);
  border-radius: inherit;
  /* 폭은 1초마다 다시 잰다 — 같은 1초로 이어 붙여 멈춤 없이 늘어나 보이게 한다 */
  transition: width 1s linear;
}
.rs-synth__fill.is-running::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--skx-white) 45%, transparent), transparent);
  transform: translateX(-100%);
  animation: rs-sheen 1.8s ease-in-out infinite;
}
.rs-synth__list {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.rs-synth__item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.4rem 0.5rem;
  font-family: inherit;
  font-size: 0.65rem;
  color: var(--skx-ink);
  text-align: left;
  background: none;
  border: 1px solid transparent;
  border-radius: var(--skx-radius-sm);
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
button.rs-synth__item {
  cursor: pointer;
}
button.rs-synth__item:hover,
button.rs-synth__item:focus-visible,
.rs-synth__item.is-linked {
  background: var(--skx-border-c1);
  border-color: var(--skx-border-c2);
  outline: none;
}
.rs-synth__icon {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 1rem;
  height: 1rem;
  font-size: 0.55rem;
  font-weight: 700;
  line-height: 1;
  border-radius: 50%;
}
.rs-synth__item.is-done .rs-synth__icon {
  color: var(--skx-white);
  background: var(--skx-primary);
}
.rs-synth__item.is-running .rs-synth__icon {
  border: 2px solid var(--skx-border-c1);
  border-top-color: var(--skx-primary);
  animation: rs-spin 0.9s linear infinite;
}
.rs-synth__item.is-waiting .rs-synth__icon {
  color: var(--skx-gray-2);
  border: 1px dashed var(--skx-line);
}
.rs-synth__item.is-failed .rs-synth__icon {
  color: var(--skx-ink);
  border: 1px solid var(--skx-ink);
}
.rs-synth__icon.is-fresh {
  animation: rs-pop 0.9s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.rs-synth__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rs-synth__item.is-waiting .rs-synth__name {
  font-weight: 400;
  color: var(--skx-gray-2);
}
.rs-synth__state {
  flex-shrink: 0;
  font-size: 0.6rem;
  font-variant-numeric: tabular-nums;
  color: var(--skx-gray-1);
}
.rs-synth__item.is-running .rs-synth__state {
  font-weight: 700;
  color: var(--skx-primary);
}
@keyframes rs-sheen {
  to {
    transform: translateX(100%);
  }
}
@keyframes rs-spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes rs-pop {
  0% {
    transform: scale(0.3);
  }
  55% {
    transform: scale(1.35);
  }
  100% {
    transform: scale(1);
  }
}
@media (prefers-reduced-motion: reduce) {
  .rs-synth__fill,
  .rs-synth__item {
    transition: none;
  }
  .rs-synth__fill.is-running::after,
  .rs-synth__item.is-running .rs-synth__icon,
  .rs-synth__icon.is-fresh {
    animation: none;
  }
}
```

(줄임 동작 블록의 셀렉터는 끄려는 규칙과 명시도가 같게 쓴다. `.rs-synth__icon` 하나만 쓰면 `.rs-synth__item.is-running .rs-synth__icon` 에 져서 링이 계속 돈다.)

- [ ] **Step 8: 컴파일 확인**

```bash
cd frontend
npx nuxi typecheck 2>&1 | grep "error TS"
npm run build 2>&1 | tail -1
```
기대 출력:
- 첫 명령은 아무것도 출력하지 않는다. `[Vue] Resolve plugin path failed …` 줄은 기존 소음이고 grep 에 걸리지 않는다.
- 둘째 명령은 `└  ✨ Build complete!`.

화면 확인은 Task 7 에서 한다. 카드가 페이지에 끼워지는 것이 Task 7 이다.

- [ ] **Step 9: 커밋**

```bash
git add frontend/utils/synthCard.ts frontend/tests/unit/synthCard.test.ts frontend/composables/useNow.ts frontend/components/research/SynthProgressCard.vue frontend/assets/css/research.css
git commit -m "[Feat] round04b — 보고서 작성 현황 카드: 절 목록(완료 시간·작성 중 경과·대기·서술 받지 못함)과 1초마다 이어 늘어나는 진행 막대·남은 시간을 보이고, 방금 끝난 절은 체크가 튀어 오르며 스크린리더에 한 번 알리고, 항목 포인터·초점·클릭을 초안 강조·이동 신호로 내보낸다"
```

---

### Task 7: 보고서 초안 모드 (`ReportView` draft) · 페이지 배선

**계약 추가:**
- `frontend/components/research/ReportSectionBody.vue` (새 파일).
  - props `{ sec: ReportSection; evidence: Record<string, ReportEvidence> }`, emits `{ "open-pdf": [payload: OpenPdfPayload] }`.
  - 지금 `ReportView` 의 절 본문(도입·대표 논문·향후 과제)을 그대로 옮긴 부품이다. 최종본과 초안이 이 부품 하나로 그린다.
  - 템플릿 안에서 `sec: ReportSection | null` 을 좁히는 데 기대지 않으려고 컴포넌트로 뺐다(v-for 안 콜백에서는 좁혀지지 않을 수 있다).
- `frontend/utils/researchReport.ts` 에 `draftIntro(slots: readonly DraftSlot[], interrupted: boolean, stats?: CountersPayload): string` 을 더한다.
  - 초안의 서론 자리에 쓴다. 초안에는 `trail` 이 없고 끝난 절만 있어서 `reportIntro` 로 세면 하위질문 수가 틀린다.
  - 화면 전용 문장이다. 초안을 저장한 문서(Task 8 `docInputFromDraft`)는 spec §14-4 3번대로 `reportIntro` 를 쓴다("조립 때 맞춘 것" 4번).

**선행:** Task 4 (`SynthView`·`SynthSectionView` 확장), Task 5 (`draftSlots`·`draftReport`·`synthEta`·`DraftSlot`·`DraftSlotStatus`·`SynthEta`), Task 6.

**동작 (spec §14-3, §7-4):**
- **종합 중:** 본문 카드 자리에 `SynthProgressCard` 를 둔다. 끝난 절이 하나라도 있으면 보고서 블록에 `ReportView` 초안을 둔다.
  - 배치 A 에서는 카드 아래, 배치 B 에서는 진행 패널 다음(`order: 3`)이다.
  - 모든 절은 제자리를 잡아 둔다. 끝난 절은 최종본과 같은 부품으로 그리고, 쓰는 중인 절은 움직이는 회색 줄, 대기 절은 "작성 대기"다.
  - 절 본문은 나타날 때 0.45초 동안 서서히 떠오른다. **자동 스크롤은 없다.**
- **카드 항목을 누르면:** `#rs-sec-N` 으로 `scrollIntoView` 한다(줄임 동작이면 `auto`, 아니면 `smooth`). 절에 초점을 옮기고(`preventScroll`) 1.6초 강조한다.
  - 포인터나 초점을 올리면 초안의 그 절 테두리를 함께 강조한다(`highlightIdx = hoverIdx ?? flashIdx`).
  - 종합이 끝나 카드가 사라지면 올려 둔 강조를 푼다.
- **실패·취소이고 초안이 있으면:** 오류·취소 카드 아래에 "완성되지 않은 초안" 배지를 단 초안을 둔다.
  - 쓰는 중이던 절과 대기 절은 회색 줄 없이 "작성을 마치지 못한 절입니다"로 그린다(더는 쓰고 있지 않다).
- **완료인데 보고서를 받는 중이거나 받기에 실패했고 초안이 있으면:** 초안 위에 작은 안내(불러오는 중 / 불러오지 못함 + [다시 불러오기])를 둔다. 초안이 없으면(옛 잡) 지금 카드 그대로다.
- 진행 패널(`ProgressPanel`)은 건드리지 않는다.
- `ReportView` 의 `actions` 슬롯과 카드의 `actions` 슬롯은 비워 둔다. [다운로드 ▾]·[초안 저장 ▾] 는 Task 10 이 끼운다.
- 시계(`useNow`)는 종합 중에만 돈다. 초안 모드 객체는 `computed` 로 만든다. 매초 도는 시계 때문에 페이지가 다시 그려져도 초안 `ReportView` 에 같은 참조가 가서 초안은 다시 그려지지 않는다.

**Files:**
- Test: `frontend/tests/unit/researchReport.test.ts` (import 줄 교체 + 끝에 `describe("draftIntro")` 추가)
- Modify: `frontend/utils/researchReport.ts` (import 줄, `reportIntro` 뒤에 `draftIntro`)
- Create: `frontend/components/research/ReportSectionBody.vue`
- Modify: `frontend/components/research/ReportView.vue` (전체 교체)
- Modify: `frontend/assets/css/research.css` (Task 6 이 덧붙인 줄임 동작 블록 뒤에 "보고서 초안" 절)
- Modify: `frontend/pages/research/[id].vue` (종합 카드 자리, 보고서 블록, import, `synthLine` 제거, 현황·초안 상태와 이동 함수)

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/tests/unit/researchReport.test.ts`

1) import 교체. 찾을 코드:

```ts
import type { ResearchReport } from "~/types/research";
import { hideOnPointerLeave, paperByline, rangeLabel, reportIntro, reportSlot, stepChunk } from "~/utils/researchReport";
```

바꿀 코드:

```ts
import type { ResearchReport } from "~/types/research";
import type { DraftSlot } from "~/utils/researchDraft";
import { draftIntro, hideOnPointerLeave, paperByline, rangeLabel, reportIntro, reportSlot, stepChunk } from "~/utils/researchReport";
```

2) 파일 끝에 덧붙인다.

```ts

describe("draftIntro", () => {
  const slots: DraftSlot[] = [
    { idx: 0, heading: "가", status: "done", durationMs: 30_000, startedAt: null, sectionIndex: 0 },
    { idx: 1, heading: "나", status: "failed", durationMs: 20_000, startedAt: null, sectionIndex: 1 },
    { idx: 2, heading: "다", status: "running", durationMs: null, startedAt: null, sectionIndex: null },
    { idx: 3, heading: "라", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null },
  ];

  it("전체 절 수는 슬롯으로, 쓴 절은 초안에 실린 절로 센다", () => {
    expect(draftIntro(slots, false)).toBe("4개 절 중 2개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다.");
  });

  it("라이브 카운터가 있으면 검토·채택 수를 덧붙인다", () => {
    expect(draftIntro(slots, false, { papers_reviewed: 38, evidence_adopted: 11, rechecks: 2 }))
      .toBe("4개 절 중 2개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다. 지금까지 논문 38편을 검토하고 11편을 근거로 삼았습니다.");
  });

  it("멈춘 초안은 완성되지 않았음과 한계가 빠졌음을 알린다", () => {
    expect(draftIntro(slots, true)).toBe("4개 절 중 2개를 쓰고 멈춘 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.");
  });
});
```

- [ ] **Step 2: 실행해 실패 확인**

```bash
cd frontend && npx vitest run tests/unit/researchReport.test.ts
```
기대 출력: `TypeError: (0 , draftIntro) is not a function` 가 3번 나오고, `Tests  3 failed | 15 passed (18)`.

- [ ] **Step 3: `draftIntro` 구현**

`frontend/utils/researchReport.ts`

1) import. 찾을 코드:

```ts
import type { EvidenceMeta, ReportRange, ResearchReport } from "../types/research";
import { pubYear, splitAuthors } from "./citations";
```

바꿀 코드:

```ts
import type { CountersPayload, EvidenceMeta, ReportRange, ResearchReport } from "../types/research";
import { pubYear, splitAuthors } from "./citations";
import type { DraftSlot } from "./researchDraft";
```

2) `reportIntro` 뒤. 찾을 코드:

```ts
  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
}
```

바꿀 코드:

```ts
  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
}

// 초안의 서론 자리. 초안에는 trail 이 없고 끝난 절만 있어 reportIntro 로 세면 하위질문 수가 틀린다 —
// 전체 절 수는 자리를 잡아 둔 슬롯 수로, 쓴 절은 초안에 실린 절로 센다
export function draftIntro(slots: readonly DraftSlot[], interrupted: boolean, stats?: CountersPayload): string {
  const done = slots.filter((s) => s.sectionIndex !== null).length;
  const head = interrupted
    ? `${slots.length}개 절 중 ${done}개를 쓰고 멈춘 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.`
    : `${slots.length}개 절 중 ${done}개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다.`;
  return stats
    ? `${head} 지금까지 논문 ${stats.papers_reviewed}편을 검토하고 ${stats.evidence_adopted}편을 근거로 삼았습니다.`
    : head;
}
```

- [ ] **Step 4: 통과 확인**

```bash
cd frontend && npx vitest run tests/unit/researchReport.test.ts
```
기대 출력: `Tests  18 passed (18)`.

- [ ] **Step 5: 절 본문 부품**

`frontend/components/research/ReportSectionBody.vue`. 지금 `ReportView.vue` 19~68줄의 절 본문을 그대로 옮긴다. `report.evidence` 는 `evidence`, `sec` 는 prop 이 된다.

```vue
<!-- frontend/components/research/ReportSectionBody.vue -->
<!-- 절 본문(도입·대표 논문·향후 과제). 최종본과 작성 중 초안이 같은 부품으로 그려야 두 화면의 글이 갈리지 않는다 -->
<template>
  <div class="rs-section__body">
    <p v-if="sec.intro" class="rs-section__intro">
      <template v-for="(part, pi) in splitCitations(sec.intro)" :key="pi">
        <template v-if="part.type === 'text'">{{ part.text }}</template>
        <CitationChip
          v-else
          :eid="part.eid"
          :evidence="evidence[part.eid]"
          :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
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
            :evidence="evidence[eid]"
            :chunks="citeChunks(sec, evidence[eid], eid)"
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
              :evidence="evidence[part.eid]"
              :chunks="citeChunks(sec, evidence[part.eid], part.eid)"
              @open-pdf="$emit('open-pdf', $event)"
            />
          </template>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EvidenceMeta, OpenPdfPayload, ReportEvidence, ReportPaper, ReportSection } from "~/types/research";
import { citeChunks, splitCitations } from "~/utils/citations";
import { paperByline } from "~/utils/researchReport";
import CitationChip from "./CitationChip.vue";

const props = defineProps<{ sec: ReportSection; evidence: Record<string, ReportEvidence> }>();
defineEmits<{ "open-pdf": [payload: OpenPdfPayload] }>();

function paperMeta(p: ReportPaper): EvidenceMeta | undefined {
  return props.evidence[p.evidence[0] ?? ""]?.meta;
}
</script>
```

- [ ] **Step 6: `ReportView.vue` 전체 교체**

교체 전은 HEAD(`a6fd98c`)의 104줄 파일이다. 달라지는 점:
- 절 루프(17~69줄)는 `rows` 순회 + `ReportSectionBody` 가 된다.
- `paperMeta`·`EvidenceMeta`·`ReportPaper`·`citations`·`paperByline`·`CitationChip` import 는 부품으로 옮긴다.
- 머리의 [링크 복사] 는 `rs-report__actions` 로 감싸고 `actions` 슬롯을 단다.
- 메타 줄은 범위·생성 시각이 없으면 그리지 않는다. 초안에는 둘 다 없어 빈 줄의 여백만 남기 때문이다.
- 한계 섹션은 `v-if="!draft"` 가 된다.
- 최종본은 `rows` 가 `sections` 를 그대로 옮긴 것이라 출력이 같다(절 요소에 `id="rs-sec-N"`·`is-done` 클래스만 늘어난다).

전체 내용:

```vue
<!-- frontend/components/research/ReportView.vue -->
<template>
  <article class="rs-card rs-report" :class="{ 'rs-report--draft': !!draft }">
    <header class="rs-report__head">
      <div>
        <p v-if="draft" class="rs-report__kicker">
          <span class="rs-badge rs-badge--draft" :class="{ 'rs-badge--live': !draft.interrupted }">
            {{ draft.interrupted ? "완성되지 않은 초안" : "작성 중" }}
          </span>
        </p>
        <h2 class="rs-report__question">{{ report.question }}</h2>
        <p v-if="range || generated" class="rs-report__meta">
          <span v-if="range">{{ range }}</span>
          <span v-if="generated">{{ generated }} 생성</span>
        </p>
      </div>
      <div class="rs-report__actions">
        <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="$emit('copy-link')">링크 복사</button>
        <slot name="actions" />
      </div>
    </header>

    <p class="rs-report__intro">{{ intro }}</p>

    <!-- 절 id 는 작성 현황 카드가 눌러 옮겨 오는 자리다. 초안은 초점도 받아 키보드로 옮긴 사람이 이어 읽는다 -->
    <section
      v-for="row in rows"
      :id="`rs-sec-${row.idx}`"
      :key="row.idx"
      class="rs-section"
      :class="[`is-${row.state}`, { 'is-linked': highlightIdx === row.idx }]"
      :tabindex="draft ? -1 : undefined"
    >
      <h3 class="rs-section__heading">{{ row.idx + 1 }}. {{ row.heading }}</h3>
      <ReportSectionBody v-if="row.sec" :sec="row.sec" :evidence="report.evidence" @open-pdf="$emit('open-pdf', $event)" />
      <p v-else-if="draft?.interrupted" class="rs-muted">작성을 마치지 못한 절입니다.</p>
      <template v-else-if="row.state === 'running'">
        <p class="rs-muted">이 절을 쓰는 중입니다</p>
        <div class="rs-skeleton" aria-hidden="true">
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
        </div>
      </template>
      <p v-else-if="row.state === 'failed'" class="rs-muted">이 절은 서술을 받지 못했습니다.</p>
      <p v-else class="rs-muted">작성 대기</p>
    </section>

    <section v-if="!draft" class="rs-limits" aria-labelledby="rs-limits-title">
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
import type { OpenPdfPayload, ReportSection, ResearchReport } from "~/types/research";
import type { DraftSlot, DraftSlotStatus } from "~/utils/researchDraft";
import { draftIntro, rangeLabel, reportIntro } from "~/utils/researchReport";
import ReportSectionBody from "./ReportSectionBody.vue";

interface SectionRow {
  idx: number;
  heading: string;
  state: DraftSlotStatus;
  sec: ReportSection | null;
}

const props = withDefaults(
  defineProps<{
    report: ResearchReport;
    generatedAt: string | null;
    draft?: { slots: DraftSlot[]; interrupted: boolean } | null;
    highlightIdx?: number | null;
  }>(),
  { draft: null, highlightIdx: null },
);
defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; "copy-link": [] }>();

const range = computed(() => rangeLabel(props.report.range));
const intro = computed(() =>
  props.draft ? draftIntro(props.draft.slots, props.draft.interrupted, props.report.stats) : reportIntro(props.report),
);
const generated = computed(() => {
  if (!props.generatedAt) return "";
  const d = new Date(props.generatedAt);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("ko-KR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
});

// 최종본은 절 순서 그대로, 초안은 아직 쓰지 않은 절까지 자리를 잡아 둔다 — 절이 끝나도 뒤 절이 밀리지 않는다
const rows = computed<SectionRow[]>(() => {
  const sections = props.report.sections;
  if (!props.draft) return sections.map((sec, si) => ({ idx: si, heading: sec.heading, state: "done", sec }));
  return props.draft.slots.map((slot) => ({
    idx: slot.idx,
    heading: slot.heading,
    state: slot.status,
    sec: slot.sectionIndex !== null ? (sections[slot.sectionIndex] ?? null) : null,
  }));
});
</script>
```

- [ ] **Step 7: 초안 CSS**

`frontend/assets/css/research.css`

찾을 코드 (Task 6 이 덧붙인 파일 끝 블록):

```css
@media (prefers-reduced-motion: reduce) {
  .rs-synth__fill,
  .rs-synth__item {
    transition: none;
  }
  .rs-synth__fill.is-running::after,
  .rs-synth__item.is-running .rs-synth__icon,
  .rs-synth__icon.is-fresh {
    animation: none;
  }
}
```

바꿀 코드:

```css
@media (prefers-reduced-motion: reduce) {
  .rs-synth__fill,
  .rs-synth__item {
    transition: none;
  }
  .rs-synth__fill.is-running::after,
  .rs-synth__item.is-running .rs-synth__icon,
  .rs-synth__icon.is-fresh {
    animation: none;
  }
}

/* ── 보고서 초안 ─────────────────────────────────────────── */
.rs-block--report {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.rs-report-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.8rem;
  font-size: 0.65rem;
  color: var(--skx-ink);
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
}
.rs-report-note p {
  flex: 1;
  min-width: 0;
  margin: 0;
}
.rs-spinner--small {
  width: 0.9rem;
  height: 0.9rem;
}
.rs-report__kicker {
  margin: 0 0 0.3rem;
}
.rs-report__actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}
.rs-badge--draft {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: var(--skx-primary);
  border-color: var(--skx-border-c2);
}
.rs-badge--live::before {
  content: "";
  width: 0.35rem;
  height: 0.35rem;
  background: var(--skx-primary);
  border-radius: 50%;
  animation: rs-blink 1.2s ease-in-out infinite;
}
/* 카드 목록에서 눌러 옮겨 오는 자리 — 화면 맨 위에 딱 붙지 않게 조금 띄우고, 강조는 바깥 테두리로 한다 */
.rs-section {
  scroll-margin-top: 1.2rem;
  border-radius: var(--skx-radius-sm);
  outline: 2px solid transparent;
  outline-offset: 0.4rem;
  transition: outline-color 0.2s ease;
}
.rs-section:focus {
  outline-color: transparent;
}
.rs-section.is-linked {
  outline-color: var(--skx-border-c2);
}
.rs-section.is-waiting .rs-section__heading {
  color: var(--skx-gray-2);
}
.rs-section__body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.rs-report--draft .rs-section__body {
  animation: rs-reveal 0.45s ease-out both;
}
.rs-skeleton {
  --rs-skeleton: color-mix(in srgb, var(--skx-line) 40%, var(--skx-white));
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.rs-skeleton__line {
  height: 0.55rem;
  background: linear-gradient(90deg, var(--rs-skeleton) 25%, var(--skx-white) 50%, var(--rs-skeleton) 75%);
  background-size: 200% 100%;
  border-radius: var(--skx-radius-pill);
  animation: rs-shimmer 1.6s linear infinite;
}
.rs-skeleton__line:nth-child(2) {
  width: 92%;
}
.rs-skeleton__line:nth-child(3) {
  width: 64%;
}
@keyframes rs-reveal {
  from {
    opacity: 0;
    transform: translateY(0.4rem);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes rs-shimmer {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}
@keyframes rs-blink {
  50% {
    opacity: 0.25;
  }
}
@media (prefers-reduced-motion: reduce) {
  .rs-section {
    transition: none;
  }
  .rs-badge--live::before,
  .rs-report--draft .rs-section__body,
  .rs-skeleton__line {
    animation: none;
  }
}
```

(`.rs-section__body` 는 기존 `.rs-section` 과 같은 `gap: 0.5rem` 이라 최종본의 절 간격은 바뀌지 않는다.)

- [ ] **Step 8: 페이지 배선 (`frontend/pages/research/[id].vue`)**

1) 종합 단계 본문 → 작성 현황 카드. 찾을 코드:

```vue
              <div v-else-if="phase === 'synthesizing'" class="rs-card rs-card--wait">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <p>{{ synthLine }}</p>
              </div>
```

바꿀 코드:

```vue
              <SynthProgressCard
                v-else-if="phase === 'synthesizing'"
                :slots="slots"
                :eta="eta"
                :highlight-idx="linkedIdx"
                @jump="jumpToSection"
                @hover="hoverIdx = $event"
              />
```

2) 보고서 블록: 초안과 받는 중·실패 안내. 찾을 코드:

```vue
            <section v-if="reportState" class="rs-block rs-block--report">
              <ReportView
                v-if="reportState === 'ready' && view.report"
                :report="view.report"
                :generated-at="view.finishedAt"
                @open-pdf="openPdf"
                @copy-link="copyLink"
              />
              <div v-else-if="reportState === 'failed'" class="rs-card rs-card--error">
```

바꿀 코드:

```vue
            <section v-if="reportState || draft" class="rs-block rs-block--report">
              <ReportView
                v-if="reportState === 'ready' && view.report"
                :report="view.report"
                :generated-at="view.finishedAt"
                @open-pdf="openPdf"
                @copy-link="copyLink"
              />
              <template v-else-if="draft">
                <!-- 완료 이벤트 뒤 최종본을 받는 동안·실패해 다시 시도하는 동안에도 읽던 초안을 치우지 않는다 -->
                <div v-if="reportState === 'failed'" class="rs-report-note" role="alert">
                  <p>최종 보고서를 불러오지 못했습니다. 잠시 뒤 자동으로 다시 시도합니다 — 아래는 작성 중에 받은 초안입니다.</p>
                  <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" :disabled="syncing" @click="resync">다시 불러오기</button>
                </div>
                <div v-else-if="reportState === 'loading'" class="rs-report-note" role="status">
                  <img src="/img/ico-spinner.svg" alt="" class="rs-spinner rs-spinner--small" />
                  <p>최종 보고서를 불러오는 중입니다 — 서론과 한계가 붙은 완성본으로 곧 바뀝니다.</p>
                </div>
                <ReportView
                  :report="draft.report"
                  :generated-at="null"
                  :draft="draftMode"
                  :highlight-idx="linkedIdx"
                  @open-pdf="openPdf"
                  @copy-link="copyLink"
                />
              </template>
              <div v-else-if="reportState === 'failed'" class="rs-card rs-card--error">
```

(그 아래 기존 `reportState === 'failed'` 카드와 불러오는 중 카드는 그대로 둔다. 초안이 없는 옛 잡은 지금처럼 그것을 본다.)

3) import. 찾을 코드:

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
import { safeLocalStorage } from "~/utils/browserId";
import { researchPhase, synthProgress } from "~/utils/researchEvents";
```

바꿀 코드:

```ts
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import PdfViewer from "~/components/PdfViewer.vue";
import PlanCard from "~/components/research/PlanCard.vue";
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ReportView from "~/components/research/ReportView.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
import SynthProgressCard from "~/components/research/SynthProgressCard.vue";
import { apiHeaders, apiUrl } from "~/composables/useApi";
import { useNow } from "~/composables/useNow";
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
import type { OpenPdfPayload } from "~/types/research";
import { safeLocalStorage } from "~/utils/browserId";
import { draftReport, draftSlots, synthEta, type SynthEta } from "~/utils/researchDraft";
import { researchPhase, type ResearchPhase } from "~/utils/researchEvents";
```

4) 쓰지 않게 된 `synthLine` 제거. `synthProgress` 는 `ProgressPanel` 이 계속 쓴다. 찾을 코드:

```ts
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
const synthLine = computed(() => {
  if (!view.value) return "";
  const p = synthProgress(view.value);
  return p.total ? `보고서 작성 중 ${p.current}/${p.total}` : "보고서 작성 중";
});
```

바꿀 코드:

```ts
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
```

5) 현황·초안 상태와 이동 함수. 배치 블록의 `onBeforeUnmount` 바로 뒤에 둔다. 찾을 코드:

```ts
onBeforeUnmount(() => {
  media?.removeEventListener("change", onMediaChange);
});
```

바꿀 코드:

```ts
onBeforeUnmount(() => {
  media?.removeEventListener("change", onMediaChange);
});

// ── 보고서 작성 현황·초안 ─────────────────────────────────
// 초안은 쓰는 동안·멈춘 뒤·완료 직후 최종본을 받기 전까지만 보인다 — 최종본이 오면 그것으로 바꾼다
const DRAFT_PHASES: readonly ResearchPhase[] = ["synthesizing", "failed", "canceled", "completed"];
const EMPTY_ETA: SynthEta = { done: 0, total: 0, runningIdx: null, runningElapsedMs: null, remainingMs: null };
// 절이 쌓이는 동안만 1초마다 시계를 읽는다 — 쓰는 중인 절의 경과·남은 시간·막대가 따라 움직인다
const now = useNow(computed(() => phase.value === "synthesizing"));
const slots = computed(() => (view.value ? draftSlots(view.value) : []));
const eta = computed<SynthEta>(() => (view.value ? synthEta(view.value, now.value) : EMPTY_ETA));
const draft = computed(() => {
  if (!view.value || !phase.value || !DRAFT_PHASES.includes(phase.value) || reportState.value === "ready") return null;
  return draftReport(view.value);
});
// 템플릿에서 객체를 만들면 1초마다 도는 시계 때문에 초안 전체가 매초 다시 그려진다
const draftMode = computed(() =>
  draft.value ? { slots: draft.value.slots, interrupted: phase.value === "failed" || phase.value === "canceled" } : null,
);

// 현황 카드 항목에 포인터·초점을 올린 절, 눌러서 옮겨 간 절을 초안에서 함께 강조한다
const FLASH_MS = 1600;
const hoverIdx = ref<number | null>(null);
const flashIdx = ref<number | null>(null);
const linkedIdx = computed(() => hoverIdx.value ?? flashIdx.value);
let flashTimer: ReturnType<typeof setTimeout> | null = null;

// 사용자가 누를 때만 옮긴다 — 절이 완성될 때마다 끌고 가면 초안을 읽던 자리를 잃는다
function jumpToSection(idx: number): void {
  const el = document.getElementById(`rs-sec-${idx}`);
  if (!el) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  // 키보드로 누른 사람이 그 절부터 이어 읽게 초점도 옮긴다(스크롤은 위에서 했다)
  el.focus({ preventScroll: true });
  flashIdx.value = idx;
  if (flashTimer) clearTimeout(flashTimer);
  flashTimer = setTimeout(() => {
    flashIdx.value = null;
  }, FLASH_MS);
}

// 종합이 끝나 카드가 사라지면 mouseleave 가 오지 않는다 — 올려 둔 강조가 초안에 남지 않게 푼다
watch(phase, (p) => {
  if (p !== "synthesizing") hoverIdx.value = null;
});

onBeforeUnmount(() => {
  if (flashTimer) clearTimeout(flashTimer);
});
```

- [ ] **Step 9: 전체 확인**

```bash
cd frontend
npm test
npx nuxi typecheck 2>&1 | grep "error TS"
npm run build 2>&1 | tail -1
```
기대 출력:
- `npm test`: 실패 0 (18파일 / 325 tests — `researchReport.test.ts` 18, `synthCard.test.ts` 18 포함).
- 타입검사: 출력 없음.
- 빌드: `└  ✨ Build complete!`.
- 확인용 grep 두 개:
  - `grep -n "synthLine\|synthProgress" "pages/research/[id].vue"` → 출력 없음.
  - `grep -rn "rs-sec-" components pages` → `ReportView.vue`(id)와 `[id].vue`(getElementById) 두 곳.

- [ ] **Step 10: 수동 확인 — 로컬에서 되는 것과 운영으로 넘기는 것**

(a) **로컬: 완성된 보고서가 전과 같은지(회귀).** 운영 게이트웨이로 GET 만 보내므로 데이터는 바뀌지 않는다.
- 서버에서 읽기 전용으로 잡 id 를 고른다.
  ```sql
  select id from research_jobs where status='completed' order by finished_at desc limit 3;
  select id from research_jobs where status in ('failed','canceled') order by created_at desc limit 3;
  ```
- 로컬 화면을 띄운다.
  ```bash
  cd frontend
  NUXT_DEV_API_TARGET=http://<운영 서버>:92/api npm run dev
  ```
- `http://localhost:3000/research/<완료 잡 id>` 에서 확인한다.
  - 절·도입·대표 논문·향후 과제·인용칩 팝오버·[원문 보기]·한계 섹션이 전과 같다.
  - DevTools 콘솔에서 `[...document.querySelectorAll('.rs-section')].map(s => s.id)` → `["rs-sec-0", "rs-sec-1", …]`.
  - `document.querySelector('.rs-badge--draft')` → `null`.
- 실패·취소된 잡(보강 전 워커가 만든 것)은 절 미리보기가 없다. 초안 없이 오류·취소 카드만 보여야 한다.

(b) **로컬에서 볼 수 없는 것 → 운영 확인 태스크(spec §14-6 "화면(운영, 배포 뒤 잡 1회)")로 넘긴다.**
- 이유 세 가지:
  - 작성 중 화면에는 종합 중인 잡이 있어야 한다.
  - 절 미리보기(`heading`·`started_at`·`duration_ms`·`section`)를 내는 워커(Task 1~3)는 배포 전이다.
  - `useResearchJob` 의 `view` 는 컴포넌트 안 `shallowRef` 라 브라우저 콘솔에서 뷰 상태를 주입할 수 없다.
- 운영에서 볼 항목:
  - 절이 하나씩 제자리에 나타나고(서서히 떠오름) 화면이 저절로 스크롤되지 않는다.
  - 막대가 1초마다 끊김 없이 늘어나고, 쓰는 중 절의 경과 시계와 "약 N분 N초 남음"이 갱신된다.
  - 방금 끝난 절의 체크가 튀어 오른다. 작성 중에 새로고침하면 이미 쓴 절이 복원되고, 이때는 튀어 오르지 않는다.
  - 카드 항목에 포인터·Tab 초점을 올리면 초안 절 테두리가 강조된다. 누르면 그 절로 부드럽게 옮겨 1.6초 강조되고 초점이 그 절로 간다.
  - DevTools → Rendering → `prefers-reduced-motion: reduce` 에뮬레이션에서 막대·링·반짝임·등장 애니메이션이 멈추고 이동이 즉시 된다.
  - DevTools → Accessibility 에서 카드의 `status` 영역 글이 "절 N 작성 완료: …"로 바뀐다.
  - 배치 B 에서 순서가 카드 → 진행 패널 → 초안이다.
  - 종합 중 취소하면 취소 카드 아래에 "완성되지 않은 초안"이 보이고, 남은 절은 "작성을 마치지 못한 절입니다"로 나온다.
  - 완료 직후 최종본을 받는 동안 초안 위에 "최종 보고서를 불러오는 중입니다" 안내가 보이고, 서론·한계가 붙은 최종본으로 바뀐다.
- 참고(계획 작성 때 확인한 것): 저장소 밖 사본에 계약대로 만든 임시 `researchDraft`·타입과 이 두 태스크의 코드를 넣고 확인했다.
  - `nuxi typecheck` 오류 0, `nuxt build` 성공.
  - 가짜 뷰 하네스 페이지에서 포인터·초점 강조, 클릭 이동과 초점 이동, 체크 튀어오름, 절 등장 애니메이션, `aria-live` 문구, interrupted 문구·배지·한계 섹션 숨김을 브라우저로 봤다.

- [ ] **Step 11: 커밋**

```bash
git add frontend/tests/unit/researchReport.test.ts frontend/utils/researchReport.ts frontend/components/research/ReportSectionBody.vue frontend/components/research/ReportView.vue frontend/assets/css/research.css "frontend/pages/research/[id].vue"
git commit -m "[Feat] round04b — 보고서 초안: 종합 중 다 쓴 절부터 최종본과 같은 절 부품으로 제자리에 보여 주고(쓰는 중 절은 움직이는 회색 줄, 대기 절은 작성 대기), 현황 카드 항목을 누르면 그 절로 부드럽게 옮겨 강조하며, 실패·취소 뒤와 완료 직후 최종본을 받는 동안에도 초안을 남긴다"
```

---

## 단계 3(이어서)·4 — 내보내기 (Task 8~10)

### 공통 전제 (Task 8~10)

**계약 추가:**
- `utils/reportDocument.ts`
  - `export function docRunText(run: DocRun): string` — 인용은 `[n]`, 글 조각은 그대로. Word·인쇄·테스트가 같은 규칙을 쓴다.
  - `export type ReportExportFormat = "docx" | "pdf"` — `ReportDownloadMenu` 의 `select` 인자 타입. 계약의 `"docx" | "pdf"` 와 같다.
- `utils/reportDocx.ts`
  - `export type DocxModule = typeof import("docx")`
  - `export function buildDocxDocument(docx: DocxModule, doc: ReportDoc): Document` — 계약의 "docx 모듈을 인자로 받는 순수 구성 함수".

**선행 태스크:**
- Task 8 은 Task 4(`types/research.ts` 의 `SynthView.headings·evidence`, `SynthSectionView` 확장)와 Task 5(`utils/researchDraft.ts` 의 `DraftReport`·`DraftSlot`) 뒤에 한다.
- Task 10 은 Task 6(`SynthProgressCard.vue` 의 `actions` 슬롯), Task 7(`ReportView.vue` 의 `actions` 슬롯·`draft` prop, 페이지의 작성 현황 카드·초안·`draft`·`draftMode`), Task 9(`reportDocx.ts`) 뒤에 한다.

**초안 문서의 서론(조립 때 정함):** 초안 문서의 서론은 spec §14-4 3번대로 `reportIntro` 로 만든다. 이때 하위질문 수는 끝난 절 수가 아니라 `view.subqs` 수다. 화면 초안(Task 7)은 진행을 알리는 `draftIntro` 를 쓴다 — "다 쓴 절부터 먼저 보여 드립니다"는 저장한 파일에 맞지 않고, 초안 문서는 제목("(초안 · N개 절 중 M개 작성)")과 한계 자리 안내로 초안임을 밝힌다. 완성본은 화면·문서 모두 `reportIntro` 라 spec 의 "화면과 같은 문장"을 지킨다.

**계획 작성 때 검증한 범위:** 저장소 밖 사본에서 확인했다.
- 태스크 코드를 그대로 넣어 돌린 결과:
  - `reportDocument.test.ts` 20 passed, `reportDocx.test.ts` 3 passed.
  - 두 소스와 테스트 모두 Nuxt 와 같은 엄격 옵션(`strict`·`noUncheckedIndexedAccess`·`verbatimModuleSyntax`)의 `tsc` 에서 오류 0.
- 앞 태스크를 계약 모양 대역(stub)으로 채운 사본 위에 Task 10 을 얹어 확인한 결과:
  - `npx nuxi typecheck` 오류 0.
  - `npm run build` 통과.
  - docx 는 별도 청크 1개(436KB)로 나뉘고, 그 청크를 부르는 것은 딥리서치 페이지 청크 하나뿐이다.
- 확인하지 못한 것:
  - 앞 태스크가 실제로 만든 페이지·컴포넌트 위에서의 타입검사. 특히 Task 10 의 템플릿 교체(조립 때 Task 7 코드에 맞춰 고쳤다)는 Task 10 Step 8·Task 11 의 `nuxi typecheck` 가 방어선이다.
  - 브라우저에서 메뉴를 누르고 인쇄해 보는 동작 확인. Task 10 Step 9 의 수동 확인이 방어선이다.

---

### Task 8: 보고서 문서 모델 (`utils/reportDocument.ts`)

**Files:**
- Create: `frontend/utils/reportDocument.ts`
- Test: `frontend/tests/unit/reportDocument.test.ts`(새 파일)

재사용하는 기존 함수:
- `utils/citations.ts`: `splitCitations`·`splitAuthors`·`pubYear`·`citeChunks`·`pdfPage`
- `utils/researchReport.ts`: `reportIntro`·`rangeLabel`·`paperByline`
- `utils/researchEvents.ts`: `verdictLabel`

기존 파일은 고치지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`frontend/tests/unit/reportDocument.test.ts`:

```ts
// frontend/tests/unit/reportDocument.test.ts
import { describe, expect, it } from "vitest";
import type {
  ReportChunk,
  ReportEvidence,
  ReportSection,
  ResearchReport,
  ResearchView,
  RoundView,
  SubqView,
} from "~/types/research";
import type { DraftReport } from "~/utils/researchDraft";
import {
  buildReportDocument,
  docInputFromDraft,
  docInputFromReport,
  docRunText,
  reportFileName,
  type DocBlock,
  type ReportDoc,
  type ReportDocInput,
} from "~/utils/reportDocument";
import { reportIntro } from "~/utils/researchReport";

// 한국 시각 2026-09-28 15:05
const NOW = new Date("2026-09-28T06:05:00Z");

function chunk(id: string, page: number, pageEnd = page): ReportChunk {
  return { chunk_id: id, text: `대목 ${id}`, page_start: page, page_end: pageEnd, score: 0.5 };
}

function ev(cntsId: string, meta: ReportEvidence["meta"] = {}, chunks: ReportChunk[] = []): ReportEvidence {
  return { cnts_id: cntsId, meta, chunks };
}

function section(over: Partial<ReportSection> = {}): ReportSection {
  return { heading: "절", intro: "", papers: [], future: [], evidence_chunks: {}, chunk_scores: {}, ...over };
}

function input(over: Partial<ReportDocInput> = {}): ReportDocInput {
  return {
    question: "국내 AI 규제 연구 동향",
    range: null,
    generatedAt: null,
    url: "",
    intro: "",
    sections: [],
    evidence: {},
    limitations: [],
    trail: [],
    draft: null,
    ...over,
  };
}

function lineOf(b: DocBlock): string {
  switch (b.type) {
    case "para":
      return b.runs.map(docRunText).join("");
    case "bullets":
      return b.items.map((runs) => runs.map(docRunText).join("")).join(" / ");
    default:
      return b.text;
  }
}

// 블록을 "종류: 글" 한 줄씩 — 문서의 뼈대를 한눈에 비교한다
function lines(doc: ReportDoc): string[] {
  return doc.blocks.map((b) => `${b.type}${b.type === "heading" ? b.level : ""}: ${lineOf(b)}`);
}

describe("docRunText", () => {
  it("글 조각은 그대로, 인용은 [번호] 로 쓴다", () => {
    expect(docRunText({ text: "효과가 있다" })).toBe("효과가 있다");
    expect(docRunText({ cite: 3 })).toBe("[3]");
  });
});

describe("buildReportDocument — 구성", () => {
  it("제목 → 메타 → 서론 → 절(도입·대표 논문·향후 과제) → 한계 → 부록 순으로 쌓는다", () => {
    const doc = buildReportDocument(
      input({
        generatedAt: "2026-09-27T23:30:00Z",
        range: { from: "2002", to: "2026", n_papers: 1234 },
        url: "http://nl.example/research/abc",
        intro: "하위질문 1개로 나눠 논문 3편을 검토하고 1편을 근거로 삼았다.",
        sections: [
          section({
            heading: "규제 논의의 흐름",
            intro: "논의가 늘었다 [E1].",
            papers: [
              { cnts_id: "C1", summary: "규제 샌드박스를 분석했다", evidence: ["E1"] },
              { cnts_id: "C2", summary: "", evidence: [] },
            ],
            future: [{ text: "국제 비교가 필요하다 [E1]", evidence: ["E1"] }],
          }),
        ],
        evidence: { E1: ev("C1", { title: "AI 규제", personal_author: "김철수; 이영희", pub_date: "2021" }) },
        limitations: ["근거가 1편뿐인 절이 있다."],
        trail: [
          { subquestion: "규제 논의의 흐름", queries: ["AI 규제", "AI 규제 샌드박스"], verdict: "sufficient", evidenceCount: 1 },
        ],
      }),
      NOW,
    );
    expect(lines(doc)).toEqual([
      "title: 국내 AI 규제 연구 동향",
      "meta: 생성 일시 2026년 9월 28일 08:30",
      "meta: 수록 범위 2002~2026 논문 1,234편 기준",
      "meta: 연구 주소 http://nl.example/research/abc",
      "para: 하위질문 1개로 나눠 논문 3편을 검토하고 1편을 근거로 삼았다.",
      "heading1: 1. 규제 논의의 흐름",
      "para: 논의가 늘었다 [1].",
      "heading2: 대표 논문",
      "bullets: 김철수 외 (2021) 「AI 규제」 — 규제 샌드박스를 분석했다 [1] / 저자 미상 — 요약을 받지 못했습니다.",
      "heading2: 향후 과제",
      "bullets: 국제 비교가 필요하다 [1]",
      "heading1: 이 보고서의 한계",
      "bullets: 근거가 1편뿐인 절이 있다.",
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 규제 논의의 흐름",
      "bullets: 검색어: ‘AI 규제’ → ‘AI 규제 샌드박스’ (재검색 1회) / 판정: 근거 충분 / 채택한 근거: 1편",
    ]);
    expect(doc.fileName).toBe("딥리서치_국내_AI_규제_연구_동향_20260928.docx");
  });

  it("생성 시각을 모르면 지금 시각을 쓰고, 범위·주소가 없으면 그 줄을 뺀다", () => {
    const doc = buildReportDocument(input({ generatedAt: "잘못된 값" }), NOW);
    expect(doc.blocks.filter((b) => b.type === "meta").map(lineOf)).toEqual(["생성 일시 2026년 9월 28일 15:05"]);
  });

  it("도입이 없는 절은 화면과 같은 안내를, 한계가 없으면 화면과 같은 문구를 흐리게 싣는다", () => {
    const doc = buildReportDocument(input({ sections: [section({ heading: "빈 절" })], limitations: [] }), NOW);
    expect(doc.blocks).toContainEqual({
      type: "para",
      runs: [{ text: "이 절은 도입 서술을 받지 못했습니다. 아래 논문 목록만 싣습니다." }],
      muted: true,
    });
    expect(doc.blocks).toContainEqual({
      type: "para",
      runs: [{ text: "자동 점검에서 보고할 한계가 발견되지 않았습니다." }],
      muted: true,
    });
  });

  it("부록은 하위질문마다 검색어 이력·판정·채택한 근거 수를 싣고, 모르는 칸은 뺀다", () => {
    const doc = buildReportDocument(
      input({
        trail: [
          { subquestion: "가", queries: ["가"], verdict: "insufficient", evidenceCount: 0 },
          { subquestion: "나", queries: [], verdict: null, evidenceCount: null },
        ],
      }),
      NOW,
    );
    const all = lines(doc);
    expect(all.slice(all.indexOf("heading1: 부록: 탐색 경로"))).toEqual([
      "heading1: 부록: 탐색 경로",
      "heading2: 1. 가",
      "bullets: 검색어: ‘가’ / 판정: 근거 부족 / 채택한 근거: 0편",
      "heading2: 2. 나",
    ]);
  });

  it("탐색 경로가 없으면 부록을 싣지 않는다", () => {
    const doc = buildReportDocument(input(), NOW);
    expect(lines(doc)).not.toContain("heading1: 부록: 탐색 경로");
  });
});

describe("buildReportDocument — 인용 번호", () => {
  const evidence = { E1: ev("C1"), E2: ev("C2"), E3: ev("C3"), E4: ev("C4"), E5: ev("C5"), E9: ev("C9") };
  const secA = section({
    heading: "가",
    intro: "도입 [E3] 그리고 [E1].",
    papers: [{ cnts_id: "C2", summary: "요약", evidence: ["E2"] }],
    future: [{ text: "과제 [E4]", evidence: ["E4"] }],
  });
  const secB = section({ heading: "나", intro: "다시 [E1], 새로 [E5]" });
  const doc = buildReportDocument(input({ sections: [secA, secB], evidence }), NOW);

  it("절 순서 → 도입 → 대표 논문 → 향후 과제 순으로, 처음 나온 근거부터 번호를 매긴다", () => {
    expect(doc.references.map((r) => [r.n, r.eid])).toEqual([
      [1, "E3"],
      [2, "E1"],
      [3, "E2"],
      [4, "E4"],
      [5, "E5"],
    ]);
  });

  it("같은 근거는 어디서 나와도 같은 번호다", () => {
    const paras = doc.blocks.filter((b) => b.type === "para").map(lineOf);
    expect(paras).toContain("도입 [1] 그리고 [2].");
    expect(paras).toContain("다시 [2], 새로 [5]");
  });

  it("인용하지 않은 근거는 참고문헌에 싣지 않는다", () => {
    expect(doc.references.some((r) => r.eid === "E9")).toBe(false);
  });
});

describe("buildReportDocument — 참고문헌", () => {
  it("저자, 연도, 제목, 학술지·권호, 인용 쪽을 한 줄로 쓴다", () => {
    const e1 = ev(
      "C1",
      { title: "AI 윤리 교육", personal_author: "김철수; 이영희", pub_date: "2019-03", series_title: "교육학연구", vol_issue: "57(3)" },
      [chunk("c1", 11, 12), chunk("c2", 19)],
    );
    const doc = buildReportDocument(input({ sections: [section({ intro: "[E1]" })], evidence: { E1: e1 } }), NOW);
    expect(doc.references).toEqual([
      { n: 1, eid: "E1", text: "김철수, 이영희 (2019). AI 윤리 교육. 교육학연구, 57(3). 인용 쪽: 12–13, 20" },
    ]);
  });

  it("메타가 빠진 칸은 생략하고, 근거를 찾을 수 없으면 그렇다고 쓴다", () => {
    const doc = buildReportDocument(
      input({
        sections: [section({ intro: "[E1][E2][E3][E4][E7]" })],
        evidence: {
          E1: ev("C1", { title: "제목만" }),
          E2: ev("C2", { personal_author: "김철수", title: "물음표로 끝나는 제목?" }),
          E3: ev("C3", { pub_date: "2021", series_title: "정책연구" }),
          E4: ev("C4"),
        },
      }),
      NOW,
    );
    expect(doc.references.map((r) => r.text)).toEqual([
      "제목만.",
      "김철수. 물음표로 끝나는 제목?",
      "(2021). 정책연구.",
      "서지 정보 없음 (C4).",
      "근거 정보를 찾을 수 없습니다",
    ]);
  });

  it("인용 쪽은 인용한 절들이 쓴 대목의 쪽을 1부터 세어 정렬·중복 제거하고, 쪽 정보가 없으면 칸을 뺀다", () => {
    const e1 = ev("C1", { title: "가" }, [chunk("a", 19), chunk("b", 11), chunk("c", 12), chunk("z", 30), chunk("zero", 0)]);
    const e2 = ev("C2", { title: "나" }, [chunk("p", 0)]);
    const secA = section({ intro: "[E1]", evidence_chunks: { E1: ["a", "b", "zero"] } });
    const secB = section({
      papers: [{ cnts_id: "C1", summary: "요약", evidence: ["E1"] }],
      evidence_chunks: { E1: ["c", "a"] },
    });
    const secC = section({ future: [{ text: "과제 [E2]", evidence: ["E2"] }] });
    const doc = buildReportDocument(input({ sections: [secA, secB, secC], evidence: { E1: e1, E2: e2 } }), NOW);
    // z(31쪽)는 어느 절도 인용하지 않았고, 0 은 첫 쪽과 쪽 정보 없음이 겹쳐 뺀다
    expect(doc.references.map((r) => r.text)).toEqual(["가. 인용 쪽: 12–13, 20", "나."]);
  });
});

describe("buildReportDocument — 초안", () => {
  it("제목·파일 이름에 초안임을 밝히고 한계 대신 안내 문구를 싣는다", () => {
    const doc = buildReportDocument(input({ draft: { done: 2, total: 5 }, limitations: null }), NOW);
    expect(doc.blocks[0]).toEqual({ type: "title", text: "국내 AI 규제 연구 동향 (초안 · 5개 절 중 2개 작성)" });
    const all = lines(doc);
    expect(all[all.indexOf("heading1: 이 보고서의 한계") + 1]).toBe(
      "para: 작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.",
    );
    expect(doc.fileName).toBe("딥리서치_국내_AI_규제_연구_동향_20260928_초안.docx");
  });
});

describe("docInputFromReport", () => {
  it("서론은 화면과 같은 reportIntro 이고, 탐색 경로를 부록 항목으로 옮긴다", () => {
    const report: ResearchReport = {
      question: "q",
      range: { from: "2002", to: "2026", n_papers: 10 },
      sections: [section()],
      evidence: {},
      trail: [
        { subquestion: "가", queries: ["가", "가2"], evidence_count: 2, verdict: "sufficient", note: "", parse_failed: false, failed: false, capped: 0 },
        { subquestion: "나", queries: ["나"], evidence_count: 0, verdict: "pending", note: "", parse_failed: false, failed: true, capped: 0 },
      ],
      limitations: ["한계"],
      stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 1 },
    };
    const got = docInputFromReport(report, { generatedAt: "2026-09-28T06:05:00Z", url: "http://x/research/1" });
    expect(got.intro).toBe(reportIntro(report));
    expect(got.intro).toBe("하위질문 2개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
    // 오류로 끝난 하위질문은 판정을 싣지 않는다
    expect(got.trail).toEqual([
      { subquestion: "가", queries: ["가", "가2"], verdict: "sufficient", evidenceCount: 2 },
      { subquestion: "나", queries: ["나"], verdict: null, evidenceCount: 0 },
    ]);
    expect(got).toMatchObject({
      question: "q",
      range: { from: "2002", to: "2026", n_papers: 10 },
      generatedAt: "2026-09-28T06:05:00Z",
      url: "http://x/research/1",
      limitations: ["한계"],
      draft: null,
    });
  });
});

function round(n: number, query: string): RoundView {
  return { round: n, query, foundChunks: 3, newPapers: 1, verdict: null, note: "", nextQuery: null };
}

function subq(idx: number, over: Partial<SubqView> = {}): SubqView {
  return {
    idx,
    title: `하위질문 ${idx + 1}`,
    seq: idx + 2,
    status: "done",
    rounds: [],
    verdict: "sufficient",
    note: "",
    adopted: 1,
    parseFailed: false,
    error: null,
    ...over,
  };
}

function view(subqs: SubqView[]): ResearchView {
  return {
    jobId: "job-1",
    question: "초안 질문",
    status: "running",
    stage: "explored",
    plan: subqs.map((s) => s.title),
    params: {},
    report: null,
    lastError: null,
    createdAt: null,
    startedAt: null,
    finishedAt: null,
    steps: [],
    subqs,
    counters: { papersReviewed: 38, evidenceAdopted: 11, rechecks: 1 },
    highlight: null,
    synth: { seq: 9, status: "running", total: 3, sections: [], headings: [], evidence: {} },
    source: "rounds",
  };
}

describe("docInputFromDraft", () => {
  const draft: DraftReport = {
    report: {
      question: "초안 질문",
      range: null,
      sections: [section({ heading: "하위질문 1", intro: "초안 도입 [E1]" })],
      evidence: { E1: ev("C1", { title: "가" }) },
      trail: [],
      limitations: [],
      stats: { papers_reviewed: 38, evidence_adopted: 11, rechecks: 1 },
    },
    slots: [
      { idx: 0, heading: "하위질문 1", status: "done", durationMs: 38000, startedAt: null, sectionIndex: 0 },
      { idx: 1, heading: "하위질문 2", status: "running", durationMs: null, startedAt: "2026-09-28T06:04:50Z", sectionIndex: null },
      { idx: 2, heading: "하위질문 3", status: "waiting", durationMs: null, startedAt: null, sectionIndex: null },
    ],
    done: 1,
    total: 3,
  };
  const v = view([
    subq(0, { rounds: [round(1, "가"), round(2, "가 재검색")] }),
    subq(1, { status: "failed", verdict: null, adopted: null }),
    subq(2),
  ]);

  it("부록은 화면의 탐색 타임라인에서, 서론의 하위질문 수는 끝난 절 수가 아니라 탐색한 하위질문 수로 쓴다", () => {
    const got = docInputFromDraft(draft, v, "http://x/research/job-1");
    expect(got.intro).toBe("하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다.");
    expect(got.trail).toEqual([
      { subquestion: "하위질문 1", queries: ["가", "가 재검색"], verdict: "sufficient", evidenceCount: 1 },
      { subquestion: "하위질문 2", queries: [], verdict: null, evidenceCount: 0 },
      { subquestion: "하위질문 3", queries: [], verdict: "sufficient", evidenceCount: 1 },
    ]);
    expect(got).toMatchObject({
      question: "초안 질문",
      url: "http://x/research/job-1",
      generatedAt: null,
      limitations: null,
      draft: { done: 1, total: 3 },
    });
  });

  it("초안 문서는 제목·파일 이름에 초안임을 밝힌다", () => {
    const doc = buildReportDocument(docInputFromDraft(draft, v, ""), NOW);
    expect(doc.blocks[0]).toEqual({ type: "title", text: "초안 질문 (초안 · 3개 절 중 1개 작성)" });
    expect(doc.fileName).toBe("딥리서치_초안_질문_20260928_초안.docx");
  });
});

describe("reportFileName", () => {
  it("파일 이름에 못 쓰는 글자와 제어문자는 빼고 공백은 _ 로 바꾼다", () => {
    expect(reportFileName('AI 규제: "무엇이" 바뀌었나?', NOW, false)).toBe("딥리서치_AI_규제_무엇이_바뀌었나_20260928.docx");
    expect(reportFileName("a\\b/c*d<e>f|g\u0001h", NOW, false)).toBe("딥리서치_abcdefgh_20260928.docx");
  });

  it("질문은 앞 20자만 쓰고, 잘린 끝에 남은 _ 는 뗀다", () => {
    expect(reportFileName("국내 인공지능 규제 연구 동향은 지난 10년간 어떻게 변해 왔는가", NOW, false)).toBe(
      "딥리서치_국내_인공지능_규제_연구_동향은_지난_20260928.docx",
    );
    expect(reportFileName("가나다라마바사아자차카타파하가나다라마 바사", NOW, false)).toBe(
      "딥리서치_가나다라마바사아자차카타파하가나다라마_20260928.docx",
    );
  });

  it("초안은 _초안 을 붙이고, 날짜는 한국 시각으로 적는다", () => {
    expect(reportFileName("질문", new Date("2026-09-28T15:30:00Z"), true)).toBe("딥리서치_질문_20260929_초안.docx");
  });

  it("쓸 글자가 남지 않으면 보고서 로 대신한다", () => {
    expect(reportFileName(' ?*" ', NOW, false)).toBe("딥리서치_보고서_20260928.docx");
  });
});
```

- [ ] **Step 2: 실행해 실패를 확인한다**

```bash
cd frontend && npx vitest run tests/unit/reportDocument.test.ts
```

기대 출력(모듈이 없어 수집 단계에서 실패):

```
 FAIL  tests/unit/reportDocument.test.ts [ tests/unit/reportDocument.test.ts ]
Error: Cannot find module '~/utils/reportDocument' imported from '.../frontend/tests/unit/reportDocument.test.ts'.
 Test Files  1 failed (1)
      Tests  no tests
```

- [ ] **Step 3: 구현한다**

`frontend/utils/reportDocument.ts`:

```ts
// frontend/utils/reportDocument.ts
import type {
  ReportEvidence,
  ReportPaper,
  ReportRange,
  ReportSection,
  ResearchReport,
  ResearchView,
  SubqView,
  TrailItem,
  Verdict,
} from "../types/research";
import { citeChunks, pdfPage, pubYear, splitAuthors, splitCitations } from "./citations";
import type { DraftReport } from "./researchDraft";
import { verdictLabel } from "./researchEvents";
import { paperByline, rangeLabel, reportIntro } from "./researchReport";

// Word·PDF 가 같은 모델에서 그려진다 — 인용 번호·참고문헌·부록이 두 형식에서 어긋나지 않게

export type ReportExportFormat = "docx" | "pdf";

export interface DocTrailItem {
  subquestion: string;
  queries: string[];
  verdict: Verdict | null;
  evidenceCount: number | null;
}

export interface ReportDocInput {
  question: string;
  range: Partial<ReportRange> | null;
  generatedAt: string | null;
  url: string;
  intro: string;
  sections: ReportSection[];
  evidence: Record<string, ReportEvidence>;
  limitations: string[] | null;
  trail: DocTrailItem[];
  draft: { done: number; total: number } | null;
}

export type DocRun = { text: string } | { cite: number };

export type DocBlock =
  | { type: "title"; text: string }
  | { type: "meta"; text: string }
  | { type: "heading"; level: 1 | 2; text: string }
  | { type: "para"; runs: DocRun[]; muted?: boolean }
  | { type: "bullets"; items: DocRun[][] };

export interface DocReference {
  n: number;
  eid: string;
  text: string;
}

export interface ReportDoc {
  fileName: string;
  blocks: DocBlock[];
  references: DocReference[];
}

// 화면(ReportView)과 같은 문구 — 내려받은 문서가 화면과 다른 말을 하지 않게
const INTROLESS = "이 절은 도입 서술을 받지 못했습니다. 아래 논문 목록만 싣습니다.";
const NO_SUMMARY = "요약을 받지 못했습니다.";
const NO_LIMITS = "자동 점검에서 보고할 한계가 발견되지 않았습니다.";
const DRAFT_LIMITS = "작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.";
const MISSING_EVIDENCE = "근거 정보를 찾을 수 없습니다";

// 사용자는 한국에 있다 — 문서의 날짜를 브라우저·테스트 기계의 시간대와 무관하게 한국 시각으로 적는다
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
// Windows·macOS 파일 이름에 못 쓰는 글자와 제어문자
const FILE_FORBIDDEN = /[\\/:*?"<>|\u0000-\u001f\u007f]/g;
const FILE_HEAD_CHARS = 20;

export function docRunText(run: DocRun): string {
  return "text" in run ? run.text : `[${run.cite}]`;
}

export function reportFileName(question: string, date: Date, draft: boolean): string {
  const cleaned = question
    .trim()
    .replace(/\s+/g, "_")
    .replace(FILE_FORBIDDEN, "")
    .replace(/_+/g, "_")
    .replace(/^_+/, "");
  // 코드 포인트 단위로 자른다 — 서로게이트 쌍 한가운데서 끊으면 깨진 글자가 남는다
  const head = Array.from(cleaned).slice(0, FILE_HEAD_CHARS).join("").replace(/[_.]+$/, "");
  return `딥리서치_${head || "보고서"}_${kstYmd(date)}${draft ? "_초안" : ""}.docx`;
}

export function buildReportDocument(input: ReportDocInput, now: Date): ReportDoc {
  const numbers = new Map<string, number>();
  const citedIn = new Map<string, ReportSection[]>();

  // 번호는 문서에 처음 나온 순서다 — 블록을 위에서 아래로 만드는 순서가 곧 읽는 순서라 여기서 매긴다
  function cite(eid: string, sec: ReportSection): DocRun {
    const n = numbers.get(eid) ?? numbers.size + 1;
    numbers.set(eid, n);
    const secs = citedIn.get(eid) ?? [];
    if (!secs.includes(sec)) secs.push(sec);
    citedIn.set(eid, secs);
    return { cite: n };
  }

  function runs(text: string, sec: ReportSection): DocRun[] {
    return splitCitations(text).map((p) => (p.type === "text" ? { text: p.text } : cite(p.eid, sec)));
  }

  const blocks: DocBlock[] = [{ type: "title", text: docTitle(input) }, ...metaBlocks(input, now)];
  if (input.intro) blocks.push({ type: "para", runs: [{ text: input.intro }] });

  input.sections.forEach((sec, si) => {
    blocks.push({ type: "heading", level: 1, text: `${si + 1}. ${sec.heading}` });
    blocks.push(
      sec.intro
        ? { type: "para", runs: runs(sec.intro, sec) }
        : { type: "para", runs: [{ text: INTROLESS }], muted: true },
    );
    if (sec.papers.length) {
      blocks.push({ type: "heading", level: 2, text: "대표 논문" });
      blocks.push({
        type: "bullets",
        items: sec.papers.map((p) => [
          { text: paperLine(p, input.evidence) + (p.evidence.length ? " " : "") },
          ...p.evidence.map((eid) => cite(eid, sec)),
        ]),
      });
    }
    if (sec.future.length) {
      blocks.push({ type: "heading", level: 2, text: "향후 과제" });
      blocks.push({ type: "bullets", items: sec.future.map((f) => runs(f.text, sec)) });
    }
  });

  blocks.push(...limitBlocks(input), ...trailBlocks(input.trail));

  const references = [...numbers].map(([eid, n]) => ({
    n,
    eid,
    text: referenceText(input.evidence[eid], citedIn.get(eid) ?? [], eid),
  }));
  return { fileName: reportFileName(input.question, now, input.draft !== null), blocks, references };
}

export function docInputFromReport(
  report: ResearchReport,
  opts: { generatedAt: string | null; url: string },
): ReportDocInput {
  return {
    question: report.question,
    range: report.range,
    generatedAt: opts.generatedAt,
    url: opts.url,
    intro: reportIntro(report),
    sections: report.sections,
    evidence: report.evidence,
    limitations: report.limitations,
    trail: report.trail.map(docTrailItem),
    draft: null,
  };
}

export function docInputFromDraft(draft: DraftReport, view: ResearchView, url: string): ReportDocInput {
  // 초안에는 trail 이 없다(종합이 끝나야 생긴다). 탐색은 이미 끝났으니 화면의 탐색 타임라인이 같은 내용이다.
  // reportIntro 는 하위질문 수를 trail 로 세므로, 끝난 절 수로 세지 않게 채워 넘긴다
  const trail = view.subqs.map(trailFromSubq);
  return {
    question: draft.report.question,
    range: draft.report.range,
    generatedAt: null,
    url,
    intro: reportIntro({ ...draft.report, trail }),
    sections: draft.report.sections,
    evidence: draft.report.evidence,
    limitations: null,
    trail: trail.map(docTrailItem),
    draft: { done: draft.done, total: draft.total },
  };
}

function docTitle(input: ReportDocInput): string {
  if (!input.draft) return input.question;
  return `${input.question} (초안 · ${input.draft.total}개 절 중 ${input.draft.done}개 작성)`;
}

function metaBlocks(input: ReportDocInput, now: Date): DocBlock[] {
  const parsed = input.generatedAt ? new Date(input.generatedAt) : null;
  const when = parsed && !Number.isNaN(parsed.getTime()) ? parsed : now;
  const range = rangeLabel(input.range);
  return [
    `생성 일시 ${kstDateTime(when)}`,
    range ? `수록 범위 ${range}` : "",
    input.url ? `연구 주소 ${input.url}` : "",
  ]
    .filter(Boolean)
    .map((text): DocBlock => ({ type: "meta", text }));
}

function paperLine(p: ReportPaper, evidence: Record<string, ReportEvidence>): string {
  const meta = evidence[p.evidence[0] ?? ""]?.meta;
  const title = meta?.title?.trim();
  const who = paperByline(meta);
  return `${title ? `${who} 「${title}」` : who} — ${p.summary || NO_SUMMARY}`;
}

function limitBlocks(input: ReportDocInput): DocBlock[] {
  const head: DocBlock = { type: "heading", level: 1, text: "이 보고서의 한계" };
  if (input.draft) return [head, { type: "para", runs: [{ text: DRAFT_LIMITS }], muted: true }];
  const lines = input.limitations ?? [];
  if (!lines.length) return [head, { type: "para", runs: [{ text: NO_LIMITS }], muted: true }];
  return [head, { type: "bullets", items: lines.map((line) => [{ text: line }]) }];
}

function trailBlocks(trail: DocTrailItem[]): DocBlock[] {
  if (!trail.length) return [];
  const out: DocBlock[] = [{ type: "heading", level: 1, text: "부록: 탐색 경로" }];
  trail.forEach((t, i) => {
    out.push({ type: "heading", level: 2, text: `${i + 1}. ${t.subquestion}` });
    const items: DocRun[][] = [];
    if (t.queries.length) items.push([{ text: `검색어: ${queryPath(t.queries)}` }]);
    if (t.verdict) items.push([{ text: `판정: ${verdictLabel(t.verdict)}` }]);
    if (t.evidenceCount !== null) items.push([{ text: `채택한 근거: ${t.evidenceCount}편` }]);
    if (items.length) out.push({ type: "bullets", items });
  });
  return out;
}

// 재검색은 근거가 부족하다고 판정했을 때만 일어난다 — 검색어가 바뀐 흐름이 곧 자기점검의 기록이다
function queryPath(queries: string[]): string {
  const path = queries.map((q) => `‘${q}’`).join(" → ");
  return queries.length > 1 ? `${path} (재검색 ${queries.length - 1}회)` : path;
}

function docTrailItem(t: TrailItem): DocTrailItem {
  // 오류로 끝난 하위질문의 판정은 점검을 마친 결과가 아니다
  return {
    subquestion: t.subquestion,
    queries: t.queries,
    verdict: t.failed ? null : t.verdict,
    evidenceCount: t.evidence_count,
  };
}

function trailFromSubq(sq: SubqView): TrailItem {
  return {
    subquestion: sq.title,
    queries: sq.rounds.map((r) => r.query).filter(Boolean),
    evidence_count: sq.adopted ?? 0,
    verdict: sq.verdict ?? "pending",
    note: sq.note,
    parse_failed: sq.parseFailed,
    failed: sq.status === "failed",
    capped: 0,
  };
}

function referenceText(ev: ReportEvidence | undefined, secs: ReportSection[], eid: string): string {
  if (!ev) return MISSING_EVIDENCE;
  const m = ev.meta;
  const authors = splitAuthors(m.personal_author).join(", ");
  const year = pubYear(m.pub_date);
  const title = m.title?.trim() ?? "";
  const journal = [m.series_title, m.vol_issue].map((s) => s?.trim() ?? "").filter(Boolean).join(", ");
  const parts: string[] = [];
  if (authors && year) parts.push(`${authors} (${year}).`);
  else if (authors) parts.push(sentence(authors));
  else if (year) parts.push(`(${year}).`);
  if (title) parts.push(sentence(title));
  if (journal) parts.push(sentence(journal));
  if (!parts.length) parts.push(`서지 정보 없음 (${ev.cnts_id}).`);
  const pages = citedPages(secs, ev, eid);
  if (pages) parts.push(`인용 쪽: ${pages}`);
  return parts.join(" ");
}

function sentence(s: string): string {
  return /[.?!]$/.test(s) ? s : `${s}.`;
}

// 칩 팝오버와 같은 대목(citeChunks)·같은 쪽 규칙(pdfPage — 0-based 저장값 + 1, 0 은 쪽 정보 없음)을 쓴다.
// 겹치거나 맞붙은 쪽은 한 범위로 합친다 — 같은 대목을 두 절이 인용해도 한 번만 적힌다
function citedPages(secs: ReportSection[], ev: ReportEvidence, eid: string): string {
  const ranges: [number, number][] = [];
  for (const sec of secs) {
    for (const c of citeChunks(sec, ev, eid)) {
      const start = pdfPage(c);
      if (start === undefined) continue;
      ranges.push([start, Math.max(start, c.page_end + 1)]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const merged: [number, number][] = [];
  for (const [s, e] of ranges) {
    const last = merged[merged.length - 1];
    if (last && s <= last[1] + 1) last[1] = Math.max(last[1], e);
    else merged.push([s, e]);
  }
  return merged.map(([s, e]) => (e > s ? `${s}–${e}` : `${s}`)).join(", ");
}

function kstParts(date: Date): { y: number; m: number; d: number; hh: number; mm: number } {
  const k = new Date(date.getTime() + KST_OFFSET_MS);
  return { y: k.getUTCFullYear(), m: k.getUTCMonth() + 1, d: k.getUTCDate(), hh: k.getUTCHours(), mm: k.getUTCMinutes() };
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function kstDateTime(date: Date): string {
  const p = kstParts(date);
  return `${p.y}년 ${p.m}월 ${p.d}일 ${pad2(p.hh)}:${pad2(p.mm)}`;
}

function kstYmd(date: Date): string {
  const p = kstParts(date);
  return `${p.y}${pad2(p.m)}${pad2(p.d)}`;
}
```

- [ ] **Step 4: 통과를 확인한다**

```bash
cd frontend && npx vitest run tests/unit/reportDocument.test.ts
```

기대 출력: `Test Files  1 passed (1)` · `Tests  20 passed (20)`

- [ ] **Step 5: 타입검사**

```bash
cd frontend && npx nuxi typecheck 2>&1 | grep "error TS"
```

기대 출력: 없음. 테스트 파일도 검사 대상이다(`.nuxt/tsconfig.app.json` 의 include 가 `../**/*`). `ResearchView` 픽스처의 `synth.headings·evidence` 는 Task 4 의 타입 변경을 전제로 한다.

- [ ] **Step 6: 커밋**

```bash
git add frontend/utils/reportDocument.ts frontend/tests/unit/reportDocument.test.ts
git commit -m "[Feat] round04b — 보고서 문서 모델: 완성본·초안을 제목·메타·서론·절·한계·부록 블록과 참고문헌으로 만들고, 인용은 문서에 처음 나온 순서로 번호를 매겨 인용 쪽(0-based+1, 0 쪽 제외)과 함께 참고문헌에 싣는다 — Word·PDF 가 같은 모델을 쓴다"
```

---

### Task 9: Word 내보내기 (`docx` 의존성 + `utils/reportDocx.ts`)

**Files:**
- Modify: `frontend/package.json`(`dependencies` 에 `docx`), `frontend/package-lock.json`
- Create: `frontend/utils/reportDocx.ts`
- Test: `frontend/tests/unit/reportDocx.test.ts`(새 파일)

- [ ] **Step 1: `docx` 를 설치한다**

```bash
cd frontend && npm install docx
```

`package.json` 변경(npm 이 알파벳 순으로 넣는다. 2026-09-28 기준 최신 9.8.0 — 설치 결과의 `^` 버전을 그대로 둔다):

교체 전:
```json
  "dependencies": {
    "marked": "^18.0.0",
```
교체 후:
```json
  "dependencies": {
    "docx": "^9.8.0",
    "marked": "^18.0.0",
```

확인:
```bash
cd frontend && npm ls docx jszip
```
기대 출력:
```
frontend@ ...
`-- docx@9.8.0
  `-- jszip@3.10.2
```

- 잠금 파일에 새로 들어오는 패키지는 16개다: `docx`·`jszip`·`pako`·`lie`·`immediate`·`setimmediate`·`xml`·`xml-js`·`hash.js`·`minimalistic-assert`, 그리고 jszip·docx 아래 중첩된 것들.
- `docx` 는 `@types/node@^26` 을 자기 아래(`node_modules/docx/node_modules`)에 중첩해 둔다. 루트의 `@types/node@25` 와 섞이지 않아 타입검사에 영향이 없다. 계획 작성 때 사본의 `nuxi typecheck` 에서 오류 0 을 확인했다.
- 테스트는 `jszip` 을 직접 import 한다. `docx` 가 끌어와 `node_modules/jszip` 에 올라오는 패키지라 새 의존성을 package.json 에 적지 않는다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`frontend/tests/unit/reportDocx.test.ts`:

```ts
// frontend/tests/unit/reportDocx.test.ts
// jszip 은 docx 가 끌어오는 의존성이다 — 압축을 풀어 보려고 새 패키지를 들이지 않는다
import JSZip from "jszip";
import { describe, expect, it } from "vitest";
import type { ReportDoc } from "~/utils/reportDocument";
import { toDocxBuffer } from "~/utils/reportDocx";

const doc: ReportDoc = {
  fileName: "딥리서치_국내_AI_규제_연구_동향_20260928.docx",
  blocks: [
    { type: "title", text: "국내 AI 규제 연구 동향" },
    { type: "meta", text: "생성 일시 2026년 9월 28일 15:05" },
    { type: "heading", level: 1, text: "1. 규제 논의의 흐름" },
    { type: "para", runs: [{ text: "규제 논의가 늘었다 " }, { cite: 1 }, { text: "." }] },
    { type: "heading", level: 2, text: "향후 과제" },
    { type: "bullets", items: [[{ text: "국제 비교가 필요하다 " }, { cite: 2 }]] },
    { type: "para", runs: [{ text: "자동 점검에서 보고할 한계가 발견되지 않았습니다." }], muted: true },
  ],
  references: [
    { n: 1, eid: "E1", text: "김철수 (2019). AI 윤리 교육." },
    { n: 2, eid: "E2", text: "이영희 (2021). 규제 샌드박스." },
  ],
};

async function unzip(target: ReportDoc): Promise<JSZip> {
  return JSZip.loadAsync(await toDocxBuffer(target));
}

async function read(zip: JSZip, path: string): Promise<string> {
  return (await zip.file(path)?.async("string")) ?? "";
}

describe("toDocxBuffer", () => {
  it("본문에 질문·인용 번호·참고문헌을 싣는다", async () => {
    const xml = await read(await unzip(doc), "word/document.xml");
    expect(xml).toContain("국내 AI 규제 연구 동향");
    expect(xml).toContain("[1]");
    expect(xml).toContain("[2]");
    expect(xml).toContain("참고문헌");
    expect(xml).toContain("[1] 김철수 (2019). AI 윤리 교육.");
  });

  it("A4 용지·맑은 고딕으로 만들고 바닥글에 쪽 번호를 단다", async () => {
    const zip = await unzip(doc);
    expect(await read(zip, "word/document.xml")).toMatch(/<w:pgSz [^>]*w:w="11906"[^>]*w:h="16838"/);
    expect(await read(zip, "word/styles.xml")).toContain('w:eastAsia="맑은 고딕"');
    const footer = Object.keys(zip.files).find((name) => /^word\/footer\d+\.xml$/.test(name));
    expect(footer).toBeDefined();
    expect(await read(zip, footer ?? "")).toContain("PAGE");
  });

  it("인용한 근거가 없으면 참고문헌 제목을 싣지 않는다", async () => {
    const xml = await read(await unzip({ ...doc, references: [] }), "word/document.xml");
    expect(xml).not.toContain("참고문헌");
  });
});
```

- [ ] **Step 3: 실행해 실패를 확인한다**

```bash
cd frontend && npx vitest run tests/unit/reportDocx.test.ts
```

기대 출력:
```
 FAIL  tests/unit/reportDocx.test.ts [ tests/unit/reportDocx.test.ts ]
Error: Cannot find module '~/utils/reportDocx' imported from '.../frontend/tests/unit/reportDocx.test.ts'.
 Test Files  1 failed (1)
```

- [ ] **Step 4: 구현한다**

`frontend/utils/reportDocx.ts`:

```ts
// frontend/utils/reportDocx.ts
import type { Document as DocxDocument, Paragraph } from "docx";
import { docRunText, type DocBlock, type DocRun, type ReportDoc } from "./reportDocument";

// docx 는 1MB 가 넘는다 — 화면 번들에 넣지 않고 내려받기를 누를 때 받는다(동적 import).
// 구성 함수는 모듈을 인자로 받아 Node 테스트가 브라우저와 같은 코드를 그대로 돌린다.
export type DocxModule = typeof import("docx");

const FONT = "맑은 고딕";
const MUTED = "666666";
// A4(210×297mm)와 여백 2cm — 단위는 twip(1/1440인치)
const A4 = { width: 11906, height: 16838 };
const MARGIN = 1134;

// docx 의 글자 크기는 반 포인트 단위다
function pt(n: number): number {
  return Math.round(n * 2);
}

export function buildDocxDocument(docx: DocxModule, doc: ReportDoc): DocxDocument {
  const { AlignmentType, Document, Footer, HeadingLevel, PageNumber, Paragraph, TextRun } = docx;

  const runsOf = (runs: DocRun[], muted = false) =>
    runs.map((r) => new TextRun({ text: docRunText(r), color: muted ? MUTED : undefined }));

  function paragraphs(block: DocBlock): Paragraph[] {
    switch (block.type) {
      case "title":
        return [new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun(block.text)] })];
      case "meta":
        return [new Paragraph({ children: [new TextRun({ text: block.text, size: pt(9), color: MUTED })] })];
      case "heading":
        return [
          new Paragraph({
            heading: block.level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
            children: [new TextRun(block.text)],
          }),
        ];
      case "para":
        return [new Paragraph({ children: runsOf(block.runs, block.muted), spacing: { after: 120 } })];
      case "bullets":
        return block.items.map((runs) => new Paragraph({ bullet: { level: 0 }, children: runsOf(runs) }));
    }
  }

  // 참고문헌은 번호가 긴 줄 앞으로 튀어나오게(내어쓰기) 둔다 — 번호로 찾아 읽는 목록이다
  const references = doc.references.length
    ? [
        new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("참고문헌")] }),
        ...doc.references.map(
          (r) =>
            new Paragraph({
              children: [new TextRun(`[${r.n}] ${r.text}`)],
              indent: { left: 440, hanging: 440 },
              spacing: { after: 80 },
            }),
        ),
      ]
    : [];

  return new Document({
    creator: "NL-Lib 딥리서치",
    title: doc.fileName.replace(/\.docx$/i, ""),
    styles: {
      default: {
        document: { run: { font: FONT, size: pt(10.5) }, paragraph: { spacing: { line: 312 } } },
        title: { run: { font: FONT, size: pt(18), bold: true, color: "000000" }, paragraph: { spacing: { after: 160 } } },
        heading1: {
          run: { font: FONT, size: pt(14), bold: true, color: "000000" },
          paragraph: { spacing: { before: 360, after: 120 } },
        },
        heading2: {
          run: { font: FONT, size: pt(12), bold: true, color: "333333" },
          paragraph: { spacing: { before: 200, after: 80 } },
        },
      },
    },
    sections: [
      {
        properties: { page: { size: A4, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ children: [PageNumber.CURRENT], size: pt(9), color: MUTED })],
              }),
            ],
          }),
        },
        children: [...doc.blocks.flatMap(paragraphs), ...references],
      },
    ],
  });
}

export async function toDocxBlob(doc: ReportDoc): Promise<Blob> {
  const docx = await import("docx");
  return docx.Packer.toBlob(buildDocxDocument(docx, doc));
}

// Node 에는 Blob 을 파일로 풀어 볼 도구가 마땅치 않다 — 테스트는 같은 경로로 바이트를 받는다
export async function toDocxBuffer(doc: ReportDoc): Promise<Uint8Array> {
  const docx = await import("docx");
  return new Uint8Array(await docx.Packer.toArrayBuffer(buildDocxDocument(docx, doc)));
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  // 문서에 붙지 않은 링크의 click 을 무시하는 브라우저가 있다
  document.body.appendChild(a);
  a.click();
  a.remove();
  // 곧바로 해제하면 내려받기가 시작되기 전에 주소가 사라지는 브라우저가 있다
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
```

`docx` 의 `Document` 타입을 `DocxDocument` 로 바꿔 부르는 까닭: 이름을 그대로 두면 이 모듈 안에서 DOM 의 `Document` 타입을 가려 읽는 사람이 헷갈린다. 쓰는 곳은 타입뿐이라 `import type` 으로 지워진다. 번들에는 동적 import 하나만 남는다.

- [ ] **Step 5: 통과를 확인한다**

```bash
cd frontend && npx vitest run tests/unit/reportDocx.test.ts
```

기대 출력: `Test Files  1 passed (1)` · `Tests  3 passed (3)`. 수집에 약 0.5초 걸린다(docx 로드).

- [ ] **Step 6: 전체 테스트·타입검사**

```bash
cd frontend && npx vitest run
cd frontend && npx nuxi typecheck 2>&1 | grep "error TS"
```

기대 출력: vitest 는 실패 0(20파일 / 348 tests), typecheck 는 출력 없음.

- [ ] **Step 7: 번들 확인 — docx 가 별도 청크인지**

이 시점에는 아직 `toDocxBlob` 을 부르는 화면이 없다. 그래서 청크 확인은 Task 10 Step 8 에서 한다. 여기서는 빌드가 깨지지 않는지만 본다.

```bash
cd frontend && npm run build 2>&1 | tail -3
```

기대 출력: `✨ Build complete!`

- [ ] **Step 8: 커밋**

```bash
git add frontend/package.json frontend/package-lock.json frontend/utils/reportDocx.ts frontend/tests/unit/reportDocx.test.ts
git commit -m "[Feat] round04b — Word 내보내기: docx 를 추가하고 문서 모델을 A4·맑은 고딕·바닥글 쪽 번호의 .docx 로 만든다. docx 는 내려받기를 누를 때만 동적 import 하고, 구성 함수는 모듈을 인자로 받아 Node 테스트가 실제 파일을 풀어 확인한다"
```

---

### Task 10: 내려받기 메뉴·인쇄 화면·배선

**Files:**
- Create: `frontend/components/research/ReportDownloadMenu.vue`, `frontend/components/research/ReportPrint.vue`, `frontend/composables/useReportExport.ts`
- Modify: `frontend/assets/css/research.css`(파일 끝에 두 절 추가), `frontend/pages/research/[id].vue`(import 3곳 · 템플릿 4곳 · 스크립트 1절)

**인터랙션(spec §7-4):**
- 메뉴가 짧게 떠오르며 열린다.
- 항목마다 한 줄 설명이 붙는다.
- 만드는 동안 버튼 안에서 점이 숨 쉬고 "만드는 중…" 을 보인다.
- Word 가 끝나면 토스트로 알린다.
- 움직임은 모두 `prefers-reduced-motion` 이면 끈다.
- 키보드 규칙은 `+` 메뉴와 같다(`menuStep`).

**[초안 저장]의 원천:** Task 7 이 페이지에 둔 `draft`(초안이 보이는 단계에서 `draftReport(view)`, 끝난 절이 없으면 null)를 그대로 쓴다. 현황 카드는 `:disabled="!draft"` 로 끝난 절이 생길 때까지 막고, 멈춘 초안은 `draftMode.interrupted` 일 때만 메뉴를 보인다.

- [ ] **Step 1: 전용 CSS 를 덧붙인다**

`frontend/assets/css/research.css` 의 **파일 끝**, 즉 Task 7 이 덧붙인 아래 줄임 동작 블록 바로 뒤에 덧붙인다.

찾을 코드(Task 7 이 덧붙인 파일 끝 블록):

```css
@media (prefers-reduced-motion: reduce) {
  .rs-section {
    transition: none;
  }
  .rs-badge--live::before,
  .rs-report--draft .rs-section__body,
  .rs-skeleton__line {
    animation: none;
  }
}
```

그 뒤에 아래를 그대로 덧붙인다. 이 파일은 `nuxt.config.ts` 의 `css` 로 모든 페이지에 실린다. 그래서 인쇄 숨김 규칙은 딥리서치 화면(`.rs-page`)과 인쇄 전용 문서(`.rs-print`)가 있을 때만 걸리게 좁혔다.

```css

/* ── 내려받기 메뉴 ───────────────────────────────────────── */
.rs-dl {
  position: relative;
  display: inline-flex;
}
.rs-dl__btn[aria-disabled="true"] {
  opacity: 0.5;
  cursor: not-allowed;
}
.rs-dl__btn[aria-busy="true"] {
  cursor: progress;
}
/* 만드는 중 — 누른 뒤 아무 일도 없는 것처럼 보이지 않게 버튼 안에서 점이 숨 쉰다 */
.rs-dl__dot {
  width: 0.4rem;
  height: 0.4rem;
  background: var(--skx-primary);
  border-radius: 50%;
  animation: rs-dl-breathe 1s ease-in-out infinite alternate;
}
@keyframes rs-dl-breathe {
  from {
    opacity: 0.3;
  }
  to {
    opacity: 1;
  }
}
.rs-dl__menu {
  position: absolute;
  top: calc(100% + 0.3rem);
  right: 0;
  z-index: 40;
  min-width: 13rem;
  margin: 0;
  padding: 0.3rem;
  list-style: none;
  background: var(--skx-white);
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-shadow-banner);
  transform-origin: top right;
  animation: rs-dl-in 0.14s ease-out;
}
@keyframes rs-dl-in {
  from {
    opacity: 0;
    transform: translateY(-0.2rem) scale(0.98);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.rs-dl__item {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  width: 100%;
  padding: 0.5rem;
  font-family: inherit;
  text-align: left;
  background: none;
  border: none;
  border-radius: var(--skx-radius-sm);
  cursor: pointer;
}
.rs-dl__item:hover,
.rs-dl__item:focus-visible {
  background: var(--skx-border-c1);
  outline: none;
}
.rs-dl__label {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--skx-ink);
}
.rs-dl__desc {
  font-size: 0.55rem;
  color: var(--skx-gray-1);
  line-height: 1.4;
}
@media (prefers-reduced-motion: reduce) {
  .rs-dl__menu,
  .rs-dl__dot {
    animation: none;
  }
}

/* ── 인쇄(PDF로 저장) ────────────────────────────────────── */
/* 인쇄 전용 문서는 화면에 그리지 않는다 — [PDF로 저장]을 누른 동안에만 body 에 붙는다 */
.rs-print {
  display: none;
}
@media print {
  @page {
    size: A4;
    margin: 18mm 16mm;
  }
  /* [PDF로 저장] 중에는 인쇄 전용 문서만 찍는다 — body 의 다른 자식(앱·토스트·원문 뷰어)은 숨긴다 */
  body:has(> .rs-print) > :not(.rs-print) {
    display: none !important;
  }
  /* 딥리서치 화면을 그대로 인쇄(Ctrl+P)해도 사이드바·머리·버튼·진행 패널은 뺀다.
     이 파일은 모든 페이지에 실리므로 다른 화면의 인쇄에는 걸리지 않게 딥리서치 화면으로 좁힌다 */
  .skx-app:has(.rs-page) .skx-lnb,
  body:has(.rs-page) .skx-footer,
  .rs-page .rs-head,
  .rs-page .rs-col-side,
  .rs-page .rs-dl,
  .rs-page .rs-btn {
    display: none !important;
  }
  .rs-print {
    display: block;
    font-family: "맑은 고딕", "Malgun Gothic", "Pretendard", sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: var(--skx-ink);
  }
  .rs-print__title {
    margin: 0 0 6pt;
    font-size: 18pt;
    font-weight: 700;
    line-height: 1.35;
  }
  .rs-print__meta {
    margin: 0;
    font-size: 9pt;
    color: var(--skx-gray-1);
    word-break: break-all;
  }
  .rs-print__h1 {
    margin: 18pt 0 6pt;
    font-size: 14pt;
    font-weight: 700;
    break-after: avoid;
  }
  .rs-print__h2 {
    margin: 10pt 0 4pt;
    font-size: 12pt;
    font-weight: 700;
    break-after: avoid;
  }
  .rs-print__para {
    margin: 0 0 6pt;
  }
  .rs-print__para.is-muted {
    color: var(--skx-gray-1);
  }
  .rs-print__list {
    margin: 0 0 6pt;
    padding-left: 16pt;
  }
  .rs-print__refs {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .rs-print__list li,
  .rs-print__refs li {
    margin-bottom: 3pt;
    break-inside: avoid;
  }
  /* 번호로 찾아 읽는 목록이라 둘째 줄부터 들여 번호가 튀어나오게 한다 */
  .rs-print__refs li {
    padding-left: 22pt;
    text-indent: -22pt;
  }
}
```

- [ ] **Step 2: 내려받기 메뉴 컴포넌트**

`frontend/components/research/ReportDownloadMenu.vue`:

```vue
<!-- frontend/components/research/ReportDownloadMenu.vue -->
<template>
  <div ref="root" class="rs-dl" @keydown="onRootKeydown">
    <!-- disabled 대신 aria-disabled: 고른 직후 만드는 중(busy)으로 바뀔 때 초점을 쥔 버튼이 비활성이 되면
         초점이 body 로 떨어진다(키보드 사용자가 제자리를 잃는다) -->
    <button
      ref="trigger"
      type="button"
      class="rs-btn rs-btn--ghost rs-btn--small rs-dl__btn"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="open ? menuId : undefined"
      :aria-disabled="inactive"
      :aria-busy="busy"
      :title="disabled ? '아직 내려받을 내용이 없습니다' : undefined"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span v-if="busy" class="rs-dl__dot" aria-hidden="true" />
      {{ busy ? "만드는 중…" : `${label} ▾` }}
    </button>
    <ul v-if="open" :id="menuId" ref="menu" class="rs-dl__menu" role="menu" :aria-label="label" @keydown="onMenuKeydown">
      <li v-for="f in FORMATS" :key="f.id" role="none">
        <!-- tabindex=-1: 항목 사이는 방향키로 옮긴다. Tab 은 메뉴를 닫고 다음 요소로 간다 -->
        <button type="button" role="menuitem" tabindex="-1" class="rs-dl__item" @click="choose(f.id)">
          <span class="rs-dl__label">{{ f.label }}</span>
          <span class="rs-dl__desc">{{ f.description }}</span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { menuStep } from "~/utils/menuNav";
import type { ReportExportFormat } from "~/utils/reportDocument";

const props = withDefaults(defineProps<{ label: string; disabled?: boolean; busy?: boolean }>(), {
  disabled: false,
  busy: false,
});
const emit = defineEmits<{ select: [format: ReportExportFormat] }>();

const FORMATS: readonly { id: ReportExportFormat; label: string; description: string }[] = [
  { id: "docx", label: "Word 문서(.docx)", description: "고쳐 쓰기 좋고 한글에서도 열립니다" },
  { id: "pdf", label: "PDF로 저장", description: "인쇄 창에서 대상을 ‘PDF로 저장’으로 고릅니다" },
];

const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const menuId = useId();
const open = ref(false);
const inactive = computed(() => props.disabled || props.busy);

watch(inactive, (value) => {
  if (value) open.value = false;
});

function items(): HTMLElement[] {
  return Array.from(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
}

function focusItem(key: string): boolean {
  const list = items();
  const at = list.findIndex((el) => el === document.activeElement);
  const next = menuStep(at, key, list.length);
  if (next === null) return false;
  list[next]?.focus();
  return true;
}

// 열면 첫 항목(위 방향키로 열면 마지막 항목)으로 초점을 옮긴다 — 방향키·Esc 가 메뉴 안에서 먹게
async function openMenu(key: "ArrowDown" | "ArrowUp" = "ArrowDown"): Promise<void> {
  if (inactive.value) return;
  open.value = true;
  await nextTick();
  focusItem(key);
}

function closeMenu(returnFocus: boolean): void {
  open.value = false;
  if (returnFocus) trigger.value?.focus();
}

function toggle(): void {
  if (open.value) closeMenu(false);
  else void openMenu();
}

function onTriggerKeydown(e: KeyboardEvent): void {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  e.preventDefault();
  if (open.value) focusItem(e.key === "ArrowUp" ? "End" : "Home");
  else void openMenu(e.key);
}

function onMenuKeydown(e: KeyboardEvent): void {
  // Tab 은 막지 않는다 — 버튼으로 초점을 돌려 둔 뒤 기본 동작이 그 앞뒤 요소로 옮긴다
  if (e.key === "Tab") {
    closeMenu(true);
    return;
  }
  if (focusItem(e.key)) e.preventDefault();
}

// 버튼에 초점이 있어도(마우스로 연 뒤) Esc 로 닫히게 묶음 전체에서 듣는다
function onRootKeydown(e: KeyboardEvent): void {
  if (e.key !== "Escape" || !open.value) return;
  e.preventDefault();
  e.stopPropagation();
  closeMenu(true);
}

function choose(format: ReportExportFormat): void {
  closeMenu(true);
  emit("select", format);
}

function onDocumentClick(e: MouseEvent): void {
  if (open.value && root.value && e.target instanceof Node && !root.value.contains(e.target)) open.value = false;
}

onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));
</script>
```

- [ ] **Step 3: 인쇄 전용 화면 컴포넌트**

`frontend/components/research/ReportPrint.vue`:

```vue
<!-- frontend/components/research/ReportPrint.vue -->
<template>
  <!-- body 바로 아래에 붙인다 — 인쇄 CSS 가 body 의 다른 자식(앱 전체)을 한 번에 숨기고 이것만 찍는다 -->
  <Teleport to="body">
    <article class="rs-print">
      <template v-for="(block, bi) in doc.blocks" :key="bi">
        <h1 v-if="block.type === 'title'" class="rs-print__title">{{ block.text }}</h1>
        <p v-else-if="block.type === 'meta'" class="rs-print__meta">{{ block.text }}</p>
        <h2 v-else-if="block.type === 'heading' && block.level === 1" class="rs-print__h1">{{ block.text }}</h2>
        <h3 v-else-if="block.type === 'heading'" class="rs-print__h2">{{ block.text }}</h3>
        <p v-else-if="block.type === 'para'" class="rs-print__para" :class="{ 'is-muted': block.muted }">
          {{ runsText(block.runs) }}
        </p>
        <ul v-else-if="block.type === 'bullets'" class="rs-print__list">
          <li v-for="(runs, ii) in block.items" :key="ii">{{ runsText(runs) }}</li>
        </ul>
      </template>
      <template v-if="doc.references.length">
        <h2 class="rs-print__h1">참고문헌</h2>
        <ol class="rs-print__refs">
          <li v-for="r in doc.references" :key="r.n">[{{ r.n }}] {{ r.text }}</li>
        </ol>
      </template>
    </article>
  </Teleport>
</template>

<script setup lang="ts">
import { docRunText, type DocRun, type ReportDoc } from "~/utils/reportDocument";

defineProps<{ doc: ReportDoc }>();

function runsText(runs: DocRun[]): string {
  return runs.map(docRunText).join("");
}
</script>
```

- [ ] **Step 4: 내보내기 composable**

`frontend/composables/useReportExport.ts`:

```ts
// frontend/composables/useReportExport.ts
import { nextTick, ref, shallowRef } from "vue";
import type { ReportDoc } from "~/utils/reportDocument";
import { downloadBlob, toDocxBlob } from "~/utils/reportDocx";

export function useReportExport() {
  const exporting = ref(false);
  // 문서 모델은 한 번 만들고 바꾸지 않는다 — 깊은 반응형으로 감쌀 까닭이 없다
  const printDoc = shallowRef<ReportDoc | null>(null);

  async function exportDocx(doc: ReportDoc): Promise<void> {
    if (exporting.value) return;
    exporting.value = true;
    try {
      downloadBlob(await toDocxBlob(doc), doc.fileName);
    } finally {
      exporting.value = false;
    }
  }

  async function printPdf(doc: ReportDoc): Promise<void> {
    if (exporting.value) return;
    exporting.value = true;
    const previousTitle = document.title;
    const restore = () => {
      document.title = previousTitle;
      printDoc.value = null;
      exporting.value = false;
    };
    try {
      printDoc.value = doc;
      // 인쇄 전용 문서가 DOM 에 그려진 뒤에 인쇄 창을 연다
      await nextTick();
      // 인쇄 창의 "PDF로 저장"은 문서 제목을 기본 파일 이름으로 쓴다
      document.title = doc.fileName.replace(/\.docx$/i, "");
      window.addEventListener("afterprint", restore, { once: true });
      window.print();
    } catch (e) {
      window.removeEventListener("afterprint", restore);
      restore();
      throw e;
    }
  }

  return { exporting, printDoc, exportDocx, printPdf };
}
```

- [ ] **Step 5: 페이지 — import**

`frontend/pages/research/[id].vue` 의 `<script setup>` import 를 고친다. Task 7 이 import 블록을 고쳤으므로 문자열로 찾는다.

(1) 컴포넌트 import:

교체 전:
```ts
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ReportView from "~/components/research/ReportView.vue";
```
교체 후:
```ts
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ReportDownloadMenu from "~/components/research/ReportDownloadMenu.vue";
import ReportPrint from "~/components/research/ReportPrint.vue";
import ReportView from "~/components/research/ReportView.vue";
```

(2) composable import:

교체 전:
```ts
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
```
교체 후:
```ts
import { useReportExport } from "~/composables/useReportExport";
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
```

(3) 문서 모델 import:

교체 전:
```ts
import { pdfCheckProblem, researchErrorMessage } from "~/utils/researchErrors";
```
교체 후:
```ts
import { pdfCheckProblem, researchErrorMessage } from "~/utils/researchErrors";
import {
  buildReportDocument,
  docInputFromDraft,
  docInputFromReport,
  type ReportDoc,
  type ReportExportFormat,
} from "~/utils/reportDocument";
```

(`draftReport` 는 import 하지 않는다 — [초안 저장]은 Task 7 이 둔 `draft` computed 를 쓴다. Task 7 이 `~/utils/researchDraft` import 줄을 이미 넣었으니 같은 이름을 다시 들이지 않는다.)

- [ ] **Step 6: 페이지 — 스크립트 절**

`// ── 토스트` 절 바로 앞에 새 절을 넣는다.

교체 전:
```ts
// ── 토스트 ────────────────────────────────────────────────
```
교체 후:
```ts
// ── 내려받기(Word·PDF) ────────────────────────────────────
const { exporting, printDoc, exportDocx, printPdf } = useReportExport();

// 문서에 싣는 연구 주소 — 주소창의 쿼리·해시는 빼고 잡 주소 정본만 적는다
function researchUrl(jobId: string): string {
  return `${window.location.origin}/research/${jobId}`;
}

async function runExport(doc: ReportDoc, format: ReportExportFormat): Promise<void> {
  try {
    if (format === "docx") {
      await exportDocx(doc);
      showToast("Word 문서를 내려받았습니다");
    } else {
      await printPdf(doc);
    }
  } catch (e) {
    console.warn("[research] 내보내기 실패", e);
    // 배포 뒤 옛 화면에서 누르면 docx 조각 파일이 사라져 동적 import 가 실패한다 — 새로고침이 답이다
    showToast(
      format === "docx"
        ? "Word 문서를 만들지 못했습니다. 새로고침한 뒤 다시 시도해 주세요."
        : "인쇄 창을 열지 못했습니다. 다시 시도해 주세요.",
    );
  }
}

function downloadReport(format: ReportExportFormat): void {
  const v = view.value;
  if (!v?.report) return;
  const input = docInputFromReport(v.report, { generatedAt: v.finishedAt, url: researchUrl(v.jobId) });
  void runExport(buildReportDocument(input, new Date()), format);
}

// 작성 중·멈춘 초안은 화면에 보이는 초안(draft — 끝난 절이 하나도 없으면 null)을 그대로 문서로 만든다
function saveDraft(format: ReportExportFormat): void {
  const v = view.value;
  const saved = draft.value;
  if (!v || !saved) return;
  void runExport(buildReportDocument(docInputFromDraft(saved, v, researchUrl(v.jobId)), new Date()), format);
}

// ── 토스트 ────────────────────────────────────────────────
```

`showToast` 는 아래 토스트 절의 함수 선언이라 끌어올려진다. 여기서 먼저 불러도 된다. `draft` 는 Task 7 의 "보고서 작성 현황·초안" 절에 있다.

- [ ] **Step 7: 페이지 — 템플릿 4곳**

(1) 완성 보고서 — `[링크 복사]` 옆 `[다운로드 ▾]`. Task 7 은 이 요소를 고치지 않았다.

교체 전:
```html
              <ReportView
                v-if="reportState === 'ready' && view.report"
                :report="view.report"
                :generated-at="view.finishedAt"
                @open-pdf="openPdf"
                @copy-link="copyLink"
              />
```
교체 후:
```html
              <ReportView
                v-if="reportState === 'ready' && view.report"
                :report="view.report"
                :generated-at="view.finishedAt"
                @open-pdf="openPdf"
                @copy-link="copyLink"
              >
                <template #actions>
                  <ReportDownloadMenu label="다운로드" :busy="exporting" @select="downloadReport" />
                </template>
              </ReportView>
```

(2) 작성 현황 카드 — Task 7 이 넣은 요소에 [초안 저장 ▾]를 단다. 끝난 절이 없으면(`draft` 가 null) 흐리고 눌리지 않는다.

교체 전:
```html
              <SynthProgressCard
                v-else-if="phase === 'synthesizing'"
                :slots="slots"
                :eta="eta"
                :highlight-idx="linkedIdx"
                @jump="jumpToSection"
                @hover="hoverIdx = $event"
              />
```
교체 후:
```html
              <SynthProgressCard
                v-else-if="phase === 'synthesizing'"
                :slots="slots"
                :eta="eta"
                :highlight-idx="linkedIdx"
                @jump="jumpToSection"
                @hover="hoverIdx = $event"
              >
                <template #actions>
                  <ReportDownloadMenu label="초안 저장" :disabled="!draft" :busy="exporting" @select="saveDraft" />
                </template>
              </SynthProgressCard>
```

(3) 멈춘 초안 — Task 7 의 초안 `ReportView` 는 작성 중·멈춘 초안·완료 직후를 `:draft="draftMode"` 요소 하나로 그린다. 슬롯은 늘 달되 메뉴는 `draftMode.interrupted`(실패·취소)일 때만 보인다. spec §14-3 "작성 중 초안에는 한계 섹션·[다운로드]가 없다" — 작성 중 저장은 현황 카드가 맡고, 완료 직후에는 곧 최종본의 [다운로드]로 바뀐다.

교체 전:
```html
                <ReportView
                  :report="draft.report"
                  :generated-at="null"
                  :draft="draftMode"
                  :highlight-idx="linkedIdx"
                  @open-pdf="openPdf"
                  @copy-link="copyLink"
                />
```
교체 후:
```html
                <ReportView
                  :report="draft.report"
                  :generated-at="null"
                  :draft="draftMode"
                  :highlight-idx="linkedIdx"
                  @open-pdf="openPdf"
                  @copy-link="copyLink"
                >
                  <!-- 멈춘 초안에만 둔다 — 작성 중 저장은 현황 카드가 맡고, 완료 직후에는 곧 최종본의 [다운로드]로 바뀐다 -->
                  <template #actions>
                    <ReportDownloadMenu v-if="draftMode?.interrupted" label="초안 저장" :busy="exporting" @select="saveDraft" />
                  </template>
                </ReportView>
```

(이 요소는 `<template v-else-if="draft">` 안에 있어 `draft` 가 늘 있다 — `disabled` 가 필요 없다.)

(4) 인쇄 전용 문서 — 원문 뷰어 줄 아래:

교체 전:
```html
    <PdfViewer v-if="pdf" :cnts-id="pdf.cntsId" :title="pdf.title" :page="pdf.page" @close="pdf = null" />
```
교체 후:
```html
    <PdfViewer v-if="pdf" :cnts-id="pdf.cntsId" :title="pdf.title" :page="pdf.page" @close="pdf = null" />
    <ReportPrint v-if="printDoc" :doc="printDoc" />
```

- [ ] **Step 8: 타입검사·빌드·번들 확인**

```bash
cd frontend && npx nuxi typecheck 2>&1 | grep "error TS"
```
기대 출력: 없음.

```bash
cd frontend && npm run build 2>&1 | tail -3
DOCX=$(grep -l "wordprocessingml" .output/public/_nuxt/*.js); echo "$DOCX" | wc -l
du -k $DOCX
IMPORTERS=$(grep -l "$(basename "$DOCX")" .output/public/_nuxt/*.js); echo "$IMPORTERS"
grep -c "rs-page" $IMPORTERS
```

기대:
- `✨ Build complete!`
- docx 청크는 **1개**, 약 **436K**.
- 그 청크 이름을 담은 파일은 **딥리서치 페이지 청크 하나**다. 동적 import 로 부르고, `rs-page` 개수가 1 이상이다.
- 진입 청크(`entry.*`)에 docx 가 들어가 있으면 동적 import 가 정적 import 로 바뀐 것이다. `utils/reportDocx.ts` 에 `import … from "docx"`(값 import)가 있는지 확인한다. 타입은 `import type` 만 써야 한다.
- 참고로 `.output/server/node_modules/docx` 도 생긴다. Nitro 가 서버 번들의 동적 import 를 따라 복사한 것이며 동작에는 영향이 없다.

```bash
cd frontend && grep -n "savableDraft\|ReportDownloadMenu" "pages/research/[id].vue"
```
기대: `savableDraft` 는 없고, `ReportDownloadMenu` 는 import 1줄 + 템플릿 3곳(완성 보고서·현황 카드·초안)이다.

- [ ] **Step 9: 화면 확인(로컬 → 운영 API 프록시)**

```bash
cd frontend && NUXT_DEV_API_TARGET=http://<서버>:92/api npm run dev
```

- **완성된 연구** `/research/<id>`
  - 보고서 머리의 [링크 복사] 옆에 [다운로드 ▾]가 보인다.
  - 누르면 메뉴가 짧게 떠오르며 열리고, 항목 두 개에 한 줄 설명이 붙는다.
  - **Word 문서(.docx)**: 버튼이 잠깐 "만드는 중…"(숨 쉬는 점)이 됐다가 `딥리서치_<질문 앞 20자>_<YYYYMMDD>.docx` 가 내려받아지고 토스트 "Word 문서를 내려받았습니다" 가 뜬다.
  - 받은 파일을 Word 와 한글에서 연다. 제목·메타·서론·절·`[n]`·한계·부록·참고문헌, A4, 맑은 고딕, 바닥글 쪽 번호를 확인한다.
  - DevTools Network 에서 docx 청크가 **이때 처음** 받아지는지 본다.
  - **PDF로 저장**: 인쇄 미리보기에 사이드바·머리·진행 패널 없이 문서만 A4 로 보이는지, 대상을 "PDF로 저장"으로 골랐을 때 파일 이름 기본값이 `딥리서치_…_YYYYMMDD` 인지 본다. 창을 닫으면 탭 제목이 원래대로("<질문> — 딥리서치") 돌아와야 한다.
- **키보드**
  - [다운로드]에 Tab → ↓ 로 열면 첫 항목에 초점이 간다. ↑↓·Home·End 로 옮기고, Enter 로 고른다.
  - Esc 는 닫고 버튼으로 초점을 돌린다. Tab 은 닫고 다음 요소로 간다.
- **Ctrl+P(메뉴 없이)**: 딥리서치 화면을 그대로 인쇄해도 사이드바·머리·버튼·진행 패널이 빠진다. 다른 페이지(논문 검색)의 인쇄는 전과 같다.
- **작성 중**(종합 단계 잡 — 워커 배포 뒤 운영에서 본다)
  - 현황 카드의 [초안 저장 ▾]는 끝난 절이 없을 때 흐리고 눌리지 않는다. 포인터를 올리면 "아직 내려받을 내용이 없습니다" 가 뜬다.
  - 첫 절이 끝나면 활성이 된다.
  - 초안 Word 의 제목은 "(초안 · N개 절 중 M개 작성)", 파일 이름은 `…_초안.docx` 이고, 한계 자리에 초안 안내 문구가 실린다.
  - 작성 중 초안(`작성 중` 배지)의 머리에는 [링크 복사]만 있고 [초안 저장]이 없다.
- **멈춘 초안**(종합 중 실패·취소한 잡): 초안 머리("완성되지 않은 초안" 배지)의 [초안 저장 ▾]가 같은 규칙으로 동작한다.
- **움직임 줄이기**: OS 에서 "동작 줄이기"를 켜면 메뉴 떠오름·점 숨쉬기가 멈춘다.

- [ ] **Step 10: 커밋**

```bash
git add frontend/components/research/ReportDownloadMenu.vue frontend/components/research/ReportPrint.vue frontend/composables/useReportExport.ts frontend/assets/css/research.css "frontend/pages/research/[id].vue"
git commit -m "[Feat] round04b — 보고서 내려받기: 완성 보고서 머리에 [다운로드 ▾], 작성 현황 카드·멈춘 초안에 [초안 저장 ▾](끝난 절이 있을 때만)를 두고 Word·PDF 를 고른다. PDF 는 같은 문서 모델을 인쇄 전용 화면으로 body 에 붙여 A4 로 찍고, 인쇄하는 동안 문서 제목을 파일 이름으로 바꿔 둔다"
```

---

## 단계 5 — 최종 확인

### Task 11: 최종 확인과 spec 상태 갱신

**Files:**
- Modify: `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` (3행 머리 상태 줄)

- [ ] **Step 1: 백엔드 전체 테스트**

`app/` 에서 전체를 돈다. 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 죽는 3개 파일만 뺀다(이 계획과 무관 — 기준선 745 도 같은 명령으로 잰 값이다).

```bash
cd app && python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py
```
기대 출력: `770 passed`(경고 2건은 기존 것). 대상 파일만 다시 보면 `test_research_synthesizer.py` 91, `test_research_tasks.py` 82 다.

- [ ] **Step 2: 프론트 전체 테스트·타입검사·빌드**

```bash
cd frontend && npx vitest run
cd frontend && npx nuxi typecheck 2>&1 | grep "error TS"
cd frontend && npm run build 2>&1 | tail -1
```
기대 출력:
- vitest: `Test Files  20 passed (20)`, `Tests  348 passed (348)`.
- typecheck: 출력 없음.
- build: `└  ✨ Build complete!`.

남은 흔적 확인(진행 패널 `ProgressPanel.vue` 는 자기 `synthLine` 을 그대로 쓰므로 페이지만 본다):
```bash
cd frontend && grep -n "synthLine\|synthProgress\|savableDraft" "pages/research/[id].vue"
```
기대: 출력 없음.

- [ ] **Step 3: 커밋 저자·트레일러 확인**

```bash
git log --format='%h %an <%ae> %s' a6fd98c..HEAD
git log --format=%B a6fd98c..HEAD | grep -ciE "co-authored-by|generated with claude"
```
기대:
- 첫 명령: 계획 커밋 1개 + Task 1~10 커밋 10개가 모두 저장소 사용자(`git config user.name` — Hyonii) 이름으로 나온다.
- 둘째 명령: `0`.
- 하나라도 트레일러가 나오면 멈추고 사용자에게 알린다. 이미 쌓인 커밋의 메시지를 고치려면 사용자 승인 아래 비대화형 rebase 가 필요하다.

- [ ] **Step 4: spec 머리 상태 줄 갱신**

`docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` 3행을 Edit 도구로 고친다(CRLF 유지).

교체 전:
```markdown
> 상태: 설계 확정(2026-09-26, 사용자 승인) · §1~13 구현·운영 배포 완료 · **§14 보고서 작성 대기 화면·내보내기 추가(2026-09-28, 사용자 승인) · 구현 전**
```
교체 후:
```markdown
> 상태: 설계 확정(2026-09-26, 사용자 승인) · §1~13 구현·운영 배포 완료 · **§14 보고서 작성 대기 화면·내보내기 추가(2026-09-28, 사용자 승인) · 구현 완료(운영 배포 전)**
```

- [ ] **Step 5: 커밋**

```bash
git add docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md
git commit -m "[Docs] round04b — spec §14 상태를 구현 완료(운영 배포 전)로 고친다: 절 미리보기 백엔드·보고서 작성 현황 카드·초안·Word·PDF 내보내기 구현과 전체 테스트·타입검사·빌드 통과"
```

- [ ] **Step 6: 남은 일 알리기(이 계획에서 실행하지 않는다)**

사용자에게 다음을 알린다.
- 운영 배포(spec §14-7): 도는 잡 확인 → fastapi 이미지 빌드·푸시 → `nl-lib-celery-research` 하나만 Recreate → nuxt 이미지 → `nl-lib-nuxt` Recreate → `docker exec nl-lib-gateway nginx -s reload`. 공유 운영 서버라 **사용자 승인 뒤** 한다.
- 배포 뒤 잡 1회로 운영 화면 확인: Task 7 Step 10(b)의 항목과 Task 10 Step 9 의 "작성 중"·"멈춘 초안" 항목.
- 라운드 마무리(완료노트·교본·dev 머지)는 라운드 종료 절차(`GIT_WORKFLOW.md`, `.claude/skills/round-finish/SKILL.md`)를 따른다.

---

## 이 계획에서 다루지 않는 것

- 운영 배포와 운영 화면 확인(spec §14-7·§14-6 "화면(운영)") — 사용자 승인 뒤 따로 한다.
- Markdown·HWPX 내보내기, 서버에서 만드는 PDF, 절 서술의 토큰 스트리밍(타이핑 효과), 탐색 단계(하위질문 검색·점검) 화면 보강(spec §14-8).
- 진행 패널(`ProgressPanel.vue`)과 배치 A·B 의 기본 보기 변경. 기획자 피드백(spec §7-4 — 배치 A 는 덜 인터랙티브해 보인다)은 전환 버튼으로 언제든 바꿀 수 있어 이번에는 기본 보기를 바꾸지 않는다. 기본 보기를 정할 때 그 피드백을 근거로 쓴다.
- DB 구조 변경·fastapi 코드 변경 — 초안 데이터는 기존 `research_steps.result`(JSONB)에 담고 fastapi 는 단계 결과를 그대로 전달한다.
