// frontend/utils/historyRoute.ts
import type { HistoryEntry, HistoryKind } from "~/types/history";

export interface HistoryRoute {
  path: string;
  query?: Record<string, string>;
}

export interface HistoryQuery {
  h?: string;
  q?: string;
  grade?: string;
}

// 서버 기록 id 는 브라우저 v4 · 잡 id v4 · v1 이전분 uuid5 가 섞여 있어 버전을 가리지 않는다
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const V1_ID = /^\d{10,16}$/;

function first(v: unknown): string | undefined {
  const s = Array.isArray(v) ? v[0] : v;
  return typeof s === "string" && s.trim() ? s.trim() : undefined;
}

export function routeFor(entry: HistoryEntry): HistoryRoute {
  if (entry.kind === "research") return { path: `/research/${entry.refId || entry.id}` };
  const query: Record<string, string> = { h: entry.id, q: entry.title };
  if (entry.kind === "book") return { path: "/", query };
  const grade = entry.params?.grade;
  if (typeof grade === "string" && grade) query.grade = grade;
  return { path: "/papers", query };
}

export function readHistoryQuery(
  query: Record<string, unknown>,
  v1Map: Record<string, string> = {},
): HistoryQuery {
  const out: HistoryQuery = {};
  const raw = first(query.h) ?? first(query.restore);
  if (raw && UUID.test(raw)) out.h = raw.toLowerCase();
  else if (raw && V1_ID.test(raw) && v1Map[raw]) out.h = v1Map[raw];
  const q = first(query.q);
  if (q) out.q = q;
  const grade = first(query.grade);
  if (grade) out.grade = grade;
  return out;
}

// 업그레이드 뒤 첫 로드에서는 v1 이전이 서버 응답을 받아야 대응표가 생긴다 — 그 전에 푼 옛 주소는 랜딩으로 빠진다
export function awaitsV1Map(query: Record<string, unknown>, v1Map: Record<string, string> = {}): boolean {
  const raw = first(query.h) ?? first(query.restore);
  return !!raw && V1_ID.test(raw) && !v1Map[raw];
}

export function activeKindForPath(path: string): HistoryKind {
  if (path === "/research" || path.startsWith("/research/")) return "research";
  if (path === "/papers" || path.startsWith("/papers/")) return "paper";
  return "book";
}

export function activeIdFor(
  path: string,
  query: Record<string, unknown>,
  v1Map: Record<string, string> = {},
): string | null {
  const match = /^\/research\/([^/?#]+)/.exec(path);
  if (match) return decodeURIComponent(match[1]!);
  return readHistoryQuery(query, v1Map).h ?? null;
}
