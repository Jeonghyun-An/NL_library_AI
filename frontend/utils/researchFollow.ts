// frontend/utils/researchFollow.ts
// 지금 진행하는 절 따라가기(spec §12-3, D22)의 켜고 끄는 판단. 창 이벤트·스크롤은 composables/useSectionFollow.ts 가 한다.
// 따라가기를 멈추는 것은 사용자 입력(굴림·Tab 으로 초점 옮기기)뿐이다(정함 4) — scroll 이벤트로 가르지 않는다. 브라우저의
// 스크롤 앵커링·절이 펼쳐지며 밀린 자리·돌아온 자리 붙잡기(useRestorePosition)가 내는 scroll 을 플래그로 다 거를 수 없고, 화면이
// 부른 scrollIntoView 는 입력 이벤트를 내지 않아 저절로 걸러진다(spec 의 '프로그램 스크롤은 플래그로 거른다'를 이것으로 갈음한다)
import type { SubqView } from "~/types/research";
import { slotElementId, type PlanSlot } from "~/utils/planSlots";
import type { SynthEta } from "~/utils/researchDraft";
import { exploreAttemptStart, fromEarlierAttempt, type ResearchPhase } from "~/utils/researchEvents";

// 창에서 받은 입력 — 이벤트마다 판단에 쓰는 값만 옮긴다(viewportWidth = document.documentElement.clientWidth). inner 는 그 입력을
// 페이지가 아니라 안쪽 스크롤 칸(넓은 화면 A 의 옆 칸·근거 장부 목록·인용문)이 받는가 — 대상의 조상 사슬로 scrollsInner 가 잰다
export type FollowInput =
  | { type: "wheel"; deltaX: number; deltaY: number; ctrlKey: boolean; inner: boolean }
  | { type: "touchmove"; inner: boolean }
  | { type: "keydown"; key: string; editable: boolean; ctrlKey: boolean; metaKey: boolean; altKey: boolean; inner: boolean }
  | { type: "pointerdown"; clientX: number; viewportWidth: number };

// 입력 대상(자기 포함)에서 위로 올라가며 본 조상의 세로 스크롤 모양 — 가까운 것부터, body·html(창)은 넣지 않는다.
// overflowY 는 getComputedStyle 의 값
export type FollowScroller = { overflowY: string; scrollTop: number; scrollHeight: number; clientHeight: number };

// 페이지를 굴리는 키(" " 는 Space)
export const FOLLOW_KEYS: readonly string[] = ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "];
export const FOLLOW_PILL_WRITE = "↓ 지금 쓰는 곳으로";
// 탐색 중에는 쓰는 글이 없다 — 도는 하위질문의 자리로 간다
export const FOLLOW_PILL_EXPLORE = "↓ 지금 찾는 곳으로";

// 사용자가 굴릴 수 있는 세로 overflow — hidden·clip 칸은 사용자가 굴리지 못한다
const USER_SCROLLING = new Set(["auto", "scroll", "overlay"]);
// 스크롤 키가 굴리는 방향(1 아래, -1 위). Space 는 Shift 에 따라 갈린다(followKeyDirection)
const KEY_DIRECTION: Readonly<Record<string, number>> = { ArrowUp: -1, PageUp: -1, Home: -1, ArrowDown: 1, PageDown: 1, End: 1 };

export function breaksFollow(e: FollowInput): boolean {
  switch (e.type) {
    case "wheel": {
      // 세로가 앞설 때만 — 가로 휠(트랙패드 옆 밀기)·Ctrl+휠(확대)은 화면을 굴리지 않는다. 안쪽 칸이 받는 휠도 페이지는 그대로다
      const dy = Math.abs(e.deltaY);
      return !e.inner && !e.ctrlKey && dy > 0 && dy >= Math.abs(e.deltaX);
    }
    case "touchmove":
      return !e.inner;
    case "keydown":
      // Tab·Shift+Tab 은 초점을 옮기고 브라우저는 초점 받은 요소가 보이게 창을 굴린다 — 따라가면 그 초점이 화면 밖에 남는다.
      // 입력칸·인용 팝오버(role=dialog)·메뉴를 떠나는 Tab 도 같다(키를 스스로 쓰는 자리도 Tab 은 넘긴다). Ctrl+Tab(탭 전환)·
      // Cmd/Alt+Tab(앱·창 전환)은 페이지의 초점을 옮기지 않는다. 모달이 초점을 가둔 동안은 composable 이 거른다
      if (e.key === "Tab") return !e.ctrlKey && !e.metaKey && !e.altKey;
      // 입력칸 안의 키(글자 사이 이동·공백)와 안쪽 칸이 받는 키(옆 칸 안 초점의 방향키)는 페이지를 굴리지 않는다
      if (e.editable || e.inner || !FOLLOW_KEYS.includes(e.key)) return false;
      return modifiedScrolls(e);
    case "pointerdown":
      // 페이지 스크롤바는 문서 폭(clientWidth) 바깥 띠다 — 그 띠를 누르거나 끄는 것은 사용자가 굴리는 것이다. 안쪽 칸의
      // 스크롤바는 그 띠 안이라 멈추지 않는다(안쪽 칸 위의 휠과 같은 판정)
      return e.clientX >= e.viewportWidth;
  }
}

// 입력이 페이지가 아니라 안쪽 스크롤 칸만 굴리는가(dir: 1 아래, -1 위, 0 모름). 휠·터치·스크롤 키는 대상에서 가까운 칸부터
// 그 방향으로 아직 굴러갈 수 있는 칸이 받고, 끝에 닿은 칸은 바깥 칸으로 넘긴다(연쇄 스크롤) — 받을 칸이 하나도 없으면 창이
// 받는다(페이지가 구른다). 넘치지 않는 칸(짧은 옆 칸·가로로만 굴러가는 감싸개)은 굴러갈 틈이 없어 저절로 건너뛴다. 끝까지
// 1px 이 안 남으면 끝으로 본다 — 확대한 화면은 scrollTop 이 소수라 끝에서도 몇 분의 1px 이 남는다. 방향을 모르면 안쪽으로
// 보지 않는다(멈추는 쪽 — 알약으로 다시 켤 수 있다). overscroll-behavior 는 보지 않는다 — 이 화면의 칸은 쓰지 않는다
export function scrollsInner(chain: readonly FollowScroller[], dir: number): boolean {
  if (!dir) return false;
  return chain.some((a) => {
    if (!USER_SCROLLING.has(a.overflowY)) return false;
    const room = dir > 0 ? a.scrollHeight - a.clientHeight - a.scrollTop : a.scrollTop;
    return room >= 1;
  });
}

// 스크롤 키가 굴리는 방향 — 1 아래, -1 위, 페이지를 굴리지 않는 키 0. Shift+Space 는 한 화면 위다. 그 밖의 수식 키는 방향을
// 바꾸지 않는다(Ctrl+Home 은 위, Cmd+↓ 는 아래 — 굴리는지는 breaksFollow 가 가른다)
export function followKeyDirection(key: string, shiftKey: boolean): number {
  if (key === " ") return shiftKey ? -1 : 1;
  return KEY_DIRECTION[key] ?? 0;
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

// 사용자 입력이 따라가기를 멈추는 단계 — 따라갈 것이 생기는 탐색·작성뿐이다. 그 앞(계획·승인 대기·대기열)에 계획을 굴려 읽거나
// Tab 으로 [승인] 까지 간 입력이 멈추면 탐색이 시작될 때 이미 꺼져 있어 기본 켬이 지켜지지 않는다. 끝난 잡도 멈추지 않는다 —
// 다시 시도하면 처음처럼 따라간다
export function inFollowPhase(phase: ResearchPhase | null): boolean {
  return phase === "exploring" || phase === "synthesizing";
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
