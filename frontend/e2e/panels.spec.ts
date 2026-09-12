/**
 * T8 panels.spec.ts — failing-first E2E for machine panels + buffer bars +
 * SBUF/AGV legend + ControlsBar mount on /sim.
 * Owns ONLY panels assertions; never touches topology/store/controls/tickSource.
 * Spins its own bridge (:18008) + vite main config (:19105); the page under
 * test is /sim?bridge=<bridge>&seed=777 (+&probe=ZZZ for the unknown-id case).
 */
import { spawn, type ChildProcess } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial", retries: 1 });
test.setTimeout(120_000);

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const FRONTEND = resolve(HERE, "..");
// Same-origin convention (vite proxies /episode|/stream|/schema → :8000),
// so no ?bridge= param: cross-origin fetches have no CORS headers.
const BRIDGE = "http://127.0.0.1:8000";
const WEB = "http://localhost:19105";

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
    bridge = spawn("python3", ["-m", "uvicorn", "services.sim_bridge.app:app", "--host", "127.0.0.1", "--port", "8000"], {
      cwd: REPO,
      stdio: "ignore",
    });
  }
  await waitFor(`${BRIDGE}/health`, 30_000);
  if (!(await isUp(`${WEB}/sim`))) {
    web = spawn(
      "node",
      [resolve(FRONTEND, "node_modules", "vite", "bin", "vite.js"), "--port", "19105", "--strictPort"],
      { cwd: FRONTEND, stdio: "ignore" },
    );
  }
  await waitFor(`${WEB}/sim`, 60_000);
});

test.afterAll(async () => {
  bridge?.kill();
  web?.kill();
});

const SIM = `${WEB}/sim?seed=777`;

test("ControlsBar visible on /sim and functional", async ({ page }) => {
  await page.goto(SIM);
  await page.getByTestId("seed-input").waitFor();
  await page.getByTestId("seed-input").fill("777");
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("episode-id")).not.toHaveText("none", { timeout: 60_000 });
  await expect(page.getByTestId("row-count")).toHaveText("300", { timeout: 60_000 });
});

test("select one machine per class → panel values render live", async ({ page }) => {
  await page.goto(SIM);
  await page.getByTestId("buffer-bars").waitFor({ timeout: 60_000 });
  const probes = ["A0", "A1", "B5", "A8", "A9", "ASM0", "ASM1", "ASM2", "RWK0"];
  for (const id of probes) {
    await page.getByTestId(`select-${id}`).click();
    await expect(page.getByTestId("machine-panel-state")).not.toBeEmpty({ timeout: 30_000 });
    await expect(page.getByTestId("machine-panel-obs")).not.toBeEmpty();
    await expect(page.getByTestId("machine-panel-tput")).not.toBeEmpty();
    await expect(page.getByTestId("machine-panel-envelope")).toContainText("base±3σ");
    await expect(page.getByTestId("machine-panel-cycle")).not.toBeEmpty();
  }
});

test("c7tail shows final + no-series label; legends never claim SBUF-divert", async ({ page }) => {
  await page.goto(SIM);
  await page.getByTestId("buffer-bars").waitFor({ timeout: 60_000 });
  await page.getByTestId("select-_C7TAIL").click();
  await expect(page.getByTestId("machine-panel-c7tail-label")).toContainText("no per-step series");
  await expect(page.getByTestId("legend-tails")).toContainText("never SBUF-divert");
  await expect(page.getByTestId("legend-feed-form")).toContainText("never divert");
  await expect(page.getByTestId("sbuf-agv-legend")).toContainText("high-util");
});

test("unknown machine id → empty state, no throw (evidence screenshot)", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${SIM}&probe=ZZZ`);
  await expect(page.getByTestId("machine-panel-empty")).toContainText("Unknown machine id", { timeout: 30_000 });
  expect(errors).toEqual([]);
  await page.screenshot({ path: resolve(REPO, ".omo/evidence/task-8-unknown-id.png") });
});

test("B5 selected live screenshot (evidence)", async ({ page }) => {
  await page.goto(SIM);
  await page.getByTestId("buffer-bars").waitFor({ timeout: 60_000 });
  await page.getByTestId("select-B5").click();
  await expect(page.getByTestId("machine-panel-state")).not.toBeEmpty({ timeout: 30_000 });
  await page.screenshot({ path: resolve(REPO, ".omo/evidence/task-8-verdandi-pixel-twin-frontend.png"), fullPage: true });
});
