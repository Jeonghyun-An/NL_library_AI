<!-- frontend/components/work/ReadingTable.vue -->
<template>
  <ol v-if="rows.length" class="wk-reading" aria-label="읽기 후보">
    <li
      v-for="(item, index) in rows"
      :key="item.cnts_id"
      class="wk-reading__row"
      :class="{
        'wk-reading__row--in': item.state === 'in',
        'wk-reading__row--out': item.state === 'out',
        'wk-reading__row--saving': saving.has(item.cnts_id),
        'wk-reading__row--fresh': fresh.has(item.cnts_id),
      }"
      :data-anchor="readingAnchor(item.cnts_id)"
      :aria-busy="saving.has(item.cnts_id)"
      @animationend.self="fresh.delete(item.cnts_id)"
    >
      <label class="wk-reading__check">
        <input
          type="checkbox"
          :checked="item.state === 'in'"
          :disabled="readOnly || busy || item.state === 'out'"
          @change="toggleIn(item, $event)"
        />
        <span>담음</span>
        <span class="rs-sr-only"> {{ rowName(item) }}</span>
      </label>

      <div class="wk-reading__main">
        <!-- 누르는 순간의 행 높이를 주소에 실어야 해서 NuxtLink 대신 직접 옮긴다(CitationChip 과 같다) -->
        <a
          :href="detailHref(item.cnts_id, null)"
          class="wk-reading__title"
          @click="goDetail($event, item.cnts_id)"
          @auxclick="goDetail($event, item.cnts_id)"
          @contextmenu="goDetail($event, item.cnts_id)"
        >{{ rowTitle(item) }}</a>
        <p class="wk-reading__meta">
          <span>{{ paperByline(item.meta) }}</span>
          <span class="rs-badge">{{ originLabel(item.origin) }}</span>
        </p>
        <div class="wk-reading__fields">
          <label class="wk-edit__field">
            <span class="wk-edit__label">메모<span class="rs-sr-only"> {{ rowName(item) }}</span></span>
            <textarea
              class="wk-edit__input"
              rows="2"
              :value="notes[item.cnts_id] ?? item.note ?? ''"
              :maxlength="READING_NOTE_MAX"
              :disabled="readOnly"
              @input="notes[item.cnts_id] = fieldText($event)"
              @blur="saveNote(item)"
            />
          </label>
          <label class="wk-edit__field">
            <span class="wk-edit__label">묶음 이름<span class="rs-sr-only"> {{ rowName(item) }}</span></span>
            <input
              class="wk-edit__input"
              type="text"
              :value="groups[item.cnts_id] ?? item.group_label ?? ''"
              :maxlength="GROUP_LABEL_MAX"
              :disabled="readOnly"
              @input="groups[item.cnts_id] = fieldText($event)"
              @blur="saveGroup(item)"
            />
          </label>
        </div>
      </div>

      <div class="wk-reading__actions">
        <button
          type="button"
          class="rs-btn rs-btn--small rs-btn--ghost"
          :disabled="readOnly || busy || reordering || index === 0"
          @click="move(item.cnts_id, -1)"
        >
          위로<span class="rs-sr-only"> {{ rowName(item) }}</span>
        </button>
        <button
          type="button"
          class="rs-btn rs-btn--small rs-btn--ghost"
          :disabled="readOnly || busy || reordering || index === rows.length - 1"
          @click="move(item.cnts_id, 1)"
        >
          아래로<span class="rs-sr-only"> {{ rowName(item) }}</span>
        </button>
        <button
          type="button"
          class="rs-btn rs-btn--small rs-btn--ghost"
          :aria-expanded="openPath === item.cnts_id"
          :aria-controls="openPath === item.cnts_id ? pathId(item.cnts_id) : undefined"
          @click="togglePath(item.cnts_id)"
        >
          경로<span class="rs-sr-only"> {{ rowName(item) }}</span>
        </button>
        <button
          type="button"
          class="rs-btn rs-btn--small rs-btn--ghost"
          :disabled="readOnly || busy"
          @click="toggleOut(item)"
        >
          {{ item.state === "out" ? "되돌리기" : "빼기" }}<span class="rs-sr-only"> {{ rowName(item) }}</span>
        </button>
      </div>

      <PathPopover
        v-if="openPath === item.cnts_id"
        :id="pathId(item.cnts_id)"
        :item="item"
        :job-id="jobId"
        @open-pdf="(payload) => emit('open-pdf', payload)"
      />
    </li>
  </ol>
  <p v-else class="rs-muted">후보 논문이 없습니다.</p>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import PathPopover from "~/components/work/PathPopover.vue";
import { useDetailLeave } from "~/composables/useRestorePosition";
import type { OpenPdfPayload } from "~/types/research";
import type { ReadingItem, ReadingPut } from "~/types/work";
import { detailUrl, readingAnchor } from "~/utils/detailSource";
import {
  GROUP_LABEL_MAX,
  READING_NOTE_MAX,
  fieldValue,
  freshIds,
  originLabel,
  reorderPuts,
  sortedItems,
  withPositions,
} from "~/utils/readingList";
import { paperByline } from "~/utils/researchReport";
import { isPlainClick, spotOf } from "~/utils/restorePosition";

// 읽기 목록 표(spec §4 S4·§5-4) — 행마다 담음/뺌·메모·묶음 이름·순서([위로]·[아래로])·[경로]. 고침은 update 로 emit 만 하고 PUT 은 ReadingStep 이 한다.
// reordering 은 ReadingStep 에 순서 저장이 남아 있는 동안(그 묶음을 다시 읽기까지) 참이다
const props = defineProps<{ items: ReadingItem[]; readOnly: boolean; busy: boolean; reordering: boolean; jobId: string }>();
const emit = defineEmits<{ update: [cnts: string, body: ReadingPut]; "open-pdf": [payload: OpenPdfPayload] }>();

const { leave } = useDetailLeave();
// [위로]·[아래로] 로 보낸 새 번호 — 순서 저장 묶음이 끝날 때까지(reordering) 표를 이 순서로 그려 옮긴 행이 바로 움직인다.
// 묶음이 끝나면 버리고 다시 읽은 서버 순서를 그린다(저장에 실패한 행은 그때 서버 자리로 돌아간다)
const moved = ref<{ cnts: string; position: number }[]>([]);
const rows = computed(() => sortedItems(withPositions(props.items, moved.value)));
const openPath = ref<string | null>(null);
// 서버에 보내고 다시 읽기를 기다리는 행. 체크 상자는 서버 값으로만 바뀐다 — 실패하면 그대로 남는다
const saving = ref(new Set<string>());
// 저장 전·저장에 실패한 메모·묶음 이름. 다른 행을 저장해 목록을 다시 그려도 쓰던 글을 덮지 않는다
const notes = ref<Record<string, string>>({});
const groups = ref<Record<string, string>>({});
// 되살리기·담기 응답 뒤 다시 읽은 목록에 처음 나온 행 — 잠깐 밝힌다(첫 그림은 강조하지 않는다)
const fresh = ref(new Set<string>());
let known: Set<string> | null = null;

watch(
  () => props.items,
  (items) => {
    const ids = items.map((i) => i.cnts_id);
    const added = freshIds(known, ids);
    known = new Set(ids);
    if (added.length) fresh.value = new Set(added);
    saving.value = new Set();
    const byId = new Map(items.map((i) => [i.cnts_id, i]));
    for (const [cnts, raw] of Object.entries(notes.value)) {
      const item = byId.get(cnts);
      if (!item || fieldValue(raw) === item.note) delete notes.value[cnts];
    }
    for (const [cnts, raw] of Object.entries(groups.value)) {
      const item = byId.get(cnts);
      if (!item || fieldValue(raw) === item.group_label) delete groups.value[cnts];
    }
  },
  { immediate: true },
);

watch(
  () => props.reordering,
  (on) => {
    if (!on) moved.value = [];
  },
);

function fieldText(e: Event): string {
  return (e.target as HTMLInputElement | HTMLTextAreaElement).value;
}

function send(cnts: string, body: ReadingPut): void {
  if (props.readOnly) return;
  saving.value.add(cnts);
  emit("update", cnts, body);
}

// 누른 칸은 곧바로 서버 값으로 되돌려 두고, 다시 읽은 목록이 새 값을 그린다(실패한 체크가 남지 않게)
function toggleIn(item: ReadingItem, e: Event): void {
  const box = e.target as HTMLInputElement;
  const want = box.checked ? "in" : "candidate";
  box.checked = item.state === "in";
  send(item.cnts_id, { state: want });
}

function toggleOut(item: ReadingItem): void {
  send(item.cnts_id, { state: item.state === "out" ? "candidate" : "out" });
}

// [위로]·[아래로] — 바뀐 순서를 행마다 position 으로 보낸다(서버 PUT 은 한 행씩). ReadingStep 이 차례로 보내고 묶음이 끝나면
// 한 번 다시 읽는다. 앞 옮김의 저장이 남은 동안에는 누르지 못한다 — 다음 옮김은 늘 저장이 끝난 순서로 계산한다
function move(cnts: string, dir: -1 | 1): void {
  if (props.readOnly || props.busy || props.reordering) return;
  const puts = reorderPuts(props.items, cnts, dir);
  if (!puts.length) return;
  moved.value = puts;
  for (const put of puts) send(put.cnts, { position: put.position });
}

function saveNote(item: ReadingItem): void {
  const raw = notes.value[item.cnts_id];
  if (raw === undefined) return;
  const next = fieldValue(raw);
  if (next === item.note) {
    delete notes.value[item.cnts_id];
    return;
  }
  send(item.cnts_id, { note: next });
}

function saveGroup(item: ReadingItem): void {
  const raw = groups.value[item.cnts_id];
  if (raw === undefined) return;
  const next = fieldValue(raw);
  if (next === item.group_label) {
    delete groups.value[item.cnts_id];
    return;
  }
  send(item.cnts_id, { group_label: next });
}

function rowTitle(item: ReadingItem): string {
  return item.meta.title?.trim() || item.cnts_id;
}

// 행마다 되풀이되는 컨트롤(담음·위로·아래로·경로·빼기·메모·묶음 이름)의 이름에 붙이는 대상 — 화면에는 보이지 않는다.
// 스크린리더의 컨트롤 목록·Tab 에서 수십 개의 '담음 체크박스'가 어느 논문인지 구별되게(OutlineEditor·ConceptChips 와 같은 관례)
function rowName(item: ReadingItem): string {
  return `「${rowTitle(item)}」`;
}

function pathId(cnts: string): string {
  return `wk-path-${cnts}`;
}

function togglePath(cnts: string): void {
  openPath.value = openPath.value === cnts ? null : cnts;
}

// 상세에서 [연구 화면으로]·뒤로 가기로 돌아오면 읽기 목록 단계(s=reading)의 이 행(r-<cnts>)으로 돌아온다
function detailHref(cnts: string, y: number | null): string {
  return detailUrl(cnts, { kind: "research", job: props.jobId, e: null, s: "reading" }, { at: readingAnchor(cnts), y });
}

// 누르는 순간의 행 높이를 싣는다. 새 창·새 탭 클릭과 오른쪽 클릭 메뉴는 브라우저에 맡기되 주소에는 같은 자리를 싣는다
function goDetail(e: MouseEvent, cnts: string): void {
  const link = e.currentTarget as HTMLAnchorElement;
  const spot = spotOf(link.closest("li") ?? link, readingAnchor(cnts));
  const url = detailHref(cnts, spot.y);
  if (e.type === "contextmenu" || !isPlainClick(e)) {
    link.href = url;
    return;
  }
  e.preventDefault();
  void leave(url, spot);
}
</script>
