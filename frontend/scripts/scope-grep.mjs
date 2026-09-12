// frontend/scripts/scope-grep.mjs — T12 scope-fidelity gate.
// Fails (exit 1, file:line hits) if any forbidden token from plan line 31
// appears under frontend/ or services/. Word boundaries are load-bearing:
// bare-substring matching false-positives on `underscore`/`revival`, so
// `score`/`viva` substrings are NOT patterns — only the bounded forms below.
// Allowlist: `replay_digest` is explicitly ALLOWED in services/ (bridge
// determinism); it is intentionally absent from the pattern set. This script
// excludes itself: it must spell the patterns to enforce them.
// Usage: node scripts/scope-grep.mjs  (from frontend/)
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const FRONTEND = resolve(new URL(".", import.meta.url).pathname, "..");
const REPO = resolve(FRONTEND, "..");
const ROOTS = [FRONTEND, resolve(REPO, "services")];
const SKIP_DIRS = new Set(["node_modules", "dist", "test-results", "playwright-report", ".git"]);
const SKIP_FILES = new Set(["scope-grep.mjs"]);
const SKIP_EXT = new Set([".png", ".webm", ".svg", ".woff", ".woff2", ".map"]);

// Case-insensitive word-boundary patterns, verbatim from plan line 31.
const PATTERN = "\\bQ_DET\\b|\\bVETO\\b|\\bPCMCI\\b|\\branked\\b|\\btriple\\b|\\bgrounding_rate\\b|\\breplay_hash\\b|\\bviva\\b|\\bnarrat\\w*\\b|\\bwalk\\s*\\(";
const RE = new RegExp(PATTERN, "gi");

function walk(dir, out) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name) || SKIP_FILES.has(name)) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (st.isFile()) {
      if ([...SKIP_EXT].some((ext) => name.endsWith(ext))) continue;
      out.push(p);
    }
  }
}

const hits = [];
for (const root of ROOTS) {
  const files = [];
  walk(root, files);
  for (const f of files) {
    let text;
    try {
      text = readFileSync(f, "utf8");
    } catch {
      continue; // binary/unreadable: not a token carrier
    }
    if (text.includes("\uFFFD")) continue; // binary decoded as text
    const lines = text.split("\n");
    lines.forEach((line, i) => {
      RE.lastIndex = 0;
      let m;
      while ((m = RE.exec(line)) !== null) {
        hits.push(`${relative(REPO, f)}:${i + 1}: ${m[0].trim()}`);
        if (m[0].length === 0) break;
      }
    });
  }
}

if (hits.length > 0) {
  for (const h of hits) console.log(`SCOPE-FAIL ${h}`);
  process.exit(1);
}
console.log("scope-grep: OK (frontend/ + services/ clean)");
