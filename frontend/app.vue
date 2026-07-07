<template>
  <div>
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
  color: var(--ink);
  background: var(--bg);
}

button {
  font-family: inherit;
}
</style>
