# round02a — 공공영역 문학 99권 자동 적재 설계

## 0. 사용자 프롬프트 (paraphrase)
> 연구/시연 목적으로, 저작권 문제 없는(주로 Project Gutenberg 공공영역) 문학 작품 100권 목록(CSV, 제목·저자·출처·저작권상태·다운로드 링크 포함)을 인터넷에서 내려받아 NL-Lib에 적재하고 싶다. 실제 검색 데모/시연에도 함께 노출되어야 한다. 이번엔 계획만 세우고, 곧바로 구현하지 않는다. (별도로 논의된 SKOVIX 기관 연동 자동확보 파이프라인과는 성격이 달라 이 라운드에서는 분리한다 — 그쪽은 round02b로 별도 브레인스토밍.)

## 1. 배경
- 기존 NL-Lib 카탈로그(~700권)는 국립중앙도서관 CNTS 스캔 PDF + KCI 논문 위주로, OCR/VLM 추출 파이프라인이 이를 전제로 설계돼 있다.
- `skovix_literature_100.csv`(첨부, 100행)는 대부분 Project Gutenberg의 **이미 디지털화된 클린 텍스트**(EPUB3/TXT/HTML)로, 스캔·OCR이 전혀 필요 없는 성격이 다른 입력이다.
- 이 작업은 SKOVIX 기관 연동 자동확보 파이프라인(round02b, 계획만 진행 예정)이 나중에 다룰 "이미 디지털인 자료"(공유마당 문학, CORE/OpenAlex OA 논문 등) 적재 방식을 미리 검증하는 축소판이기도 하다.

## 2. 범위
- **포함**: CSV 100행 중 99행(38번 `The Castle` 제외 — §6 참고)의 다운로드 → 텍스트화 → PDF 변환 → 카탈로그 적재 → 임베딩/인덱싱 → 검색 노출까지.
- **제외(이번 라운드 아님)**:
  - SKOVIX 기관 연동 자동확보 파이프라인(국립중앙도서관 Open API·정보나루·KOLIS-NET·CORE/OpenAlex/Crossref·공유마당) — round02b로 별도 브레인스토밍·계획만.
  - FLUX 표지 생성 — 현재 리소스 문제로 비활성화 상태라 이번엔 스킵, 나중에 별도 백필(§7 이월).
  - CSV 38번(`The Castle`) — 원본 링크 데이터 오류(§6), 정확한 링크 확보 후 별도 처리.

## 3. 아키텍처 — 전체 흐름

```
skovix_literature_100.csv (99행 사용)
        │
        ▼
① 다운로드 + 텍스트화        각 행의 download_link에서 원문 다운로드
   (신규: scripts/literature_ingest/fetch_and_render.py)
                              TXT 우선(가능하면), EPUB만 있으면 파싱해 텍스트 추출
        │
        ▼
② 텍스트 → 간단 PDF 생성      책 1권 = PDF 1개 (제목 페이지 + 본문, 단일 컬럼)
   (같은 스크립트)
        │
        ▼
③ 카탈로그 upsert             CSV 메타 → library_catalog
   (기존 repositories/catalog_bulk.py::upsert_catalog_records() 재사용)
        │
        ▼
④ 매니페스트 생성              {book_id, file, object_key, size, title} × 99줄
   (scripts/bulk_ingest/build_manifest.py 패턴을 CSV 소스에 맞게 변형)
        │
        ▼
⑤ MinIO 업로드                 scripts/bulk_ingest/upload_from_manifest.py 그대로 재사용
                                → originals/{book_id}.pdf
        │
        ▼
⑥ 잡 생성 + 시작                POST /api/admin/ingest-jobs (기존 admin API 그대로)
                                params: {"doc_type": "literature", "skip_cover": true}
                                → extract → summarize → embed_index → finalize
                                  (전부 기존 코드 무변경 — services/ingestion/stages.py)
        │
        ▼
⑦ /admin/jobs 대시보드로 진행 모니터링 (기존 UI, 무변경)
```

신규 코드는 **①②④**(다운로드·PDF 변환·매니페스트 생성 스크립트) 뿐이다. ③⑤⑥⑦은 기존 코드·API를 그대로 호출한다 — `services/ingestion/extractor.py`(OCR/VLM)·`stages.py`·`indexer.py` 등 핵심 파이프라인은 **한 줄도 수정하지 않는다**.

## 4. 세부 규칙

### 4.1 book_id
- Gutenberg 출처: `LIT-GUTENBERG-{ebook번호}` (예: `https://www.gutenberg.org/ebooks/1342` → `LIT-GUTENBERG-1342`)
- Standard Ebooks 출처(어린왕자 1건): `LIT-STDEBOOKS-{URL 슬러그}` (예: `LIT-STDEBOOKS-antoine-de-saint-exupery-the-little-prince`)
- 기존 `CNTS-...`(국중)·`KCI_FI...`(KCI) 접두사와 겹치지 않아 `cnts_id` unique 제약과 충돌 없음.

### 4.2 메타데이터 매핑 (`library_catalog`)
| 필드 | 값 |
|---|---|
| `cnts_id` | §4.1의 book_id |
| `title` | CSV `title` |
| `personal_author` | CSV `author` |
| `url` | CSV `source_url` |
| `language` | `"eng"` (MARC 008 방식 3자리 코드 — 전부 영어 원문/영역본) |
| `doc_type` | `"literature"` (기존 KDC 800~899 판별값과 동일 — 잡 파라미터로 명시 지정, KDC 없이도 정확히 분류됨) |
| `source_format` | `"PD_TEXT"` (신규 값 — 기존 `MARC`/`MODS`/`KCI`와 구분되는 "공공영역 텍스트" 표시) |
| `extra.acquisition` | `{source, copyright_status, download_format, download_link}` — CSV 원본 행 그대로 보존 (§4.4) |

카탈로그 upsert는 매니페스트/잡 생성보다 **먼저** 수행한다 — `run_extract`의 `_ensure_book_and_doc_type()`은 카탈로그 row가 이미 있으면 그대로 쓰고, 없으면 PDF에서 LLM으로 메타를 추측하므로(부정확할 수 있음), CSV의 정확한 메타를 먼저 심어 그 추측 경로를 타지 않게 한다.

### 4.3 PDF 변환
- 다운로드: `download_link` 우선 시도, 실패 시 같은 ebook의 TXT 변형(`.txt.utf-8` 등) 폴백. EPUB인 경우 챕터 HTML을 파싱해 텍스트만 추출(`ebooklib` + HTML 태그 제거).
- 변환: 텍스트 → 단순 단일 컬럼 PDF(제목 페이지 1장 + 본문). 표·이미지 없음 — 화려한 서식 불필요(기존 코딩표준 "교육적·모범적" 원칙과 일치).
- 원본 파일(EPUB/TXT) 자체는 MinIO에 보관하지 않는다(§4.4의 `extra.acquisition.download_link`로 언제든 재다운로드 가능하므로 중복 저장 불필요).

### 4.4 저작권 추적 (`extra` JSONB)
- 신규 DB 컬럼·마이그레이션 없이 기존 `extra` JSONB 필드를 재사용한다(코딩표준 문서의 "도메인 확장 필드" 용도와 일치).
- `extra["acquisition"] = {"source": "Project Gutenberg", "copyright_status": "Public domain (US)", "download_format": "EPUB3/TXT/HTML", "download_link": "https://..."}` 형태로 CSV 원본 필드를 그대로 보존.
- 나중에 저작권 문제가 의심되는 항목만 선별해 삭제할 때: `SELECT cnts_id, title, extra->'acquisition'->>'copyright_status' FROM library_catalog WHERE extra->'acquisition'->>'copyright_status' NOT IN ('Public domain (US)') ` 식으로 조회 후 개별 삭제 가능. (CSV상 `Jurisdiction-specific`/`verify jurisdiction`/`Not safe to classify globally` 상태인 행이 여럿 있어 실제로 쓰이게 될 조회다.)

### 4.5 표지 생성
- FLUX 모듈이 현재 리소스 문제로 비활성화 상태 — 이번 잡은 `skip_cover: true`로 실행(KCI 논문 적재와 동일 방식).
- 표지가 없어도 `GET /api/books/{cnts_id}/thumbnail`이 "PDF 1페이지 즉석 렌더"로 자동 폴백하므로 화면은 깨지지 않는다.
- 나중에(FLUX 재활성화 시) 표지만 별도로 채우는 방법은 §7 이월 참고.

## 5. 검증 방법
- 매니페스트 생성 직후: `build_manifest.py` 스타일 검증(book_id 중복·0바이트 PDF·메타 누락)으로 99개 전부 매치 확인.
- PDF 변환 스팟체크: 3~5권을 직접 열어 인코딩 깨짐·레이아웃 문제 없는지 육안 확인.
- 잡 실행 후 `/admin/jobs` 대시보드에서 99/99 완료 확인.
- 검색 데모 스모크: 최소 2~3권을 실제로 검색해 제목·저자·요약·(폴백)표지가 정상 노출되는지 확인.
- 저작권 상태 집계: `extra->'acquisition'->>'copyright_status'`로 그룹핑해 "확인 필요" 상태가 몇 건인지 미리 파악(§4.4의 향후 필터링 대비 사전 점검).

## 6. 데이터 이슈 — CSV 38번 제외
- CSV 37번(`The Trial`)과 38번(`The Castle`, 둘 다 Kafka)의 `source_url`/`download_link`가 완전히 동일하다(`gutenberg.org/ebooks/7849` = 실제로는 The Trial). 이대로 적재하면 "The Castle"이라는 제목 아래 The Trial 본문이 들어가는 오류가 발생한다.
- **결정**: 이번 라운드에서는 38번을 제외(99행만 처리)하고, 정확한 링크를 확보한 뒤 별도로 보완한다(§7 이월).

## 7. 이월
- CSV 38번(`The Castle`) — 정확한 Gutenberg 링크 확보 후 개별 추가.
- 표지 백필 — FLUX 재활성화 시, 이 99권 중 `cover_image_key IS NULL`인 행만 골라 이미 저장된 title·personal_author·kdc·themes·introduction·summary로 `services/ingestion/cover_generator.py::generate_and_store_cover()`를 재호출하는 짧은 스크립트 하나면 됨 — extract·summarize·embed_index 재실행 불필요.
- round02b(SKOVIX 기관 연동 자동확보 파이프라인) — 별도 브레인스토밍·계획.

## 8. 디자인 참조
해당 없음 — 디자인 트랙 미도입(`docs/design/README.md`). 이 작업은 기존 검색 UI에 새 데이터가 노출되는 것뿐, 신규 화면·UI 변경 없음.
