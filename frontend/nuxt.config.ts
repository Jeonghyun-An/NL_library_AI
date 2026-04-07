import tailwindcss from "@tailwindcss/vite";
import tsconfigPaths from "vite-tsconfig-paths";
import { resolve } from "path";

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },

  vite: {
    plugins: [tailwindcss(), tsconfigPaths()],
  },

  css: [resolve(__dirname, "assets/css/tailwind.css")],

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE ?? "/api",
    },
  },

  nitro: {
    devProxy: {
      "/api": {
        target: "http://localhost:18002",
        changeOrigin: true,
      },
    },
  },
});
