<template>
  <NuxtPage />
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
