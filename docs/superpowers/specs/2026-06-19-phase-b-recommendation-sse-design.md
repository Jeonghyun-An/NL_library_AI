# Phase B: 추천이유 + 독후효과 SSE 통합 설계

작성일: 2026-06-19  
상태: 설계 확정 (구현 미착수)  
관련 스펙: `docs/specs/2026-06-18-curation-enhancement-design.md`

---

## 목표

기존 `stream_book_reason` SSE에 **독후효과(read_effect)** 생성을 통합한다.  
사용자 쿼리 맥락이 독후효과에 반영되도록 단일 LLM 호출에서 추천이유 → 독후효과를 연속 생성한다.  
아울러 인라인 프롬프트를 `recommendation.yaml`로 외부화하고, `extra["plot"]`을 컨텍스트에 추가한다.

---

## 설계 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 독후효과 생성 방식 | SSE 통합 (단일 LLM 호출) | 쿼리 맥락 반영 + 추가 지연 없음 |
| 구분자 | `###EFFECT###` | LLM 출력 내 명확한 섹션 경계 |
| 토큰 예산 | `RECOMMENDATION_MAX_TOKENS=1200` | 추천이유(~650) + 효과(~400) + 여유 |
| 프롬프트 관리 | `recommendation.yaml` | 기존 plot/read_effect YAML 패턴 통일 |
| plot 컨텍스트 | `extra["plot"]` 있을 때만 추가 | 사전 생성 없는 도서도 동작 보장 |

---

## SSE 이벤트 프로토콜

```
클라이언트 수신 순서:

data: {"keywords": ["생명", "소중함", ...]}   // MARC 키워드 or LLM #KW: 첫 줄
data: {"text": "이 책은 ..."}                 // 추천이유 스트림 (###EFFECT### 이전)
data: {"text": "...계속..."}
data: {"effect": "이 책을 읽으면 ..."}        // 독후효과 스트림 (###EFFECT### 이후)
data: {"effect": "...계속..."}
```

- `{keywords}`, `{text}` 이벤트 형식 유지 → **기존 프론트 하위 호환**
- `{effect}` 이벤트 신규 추가

---

## 컨텍스트 블록 변경

```
[도서 요약]            ← 기존 (book.summary)
[도서 줄거리]          ← 신규 (extra["plot"], 있을 때만)
[검색 매칭 구절]       ← 기존 (chunk_texts)
```

---

## 프롬프트 구조 (`recommendation.yaml`)

```yaml
parser: plain
params:
  temperature: 0.4   # REASON_TEMPERATURE 기본값 사용
system: |-
  당신은 도서관의 AI 사서입니다.

  {kw_instruction}  # 런타임 주입 (MARC 키워드 없을 때만)

  답변은 반드시 아래 두 섹션으로 작성하세요:

  [섹션 1 — 추천 이유]
  - 독서 의도와 도서 내용의 구체적 연결점을 찾아 3~4문장으로 작성
  - 제목·저자 반복 금지, 사과 표현 금지

  ###EFFECT###

  [섹션 2 — 읽고 난 후]
  - 사용자의 현재 상황·감정 맥락을 반영해 이 책을 읽으면 어떤 변화를 경험할지 2~3문장으로 작성
  - "이 책을 읽으면 ..." 형식

user: |-
  독서 의도: {{ intent }}
  원본 질의: {{ query }}

  도서 정보:
  {{ book_meta }}

  {{ context_text }}

  위 독서 의도를 기준으로 추천 이유와 읽고 난 후 효과를 작성하세요.
```

> `max_tokens`는 `params`에 넣지 않고 호출 시 `cfg.RECOMMENDATION_MAX_TOKENS`를 직접 주입한다.  
> `kw_instruction`도 런타임에 주입 (MARC 키워드 유무에 따라 달라지므로).

---

## 스트리밍 루프 상태 머신

```
상태: kw_phase → text_phase → effect_phase

[kw_phase]
  - 버퍼에 \n 등장 시 첫 줄에서 #KW: 파싱
  - 파싱 완료 → text_phase 전환, 나머지 텍스트는 text_phase로

[text_phase]
  - 델타를 버퍼에 누적
  - 버퍼에 "###EFFECT###" 포함 시:
      - 구분자 이전 텍스트 → {text: ...} emit
      - effect_phase 전환, 구분자 이후 텍스트는 effect_phase로
  - 구분자 없으면 버퍼 앞부분(len-12 chars) 안전 emit → {text: ...}

[effect_phase]
  - 델타를 즉시 {effect: ...} emit (구분자 재등장 없으므로 단순)

[flush on end]
  - 버퍼 잔여 텍스트 → 현재 phase에 맞게 emit
```

구분자 길이 = `len("###EFFECT###")` = 12. text_phase 버퍼에서 마지막 11자는 홀딩해 구분자 단어 분리 방지.

---

## 변경 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `app/domains/nl_library/prompts/recommendation.yaml` | 신규 — system/user 프롬프트 |
| `app/services/search/pipeline.py` | `stream_book_reason` 확장 — plot 컨텍스트, YAML 프롬프트 로드, `###EFFECT###` 상태 머신 |
| `app/core/config.py` | `RECOMMENDATION_MAX_TOKENS: int = 1200` 추가 |
| `.env.example` | `RECOMMENDATION_MAX_TOKENS=1200` 추가 |
| `app/tests/test_stream_book_reason.py` | 신규 — 상태 머신 단위 테스트 |

`REASON_MAX_TOKENS`(650) 설정은 그대로 유지 (다른 곳에서 참조 가능).

---

## 프론트엔드 4섹션 표출 (Phase G에서 구현)

| 섹션 | 데이터 출처 | 시점 |
|---|---|---|
| 줄거리 | `BookOut.plot` (`extra["plot"]`) | 즉시 (사전 저장) |
| 책 소개 | `BookOut.introduction` | 즉시 (사전 저장) |
| 읽고 난 후 | SSE `{effect: ...}` | 스트리밍 |
| 추천하는 이유 | SSE `{text: ...}` | 스트리밍 |

---

## 검증 방법

1. `POST /api/books/reason/stream` 호출 → SSE 수신 순서: `keywords` → `text` → `effect`
2. `extra["plot"]` 있는 도서: `[도서 줄거리]` 컨텍스트 포함 여부 확인
3. `extra["plot"]` 없는 도서: 오류 없이 동작 확인
4. `###EFFECT###` 구분자가 여러 토큰에 걸쳐 오는 케이스 단위 테스트
5. MARC 키워드 있는 도서 / 없는 도서 양쪽 `keywords` 이벤트 확인
