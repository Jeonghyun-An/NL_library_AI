// frontend/utils/researchReport.ts
import type {
  CountersPayload,
  EvidenceMeta,
  ExcludedPaperView,
  ReportRange,
  ResearchReport,
  SubqView,
  TrailItem,
} from "../types/research";
import { pubYear, splitAuthors } from "./citations";
import type { DraftSlot } from "./researchDraft";
import { toExcludedPaperView, type ResearchPhase } from "./researchEvents";

export function rangeLabel(range: Partial<ReportRange> | null | undefined): string | null {
  if (!range?.n_papers) return null;
  const count = `논문 ${range.n_papers.toLocaleString("ko-KR")}편 기준`;
  if (!range.from || !range.to) return count;
  const years = range.from === range.to ? `${range.from}년` : `${range.from}~${range.to}`;
  return `${years} ${count}`;
}

// 서론 문장은 모델이 아니라 화면이 만든다 — 수치를 모델에게 쓰게 하면 틀린 숫자가 실린다.
// 하위질문 수는 탐색 경로(trail)로 센다. trail 은 종합이 끝나야 생기므로 초안은 탐색한 하위질문 수를 넘긴다
export function reportIntro(report: ResearchReport, subqCount = report.trail.length): string {
  const subqs = subqCount || report.sections.length;
  const s = report.stats;
  if (s) {
    return `하위질문 ${subqs}개로 나눠 논문 ${s.papers_reviewed}편을 검토하고 ${s.evidence_adopted}편을 근거로 삼았다${droppedNote(s, "걸러냈다")}.`;
  }
  return `하위질문 ${subqs}개로 나눠 논문 ${Object.keys(report.evidence).length}편을 근거로 삼았다.`;
}

// 걸러낸 수를 서론에 덧붙인다 — 채택 수만 적으면 무관 제외로 결과가 줄어든 것처럼 읽힌다.
// 제외 수는 하위질문별 판단의 수다(한 논문을 두 하위질문이 빼면 두 번, 한 하위질문이 뺀 논문을 다른 하위질문이
// 채택하면 채택 수에도 든다). "편"으로 적으면 검토·채택 수와 더해 맞아야 할 서로 다른 논문 수로 읽혀 "건"으로 적는다.
// 뺀 것이 없거나(0) 제외 수가 없는 잡(무관 제외 전)은 적지 않는다
function droppedNote(stats: CountersPayload, verb: string): string {
  return stats.excluded ? `(하위질문별로 무관하다고 본 ${stats.excluded}건은 ${verb})` : "";
}

// 빈자리 문구는 화면(절 본문·보고서)과 내려받은 문서가 같이 쓴다 — 문서가 화면과 다른 말을 하지 않게
export const INTROLESS = "이 절은 도입 서술을 받지 못했습니다. 아래 논문 목록만 싣습니다.";
export const NO_SUMMARY = "요약을 받지 못했습니다.";
export const NO_LIMITS = "자동 점검에서 보고할 한계가 발견되지 않았습니다.";
// 제외한 논문 목록의 제목·설명 — 보고서 화면의 접힌 섹션과 내려받은 문서의 부록이 같은 말을 쓴다
export const EXCLUDED_TITLE = "관련성이 낮아 제외한 논문";
export const EXCLUDED_WHY = "자기점검이 하위질문의 핵심 개념과 무관하다고 판단해 근거에서 뺀 논문입니다.";

// 초안이 놓인 때 — writing: 쓰는 중, finishing: 다 쓰고 최종본을 받는 중(받기에 실패해 다시 시도하는 중 포함),
// interrupted: 실패·취소로 멈춤
export type DraftState = "writing" | "finishing" | "interrupted";

// 보고서 칸에 초안을 그릴지와 그 때. 완료 뒤에도 최종본을 받기 전에는 읽던 초안을 치우지 않는다
export function draftStateFor(phase: ResearchPhase | null, slot: ReportSlot | null): DraftState | null {
  switch (phase) {
    case "synthesizing":
      return "writing";
    case "failed":
    case "canceled":
      return "interrupted";
    case "completed":
      return slot === "ready" ? null : "finishing";
    default:
      return null;
  }
}

// 깜빡이는 점은 절이 아직 쌓이는 동안만 — 다 쓴 초안에 달면 완료된 연구가 아직 쓰는 중으로 읽힌다
export function draftBadge(state: DraftState): { label: string; live: boolean } {
  switch (state) {
    case "writing":
      return { label: "작성 중", live: true };
    case "finishing":
      return { label: "작성을 마친 초안", live: false };
    case "interrupted":
      return { label: "완성되지 않은 초안", live: false };
  }
}

// 초안의 서론 자리. 초안에는 trail 이 없고 끝난 절만 있어 reportIntro 로 세면 하위질문 수가 틀린다 —
// 전체 절 수는 자리를 잡아 둔 슬롯 수로, 쓴 절은 초안에 실린 절로 센다
export function draftIntro(slots: readonly DraftSlot[], state: DraftState, stats?: CountersPayload): string {
  const done = slots.filter((s) => s.sectionIndex !== null).length;
  const head = {
    writing: `${slots.length}개 절 중 ${done}개를 썼습니다. 다 쓴 절부터 먼저 보여 드립니다.`,
    finishing: `${slots.length}개 절을 모두 쓴 초안입니다. 서론과 한계 점검은 완성본에 실립니다.`,
    interrupted: `${slots.length}개 절 중 ${done}개를 쓰고 멈춘 초안입니다. 한계 점검은 보고서가 완성된 뒤에 실립니다.`,
  }[state];
  if (!stats) return head;
  // 다 쓴 뒤의 카운터는 최종 집계라 "지금까지"를 붙이지 않는다
  const upTo = state === "finishing" ? "" : "지금까지 ";
  return `${head} ${upTo}논문 ${stats.papers_reviewed}편을 검토하고 ${stats.evidence_adopted}편을 근거로 삼았습니다${droppedNote(stats, "걸러냈습니다")}.`;
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

// 하위질문 하나에서 뺀 논문들. subqIdx 는 탐색 타임라인·부록의 하위질문 번호(0부터)다
export interface ExcludedGroup {
  subqIdx: number;
  subquestion: string;
  papers: ExcludedPaperView[];
}

// 최종본은 보고서 trail 에서 만든다. 뺀 논문이 없는 하위질문과 목록을 기록하기 전 보고서는 빠진다
export function excludedFromTrail(trail: TrailItem[]): ExcludedGroup[] {
  return trail
    .map((t, i) => ({
      subqIdx: i,
      subquestion: t.subquestion,
      papers: (t.excluded_papers ?? []).map(toExcludedPaperView),
    }))
    .filter((g) => g.papers.length > 0);
}

// 초안에는 trail 이 없다(종합이 끝나야 생긴다) — 탐색 타임라인의 회차 기록을 회차 순으로 이어 같은 목록을
// 만든다. 한 하위질문은 뺀 논문을 다시 넣지 않으므로 이어 붙여도 겹치지 않는다(최종본 trail 과 같다)
export function excludedFromSubqs(subqs: SubqView[]): ExcludedGroup[] {
  return subqs
    .map((sq) => ({ subqIdx: sq.idx, subquestion: sq.title, papers: sq.rounds.flatMap((r) => r.excludedPapers) }))
    .filter((g) => g.papers.length > 0);
}

// 뺀 논문 한 줄 — "저자 외 (연도) 「제목」". 타임라인·보고서·문서가 같이 쓴다
export function excludedPaperLine(p: ExcludedPaperView): string {
  const who = paperByline({ personal_author: p.personalAuthor, pub_date: p.pubDate });
  return p.title ? `${who} 「${p.title}」` : who;
}
