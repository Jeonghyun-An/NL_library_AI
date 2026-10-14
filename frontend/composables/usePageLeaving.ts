// frontend/composables/usePageLeaving.ts
import { onBeforeUnmount, ref, type Ref } from "vue";

/**
 * 이 화면을 떠나는 이동이 시작됐는가 — 결과 화면이 검색·복원 뒤 늦게 주소(?q=&h=)를 바꿀 때 본다.
 * 결과는 기록 저장(await) 전에 먼저 그려지므로 그 사이 카드를 누를 수 있다. 저장이 끝나 router.replace 가 돌면 vue-router 는
 * 새 이동이 이기게 해 진행 중이던 상세 이동이 취소되고 결과 화면에 남는다(2026-10-14 운영 확인 — 첫 클릭이 상세로 가지 않음).
 * 떠나는 중이면 주소를 건드리지 않는다. 떠남은 경로가 바뀌는 이동이 시작될 때(onBeforeRouteLeave) 켜지고, 누르는 순간 직접
 * 켤 수도 있다(markLeaving — 가드가 돌기 전의 틈까지 막는다). 그 이동이 실패·취소되면 다시 끈다
 */
export function usePageLeaving(): { leaving: Ref<boolean>; markLeaving: () => void } {
  const router = useRouter();
  const leaving = ref(false);
  onBeforeRouteLeave(() => {
    leaving.value = true;
  });
  // 떠나는 이동(경로가 바뀌는)이 실패·취소됐을 때만 끈다 — 떠나기 직전 같은 화면 주소에 자리(at·y)를 싣는 replace 가
  // 같은 주소라 '중복'으로 실패해도 떠남은 그대로다
  const off = router.afterEach((to, from, failure) => {
    if (failure && to.path !== from.path) leaving.value = false;
  });
  onBeforeUnmount(off);
  return {
    leaving,
    markLeaving: () => {
      leaving.value = true;
    },
  };
}
