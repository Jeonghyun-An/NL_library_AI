// frontend/tests/unit/researchJobErrors.test.ts
// 딥리서치 화면(pages/research/[id].vue·composables/useResearch.ts)의 오류 처리 — 첫 로드·재동기화 실패, 보던 연구가 사라짐(404),
// 409 뒤 맞추기, 취소 뒤 종합 단계 기다리기의 끝, 연결 띠 상태. 컴포넌트를 띄우지 않는 Node 환경이라 composable 은 직접 부르고
// (EventSource 는 import.meta.client 가 없어 열리지 않는다), 화면·스타일의 계약은 소스 텍스트로 본다
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useResearchJob } from "~/composables/useResearch";
import type { ResearchJob, ResearchStepRow } from "~/types/research";
import { ERROR_HINTS } from "~/utils/apiErrors";
import { RESEARCH_STATE_TEXT } from "~/utils/researchErrors";
import { describedByWith } from "~/utils/researchStart";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("~/composables/useApi", () => ({ apiUrl: (path: string) => `/api${path}`, useApi: () => api }));
vi.mock("~/composables/useHistory", () => ({ useHistory: () => ({ refresh: vi.fn(), entries: { value: [] } }) }));

const ID = "11111111-1111-4111-8111-111111111111";
const SYNC_FAILED = "최신 상태를 불러오지 못했어요";

function job(over: Partial<ResearchJob> = {}): ResearchJob {
  return {
    job_id: ID,
    question: "AI 윤리 교육의 효과",
    status: "running",
    stage: "planned",
    plan: ["효과 측정", "교사 인식"],
    report: null,
    last_error: null,
    steps: [],
    params: { max_subquestions: 6 },
    ...over,
  };
}

const SYNTH_RUNNING: ResearchStepRow = {
  seq: 3, kind: "synthesize", subq_idx: null, title: "보고서 종합", status: "running", result: { sections_total: 2, sections: [] },
};

function httpError(status: number): Error & { status: number } {
  return Object.assign(new Error(`HTTP ${status}`), { status });
}

const networkError = (): Error => Object.assign(new Error("[GET] <no response> Failed to fetch"), {
  name: "FetchError",
  cause: new TypeError("Failed to fetch"),
});

// 요청마다 응답을 차례로 꺼낸다 — GET 은 'get', 동작은 주소 끝(approve·retry·cancel). Error 면 거절
function route(replies: Record<string, unknown[]>): void {
  api.mockImplementation((url: string, opts?: { method?: string }) => {
    const kind = opts?.method === "POST" ? url.slice(url.lastIndexOf("/") + 1) : "get";
    const next = replies[kind]?.shift();
    if (next === undefined) return Promise.reject(new Error(`예상하지 않은 요청 ${kind} ${url}`));
    if (next instanceof Error) return Promise.reject(next);
    return Promise.resolve(next);
  });
}

afterEach(() => {
  api.mockReset();
  vi.useRealTimers();
});

describe("useResearchJob — 첫 로드", () => {
  it("404·422 는 찾을 수 없는 연구, 그 밖의 실패는 상태 블록의 kind·이유(제목은 화면이 '연구를 불러오지 못했어요')", async () => {
    route({ get: [httpError(404)] });
    const notFound = useResearchJob(ID);
    await notFound.load();
    expect(notFound.notFound.value).toBe(true);
    expect(notFound.loadError.value).toBeNull();

    route({ get: [httpError(500)] });
    const server = useResearchJob(ID);
    await server.load();
    expect(server.loadError.value).toEqual({ kind: "server", message: "" });

    route({ get: [networkError()] });
    const offline = useResearchJob(ID);
    await offline.load();
    expect(offline.loadError.value).toEqual({ kind: "network", message: ERROR_HINTS.network });
    // [다시 불러오기] 가 성공하면 오류가 걷힌다
    route({ get: [job()] });
    await offline.load();
    expect(offline.loadError.value).toBeNull();
    expect(offline.view.value?.status).toBe("running");
  });
});

describe("useResearchJob — 재동기화", () => {
  it("보던 연구가 사라지면(재동기화 GET 404) 첫 로드처럼 '찾을 수 없는 연구'로 바꾸고 화면을 비운다", async () => {
    route({ get: [job(), httpError(404)] });
    const r = useResearchJob(ID);
    await r.load();
    expect(await r.refresh()).toBe(false);
    expect(r.notFound.value).toBe(true);
    expect(r.view.value).toBeNull();
    expect(r.actionError.value).toBe("");
    expect(r.syncFailed.value).toBe(false);
  });

  it("도는 잡의 재동기화 실패는 오류 줄이 아니라 연결 띠로 — 다시 연결하는 중, 거듭되면 연결하지 못함", async () => {
    route({ get: [job(), httpError(502), networkError(), httpError(503)] });
    const r = useResearchJob(ID);
    await r.load();
    expect(r.connState.value).toBe("connected");
    await r.refresh();
    expect(r.actionError.value).toBe("");
    expect(r.syncFailed.value).toBe(true);
    expect(r.connState.value).toBe("reconnecting");
    await r.refresh();
    expect(r.connState.value).toBe("reconnecting");
    await r.refresh();
    expect(r.connState.value).toBe("lost");
    // [다시 연결] — '다시 연결하는 중'으로 돌리고 GET 으로 맞춘다. 또 실패하면 바로 연결하지 못함
    route({ get: [httpError(502)] });
    r.reconnect();
    expect(r.connState.value).toBe("reconnecting");
    await vi.waitFor(() => expect(r.connState.value).toBe("lost"));
  });

  it("끝난 잡(최종 보고서 받기)의 재동기화 실패는 오류 줄에 — 연결 띠는 서지 않는다. 성공하면 그 줄이 걷힌다", async () => {
    route({ get: [job({ status: "completed", stage: "synthesized" }), httpError(500), job({ status: "completed", stage: "synthesized" })] });
    const r = useResearchJob(ID);
    await r.load();
    await r.refresh();
    expect(r.actionError.value).toBe(SYNC_FAILED);
    expect(r.connState.value).toBe("connected");
    await r.resync();
    expect(r.actionError.value).toBe("");
  });
});

describe("useResearchJob — 409 뒤 맞추기", () => {
  it("다시 읽어 맞췄으면 해요체 안내, 다시 읽기마저 실패하면 그 문구", async () => {
    route({ get: [job({ status: "awaiting_approval" }), job({ status: "running" })], approve: [httpError(409)] });
    const ok = useResearchJob(ID);
    await ok.load();
    await ok.approve();
    expect(ok.actionError.value).toBe(RESEARCH_STATE_TEXT.stateChanged);
    expect(ok.actionError.value).toBe("그 사이 상태가 바뀌어 최신 상태로 맞췄어요");

    route({ get: [job({ status: "awaiting_approval" }), httpError(500)], approve: [httpError(409)] });
    const failed = useResearchJob(ID);
    await failed.load();
    await failed.approve();
    expect(failed.actionError.value).toBe(SYNC_FAILED);
  });

  it("같은 브라우저의 다른 연구에 막힌 승인은 서버 문구 대신 화면의 해요체 문구와 그 연구 링크", async () => {
    const other = "22222222-2222-4222-8222-222222222222";
    const blocked = Object.assign(httpError(429), {
      data: { detail: { code: "browser_active", message: "진행 중인 DeepResearch가 있습니다 — 끝나거나 취소한 뒤 다시 시작하세요", job_id: other } },
    });
    route({ get: [job({ status: "awaiting_approval" })], approve: [blocked] });
    const r = useResearchJob(ID);
    await r.load();
    await r.approve();
    expect(r.actionError.value).toBe("진행 중인 DeepResearch가 있어요 — 끝나거나 취소한 뒤 다시 시작해 주세요");
    expect(r.activeJobId.value).toBe(other);
  });
});

describe("useResearchJob — 취소 뒤 종합 단계 닫힘 기다리기", () => {
  it("상한(6번, 약 1분 반)까지 닫히지 않으면 조용히 끝내지 않고 알리고, 다시 읽어 닫혔으면 걷힌다", async () => {
    vi.useFakeTimers();
    const pending = job({ status: "canceled", stage: "explored", steps: [SYNTH_RUNNING] });
    route({
      get: [job({ status: "running", stage: "explored", steps: [SYNTH_RUNNING] }), ...Array.from({ length: 7 }, () => pending)],
      cancel: [{ job_id: ID, status: "canceled" }],
    });
    const r = useResearchJob(ID);
    await r.load();
    await r.cancel();
    expect(r.closeWaitEnded.value).toBe(false);
    await vi.runAllTimersAsync();
    // 종료 직후 1번 + 기다리며 6번
    expect(api.mock.calls.filter(([, opts]) => !opts).length).toBe(1 + 7);
    expect(r.closeWaitEnded.value).toBe(true);

    const closed = job({ status: "canceled", stage: "explored", steps: [{ ...SYNTH_RUNNING, status: "failed" }] });
    route({ get: [closed] });
    await r.resync();
    expect(r.closeWaitEnded.value).toBe(false);
  });
});

describe("describedByWith — 입력창의 aria-describedby 에 글자 수 id 를 잇고 뗀다", () => {
  it("페이지가 단 다른 id 는 그대로 두고, 남는 것이 없으면 null", () => {
    expect(describedByWith(null, "c1", true)).toBe("c1");
    expect(describedByWith("hint", "c1", true)).toBe("hint c1");
    expect(describedByWith("hint c1", "c1", true)).toBe("hint c1");
    expect(describedByWith("hint c1", "c1", false)).toBe("hint");
    expect(describedByWith("c1", "c1", false)).toBeNull();
    expect(describedByWith("  ", "c1", false)).toBeNull();
  });
});

const read = (rel: string): string => readFileSync(fileURLToPath(new URL(`../../${rel}`, import.meta.url)), "utf8");

describe("딥리서치 화면 — 공통 오류 컴포넌트로 옮긴 표시(소스)", () => {
  const page = read("pages/research/[id].vue");
  const tpl = page.slice(0, page.indexOf("<script"));

  it("없는 연구·첫 로드 실패는 상태 블록(notFound·kind) — 첫 로드 실패의 [다시 불러오기]는 load", () => {
    expect(tpl).toMatch(/<SkxErrorState kind="notFound" title-tag="h1" :title="RESEARCH_NOT_FOUND"/);
    expect(tpl).toMatch(/<SkxErrorState\s+:kind="loadError\.kind"[\s\S]*?:message="loadError\.message"[\s\S]*?@retry="load"/);
  });

  it("멈춘·취소한 연구 카드는 진행 막대 자리(머리 바로 아래, 본문 2단 위) — 아래 멈춘 지점·근거 장부는 덮지 않는다", () => {
    const failed = tpl.indexOf("v-if=\"phase === 'failed'\"");
    const canceled = tpl.indexOf("v-else-if=\"phase === 'canceled'\"");
    const bar = tpl.indexOf("<ResearchProgressBar");
    const body = tpl.indexOf('class="rs-body"');
    expect(bar).toBeGreaterThan(-1);
    expect(failed).toBeGreaterThan(bar);
    expect(canceled).toBeGreaterThan(failed);
    expect(body).toBeGreaterThan(canceled);
    // 실패는 error, 취소는 canceled 갈래 — 버튼은 지금 동작 그대로(재시도 글은 멈춘 단계를 따른다, 계획이 없으면 다시 시작)
    expect(tpl).toMatch(/:message="failedMessage"[\s\S]*?:retry-label="retryLabel"[\s\S]*?:on-retry="canRetry \? retry : undefined"/);
    expect(tpl).toMatch(/<SkxErrorState compact kind="canceled" :title="RESEARCH_STATE_TEXT\.canceledTitle" :message="RESEARCH_STATE_TEXT\.canceledMessage">/);
    // 덮개·흐림 없음, 서버 last_error 원문을 그리지 않는다
    expect(tpl).not.toContain("view.lastError");
    expect(page).toContain("researchFailedMessage(view.value.stage, canRetry.value, view.value.lastError)");
  });

  it("연결 띠는 늘 그려 두고 상태만 — [다시 연결]은 reconnect", () => {
    expect(tpl).toContain('<SkxConnectionBanner :state="connState" @retry="reconnect" />');
    expect(tpl).not.toMatch(/<SkxConnectionBanner[^>]*v-if/);
  });

  it("동작 실패·최종 보고서를 받지 못한 안내·취소 뒤 정리 안내는 줄 안내(SkxInlineError) — 합쇼체 문구가 남지 않는다", () => {
    expect(tpl).toMatch(/<SkxInlineError :message="actionError \|\| pageError">/);
    expect(tpl).toContain(':message="RESEARCH_STATE_TEXT.reportFailedOverDraft"');
    expect(tpl).toContain(':message="RESEARCH_STATE_TEXT.closePending"');
    expect(tpl).toMatch(/<div v-if="closeWaitEnded" class="rs-report-note">/);
    expect(page).not.toMatch(/못했습니다|시도합니다|초안입니다|복사하세요/);
    // 내보내기 실패 문구는 작업대 영역이 useReportExport 의 REPORT_EXPORT_FAILED 한 곳으로 모았다 — 화면은 그 상수를 쓴다
    expect(page).toContain("showToast(REPORT_EXPORT_FAILED[format]);");
    const exportSrc = read("composables/useReportExport.ts");
    expect(exportSrc).toContain('docx: "Word 문서를 만들지 못했어요.\\n새로고침한 뒤 다시 시도해 주세요."');
    expect(exportSrc).toContain('pdf: "인쇄 창을 열지 못했어요.\\n다시 시도해 주세요."');
  });
});

describe("useResearch — 스트림 감시(소스)", () => {
  const src = read("composables/useResearch.ts");

  it("마지막 수신 뒤 45초 동안 아무것도 없으면 닫고 다시 붙는다 — 받을 때마다(onopen·onmessage) 시계를 다시 건다", () => {
    expect(src).toContain("const STREAM_QUIET_MS = 45_000;");
    expect(src).toMatch(/quietTimer = setTimeout\(\(\) => \{[\s\S]*?if \(source !== es\) return;[\s\S]*?closeStream\(\);\s*connect\(\);/);
    expect(src).toMatch(/es\.onopen = \(\) => \{[\s\S]*?heard\(es\);/);
    expect(src).toMatch(/es\.onmessage = \(msg: MessageEvent<string>\) => \{[\s\S]*?heard\(es\);[\s\S]*?JSON\.parse/);
  });

  it("서버 하트비트(이름 붙은 'ping' 이벤트)는 조용함 감시 시계만 다시 건다 — 이벤트 없는 승인 대기·대기열에서 45초마다 다시 붙지 않는다", () => {
    expect(src).toMatch(/es\.addEventListener\("ping", \(\) => \{\s*if \(source !== es\) return;\s*armQuietWatch\(es\);\s*\}\);/);
    // 화면 상태(view)·연결 띠(drops)는 건드리지 않는다
    const listener = src.match(/es\.addEventListener\("ping", \(\) => \{([\s\S]*?)\}\);/)?.[1] ?? "";
    expect(listener).not.toMatch(/view\.value|drops\.value|heard\(/);
  });

  it("읽지 못한 스트림 메시지를 버리지 않고 저장본으로 한 번 맞춘다", () => {
    expect(src).toMatch(/JSON\.parse\(msg\.data\) as ResearchEvent;\s*\} catch \{[\s\S]*?if \(!syncing\.value\) void refresh\(\);\s*return;/);
  });

  it("끊기면(onerror) 실패 수를 쌓아 연결 띠가 알린다", () => {
    expect(src).toMatch(/es\.onerror = \(\) => \{[\s\S]*?drops\.value \+= 1;/);
  });
});

describe("하위질문 부분 실패·입력 오류 — 공통 줄 안내(소스)", () => {
  it("탐색 중(ResearchLive)·탐색 뒤(ProgressPanel) 모두 서버 원문 대신 subqFailureText", () => {
    const live = read("components/research/ResearchLive.vue");
    const panel = read("components/research/ProgressPanel.vue");
    expect(live).toContain('<SkxInlineError v-if="sq.status === \'failed\'" :message="subqFailureText(sq.error)" />');
    expect(live).not.toContain("{{ sq.error }}");
    expect(panel).toContain(':message="subqFailureText(sq.error)"');
    expect(panel).not.toContain("stoppedSubq.error }}");
    expect(panel).not.toMatch(/멈췄습니다/);
  });

  it("빨간 오류 글 규칙을 없앴다 — research.css 의 위험색은 위험 단추 면에만", () => {
    const css = read("assets/css/research.css");
    expect(css).not.toContain(".rs-live__error");
    expect(css).not.toMatch(/(^|[^-])color:\s*var\(--skx-danger\)/m);
  });

  it("계획 편집값 오류·시작 실패는 줄 안내, DeepResearch 질문 입력에는 maxlength 500 과 글자 수", () => {
    const plan = read("components/research/PlanCard.vue");
    expect(plan).toContain('<SkxInlineError v-if="problem" :message="problem" />');
    const menu = read("components/research/SearchPlusMenu.vue");
    expect(menu).toContain('<SkxInlineError v-if="error" class="rs-plus__error" :message="error" />');
    expect(menu).toMatch(/<SkxCharCount\s+v-if="researchActive"\s+:id="countId"[\s\S]*?:max="QUESTION_MAX"/);
    expect(menu).toContain('field.setAttribute("maxlength", String(QUESTION_MAX));');
    expect(menu).toContain("describedByWith(field.getAttribute(\"aria-describedby\"), countId, on)");
  });
});
