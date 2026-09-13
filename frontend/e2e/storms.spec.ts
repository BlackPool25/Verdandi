/**
 * T13 storms.spec.ts — adversarial pass: fault storms, rework surge, AGV contention.
 * Owns ONLY storm assertions; never touches scaffold/topology/store/feed sources.
 * Spins its own bridge (:18010) + vite main config (:19106); pages under test
 * are /sim?episode=<storm-id> (T13 deep-link, SimPage-owned).
 */
import { spawn, type ChildProcess } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

test.describe.configure({ mode: "serial", retries: 1 });
test.setTimeout(180_000);

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const FRONTEND = resolve(HERE, "..");
const BRIDGE = "http://127.0.0.1:8000";
const WEB = "http://localhost:19106";
const EVIDENCE = resolve(REPO, ".omo", "evidence");

interface WireFault {
  readonly id: string;
  readonly class: string;
  readonly origin: string;
  readonly t0: number;
  readonly dur: number;
  readonly extra?: Record<string, number>;
}

// Pinned by /tmp/t13-pin*.py hunts (bridge-strict ranges hold for all):
// A: 603 events, B: 574 events + REJECT flags, C: 587 events + 6 DIVERT_SBUF.
const STORMS = {
  A: {
    seed: 4242,
    faults: [
      { id: "S-A1", class: "breakdown", origin: "B5", t0: 150, dur: 12, extra: { mttr_mult: 2 } },
      { id: "S-A2", class: "delay", origin: "C3", t0: 170, dur: 10, extra: { d: 5 } },
      { id: "S-A3", class: "drift", origin: "A2", t0: 200, dur: 10, extra: { mag_sigma: 5.5 } },
    ] as WireFault[],
  },
  B: {
    seed: 59,
    faults: [
      { id: "S-B1", class: "quality", origin: "ASM2", t0: 140, dur: 25, extra: { reject_rate: 0.35 } },
    ] as WireFault[],
  },
  C: {
    seed: 95,
    faults: [
      { id: "S-C1", class: "delay", origin: "B4", t0: 140, dur: 15, extra: { d: 6 } },
      { id: "S-C2", class: "delay", origin: "B5", t0: 150, dur: 15, extra: { d: 6 } },
      { id: "S-C3", class: "delay", origin: "B6", t0: 160, dur: 15, extra: { d: 6 } },
    ] as WireFault[],
  },
} as const;

// Pinned: storm C seed 95 first BLOCKED tick (digest-stable, natural ON).
const BLOCKED_STEP = 271;
const BLOCKED_MACHINE = "C4";

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
    bridge = spawn(
      "python3",
      ["-m", "uvicorn", "services.sim_bridge.app:app", "--host", "127.0.0.1", "--port", "8000"],
      { cwd: REPO, stdio: "ignore" },
    );
  }
  await waitFor(`${BRIDGE}/health`, 30_000);
  if (!(await isUp(`${WEB}/sim`))) {
    web = spawn("node", [resolve(FRONTEND, "node_modules", "vite", "bin", "vite.js"), "--port", "19106", "--strictPort"], {
      cwd: FRONTEND,
      stdio: "ignore",
    });
  }
  await waitFor(`${WEB}/sim`, 60_000);
});

test.afterAll(async () => {
  bridge?.kill();
  web?.kill();
});

function pageErrors(page: Page): string[] {
  const errs: string[] = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  return errs;
}

async function createStorm(key: keyof typeof STORMS): Promise<{ episode_id: string; replay_digest: string }> {
  const s = STORMS[key];
  const post = async (): Promise<{ episode_id: string; replay_digest: string }> => {
    const r = await fetch(`${BRIDGE}/episode`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ seed: s.seed, faults: s.faults }),
    });
    if (!r.ok) throw new Error(`POST /episode ${r.status}: ${await r.text()}`);
    const j = (await r.json()) as { episode_id: string; replay_digest: string };
    return { episode_id: j.episode_id, replay_digest: j.replay_digest };
  };
  const first = await post();
  const second = await post();
  // Stale-state probe: same seed+faults twice → identical digest, distinct ids.
  expect(second.replay_digest).toBe(first.replay_digest);
  expect(second.episode_id).not.toBe(first.episode_id);
  return first;
}

async function openStorm(page: Page, episodeId: string): Promise<void> {
  await page.goto(`${WEB}/sim?episode=${episodeId}`);
  await expect(page.getByTestId("episode-id")).toHaveText(episodeId, { timeout: 30_000 });
  await page.getByTestId("speed-select").selectOption("4");
  await expect(page.getByTestId("row-count")).toHaveText("300", { timeout: 120_000 });
}

async function cursorStep(page: Page): Promise<number> {
  const text = (await page.getByTestId("cursor").textContent()) ?? "";
  const m = text.match(/Step (\d+)/);
  if (m === null || m[1] === undefined) throw new Error(`unparseable cursor: ${text}`);
  return Number(m[1]);
}

test("storm A multi-fault renders with capped feed + working filter", async ({ page }) => {
  const errs = pageErrors(page);
  const storm = await createStorm("A");
  await openStorm(page, storm.episode_id);
  // Storm identity on-page: FAULT_START rows from the injected B5 breakdown
  // (the clean auto-seed episode carries none). Digest equality is proven at
  // the API level by createStorm's double POST.
  const badge = page.getByTestId("feed-overflow");
  await expect(badge).toBeVisible({ timeout: 30_000 });
  await expect(badge).toContainText(/…\+\d+ more/);
  // Filter narrows to the injected DOWN/UP family only (7 DOWN + 7 UP pinned).
  await page.getByTestId("feed-family-filter").selectOption("DOWN_UP");
  const rows = page.getByTestId("event-row");
  await expect(rows).toHaveCount(14, { timeout: 30_000 });
  for (let i = 0; i < 14; i += 1) {
    await expect(rows.nth(i)).toHaveAttribute("data-family", "DOWN_UP");
  }
  // Storm identity: FAULT_START/END rows from the injected faults (3 + 3 pinned).
  await page.getByTestId("feed-family-filter").selectOption("FAULT");
  const faultRows = page.getByTestId("event-row");
  await expect(faultRows).toHaveCount(6, { timeout: 30_000 });
  await expect(faultRows.first()).toHaveAttribute("data-machine", "B5");
  // Telemetry chart stays mounted and legible under the storm (Canvas paints
  // via the transient store; unit-level p95 proof lives in render-counter).
  await expect(page.getByTestId("strip-B5")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("feed-family-filter").selectOption("ALL");
  await page.getByTestId("event-feed").scrollIntoViewIfNeeded();
  await page.screenshot({ path: resolve(EVIDENCE, "task-13-storm-A.png") });
  expect(errs).toEqual([]);
});

test("storm B quality surge renders; REJECT flags visible on ASM2", async ({ page }) => {
  const errs = pageErrors(page);
  const storm = await createStorm("B");
  await openStorm(page, storm.episode_id);
  await expect(page.getByTestId("feed-overflow")).toBeVisible({ timeout: 30_000 });
  // Quality surge reaches parts: ASM2 panel flag reads REJECT (sticky-last join).
  await page.getByTestId("select-ASM2").click();
  await expect(page.getByTestId("machine-panel-flag")).toContainText("REJECT", { timeout: 30_000 });
  await page.screenshot({ path: resolve(EVIDENCE, "task-13-storm-B.png") });
  expect(errs).toEqual([]);
});

test("storm C delay cascade renders; DIVERT_SBUF rows filterable", async ({ page }) => {
  const errs = pageErrors(page);
  const storm = await createStorm("C");
  await openStorm(page, storm.episode_id);
  await page.getByTestId("feed-family-filter").selectOption("DIVERT_SBUF");
  const rows = page.getByTestId("event-row");
  await expect(rows).toHaveCount(6, { timeout: 30_000 });
  for (let i = 0; i < 6; i += 1) {
    await expect(rows.nth(i)).toHaveAttribute("data-family", "DIVERT_SBUF");
  }
  await page.getByTestId("feed-family-filter").selectOption("ALL");
  await expect(page.getByTestId("feed-overflow")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("event-feed").scrollIntoViewIfNeeded();
  await page.screenshot({ path: resolve(EVIDENCE, "task-13-storm-C.png") });
  expect(errs).toEqual([]);
});

test("unknown episode → disconnected banner, no crash", async ({ page }) => {
  const errs = pageErrors(page);
  await page.goto(`${WEB}/sim?episode=does-not-exist`);
  await expect(page.getByTestId("disconnected-banner")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("topology")).toBeVisible();
  expect(errs).toEqual([]);
});

test("BLOCKED states are shown, not hidden (storm C step 271 C4)", async ({ page }) => {
  const errs = pageErrors(page);
  const storm = await createStorm("C");
  await page.goto(`${WEB}/sim?episode=${storm.episode_id}`);
  await expect(page.getByTestId("episode-id")).toHaveText(storm.episode_id, { timeout: 30_000 });
  // Pause early, then step the shared cursor exactly onto the pinned BLOCKED tick.
  await page.getByTestId("play-pause").click();
  for (let i = 0; i < 320; i += 1) {
    if ((await cursorStep(page)) >= BLOCKED_STEP) break;
    await page.getByTestId("step-fwd").click();
  }
  expect(await cursorStep(page)).toBe(BLOCKED_STEP);
  await page.getByTestId(`select-${BLOCKED_MACHINE}`).click();
  await expect(page.getByTestId("machine-panel-state")).toHaveText("BLOCKED", { timeout: 30_000 });
  await page.screenshot({ path: resolve(EVIDENCE, "task-13-blocked-C4.png") });
  expect(errs).toEqual([]);
});
