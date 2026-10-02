// frontend/tests/unit/aiCache.test.ts
import { describe, expect, it } from "vitest";
import { readAiCache, relatedCacheKey, summaryCacheKey, writeAiCache } from "~/utils/aiCache";
import { MemoryStorage } from "./helpers/memoryStorage";

describe("캐시 키", () => {
  it("AI 요약은 논문과 기준 질문으로, 연관 이유는 두 논문으로 가른다", () => {
    expect(summaryCacheKey("CNTS-1", "딥러닝")).not.toBe(summaryCacheKey("CNTS-1", "자연어"));
    expect(summaryCacheKey("CNTS-1", "딥러닝")).not.toBe(summaryCacheKey("CNTS-2", "딥러닝"));
    expect(relatedCacheKey("CNTS-1", "CNTS-2")).not.toBe(relatedCacheKey("CNTS-2", "CNTS-1"));
    expect(summaryCacheKey("CNTS-1", "CNTS-2")).not.toBe(relatedCacheKey("CNTS-1", "CNTS-2"));
  });
});

describe("readAiCache·writeAiCache", () => {
  it("쓴 글을 같은 키로 다시 읽는다", () => {
    const s = new MemoryStorage();
    const key = summaryCacheKey("CNTS-1", "딥러닝");
    writeAiCache(s, key, "핵심 요약");
    expect(readAiCache(s, key)).toBe("핵심 요약");
    expect(readAiCache(s, summaryCacheKey("CNTS-1", "자연어"))).toBeNull();
  });

  it("빈 글과 서버가 보낸 생성 실패 문구는 담지 않는다", () => {
    const s = new MemoryStorage();
    writeAiCache(s, "k1", "  ");
    writeAiCache(s, "k2", "앞부분 요약 분석 생성 중 오류가 발생했습니다.");
    expect(s.length).toBe(0);
  });

  it("용량 초과·막힌 저장소·저장소 없음은 조용히 넘긴다", () => {
    const small = new MemoryStorage(10);
    expect(() => writeAiCache(small, "key", "아주 긴 요약 글입니다")).not.toThrow();
    expect(readAiCache(small, "key")).toBeNull();
    const blocked = new MemoryStorage();
    blocked.failWith = new Error("SecurityError");
    expect(() => writeAiCache(blocked, "key", "요약")).not.toThrow();
    expect(() => writeAiCache(null, "key", "요약")).not.toThrow();
    expect(readAiCache(null, "key")).toBeNull();
  });

  it("읽기가 막혀도 null 이다", () => {
    const broken = {
      getItem: () => {
        throw new Error("SecurityError");
      },
    } as unknown as Storage;
    expect(readAiCache(broken, "key")).toBeNull();
  });
});
