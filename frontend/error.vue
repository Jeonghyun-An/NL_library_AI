<!-- frontend/error.vue -->
<!-- Nuxt 전역 오류 화면 — 없는 주소(404)와 화면을 그리다 난 치명 오류. 이 파일이 없으면 Nuxt 기본 영문 화면('Page not found')이 뜬다.
     app.vue 대신 이것이 통째로 그려지므로 홀로그램 배경을 여기 다시 둔다(사이드바가 없어 그 폭을 가리는 veil 은 두지 않는다).
     테마: html[data-theme] 은 nuxt.config 의 app.head 인라인 스크립트(utils/theme.ts themeInitScript)가 붙이고, 서버 렌더러가 오류 화면에도
     같은 head 를 싣는다 — 화면 이동 중 난 오류면 이미 붙은 속성이 그대로 남는다. 오류 객체의 영문 message·stack 은 보이지 않는다 -->
<template>
  <div class="skx-error-page">
    <div class="skx-holo" aria-hidden="true">
      <span class="skx-holo__band skx-holo__band--1"></span>
      <span class="skx-holo__band skx-holo__band--2"></span>
      <span class="skx-holo__band skx-holo__band--3"></span>
    </div>
    <main class="skx-error-page__main">
      <SkovixWordmark class="skx-error-page__logo" decorative />
      <SkxErrorState
        v-if="notFound"
        kind="notFound"
        title-tag="h1"
        title="페이지를 찾을 수 없습니다"
        message="주소가 바뀌었거나 없는 페이지입니다."
      >
        <button type="button" class="skx-state__action" @click="goHome">처음 화면으로</button>
      </SkxErrorState>
      <SkxErrorState
        v-else
        kind="error"
        title-tag="h1"
        title="문제가 생겼습니다"
        message="잠시 뒤 다시 시도하세요."
        @retry="reload"
      >
        <button type="button" class="skx-state__action" @click="goHome">처음 화면으로</button>
      </SkxErrorState>
    </main>
  </div>
</template>

<script setup lang="ts">
import type { NuxtError } from "#app";

const props = defineProps<{ error: NuxtError }>();

// Nuxt 4 는 status 를, 서버 렌더에서 넘어온 오류 객체는 statusCode 만 들고 올 수 있어 둘 다 본다
const notFound = computed(() => (props.error?.status ?? props.error?.statusCode) === 404);

// app.vue 가 그려지지 않아 그쪽 기본 탭 제목이 없다 — 여기서 같은 값을 둔다
useHead({ title: "SKOVIX" });

/** 오류를 걷고 처음 화면으로 */
function goHome(): void {
  clearError({ redirect: "/" });
}

/** 지금 주소를 새로 불러온다 — 화면 상태가 꼬여 난 오류일 수 있어 앱을 처음부터 다시 띄운다 */
function reload(): void {
  window.location.reload();
}
</script>
