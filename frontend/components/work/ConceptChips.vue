<!-- frontend/components/work/ConceptChips.vue -->
<template>
  <section class="wk-concepts" aria-labelledby="wk-concepts-title" :aria-busy="status === 'making'">
    <div class="wk-concepts__head">
      <h3 id="wk-concepts-title" class="wk-concepts__title">핵심 개념</h3>
      <p v-if="note" class="rs-muted" aria-live="polite">{{ note }}</p>
    </div>

    <ul v-if="draft.length" class="wk-concepts__list">
      <li v-for="(concept, i) in draft" :key="concept" class="wk-concept">
        <span>{{ concept }}</span>
        <button
          v-if="editable"
          type="button"
          class="wk-concept__remove"
          :aria-label="`핵심 개념 ${concept} 빼기`"
          :disabled="busy"
          @click="remove(i)"
        >
          ×
        </button>
      </li>
    </ul>

    <div v-if="editable" class="wk-concepts__edit">
      <input
        v-model="input"
        class="wk-edit__input wk-concepts__input"
        type="text"
        :maxlength="CONCEPT_LEN_MAX"
        :placeholder="full ? `핵심 개념은 ${CONCEPTS_MAX}개까지입니다` : '핵심 개념 넣기 — Enter 로 더합니다'"
        aria-label="핵심 개념 넣기"
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
      <button type="button" class="rs-btn rs-btn--small" :disabled="busy || !dirty || !draft.length" @click="save">
        저장
      </button>
      <button v-if="dirty" type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="reset">
        되돌리기
      </button>
    </div>
    <div v-if="retryable" class="rs-card__actions">
      <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="retry">다시</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { WorkGeneration } from "~/types/work";
import {
  CONCEPTS_MAX,
  CONCEPT_LEN_MAX,
  addConcept,
  conceptsNote,
  conceptsRetryable,
  conceptsStatus,
} from "~/utils/topicDeck";

// 주제 단계 맨 위 핵심 개념 칩(spec §5-2). 고친 칩은 [저장] 으로 emit 만 하고 저장(PATCH work)은 TopicsStep 이 한다
const props = defineProps<{ concepts: string[]; generation: WorkGeneration | null; readOnly: boolean; busy: boolean }>();
const emit = defineEmits<{ save: [concepts: string[]]; retry: [genId: number] }>();

const draft = ref<string[]>([...props.concepts]);
const input = ref("");

const status = computed(() => conceptsStatus(props.concepts, props.generation));
const note = computed(() => conceptsNote(props.concepts, props.generation));
// 생성이 열려 있으면 서버 PATCH 가 409(만드는 중) — 그동안은 칩을 고치지 않는다
const editable = computed(() => !props.readOnly && status.value !== "making");
const retryable = computed(() => !props.readOnly && conceptsRetryable(props.concepts, props.generation));
const full = computed(() => draft.value.length >= CONCEPTS_MAX);
const dirty = computed(() => !sameList(draft.value, props.concepts));

function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((c, i) => c === b[i]);
}

// 저장했거나 생성이 칩을 채우면 새 목록을 받는다 — 고치던 중(저장 전)이면 사용자가 쓴 칩을 덮지 않는다
watch(
  () => props.concepts,
  (next, before) => {
    if (sameList(draft.value, before ?? [])) draft.value = [...next];
  },
);

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

function remove(i: number): void {
  draft.value = draft.value.filter((_, j) => j !== i);
}

function reset(): void {
  draft.value = [...props.concepts];
  input.value = "";
}

function save(): void {
  if (!dirty.value || !draft.value.length) return;
  emit("save", [...draft.value]);
}

function retry(): void {
  if (props.generation) emit("retry", props.generation.id);
}
</script>
