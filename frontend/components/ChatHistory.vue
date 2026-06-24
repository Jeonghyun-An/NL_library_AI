<template>
  <div class="chat-history">
    <div class="ch-header">
      <button
        v-if="history.length"
        class="ch-clear"
        @click="$emit('clear')"
        title="기록 삭제"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6l-1 14H6L5 6" />
          <path d="M10 11v6M14 11v6" />
          <path d="M9 6V4h6v2" />
        </svg>
      </button>
    </div>

    <div v-if="!history.length" class="ch-empty">
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
      <p>검색 기록이 없습니다</p>
    </div>

    <ul v-else class="ch-list scrollbar-zinc">
      <li
        v-for="entry in history"
        :key="entry.id"
        class="ch-item"
        :class="{ active: entry.id === currentId }"
        @click="$emit('select', entry)"
      >
        <span class="ch-query">{{ entry.query }}</span>
        <span class="ch-time">{{ formatTime(entry.timestamp) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { HistoryEntry } from "~/types/history";

defineProps<{
  history: HistoryEntry[];
  currentId: string | null;
}>();

defineEmits<{
  select: [entry: HistoryEntry];
  clear: [];
}>();

function formatTime(ts: number | string): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (diffMin < 1) return "방금";
  if (diffMin < 60) return `${diffMin}분 전`;
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}
</script>

<style scoped>
.chat-history {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 8px 0;
}

.ch-header {
  display: flex;
  justify-content: flex-end;
  padding: 4px 8px;
}

.ch-clear {
  display: flex;
  align-items: center;
  padding: 4px;
  border: none;
  background: transparent;
  color: #a1a1aa;
  cursor: pointer;
  border-radius: 4px;
  transition:
    color 0.15s,
    background 0.15s;
}

.ch-clear:hover {
  color: #ef4444;
  background: #fef2f2;
}

.ch-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: #d4d4d8;
}

.ch-empty p {
  font-size: 13px;
  color: #a1a1aa;
  text-align: center;
}

.ch-list {
  list-style: none;
  margin: 0;
  padding: 8px 0;
  overflow-y: auto;
  flex: 1;
}

.ch-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 16px;
  cursor: pointer;
  border-radius: 8px;
  margin: 2px 8px;
  transition: background 0.15s;
}

.ch-item:hover {
  background: #fafafa;
}

.ch-item.active {
  background: #fafafa;
  border: #e7e7e2 0.6px solid;
}

.ch-item.active .ch-query {
  color: #18181b;
  font-weight: 600;
}

.ch-query {
  font-size: 13px;
  color: #3f3f46;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ch-time {
  font-size: 11px;
  color: #a1a1aa;
}
</style>
