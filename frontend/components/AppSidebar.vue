<!-- frontend/components/AppSidebar.vue -->
<template>
  <aside :class="['skx-lnb', isCollapsed && 'is-lnb-collapsed']">
    <!-- 접힌 상태에서 펼치기 버튼 -->
    <button
      type="button"
      class="skx-lnb__expand"
      aria-label="사이드바 열기"
      @click="open = true"
    >
      <img src="/img/ico-arrow.svg" alt="" />
    </button>

    <!-- 로고 + 접기 버튼 -->
    <div class="skx-lnb__logo">
      <a class="skx-logo" href="/" aria-label="SKOVIX 메인으로 이동">
        <img class="skx-logo__mark" src="/img/logo-mark.svg" alt="" />
        <img class="skx-logo__word" src="/img/logo-word.svg" alt="SKOVIX" />
      </a>
      <button
        type="button"
        class="skx-icon-btn"
        aria-label="사이드바 접기"
        @click="open = false"
      >
        <img src="/img/ico-collapse.svg" alt="" />
      </button>
    </div>

    <!-- 새 채팅 -->
    <!-- <div class="skx-lnb__new">
      <button type="button" class="skx-newchat" @click="navigateTo('/')">
        <span class="skx-newchat__icon"><img src="/img/ico-newchat.svg" alt=""></span>
        <span class="skx-newchat__label">새 채팅</span>
      </button>
    </div> -->

    <!-- 메뉴 -->
    <nav class="skx-lnb__menu" aria-label="주요 메뉴">
      <!-- <button type="button" class="skx-menu-item" @click="emit('cart')">
        <span class="skx-menu-item__icon"
          ><img src="/img/ico-cart-menu.svg" alt=""
        /></span>
        <span class="skx-menu-item__label">대출 장바구니</span>
      </button> -->
      <button type="button" class="skx-menu-item" @click="emit('save')">
        <span class="skx-menu-item__icon"
          ><img src="/img/ico-bookmark-menu.svg" alt=""
        /></span>
        <span class="skx-menu-item__label">저장목록</span>
      </button>
    </nav>

    <!-- 검색기록 -->
    <div class="skx-history">
      <div class="skx-history__head">
        <p class="skx-history__title">검색기록</p>
        <ClientOnly>
          <button
            v-if="activeList.length"
            type="button"
            class="skx-history__clear"
            @click="confirmOpen = true"
          >
            전체 삭제
          </button>
        </ClientOnly>
      </div>
      <div class="skx-history__tabs" role="tablist" aria-label="검색기록 종류">
        <button
          v-for="t in TABS"
          :key="t.kind"
          type="button"
          role="tab"
          :aria-selected="historyTab === t.kind"
          :class="['skx-history__tab', historyTab === t.kind && 'is-active']"
          @click="selectTab(t.kind)"
        >
          {{ t.label }}
        </button>
      </div>

      <div v-if="confirmOpen" class="skx-history__confirm" role="alertdialog" aria-live="assertive">
        <p class="skx-history__confirm-text">{{ CLEAR_TEXT[historyTab] }}</p>
        <div class="skx-history__confirm-actions">
          <button type="button" class="skx-history__confirm-btn is-danger" @click="clearTab">
            지우기
          </button>
          <button type="button" class="skx-history__confirm-btn" @click="confirmOpen = false">
            취소
          </button>
        </div>
      </div>

      <ClientOnly>
        <p v-if="!activeList.length" class="skx-history__empty">{{ EMPTY_TEXT[historyTab] }}</p>
        <ul v-else class="skx-history__list">
          <li v-for="h in activeList" :key="h.id" class="skx-history__row">
            <button
              type="button"
              :class="['skx-history-item', h.id === activeId && 'is-active']"
              :aria-current="h.id === activeId ? 'page' : undefined"
              @click="go(h)"
            >
              <span class="skx-history-item__query">{{ h.title }}</span>
              <span class="skx-history-item__meta">
                <span
                  v-if="h.kind === 'research'"
                  :class="['skx-history-badge', `is-${badgeOf(h).tone}`]"
                  >{{ badgeOf(h).label }}</span
                >
                <span class="skx-history-item__time">{{ formatTime(h.updatedAt ?? h.createdAt) }}</span>
              </span>
            </button>
            <button
              type="button"
              class="skx-history-item__del"
              :aria-label="`'${h.title}' 기록 삭제`"
              @click="remove(h.id)"
            >
              <img src="/img/ico-delete.svg" alt="" />
            </button>
          </li>
        </ul>
      </ClientOnly>
    </div>

    <!-- 프로필 -->
    <div class="skx-profile">
      <img class="skx-profile__avatar" src="/img/ico-avatar.svg" alt="" />
      <span class="skx-profile__name">김랜드</span>
      <button type="button" class="skx-icon-btn" aria-label="설정">
        <img src="/img/ico-settings.svg" alt="" />
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { HistoryEntry, HistoryKind } from "~/types/history";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { readV1Map } from "~/utils/historyStore";
import { activeIdFor, activeKindForPath, routeFor } from "~/utils/historyRoute";

const props = defineProps<{ collapsed?: boolean }>();
const emit = defineEmits<{ cart: []; save: [] }>();

const TABS: Array<{ kind: HistoryKind; label: string }> = [
  { kind: "book", label: "도서" },
  { kind: "paper", label: "논문" },
  { kind: "research", label: "딥리서치" },
];
const EMPTY_TEXT: Record<HistoryKind, string> = {
  book: "도서 검색 기록이 없습니다.",
  paper: "논문 검색 기록이 없습니다.",
  research: "딥리서치 기록이 없습니다. 논문 검색창의 + 에서 시작해 보세요.",
};
const CLEAR_TEXT: Record<HistoryKind, string> = {
  book: "도서 검색 기록을 모두 지울까요?",
  paper: "논문 검색 기록을 모두 지울까요?",
  research: "딥리서치 기록을 모두 지울까요? 보고서 자체는 지워지지 않습니다.",
};
// 이 상태의 딥리서치가 있으면 배지가 바뀔 수 있다 — 승인 대기는 사용자가 움직여야 바뀌므로 뺀다
const LIVE_STATUSES = new Set(["created", "planning", "approved", "queued", "running"]);
const POLL_MS = 30_000;

const route = useRoute();
const router = useRouter();
const history = useHistory();

// open 에는 사용자가 누른 상태만 둔다 — 채팅 때문에 접힌 상태를 여기 쓰면, 채팅을 연 채 페이지를 떠날 때
// 되돌릴 기회가 없어 다음 페이지들까지 접힌 채로 남는다
const open = useState<boolean>("skx:lnb-open", () => true);
const isCollapsed = computed(() => !open.value || !!props.collapsed);
const historyTab = ref<HistoryKind>(activeKindForPath(route.path));
const confirmOpen = ref(false);
const v1Map = ref<Record<string, string>>({});

const activeList = computed(() => history.byKind(historyTab.value).value);
const activeId = computed(() => activeIdFor(route.path, route.query, v1Map.value));
const hasLiveResearch = computed(() =>
  history
    .byKind("research")
    .value.some((h) => h.kind === "research" && !!h.research && LIVE_STATUSES.has(h.research.status)),
);

function selectTab(kind: HistoryKind) {
  historyTab.value = kind;
  confirmOpen.value = false;
}

function go(h: HistoryEntry) {
  router.push(routeFor(h));
}

function remove(id: string) {
  void history.remove(id);
}

async function clearTab() {
  confirmOpen.value = false;
  await history.clear(historyTab.value);
}

function badgeOf(h: HistoryEntry): { label: string; tone: string } {
  const status = h.kind === "research" ? h.research?.status : undefined;
  switch (status) {
    case "completed":
      return { label: "완료", tone: "done" };
    case "failed":
      return { label: "실패", tone: "failed" };
    case "canceled":
      return { label: "취소", tone: "canceled" };
    case "awaiting_approval":
      return { label: "승인 대기", tone: "waiting" };
    case undefined:
      return { label: "알 수 없음", tone: "unknown" };
    default:
      return { label: "진행 중", tone: "running" };
  }
}

function formatTime(ts: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

function pollOnce() {
  if (document.hidden || isCollapsed.value) return;
  void history.refresh("research");
}

function syncPolling() {
  if (hasLiveResearch.value && !pollTimer) pollTimer = setInterval(pollOnce, POLL_MS);
  if (!hasLiveResearch.value && pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function onVisibility() {
  if (!document.hidden && hasLiveResearch.value) pollOnce();
}

watch(hasLiveResearch, syncPolling);

onMounted(() => {
  v1Map.value = readV1Map(safeLocalStorage());
  void history.load();
  // 업그레이드 뒤 첫 로드에서는 이전이 서버 응답을 받아야 대응표가 생긴다 — 옛 ?restore= 주소의 강조를 그때 맞춘다
  void history.migrated().then(() => {
    v1Map.value = readV1Map(safeLocalStorage());
  });
  syncPolling();
  document.addEventListener("visibilitychange", onVisibility);
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
  document.removeEventListener("visibilitychange", onVisibility);
});
</script>

<style scoped>
.skx-history__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
}
.skx-history__clear {
  padding: 0.1rem 0.4rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  font-size: 0.6rem;
  color: var(--skx-gray-2);
  cursor: pointer;
}
.skx-history__clear:hover {
  color: var(--skx-primary);
  background: rgba(79, 70, 229, 0.06);
}
.skx-history__empty {
  margin: 0;
  padding: 0.8rem 0.4rem;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-gray-2);
}
.skx-history__row {
  position: relative;
}
.skx-history__row .skx-history-item {
  padding-right: 1.6rem;
}
.skx-history-item__meta {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  width: 100%;
}
.skx-history-item__meta .skx-history-item__time {
  width: auto;
}
.skx-history-item__del {
  position: absolute;
  top: 50%;
  right: 0.2rem;
  width: 1.2rem;
  height: 1.2rem;
  padding: 0.2rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  opacity: 0;
  transform: translateY(-50%);
  cursor: pointer;
  transition: opacity 0.15s;
}
.skx-history__row:hover .skx-history-item__del,
.skx-history-item__del:focus-visible {
  opacity: 1;
}
@media (hover: none) {
  .skx-history-item__del {
    opacity: 1;
  }
}
.skx-history-item__del img {
  width: 100%;
  height: 100%;
}
.skx-history-badge {
  flex: none;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  font-size: 0.5rem;
  font-weight: 600;
  line-height: 1.6;
  background: rgba(79, 70, 229, 0.1);
  color: var(--skx-primary);
}
.skx-history-badge.is-done {
  background: #e7f6ec;
  color: #1e7b3c;
}
.skx-history-badge.is-failed {
  background: #fdecec;
  color: #c62828;
}
.skx-history-badge.is-waiting {
  background: #fff5e0;
  color: #a56a00;
}
.skx-history-badge.is-canceled,
.skx-history-badge.is-unknown {
  background: #f0f0f0;
  color: var(--skx-gray-1);
}
.skx-history__confirm {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.6rem;
  border: 1px solid var(--skx-border-c1);
  border-radius: var(--skx-radius-md);
  background: var(--skx-white);
}
.skx-history__confirm-text {
  margin: 0;
  font-size: 0.6rem;
  line-height: 1.5;
  color: var(--skx-ink);
}
.skx-history__confirm-actions {
  display: flex;
  gap: 0.3rem;
  justify-content: flex-end;
}
.skx-history__confirm-btn {
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
  background: var(--skx-white);
  font-size: 0.6rem;
  cursor: pointer;
}
.skx-history__confirm-btn.is-danger {
  border-color: #c62828;
  background: #c62828;
  color: var(--skx-white);
}
</style>
