# round06c 완료노트

날짜: 2026-10-12 (계획 2026-10-08 · 구현·리뷰 2026-10-12 · `dev` 머지·운영 배포·두 갈래 재판정은 §5)
브랜치: `feat/round06c-query-broadening` (worktree `.worktrees/round06c`, dev `4b6783b` 에서 분기 · 커밋 23개(이 문서 커밋 전) · 리뷰를 마친 커밋 `5f11e21`)
spec: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` (D25, §12-2·§12-5·§12-6·§12-7, Q4·Q9)
plan: `docs/superpowers/plans/2026-10-08-round06c-query-broadening.md` (Task 0 · C1~C7 · V1~V3 · Z1~Z9, 정함 1~22)
교본: 대회 뒤 round06 한 권(D13) — 06c 는 그 책의 한 장이 된다

> 한 줄 요약: 딥리서치 계획 직전에 gemma 한 번으로 시작 질문을 한 문장으로 넓히고 범위 용어를 뽑아(스위치 `broaden`) 계획 프롬프트는 그대로 둔 채 입력만 넓혔고, 검색어에 범위 용어를 합성하고 '국내 학술논문에서'를 떼게 했다(스위치 `query_context`). 회차마다 자기점검 전에 탐색 후보 목록 이벤트 `candidates` 를 낸다(06d '검토 중' 더미의 재료). 두 스위치는 기본 0 으로 배포하고 배포 당일 두 갈래 판정으로 기본값을 정한다(§5). 스키마 변경은 없다.

---

## 1. 왜 했나

- **일반 틀 하위질문** — 개념 하나짜리 짧은 질문은 계획 프롬프트의 측면 목록(개념·정의, 방법·기법, 적용 분야, 성과·평가, 한계·과제)을 그대로 옮긴다. 06b 계획 30개 중 약 25개가 그랬다(spec §12-2). 논문 상세 [이 논문으로 딥리서치] 질문은 실제 제목·키워드·측면이 있어 잘 나뉜다 — 그 일을 계획 전에 자동으로 한다(회의 결정 ⑥, D25).
- **검색어의 동음이의** — 06b 재판정에서 남은 무관은 하위질문 문장이 아니라 검색어가 데려왔다('컴퓨팅' 사고력·무선 자원할당 — 06b 이월 §7-10·§7-11). D18 의 부작용으로 하위질문에 붙은 '국내 학술논문에서' 도 검색어에 섞였다(§7-12). 검색어에 범위 용어를 합성한다(회의 결정 ⑦, 사용자 결정 2026-10-08 "06c에 검색어 합성 넣어").
- **탐색 후보 목록(Q9)** — 회차마다 검토하는 후보를 화면이 '검토 중' 으로 먼저 세우게, runner 가 이벤트를 낸다(화면은 06d).

---

## 2. 한 일

| 영역 | 한 것 |
|---|---|
| 낱말 맞추기 | `app/services/research/terms.py` — `tokens`(어절 나누기 — NFKC·casefold·문장부호를 공백으로, 넓히기의 한 글자 어절 검사도 이것을 쓴다)·`content_words`(조사 하나 떼기·질문 꼴 낱말과 조사만 남은 어절 제외)·`contains`(공백 무시 부분 문자열, 아니면 낱말이 순서대로)·`compose_query`, 상수 `PARTICLES`·`QUESTION_WORDS`·`QUERY_FILLERS`. 표준 라이브러리만 쓴다. 공용 고정 예제 `frontend/tests/fixtures/term_checks.json`(score.py 복사본·06e 가 같은 규칙) |
| 넓히기 | `research_frame.yaml`(예시 없음)·`framing.py` — gemma 1회·20초(`BROADEN_TIMEOUT`), 원 질문 낱말 보존 검사(내용어는 `contains`, 한 글자 어절은 어절 경계로), 원 질문에 대조할 낱말이 없으면 넓히지 않음, 입력 이름표(`질문:`) 떼기, 범위 용어 정리(30자·4개), `FRAME_FAILURES`·빈 응답·검사 실패면 원 질문(물러날 때마다 `[framing]` 경고 한 줄). 계획 태스크가 `broaden` 1 이면 계획 전에 넓히고 `{question_used, terms}` 를 먼저 알린다. plan step 결과 `{subquestions, question_used, terms, elapsed_ms}` |
| 검색어 합성 | 실행 태스크가 마지막 plan step 의 `terms` 를 `ResearchState.terms`·체크포인트에 싣는다(`_plan_terms`, 스위치와 무관). runner `_search_query` 가 `query_context` 1 이면 첫 검색어·재검색 제안에 없는 범위 용어를 붙이고 '국내 학술논문에서' 를 뗀다 — `subq.queries`·critic `tried_queries`·회차 기록이 모두 실제로 보낸 글. 0 이면 공백까지 글자 그대로 |
| 탐색 후보 이벤트 | `candidates {subq_idx, round, papers}` — 회차마다 `counters` 뒤·자기점검 전에 한 번(빈 목록도), 스위치와 무관, 저장하지 않음. `papers` 는 이번에 이은 근거 전부(`linked` 순서)라 이 하위질문이 이미 채택한 논문이 다시 걸리면 후보에 다시 든다 — 06d 가 `cnts_id` 로 기존 채택과의 겹침을 처리한다 |
| 스위치 | 잡 파라미터 `broaden`·`query_context`(int 0~1, 기본 0 — `critic_scope` 와 같은 검증 경로). 기본값을 단언하는 테스트는 `test_query_switches_are_off_by_default`·`test_query_switches_are_saved_off_unless_asked` 둘뿐이다(Task Z7 이 이 둘만 고친다) |
| 판정 도구 | `run_pair.py --param0·--param·--plan own`(own 은 두 계획을 먼저 세운 뒤 승인, 잡 만들기 422 면 멈춤), 대조군 `questions_control.json`, `score.py` 계획 지표(넓힌 질문·일반 틀·근거 0편·insufficient·계획 시간)·`--plan-only`·`contains` 복사본, README '06c 재판정' 절차 |
| 화면 한 줄 | `StepResult` 선택 칸 셋, `questionUsedFromSteps`·`understoodLine`, PlanCard 선택 prop `questionUsed`(`[id].vue` 바인딩은 06d — 10/17~18 nuxt 배포) |

스키마 변경 없음 — 바뀐 모양은 plan step result(JSONB)·잡 파라미터·체크포인트 안이다. `planner.py`·`research_plan.yaml`·`parse_plan`·계획 고정 테스트·`job.plan`·승인 API·critic·explorer·synthesizer·검색 파이프라인·critic/종합 프롬프트(sha256)·06d·06e 파일·compose·인프라는 그대로다.

---

## 3. 리뷰

작업마다 구현 → spec 준수 → 품질 검토를 돌렸고, 끝에 브랜치 전체 최종 리뷰(4영역 — 백엔드 핵심·워커·테스트·판정 도구와 화면)를 돌렸다. 최종 리뷰는 Important 1 · Minor 14 — 15건을 수정 6커밋(`8ede41e`·`bcdeead`·`8e562d6`·`5ba84a0`·`1b46487`·`5f11e21`)으로 반영했고, 그 가운데 한 건(질문 꼴 낱말)은 일부만 반영하고 나머지를 이월했다(아래). 넘긴 것은 §7.

- **작업별(2026-10-12)** — Task C1~C7·V1~V3 을 구현 → spec 준수 → 품질 검토로 돌렸다. 계획의 코드는 실제 코드와 맞아 글자 그대로 들어갔고, 품질 검토로 고친 것이 6커밋이다 — 공용 고정 예제에 '다문화 가정 아동의 언어 발달'/'다문화가정 언어' 사례(공백 지운 글에서 낱말을 차례로 찾는지 가르는 사례가 없었다 — `d24101b`), 빈 문장 검사를 내용어 없는 질문으로 고정(`0c17142`), 한 글자 명사(암·뇌·법)도 낱말 검사가 지킴(`b33462d`), 한 글자는 부분 문자열이 아니라 어절 경계로 대조('방법'의 '법', '암호화'의 '암', '뇌물'의 '뇌'에 맞지 않게 — `77ee069`, 계획 문서 `a43ffb5`), `candidates` 의 `papers` 가 `linked` 전부라는 결정을 이미 채택한 논문이 다시 걸리는 사례로 고정(`0addb8a` — 06d 의 겹침 처리를 계획 경계·spec 맞춤 ⑪-3 에 적음), 원 질문 쪽 정규화를 화면 함수 테스트가 고정(`479b176`).
- **최종 리뷰(2026-10-12)** — 15건(백엔드 핵심 3 · 워커 2 · 테스트 8 · 판정 도구와 화면 2). Important 1: `parse_frame` 이 응답 `terms` 를 `clean_terms` 로 정리하는 연결을 어느 테스트도 고정하지 않았다 — 빠지면 30자 넘는 문장·중복·전각 글자가 그대로 검색어에 붙는다(`8ede41e` — `parse_frame`·`frame_question` 두 경로에 정리 전 용어를 주는 테스트). Minor 14 — 백엔드 핵심: 대조할 낱말이 없는 질문('연구가 궁금해')에 지어낸 주제가 지나가던 것을 넓히지 않게(`8ede41e`), 어절 나누기를 `terms.tokens` 한 곳에(`bcdeead`), `QUESTION_WORDS` 에 처음 값의 활용 꼴 여덟(`8e562d6` — 요청 꼴 질문이 늘 원문으로 물러나지 않게). 워커(문서만): plan step result 의 실패 모양 주석, 계획 롤백 3 의 'stage `planned` 로 실패한 잡은 옛 워커에서 다시 시도해도 실패'(`5f11e21`). 테스트: `elapsed_ms` 가 넓히기 + 계획인지 가짜 시계로, `compose_query` 의 빈 용어·용어 공백·멱등, 스위치 0 의 '글자 그대로'를 공백까지(계획 입력·`question_used`·첫 검색어·재검색 제안), 테스트 이름 하나(`5ba84a0`), 띄어 쓴 조사('노인 의 우울') 사례(`8ede41e`), run_pair 의 플래그 없는 기본값(`1b46487`), 계획 Task Z7 Step 2 의 기대값 K 640 → 680(`5f11e21`). 판정 도구: `--plan own` 은 두 계획을 먼저 세운 뒤 승인(갈래 1 의 계획 시간을 갈래 0 실행과 겹치지 않게 잰다), 잡 만들기 422 면 남은 질문을 멈춤(`1b46487`). 리뷰어는 작업 사본 변형으로 빈틈을 확인했고, 반영한 테스트는 모두 리뷰가 든 변형에서 떨어지는 것을 확인했다. 리뷰어가 Z7 을 미리 돌려 본 결과 두 스위치를 모두·하나씩 켠 세 변형에서 떨어지는 테스트는 기본값을 단언하는 둘뿐이었고 10초 넘는 테스트도 없었다.
- **고치지 않은 것**
  - **질문 꼴 낱말의 새 낱말** — 리뷰가 든 '논문' 과 띄어 쓴 꼴('알려 주세요')은 더하지 않았다. spec 처음 값의 활용 꼴만 더해 보고된 실패는 고치되, 무엇을 질문 꼴 낱말로 볼지 새로 정하지 않는다 — '논문' 은 연구 주제일 수 있고('논문 작성 방법') 띄어 쓴 꼴은 변형이 끝없다. 운영 질문을 모은 뒤 정한다(§7-3).
  - **작업별 보고가 남긴 것** — runner `_paper_brief` 의 설명 주석이 아직 '뺀 논문의 서지 요약' 이다(이 함수는 `adopted_papers`·`candidates` 에도 쓴다) — 주석뿐이라 §7-7. score.py 가 `sys.stdout.reconfigure(errors="replace")` 를 불러 같은 pytest 프로세스 안에서 캡처 스트림의 errors 설정이 바뀐 채 남는다 — 기능과 전체 회귀에 영향이 없어 그대로 둔다.
- **실행 메모** — 계획의 절대 기대값(백엔드 전체 2381·2408 …)은 작업별 품질 검토가 테스트를 더해 뒤 Task 로 갈수록 최대 21 컸다. 모두 계획의 "Task 앞 수 + N" 상대값으로는 맞았다. 계획의 `git add` 한 줄 여러 경로는 파일마다 따로 했다(결과는 같다).

---

## 4. 검증

- 백엔드 pytest `5 failed, 2491 passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 Task 0 기준선과 같은 로컬 의존성 파일(test_build_manifest 2·test_loaders 3·test_book_chat 수집). 기준선 2327 + 164(계획 124 · 작업별 품질 검토 21 · 최종 리뷰 19).
- 06c 묶음 열두 파일 817 passed(기준선 열 파일 653 — 계획의 777 에 작업별 21·최종 리뷰 19). Task Z7 의 열 파일 묶음 K = 680.
- 프론트 vitest 40파일 739 · `nuxi typecheck` 오류 0 · `npm run build` 완료(2026-10-12, dev 머지 전 — 기준선 40파일 732).
- 고친 파일 23개 밖은 그대로(계획 프롬프트·planner·계획 고정 테스트·critic/종합 프롬프트·API·critic·explorer·synthesizer·검색 파이프라인·06d·06e 파일·마이그레이션·인프라·compose diff 없음), 프롬프트에 예시·`guided_*` 없음, `except Exception` 없음, `terms.py` import 는 표준 라이브러리만, 커밋 트레일러 0.

---

## 5. `dev` 머지·운영 배포·재판정

배포 전 — 계획 Task Z3~Z7 의 결과를 Task Z8 의 기록 브랜치에서 채운다. 롤백하게 되면 계획 끝 '롤백' 절을 따른다 — 06c 배포 동안 만들어 failed 로 끝난 잡 중 stage `planned` 인 것은 옛 워커에서 [다시 시도]해도 곧바로 실패하므로(`broaden` 이 '알 수 없는 파라미터', `explored` 는 재개된다) 새로 만들게 안내한다. 반복 함정(`docs/ops/recurring-gotchas.md`)은 이번에 더하지 않았다 — 운영 전이라 라이브에서만 드러난 것이 아직 없다. Task Z8 이 운영 확인·판정의 관찰을 보고 다시 판단한다(예: gemma 가 넓힌 문장에서 원 질문 낱말을 자주 바꿔 원문으로 떨어지면 함정 26 에 덧붙인다).

---

## 6. 결정

| # | 결정 |
|---|---|
| 정함 1 | 넓히기는 새 모듈 `framing.py` — `planner.py` 는 한 글자도 고치지 않는다(계획 태스크가 함수 안에서 import) |
| 정함 2 | 프롬프트 `research_frame.yaml` — plain·max_tokens 600·temperature 0.2, 변수 `question`, 출력 `{"question", "terms"}`, 예시 없음 |
| 정함 3 | 탐색 후보 이벤트 이름 `candidates`, 하위질문 키 `subq_idx`(runner 의 다른 이벤트와 같은 키 — spec §12-2 를 계획 확정 전에 맞춤) |
| 정함 4 | `candidates` 는 회차마다 늘 한 번(빈 목록도) — `search` → `counters` → `candidates` → `critique`. 기존 순서 테스트 하나(`test_counters_follow_each_search`)의 기대를 고쳤다 |
| 정함 5 | plan step 결과에 `elapsed_ms`(넓히기 + 계획) |
| 정함 6 | 중간 알림은 `broaden` 1 일 때만, 넓히기 결과와 무관하게 한 번 |
| 정함 7 | `content_words` — 문장부호를 공백으로, 조사만 남은 어절은 내용어가 아니다(spec 정의에 더함 — §12-2 를 맞췄다). `QUESTION_WORDS` 에 처음 값의 활용 꼴 여덟(관해·관하여·대해·대하여·궁금해요·알려주세요·찾아주세요·연구들)을 더했다(최종 리뷰 — 요청 꼴 질문이 넓히기에서 늘 원문으로 물러나지 않게) |
| 정함 8 | `contains` 는 spec 글자 그대로(06e 제목 일치가 같은 함수) |
| 정함 9 | 범위 용어 정리(문자열·NFKC·공백·빈 것과 30자 초과 버림·casefold 중복 제거·4개), 넓힌 질문이 비었거나 500자 초과면 원문. 넓힌 질문은 맨 앞 입력 이름표(`질문:`·`질문：`)를 떼고 본다(이름표째 옮긴 답이 낱말 검사를 통과하지 않게 — 함정 26). 낱말 검사는 `content_words` 에 더해 원 질문의 한 글자 어절(암·뇌·법 — 2자 바닥에 걸린다. 및·등·왜·더·수·것 같은 잇는 말은 빼고)도 본다 — 한 글자는 부분 문자열이 아니라 어절 경계로(그 글자이거나 그 글자 + 조사 하나, '방법'의 '법'은 아니다)(C3 품질 검토 — '암 연구가 궁금해'에 지어낸 주제가 지나가지 않게). 원 질문에 대조할 낱말(내용어·한 글자 어절)이 하나도 없으면('연구가 궁금해') 넓히지 않는다(최종 리뷰 — 검사할 수 없는 질문에 지어낸 주제가 지나가지 않게). 어절 나누기는 `terms.tokens` 한 곳 |
| 정함 10 | 넓히기가 원문으로 물러나는 범위 = `FRAME_FAILURES`(전송·상태·JSON·응답 모양 오류)·빈 응답·검사 실패, 그 밖의 예외는 계획 실패(함정 19 — spec 의 '잡을 실패시키지 않는다' 를 맞췄다) |
| 정함 11 | 검색어 합성은 runner `_search_query` 한 곳(첫 검색어·재검색 제안), `_next_query` 그대로 |
| 정함 12 | `QUERY_FILLERS`·`compose_query` 도 `terms.py` — 붙일지는 지금까지의 글(이어 붙인 용어 포함)에 `contains` 인지로, 군더더기만 남으면 원문, 빈 용어는 건너뜀(두 번 거쳐도 같다 — 군더더기만으로 된 글은 예외. spec §12-2 를 맞췄다) |
| 정함 13 | `state.terms` 는 스위치와 무관하게 늘 담고, 검색어에는 `query_context` 1 일 때만 |
| 정함 14 | score.py 는 `contains` 만 복사(공용 고정 예제로 묶음) |
| 정함 15 | 공용 고정 예제 `frontend/tests/fixtures/term_checks.json` |
| 정함 16 | run_pair `--param0`·`--param`·`--plan shared\|own` — 기본값은 06c 전 동작 그대로 |
| 정함 17 | score `--plan-only`(대조군 — 라벨 없이 계획 지표) |
| 정함 18 | 대조군 질문 파일 `questions_control.json`(소장 논문 제목 2개, 논문 버튼 꼴) — 고정 5문항에 섞지 않는다 |
| 정함 19 | 계획 p50 5초는 판정 지표로만, 코드 상한 `BROADEN_TIMEOUT = 20` |
| 정함 20 | 스위치를 나눠 판정 — `query_context` = shared + 갈래 1 `{broaden 1, query_context 1}`, `broaden` = own + 갈래 1 `{broaden 1, query_context 0}` |
| 정함 21 | 화면 판단은 순수 함수 `questionUsedFromSteps`·`understoodLine` 의 vitest, PlanCard 는 typecheck·build(node 환경 vitest — spec 의 '그리기·숨기기 vitest' 를 맞췄다) |
| 정함 22 | PlanCard 는 새 CSS 없이 `rs-muted`, `rs-plan__understood` 는 규칙 없는 고리(06d 도 규칙을 더하지 않는다) |

§12-11 '계획에서 정할 것' — 06c 에 걸린 항목은 없다(10항목 모두 06d·06e). 선택 항목 '연구 맥락을 반영한 딥리드 첫 화면'은 하지 않았다. 열린 질문 Q4(기본값)는 §5 의 판정으로 닫는다.

---

## 디자인 참조

해당 없음 — 디자인 트랙 미도입. 06c 의 화면 변경은 PlanCard 머리 한 줄(`rs-muted` 재사용)뿐이고 `rs-plan__understood` 는 규칙 없는 고리다(06d 도 CSS 를 더하지 않는다).

---

## 7. 이월

1. **넓힌 문장을 고쳐 같은 잡에서 다시 계획하기** — 대회 뒤(사용자 "고도화로 냅두고", spec §12-9). `awaiting_approval → created` 전이와 `_plan_known` 처리가 필요하다.
2. **범위 용어를 critic·핵심 개념에 공급** — 대회 뒤(spec §12-9 구조화 해석). 06c 의 `terms` 는 검색어에만 쓴다.
3. **`QUESTION_WORDS`·`QUERY_FILLERS` 를 운영 질문으로 늘릴지** — `QUESTION_WORDS` 는 spec 의 처음 값에 그 활용 꼴 여덟을 더한 것(최종 리뷰), `QUERY_FILLERS` 는 처음 값 그대로다. 띄어 쓴 꼴('알려 주세요')·'논문' 같은 새 낱말과 하위질문 군더더기는 운영 질문을 모아 본 뒤 정한다 — Z5·Z6 운영 확인에서 '[framing] 넓힌 질문이 원 질문 낱말' 줄의 빠진 낱말 목록을 본다(목록에 요청 말만 있으면 더할 후보다).
4. **넓히기가 원 질문 낱말 검사에서 떨어진 비율** — 물러난 잡 수는 `grep -c '\[framing\]'`(물러날 때마다 정확히 한 줄), 그 가운데 낱말 검사에서 떨어진 수는 `grep -c '\[framing\] 넓힌 질문이 원 질문 낱말'` 로 센다(§5-4 에 판정 잡의 두 수를 적는다).
5. **화면 한 줄의 `[id].vue` 바인딩·`candidates` 의 화면** — 06d(10/17~18 nuxt 배포).
6. **06e 의 제목 일치** — 06c 머지 뒤 `services.research.terms.contains` 를 쓴다(06e).
7. **runner `_paper_brief` 설명 주석 넓히기** — 지금 글은 '뺀 논문의 서지 요약 — 회차 기록(excluded_papers)에 남는다' 뿐인데 `adopted_papers`·`candidates` 도 이 함수를 쓴다. 동작과 무관한 주석이라 다음에 `runner.py` 를 고칠 때 함께 고친다(Task C7 보고).

---

## 8. 다음 라운드 진입점

- **06c 배포·판정(10/13~14)** — 계획 Task Z3~Z8. 운영 배포가 끝나면 06d·06e 의 dev 머지 문이 열린다(§12-6).
- **06e·06d(10/17~18 배포)** — 06c 기본값 커밋(판정 결과)을 그 배포에 싣는다. 배포 뒤 06c 확인은 계획 Task Z9.

---

## 상태
- [x] 정적 리뷰 통과(발견 사항 반영 완료) — 작업별 · 최종 4영역
- [x] 테스트 green — 백엔드 2491 · vitest 739 · typecheck 0 · build
- [ ] 수동 스모크 확인 — 운영 처음부터 끝까지 1회(§5)
- [ ] 두 갈래 재판정·기본값 결정(Q4 — §5)
- [ ] 문서 갱신 — `00_status` · spec · `scripts/research_eval/README.md` 06c 재판정 결과 (교본은 대회 뒤 round06 한 권 — D13)
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push 완료
