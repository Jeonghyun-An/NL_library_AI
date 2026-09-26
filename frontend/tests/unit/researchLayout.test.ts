// frontend/tests/unit/researchLayout.test.ts
import { describe, expect, it } from "vitest";
import { DEFAULT_LAYOUT, LAYOUT_KEY, effectiveLayout, readLayoutPref, writeLayoutPref } from "~/utils/researchLayout";

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(initial));
  return {
    get length() { return data.size; },
    clear: () => data.clear(),
    getItem: (k: string) => data.get(k) ?? null,
    key: (i: number) => [...data.keys()][i] ?? null,
    removeItem: (k: string) => { data.delete(k); },
    setItem: (k: string, v: string) => { data.set(k, v); },
  };
}

const blocked = {
  getItem: () => { throw new Error("SecurityError"); },
  setItem: () => { throw new Error("QuotaExceededError"); },
} as unknown as Storage;

describe("effectiveLayout", () => {
  it("넓은 화면은 고른 보기, 고른 적 없으면 기본 보기다", () => {
    expect(effectiveLayout(null, true)).toBe(DEFAULT_LAYOUT);
    expect(effectiveLayout("B", true)).toBe("B");
  });

  it("좁은 화면은 고른 보기와 무관하게 B 다", () => {
    expect(effectiveLayout("A", false)).toBe("B");
  });
});

describe("보기 선택 기억", () => {
  it("저장한 보기를 다시 읽는다", () => {
    const storage = memoryStorage();
    writeLayoutPref(storage, "B");
    expect(storage.getItem(LAYOUT_KEY)).toBe("B");
    expect(readLayoutPref(storage)).toBe("B");
  });

  it("모르는 값·없는 저장소·막힌 저장소는 기억 없음으로 본다", () => {
    expect(readLayoutPref(memoryStorage({ [LAYOUT_KEY]: "C" }))).toBeNull();
    expect(readLayoutPref(null)).toBeNull();
    expect(readLayoutPref(blocked)).toBeNull();
    writeLayoutPref(blocked, "A");
  });
});
