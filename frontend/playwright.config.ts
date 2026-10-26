import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', timeout: 60_000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:15173', browserName: 'chromium', trace: 'retain-on-failure' },
  webServer: [
    { command: 'poetry run python -m uvicorn backend.app:app --host 127.0.0.1 --port 18000', cwd: '..', url: 'http://127.0.0.1:18000/api/health', reuseExistingServer: false, timeout: 120_000 },
    { command: 'npm run dev -- --port 15173', env: { UTM_API_TARGET: 'http://127.0.0.1:18000' }, url: 'http://127.0.0.1:15173', reuseExistingServer: false },
  ],
});
