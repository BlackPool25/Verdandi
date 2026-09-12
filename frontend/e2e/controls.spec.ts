/**
 * T7 controls.spec.ts — failing-first E2E for sim controls.
 * Owns ONLY controls assertions; never touches scaffold/topology/store.
 * Spins its own bridge (:18007) + vite (:19104) so T4's playwright.config
 * (no webServer block) stays untouched. Page under test is /controls.html,
 * a T7-owned harness (scaffold index.html / App.tsx untouched).
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
const BRIDGE = "http://127.0.0.1:18007";
const WEB = "http://localhost:19104";

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
  // Idempotent: under fullyParallel each worker runs this; only the first
  // spawn wins the port, losers exit, waitFor still passes.
  if (!(await isUp(`${BRIDGE}/health`))) {
    bridge = spawn("python3", ["-m", "uvicorn", "services.sim_bridge.app:app", "--host", "127.0.0.1", "--port", "18007"], {
      cwd: REPO,
      stdio: "ignore",
    });
  }
  await waitFor(`${BRIDGE}/health`, 30_000);
  if (!(await isUp(`${WEB}/controls.html`))) {
    web = spawn(
      "node",
      [
        resolve(FRONTEND, "node_modules", "vite", "bin", "vite.js"),
        "--config",
        "vite.controls.config.ts",
        "--port",
        "19104",
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

async function startEpisode(page: Page, seed: string): Promise<string> {
  await page.goto("/controls.html");
  await page.getByTestId("seed-input").fill(seed);
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("episode-id")).not.toHaveText("none", { timeout: 60_000 });
  await expect(page.getByTestId("row-count")).toHaveText("300", { timeout: 60_000 });
  await expect(page.getByTestId("cursor")).toContainText("Step", { timeout: 60_000 });
  return (await page.getByTestId("episode-id").textContent()) ?? "";
}

test("pause freezes cursor, resume advances", async ({ page }) => {
  await startEpisode(page, "777");
  // let it tick
  await page.waitForTimeout(1500);
  await page.getByTestId("play-pause").click(); // pause
  const frozen = await page.getByTestId("cursor").textContent();
  await page.waitForTimeout(900);
  expect(await page.getByTestId("cursor").textContent()).toBe(frozen);
  await page.getByTestId("play-pause").click(); // resume
  await page.waitForTimeout(900);
  expect(await page.getByTestId("cursor").textContent()).not.toBe(frozen);
});

test("step ±1 is deterministic (step k twice identical)", async ({ page }) => {
  await startEpisode(page, "777");
  await page.getByTestId("play-pause").click(); // pause for manual stepping
  await expect(page.getByTestId("play-pause")).toHaveText("Play");
  const at = async (): Promise<number> => {
    const t = (await page.getByTestId("cursor").textContent()) ?? "";
    return Number(t.replace("Step ", "").split(" /")[0]);
  };
  const s = await at();
  const first = await page.getByTestId("tick-json").textContent();
  for (let i = 0; i < 3; i++) await page.getByTestId("step-fwd").click();
  await expect(page.getByTestId("cursor")).toContainText(`Step ${Math.min(s + 3, 299)} / 300`);
  for (let i = 0; i < 3; i++) await page.getByTestId("step-back").click();
  await expect(page.getByTestId("cursor")).toContainText(`Step ${s} / 300`);
  expect(await page.getByTestId("tick-json").textContent()).toBe(first);
});

test("fault@B5 POSTs a new episode", async ({ page }) => {
  await startEpisode(page, "777");
  const before = await page.getByTestId("episode-id").textContent();
  await page.getByTestId("fault-class").selectOption("drift");
  await page.getByTestId("fault-origin").selectOption("B5");
  await page.getByTestId("fault-t0").fill("150");
  await page.getByTestId("fault-dur").fill("12");
  await page.getByTestId("fault-add").click();
  await expect(page.getByTestId("fault-list")).toContainText("B5");
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("episode-id")).not.toHaveText(before ?? "none", { timeout: 60_000 });
  await expect(page.getByTestId("form-error")).toBeEmpty({ timeout: 60_000 });
  await expect(page.getByTestId("episode-faults")).toContainText("B5");
});

test("quality@B9 warns noop, STUCK maps to breakdown", async ({ page }) => {
  await page.goto("/controls.html");
  await page.getByTestId("seed-input").fill("777");
  await page.getByTestId("fault-class").selectOption("quality");
  await page.getByTestId("fault-origin").selectOption("B9");
  await page.getByTestId("fault-t0").fill("150");
  await page.getByTestId("fault-dur").fill("12");
  await page.getByTestId("fault-add").click();
  await page.getByTestId("fault-class").selectOption("STUCK");
  await page.getByTestId("fault-origin").selectOption("B5");
  await page.getByTestId("fault-t0").fill("200");
  await page.getByTestId("fault-dur").fill("10");
  await page.getByTestId("fault-add").click();
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("noop-warning")).toContainText("noop", { timeout: 60_000 });
  await expect(page.getByTestId("episode-faults")).toContainText("breakdown");
});

test("full control tour (evidence)", async ({ page }) => {
  await page.goto("/controls.html");
  await page.getByTestId("seed-input").fill("777");
  await page.getByTestId("natural-toggle").uncheck();
  await page.getByTestId("natural-toggle").check();
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("row-count")).toHaveText("300", { timeout: 60_000 });
  await page.getByTestId("speed-select").selectOption("4");
  await page.getByTestId("play-pause").click();
  await page.getByTestId("step-fwd").click();
  await page.getByTestId("step-back").click();
  await page.getByTestId("play-pause").click();
  await page.getByTestId("speed-select").selectOption("1");
  await page.getByTestId("fault-class").selectOption("drift");
  await page.getByTestId("fault-origin").selectOption("B5");
  await page.getByTestId("fault-t0").fill("150");
  await page.getByTestId("fault-dur").fill("12");
  await page.getByTestId("fault-add").click();
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("episode-faults")).toContainText("B5", { timeout: 60_000 });
  await page.getByTestId("fault-class").selectOption("quality");
  await page.getByTestId("fault-origin").selectOption("B9");
  await page.getByTestId("fault-t0").fill("200");
  await page.getByTestId("fault-dur").fill("10");
  await page.getByTestId("fault-add").click();
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("noop-warning")).toContainText("noop", { timeout: 60_000 });
  await page.getByTestId("fault-class").selectOption("bias");
  await page.getByTestId("fault-origin").selectOption("C3");
  await page.getByTestId("fault-t0").fill("119");
  await page.getByTestId("fault-dur").fill("12");
  await page.getByTestId("fault-add").click();
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("form-error")).toContainText("fault window out of range", { timeout: 60_000 });
  await expect(page.getByTestId("cursor")).toContainText("Step");
});

test("t0=119 shows inline 422 twin text, no crash", async ({ page }) => {
  const firstId = await startEpisode(page, "777");
  await page.getByTestId("fault-class").selectOption("drift");
  await page.getByTestId("fault-origin").selectOption("B5");
  await page.getByTestId("fault-t0").fill("119");
  await page.getByTestId("fault-dur").fill("12");
  await page.getByTestId("fault-add").click();
  await page.getByTestId("new-episode").click();
  await expect(page.getByTestId("form-error")).toContainText("fault window out of range", { timeout: 60_000 });
  // old episode survives the failed submit (never mid-stream patched)
  expect(await page.getByTestId("episode-id").textContent()).toBe(firstId);
  await expect(page.getByTestId("cursor")).toContainText("Step");
});
