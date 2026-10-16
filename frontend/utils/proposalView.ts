// frontend/utils/proposalView.ts
import type {
  Outline,
  Paragraph,
  ParagraphChecks,
  ProposalSection,
  ProposalView,
  SectionPut,
  WorkGeneration,
  WorkState,
  WorkView,
} from "~/types/work";
import { sentenceFlags, spaceBeforeCites, splitMarkers, type MarkerPart, type SentenceFlag } from "~/utils/figureMarkers";
import { httpStatus } from "~/utils/apiErrors";
import { versionConflict } from "~/utils/researchErrors";
import { latestGeneration, openGeneration } from "~/utils/workEvents";
import { FINAL_STEP_NAME } from "~/utils/workPhase";

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

// 인용 표기를 칩으로 그릴 조각. 이 절의 근거 지도에 없는 번호는 badcite(취소선) — 저장할 때 서버가 버리는 번호다.
// 앞 낱말에 붙은 칩 앞에는 띄어쓰기를 넣는다(spaceBeforeCites — 취소선 번호는 [E9] 글자 그대로라 띄우지 않는다)
export function paragraphParts(text: string, evidence: Record<string, string>): ParaPart[] {
  return spaceBeforeCites(
    splitMarkers(text).map((p): ParaPart => (p.type === "cite" && !evidence[p.eid] ? { type: "badcite", eid: p.eid } : p)),
  );
}

// 화면이 그리는 문단 — 문장(근거 표시 없는 문장·[F#] 밖 숫자)과 문장마다의 칩 조각, 검사 한 줄을 미리 나눠 둔다
export interface SentenceView extends SentenceFlag {
  parts: ParaPart[];
}

export interface ParagraphView {
  p: Paragraph;
  sentences: SentenceView[];
  check: string | null;
}

// 절 하나의 문단을 한 번에 나눈다. 화면은 절이 바뀔 때(계획서를 다시 읽을 때)만 이것을 다시 부른다 — 절 글이
// 흐르는 동안 조각(section_delta)마다 모든 절이 다시 그려지는데, 그때마다 문단을 다시 나누지 않게
export function paragraphViews(section: ProposalSection): ParagraphView[] {
  return section.paragraphs.map((p) => ({
    p,
    sentences: sentenceFlags(p.text).map((s) => ({ ...s, parts: paragraphParts(s.text, section.evidence) })),
    check: checkLine(p.checks),
  }));
}

// 이 절의 문단마다 열린 다시 쓰기 생성(문단 id → 가장 새 생성). 생성 목록(work)에만 기댄다
export function openParagraphGens(
  work: WorkView | null,
  key: string,
  pids: readonly string[],
): Map<string, WorkGeneration> {
  const out = new Map<string, WorkGeneration>();
  for (const pid of pids) {
    const g = openGeneration({ work }, "paragraph", `${key}#${pid}`);
    if (g) out.set(pid, g);
  }
  return out;
}

// 이 절에서 다시 쓰기가 글을 얻지 못하고 끝난 문단(id). 그 문단을 쓴 생성보다 나중인 가장 새 다시 쓰기가 실패했거나
// 세 번 다 검사를 못 넘은 빈 결과(done 인데 model 없음 — 입력을 옮긴 답 등)일 때다. 서버는 그 문단을 그대로 두므로
// 알리지 않으면 [다시]가 듣지 않은 듯 보인다. 사용자가 고친·쓴 문단은 알리지 않는다 — 그 글은 이미 사용자 것이다
export function failedParagraphGens(
  work: WorkView | null,
  key: string,
  paragraphs: readonly Paragraph[],
): Set<string> {
  const out = new Set<string>();
  for (const p of paragraphs) {
    if (p.state !== "proposed" && p.state !== "accepted") continue;
    const g = latestGeneration({ work }, "paragraph", `${key}#${p.id}`);
    if (!g || (p.gen_id !== null && g.id <= p.gen_id)) continue;
    if (g.status === "failed" || (g.status === "done" && g.model === null)) out.add(p.id);
  }
  return out;
}

// 문단 상태로 센 기여 — 검토 전·수락만 한 문단도 AI 작성으로 센다(spec §3·D21)
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
    ? `AI 작성 ${ai}문단 중 수락 ${f.accepted}·수정 ${f.edited}${f.proposed ? `·검토 전 ${f.proposed}` : ""}`
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
  if (!n) return "빈 문단은 저장할 수 없어요 — 지우려면 [지우기]를 눌러 주세요";
  if (n > MAX_PARAGRAPH_CHARS) return `문단은 ${MAX_PARAGRAPH_CHARS}자까지 쓸 수 있어요`;
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

// PUT /outline 이 본문 그대로 덮어쓰는 목차 값 — 묶음(키·이름·논문 순서), 연구 질문, 방법, 승인 상태, 연구 배경.
// 묶음 hint·연구 질문 후보·승인 시각은 본문이 정하지 않는다(서버가 지키거나 새로 찍는다)
function outlineWrites(o: Outline): string {
  return JSON.stringify([
    o.groups.map((g) => [g.key, g.name, g.papers]),
    o.question ?? "",
    o.method,
    o.state,
    outlineBackground(o),
  ]);
}

// 연구 배경·방법 저장(PUT /outline) — 보고서를 자동으로 쓰는 동안 절이 반영될 때마다 version 이 올라 409 version_conflict
// 를 받는다. 본문(fieldPut)은 보낼 때의 목차로 묶음·연구 질문·방법·승인을 다시 싣고 서버는 그 값을 그대로 덮어쓰므로,
// 충돌이 절 반영 때문일 때만 다시 보낸다: 계획서를 다시 읽어(reread — ProposalStep 은 proposalReread) 목차의 그 값
// (outlineWrites)이 그대로면 다시 읽은 version·목차로 한 번만 보낸다(spec §12-4 — 절 반영은 목차를 바꾸지 않아 덮어쓸
// 것이 없다). 목차가 바뀐 충돌(다른 탭의
// [목차 고치기]·초안 저장, [보고서 다시 만들기] 반영 뒤 다시 읽기 전)이면 옛 본문이 그 변경을 되돌리고 초안을 다시 승인하므로
// 보내지 않고 첫 충돌을 던진다 — 다시 읽기가 실패해 version 이 그대로일 때도 같다. 두 번째 409 와 그 밖의 오류도 그대로
// 던진다 — 부르는 쪽(ProposalStep act)이 다시 읽고 알린다(칸은 열린 채 글이 남는다)
export async function putOnceMore<T>(
  put: (version: number, outline: Outline) => Promise<T>,
  sent: { version: number; outline: Outline },
  reread: () => Promise<Pick<ProposalView, "version" | "outline"> | null>,
): Promise<T> {
  try {
    return await put(sent.version, sent.outline);
  } catch (e) {
    if (versionConflict(e) === null) throw e;
    const fresh = await reread();
    if (!fresh?.outline || fresh.version <= sent.version || outlineWrites(fresh.outline) !== outlineWrites(sent.outline)) {
      throw e;
    }
    return put(fresh.version, fresh.outline);
  }
}

// putOnceMore 의 다시 읽기 — 화면 상태를 거치지 않고 GET /proposal 응답 하나에서 version·목차를 함께 꺼낸다. 화면의
// work.reload('proposal') 는 같은 조회를 새로 읽기 시작하면 제 응답을 버린다(늦은 응답 버리기). 충돌은 절이 반영된 바로
// 그때 나고 그 절의 generation 이벤트가 reload('proposal') 를 부르므로, reload 로 다시 읽으면 화면이 옛 version 에 머물러
// 절 반영만 있었는데도 첫 충돌을 던졌다. 읽기가 실패하면 null — putOnceMore 가 다시 보내지 않고 첫 충돌을 던진다.
// 화면 갱신은 부르는 쪽이 그대로 맡는다(저장 뒤·act 의 충돌 처리에서 reload)
export function proposalReread(get: () => Promise<ProposalView>): () => Promise<ProposalView | null> {
  return async () => {
    try {
      return await get();
    } catch {
      return null;
    }
  };
}

// 검토할 곳(06e, §12-11 권고) — 수락 관문이 빠진 자동 보고서에서 코드 검사 표시(근거 표시 없는 문장·[F#] 밖 숫자)가 사실상
// 유일한 검토 단서다. 문서가 그리는 절(목차 묶음 → 연구 공백)의 저장된 문단만 센다 — 목차에서 빠진 옛 절은 화면·문서에 없다.
// first 는 둘 중 하나라도 있는 첫 문단(머리 줄을 누르면 그 자리로 간다)
export interface ReviewSpots {
  unmarked: number;
  numbers: number;
  first: { key: string; pid: string } | null;
}

export function reviewSpots(p: ProposalView): ReviewSpots {
  const out: ReviewSpots = { unmarked: 0, numbers: 0, first: null };
  for (const key of sectionKeysOf(p)) {
    for (const para of p.sections[key]?.paragraphs ?? []) {
      // 직접 쓴 문단은 저장 전 checks 가 {} 일 수 있다(서버가 다시 검사해 채운다) — 없는 칸은 0 으로 센다
      const unmarked = para.checks?.unmarked ?? 0;
      const numbers = para.checks?.numbers?.length ?? 0;
      out.unmarked += unmarked;
      out.numbers += numbers;
      if (!out.first && (unmarked || numbers)) out.first = { key, pid: para.id };
    }
  }
  return out;
}

// 머리 한 줄 '검토할 곳: 근거 없는 문장 n · 확인 필요 숫자 m' — 0 인 칸은 빼고, 둘 다 0 이면 null(줄을 그리지 않는다).
// 공개 부록에도 같은 줄을 싣는다(proposalDocument.disclosureLines)
export function reviewLine(r: ReviewSpots): string | null {
  const parts = [r.unmarked ? `근거 없는 문장 ${r.unmarked}` : "", r.numbers ? `확인 필요 숫자 ${r.numbers}` : ""].filter(
    Boolean,
  );
  return parts.length ? `검토할 곳: ${parts.join(" · ")}` : null;
}

// ── 보고서 자동 산출(06e D20) — [보고서 만들기] 한 번으로 목차를 자동 확정하고 절을 문서 순서대로 넣는다 ──

// 화면이 쓰는 절의 차례 — 목차 묶음 순서(prior.g1~g4) → 연구 공백. 계획서 화면의 절 목록·문서(proposalDocument.printedKeys)·
// 자동 산출이 모두 이 순서다. 목차가 없으면 연구 공백만
export function sectionKeysOf(p: ProposalView): string[] {
  return [...(p.outline?.groups.map((g) => g.key) ?? []), "gap"];
}

// 절 연쇄가 도는 조건 — [보고서 만들기]의 반영이 자동 승인한 목차(state approved·auto)이고, 예시 연구가 아니고(쓰기가 409),
// 목차를 다시 만드는 중이 아니고, 끝난 목차 생성이 계획서에 다 반영됐을 때. 06b 때 승인한 목차(auto 없음)·[목차 고치기]에서
// 승인을 푼 목차는 돌지 않는다. 조건은 늘 서버 값으로 다시 계산한다 — 탭을 닫았다 와도 같은 조건으로 이어 넣는다(spec §12-4)
export function autoChainOn(p: ProposalView | null, work: WorkView | null): boolean {
  const outline = p?.outline;
  if (!outline || !work) return false;
  return (
    outline.state === "approved" &&
    outline.auto === true &&
    !work.is_example &&
    !openGeneration({ work }, "outline", "outline") &&
    !unappliedOutline(outline, work)
  );
}

// 끝났지만 이 계획서에 아직 없는 목차 생성 — done 이벤트는 생성 목록에 바로 오고 계획서는 비동기로 다시 읽는다. 그 틈에
// 옛 목차의 묶음 키를 넣으면 서버(새 목차)가 404·409 로 거절해 연쇄가 멈춘다. 목차 반영(outline.apply)은 빈 결과여도 늘
// gen_id 를 그 생성으로 쓰므로 목차의 gen_id 보다 나중의 done 이면 다시 읽기 전이다. failed·canceled 는 목차를 바꾸지 않는다.
// 가장 새 생성만 보지 않는다 — done 뒤에 또 다시 만들기가 실패해도 계획서는 그 done 의 목차여야 한다(sectionStatus 와 같은 규칙)
function unappliedOutline(outline: Outline, work: WorkView): boolean {
  const applied = outline.gen_id ?? 0;
  return work.generations.some(
    (g) => g.kind === "outline" && g.target === "outline" && g.status === "done" && g.id > applied,
  );
}

// 자동으로 쓸 절 — 문서 순서에서 절도, 그 키의 section 생성 기록(상태 무관 — failed·canceled 포함)도 없는 키. 실패·취소로
// 끝난 절은 다시 넣지 않고 그 절의 [다시 시도]에 맡긴다. section_gens 가 없는 옛 서버 응답은 절이 없는 키를 모두 고른다
export function autoTargets(p: ProposalView): string[] {
  const gens = p.section_gens ?? {};
  return sectionKeysOf(p).filter((k) => !p.sections[k] && !gens[k]);
}

// 보고서를 다 썼는가 — 서버 단계(phase)는 Word 를 받아야 done 이 되어, 절을 다 쓴 뒤에도 머리 단계 줄이 '보고서 쓰는 중'으로
// 남았다(2026-10-15 운영 확인). 문서 순서의 절이 모두 끝났고(다 씀, 또는 취소로 끝나 생성 기록만 있음) 쓰는·기다리는·실패한 절과
// 아직 손대지 않은 절(autoTargets)이 없으며 다 쓴 절이 하나라도 있을 때 true. 계획서·목차를 아직 못 읽었으면 false(옛 줄 그대로)
export function proposalWritten(state: WorkState): boolean {
  const p = state.proposal;
  if (!p?.outline) return false;
  const statuses = sectionKeysOf(p).map((k) => sectionStatus(k, state));
  if (statuses.some((s) => s === "writing" || s === "queued" || s === "failed")) return false;
  return autoTargets(p).length === 0 && statuses.includes("done");
}

// 다음에 넣을 절 — skip(이 방문에서 이미 넣었거나 근거가 없어 건너뛴 키)을 뺀 첫 키, 없으면 null
export function nextAutoSection(p: ProposalView, skip: ReadonlySet<string>): string | null {
  return autoTargets(p).find((k) => !skip.has(k)) ?? null;
}

// 절 쓰기가 '그 절에 넣을 논문이 없어' 막혔다 — 409 detail {code: "no_section_papers", message}(06e 서버). 연쇄는 그 절만
// 건너뛰고 다음 키로 간다. 문자열 detail(06e 전 서버)·다른 409(쓰는 중·승인 전)는 아니다
export function isNoSectionPapers(err: unknown): boolean {
  if (httpStatus(err) !== 409) return false;
  const data = (err as { data?: unknown } | null)?.data;
  const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : null;
  return !!detail && typeof detail === "object" && (detail as { code?: unknown }).code === "no_section_papers";
}

// 연구 배경 글 — Outline.background 키가 없는 응답(필드를 열기 전 서버)은 빈 글이다
export function outlineBackground(outline: Outline): string {
  const value = (outline as Outline & { background?: unknown }).background;
  return typeof value === "string" ? value : "";
}

// 머리 목차의 한 항목. anchor 는 보고서 화면의 자리 id(ProposalStep — 1·2·5·6 은 wk-doc-*, 절은 ProposalSection 의 wk-sec-<key>)
export interface TocItem {
  key: string;
  no: string;
  label: string;
  anchor: string;
  status: SectionStatus | "text" | "blank" | "skipped";
}

// 머리 목차 — 문서 순서의 여섯 자리(1 주제·2 연구 배경·3.n 선행연구 묶음·4 연구 공백·5 연구 질문·6 방법 제안 — Word 의 절
// 제목과 같은 말). 글 자리는 적었으면 text, 비면 blank. 절은 그 절의 상태(sectionStatus), 근거가 없어 연쇄가 건너뛴 쓰기 전
// 절은 skipped. 목차가 없으면 빈 목록
export function docToc(p: ProposalView, state: WorkState, skipped: ReadonlySet<string>): TocItem[] {
  const outline = p.outline;
  if (!outline) return [];
  const filled = (text: string | null | undefined): TocItem["status"] => (text?.trim() ? "text" : "blank");
  const sectionItem = (key: string, no: string, label: string): TocItem => {
    const status = sectionStatus(key, state);
    return { key, no, label, anchor: `wk-sec-${key}`, status: status === "empty" && skipped.has(key) ? "skipped" : status };
  };
  return [
    { key: "topic", no: "1", label: SECTION_LABELS.topic!, anchor: "wk-doc-topic", status: filled(outline.topic.title) },
    {
      key: "background",
      no: "2",
      label: SECTION_LABELS.background!,
      anchor: "wk-doc-background",
      status: filled(outlineBackground(outline)),
    },
    ...outline.groups.map((g, i) => sectionItem(g.key, `3.${i + 1}`, g.name)),
    sectionItem("gap", "4", SECTION_LABELS.gap!),
    { key: "question", no: "5", label: SECTION_LABELS.question!, anchor: "wk-doc-question", status: filled(outline.question) },
    { key: "method", no: "6", label: SECTION_LABELS.method!, anchor: "wk-doc-method", status: filled(outline.method) },
  ];
}

// 목차 편집기의 편집 버튼 이름 — 머리 목차의 토글도 접혀 있을 때 이 이름으로 편집기를 편집 모드로 바로 연다
export const OUTLINE_EDIT = "목차 고치기";

// 머리 목차의 편집기 토글 이름(06e) — 접혀 있으면 여는 이름(고칠 수 있으면 [목차 고치기], 예시 연구는 읽기만), 펴 있으면
// '목차 접기'. 편 동안 편집기 안의 [목차 고치기](그만두기·다시 승인 뒤 읽기 모드에서 서는 버튼)와 같은 이름의 버튼이 한
// 화면에 둘 서지 않는다 — 접으면 편집기는 v-show 로 숨어 컨트롤 목록에서 빠진다
export function outlineToggleLabel(open: boolean, readOnly: boolean): string {
  if (open) return "목차 접기";
  return readOnly ? "목차 자세히 보기" : OUTLINE_EDIT;
}

// 보고서 화면 머리의 큰 진행 막대(06e 정함 28 — 사용자 Q1 답 '현재 절 작성 중에 보이는 커다란 프로그레스바'를 자동 보고서에도)
export interface ReportBar {
  label: string;
  done: number;
  total: number;
  percent: number;
  running: boolean;
}

// 절이 끝날 때만 움직인다(추정 증가 없음 — 절 하나 평균 8초). 끝난 절 = 다 썼거나(done) 실패했거나, 쓰기 전인데 근거가 없어
// 건너뛰었거나 생성 기록이 있는(취소로 끝난) 절. 쓰는 절 = 대기·쓰는 중. 남은 절 = 연쇄가 돌 때 아직 넣지 않은 절(건너뛴 키
// 빼고) — stopped(연쇄가 오류로 멈춤)면 없다고 본다. 쓰는 절도 남은 절도 없으면 null(다 썼거나, 연쇄가 돌지 않는 목차에서
// 손으로 쓰는 절이 없을 때 — 막대를 걷는다). 글줄은 조사 없는 꼴(정함 1)
export function reportBar(
  p: ProposalView,
  state: WorkState,
  skipped: ReadonlySet<string>,
  stopped = false,
): ReportBar | null {
  const outline = p.outline;
  if (!outline) return null;
  const keys = sectionKeysOf(p);
  const gens = p.section_gens ?? {};
  const status = new Map(keys.map((k) => [k, sectionStatus(k, state)] as const));
  const done = keys.filter((k) => {
    const st = status.get(k);
    return st === "done" || st === "failed" || (st === "empty" && (skipped.has(k) || gens[k] !== undefined));
  }).length;
  const active = keys.filter((k) => status.get(k) === "writing" || status.get(k) === "queued");
  const pending =
    !stopped && autoChainOn(p, state.work)
      ? autoTargets(p).filter((k) => status.get(k) === "empty" && !skipped.has(k))
      : [];
  const current = active.find((k) => status.get(k) === "writing") ?? active[0] ?? pending[0];
  if (current === undefined) return null;
  const total = keys.length;
  return {
    label: `${FINAL_STEP_NAME} 작성 중 · ${done}/${total}절 — 「${sectionLabel(current, outline)}」`,
    done,
    total,
    percent: Math.round((done / total) * 100),
    running: status.get(current) === "writing",
  };
}
