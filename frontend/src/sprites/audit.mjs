// frontend/src/sprites/audit.mjs — T6 palette + crispness gate.
// Sweetie16-locked (GrafxKid). Status hues are referenced by hex value only.
// PICO-8 hexes are allowed by hex reference only (no license/CC-0 claim).
// Usage: node src/sprites/audit.mjs  (from frontend/)
// Exit 0 = clean, 1 = violation (prints file:line-style hits to stdout).
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const svg = readFileSync(join(here, "sprites.svg"), "utf8");

const SWEETIE16 = new Set(
  [
    "#1a1c2c", "#5d275d", "#b13e53", "#ef7d57",
    "#ffcd75", "#a7f070", "#38b764", "#257179",
    "#29366f", "#3b5dc9", "#41a6f6", "#73eff7",
    "#f4f4f4", "#94b0c2", "#566c86", "#333c57",
  ].map((h) => h.toLowerCase()),
);
// Status hues, by hex value only (all currently inside Sweetie16;
// listed separately so a future status hue is judged explicitly).
const STATUS_HEX = new Set(["#38b764", "#ef7d57", "#41a6f6", "#b13e53"]);
// PICO-8 palette hexes, allowed by hex reference only (no license claim).
const PICO8_HEX = new Set(
  [
    "#000000", "#1d2b53", "#7e2553", "#008751",
    "#ab5236", "#5f574f", "#c2c3c7", "#fff1e8",
    "#ff004d", "#ffa300", "#ffec27", "#00e436",
    "#29adff", "#83769c", "#ff77a8", "#ffccaa",
  ].map((h) => h.toLowerCase()),
);
const ALLOWED = new Set([...SWEETIE16, ...STATUS_HEX, ...PICO8_HEX]);

const failures = [];
const ok = (cond, msg) => {
  if (!cond) failures.push(msg);
  return cond;
};

// 1. Nine symbols, exact ids.
const ids = [...svg.matchAll(/<symbol[^>]*id="([^"]+)"/g)].map((m) => m[1]);
const want = [
  "feed", "form", "process", "finish", "inspect-tail",
  "assembly-kit", "assembly-join", "test", "rework",
].map((n) => `sprite-${n}`);
ok(ids.length === 9, `audit: want 9 symbols, found ${ids.length} [${ids.join(",")}]`);
for (const id of want) ok(ids.includes(id), `audit: missing symbol ${id}`);

// 2. Zero off-palette hex (any #rgb/#rrggbb in the file must be allowed).
const hexes = [...svg.matchAll(/#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g)].map((m) => m[0].toLowerCase());
const off = [...new Set(hexes)].filter((h) => !ALLOWED.has(h));
ok(off.length === 0, `audit: off-palette hex: ${off.join(" ") || "(none)"} — total hex refs=${hexes.length}`);

// 3. Crispness: crispEdges present, no stroke/filter/blur/rx/opacity.
ok(svg.includes("crispEdges"), "audit: shape-rendering=crispEdges missing");
for (const bad of ["stroke", "<filter", "feGaussianBlur", "feDropShadow", "rx=", "opacity="]) {
  ok(!svg.includes(bad), `audit: forbidden token '${bad}' present`);
}

// 4. Integer geometry on every rect.
const rects = [...svg.matchAll(/<rect ([^/]*)\/>/g)].map((m) => m[1]);
ok(rects.length > 0, "audit: no <rect> elements found");
for (const r of rects) {
  for (const k of ["x", "y", "width", "height"]) {
    const m = r.match(new RegExp(`${k}="([^"]+)"`));
    ok(!!m && /^\d+$/.test(m[1]), `audit: non-integer rect geometry ${k} in <rect ${r}/>`);
  }
}

if (failures.length > 0) {
  for (const f of failures) console.log(`FAIL ${f}`);
  process.exit(1);
}
console.log(`palette-audit: OK symbols=9 rects=${rects.length} hexrefs=${hexes.length} off-palette=0`);
