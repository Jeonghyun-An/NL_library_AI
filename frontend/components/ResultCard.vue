<template>
  <!-- 카드 전체를 누르면 상세로 간다(마우스). 키보드는 제목 버튼이 같은 길이고, 안쪽 버튼·관련도 알약의 클릭은 카드로 번지지 않는다 -->
  <article
    :class="['skx-rc', compact && 'skx-rc--compact']"
    :data-anchor="anchor"
    @click="emit('open', $event)"
  >
    <div class="skx-rc__thumb">
      <BookCover v-if="kind === 'book'" :book-id="item.book_id" />
      <img
        v-else
        :src="thumbSrc"
        :alt="item.book_info?.title ?? ''"
        loading="lazy"
        @error="onThumbError"
      />
      <span v-if="badge" class="skx-rc__badge">{{ badge }}</span>
    </div>

    <div class="skx-rc__main">
      <div class="skx-rc__chips">
        <span v-if="aiCitedNum" class="skx-ptag skx-ptag--ai-cited">
          <span class="skx-ai-dot" aria-hidden="true"></span>
          AI 답변 인용 {{ aiCitedNum }}
        </span>
        <RelevanceBadge
          :score="item.best_score"
          :title-score="item.title_score"
          :content-score="item.content_score"
        />
        <span v-for="kw in chips" :key="kw" class="skx-tag skx-tag--keyword">#{{ kw }}</span>
        <!-- 키워드가 하나도 없는 소장자료만 — 도서관 분류(KDC) 이름 칩. '#' 없이 테두리만 있는 옅은 칩이라 키워드 칩과 구별된다 -->
        <span v-if="kdc" class="skx-rc__kdc" :title="kdc.title">
          <span class="skx-sr-only">{{ kdc.title }}: </span>{{ kdc.name }}
        </span>
      </div>
      <h3 class="skx-rc__title">
        <button type="button" class="skx-rc__title-btn">
          {{ item.book_info?.title || item.book_id }}
        </button>
      </h3>
      <p v-if="meta.author" class="skx-rc__author">{{ meta.author }}</p>
      <p v-if="meta.parts.length" class="skx-rc__meta">
        <template v-for="(part, i) in meta.parts" :key="i">
          <img v-if="part.arrow" class="skx-rc__arrow" src="/img/ico-arrow.svg" alt="" />
          <span v-else-if="i > 0" class="skx-dot" aria-hidden="true"></span>
          <span class="skx-rc__meta-text">{{ part.text }}</span>
        </template>
      </p>
    </div>

    <div class="skx-rc__actions" @click.stop>
      <div class="skx-rc__row">
        <button type="button" class="skx-btn-pview" @click="emit('pdf', $event)">원문 보기</button>
        <button
          v-if="showCite"
          type="button"
          class="skx-btn-pbmark"
          aria-label="출처 인용"
          @click="emit('cite', $event)"
        >
          <img src="/img/ico-paper-bookmark.svg" alt="" />
        </button>
      </div>
      <button type="button" class="skx-btn-ptalk" @click="emit('chat', $event)">
        <img src="/img/ico-chat.svg" alt="" />
        DeepRead
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { kdcChip } from "~/utils/kdc";
import { cardKeywords, cardMeta, type ResultKind } from "~/utils/resultCard";
import type { BookChunkGroup } from "~/types/search";

// 결과 카드 하나 — 소장자료 목록·논문 목록·'SKOVIX 추천 1권'이 같은 해부도를 쓴다(표지 · 관련도 알약 + #키워드 칩 · 제목 · 저자 · 서지 · 버튼 열).
// 어디로 가는지(상세·원문·인용·DeepRead)는 부모가 정한다 — 이 컴포넌트는 눌렸다고만 알린다. 이벤트는 원래 MouseEvent 를 그대로 넘긴다
// (부모가 e.currentTarget 으로 카드 자리를 읽는다)
const props = withDefaults(
  defineProps<{
    item: BookChunkGroup;
    kind: ResultKind;
    /** 자료에 키워드가 없을 때 칩으로 쓸 키워드(추천 이유 스트림이 준 것) */
    fallbackKeywords?: readonly string[];
    /** 논문: AI 답변이 이 논문을 N번으로 인용했다 */
    aiCitedNum?: number | null;
    /** 상세에서 돌아올 때 이 카드 자리를 되찾는 표지(data-anchor) */
    anchor?: string;
    /** [인용] 버튼 — 논문만 */
    showCite?: boolean;
    /** 표지 오른쪽 위 작은 배지('AI 추천') */
    badge?: string;
    /** 좁은 칸(추천 패널 오른쪽)용 — 버튼 열이 아래로 내려온다 */
    compact?: boolean;
  }>(),
  { fallbackKeywords: () => [], aiCitedNum: null, anchor: undefined, showCite: false, badge: undefined, compact: false },
);
const emit = defineEmits<{
  open: [e: MouseEvent];
  chat: [e: MouseEvent];
  pdf: [e: MouseEvent];
  cite: [e: MouseEvent];
}>();

const chips = computed(() => cardKeywords(props.item.book_info, props.fallbackKeywords));
const meta = computed(() => cardMeta(props.item.book_info, props.kind));
// 소장자료에서 키워드 칩이 하나도 나오지 않을 때만 분류 칩(1위 추천 카드와 목록 카드가 같은 규칙)
const kdc = computed(() => (props.kind === "book" && !chips.value.length ? kdcChip(props.item.book_info?.kdc) : null));

// 논문 표지는 서버 썸네일, 없으면 논문 기본 그림. 소장자료는 BookCover 가 자리표시를 낸다
const thumbFailed = ref(false);
const thumbSrc = computed(() =>
  thumbFailed.value ? "/img/img-paper-thumb.png" : `/api/books/${props.item.book_id}/thumbnail`,
);
function onThumbError() {
  thumbFailed.value = true;
}
</script>
