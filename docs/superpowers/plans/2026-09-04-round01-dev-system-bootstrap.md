# round01 — 개발 체계 도입 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** museum 스타일 개발 체계(CLAUDE.md·GIT_WORKFLOW.md·round 워크플로우·`.claude/` 자동화·`research/` 산출물 규칙)를 NL-Lib에 이식하고, 루트·`scripts/`에 흩어진 118개(scripts) + 6개(root) 실험 산출물을 주제별 `research/`로 재배치한다.

**Architecture:** 신규 파일은 전부 문서/설정(마크다운·YAML frontmatter)이라 고전적 red-green TDD 대상이 아니다. 각 문서 Task는 "파일 없음 확인 → 전문 작성 → grep/구조 검증 → 커밋"으로 진행하고, 파일 이동 Task는 "git mv → 위치·개수 검증 → (해당 시) py_compile 검증 → 커밋"으로 진행한다.

**Tech Stack:** Git, Markdown, YAML frontmatter(.claude 스킬/에이전트), Python(py_compile 검증), Bash.

**선행 완료 사항 (이 plan 실행 전 이미 끝남 — 재실행 불필요):**
- 브랜치 캐치업: `SKOVIX-JeongHyun`(로컬 gitignore 수정 2커밋 포함) → `main` 병합 완료, `origin/main`에 push 완료(`5144cdd`).
- `feat/search-session-history` 브랜치 로컬·원격 삭제 완료(사용자 승인 하 폐기).
- GitHub Desktop 자동 stash pop 완료 — 4개 실험 수정(`scripts/build_wikisource_manifest.py`, `scripts/odl_lengths_result.json`, `scripts/audit_routing_fix_result.json`, `scripts/fitz_lengths_result.json`)은 discard, 루트 14개 미추적 파일 + `app/scripts/recheck_table_fill.py`는 작업 트리에 복원됨(미추적 상태 유지).
- `.gitignore`의 `/docs`·`/scripts`·`.claude/` 오추적 제외 버그 수정 및 기존 문서 백업 완료.
- **격리 워크트리**: `C:\Users\LANDSOFT\mygit\NL_library_AI\.claude\worktrees\round01-dev-system-bootstrap`, 브랜치 `feat/round01-dev-system-bootstrap-wt`(`EnterWorktree`가 `origin/main`에서 `feat/round01-dev-system-bootstrap-wt`으로 fresh 분기했다가, GIT_WORKFLOW.md의 `<type>/round<NN>-<설명>` 규칙을 따르도록 rename — 공유 체크아웃에 미리 만들어 둔 `feat/round01-dev-system-bootstrap`(접미 `-wt` 없음)은 이름 충돌로 그 이름을 그대로 쓸 수 없어 `-wt` 접미로 구분. 그 빈 브랜치는 최종 정리 시 삭제 대상).
- **Task 1 완료** (CLAUDE.md): 최초 구현 `f5983bb` → 리뷰(spec 컴플라이언스 ✅, 코드품질 리뷰에서 Important 4건 발견) → 수정 `11815ae`. 아래 Task 1 본문은 **수정 반영된 최종본**이다.

이 plan의 모든 Task는 `feat/round01-dev-system-bootstrap-wt` 브랜치(워크트리) 위에서 진행한다.

---

### Task 1: CLAUDE.md — ✅ 완료 (`f5983bb` → 리뷰 수정 `11815ae`)

**Files:**
- Create: `CLAUDE.md`

- [x] **Step 1: 파일 없음 확인**

Run: `test -f CLAUDE.md && echo EXISTS || echo MISSING`
Expected: `MISSING`

- [x] **Step 2: 작성 (리뷰 수정 반영 최종본)**

```markdown
# CLAUDE.md — 개발 운영 진입점

> Claude가 이 프로젝트에서 어떻게 작동하고 어떤 작업에 어디를 보는지의 단일 진입점.
> 상세는 각 문서로 링크(중복 금지). 충돌 시 이 파일이 우선.

## 0. 병렬 작업 원칙
- 독립적인 작업(백엔드 API ↔ 프론트 ↔ 리서치 분석)은 가능하면 서브에이전트로 병행한다. 순차 진행은 의존성이 있을 때만.

## 1. 산출물 위치 규칙 (불변)
- 루트에는 운영 파일(`CLAUDE.md`·`GIT_WORKFLOW.md`·`README.md`·`.gitignore`·`docker-compose*.yml` 등 설정)만 둔다. 그 외 루트에 남아있는 개별 파일(예: `INDEX.README.md`·`inspect_odl.py`·`migrate_add_*.sql`)은 round01 스코프 밖의 기존 잔재로, 정리는 다음 라운드로 이월한다.
- `app/`·`frontend/`·`infra/` = 실제 서비스 코드/배포 설정의 정본. 이름을 바꾸지 않는다.
- `docs/` = 문서 전용.
- `scripts/` = **재실행되는 운영 도구**만 둔다 — 파이프라인이 지금도 호출하거나 반복 실행하는 것(`scripts/bulk_ingest/`, 매니페스트 빌더 등).
- `research/` = **1회성 실험**(스크립트 + 그 산출물)만 둔다. "이 스크립트를 다시 실행할 일이 있는가"가 `scripts/`와의 구분 기준이다. 코드와 산출물은 분리하지 않는다(재현 가능성 유지) — 실행해서 파일을 만들어내는 1회성 스크립트는 항상 대응하는 `research/<주제>/`에 산출물과 함께 둔다.
- 디버그 로그(`*.log`, `*_debug_out*.txt` 등)는 커밋하지 않는다(`.gitignore`).

## 2. 개발 어휘 — round
- **round**: 사용자 프롬프트 1개 → 구현 → 리뷰 → dev 머지(사용자 승인) → dev→main 머지 + push까지가 한 라운드. 라운드당 spec 1(브레인스토밍) + 완료노트 1 + 교본(가이드) 1권.
- 라운드 번호는 2자리(`round01`, `round02`…). 성격이 다른 여러 덩어리로 쪼개지면 소문자 접미(`round01a`, `round01b`…)를 붙인다. 접미는 성격 라벨이며 실행 순서가 아니다.
- 브랜치명은 영문 kebab-case만 사용한다(Windows·CI 호환성 — 한글 브랜치명 금지).
- 생애주기·브랜치 모델 상세: `GIT_WORKFLOW.md`.

## 3. 세션 시작 시 확인
- 새 세션(=새 라운드)을 열면 먼저 `docs/roadmap/00_status.md`(현재 상태·다음 할 일)와 직전 라운드 완료노트(`docs/roadmap/round<NN>-완료노트.md`)를 읽어 맥락을 이어받는다.
- 문서와 코드가 어긋나면 코드가 실제이니 문서를 고친다.

## 4. 어디를 보나
| 알고 싶은 것 | 위치 |
|---|---|
| 브랜치·커밋·라운드 생애주기·개발 환경 | `GIT_WORKFLOW.md` |
| 현재 상태·다음 할 일 | `docs/roadmap/00_status.md` |
| 라운드 완료 기록 | `docs/roadmap/round<NN>-완료노트.md` |
| 라운드 교본(클론코딩 + 면접 Q&A) | `docs/guides/round<NN>/` |
| 기능 설계(브레인스토밍 spec) | `docs/specs/` · `docs/superpowers/specs/` |
| 구현 계획(writing-plans) | `docs/superpowers/plans/` |
| 코딩 표준 | `docs/standards/coding-standard.md` |
| 반복 함정(라이브에서만 드러나는 버그) | `docs/ops/recurring-gotchas.md` |
| 대량 인덱싱 배포·검증 런북 | `docs/bulk_ingest_runbook.md` |
| 디자인 정본(미도입 — 스텁) | `docs/design/README.md` |
| 시스템 아키텍처 다이어그램 | `docs/architecture.drawio` |
| 라운드 종료 절차 자동화 | `.claude/skills/round-finish/SKILL.md` |
| 정적 코드 리뷰 서브에이전트 | `.claude/agents/code-reviewer.md` |
| 기능·아키텍처 설명·다음 개선 백로그(§10 로드맵) | `README.md` |
```

- [x] **Step 3: 검증**

Run: `grep -c "^## " CLAUDE.md`
Expected: `5` (§0~§4)

Run: `grep -q "workspace" CLAUDE.md && echo FOUND || echo CLEAN`
Expected: `CLEAN`

- [x] **Step 4: 커밋** — `f5983bb`, 리뷰 수정 `11815ae`

---

### Task 2: GIT_WORKFLOW.md — ✅ 완료 (`e2911cf` → 리뷰 수정 `457ee1b` → `132982f`)

**Files:**
- Create: `GIT_WORKFLOW.md`

- [x] **Step 1: 파일 없음 확인**

Run: `test -f GIT_WORKFLOW.md && echo EXISTS || echo MISSING`
Expected: `MISSING`

- [x] **Step 2: 작성**

```markdown
# Git Workflow

> 이 프로젝트(NL-Lib)의 브랜치·커밋·머지 규칙. 모든 작업은 이 문서를 따른다.

## 브랜치 모델

| 브랜치 | 역할 | 규칙 |
|---|---|---|
| `main` | 배포 기준 | 평소 직접 작업 금지. 라운드 종료 시 사용자 승인 하에 `dev → main` 머지 후 `origin` push. |
| `dev` | 통합 브랜치 | 완성된 작업 브랜치가 모이는 곳. |
| `<type>/round<NN>-<설명>` | 작업 브랜치 | `dev`에서 분기. 한 작업 단위 = 한 브랜치. |

- 타입(Conventional): `feat`·`fix`·`docs`·`chore`·`refactor`·`test`
- 설명은 영문 kebab-case(예: `feat/round02-search-quality`) — 한글 브랜치명은 Windows·CI 호환성 문제로 쓰지 않는다.
- 서브라운드: 한 라운드가 성격이 다른 여러 덩어리로 쪼개지면 `round<NN>a`~`round<NN>f`로 표기(예: `round02a`). 접미는 성격 라벨이며 실행 순서가 아니다.

## 흐름

```
dev ─분기→ <type>/round<NN>-<설명> ─개발·커밋─→ [사용자 승인] ─merge→ dev ─[라운드 종료 승인]→ main ─push→ origin
```

1. `dev`에서 작업 브랜치 분기
2. 개발 → 커밋 → 원격 푸시
3. 완성되면 사용자 승인을 받은 뒤 `dev`로 머지 (승인 전 머지 금지)
4. `dev` 푸시
5. 라운드 종료(사용자 승인): `dev → main` 머지 + `origin` push

## 개발 환경

- **prod** (`docker-compose.yml`): 전체 스택 — API·워커·데이터 계층(postgres·redis·minio·milvus)·GPU 서비스(vllm·gemma·flux).
- **dev** (`docker-compose.dev.yml`): 앱 계층(`fastapi-dev`·celery 워커 4종·`nuxt-dev`·`gateway-dev`)과 데이터 계층(`postgres-dev`·`redis-dev`·`minio-dev`·`milvus-dev`, DB명 `nl_lib_dev` 등 `_dev` 접미)을 **모두** prod와 별도로 띄운다. GPU를 크게 먹는 vllm/gemma/flux만 prod 스택 컨테이너를 `nl-lib-net` 경유로 그대로 공유한다(따로 띄우지 않음).
- 두 스택은 GPU 서비스만 공유하고 나머지(앱+데이터)는 완전히 분리된 단일 서버 구조다. museum류의 별도 물리 노드 SSH 터널은 필요 없다.
- 개발 사이클: `docker compose -f docker-compose.dev.yml up -d`로 dev 스택(앱+데이터) 전체 기동 → 코드 개발·검증 → 확정되면 위 브랜치 흐름대로 병합.

## 머지 승인 규칙

- 작업 브랜치 → `dev`: 매번 사용자 채팅 승인 필수. 협업자가 없으므로 리뷰는 자가 점검 체크리스트(테스트 green + 관련 파이프라인 수동 스모크 + 문서 갱신 여부)로 한다.
- `dev` → `main`: 라운드 종료 판단·승인은 사용자. 승인되면 `dev→main` 머지 + `origin` push.

## 커밋 메시지

- 기존 관행 유지: `[Type] 설명` (한국어, 대괄호 태그 + 한 줄 요약)
- Type: `Feat`·`Fix`·`Docs`·`Chore`·`Refactor`·`Test`
- 예) `[Feat] 하이브리드 검색 RRF 가중치 조정`, `[Fix] 이미지 업로드 408 재시도`, `[Docs] round01 가이드 추가`
- 본문은 꼭 필요할 때만 몇 줄. `Co-Authored-By` 트레일러는 넣지 않는다(기존 커밋 이력에 없던 관행 — 유지).

## 개발 가이드 문서 (필수)

- 1 라운드 = 1 교본(가이드). `docs/guides/round<NN>/`에 저장(템플릿: `docs/guides/_TEMPLATE.md`).
- 구성: paraphrase된 라운드 프롬프트 → 전 코드/문서 클론코딩 가능하게 수록(발췌·플레이스홀더 금지) → 면접식 Q&A.
- 리뷰 흐름: 작업 브랜치 푸시 → 가이드+diff 대조 리뷰(`.claude/agents/code-reviewer.md`) → 승인 → `dev` 머지.

## 라운드 생애주기

1. 프롬프트→spec: `docs/superpowers/specs/`에 브레인스토밍 설계 작성(브레인스토밍 스킬).
2. 계획: `docs/superpowers/plans/`에 구현 계획 작성(writing-plans 스킬).
3. 구현: TDD·교육적 코드(`docs/standards/coding-standard.md`).
4. 검증: 단위테스트 + 관련 기능 수동 스모크.
5. 리뷰: `.claude/agents/code-reviewer.md` 서브에이전트로 정적 리뷰 → 발견 수정.
6. 머지: 작업 브랜치 → 사용자 승인 → `dev`.
7. 라운드 종료: 완료노트 작성(`docs/roadmap/round<NN>-완료노트.md`, 템플릿 `docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md`) → `docs/roadmap/00_status.md` 갱신 → `dev→main` 머지 + `origin` push. 자동화: `/round-finish` 스킬.

## 디자인 트랙 (미도입)

- 현재 Figma·퍼블리싱 트랙 없음. 도입되면 `docs/design/README.md`의 버전 폴더 방식을 따른다.
- 라운드 완료노트의 「디자인 참조」 항목은 도입 전까지 "해당 없음 — 디자인 트랙 미도입"으로 기입한다.

## 비고

- 비밀정보·데이터·미공개 자료는 커밋하지 않는다(`.gitignore`).
- 실행해서 파일을 만들어내는 1회성 스크립트는 대응하는 `research/<주제>/`에 산출물과 함께 둔다(`CLAUDE.md` §1).
```

> **참고**: 위 "작성" 코드블록은 최초 spec이다. 코드품질 리뷰에서 `## 개발 환경`(dev 스택이 이미지 pull 전용·GPU서버 전용·external volume 의존이라는 사실 누락 등)·`## 머지 승인 규칙`(리뷰 게이트 서술 모순)·`## 흐름`(리뷰 단계 누락) 3곳에 Important 이슈가 나와 `132982f`로 수정 반영됐다. **최종 진실은 커밋된 `GIT_WORKFLOW.md` 파일이다** — Task 13(교본)은 이 코드블록이 아니라 실제 파일을 `Read`해서 옮겨 담는다.

- [x] **Step 3: 검증**

Run: `grep -c "^## " GIT_WORKFLOW.md`
Expected: `9` (브랜치 모델·흐름·개발 환경·머지 승인 규칙·커밋 메시지·개발 가이드 문서·라운드 생애주기·디자인 트랙·비고 — 최초 plan 작성 시 8로 오기재됐던 것을 Task 2 구현자가 발견해 정정)

- [x] **Step 4: 커밋**

```bash
git add GIT_WORKFLOW.md
git commit -m "[Docs] round01 — GIT_WORKFLOW.md 추가"
```

---

### Task 3: docs/roadmap/00_status.md + 완료노트 템플릿 — ✅ 완료 (`5b5c914` → 리뷰 수정 `b972752`)

> 최종 파일은 코드블록보다 진전됨(리뷰로 §10 중복 제거·완료노트 링크·리뷰게이트 체크박스 2개·spec/plan/교본 경로 필드 추가) — Task 13은 실제 파일을 `Read`한다.

**Files:**
- Create: `docs/roadmap/00_status.md`
- Create: `docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md`

- [x] **Step 1: 디렉토리·파일 없음 확인**

Run: `test -d docs/roadmap && echo EXISTS || echo MISSING`
Expected: `MISSING`

- [x] **Step 2: `docs/roadmap/00_status.md` 작성**

```markdown
# 현재 상태 · 다음 할 일

최종 갱신: 2026-09-04 (round01)

## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 진행 중.
- 다음에 무엇을 개선할지는 코드/기능 단위로 `README.md` §10(앞으로 고치면 좋을 것)에 상시 갱신된다 — 라운드 착수 전 그 목록도 함께 확인한다.

## 다음 할 일
- round01 완료 후: 다음 라운드 범위는 미정 — 착수 시 이 문서에 갱신하고, `README.md` §10의 백로그 중 우선순위를 정해 반영한다.

## 라운드 이력
| 라운드 | 요약 | 상태 |
|---|---|---|
| round01 | 개발 체계 도입(museum 스타일 이식) | 진행 중 |
```

- [x] **Step 3: `docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md` 작성**

```markdown
# round<NN> 완료노트

날짜: <YYYY-MM-DD>
브랜치: `<type>/round<NN>-<설명>`

## 한 일
-

## 결정
-

## 디자인 참조
- 버전:
- 참조 화면:
- 참조 자산:
- 미참조 사유:

(디자인 트랙 미도입 시: "해당 없음 — 디자인 트랙 미도입"으로 위 4항목을 대체)

## 이월
-

## 다음 라운드 진입점
-

## 상태
- [ ] 테스트 green
- [ ] 수동 스모크 확인
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push 완료
```

- [x] **Step 4: 검증**

Run: `test -f docs/roadmap/00_status.md && test -f docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md && echo BOTH_EXIST`
Expected: `BOTH_EXIST`

- [x] **Step 5: 커밋**

```bash
git add docs/roadmap/00_status.md docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md
git commit -m "[Docs] round01 — 상태 문서·완료노트 템플릿 추가"
```

---

### Task 4: docs/guides/_TEMPLATE.md — ✅ 완료 (`e6e5877` → 리뷰 수정 `db142ae`)

> 리뷰에서 Critical 발견: `### 2.5 디자인 참조 요약`이 `### 2.N` 구현 서브섹션 시퀀스와 헤딩레벨 충돌 — 5개 이상 서브섹션(Task 13은 9개)이 있는 라운드에서 `### 2.5`가 중복돼 검증 grep이 깨짐. `## 2.5`로 h2 승격해 수정. 헤더 블록쿼트(발췌·플레이스홀더 금지 상설화)·중첩펜스 안내도 함께 추가.

**Files:**
- Create: `docs/guides/_TEMPLATE.md`

- [x] **Step 1: 작성**

```markdown
# round<NN> 교본 — <제목>

## 0. 사용자 프롬프트 (paraphrase)
> <사용자가 이 라운드에서 실제로 요청한 내용을 의도가 드러나게 재서술>

## 1. 설계 요약
(spec 링크: `docs/superpowers/specs/<파일>`)

## 2. 구현 (클론코딩)
### 2.1 <파일/컴포넌트명>
**파일**: `<경로>`

```<언어>
<전체 코드 — 발췌 금지>
```

### 2.5 디자인 참조 요약
(디자인 트랙 미도입 라운드는 "해당 없음 — 디자인 트랙 미도입"으로 기입)

## 3. 검증
- 실행 명령과 기대 출력을 그대로 적는다.

## 4. 면접식 Q&A
**Q1. <질문>**
A. <답변>
```

- [x] **Step 2: 검증**

Run: `test -f docs/guides/_TEMPLATE.md && echo EXISTS`
Expected: `EXISTS`

- [x] **Step 3: 커밋**

```bash
git add docs/guides/_TEMPLATE.md
git commit -m "[Docs] round01 — 라운드 교본 템플릿 추가"
```

---

### Task 5: docs/standards/coding-standard.md — ✅ 완료 (`0086ef1` → 리뷰 재작성 `0b338e7` → 정밀도 보정 `4778d4e`)

> **가장 큰 리뷰 발견**: 최초 spec은 "이미 따르고 있는 관행"이라 주장했지만 실측 결과 다수가 거짓이었다(API 얇음·ORM 미유출·비동기 테스트·LLM 격리·의존방향 5개 항목 전부 반례 존재). "지향점 vs 준수 예 vs 실측 반례(백로그)"로 재구성해 정정. **Task 8(`.claude/agents/code-reviewer.md`)의 스펙도 같은 거짓 의존방향 체인을 하드코딩하고 있어 함께 정정함** — 아래 Task 8 섹션은 이미 수정 반영된 버전이다.

**Files:**
- Create: `docs/standards/coding-standard.md`

이 문서는 `app/`가 **이미** 따르고 있는 패턴(`app/repositories/book.py`의 `BookRepository`, `app/api/health.py`)을 근거로 작성한다 — 새 규칙이 아니라 기존 관행의 성문화.

- [x] **Step 1: 작성**

```markdown
# 코딩 표준

지금 `app/`가 실제로 따르고 있는 관행을 성문화한 것 — 새 규칙이 아니라 기존 패턴의 문서화다.

## 계층과 의존 방향

```
api/  → services/ → domains/ → repositories/ → models/
              ↘ schemas/ (경계 입출력 타입)
```

- `api/`: FastAPI 라우터. 얇게 유지 — 검증·조합은 `services/`에 위임(`app/api/health.py` 참고).
- `services/`: 유스케이스 로직(`chat/`·`ingestion/`·`search/`). 외부 I/O(LLM·OCR)는 `llm_client.py`류로 격리.
- `domains/`: 도메인 규칙(`nl_library/`).
- `repositories/`: DB 접근만 담당. **ORM 모델을 밖으로 내보내지 않고 항상 스키마로 변환해 반환**한다(`repositories/book.py`의 `BookRepository`가 `Book`이 아닌 `BookOut`을 반환하는 패턴).
- `schemas/`: Pydantic v2 모델. `model_dump()`/`model_validate()`로 ORM ↔ 스키마 변환.
- `models/`: SQLAlchemy ORM 모델.

## 타입힌트

- 모든 함수 시그니처에 인자·반환 타입을 명시한다. `list[str]`·`dict[str, BookOut]`·`X | None` 같은 최신 문법을 쓴다(`repositories/book.py` 전체가 이 패턴).
- 비동기 I/O는 `async def` + `AsyncSession`을 일관되게 쓴다.

## 주석·docstring

- 기본은 주석 없음. 왜(why)가 non-obvious할 때만 한 줄 docstring을 단다(`get_by_cnts_ids`의 `"""cnts_id 목록 조회 → {cnts_id: BookOut}"""`처럼 반환 형태가 함수명만으로 안 드러날 때).
- 무엇을 하는지 설명하는 주석, 현재 작업/이슈 번호를 참조하는 주석은 쓰지 않는다.

## 에러 처리

- 시스템 경계(API 입력, 외부 서비스 응답)에서만 검증한다. 내부 계층 간 호출은 서로를 신뢰한다.
- 발생할 수 없는 상황에 대한 방어 코드를 넣지 않는다.

## 테스트

- `app/tests/`에 pytest. 새 기능은 실패하는 테스트 → 최소 구현 → 통과 순서(TDD)로 진행한다.
- 리포지토리·서비스 계층은 실제 비동기 세션으로 테스트하고, 외부 LLM/OCR 호출만 목(mock)한다 — 목 범위를 넓히지 않는다.

## 네이밍

- 파일·함수: `snake_case`. 클래스: `PascalCase`(`BookRepository`).
- 1회성 실험 스크립트와 운영 스크립트를 구분해 위치시킨다(`CLAUDE.md` §1 — `scripts/` vs `research/`).
```

- [x] **Step 2: 검증**

Run: `grep -q "BookRepository" docs/standards/coding-standard.md && echo GROUNDED`
Expected: `GROUNDED` (실제 코드 근거를 인용했는지 확인)

- [x] **Step 3: 커밋**

```bash
git add docs/standards/coding-standard.md
git commit -m "[Docs] round01 — 코딩 표준 문서화(app/ 기존 관행 성문화)"
```

---

### Task 6: docs/ops/recurring-gotchas.md + docs/design/README.md — ✅ 완료 (`77b190a` → 표→산문 전환+시딩 `6b83f15` → 트리거·중복제거 `69a060a`)

> **리뷰 발견(Important)**: 표 스키마(6열 마크다운 테이블)가 museum 원본(39개 항목, 산문 섹션 `## N. 제목` 형식, 26줄이 하위 불릿·코드블록 포함, 11줄이 `|` 문자 포함)과 비교하면 실제 항목을 못 담는다 — 지금(비어있을 때) 고치는 게 공짜, 첫 항목이 생긴 뒤엔 마이그레이션 비용 발생. 산문 섹션 형식으로 전환하고, round01 자체에서 발견한 실제 함정 2건(dev 이미지 pull-only·external volume 의존)을 시드 데이터로 넣는다. 쓰기·읽기 트리거도 없었음(CLAUDE.md에 사전 확인 게이트 없음, 완료노트에 구체 지시 없음) — 함께 보강.

**Files:**
- Create: `docs/ops/recurring-gotchas.md`
- Create: `docs/design/README.md`

- [x] **Step 1: `docs/ops/recurring-gotchas.md` 작성 (빈 템플릿)**

```markdown
# 반복 함정 (Recurring Gotchas)

라이브(docker·실데이터)에서만 드러나는 패턴을 기록한다. 겪을 때마다 아래 표에 행을 추가한다 — 라운드 문서가 아니라 상시 갱신 문서다.

| # | 날짜 | 증상 | 원인 | 해결 | 재발 방지 |
|---|---|---|---|---|---|

(아직 항목 없음 — round01 시점 기준 빈 템플릿으로 시작)
```

- [x] **Step 2: `docs/design/README.md` 작성 (스텁)**

```markdown
# 디자인 트랙 (미도입)

현재 이 프로젝트에는 Figma 연동·퍼블리싱 디자인 트랙이 없다. 프론트엔드(`frontend/`)는 자체 구현 기준으로 개발한다.

## 도입 시 원칙 (미리 정해둠)
- Figma 디자인이 실제로 연동되면, 이 폴더가 퍼블리싱 납품물의 정본이 된다.
- **버전 폴더는 덮어쓰지 않는다** — `docs/design/<버전>/`에 원본을 보존하고 개정본은 새 폴더로 쌓는다(예: `publish-v1`, `publish-v2`).
- 디자인 개정 반영은 별도 세부 라운드로 분리하고, 착수 시점 버전으로 완주한다.
- 라운드 완료노트의 「디자인 참조」 4항목(버전·참조 화면·참조 자산·미참조 사유)을 이때부터 실제로 채운다.

## 현재 상태
- 스텁 — 실제 자산 없음. 도입 전까지 모든 라운드의 「디자인 참조」는 "해당 없음 — 디자인 트랙 미도입"으로 기입한다.
```

- [x] **Step 3: 검증**

Run: `test -f docs/ops/recurring-gotchas.md && test -f docs/design/README.md && echo BOTH_EXIST`
Expected: `BOTH_EXIST`

- [x] **Step 4: 커밋**

```bash
git add docs/ops/recurring-gotchas.md docs/design/README.md
git commit -m "[Docs] round01 — 반복 함정 템플릿·디자인 트랙 스텁 추가"
```

---

### Task 7: .claude/skills/round-finish/SKILL.md — ✅ 완료 (`ac4b163` → 가드·description 보강 `9baffa8`)

> **리뷰 발견(Important)**: (1) dev 미반영 상태에서 실행하면 `merge --no-ff`가 조용히 no-op하고 성공으로 오보될 수 있었음 — 머지전 `main..dev`/`main..origin/main` 가드 추가. (2) `main`/`dev` 체크아웃은 **격리 워크트리가 아니라 공유 체크아웃에서** 해야 함(워크트리에 dev/main이 이미 물려있으면 체크아웃 자체가 거부되고, 워크트리 안에서 main으로 전환하면 그 라운드 신규 파일이 일시적으로 사라짐) — **Task 15 실행 시 이 규칙을 따른다**: Step 6·8(dev·main 머지)은 이 워크트리가 아니라 공유 체크아웃(`C:\Users\LANDSOFT\mygit\NL_library_AI`)에서 수행한다.

**Files:**
- Create: `.claude/skills/round-finish/SKILL.md`

- [x] **Step 1: 디렉토리 없음 확인**

Run: `test -d .claude/skills && echo EXISTS || echo MISSING`
Expected: `MISSING`

- [x] **Step 2: 작성**

```markdown
---
name: round-finish
description: 한 라운드를 종료할 때 사용 — 검증 확인 후 dev→main 머지 + origin push. "라운드 끝내자/마무리/main 올리고 push" 같은 요청에 활성화.
---

# round-finish — 라운드 종료 절차

한 라운드(사용자 프롬프트 1개의 구현)가 검증·리뷰까지 끝나 `main`에 올리고 원격에 동기화하는 절차다. 상세 흐름은 `GIT_WORKFLOW.md` §라운드.

## 전제 (확인 후 진행)
- 작업 브랜치가 이미 `dev`에 머지돼 있다(사용자 승인 하).
- 검증 green: 관련 테스트(`pytest`) + 핵심 기능 수동 스모크 확인.
- 사용자가 라운드 종료를 승인했다(이 단계는 `main`을 움직이므로 임의 진행 금지).

## 절차
1. 검증 재확인 — 테스트 green, 핵심 동작 스모크 확인.
2. 완료노트(`docs/roadmap/round<NN>-완료노트.md`)의 `## 상태` 체크리스트(code-reviewer 정적 리뷰·테스트·스모크·문서 갱신·머지 승인 전부)와 「디자인 참조」 필드(디자인 트랙 미도입이면 "해당 없음") 확인.
3. `docs/roadmap/00_status.md` 갱신 확인(최종 갱신 날짜·현재 상태·다음 할 일·라운드 이력 — 라운드 이력만 바꾸고 현재 상태를 그대로 두지 않는다).
4. `dev → main` 머지
   ```bash
   git checkout main
   git merge --no-ff dev -m "Merge dev into main — round<N> (<요약>)"
   ```
5. origin push
   ```bash
   git push origin main && git push origin dev
   ```
6. 작업 복귀: `git checkout dev`.

## 주의
- 평소 작업은 `dev`에서 분기 → 작업 브랜치. `main` 직접 작업은 이 종료 절차에서만.
- 비밀정보·데이터·미공개 자료는 커밋·push 금지(`.gitignore`).
```

- [x] **Step 3: frontmatter 검증**

Run: `python -c "import yaml; d=yaml.safe_load(open('.claude/skills/round-finish/SKILL.md', encoding='utf-8').read().split('---')[1]); assert d['name']=='round-finish'; print('OK')"`
Expected: `OK`

- [x] **Step 4: 커밋**

```bash
git add .claude/skills/round-finish/SKILL.md
git commit -m "[Chore] round01 — round-finish 스킬 추가"
```

---

### Task 8: .claude/agents/code-reviewer.md — ✅ 완료 (`ecd18ae` → 리뷰 보강 `3ccea0e`)

> **리뷰 발견**: (1) 항목2에 테스트충분성 축 누락 — 추가. (2) 항목5 "의식"이 실행 불가능한 지시 — "먼저 읽고 대조" 로 수정. (3) **리뷰 중 실제 보안 취약점 발견**: `app/api/admin.py:199,378,380`의 Milvus expression injection(인증 없음, `cnts_id` 미검증 f-string 삽입으로 임의 삭제 가능) — 사용자에게 즉시 보고, 도서관 대회 시연(2026-09-07 기준 약 1개월 후) 우선으로 이월 승인받음 + "DB 파괴 행위 절대 금지" 지시 받아 메모리에 저장([[nl-lib-never-wipe-db]], [[nl-lib-library-competition-deadline]]). code-reviewer 항목3에 이 이슈의 이월 상태와 "데모 전까지 수정 코드 생성 금지"를 명시해 향후 라운드가 재보고하거나 섣불리 손대지 않도록 함. **round01 자체는 이 취약점을 고치지 않는다** — Task 14 완료노트 이월 항목에 반영.
> **환경 유의**: 이 세션은 museum 프로젝트 루트에서 시작돼 `/round-finish`·`code-reviewer` 등 스킬/에이전트 로더가 museum 버전을 가리키고 있다(NL-Lib 버전은 이 워크트리에만 존재, 아직 dev/main에 없음). Task 15에서 `/round-finish` 스킬을 직접 호출하지 말고 `.claude/skills/round-finish/SKILL.md`의 절차를 수동으로 따른다.

**Files:**
- Create: `.claude/agents/code-reviewer.md`

- [x] **Step 1: 작성**

`model: opus` 명시 — 개발(메인 세션)은 Sonnet이어도 리뷰는 항상 Opus로 고정(2026-09-04 합의).

```markdown
---
name: code-reviewer
description: 라운드 코드·문서를 영역별로 정적 리뷰한다. 정확성·코딩표준·문서 일관성을 severity로 보고. 읽기 전용(파일·git·docker 미수정). 라운드 리뷰 단계에서 영역마다 병렬로 띄워 쓴다.
tools: Read, Grep, Glob
model: opus
---

너는 이 프로젝트(NL-Lib — 국립중앙도서관 의미 기반 검색 시스템)의 정적 리뷰어다. 지정된 영역(코드 디렉터리 또는 문서 집합)을 읽고 결함을 찾아 보고한다. 파일을 수정하지 않는다. git·docker·테스트를 실행하지 않는다.

## 프로젝트 맥락 (판단 기준)
- 검색: BGE-M3 Dense+Sparse 하이브리드(Milvus `hybrid_search`+RRFRanker) + 메타데이터 이중 전략(전용 청크 `chunk_idx=-1` + 스칼라 필터) + Contextual Chunking.
- 인덱싱: OCR 라우팅(VLM/Surya/Tesseract/fitz, 표 셀 충전율·폰트 CMap 손상 등 신호 기반 폴백).
- 계층 의존 방향·경계 타입 규칙은 `docs/standards/coding-standard.md`가 정본이다(여기 별도 서술하지 않음 — 그 문서에 "지향점"과 "실측 반례(백로그)"가 파일 단위로 구분돼 있으니, `section.py`·`catalog_bulk.py`처럼 이미 문서화된 반례는 새 발견으로 재보고하지 말고 그 문서의 백로그로 취급한다).
- 개발 환경: prod(`docker-compose.yml`) 전체 스택, dev(`docker-compose.dev.yml`)는 앱+데이터 계층 모두 별도로 뜨고 GPU 서비스(vllm/gemma/flux)만 prod와 공유. dev는 이미지를 registry에서 pull하므로 `scripts/build_dev_images.sh`로 재빌드+push 없이는 코드 변경이 반영되지 않는다.

## 점검 항목
1. **정확성**: 버그·엣지케이스·미구현(placeholder)·죽은 코드.
2. **코딩표준**: `docs/standards/coding-standard.md` 기준으로 타입힌트·계층 의존 방향·ORM 유출·비동기 일관성을 본다 — 단, 그 문서가 이미 "지향점/백로그"로 명시한 기존 반례(예: `section.py`·`catalog_bulk.py`)는 새 결함으로 보고하지 않는다. **신규/수정 코드**가 그 반례를 새로 늘리는 경우에만 지적한다.
3. **보안**: 비밀 하드코딩·SQL 인젝션(파라미터 바인딩) · Milvus expression 필터에 사용자 입력이 직접 문자열 결합되지 않는지.
4. **일관성**(문서 리뷰 시): 문서↔코드, 문서 간(어휘·스택·결정) 정합 + stale 서술.
5. **반복 함정**(`docs/ops/recurring-gotchas.md`): 라이브에서만 드러나는 패턴을 의식.

## 보고 형식
- 각 결함: severity(high=동작불가/보안 · medium=표준위반/불일치/누락 · low=개선) · location(파일:라인) · issue(파일 근거로 구체적) · suggestion.
- 추측 금지 — 읽은 근거만. 발견 없으면 "없음"을 명확히.
- 동작을 막는 high는 맨 앞에. 요약 1~2문장 + 결함 목록.
```

- [x] **Step 2: frontmatter 검증**

Run: `python -c "import yaml; d=yaml.safe_load(open('.claude/agents/code-reviewer.md', encoding='utf-8').read().split('---')[1]); assert d['model']=='opus'; print('OK')"`
Expected: `OK`

- [x] **Step 3: 커밋**

```bash
git add .claude/agents/code-reviewer.md
git commit -m "[Chore] round01 — code-reviewer 서브에이전트 추가(model: opus 고정)"
```

---

### Task 9: .gitignore 디버그 로그 패턴 + 로그 파일 삭제 — ✅ 완료 (`f8c9fb7` → 패턴 보강 `89ad0d1`)

> **실행 시 스펙과 다르게 확인된 사실**: `scripts/debug_raw.txt`는 실제로는 **추적 상태**였다(이 라운드 초반의 구제 커밋 `3743453`이 scripts/의 미추적 파일을 통째로 되살릴 때 개별 제외 없이 함께 커밋됨) — `rm` 대신 `git rm`으로 처리(구현자가 올바르게 적응). **리뷰 발견**: 새 패턴 2개(`*_debug_out*.txt`·`soffice_log*.txt`) 중 어느 것도 `debug_raw.txt`류(`debug_*.txt`)를 안 잡아서, 정작 재발 이력이 있는 파일이 재발 방지 대상에서 빠져있었음 — `debug_*.txt` 패턴 추가로 보강. 공유 체크아웃에는 이 3개 미추적 파일(`scripts_debug_out.txt`·`scripts_debug_out2.txt`·`soffice_log2.txt`)이 워크트리 격리 때문에 그대로 남아있음(무해한 로컬 잔재, Task 15에서 공유 체크아웃 작업 시 함께 정리).

**Files:**
- Modify: `.gitignore`
- Delete (untracked, 디스크에서만 제거): `scripts_debug_out.txt`, `scripts_debug_out2.txt`, `soffice_log2.txt`, `scripts/debug_raw.txt`

이 4개는 전부 **미추적 상태**(git이 모르는 파일)이므로 `git rm` 대상이 아니라 단순 파일 삭제 + 향후 재발 방지용 gitignore 패턴 추가다.

- [x] **Step 1: 대상이 정말 미추적인지 확인**

Run: `git ls-files scripts_debug_out.txt scripts_debug_out2.txt soffice_log2.txt scripts/debug_raw.txt`
Expected: (빈 출력 — 4개 다 미추적)

- [x] **Step 2: `.gitignore`에 패턴 추가**

`.gitignore`의 `# Logs` 섹션(`*.log` 다음 줄)에 아래 두 줄 추가:

```
*_debug_out*.txt
soffice_log*.txt
```

- [x] **Step 3: 로그 파일 삭제**

```bash
rm scripts_debug_out.txt scripts_debug_out2.txt soffice_log2.txt scripts/debug_raw.txt
```

- [x] **Step 4: 검증**

Run: `git status --short | grep -E "scripts_debug_out|soffice_log|debug_raw"`
Expected: (빈 출력 — 삭제된 미추적 파일은 status에 안 잡힘)

Run: `git check-ignore scripts_debug_out.txt`
Expected: `scripts_debug_out.txt` (지금은 없는 파일이지만 패턴 매칭 자체는 확인 가능 — `git check-ignore`는 파일 존재 여부와 무관하게 패턴만 검사)

- [x] **Step 5: 커밋**

```bash
git add .gitignore
git commit -m "[Chore] round01 — 디버그 로그 gitignore 패턴 추가 + 기존 로그 삭제"
```

---

### Task 10: research/ 생성 + ocr-extraction-comparison·vlm-routing-policy 이동 — ✅ 완료

> **실행 중 발견**: `quality_extra.json`·`vlm_sample.json`은 실제로는 이 워크트리에 **한 번도 추적된 적 없었음**(공유 체크아웃에만 미추적 파일로 존재 — 워크트리 생성 시 미추적 파일은 안 딸려옴). 구현자가 `git mv` 대신 BLOCKED로 정확히 보고했고, 컨트롤러가 공유 체크아웃에서 내용을 읽어와 동일 내용으로 재생성 후 커밋(구 파일 대비 CRLF→LF·말미 개행 차이만 있고 내용은 100% 동일 — `diff --strip-trailing-cr`로 확인). `research/` 나머지 5개 디렉토리는 의도대로 빈 채로 생성됨(Task 11 대상).
> **리뷰 발견 + 정정**: `space_stats_full.py`(내용상 `cell_stats_full.py`의 v2 — docstring·OUT 경로 모두 table-cell-fill 주제)가 ocr-extraction-comparison에, `quality_extra.json`(요약·청킹 품질 데이터, VLM 라우팅과 무관)이 vlm-routing-policy에 잘못 배정돼 있었음 — Task 11이 그 두 폴더를 채우기 전에 미리 재배치(`c61f427`). **Task 11의 table-cell-fill·kci-paper-samples 개수 검증값은 이 선(先)배치분을 포함하도록 조정됨(각 +1).**
> **이월(고치지 않음)**: 이동된 스크립트 20개 중 15개가 산출물 경로를 여전히 `scripts/...` 절대/상대 경로로 하드코딩하고 있어, 재실행하면 새 산출물이 `research/`가 아니라 예전 `scripts/` 위치에 다시 생긴다. 코드 내용 수정은 round01(파일 재배치) 스코프 밖으로 보고 이월 — 완료노트에 기록.

**Files:**
- Create: `research/` 7개 하위 디렉토리
- Move: `scripts/*` → `research/ocr-extraction-comparison/`, `research/vlm-routing-policy/` (42 + 19파일 + `vlm_raw100/` 디렉토리 + root 2파일)

- [x] **Step 1: 대상 디렉토리 전체 생성**

```bash
mkdir -p research/ocr-extraction-comparison research/vlm-routing-policy research/table-cell-fill research/font-and-layout-forensics research/corpus-and-failure-analysis research/kci-paper-samples research/gongu-wikisource-manifest-check
```

- [x] **Step 2: ocr-extraction-comparison 이동 (42개)**

```bash
for f in compare_extraction_methods.py compare_summary.json compare_vlm.py dump_odl_text.py \
  easyocr_born_result.json exp1_recomputed.txt fitz_lengths_lit.py fitz_lengths_lit100.json \
  fitz_lengths_policy.py fitz_lengths_policy200.json fitz_lengths_result.json fitz_lengths_result100.json \
  fitz_nospace_policy.json fitz_nospace_policy.py fitz_pages.txt four_way_comparison.json \
  four_way_comparison100.json hf_test_bodypage.txt hf_test_bodypage2.txt hf_test_p0.txt hyeol_subpage.txt \
  odl_lengths_result.json odl_lengths_result100.json odl_lengths_result70.json odl_p7_KCI_FI002529577.txt \
  odl_table_sample.json odl_text_dump.json odl_vs_fitz_lengths.txt rep_check.txt run_easyocr_born.py \
  run_surya_paddle_born.py space_stats_full.py surya_paddle_born_result.json tesseract_born_psm11.json \
  tesseract_born_psm11.py tesseract_extract.py tesseract_lengths_result.json tesseract_lengths_result100.json \
  tesseract_p7_KCI_FI002529577.txt tesseract_psm_sweep.json tesseract_psm_sweep.py three_way_comparison.json; do
  git mv "scripts/$f" research/ocr-extraction-comparison/
done
```

- [x] **Step 3: vlm-routing-policy 이동 (19개 + 디렉토리 1개 + root 2개)**

```bash
for f in analyze_vlm_policy.py audit_result.txt audit_routing_fix.py audit_routing_fix_result.json \
  audit_routing_fix_result100.json audit_routing_fix_result_orig5.json audit_routing_lit.py \
  audit_routing_lit100.json audit_routing_policy.py audit_routing_policy200.json missing_vlm_files.txt \
  policy_sample200.txt reextract_vlm_raw_flagged.py run_vlm_batch.py run_vlm_batch2.py run_vlm_policy.py \
  vlm_lengths_result.json vlm_lengths_result100.json vlm_policy_merged.json; do
  git mv "scripts/$f" research/vlm-routing-policy/
done
git mv scripts/vlm_raw100 research/vlm-routing-policy/vlm_raw100
git mv quality_extra.json research/vlm-routing-policy/
git mv vlm_sample.json research/vlm-routing-policy/
```

- [x] **Step 4: 개수 검증**

Run: `ls research/ocr-extraction-comparison | wc -l`
Expected: `42`

Run: `ls research/vlm-routing-policy | wc -l`
Expected: `22` (파일 19 + `vlm_raw100` 디렉토리 1 + root 파일 2)

Run: `ls research/vlm-routing-policy/vlm_raw100 | wc -l`
Expected: `1284`

- [x] **Step 5: 이동한 .py 문법 검증**

```bash
find research/ocr-extraction-comparison research/vlm-routing-policy -name "*.py" -exec python -m py_compile {} \;
echo "exit=$?"
```
Expected: `exit=0` (문법 오류 없음 — import 자체는 실행하지 않으므로 서드파티 라이브러리 미설치 환경에서도 통과해야 함)

- [x] **Step 6: 커밋**

```bash
git add research/ocr-extraction-comparison research/vlm-routing-policy
git commit -m "[Chore] round01 — 실험 산출물 research/ocr-extraction-comparison, vlm-routing-policy로 이동"
```

---

### Task 11: research/ 나머지 5개 주제 이동 + 루트 파일 분배 — ✅ 완료

> **Task 10과 동일한 패턴 재발**: 루트 파일 3개(`kci_FI000865437_sections.json`·`paper_chunk_sample.json`·`summary_sample.json`)가 이 워크트리에 한 번도 추적된 적 없어 `git mv` 불가 — 구현자가 BLOCKED로 정확히 보고, 컨트롤러가 공유 체크아웃에서 내용을 읽어와 재생성. **이번엔 `diff --strip-trailing-cr`로 대조하다 실제 오타를 하나 잡았다** — `paper_chunk_sample.json`의 부동소수점 `score` 값을 옮겨적으며 `...306529`로 오기(원본은 `...306549`) — 재대조 후 정정, 최종 확인 완료.

**Files:**
- Move: `scripts/*` → `research/table-cell-fill/`, `research/font-and-layout-forensics/`, `research/corpus-and-failure-analysis/`, `research/kci-paper-samples/`, `research/gongu-wikisource-manifest-check/`

- [x] **Step 1: table-cell-fill 이동 (9개)**

```bash
for f in cell_fill.json cell_fill_analysis.py cell_stats_full.py cell_stats_policy.json \
  cell_stats_policy2.json json_cell_stats.json json_cell_stats.py json_cell_stats2.json json_cell_stats2.py; do
  git mv "scripts/$f" research/table-cell-fill/
done
```

- [x] **Step 2: font-and-layout-forensics 이동 (9개)**

```bash
for f in font_forensics.json font_forensics.py font_targets.json glyph_gap.json glyph_recovery_gap.py \
  page_geometry_features.py page_geometry_policy.json xobject_check.json xobject_hypothesis.py; do
  git mv "scripts/$f" research/font-and-layout-forensics/
done
```

- [x] **Step 3: corpus-and-failure-analysis 이동 (16개 + root 1개)**

```bash
for f in analyze_corpus_types.py cluster_failures.py corpus_type_comparison.json fail_check2.json \
  failure_features.json failure_taxonomy.json failure_taxonomy.py item14016_status.json \
  output1_doctype.json output1_doctype.txt output_doctype.json output_doctype.py sample_book_ids.txt \
  stratified_page_selection.json suspect_books.txt tess_inspect_targets.json; do
  git mv "scripts/$f" research/corpus-and-failure-analysis/
done
git mv failures_out.json research/corpus-and-failure-analysis/
```

- [x] **Step 4: kci-paper-samples 이동 (11개 + root 3개)**

```bash
for f in kci_FI000921643_full.txt kci_sample.txt kci_sample100.txt kci_sample70.txt \
  kci_sample_comparison.json kci_sample_section2.txt kci_sample_section3.txt kci_stall_check.json \
  lit_sample100.txt paper_draft.txt test_plain_sample.txt; do
  git mv "scripts/$f" research/kci-paper-samples/
done
git mv kci_FI000865437_sections.json research/kci-paper-samples/
git mv paper_chunk_sample.json research/kci-paper-samples/
git mv summary_sample.json research/kci-paper-samples/
```

- [x] **Step 5: gongu-wikisource-manifest-check 이동 (6개)**

```bash
for f in verify_ws001.txt ws9_fail.json ws_doctype_check.json ws_fail.json ws_search_test.json ws_status.json; do
  git mv "scripts/$f" research/gongu-wikisource-manifest-check/
done
```

- [x] **Step 6: 개수 검증**

Run:
```bash
echo "table-cell-fill: $(ls research/table-cell-fill | wc -l) (expect 10 — Task 10 리뷰로 재분류된 space_stats_full.py 1개가 이미 들어있음)"
echo "font-and-layout-forensics: $(ls research/font-and-layout-forensics | wc -l) (expect 9)"
echo "corpus-and-failure-analysis: $(ls research/corpus-and-failure-analysis | wc -l) (expect 17)"
echo "kci-paper-samples: $(ls research/kci-paper-samples | wc -l) (expect 15 — Task 10 리뷰로 재분류된 quality_extra.json 1개가 이미 들어있음)"
echo "gongu-wikisource-manifest-check: $(ls research/gongu-wikisource-manifest-check | wc -l) (expect 6)"
```
Expected: 괄호 안 숫자와 일치

- [x] **Step 7: 이동한 .py 문법 검증**

```bash
find research/table-cell-fill research/font-and-layout-forensics research/corpus-and-failure-analysis -name "*.py" -exec python -m py_compile {} \;
echo "exit=$?"
```
Expected: `exit=0`

- [x] **Step 8: scripts/ 잔존 파일 확인 (운영 도구만 남아야 함)**

Run: `git ls-files scripts/ | grep -v '^scripts/bulk_ingest/'`
Expected:
```
scripts/build_dev_images.sh
scripts/build_gongu_manifest.py
scripts/build_vlm_policy_selection.py
scripts/build_wikisource_manifest.py
scripts/crawler.py
```
(`build_vlm_policy_selection.py`는 Task 12에서 최종 확정)

- [x] **Step 9: 커밋**

```bash
git add research/table-cell-fill research/font-and-layout-forensics research/corpus-and-failure-analysis research/kci-paper-samples research/gongu-wikisource-manifest-check
git commit -m "[Chore] round01 — 실험 산출물 나머지 5개 주제 research/로 이동 + 루트 파일 분배"
```

---

### Task 12: 애매 파일 확인 및 최종 배치

**Files:**
- Move (확인 후): `scripts/build_vlm_policy_selection.py`, root의 `claim17_xml.txt`·`claim2_xml.txt`·`editor_note_heading.txt`·`editor_note_xml.txt`·`effect_close_xml.txt`·`effect_last_para.txt`

spec에서 "확인 필요"로 남겨둔 7개 파일을 사용자에게 실제 용도를 물어 확정한다.

- [ ] **Step 1: 각 파일의 내용을 먼저 훑는다**

```bash
head -c 500 scripts/build_vlm_policy_selection.py
head -c 300 claim17_xml.txt claim2_xml.txt editor_note_heading.txt editor_note_xml.txt effect_close_xml.txt effect_last_para.txt
```

- [ ] **Step 2: 사용자에게 질의 (AskUserQuestion)**

두 질문을 던진다:
1. `build_vlm_policy_selection.py`가 지금도 파이프라인이 참조하는 정책 산출물을 만드는 운영 스크립트인지, 1회성 연구였는지.
2. `claim*`·`editor_note*`·`effect*` 6개 파일이 어떤 실험(특허 청구항 처리? 다른 도메인 테스트?)이었는지, 그리고 이 프로젝트에 남겨둘 가치가 있는지 — 있다면 새 주제 폴더명을, 없다면 삭제 여부를.

- [ ] **Step 3: 답변에 따라 배치**

- `build_vlm_policy_selection.py`가 운영 도구라는 답이면: `scripts/`에 잔류(아무 작업 불필요).
- 1회성 연구라는 답이면: `git mv scripts/build_vlm_policy_selection.py research/vlm-routing-policy/`
- claim/editor_note/effect 6개는 답변받은 폴더명으로 `mkdir -p research/<확정된 폴더명>` 후 `git mv <파일> research/<확정된 폴더명>/`, 혹은 불필요하다는 답이면 `rm <파일>`(미추적 파일이므로 `git rm` 아님).

- [ ] **Step 4: 검증**

Run: `git status --short | grep -E "^\?\?"`
Expected: `?? app/scripts/recheck_table_fill.py` 한 줄만(round01 스코프 밖 WIP, 정상).

Run: `ls *.txt *.json 2>/dev/null | grep -v package-lock`
Expected: 빈 출력 — 루트에 더 이상 미추적 실험 파일이 없어야 한다(`package-lock.json` 제외).

Run: `git ls-files scripts/ | grep -v '^scripts/bulk_ingest/'`
Expected:
```
scripts/build_dev_images.sh
scripts/build_gongu_manifest.py
scripts/build_wikisource_manifest.py
scripts/crawler.py
```
(`build_vlm_policy_selection.py`는 Step 3 결과에 따라 있을 수도 없을 수도 있음)

- [ ] **Step 5: 커밋**

`app/scripts/recheck_table_fill.py`는 round01 스코프 밖의 별개 WIP이므로 반드시 제외하고 스테이징한다(`git add -A` 금지 — 그 파일까지 실수로 딸려 들어감).

```bash
git add -A -- . ':(exclude)app/scripts/recheck_table_fill.py'
git commit -m "[Chore] round01 — 애매 파일(build_vlm_policy_selection·claim/editor_note/effect) 최종 배치"
```

---

### Task 13: docs/guides/round01/00-체계도입.md 작성

**Files:**
- Create: `docs/guides/round01/00-체계도입.md`

museum 관행대로 **전체 코드 재수록** — 발췌·"Task N과 동일" 금지. Task 1~12에서 만든 파일들을 실제로 읽어 그대로 옮겨 담는다(내용은 이미 이 plan에 전문이 있으므로, 실행자는 각 파일을 `Read`해서 그 내용을 아래 골격에 채운다). Task 1·2·3·4는 리뷰로 수정된 **최종본**(커밋된 실제 파일 — Task 1은 `11815ae`, Task 2는 `132982f`, Task 3은 `b972752`, Task 4는 `db142ae` 시점)을 사용한다.

**중첩 코드펜스 주의**: `GIT_WORKFLOW.md`(bash 블록 2개)·`docs/guides/_TEMPLATE.md`(자기 자신이 예시 펜스를 담음)처럼 담을 파일 자체에 ` ``` ` 펜스가 있으면, 그 섹션을 감싸는 바깥 펜스는 4개 백틱(` ```` `)이나 `~~~~`를 써서 조기 종료를 막는다(`docs/guides/_TEMPLATE.md`가 `db142ae`에서 정한 관행).

- [ ] **Step 1: 디렉토리 생성 확인**

Run: `mkdir -p docs/guides/round01 && test -d docs/guides/round01 && echo EXISTS`
Expected: `EXISTS`

- [ ] **Step 2: 골격 작성 후 각 섹션에 실제 파일 내용을 채운다**

```markdown
# round01 교본 — 개발 체계 도입(museum 스타일 이식)

## 0. 사용자 프롬프트 (paraphrase)
> museum 프로젝트(`Habonit/20260601-museum-platform`)처럼 CLAUDE.md 진입점·round 기반 워크플로우·문서 지도·산출물 위치 규칙을 갖춘 체계적인 개발 방식을 NL-Lib에도 도입하고 싶다. 단, NL-Lib은 이미 배포 중인 코드(`app/`·`frontend/`·`infra/`)를 물리적으로 재배치하지 않고, 협업자 없는 솔로 개발 환경에 맞게, GitHub 단일 리모트 기준으로 이식한다. 루트·`scripts/`에 쌓인 실험 산출물도 이번 기회에 주제별로 정리한다.

## 1. 설계 요약
(spec: `docs/superpowers/specs/2026-09-04-round01-dev-system-bootstrap-design.md`)

museum과의 핵심 차이:
- 디렉토리 물리 이동 없음(이름 유지, 문서로만 정본화)
- 리뷰 게이트는 자가 점검 체크리스트(협업자 없음)
- GitLab 없음 — origin(GitHub) 단일 push
- 역할 문서는 6분할 대신 단일 `docs/roadmap/00_status.md`
- ADR 이번 라운드 생략(README에 이미 설계 근거 있음)
- 디자인 트랙은 미도입이지만 Figma 연동 훅(`docs/design/README.md`)만 남김
- 산출물 위치 규칙: `research/<주제>/`로 118개(scripts) + 6개(root) 파일 이동

## 2. 구현 (클론코딩)

### 2.1 CLAUDE.md
**파일**: `CLAUDE.md`

```markdown
<위 Task 1(리뷰 수정 최종본, 11815ae 시점) CLAUDE.md 전체 내용을 그대로 붙여넣는다>
```

### 2.2 GIT_WORKFLOW.md
**파일**: `GIT_WORKFLOW.md`

```markdown
<Task 2에서 작성한 GIT_WORKFLOW.md 전체 내용을 그대로 붙여넣는다>
```

### 2.3 docs/roadmap/00_status.md, _ROUND_COMPLETE_TEMPLATE.md
**파일**: `docs/roadmap/00_status.md`, `docs/roadmap/_ROUND_COMPLETE_TEMPLATE.md`

```markdown
<Task 3에서 작성한 두 파일 전체 내용을 그대로 붙여넣는다>
```

### 2.4 docs/guides/_TEMPLATE.md
**파일**: `docs/guides/_TEMPLATE.md`

```markdown
<Task 4에서 작성한 내용을 그대로 붙여넣는다>
```

### 2.5 docs/standards/coding-standard.md
**파일**: `docs/standards/coding-standard.md`

```markdown
<Task 5에서 작성한 내용을 그대로 붙여넣는다>
```

### 2.6 docs/ops/recurring-gotchas.md, docs/design/README.md
**파일**: `docs/ops/recurring-gotchas.md`, `docs/design/README.md`

```markdown
<Task 6에서 작성한 두 파일 전체 내용을 그대로 붙여넣는다>
```

### 2.7 .claude/skills/round-finish/SKILL.md
**파일**: `.claude/skills/round-finish/SKILL.md`

```markdown
<Task 7에서 작성한 내용을 그대로 붙여넣는다>
```

### 2.8 .claude/agents/code-reviewer.md
**파일**: `.claude/agents/code-reviewer.md`

```markdown
<Task 8에서 작성한 내용을 그대로 붙여넣는다(model: opus 포함)>
```

### 2.9 research/ 마이그레이션
Task 10~12의 `git mv` 목록 전체와 최종 `research/` 트리 구조(`find research -maxdepth 1 -type d` 결과)를 표로 정리해 싣는다.

## 2.5 디자인 참조 요약
해당 없음 — 디자인 트랙 미도입(`docs/design/README.md` §현재 상태).

## 3. 검증
- Task 1~12의 각 Step 3/4/5(grep·py_compile·개수 확인) 명령과 실제 실행 결과를 그대로 옮겨 적는다.
- 추가로 `docker compose -f docker-compose.yml config --quiet && docker compose -f docker-compose.dev.yml config --quiet && echo OK` 실행 결과(물리 경로를 안 건드렸으므로 두 compose 파일이 여전히 정상 파싱되는지 확인).

## 4. 면접식 Q&A

**Q1. `docs/`가 왜 저장소 생성 이후 한 번도 git에 커밋되지 않았나?**
A. `.gitignore`에 `/docs`가 있었기 때문이다. round01 착수 전 이를 발견해 별도로(라운드 범위 밖) 제거하고 그동안 쌓인 문서를 백업 커밋했다.

**Q2. museum은 `workspace/app`처럼 물리적으로 코드를 옮겼는데 왜 NL-Lib은 안 옮기나?**
A. `app/`·`frontend/`·`infra/`가 이미 `docker-compose.yml`·`Dockerfile`·`alembic.ini`의 실제 배포 경로로 물려 있어, 물리 이동은 그 모든 참조를 갱신해야 하는 별도의 큰 위험 작업이 된다. 이름은 유지하고 "이 구조가 정본"이라고 문서로만 규정하는 쪽을 택했다.

**Q3. `scripts/`와 `research/`를 가르는 기준은?**
A. "이 스크립트를 다시 실행할 일이 있는가." 파이프라인이 지금도 호출하거나 반복 실행하는 운영 도구는 `scripts/`에 남고, 특정 질문 하나에 답하고 끝난 1회성 분석은 스크립트와 산출물을 함께 `research/<주제>/`로 옮긴다.

**Q4. code-reviewer 에이전트에 `model: opus`를 고정한 이유는?**
A. 개발(메인 세션)은 비용 효율을 위해 Sonnet을 쓰더라도, 라운드 종료 직전의 정적 리뷰만은 항상 더 강력한 모델로 고정해 검증 품질을 담보하기 위해서다. 에이전트 정의 frontmatter의 `model` 필드로 서브에이전트별 모델을 오버라이드할 수 있다.

**Q5. 라운드 종료 시 왜 GitLab push가 없나?**
A. museum은 GitHub·GitLab 이원화 운영이지만, NL-Lib은 `git remote -v` 확인 결과 GitHub(origin) 단일 리모트다. `round-finish` 스킬에서 GitLab 관련 단계를 전부 제거했다.

**Q6. Task 1은 왜 커밋이 2개인가?**
A. 최초 구현(`f5983bb`) 후 code-quality 리뷰에서 review-순서 모순(§2가 "리뷰 전 dev 머지"로 잘못 서술), README 로드맵 위치 누락, `docs/specs/` 누락, 루트 파일 규칙 부재 4건의 Important 이슈가 나와 별도 수정 커밋(`11815ae`)으로 반영했다. 리뷰가 실제로 내용을 검증한다는 증거로 남겨둔다.
```

- [ ] **Step 3: 검증**

Run: `grep -c "^### 2\." docs/guides/round01/00-체계도입.md`
Expected: `8` (2.1~2.4, 2.6~2.9 — 2.5 디자인 참조 요약은 `## 2.5`로 h2 승격돼 있어 `### 2.` 패턴에 안 잡힌다. Task 4 리뷰에서 `### 2.5`가 구현 서브섹션 시퀀스와 헤딩레벨이 충돌하는 Critical 버그로 발견돼 `db142ae`에서 h2로 수정됐다 — 원래 "9"였던 기대값도 그에 맞춰 정정)

Run: `grep -c "^## 2\.5" docs/guides/round01/00-체계도입.md`
Expected: `1`

Run: `grep -c "^\*\*Q" docs/guides/round01/00-체계도입.md`
Expected: `6`

- [ ] **Step 4: 커밋**

```bash
git add docs/guides/round01/00-체계도입.md
git commit -m "[Docs] round01 — 라운드 교본 작성"
```

---

### Task 14: docs/roadmap/round01-완료노트.md 작성 + 00_status.md 갱신

**Files:**
- Create: `docs/roadmap/round01-완료노트.md`
- Modify: `docs/roadmap/00_status.md`

- [ ] **Step 1: `_ROUND_COMPLETE_TEMPLATE.md`를 기반으로 완료노트 작성**

```markdown
# round01 완료노트

날짜: 2026-09-04
브랜치: `feat/round01-dev-system-bootstrap-wt`

## 한 일
- CLAUDE.md·GIT_WORKFLOW.md 등 운영 진입점 문서 신설
- `docs/roadmap/`·`docs/guides/`·`docs/standards/`·`docs/ops/`·`docs/design/` 신설
- `.claude/skills/round-finish/`·`.claude/agents/code-reviewer.md`(model: opus) 신설
- `research/` 7개 주제 폴더 신설, scripts/root의 실험 산출물 118개(scripts 112 + root 6) 이동 + `vlm_raw100/`(1,284개 파일) 디렉토리 이동. 운영 도구 5개(`build_dev_images.sh`·`build_gongu_manifest.py`·`build_wikisource_manifest.py`·`crawler.py`·확인된 `build_vlm_policy_selection.py`)는 `scripts/` 잔류
- 디버그 로그 4개 삭제 + `.gitignore` 재발 방지 패턴 추가
- README §5(프로젝트 구조)를 `docs/`·`scripts/`·`research/` 신설 반영해 갱신 — 실존하지 않는 `migrate_add_KCI.sql` 참조 제거
- (라운드 범위 밖, 착수 전 별도 조치) `.gitignore`의 `/docs`·`/scripts`·`.claude/` 오추적 제외 버그 수정, 밀린 문서 백업, `SKOVIX-JeongHyun`/`feat/search-session-history` 브랜치 정리

## 결정
- 물리 디렉토리 이동 없음 — `app/`·`frontend/`·`infra/`는 이름 유지
- 리뷰 게이트는 자가 점검 체크리스트(협업자 없음)
- ADR 이번 라운드 생략
- code-reviewer는 `model: opus` 고정
- 서브에이전트 실행은 격리 워크트리(`feat/round01-dev-system-bootstrap-wt`)에서 진행(GitHub Desktop 동시 사용 충돌 방지)

## 디자인 참조
해당 없음 — 디자인 트랙 미도입(`docs/design/README.md`)

## 이월
- `docs/adr/ADR-001-*.md` — 다음 큰 결정 시점에
- `app/odl_stderr.log`(8MB, 미추적) 등 `app/` 내부 대용량 로그 정리 — 이번 스코프 밖
- 루트의 `INDEX.README.md`·`inspect_odl.py`·`migrate_add_*.sql` — round01 스코프 밖(CLAUDE.md §1에 이월 명시)
- **[보안, 우선순위 높음] `app/api/admin.py:199,378,380` Milvus expression injection** — 인증 없는 엔드포인트에서 `cnts_id`가 검증 없이 f-string으로 `expr`에 삽입돼 임의 삭제 가능. 2026-09-07 발견·보고, 도서관 대회 시연(약 1개월 후) 우선으로 사용자가 명시적으로 이월 지시 + "DB 파괴 행위 절대 금지" 지시(메모리 저장: `nl-lib-never-wipe-db`·`nl-lib-library-competition-deadline`). **대회 이후 최우선으로 별도 라운드에서 처리.**
- `research/`로 옮긴 스크립트 20개 중 15개가 산출물 경로를 여전히 옛 `scripts/...` 위치로 하드코딩 — 재실행 시 `research/`가 아니라 `scripts/`에 다시 산출물이 생긴다(Task 10 리뷰 발견). 코드 수정은 이번 라운드(파일 재배치) 스코프 밖 — 다음에 그 스크립트들을 실제로 재실행할 일이 생기면 그때 경로 상수를 `Path(__file__).parent` 기준으로 고친다.

## 다음 라운드 진입점
- 범위 미정 — `docs/roadmap/00_status.md`와 `README.md` §10 로드맵에서 확인

## 상태
- [x] 테스트 green (해당 변경 없음 — 문서/파일 이동만, `py_compile` 검증 완료)
- [x] 수동 스모크 확인 (docker-compose config 파싱 확인)
- [ ] `dev` 머지 승인
- [ ] `dev→main` 머지 + push 완료
```

- [ ] **Step 2: `docs/roadmap/00_status.md`의 현재 상태·라운드 이력·다음 할 일 전체 갱신** (Task 3 리뷰 이슈 I1 반영 — 라운드 이력만 "완료"로 바뀌고 현재 상태가 "진행 중"으로 남아 자기모순되는 것 방지)

`docs/roadmap/00_status.md`의 세 섹션을 함께 갱신한다 — "현재 상태"의 round01 불릿도 반드시 함께 고친다(라운드 이력만 고치면 같은 파일 안에서 "진행 중"과 "완료"가 공존하게 된다):

```markdown
## 현재 상태
- NL-Lib 핵심 검색 파이프라인(BGE-M3 하이브리드 검색 · 메타데이터 이중 전략 · Contextual Chunking) 구현·운영 중.
- 대량 인덱싱 파이프라인(OCR 라우팅: VLM/Surya/Tesseract/fitz) 운영 중 — 상세: `docs/ops/bulk_ingest_runbook.md`.
- round01: museum 스타일 개발 체계(`CLAUDE.md`·`GIT_WORKFLOW.md`·round 워크플로우·`research/` 산출물 규칙) 도입 완료.

## 다음 할 일
- round01 완료. 다음 라운드 범위는 미정 — 착수 시 이 문서와 `README.md` §10 로드맵을 함께 갱신한다.
- **[보류 — 도서관 대회 시연 이후]** `app/api/admin.py` Milvus expression injection 보안 수정. 대회 전까지는 손대지 않는다(round01-완료노트 §이월 참고).

## 라운드 이력
| 라운드 | 요약 | 상태 |
|---|---|---|
| round01 | [개발 체계 도입](round01-완료노트.md)(museum 스타일 이식) | 완료 |
```

- [ ] **Step 3: README.md §5(프로젝트 구조) 갱신** (Task 1 리뷰 이슈 10 반영)

`README.md` §5의 트리 구조에서 다음을 반영한다: 실존하지 않는 `migrate_add_KCI.sql` 참조 제거(실제 파일명은 4개의 `migrate_add_book_figures.sql`·`migrate_add_cover_image.sql`·`migrate_add_introduction.sql`·`migrate_add_themes.sql` — 파일명은 확인 후 정확히 반영), `docs/`·`scripts/`·`research/`를 트리에 추가, 배치 원칙은 `CLAUDE.md` §1이 정본임을 명시하는 한 줄 추가.

- [ ] **Step 4: 검증**

Run: `grep -q "완료" docs/roadmap/00_status.md && grep -q "dev→main 머지 + push 완료" docs/roadmap/round01-완료노트.md && grep -q "research/" README.md && echo OK`
Expected: `OK`

- [ ] **Step 5: 커밋**

```bash
git add docs/roadmap/round01-완료노트.md docs/roadmap/00_status.md README.md
git commit -m "[Docs] round01 — 완료노트 작성, 상태 문서 갱신, README 구조 반영"
```

---

### Task 15: 최종 검증 + dev 머지 + round-finish

**이 Task는 서브에이전트에 위임하지 않고 컨트롤러(메인 세션)가 직접 수행한다** — 사용자 승인 대기가 포함돼 있어 단발성 subagent 실행과 맞지 않는다.

**Files:** 없음(git 작업만)

> **Task 9 리뷰에서 남은 잔재**: 공유 체크아웃(`C:\Users\LANDSOFT\mygit\NL_library_AI`, 워크트리 아님)에 `scripts_debug_out.txt`·`scripts_debug_out2.txt`·`soffice_log2.txt` 3개 미추적 파일이 격리 때문에 그대로 남아있다(무해하지만 이제 `.gitignore`로 커버됨). 이 Task에서 공유 체크아웃으로 옮겨간 뒤(Step 6) 한 번 `rm scripts_debug_out.txt scripts_debug_out2.txt soffice_log2.txt`로 정리한다.

- [ ] **Step 1: 작업 트리 점검 — 의도한 파일만 변경됐는지**

Run: `git status --short`
Expected: `?? app/scripts/recheck_table_fill.py` 한 줄만 — Task 1~14는 전부 커밋 완료했으므로 그 외엔 클린해야 한다. `app/scripts/recheck_table_fill.py`는 round01 스코프 밖의 별개 WIP이므로 미추적 상태로 남아있는 것이 정상이다(round01에서 손대지 않는다).

- [ ] **Step 2: docker-compose 파싱 확인 (물리 경로 무변경 실증)**

Run: `docker compose -f docker-compose.yml config --quiet && echo PROD_OK`
Expected: `PROD_OK`

Run: `docker compose -f docker-compose.dev.yml config --quiet && echo DEV_OK`
Expected: `DEV_OK`

- [ ] **Step 3: 이동된 스크립트 스모크 실행 (경로 참조 깨짐 없는지 최소 1건)**

Run: `python -m py_compile research/ocr-extraction-comparison/compare_extraction_methods.py && echo SMOKE_OK`
Expected: `SMOKE_OK`

- [ ] **Step 4: CLAUDE.md 경로 참조 실측 스윕 (Task 1 리뷰 이슈 4 반영 — `grep -c "|"` 트리비얼 체크 대체)**

`CLAUDE.md` §4 표의 모든 백틱 경로(및 §1에서 언급된 예시 경로)를 하나씩 존재 확인한다 — Task 2~14 완료 후에는 전부 존재해야 한다. 하나라도 dangling이면 BLOCKED로 보고.

- [ ] **Step 5: 사용자 승인 요청 — `dev` 머지**

여기서 실행을 멈추고 사용자에게 보고한다: "Task 1~14 완료, Step 1~4 검증 통과. `feat/round01-dev-system-bootstrap-wt`을 `dev`에 머지해도 될까요?" **승인 전 진행 금지.**

- [ ] **Step 6: 승인 후 `dev` 머지 — 공유 체크아웃에서 수행** (Task 7 리뷰 반영: 격리 워크트리 안에서 `main`/`dev`를 체크아웃하지 않는다)

이 워크트리(`.claude/worktrees/round01-dev-system-bootstrap`)가 아니라 공유 체크아웃(`C:\Users\LANDSOFT\mygit\NL_library_AI`)에서 실행한다. 공유 체크아웃은 지금 빈 브랜치 `feat/round01-dev-system-bootstrap`(이름 충돌로 안 쓰인 것) 위에 있으므로 `dev` 체크아웃이 막히지 않는다.

```bash
git checkout dev
git merge --no-ff feat/round01-dev-system-bootstrap-wt -m "Merge feat/round01-dev-system-bootstrap-wt into dev — round01"
git push origin dev
```

- [ ] **Step 7: 라운드 종료 승인 요청**

사용자에게 라운드 종료(= `dev→main` 머지 + push) 승인을 구한다. **승인 전 진행 금지.**

- [ ] **Step 8: 승인 후 `/round-finish` 스킬 실행 — 공유 체크아웃에서**

공유 체크아웃에서 `.claude/skills/round-finish/SKILL.md`의 절차를 그대로 따른다(머지전 가드 `git rev-list --count main..dev`·`git fetch origin && git rev-list --count main..origin/main` 포함) → `dev→main` 머지 → `git push origin main && git push -u origin dev` → `git checkout dev`로 복귀.

- [ ] **Step 9: 워크트리 정리**

`ExitWorktree`로 워크트리를 정리한다(`action: "keep"` — main 머지까지 끝난 뒤 사용자가 확인할 수 있게 바로 지우지 않는다). 공유 체크아웃의 미사용 빈 브랜치 `feat/round01-dev-system-bootstrap`(worktree 이름 충돌로 실제 작업에 쓰이지 않음)도 사용자 확인 후 정리 대상으로 보고.

- [ ] **Step 10: 최종 검증**

Run: `git log main -1 --oneline && git status --short`
Expected: 머지 커밋이 `main` 최신이고, 작업 트리 클린.
