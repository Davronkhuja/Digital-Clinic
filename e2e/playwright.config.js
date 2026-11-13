import { defineConfig } from '@playwright/test'

// Smoke e2e: ishlayotgan stek (CI: docker compose, alohida `clinic_e2e` bazasi; lokal: E2E_BASE_URL).
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,                       // testlar bir-biriga bog'liq (bemor -> qabul -> hisob -> portal)
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5180',
    locale: 'uz-UZ',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
})
