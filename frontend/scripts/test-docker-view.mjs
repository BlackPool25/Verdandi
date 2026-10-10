import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SCREENSHOTS_DIR = resolve(HERE, "../docs-redesign/screenshots");
mkdirSync(SCREENSHOTS_DIR, { recursive: true });

async function main() {
  const browser = await chromium.launch();
  
  // 1. Viewport 1366x650
  const context1366 = await browser.newContext({ viewport: { width: 1366, height: 650 } });
  const page1366 = await context1366.newPage();

  console.log("Navigating to http://localhost:19104/live at 1366x650...");
  await page1366.goto("http://localhost:19104/live", { waitUntil: "networkidle" });
  await page1366.waitForSelector('[data-testid="sim-shell"]');
  await page1366.waitForTimeout(3000);

  // Capture top view
  await page1366.screenshot({
    path: resolve(SCREENSHOTS_DIR, "docker-live-1366x650-top.png"),
  });
  console.log("Captured docker-live-1366x650-top.png");

  // Scroll down to the dock boxes
  const dock = await page1366.waitForSelector('[data-testid="sim-dock"]');
  await dock.scrollIntoViewIfNeeded();
  await page1366.waitForTimeout(1000);

  // Capture dock view
  await page1366.screenshot({
    path: resolve(SCREENSHOTS_DIR, "docker-live-1366x650-dock.png"),
  });
  console.log("Captured docker-live-1366x650-dock.png");

  // 2. Viewport 1920x1080
  const context1920 = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page1920 = await context1920.newPage();

  console.log("Navigating to http://localhost:19104/live at 1920x1080...");
  await page1920.goto("http://localhost:19104/live", { waitUntil: "networkidle" });
  await page1920.waitForSelector('[data-testid="sim-shell"]');
  await page1920.waitForTimeout(3000);

  await page1920.screenshot({
    path: resolve(SCREENSHOTS_DIR, "docker-live-1920x1080-top.png"),
  });
  console.log("Captured docker-live-1920x1080-top.png");

  const dock1920 = await page1920.waitForSelector('[data-testid="sim-dock"]');
  await dock1920.scrollIntoViewIfNeeded();
  await page1920.waitForTimeout(1000);

  await page1920.screenshot({
    path: resolve(SCREENSHOTS_DIR, "docker-live-1920x1080-dock.png"),
  });
  console.log("Captured docker-live-1920x1080-dock.png");

  // 3. Anomaly Page at 1366x650 and 1920x1080
  console.log("Navigating to http://localhost:19104/anomalies at 1366x650...");
  await page1366.goto("http://localhost:19104/anomalies", { waitUntil: "networkidle" });
  await page1366.waitForSelector('[data-testid="anomaly-page"]');
  await page1366.waitForTimeout(3000);

  await page1366.screenshot({
    path: resolve(SCREENSHOTS_DIR, "docker-anomalies-1366x650.png"),
  });
  console.log("Captured docker-anomalies-1366x650.png");

  console.log("Navigating to http://localhost:19104/anomalies at 1920x1080...");
  await page1920.goto("http://localhost:19104/anomalies", { waitUntil: "networkidle" });
  await page1920.waitForSelector('[data-testid="anomaly-page"]');
  await page1920.waitForTimeout(3000);

  await page1920.screenshot({
    path: resolve(SCREENSHOTS_DIR, "docker-anomalies-1920x1080.png"),
  });
  console.log("Captured docker-anomalies-1920x1080.png");

  // Check metrics values on anomaly page
  const textContent = await page1920.textContent('[data-testid="anomaly-page"]');
  console.log("\nAnomaly Page Content Analysis:");
  console.log("Contains 'INJECTED ANOMALIES':", textContent.includes("INJECTED ANOMALIES"));
  console.log("Contains 'NATURAL BREAKDOWNS':", textContent.includes("NATURAL BREAKDOWNS"));
  console.log("Contains 'MATERIAL STARVATION':", textContent.includes("MATERIAL STARVATION"));
  console.log("Contains 'No Cascading Mechanical Breakdowns':", textContent.includes("No Cascading Mechanical Breakdowns"));

  await browser.close();
  console.log("\nDone verifying Docker frontend!");
}

main().catch((err) => {
  console.error("Error in test script:", err);
  process.exit(1);
});
