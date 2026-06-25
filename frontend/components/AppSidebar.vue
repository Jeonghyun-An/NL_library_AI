<template>
  <aside :class="['sk-sidebar', !open && 'collapsed']">
    <div class="sk-sidebar-top">
      <button class="sk-logo" @click="navigateTo('/')">
        <img src="/skovix-character.png" alt="SKOVIX" class="sk-logo-img" />
        <Transition name="sk-fade">
          <span v-if="open" class="sk-logo-text">SKOVIX</span>
        </Transition>
      </button>
      <button class="sk-sidebar-toggle" @click="open = !open">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline :points="open ? '15 18 9 12 15 6' : '9 18 15 12 9 6'" />
        </svg>
      </button>
    </div>

    <div v-if="open" class="sk-sidebar-body">
      <button class="sk-new-chat" @click="navigateTo('/')">
        <span class="sk-new-chat-icon">+</span>
        <span>새 채팅</span>
      </button>

      <nav class="sk-nav">
        <button class="sk-nav-item" @click="emit('cart')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
            <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
          </svg>
          대출 장바구니
        </button>
        <button class="sk-nav-item" @click="emit('save')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
          </svg>
          저장목록
        </button>
      </nav>

      <div class="sk-history-section">
        <p class="sk-history-label">검색기록</p>
        <div class="sk-history-list scrollbar-zinc">
          <p v-if="!history.length" class="sk-history-empty">검색 기록이 없습니다</p>
          <button v-for="h in history" :key="h.id" class="sk-history-item" @click="emit('select-history', h)">
            <span class="sk-history-query">{{ h.query }}</span>
            <span class="sk-history-time">{{ formatTime(h.timestamp) }}</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="open" class="sk-sidebar-footer">
      <div class="sk-user-row">
        <div class="sk-avatar">김</div>
        <span class="sk-user-name">김랜드</span>
      </div>
      <button class="sk-settings-btn">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
const emit = defineEmits<{
  cart: []
  save: []
  'select-history': [h: any]
}>()

const open = useState('sidebarOpen', () => true)

const config = useRuntimeConfig()
const apiBase = config.public.apiBase as string

const history = useState<any[]>('searchHistory', () => [])

onMounted(async () => {
  if (!process.client || history.value.length) return
  try {
    const sid = localStorage.getItem('sid')
    if (!sid) return
    const data = await $fetch<any[]>(`${apiBase}/books/history/${sid}`)
    if (Array.isArray(data)) history.value = data
  } catch { /* ignore */ }
})

function formatTime(ts: string | number): string {
  if (!ts) return ''
  const d = new Date(ts)
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '방금'
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`
  return d.toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' })
}
</script>

<style scoped>
.sk-sidebar {
  display: flex; flex-direction: column;
  width: 240px; min-width: 240px;
  background: var(--surface);
  border-right: 1px solid var(--line);
  transition: width 0.25s, min-width 0.25s;
  overflow: hidden; flex-shrink: 0;
}
.sk-sidebar.collapsed { width: 56px; min-width: 56px; }
.sk-sidebar-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 14px; border-bottom: 1px solid var(--line);
}
.sk-logo { display: flex; align-items: center; gap: 8px; background: none; border: none; cursor: pointer; padding: 0; }
.sk-logo-img { width: 28px; height: 28px; object-fit: contain; }
.sk-logo-text { font-size: 15px; font-weight: 700; color: var(--ink); white-space: nowrap; }
.sk-sidebar-toggle { background: none; border: none; cursor: pointer; color: #999; padding: 4px; border-radius: 6px; display: flex; align-items: center; }
.sk-sidebar-toggle:hover { background: var(--bg); color: var(--ink); }
.sk-sidebar-body { display: flex; flex-direction: column; flex: 1; padding: 12px; gap: 6px; overflow: hidden; }
.sk-new-chat {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 10px 14px; background: var(--bg); border: 1px solid var(--line);
  border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; font-weight: 500; color: var(--ink);
}
.sk-new-chat:hover { background: var(--lilac); }
.sk-new-chat-icon { font-size: 16px; font-weight: 300; color: var(--accent); }
.sk-nav { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.sk-nav-item {
  display: flex; align-items: center; gap: 8px; padding: 9px 12px;
  background: none; border: none; border-radius: var(--radius-sm);
  cursor: pointer; font-size: 13px; color: #555;
}
.sk-nav-item:hover { background: var(--bg); color: var(--ink); }
.sk-history-section { flex: 1; display: flex; flex-direction: column; overflow: hidden; margin-top: 8px; }
.sk-history-label { font-size: 11px; font-weight: 600; color: #999; letter-spacing: 0.06em; text-transform: uppercase; padding: 0 4px 6px; }
.sk-history-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.sk-history-empty { font-size: 12px; color: #bbb; padding: 8px 4px; margin: 0; }
.sk-history-item {
  display: flex; flex-direction: column; gap: 2px; padding: 8px 10px;
  border-radius: var(--radius-sm); background: none; border: none; cursor: pointer; text-align: left;
}
.sk-history-item:hover { background: var(--lilac); }
.sk-history-query { font-size: 12px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 190px; }
.sk-history-time { font-size: 10px; color: #aaa; }
.sk-sidebar-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; border-top: 1px solid var(--line);
}
.sk-user-row { display: flex; align-items: center; gap: 8px; }
.sk-avatar { width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
.sk-user-name { font-size: 13px; color: var(--ink); }
.sk-settings-btn { background: none; border: none; cursor: pointer; color: #999; padding: 4px; border-radius: 6px; display: flex; }
.sk-settings-btn:hover { color: var(--ink); }
.sk-fade-enter-active, .sk-fade-leave-active { transition: opacity 0.2s; }
.sk-fade-enter-from, .sk-fade-leave-to { opacity: 0; }
</style>
