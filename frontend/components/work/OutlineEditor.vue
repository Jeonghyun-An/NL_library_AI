<!-- frontend/components/work/OutlineEditor.vue -->
<template>
  <section v-if="outline" class="rs-card wk-outline" aria-labelledby="wk-outline-title">
    <header class="wk-outline__head">
      <h3 id="wk-outline-title" class="rs-card__title">목차</h3>
      <span class="rs-badge" :class="approved ? 'rs-badge--done' : 'rs-badge--running'">{{ approved ? "승인함" : "초안" }}</span>
      <span v-if="proposal.stale.outline" class="rs-badge wk-outline__stale">다시 맞춤 필요</span>
    </header>
    <p v-if="proposal.stale.outline" class="rs-muted">
      목차를 만든 뒤 주제나 읽기 목록이 바뀌었습니다. 지금 목차는 지우지 않고 그대로 두었습니다 — 바뀐 목록으로 묶음을
      다시 나누려면 목차를 다시 만드세요.
    </p>
    <p v-if="fallback" class="rs-muted">
      모델이 목차 초안을 만들지 못해 묶음 이름은 묶음의 핵심 개념으로, 연구 질문 후보는 고른 주제의 질문으로 채웠습니다.
      직접 고쳐 승인하거나 목차를 다시 만드세요.
    </p>

    <ol class="wk-outline__rows">
      <li class="wk-outline__row">
        <h4 class="wk-outline__label">1. {{ LABELS.topic }}</h4>
        <p class="wk-outline__text">{{ outline.topic.title }}</p>
      </li>
      <li class="wk-outline__row">
        <h4 class="wk-outline__label">2. {{ LABELS.background }}</h4>
        <p class="rs-muted">이 초안에는 아직 없습니다 — 다음 단계에서 씁니다.</p>
      </li>
      <li class="wk-outline__row">
        <h4 class="wk-outline__label">3. {{ LABELS.prior }}</h4>
        <p class="rs-muted">{{ basisNote }}</p>
        <div class="wk-outline__groups">
          <div
            v-for="(g, gi) in draft.groups"
            :key="g.key"
            class="wk-outline__group"
            :class="{ 'is-drop': dropKey === g.key }"
            @dragover.prevent="onDragOver(g.key)"
            @dragleave="onDragLeave(g.key)"
            @drop.prevent="onDrop(g.key)"
          >
            <label v-if="editing" class="wk-outline__name">
              <span class="rs-sr-only">{{ gi + 1 }}번째 묶음 이름</span>
              <input type="text" :value="g.name" :disabled="busy" @input="onRename(g.key, $event)" />
            </label>
            <p v-else class="wk-outline__name">{{ gi + 1 }}. {{ g.name }}</p>
            <ul class="wk-outline__papers">
              <li
                v-for="cnts in g.papers"
                :key="cnts"
                class="wk-outline__paper"
                :class="{ 'is-dragging': dragging === cnts }"
                :data-paper="cnts"
                :draggable="editing && !busy"
                @dragstart="onDragStart($event, cnts)"
                @dragend="onDragEnd"
              >
                <span class="wk-outline__paper-text" :title="paperTitle(cnts)">
                  <strong v-if="paperWho(cnts)">{{ paperWho(cnts) }}</strong>
                  {{ paperTitle(cnts) }}
                </span>
                <select
                  v-if="editing && draft.groups.length > 1"
                  class="wk-outline__move"
                  :aria-label="`「${paperTitle(cnts)}」 다른 묶음으로 옮기기`"
                  :disabled="busy"
                  @change="onMoveSelect(cnts, $event)"
                >
                  <option value="">옮기기…</option>
                  <option v-for="o in otherGroups(g.key)" :key="o.key" :value="o.key">{{ groupName(o) }}</option>
                </select>
              </li>
            </ul>
            <p v-if="!g.papers.length" class="rs-muted">빈 묶음 — 논문을 끌어 오거나 [옮기기]로 넣으세요</p>
          </div>
        </div>
        <p class="rs-sr-only" role="status">{{ moveNote }}</p>
      </li>
      <li class="wk-outline__row">
        <h4 class="wk-outline__label">4. {{ LABELS.gap }}</h4>
        <p class="rs-muted">보고서의 향후 과제와 근거가 부족했던 하위질문으로 씁니다 — {{ gapNote }}로만 적습니다.</p>
      </li>
      <li class="wk-outline__row">
        <h4 class="wk-outline__label">5. {{ LABELS.question }}</h4>
        <template v-if="editing">
          <fieldset class="wk-outline__choices">
            <legend class="rs-sr-only">연구 질문 후보</legend>
            <label v-for="(q, qi) in outline.questions" :key="qi" class="wk-outline__choice">
              <input
                type="radio"
                name="wk-outline-question"
                :checked="draft.question.trim() === q"
                :disabled="busy"
                @change="setQuestion(q)"
              />
              <span>{{ q }}</span>
            </label>
          </fieldset>
          <label class="wk-outline__field">
            <span class="rs-muted">고른 질문을 다듬으세요</span>
            <textarea :value="draft.question" rows="2" :disabled="busy" @input="onQuestionInput" />
          </label>
        </template>
        <p v-else class="wk-outline__text">{{ outline.question || "아직 고르지 않았습니다" }}</p>
      </li>
      <li class="wk-outline__row">
        <h4 class="wk-outline__label">6. {{ LABELS.method }}</h4>
        <label v-if="editing" class="wk-outline__field">
          <span class="rs-muted">연구 방법을 직접 적으세요 — 이 단계에는 고를 선택지가 없습니다</span>
          <textarea :value="draft.method" rows="3" :disabled="busy" @input="onMethodInput" />
        </label>
        <p v-else class="wk-outline__text">{{ outline.method || "아직 적지 않았습니다" }}</p>
      </li>
    </ol>
    <p class="rs-muted">결과·논의 — 연구 후 직접 씁니다.</p>

    <ul v-if="editing && problems.length" class="wk-outline__problems">
      <li v-for="p in problems" :key="p">{{ p }}</li>
    </ul>
    <div v-if="!readOnly" class="rs-card__actions">
      <template v-if="editing">
        <button v-if="!approved" type="button" class="rs-btn rs-btn--ghost" :disabled="!canSave" @click="submit(false)">
          저장
        </button>
        <button type="button" class="rs-btn" :disabled="!canApprove" @click="submit(true)">
          {{ approved ? "고친 목차로 다시 승인" : "목차 승인" }}
        </button>
        <button v-if="approved" type="button" class="rs-btn rs-btn--ghost" :disabled="busy" @click="stopEditing">
          그만두기
        </button>
      </template>
      <button v-else type="button" class="rs-btn rs-btn--ghost" :disabled="busy" @click="editing = true">목차 고치기</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import type { OutlinePut, ProposalView } from "~/types/work";
import { citeLabel } from "~/utils/citations";
import {
  draftFrom,
  isFallbackOutline,
  movePaper,
  outlineProblems,
  renameGroup,
  toOutlinePut,
  type OutlineDraft,
} from "~/utils/outlineEdit";

const props = defineProps<{ proposal: ProposalView; readOnly: boolean; busy: boolean }>();
const emit = defineEmits<{ save: [body: OutlinePut] }>();

const LABELS = {
  topic: "주제",
  background: "연구 배경",
  prior: "선행연구 검토",
  gap: "연구 공백",
  question: "연구 질문",
  method: "방법 제안",
} as const;
const gapNote = "소장 코퍼스에서 확인하지 않은 공백 후보";
const EMPTY: OutlineDraft = { groups: [], question: "", method: "" };

const outline = computed(() => props.proposal.outline);
const approved = computed(() => outline.value?.state === "approved");
const fallback = computed(() => !!outline.value && isFallbackOutline(outline.value));
const base = computed<OutlineDraft>(() => (outline.value ? draftFrom(outline.value) : EMPTY));
const draft = ref<OutlineDraft>(base.value);
// 승인한 목차는 읽기로 보이고 [목차 고치기]로 연다. 예시 연구는 늘 읽기다
const editing = ref(!approved.value && !props.readOnly);

// 서버의 목차가 바뀌면(저장·승인·다시 만들기·다른 곳에서 고침) 고치던 것을 버리고 새 목차에서 다시 시작한다.
// 절 생성처럼 목차가 아닌 것으로 version 만 오른 다시 읽기에서는 고치던 것을 지킨다 — 그래서 글자로 견준다
watch(
  () => JSON.stringify([base.value, outline.value?.state]),
  () => {
    draft.value = base.value;
    editing.value = !approved.value && !props.readOnly;
  },
);

const dirty = computed(
  () => JSON.stringify(toOutlinePut(draft.value, false)) !== JSON.stringify(toOutlinePut(base.value, false)),
);
const problems = computed(() => outlineProblems(draft.value, true));
const canSave = computed(() => !props.busy && dirty.value && outlineProblems(draft.value, false).length === 0);
// 승인한 목차를 고칠 때는 바뀐 것이 있어야 다시 승인한다
const canApprove = computed(() => !props.busy && problems.value.length === 0 && (!approved.value || dirty.value));

const basisNote = computed(() => {
  const why =
    outline.value?.basis === "subq"
      ? "핵심 개념이 비어 담은 논문의 하위질문 소속으로 묶음을 나눴습니다."
      : "묶음 수와 배정은 담은 논문의 핵심 개념 소속으로 서버가 정했습니다.";
  return editing.value ? `${why} 논문을 끌어 놓거나 [옮기기]로 다른 묶음에 넣을 수 있습니다.` : why;
});

function paperTitle(cnts: string): string {
  return props.proposal.papers[cnts]?.title?.trim() || cnts;
}

function paperWho(cnts: string): string {
  const meta = props.proposal.papers[cnts];
  return meta ? citeLabel(meta, "") : "";
}

function groupName(g: { key: string; name: string }): string {
  return g.name.trim() || g.key;
}

function otherGroups(key: string): OutlineDraft["groups"] {
  return draft.value.groups.filter((g) => g.key !== key);
}

function onRename(key: string, e: Event): void {
  draft.value = renameGroup(draft.value, key, (e.target as HTMLInputElement).value);
}

function setQuestion(q: string): void {
  draft.value = { ...draft.value, question: q };
}

function onQuestionInput(e: Event): void {
  setQuestion((e.target as HTMLTextAreaElement).value);
}

function onMethodInput(e: Event): void {
  draft.value = { ...draft.value, method: (e.target as HTMLTextAreaElement).value };
}

// ── 끌어 옮기기 ──────────────────────────────────────────
// 끄는 논문은 dataTransfer 가 아니라 이 상태로 기억한다 — dragover 중에는 dataTransfer 를 읽을 수 없는 브라우저가 있다
const dragging = ref<string | null>(null);
const dropKey = ref<string | null>(null);

function onDragStart(e: DragEvent, cnts: string): void {
  if (!editing.value || props.busy) {
    e.preventDefault();
    return;
  }
  dragging.value = cnts;
  // Firefox 는 dataTransfer 에 무엇이든 실어야 끌기를 시작한다
  e.dataTransfer?.setData("text/plain", cnts);
  if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
}

function onDragOver(key: string): void {
  if (dragging.value) dropKey.value = key;
}

function onDragLeave(key: string): void {
  if (dropKey.value === key) dropKey.value = null;
}

function onDrop(key: string): void {
  if (dragging.value) move(dragging.value, key, false);
  onDragEnd();
}

function onDragEnd(): void {
  dragging.value = null;
  dropKey.value = null;
}

// ── 키보드로 옮기기(옮기기 메뉴) ──────────────────────────
const moveNote = ref("");

function onMoveSelect(cnts: string, e: Event): void {
  const select = e.target as HTMLSelectElement;
  const to = select.value;
  select.value = "";
  if (to) move(cnts, to, true);
}

// 메뉴로 옮긴 논문은 새 묶음에서 다시 그려져 초점이 사라진다 — 그 논문의 메뉴로 초점을 돌려 이어서 옮기게 한다
function move(cnts: string, to: string, refocus: boolean): void {
  const next = movePaper(draft.value, cnts, to);
  if (next === draft.value) return;
  draft.value = next;
  const target = next.groups.find((g) => g.key === to);
  moveNote.value = `「${paperTitle(cnts)}」을 「${target ? groupName(target) : to}」 묶음으로 옮겼습니다`;
  if (!refocus) return;
  void nextTick(() => {
    document.querySelector<HTMLSelectElement>(`[data-paper="${CSS.escape(cnts)}"] select`)?.focus();
  });
}

function submit(approve: boolean): void {
  emit("save", toOutlinePut(draft.value, approve));
}

function stopEditing(): void {
  draft.value = base.value;
  editing.value = false;
}
</script>
