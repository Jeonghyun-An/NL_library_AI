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

export function paperByline(meta: EvidenceMeta | undefined): string {
  const authors = splitAuthors(meta?.personal_author);
  const who = authors.length > 1 ? `${authors[0]} 외` : (authors[0] ?? "저자 미상");
  const year = pubYear(meta?.pub_date);
  return year ? `${who} (${year})` : who;
}
