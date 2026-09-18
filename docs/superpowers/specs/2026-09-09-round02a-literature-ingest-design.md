# round02a — 공공영역 문학 215권 자동 적재 설계

## 0. 사용자 프롬프트 (paraphrase)
> 연구/시연 목적으로, 저작권 문제 없는(주로 Project Gutenberg 공공영역) 문학 작품 목록(CSV, 제목·저자·출처·저작권상태·다운로드 링크 포함)을 인터넷에서 내려받아 NL-Lib에 적재하고 싶다. 처음엔 100권 CSV로 시작했고, 이어서 183권을 추가로 구해와 총 두 개의 CSV로 늘어났다. 실제 검색 데모/시연에도 함께 노출되어야 한다. 이번엔 계획만 세우고, 곧바로 구현하지 않는다. (별도로 논의된 SKOVIX 기관 연동 자동확보 파이프라인과는 성격이 달라 이 라운드에서는 분리한다 — 그쪽은 round02b로 별도 브레인스토밍.)

## 1. 배경
- 기존 NL-Lib 카탈로그(~700권)는 국립중앙도서관 CNTS 스캔 PDF + KCI 논문 위주로, OCR/VLM 추출 파이프라인이 이를 전제로 설계돼 있다.
- `skovix_literature_100.csv`(100행) + `skovix_literature_additional.csv`(183행), 대부분 Project Gutenberg의 **이미 디지털화된 클린 텍스트**(EPUB3/TXT/HTML)로, 스캔·OCR이 전혀 필요 없는 성격이 다른 입력이다.
- 이 작업은 SKOVIX 기관 연동 자동확보 파이프라인(round02b, 계획만 진행 예정)이 나중에 다룰 "이미 디지털인 자료"(공유마당 문학, CORE/OpenAlex OA 논문 등) 적재 방식을 미리 검증하는 축소판이기도 하다.

## 2. 범위
- **포함**: 두 CSV 합계 283행 중 정제 후 **215권**(§6 참고)의 다운로드 → 텍스트화 → PDF 변환 → 카탈로그 적재 → 임베딩/인덱싱 → 검색 노출까지.
- **제외(이번 라운드 아님)**:
  - SKOVIX 기관 연동 자동확보 파이프라인(국립중앙도서관 Open API·정보나루·KOLIS-NET·CORE/OpenAlex/Crossref·공유마당) — round02b로 별도 브레인스토밍·계획만.
  - FLUX 표지 생성 — 현재 리소스 문제로 비활성화 상태라 이번엔 스킵, 나중에 별도 백필(§7 이월).
  - Kafka `The Castle` — Project Gutenberg에 영어 공공영역판 자체가 없는 것으로 확인(§6), 이번 소스로는 확보 불가.

## 3. 아키텍처 — 전체 흐름

```
skovix_literature_100.csv (100행) + skovix_literature_additional.csv (183행)
        │
        ▼
⓪ CSV 병합 + 정제              두 CSV를 ebook ID 기준으로 병합, 중복·충돌 제거 → 215행 (§6)
   (신규 스크립트의 일부)
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
④ 매니페스트 생성              {book_id, file, object_key, size, title} × 215줄
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

신규 코드는 **⓪①②④**(CSV 병합·다운로드·PDF 변환·매니페스트 생성 스크립트) 뿐이다. ③⑤⑥⑦은 기존 코드·API를 그대로 호출한다 — `services/ingestion/extractor.py`(OCR/VLM)·`stages.py`·`indexer.py` 등 핵심 파이프라인은 **한 줄도 수정하지 않는다**.

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
- CSV 병합 직후: ebook ID 기준 중복·충돌 검출 스크립트 재실행 결과가 §6과 일치하는지 확인(215개).
- 매니페스트 생성 직후: `build_manifest.py` 스타일 검증(book_id 중복·0바이트 PDF·메타 누락)으로 215개 전부 매치 확인.
- PDF 변환 스팟체크: 5~8권을 직접 열어 인코딩 깨짐·레이아웃 문제 없는지 육안 확인(권수가 늘어난 만큼 스팟체크 표본도 확대).
- 잡 실행 후 `/admin/jobs` 대시보드에서 215/215 완료 확인.
- 검색 데모 스모크: 최소 2~3권을 실제로 검색해 제목·저자·요약·(폴백)표지가 정상 노출되는지 확인.
- 저작권 상태 집계: `extra->'acquisition'->>'copyright_status'`로 그룹핑해 "확인 필요" 상태가 몇 건인지 미리 파악(§4.4의 향후 필터링 대비 사전 점검). 두 번째 CSV는 전부 `"Project Gutenberg: U.S. public-domain basis; verify Korean use separately"`로 동일 표기라, 한국 저작권법 기준 재확인이 아직 안 됐다는 뜻 — 집계에서 별도로 눈에 띄게 표시한다.

## 6. 데이터 이슈 — 두 CSV 정제 경위

두 CSV(원본 100행 + 추가 183행, 합계 283행)를 ebook ID(Gutenberg URL의 `/ebooks/{id}`) 기준으로 교차검증한 결과:

### 6.1 원본 CSV 자체 결함 — Kafka `The Trial` / `The Castle`
- 37번(`The Trial`)과 38번(`The Castle`)의 `source_url`/`download_link`가 완전히 동일(`gutenberg.org/ebooks/7849` = 실제로는 The Trial). 이대로 두면 "The Castle" 제목 아래 The Trial 본문이 들어가는 오류.
- Gutenberg에서 직접 검색한 결과 **Kafka `The Castle`(Das Schloss)의 영어 공공영역판 자체가 Gutenberg 카탈로그에 없다**(Kafka 저자 목록엔 Metamorphosis·The Trial·단편들만 있음 — 번역판 저작권이 아직 살아있는 것으로 추정). **결론: 이번 소스로는 확보 불가 — "나중에 링크 보완"이 아니라 사실상 제외.** 다른 소스(Standard Ebooks 등)에서 구할 수 있는지는 round02b 이후 별도 검토.
- 100행 → **99행**으로 확정.

### 6.2 추가 CSV(183행) 내부 충돌 5건
같은 ebook ID를 서로 다른 제목 2개가 주장하는 경우가 5건 있었다. Gutenberg에서 직접 검색해 전부 해결:

| ebook ID | 충돌한 두 제목 | 실제 정답 | 비고 |
|---|---|---|---|
| 967 | Nicholas Nickleby / The Star Rover | **967 = Nicholas Nickleby**(원래 값이 맞음) | The Star Rover는 **1162**(Gutenberg 표제 "The Jacket (The Star-Rover)")로 정정 |
| 18857 | Journey to the Centre of the Earth / From the Earth to the Moon | **18857 = Journey to the Centre of the Earth**(원래 값이 맞음) | From the Earth to the Moon은 **83**(표준판, 8986/44278 등 이본 있음)으로 정정 |
| 910 | White Fang / Martin Eden | **910 = White Fang**(원본 100권 CSV와도 일치 확인) | Martin Eden은 **1056**으로 정정 |
| 2226 | Carmen / Kim | **2226 = Kim**(원본 100권 CSV와도 일치 확인) | Carmen은 **2465**로 정정 |
| 146 | A Little Princess / The Little Princess | 둘 다 동일 도서의 표제 이표기(원본 100권 CSV에 이미 `A Little Princess`로 포함) | 실질적 충돌 아님 — 원본과 중복이라 어차피 스킵 |

**결론**: 5건 모두 정확한 ebook ID가 확정됨 — Nicholas Nickleby(967)·Journey to the Centre of the Earth(18857)·White Fang(910, 원본과 중복)·Kim(2226, 원본과 중복)은 원래 있던 값 그대로 사용, The Star Rover(1162)·Martin Eden(1056)·Carmen(2465)은 정정된 ID로 신규 추가.

### 6.3 추가 CSV ↔ 원본 CSV 교차 중복 66건
추가 183행 중 66개 ebook ID가 원본 99권에 이미 포함돼 있음(예: The Time Machine, War and Peace, Jane Eyre 등). 완전 중복이라 자동 스킵 — 원본에 있는 메타데이터·정정을 그대로 신뢰한다.

### 6.4 최종 집계

충돌 5개 그룹 각각 정답/오답을 가려낸 뒤 최종 처리:

| 그룹(ID) | 항목 | 처리 |
|---|---|---|
| 967 | Nicholas Nickleby | 정답, 원본과 안 겹침 → **추가** |
| 967 | The Star Rover → 1162로 정정 | 원본과 안 겹침 → **추가** |
| 18857 | Journey to the Centre of the Earth | 정답, 원본과 안 겹침 → **추가** |
| 18857 | From the Earth to the Moon → 83으로 정정 | 원본과 안 겹침 → **추가** |
| 910 | White Fang | 정답이지만 원본과 중복(§6.3에 포함) → 스킵 |
| 910 | Martin Eden → 1056으로 정정 | 원본과 안 겹침 → **추가** |
| 2226 | Kim | 정답이지만 원본과 중복(§6.3에 포함) → 스킵 |
| 2226 | Carmen → 2465로 정정 | 원본과 안 겹침 → **추가** |
| 146 | A Little Princess / The Little Princess | 둘 다 원본과 동일 도서 → 스킵 |

충돌 그룹에서 순수 추가되는 건 6권(Nicholas Nickleby·The Star Rover·Journey to the Centre of the Earth·From the Earth to the Moon·Martin Eden·Carmen).

```
원본 CSV 100행 - The Castle 1건(§6.1, 확보 불가) = 99행
+ 추가 CSV 183행에서:
    교차중복 66건(§6.3, 충돌그룹 중 White Fang·Kim·A Little Princess/The Little Princess 포함) → 스킵
    내부 충돌 5개 그룹 중 순수 신규 6건(위 표) → 추가
    나머지 정상 신규 110건 → 추가
= 99 + 110 + 6 = 최종 215권
```
스크립트로 ebook ID 집합 연산 재검증 완료(§5) — 세 부분(99·110·6) 사이에 겹치는 ID 없음을 확인.

## 7. 이월
- Kafka `The Castle` — Project Gutenberg엔 없음(§6.1). Standard Ebooks·Internet Archive 등 다른 공공영역 소스에서 영어 공공영역판을 구할 수 있는지 확인되면 개별 추가.
- 표지 백필 — FLUX 재활성화 시, 이 215권 중 `cover_image_key IS NULL`인 행만 골라 이미 저장된 title·personal_author·kdc·themes·introduction·summary로 `services/ingestion/cover_generator.py::generate_and_store_cover()`를 재호출하는 짧은 스크립트 하나면 됨 — extract·summarize·embed_index 재실행 불필요.
- 두 번째 CSV의 `copyright_status`가 전부 "verify Korean use separately"로 동일 — 한국 저작권법 기준 재확인은 아직 안 된 상태(§5). 필요 시 개별 검토.
- round02b(SKOVIX 기관 연동 자동확보 파이프라인) — 별도 브레인스토밍·계획.

## 8. 디자인 참조
해당 없음 — 디자인 트랙 미도입(`docs/design/README.md`). 이 작업은 기존 검색 UI에 새 데이터가 노출되는 것뿐, 신규 화면·UI 변경 없음.
