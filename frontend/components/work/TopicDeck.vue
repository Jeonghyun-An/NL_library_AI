<!-- frontend/components/work/TopicDeck.vue -->
<template>
  <section class="wk-deck" aria-label="주제 카드">
    <div v-if="items.length" class="wk-deck__grid">
      <TopicCard
        v-for="item in items"
        :key="item.id"
        :item="item"
        :papers="topics.papers"
        :picked="item.id === topics.picked_id"
        :read-only="readOnly"
        :busy="busy"
        @pick="emit('pick', item.id)"
        @edit="(body) => emit('edit', item.id, body)"
        @retry="(genId) => emit('retry', genId)"
        @arrived="(el) => emit('arrived', el)"
      />
    </div>
    <p v-else class="rs-muted">아직 주제 카드가 없습니다 — [다른 방향] 으로 받거나 [직접 쓰기] 로 씁니다.</p>

    <div class="wk-deck__actions">
      <button
        type="button"
        class="rs-btn rs-btn--ghost"
        :disabled="readOnly || busy || topics.seeds_left <= 0"
        @click="emit('more')"
      >
        다른 방향
      </button>
      <button
        type="button"
        class="rs-btn rs-btn--ghost"
        :disabled="readOnly"
        :aria-expanded="writing"
        :aria-controls="writing ? 'wk-deck-write' : undefined"
        @click="toggleWrite"
      >
        직접 쓰기
      </button>
      <p class="rs-muted">{{ moreLine(topics.seeds_left) }}</p>
    </div>

    <form v-if="writing" id="wk-deck-write" class="wk-edit wk-deck__write" @submit.prevent="submitWrite">
      <label class="wk-edit__field">
        <span class="wk-edit__label">제목</span>
        <input v-model="title" class="wk-edit__input" type="text" :maxlength="TOPIC_TITLE_MAX" />
      </label>
      <label class="wk-edit__field">
        <span class="wk-edit__label">연구 질문</span>
        <textarea v-model="question" class="wk-edit__input" rows="3" :maxlength="TOPIC_QUESTION_MAX" />
      </label>
      <p v-if="problem" class="wk-edit__problem" role="alert">{{ problem }}</p>
      <div class="rs-card__actions">
        <button type="submit" class="rs-btn rs-btn--small" :disabled="readOnly || busy">카드 더하기</button>
        <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="toggleWrite">닫기</button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import TopicCard from "~/components/work/TopicCard.vue";
import type { TopicCreate, TopicPatch, TopicsView } from "~/types/work";
import { TOPIC_QUESTION_MAX, TOPIC_TITLE_MAX, deckOrder, moreLine, topicProblem } from "~/utils/topicDeck";

// 주제 카드 덱(spec §4 S3) — 카드 순서는 deckOrder, [다른 방향]·[직접 쓰기] 는 의도만 emit 한다.
// 카드 도착(arrived)은 그대로 올린다 — 화면 밖인지 보고 알약을 띄우는 것은 TopicsStep 이다
const props = defineProps<{ topics: TopicsView; readOnly: boolean; busy: boolean }>();
const emit = defineEmits<{
  pick: [tid: number];
  edit: [tid: number, body: TopicPatch];
  retry: [genId: number];
  more: [];
  write: [body: TopicCreate];
  arrived: [el: HTMLElement];
}>();

const items = computed(() => deckOrder(props.topics.items));

const writing = ref(false);
const title = ref("");
const question = ref("");
const problem = ref<string | null>(null);
// 보낼 때 이미 있던 사용자 카드 id — 저장 성공 = 새 사용자 카드 id 가 목록에 들어옴. 그때 입력을 비우고 닫는다(실패면 쓴 글을
// 지킨다). 서버가 제목을 다듬어 저장하므로(공백 접기·단정 표현 바꾸기·120자 자르기) 글자가 아니라 id 로 성공을 안다
const sentIds = ref<Set<number> | null>(null);

function toggleWrite(): void {
  writing.value = !writing.value;
  problem.value = null;
}

function submitWrite(): void {
  const body: TopicCreate = { title: title.value.trim(), question: question.value.trim() };
  problem.value = topicProblem(body);
  if (problem.value) return;
  sentIds.value = new Set(props.topics.items.filter((i) => i.origin === "user").map((i) => i.id));
  emit("write", body);
}

watch(
  () => props.topics.items,
  (list) => {
    const known = sentIds.value;
    if (!known || !list.some((i) => i.origin === "user" && !known.has(i.id))) return;
    sentIds.value = null;
    writing.value = false;
    title.value = "";
    question.value = "";
  },
);
</script>
