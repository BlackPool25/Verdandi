/**
 * T9 events.spec.ts — event feed + DOWN disambiguation + anomaly overlay.
 * Owns ONLY events assertions; never touches SimPage/tickSource/panels.
 * Spins its own bridge (:18009) + vite events harness (:19109) so the T4
 * scaffold config and T7 controls harness stay untouched. Page under test
 * is /events.html (T9-owned harness).
 */
import { spawn, type ChildProcess } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect, type Page } from "@playwright/test";

test.use({ video: "on" });
test.setTimeout(120_000);
test.describe.configure({ mode: "serial", retries: 1 });

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const FRONTEND = resolve(HERE, "..");
const BRIDGE = "http://127.0.0.1:18009";
const WEB = "http://localhost:19109";

let bridge: ChildProcess | null = null;
let web: ChildProcess | null = null;

async function waitFor(url: string, timeoutMs: number): Promise<void> {
  const t0 = Date.now();
  for (;;) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      /* not up yet */
    }
    if (Date.now() - t0 > timeoutMs) throw new Error(`timeout waiting for ${url}`);
    await new Promise((r) => setTimeout(r, 250));
  }
}

async function isUp(url: string): Promise<boolean> {
  try {
    const r = await fetch(url);
    return r.ok;
  } catch {
    return false;
  }
}

test.beforeAll(async () => {
  if (!(await isUp(`${BRIDGE}/health`))) {
    bridge = spawn("python3", ["-m", "uvicorn", "services.sim_bridge.app:app", "--host", "127.0.0.1", "--port", "18009"], {
      cwd: REPO,
      stdio: "ignore",
    });
  }
  await waitFor(`${BRIDGE}/health`, 30_000);
  if (!(await isUp(`${WEB}/events.html`))) {
    web = spawn(
      "node",
      [
        resolve(FRONTEND, "node_modules", "vite", "bin", "vite.js"),
        "--config",
        "vite.events.config.ts",
        "--port",
        "19109",
        "--strictPort",
      ],
      { cwd: FRONTEND, stdio: "ignore" },
    );
  }
  await waitFor(`${WEB}/`, 60_000);
});

test.afterAll(async () => {
  bridge?.kill();
  web?.kill();
});

async function startF21(page: Page): Promise<void> {
  await page.goto(`${WEB}/events.html`);
  await page.getByTestId("new-f21").click();
  await expect(page.getByTestId("episode-id")).not.toHaveText("none", { timeout: 60_000 });
  await expect(page.getByTestId("cursor")).toContainText("/ 300", { timeout: 60_000 });
}

async function scrub(page: Page, step: number): Promise<void> {
  await page.getByTestId("step-scrub").fill(String(step));
  await expect(page.getByTestId("cursor")).toContainText(`Step ${step} / 300`);
}

test("F-21 GT outline on B5 for t in [150,162), nowhere else", async ({ page }) => {
  await startF21(page);
  await scrub(page, 155);
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-gt", "true");
  await expect(page.getByTestId("gt-probe-B6")).toHaveAttribute("data-gt", "false");
  await expect(page.getByTestId("gt-probe-B7")).toHaveAttribute("data-gt", "false");
  await expect(page.getByTestId("gt-probe-B4")).toHaveAttribute("data-gt", "false");
  // Depth-1 only, live: B7 is two hops from B5 so never highlighted; B4/B6
  // highlight exactly when their live same-step state is BLOCKED/STARVED
  // (natural line rhythm, never promised as demo congestion per ruling A).
  await expect(page.getByTestId("gt-probe-B7")).toHaveAttribute("data-neighbor", "false");
  for (const id of ["B4", "B6"]) {
    const probe = page.getByTestId(`gt-probe-${id}`);
    const state = await probe.getAttribute("data-state");
    const congested = state === "BLOCKED" || state === "STARVED";
    await expect(probe).toHaveAttribute("data-neighbor", congested ? "true" : "false");
  }
  // Window edges: 149 off, 162 off.
  await scrub(page, 149);
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-gt", "false");
  await scrub(page, 162);
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-gt", "false");
  await scrub(page, 155);
});

test("real MachineNode shows outline + ! glyph at GT step", async ({ page }) => {
  await startF21(page);
  await scrub(page, 155);
  const node = page.getByTestId("node-B5");
  await expect(node).toHaveAttribute("data-gt", "true");
  await expect(node).toHaveClass(/gt-outline/);
  await expect(page.getByTestId("node-glyph-B5")).toHaveText("!");
  await expect(page.getByTestId("node-B6")).toHaveAttribute("data-gt", "false");
  await expect(page.getByTestId("node-B6")).not.toHaveClass(/gt-outline/);
});

test("global feed carries FAULT_START B5; per-machine feed filters", async ({ page }) => {
  await startF21(page);
  await scrub(page, 160);
  const feed = page.getByTestId("event-feed");
  await feed.getByTestId("feed-family-filter").selectOption("FAULT");
  await expect(
    feed.locator('[data-testid="event-row"][data-event="FAULT_START"][data-machine="B5"]'),
  ).toHaveCount(1);
  await scrub(page, 299);
  await expect(feed.locator('[data-testid="event-row"][data-event="FAULT_END"][data-machine="B5"]')).toHaveCount(1);
  await feed.getByTestId("feed-family-filter").selectOption("ALL");
  await page.getByTestId("machine-select").selectOption("B5");
  const mfeed = page.getByTestId("machine-event-feed");
  const rows = mfeed.locator('[data-testid="event-row"]');
  expect(await rows.count()).toBeGreaterThan(0);
  for (const m of await rows.evaluateAll((els) => els.map((e) => e.getAttribute("data-machine")))) {
    expect(m).toBe("B5");
  }
});

test("DOWN rows disambiguate injected vs natural with ! glyph, distinct style", async ({ page }) => {
  await startF21(page);
  await scrub(page, 299);
  const probe = page.getByLabel("down style probe");
  const inj = probe.locator('[data-testid="event-row"][data-down-kind="injected"]');
  const nat = probe.locator('[data-testid="event-row"][data-down-kind="natural"]');
  await expect(inj).toHaveCount(1);
  await expect(nat).toHaveCount(1);
  await expect(inj).toContainText("! FAULT");
  await expect(nat).toContainText("! NATURAL");
  const injBorder = await inj.evaluate((e) => getComputedStyle(e).borderLeftStyle);
  const natBorder = await nat.evaluate((e) => getComputedStyle(e).borderLeftStyle);
  expect(injBorder).not.toBe(natBorder);
});

test("breakdown: GT ends at t1 but injected DOWN outlives it", async ({ page }) => {
  await page.goto(`${WEB}/events.html`);
  await page.getByTestId("new-breakdown").click();
  await expect(page.getByTestId("cursor")).toContainText("/ 300", { timeout: 60_000 });
  await scrub(page, 155);
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-gt", "true");
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-down", "injected");
  await scrub(page, 165);
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-gt", "false");
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-down", "injected");
});

test("re-stream same episode reproduces the same outline (no stale state)", async ({ page }) => {
  await startF21(page);
  await scrub(page, 155);
  const before = await page.getByTestId("gt-probe-B5").textContent();
  await page.reload();
  await startF21(page);
  await scrub(page, 155);
  expect(await page.getByTestId("gt-probe-B5").textContent()).toBe(before);
  await expect(page.getByTestId("gt-probe-B5")).toHaveAttribute("data-gt", "true");
});

test("evidence screenshot at GT step", async ({ page }) => {
  await startF21(page);
  await scrub(page, 155);
  await expect(page.getByTestId("node-B5")).toHaveClass(/gt-outline/);
  await page.screenshot({ path: resolve(REPO, ".omo", "evidence", "task-9-verdandi-pixel-twin-frontend.png"), fullPage: true });
});

test("reduced-motion pins a static outline (no blink)", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  try {
    await page.goto(`${WEB}/events.html`);
    await page.getByTestId("new-f21").click();
    await expect(page.getByTestId("cursor")).toContainText("/ 300", { timeout: 60_000 });
    await page.getByTestId("step-scrub").fill("155");
    await expect(page.getByTestId("cursor")).toContainText("Step 155 / 300");
    const outline = page.getByTestId("node-B5");
    await expect(outline).toHaveClass(/gt-outline/);
    expect(await outline.evaluate((e) => getComputedStyle(e).animationName)).toBe("none");
    expect(await outline.evaluate((e) => getComputedStyle(e).outlineStyle)).not.toBe("none");
  } finally {
    await ctx.close();
  }
});
