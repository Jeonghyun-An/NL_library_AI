<!-- frontend/components/work/ReadingNextActions.vue -->
<template>
  <div>
    <!-- 참고문헌 선택하기의 다음 단계 버튼 묶음 — ReadingStep 이 머리(소개 옆)와 표 아래 두 곳에 쓴다(사용자 요청 2026-10-13).
         두 곳은 같은 상태를 받아 같은 버튼·같은 비활성 조건·같은 문구다. 누르면 go·make 를 올려 보내기만 하고 저장·목차 생성과
         그 잠금은 ReadingStep 한 곳에 있어 위·아래를 번갈아 눌러도 한 번만 만든다. 비활성 까닭(hint)은 버튼 곁에 보이고
         aria-describedby 로 잇는다 — id 는 자리(where)마다 달라 두 묶음이 같은 id 를 갖지 않는다. 읽기 전용으로 꺼진 버튼은
         화면 머리의 읽기 전용 줄(disabledWhyId)도 함께 잇는다 -->
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
      <!-- 누르면 바로 만들지 않고 ReadingStep 이 이 묶음 아래에 확인 칸을 편다 — 펴진 동안 aria-expanded, 접히면 이 id 로 초점이 돌아온다 -->
      <button
        :id="remakeId"
        type="button"
        class="rs-btn rs-btn--ghost"
        :disabled="makeDisabled"
        :aria-describedby="makeDescribedBy"
        :aria-expanded="remakeOpen"
        @click="emit('make', true, where)"
      >
        {{ REMAKE_REPORT }}
      </button>
    </template>
    <button
      v-else
      type="button"
      class="rs-btn"
      :disabled="makeDisabled"
      :aria-describedby="makeDescribedBy"
      @click="emit('make', false, where)"
    >
      {{ MAKE_REPORT }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { WorkStep } from "~/types/work";
import { describedByIds, remakeButtonId } from "~/utils/readingList";
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
  // hint 밖에서 [보고서 만들기]·[보고서 다시 만들기] 를 끄는 까닭이 화면에 보이는 줄의 id(읽기 전용 줄) — 없으면 null.
  // 두 묶음이 같은 한 줄을 가리킨다(id 를 새로 만들지 않아 겹치지 않는다)
  disabledWhyId: string | null;
  // [보고서 다시 만들기] 확인 칸이 이 묶음 아래에 펴져 있다 — 그 버튼의 aria-expanded
  remakeOpen?: boolean;
}>();
// make — 누른 버튼(again: [보고서 다시 만들기])과 그 묶음의 자리(where — ReadingStep 이 확인 칸을 그 묶음 아래에 편다)
const emit = defineEmits<{ go: [step: WorkStep]; make: [again: boolean, where: "top" | "bottom"] }>();

const hintId = computed(() => `wk-reading-next-hint-${props.where}`);
// [제목 고르기] — 끄지 않는 버튼이라 '주제를 먼저 고르세요'(hint)만 잇는다
const describedBy = computed(() => describedByIds(props.hint ? hintId.value : null));
// [보고서 만들기]·[보고서 다시 만들기] — 만들 수 없는 까닭(hint)과 읽기 전용 줄을 함께 잇는다
const makeDescribedBy = computed(() => describedByIds(props.hint ? hintId.value : null, props.disabledWhyId));
const remakeId = computed(() => remakeButtonId(props.where));
</script>
