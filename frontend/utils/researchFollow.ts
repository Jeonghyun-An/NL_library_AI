// frontend/utils/researchFollow.ts
// 지금 진행하는 절 따라가기(spec §12-3, D22)의 켜고 끄는 판단. 창 이벤트·스크롤은 composables/useSectionFollow.ts 가 한다.
// 따라가기를 멈추는 것은 사용자 입력뿐이다(정함 4) — scroll 이벤트로 가르지 않는다. 브라우저의 스크롤 앵커링·절이 펼쳐지며 밀린
// 자리·돌아온 자리 붙잡기(useRestorePosition)가 내는 scroll 을 플래그로 다 거를 수 없고, 화면이 부른 scrollIntoView 는 입력
// 이벤트를 내지 않아 저절로 걸러진다(spec 의 '프로그램 스크롤은 플래그로 거른다'를 이것으로 갈음한다)
import type { SubqView } from "~/types/research";
import { slotElementId, type PlanSlot } from "~/utils/planSlots";
import type { SynthEta } from "~/utils/researchDraft";
import { exploreAttemptStart, fromEarlierAttempt, type ResearchPhase } from "~/utils/researchEvents";

// 창에서 받은 입력 — 이벤트마다 판단에 쓰는 값만 옮긴다(viewportWidth = document.documentElement.clientWidth)
export type FollowInput =
  | { type: "wheel"; deltaX: number; deltaY: number; ctrlKey: boolean }
  | { type: "touchmove" }
  | { type: "keydown"; key: string; editable: boolean; ctrlKey: boolean; metaKey: boolean; altKey: boolean }
  | { type: "pointerdown"; clientX: number; viewportWidth: number };

// 페이지를 굴리는 키(" " 는 Space)
export const FOLLOW_KEYS: readonly string[] = ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "];
export const FOLLOW_PILL_WRITE = "↓ 지금 쓰는 곳으로";
// 탐색 중에는 쓰는 글이 없다 — 도는 하위질문의 자리로 간다
export const FOLLOW_PILL_EXPLORE = "↓ 지금 찾는 곳으로";

export function breaksFollow(e: FollowInput): boolean {
  switch (e.type) {
    case "wheel": {
      // 세로가 앞설 때만 — 가로 휠(트랙패드 옆 밀기)·Ctrl+휠(확대)은 화면을 굴리지 않는다
      const dy = Math.abs(e.deltaY);
      return !e.ctrlKey && dy > 0 && dy >= Math.abs(e.deltaX);
    }
    case "touchmove":
      return true;
    case "keydown":
      // 입력칸 안의 키(글자 사이 이동·공백)는 페이지를 굴리지 않는다
      if (e.editable || !FOLLOW_KEYS.includes(e.key)) return false;
      return modifiedScrolls(e);
    case "pointerdown":
      // 페이지 스크롤바는 문서 폭(clientWidth) 바깥 띠다 — 그 띠를 누르거나 끄는 것은 사용자가 굴리는 것이다
      return e.clientX >= e.viewportWidth;
  }
}

// 스크롤 키에 수식 키를 함께 누른 조합이 페이지를 굴리는가(수식 키가 없으면 굴린다). 굴리는 조합은 셋뿐이다 — Ctrl+Home/End
// (Windows·Linux 의 문서 처음·끝 — Chromium 은 Firefox 에 맞춰 Ctrl 조합 가운데 이 둘만 굴린다), Cmd+↑/↓(macOS 의 문서
// 처음·끝), Option+↑/↓(macOS 의 PageUp/PageDown). 그 밖의 조합 — Ctrl+PageUp/PageDown(탭 전환)·Alt+Home(브라우저 홈)·
// Ctrl/Cmd+Space(입력기 전환)·Ctrl+방향키, 수식 키를 둘 이상 함께 누른 것 — 은 굴리지 않는다. 플랫폼은 가르지 않는다: Windows 의
// Alt+↑/↓ 처럼 굴리지 않는 곳에서 멈춰도 알약으로 다시 켤 수 있지만, 굴렸는데 놓치면 화면을 도로 끌고 간다
function modifiedScrolls(e: Extract<FollowInput, { type: "keydown" }>): boolean {
  const mods = Number(e.ctrlKey) + Number(e.metaKey) + Number(e.altKey);
  if (mods === 0) return true;
  if (mods > 1) return false;
  if (e.ctrlKey) return e.key === "Home" || e.key === "End";
  return e.key === "ArrowUp" || e.key === "ArrowDown";
}

// 보고서 절의 자리 id — ReportView 의 절 <section> 과 현황 카드의 jumpToSection 이 같은 글자를 쓴다
export function sectionElementId(idx: number): string {
  return `rs-sec-${idx}`;
}

// 따라갈 자리. 종합 중 초안이 있으면 쓰는 절, 첫 절 전이면 그 절이 될 하위질문의 자리(절 번호를 아는 자리만),
// 탐색 중이면 도는 하위질문의 자리. 쓰는·도는 것이 없거나(사이) 그 밖의 단계(최종본 포함)는 null
export function followTarget(input: {
  phase: ResearchPhase | null;
  eta: SynthEta;
  hasDraft: boolean;
  slots: readonly PlanSlot[];
  subqs: readonly SubqView[];
}): string | null {
  if (input.phase === "synthesizing") {
    const idx = input.eta.runningIdx;
    if (idx === null) return null;
    if (input.hasDraft) return sectionElementId(idx);
    const slot = input.slots.find((s) => s.sectionIdx === idx);
    return slot ? slotElementId(slot.subqIdx) : null;
  }
  if (input.phase === "exploring") {
    // 이번 시도의 행만 — 탐색부터 다시 도는 재시도에서 이전 시도에 남은 행은 도는 하위질문이 아니다(stopPoint 와 같은 규칙)
    const since = exploreAttemptStart(input.subqs);
    const running = input.subqs.find((s) => s.status === "running" && !fromEarlierAttempt(s, since));
    return running ? slotElementId(running.idx) : null;
  }
  return null;
}

// 옮기지 않는 때 — 돌아온 자리를 맞추는 중, 원문 뷰어를 연 동안, 인용 팝오버를 읽는 동안(고정·hover 를 가리지 않는다)
export function followBlocked(c: { restoring: boolean; pdfOpen: boolean; popoverOpen: boolean }): boolean {
  return c.restoring || c.pdfOpen || c.popoverOpen;
}

export function shouldFollowMove(s: { following: boolean; blocked: boolean; target: string | null; last: string | null }): boolean {
  return s.following && !s.blocked && s.target !== null && s.target !== s.last;
}

export function followPill(s: { phase: ResearchPhase | null; following: boolean; target: string | null }): string | null {
  if (s.following || s.target === null) return null;
  if (s.phase === "synthesizing") return FOLLOW_PILL_WRITE;
  if (s.phase === "exploring") return FOLLOW_PILL_EXPLORE;
  return null;
}

// 움직임 줄이기를 켠 사람에게는 부드럽게 굴리지 않고 곧바로 옮긴다
export function followBehavior(reducedMotion: boolean): "auto" | "smooth" {
  return reducedMotion ? "auto" : "smooth";
}
