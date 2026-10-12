// frontend/composables/useSectionFollow.ts
import {
  computed,
  getCurrentInstance,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from "vue";
import type { ResearchPhase } from "~/utils/researchEvents";
import {
  NO_POINTER,
  breaksFollow,
  followBehavior,
  followKeyDirection,
  followPill,
  inFollowPhase,
  notePointer,
  scrollsInner,
  shouldFollowMove,
  type FollowInput,
  type FollowScroller,
  type PointerTrail,
} from "~/utils/researchFollow";

// 따라가기를 멈추는 사용자 입력(keydown 은 스크롤 키와 Tab). scroll 은 넣지 않는다 — 화면이 부른 이동·스크롤 앵커링도 scroll 을
// 낸다(utils/researchFollow.ts 머리)
const USER_INPUTS = ["wheel", "touchmove", "keydown", "pointerdown"] as const;
// 포인터를 움직인 곳·누른 곳을 적는 입력 — 따라가기를 멈추지 않는다. 열린 인용 팝오버를 사용자가 열었는지 가르는 데만 쓴다(isBlocked)
const POINTER_INPUTS = ["pointermove", "pointerdown"] as const;
// 키를 스스로 쓰는 자리 — 안에서 누른 방향키·Space 는 페이지를 굴리지 않는다(입력칸·메뉴·목록 상자·대화상자)
const KEY_OWNERS = "input, textarea, select, [contenteditable], [role='menu'], [role='listbox'], [role='dialog']";
// Space 를 누름으로 받는 자리 — 초점이 간 버튼(인용칩·현황 카드의 절)·펼침 머리 위의 Space 는 페이지를 굴리지 않는다
const SPACE_OWNERS = "button, [role='button'], summary";
// 페이지를 묶는 모달 — 원문 뷰어(PdfViewer.vue lockPage)·온보딩(OnboardingModal.vue lock)이 열린 동안 documentElement 의 overflow 를
// 숨긴다. 그동안의 입력(뷰어 머리 줄·어두운 바탕 위의 휠·터치 포함)은 페이지를 굴리지 않는다. PDF 쪽 위의 휠은 iframe 안이라 이 창에 오지 않는다
const PAGE_LOCKERS = "[aria-modal='true']";

export interface SectionFollow {
  following: Readonly<Ref<boolean>>;
  pill: ComputedRef<string | null>;
  // 알약 — 다시 따라가며 지금 대상(사이면 마지막으로 진행한 자리)으로 곧바로 옮기고 초점도 그 자리로 옮긴다
  resume(): void;
  // 현황 카드에서 절을 눌러 옮길 때
  pause(): void;
}

function ownsKeys(t: EventTarget | null): boolean {
  return t instanceof Element && t.closest(KEY_OWNERS) !== null;
}

function ownsSpace(t: EventTarget | null): boolean {
  return t instanceof Element && t.closest(SPACE_OWNERS) !== null;
}

// 입력을 페이지가 아니라 안쪽 스크롤 칸(넓은 화면 A 의 옆 칸·근거 장부 목록·인용문)이 받는가 — 입력 대상(자기 포함)에서 body
// 앞까지 조상의 세로 스크롤 모양을 모아 scrollsInner 로 잰다(dir: 1 아래, -1 위, 0 모름). 대상이 요소가 아니면(창·문서) 페이지다
function innerOf(t: EventTarget | null, dir: number): boolean {
  if (!(t instanceof Element) || !dir) return false;
  const chain: FollowScroller[] = [];
  for (let a: Element | null = t; a && a !== document.body && a !== document.documentElement; a = a.parentElement) {
    chain.push({
      overflowY: window.getComputedStyle(a).overflowY,
      scrollTop: a.scrollTop,
      scrollHeight: a.scrollHeight,
      clientHeight: a.clientHeight,
    });
  }
  return scrollsInner(chain, dir);
}

// 창 이벤트를 판단 함수가 읽는 모양으로 옮긴다. 버튼 위의 Space 는 누름이라 입력칸 안의 키처럼 본다(editable). touchDir 는
// 터치 이동의 방향(손가락이 위로 가면 1 — 내용이 아래로 구른다, 모르면 0)
function inputOf(e: Event, touchDir: number): FollowInput | null {
  switch (e.type) {
    case "wheel": {
      const w = e as WheelEvent;
      return { type: "wheel", deltaX: w.deltaX, deltaY: w.deltaY, ctrlKey: w.ctrlKey, inner: innerOf(w.target, Math.sign(w.deltaY)) };
    }
    case "touchmove":
      return { type: "touchmove", inner: innerOf(e.target, touchDir) };
    case "keydown": {
      const k = e as KeyboardEvent;
      const editable = ownsKeys(k.target) || (k.key === " " && ownsSpace(k.target));
      const inner = !editable && innerOf(k.target, followKeyDirection(k.key, k.shiftKey));
      return { type: "keydown", key: k.key, editable, ctrlKey: k.ctrlKey, metaKey: k.metaKey, altKey: k.altKey, inner };
    }
    case "pointerdown":
      return { type: "pointerdown", clientX: (e as PointerEvent).clientX, viewportWidth: document.documentElement.clientWidth };
    default:
      return null;
  }
}

/**
 * 지금 진행하는 절을 스크롤이 따라가게 한다(spec D22). 대상(자리 id)이 바뀌면 그 자리를 화면 안으로 옮기고(가장 가까운 끝 — 방금
 * 끝난 절이 위에 남는다), 탐색·작성 중에 사용자가 직접 굴리거나 Tab 으로 초점을 옮기면 멈춘다 —
 * 멈춘 동안은 알약 글(pill)을 내고, 알약을 누르면(resume) 다시 따라가며 지금 대상으로 곧바로 옮기고 초점도 그 자리로 옮긴다.
 * 절과 절 사이(하위질문과 하위질문 사이)처럼 대상이 잠깐 없는 동안에도 알약은 마지막으로 진행한 자리를 가리키며 남는다.
 * 처음 본 대상은 기준으로만 삼는다 — 들어온 화면을 곧바로 끌고 내려가지 않고 다음 바뀜부터 옮긴다. 막힌 동안(isBlocked) 바뀐
 * 대상은 지나간 것으로 두고 다음 바뀜에 옮긴다. 모달이 페이지를 묶은 동안의 입력은 멈춤으로 보지 않는다 — 원문 뷰어를 닫으면
 * 따라가던 대로 다음 바뀜에 옮긴다. 안쪽 스크롤 칸(옆 칸·근거 장부·인용문)이 받는 입력도 페이지를 굴리지 않아 멈춤이 아니다.
 * 막힘에는 마지막으로 포인터를 움직인 곳·누른 곳(PointerTrail)을 넘긴다 — 손을 뗀 포인터 밑으로 칩이 와서 hover 로 열린 팝오버를
 * 사용자가 연 것과 가른다(userOpenedPopover)
 */
export function useSectionFollow(opts: {
  phase: ComputedRef<ResearchPhase | null>;
  target: ComputedRef<string | null>;
  // 옮기려는 순간에 부른다(DOM 을 본다). pointer 는 마지막으로 포인터를 움직인 곳·누른 곳 — 창 리스너가 없으면(컴포넌트 밖) 비어 있다
  isBlocked: (pointer: PointerTrail) => boolean;
  // 상세에서 돌아온 화면(restore.anchor !== null) — 사용자가 고른 자리를 빼앗지 않게 멈춘 채 시작한다
  startPaused: boolean;
}): SectionFollow {
  const following = ref(!opts.startPaused);
  // 마지막으로 옮겨 간(또는 지나간) 대상 — 사이에 알약이 갈 곳이기도 해 반응형으로 둔다
  const last = ref<string | null>(null);
  // 알약이 갈 곳 — 지금 대상, 절과 절 사이(하위질문과 하위질문 사이 — 쓰는·도는 것이 잠깐 없음)면 마지막으로 진행한 자리.
  // 대상만 보면 멈춘 동안 사이마다 알약이 사라졌다 다시 서고, 그 알약에 Tab 으로 가 있던 초점이 body 로 떨어진다
  const destination = computed(() => opts.target.value ?? last.value);
  const pill = computed(() => followPill({ phase: opts.phase.value, following: following.value, target: destination.value }));
  let primed = false;
  let frame = 0;
  // 터치 이동의 방향을 재는 손가락의 앞 높이 — touchstart 는 높이만 적고 따라가기를 멈추지 않는다(탭은 굴림이 아니다)
  let touchY: number | null = null;
  // 마지막으로 포인터를 움직인 곳·누른 곳 — 막힘(isBlocked)이 열린 인용 팝오버를 사용자가 열었는지 가르는 데 쓴다
  let pointer: PointerTrail = NO_POINTER;

  // 멈춘 동안에도 적는다 — 알약으로 다시 켠 뒤의 막힘도 같은 기준으로 본다
  function onPointer(e: Event): void {
    const p = e as PointerEvent;
    const type = p.type === "pointerdown" ? "pointerdown" : "pointermove";
    pointer = notePointer(pointer, { type, x: p.clientX, y: p.clientY, target: p.target });
  }

  function onTouchStart(e: TouchEvent): void {
    touchY = e.touches[0]?.clientY ?? null;
  }

  // 손가락이 위로 가면(높이가 줄면) 내용은 아래로 구른다. 멈춘 동안에도 높이는 따라 적는다
  function touchDirOf(e: Event): number {
    if (e.type !== "touchmove") return 0;
    const y = (e as TouchEvent).touches[0]?.clientY ?? null;
    const dir = touchY === null || y === null ? 0 : Math.sign(touchY - y);
    touchY = y;
    return dir;
  }

  function onInput(e: Event): void {
    const touchDir = touchDirOf(e);
    // 따라갈 것이 생기기 전(계획·승인 대기·대기열)의 입력은 멈추지 않는다 — 계획을 굴려 읽고 [승인] 해도 탐색부터 따라간다
    if (!following.value || !inFollowPhase(opts.phase.value)) return;
    const input = inputOf(e, touchDir);
    if (!input || !breaksFollow(input)) return;
    // 모달이 페이지를 묶은 동안은 굴려도 페이지가 움직이지 않는다 — 멈추면 닫은 뒤에도 꺼진 채 알약만 남는다
    if (document.querySelector(PAGE_LOCKERS)) return;
    pause();
  }

  // 대상 자리가 DOM 에 붙은 뒤(nextTick) 배치가 끝난 다음 프레임에 옮긴다. 옮기는 순간에 다시 본다 — 그 사이 사용자가 굴렸거나
  // 팝오버를 열었을 수 있다. 알약으로 다시 켠 이동(force)은 막힘을 보지 않는다 — 사용자가 누른 이동이다
  function move(id: string, force: boolean): void {
    void nextTick(() => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (!following.value || (!force && opts.isBlocked(pointer))) return;
        const el = document.getElementById(id);
        if (!el) return;
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        // 따라가며 옮길 때는 가장 가까운 끝에 맞춘다 — 이미 보이면 굴리지 않고, 아래에 있으면 그 자리 끝을 화면 아래에 맞춰 바로
        // 위의 방금 끝난 절(하위질문 자리)이 화면에 남는다. 종합기는 절 i 의 done 을 보내자마자 i+1 의 running 을 보내므로
        // (app/services/research/synthesizer.py 의 절 루프) 머리를 위에 맞추면(start) 절 i 의 본문이 나타나는 순간 화면 위로
        // 밀려난다. 위에 있으면(탐색 → 작성의 첫 자리) 머리를 막대 아래에 맞춘다(문서 scroll-padding-top). 알약을 누른 이동은
        // 사용자가 고른 자리라 머리를 위에 둔다
        el.scrollIntoView({ behavior: followBehavior(reduce), block: force ? "start" : "nearest" });
        // 알약을 누른 이동은 초점도 그 자리로 옮긴다(자리 rs-sec-N·rs-slot-N 은 tabindex=-1, jumpToSection 과 같은 꼴). 누른 알약은
        // 따라가기가 켜지며 사라져 초점이 body 로 떨어지고, 다음 Tab 이 옮겨 간 절이 아니라 알약이 있던 자리(.rs-page 끝)에서
        // 이어진다. 따라가며 옮길 때는 읽거나 고르던 초점을 빼앗지 않는다
        if (force) el.focus({ preventScroll: true });
      });
    });
  }

  function resume(): void {
    following.value = true;
    // 사이(대상이 잠깐 없음)에 누르면 마지막으로 진행한 자리로 간다 — 다음 바뀜(다음 절·하위질문)에 그리로 다시 옮긴다
    const t = destination.value;
    last.value = t;
    if (t !== null) move(t, true);
  }

  function pause(): void {
    following.value = false;
  }

  watch(
    opts.target,
    (t) => {
      if (!primed) {
        primed = t !== null;
        last.value = t;
        return;
      }
      if (t !== null && shouldFollowMove({ following: following.value, blocked: opts.isBlocked(pointer), target: t, last: last.value })) {
        move(t, false);
      }
      if (t !== null) last.value = t;
    },
    { immediate: true },
  );

  // 컴포넌트 밖(단위 테스트)에서는 창 리스너를 걸지 않는다 — useResearchWork 와 같은 꼴
  if (getCurrentInstance()) {
    onMounted(() => {
      for (const type of USER_INPUTS) window.addEventListener(type, onInput, { capture: true, passive: true });
      for (const type of POINTER_INPUTS) window.addEventListener(type, onPointer, { capture: true, passive: true });
      window.addEventListener("touchstart", onTouchStart, { capture: true, passive: true });
    });

    onBeforeUnmount(() => {
      for (const type of USER_INPUTS) window.removeEventListener(type, onInput, true);
      for (const type of POINTER_INPUTS) window.removeEventListener(type, onPointer, true);
      window.removeEventListener("touchstart", onTouchStart, true);
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
    });
  }

  return { following, pill, resume, pause };
}
