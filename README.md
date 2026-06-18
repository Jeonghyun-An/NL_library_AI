# NL-Lib — 국립중앙도서관 의미 기반 검색 시스템

**최종 갱신:** 2026-06-18
**작성자:** 안정현
**프로젝트명:** NL-Lib (National Library — Semantic Search)

---

## 왜 일반 RAG로는 부족한가

대부분의 RAG 시스템은 세 가지 구조적 한계를 가진다.

| 한계 | 일반 RAG | NL-Lib |
| --- | --- | --- |
| **어휘 매칭 실패** | Dense 벡터만 사용 → "기획예산처", "국가재정법" 같은 고유명사를 의미 공간에서 놓침 | BGE-M3 **Dense + Sparse 하이브리드** → 의미 + 어휘 동시 검색 |
| **메타데이터 무시** | 본문 텍스트만 임베딩 → "조달청의 2024년 최신 자료"처럼 구조적 조건은 처리 불가 | MARC/MODS 메타데이터를 **두 레이어**로 분리 활용 (전용 메타 청크 + Milvus 스칼라 필터) |
| **맥락 없는 청크** | 잘린 문단만 임베딩 → "이 문단이 책의 어떤 맥락인지"가 벡터에 없음 | **Contextual Chunking** — 섹션 테마/요약을 청크 임베딩에 주입 |

이 세 문제를 해결하기 위해 설계한 것이 NL-Lib이다. 본 문서는 2026-06-18 시점의 구현 현황과 앞으로의 개선 과제를 정리한다.

---

## 1. 차별화 포인트

### 1.1 Dense + Sparse 하이브리드 검색 (BGE-M3)

도서관 데이터는 기관명·법령명·인명처럼 Dense가 취약한 고유명사가 핵심 검색어다. BGE-M3의 Sparse 벡터(어휘 가중치)를 함께 쓰면 **고유명사·전문용어 매칭**이 근본적으로 달라진다.

```
Dense  : "기획예산처 예산안" → 의미 공간에서 "재정 정책 문서"와 가까운 것들
Sparse : "기획예산처"의 토큰 ID → 해당 토큰이 포함된 문서를 정확히 타격
RRFRanker(k=60) → 의미 + 어휘 동시 만족 문서가 상위
```

```python
dense_req  = AnnSearchRequest(data=[query_dense],  anns_field="embedding",        ...)
sparse_req = AnnSearchRequest(data=[query_sparse], anns_field="sparse_embedding", ...)
results = col.hybrid_search(reqs=[dense_req, sparse_req], rerank=RRFRanker(k=60), ...)
```

### 1.2 메타데이터 기반 검색 — 이중 전략

#### ① 메타데이터 전용 청크 (`chunk_idx = -1`)

```
메타 텍스트: "제목: X | 기관: 조달청 | 출판사: Y | 발행년도: 2024 | KDC: 320 | 주제: ... | 초록: ..."
→ 본문 청크와 동등하게 Milvus에 저장
→ 검색 후 응답에는 노출하지 않고 도서 점수 산정에만 사용
```

#### ② Milvus 스칼라 필드 expression 필터

```python
# "2023년 이후 환경부 정책" 같은 자연어 → LLM이 조건 추출 (metadata_filter.py)
expr = 'pub_date >= "2023" && pub_date < "2025"'

# 논문/도서 도메인 분리
_PAPER_EXPR = 'book_id like "KCI_FI%"'
_BOOK_EXPR  = 'book_id not like "KCI_FI%"'
```

날짜 정렬 요청 시 후보 풀을 `top_k × 4`로 확장 후 정렬 → 축소한다. (후보가 적으면 가장 최근 책이 벡터 점수로 탈락해 있을 수 있다.)

### 1.3 Contextual Chunking — 테마·요약을 벡터에 주입

```
임베딩 입력 (저장은 원본 텍스트):
  "[핵심 테마] 가부장적 폭력, 채식, 신체적 저항
   [섹션 요약] 영혜가 채식을 통해 폭력에 저항하는 과정을 다룸
   [본문] 채식주의자는 폭력에 맞서는 방식으로..."
```

이를 위해 **계층적 요약 파이프라인**을 먼저 수행:

1. 섹션(3000~5000토큰) → LLM 섹션 요약 + 테마 키워드 동시 추출 (`LLM_SECTION_CONCURRENCY` 병렬)
2. 섹션의 테마·요약을 청크 임베딩 prefix로 활용
3. 전체 섹션 요약 합산 → LLM 도서 요약 + 도서 테마 (1회 호출). 합산 길이가 상한(`SUMMARIZER_MAX_INPUT_CHARS`, 기본 14000자)을 넘으면 앞부분만 자르지 않고 **책 전체에 걸쳐 균등 샘플링**하여 컨텍스트 오버플로를 방지한다.

### 1.4 다중 매칭 부스팅

동일 도서 내에서 여러 청크가 매칭될수록 도서 적합도가 높다는 점을 점수에 반영한다.

```python
# 청크 1개=×1.00, 2개=×1.10, 3개=×1.16, 5개=×1.23 (상한 1.0 클립)
if n_chunks > 1:
    best = min(best * (1 + 0.1 * math.log2(n_chunks)), 1.0)
```

### 1.5 콘텐츠 3분리 — 도서 소개 / AI 추천 이유 / 도서 대화

| 표시 항목 | 내용 | 생성 시점 | 엔드포인트 |
| --- | --- | --- | --- |
| **도서 소개** (introduction) | 이 책이 어떤 책인지 — 사서 톤 자연어 | 인덱싱 시 1회, PostgreSQL 저장 | `GET /api/books/{id}` |
| **AI 추천 이유** | 이 질의에 이 책의 어떤 부분이 답이 되는지 | 검색 후 실시간 SSE 스트리밍 | `POST /api/books/reason/stream` |
| **이 책과 대화하기** | 특정 도서 내부에서 RAG 기반 심층 Q&A | 사용자 메시지마다 SSE 스트리밍 | `POST /api/books/chat/{id}` |

추천 이유 프롬프트에 "책의 일반적인 소개는 도서 소개란에 이미 표시됩니다. 반복하지 마세요"를 명시 → 두 섹션이 중복되지 않게 한다.

### 1.6 문서 유형별 특화 요약

`detect_doc_type()` 으로 KDC, 제목 키워드, PDF source_format + genre 를 조합해 판별, 유형별 최적 프롬프트를 적용한다.

| 유형 | 판별 기준 | 요약 포커스 |
| --- | --- | --- |
| `paper` | source_format=PDF + genre∈(paper, thesis, report) | 연구 목적·방법론·발견·학술 키워드 |
| `literature` | KDC 800~899 | 사건·인물 심리·문체·상징·정서 |
| `policy` | KDC 320~359 또는 "법령"·"훈령" 등 제목 키워드 | 조항 목적·규정·적용 범위·정의 |
| `book` (기본) | 그 외 | 핵심 질문·주장·개념·연관 키워드 |

### 1.7 자동 표지 생성 (FLUX.1-dev)

요약·테마·소개글을 LLM에게 주고 → 영문 이미지 프롬프트 생성 → FLUX 컨테이너에서 768×1152 JPEG 렌더 → MinIO `covers/{book_id}.jpg` 업로드. 표지가 없는 도서도 시각적으로 변별 가능하다.

```
PostgreSQL → cover_image_key, cover_prompt
프런트 표지 우선순위: ① FLUX 자동표지 → ② PDF 1p 캐시 → ③ PDF 1p 즉석 렌더
```

---

## 2. 시스템 아키텍처

### 2.1 전체 구성

```
사용자
  ↓
Nginx (Gateway :92)
  ├── /                  → Nuxt 3 (검색 UI, 도서 / 논문 두 모드)
  └── /api/              → FastAPI (:18002)
                            ├── /books/*        검색·도서·소개·추천이유·대화·표지·PDF
                            ├── /papers/*       논문 전용 검색·KCI 카탈로그 적재
                            └── /admin/*        현황·도서·섹션·청크 관리
```

### 2.2 데이터 수집 파이프라인

```
PDF 업로드 → MinIO 저장 (originals/{book_id}/)
  ↓
Celery Task: process_book_file
  │
  ├── ① 텍스트 추출 — 2티어 라우팅 (extractor.py)
  │     [1티어] OpenDataLoader v2 — 한컴·듀얼랩 하이브리드, 마크다운 + 표 + 그림 base64
  │     [2티어] VLM (Qwen3-VL-8B) — 페이지에 `[그림]` 검출 또는 50자 미만일 때만 선별 보완
  │              · `[그림]` 외 본문이 80자 이상 → diagram 프롬프트 (다이어그램 OCR)
  │              · 그렇지 않으면(스캔/TIF) → ocr 프롬프트 (전체 페이지 OCR)
  │
  ├── ①-b 그림 추출 (base64) → MinIO + book_figures
  │        앞 300자 / 뒤 300자 컨텍스트도 함께 저장 (도표·캡션 검색 대비)
  │
  ├── ② 메타데이터 보완 (xlsx 미적재 PDF)
  │     pdf_meta_extractor — OpenDataLoader 1-2페이지 → LLM JSON 파싱
  │     → title, authors, publisher, pub_date, abstract, keyword, language, url, genre
  │
  ├── ③ 섹션 분할 (3000~5000 토큰) → book_sections 저장
  │
  ├── ③-b 섹션별 요약 + 테마 키워드 병렬 생성 (LLM_SECTION_CONCURRENCY)
  │       문서 유형별 특화 프롬프트, SUMMARY: / THEMES: 구조화 출력
  │       → section.summary, section.themes 저장
  │
  ├── ④ 시맨틱 청킹 (chunker.py)
  │     문장 분리 → BGE-M3 임베딩 유사도 기반 경계 감지
  │     → min 128 ~ max 1024 토큰 → section_idx 매핑
  │
  ├── ⑤ Contextual 임베딩 + 메타 청크 생성
  │     본문 청크: "[핵심 테마]\n[섹션 요약]\n[본문]" 으로 임베딩 (저장은 원본)
  │     메타 청크: "제목: X | 기관: Y | 발행년도: Z | KDC: ... | 초록: ..." (chunk_idx=-1)
  │     → BGEM3FlagModel(return_dense, return_sparse)
  │     → Dense + Sparse + MARC 스칼라 필드 (publisher/corporate_author/pub_date/kdc) 저장
  │
  ├── ⑥ 도서 요약 + 테마 + 소개글 생성 (LLM 2회)
  │     summarize_book_from_sections — 검색용 SUMMARY/THEMES
  │     generate_book_introduction   — 사서 톤 자연어 소개 (400~600자)
  │
  └── ⑦ FLUX 표지 자동 생성
        cover_generator — LLM 영문 프롬프트 → FLUX 렌더 → MinIO 업로드
```

### 2.3 RAG 검색 파이프라인 (book / paper 공용)

```
사용자: "기획예산처 2024년 이후 보고서 찾아줘"
  ↓
① [병렬] 쿼리 재작성  (Gemma 3) — 의미 확장
   [병렬] 메타 필터 추출 (Gemma 3) — pub_year_from=2024, sort_by=None
   → Milvus expression 조립 (doc_scope + 메타 필터)
  ↓
② BGE-M3 → Dense + Sparse 동시 생성 (is_query=True)
  ↓
③ Milvus hybrid_search (RRFRanker(k=60))
   AnnSearchRequest(embedding,        COSINE)
   AnnSearchRequest(sparse_embedding, IP)
   → book 모드: 청크별 검색 결과를 book_id 단위로 그룹 (top_k×3, 날짜 정렬 시 ×4)
   → 메타 청크(chunk_idx=-1)도 점수 산정에 기여 (응답에서는 제거)
  ↓
④ Jina Reranker v2 (8K 컨텍스트) — 도서별 청크 내부 리랭킹
  ↓
⑤ 다중 매칭 부스팅 + 날짜 정렬 (필요 시)
  ↓
응답: 도서 + 청크 (도서 소개·표지·추천이유·대화는 별도 엔드포인트)
```

---

## 3. 기술 스택

| 구분 | 기술 | 역할 |
| --- | --- | --- |
| **LLM** | Gemma 3 12B (vLLM, 32K ctx) | 섹션·도서 요약, 쿼리 재작성, 메타 필터 추출, 추천 이유, 도서 대화, 메타 자동추출, 표지 프롬프트 |
| **VLM** | Qwen3-VL-8B (vLLM, max-model-len 32768) | 스캔본/다이어그램 페이지 보완 추출 |
| **Embedding** | BAAI/bge-m3 (BGEM3FlagModel) | Dense(1024차원) + Sparse 동시 |
| **Reranker** | jinaai/jina-reranker-v2 | Cross-Encoder 리랭킹 (8K) |
| **Image Gen** | FLUX.1-dev | 도서 표지 자동 생성 (768×1152 JPEG) |
| **PDF 추출** | OpenDataLoader v2 (1티어) + PyMuPDF (페이지 렌더링) | 마크다운 + 표 + 그림 base64 |
| **Vector DB** | Milvus 2.4.6 | Dense IVF_FLAT + Sparse INVERTED_INDEX + 스칼라 필터 |
| **RDB** | PostgreSQL 16 | 도서 메타 + 섹션 + 그림 + 검색 히스토리 |
| **Queue** | Redis 7 + Celery | 수집 비동기 (concurrency=2) |
| **Storage** | MinIO | 원본 PDF + 자동표지 + 썸네일 캐시 + 그림 |
| **Backend** | FastAPI | REST API + SSE 스트리밍 |
| **Frontend** | Nuxt 3 + Vue 3 | 도서/논문 듀얼 모드 UI + 인라인 채팅 + PDF.js 뷰어 |
| **Gateway** | Nginx | 라우팅 (:92) |
| **Infra** | Docker + Portainer | 컨테이너 관리 |
| **Server** | NVIDIA H200 140GB | GPU 서버 (LLM + VLM + FLUX + 임베딩) |

---

## 4. 데이터 설계

### 4.1 PostgreSQL 테이블

**library_catalog** — 도서·논문 통합 메타데이터 (MARC + MODS + KCI)

| 그룹 | 필드 |
| --- | --- |
| **MARC** | record_id, title, title_remainder, part_number, personal_author, corporate_author, publisher, pub_place, pub_date, extent, kdc, ddc, isbn, series_title, subject, keyword, note, language |
| **MODS** | abstract, url, uci, media_type, material_type, genre, access_condition, target_audience, digital_origin |
| **KCI 논문 전용** | grade, vol_issue, kci_citations, wos_citations |
| **메타** | source_format ('MARC' \| 'MODS' \| 'KCI'), cnts_id (PK) |
| **RAG 생성** | summary, themes, introduction, cover_image_key, cover_prompt, is_embedded |

**book_sections** — 섹션 원문 + 요약 + 테마

| 필드 | 설명 |
| --- | --- |
| book_id, section_idx | 복합 식별자 |
| full_text | 원문 |
| summary | LLM 섹션 요약 |
| themes | 섹션 테마 키워드 (쉼표 구분) |
| page_start, page_end, token_count | 메타 |

**book_figures** — 그림 메타 + 컨텍스트

| 필드 | 설명 |
| --- | --- |
| book_id, page_num, img_idx | 위치 |
| minio_key | `figures/{book_id}/p{page}_i{idx}.jpg` |
| before_context, after_context | 그림 앞/뒤 300자 (캡션·출처) |

**search_history** — 검색 히스토리

| 필드 | 설명 |
| --- | --- |
| session_id, query, mode, result, created_at | 세션 단위 검색 기록, 결과 JSON |

### 4.2 Milvus 컬렉션 (nl_lib_embeddings)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| chunk_id | VARCHAR PK | `{book_id}__{chunk_idx:04d}` |
| book_id, chunk_idx, section_idx | VARCHAR / INT16 | 식별·정렬 |
| text, page_start, page_end | VARCHAR / INT16 | 응답 표시용 |
| publisher, corporate_author, pub_date, kdc | VARCHAR | **스칼라 필터·정렬용** |
| embedding | FLOAT_VECTOR(1024) | BGE-M3 Dense (IVF_FLAT, COSINE) |
| sparse_embedding | SPARSE_FLOAT_VECTOR | BGE-M3 Sparse (SPARSE_INVERTED_INDEX, IP) |

> `chunk_idx == -1` 메타 청크는 응답에서 제외, 도서 점수 산정에만 사용.
> 도메인 분리는 `book_id like "KCI_FI%"` 로 KCI 논문과 도서를 구별한다.

### 4.3 MinIO 버킷 구조 (nl-lib-bucket)

```
originals/{book_id}/{filename}.pdf       — 원본 PDF
thumbnails/{book_id}.jpg                 — PDF 1페이지 썸네일 캐시
covers/{book_id}.jpg                     — FLUX 자동 생성 표지
figures/{book_id}/p{page}_i{idx}.jpg     — 그림 추출본
```

---

## 5. 프로젝트 구조

```
nl-lib/
├── docker-compose.yml
├── migrate_add_KCI.sql                  # KCI 논문 컬럼 마이그레이션
├── infra/vllm/Dockerfile                # 커스텀 vLLM 이미지 (gemma 서비스용)
│
├── app/                                  # FastAPI 백엔드
│   ├── main.py
│   ├── core/config.py
│   ├── api/
│   │   ├── book.py                       # 검색·수집·추천이유·대화·PDF·표지·비교
│   │   ├── paper.py                      # 논문 검색 + KCI 카탈로그 로드
│   │   ├── admin.py                      # 현황·관리 대시보드
│   │   └── health.py
│   ├── services/
│   │   ├── ingestion/
│   │   │   ├── extractor.py              # 2티어 (OpenDataLoader → VLM 선별)
│   │   │   ├── pdf_meta_extractor.py     # PDF 1-2p → LLM 메타 JSON 자동추출
│   │   │   ├── kci_loader.py             # KCI 논문 xlsx 파서
│   │   │   ├── xlsx_loader.py            # MARC/MODS xlsx 파서
│   │   │   ├── marc_parser.py / mods_parser.py
│   │   │   ├── chunker.py                # 시맨틱 청킹
│   │   │   ├── embedder.py               # BGE-M3 (dense+sparse)
│   │   │   ├── indexer.py                # Milvus hybrid_search + 스칼라 필터
│   │   │   ├── summarizer.py             # 섹션·도서 요약, doc_type 판별, 소개글
│   │   │   └── cover_generator.py        # LLM 프롬프트 → FLUX → MinIO
│   │   ├── search/
│   │   │   ├── pipeline.py               # 검색 통합 + 추천이유 SSE
│   │   │   ├── query_rewriter.py
│   │   │   ├── metadata_filter.py
│   │   │   ├── reranker.py
│   │   │   └── context_expander.py
│   │   └── chat/
│   │       └── book_chat.py              # 도서 단위 RAG 대화 + SSE
│   ├── models/
│   │   ├── book.py                       # library_catalog
│   │   ├── section.py                    # book_sections
│   │   ├── figure.py                     # book_figures
│   │   └── search_history.py
│   ├── schemas/book.py
│   ├── repositories/{book,section}.py
│   ├── workers/{celery_app,tasks}.py
│   └── db/postgres.py
│
└── frontend/                             # Nuxt 3
    ├── pages/
    │   ├── index.vue                     # 도서 검색 (세그먼티드 토글로 논문 이동) + 장바구니 패널
    │   └── papers.vue                    # 논문 검색 (자료유형/연도/학술지/언어 필터)
    ├── composables/
    │   └── useCart.ts                    # 장바구니 상태 (임시) — 담기/제거/목록
    └── components/
        ├── SearchInput.vue
        ├── TopResult.vue                 # Top 1 도서 + 추천이유 + 대화 + PDF 뷰어 + 장바구니 담기
        ├── BookCard.vue                  # 추천 도서 카드
        ├── BookCover.vue                 # 표지 (FLUX → 썸네일 폴백)
        ├── BookChat.vue                  # 도서 단위 RAG 대화창
        ├── ChatHistory.vue               # 검색 히스토리 사이드바
        ├── PdfViewer.vue                 # PDF.js iframe 모달
        └── CategoryAccordion.vue
```

---

## 6. API 엔드포인트

### 6.1 검색 / 도서

| Method | Path | 설명 |
| --- | --- | --- |
| POST | /api/books/search | 도서 의미 기반 검색 (book/chunk 모드) |
| POST | /api/books/reason/stream | 추천 이유 SSE 스트리밍 |
| POST | /api/books/chat/{cnts_id} | 도서 단위 RAG 대화 SSE |
| GET | /api/books/{cnts_id} | 도서 단건 조회 (소개·요약·테마 포함) |
| GET | /api/books/{cnts_id}/thumbnail | FLUX 표지 → PDF 썸네일 폴백 |
| GET | /api/books/{cnts_id}/pdf | 원본 PDF 스트리밍 (브라우저 PDF.js용) |
| GET | /api/books/history/{session_id} | 세션 검색 기록 |

### 6.2 논문

| Method | Path | 설명 |
| --- | --- | --- |
| POST | /api/papers/search | 논문 검색 (`doc_scope=paper`로 KCI만 필터) |
| POST | /api/papers/catalog/load | KCI xlsx 메타데이터 적재 |

### 6.3 수집

| Method | Path | 설명 |
| --- | --- | --- |
| POST | /api/books/ingest/upload | 단일 PDF → MinIO → Celery |
| POST | /api/books/ingest/upload/batch | 다중 PDF 일괄 업로드 |
| POST | /api/books/ingest/batch | MinIO 기존 파일 배치 수집 |
| POST | /api/books/catalog/load | MARC/MODS xlsx 메타 적재 |
| GET | /api/books/ingest/{task_id} | Celery 태스크 상태 |
| POST | /api/books/ingest/{task_id}/cancel | 인덱싱 태스크 취소 (revoke + 락 해제 + state=canceled) |
| POST | /api/books/{cnts_id}/retry | 실패/취소 도서 재시도 (저장된 source_key 로 재디스패치) |
| GET | /api/books/{cnts_id}/ingest-status | 인덱싱 상태 폴링 (state, task_id, started/finished, error) |
| POST | /api/books/compare/extract | fitz / VLM / OpenDataLoader 추출 비교 |

### 6.4 관리

| Method | Path | 설명 |
| --- | --- | --- |
| GET | /api/admin/status | 도서·섹션·Milvus·MinIO 통계 |
| GET | /api/admin/books | 도서 목록 (페이지네이션) |
| GET | /api/admin/books/{cnts_id}/sections | 섹션 목록 |
| GET | /api/admin/books/{cnts_id}/chunks | Milvus 청크 목록 |
| GET | /api/admin/minio/files | MinIO 파일 목록 |

---

## 7. 인프라 구성

### 7.1 Docker Compose 서비스

| 서비스 | 이미지 | 호스트 포트 | 비고 |
| --- | --- | --- | --- |
| etcd | quay.io/coreos/etcd:v3.5.0 | - | Milvus 메타데이터 |
| minio | minio/minio:latest | 21000, 21001 | 원본·표지·썸네일·그림 |
| milvus | milvusdb/milvus:v2.4.6 | - | 벡터 DB |
| postgres | postgres:16-alpine | 15432 | RDB |
| redis | redis:7-alpine | 16379 | Celery broker/backend |
| gemma | vllm/vllm-openai (커스텀) | 18080 | Gemma 3 12B (텍스트 LLM) — `--max-model-len 32768` |
| vllm | vllm/vllm-openai:latest-cu130 | 18081 | Qwen3-VL-8B (VLM) — `--max-model-len 32768` |
| flux | landsoftdocker/nl-lib-flux:latest | 18090 | FLUX.1-dev 표지 생성 |
| fastapi | landsoftdocker/nl-lib-fastapi:latest | 18002 | API |
| celery-worker | landsoftdocker/nl-lib-fastapi:latest | - | 수집 워커 (concurrency=2) |
| nuxt | landsoftdocker/nl-lib-nuxt:latest | - | 프론트 |
| gateway | nginx:alpine | 92 | 라우팅 |

> 텍스트 LLM(Gemma 3 12B)을 본 스택의 `gemma` 서비스로 이관 (`LLM_BASE_URL=http://gemma:8000/v1`). 개발 환경에서는 `host.docker.internal:18080` 외부 서버로 분리 가능 (`core/config.py` 기본값).
> PaddleOCR은 비활성화 — OpenDataLoader + VLM 조합으로 대체.

### 7.2 GPU 메모리 현황 (H200 140GB, 대략치)

| 프로세스 | VRAM |
| --- | --- |
| nl-lib vLLM (Qwen3-VL-8B, util 0.3) | ~22GB |
| FLUX.1-dev | ~20GB |
| nl-lib FastAPI (BGE-M3 + Jina) | ~2.4GB |
| nl-lib Celery (BGE-M3 + Jina) | ~2.4GB |
| Gemma 3 12B (vLLM) | ~24GB |
| **합계** | **~72GB / 143GB** |

---

## 8. 운영 스크립트

### 8.1 PDF 일괄 업로드 (PowerShell)

```powershell
$outputDir = "C:\Users\LANDSOFT\Downloads\output"
$apiUrl    = "http://211.219.26.15:18002/api/books/ingest/upload"
foreach ($pdf in (Get-ChildItem -Path $outputDir -Recurse -Filter "*.pdf")) {
    curl.exe -X POST $apiUrl -F "file=@$($pdf.FullName)" --silent --show-error
}
```

### 8.2 인덱싱 중단 & 큐 비우기

```bash
# 컨테이너 내부 (Portainer 콘솔)
celery -A workers.celery_app inspect active        # 실행 중 태스크 PID 확인
kill -9 <pid>                                       # 또는: celery control shutdown
celery -A workers.celery_app purge -f -Q ingestion,default

# 호스트에서 컨테이너 자체 재생성
docker compose stop celery-worker && docker compose rm -f celery-worker
docker exec nl-lib-redis redis-cli FLUSHDB         # (선택) 큐 완전 초기화
docker compose up -d celery-worker
```

### 8.3 재인덱싱 (Milvus 전체 드롭 → 재수집)

```bash
docker exec nl-lib-fastapi python -c "
from pymilvus import connections, utility
connections.connect(host='milvus', port='19530')
utility.drop_collection('nl_lib_embeddings')
"
docker exec nl-lib-postgres psql -U admin -d nl_lib -c "UPDATE library_catalog SET is_embedded = false;"

docker exec nl-lib-fastapi python -c "
from workers.tasks import process_from_minio
from db.postgres import SyncSessionLocal
from models.book import Book
db = SyncSessionLocal()
for (cnts_id,) in db.query(Book.cnts_id).filter(Book.is_embedded == False).all():
    process_from_minio.delay(cnts_id, f'originals/{cnts_id}/{cnts_id}.pdf')
"
```

### 8.4 KCI 컬럼 마이그레이션 (Alembic 도입 이전 수동 패치)

```bash
docker exec -i nl-lib-postgres psql -U admin -d nl_lib < migrate_add_KCI.sql
```

### 8.5 Alembic 마이그레이션 운영

```bash
# 작업 디렉터리는 항상 app/ — alembic.ini 가 거기 있음
cd /app

# 현재 적용된 리비전 확인
alembic current

# 운영 DB 첫 도입 시 (이미 베이스 스키마는 존재) — 베이스라인 stamp
alembic stamp 0001_baseline

# 최신까지 적용
alembic upgrade head

# 새 마이그레이션 생성 (모델 변경 후)
alembic revision --autogenerate -m "add some column"

# 컨테이너에서 일괄 실행
docker exec -w /app nl-lib-fastapi alembic upgrade head
```

> 0002_add_ingest_state 는 `is_embedded=true` 도서를 `ingest_state='embedded'` 로 자동 백필한다.

### 8.6 인덱싱 취소 / 재시도

```bash
# 진행 중 태스크 취소 (Celery revoke + Redis 락 해제 + state=canceled)
curl -X POST http://localhost:18002/api/books/ingest/<task_id>/cancel

# 실패/취소된 도서 재시도 (저장된 ingest_source_key 로 재디스패치)
curl -X POST http://localhost:18002/api/books/<cnts_id>/retry

# 인덱싱 상태 폴링
curl http://localhost:18002/api/books/<cnts_id>/ingest-status
```

```bash
# 진행 중 / 실패 도서 일괄 조회
docker exec nl-lib-postgres psql -U admin -d nl_lib -c "
  SELECT cnts_id, ingest_state, ingest_task_id, ingest_error
  FROM library_catalog
  WHERE ingest_state IN ('processing','failed','pending','canceled')
  ORDER BY ingest_started_at DESC LIMIT 20;
"
```

---

## 9. 도커라이징 과정에서 해결한 문제들

| 문제 | 원인 | 해결 |
| --- | --- | --- |
| `Transformers does not recognize gemma4` | 공식 vLLM 이미지의 transformers가 Gemma 4 미지원 | 커스텀 vLLM 이미지로 transformers 최신 설치 |
| `Qwen2Tokenizer has no attribute all_special_tokens_extended` | transformers ↔ vLLM 버전 충돌 | transformers + tokenizers + huggingface_hub만 업그레이드 |
| `hanja` 빌드 실패 (`No module named pkg_resources`) | kss 의존성 빌드 격리 문제 | `--no-build-isolation` |
| `kss idioms.txt not found` | kss 데이터 파일 누락 | kss 제거, 정규식 fallback |
| `pymilvus marshmallow` 충돌 | 의존성 버전 불일치 | 버전 고정 |
| VLM 400 Bad Request (스캔 PDF) | DPI=300 PNG가 Qwen3-VL `max-model-len 32768` 초과 | extractor에서 1568px 상한 + DPI 150 + JPEG q=85 로 다운스케일 (필요 시 재적용) |
| Celery 태스크 중단 불가 | `control shutdown`이 통신 끊김으로 응답 안 함 | worker PID 직접 `kill -9`, 또는 컨테이너 재생성 |

---

## 10. 앞으로 고치면 좋을 것 (Roadmap)

현재 운영 중 발견된 약점과, 차기 작업에서 다루면 좋을 항목들을 우선순위가 높은 순으로 정리한다.

### 10.1 수집 파이프라인 안정성

- ✅ **태스크 중복 실행 방지** (2026-05-19) — `core/lock.py` 에 Redis 기반 `BookLock` (SETNX + TTL 3600s + Lua 토큰 검증) 도입. `process_book_file` 진입 시 `book_id` 단위로 락 획득, 이미 처리 중이면 즉시 `skipped` 반환.
- ✅ **재인덱싱 시 멱등성** (2026-05-19) — `library_catalog.ingest_state` 컬럼 추가 (`pending`/`processing`/`embedded`/`failed`/`canceled`). 진입·완료·실패·취소 시점에 상태 전이 + 시작/종료 시각·에러 사유·source MinIO key 기록.
- ✅ **태스크 취소·재시도 API** (2026-05-19) — `POST /api/books/ingest/{task_id}/cancel` (Celery revoke SIGTERM + 락 강제 해제 + 상태=canceled), `POST /api/books/{cnts_id}/retry` (저장된 `ingest_source_key` 로 재디스패치, processing 중이면 409), `GET /api/books/{cnts_id}/ingest-status` (폴링용).
- ✅ **DB 마이그레이션 관리** (2026-05-19) — Alembic 도입 (`app/alembic.ini`, `app/alembic/`). `0001_baseline` (no-op 기준점) + `0002_add_ingest_state` (신규 컬럼). 운영 절차는 §8.5 참조.
- ✅ **요약 컨텍스트 오버플로 방지** (2026-06-18) — 도서 요약/소개 입력이 `SUMMARIZER_MAX_INPUT_CHARS`(기본 14000자)를 넘으면 앞부분 절단 대신 **균등 샘플링**(앞·중간·뒤 고루)으로 전체 맥락 보존. `_combine_sections` + `test_summarizer.py` 회귀 테스트.
- ✅ **상수 환경변수화** (2026-06-18) — 하드코딩 상수를 `core/config.py` Settings + `.env.example` 로 외부화 (검색 배수·요약 타임아웃·Milvus·FLUX·배치/락 등). 배포는 docker-compose env / Portainer 스택 env 우선.
- ✅ **텍스트 LLM 스택 내 이관** (2026-06-18) — Gemma 3 12B 를 외부 서버에서 본 compose 스택의 `gemma` 서비스로 이관. `LLM_BASE_URL`로 외부 분리도 유지.
- **VLM 400 재발 방지** — 이미지 크기 가드(1568px / JPEG q85) 가 린터 변경으로 되돌아간 적 있음. 회귀 방지 테스트 + 환경변수로 DPI/해상도 외부화.
- **`process_book_file` 멱등성 깊이 확장** — Milvus `delete(book_id == X)` 는 들어가 있지만, `book_sections` / `book_figures` 도 동일하게 인덱싱 시작부에서 정리해야 부분 잔류 방지. 현재는 sections 만 정리됨.

### 10.2 검색 품질

- **도서 검색의 논문 노출** — `/api/books/search`가 `doc_scope=all` 기본이라 KCI 논문이 도서 결과에 섞임. book.py에서 `doc_scope="book"`로 명시.
- **그림(figure) 검색 연동** — book_figures 데이터를 검색에 활용 못 하고 있음. 그림의 before/after_context 를 별도 청크로 인덱싱 또는 별도 그림 검색 엔드포인트.
- **한국어 특화 임베더 비교** — BGE-M3 외에 KURE, jhgan/ko-sroberta 등과 도서관 도메인 RecallExample 비교 평가.
- **리랭커 업그레이드 옵션** — Jina v2 외에 BGE-Gemma 시리즈 8K 컨텍스트 모델 비교.
- **메타 필터 추출 신뢰도** — `metadata_filter.py`가 LLM JSON 파싱 의존이라 가끔 실패. JSON 모드 강제 + 정규식 fallback 강화.

### 10.3 사용자 경험

- **요약 활용 콘텐츠 확장 (계획)** — 저장된 요약·섹션 데이터를 활용해 검색 질의에 대한 **① 추천 이유 ② 읽은 후 효과 ③ 줄거리**를 함께 표출. 줄거리(`plot`)는 인덱싱 시 사전 생성·저장, 효과·추천이유는 질의 시 실시간 생성(하이브리드). 설계 상세는 별도 계획 문서 참조.
- **다중 도서 큐레이션 (계획)** — 한 권이 아닌 **최대 3권**의 요약·테마·줄거리를 한 번의 LLM 호출로 묶어 컬렉션 소개문 + 책별 추천 한 줄(혜택 문구형) 생성. `POST /api/books/curate`.
- **"내 상황에 맞는 책 추천" 시나리오 (계획)** — 미리 지정한 시나리오(위로가 필요할 때 / 심리적 단단함이 필요할 때 / 늦은 밤 잠이 오지 않을 때 / 흥미진진한 역사 등) 버튼 클릭 → 고정 후보군 또는 동적 검색으로 확보한 후보에서 AI가 3권 큐레이션. 시나리오 정의는 우선 설정 파일(YAML), 추후 DB화. `GET /api/scenarios`, `POST /api/scenarios/{key}/recommend`.
- **장바구니 (임시 도입, 2026-06-18)** — 관심 도서 담기/목록 (`composables/useCart.ts`). 현재 클라이언트 상태만 유지하는 임시 구현 — 영속화·세션 동기화는 후속 과제.
- **도서 상세 페이지** — 현재 검색 결과에서 도서별 상세 뷰가 없음. 섹션 목차, 그림 갤러리, 인용 청크 미리보기 페이지 추가.
- **논문 상세 페이지** — papers.vue도 동일하게 인용 정보(`kci_citations`, `wos_citations`) 강조 페이지 필요.
- **대용량 결과 가상화** — 300건 이상 결과 시 페이지 끊김. Virtual scrolling (`vue-virtual-scroller`) 도입.
- **검색 히스토리 동기화** — 현재 sessionStorage 기반. session_id로 백엔드 동기화는 되어 있지만 다중 디바이스 미지원. 로그인 도입 시 정리.
- **인덱싱 진행률 UI** — 관리 화면에서 Celery 태스크별 진행률 (페이지 X/Y) 표시.

### 10.4 모니터링 / 운영

- **구조화 로깅** — 현재 평문 로그. structlog + JSON 출력으로 전환 → ELK/Loki 수집 용이.
- **메트릭 대시보드** — 검색 latency, 리랭킹 성공률, LLM 토큰 사용량, GPU VRAM, Milvus QPS를 Grafana로.
- **Sentry 연동** — Celery 태스크 실패·LLM 타임아웃 추적.
- **헬스체크 강화** — 현재 fastapi `/health`는 단순 ping. Milvus·Redis·LLM·VLM·FLUX 의존성 체크 포함하는 `/health/deep`.

### 10.5 코드 품질

- **테스트 부재** — pytest 기반 단위·통합 테스트 추가. 특히 `_parse_summary_themes`, `detect_doc_type`, `_build_milvus_expr` 등 순수함수부터.
- **schemas/book.py 비대화** — 도서·청크·논문·대화·추천 요청·응답이 한 파일. 도메인별 분리(`book.py`, `search.py`, `chat.py`).
- **Celery 태스크 시그니처 통일** — `process_book_file`, `process_from_minio`, `ingest_batch`, `ingest_books_batch` 등 유사 태스크가 산재. 단일 진입점 + 옵션 dict로 통합.
- **Frontend 타입 정의 통합** — `~/types/search.ts` 외 곳곳에 인라인 타입 산재. shared types로 통합.

### 10.6 모델·인프라

- **Reranker GPU 분리** — FastAPI + Celery 양쪽에서 Reranker 로드되어 VRAM 중복. 별도 reranker 서비스 컨테이너 분리.
- **MinIO → S3 호환 마이그레이션** — 클라우드 이전 대비 endpoint·credential 외부화.
- **PostgreSQL 백업 자동화** — 현재 미설정. `pg_dump` cron + MinIO 업로드.

---

## 11. 참고 자료

- Gemma 3 12B: <https://huggingface.co/google/gemma-3-12b-it>
- Qwen3-VL: <https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct>
- BGE-M3: <https://huggingface.co/BAAI/bge-m3>
- Jina Reranker v2: <https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual>
- FLUX.1-dev: <https://huggingface.co/black-forest-labs/FLUX.1-dev>
- OpenDataLoader PDF: <https://github.com/opendataloader-project/opendataloader-pdf>
- vLLM: <https://github.com/vllm-project/vllm>
- Milvus Hybrid Search: <https://milvus.io/docs/multi-vector-search.md>
- 국립중앙도서관: <https://www.nl.go.kr>
- KCI (한국학술지인용색인): <https://www.kci.go.kr>
