<!-- frontend/components/work/ConceptChips.vue -->
<template>
  <section class="wk-concepts" aria-labelledby="wk-concepts-title" :aria-busy="status === 'making'">
    <div class="wk-concepts__head">
      <h3 id="wk-concepts-title" class="wk-concepts__title">키워드</h3>
      <p v-if="note" class="rs-muted" aria-live="polite">{{ note }}</p>
    </div>
    <p v-if="editable && chips.length" id="wk-concepts-help" class="rs-muted">
      카드 제목에 넣을 키워드를 고르세요 — 고른 키워드가 하나 이상 들어간 제목으로 카드를 만듭니다.
    </p>

    <ul v-if="chips.length" class="wk-concepts__list" aria-label="키워드 후보">
      <li v-for="chip in chips" :key="chip.text">
        <button
          type="button"
          class="wk-kwchip"
          :aria-pressed="chip.pressed"
          :aria-describedby="editable ? 'wk-concepts-help' : undefined"
          :disabled="!editable || busy || (!chip.pressed && full)"
          @click="toggle(chip.text)"
        >
          <span>{{ chip.text }}</span>
          <span v-if="chip.badge" class="wk-kwchip__badge">{{ chip.badge }}</span>
        </button>
      </li>
    </ul>

    <div v-if="editable" class="wk-concepts__edit">
      <input
        v-model="input"
        class="wk-edit__input wk-concepts__input"
        type="text"
        :maxlength="CONCEPT_LEN_MAX"
        :placeholder="full ? `키워드는 ${CONCEPTS_MAX}개까지 고릅니다` : '후보에 없는 키워드 — Enter 로 더합니다'"
        aria-label="키워드 직접 더하기"
        :disabled="busy || full"
        @keydown.enter="onEnter"
      />
      <button
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="busy || full || !input.trim()"
        @click="add"
      >
        더하기
      </button>
      <button
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="busy || !dirty || !draft.length"
        @click="save"
      >
        키워드만 저장
      </button>
      <button v-if="dirty" type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="reset">
        되돌리기
      </button>
    </div>
    <div v-if="editable && (dirty || stale)" class="wk-concepts__regen">
      <button
        type="button"
        class="rs-btn rs-btn--small"
        :disabled="busy || problem !== null"
        :aria-describedby="problem ? 'wk-concepts-problem' : undefined"
        @click="regenerate"
      >
        이 키워드로 다시 만들기
      </button>
      <p v-if="problem" id="wk-concepts-problem" class="rs-muted">{{ problem }}</p>
    </div>
    <div v-if="retryable" class="rs-card__actions">
      <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="retry">다시</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { KeywordCandidate, WorkGeneration } from "~/types/work";
import {
  CONCEPTS_MAX,
  CONCEPT_LEN_MAX,
  addConcept,
  conceptsNote,
  conceptsRetryable,
  conceptsStatus,
  keywordChips,
  regenerateProblem,
  toggleKeyword,
} from "~/utils/topicDeck";

// 주제 단계 맨 위 키워드 칩(06e D23 — 06b 의 핵심 개념 칩을 후보 토글 칩으로). 후보(최신 키워드 생성)를 누르면 고르고
// 다시 누르면 뺀다. 후보에 없는 말은 직접 더한다(배지 '직접'). 고친 칩은 emit 만 하고 저장(PATCH work)·다시 만들기
// (POST topics/regenerate)는 TopicsStep 이 한다. [이 키워드로 다시 만들기] 는 고른 것이 저장된 것과 다르거나, 지금
// 키워드와 다른 키워드로 만든 AI 카드가 있을 때(stale) 보인다 — 둘 미만이면 누를 수 없고 까닭을 적는다
const props = defineProps<{
  concepts: string[];
  candidates: KeywordCandidate[] | null;
  generation: WorkGeneration | null;
  readOnly: boolean;
  busy: boolean;
  stale: boolean;
}>();
const emit = defineEmits<{ save: [concepts: string[]]; regenerate: [concepts: string[]]; retry: [genId: number] }>();

const draft = ref<string[]>([...props.concepts]);
const input = ref("");

const status = computed(() => conceptsStatus(props.concepts, props.generation));
const note = computed(() => conceptsNote(props.concepts, props.generation));
// 생성이 열려 있으면 서버 PATCH 가 409(만드는 중) — 그동안은 칩을 고치지 않는다
const editable = computed(() => !props.readOnly && status.value !== "making");
const retryable = computed(() => !props.readOnly && conceptsRetryable(props.concepts, props.generation));
const chips = computed(() => keywordChips(props.candidates, draft.value));
const full = computed(() => draft.value.length >= CONCEPTS_MAX);
const dirty = computed(() => !sameList(draft.value, props.concepts));
const problem = computed(() => regenerateProblem(draft.value));

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((c, i) => c === b[i]);
}

// 저장했거나 생성이 칩을 채우면 새 목록을 받는다 — 고치던 중(저장 전)이면 사용자가 고른 칩을 덮지 않는다
watch(
  () => props.concepts,
  (next, before) => {
    if (sameList(draft.value, before ?? [])) draft.value = [...next];
  },
);

function toggle(text: string): void {
  draft.value = toggleKeyword(draft.value, text);
}

function add(): void {
  const next = addConcept(draft.value, input.value);
  if (next === draft.value) return;
  draft.value = next;
  input.value = "";
}

// 한글 조합 중의 Enter 는 글자를 확정하는 키다 — 그때 더하면 조합 중인 글자가 빠진 채 들어간다
function onEnter(e: KeyboardEvent): void {
  if (e.isComposing) return;
  e.preventDefault();
  add();
}

function reset(): void {
  draft.value = [...props.concepts];
  input.value = "";
}

function save(): void {
  if (!dirty.value || !draft.value.length) return;
  emit("save", [...draft.value]);
}

function regenerate(): void {
  if (problem.value) return;
  emit("regenerate", [...draft.value]);
}

function retry(): void {
  if (props.generation) emit("retry", props.generation.id);
}
</script>
