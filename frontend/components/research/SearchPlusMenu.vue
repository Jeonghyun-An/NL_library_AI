<!-- frontend/components/research/SearchPlusMenu.vue -->
<template>
  <div v-if="modes.length" ref="root" class="rs-plus" :class="{ 'is-active': !!active }" @keydown="onRootKeydown">
    <span class="rs-plus__anchor">
      <button
        ref="trigger"
        type="button"
        class="rs-plus__btn"
        aria-haspopup="menu"
        :aria-expanded="menuOpen"
        :aria-controls="menuOpen ? menuId : undefined"
        aria-label="검색 모드 선택"
        :disabled="disabled || busy"
        @click="toggleMenu"
        @keydown="onTriggerKeydown"
      >
        +
      </button>
      <ul v-if="menuOpen" :id="menuId" ref="menu" class="rs-plus__menu" role="menu" aria-label="검색 모드" @keydown="onMenuKeydown">
        <li v-for="m in modes" :key="m.id" role="none">
          <!-- tabindex=-1: 항목 사이는 방향키로 옮긴다. Tab 은 메뉴를 닫고 다음 요소로 간다 -->
          <button
            type="button"
            role="menuitem"
            tabindex="-1"
            class="rs-plus__item"
            :class="{ 'is-selected': active?.id === m.id }"
            @click="choose(m)"
          >
            <img class="rs-plus__icon" :src="m.icon" alt="" />
            <span class="rs-plus__text">
              <span class="rs-plus__label">{{ m.label }}</span>
              <span class="rs-plus__desc">{{ m.description }}</span>
            </span>
          </button>
        </li>
      </ul>
    </span>
    <span v-if="active" class="rs-plus__chip">
      {{ active.label }}
      <button type="button" class="rs-plus__chip-x" :aria-label="`${active.label} 해제`" @click="clear">×</button>
    </span>
    <p v-if="error" class="rs-plus__error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { useResearchStarter } from "~/composables/useResearch";
import { menuStep } from "~/utils/menuNav";
import { researchErrorMessage } from "~/utils/researchErrors";
import {
  createEchoGuard,
  modesFor,
  parseSlash,
  planSlashSubmit,
  shouldAutoChip,
  type SearchInputKind,
  type SearchMode,
  type SearchModeId,
} from "~/utils/slashCommand";

const props = withDefaults(
  defineProps<{ modelValue: string; kind?: SearchInputKind; disabled?: boolean }>(),
  { kind: "paper", disabled: false },
);
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const { startResearch } = useResearchStarter();
const modes = computed(() => modesFor(props.kind));
const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const menuId = useId();
const menuOpen = ref(false);
const active = ref<SearchMode | null>(null);
const busy = ref(false);
const error = ref("");

let host: HTMLElement | null = null;
let field: HTMLTextAreaElement | HTMLInputElement | null = null;
let basePlaceholder = "";
const echo = createEchoGuard();

function modeFor(id: SearchModeId | null): SearchMode | undefined {
  return modes.value.find((m) => m.id === id);
}

// 입력창 값은 모두 여기로 바꾼다 — 되돌아오는 modelValue 를 watch 가 사용자 입력과 가려 보게
function emitText(value: string): void {
  echo.mark(value);
  emit("update:modelValue", value);
}

function currentText(): string {
  return field?.value ?? props.modelValue;
}

function activate(mode: SearchMode): void {
  active.value = mode;
  error.value = "";
  if (field) field.placeholder = mode.placeholder;
}

// ── + 메뉴 키보드(WAI-ARIA 메뉴 버튼 관례) ─────────────────
function menuItems(): HTMLElement[] {
  return Array.from(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
}

function focusItem(key: string): boolean {
  const items = menuItems();
  const at = items.findIndex((el) => el === document.activeElement);
  const next = menuStep(at, key, items.length);
  if (next === null) return false;
  items[next]?.focus();
  return true;
}

// 열면 첫 항목(위 방향키로 열면 마지막 항목)으로 초점을 옮긴다 — 방향키·Esc 가 메뉴 안에서 먹게
async function openMenu(key: "ArrowDown" | "ArrowUp" = "ArrowDown"): Promise<void> {
  menuOpen.value = true;
  await nextTick();
  focusItem(key);
}

function closeMenu(returnFocus: boolean): void {
  menuOpen.value = false;
  if (returnFocus) trigger.value?.focus();
}

function toggleMenu(): void {
  if (menuOpen.value) closeMenu(false);
  else void openMenu();
}

function onTriggerKeydown(e: KeyboardEvent): void {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  e.preventDefault();
  if (menuOpen.value) focusItem(e.key === "ArrowUp" ? "End" : "Home");
  else void openMenu(e.key);
}

function onMenuKeydown(e: KeyboardEvent): void {
  // Tab 은 막지 않는다 — + 버튼으로 초점을 돌려 둔 뒤 기본 동작이 그 앞뒤 요소로 옮긴다.
  // 초점을 쥔 항목을 그대로 지우면 초점이 body 로 떨어져 Tab 순서를 잃는다.
  if (e.key === "Tab") {
    closeMenu(true);
    return;
  }
  if (focusItem(e.key)) e.preventDefault();
}

// + 버튼에 초점이 있어도(마우스로 연 뒤) Esc 로 닫히게 메뉴가 아니라 묶음 전체에서 듣는다
function onRootKeydown(e: KeyboardEvent): void {
  if (e.key !== "Escape" || !menuOpen.value) return;
  e.preventDefault();
  e.stopPropagation();
  closeMenu(true);
}

function choose(mode: SearchMode): void {
  menuOpen.value = false;
  activate(mode);
  const slash = parseSlash(props.modelValue);
  if (slash.mode) emitText(slash.text);
  field?.focus();
}

function clear(): void {
  active.value = null;
  error.value = "";
  if (field) field.placeholder = basePlaceholder;
  field?.focus();
}

watch(
  () => props.modelValue,
  (value) => {
    // 접두를 떼며 스스로 emit 한 값이 되돌아온 것이면 submit 이 방금 넣은 검증 오류를 두고,
    // 사용자가 글을 고칠 때만 지운다
    if (!echo.take(value) && error.value && !busy.value) error.value = "";
    // 같은 검색어를 다른 입력창·코드도 바꾼다(메인 랜딩은 도서·논문 패널이 한 currentQuery 에
    // 묶여 있고, 숨은 논문 패널의 이 컴포넌트도 마운트된 채다. 기록 복원도 값을 넣는다). 자기
    // 입력창에 사용자가 친 글에만 칩을 켠다. 부모 상자의 캡처 단계 input 리스너로 가리면 입력창의
    // v-model 보다 먼저 돌아 접두를 뗀 값이 원문으로 다시 덮이므로, 값이 바뀐 뒤 도는 여기서 가린다.
    if (!field || document.activeElement !== field) return;
    if (active.value || !shouldAutoChip(value)) return;
    const slash = parseSlash(value);
    const mode = modeFor(slash.mode);
    if (!mode) return;
    activate(mode);
    emitText(slash.text);
  },
);

function researchWanted(): boolean {
  return !!active.value || !!modeFor(parseSlash(currentText()).mode);
}

async function submit(): Promise<void> {
  if (busy.value || props.disabled) return;
  const plan = planSlashSubmit(currentText(), active.value?.id ?? null, modes.value);
  const mode = active.value ?? modeFor(plan?.mode ?? null);
  if (!plan || !mode) return;
  if (!active.value) activate(mode);
  if (plan.stripped !== null) emitText(plan.stripped);
  if (plan.problem) {
    error.value = plan.problem;
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const jobId = await startResearch(plan.question);
    await navigateTo(`/research/${jobId}`);
  } catch (e) {
    // 입력은 지우지 않는다 — 사용자가 고쳐서 다시 보낼 수 있어야 한다
    error.value = researchErrorMessage(e, "딥리서치를 시작하지 못했습니다");
  } finally {
    busy.value = false;
  }
}

// 페이지의 엔터 처리를 고치지 않고 한 줄 삽입으로 붙이려고(입력창은 화면 고도화와 가장
// 겹치는 곳이다) 부모 상자에서 캡처 단계로 엔터·전송 클릭을 가로챈다. 캡처 단계에서
// 전파를 끊으면 입력창·전송 버튼에 달린 페이지의 검색 핸들러까지 가지 않는다.
function onHostKeydown(e: KeyboardEvent): void {
  if (e.key !== "Enter" || e.target !== field || !researchWanted()) return;
  if (e.shiftKey && field instanceof HTMLTextAreaElement) return;
  e.preventDefault();
  e.stopPropagation();
  // 한글 조합 중의 엔터는 글자 확정용이다 — 여기서 보내면 마지막 글자가 빠지거나 두 번 간다
  if (e.isComposing) return;
  void submit();
}

function onHostClick(e: MouseEvent): void {
  const target = e.target instanceof Element ? e.target : null;
  if (!target?.closest(".skx-send") || !researchWanted()) return;
  e.preventDefault();
  e.stopPropagation();
  void submit();
}

function onDocumentClick(e: MouseEvent): void {
  if (menuOpen.value && root.value && e.target instanceof Node && !root.value.contains(e.target)) {
    menuOpen.value = false;
  }
}

onMounted(() => {
  host = root.value?.parentElement ?? null;
  field = host?.querySelector<HTMLTextAreaElement | HTMLInputElement>("textarea, input[type='text'], input:not([type])") ?? null;
  basePlaceholder = field?.placeholder ?? "";
  host?.addEventListener("keydown", onHostKeydown, true);
  host?.addEventListener("click", onHostClick, true);
  document.addEventListener("click", onDocumentClick);
});

onBeforeUnmount(() => {
  host?.removeEventListener("keydown", onHostKeydown, true);
  host?.removeEventListener("click", onHostClick, true);
  document.removeEventListener("click", onDocumentClick);
});
</script>
