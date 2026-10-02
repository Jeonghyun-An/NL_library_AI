// frontend/composables/useRestorePosition.ts
import { nextTick, onBeforeUnmount, onMounted, ref, watch, type ComputedRef, type Ref } from "vue";
import {
  anchorSelector,
  excludedAnchor,
  excludedDetailUrl,
  parseAnchor,
  readReturnSpot,
  type Anchor,
  type ReturnSpot,
} from "~/utils/detailSource";
import {
  RESTORE_HOLD_MS,
  RESTORE_MAX_WAIT_MS,
  RESTORE_RETRY_MS,
  hasSpot,
  holdDelta,
  isUserMove,
  restoreStep,
  scrollDelta,
  spotFromState,
  spotOf,
  spotState,
  stateWithSpot,
  stateWithoutSpot,
  targetTop,
  withSpot,
  withoutSpot,
} from "~/utils/restorePosition";

// 사용자가 먼저 움직이면 맞추지 않고, 맞춘 뒤 움직이면 더 붙잡지 않는다 — 읽기 시작한 화면을 끌고 가지 않게.
// scroll 은 넣지 않는다 — 맞추며 직접 굴린 것도 scroll 을 낸다
const USER_MOVES = ["wheel", "touchstart", "keydown", "pointerdown"] as const;

// 서버 렌더에는 history 가 없다. 두 화면 모두 내용을 마운트 뒤에 받아 pending 이 서버 렌더 결과를 바꾸지 않는다
function entryState(): unknown {
  return import.meta.client ? window.history.state : null;
}

// 접힌 목록 안의 사본(display:none)은 높이가 없다
function isShown(el: HTMLElement): boolean {
  return el.isConnected && el.getClientRects().length > 0;
}

/**
 * 상세에서 돌아온 화면에서, 떠날 때 누른 요소를 같은 화면 높이에 즉시 맞추고 사용자가 움직이기 전까지 붙잡아 둔다.
 * 자리는 주소의 at·y 에서, 없으면 그 기록의 history.state 에 남긴 자리(한 번 맞춰 주소를 비운 뒤 앞으로 갔다 다시
 * 돌아온 경우)에서 읽는다. ready 는 그 요소가 든 내용(보고서·복원한 결과 목록)이 그려질 준비가 됐는지 — 화면이 정한다.
 * 쓰는 화면은 definePageMeta({ scrollToTop: (to) => !holdsReturnSpot(to.query, history.state) }) 로 Nuxt 의 스크롤을 끈다
 */
export function useRestorePosition(
  ready: Ref<boolean> | ComputedRef<boolean>,
  opts: { maxWaitMs?: number } = {},
): { pending: Readonly<Ref<boolean>>; anchor: Anchor | null } {
  const route = useRoute();
  const router = useRouter();
  // 들어온 순간의 자리만 본다 — 이 화면을 떠나기 직전 주소에 at·y 를 다시 싣는데(useDetailLeave) 그때 맞추면 안 된다
  const given = hasSpot(route.query) ? route.query : spotFromState(entryState());
  const spot = readReturnSpot(given ?? {});
  const selector = spot.at ? anchorSelector(spot.at) : null;
  const anchor = spot.at ? parseAnchor(spot.at) : null;
  const pending = ref(selector !== null);
  let deadline = 0;
  let scheduled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  // 맞추는 프레임과 붙잡는 프레임은 차례로 돌아 하나만 쥔다
  let frame = 0;
  // 맞춘 자리를 그 기록의 state 에 다 적었는지, 그 전에 사용자가 움직였는지
  let remembered = false;
  let moved = false;
  let disposed = false;

  function listen(): void {
    for (const type of USER_MOVES) window.addEventListener(type, onUserMove, { capture: true, passive: true });
  }

  function unlisten(): void {
    for (const type of USER_MOVES) window.removeEventListener(type, onUserMove, true);
  }

  function cancelFrames(): void {
    if (timer) clearTimeout(timer);
    timer = null;
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  }

  // 맞춘 뒤 처음 움직이면 더 붙잡지 않고 남긴 자리도 지운다 — 움직이기 전까지는 앞뒤로 오가거나 새로고침해도 같은
  // 요소로 돌아와야 하지만, 움직인 뒤에는 그 요소가 더는 읽던 자리가 아니다
  function onUserMove(e: Event): void {
    if (!isUserMove(e)) return;
    unlisten();
    cancelFrames();
    if (pending.value) {
      finish(null);
      return;
    }
    moved = true;
    if (remembered) forgetSpot();
  }

  function finish(aligned: HTMLElement | null): void {
    if (!pending.value) return;
    pending.value = false;
    if (!aligned) {
      unlisten();
      dropSpot();
      return;
    }
    // 다 적은 뒤에야 지운다 — 먼저 지우면 늦게 끝난 replace 가 자리를 다시 싣는다
    void rememberSpot().finally(() => {
      remembered = true;
      if (moved && !disposed) forgetSpot();
    });
  }

  // 맞춘 자리를 그 기록의 state 에 남기고 주소에서는 뗀다 — 새로고침·링크 복사에 옛 자리가 따라가지 않되, 상세로 앞으로
  // 갔다 돌아와도 같은 요소로 온다. 상세의 [돌아가기]가 고르는 router.back() 은 이 기록의 깨끗한 주소로 온다
  function rememberSpot(): Promise<unknown> {
    if (hasSpot(route.query)) return router.replace({ query: withoutSpot(route.query), state: spotState(spot) });
    window.history.replaceState(stateWithSpot(window.history.state, spot), "");
    return Promise.resolve();
  }

  // 맞추지 못했으면(요소가 없음·사용자가 먼저 움직임·모양이 틀림) 남긴 자리도 비운다 — 다음에 돌아와 엉뚱한 데로 끌지 않게
  function dropSpot(): void {
    if (hasSpot(route.query)) void router.replace({ query: withoutSpot(route.query), state: spotState(null) });
    else forgetSpot();
  }

  // 주소는 그대로 두고(url 인자 생략) state 의 자리만 지운다
  function forgetSpot(): void {
    if (spotFromState(window.history.state)) window.history.replaceState(stateWithoutSpot(window.history.state), "");
  }

  function visibleTarget(): HTMLElement | null {
    return Array.from(document.querySelectorAll<HTMLElement>(selector!)).find(isShown) ?? null;
  }

  function tryAlign(): void {
    timer = null;
    frame = 0;
    if (!pending.value) return;
    const el = visibleTarget();
    switch (restoreStep(el !== null, Date.now(), deadline)) {
      case "retry":
        timer = setTimeout(tryAlign, RESTORE_RETRY_MS);
        return;
      case "align": {
        const top = targetTop(spot.y, window.innerHeight);
        window.scrollBy({ top: scrollDelta(el!.getBoundingClientRect().top, top), behavior: "instant" });
        // 인용칩은 초점을 돌려 주면 칩의 초점 열림으로 팝오버가 다시 열린다
        if (anchor?.kind === "cite") el!.focus({ preventScroll: true });
        finish(el);
        hold(el!, top);
        return;
      }
      case "give-up":
        // 보고서가 다른 시도로 바뀌었거나 결과가 바뀌어 요소가 없다 — 오류 없이 맨 위에 둔다
        finish(null);
        return;
    }
  }

  // 맞춘 뒤 사용자가 움직이기 전까지 그 요소를 같은 화면 높이에 붙잡는다 — 위쪽의 AI 요약을 다시 받아 펼치거나 인용 논문을
  // 맨 위로 올릴 때, 초안 절이 올라오며 나타날 때 밀린 만큼 즉시 되돌린다. 목표 높이는 맞출 때 한 번 정한 것을 쓴다
  function hold(el: HTMLElement, top: number): void {
    const until = Date.now() + RESTORE_HOLD_MS;
    const step = (): void => {
      frame = 0;
      if (Date.now() >= until || !isShown(el)) return;
      const delta = holdDelta(el.getBoundingClientRect().top, top);
      if (delta !== 0) window.scrollBy({ top: delta, behavior: "instant" });
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
  }

  // 내용이 DOM 에 붙은 뒤(nextTick) 배치가 끝난 다음 프레임에 잰다. 기한은 내용이 준비된 때부터 센다 —
  // 늦게 붙는 목록은 기다리되 느린 응답 시간은 기한에 넣지 않는다
  function schedule(): void {
    if (!pending.value || scheduled) return;
    scheduled = true;
    deadline = Date.now() + (opts.maxWaitMs ?? RESTORE_MAX_WAIT_MS);
    void nextTick(() => {
      if (pending.value) frame = requestAnimationFrame(tryAlign);
    });
  }

  onMounted(() => {
    if (!pending.value) {
      // 자리는 있었지만 모양이 틀렸다(손으로 고친 주소 등) — scrollToTop 이 Nuxt 의 스크롤을 껐으니 맨 위에서 시작한다
      if (given !== null) {
        window.scrollTo({ top: 0, left: 0, behavior: "instant" });
        dropSpot();
      }
      return;
    }
    // Nuxt 가 맞추지 않으므로(scrollToTop) 내용을 기다리는 동안은 맨 위에 둔다
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    listen();
    watch(
      ready,
      (ok) => {
        if (ok) schedule();
      },
      { immediate: true },
    );
  });

  // 화면을 떠난 뒤 늦게 도는 프레임·타이머가 새 화면의 주소·스크롤을 건드리지 않게
  onBeforeUnmount(() => {
    disposed = true;
    pending.value = false;
    cancelFrames();
    unlisten();
  });

  return { pending, anchor };
}

/**
 * 상세로 떠날 때 이 화면 주소에도 자리(at·y)를 실어 둔다 — 상세의 [돌아가기]가 router.back() 을 고르거나
 * 브라우저 뒤로 가기로 돌아와도 그 기록의 주소에 맞출 자리가 남아 있다
 */
export function useDetailLeave(): { leave: (url: string, spot: ReturnSpot) => Promise<void> } {
  const route = useRoute();
  const router = useRouter();

  async function leave(url: string, spot: ReturnSpot): Promise<void> {
    await router.replace({ query: withSpot(route.query, spot) });
    await navigateTo(url);
  }

  return { leave };
}

// 새 창으로 여는 제외 논문 링크 — 이 화면은 그대로 두고, 누르는 순간의 항목 높이만 새 창 주소에 싣는다.
// 오른쪽 버튼(auxclick)·메뉴(contextmenu)에서도 실어 두면 메뉴의 "새 탭에서 열기"도 같은 자리를 받는다 — 메뉴가
// auxclick 보다 먼저 뜨는 브라우저가 있다
export function stampExcludedLink(e: MouseEvent, job: string, cnts: string): void {
  const link = e.currentTarget as HTMLAnchorElement;
  link.href = excludedDetailUrl(job, cnts, spotOf(link, excludedAnchor(cnts)).y);
}
