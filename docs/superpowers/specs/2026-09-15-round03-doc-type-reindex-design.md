# round03 — 문학 41편 doc_type 오분류 교정 + 재발방지 설계

## 0. 사용자 프롬프트 (paraphrase)
> 검색 결과에 논문과 도서가 둘 다 이상하게 뜬다 — 카드에 제목 대신 `CNTS-00049204004` 같은 ID가 나오고 `/api/books/curate` 가 404 를 낸다. (원인 추적 결과 `library_catalog` 전체 유실로 판명, 복구 완료.) 복구 과정에서 드러난 **문학 41편의 `doc_type` 오분류를 재인덱싱으로 바로잡고, 라운드로 정리하자.** 재기록 시 청크 백업을 넣을 것.

## 1. 배경

### 1-1. 선행 사건 — `library_catalog` 전체 유실 (2026-09-14)
`library_catalog` 가 통째로 비워졌다. `book_sections`(1,121,526행) · Milvus(3,884,183청크) · MinIO(238,369객체)는 전부 무사했고 **카탈로그 메타 행만** 사라져, 고아 문서 72,601건이 발생했다.

- 증상: 검색 카드 `book_info: null` → 프론트가 ID 를 제목 자리에 출력, `title_score` 계산 불가, `POST /api/books/curate` 가 404(`get_by_cnts_ids` 빈 결과)
- 논문·도서가 함께 깨진 이유: 둘 다 같은 `library_catalog` 를 쓴다(`doc_type='paper'` 로 구분)
- 표지가 계속 보인 이유: 썸네일이 ① DB 커버키 → ② MinIO 캐시 → ③ 원본 PDF 1페이지 즉석 렌더로 폴백해, DB 없이 ③ 으로 그려지고 있었다

복구는 이번 세션에서 이미 끝냈다(§6-1). 이 spec 의 구현 범위는 **복구 과정에서 드러난 별건 버그**다.

### 1-2. 이번 라운드가 다루는 버그 — 문학 41편이 `doc_type='paper'`
위키문헌(`WS_*` 36편) · 공유마당(`GM_*` 5편)에서 크롤링한 한국 근대문학(무정 · 진달래꽃 · 님의 침묵 · 구운몽 · 홍길동전 등)이 Milvus 스칼라에 `doc_type='paper'` 로 박혀 있다.

**근본 원인**: 이 문서들은 카탈로그 적재를 거치지 않고 바로 인덱싱됐다. `_ensure_book_and_doc_type`(`app/services/ingestion/stages.py:337`)가 카탈로그 행이 없으면 PDF 에서 메타를 자동추출해 행을 만드는데(`source_format="PDF"`), 그때 LLM 이 찍은 `genre` 를 `detect_doc_type` 이 그대로 신뢰한다. `app/domains/nl_library/doc_types.py:38` 이 `genre in ("paper","thesis","report")` 면 **KDC 검사 전에 즉시 `paper` 로 단락**하고, 이 문서들엔 KDC 가 없어 구제되지 못했다.

**피해가 비대칭이다.**

| 필터 | 표현식 | 결과 |
|---|---|---|
| 논문 | `(doc_type == "paper" \|\| book_id like "KCI_FI%")` | 41편이 **논문 검색을 오염** |
| 도서 | `(doc_type != "paper" && not (book_id like "KCI_FI%"))` | 41편이 **도서 검색에서 완전 실종** |

논문 쪽엔 `book_id like "KCI_FI%"` 라는 ID 기반 안전망이 있어 진짜 논문은 `doc_type` 이 틀려도 잡힌다. 도서 쪽엔 그런 안전망이 없어, `paper` 오판정 한 번이면 문서가 도서 검색에서 통째로 사라진다. 지금 「무정」을 도서로 검색하면 안 잡힌다.

이 오분류는 **이번 유실 사고 이전부터 있었다.** 제목이 정상 출력되던 때에는 눈에 띄지 않았을 뿐이다.

## 2. 범위

**포함**
- Milvus `doc_type` 스칼라 재기록 도구(백업 · 재기록 · 검증 · 복구) 신규 작성
- 문학 41편의 Milvus `doc_type` → `literature` 교정 실행
- 재발방지: `detect_doc_type` 판정 수정 + `run_embed_index` 빈 본문 가드
- 크롤링 적재 시 `doc_type` 명시를 운영 절차로 못박기(`docs/ops/bulk_ingest_runbook.md`)
- §1-1 복구 경위를 완료노트에 기록

**제외 (이번 라운드 아님)**
- **LLM 생성물 재생성** — 유실된 `summary` · `themes` · `introduction` · `cover_prompt` 는 41편만의 문제가 아니라 복원된 72,800건 전체의 문제다. `plot` · `read_effect` 는 기존 백필 엔드포인트(`/api/admin/backfill/plot`, `/backfill/read-effect`)가 있고 나머지는 백필 태스크가 없다. 별도 라운드.
- **41편 전체 재적재** — `run_extract` 가 `book_sections` 를 지우고 다시 만들어(`stages.py:300`) 현재 99.9% 살아있는 섹션 요약·테마(1,120,153 / 1,121,526)를 갈아엎는다. OCR·LLM 비용도 크다.
- **Postgres 기준 후처리 필터** (검토했으나 채택하지 않음) — 검색 후 `book_info.doc_type` 으로 스코프 불일치 건을 걸러내는 안이다. 위험이 거의 없고 향후 오분류에 자동 대응하지만, 애초에 검색되지 않은 문서를 후처리로 되살릴 수는 없어 **"도서 검색 실종"이라는 증상의 절반을 못 고친다.** 근본 원인을 코드로 막으면(§4-2) 안전망 가치도 줄어들어, 핫패스에 코드를 더할 근거가 약하다.
- **청크 0건 논문 2편**(`KCI_FI003333197` · `KCI_FI003335027`) — 카탈로그 원본·Milvus 메타청크 모두 없고 임베딩도 없다. 원본 PDF 재적재가 필요해 별건.
- **`app/api/admin.py` Milvus expression injection** — round01 완료노트의 이월 항목, 대회 시연 이후로 보류 유지.

## 3. 아키텍처 — 재기록 도구 흐름

```
① 대상 선정 (Postgres)
   library_catalog WHERE extra->>'restored_from' = 'milvus_meta_chunk'
   → {cnts_id, doc_type} 41건
        │
        ▼
② 불일치 판정 (문서별)
   Milvus 메타청크(chunk_idx = -1)의 doc_type  vs  Postgres doc_type
   같으면 skip → 중간에 끊겨도 재실행하면 남은 것만 처리 (멱등)
        │
        ▼
③ 백업 (문서별)
   해당 book_id 전 청크를 스키마 전 필드 + embedding + sparse_embedding 까지 읽어(offset 페이징)
   /app/data/recovery/backup/doc_type_<타임스탬프>/<book_id>.jsonl 로 저장
   (호스트 바인드 마운트 /data/nl-lib/data → 컨테이너가 죽어도 남는다)
        │
        ▼
④ 백업 검증
   백업 줄 수 == Milvus 청크 수 ?  아니면 그 문서는 건너뛴다 — 교체하기 전에 멈춘다
        │
        ▼
⑤ 재기록
   col.upsert(읽은 값 그대로, doc_type 만 교체)  ← 기본키(chunk_id) 제자리 교체
        │
        ▼
⑥ 사후 검증
   재조회로 청크 수 · doc_type 확인. 어긋나면 즉시 중단하고 남은 문서는 손대지 않는다
```

**처리 단위는 문서 1건.** Milvus 에는 트랜잭션이 없어 41편을 묶어봐야 의미가 없고, 문서 단위로 끊으면 실패 피해가 그 1편에 갇힌다.

## 4. 구성요소

### 4-1. `scripts/recovery/rewrite_milvus_doc_type.py` (신규)

| 모드 | 동작 |
|---|---|
| (기본) dry-run | 대상 목록 · 문서별 청크 수 · 예상 백업 용량만 출력. 아무것도 쓰지 않는다 |
| `--apply` | §3 의 ③~⑥ 실행 |
| `--restore <백업디렉터리>` | 백업 JSONL 을 그대로 되돌린다 (같은 upsert 경로) |
| `--limit N` | 대상을 N 건으로 자른다 — 첫 운영 실행을 1건으로 하기 위한 안전장치 |

**`index_chunks()` 를 재사용하지 않는다.** 그 함수는 `chunk_id` 를 `{book_id}__{idx:04d}` 로 재생성하고 `text` 를 다시 16,000바이트로 자른다(`app/services/ingestion/indexer.py:223`). 읽은 값을 한 글자도 바꾸지 않고 되넣어야 하므로 별도 insert 경로를 쓴다. 컬럼 순서만 `_scalar_field_specs()` 로 스키마와 맞춘다.

실행은 앱 이미지에 `scripts/` 가 없어 호스트 바인드 마운트를 경유한다. 스크립트 파일로 실행하면 `sys.path[0]` 이 스크립트 디렉터리로 잡혀 앱 모듈을 못 찾으므로 `PYTHONPATH=/app` 이 필요하다.

```
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py
docker exec -e PYTHONPATH=/app nl-lib-fastapi python /app/data/recovery/rewrite_milvus_doc_type.py --apply
```

`pymilvus==2.4.6` — `Collection.upsert` 가용 확인 완료. 청크 조회는 `query` + offset 페이징을 쓴다.

### 4-2. `detect_doc_type` 수정 (`app/domains/nl_library/doc_types.py`)

2층 방어로 간다.

**원천 — 크롤링 적재 시 `doc_type` 명시.** 메커니즘은 이미 있다. `IngestJob.params` 가 `{"skip_cover": true, "doc_type": "paper", ...}` 를 지원하고(`app/models/ingest_job.py:40`), `_ensure_book_and_doc_type` 는 `ctx.params.get("doc_type")` 를 최우선으로 본다. 코드 추가 없이 쓰기만 하면 된다. 매니페스트 스키마는 건드리지 않는다 — 한 코퍼스 = 한 `doc_type` 이라 잡 단위 지정으로 충분하다. `docs/ops/bulk_ingest_runbook.md` 에 **카탈로그 없는 코퍼스는 `doc_type` 을 반드시 지정한다**를 절차로 넣는다.

**안전망 — `source_format == "PDF"` 면 `genre` 단락을 건너뛴다.** PDF 자동추출의 `genre` 는 LLM 추측이라 실제 카탈로그에서 온 값과 신뢰도가 같을 수 없다. 이 경우 KDC → 제목 키워드 → 기본값(`book`) 순으로 내려간다.

대가: 카탈로그 없이 올라온 진짜 학위논문 PDF 가 `book` 으로 잡힌다. 그래도 도서 검색에서 보이는 상태라 회복 가능하고, 적재 시 `params` 로 명시하면 그게 이긴다. §1-2 의 비대칭 — `paper` 오판정은 도서 검색 실종(치명적), `book` 오판정은 ID 폴백으로 완화 — 을 고려한 선택이다.

원천만으론 절차 의존이라 또 빠뜨리면 재발하고, 안전망만으론 학위논문 PDF 가 `book` 으로 잡히는 대가를 계속 진다. 둘 다 있어야 한다.

### 4-3. `run_embed_index` 빈 본문 가드 (`app/services/ingestion/stages.py`)

현재 아티팩트가 없고 `doc_type != "paper"` 면 `full_text = ""` 로 조용히 진행한다(`stages.py:494`). 그러면 청킹 결과 0개인 채로 `col.delete(book_id)` → 메타청크 1개만 insert 가 돌아 **기존 본문 청크가 전멸한다.** `run_finalize` 가 성공한 문서의 추출 아티팩트를 지우므로(`stages.py:803`), 이미 적재 완료된 문서에서 임베딩 단계만 다시 돌리면 바로 이 경로를 밟는다.

폴백 텍스트조차 만들지 못하면 `StageError("empty_body", ...)` 로 중단시킨다. **인덱스를 건드리기 전에 멈추는 것**이 요점이다.

판정은 `full_text.strip()` 으로 한다. `load_extraction_artifact` 의 페이지 필터가 truthiness 기반이라 공백만 있는 페이지 텍스트가 살아남고, 청킹 단계(`chunker._normalize_linebreaks` 끝의 `strip()`)에서야 빈 문자열이 돼 0청크가 되기 때문이다.

`error_group` 에 기존 `artifact_missing` 을 재사용하지 않는 이유: 위 `strip()` 때문에 **아티팩트가 정상 로드된 문서도 이 가드에 걸린다.** 그런 건을 `artifact_missing` 으로 집계하면 실패 대시보드(`/api/admin/ingest-jobs/{id}/failures`)가 거짓을 말하고, 그 그룹의 표준 복구 절차("extract 단계부터 재실행")도 맞지 않는다. `error_group` 은 `String(32)` 자유 문자열이고 집계·필터에만 쓰여(`app/api/ingest_jobs.py:253`) 새 값 도입에 부수 작업이 없다.

## 5. 오류 처리 · 롤백

| 실패 지점 | 상태 | 대응 |
|---|---|---|
| ③ 백업 중 | Milvus 무손상 | 그 문서 건너뜀, 다음 문서 진행 |
| ④ 검증 불일치 | Milvus 무손상 | 그 문서 건너뜀 (지우기 전) |
| ⑤ upsert 실패 | **변화 없음** — 기존 청크 유지 | 재실행 (백업은 그래도 남긴다) |
| ⑥ 사후 검증 실패 | 해당 문서 의심 | 즉시 전체 중단, 남은 문서는 손대지 않음 |

**delete + insert 가 아니라 upsert 를 쓴다.** 기본키(`chunk_id`)가 동일해 의미는 같으면서, 그 문서의 청크가 0개가 되는 구간이 생기지 않는다 — delete 직후 죽으면 지워진 상태로 남지만 upsert 는 실패해도 기존 청크가 그대로다. 이로써 **실제 데이터 소실 경로가 사라진다.**

백업은 그래도 남긴다. `fetch_chunks` 가 일부를 놓치면 upsert 가 읽어온 것만 교체해 옛 `doc_type` 청크가 섞인 채 남을 수 있어, 줄 수 대조(④)와 사후 검증(⑥)이 여전히 필요하고 되돌릴 수단도 있어야 한다. 피해 범위는 항상 1문서다.

## 6. 검증

### 6-1. 선행 복구 (이번 세션에서 완료 — 완료노트에 기록)

| 항목 | 결과 |
|---|---|
| `/api/admin` · `/docs` 외부 노출 차단 | 403 확인 (`infra/conf.d/default.conf`) |
| 논문 카탈로그 (`metadata.xlsx`, 260,388건 파싱) | 신규 236,478 / 갱신 3,837 |
| 도서 카탈로그 (`marc_mods*.xlsx` 5개) | 703건 |
| 한국 근대문학 41편 (Milvus 메타청크 역복원) | 41건 |
| `cover_image_key` 재매핑 (`covers/{cnts_id}.jpg` 결정론적) | 588건, 무손실 |
| `is_embedded` · `ingest_state` · `full_text_length` | 72,841건 |
| 파편 정리 (`CNTS-*_` 3건 · `LIT-GUTENBERG-100`) | 임베딩 없는 중단분, 삭제 |
| 고아 문서 | 72,601 → **2건** (임베딩 없는 논문 2편, §7 이월) |
| `POST /api/books/curate` | 404 → 200 |

### 6-2. 단위 테스트 (`app/tests/`)

- `detect_doc_type` — ① `source_format="PDF"` + `genre="paper"` → `paper` 아님 ② `source_format="KCI"` + `genre="paper"` → 여전히 `paper` ③ KDC 800–899 → `literature` 유지 ④ 기존 policy / book 분기 회귀
- `run_embed_index` 빈 본문 가드 — 아티팩트 없고 폴백 불가면 `StageError`, **`col.delete` 가 호출되지 않는다**(핵심 단언)
- 재기록 스크립트 순수 함수 — 백업 직렬화 ↔ 역직렬화 값 보존(특히 sparse 벡터), 스칼라 교체가 `doc_type` 만 바꾸는지

### 6-3. 운영 검증 (순서대로)

1. dry-run — 대상 41편 목록 · 문서별 청크 수 · 예상 백업 용량
2. `--apply` 후 — 문서별 청크 수 전후 동일, `doc_type` 샘플이 `literature`
3. **라이브 API — 도서 검색에 「무정」이 잡히고, 논문 검색에서 빠진다**

3번이 합격 기준이다. 1·2번을 통과해도 3번이 안 되면 의미가 없다.

## 7. 이월

- **LLM 생성물 재생성** — `summary` · `themes` · `introduction` · `cover_prompt` 가 복원된 72,800건 전체에서 유실. `plot` · `read_effect` 는 기존 백필 엔드포인트 존재, 나머지는 백필 태스크 신규 작성 필요. 섹션 요약이 99.9% 살아있어 재추출 없이 LLM 호출만으로 가능하다.
- **청크 0건 논문 2편** — `KCI_FI003333197`(Name Customization, Psychological Ownership, and Resale Penalty) · `KCI_FI003335027`(나노초 레이저 및 화학 처리를 이용한 316 스테인리스강의 초소수성 표면 제작 및 특성 분석). 본문에서 읽은 서지정보로 카탈로그 행은 수기 등록 가능하나, 임베딩이 없어 검색에 잡히려면 원본 PDF 재적재가 필요하다.
- **`CNTS-00052063319` OCR 품질** — 삭제한 중복본(`…319_`)의 제목이 `宋純의詩歌文學研究` 로 정확한 반면, 남긴 정본은 `宋純純の詩歌文學研究` 로 깨져 있다. 남는 쪽이 품질이 낮은 추출본이라, 그 1건만 재추출하면 좋다. VLM 폴백 라우팅 오류와 같은 계열로 보인다.
- **`build_manifest.py` ID 정규화 누수** — `normalize_book_id`(`scripts/bulk_ingest/build_manifest.py:41`)가 "strip + 끝 `_` 제거"를 하는데, 삭제한 `CNTS-*_` 3건은 이 정규화를 거치지 않은 경로로 들어왔다. 어느 경로인지 미확인.
- **Postgres 백업 부재** — `docker-compose.yml` 에 백업 서비스가 없다. 이번 사고에서 복구가 가능했던 건 원본 카탈로그 파일이 `/data/nl-lib/data/uploads/` 에 남아 있었기 때문이지 설계된 안전장치 덕이 아니다. 정기 `pg_dump` 도입 필요.
- **호스트 포트 직접 노출** — `fastapi`(18002) · `postgres`(15432) · `redis`(16379) · `minio`(21000/21001)가 호스트에 발행돼 있어 게이트웨이 `deny` 를 우회한다. 외부에선 방화벽에 막혀 있으나 사내망에는 열려 있다. `127.0.0.1:` 바인딩으로 좁힐 것.
