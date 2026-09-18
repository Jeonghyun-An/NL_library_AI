# 현재 상태 · 다음 할 일

최종 갱신: 2026-09-17 (round03 — 사고 복구·본 스코프·교본 완료, 머지 대기)

## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/ops/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 완료 — `dev` 머지(`126783d`) + `dev→main` 머지·push 완료.
- round02a: 공공영역 문학 215권 자동 적재 — 계획까지 작성, 구현은 부분 진행(문학 211권 적재됨).
- **round03** — 2026-09-14 `library_catalog` 전멸 사고 복구 완료, doc_type 재기록도 운영 실행·라이브 검증까지 완료. 교본(`docs/guides/round03/`, 4챕터 3,089줄)까지 작성했다. 상세: `round03-완료노트.md`.

### 2026-09-14 사고와 복구 (요약)
`library_catalog` 이 통째로 비워져 고아 문서 72,601건 발생. `book_sections`·Milvus·MinIO 는 무사. 원본 카탈로그 파일과 Milvus 청크에서 전량 복구했고 고아는 0건. **원인은 미확정** — API 경유 삭제는 로그로 배제됐고 직접 SQL 로 추정되나 `log_statement=none` 이라 증거가 없다.

복구 후 신설된 안전장치:
- Postgres 정기 백업(`infra/backup/pg_backup.sh` + 호스트 cron, 복원 연습 완료) — **사고 당시 백업이 전혀 없었다**
- `/api/admin`·`/docs` 게이트웨이 외부 차단
- 읽기 전용 DB 역할 `nl_readonly`
- `log_statement='ddl'` + `log_connections=on`

## 다음 할 일
- **논문 참고문헌 — 완료(추가 개선 여지 있음)** — 섹션 원문 재추출로 1차 30,532건, `extract_references()` 보강(`bdbf86c`, 붙은 헤더·구분자 없는 `저자(연도)` 항목 인식) 후 2차 6,931건을 더 살려 **누적 37,463건**. 남은 34,468건은 참고문헌 섹션이 없거나 OCR 이 깨진 경우다. 다만 2차 반영분은 한 줄에 여러 항목이 뭉친 문서에서 **항목이 합쳐진 채로** 저장돼 있다 — 줄 내부 분할을 넣으면 `restore_references_from_sections.py --force` 로 덮어쓸 수 있다(가드 기본값은 기록된 문서를 건너뛴다).
- 논문 `summary` 29,006건 재생성 — 복원 소스 없음, LLM 만 가능(단일 63시간/4병렬 16시간). 초록이 채워져 화면은 정상이라 급하지 않음.
- `docs/superpowers/specs/2026-09-15-search-top-pick-recommend-design.md` — 검색 결과 최상위 1권 자동추천 기획 초안(별도 세션 작성) 대기.
- **[보류 — 도서관 대회 시연 이후]** `app/api/admin.py` Milvus expression injection 보안 수정. 대회 전까지는 손대지 않는다(`round01-완료노트.md` §이월 참고).

## 라운드 이력
| 라운드 | 요약 | 상태 |
|---|---|---|
| round01 | [개발 체계 도입](round01-완료노트.md)(museum 스타일 이식) | 완료 |
| round02a | 공공영역 문학 215권 자동 적재 | 계획 완료, 구현 부분 진행 |
| round03 | [카탈로그 전멸 복구 + doc_type 오분류 교정](round03-완료노트.md) · [교본](../guides/round03/00-개요.md) | 완료 |
