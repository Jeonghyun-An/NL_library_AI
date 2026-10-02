// frontend/utils/browserId.ts
export const BROWSER_ID_KEY = "sid";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function isUuidV4(s: unknown): s is string {
  return typeof s === "string" && UUID_V4.test(s);
}

export function generateUuidV4(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  // randomUUID 는 https·localhost 에서만 있다 — 운영 게이트웨이(http)에서는 getRandomValues 로 만든다
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  const bytes = new Uint8Array(16);
  if (c && typeof c.getRandomValues === "function") {
    c.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function readOrCreateBrowserId(storage: Storage | null, gen: () => string): string {
  let stored: string | null = null;
  try {
    stored = storage ? storage.getItem(BROWSER_ID_KEY) : null;
  } catch {
    stored = null;
  }
  if (isUuidV4(stored)) return stored;
  const fresh = gen().toLowerCase();
  try {
    storage?.setItem(BROWSER_ID_KEY, fresh);
  } catch {
    // 막힌 저장소 — 이 페이지 수명 동안만 메모리 값으로 쓴다
  }
  return fresh;
}

export function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

// 탭 하나에서만 쓰는 캐시용(논문 상세의 AI 글) — 서버 렌더·막힌 저장소에서는 null
export function safeSessionStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}
