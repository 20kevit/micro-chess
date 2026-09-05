import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Minimal unit-test setup for exercise UI logic (mode navigation,
// selection, submit, prefetch transitions, timer, report rendering).
// Backend authority is covered by pytest; these tests mock the api client.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
