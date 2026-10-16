<!-- frontend/pages/research/[id].vue -->
<template>
  <div :class="['skx-app', workPanelOpen && 'is-lnb-collapsed']">
    <AppSidebar
      :collapsed="workPanelOpen"
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="rs-page" :class="{ 'has-progressbar': !!barView }">
      <div v-if="notFound" class="rs-card rs-state">
        <h1 class="rs-state__title">찾을 수 없는 연구입니다</h1>
        <p class="rs-muted">주소가 잘못됐거나 지워진 연구입니다.</p>
        <NuxtLink to="/papers" class="rs-btn">논문 검색으로 돌아가기</NuxtLink>
      </div>

      <div v-else-if="loadError" class="rs-card rs-state">
        <p>{{ loadError }}</p>
        <button type="button" class="rs-btn" @click="load">다시 불러오기</button>
      </div>

      <div v-else-if="!view || !phase" class="rs-card rs-state">
        <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
        <p class="rs-muted">연구를 불러오는 중입니다</p>
      </div>

      <template v-else>
        <ResearchHeader
          :question="view.question"
          :phase="phase"
          :layout="layout"
          :can-toggle="canToggle"
          :can-retry="canRetry"
          :busy="busy || restarting"
          :mode-line="modeLine"
          @toggle-layout="toggleLayout"
          @copy-link="copyLink"
          @cancel="onCancel"
          @retry="retry"
          @restart="onRestart"
        />
        <!-- 고정 진행 영역 — 끝나지 않은 잡에만 선다. 끝난 잡의 이어간 연구에 서는 아래 WorkStepper 와 함께 서지 않는다 -->
        <ResearchProgressBar v-if="barView" :view="barView" :tag="currentStageTag(phase)" />
        <!-- 이어간 연구에만 단다 — 이어가지 않은 딥리서치의 머리는 지금과 같다 -->
        <WorkStepper
          v-if="workView"
          :phase="workView.phase"
          :current="stepMode ? step : null"
          :written="proposalWritten(work.state.value)"
          @go="goStep"
          @help="onboardingOpen = true"
        />
        <!-- 막은 연구가 있으면 [진행 중인 연구 보기]를 글 뒤에 작은 테두리 버튼으로 — 글에 붙은 링크라 눈에 띄지 않았다(2026-10-15) -->
        <p v-if="actionError || pageError" :class="['rs-alert', activeJobId && 'rs-alert--action']" role="alert">
          {{ actionError || pageError }}
          <NuxtLink
            v-if="activeJobId"
            class="rs-btn rs-btn--ghost rs-btn--small"
            :to="`/research/${encodeURIComponent(activeJobId)}`"
          >
            진행 중인 연구 보기
          </NuxtLink>
        </p>

        <!-- 연구 어시스턴트 단계(?s=) — 보고서는 요약 띠로 접고 단계 화면을 그린다.
             ?s= 가 없거나 이어가지 않은 연구면 아래 탐색·보고서 화면을 그대로 그린다 -->
        <div v-if="stepMode" class="wk-body">
          <div class="rs-card wk-summary">
            <p class="wk-summary__line">{{ band ? summaryLine(band) : view.question }}</p>
            <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" @click="goStep(null)">{{ DEEP_RESEARCH }} 보고서 보기</button>
          </div>
          <div v-if="!workView && work.errorOf('load')" class="rs-card rs-card--error">
            <p>{{ work.errorOf("load") }}</p>
            <div class="rs-card__actions">
              <button type="button" class="rs-btn" @click="work.load()">다시 불러오기</button>
            </div>
          </div>
          <div v-else-if="!workView" class="rs-card rs-card--wait" role="status">
            <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
            <p>이어간 연구를 불러오는 중입니다</p>
          </div>
          <TopicsStep v-else-if="step === 'topics'" :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" />
          <ReadingStep v-else-if="step === 'reading'" :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" @open-pdf="openPdf" @panel="workPanelOpen = $event" />
          <ProposalStep v-else :job-id="view.jobId" :work="work" :question="view.question" @go="goStep" @open-pdf="openPdf" @panel="workPanelOpen = $event" />
        </div>

        <div v-else class="rs-body" :class="[`rs-body--${layout}`, { 'is-exploring': phase === 'exploring' }]">
          <div class="rs-col-main">
            <!-- 탐색 중에는 계획 블록을 그리지 않는다 — 하위질문 목록·상태는 본문의 절 자리(ReportSkeleton)가 보인다 -->
            <section v-if="phase !== 'completed' && phase !== 'exploring'" class="rs-block rs-block--plan">
              <div v-if="phase === 'planning'" class="rs-card rs-card--wait" role="status">
                <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
                <div class="rs-card__text">
                  <p>연구 계획을 세우는 중입니다</p>
                  <!-- 넓히기가 끝나면 계획이 나오기 전에도 도는 계획 단계에 넓힌 질문이 먼저 실려 온다 -->
                  <p v-if="questionUsed" class="rs-muted rs-plan__understood">{{ understoodLine(questionUsed) }}</p>
                </div>
              </div>
              <PlanCard
                v-else-if="phase === 'awaiting'"
                :plan="view.plan"
                :max="maxSubquestions"
                :question-used="questionUsed"
                editable
                :busy="busy"
                @approve="approve"
                @cancel="onCancel"
              />
              <div v-else-if="phase === 'queued'" class="rs-card rs-card--wait" role="status">
                <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
                <div class="rs-card__text">
                  <p>앞선 연구가 끝나면 시작합니다</p>
                  <p v-if="queueText" class="rs-muted">{{ queueText }}</p>
                </div>
              </div>
              <SynthProgressCard
                v-else-if="phase === 'synthesizing'"
                :slots="slots"
                :eta="eta"
                :highlight-idx="linkedIdx"
                @jump="jumpToSection"
                @hover="hover = nextSlotHover(hover, $event)"
              >
                <template #actions>
                  <ReportDownloadMenu label="초안 저장" :disabled="!draft" :busy="exporting" @select="saveDraft" />
                </template>
              </SynthProgressCard>
              <div v-else-if="phase === 'failed'" class="rs-card rs-card--error">
                <p class="rs-card__title">연구가 도중에 멈췄습니다</p>
                <p v-if="view.lastError" class="rs-muted">{{ view.lastError }}</p>
                <div class="rs-card__actions">
                  <button v-if="canRetry" type="button" class="rs-btn" :disabled="busy" @click="retry">{{ retryLabel }}</button>
                  <button v-else type="button" class="rs-btn" :disabled="restarting" @click="onRestart">같은 질문으로 다시 시작</button>
                </div>
              </div>
              <div v-else-if="phase === 'canceled'" class="rs-card">
                <p class="rs-card__title">취소된 연구입니다</p>
                <div class="rs-card__actions">
                  <button type="button" class="rs-btn" :disabled="restarting" @click="onRestart">같은 질문으로 다시 시작</button>
                </div>
              </div>
            </section>

            <section v-if="reportState || draft || slotsShown" class="rs-block rs-block--report">
              <template v-if="shownReport">
                <!-- 완료 이벤트 뒤 최종본을 받는 동안·실패해 다시 시도하는 동안에도 읽던 초안을 치우지 않는다 -->
                <div v-if="reportState === 'failed'" class="rs-report-note" role="alert">
                  <p>최종 보고서를 불러오지 못했습니다. 잠시 뒤 자동으로 다시 시도합니다 — 아래는 작성 중에 받은 초안입니다.</p>
                  <button type="button" class="rs-btn rs-btn--ghost rs-btn--small" :disabled="syncing" @click="resync">다시 불러오기</button>
                </div>
                <div v-else-if="reportState === 'loading'" class="rs-report-note" role="status">
                  <img :src="SPINNER_SRC" alt="" class="rs-spinner rs-spinner--small" />
                  <p>최종 보고서를 불러오는 중입니다 — 서론과 한계가 붙은 완성본으로 곧 바뀝니다.</p>
                </div>
                <ReportView
                  :report="shownReport"
                  :job-id="view.jobId"
                  :generated-at="reportState === 'ready' ? view.finishedAt : null"
                  :draft="draftMode"
                  :highlight-idx="linkedIdx"
                  :reveal-excluded="revealExcluded"
                  :reveal-references="revealReferences"
                  @open-pdf="openPdf"
                  @copy-link="copyLink"
                >
                  <template #actions>
                    <ReportDownloadMenu v-if="reportState === 'ready'" label="다운로드" :busy="exporting" @select="downloadReport" />
                    <!-- 초안 저장은 멈춘 초안에만 둔다 — 작성 중 저장은 현황 카드가 맡고, 완료 직후에는 곧 최종본의 [다운로드]로 바뀐다 -->
                    <ReportDownloadMenu
                      v-else-if="draftMode?.state === 'interrupted'"
                      label="초안 저장"
                      :busy="exporting"
                      @select="saveDraft"
                    />
                  </template>
                  <template v-if="reportState === 'ready'" #footer>
                    <ContinueResearchCard
                      :exists="work.exists.value"
                      :work="workView"
                      :written="proposalWritten(work.state.value)"
                      :busy="continuing"
                      :error="continueError"
                      @continue="onContinue"
                      @open="openWork"
                    />
                  </template>
                </ReportView>
              </template>
              <!-- 탐색 중에는 보고서 자리에 'AI가 지금 하는 일'(과정)을 크게 — 보고서를 쓰기 시작하면 절 자리·초안으로 바뀌고 과정은 옆 칸
                   탐색 경로로 간다(사용자 결정 2026-10-14) -->
              <ResearchLive v-else-if="phase === 'exploring'" :view="view" />
              <ReportSkeleton v-else-if="slotsShown" :slots="planSlotList" />
              <div v-else-if="reportState === 'failed'" class="rs-card rs-card--error">
                <p class="rs-card__title">보고서를 불러오지 못했습니다</p>
                <p class="rs-muted">잠시 뒤 자동으로 다시 시도합니다</p>
                <div class="rs-card__actions">
                  <button type="button" class="rs-btn" :disabled="syncing" @click="resync">다시 불러오기</button>
                </div>
              </div>
              <div v-else class="rs-card rs-card--wait" role="status">
                <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
                <p>보고서를 불러오는 중입니다</p>
              </div>
            </section>
          </div>

          <aside class="rs-col-side">
            <!-- 진행 패널(탐색 경로) — 탐색 중에는 과정이 본문(ResearchLive)에 크게 뜨므로 옆 칸에서 뺀다. 보고서를 쓰기 시작하면
                 다시 옆 칸 맨 위로 오고 근거 장부는 그 아래로 내린다(사용자 결정 2026-10-14) -->
            <ProgressPanel
              v-if="phase !== 'exploring'"
              :view="view"
              :phase="phase"
              :reveal-excluded="revealExcluded"
              :queue-note="queueText"
            />
            <!-- 근거 장부 — 탐색 중에는 옆 칸에 혼자(본문의 과정 옆에서 채택 논문이 떨어져 쌓이고 critic 이 뺀 논문은 '뺌'으로 내려간다),
                 그 밖에는 탐색 경로 아래. 바깥 v-if 없이 늘 그린다: 장부가 빈 때부터 떠 있어야 첫 회차의 채택이 떨어진다.
                 06a 전 잡은 컴포넌트가 카드를 그리지 않는다 -->
            <div class="wk-side-ledger">
              <EvidenceLedger :subqs="view.subqs" :live="phase === 'exploring'" />
            </div>
          </aside>
        </div>
        <!-- 따라가기를 멈춘 동안만 뜬다 — 누르면 지금 쓰는(찾는) 곳으로 옮기고 다시 따라간다. 화면 아래 가운데에 붙는다 -->
        <button v-if="follow.pill.value" type="button" class="rs-btn rs-btn--small rs-follow-pill" @click="follow.resume()">
          {{ follow.pill.value }}
        </button>
      </template>
    </main>

    <PdfViewer v-if="pdf" :cnts-id="pdf.cntsId" :title="pdf.title" :page="pdf.page" :passages="pdf.passages" @close="closePdf" />
    <ReportPrint v-if="printDoc" :doc="printDoc" />
    <OnboardingModal :open="onboardingOpen" @close="closeOnboarding" />

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import PdfViewer from "~/components/PdfViewer.vue";
import PlanCard from "~/components/research/PlanCard.vue";
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ResearchLive from "~/components/research/ResearchLive.vue";
import ReportDownloadMenu from "~/components/research/ReportDownloadMenu.vue";
import ReportPrint from "~/components/research/ReportPrint.vue";
import ReportSkeleton from "~/components/research/ReportSkeleton.vue";
import ReportView from "~/components/research/ReportView.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
import ResearchProgressBar from "~/components/research/ResearchProgressBar.vue";
import SynthProgressCard from "~/components/research/SynthProgressCard.vue";
import ContinueResearchCard from "~/components/work/ContinueResearchCard.vue";
import EvidenceLedger from "~/components/work/EvidenceLedger.vue";
import OnboardingModal from "~/components/work/OnboardingModal.vue";
import ProposalStep from "~/components/work/ProposalStep.vue";
import ReadingStep from "~/components/work/ReadingStep.vue";
import TopicsStep from "~/components/work/TopicsStep.vue";
import WorkStepper from "~/components/work/WorkStepper.vue";
import { useNow } from "~/composables/useNow";
import { usePdfOpener } from "~/composables/usePdfOpener";
import { useReportExport } from "~/composables/useReportExport";
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
import { useHistory } from "~/composables/useHistory";
import { sidebarStatusOf } from "~/utils/sidebarResearch";
import { useResearchWork, useWorkApi } from "~/composables/useResearchWork";
import { useRestorePosition } from "~/composables/useRestorePosition";
import { useSectionFollow } from "~/composables/useSectionFollow";
import type { OpenPdfPayload } from "~/types/research";
import type { WorkStep } from "~/types/work";
import { safeLocalStorage } from "~/utils/browserId";
import { DEEP_RESEARCH } from "~/utils/brand";
import { queueLine } from "~/utils/queueLine";
import { draftReport, draftSlots, synthEta, type SynthEta } from "~/utils/researchDraft";
import { questionUsedFromSteps, researchPhase, understoodLine } from "~/utils/researchEvents";
import { researchErrorMessage } from "~/utils/researchErrors";
import { researchModeLine, restartParams } from "~/utils/researchMode";
import {
  buildReportDocument,
  docInputFromDraft,
  docInputFromReport,
  type ReportDoc,
  type ReportExportFormat,
} from "~/utils/reportDocument";
import { DEFAULT_MAX_SUBQUESTIONS } from "~/utils/researchInput";
import { draftStateFor, reportSlot } from "~/utils/researchReport";
import { SHOW_LAYOUT_TOGGLE, WIDE_MIN_PX, effectiveLayout, type ResearchLayout } from "~/utils/researchLayout";
import { planSlots, showsPlanSlots, slotFocusSection } from "~/utils/planSlots";
import { activeRoundKey, currentStageTag, maxRoundsOf, progressBarView, showsProgressBar } from "~/utils/researchProgress";
import { followBlocked, followTarget, userOpenedPopover, type PointerTrail } from "~/utils/researchFollow";
import { holdsReturnSpot } from "~/utils/restorePosition";
import { NO_SLOT_HOVER, linkedSlot, nextSlotHover, type SlotHover } from "~/utils/synthCard";
import { proposalWritten } from "~/utils/proposalView";
import { ONBOARDING_KEY, parseWorkStep, stepForPhase, summaryBand, summaryLine, withStep } from "~/utils/workPhase";

const route = useRoute();
const router = useRouter();
const {
  view, notFound, loadError, actionError, activeJobId, busy, syncFailed, syncing, load, resync, approve, retry, cancel,
} = useResearchJob(() => String(route.params.id ?? ""));
const { startResearch } = useResearchStarter();

const phase = computed(() => (view.value ? researchPhase(view.value) : null));

// 이 화면이 받은 상태를 사이드바의 그 연구 줄에 바로 싣는다 — 사이드바의 다시 읽기(몇 초 간격)를 기다리지 않아 승인·대기열·작성
// 시작이 본문과 같은 때에 바뀐다(sidebarStatusOf)
const historyList = useHistory();
watch(
  () => (view.value && phase.value ? sidebarStatusOf(view.value, phase.value) : null),
  (next) => {
    if (next && view.value) historyList.setResearchStatus(view.value.jobId, next);
  },
  { immediate: true, deep: true },
);
// 대기 카드·진행 패널의 대기열 문구 뒤에 덧붙이는 순번 — 대기 중이 아니거나 순번을 모르면 null
const queueText = computed(() => (view.value ? queueLine(view.value.queue) : null));
// 계획이 쓴 넓힌 질문("이렇게 이해했어요" 한 줄). 원 질문과 같거나(넓히기를 껐거나 원문으로 물러남) 넓히기 전 잡이면 null
const questionUsed = computed(() => (view.value ? questionUsedFromSteps(view.value.steps, view.value.question) : null));
const reportState = computed(() => reportSlot(phase.value, !!view.value?.report, syncFailed.value));
const maxSubquestions = computed(() => Number(view.value?.params.max_subquestions) || DEFAULT_MAX_SUBQUESTIONS);
// 계획이 없는 잡의 재시도는 서버가 409 로 거절한다
const canRetry = computed(() => (view.value?.plan.length ?? 0) > 0);
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
// 머리의 탐색 방식 — 두 칸이 다 0 이면 폭넓게, 두 칸이 없는 잡(06c 전)은 null(그리지 않는다)
const modeLine = computed(() => (view.value ? researchModeLine(view.value.params) : null));

useHead({ title: () => (view.value ? `${view.value.question} — ${DEEP_RESEARCH}` : DEEP_RESEARCH) });

// ── 보고서 작성 현황·초안 ─────────────────────────────────
const EMPTY_ETA: SynthEta = { done: 0, total: 0, runningIdx: null, runningElapsedMs: null, remainingMs: null };
// 근거를 모으는 동안·절이 쌓이는 동안만 1초마다 시계를 읽는다 — 쓰는 중인 절의 경과·남은 시간과 큰 진행 막대(탐색 중에는
// 열린 회차의 다가감)가 따라 움직인다
const now = useNow(computed(() => phase.value === "synthesizing" || phase.value === "exploring"));
const slots = computed(() => (view.value ? draftSlots(view.value) : []));
const eta = computed<SynthEta>(() => (view.value ? synthEta(view.value, now.value) : EMPTY_ETA));
// 초안은 쓰는 동안·멈춘 뒤·완료 직후 최종본을 받기 전까지만 보인다 — 최종본이 오면 그것으로 바꾼다
const draftState = computed(() => draftStateFor(phase.value, reportState.value));
const draft = computed(() => (view.value && draftState.value ? draftReport(view.value) : null));
// 승인 뒤 첫 절 전까지 본문에 세우는 하위질문별 절 자리 — 대기열·탐색 중·종합 첫 절 전에만 그리고, 첫 절이
// 완성되면(초안이 생기면) 초안이 그 자리에 선다. 자리는 하위질문 번호로 세운다(절 번호와 다르다 — utils/planSlots)
const planSlotList = computed(() => (view.value ? planSlots(view.value) : []));
const slotsShown = computed(() => showsPlanSlots(phase.value, !!draft.value));
// 템플릿에서 객체를 만들면 1초마다 도는 시계 때문에 초안 전체가 매초 다시 그려진다
const draftMode = computed(() => {
  const state = draftState.value;
  return draft.value && state ? { slots: draft.value.slots, state, excluded: draft.value.excluded } : null;
});
// 최종본이 오면 초안을 그리던 같은 ReportView 에 넘긴다 — 갈아 끼우면 초안 안의 초점·열린 인용 팝오버가
// 사라지고, 스크롤 기준이던 노드도 없어져 읽던 자리가 튄다
const shownReport = computed(() => (reportState.value === "ready" ? view.value?.report : draft.value?.report) ?? null);

// ── 연구 어시스턴트(이어간 연구) ──────────────────────────
// 단계는 주소의 ?s= 다. 이어간 연구의 상태는 딥리서치가 끝난 뒤에만 읽는다(GET work 가 404 면 이어가지 않은 연구)
const step = computed(() => parseWorkStep(route.query));
const work = useResearchWork(() => String(route.params.id ?? ""), {
  enabled: computed(() => phase.value === "completed"),
});
const workView = computed(() => work.state.value.work);
// 보고서 단계에 온 연구는 어느 화면에서 열든 계획서를 읽어 둔다 — 머리 단계 줄·이어가기 카드의 '보고서 완성'(proposalWritten)이
// 계획서로 정해진다. 보고서 단계 화면(ProposalStep)에서만 읽으면 처음 연 화면에 따라 같은 연구의 줄이 달랐다
watch(
  () => workView.value?.phase,
  (p) => {
    if (p === "proposal") void work.ensure("proposal");
  },
  { immediate: true },
);
// 이어가지 않은 연구로 확인되면(exists false) ?s= 가 붙어 와도 지금의 탐색·보고서 화면을 그린다
const stepMode = computed(() => step.value !== null && phase.value === "completed" && work.exists.value !== false);

// ── 큰 진행 막대(고정 진행 영역) ──────────────────────────
// 열린 회차(검색·자기점검을 기다리는 회차)는 화면이 그 회차를 처음 본 때부터 잰 경과로 다가간다 — 서버는 회차 시각을 주지
// 않는다. 회차가 늘거나 판정이 나면 열쇠가 바뀌어 0 부터 다시 센다(그때 점검이 끝난 회차 한 칸이 늘어 막대는 뒤로 가지 않는다)
const roundKey = computed(() => (view.value ? activeRoundKey(view.value.subqs) : null));
const roundSeenAt = ref<number | null>(null);
watch(
  roundKey,
  (k) => {
    roundSeenAt.value = k ? Date.now() : null;
  },
  { immediate: true },
);
// 시계는 1초마다만 바뀐다 — 열쇠가 바뀐 직후에는 시계가 그 시각보다 앞일 수 있어 0 에서 자른다
const roundElapsedMs = computed(() => (roundSeenAt.value === null ? null : Math.max(0, now.value - roundSeenAt.value)));
// 끝나지 않은 잡에만 선다 — 끝나면 머리 상태 배지만 남고, 끝난 잡의 단계 화면(stepMode)에는 WorkStepper 가 선다(한 화면에
// 큰 막대와 단계 막대가 함께 서지 않는다). 이어간 연구의 보고서 단계(?s=proposal)의 큰 막대는 06e 몫이다
const barView = computed(() =>
  view.value && phase.value && showsProgressBar(phase.value, stepMode.value)
    ? progressBarView({
        phase: phase.value,
        subqs: view.value.subqs,
        maxRounds: maxRoundsOf(view.value.params),
        roundElapsedMs: roundElapsedMs.value,
        eta: eta.value,
        slots: slots.value,
        queueNote: queueText.value,
      })
    : null,
);
const band = computed(() => (view.value ? summaryBand(view.value) : null));
// 단계 화면이 읽는 조회가 끝났는가 — 상세에서 돌아온 자리를 그 뒤에 맞춘다
const stepLoaded = computed(() => {
  const s = work.state.value;
  if (step.value === "topics") return !!s.topics;
  if (step.value === "reading") return !!s.reading;
  return !!s.proposal;
});

// ── 상세에서 돌아온 자리 ──────────────────────────────────
// 보고서는 비동기로 다시 그려 브라우저·Nuxt 의 스크롤 복원이 내용보다 먼저 끝난다 — 맞출 자리(주소의 at·y, 없으면
// 그 기록의 state)가 있으면 Nuxt 는 맞추지 않고, 누른 칩·항목을 내용이 그려진 뒤 직접 맞춘다. 완료된 연구는 최종본을
// 받은 뒤에 맞춘다 — 초안 위에서 맞추면 서론·한계가 붙는 순간 자리가 밀린다
definePageMeta({ scrollToTop: (to) => !holdsReturnSpot(to.query, import.meta.client ? window.history.state : null) });
// 단계 화면(?s=)은 그 단계의 조회가 끝난 뒤에 맞춘다 — 한 화면에 useRestorePosition 은 하나다
const restoreReady = computed(() => {
  if (!view.value || !phase.value) return false;
  return stepMode.value ? stepLoaded.value : reportState.value !== "loading";
});
// 고정 진행 막대가 화면 위에 붙어 가리는 높이 — 돌아온 자리를 그 아래로 맞춘다. 맞추는 순간에는 화면이 맨 위라 막대가 머리
// 아래 제자리에 있으므로 위치(bottom)가 아니라 높이를 쓴다(맞춘 뒤에는 막대가 화면 맨 위에 붙는다). 막대가 없으면 0
function progressInset(): number {
  return document.querySelector<HTMLElement>(".rs-page .rs-pbar")?.getBoundingClientRect().height ?? 0;
}
const restore = useRestorePosition(restoreReady, { topInset: progressInset });
// 맞추는 동안만 알린다 — 다 맞춘 뒤 사용자가 접은 목록을 다시 펼치지 않게
const revealExcluded = computed(() =>
  restore.pending.value && restore.anchor?.kind === "excluded" ? restore.anchor.cnts : null,
);
const revealReferences = computed(() =>
  restore.pending.value && restore.anchor?.kind === "reference" ? restore.anchor.cnts : null,
);

// ── 배치 A·B ──────────────────────────────────────────────
// 넓은 화면은 처음부터 2단이다 — 탐색 중에도 본문(절 자리)과 옆 칸(진행 패널·근거 장부)을 함께 본다(spec D22)
// 서버 렌더에는 폭을 모르므로 넓은 화면으로 두고, 마운트 뒤 실제 폭으로 맞춘다
const wide = ref(true);
// 손으로 고른 보기는 이번 방문 동안 따른다(저장하지 않는다). 보고서가 나와도 풀지 않는다 — 문서형을 고른 사람이 첫 절이
// 완성되는 순간 2단으로 끌려가지 않게
const layoutOverride = ref<ResearchLayout | null>(null);
const layout = computed(() => effectiveLayout(layoutOverride.value, wide.value));
// 단계 화면(stepMode)은 탐색·보고서 배치(rs-body)를 그리지 않는다 — 머리에서 보기 전환을 걷는다(눌러도 바뀌지 않다가
// [보고서 보기]로 돌아가는 순간 그때 고른 배치가 갑자기 적용된다). 이어가지 않은 딥리서치·보고서 화면은 그대로다(D15)
const canToggle = computed(() => SHOW_LAYOUT_TOGGLE && wide.value && !stepMode.value);
let media: MediaQueryList | null = null;

function onMediaChange(e: MediaQueryListEvent): void {
  wide.value = e.matches;
}

function toggleLayout(): void {
  layoutOverride.value = layout.value === "A" ? "B" : "A";
}

onMounted(() => {
  media = window.matchMedia(`(min-width: ${WIDE_MIN_PX}px)`);
  wide.value = media.matches;
  media.addEventListener("change", onMediaChange);
});

onBeforeUnmount(() => {
  media?.removeEventListener("change", onMediaChange);
});

// 현황 카드 항목에 포인터·초점을 올린 절, 눌러서 옮겨 간 절을 초안에서 함께 강조한다
const FLASH_MS = 1600;
const hover = ref<SlotHover>(NO_SLOT_HOVER);
const flashIdx = ref<number | null>(null);
const linkedIdx = computed(() => linkedSlot(flashIdx.value, hover.value));
let flashTimer: ReturnType<typeof setTimeout> | null = null;

// 현황 카드에서 절을 누르면 그 절로 옮기고 따라가기를 멈춘다 — 고른 절을 읽는 동안 다음 절이 시작돼도 끌고 가지 않는다(알약으로
// 다시 켠다). 절이 시작될 때마다 옮기는 것은 아래 따라가기(useSectionFollow)가 맡는다(spec D22 가 round04b §7-4 를 덮음)
function jumpToSection(idx: number): void {
  const el = document.getElementById(`rs-sec-${idx}`);
  if (!el) return;
  // follow 는 아래 '지금 진행하는 절 따라가기' 절에서 만든다 — 이 함수는 누를 때만 돌아 그때는 이미 있다
  follow.pause();
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  // 키보드로 누른 사람이 그 절부터 이어 읽게 초점도 옮긴다(스크롤은 위에서 했다). 이때 카드 항목의
  // blur 는 초점 상태만 푼다 — 포인터가 항목에 남아 있으면 flash 가 끝난 뒤에도 그 강조가 이어진다
  el.focus({ preventScroll: true });
  flashIdx.value = idx;
  if (flashTimer) clearTimeout(flashTimer);
  flashTimer = setTimeout(() => {
    flashIdx.value = null;
  }, FLASH_MS);
}

// 종합이 끝나 카드가 사라지면 pointerleave·blur 가 오지 않는다 — 올려 둔 강조가 초안에 남지 않게 푼다
watch(phase, (p) => {
  if (p !== "synthesizing") hover.value = NO_SLOT_HOVER;
});

onBeforeUnmount(() => {
  if (flashTimer) clearTimeout(flashTimer);
});

// ── 동작 ──────────────────────────────────────────────────
const restarting = ref(false);
const pageError = ref("");

// 확인은 누른 버튼(CancelConfirm — 화면 안 '정말 취소')이 이미 받았다. 브라우저 확인창은 쓰지 않는다 — 메인 입력창의 연구 줄과 같게
function onCancel(): void {
  void cancel();
}

async function onRestart(): Promise<void> {
  if (!view.value || restarting.value) return;
  restarting.value = true;
  pageError.value = "";
  try {
    // 원래 잡의 탐색 방식(broaden·query_context 두 칸)을 그대로 이어 쓴다 — 고르는 칸은 없다
    const jobId = await startResearch(view.value.question, restartParams(view.value.params));
    await navigateTo(`/research/${jobId}`);
  } catch (e) {
    pageError.value = researchErrorMessage(e, "새 연구를 시작하지 못했어요");
  } finally {
    restarting.value = false;
  }
}

async function copyLink(): Promise<void> {
  const url = window.location.href;
  try {
    await navigator.clipboard.writeText(url);
    showToast("링크를 복사했습니다");
  } catch {
    // 운영 게이트웨이가 http 라 clipboard API 가 없을 수 있다(보안 컨텍스트 전용)
    window.prompt("아래 주소를 복사하세요", url);
  }
}

// ── 이어가기·단계 이동 ────────────────────────────────────
const workApi = useWorkApi();
const continuing = ref(false);
const continueError = ref<string | null>(null);
const onboardingOpen = ref(false);

async function goStep(s: WorkStep | null): Promise<void> {
  await router.push({ query: withStep(route.query, s) });
}

// 단계(?s=)가 바뀌는 모든 이동 — 단계 화면의 버튼·진행 막대·사이드바 기록·브라우저 뒤로·앞으로 — 에서 맨 위로 올리고
// 새 화면의 제목으로 초점을 옮긴다. 같은 경로에서 쿼리만 바뀌면 Nuxt 기본 scrollBehavior 가 스크롤을 건드리지 않아(같은
// path 분기가 false — savedPosition 도 쓰지 않는다) 앞 화면의 높이에 머물러 빈 곳을 보게 되고, 누른 버튼은 앞 화면과 함께
// 사라져 초점이 body 로 떨어진다(키보드·스크린리더 사용자는 문서 처음부터 다시 Tab 하고 새 화면이 열린 것도 듣지 못한다).
// 첫 마운트(immediate 아님)와 상세에서 돌아와 자리를 맞추는 동안(restore.pending — 맞춘 뒤 주소의 at·y 를 떼는 replace 는
// s 를 바꾸지 않는다)은 건드리지 않는다
let focusAfterOnboarding = false;

watch(step, (now, before) => {
  if (now === before || restore.pending.value) return;
  window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  // 처음 이어가며 띄운 안내가 배경을 inert 로 막고 있다 — 안내를 닫은 뒤 옮긴다
  if (onboardingOpen.value) focusAfterOnboarding = true;
  else void nextTick(focusScreenTitle);
});

// 새 화면의 제목 — 단계 화면은 그 단계의 h2, 보고서는 보고서 제목, 아직 그려지지 않았으면(연구를 읽는 중) 연구 머리의 질문
function focusScreenTitle(): void {
  const el =
    document.querySelector<HTMLElement>(stepMode.value ? ".wk-body h2" : ".rs-report__question") ??
    document.querySelector<HTMLElement>(".rs-head__question");
  if (!el) return;
  // 보고서·머리의 제목은 tabindex 가 없는 부품(D15 — 고치지 않는다)이라 초점을 받게 여기서 단다
  if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
}

// 안내는 닫힐 때 연 순간의 초점 요소로 돌려주는데 [이 연구 이어가기]는 보고서와 함께 사라졌다 — 그 뒤(nextTick) 새 화면의
// 제목으로 옮긴다. 진행 막대의 [?]로 연 안내는 그 버튼으로 돌아간다
function closeOnboarding(): void {
  onboardingOpen.value = false;
  if (!focusAfterOnboarding) return;
  focusAfterOnboarding = false;
  void nextTick(focusScreenTitle);
}

function openWork(): void {
  void goStep(workView.value ? stepForPhase(workView.value.phase) : "topics");
}

// 화면을 떠났다 — 그 뒤 도착한 응답이 이 화면의 일(안내·단계 이동)을 하지 않게
let left = false;
onBeforeUnmount(() => {
  left = true;
});

async function onContinue(): Promise<void> {
  if (!view.value || continuing.value) return;
  const jobId = view.value.jobId;
  continuing.value = true;
  continueError.value = null;
  try {
    const continued = await workApi.continueWork(jobId);
    // 떠났거나 잡이 바뀐 뒤의 응답은 setWork 가 안에서 버린다. 서버는 이미 바뀌었으니 사이드바는 맞춘다
    work.setWork(continued);
    work.afterAction();
    // 응답을 기다리는 동안 사이드바로 다른 화면에 갔으면 여기서 멈춘다 — 경로 없는 router.push 는 지금 위치(그 화면)의
    // 경로에 붙어, 예컨대 /papers?h=…&q=… 를 ?s=topics 로 바꿔 검색 복원을 깨뜨린다
    if (left || view.value?.jobId !== jobId) return;
    work.connect();
    if (firstContinue()) onboardingOpen.value = true;
    await goStep("topics");
  } catch (e) {
    continueError.value = researchErrorMessage(e, "연구를 이어가지 못했어요");
  } finally {
    continuing.value = false;
  }
}

// 온보딩은 이 브라우저에서 처음 이어갈 때 한 번 띄운다. 저장소가 막혔으면 매번 띄운다 — 안내를 놓치는 것보다 낫다
function firstContinue(): boolean {
  const storage = safeLocalStorage();
  try {
    if (storage?.getItem(ONBOARDING_KEY)) return false;
    storage?.setItem(ONBOARDING_KEY, "1");
  } catch {
    // 막힌 저장소 — 띄운다
  }
  return true;
}

// ── 원문 보기 ─────────────────────────────────────────────
const pdfOpener = usePdfOpener();
const { pdf, closePdf } = pdfOpener;
// 단계 화면(ReadingStep·ProposalStep)의 오른쪽 딥리드 패널이 열려 있는지 — 왼쪽 메뉴(LNB) 접기가 읽는다(06e 정함 30)
const workPanelOpen = ref(false);

async function openPdf(target: OpenPdfPayload): Promise<void> {
  const problem = await pdfOpener.openPdf(target);
  if (problem) showToast(problem);
}

// ── 지금 진행하는 절 따라가기 ─────────────────────────────
// 종합 중에는 쓰는 절(초안 전에는 그 절이 될 하위질문 자리), 탐색 중에는 도는 하위질문 자리로 스크롤이 따라간다(spec D22).
// 사용자가 직접 굴리면 멈추고 알약으로 다시 켠다. 돌아온 자리를 맞추는 중·원문 뷰어·사용자가 연 인용 팝오버 동안은 옮기지 않고,
// 상세에서 돌아온 화면은 멈춘 채 시작한다(고른 자리를 빼앗지 않게). 최종본 뒤에는 대상이 없어 멈춘다
const followTargetId = computed(() =>
  followTarget({
    phase: phase.value,
    eta: eta.value,
    hasDraft: !!draft.value,
    slots: planSlotList.value,
    subqs: view.value?.subqs ?? [],
  }),
);
// 사용자가 연 인용 팝오버가 있는가 — 열린 팝오버(.rs-cite__pop)를 품은 칩 묶음(.rs-cite) 안에 초점·마지막으로 포인터를 움직인 곳·
// 누른 곳이 있다. 따라가기가 굴리거나 끝난 절의 본문이 나타나 손을 뗀 포인터 밑으로 칩이 와서 hover 로 열린 팝오버는 막힘이
// 아니다(CitationChip.vue 는 고치지 않는다 — 고정 여부를 밖에 알리지 않으므로 DOM 과 포인터 자취로 본다)
function userCitePopover(pointer: PointerTrail): boolean {
  const cites = Array.from(document.querySelectorAll(".rs-page .rs-cite__pop"), (pop) => pop.closest(".rs-cite"));
  const within = (t: EventTarget | null): boolean => t instanceof Node && cites.some((c) => !!c?.contains(t));
  return userOpenedPopover({
    open: cites.length > 0,
    focused: within(document.activeElement),
    pointed: within(pointer.moved),
    pressed: within(pointer.pressed),
  });
}

const follow = useSectionFollow({
  phase,
  target: followTargetId,
  isBlocked: (pointer) =>
    followBlocked({
      restoring: restore.pending.value,
      pdfOpen: !!pdf.value,
      userPopover: userCitePopover(pointer),
    }),
  startPaused: restore.anchor !== null,
});

// 사라지는 자리에 있던 초점을 지킨다 — 종합의 첫 절이 완성되면 절 자리(ReportSkeleton — 자리는 tabindex=-1 이라 알약 이동·누름으로
// 초점을 받는다)가 통째로 빠지고 같은 자리에 초안이 서며, 잡이 끝나면 알약이 사라진다. 그대로 두면 초점이 body 로 떨어져 키보드·
// 스크린리더 사용자가 문서 처음부터 다시 시작한다(ReportView 가 초안 → 최종본 교체에서 막아 둔 것과 같은 손실). 바뀌기 전(watch 의
// 기본 flush 'pre' — DOM 이 아직 그대로)에 초점 자리를 보고, 그린 뒤(nextTick) 그 하위질문의 절(rs-sec-N)로, 대응이 없으면 보고서
// 제목으로 옮긴다
function keepFocusAt(sectionId: string | null): void {
  void nextTick(() => {
    const el = sectionId ? document.getElementById(sectionId) : null;
    if (el) el.focus({ preventScroll: true });
    else focusScreenTitle();
  });
}

watch(slotsShown, (shown, was) => {
  if (shown || !was) return;
  const active = document.activeElement;
  if (!(active instanceof HTMLElement) || !active.closest(".rs-report--slots")) return;
  keepFocusAt(slotFocusSection(planSlotList.value, active.closest(".rs-slot")?.id ?? null));
});

// 누른 알약(다시 따라가기)은 옮겨 간 자리가 초점을 받는다(useSectionFollow 의 move) — 멈춘 채 잡이 끝나 알약이 사라질 때만 옮긴다
watch(follow.pill, (now, before) => {
  if (now !== null || before === null || follow.following.value) return;
  const active = document.activeElement;
  if (active instanceof HTMLElement && active.classList.contains("rs-follow-pill")) keepFocusAt(null);
});

// ── 내려받기(Word·PDF) ────────────────────────────────────
const { exporting, printDoc, exportDocx, printPdf } = useReportExport();

// 문서에 싣는 연구 주소 — 주소창의 쿼리·해시는 빼고 잡 주소 정본만 적는다
function researchUrl(jobId: string): string {
  return `${window.location.origin}/research/${jobId}`;
}

async function runExport(doc: ReportDoc, format: ReportExportFormat): Promise<void> {
  try {
    if (format === "docx") {
      await exportDocx(doc);
      showToast("Word 문서를 내려받았습니다");
    } else {
      await printPdf(doc);
    }
  } catch (e) {
    console.warn("[research] 내보내기 실패", e);
    // 배포 뒤 옛 화면에서 누르면 docx 조각 파일이 사라져 동적 import 가 실패한다 — 새로고침이 답이다
    showToast(
      format === "docx"
        ? "Word 문서를 만들지 못했습니다. 새로고침한 뒤 다시 시도해 주세요."
        : "인쇄 창을 열지 못했습니다. 다시 시도해 주세요.",
    );
  }
}

function downloadReport(format: ReportExportFormat): void {
  const v = view.value;
  if (!v?.report) return;
  const input = docInputFromReport(v.report, { generatedAt: v.finishedAt, url: researchUrl(v.jobId) });
  void runExport(buildReportDocument(input, new Date()), format);
}

// 작성 중·멈춘 초안은 화면에 보이는 초안(draft — 끝난 절이 하나도 없으면 null)을 그대로 문서로 만든다
function saveDraft(format: ReportExportFormat): void {
  const v = view.value;
  const saved = draft.value;
  if (!v || !saved) return;
  void runExport(buildReportDocument(docInputFromDraft(saved, v, researchUrl(v.jobId)), new Date()), format);
}

// ── 토스트 ────────────────────────────────────────────────
const toast = ref("");
let toastTimer: ReturnType<typeof setTimeout> | null = null;

function showToast(msg: string): void {
  toast.value = msg;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = "";
  }, 2400);
}
</script>
