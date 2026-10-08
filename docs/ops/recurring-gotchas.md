# 반복 함정 (Recurring Gotchas)

라이브(docker·실데이터)에서만 드러나는 패턴을 기록한다. 겪을 때마다 아래에 `## N. 제목` 섹션을 추가한다 — 라운드 문서가 아니라 상시 갱신 문서다. 표가 아니라 산문 섹션인 이유: 항목 하나가 원인 여러 개·하위 절차·쉘 명령(`|` 포함)을 가지는 경우가 흔한데, 표 셀에는 이게 안 들어간다.

각 섹션 구성: 증상 · 원인 · 해결 · 재발 방지.

## 1. dev 스택 코드 변경이 반영 안 됨 — 이미지가 registry pull 방식이라

- **날짜**: 2026-09-04 (round01)
- **증상**: `app/` 코드를 고치고 `docker compose -f docker-compose.dev.yml up -d`를 실행해도 변경이 반영되지 않는다.
- **원인**: `fastapi-dev`·celery 워커 4종+`celery-beat-dev`·`nuxt-dev`는 전부 `build:` 키가 없고 `image: landsoftdocker/nl-lib-fastapi:dev`처럼 registry에서 미리 빌드된 이미지를 pull한다. `up -d`는 이미지를 새로 빌드하지 않는다.
- **해결**: `bash scripts/build_dev_images.sh`로 이미지를 다시 빌드+push한 뒤, Portainer에서 `nl-lib-dev` 스택을 Pull & Redeploy한다.
- **재발 방지**: dev 스택에서 코드 반영이 안 될 때 가장 먼저 "이미지를 다시 빌드했는가"부터 확인한다. `docker compose config`는 이 문제를 못 잡는다(파싱만 하지 이미지 소스는 안 봄).

## 2. dev 스택은 Windows 개발 PC에서 직접 못 띄운다

- **날짜**: 2026-09-04 (round01)
- **증상**: `docker compose -f docker-compose.dev.yml up -d`가 볼륨/네트워크 오류로 실패하거나, 뜨더라도 `fastapi-dev`가 GPU를 못 잡고 죽는다.
- **원인**: 볼륨 5종(`nl_lib_dev_etcd_data` 등)과 `nl-lib-net`이 전부 `external: true`라 prod 스택이 먼저 떠 있어야 하고, `fastapi-dev`는 NVIDIA GPU를 예약하며 `/data/models/.hf-cache`·`/data/nl-lib/dev-data` 같은 Linux 경로를 바인드마운트한다.
- **해결**: dev 스택은 GPU 서버에서만 띄운다. 개발 PC(Windows 등)에서는 코드만 수정하고, 반영은 위 1번 절차(빌드+push → Portainer redeploy)로 한다.
- **재발 방지**: "왜 로컬에서 dev 스택이 안 뜨지?"라는 질문 자체가 잘못된 전제다 — 애초에 로컬에서 띄우는 스택이 아니다.

## 3. 운영 스택에 코드가 반영 안 됨 — build_dev_images.sh 는 `:dev` 태그만 만든다

- **날짜**: 2026-09-17 (round03)
- **증상**: 재빌드·푸시·재배포를 마쳤는데 `docker exec nl-lib-fastapi python -c "from workers.tasks import <신규함수>"` 가 `ImportError` 로 죽는다.
- **원인**: `scripts/build_dev_images.sh` 는 `landsoftdocker/nl-lib-fastapi:dev` 를 빌드·푸시한다. 운영 스택(`docker-compose.yml`)은 `:latest` 를 쓴다. 새 코드가 `:dev` 이미지에만 들어가고 운영 컨테이너는 옛 `:latest` 그대로다.
- **해결**: `NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi` 로 태그를 override 한 뒤 운영 스택을 Pull & Redeploy 한다.
- **재발 방지**: 1번 함정의 연장이다. "빌드했는가" 다음에 **"어느 태그로 빌드했는가"** 를 확인한다. 배포 없이 급히 돌려야 하면 `docker exec -i <컨테이너> python - <<'PY'` 로 단독 스크립트를 stdin 에 먹이면 이미지 변경이 필요 없다.

## 4. 스크립트를 파일 경로로 실행하면 앱 모듈을 못 찾는다

- **날짜**: 2026-09-16 (round03)
- **증상**: `docker exec nl-lib-fastapi python /app/data/recovery/foo.py` 가 `ModuleNotFoundError: No module named 'core'` 로 죽는다. 같은 코드를 `python -c` 로 넣으면 된다.
- **원인**: 파이썬은 스크립트를 경로로 실행하면 `sys.path[0]` 을 **스크립트가 있는 디렉터리**로 잡는다(`/app/data/recovery`). `python -c` 나 `python -`(stdin) 은 cwd(`/app`, 이미지의 WORKDIR)가 들어와 앱 모듈이 보인다.
- **해결**: `docker exec -e PYTHONPATH=/app ...` 를 붙이거나, `docker cp` 로 `/app/` 밑에 두고 실행한다.
- **재발 방지**: `/app/data/` 바인드 마운트는 앱 이미지에 `scripts/` 가 없어 쓰는 통로다. 그 경로에서 실행할 땐 `PYTHONPATH=/app` 이 기본이라고 생각한다.

## 5. KCI 로더는 xlsx 전용 — CSV 를 넣으면 죽는다

- **날짜**: 2026-09-16 (round03)
- **증상**: KCI 카탈로그 CSV 적재가 `openpyxl.utils.exceptions.InvalidFileException: openpyxl does not support .csv file format` 으로 실패한다.
- **원인**: `domains/nl_library/loaders/kci_xlsx.py` 의 `load_kci_xlsx()` 가 `load_workbook()` 직결이다. NL MARC/MODS 로더는 `_read_rows()` 로 xlsx·CSV 를 모두 처리하는데 KCI 만 다르다. 헤더 판별용 `read_headers()` 는 CSV 를 읽으므로 **자동 판별은 통과하고 본 적재에서 죽는다** — 더 헷갈린다.
- **해결**: xlsx 를 쓰거나, 같은 매핑을 재사용하는 별도 경로(`scripts/recovery/load_kci_csv.py`)로 적재한다.
- **재발 방지**: 로더가 포맷을 지원하는지는 `detect()` 가 아니라 `load()` 구현을 봐야 안다.

## 6. Milvus 메타청크의 구분자 ` | ` 가 값 안에도 들어있다

- **날짜**: 2026-09-16 (round03)
- **증상**: 메타청크를 `split(" | ")` 로 파싱하면 저자·주제가 두 동강 난다.
- **원인**: 메타청크는 `제목: … | 저자: … | 출판사: …` 형태인데, MARC 다중값 필드 자체가 ` | ` 로 이어져 있다. 실측: `저자: 柳在元 | 林慧俊`, `주제: 인연 | 덫 | 사랑`.
- **해결**: 알려진 라벨 집합(`제목`·`기관`·`저자`·`출판사`·`발행년도`·`KDC분류`·`주제`·`키워드`·`초록`)과 `": "` 가 이어지는 경계로만 자른다. `scripts/recovery/restore_from_milvus_meta.py` 참고.
- **재발 방지**: 구분자가 값에 나타날 수 있는 포맷은 라벨 경계로 파싱한다.

## 7. SQLAlchemy `text()` 는 바인드 파라미터 뒤의 `::` 캐스트를 못 넘긴다

- **날짜**: 2026-09-17 (round03)
- **증상**: `UPDATE ... SET extra = coalesce(extra,'{}'::jsonb) || :e::jsonb` 가 `psycopg2.errors.SyntaxError: syntax error at or near ":"` 로 죽는다. 같은 쿼리의 다른 파라미터(`:a`, `:i`)는 `%(a)s` 로 정상 변환된다.
- **원인**: 파라미터 바로 뒤에 PostgreSQL 캐스트 `::` 가 붙으면 SQLAlchemy 가 그 파라미터를 바인딩하지 못하고 SQL 에 그대로 흘려보낸다.
- **해결**: `CAST(:e AS jsonb)` 로 쓴다. 값이 없는 `'{}'::jsonb` 같은 리터럴 캐스트는 문제없다.
- **재발 방지**: `text()` 안에서 `:param::type` 패턴을 쓰지 않는다.

## 8. `NOT IN (서브쿼리)` 가 데이터가 늘면 급격히 느려진다

- **날짜**: 2026-09-16 (round03)
- **증상**: 고아 문서 조회가 즉시 끝나다가, 카탈로그 복구 후 5분 넘게 멈춘다.
- **원인**: `WHERE book_id NOT IN (SELECT cnts_id FROM library_catalog)` 는 NULL 의미론 때문에 안티조인으로 풀리지 않는다. 대상이 246행일 땐 티가 안 나다가 24만 행이 되자 드러났다.
- **해결**: `WHERE NOT EXISTS (SELECT 1 FROM library_catalog c WHERE c.cnts_id = d.book_id)` 로 바꾼다. distinct 를 먼저 줄이면 더 빠르다.
- **재발 방지**: 진단 쿼리도 데이터 규모가 바뀌면 성능이 뒤집힌다. `NOT IN` 서브쿼리는 처음부터 `NOT EXISTS` 로 쓴다.

## 9. 표지가 보인다고 DB 가 멀쩡한 게 아니다

- **날짜**: 2026-09-15 (round03)
- **증상**: `library_catalog` 이 통째로 비었는데도 검색 결과의 표지 이미지는 정상 표시돼, 피해 범위를 과소평가하게 만든다.
- **원인**: 썸네일 엔드포인트(`app/api/book.py:368`)가 ① DB `cover_image_key` → ② MinIO 캐시 → ③ 원본 PDF 1페이지 즉석 렌더 순으로 폴백한다. DB 행이 없어도 ③ 으로 그려진다.
- **해결**: 데이터 유실을 의심할 땐 화면이 아니라 저장소별 건수를 직접 센다(`library_catalog` · `book_sections` · Milvus · MinIO).
- **재발 방지**: 폴백이 촘촘한 화면은 진단 지표로 쓰지 않는다.

## 10. jsonb `?` 는 키 존재만 본다 — 빈 배열이 "값 있음"으로 새어든다

- **날짜**: 2026-09-18 (round03)
- **증상**: (이번엔 터지지 않았다 — 잠복 함정으로 기록한다.) 참고문헌 복구 스크립트의 대상 선정과 검증 쿼리가 모두 `extra ? 'references'` 를 썼다. 이 조건은 값이 `[]` 인 문서를 "참고문헌 있음"으로 세고 복구 대상에서도 뺀다.
- **원인**: 적재 파이프라인(`app/services/ingestion/stages.py`)이 초록·목차·키워드 중 하나만 있어도 `extra["references"]` 를 **빈 리스트째로** 기록한다. jsonb `?` 는 키 존재만 본다.
- **실측**: 운영에서는 빈 배열이 **0건**이었다. 파이프라인이 쓴 `extra` 는 2026-09-14 카탈로그 전멸 때 행과 함께 사라졌고, 이후 `extra` 를 채운 복구 스크립트는 `if not refs: continue` 로 빈 결과를 쓰지 않아 빈 배열이 생길 경로가 없었다. 재인덱싱이 돌면 다시 생긴다.
- **해결**: 존재가 아니라 길이로 판정한다 — `jsonb_array_length(coalesce(extra->'references','[]'::jsonb)) = 0`.
- **재발 방지**: jsonb 배열·객체 필드에 `?` 를 쓸 땐 "키가 있는가"와 "값이 비었는가"가 다른 질문임을 먼저 확인한다. 그리고 **코드 경로가 있다고 그 경로를 탄 데이터가 있는 것은 아니다** — 영향 범위는 세어서 확정한다.

## 11. 정렬이 걸린 `LIMIT` 은 표본이 아니다

- **날짜**: 2026-09-17 (round03)
- **증상**: 참고문헌 재추출 dry-run 500건에서 25.4% 가 나와 전체 41,399건에 약 1만 건을 기대했으나, 실제 실행은 16.7%(6,931건)였다.
- **원인**: dry-run 대상이 `ORDER BY cnts_id LIMIT 500` 으로 뽑혀 ID 앞쪽에 몰렸고, 그 구간에 추출 성공률이 높은 문서가 편중돼 있었다.
- **해결**: 비율을 외삽할 목적이면 `ORDER BY random() LIMIT n` 을 쓴다.
- **재발 방지**: dry-run 결과를 전체에 곱하기 전에 그 표본이 어떻게 뽑혔는지 먼저 본다. 정렬된 앞부분은 모집단을 대표하지 않는다.

## 12. Portainer 이미지 Pull 이 수 GB 이미지에서 타임아웃한다

- **날짜**: 2026-09-17 (round03)
- **증상**: Portainer 스택 Redeploy 시 `context deadline exceeded` 로 실패한다. 같은 이미지를 서버 셸에서 받으면 정상이다.
- **원인**: Portainer 의 Docker API 클라이언트 타임아웃이 CUDA 포함 수 GB 이미지 pull 시간을 못 견딘다.
- **해결**: 서버에서 `docker pull <이미지>` 로 먼저 받아두고, Portainer 에서는 Redeploy 만 누른다(이미 로컬에 있으면 즉시 끝난다).
- **재발 방지**: 큰 이미지를 새로 빌드한 배포는 Portainer 에 맡기지 말고 pull 을 분리한다.
- **재발 (2026-09-23, round04a)**: 스택 정의를 고쳐 **Update the stack** 을 누를 때 "Re-pull image" 토글을 켠 채였더니 `Request failed with status code 500` 으로 실패했다. 새 이미지는 서버에서 이미 받아 둔 상태였는데, 토글이 스택의 **모든** 이미지(`vllm/vllm-openai:latest-cu130` 등)를 다시 받으려다 끊긴 것이다. 적용 전 단계에서 실패해 컨테이너는 하나도 바뀌지 않았고, 토글을 끄고 다시 누르자 바로 됐다. UI 는 원인을 보여 주지 않으니, 500 이 나면 재시도 전에 `docker ps -a --format '{{.Names}}	{{.CreatedAt}}'` 로 무엇이 바뀌었는지부터 본다. Portainer 로그는 오류를 `ERR` 로 적는다(`grep -i error` 로는 안 걸린다).

## 13. `services.search.pipeline` 을 모듈 최상단에서 import 하면 로컬 테스트가 통째로 죽는다

- **날짜**: 2026-09-21 (round04a)
- **증상**: 새 모듈이 `from services.search.pipeline import search` 를 최상단에 넣자 `pytest` 가 `ModuleNotFoundError: No module named 'torch'` 로 **collection 단계에서 중단**된다. 그 모듈의 테스트뿐 아니라 세션 전체가 0건이 된다.
- **원인**: `pipeline.py` → `reranker.py` → `import torch` 인데, **torch 는 로컬 venv 에 의도적으로 없다.** `requirements.txt` 에도 없고 Dockerfile 에서 CUDA 버전으로 따로 설치한다(`reranker.py` 주석 참고).
- **해결**: torch 를 끌어오는 모듈(`pipeline`·`reranker`·`embedder`)은 **함수 본문 안에서 import 한다.** 이미 코드베이스의 관례다 — `app/api/book.py:619`, `app/main.py:53`, `app/services/ingestion/stages.py:87` 이 전부 그렇게 한다.
- **재발 방지**: 검색·임베딩·리랭킹을 쓰는 새 모듈을 만들 때 최상단 import 를 쓰지 않는다. 순수 계산 부분을 같은 파일에 두고 싶다면 더더욱 — 그 순수 함수 테스트까지 같이 죽는다.


## 14. 운영 스키마를 만드는 것은 Alembic 이 아니라 lifespan(`create_all`·ad-hoc `ALTER`)이다 — 버전 스탬프가 현실보다 뒤처져 있다

- **날짜**: 2026-09-22 (round04a)
- **증상**: 서버의 `alembic_version` 이 `0003_widen_varchar_fields` 인데, `0004` 가 만드는 객체(`ingest_jobs`·`ingest_job_items`·`library_catalog.doc_type`·`extra`·인덱스 6종)는 **전부 실재한다**(10/10 확인). 이 상태에서 `alembic upgrade head` 를 돌리면 `0004` 의 `op.add_column("library_catalog", "doc_type")` 이 `DuplicateColumn` 으로 죽는다.
- **원인**: 스키마를 만드는 경로가 Alembic 말고 **둘 더** 있다. 둘 다 `app/main.py` 의 lifespan 안에 있고 FastAPI 가 뜰 때마다 돈다.
  - `Base.metadata.create_all`(33행) — 새 **테이블**을 모델에서 만든다. `ingest_jobs`·`ingest_job_items`(그리고 round04a 의 `research_*`)는 이걸로 마이그레이션 없이 생겼다. `create_all` 은 기존 테이블에 컬럼을 추가하지 못한다.
  - `ALTER TABLE … ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` 블록(41~50행, `ecbc42a` 의 "기존 DB 자가치유") — `library_catalog.doc_type`·`extra`·`ix_library_catalog_doc_type` 을 넣는다. `0004` 가 만드는 것과 **같은 객체**다. `doc_type`·`extra` 는 수동 SQL 로 들어간 것이 아니다 — README §8.4 의 수동 SQL 4건은 `book_figures`·`cover_image_key`·`introduction`·`themes` 이고 이 두 컬럼과 무관하다.

  앞의 두 경로는 Alembic 을 거치지 않으므로 객체는 생기고 스탬프만 뒤처졌다.
- **파생 함정**: 새 모델이 포함된 이미지가 뜨면 `create_all` 이 그 테이블을 **먼저** 만든다. 그 뒤에 해당 마이그레이션을 돌리면 이번엔 `DuplicateTable` 로 죽는다. 그리고 `create_all` 이 만든 테이블에는 모델의 `server_default` 만 반영되고 `default=`(파이썬 측)는 DB 기본값이 되지 않아, 마이그레이션이 만들었을 테이블과 미묘하게 다르다.
- **해결**: ① 객체가 전부 실재함을 확인한 뒤 `alembic stamp <리비전>` 으로 현실과 스탬프를 맞춘다. ② **`stamp` 는 DDL 뿐 아니라 마이그레이션 안의 데이터 백필(`op.execute(UPDATE …)`)도 건너뛴다** — 스탬프 전에 그 UPDATE 가 필요한 행이 남아 있는지 따로 세고, 남았으면 손으로 돌린다. ③ 새 테이블은 `create_all` 이 만들게 두고 `stamp` 로 맞추거나, 이미지 배포 전에 마이그레이션을 먼저 돌린다 — 둘 중 하나로 정하고 섞지 않는다.
- **재발 방지**: 배포 전에 `select version_num from alembic_version` 과 실제 객체 존재를 **따로** 확인한다. 버전 테이블은 현실을 반영하지 않는다. 그리고 **스키마를 만드는 경로가 셋(`create_all` · lifespan 의 ad-hoc `ALTER` · Alembic)인 구조 자체가 원인**이므로, 대회 이후 정본 하나만 남긴다. `create_all` 만 지우고 lifespan `ALTER` 블록을 남기면 앱이 뜰 때마다 Alembic 밖에서 DDL 이 계속 돌아 같은 사고가 다음 컬럼에서 재발한다. 그 `ALTER` 는 컬럼이 이미 있어도 테이블 배타 잠금을 요구한다는 부작용도 있다(18번).
- **현재 서버**: `alembic_version = 0007_research_work` — round06a 운영 배포(2026-10-06) 때 테이블 7개(`research_works`·`research_generations`·`research_topics`·`research_gap_checks`·`research_reading`·`paper_facets`·`research_proposals`)와 인덱스 8개를 확인한 뒤 `stamp` 로 맞췄다(lifespan 이 `models.research_work` 를 import 해 `create_all` 이 만드는 새 테이블이다 — 위 ③ 의 `create_all` + `stamp` 경로, `0007` 에는 데이터 백필이 없다). 그 전 `0006_history_items` 는 round04b 운영 배포(2026-09-28), `0005_research_jobs` 는 2026-09-23 확인.


## 15. LLM 은 프롬프트 JSON 예시의 개수를 베낀다 — 구성은 코드가 정한다

- **날짜**: 2026-09-23 (round04a)
- **증상**: 딥리서치 보고서가 하위질문 3개·근거 10편을 모아놓고 **절 1개, 논문 1편, 향후 과제 1개**만 냈다. 인용 무결성 검사(미해석 마커 0)는 통과해 오류로 보이지 않았다. 단위 테스트는 가짜 LLM 응답을 쓰므로 라이브 모델에서만 드러난다.
- **원인**: 종합 프롬프트의 출력 예시가 `{"sections": [{…, "papers": [{…}], "future": [{…}]}]}` — 배열마다 항목이 하나였다. gemma-3-12b 는 이를 형식이 아니라 **개수까지 포함한 견본**으로 따랐다. 어느 절·어느 논문을 실을지를 모델에게 맡긴 설계가 이 실패를 가능하게 했다.
- **해결**: 구성을 코드로 옮겼다 — 하위질문마다 호출 1회, 소제목·논문 목록은 코드가 정하고 모델은 `{"summaries": {"E1": …}}` 처럼 **채울 칸이 이미 정해진** 출력만 낸다. 빠뜨린 칸은 코드가 세어 한계로 보고한다(`synthesizer.build_section`).
- **재발 방지**: LLM 출력의 **구조(몇 개·무엇을)** 가 정확해야 하면 모델에게 고르게 하지 말고 코드가 정한다. 불가피하면 프롬프트에 기대 개수와 키 목록을 명시한다("다음 번호를 빠짐없이: E1, E3"). 라이브 검증 스크립트는 무결성뿐 아니라 **구성(입력 대비 출력 개수)** 도 확인한다. 같은 드라이런에서 모델이 시키지 않은 `[E#]` 를 요약에 달기도 했다 — 검증을 거치지 않는 필드에 모델 출력이 들어가면 그 필드도 정리한다.

## 16. 앱 서비스는 모두 같은 `:latest` 이미지다 — 배포 한 번이 도는 적재 워커를 끊는다

- **날짜**: 2026-09-23 (round04a)
- **증상**: 대량 인덱싱이 도는 중에 딥리서치 코드만 반영하려고 스택을 업데이트하면, 손대지 않은 `celery-worker`·`celery-cpu`·`celery-llm`·`celery-embed`·`celery-beat` 까지 재생성된다. 처리 중이던 적재 아이템이 끊긴다. 스택이 아니라 `nl-lib-celery-llm` 컨테이너 하나만 recreate 해도 같다 — 그 워커가 적재의 요약·마무리 단계(`q_llm`)를 돌리고 있기 때문이다.
- **원인**:
  - fastapi 와 적재 워커 5개(그리고 round04a 의 `celery-research`·`celery-research-plan`)가 전부 `landsoftdocker/nl-lib-fastapi:latest` 를 쓴다. 서버에서 새 이미지를 `docker pull` 하면(12번 절차) 로컬 `:latest` 가 새 이미지를 가리키고, 스택 업데이트(compose `up`)는 이미지가 바뀐 서비스를 모두 재생성한다. `x-common-env` 를 고쳐도 같다 — 그걸 물고 있는 서비스 전부의 설정이 바뀐다.
  - `q_llm` 은 딥리서치 전용이 아니다. `tasks.stage_summarize`·`tasks.stage_finalize` 가 같은 큐이고 소비자는 `celery-llm` 하나다(`workers/celery_app.py`). 컨테이너를 멈추면 도커가 SIGTERM 뒤 10초 만에 SIGKILL 하므로 수 분짜리 요약 태스크는 중간에 죽는다.
- **해결**: 인덱싱이 도는 동안에는 스택 업데이트(Pull & Redeploy 포함)를 하지 않는다. 앱 코드 배포는 인덱싱이 끝난 뒤, 또는 적재를 pause 해 in-flight 를 비운 뒤(아래) 한 번에 한다. 딥리서치 큐 전환처럼 일부 서비스만 바뀌는 설정은 `x-common-env` 가 아니라 해당 서비스 env 에 둔다(`RESEARCH_QUEUE`·`RESEARCH_PLAN_QUEUE` 가 fastapi·딥리서치 워커에만 있는 이유). 인덱싱 중에 꼭 먼저 내보내야 하면 **바뀐 코드를 쓰는 컨테이너만** recreate 하되, 새 compose 를 다시 읽지 않는 방식으로 한다 — 서버에서 `docker pull` 로 이미지를 받아 두고(12번, pull 만으로는 아무것도 재시작되지 않는다) Portainer 에서 해당 컨테이너만 Recreate 한다(`nl-lib-fastapi`·`nl-lib-nuxt` 를 Recreate 했으면 끝에 게이트웨이를 reload 한다 — 20번). 컨테이너 Recreate 는 기존 컨테이너 설정(env 포함)을 그대로 쓴다. 새 compose 로 `docker compose up -d fastapi celery-llm` 을 하면 fastapi 만 `RESEARCH_QUEUE: q_research` 를 받아 딥리서치 잡이 소비자 없는 큐에 쌓인다. 어느 쪽이든 `celery-llm` recreate 는 그 순간의 적재 요약·마무리 태스크(최대 4개)를 끊는다. **끊지 않으려면 적재 잡을 pause 하고 in-flight(`dispatched`·`running`)가 0 이 된 뒤 재생성한다**(`bulk_ingest_runbook.md` §8) — 끊기는 태스크가 없으면 아래 복구 경로도 돌지 않는다.
- **끊긴 적재 아이템은 어떻게 되나 (코드 근거)**: 볼륨의 데이터는 컨테이너 재생성으로 지워지지 않는다 — Postgres·Milvus·MinIO 는 외부 볼륨(`external: true`)이고, 끝난 단계의 결과는 이미 커밋돼 있다. 문제는 끊긴 아이템이다. 복구 경로가 **둘 다** 돈다 — 한쪽이 다른 쪽을 막지 않는다.
  - ① stale 복구: 디스패처(beat 30초)가 단계 타임아웃(요약·임베딩 1200초·마무리 900초, 아직 안 집힌 디스패치는 14400초)을 넘긴 아이템을 `failed`(`error_group=stale`)·`attempt+1` 로 표시하고, `attempt < max_attempts`(기본 3)면 **마지막 체크포인트(`item.stage`)부터** 새 체인을 디스패치한다. 옛 태스크를 revoke 하지는 않는다(`job_runtime._recover_stale`·`_dispatch_for_job`).
  - ② 브로커 재전달: `task_acks_late=True` 라 끊긴 태스크의 메시지는 ack 되지 않은 채 Redis 에 남는다. 도커는 SIGTERM 10초 뒤 SIGKILL 해 워커가 메시지를 되돌리지 못하고, 메시지는 전달 시각 기준 `visibility_timeout`(7200초) 뒤 재전달된다 — 체인의 뒤 단계(`embed_index`·`finalize`)까지 달고.
  - 그래서 ①이 약 20분 뒤 새 체인으로 아이템을 끝내고(마무리 단계가 추출 아티팩트를 지운다), 약 2시간 뒤 ②의 옛 체인이 **같은 아이템을 다시 돌린다.** 단계 래퍼(`_run_stage`)는 `canceled` 만 건너뛰고 `done`·체크포인트는 보지 않는다. 재전달된 요약은 이미 요약된 섹션을 건너뛰어(기본 `resume_summaries`) 그냥 통과하고, 이어진 `embed_index` 는 아티팩트가 없어 본문이 빈다.
    - **논문**: 초록(없으면 메타 필드)으로 대체해 `index_chunks` 가 그 논문의 청크를 delete 후 insert 한다 — **PDF 본문 청크가 초록 청크로 덮인다.** 이미 적재된 데이터가 실제로 손상되는 경로다.
    - **도서**: `empty_body` 가드가 인덱스를 건드리기 전에 멈춰 벡터는 멀쩡하지만, 아이템이 `failed`·`attempt+1` 이 되고 `library_catalog.ingest_state` 에 거짓 `failed` 가 찍힌다.
  - 영향 범위는 재생성 순간 요약·임베딩 중이던 아이템이다(`celery-llm` 은 최대 4건, `celery-embed` 는 1건). 추출 중에 끊긴 아이템은 옛 체인이 추출부터 다시 해 아티팩트를 새로 만들므로 덮이지 않는다(비용만 든다).
  - **의심 아이템 찾기**: stale 복구를 거친 아이템은 `done` 이 된 뒤에도 `last_error` 에 `stale 복구` 문구가 남는다 — `SELECT id, book_id, status, stage FROM ingest_job_items WHERE job_id = '<job_id>' AND last_error LIKE '%stale 복구%'`. 되돌리는 법은 그 아이템을 추출부터 다시 돌리는 것이다(`POST /api/admin/ingest-jobs/{job_id}/retry` `{"item_ids": [...], "reset_stage": "pending"}` — 원본 PDF 로 다시 적재). 인덱싱이 끝난 뒤 한 건으로 먼저 확인한다.
  - 근본 원인(단계 래퍼가 `done` 을 보지 않음, stale 복구가 옛 태스크를 revoke 하지 않음)은 적재 코드에 있다. 인덱싱 잡이 도는 동안에는 적재 코드를 고치지 않으므로 인덱싱이 끝난 뒤의 과제로 남겼다가, round07 에서 적재를 멈추고 고쳤다(아래 **근본 수정**).
  - 이미 두 번 실패한 아이템은 한도에 닿아 자동 재시도에서 빠지고, `POST /api/admin/ingest-jobs/{job_id}/retry` `{"error_group": "stale"}` 로 되살린다(attempt 를 0 으로 리셋).
- **컨테이너를 끊지 않아도 같은 경로가 열린다 — 과도기 구성의 딥리서치.** 전용 워커로 넘기기 전(`RESEARCH_QUEUE` 기본값 `q_llm`)에는 딥리서치 실행이 `celery-llm` 슬롯을 잡마다 최대 25분 쥔다. 여럿이 슬롯을 쥐면 요약·마무리를 기다리는 적재 아이템이 단계 타임아웃을 넘긴다 — 타임아웃은 `updated_at` 부터 재고 큐 대기 중에는 갱신되지 않으며, 마무리를 기다리는 아이템은 900초라 더 빨리 걸린다. 그러면 ①과 같은 stale 복구가 새 체인을 띄우고, 큐에 남은 옛 메시지도 그대로 돈다(`_run_stage` 는 `canceled` 만 건너뛴다). 끝나는 순서에 따라 한쪽 `finalize` 가 아티팩트를 지운 뒤 다른 쪽 `embed_index` 가 돌면 위의 논문 덮어쓰기가 난다. 머지 전 리뷰에서 이산 사건 모델로 재현했다(잡 여러 건을 몰아서 승인하거나 긴 잡이 겹칠 때). 그래서 API 가 이 구성에서는 실행을 한 번에 한 잡으로 묶는다(approve·retry 429, `api/research.py` `_to_run_queue`) — 같은 모델에서 한 번에 한 잡이면 25분짜리를 연달아 돌려도 stale 은 0 이었다. 그래도 가정값 위의 결과라, **적재 잡이 `running` 인 동안에는 운영 딥리서치를 돌리지 않는다 — pause 하고 in-flight 0 을 본 뒤 돌린다**(`bulk_ingest_runbook.md` §8). pause 만으로는 모자라다 — `resume` 뒤 첫 틱이 그동안 타임아웃을 넘긴 아이템을 복구한다.
- **근본 수정 — round07 (2026-10, 배포는 `bulk_ingest_runbook.md` §9)**: 위 경로를 적재 코드에서 닫았다(`app/workers/job_runtime.py`).
  - **실행 토큰**: 디스패처가 체인을 보낼 때마다 새 `run_token` 을 아이템 `meta.run_token` 에 적고 모든 단계 태스크 인자로 넘긴다(`.si(item_id, run_token)`). `_run_stage` 는 메시지의 토큰이 아이템의 지금 토큰과 다르면(stale 복구로 새 체인이 떴거나 재전달된 옛 메시지) 실행하지 않고 체인을 멈춘다 — `celery.exceptions.Ignore`, 로그 `실행 안 함 — 실행 토큰 불일치(…) → 체인 정지`. 토큰 없이 온 배포 전 메시지는 아이템에도 토큰이 없을 때만 돈다. stale 복구는 아이템을 `failed`(`stale`)로 찍는 순간 토큰을 새 값으로 바꿔 옛 체인을 끊는다. 수동 retry 는 토큰을 `retry` 로 바꾼다 — 디스패처가 다시 보낼 때 새 토큰으로 덮으므로, 그 사이 큐에 남은 옛 메시지는 토큰이 있든 없든 그 아이템을 돌리지 못한다.
  - **기록마다 토큰을 다시 본다 — 단계 타임아웃은 시도별 하드 마감이다**: 단계가 도는 동안 토큰이 바뀔 수 있어 시작·성공·실패 기록마다 아이템을 FOR UPDATE 로 다시 읽어 대조하고, 다르면 아무것도 쓰지 않는다. 시작 기록이면 실행 안 함, 성공 기록이면 `늦은 성공 기록 버림 — 새 체인이 있다 → 체인 정지`(finalize 도 카탈로그를 `embedded` 로 바꾸지 않는다), 실패 기록이면 `늦은 실패 기록 버림 — 새 체인이 있다`(카탈로그 상태는 두고 예외만 올린다). 토큰 없는 배포 전 메시지도 같다 — 도는 사이 아이템에 토큰이 생겼으면(stale 복구·retry) 그 기록을 버린다. 버리는 것은 아이템·카탈로그의 상태 기록뿐이다 — 그 시도가 이미 쓴 `book_sections`·MinIO 아티팩트·Milvus 청크는 남는다. 그래서 단계 타임아웃(추출 3600·요약 1200·embed 1200·마무리 900초)을 넘긴 시도는 결과가 버려지고, 문서 락(`BookLock`) TTL 도 같은 값이라 다시 나간 체인이 같은 문서를 옛 시도와 함께 돌 수 있다(카나리에서 단계 꼬리와 겹쳐 쓴 흔적을 본다 — `bulk_ingest_runbook.md` §9-7 ⑧·⑨).
  - **체크포인트 확인**: 아이템이 `done` 이거나 체크포인트가 그 단계를 이미 지났으면 멈춘다 — 위 ②의 재전달된 요약·`embed_index` 가 여기서 멈춘다.
  - **락 경합 시 체인 정지 — `pending` 으로 되돌리지 않는다**: 단계가 문서 락을 얻지 못하면 아이템을 건드리지 않고 `실행 안 함 — 락 경합 → 체인 정지` 로 이 체인만 멈춘다. 옛 코드는 `pending` 으로 되돌린 뒤 `skipped` 를 돌려줘 체인이 다음 단계로 갔다. 되돌리지 않는 까닭: 되돌리면 디스패처가 30초 안에 새 토큰으로 다시 보내, 락을 쥐고 일하는 체인의 다음 단계를 토큰 불일치로 끊고 경합을 되풀이한다. 대가: 멈춘 아이템은 `dispatched`(단계 사이였으면 `running`)로 남아 잡의 진행 상한(`INGEST_HIGH_WATER`) 한 칸을 쥔 채, 마지막 갱신에서 `DISPATCH_STALE_SECONDS`(기본 14400초) 뒤 stale 복구가 회수할 때까지 기다린다. 같은 `book_id` 를 두 잡이 동시에 돌리면 이 경로를 탄다 — 카나리 잡과 본 잡을 동시에 `running` 으로 두지 않는다(`bulk_ingest_runbook.md` §9).
  - **stale 판정 분리**: `_run_stage` 가 시작할 때 `meta.stage_running`·`stage_started_at` 을 적고 끝날 때 지운다. 실행 중이면 그 단계 타임아웃을 단계 시작 시각부터, 다음 단계를 기다리는 중이면 대기 상한(`DISPATCH_STALE_SECONDS`)을 마지막 갱신부터 잰다 — 큐 대기를 실행 시간으로 세던 오판(위 '컨테이너를 끊지 않아도 같은 경로가 열린다')이 없어진다.
  - PDF 가 있던 논문(`meta.pages > 0`)인데 추출 아티팩트가 없으면 초록으로 색인하지 않고 `artifact_missing` 으로 멈춘다. 초록 대체는 PDF 없는 메타데이터 전용 논문만 쓴다.
  - **배포 규칙은 그대로다.** 재생성은 여전히 도는 태스크를 끊는다 — 중복 체인은 멈추지만 끊긴 일은 다시 해야 한다. 적재 워커를 재생성할 땐 pause → in-flight 0 → 재생성 → resume 순서로 한다(`bulk_ingest_runbook.md` §8·§9).
- **재발 방지**: 배포 전에 "지금 도는 적재 잡이 있는가"와 "이 배포가 어느 컨테이너를 재생성하는가"를 먼저 본다. 적재 워커를 재생성해야 하면 pause → in-flight 0 확인 → 재생성 → resume 순서로 한다(`bulk_ingest_runbook.md` §8). fastapi 를 재시작하면 lifespan 의 `ALTER TABLE library_catalog` 가 배타 잠금을 기다리는 동안 그 뒤 조회·쓰기가 줄 선다(18번). `MILVUS_RECREATE_ON_MISMATCH` 는 반드시 `false` 인지 확인한다 — `ensure_collection()`(`app/services/ingestion/indexer.py`)은 이 값이 `true` 면 스키마가 다를 때 컬렉션을 지우고 새로 만든다. 이 함수를 부르는 것은 fastapi 기동만이 아니다 — fastapi 의 검색·관리 API, 적재 `celery-embed`·단건 `celery-worker`(색인), `celery-research`(검색), `celery-control` 의 1시간 정리(`cleanup_temp_files` 의 Milvus flush)도 부른다. 모두 `x-common-env` 에서 같은 값을 받으므로 컨테이너 하나의 `printenv MILVUS_RECREATE_ON_MISMATCH` 로 모두를 본다.

## 17. `celery-llm` 에는 GPU 도 모델 캐시도 없다 — 거기서 검색을 돌리면 recreate 마다 모델을 받고 CPU 로 리랭크한다

- **날짜**: 2026-09-23 (round04a)
- **증상**: 딥리서치 첫 잡이 컨테이너 recreate 직후 89초, 같은 파라미터의 두 번째 잡은 34초였다(완료노트 §2 — 원인은 확인하지 않았다). 딥리서치 탐색이 `celery-llm` 에서 도는 동안 BGE-M3·리랭커가 GPU 없이 돈다.
- **원인**: `celery-llm` 은 외부 vLLM 을 HTTP 로 부르는 적재 요약 전용으로 설계된 워커라 GPU 예약도 `/data/models/.hf-cache:/models` 마운트도 없다. 그런데 딥리서치 탐색은 `pipeline.search()` 를 통해 BGE-M3(질의 임베딩)와 Jina 리랭커를 **워커 프로세스 안에서** 올린다. 이미지가 `HF_HOME=/models` 라 마운트가 없으면 `/models` 는 컨테이너 쓰기 계층이다 → recreate 할 때마다 모델을 새로 받는다. 모델은 프로세스마다 한 번 로드(`lru_cache`)되는데 `celery-llm` 은 prefork `--concurrency=4`·`--max-tasks-per-child=200` 이라 자식마다 따로 올리고, 자식이 교체되면 다시 올린다. 리랭커는 `float16` 고정이라 CPU 반정밀도로 올라갔다.
- **해결**: 딥리서치 전용 워커 `celery-research`(GPU 예약·모델 캐시 마운트·`--concurrency=1`·`-Q q_research`)를 compose 에 추가했고, 리랭커는 GPU 가 없으면 `float32` 로 올린다(`reranker._load_model`). 계획은 GPU 가 필요 없어 별도 경량 워커 `celery-research-plan`(`-Q q_research_plan`)이 받는다. 전용 워커로 넘기는 순서는 완료노트 §5 — `RESEARCH_QUEUE` 기본값은 아직 `q_llm` 이다. 넘기기 전(이 구성)에는 슬롯을 쥔 실행이 적재 아이템을 stale 복구로 밀어 16번의 중복 체인을 열 수 있어, API 가 실행을 한 번에 한 잡으로 묶고(429) 운영 딥리서치는 적재를 pause 해 in-flight 0 을 본 뒤에만 돌린다. 시연·리허설도 그 안에서 하고, 워커 기동·recreate 뒤 워밍업 잡을 한 번 돌린다(`bulk_ingest_runbook.md` §8).
- **재발 방지**: 태스크를 기존 큐에 얹기 전에 그 큐 워커의 GPU·볼륨·동시성이 태스크의 전제와 맞는지 compose 에서 확인한다. 긴 태스크를 짧은 태스크의 큐에 얹으면 그 큐를 타임아웃으로 감시하는 쪽(적재 디스패처의 stale 판정)이 오판한다 — 대기가 길어지는 것만의 문제가 아니다. 같은 이미지라도 컨테이너마다 마운트와 장치가 다르다 — "코드가 돈다"와 "제대로 돈다"는 다르다. 모델을 쓰는 워커는 `nvidia-smi` 로 GPU 여유(BGE-M3+리랭커 약 3~4GB)를 먼저 본다.

## 18. FastAPI 재시작은 `library_catalog` 배타 잠금을 요구한다 — 트랜잭션을 연 채 기다리는 세션 하나가 전체 조회를 멈춘다

- **날짜**: 2026-09-23 (round04a)
- **증상**: (이번엔 터지지 않았다 — 머지 전 리뷰에서 코드로 찾은 잠복 함정이다.) 딥리서치 워커가 하위질문을 탐색하는 동안 FastAPI 를 재시작하면, 기동이 lifespan 에서 멈추고 그동안 `library_catalog` 를 읽고 쓰는 요청(검색·서지 조회·적재 쓰기)이 전부 줄 선다.
- **원인**: lifespan 의 `ALTER TABLE library_catalog ADD COLUMN IF NOT EXISTS …`(14번의 두 번째 경로)는 컬럼이 이미 있어도 먼저 ACCESS EXCLUSIVE 잠금을 잡으려 한다. `library_catalog` 를 읽은 트랜잭션이 하나라도 열려 있으면 그게 끝날 때까지 기다리고, PostgreSQL 은 대기 중인 배타 요청 뒤로 새 조회를 줄 세운다. 딥리서치 워커는 `explore()` 가 서지를 조회한 트랜잭션을 연 채 critic LLM 응답(수십 초)을 기다렸다 — SQLAlchemy 세션은 첫 쿼리에서 트랜잭션을 열고 `commit`/`rollback` 전까지 닫지 않는다.
- **해결**: 러너가 `explore()` 직후 `db.commit()` 으로 읽기 트랜잭션을 닫는다(`runner.explore_subquestion`). 워커의 취소 확인(`_current_status`)도 읽고 바로 닫고, 계획 태스크는 LLM 을 부르기 전에 닫는다.
- **재발 방지**: DB 세션을 쥔 채 LLM·외부 HTTP·긴 CPU 연산을 기다리지 않는다 — 기다리기 전에 커밋한다. 의심되면 `select pid, state, xact_start, left(query, 80) from pg_stat_activity where state = 'idle in transaction'` 으로 찾는다. lifespan 의 `ALTER` 블록을 없애는 것은 14번의 스키마 경로 정리와 같은 일이다.

## 19. Celery 소프트 리밋은 asyncio 코루틴 안에서 믿을 수 없다

- **날짜**: 2026-09-23 (round04a)
- **증상**: (라이브에서는 아직 안 터졌다 — 머지 전 리뷰에서 재현했다.) 딥리서치 잡이 30분 소프트 리밋에 걸려도 정리 핸들러가 돌지 않아 잡이 `running`, step 도 `running` 으로 남고, 하드 리밋(35분)에 프로세스째 죽는다. SSE 는 회수기가 올 때까지 ping 만 보낸다.
- **원인** 둘:
  - 소프트 리밋은 시그널 핸들러가 메인 스레드에서 `SoftTimeLimitExceeded` 를 던지는 방식이다. 메인 스레드가 LLM 응답을 await 하느라 이벤트 루프의 `select` 안에 있으면 예외가 코루틴이 아니라 `asyncio.run` 밖으로 튀어나가, 코루틴 안의 `except SoftTimeLimitExceeded` 정리가 돌지 않는다.
  - `SoftTimeLimitExceeded` 는 `Exception` 의 하위다. 동기 리랭크 도중 걸리면 `pipeline.py` 의 리랭크 폴백 `except Exception` 이 삼키고 "리랭킹 실패, 벡터 점수 유지" 경고 한 줄만 남긴 채 계속 돈다.
- **해결**: 잡 본문을 자체 asyncio 데드라인(`JOB_DEADLINE = SOFT_LIMIT - 300`)으로 감쌌다. `asyncio.timeout` 은 await 지점에서 `CancelledError` 로 끊으므로 코루틴 안에서 확실히 잡히고, 초과하면 조건부 UPDATE 로 잡을 `failed`(`시간 상한 초과`)로 두고 열린 step 을 닫는다. `asyncio.run` 밖으로 튄 소프트 리밋은 새 루프·새 엔진으로 같은 정리를 한다(백스톱 — 데드라인이 못 끊는 동기 구간용). 리랭크 폴백은 리랭커가 실제로 내는 실패(`RuntimeError`·`OSError`·`ValueError`·`ImportError`)만 잡는다.
- **재발 방지**: Celery 태스크에서 asyncio 를 돌리면 시간 상한을 Celery 에 맡기지 말고 코루틴 안의 데드라인으로 둔다. 하위 계층의 폴백 `except Exception` 은 태스크 제어 예외까지 삼킨다 — 폴백은 실제로 나는 실패 타입만 잡는다.

## 20. 컨테이너를 개별 Recreate 하면 nginx 게이트웨이가 옛 IP 로 보내 502 가 난다

- **날짜**: 2026-09-28 (round04b)
- **증상**: round04b 운영 배포(`nl-lib-fastapi`·`nl-lib-celery-research`·`nl-lib-celery-research-plan`·`nl-lib-nuxt` 를 컨테이너별로 Recreate) 직후 게이트웨이(포트 92)를 거친 요청이 502 Bad Gateway 를 냈다. nginx 가 요청을 Recreate **전** 컨테이너의 IP(`172.21.0.14`)로 보내고 있었다(사용자 기록). 진단은 nginx 오류 로그(`docker logs nl-lib-gateway`)의 upstream 오류 줄에 찍힌 `upstream:` 주소를 `docker inspect` 로 본 그 컨테이너의 지금 IP 와 견주는 것이다 — 다르면 이 함정이다.
- **원인**: `infra/conf.d/default.conf` 의 `upstream fastapi { server fastapi:8000; }`·`upstream nuxt { server nuxt:3000; }` 처럼 upstream 블록에 쓴 호스트 이름은 nginx 가 **설정을 읽을 때(시작·reload) 한 번만** IP 로 바꿔 쥐고, 그 뒤로는 DNS 를 다시 묻지 않는다. 도커 네트워크(`nl-lib-net`)는 컨테이너를 만들 때마다 빈 IP 를 배정하므로(compose 에 고정 `ipv4_address` 가 없다) Recreate 한 컨테이너는 다른 IP 를 받을 수 있다. 도커 내장 DNS(`127.0.0.11`)는 새 IP 를 알려 주지만 nginx 가 묻지 않는다. 게이트웨이는 Recreate 대상이 아니어서 옛 IP 를 그대로 쥐고 있었다. 함정 16번이 권하는 "바뀐 코드를 쓰는 컨테이너만 Recreate" 가 이 함정을 연다 — 게이트웨이도 함께 다시 시작되면 그때 이름을 새로 풀어서 드러나지 않는다.
- **해결**: `docker exec nl-lib-gateway nginx -s reload`. 설정을 다시 읽으며 이름을 새로 푼다. 컨테이너를 재시작하지 않고 새 워커 프로세스로 넘어가며, 옛 워커는 붙어 있던 연결을 마저 처리하고 내려간다. reload 는 서버의 `/data/nl-lib/nginx/conf.d`(바인드 마운트 — `docker-compose.yml` 의 `gateway`)를 지금 내용 그대로 다시 읽는다. 저장소의 `infra/conf.d/default.conf` 와 다르면 그 차이도 함께 적용되니, 서버 파일을 손댄 적이 있으면 `docker exec nl-lib-gateway nginx -t` 로 먼저 본다.
- **재발 방지**:
  - 게이트웨이가 보내는 곳은 `fastapi`·`nuxt` 둘뿐이다(`infra/conf.d/default.conf`). **둘 중 하나라도 Recreate 했으면 배포의 마지막 단계로 reload 한다.** 워커(`celery-*`)만 Recreate 한 배포에는 필요 없다. round04b §14·round04c 계획의 배포 순서에 넣었고(`docs/superpowers/plans/2026-09-28-round04b-report-wait-export.md`·`2026-09-29-round04c-research-quality.md`·`2026-09-29-round04c-safeguards.md`), round04c 배포(2026-09-30)는 워커 → fastapi → nuxt → `nginx -s reload` 순서로 했다.
  - 배포 뒤 확인은 컨테이너에 직접 붙지 말고 게이트웨이를 거쳐 한다(`curl -s -o /dev/null -w '%{http_code}\n' http://<서버>:92/health` — `/health` 는 fastapi 로, `/` 는 nuxt 로 간다). round04a 의 SSE 확인처럼 컨테이너 안에서 앱에 붙는 확인은 이 함정을 못 잡는다.
  - 게이트웨이 헬스체크(`wget http://127.0.0.1/health` — fastapi upstream 을 탄다)도 같은 이유로 실패하므로, fastapi IP 가 바뀐 채 두면 10초 간격 10회 뒤 `docker ps` 에 `unhealthy` 로 보일 것이다. 도커는 unhealthy 라고 재시작하지 않는다. (compose 설정으로 본 추론이다 — 이번에는 reload 로 바로 고쳐 관찰하지 않았다.)
  - **근본 해결(검토)**: 실행 중에도 이름을 다시 풀게 한다. nginx 1.27.3 부터 오픈소스판도 upstream 의 `server … resolve` 를 쓸 수 있다(upstream 이 공유 메모리 `zone` 에 있어야 한다). 도커 내장 DNS 의 TTL 을 따르지 않게 `valid` 를 짧게 둔다.

    ```nginx
    resolver 127.0.0.11 valid=10s ipv6=off;   # 도커 내장 DNS
    upstream fastapi {
        zone fastapi 64k;
        server fastapi:8000 resolve;
    }
    ```

    적용 전에 확인할 것: 게이트웨이 이미지는 버전 고정이 없는 `nginx:alpine`(`docker-compose.yml`)이라 서버의 실제 버전을 `docker exec nl-lib-gateway nginx -v` 로 본다. 설정은 서버의 `/data/nl-lib/nginx/conf.d` 를 마운트하므로 저장소 파일을 고친 뒤 서버 파일에도 옮겨야 한다. 그 전까지는 reload 를 절차로 지킨다.
- **참고 — 같은 배포에서 SSE 는 게이트웨이 설정을 바꾸지 않고 통과했다.** round04a 는 스트림을 컨테이너 안에서만 확인했었다(`round04a-완료노트.md` §2). 딥리서치 스트림 응답이 `X-Accel-Buffering: no` 헤더(`app/api/research.py`)로 nginx 응답 버퍼링을 끄고, 15초 하트비트(`relay.subscribe` 의 `idle_timeout=15.0` → `: ping`)가 `location /api/` 의 `proxy_read_timeout 120s` 안에서 연결을 이어 준다. 하트비트 간격을 120초보다 길게 늘리면 게이트웨이가 스트림을 끊는다.

## 21. 텍스트 층에 스탬프 한 줄만 남은 스캔본이 VLM 을 건너뛴다 — ODL 본문은 비었는데 fitz 는 그 글자를 센다

- **날짜**: 2026-10-01 (round07)
- **증상**: 2026-10-01 06:43~07:04 UTC 에 섹션 0개로 실패한 아이템 281건이 몰렸다(`not_found` "섹션 없음 — extract 단계부터 재실행 필요"). 전부 「한국문학연구」(1980~2002) 한 블록이었고, 블록이 끝나자 멈췄다 — 고쳐진 게 아니다. 재시도 두 번도 요약 단계에서 같은 실패를 내 1~2분 만에 시도 한도(3)를 다 썼고, 영구 실패로 남았다.
- **원인**:
  - round07 전 쪽 라우팅(`app/services/ingestion/extractor.py` 의 `0 < fitz_check_len < 50` 분기)은 ODL 본문이 짧아도 fitz 도 짧으면 '원래 짧은 쪽'(표지·간지)으로 보고 ODL 결과를 채택했다. 실패한 스캔본은 쪽이 스캔 이미지뿐이라 ODL 본문이 "" 인데(ODL 은 머리말·꼬리말도 json header/footer 로 지운다), fitz 는 텍스트 층에 남은 DBPIA 스탬프 한 줄(`Copyright (C) 2002 Nuri Media Co., Ltd.`, 본문 길이 33자)을 세어 0 이 아니게 되고, 그래서 모든 쪽이 VLM 을 건너뛰었다. 실패 블록 표본 40건이 모두 이 모양이었다(KCI_FI002025246 등 — round07 계획 Task 3 조각 D 근거 ①). 두 추출기가 같은 것을 세지 않는 교차검증이었다.
  - 섹션 0개를 추출 성공으로 넘겼다(`run_extract`). 요약이 "섹션 없음"으로 실패하면 체크포인트가 `extracted` 라 재시도가 추출을 다시 하지 않는다.
- **해결 (round07)**:
  - **문서 단위로만 판정한다.** 각 쪽의 짧음은 ODL 본문 길이와, fitz 텍스트에서 문서 쪽의 60% 이상(`SCAN_REPEAT_LINE_RATIO`)에 되풀이되는 40자 이하 줄(머리말·꼬리말·스탬프 — 숫자는 접어 쪽 번호·연도 차이를 무시한다)을 뺀 길이로 센다 — ODL 이 지우거나 아예 못 보는 줄을 fitz 쪽에서도 지워야 같은 것끼리 비교가 된다. 3쪽 이상(`SCAN_MIN_PAGES`) 문서에서 짧은 쪽이 절반(`SCAN_SHORT_PAGE_RATIO`)을 넘으면 스캔본으로 보고 짧은 쪽을 OCR 로 보낸다(`app/services/ingestion/page_routing.py`). 「한국문학연구」 블록은 스탬프 줄을 빼면 모든 쪽이 0자라 여기서 잡힌다 — 회귀 하네스에서 이 블록 318건이 모두 스캔본으로 잡혔다(OCR 0 → 6,837쪽, `research/round07-ingest-regression/`).
  - **쪽 단위 이미지 규칙은 쓰지 않는다(표지 되돌림 방지).** 쪽 하나만 보면 '스탬프만 남은 스캔 본문 쪽'과 '스탬프만 남은 이미지 표지'를 구분할 수 없다. 쪽 면적 이미지 규칙처럼 쪽마다 OCR 로 보내면 표지·간지를 다시 VLM 으로 보내 d85df93 의 수정(50자 미만 트리거가 VLM 호출의 90% 이상이던 것을 fitz 교차검증으로 고친 것)을 되돌린다.
  - **되풀이 줄을 뺀 길이는 문서 단위 스캔 판정에만 쓴다.** 쪽별 판정(짧은 쪽의 'ODL 이 놓친 본문' = fitz 50자 이상 → OCR, CMap 손상 2배 판정)은 원래 fitz 길이 그대로다 — 뺀 길이로 판정하면 본문이 이미지뿐이고 텍스트 층에 머리말·꼬리말만 남은 쪽을 '원래 짧은 쪽'으로 채택해 본문을 잃는다(Task 3 리뷰, 스마트미디어저널 로컬 278건 중 83건·291쪽). 그래서 스캔본이 아닌 문서는 쪽마다 전과 같다 — 원래 짧은 쪽은 ODL 을 채택하고, fitz 0자 → OCR·표 셀 충전율 판정도 그대로다(회귀 하네스: 비스캔 문서에서 OCR 에서 빠진 쪽도 새로 OCR 된 쪽도 0).
  - **섹션 0개는 추출 성공으로 넘기지 않는다(`run_extract`) — 같은 입력에 같은 결과가 나오는 실패와 다시 하면 달라질 수 있는 실패를 나눈다.**
    - 첫 추출에 VLM 요청 실패(`ocr_errors` — 연결·타임아웃·5xx 와 400·413·422 밖의 4xx 처럼 다시 하면 달라질 수 있거나 서버 전체 설정 문제인 것)나 추출 데드라인(`extract_deadline_hit`, `INGEST_EXTRACT_DEADLINE` 2700초)이 있었으면 강제 재추출 없이 `vlm_error` 다. 디스패처가 체크포인트를 `pending` 으로 되돌려 백오프(`INGEST_RETRY_BACKOFF_SECONDS` 120·600초) 뒤 추출부터 자동 재시도한다.
    - 없고, '원래 짧은 쪽'으로 ODL 결과를 채택한 쪽(`ExtractionResult.short_kept`)도 없으면 바로 `no_text` 다 — 강제 OCR 이 판정을 바꾸는 쪽은 그것뿐이라 다시 추출해도 같다. 결정적 실패라 attempt 를 한도로 올려 자동 재시도하지 않는다.
    - 있으면 짧은 쪽을 모두 OCR 로 보내 한 번 더 추출한다(`meta.forced_ocr`). 시간은 첫 추출이 남긴 만큼이다(`INGEST_EXTRACT_DEADLINE` − 첫 추출 경과, 하한 60초). 두 번째 추출의 ODL 변환도 그 시간 안에서 한다 — 시도마다 ODL 상한(max(10초, 쪽수 × 1.5초))을 남은 시간으로 줄이고 2초도 안 남으면 변환을 띄우지 않고 fitz 텍스트로 간다. 그래서 두 추출을 합쳐도 추출 단계 전체가 stale 판정 3600초 아래다. 그래도 0개면 VLM 요청 실패·데드라인이 있었으면 `vlm_error`, 없었으면 `no_text`.
    - 퇴화 출력(같은 구절 되풀이 — `vlm_truncated` 로 센다), 쪽 이미지 렌더링 실패(`render_errors`), VLM 이 그 쪽 요청을 HTTP 400·413·422 로 거절한 것(`ocr_rejected` — 쪽 이미지가 `max-model-len` 을 넘는 등, 다시 보내지 않는다)은 `ocr_errors` 로 세지 않는다. 다시 해도 대개 같아서, 그것만으로는 `vlm_error` 로 재시도를 헛돌지 않고 `no_text` 로 간다. 거절 때문에 섹션이 0개이거나 본문이 빈 문서는 `last_error` 에 `거절` 과 그 수가 남는다 — 이것들만 VLM·`FITZ_DPI`·`max-model-len` 을 바꾼 뒤 `reset_stage: "pending"` 으로 다시 보낼 만하고(목록 SQL 은 `bulk_ingest_runbook.md` §9-9), 나머지 `no_text` 는 같은 코드로 다시 해도 같다. 401·403·404 같은 그 밖의 4xx 는 서버 전체 설정 문제라 `ocr_errors` 로 세어 `vlm_error` 로 재시도한다.
  - 옛 코드가 요약 단계에서 '섹션 없음'으로 실패시킨 아이템은 자동 재시도 때 체크포인트를 `pending` 으로 되돌려 추출부터 한다. 이미 시도 한도를 다 쓴 아이템은 배포 뒤 `reset_stage: "pending"` 으로 추출부터 다시 돌린다(`bulk_ingest_runbook.md` §9-8).
- **재발 방지**: 서로 다른 추출기로 교차검증할 땐 둘이 같은 것을 세는지(머리말·꼬리말·스탬프를 누가 지우는지, 누가 아예 못 보는지)부터 맞춘다. 표지와 스캔 쪽처럼 쪽 하나로는 가를 수 없는 판정은 문서 단위 신호로 한다. 섹션 0개처럼 같은 입력에 같은 결과가 나오는 실패는 재시도할 그룹과 나눠, 재시도가 같은 일을 되풀이하며 한도를 태우지 않게 한다. 남은 pending 의 2005년 이전 발행분(표본 6.3%)에서 같은 제작 방식의 학술지가 또 나올 수 있다(수백 건 추정 — 회귀 하네스에서도 2004년 이전 200건 중 10건, 2005년 이후 200건 중 3건이 옛 규칙으로 OCR 0쪽인 스캔본이었다). 카나리의 `scan_no_sections` 범주와 `/failures` 의 `no_text` 로 본다.

## 22. 개발 PC 의 opendataloader-pdf 와 운영 버전이 다르면 markdown 글자가 다르다 — 2.5.1 부터 `& < >` 를 HTML 이스케이프한다

- **날짜**: 2026-10-02 (round07)
- **증상**: round07 의 ODL 관찰·판정 근거는 개발 PC 의 2.5.0 으로 냈는데 운영이 적재해 온 버전은 2.5.9 였다(`docker exec nl-lib-celery-cpu pip show opendataloader-pdf`). 같은 문서 45건을 두 버전으로 돌리면 쪽 수·표 충전율·OCR 판정은 같았지만 본문이 같은 문서는 26건뿐이었다 — 차이의 대부분은 2.5.9 의 markdown 이 본문 `<표 1>`·`R&D` 를 `&lt;표 1&gt;`·`R&amp;D` 로 낸 것이다. 그 글자가 섹션·청크·임베딩·요약 입력에 그대로 들어가고, 이스케이프하지 않는 json 의 머리말 문자열과 markdown 줄이 어긋날 수 있다(코드 경로상 — 운영 변환은 `include_header_footer` 를 주지 않아 표본 json 에는 머리말 요소가 없었고, 관찰되지는 않았다).
- **원인**: opendataloader-pdf 2.5.1(#637)이 `MarkdownGenerator.getCorrectMarkdownString` 에서 `&`·`<`·`>` 셋을 바꾸게 했다(2.5.9 jar 의 상수 `&amp;`·`&lt;`·`&gt;`, 2.5.0 에는 없음). json 출력은 바꾸지 않는다. 개발 PC 의 `.venv` 는 2.4.3, round07 관찰은 2.5.0 이라 개발 중에는 드러나지 않았다.
- **해결 (round07)**: `requirements.txt` 를 `opendataloader-pdf==2.5.9` 로 고정하고(fe1be0c), 쪽 구분자로 나눈 뒤 쪽마다 이 셋만 한 번에 되돌린다(`extractor._unescape_odl_markdown` — ODL 이 `&` 를 모두 바꾸므로 정확한 역변환). 되돌리기는 조건 없이 돌아 이스케이프하지 않는 버전이면 원문 `&amp;` 를 잘못 풀므로, 고정값이 바뀌면 테스트(`test_restoring_assumes_the_pinned_odl_version`)가 깨져 이스케이프를 다시 확인하게 했다. 이미 적재된 분은 섞인 채 둔다. 근거: `research/round07-odl-259-recheck/README.md`(45건 비교 두 번, jar 상수, 원본 markdown 의 엔티티 수).
- **재발 방지**: 파서·변환기 같은 외부 엔진은 운영 이미지의 버전(`pip show`)부터 확인하고 그 버전으로 관찰한다. 버전을 올릴 때는 같은 문서 표본을 두 버전으로 돌려 쪽 수·판정만이 아니라 본문 글자까지 비교한다.

## 23. 컨테이너에 메모리 상한이 없으면 JVM 기본 힙은 호스트 메모리의 1/4 다 — 문서 하나가 수십 GB 를 쓸 수 있다

- **날짜**: 2026-10-02 (round07)
- **증상**: ODL(java) 로 변환하던 병리 문서 하나가 몇 초 만에 8GB 를 넘겼고, 개발 PC(42GB)에서는 10.5GB 에서 메모리 부족으로 끝났다. 운영 서버는 RAM 251GB 라 같은 문서가 java 하나로 약 63GB 까지 쓸 수 있고, `celery-cpu` 는 변환을 4칸 동시에 돌린다.
- **원인**: compose 에 `mem_limit` 이 없으면 컨테이너는 호스트 메모리를 그대로 보고, Java 17 은 `-Xmx` 가 없으면 최대 힙을 그 1/4 로 잡는다. opendataloader-pdf 는 `java -jar` 를 `-Xmx` 없이 띄운다.
- **해결 (round07)**: `ODL_JAVA_MAX_HEAP`(기본 `3g`, 1g 이상만) — ODL 자식의 환경에만 `JAVA_TOOL_OPTIONS=-Xmx<값>` 을 붙인다(`extractor._odl_child_env`). 운영 이미지 실측(`research/round07-odl-heap`): 무거운 문서 61건은 2·3g 에서 추출 결과가 상한 없을 때와 같았고, 일반 688건 가운데 3g 로도 넘치는 건 2건(fitz 텍스트로 간다). 형식이 틀리면(`2gb`) java 가 뜨지 않고 너무 작으면(`3m`) 떠도 변환이 모두 실패해 모든 문서가 조용히 fitz 텍스트가 되므로, 설정을 읽을 때 형식과 하한 1g 를 막는다(1g 아래로는 무거운 문서부터 메모리 부족이 는다). compose 의 `${ODL_JAVA_MAX_HEAP:-3g}` 는 빈 스택 env 도 3g 로 채운다 — 상한을 풀려면 `64g` 같은 큰 값을 준다.
- **재발 방지**: 컨테이너 안에서 JVM·대형 모델 같은 메모리를 크게 쓰는 하위 프로세스를 띄우면 상한을 명시한다. 기본값은 "호스트 크기에 비례"라 개발 PC 에서 잰 값이 운영에서는 몇 배가 된다.

## 24. 브로커 메시지를 잃은 approved·queued 딥리서치 잡이 그 브라우저의 승인·재시도를 계속 429 로 막는다

- **날짜**: 2026-10-03 (round06a — 머지 전 리뷰에서 찾았다. 라이브에서는 아직 안 터졌다)
- **증상**: 한 브라우저에서 딥리서치를 승인·다시 시도하면 계속 429 `browser_active`("진행 중인 딥리서치가 있습니다 …")와 [진행 중인 연구 보기] 링크가 나오는데, 링크의 잡은 '대기열'(approved·queued)에서 움직이지 않는다. 사용자에게는 '진행 중' 으로 보여 취소할 까닭을 알기 어렵다.
- **원인**: round06a 의 브라우저당 실행 제한(`app/api/research.py` 의 `_to_run_queue`)은 같은 `created_by` 의 approved·queued·running 잡을 센다. 그런데 회수기(`tasks.reap_stale_research`)는 approved·queued 를 회수하지 않는다 — 아직 워커가 집지 않은 정상 대기 상태라서다. 그래서 브로커 메시지를 잃어 워커가 끝내 집지 못한 잡(Redis 컨테이너가 AOF 없이 죽어 `q_research` 목록이 사라짐, 연구 테이블을 덤프에서 복원 — `infra/backup/pg_backup.sh` 머리 주석)은 approved·queued 로 영원히 남고, 06a 전에는 그 잡 하나만 멈췄지만 이제는 같은 브라우저의 모든 승인·재시도가 막힌다.
- **확인 순서**:
  1. 429 응답의 `job_id`(또는 링크의 잡)가 approved·queued 인지 본다 — `echo "SELECT id, status, created_at FROM research_jobs WHERE id = '<job_id>'" | pgq`(계획 Task 17 Step 5 의 셸 함수).
  2. 실행 큐가 비었는지 본다 — `docker exec nl-lib-redis redis-cli LLEN q_research` 가 0 이고 running 딥리서치 잡이 없다(`SELECT count(*) FROM research_jobs WHERE status = 'running'`).
  3. 대기 순번 줄에 남았는지 본다 — `docker exec nl-lib-redis redis-cli ZSCORE research:run_queue <job_id>`(값이 있으면 줄에는 섰지만 메시지가 없다).
  4. 1~3 이 맞으면 메시지를 잃은 잡이다 — 화면(링크의 잡)에서 취소하면 브라우저 제한이 풀리고, 다시 시작한다.
- **해결**: 지금은 위 순서로 사람이 푼다(코드 수정 없음). 덤프에서 연구 테이블을 복원했다면 복원 직후 approved·queued 를 failed 로 돌린다(`pg_backup.sh` 머리 주석의 UPDATE).
- **재발 방지(후속 과제 — 06a 범위 밖)**: 코드로 막으려면 `created_at` 같은 시간 기준을 쓰지 않는다(정상 대기가 길 수 있다). 회수기 두 틱 연속으로 `q_research` LLEN 0 · running 딥리서치 0 · 대기 ZSET 에 없음이 함께 성립할 때만 failed('브로커 메시지 유실')로 둔다.

## 25. vLLM 은 없어진 요청 필드를 400 없이 받아 버린다 — `guided_json` 제약이 한 달 넘게 걸리지 않았다

- **날짜**: 2026-10-08 (`fix/metadata-filter-response-format`)
- **증상**: 메타데이터 필터 프롬프트(`metadata_filter.yaml`)가 params 에 `guided_json` 스키마를 실어 보냈는데(6d4e8f1, 2026-09-03) 운영 gemma 는 그 제약을 걸지 않았다. 응답은 200 이고 대개 JSON 이라(프롬프트가 JSON 을 시키고 파서가 코드펜스를 걷어 낸다) 드러나지 않았다. 서버 A/B(2026-10-08, `docker exec nl-lib-gemma curl … /v1/chat/completions`): "JSON 쓰지 말고 한국어 한 문장으로 인사해 줘" 에 `guided_json` 을 붙이면 "안녕하세요! …" 평문, 같은 스키마를 `response_format` 으로 붙이면 스키마대로의 JSON 이 나왔다.
- **원인**: vLLM 은 v0.12.0 에서 `guided_*` 요청 필드를 뺐다(`docs/features/structured_outputs.md`). 운영 이미지 `vllm/vllm-openai:latest-cu130`(v0.20.0)의 요청 모델은 `extra="allow"` 라 모르는 필드를 거부하지 않고 "fields were present in the request but ignored" 를 **debug** 로그로만 남긴다(`vllm/entrypoints/openai/engine/protocol.py` 의 `OpenAIBaseModel`). 기본 로그 레벨이 INFO 라 `docker logs` 에도 남지 않는다.
- **해결**: 제약을 OpenAI 표준 `response_format: {type: json_schema, json_schema: {name, schema}}` 로 옮겼다(1747e68 — v0.20.0 은 `to_sampling_params` 에서 이것을 `structured_outputs.json` 으로 바꿔 건다). 스키마는 그대로이고, 테스트가 요청 본문 모양과 프롬프트 YAML 에 `guided_*` 가 남지 않음을 지킨다. 운영 반영은 `nl-lib-fastapi` 이미지를 `:latest` 태그로 다시 빌드·배포한 뒤다(3번 함정 — 프롬프트 YAML 은 바인드 마운트가 아니라 이미지에 들어 있다).
- **재발 방지**: vLLM 전용 확장 필드를 보낼 때는 운영 이미지 버전의 `ChatCompletionRequest` 원문에 그 필드가 있는지부터 본다 — 이름이 틀리거나 빠진 필드는 오류가 아니라 무시다. 적용 여부는 로그가 아니라 제약을 어기게 시키는 A/B 요청으로 확인한다. 제약은 되도록 OpenAI 표준 필드(`response_format`)로 싣는다.

## 26. LLM '다시 쓰기' 가 입력을 옮긴다 — 문단 [다시]가 고칠 문단을 그대로 내거나 앞 문단을 그 자리에 복사했다

- **날짜**: 2026-10-08 (round06b 운영 확인)
- **증상**: 운영 연구 어시스턴트(computing D18 잡 `d8348de8`)의 연구 공백 절에서 문단 [다시]를 눌렀더니, 3번째 문단은 gemma 가 고칠 문단을 글자 그대로 내 아무것도 바뀌지 않았고(생성 13), 2번째 문단은 입력의 '앞 문단: …' 블록을 이름표째 옮겨 1번째 문단의 글이 2번째 자리에 들어갔다(생성 14). 두 생성 모두 done 이었고 옮긴 글에도 유효한 `[E#]` 가 있어 인용 검사를 통과했으므로 화면은 아무것도 알리지 않았다 — [다시]가 듣지 않은 듯 보이거나 같은 글이 두 문단에 보일 뿐이다. 단위 테스트는 가짜 LLM 응답을 쓰므로 라이브 모델에서만 드러난다(15번과 같다).
- **원인**:
  - 프롬프트(`app/domains/nl_library/prompts/research_paragraph.yaml`)는 '고칠 문단이 다루던 내용을 같은 근거로 다시 쓰고 앞뒤 문단과 자연스럽게 잇게' 하라고만 했고 고칠 문단과 달라야 한다는 말이 없었다. 출력 형식에 '앞뒤 문단을 옮겨 쓰지 마세요' 한 줄이 있었지만 사용자 메시지는 앞·고칠·뒤 세 문단을 `앞 문단:`·`고칠 문단:`·`뒤 문단:` 이름표만 붙여 나란히 줘 어느 블록이 참고인지가 흐렸다. temperature 0.3 의 gemma-3-12b 는 가장 쉬운 답 — 입력을 옮겨 적기 — 을 냈다.
  - 파서(`app/services/research_work/paragraph.py` 의 `_parse`)는 한 줄짜리 머리줄만 버리고 첫 문단을 썼다. 이름표와 글이 한 블록에 붙어 오면 머리줄로 걸러지지 않아 '앞 문단: <1번째 문단>' 이 그대로 답이 됐다.
  - 출력을 입력과 견주는 검사가 없었다. 검사는 인용 표기의 유효성만 봐서 입력을 옮긴 글도 통과했다.
- **해결 (82323fd — dev 머지 3aa6d79)**:
  - 프롬프트: 첫머리를 '고칠 문단과 다른 문장으로 새로 씁니다. 앞 문단·뒤 문단은 흐름을 보라고 주는 참고이고, 옮겨 쓸 글이 아닙니다' 로 바꾸고, 규칙 '고칠 문단·앞 문단·뒤 문단의 문장을 그대로 옮기지 마세요'·'… 같은 이름표를 붙이지 마세요' 를 더했다. 앞·뒤 문단 이름표에 `(참고 — 옮겨 쓰지 않습니다)` 를 붙이고(`앞 문단(참고 — 옮겨 쓰지 않습니다):`), 끝에 할 일 한 줄(`위 '고칠 문단'을 다른 문장으로 다시 쓴 문단 하나만 쓰세요.`)을 붙였다. temperature 0.3 → 0.5(절 쓰기는 0.3 그대로).
  - 파서: 입력 이름표(`앞|뒤|고칠 문단(…):`)로 시작하는 문단은 건너뛰고 제 이름표(`다시 쓴 문단:`·`새 문단:`)는 뗀다(`_ECHO_LABEL`·`_OWN_LABEL`). 옮긴 블록이 앞에 여럿 와도 제 문단이 잘리지 않게 문단 수 상한을 두지 않는다(`section.split_paragraphs(limit=None)`).
  - 검사: `[E#]`·`[F#]` 와 공백을 뺀 글이 고칠·앞·뒤 문단 가운데 하나와 `SequenceMatcher` 비율 0.9 이상이면 빈 문단으로 묶어 검사에서 떨어뜨린다(`copied`·`COPY_RATIO`). `run_generation` 이 다시 부르고(두 번 떨어지면 Qwen 으로 넘김, 최대 3회) 끝내 못 얻으면 빈 결과로 닫아 문단은 그대로 둔다.
  - 화면: 그 문단을 쓴 생성보다 나중인 가장 새 다시 쓰기가 failed 이거나 빈 결과(done 인데 model 없음)면 '이 문단을 다시 쓰지 못했습니다 — 앞의 글을 그대로 두었습니다' 를 띄운다(`frontend/utils/proposalView.ts` 의 `failedParagraphGens`, `ProposalSection.vue`). 사용자가 고친·쓴 문단은 알리지 않는다.
  - 배포·확인: 같은 날 워커 셋·fastapi·nuxt 를 새 이미지로 재배포했다(서버 되돌리기 태그 `:pre-r06b-fix1`, 컨테이너 안 프롬프트에서 `옮겨 쓰지 않습니다` grep = 2). 운영에서 다시 눌러 연구 공백 3번째(생성 15)·선행연구 3번째(생성 16) 모두 새 글·이름표 없음·인용 유효를 봤다. 이미 망가진 연구 공백 2번째 문단은 코드가 되돌리지 않는다 — [고치기]로 원래 글을 넣었다(상태 '수정').
- **재발 방지**: '이것을 다시 써라' 류 실행기는 출력을 입력과 견주는 검사를 둔다 — 입력과 같거나 문맥 블록을 옮긴 답은 형식·인용이 맞아도 실패다. 문맥으로 주는 블록은 이름표에 참고임을 적고('참고 — 옮겨 쓰지 않습니다') 할 일을 프롬프트 끝에 한 번 더 쓴다. 파서는 입력 이름표로 시작하는 문단을 답으로 받지 않는다. 가짜 응답 단위 테스트로는 모델이 입력을 베끼는지 알 수 없으므로 새 생성 종류는 배포 뒤 운영 모델로 한 번 눌러 본다.

## 27. vLLM 도구 호출 파서가 모델이 내는 형식과 다르면 조용히 실패한다 — 그리고 `latest-cu130` 태그는 v0.20.0 에 멈췄다

- **날짜**: 2026-10-08 (round06b 13495ee — 운영 compose 를 배포 상태에 맞추며 조사하다 찾았다. 앱이 tools 를 보내지 않아 라이브에서는 아직 안 터졌다)
- **증상**: 사용자가 10-08 운영 스택의 `nl-lib-vllm`(Qwen/Qwen3-VL-30B-A3B-Instruct-FP8, 이름 `qwen3-vl-8b`)에 `--enable-auto-tool-choice --tool-call-parser qwen3_coder` 를 더했다. 서버는 오류 없이 뜨고 tools 없는 요청(OCR·그림 설명·연구 어시스턴트의 Qwen 호출)은 그대로라 이상이 보이지 않는다. 그러나 tools 를 실은 요청에서 모델이 도구를 부르면, 운영 v0.20.0 의 비스트리밍 응답은 `tool_calls` 가 비고 `finish_reason` 이 `stop` 이며 `<tool_call>\n{"name": …, "arguments": …}\n</tool_call>` 원문이 `content` 에 남는다. 스트리밍은 `<tool_call>` 뒤를 삼켜 호출이 content 에도 tool_calls 에도 나오지 않는다. 클라이언트에는 '모델이 도구를 부르지 않았다' 로 보인다.
- **원인**:
  - 도구 호출 파서는 모델이 호출을 **어떤 글로 내는가**에 맞춰 골라야 한다. Qwen3-VL 채팅 템플릿(HF `chat_template.json` — Instruct 와 FP8 이 글자까지 같다)은 `<tool_call>` 안에 `{"name", "arguments"}` JSON 을 내는 Hermes 형식이다. `qwen3_coder`·`qwen3_xml` 은 Qwen3-Coder 계열의 `<tool_call><function=…><parameter=…>` XML 형식용이다. 이름에 같은 'qwen3' 이 들어 있어 맞는 파서처럼 보인다.
  - v0.20.0 의 `Qwen3CoderToolParser`(`vllm/tool_parsers/qwen3coder_tool_parser.py`)는 출력에 `<function=` 이 없으면 `tools_called=False` 로 원문을 content 로 돌려준다. 스트리밍은 `<tool_call>` 을 보고 호출 시작으로 표시한 뒤 `<function=` 이 끝내 오지 않아 남은 조각마다 None 을 낸다. 파서 이름이 등록돼 있고 토크나이저에 `<tool_call>` 토큰이 있어 기동 검사도 통과한다 — 25번처럼 잘못된 설정이 오류가 아니라 무시로 나타난다.
  - 이미지를 올려도 풀리지 않는다. v0.24 부터(latest·v0.31.0 포함) 두 이름은 같은 엔진 파서(`vllm/parser/qwen3.py`)를 가리키는데 역시 XML 만 읽어 JSON 본문을 버린다(tool_calls 빈 채 `stop`).
  - **이미지 태그도 멈춰 있다.** `vllm`·`gemma` 두 서비스가 쓰는 `vllm/vllm-openai:latest-cu130` 은 Docker Hub 에서 2026-04-28 에 갱신이 멈췄다(digest `sha256:04563c30…` = `v0.20.0`·`v0.20.0-cu130`). 기본 태그(`latest`·`vX`)가 CUDA 13 빌드로 바뀌면서 `-cu130` 접미 태그를 더 올리지 않는다. 그래서 다시 받아도(Pull & Redeploy) v0.20.0 에 머물고(그 전에 받았으면 더 옛 버전일 수 있다), 더 새것은 `latest`·`v0.31.0` 이다. 25번(`guided_json` 무시)도 같은 멈춘 이미지 위에서 일어났다 — vLLM 동작을 원문으로 확인할 때는 최신 소스가 아니라 운영 버전의 소스를 본다.
- **해결**:
  - 저장소 `docker-compose.yml` 의 vllm 서비스는 `--tool-call-parser hermes` 로 적었다(13495ee, command 주석에 까닭). 운영 스택은 사용자가 Portainer 에서 `qwen3_coder` → `hermes` 로 바꾼다(2026-10-08 대기). `--enable-auto-tool-choice` 는 그대로 두고 `--reasoning-parser` 는 붙이지 않는다(Instruct 모델). `--enable-auto-tool-choice` 만 두고 `--tool-call-parser` 를 빼면 기동이 실패한다. 도구 호출을 당장 쓰지 않으면 두 플래그를 모두 빼도 된다.
  - 바꾸는 동안 지금 앱 호출은 영향이 없다 — `app/` 에 `tools`·`tool_choice` 를 싣는 곳이 없고(grep), tools 가 없으면 `tool_choice` 기본값이 `none` 이라 v0.20.0 의 비스트리밍 응답은 파서를 거치지 않고 content 를 그대로 낸다. 스트리밍(절 쓰기가 Qwen 으로 넘어갈 때)은 tools 가 없어도 조각마다 도구 파서를 거치지만(`vllm/parser/abstract_parser.py` 의 `parse_delta`) 평문은 그대로 지나간다 — 출력에 `<tool_call>` 이 나오면 그 뒤를 삼키고, hermes 는 `<tool_call>` 의 앞부분처럼 보이는 끝 글자(`<`·`<tool_` 등)를 다음 조각까지 잡아 두어 글이 그런 글자로 끝날 때만 그 몇 글자가 빠진다. 다만 vllm 컨테이너를 다시 만드는 동안은 OCR(`celery-cpu`)·그림 설명·연구 어시스턴트의 Qwen 호출이 멈추거나 넘김 경로로 간다.
  - 확인 — 같은 요청을 파서를 바꾸기 전·후에 보낸다(서버 셸. 이미지에 curl 이 있다 — healthcheck 가 쓴다. 호스트에서는 `http://localhost:18081`):

    ```sh
    docker exec nl-lib-vllm curl -s http://127.0.0.1:8000/version          # 운영 vLLM 버전
    docker inspect nl-lib-vllm --format '{{json .Config.Cmd}}'              # 실제 --tool-call-parser 값
    docker exec nl-lib-vllm curl -s http://127.0.0.1:8000/v1/chat/completions \
      -H 'Content-Type: application/json' -d '{
      "model": "qwen3-vl-8b",
      "messages": [{"role": "user", "content": "What is the weather in Seoul right now? Use the get_weather tool."}],
      "tools": [{"type": "function", "function": {
        "name": "get_weather", "description": "Get the current weather for a city",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}],
      "tool_choice": "auto", "temperature": 0, "max_tokens": 200
    }'
    ```

    맞는 파서(`hermes`)면 `"finish_reason":"tool_calls"`·`tool_calls[0].function.name` 이 `get_weather`·arguments `{"city": "Seoul"}`·content null(호출 앞에 글이 있으면 그 글)이다. `qwen3_coder`·`qwen3_xml` 이면 `"tool_calls":[]`·`"finish_reason":"stop"` 이고 content 에 `<tool_call>…</tool_call>` 원문이 남는다. 기동 로그(`docker logs nl-lib-vllm 2>&1 | grep -i 'tool choice has been enabled'`)는 플래그가 켜졌다는 것만 알려 주고 파서가 맞는지는 알려 주지 않는다.
- **재발 방지**:
  - 도구 호출 파서는 모델 이름이 아니라 그 모델의 채팅 템플릿이 도구 호출을 쓰는 글을 보고 고른다 — `<tool_call>` 안이 JSON 이면 `hermes`, `<function=…>` XML 이면 `qwen3_coder`·`qwen3_xml`. 같은 Qwen3 이라도 VL·Instruct 와 Coder 의 형식이 다르다.
  - 서빙 플래그를 바꾸면 서버가 뜨는 것만 보지 말고 그 기능을 쓰는 요청 하나(위 curl)로 결과 필드를 본다.
  - 앱이 tools 를 보내기 시작하는 변경 전에 이 확인을 다시 한다. 도구를 부르면 `content` 가 null 이 되므로 `["content"].strip()` 처럼 읽는 곳(`app/services/ingestion/paper_enricher.py` 의 `describe_figure`)을 함께 고친다(`llm_client` 는 `or ""` 로 받는다).
  - vLLM 버전은 태그 이름이 아니라 `/version` 으로 본다. 버전을 올릴 때는 `latest-cu130` 같은 떠다니는 태그 대신 `vX.Y.Z` 로 고정하고, 올리기 전에 25번·이 항목처럼 요청 필드·파서 동작이 바뀌었는지 그 버전의 소스로 확인한다.
