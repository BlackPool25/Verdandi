/**
 * T11 demo tour: seed 777 + F-21 (drift@B5 t0=150 dur=12 mag 5.2) on /sim.
 * Autoplay 1x -> pause at t=160 -> step -> screenshot.
 * Run via demo/frontend.sh (owns servers, video dir, evidence paths).
 */
import { chromium, expect } from "../frontend/node_modules/@playwright/test/index.mjs";

const WEB = process.env.T11_WEB ?? "http://localhost:19106";
const PNG = process.env.T11_PNG ?? ".omo/evidence/task-11-verdandi-pixel-twin-frontend.png";
const VIDEO_DIR = process.env.T11_VIDEO_DIR ?? "/tmp/t11-video";

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  recordVideo: { dir: VIDEO_DIR, size: { width: 1280, height: 800 } },
});
const page = await context.newPage();

// Live-EventSource counter: unification asserts exactly 1 on /sim.
await page.addInitScript(() => {
  window.__esLive = 0;
  const O = window.EventSource;
  window.EventSource = function (url, init) {
    window.__esLive += 1;
    const s = new O(url, init);
    const origClose = s.close.bind(s);
    s.close = () => {
      window.__esLive -= 1;
      origClose();
    };
    return s;
  };
});
const liveSources = () => page.evaluate(() => window.__esLive);

// 1. Open /sim (auto-seeds ?seed=777 into the SHARED source) and wait for
// the full 300-row stream. episode-id stays "none" until a ControlsBar
// episode is posted (local meta); the shared stream is row-count/cursor.
await page.goto(`${WEB}/sim?seed=777`);
await expect(page.getByTestId("row-count")).toHaveText("300", { timeout: 60_000 });
await expect(page.getByTestId("cursor")).not.toHaveText("Step 0 / 300", { timeout: 60_000 });
console.log(`auto-seed streaming: ${await page.getByTestId("cursor").textContent()}`);
console.log(`live-eventsource-after-autoseed=${await liveSources()}`);
if ((await liveSources()) !== 1) throw new Error("expected exactly 1 live EventSource after auto-seed");

// 2. Inject F-21 through the fault form (drift@B5 t0=150 dur=12 mag 5.2).
await page.getByTestId("fault-class").selectOption("drift");
await page.getByTestId("fault-origin").selectOption("B5");
await page.getByTestId("fault-t0").fill("150");
await page.getByTestId("fault-dur").fill("12");
await page.getByTestId("fault-extra").fill('{"mag_sigma": 5.2}');
await page.getByTestId("fault-add").click();
await expect(page.getByTestId("fault-list")).toContainText("B5");
await page.getByTestId("new-episode").click();
await expect(page.getByTestId("episode-id")).not.toHaveText("none", { timeout: 60_000 });
await expect(page.getByTestId("episode-faults")).toContainText("B5", { timeout: 60_000 });
await expect(page.getByTestId("row-count")).toHaveText("300", { timeout: 60_000 });
console.log(`f21 episode=${await page.getByTestId("episode-id").textContent()}`);
console.log(`digest=${await page.getByTestId("episode-digest").textContent()}`);
console.log(`live-eventsource-after-new-episode=${await liveSources()}`);
if ((await liveSources()) !== 1) throw new Error("expected exactly 1 live EventSource after new episode (split-brain)");

// 3. Autoplay 1x, pause at t=160, single-step, screenshot.
await page.getByTestId("speed-select").selectOption("1");
if ((await page.getByTestId("play-pause").textContent()) !== "Pause") {
  await page.getByTestId("play-pause").click();
}
await page.waitForFunction(() => {
  const t = document.querySelector('[data-testid="cursor"]')?.textContent ?? "";
  const m = /Step (\d+)/.exec(t);
  return m !== null && Number(m[1]) >= 160;
}, undefined, { timeout: 120_000 });
await page.getByTestId("play-pause").click();
await expect(page.getByTestId("play-pause")).toHaveText("Play");
const stepNow = async () => {
  const t = (await page.getByTestId("cursor").textContent()) ?? "";
  return Number(/Step (\d+)/.exec(t)?.[1] ?? "-1");
};
// Settle back/forward to exactly t=160 (autoplay may overshoot while
// pausing). One awaited step at a time: fire-and-forget clicks reuse a
// stale render cursor and never converge.
let settled = await stepNow();
for (let i = 0; i < 60 && settled !== 160; i += 1) {
  const target = settled > 160 ? settled - 1 : settled + 1;
  await page.getByTestId(settled > 160 ? "step-back" : "step-fwd").click();
  await expect(page.getByTestId("cursor")).toHaveText(`Step ${target} / 300`, { timeout: 10_000 });
  settled = target;
}
await expect(page.getByTestId("cursor")).toHaveText("Step 160 / 300", { timeout: 30_000 });
const frozen = await page.getByTestId("cursor").textContent();
await page.waitForTimeout(900);
if ((await page.getByTestId("cursor").textContent()) !== frozen) throw new Error("cursor moved while paused");
await page.getByTestId("step-fwd").click();
await expect(page.getByTestId("cursor")).toHaveText("Step 161 / 300");
const tickJson = await page.getByTestId("tick-json").textContent();
if (tickJson === null || tickJson === "null") throw new Error("step 161 has no tick row");
await page.getByTestId("select-B5").click();
await expect(page.getByTestId("machine-panel-state")).not.toBeEmpty({ timeout: 30_000 });
console.log(`b5-state-at-161=${await page.getByTestId("machine-panel-state").textContent()}`);
await page.screenshot({ path: PNG, fullPage: true });
console.log(`screenshot=${PNG}`);

await context.close();
await browser.close();
console.log("TOUR-PASS");
