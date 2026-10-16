// frontend/tests/unit/workErrors.test.ts
// 연구 작업대(이어간 연구 — 제목 고르기·참고문헌 선택하기·보고서)의 오류 처리(에러 처리 2단계, 2026-10-16).
// 순수 함수(utils/workErrors)는 실제로 돌리고, 화면(.vue)은 Nuxt 를 띄우지 않고 소스 글을 검사한다(기존 관례)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { REPORT_EXPORT_FAILED } from "~/composables/useReportExport";
import type { WorkState } from "~/types/work";
import { ERROR_HINTS } from "~/utils/apiErrors";
import { RESEARCH_NOT_FOUND } from "~/utils/researchErrors";
import { initialWorkState } from "~/utils/workEvents";
import {
  WORK_CONFLICT,
  WORK_LOAD_FAILED,
  WORK_REFRESH_FAILED,
  WORK_SAVED_STALE,
  WORK_SLOW_MESSAGE,
  WORK_SOURCES_FAILED,
  autoResumeLine,
  staleWorkKinds,
  withPeriod,
  withWorkReason,
  workConnectionAfter,
  workFailure,
  workReason,
} from "~/utils/workErrors";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");
/** <template> 부분만 — 머리 주석의 글에 속지 않게 */
const template = (src: string) => src.match(/<template>([\s\S]*)<\/template>/)?.[1] ?? "";

function httpError(status: number, detail?: unknown): Error & { status: number; data?: unknown } {
  return Object.assign(new Error(`HTTP ${status}`), { status, data: detail === undefined ? undefined : { detail } });
}

describe("workReason·workFailure — 대체 문구 머리를 떼고 이유만", () => {
  it("대체 문구 그대로면 이유가 없고, '머리 — 이유' 면 이유만, 이유만 온 문구는 그대로", () => {
    expect(workReason(WORK_REFRESH_FAILED, WORK_REFRESH_FAILED)).toBe("");
    expect(workReason(`${WORK_REFRESH_FAILED} — ${ERROR_HINTS.network}`, WORK_REFRESH_FAILED)).toBe(ERROR_HINTS.network);
    expect(workReason(ERROR_HINTS.busy, WORK_REFRESH_FAILED)).toBe(ERROR_HINTS.busy);
  });

  it("상태별로 종류(SkxErrorState kind)와 이유를 고른다 — 5xx 는 머리만, 몰림·찾을 수 없음·네트워크는 이유", () => {
    expect(workFailure(httpError(500), WORK_REFRESH_FAILED)).toEqual({
      kind: "server",
      message: WORK_REFRESH_FAILED,
      reason: "",
    });
    expect(workFailure(httpError(503), WORK_REFRESH_FAILED)).toMatchObject({ kind: "busy", reason: ERROR_HINTS.busy });
    expect(workFailure(httpError(404), WORK_LOAD_FAILED)).toMatchObject({ kind: "notFound", reason: RESEARCH_NOT_FOUND });
    expect(workFailure(new TypeError("Failed to fetch"), WORK_REFRESH_FAILED)).toEqual({
      kind: "network",
      message: `${WORK_REFRESH_FAILED} — ${ERROR_HINTS.network}`,
      reason: ERROR_HINTS.network,
    });
  });

  it("쓰기 문구 규칙(workErrorMessage)도 받는다 — 404 의 서버 한글 사유는 그대로 이유가 된다", async () => {
    const { workErrorMessage } = await import("~/utils/researchErrors");
    expect(workFailure(httpError(404, "대목이 없습니다"), WORK_SOURCES_FAILED, workErrorMessage)).toMatchObject({
      kind: "notFound",
      reason: "대목이 없습니다",
    });
  });

  it("withWorkReason 은 이유가 있을 때만 ' — ' 로 잇는다", () => {
    expect(withWorkReason(WORK_REFRESH_FAILED, "")).toBe(WORK_REFRESH_FAILED);
    expect(withWorkReason(WORK_SAVED_STALE.saved, ERROR_HINTS.network)).toBe(
      "저장은 됐지만 화면을 새로 고치지 못했어요 — 네트워크 연결을 확인해 주세요",
    );
  });
});

describe("withPeriod·autoResumeLine — 여러 줄 문구는 줄마다 마침표", () => {
  it("끝에 마침표가 없으면 붙이고 있으면 그대로", () => {
    expect(withPeriod("보고서를 이어 쓰지 못했어요")).toBe("보고서를 이어 쓰지 못했어요.");
    expect(withPeriod(ERROR_HINTS.busy)).toBe(ERROR_HINTS.busy);
  });

  it("멈춘 까닭 뒤에 [이어서 쓰기] 안내를 다음 줄로 — 까닭이 여러 줄이어도 줄마다 마침표로 끝난다", () => {
    for (const stopped of ["보고서를 이어 쓰지 못했어요 — 네트워크 연결을 확인해 주세요", ERROR_HINTS.busy]) {
      const line = autoResumeLine(stopped);
      expect(line.endsWith("\n[이어서 쓰기]를 누르면 남은 절부터 다시 써요.")).toBe(true);
      for (const part of line.split("\n")) expect(part).toMatch(/[.?!…]$/);
    }
  });
});

describe("staleWorkKinds — 단계 위 한 줄로 알릴 조회", () => {
  const withTopics: WorkState = { ...initialWorkState(), topics: { picked_id: null, seeds_left: 0, corpus: null, papers: {}, items: [] } };

  it("본문 조회가 값이 없으면 본문 자리의 오류 블록이 알리므로 빼고, 값이 있으면 한 줄로 알린다", () => {
    const failed = () => true;
    expect(staleWorkKinds(["topics", "work"], "topics", initialWorkState(), failed)).toEqual(["work"]);
    expect(staleWorkKinds(["topics", "work"], "topics", withTopics, failed)).toEqual(["topics", "work"]);
  });

  it("실패하지 않은 조회는 알리지 않는다", () => {
    expect(staleWorkKinds(["topics", "work"], "topics", withTopics, (k) => k === "work")).toEqual(["work"]);
    expect(staleWorkKinds(["topics", "work"], "topics", withTopics, () => false)).toEqual([]);
  });
});

describe("workConnectionAfter — 연구 스트림 연결 띠의 상태", () => {
  it("끊기면 다시 연결하는 중, 오래 못 붙으면 연결하지 못함, 다시 붙거나 일부러 닫으면 붙어 있음", () => {
    expect(workConnectionAfter("connected", "drop")).toBe("reconnecting");
    expect(workConnectionAfter("reconnecting", "giveUp")).toBe("lost");
    expect(workConnectionAfter("lost", "drop")).toBe("lost");
    expect(workConnectionAfter("lost", "retry")).toBe("reconnecting");
    expect(workConnectionAfter("reconnecting", "open")).toBe("connected");
    expect(workConnectionAfter("lost", "stop")).toBe("connected");
    // 이미 붙었으면 늦게 온 포기 시계는 아무것도 바꾸지 않는다
    expect(workConnectionAfter("connected", "giveUp")).toBe("connected");
  });
});

describe("작업대 오류 문구 — 해요체·문장마다 줄바꿈", () => {
  const copies: [string, string][] = [
    ["WORK_REFRESH_FAILED", WORK_REFRESH_FAILED],
    ["WORK_LOAD_FAILED", WORK_LOAD_FAILED],
    ["WORK_SOURCES_FAILED", WORK_SOURCES_FAILED],
    ["WORK_SLOW_MESSAGE", WORK_SLOW_MESSAGE],
    ...Object.entries(WORK_SAVED_STALE),
    ...Object.entries(WORK_CONFLICT),
    ...Object.entries(REPORT_EXPORT_FAILED),
  ];

  it.each(copies)("%s: 합쇼체('~습니다'·'~하세요')를 쓰지 않는다", (_name, text) => {
    expect(text).not.toMatch(/습니다|[^주]세요/);
  });

  it.each(copies)("%s: 한 줄 안에 두 문장을 잇지 않는다('. ' 대신 '.\\n')", (_name, text) => {
    expect(text).not.toMatch(/[.?!] \S/);
  });

  it.each(copies.filter(([, t]) => t.includes("\n")))("%s: 여러 줄이면 줄마다 마침표로 끝난다", (_name, text) => {
    for (const line of text.split("\n")) expect(line).toMatch(/[.?!…]$/);
  });

  it("보고서 충돌 안내는 다시 읽기 결과에 따라 사실대로 — 다시 읽지 못했으면 '다시 불러왔어요'라고 하지 않는다", () => {
    expect(WORK_CONFLICT.reloaded).toContain("다시 불러왔어요");
    expect(WORK_CONFLICT.unloaded).not.toContain("불러왔어요");
    expect(WORK_CONFLICT.stale).not.toContain("다른 곳에서");
  });
});

describe("단계 화면 — 다시 읽기 실패·쓰기 오류·느린 쓰기를 공통 컴포넌트로", () => {
  const steps: [string, string, string][] = [
    ["components/work/TopicsStep.vue", '["topics", "work"], "topics"', "주제 카드를 불러오지 못했어요"],
    ["components/work/ReadingStep.vue", '["reading", "work", "topics"], "reading"', "참고문헌 후보를 불러오지 못했어요"],
    ["components/work/ProposalStep.vue", '["proposal", "work"], "proposal"', "보고서를 불러오지 못했어요"],
  ];

  it.each(steps)("%s: 읽어 둔 뒤의 다시 읽기 실패는 위 한 줄(SkxInlineError)과 [다시 시도]로 알린다", (file, kinds) => {
    const src = read(file);
    expect(src).toContain(`useWorkStale(props.work, ${kinds})`);
    expect(template(src)).toMatch(/<SkxInlineError v-if="staleLine" :message="staleLine" :busy="staleRetrying" @retry="retryStale" \/>/);
    expect(template(src)).toContain('<SkxInlineError v-if="slow" :message="WORK_SLOW_MESSAGE" />');
  });

  it.each(steps)("%s: 값이 없을 때의 조회 실패는 본문 자리의 SkxErrorState(kind·이유·[다시 시도])", (file, _kinds, title) => {
    const tpl = template(read(file));
    expect(tpl).toMatch(new RegExp(`<SkxErrorState\\s+v-if="![a-z]+ && loadFailure"\\s+:kind="loadFailure.kind"\\s+title="${title}"\\s+:message="loadFailure.reason"`));
  });

  it.each(steps)("%s: 빨간 안내 줄(rs-alert role=alert)·옛 오류 카드를 쓰지 않는다", (file) => {
    const tpl = template(read(file));
    expect(tpl).not.toMatch(/rs-alert"\s+role="alert"|rs-card--error|class="rs-card rs-state"/);
  });

  it("쓰기는 다시 읽기까지 성공해야 성공 문구 — 실패면 위 한 줄의 머리를 '…했지만 화면을 새로 고치지 못했어요'로", () => {
    const proposal = read("components/work/ProposalStep.vue");
    expect(proposal).toMatch(
      /if \(await refresh\(\["proposal"\], body\.approve \? WORK_SAVED_STALE\.approved : WORK_SAVED_STALE\.saved\)\) \{\s+say\(body\.approve/,
    );
    expect(proposal).toMatch(/markWritten\(field\);\s+if \(await refresh\(\["proposal"\], WORK_SAVED_STALE\.saved\)\) \{/);
    // 충돌 안내는 다시 읽기 결과를 본 뒤 고른다
    expect(proposal).toContain("say(!fresh ? WORK_CONFLICT.unloaded : ours ? WORK_CONFLICT.stale : WORK_CONFLICT.reloaded, true)");
    const topics = read("components/work/TopicsStep.vue");
    expect(topics).toMatch(/opts\.done\?\.\(\);\s+if \(!\(await reloadAll\(kinds\)\)\) markSaved\(opts\.stale \?\? WORK_SAVED_STALE\.saved\);/);
  });

  it("쓰기 응답을 받으면 다시 읽기가 실패해도 열어 둔 칸을 닫는다 — 카드 고치기·카드 더하기·문단 고치기·연구 배경/방법", () => {
    expect(read("components/work/TopicCard.vue")).toMatch(/\(\) => props\.savedSeq \?\? 0,\s+\(seq\) => \{\s+if \(seq\) editing\.value = false;/);
    expect(read("components/work/TopicDeck.vue")).toMatch(/if \(props\.saved\?\.kind === "write" && sentIds\.value\) closeWrite\(\);/);
    expect(read("components/work/ProposalSection.vue")).toMatch(/const wrote = \(props\.savedSeq \?\? 0\) !== p\.seq;/);
    expect(read("components/work/DocField.vue")).toMatch(/props\.value\.trim\(\) === pending \|\| \(props\.savedSeq \?\? 0\) !== pendingSeq/);
  });

  it("참고문헌 표는 저장 사슬이 비면(다시 읽기가 실패해도) 저장 중 표시를 걷는다", () => {
    const table = read("components/work/ReadingTable.vue");
    expect(table).toMatch(/\(\) => props\.pending \?\? 0,\s+\(n\) => \{\s+if \(n === 0 && saving\.value\.size\) saving\.value = new Set\(\);/);
    expect(template(read("components/work/ReadingStep.vue"))).toContain(':pending="saves.pending.value"');
  });
});

describe("연구 화면([id].vue) — 이어간 연구 조회 실패·연결 끊김 띠", () => {
  const page = read("pages/research/[id].vue");
  const tpl = template(page);

  it("단계 화면에 연결 끊김 띠를 늘 그려 두고 상태만 바꾼다(v-if 없이)", () => {
    expect(tpl).toContain('<SkxConnectionBanner class="wk-conn" :state="work.connection.value" @retry="work.reconnect()" />');
  });

  it("보고서 화면의 이어가기 카드 자리 — 조회가 실패했으면 '이 연구 이어가기' 대신 안내와 [다시 시도]", () => {
    expect(tpl).toMatch(
      /<SkxErrorState\s+v-if="work\.exists\.value === null && \(workLoadFailure \|\| workLoadRetrying\)"\s+compact[\s\S]*?@retry="retryWorkLoad"\s+\/>\s+<ContinueResearchCard\s+v-else/,
    );
  });

  it("단계 화면의 첫 조회 실패도 공통 상태 블록으로", () => {
    expect(tpl).toMatch(/<SkxErrorState\s+v-if="!workView && workLoadFailure"[\s\S]*?:title="WORK_LOAD_FAILED"[\s\S]*?@retry="work\.load\(\)"/);
  });

  it("내보내기 실패 토스트는 공통 문구(해요체)를 쓴다", () => {
    expect(page).toContain("showToast(REPORT_EXPORT_FAILED[format]);");
    expect(page).not.toContain("Word 문서를 만들지 못했습니다");
  });
});

describe("useResearchWork — 연구 스트림의 끊김을 연결 상태로 내보낸다", () => {
  const src = read("composables/useResearchWork.ts");

  it("오류가 나면 drop, 열리면 open, 일부러 닫으면 stop — 늦게 온 옛 연결의 오류는 무시한다", () => {
    expect(src).toMatch(/es\.onerror = \(\) => \{[\s\S]*?if \(source !== es\) return;\s+streamEvent\("drop"\);/);
    expect(src).toMatch(/es\.onopen = \(\) => \{\s+attempts = 0;\s+if \(source === es\) streamEvent\("open"\);/);
    expect(src).toMatch(/function disconnect\(\): void \{[\s\S]*?streamEvent\("stop"\);/);
  });
});
