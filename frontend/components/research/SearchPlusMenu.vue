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
          <p class="rs-plus__hint">키보드로는 {{ m.slash }}</p>
        </li>
      </ul>
    </span>
    <!-- 글은 대문자 높이 기준으로 가운데(.rs-plus__chip-label — text-box), × 는 글자 대신 그림이라 칩 정가운데에 선다. 전에는 × 글자가
         글꼴·크기가 달라 1px 쯤 처져 'DeepResearch' 가 위로 떠 보였다(사용자 의견 2026-10-14) -->
    <span v-if="active" class="rs-plus__chip">
      <span class="rs-plus__chip-label">{{ active.label }}</span>
      <button type="button" class="rs-plus__chip-x" :aria-label="`${active.label} 해제`" @click="clear">
        <svg viewBox="0 0 10 10" aria-hidden="true" focusable="false">
          <path d="M2 2 8 8M8 2 2 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" fill="none" />
        </svg>
      </button>
    </span>
    <!-- DeepResearch 를 고르면 칩 옆에 탐색 방식(spec D28) — 고른 값을 잡 params 두 칸(broaden·query_context)으로 싣는다 -->
    <ResearchModePicker
      v-if="active?.id === 'deep-research'"
      :model-value="researchMode"
      :disabled="disabled || busy"
      @update:model-value="pickMode"
    />
    <!-- DeepResearch 모드인 동안 질문 글자 수 — 입력창에는 같은 한도의 maxlength 를 달고 aria-describedby 로 이것을 가리킨다
         (syncFieldLimit — 입력창은 페이지의 요소라 마크업을 고치지 않는다). 랜딩 상자에서는 칩 줄 오른쪽 끝, 결과 검색바에서는 한도
         가까이에서만 보인다(research.css .rs-plus__count) -->
    <SkxCharCount
      v-if="researchActive"
      :id="countId"
      class="rs-plus__count"
      :length="modelValue.length"
      :max="QUESTION_MAX"
    />
    <!-- 시작 전 질문 길이 오류·시작 요청 실패·입력창 줄의 [취소] 실패 — 입력 상자 아래 왼쪽의 줄 안내 -->
    <SkxInlineError v-if="error" class="rs-plus__error" :message="error" />
    <!-- DeepResearch 모드일 때 이 브라우저에 끝나지 않은 연구가 있으면 한 줄(사용자 결정 2026-10-13 — 판단은 useResearchStarter·
         utils/researchStart). [보기]는 그 연구 화면, [취소]는 한 번 더 눌러('정말 취소') 기존 취소 API 로 멈춘다. 보내기는 막지
         않는다 — 서버의 승인 429 browser_active 가 마지막 안전망이다. 랜딩 입력 상자에서는 칩 줄 아래, 결과 검색바에서는 바 아래에 선다 -->
    <!-- 확인에 들어가면 취소 버튼에 숨김 확인 문구를 단다(aria-describedby). 바뀐 버튼 이름은 초점을 쥔 채로는 잘 읽히지 않아 들어갈 때와
         취소에 성공했을 때는 아래 live 영역으로도 알린다. Esc 는 확인 중일 때만 받아 물러난다(그 밖에는 + 메뉴 닫기 등으로 흘려보낸다) -->
    <div
      v-if="active?.id === 'deep-research' && notice"
      ref="noteLine"
      class="rs-start-note"
      role="group"
      :aria-labelledby="noteId"
      @keydown.esc="onNoticeEscape"
    >
      <span :id="noteId" class="rs-start-note__text" role="status">{{ notice.text }}</span>
      <span class="rs-start-note__dot" aria-hidden="true">·</span>
      <NuxtLink :to="notice.to" class="rs-start-note__btn">보기</NuxtLink>
      <button
        ref="cancelBtn"
        type="button"
        :class="['rs-start-note__btn', cancelStep !== 'idle' && 'is-danger']"
        :disabled="cancelStep === 'busy'"
        :aria-describedby="cancelStep === 'confirm' ? confirmId : undefined"
        @click="onNoticeCancel"
      >
        {{ noticeCancelLabel(cancelStep) }}
      </button>
      <button v-if="cancelStep === 'confirm'" type="button" class="rs-start-note__btn" @click="keepNotice">
        그대로 두기
      </button>
      <span v-if="cancelStep === 'confirm'" :id="confirmId" class="rs-sr-only">{{ NOTICE_CANCEL_CONFIRM_TEXT }}</span>
    </div>
    <!-- 알림 줄의 live 영역 — 줄 밖 뿌리에 늘 두어야 마지막 한 건을 취소해 줄째 사라져도 '취소했습니다'가 들린다 -->
    <span class="rs-sr-only" role="status">{{ noticeLive }}</span>
    <!-- 슬래시 명령 목록: 초점은 입력창에 둔 채(aria-activedescendant) 방향키로 고른다.
         mousedown 을 막아 항목·여백을 눌러도 입력창 초점이 빠지지 않게 한다 -->
    <ul
      v-if="paletteOpen"
      :id="paletteId"
      class="rs-plus__palette"
      role="listbox"
      aria-label="슬래시 명령"
      @mousedown.prevent
    >
      <li
        v-for="(m, i) in suggestions"
        :id="optionId(m)"
        :key="m.id"
        role="option"
        class="rs-plus__option"
        :class="{ 'is-selected': i === highlight }"
        :aria-selected="i === highlight"
        @mouseenter="highlight = i"
        @click="pick(m)"
      >
        <img class="rs-plus__icon" :src="m.icon" alt="" />
        <span class="rs-plus__text">
          <span class="rs-plus__cmd">
            <span class="rs-plus__slash">{{ m.slash }}</span>
            <span class="rs-plus__alias">{{ m.label }}</span>
          </span>
          <span class="rs-plus__desc">{{ m.description }}</span>
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import ResearchModePicker from "~/components/research/ResearchModePicker.vue";
import { useResearchStarter } from "~/composables/useResearch";
import { DEEP_RESEARCH } from "~/utils/brand";
import { safeLocalStorage } from "~/utils/browserId";
import { menuStep } from "~/utils/menuNav";
import { researchErrorMessage } from "~/utils/researchErrors";
import { QUESTION_MAX } from "~/utils/researchInput";
import {
  DEFAULT_RESEARCH_MODE,
  modeParams,
  readResearchMode,
  saveResearchMode,
  type ResearchMode,
} from "~/utils/researchMode";
import {
  NOTICE_CANCEL_CONFIRM_TEXT,
  NOTICE_CANCEL_DONE_TEXT,
  describedByWith,
  noticeCancelBack,
  noticeCancelLabel,
  noticeCancelPress,
  noticeFocusTarget,
  type NoticeCancelStep,
} from "~/utils/researchStart";
import {
  createEchoGuard,
  modesFor,
  paletteKeyAction,
  parseSlash,
  planSlashSubmit,
  shouldAutoChip,
  slashSuggestions,
  type SearchInputKind,
  type SearchMode,
  type SearchModeId,
} from "~/utils/slashCommand";

const props = withDefaults(
  defineProps<{ modelValue: string; kind?: SearchInputKind; disabled?: boolean }>(),
  { kind: "paper", disabled: false },
);
// update:mode — 켜진 모드가 바뀔 때마다(+ 메뉴·슬래시 명령·× 해제·페이지의 activateMode/clearMode) 새 모드 id 를 알린다.
// 끈 상태는 null. 메인 랜딩이 이 값으로 딥리서치 모드 여부(KCI 등재 필터 숨김 등)를 맞춘다
const emit = defineEmits<{ "update:modelValue": [value: string]; "update:mode": [id: SearchModeId | null] }>();

const { startResearch, notice, cancelResearch } = useResearchStarter();
const modes = computed(() => modesFor(props.kind));
const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const menu = ref<HTMLElement | null>(null);
const menuId = useId();
const menuOpen = ref(false);
const active = ref<SearchMode | null>(null);
const busy = ref(false);
const error = ref("");
// 탐색 방식 — 서버 렌더와 첫 그림이 같게 기본(정밀하게)으로 시작하고 마운트 뒤 기억한 값을 읽는다
const researchMode = ref<ResearchMode>(DEFAULT_RESEARCH_MODE);

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

// 고른 탐색 방식은 같은 브라우저에 기억한다 — 편의일 뿐이라 저장이 막혀도 이 화면에서는 고른 값을 쓴다
function pickMode(mode: ResearchMode): void {
  researchMode.value = mode;
  saveResearchMode(safeLocalStorage(), mode);
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

function deactivate(): void {
  active.value = null;
  error.value = "";
  if (field) field.placeholder = basePlaceholder;
}

function clear(): void {
  deactivate();
  field?.focus();
}

// 페이지가 칩을 켠 채 입력창을 채울 때 쓴다(논문 상세의 [이 논문으로 딥리서치]가 넘긴 질문 초안).
// 초안은 고쳐 쓰라고 주는 것이라 초점을 글 끝에 둔다. 초점을 다른 곳(예: 방향키로 옮기는 중인 전환 탭)에
// 두고 싶으면 { focus: false }
function activateMode(id: SearchModeId, options: { focus?: boolean } = {}): void {
  const mode = modeFor(id);
  if (!mode) return;
  activate(mode);
  if (!field || options.focus === false) return;
  field.focus();
  field.setSelectionRange(field.value.length, field.value.length);
}

// 페이지가 칩을 끈다(메인 랜딩에서 자료 검색 갈래로 갈 때). × 버튼과 달리 초점을 옮기지 않는다
function clearMode(): void {
  deactivate();
}

defineExpose({ activateMode, clearMode });

// sync — 같은 틱에 메뉴가 unmount 되는 경로(딥리서치 모드가 켜진 채 자료 검색 기록을 열어 랜딩이 걷힘)에서도 알림이 가게,
// 기본(pre) 플러시는 unmount 로 감시자가 멈추면 한 번도 돌지 못한다
watch(active, (mode) => emit("update:mode", mode?.id ?? null), { flush: "sync" });

// ── DeepResearch 질문 한도(maxlength + 글자 수) ─────────────
// 서버 ResearchCreate.question 의 max_length(500)를 입력창에서 먼저 막는다 — 모드인 동안만 입력창에 maxlength 를 달고, 끄면 페이지가 둔
// 값으로 되돌린다(논문 검색어의 한도는 페이지 몫이다). 글자 수(SkxCharCount)는 aria-describedby 로 잇는다 — 페이지가 단 다른 id 는 둔다
const researchActive = computed(() => active.value?.id === "deep-research");
const countId = useId();
// 지금 입력창에 한도를 달아 두었는가, 달기 전에 페이지가 둔 maxlength(없으면 null)
let limiting = false;
let pageMaxLength: string | null = null;

function syncFieldLimit(on: boolean): void {
  if (!field || on === limiting) return;
  limiting = on;
  if (on) {
    pageMaxLength = field.getAttribute("maxlength");
    field.setAttribute("maxlength", String(QUESTION_MAX));
  } else if (pageMaxLength === null) {
    field.removeAttribute("maxlength");
  } else {
    field.setAttribute("maxlength", pageMaxLength);
  }
  const described = describedByWith(field.getAttribute("aria-describedby"), countId, on);
  if (described) field.setAttribute("aria-describedby", described);
  else field.removeAttribute("aria-describedby");
}

// 글자 수 요소가 DOM 에 생긴 뒤 가리키게 렌더 뒤에 맞춘다
watch(researchActive, syncFieldLimit, { flush: "post" });

// ── 끝나지 않은 연구 한 줄(DeepResearch 모드일 때만) ─────────
// [취소]는 두 번 눌러야 멈춘다 — 첫 누름은 '정말 취소'로 바꾸기만 하고, 잠깐(NOTICE_CANCEL_ARM_MS) 안의 누름은 받지 않는다(더블클릭
// 한 번에 확인까지 넘어가지 않게). 줄의 연구가 바뀌거나 모드를 끄면 확인을 푼다 — '정말 취소'가 다른 연구에 남지 않게.
// 초점은 사이드바 인라인 확인(openConfirm·closeConfirm·clearGroup)과 같은 관례를 따른다 — 쥔 버튼이 v-if 로 사라지면 초점이 body 로
// 떨어져 Tab 순서를 잃으므로, 물러나면 취소 버튼으로, 취소가 끝나 줄째 사라지면 입력창으로 돌린다(noticeFocusTarget)
const noteId = useId();
const confirmId = useId();
const noteLine = ref<HTMLElement | null>(null);
const cancelBtn = ref<HTMLButtonElement | null>(null);
const cancelStep = ref<NoticeCancelStep>("idle");
// 뿌리 live 영역의 글 — 확인에 들어갈 때와 취소에 성공했을 때만 채우고, 물러나거나 다시 취소를 보낼 때 비운다(같은 글도 다시 들리게)
const noticeLive = ref("");
let cancelArmedAt = 0;

// 렌더가 끝난 뒤(사라질 버튼이 걷히고 잠금이 풀린 뒤) 초점을 돌린다. 그새 사용자가 다른 곳으로 옮긴 초점은 빼앗지 않는다
async function restoreNoticeFocus(): Promise<void> {
  await nextTick();
  noticeFocusTarget<HTMLElement>({ active: document.activeElement, body: document.body }, cancelBtn.value, field)?.focus();
}

// 확인에서 물러난다([그대로 두기]·Esc·줄의 연구가 바뀜). 확인 중이 아니면 false. refocus 가 false 면 초점은 그대로 둔다 —
// 줄 밖에 있던 초점(폴링으로 연구가 바뀐 때)까지 끌어오지 않게
function backOffNotice(refocus: boolean): boolean {
  const next = noticeCancelBack(cancelStep.value);
  if (!next) return false;
  cancelStep.value = next;
  noticeLive.value = "";
  if (refocus) void restoreNoticeFocus();
  return true;
}

// [그대로 두기] — 누른 버튼이 사라지므로 초점을 취소 버튼으로 돌린다
function keepNotice(): void {
  backOffNotice(true);
}

// Esc 는 확인 중일 때만 받는다 — 그 밖에는 흘려보내 + 메뉴 닫기(onRootKeydown)·페이지 처리가 그대로 돈다
function onNoticeEscape(e: KeyboardEvent): void {
  if (!backOffNotice(true)) return;
  e.preventDefault();
  e.stopPropagation();
}

async function onNoticeCancel(): Promise<void> {
  const target = notice.value;
  if (!target) return;
  const now = Date.now();
  const press = noticeCancelPress(cancelStep.value, cancelArmedAt, now);
  if (press === "arm") {
    cancelStep.value = "confirm";
    cancelArmedAt = now;
    noticeLive.value = NOTICE_CANCEL_CONFIRM_TEXT;
    return;
  }
  if (press !== "run") return;
  cancelStep.value = "busy";
  error.value = "";
  noticeLive.value = "";
  try {
    await cancelResearch(target.jobId);
    noticeLive.value = NOTICE_CANCEL_DONE_TEXT;
  } catch (e) {
    error.value = researchErrorMessage(e, `${DEEP_RESEARCH}를 취소하지 못했어요`);
  } finally {
    cancelStep.value = "idle";
    await restoreNoticeFocus();
  }
}

// 감시자는 렌더 전(pre)에 돈다 — 사라질 [그대로 두기]가 아직 초점을 쥐고 있는지 여기서 본다
watch([() => notice.value?.jobId, () => active.value?.id], () => {
  backOffNotice(!!noteLine.value?.contains(document.activeElement));
});

// ── 슬래시 명령 목록(WAI-ARIA 콤보박스 관례: 초점은 입력창, 강조는 aria-activedescendant) ──
const paletteId = useId();
// document.activeElement 는 반응형이 아니라 입력창의 focus·blur 로 따로 쥔다
const focused = ref(false);
// Esc 로 닫으면 입력값이 바뀔 때까지 다시 띄우지 않는다
const dismissed = ref(false);
const highlight = ref(0);
const suggestions = computed(() => slashSuggestions(props.modelValue, modes.value));
// 메인 랜딩은 숨은 논문 패널의 이 컴포넌트도 마운트돼 있고 도서 입력창과 값을 공유한다 —
// 값만 보고 띄우면 엉뚱한 곳에 뜨므로 자기 입력창에 초점이 있을 때만 띄운다(watch 의 가림과 같은 이유)
const paletteOpen = computed(
  () =>
    focused.value &&
    !active.value &&
    !props.disabled &&
    !busy.value &&
    !menuOpen.value &&
    !dismissed.value &&
    suggestions.value.length > 0,
);
const highlighted = computed(() => suggestions.value[highlight.value] ?? suggestions.value[0] ?? null);

function optionId(mode: SearchMode): string {
  return `${paletteId}-${mode.id}`;
}

function pick(mode: SearchMode): void {
  activate(mode);
  // 목록은 글 전체가 "/토큰" 하나일 때만 뜬다 — 토큰(앞 공백 포함)을 떼고 질문 칸을 비워 준다
  emitText(currentText().trimStart().replace(/^\S+/, ""));
  field?.focus();
}

// 처리한 키면 true — 기존 엔터 처리(딥리서치 제출)와 페이지의 검색 핸들러까지 가지 않게 끊는다
function onPaletteKey(e: KeyboardEvent): boolean {
  const action = paletteKeyAction(e.key, { composing: e.isComposing, shift: e.shiftKey });
  if (!action) return false;
  e.preventDefault();
  e.stopPropagation();
  const count = suggestions.value.length;
  if (action === "next" || action === "prev") {
    highlight.value = menuStep(highlight.value, action === "next" ? "ArrowDown" : "ArrowUp", count) ?? 0;
  } else if (action === "select") {
    if (highlighted.value) pick(highlighted.value);
  } else if (action === "close") {
    dismissed.value = true;
  }
  return true;
}

function onFieldFocus(): void {
  focused.value = true;
}

function onFieldBlur(): void {
  focused.value = false;
}

// 입력창은 페이지가 가진 요소라 마크업을 고치지 않고 목록이 떠 있는 동안만 속성을 단다
const FIELD_ARIA = ["aria-controls", "aria-expanded", "aria-activedescendant", "aria-autocomplete"] as const;

function syncFieldAria(): void {
  if (!field) return;
  if (!paletteOpen.value) {
    for (const name of FIELD_ARIA) field.removeAttribute(name);
    return;
  }
  field.setAttribute("aria-controls", paletteId);
  field.setAttribute("aria-expanded", "true");
  field.setAttribute("aria-autocomplete", "list");
  if (highlighted.value) field.setAttribute("aria-activedescendant", optionId(highlighted.value));
  else field.removeAttribute("aria-activedescendant");
}

// 목록이 바뀌거나 새로 뜨면 강조는 첫 항목으로 돌아간다
watch([paletteOpen, () => suggestions.value.map((m) => m.id).join(" ")], () => {
  highlight.value = 0;
});
// 항목의 id 가 DOM 에 생긴 뒤 aria-activedescendant 가 가리키게 렌더 뒤에 맞춘다
watch([paletteOpen, highlighted], syncFieldAria, { flush: "post" });
watch(
  () => props.modelValue,
  () => {
    dismissed.value = false;
  },
);

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
    const jobId = await startResearch(plan.question, modeParams(researchMode.value));
    await navigateTo(`/research/${jobId}`);
  } catch (e) {
    // 입력은 지우지 않는다 — 사용자가 고쳐서 다시 보낼 수 있어야 한다
    error.value = researchErrorMessage(e, `${DEEP_RESEARCH}를 시작하지 못했어요`);
  } finally {
    busy.value = false;
  }
}

// 페이지의 엔터 처리를 고치지 않고 한 줄 삽입으로 붙이려고(입력창은 화면 고도화와 가장
// 겹치는 곳이다) 부모 상자에서 캡처 단계로 엔터·전송 클릭을 가로챈다. 캡처 단계에서
// 전파를 끊으면 입력창·전송 버튼에 달린 페이지의 검색 핸들러까지 가지 않는다.
function onHostKeydown(e: KeyboardEvent): void {
  // 슬래시 명령 목록이 떠 있으면 그 키(엔터 포함)를 먼저 쓴다 — "/deep-research" 까지만 치고
  // 엔터를 쳐도 빈 질문 오류 대신 칩이 켜진다
  if (e.target === field && paletteOpen.value && onPaletteKey(e)) return;
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
  researchMode.value = readResearchMode(safeLocalStorage());
  focused.value = !!field && document.activeElement === field;
  syncFieldLimit(researchActive.value);
  field?.addEventListener("focus", onFieldFocus);
  field?.addEventListener("blur", onFieldBlur);
  host?.addEventListener("keydown", onHostKeydown, true);
  host?.addEventListener("click", onHostClick, true);
  document.addEventListener("click", onDocumentClick);
});

onBeforeUnmount(() => {
  field?.removeEventListener("focus", onFieldFocus);
  field?.removeEventListener("blur", onFieldBlur);
  if (field) for (const name of FIELD_ARIA) field.removeAttribute(name);
  syncFieldLimit(false);
  host?.removeEventListener("keydown", onHostKeydown, true);
  host?.removeEventListener("click", onHostClick, true);
  document.removeEventListener("click", onDocumentClick);
});
</script>
