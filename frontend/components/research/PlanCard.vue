<!-- frontend/components/research/PlanCard.vue -->
<template>
  <section class="rs-card rs-plan" :aria-busy="busy">
    <header class="rs-card__head">
      <h2 class="rs-card__title">{{ editable ? "연구 계획 확인" : "연구 계획" }}</h2>
      <p v-if="questionUsed" class="rs-muted rs-plan__understood">{{ understoodLine(questionUsed) }}</p>
      <p v-if="editable" class="rs-muted">하위질문을 고치거나 지우고 더할 수 있습니다. 최대 {{ max }}개까지입니다.</p>
    </header>

    <ol v-if="editable" ref="list" class="rs-plan__list">
      <li v-for="(_, i) in items" :key="keys[i]" class="rs-plan__item">
        <span class="rs-plan__no">{{ i + 1 }}</span>
        <input
          v-model="items[i]"
          class="rs-plan__input"
          type="text"
          :maxlength="PLAN_ITEM_MAX"
          :aria-label="`하위질문 ${i + 1}`"
          :disabled="busy"
        />
        <button
          type="button"
          class="rs-icon-btn"
          :aria-label="`하위질문 ${i + 1} 삭제`"
          :disabled="busy || items.length <= 1"
          @click="remove(i)"
        >
          ×
        </button>
      </li>
    </ol>
    <ol v-else class="rs-plan__list">
      <li v-for="sq in subqs" :key="sq.idx" class="rs-plan__item" :class="`is-${sq.status}`">
        <span class="rs-plan__no">{{ sq.idx + 1 }}</span>
        <span class="rs-plan__text">{{ sq.title }}</span>
        <span class="rs-badge" :class="`rs-badge--${sq.status}`">{{ subqStatusLabel(sq) }}</span>
      </li>
    </ol>

    <template v-if="editable">
      <button type="button" class="rs-btn rs-btn--ghost rs-plan__add" :disabled="busy || items.length >= max" @click="add">
        + 하위질문 추가
      </button>
      <!-- 서버가 422 로 거절하기 전에 화면이 먼저 막는 계획 편집값 오류 — [승인하고 시작]이 잠긴 까닭을 줄 안내로 -->
      <SkxInlineError v-if="problem" :message="problem" />
      <div class="rs-card__actions">
        <button type="button" class="rs-btn" :disabled="busy || !!problem" @click="approve">승인하고 시작</button>
        <!-- 취소는 화면 안 한 번 확인('정말 취소' + [그대로 두기]) — 메인 입력창의 연구 줄과 같다 -->
        <CancelConfirm :disabled="busy" @confirm="$emit('cancel')" />
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import CancelConfirm from "~/components/research/CancelConfirm.vue";
import type { SubqView } from "~/types/research";
import { subqStatusLabel, understoodLine } from "~/utils/researchEvents";
import { PLAN_ITEM_MAX, planProblem } from "~/utils/researchInput";

// questionUsed — 계획이 쓴 넓힌 질문(06c). 원 질문과 같으면 null 로 받는다(판단은 questionUsedFromSteps)
const props = withDefaults(
  defineProps<{
    plan: string[];
    max: number;
    editable?: boolean;
    busy?: boolean;
    subqs?: SubqView[];
    questionUsed?: string | null;
  }>(),
  { editable: false, busy: false, subqs: () => [], questionUsed: null },
);
const emit = defineEmits<{ approve: [plan: string[]]; cancel: [] }>();

const list = ref<HTMLOListElement | null>(null);
const items = ref<string[]>([]);
// 항목을 지우면 뒤 항목의 입력칸이 앞 항목의 글을 물려받지 않게 항목마다 고정 키를 준다
const keys = ref<number[]>([]);
let nextKey = 0;
let received: string[] = [];

const problem = computed(() => planProblem(items.value, props.max));

// snapshot 이 같은 계획을 새 배열로 다시 보내도 사용자가 고치던 내용을 덮지 않는다
watch(
  () => props.plan,
  (plan) => {
    if (plan.length === received.length && plan.every((t, i) => t === received[i])) return;
    received = [...plan];
    items.value = [...plan];
    keys.value = plan.map(() => nextKey++);
  },
  { immediate: true },
);

function remove(i: number): void {
  items.value.splice(i, 1);
  keys.value.splice(i, 1);
}

async function add(): Promise<void> {
  items.value.push("");
  keys.value.push(nextKey++);
  await nextTick();
  const inputs = list.value?.querySelectorAll<HTMLInputElement>("input");
  inputs?.[inputs.length - 1]?.focus();
}

function approve(): void {
  if (problem.value) return;
  emit("approve", items.value.map((t) => t.trim()));
}
</script>
