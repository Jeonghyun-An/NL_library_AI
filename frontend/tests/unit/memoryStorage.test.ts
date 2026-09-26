import { describe, expect, it } from "vitest";
import { MemoryStorage } from "./helpers/memoryStorage";

describe("MemoryStorage", () => {
  it("저장한 값을 돌려주고 지운다", () => {
    const s = new MemoryStorage();
    s.setItem("a", "1");
    s.setItem("b", "2");
    expect(s.getItem("a")).toBe("1");
    expect(s.length).toBe(2);
    expect(s.key(1)).toBe("b");
    s.removeItem("a");
    expect(s.getItem("a")).toBeNull();
  });

  it("용량을 넘기면 QuotaExceededError DOMException 을 던진다", () => {
    const s = new MemoryStorage(10);
    let caught: unknown;
    try {
      s.setItem("k", "x".repeat(20));
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(DOMException);
    expect((caught as DOMException).name).toBe("QuotaExceededError");
    expect(s.getItem("k")).toBeNull();
  });

  it("같은 키를 덮어쓸 때는 기존 값 크기를 빼고 계산한다", () => {
    const s = new MemoryStorage(12);
    s.setItem("k", "x".repeat(10));
    expect(() => s.setItem("k", "y".repeat(10))).not.toThrow();
    expect(s.getItem("k")).toBe("y".repeat(10));
  });

  it("failWith 가 있으면 그 오류를 던진다", () => {
    const s = new MemoryStorage();
    s.failWith = new DOMException("막힘", "SecurityError");
    expect(() => s.setItem("k", "v")).toThrow("막힘");
  });
});
