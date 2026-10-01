<!-- frontend/components/research/ReportDownloadMenu.vue -->
<template>
  <div ref="root" class="rs-dl" @keydown="onRootKeydown">
    <!-- disabled 대신 aria-disabled: 고른 직후 만드는 중(busy)으로 바뀔 때 초점을 쥔 버튼이 비활성이 되면
         초점이 body 로 떨어진다(키보드 사용자가 제자리를 잃는다) -->
    <button
      ref="trigger"
      type="button"
      class="rs-btn rs-btn--ghost rs-btn--small rs-dl__btn"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="open ? menuId : undefined"
      :aria-disabled="inactive"
      :aria-busy="busy"
      :title="disabled ? '아직 내려받을 내용이 없습니다' : undefined"
      @click="toggle"
      @keydown="onTriggerKeydown"
    >
      <span v-if="busy" class="rs-dl__dot" aria-hidden="true" />
      {{ busy ? "만드는 중…" : `${label} ▾` }}
    </button>
    <ul v-if="open" :id="menuId" ref="menu" class="rs-dl__menu" role="menu" :aria-label="label" @keydown="onMenuKeydown">
      <li v-for="f in FORMATS" :key="f.id" role="none">
        <!-- tabindex=-1: 항목 사이는 방향키로 옮긴다. Tab 은 메뉴를 닫고 다음 요소로 간다 -->
        <button type="button" role="menuitem" tabindex="-1" class="rs-dl__item" @click="choose(f.id)">
          <span class="rs-dl__label">{{ f.label }}</span>
          <span class="rs-dl__desc">{{ f.description }}</span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { menuStep } from "~/utils/menuNav";
import type { ReportExportFormat } from "~/utils/reportDocument";

const props = withDefaults(defineProps<{ label: string; disabled?: boolean; busy?: boolean }>(), {
  disabled: false,
  busy: false,
});
const emit = defineEmits<{ select: [format: ReportExportFormat] }>();

const FORMATS: readonly { id: ReportExportFormat; label: string; description: string }[] = [
  { id: "docx", label: "Word 문서(.docx)", description: "고쳐 쓰기 좋고 한글에서도 열립니다" },
  { id: "pdf", label: "PDF로 저장", description: "인쇄 창에서 대상을 ‘PDF로 저장’으로 고릅니다" },
];

const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const menuId = useId();
const open = ref(false);
const inactive = computed(() => props.disabled || props.busy);

watch(inactive, (value) => {
  if (value) open.value = false;
});

function items(): HTMLElement[] {
  return Array.from(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
}

function focusItem(key: string): boolean {
  const list = items();
  const at = list.findIndex((el) => el === document.activeElement);
  const next = menuStep(at, key, list.length);
  if (next === null) return false;
  list[next]?.focus();
  return true;
}

// 열면 첫 항목(위 방향키로 열면 마지막 항목)으로 초점을 옮긴다 — 방향키·Esc 가 메뉴 안에서 먹게
async function openMenu(key: "ArrowDown" | "ArrowUp" = "ArrowDown"): Promise<void> {
  if (inactive.value) return;
  open.value = true;
  await nextTick();
  focusItem(key);
}

function closeMenu(returnFocus: boolean): void {
  open.value = false;
  if (returnFocus) trigger.value?.focus();
}

function toggle(): void {
  if (open.value) closeMenu(false);
  else void openMenu();
}

function onTriggerKeydown(e: KeyboardEvent): void {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  e.preventDefault();
  if (open.value) focusItem(e.key === "ArrowUp" ? "End" : "Home");
  else void openMenu(e.key);
}

function onMenuKeydown(e: KeyboardEvent): void {
  // Tab 은 막지 않는다 — 버튼으로 초점을 돌려 둔 뒤 기본 동작이 그 앞뒤 요소로 옮긴다
  if (e.key === "Tab") {
    closeMenu(true);
    return;
  }
  if (focusItem(e.key)) e.preventDefault();
}

// 버튼에 초점이 있어도(마우스로 연 뒤) Esc 로 닫히게 묶음 전체에서 듣는다
function onRootKeydown(e: KeyboardEvent): void {
  if (e.key !== "Escape" || !open.value) return;
  e.preventDefault();
  e.stopPropagation();
  closeMenu(true);
}

function choose(format: ReportExportFormat): void {
  closeMenu(true);
  emit("select", format);
}

function onDocumentClick(e: MouseEvent): void {
  if (open.value && root.value && e.target instanceof Node && !root.value.contains(e.target)) open.value = false;
}

onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));
</script>
