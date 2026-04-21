# NL-Lib — 국립중앙도서관 의미 기반 검색 시스템

**작성일:** 2026-04-16  
**작성자:** 안정현  
**프로젝트명:** NL-Lib (National Library — Semantic Search)

---

## 왜 일반 RAG로는 부족한가

대부분의 RAG 시스템은 세 가지 구조적 한계를 가진다.

| 한계                | 일반 RAG                                                                          | NL-Lib                                                                  |
| ------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **어휘 매칭 실패**  | Dense 벡터만 사용 → "기획예산처", "국가재정법" 같은 고유명사를 의미 공간에서 놓침 | BGE-M3 **Dense + Sparse 하이브리드** → 의미 + 어휘 동시 검색            |
| **메타데이터 무시** | 본문 텍스트만 임베딩 → "조달청의 2024년 최신 자료"처럼 구조적 조건은 처리 불가    | MARC/MODS 메타데이터를 **두 레이어**로 분리 활용 (임베딩 + 스칼라 필터) |
| **맥락 없는 청크**  | 잘린 문단만 임베딩 → "이 문단이 책의 어떤 맥락인지"가 벡터에 없음                 | **Contextual Chunking** — 섹션 요약을 청크 임베딩에 주입                |

이 세 문제를 모두 해결하기 위해 설계한 것이 NL-Lib이다.

---

## 1. 차별화 포인트

### 1.1 Dense + Sparse 하이브리드 검색 (BGE-M3)

일반 RAG는 Dense 벡터(의미 유사도) 하나만 쓴다.  
BGE-M3의 Sparse 벡터(어휘 가중치)를 함께 쓰면 **고유명사·전문용어 매칭**이 근본적으로 달라진다.

```
Dense  : "기획예산처 예산안" → 의미 공간에서 "재정 정책 문서"와 가까운 것들
Sparse : "기획예산처"의 토큰 ID → 해당 토큰이 포함된 문서를 정확히 타격

두 결과를 RRFRanker(k=60)로 합산 → 의미도 맞고, 명칭도 맞는 문서가 상위
```

도서관 데이터는 기관명·법령명·인명처럼 Dense가 취약한 고유명사가 핵심 검색어다.  
Sparse 없이는 "기획예산처 자료 찾아줘"를 절대 정확히 처리할 수 없다.

```python
# Milvus hybrid_search: dense + sparse 동시 검색
dense_req  = AnnSearchRequest(data=[query_dense],  anns_field="embedding",        ...)
sparse_req = AnnSearchRequest(data=[query_sparse], anns_field="sparse_embedding", ...)
results = col.hybrid_search(reqs=[dense_req, sparse_req], rerank=RRFRanker(k=60), ...)
```

---

### 1.2 메타데이터 기반 검색 — 이중 전략

"조달청의 가장 최신 자료 찾아줘"라는 쿼리를 처리하려면 두 가지가 모두 필요하다.

#### ① 메타데이터 전용 임베딩 청크 (chunk_idx = -1)

```
메타 텍스트: "제목: X | 기관: 조달청 | 출판사: Y | 발행년도: 2024 | KDC: 320 | ..."
→ 본문 청크와 동등하게 Milvus에 저장·검색
```

본문 청크에 메타데이터를 섞으면 모든 청크가 같은 메타 prefix를 가져 임베딩이 균질화된다.  
**메타 청크를 분리**함으로써 본문 청크는 순수하게 내용 기반, 메타 청크는 기관·저자·주제 매칭 전담.

#### ② Milvus 스칼라 필드 expression 필터

```python
# "2023년 이후" → Milvus pre-filter (벡터 검색 전 적용)
expr = 'pub_date >= "2023" && pub_date < "2025"'

# LLM이 쿼리에서 조건을 추출 (metadata_filter.py)
# "기획예산처 가장 최근 자료" → sort_by="recent"
# "2020년 이후 환경부 정책" → pub_year_from=2020, sort_by=None
```

날짜 정렬 요청 시 후보 풀을 `top_k × 4`로 확장 후 날짜 정렬 → `top_k`로 축소.  
(후보가 적으면 "가장 최근"인 책이 벡터 점수로 탈락해 있을 수 있기 때문)

---

### 1.3 Contextual Chunking — 맥락을 벡터에 주입

BGE-M3의 512토큰 한계 안에서 문맥을 살리기 위해 섹션 요약을 청크 임베딩에 주입.

```
임베딩 입력 (저장은 원본 텍스트):
  "[섹션 요약] 이 섹션은 주인공 영혜가 채식을 통해
   가부장적 폭력에 저항하는 과정을 다룸
   [본문] 채식주의자는 폭력에 맞서는 방식으로..."

→ "채식 레시피" 쿼리에는 매칭 안 됨
→ "폭력에 저항하는 소설" 쿼리에 올바르게 매칭
```

이를 위해 **계층적 요약 파이프라인**을 먼저 수행한다:

1. 섹션(3000~5000토큰) → LLM 섹션 요약 (병렬 8개, asyncio.Semaphore)
2. 섹션 요약을 청크 임베딩 prefix로 활용 (저장은 원본 유지)
3. 전체 섹션 요약 합산 → LLM 도서 요약 (126K 컨텍스트 1회 호출)

---

### 1.4 추천 이유 vs 도서 소개 — 콘텐츠 분리

일반 RAG: LLM이 책을 설명하는 텍스트 1개 생성  
NL-Lib: **두 가지를 목적에 맞게 분리**

| 표시 항목        | 내용                                      | 생성 시점                   |
| ---------------- | ----------------------------------------- | --------------------------- |
| **도서 소개**    | 이 책이 어떤 책인지 (책의 일반적 설명)    | 인덱싱 시 1회 생성, DB 저장 |
| **AI 추천 이유** | 이 질의에 이 책의 어떤 부분이 답이 되는지 | 검색 시 실시간 생성         |

추천 이유 프롬프트에 "책의 일반적인 소개는 도서 소개란에 이미 표시됩니다. 반복하지 마세요"를 명시 → 두 섹션이 같은 내용이 되는 현상 방지.

---

### 1.5 문서 유형별 특화 요약

KDC 분류와 제목 키워드로 문서 유형을 자동 판별, 유형별 최적 프롬프트 적용.

| 유형          | 판별 기준                             | 요약 프롬프트 포커스               |
| ------------- | ------------------------------------- | ---------------------------------- |
| `literature`  | KDC 800~899 또는 "소설"·"시집" 키워드 | 핵심 사건·인물 심리·문체·정서·상징 |
| `policy`      | KDC 320~359 또는 "법령"·"정책" 키워드 | 조항 목적·규정·적용 범위·정의      |
| `book` (기본) | 그 외                                 | 핵심 질문·주장·개념·연관 키워드    |

---

## 2. 시스템 아키텍처

### 2.1 전체 구성

```
사용자
  ↓
Nginx (Gateway :92)
  ├── /         → Nuxt 3 (검색 UI)
  └── /api/     → FastAPI (:18002)
                    ├── 검색 파이프라인 (실시간)
                    ├── 관리 API
                    └── 수집 파이프라인 (Celery 비동기)
```

### 2.2 데이터 수집 파이프라인

```
PDF 업로드 → MinIO 저장 (originals/{book_id}/)
  ↓
Celery Task: process_book_file
  │
  ├── ① 텍스트 추출
  │     fitz(PyMuPDF): 디지털 PDF (글자 수 > 50/페이지)
  │     Gemma 4 VLM:   스캔본 fallback
  │
  ├── ② 섹션 분할 (3000~5000 토큰 단위)
  │     → PostgreSQL book_sections 저장
  │
  ├── ②-b 섹션별 요약 병렬 생성 (asyncio.Semaphore(8))
  │     문서 유형 자동 분류 (KDC + 제목 키워드)
  │     → 유형별 특화 프롬프트로 섹션 요약 생성
  │     → book_sections.summary 저장
  │
  ├── ③ 시맨틱 청킹
  │     문장 분리 → BGE-M3 임베딩 유사도로 의미 경계 감지
  │     → min 128 ~ max 1024 토큰 제약 → section_idx 매핑
  │
  ├── ④ Contextual 임베딩 + 메타 청크 생성
  │     본문 청크: "[섹션 요약] {summary}\n[본문] {chunk.text}" 로 임베딩
  │     메타 청크: "제목: X | 기관: Y | 발행년도: Z | ..." (chunk_idx=-1)
  │     → BGEM3FlagModel.encode(return_dense=True, return_sparse=True)
  │     → Dense + Sparse 벡터 쌍을 Milvus에 저장
  │
  └── ⑤ 도서 요약 생성 (1회)
        섹션 요약 전체 합산 → Gemma 4 (126K 활용)
        → PostgreSQL library_catalog.summary 업데이트
```

### 2.3 RAG 검색 파이프라인 (book 모드)

```
사용자 입력: "기획예산처 가장 최근 자료 찾아줘"
  ↓
① [병렬 실행]
   Query Rewriter (Gemma 4)  : 의미 확장 쿼리 생성
   MetadataFilter (Gemma 4)  : sort_by="recent" 추출 → 후보 풀 4× 확장
  ↓
② BGE-M3 → Dense 벡터 + Sparse 어휘 벡터 동시 생성
  ↓
③ Milvus 하이브리드 검색
   AnnSearchRequest(embedding,        COSINE)  — 의미 유사도
   AnnSearchRequest(sparse_embedding, IP)      — 어휘 매칭
   → RRFRanker(k=60) 합산 → 도서별 청크 그룹핑
   (메타 청크 포함 → 기관명·발행연도 조건도 도서 발견에 기여)
  ↓
④ Jina Reranker v2 (8K 컨텍스트) — 도서별 청크 내부 리랭킹
  ↓
⑤ 날짜 정렬 (sort_by 있을 때)
   pub_date 스칼라 기준 Python 재정렬 → top_k 축소
  ↓
⑥ 추천 이유 생성 (상위 3권 병렬)
   book.summary (DB) + 상위 매칭 청크 3개 → Gemma 4
   "이 질의에 이 책의 어떤 부분이 답인지" (일반 소개 중복 금지)
  ↓
결과: 도서 정보 + AI 추천 이유 + 도서 소개(인덱싱 시 생성) + 관련 구절
```

---

## 3. 기술 스택

| 구분          | 기술                         | 역할                                                               |
| ------------- | ---------------------------- | ------------------------------------------------------------------ |
| **LLM**       | Gemma 4 E4B (vLLM, 126K ctx) | 섹션 요약·도서 요약·쿼리 재작성·메타 필터 추출·추천 이유·VLM OCR   |
| **Embedding** | BAAI/bge-m3 (BGEM3FlagModel) | Dense(1024차원) + Sparse(어휘 가중치) 동시 생성                    |
| **Reranker**  | jinaai/jina-reranker-v2      | Cross-Encoder 리랭킹 (8K 컨텍스트, 긴 도서 청크 처리)              |
| **Vector DB** | Milvus 2.4.6                 | Dense IVF_FLAT + Sparse INVERTED_INDEX, 스칼라 필터, hybrid_search |
| **RDB**       | PostgreSQL 16                | 도서 메타 + 섹션 원문 + 섹션 요약 + 도서 요약                      |
| **Queue**     | Redis 7 + Celery             | 수집 비동기 처리 (concurrency=2)                                   |
| **Storage**   | MinIO                        | 원본 PDF + 썸네일 캐시                                             |
| **Backend**   | FastAPI                      | REST API                                                           |
| **Frontend**  | Nuxt 3                       | 검색 UI                                                            |
| **Gateway**   | Nginx                        | 라우팅 (:92)                                                       |
| **Infra**     | Docker + Portainer           | 컨테이너 관리                                                      |
| **Server**    | NVIDIA H200 140GB            | GPU 서버                                                           |

### 3.1 리랭커 선정 근거 (Jina Reranker v2)

| 항목          | bge-reranker-v2-m3 | **Jina Reranker v2** |
| ------------- | ------------------ | -------------------- |
| 파라미터      | ~568M              | ~278M                |
| 컨텍스트      | 512 토큰           | **8192 토큰**        |
| 속도 (20청크) | ~0.5초             | ~0.3초               |
| VRAM          | ~1.5GB             | ~0.8GB               |

도서 원문 청크가 긴 경우가 많아 8K 컨텍스트 지원이 결정적 요인.

### 3.2 LLM 선정 근거 (Gemma 4 E4B)

- **126K 컨텍스트**: 섹션 전체를 LLM에 전달 가능, 섹션 요약 합산으로 도서 전체 요약 가능
- **멀티모달(비전+텍스트)**: 스캔 PDF VLM OCR fallback
- **4B 파라미터**: H200에서 다른 서비스와 GPU 공유 가능 (~22GB VRAM, `gpu_memory_utilization 0.3`)
- vLLM OpenAI 호환 API → 추후 한국어 특화 모델로 교체 용이

---

## 4. 데이터 설계

### 4.1 PostgreSQL 테이블

**library_catalog** — 도서 메타데이터 (MARC 기준, MODS 보완)

| 필드                                        | 설명                                               |
| ------------------------------------------- | -------------------------------------------------- |
| cnts_id                                     | PK (CSV 기준)                                      |
| title, personal_author, publisher, pub_date | 서지 정보                                          |
| kdc                                         | 한국십진분류 (문서 유형 판별 + Milvus 스칼라 필터) |
| subject, keyword, abstract                  | 주제·키워드·초록                                   |
| summary                                     | LLM 생성 도서 요약 (섹션 요약 합산 기반)           |
| is_embedded                                 | 수집 완료 여부                                     |

**book_sections** — 도서 원문 섹션

| 필드                  | 설명                                            |
| --------------------- | ----------------------------------------------- |
| book_id               | = cnts_id                                       |
| section_idx           | 섹션 순번                                       |
| full_text             | 원문 전체                                       |
| summary               | LLM 생성 섹션 요약 (Contextual 임베딩 prefix용) |
| page_start / page_end | 페이지 범위                                     |
| token_count           | 토큰 수                                         |

### 4.2 Milvus 컬렉션 (nl_lib_embeddings)

| 필드                  | 타입                | 설명                                                  |
| --------------------- | ------------------- | ----------------------------------------------------- |
| chunk_id              | VARCHAR (PK)        | `{book_id}__{chunk_idx:04d}` (메타 청크는 `__-001`)   |
| book_id               | VARCHAR             | = cnts_id                                             |
| chunk_idx             | INT16               | 청크 순번 (`-1` = 메타데이터 전용 청크)               |
| section_idx           | INT16               | 소속 섹션 포인터                                      |
| text                  | VARCHAR             | 원본 청크 텍스트 (표시용)                             |
| page_start / page_end | INT16               | 페이지 범위                                           |
| publisher             | VARCHAR             | 출판사 (스칼라 필터용)                                |
| corporate_author      | VARCHAR             | 기관 저자 (스칼라 필터용)                             |
| pub_date              | VARCHAR             | 발행연도 "YYYY" (날짜 필터·정렬용)                    |
| kdc                   | VARCHAR             | KDC 분류 (스칼라 필터용)                              |
| embedding             | FLOAT_VECTOR(1024)  | BGE-M3 Dense (IVF_FLAT, COSINE)                       |
| sparse_embedding      | SPARSE_FLOAT_VECTOR | BGE-M3 Sparse 어휘 가중치 (SPARSE_INVERTED_INDEX, IP) |

> `chunk_idx=-1` 메타데이터 청크: API 응답에서 제외, 도서 점수 산정에만 사용.

### 4.3 MinIO 버킷 구조 (nl-lib-bucket)

```
originals/{book_id}/{filename}.pdf   — 원본 PDF
thumbnails/{book_id}.jpg             — PDF 1페이지 썸네일 캐시
```

### 4.4 데이터 흐름

```
엑셀 (MARC/MODS)  →  library_catalog (cnts_id, publisher, pub_date, kdc, ...)
                              ↑
원본 PDF  →  book_sections (full_text, summary)
                    ↑
              Milvus chunks
                ├── 본문 청크 × N  (contextual dense+sparse 임베딩, chunk_idx ≥ 0)
                └── 메타 청크 × 1  (MARC/MODS 전체 필드 텍스트, chunk_idx = -1)
                      + 스칼라 필드: publisher, corporate_author, pub_date, kdc
```

---

## 5. 프로젝트 구조

```
nl-lib/
├── docker-compose.yml
├── .env
├── infra/
│   └── vllm/Dockerfile              # 커스텀 vLLM (Gemma 4 지원)
│
├── app/                              # FastAPI 백엔드
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── deps.py
│   ├── api/
│   │   ├── book.py                   # 검색 + 수집 + 썸네일 + CRUD
│   │   ├── admin.py                  # 현황 대시보드, 도서·섹션·청크 목록
│   │   └── health.py
│   ├── services/
│   │   ├── ingestion/
│   │   │   ├── extractor.py          # fitz → VLM fallback OCR
│   │   │   ├── chunker.py            # 시맨틱 청킹 (BGE-M3 유사도 경계)
│   │   │   ├── embedder.py           # BGEM3FlagModel → (dense, sparse) 튜플 반환
│   │   │   ├── indexer.py            # Milvus 저장·hybrid_search·RRFRanker
│   │   │   └── summarizer.py         # 섹션 요약 / 도서 요약 / 문서 유형 판별
│   │   └── search/
│   │       ├── query_rewriter.py     # 쿼리 의미 확장
│   │       ├── metadata_filter.py    # 날짜·정렬 조건 LLM 추출 (pub_year_from/to, sort_by)
│   │       ├── reranker.py           # Jina Reranker v2
│   │       ├── context_expander.py   # 원문 섹션 확장 (126K 예산)
│   │       └── pipeline.py           # 검색 파이프라인 통합 조율
│   ├── models/
│   │   ├── book.py                   # library_catalog ORM
│   │   └── section.py                # book_sections ORM
│   ├── schemas/book.py
│   ├── repositories/
│   │   ├── book.py
│   │   └── section.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks.py                  # 수집 파이프라인 (섹션 요약 병렬 포함)
│   └── db/postgres.py
│
└── frontend/                         # Nuxt 3
    ├── pages/index.vue               # 검색 메인 (랜딩 → 결과 페이지)
    └── components/
        ├── SearchInput.vue           # 검색 입력창
        ├── TopResult.vue             # Top 1 도서 (AI 추천 이유 + 도서 소개 + 메타)
        ├── BookCard.vue              # 추천 도서 카드 (클릭 → NL 제목 검색)
        └── BookCover.vue             # PDF 썸네일 (오류 시 placeholder)
```

---

## 6. API 엔드포인트

### 검색 / 도서

| Method | Path                           | 설명                               |
| ------ | ------------------------------ | ---------------------------------- |
| POST   | /api/books/search              | 의미 기반 검색 (chunk/book 모드)   |
| GET    | /api/books/{cnts_id}/thumbnail | PDF 1페이지 JPEG 반환 (MinIO 캐싱) |
| GET    | /api/books/{cnts_id}           | 도서 단건 조회                     |

### 수집

| Method | Path                           | 설명                        |
| ------ | ------------------------------ | --------------------------- |
| POST   | /api/books/ingest/upload       | 단일 PDF 업로드 → 수집      |
| POST   | /api/books/ingest/upload/batch | 복수 PDF 일괄 업로드 → 수집 |
| POST   | /api/books/ingest/batch        | MinIO 기존 파일 배치 수집   |
| POST   | /api/books/catalog/load        | 엑셀 메타데이터 적재        |
| GET    | /api/books/ingest/{task_id}    | Celery 태스크 상태 조회     |

### 관리

| Method | Path                                | 설명                               |
| ------ | ----------------------------------- | ---------------------------------- |
| GET    | /api/admin/status                   | 전체 현황 (도서·섹션·Milvus·MinIO) |
| GET    | /api/admin/books                    | 도서 목록 (페이지네이션)           |
| GET    | /api/admin/books/{cnts_id}/sections | 섹션 목록                          |
| GET    | /api/admin/books/{cnts_id}/chunks   | Milvus 청크 목록                   |
| GET    | /api/admin/minio/files              | MinIO 파일 목록                    |

---

## 7. 인프라 구성

### 7.1 Docker Compose 서비스

| 서비스   | 이미지                               | 호스트 포트  | 비고                      |
| -------- | ------------------------------------ | ------------ | ------------------------- |
| etcd     | quay.io/coreos/etcd:v3.5.0           | -            | Milvus 메타데이터         |
| minio    | minio/minio:latest                   | 21000, 21001 | 원본 파일 + 썸네일 캐시   |
| milvus   | milvusdb/milvus:v2.4.6               | -            | 벡터 DB                   |
| postgres | postgres:16-alpine                   | 15432        | RDB                       |
| redis    | redis:7-alpine                       | 16379        | 캐시/큐                   |
| vllm     | landsoftdocker/nl-lib-vllm:latest    | 18081        | Gemma 4 E4B               |
| fastapi  | landsoftdocker/nl-lib-fastapi:latest | 18002        | API 서버                  |
| celery   | landsoftdocker/nl-lib-fastapi:latest | -            | 수집 워커 (concurrency=2) |
| nuxt     | landsoftdocker/nl-lib-nuxt:latest    | -            | 프론트엔드                |
| gateway  | nginx:alpine                         | 92           | 라우팅                    |

> PaddleOCR은 현재 비활성화 (주석 처리). Gemma 4 VLM이 스캔본 OCR을 대체.

### 7.2 GPU 메모리 현황 (H200 140GB)

| 프로세스                            | VRAM              | 역할          |
| ----------------------------------- | ----------------- | ------------- |
| nl-lib vLLM (Gemma 4 E4B, util 0.3) | ~22GB             | LLM 서빙      |
| nl-lib FastAPI (BGE-M3 + Jina)      | ~2.4GB            | 임베딩·리랭킹 |
| nl-lib Celery (BGE-M3 + Jina)       | ~2.4GB            | 수집 워커     |
| 타 스택 (library-ragnet 등)         | ~35GB             | 병행 운용     |
| **합계**                            | **~62GB / 143GB** |               |

### 7.3 vLLM 주요 설정

```yaml
--max-model-len 126976   # 126K 컨텍스트
--gpu-memory-utilization 0.3
--max-num-seqs 16        # 동시 처리 (섹션 요약 Semaphore 8로 절반 사용)
--enforce-eager          # CUDA graph 비활성화 (메모리 절감)
```

---

## 8. 도커라이징 과정에서 해결한 문제들

### 8.1 Gemma 4 모델 아키텍처 미인식

**에러:** `Transformers does not recognize this architecture: gemma4`

**원인:** Gemma 4는 2025년 3~4월 공개 최신 모델로 vLLM 공식 이미지(v0.19.0)의 transformers에 미포함.

**해결:** 커스텀 vLLM Docker 이미지. transformers 소스 최신 설치:

```docker
FROM vllm/vllm-openai:latest
RUN pip install git+https://github.com/huggingface/transformers.git \
      tokenizers>=0.21 huggingface_hub>=0.30
```

### 8.2 transformers-vLLM 버전 충돌

**에러:** `Qwen2Tokenizer has no attribute all_special_tokens_extended`

**해결:** transformers + tokenizers + huggingface_hub만 업그레이드, vLLM 바이너리 유지.

### 8.3 pip 의존성 문제

| 패키지                      | 에러                              | 해결                      |
| --------------------------- | --------------------------------- | ------------------------- |
| hanja (kss 의존)            | `No module named 'pkg_resources'` | `--no-build-isolation`    |
| peft (FlagEmbedding 의존)   | `No module named 'peft'`          | requirements 추가         |
| marshmallow (pymilvus 의존) | `no attribute '__version_info__'` | 버전 고정                 |
| kss                         | `idioms.txt not found`            | kss 제거, 정규식 fallback |
| einops (Jina 의존)          | `No module named 'einops'`        | requirements 추가         |

---

## 9. 운영 스크립트

### 9.1 PDF 일괄 업로드 (PowerShell)

```powershell
$outputDir = "C:\Users\LANDSOFT\Downloads\output"
$apiUrl = "http://211.219.26.15:18002/api/books/ingest/upload"

$pdfs = Get-ChildItem -Path $outputDir -Recurse -Filter "*.pdf"
Write-Host "총 $($pdfs.Count)개 PDF 발견"

foreach ($pdf in $pdfs) {
    Write-Host "업로드 중: $($pdf.Name)"
    curl.exe -X POST $apiUrl -F "file=@$($pdf.FullName)" --silent --show-error
    Write-Host " → 완료"
}
```

### 9.2 재처리 (Milvus 컬렉션 초기화 후 전체 재수집)

```bash
# Milvus 컬렉션 드롭 (스키마 변경 시 자동 재생성됨)
docker exec nl-lib-fastapi python -c "
from pymilvus import connections, utility
connections.connect(host='milvus', port='19530')
utility.drop_collection('nl_lib_embeddings')
print('dropped')
"

# is_embedded 플래그 초기화
docker exec nl-lib-postgres psql -U admin -d nl_lib -c \
  "UPDATE library_catalog SET is_embedded = false;"

# 전체 재처리 디스패치
docker exec nl-lib-fastapi python -c "
from workers.tasks import process_from_minio
from db.postgres import SyncSessionLocal
from models.book import Book

db = SyncSessionLocal()
not_embedded = db.query(Book.cnts_id).filter(Book.is_embedded == False).all()
db.close()

print(f'재처리 대상: {len(not_embedded)}건')
for (cnts_id,) in not_embedded:
    minio_key = f'originals/{cnts_id}/{cnts_id}.pdf'
    task = process_from_minio.delay(cnts_id, minio_key)
    print(f'  {cnts_id} → {task.id}')
print('디스패치 완료')
"
```

---

## 10. 참고 자료

- Gemma 4 E4B: https://huggingface.co/google/gemma-4-E4B-it
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- Jina Reranker v2: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
- vLLM: https://github.com/vllm-project/vllm
- Milvus Hybrid Search: https://milvus.io/docs/multi-vector-search.md
- 국립중앙도서관: https://www.nl.go.kr
