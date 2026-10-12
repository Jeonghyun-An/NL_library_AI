<!-- frontend/components/SettingsMenu.vue -->
<!-- 사이드바 하단 설정(톱니) + 작은 팝오버 — 제목 '설정', 항목 '테마' 아래 [다크] [라이트] 두 칸 토글.
     누르면 바로 바뀌고 localStorage 에 기억된다(composables/useTheme.ts · utils/theme.ts). 기본은 다크(다크 그린).
     키보드: 톱니를 누르면 선택된 칸으로 초점이 가고, ←→(↑↓)로 옮기면 바로 선택된다(라디오), Esc 는 닫고 톱니로 초점을 되돌린다.
     바깥을 누르거나 초점이 팝오버 밖으로 나가면 닫는다. 팝오버는 톱니 위쪽, 사이드바 폭 안에 열려 화면 밖으로 나가지 않는다.
     접힌 띠에서는 AppSidebar 의 규칙으로 통째로 숨는다(.skx-settings). -->
<template>
  <div ref="rootEl" class="skx-set" @focusout="onFocusOut">
    <button
      ref="gearEl"
      type="button"
      class="skx-icon-btn skx-set__gear"
      aria-label="설정"
      aria-haspopup="dialog"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="toggle"
    >
      <img src="/img/ico-settings.svg" alt="" />
    </button>
    <div v-if="open" :id="panelId" class="skx-set__panel" role="dialog" aria-label="설정">
      <h2 class="skx-set__title">설정</h2>
      <p :id="labelId" class="skx-set__label">테마</p>
      <div class="skx-set__seg" role="radiogroup" :aria-labelledby="labelId" @keydown="onKeydown">
        <button
          v-for="name in THEMES"
          :key="name"
          :ref="(el) => setOptEl(name, el)"
          type="button"
          role="radio"
          :aria-checked="theme === name"
          :tabindex="theme === name ? 0 : -1"
          :class="['skx-set__opt', theme === name && 'is-active']"
          @click="pick(name)"
        >
          {{ THEME_LABELS[name] }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useTheme } from "~/composables/useTheme";
import { THEMES, THEME_LABELS, stepTheme, type ThemeName } from "~/utils/theme";

const { theme, setTheme } = useTheme();

const uid = useId();
const panelId = `skx-set-panel-${uid}`;
const labelId = `skx-set-theme-${uid}`;

const open = ref(false);
const rootEl = ref<HTMLElement | null>(null);
const gearEl = ref<HTMLButtonElement | null>(null);
const optEls: Partial<Record<ThemeName, HTMLElement>> = {};

function setOptEl(name: ThemeName, el: unknown) {
  if (el instanceof HTMLElement) optEls[name] = el;
  else delete optEls[name];
}

function focusChecked() {
  optEls[theme.value]?.focus({ preventScroll: true });
}

async function openPanel() {
  open.value = true;
  await nextTick();
  focusChecked();
}

/** 닫기 — restoreFocus 면 톱니로 초점을 되돌린다(Esc) */
function close(restoreFocus: boolean) {
  if (!open.value) return;
  open.value = false;
  if (restoreFocus) nextTick(() => gearEl.value?.focus({ preventScroll: true }));
}

function toggle() {
  if (open.value) close(false);
  else void openPanel();
}

function pick(name: ThemeName) {
  setTheme(name);
}

function onKeydown(e: KeyboardEvent) {
  const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
  if (step) {
    e.preventDefault();
    const next = stepTheme(theme.value, step);
    setTheme(next);
    nextTick(() => optEls[next]?.focus({ preventScroll: true }));
  } else if (e.key === "Home" || e.key === "End") {
    e.preventDefault();
    const next = e.key === "Home" ? THEMES[0]! : THEMES[THEMES.length - 1]!;
    setTheme(next);
    nextTick(() => optEls[next]?.focus({ preventScroll: true }));
  }
}

/** 초점이 이 상자 밖으로 나가면 닫는다(Tab 으로 떠날 때) */
function onFocusOut(e: FocusEvent) {
  const to = e.relatedTarget as Node | null;
  if (open.value && to && !rootEl.value?.contains(to)) close(false);
}

function onDocPointerDown(e: PointerEvent) {
  if (open.value && !rootEl.value?.contains(e.target as Node)) close(false);
}

function onDocKeydown(e: KeyboardEvent) {
  if (open.value && e.key === "Escape") {
    e.preventDefault();
    close(true);
  }
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocPointerDown);
  document.addEventListener("keydown", onDocKeydown);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocPointerDown);
  document.removeEventListener("keydown", onDocKeydown);
});
</script>
