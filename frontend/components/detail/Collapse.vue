<template>
  <!-- 접고 펴는 구획 — 제목 줄 전체가 버튼이다(오른쪽 ˄ 접기 / ˅ 펼치기). 접힌 본문은 그리지 않는다 -->
  <section class="dt-section dt-collapse">
    <h2 class="dt-collapse__head">
      <button
        type="button"
        class="dt-collapse__btn"
        :aria-expanded="open"
        :aria-controls="open ? bodyId : undefined"
        @click="emit('update:open', !open)"
      >
        <span>{{ title }}</span>
        <span class="skx-sr-only">{{ open ? " 접기" : " 펼치기" }}</span>
        <svg class="dt-collapse__chev" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M5 15l7-7 7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    </h2>
    <div v-if="open" :id="bodyId" class="dt-collapse__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ title: string; open: boolean }>();
const emit = defineEmits<{ "update:open": [open: boolean] }>();
const bodyId = `dt-collapse-${useId()}`;
</script>
