# 현재 상태 · 다음 할 일

최종 갱신: 2026-09-08 (round01 dev 머지 완료, main 반영 대기)

## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/ops/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 — `dev` 머지 완료(`126783d`). `dev→main` 머지 + push는 사용자의 라운드 종료 승인 대기 중(`CLAUDE.md` §2 정의상 그때까지가 라운드다).

## 다음 할 일
- round01: 라운드 종료(`dev→main` 머지 + push) 승인 받으면 이 문서를 "완료"로 갱신한다. 다음 라운드 범위는 미정 — 착수 시 이 문서와 `README.md` §10 로드맵을 함께 갱신한다.
- **[보류 — 도서관 대회 시연 이후]** `app/api/admin.py` Milvus expression injection 보안 수정. 대회 전까지는 손대지 않는다(`round01-완료노트.md` §이월 참고).

## 라운드 이력
| 라운드 | 요약 | 상태 |
|---|---|---|
| round01 | [개발 체계 도입](round01-완료노트.md)(museum 스타일 이식) | dev 머지 완료(main 반영 대기) |
