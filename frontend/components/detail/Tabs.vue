<template>
  <!-- 가로 밑줄 탭 — 켜진 탭은 포인트색 굵은 글 + 밑줄. 탭은 방향키(←→·Home·End)로 옮기고, 옮기면 바로 그 탭을 연다.
       Tab 키는 켜진 탭 하나에만 들르고(나머지 tabindex -1) 다음은 본문(tabpanel)으로 간다 -->
  <div class="dt-tabs">
    <div class="dt-tabs__list" role="tablist" :aria-label="label">
      <button
        v-for="(tab, i) in tabs"
        :id="tabId(tab.key)"
        :key="tab.key"
        type="button"
        role="tab"
        :class="['dt-tabs__tab', tab.key === modelValue && 'is-active']"
        :aria-selected="tab.key === modelValue"
        :aria-controls="panelId"
        :tabindex="tab.key === modelValue ? 0 : -1"
        @click="emit('update:modelValue', tab.key)"
        @keydown="onKeydown($event, i)"
      >
        {{ tab.label }}
      </button>
    </div>
    <div
      :id="panelId"
      class="dt-tabs__panel"
      role="tabpanel"
      :aria-labelledby="modelValue ? tabId(modelValue) : undefined"
      tabindex="0"
    >
      <slot :active="modelValue" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { tabKeyTarget } from "~/utils/detailView";

const props = defineProps<{
  tabs: readonly { key: string; label: string }[];
  modelValue: string | null;
  /** 탭 목록의 이름(스크린리더) */
  label: string;
}>();
const emit = defineEmits<{ "update:modelValue": [key: string] }>();

const uid = useId();
const panelId = `dt-tabs-${uid}-panel`;
function tabId(key: string): string {
  return `dt-tabs-${uid}-${key}`;
}

function onKeydown(e: KeyboardEvent, index: number) {
  const next = tabKeyTarget(e.key, index, props.tabs.length);
  if (next === null) return;
  e.preventDefault();
  const tab = props.tabs[next];
  if (!tab) return;
  emit("update:modelValue", tab.key);
  document.getElementById(tabId(tab.key))?.focus();
}
</script>
