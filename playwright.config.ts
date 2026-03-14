import { defineConfig } from "@playwright/test";

const PORT = 3100;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${PORT}`;
const IS_CI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./web/tests/browser",
  testMatch: ["**/*.spec.ts"],
  fullyParallel: true,
  forbidOnly: IS_CI,
  retries: IS_CI ? 1 : 0,
  workers: IS_CI ? 1 : undefined,
  timeout: 90_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      scale: "css"
    }
  },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }]
  ],
  outputDir: "test-results",
  use: {
    baseURL: BASE_URL,
    colorScheme: "dark",
    locale: "en-GB",
    timezoneId: "Europe/London",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: {
      width: 1366,
      height: 900
    }
  },
  webServer: {
    command: `pnpm --filter @ukde/web exec next dev --webpack --port ${PORT}`,
    url: `${BASE_URL}/login`,
    reuseExistingServer: !IS_CI,
    timeout: 180_000,
    env: {
      APP_ENV: "test",
      NEXT_PUBLIC_APP_ENV: "test",
      UKDE_BROWSER_TEST_MODE: "1"
    }
  },
  projects: [
    {
      name: "chromium",
      use: {
        browserName: "chromium"
      }
    },
    {
      name: "firefox-phase1",
      grep: /@phase1/,
      grepInvert: /@perf|@visual/,
      use: {
        browserName: "firefox"
      }
    },
    {
      name: "webkit-phase1",
      grep: /@phase1/,
      grepInvert: /@perf|@visual/,
      use: {
        browserName: "webkit"
      }
    }
  ]
});
