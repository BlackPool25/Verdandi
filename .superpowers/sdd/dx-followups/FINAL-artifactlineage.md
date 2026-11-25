# FINAL artifact lineage audit — follow-up wave (read-only)

Date: 2026-11-25. Worktree: `.worktrees/m0b-t-build` (Verdandi repo).
Method: read-only. Plain file reads + `python json.load` (parse + field/length
checks) + text reads of the two shuffle logs. No artifacts modified, no commit,
no tests run, no Linear writes.

Lane reports used as headline sources:
- fullnat pair → `.superpowers/sdd/dx-followups/W-v2naturals74.md` + `docs/SIM_BASELINE.md` (§ audit + § rerun results)
- e2e pair → `.superpowers/sdd/dx-followups/W-e2e66.md`
- normfam → `.superpowers/sdd/dx-followups/W-normfam.md`
- shuffle logs → `.superpowers/sdd/dx-followups/W-shuffle62.md`

## Summary table

| file | parses as JSON | entries / rows | seed fields | headline match |
|---|---|---|---|---|
| `docs/m0b_mass_v2_fullnat_on.json` | yes | 700 rows; fault_ids 700, clean_ids 300; 3 shards | `master_seed` 1 | yes |
| `docs/m0b_mass_v2_fullnat_off.json` | yes | 700 rows; fault_ids 700, clean_ids 300; 3 shards | `master_seed` 1 | yes |
| `artifacts/e2e-selective-n200-s0.json` | yes | 200 per-episode entries; n=200, n_covered=3 | lineage `seed` 0 | yes |
| `artifacts/e2e-selective-n200-s1.json` | yes | 200 per-episode entries; n=200, n_covered=5 | lineage `seed` 1 | yes |
| `artifacts/eval_family_norm.json` | yes | 240 episode_ids; n_ep=240, n_win=4800; 4 cells | `seed` 0 | yes |
| `artifacts/tev_shuffle62_fixed.log` | n/a (text) | 110 lines: 53 ep + 53 sc + summaries | order=fixed, order_seed=0 in summary line | yes |
| `artifacts/tev_shuffle62_shuffled.log` | n/a (text) | 110 lines: 53 ep + 53 sc + summaries | order=shuffled, order_seed=1 in summary line | yes |

Verified: 7. Mismatched: 0.

## 1. `docs/m0b_mass_v2_fullnat_on.json` / `_off.json` — VERIFIED (both)

- Both parse as JSON (`json.load` OK).
- Both are dicts with exactly the expected keys:
  `battery_id / fault_episodes / clean_episodes / rows / master_seed / shards`.
- Counts: `len(rows)` = 700 both arms; `len(fault_episodes)` = 700,
  `len(clean_episodes)` = 300 both arms (the fields hold ID lists, not scalars).
- `battery_id`: `m0b-mass-v2-fullnat-on` / `m0b-mass-v2-fullnat-off` (distinct, correct arms).
- `master_seed`: 1 both arms (matches "seed 1" rerun claim).
- `shards`: 3 paths each
  (`artifacts/m0b_mass_v2_fullnat_{on,off}_{00,01,02}.parquet`); all six
  parquet files exist in `artifacts/`.
- Row schema spot-check (`rows[0]`): keys
  `class/dur/extra/id/mag_rung/mag_sigma/origin/rep/sev/t0`; `rows[0]` is
  `M-BII000` bias in BOTH arms (grid-identity anchor consistent with report).
- Grid-identity re-check via `json.load` (read-only comparison):
  row-diff OFF↔ON ignoring `extra` = 0; `extra`-diffs = 200 — exactly the
  "0 / 200 = 100 loss `couple_loss` + 100 quality `sink_all`" claim in
  `SIM_BASELINE.md:91-94` and `W-v2naturals74.md:23`.
- Headline match: the JSONs are battery manifests, not eval outputs, so the
  retrieval/clean-fire numbers (e.g. ON 0.733 @ cf 0.117 vs OFF 0.694 @ 0.093,
  `SIM_BASELINE.md:112-121`) live in the markdown table, with `n=700/300`
  consistent with the manifest's 700 fault + 300 clean IDs. No contradiction.
  Expectation "700 rows each" met exactly.

## 2. `artifacts/e2e-selective-n200-s0.json` / `-s1.json` — VERIFIED (both)

- Both parse as JSON. Top-level keys: `episodes / lineage / summary`.
- Entry counts: `len(episodes)` = 200 each; `summary.n` = 200 each.
- Lineage seeds: s0 `seed` 0, s1 `seed` 1 (distinct, as expected).
  Lineage battery `artifacts/m0b_mass_*.parquet (frozen, read-only)`,
  gate `live src.diagnose.diagnose_incident + load_calibrator()`,
  trigger `oracle first fault_mask tick (perfect-retrieval assumption)`,
  scores `measured max|prefix-z|`, served calibrator
  T=2.58 / a=6.4202 / b=-2.7236 / tau=0.739 / risk_target=0.3 — matches `W-e2e66.md:29-31,79-80`.
- Headline numbers match `W-e2e66.md:39-41` exactly:
  - s0: coverage 0.015 (n_covered 3/200), selective-acc 0.3333 (1/3),
    selective-risk 0.6667; abstain single-node 112 / silent-clean 39 / low-conf-cal 46.
  - s1: coverage 0.025 (5/200), selective-acc 0.8 (4/5),
    selective-risk 0.2; abstain 121 / 33 / 41.
  - pooled (computed from the two files): (3+5)/400 = 0.020 @ (1+4)/8 = 0.625 —
    the report's pooled row 0.020 (8/400) @ 0.625.
- Internal consistency: `covered` flags in `episodes` count 3 (s0) and 5 (s1),
  equal to `n_covered`; abstain sums + covered = 200 each
  (112+39+46+3, 121+33+41+5). Spot-check s0 `episodes[0]`: ep 40023, tau 0.739,
  reason single-node — the live-gate abstain path the report attributes the
  coverage collapse to.
- Expectation "measured E2E ~0.020 lineage" met: pooled measured coverage 0.020,
  lineage fields present in both files.

## 3. `artifacts/eval_family_norm.json` — VERIFIED

- Parses as JSON. Keys: `seed/parquet/w/stride/splits/n_windows/n_episodes/
  episode_ids/episodes_per_family/n_clean_episodes/features/cells`.
- Counts: `n_episodes` 240, `len(episode_ids)` 240, `n_windows` 4800,
  `episodes_per_family` 24 each × 7 families (bias/breakdown/delay/drift/loss/
  quality/spike), `n_clean_episodes` 72 — matches "same seed-pinned 240 episodes
  (24/family + 72 clean)" and "n=4800 windows" in `W-normfam.md:26,34`.
- Seeds/config: `seed` 0; `parquet` `artifacts/m0b_mass_c*.parquet` (the
  constrained dense-cut glob — the rerun fix the report describes);
  `w` 128, `splits` 3 — match the report.
- Headline F1s match `W-normfam.md:37-39` exactly:
  binary/clean 0.7773, binary/all 0.7773, multiclass/clean 0.7645,
  multiclass/all 0.7645 (norm effect 0.0000 both heads).
- Per-family values match within report rounding:
  binary breakdown 0.9818 / delay 0.9385 / loss 0.9461 / spike 0.6129 /
  bias 0.5884 / quality 0.4963 / drift 0.3293;
  multiclass breakdown 0.7956 / loss 0.9293 / delay 0.4836 / bias 0.3027 /
  spike 0.0753 / quality 0.0662 / drift 0.0482.
- Supporting file `artifacts/eval_family_norm.log` exists (2062 bytes; not
  UTF-8 text — binary-ish, noted only; the JSON is the verified artifact).

## 4. Shuffle probe logs (`artifacts/tev_shuffle62_{fixed,shuffled}.log`) — VERIFIED (both)

Referenced by `W-shuffle62.md:30-31`. Both logs read as text (UTF-8-SIG; first
line carries a BOM — counting note only, content unaffected).
- Fixed: 110 lines = 53 `ep` + 1 `tev machine top-1` summary + 1 kill-bar +
  53 `sc` + 2 SC summary lines.
- Shuffled: identical structure, 110 lines, 53 `ep` + 53 `sc`.
- Episode-set check (text read): the 53 `ep` IDs are identical as sets AND in
  order between arms (first ep 43007 both) — matches "same 53 eps, identical
  episode set both arms".
- Summary lines match `W-shuffle62.md:4-10` verbatim:
  - fixed: `machine top-1=0.113 family top-1=0.132 null_rate=0.000 (n=53,
    order=fixed, order_seed=0)`; SC `machine top-1=0.113 (n=53, votes=5)`.
  - shuffled: `machine top-1=0.113 family top-1=0.170 null_rate=0.000 (n=53,
    order=shuffled, order_seed=1)`; SC `machine top-1=0.094`.
- `artifacts/tev_shuffle62.done` exists (marker, content `DONE`).

## Result

Files verified: 7 (2 fullnat manifests + 2 e2e + 1 normfam + 2 shuffle logs).
Mismatched: 0. No headline number in any of the four lane reports contradicts
its data file(s); internal sums (abstain+covered=200, pooled 8/400=0.020,
240 eps / 4800 windows, 53+53 identical shuffle episodes, 0/200 grid diff)
all reconcile. Nothing was modified, committed, tested, or written to Linear.
