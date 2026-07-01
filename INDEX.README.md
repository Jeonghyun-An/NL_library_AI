# NL Library AI - Ingest Job 관리(1000권 논문 재처리 로직)

## 1. 전체 아이템 pending 리셋 (stage도 처음부터)

curl -X POST http://localhost:18002/api/admin/ingest-jobs/3d2a5e06-38d4-4b3c-ba98-1388218848d4/retry \
 -H "Content-Type: application/json" \
 -d '{"force_all": true, "reset_stage": "pending"}'

## 2. 잡 시작

curl -X POST http://localhost:18002/api/admin/ingest-jobs/3d2a5e06-38d4-4b3c-ba98-1388218848d4/start
reset_stage: "pending" 을 주면 extract(OCR) → summarize → embed_index 전 단계 재실행입니다.

## 3. 잡 상태 확인

curl http://localhost:18002/api/admin/ingest-jobs/3d2a5e06-38d4-4b3c-ba98-1388218848d4
