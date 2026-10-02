// frontend/tests/unit/browserId.test.ts
import { webcrypto } from "node:crypto";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BROWSER_ID_KEY,
  generateUuidV4,
  isUuidV4,
  readOrCreateBrowserId,
  safeLocalStorage,
  safeSessionStorage,
} from "~/utils/browserId";
import { MemoryStorage } from "./helpers/memoryStorage";

const V4 = "3f2b8c1e-9d4a-4f6b-8a2c-1e5d7b9c0a12";

describe("isUuidV4", () => {
  it("소문자 표준형 v4 를 받는다", () => {
    expect(isUuidV4(V4)).toBe(true);
  });

  it("대문자·v1·v5·변형 비트가 틀린 값·형식 밖 값은 거절한다", () => {
    expect(isUuidV4(V4.toUpperCase())).toBe(false);
    expect(isUuidV4("3f2b8c1e-9d4a-1f6b-8a2c-1e5d7b9c0a12")).toBe(false);
    expect(isUuidV4("3f2b8c1e-9d4a-5f6b-8a2c-1e5d7b9c0a12")).toBe(false);
    expect(isUuidV4("3f2b8c1e-9d4a-4f6b-ca2c-1e5d7b9c0a12")).toBe(false);
    expect(isUuidV4("null")).toBe(false);
    expect(isUuidV4(null)).toBe(false);
    expect(isUuidV4(undefined)).toBe(false);
  });
});

describe("readOrCreateBrowserId", () => {
  it("저장된 값이 올바르면 그대로 쓴다", () => {
    const s = new MemoryStorage();
    s.setItem(BROWSER_ID_KEY, V4);
    const gen = vi.fn(() => "unused");
    expect(readOrCreateBrowserId(s, gen)).toBe(V4);
    expect(gen).not.toHaveBeenCalled();
  });

  it("형식이 틀리면 새로 만들어 저장한다", () => {
    const s = new MemoryStorage();
    s.setItem(BROWSER_ID_KEY, "null");
    const fresh = "0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d";
    expect(readOrCreateBrowserId(s, () => fresh)).toBe(fresh);
    expect(s.getItem(BROWSER_ID_KEY)).toBe(fresh);
  });

  it("생성기가 대문자를 주면 소문자로 저장한다", () => {
    const s = new MemoryStorage();
    expect(readOrCreateBrowserId(s, () => V4.toUpperCase())).toBe(V4);
    expect(s.getItem(BROWSER_ID_KEY)).toBe(V4);
  });

  it("저장소가 없으면 만든 값을 돌려준다", () => {
    expect(readOrCreateBrowserId(null, () => V4)).toBe(V4);
  });

  it("읽기·쓰기가 막혀도 던지지 않는다", () => {
    const blocked = {
      getItem: () => {
        throw new DOMException("막힘", "SecurityError");
      },
      setItem: () => {
        throw new DOMException("막힘", "SecurityError");
      },
    } as unknown as Storage;
    expect(readOrCreateBrowserId(blocked, () => V4)).toBe(V4);
  });
});

describe("generateUuidV4", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("randomUUID 가 있으면 v4 를 만든다", () => {
    expect(isUuidV4(generateUuidV4())).toBe(true);
  });

  it("randomUUID 가 없는 비보안 컨텍스트에서도 서로 다른 v4 를 만든다", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: (a: Uint8Array<ArrayBuffer>) => webcrypto.getRandomValues(a),
    });
    const ids = new Set(Array.from({ length: 50 }, () => generateUuidV4()));
    expect([...ids].every((id) => isUuidV4(id))).toBe(true);
    expect(ids.size).toBe(50);
  });

  it("crypto 가 아예 없어도 v4 를 만든다", () => {
    vi.stubGlobal("crypto", undefined);
    expect(isUuidV4(generateUuidV4())).toBe(true);
  });
});

describe("safeLocalStorage", () => {
  it("window 가 없는 서버 렌더에서는 null", () => {
    expect(safeLocalStorage()).toBeNull();
  });
});

describe("safeSessionStorage", () => {
  it("window 가 없는 서버 렌더에서는 null", () => {
    expect(safeSessionStorage()).toBeNull();
  });
});
