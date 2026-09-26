<!-- frontend/components/research/SearchPlusMenu.vue -->
<template>
  <div v-if="modes.length" ref="root" class="rs-plus" :class="{ 'is-active': !!active }">
    <span class="rs-plus__anchor">
      <button
        type="button"
        class="rs-plus__btn"
        aria-haspopup="menu"
        :aria-expanded="menuOpen"
        aria-label="검색 모드 선택"
        :disabled="disabled || busy"
        @click="menuOpen = !menuOpen"
      >
        +
      </button>
      <ul v-if="menuOpen" class="rs-plus__menu" role="menu" @keydown.escape.stop="menuOpen = false">
        <li v-for="m in modes" :key="m.id" role="none">
          <button
            type="button"
            role="menuitem"
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useResearchStarter } from "~/composables/useResearch";
import { researchErrorMessage } from "~/utils/researchErrors";
import { questionProblem } from "~/utils/researchInput";
import {
  modesFor,
  parseSlash,
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
const menuOpen = ref(false);
const active = ref<SearchMode | null>(null);
const busy = ref(false);
const error = ref("");

let host: HTMLElement | null = null;
let field: HTMLTextAreaElement | HTMLInputElement | null = null;
let basePlaceholder = "";

function modeFor(id: SearchModeId | null): SearchMode | undefined {
  return modes.value.find((m) => m.id === id);
}

function currentText(): string {
  return field?.value ?? props.modelValue;
}

function activate(mode: SearchMode): void {
  active.value = mode;
  error.value = "";
  if (field) field.placeholder = mode.placeholder;
}

function choose(mode: SearchMode): void {
  menuOpen.value = false;
  activate(mode);
  const slash = parseSlash(props.modelValue);
  if (slash.mode) emit("update:modelValue", slash.text);
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
    if (error.value && !busy.value) error.value = "";
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
    emit("update:modelValue", slash.text);
  },
);

function researchWanted(): boolean {
  return !!active.value || !!modeFor(parseSlash(currentText()).mode);
}

async function submit(): Promise<void> {
  if (busy.value || props.disabled) return;
  const slash = parseSlash(currentText());
  const mode = active.value ?? modeFor(slash.mode);
  if (!mode) return;
  if (!active.value) activate(mode);
  const question = (slash.mode ? slash.text : currentText()).trim();
  if (slash.mode) emit("update:modelValue", slash.text);
  const problem = questionProblem(question);
  if (problem) {
    error.value = problem;
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const jobId = await startResearch(question);
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
