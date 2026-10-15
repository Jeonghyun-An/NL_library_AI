# round06e 완료노트

날짜: 2026-10-13 (계획 2026-10-08 · 구현·리뷰 2026-10-12~13 · `dev` 머지·운영 배포·처음부터 끝까지 1회는 §5)
브랜치: `feat/round06e-assistant-auto-report` (worktree `.worktrees/round06e`, dev `d261476` 에서 분기 · 최종 리뷰 전에 dev `0802e27`(06d 진행 화면·입구 + round08 다크 테마)을 받음 `f9914e9` · 커밋 60개(첫 부모 기준, 받기 merge 1 포함, 이 문서 커밋 전) · 리뷰를 마친 커밋 `afafa0a`)
spec: `docs/superpowers/specs/2026-10-02-round06-paper-agent-design.md` (D20·D21·D23·D24·D27·D26 의 N, §12-4·§12-5·§12-6·§12-7·§12-11, Q1(보고서 화면에도 — 2026-10-11 사용자 확인)·Q2·Q3 기본값)
plan: `docs/superpowers/plans/2026-10-08-round06e-assistant-auto-report.md` (Task 0 · A1~A5 · X1~X5 · R1~R6 · S1~S4 · K1~K9 · H1~H3 · Z1~Z7, 정함 1~31)
교본: 대회 뒤 round06 한 권(D13) — 06e 는 그 책의 한 장이 된다

> 한 줄 요약: 이어간 연구의 마지막 단계를 [보고서 만들기] 한 번으로 끝까지 가게 했다 — 목차가 자동으로 확정되고 선행연구 묶음·연구 공백 절이 문서 순서대로 차오르며, 화면 머리에 크게 보이는 진행 막대(사용자 Q1 답을 보고서 화면에도 — 2026-10-11 확인)·머리 목차·문서 자리 1~6·'검토할 곳'이 선다. Word 기본은 모든 문단·워터마크 없음과 공개 부록의 문단 상태별 개수다. 단계 이름을 '제목 고르기'·'참고문헌 선택하기'·'보고서'로 바꾸고, 논문 제목·보고서 인용 칩을 누르면 오른쪽에 딥리드·인용 근거(모델이 본 원문 대목 하이라이트)가 열린다. 제목 고르기는 후보 키워드 칩(LLM 후보 + 채택 논문 키워드)을 고르면 그 말이 박힌 카드 제목이 온다. 주제 카드 근거 칩은 제1저자 전체 이름 연도로, 기록 목록은 kind 별 total 을 싣고(읽는 화면이 없어 머지 전 결정 — '확인할 것' 1), 보고서를 PDF 로도 내려받는다. 워커·fastapi·nuxt — 스키마 변경은 없다. 논문 키워드 채움률 측정(Task Z1 — 사용자 서버 실행)은 아직이다.

---

## 1. 왜 했나

- **보고서 자동 산출(D20 — 회의 결정 ①, '최우선')** — 06b 의 마지막 단계는 목차 승인 → 절마다 [이 절 쓰기] → 문단 수락이라 시연에서 단계가 길었다. 회의 뒤 결정: 한 번 누르면 인용 달린 보고서가 끝까지 나오고, 수락·고치기는 선택 기능으로 남긴다. 수락 관문이 빠지므로 연구 공백 문단의 '확인했다' 단정(06b 이월 §7-13)을 함께 고쳤다.
- **큰 진행 막대(Q1)** — 사용자 "현재 절 작성 중에 보여지는 커다란 프로그레스바 필요, 예시 막대는 너무 작음"(10-08). spec 은 06d 딥리서치 진행 화면에만 적었지만 자동 보고서도 '절을 차례로 쓰는 중'인 화면이라 같은 크기 규칙의 막대를 두었다 — 사용자 확인 "보고서 화면에도 넣으라고 한 것이 맞아"(2026-10-11).
- **내보내기 기본값(D21)** — 수락이 선택이 되면 06b 기본 Word(수락 문단만)는 모든 절이 빈 채로 나간다. 전부 싣고 부록으로 밝힌다.
- **참고문헌 선택하기·오른쪽 딥리드·인용 근거(D24 — 회의 결정 ⑤)** — 논문을 읽으러 상세 화면으로 떠나지 않고 그 자리에서 대화하고, 보고서 인용을 누르면 모델이 본 원문 대목을 바로 본다(저장된 대목을 보이는 것이 리랭커 점수보다 정직하고 싸다).
- **제목 고르기(D23 — 회의 결정 ③)** — 06b 핵심 개념에 일반어('측정 및 평가 · 연구 분야 · 발전 방향')가 섞였고 카드 제목이 그 개념을 쓰지 않았다. 고른 키워드가 제목에 박혀 오게 했다.
- **근거 칩 표기(D27 — 회의 결정 ④, 06b 이월 §7-14)** — '최 2018'(한글 이름 첫 글자·복성 잘림). Q3 답이 없어 주제 카드 칩만 고쳤다(S).
- **기록 total(D26 의 N)** — 06d 사이드바 '모두 보기 (N)' 의 재료로 계획했다. 06d 가 2026-10-12~13 사용자 결정으로 '모두 보기 (N)' 을 만들지 않아 지금은 읽는 화면이 없다('확인할 것' 1).

---

## 2. 한 일

| 파트 | 한 것 |
|---|---|
| A 보고서 자동 산출 | 목차 반영이 질문이 있으면 승인 목차(`auto`)로 저장, ProposalView 의 절 키별 마지막 section 생성(`section_gens`), 근거 없음 409 에 code, 자동 산출 판정 순수 함수(`autoChainOn`·`autoTargets`·`nextAutoSection`·`docToc`·`reportBar`), 절 연쇄 `useAutoReport`(앞 응답 뒤 다음 키·근거 없음 건너뜀·오류면 멈추고 [이어서 쓰기]), 보고서 화면(큰 진행 막대·머리 목차·문서 자리 1~6·[목차 고치기] 뒤로 접기·[보고서 만들기]) |
| X 보고서 마무리·내보내기 | `outline.background`(상한 2000)·절 basis 의 연구 질문(바뀌면 '다시 맞춤 필요'), 연구 공백 단정 다듬기(`GAP_CLAIM_*` — 코퍼스 범위 문장만, 결핍 말 바로 앞일 때만·결핍 말의 부정과 '없' 합성어는 그대로·두 번 거쳐도 같게), 연구 배경·방법 칸(`DocField` — 승인 상태 그대로, 버전 충돌이면 `GET …/proposal` 로 다시 읽어 목차가 그대로일 때만 한 번 다시 — `putOnceMore`·`proposalReread`), '검토할 곳' 줄, 내보내기 기본값(모든 문단·워터마크 없음·'수락한 문단만'·2절 연구 배경·부록 상태별 개수·모델과 시도 기록 뺌·'다시 맞춤 필요' 절 표시)·문단 상태 이름 'AI 작성 · 검토 전' |
| R 단계 이름·딥리드 | 보이는 이름 '제목 고르기'·'참고문헌 선택하기'·'보고서'(`STEP_NAMES`·`FINAL_STEP_NAME` — 키·주소·API 그대로, 서버 문구도 '계획서'·'핵심 개념' → '보고서'·'키워드'), 딥리드 스트림 분리(`deepReadSse`·`useDeepReadChat` — 논문별 대화·AbortController·멈춘 답 남기기), BookChat 문서 종류(책/논문 문구)·출처 칩 버튼·[원문 보기]·논문 화면 두 호출처 `doc-kind="paper"`, 오른쪽 패널 부품(`DeepReadPanel` — 2단·서랍·전체 폭·초점, 서랍·전체 폭은 Tab 을 가두는 모달 dialog), 참고문헌 선택하기의 제목 → 딥리드·[담음]·들어온 경로 첫 대목, LNB 접기 연결(06d 가 먼저 머지돼(`0802e27`) 06e 가 `[id].vue` 두 곳을 달았다 — `a9f4a6c`) |
| S 인용 근거 | `GET …/sections/{key}/sources`(생성 행의 `input.papers` — 서지·Milvus·리랭커 없음), 딥리드 논문 프롬프트(`book_chat.paper.yaml`·`chat_prompt`·`BookOut.doc_type`, 참고문헌 질문은 [이 논문의 참고문헌 목록]을 근거로)·참고문헌 질문이 끊기던 기존 버그(`_book_references`), 대목 하이라이트 순수 함수(`citationEvidence` — 글자 2-gram 겹침, 누른 칩의 근거 번호 기준), 인용 칩 → 오른쪽 인용 근거 탭(`CitationSource` — 인용한 문장·대목 강조·[원문 보기]·[이 논문과 대화하기]) |
| K 제목 고르기 | 논문 키워드 채움률 1회성 측정 도구(`research/round06e-keyword-candidates/` — 서버 실행·판정은 Task Z1, 아직. `PAPER_KEYWORD_MIN_N` 은 기본값 1), 후보 키워드(`keywords.py` — LLM + 논문 편수·일반어·상한 10·위 3개, 목록 키워드는 `;`·`,`·`|` 로 나눔), WorkView `concept_candidates`, 카드 입력·프롬프트의 키워드 규칙·[다른 방향]도 지금 키워드(개념 생성 중이면 409), 카드는 개념 반영 때 씨앗 자리마다 한 번(`enqueue_seed_cards` — done 과 취소가 같은 함수, 카드가 있는 자리는 건너뜀), [이 키워드로 다시 만들기](`POST …/topics/regenerate` — 빈 결과는 빈 자리만 채움), 키워드 칩·제목 하이라이트(`keywordSpans`·공용 고정 예제), 제목 키워드 검사(06c `terms.contains`)·세 번 놓친 카드(`soft_check`) |
| H 칩·total·PDF | 주제 카드 근거 칩 '제1저자 전체 이름 연도'·툴팁 서지 한 줄, 기록 목록 `total`(`HistoryRepository.count` — 읽는 화면 없음, '확인할 것' 1), 보고서 PDF(보고서 화면이 스스로 인쇄 — Word 와 같은 문서·기본값) |

스키마 변경 없음 — 바뀐 모양은 모두 JSONB·응답 안이다(`models/research_work.py` 머리 주석). 딥리서치 코드·워커 파일(`research_tasks.py`·`research_work_tasks.py`)·딥리서치 프롬프트·compose·인프라·06c/06d 파일(논문 검색 화면의 `doc-kind` 한 속성 밖)·`citations.ts`·`style_skovix.css`·근거 장부 블록은 그대로다(Task Z2 Step 2). 예외는 아래 round08 맞춤의 경계 밖 세 곳이다.

리뷰를 마친 뒤 round08 맞춤(2026-10-13 — 이 문서의 첫 커밋 `94f77d5` 뒤):
- `3f7a4fe` — 서버 화면 문구 두 곳의 '딥리서치'를 'DeepResearch' 로(round08 사용자 결정 — 화면 표기 DeepResearch): 승인·재시도를 막는 429 `browser_active` 의 message('진행 중인 DeepResearch가 있습니다 — …', `app/api/research.py` — 화면 `utils/researchErrors.ts` 의 기본 문구와 같은 말)와 [이 연구 이어가기]의 409('완료된 DeepResearch만 이어갈 수 있습니다', `app/api/research_work.py`). 공유 큐 429 의 '다른 딥리서치가 …' 는 화면이 '요청이 몰려 있습니다'로 바꿔 보여 그대로. 06d 이월 §7-9 를 닫는다.
- `5d56f12` — 도서 추천 이유 스트림(`services/search/pipeline.py` `stream_book_reason`)이 LLM 호출이 실패하면 `[DONE]` 앞에 `{error: REASON_STREAM_ERROR}` 이벤트를 먼저 보낸다(예전에는 `[DONE]` 만 보내 받다 만 이유가 완성본으로 기록에 저장됐다). 화면 `utils/bookAiPick.ts` `readReasonStream` 은 `{error}` 를 보면 false — 랜딩 검색은 받은 글이 있으면 'interrupted'(보이되 저장하지 않음), 없으면 'error'. `2af9aff` 가 vLLM 의 4xx·5xx 응답도 같은 길로 보낸다(`resp.raise_for_status()` — 형제 `paper_summary.stream_paper_reason` 과 같은 관례).
- `07118ff` — 06e 화면 글의 '딥리드'를 화면 표기 상수 `DEEP_READ`('DeepRead', `utils/brand.ts`)로: 오른쪽 패널의 대화 탭 이름(`utils/deepRead.ts` 의 `PANEL_TAB_LABEL`)과 참고문헌 선택하기 온보딩('그 논문과 대화(DeepRead)할 수 있고'). 남은 '딥리드'는 주석뿐이다.
- `8acbcb1`·`786c2bf` — 근거 없음 안내(`ProposalSection.vue` `skippedNow`)의 씨앗 출처를 '`{{ DEEP_RESEARCH }}` 보고서의 향후 과제·근거가 부족했던 하위질문'으로(§2 '계획과 다르게 한 것' A5).
- 그 네 커밋 검토의 minor 다섯 반영 — `2af9aff`(4xx·5xx, pytest +1)·`786c2bf`(위 문구)·`355cc53`(`proposalSection.test.ts` 의 import 줄 단언을 이름만 보는 꼴로)·`d353b3b`(두 테스트에 복제된 pipeline import 대역을 공용 `app/tests/pipeline_stub.py` 로 — 되돌림 테스트는 `test_pipeline_stub.py` 한 곳, 같은 단언이 두 번 돌던 것이 한 번)·이 문서 맞춤(spec §12-4 탭 이름, 06d 완료노트 이월 §7-8·§7-9, 반복 함정 24 의 429 문구).

경계 밖 세 곳(round08 맞춤): `app/api/research.py` 문구 한 줄(딥리서치 코드), `services/search/pipeline.py`·`utils/bookAiPick.ts`(도서 추천 이유 — 06e 기능이 아닌 기존 화면의 끊김 처리).

계획과 다르게 한 것(작업 보고에서 모음):
- **서랍 CSS(R4)** — 계획(공통 계약 1-8)은 패널 루트에 `style_skovix.css` 의 `.skx-chat-side` 를 함께 달아 모양을 물려받고 `work.css` 의 `.wk-panel.skx-chat-side` 로 덮는 것이었다. round08 이 그 블록을 쓰이지 않는 규칙으로 지워, 루트는 `wk-panel` 하나이고 세로 flex·overflow·바탕·서랍(1200px 미만)·전체 폭(768px 이하)을 모두 `work.css` 의 `.wk-panel` 에 두었다.
- **근거 없음 안내(A5)** — '고른 주제의 씨앗(딥리서치 보고서의 향후 과제·부족한 하위질문)'에서 '딥리서치 보고서의'를 뺐다(round08 의 화면 표기 통일 중이라 새 '딥리서치' 글을 넣지 않음). → round08 맞춤에서 `8acbcb1` 이 화면 표기 상수로 되살리고(`{{ DEEP_RESEARCH }} 보고서의 …`), `786c2bf` 가 목차 편집·온보딩과 말을 맞췄다('향후 과제·근거가 부족했던 하위질문').
- **R1 의 '딥리서치' 여섯 자리** — dev 를 받은 뒤 최종 리뷰 반영(`ef9746d`)에서 화면 표기 상수 `DEEP_RESEARCH`(`utils/brand.ts` — 'DeepResearch', 사용자 결정 2026-10-12)로 바꿨다.
- **`putOnceMore`(X3)** — 계획의 '응답 version 으로 한 번 다시'를 '`GET …/proposal` 로 다시 읽어 목차가 그대로일 때만 다시 읽은 version·목차로 한 번 다시, 목차가 바뀌었거나 읽기에 실패하면 첫 충돌'로 고쳤다(`0bc2a92`·`07ea0fe` — 옛 본문이 다른 곳의 목차 변경을 말없이 되돌리던 것, 화면의 reload 가 늦은 응답 버리기로 옛 version 에 머물던 것).
- **목록 키워드 구분자 `|`** — 계획은 Task Z1 측정 판정 뒤 더하기로 했지만, MARC·MARC+MODS 로더가 653 $a 를 ' | ' 로 잇는 것이 코드로 확정이라 최종 리뷰 반영(`22f9651`)에서 먼저 더했다.
- **버튼 자간** — 링크였던 제목·인용 칩을 버튼으로 바꾸며 `letter-spacing: inherit` 한 줄씩(R5·S4).

---

## 3. 리뷰

작업마다 구현 → spec 준수 → 품질 검토를 돌렸다 — 그 지적을 고친 `[Fix]` 커밋이 22개다(연구 공백 단정 넷, 연구 배경·방법 칸 둘, 딥리드 패널 초점·인쇄 셋, 인용 근거 강조 넷, 그 밖에 하나씩). 끝에 dev(`0802e27` — 06d·round08)를 받은 뒤(`f9914e9`) 영역별 정적 리뷰를 돌렸다(리뷰 20회). 지적 16건을 반영했다 — 커밋 넷:
- `a9f4a6c` — Task R6: 06d 가 먼저 머지돼 늦게 머지하는 06e 가 `[id].vue` 의 루트 `is-lnb-collapsed`·`AppSidebar :collapsed="workPanelOpen"` 두 곳을 단다.
- `22f9651`(백엔드 다섯) — [이 키워드로 다시 만들기]의 빈 결과가 멀쩡한 카드를 '근거 부족'으로 지우던 것, 06e 전 입력으로 묶은 카드에 `keywords` 를 싣지 않기, 목록 키워드 `|` 나누기, 딥리드 논문 프롬프트의 참고문헌 목록 한 줄, 타입힌트·주석. 테스트 +3.
- `ef9746d`(프론트 아홉) — [이어서 쓰기] 뒤 초점, 큰 진행 막대 이름, '수락한 문단만' 체크가 켜진 채 막히던 것, 서랍·전체 폭 패널의 dialog, 인용 칩 `aria-controls` 는 열린 칩에만, 딥리드 답 끝 초점, 안내 글의 버튼 이름 상수, '딥리서치' 여섯 자리 → `DEEP_RESEARCH`, 부록 상태 이름 주석. 테스트 수 그대로.
- `afafa0a`(계획) — 공통 계약 1-6 의 `putOnceMore` 행을 실제 시그니처로, 정함 1 의 이름 바꾸기 절차에 `DEEP_RESEARCH`.

반영하지 않은 지적 넷과 까닭:
1. **기록 `total` 을 아무도 읽지 않는다**(important) — 고치는 방법이 사용자 결정이다. '확인할 것' 1.
2. **연쇄가 POST 하는 중인 절이 '쓰기 전'·[이 절 쓰기]로 보인다**(minor) — 누르면 409 `SECTION_BUSY` 로 연쇄가 멈출 수 있지만 [이어서 쓰기]로 남은 절부터 다시 돈다. `AutoReportHandle` 계약을 바꿔야 해 싸지 않다 — §7-13.
3. **문단 상태 이름 '고침'(화면 띠) ↔ '수정'(부록)**(minor) — 어느 말로 맞출지는 spec 결정이라 이 문서 작업(Task Z3)에서 spec §12-4 를 코드대로(둘 다 그대로) 적고 통일은 넘겼다 — §7-14.
4. **`putOnceMore` 새 시그니처를 완료노트·spec §12-4 에**(minor) — 이 문서 작업에서 반영했다(§2 '계획과 다르게 한 것', §6 정함 8, spec §12-4).

그 뒤 round08 맞춤 커밋 넷(`3f7a4fe`·`5d56f12`·`07118ff`·`8acbcb1`)을 다시 검토해 minor 다섯을 모두 반영했다 — §2 끝 'round08 맞춤'.

---

## 4. 검증

2026-10-13, 리뷰를 마친 커밋 `afafa0a`(dev 머지 전):
- 백엔드 pytest `5 failed, 2664 passed, 1 skipped, 2 warnings, 1 error` — 실패 5·오류 1 은 Task 0 기준선과 같은 로컬 의존성 파일(test_build_manifest 2·test_loaders 3·test_book_chat 수집). 기준선 2491(이 worktree 의 Task 0 실측 — 계획 머리의 2327 보다 06c 등 dev 에 들어온 테스트만큼 많다) → 06e +173. dev 받기(06d·round08)는 nuxt 만이라 백엔드 수를 바꾸지 않았다. 06e 백엔드 묶음 스물세 파일 917 passed(`test_embed_index_guard` 포함), 06c 의 `test_research_terms.py`·`test_research_eval.py` 92 passed.
- 프론트 vitest — dev 받기 전 45파일 908(Task 0 기준선 40파일 739 → 06e +5파일·+169), dev 받은 뒤 73파일 1569(06d·round08 테스트가 들어옴). 06e 프론트 묶음 열여덟 파일 391 passed. `nuxi typecheck` 오류 0 · `Duplicated imports` 2 — 둘 다 round08 의 `MetaPart`(`utils/detailView.ts` ↔ `resultCard.ts`)이고 06e 이름은 아니다(Task 0 의 2 는 `queueLine` 이었고 06d 가 지웠다) · `npm run build` 완료. 그대로여야 하는 `citations`·`reportDocument`·`reportDocx` 50 그대로(계획의 49 에 round08 이 `reportDocx` 테스트 하나를 더했다).
- 경계(받은 dev `0802e27` 기준): 고치지 않을 파일(`utils/brand.ts` 포함) diff 없음, `[id].vue` 는 요약 띠 버튼 글 한 줄(R1 — '{{ DEEP_RESEARCH }} 보고서 보기') + 리스너 두 줄 + `workPanelOpen` 두 줄 + 루트·AppSidebar(R6)뿐, 논문 화면 두 곳은 `doc-kind="paper"` 한 줄씩(dev 가 `pages/papers/[id].vue` 의 BookChat 을 한 줄로 바꿔 그 줄 안에 넣었다), 근거 장부 블록 그대로, `work.css` 에서 지운 줄 0·더한 색값 0, 프롬프트에 예시 낱말 0, 커밋 트레일러 0, `git status` 깨끗함. 고친 파일 목록은 계획 Z2 목록과 같고 `research/round06e-keyword-candidates/out/fill_rate.md` 하나만 없다(Task Z1 전).
- round08 맞춤 뒤(2026-10-13, `d353b3b` — 이 문서 맞춤 전): 백엔드 pytest `5 failed, 2669 passed, 1 skipped, 2 warnings, 1 error`(실패 5·오류 1 은 위 기준선 그대로, +5 = `5d56f12` +5 · `2af9aff` +1 · `d353b3b` −1 — 두 파일에 있던 같은 sys.modules 되돌림 테스트가 하나로), 공용 대역을 쓰는 세 파일(`test_search_chunk_answer_flag`·`test_stream_book_reason_end`·`test_pipeline_stub`)은 여섯 순서로 함께 돌려 모두 11 passed. 프론트 vitest 74파일 1574(+1파일·+5 — brand·deepRead·proposalSection 각 +1, bookAiPick +2), `nuxi typecheck` 오류 0 · `Duplicated imports` 2(`MetaPart` 그대로) · `npm run build` 완료.
- 브라우저 확인은 하지 않았다 — `.vue` 동작(막대 차오름·sticky·머리 목차 초점·연쇄·패널 2단/서랍/전체 폭·Tab 가두기·초점 복귀·하이라이트·[원문 보기]·Word/PDF 내용)은 운영 쓰기 금지라 Task Z6 운영 확인에서 본다.

---

## 확인할 것 (사용자와 — `dev` 머지(Task Z4) 전)

1. **기록 `total`(Task H2 — `dbde4af`)을 어떻게 할지.** 06d 가 '모두 보기 (N)' 을 만들지 않기로 해(spec D26, 사용자 결정 2026-10-12~13) dev 를 받은 뒤에도 `types/history.ts`·`utils/historyStore.ts`·`composables/useHistory.ts`·`AppSidebar.vue` 어디도 `total` 을 읽지 않는다. 남겨 두면 `GET /api/history` 마다 아무도 읽지 않는 COUNT 가 한 번 더 돈다(진행 중 연구가 있으면 사이드바가 30초마다 부른다).
   - (a) `dbde4af` 되돌리기 — 백엔드 테스트 −3, `test_other_browser_list_is_empty` 기대 원복, 계획 H2·정함 26·Task Z6 7번과 이 노트·spec 에서 지운다.
   - (b) API 전용 필드로 남기기 — 주석 네 곳(`api/history.py`·`repositories/history.py`·`schemas/history.py`)을 용도만 말하게 고치고 Task Z6 7번을 지운다.
2. **논문 키워드 채움률 측정(Task Z1) — 아직 하지 않았다.** 측정 도구(`research/round06e-keyword-candidates/measure.py`·README)는 만들고 개발 PC 에서 `--dry-run` 까지 봤다. 서버 실행(README '실행' — `/app/data/` 바인드 + `-e PYTHONPATH=/app`, 읽기 전용)은 사용자 몫이다. 결과로 `PAPER_KEYWORD_MIN_N` 을 1(채택 논문 중 키워드가 있는 비율 50% 이상) 그대로 둘지 2 로 바꿀지 정하고 README '결과'·`out/fill_rate.md` 를 커밋한다(2 면 상수 한 줄과 테스트). 목록 키워드 구분자 `|` 는 이미 더했다(`22f9651`) — 측정 ③ 은 그 밖의 구분자가 있는지만 본다. 지금 값(1)으로 머지·배포해도 동작은 한다(논문에만 있는 1편짜리 후보도 칩에 선다).
3. **round08 과 겹치는 것 — 머지 때 맞출 것.** dev(`0802e27`)를 이미 받아(`f9914e9`) 코드 충돌은 풀렸고 R1 의 '딥리서치' 여섯 자리는 `DEEP_RESEARCH` 로 바꿨다. 남은 것:
   - **'딥리드' 표기** — 패널 탭 이름(`DeepReadPanel.vue` `TAB_LABEL.chat`)과 온보딩 ② 본문('그 논문과 대화(딥리드)')은 계획·spec 대로 '딥리드'다. round08 화면은 영문 'DeepRead'(상세·검색 결과·TopResult — 상수 없음, `utils/brand.ts` 에는 `DEEP_RESEARCH` 만)를 쓴다. 맞추려면 `brand.ts` 에 상수 하나를 두고 두 자리를 바꾼다(그 글자를 기대하는 테스트는 없다). → `07118ff` 로 닫음 — `brand.ts` 에 `DEEP_READ`('DeepRead')를 두고 두 자리가 그것을 쓴다(탭 이름은 `utils/deepRead.ts` 의 `PANEL_TAB_LABEL`, vitest brand·deepRead·workPhase 단언).
   - **근거 없음 안내의 출처** — A5 에서 뺀 '딥리서치 보고서의'를 다시 밝히려면 `ProposalSection.vue` 의 근거 없음 안내 문단(`skippedNow`)에 `DEEP_RESEARCH` 로 넣는다. → `8acbcb1`·`786c2bf` 로 닫음 — '`{{ DEEP_RESEARCH }}` 보고서의 향후 과제·근거가 부족했던 하위질문'(vitest `proposalSection.test.ts`).
   - **주석의 '딥리서치'** — `utils/proposalDocument.ts` 머리 주석·`ProposalStep.vue` 진행 막대 주석. 화면 글이 아니라 그대로 둬도 된다.
   - **서랍 색** — 서랍 그림자·배경이 `color-mix(… var(--skx-ink) 15%·25% …)` 다. round08 다크 테마에서 `--skx-ink` 가 밝은 회색(`#cccccc`)이라 배경이 밝은 기운이 된다 — Task Z6 에서 보고 어색하면 새 색값 없이 다른 토큰으로 바꾼다.
   - **흰 바탕 토큰** — `.wk-review__jump`·`.wk-docfield` 등이 `--skx-white`·`--skx-ink` 를 쓴다. 다크 테마가 두 토큰을 다시 정의해(`#152e28`·`#cccccc`) 따라가지만 대비는 Task Z6 에서 본다.
   - **PDF 버튼** — `research.css` 의 `.rs-btn--ghost` 를 쓴다. dev 에도 있다(`research.css:171`) — 확인됨.
   - **BookChat** — 06e 는 스크립트(`useDeepReadChat`)·출처 칩 버튼·`doc-kind`·`pdfLinks` 를 바꿨다. 기존 네 화면(논문 상세·논문 검색 채팅·도서 상세·TopResult)의 회귀 — 문구, 출처 칩 모양(span → button), 미리보기 펼침, [원문 보기]가 보이지 않음, 보내기 버튼 이름 '검색' → '질문 보내기', 같은 화면에서 논문이 바뀌면 대화를 비움(의도한 버그 수정) — 는 Task Z6 에서 다크 테마와 함께 본다.
4. **06c 기본값 커밋은 없다** — 06c 판정(2026-10-12)으로 서버 기본값 `broaden` 0 · `query_context` 0 그대로다. Task Z5 의 '06c 기본값' 줄은 dev 값이 `0 0` 인지 확인만 한다.

---

## 5. `dev` 머지·운영 배포·운영 확인

- **`dev` 머지** — `7d59f72`(2026-10-13, 06d `0802e27` 뒤).
- **운영 배포 2026-10-13** — 사용자가 dev `7d59f72` 이미지로 워커·fastapi·nuxt(fastapi `sha256:9f373924…`·nuxt `sha256:4a3cb449…`, 되돌리기 태그 `:pre-round06de` — 06d 와 한 이미지라 되돌리면 함께 빠진다).
- **운영 확인** — 그날 운영 확인에서 수정 4건이 나왔다(인용 대목 `<br>`·Word 참고문헌 '-46'·'이렇게 이해했어요' 끝 부호·참고문헌 상위 8편 미리 담기 요청). 고친 것과 그 배포·점검은 아래 '운영 확인 수정(10-13~14)'. 운영 처음부터 끝까지 1회(Task Z6)는 아직이다.

### 운영 확인 수정(10-13~14)

브랜치 `fix/round06-live-check`(worktree `.worktrees/fix-live`) → `dev` 머지 `c205a88`(2026-10-14, 인용 팝오버 `3171ee2` 위). 06c·06d·06e 와 소장자료·논문 검색에 걸친 수정이라 06e 완료노트에 모은다.

| 고친 것 | 내용 |
|---|---|
| 인용 대목 `<br>` | 원문 대목의 `<br>` 태그 글자를 줄바꿈으로(인용 근거 패널·보고서 인용칩 팝오버·들어온 경로 대목·DeepRead 출처 미리보기) |
| 참고문헌 학술지 자리 | Word 의 '-46' → '학술지, 권(호), 쪽'(권·호·쪽이 비거나 일부만 있어도 깨지지 않게 — Word·화면 공통). 권 없이 호만 있는 '(46)' 은 그대로(D1) |
| '이렇게 이해했어요' | 원 질문과 끝 문장부호·따옴표·띄어쓰기·끝 물결만 다르면 띄우지 않는다 |
| 참고문헌 미리 담기 | 이어가기 때 채택 근거 상위 8편을 참고문헌 선택하기에 미리 담는다(사용자 결정 2026-10-13). 같은 순위는 대목 점수 높은 편 먼저(D2), Word 'AI 사용 공개' 부록에 '참고문헌: 이어가기 때 채택 근거 상위 N편을 미리 담음 — 사용자가 확인·수정'(D3, N 이 1 이상일 때만) |
| 참고문헌 선택하기 문구 | 기획 세션 승인 문구(합니다체)·다음 단계 버튼을 머리 소개 옆에도 |
| 소장자료 관련 자료 | 전용 `GET /api/books/{id}/related` — 자기 제외·하한(종합 0.3 + 원점수 0.2)·검색 기록에 남기지 않음. 첫 시연 질의 1위의 관련 자료 1권 → 4권 |
| 스트리밍 오류 | AI 글 스트림 다섯이 LLM 실패를 `{error}` 이벤트로(D4 — `app/services/llm_sse.py` `sse_deltas`, 스트림 안 오류 줄·`[DONE]` 없는 끝 포함). 캐시·검색 기록·DeepRead 이력에 오류가 남지 않는다 |
| 논문 검색 쿼리 재작성 | 끔 — 서버가 요청 값을 무시한다(사용자 결정 2026-10-14). 근거는 켬 71% vs 끔 87%(파이프라인 측정, 독립 3세트 450문항 — 재작성 단계 −17.6%p), 배포본 실측 Recall@10 89%(2026-10-14, 합성 질문 150건 기준 — 사람 검증 없음) — 브랜치 `feat/brochure-search-eval` 의 `research/brochure-search-eval/README.md`. 메타데이터 필터는 판단 불가(날짜 조건이 걸린 질의 5%)라 그대로 둔다 |
| 소장자료 비교 사유 | 시험만 하고 접음(`research/book-related-reason-trial`) |

| 배포 | 이미지 | 비고 |
|---|---|---|
| 2026-10-14 (사용자) | 워커(celery-research 등)·fastapi `:latest` `sha256:3389d01f…`(`c205a88`) · nuxt `:latest` `sha256:c6d7a7f7…`(`1f2c328` — 프론트 세션의 기록 삭제 확인·탐색 방식 문구 포함) | 되돌리기 태그 `:pre-1f2c328`. DB 변경 없음(새 설정 셋은 코드 기본값). 계획 순서는 워커 → fastapi → nuxt → 게이트웨이 reload, fastapi·nuxt 는 이어서(반복 함정 28번). Portainer Re-pull 을 켠 채였지만 문제 없었다 |
| 그 뒤 (프론트 세션) | nuxt `sha256:1ff34f28…`(`b1d933e`·`64cfb18` — 인용 정리·사이드바 상태 라벨·강조 색) | 이미지는 프론트 세션이 올렸고 그 배포도 프론트 세션 몫 |

| 운영 점검(10-14, 배포 뒤) | 결과 |
|---|---|
| 소장자료 관련 자료 | 6건 모두 4권(시연 질의 3 의 1위는 소설 연구 2권이 빠지고 시 연구로 바뀜) |
| AI 글 스트림 5종 | 정상 `[DONE]` |
| 논문 검색 | `rewritten_query` null |
| 인용 대목 | `'<br'` 0 |
| 참고문헌 | '학술지, 권(호), 쪽' |
| 읽기 목록(reading) 순서 | 새 키(같은 순위는 대목 점수 순) |

이번 배포분 결함 없음.

| 남은 것 | 상태 |
|---|---|
| 예시 연구 | 0건 — 지정 필요(`scripts/research_eval/mark_example.py`) |
| 미리 담기 8편 | 운영 E2E 2회(이어가기 630e0d65·d60a5dc1)에서 8편이 담겼다 — 목차 묶음이 7:1 로 나뉘던 것은 아래 3차에서 고침 |
| 옛 검색 기록 API 의 비-uuid 세션 id 500 | `20dbe10` 으로 고침(fastapi 만) — 아래 2차(`dev` `65907eb`)로 운영 배포됨(10-14) |

반복 함정 — 이 배포 작업에서 나온 것 셋을 `docs/ops/recurring-gotchas.md` 28~30번에 더했다(서버·화면이 같이 바뀐 배포의 순서, Git Bash curl 의 한글 JSON, 서버 셸 root 전환 줄 붙여 넣기).

#### 운영 E2E 품질 수정 2~4차(10-14)

위 배포(1차 `c205a88`) 뒤 운영 E2E(딥리서치 → 이어가기 → 보고서, 이어가기 630e0d65·d60a5dc1)에서 나온 서버 품질 수정을 같은 브랜치에서 차수마다 `dev` 에 머지했다. 3·4차는 서버만이다 — nuxt 는 바뀌지 않았고 DB·env·compose 설정 변화도 없다.

| 차수 | `dev` 머지 | 고친 것 | 다시 만들 컨테이너 | 이미지 | 배포 |
|---|---|---|---|---|---|
| 2차 | `65907eb` | 근거 대목에서 논문 끝 참고문헌 목록 조각 빼기([`research/bibliography-chunk-filter/`](../../research/bibliography-chunk-filter/README.md))·이어가기 절의 수치 칩 누설과 '본 연구' 지칭·한계 문구의 조사와 '결론이 약하다'·거의 같은 씨앗 중복·보고서 연구 질문을 고른 카드 질문으로·옛 검색 기록 세션 id 400(`20dbe10`) | celery-research·celery-research-plan·fastapi·nuxt(프론트 세션 변경 포함) | fastapi `sha256:37856894…`·nuxt `sha256:14d93215…` | 운영 배포됨(10-14) |
| 3차 | `cb12bcb` | 이어가기 목차 묶음 최소 2편(`MIN_GROUP_PAPERS` — 8편이 7:1 로 나뉘던 것)·연구 공백 절이 고른 카드 씨앗만·한계 줄을 절 번호 + 자기점검 메모 첫 문장으로·짧은 참고문헌 조각 판정·[이 키워드로 다시 만들기]가 더한 키워드를 제목에 넣기(두 번 놓치면 다른 모델로 넘기지 않고 무른 검사 카드를 보관 — `settle`)·절 생성 대목을 논문마다 서술 대목으로 고르고 절 사이 되풀이 문장 지움(`drop_repeats`) | fastapi·celery-research·celery-research-plan | fastapi `sha256:99c360b2…` | 운영 배포됨(2026-10-15, 사용자 — 어느 컨테이너까지 했는지는 사용자 확인 전) |
| 4차 | `f06b814` | 딥리서치 종합 프롬프트 개편(A/B 채택 focus — 절마다 하위질문에 곧장 답하기, `fd360d1`)·대목 속 남의 번호 인용 지우기(`strip_numbered_refs`)·요약 빠지면 재요청(도입 있는 응답 우선)·모델에 넘기는 대목을 400자 안 문장 끝에서 자르기(통계 소수·약어 예외) | celery-research(3차를 안 했으면 위 셋) | fastapi `sha256:b8dd67fb…`(3차 내용 포함) | 운영 배포됨(2026-10-15, 사용자 — 어느 컨테이너까지 했는지는 사용자 확인 전) |

- **배포(사용자)** — 도는 연구·생성이 없을 때, 적재 워커는 건드리지 않고 Portainer 에서 하나씩 Recreate(스택 업데이트 금지). 순서는 celery-research → celery-research-plan → fastapi → 게이트웨이 reload, 되돌리기 태그 `:pre-cb12bcb`·`:pre-f06b814`. 확인: fastapi 의 `services/research_work/shapes.py` 에 `MIN_GROUP_PAPERS`, celery-research 의 `domains/nl_library/prompts/research_synthesize.yaml` 에 '하위질문에 대한 답'·`services/research/citations.py` 에 `strip_numbered_refs`. 2026-10-15 11:13 KST 사용자가 '배포 했어'라고 답했다 — 위 '다시 만들 컨테이너' 가운데 어느 것까지 다시 만들었는지는 사용자 확인 전이고, 서버에서 낸 이미지 digest·위 확인 grep 의 출력도 아직 받지 않았다.
- **4차 A/B** — [`research/synth-prompt-ab/`](../../research/synth-prompt-ab/README.md). 운영 보고서 4건(630e0d65·d60a5dc1·85d2bc0e·9ba10849, 보고서마다 6절) × 2회를 종합 프롬프트 세 방향(focus·attrib·concise)으로 다시 만들어 LLM 판정자 셋이 블라인드로 판정했다. focus 채택 — 현행 대비 10승 0패 2무(r0 회차 4짝 × 판정자 3), 보고서당 근거 표시 없는 문장 3.5→0.8, 첫 문장이 일반론인 절 3.8→0(v1 정규식)·3.9→0.6(v2), '본 절에서는' 류 군말 1.0→0. attrib·concise 는 판정은 넘었지만 자동 지표(무효 인용 / 형식 문제·빈 요약)에서 떨어졌다. 남은 약점은 도입 4문장 초과 절 42%·1문장 요약 45%·한 논문의 표본을 분야 전체로 넓히는 일반화·재인용 오귀속(6.1→6.4 그대로). 한 번 더 겨룬 focus2(focus + 재인용·일반화 규칙)는 focus 대비 판정 15승 7패 2무였지만 형식 문제 1·빈 요약 1·게재지 군말 19편으로 채택하지 않았다. 수치 범위: 자동 지표는 운영 보고서 4건 × 2회, 1차 판정은 r0 회차만(위 괄호)·2차 판정은 4건 × 2회 = 8짝 × 판정자 3, 생성 gemma-3-12b, 판정자는 사람이 아닌 LLM 에이전트 — 운영 화면에서 다시 잰 값이 아니다.
- **배포 뒤** — 새 연구(딥리서치 → 이어가기 → 보고서)로 품질을 확인한다(진행 중 — Task Z6 운영 처음부터 끝까지 1회와 함께).

---

## 6. 결정

| # | 결정 |
|---|---|
| 정함 1 | Q2 기본 '보고서' — 이름 낱말은 `FINAL_STEP_NAME` 하나이고 조사가 붙지 않는 꼴에만 쓴다(조사가 붙는 문장은 글자 그대로 — 이름을 바꾸면 상수 한 줄과 `grep -rn "보고서[를로가는의은이]"` 가 내는 문장·테스트). Q2 의 딥리서치 용어 — 단계 화면에서 딥리서치 보고서는 화면 표기 상수 `DEEP_RESEARCH`('DeepResearch' — 사용자 결정 2026-10-12) + '보고서'(Task R1 의 다섯 곳과 온보딩 ① — dev 받기 뒤 `ef9746d`) |
| 정함 2 | Q3 기본 S — 주제 카드 칩만(`topicDeck.ts`), `citeLabel`·보고서 칩·상세 인용 배너 그대로 |
| 정함 3 | 자동 승인은 연구 질문이 있을 때만(첫 후보 → 카드 질문, 공백 정리 뒤 2자 미만은 없는 것) — 없으면 06b 처럼 초안·`auto` false |
| 정함 4 | [보고서 다시 만들기]는 이미 쓴 절을 다시 쓰지 않는다 — 주제·묶음·연구 질문이 바뀐 절은 '다시 맞춤 필요' + [이 절 다시 쓰기](Word 에도 그 표시), 아직 쓰지 않은 절만 자동, 연구 배경은 이어 받는다 |
| 정함 5 | 근거 없음 409 는 `{"code": "no_section_papers", "message"}` — 연쇄는 code 로 가른다 |
| 정함 6 | 연쇄는 보고서 화면이 열려 있을 때 돈다 — 서버 값으로 매번 다시 계산해 탭을 닫았다 와도 남은 절부터 |
| 정함 7 | 연구 배경 = `outline.background` 자유 글(상한 2000, PUT 에서 생략·null 이면 지킴, 새 반영(apply)은 옛 목차에서 이어 받음 — Task X1) — Word·PDF 2절에도, '다음 단계에서 씁니다'는 지움 |
| 정함 8 | 방법·배경 칸은 문서 2·6절 자리에서 승인 상태 그대로 저장. `version_conflict` 면 `GET …/proposal` 로 다시 읽어(`proposalReread`) 목차가 그대로일 때만 다시 읽은 version·목차로 한 번 다시 보내고(`putOnceMore(put(version, outline), {version, outline}, reread)`), 목차가 바뀌었거나 읽기가 실패하면 첫 충돌을 오류 줄로 |
| 정함 9 | 연구 질문 바뀜 = 절 basis 의 `question` — 06e 부터 쓴 절만 견준다(06b 절은 이 이유로 stale 이 되지 않음) |
| 정함 10 | 연구 공백 단정은 '소장 코퍼스 범위' 낱말(코퍼스·소장 논문/자료/문헌/학술논문)이 든 문장에서만 공백 후보 투로 — 인용한 발견은 그대로 |
| 정함 11 | '검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m' 줄과 부록의 같은 수는 넣고, '근거 없음' 보이는 배지는 넣지 않는다(화면낭독 글만) |
| 정함 12 | 문단 버튼 줄은 접지 않는다 |
| 정함 13 | 내보내기 기본 = 네 상태 전부·워터마크 없음, '수락한 문단만'(`acceptedOnly`)이면 수락·수정·직접 작성만과 파일 이름 꼬리 `_수락문단만`(켜 둔 채 검토 전 문단이 없어지면 모든 문단과 같은 문서). 부록에서 모델 이름·시도 기록 줄을 뺐다 — 저장은 그대로(`research_generations.model`·`output.attempts` — 필요하면 DB 로 본다). 문단 상태의 보이는 이름은 화면 띠 'AI 작성 · 검토 전 / AI 작성 · 수락 / AI 작성 · 고침 / 직접 작성', 부록 'AI 작성·검토 전 / 수락 / 수정 / 직접 작성' — 고침·수정 통일은 §7-14 |
| 정함 14 | 키워드 후보 = LLM 후보 + 채택 논문 키워드 문서 빈도 — `PAPER_KEYWORD_MIN_N` 은 기본값 1 로 구현했고 Task Z1(운영 채움률 측정 — 사용자 서버 실행)이 아직이다('확인할 것' 2). 목록 키워드 구분자는 `[;,|]` |
| 정함 15 | 키워드 최소 선택 2(처음 미리 선택 3 은 하한을 보지 않음)·상한 5·직접 더하기 남김 |
| 정함 16 | 고른·고친·직접 쓴·접은 카드는 키워드를 바꿔도 다시 만들지 않는다 |
| 정함 17 | 세 번 다 놓친 카드는 `soft_check` 로 마지막 무른 통과 출력을 보관해 '제목에 「…」 없음' 경고와 함께 보인다 |
| 정함 18 | 딥리드 논문 프롬프트 채택 — `book_chat.paper.yaml` + `chat_prompt(book)`, `BookOut.doc_type` 을 더했다(spec 이 가정한 필드가 응답에 없었다) |
| 정함 19 | 연구 맥락을 반영한 딥리드 첫 화면은 하지 않는다 |
| 정함 20 | 딥리드 대화는 단계 화면이 쥔 논문별 대화 — 같은 단계 안에서만 이어지고 서버에 저장하지 않는다 |
| 정함 21 | 닫기·논문 바꾸기로 끊은 답은 받은 글 + '(답을 받다가 멈췄습니다)'로 남긴다(history 의 짝을 지킨다) |
| 정함 22 | 출처 칩 글자는 저장값 그대로(LLM 문맥과 같은 쪽), [원문 보기]만 뷰어 쪽(+1) |
| 정함 23 | 인용 근거 조회 = `{E#: {cnts_id, abstract, excerpt}}`, 생성은 `?gen=` → 저장된 절 → 열린 생성 순, 그 생성 행의 `input.papers` 만 읽는다 |
| 정함 24 | 인용 칩은 저장된 문단에서만 패널을 연다(쓰는 중인 글의 칩은 그대로) |
| 정함 25 | 개념 반영이 넣은 카드는 화면이 개념 done 에 다시 읽어 보고, 취소 API 가 넣은 카드는 커밋 뒤 queued 이벤트 |
| 정함 26 | 기록 total 은 `HistoryRepository.count` 로 따로 센다 — `list` 의 반환 모양 그대로, `before` 와 무관. 읽는 화면이 없어 남길지 되돌릴지는 '확인할 것' 1 |
| 정함 27 | PDF 는 보고서 화면이 스스로 인쇄한다(Word 와 같은 문서·기본값) — 했다(Task H3 — `65b0db6`) |
| 정함 28 | 자동 보고서 화면에도 큰 진행 막대(두께 1rem·768px 이하 0.75rem·큰 글줄·퍼센트 — `work.css` 토큰) — 이 계획의 판단, 사용자 확인 2026-10-11 |
| 정함 29 | 씨앗 카드 '한 번만'은 씨앗 자리마다 판정하고(카드가 이미 있는 자리도 건너뜀), [다른 방향]은 개념 생성이 열려 있으면 409 `KEYWORDS_BUSY` |
| 정함 30 | LNB 접기 — 06e 는 emit·리스너·`workPanelOpen`, `[id].vue:3-7` 두 곳은 늦게 머지하는 줄 — 06d 가 먼저 머지돼(`0802e27`) 06e 가 달았다(Task R6 — `a9f4a6c`) |
| 정함 31 | 딥리드 참고문헌 질문의 기존 버그(`book_chat.py:117-118` 이 `BookOut` 에 없는 `extra` 를 읽는다 — 코드는 0b51e68 부터) — Task S2 에서 고쳤다(`_book_references` 가 `BookOut.references` 를 읽는다, 테스트 1). 목록이 없으면 청크 검색으로 돌아간다(`7443ca4`) |

---

## 디자인 참조

해당 없음 — 디자인 트랙 미도입(화면은 `--skx-*` 토큰만 읽는 `work.css` 에 두었다. 큰 진행 막대의 치수는 `--wk-bar-thick` 토큰이라 시각 디자인 담당이 고칠 수 있다). round08 다크 테마와의 대비는 '확인할 것' 3.

---

## 7. 이월

1. **근거 칩 다섯 곳 통일(Q3 M)** — 보고서 `CitationChip`·상세 인용 배너·`OutlineEditor`·`ProposalSection`·`paperDetail` 의 '성 연도'(`citeLabel`)는 그대로다. 06b 이월 §7-14 가운데 보고서 절 인용 칩('박 2007' 꼴 — 운영 확인 표의 관찰)도 여기 남는다. 사용자가 M 을 고르면 `citeLabel` 한 곳을 `chipLabel` 규칙으로 바꾸고 `citations.test.ts` 를 고친다.
2. **딥리드 대화 서버 저장**(§12-9) — 지금은 단계 화면의 세션만(정함 20).
3. **연구 맥락을 반영한 딥리드 첫 화면**(§12-11 선택 — 정함 19).
4. **리랭커 뒷받침 점수·원문 뷰어 안 하이라이트**(§12-9 — 인용 근거 하이라이트가 대신한다).
5. **연쇄를 다른 단계 화면에서도 돌리기**(정함 6)·**쓰는 중인 글의 인용 칩**(정함 24).
6. **연구 공백 단정의 남는 한계** — 코퍼스 낱말이 앞 문장에만 있고 단정이 다음 문장에 있으면 잡지 못한다(Task X2 — '확인했다' 를 문장 단위로만 본다. 예: '소장 코퍼스를 살펴보았다. 관련 연구가 없음을 확인했다.'). 코퍼스 문장 안의 효과 없음 결과('소장 논문을 분석한 결과 성별 간 차이가 없음을 확인했다')는 결핍 단정('관련 연구가 없음을 확인했다')과 같은 꼴이라 공백 후보로 바뀐다 — 주어를 연구·논문으로 좁히면 '다룬 것이 없음을'·'아직까지 없음을' 같은 결핍 단정을 놓쳐 좁히지 않았다(결핍 말의 부정 '부족하지 않은'·'적지 않음을'·'다르지 않음을'과 '다름없는'·'변함없음' 같은 합성어는 그대로 둔다).
7. **LNB 접기 연결** — 06e 가 달았다(`a9f4a6c`) — 이월 없음.
8. **PDF** — 했다. 인쇄 창 취소를 브라우저가 알려 주지 않아(`window.print()`) 창이 닫히면 내려받은 것으로 본다 — 취소해도 처음 누르면 단계가 done 이 된다(단계 done 은 앞으로만 가는 도달 표시).
9. **리허설 전** — ETA 표본 섞임(06b 이월 §7-1), 3~5명 동시 사용 때 자동 보고서의 대기 길이(보고서 1건 = 생성 약 6건, 디스패처 전역 1건 — §12-8).
10. **해당 없음으로 닫은 06b 이월** — §7-3(개념 칩을 고쳐도 소속을 다시 세지 않음 — 06b 규칙 그대로, 목차 때 다시 센다), §7-6(`Section.model` 늘 null — D21 로 부록에 모델을 싣지 않는다).
11. **딥리드 참고문헌 질문(정함 31)** — 끊기던 것은 고쳤다(Task S2 의 `_book_references`). 참고문헌 목록이 없으면(책·참고문헌을 뽑지 못한 논문) 청크 검색으로 돌아가 본문 대목을 근거로 답한다(S2 quality 검토 반영). 남은 것은 의도 낱말이다 — `_REF_INTENT_KEYWORDS`(`book_chat.py:19-22`)를 부분 문자열로 보아, 목록이 있는 논문에서는 '이 인용 근거가 맞아?'·'출처가 어디야?'(spec §12-8 장면 3) 같은 본문 확인 질문도 청크 대신 참고문헌 목록을 받는다. 끊기지는 않지만 본문으로 확인한 답은 아니다. '인용'·'출처' 단독을 빼거나 '참고문헌'·'목록'과 함께 나올 때만 거는 좁히기는 사용자 결정 몫이다(기존 네 화면도 같은 길을 쓴다).
12. **방법 칸이 둘** — [목차 고치기] 안의 방법 칸과 문서 6절의 칸(`DocField`)이 같은 `outline.method` 를 고친다(시각 디자인 정리 때 하나로).
13. **연쇄가 쓰는 중인 절의 [이 절 쓰기]**(최종 리뷰 — 반영하지 않음) — 연쇄가 POST 하는 중인 절(과 다음 키)이 '쓰기 전'·[이 절 쓰기]·'지금 쓰려면 [이 절 쓰기]를 누르세요'로 보여, 누르면 409 `SECTION_BUSY` 로 연쇄가 멈출 수 있다. [이어서 쓰기]로 남은 절부터 다시 돌아 되돌릴 수 있다. 고치려면 `AutoReportHandle` 에 진행 중인 키(inflight)를 더하고 `useAutoReport.test`·ProposalStep·ProposalSection 의 새 prop·문구를 함께 바꾼다. `SECTION_BUSY` 를 '건너뜀'으로 바꾸는 쪽은 spec §12-4 '그 밖의 4xx 는 멈춤'과 어긋나 따로 정한다.
14. **문단 상태 이름 '고침' ↔ '수정'** — 화면 띠는 'AI 작성 · 고침'(`ProposalSection.vue` `STATE_LABELS`), 부록과 보고서 화면의 'AI 기여' 줄(`AiFootprintMeter` — `footprintLine`)은 '수정'(D21 의 네 상태 이름)이다. spec §12-4 는 둘 다 그대로 적었다. 하나로 맞추려면 `STATE_LABELS` 또는 `proposalDocument.ts` 의 `MIX_LABELS`·`DISCLOSURE_INTRO` 와 `proposalView.ts` 의 `footprintLine` 을 바꾸고 그 글자를 기대하는 테스트(`proposalDocument.test.ts` 등)를 고친다 — 공개 부록 문구가 바뀌므로 사용자 결정 몫이다.
15. **키워드 하이라이트의 글자 정규화 차이** — `keywordSpans` 는 JS `toLowerCase` 라 Python `casefold` 와 몇 글자(ß 등)에서 다르고, NFKC 를 글자마다 해서 결합 자모(분리형 한글)를 합치지 못한다. 06c `term_checks.json` 의 `contains` 10사례는 모두 같은 참·거짓이다(Task K9).
16. **1회성·검증 도구** — `app/scripts/verify_prompt_parity.py` 는 원래부터 로컬에서 돌지 않는다(APP 경로가 `parents[1]/"app"` 으로 잡혀 있다 — 06e 무관, 검사 줄만 더했다). `research/round06-qwen-check/smoke_check.py`(06a 1회성)는 개념 생성 출력이 바뀌어 `['concepts']` 를 읽으면 KeyError 다 — 다시 돌릴 일이 생기면 그때 맞춘다.
17. **패널 가장자리 경우** — 패널에 열린 논문의 행이 다시 읽은 목록에서 사라지면 패널은 닫히지만 안쪽 상태가 남아, 같은 제목이 다시 나타나 누르면 첫 클릭이 닫기로 쓰인다. 행은 보통 목록에서 빠지지 않아(뺀 것도 남는다) 그대로 두었다.

---

## 8. 다음 라운드 진입점

- **`dev` 머지 전** — '확인할 것' 1(기록 `total` a/b)·2(Task Z1 측정, 사용자 서버)를 정한다.
- **Task Z4 `dev` 머지(사용자 승인)** — 머지 문은 열렸다(06c 운영 배포 2026-10-12). 06d 는 이미 dev 에 있고(`0802e27`) Task R6 을 했다. 그 뒤 dev 에 들어온 커밋이 있으면 `merge-tree` 로 충돌을 먼저 본다.
- **Task Z5 배포(10/17~18, 사용자)** — 워커 셋(`celery-research`·`celery-research-plan`·`celery-control`) → fastapi → nuxt → 게이트웨이 reload. **워커가 fastapi 보다 먼저다**(새 fastapi 의 이어가기는 카드 생성을 넣지 않고 새 워커의 개념 반영이 넣는다 — Task K5). dev 에 06d·round08 이 이미 있어 06e 를 머지한 dev 로 만드는 nuxt 이미지는 셋을 함께 싣는다 — 06d 계획의 배포 순서(round08 운영 반영 뒤 06d nuxt)와 어떻게 묶을지 사용자와 정한다(Task Z5 경우 가·다). 06c 기본값 커밋은 없다.
- **Task Z6 운영 처음부터 끝까지 1회** — 이어가기 → 키워드 칩 → 카드 → 참고문헌 선택하기(딥리드 패널) → [보고서 만들기] → 인용 근거 → Word·PDF 까지 소요·대기 순번, 그리고 '확인할 것' 3 의 화면 확인. **Task Z7** 이 §5 와 반복 함정 판단을 채운다.
- **10/19~21 운영 확인·수정 → 10/22 대회 배포 → 10/23 동결·리허설** — 시연용 자기 연구는 06e·06d 배포 뒤 새로 이어가기로 만든다(키워드 칩·자동 보고서 경로, §12-8). 예시 연구 3건은 그때 코퍼스로 다시 돌려 `mark_example.py` 로 지정한다.

---

## 상태
- [x] code-reviewer 정적 리뷰 통과(발견 사항 반영 완료 — 반영하지 않은 넷은 §3) — 작업별 · 최종 영역별
- [x] 테스트 green — 백엔드 2664 · vitest 1569(dev 받은 뒤, 06e 만 908) · typecheck 0 · build
- [ ] 논문 키워드 채움률 측정·판정(Task Z1 — 사용자 서버 실행)
- [ ] 기록 `total` 처리 결정('확인할 것' 1)
- [ ] 수동 스모크 확인 — 운영 처음부터 끝까지 1회(§5)
- [x] 문서 갱신 — `00_status` · spec (교본은 대회 뒤 round06 한 권 — D13)
- [x] `dev` 머지 승인 — `7d59f72`(2026-10-13), 운영 배포 2026-10-13·운영 확인 수정 배포 2026-10-14(§5)
- [ ] `dev→main` 머지 + push 완료
