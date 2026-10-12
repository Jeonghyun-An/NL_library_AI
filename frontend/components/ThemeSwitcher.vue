<!-- frontend/components/ThemeSwitcher.vue -->
<!-- 화면 테마 고르기(최소 UI) — 사이드바 맨 아래 한 줄에 테마마다 동그란 견본 하나씩. 고르면 html[data-theme] 이 바뀌고 localStorage 에 기억된다(composables/useTheme.ts).
     utils/featureFlags.ts 의 SHOW_THEME_SWITCH 가 켜질 때만 AppSidebar 가 그린다(기본은 숨김 — 주소의 ?theme=pink 로도 고를 수 있다). -->
<template>
  <div class="skx-theme" role="group" aria-label="화면 테마">
    <span class="skx-theme__label">테마</span>
    <button
      v-for="name in THEMES"
      :key="name"
      type="button"
      :class="['skx-theme__btn', `skx-theme__btn--${name}`, theme === name && 'is-active']"
      :aria-pressed="theme === name"
      :aria-label="`${THEME_LABELS[name]} 테마`"
      :title="THEME_LABELS[name]"
      @click="setTheme(name)"
    >
      <span class="skx-theme__dot"></span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useTheme } from "~/composables/useTheme";
import { THEMES, THEME_LABELS } from "~/utils/theme";

const { theme, setTheme } = useTheme();
</script>
