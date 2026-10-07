// frontend/utils/proposalView.ts
import type {
  Outline,
  ParagraphChecks,
  ProposalSection,
  ProposalView,
  SectionPut,
  WorkState,
} from "~/types/work";
import { splitMarkers, type MarkerPart } from "~/utils/figureMarkers";
import { latestGeneration, openGeneration } from "~/utils/workEvents";

// 고정 6절 — 키 순서가 곧 문서 순서다. 선행연구 검토의 묶음(prior.g1~g4)은 목차의 묶음 이름으로 부른다(sectionLabel)
export const SECTION_LABELS: Record<string, string> = {
  topic: "주제",
  background: "연구 배경",
  prior: "선행연구 검토",
  gap: "연구 공백",
  question: "연구 질문",
  method: "방법 제안",
};

// 서버(services/research_work/shapes.py 의 같은 이름)와 같은 값 — 연구 공백 절은 확인 검색을 거치지 않은 후보로만 쓴다
export const GAP_NOTE = "소장 코퍼스에서 확인하지 않은 공백 후보";
// 서버 절 PUT 검증과 같은 상한 — 넘기면 422 로 거절된다
export const MAX_PARAGRAPH_CHARS = 3000;
export const MAX_PARAGRAPHS_PUT = 12;

export type SectionStatus = "empty" | "queued" | "writing" | "done" | "failed";
export type ParaPart = MarkerPart | { type: "badcite"; eid: string };

export interface Footprint {
  proposed: number;
  accepted: number;
  edited: number;
  authored: number;
}

export function sectionLabel(key: string, outline: Outline | null): string {
  const group = outline?.groups.find((g) => g.key === key);
  if (group) return `${SECTION_LABELS.prior} · ${group.name}`;
  if (key.startsWith("prior.")) return SECTION_LABELS.prior ?? key;
  return SECTION_LABELS[key] ?? key;
}

// 절 하나의 상태. 다시 쓰기가 실패해도 앞서 쓴 절은 남는다 — 그 절보다 나중의 실패만 알린다.
// 취소는 실패가 아니다 — 앞서 쓴 절이 있으면 그것, 없으면 아직 쓰지 않은 절이다.
// 끝났지만 아직 절에 반영되지 않은 done(그 절보다 나중의 생성)은 둘로 가른다. 세 번 다 검사를 못 넘은 빈 결과
// (model 없음 — 서버는 절을 건드리지 않고 retry 를 받는다)는 실패다. 결과가 있으면 계획서를 다시 읽기 전까지
// 쓰는 중이다 — done 이벤트에 흐르던 글은 지워지므로, 그대로 두면 '쓰기 전'·옛 문단이 잠깐 비치고 처음 쓰는 절은
// [이 절 쓰기]가 다시 눌린다(topicDeck.liveTopics 와 같은 규칙)
export function sectionStatus(key: string, state: WorkState): SectionStatus {
  const open = openGeneration(state, "section", key);
  // 워커는 running 을 이벤트로 알리지 않고(계약 §7) 조각이 흐르는 동안은 하트비트·snapshot 도 없다 —
  // 이 생성의 조각(section_delta)을 받기 시작했으면 쓰는 중이다
  if (open) return open.status === "running" || state.live[key]?.genId === open.id ? "writing" : "queued";
  const section = state.proposal?.sections[key] ?? null;
  const last = latestGeneration(state, "section", key);
  if (last && (!section || last.id > section.gen_id)) {
    if (last.status === "failed") return "failed";
    if (last.status === "done") return last.model === null ? "failed" : "writing";
  }
  return section && section.paragraphs.length ? "done" : "empty";
}

// 인용 표기를 칩으로 그릴 조각. 이 절의 근거 지도에 없는 번호는 badcite(취소선) — 저장할 때 서버가 버리는 번호다
export function paragraphParts(text: string, evidence: Record<string, string>): ParaPart[] {
  return splitMarkers(text).map((p): ParaPart => (p.type === "cite" && !evidence[p.eid] ? { type: "badcite", eid: p.eid } : p));
}

// 문단 상태로 센 기여 — 수락만 한 문단도 AI 작성으로 센다(spec §3)
export function footprint(p: ProposalView): Footprint {
  const f: Footprint = { proposed: 0, accepted: 0, edited: 0, authored: 0 };
  for (const section of Object.values(p.sections)) {
    for (const para of section.paragraphs) f[para.state] += 1;
  }
  return f;
}

export function footprintLine(f: Footprint): string {
  const ai = f.proposed + f.accepted + f.edited;
  const head = ai
    ? `AI 제안 ${ai}문단 중 수락 ${f.accepted}·수정 ${f.edited}${f.proposed ? `·검토 전 ${f.proposed}` : ""}`
    : "";
  const own = f.authored ? `직접 쓴 문단 ${f.authored}` : "";
  return [head, own].filter(Boolean).join(" · ") || "아직 쓴 문단이 없습니다";
}

// 서버가 문단을 검사하며 남긴 것 — 버린 인용·수치 표기, 고친 단정 표현, 근거 표시 없는 문장, [F#] 밖 숫자
export function checkLine(checks: ParagraphChecks): string | null {
  const parts = [
    checks.dropped ? `인용 ${checks.dropped}개 버림` : "",
    checks.dropped_f ? `수치 표기 ${checks.dropped_f}개 버림` : "",
    checks.softened ? `단정 표현 ${checks.softened}곳 고침` : "",
    checks.unmarked ? `근거 표시 없는 문장 ${checks.unmarked}` : "",
    checks.numbers.length ? `확인 필요한 숫자 ${checks.numbers.length}개` : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

export function paragraphProblem(text: string): string | null {
  const n = Array.from(text.trim()).length;
  if (!n) return "빈 문단은 저장할 수 없습니다 — 지우려면 [지우기]를 누르세요";
  if (n > MAX_PARAGRAPH_CHARS) return `문단은 ${MAX_PARAGRAPH_CHARS}자까지입니다`;
  return null;
}

// ── 절 PUT 본문 — 늘 절 전체를 보낸다. 상태 전이는 서버가 정한다(글이 바뀐 문단 → 고침, 사용자 작성은 그대로) ──
function entry(p: ProposalSection["paragraphs"][number]): SectionPut["paragraphs"][number] {
  return { id: p.id, text: p.text, state: p.state };
}

export function editParagraph(section: ProposalSection, pid: string, text: string): SectionPut {
  return {
    paragraphs: section.paragraphs.map((p) => {
      if (p.id !== pid || p.text === text) return entry(p);
      return { id: p.id, text, state: p.state === "authored" ? "authored" : "edited" };
    }),
  };
}

export function acceptParagraph(section: ProposalSection, pid: string): SectionPut {
  return {
    paragraphs: section.paragraphs.map((p) =>
      p.id === pid && p.state === "proposed" ? { ...entry(p), state: "accepted" } : entry(p),
    ),
  };
}

export function removeParagraph(section: ProposalSection, pid: string): SectionPut {
  return { paragraphs: section.paragraphs.filter((p) => p.id !== pid).map(entry) };
}

export function addParagraph(section: ProposalSection, text: string): SectionPut {
  return { paragraphs: [...section.paragraphs.map(entry), { id: null, text, state: "authored" }] };
}
