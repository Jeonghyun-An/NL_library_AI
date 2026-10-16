<!-- frontend/components/work/ReadingStep.vue -->
<template>
  <!-- 제목을 누르면 오른쪽에 그 논문의 딥리드 패널이 열린다(spec §12-4 D24) — 넓은 화면은 본문 옆 2단, 좁으면 서랍 -->
  <div class="wk-split" :class="{ 'is-panel-open': panelPaper !== null }">
    <section class="wk-screen wk-split__main" aria-labelledby="wk-reading-title">
      <header class="wk-screen__head">
        <!-- tabindex="-1" — 단계를 옮기면 연구 화면이 이 제목으로 초점을 옮긴다 -->
        <h2 id="wk-reading-title" class="wk-screen__title" tabindex="-1">참고문헌 선택하기</h2>
        <div v-if="reading" class="wk-screen__lead">
          <!-- 소개와 다음 단계 버튼은 읽기 목록을 불러온 뒤에만 — 소개는 미리 담은 수(preselected)를, 버튼은 주제·담은 수를 알아야
               맞는 말·맞는 상태가 된다. 버튼은 표 아래와 같은 묶음(ReadingNextActions) — 넓으면 소개 옆, 좁으면 소개 아래 -->
          <p v-if="intro" class="rs-muted wk-screen__intro">{{ intro }}</p>
          <ReadingNextActions class="wk-screen__lead-actions" where="top" v-bind="nextActions" @go="emit('go', $event)" @make="makeOutline" />
        </div>
        <p v-if="topicTitle" class="wk-screen__picked">고른 주제 <strong>{{ topicTitle }}</strong></p>
        <p v-if="reading?.stale" class="rs-muted"><span class="rs-badge">다시 맞춤 필요</span> 목차를 만든 뒤 고른 주제가 바뀌었습니다 — 담은 논문을 다시 보고 [{{ REMAKE_REPORT }}]로 맞추세요.</p>
        <!-- 읽기 전용으로 꺼진 [보고서 만들기]·[보고서 다시 만들기](위·아래 두 묶음)가 이 줄을 까닭으로 가리킨다(aria-describedby) -->
        <p v-if="readOnly" :id="READ_ONLY_ID" class="rs-muted">예시 연구는 읽기 전용입니다 — 미리 돌린 실제 기록을 그대로 보여 줍니다.</p>
      </header>

      <CorpusScopeNote :corpus="corpus" />
      <p v-if="error" class="rs-alert" role="alert">{{ error }}</p>

      <div v-if="!reading && loadError" class="rs-card rs-state">
        <p>{{ loadError }}</p>
        <button type="button" class="rs-btn" @click="reloadAll(['reading'])">다시 불러오기</button>
      </div>
      <div v-else-if="!reading" class="rs-card rs-card--wait">
        <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
        <p>참고문헌 후보를 불러오는 중입니다</p>
      </div>
      <template v-else>
        <FunnelCounter :funnel="reading.funnel" />
        <ReadingTable
          :items="reading.items"
          :read-only="readOnly"
          :busy="busy"
          :reordering="saves.reordering.value"
          :job-id="jobId"
          :active-id="panelPaper?.cntsId ?? null"
          :panel-id="PANEL_ID"
          @update="update"
          @open="openPanel"
          @open-pdf="(payload) => emit('open-pdf', payload)"
        />
        <CandidateDrawer
          v-if="reading.excluded.length"
          :excluded="reading.excluded"
          :read-only="readOnly"
          :busy="busy"
          @revive="(cnts) => update(cnts, { state: 'candidate' })"
        />
        <ReadingNextActions class="wk-screen__next" where="bottom" v-bind="nextActions" @go="emit('go', $event)" @make="makeOutline" />
      </template>
    </section>

    <DeepReadPanel
      :panel-id="PANEL_ID"
      :paper="panelPaper"
      :tabs="PANEL_TABS"
      tab="chat"
      :detail-href="panelDetailHref"
      :store="chatStore"
      @close="closePanel"
      @open-pdf="(payload) => emit('open-pdf', payload)"
      @detail="onDetail"
    >
      <template #extra>
        <div v-if="panelItem" class="wk-panel__save">
          <!-- 표의 [담음] 과 같은 저장(update) — 누른 상태(aria-pressed)가 담음이다 -->
          <button
            type="button"
            class="rs-btn rs-btn--small"
            :class="{ 'rs-btn--ghost': panelItem.state !== 'in' }"
            :aria-pressed="panelItem.state === 'in'"
            :disabled="readOnly || busy || panelItem.state === 'out'"
            @click="togglePanelSave"
          >
            담음
          </button>
          <span v-if="readOnly" class="rs-muted">예시 연구는 담을 수 없습니다 — 대화는 할 수 있습니다.</span>
          <span v-else-if="panelItem.state === 'out'" class="rs-muted">뺀 논문입니다 — 표에서 [되돌리기]를 누르면 담을 수 있습니다.</span>
        </div>
        <details v-if="panelPath" class="wk-panel__path">
          <summary>들어온 경로 — {{ panelPath.label }}</summary>
          <p class="wk-path__quote">{{ passageText(panelPath.chunk.text) }}</p>
          <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="openPathChunk">원문 보기</button>
        </details>
      </template>
    </DeepReadPanel>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import CandidateDrawer from "~/components/work/CandidateDrawer.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import DeepReadPanel from "~/components/work/DeepReadPanel.vue";
import FunnelCounter from "~/components/work/FunnelCounter.vue";
import ReadingNextActions from "~/components/work/ReadingNextActions.vue";
import ReadingTable from "~/components/work/ReadingTable.vue";
import { useReadingSaves } from "~/composables/useReadingSaves";
import { type ResearchWorkHandle, useWorkApi } from "~/composables/useResearchWork";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { OpenPdfPayload } from "~/types/research";
import type { ReadingPut, WorkResource, WorkStep } from "~/types/work";
import { type PanelPaper, panelTabs } from "~/utils/deepRead";
import type { DeepReadMessage } from "~/utils/deepReadSse";
import { detailUrl, readingAnchor } from "~/utils/detailSource";
import { passageText } from "~/utils/passageText";
import { canMakeOutline, firstPathChunk, outlineHint, pathPdfTarget, readingIntro } from "~/utils/readingList";
import { httpStatus } from "~/utils/apiErrors";
import { workErrorMessage } from "~/utils/researchErrors";
import { isPlainClick } from "~/utils/restorePosition";
import { REMAKE_REPORT } from "~/utils/workPhase";

// 읽기 목록 단계 화면(?s=reading, spec §4 S4). 표·서랍의 의도를 받아 PUT .../reading/{cnts_id} 로 저장하고 다시 읽는다.
// 담은 논문이 MIN_READING_FOR_OUTLINE 편 이상이면 [보고서 만들기] → POST .../outline 뒤 마지막 단계로 간다(반영이 목차를 자동 확정하고 그 화면이 절을 차례로
// 넣는다 — 06e D20)
const props = defineProps<{ jobId: string; work: ResearchWorkHandle; question: string }>();
const emit = defineEmits<{ go: [step: WorkStep]; "open-pdf": [payload: OpenPdfPayload]; panel: [open: boolean] }>();

// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 바꾼다 — 다시 만들기 전에 묻는다. 새 반영은 다시 자동 승인하지만
// 절 연쇄는 절도 생성 기록도 없는 키만 쓴다 — 이미 쓴 절은 다시 쓰지 않는다(06e 정함 4)
const REMAKE_CONFIRM =
  "보고서를 다시 만들면 지금 목차(묶음 이름·연구 질문·방법·승인)가 새로 만든 목차로 바뀝니다 — 연구 배경은 그대로 둡니다. 이미 쓴 절은 지우지 않고(주제·묶음·연구 질문이 바뀐 절에는 '다시 맞춤 필요'가 붙습니다) 아직 쓰지 않은 절만 자동으로 씁니다. 계속할까요?";

const api = useWorkApi();
const busy = ref(false);
const error = ref<string | null>(null);

const state = computed(() => props.work.state.value);
const view = computed(() => state.value.work);
const reading = computed(() => state.value.reading);
const readOnly = computed(() => view.value?.is_example ?? true);
// 읽기 목록 조회가 낸 오류만 — 다른 조회의 오류는 이 화면의 '불러오는 중'을 가리지 않는다
const loadError = computed(() => props.work.errorOf("reading"));
const hint = computed(() => (reading.value ? outlineHint(reading.value) : null));
// 머리 소개 — 이어가기가 미리 담은 수에 따라 승인 문구(사용자 결정 2026-10-13) 또는 옛 소개, 읽기 전용이면 첫 문장만
const intro = computed(() => readingIntro(reading.value, props.question, readOnly.value));
const canOutline = computed(() => !!reading.value && canMakeOutline(reading.value));
const outlineMade = computed(() => view.value?.phase === "proposal" || view.value?.phase === "done");
// 다음 단계 버튼 묶음(머리·표 아래 두 곳의 ReadingNextActions)이 함께 받는 상태 — 비활성 조건을 여기 한 곳에서 정한다.
// busy 는 makeOutline 의 잠금이라 위·아래 어느 쪽을 눌러도 두 묶음이 함께 꺼진다. 까닭은 hint(주제 없음·담음 모자람)와
// 읽기 전용 줄(READ_ONLY_ID) — busy 는 누른 그 순간뿐이라 따로 적지 않는다
const READ_ONLY_ID = "wk-reading-readonly";
const makeDisabled = computed(() => readOnly.value || busy.value || !canOutline.value);
const nextActions = computed(() => ({
  noTopic: reading.value?.topic_id === null,
  outlineMade: outlineMade.value,
  makeDisabled: makeDisabled.value,
  hint: hint.value,
  disabledWhyId: readOnly.value ? READ_ONLY_ID : null,
}));
// 범위 띠(spec §4 단계 공통·§7) — TopicsStep 과 같이 주제 목록의 corpus, 없으면 연구의 corpus
const corpus = computed(() => state.value.topics?.corpus ?? view.value?.corpus ?? null);
const topicTitle = computed(() => {
  const id = reading.value?.topic_id;
  if (id == null) return null;
  return state.value.topics?.items.find((i) => i.id === id)?.card?.title ?? null;
});

onMounted(() => {
  // 고른 주제는 주제 단계(TopicsStep)가 바꾸고 읽기 목록의 topic_id 는 조회 때 정해진다 — 이 단계에 들어올 때마다 다시 읽는다
  // (ensure 로 두면 다른 카드를 고르고 돌아왔을 때 머리의 '고른 주제' 가 옛 카드로 남는다)
  void props.work.reload("reading");
  void props.work.ensure("topics");
});

async function reloadAll(kinds: WorkResource[]): Promise<void> {
  await Promise.allSettled(kinds.map((kind) => props.work.reload(kind)));
}

// 행 고침(담음·뺌·메모·묶음·순서·되살리기)은 차례로 보내고, 사슬이 빌 때 한 번만 다시 읽어 표를 서버 값으로 맞춘다
// (useReadingSaves — 실패해도 다시 읽는다, 쓰던 메모는 표가 지킨다). 순서 저장이 남은 동안 표는 [위로]·[아래로] 를 끈다
const saves = useReadingSaves({
  put: (cnts, body) => api.putReading(props.jobId, cnts, body),
  reload: reloadAll,
  afterAction: () => props.work.afterAction(),
  error,
});

function update(cnts: string, body: ReadingPut): void {
  if (readOnly.value) return;
  saves.enqueue(cnts, body);
}

// ── 오른쪽 딥리드 패널(spec §12-4 D24) ─────────────────────────
// 이 단계는 딥리드 탭만 둔다. [담음] 은 표와 같은 저장 사슬(update → useReadingSaves)을 탄다. 논문별 대화는 이 방문 동안만
// 이 화면이 쥔다 — 단계를 옮기거나 새로고침하면 비운다(서버는 대화를 저장하지 않는다, 06e 정함 20)
const PANEL_ID = "wk-panel-reading";
const PANEL_TABS = panelTabs("reading");
const chatStore = new Map<string, DeepReadMessage[]>();
const { leave } = useDetailLeave();
// opener — 패널을 연 행 제목 버튼. 닫으면 그리로 초점을 돌린다
const panel = shallowRef<{ cntsId: string; opener: HTMLElement | null } | null>(null);
// 패널의 논문은 지금 표의 행에서 읽는다 — [담음] 을 누른 뒤 다시 읽은 상태가 패널에도 그대로 보인다
const panelItem = computed(() => {
  const id = panel.value?.cntsId;
  return id ? (reading.value?.items.find((i) => i.cnts_id === id) ?? null) : null;
});
const panelPaper = computed<PanelPaper | null>(() =>
  panelItem.value ? { cntsId: panelItem.value.cnts_id, meta: panelItem.value.meta } : null,
);
const panelPath = computed(() => (panelItem.value ? firstPathChunk(panelItem.value) : null));
const panelDetailHref = computed(() => (panelItem.value ? readingDetailUrl(panelItem.value.cnts_id) : null));

// 상세에서 [연구 화면으로]·뒤로 가기로 돌아오면 이 단계(s=reading)의 그 행(r-<cnts>)으로 돌아온다 — 표의 [논문 상세 ↗] 와 같은 출처
function readingDetailUrl(cnts: string): string {
  return detailUrl(cnts, { kind: "research", job: props.jobId, e: null, s: "reading" }, { at: readingAnchor(cnts), y: null });
}

// 같은 제목을 다시 누르면 닫는다(제목 버튼의 aria-expanded 와 같은 뜻)
function openPanel(cnts: string, el: HTMLElement): void {
  if (panel.value?.cntsId === cnts) {
    closePanel();
    return;
  }
  panel.value = { cntsId: cnts, opener: el };
}

// 닫으면 누른 행 제목으로 초점을 돌린다 — 그 사이 표를 다시 그려 요소가 바뀌었으면 같은 행의 제목 버튼을 찾는다
function closePanel(): void {
  const was = panel.value;
  panel.value = null;
  if (!was) return;
  void nextTick(() => {
    const back = was.opener?.isConnected
      ? was.opener
      : document.querySelector<HTMLElement>(`[data-anchor="${readingAnchor(was.cntsId)}"] .wk-reading__open`);
    back?.focus();
  });
}

// [담음] 토글 — 예시 연구·뺀 논문은 버튼이 꺼져 있다(update 도 예시 연구를 막는다)
function togglePanelSave(): void {
  const item = panelItem.value;
  if (!item || item.state === "out") return;
  update(item.cnts_id, { state: item.state === "in" ? "candidate" : "in" });
}

function openPathChunk(): void {
  const item = panelItem.value;
  const path = panelPath.value;
  if (item && path) emit("open-pdf", pathPdfTarget(item, path.chunk));
}

// [논문 상세 ↗] — 새 창·새 탭은 브라우저에 맡기고(주소에 돌아올 자리가 이미 있다), 그냥 누르면 지금 주소에 자리를 남기고 떠난다
function onDetail(e: MouseEvent): void {
  const item = panelItem.value;
  if (!item || !isPlainClick(e)) return;
  e.preventDefault();
  void leave(readingDetailUrl(item.cnts_id), { at: readingAnchor(item.cnts_id), y: null });
}

// 패널이 열리고 닫히는 것을 연구 화면에 알린다 — 넓은 화면에서 왼쪽 메뉴(LNB)를 접는다(06e 정함 30). 단계를 옮기면 이 화면이
// 내려가며 닫힘을 알리므로 연구 화면은 단계를 따로 보지 않는다
watch(
  () => panelPaper.value !== null,
  (open) => emit("panel", open),
);
onBeforeUnmount(() => emit("panel", false));

async function makeOutline(again: boolean): Promise<void> {
  if (busy.value || readOnly.value || !canOutline.value) return;
  if (again && !window.confirm(REMAKE_CONFIRM)) return;
  busy.value = true;
  error.value = null;
  try {
    // 앞서 보낸 담음 고침이 반영된 뒤에 목차를 만든다 — 서버는 그때의 담음으로 묶음을 배정한다
    await saves.idle();
    await api.createOutline(props.jobId);
    await reloadAll(["work"]);
    props.work.afterAction();
    emit("go", "proposal");
  } catch (err) {
    error.value = workErrorMessage(err, "보고서를 만들지 못했어요");
    if (httpStatus(err) === 409) await reloadAll(["reading", "work"]);
  } finally {
    busy.value = false;
  }
}
</script>
