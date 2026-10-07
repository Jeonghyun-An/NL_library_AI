<!-- frontend/components/work/ReadingStep.vue -->
<template>
  <section class="wk-screen" aria-labelledby="wk-reading-title">
    <header class="wk-screen__head">
      <h2 id="wk-reading-title" class="wk-screen__title">읽기 목록</h2>
      <p class="rs-muted">
        「{{ question }}」 탐색의 채택 근거가 후보로 들어와 있습니다. 읽을 논문을 담고, 담은 논문으로 계획서의 선행연구
        목차를 만듭니다.
      </p>
      <p v-if="topicTitle" class="wk-screen__picked">고른 주제 <strong>{{ topicTitle }}</strong></p>
      <p v-if="reading?.stale" class="rs-muted"><span class="rs-badge">다시 맞춤 필요</span> 목차를 만든 뒤 고른 주제가 바뀌었습니다 — 담은 논문을 다시 보고 [목차 다시 만들기]로 맞추세요.</p>
      <p v-if="readOnly" class="rs-muted">예시 연구는 읽기 전용입니다 — 미리 돌린 실제 기록을 그대로 보여 줍니다.</p>
    </header>

    <CorpusScopeNote :corpus="corpus" />
    <p v-if="error" class="rs-alert" role="alert">{{ error }}</p>

    <div v-if="!reading && loadError" class="rs-card rs-state">
      <p>{{ loadError }}</p>
      <button type="button" class="rs-btn" @click="reloadAll(['reading'])">다시 불러오기</button>
    </div>
    <div v-else-if="!reading" class="rs-card rs-card--wait">
      <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
      <p>읽기 목록을 불러오는 중입니다</p>
    </div>
    <template v-else>
      <FunnelCounter :funnel="reading.funnel" />
      <ReadingTable
        :items="reading.items"
        :read-only="readOnly"
        :busy="busy"
        :job-id="jobId"
        @update="update"
        @open-pdf="(payload) => emit('open-pdf', payload)"
      />
      <CandidateDrawer
        v-if="reading.excluded.length"
        :excluded="reading.excluded"
        :read-only="readOnly"
        :busy="busy"
        @revive="(cnts) => update(cnts, { state: 'candidate' })"
      />
      <div class="wk-screen__next">
        <p v-if="hint" class="rs-muted">{{ hint }}</p>
        <button v-if="reading.topic_id === null" type="button" class="rs-btn rs-btn--ghost" @click="emit('go', 'topics')">
          주제 고르기
        </button>
        <template v-else-if="outlineMade">
          <button type="button" class="rs-btn" @click="emit('go', 'proposal')">계획서로</button>
          <button
            type="button"
            class="rs-btn rs-btn--ghost"
            :disabled="readOnly || busy || !canOutline"
            @click="makeOutline(true)"
          >
            목차 다시 만들기
          </button>
        </template>
        <button
          v-else
          type="button"
          class="rs-btn"
          :disabled="readOnly || busy || !canOutline"
          @click="makeOutline(false)"
        >
          목차 만들기
        </button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import CandidateDrawer from "~/components/work/CandidateDrawer.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import FunnelCounter from "~/components/work/FunnelCounter.vue";
import ReadingTable from "~/components/work/ReadingTable.vue";
import { type ResearchWorkHandle, useWorkApi } from "~/composables/useResearchWork";
import type { OpenPdfPayload } from "~/types/research";
import type { ReadingPut, WorkResource, WorkStep } from "~/types/work";
import { canMakeOutline, outlineHint } from "~/utils/readingList";
import { httpStatus, workErrorMessage } from "~/utils/researchErrors";

// 읽기 목록 단계 화면(?s=reading, spec §4 S4). 표·서랍의 의도를 받아 PUT .../reading/{cnts_id} 로 저장하고 다시 읽는다.
// 담음 5편 이상이면 [목차 만들기] → POST .../outline 뒤 계획서 단계로 간다
const props = defineProps<{ jobId: string; work: ResearchWorkHandle; question: string }>();
const emit = defineEmits<{ go: [step: WorkStep]; "open-pdf": [payload: OpenPdfPayload] }>();

// 목차가 이미 있으면 서버 outline 생성이 지금 목차를 통째로 바꾼다 — 다시 만들기 전에 묻는다
const REMAKE_CONFIRM =
  "목차를 다시 만들면 지금 목차(묶음 이름·연구 질문·승인)가 새로 만든 목차로 바뀝니다. 계속할까요?";

const api = useWorkApi();
const busy = ref(false);
const error = ref<string | null>(null);
let saving: Promise<void> = Promise.resolve();

const state = computed(() => props.work.state.value);
const view = computed(() => state.value.work);
const reading = computed(() => state.value.reading);
const readOnly = computed(() => view.value?.is_example ?? true);
const loadError = computed(() => props.work.error.value);
const hint = computed(() => (reading.value ? outlineHint(reading.value) : null));
const canOutline = computed(() => !!reading.value && canMakeOutline(reading.value));
const outlineMade = computed(() => view.value?.phase === "proposal" || view.value?.phase === "done");
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

// 행 고침(담음·뺌·메모·묶음·순서·되살리기)은 차례로 보낸다 — 앞 저장이 도는 동안 누른 것도 버리지 않고, 같은 행의 두 고침이
// 거꾸로 도착하지 않는다. 실패해도 다시 읽어 표를 서버 값으로 맞춘다(쓰던 메모는 표가 지킨다)
function update(cnts: string, body: ReadingPut): void {
  if (readOnly.value) return;
  saving = saving.then(() => saveRow(cnts, body));
}

async function saveRow(cnts: string, body: ReadingPut): Promise<void> {
  error.value = null;
  try {
    await api.putReading(props.jobId, cnts, body);
    await reloadAll(body.state === undefined ? ["reading"] : ["reading", "work"]);
    props.work.afterAction();
  } catch (err) {
    error.value = workErrorMessage(err, "읽기 목록을 고치지 못했습니다");
    await reloadAll(httpStatus(err) === 409 ? ["reading", "work"] : ["reading"]);
  }
}

async function makeOutline(again: boolean): Promise<void> {
  if (busy.value || readOnly.value || !canOutline.value) return;
  if (again && !window.confirm(REMAKE_CONFIRM)) return;
  busy.value = true;
  error.value = null;
  try {
    // 앞서 보낸 담음 고침이 반영된 뒤에 목차를 만든다 — 서버는 그때의 담음으로 묶음을 배정한다
    await saving;
    await api.createOutline(props.jobId);
    await reloadAll(["work"]);
    props.work.afterAction();
    emit("go", "proposal");
  } catch (err) {
    error.value = workErrorMessage(err, "목차를 만들지 못했습니다");
    if (httpStatus(err) === 409) await reloadAll(["reading", "work"]);
  } finally {
    busy.value = false;
  }
}
</script>
