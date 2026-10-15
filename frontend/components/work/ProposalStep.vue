<!-- frontend/components/work/ProposalStep.vue -->
<template>
  <!-- 오른쪽 패널(인용 근거·딥리드)이 열리면 본문 | 패널 2단 — .wk-split 은 ReadingStep 과 같은 공용 배치다 -->
  <div class="wk-split" :class="{ 'is-panel-open': !!panel }">
  <section class="wk-proposal wk-split__main" aria-labelledby="wk-proposal-title">
    <header class="wk-proposal__head">
      <!-- tabindex="-1" — 단계를 옮기면 연구 화면이 이 제목으로 초점을 옮긴다 -->
      <h2 id="wk-proposal-title" class="wk-proposal__title" tabindex="-1">{{ FINAL_STEP_NAME }}</h2>
      <CorpusScopeNote :corpus="corpus" />
    </header>
    <p v-if="notice" class="rs-alert" :role="noticeIsError ? 'alert' : 'status'">{{ notice }}</p>

    <div v-if="!proposal && work.errorOf('proposal')" class="rs-card rs-card--error">
      <p>{{ work.errorOf("proposal") }}</p>
      <div class="rs-card__actions">
        <button type="button" class="rs-btn" @click="work.reload('proposal')">다시 불러오기</button>
      </div>
    </div>
    <div v-else-if="!proposal" class="rs-card rs-card--wait" role="status">
      <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
      <p>보고서를 불러오는 중입니다</p>
    </div>

    <div v-else-if="!proposal.outline" class="rs-card">
      <template v-if="outlineGen">
        <p class="rs-card__title">목차를 만드는 중입니다</p>
        <p v-if="genQueueLine(outlineGen)" class="rs-muted" role="status">{{ genQueueLine(outlineGen) }}</p>
      </template>
      <template v-else>
        <p class="rs-card__title">아직 목차가 없습니다</p>
        <p class="rs-muted">
          참고문헌에 담은 논문이 {{ MIN_READING_FOR_OUTLINE }}편 이상이면 보고서를 만들 수 있습니다. 선행연구 묶음의 수와 배정은
          담은 논문의 키워드 소속으로 서버가 정합니다.
        </p>
        <div v-if="!readOnly" class="rs-card__actions">
          <button type="button" class="rs-btn" :disabled="busy" @click="makeOutline">{{ MAKE_REPORT }}</button>
          <button type="button" class="rs-btn rs-btn--ghost" @click="emit('go', 'reading')">참고문헌 선택하기로</button>
        </div>
      </template>
    </div>

    <template v-else>
      <p v-if="outlineGen" class="rs-muted" role="status">
        목차를 다시 만드는 중입니다{{ genQueueLine(outlineGen) ? ` · ${genQueueLine(outlineGen)}` : "" }}
      </p>
      <div v-else-if="canRemake" class="wk-proposal__remake">
        <p class="rs-muted">{{ remakeWhy }}</p>
        <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" :disabled="busy" @click="makeOutline">
          {{ REMAKE_REPORT }}
        </button>
      </div>

      <template v-if="approved">
        <!-- 큰 진행 막대(06e 정함 28) — 절을 차례로 쓰는 동안만 서고 다 쓰면 걷힌다. 글줄·퍼센트는 valuetext 로 읽힌다.
             progressbar 는 이름이 있어야 한다(ARIA 1.2 — 딥리서치 진행 카드 SynthProgressCard 와 같은 꼴) -->
        <div
          v-if="bar"
          class="wk-rbar"
          role="progressbar"
          :aria-label="`${FINAL_STEP_NAME} 작성 진행`"
          :aria-valuenow="bar.percent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuetext="bar.label"
        >
          <p class="wk-rbar__line">{{ bar.label }}</p>
          <span class="wk-rbar__pct">{{ bar.percent }}%</span>
          <div class="wk-rbar__track">
            <div class="wk-rbar__fill" :class="{ 'is-running': bar.running }" :style="{ width: `${bar.percent}%` }" />
          </div>
        </div>
        <!-- 연쇄가 멈춘 줄 — 남은 절이 있을 때만(멈춘 뒤 남은 절을 손으로 다 쓰면 이어서 쓸 것이 없어 걷는다) -->
        <div v-if="autoStopped && autoLeft.length" class="rs-alert wk-doc__resume" role="alert">
          <p>{{ autoStopped }} — [이어서 쓰기]를 누르면 남은 절부터 다시 씁니다.</p>
          <button type="button" class="rs-btn rs-btn--small" :disabled="autoRunning" @click="resumeAuto">이어서 쓰기</button>
        </div>
        <nav class="rs-card wk-doc__toc" aria-labelledby="wk-doc-toc-title">
          <div class="wk-doc__toc-head">
            <!-- tabindex="-1" — [이어서 쓰기]를 누르면 그 줄이 사라져 초점을 여기로 옮긴다(resumeAuto) -->
            <h3 id="wk-doc-toc-title" class="rs-card__title" tabindex="-1">목차</h3>
            <button
              type="button"
              class="rs-btn rs-btn--small rs-btn--ghost"
              :aria-expanded="outlineOpen"
              aria-controls="wk-outline-editor"
              @click="toggleOutline"
            >
              {{ outlineToggleLabel(outlineOpen, readOnly) }}
            </button>
          </div>
          <ol class="wk-doc__toc-list">
            <li v-for="item in toc" :key="item.key">
              <button type="button" class="wk-doc__toc-item" :class="`is-${item.status}`" @click="goPart(item.anchor)">
                <span class="wk-doc__toc-no">{{ item.no }}</span>
                <span class="wk-doc__toc-label">{{ item.label }}</span>
                <span v-if="TOC_STATUS[item.status]" class="wk-doc__toc-status">{{ TOC_STATUS[item.status] }}</span>
              </button>
            </li>
          </ol>
        </nav>
        <p v-if="reviewText" class="wk-review">
          <button type="button" class="wk-review__jump" @click="jumpToReview">
            {{ reviewText }}<span class="rs-sr-only"> — 첫 자리로 가기</span>
          </button>
          <span class="rs-muted">코드 검사가 표시한 곳입니다. 원문과 맞는지 확인하세요.</span>
        </p>
      </template>
      <!-- [목차 고치기] — 승인 목차는 접어 두고, 초안 목차(06b·질문이 없어 자동 승인하지 못한 목차)는 승인하러 늘 편다.
           v-show 라 접어도 편집기가 붙어 있어 고치던 목차(draft·편집 모드)가 남는다 — 다시 펴면 이어서 고친다 -->
      <div v-show="editorShown" id="wk-outline-editor">
        <OutlineEditor
          ref="outlineEditor"
          :proposal="proposal"
          :read-only="readOnly"
          :busy="busy || !!outlineGen"
          @save="saveOutline"
        />
      </div>

      <template v-if="approved">
        <div class="rs-card wk-proposal__intro">
          <AiFootprintMeter :proposal="proposal" />
          <!-- 절을 차례로 쓰는 것은 [보고서 만들기]가 자동 승인한 목차(auto)뿐 — 06b 때 승인했거나 초안을 손으로 승인한 목차는 손으로 쓴다 -->
          <p v-if="proposal.outline.auto" class="rs-muted">
            [{{ MAKE_REPORT }}]로 목차가 서면 선행연구 묶음·연구 공백 절을 차례로 씁니다. 다 쓴 문단은 그대로 두어도 되고,
            [수락]·[다시]·[고치기]로 다듬을 수 있습니다.
          </p>
          <p v-else class="rs-muted">
            절마다 [이 절 쓰기]를 누르면 씁니다. 다 쓴 문단은 [수락]·[다시]·[고치기]로 다듬을 수 있습니다.
          </p>
        </div>
        <div class="wk-doc">
          <section id="wk-doc-topic" class="rs-card wk-doc__part" aria-labelledby="wk-doc-topic-title">
            <h3 id="wk-doc-topic-title" class="wk-doc__part-title" tabindex="-1">1. {{ SECTION_LABELS.topic }}</h3>
            <p class="wk-doc__text">{{ proposal.outline.topic.title }}</p>
          </section>
          <section id="wk-doc-background" class="rs-card wk-doc__part" aria-labelledby="wk-doc-background-title">
            <h3 id="wk-doc-background-title" class="wk-doc__part-title" tabindex="-1">2. {{ SECTION_LABELS.background }}</h3>
            <DocField
              field-id="wk-docfield-background"
              label="연구 배경"
              :value="background"
              :max="OUTLINE_BACKGROUND_MAX"
              placeholder="이 연구가 왜 필요한지 — 연구 대상과 문제 상황, 이 주제를 보게 된 맥락을 적습니다. AI 는 이 칸을 쓰지 않습니다."
              :read-only="readOnly"
              :busy="busy || !!outlineGen"
              @save="saveField('background', $event)"
            />
          </section>
          <ProposalSection
            v-for="key in writableKeys"
            :key="key"
            :section-key="key"
            :label="partLabel(key)"
            :proposal="proposal"
            :state="state"
            :read-only="readOnly"
            :busy="busy"
            :active-cite="activeCite?.key === key ? activeCite : null"
            :panel-id="PANEL_ID"
            @cite="onCite"
            :skipped="autoSkipped.has(key)"
            :auto-next="autoNext.has(key)"
            @write="write(key)"
            @save="saveSection(key, $event)"
            @regenerate="regenerate(key, $event)"
            @retry="retry"
          />
          <section id="wk-doc-question" class="rs-card wk-doc__part" aria-labelledby="wk-doc-question-title">
            <h3 id="wk-doc-question-title" class="wk-doc__part-title" tabindex="-1">5. {{ SECTION_LABELS.question }}</h3>
            <p v-if="proposal.outline.question" class="wk-doc__text">{{ proposal.outline.question }}</p>
            <p v-else class="rs-muted">연구 질문을 아직 정하지 않았습니다 — [목차 고치기]에서 고르세요.</p>
          </section>
          <section id="wk-doc-method" class="rs-card wk-doc__part" aria-labelledby="wk-doc-method-title">
            <h3 id="wk-doc-method-title" class="wk-doc__part-title" tabindex="-1">6. {{ SECTION_LABELS.method }}</h3>
            <DocField
              field-id="wk-docfield-method"
              label="방법"
              :value="proposal.outline?.method ?? ''"
              :max="OUTLINE_METHOD_MAX"
              placeholder="연구 설계·대상·자료 수집과 분석 방법을 적습니다. AI 는 이 칸을 쓰지 않습니다."
              :read-only="readOnly"
              :busy="busy || !!outlineGen"
              @save="saveField('method', $event)"
            />
          </section>
        </div>

        <div class="rs-card wk-proposal__export">
          <p class="rs-card__title">내려받기</p>
          <label class="wk-proposal__toggle">
            <!-- 켠 채 검토 전 문단이 0 이 되어도(다 [수락]) 끌 수 있게 켜져 있으면 막지 않는다 — 그때 문서는 모든 문단과 같다(exportProposal) -->
            <input v-model="acceptedOnly" type="checkbox" :disabled="!printedProposed && !acceptedOnly" />
            수락한 문단만 싣기 — 검토 전 AI 작성 {{ printedProposed }}문단을 뺍니다
          </label>
          <p class="rs-muted">기본은 모든 문단을 싣습니다. 끝에 참고문헌과 AI 사용 공개 부록(문단 상태별 개수)이 붙습니다.</p>
          <div class="rs-card__actions">
            <button type="button" class="rs-btn" :disabled="exporting" @click="exportProposal('docx')">
              {{ exportingAs === "docx" ? "만드는 중…" : "Word 로 내려받기" }}
            </button>
            <button type="button" class="rs-btn rs-btn--ghost" :disabled="exporting" @click="exportProposal('pdf')">
              {{ exportingAs === "pdf" ? "인쇄 창을 여는 중…" : "PDF 로 내려받기" }}
            </button>
          </div>
          <p class="rs-muted">PDF 는 인쇄 창에서 대상을 ‘PDF로 저장’으로 고릅니다. Word 와 같은 문서·같은 기본값입니다.</p>
        </div>
      </template>
      <p v-else class="rs-muted">목차를 승인하면 선행연구 검토(묶음마다)와 연구 공백 절을 쓸 수 있습니다.</p>
    </template>
  </section>
  <DeepReadPanel
    :panel-id="PANEL_ID"
    :paper="panelPaper"
    :tabs="PANEL_TABS"
    :tab="panel?.tab ?? 'sources'"
    :detail-href="panelDetailHref"
    :store="chatStore"
    @update:tab="setTab"
    @close="closePanel"
    @open-pdf="emit('open-pdf', $event)"
    @detail="onDetail"
  >
    <template #sources>
      <CitationSource
        v-if="panel?.pick"
        :pick="panel.pick"
        :meta="panelPaper?.meta ?? null"
        :source="panelSource"
        :loading="sourcesLoading"
        :error="sourcesError"
        @open-pdf="emit('open-pdf', $event)"
        @chat="openChat"
      />
    </template>
  </DeepReadPanel>
  <!-- PDF 내려받기(인쇄) 동안에만 body 에 붙는 인쇄 전용 문서(Teleport) — 화면에는 그리지 않는다(research.css .rs-print) -->
  <ReportPrint v-if="printDoc" :doc="printDoc" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import ReportPrint from "~/components/research/ReportPrint.vue";
import AiFootprintMeter from "~/components/work/AiFootprintMeter.vue";
import CitationSource from "~/components/work/CitationSource.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import DeepReadPanel from "~/components/work/DeepReadPanel.vue";
import DocField from "~/components/work/DocField.vue";
import OutlineEditor from "~/components/work/OutlineEditor.vue";
import ProposalSection from "~/components/work/ProposalSection.vue";
import { useAutoReport } from "~/composables/useAutoReport";
import { useReportExport } from "~/composables/useReportExport";
import { useWorkApi, type ResearchWorkHandle } from "~/composables/useResearchWork";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { OpenPdfPayload } from "~/types/research";
import type { CitePick, OutlinePut, PaperMeta, SectionPut, SectionSources, WorkStep } from "~/types/work";
import { activeCiteOf, type ActiveCite } from "~/utils/citationEvidence";
import { panelTabs, type PanelPaper, type PanelTab } from "~/utils/deepRead";
import type { DeepReadMessage } from "~/utils/deepReadSse";
import { detailUrl, paraAnchor } from "~/utils/detailSource";
import { OUTLINE_BACKGROUND_MAX, OUTLINE_METHOD_MAX, fieldPut, isFallbackOutline } from "~/utils/outlineEdit";
import { buildProposalDocument, printedKeys, printedProposedCount } from "~/utils/proposalDocument";
import {
  SECTION_LABELS,
  autoChainOn,
  autoTargets,
  docToc,
  outlineBackground,
  outlineToggleLabel,
  proposalReread,
  putOnceMore,
  reportBar,
  reviewLine,
  reviewSpots,
  sectionLabel,
  type TocItem,
} from "~/utils/proposalView";
import { genQueueLine } from "~/utils/queueLine";
import { MIN_READING_FOR_OUTLINE } from "~/utils/readingList";
import type { ReportExportFormat } from "~/utils/reportDocument";
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
import { isPlainClick, spotOf } from "~/utils/restorePosition";
import { openGeneration } from "~/utils/workEvents";
import { FINAL_STEP_NAME, MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";

const props = defineProps<{ jobId: string; work: ResearchWorkHandle; question: string }>();
const emit = defineEmits<{
  go: [step: WorkStep];
  // [원문 보기] — 연구 화면의 원문 뷰어(openPdf)가 연다
  "open-pdf": [payload: OpenPdfPayload];
  // 오른쪽 패널이 열렸는지 — 연구 화면이 LNB 를 접는 재료(workPanelOpen)
  panel: [open: boolean];
}>();

const CONFLICT = "다른 곳에서 보고서가 바뀌어 다시 불러왔습니다 — 바뀐 내용을 확인한 뒤 다시 해 주세요";
// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 덮는다(계약 보강 4) — 다시 만들기 전에 묻는다. 새 반영은 다시
// 자동 승인하지만 절 연쇄는 절도 생성 기록도 없는 키만 쓴다 — 이미 쓴 절은 다시 쓰지 않는다(06e 정함 4)
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다 — 연구 배경은 그대로 둡니다. 이미 쓴 절은 지우지 않고(주제·묶음·연구 질문이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";

const api = useWorkApi();
// PDF 는 딥리서치 보고서와 같은 인쇄 경로다 — printDoc 이 차면 템플릿 끝의 ReportPrint 가 body 에 붙고 인쇄 창이 열린다
const { exporting, printDoc, exportDocx, printPdf } = useReportExport();

const state = computed(() => props.work.state.value);
const proposal = computed(() => state.value.proposal);
const workView = computed(() => state.value.work);
// 예시 연구는 읽기 전용이다 — 쓰기 API 는 409 로 막히므로 버튼을 두지 않는다
const readOnly = computed(() => workView.value?.is_example ?? false);
const corpus = computed(() => proposal.value?.corpus ?? workView.value?.corpus ?? null);
// 목차 생성의 target 은 연구마다 하나("outline" — 서버 OUTLINE_TARGET)
const outlineGen = computed(() => openGeneration(state.value, "outline", "outline"));
const approved = computed(() => proposal.value?.outline?.state === "approved");
// 06b 가 쓰는 절 — 문서가 그리는 절과 같다(선행연구 묶음(목차 순서) → 연구 공백, proposalDocument printedKeys)
const writableKeys = computed(() => (proposal.value ? printedKeys(proposal.value) : []));
// 문서에 실릴 검토 전 문단 — 목차를 다시 만들며 빠진 옛 절은 문서에 실리지 않아 세지 않는다(공개 부록·'수락한 문단만'과 같은 수)
const printedProposed = computed(() => (proposal.value ? printedProposedCount(proposal.value) : 0));
const canRemake = computed(() => {
  const p = proposal.value;
  return !readOnly.value && !!p?.outline && (p.stale.outline || isFallbackOutline(p.outline));
});
const remakeWhy = computed(() =>
  proposal.value?.stale.outline
    ? "주제나 참고문헌이 바뀌었습니다 — 목차를 다시 만들면 지금 담은 논문으로 묶음을 새로 나눕니다(지금 목차를 바꿉니다)."
    : "모델이 목차 초안을 만들지 못했습니다 — 다시 만들어 볼 수 있습니다.",
);

// ── 보고서 자동 산출(06e D20) ─────────────────────────────
// [보고서 만들기]의 반영이 자동 승인한 목차에서 남은 절을 문서 순서대로 하나씩 넣는다 — 이 화면이 열려 있는 동안만 돌고,
// 조건은 서버 값으로 다시 계산해 탭을 닫았다 와도 남은 절부터 잇는다(useAutoReport, 정함 6)
const {
  running: autoRunning,
  stopped: autoStopped,
  skipped: autoSkipped,
  resume: resumeChain,
} = useAutoReport({
  proposal,
  work: workView,
  generate: (key) => api.generateSection(props.jobId, key),
  reload: async () => {
    await Promise.all([props.work.reload("proposal"), props.work.reload("work")]);
    props.work.afterAction();
  },
});
// 연쇄가 아직 넣을 절 — 문서 순서에서 절도 생성 기록도 없고 근거가 없어 건너뛰지도 않은 키. 연쇄가 돌지 않는 목차(06b 때
// 승인한 목차·초안·예시 연구·목차를 다시 만드는 중)면 빈 목록이다. 멈춘 뒤 남은 절을 손으로 다 쓰면 비어 멈춘 줄이 걷힌다
// (useAutoReport 의 stopped 는 resume·새 목차에서만 비워진다)
const autoLeft = computed(() => {
  const p = proposal.value;
  return p && autoChainOn(p, workView.value) ? autoTargets(p).filter((k) => !autoSkipped.value.has(k)) : [];
});
// [이어서 쓰기] — 멈춤이 풀리면 그 줄(v-if autoStopped)이 누른 버튼째 사라져 초점이 body 로 떨어진다. 그린 뒤 초점을 잃었을
// 때만 바로 아래 머리 목차 제목으로 옮긴다(다른 곳으로 간 초점은 빼앗지 않는다 — ConceptChips·TopicCard 와 같은 꼴)
function resumeAuto(): void {
  resumeChain();
  void nextTick(() => {
    const active = document.activeElement;
    if (active && active !== document.body) return;
    document.getElementById("wk-doc-toc-title")?.focus({ preventScroll: true });
  });
}
// 쓰기 전 절 안내가 '차례가 오면 자동으로 씁니다' 를 말해도 되는 키 — 멈춘 동안은 [이어서 쓰기]를 눌러야 쓰므로 뺀다
const autoNext = computed(() => new Set<string>(autoStopped.value ? [] : autoLeft.value));
// 머리의 큰 진행 막대(정함 28) — 절이 끝날 때만 차오르고, 다 쓰면 걷힌다. 연쇄가 멈추면 쓰는 절이 있을 때만
const bar = computed(() =>
  proposal.value ? reportBar(proposal.value, state.value, autoSkipped.value, autoStopped.value !== null) : null,
);
// 머리 목차 — 문서 순서의 여섯 자리(anchor = 아래 자리 id)
const toc = computed(() => (proposal.value ? docToc(proposal.value, state.value, autoSkipped.value) : []));
const TOC_STATUS: Record<TocItem["status"], string> = {
  text: "",
  blank: "비어 있음",
  empty: "쓰기 전",
  queued: "대기 중",
  writing: "쓰는 중",
  done: "씀",
  failed: "실패",
  skipped: "근거 없음",
};
const background = computed(() => (proposal.value?.outline ? outlineBackground(proposal.value.outline) : ""));
// [목차 고치기] — 승인 목차는 편집기를 접어 둔 채 시작한다(자동 확정이 기본). 초안 목차는 승인하러 늘 펴고, 편집기에서
// 승인하면 saveOutline 이 outlineOpen 을 참으로 둬 편 채로 남는다
const outlineOpen = ref(false);
const editorShown = computed(() => !approved.value || outlineOpen.value);
const outlineEditor = ref<InstanceType<typeof OutlineEditor> | null>(null);

// 머리 목차의 토글 — 접혀 있으면 [목차 고치기]로 펴며 편집 모드로 바로 열고(예시 연구는 읽기), 펴 있으면 [목차 접기]로
// 접는다. 접어도 편집기는 v-show 로 붙어 있어 고치던 것을 잃지 않는다(outlineToggleLabel)
function toggleOutline(): void {
  outlineOpen.value = !outlineOpen.value;
  if (outlineOpen.value) outlineEditor.value?.startEditing();
}

// 절 자리 제목 — 머리 목차의 번호를 붙인다(3.1 선행연구 검토 · 묶음 이름, 4. 연구 공백 — Word 의 절 번호와 같다)
function partLabel(key: string): string {
  const label = sectionLabel(key, proposal.value?.outline ?? null);
  const no = toc.value.find((i) => i.key === key)?.no;
  if (!no) return label;
  return `${no.includes(".") ? no : `${no}.`} ${label}`;
}

// 머리 목차 항목 — 그 자리로 옮기고 자리 제목(h3 tabindex="-1")에 초점을 둔다(화면낭독기가 어디로 왔는지 읽는다)
function goPart(anchor: string): void {
  const el = document.getElementById(anchor);
  if (!el) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  el.querySelector<HTMLElement>("h3")?.focus({ preventScroll: true });
}

// 검토할 곳(06e) — 머리 한 줄. 누르면 첫 자리로 간다
const review = computed(() => (proposal.value ? reviewSpots(proposal.value) : null));
const reviewText = computed(() => (review.value ? reviewLine(review.value) : null));

// 첫 자리 문단(li — ProposalSection 이 tabindex="-1" 를 단다)으로 스크롤하고 초점을 옮긴다. 그 절을 다시 쓰는 중이라 문단이
// 그려지지 않았으면 그 절의 제목으로 간다
function jumpToReview(): void {
  const first = review.value?.first;
  if (!first) return;
  const el =
    document.querySelector<HTMLElement>(`[data-anchor="${paraAnchor(first.key, first.pid)}"]`) ??
    document.getElementById(`wk-sec-title-${first.key}`);
  if (!el) return;
  el.scrollIntoView({ block: "center" });
  el.focus({ preventScroll: true });
}

onMounted(() => {
  // 다른 단계(주제·읽기 목록)에서 바뀐 다시 맞춤 표시는 조회 때 계산된다 — 단계에 들어올 때마다 다시 읽는다
  void props.work.reload("proposal");
});

// ── 동작 ──────────────────────────────────────────────────
const busy = ref(false);
const notice = ref("");
const noticeIsError = ref(false);

function say(message: string, error = false): void {
  notice.value = message;
  noticeIsError.value = error;
}

// 계획서 쓰기는 If-Match(version)를 싣는다. 그 사이 생성이 끝났거나 다른 탭에서 고쳤으면 409 version_conflict —
// 다시 읽고 알린다(고치던 목차·문단은 새 내용으로 바뀐다)
async function act(run: () => Promise<void>, fallback: string): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  say("");
  try {
    await run();
    props.work.afterAction();
  } catch (e) {
    if (versionConflict(e) !== null) {
      await props.work.reload("proposal");
      say(CONFLICT, true);
    } else {
      // 그 밖의 409(다른 곳에서 고쳐 저장해 승인이 풀린 목차의 절 쓰기·다시 쓸 수 없는 문단 등)와 404(다른 곳에서 지우거나
      // 다시 만든 문단·묶음)도 그 사이 서버 상태가 바뀐 것이다 — 계획서·생성 목록을 다시 읽어 눌러도 막히는 버튼을 걷은 뒤
      // 서버 문구를 보인다(단계 화면 관례, 계약 보강 8). work 이벤트는 계획서를 다시 읽지 않아 기다려도 풀리지 않는다
      const status = httpStatus(e);
      if (status === 409 || status === 404) {
        await Promise.allSettled([props.work.reload("proposal"), props.work.reload("work")]);
      }
      say(workErrorMessage(e, fallback), true);
    }
  } finally {
    busy.value = false;
  }
}

function makeOutline(): void {
  if (proposal.value?.outline && !window.confirm(REMAKE_CONFIRM)) return;
  void act(async () => {
    await api.createOutline(props.jobId);
    // 대기 순번은 이벤트를 기다리지 않고 바로 그린다. 계획서 행이 없던 연구는 이 요청이 만든다
    await Promise.all([props.work.reload("work"), props.work.reload("proposal")]);
  }, "보고서를 만들지 못했습니다");
}

function saveOutline(body: OutlinePut): void {
  const p = proposal.value;
  if (!p) return;
  // 초안 목차를 승인해도 편집기를 접지 않는다(editorShown) — 고치던 목차가 통째로 사라지지 않고 그 자리에서 '승인함'으로
  // 바뀐다(06b 와 같다). 접기는 머리 목차의 토글([목차 접기])로
  if (body.approve) outlineOpen.value = true;
  void act(async () => {
    await api.putOutline(props.jobId, p.version, body);
    await props.work.reload("proposal");
    say(body.approve ? "목차를 승인했습니다 — 이제 절을 쓸 수 있습니다" : "목차를 저장했습니다");
  }, "목차를 저장하지 못했습니다");
}

// 문서의 연구 배경(2절)·방법(6절) 칸 — 승인 상태를 지킨 채(fieldPut) PUT /outline. 보고서를 자동으로 쓰는 동안에는 절이
// 반영될 때마다 version 이 올라 409 version_conflict 가 난다 — 계획서를 다시 읽어 목차가 그대로면 다시 읽은 version·목차로
// 본문을 다시 만들어 한 번만 보낸다(putOnceMore). 다시 읽기는 work.reload 가 아니라 GET 을 바로 부른다(proposalReread —
// 절의 generation 이벤트가 그 사이 reload('proposal') 를 부르면 reload 는 제 응답을 버린다). 목차가 바뀐 충돌(work 이벤트는
// 계획서를 다시 읽지 않아 다른 탭의 [목차 고치기]를 이 탭은 모른다)이나 두 번째 409 면 act 가 보고서를 다시 읽고 CONFLICT 를
// 알린다(칸은 열린 채 글이 남아 다시 저장할 수 있다)
function saveField(field: "background" | "method", text: string): void {
  const p = proposal.value;
  const outline = p?.outline;
  if (!p || !outline) return;
  const patch = field === "background" ? { background: text } : { method: text };
  void act(
    async () => {
      await putOnceMore(
        (v, o) => api.putOutline(props.jobId, v, fieldPut(o, patch)),
        { version: p.version, outline },
        proposalReread(() => api.getProposal(props.jobId)),
      );
      await props.work.reload("proposal");
      say(field === "background" ? "연구 배경을 저장했습니다" : "방법을 저장했습니다");
    },
    field === "background" ? "연구 배경을 저장하지 못했습니다" : "방법을 저장하지 못했습니다",
  );
}

function write(key: string): void {
  void act(async () => {
    await api.generateSection(props.jobId, key);
    // 스트리밍 글의 칩을 그릴 근거 지도(drafts)는 열린 생성에서 만들어진다 — 생성을 넣은 뒤 계획서를 다시 읽어야 생긴다
    await Promise.all([props.work.reload("work"), props.work.reload("proposal")]);
  }, "이 절을 쓰기 시작하지 못했습니다");
}

function saveSection(key: string, body: SectionPut): void {
  const p = proposal.value;
  if (!p) return;
  void act(async () => {
    await api.putSection(props.jobId, key, p.version, body);
    await props.work.reload("proposal");
  }, "문단을 저장하지 못했습니다");
}

function regenerate(key: string, pid: string): void {
  void act(async () => {
    await api.regenerateParagraph(props.jobId, key, pid);
    await props.work.reload("work");
  }, "문단을 다시 쓰지 못했습니다");
}

function retry(genId: number): void {
  void act(async () => {
    await api.retryGeneration(props.jobId, genId);
    await Promise.all([props.work.reload("work"), props.work.reload("proposal")]);
  }, "다시 시도하지 못했습니다");
}

// ── 내려받기(Word·PDF) ────────────────────────────────────
const acceptedOnly = ref(false);
// 누른 형식 — 두 버튼은 한 exporting 으로 함께 잠그고, '만드는 중…' 글은 누른 버튼에만 보인다
const exportingAs = ref<ReportExportFormat | null>(null);

// 문서에 싣는 연구 주소 — 계획서 단계로 바로 열리는 주소(쿼리의 at·y 는 빼고 s 만)
function proposalUrl(): string {
  return `${window.location.origin}/research/${props.jobId}?s=proposal`;
}

// Word·PDF 는 같은 문서 모델(buildProposalDocument — 같은 기본값과 '수락한 문단만' 체크)이다. PDF 는 인쇄 창의
// 'PDF로 저장' 이 문서 제목(파일 이름에서 .docx 를 뗀 것)을 파일 이름으로 쓴다(useReportExport.printPdf)
async function exportProposal(format: ReportExportFormat): Promise<void> {
  const p = proposal.value;
  const w = workView.value;
  // 이미 내보내는 중이면 exportDocx·printPdf 가 아무 일 없이 돌아온다 — 여기서 먼저 막아 markDone 이 헛돌지 않게 한다
  if (!p || !w || exporting.value) return;
  // 앞 안내를 지운다(act 와 같다) — PDF 는 성공 안내가 없어, 지우지 않으면 앞선 실패 안내가 성공 뒤에도 남는다
  say("");
  // 검토 전 문단이 없으면 '수락한 문단만'은 모든 문단과 같은 문서다 — 파일 이름 꼬리(_수락문단만)·부록의 '…만' 줄을 달지 않는다
  const onlyAccepted = acceptedOnly.value && printedProposed.value > 0;
  const doc = buildProposalDocument(
    { question: props.question, url: proposalUrl(), proposal: p, work: w, acceptedOnly: onlyAccepted },
    new Date(),
  );
  exportingAs.value = format;
  try {
    if (format === "docx") await exportDocx(doc);
    else await printPdf(doc);
  } catch (e) {
    console.warn("[research] 보고서 내보내기 실패", e);
    // 배포 뒤 옛 화면에서 누르면 docx 조각 파일이 사라져 동적 import 가 실패한다 — 새로고침이 답이다
    say(
      format === "docx"
        ? "Word 문서를 만들지 못했습니다. 새로고침한 뒤 다시 시도해 주세요."
        : "인쇄 창을 열지 못했습니다. 다시 시도해 주세요.",
      true,
    );
    return;
  } finally {
    exportingAs.value = null;
  }
  // PDF 는 인쇄 창 자체가 결과다 — 딥리서치 보고서의 PDF 도 안내를 띄우지 않는다
  if (format === "docx") say("Word 문서를 내려받았습니다");
  await markDone();
}

// 처음 내려받으면 연구를 마친 것으로 둔다(phase done) — 단계는 앞으로만 가므로 이미 done 이면 보내지 않는다.
// PDF 는 인쇄 창을 취소했는지 브라우저가 알려 주지 않아, 창이 닫히고 오류 없이 돌아오면 내려받은 것으로 본다
async function markDone(): Promise<void> {
  const w = workView.value;
  if (!w || w.phase !== "proposal" || readOnly.value) return;
  try {
    props.work.setWork(await api.patchWork(props.jobId, { phase: "done" }));
    props.work.afterAction();
  } catch (e) {
    // 내려받기는 끝났다 — 단계 표시는 다음 내려받기나 새로고침에서 다시 맞춘다
    console.warn("[research] 완료 단계를 저장하지 못했습니다", e);
  }
}

// ── 오른쪽 패널 — 인용 근거·딥리드(D24) ─────────────────
// 인용 칩을 누르면 인용 근거 탭으로 열리고, [이 논문과 대화하기]는 같은 자리를 딥리드 탭으로 바꾼다. 보고서 단계에는
// [담음]을 두지 않는다 — 바꾸면 목차가 '다시 맞춤 필요'가 된다(spec §12-4)
interface ProposalPanel {
  cntsId: string;
  tab: PanelTab;
  pick: CitePick | null;
  // 닫으면 초점을 돌려줄 칩
  opener: HTMLElement | null;
}

const PANEL_ID = "wk-panel-proposal";
const PANEL_TABS = panelTabs("proposal");
// 통째로 바꿔 끼운다(shallowRef) — 칩 요소를 반응형으로 감싸지 않는다
const panel = shallowRef<ProposalPanel | null>(null);
// 딥리드 대화 — 이 단계 안에서 논문을 오가면 이어지고, 단계를 옮기거나 새로고침하면 비운다(서버 저장 없음)
const chatStore = new Map<string, DeepReadMessage[]>();
// 인용 근거는 절 생성마다 한 번 읽는다 — 같은 절의 다른 칩은 다시 부르지 않는다
const sourceCache = new Map<string, SectionSources>();
const sources = shallowRef<SectionSources | null>(null);
const sourcesLoading = ref(false);
const sourcesError = ref<string | null>(null);
let sourcesSeq = 0;
const { leave } = useDetailLeave();

const panelPaper = computed<PanelPaper | null>(() => {
  const p = panel.value;
  if (!p) return null;
  // 서지가 없는 논문은 서버 book_meta 와 같이 cnts_id 를 제목 자리에 쓴다
  const meta: PaperMeta = proposal.value?.papers[p.cntsId] ?? {
    title: p.cntsId,
    personal_author: null,
    pub_date: null,
    series_title: null,
  };
  return { cntsId: p.cntsId, meta };
});
const panelSource = computed(() => {
  const pick = panel.value?.pick;
  return pick && sources.value ? (sources.value[pick.eid] ?? null) : null;
});
// 본문 쪽 강조 — 누른 칩이 든 문장이 지금도 같은 글일 때만 둔다(activeCiteOf). 절을 다시 써 gen_id 가 바뀌었거나, 절
// gen_id 는 그대로인 문단 [고치기] 저장·문단 [다시]로 그 문단의 글이 바뀌어 같은 문장 번호가 다른 글을 가리키면 강조와
// 펼침을 뗀다(S4 quality 검토 반영 — 파트 S 메모 13). 패널의 카드·근거는 그대로 둔다 — 그 문장을 쓸 때의 입력이다
const activeCite = computed(() => activeCiteOf(panel.value?.pick, proposal.value));
// [논문 상세 ↗] 의 링크 주소 — 높이(y)는 누르는 순간에만 잴 수 있어 링크에는 문단 앵커만 싣는다. 그냥 누르기·Ctrl·Shift
// 클릭은 onDetail 이 그때 잰 높이를 실은 주소로 갈음하고, 가운데 버튼·메뉴는 이 주소 그대로다
const panelDetailHref = computed(() => {
  const p = panel.value;
  return p ? detailUrlOf(p, null) : null;
});

// 연구 화면이 LNB 를 접는 재료 — 단계를 옮기면 이 화면이 내려가며 닫힘을 알린다(연구 화면에 watch(step) 가 필요 없다)
watch(
  () => panel.value !== null,
  (open) => emit("panel", open),
);
onBeforeUnmount(() => emit("panel", false));

function samePick(a: ActiveCite, b: ActiveCite): boolean {
  return a.key === b.key && a.pid === b.pid && a.si === b.si && a.eid === b.eid;
}

function onCite(pick: CitePick, el: HTMLElement): void {
  const now = panel.value;
  // 펼친 칩을 다시 누르면 닫는다(aria-expanded 토글). 펼침은 activeCite 를 따른다 — 그 사이 문단을 고치거나 다시 써 강조가
  // 떨어진(펼침이 아닌) 자리의 칩은 같은 문단·문장 번호·근거 번호여도 그 문장으로 새로 연다
  const open = activeCite.value;
  if (now?.tab === "sources" && open && samePick(open, pick)) {
    closePanel();
    return;
  }
  panel.value = { cntsId: pick.cntsId, tab: "sources", pick, opener: el };
  void loadSources(pick);
}

// 늦게 온 응답은 버린다 — 그 사이 다른 칩을 눌렀으면 그 칩의 근거가 보여야 한다(받은 것은 캐시에만 남긴다)
async function loadSources(pick: CitePick): Promise<void> {
  const cacheKey = `${pick.key}#${pick.genId}`;
  const seq = ++sourcesSeq;
  sourcesError.value = null;
  const cached = sourceCache.get(cacheKey);
  if (cached) {
    sources.value = cached;
    sourcesLoading.value = false;
    return;
  }
  sources.value = null;
  sourcesLoading.value = true;
  try {
    const got = await api.getSectionSources(props.jobId, pick.key, pick.genId);
    sourceCache.set(cacheKey, got);
    if (seq === sourcesSeq) sources.value = got;
  } catch (e) {
    if (seq === sourcesSeq) sourcesError.value = workErrorMessage(e, "원문 대목을 불러오지 못했습니다");
  } finally {
    if (seq === sourcesSeq) sourcesLoading.value = false;
  }
}

function setTab(tab: PanelTab): void {
  if (panel.value) panel.value = { ...panel.value, tab };
}

// [이 논문과 대화하기] — 같은 자리를 딥리드 탭으로 바꾼다. 누른 버튼은 인용 근거 탭 본문(v-if)과 함께 사라지므로 초점을
// 딥리드 탭 단추로 옮긴다 — body 로 떨어지면 패널의 Esc(aside 의 keydown)·Tab 가두기(처음·끝 보초)가 듣지 못한다
function openChat(): void {
  setTab("chat");
  void nextTick(() => document.getElementById(`${PANEL_ID}-tab-chat`)?.focus());
}

// 닫으면 누른 칩으로 초점을 돌려준다. 그 사이 보고서를 다시 읽어 칩이 새로 그려졌으면 같은 자리의 칩을 찾는다 — 단 누른
// 문장이 아직 같은 글일 때만(activeCite). 절을 다시 썼거나 문단을 고치거나 다시 써 그 문장이 바뀌었으면 같은 자리의 칩은
// (쥔 칩 요소가 다시 쓰여 문서에 남아 있어도) 다른 문장의 칩이라 그 문단(li tabindex -1)으로 간다. 문단도 없으면(지웠거나
// 절을 다시 쓰는 중) 그 절 제목(tabindex -1)으로 간다
function closePanel(): void {
  const p = panel.value;
  // 패널을 비우면 activeCite 도 null 이 된다 — 비우기 전에 잰다
  const same = activeCite.value !== null;
  panel.value = null;
  if (!p) return;
  void nextTick(() => {
    const pick = p.pick;
    const opener = p.opener?.isConnected ? p.opener : null;
    if (!pick) {
      opener?.focus();
      return;
    }
    const chip = same
      ? (opener ??
        document.querySelector<HTMLElement>(
          `#${CSS.escape(`wk-sec-${pick.key}`)} [data-cite="${CSS.escape(`${pick.pid}:${pick.si}:${pick.eid}`)}"]`,
        ))
      : null;
    const para = document.querySelector<HTMLElement>(`[data-anchor="${CSS.escape(paraAnchor(pick.key, pick.pid))}"]`);
    (chip ?? para ?? document.getElementById(`wk-sec-title-${pick.key}`))?.focus();
  });
}

// 상세 주소 — 출처는 이 연구의 보고서 단계, 돌아올 자리는 누른 칩의 문단(06b 칩 링크와 같은 주소)
function detailUrlOf(p: ProposalPanel, y: number | null): string {
  const at = p.pick ? paraAnchor(p.pick.key, p.pick.pid) : null;
  return detailUrl(p.cntsId, { kind: "research", job: props.jobId, e: null, s: "proposal" }, { at, y });
}

// [논문 상세 ↗] — 누르는 순간 누른 칩의 문단 높이를 재어 상세 주소와 이 화면 주소(돌아올 자리)에 함께 싣는다(06b goDetail
// 과 같다 — 상세가 연관 논문으로 넘어가도 높이가 이어져 router.back() 을 못 쓰는 [돌아가기]도 같은 높이로 온다). 칩이 새로
// 그려졌어도 문단은 앵커로 다시 찾는다. 그냥 누르면 떠나고, Ctrl·Shift 클릭은 높이를 실은 주소를 새 탭에 맡긴다
function onDetail(e: MouseEvent): void {
  const p = panel.value;
  if (!p) return;
  const at = p.pick ? paraAnchor(p.pick.key, p.pick.pid) : null;
  const item = at ? document.querySelector<HTMLElement>(`[data-anchor="${CSS.escape(at)}"]`) : null;
  const spot = item && at ? spotOf(item, at) : { at, y: null };
  const url = detailUrlOf(p, spot.y);
  if (!isPlainClick(e)) {
    (e.currentTarget as HTMLAnchorElement).href = url;
    return;
  }
  e.preventDefault();
  void leave(url, spot);
}
</script>
