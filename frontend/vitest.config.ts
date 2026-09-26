import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Nuxt 를 띄우지 않고 순수 로직만 돌린다 — 앱 코드의 "~/..." 경로만 맞춰 준다
const root = fileURLToPath(new URL("./", import.meta.url)).replace(/\\/g, "/");

export default defineConfig({
  resolve: {
    alias: [{ find: /^~\//, replacement: root }],
  },
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.ts"],
  },
});
