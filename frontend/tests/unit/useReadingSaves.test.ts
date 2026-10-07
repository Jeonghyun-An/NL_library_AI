// frontend/tests/unit/useReadingSaves.test.ts
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useReadingSaves } from "~/composables/useReadingSaves";
import type { ReadingPut, WorkResource } from "~/types/work";

interface Deferred {
  resolve: () => void;
  reject: (err: unknown) => void;
}

function httpError(status: number): Error & { status: number } {
  return Object.assign(new Error(`HTTP ${status}`), { status });
}

// PUT·다시 읽기를 하나씩 손으로 끝낸다 — 기록(log)으로 보낸 차례를 본다
function setup() {
  const log: string[] = [];
  const puts: Deferred[] = [];
  const reloads: Deferred[] = [];
  const error = ref<string | null>(null);
  const afterAction = vi.fn();
  const saves = useReadingSaves({
    put: (cnts: string, body: ReadingPut) => {
      log.push(`PUT ${cnts} ${JSON.stringify(body)}`);
      return new Promise<void>((resolve, reject) => puts.push({ resolve, reject }));
    },
    reload: (kinds: WorkResource[]) => {
      log.push(`GET ${kinds.join(",")}`);
      return new Promise<void>((resolve) => reloads.push({ resolve, reject: () => {} }));
    },
    afterAction,
    error,
  });
  return { saves, log, puts, reloads, error, afterAction };
}

// 사슬의 다음 단계가 돌 만큼 마이크로태스크를 비운다
async function flush(): Promise<void> {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
}

describe("useReadingSaves — 저장은 차례로, 다시 읽기는 사슬이 빌 때 한 번", () => {
  it("처음 옮김의 PUT 묶음은 PUT 만 차례로 보내고 끝에 GET reading 한 번·afterAction 한 번", async () => {
    const { saves, log, puts, reloads, afterAction } = setup();
    for (const [cnts, position] of [["A", 0], ["B", 10], ["C", 20]] as const) saves.enqueue(cnts, { position });
    expect(saves.pending.value).toBe(3);
    expect(saves.reordering.value).toBe(true);

    await flush();
    puts[0]!.resolve();
    await flush();
    puts[1]!.resolve();
    await flush();
    expect(log).toEqual(['PUT A {"position":0}', 'PUT B {"position":10}', 'PUT C {"position":20}']);
    puts[2]!.resolve();
    await flush();
    expect(log.at(-1)).toBe("GET reading");
    // 다시 읽기가 끝날 때까지 순서 저장이 남은 것으로 본다 — 표는 아직 옛 목록이라 [위로]·[아래로] 를 꺼 둔다
    expect(saves.reordering.value).toBe(true);
    expect(afterAction).not.toHaveBeenCalled();

    reloads[0]!.resolve();
    await saves.idle();
    expect(log.filter((l) => l.startsWith("GET"))).toHaveLength(1);
    expect(afterAction).toHaveBeenCalledTimes(1);
    expect(saves.pending.value).toBe(0);
    expect(saves.reordering.value).toBe(false);
  });

  it("묶음이 도는 동안 넣은 저장은 그 묶음 뒤에 붙고, 담음 상태를 바꾼 저장이 있으면 work 도 다시 읽는다", async () => {
    const { saves, log, puts, reloads } = setup();
    saves.enqueue("A", { note: "메모" });
    await flush();
    saves.enqueue("B", { state: "in" });
    expect(saves.reordering.value).toBe(false);
    puts[0]!.resolve();
    await flush();
    puts[1]!.resolve();
    await flush();
    expect(log).toEqual(['PUT A {"note":"메모"}', 'PUT B {"state":"in"}', "GET reading,work"]);
    reloads[0]!.resolve();
    await saves.idle();
  });

  it("다시 읽기를 기다리는 동안 들어온 저장은 그 뒤에 보내고 끝나면 다시 한 번 읽는다", async () => {
    const { saves, log, puts, reloads, afterAction } = setup();
    saves.enqueue("A", { position: 0 });
    await flush();
    puts[0]!.resolve();
    await flush();
    saves.enqueue("B", { note: "뒤" });
    reloads[0]!.resolve();
    await flush();
    expect(afterAction).toHaveBeenCalledTimes(1);
    expect(saves.reordering.value).toBe(true);
    puts[1]!.resolve();
    await flush();
    reloads[1]!.resolve();
    await saves.idle();
    expect(log).toEqual(['PUT A {"position":0}', "GET reading", 'PUT B {"note":"뒤"}', "GET reading"]);
    expect(afterAction).toHaveBeenCalledTimes(2);
    expect(saves.reordering.value).toBe(false);
  });

  it("묶음 중간의 실패 문구는 다음 저장이 지우지 않고, 409 면 work 도 다시 읽는다 — 새 묶음이 시작될 때 비운다", async () => {
    const { saves, log, puts, reloads, error, afterAction } = setup();
    error.value = "옛 오류";
    saves.enqueue("A", { state: "in" });
    expect(error.value).toBeNull();
    saves.enqueue("B", { note: "메모" });
    await flush();
    puts[0]!.reject(httpError(409));
    await flush();
    expect(error.value).not.toBeNull();
    const message = error.value;
    puts[1]!.resolve();
    await flush();
    expect(error.value).toBe(message);
    expect(log.at(-1)).toBe("GET reading,work");
    reloads[0]!.resolve();
    await saves.idle();
    expect(afterAction).toHaveBeenCalledTimes(1);

    saves.enqueue("C", { note: null });
    expect(error.value).toBeNull();
    await flush();
    puts[2]!.reject(httpError(500));
    await flush();
    // 성공한 저장이 없는 묶음 — 다시 읽기만 하고 afterAction 은 부르지 않는다. 409 가 아니면 reading 만
    expect(log.at(-1)).toBe("GET reading");
    reloads[1]!.resolve();
    await saves.idle();
    expect(afterAction).toHaveBeenCalledTimes(1);
    expect(error.value).not.toBeNull();
  });
});
