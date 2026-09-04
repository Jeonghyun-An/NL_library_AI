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
- **dev** (`docker-compose.dev.yml`): 데이터 계층만 별도(`postgres-dev`·`redis-dev`·`minio-dev`·`milvus-dev`, DB명 `nl_lib_dev` 등 `_dev` 접미). GPU를 크게 먹는 vllm/gemma/flux는 prod 스택 컨테이너를 `nl-lib-net` 경유로 그대로 공유한다(따로 띄우지 않음).
- 두 스택은 완전히 분리된 데이터 계층 + 공유 GPU 서비스라는 단일 서버 구조다. museum류의 별도 물리 노드 SSH 터널은 필요 없다.
- 개발 사이클: `docker compose -f docker-compose.dev.yml up -d`로 dev 데이터 계층 기동 → 코드 개발·검증 → 확정되면 위 브랜치 흐름대로 병합.

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
