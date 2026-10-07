<!-- frontend/components/work/TopicsStep.vue -->
<template>
  <section class="wk-screen" aria-labelledby="wk-topics-title">
    <header class="wk-screen__head">
      <h2 id="wk-topics-title" class="wk-screen__title">주제 고르기</h2>
      <p class="rs-muted">
        「{{ question }}」 보고서에서 이어 갈 주제를 하나 고릅니다. 고른 주제로 읽기 목록과 계획서를 만듭니다.
      </p>
      <p v-if="readOnly" class="rs-muted">예시 연구는 읽기 전용입니다 — 미리 돌린 실제 기록을 그대로 보여 줍니다.</p>
    </header>

    <p v-if="error" class="rs-alert" role="alert">{{ error }}</p>

    <ConceptChips
      v-if="view"
      :concepts="view.concepts"
      :generation="conceptGen"
      :read-only="readOnly"
      :busy="busy"
      @save="saveConcepts"
      @retry="retryConcepts"
    />
    <CorpusScopeNote :corpus="corpus" />

    <div v-if="!topics && loadError" class="rs-card rs-state">
      <p>{{ loadError }}</p>
      <button type="button" class="rs-btn" @click="reloadAll(['topics'])">다시 불러오기</button>
    </div>
    <div v-else-if="!topics" class="rs-card rs-card--wait">
      <img src="/img/ico-spinner.svg" alt="" class="rs-spinner" />
      <p>주제 카드를 불러오는 중입니다</p>
    </div>
    <template v-else>
      <p v-if="queueNote" class="rs-muted" aria-live="polite">{{ queueNote }}</p>
      <button
        v-if="offscreen.length"
        type="button"
        class="rs-btn rs-btn--small wk-pill"
        aria-live="polite"
        @click="showArrived"
      >
        새 후보 {{ offscreen.length }} ↓
      </button>
      <TopicDeck
        :topics="topics"
        :read-only="readOnly"
        :busy="busy"
        @pick="pick"
        @edit="edit"
        @retry="retryCard"
        @more="more"
        @write="write"
        @arrived="onArrived"
      />
      <div v-if="pickedTitle" class="wk-screen__next">
        <p class="wk-screen__picked">고른 주제 <strong>{{ pickedTitle }}</strong></p>
        <button type="button" class="rs-btn" @click="emit('go', 'reading')">읽기 목록으로</button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue";
import ConceptChips from "~/components/work/ConceptChips.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import TopicDeck from "~/components/work/TopicDeck.vue";
import { type ResearchWorkHandle, useWorkApi } from "~/composables/useResearchWork";
import type { TopicCreate, TopicPatch, WorkResource, WorkStep } from "~/types/work";
import { httpStatus, workErrorMessage } from "~/utils/researchErrors";
import { deckQueueLine, liveTopics } from "~/utils/topicDeck";
import { latestGeneration } from "~/utils/workEvents";

// 주제 단계 화면(?s=topics, spec §4 S3). 잎 부품(ConceptChips·TopicDeck·TopicCard)의 의도를 받아 useWorkApi 로 부르고,
// 성공하면 바뀐 조회를 다시 읽은 뒤 사이드바를 맞춘다(afterAction). 화면은 실제 응답·이벤트로만 바뀐다
const props = defineProps<{ jobId: string; work: ResearchWorkHandle; question: string }>();
const emit = defineEmits<{ go: [step: WorkStep] }>();

const api = useWorkApi();
const busy = ref(false);
const error = ref<string | null>(null);
// 화면 밖에서 도착한 카드 요소 — '새 후보 N ↓' 알약의 수. 누를 때만 스크롤한다(자동 스크롤 없음, spec §4 단계 공통)
const offscreen = shallowRef<HTMLElement[]>([]);

const state = computed(() => props.work.state.value);
const view = computed(() => state.value.work);
const readOnly = computed(() => view.value?.is_example ?? true);
const loadError = computed(() => props.work.error.value);
// 카드 생성의 대기 → 쓰는 중은 연구 SSE 가 work.generations 로 알린다 — 주제 목록을 다시 읽지 않아도 슬롯에 보인다
const topics = computed(() => {
  const t = state.value.topics;
  return t && view.value ? liveTopics(t, view.value.generations) : t;
});
const conceptGen = computed(() => latestGeneration(state.value, "concepts"));
const corpus = computed(() => state.value.topics?.corpus ?? view.value?.corpus ?? null);
const queueNote = computed(() => (view.value ? deckQueueLine(view.value.generations) : null));
const pickedTitle = computed(() => {
  const t = topics.value;
  if (!t || t.picked_id === null) return null;
  return t.items.find((i) => i.id === t.picked_id)?.card?.title ?? null;
});

onMounted(() => {
  void props.work.ensure("topics");
});

// 카드가 도착했는데 그 카드가 뷰포트 밖이면(개념 칩·다른 카드를 보느라 스크롤한 동안) 알약에 더한다. 화면 안이면 뒤집기로 충분하다
function onArrived(el: HTMLElement): void {
  const rect = el.getBoundingClientRect();
  if (rect.bottom > 0 && rect.top < window.innerHeight) return;
  if (!offscreen.value.includes(el)) offscreen.value = [...offscreen.value, el];
}

// 알약을 누르면 처음 도착한 카드로 간다 — 움직임 줄이기면 즉시. 그 사이 덱이 다시 그려져 빠진 요소는 건너뛴다
function showArrived(): void {
  const first = offscreen.value.find((el) => el.isConnected);
  offscreen.value = [];
  if (!first) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  first.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
}

async function reloadAll(kinds: WorkResource[]): Promise<void> {
  await Promise.allSettled(kinds.map((kind) => props.work.reload(kind)));
}

// 쓰기 하나 — 성공하면 kinds 를 다시 읽고 사이드바를 맞춘다. 409 는 그 사이 상태가 바뀐 것이라(카드를 만드는 중·
// 더 쓸 씨앗 없음·예시 연구) 주제와 연구 요약을 다시 읽은 뒤 서버 문구를 보인다
async function act(run: () => Promise<unknown>, kinds: WorkResource[], fallback: string): Promise<void> {
  if (busy.value || readOnly.value) return;
  busy.value = true;
  error.value = null;
  try {
    await run();
    await reloadAll(kinds);
    props.work.afterAction();
  } catch (err) {
    error.value = workErrorMessage(err, fallback);
    if (httpStatus(err) === 409) await reloadAll(["topics", "work"]);
  } finally {
    busy.value = false;
  }
}

function saveConcepts(concepts: string[]): void {
  void act(
    async () => props.work.setWork(await api.patchWork(props.jobId, { concepts })),
    [],
    "핵심 개념을 저장하지 못했습니다",
  );
}

function retryConcepts(genId: number): void {
  void act(() => api.retryGeneration(props.jobId, genId), ["work"], "핵심 개념을 다시 부르지 못했습니다");
}

function retryCard(genId: number): void {
  void act(() => api.retryGeneration(props.jobId, genId), ["topics", "work"], "카드를 다시 부르지 못했습니다");
}

function pick(tid: number): void {
  void act(() => api.pickTopic(props.jobId, tid), ["topics", "work"], "주제를 고르지 못했습니다");
}

function edit(tid: number, body: TopicPatch): void {
  void act(() => api.editTopic(props.jobId, tid, body), ["topics", "work"], "주제 카드를 고치지 못했습니다");
}

function more(): void {
  void act(() => api.generateTopics(props.jobId), ["topics", "work"], "다른 방향 카드를 받지 못했습니다");
}

function write(body: TopicCreate): void {
  void act(() => api.createTopic(props.jobId, body), ["topics", "work"], "주제 카드를 더하지 못했습니다");
}
</script>
