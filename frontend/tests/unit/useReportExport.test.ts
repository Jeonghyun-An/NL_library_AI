// frontend/tests/unit/useReportExport.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PRINT_END_FALLBACK_MS, PRINT_START_GRACE_MS, useReportExport } from "~/composables/useReportExport";
import type { ReportDoc } from "~/utils/reportDocument";

const doc: ReportDoc = { fileName: "DeepResearch_질문_20260928.docx", blocks: [], references: [] };

// Node 에는 인쇄 창이 없다 — print() 와 beforeprint·afterprint 를 흉내 낸다. fire(name) 이 그 이벤트를 쏜다
function stubPage(print: (fire: (name: string) => void) => void): (name: string) => void {
  const listeners = new Map<string, Set<() => void>>();
  const fire = (name: string) => {
    for (const fn of [...(listeners.get(name) ?? [])]) fn();
  };
  vi.stubGlobal("document", { title: "DeepResearch" });
  vi.stubGlobal("window", {
    print: () => print(fire),
    addEventListener: (name: string, fn: () => void) => {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name)!.add(fn);
    },
    removeEventListener: (name: string, fn: () => void) => listeners.get(name)?.delete(fn),
  });
  return fire;
}

// 약속이 풀렸는지 — 시계를 돌리는 사이 확인한다
function tracked<T>(p: Promise<T>): { done: () => boolean; p: Promise<T> } {
  let settled = false;
  const q = p.finally(() => {
    settled = true;
  });
  return { done: () => settled, p: q };
}

async function flush(): Promise<void> {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("printPdf", () => {
  it("print() 가 막혀 있다 돌아오는 브라우저 — 그 안의 afterprint 로 바로 되돌린다", async () => {
    const { exporting, printDoc, printPdf } = useReportExport();
    let during: unknown = null;
    stubPage((fire) => {
      fire("beforeprint");
      during = { title: document.title, printDoc: printDoc.value, exporting: exporting.value };
      fire("afterprint");
    });
    // 인쇄가 시작됐다 — 부르는 쪽이 완료 처리를 한다
    expect(await printPdf(doc)).toBe(true);
    expect(during).toEqual({ title: "DeepResearch_질문_20260928", printDoc: doc, exporting: true });
    expect(document.title).toBe("DeepResearch");
    expect(printDoc.value).toBeNull();
    expect(exporting.value).toBe(false);
  });

  it("print() 가 곧바로 돌아오는 브라우저 — 인쇄가 끝났다는 afterprint 까지 인쇄 문서를 붙여 둔다(앱 화면이 찍히지 않게)", async () => {
    const { exporting, printDoc, printPdf } = useReportExport();
    const fire = stubPage((f) => f("beforeprint"));
    const run = tracked(printPdf(doc));
    await flush();
    vi.advanceTimersByTime(PRINT_START_GRACE_MS + 30_000);
    await flush();
    // 인쇄 창이 열려 있는 동안 — 인쇄 문서·파일 이름 제목이 남아 있다
    expect(printDoc.value).toBe(doc);
    expect(document.title).toBe("DeepResearch_질문_20260928");
    expect(exporting.value).toBe(true);
    expect(run.done()).toBe(false);

    fire("afterprint");
    expect(await run.p).toBe(true);
    expect(printDoc.value).toBeNull();
    expect(document.title).toBe("DeepResearch");
    expect(exporting.value).toBe(false);
  });

  it("beforeprint 없이 afterprint 만 주는 브라우저도 인쇄한 것으로 본다", async () => {
    const { printPdf } = useReportExport();
    stubPage((f) => f("afterprint"));
    expect(await printPdf(doc)).toBe(true);
  });

  it("인쇄가 시작되지 않으면(beforeprint 없음 — 정책 차단·인앱 브라우저) 잠깐 뒤 되돌려 버튼이 멈추지 않는다", async () => {
    const { exporting, printDoc, printPdf } = useReportExport();
    stubPage(() => {});
    const run = tracked(printPdf(doc));
    await flush();
    expect(exporting.value).toBe(true);
    vi.advanceTimersByTime(PRINT_START_GRACE_MS);
    // 인쇄 창이 열리지 않았다 — 부르는 쪽이 실패 안내를 보이고 완료 처리를 하지 않게 false
    expect(await run.p).toBe(false);
    expect(printDoc.value).toBeNull();
    expect(document.title).toBe("DeepResearch");
    expect(exporting.value).toBe(false);
  });

  it("시작했는데 afterprint 가 끝내 오지 않으면 대체 시간 뒤 되돌린다", async () => {
    const { exporting, printPdf } = useReportExport();
    stubPage((f) => f("beforeprint"));
    const run = tracked(printPdf(doc));
    await flush();
    vi.advanceTimersByTime(PRINT_START_GRACE_MS + PRINT_END_FALLBACK_MS - 1);
    await flush();
    expect(run.done()).toBe(false);
    vi.advanceTimersByTime(1);
    expect(await run.p).toBe(true);
    expect(exporting.value).toBe(false);
  });

  it("print() 가 던져도 원래대로 되돌리고 오류를 넘긴다", async () => {
    const { exporting, printDoc, printPdf } = useReportExport();
    stubPage(() => {
      throw new Error("인쇄 막힘");
    });
    await expect(printPdf(doc)).rejects.toThrow("인쇄 막힘");
    expect(document.title).toBe("DeepResearch");
    expect(printDoc.value).toBeNull();
    expect(exporting.value).toBe(false);
  });

  it("인쇄 중에 다시 누르면 아무 일 없이 돌아온다", async () => {
    const { printPdf } = useReportExport();
    const print = vi.fn((f: (name: string) => void) => f("beforeprint"));
    const fire = stubPage(print);
    const first = tracked(printPdf(doc));
    await flush();
    // 이 누름은 인쇄를 시작하지 않았다 — 부르는 쪽은 exporting 으로 먼저 막는다
    expect(await printPdf(doc)).toBe(false);
    expect(print).toHaveBeenCalledTimes(1);
    fire("afterprint");
    await first.p;
  });
});

describe("인쇄가 시작되지 않았을 때 화면(소스)", () => {
  const read = (rel: string): string => readFileSync(fileURLToPath(new URL(`../../${rel}`, import.meta.url)), "utf8");

  it("딥리서치 보고서는 실패 안내 토스트, 작업대 보고서는 실패 줄 — 완료 처리(markDone)는 하지 않는다", () => {
    const page = read("pages/research/[id].vue");
    expect(page).toMatch(/\} else if \(!\(await printPdf\(doc\)\)\) \{[\s\S]*?showToast\(REPORT_EXPORT_FAILED\.pdf\);/);
    const step = read("components/work/ProposalStep.vue");
    expect(step).toMatch(/else printed = await printPdf\(doc\);/);
    expect(step).toMatch(/if \(!printed\) \{\s*say\(REPORT_EXPORT_FAILED\.pdf, true\);\s*return;\s*\}[\s\S]*?await markDone\(\);/);
  });
});
