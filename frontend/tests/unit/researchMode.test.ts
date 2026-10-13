// frontend/tests/unit/researchMode.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parse } from "vue/compiler-sfc";
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
import { cssRules } from "./helpers/cssRules";
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

// ── 배치(research.css·부품 템플릿) — 컴포넌트를 띄우지 않는 단위 테스트 환경(DOM 없음)이라 규칙과 템플릿 모양을 본다.
// 실제 폭에서의 움직임은 헤드리스 Chrome 으로 쟀다(P6 품질 리뷰 반영 커밋 메시지)
const researchCss = readFileSync(fileURLToPath(new URL("../../assets/css/research.css", import.meta.url)), "utf8");
const rules = cssRules(researchCss);
const rule = (selector: string, at = "") => rules.find((r) => r.at === at && r.selectors.includes(selector));

interface TplNode {
  type: number;
  tag?: string;
  props?: { type: number; name: string; value?: { content: string }; arg?: { content?: string }; exp?: { content?: string } }[];
  children?: TplNode[];
}
const ELEMENT = 1;
const classOf = (n: TplNode) => n.props?.find((p) => p.type === 6 && p.name === "class")?.value?.content ?? "";
const hasClass = (n: TplNode, cls: string) => classOf(n).split(/\s+/).includes(cls);
const directive = (n: TplNode, name: string, arg?: string) =>
  n.props?.find((p) => p.type === 7 && p.name === name && (arg === undefined || p.arg?.content === arg))?.exp?.content;
function descendants(n: TplNode, out: TplNode[] = []): TplNode[] {
  for (const c of n.children ?? []) {
    if (c.type === ELEMENT) out.push(c);
    descendants(c, out);
  }
  return out;
}

describe("탐색 방식 배치 — 랜딩 입력 상자(설명 길이가 줄 자리·상자 높이를 정하지 않는다)", () => {
  const source = readFileSync(fileURLToPath(new URL("../../components/research/ResearchModePicker.vue", import.meta.url)), "utf8");
  const tpl = parse(source).descriptor.template?.ast as unknown as TplNode;
  const roots = (tpl.children ?? []).filter((n) => n.type === ELEMENT);
  const mode = roots.find((n) => hasClass(n, "rs-mode"));
  const hint = roots.find((n) => hasClass(n, "rs-mode__hint"));

  it("설명은 .rs-mode(라벨·두 칸) 밖 — + 메뉴 줄의 자식으로 늘 자기 줄에 선다. 묶음이 칩 줄에 서는지가 설명 길이로 바뀌지 않는다", () => {
    expect(mode).toBeDefined();
    expect(hint).toBeDefined();
    expect(descendants(mode!).some((n) => hasClass(n, "rs-mode__hint"))).toBe(false);
    expect(rule(".rs-mode__hint")?.decls.get("flex")).toBe("1 0 100%");
    // .rs-mode 는 라벨·두 칸만이라 크기가 고른 방식과 상관없다 — 설명 길이를 따르는 기준 크기(flex-basis)를 두지 않는다
    expect(rule(".rs-mode")?.decls.has("flex")).toBe(false);
  });

  it("두 방식의 설명을 같은 칸에 겹쳐 두고 고른 것만 보인다 — 칸을 바꿔도 설명 줄 높이(=상자 높이)가 그대로, 설명은 고른 것만 읽힌다", () => {
    expect(hint).toBeDefined();
    const texts = descendants(hint!).filter((n) => hasClass(n, "rs-mode__hint-text"));
    expect(texts).toHaveLength(1);
    expect(directive(texts[0]!, "for")).toMatch(/\bin RESEARCH_MODES$/);
    expect(directive(texts[0]!, "bind", "class")).toContain("is-shown");
    // radiogroup 의 설명(aria-describedby)은 보이는 설명 하나 — 숨긴 설명은 읽히지 않는다
    expect(directive(texts[0]!, "bind", "id")).toMatch(/hintId/);
    expect(directive(texts[0]!, "bind", "aria-hidden")).toBeDefined();
    expect(rule(".rs-mode__hint")?.decls.get("display")).toBe("grid");
    expect(rule(".rs-mode__hint-text")?.decls.get("grid-area")).toBe("1 / 1");
    expect(rule(".rs-mode__hint-text:not(.is-shown)")?.decls.get("visibility")).toBe("hidden");
  });

  it("설명 줄이 붙어 + 메뉴 줄이 높아지면 보내기는 칩 줄에 맞춘다(P4 의 끝나지 않은 연구 한 줄과 같이)", () => {
    expect(rule(".skx-search__box:has(> .rs-plus > .rs-mode) > .skx-search__actions")?.decls.get("align-self")).toBe("start");
  });
});

describe("탐색 방식 배치 — 결과 검색바(높이가 정해진 한 줄 알약 — 입력칸이 사라지지 않는다)", () => {
  const NARROW = "@container rs-bar (max-width: 34rem)";
  const WIDE = "@container rs-bar (width > 34rem)";

  it("+ 메뉴 줄은 꺾지 않고(바 밖으로 넘치지 않게) 탐색 방식은 줄거나 안에서 꺾이지 않는다", () => {
    expect(rule(".skx-rsearch > .rs-plus:has(> .rs-mode)")?.decls.get("flex-wrap")).toBe("nowrap");
    expect(rule(".skx-rsearch .rs-mode")?.decls.get("flex-wrap")).toBe("nowrap");
    expect(rule(".skx-rsearch .rs-mode")?.decls.get("flex-shrink")).toBe("0");
  });

  it("바 폭으로 정한다 — 바가 좁으면(34rem 이하 — LNB 가 열린 노트북·휴대폰) 탐색 방식을 바 아래 왼쪽으로 내리고, 넓으면 입력칸이 8rem 아래로 줄지 않는다", () => {
    expect(rule(".skx-rsearch:has(> .rs-plus > .rs-mode)")?.decls.get("container")).toBe("rs-bar / inline-size");
    const dropped = rule(".skx-rsearch .rs-mode", NARROW);
    expect(dropped?.decls.get("position")).toBe("absolute");
    expect(dropped?.decls.get("top")).toBe("calc(100% + 0.4rem)");
    expect(dropped?.decls.get("left")).toBe("0");
    // 바 아래로 내려 결과 틀 위에 겹치므로 + 메뉴 팝오버·끝나지 않은 연구 줄과 같은 면을 깐다
    expect(dropped?.decls.get("background")).toBe("var(--skx-frost-menu-bg)");
    expect(rule(".skx-rsearch > .skx-rsearch__input", WIDE)?.decls.get("min-width")).toBe("8rem");
  });

  it("내린 탐색 방식·오류 문구·끝나지 않은 연구 줄 셋의 자리가 겹치지 않는다 — 바 아래 첫 줄은 탐색 방식, 오류(왼쪽)·한 줄(오른쪽)은 그 아래", () => {
    // 바 아래 기본 자리(P4) — 오류는 왼쪽, 한 줄은 오른쪽
    expect(rule(".rs-plus__error")?.decls.get("top")).toBe("calc(100% + 0.4rem)");
    expect(rule(".skx-rsearch .rs-start-note")?.decls.get("top")).toBe("calc(100% + 0.4rem)");
    // 탐색 방식을 내린 바에서는 둘 다 그 줄(0.4rem + 높이 1.74rem + 테두리) 아래로
    for (const sel of [".skx-rsearch .rs-plus:has(> .rs-mode) > .rs-plus__error", ".skx-rsearch .rs-plus:has(> .rs-mode) > .rs-start-note"]) {
      expect(rule(sel, NARROW)?.decls.get("top")).toBe("calc(100% + 2.6rem)");
    }
  });
});
