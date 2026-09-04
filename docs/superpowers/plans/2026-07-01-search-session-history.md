# Search Session History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save book and paper search sessions (query + results + AI summary) to localStorage, display them in AppSidebar with separate tabs, and restore any session instantly without re-fetching.

**Architecture:** A module-level reactive composable (`useSearchHistory`) acts as the single source of truth, persisting to `localStorage` key `skx_search_history`. Both `pages/index.vue` (books) and `pages/papers/index.vue` (papers) call `addEntry` on search and `updateAiSummary` when streaming completes. `AppSidebar` gains a 도서/논문 tab that filters by `entry.type`. Cross-page restore navigates with `?restore=<id>`; the destination page reads the entry from localStorage on mount and renders immediately.

**Tech Stack:** Vue 3 Composition API, Nuxt 3, TypeScript, localStorage

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/types/history.ts` | Modify | Add `type`, `aiSummary` fields |
| `frontend/composables/useSearchHistory.ts` | Rewrite | localStorage persistence, addEntry, updateAiSummary, clearByType, getById |
| `frontend/components/AppSidebar.vue` | Modify | 도서/논문 tabs, accept bookHistory/paperHistory props |
| `frontend/assets/css/style_skovix.css` | Modify | Tab styles inside sidebar history section |
| `frontend/pages/papers/index.vue` | Modify | addEntry on search, updateAiSummary after stream, restore from ?restore= |
| `frontend/pages/index.vue` | Modify | addEntry on search, updateAiSummary after curation, restore from ?restore=, update sidebar props |

---

### Task 1: Extend HistoryEntry type

**Files:**
- Modify: `frontend/types/history.ts`

- [ ] **Step 1: Replace file contents**

```typescript
// frontend/types/history.ts
export interface HistoryEntry {
  id: string;
  type: "book" | "paper";
  query: string;
  timestamp: number | string;
  result?: any;       // full search response (books array)
  aiSummary?: string; // AI 요약/큐레이션 텍스트 (스트리밍 완료 후 저장)
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/types/history.ts
git commit -m "feat: add type and aiSummary fields to HistoryEntry"
```

---

### Task 2: Rewrite useSearchHistory composable

**Files:**
- Modify: `frontend/composables/useSearchHistory.ts`

- [ ] **Step 1: Rewrite the composable**

```typescript
// frontend/composables/useSearchHistory.ts
import type { HistoryEntry } from "~/types/history";

const STORAGE_KEY = "skx_search_history";
const MAX_ENTRIES = 30;

// Module-level state — shared across all composable calls (singleton)
const _history = ref<HistoryEntry[]>([]);
let _loaded = false;

export function useSearchHistory() {
  // Lazy-load from localStorage once per app lifetime
  if (process.client && !_loaded) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) _history.value = JSON.parse(raw);
    } catch {
      /* corrupted storage — start fresh */
    }
    _loaded = true;
  }

  function _persist() {
    if (!process.client) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(_history.value));
    } catch {
      /* quota exceeded — ignore */
    }
  }

  /** Add a new entry to the front of the list. Returns the generated id. */
  function addEntry(
    entry: Omit<HistoryEntry, "id" | "timestamp">,
  ): string {
    const id = Date.now().toString();
    _history.value.unshift({ id, timestamp: new Date().toISOString(), ...entry });
    if (_history.value.length > MAX_ENTRIES) {
      _history.value = _history.value.slice(0, MAX_ENTRIES);
    }
    _persist();
    return id;
  }

  /** Patch the aiSummary field of an existing entry after streaming completes. */
  function updateAiSummary(id: string, summary: string) {
    const entry = _history.value.find((h) => h.id === id);
    if (entry) {
      entry.aiSummary = summary;
      _persist();
    }
  }

  /** Remove all entries of a given type. */
  function clearByType(type: "book" | "paper") {
    _history.value = _history.value.filter((h) => h.type !== type);
    _persist();
  }

  /** Lookup a single entry by id (used on restore navigation). */
  function getById(id: string): HistoryEntry | undefined {
    return _history.value.find((h) => h.id === id);
  }

  const bookHistory = computed(() =>
    _history.value.filter((h) => h.type === "book"),
  );
  const paperHistory = computed(() =>
    _history.value.filter((h) => h.type === "paper"),
  );

  return {
    history: _history,
    bookHistory,
    paperHistory,
    addEntry,
    updateAiSummary,
    clearByType,
    getById,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/composables/useSearchHistory.ts
git commit -m "feat: rewrite useSearchHistory with localStorage persistence and type support"
```

---

### Task 3: Update AppSidebar with 도서/논문 tabs

**Files:**
- Modify: `frontend/components/AppSidebar.vue`
- Modify: `frontend/assets/css/style_skovix.css`

- [ ] **Step 1: Replace the `<script setup>` block**

```typescript
// inside <script setup lang="ts">
import type { HistoryEntry } from "~/types/history";

const open = ref(true);
const historyTab = ref<"book" | "paper">("book");

const props = defineProps<{
  bookHistory?: HistoryEntry[];
  paperHistory?: HistoryEntry[];
  activeId?: string;
}>();

const emit = defineEmits<{
  cart: [];
  save: [];
  restore: [h: HistoryEntry];
}>();

const activeHistory = computed(() =>
  historyTab.value === "book"
    ? (props.bookHistory ?? [])
    : (props.paperHistory ?? []),
);

function formatTime(ts: string | number): string {
  if (!ts) return "";
  const d = new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}
```

- [ ] **Step 2: Replace the `검색기록` section in the template**

Find this block in the template:
```html
<!-- 검색기록 -->
<div class="skx-history">
  <p class="skx-history__title">검색기록</p>
  <ul class="skx-history__list">
    <li v-for="h in history" :key="h.id">
      <button
        type="button"
        :class="['skx-history-item', h.id === activeId && 'is-active']"
        @click="emit('restore', h)"
      >
        <span class="skx-history-item__query">{{ h.query }}</span>
        <span class="skx-history-item__time">{{
          formatTime(h.timestamp)
        }}</span>
      </button>
    </li>
  </ul>
</div>
```

Replace with:
```html
<!-- 검색기록 -->
<div class="skx-history">
  <p class="skx-history__title">검색기록</p>
  <div class="skx-history__tabs">
    <button
      :class="['skx-history__tab', historyTab === 'book' && 'is-active']"
      type="button"
      @click="historyTab = 'book'"
    >도서</button>
    <button
      :class="['skx-history__tab', historyTab === 'paper' && 'is-active']"
      type="button"
      @click="historyTab = 'paper'"
    >논문</button>
  </div>
  <ul class="skx-history__list">
    <li v-for="h in activeHistory" :key="h.id">
      <button
        type="button"
        :class="['skx-history-item', h.id === activeId && 'is-active']"
        @click="emit('restore', h)"
      >
        <span class="skx-history-item__query">{{ h.query }}</span>
        <span class="skx-history-item__time">{{ formatTime(h.timestamp) }}</span>
      </button>
    </li>
  </ul>
</div>
```

- [ ] **Step 3: Add tab CSS to `style_skovix.css`** (append near the `.skx-history` block)

```css
.skx-history__tabs {
  display: flex;
  gap: 4px;
  padding: 4px 0 8px;
}
.skx-history__tab {
  flex: 1;
  padding: 5px 0;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-3);
  background: transparent;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.skx-history__tab:hover {
  background: var(--line-2);
  color: var(--ink-2);
}
.skx-history__tab.is-active {
  background: var(--violet);
  color: #fff;
}
```

Find the CSS block for `.skx-history` and insert above or after it. It starts at a recognisable comment in the file — add after the last `.skx-history-item` rule block.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/AppSidebar.vue frontend/assets/css/style_skovix.css
git commit -m "feat: add 도서/논문 tabs to AppSidebar history section"
```

---

### Task 4: Wire papers/index.vue session saving and restore

**Files:**
- Modify: `frontend/pages/papers/index.vue`

- [ ] **Step 1: Add composable import and currentHistoryId ref**

Find the `<script setup lang="ts">` block. Near the top (after existing imports/refs), add:

```typescript
const { bookHistory, paperHistory, addEntry, updateAiSummary, getById } =
  useSearchHistory();
const currentHistoryId = ref<string | null>(null);
```

- [ ] **Step 2: Save entry on successful search**

In `handleSearch`, find where `paperResult.value = data;` is set and add entry saving immediately after:

```typescript
paperResult.value = data;
// 세션 저장
currentHistoryId.value = addEntry({
  type: "paper",
  query,
  result: data,
});
```

- [ ] **Step 3: Save AI summary after streaming completes**

In `streamAiSummary`, find the `finally` block and add the `updateAiSummary` call:

```typescript
} finally {
  aiLoading.value = false;
  // 스트리밍 완료 후 AI 요약 저장
  if (currentHistoryId.value && aiText.value) {
    updateAiSummary(currentHistoryId.value, aiText.value);
  }
}
```

- [ ] **Step 4: Add restoreSession function**

Add this function near `handleSearch`:

```typescript
function restoreSession(entry: HistoryEntry) {
  if (entry.type === "book") {
    // 도서 세션은 books 페이지로 이동
    navigateTo(`/?restore=${entry.id}`);
    return;
  }
  // 논문 세션 복원 — API 재호출 없이 직접 세팅
  currentQuery.value = entry.query;
  currentHistoryId.value = entry.id;
  paperResult.value = entry.result ?? null;
  aiText.value = entry.aiSummary ?? "";
  aiRefs.value = [];
  currentPage.value = 1;
  sortBy.value = "relevance";
  aiExpanded.value = true;
}
```

- [ ] **Step 5: Handle `?restore=` on mount**

In `onMounted`, replace the current logic with:

```typescript
onMounted(() => {
  document.addEventListener("click", () => {
    perpageOpen.value = false;
  });
  const route = useRoute();
  const restoreId = route.query.restore as string | undefined;
  if (restoreId) {
    const entry = getById(restoreId);
    if (entry) {
      restoreSession(entry);
      return;
    }
  }
  const q = route.query.q as string | undefined;
  if (q?.trim()) handleSearch(q.trim());
});
```

- [ ] **Step 6: Update AppSidebar props and restore handler in the template**

Find the `<AppSidebar` tag and replace its props/events:

```html
<AppSidebar
  :book-history="bookHistory"
  :paper-history="paperHistory"
  :active-id="currentHistoryId"
  @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
  @save="showToast('저장목록 기능은 준비 중입니다.')"
  @restore="restoreSession"
/>
```

- [ ] **Step 7: Commit**

```bash
git add frontend/pages/papers/index.vue
git commit -m "feat: add session saving and restore to papers search page"
```

---

### Task 5: Wire pages/index.vue session saving and restore

**Files:**
- Modify: `frontend/pages/index.vue`

- [ ] **Step 1: Add composable and currentHistoryId**

Near the top of `<script setup lang="ts">`, find the `// ── 검색 기록` section. Replace:

```typescript
// ── 검색 기록 ─────────────────────────────────────────────
const history = ref<any[]>([]);
```

With:

```typescript
// ── 검색 기록 ─────────────────────────────────────────────
const { bookHistory, paperHistory, addEntry, updateAiSummary, getById } =
  useSearchHistory();
const currentHistoryId = ref<string | null>(null);
```

- [ ] **Step 2: Save entry on successful book search**

In `handleSearch`, find where `history.value.unshift(...)` is called:

```typescript
history.value.unshift({
  id: Date.now().toString(),
  query,
  timestamp: new Date().toISOString(),
});
```

Replace with:

```typescript
currentHistoryId.value = addEntry({
  type: "book",
  query,
  result: data,
});
```

- [ ] **Step 3: Save AI summary after curation completes**

In `fetchCuration`, find the `typeIntro` function and its completion branch (the `else` inside `typeIntro`):

```typescript
const typeIntro = () => {
  if (i < intro.length) {
    curationIntro.value += intro[i++];
    setTimeout(typeIntro, 18);
  } else {
    // intro 완료 후 items를 순서대로 추가
    for (const ci of items) {
      curationItems.value.push({ book_id: ci.book_id, reason: ci.reason });
    }
  }
};
```

Replace the `else` branch with:

```typescript
  } else {
    for (const ci of items) {
      curationItems.value.push({ book_id: ci.book_id, reason: ci.reason });
    }
    // 큐레이션 완료 후 AI 요약 저장
    if (currentHistoryId.value && curationIntro.value) {
      updateAiSummary(currentHistoryId.value, curationIntro.value);
    }
  }
```

- [ ] **Step 4: Add restoreSession function**

Find the existing `restoreHistory` function:

```typescript
function restoreHistory(h: any) {
  currentQuery.value = h.query;
  currentHistoryId.value = h.id;
  handleSearch(h.query);
}
```

Replace it with:

```typescript
function restoreSession(entry: HistoryEntry) {
  if (entry.type === "paper") {
    // 논문 세션은 papers 페이지로 이동
    navigateTo(`/papers?restore=${entry.id}`);
    return;
  }
  // 도서 세션 복원 — API 재호출 없이 직접 세팅
  currentQuery.value = entry.query;
  currentHistoryId.value = entry.id;
  view.value = "results";
  books.value = entry.result?.books ?? [];
  curationIntro.value = entry.aiSummary ?? "";
  curationItems.value = [];
  curationOpen.value = true;
  bookListExpanded.value = false;
  aiExpanded.value = false;
}
```

Add the `HistoryEntry` import at the top of the script if not already present:
```typescript
import type { HistoryEntry } from "~/types/history";
```

- [ ] **Step 5: Handle `?restore=` on mount and remove backend history fetch**

In `onMounted`, find:

```typescript
try {
  const sid = getSessionId();
  const data = await $fetch<any[]>(`${apiBase}/books/history/${sid}`);
  if (Array.isArray(data)) history.value = data;
} catch {
  /* 기록 없음 */
}
```

Replace with:

```typescript
const restoreId = (useRoute().query.restore as string) ?? null;
if (restoreId) {
  const entry = getById(restoreId);
  if (entry) restoreSession(entry);
}
```

- [ ] **Step 6: Update AppSidebar in the template**

Find:

```html
<AppSidebar
  :history="history"
  ...
  @restore="restoreHistory"
```

Replace with:

```html
<AppSidebar
  :book-history="bookHistory"
  :paper-history="paperHistory"
  :active-id="currentHistoryId ?? undefined"
  ...
  @restore="restoreSession"
```

- [ ] **Step 7: Commit**

```bash
git add frontend/pages/index.vue
git commit -m "feat: add session saving and restore to book search page"
```

---

## Self-Review

**Spec coverage:**
- ✅ 도서 검색 세션 저장 (Task 5)
- ✅ 논문 검색 세션 저장 (Task 4)
- ✅ type 필드로 분류 (Task 1)
- ✅ AI 요약 저장 + 복원 시 즉시 표시 (Tasks 4, 5)
- ✅ 검색 결과 목록 저장 (Tasks 4, 5 — `result` field)
- ✅ 사이드바 탭 분리 (Task 3)
- ✅ 도서 기록 클릭 → 도서 페이지 복원 (Task 5)
- ✅ 논문 기록 클릭 → 논문 페이지 복원 (Task 4)
- ✅ 크로스 페이지 복원: `?restore=<id>` 파라미터 (Tasks 4, 5)

**Placeholder scan:** 없음 — 모든 스텝에 실제 코드 포함.

**Type consistency:**
- `HistoryEntry` (Task 1) → `useSearchHistory` 반환값 (Task 2) → `AppSidebar` props (Task 3) → 각 페이지 (Tasks 4, 5) — 일관됨
- `addEntry` 반환 `string` (id) → `currentHistoryId.value` 에 할당 → `updateAiSummary(currentHistoryId.value, ...)` — 일관됨
- `restoreSession(entry: HistoryEntry)` — Tasks 4, 5 모두 동일 시그니처, AppSidebar `emit('restore', h: HistoryEntry)` 와 일치
