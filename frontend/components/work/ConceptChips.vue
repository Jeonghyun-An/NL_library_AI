<!-- frontend/components/work/ConceptChips.vue -->
<template>
  <section class="wk-concepts" aria-labelledby="wk-concepts-title" :aria-busy="status === 'making'">
    <div class="wk-concepts__head">
      <!-- tabindex="-1" — 다시 만들기 줄처럼 초점이 있던 버튼이 사라지면 이 제목으로 옮긴다 -->
      <h3 id="wk-concepts-title" ref="titleEl" class="wk-concepts__title" tabindex="-1">키워드</h3>
      <p v-if="note && !failed" class="rs-muted" aria-live="polite">{{ note }}</p>
    </div>
    <!-- 키워드 생성 실패 — 공통 줄 안내로, [다시] 는 그 안에(예시 연구는 누를 수 없어 글만) -->
    <SkxInlineError
      v-if="failed && note"
      :message="note"
      retry-label="다시"
      :busy="busy"
      :on-retry="retryable ? retry : undefined"
    />
    <p v-if="editable && chips.length" id="wk-concepts-help" class="rs-muted">
      카드 제목에 넣을 키워드를 고르세요 — 고른 키워드가 하나 이상 들어간 제목으로 카드를 만듭니다.
    </p>

    <ul v-if="chips.length" ref="listEl" class="wk-concepts__list" aria-label="키워드 후보">
      <li v-for="chip in chips" :key="chip.text">
        <button
          type="button"
          class="wk-kwchip"
          :data-chip="chip.text"
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
        ref="inputEl"
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
    <div v-if="showRegen" ref="regenEl" class="wk-concepts__regen">
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
    <div v-if="retryable && !failed" class="rs-card__actions">
      <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="retry">다시</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import type { KeywordCandidate, WorkGeneration } from "~/types/work";
import {
  CONCEPTS_MAX,
  CONCEPT_LEN_MAX,
  addConcept,
  chipFocusAfterToggle,
  conceptsNote,
  conceptsRetryable,
  conceptsStatus,
  keywordChips,
  regenerateFocusMoves,
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
// 키워드를 뽑지 못했다(생성 실패·취소) — 안내를 공통 줄 안내(SkxInlineError)로 보이고 [다시] 를 그 안에 둔다
const failed = computed(() => status.value === "failed");
const chips = computed(() => keywordChips(props.candidates, draft.value));
const full = computed(() => draft.value.length >= CONCEPTS_MAX);
const dirty = computed(() => !sameList(draft.value, props.concepts));
const problem = computed(() => regenerateProblem(draft.value));
const showRegen = computed(() => editable.value && (dirty.value || props.stale));

const titleEl = ref<HTMLElement | null>(null);
const listEl = ref<HTMLElement | null>(null);
const inputEl = ref<HTMLInputElement | null>(null);
const regenEl = ref<HTMLElement | null>(null);

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

// 누른 버튼이 v-if 로 사라지면 초점이 body 로 떨어진다(TopicCard [직접 고치기] 와 같은 문제 — 운영 확인 2026-10-08).
// 그리고 난 뒤 살아 있는(막히지 않은) 곳으로 옮긴다 — 받은 칩, 없으면 직접 더하기 칸, 그것도 막혔으면 키워드 제목
function focusAfterGone(chip: string | null): void {
  const chipEl =
    chip === null
      ? undefined
      : Array.from(listEl.value?.querySelectorAll<HTMLButtonElement>("button[data-chip]") ?? []).find(
          (b) => b.dataset.chip === chip && !b.disabled,
        );
  const field = inputEl.value && !inputEl.value.disabled ? inputEl.value : null;
  (chipEl ?? field ?? titleEl.value)?.focus();
}

// 칩을 빼면 그 칩이 사라지는 때가 있다(후보 없는 연구의 칩·'직접' 칩) — 그 자리 다음 칩이나 직접 더하기 칸으로
function toggle(text: string): void {
  const before = chips.value;
  draft.value = toggleKeyword(draft.value, text);
  const next = chipFocusAfterToggle(before, chips.value, text);
  if (next !== text) void nextTick(() => focusAfterGone(next));
}

// [이 키워드로 다시 만들기] 가 성공하면 줄이 통째로 사라진다 — 그 줄에 있던 초점을 키워드 제목으로(regenerateFocusMoves).
// 부르는 동안 버튼이 막혀 브라우저가 초점을 이미 놓았을 수 있어 누른 것을 기억하고, 줄이 남은 채 끝나면(409 등) 잊는다.
// 줄 안의 초점은 그리기 전(이 watch 는 pre)에 보고, 옮기기는 그린 뒤 초점을 잃었을 때만 — 다른 곳으로 간 초점은 빼앗지 않는다
let regenAsked = false;
watch([showRegen, () => props.busy], ([shown, busy], [wasShown]) => {
  const focusInside = regenEl.value?.contains(document.activeElement) ?? false;
  if (regenerateFocusMoves({ wasShown, shown, asked: regenAsked, focusInside })) {
    void nextTick(() => {
      const active = document.activeElement;
      if (!active || active === document.body) titleEl.value?.focus();
    });
  }
  if (!shown || !busy) regenAsked = false;
});

// 실패 안내의 [다시] 를 누르면 생성이 다시 열려 안내가 버튼째 사라진다 — 그린 뒤 초점을 잃었을 때만 키워드 제목으로
watch(failed, (now, was) => {
  if (now || !was) return;
  void nextTick(() => {
    const active = document.activeElement;
    if (!active || active === document.body) titleEl.value?.focus();
  });
});

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

// [되돌리기] 는 고친 것이 있을 때만 보여 누르면 사라진다 — 저장된 키워드로 돌아간 이 묶음의 제목으로 초점을 옮긴다
// (입력 칸으로 보내면 휴대폰에서 고치지도 않을 자판이 올라온다)
function reset(): void {
  draft.value = [...props.concepts];
  input.value = "";
  void nextTick(() => titleEl.value?.focus());
}

function save(): void {
  if (!dirty.value || !draft.value.length) return;
  emit("save", [...draft.value]);
}

function regenerate(): void {
  if (problem.value) return;
  regenAsked = true;
  emit("regenerate", [...draft.value]);
}

function retry(): void {
  if (props.generation) emit("retry", props.generation.id);
}
</script>
