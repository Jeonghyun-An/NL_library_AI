<!-- frontend/components/work/ProposalStep.vue -->
<template>
  <section class="wk-proposal" aria-labelledby="wk-proposal-title">
    <header class="wk-proposal__head">
      <!-- tabindex="-1" — 단계를 옮기면 연구 화면이 이 제목으로 초점을 옮긴다 -->
      <h2 id="wk-proposal-title" class="wk-proposal__title" tabindex="-1">연구계획서</h2>
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
      <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
      <p>계획서를 불러오는 중입니다</p>
    </div>

    <div v-else-if="!proposal.outline" class="rs-card">
      <template v-if="outlineGen">
        <p class="rs-card__title">목차를 만드는 중입니다</p>
        <p v-if="genQueueLine(outlineGen)" class="rs-muted" role="status">{{ genQueueLine(outlineGen) }}</p>
      </template>
      <template v-else>
        <p class="rs-card__title">아직 목차가 없습니다</p>
        <p class="rs-muted">
          읽기 목록에 논문을 5편 이상 담으면 목차를 만들 수 있습니다. 선행연구 묶음의 수와 배정은 담은 논문의 핵심 개념
          소속으로 서버가 정합니다.
        </p>
        <div v-if="!readOnly" class="rs-card__actions">
          <button type="button" class="rs-btn" :disabled="busy" @click="makeOutline">{{ MAKE_REPORT }}</button>
          <button type="button" class="rs-btn rs-btn--ghost" @click="emit('go', 'reading')">읽기 목록으로</button>
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
        <!-- 큰 진행 막대(06e 정함 28) — 절을 차례로 쓰는 동안만 서고 다 쓰면 걷힌다. 글줄·퍼센트는 valuetext 로 읽힌다 -->
        <div
          v-if="bar"
          class="wk-rbar"
          role="progressbar"
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
            <h3 id="wk-doc-toc-title" class="rs-card__title">목차</h3>
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
            [보고서 만들기]로 목차가 서면 선행연구 묶음·연구 공백 절을 차례로 씁니다. 다 쓴 문단은 그대로 두어도 되고,
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
            <p v-if="background.trim()" class="wk-doc__text">{{ background }}</p>
            <p v-else class="rs-muted">연구 배경을 아직 적지 않았습니다.</p>
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
            :job-id="jobId"
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
            <p v-if="proposal.outline.method.trim()" class="wk-doc__text">{{ proposal.outline.method }}</p>
            <p v-else class="rs-muted">방법을 아직 적지 않았습니다.</p>
          </section>
        </div>

        <div class="rs-card wk-proposal__export">
          <p class="rs-card__title">내려받기</p>
          <label class="wk-proposal__toggle">
            <input v-model="includeProposed" type="checkbox" :disabled="!printedProposed" />
            미수락 문단도 넣기(워터마크) — 검토 전 AI 제안 {{ printedProposed }}문단
          </label>
          <p class="rs-muted">
            {{
              includeProposed && printedProposed
                ? "문서 쪽마다 '미검토 AI 초안' 워터마크가 붙습니다."
                : "기본은 수락·수정·직접 쓴 문단만 싣습니다."
            }}
            끝에 참고문헌과 AI 사용 공개 부록이 붙습니다.
          </p>
          <div class="rs-card__actions">
            <button type="button" class="rs-btn" :disabled="exporting" @click="downloadWord">
              {{ exporting ? "만드는 중…" : "Word 로 내려받기" }}
            </button>
          </div>
        </div>
      </template>
      <p v-else class="rs-muted">목차를 승인하면 선행연구 검토(묶음마다)와 연구 공백 절을 쓸 수 있습니다.</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import AiFootprintMeter from "~/components/work/AiFootprintMeter.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import OutlineEditor from "~/components/work/OutlineEditor.vue";
import ProposalSection from "~/components/work/ProposalSection.vue";
import { useAutoReport } from "~/composables/useAutoReport";
import { useReportExport } from "~/composables/useReportExport";
import { useWorkApi, type ResearchWorkHandle } from "~/composables/useResearchWork";
import type { OutlinePut, SectionPut, WorkStep } from "~/types/work";
import { isFallbackOutline } from "~/utils/outlineEdit";
import { buildProposalDocument, printedKeys, printedProposedCount } from "~/utils/proposalDocument";
import {
  SECTION_LABELS,
  autoChainOn,
  autoTargets,
  docToc,
  outlineBackground,
  outlineToggleLabel,
  reportBar,
  sectionLabel,
  type TocItem,
} from "~/utils/proposalView";
import { genQueueLine } from "~/utils/queueLine";
import { httpStatus, versionConflict, workErrorMessage } from "~/utils/researchErrors";
import { openGeneration } from "~/utils/workEvents";
import { MAKE_REPORT, REMAKE_REPORT } from "~/utils/workPhase";

const props = defineProps<{ jobId: string; work: ResearchWorkHandle; question: string }>();
const emit = defineEmits<{ go: [step: WorkStep] }>();

const CONFLICT = "다른 곳에서 계획서가 바뀌어 다시 불러왔습니다 — 바뀐 내용을 확인한 뒤 다시 해 주세요";
// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 덮는다(계약 보강 4) — 다시 만들기 전에 묻는다. 새 반영은 다시
// 자동 승인하지만 절 연쇄는 절도 생성 기록도 없는 키만 쓴다 — 이미 쓴 절은 다시 쓰지 않는다(06e 정함 4)
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다. 이미 쓴 절은 지우지 않고(주제나 묶음이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";

const api = useWorkApi();
const { exporting, exportDocx } = useReportExport();

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
// 문서에 실릴 검토 전 문단 — 목차를 다시 만들며 빠진 옛 절은 문서에 실리지 않아 세지 않는다(공개 부록·워터마크와 같은 수)
const printedProposed = computed(() => (proposal.value ? printedProposedCount(proposal.value) : 0));
const canRemake = computed(() => {
  const p = proposal.value;
  return !readOnly.value && !!p?.outline && (p.stale.outline || isFallbackOutline(p.outline));
});
const remakeWhy = computed(() =>
  proposal.value?.stale.outline
    ? "주제나 읽기 목록이 바뀌었습니다 — 목차를 다시 만들면 지금 담은 논문으로 묶음을 새로 나눕니다(지금 목차를 바꿉니다)."
    : "모델이 목차 초안을 만들지 못했습니다 — 다시 만들어 볼 수 있습니다.",
);

// ── 보고서 자동 산출(06e D20) ─────────────────────────────
// [보고서 만들기]의 반영이 자동 승인한 목차에서 남은 절을 문서 순서대로 하나씩 넣는다 — 이 화면이 열려 있는 동안만 돌고,
// 조건은 서버 값으로 다시 계산해 탭을 닫았다 와도 남은 절부터 잇는다(useAutoReport, 정함 6)
const {
  running: autoRunning,
  stopped: autoStopped,
  skipped: autoSkipped,
  resume: resumeAuto,
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

// ── Word 내려받기 ─────────────────────────────────────────
const includeProposed = ref(false);

// 문서에 싣는 연구 주소 — 계획서 단계로 바로 열리는 주소(쿼리의 at·y 는 빼고 s 만)
function proposalUrl(): string {
  return `${window.location.origin}/research/${props.jobId}?s=proposal`;
}

async function downloadWord(): Promise<void> {
  const p = proposal.value;
  const w = workView.value;
  if (!p || !w) return;
  const doc = buildProposalDocument(
    { question: props.question, url: proposalUrl(), proposal: p, work: w, includeProposed: includeProposed.value },
    new Date(),
  );
  try {
    await exportDocx(doc);
  } catch (e) {
    console.warn("[research] 계획서 내보내기 실패", e);
    // 배포 뒤 옛 화면에서 누르면 docx 조각 파일이 사라져 동적 import 가 실패한다 — 새로고침이 답이다
    say("Word 문서를 만들지 못했습니다. 새로고침한 뒤 다시 시도해 주세요.", true);
    return;
  }
  say("Word 문서를 내려받았습니다");
  // 처음 내려받으면 연구를 마친 것으로 둔다(phase done) — 단계는 앞으로만 가므로 이미 done 이면 보내지 않는다
  if (w.phase !== "proposal" || readOnly.value) return;
  try {
    props.work.setWork(await api.patchWork(props.jobId, { phase: "done" }));
    props.work.afterAction();
  } catch (e) {
    // 내려받기는 끝났다 — 단계 표시는 다음 내려받기나 새로고침에서 다시 맞춘다
    console.warn("[research] 완료 단계를 저장하지 못했습니다", e);
  }
}
</script>
