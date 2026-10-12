import tailwindcss from "@tailwindcss/vite";
import tsconfigPaths from "vite-tsconfig-paths";
import { resolve } from "path";
import { themeInitScript } from "./utils/theme";

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },

  app: {
    head: {
      // 화면 테마(html[data-theme]) 를 첫 그림 전에 붙인다 — 저장된 테마로 처음부터 그려져 깜빡이지 않는다(utils/theme.ts)
      script: [{ innerHTML: themeInitScript(), tagPosition: "head", tagPriority: "critical" }],
    },
  },

  vite: {
    plugins: [tailwindcss(), tsconfigPaths()],
  },

  css: [
    resolve(__dirname, "assets/css/tailwind.css"),
    resolve(__dirname, "assets/css/style_skovix.css"),
    resolve(__dirname, "assets/css/detail.css"),
    resolve(__dirname, "assets/css/research.css"),
    resolve(__dirname, "assets/css/work.css"),
  ],

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE ?? "/api",
    },
  },

  nitro: {
    devProxy: {
      "/api": {
        // devProxy 는 "/api" 접두를 떼고 넘긴다 — 대상 주소에 /api 를 붙여야 FastAPI 경로와 맞는다.
        // 로컬 화면을 운영 게이트웨이에 붙일 때는 NUXT_DEV_API_TARGET=http://<서버>:92/api 로 띄운다.
        target: process.env.NUXT_DEV_API_TARGET ?? "http://localhost:18002/api",
        changeOrigin: true,
      },
    },
  },
});
