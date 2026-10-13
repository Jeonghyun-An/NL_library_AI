// frontend/tests/unit/researchMode.test.ts
import { describe, expect, it } from "vitest";
import {
  DEFAULT_RESEARCH_MODE,
  RESEARCH_MODES,
  RESEARCH_MODE_KEY,
  modeOfParams,
  modeParams,
  modeStep,
  readResearchMode,
  researchModeLabel,
  researchModeLine,
  restartParams,
  saveResearchMode,
} from "~/utils/researchMode";
import { MemoryStorage } from "./helpers/memoryStorage";

// 06c 배포 뒤 서버가 만든 잡의 params 모양 — 서버가 기본값을 채워 저장한다(app/api/research.py create_research)
const SERVER_DEFAULTS = { max_subquestions: 6, max_recheck: 3, exclude_off_topic: 1, critic_scope: 0 };

describe("modeParams · 선택지", () => {
  it("폭넓게는 두 칸 모두 0, 정밀하게는 두 칸 모두 1 — 늘 두 칸을 함께 싣는다", () => {
    expect(modeParams("broad")).toEqual({ broaden: 0, query_context: 0 });
    expect(modeParams("precise")).toEqual({ broaden: 1, query_context: 1 });
  });

  it("기본 선택은 정밀하게, 선택지는 폭넓게 · 정밀하게 순서", () => {
    expect(DEFAULT_RESEARCH_MODE).toBe("precise");
    expect(RESEARCH_MODES.map((m) => m.id)).toEqual(["broad", "precise"]);
    expect(RESEARCH_MODES.map((m) => researchModeLabel(m.id))).toEqual(["폭넓게", "정밀하게"]);
  });
});

describe("modeOfParams · researchModeLine", () => {
  it("두 칸이 모두 1 이면 정밀하게, 모두 0 이면 폭넓게(06c 배포 뒤·06d 전 잡)", () => {
    expect(modeOfParams({ ...SERVER_DEFAULTS, broaden: 1, query_context: 1 })).toBe("precise");
    expect(modeOfParams({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 })).toBe("broad");
    expect(researchModeLine({ ...SERVER_DEFAULTS, broaden: 1, query_context: 1 })).toBe("탐색 방식 · 정밀하게");
    expect(researchModeLine({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 })).toBe("탐색 방식 · 폭넓게");
  });

  it("두 칸이 모두 없으면(06c 전 잡·params 없음) null — 머리에 그리지 않는다", () => {
    expect(modeOfParams({})).toBeNull();
    expect(modeOfParams(SERVER_DEFAULTS)).toBeNull();
    expect(modeOfParams(null)).toBeNull();
    expect(modeOfParams(undefined)).toBeNull();
    expect(researchModeLine({})).toBeNull();
  });

  it("두 칸이 갈리면 어느 방식도 아니라 null, 한 칸만 있으면 없는 칸을 서버 기본값 0 으로 읽는다", () => {
    expect(modeOfParams({ broaden: 1, query_context: 0 })).toBeNull();
    expect(modeOfParams({ broaden: 0, query_context: 1 })).toBeNull();
    expect(modeOfParams({ broaden: 0 })).toBe("broad");
    expect(modeOfParams({ broaden: 1 })).toBeNull();
  });
});

describe("restartParams", () => {
  it("같은 질문으로 다시 시작할 때 원래 잡의 두 칸을 그대로 이어 쓴다(다른 칸은 싣지 않는다)", () => {
    expect(restartParams({ ...SERVER_DEFAULTS, broaden: 1, query_context: 1 })).toEqual({ broaden: 1, query_context: 1 });
    expect(restartParams({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 })).toEqual({ broaden: 0, query_context: 0 });
    expect(restartParams({ broaden: 1, query_context: 0 })).toEqual({ broaden: 1, query_context: 0 });
  });

  it("두 칸이 모두 없는 잡(06c 전 잡)은 기본 탐색 방식", () => {
    expect(restartParams(SERVER_DEFAULTS)).toEqual(modeParams(DEFAULT_RESEARCH_MODE));
    expect(restartParams({})).toEqual({ broaden: 1, query_context: 1 });
  });

  it("받은 params 를 고치지 않는다", () => {
    const params = { ...SERVER_DEFAULTS, broaden: 0, query_context: 0 };
    restartParams(params);
    modeOfParams(params);
    expect(params).toEqual({ ...SERVER_DEFAULTS, broaden: 0, query_context: 0 });
  });
});

describe("modeStep", () => {
  it("방향키로 옆 칸을 고르고 끝에서 돈다(radiogroup 관례), Home·End 는 처음·끝", () => {
    expect(modeStep("broad", "ArrowRight")).toBe("precise");
    expect(modeStep("broad", "ArrowDown")).toBe("precise");
    expect(modeStep("precise", "ArrowRight")).toBe("broad");
    expect(modeStep("precise", "ArrowLeft")).toBe("broad");
    expect(modeStep("broad", "ArrowUp")).toBe("precise");
    expect(modeStep("precise", "Home")).toBe("broad");
    expect(modeStep("broad", "End")).toBe("precise");
  });

  it("움직일 키가 아니면 null — 부품은 그 키를 막지 않는다(Tab·Space·Enter)", () => {
    expect(modeStep("broad", "Tab")).toBeNull();
    expect(modeStep("broad", " ")).toBeNull();
    expect(modeStep("broad", "Enter")).toBeNull();
  });
});

describe("readResearchMode · saveResearchMode", () => {
  it("고른 방식을 기억하고 다시 읽는다", () => {
    const storage = new MemoryStorage();
    saveResearchMode(storage, "broad");
    expect(storage.getItem(RESEARCH_MODE_KEY)).toBe("broad");
    expect(readResearchMode(storage)).toBe("broad");
  });

  it("저장소가 없거나 비었거나 모르는 값이면 기본 정밀하게", () => {
    expect(readResearchMode(null)).toBe("precise");
    expect(readResearchMode(new MemoryStorage())).toBe("precise");
    const storage = new MemoryStorage();
    storage.setItem(RESEARCH_MODE_KEY, "deep");
    expect(readResearchMode(storage)).toBe("precise");
  });

  it("막힌 저장소(읽기·쓰기가 던짐)에서도 던지지 않는다", () => {
    const blocked = {
      getItem: () => {
        throw new DOMException("막힘", "SecurityError");
      },
    } as unknown as Storage;
    expect(readResearchMode(blocked)).toBe("precise");
    const full = new MemoryStorage();
    full.failWith = new DOMException("쿼터 초과", "QuotaExceededError");
    expect(() => saveResearchMode(full, "broad")).not.toThrow();
    expect(() => saveResearchMode(null, "broad")).not.toThrow();
  });
});
