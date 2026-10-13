<!-- frontend/components/AppSidebar.vue -->
<template>
  <!-- 좁은 화면(≤768px) 전용 [사이드바 열기] — 사이드바는 본문을 밀지 않는 서랍(position: fixed, 왼쪽에서 열림)이라 본문 위 한 줄에 둔다.
       서랍이 닫히면 초점이 여기로 돌아온다. 넓은 화면에서는 CSS 로 숨는다(그쪽은 아래 접힌 띠가 한다) -->
  <button
    ref="openerBtn"
    type="button"
    class="skx-lnb-opener"
    aria-label="사이드바 열기"
    :aria-expanded="drawerOpen"
    aria-controls="skx-lnb"
    @click="openDrawer"
  >
    <img src="/img/ico-collapse.svg" alt="" />
  </button>
  <aside
    id="skx-lnb"
    ref="asideEl"
    :class="['skx-lnb', isCollapsed && 'is-lnb-collapsed', drawerOpen && 'is-drawer-open']"
    @keydown="onAsideKeydown"
  >
    <!-- 접힌 띠(데스크톱) — 위에서부터 [사이드바 열기](접기 버튼과 같은 아이콘) · [새 검색] · [DeepResearch].
         이름표는 마우스를 올리거나 키보드 초점이 갈 때 오른쪽에 뜨고 Esc 로 닫힌다. 좁은 화면(≤768px)에는 띠가 없다 — 위 [사이드바 열기]와 서랍이 대신한다.
         06e R6(사이드바 접기)는 이 띠 위에 붙인다 — 접힘 상태는 아래 open 이 정한다 -->
    <div class="skx-lnb__rail">
      <div class="skx-rail__item">
        <button
          type="button"
          class="skx-rail__btn skx-rail__btn--open"
          :aria-label="RAIL_TIPS.open"
          @click="expandFromRail"
          @pointerenter="showTip('open', $event)"
          @pointerleave="hideTip('open')"
          @focus="showTip('open', $event)"
          @blur="hideTip('open')"
        >
          <img class="skx-rail__ico" src="/img/ico-collapse.svg" alt="" />
        </button>
        <span v-if="railTip === 'open'" class="skx-rail__tip" aria-hidden="true">{{ RAIL_TIPS.open }}</span>
      </div>
      <div class="skx-rail__item skx-rail__item--extra">
        <button
          type="button"
          class="skx-rail__btn"
          :aria-label="RAIL_TIPS.new"
          @click="newSearch"
          @pointerenter="showTip('new', $event)"
          @pointerleave="hideTip('new')"
          @focus="showTip('new', $event)"
          @blur="hideTip('new')"
        >
          <img class="skx-rail__ico" src="/img/ico-newchat.svg" alt="" />
        </button>
        <span v-if="railTip === 'new'" class="skx-rail__tip" aria-hidden="true">{{ RAIL_TIPS.new }}</span>
      </div>
      <div class="skx-rail__item skx-rail__item--extra">
        <button
          type="button"
          class="skx-rail__btn"
          :aria-label="RAIL_TIPS.research"
          :aria-describedby="researchActive ? 'skx-rail-live' : undefined"
          @click="openResearchFromRail"
          @pointerenter="showTip('research', $event)"
          @pointerleave="hideTip('research')"
          @focus="showTip('research', $event)"
          @blur="hideTip('research')"
        >
          <img class="skx-rail__ico" src="/img/ico-microscope.svg" alt="" />
          <span v-if="researchActive" class="skx-rail__dot" aria-hidden="true"></span>
        </button>
        <span v-if="researchActive" id="skx-rail-live" class="skx-sr-only">진행 중이거나 승인을 기다리는 연구가 있어요</span>
        <span v-if="railTip === 'research'" class="skx-rail__tip" aria-hidden="true">{{ RAIL_TIPS.research }}</span>
      </div>
    </div>

    <!-- 로고 + 접기 버튼 -->
    <div class="skx-lnb__logo">
      <a class="skx-logo" href="/" aria-label="SKOVIX 메인으로 이동">
        <SkovixWordmark class="skx-logo__word" />
      </a>
      <button
        ref="collapseBtn"
        type="button"
        class="skx-icon-btn"
        aria-label="사이드바 접기"
        @click="collapse"
      >
        <img src="/img/ico-collapse.svg" alt="" />
      </button>
    </div>

    <!-- 새 검색 — 랜딩 첫 화면으로 -->
    <div class="skx-lnb__new">
      <button ref="newSearchBtn" type="button" class="skx-newchat" @click="newSearch">
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
        <!-- 첫 로드가 끝나기 전의 빈 목록을 '기록 없음'으로 보이지 않게 loaded 를 기다린다 -->
        <ClientOnly>
          <template v-if="loaded">
            <!-- 딥리서치: 진행 중·승인 대기가 위로, 그다음 최신순. 기록이 하나도 없어도 묶음 머리와 [+ 연구 시작하기]는 보인다.
                 머리 줄은 왼쪽 'DeepResearch' + 진행 중 배지 · 오른쪽 '전체 삭제'(기록이 있을 때만)이고, [+ 연구 시작하기]는 머리 아래 줄의 전체 폭 버튼이다 —
                 한 줄에 넷을 두면 배지와 알약이 겹쳤다 -->
            <section class="skx-history__group skx-history__group--research" aria-labelledby="skx-history-research">
              <div class="skx-history__head">
                <div class="skx-history__head-main">
                  <h2 id="skx-history-research" class="skx-history__title" tabindex="-1">{{ DEEP_RESEARCH }}</h2>
                  <span v-if="liveCount > 0" class="skx-history__live">진행 중 {{ liveCount }}</span>
                </div>
                <button
                  v-if="researchRows.length"
                  ref="researchClearBtn"
                  type="button"
                  class="skx-history__clear"
                  @click="openConfirm('research')"
                >
                  전체 삭제
                </button>
              </div>
              <button type="button" class="skx-history__start" @click="startDeepResearch">
                <span aria-hidden="true">+</span> 연구 시작하기
              </button>

              <div
                v-if="confirming === 'research'"
                class="skx-history__confirm"
                role="alertdialog"
                :aria-label="`${DEEP_RESEARCH} 기록 전체 삭제 확인`"
                aria-describedby="skx-history-research-confirm"
                @keydown.esc.stop="closeConfirm('research')"
              >
                <p id="skx-history-research-confirm" class="skx-history__confirm-text">{{ CLEAR_TEXT.research }}</p>
                <div class="skx-history__confirm-actions">
                  <button
                    ref="researchConfirmBtn"
                    type="button"
                    class="skx-history__confirm-btn is-danger"
                    @click="clearGroup('research')"
                  >
                    지우기
                  </button>
                  <button type="button" class="skx-history__confirm-btn" @click="closeConfirm('research')">
                    취소
                  </button>
                </div>
              </div>

              <ul v-if="researchRows.length" class="skx-history__list">
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
                      <span class="skx-history-item__time">{{ formatHistoryTime(entryTime(h)) }}</span>
                    </span>
                  </button>
                  <button
                    type="button"
                    class="skx-history-item__del"
                    :aria-label="`'${h.title}' 기록 삭제`"
                    @click="removeRow(h.id, $event)"
                  >
                    <img src="/img/ico-delete.svg" alt="" />
                  </button>
                </li>
              </ul>
              <!-- 5줄을 넘는 딥리서치는 '더 보기'로 이 자리에서 펼친다 -->
              <button
                v-if="researchHiddenCount > 0 || researchExpanded"
                type="button"
                class="skx-history__more"
                :aria-expanded="researchExpanded"
                @click="researchExpanded = !researchExpanded"
              >
                {{ researchExpanded ? "접기" : `더 보기 (${researchHiddenCount})` }}
              </button>
              <!-- 06d: 전용 화면으로 가는 '모두 보기 (N)' 줄은 이 자리(더 보기 버튼 아래)에 둔다 — N 은 groups.researchTotal -->
            </section>

            <p v-if="!researchRows.length && !recentRows.length" class="skx-history__empty" role="status">
              {{ listFailed ? "기록을 불러오지 못했어요. 잠시 뒤 다시 열어 주세요." : "아직 검색 기록이 없어요." }}
            </p>

            <!-- 최근 검색: 소장자료·논문 -->
            <section v-if="recentRows.length" class="skx-history__group" aria-labelledby="skx-history-recent">
              <div class="skx-history__head">
                <h2 id="skx-history-recent" class="skx-history__title" tabindex="-1">최근 검색</h2>
                <button
                  ref="recentClearBtn"
                  type="button"
                  class="skx-history__clear"
                  @click="openConfirm('recent')"
                >
                  전체 삭제
                </button>
              </div>

              <div
                v-if="confirming === 'recent'"
                class="skx-history__confirm"
                role="alertdialog"
                aria-label="최근 검색 기록 전체 삭제 확인"
                aria-describedby="skx-history-recent-confirm"
                @keydown.esc.stop="closeConfirm('recent')"
              >
                <p id="skx-history-recent-confirm" class="skx-history__confirm-text">{{ CLEAR_TEXT.recent }}</p>
                <div class="skx-history__confirm-actions">
                  <button
                    ref="recentConfirmBtn"
                    type="button"
                    class="skx-history__confirm-btn is-danger"
                    @click="clearGroup('recent')"
                  >
                    지우기
                  </button>
                  <button type="button" class="skx-history__confirm-btn" @click="closeConfirm('recent')">
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
                      <span class="skx-history-item__time">{{ formatHistoryTime(entryTime(r.entry)) }}</span>
                    </span>
                  </button>
                  <button
                    type="button"
                    class="skx-history-item__del"
                    :aria-label="`'${r.entry.title}' 기록 삭제`"
                    @click="removeRow(r.entry.id, $event)"
                  >
                    <img src="/img/ico-delete.svg" alt="" />
                  </button>
                </li>
              </ul>
            </section>
          </template>
        </ClientOnly>
      </div>
    </div>

    <!-- 프로필(목업, 숨김) — 설정(톱니)은 목업이 아니라 진짜라 늘 보인다. 접힌 띠에서는 숨는다(.skx-settings 는 접히면 통째로 숨고, 프로필 줄은 아바타만 남는다) -->
    <div v-if="SHOW_MOCKS" class="skx-profile">
      <img class="skx-profile__avatar" src="/img/ico-avatar.svg" alt="" />
      <span class="skx-profile__name">김랜드</span>
      <SettingsMenu />
    </div>
    <div v-else class="skx-settings">
      <SettingsMenu />
    </div>
  </aside>
  <!-- 서랍이 열렸을 때 본문을 덮는 어두운 막 — 누르면 닫힌다(좁은 화면에서만 그려진다) -->
  <div :class="['skx-lnb-scrim', drawerOpen && 'is-open']" aria-hidden="true" @click="closeDrawer(true)"></div>
</template>

<script setup lang="ts">
import type { HistoryEntry } from "~/types/history";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { readV1Map } from "~/utils/historyStore";
import { activeIdFor, routeFor } from "~/utils/historyRoute";
import { DEEP_RESEARCH } from "~/utils/brand";
import { deepResearchStartRoute } from "~/utils/landingStart";
import { NARROW_QUERY, trapTabTarget } from "~/utils/sidebarDrawer";
import {
  countLiveResearch,
  entryTime,
  formatHistoryTime,
  groupSidebarHistory,
  hasActiveResearch,
} from "~/utils/sidebarGroups";

const props = defineProps<{ collapsed?: boolean }>();
const emit = defineEmits<{ cart: []; save: [] }>();

// 딥리서치 묶음이 처음 보이는 행 수 — 넘치는 만큼은 '더 보기 (N)' 로 이 자리에서 펼친다(전용 화면으로 가는 '모두 보기'는 템플릿의 06d 자리 주석)
const RESEARCH_ROW_LIMIT = 5;
type ClearGroup = "research" | "recent";
// 묶음별 전체 삭제 확인 문구 — 최근 검색은 도서·논문만, 딥리서치는 따로 지운다
const CLEAR_TEXT: Record<ClearGroup, string> = {
  research: `${DEEP_RESEARCH} 기록을 모두 지울까요? 보고서 자체는 지워지지 않습니다.`,
  recent: `최근 검색 기록(소장자료·논문)을 모두 지울까요? ${DEEP_RESEARCH} 기록은 지워지지 않습니다.`,
};
const POLL_MS = 30_000;

const route = useRoute();
const router = useRouter();
const history = useHistory();

// open 에는 사용자가 누른 상태만 둔다 — 채팅 때문에 접힌 상태를 여기 쓰면, 채팅을 연 채 페이지를 떠날 때
// 되돌릴 기회가 없어 다음 페이지들까지 접힌 채로 남는다. 넓은 화면(>768px)의 펼침·접힘(띠)만 이 값이 정한다
const open = useState<boolean>("skx:lnb-open", () => true);
const isCollapsed = computed(() => !open.value || !!props.collapsed);

// ── 좁은 화면(≤768px)의 서랍 ─────────────────────────────
// 좁은 화면에서는 위 open 값과 상관없이 늘 닫힌 채 시작한다(데스크톱에서 펼쳐 둔 상태가 휴대폰에 그대로 열려 나오지 않게) —
// 서랍의 열림은 이 컴포넌트가 따로 갖는다(페이지마다 새로 마운트되므로 페이지를 옮기면 저절로 닫힌다). 서랍은 본문을 밀지 않고 위를 덮는다
const narrow = ref(false);
const drawerOpen = ref(false);
const asideEl = ref<HTMLElement | null>(null);
const openerBtn = ref<HTMLButtonElement | null>(null);
const collapseBtn = ref<HTMLButtonElement | null>(null);
let narrowMql: MediaQueryList | null = null;

const SCROLL_LOCK_CLASS = "skx-scroll-lock";

async function openDrawer() {
  drawerOpen.value = true;
  await nextTick();
  collapseBtn.value?.focus({ preventScroll: true });
}

/** 서랍 닫기 — restoreFocus 면 [사이드바 열기]로 초점을 되돌린다(Esc·막·접기 버튼) */
function closeDrawer(restoreFocus: boolean) {
  if (!drawerOpen.value) return;
  drawerOpen.value = false;
  if (restoreFocus) void nextTick(() => openerBtn.value?.focus({ preventScroll: true }));
}

/** 서랍 안의 [사이드바 접기] — 좁은 화면에서는 서랍을 닫고, 넓은 화면에서는 띠로 접는다 */
function collapse() {
  if (narrow.value) closeDrawer(true);
  else open.value = false;
}

function onDrawerEsc(e: KeyboardEvent) {
  if (e.key === "Escape" && drawerOpen.value) {
    e.preventDefault();
    closeDrawer(true);
  }
}

/** 서랍이 열린 동안 Tab 이 서랍 밖(본문)으로 새지 않게 돌린다 */
function onAsideKeydown(e: KeyboardEvent) {
  if (e.key !== "Tab" || !narrow.value || !drawerOpen.value || !asideEl.value) return;
  const items = [
    ...asideEl.value.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((el) => el.getClientRects().length > 0);
  const target = trapTabTarget(items, document.activeElement as HTMLElement | null, e.shiftKey);
  if (target) {
    e.preventDefault();
    target.focus();
  }
}

function onNarrowChange(e: MediaQueryListEvent) {
  narrow.value = e.matches;
  // 넓은 화면으로 돌아가거나 좁아지는 순간에는 서랍을 닫아 둔다(열린 채 폭이 바뀌어 막이 남지 않게)
  drawerOpen.value = false;
}

// 서랍이 열린 동안 본문 스크롤을 잠근다(Esc 도 이때만 듣는다)
watch(drawerOpen, (isOpen) => {
  document.documentElement.classList.toggle(SCROLL_LOCK_CLASS, isOpen);
  if (isOpen) document.addEventListener("keydown", onDrawerEsc);
  else document.removeEventListener("keydown", onDrawerEsc);
});
// 같은 페이지 안에서 주소가 바뀌어도(최근 검색 눌러 결과 전환 등) 서랍은 닫는다
watch(
  () => route.fullPath,
  () => closeDrawer(false),
);
const v1Map = ref<Record<string, string>>({});
// 첫 목록을 읽기 전·읽지 못한 때에 '기록 없음'을 띄우지 않으려고 쓴다(최상위 ref 라 템플릿에서 풀린다)
const { loaded, listFailed } = history;

const researchExpanded = ref(false);
const confirming = ref<ClearGroup | null>(null);
const newSearchBtn = ref<HTMLButtonElement | null>(null);
const researchClearBtn = ref<HTMLButtonElement | null>(null);
const recentClearBtn = ref<HTMLButtonElement | null>(null);
const researchConfirmBtn = ref<HTMLButtonElement | null>(null);
const recentConfirmBtn = ref<HTMLButtonElement | null>(null);

const groups = computed(() =>
  groupSidebarHistory(history.entries.value, {
    researchLimit: researchExpanded.value ? undefined : RESEARCH_ROW_LIMIT,
  }),
);
const researchRows = computed(() => groups.value.research);
const researchHiddenCount = computed(() => groups.value.researchTotal - groups.value.research.length);
const recentRows = computed(() => groups.value.recent);
// 진행 중 수·폴링은 자르기 전 전체에서 센다 — 접힌 줄 밖의 진행 중 건도 놓치지 않는다
const liveCount = computed(() => countLiveResearch(history.entries.value));
const hasLiveResearch = computed(() => liveCount.value > 0);
// 접힌 띠의 현미경 점 — 진행 중이거나 승인을 기다리는 연구가 있다는 신호(펼친 묶음의 '진행 중 N' 자리)
const researchActive = computed(() => hasActiveResearch(history.entries.value));
const activeId = computed(() => activeIdFor(route.path, route.query, v1Map.value));

// 기록이 하나씩 지워져 묶음이 비면 열려 있던 확인창을 닫고, 5줄 이하로 줄면 펼침도 푼다 —
// 안 풀면 다음에 기록이 늘 때 처음부터 펼쳐진 채 나타난다
watch(
  () => [groups.value.researchTotal, recentRows.value.length] as const,
  ([researchTotal, recentCount]) => {
    if ((confirming.value === "research" && !researchTotal) || (confirming.value === "recent" && !recentCount)) {
      confirming.value = null;
    }
    if (researchTotal <= RESEARCH_ROW_LIMIT) researchExpanded.value = false;
  },
);

const OPENER = { research: researchClearBtn, recent: recentClearBtn } as const;
const CONFIRM = { research: researchConfirmBtn, recent: recentConfirmBtn } as const;

// 확인창이 열리면 확인 버튼으로, 닫히면 연 버튼으로 초점을 옮긴다 — 키보드 사용자가 자리를 잃지 않게
async function openConfirm(group: ClearGroup) {
  confirming.value = group;
  await nextTick();
  CONFIRM[group].value?.focus();
}

async function closeConfirm(group: ClearGroup) {
  confirming.value = null;
  await nextTick();
  OPENER[group].value?.focus();
}

// 지운 묶음은 화면에서 사라져 되돌아갈 버튼이 없다 — 맨 위 새 검색 버튼으로 초점을 옮긴다
async function clearGroup(group: ClearGroup) {
  confirming.value = null;
  // 목록은 바로 비고(상태가 먼저 지운다) 서버 응답은 기다리지 않는다. 최근 검색은 도서·논문 둘이라 하이브리드 저장소가 줄 세워 보낸다
  const done =
    group === "research"
      ? history.clear("research")
      : Promise.all([history.clear("book"), history.clear("paper")]);
  await nextTick();
  const opener = OPENER[group].value;
  (opener?.isConnected ? opener : newSearchBtn.value)?.focus();
  await done;
}

// 행을 지우면 초점을 다음 행으로, 마지막 행이었으면 그 묶음 제목으로, 묶음이 사라지면 새 검색 버튼으로 옮긴다
function removeRow(id: string, ev: Event) {
  const li = (ev.currentTarget as HTMLElement).closest("li");
  const nextRow = li?.nextElementSibling?.querySelector<HTMLElement>(".skx-history-item") ?? null;
  const title = li?.closest("section")?.querySelector<HTMLElement>(".skx-history__title") ?? null;
  void history.remove(id);
  void nextTick(() => {
    const target = nextRow?.isConnected ? nextRow : title?.isConnected ? title : newSearchBtn.value;
    target?.focus();
  });
}

// ── 접힌 띠(데스크톱) ─────────────────────────────────────
// 이름표 문구가 곧 버튼의 aria-label 이다 — 이름표는 눈으로만 보는 보조라 스크린리더에는 숨긴다
const RAIL_TIPS = { open: "사이드바 열기", new: "새 검색", research: DEEP_RESEARCH } as const;
type RailKey = keyof typeof RAIL_TIPS;
const railTip = ref<RailKey | null>(null);

// 마우스는 올리면, 키보드는 초점이 갈 때만 보인다 — 터치나 마우스 클릭으로 간 초점은 이름표를 남기지 않는다
function showTip(key: RailKey, e: Event) {
  if (e instanceof PointerEvent && e.pointerType === "touch") return;
  if (e.type === "focus" && !(e.target as HTMLElement).matches(":focus-visible")) return;
  railTip.value = key;
}

function hideTip(key: RailKey) {
  if (railTip.value === key) railTip.value = null;
}

// 이름표가 떠 있는 동안 어디서든 Esc 로 닫는다(마우스만 올린 때도) — 다시 올려야 또 뜬다
function onTipEsc(e: KeyboardEvent) {
  if (e.key === "Escape") railTip.value = null;
}
watch(railTip, (now, before) => {
  if (now && !before) document.addEventListener("keydown", onTipEsc);
  if (!now && before) document.removeEventListener("keydown", onTipEsc);
});

function expandFromRail() {
  railTip.value = null;
  open.value = true;
}

// 현미경 — 사이드바를 펼치고 DeepResearch 묶음 머리로 초점을 옮긴다(펼침 폭 전환이 끝나기 전에도 머리는 이미 그려져 있다)
async function openResearchFromRail() {
  railTip.value = null;
  open.value = true;
  await nextTick();
  const head = document.getElementById("skx-history-research");
  head?.focus({ preventScroll: true });
  head?.scrollIntoView({ block: "nearest" });
}

// 랜딩의 첫 화면으로 간다. '/' 에서 결과(?q=·?h=)를 보던 중이면 쿼리가 사라지는 이동이라,
// pages/index.vue 의 route.query watch 가 같은 페이지에서 goLanding 으로 결과를 걷는다 — 이쪽에서 따로 비울 상태는 없다
function newSearch() {
  confirming.value = null;
  void router.push({ path: "/" });
}

// 딥리서치 묶음의 [+ 연구 시작하기] — 랜딩에서 논문 패널 + 딥리서치 모드를 켠다(pages/index.vue 가 ?start= 를 받는다).
// '/' 에 이미 있어도 쿼리가 바뀌는 이동이라 같은 길로 받는다
function startDeepResearch() {
  confirming.value = null;
  void router.push(deepResearchStartRoute());
}

function go(h: HistoryEntry) {
  router.push(routeFor(h));
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

let pollTimer: ReturnType<typeof setInterval> | null = null;

// 접혀 있어도 읽는다 — 접힌 띠의 현미경 점이 낡지 않게(숨은 탭에서만 건너뛴다)
function pollOnce() {
  if (document.hidden) return;
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
// 펼치는 순간 바로 한 번 새로 읽는다 — 진행 중 배지가 낡았을 수 있다
watch(isCollapsed, (collapsed, wasCollapsed) => {
  if (wasCollapsed && !collapsed && hasLiveResearch.value) pollOnce();
});
watch(drawerOpen, (isOpen) => {
  if (isOpen && hasLiveResearch.value) pollOnce();
});

onMounted(() => {
  narrowMql = window.matchMedia(NARROW_QUERY);
  narrow.value = narrowMql.matches;
  narrowMql.addEventListener("change", onNarrowChange);
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
  document.removeEventListener("keydown", onTipEsc);
  document.removeEventListener("keydown", onDrawerEsc);
  document.documentElement.classList.remove(SCROLL_LOCK_CLASS);
  narrowMql?.removeEventListener("change", onNarrowChange);
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
/* DeepResearch 묶음 카드(시안): 흰 5% 유리 — 사이드바가 이미 흐려져 있어 이 카드는 흐림 없이 바탕만 얹는다 */
.skx-history__group--research {
  padding: 0.6rem;
  background: var(--skx-frost-side-card);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-frost-hilite);
  /* 카드 안의 글 톤은 사이드바 글 톤을 올리기 전 그대로(제목 청록·행 글·시간·칩) */
  --skx-ink: var(--skx-research-ink);
  --skx-ink-2: var(--skx-research-ink-2);
  --skx-gray-1: var(--skx-research-gray-1);
  --skx-gray-2: var(--skx-research-gray-2);
  --skx-teal-ink: var(--skx-research-teal-ink);
  --skx-ico-filter: var(--skx-research-ico-filter);
}
.skx-history__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.2rem 0.4rem;
  min-height: 1.2rem;
}
/* [+ 연구 시작하기] — 머리 아래 줄의 옅은 전체 폭 버튼(새 검색 버튼보다 한 단계 작고 옅게, 산호 글·테두리). 눌러 랜딩에서 딥리서치를 시작한다 */
.skx-history__start {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.2rem;
  width: 100%;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--skx-primary);
  border-color: color-mix(in srgb, var(--skx-primary) 70%, transparent);
  border-radius: var(--skx-radius-sm);
  background: none;
  font-size: 0.65rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--skx-primary);
  white-space: nowrap;
  cursor: pointer;
  transition:
    background-color 0.15s,
    border-color 0.15s,
    color 0.15s;
}
.skx-history__start:hover {
  background: var(--skx-primary);
  border-color: var(--skx-primary);
  color: var(--skx-on-accent);
}
.skx-history__start:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
.skx-history__head-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.2rem 0.4rem;
  min-width: 0;
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
  font-size: 0.6rem;
  font-weight: 700;
  line-height: 1.5;
}
.skx-history__clear {
  flex: none;
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
  background: var(--skx-frost-bg);
}
/* 더 보기 / 접기 — 묶음 맨 아래의 조용한 글자 버튼 */
.skx-history__more {
  align-self: flex-start;
  padding: 0.2rem 0.4rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  font-size: 0.6rem;
  color: var(--skx-teal-ink);
  cursor: pointer;
}
.skx-history__more:hover {
  color: var(--skx-primary);
  background: var(--skx-frost-bg);
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
/* 아이콘 버튼 올림은 모두 같은 모양(살짝 둥근 네모 + 흰 10% 면) */
.skx-history-item__del:hover {
  background: var(--skx-frost-bg);
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
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
}
/* 상태 배지 — 진행 중은 산호 면, 승인 대기는 산호 테두리(사용자가 움직여야 하는 상태) */
.skx-history-badge {
  flex: none;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
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
