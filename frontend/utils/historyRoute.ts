// frontend/utils/historyRoute.ts
import type { HistoryEntry, HistoryKind } from "~/types/history";
import { firstValue, isUuid, readDetailSource } from "~/utils/detailSource";
import { stepForPhase } from "~/utils/workPhase";

export interface HistoryRoute {
  path: string;
  query?: Record<string, string>;
}

export interface HistoryQuery {
  h?: string;
  q?: string;
  grade?: string;
}

const V1_ID = /^\d{10,16}$/;

// 이어간 연구는 그 연구의 지금 단계(?s=)로 간다 — 완료(done)는 계획서 화면. 이어가지 않은 딥리서치는 지금처럼 쿼리가 없다
export function routeFor(entry: HistoryEntry): HistoryRoute {
  if (entry.kind === "research") {
    const path = `/research/${entry.refId || entry.id}`;
    const phase = entry.research?.phase;
    return phase ? { path, query: { s: stepForPhase(phase) } } : { path };
  }
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
  const raw = firstValue(query.h) ?? firstValue(query.restore);
  if (raw && isUuid(raw)) out.h = raw.toLowerCase();
  else if (raw && V1_ID.test(raw) && v1Map[raw]) out.h = v1Map[raw];
  const q = firstValue(query.q);
  if (q) out.q = q;
  const grade = firstValue(query.grade);
  if (grade) out.grade = grade;
  return out;
}

// 업그레이드 뒤 첫 로드에서는 v1 이전이 서버 응답을 받아야 대응표가 생긴다 — 그 전에 푼 옛 주소는 랜딩으로 빠진다
export function awaitsV1Map(query: Record<string, unknown>, v1Map: Record<string, string> = {}): boolean {
  const raw = firstValue(query.h) ?? firstValue(query.restore);
  return !!raw && V1_ID.test(raw) && !v1Map[raw];
}

// 보고서에서 온 상세(from=research)는 그 보고서를 읽던 중으로 본다 — 사이드바가 딥리서치 탭과 그 보고서를 강조한다
export function activeKindForPath(path: string, query: Record<string, unknown> = {}): HistoryKind {
  if (path === "/research" || path.startsWith("/research/")) return "research";
  if (path.startsWith("/papers/") && readDetailSource(query).kind === "research") return "research";
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
  const source = path.startsWith("/papers/") ? readDetailSource(query) : null;
  if (source?.kind === "research") return source.job;
  return readHistoryQuery(query, v1Map).h ?? null;
}
