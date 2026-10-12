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

    <!-- 새 검색 — 랜딩 첫 화면으로 -->
    <div class="skx-lnb__new">
      <button type="button" class="skx-newchat" @click="newSearch">
        <span class="skx-newchat__icon"><img src="/img/ico-newchat.svg" alt="" /></span>
        <span class="skx-newchat__label">새 검색</span>
      </button>
    </div>

    <!-- 메뉴 -->
    <nav v-if="SHOW_MOCKS" class="skx-lnb__menu" aria-label="주요 메뉴">
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

    <!-- 검색기록 — 딥리서치 묶음 · 최근 검색(소장자료·논문 섞어 최신순) -->
    <div class="skx-history">
      <div class="skx-history__body">
        <ClientOnly>
          <p v-if="!researchRows.length && !recentRows.length" class="skx-history__empty">
            아직 검색 기록이 없어요.
          </p>

          <!-- 딥리서치: 진행 중·승인 대기가 위로, 그다음 최신순 -->
          <section v-if="researchRows.length" class="skx-history__group" aria-labelledby="skx-history-research">
            <div class="skx-history__head">
              <p id="skx-history-research" class="skx-history__title">딥리서치</p>
              <span v-if="liveCount > 0" class="skx-history__live">진행 중 {{ liveCount }}</span>
            </div>
            <ul class="skx-history__list">
              <li v-for="h in researchRows" :key="h.id" class="skx-history__row">
                <button
                  type="button"
                  :class="['skx-history-item', h.id === activeId && 'is-active']"
                  :aria-current="h.id === activeId ? 'page' : undefined"
                  @click="go(h)"
                >
                  <span class="skx-history-item__query">{{ h.title }}</span>
                  <span class="skx-history-item__meta">
                    <span :class="['skx-history-badge', `is-${badgeOf(h).tone}`]">{{ badgeOf(h).label }}</span>
                    <!-- 06d: 단계 문구(stage text)는 이 배지 옆에 붙인다 -->
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
            <!-- 06d: 5개를 넘으면 여기에 '모두 보기 (N)' 줄 — N 은 groups.research.length -->
          </section>

          <!-- 최근 검색: 소장자료·논문 -->
          <section v-if="recentRows.length" class="skx-history__group" aria-labelledby="skx-history-recent">
            <div class="skx-history__head">
              <p id="skx-history-recent" class="skx-history__title">최근 검색</p>
              <button type="button" class="skx-history__clear" @click="confirmOpen = true">전체 삭제</button>
            </div>

            <div v-if="confirmOpen" class="skx-history__confirm" role="alertdialog" aria-live="assertive">
              <p class="skx-history__confirm-text">{{ CLEAR_TEXT }}</p>
              <div class="skx-history__confirm-actions">
                <button type="button" class="skx-history__confirm-btn is-danger" @click="clearRecent">
                  지우기
                </button>
                <button type="button" class="skx-history__confirm-btn" @click="confirmOpen = false">
                  취소
                </button>
              </div>
            </div>

            <ul class="skx-history__list">
              <li v-for="r in recentRows" :key="r.entry.id" class="skx-history__row">
                <button
                  type="button"
                  :class="['skx-history-item', r.entry.id === activeId && 'is-active']"
                  :aria-current="r.entry.id === activeId ? 'page' : undefined"
                  @click="go(r.entry)"
                >
                  <span class="skx-history-item__query">{{ r.entry.title }}</span>
                  <span class="skx-history-item__meta">
                    <span class="skx-history-chip">{{ r.label }}</span>
                    <span class="skx-history-item__time">{{ formatTime(r.entry.updatedAt ?? r.entry.createdAt) }}</span>
                  </span>
                </button>
                <button
                  type="button"
                  class="skx-history-item__del"
                  :aria-label="`'${r.entry.title}' 기록 삭제`"
                  @click="remove(r.entry.id)"
                >
                  <img src="/img/ico-delete.svg" alt="" />
                </button>
              </li>
            </ul>
          </section>
        </ClientOnly>
      </div>
    </div>

    <!-- 프로필 -->
    <div v-if="SHOW_MOCKS" class="skx-profile">
      <img class="skx-profile__avatar" src="/img/ico-avatar.svg" alt="" />
      <span class="skx-profile__name">김랜드</span>
      <button type="button" class="skx-icon-btn" aria-label="설정">
        <img src="/img/ico-settings.svg" alt="" />
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { HistoryEntry } from "~/types/history";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { readV1Map } from "~/utils/historyStore";
import { activeIdFor, routeFor } from "~/utils/historyRoute";
import { countLiveResearch, groupSidebarHistory } from "~/utils/sidebarGroups";

const props = defineProps<{ collapsed?: boolean }>();
const emit = defineEmits<{ cart: []; save: [] }>();

// 딥리서치 묶음에 보이는 행 수 — 넘치는 만큼은 06d 의 '모두 보기 (N)' 가 맡는다
const RESEARCH_ROW_LIMIT = 5;
// 최근 검색(도서·논문) 전체 삭제 확인 문구 — 딥리서치는 이 삭제에 들지 않는다
const CLEAR_TEXT = "최근 검색 기록을 모두 지울까요? 딥리서치 기록은 지워지지 않습니다.";
const POLL_MS = 30_000;

const route = useRoute();
const router = useRouter();
const history = useHistory();

// open 에는 사용자가 누른 상태만 둔다 — 채팅 때문에 접힌 상태를 여기 쓰면, 채팅을 연 채 페이지를 떠날 때
// 되돌릴 기회가 없어 다음 페이지들까지 접힌 채로 남는다
const open = useState<boolean>("skx:lnb-open", () => true);
const isCollapsed = computed(() => !open.value || !!props.collapsed);
const confirmOpen = ref(false);
const v1Map = ref<Record<string, string>>({});

const groups = computed(() => groupSidebarHistory(history.entries.value));
const researchRows = computed(() => groups.value.research.slice(0, RESEARCH_ROW_LIMIT));
const recentRows = computed(() => groups.value.recent);
const liveCount = computed(() => countLiveResearch(groups.value.research));
const hasLiveResearch = computed(() => liveCount.value > 0);
const activeId = computed(() => activeIdFor(route.path, route.query, v1Map.value));

// 기록이 하나씩 지워져 비면 열려 있던 확인창도 함께 닫는다 — 안 닫으면 다음 기록이 생길 때 되살아난다
watch(
  () => recentRows.value.length,
  (n) => {
    if (!n) confirmOpen.value = false;
  },
);

// 랜딩의 첫 화면으로 간다. '/' 에서 결과(?q=·?h=)를 보던 중이면 쿼리가 사라지는 이동이라,
// pages/index.vue 의 route.query watch 가 같은 페이지에서 goLanding 으로 결과를 걷는다 — 이쪽에서 따로 비울 상태는 없다
function newSearch() {
  confirmOpen.value = false;
  void router.push({ path: "/" });
}

function go(h: HistoryEntry) {
  router.push(routeFor(h));
}

function remove(id: string) {
  void history.remove(id);
}

async function clearRecent() {
  confirmOpen.value = false;
  await history.clear("book");
  await history.clear("paper");
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
/* 검색기록 영역 전체가 스크롤한다 — 묶음마다 따로 스크롤하지 않는다 */
.skx-history__body {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.skx-history__group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.skx-history__group .skx-history__list {
  overflow: visible;
}
.skx-history__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  min-height: 1.2rem;
}
.skx-history__group .skx-history__title {
  color: var(--skx-teal-ink);
}
/* '진행 중 N' — 살아 있는 딥리서치가 있다는 표시. 행 배지(진행 중)와 같은 산호색 */
.skx-history__live {
  flex: none;
  padding: 0 0.4rem;
  border-radius: var(--skx-radius-pill);
  background: var(--skx-primary);
  color: var(--skx-on-accent);
  font-size: 0.5rem;
  font-weight: 700;
  line-height: 1.6;
}
.skx-history__clear {
  padding: 0.1rem 0.4rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  font-size: 0.6rem;
  color: var(--skx-gray-1);
  cursor: pointer;
}
.skx-history__clear:hover {
  color: var(--skx-primary);
  background: var(--skx-glass-teal);
}
.skx-history__empty {
  margin: 0;
  padding: 0.8rem 0.4rem;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-gray-1);
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
  color: var(--skx-gray-1);
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
/* 종류 라벨(소장자료·논문) — 조용한 청록 알약 */
.skx-history-chip {
  flex: none;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  background: var(--skx-glass-teal);
  color: var(--skx-teal-ink);
  font-size: 0.5rem;
  font-weight: 600;
  line-height: 1.6;
}
/* 상태 배지 — 진행 중은 산호 면, 승인 대기는 산호 테두리(사용자가 움직여야 하는 상태) */
.skx-history-badge {
  flex: none;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  font-size: 0.5rem;
  font-weight: 600;
  line-height: 1.6;
  background: var(--skx-primary);
  color: var(--skx-on-accent);
}
.skx-history-badge.is-done {
  background: var(--skx-success-bg);
  color: var(--skx-success);
}
.skx-history-badge.is-failed {
  background: var(--skx-danger-bg);
  color: var(--skx-danger);
}
.skx-history-badge.is-waiting {
  background: none;
  color: var(--skx-primary);
  box-shadow: inset 0 0 0 1px var(--skx-primary);
}
.skx-history-badge.is-canceled,
.skx-history-badge.is-unknown {
  background: var(--skx-glass-teal);
  color: var(--skx-gray-1);
}
.skx-history__confirm {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.6rem;
  border: 1px solid var(--skx-glass-border);
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
  color: var(--skx-ink);
  cursor: pointer;
}
.skx-history__confirm-btn:hover {
  background: var(--skx-glass-teal);
}
.skx-history__confirm-btn.is-danger {
  border-color: var(--skx-danger);
  background: var(--skx-danger);
  color: var(--skx-on-accent);
}
</style>
