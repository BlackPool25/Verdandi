/**
 * FE-1 tour.spec.ts — roster guard for demo/frontend-tour.mjs.
 * The tour died when the v1 roster retired (B5 gone): selectOption("B5")
 * has no matching fault-form option and validateFaults rejects unknown
 * origins, so the F-21 episode never posts. This spec pins the tour to
 * machines that exist in today's 26-machine roster (MACHINE_IDS in
 * store/tick.ts, mirroring src/config.py MACHINE_INDEX) and to the
 * seed-777 F-21 contract shared with demo/frontend.sh.
 * Static (no servers): fails fast on roster drift without a browser.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const TOUR = resolve(REPO, "demo", "frontend-tour.mjs");
const TICK = resolve(HERE, "..", "src", "store", "tick.ts");

function roster(): Set<string> {
  const src = readFileSync(TICK, "utf8");
  const block = src.split("export const MACHINE_IDS =")[1]?.split("] as const")[0] ?? "";
  return new Set([...block.matchAll(/"([A-Z0-9_]+)"/g)].map((m) => m[1] as string));
}

function tourMachines(): string[] {
  const src = readFileSync(TOUR, "utf8");
  const out = new Set<string>();
  for (const re of [/selectOption\("([A-Z][A-Z0-9_]*)"\)/g, /select-([A-Z][A-Z0-9_]*)/g, /drift@([A-Z][A-Z0-9_]*)/g]) {
    for (const m of src.matchAll(re)) out.add(m[1] as string);
  }
  return [...out];
}

test("tour references only roster machines (no retired B5)", () => {
  const ids = roster();
  expect(ids.size).toBe(26);
  expect(ids.has("B5")).toBe(false);
  expect(ids.has("B2")).toBe(true);
  const used = tourMachines();
  expect(used.length).toBeGreaterThan(0);
  for (const id of used) {
    expect(ids.has(id), `tour machine ${id} not in 26-machine roster`).toBe(true);
  }
});

test("tour keeps the seed-777 F-21 drift contract", () => {
  const src = readFileSync(TOUR, "utf8");
  expect(src).toContain("seed=777");
  expect(src).toContain('selectOption("drift")');
  expect(src).toContain('selectOption("B2")');
  expect(src).toContain('fill("150")');
  expect(src).toContain('fill("12")');
  expect(src).toContain("mag_sigma");
});
