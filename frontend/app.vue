<template>
  <div>
    <!-- 움직이는 홀로그램 배경(style_skovix.css 의 .skx-holo) — 화면 뒤에 고정, 장식이라 보조기기에서 숨긴다 -->
    <div class="skx-holo" aria-hidden="true">
      <span class="skx-holo__band skx-holo__band--1"></span>
      <span class="skx-holo__band skx-holo__band--2"></span>
      <span class="skx-holo__band skx-holo__band--3"></span>
      <span class="skx-holo__veil"></span>
    </div>
    <NuxtPage />
    <footer class="skx-footer">
      <p class="skx-footer__copy">
        Copyright &copy; {{ new Date().getFullYear() }} LANDSOFT Co., Ltd. All
        rights reserved.
        <span class="skx-footer__credit"
          >&middot; Crafted by
          <strong class="skx-footer__name">
            <span class="skx-footer__name-short">AJH</span>
            <span class="skx-footer__name-full">AN Jeonghyun</span>
          </strong>
        </span>
      </p>
    </footer>
  </div>
</template>

<script setup lang="ts">
// 기본 탭 제목 — 제목을 따로 두지 않는 화면(메인·결과)으로 돌아오면 이 값으로 돌아간다. 페이지의 useHead 가 떠나며 걷히면 남은 항목이
// 없어 직전 화면(연구·상세)의 제목이 그대로 남았다(2026-10-14 운영 확인 — 메인인데 탭이 'DeepResearch'). nuxt.config 의 app.head 는
// 서버 첫 그림에만 실려 화면을 옮길 때는 되살아나지 않으므로 늘 살아 있는 이 컴포넌트에 둔다
useHead({ title: "SKOVIX" });
</script>

<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

:root {
  --bg: #f6f6f4;
  --surface: #ffffff;
  --ink: #12131a;
  --ink-2: #3a3b46;
  --ink-3: #6a6b76;
  --ink-4: #9a9ba4;
  --line: #e7e7e2;
  --line-2: #f0efea;
  --radius: 14px;
  --radius-sm: 10px;
  --ai-hue: 277;
  /* ── 논문 검색 / 바이올렛 시스템 ── */
  --violet: #7c4dff;
  --violet-deep: #4a2ed6;
  --violet-soft: #b9a7ff;
  --lilac: #f1edff;
  --lilac-2: #f7f4ff;
  --rose: #ff5cad;
  --teal: #2dd4bf;
  --bg-soft: #fafafa;
  --bg-card: #ffffff;
  --muted: #6a6a72;
  --muted-2: #9a9aa3;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif;
  -webkit-font-smoothing: antialiased;
  color: var(--skx-ink);
  background: var(--skx-page-bg);
}

button {
  font-family: inherit;
}
</style>
