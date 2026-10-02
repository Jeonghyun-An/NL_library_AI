// frontend/utils/detailSource.ts
import type { ComputedRef, InjectionKey } from "vue";
import type { ReportPaper, ReportSection } from "~/types/research";
import { splitCitations } from "~/utils/citations";

// 논문 상세의 출처. 주소만으로 돌아갈 곳·사이드바 강조·배너·AI 요약 기준이 정해진다(새 탭·새로고침에도)
export type DetailSource =
  | { kind: "search"; h: string | null; q: string }
  | { kind: "research"; job: string; e: string | null }
  | { kind: "none" };

// 돌아가서 맞출 요소의 앵커와, 떠날 때 그 요소의 화면 높이(px). 픽셀 좌표가 아니라 요소 기준이라
// 배치(A/B)·창 크기가 바뀌어도 같은 자리를 찾는다
export interface ReturnSpot {
  at: string | null;
  y: number | null;
}

// n 은 같은 절에서 같은 근거 칩의 순번(0 부터, 0 은 앵커에 적지 않는다)
export type Anchor =
  | { kind: "cite"; section: number; eid: string; n: number }
  | { kind: "excluded"; cnts: string }
  | { kind: "result"; cnts: string };

export type AnchoredPart = { type: "text"; text: string } | { type: "cite"; eid: string; anchor: string };

export interface AnchoredSection {
  intro: AnchoredPart[];
  papers: Array<{ paper: ReportPaper; chips: Array<{ eid: string; anchor: string }> }>;
  future: AnchoredPart[][];
}

// 인용칩의 [논문 상세]가 돌아올 보고서의 잡 id — ReportView 가 내려 주고 칩이 받는다(절·본문 부품을 거치지 않게)
export const REPORT_JOB: InjectionKey<ComputedRef<string>> = Symbol("report-job");

// 서버 기록 id 는 브라우저 v4 · 잡 id v4 · v1 이전분 uuid5 가 섞여 있어 버전을 가리지 않는다
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const EID = /^E\d+$/;
const PIXELS = /^\d{1,6}$/;
// 앵커는 [data-anchor="…"] 선택자에 그대로 들어간다 — 따옴표·괄호·공백이 낄 수 없는 모양만 받는다
const CITE_ANCHOR = /^c-(0|[1-9]\d*)-(E\d+)(?:-([1-9]\d*))?$/;
const ITEM_ANCHOR = /^([xp])-([A-Za-z0-9_.-]{1,64})$/;
// 주소 비교용 기준 — 경로와 쿼리만 본다
const BASE = "http://local";

export function firstValue(v: unknown): string | undefined {
  const s = Array.isArray(v) ? v[0] : v;
  return typeof s === "string" && s.trim() ? s.trim() : undefined;
}

export function isUuid(s: string): boolean {
  return UUID.test(s);
}

function idOf(v: unknown): string | null {
  const s = firstValue(v);
  return s && isUuid(s) ? s.toLowerCase() : null;
}

export function readDetailSource(query: Record<string, unknown>): DetailSource {
  const from = firstValue(query.from);
  // from 을 싣기 전의 상세 주소(?q=&h=)는 검색 결과에서만 만들었다 — 열린 탭·방문 기록·북마크에 남아 있어 검색 출처로 읽는다
  if (from === "search" || from === undefined) {
    const h = idOf(query.h);
    const q = firstValue(query.q) ?? "";
    return h || q ? { kind: "search", h, q } : { kind: "none" };
  }
  if (from === "research") {
    const job = idOf(query.job);
    const e = firstValue(query.e);
    return job ? { kind: "research", job, e: e && EID.test(e) ? e : null } : { kind: "none" };
  }
  return { kind: "none" };
}

// y 는 at 이 가리키는 요소의 높이라 at 없이는 쓰지 않는다
export function readReturnSpot(query: Record<string, unknown>): ReturnSpot {
  const raw = firstValue(query.at);
  const at = raw && parseAnchor(raw) ? raw : null;
  const y = firstValue(query.y);
  return { at, y: at && y && PIXELS.test(y) ? Number(y) : null };
}

function appendSpot(params: URLSearchParams, spot: ReturnSpot): void {
  if (!spot.at) return;
  params.set("at", spot.at);
  if (spot.y !== null) params.set("y", String(spot.y));
}

function withQuery(path: string, params: URLSearchParams): string {
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export function detailUrl(
  cntsId: string,
  source: DetailSource,
  spot?: ReturnSpot,
  extra: Record<string, string> = {},
): string {
  const params = new URLSearchParams();
  if (source.kind === "search") {
    params.set("from", "search");
    if (source.h) params.set("h", source.h);
    if (source.q) params.set("q", source.q);
  } else if (source.kind === "research") {
    params.set("from", "research");
    params.set("job", source.job);
    if (source.e) params.set("e", source.e);
  }
  if (spot) appendSpot(params, spot);
  for (const [key, value] of Object.entries(extra)) params.set(key, value);
  return withQuery(`/papers/${encodeURIComponent(cntsId)}`, params);
}

// 연관 논문으로 넘어가도 처음 출처와 돌아갈 자리를 잇는다 — 몇 편을 넘겨 봐도 [돌아가기]는 처음 화면의 그 자리로 간다.
// 인용 근거 번호(e)·관련도(score)는 처음 논문의 것이라 뗀다
export function relatedDetailUrl(cntsId: string, source: DetailSource, spot: ReturnSpot): string {
  return detailUrl(cntsId, source.kind === "research" ? { ...source, e: null } : source, spot);
}

// 보고서·탐색 타임라인의 "제외한 논문" 링크 — 인용한 근거가 아니라 e 가 없다
export function excludedDetailUrl(job: string, cnts: string, y: number | null = null): string {
  return detailUrl(cnts, { kind: "research", job, e: null }, { at: excludedAnchor(cnts), y });
}

export function backTarget(source: DetailSource, spot: ReturnSpot): { label: string; to: string } {
  const params = new URLSearchParams();
  switch (source.kind) {
    case "search":
      if (source.h) params.set("h", source.h);
      if (source.q) params.set("q", source.q);
      appendSpot(params, spot);
      return { label: "검색 결과로", to: withQuery("/papers", params) };
    case "research":
      appendSpot(params, spot);
      return { label: "딥리서치 보고서로", to: withQuery(`/research/${source.job}`, params) };
    case "none":
      return { label: "검색으로", to: "/" };
  }
}

// 직전 기록(vue-router 의 history.state.back)이 돌아갈 곳이면 router.back() 으로 브라우저 상태를 그대로 쓴다.
// 자리(at·y)는 견주지 않는다 — 떠날 때 출처 주소에 실어 둔 자리와 상세 주소의 자리는 같은 요소를 가리킨다
export function shouldGoBack(historyBack: string | null, to: string): boolean {
  if (!historyBack) return false;
  const back = new URL(historyBack, BASE);
  const target = new URL(to, BASE);
  if (back.pathname !== target.pathname) return false;
  const h = target.searchParams.get("h");
  if (h) return back.searchParams.get("h") === h;
  return back.searchParams.get("q") === target.searchParams.get("q");
}

export function citeAnchor(sectionIdx: number, eid: string, n = 0): string {
  return n ? `c-${sectionIdx}-${eid}-${n}` : `c-${sectionIdx}-${eid}`;
}

export function excludedAnchor(cnts: string): string {
  return `x-${cnts}`;
}

export function resultAnchor(cnts: string): string {
  return `p-${cnts}`;
}

export function parseAnchor(at: string): Anchor | null {
  const cite = CITE_ANCHOR.exec(at);
  if (cite) return { kind: "cite", section: Number(cite[1]), eid: cite[2]!, n: Number(cite[3] ?? 0) };
  const item = ITEM_ANCHOR.exec(at);
  if (!item) return null;
  return item[1] === "x" ? { kind: "excluded", cnts: item[2]! } : { kind: "result", cnts: item[2]! };
}

export function anchorSelector(at: string): string | null {
  return parseAnchor(at) ? `[data-anchor="${at}"]` : null;
}

// 한 절에 같은 근거 칩이 여러 번 나오면 그리는 순서(도입 → 대표 논문 → 향후 과제)대로 순번을 붙인다 —
// 돌아왔을 때 사용자가 누른 바로 그 칩을 찾는다
export function anchoredSection(sec: ReportSection, sectionIdx: number): AnchoredSection {
  const seen = new Map<string, number>();
  const anchorFor = (eid: string): string => {
    const n = seen.get(eid) ?? 0;
    seen.set(eid, n + 1);
    return citeAnchor(sectionIdx, eid, n);
  };
  const withAnchors = (text: string): AnchoredPart[] =>
    splitCitations(text).map((part) => (part.type === "cite" ? { ...part, anchor: anchorFor(part.eid) } : part));
  return {
    intro: sec.intro ? withAnchors(sec.intro) : [],
    papers: sec.papers.map((paper) => ({
      paper,
      chips: paper.evidence.map((eid) => ({ eid, anchor: anchorFor(eid) })),
    })),
    future: sec.future.map((f) => withAnchors(f.text)),
  };
}
