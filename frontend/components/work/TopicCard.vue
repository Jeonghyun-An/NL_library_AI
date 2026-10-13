<!-- frontend/components/work/TopicCard.vue -->
<template>
  <article
    ref="rootEl"
    class="wk-topic"
    :class="[`wk-topic--${status}`, { 'wk-topic--picked': picked, 'wk-topic--arrived': arrived }]"
    :aria-busy="pending"
    :aria-labelledby="card && !editing ? titleId : undefined"
    @animationend.self="arrived = false"
  >
    <p v-if="origin" class="wk-topic__origin">{{ origin }}</p>

    <form v-if="editing" class="wk-edit" @submit.prevent="submitEdit">
      <label class="wk-edit__field">
        <span class="wk-edit__label">제목</span>
        <input v-model="draftTitle" data-edit-box class="wk-edit__input" type="text" :maxlength="TOPIC_TITLE_MAX" />
      </label>
      <label class="wk-edit__field">
        <span class="wk-edit__label">연구 질문</span>
        <textarea v-model="draftQuestion" class="wk-edit__input" rows="3" :maxlength="TOPIC_QUESTION_MAX" />
      </label>
      <p v-if="problem" class="wk-edit__problem" role="alert">{{ problem }}</p>
      <div class="rs-card__actions">
        <button type="submit" class="rs-btn rs-btn--small" :disabled="busy">저장</button>
        <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="editing = false">
          취소
        </button>
      </div>
    </form>

    <template v-else-if="card">
      <!-- 고른 키워드가 든 자리는 <mark> — 서버 제목 검사와 같은 일치 규칙(keywordSpans, 06e D23) -->
      <h3 :id="titleId" class="wk-topic__title">
        <template v-for="(part, i) in titleParts" :key="i">
          <mark v-if="part.mark" class="wk-kw">{{ part.text }}</mark>
          <template v-else>{{ part.text }}</template>
        </template>
      </h3>
      <p v-if="kwWarning" class="wk-topic__kwwarn">{{ kwWarning }}</p>
      <p class="wk-topic__question">{{ card.question }}</p>
      <p v-if="kwChanged" class="wk-topic__kwchanged">키워드가 바뀌었습니다</p>
      <p v-if="remakingNote" class="wk-topic__note">{{ remakingNote }}</p>
      <ul v-if="chips.length" class="wk-topic__chips" aria-label="근거 논문">
        <li v-for="chip in chips" :key="chip.cntsId">
          <span class="wk-topic__chip" :title="chip.title">{{ chip.label }}</span>
        </li>
      </ul>
      <p v-if="figurePieces.length" class="wk-topic__figures">
        <template v-for="(piece, i) in figurePieces" :key="i">
          <FigureChip v-if="piece.figure" :figure="piece.figure" />
          <template v-else>{{ piece.text }}</template>
        </template>
      </p>
      <p v-if="card.latest_year !== null" class="rs-muted">근거 중 최신 {{ card.latest_year }}년</p>
      <p v-if="numbersLine" class="wk-topic__check">
        <span class="wk-psec__check" title="[F#] 밖에서 쓴 숫자 — 원문과 맞는지 확인하세요">{{ numbersLine }}</span>
      </p>
    </template>

    <template v-else>
      <div v-if="pending" class="rs-skeleton" aria-hidden="true">
        <span class="rs-skeleton__line" />
        <span class="rs-skeleton__line" />
        <span class="rs-skeleton__line" />
      </div>
      <p v-else-if="seedText" class="wk-topic__seed">{{ seedText }}</p>
      <p class="wk-topic__note" :aria-live="pending ? 'polite' : undefined">{{ note }}</p>
    </template>

    <div v-if="!editing && !pending" class="rs-card__actions">
      <span v-if="picked" class="rs-badge rs-badge--done">고른 주제</span>
      <button
        v-else-if="card"
        type="button"
        class="rs-btn rs-btn--small"
        :disabled="readOnly || busy || !pickable"
        @click="emit('pick')"
      >
        고르기<span v-if="cardName" class="rs-sr-only"> {{ cardName }}</span>
      </button>
      <button
        v-if="retryId !== null"
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="readOnly || busy"
        @click="onRetry"
      >
        다시<span v-if="cardName" class="rs-sr-only"> {{ cardName }}</span>
      </button>
      <button
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="readOnly || busy || remakingNote !== null"
        data-edit-open
        @click="startEdit"
      >
        직접 고치기<span v-if="cardName" class="rs-sr-only"> {{ cardName }}</span>
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import FigureChip from "~/components/work/FigureChip.vue";
import type { Figure, PaperMeta, TopicItem, TopicPatch, WorkGeneration } from "~/types/work";
import { figureById, splitMarkers } from "~/utils/figureMarkers";
import {
  TOPIC_QUESTION_MAX,
  TOPIC_TITLE_MAX,
  canPick,
  cardArrived,
  cardNote,
  cardNumbersLine,
  cardRemakingNote,
  cardStatus,
  evidenceChips,
  keywordSpans,
  keywordWarning,
  keywordsChanged,
  seedLine,
  topicProblem,
} from "~/utils/topicDeck";

// 주제 카드 한 장(spec §4 S3·§5-2). 의도만 emit 하고 API(고르기·고치기·다시)는 TopicsStep 이 부른다
// concepts·conceptsGen — 지금 고른 키워드와 그 생성(06e D23). 빈 씨앗 자리는 키워드가 정해지기를 기다린다(cardStatus)
const props = defineProps<{
  item: TopicItem;
  papers: Record<string, PaperMeta>;
  picked: boolean;
  readOnly: boolean;
  busy: boolean;
  concepts: string[];
  conceptsGen: WorkGeneration | null;
}>();
const emit = defineEmits<{ pick: []; edit: [body: TopicPatch]; retry: [genId: number]; arrived: [el: HTMLElement] }>();

const status = computed(() => cardStatus(props.item, props.conceptsGen));
const pending = computed(() => status.value === "waiting" || status.value === "making");
const card = computed(() => (status.value === "ready" ? props.item.card : null));
const note = computed(() => cardNote(status.value));
const pickable = computed(() => canPick(props.item));
const chips = computed(() => (card.value ? evidenceChips(card.value, props.papers) : []));
// 제목·질문에 [F#] 밖 숫자가 있으면 '확인 필요' — 서버가 센 값(card.checks.numbers)을 계획서 문단과 같은 모양으로 보인다
const numbersLine = computed(() => (card.value ? cardNumbersLine(card.value) : null));
// 제목 속 고른 키워드(카드를 만들 때 넘긴 키워드), 하나도 못 넣은 카드의 경고, 지금 고른 키워드와 다른 키워드로 만든 카드.
// '바뀌었습니다'는 다시 만들 대상(고르지 않은·고치지 않은 AI 카드)에만 단다 — 고른 카드는 다시 만들지 않는다(06e 정함 16)
const titleParts = computed(() => (card.value ? keywordSpans(card.value.title, card.value.keywords ?? []) : []));
const kwWarning = computed(() => (card.value ? keywordWarning(card.value) : null));
// [이 키워드로 다시 만들기] 가 넣은 새 카드를 기다리는 중 — 새 결과가 반영될 때까지 지금 카드를 그대로 보이고 [고르기]
// (canPick)·[직접 고치기](서버 409 CARD_BUSY)는 막는다. 그동안은 '바뀌었습니다'를 달지 않는다(06e 정함 16)
const remakingNote = computed(() => cardRemakingNote(props.item));
const kwChanged = computed(
  () =>
    card.value !== null &&
    remakingNote.value === null &&
    !props.picked &&
    props.item.origin !== "user" &&
    !card.value.edited &&
    keywordsChanged(card.value, props.concepts),
);
// 머리 줄은 보고서 씨앗 카드의 계보뿐이다 — 사용자 카드(seed 가 {} → null)·고친 카드에는 출처 표시를 달지 않는다(D7·D9)
const origin = computed(() => seedLine(props.item.seed));
const seedText = computed(() => props.item.seed?.text.trim() || null);
const titleId = computed(() => `wk-topic-title-${props.item.id}`);
// 카드마다 되풀이되는 버튼([고르기]·[다시]·[직접 고치기])의 이름에 붙이는 대상 — 화면에는 보이지 않는다. 카드 제목,
// 카드가 없는 슬롯(근거 부족·실패)은 씨앗 글. 스크린리더의 컨트롤 목록에서 어느 카드의 버튼인지 구별되게
const cardName = computed(() => {
  const name = card.value?.title.trim() || seedText.value;
  return name ? `「${name}」` : null;
});
// 근거 부족·실패 슬롯의 [다시] — 그 주제의 마지막 카드 생성을 다시 부른다(서버 _retryable 의 범위)
const retryId = computed(() =>
  (status.value === "insufficient" || status.value === "failed") && props.item.generation
    ? props.item.generation.id
    : null,
);

// 수치 문장은 코드가 [F#] 를 넣어 만든 틀이다(06b 정함 3) — [F#] 는 수치 칩으로, 혹시 남은 [E#] 는 글자 그대로 둔다
const figurePieces = computed<{ text: string; figure: Figure | null }[]>(() => {
  const c = card.value;
  if (!c?.figure_sentence) return [];
  return splitMarkers(c.figure_sentence).map((part) => {
    if (part.type === "text") return { text: part.text, figure: null };
    if (part.type === "cite") return { text: `[${part.eid}]`, figure: null };
    const figure = figureById(c.figures, part.fid);
    return figure ? { text: "", figure } : { text: `[${part.fid}]`, figure: null };
  });
});

// 카드는 기다리던 슬롯에 실제로 도착했을 때만 한 번 뒤집는다 — 처음 그릴 때(watch 는 바뀔 때만 돈다)·직접 채운 카드는 그대로.
// 도착한 카드 요소를 위로 올린다 — 화면 밖이면 TopicsStep 이 '새 후보 N ↓' 알약만 띄운다(이 부품은 스크롤하지 않는다)
const rootEl = ref<HTMLElement | null>(null);
const arrived = ref(false);
watch(status, (now, before) => {
  if (!cardArrived(before, now)) return;
  arrived.value = true;
  if (rootEl.value) emit("arrived", rootEl.value);
});

const editing = ref(false);
const draftTitle = ref("");
const draftQuestion = ref("");
const problem = ref<string | null>(null);

// 열면 제목 칸으로, 닫으면 [직접 고치기]로 포커스를 옮긴다 — 여는 버튼과 칸이 v-if 로 번갈아 사라져 그대로 두면
// 포커스가 body 로 떨어진다(운영 확인 2026-10-08)
watch(editing, (now) => {
  void nextTick(() => rootEl.value?.querySelector<HTMLElement>(now ? "[data-edit-box]" : "[data-edit-open]")?.focus());
});

function startEdit(): void {
  draftTitle.value = props.item.card?.title ?? "";
  draftQuestion.value = props.item.card?.question ?? "";
  problem.value = null;
  editing.value = true;
}

// 바뀐 칸만 보낸다. 빈 슬롯(근거 부족·실패)은 두 칸을 다 보내 카드를 만든다(서버 PATCH .../topics/{tid})
function submitEdit(): void {
  const title = draftTitle.value.trim();
  const question = draftQuestion.value.trim();
  problem.value = topicProblem({ title, question });
  if (problem.value) return;
  const current = card.value;
  const body: TopicPatch = {};
  if (title !== current?.title) body.title = title;
  if (question !== current?.question) body.question = question;
  if (body.title === undefined && body.question === undefined) {
    editing.value = false;
    return;
  }
  emit("edit", body);
}

// 저장이 반영돼 카드 글이 바뀌면 편집을 닫는다 — 실패(409 등)면 열어 둔 채 쓴 글을 지킨다.
// 열쇠를 문자열로 만들어 다른 카드 때문에 목록을 다시 읽어도(새 객체) 닫히지 않게 한다
watch(
  () => `${props.item.card?.title ?? ""}\u0000${props.item.card?.question ?? ""}`,
  () => {
    editing.value = false;
  },
);

function onRetry(): void {
  if (retryId.value !== null) emit("retry", retryId.value);
}
</script>
