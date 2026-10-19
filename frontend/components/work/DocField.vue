<!-- frontend/components/work/DocField.vue -->
<!-- 보고서 문서의 사용자 칸(2 연구 배경·6 방법, round06e) — 보기 ↔ [고치기] 편집. 저장은 부르는 쪽(ProposalStep)이
     PUT /outline 으로 하고, 결과가 오면(busy 가 풀리고 값이 보낸 글과 같거나, 저장 응답을 받았다는 savedSeq 가 올랐으면) 칸을
     닫고 [고치기]로 초점을 돌린다 -->
<template>
  <div class="wk-docfield">
    <template v-if="editing">
      <label :for="`${fieldId}-text`" class="rs-sr-only">{{ label }} 고치기</label>
      <textarea
        :id="`${fieldId}-text`"
        ref="boxEl"
        v-model="text"
        class="wk-docfield__text"
        rows="5"
        :placeholder="placeholder"
        :disabled="busy"
        :aria-describedby="`${fieldId}-count`"
        @keydown.esc.prevent="cancel"
      />
      <p :id="`${fieldId}-count`" class="wk-docfield__count" :class="{ 'is-over': left < 0 }">
        {{ left < 0 ? `${max}자까지 쓸 수 있어요 — ${-left}자를 줄여 주세요` : `${left}자 남음` }}
      </p>
      <div class="rs-card__actions">
        <button type="button" class="rs-btn rs-btn--small" :disabled="busy || left < 0" @click="save">저장</button>
        <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="cancel">그만두기</button>
      </div>
    </template>
    <template v-else>
      <p v-for="(line, i) in lines" :key="i" class="wk-docfield__line">{{ line }}</p>
      <p v-if="!lines.length" class="rs-muted">아직 적지 않았어요.</p>
      <div v-if="!readOnly" class="rs-card__actions">
        <button ref="editEl" type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="open">
          {{ lines.length ? "고치기" : "적기" }}<span class="rs-sr-only"> {{ label }}</span>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

const props = defineProps<{
  fieldId: string;
  label: string;
  value: string;
  max: number;
  placeholder: string;
  // 예시 연구는 보기만 — 쓰기 API 가 409 로 막는다
  readOnly: boolean;
  busy: boolean;
  // 저장 응답을 받을 때마다 오르는 수(ProposalStep) — 뒤의 다시 읽기가 실패해 값이 그대로여도 저장은 된 것이라 칸을 닫는다
  savedSeq?: number;
}>();
const emit = defineEmits<{ save: [text: string] }>();

const editing = ref(false);
const text = ref("");
const boxEl = ref<HTMLTextAreaElement | null>(null);
const editEl = ref<HTMLButtonElement | null>(null);
// 보낸 글 — 저장이 끝났는지(busy 가 풀린 뒤 값이 이 글과 같은지, 또는 보낸 뒤 savedSeq 가 올랐는지)로 칸을 닫는다.
// 실패하면 칸과 글이 그대로 남는다
let pending: string | null = null;
let pendingSeq = 0;

// 사용자가 줄을 나눠 적을 수 있다 — 보기에서는 줄마다 문단(Word 의 2절·6절과 같은 나눔)
const lines = computed(() =>
  props.value
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean),
);
// 서버 상한은 앞뒤 공백을 뗀 글의 코드 포인트 수(파이썬 len)로 본다 — fieldPut 이 떼고 보낸다
const left = computed(() => props.max - Array.from(text.value.trim()).length);

function open(): void {
  text.value = props.value;
  editing.value = true;
  void nextTick(() => boxEl.value?.focus());
}

function close(): void {
  editing.value = false;
  pending = null;
  void nextTick(() => editEl.value?.focus());
}

function cancel(): void {
  if (!props.busy) close();
}

function save(): void {
  const next = text.value.trim();
  if (next === props.value.trim()) {
    close();
    return;
  }
  pending = next;
  pendingSeq = props.savedSeq ?? 0;
  emit("save", next);
}

watch(
  () => props.busy,
  (now, was) => {
    if (!was || now || pending === null) return;
    if (props.value.trim() === pending || (props.savedSeq ?? 0) !== pendingSeq) close();
    else pending = null;
  },
);
</script>
