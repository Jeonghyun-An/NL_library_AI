// frontend/utils/researchReport.ts
import type { EvidenceMeta, ReportRange, ResearchReport } from "../types/research";
import { pubYear, splitAuthors } from "./citations";

export function rangeLabel(range: Partial<ReportRange> | null | undefined): string | null {
  if (!range?.n_papers) return null;
  const count = `논문 ${range.n_papers.toLocaleString("ko-KR")}편 기준`;
  if (!range.from || !range.to) return count;
  const years = range.from === range.to ? `${range.from}년` : `${range.from}~${range.to}`;
  return `${years} ${count}`;
}

// 서론 문장은 모델이 아니라 화면이 만든다 — 수치를 모델에게 쓰게 하면 틀린 숫자가 실린다
export function reportIntro(report: ResearchReport): string {
  const subqs = report.trail.length || report.sections.length;
  const s = report.stats;
  if (s) {
    return `하위질문 ${subqs}개로 나눠 논문 ${s.papers_reviewed}편을 검토하고 ${s.evidence_adopted}편을 근거로 삼았다.`;
  }
  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
}

// 끝에서는 제자리에 선다. 버튼을 disabled 로 막으면 초점을 쥔 버튼이 비활성이 되는 순간
// 초점이 body 로 떨어져 팝오버가 닫히므로, 화면은 aria-disabled 로 알리기만 하고 범위는 여기서 지킨다
export function stepChunk(index: number, delta: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(Math.max(index + delta, 0), total - 1);
}

// 포인터가 칩·팝오버를 벗어날 때 닫을지. 클릭으로 고정했거나 초점이 안에 있으면 닫지 않는다 —
// 초점을 쥔 팝오버를 닫으면 초점이 body 로 떨어진다(키보드 사용자는 제자리를 잃는다). 초점이
// 안에 있을 때 닫는 일은 focusout(초점이 밖으로 옮겨 가거나 빠질 때)이 맡는다.
export function hideOnPointerLeave(pinned: boolean, focusInside: boolean): boolean {
  return !pinned && !focusInside;
}

export type ReportSlot = "ready" | "loading" | "failed";

// 완료 이벤트에는 보고서가 없어 GET 으로 다시 받는다. 그 사이·실패해 다시 시도하는 동안 본문
// 칼럼을 비우면 연구가 사라진 것처럼 보인다 — 불러오는 중, 실패 중이면 다시 불러오기를 그린다.
export function reportSlot(phase: string | null, hasReport: boolean, syncFailed: boolean): ReportSlot | null {
  if (phase !== "completed") return null;
  if (hasReport) return "ready";
  return syncFailed ? "failed" : "loading";
}

export function paperByline(meta: EvidenceMeta | undefined): string {
  const authors = splitAuthors(meta?.personal_author);
  const who = authors.length > 1 ? `${authors[0]} 외` : (authors[0] ?? "저자 미상");
  const year = pubYear(meta?.pub_date);
  return year ? `${who} (${year})` : who;
}
