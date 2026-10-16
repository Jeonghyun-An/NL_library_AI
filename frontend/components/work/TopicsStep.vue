<!-- frontend/components/work/TopicsStep.vue -->
<template>
  <section class="wk-screen" aria-labelledby="wk-topics-title">
    <header class="wk-screen__head">
      <!-- tabindex="-1" — 단계를 옮기면 연구 화면이 이 제목으로 초점을 옮긴다 -->
      <h2 id="wk-topics-title" class="wk-screen__title" tabindex="-1">제목 고르기</h2>
      <p class="rs-muted">
        「{{ question }}」 {{ DEEP_RESEARCH }} 보고서에서 이어 갈 주제를 하나 고릅니다. 고른 주제로 참고문헌을 고르고 보고서를 만듭니다.
      </p>
      <p v-if="readOnly" class="rs-muted">예시 연구는 읽기 전용입니다 — 미리 돌린 실제 기록을 그대로 보여 줍니다.</p>
    </header>

    <!-- 쓰기 실패 · 다시 읽기 실패(이미 읽어 둔 카드가 옛 값일 수 있다 — [다시 시도]) · 쓰기가 오래 걸림 -->
    <SkxInlineError v-if="error" :message="error" />
    <SkxInlineError v-if="staleLine" :message="staleLine" :busy="staleRetrying" @retry="retryStale" />
    <SkxInlineError v-if="slow" :message="WORK_SLOW_MESSAGE" />

    <ConceptChips
      v-if="view"
      :concepts="view.concepts"
      :candidates="view.concept_candidates ?? null"
      :generation="conceptGen"
      :read-only="readOnly"
      :busy="busy"
      :stale="cardsStale"
      @save="saveConcepts"
      @regenerate="regenerate"
      @retry="retryConcepts"
    />
    <CorpusScopeNote :corpus="corpus" />

    <SkxErrorState
      v-if="!topics && loadFailure"
      :kind="loadFailure.kind"
      title="주제 카드를 불러오지 못했어요"
      :message="loadFailure.reason"
      @retry="reloadAll(['topics'])"
    />
    <div v-else-if="!topics" class="rs-card rs-card--wait">
      <img :src="SPINNER_SRC" alt="" class="rs-spinner" />
      <p>주제 카드를 불러오는 중입니다</p>
    </div>
    <template v-else>
      <p v-if="queueNote" class="rs-muted" aria-live="polite">{{ queueNote }}</p>
      <TopicDeck
        :topics="topics"
        :concepts="view?.concepts ?? []"
        :concepts-gen="conceptGen"
        :read-only="readOnly"
        :busy="busy"
        :saved="saved"
        @pick="pick"
        @edit="edit"
        @retry="retryCard"
        @more="more"
        @write="write"
        @arrived="onArrived"
      />
      <!-- 화면 밖에 도착한 카드가 있으면 덱 뒤에서 화면 아래에 붙어 뜬다(.wk-pill — 위에 붙이면 카드 제목을 덮었다) -->
      <button
        v-if="offscreen.length"
        type="button"
        class="rs-btn rs-btn--small wk-pill"
        aria-live="polite"
        @click="showArrived"
      >
        새 후보 {{ offscreen.length }} ↓
      </button>
      <div v-if="pickedTitle" class="wk-screen__next">
        <p class="wk-screen__picked">고른 주제 <strong>{{ pickedTitle }}</strong></p>
        <button type="button" class="rs-btn" @click="emit('go', 'reading')">참고문헌 선택하기로</button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue";
import ConceptChips from "~/components/work/ConceptChips.vue";
import CorpusScopeNote from "~/components/work/CorpusScopeNote.vue";
import TopicDeck from "~/components/work/TopicDeck.vue";
import { type ResearchWorkHandle, useSlowWrite, useWorkApi, useWorkStale } from "~/composables/useResearchWork";
import type { TopicCreate, TopicPatch, WorkResource, WorkStep } from "~/types/work";
import { DEEP_RESEARCH } from "~/utils/brand";
import { httpStatus } from "~/utils/apiErrors";
import { workErrorMessage } from "~/utils/researchErrors";
import { type DeckSaved, aiCardsStale, deckQueueLine, liveTopics } from "~/utils/topicDeck";
import { latestGeneration } from "~/utils/workEvents";
import { WORK_SAVED_STALE, WORK_SLOW_MESSAGE } from "~/utils/workErrors";

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
// 주제 조회가 낸 오류만 — 다른 조회의 오류는 이 화면의 '불러오는 중'을 가리지 않는다
const loadFailure = computed(() => props.work.failureOf("topics"));
// 카드를 읽어 둔 뒤의 다시 읽기 실패(주제·연구 요약)는 위 한 줄로 — 옛 카드가 아무 안내 없이 남지 않게
const {
  line: staleLine,
  retrying: staleRetrying,
  retry: retryStale,
  markSaved,
} = useWorkStale(props.work, ["topics", "work"], "topics");
// 쓰기가 오래 걸리면(응답 없음) 안내만 — 잠금은 그대로
const slow = useSlowWrite(busy);
// [직접 고치기]·[카드 더하기] 쓰기가 끝났다는 알림(덱·카드가 칸을 닫는다 — 다시 읽기가 실패해도)
const saved = shallowRef<DeckSaved | null>(null);
let savedSeq = 0;
// 카드 생성의 대기 → 쓰는 중은 연구 SSE 가 work.generations 로 알린다 — 주제 목록을 다시 읽지 않아도 슬롯에 보인다
const topics = computed(() => {
  const t = state.value.topics;
  return t && view.value ? liveTopics(t, view.value.generations) : t;
});
const conceptGen = computed(() => latestGeneration(state.value, "concepts"));
// 다시 만들 AI 자리가 있다(지금 키워드와 다른 키워드로 만든 AI 카드, 키워드 생성이 실패해 카드가 없는 씨앗 자리) —
// 칩을 고치지 않아도 [이 키워드로 다시 만들기] 를 보인다
const cardsStale = computed(() =>
  topics.value && view.value ? aiCardsStale(topics.value, view.value.concepts, conceptGen.value) : false,
);
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

// 모두 다시 읽었으면 true — 하나라도 실패하면 false(그 실패는 위 한 줄이 알린다)
async function reloadAll(kinds: WorkResource[]): Promise<boolean> {
  const results = await Promise.all(kinds.map((kind) => props.work.reload(kind)));
  return results.every(Boolean);
}

interface ActOptions {
  // 쓰기 뒤 다시 읽기가 실패했을 때 위 한 줄의 머리(기본: 저장은 됐지만 화면을 새로 고치지 못했어요)
  stale?: string;
  // 쓰기 응답을 받은 직후 — 다시 읽기 결과와 상관없이 열어 둔 칸을 닫는다
  done?: () => void;
}

// 쓰기 하나 — 성공하면 kinds 를 다시 읽고 사이드바를 맞춘다. 다시 읽기가 실패하면 쓰기는 된 것이라 그 사실을 위 한 줄로
// 알린다(화면은 쓰기 전 값이다). 409 는 그 사이 상태가 바뀐 것이라(카드를 만드는 중·더 쓸 씨앗 없음·예시 연구) 주제와 연구
// 요약을 다시 읽은 뒤 서버 문구를 보인다
async function act(
  run: () => Promise<unknown>,
  kinds: WorkResource[],
  fallback: string,
  opts: ActOptions = {},
): Promise<void> {
  if (busy.value || readOnly.value) return;
  busy.value = true;
  error.value = null;
  try {
    await run();
    opts.done?.();
    if (!(await reloadAll(kinds))) markSaved(opts.stale ?? WORK_SAVED_STALE.saved);
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
    "키워드를 저장하지 못했어요",
  );
}

function retryConcepts(genId: number): void {
  void act(() => api.retryGeneration(props.jobId, genId), ["work"], "키워드를 다시 부르지 못했어요", {
    stale: WORK_SAVED_STALE.started,
  });
}

// [이 키워드로 다시 만들기] — 고른 칩이 저장된 것과 다르면 먼저 저장(PATCH work)하고 그 키워드로 AI 카드를 다시 만든다
// (POST topics/regenerate). 409(키워드가 둘 미만·키워드를 고르는 중·다시 만들 카드 없음)면 act 가 주제·연구를 다시 읽는다
function regenerate(concepts: string[]): void {
  void act(
    async () => {
      const saved = view.value?.concepts ?? [];
      if (concepts.length !== saved.length || concepts.some((c, i) => c !== saved[i])) {
        props.work.setWork(await api.patchWork(props.jobId, { concepts }));
      }
      await api.regenerateTopics(props.jobId);
    },
    ["topics", "work"],
    "카드를 다시 만들지 못했어요",
    { stale: WORK_SAVED_STALE.started },
  );
}

function retryCard(genId: number): void {
  void act(() => api.retryGeneration(props.jobId, genId), ["topics", "work"], "카드를 다시 부르지 못했어요", {
    stale: WORK_SAVED_STALE.started,
  });
}

function pick(tid: number): void {
  void act(() => api.pickTopic(props.jobId, tid), ["topics", "work"], "주제를 고르지 못했어요");
}

function edit(tid: number, body: TopicPatch): void {
  void act(() => api.editTopic(props.jobId, tid, body), ["topics", "work"], "주제 카드를 고치지 못했어요", {
    done: () => (saved.value = { kind: "edit", tid, seq: ++savedSeq }),
  });
}

function more(): void {
  void act(() => api.generateTopics(props.jobId), ["topics", "work"], "다른 방향 카드를 받지 못했어요", {
    stale: WORK_SAVED_STALE.started,
  });
}

function write(body: TopicCreate): void {
  void act(() => api.createTopic(props.jobId, body), ["topics", "work"], "주제 카드를 더하지 못했어요", {
    done: () => (saved.value = { kind: "write", tid: null, seq: ++savedSeq }),
  });
}
</script>
