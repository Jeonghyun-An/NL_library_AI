<!-- frontend/components/work/EvidenceLedger.vue -->
<template>
  <!-- 이 컴포넌트는 탐색 시작 전부터(장부가 비어 있을 때부터) 마운트돼 있어야 첫 회차의 채택이 '새로 든 것'으로
       떨어진다 — 바깥에서 hasLedger(장부 유무)로 감싸지 말 것(간격용 감싸개도 늘 그린다). 장부를 그릴지는 안에서
       정한다(회차 끝 채택 목록을 기록하기 전 잡(06a 전)은 장부가 없어 카드를 그리지 않는다) -->
  <section v-if="shown" class="rs-card wk-ledger" aria-labelledby="wk-ledger-title">
    <header class="wk-ledger__head">
      <h2 id="wk-ledger-title" class="rs-card__title">근거 장부</h2>
      <p class="wk-ledger__count">{{ line }}</p>
    </header>

    <ol ref="adoptedList" class="wk-ledger__list" aria-label="채택한 논문">
      <li
        v-for="p in ledger.adopted"
        :key="p.cntsId"
        class="wk-ledger__paper"
        :class="{ 'is-fresh': fresh.adopted.includes(p.cntsId) }"
      >
        <span class="wk-ledger__title">{{ p.title || p.cntsId }}</span>
        <span class="wk-ledger__meta">{{ byline(p) }} · 하위질문 {{ subqLabel(p) }}</span>
      </li>
    </ol>

    <template v-if="ledger.dropped.length">
      <h3 class="wk-ledger__pile-title">뺌 {{ ledger.dropped.length }}</h3>
      <ol ref="droppedList" class="wk-ledger__list wk-ledger__list--dropped" aria-label="자기점검이 뺀 논문">
        <li
          v-for="p in ledger.dropped"
          :key="p.cntsId"
          class="wk-ledger__paper"
          :class="{ 'is-fresh': fresh.dropped.includes(p.cntsId) }"
        >
          <span class="wk-ledger__title">{{ p.title || p.cntsId }}</span>
          <span class="wk-ledger__meta">{{ byline(p) }} · 하위질문 {{ subqLabel(p) }} · {{ p.round }}회차에 뺌</span>
        </li>
      </ol>
    </template>
  </section>

  <!-- 점검이 끝날 때만 읽힌다. 다시 연 화면에서 장부 전체를 몰아 읽지 않는다. 알림 영역은 카드 밖에 늘 있어 장부
       내용보다 먼저 생긴다 — 카드와 함께 생기면 첫 알림을 놓친다(SynthProgressCard 와 같은 방식).
       문장은 알릴 때마다 새 노드(:key)로 갈아 넣는다 — 같은 문장이 연달아 오면(두 점검이 모두 '근거 2편 채택') 글자만
       바꿔서는 브라우저가 프레임마다 접근성 트리를 견줄 때 바뀐 것이 없어 두 번째를 읽지 않는다(비운 뒤 다음 틱에 다시
       넣어도 한 프레임 안에서 끝나 같다). 새로 더해진 노드는 같은 글자여도 읽힌다 -->
  <p class="rs-sr-only" role="status" aria-live="polite"><span :key="announceSeq">{{ announcement }}</span></p>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch, type Ref } from "vue";
import type { SubqView } from "~/types/research";
import {
  hasLedger,
  ledgerFollowing,
  ledgerFrom,
  ledgerLine,
  ledgerRevealTop,
  newlyAdded,
  type LedgerPaper,
  type LedgerRowSpan,
  type LedgerScroll,
} from "~/utils/evidenceLedger";
import { paperByline } from "~/utils/researchReport";

// live: 탐색 중(점검 이벤트가 오는 화면)일 때만 참 — 끝난 잡·다시 연 화면은 움직이지 않는다
const props = defineProps<{ subqs: SubqView[]; live: boolean }>();

// 떨어지는 효과의 길이(work.css 의 wk-drop·wk-sink 와 맞춘다)
const FRESH_MS = 900;

const shown = computed(() => hasLedger(props.subqs));
const ledger = computed(() => ledgerFrom(props.subqs));
const line = computed(() => ledgerLine(ledger.value));

const fresh = ref<{ adopted: string[]; dropped: string[] }>({ adopted: [], dropped: [] });
const announcement = ref("");
// 알림 문장을 담는 노드의 key — 알릴 때마다 올려 새 노드로 넣는다(템플릿의 알림 영역 주석)
const announceSeq = ref(0);
let prevAdopted: Set<string> | null = null;
let prevDropped: Set<string> | null = null;
let freshTimer: ReturnType<typeof setTimeout> | null = null;

const adoptedList = ref<HTMLOListElement | null>(null);
const droppedList = ref<HTMLOListElement | null>(null);
// 목록마다 마지막으로 둔 scrollTop — 사용자가 굴려 옮겼는지 가린다(목록이 새로 생기면 새 요소라 0 에서 시작한다)
const placed = new WeakMap<HTMLElement, number>();

watch(
  ledger,
  (l) => {
    // 효과는 실제로 도착한 점검 이벤트가 장부를 바꿨을 때만이다(시연 정직성) — 처음 그릴 때는 prev 가 없다.
    // 기준선은 live 와 상관없이 마운트 때 잡는다: 탐색 전부터 떠 있던 화면은 빈 장부가 기준선이라 첫 회차의 채택이
    // 떨어지고, 장부가 찬 채로 다시 연 화면은 그 장부가 기준선이라 움직이지 않는다
    const adopted = props.live ? newlyAdded(prevAdopted, l.adopted) : [];
    const dropped = props.live ? newlyAdded(prevDropped, l.dropped) : [];
    prevAdopted = new Set(l.adopted.map((p) => p.cntsId));
    prevDropped = new Set(l.dropped.map((p) => p.cntsId));
    if (props.live) {
      follow(adoptedList, adopted.length > 0);
      follow(droppedList, dropped.length > 0);
    }
    if (!adopted.length && !dropped.length) return;
    fresh.value = { adopted, dropped };
    announcement.value = [
      adopted.length ? `근거 ${adopted.length}편 채택` : "",
      dropped.length ? `${dropped.length}편 뺌` : "",
    ]
      .filter(Boolean)
      .join(", ");
    // 같은 문장이 연달아 와도 읽히게 새 노드로 넣는다(템플릿의 알림 영역 주석)
    announceSeq.value += 1;
    if (freshTimer) clearTimeout(freshTimer);
    freshTimer = setTimeout(() => {
      fresh.value = { adopted: [], dropped: [] };
    }, FRESH_MS);
  },
  { immediate: true },
);

// 새 채택은 지금 도는 하위질문 묶음(목록 끝)에 들고 뺌도 끝에 붙는다 — 목록(높이 14rem)을 그대로 두면 떨어지는 효과가
// 화면 밖에서 일어난다. 렌더 전(이 watch 는 렌더보다 먼저 돈다)에 사용자가 목록을 굴려 읽고 있는지 보고, 렌더 뒤 새 줄이
// 보이게 그 목록의 scrollTop 만 옮긴다(페이지는 굴리지 않는다). 부드럽게 굴리지 않고 한 번에 옮긴다 — 굴리는 동안
// 0.9초 효과의 앞부분(위에서 떨어짐)이 목록의 움직임에 묻힌다. 새 줄이 없는 바뀜에도 둔 자리를 다시 적어 둔다
function follow(list: Ref<HTMLOListElement | null>, hasFresh: boolean): void {
  const before = list.value;
  if (before && !ledgerFollowing(scrollOf(before), placed.get(before) ?? 0)) return;
  void nextTick(() => {
    const el = list.value;
    if (!el) return;
    const rows = hasFresh ? Array.from(el.querySelectorAll<HTMLElement>(".is-fresh"), rowSpan) : [];
    const top = ledgerRevealTop(scrollOf(el), rows);
    if (top !== null) el.scrollTop = top;
    placed.set(el, el.scrollTop);
  });
}

function scrollOf(el: HTMLElement): LedgerScroll {
  return { scrollTop: el.scrollTop, clientHeight: el.clientHeight, scrollHeight: el.scrollHeight };
}

// 줄의 offsetTop 은 목록(position: relative) 내용의 맨 위에서 잰다 — 스크롤과 떨어지는 효과의 transform 에 흔들리지 않는다
function rowSpan(row: HTMLElement): LedgerRowSpan {
  return { top: row.offsetTop, bottom: row.offsetTop + row.offsetHeight };
}

function byline(p: LedgerPaper): string {
  return paperByline({ personal_author: p.personalAuthor, pub_date: p.pubDate });
}

function subqLabel(p: LedgerPaper): string {
  return p.subqIdx.map((i) => i + 1).join("·");
}

onBeforeUnmount(() => {
  if (freshTimer) clearTimeout(freshTimer);
});
</script>
