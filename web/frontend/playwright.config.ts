import { defineConfig, devices } from "@playwright/test";

/**
 * Two suites, deliberately separated.
 *
 * `wizard` is hermetic: every /api call is intercepted, so it runs anywhere
 * (including CI) and catches regressions in the deploy wizard's UI and its SSE
 * handling without touching Notion.
 *
 * `wizard-live` drives the real FastAPI app and really deploys into Notion. It
 * needs E2E_LIVE_BASE_URL plus a minted session (see e2e/README.md) and skips
 * itself otherwise — it is never part of a default run.
 */
const PORT = Number(process.env.E2E_PORT ?? 4173);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  expect: { timeout: 7_000 },

  use: {
    baseURL: process.env.E2E_LIVE_BASE_URL ?? `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  // Only stand up the static preview when we are not pointed at a live server.
  webServer: process.env.E2E_LIVE_BASE_URL
    ? undefined
    : {
        command: `npx vite preview --port ${PORT} --strictPort`,
        port: PORT,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
});
