// frontend/utils/topicDeck.ts
// 주제 단계(spec §4 S3·§5-2) 화면의 문구·정렬·상태 판단. TopicDeck·TopicCard·ConceptChips 는 이 결과만 그린다.
// 카드 한 장 = 생성 1건(topic_card)이고, 카드가 오지 않으면 '근거 부족' 빈 슬롯으로 정직하게 보인다(spec §4 시연 정직성)
import type {
  GenStatus,
  KeywordCandidate,
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

// blocked — 키워드 생성이 실패해 씨앗 카드가 아직 들어가지 않은 자리(06e D23 — 키워드를 다시 부르면 카드가 들어간다)
export type CardStatus = "waiting" | "making" | "ready" | "insufficient" | "failed" | "blocked";
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
// [이 키워드로 다시 만들기] 의 최소 선택 수(keywords.MIN_PICKED_KEYWORDS) — 선행연구 묶음 수가 키워드 수 이하다
export const MIN_PICKED_KEYWORDS = 2;

const OPEN: readonly GenStatus[] = ["queued", "running"];
// 저자를 모르는 근거 칩은 제목 앞부분으로 가른다
const CHIP_TITLE_CHARS = 12;
const SEED_KIND_LABEL: Record<TopicSeed["kind"], string> = {
  future: "딥리서치 보고서의 향후 과제",
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
// (서버 topic_card.apply 가 state 를 insufficient 로 둔다), 실패·취소면 failed. 생성 기록이 없는 빈 씨앗 자리(slot 이 있는
// 보고서 씨앗)는 06e 부터 키워드가 정해지기를 기다린다(D23) — 씨앗 자리 카드 생성은 키워드 생성의 반영·취소와 같은
// 트랜잭션에 들어간다. 그래서 키워드 생성(concepts)이 열려 있을 때뿐 아니라 done·canceled 이벤트와 topics·work 다시 읽기
// 사이도 waiting 이고, 키워드 생성이 실패했으면 카드가 들어가지 않아 blocked. 그 밖은 근거 부족(state 가 그렇다면) 또는 failed
export function cardStatus(item: TopicItem, concepts?: WorkGeneration | null): CardStatus {
  if (cardOf(item)) return "ready";
  const g = item.generation;
  if (!g) {
    if (item.state === "insufficient") return "insufficient";
    if (concepts && item.slot !== null && item.origin === "report_seed") {
      return concepts.status === "failed" ? "blocked" : "waiting";
    }
    return "failed";
  }
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
    case "blocked":
      return "키워드를 다시 부르거나 [이 키워드로 다시 만들기]를 누르면 카드를 만듭니다";
    case "ready":
      return null;
  }
}

// 카드는 있는데 그 카드 생성이 열려 있다 — [이 키워드로 다시 만들기](06e)가 넣은 새 카드를 기다리는 중
function remaking(item: TopicItem): boolean {
  return cardOf(item) !== null && item.generation !== null && OPEN.includes(item.generation.status);
}

// 다시 만드는 중인 카드는 고르지 않는다 — 고른 카드는 다시 만든 결과로 덮지 않으므로(서버 topic_card.apply,
// 06e 정함 16) 고르면 새 카드가 버려진다
export function canPick(item: TopicItem): boolean {
  return item.state === "candidate" && cardStatus(item) === "ready" && !remaking(item);
}

// 다시 만드는 중인 카드에 붙이는 줄 — 새 결과가 반영될 때까지 지금 카드를 그대로 보인다
export function cardRemakingNote(item: TopicItem): string | null {
  return remaking(item) ? "새 키워드로 다시 만드는 중입니다" : null;
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

// 카드 제목·질문에서 [F#] 밖에 쓴 숫자(서버가 card.checks.numbers 에 센다) — 계획서 문단과 같은 '확인 필요' 줄.
// 수치는 [F#] 로만 들어간다(spec §5-2·§5-5·§7) — 모델이나 사용자가 직접 쓴 숫자는 원문과 맞는지 확인하게 알린다
export function cardNumbersLine(card: TopicCard): string | null {
  const numbers = card.checks?.numbers ?? [];
  return numbers.length ? `확인 필요 ${numbers.join(", ")}` : null;
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
      return line ? `키워드를 뽑는 중입니다 · ${line}` : "키워드를 뽑는 중입니다";
    }
    case "failed":
      return "키워드를 뽑지 못했습니다 — 직접 넣거나 [다시] 를 누르세요";
    case "empty":
      return generation
        ? "뽑힌 키워드가 없습니다 — 직접 넣거나 [다시] 를 누르세요"
        : "키워드 넣기 — 원 질문의 키워드를 칩으로 더하세요";
    case "ready":
      return null;
  }
}

// ── 제목 고르기 — 키워드(06e D23) ──

// 원문 → 글자 맞추기용 평평한 글. 원문 글자(코드포인트)마다 NFKC·소문자로 바꾼 글자를 잇고 공백은 뺀다. at[k] 는 평평한
// 글의 k 번째 UTF-16 단위가 나온 원문 글자 순번이다 — 맞은 자리를 원문 그대로 감싸려고(전각 'ＣＳＲ' 은 'csr' 로 맞추고
// 'ＣＳＲ' 을 감싼다, 공백을 지우고 맞춘 '다문화가정' 은 원문 '다문화 가정' 을 감싼다)
function flatten(chars: readonly string[]): { flat: string; at: number[] } {
  let flat = "";
  const at: number[] = [];
  chars.forEach((ch, i) => {
    for (const c of ch.normalize("NFKC").toLowerCase()) {
      if (/\s/.test(c)) continue;
      flat += c;
      for (let u = 0; u < c.length; u += 1) at.push(i);
    }
  });
  return { flat, at };
}

// 낱말 하나의 맞은 자리(원문 글자 순번 [처음, 끝]) — 서버 06c terms.contains 와 같은 규칙: 공백을 지운 글에서 낱말 전체가
// 부분 문자열이면 그 자리, 아니면 낱말 조각이 모두 순서대로 있을 때 조각마다. 하나라도 없으면 맞지 않는다(빈 배열)
function keywordRanges(flat: string, at: readonly number[], word: string): [number, number][] {
  const pieces = word.normalize("NFKC").toLowerCase().split(/\s+/).filter(Boolean);
  if (!pieces.length) return [];
  const joined = pieces.join("");
  const hit = flat.indexOf(joined);
  if (hit >= 0) return [[at[hit]!, at[hit + joined.length - 1]!]];
  const out: [number, number][] = [];
  let pos = 0;
  for (const piece of pieces) {
    const found = flat.indexOf(piece, pos);
    if (found < 0) return [];
    out.push([at[found]!, at[found + piece.length - 1]!]);
    pos = found + piece.length;
  }
  return out;
}

// 카드 제목 속 키워드 자리 — <mark> 로 감쌀 조각. 이어 붙이면 원문 그대로다. 키워드마다 처음 맞은 자리만(서버 검사와 같은
// '들어 있음' 판정), 겹치거나 맞닿은 자리는 하나로 합친다. 일치 규칙의 정본은 06c 의 frontend/tests/fixtures/term_checks.json
export function keywordSpans(title: string, keywords: readonly string[]): { text: string; mark: boolean }[] {
  const chars = [...title];
  if (!chars.length) return [];
  const { flat, at } = flatten(chars);
  const ranges = keywords.flatMap((k) => keywordRanges(flat, at, k)).sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const [start, end] of ranges) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1] + 1) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  const parts: { text: string; mark: boolean }[] = [];
  let pos = 0;
  for (const [start, end] of merged) {
    if (start > pos) parts.push({ text: chars.slice(pos, start).join(""), mark: false });
    parts.push({ text: chars.slice(start, end + 1).join(""), mark: true });
    pos = end + 1;
  }
  if (pos < chars.length) parts.push({ text: chars.slice(pos).join(""), mark: false });
  return parts;
}

// 카드를 만들 때 넘긴 키워드(card.keywords)가 지금 고른 키워드와 다른가 — 순서·띄어쓰기·대소문자는 보지 않는다.
// 06e 전 카드(keywords 없음)는 무엇으로 만들었는지 모르니 알리지 않는다
export function keywordsChanged(card: TopicCard, concepts: readonly string[]): boolean {
  if (!card.keywords) return false;
  const made = new Set(card.keywords.map(conceptKey));
  const now = new Set(concepts.map(conceptKey));
  return made.size !== now.size || [...made].some((k) => !now.has(k));
}

// 고른 키워드를 제목에 하나도 넣지 못한 카드 — 서버가 세 번 다 놓친 카드를 버리지 않고 마지막 답을 보관한다(06e 정함 17).
// 사용자가 고친 카드는 서버 검사가 고친 제목을 보지 않아 알리지 않는다
export function keywordWarning(card: TopicCard): string | null {
  const keywords = card.keywords ?? [];
  const missing = new Set(card.checks?.missing_keywords ?? []);
  if (card.edited || !keywords.length || !keywords.every((k) => missing.has(k))) return null;
  return `제목에 ${keywords.map((k) => `「${k}」`).join("·")} 없음`;
}

export interface KeywordChip {
  text: string;
  pressed: boolean;
  badge: string | null;
}

function candidateBadge(c: KeywordCandidate): string {
  if (c.source === "paper") return `논문 ${c.n}편`;
  if (c.source === "both") return `AI · 논문 ${c.n}편`;
  return "AI 후보";
}

// 키워드 칩 — 후보(최신 키워드 생성)를 낸 순서대로, 고른 것은 눌린 칩. 후보에 없는 고른 말(직접 더한 것)은 뒤에 '직접'.
// 후보가 없는 연구(06e 전·예시 연구)는 지금 고른 키워드를 눌린 칩으로만 보인다
export function keywordChips(
  candidates: readonly KeywordCandidate[] | null | undefined,
  picked: readonly string[],
): KeywordChip[] {
  if (!candidates?.length) return picked.map((text) => ({ text, pressed: true, badge: null }));
  const pickedKeys = new Set(picked.map(conceptKey));
  const shown = new Set(candidates.map((c) => conceptKey(c.text)));
  return [
    ...candidates.map((c) => ({ text: c.text, pressed: pickedKeys.has(conceptKey(c.text)), badge: candidateBadge(c) })),
    ...picked.filter((text) => !shown.has(conceptKey(text))).map((text) => ({ text, pressed: true, badge: "직접" })),
  ];
}

// 칩 하나를 누르면 — 고른 것이면 빼고, 아니면 뒤에 더한다. 고른 수는 칩 상한(CONCEPTS_MAX — 서버 PATCH 와 같다)을 넘지 않는다
export function toggleKeyword(picked: readonly string[], text: string): string[] {
  const key = conceptKey(text);
  if (picked.some((p) => conceptKey(p) === key)) return picked.filter((p) => conceptKey(p) !== key);
  if (picked.length >= CONCEPTS_MAX) return [...picked];
  return [...picked, text];
}

// [이 키워드로 다시 만들기] 를 막는 까닭 — 선행연구 묶음 수가 키워드 수 이하라 둘 이상 골라야 한다(서버도 409)
export function regenerateProblem(picked: readonly string[]): string | null {
  return picked.length < MIN_PICKED_KEYWORDS
    ? `키워드를 ${MIN_PICKED_KEYWORDS}개 이상 고르면 다시 만들 수 있습니다`
    : null;
}

// 다시 만들 AI 자리가 있는가 — 칩을 고치지 않아도 [이 키워드로 다시 만들기] 를 보일 때. ① 지금 키워드와 다른 키워드로
// 만든 AI 후보 카드(다시 만드는 중인 카드는 빼고), ② 키워드 생성이 실패해 카드가 들어가지 않은 빈 씨앗 자리(blocked —
// 키워드를 직접 넣고 [키워드만 저장] 한 뒤 카드를 받는 길. 서버 regenerate 는 카드 없는 후보 씨앗 행도 넣는다). 고른 카드·
// 고친 카드·사용자가 쓴 카드는 다시 만들지 않으므로 세지 않는다(06e 정함 16). conceptsGen 은 최신 키워드 생성(cardStatus)
export function aiCardsStale(
  topics: TopicsView,
  concepts: readonly string[],
  conceptsGen?: WorkGeneration | null,
): boolean {
  return topics.items.some((item) => {
    if (item.state === "candidate" && cardStatus(item, conceptsGen) === "blocked") return true;
    const card = cardOf(item);
    return (
      item.origin !== "user" && item.state === "candidate" && card !== null && !card.edited &&
      !remaking(item) && keywordsChanged(card, concepts)
    );
  });
}
