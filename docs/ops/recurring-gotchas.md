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
- **현재 서버**: `alembic_version = 0005_research_jobs`(2026-09-23 확인) — round04a 의 `0004`·`0005` 스탬프까지 맞춰졌다.


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
- **해결**: 인덱싱이 도는 동안에는 스택 업데이트(Pull & Redeploy 포함)를 하지 않는다. 앱 코드 배포는 인덱싱이 끝난 뒤, 또는 적재를 pause 해 in-flight 를 비운 뒤(아래) 한 번에 한다. 딥리서치 큐 전환처럼 일부 서비스만 바뀌는 설정은 `x-common-env` 가 아니라 해당 서비스 env 에 둔다(`RESEARCH_QUEUE`·`RESEARCH_PLAN_QUEUE` 가 fastapi·딥리서치 워커에만 있는 이유). 인덱싱 중에 꼭 먼저 내보내야 하면 **바뀐 코드를 쓰는 컨테이너만** recreate 하되, 새 compose 를 다시 읽지 않는 방식으로 한다 — 서버에서 `docker pull` 로 이미지를 받아 두고(12번, pull 만으로는 아무것도 재시작되지 않는다) Portainer 에서 해당 컨테이너만 Recreate 한다. 컨테이너 Recreate 는 기존 컨테이너 설정(env 포함)을 그대로 쓴다. 새 compose 로 `docker compose up -d fastapi celery-llm` 을 하면 fastapi 만 `RESEARCH_QUEUE: q_research` 를 받아 딥리서치 잡이 소비자 없는 큐에 쌓인다. 어느 쪽이든 `celery-llm` recreate 는 그 순간의 적재 요약·마무리 태스크(최대 4개)를 끊는다. **끊지 않으려면 적재 잡을 pause 하고 in-flight(`dispatched`·`running`)가 0 이 된 뒤 재생성한다**(`bulk_ingest_runbook.md` §8) — 끊기는 태스크가 없으면 아래 복구 경로도 돌지 않는다.
- **끊긴 적재 아이템은 어떻게 되나 (코드 근거)**: 볼륨의 데이터는 컨테이너 재생성으로 지워지지 않는다 — Postgres·Milvus·MinIO 는 외부 볼륨(`external: true`)이고, 끝난 단계의 결과는 이미 커밋돼 있다. 문제는 끊긴 아이템이다. 복구 경로가 **둘 다** 돈다 — 한쪽이 다른 쪽을 막지 않는다.
  - ① stale 복구: 디스패처(beat 30초)가 단계 타임아웃(요약·임베딩 1200초·마무리 900초, 아직 안 집힌 디스패치는 14400초)을 넘긴 아이템을 `failed`(`error_group=stale`)·`attempt+1` 로 표시하고, `attempt < max_attempts`(기본 3)면 **마지막 체크포인트(`item.stage`)부터** 새 체인을 디스패치한다. 옛 태스크를 revoke 하지는 않는다(`job_runtime._recover_stale`·`_dispatch_for_job`).
  - ② 브로커 재전달: `task_acks_late=True` 라 끊긴 태스크의 메시지는 ack 되지 않은 채 Redis 에 남는다. 도커는 SIGTERM 10초 뒤 SIGKILL 해 워커가 메시지를 되돌리지 못하고, 메시지는 전달 시각 기준 `visibility_timeout`(7200초) 뒤 재전달된다 — 체인의 뒤 단계(`embed_index`·`finalize`)까지 달고.
  - 그래서 ①이 약 20분 뒤 새 체인으로 아이템을 끝내고(마무리 단계가 추출 아티팩트를 지운다), 약 2시간 뒤 ②의 옛 체인이 **같은 아이템을 다시 돌린다.** 단계 래퍼(`_run_stage`)는 `canceled` 만 건너뛰고 `done`·체크포인트는 보지 않는다. 재전달된 요약은 이미 요약된 섹션을 건너뛰어(기본 `resume_summaries`) 그냥 통과하고, 이어진 `embed_index` 는 아티팩트가 없어 본문이 빈다.
    - **논문**: 초록(없으면 메타 필드)으로 대체해 `index_chunks` 가 그 논문의 청크를 delete 후 insert 한다 — **PDF 본문 청크가 초록 청크로 덮인다.** 이미 적재된 데이터가 실제로 손상되는 경로다.
    - **도서**: `empty_body` 가드가 인덱스를 건드리기 전에 멈춰 벡터는 멀쩡하지만, 아이템이 `failed`·`attempt+1` 이 되고 `library_catalog.ingest_state` 에 거짓 `failed` 가 찍힌다.
  - 영향 범위는 재생성 순간 요약·임베딩 중이던 아이템이다(`celery-llm` 은 최대 4건, `celery-embed` 는 1건). 추출 중에 끊긴 아이템은 옛 체인이 추출부터 다시 해 아티팩트를 새로 만들므로 덮이지 않는다(비용만 든다).
  - **의심 아이템 찾기**: stale 복구를 거친 아이템은 `done` 이 된 뒤에도 `last_error` 에 `stale 복구` 문구가 남는다 — `SELECT id, book_id, status, stage FROM ingest_job_items WHERE job_id = '<job_id>' AND last_error LIKE '%stale 복구%'`. 되돌리는 법은 그 아이템을 추출부터 다시 돌리는 것이다(`POST /api/admin/ingest-jobs/{job_id}/retry` `{"item_ids": [...], "reset_stage": "pending"}` — 원본 PDF 로 다시 적재). 인덱싱이 끝난 뒤 한 건으로 먼저 확인한다.
  - 근본 원인(단계 래퍼가 `done` 을 보지 않음, stale 복구가 옛 태스크를 revoke 하지 않음)은 적재 코드에 있다. 인덱싱 잡이 도는 동안에는 적재 코드를 고치지 않으므로, 인덱싱이 끝난 뒤의 과제로 남긴다.
  - 이미 두 번 실패한 아이템은 한도에 닿아 자동 재시도에서 빠지고, `POST /api/admin/ingest-jobs/{job_id}/retry` `{"error_group": "stale"}` 로 되살린다(attempt 를 0 으로 리셋).
- **컨테이너를 끊지 않아도 같은 경로가 열린다 — 과도기 구성의 딥리서치.** 전용 워커로 넘기기 전(`RESEARCH_QUEUE` 기본값 `q_llm`)에는 딥리서치 실행이 `celery-llm` 슬롯을 잡마다 최대 25분 쥔다. 여럿이 슬롯을 쥐면 요약·마무리를 기다리는 적재 아이템이 단계 타임아웃을 넘긴다 — 타임아웃은 `updated_at` 부터 재고 큐 대기 중에는 갱신되지 않으며, 마무리를 기다리는 아이템은 900초라 더 빨리 걸린다. 그러면 ①과 같은 stale 복구가 새 체인을 띄우고, 큐에 남은 옛 메시지도 그대로 돈다(`_run_stage` 는 `canceled` 만 건너뛴다). 끝나는 순서에 따라 한쪽 `finalize` 가 아티팩트를 지운 뒤 다른 쪽 `embed_index` 가 돌면 위의 논문 덮어쓰기가 난다. 머지 전 리뷰에서 이산 사건 모델로 재현했다(잡 여러 건을 몰아서 승인하거나 긴 잡이 겹칠 때). 그래서 API 가 이 구성에서는 실행을 한 번에 한 잡으로 묶는다(approve·retry 429, `api/research.py` `_to_run_queue`) — 같은 모델에서 한 번에 한 잡이면 25분짜리를 연달아 돌려도 stale 은 0 이었다. 그래도 가정값 위의 결과라, **적재 잡이 `running` 인 동안에는 운영 딥리서치를 돌리지 않는다 — pause 하고 in-flight 0 을 본 뒤 돌린다**(`bulk_ingest_runbook.md` §8). pause 만으로는 모자라다 — `resume` 뒤 첫 틱이 그동안 타임아웃을 넘긴 아이템을 복구한다.
- **재발 방지**: 배포 전에 "지금 도는 적재 잡이 있는가"와 "이 배포가 어느 컨테이너를 재생성하는가"를 먼저 본다. 적재 워커를 재생성해야 하면 pause → in-flight 0 확인 → 재생성 → resume 순서로 한다(`bulk_ingest_runbook.md` §8). fastapi 를 재시작하면 lifespan 의 `ALTER TABLE library_catalog` 가 배타 잠금을 기다리는 동안 그 뒤 조회·쓰기가 줄 선다(18번). `MILVUS_RECREATE_ON_MISMATCH` 는 반드시 `false` 인지 확인한다 — fastapi 기동의 `ensure_collection` 이 스키마 불일치 때 컬렉션을 지우는 유일한 경로다.

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
