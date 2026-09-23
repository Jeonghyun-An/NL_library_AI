# 현재 상태 · 다음 할 일

최종 갱신: 2026-09-23 (round04a 딥리서치 백엔드 — 라이브 검증·머지 전 리뷰 반영 완료, 교본·`dev` 머지 전)

## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/ops/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 완료 — `dev` 머지(`126783d`) + `dev→main` 머지·push 완료.
- round02a: 공공영역 문학 215권 자동 적재 — 계획까지 작성, 구현은 부분 진행(문학 211권 적재됨).
- **round03 종료** — 2026-09-14 `library_catalog` 전멸 사고 복구, doc_type 재기록 운영 실행·라이브 검증, 교본(`docs/guides/round03/` 4챕터)까지 완료하고 `main` 에 머지·push 했다. 상세: `round03-완료노트.md`.
- **round04a 진행 중** — 논문 딥리서치 에이전트 백엔드(계획·탐색·자기점검·종합·Celery·SSE). 운영 `:latest` 배포와 라이브 검증(Step 4~9, 재개 경로 제외)까지 끝났고, 라이브에서 종합이 절 1개만 내던 버그를 고쳐 재배포했다(`b6360b8`). 머지 전 영역별 리뷰 + 적대적 검증(발견 133 · CONFIRMED 118 · 원인 약 18개)을 반영했다 — 취소한 잡이 `completed` 로 되살아나던 high 결함 포함, 테스트 549 passed. **반영분은 아직 운영 미배포**이고 딥리서치 전용 워커(`celery-research`·`celery-research-plan`) 전환은 인덱싱이 끝난 뒤, 또는 적재를 pause 해 in-flight 를 비운 뒤 스택 업데이트로 한다. 서버 `alembic_version` 은 `0005_research_jobs`. 남은 것: 교본·`dev` 머지. 상세: `round04a-완료노트.md`.

### 2026-09-14 사고와 복구 (요약)
`library_catalog` 이 통째로 비워져 고아 문서 72,601건 발생. `book_sections`·Milvus·MinIO 는 무사. 원본 카탈로그 파일과 Milvus 청크에서 전량 복구했고 고아는 0건. **원인은 미확정** — API 경유 삭제는 로그로 배제됐고 직접 SQL 로 추정되나 `log_statement=none` 이라 증거가 없다.

복구 후 신설된 안전장치:
- Postgres 정기 백업(`infra/backup/pg_backup.sh` + 호스트 cron, 복원 연습 완료) — **사고 당시 백업이 전혀 없었다**
- `/api/admin`·`/docs` 게이트웨이 외부 차단
- 읽기 전용 DB 역할 `nl_readonly`
- `log_statement='ddl'` + `log_connections=on`

## 다음 할 일
- **round04a 마무리** — 교본(`docs/guides/round04a/`) → `dev` 머지. 시연 질문·파라미터 선정(기본 파라미터 5~7분 실측 포함)도 여기서. 시연(10월 초 추정)이 인덱싱 완주(11월 초 추정)보다 먼저다 — 시연 전에 전용 워커로 넘길지(적재 pause 후 스택 업데이트), 지금 구성(`q_llm`·`celery-llm`)으로 치르며 시연 구간만 적재를 pause 하고 워밍업할지 정한다(`bulk_ingest_runbook.md` §8).
- **round04a 반영분 운영 배포** — 스키마 변경 없음. **인덱싱이 도는 동안에는 적재 워커를 재생성하지 않는다.** 스택 업데이트는 `:latest` 를 쓰는 적재 워커 전부를, `nl-lib-celery-llm` 컨테이너 Recreate 도 그 순간의 적재 요약·마무리 태스크(최대 4건)를 끊는다 — 볼륨의 데이터는 지워지지 않지만, 끊긴 아이템은 약 2시간 뒤 옛 태스크가 재전달돼 다시 돌면서 논문은 PDF 본문 청크가 초록 청크로 덮일 수 있다(함정 16번). 재생성이 필요하면 **적재를 pause 하고 in-flight 가 0 이 된 뒤** 한다(`bulk_ingest_runbook.md` §8). 그 안에서 `nl-lib-fastapi`·`nl-lib-celery-llm` 컨테이너만 Recreate(1단계)하거나 스택 업데이트로 전용 워커까지 전환(2단계)한다. fastapi 재시작은 lifespan 의 `ALTER TABLE library_catalog` 가 잠금을 기다리는 동안 조회를 줄 세운다(함정 18번). 순서: 완료노트 §5.
- **과도기 구성(`q_llm`·`celery-llm`)에서는 적재가 running 인 동안 운영 딥리서치를 돌리지 않는다** — 실행이 적재 요약·마무리 슬롯을 최대 25분 쥐어, 여럿이면 슬롯을 기다리는 적재 아이템이 stale 복구되고 중복 체인이 논문 본문 청크를 초록으로 덮을 수 있다(함정 16번). 시연 후보 미리 돌리기·기본 파라미터 실측·워밍업도 적재 pause → in-flight 0 확인 뒤에 한다(`bulk_ingest_runbook.md` §8). 반영분부터 API 가 이 구성에서 실행을 한 번에 한 잡으로 묶지만(429) 안전장치일 뿐이고, 지금 운영에서 도는 반영 전 코드에는 상한이 없다.
- **round04b** — 딥리서치 프론트(슬래시 진입·계획 승인·진행 패널·보고서·인용칩·재시도 버튼). 착수 전에 백엔드 보강 목록(SSE 단계 전이 중계·진행 카운터·자기점검 강조 데이터·잡 목록 API)을 보강할지 화면을 맞출지 정한다 — 완료노트 §8.
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
| round04a | [논문 딥리서치 백엔드](round04a-완료노트.md) | 라이브 검증·머지 전 리뷰 반영 완료, 교본·머지 전 |
