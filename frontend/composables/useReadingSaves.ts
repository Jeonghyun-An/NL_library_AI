// frontend/composables/useReadingSaves.ts
import { type Ref, readonly, ref } from "vue";
import type { ReadingPut, WorkResource } from "~/types/work";
import { httpStatus, workErrorMessage } from "~/utils/researchErrors";

export interface ReadingSavesDeps {
  put: (cnts: string, body: ReadingPut) => Promise<unknown>;
  // 거절하지 않는다(ReadingStep 은 Promise.allSettled 로 읽는다) — 조회 오류는 useResearchWork 의 error 가 맡는다
  reload: (kinds: WorkResource[]) => Promise<void>;
  afterAction: () => void;
  error: Ref<string | null>;
}

interface Batch {
  kinds: Set<WorkResource>;
  saved: boolean;
}

// 읽기 목록 행 저장(PUT .../reading/{cnts_id})의 차례 — ReadingStep 이 쓴다. 앞 저장이 도는 동안 누른 것도 버리지 않고 같은 행의
// 두 고침이 거꾸로 도착하지 않게 한 사슬로 차례로 보낸다. 다시 읽기는 저장마다 하지 않고 사슬이 빌 때 한 번만 한다(묶음) —
// 처음 [위로]·[아래로] 는 모든 행의 PUT 을 내므로(reorderPuts) 저장마다 GET reading 을 하면 i번째 행이 PUT+GET i번 뒤에야
// 움직이고 표가 '앞쪽만 번호를 받은' 중간 순서로 거듭 다시 정렬된다. 묶음이 다시 읽을 것은 그동안 모은다: reading 은 늘,
// 담음 상태(state)를 바꾼 저장이 성공했거나 409 가 났으면 work 도. 오류 문구는 묶음이 시작될 때만 비운다 — 묶음 중간의 실패가
// 다음 저장에 지워지지 않게. reordering 은 순서(position) 저장이 든 묶음이 다시 읽기까지 끝날 때까지 참이다 — 그동안 표는
// [위로]·[아래로] 를 꺼서 다음 클릭이 끝난 순서를 기준으로 계산되게 한다(중간 목록으로 계산하면 앞 옮김이 사라진다)
export function useReadingSaves(deps: ReadingSavesDeps) {
  const pending = ref(0);
  const reordering = ref(false);
  let chain: Promise<void> = Promise.resolve();
  let batch: Batch = newBatch();

  function newBatch(): Batch {
    return { kinds: new Set<WorkResource>(["reading"]), saved: false };
  }

  function enqueue(cnts: string, body: ReadingPut): void {
    if (pending.value === 0) {
      deps.error.value = null;
      batch = newBatch();
    }
    pending.value += 1;
    if (body.position !== undefined) reordering.value = true;
    const current = batch;
    chain = chain.then(() => save(cnts, body, current));
  }

  async function save(cnts: string, body: ReadingPut, current: Batch): Promise<void> {
    try {
      await deps.put(cnts, body);
      current.saved = true;
      if (body.state !== undefined) current.kinds.add("work");
    } catch (err) {
      deps.error.value = workErrorMessage(err, "읽기 목록을 고치지 못했습니다");
      if (httpStatus(err) === 409) current.kinds.add("work");
    }
    try {
      // 뒤에 기다리는 저장이 없으면 이 묶음의 마지막이다 — 다시 읽기를 기다리는 동안 들어온 저장은 이 묶음에 붙어 그 뒤에 다시 읽는다
      if (pending.value === 1) {
        await deps.reload([...current.kinds]);
        if (current.saved) deps.afterAction();
      }
    } finally {
      pending.value -= 1;
      if (pending.value === 0) reordering.value = false;
    }
  }

  // 지금까지 넣은 저장과 그 묶음의 다시 읽기가 끝나면 풀린다 — [목차 만들기] 는 앞서 보낸 담음 고침이 반영된 뒤에 부른다
  function idle(): Promise<void> {
    return chain;
  }

  return { pending: readonly(pending), reordering: readonly(reordering), enqueue, idle };
}
