<!-- frontend/error.vue -->
<!-- Nuxt 전역 오류 화면 — 없는 주소(404)와 화면을 그리다 난 치명 오류. 이 파일이 없으면 Nuxt 기본 영문 화면('Page not found')이 뜬다.
     본문은 components/SkxErrorPage.vue 하나다 — 오류 화면 모음(/dev/error-states)이 같은 컴포넌트를 액자에 담아 디자인을 함께 본다.
     테마: html[data-theme] 은 nuxt.config 의 app.head 인라인 스크립트(utils/theme.ts themeInitScript)가 붙이고, 서버 렌더러가 오류 화면에도
     같은 head 를 싣는다 — 화면 이동 중 난 오류면 이미 붙은 속성이 그대로 남는다. 오류 객체의 영문 message·stack 은 넘기지 않는다(상태 코드만) -->
<template>
  <SkxErrorPage :status="status" />
</template>

<script setup lang="ts">
import type { NuxtError } from "#app";

const props = defineProps<{ error: NuxtError }>();

// Nuxt 4 는 status 를, 서버 렌더에서 넘어온 오류 객체는 statusCode 만 들고 올 수 있어 둘 다 본다. 둘 다 없으면 치명 오류(500)로 본다
const status = computed(() => props.error?.status ?? props.error?.statusCode ?? 500);

// app.vue 가 그려지지 않아 그쪽 기본 탭 제목이 없다 — 여기서 같은 값을 둔다. 모음의 액자(preview)가 탭 제목을 덮지 않게 SkxErrorPage 가 아니라 여기에
useHead({ title: "SKOVIX" });
</script>
