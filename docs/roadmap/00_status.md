# 현재 상태 · 다음 할 일

최종 갱신: 2026-09-23 (round04a 딥리서치 백엔드 — 리뷰 반영분 운영 배포·전용 워커 전환·교본 완료, `dev` 머지 전)

## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/ops/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 완료 — `dev` 머지(`126783d`) + `dev→main` 머지·push 완료.
- round02a: 공공영역 문학 215권 자동 적재 — 계획까지 작성, 구현은 부분 진행(문학 211권 적재됨).
- **round03 종료** — 2026-09-14 `library_catalog` 전멸 사고 복구, doc_type 재기록 운영 실행·라이브 검증, 교본(`docs/guides/round03/` 4챕터)까지 완료하고 `main` 에 머지·push 했다. 상세: `round03-완료노트.md`.
- **round04a 진행 중** — 논문 딥리서치 에이전트 백엔드(계획·탐색·자기점검·종합·Celery·SSE). 운영 라이브 검증(Step 4~9, 재개 경로 제외) 중 종합이 절 1개만 내던 버그를 고쳤고(`b6360b8`), 머지 전 영역별 리뷰 + 적대적 검증(발견 133 · CONFIRMED 118 · 원인 약 18개)을 반영했다 — 취소한 잡이 `completed` 로 되살아나던 high 결함 포함, 테스트 549 passed. **반영분은 2026-09-23 18:23 KST 운영 배포 완료** — 적재 pause·in-flight 0 안에서 스택 업데이트로 딥리서치 전용 워커(`nl-lib-celery-research`·`nl-lib-celery-research-plan`)로 전환했고, 워밍업 잡이 30초에 끝났다(리랭커 `cuda`). 교본 `docs/guides/round04a/` 5챕터 작성. 서버 `alembic_version` 은 `0005_research_jobs`. 남은 것: `dev` 머지 → `main`. 상세: `round04a-완료노트.md`.

### 2026-09-14 사고와 복구 (요약)
`library_catalog` 이 통째로 비워져 고아 문서 72,601건 발생. `book_sections`·Milvus·MinIO 는 무사. 원본 카탈로그 파일과 Milvus 청크에서 전량 복구했고 고아는 0건. **원인은 미확정** — API 경유 삭제는 로그로 배제됐고 직접 SQL 로 추정되나 `log_statement=none` 이라 증거가 없다.

복구 후 신설된 안전장치:
- Postgres 정기 백업(`infra/backup/pg_backup.sh` + 호스트 cron, 복원 연습 완료) — **사고 당시 백업이 전혀 없었다**
- `/api/admin`·`/docs` 게이트웨이 외부 차단
- 읽기 전용 DB 역할 `nl_readonly`
- `log_statement='ddl'` + `log_connections=on`

## 다음 할 일
- **round04a 마무리** — `dev` 머지 → `dev→main` 머지·push. 시연 질문·파라미터 선정(기본 파라미터 5~7분 실측 포함)은 전용 워커 구성에서 한다 — 이제 적재가 돌아도 딥리서치는 적재 큐와 분리돼 있다.
- **인덱싱 워커를 재생성하는 배포 규칙** — 스택 업데이트는 `:latest` 를 쓰는 적재 워커 전부를, `nl-lib-celery-llm` 컨테이너 Recreate 도 그 순간의 적재 요약·마무리 태스크를 끊는다. 볼륨 데이터는 지워지지 않지만 끊긴 아이템은 약 2시간 뒤 옛 태스크가 재전달돼 다시 돌면서 논문은 PDF 본문 청크가 초록 청크로 덮일 수 있다(함정 16번). **적재를 pause 하고 in-flight 가 0 이 된 뒤** 재생성한다(`bulk_ingest_runbook.md` §8). Portainer 스택 업데이트는 새 이미지를 미리 `docker pull` 해 두고 **"Re-pull image" 토글을 끄고** 한다(켜면 500 — 함정 12번, 2026-09-23 재발).
- **[적재] 손상 의심 논문 2건** — stale 복구를 거친 `KCI_FI001484600`·`KCI_FI001484593`. 옛 체인 재실행 흔적은 없으나 Redis `unacked`·Milvus 청크로 확인 필요. 나중에 한꺼번에 처리 — 완료노트 §8.
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
| round04a | [논문 딥리서치 백엔드](round04a-완료노트.md) · [교본](../guides/round04a/00-개요.md) | 리뷰 반영·운영 배포·교본 완료, `dev` 머지 전 |
