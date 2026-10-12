<template>
  <div class="skx-rhead">
    <p class="skx-rhead__count">
      {{ prefix }}총 <strong>{{ count.toLocaleString("ko-KR") }}</strong> 건
    </p>
    <div v-if="$slots.default" class="skx-rhead__right"><slot /></div>
  </div>
</template>

<script setup lang="ts">
// 결과 목록 머리 — 왼쪽 '총 N 건'(숫자만 포인트색), 오른쪽 정렬·개수 같은 조작은 슬롯으로 받는다.
// prefix 는 목록에서 빠진 것이 있을 때('그 외 ') 건수가 목록의 카드 수와 맞게 붙인다
withDefaults(defineProps<{ count: number; prefix?: string }>(), { prefix: "" });
</script>
