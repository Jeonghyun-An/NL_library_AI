# 현재 상태 · 다음 할 일

최종 갱신: 2026-10-02 (round05a `dev` 머지(`f293e0e`)·운영 배포(`nl-lib-nuxt`) — `main` 머지와 push 는 라운드 종료 승인 뒤 `/round-finish` 에서. round04b·round04c 종료, round07b `dev` 머지, round07 구현·리뷰 마무리·배포 대기, round06 기획 중단)

## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/ops/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 완료 — `dev` 머지(`126783d`) + `dev→main` 머지·push 완료.
- round02a: 공공영역 문학 215권 자동 적재 — 계획까지 작성, 구현은 부분 진행(문학 211권 적재됨).
- **round03 종료** — 2026-09-14 `library_catalog` 전멸 사고 복구, doc_type 재기록 운영 실행·라이브 검증, 교본(`docs/guides/round03/` 4챕터)까지 완료하고 `main` 에 머지·push 했다. 상세: `round03-완료노트.md`.
- **round04a 종료** — 논문 딥리서치 에이전트 백엔드(계획·탐색·자기점검·종합·Celery·SSE). 운영 라이브 검증(Step 4~9, 재개 경로 제외) 중 종합이 절 1개만 내던 버그를 고쳤고(`b6360b8`), 머지 전 영역별 리뷰 + 적대적 검증(발견 133 · CONFIRMED 118 · 원인 약 18개)을 반영했다 — 취소한 잡이 `completed` 로 되살아나던 high 결함 포함, 테스트 549 passed. **반영분은 2026-09-23 18:23 KST 운영 배포 완료** — 적재 pause·in-flight 0 안에서 스택 업데이트로 딥리서치 전용 워커(`nl-lib-celery-research`·`nl-lib-celery-research-plan`)로 전환했고, 워밍업 잡이 30초에 끝났다(리랭커 `cuda`). 교본 `docs/guides/round04a/` 5챕터 작성. `dev`·`main` 머지와 push 로 라운드를 닫았다. 상세: `round04a-완료노트.md`.
- **round04b 종료** — `dev`(`9b776d2`)·`main` 머지와 push(2026-10-01). 딥리서치 화면(계획 카드·진행 패널·보고서·인용칩 팝오버)·기록 세션 서버 저장(`history_items`, 마이그레이션 `0006`)·입력창 + 메뉴와 슬래시 명령, 그리고 spec §14 보고서 작성 대기 화면(다 쓴 절부터 초안·남은 시간)·Word·PDF 내보내기. 브랜치 `feat/round04b-deep-research-frontend` 커밋 120개(2026-09-26~29). 교본 `docs/guides/round04b/` 6챕터.
  - **운영 배포 2026-09-28** — 적재 워커는 건드리지 않고 `nl-lib-fastapi`·`nl-lib-celery-research`·`nl-lib-celery-research-plan`·`nl-lib-nuxt` 를 컨테이너별로 Recreate, `alembic stamp 0006_history_items`(서버 `alembic_version` 은 이제 `0006_history_items`). 배포 직후 게이트웨이가 502 를 냈다 — nginx 가 Recreate 전 컨테이너 IP 로 보내고 있었고 `docker exec nl-lib-gateway nginx -s reload` 로 풀었다(함정 20번). SSE 는 게이트웨이 설정을 바꾸지 않고 통과했다(`X-Accel-Buffering: no` + 15초 하트비트). 같은 날 §14 를 `celery-research`·`nuxt` 로 배포했다.
  - 2026-09-29 사용자 확인: 작성 중 초안 화면이 동적으로 바뀌고 Word·PDF 둘 다 정상. 기획자 시연(2026-09-28) 피드백은 배치 A(우측 패널 과정)가 덜 인터랙티브해 보인다는 것 — 화면은 인터랙티브함을 최우선으로 한다(spec §7-4).
- **round04c 종료** — `dev`(`3dfeb45`)·`main` 머지와 push(2026-10-01). 딥리서치 보고서 품질 A·B·C·G: 하위질문별 근거 예산(A), 자기점검이 무관하다고 본 근거 제외(B)와 제외한 논문을 타임라인·보고서·문서에 보이기·카운터 "제외"·잡 파라미터 `exclude_off_topic` 으로 끄기(spec §11), 계획을 원 질문의 핵심 개념 중심으로(C), 문체 "~다" 통일(G). 브랜치 `feat/round04c-research-quality` 커밋 42개(2026-09-29~30). 교본 `docs/guides/round04c/` 4챕터.
  - 계기: round04b 운영 검증 잡 "컴퓨팅 자원에 대한 연구가 궁금해"(2026-09-29 10:20) — 6절 27편, 근거 60 중 HPC 32·자원관리 2, 엣지 절에 의료영상 Edge method 처럼 같은 단어·다른 뜻 논문. 같은 질문의 DBpia AI 답변과 비교해 착수했다.
  - **운영 배포 2026-09-30** — 워커 먼저 → fastapi → nuxt → `nginx -s reload`. 배포 뒤 첫 잡 `2a56f8b6-e841-4a3c-88e6-9ccc6e76908b`(같은 질문): 6절, papers 합 30(서로 다른 27), 검토 121·채택 48·제외 91건·재검색 16, started→finished 1분 42초. 수치는 합격선(spec §11-4)이지만 **질 문제가 남았다** — 다음 할 일.
  - 같은 날 사용자 요청 화면 수정 3가지 — 제외 캡션 문구(`a303325`), 딥리서치 배치 자동 전환(보고서 전 B·보고서가 나오면 A, localStorage 기억 폐지 — `2e3d87a`), 예시 질의는 입력창만 채움(`2d8320d`) — 와 로컬 화면을 운영 API 에 붙이는 미리보기 설정(`frontend-prod-api`, `9bba9c4`)도 이 브랜치에 커밋됐다.
- **round05a — `dev` 머지·운영 배포, `main` 머지 대기** — 논문 상세 재구현(UI 고도화 기능 명세서 03·S6, 사용자 결정 "보던 곳의 위치로까지 그대로" — A안). 상세 주소에 출처(`from=search`·`research`)와 돌아갈 자리(`at`·`y`)를 싣고, [돌아가기]로 보고서의 그 인용칩·검색 결과의 그 카드까지 같은 화면 높이로 복원한다(맞춘 뒤 붙잡기, 자리를 그 기록의 `history.state` 에도 남김). 사이드바는 출처를 따라 강조한다. 03 화면(인용 맥락 배너·관련도는 검색에서만·DeepRead 이름 통일·원문 보기는 늘 원문 뷰어·AI 요약 기준 질문과 탭 캐시·키워드 검색·연관 논문 링크·탭 제목·이 논문으로 딥리서치 초안)과 원문 뷰어(Esc·초점·배경 고정·쪽 표시·인용 대목 넘기기·열기 전 확인 공용화·pdf.js 글꼴 eval 끄기 — CVE-2024-4367). 백엔드 변경 없음. 브랜치 `feat/round05a-paper-detail` 커밋 22개(2026-10-01~02), `dev` 머지 `f293e0e`(2026-10-02, round07b `5fa1a38` 위에 충돌 없이). 테스트: 프론트 vitest 21파일 406 → 28파일 495·typecheck 오류 0·빌드 완료, 백엔드 pytest 890(브랜치)·`dev` 머지 뒤 1369. 교본 `docs/guides/round05a/00-개요.md`. `main` 머지·push 는 라운드 종료 승인 뒤(`/round-finish`) 한다. 상세: `round05a-완료노트.md`.
  - **운영 배포 2026-10-02** — 사용자가 `nl-lib-nuxt` 만 Recreate(빌드는 `dev` `f293e0e` 내용, `frontend/public/pdfjs` 가 있는 폴더에서) → 게이트웨이 reload. 백엔드 변경이 없어 fastapi·워커는 대상이 아니다. 같은 이미지로 round07b 화면(`/search-classic`)도 함께 나갔다. 배포 직후 확인: 탭 제목·"검색으로"·DeepRead·이 논문으로 딥리서치 칸, `/search-classic` 200, 원문 뷰어 1/31쪽·Esc·초점·`isEvalSupported=false`·`externalLinkTarget=2`.
  - 보고서 인용칩 왕복(spec §7 ①~④·⑪)은 검증 브라우저에 딥리서치 기록이 없어 화면으로 보지 못했다 — 다음 할 일.
- **round06 — 기획 중단** — 딥리서치를 논문 에이전트 플랫폼(질문 → 문헌 탐색 → 주제 후보·읽기 목록 → 연구계획서형 초안)으로 넓히는 브레인스토밍. 브랜치 `feat/round06-paper-agent`(dev `138a467` 에서 분기, worktree `.worktrees/round06`). 2026-10-01 기술 구조(설계 ③)와 검증 기준까지 승인된 상태에서 적재 수정(round07)을 먼저 하려고 멈췄다 — 일정(④)이 남았고, spec 은 아직 쓰지 않았다.
- **round07 — 구현·리뷰 마무리, 배포 대기(사용자가 런북 §9 로 배포)** — 적재 파이프라인 보강(spec §2 의 18개). 브랜치 `feat/round07-ingest-pipeline-fix`(dev `9798f46` 에서 분기, worktree `.worktrees/round07`), 설계 `docs/superpowers/specs/2026-10-01-round07-ingest-pipeline-fix-design.md`, 계획 `docs/superpowers/plans/2026-10-01-round07-ingest-pipeline-fix.md`. 배포·카나리·재처리 절차는 `bulk_ingest_runbook.md` §9, 고친 함정은 16번(근본 수정)·21번. 본 잡 `kci-full-236k` 는 2026-10-01 사용자가 pause 했다(in-flight 0, 08:11 UTC 확인) — 배포(§9) 전까지 그대로 둔다.
- **round07b — `dev` 머지(`5fa1a38`)** — 초기 SKOVIX 화면 `/search-classic` 복원(round04b 에서 지운 보존 화면, 되살린 세 파일은 `@ts-nocheck` — 사용자 결정). 2026-10-02 round05a 의 `nl-lib-nuxt` 배포로 운영에 함께 나갔다(`/search-classic` 200).
- **적재 현황(2026-09-29)** — `kci-full-236k` 47%: done 111,658 / pending 123,979 / failed 782. 항목 번호(옛 논문) 순으로 돌아 딥리서치 코퍼스가 아직 2013년까지다. 하루 약 5,200건 → **10월 23일쯤 완료 예상(목표 10월 28일)**. 최신순 재배열은 하지 않기로 했다.
- **적재 진단(2026-10-01, round07 착수 근거)** — 48시간 완료 11,510건(하루 5,755건). 병목 두 곳이 번갈아 막는다. 일반 PDF(ODL) 문서는 `celery-embed` 1칸 안에서 논문 보강 LLM 을 기다리는 시간(embed 의 46~59%) 때문에 약 300건/h, 스캔본은 쪽을 하나씩 OCR 하는 추출 4칸 때문에 약 50건/h 다. GPU 서버는 여유가 있다(gemma 평균 5~8/16석, VLM 1.9/8석). 결함도 여럿이다 — 텍스트 층에 몇 글자만 남은 스캔본이 VLM 을 건너뛰어 섹션 0개로 영구 실패하고(10-01 281건, 함정 21번), 문서 요약 입력의 균등 샘플링이 마지막 섹션을 빼고, LLM·VLM 잘림을 감지하지 않으며(gemma 응답 5.3%·VLM 3.8%), 빈 본문으로 완료된 문서가 약 900건(추정)이고, 중복 체인이 논문 본문을 초록으로 덮는 경로(함정 16번)가 열려 있다. 고칠 것 18개는 spec §2, 재처리는 실패 1,099건과 빈 본문 완료분만 배포 직후에 한다. 지금 설정이면 남은 약 11.3만 건은 10/19~24 완료로 추정했다(잡 API 의 ETA 856시간은 스캔본이 몰린 1시간 창 값이었다).

### 2026-09-14 사고와 복구 (요약)
`library_catalog` 이 통째로 비워져 고아 문서 72,601건 발생. `book_sections`·Milvus·MinIO 는 무사. 원본 카탈로그 파일과 Milvus 청크에서 전량 복구했고 고아는 0건. **원인은 미확정** — API 경유 삭제는 로그로 배제됐고 직접 SQL 로 추정되나 `log_statement=none` 이라 증거가 없다.

복구 후 신설된 안전장치:
- Postgres 정기 백업(`infra/backup/pg_backup.sh` + 호스트 cron, 복원 연습 완료) — **사고 당시 백업이 전혀 없었다**
- `/api/admin`·`/docs` 게이트웨이 외부 차단
- 읽기 전용 DB 역할 `nl_readonly`
- `log_statement='ddl'` + `log_connections=on`

## 다음 할 일
- **round07 배포** — 사용자가 `bulk_ingest_runbook.md` §9 순서로 한다: 비움 확인 → 이미지 빌드·pull → 스택 업데이트(바뀐 곳만, Re-pull 끔, **FLUX 를 켜지 않는다**) → 게이트웨이 reload → 카나리 잡과 지표(멈춤 기준) → 본 잡 실패분 retry → 본 잡 resume → 빈 본문 목록 retry. 그때까지 본 잡은 paused 로 둔다. 배포·운영 확인 뒤 dev 머지(사용자 승인)로 라운드를 닫는다. 이번에 하지 않기로 한 것(임베딩 512 절단 등)은 spec §3.
- **round06 재개** — round07 배포와 본 잡 재개 뒤 `.worktrees/round06` 에서 브레인스토밍 일정(④)부터 이어 spec 을 쓴다.
- **round05a 후속** — ① 운영에서 보고서 인용칩 왕복 확인(칩 → 상세 → [딥리서치 보고서로], 앞으로 갔다 다시, 배치 A/B, 새 탭으로 연 제외 논문 — spec §7 ①~④·⑪) ② 원문 뷰어의 pdf.js(`frontend/public/pdfjs` 4.0.379)를 4.2.67 이상으로 올리기 — 지금은 끼운 뷰어에서만 CVE-2024-4367 설정이 걸리고 `/pdfjs/web/viewer.html` 을 바로 열면 걸리지 않는다 ③ 제외 논문 앵커를 담는 곳별로(`t-…`) — 보고서 제외 목록과 탐색 타임라인의 같은 논문이 같은 앵커 `x-<cnts>` 다 ④ 03-1 도서 상세에 같은 돌아가기·위치 복원(spec §8) ⑤ 인용칩 팝오버의 [원문 보기]에도 대목 목록 넘기기. nuxt 이미지는 `frontend/public/pdfjs`(gitignore)가 있는 폴더에서 빌드한다. 라운드 종료(`dev→main` 머지·push)는 사용자 승인 뒤 `/round-finish`. 상세: `round05a-완료노트.md` §9.
- **round04c 품질 후속** — 배포 뒤 첫 잡에서 남은 문제: ① 계획이 여전히 일반 틀(정의·방법론·적용 분야·성과·한계·동향)이라 C 미달이고, 6개 하위질문 모두 재검색 한도까지 "근거 부족" ② 과잉 제외 — 「프록시기반 모바일 그리드 자원관리」·「웹기반 대용량 계산환경」처럼 주제에 맞는 논문을 하위질문 측면에 안 맞는다고 뺐다 ③ 반대로 방법론 절에 「DI 한글읽기프로그램」·「발명교육」이 근거로 들어갔다. 대응: spec §11-4 의 "어긋나면" — 제외 기준을 "원 질문 주제와 명백히 무관한 것만"으로 좁히고(`app/domains/nl_library/prompts/research_critique.yaml`), 계획 프롬프트(`research_plan.yaml`)를 다시 본다. 그다음 묶음은 D 핵심 요약·주제 종합, E 이어서 물어보기, F 화면 참고문헌(spec §8).
- ~~**[배포] 04c 운영 확인을 반영한 화면 수정**~~ — **해소(2026-10-02).** `a303325`·`2e3d87a`·`2d8320d` 는 `dev` 에 있어, round05a 의 `nl-lib-nuxt` 배포(`dev` `f293e0e` 로 빌드)에 함께 나갔다.
- **round04a 후속** — 시연 질문·파라미터 선정(spec 설계값 5~7분 대비 실측 포함). 손상 의심 논문 2건 확인·미병합 브랜치 `hyoni2/epic-ishizaka-cf9743`(chunk_kinds) 정리·Portainer 스택과 저장소 compose 맞추기는 round04a 완료노트 §8.
- **인덱싱 워커를 재생성하는 배포 규칙** — 스택 업데이트는 `:latest` 를 쓰는 적재 워커 전부를, `nl-lib-celery-llm` 컨테이너 Recreate 도 그 순간의 적재 요약·마무리 태스크를 끊는다. 볼륨 데이터는 지워지지 않지만 끊긴 아이템은 약 2시간 뒤 옛 태스크가 재전달돼 다시 돌면서 논문은 PDF 본문 청크가 초록 청크로 덮일 수 있다(함정 16번). **적재를 pause 하고 in-flight 가 0 이 된 뒤** 재생성한다(`bulk_ingest_runbook.md` §8). Portainer 스택 업데이트는 새 이미지를 미리 `docker pull` 해 두고 **"Re-pull image" 토글을 끄고** 한다(켜면 500 — 함정 12번, 2026-09-23 재발). 적재 중 딥리서치·화면 배포는 round04b·04c 처럼 바뀐 컨테이너만 Recreate 하고, `nl-lib-fastapi`·`nl-lib-nuxt` 를 Recreate 했으면 **마지막에 `docker exec nl-lib-gateway nginx -s reload`** 한다(함정 20번).
- **[게이트웨이] upstream 이름 재해석** — reload 를 빠뜨리면 502 가 나는 구조 자체의 근본 해결로 `resolver 127.0.0.11` + upstream `server … resolve`(nginx 1.27.3+, `zone` 필요)를 검토한다. 게이트웨이 이미지가 버전 고정 없는 `nginx:alpine` 이라 서버 버전부터 확인 — 함정 20번.
- **[적재] `kci-full-236k` 완주 뒤** — ① 추가 수집: 메타 없는 PDF 28,074편, 연도별 1만 건 상한 뒤 나머지(수집기가 KCI 검색 200쪽 상한을 봇 탐지로 오인한다) ② 모델 교체: Qwen3.6-35B-A3B-FP8 로 OCR·텍스트 통합 검토. 둘 다 적재가 끝난 뒤 한다. 적재 코드의 근본 원인(단계 래퍼가 `done` 을 보지 않음·stale 복구가 옛 태스크를 revoke 하지 않음 — 함정 16번)은 round07 에서 고쳤다(배포 대기 — 함정 16번 근본 수정).
- **[적재] 손상 의심 논문 2건** — stale 복구를 거친 `KCI_FI001484600`·`KCI_FI001484593`. 옛 체인 재실행 흔적은 없으나 Redis `unacked`·Milvus 청크로 확인 필요. 나중에 한꺼번에 처리 — round04a 완료노트 §8.
- **[보안] Redis 무인증 호스트 노출(prod 16379·dev 26379)** — round03 이월에서 추적이 끊겼던 항목. round04a 부터 SSE 중계 입력으로 쓰인다. 대회 전 조치 여부는 사용자 결정.
- **논문 참고문헌 — 완료** — 섹션 원문 재추출로 1차 30,532건 + 2차 6,931건 = **37,463건 / 71,931건(52.1%)**. `jsonb_array_length` 기준 재측정으로 확정했고 빈 배열은 0건이었다. 남은 34,468건은 참고문헌 섹션이 없거나 OCR 이 깨진 문서라 패턴 추출로는 더 못 건진다. 대상 선정 조건은 길이 기준(`_EMPTY_REFS`)으로 고쳐 뒀다 — 재인덱싱이 돌면 빈 배열이 생기므로 그때 필요하다.
- 논문 `summary` 29,006건 재생성 — 복원 소스 없음, LLM 만 가능(단일 63시간/4병렬 16시간). 초록이 채워져 화면은 정상이라 급하지 않음.
- `docs/superpowers/specs/2026-09-15-search-top-pick-recommend-design.md` — 검색 결과 최상위 1권 자동추천 기획 초안(별도 세션 작성) 대기.
- **[보류 — 도서관 대회 시연 이후]** `app/api/admin.py` Milvus expression injection 보안 수정. 대회 전까지는 손대지 않는다(`round01-완료노트.md` §이월 참고).

## 라운드 이력
| 라운드 | 요약 | 상태 |
|---|---|---|
| round01 | [개발 체계 도입](round01-완료노트.md)(museum 스타일 이식) | 완료 |
| round02a | 공공영역 문학 215권 자동 적재 | 계획 완료, 구현 부분 진행 |
| round03 | [카탈로그 전멸 복구 + doc_type 오분류 교정](round03-완료노트.md) · [교본](../guides/round03/00-개요.md) | 완료 (`main` 머지·push) |
| round04a | [논문 딥리서치 백엔드](round04a-완료노트.md) · [교본](../guides/round04a/00-개요.md) | 완료 (`main` 머지·push) |
| round04b | [딥리서치 화면·기록 세션·보고서 작성 대기 화면·Word·PDF 내보내기](round04b-완료노트.md) · [교본](../guides/round04b/00-개요.md) | 완료 (`main` 머지·push) |
| round04c | [딥리서치 보고서 품질(근거 예산·무관 제외·계획·문체)](round04c-완료노트.md) · [교본](../guides/round04c/00-개요.md) | 완료 (`main` 머지·push) |
| round05a | [논문 상세 재구현(돌아가기·주소·보던 위치 복원·03 화면·원문 뷰어)](round05a-완료노트.md) · [교본](../guides/round05a/00-개요.md) | dev 머지·운영 배포 (main 머지 대기) |
| round06 | 논문 에이전트 플랫폼(딥리서치 → 주제 후보·읽기 목록·계획서 초안) | 기획 중단 (`feat/round06-paper-agent`, 브레인스토밍 ③까지 승인) |
| round07 | 적재 파이프라인 보강(병목 두 곳·스캔본 라우팅·중복 체인 차단) | 구현·리뷰 마무리, 배포 대기 (`feat/round07-ingest-pipeline-fix`) |
