const { defineConfig } = require("@playwright/test");
module.exports = defineConfig({
  testDir: ".",
  testMatch: "**/*.e2e.spec.js",
  workers: 1,
  retries: 0,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    browserName: "chromium",
    headless: true,
    viewport: { width: 1280, height: 800 },
  },
  webServer: {
    command: "python3 -m http.server 8765 --bind 127.0.0.1 --directory web",
    url: "http://127.0.0.1:8765",
    reuseExistingServer: false,
    timeout: 15000,
  },
});
