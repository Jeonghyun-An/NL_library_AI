// frontend/utils/researchDraft.ts
import type {
  CountersPayload,
  CountersView,
  ReportSection,
  ResearchReport,
  ResearchView,
  SynthSectionView,
} from "../types/research";
import { isTerminalStatus } from "./researchEvents";

export type DraftSlotStatus = "done" | "failed" | "running" | "waiting";

// 작성 현황 카드의 한 줄이자 초안의 절 자리 하나. idx 는 워커의 section_idx(절 순번)와 같다
export interface DraftSlot {
  idx: number;
  heading: string;
  status: DraftSlotStatus;
  durationMs: number | null;
  startedAt: string | null;
  // DraftReport.report.sections 안의 위치 — 내용을 받은 끝난 절에만 있다
  sectionIndex: number | null;
}

export interface DraftReport {
  report: ResearchReport;
  slots: DraftSlot[];
  done: number;
  total: number;
}

export interface SynthEta {
  done: number;
  total: number;
  runningIdx: number | null;
  runningElapsedMs: number | null;
  remainingMs: number | null;
}

export function draftSlots(view: ResearchView): DraftSlot[] {
  const byIdx = new Map(view.synth.sections.map((s) => [s.idx, s]));
  const stopped = isStopped(view);
  const slots: DraftSlot[] = [];
  let placed = 0;
  for (let idx = 0; idx < slotCount(view); idx++) {
    const s = byIdx.get(idx);
    const finished = s?.status === "done" || s?.status === "failed";
    slots.push({
      idx,
      heading: slotHeading(view, idx, s),
      status: slotStatus(s, stopped),
      durationMs: s?.durationMs ?? null,
      startedAt: s?.startedAt ?? null,
      sectionIndex: finished && s?.section ? placed++ : null,
    });
  }
  return slots;
}

// 끝난 절을 절 순서대로 모아 최종 보고서와 같은 모양으로 만든다 — ReportView·내보내기가 최종본과
// 같은 코드로 그리게. 한계는 보고서가 완성된 뒤에만 있으므로 비워 둔다.
export function draftReport(view: ResearchView): DraftReport | null {
  const slots = draftSlots(view);
  const byIdx = new Map(view.synth.sections.map((s) => [s.idx, s.section]));
  const sections = slots
    .filter((slot) => slot.sectionIndex !== null)
    .map((slot) => byIdx.get(slot.idx))
    .filter((sec): sec is ReportSection => !!sec);
  if (!sections.length) return null;
  const stats = liveStats(view.counters);
  return {
    report: {
      question: view.question,
      range: null,
      sections,
      evidence: view.synth.evidence,
      trail: [],
      limitations: [],
      ...(stats ? { stats } : {}),
    },
    slots,
    done: sections.length,
    total: slots.length,
  };
}

// 남은 시간 = 끝난 절들의 걸린 시간 평균 × 대기 절 수 + 쓰는 중인 절의 (평균 − 경과, 0 미만이면 0).
// 걸린 시간은 워커가 잰 값이라 화면 시계와 무관하다. 경과만 화면 시계(nowMs)와 서버의 started_at 을
// 견주므로, 두 시계가 어긋나 started_at 이 미래로 보여도 음수가 되지 않게 자른다.
export function synthEta(view: ResearchView, nowMs: number): SynthEta {
  const slots = draftSlots(view);
  const finished = slots.filter((s) => s.status === "done" || s.status === "failed");
  const running = slots.find((s) => s.status === "running");
  const runningElapsedMs = running ? elapsedSince(running.startedAt, nowMs) : null;
  const durations = finished.map((s) => s.durationMs).filter((d): d is number => d !== null && d >= 0);
  let remainingMs: number | null = null;
  if (durations.length) {
    const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length;
    const waiting = slots.filter((s) => s.status === "waiting").length;
    const current = running ? Math.max(0, avg - (runningElapsedMs ?? 0)) : 0;
    remainingMs = Math.round(avg * waiting + current);
  }
  return {
    done: finished.length,
    total: slots.length,
    runningIdx: running?.idx ?? null,
    runningElapsedMs,
    remainingMs,
  };
}

export function formatClock(ms: number): string {
  const total = Number.isFinite(ms) ? Math.max(0, Math.floor(ms / 1000)) : 0;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function formatRemaining(ms: number | null, done: number): string {
  if (done <= 0) return "첫 절을 쓰는 중";
  // 끝난 절은 있는데 걸린 시간을 모른다(옛 워커의 결과) — "첫 절을 쓰는 중"이라 적으면 틀린 말이 된다
  if (ms === null || !Number.isFinite(ms)) return "남은 시간 계산 중";
  const sec = Math.round(Math.max(0, ms) / 1000);
  if (sec < 10) return "곧 끝납니다";
  if (sec < 60) return `약 ${sec}초 남음`;
  // 1분을 넘으면 초 자리를 10초 단위로 반올림한다 — 긴 추정을 초 단위로 적으면 매초 흔들려 읽기 어렵다
  const rounded = Math.round(sec / 10) * 10;
  const m = Math.floor(rounded / 60);
  const s = rounded % 60;
  return s ? `약 ${m}분 ${s}초 남음` : `약 ${m}분 남음`;
}

// 절 수는 워커가 알린 total 이 정본이다. 모르면(옛 결과·첫 이벤트 전) 제목 목록·받은 절 번호로 센다
function slotCount(view: ResearchView): number {
  const { total, headings, sections } = view.synth;
  const known = sections.reduce((n, s) => Math.max(n, s.idx + 1), 0);
  return Math.max(total, headings.length, known);
}

function slotHeading(view: ResearchView, idx: number, s: SynthSectionView | undefined): string {
  const named = [view.synth.headings[idx], s?.heading, s?.section?.heading].find((h) => h?.trim());
  return named?.trim() || `절 ${idx + 1}`;
}

function slotStatus(s: SynthSectionView | undefined, stopped: boolean): DraftSlotStatus {
  if (!s) return "waiting";
  // 실패·취소로 멈춘 뒤의 "작성 중"은 더 쓰이지 않는다 — 움직이는 줄·경과 시계를 띄우지 않게 대기로 본다
  if (s.status === "running" && stopped) return "waiting";
  return s.status;
}

function isStopped(view: ResearchView): boolean {
  return view.synth.status === "done" || view.synth.status === "failed" || isTerminalStatus(view.status);
}

// 보고서 서론 한 줄(reportIntro)이 읽는 stats — 라이브 카운터가 셋 다 있을 때만 싣는다.
// 하나라도 비면(옛 잡) 서론은 근거 수만 쓰는 옛 문장으로 되돌아간다
function liveStats(c: CountersView): CountersPayload | null {
  if (c.papersReviewed === null || c.evidenceAdopted === null || c.rechecks === null) return null;
  return { papers_reviewed: c.papersReviewed, evidence_adopted: c.evidenceAdopted, rechecks: c.rechecks };
}

function elapsedSince(startedAt: string | null, nowMs: number): number | null {
  if (!startedAt) return null;
  const t = Date.parse(startedAt);
  return Number.isNaN(t) ? null : Math.max(0, nowMs - t);
}
