// frontend/utils/topicDeck.ts
// 주제 단계(spec §4 S3·§5-2) 화면의 문구·정렬·상태 판단. TopicDeck·TopicCard·ConceptChips 는 이 결과만 그린다.
// 카드 한 장 = 생성 1건(topic_card)이고, 카드가 오지 않으면 '근거 부족' 빈 슬롯으로 정직하게 보인다(spec §4 시연 정직성)
import type {
  GenStatus,
  PaperMeta,
  TopicCard,
  TopicCreate,
  TopicItem,
  TopicSeed,
  TopicsView,
  WorkGeneration,
} from "~/types/work";
import { citeLabel } from "~/utils/citations";
import { genQueueLine } from "~/utils/queueLine";

export type CardStatus = "waiting" | "making" | "ready" | "insufficient" | "failed";
export type ConceptsStatus = "making" | "ready" | "empty" | "failed";

// 서버 경계와 같은 값(app/services/research_work/shapes.py·concepts.py) — 화면이 먼저 막아 422 를 보지 않게 한다
export const TOPIC_TITLE_MIN = 2;
export const TOPIC_TITLE_MAX = 120;
export const TOPIC_QUESTION_MIN = 2;
export const TOPIC_QUESTION_MAX = 300;
export const MIN_TOPIC_EVIDENCE = 2;
export const OTHER_DIRECTION_CARDS = 2;
export const CONCEPTS_MAX = 5;
export const CONCEPT_LEN_MAX = 40;

const OPEN: readonly GenStatus[] = ["queued", "running"];
// 저자를 모르는 근거 칩은 제목 앞부분으로 가른다
const CHIP_TITLE_CHARS = 12;
const SEED_KIND_LABEL: Record<TopicSeed["kind"], string> = {
  future: "보고서의 향후 과제",
  insufficient: "근거가 모자랐던 하위질문",
};

// 파이썬 len 은 코드포인트를 센다 — JS length(UTF-16)로 세면 이모지에서 어긋난다(researchInput 과 같은 규칙)
function codepoints(text: string): number {
  return [...text].length;
}

// 카드가 실제로 있는가 — 서버는 빈 카드({})를 null 로 보내지만 제목이 빈 카드도 없는 것으로 본다
function cardOf(item: TopicItem): TopicCard | null {
  return item.card && item.card.title.trim() ? item.card : null;
}

// 접힌 카드(06c 가지치기)는 빼고, 처음 자리(slot)가 있는 카드를 자리 순으로, 그 뒤에 [다른 방향]·[직접 쓰기] 카드를 만든 순으로
export function deckOrder(items: TopicItem[]): TopicItem[] {
  return items
    .filter((item) => item.state !== "folded")
    .sort((a, b) => {
      if (a.slot !== null && b.slot !== null) return a.slot - b.slot || a.id - b.id;
      if (a.slot !== null) return -1;
      if (b.slot !== null) return 1;
      return a.id - b.id;
    });
}

// 카드가 있으면 ready. 없으면 그 주제의 마지막 카드 생성으로 가른다 — 끝났는데(done) 카드가 없으면 근거 부족이고
// (서버 topic_card.apply 가 state 를 insufficient 로 둔다), 실패·취소면 failed. 생성 기록이 없는 빈 카드는
// 다시 부를 생성도 없으므로 근거 부족(state 가 그렇다면) 또는 failed 로 둔다
export function cardStatus(item: TopicItem): CardStatus {
  if (cardOf(item)) return "ready";
  const g = item.generation;
  if (!g) return item.state === "insufficient" ? "insufficient" : "failed";
  if (g.status === "queued") return "waiting";
  if (g.status === "running") return "making";
  if (g.status === "done") return "insufficient";
  return "failed";
}

// 카드를 뒤집는 때 — 기다리거나 쓰던 슬롯에 카드가 실제로 도착했을 때만. 처음 그릴 때(before 없음)나
// 사용자가 빈 슬롯을 직접 채웠을 때(insufficient → ready)는 뒤집지 않는다
export function cardArrived(before: CardStatus | undefined, now: CardStatus): boolean {
  return now === "ready" && (before === "waiting" || before === "making");
}

export function cardNote(status: CardStatus): string | null {
  switch (status) {
    case "waiting":
      return "차례를 기다리는 중입니다";
    case "making":
      return "카드를 쓰는 중입니다";
    case "insufficient":
      return `근거 부족 — 이 씨앗을 직접 받치는 논문을 ${MIN_TOPIC_EVIDENCE}편 이상 찾지 못했습니다`;
    case "failed":
      return "카드를 만들지 못했습니다";
    case "ready":
      return null;
  }
}

export function canPick(item: TopicItem): boolean {
  return item.state === "candidate" && cardStatus(item) === "ready";
}

function shortTitle(title: string | null | undefined): string | null {
  const chars = [...(title ?? "").trim()];
  if (!chars.length) return null;
  return chars.length > CHIP_TITLE_CHARS ? `${chars.slice(0, CHIP_TITLE_CHARS).join("")}…` : chars.join("");
}

// 근거 칩 — 보고서 인용칩과 같은 '저자 연도' 라벨(citeLabel). 단계 화면에는 REPORT_JOB provide 가 없어
// CitationChip 을 쓰지 않는다. 저자를 모르면 제목 앞부분, 서지가 없으면 cnts_id
export function evidenceChips(
  card: TopicCard,
  papers: Record<string, PaperMeta>,
): { cntsId: string; label: string; title: string }[] {
  return card.evidence.map((cntsId) => {
    const meta = papers[cntsId];
    return {
      cntsId,
      label: citeLabel(meta, shortTitle(meta?.title) ?? cntsId),
      title: meta?.title?.trim() || cntsId,
    };
  });
}

// 카드가 어디서 왔는지 — 보고서 씨앗(향후 과제·근거가 모자랐던 하위질문)과 그 절 소제목
export function seedLine(seed: TopicSeed | null): string | null {
  if (!seed) return null;
  const heading = seed.heading.trim();
  return heading ? `${SEED_KIND_LABEL[seed.kind]} · ${heading}` : SEED_KIND_LABEL[seed.kind];
}

// 주제 목록(GET topics)의 생성 상태를 연구 SSE 로 받은 최신 상태로 덮는다 — 대기 → 쓰는 중이 다시 읽지 않아도 보인다.
// 끝난(done) 생성의 결과(카드)는 주제 목록을 다시 읽어야 들어오므로 그때까지는 쓰는 중으로 둔다 — 근거 부족이 잠깐
// 비쳤다가 카드로 바뀌지 않게 한다. 목록이 더 새 생성을 알면(다시 부른 직후) 목록 값을 쓴다
export function liveTopics(topics: TopicsView, generations: readonly WorkGeneration[]): TopicsView {
  const latest = new Map<string, WorkGeneration>();
  for (const g of generations) {
    if (g.kind !== "topic_card" || g.target === null) continue;
    const seen = latest.get(g.target);
    if (!seen || g.id > seen.id) latest.set(g.target, g);
  }
  if (!latest.size) return topics;
  const items = topics.items.map((item) => {
    const live = latest.get(String(item.id));
    const shown = item.generation;
    if (!live || (shown && shown.id > live.id)) return item;
    if (shown && shown.id === live.id && shown.status === live.status) return item;
    const status: GenStatus = live.status === "done" ? "running" : live.status;
    return { ...item, generation: { id: live.id, status } };
  });
  return { ...topics, items };
}

// 덱 위 한 줄 — 남은 카드 생성 수와 맨 앞 생성의 대기 문구(쓰는 중 · 앞에 N건 · 약 M분 …)
export function deckQueueLine(generations: readonly WorkGeneration[]): string | null {
  const open = generations.filter((g) => g.kind === "topic_card" && OPEN.includes(g.status));
  if (!open.length) return null;
  const first =
    open.find((g) => g.status === "running") ??
    [...open].sort((a, b) => (a.position ?? Number.MAX_SAFE_INTEGER) - (b.position ?? Number.MAX_SAFE_INTEGER))[0]!;
  const line = genQueueLine(first);
  return line ? `주제 카드 ${open.length}장 남음 · ${line}` : `주제 카드 ${open.length}장 남음`;
}

// [다른 방향] 옆 안내 — 쓰지 않은 보고서 씨앗으로 한 번에 최대 2장
export function moreLine(seedsLeft: number): string {
  if (seedsLeft <= 0) return "더 쓸 씨앗이 없습니다 — [직접 쓰기] 로 주제를 더할 수 있습니다";
  return `남은 씨앗 ${seedsLeft}개 · 누르면 ${Math.min(OTHER_DIRECTION_CARDS, seedsLeft)}장을 더 받습니다`;
}

// [직접 쓰기]·[직접 고치기] 입력 검사 — 서버 TopicCreate·TopicPatch 와 같은 경계(앞뒤 공백을 뺀 코드포인트)
export function topicProblem(body: TopicCreate): string | null {
  const title = codepoints(body.title.trim());
  if (title < TOPIC_TITLE_MIN) return `제목을 ${TOPIC_TITLE_MIN}자 이상 쓰세요`;
  if (title > TOPIC_TITLE_MAX) return `제목은 ${TOPIC_TITLE_MAX}자까지입니다`;
  const question = codepoints(body.question.trim());
  if (question < TOPIC_QUESTION_MIN) return `연구 질문을 ${TOPIC_QUESTION_MIN}자 이상 쓰세요`;
  if (question > TOPIC_QUESTION_MAX) return `연구 질문은 ${TOPIC_QUESTION_MAX}자까지입니다`;
  return null;
}

// 서버 concepts.clean_concepts 와 같은 정리 — NFKC 뒤 공백을 하나로
export function cleanConcept(raw: string): string {
  return raw.normalize("NFKC").split(/\s+/).filter(Boolean).join(" ");
}

// 대소문자·공백을 무시한 같은 개념(서버 clean_concepts 의 중복 열쇠)
function conceptKey(text: string): string {
  return text.replace(/\s/g, "").toLowerCase();
}

// 칩 하나 더하기. 빈 글·40자 초과·이미 있는 개념·5개가 찬 목록이면 받은 배열을 그대로 돌려준다(새 배열이 아니다)
export function addConcept(concepts: string[], raw: string): string[] {
  const text = cleanConcept(raw);
  const n = codepoints(text);
  if (n < 1 || n > CONCEPT_LEN_MAX || concepts.length >= CONCEPTS_MAX) return concepts;
  const key = conceptKey(text);
  if (concepts.some((c) => conceptKey(c) === key)) return concepts;
  return [...concepts, text];
}

// 핵심 개념 칩의 상태 — 생성이 열려 있으면 고칠 수 없다(서버 PATCH 가 409). 끝내 못 얻으면 비운 채 done(spec §5-2)
export function conceptsStatus(concepts: string[], generation: WorkGeneration | null): ConceptsStatus {
  if (generation && OPEN.includes(generation.status)) return "making";
  if (concepts.length) return "ready";
  if (generation && (generation.status === "failed" || generation.status === "canceled")) return "failed";
  return "empty";
}

// [다시] 를 보일 때 — 서버 _retryable 의 범위(failed·canceled, 비운 채 끝난 done) 가운데 칩이 비어 있을 때만.
// 사용자가 칩을 채운 뒤에는 다시 부르지 않는다(결과가 사용자 칩을 덮는다)
export function conceptsRetryable(concepts: string[], generation: WorkGeneration | null): boolean {
  if (!generation || concepts.length) return false;
  return generation.status === "failed" || generation.status === "canceled" || generation.status === "done";
}

export function conceptsNote(concepts: string[], generation: WorkGeneration | null): string | null {
  switch (conceptsStatus(concepts, generation)) {
    case "making": {
      const line = generation ? genQueueLine(generation) : null;
      return line ? `핵심 개념을 뽑는 중입니다 · ${line}` : "핵심 개념을 뽑는 중입니다";
    }
    case "failed":
      return "핵심 개념을 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요";
    case "empty":
      return generation
        ? "뽑힌 핵심 개념이 없습니다 — 직접 넣거나 [다시] 를 누르세요"
        : "핵심 개념 넣기 — 원 질문의 핵심 개념을 칩으로 더하세요";
    case "ready":
      return null;
  }
}
