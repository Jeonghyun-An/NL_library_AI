<!-- frontend/components/work/ReadingNextActions.vue -->
<template>
  <div>
    <!-- 참고문헌 선택하기의 다음 단계 버튼 묶음 — ReadingStep 이 머리(소개 옆)와 표 아래 두 곳에 쓴다(사용자 요청 2026-10-13).
         두 곳은 같은 상태를 받아 같은 버튼·같은 비활성 조건·같은 문구다. 누르면 go·make 를 올려 보내기만 하고 저장·목차 생성과
         그 잠금은 ReadingStep 한 곳에 있어 위·아래를 번갈아 눌러도 한 번만 만든다. 비활성 까닭(hint)은 버튼 곁에 보이고
         aria-describedby 로 잇는다 — id 는 자리(where)마다 달라 두 묶음이 같은 id 를 갖지 않는다 -->
    <p v-if="hint" :id="hintId" class="rs-muted">{{ hint }}</p>
    <button
      v-if="noTopic"
      type="button"
      class="rs-btn rs-btn--ghost"
      :aria-describedby="describedBy"
      @click="emit('go', 'topics')"
    >
      제목 고르기
    </button>
    <template v-else-if="outlineMade">
      <button type="button" class="rs-btn" @click="emit('go', 'proposal')">{{ FINAL_STEP_NAME }} 단계로</button>
      <button
        type="button"
        class="rs-btn rs-btn--ghost"
        :disabled="makeDisabled"
        :aria-describedby="describedBy"
        @click="emit('make', true)"
      >
        {{ REMAKE_REPORT }}
      </button>
    </template>
    <button
      v-else
      type="button"
      class="rs-btn"
      :disabled="makeDisabled"
      :aria-describedby="describedBy"
      @click="emit('make', false)"
    >
      {{ MAKE_REPORT }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { WorkStep } from "~/types/work";
import { FINAL_STEP_NAME, MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";

const props = defineProps<{
  // 머리(소개 옆)인지 표 아래인지 — 까닭 줄의 id 를 나눈다
  where: "top" | "bottom";
  // 고른 주제가 없다 — [제목 고르기] 만 둔다
  noTopic: boolean;
  // 목차를 이미 만들었다(phase proposal·done) — [보고서 단계로] + [보고서 다시 만들기]
  outlineMade: boolean;
  // [보고서 만들기]·[보고서 다시 만들기] 를 끈다 — 읽기 전용·저장 중·만들 수 없음(ReadingStep 이 한 번 계산한다)
  makeDisabled: boolean;
  // 만들 수 없는 까닭(readingList.outlineHint) — 없으면 null
  hint: string | null;
}>();
const emit = defineEmits<{ go: [step: WorkStep]; make: [again: boolean] }>();

const hintId = computed(() => `wk-reading-next-hint-${props.where}`);
const describedBy = computed(() => (props.hint ? hintId.value : undefined));
</script>
