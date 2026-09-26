<!-- frontend/pages/research/[id].vue -->
<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="rs-page">
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
        <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
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
          @toggle-layout="toggleLayout"
          @copy-link="copyLink"
          @cancel="onCancel"
          @retry="retry"
          @restart="onRestart"
        />
        <p v-if="actionError || pageError" class="rs-alert" role="alert">{{ actionError || pageError }}</p>

        <div class="rs-body" :class="`rs-body--${layout}`">
          <div class="rs-col-main">
            <section v-if="phase !== 'completed'" class="rs-block rs-block--plan">
              <div v-if="phase === 'planning'" class="rs-card rs-card--wait">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <p>연구 계획을 세우는 중입니다</p>
              </div>
              <PlanCard
                v-else-if="phase === 'awaiting'"
                :plan="view.plan"
                :max="maxSubquestions"
                editable
                :busy="busy"
                @approve="approve"
                @cancel="onCancel"
              />
              <div v-else-if="phase === 'queued'" class="rs-card rs-card--wait">
                <p>앞선 연구가 끝나면 시작합니다</p>
              </div>
              <PlanCard v-else-if="phase === 'exploring'" :plan="view.plan" :max="maxSubquestions" :subqs="view.subqs" />
              <div v-else-if="phase === 'synthesizing'" class="rs-card rs-card--wait">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <p>{{ synthLine }}</p>
              </div>
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

            <section v-if="reportState" class="rs-block rs-block--report">
              <ReportView
                v-if="reportState === 'ready' && view.report"
                :report="view.report"
                :generated-at="view.finishedAt"
                @open-pdf="openPdf"
                @copy-link="copyLink"
              />
              <div v-else-if="reportState === 'failed'" class="rs-card rs-card--error">
                <p class="rs-card__title">보고서를 불러오지 못했습니다</p>
                <p class="rs-muted">잠시 뒤 자동으로 다시 시도합니다</p>
                <div class="rs-card__actions">
                  <button type="button" class="rs-btn" :disabled="syncing" @click="resync">다시 불러오기</button>
                </div>
              </div>
              <div v-else class="rs-card rs-card--wait" role="status">
                <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
                <p>보고서를 불러오는 중입니다</p>
              </div>
            </section>
          </div>

          <aside class="rs-col-side">
            <ProgressPanel :view="view" :phase="phase" />
          </aside>
        </div>
      </template>
    </main>

    <PdfViewer v-if="pdf" :cnts-id="pdf.cntsId" :title="pdf.title" :page="pdf.page" @close="pdf = null" />

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import PdfViewer from "~/components/PdfViewer.vue";
import PlanCard from "~/components/research/PlanCard.vue";
import ProgressPanel from "~/components/research/ProgressPanel.vue";
import ReportView from "~/components/research/ReportView.vue";
import ResearchHeader from "~/components/research/ResearchHeader.vue";
import { apiHeaders, apiUrl } from "~/composables/useApi";
import { useResearchJob, useResearchStarter } from "~/composables/useResearch";
import type { OpenPdfPayload } from "~/types/research";
import { safeLocalStorage } from "~/utils/browserId";
import { researchPhase, synthProgress } from "~/utils/researchEvents";
import { researchErrorMessage } from "~/utils/researchErrors";
import { DEFAULT_MAX_SUBQUESTIONS } from "~/utils/researchInput";
import { reportSlot } from "~/utils/researchReport";
import {
  SHOW_LAYOUT_TOGGLE,
  WIDE_MIN_PX,
  effectiveLayout,
  readLayoutPref,
  writeLayoutPref,
  type ResearchLayout,
} from "~/utils/researchLayout";

const route = useRoute();
const { view, notFound, loadError, actionError, busy, syncFailed, syncing, load, resync, approve, retry, cancel } =
  useResearchJob(() => String(route.params.id ?? ""));
const { startResearch } = useResearchStarter();
const pdfBase = apiUrl("/books");

const phase = computed(() => (view.value ? researchPhase(view.value) : null));
const reportState = computed(() => reportSlot(phase.value, !!view.value?.report, syncFailed.value));
const maxSubquestions = computed(() => Number(view.value?.params.max_subquestions) || DEFAULT_MAX_SUBQUESTIONS);
// 계획이 없는 잡의 재시도는 서버가 409 로 거절한다
const canRetry = computed(() => (view.value?.plan.length ?? 0) > 0);
const retryLabel = computed(() => (view.value?.stage === "explored" ? "보고서 작성부터 다시 시도" : "다시 시도"));
const synthLine = computed(() => {
  if (!view.value) return "";
  const p = synthProgress(view.value);
  return p.total ? `보고서 작성 중 ${p.current}/${p.total}` : "보고서 작성 중";
});

useHead({ title: () => (view.value ? `${view.value.question} — 딥리서치` : "딥리서치") });

// ── 배치 A·B ──────────────────────────────────────────────
// 서버 렌더에는 폭을 모르므로 넓은 화면으로 두고, 마운트 뒤 실제 폭으로 맞춘다
const wide = ref(true);
const layoutPref = ref<ResearchLayout | null>(null);
const layout = computed(() => effectiveLayout(layoutPref.value, wide.value));
const canToggle = computed(() => SHOW_LAYOUT_TOGGLE && wide.value);
let media: MediaQueryList | null = null;

function onMediaChange(e: MediaQueryListEvent): void {
  wide.value = e.matches;
}

function toggleLayout(): void {
  const next: ResearchLayout = layout.value === "A" ? "B" : "A";
  layoutPref.value = next;
  writeLayoutPref(safeLocalStorage(), next);
}

onMounted(() => {
  layoutPref.value = readLayoutPref(safeLocalStorage());
  media = window.matchMedia(`(min-width: ${WIDE_MIN_PX}px)`);
  wide.value = media.matches;
  media.addEventListener("change", onMediaChange);
});

onBeforeUnmount(() => {
  media?.removeEventListener("change", onMediaChange);
});

// ── 동작 ──────────────────────────────────────────────────
const restarting = ref(false);
const pageError = ref("");

function onCancel(): void {
  if (window.confirm("이 연구를 취소할까요? 진행 중인 단계가 끝나는 대로 멈춥니다.")) void cancel();
}

async function onRestart(): Promise<void> {
  if (!view.value || restarting.value) return;
  restarting.value = true;
  pageError.value = "";
  try {
    const jobId = await startResearch(view.value.question);
    await navigateTo(`/research/${jobId}`);
  } catch (e) {
    pageError.value = researchErrorMessage(e, "새 연구를 시작하지 못했습니다");
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

// ── 원문 보기 ─────────────────────────────────────────────
const pdf = ref<OpenPdfPayload | null>(null);

async function pdfExists(cntsId: string): Promise<boolean> {
  const ctrl = new AbortController();
  try {
    const res = await fetch(`${pdfBase}/${encodeURIComponent(cntsId)}/pdf`, { headers: apiHeaders(), signal: ctrl.signal });
    return res.ok;
  } catch {
    // 확인 요청 자체가 실패하면 판단하지 않고 뷰어가 직접 보여 주게 둔다
    return true;
  } finally {
    // 본문은 필요 없다 — 뷰어가 다시 받는다. 끊지 않으면 PDF 전체를 두 번 내려받는다
    ctrl.abort();
  }
}

async function openPdf(target: OpenPdfPayload): Promise<void> {
  if (await pdfExists(target.cntsId)) pdf.value = target;
  else showToast("원문 파일이 없습니다");
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
