# round04b 완료노트

날짜: 2026-10-01 (구현 2026-09-23~28 · 운영 배포 2026-09-28 · `dev` 머지 2026-10-01)
브랜치: `feat/round04b-deep-research-frontend` (끝 커밋 `d845b8b` · 커밋 120개 · `dev` 머지 `9b776d2`)
spec: `docs/superpowers/specs/2026-09-26-round04b-deep-research-frontend-design.md` (§1~13 본편, §14 보고서 작성 대기 화면·내보내기)
plan: `docs/superpowers/plans/2026-09-26-round04b-deep-research-frontend.md`(본편, Task 1~38) · `docs/superpowers/plans/2026-09-28-round04b-report-wait-export.md`(§14, Task 1~11)
교본: `docs/guides/round04b/` (6챕터 — [00-개요](../guides/round04b/00-개요.md), `7dbd962`)

> `dev` 머지(`9b776d2`) 뒤에 썼고, 교본 커밋(`7dbd962`)과 마감 문서 검토를 반영해 같은 날 갱신했다. round04c 가 이 브랜치 끝(`d845b8b`)에서 땄고 같은 날 함께 `dev` 에 머지됐다(`3dfeb45`). `dev→main` 머지와 push 는 아직이다.
> 구현 기간은 사용자 기록이다. 브랜치 커밋은 2026-09-26 18:40(spec `ae00bfd`)부터 2026-09-29 00:14(`d845b8b`)까지다.
> 한 줄 요약: round04a 백엔드에 **딥리서치 화면**을 붙이고 **사이드바 기록을 서버에 저장**하게 바꿨다. 이어서 §14 로 **보고서를 쓰는 동안 다 쓴 절부터 초안으로 보이고 Word·PDF 로 내려받게** 했다. 운영 검증 잡에서 화면이 아니라 **보고서 내용의 품질 문제**가 드러나 round04c 로 넘겼다.

---

## 1. 한 일

범위는 `git log a719358..d845b8b`(round04a 를 닫은 `dev` 상태 이후)다. 커밋 120개 — `[Feat]` 44 · `[Fix]` 66 · `[Docs]` 8 · `[Chore]` 1 · `[Refactor]` 1. 변경은 106파일 +39,206 / −2,085줄이고, 그중 `app/` 24파일(+4,123), `frontend/` 79파일(+13,712), `docs/` 3파일(spec·계획 2권, +21,371)이다.

### 1-1. 본편 — 딥리서치 화면·기록 세션 (spec §1~13)

| 영역 | Task | 내용 | 주 파일 |
|---|---|---|---|
| A 기록 백엔드 | 1~4 | 새 테이블 `history_items`(컬럼 12개, 부분 인덱스 `(session_id, kind, created_at DESC) WHERE deleted_at IS NULL`)와 마이그레이션 `0006_history_items`. 헤더 `x-session-id`(UUID v4)를 브라우저 ID 로 읽는 의존성. upsert·커서 쪽넘김·소프트 삭제·v1 숫자 id 의 결정론적 변환(`uuid5`). `/api/history` 7개 엔드포인트(남의 기록은 404, 상한 초과는 413) | `models/history.py`·`schemas/history.py`·`repositories/history.py`·`api/history.py`·`core/deps.py` |
| B 딥리서치 이벤트 보강 | 5~12 | `search` 에 `round`·`new_papers`, `critique` 에 `round`·`next_query`·`will_recheck` 를 더했다. 새 이벤트 `status`·`step`·`counters`·`synth`. 같은 내용을 `research_steps.result`(회차 이력 `rounds`, 절 진행 `sections`, `counters`)와 보고서 `stats` 에 남겨 끝난 잡에서도 자기점검 장면을 다시 그린다. 검토한 고유 논문 `seen_cnts`. `GET` 에 시각·`params`, 잡 생성자 `created_by`. 스냅샷에 `result`·`job` 을 싣고, 하트비트가 놓친 전이는 스냅샷 재전송으로 되살린다 | `state.py`·`runner.py`·`synthesizer.py`·`workers/research_tasks.py`·`api/research.py` |
| C1 기록 프론트 | 13~25 | Vitest 도입. 기록 타입 v2(`kind` 유니온). 브라우저 ID 를 한 벌로 합치고 `useApi` 가 모든 `/api` 요청에 `x-session-id` 를 붙인다. 복원용 축약 결과는 허용 필드 목록 방식이다. 저장소는 서버 정본에 로컬 캐시·보낼 편지함(outbox)을 두고, 쿼터를 처리하고, v1 기록을 이전(원본은 `skx_search_history_backup_v1` 로 보존)하고, 10분 안 중복을 합친다. URL 규칙(`?h=`, 옛 `?restore=` 별칭). 사이드바는 3탭·삭제·딥리서치 상태 배지(끝나지 않은 항목이 있으면 30초 폴링). 도서·논문 화면의 URL 복원과 스트림 경합(spec §1-2 H1) 해소. 잔재 삭제: `pages/search-classic.vue`·`components/ChatHistory.vue`·`composables/useSearch.ts`·`composables/useSearchHistory.ts`(→ 2026-10-02 사용자 요청으로 되살림 — 보존 화면, round07b) | `utils/history*.ts`·`composables/useHistory.ts`·`components/AppSidebar.vue`·`pages/index.vue`·`pages/papers/index.vue` |
| C2 딥리서치 화면 | 26~35 | 타입, 인용 마커 분해·슬래시 파서, SSE 리듀서, 오류(422·409·429·503)·입력 검증과 SSE 수명주기. 개발 프록시 대상의 환경변수화(`NUXT_DEV_API_TARGET`, `/api` 접두 보존). 페이지 `/research/<job_id>`(상태 기계·배치 A/B·머리·전용 `research.css`), 계획 카드(고치기·삭제·추가·승인·취소), 진행 패널(카운터·회차 타임라인·자기점검 강조·탐색 경로), 보고서·인용칩 팝오버·원문 쪽 열기(`PdfViewer` 의 `page`), 실패 시 [재시도]. 논문 입력창 세 곳의 `+` 메뉴. 모델이 쓴 글은 `v-html` 없이 조각과 칩으로 그린다(spec D9) | `pages/research/[id].vue`·`components/research/*`·`composables/useResearch.ts`·`utils/research*.ts`·`utils/citations.ts`·`utils/slashCommand.ts` |
| 통합·배포 | 36~37 | 통합 검증, 운영 배포(§2) | — |
| 최종 리뷰 | — | 반영 12건(그중 minor 8) — §4 | — |
| 슬래시 명령 목록 | 계획 밖 | 논문 입력창에 `/` 로 시작하는 한 토큰을 치면 쓸 수 있는 명령(`/deep-research`)을 띄우고, 고르면 `+` 메뉴처럼 칩으로 바꾼다(`4212478`, 2026-09-28, spec §6-1) | `SearchPlusMenu.vue`·`utils/slashCommand.ts` |

### 1-2. §14 — 보고서 작성 대기 화면·내보내기 (2026-09-28 추가)

계기는 사용자 요청이다. 종합 단계 화면에는 "보고서 작성 중 2/5" 한 줄뿐이라 기다리기 지루했고, 보고서를 문서로 내려받고 싶다고 했다(spec §14-0).

| Task | 내용 | 주 파일 |
|---|---|---|
| 1~3 백엔드 | `assemble_report` 의 절 단위 처리를 `finalize_section` 으로, 절이 인용한 근거만 모으는 `section_evidence` 로 뗐다 — 초안과 최종본이 같은 코드로 다듬은 절을 쓴다. 종합 진행 콜백 `on_section` 에 info(소제목·다듬은 절·근거)를 싣는다. 워커는 `synth` 이벤트에 소제목·시작 시각·소요 시간·절·근거를 싣고 종합 단계 `result` 에 쌓는다. 알리는 `step` 이벤트는 미리보기를 뺀 가벼운 값이다. 완료로 닫으면 미리보기를 지우고, 실패·취소로 닫으면 멈춘 초안으로 남긴다 | `synthesizer.py`·`workers/research_tasks.py` |
| 4~5 프론트 데이터 | 절 미리보기를 `synth` 이벤트와 단계 `result` 어느 쪽으로 와도 같은 모양으로 합친다. 초안 보고서(`draftReport`)와 남은 시간(`synthEta`, 끝난 절 평균 × 남은 절) 순수 로직 | `utils/researchEvents.ts`·`utils/researchDraft.ts` |
| 6~7 초안 화면 | 보고서 작성 현황 카드(진행 막대·절 목록·경과 시계·방금 끝난 절 체크 애니메이션·항목을 누르면 초안의 그 절로 이동). 보고서 초안 모드(다 쓴 절은 최종본과 같은 부품, 쓰는 중인 절은 움직이는 회색 줄). 자동 스크롤은 하지 않고 `prefers-reduced-motion` 이면 움직임을 끈다 | `SynthProgressCard.vue`·`composables/useNow.ts`·`ReportView.vue`·`ReportSectionBody.vue`·`utils/synthCard.ts` |
| 8~10 내보내기 | 문서 모델 하나(인용은 문서에 처음 나온 순서로 번호, 참고문헌에 인용 쪽, 부록 "탐색 경로")에서 Word·PDF 를 만든다. Word 는 `docx` 를 내려받기를 누를 때만 동적 import 한다(A4·맑은 고딕·쪽 번호). PDF 는 인쇄 전용 화면을 붙여 `window.print()` 한다. 완성본은 [다운로드 ▾], 작성 중·멈춘 초안은 [초안 저장 ▾] | `utils/reportDocument.ts`·`utils/reportDocx.ts`·`ReportDownloadMenu.vue`·`ReportPrint.vue`·`composables/useReportExport.ts`·`utils/menuNav.ts` |
| 11 | 전체 확인과 spec 상태 줄 갱신(`c427f61`) | — |
| 다듬기 | 반영 21건 — §4 | — |

### 1-3. 건드리지 않은 것

- 적재 코드와 배포 설정 — `git diff a719358 d845b8b -- app/services/ingestion app/workers/tasks.py app/workers/job_runtime.py app/workers/celery_app.py app/core/config.py docker-compose.yml docker-compose.dev.yml infra` 가 비어 있다. 게이트웨이 설정(`infra/conf.d/default.conf`)도 그대로다.
- 기존 테이블 — `models/book.py`·`models/search_history.py` 변경이 없다. DB 변경은 새 테이블 `history_items` 하나이고, 기존 테이블에 ALTER·UPDATE·DELETE 가 없다(spec §10). 딥리서치 보강은 기존 JSONB 칸(`research_steps.result`·보고서 JSON)만 썼다.
- §14 는 fastapi 코드를 바꾸지 않았다 — `git diff a6fd98c d845b8b -- app` 은 `synthesizer.py`·`workers/research_tasks.py`·`models/research.py`(result 모양 주석)와 그 테스트뿐이다. 그래서 §14 배포는 워커와 nuxt 만이다(spec §14-7).

---

## 2. 운영 배포·검증

| 날짜 | 무엇 | 결과 |
|---|---|---|
| 2026-09-28 | 본편(§1~13) 배포. `nl-lib-fastapi`·`nl-lib-celery-research`·`nl-lib-celery-research-plan`·`nl-lib-nuxt` 를 컨테이너별로 Recreate 했다. 스택 업데이트는 하지 않았고 적재 워커는 건드리지 않았다(함정 16번). 그 뒤 `alembic stamp 0006_history_items` | 서버 `alembic_version` = `0006_history_items`. `history_items` 는 lifespan 의 `create_all` 이 만든다(함정 14번) |
| 같은 배포 직후 | 게이트웨이(포트 92)를 거친 요청이 502 를 냈다. nginx 가 Recreate **전** 컨테이너의 IP(`172.21.0.14`)로 보내고 있었다 | `docker exec nl-lib-gateway nginx -s reload` 로 풀었다 → 반복 함정 **20번**(`docs/ops/recurring-gotchas.md`) |
| 같은 배포 | 게이트웨이 경유 SSE | **게이트웨이 설정을 바꾸지 않고 통과했다.** 스트림 응답이 `X-Accel-Buffering: no` 헤더(`app/api/research.py`)로 nginx 버퍼링을 끄고, 15초 하트비트(`relay.subscribe` 의 `idle_timeout=15.0` → `: ping`)가 `proxy_read_timeout 120s` 안에서 연결을 잇는다. round04a 이월 "게이트웨이 경유 SSE 미검증"이 해소됐다. 계획 Task 37 Step 7 이 대비해 둔 `proxy_buffering off` 는 넣지 않았다 |
| 2026-09-28 | 기획자 시연 | 배치 A(우측 패널에 탐색 과정)가 **"덜 인터랙티브해 보인다"**는 평을 받았다. 사용자 방침: 인터랙티브함이 매우 중요하다. 전환 버튼이 있어 그날은 기본 보기를 바꾸지 않았고, 이후 화면 작업의 기준으로 삼았다(spec §7-4). §14 현황 카드의 인터랙션이 이 방침에서 나왔다 |
| 2026-09-28 | §14 배포 — `nl-lib-celery-research`·`nl-lib-nuxt` | — |
| 2026-09-29 | 사용자 확인 | 작성 중 초안 화면이 "확실히 동적으로 변했다". Word·PDF 내보내기 둘 다 정상 |

**배포한 커밋.** 정확한 커밋은 기록에 없다. spec 머리 상태 줄이 2026-09-28 17:32(`80a6734`)에 "§1~13 구현·운영 배포 완료"로 바뀌었으니 본편 배포는 그 전이다. §14 다듬기 커밋은 2026-09-29 00:14 까지 이어졌다. round04c 브랜치는 `d845b8b` 에서 땄으므로, round04c 운영 배포(2026-09-30 — 워커 → fastapi → nuxt → `nginx -s reload`)부터는 round04b 전체가 운영에 있다.

### 2-1. 운영 검증 잡 — 내용 품질 문제가 드러났다

질문 "컴퓨팅 자원에 대한 연구가 궁금해"(2026-09-29 10:20 생성). 보고서는 6절 27편이었다.

- 근거 60편 가운데 HPC 가 32편이고, 질문의 핵심인 자원 관리는 2편뿐이었다.
- 엣지 절에 의료영상 *Edge method* 처럼 같은 단어를 다른 뜻으로 쓴 논문이 실렸다.

같은 질문의 DBpia AI 답변과 비교하니 화면은 우리가 나았지만 내용은 DBpia 가 나았다. 원인은 화면이 아니라 탐색·계획 쪽이다 — 근거 상한이 잡 전체 공용(round04a 이월), 관련성 확인 없는 전부 채택, 계획 프롬프트에 "핵심 개념 안에 머물라"는 규칙 없음. **round04c(A·B·C·G)로 넘겨 착수했다.** 원인과 코드 위치는 round04c spec §1, 결과는 `round04c-완료노트.md`.

---

## 3. 테스트

| 시점 | 커밋 | 백엔드 passed | 프론트 Vitest 파일 / tests | 출처 |
|---|---|---|---|---|
| 착수 기준선 | `a719358` | 549 | (Vitest 없음) | 이 노트를 쓰며 다시 돌림 |
| 본편 계획의 기대치 | — | 728 | 14 / 158 | 본편 계획 머리(계획 작성 때 저장소 밖 사본의 실측) |
| 본편 + 최종 리뷰 + 슬래시 명령 목록 | `a6fd98c` | **745** | **16 / 277** | 백엔드는 다시 돌림, 프론트는 §14 계획의 기준선 |
| §14 계획의 기대치 | — | 770 | 20 / 348 | §14 계획 누적 기대치 |
| 라운드 끝 | `d845b8b` | **780** | **21 / 383** | 둘 다 다시 돌림. 프론트는 round04c 계획의 기준선(`738bc07` 에서 잼 — `d845b8b` 바로 다음의 문서 커밋이라 코드가 같다)과도 같다 |

- 백엔드 명령: `python -m pytest tests -q --ignore=tests/test_book_chat.py --ignore=tests/test_build_manifest.py --ignore=tests/test_loaders.py`(`app/` 에서). 제외한 3개는 로컬에 `FlagEmbedding`·`openpyxl` 이 없어 수집 단계에서 죽는다. 경고 2건(Pydantic class-based config)은 기존 것이다.
- 다시 돌린 방법: 각 커밋을 `git archive <커밋> app scripts` 로 스크래치에 꺼내 돌렸다. **`scripts/` 도 함께 꺼내야 한다** — `test_rewrite_milvus_doc_type.py` 가 `scripts/recovery/` 를 import 해서, `app/` 만 꺼내면 16건이 `ModuleNotFoundError` 로 실패한다.
- 프론트 수치: `a6fd98c` 의 16 / 277 은 §14 계획이 착수 때 잰 기준선 기록이다. `d845b8b` 의 21 / 383 은 마감 검토에서 `git archive d845b8b frontend` 사본으로 `npx vitest run` 을 다시 돌려 확인했다(파일별 건수는 교본 00-개요 §3-1 의 표와 같다).
- 타입검사·빌드: §14 Task 11 커밋(`c427f61`)이 "전체 테스트·타입검사·빌드 통과"를 적었다. 그 뒤 다듬기 21건 이후의 타입검사 결과는 커밋에 수치로 남지 않았다.

백엔드 증가분(파일별 수집 수, 세 커밋에서 다시 셈):

| 파일 | `a719358` | `a6fd98c` | `d845b8b` |
|---|---|---|---|
| `test_history_models.py` · `test_browser_id.py` · `test_history_repository.py` · `test_history_api.py` (신규) | — | 11 · 16 · 49 · 44 | 11 · 16 · 49 · 44 |
| `test_research_state.py` | 40 | 51 | 51 |
| `test_research_runner.py` | 27 | 38 | 38 |
| `test_research_synthesizer.py` | 73 | 78 | 91 |
| `test_research_tasks.py` | 43 | 70 | 92 |
| `test_research_api.py` | 44 | 66 | 66 |

기록 백엔드 테스트는 계획이 109개(11·16·48·34)를 기대했는데 120개다(저장소 +1, API +10). 늘어난 테스트는 태스크 품질 검토 반영(`55c44c7`·`e8d4446`)과 최종 리뷰 minor 반영(`5e47458` import 시각 자르기, `d4fc452` `params`·`ai` 바이트 상한)에서 더했다.

---

## 4. 리뷰

커밋 제목의 표지로 센 수다.

| 단계 | 반영 커밋 | 무엇을 고쳤나 |
|---|---|---|
| 본편 태스크별 품질 검토 | 27건 | 기록 저장소·편지함·`useHistory`(Task 17·18·20) 9건, 사이드바·페이지 URL 복원(Task 21~23) 5건, 딥리서치 리듀서·composable·진행 패널·인용칩·`+` 메뉴(Task 28·29·33·34·35) 10건, 기록 저장소·API·하트비트(Task 3·4·11) 3건. **지운 기록이 늦게 온 응답·다른 탭의 전송으로 되살아나는 경합**을 막은 반영이 5건이다(`0b987e0`·`b8bc808`·`2f028fd`·`94b8b14`, 최종 리뷰 `6b6cbb7`) |
| 본편 최종 리뷰 | 12건 (그중 minor 8) | ① 시간 상한·가드 밖 예외로 잡을 닫을 때 도는 단계의 진행 결과(`rounds`·`counters`·`sections`)를 지우지 않고 `error` 만 더한다(`7554521`). ② 업그레이드 뒤 첫 로드의 옛 `?restore=` 가 v1 이전을 기다린다(`76d8eab`). ③ 편지함 보내기를 탭 사이에서 한 번에 하나만 돌린다(`6b6cbb7` — Web Locks 가 없는 http 게이트웨이에서는 저장소 키 잠금). ④ 도서 큐레이션 요청을 끊지 않고 끝까지 받아 붙잡은 기록 id 로 저장한다(`25ce391` — 단발 POST 라 끊어도 서버 생성은 끝까지 돈다). minor 8건: 슬래시 제출 분기, `+` 메뉴 키보드, 완료 뒤 보고서를 받는 동안 본문 유지, 원문 404 와 5xx 구분, 팝오버 초점, 인용 대목 순서, import 미래 시각 자르기, 기록 API 바이트 상한 |
| §14 태스크별 품질 검토 | 6건 | 마지막 절 도중 취소로 완료 전이가 지면 종합 단계를 `failed` 로 다시 닫아 초안 보존(`05f23bf`). 초안 등장 애니메이션의 `fill` 이 팝오버를 가리던 쌓임 맥락(`a819a46`). Word 테스트가 참고문헌 줄만으로 통과하던 것(`c4ebc34`). **LLM 이 쓴 LaTeX(`\frac`)가 JSON 이스케이프로 풀려 생긴 제어문자 때문에 Word 가 파일을 열지 못하던 것**(`88806cd`). 이름 없는 `@page` 가 다른 페이지 인쇄까지 바꾸던 것(`1243044`). 인앱 브라우저처럼 `window.print()` 가 인쇄 창 없이 돌아오는 곳에서 내려받기 메뉴가 "만드는 중…"에 멈추던 것(`f5e484c`) |
| §14 다듬기 | 21건 | 완료 경로 순서를 "보고서 저장 → 단계 닫기"로(`7a27287`). 재시도가 완료되면 이전 시도의 멈춘 초안 정리(`6a6968d`). 재시도 직후 이전 초안이 잠깐 되살아나던 것(`ca764b0`). 취소 중 쓰던 절이 초안·[초안 저장]에서 빠지던 것(`cdf7b25`). 스냅샷과 구독 사이에 나간 `synth` 의 절 내용을 GET 으로 메움(`4a3cb65`). 초안 → 최종본에서 `ReportView` 를 다시 마운트하지 않아 초점·팝오버·읽던 자리 유지(`535ea4f`·`c558b81`). 강제 색 모드의 outline 회귀(`4974c42`). 근거 dict 생성 한 곳으로(`680c728`). 화면·문서가 같이 쓰는 문구 상수(`aef4049`). 그 밖에 테스트·주석·인쇄 복구 정리 |

---

## 5. 결정

- **진입은 입력창 앞 `+` 메뉴, `/deep-research` 는 키보드 단축**(spec D1·D2). `+` 가 최종 목표이고, 슬래시만으로는 일반 사용자가 모른다. 입력창은 화면 고도화와 가장 겹치는 곳이라 컴포넌트 한 줄 삽입으로 수정 면적을 줄였다. 슬래시 명령 목록은 2026-09-28 에 더했다.
- **진행 화면은 같은 탭의 `/research/<job_id>`**(D3). 주소가 곧 열쇠라 새로고침·공유·"미리 돌려둔 보고서 열기"가 주소 하나로 된다.
- **배치 A(2단)·B(쌓이는 문서)를 둘 다 지원**하고 기본값은 기획자 몫으로 뒀다(D4·§7). 2026-09-28 시연 피드백 뒤에도 기본 보기는 바꾸지 않았다. 2026-09-30 사용자가 "보고서 전 B, 보고서가 나오면 A"로 정했고(spec §7-5), 코드는 round04c 브랜치에 실렸다(`2e3d87a`).
- **기록은 서버 정본 — 새 테이블 하나만**(D5). 기존 테이블·데이터는 무변경. 소유 단위는 브라우저 ID(`sid`)이고, 로그인은 만들지 않고 `user_id` NULL 컬럼으로 자리만 뒀다(D6). 남의 기록 id 는 404, 화면은 `q` 로 재검색하는 대체 동작(D7). 브라우저 ID 는 URL 에 넣지 않는다(nginx access log).
- **딥리서치 백엔드를 보강해 이벤트로 흘리는 것은 전부 `research_steps.result` 에도 남긴다**(D8, spec §5 원칙). 라이브로 볼 때와 끝난 뒤 다시 열 때 같은 장면이 나와야 한다. round04a 가 이월한 보강 목록(단계 전이·카운터·자기점검 데이터)을 화면을 맞추는 대신 백엔드로 풀었다.
- **하트비트가 놓친 전이는 상태가 아니라 계획까지 담은 스냅샷 재전송으로 되살린다**(`c32211f`). 계획은 1초 안팎이라 계획 완료와 승인 대기가 스냅샷과 구독 사이에 함께 빠지기 쉽다. 상태만 되살리면 승인할 계획이 없는 승인 대기 화면이 된다.
- **모델이 쓴 글은 `v-html` 로 넣지 않는다**(D9). 딥리서치 CSS·컴포넌트는 별도 파일(D10) — 기획자 디자인이 나오면 그 파일만 갈아입힌다.
- **도서 큐레이션은 스트림 경합 규칙의 예외**(spec §4-7, `25ce391`). 끊어도 서버 생성이 끝까지 도므로 끊지 않고 이어받는다. 논문 요약은 스트림이라 끊으면 생성도 멈추므로 그대로 끊는다.
- **§14: 다 쓴 절부터 초안으로, 초안과 최종본은 같은 `finalize_section`**(E1·E2). 진행 표시만 늘리는 안은 끝까지 읽을 것이 없고, 토큰 스트리밍은 JSON 응답이라 중간 글을 풀기 어렵고 인용 검증 전 글이 보였다 바뀐다.
- **내보내기는 Word(.docx) + 브라우저 인쇄 PDF, 문서 모델 하나**(E3·E5). 서버·의존성 변경은 `docx` 하나이고 동적 import 다. 부록에 탐색 경로를 싣는다(E6 — 자기점검·재검색이 차별점).
- **§14 의 DB 구조 변경 없음, 백엔드 배포는 워커 하나**(E7). 초안 데이터는 기존 `research_steps.result` 에 담고, 완료로 닫으면 지워 크기가 쌓이지 않게 했다.
- **프론트 단위 테스트는 순수 로직만**(Vitest `environment: "node"`). 컴포넌트·페이지는 타입검사·빌드·수동 화면 확인으로 본다. 그래서 순수 로직을 `utils/*.ts` 로 떼는 것이 설계의 일부가 됐다.

---

## 6. 디자인 참조
해당 없음 — 디자인 트랙 미도입(`docs/design/README.md`). 화면 기획자에게 넘기는 회색조 Figma 와이어프레임의 구성은 spec §8 에 정의했다. 저장소 밖 산출물이라 이 노트에서는 확인하지 않았다.

---

## 7. 배운 점

- **컨테이너를 개별 Recreate 하면 게이트웨이가 옛 IP 로 보낸다(함정 20번).** nginx 는 upstream 호스트 이름을 설정을 읽을 때 한 번만 푼다. 함정 16번이 권하는 "바뀐 코드를 쓰는 컨테이너만 Recreate" 가 이 함정을 연다. `fastapi`·`nuxt` 를 Recreate 했으면 마지막에 `nginx -s reload` 를 한다. 같은 날 쓴 §14 배포 순서(spec §14-7·§14 계획)부터 넣었고, round04c 배포(2026-09-30)도 그 순서로 했다.
- **SSE 가 게이트웨이를 통과한 조건은 코드에 있다.** `X-Accel-Buffering: no` 와 15초 하트비트다. 하트비트 간격을 `proxy_read_timeout`(120초)보다 길게 늘리면 게이트웨이가 스트림을 끊는다. 컨테이너 안 직결 확인(round04a)으로는 둘 다 검증되지 않는다.
- **화면이 좋아도 보고서 내용은 따로 봐야 한다.** 무결성·구성 검사(round04a 함정 15번)를 통과한 보고서가 같은 질문의 외부 서비스 답변보다 내용이 못했다. 운영 잡 하나와 외부 비교로 드러났고 round04c 의 출발점이 됐다.
- **브라우저 기록을 서버 정본으로 옮기면 경합이 리뷰의 큰 몫이 된다.** 여러 탭·늦게 온 응답·편지함 재전송·메모리 모드 전환이 겹친다. "지운 기록이 되살아나는" 반영만 5건이었고, 순서 번호·잠금(Web Locks, 없으면 저장소 키 잠금)으로 막았다.
- **계획 사본 검증이 덮지 못한 곳.** 본편 계획은 사본에서 백엔드 728·프론트 158 을 돌려 보고 옮겼지만, 영역 C1 의 사이드바·페이지 통합(Task 21~25)은 계획 작성 때 실행하지 않은 코드였다(계획 머리에 명시). 그 구간(Task 21~23)에서 품질 검토 반영이 5건 나왔다.
- **LLM 출력을 문서 파일로 내보낼 때는 XML 에 쓸 수 없는 글자를 거른다.** 모델이 쓴 LaTeX 명령(`\frac`·`\beta`)의 `\f`·`\b` 가 JSON 이스케이프로 풀려 제어문자가 되고, 그 글자가 `.docx` 에 들어가면 Word 가 파일을 열지 못한다(`88806cd`). 문서 모델이 모든 글에서 걸러 Word·인쇄가 같은 글을 쓴다.
- **인쇄 CSS 의 이름 없는 `@page` 는 전역이다.** 그 CSS 가 실리는 모든 페이지의 인쇄를 바꾼다. 이름 붙은 페이지(`@page rs-report`)로 범위를 좁혔다(`1243044`). `window.print()` 가 인쇄 창 없이 돌아오는 환경(인앱 브라우저 등)도 있어 복구는 `finally` 에서 한다(`f5e484c`·`de8efe3`).
- **인터랙티브함이 화면의 기준이다.** 기획자 시연에서 정적인 2단 배치가 덜 인터랙티브하다는 평을 받았다. 이후 화면은 움직이는 진행, 눌러서 이동·펼치는 요소, 실시간 갱신을 먼저 검토한다. 단 `prefers-reduced-motion` 을 존중하고 자동 스크롤로 읽는 사람을 끌고 가지 않는다(spec §7-4).

---

## 8. 이월

**round04c 로 넘긴 것** (round04c 에서 처리 — `round04c-완료노트.md`)
- 운영 검증 잡의 내용 품질(§2-1) → A 하위질문별 근거 예산 · B 무관한 근거 걸러내기 · C 계획 프롬프트 · G 문체.
- spec §13 미확정 "하위질문별 근거 예산"(round04a 이월) → round04c A.
- 이 라운드 화면의 후속 — 배치 자동 전환(`2e3d87a`), 예시 질의는 입력창만 채움(`2d8320d`), 로컬 화면을 운영 API 에 붙이는 미리보기 설정 `frontend-prod-api`(`9bba9c4`). 모두 round04c 브랜치에 커밋됐다.

**round04a 이월 중 이 라운드에서 해소한 것**
- SSE 단계 전이 중계·진행 카운터·자기점검 강조 데이터 → `status`·`step`·`counters` 이벤트와 회차 이력 저장(§1-1 B).
- 잡 목록 API 없음 → 사이드바 기록(`history_items`)이 그 역할을 한다. `created_by` 도 채운다.
- step 시도 구분 → 화면이 이번 시도의 행으로만 멈춘 지점을 판정한다(`d489ae7`). `attempt` 컬럼은 여전히 없다.
- 게이트웨이 경유 SSE 미검증 → 통과(§2).
- 재시도 UI → [재시도]·[같은 질문으로 다시 시작].
- 원본 PDF 가 없는 논문의 원문 보기 → 404 면 "원문 파일이 없습니다", 5xx 는 다시 시도 안내(`ac3a8a7`).

**남은 것 — 화면·기록**
- 사이드바 "더 보기"(`next_cursor` UI) 없음 — 종류마다 최근 30건만 읽는다(본편 계획 "다루지 않는 것").
- 화면 기획자 결정 중 남은 것 — 진행 패널 폭(개발 기본값 `--rs-side-width: 17rem`), 자기점검 강조 정도(펄스 2회). 기본 보기·전환 버튼·자동 전환 폭(1200px)은 2026-09-30 결정(spec §7-5).
- 보고서에 PDF 유무(`has_pdf`)를 미리 실을지 — 지금은 누를 때 404 를 안내로 처리한다(spec §13).
- 큐 순번 표시 없음 — 전용 워커는 실행이 한 번에 한 잡이라 두 번째 잡은 "앞선 연구가 끝나면 시작합니다"로 기다린다.
- `BookChat.vue` 의 쪽수 표시가 0부터 센 원시값(`p.{{ src.page_start }}`)이라 한 쪽 어긋난다 — 불일치로만 기록(본편 계획).
- spec §11 범위 밖 — 로그인·사용자 계정, 채팅 대화 기록의 서버 저장, 기존 `search_history` 정리와 `GET /api/books/history/{session_id}` 폐기.
- 본편 계획 "알려진 미확정" — 탐색부터 다시 도는 재시도는 첫 회차 전까지 스냅샷 카운터가 이전 실행 값일 수 있다(첫 `counters` 이벤트가 덮는다). 10분 중복 병합은 서버·브라우저 시계를 비교한다. `legacy_history_id` 는 v1 id 만으로 만든다.

**리뷰 minor 중 남긴 것** — 태스크별 검토가 적은 minor 가운데 아래는 반영하지 않았다. `dev`(`3dfeb45`) 코드에서 다시 확인했다.
- `README.md` §5 의 frontend 파일 트리에 지운 `ChatHistory.vue` 가 남아 있다(391행).
- `search-classic.vue` 를 지운 뒤 호출부가 0 인 컴포넌트 — `components/SearchInput.vue`·`TopResult.vue`·`CategoryAccordion.vue`.
- `nuxt.config.ts` 의 `process.env.NUXT_DEV_API_TARGET ?? …` 는 빈 문자열을 통과시킨다 — 빈 값으로 띄우면 프록시 대상이 `""` 가 된다.
- `utils/historyRoute.ts` 의 `activeIdFor` 가 경로를 `decodeURIComponent` 로 풀면서 예외를 잡지 않는다 — 깨진 `%` 표기 주소에서 `URIError`.
- `utils/citations.ts` 의 칩 라벨이 저자 꼬리 "외 N인"만 떼고 "외 N명"은 떼지 못한다.
- `schemas/history.py` 의 `_research_needs_ref` 가 `ref_id` 의 존재만 보고 형식(UUID)은 보지 않는다. 저장소가 조회 때 방어한다.
- 상태 알림 `_announce` 가 `api/research.py`·`workers/research_tasks.py` 에 같은 모양으로 두 벌 있다.

**round04a 이월 중 그대로인 것** — 이 라운드는 적재 코드·compose·`infra`·`api/admin.py` 를 바꾸지 않았다(§1-3). round04a 완료노트 §8 의 다음 항목은 그대로 유효하다.
- 대표 논문 요약의 오배정 가능성, 본문 심층 읽기(`deep_read_top_n`) 미구현, 탐색 중 시간 초과의 부분 체크포인트 없음.
- 재개(retry)·종합 중 취소·계획 중 취소의 라이브 검증 — 이 라운드에서도 기록이 없다.
- 운영·적재·보안 — 적재 복구 경로 이중 실행과 손상 의심 논문 2건, Portainer 스택과 저장소 compose 불일치, 스키마를 만드는 세 경로, Redis 무인증 호스트 노출, `app/api/admin.py` Milvus expression injection.

**문서**
- 계획 문서의 체크박스를 갱신하지 않았다(본편 237개·§14 83개가 모두 `- [ ]` — 코드 블록 밖 체크박스 줄을 셌다).
- ~~spec 머리 상태 줄이 "§14 … 구현 완료(운영 배포 전)"로 남아 있다~~ — **해소(2026-10-01, 마감 문서 검토).** §14 는 2026-09-28 에 배포됐으므로 "구현·운영 배포 완료(2026-09-28)"로 고쳤다. 같은 이유로 round04a spec 머리의 "프론트 미착수(round04b)"도 고쳤다.

---

## 9. 다음 라운드 진입점

- **round05a — 논문 상세 재구현**(UI 고도화 기능 명세서 03·S6: 돌아가기·주소·보던 위치 복원). 브랜치 `feat/round05a-paper-detail`(`dev` `3dfeb45` 에서 분기), 설계 `docs/superpowers/specs/2026-10-01-round05a-paper-detail-design.md`(그 브랜치 `d7f7e95`). 화면은 인터랙티브함이 최우선이다(spec §7-4). 이 라운드의 URL 규칙(`utils/historyRoute.ts` — 상세로 갈 때 `h` 를 넘겨 뒤로가기가 복원되게)이 돌아가기·주소 복원의 출발점이다.
- **딥리서치 품질의 다음 과제**는 round04c 완료노트에 있다 — 제외 기준을 "원 질문 주제와 명백히 무관한 것만"으로 좁히기(round04c spec §11-4), 계획 프롬프트 재검토. 그 뒤 D(핵심 요약·주제 종합)·E(이어서 물어보기)·F(화면 참고문헌).
- **적재 현황(2026-09-29)** — `kci-full-236k` 47%: done 111,658 / pending 123,979 / failed 782. 항목 번호(옛 논문) 순으로 돌아 딥리서치 코퍼스가 2013년까지다. 하루 약 5,200건 → 10월 23일쯤 완료 예상(목표 10월 28일). 최신순 재배열은 하지 않기로 했다. 추가 수집(메타 없는 PDF 28,074편, 연도별 1만 건 상한 뒤 나머지 — 수집기가 KCI 검색 200쪽 상한을 봇 탐지로 오인)과 모델 교체(Qwen3.6-35B-A3B-FP8 로 OCR·텍스트 통합 검토)는 적재가 끝난 뒤다.
- **라운드 종료** — 완료노트·교본을 갖췄다. `/round-finish` 로 `dev→main` 머지 + `origin` push.
- 배포할 때는 컨테이너별 Recreate(스택 업데이트 금지, 함정 16번)와 끝의 `nginx -s reload`(함정 20번)를 지킨다.

---

## 상태
- [x] code-reviewer 정적 리뷰 통과 — 태스크별 품질 검토 33건·본편 최종 리뷰 12건·§14 다듬기 21건 반영(§4). 반영하지 않은 minor 는 §8.
- [x] 테스트 green — 백엔드 780 passed(`d845b8b`, 이 노트를 쓰며 다시 돌림, 로컬 미설치 패키지로 수집이 죽는 3개 모듈 제외), 프론트 Vitest 21파일 / 383(`d845b8b` 사본에서 다시 돌림)
- [x] 수동 스모크 — 운영 배포 뒤 사용자 확인(2026-09-29: 초안 화면 동적·Word·PDF 정상), 운영 검증 잡(§2-1)
- [x] 문서 갱신 — 완료노트(이 문서)·교본 `docs/guides/round04b/` 6챕터(`7dbd962`)·`00_status`·함정 20번·spec 상태 줄. 계획 체크박스는 갱신하지 않았다(§8 문서)
- [x] `dev` 머지 승인 — 2026-10-01(`9b776d2`)
- [x] `dev→main` 머지 + push — 2026-10-01
