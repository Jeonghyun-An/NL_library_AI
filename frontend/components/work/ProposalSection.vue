<!-- frontend/components/work/ProposalSection.vue -->
<template>
  <section :id="`wk-sec-${sectionKey}`" ref="rootEl" class="rs-card wk-psec" :aria-labelledby="`wk-sec-title-${sectionKey}`">
    <header class="wk-psec__head">
      <!-- tabindex="-1" — 보고서 화면의 머리 목차가 이 제목으로 초점을 옮긴다 -->
      <h3 :id="`wk-sec-title-${sectionKey}`" class="rs-card__title" tabindex="-1">{{ label }}</h3>
      <span class="rs-badge" :class="STATUS_BADGES[status]">{{ skippedNow ? "근거 없음" : STATUS_LABELS[status] }}</span>
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
      이 절을 쓴 뒤 주제나 목차의 묶음·연구 질문이 바뀌었어요.<br />
      쓴 문단은 그대로 두었어요 — 바뀐 목차로 맞추려면 [이 절 다시 쓰기]를 눌러 주세요.
    </p>

    <p v-if="status === 'queued'" class="rs-muted" role="status">
      쓸 차례를 기다리는 중이에요{{ queueText ? ` · ${queueText}` : "" }}
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
            <s v-else-if="part.type === 'badcite'" class="wk-psec__badcite" title="이 절의 근거 번호가 아니에요 — 저장할 때 버려요">[{{ part.eid }}]</s>
            <FigureChip v-else-if="figureOf(liveFigures, part.fid)" :figure="figureOf(liveFigures, part.fid)!" />
            <span v-else class="wk-psec__cite is-pending">[{{ part.fid }}]</span>
          </template>
        </p>
      </template>
      <template v-else>
        <p class="rs-muted" role="status">
          {{
            finishing
              ? "다 썼어요 — 문단을 불러오는 중이에요"
              : live?.broken
                ? "글을 받는 중이에요 — 다 쓰면 한 번에 보여요"
                : "쓰기 시작하는 중이에요"
          }}
        </p>
        <div class="rs-skeleton" aria-hidden="true">
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
          <span class="rs-skeleton__line" />
        </div>
      </template>
    </div>
    <!-- 실패한 절 — 공통 줄 안내와 [다시 시도](예시 연구·생성 기록이 없으면 글만). 잠긴 동안은 누름을 무시한다 -->
    <SkxInlineError
      v-else-if="status === 'failed'"
      :message="failedText"
      :busy="locked"
      :on-retry="failedGen && !readOnly ? retryFailed : undefined"
    />

    <ol v-if="section && status !== 'writing'" class="wk-psec__paras">
      <li
        v-for="({ p, sentences, check }, pi) in paraViews"
        :key="p.id"
        class="wk-psec__item"
        :class="`is-${p.state}`"
        :data-anchor="paraAnchor(sectionKey, p.id)"
        tabindex="-1"
      >
        <span :id="bandId(p.id)" class="wk-psec__band">{{ STATE_LABELS[p.state] }}</span>
        <div v-if="editingId === p.id" class="wk-psec__edit">
          <label>
            <span class="rs-sr-only">{{ paraName(pi) }} 고치기</span>
            <textarea v-model="editText" data-edit-box rows="6" :disabled="busy" />
          </label>
          <p class="rs-muted">인용 표시([E1])와 수치 표시([F1])는 그대로 둬 주세요 — 지우면 인용·수치가 빠져요.</p>
          <p v-if="editProblem" class="rs-muted" role="status">{{ editProblem }}</p>
          <div class="rs-card__actions">
            <button type="button" class="rs-btn rs-btn--small" :disabled="locked || !!editProblem" @click="saveEdit(p.id)">저장</button>
            <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="editingId = null">그만두기</button>
          </div>
        </div>
        <template v-else>
          <p class="wk-psec__para">
            <template v-for="(s, si) in sentences" :key="si">
              <span
                class="wk-psec__sent"
                :class="{ 'wk-psec__unmarked': s.unmarked, 'is-cited': isActiveSentence(p.id, si) }"
                :title="s.unmarked ? '근거 표시가 없는 문장' : undefined"
              >
                <template v-for="(part, ti) in s.parts" :key="ti">
                  <template v-if="part.type === 'text'">{{ part.text }}</template>
                  <button
                    v-else-if="part.type === 'cite'"
                    type="button"
                    class="wk-psec__cite"
                    :data-cite="citeKey(p.id, si, part.eid)"
                    :aria-expanded="isOpenCite(p.id, si, part.eid)"
                    :aria-controls="isOpenCite(p.id, si, part.eid) ? panelId : undefined"
                    :title="paperTitle(section.evidence[part.eid])"
                    @click="onCite($event, p.id, si, part.eid, s.text)"
                  >{{ citeText(section.evidence[part.eid], part.eid) }}</button>
                  <s v-else-if="part.type === 'badcite'" class="wk-psec__badcite">[{{ part.eid }}]</s>
                  <FigureChip v-else-if="figureOf(section.figures, part.fid)" :figure="figureOf(section.figures, part.fid)!" />
                  <span v-else class="wk-psec__cite is-pending">[{{ part.fid }}]</span>
                </template>
                <span v-if="s.unmarked" class="rs-sr-only">(근거 표시 없음)</span>
              </span>
              <span v-if="s.numbers.length" class="wk-psec__check" title="[F#] 밖에서 쓴 숫자 — 원문과 맞는지 확인해 주세요">
                확인 필요 {{ s.numbers.join(", ") }}
              </span>
            </template>
          </p>
          <p v-if="check" class="rs-muted">{{ check }}</p>
          <SkxInlineError v-if="failedParas.has(p.id)" message="이 문단을 다시 쓰지 못했어요 — 앞의 글을 그대로 두었어요." />
          <p v-if="paragraphGens.has(p.id)" class="rs-muted" role="status">
            이 문단을 다시 쓰는 중이에요{{ paragraphQueue(p.id) ? ` · ${paragraphQueue(p.id)}` : "" }}
          </p>
          <div v-else-if="!readOnly" class="wk-psec__para-actions">
            <button
              v-if="p.state === 'proposed'"
              type="button"
              class="rs-btn rs-btn--small"
              :disabled="locked"
              :aria-describedby="bandId(p.id)"
              @click="emit('save', acceptParagraph(section, p.id))"
            >
              수락<span class="rs-sr-only"> {{ paraName(pi) }}</span>
            </button>
            <button
              v-if="p.state === 'proposed' || p.state === 'accepted'"
              type="button"
              class="rs-btn rs-btn--small rs-btn--ghost"
              :disabled="locked"
              :aria-describedby="bandId(p.id)"
              @click="emit('regenerate', p.id)"
            >
              다시<span class="rs-sr-only"> {{ paraName(pi) }}</span>
            </button>
            <button
              type="button"
              class="rs-btn rs-btn--small rs-btn--ghost"
              :disabled="locked"
              :aria-describedby="bandId(p.id)"
              :data-edit-for="p.id"
              @click="startEdit(p.id, p.text)"
            >
              고치기<span class="rs-sr-only"> {{ paraName(pi) }}</span>
            </button>
            <button
              type="button"
              class="rs-btn rs-btn--small rs-btn--ghost"
              :disabled="locked"
              :aria-describedby="bandId(p.id)"
              @click="remove(p.id)"
            >
              지우기<span class="rs-sr-only"> {{ paraName(pi) }}</span>
            </button>
          </div>
        </template>
      </li>
    </ol>

    <div v-if="section && !readOnly && status !== 'writing'" class="wk-psec__add">
      <template v-if="adding">
        <label>
          <span class="rs-sr-only">더할 문단</span>
          <textarea v-model="addText" data-add-box rows="4" :disabled="busy" placeholder="직접 쓸 문단 — 인용하려면 이 절의 [E1] 표기를 그대로 써 주세요" />
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
        data-add-open
        @click="adding = true"
      >
        문단 직접 쓰기
      </button>
    </div>
    <!-- 근거 없음 409 는 사실상 연구 공백 절에서만 난다 — 그 논문은 담은 논문·묶음이 아니라 고른 주제의 씨앗에서 온다 -->
    <p v-if="skippedNow" class="rs-muted" role="status">
      근거가 없어 쓰지 않았어요 — 이 절은 고른 주제의 씨앗({{ DEEP_RESEARCH }} 보고서의 향후 과제·근거가 부족했던
      하위질문)에 이은 논문으로 쓰는데, 이은 논문이 없어요.<br />
      다른 주제를 고른 뒤 [{{ REMAKE_REPORT }}]로 맞춰 주세요.
    </p>
    <!-- '자동으로 써요'는 연쇄가 이 절을 곧 넣을 때만 — 06b 때 승인한 목차·취소로 끝난 절·연쇄가 멈춘 동안은 손으로 쓴다 -->
    <p v-else-if="!section && status === 'empty' && autoNext" class="rs-muted">
      아직 쓰지 않은 절이에요 — 차례가 오면 자동으로 써요.<br />
      지금 쓰려면 [이 절 쓰기]를 눌러 주세요.
    </p>
    <p v-else-if="!section && status === 'empty'" class="rs-muted">
      아직 쓰지 않은 절이에요.<br />
      [이 절 쓰기]를 누르면 문장이 흘러나오고, 끝나면 문단마다 [수락]·[다시]·[고치기]로 다듬을 수 있어요.
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import FigureChip from "~/components/work/FigureChip.vue";
import type { CitePick, Figure, ParaState, ProposalView, SectionPut, WorkState } from "~/types/work";
import { DEEP_RESEARCH } from "~/utils/brand";
import { citedQuote } from "~/utils/citationEvidence";
import { citeLabel } from "~/utils/citations";
import { paraAnchor } from "~/utils/detailSource";
import { figureById, spaceBeforeCites, splitMarkers } from "~/utils/figureMarkers";
import {
  GAP_NOTE,
  MAX_PARAGRAPHS_PUT,
  acceptParagraph,
  addParagraph,
  editParagraph,
  failedParagraphGens,
  openParagraphGens,
  paragraphParts,
  paragraphProblem,
  paragraphViews,
  removeParagraph,
  sectionStatus,
  type ParaPart,
  type SectionStatus,
} from "~/utils/proposalView";
import { genQueueLine } from "~/utils/queueLine";
import { latestGeneration, openGeneration } from "~/utils/workEvents";
import { REMAKE_REPORT } from "~/utils/workPhase";

const props = defineProps<{
  sectionKey: string;
  label: string;
  proposal: ProposalView;
  state: WorkState;
  readOnly: boolean;
  busy: boolean;
  // 오른쪽 패널이 보이는 인용 — ProposalStep 이 이 절의 것만 넘긴다. 그 문장을 강조하고 그 칩을 펼침으로 둔다
  activeCite?: { pid: string; si: number; eid?: string } | null;
  // 오른쪽 패널의 id — 칩의 aria-controls
  panelId?: string;
  // 보고서 자동 산출이 근거가 없어(409 no_section_papers) 건너뛴 절 — 이 방문만(06e)
  skipped?: boolean;
  // 보고서 자동 산출이 이 절을 곧 넣을 참이다(연쇄가 돌고 멈추지 않았고 남은 절에 든다) — 쓰기 전 안내가 '자동으로 써요'
  autoNext?: boolean;
  // 이 절의 저장(PUT) 응답을 받을 때마다 오르는 수(ProposalStep) — 뒤의 다시 읽기가 실패해 절이 그대로여도 저장은 된 것이라
  // 열어 둔 고치기·직접 쓰기 칸을 닫는다(열린 채 다시 누르면 옛 version 이라 409 가 난다)
  savedSeq?: number;
}>();
const emit = defineEmits<{
  write: [];
  save: [body: SectionPut];
  regenerate: [pid: string];
  retry: [genId: number];
  // 인용 칩 — 누른 칩(초점을 돌려줄 자리)과 함께 올린다
  cite: [pick: CitePick, el: HTMLElement];
}>();

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
  // 보고서를 자동으로 쓴 글이라 '제안'을 뺀다(D21) — 저장 값 proposed 는 그대로
  proposed: "AI 작성 · 검토 전",
  accepted: "AI 작성 · 수락",
  edited: "AI 작성 · 고침",
  authored: "직접 작성",
};

const section = computed(() => props.proposal.sections[props.sectionKey] ?? null);
const status = computed(() => sectionStatus(props.sectionKey, props.state));
const stale = computed(() => !!section.value && props.proposal.stale.sections[props.sectionKey] === true);
// 자동 산출이 근거가 없어 건너뛴 쓰기 전 절 — 손으로 다시 쓰기 시작하면(대기·쓰는 중) 그 상태를 보인다
const skippedNow = computed(() => !!props.skipped && !section.value && status.value === "empty");
const note = computed(() => section.value?.note ?? (props.sectionKey === "gap" ? `${GAP_NOTE}로만 써요` : null));
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
      ? "근거 표시가 있는 문단을 얻지 못했어요"
      : section.value
        ? "이 절을 다시 쓰지 못했어요"
        : "이 절을 쓰지 못했어요";
  if (section.value?.paragraphs.length) return `${head} — 앞서 쓴 문단은 그대로 두었어요.`;
  // 예시 연구는 읽기 전용이라 [다시 시도]도 쓰기 버튼도 없다 — 할 수 없는 일을 권하지 않는다
  return props.readOnly ? `${head}.` : `${head}.\n다시 시도하거나 잠시 뒤 다시 써 주세요.`;
});

function retryFailed(): void {
  if (failedGen.value) onRetry(failedGen.value.id);
}

// 절 글이 흐르는 동안 조각(section_delta)마다 state 는 새 객체가 되어 모든 절이 다시 그려진다. 그때 문단을 다시
// 나누거나 생성 목록을 다시 훑지 않게, 무거운 계산은 그것이 기대는 값에만 묶는다 — 문단 조각은 절(계획서를 다시 읽을
// 때만 바뀐다)에, 문단 다시 쓰기 생성은 생성 목록(work — 조각으로는 바뀌지 않는다)에
const paraViews = computed(() => (section.value ? paragraphViews(section.value) : []));
const workView = computed(() => props.state.work);
const paragraphGens = computed(() =>
  openParagraphGens(workView.value, props.sectionKey, section.value?.paragraphs.map((p) => p.id) ?? []),
);
const failedParas = computed(() =>
  failedParagraphGens(workView.value, props.sectionKey, section.value?.paragraphs ?? []),
);

// 문단마다 되풀이되는 버튼([수락]·[다시]·[고치기]·[지우기])의 이름에 붙이는 대상(화면에는 보이지 않는다)과, 설명으로
// 잇는 그 문단의 띠(AI 작성 · 검토 전 등) — 스크린리더의 컨트롤 목록에서 어느 절의 몇째 문단인지 구별되게
function paraName(index: number): string {
  return `${props.label} ${index + 1}번째 문단`;
}

function bandId(pid: string): string {
  return `wk-band-${props.sectionKey}-${pid}`;
}

function paragraphQueue(pid: string): string | null {
  const g = paragraphGens.value.get(pid);
  return g ? genQueueLine(g) : null;
}

// 절이나 그 절의 문단을 쓰는 동안 서버는 그 절의 쓰기(PUT·다시 쓰기)를 409 로 막는다 — 미리 잠근다.
// 열어 둔 고치기·직접 쓰기 칸의 [저장]·[더하기]도 이것으로 잠근다(busy 를 품는다)
const locked = computed(
  () => props.busy || status.value === "queued" || status.value === "writing" || paragraphGens.value.size > 0,
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
    .map((t) => (liveEvidence.value ? paragraphParts(t, liveEvidence.value) : spaceBeforeCites(splitMarkers(t)))),
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

// ── 인용 칩 → 오른쪽 인용 근거 패널(D24 A안 — 패널은 ProposalStep 이 쥔다) ──
// 칩은 저장된 문단에서만 패널을 연다 — 흐르는 글(liveBlocks)의 칩은 span 그대로다: 절이 끝나면 문단이 다시 나뉘어
// 문장 번호가 바뀐다. 논문 상세로 떠나는 길은 패널 머리의 [논문 상세 ↗] 가 맡는다(돌아오는 자리는 이 문단)
function citeKey(pid: string, si: number, eid: string): string {
  return `${pid}:${si}:${eid}`;
}

// 누른 칩이 든 문장 — 본문 쪽 강조(sentenceFlags 의 문장 번호). ProposalStep 은 그 번호의 문장이 지금도 누를 때와 같은
// 글일 때만 activeCite 를 넘긴다(activeCiteOf — 문단을 고치거나 다시 쓰면 같은 번호가 다른 문장을 가리킨다)
function isActiveSentence(pid: string, si: number): boolean {
  return props.activeCite?.pid === pid && props.activeCite.si === si;
}

// 패널이 그 칩의 논문을 보이는 중인가 — 한 문장에 칩이 둘이면 누른 칩만 펼침
function isOpenCite(pid: string, si: number, eid: string): boolean {
  return isActiveSentence(pid, si) && (props.activeCite?.eid ?? eid) === eid;
}

// quote — 카드에 보이는 인용한 문장. 누르는 순간의 이 절 수치로 [F#] 를 값으로 바꾼다(citedQuote) — 절을 다시 쓰면 같은
// [F#] 가 다른 값을 가리킬 수 있어 패널이 나중에 만들지 않는다. sentence 는 마커가 든 원문 그대로(대목 고르기·본문 강조가 쓴다)
function onCite(e: MouseEvent, pid: string, si: number, eid: string, sentence: string): void {
  const sec = section.value;
  const cntsId = sec?.evidence[eid];
  if (!sec || !cntsId) return;
  const pick: CitePick = {
    key: props.sectionKey,
    pid,
    si,
    eid,
    cntsId,
    genId: sec.gen_id,
    sentence,
    quote: citedQuote(sentence, sec.figures),
  };
  emit("cite", pick, e.currentTarget as HTMLElement);
}

// ── 쓰기·고치기 ──────────────────────────────────────────
function onWrite(): void {
  const kept = section.value?.paragraphs.some((p) => p.state !== "proposed") ?? false;
  if (kept && !window.confirm("이 절을 다시 쓰면 지금 문단(수락·고친·직접 쓴 문단 포함)을 새 초안으로 바꿔요.\n다시 쓸까요?")) {
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
// seq — 보낼 때의 savedSeq. 결과가 왔을 때 이보다 올랐으면 저장 응답을 받은 것이다(다시 읽기가 실패했어도)
type Pending = { kind: "edit"; id: string; before: string; seq: number } | { kind: "add"; count: number; seq: number };
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

// 칸을 여는 버튼은 칸이 열리면 사라지고(v-if) 칸은 닫히면 사라진다 — 포커스를 옮기지 않으면 body 로 떨어져 키보드·
// 스크린리더 사용자가 페이지 맨 앞에서 다시 찾아와야 한다(운영 확인 2026-10-08). 열면 칸으로, 닫으면 그 칸을 연 버튼으로
const rootEl = ref<HTMLElement | null>(null);

function focusLater(selector: string): void {
  void nextTick(() => rootEl.value?.querySelector<HTMLElement>(selector)?.focus());
}

watch(editingId, (now, was) => {
  if (now) focusLater("[data-edit-box]");
  else if (was) focusLater(`[data-edit-for="${CSS.escape(was)}"]`);
});
watch(adding, (now) => focusLater(now ? "[data-add-box]" : "[data-add-open]"));

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
  pending = { kind: "edit", id: pid, before, seq: props.savedSeq ?? 0 };
  emit("save", editParagraph(sec, pid, text));
}

function saveAdd(): void {
  const sec = section.value;
  if (!sec) return;
  pending = { kind: "add", count: sec.paragraphs.length, seq: props.savedSeq ?? 0 };
  emit("save", addParagraph(sec, addText.value.trim()));
}

watch(
  () => props.busy,
  (now, was) => {
    const p = pending;
    if (!was || now || !p) return;
    pending = null;
    const paragraphs = section.value?.paragraphs ?? [];
    const wrote = (props.savedSeq ?? 0) !== p.seq;
    if (p.kind === "edit") {
      if (wrote || paragraphs.find((x) => x.id === p.id)?.text !== p.before) editingId.value = null;
    } else if (wrote || paragraphs.length > p.count) {
      adding.value = false;
      addText.value = "";
    }
  },
);
</script>
