// frontend/composables/useNow.ts
import { getCurrentInstance, onBeforeUnmount, ref, watch, type ComputedRef, type Ref } from "vue";

// 화면 시계. 보고서를 쓰는 동안만 돌린다 — 늘 돌리면 시계를 읽는 화면 전체가 1초마다 다시 그려진다
export function useNow(active: Ref<boolean> | ComputedRef<boolean>, intervalMs = 1000): Ref<number> {
  const now = ref(Date.now());
  let timer: ReturnType<typeof setInterval> | null = null;

  function stop(): void {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function start(): void {
    // 서버 렌더에서 타이머를 걸면 요청이 끝나도 풀리지 않는다
    if (timer || !import.meta.client) return;
    now.value = Date.now();
    timer = setInterval(() => {
      now.value = Date.now();
    }, intervalMs);
  }

  watch(active, (on) => (on ? start() : stop()), { immediate: true });
  if (getCurrentInstance()) onBeforeUnmount(stop);
  return now;
}
