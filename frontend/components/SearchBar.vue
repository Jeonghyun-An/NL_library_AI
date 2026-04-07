<template>
  <div class="flex gap-2">
    <input
      v-model="model"
      type="text"
      placeholder="예: 한강의 채식주의자와 비슷한 책"
      class="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      @keydown.enter="$emit('search')"
    />
    <button
      class="px-6 py-3 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
      :disabled="loading"
      @click="$emit('search')"
    >
      {{ loading ? "검색 중..." : "검색" }}
    </button>
  </div>
</template>

<script setup lang="ts">
const model = defineModel<string>({ required: true });
defineProps<{ loading: boolean }>();
defineEmits<{ search: [] }>();
</script>
