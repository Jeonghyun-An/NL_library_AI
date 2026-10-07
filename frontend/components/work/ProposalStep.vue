<!-- frontend/components/work/ProposalStep.vue -->
<template>
  <section class="wk-proposal" aria-labelledby="wk-proposal-title">
    <header class="wk-proposal__head">
      <h2 id="wk-proposal-title" class="wk-proposal__title">연구계획서</h2>
      <CorpusScopeNote :corpus="corpus" />
    </header>
    <p v-if="notice" class="rs-alert" :role="noticeIsError ? 'alert' : 'status'">{{ notice }}</p>

    <div v-if="!proposal && work.error.value" class="rs-card rs-card--error">
      <p>{{ work.error.value }}</p>
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
          <button type="button" class="rs-btn" :disabled="busy" @click="makeOutline">목차 만들기</button>
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
          목차 다시 만들기
        </button>
      </div>
      <OutlineEditor :proposal="proposal" :read-only="readOnly" :busy="busy || !!outlineGen" @save="saveOutline" />

      <template v-if="approved">
        <div class="rs-card wk-proposal__intro">
          <AiFootprintMeter :proposal="proposal" />
          <p class="rs-muted">
            절마다 [이 절 쓰기]를 누르세요. 선행연구 검토는 묶음마다 씁니다 — 모든 절을 한 번에 쓰는 버튼은 없습니다.
          </p>
        </div>
        <ProposalSection
          v-for="key in writableKeys"
          :key="key"
          :section-key="key"
          :label="sectionLabel(key, proposal.outline)"
          :proposal="proposal"
          :state="state"
          :read-only="readOnly"
          :busy="busy"
          :job-id="jobId"
          @write="write(key)"
          @save="saveSection(key, $event)"
          @regenerate="regenerate(key, $event)"
          @retry="retry"
        />

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
import { useReportExport } from "~/composables/useReportExport";
import { useWorkApi, type ResearchWorkHandle } from "~/composables/useResearchWork";
import type { OutlinePut, SectionPut, WorkStep } from "~/types/work";
import { isFallbackOutline } from "~/utils/outlineEdit";
import { buildProposalDocument } from "~/utils/proposalDocument";
import { sectionLabel } from "~/utils/proposalView";
import { genQueueLine } from "~/utils/queueLine";
import { versionConflict, workErrorMessage } from "~/utils/researchErrors";
import { openGeneration } from "~/utils/workEvents";

const props = defineProps<{ jobId: string; work: ResearchWorkHandle; question: string }>();
const emit = defineEmits<{ go: [step: WorkStep] }>();

const CONFLICT = "다른 곳에서 계획서가 바뀌어 다시 불러왔습니다 — 바뀐 내용을 확인한 뒤 다시 해 주세요";
// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 덮는다(계약 보강 4) — 다시 만들기 전에 묻는다
const REMAKE_CONFIRM =
  "목차를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다. 쓴 절은 남지만 '다시 맞춤 필요'가 붙습니다. 계속할까요?";

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
// 06b 가 쓰는 절 — 선행연구 묶음(목차 순서) → 연구 공백
const writableKeys = computed(() => [...(proposal.value?.outline?.groups.map((g) => g.key) ?? []), "gap"]);
// 문서에 실릴 검토 전 문단 — 문서가 그리는 절(목차 묶음 → 연구 공백)만 센다. 목차를 다시 만들며 빠진 옛 절은
// 문서에 실리지 않는다(proposalDocument printedKeys 와 같은 범위)
const printedProposed = computed(() => {
  const p = proposal.value;
  if (!p) return 0;
  return writableKeys.value.reduce(
    (n, k) => n + (p.sections[k]?.paragraphs.filter((x) => x.state === "proposed").length ?? 0),
    0,
  );
});
const canRemake = computed(() => {
  const p = proposal.value;
  return !readOnly.value && !!p?.outline && (p.stale.outline || isFallbackOutline(p.outline));
});
const remakeWhy = computed(() =>
  proposal.value?.stale.outline
    ? "주제나 읽기 목록이 바뀌었습니다 — 목차를 다시 만들면 지금 담은 논문으로 묶음을 새로 나눕니다(지금 목차를 바꿉니다)."
    : "모델이 목차 초안을 만들지 못했습니다 — 다시 만들어 볼 수 있습니다.",
);

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
  }, "목차를 만들지 못했습니다");
}

function saveOutline(body: OutlinePut): void {
  const p = proposal.value;
  if (!p) return;
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
