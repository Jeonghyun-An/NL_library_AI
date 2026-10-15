<template>
  <!-- 결과 목록 아래의 쪽 이동 — 한 쪽뿐이면 그리지 않는다. 논문·소장자료 결과가 같이 쓴다 -->
  <div v-if="total > 1" class="skx-pagination">
    <nav class="skx-page" aria-label="페이지 탐색">
      <div class="skx-page-nav">
        <button
          type="button"
          class="skx-page-nav-btn"
          aria-label="처음 페이지"
          :disabled="page === 1"
          @click="emit('go', 1)"
        >
          <img src="/img/ico-page-first.svg" alt="" />
        </button>
        <button
          type="button"
          class="skx-page-nav-btn"
          aria-label="이전 페이지"
          :disabled="page === 1"
          @click="emit('go', page - 1)"
        >
          <img src="/img/ico-page-prev.svg" alt="" />
        </button>
      </div>
      <div class="skx-page-nums">
        <template v-for="(p, i) in buttons" :key="p === '...' ? `gap-${i}` : p">
          <span v-if="p === '...'" class="skx-page-ellipsis">…</span>
          <button
            v-else
            type="button"
            :class="['skx-page-num', p === page && 'is-active']"
            :aria-current="p === page ? 'page' : undefined"
            @click="emit('go', p)"
          >
            {{ p }}
          </button>
        </template>
      </div>
      <div class="skx-page-nav">
        <button
          type="button"
          class="skx-page-nav-btn"
          aria-label="다음 페이지"
          :disabled="page === total"
          @click="emit('go', page + 1)"
        >
          <img src="/img/ico-page-next.svg" alt="" />
        </button>
        <button
          type="button"
          class="skx-page-nav-btn"
          aria-label="마지막 페이지"
          :disabled="page === total"
          @click="emit('go', total)"
        >
          <img src="/img/ico-page-last.svg" alt="" />
        </button>
      </div>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { pageButtons } from "~/utils/resultPaging";

// page 는 1부터, total 은 전체 쪽 수. 가고 싶은 쪽 번호만 go 로 올린다
const props = defineProps<{ page: number; total: number }>();
const emit = defineEmits<{ go: [page: number] }>();

const buttons = computed(() => pageButtons(props.total, props.page));
</script>
