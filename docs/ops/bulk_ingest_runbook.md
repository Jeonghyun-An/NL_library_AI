# 대량 인덱싱 파이프라인 — 배포 & 검증 런북

Phase 0~5 구현 완료 후, 컨테이너 환경에서 적용·검증하는 순서. 위에서 아래로 진행.

## 0. 사전 (이미지 재빌드)

신규 의존성(`jinja2`, `PyYAML`)과 신규 모듈이 추가됐으므로 FastAPI/워커 이미지를 재빌드한다.

```bash
docker compose build fastapi
# 워커 4종(celery-worker/cpu/llm/embed/beat)은 같은 이미지(nl-lib-fastapi)를 공유
```

> **대량 인덱싱이 도는 중이면 스택을 업데이트하지 않는다.** 앱 서비스가 전부 같은 `:latest` 라 스택 업데이트 한 번이 도는 적재 워커를 모두 재생성하고, 진행 중이던 아이템이 끊긴다. 볼륨의 데이터는 지워지지 않지만, 끊긴 아이템은 stale 복구로 다시 끝난 뒤 약 2시간 뒤 브로커가 옛 태스크를 재전달해 단계가 한 번 더 돈다 — 논문은 PDF 본문 청크가 초록 청크로 덮일 수 있다(`docs/ops/recurring-gotchas.md` 16번). 꼭 재생성해야 하면 **§8 대로 적재를 pause 하고 in-flight 가 0 이 된 뒤** 한다. 딥리서치 전용 워커(`celery-research`·`celery-research-plan`) 전환도 인덱싱이 끝난 뒤, 또는 §8 절차 안에서 한다.

## 1. DB 마이그레이션 (additive — 무중단)

> **2026-09-22 실측: 이 절은 그대로는 실패한다.** 운영 DB 는 FastAPI lifespan(`create_all`·`ALTER TABLE … ADD COLUMN IF NOT EXISTS`)이 `0004` 객체를 먼저 만들어 두었고 스탬프만 `0003` 이었다 — `upgrade head` 가 `DuplicateColumn` 으로 죽는다. 객체 존재를 확인하고 `stamp` 로 맞춘다(`docs/ops/recurring-gotchas.md` 14번). 현재 운영은 `0005_research_jobs`(2026-09-23).

```bash
docker compose exec -w /app fastapi alembic current        # 0003 확인
docker compose exec -w /app fastapi alembic upgrade head    # → 0004  (위 경고 — 객체가 이미 있으면 stamp)
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

## 5-a. 관리 API 는 서버 내부에서 호출한다

`/api/admin` 은 게이트웨이에서 외부 차단돼 있다(`infra/conf.d/default.conf`). 2026-09-14
`library_catalog` 전멸 사고 이후 넣은 조치다 — 인증 없는 전체 삭제 엔드포인트가 인터넷에
열려 있었다. 이 런북의 `curl http://<host>/api/admin/...` 는 **밖에서는 403 이 난다.**

서버에서 컨테이너를 경유해 호출한다:

```bash
docker exec nl-lib-fastapi curl -s -X POST "localhost:8000/api/admin/ingest-jobs"   -H 'Content-Type: application/json' -d '{...}'
```

아래 §6 의 `http://<host>/api/admin/...` 도 전부 이 형태로 바꿔 읽는다.

## 5-b. 카탈로그 없는 코퍼스는 `doc_type` 을 반드시 지정한다

웹 크롤링처럼 **카탈로그 메타 적재를 거치지 않고 바로 인덱싱하는 코퍼스**는 잡 생성 시
`params.doc_type` 을 반드시 명시한다.

```json
{"doc_type": "literature", "skip_cover": true}
```

명시하지 않으면 `_ensure_book_and_doc_type`(`app/services/ingestion/stages.py:337`)이 PDF 에서
메타를 자동추출하고, 그때 LLM 이 찍은 `genre` 가 `doc_type` 을 정한다. `params.doc_type` 은
판정 우선순위 1위라 자동추출이 개입할 여지를 없앤다.

**빠뜨리면 생기는 일** — 위키문헌(`WS_*`)·공유마당(`GM_*`) 문학 41편이 `doc_type='paper'` 로
박혔다. 논문 검색을 오염시켰을 뿐 아니라, 도서 필터가 `doc_type != "paper"` 라
「무정」·「진달래꽃」·「구운몽」이 **도서 검색에서 완전히 실종됐다.** 논문 필터에는
`book_id like "KCI_FI%"` ID 폴백이 있지만 도서 필터에는 없다. 되돌리려면 Milvus 스칼라를
문서 단위로 재기록해야 한다(`scripts/recovery/rewrite_milvus_doc_type.py`).

코드 쪽 안전망(`source_format="PDF"` 의 `genre` 를 학술 유형 근거로 쓰지 않음)이 최악은
막지만, 그 경우 문서는 `book` 으로 떨어진다 — `literature` 나 `paper` 가 맞는 코퍼스라면
여기서 명시하는 것 외에 방법이 없다.

한 코퍼스 = 한 `doc_type` 이므로 잡 단위 지정으로 충분하다. 매니페스트 스키마에는
`doc_type` 필드가 없고, 넣을 필요도 없다.

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

## 8. 적재를 잠시 멈춰야 할 때 — 과도기 구성의 운영 딥리서치 · 적재 워커 재생성 전

세 경우에 쓴다.

- **과도기 구성에서 운영 딥리서치를 돌릴 때 — 시연·리허설, 시연 후보 미리 돌리기, 기본 파라미터 실측, 워밍업 전부.** 전용 워커로 넘기기 전(`RESEARCH_QUEUE` 기본값 `q_llm`)에는 딥리서치 계획·실행이 적재의 요약·마무리와 같은 `q_llm` FIFO 에서, GPU·모델 캐시가 없는 `celery-llm`(슬롯 4개)으로 돈다. 문제는 대기만이 아니다.
  - **적재 데이터가 손상될 수 있다.** 실행 잡 하나가 슬롯 하나를 최대 25분(`JOB_DEADLINE`) 쥔다. 여럿이 겹쳐 슬롯이 모자라면, 요약·마무리를 기다리는 적재 아이템이 단계 타임아웃(요약 1200초·마무리 900초)을 넘긴다 — 타임아웃은 `updated_at` 부터 재고, 큐에서 기다리는 동안에는 갱신되지 않는다. 그러면 디스패처가 stale 복구로 새 체인을 띄우고 큐에 남은 옛 메시지도 그대로 돌아 함정 16번의 중복 체인이 된다 — **논문은 PDF 본문 청크가 초록 청크로 덮일 수 있다.**
  - 그래서 **적재 잡이 `running` 인 동안에는 운영 딥리서치를 돌리지 않는다. 먼저 pause 하고 in-flight(`dispatched`·`running`)가 0 이 된 것을 본 뒤 돌린다**(아래 절차). pause 만 하고 in-flight 가 남은 채 돌리면 안 된다 — `paused` 동안은 stale 판정이 멈출 뿐이고, `resume` 뒤 첫 디스패처 틱이 슬롯을 기다리다 타임아웃을 넘긴 아이템을 그때 복구한다.
  - API 는 이 구성에서 실행을 한 번에 한 잡으로 묶는다 — 실행 중·대기 중(`approved`·`queued`·`running`) 잡이 있으면 approve·retry 가 429 다(`api/research.py` `_to_run_queue`, round04a 머지 전 리뷰 반영분부터 — 그 전 코드가 도는 운영에는 상한이 없다). 몰아서 승인하는 사고를 막는 안전장치이지, 적재 중 실행을 허락한다는 뜻이 아니다. 429 가 풀리지 않으면 막고 있는 잡을 찾아 취소한다 — 회수기는 `running` 만 45분 뒤에 거두고, 브로커 메시지를 잃은 `approved`·`queued` 잡은 건드리지 않는다.

    ```bash
    docker exec nl-lib-postgres psql -U <user> -d <db> -c \
      "SELECT id, status, started_at FROM research_jobs WHERE status IN ('approved','queued','running')"
    docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/research/<research_job_id>/cancel
    ```
  - 적재가 돌면 계획(0.6초)도 요약 수십 건 뒤에 서서 화면이 `created` 로 멈춘다. spec 추정으로 `kci-full-236k` 는 11월 초에 끝나고 대회는 10월 초라, 인덱싱이 끝나길 기다리면 시연은 이 구성으로 치른다.
- **적재 워커를 재생성하는 배포 전**(스택 업데이트, `nl-lib-celery-llm` 컨테이너 Recreate 등). 도는 적재 태스크를 끊으면 stale 복구와 브로커 재전달이 둘 다 일어나 끝난 아이템의 단계가 다시 돈다(`recurring-gotchas.md` 16번). **in-flight 가 0 일 때 재생성하면 끊기는 태스크가 없다.** 전용 워커 전환(완료노트 §5 2단계)을 시연 전에 하려면 이 절차 안에서 한다.

**pause 는 적재된 데이터도, 진행 중인 아이템도 버리지 않는다.** `pause` 는 잡 상태만 `paused` 로 바꾼다. 디스패처는 `running` 잡에만 새 아이템을 넣으므로 신규 디스패치가 멈추고, 이미 디스패치된 체인은 끝까지 돈다 — 그래서 pause 직후에도 요약·마무리가 한동안 `q_llm` 으로 들어온다. `paused` 동안은 stale 복구도 돌지 않고, `resume` 하면 멈춘 자리부터 이어간다. 다만 `resume` 뒤 첫 틱에서 stale 판정을 다시 하므로, 딥리서치·재생성은 **in-flight 0 을 본 뒤에** 한다 — 비운 채로 멈춰 두면 resume 때 복구될 아이템이 없다.

```bash
# 서버에서 컨테이너 경유로 호출한다(§5-a — /api/admin 은 외부 차단)
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs      # status=running 인 잡을 전부 멈춘다
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/<job_id>/pause

# 비우기 — 잡마다 status_counts 의 dispatched·running 이 0 이 될 때까지 기다린다
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/<job_id>
docker exec nl-lib-redis redis-cli LLEN q_llm      # 0 이면 q_llm 에 남은 적재 메시지가 없다
```

- **비우는 데 걸리는 시간.** 잡당 in-flight 는 `INGEST_HIGH_WATER`(기본 32)건이고, 잡 처리율(69~143건/h) 기준이면 15~30분 안팎이다. 시연 1시간 전에 pause 한다. 단계 타임아웃(요약·임베딩 1200초)의 두 배를 넘겨도 줄지 않으면 재생성하기 전에 워커 로그부터 본다.
- **멈춘 동안 — 배포.** 이 상태에서 스택 업데이트나 컨테이너 Recreate 를 한다. 적재 워커가 재생성돼도 끊기는 태스크가 없다.
- **멈춘 동안 — 시연·리허설·미리 돌리기.** in-flight 0 을 확인한 뒤에만 딥리서치를 승인한다. 워커를 띄우거나 재생성했으면 **워밍업 잡을 한 번** 돌린다. 탐색은 BGE-M3·리랭커를 워커 프로세스 안에서 처음 쓸 때 올리고, `celery-llm` 은 모델 캐시 마운트가 없어 recreate 뒤 첫 탐색이 모델을 새로 받는다(함정 17번). 축소 파라미터로 잡을 만들어 승인하고 `completed` 까지 본다. 워커 로그의 `리랭커 로드 완료 (cuda|cpu, …)` 로 장치도 확인한다.

  ```bash
  docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/research -H 'Content-Type: application/json' \
    -d '{"question":"공공도서관 서비스 품질 평가 연구","params":{"max_subquestions":1,"max_recheck":0,"per_subq_top_k":4}}'
  docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/research/<research_job_id>/approve
  ```

  과도기 구성의 한계: `celery-llm` 은 prefork 자식 4개가 모델을 따로 올리므로 워밍업 1회가 모든 자식을 데우지 않는다. 시연에서 첫 잡의 지연을 없애려면 전용 워커(`--concurrency=1`)로 먼저 넘긴다.
- **끝나면 바로 resume.**

  ```bash
  docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/<job_id>/resume
  ```

## 롤백

- 코드: 이전 이미지 태그로 `docker compose up -d`
- DB: `alembic downgrade 0003_widen_varchar_fields` (doc_type/extra/잡 테이블 제거 — additive라 안전)
- Milvus: 인덱스 파라미터 env를 되돌리고 재생성하면 IVF_FLAT로 복귀
