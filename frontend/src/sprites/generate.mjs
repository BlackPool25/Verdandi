// frontend/src/sprites/generate.mjs — T6 pixel sprite generator.
// Rect-based integer grid -> merged <rect> symbols. Constraints:
// - integer grid cells only, integer x/y/width/height in output
// - shape-rendering="crispEdges", no stroke / filter / rx / opacity
// - adjacent same-color rects merged (row runs + vertical coalescing)
// - Sweetie16-locked palette (GrafxKid); status hues referenced by hex;
//   PICO-8 hexes allowed by hex reference only (no license claim).
// Usage: node src/sprites/generate.mjs  (from frontend/)
// Display rule: render at integer multiples of the 16px base (32/48/64...).
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const GRID = 16;

// Sweetie16 (GrafxKid, lospec sweetie-16). Single source of truth for art.
const PALETTE = {
  d: "#1a1c2c", // outline / darkest
  p: "#5d275d",
  r: "#b13e53",
  o: "#ef7d57",
  y: "#ffcd75",
  l: "#a7f070",
  g: "#38b764",
  t: "#257179",
  n: "#29366f",
  b: "#3b5dc9",
  c: "#41a6f6",
  a: "#73eff7",
  w: "#f4f4f4",
  s: "#94b0c2",
  m: "#566c86",
  v: "#333c57",
};

// 9 machine classes (src/config.py TEMP_RANGES keys). "." = transparent.
const SPRITES = {
  // feed: hopper funnel + grain dots + outlet chute
  feed: [
    "................",
    ".....dddddd.....",
    ".....dmmmmd.....",
    ".....dmyymd.....",
    ".....dmyymd.....",
    "......dmmd......",
    "......dmmd......",
    "......dmmd......",
    ".....ddmmdd.....",
    ".....dmmmmd.....",
    ".....dmmmmd.....",
    ".....dddddd.....",
    ".......dd.......",
    ".......dd.......",
    ".......dd.......",
    "......dddd......",
  ],
  // form: top press block + ram + anvil base
  form: [
    "......dddd......",
    "......dwwd......",
    "......dwwd......",
    "......dddd......",
    ".......dd.......",
    ".......dd.......",
    "....dddddddd....",
    "....dmmmmmmd....",
    "....dmvwwvmd....",
    "....dmmmmmmd....",
    "....dddddddd....",
    "..dddddddddddd..",
    "..dssssssssssd..",
    "..dssssssssssd..",
    "..dddddddddddd..",
    "................",
  ],
  // process: tank + side outlet pipe (teal body)
  process: [
    "................",
    "....dddddd......",
    "....dttttd......",
    "....dttttd..c...",
    "....dttttd.cc...",
    "....dttttd..c...",
    "....dttttd......",
    "....dttttd......",
    "....dttttdcccc..",
    "....dttttd......",
    "....dttttd......",
    "....dttttd......",
    "....dddddd......",
    "....dd..dd......",
    "....dd..dd......",
    "................",
  ],
  // finish: hot-line body, orange heat stripes, heat cap
  finish: [
    "................",
    ".....dddddd.....",
    ".....doooood....",
    ".....doooood....",
    ".....dddddd.....",
    "....dddddddd....",
    "....droooord....",
    "....drroorrd....",
    "....droooord....",
    "....drroorrd....",
    "....droooord....",
    "....dddddddd....",
    ".....dyyyyd.....",
    ".....dyyyyd.....",
    ".....dddddd.....",
    "................",
  ],
  // inspect-tail: scanner frame + aqua lens + down tail arrow
  "inspect-tail": [
    "................",
    "................",
    "..dddddddddddd..",
    "..dssssssssssd..",
    "..dssddaaddssd..",
    "..dssddaaddssd..",
    "..dssssssssssd..",
    "..dddddddddddd..",
    ".......dd.......",
    ".......dd.......",
    ".......dd.......",
    "......dddd......",
    ".....dddddd.....",
    "....dddddddd....",
    "................",
    "................",
  ],
  // assembly-kit: crate with kit cross + pallet (differs from join)
  "assembly-kit": [
    "................",
    "...dddddddddd...",
    "...dnnnnnnnnd...",
    "...dnnnyynnnd...",
    "...dnnnyynnnd...",
    "...dnyyyyyynd...",
    "...dnnnyynnnd...",
    "...dnnnyynnnd...",
    "...dnnnnnnnnd...",
    "...dddddddddd...",
    "...dddddddddd...",
    "..dddddddddddd..",
    "................",
    "................",
    "................",
    "................",
  ],
  // assembly-join: twin blocks bridged by join chevron (differs from kit)
  "assembly-join": [
    "................",
    "................",
    "..dddd....dddd..",
    "..dwwd....dwwd..",
    "..dwwd.bb.dwwd..",
    "..dwwd.bb.dwwd..",
    "..dddd.bb.dddd..",
    ".......bb.......",
    ".....bbbbb......",
    ".......bb.......",
    "..dddd.bb.dddd..",
    "..dmmd.bb.dmmd..",
    "..dmmd....dmmd..",
    "..dddd....dddd..",
    "................",
    "................",
  ],
  // test (ASM2): badge with check tick + noisy bench
  test: [
    "................",
    ".....dddddd.....",
    ".....dnnnnd.....",
    ".....dnlnnd.....",
    ".....dnllnd.....",
    ".....dnnlnd.....",
    ".....dnnnnd.....",
    ".....dddddd.....",
    "...dddddddddd...",
    "...dmmmlmmmld...",
    "...dmmlmmmmmd...",
    "...dmmmmmlmmd...",
    "...dddddddddd...",
    "....dd....dd....",
    "....dd....dd....",
    "................",
  ],
  // rework: loop ring with return arrowhead (orange)
  rework: [
    "................",
    ".....dddddd.....",
    "....dooooood....",
    "....do....od....",
    "....do....od....",
    "....do....od....",
    "....do....od....",
    "....do....od....",
    "....do....oddd..",
    "....do...oddd...",
    "....do..oodd....",
    "....do.oodd.....",
    "....doood.......",
    "................",
    "................",
    "................",
  ],
};

function toRects(rows, name) {
  if (rows.length !== GRID) throw new Error(`${name}: ${rows.length} rows, want ${GRID}`);
  let naive = 0;
  // Row runs: [x, w, color]
  const runs = rows.map((row, y) => {
    if (row.length !== GRID) throw new Error(`${name} row ${y}: width ${row.length}, want ${GRID}`);
    const out = [];
    let x = 0;
    while (x < GRID) {
      const ch = row[x];
      if (ch === ".") {
        x += 1;
        continue;
      }
      if (!(ch in PALETTE)) throw new Error(`${name} row ${y}: unknown key '${ch}'`);
      let w = 1;
      while (x + w < GRID && row[x + w] === ch) w += 1;
      out.push({ x, y, w, ch });
      naive += w;
      x += w;
    }
    return out;
  });
  // Vertical coalesce: same x/w/color in consecutive rows.
  const rects = [];
  const open = new Map(); // key x,w,ch -> rect
  for (const rowRuns of runs) {
    const seen = new Set();
    for (const r of rowRuns) {
      const key = `${r.x},${r.w},${r.ch}`;
      seen.add(key);
      const prev = open.get(key);
      if (prev) prev.h += 1;
      else {
        const rect = { x: r.x, y: r.y, w: r.w, h: 1, ch: r.ch };
        open.set(key, rect);
        rects.push(rect);
      }
    }
    for (const [key, rect] of [...open]) {
      const [x, , ch] = key.split(",");
      const alive = rowRuns.some((r) => r.x === Number(x) && r.ch === ch && r.w === rect.w);
      if (!alive) open.delete(key);
      void seen;
    }
  }
  return { rects, naive };
}

const here = dirname(fileURLToPath(import.meta.url));
const names = Object.keys(SPRITES);
if (names.length !== 9) throw new Error(`want 9 sprites, got ${names.length}: ${names.join(",")}`);

let totalNaive = 0;
const symbols = names.map((name) => {
  const { rects, naive } = toRects(SPRITES[name], name);
  totalNaive += naive;
  const body = rects
    .map((r) => `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" fill="${PALETTE[r.ch]}"/>`)
    .join("");
  return { name, rects: rects.length, naive, body };
});
const totalMerged = symbols.reduce((n, s) => n + s.rects, 0);
if (!(totalMerged < totalNaive)) {
  throw new Error(`merge check failed: merged=${totalMerged} naive=${totalNaive}`);
}

const svg =
  `<svg xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">` +
  symbols
    .map((s) => `<symbol id="sprite-${s.name}" viewBox="0 0 ${GRID} ${GRID}" shape-rendering="crispEdges">${s.body}</symbol>`)
    .join("") +
  `</svg>\n`;

mkdirSync(here, { recursive: true });
writeFileSync(join(here, "sprites.svg"), svg);
for (const s of symbols) console.log(`sprite ${s.name}: cells=${s.naive} rects=${s.rects}`);
console.log(`total: cells=${totalNaive} rects=${totalMerged} symbols=${symbols.length}`);
