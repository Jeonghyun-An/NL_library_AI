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
3. 라운드 중 라이브에서 새로 겪은 함정이 있으면 `docs/ops/recurring-gotchas.md`에 추가됐는지 확인.
4. `docs/roadmap/00_status.md` 갱신 확인(최종 갱신 날짜·현재 상태·다음 할 일·라운드 이력 — 라운드 이력만 바꾸고 현재 상태를 그대로 두지 않는다).
5. `dev → main` 머지
   ```bash
   git checkout main
   git merge --no-ff dev -m "Merge dev into main — round<N> (<요약>)"
   ```
6. origin push
   ```bash
   git push origin main && git push origin dev
   ```
7. 작업 복귀: `git checkout dev`.

## 주의
- 평소 작업은 `dev`에서 분기 → 작업 브랜치. `main` 직접 작업은 이 종료 절차에서만.
- 비밀정보·데이터·미공개 자료는 커밋·push 금지(`.gitignore`).
