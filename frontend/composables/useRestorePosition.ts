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
  RESTORE_MAX_WAIT_MS,
  RESTORE_RETRY_MS,
  hasSpot,
  restoreStep,
  scrollDelta,
  spotOf,
  targetTop,
  withSpot,
  withoutSpot,
} from "~/utils/restorePosition";

// 사용자가 먼저 움직이면 맞추지 않는다 — 읽기 시작한 화면을 끌고 가지 않게
const USER_MOVES = ["wheel", "touchstart", "keydown", "pointerdown"] as const;

/**
 * 상세에서 돌아온 화면(주소의 at·y)에서, 떠날 때 누른 요소를 같은 화면 높이에 즉시 맞춘다.
 * ready 는 그 요소가 든 내용(보고서·복원한 결과 목록)이 그려질 준비가 됐는지 — 화면이 정한다.
 * 쓰는 화면은 definePageMeta({ scrollToTop: (to) => !to.query.at }) 로 Nuxt 의 스크롤을 끈다
 */
export function useRestorePosition(
  ready: Ref<boolean> | ComputedRef<boolean>,
  opts: { maxWaitMs?: number } = {},
): { pending: Readonly<Ref<boolean>>; anchor: Anchor | null } {
  const route = useRoute();
  const router = useRouter();
  // 들어온 순간의 주소만 본다 — 이 화면을 떠나기 직전 주소에 at·y 를 다시 싣는데(useDetailLeave) 그때 맞추면 안 된다
  const spot = readReturnSpot(route.query);
  const selector = spot.at ? anchorSelector(spot.at) : null;
  const anchor = spot.at ? parseAnchor(spot.at) : null;
  const pending = ref(selector !== null);
  let deadline = 0;
  let scheduled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  function stop(): void {
    if (timer) clearTimeout(timer);
    timer = null;
    for (const type of USER_MOVES) window.removeEventListener(type, finish, true);
  }

  function finish(): void {
    if (!pending.value) return;
    pending.value = false;
    stop();
    // 맞춘 뒤에는 주소에서 뗀다 — 새로고침·링크 복사에 옛 자리가 따라가지 않게
    if (hasSpot(route.query)) void router.replace({ query: withoutSpot(route.query) });
  }

  // 접힌 목록 안의 사본(display:none)은 높이가 없다 — 화면에 보이는 첫 요소를 고른다
  function visibleTarget(): HTMLElement | null {
    return (
      Array.from(document.querySelectorAll<HTMLElement>(selector!)).find((el) => el.getClientRects().length > 0) ?? null
    );
  }

  function tryAlign(): void {
    timer = null;
    if (!pending.value) return;
    const el = visibleTarget();
    switch (restoreStep(el !== null, Date.now(), deadline)) {
      case "retry":
        timer = setTimeout(tryAlign, RESTORE_RETRY_MS);
        return;
      case "align":
        window.scrollBy({
          top: scrollDelta(el!.getBoundingClientRect().top, targetTop(spot.y, window.innerHeight)),
          behavior: "instant",
        });
        // 인용칩은 초점을 돌려 주면 칩의 초점 열림으로 팝오버가 다시 열린다
        if (anchor?.kind === "cite") el!.focus({ preventScroll: true });
        break;
      case "give-up":
        // 보고서가 다른 시도로 바뀌었거나 결과가 바뀌어 요소가 없다 — 오류 없이 맨 위에 둔다
        break;
    }
    finish();
  }

  // 내용이 DOM 에 붙은 뒤(nextTick) 배치가 끝난 다음 프레임에 잰다. 기한은 내용이 준비된 때부터 센다 —
  // 늦게 붙는 목록은 기다리되 느린 응답 시간은 기한에 넣지 않는다
  function schedule(): void {
    if (!pending.value || scheduled) return;
    scheduled = true;
    deadline = Date.now() + (opts.maxWaitMs ?? RESTORE_MAX_WAIT_MS);
    void nextTick(() => requestAnimationFrame(tryAlign));
  }

  onMounted(() => {
    if (!pending.value) return;
    // Nuxt 가 맞추지 않으므로(scrollToTop) 내용을 기다리는 동안은 맨 위에 둔다
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    for (const type of USER_MOVES) window.addEventListener(type, finish, { capture: true, passive: true });
    watch(
      ready,
      (ok) => {
        if (ok) schedule();
      },
      { immediate: true },
    );
  });

  onBeforeUnmount(stop);

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
// 오른쪽 버튼(auxclick)에서도 실어 두면 메뉴의 "새 탭에서 열기"도 같은 자리를 받는다
export function stampExcludedLink(e: MouseEvent, job: string, cnts: string): void {
  const link = e.currentTarget as HTMLAnchorElement;
  link.href = excludedDetailUrl(job, cnts, spotOf(link, excludedAnchor(cnts)).y);
}
