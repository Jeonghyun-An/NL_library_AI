# 딥리서치 화면·기록 세션 설계 (round04b)

> 상태: 설계 확정(2026-09-26, 사용자 승인) · §1~13 구현·운영 배포 완료 · **§14 보고서 작성 대기 화면·내보내기 추가(2026-09-28, 사용자 승인) · 구현 전**
> 선행: round04a 딥리서치 백엔드(`docs/superpowers/specs/2026-09-21-deep-research-agent-design.md`, `docs/roadmap/round04a-완료노트.md`)
> 브랜치: `feat/round04b-deep-research-frontend`

## 0. 사용자 요청 (paraphrase)

> round04a 로 만든 딥리서치 백엔드에 화면을 붙이자. 기존 논문 검색창에서 들어가고, 진행은 별도 화면에서 보게 하자. 최종 목표는 입력창 앞의 `+` 버튼으로 딥리서치 같은 모드를 골라 함께 쓰는 것이다. 사이드바의 세션(검색 기록) 탭이 엉켜 있으니 이번에 같이 손보고, 나중에 DB id 기반 세션이 들어올 자리까지 설계해서 구현하자. 기존 데이터가 날아가는 일은 절대 없어야 하고 운영에 부담을 주지 않아야 한다.

사용자는 이 프로그램의 개발자이자 설계자이며 총괄이다. 화면에 무엇이 나와야 하는지와 큰 구도는 사용자가 정하고, 시각 디자인과 세부 배치는 화면 기획자와 함께 다듬는다. 사용자는 Figma 를 직접 다루지 않으므로 화면 기획자에게는 **Figma 와이어프레임**으로 넘긴다(§8).

---

## 1. 배경 — 설계를 제약하는 실측

### 1-1. 프론트 구조 (조사일 2026-09-26)
- Nuxt 4 · Vue 3.5 · `marked` 뿐이다. UI 라이브러리·Pinia·공통 API 래퍼·SSE 헬퍼·테스트 도구가 없다.
- 공통 레이아웃이 없다. 페이지마다 `skx-app` + `AppSidebar` 를 직접 조립한다.
- 스타일은 전역 `assets/css/style_skovix.css`(5,143줄, 6월 이후 39회 수정 — 가장 자주 바뀐 파일)가 정본이다. 토큰은 `--skx-*`(인디고)를 쓴다. `app.vue` 에 옛 바이올렛 토큰이 남아 있다.
- 논문 입력창은 세 곳이다: 메인 논문 탭(`pages/index.vue`), `/papers` 첫 화면, 결과 화면 검색바(`pages/papers/index.vue`). 셋 다 결국 `pages/papers/index.vue` 의 `handleSearch` 로 모인다.
- 기존 "DeepSearch"(논문 한 편과 채팅)·"DeepRead" 가 있다. 새 기능은 **"딥리서치"** 로 부른다.
- 화면 고도화는 저장소 밖(화면 기획자의 Figma)에서 진행 중이다. 충돌 위험이 큰 곳은 `style_skovix.css` 끝부분과 `pages/index.vue` 다.

### 1-2. 세션(기록) 탭의 엉킨 지점
| # | 증상 | 원인 |
|---|---|---|
| H1 | AI 요약이 다른 기록에 섞여 저장된다 | 스트림이 끝난 시점의 `currentHistoryId` 로 저장한다. 도는 중에 다른 기록을 복원하면 그 기록을 덮는다. 중단 장치가 없다 |
| H2 | 뒤로가기·새로고침하면 결과가 사라지거나 옛 검색이 다시 돈다 | 검색·복원이 URL 에 반영되지 않는다. `/papers` 는 돌아올 때마다 옛 `?q=` 로 재검색하고 기록이 하나 더 쌓인다 |
| H3 | 기록을 지울 수 없다 | 삭제 UI 가 없다(`clearByType` 은 호출부 0) |
| M1 | 세 번째 종류를 넣으면 빈 화면 | 복원 분기가 네 벌이고 판정 기준이 서로 반대다 |
| M2 | 메인에서 도서 기록을 누르면 빈 결과 | 복원이 `mode` 를 바꾸지 않는다 |
| M3 | 오래된 기록이 조용히 사라진다 | 쿼터에 걸리면 5개씩 말없이 버린다. 논문 결과를 무겁게 저장한다. 상한 30개를 종류가 나눠 쓴다 |
| M4 | 브라우저 탭 두 개면 서로 덮는다 | 탭 사이 동기화가 없다 |
| M5 | 같은 검색이 중복 저장 | 중복 제거가 없고 엔터 연타 가드가 없다 |
| M6 | 추천 페이지에서 기록이 비어 보인다 | 사이드바가 페이지가 넘기는 props 에 의존한다 |
| M7 | 세션 ID 가 세 벌, 서버 기록은 반쪽 | `x-session-id` 를 도서 검색만 보낸다. 서버 `search_history` 는 쓰기만 하고 읽지 않는 로그다 |
| M8 | 로컬 기록과 서버 기록을 이을 수 없다 | 로컬 id(`Date.now`)와 DB id(uuid4)가 따로 있다 |
| M9 | `search-classic.vue` 가 깨진 채 라우팅돼 있다 | 없어진 composable API 를 호출한다 |

### 1-3. round04a 백엔드가 화면에 주지 못하는 것
- SSE 로 오는 것은 `snapshot`·`search`·`critique`·종료 이벤트뿐이다. 계획 완료·단계 전이·종합 진행은 오지 않는다.
- `search.found` 는 청크 수다. 검토한 논문 수·재검색 횟수가 없다.
- `critique` 에 다음 검색어·재검색 여부가 없다. 중간 회차의 판정이 저장되지 않아 **끝난 잡에서는 자기점검 장면을 재생할 수 없다.**
- 잡 목록 API 가 없고 `created_by` 를 채우지 않는다. `GET /{id}` 에 시각·파라미터가 없다.
- 로그인·사용자 개념이 없다. 식별자는 브라우저 localStorage 의 `sid`(UUID) 하나다.

---

## 2. 결정 사항과 근거

| # | 결정 | 근거 |
|---|---|---|
| D1 | **진입은 입력창 앞 `+` 메뉴**(딥리서치 칩), `/deep-research` 는 같은 동작의 키보드 단축 | `+` 가 최종 목표다. 슬래시만으로는 일반 사용자가 모른다. 시연 서사("같은 검색창, 더 깊은 모드")는 슬래시로 살린다 |
| D2 | `+` 메뉴는 **이번 라운드에 구현**한다. 독립 컴포넌트 하나를 논문 입력창 세 곳에 한 줄씩 끼운다 | 입력창은 고도화와 가장 겹치는 영역이라 수정 면적을 컴포넌트 삽입 한 줄로 줄인다 |
| D3 | 진행 화면은 **같은 탭에서 `/research/<job_id>`** 로 이동 | 목록 API 가 없던 구조에서 주소가 곧 열쇠다. 새로고침·공유·"미리 돌려둔 보고서 열기"가 주소 하나로 된다. 새 탭은 팝업 차단, 앱 탭은 `index.vue` 대수정과 진입점 중복 |
| D4 | 페이지는 **A(2단)·B(쌓이는 문서) 둘 다 되는 구조**. 기본값은 기획자가 정한다(§7) | 사용자가 둘 중 하나를 정하지 않았다. 블록 네 개 + 배치 틀로 나누면 틀만 바꿔 둘 다 지원한다 |
| D5 | **기록은 서버에 저장한다 — 새 테이블 `history_items` 하나만 추가**. 기존 테이블·데이터는 무변경 | "DB 변경 없음·운영 부담 없음·기존 데이터 무손실" 조건. 새 테이블은 `create_all` 이 추가하고 기존 테이블에 ALTER 가 없어 잠금 문제(recurring-gotchas 18번)가 없다. `research_jobs` 도 같은 방식으로 문제없이 생성됐다 |
| D6 | 기록 소유 단위는 **브라우저 ID**(`sid`). 사용자 ID(로그인)는 **만들지 않고 자리만 둔다**(`user_id` NULL 컬럼) | 도서관 서비스의 기본은 비로그인 검색이다. 최종 형태는 도서관 회원 인증(SSO 등) 연결일 가능성이 크다. 로그인은 비밀번호·세션 만료·탈취 대응을 요구하는 보안 작업이라 대회 일정에 어설프게 넣으면 더 위험하다 |
| D7 | 남의 기록 id 로 접근하면 서버는 **404**, 화면은 **대체 동작** | 로그인이 없어 id 만 알면 남의 검색어·결과를 볼 수 있게 된다(서버 공유 환경). 공유 링크는 검색어(`q`)로 재검색하거나 딥리서치 보고서를 그대로 연다(§4-6) |
| D8 | **딥리서치 백엔드를 보강**해 단계·회차·카운터·종합 진행을 이벤트로 보내고 `research_steps.result` 에 남긴다 | 시연을 "미리 돌려둔 보고서 열기"로 할 때도 자기점검 장면을 재생하려면 저장이 필요하다. 기존 JSON 칸이라 DB 변경이 없다 |
| D9 | 모델이 쓴 글은 **`v-html` 로 넣지 않는다** | 기존 화면은 `marked`+`v-html` 에 sanitize 가 없다. 보고서는 `[E3]` 마커로 쪼개 글과 칩 컴포넌트로 그린다 |
| D10 | 딥리서치 CSS·컴포넌트는 **별도 파일** | 기획자 디자인이 나오면 그 파일만 갈아입힌다. `style_skovix.css` 끝에 덧붙이면 거의 확실히 충돌한다 |

---

## 3. 범위와 작업 순서

| # | 덩어리 | 핵심 | 운영 영향 |
|---|---|---|---|
| 1 | 기록·세션 기반 | §4 전부. §1-2 의 H1~M9 해소 | 새 테이블 추가뿐 |
| 2 | 딥리서치 백엔드 보강 | §5 | DB 변경 없음. 딥리서치 워커·fastapi 만 재배포 |
| 3 | 딥리서치 화면 | §6 | 새 페이지·컴포넌트·CSS. 기존 입력창에는 `+` 한 줄 |
| 4 | Figma 와이어프레임 | §8 | 코드와 무관. 설계 확정 직후 먼저 그려 넘긴다 |

순서는 1 → 2 → 3 이고 4 는 나란히 한다. 1 이 먼저인 이유: 딥리서치 기록이 사이드바에 들어가야 하고, 엉킨 복원 로직을 먼저 정리해야 세 번째 종류를 끼웠을 때 빈 화면이 나지 않는다(M1). 일정이 모자라면 이 순서대로 자른다.

---

## 4. 기록·세션 기반

### 4-1. 용어
- **브라우저 ID** — localStorage `sid` 의 UUID v4. 브라우저마다 하나, 만료 없음. 그 브라우저의 모든 기록이 여기에 묶인다. 사이드바의 예전 기록을 누르면 전부 같은 브라우저 ID 의 기록이라 정상적으로 열린다.
- **기록** — 사이드바 항목 하나(도서 검색·논문 검색·딥리서치 잡).
- 한계: 브라우저를 바꾸거나 저장소를 지우면 새 브라우저 ID 가 생겨 이전 기록이 사이드바에서 안 보인다(서버에서 지워지지는 않는다). 로그인이 생기면 `user_id` 로 묶어 해결한다.

### 4-2. 식별자 규칙
| 무엇 | 규칙 |
|---|---|
| 브라우저 ID | `sid` 키 유지. 소문자 표준형 UUID v4 가 아니면 새로 만든다. 생성 코드 세 벌(`pages/index.vue`·`composables/useSearch.ts`·`pages/search-classic.vue`)을 `useBrowserId()` 하나로 합친다. localStorage 접근은 전부 try/catch — 막힌 환경에서는 메모리 값으로 동작한다 |
| 헤더 | **모든 `/api` 요청에 `x-session-id`**. `$fetch` 는 `useApi()` 래퍼가, 스트림용 native `fetch` 는 `apiHeaders()` 가 붙인다. 서버가 쓰지 않는 엔드포인트에 붙어도 무해하다 |
| 기록 id | 브라우저가 만드는 UUID(`crypto.randomUUID`)가 **그대로 서버 PK**. 딥리서치 기록은 **id = `job_id`** |
| 옛 기록 id | v1 의 13자리 숫자 id 는 **서버가 import 때** `uuid5(NAMESPACE_URL, "nl-lib-history-v1:" + v1id)` 로 **결정론적으로** 변환한다 — 이전을 여러 번 해도 같은 id 가 된다. import 응답이 `{v1id: 새 id}` 대응표를 돌려주고, 브라우저는 이를 `skx_history_v1_map` 에 보관해 옛 `?restore=<v1id>` 주소를 새 id 로 찾는다(브라우저에 uuid5 구현을 두지 않는다) |

### 4-3. 새 테이블 `history_items`
기존 테이블(`search_history`·`search_sessions`·`library_catalog` 등)은 **한 줄도 바꾸지 않는다.**

| 컬럼 | 타입 | 내용 |
|---|---|---|
| `id` | UUID PK | 브라우저가 만든 id(§4-2) |
| `session_id` | UUID NOT NULL | 브라우저 ID |
| `user_id` | VARCHAR(64) NULL | **로그인 도입 시 자리.** 지금은 항상 NULL |
| `kind` | VARCHAR(16) NOT NULL | `book` · `paper` · `research` |
| `title` | TEXT NOT NULL | 검색어 또는 연구 질문 |
| `params` | JSONB NOT NULL DEFAULT `{}` | 검색 조건(논문 등재구분 등). 8KB 상한, 넘으면 413 |
| `snapshot` | JSONB NULL | 복원용 **축약** 결과 — 목록 카드에 필요한 필드만(§4-5). 200KB 상한, 넘으면 413 |
| `ai` | JSONB NULL | AI 요약. 도서 `{intro, items}`, 논문 `{text, refs}`. 64KB 상한, 넘으면 413 |
| `ref_id` | VARCHAR(64) NULL | 딥리서치 `job_id` |
| `created_at` / `updated_at` | TIMESTAMPTZ | |
| `deleted_at` | TIMESTAMPTZ NULL | **소프트 삭제** — 사용자가 지워도 행은 남는다 |

- 인덱스: `(session_id, kind, created_at DESC) WHERE deleted_at IS NULL`.
- 딥리서치 진행 상태는 저장하지 않는다. 조회 때 `research_jobs` 에서 붙인다(두 곳 상태가 어긋나지 않게).
- 생성: 모델을 추가하면 fastapi lifespan 의 `create_all` 이 만든다. Alembic `0006_history_items` 도 같은 내용으로 작성하고 배포 뒤 `stamp` 로 맞춘다(round04a `0005` 와 같은 절차, recurring-gotchas 14번). 모델↔마이그레이션 정합 테스트를 둔다.
- 기존 `search_history` 쓰기(`app/api/book.py` 의 도서 검색 로그)는 **그대로 둔다.** 정리는 범위 밖(§11).

### 4-4. 기록 API (`/api/history`)
모든 요청은 헤더 `x-session-id`(UUID v4)가 필요하다. 없거나 형식이 틀리면 400. 브라우저 ID 는 **URL 에 넣지 않는다**(nginx access log 에 남지 않게 — 기존 `GET /api/books/history/{session_id}` 의 문제).

| 메서드·경로 | 요청 | 응답 |
|---|---|---|
| `GET /api/history?kind=&limit=30&before=` | `kind` 생략 시 전체, `before` 는 이전 페이지의 `next_cursor` | `{items:[{id, kind, title, params, ref_id, created_at, updated_at, has_snapshot, has_ai, research:{status, stage}\|null}], next_cursor}` |
| `GET /api/history/{id}` | — | 위 필드 + `snapshot`·`ai` |
| `PUT /api/history/{id}` | `{kind, title, params?, snapshot?, ai?, ref_id?}` | 저장된 항목. **같은 id 를 여러 번 보내도 안전**(upsert). 다른 브라우저 ID 의 행이면 404(덮어쓰지 않는다) |
| `PATCH /api/history/{id}` | `{title?, params?, snapshot?, ai?}` 부분 | 갱신된 항목. `updated_at` 갱신 |
| `DELETE /api/history/{id}` | — | 204. 소프트 삭제 |
| `DELETE /api/history?kind=` | — | 204. 그 종류 전부 소프트 삭제 |
| `POST /api/history/import` | `{items:[v2 항목 + legacy_id(v1 숫자 id)…]}` 최대 100건 | `{imported, skipped, id_map:{v1id: id}}`. id 기준 중복 무시(§4-2) |

- 상한은 JSON 칸을 UTF-8 로 직렬화한 바이트로 잰다(한글 3바이트, `\uXXXX` 이스케이프 길이가 아니다). PUT·PATCH 는 하나라도 넘으면 413 으로 거절한다. import 는 413 을 내지 않고 넘친 칸만 비운 뒤(`snapshot`·`ai` 는 null, NOT NULL 인 `params` 는 `{}`) 나머지를 옮긴다 — 한 건 때문에 묶음 전체가 매번 실패하지 않게.
- import 의 `created_at` 은 서버 현재 시각을 넘지 못한다(미래 시각은 지금으로 자른다). 목록이 `created_at` 내림차순이라 미래 시각 항목이 새 기록 위에 계속 고정되지 않게.

- 소유 확인: 행의 `session_id` 가 헤더와 다르면 404(존재 여부를 드러내지 않는다).
- 딥리서치 잡 생성(`POST /api/research`)은 헤더의 브라우저 ID 를 `research_jobs.created_by` 에도 넣는다(기존 컬럼). 기록 항목은 화면이 `PUT` 으로 만든다 — 모든 종류가 같은 경로로 저장되게.
- 서버 쪽 코드 배치: `models/history.py` · `schemas/history.py` · `repositories/history.py`(ORM 을 밖으로 내보내지 않고 스키마로 반환 — coding-standard) · `api/history.py`(얇은 라우터).

### 4-5. 프론트 저장소
- **타입 v2**(`types/history.ts`): `kind` 로 구분하는 유니온. 공통 `{id, kind, title, createdAt, updatedAt?}`, 도서 `{params, snapshot?, ai?:{intro, items}}`, 논문 `{params:{grade?}, snapshot?, ai?:{text, refs}}`, 딥리서치 `{refId, research?:{status, stage}}`.
- **snapshot 은 허용 필드 목록 방식**으로 만든다(지금은 빼는 필드를 나열해서 서버 필드가 늘면 저장량도 는다). 도서·논문 모두 목록 카드에 쓰는 필드만, 최대 20건.
- **저장소 인터페이스** `HistoryStore { list, get, put, patch, remove, clear, importLegacy }` — 모두 Promise.
  - `ServerHistoryStore` 가 정본이다.
  - `LocalHistoryStore` 는 캐시와 **보낼 편지함(outbox)** 이다. 서버가 실패하면(네트워크·5xx) 브라우저에 먼저 저장하고 다음 로드·온라인 복귀 때 다시 보낸다. 쿼터 초과(`QuotaExceededError` 만)는 캐시의 snapshot 부터 비우고 목록은 남긴다.
  - 화면(사이드바·페이지)은 `useHistory()` 만 알고 어느 저장소인지 모른다.
- **기존 기록 이전**: 처음 로드 때 `skx_search_history`(v1)가 있으면 v2 로 바꿔(`type→kind`, `query→title`, `timestamp→createdAt`, `aiSummary` JSON 파싱) `POST /api/history/import` 로 올린다. **성공해도 원본을 지우지 않고** `skx_search_history_backup_v1` 로 이름만 바꿔 둔다. 실패하면 v1 을 그대로 두고 다음에 다시 시도한다.
- **탭 동기화**: `storage` 이벤트로 다른 탭의 변경을 받아 다시 읽는다.
- **SSR**: 기록 목록은 `<ClientOnly>` 안에서 마운트 뒤에 읽는다(하이드레이션 불일치 방지).

### 4-6. URL 규칙 (`utils/historyRoute.ts` 한 곳)
| 종류 | 주소 | 복원 |
|---|---|---|
| 도서 | `/?h=<id>&q=<검색어>` | `h` 로 기록을 읽어 snapshot·ai 를 그린다. 없거나 남의 기록이면 `q` 로 **새로 검색** |
| 논문 | `/papers?h=<id>&q=<검색어>&grade=` | 같음 |
| 딥리서치 | `/research/<job_id>` | 보고서 자체는 누구나 열린다(`GET /api/research/{id}` 는 소유 확인이 없다). 막히는 것은 남의 사이드바 목록뿐 |

- 검색이 성공하면 `router.replace` 로 `h`·`q` 를 URL 에 넣는다 → 뒤로가기·새로고침이 재검색 없이 복원된다(H2).
- 페이지는 `watch(() => route.query.h, …, {immediate: true})` 로 복원한다(같은 경로에서 쿼리만 바뀌면 다시 마운트되지 않는다).
- 옛 `?restore=<id>` 는 `h` 의 별칭으로 계속 받는다.
- 상세 페이지로 갈 때 `h` 를 함께 넘겨 사이드바가 현재 기록을 강조하고 뒤로가기가 제대로 복원되게 한다.
- 사용자에게 날것의 404 는 보여 주지 않는다. 사라진 기록은 "없는 기록" 안내 후 목록에서 정리한다.

### 4-7. 스트림 경합(H1)과 중복(M5)
- 검색·큐레이션·요약 스트림은 **시작할 때 기록 id 를 붙잡아** `fetchCuration(id, signal)`·`streamAiSummary(id, signal)` 로 넘긴다. 완료 후 저장은 붙잡은 id 로만 한다.
- 새 검색·복원·언마운트 때 `AbortController` 로 끊는다(페이지를 떠나도 GPU 작업이 계속 도는 문제도 함께 해소).
  - 예외 — 도서 큐레이션(`POST /books/curate`)은 스트리밍이 아닌 단발 호출이라 연결을 끊어도 서버 생성이 끝까지 돈다. 끊으면 결과만 버리고 돌아왔을 때 다시 만든다. 그래서 요청은 끊지 않고 끝까지 받아 붙잡은 id 로 저장하며, 같은 기록의 요청이 도는 중이면 새로 부르지 않고 이어받는다(`utils/curationRequest.ts`). 끊는 것은 화면 갱신(타이핑)뿐이다. 논문 요약은 스트림이라 끊으면 생성도 멈추므로 그대로 끊는다.
- 중복: 같은 `kind`·정규화한 `title`·`params` 가 10분 안에 다시 오면 새로 만들지 않고 기존 기록을 갱신해 맨 위로 올린다. 입력 중 로딩 가드로 엔터 연타를 막는다.

### 4-8. 사이드바 (`AppSidebar.vue`)
- `useHistory()` 를 직접 읽고 클릭 시 `historyRoute` 로 직접 이동한다. 페이지마다 네 벌 있던 복원 코드와 `bookHistory`/`paperHistory` props·`@restore` 를 없앤다 → 추천 페이지 포함 어디서나 같게 동작(M1·M6).
- 탭: 도서 · 논문 · **딥리서치**. 초기 탭과 강조 항목은 현재 라우트에서 정한다(`?h=`, `/papers*`, `/research/*`).
- 항목별 삭제, 탭별 전체 삭제(확인 창), 빈 상태 문구, 딥리서치 **상태 배지**(진행 중·완료·실패·취소). 배지는 기록 목록 응답의 `research` 필드로 그리고, 끝나지 않은 항목이 있을 때만 사이드바가 보이는 동안 **30초마다** 목록을 다시 읽는다(탭이 숨겨지면 멈춘다).
- 접힘 상태를 페이지 사이에 유지한다(`useState`).

### 4-9. 정리
- 삭제: `pages/search-classic.vue`(링크 없이 깨진 잔재 — M9), 그것만 쓰던 `components/ChatHistory.vue`. 옛 `composables/useSearch.ts` 는 세션 ID 코드를 `useBrowserId()` 로 옮긴 뒤 호출부가 없으면 삭제한다.
- 도서 상세의 연관도서 검색이 헤더 없이 `/books/search` 를 불러 주인 없는 `search_history` 행을 쌓는 문제는 헤더 자동 첨부로 완화된다. 연관 검색을 로그에서 빼는 것은 범위 밖(§11).

---

## 5. 딥리서치 백엔드 보강

**원칙: 이벤트로 흘려보내는 것은 전부 `research_steps.result` 에도 남긴다.** 라이브로 볼 때와 끝난 뒤 다시 열 때 같은 장면이 나와야 한다. 기존 JSONB 칸과 기존 컬럼만 쓴다 — **DB 변경 없음.**

### 5-1. 이벤트 (SSE `data:` 한 줄 JSON, `kind` 로 분기)
| kind | 상태 | 언제 | payload |
|---|---|---|---|
| `snapshot` | 확장 | 연결 직후 | `steps[]` 에 **`result` 포함**, + `job:{status, stage, plan}` |
| `status` | 신규 | 잡 상태·단계가 바뀔 때(워커·API 모두) | `{status, stage}` — 계획 중·**승인 대기**·대기열(`approved`/`queued`)·탐색 중·종합 중·종료 |
| `step` | 신규 | 단계가 생기고 끝날 때 | `{seq, step_kind, subq_idx, title, status, result?}` |
| `search` | 확장 | 검색 한 번 | 기존 `{subq_idx, query, found}` + **`round`**(1부터), **`new_papers`**(이번에 처음 본 논문 수) |
| `critique` | 확장 | 자기점검 한 번 | 기존 `{subq_idx, verdict, note, adopted, parse_failed, capped}` + **`round`**, **`next_query`**(없으면 null), **`will_recheck`** |
| `counters` | 신규 | 검색·점검 뒤 | `{papers_reviewed, evidence_adopted, rechecks}` — 잡 전체, 고유 논문 기준 |
| `synth` | 신규 | 절 하나를 쓰기 시작·끝낼 때 | `{section_idx, total, status}` |
| `done`·`failed`·`canceled` | 유지 | 종료 | round04a 의 통일된 종료 프레임 그대로 |

- `step` 의 종류 필드는 `kind` 와 겹치지 않게 **`step_kind`** 로 부른다.
- 승인·재시도·취소 API 는 처리 즉시 `status` 를 발행한다(취소는 이미 종료 프레임을 발행한다).
- 계획 태스크도 이벤트를 발행한다(지금은 0건 — 계획 단계에 붙은 스트림이 계획 완료를 모른다).

### 5-2. 저장
| 위치 | 추가하는 키 |
|---|---|
| search 단계 `result` | `rounds:[{round, query, found_chunks, new_papers, verdict, note, next_query}]` — 하위질문의 회차 이력. 끝난 잡에서 자기점검 장면을 재생하는 원천 |
| synthesize 단계 `result` | `sections_total`, `sections:[{idx, status}]` |
| 보고서 JSON | `stats:{papers_reviewed, evidence_adopted, rechecks}` — 보고서 서론 한 줄의 원천(키 추가만, 기존 키 무변경) |
| `ResearchState` | `seen_cnts`(검토한 고유 논문) — 스냅샷 왕복·재개 시에도 유지 |

- `GET /api/research/{id}` 응답에 `created_at`·`started_at`·`finished_at`·`params` 를 추가한다(기존 컬럼).
- 옛 잡(보강 전)의 단계 결과에는 `rounds` 가 없다. 화면은 이 경우 `report.trail` 로 대체해 보여 준다.

### 5-3. 배포
`nl-lib-fastapi`·`nl-lib-celery-research`·`nl-lib-celery-research-plan` 컨테이너만 Recreate 한다. 인덱싱 워커는 건드리지 않는다. fastapi 재시작 때 lifespan 의 `ALTER TABLE library_catalog` 가 잠금을 기다리는 동안 조회가 잠시 줄 설 수 있다(recurring-gotchas 18번) — 배포 절차에 적는다.

---

## 6. 딥리서치 화면

### 6-1. 진입 (`components/research/SearchPlusMenu.vue`)
- 입력창 앞 원형 `+` 버튼 → 메뉴 → **딥리서치** 선택 → 입력창 안에 `딥리서치 ×` 칩. 플레이스홀더가 "연구 질문을 입력하세요" 로 바뀐다.
- 입력이 `/deep-research ` 로 시작하면 자동으로 칩으로 바뀐다.
- **슬래시 명령 목록**: 자기 입력창에 초점이 있고 칩이 꺼진 채 글 전체가 `/` 로 시작하는 한 토큰이면 입력 상자 바로 아래에 쓸 수 있는 명령(`/deep-research 딥리서치`)을 띄운다 — 명령 이름·라벨 접두로 거르고(`/dee`·`/딥`), `/` 하나면 전부. ↑↓ 로 강조, 엔터·Tab 으로 고르면 `+` 메뉴와 같이 칩으로 바뀌고 토큰은 입력창에서 지운다(그래서 `/deep-research` 까지만 치고 엔터를 쳐도 빈 질문 오류 대신 칩이 켜진다). Esc 는 입력값이 바뀔 때까지 닫는다. 토큰 뒤에 공백이 붙으면 목록 없이 위 자동 칩 규칙을 따른다.
- 메뉴 항목은 목록 데이터(`id·label·description·icon·available(kind)`)로 관리한다 — 다른 모드를 한 줄로 추가할 수 있게.
- 엔터 → `POST /api/research` → `PUT /api/history/{job_id}` → `/research/<job_id>` 로 이동. 잡 생성이 실패하면 입력창 아래에 오류를 보이고 입력을 지우지 않는다.
- 논문 입력창 세 곳에만 넣는다. 도서 입력창은 이번에 넣지 않는다(딥리서치는 논문 전용).

### 6-2. 페이지 `/research/<job_id>` — 상태별 화면
블록 네 개: **머리**(질문·상태·보기 전환·취소/재시도·링크 복사), **계획 카드**, **진행 패널**, **보고서**. 배치는 §7 의 A·B 중 하나.

| 상태 | 본문 | 진행 패널 |
|---|---|---|
| `created`·`planning` | "연구 계획을 세우는 중" | 빈 타임라인 |
| `awaiting_approval` | **계획 카드**: 하위질문 바로 고치기·삭제·추가(상한 `max_subquestions` 까지), [승인하고 시작]·[취소] | 안내 |
| `approved`·`queued` | "앞선 연구가 끝나면 시작합니다" | — |
| `running`(탐색) | 계획(하위질문별 진행 표시) | 카운터 3개 · 하위질문별 **회차 타임라인** · **자기점검 강조 카드**("근거 부족 → '○○'로 재검색") |
| `running`(종합) | "보고서 작성 중 2/3" | 탐색 완료 요약 |
| `completed` | **보고서**(§6-3) | **탐색 경로** — 같은 패널로 회차 이력을 다시 본다 |
| `failed` | 오류 안내 + **[재시도]**(탐색이 끝났으면 종합부터 — `stage=explored`) | 멈춘 지점 |
| `canceled` | "취소됨" + [같은 질문으로 다시 시작](새 잡) | 멈춘 지점 |

- 상태 갱신은 SSE 가 주도하고, 연결이 끊기면 `snapshot` 으로 복원한다. 종료 이벤트를 받으면 `EventSource` 를 반드시 닫는다(닫지 않으면 자동 재접속으로 snapshot·종료를 반복 수신).
- 없는 잡(404)이면 "찾을 수 없는 연구" 안내와 검색으로 돌아가기.
- 오류 처리: 409(이미 진행·종료)는 최신 상태를 다시 읽어 화면을 맞춘다. 422 는 문자열·배열 두 모양의 `detail` 을 모두 처리한다. 429·503 은 "잠시 뒤 다시" 안내.

### 6-3. 보고서
- **머리**: 질문, 수록 범위("2002~2026 논문 N편 기준" — `report.range`), 생성 시각, [링크 복사].
- **서론 한 줄**(화면이 만든다): "하위질문 3개로 나눠 논문 38편을 검토하고 11편을 근거로 삼았다" — `report.stats`.
- **절별**: 소제목(하위질문) · 도입 문단(인용칩) · 대표 논문(`저자 (연도): 요약` + 칩) · 향후 과제.
- **한계 섹션**: 눈에 띄게 둔다(spec §2-4 의 차별점). `limitations` 문장을 가공 없이 싣는다.
- **인용칩** `[E3]` → `김 2019` 형태. 올리거나 누르면 팝오버:
  - 제목, 저자·학술지·권호·연도·피인용·등재구분(`evidence[E].meta`)
  - 그 절에서 매칭된 **원문 대목**(`sections[].evidence_chunks` → `evidence[E].chunks`), 여러 개면 1/2 넘기기, 쪽수
  - [원문 보기] — `PdfViewer` 로 `/api/books/{cnts_id}/pdf` 를 해당 쪽(`#page=N`)으로 연다. [논문 상세] — `/papers/<cnts_id>`
  - 쪽 정보가 0 이면 "p.0" 대신 "쪽 정보 없음"(0-based 라 첫 쪽과 구분 불가). PDF 가 없어 404 면 "원문 파일이 없습니다"
  - 키보드로 칩에 초점을 옮기면 같은 팝오버가 열린다
- **안전(D9)**: 마커를 파싱해 글 조각과 칩 컴포넌트 배열로 그린다. `v-html` 을 쓰지 않는다.

### 6-4. 코드 구조
| 새 파일 | 역할 |
|---|---|
| `pages/research/[id].vue` | 상태 기계·배치 틀 |
| `components/research/ResearchHeader.vue` · `PlanCard.vue` · `ProgressPanel.vue` · `ReportView.vue` · `CitationChip.vue` · `SearchPlusMenu.vue` | 블록·칩·`+` 메뉴 |
| `composables/useResearch.ts` | 생성·승인·재시도·취소·조회, SSE 수명주기 |
| `composables/useApi.ts` · `composables/useBrowserId.ts` | 헤더 자동 첨부 · 브라우저 ID |
| `composables/useHistory.ts` · `utils/historyStore.ts` · `utils/historyRoute.ts` | 기록(§4) |
| `utils/citations.ts` · `utils/slashCommand.ts` | 마커 파싱 · 슬래시 파싱 |
| `types/research.ts` · `types/history.ts`(v2) | 타입 |
| `assets/css/research.css` | 딥리서치 전용 스타일. `--skx-*` 토큰만 읽는다 |

기존 파일 수정: 논문 입력창 세 곳의 `+` 한 줄씩(`pages/index.vue`·`pages/papers/index.vue`), `nuxt.config.ts` 의 `css` 에 `research.css` 한 줄, `PdfViewer.vue` 에 선택 prop `page`, 그리고 §4 의 기록 정리(사이드바·복원 로직·스트림 경합).

---

## 7. 배치 A·B — 화면 기획자 결정용

> 이 절은 화면 기획자에게 그대로 전달할 수 있게 썼다. 개발은 **두 배치를 모두 지원**하도록 만들기 때문에, 어느 쪽을 고르든 개발 일정에는 영향이 없다. 정하는 것은 **기본 보기와 세부 규칙**이다.

### 7-1. 두 배치
| | **A. 본문 + 진행 패널 (2단)** | **B. 쌓이는 문서 (1단)** |
|---|---|---|
| 모양 | 왼쪽에 계획·보고서, 오른쪽에 진행 패널이 고정 | 위에서 아래로 계획 → 탐색 과정 → 보고서가 카드로 붙는다 |
| 진행 중 | 보고서 자리와 "에이전트가 판단하는 장면"이 **한 화면에 동시에** 보인다 | 진행 카드가 화면 가운데에 크게 보인다 |
| 완료 후 | 오른쪽 패널이 "탐색 경로"로 바뀌어 과정을 옆에서 다시 볼 수 있다 | 보고서가 길어지면 과정 카드가 위로 밀려 스크롤해야 보인다 |
| 좁은 화면 | 폭이 모자라면 자동으로 B 로 바뀐다 | 그대로 |
| 기존 화면과의 관계 | 논문 결과 화면의 오른쪽 패널(AI 요약·채팅 드로어) 구도와 같다 | 문서·보고서를 읽는 느낌에 가깝다 |

### 7-2. 판단 기준
- **시연에서 무엇을 보여 줄 것인가** — "스스로 부족을 판단하고 다시 찾는 장면"을 보고서와 함께 보여 주는 게 핵심이면 A 가 유리하다.
- **보고서 읽기가 주 용도인가** — 완료 후 긴 보고서를 읽고 공유하는 게 주 용도면 B 가 차분하다.
- **다른 화면과의 일관성** — 논문 결과 화면이 이미 2단이면 A, 문서형 화면이 기준이면 B.

### 7-3. 기획자가 정할 항목
1. 넓은 화면의 **기본 보기**(A 또는 B)
2. 보기 **전환 버튼을 사용자에게 보일지** 여부(숨기면 기본 보기로 고정)
3. A 에서 B 로 자동 전환되는 **화면 폭 기준**(개발 기본값 1200px)
4. A 의 **진행 패널 폭**과, 완료 뒤 패널을 **유지할지 접을지**
5. 자기점검 강조 카드의 **강조 정도**(색·움직임)

### 7-4. 기획자 피드백 (2026-09-28 시연)
- 배치 A(우측 패널에 탐색 과정)는 **"덜 인터랙티브해 보인다"**는 평을 받았다. 사용자 방침: **인터랙티브함이 매우 중요하다.**
- 배치는 전환 버튼이 이미 있어 언제든 바꿀 수 있으므로 이번에는 기본 보기를 바꾸지 않는다. 기본 보기를 정할 때(위 1번) 이 피드백을 근거로 쓴다.
- 이후 화면 작업(§14 포함)은 정적인 글 나열보다 진행이 눈에 보이는 움직임, 눌러서 이동·펼치는 요소, 실시간 갱신을 먼저 검토한다. 단 `prefers-reduced-motion` 을 존중하고, 자동 스크롤로 읽는 사람을 끌고 가지 않는다.

Figma 에는 두 배치를 같은 상태별로 나란히 그려 비교할 수 있게 한다(§8).

---

## 8. Figma 와이어프레임

- 위치: 이 세션에 연결된 Figma 팀 계정(`paradeigma`, "파라데이그마's team")에 새 파일 "NL-Lib 딥리서치 와이어프레임 (round04b)".
- 형식: **회색조 와이어프레임**(색·폰트는 기획자 몫), 데스크톱 1440 폭. 프레임마다 옆에 **설명 메모** — 요소가 무엇인지, 데이터가 어디서 오는지(§5·§6 의 필드), 어떤 상태에서 보이는지.

| 페이지 | 프레임 |
|---|---|
| 1. 흐름 | 입력 → 계획 승인 → 진행 → 보고서, 상태 전이도 |
| 2. 진입 | 입력창 `+` 메뉴 열림 · 딥리서치 칩 · 슬래시 입력 · 슬래시 명령 목록 |
| 3. A 배치 | 계획 대기 · 탐색 중(자기점검 강조) · 종합 중 · 완료 · 실패 · 취소 |
| 4. B 배치 | 탐색 중 · 완료 |
| 5. A·B 비교 | 같은 상태(탐색 중·완료)를 나란히 + §7-3 결정 항목 메모 |
| 6. 보고서 상세 | 인용칩 팝오버 · 한계 섹션 · 탐색 경로 다시 보기 |
| 7. 사이드바 | 세 탭 · 항목 삭제 · 전체 삭제 확인 · 빈 상태 · 딥리서치 상태 배지 |

설계 확정 직후 먼저 그려 넘긴다. 기획자가 디자인하는 동안 구현을 진행하고, 디자인이 나오면 `research.css`·`components/research/*` 를 갈아입힌다.

---

## 9. 테스트·검증

| 영역 | 방법 |
|---|---|
| 기록 API | pytest(TestClient + 의존성 교체). upsert 반복 안전, 소프트 삭제, 남의 기록 404(읽기·쓰기·삭제), import 중복 무시, v1 id 결정론 변환, snapshot·params·ai 상한 413(UTF-8 바이트, import 는 넘친 칸만 비움), import 미래 시각 자르기, 딥리서치 상태 붙이기 |
| 스키마 | 모델 ↔ `0006` 마이그레이션 정합 테스트(`test_research_models.py` 방식) |
| 딥리서치 이벤트 | 워커·러너 테스트 확장: `status`·`step`·`counters`·`synth` 발행, **같은 내용이 `research_steps.result` 에 남는지**, snapshot 에 `result`·`job` 포함, 고유 논문 계수(재사용 근거 중복 없음), `seen_cnts` 스냅샷 왕복, 계획 태스크 이벤트 |
| 프론트 순수 로직 | **Vitest 를 개발용으로 추가**. 기록 저장소(서버 실패 → outbox, 쿼터 처리, v1 이전과 백업 보존), 마커 분해, 슬래시 파싱, URL 규칙(`?h=`, `?restore=` 별칭, v1 id 변환) |
| 화면 | 로컬 Nuxt 개발 서버 + API 를 운영 서버로 프록시해 브라우저로 직접 확인(진입·승인·진행·보고서·인용칩·사이드바·뒤로가기·새로고침). 딥리서치는 축소 파라미터로 몇 건만 |
| 운영 | 배포 뒤 **게이트웨이(92번 포트) 경유 SSE** 를 `curl -N` 으로 먼저 확인(round04a 에서 미검증). 그다음 브라우저로 전 과정 1회 |

기존 백엔드 테스트(549 passed)는 계속 통과해야 한다.

---

## 10. 배포·데이터 안전

- **DB**: 새 테이블 `history_items` 하나. 기존 테이블 ALTER·UPDATE·DELETE 없음. fastapi 기동 시 `create_all` 이 만들고 `alembic stamp 0006` 으로 맞춘다.
- **기존 데이터 무손실**:
  - 기존 `search_history`·`search_sessions` 는 읽지도 쓰지도 바꾸지 않는다(도서 검색 로그 쓰기는 기존 그대로).
  - 사용자 삭제는 소프트 삭제다.
  - 브라우저의 v1 기록은 서버 이전 성공 뒤에도 `skx_search_history_backup_v1` 로 남긴다.
  - 새 테이블도 기존 Postgres 정기 백업에 자동 포함된다.
- **재생성 컨테이너**: `nl-lib-fastapi` · `nl-lib-celery-research` · `nl-lib-celery-research-plan` · `nl-lib-nuxt`. **컨테이너별 Recreate** 로 하고 스택 업데이트는 하지 않는다 — 인덱싱 워커를 건드리지 않는다(recurring-gotchas 16번).
- **배포 전 확인**: `MILVUS_RECREATE_ON_MISMATCH=false`, 새 이미지를 서버에서 미리 `docker pull`(Portainer 의 re-pull 은 끈다 — recurring-gotchas 12번).

---

## 11. 범위 밖

- 로그인·사용자 계정(자리만 둔다 — D6)
- 채팅(BookChat·논문 채팅) 대화 기록의 서버 저장 — `kind` 를 하나 더하면 되도록 구조만 둔다
- 기존 `search_history` 정리(청크 원문 제거·보존 기한·연관 검색 로그 제외)와 `GET /api/books/history/{session_id}` 폐기
- 도서 입력창의 `+`, 딥리서치 외 `+` 메뉴 항목
- 인용 그래프, AI 다이어그램(round04 spec §9). 보고서 내보내기(Word·PDF)는 §14 로 범위에 들어왔다
- `pages/index.vue` 의 죽은 코드 정리(도서 추천 개편 spec `2026-09-15-search-top-pick-recommend-design.md` 몫)
- `app/api/admin.py` Milvus expression injection(대회 이후)

## 12. 위험과 대응

| 위험 | 대응 |
|---|---|
| 대회 일정(10월 초 추정) | §3 순서대로 자른다. 1·2 만 끝나도 기록과 진행 데이터는 준비된다 |
| 게이트웨이 경유 SSE 미검증 | 배포 직후 `curl -N` 으로 먼저 확인. 막히면 nginx 의 해당 location 에 `proxy_buffering off` 를 명시한다 |
| 기획자 디자인과의 병합 | 딥리서치는 별도 CSS·컴포넌트. 기존 파일 수정은 입력창 한 줄·사이드바·기록 로직뿐 |
| 기록 이전 중 손실 | 서버 성공 확인 전에는 v1 을 건드리지 않고, 성공 뒤에도 백업 키로 보존 |
| 서버 장애 시 기록 누락 | outbox 로 브라우저에 먼저 저장하고 재전송 |

## 13. 미확정

- 대회 정확한 일자(10월 초 추정)
- 화면 확인용 로컬 프록시가 붙을 운영 서버 주소(게이트웨이 92번 포트)
- Figma `paradeigma` 팀 계정이 화면 기획자와 함께 쓰는 계정인지(사용자가 (a) Figma 진행을 지시함)
- PDF 유무를 보고서에 미리 실을지(`has_pdf`) — 지금은 클릭 시 404 를 안내로 처리한다
- 하위질문별 근거 예산(round04a 이월)을 이번 화면 카운터와 함께 정할지

---

## 14. 보고서 작성 대기 화면·내보내기 (2026-09-28 추가)

### 14-0. 사용자 요청 (paraphrase)

> 보고서를 쓰는 동안(화면에 "보고서 작성 중 2/5" 만 뜨는 구간) 보여 주는 게 부족해서 기다리기 지루하다. 그리고 보고서를 문서로 내려받는 기능이 있었으면 좋겠다. 내려받기는 최종본이 완성된 뒤에 하는 게 깔끔하지만, 중간에도 저장할 수 있으면 그렇게 해 달라.

**배경(조사일 2026-09-28)**: 종합 단계에서 화면은 본문 카드(스피너 + "보고서 작성 중 2/5")와 진행 패널에 같은 한 줄만 그린다. 워커의 `synth` 이벤트가 `{section_idx, total, status}` 뿐이라 화면이 더 그릴 재료가 없다. 절 하나는 LLM 호출 1회(round04a 실측: GPU 가 한가할 때 절당 약 6초)지만 운영에서는 vLLM 을 적재 요약과 나눠 써 절마다 수십 초씩 늘어난다.

### 14-1. 결정

| # | 결정 | 근거 |
|---|---|---|
| E1 | **다 쓴 절부터 보고서 자리에 바로 보여 준다**(초안) + 절 목록·경과·남은 시간 | 기다리는 동안 읽을 것이 생기는 것이 지루함을 가장 크게 줄인다. 진행 표시만 늘리는 안(B)은 끝까지 읽을 것이 없고, 토큰 스트리밍(C)은 모델이 JSON 으로 답해 중간 글을 풀기 어렵고 인용 검증 전 글이 보였다 바뀐다 |
| E2 | 초안의 절은 **최종본과 같은 코드로 다듬은 절**이다 | `assemble_report` 의 절 단위 처리(마커 검증·요약 정리)를 함수로 떼어 둘이 함께 쓴다. 초안과 최종본의 글이 갈리지 않는다 |
| E3 | 내보내기는 **Word(.docx) + PDF(브라우저 인쇄 → PDF로 저장)** | Word 는 고쳐 쓰기 좋고 한글(HWP)에서도 열린다. PDF 는 인쇄 전용 화면이라 서버·의존성 변경이 없다. Markdown·HWPX 는 범위 밖 |
| E4 | **완성 뒤 [다운로드]가 기본, 작성 중·멈춘 초안도 [초안 저장]** | 사용자 요청. 초안도 보고서와 같은 모양이라 같은 코드로 문서를 만든다. 초안 문서는 제목·파일 이름에 초안임을 밝힌다 |
| E5 | Word·PDF 는 **문서 모델 하나**에서 만든다 | 인용 번호·참고문헌·부록이 두 형식에서 어긋나지 않는다. 모델 생성은 순수 함수라 Vitest 로 검증한다 |
| E6 | 문서에 **부록: 탐색 경로**를 싣는다 | 자기점검·재검색 과정이 딥리서치의 차별점이다(사용자 결정) |
| E7 | **DB 구조 변경 없음**, 백엔드 배포는 `nl-lib-celery-research` 하나 | 초안 데이터는 기존 `research_steps.result`(JSONB)에 담는다. 보고서를 쓰는 곳이 그 워커뿐이고 fastapi 는 단계 결과를 그대로 전달한다 |

### 14-2. 백엔드 — 절 미리보기

**절 단위 처리 분리 (`app/services/research/synthesizer.py`)**
- `assemble_report` 의 절 루프 본문을 `finalize_section(state, sec) -> (절, 집계)` 로 떼어 낸다. 절은 지금 `report.sections[i]` 와 같은 모양(`heading·intro·papers·future·evidence_chunks·chunk_scores`)이고, 집계는 무표기·삭제·미파싱·요약 누락·도입 없음·실패 절 수다. `assemble_report` 는 절마다 이 함수를 부르고 집계를 더한다 — **출력은 한 글자도 바뀌지 않는다**(기존 테스트가 그대로 통과해야 한다).
- `section_evidence(state, sec) -> dict` — 그 절이 인용한 근거만(`papers[].evidence` 와 도입·향후 과제의 마커) `report.evidence` 와 같은 모양으로 만든다. 대목은 그 절의 `evidence_chunks` 가 가리키는 것만 점수순으로 싣는다(없으면 `_serialize_evidence` 와 같은 규칙으로 전부).

**진행 콜백 (`synthesize` 의 `on_section`)**
- 시그니처를 `on_section(idx, total, status, info)` 로 넓힌다. `info` 는 `{subq_idx, heading}`, 절을 끝낼 때(`done`·`failed`)는 여기에 `section`(finalize 한 절)과 `evidence`(section_evidence)를 더한다. 서술을 끝내 받지 못한 절(`failed`)도 논문 목록만 있는 절로 싣는다.

**워커 (`app/workers/research_tasks.py` 의 `_SynthProgress`)**
- `synth` 이벤트: `{section_idx, total, status, subq_idx, heading}` + 시작 때 `started_at`(ISO, UTC), 끝날 때 `duration_ms`(워커가 잰 값 — 화면 시계와 무관)와 `section`·`evidence`.
- 단계 `result`: `sections_total`, `sections:[{idx, status, subq_idx, heading, started_at, duration_ms, section?}]`, `evidence:{…}`(끝난 절들의 근거 합집합). 절이 바뀔 때마다 지금처럼 `_save_progress` 로 저장한다 → **새로고침·재접속한 화면이 이미 쓴 절을 그대로 받는다**(snapshot 의 `steps[].result`).
- **알리는 `step` 이벤트는 가볍게**: `_save_progress` 는 저장 뒤 단계 `result` 전체를 `step` 이벤트로 흘린다. 종합 단계에서는 절이 쌓일수록 매번 전부를 다시 보내게 되므로, 이벤트에는 `section`·`evidence` 를 뺀 `result` 를 싣는다. 절 내용은 `synth` 이벤트가 절마다 한 번만 나른다. 화면은 가벼운 `step` 이벤트가 이미 받은 절 내용을 지우지 않게 합친다(§14-3).
- **완료로 닫을 때**(`_finish(..., "done")`)는 `section`·`evidence` 를 뺀다 — 최종 보고서와 중복이다. **실패·취소로 닫을 때는 남긴다** — 멈춘 초안을 보여 주고 내려받을 원천이다.
- 크기: 절 하나에 수 KB~수십 KB(대목 원문이 대부분). 하위질문 상한 12 · 절당 논문 5 에서도 최종 보고서의 `evidence` 와 같은 규모다.
- 재시도(`POST /retry`, `stage=explored`)는 새 종합 단계(새 `seq`)를 만든다 → 초안은 처음 절부터 다시 쌓인다.

### 14-3. 화면 — 작성 중

**데이터 (`types/research.ts`, `utils/researchEvents.ts`)**
- `SynthEvent`·`SynthSectionView`·`SynthView` 를 넓힌다: 절마다 `subqIdx·heading·startedAt·durationMs·section`, `SynthView.evidence`(근거 합집합 — 같은 근거가 두 절에 나오면 대목을 `chunk_id` 로 합친다).
- `synth` 이벤트와 단계 `result`(snapshot·step 이벤트) 어느 쪽으로 와도 같은 모양으로 합친다. `section` 이 없는 값이 있는 값을 덮지 않는다. 새 시도(`seq` 가 바뀜)면 비운다 — 기존 `sameAttempt` 규칙.
- 새 필드가 없는 옛 잡·옛 서버는 지금 동작("보고서 작성 중 2/5")으로 되돌아간다.

**순수 로직 (`utils/researchDraft.ts` 신규)**
- `draftReport(view)` — 끝난 절들을 절 순서대로 모아 `ResearchReport` 모양(질문·절·근거, `limitations` 없음, `stats` 는 라이브 카운터)으로 만든다. 절이 하나도 없으면 null.
- `synthEta(view, now)` — `{done, total, runningElapsedMs, remainingMs|null}`. 남은 시간은 끝난 절들의 `durationMs` 평균 × 남은 절 수(쓰는 중인 절은 평균에서 경과를 뺀 값, 0 미만이면 0). 끝난 절이 없으면 null. 쓰는 중인 절의 경과는 `startedAt` 기준이고 음수가 되지 않게 자른다(서버·브라우저 시계 차이).

**배치 (`pages/research/[id].vue` 의 종합 단계 본문 — 배치 A·B 공통)**
- **보고서 작성 현황 카드**(`components/research/SynthProgressCard.vue` 신규)
  - 진행 막대 + "2/5 절 완료 · 약 1분 30초 남음"(첫 절 전에는 "첫 절을 쓰는 중")
  - 절 목록: `✓ 완료 0:38` · `◐ 작성 중 0:12`(1초마다 갱신) · `· 대기` · `✕ 서술 받지 못함`. 제목은 하위질문(`heading`)
  - **[초안 저장 ▾]** — 끝난 절이 하나 이상일 때만 누를 수 있다
  - **인터랙션**(§7-4): 완료된 절 항목을 누르면 초안의 그 절로 부드럽게 이동하고 잠깐 강조한다(사용자가 누를 때만 — 자동 스크롤은 없다). 항목에 포인터·초점을 올리면 초안의 해당 절 테두리가 함께 강조된다. 진행 막대는 끊기지 않게 늘어나고, 방금 완성된 항목은 체크 표시가 짧게 튀어 오른다. 움직임은 모두 `prefers-reduced-motion` 이면 끈다
- **보고서 초안** — `ReportView` 에 `draft` 모드를 더해 그린다: 머리에 "작성 중" 배지, 끝난 절은 최종본과 똑같이(인용칩·원문 보기 동작), 쓰는 중인 절은 제목 + 은은하게 움직이는 회색 줄, 대기 절은 제목 + "작성 대기". 한계 섹션·[다운로드]는 없다.
- 절이 완성되면 제자리에 부드럽게 나타난다(애니메이션은 `prefers-reduced-motion` 이면 끈다). **자동 스크롤하지 않는다** — 초안을 읽는 사람을 끌고 가지 않는다. 절 완성은 `aria-live="polite"` 로 한 번 알린다.
- 진행 패널(카운터·탐색 타임라인)은 그대로 둔다.
- **작성 중 실패·취소**: 실패·취소 카드 아래에 초안을 "완성되지 않은 초안입니다" 안내와 함께 보이고 [초안 저장]을 둔다. 재시도하면 종합 단계로 돌아가 초안이 새로 쌓인다.
- **완료**: 최종 보고서를 GET 으로 받으면 초안을 최종본으로 바꾼다(서론·한계가 붙는다). 받는 동안과 받기에 실패해 다시 시도하는 동안에도 초안이 있으면 초안을 그대로 두고, 그 위에 지금의 불러오는 중·다시 불러오기 안내를 작게 둔다. 초안이 없으면(옛 잡) 지금 카드 그대로다. 완료 뒤 새로 연 화면은 보고서를 바로 받으므로 초안이 필요 없다 — 완료로 닫힌 단계에는 미리보기가 없다(§14-2).

### 14-4. 내보내기

**버튼 (`components/research/ReportDownloadMenu.vue` 신규)**
- 완성된 보고서 머리의 [링크 복사] 옆 **[다운로드 ▾]**, 작성 현황 카드와 멈춘 초안의 **[초안 저장 ▾]**. 메뉴: "Word 문서(.docx)" · "PDF로 저장". 키보드는 `+` 메뉴와 같은 규칙(`utils/menuNav.ts`).

**문서 모델 (`utils/reportDocument.ts` 신규, 순수 함수)**
- 입력: `{question, range, generatedAt, url, sections, evidence, limitations | null, trail, draft: {done, total} | null}`. 페이지가 최종 보고서(`view.report`) 또는 초안(`draftReport`)에서 만든다. 초안의 부록은 화면의 탐색 타임라인(`view.subqs` — 탐색은 이미 끝났다)에서, 최종본은 `report.trail` 에서 만든다.
- 출력: 블록 목록(제목·메타·문단·목록·참고문헌) — 문단은 글 조각과 인용 번호의 배열.
- 구성
  1. 제목(질문). 초안이면 "(초안 · 5개 절 중 2개 작성)"
  2. 메타: 생성 일시 · 수록 범위(`rangeLabel`) · 연구 주소(`<origin>/research/<id>`)
  3. 서론 한 줄(`reportIntro` — 화면과 같은 문장)
  4. 절: "1. 소제목" → 도입 → "대표 논문"(`저자 외 (연도) 「제목」 — 요약 [n]`) → "향후 과제" 목록. 도입이 없는 절은 화면과 같은 안내 문장
  5. **이 보고서의 한계**(최종본). 한계가 없으면 화면과 같은 문구. 초안이면 대신 "작성 중에 저장한 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다."
  6. **부록: 탐색 경로** — 하위질문마다 검색어 이력(→ 재검색), 판정, 근거 수
  7. **참고문헌**
- **인용 번호**: 문서에 처음 나온 순서(절 순서 → 도입 → 대표 논문 → 향후 과제)로 `[1]`, `[2]` … 를 매긴다. 같은 근거는 어디서 나와도 같은 번호. 참고문헌에는 인용된 근거만 싣는다.
- **참고문헌 한 줄**: `[n] 저자1, 저자2 (연도). 제목. 학술지명, 권(호). 인용 쪽: 12–13, 20` — 메타가 빠진 칸은 생략한다(`splitAuthors`·`pubYear` 재사용). 인용 쪽은 그 근거를 인용한 절들이 쓴 대목(`evidence_chunks` → `chunks[].page_start·page_end`)을 모아 정렬·중복 제거한다. 쪽 번호는 화면의 `pageLabel`·`pdfPage` 와 같은 규칙이다 — 저장값은 0-based 라 1 을 더해 적고, `page_start` 가 0 인 대목은 쪽 정보 없음으로 보고 뺀다(§6-3). 남는 쪽이 없으면 "인용 쪽" 칸을 싣지 않는다.
- **파일 이름**: `딥리서치_<질문 앞 20자>_<YYYYMMDD>.docx`(초안은 `…_초안.docx`). 파일 이름에 못 쓰는 글자(`\ / : * ? " < > |`·제어문자)는 빼고 공백은 `_` 로.

**Word (`utils/reportDocx.ts` 신규)**
- `docx`(npm) 로 브라우저에서 만든다. **다운로드를 누를 때 동적 import** 한다 — 평소 화면 번들에 넣지 않는다. 의존성 추가는 이것 하나.
- A4, 글꼴 맑은 고딕, 제목·절 제목·소제목·본문 크기 구분, 바닥글 쪽 번호. 인용 번호는 본문과 같은 줄의 `[n]`.

**PDF (`components/research/ReportPrint.vue` 신규)**
- 같은 문서 모델을 인쇄 전용 화면으로 그린다(화면에서는 숨김). [PDF로 저장]을 누르면 그린 뒤 `window.print()` 를 부르고, `@media print` 로 사이드바·머리·버튼·진행 패널을 숨긴 A4 문서만 찍는다. 인쇄하는 동안 `document.title` 을 파일 이름으로 바꿔 "PDF로 저장"의 기본 파일명이 되게 하고, `afterprint` 에서 되돌린다.
- 대상 브라우저: Chrome·Edge(인쇄 창의 머리글·바닥글은 사용자 설정이다).

### 14-5. 코드 구조

| 파일 | 변경 |
|---|---|
| `app/services/research/synthesizer.py` | `finalize_section`·`section_evidence` 분리, `on_section` 에 `info` |
| `app/workers/research_tasks.py` | `_SynthProgress` 확장, 종합 단계의 가벼운 `step` 이벤트, 완료 시 미리보기 제거 |
| `frontend/types/research.ts` · `utils/researchEvents.ts` | 절 미리보기 합치기 |
| `frontend/utils/researchDraft.ts` · `reportDocument.ts` · `reportDocx.ts` (신규) | 초안·남은 시간·문서 모델·Word |
| `frontend/components/research/SynthProgressCard.vue` · `ReportDownloadMenu.vue` · `ReportPrint.vue` (신규) | 작성 현황·내보내기 메뉴·인쇄 화면 |
| `frontend/components/research/ReportView.vue` · `pages/research/[id].vue` · `assets/css/research.css` | 초안 모드·배치·인쇄 CSS |
| `frontend/package.json` | `docx` 추가 |

### 14-6. 테스트·검증

| 대상 | 방법 |
|---|---|
| 절 단위 처리 분리 | 기존 보고서 테스트 무변경 통과 + 같은 입력에서 `finalize_section` 의 절 == `assemble_report` 의 절 |
| 진행 콜백·이벤트 | 시작에 `subq_idx·heading·started_at`, 끝에 `duration_ms·section·evidence`(그 절이 인용한 근거·대목만), 실패 절은 논문 목록만 |
| 단계 result | 절마다 저장, 가벼운 `step` 이벤트에는 `section`·`evidence` 없음, 완료로 닫으면 제거·실패·취소로 닫으면 유지, 절 6개·논문 30편 기준 크기 확인 |
| 화면 데이터 | 이벤트 누적, snapshot 복원, 가벼운 step 이벤트가 내용을 지우지 않음, 새 시도면 비움, 옛 신호 폴백 |
| 남은 시간 | 끝난 절 없음(null), 평균 계산, 쓰는 중인 절 경과 차감, 음수 방지 |
| 문서 모델 | 첫 등장 순 번호, 같은 근거 같은 번호, 미인용 근거 제외, 인용 쪽 정렬·중복 제거·0 쪽 제외, 초안 표시·한계 대체 문구, 도입 없는 절, 한계 없음 문구, 부록 |
| Word | Node 에서 실제로 만들어 압축을 풀고 `word/document.xml` 에 질문·`[1]`·참고문헌이 있는지 |
| 파일 이름 | 금지 문자 제거·20자 자르기·초안 접미 |
| 공통 | `npx vitest run` · `npx nuxi typecheck` · `npm run build` · `pytest` |
| 화면(로컬) | 완성된 연구로 [다운로드] Word·PDF — 운영 서버 프록시(`NUXT_DEV_API_TARGET`)가 필요하다 |
| 화면(운영, 배포 뒤 잡 1회) | 절이 하나씩 나타나는지, 작성 중 새로고침 복원, 남은 시간, [초안 저장], 완성 뒤 [다운로드] Word(Word·한글에서 열기)·PDF |

### 14-7. 배포

1. 도는 딥리서치 잡이 없는지 확인한다 — 종합 중에 워커를 Recreate 하면 그 잡은 회수기가 `failed` 로 떨어뜨린다.
   `select id, status, stage from research_jobs where status in ('approved','queued','running');`
2. fastapi 이미지 빌드·푸시(`NL_LIB_FASTAPI_IMAGE=landsoftdocker/nl-lib-fastapi:latest bash scripts/build_dev_images.sh fastapi`) → 서버에서 `docker pull` → **`nl-lib-celery-research` 하나만** Recreate(re-pull 끔). `nl-lib-fastapi`·`nl-lib-celery-research-plan`·적재 워커는 그대로 둔다 — 같은 `:latest` 를 pull 해도 돌고 있는 컨테이너는 바뀌지 않는다.
3. nuxt 이미지 빌드·푸시 → pull → `nl-lib-nuxt` Recreate → **`docker exec nl-lib-gateway nginx -s reload`**(Recreate 로 바뀐 컨테이너 IP 를 게이트웨이가 다시 찾게 — 2026-09-28 502 재발 방지).
4. 잡 1회로 §14-6 의 운영 화면 확인.

### 14-8. 범위 밖

- Markdown·HWPX 내보내기, 서버에서 만드는 PDF
- 절 서술의 토큰 스트리밍(타이핑 효과)
- 탐색 단계(하위질문 검색·점검) 화면 보강 — 이번 요청은 종합 단계다

### 14-9. 위험과 대응

| 위험 | 대응 |
|---|---|
| 초안과 최종본의 글이 다름 | 같은 `finalize_section` 을 쓰고 동일성 테스트로 묶는다 |
| 단계 result·snapshot 이 커짐 | 절 미리보기는 완료 시 지우고, 라이브 `step` 이벤트에는 싣지 않는다 |
| `docx` 번들 크기 | 동적 import — 다운로드를 누를 때만 받는다 |
| 인쇄 결과가 브라우저마다 다름 | 대상은 Chrome·Edge, 인쇄 CSS 는 A4 기준 |
| 워커만 새 이미지(혼재 버전) | fastapi 는 단계 result 를 그대로 전달하므로 영향 없다. 화면은 새 필드가 없으면 옛 동작으로 되돌아간다 |
