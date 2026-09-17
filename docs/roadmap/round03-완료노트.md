# round03 완료노트

날짜: 2026-09-17 (사고 2026-09-14, 복구·구현 2026-09-15~17)
브랜치: `fix/round03-doc-type-reindex`
spec: `docs/superpowers/specs/2026-09-15-round03-doc-type-reindex-design.md`
plan: `docs/superpowers/plans/2026-09-15-round03-doc-type-reindex.md`
교본: 미작성 — 라운드 완료 시 `docs/guides/round03/`

> **이 라운드는 아직 진행 중이다.** round03 본 스코프(문학 41편 Milvus `doc_type` 재기록)는
> Task 1~5 가 끝났고 Task 6(운영 실행)·7(교본)이 남아있다. 그럼에도 지금 완료노트를 쓰는 이유는,
> 이 라운드가 **선행 사고(`library_catalog` 전멸) 복구와 뒤엉켜 진행됐고 그 복구 지식이
> 휘발성이기 때문**이다. 복구 경로·실패한 시도·함정을 지금 적지 않으면 재현 불가능해진다.
> 라운드 종료 시 §상태 체크박스를 채우고 교본을 붙인다.

---

## 1. 선행 사고 — `library_catalog` 전멸 (2026-09-14)

### 무슨 일이 있었나
`library_catalog` 이 통째로 비워져 **고아 문서 72,601건**이 발생했다. 다른 저장소는 전부 무사했다.

| 저장소 | 상태 |
|---|---|
| `library_catalog` | **246행만 남음** (사고 후 새로 들어온 것들) |
| `book_sections` | 1,121,526행 무사 (summary 1,120,153 · themes 1,117,061) |
| Milvus | 3,884,183 청크 무사 |
| MinIO `originals/` | 238,369 객체 무사 |

살아남은 246행의 `created_at` 이 전부 **2026-09-14 08:57:56 ~ 09:07:09 (UTC)** 10분 구간에 몰려 있다 — 그 직전에 비워졌다는 뜻이다.

### 증상이 그렇게 보인 이유
- 검색 카드에 제목 대신 `CNTS-00049204004` 같은 ID → `app/api/book.py:88` 이 `repo.get_by_cnts_id()` 로 `book_info` 를 채우는데 행이 없어 `None`, 프론트가 ID 로 폴백
- 제목 일치율 게이지 0 → `apply_title_scores` 가 제목 없이 계산
- `POST /api/books/curate` 404 → `get_by_cnts_ids` 빈 결과 → `HTTPException(404, "도서를 찾을 수 없습니다")`
- 논문·도서가 함께 깨짐 → 둘 다 같은 `library_catalog` 를 쓴다(`doc_type='paper'` 로만 구분)
- **표지는 계속 보였다** → 썸네일이 ① DB 커버키 → ② MinIO 캐시 → ③ 원본 PDF 1페이지 즉석 렌더로 폴백해(`app/api/book.py:368`), DB 없이 ③ 으로 그려지고 있었다. 이 폴백 때문에 "일부만 깨졌다"고 오판하기 쉽다.

### 원인 — 미확정
**확정된 것:**
- `library_catalog` 을 지울 수 있는 코드는 둘뿐 — `DELETE /api/admin/books`(파라미터 없으면 전체, 확인 절차 없음, `app/api/admin.py:321`)와 `DELETE /api/admin/books/all?confirm=yes`(`TRUNCATE ... CASCADE`, `:350`)
- **API 경유 삭제는 배제됨.** `nl-lib-fastapi` 가 2026-09-03 부터 재시작 없이 떠 있어 로그가 사고 시점을 덮었고, `DELETE /api/admin` 전수 검색에 전체 삭제 요청이 없었다(특정 ID 2건 삭제 1회만 존재). uvicorn 은 `:18002` 직결 요청도 기록하므로 게이트웨이 우회도 배제된다.
- 카탈로그 적재 코드는 전부 `INSERT ... ON CONFLICT`(`repositories/catalog_bulk.py`) — 비파괴
- 테스트·스크립트·alembic·startup(`Base.metadata.create_all`) 어디에도 삭제 없음
- `landsoft` bash_history 에 `nl_lib` 대상 파괴적 SQL 없음
- `book_sections` 가 살아남은 것은 `book_id` 가 FK 가 아니라 평범한 `String` 이기 때문(`models/section.py:21`) — `TRUNCATE ... CASCADE` 여도 전파되지 않는다

**결론:** Postgres 에 **직접 SQL** 을 날린 것으로 추정된다. `log_statement=none` 이라 증거가 남지 않았고, 포렌식용 FastAPI 로그도 이후 재배포로 컨테이너가 재생성되며 소실됐다. **누가·언제·무엇을 실행했는지는 확정 불가.** 추정을 사실로 적지 않는다.

정황상 가장 그럴듯한 시나리오는 round02a 문학 적재 준비 중 "깨끗하게 하고 시작하자"며 카탈로그를 비운 것이다 — 시각이 문학 211건 적재 직전과 정확히 겹친다. 서버를 공동 사용하므로 작업자 특정도 어렵다.

### 복구 실적 (순서대로, 재현 가능하게)

| # | 대상 | 방법 | 결과 |
|---|---|---|---|
| 1 | 논문 카탈로그 | `metadata.xlsx`(KCI, 260,388건 파싱) 재적재 | 신규 236,478 / 갱신 3,837 |
| 2 | 도서 카탈로그 | `marc_mods*.xlsx` 5개 재적재 | 703건 |
| 3 | 한국 근대문학 41편 | Milvus 메타청크(`chunk_idx=-1`) 역복원 | 41건 |
| 4 | `cover_image_key` | `covers/{cnts_id}.jpg` 결정론적 키 규칙 | 588건 (무손실) |
| 5 | `is_embedded`·`ingest_state`·`full_text_length` | `book_sections` 존재 여부로 SQL 갱신 | 72,841건 |
| 6 | `doc_type` (NL 도서 누락분) | KDC 기반 `detect_doc_type` 규칙 SQL 적용 | 658건 |
| 7 | 논문 `abstract`·`extracted_keywords` | Milvus `[초록]`·`[키워드]` 보강청크 역복원 | 42,850건 (LLM 비용 0) |
| 8 | `plot`·`read_effect` | 기존 백필 엔드포인트 | 910건 |
| 9 | `summary`·`themes`·`introduction` | 신규 백필(섹션 요약 재사용) | 910건 |

고아 문서 **72,601 → 0건**. 복구 스크립트는 `scripts/recovery/` 에 있다.

### 복구가 가능했던 이유 — 운이었다
원본 카탈로그 파일이 `/data/nl-lib/data/uploads/` 에 남아있었고, 초록이 Milvus 청크에 남아있었기 때문이다. **설계된 안전장치가 아니었다.** `docker-compose.yml` 에 백업 서비스가 없어 `pg_dump` 가 한 번도 돈 적이 없었다.

---

## 2. 한 일

### 2-1. 사고 복구 (§1-4 참고)
위 9단계. 스크립트 4종을 `scripts/recovery/` 에 남겼다 — `restore_from_milvus_meta.py`(메타청크 역복원), `restore_cover_keys.py`(커버 재매핑), `restore_abstract_from_chunks.py`(초록·키워드 역복원), `load_kci_csv.py`(KCI CSV 우회 로더).

### 2-2. 보안·운영 보강
- **`/api/admin`·`/docs`·`/openapi.json` 게이트웨이 차단** (`infra/conf.d/default.conf`, `conf.d.dev` 동일). 외부에서 403 확인. `location ^~ /api/admin` 은 접두 최장일치로 `location /api/` 를 이긴다.
- **Postgres 정기 백업 신설** (`infra/backup/pg_backup.sh` + 호스트 cron). daily 는 `library_catalog` 만(77MB 압축), weekly 는 전체 DB. **복원 연습까지 완료** — 임시 DB 에 `pg_restore` 해 241,243행 / abstract 42,957 / summary 945 확인.
- **읽기 전용 DB 역할 `nl_readonly` 생성** — 조회만 하는 사람이 `admin` 을 쓰면 `TRUNCATE` 권한까지 갖게 된다.
- **`log_statement='ddl'` + `log_connections=on`** — 다음에 같은 일이 나면 `TRUNCATE`·`DROP` 과 접속 기록이 남는다. `mod` 는 검색마다 `search_history` INSERT 가 찍혀 과하다고 판단.

### 2-3. round03 본 스코프 (Task 1~5 완료)
- **Task 1** `detect_doc_type` — `source_format="PDF"`(카탈로그 없이 적재돼 PDF 에서 자동추출한 메타)의 `genre` 를 `paper` 판정 근거로 쓰지 않는다. 테스트 11개.
- **Task 2** `run_embed_index` 빈 본문 가드 — 아티팩트도 폴백 텍스트도 없으면 `StageError("empty_body")` 로 중단. 테스트 3개.
- **Task 3** Milvus `doc_type` 재기록 도구의 순수 변환 함수 + 테스트 10개.
- **Task 4** Milvus `doc_type` 재기록 I/O — 문서 단위 백업·검증·`--restore`. `delete`+`insert` 가 아니라 **`upsert` 로 제자리 교체**해 청크가 0개가 되는 구간이 없다(실패해도 기존 청크가 남는다). 백업 완전성 검증은 `fetch_chunks` 직후 다시 센 값과 대조한다. `--limit` 으로 첫 운영 실행을 1건으로 제한.
- **Task 5** 런북에 `params.doc_type` 명시 절차 추가 + 관리 API 를 컨테이너 경유 호출로 정정(게이트웨이 차단으로 기존 안내가 403 이 됐다).
- **Task 6~7 미완** — 운영 실행(dry-run → `--limit 1` → 나머지 → 라이브 검증), 교본.

---

## 3. 결정

- **`doc_type` 오분류를 후처리 필터가 아니라 Milvus 재기록으로 고친다.** 후처리(검색 후 `book_info.doc_type` 으로 거르기)는 위험이 낮지만 증상의 절반만 덮는다 — 도서 필터가 `doc_type != "paper"` 라 41편은 **애초에 검색되지 않으므로** 후처리로 되살릴 수 없다.
- **재발방지는 2층.** 원천은 크롤링 적재 잡에 `params.doc_type` 명시(메커니즘은 이미 있었고 안 쓴 것), 안전망은 PDF 자동추출 `genre` 불신. 원천만으론 절차 의존이고, 안전망만으론 학위논문 PDF 가 `book` 으로 잡히는 대가를 계속 진다.
- **`paper` 오판정이 `book` 오판정보다 치명적이다.** 논문 필터에는 `book_id like "KCI_FI%"` ID 폴백이 있어 회복되지만 도서 필터에는 없다. 이 비대칭이 Task 1 설계의 근거다.
- **빈 본문 가드의 `error_group` 을 `artifact_missing` 재사용이 아닌 `empty_body` 로 분리.** 판정에 `strip()` 이 필요해 **아티팩트가 정상 로드된 문서도 걸리기 때문** — `artifact_missing` 으로 집계하면 실패 대시보드가 거짓을 말하고 그 그룹의 표준 복구 절차("extract 부터 재실행")도 맞지 않는다.
- **재기록 도구가 스칼라 컬럼 순서를 하드코딩하지 않는다.** 앱의 `_scalar_field_specs()` 에서 파생시키고, 드리프트를 테스트가 잡게 했다(`profile.py` 순서를 바꾸면 테스트가 실패함을 실증 확인). 순서가 어긋나면 임베딩이 텍스트 컬럼에 들어가는 식의 조용한 파괴가 난다.
- **백업은 compose 서비스가 아니라 호스트 cron.** compose 에 넣으면 스택 재배포가 필요해 사고 직후에 붙이기 어렵고, 백업은 앱 배포 주기와 분리돼 있는 편이 낫다.
- **백업을 두 단계로 나눈다.** 실측 DB 4.8GB 중 `book_sections` 가 4.1GB, `library_catalog` 은 381MB. 매일 5GB 를 덤프하는 건 낭비이고, 실제로 날아간 건 카탈로그다.
- **공유 서버에서 포트 바인딩(`127.0.0.1:15432`)은 효과가 제한적이다.** 서버에 들어올 수 있는 사람은 그대로 붙을 수 있고 `docker` 그룹은 사실상 root 다. 그래서 순서를 **백업 → 계정 분리 → 로깅** 으로 잡았다.

---

## 4. 라이브에서만 드러난 함정

`docs/ops/recurring-gotchas.md` 에도 반영한다.

- **KCI 로더는 xlsx 전용이다.** `domains/nl_library/loaders/kci_xlsx.py:44` 가 `load_workbook()` 직결이라 `.csv` 를 넣으면 `InvalidFileException` 으로 죽는다. NL MARC/MODS 로더는 `_read_rows()` 로 CSV 를 지원하는데 KCI 만 다르다.
- **KCI 카탈로그(`metadata.xlsx`)에는 초록 컬럼이 없다.** 컬럼은 `KCI_FI_ID · ARTI_ID · GRADE · TITLE_KR · TITLE_EN · AUTHORS · INSTITUTION · JOURNAL · VOL_ISSUE · PAGES · YEAR_MONTH · KCI_CITATIONS · WOS_CITATIONS` 뿐. 논문 `abstract` 는 적재 시 PDF enrichment 결과이며 **Milvus `[초록]` 청크가 유일한 복원 소스**다.
- **메타청크의 구분자 ` | ` 가 값 안에도 들어간다.** 실측: `저자: 柳在元 | 林慧俊`, `주제: 인연 | 덫 | 사랑`. 단순 `split(" | ")` 은 값을 깨뜨린다 — 알려진 라벨 집합 경계로만 잘라야 한다.
- **도서 초록은 메타청크에서 복원할 게 없었다.** MODS `abstract` 가 카탈로그에 있어 `marc_mods*.xlsx` 재적재로 이미 복구됐고, 남은 도서는 애초에 초록이 없던 문서라 메타청크에도 없다(메타청크는 적재 당시 `book.abstract` 로 만든다).
- **`NOT IN (서브쿼리)` 가 카탈로그 복구 후 급격히 느려진다.** 246행일 때는 즉시 끝나던 고아 조회가 24만 행이 되자 5분 넘게 멈췄다. `NOT EXISTS` 안티조인으로 바꾸면 인덱스를 탄다.
- **SQLAlchemy `text()` 는 바인드 파라미터 뒤의 `::` 캐스트를 못 넘긴다.** `:e::jsonb` 가 바인딩되지 않고 SQL 에 그대로 흘러가 `syntax error at or near ":"` 가 난다. `CAST(:e AS jsonb)` 를 쓴다.
- **스크립트를 파일 경로로 실행하면 `PYTHONPATH=/app` 이 필요하다.** `sys.path[0]` 이 스크립트 디렉터리로 잡혀 앱 모듈을 못 찾는다. `python -c` 나 `python -` (stdin) 은 cwd(`/app`)가 들어와 필요 없다.
- **`scripts/build_dev_images.sh` 는 `:dev` 태그를 빌드·푸시한다.** 운영 스택(`docker-compose.yml`)은 `:latest` 를 쓴다. 운영에 반영하려면 `NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest` 로 override 해야 한다.
- **`/data/nl-lib/data/` 는 root 소유다.** 일반 계정으로 리다이렉트 쓰기가 막힌다. `docker cp` 로 컨테이너에 직접 넣거나 root 로 쓴다.
- **백필 엔드포인트의 `candidates` 집계가 태스크의 `doc_type` 필터를 빠뜨려 실제(699)와 100배 어긋난 값(72,630)을 보고했다.** 이번에 수정.

---

## 5. 디자인 참조
해당 없음 — 디자인 트랙 미도입(`docs/design/README.md`)

---

## 6. 이월

- **round03 Task 6~7** — 운영 실행(dry-run → `--limit 1` 로 1편 확인 → 나머지 40편 → 라이브 검증), 교본. **문학 41편은 지금도 Milvus 에서 `paper` 라 도서 검색에서 실종 상태다**(Postgres 는 `literature` 로 교정 완료).
- **`restore()` 의 `book_id` 를 파일명에서 얻는다** — `path.stem` 기반이라, 경고를 무시하고 `.incomplete` 파일을 직접 `--restore` 인자로 넘기면 `book_id` 가 어긋나 허위 `[FAIL]` 이 난다. 데이터 위험은 없다(그 문서는 애초에 upsert 된 적이 없어 no-op). `records[0]["book_id"]` 에서 읽으면 이 오용이 원천 차단된다.
- **논문 `summary` 29,006건** — `[초록]` 청크가 없어 복원 소스가 없다. LLM 재생성만 가능하며 7.8초/건 기준 단일 63시간 / 4병렬 16시간. 초록 42,850건이 채워져 화면은 정상이라 급하지 않다.
- **미배포 코드** — `backfill_summary` 태스크·엔드포인트와 백필 집계 수정이 커밋은 됐으나 운영 `:latest` 이미지에 없다. 다음 배포 때 태그 맞춰 빌드해야 한다.
- **`_BACKFILL_DOC_TYPES` 중복** — `app/api/admin.py:71` 과 `app/workers/tasks.py` 의 `_GENERATE_DOC_TYPES` 가 값으로 중복돼 드리프트 여지가 있다. Task 3 에서 없앤 `SCALAR_ORDER` 하드코딩과 같은 종류.
- **`_scalar_field_specs` private 이름 참조** — `scripts/recovery/rewrite_milvus_doc_type.py` 가 모듈 경계 밖에서 언더스코어 함수를 쓴다. 공개 이름 승격이 더 명시적이나 이번 스코프 밖.
- **`CNTS-00052063319` OCR 품질** — 삭제한 중복본(`…319_`)의 제목이 `宋純의詩歌文學研究` 로 정확한 반면, 남긴 정본은 `宋純純の詩歌文學研究` 로 깨져 있다. 남는 쪽이 품질이 낮은 추출본이다.
- **`build_manifest.py` ID 정규화 누수** — `normalize_book_id`(`scripts/bulk_ingest/build_manifest.py:41`)가 끝 `_` 를 제거하는데, 삭제한 `CNTS-*_` 3건은 이 정규화를 거치지 않은 경로로 들어왔다. 어느 경로인지 미확인.
- **청크 0건 논문 2건** — `KCI_FI003333197`·`KCI_FI003335027`. 본문에서 읽은 서지정보로 카탈로그 행은 수기 등록 가능하나 임베딩이 없어 검색에 안 잡힌다. 원본 PDF 재적재 필요.
- **[보안, 우선순위 높음] `app/api/admin.py` Milvus expression injection** — round01 이월 항목 유지. 도서관 대회 이후 별도 라운드.
- **동시 세션 작업 충돌** — 다른 Claude 세션이 같은 체크아웃·같은 브랜치에 커밋(`89d1e1a`)해 서브에이전트의 `git commit --amend` 가 그 커밋을 덮었다. git 플러밍으로 히스토리를 재구성해 복구했고(`backup-before-amend-fix` 에 오염 상태 보존), 별건 작업은 `git worktree` 나 별도 브랜치로 분리해야 한다.

---

## 7. 다음 라운드 진입점
- round03 Task 6~7 이 우선. 문학 41편 도서 검색 실종이 실사용자에게 보이는 결함이다.
- 그 뒤 `docs/superpowers/specs/2026-09-15-search-top-pick-recommend-design.md`(다른 세션의 검색 추천 기획 초안)가 대기 중.

---

## 상태
- [x] code-reviewer 정적 리뷰 통과 — Task 1~4 각각 spec-compliance + code-quality 2단계 리뷰, 발견 사항 전부 반영(Task 4 는 Important 3건 포함)
- [x] 테스트 green — 120 passed (로컬 미설치 패키지로 collect 실패하는 3개 모듈 제외: `FlagEmbedding`·`openpyxl`)
- [x] 수동 스모크 — 복구 전 구간 라이브 API 검증(`/api/books/curate` 404→200, 초록·제목 노출 확인), 백업 복원 연습 완료
- [ ] 문서 갱신 — 완료노트 작성(이 문서). 교본·`00_status`·`recurring-gotchas.md` 미반영
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push
