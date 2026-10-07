<!-- frontend/components/work/ProposalSection.vue -->
<template>
  <section :id="`wk-sec-${sectionKey}`" class="rs-card wk-psec" :aria-labelledby="`wk-sec-title-${sectionKey}`">
    <header class="wk-psec__head">
      <h3 :id="`wk-sec-title-${sectionKey}`" class="rs-card__title">{{ label }}</h3>
      <span class="rs-badge" :class="STATUS_BADGES[status]">{{ STATUS_LABELS[status] }}</span>
      <span v-if="stale" class="rs-badge wk-psec__stale">다시 맞춤 필요</span>
      <button
        v-if="!readOnly && status !== 'queued' && status !== 'writing'"
        type="button"
        class="rs-btn rs-btn--small wk-psec__write"
        :disabled="locked"
        @click="onWrite"
      >
        {{ section ? "이 절 다시 쓰기" : "이 절 쓰기" }}
      </button>
    </header>
    <p v-if="note" class="rs-muted">{{ note }}</p>
    <p v-if="stale" class="rs-muted">
      이 절을 쓴 뒤 주제나 목차의 묶음이 바뀌었습니다. 쓴 문단은 그대로 두었습니다 — 바뀐 목차로 맞추려면 이 절을 다시
      쓰세요.
    </p>

    <p v-if="status === 'queued'" class="rs-muted" role="status">
      쓸 차례를 기다리는 중입니다{{ queueText ? ` · ${queueText}` : "" }}
    </p>
    <div v-else-if="status === 'writing'" class="wk-psec__live">
      <template v-if="!finishing && live && !live.broken && live.text">
        <p v-for="(parts, li) in liveBlocks" :key="li" class="wk-psec__para is-live">
          <template v-for="(part, ti) in parts" :key="ti">
            <template v-if="part.type === 'text'">{{ part.text }}</template>
            <span
              v-else-if="part.type === 'cite'"
              class="wk-psec__cite"
              :class="{ 'is-pending': !liveEvidence }"
              :title="paperTitle(liveEvidence?.[part.eid])"
            >{{ citeText(liveEvidence?.[part.eid], part.eid) }}</span>
            <s v-else-if="part.type === 'badcite'" class="wk-psec__badcite" title="이 절의 근거 번호가 아닙니다 — 저장할 때 버립니다">[{{ part.eid }}]</s>
            <FigureChip v-else-if="figureOf(liveFigures, part.fid)" :figure="figureOf(liveFigures, part.fid)!" />
            <span v-else class="wk-psec__cite is-pending">[{{ part.fid }}]</span>
          </template>
        </p>
      </template>
      <template v-else>
        <p class="rs-muted" role="status">
          {{
            finishing
              ? "다 썼습니다 — 문단을 불러오는 중입니다"
              : live?.broken
                ? "글을 받는 중입니다 — 다 쓰면 한 번에 보입니다"
                : "쓰기 시작하는 중입니다"
          }}
        </p>
        <div class="rs-skeleton" aria-hidden="true">
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
        </div>
      </template>
    </div>
    <div v-else-if="status === 'failed'" class="wk-psec__failed" role="alert">
      <p class="rs-muted">{{ failedText }}</p>
      <button
        v-if="failedGen && !readOnly"
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="locked"
        @click="onRetry(failedGen.id)"
      >
        다시 시도
      </button>
    </div>

    <ol v-if="section && status !== 'writing'" class="wk-psec__paras">
      <li
        v-for="p in section.paragraphs"
        :key="p.id"
        class="wk-psec__item"
        :class="`is-${p.state}`"
        :data-anchor="paraAnchor(sectionKey, p.id)"
      >
        <span class="wk-psec__band">{{ STATE_LABELS[p.state] }}</span>
        <div v-if="editingId === p.id" class="wk-psec__edit">
          <label>
            <span class="rs-sr-only">문단 고치기</span>
            <textarea v-model="editText" rows="6" :disabled="busy" />
          </label>
          <p class="rs-muted">인용 표시([E1])와 수치 표시([F1])는 그대로 두세요 — 지우면 인용·수치가 빠집니다.</p>
          <p v-if="editProblem" class="rs-muted" role="status">{{ editProblem }}</p>
          <div class="rs-card__actions">
            <button type="button" class="rs-btn rs-btn--small" :disabled="locked || !!editProblem" @click="saveEdit(p.id)">저장</button>
            <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="editingId = null">그만두기</button>
          </div>
        </div>
        <template v-else>
          <p class="wk-psec__para">
            <template v-for="(s, si) in sentenceFlags(p.text)" :key="si">
              <span :class="{ 'wk-psec__unmarked': s.unmarked }" :title="s.unmarked ? '근거 표시가 없는 문장' : undefined">
                <template v-for="(part, ti) in paragraphParts(s.text, section.evidence)" :key="ti">
                  <template v-if="part.type === 'text'">{{ part.text }}</template>
                  <a
                    v-else-if="part.type === 'cite'"
                    class="wk-psec__cite"
                    :href="detailHref(section.evidence[part.eid] ?? '', p.id, null)"
                    :title="paperTitle(section.evidence[part.eid])"
                    @click="goDetail($event, section.evidence[part.eid] ?? '', p.id)"
                    @auxclick="goDetail($event, section.evidence[part.eid] ?? '', p.id)"
                    @contextmenu="goDetail($event, section.evidence[part.eid] ?? '', p.id)"
                  >{{ citeText(section.evidence[part.eid], part.eid) }}</a>
                  <s v-else-if="part.type === 'badcite'" class="wk-psec__badcite">[{{ part.eid }}]</s>
                  <FigureChip v-else-if="figureOf(section.figures, part.fid)" :figure="figureOf(section.figures, part.fid)!" />
                  <span v-else class="wk-psec__cite is-pending">[{{ part.fid }}]</span>
                </template>
              </span>
              <span v-if="s.numbers.length" class="wk-psec__check" :title="`[F#] 밖에서 쓴 숫자 — 원문과 맞는지 확인하세요`">
                확인 필요 {{ s.numbers.join(", ") }}
              </span>
            </template>
          </p>
          <p v-if="checkLine(p.checks)" class="rs-muted">{{ checkLine(p.checks) }}</p>
          <p v-if="paragraphGen(p.id)" class="rs-muted" role="status">
            이 문단을 다시 쓰는 중입니다{{ paragraphQueue(p.id) ? ` · ${paragraphQueue(p.id)}` : "" }}
          </p>
          <div v-else-if="!readOnly" class="wk-psec__para-actions">
            <button
              v-if="p.state === 'proposed'"
              type="button"
              class="rs-btn rs-btn--small"
              :disabled="locked"
              @click="emit('save', acceptParagraph(section, p.id))"
            >
              수락
            </button>
            <button
              v-if="p.state === 'proposed' || p.state === 'accepted'"
              type="button"
              class="rs-btn rs-btn--small rs-btn--ghost"
              :disabled="locked"
              @click="emit('regenerate', p.id)"
            >
              다시
            </button>
            <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="locked" @click="startEdit(p.id, p.text)">
              고치기
            </button>
            <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="locked" @click="remove(p.id)">지우기</button>
          </div>
        </template>
      </li>
    </ol>

    <div v-if="section && !readOnly && status !== 'writing'" class="wk-psec__add">
      <template v-if="adding">
        <label>
          <span class="rs-sr-only">더할 문단</span>
          <textarea v-model="addText" rows="4" :disabled="busy" placeholder="직접 쓸 문단 — 인용하려면 이 절의 [E1] 표기를 그대로 쓰세요" />
        </label>
        <p v-if="addText && addProblem" class="rs-muted" role="status">{{ addProblem }}</p>
        <div class="rs-card__actions">
          <button type="button" class="rs-btn rs-btn--small" :disabled="locked || !!addProblem" @click="saveAdd">더하기</button>
          <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="adding = false">그만두기</button>
        </div>
      </template>
      <button
        v-else
        type="button"
        class="rs-btn rs-btn--small rs-btn--ghost"
        :disabled="locked || section.paragraphs.length >= MAX_PARAGRAPHS_PUT"
        @click="adding = true"
      >
        문단 직접 쓰기
      </button>
    </div>
    <p v-if="!section && status === 'empty'" class="rs-muted">
      아직 쓰지 않은 절입니다. [이 절 쓰기]를 누르면 문장이 흘러나오고, 끝나면 문단마다 [수락]·[다시]·[고치기]로 받아들입니다.
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import FigureChip from "~/components/work/FigureChip.vue";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { Figure, ParaState, ProposalView, SectionPut, WorkState } from "~/types/work";
import { citeLabel } from "~/utils/citations";
import { detailUrl, paraAnchor } from "~/utils/detailSource";
import { figureById, sentenceFlags, splitMarkers } from "~/utils/figureMarkers";
import {
  GAP_NOTE,
  MAX_PARAGRAPHS_PUT,
  acceptParagraph,
  addParagraph,
  checkLine,
  editParagraph,
  paragraphParts,
  paragraphProblem,
  removeParagraph,
  sectionStatus,
  type ParaPart,
  type SectionStatus,
} from "~/utils/proposalView";
import { genQueueLine } from "~/utils/queueLine";
import { isPlainClick, spotOf } from "~/utils/restorePosition";
import { latestGeneration, openGeneration } from "~/utils/workEvents";

const props = defineProps<{
  sectionKey: string;
  label: string;
  proposal: ProposalView;
  state: WorkState;
  readOnly: boolean;
  busy: boolean;
  jobId: string;
}>();
const emit = defineEmits<{ write: []; save: [body: SectionPut]; regenerate: [pid: string]; retry: [genId: number] }>();

const STATUS_LABELS: Record<SectionStatus, string> = {
  empty: "쓰기 전",
  queued: "대기 중",
  writing: "쓰는 중",
  done: "씀",
  failed: "실패",
};
const STATUS_BADGES: Record<SectionStatus, string> = {
  empty: "",
  queued: "rs-badge--running",
  writing: "rs-badge--running",
  done: "rs-badge--done",
  failed: "rs-badge--failed",
};
// 'AI 작성' 띠는 수락해도 남는다 — 사용자가 고친 문단도 AI 가 처음 쓴 문단이다
const STATE_LABELS: Record<ParaState, string> = {
  proposed: "AI 제안 · 검토 전",
  accepted: "AI 작성 · 수락",
  edited: "AI 작성 · 고침",
  authored: "직접 작성",
};

const section = computed(() => props.proposal.sections[props.sectionKey] ?? null);
const status = computed(() => sectionStatus(props.sectionKey, props.state));
const stale = computed(() => !!section.value && props.proposal.stale.sections[props.sectionKey] === true);
const note = computed(() => section.value?.note ?? (props.sectionKey === "gap" ? `${GAP_NOTE}로만 씁니다` : null));
const openSection = computed(() => openGeneration(props.state, "section", props.sectionKey));
const queueText = computed(() => (openSection.value ? genQueueLine(openSection.value) : null));
// 끝났지만 계획서를 다시 읽기 전이라 아직 절에 오지 않은 결과(sectionStatus 의 쓰는 중) — 흐르던 글은 이미 지워졌다
const finishing = computed(() => status.value === "writing" && !openSection.value);
// 실패로 보이는 생성 — failed, 또는 빈 결과로 끝난 done(세 번 다 검사를 못 넘음 — 서버 retry 가 받는다)
const failedGen = computed(() =>
  status.value === "failed" ? latestGeneration(props.state, "section", props.sectionKey) : null,
);
const failedText = computed(() => {
  const head =
    failedGen.value?.status === "done"
      ? "근거 표시가 있는 문단을 얻지 못했습니다"
      : section.value
        ? "이 절을 다시 쓰지 못했습니다"
        : "이 절을 쓰지 못했습니다";
  return section.value?.paragraphs.length
    ? `${head} — 앞서 쓴 문단은 그대로 두었습니다.`
    : `${head}. 다시 시도하거나 잠시 뒤 다시 쓰세요.`;
});

function paragraphGen(pid: string) {
  return openGeneration(props.state, "paragraph", `${props.sectionKey}#${pid}`);
}

function paragraphQueue(pid: string): string | null {
  const g = paragraphGen(pid);
  return g ? genQueueLine(g) : null;
}

// 절이나 그 절의 문단을 쓰는 동안 서버는 그 절의 쓰기(PUT·다시 쓰기)를 409 로 막는다 — 미리 잠근다.
// 열어 둔 고치기·직접 쓰기 칸의 [저장]·[더하기]도 이것으로 잠근다(busy 를 품는다)
const locked = computed(
  () =>
    props.busy ||
    status.value === "queued" ||
    status.value === "writing" ||
    (section.value?.paragraphs.some((p) => !!paragraphGen(p.id)) ?? false),
);

// ── 스트리밍 중인 글 ─────────────────────────────────────
// 칩을 그릴 근거 지도는 이 생성의 입력(drafts)이다. 다시 읽기 전이라 지도가 없거나 다른 생성의 것이면 번호를 그대로 둔다
const live = computed(() => props.state.live[props.sectionKey] ?? null);
const liveDraft = computed(() => {
  const draft = props.proposal.drafts[props.sectionKey];
  return draft && live.value && draft.gen_id === live.value.genId ? draft : null;
});
const liveEvidence = computed(() => liveDraft.value?.evidence ?? null);
const liveFigures = computed<Figure[]>(() => liveDraft.value?.figures ?? []);
const liveBlocks = computed<ParaPart[][]>(() =>
  (live.value?.text ?? "")
    .split(/\n\s*\n/)
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => (liveEvidence.value ? paragraphParts(t, liveEvidence.value) : splitMarkers(t))),
);

function figureOf(figures: Figure[], fid: string): Figure | null {
  return figureById(figures, fid);
}

function paperTitle(cnts: string | undefined): string {
  return (cnts && props.proposal.papers[cnts]?.title?.trim()) || "";
}

function citeText(cnts: string | undefined, eid: string): string {
  return citeLabel(cnts ? props.proposal.papers[cnts] : undefined, eid);
}

// ── 논문 상세로 — 돌아오면 이 문단에 맞춘다 ───────────────
const { leave } = useDetailLeave();

function detailHref(cnts: string, pid: string, y: number | null): string {
  return detailUrl(
    cnts,
    { kind: "research", job: props.jobId, e: null, s: "proposal" },
    { at: paraAnchor(props.sectionKey, pid), y },
  );
}

function goDetail(e: MouseEvent, cnts: string, pid: string): void {
  if (!cnts) return;
  const at = paraAnchor(props.sectionKey, pid);
  const item = (e.currentTarget as HTMLElement).closest<HTMLElement>("[data-anchor]");
  const spot = item ? spotOf(item, at) : { at, y: null };
  const url = detailHref(cnts, pid, spot.y);
  if (e.type === "contextmenu" || !isPlainClick(e)) {
    (e.currentTarget as HTMLAnchorElement).href = url;
    return;
  }
  e.preventDefault();
  void leave(url, spot);
}

// ── 쓰기·고치기 ──────────────────────────────────────────
function onWrite(): void {
  const kept = section.value?.paragraphs.some((p) => p.state !== "proposed") ?? false;
  if (kept && !window.confirm("이 절을 다시 쓰면 지금 문단(수락·고친·직접 쓴 문단 포함)을 새 초안으로 바꿉니다. 다시 쓸까요?")) {
    return;
  }
  emit("write");
}

// [다시 시도] — 앞서 쓴 절이 있으면 [이 절 다시 쓰기]와 같다(지금 목차·담은 논문으로 새로 쓰고, 수락·고친·직접 쓴
// 문단이 있으면 확인을 묻는다). 실패한 생성을 그대로 다시 부르면(retry) 옛 입력을 다시 넣어 그 사이 바뀐 목차를
// 놓치고, 결과가 그 뒤 수락·고친 문단을 확인 없이 통째로 덮는다. 쓴 절이 없으면 덮을 문단이 없어 같은 생성을 다시 부른다
function onRetry(genId: number): void {
  if (section.value) {
    onWrite();
    return;
  }
  emit("retry", genId);
}

function remove(pid: string): void {
  if (!section.value || !window.confirm("이 문단을 지울까요?")) return;
  emit("save", removeParagraph(section.value, pid));
}

const editingId = ref<string | null>(null);
const editText = ref("");
const editProblem = computed(() => paragraphProblem(editText.value));
const adding = ref(false);
const addText = ref("");
const addProblem = computed(() => paragraphProblem(addText.value));
// 저장을 보낸 뒤 결과가 화면에 올 때까지 고치던 글을 쥐고 있다 — 실패(버전 충돌 등)하면 그대로 남아 다시 보낼 수 있다
type Pending = { kind: "edit"; id: string; before: string } | { kind: "add"; count: number };
let pending: Pending | null = null;

// 절을 새 생성으로 다시 쓰면 서버가 문단 id 를 p1 부터 다시 매기고 근거 지도도 바뀔 수 있다 — 열어 둔 칸을
// 그대로 두면 옛 글이 같은 id 의 새 문단에 다시 열려 [저장] 하면 새 문단을 덮고 [E#] 가 다른 논문에 붙는다.
// 다시 쓰기가 실패·취소되면 gen_id 가 그대로라 고치던 글을 지킨다(옛 문단이 그대로 남아 있다)
watch(
  () => section.value?.gen_id,
  () => {
    editingId.value = null;
    editText.value = "";
    adding.value = false;
    addText.value = "";
    pending = null;
  },
);

function startEdit(pid: string, text: string): void {
  editingId.value = pid;
  editText.value = text;
}

function saveEdit(pid: string): void {
  const sec = section.value;
  const text = editText.value.trim();
  const before = sec?.paragraphs.find((p) => p.id === pid)?.text;
  if (!sec || before === undefined) return;
  if (text === before) {
    editingId.value = null;
    return;
  }
  pending = { kind: "edit", id: pid, before };
  emit("save", editParagraph(sec, pid, text));
}

function saveAdd(): void {
  const sec = section.value;
  if (!sec) return;
  pending = { kind: "add", count: sec.paragraphs.length };
  emit("save", addParagraph(sec, addText.value.trim()));
}

watch(
  () => props.busy,
  (now, was) => {
    const p = pending;
    if (!was || now || !p) return;
    pending = null;
    const paragraphs = section.value?.paragraphs ?? [];
    if (p.kind === "edit") {
      if (paragraphs.find((x) => x.id === p.id)?.text !== p.before) editingId.value = null;
    } else if (paragraphs.length > p.count) {
      adding.value = false;
      addText.value = "";
    }
  },
);
</script>
