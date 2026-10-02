// frontend/utils/paperDetail.ts
import type { ReportChunk, ResearchJob } from "~/types/research";
import { citeLabel, pdfPage } from "./citations";
import type { DetailSource } from "./detailSource";

type JobText = Pick<ResearchJob, "question" | "report">;

export interface CiteContext {
  question: string;
  label: string;
  // 인용 대목 — 쪽 순이라 첫 대목이 첫 인용 쪽이다. 쪽 정보가 없는 대목도 빼지 않고 뒤에 둔다 —
  // 배너의 "인용 대목 N곳"과 원문 뷰어의 "n/N"이 같은 수를 센다
  chunks: ReportChunk[];
}

// 쪽 정보가 없는 대목(pdfPage 가 undefined)을 맨 뒤로 보내는 정렬 값
const NO_PAGE = Number.MAX_SAFE_INTEGER;

// 보고서에서 온 상세의 인용 맥락 배너. 보고서가 아직 없거나(작성 중) 근거 번호가 이 논문의 것이 아니면 내지 않는다 —
// 주소의 e 를 고쳐 쓰면 다른 논문의 대목을 이 논문 것처럼 보이게 된다
export function citeContext(job: JobText, eid: string | null, cntsId: string): CiteContext | null {
  if (!eid || !job.report) return null;
  const evidence = job.report.evidence[eid];
  if (!evidence || evidence.cnts_id !== cntsId) return null;
  return {
    question: job.report.question || job.question,
    label: citeLabel(evidence.meta, eid),
    chunks: [...evidence.chunks].sort((a, b) => (pdfPage(a) ?? NO_PAGE) - (pdfPage(b) ?? NO_PAGE)),
  };
}

// AI 요약의 기준 질문 — 검색에서 왔으면 결과의 검색어, 보고서에서 왔으면 보고서 질문(작성 중이면 잡 질문).
// 빈 문자열이면 요약을 만들지 않고 소개글을 보인다
export function summaryQuestion(source: DetailSource, job: JobText | null): string {
  if (source.kind === "search") return source.q;
  if (source.kind === "research" && job) return job.report?.question || job.question;
  return "";
}

// "김 2019로"·"김 2020으로" — 끝 글자에 받침이 있으면(ㄹ 제외) "으로". 숫자는 읽는 소리로 가린다(0 십·백·천, 3 삼, 6 육).
// 한글·숫자가 아니면(영문 성) 받침을 알 수 없어 "로"로 둔다
const DIGIT_BATCHIM = new Set(["0", "3", "6"]);
const HANGUL_FIRST = 0xac00;
const HANGUL_LAST = 0xd7a3;
const RIEUL = 8;

function needsEuro(ch: string): boolean {
  if (DIGIT_BATCHIM.has(ch)) return true;
  const code = ch.charCodeAt(0);
  if (code < HANGUL_FIRST || code > HANGUL_LAST) return false;
  const jong = (code - HANGUL_FIRST) % 28;
  return jong !== 0 && jong !== RIEUL;
}

export function withRo(word: string): string {
  return `${word}${needsEuro(word.slice(-1)) ? "으로" : "로"}`;
}
