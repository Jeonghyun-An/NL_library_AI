# 큐레이션 고도화 설계 (Curation Enhancement)

작성일: 2026-06-18
상태: 설계 확정 (구현 미착수)

## Context

현재 시스템은 인덱싱 시 도서별로 `summary`(검색지향 분석)·`introduction`(사서 소개)·`themes`를 생성하고,
질의 시 **Top-1 도서 1권**에 대해서만 추천 이유를 스트리밍한다.

확장 목표:
1. **줄거리(plot)** — 책의 서사 요약(논문은 핵심 내용·기여) 표출
2. **독후효과(read_effect)** — "이 책을 읽으면 얻는 것"
3. **멀티북 큐레이션** — 검색 결과 **최대 3권**의 요약 데이터로 권별 추천이유 + 종합 큐레이션

이 기능들은 전부 per-book 요약 품질에 의존하므로, 요약 입력 캡(`SUMMARIZER_MAX_INPUT_CHARS`,
필요 시 맵-리듀스)이 토대가 된다.

## 핵심 결정 (확정)

| 항목 | 결정 |
|---|---|
| 줄거리·독후효과 생성 시점 | **인덱싱 시 미리** (질의 무관 자산, finalize 단계) |
| 멀티북 큐레이션 출력 | **권별 추천이유 3개 + 종합 큐레이션 1단락** |
| 줄거리 저장 | **신규 필드 — `library_catalog.extra` JSONB** (마이그레이션 불필요) |

## 1. 데이터 모델

`library_catalog.extra` (이미 존재하는 JSONB)에 키 추가 — 컬럼 추가 없음:
- `extra.plot` — 줄거리 (도서/문학: 서사 요약 / 논문: 핵심 내용·기여·방법)
- `extra.read_effect` — 독후효과 (일반형, 질의 무관)

기존 `summary` / `introduction` / `themes` 는 그대로 유지(역할 분리):
- `summary`: 검색·매칭 지향 분석 (벡터 메타청크에도 사용)
- `introduction`: 사서 톤 소개글
- `plot`: 읽기용 서사 줄거리 (신규)
- `read_effect`: 독후 효과 (신규)

## 2. 인덱싱 — `run_finalize` 확장

`app/services/ingestion/stages.py: run_finalize` 에서 도서 요약/소개 생성 직후,
동일 입력(`_combine_sections`, 입력 캡 적용)으로 **줄거리·독후효과를 추가 생성**하여
`book.extra["plot"]`, `book.extra["read_effect"]` 에 저장.

- **프롬프트 YAML 신설** (doc_type별, `app/domains/nl_library/prompts/`):
  - `plot.book.yaml` / `plot.literature.yaml` / `plot.policy.yaml`
  - `read_effect.book.yaml` / `read_effect.literature.yaml` / `read_effect.policy.yaml`
  - 논문(paper)은 §5 비용 분기 참조
- 입력: 섹션 요약 묶음(`_combine_sections` — 균등 샘플링 + 14,000자 캡 그대로 재사용)
- 생성 파라미터: 프롬프트 `params:`에서 관리 (max_tokens 등)

### 기존 도서 백필
신규 필드라 기존 인덱싱 도서엔 `plot`/`read_effect`가 없다.
finalize-only 재실행 스크립트(요약 복구 때 쓴 패턴)와 동일하게, extra에 누락된 도서만
순회하며 줄거리·독후효과를 생성·저장한다.

## 3. 질의 시 — 멀티북 큐레이션 API

신규 엔드포인트 `POST /api/books/curate` (SSE 스트리밍):
- 입력: `{ query, book_ids[≤3] }` (검색 결과 Top-3에서 전달)
- 서버: 각 권의 `{title, summary, themes, plot}` 로드 → **큐레이션 LLM 1회 호출**
- 출력(스트리밍):
  - 권별 추천이유 3개 (왜 이 책이 이 질의에 맞는지)
  - 종합 큐레이션 1단락 (3권을 어떻게 조합·활용할지, 순서/관계)
- 토큰: 3권 × (summary ~1,500 + plot) + 질의 ≈ 6~8k → 32768 컨텍스트 여유
- 프롬프트: `curation.yaml` (도메인 프롬프트로 외부화)

기존 단일 `reason/stream`(Top-1)은 유지하거나 `curate`로 흡수(권수 1도 처리).

## 4. 프론트엔드

- 검색 결과 Top-3 카드 각각에 **줄거리 · 독후효과 · 권별 추천이유** 표출
- 결과 상단에 **종합 큐레이션** 영역 신설
- `curate` SSE 수신 → 권별/종합 점진 렌더

## 5. ⚠️ 30만 논문 비용 분기 (doc_type별)

finalize에 LLM 2회(줄거리+독후효과)를 무조건 추가하면 인덱싱 LLM 부하가 ~40~50% 증가 →
본가동 일정에 직접 영향. doc_type으로 분기해 비용을 제어:

| doc_type | plot | read_effect | 근거 |
|---|---|---|---|
| book / literature | 생성 | 생성 | 줄거리·효과 가치 높음 |
| paper (KCI) | **생략** (abstract 대체) | 선택(경량) 또는 생략 | 논문은 abstract가 줄거리 역할, 비용 절감 |
| policy | 선택 | 선택 | 운영 판단 |

→ `run_finalize`에서 `doc_type` 기준으로 plot/read_effect 생성 여부를 분기.
설정으로도 토글 가능하게 (`GENERATE_PLOT_FOR`, `GENERATE_READ_EFFECT_FOR` 등 — 추후).

## 구현 순서

1. 프롬프트 YAML(plot/read_effect ×doc_type) + `run_finalize` 확장 + `extra` 저장 + doc_type 비용 분기
2. 기존 도서 백필 스크립트(finalize-only 패턴, extra 누락분만)
3. `POST /api/books/curate` 멀티북 큐레이션 엔드포인트 + `curation.yaml`
4. 프론트 Top-3 표출 + 종합 큐레이션 UI

## 의존성 / 리스크

- **요약 품질 토대**: plot/read_effect/추천이유 모두 per-book `summary` 품질에 좌우. 입력 캡(14,000자)·
  필요 시 맵-리듀스가 선행 토대.
- **비용**: §5 분기 없이는 30만 논문 인덱싱 시간이 크게 늘어남.
- **재인덱싱 불필요**: extra JSONB라 Milvus 스키마·재인덱싱과 무관 (DB UPDATE만).

## 검증

- 단건: 도서 1권 finalize → `extra.plot`/`read_effect` 생성 확인, doc_type 분기 확인
- 큐레이션: 질의 + 3권 → 권별 추천이유 3개 + 종합 1단락 스트리밍 확인
- 비용: 파일럿에서 doc_type별 finalize LLM 호출 수 측정 → 본가동 일정 재산정
