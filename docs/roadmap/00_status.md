# 현재 상태 · 다음 할 일

최종 갱신: 2026-09-23 (round04a 딥리서치 백엔드 — 운영 배포·라이브 검증 완료, 머지 전)

## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/ops/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 완료 — `dev` 머지(`126783d`) + `dev→main` 머지·push 완료.
- round02a: 공공영역 문학 215권 자동 적재 — 계획까지 작성, 구현은 부분 진행(문학 211권 적재됨).
- **round03 종료** — 2026-09-14 `library_catalog` 전멸 사고 복구, doc_type 재기록 운영 실행·라이브 검증, 교본(`docs/guides/round03/` 4챕터)까지 완료하고 `main` 에 머지·push 했다. 상세: `round03-완료노트.md`.
- **round04a 진행 중** — 논문 딥리서치 에이전트 백엔드(계획·탐색·자기점검·종합·Celery·SSE). 운영 `:latest` 배포와 라이브 검증(Step 4~9)까지 끝났고, 라이브에서 종합이 절 1개만 내던 버그를 고쳐 재배포했다(`451f348`). 남은 것: 머지 전 리뷰·교본·`dev` 머지. 상세: `round04a-완료노트.md`.

### 2026-09-14 사고와 복구 (요약)
`library_catalog` 이 통째로 비워져 고아 문서 72,601건 발생. `book_sections`·Milvus·MinIO 는 무사. 원본 카탈로그 파일과 Milvus 청크에서 전량 복구했고 고아는 0건. **원인은 미확정** — API 경유 삭제는 로그로 배제됐고 직접 SQL 로 추정되나 `log_statement=none` 이라 증거가 없다.

복구 후 신설된 안전장치:
- Postgres 정기 백업(`infra/backup/pg_backup.sh` + 호스트 cron, 복원 연습 완료) — **사고 당시 백업이 전혀 없었다**
- `/api/admin`·`/docs` 게이트웨이 외부 차단
- 읽기 전용 DB 역할 `nl_readonly`
- `log_statement='ddl'` + `log_connections=on`

## 다음 할 일
- **round04a 마무리** — 머지 전 영역별 code-reviewer 리뷰 → 교본(`docs/guides/round04a/`) → `dev` 머지. 시연 질문·파라미터 선정(기본 파라미터 5~7분 실측 포함)도 여기서.
- **round04b** — 딥리서치 프론트(슬래시 진입·계획 승인·진행 패널·보고서·인용칩).
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
| round04a | [논문 딥리서치 백엔드](round04a-완료노트.md) | 라이브 검증 완료, 리뷰·교본·머지 전 |
