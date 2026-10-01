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
docker compose up -d celery-control celery-cpu celery-llm celery-embed celery-beat
docker compose ps      # 워커(제어·추출·요약·임베딩) + beat 가 Up 인지 확인 — 제어 큐(q_control)는 celery-control 만 받는다
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

## 9. round07 배포 — 적재 파이프라인 보강 (2026-10)

round07(spec `docs/superpowers/specs/2026-10-01-round07-ingest-pipeline-fix-design.md`)은 앱 이미지와 compose 를 함께 바꾼다. `x-common-env` 에 새 설정 11개를 선언하고 추출 stale 판정 기본값을 14400 → 3600초로 줄이며, 제어 큐 `q_control` 은 새 워커 `celery-control`(동시 1, GPU 없음)이 받고 `celery-cpu` 는 `q_cpu` 만 받는다. `x-common-env` 를 물고 있는 앱 서비스가 전부 재생성되므로 적재를 비운 뒤 한 번에 한다(§8, 함정 16번). 아래 명령은 서버의 같은 셸에서 이어 쓴다 — `JOB` 은 본 잡 `kci-full-236k` 이고 `CANARY` 는 9-6 에서 정한다. 셸을 새로 열었으면 `JOB=1ca22f59-1e50-4dd1-81f5-2d3c79126825` 와 `CANARY=$(cat /data/nl-lib/data/round07/canary_job_id.txt)` 를 다시 넣는다.

**배포 규칙**

- **이미지와 compose 를 스택 업데이트 한 번으로 같이 낸다.** compose 만(추출 stale 판정 3600초) 먼저 내지 않는다 — 3600초는 추출 stale 판정이자 추출 단계 문서 락(`BookLock`)의 TTL 이고, 추출이 그 안에 끝난다는 보장(추출 데드라인 2700초)과 넘겼을 때 옛 체인을 멈추는 실행 토큰은 새 코드에만 있다. 새 이미지만 내고 compose 를 그대로 두지도 않는다 — `celery-control` 이 없고, 새 설정을 스택 env 로 바꿀 수 없다(선언이 없다).
- **적재 워커가 모두 새 이미지인 것을 본 뒤 카나리를 시작한다(9-3).** 새 디스패처는 단계 메시지에 인자 둘(`item_id`, `run_token`)을 싣는다 — 옛 코드 워커가 받으면 `TypeError` 로 실패한다. `celery-llm` 과 `celery-embed` 는 특히 함께 새 코드여야 한다 — 요약 단계가 옛 보강 아티팩트를 지우고 이번 실행의 것을 만들면 embed 가 그것을 읽는 짝이라, 한쪽만 옛 코드면 옛 요약은 아티팩트를 지우지 않고 새 embed 는 이전 실행의 보강을 색인할 수 있다.
- **카나리 잡과 본 잡을 동시에 `running` 으로 두지 않는다.** 카나리 문서는 본 잡에도 같은 `book_id` 로 있다. 두 잡이 같은 문서를 함께 돌리면 한쪽이 문서 락 경합으로 체인을 멈추는데, round07 은 그 아이템을 `pending` 으로 되돌리지 않는다 — 잡의 진행 상한 한 칸을 쥔 채 stale 복구(`DISPATCH_STALE_SECONDS`, 4시간)까지 멈춰 있다(함정 16번 근본 수정).
- **되돌리기도 in-flight 0 에서만 한다.** 9-1 처럼 비운 뒤, 9-2 에서 남긴 이미지를 `:latest` 로 다시 붙이고(`docker tag landsoftdocker/nl-lib-fastapi:pre-round07 landsoftdocker/nl-lib-fastapi:latest`) 9-3 에서 받아 둔 옛 스택 정의(`celery-cpu` 가 `-Q q_cpu,q_control`, `celery-control` 없음, 추출 stale 14400)로 9-3 처럼 업데이트한다. 큐에 새 형식 메시지가 남은 채 되돌리면 옛 워커가 `TypeError` 로 실패한다.

> **FLUX 를 켜지 않는다.** 저장소 compose 에는 `flux` 서비스가 살아 있지만 운영 스택은 주석 처리해 두었다(스택 정의와 저장소 compose 가 다르다 — `round04a-완료노트.md` §8). 스택 편집기에 저장소 compose 를 통째로 붙이면 FLUX.1-dev 가 GPU 0 에 올라와 VLM·gemma·임베딩과 GPU 를 나눠 쓴다. round07 전 코드는 논문마다 마무리 단계에서 표지를 만들려 한다(FLUX 가 꺼져 있어 지금은 즉시 실패한다). round07 은 논문 표지를 건너뛰지만, 적재가 도는 동안 FLUX 를 켤 이유는 없다. 그래서 9-3 은 바뀐 곳만 옮긴다.

### 9-1. 비었는지 확인

본 잡은 2026-10-01 에 pause 했다(§8). 하나라도 기대와 다르면 배포하지 않는다.

```bash
JOB=1ca22f59-1e50-4dd1-81f5-2d3c79126825
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs          # status 가 running 인 잡이 없어야 한다 — 있으면 §8 대로 pause
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$JOB     # "status":"paused", status_counts 에 dispatched·running 이 없다
for q in q_cpu q_llm q_embed; do docker exec nl-lib-redis redis-cli LLEN $q; done   # 셋 다 0
docker exec nl-lib-redis redis-cli HLEN unacked                                    # 0 — 아래 첫째 줄
docker exec nl-lib-redis redis-cli --scan --pattern 'book_lock:*' | wc -l         # 0 — 남은 문서 락이 없다
docker exec nl-lib-postgres psql -U <user> -d <db> -c \
  "SELECT id, status FROM research_jobs WHERE status IN ('approved','queued','planning','running')"   # 0행 — celery-research 도 재생성된다
docker exec nl-lib-postgres psql -U <user> -d <db> -c \
  "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'ingest_job_items' AND column_name IN ('meta', 'stage_timings')"   # 둘 다 jsonb
```

- `unacked` 는 워커가 받고 아직 ack 하지 않은 메시지다(`task_acks_late`). 남은 채 배포하면 `visibility_timeout`(7200초) 뒤 새 워커로 재전달된다. 디스패처 틱(30초마다 잠깐 돈다)이면 1 이 보일 수 있다 — `docker exec nl-lib-redis redis-cli HVALS unacked | grep -o 'tasks\.[a-z_]*' | sort | uniq -c` 로 보고 `tasks.dispatch_job_items` 뿐이면 몇 초 뒤 다시 센다. `tasks.stage_*` 가 있으면 배포를 멈추고 원인부터 본다(함정 16번 ② 브로커 재전달).
- 문서 락(`book_lock:<book_id>`)이 남아 있으면 그 문서의 카나리 단계가 락 경합으로 멈춘다(위 배포 규칙). 남은 키는 TTL(옛 코드는 그 단계 타임아웃 — 추출 14400초)이 지나면 스스로 사라진다 — 사라진 뒤 배포한다.
- `meta` 가 jsonb 여야 한다 — round07 의 수동 retry 가 jsonb 연산(`||`)으로 `meta.run_token` 을 덮고, 재처리·카나리 스크립트가 `jsonb_typeof` 를 쓴다. 모델과 마이그레이션 0004 는 jsonb 로 만든다. 읽기만 하는 확인이다.

### 9-2. 이미지 빌드·받기

운영 스택은 `:latest` 를 쓴다(함정 3번). Portainer 에 pull 을 맡기지 않는다(함정 12번) — pull 만으로는 아무것도 재시작되지 않는다. round07 은 화면을 고치지 않으므로 nuxt 이미지는 그대로다.

```bash
# 개발 PC — 리뷰를 마친 round07 커밋에서(.worktrees/round07). 빌드한 커밋을 적어 둔다
git rev-parse --short HEAD
NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi
```

```bash
# 서버 — 지금 nl-lib-fastapi 가 쓰는 이미지를 되돌리기용 태그로 남기고 새 이미지를 받는다
docker tag "$(docker inspect --format '{{.Image}}' nl-lib-fastapi)" landsoftdocker/nl-lib-fastapi:pre-round07
docker pull landsoftdocker/nl-lib-fastapi:latest
docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:latest   # 9-3 에서 컨테이너 이미지와 견준다
mkdir -p /data/nl-lib/data/round07                                             # 9-3·9-6~9-10 의 파일 자리(fastapi 안에서는 /app/data/round07)
```

### 9-3. Portainer 스택 업데이트

- 고치기 전에 지금 스택 정의를 파일로 받아 둔다(되돌리기용 — 위 배포 규칙).
- 스택 편집기에서 저장소 `docker-compose.yml` 과 견주어 **바뀐 곳만** 옮긴다. 바뀐 곳은 round07 분기점과의 차이다(`git diff 9798f46 -- docker-compose.yml`).
  - `x-common-env` 에 새 키 11개. 모두 `${이름:-기본값}` 으로 선언한다 — 선언이 없으면 Portainer 가 그 이름의 스택 env 를 무시해 9-7 에서 값을 바꿀 수 없다.
    - LLM 묶음(`LLM_SECTION_CONCURRENCY` 아래): `LLM_RETRY_ATTEMPTS`·`LLM_RETRY_BACKOFF_SECONDS`.
    - 텍스트 추출 묶음(`VLM_TIMEOUT` 아래): `VLM_PAGE_CONCURRENCY`·`SCAN_REPEAT_LINE_RATIO`·`SCAN_SHORT_PAGE_RATIO`·`SCAN_MIN_PAGES`·`ODL_TIMEOUT_BASE_SECONDS`(기본 `10.0`)·`ODL_TIMEOUT_PER_PAGE_SECONDS`(기본 `1.5`)·`ODL_IMAGE_OUTPUT`.
    - 대량 인덱싱 잡 묶음(`INGEST_MAX_ATTEMPTS` 아래): `INGEST_RETRY_BACKOFF_SECONDS`·`INGEST_EXTRACT_DEADLINE`.
  - 같은 묶음의 `INGEST_STAGE_TIMEOUT_EXTRACT` 기본값 `14400` → `3600`(바로 위 주석도 바뀌었다).
  - ODL 을 돌리는 `fastapi`(바로 위 주석 포함)·`celery-worker`·`celery-cpu` 에 `init: true` — ODL 이 시간을 넘겨 자식 프로세스를 끄면 고아가 된 java 를 PID 1(tini)이 거둔다(없으면 시간 초과마다 좀비가 남는다). SIGTERM 은 그대로 넘겨 celery warm shutdown 은 같다.
  - `celery-cpu` 의 `command`: `-Q q_cpu,q_control` → `-Q q_cpu`.
  - 새 서비스 `celery-control` 블록 전체(바로 위 주석 포함, `celery-cpu` 와 `celery-llm` 사이).
  - 주석만 바뀐 곳(안 옮겨도 동작은 같다): `gemma` 의 `--max-num-seqs` 위, `celery-llm` 머리.
- 스택 env(Environment variables)를 본다. `INGEST_STAGE_TIMEOUT_EXTRACT` 가 있으면 지운다 — 있으면 새 기본값 대신 그 값이 들어간다. `MILVUS_RECREATE_ON_MISMATCH` 는 없거나 `false` 여야 한다 — 재생성되는 fastapi 가 기동하며 바로 `ensure_collection()` 을 부른다(9-5).
- **"Re-pull image" 토글을 끄고** Update the stack 을 누른다(함정 12번). 500 이 나면 다시 누르기 전에 `docker ps -a --format '{{.Names}}\t{{.CreatedAt}}'` 로 무엇이 바뀌었는지부터 본다.
- 업데이트 뒤 앱 컨테이너가 재시작을 되풀이하면(`docker ps` 의 `Restarting`) 먼저 `docker logs --tail 50 nl-lib-celery-cpu` 에서 설정 검증 오류를 본다. `ODL_IMAGE_OUTPUT` 은 `off`·`embedded`·`external` 만 받는다 — 오타면 앱이 뜨지 않는다(예전에는 문서가 모두 fitz 텍스트로 조용히 떨어졌다).

```bash
docker ps --format '{{.Names}}\t{{.Status}}' | grep nl-lib-celery              # nl-lib-celery-control 이 Up
docker inspect nl-lib-celery-cpu --format '{{join .Config.Cmd " "}}'         # … -Q q_cpu --max-tasks-per-child=50 (q_control 없음)
for c in nl-lib-fastapi nl-lib-celery nl-lib-celery-cpu; do echo "$c init=$(docker inspect --format '{{.HostConfig.Init}}' $c)"; done   # 셋 다 true
docker exec nl-lib-celery-cpu printenv INGEST_STAGE_TIMEOUT_EXTRACT INGEST_EXTRACT_DEADLINE VLM_PAGE_CONCURRENCY ODL_TIMEOUT_BASE_SECONDS ODL_TIMEOUT_PER_PAGE_SECONDS ODL_IMAGE_OUTPUT   # 3600 / 2700 / 2 / 10.0 / 1.5 / off
docker logs --since 2m nl-lib-celery-control 2>&1 | grep -c dispatch_job_items   # 0 이 아니다 — 30초마다 디스패치 틱을 받는다
NEW=$(docker image inspect --format '{{.Id}}' landsoftdocker/nl-lib-fastapi:latest)
for c in nl-lib-fastapi nl-lib-celery nl-lib-celery-cpu nl-lib-celery-control nl-lib-celery-llm nl-lib-celery-embed nl-lib-celery-beat nl-lib-celery-research nl-lib-celery-research-plan; do
  [ "$(docker inspect --format '{{.Image}}' $c)" = "$NEW" ] && echo "$c 새 이미지" || echo "$c 옛 이미지"
done
date -u +%Y-%m-%dT%H:%M:%S+00:00 | tee /data/nl-lib/data/round07/deployed_at.txt   # 배포 시각 — 9-10 의 --finished-before
```

- 아홉 개가 모두 `새 이미지` 여야 카나리로 간다(위 배포 규칙). `옛 이미지` 가 있으면 Portainer 에서 그 컨테이너를 Recreate 한다("Re-pull image" 끔 — 서버에 받아 둔 `:latest` 를 쓴다).

### 9-4. 게이트웨이 reload

fastapi 가 재생성됐다(함정 20번).

```bash
docker exec nl-lib-gateway nginx -s reload
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:92/health     # 200
```

### 9-5. `MILVUS_RECREATE_ON_MISMATCH` 확인

9-3 에서 스택 env 를 봤어도 컨테이너에 들어간 값을 한 번 더 본다(함정 16번). `ensure_collection()`(`app/services/ingestion/indexer.py`)은 이 값이 `true` 이고 컬렉션 스키마가 다르면 컬렉션을 지우고 새로 만든다. 이 함수를 부르는 것은 fastapi(기동·검색·관리 API)만이 아니다 — `celery-embed`·`celery-worker`(색인), `celery-research`(검색), `celery-control`(1시간마다 `cleanup_temp_files` 의 Milvus flush)도 부른다. 모두 `x-common-env` 에서 같은 값을 받으므로 컨테이너 하나를 보면 된다. round07 은 Milvus 스키마를 바꾸지 않지만, `true` 면 어느 프로세스든 스키마 차이를 보는 순간 컬렉션 전체(약 620만 청크)가 지워진다.

```bash
docker exec nl-lib-celery-control printenv MILVUS_RECREATE_ON_MISMATCH     # false
```

### 9-6. 카나리 잡

본 잡은 paused 로 둔다(위 배포 규칙). 개발 PC 의 `scripts/bulk_ingest/` 에서 `build_canary_manifest.py`·`select_near_empty_items.py` 를 서버의 `/data/nl-lib/data/round07/` 로 옮긴다(scp 등 평소 쓰는 방법 — `scripts/` 는 앱 이미지에 없다, 함정 4번).

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round07/build_canary_manifest.py \
  --job $JOB --out /app/data/round07/canary
```

- 범주별 몫·고른 수(`scan_no_sections` 20 · `many_tables` 10 · `dense_chunks` 5 · `many_sections` 5 · `normal` 10)와 다음 명령 셋(MinIO 업로드 → 잡 생성 → 시작)을 출력한다. 모자란 범주가 있으면 그대로 써도 된다. 아래는 출력되는 명령과 같고, 잡 생성 응답의 `job_id` 를 `CANARY` 로 받는 것만 더했다.
- `--out` 은 `/app/data/` 아래 절대 경로로 준다 — 업로드 명령이 컨테이너 안의 그 경로를 읽고, 호스트에서는 `/data/nl-lib/data/round07/canary/` 다(9-7 ⑥ 도 이 매니페스트를 읽는다).
- `scan_no_sections` 는 본 잡의 '섹션 없음' 실패에서 고른다 — 9-8(실패분 retry 가 `last_error` 를 지운다) 전에 만든다.

```bash
# 1) 매니페스트를 MinIO 에
docker exec -e PYTHONPATH=/app nl-lib-fastapi python -c "from core.config import get_settings; from services.ingestion.stages import minio_client; minio_client().fput_object(get_settings().MINIO_BUCKET, 'manifests/round07-canary/manifest.jsonl', '/app/data/round07/canary/manifest.jsonl'); print('uploaded')"
# 2) 시작 전 카운터를 적어 둔다 — 9-7 ④·⑤ 의 기준(선점 카운터 이름이 없으면 grep -i preempt 로 찾는다)
docker exec nl-lib-fastapi curl -s gemma:8000/metrics | grep -E '^vllm:request_success_total.*finished_reason="(stop|length)"'
docker exec nl-lib-fastapi curl -s vllm:8000/metrics | grep -E '^vllm:num_preemptions_total'
# 3) 잡 생성(dry-run 검증 → ready, MinIO originals/ 목록을 읽어 시간이 걸린다) — 응답의 job_id 를 CANARY 로
RESP=$(docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs \
  -H 'Content-Type: application/json' \
  -d '{"name":"round07-canary","manifest_key":"manifests/round07-canary/manifest.jsonl","params":{"reembed":true,"skip_cover":true}}')
echo "$RESP"                                                       # total_items 가 고른 수와 같고 validation_report 의 missing_* 가 비었다
CANARY=$(echo "$RESP" | sed -n 's/.*"job_id":"\([^"]*\)".*/\1/p')
echo "$CANARY" | tee /data/nl-lib/data/round07/canary_job_id.txt   # 비었으면 잡이 만들어지지 않았다 — 위 응답의 detail 을 본다
# 4) 시작
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$CANARY/start
```

- 시작하고 몇 분 안에 `docker logs nl-lib-celery-cpu 2>&1 | grep -E '초 / 상한|ODL 실패' | head -20` 으로 첫 문서들의 ODL 이 실제로 변환되는지 본다 — ODL 자식 프로세스가 Celery 풀 자식 안에서 도는 첫 확인이다(9-7 ⑩). 시도마다 `ODL 12.3초 / 상한 56초` 같은 줄이 남고, 실패하면 바로 뒤에 `ODL 실패(…) — fitz 재저장본으로 한 번 더` 가 붙는다. 실패가 대부분이면 카나리를 멈추고(`docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$CANARY/pause`) 괄호 안의 사유를 본다.
- `docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$CANARY` 의 `status` 가 `completed`·`completed_with_errors` 가 될 때까지 기다린다. 도는 동안 9-7 ④ 를 몇 번 본다. `status_counts` 의 `dispatched`·`running` 이 한 시간 넘게 줄지 않으면 9-7 ⑦ 의 로그부터 본다.
- 9-7 에서 멈추고 고친 뒤 다시 돌릴 때는 앞 카나리가 `completed`·`completed_with_errors` 인지 보고 이 절을 처음부터 한다. 같은 이름이면 매니페스트를 덮어쓰고 잡은 새 id 로 생긴다.

### 9-7. 카나리 지표

카나리가 끝나면 아래를 차례로 본다(④ 는 도는 동안 본다). ①~⑦ 은 spec §5 의 확인 목록이고 ⑧~⑬ 은 구현 리뷰가 더한 것이다. 9-3 에서 워커가 재생성됐고 본 잡은 paused 라 워커 로그는 배포 뒤 카나리 것뿐이다(워커를 재생성하지 않고 카나리를 다시 돌렸으면 앞 카나리 것도 섞인다 — `docker logs` 에 `--since 2h` 처럼 시간을 붙인다). **멈춤**에 하나라도 걸리면 9-8·9-9 로 가지 않는다 — 본 잡은 paused 로 두고, 고친 뒤 9-6 부터 카나리를 다시 돌린다. 설정을 바꿀 때는 스택 env 에 넣고 9-3 처럼(Re-pull 끔) 업데이트한 뒤 9-4 를 한다 — `x-common-env` 를 무는 앱 서비스가 모두 재생성되므로 카나리가 끝나 in-flight 0 일 때 한다.

① 결과·실패 그룹·추출 방법.

```bash
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$CANARY            # status_counts · extract_methods
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$CANARY/failures   # error_group 별 수 · 가장 흔한 메시지
docker exec nl-lib-postgres psql -U <user> -d <db> -c \
  "SELECT id, book_id, error_group, left(last_error, 200) AS last_error FROM ingest_job_items WHERE job_id = '$CANARY' AND status = 'failed' ORDER BY id"
```

- `extract_methods` 는 문서마다 가장 많이 쓴 쪽 방법의 분포다 — `opendataloader`(ODL 채택) · `vlm`(OCR) · `fitz`(ODL 이 두 번 다 실패해 fitz 텍스트로 대신 — ⑩).
- `no_text` 는 강제 OCR 까지 해도 글자가 없거나 강제 OCR 로 바뀔 쪽이 없는 문서다 — 결정적 실패라 자동 재시도하지 않고 목록만 남긴다(②).
- 멈춤: `no_text` 가 아닌 실패가 남았다(`vlm_error`·`extract_empty`·`llm_error`·`llm_timeout`·`artifact_missing`·`milvus_error`·`unknown` 등 — 자동 재시도를 다 쓴 것이다). `last_error` 로 원인을 안 뒤에 간다. 일시 장애로 보이면(예: 카나리 중 gemma 재기동) 카나리를 다시 돌려 사라지는지 본다.

② 스캔본이 VLM 으로 가고 섹션이 생겼는가 — 본 잡에서 '섹션 없음'으로 실패한 문서(`scan_no_sections`)만 본다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT c.status, c.error_group, c.meta->>'extract_method' AS method, count(*) AS n, count(*) FILTER (WHERE (c.meta->>'sections')::int > 0) AS with_sections, count(*) FILTER (WHERE (c.meta->>'forced_ocr')::boolean) AS forced_ocr, sum((c.meta->>'vlm_truncated')::int) AS vlm_truncated, sum((c.meta->>'ocr_errors')::int) AS ocr_errors, sum((c.meta->>'render_errors')::int) AS render_errors, count(*) FILTER (WHERE (c.meta->>'extract_deadline_hit')::boolean) AS deadline_hit FROM ingest_job_items c JOIN ingest_job_items m ON m.book_id = c.book_id AND m.job_id = '$JOB' WHERE c.job_id = '$CANARY' AND m.status = 'failed' AND m.last_error LIKE '섹션 없음%' GROUP BY 1, 2, 3 ORDER BY 4 DESC"
```

- 이 묶음의 9할 이상이 `done`·`vlm`·`with_sections` 여야 한다 — 회귀 하네스에서 같은 블록 318건이 모두 스캔본으로 잡혔다(`research/round07-ingest-regression/README.md`).
- 칸: `forced_ocr` = 섹션 0개라 짧은 쪽을 모두 OCR 로 보내 다시 추출했다 — 스캔본으로 잡힌 문서는 짧은 쪽을 처음부터 OCR 하므로 0 이어야 하고, 0 이 아니면 스캔본 판정이 놓친 문서다. `vlm_truncated` = max_tokens 에서 끝난 OCR 쪽(되풀이 꼬리를 걷어 냈거나 퇴화 출력이라 버렸다). `ocr_errors` = VLM 요청 실패(연결·타임아웃·HTTP 오류)만. `render_errors` = 쪽 이미지 렌더링 실패. `deadline_hit` = 추출 데드라인(2,700초)에 걸렸다. 추출이 실패한 아이템은 이 칸들이 비어 있다(추출이 성공했을 때만 meta 에 남는다).
- 멈춤: `done`·`vlm` 이 9할 미만이거나 `forced_ocr` 이 0 이 아니다. `vlm_error` 가 있으면 ④ 로 VLM 부터 본다.

③ embed 단계가 GPU 일만 남아 줄었는가 — 같은 문서의 본 잡(옛 코드) 시간과 견준다. 표 5개 이상 문서의 `embed_after` 가 크게 줄고(진단 때 표 9개 이상 문서의 embed 중앙 24.6초) 그만큼 `summarize_after` 가 는다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT coalesce((m.meta->>'n_tables')::int, 0) >= 5 AS tables_5plus, count(*) AS n, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (m.stage_timings->>'embed_index_s')::float)::numeric, 1) AS embed_before, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (c.stage_timings->>'embed_index_s')::float)::numeric, 1) AS embed_after, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (m.stage_timings->>'summarize_s')::float)::numeric, 1) AS summarize_before, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (c.stage_timings->>'summarize_s')::float)::numeric, 1) AS summarize_after FROM ingest_job_items c JOIN ingest_job_items m ON m.book_id = c.book_id AND m.job_id = '$JOB' WHERE c.job_id = '$CANARY' AND c.status = 'done' AND m.status = 'done' GROUP BY 1 ORDER BY 1"
```

- 줄지 않으면 ⑪ 의 `enrich_source` 를 본다 — `inline` 이면 embed 가 보강 LLM 을 다시 기다린 것이다. 처리량 문제라 이것만으로 멈추지는 않는다.

④ 문서 안 VLM 병렬과 VLM 부하 — 스캔본을 추출하는 동안 여러 번 본다.

```bash
docker exec nl-lib-fastapi curl -s vllm:8000/metrics | grep -E '^vllm:(num_requests_(running|waiting)|num_preemptions_total)'
```

- `num_requests_running` 이 2 이상으로 오른다. 4 를 넘으면 문서 안 병렬이 도는 것이다(옛 코드는 추출 4칸이 한 쪽씩이라 4 가 최대였다. 지금은 4 × `VLM_PAGE_CONCURRENCY` 2 = 8 까지).
- 8건이 한꺼번에 들어가도 VLM 의 KV 캐시는 약 6건 몫이다(Task 4 리뷰 추정 — `--gpu-memory-utilization 0.2`·`--max-model-len 16384`). 넘는 요청은 vLLM 안에서 기다리거나(`num_requests_waiting`) 선점되고(`num_preemptions_total` 이 9-6 에서 적은 값보다 는다), 그 시간도 쪽 요청 하나의 `VLM_TIMEOUT`(120초) 안에 센다. 카나리가 끝나면 실패를 센다.

```bash
docker logs nl-lib-celery-cpu 2>&1 | grep -c 'OCR 보완 ('                   # OCR 로 보낸 쪽
docker logs nl-lib-celery-cpu 2>&1 | grep -c 'OCR(vlm) 실패'                # 그중 VLM 요청 실패(줄에 예외 이름이 붙는다)
docker logs nl-lib-celery-cpu 2>&1 | grep -c 'OCR(vlm) 실패: ReadTimeout'   # 그중 읽기 타임아웃
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT count(*) AS done, count(*) FILTER (WHERE (meta->>'ocr_errors')::int > 0) AS docs_ocr_errors, coalesce(sum((meta->>'ocr_errors')::int), 0) AS ocr_errors, count(*) FILTER (WHERE (meta->>'render_errors')::int > 0) AS docs_render_errors, count(*) FILTER (WHERE (meta->>'extract_deadline_hit')::boolean) AS docs_deadline_hit FROM ingest_job_items WHERE job_id = '$CANARY' AND status = 'done'"
```

- `ocr_errors > 0` 인 완료 문서는 OCR 하지 못한 쪽을 ODL 결과(대개 빈 쪽)로 채웠다 — ⑬ 의 다시 돌릴 목록에 오른다. `render_errors`·`deadline_hit` 은 다시 해도 대개 같다.
- 멈춤: VLM 요청 실패가 OCR 로 보낸 쪽의 1% 를 넘는다(대개 `ReadTimeout` — `num_requests_waiting` 이 오래 0 보다 크고 선점이 늘었으면 대기열 때문이다). 스택 env 에 `VLM_PAGE_CONCURRENCY=1`(문서 안 병렬을 끈다 — 옛 코드처럼 동시 4건) 또는 `VLM_TIMEOUT=180`~`240` 을 넣는다. 둘 다 compose 에 선언돼 있다.

⑤ gemma 잘림 비율 — 9-6 에서 적은 값과의 차이로 (length 증가분) ÷ (stop 증가분 + length 증가분) 을 구한다. 진단 때 5.3%(대부분 표 해석)보다 낮아야 한다.

```bash
docker exec nl-lib-fastapi curl -s gemma:8000/metrics | grep -E '^vllm:request_success_total.*finished_reason="(stop|length)"'
```

- 낮지 않으면 표 해석 프롬프트(`paper_table_interp.yaml`)가 듣지 않는 것이다. 저장 텍스트·생성 시간의 문제라 이것만으로 멈추지는 않는다 — ⑥ 과 함께 본다.

⑥ 표 설명이 문장으로 끝나는가 — 카나리 문서의 보강 아티팩트(`artifacts/{book_id}/enrichment.json.gz`, 마무리 단계는 지우지 않는다)를 본다. 잘린 해석은 마지막으로 끝난 문장까지만 남기므로 `그 밖` 이 0 에 가까워야 한다. `python -`(stdin)은 `/app` 에서 돌아 앱 모듈이 보인다(함정 4번).

```bash
docker exec -i nl-lib-fastapi python - <<'PY'
import gzip, json
from core.config import get_settings
from services.ingestion.stages import minio_client
cfg, client = get_settings(), minio_client()
ends = {"문장": 0, "그 밖": 0}
for line in open("/app/data/round07/canary/manifest.jsonl", encoding="utf-8"):
    book_id = json.loads(line)["book_id"]
    try:
        resp = client.get_object(cfg.MINIO_BUCKET, f"artifacts/{book_id}/enrichment.json.gz")
        data = json.loads(gzip.decompress(resp.read()))
        resp.close()
        resp.release_conn()
    except Exception:
        continue
    for table in data["table_chunks"]:
        desc = (table["description"] or "").rstrip().rstrip("\"'”’)）]」』》〉】")
        if desc:
            ends["문장" if desc.endswith((".", "!", "?", "。", "다")) else "그 밖"] += 1
print(ends)
PY
```

- 멈춤: `그 밖` 이 표 설명의 1할을 넘는다 — 몇 개를 열어 끝이 잘렸는지 본다(잘린 해석 다듬기 `trim_to_last_sentence` 가 듣지 않는 것이다).

⑦ 중복 체인·stale 복구·락 경합·늦은 기록이 없는가 — 모두 0 이어야 한다.

```bash
for c in nl-lib-celery-cpu nl-lib-celery-llm nl-lib-celery-embed; do
  echo "$c 실행안함=$(docker logs $c 2>&1 | grep -c '실행 안 함 — ') 락경합=$(docker logs $c 2>&1 | grep -c '실행 안 함 — 락 경합') 늦은성공=$(docker logs $c 2>&1 | grep -c '늦은 성공 기록 버림') 늦은실패=$(docker logs $c 2>&1 | grep -c '늦은 실패 기록 버림')"
done
docker logs nl-lib-celery-control 2>&1 | grep -c 'stale 복구 (stage='           # 디스패처(제어 워커)가 남긴 stale 복구 줄
docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT count(*) FROM ingest_job_items WHERE job_id = '$CANARY' AND last_error LIKE '%stale 복구%'"
```

- `실행 안 함 — ` 은 단계 래퍼가 체인을 멈춘 줄 전부다. 이유가 `실행 토큰 불일치(…)`·`토큰 없는 옛 메시지…` 면 옛 체인, `이미 완료(done)`·`이미 지난 단계(…)` 면 재전달된 메시지, `락 경합` 이면 같은 문서를 다른 체인이 돌리고 있었다.
- stale 복구는 `last_error` 에 `3600s 무응답 — 워커 중단 추정 (stale 복구, extract 실행 중)` 같은 문구(괄호 안은 `<단계> 실행 중`·`다음 단계 대기`·`디스패치 대기`)를 남기고, 그 아이템이 나중에 `done` 이 돼도 지워지지 않는다.
- 늦은 성공·실패는 stale 복구가 토큰을 바꾼 뒤 옛 시도가 끝난 것이다 — 기록은 버렸지만 그 시도가 이미 쓴 결과는 남는다(⑨).
- 멈춤: 하나라도 0 이 아니다. `락 경합` 이면 본 잡이 `running` 이었는지 보고(위 배포 규칙), stale 복구·늦은 기록이면 ⑧ 로 그 단계가 타임아웃에 닿았는지 본 뒤 ⑨ 로 중복 저장을 확인한다.

⑧ 단계 꼬리 — 단계 타임아웃은 이제 시도별 하드 마감이다. 넘기면 stale 복구가 토큰을 바꿔 그 시도의 결과를 버리고(⑦ 의 늦은 성공), 문서 락 TTL 도 같은 값이라 다시 나간 체인이 옛 시도와 같은 문서를 함께 돌 수 있다(⑨).

```bash
docker exec nl-lib-celery-control printenv INGEST_STAGE_TIMEOUT_EXTRACT INGEST_STAGE_TIMEOUT_SUMMARIZE INGEST_STAGE_TIMEOUT_EMBED INGEST_STAGE_TIMEOUT_FINALIZE   # 3600 / 1200 / 1200 / 900
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT max((stage_timings->>'extract_s')::float) AS extract_max, max((stage_timings->>'summarize_s')::float) AS summarize_max, max((stage_timings->>'embed_index_s')::float) AS embed_max, max((stage_timings->>'finalize_s')::float) AS finalize_max FROM ingest_job_items WHERE job_id = '$CANARY'"
```

- round07 전 측정(본 잡 14,579건): 추출 최대 2,036초(spec 16 의 표본 27,000건에서는 2,785초), 요약 438초, embed 90초, 마무리 35초. round07 은 요약 단계가 논문 보강을 맡아 요약이 길어지고 embed 는 짧아지며, 마무리는 섹션이 많은 문서에서 계층 요약만큼 길어진다(논문의 계층 요약 시간 예산은 900 − 최종 호출 120 − 여유 60 = 720초, ⑫).
- 멈춤: 추출 최대가 3,000초(데드라인 2,700초 + ODL·섹션 분할 몫)를 넘는다 · 요약·embed 최대가 900초(타임아웃 1,200초의 3/4)를 넘는다 · 마무리 최대가 840초(마감 900초에서 여유 60초 안쪽 — 계층 요약이 예산을 다 쓴 문서다)를 넘는다. 추출이면 `INGEST_EXTRACT_DEADLINE` 을 낮추고, 요약·embed·마무리면 그 단계 타임아웃(`INGEST_STAGE_TIMEOUT_SUMMARIZE`·`_EMBED`·`_FINALIZE` — 마무리는 계층 요약 예산도 같이 는다)을 올린다. 모두 compose 에 선언돼 있고, 올릴 때는 Celery `visibility_timeout`(7,200초) 아래로 둔다 — 넘으면 도는 메시지가 재전달된다.

⑨ 늦은 기록이 남긴 중복 — ⑦ 에서 stale 복구나 늦은 기록이 0 이 아닐 때만 본다. 늦은 기록은 stale 복구가 토큰을 바꾼 뒤에만 나므로(카나리에서는 수동 retry 를 하지 않는다) stale 복구를 거친 아이템을 본다. 같은 `(book_id, section_idx)` 가 `book_sections` 에 두 줄 이상이거나, Milvus 의 그 문서 청크 수(`count(*)`)가 서로 다른 `chunk_id` 수나 기록된 `indexed` 와 다르면 두 시도가 겹쳐 썼다.

```bash
docker exec -i -e CANARY=$CANARY nl-lib-fastapi python - <<'PY'
import os
from pymilvus import Collection, connections
from sqlalchemy import text
from core.config import get_settings
from db.postgres import SyncSessionLocal
cfg = get_settings()
db = SyncSessionLocal()
try:
    items = db.execute(text(
        "SELECT book_id, meta->>'indexed' FROM ingest_job_items WHERE job_id = :job AND last_error LIKE :pat"
    ), {"job": os.environ["CANARY"], "pat": "%stale 복구%"}).all()
    dup = dict(db.execute(text(
        "SELECT book_id, count(*) FROM (SELECT book_id, section_idx FROM book_sections"
        " WHERE book_id = ANY(:ids) GROUP BY 1, 2 HAVING count(*) > 1) d GROUP BY 1"
    ), {"ids": [b for b, _ in items] or [""]}).all())
finally:
    db.rollback()
    db.close()
connections.connect(host=cfg.MILVUS_HOST, port=cfg.MILVUS_PORT)
col = Collection(cfg.MILVUS_COLLECTION)
for book_id, indexed in items:
    expr = f'book_id == "{book_id}"'
    total = col.query(expr=expr, output_fields=["count(*)"])[0]["count(*)"]
    ids = {r["chunk_id"] for r in col.query(expr=expr, output_fields=["chunk_id"], limit=16384)}
    print(f"{book_id} 섹션 중복 {dup.get(book_id, 0)} · Milvus {total}개 / chunk_id {len(ids)}개 · 기록 indexed {indexed}")
print(f"stale 복구를 거친 아이템 {len(items)}건")
PY
```

- 어긋난 아이템은 추출부터 다시 돌리면 고쳐진다 — 추출이 그 문서의 `book_sections` 를, embed 가 Milvus 청크를 `book_id` 로 모두 지우고 다시 쓴다. ⑧ 의 원인을 고친 뒤, 본 잡은 paused 인 채로 카나리 잡에서 다시 돌리고(retry 는 끝난 카나리 잡을 `running` 으로 되돌린다) 끝나면 ① 부터 다시 본다.

```bash
IDS=$(docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT coalesce(json_agg(id ORDER BY id), '[]') FROM ingest_job_items WHERE job_id = '$CANARY' AND last_error LIKE '%stale 복구%'")
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$CANARY/retry \
  -H 'Content-Type: application/json' -d "{\"item_ids\": $IDS, \"reset_stage\": \"pending\"}"
```

⑩ ODL 타임아웃·fitz 폴백. ODL 변환 상한은 max(`ODL_TIMEOUT_BASE_SECONDS` 10초, 쪽수 × `ODL_TIMEOUT_PER_PAGE_SECONDS` 1.5초)다. 넘거나 실패하면 fitz 로 다시 저장한 PDF 로 한 번 더(`meta.odl_fallback` = `resaved`), 그래도 안 되면 fitz 텍스트로 대신한다(`fitz` — json 이 없어 머리말·꼬리말 제거와 표 구조를 잃는다, 쪽 방법도 `fitz`). 정상이면 `odl_fallback` 은 null 이다. `meta.odl_seconds` 는 그 문서의 ODL 시도를 모두 더한 시간(0.1초 단위)이다. 카나리의 첫 문서들이 ODL 자식 프로세스가 Celery 풀 자식 안에서 실제로 도는지 보는 첫 확인이다 — 개발 PC 의 확인은 풀 밖에서 했다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT meta->>'odl_fallback' AS odl_fallback, count(*) AS n FROM ingest_job_items WHERE job_id = '$CANARY' AND status = 'done' GROUP BY 1 ORDER BY 2 DESC"
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT coalesce((meta->>'n_tables')::int, 0) >= 5 AS tables_5plus, count(*) AS n, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY (meta->>'odl_seconds')::float / greatest(10, (meta->>'pages')::float * 1.5))::numeric, 2) AS ratio_median, round(max((meta->>'odl_seconds')::float / greatest(10, (meta->>'pages')::float * 1.5))::numeric, 2) AS ratio_max FROM ingest_job_items WHERE job_id = '$CANARY' AND status = 'done' AND meta->>'odl_fallback' IS NULL GROUP BY 1 ORDER BY 1"
docker logs nl-lib-celery-cpu 2>&1 | grep -c '초 / 상한'                       # ODL 변환 시도 수(실패한 시도 포함)
docker logs nl-lib-celery-cpu 2>&1 | grep -c 'fitz 재저장본으로 한 번 더'      # 원본 ODL 이 실패한 문서(타임아웃 포함)
docker logs nl-lib-celery-cpu 2>&1 | grep -cE 'ODL 실패\([0-9]+초 초과\)'      # 그중 타임아웃
docker logs nl-lib-celery-cpu 2>&1 | grep -c 'ODL 실패 — fitz 텍스트'          # 재저장본도 실패해 fitz 텍스트로 대신한 문서
docker logs nl-lib-celery-cpu 2>&1 | grep 'fitz 재저장본으로 한 번 더' | head  # 사유 — 'ODL 실패(…)' 괄호 안
docker exec nl-lib-celery-cpu printenv ODL_IMAGE_OUTPUT ODL_TIMEOUT_BASE_SECONDS ODL_TIMEOUT_PER_PAGE_SECONDS   # off / 10.0 / 1.5
```

- 둘째 SQL 은 시도 한 번이 상한의 몇 배를 썼는지다(`meta.pages` 는 추출이 연 쪽수). 상한 식은 기본값(10·1.5)으로 썼다 — 스택 env 로 바꿨으면 SQL 의 두 수도 바꾼다. 재저장본까지 간 문서는 두 시도를 더한 시간이라 뺐다. 표 5개 이상(`tables_5plus`)은 카나리 실행이 센 표 수다.
- 정상이면 `odl_fallback` 이 있는 문서는 0~1% 다(검토 때 개발 PC 186건 중 1건). 개발 PC 측정에서 37쪽 표 많은 문서(KCI_FI001930485)는 혼자 12초, 4건 동시 28초, 8건 동시 47초가 걸렸다 — 옛 기본값(5초·쪽당 0.5초)의 상한 18.5초는 `celery-cpu` 4칸이 함께 변환하면 넘는다. 그래서 기본값을 10초·쪽당 1.5초로 올렸다.
- ODL 자식은 상한 + 5초에 SIGALRM 으로 java 까지 스스로 끈다 — 풀 자식이 끊겨도 ODL 이 끝없이 돌지 않고, 끈 java 는 `init: true`(tini)가 거둔다.
- 멈춤: `odl_fallback` 이 `fitz` 인 문서가 과반이다 — ODL 자식 프로세스가 깨진 것이다. 위 사유를 본다. 표 많은 문서의 `ratio_max` 가 0.8 을 넘으면 스택 env 의 `ODL_TIMEOUT_PER_PAGE_SECONDS` 를 올린다(compose 에 선언돼 있다).

⑪ 논문 보강이 요약 단계에서 됐는가.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT meta->>'enrich_source' AS source, count(*) AS n, count(*) FILTER (WHERE meta->>'enrich_error' IS NOT NULL) AS enrich_error FROM ingest_job_items WHERE job_id = '$CANARY' AND status = 'done' GROUP BY 1 ORDER BY 2 DESC"
```

- `enrich_source`: `artifact` = 요약 단계가 만든 이번 실행의 보강을 embed 가 읽었다 · `inline` = 그것이 없어 embed 가 보강 LLM 을 다시 기다렸다(옛 병목) · `none` = 논문이 아니거나 보강이 꺼져 있다. 카나리는 논문이라 거의 모두 `artifact` 여야 한다.
- `enrich_error` 는 성공하면 JSON null 이라 `->>` 가 NULL 이 된다 — `IS NOT NULL` 로 센다. jsonb `?` 는 키가 있으면 null 도 세므로 쓰지 않는다(함정 10번). 0 이 아니면 그 논문은 보강 청크 없이 색인됐다.
- 멈춤: `enrich_error` 가 있거나 `inline` 이 논문의 1할을 넘는다 — `for c in nl-lib-celery-llm nl-lib-celery-embed; do docker logs $c 2>&1 | grep -E 'paper enrichment 실패|enrichment 아티팩트 MinIO 저장 실패'; done` 로 까닭을 본다(요약 단계의 보강은 `celery-llm`, embed 단계가 보강을 다시 돌리면 `celery-embed` 에 남는다).

⑫ 마무리 계층 요약.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c "SELECT meta->>'reduce_levels' AS levels, meta->>'reduce_fallback' AS fallback, count(*) AS n, count(*) FILTER (WHERE (meta->>'sections_total')::int > 40) AS sections_over_40, sum((meta->>'reduce_groups')::int) AS groups, max((stage_timings->>'finalize_s')::float) AS finalize_max FROM ingest_job_items WHERE job_id = '$CANARY' AND status = 'done' GROUP BY 1, 2 ORDER BY 1, 2"
```

- `reduce_levels`: 0 = 섹션 요약을 이어도 상한(`SUMMARIZER_MAX_INPUT_CHARS` 14,000자) 안이라 합치기만 했다, 1·2 = 중간 요약 단계까지 갔다. `reduce_groups` = 만든 묶음 수. `reduce_fallback` = 실패하거나 시간 예산(⑧)을 넘겨 예전의 균등 샘플링 입력을 썼다.
- 섹션 40개 넘는 문서(`many_sections`)는 대개 `levels` 가 1 이상이고 `fallback` 은 false 여야 한다.
- 멈춤: `fallback` 이 true 인 문서가 섹션 40개 넘는 문서의 절반 이상이다 — `docker logs nl-lib-celery-llm 2>&1 | grep -E '계층 요약이 시간 예산|계층 요약 실패'` 로 까닭을 본다. 시간 예산 때문이면 `INGEST_STAGE_TIMEOUT_FINALIZE` 를 올린다(⑧).

⑬ 나중에 다시 돌릴 목록 — OCR 요청 실패가 있던 완료 문서. 지금 돌리지 않는다 — VLM 설정을 바꿨으면(④) 그 뒤에, 아니면 본 잡이 끝날 무렵 한 번 돌린다(본 잡이 도는 동안 해도 된다). 본 잡 아이템으로 보낸다 — 카나리 문서도 같은 `book_id` 로 본 잡에 있고, 카나리 잡을 다시 돌리면 본 잡과 동시에 돈다. 지금 `done` 인 아이템만 넣는다 — 도는 아이템을 retry 하면 그 체인의 기록이 버려지고, 다시 나간 체인은 옛 체인이 쥔 문서 락에 막혀 멈춘다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -At -c "SELECT json_build_object('item_ids', coalesce(json_agg(m.id ORDER BY m.id), '[]'::json), 'reset_stage', 'pending') FROM ingest_job_items m WHERE m.job_id = '$JOB' AND m.status = 'done' AND ((m.meta->>'ocr_errors')::int > 0 OR (NOT (m.meta ? 'ocr_errors') AND EXISTS (SELECT 1 FROM ingest_job_items c WHERE c.job_id = '$CANARY' AND c.book_id = m.book_id AND c.status = 'done' AND (c.meta->>'ocr_errors')::int > 0)))" \
  > /data/nl-lib/data/round07/ocr_errors_retry.json
cat /data/nl-lib/data/round07/ocr_errors_retry.json
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
  -H 'Content-Type: application/json' -d @/app/data/round07/ocr_errors_retry.json
```

- 본 잡 아이템에 `ocr_errors` 키가 없으면 옛 코드로 끝난 것이다 — 그런 문서는 카나리(새 코드) 결과로 고른다.

### 9-8. 본 잡 실패분 재시도

9-7 에 멈춤이 없을 때 한다. 추출부터 다시 돌린다(`reset_stage: "pending"`, spec §4). 먼저 그룹을 본다.

```bash
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$JOB/failures
```

- 본 잡의 실패는 모두 옛 코드가 낸 것이다(10-01 pause 뒤 in-flight 0 — 9-1). 진단 때는 `not_found` 560(그중 '섹션 없음' 545 · '카탈로그 row 없음' 15) · `extract_empty` 275 · `llm_error` 264, 합 1,099건이었다.
- `not_found` 는 '섹션 없음'만 `item_ids` 로 보낸다. '카탈로그 row 없음'은 카탈로그 문제라 재시도하지 않고 목록만 남긴다 — 행이 지금도 없으면 추출 단계가 PDF 메타 자동추출로 카탈로그 행을 새로 만들고 `doc_type` 이 어긋날 수 있다(§5-b).
- 나머지는 `error_group` 별로 보낸다. 아래 `for` 는 다시 돌려 볼 만한 그룹을 모두 담았다 — `/failures` 에 없는 그룹은 `retried` 가 0 이다. `unknown` 은 대표 메시지(`sample_error`)를 본 뒤 정하고, `no_text` 는 보내지 않는다(같은 코드로 다시 해도 같다 — 옛 코드는 이 그룹을 내지 않으므로 본 잡에는 아직 없다).

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT id, book_id, last_error FROM ingest_job_items WHERE job_id = '$JOB' AND status = 'failed' AND error_group = 'not_found' AND last_error LIKE '카탈로그 row 없음%'" \
  > /data/nl-lib/data/round07/catalog_missing.txt
IDS=$(docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT coalesce(json_agg(id ORDER BY id), '[]') FROM ingest_job_items WHERE job_id = '$JOB' AND status = 'failed' AND error_group = 'not_found' AND last_error LIKE '섹션 없음%'")
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
  -H 'Content-Type: application/json' -d "{\"item_ids\": $IDS, \"reset_stage\": \"pending\"}"; echo
for g in extract_empty llm_error llm_timeout vlm_error stale artifact_missing empty_body milvus_error minio_error; do
  echo -n "$g "
  docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
    -H 'Content-Type: application/json' -d "{\"error_group\": \"$g\", \"reset_stage\": \"pending\"}"; echo
done
```

- 응답 `retried` 의 합은 진단 때 기준 545 + 275 + 264 = 1,084건 안팎이다. `/failures` 를 다시 보면 '카탈로그 row 없음'(과 남겨 둔 `unknown`)만 남는다.
- 다시 돈 아이템이 또 실패하면 새 코드의 자동 재시도를 탄다 — 백오프(`INGEST_RETRY_BACKOFF_SECONDS` 120·600초)를 두고, `vlm_error` 와 옛 '섹션 없음'은 추출부터 다시 한다. `no_text` 로 끝나면 자동 재시도하지 않는다(9-9 목록).

### 9-9. 본 잡 재개

카나리 잡이 끝났는지 먼저 본다 — 두 잡을 동시에 `running` 으로 두지 않는다(위 배포 규칙).

```bash
docker exec nl-lib-fastapi curl -s localhost:8000/api/admin/ingest-jobs/$CANARY | grep -o '"status":"[a-z_]*"' | head -1   # completed 또는 completed_with_errors
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/resume
```

- 디스패처는 id 순으로 집으므로 9-8 에서 다시 돌린 아이템(앞 id)이 먼저 나간다. '섹션 없음' 545건은 스캔본이라 처음 몇 시간의 `rate_per_hour` 는 스캔본 처리량이다. 아래 수(예전에 시작한 적이 있는 아이템 + 지금 도는 아이템)가 진행 상한(32) 안팎까지 줄면 다시 돌린 아이템이 다 빠진 것이다.

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT count(*) FROM ingest_job_items WHERE job_id = '$JOB' AND status IN ('pending','dispatched','running') AND started_at IS NOT NULL"
```

- 그 뒤 1~2시간 동안 `GET …/ingest-jobs/$JOB` 의 `rate_per_hour`(최근 1시간)로 처리량을 잰다. 기대치(추정, spec §2.1)는 ODL 문서 약 340~390건/h, 스캔본 약 80~100건/h 다.
- `rate_per_hour_24h`·`eta_hours`(24시간 기준)는 재개 직후엔 멈춰 있던 시간이 창에 섞여 처리량은 낮게, ETA 는 길게 나온다 — 재개 하루 뒤부터 본다.
- 도는 동안 생기는 `no_text` 는 자동 재시도하지 않는다 — 가끔 목록을 뽑아 둔다(강제 OCR 까지 해도 글자가 없거나 강제 OCR 로 바뀔 쪽이 없는 문서).

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -At -c \
  "SELECT id, book_id, last_error FROM ingest_job_items WHERE job_id = '$JOB' AND status = 'failed' AND error_group = 'no_text'" \
  > /data/nl-lib/data/round07/no_text.txt
```

### 9-10. 빈 본문 완료분 재처리

본 잡이 도는 동안 해도 된다(완료된 아이템만 고른다). 먼저 `book_sections` 에 `book_id` 인덱스가 있는지 본다 — 없으면 돌리지 않는다(선정 질의가 고른 문서마다 `book_sections` 를 다시 훑어 문장 상한 15분에 걸린다).

```bash
docker exec nl-lib-postgres psql -U <user> -d <db> -c '\d book_sections'      # Indexes: 에 (book_id) btree — 이름은 대개 ix_book_sections_book_id
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round07/select_near_empty_items.py \
  --job $JOB --out /app/data/round07 --finished-before "$(cat /data/nl-lib/data/round07/deployed_at.txt)"
```

- `--finished-before` 는 9-3 에서 적은 배포 시각(시간대 포함)이다 — 새 코드로 끝난 문서는 다시 돌려도 결과가 같다. `--out` 은 `/app/data/` 아래 절대 경로로 준다 — 끝에 출력되는 retry 명령이 컨테이너 안의 그 경로를 읽는다.
- 출력의 `선정 N건` 을 spec 추정(약 907건)과, `완료 날짜(UTC)별` 의 `2026-09-03` 줄을 그날 일시 코드분 추정(약 458건)과 견준다. 크게 적으면(예: 선정 500건 아래) 쪽당 기준을 올려 다른 폴더에 다시 뽑고 늘어난 행을 CSV 로 본다 — 빈 격자·부분 본문 중에는 쪽당 150자를 넘는 것이 있다.

```bash
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/round07/select_near_empty_items.py \
  --job $JOB --out /app/data/round07/cpp300 --max-chars-per-page 300 --finished-before "$(cat /data/nl-lib/data/round07/deployed_at.txt)"
```

- 서버의 `/data/nl-lib/data/round07/near_empty_items.csv`(기준을 올렸으면 `cpp300/` 아래)를 사람이 본다. 뺄 문서가 있으면 같은 폴더 `near_empty_retry.json` 의 `item_ids` 에서도 뺀다. `vlm_capped` 가 true 인 문서는 VLM 60쪽 상한에 걸린 것이라 다시 돌려도 결과가 같다.
- 재처리는 대부분 VLM 으로 가서 약 1만 쪽·약 10시간(추정)이 든다. id 가 앞이라 본 잡의 새 아이템보다 먼저 돈다.

```bash
docker exec nl-lib-fastapi curl -s -X POST localhost:8000/api/admin/ingest-jobs/$JOB/retry \
  -H 'Content-Type: application/json' -d @/app/data/round07/near_empty_retry.json
```

기준을 올려 고른 목록을 쓰면 `-d @/app/data/round07/cpp300/near_empty_retry.json` 으로 보낸다. 9-7 ⑬ 의 OCR 요청 실패 목록도 이때 같이 보낼 수 있다.

## 롤백

- 코드: 이전 이미지 태그로 `docker compose up -d`
- DB: `alembic downgrade 0003_widen_varchar_fields` (doc_type/extra/잡 테이블 제거 — additive라 안전)
- Milvus: 인덱스 파라미터 env를 되돌리고 재생성하면 IVF_FLAT로 복귀
