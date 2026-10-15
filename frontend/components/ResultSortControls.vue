<template>
  <!-- 결과 목록 머리(ResultListHead)의 오른쪽 — 정렬 버튼 · 한 쪽에 보일 개수. 논문·소장자료 결과가 같이 쓴다.
       고른 값은 부모가 쥐고(sortBy·pageSize), 바꾸라는 요청만 sort·size 로 올린다 — 쪽을 1로 되돌리는 일도 부모 몫이다 -->
  <div class="skx-paper-sorts" role="group" aria-label="정렬 기준">
    <button
      v-for="opt in SORT_OPTIONS"
      :key="opt.key"
      type="button"
      :class="['skx-paper-sort', sortBy === opt.key && 'is-active']"
      :aria-pressed="sortBy === opt.key"
      @click="emit('sort', opt.key)"
    >
      <img :src="sortBy === opt.key ? '/img/ico-sort-on.svg' : '/img/ico-sort-off.svg'" alt="" />
      {{ opt.label }}
    </button>
  </div>
  <div
    ref="perpageRef"
    :class="['skx-paper-perpage', open && 'is-open']"
    @keydown.esc="open = false"
  >
    <button
      type="button"
      class="skx-paper-perpage__btn"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click.stop="open = !open"
    >
      <span class="skx-paper-perpage__label">{{ pageSize }}개씩</span>
      <img src="/img/ico-arrow-down.svg" alt="" aria-hidden="true" />
    </button>
    <ul class="skx-paper-perpage__menu" role="listbox">
      <li v-for="n in PAGE_SIZES" :key="n">
        <button
          type="button"
          :class="['skx-paper-perpage__opt', pageSize === n && 'is-selected']"
          role="option"
          :aria-selected="pageSize === n"
          @click="pick(n)"
        >
          {{ n }}개씩
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { PAGE_SIZES, SORT_OPTIONS, type PageSize, type SortKey } from "~/utils/resultPaging";

defineProps<{ sortBy: SortKey; pageSize: number }>();
const emit = defineEmits<{ sort: [key: SortKey]; size: [n: PageSize] }>();

// 개수 메뉴 — 열려 있을 때 메뉴 밖을 누르거나 Esc 를 누르면 닫힌다
const open = ref(false);
const perpageRef = ref<HTMLElement | null>(null);

function pick(n: PageSize) {
  open.value = false;
  emit("size", n);
}

function closeOutside(e: MouseEvent) {
  if (!open.value) return;
  if (e.target instanceof Node && perpageRef.value?.contains(e.target)) return;
  open.value = false;
}

onMounted(() => document.addEventListener("click", closeOutside));
onBeforeUnmount(() => document.removeEventListener("click", closeOutside));
</script>
