# 대량 인덱싱 파이프라인 — 배포 & 검증 런북

Phase 0~5 구현 완료 후, 컨테이너 환경에서 적용·검증하는 순서. 위에서 아래로 진행.

## 0. 사전 (이미지 재빌드)

신규 의존성(`jinja2`, `PyYAML`)과 신규 모듈이 추가됐으므로 FastAPI/워커 이미지를 재빌드한다.

```bash
docker compose build fastapi
# 워커 4종(celery-worker/cpu/llm/embed/beat)은 같은 이미지(nl-lib-fastapi)를 공유
```

## 1. DB 마이그레이션 (additive — 무중단)

```bash
docker compose exec -w /app fastapi alembic current        # 0003 확인
docker compose exec -w /app fastapi alembic upgrade head    # → 0004
```

0004가 하는 일 (전부 additive, 기존 데이터 영향 없음):
- `library_catalog.doc_type`(+인덱스), `library_catalog.extra JSONB` 추가
- KCI 행 `doc_type='paper'` 백필
- `ingest_jobs`, `ingest_job_items` 테이블 생성

## 2. 워커/스케줄러 기동

```bash
docker compose up -d celery-cpu celery-llm celery-embed celery-beat
docker compose ps      # 5개 워커 + beat 가 Up 인지 확인
docker compose logs -f celery-beat   # dispatch-job-items 30s, cleanup-temp-files 1h 스케줄 로그
```

## 3. 단건 흐름 회귀 스모크 (Milvus 스키마 변경 전)

> ⚠️ 주의: `MILVUS_RECREATE_ON_MISMATCH`를 켜기 전에는, doc_type 스칼라가 추가된
> 새 스키마와 기존 컬렉션이 불일치하여 인덱싱이 **RuntimeError로 안전하게 중단**된다.
> 이는 의도된 가드다 (기존 인덱스 무단 삭제 방지). 아래 4단계에서 재생성한다.

기존 검색이 정상인지만 먼저 확인:
```bash
curl -s -X POST http://<host>/api/books/search \
  -H 'Content-Type: application/json' -d '{"query":"인공지능","mode":"book"}' | head
```

## 4. Milvus 컬렉션 재생성 (doc_type 스칼라 추가 — 1회, 재인덱싱 필요)

30만건 시작 **직전** 1회만. 대량 인덱싱용 인덱스 파라미터를 함께 적용한다.

`.env` 또는 compose 環경변수:
```
MILVUS_RECREATE_ON_MISMATCH=true
MILVUS_INDEX_TYPE=IVF_SQ8
MILVUS_NLIST=16384
MILVUS_NPROBE=64
EMBEDDING_BATCH_SIZE=64
LLM_SECTION_CONCURRENCY=4
INGEST_HIGH_WATER=32
```

재생성 (기존 컬렉션 drop → 새 스키마):
```bash
docker compose exec fastapi python -c "
from services.ingestion.indexer import ensure_collection
ensure_collection()
print('recreated')
"
docker compose restart fastapi celery-worker celery-embed   # 모듈 캐시 리셋
```

> 재생성 후에는 기존 도서를 다시 인덱싱해야 한다(소량이면 단건 흐름, 대량이면 잡).
> 운영 중 실수 방지를 위해 재생성 완료 후 `MILVUS_RECREATE_ON_MISMATCH=false`로 되돌릴 것.

## 5. 단건 인덱싱 스모크 (새 스키마)

PDF 1건 업로드 → 4단계(extract→summarize→embed_index→finalize) 완료 확인:
```bash
curl -s -X POST http://<host>/api/books/ingest/upload -F "file=@sample.pdf"
# ingest-status 폴링
curl -s http://<host>/api/books/<cnts_id>/ingest-status
```
로그에서 `scalar: {... 'doc_type': ...}` 가 찍히는지, 검색에 노출되는지 확인.

## 6. 소량 배치 잡 E2E (10건)

```bash
# 로컬: 매니페스트 생성 (scripts/bulk_ingest/README.md 참조)
python scripts/bulk_ingest/build_manifest.py --excel meta.xlsx --pdf-dir ./pdfs --out ./out
# 검증 리포트 확인 후 rclone/upload_from_manifest.py 로 MinIO 업로드
# 매니페스트도 MinIO manifests/test/ 로 업로드

# 잡 생성 (dry-run 검증 → ready)
curl -s -X POST http://<host>/api/admin/ingest-jobs -H 'Content-Type: application/json' \
  -d '{"name":"smoke-10","manifest_key":"manifests/test/manifest.jsonl","params":{"skip_cover":true,"doc_type":"paper"}}'
# 시작
curl -s -X POST http://<host>/api/admin/ingest-jobs/<job_id>/start
# 진행 현황 (대시보드: /admin/jobs)
curl -s http://<host>/api/admin/ingest-jobs/<job_id>
```

확인 포인트:
- stage가 pending→extracted→summarized→indexed→finalized로 진행
- 일부러 실패 유발(잘못된 PDF) → `/failures`에 error_group별 집계 → 그룹 재시도 → 복구
- 워커 강제 kill → 다음 디스패처 주기(30s)에 stale 복구되는지(`error_group='stale'`)

## 7. 본 가동 전 파일럿 (1,000건)

- 건당 처리시간 분포, VLM 폴백률(`item.meta.extract_method`), 시간당 처리율/ETA 확인
- `INGEST_HIGH_WATER`/워커 concurrency 튜닝 → 일 4,000건 처리율 달성 확인 후 30만건 1회차

## 롤백

- 코드: 이전 이미지 태그로 `docker compose up -d`
- DB: `alembic downgrade 0003_widen_varchar_fields` (doc_type/extra/잡 테이블 제거 — additive라 안전)
- Milvus: 인덱스 파라미터 env를 되돌리고 재생성하면 IVF_FLAT로 복귀
