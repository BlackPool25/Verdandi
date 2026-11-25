# FINAL-f5-spec — read-only fidelity audit: 5 delay STARVED-mass test constants vs probe evidence

Scope: read-only. No edits to `src/possibility.py`, `tests/test_possibility.py`, `probe_delay.py`. No pytest, no commits, no Linear.
Sources: `tests/test_possibility.py` lines 71–117; `.superpowers/sdd/dx-followups/FINAL-probeassist.md`;
`docs/m0b_mass_full_manifest.json` (read-only dur lookup); probe episode table reproduced below.

## Probe evidence (FINAL-probeassist §1, live output 6/6 found)

| ep | with_O | miss6 | miss7 | sum_miss | S_starved | bufq |
|----|--------|-------|-------|----------|-----------|------|
| 41218 | 0.83 | 0.83 | 0.83 | 1.67 | 7 | 2.0 |
| 41220 | 0.50 | 0.50 | 0.50 | 1.00 | 7 | 0.0 |
| 41221 | 1.00 | 1.00 | 0.00 | 1.00 | 9 | 0.0 |
| 41242 | 0.50 | 0.50 | −0.50 | 0.00 | 3 | 0.0 |
| 41281 | 0.83 | 0.83 | −0.17 | 0.67 | 3 | 0.0 |
| 41291 | 1.00 | 1.00 | 1.00 | 2.00 | 9 | 0.0 |

Observed ranges: S_starved 3–9; bufq 0.0 in 5/6, one 2.0 (max 2.0); sum_miss 0.00–2.00 units vs S 3–9 steps
(steps ≪≫ units — gate must compare steps-to-steps with fan-out, per probeassist).
Manifest dur lookup (read-only, `rows[idx[ep]]`): 41218:dur=11, 41220:dur=9, 41221:dur=12,
41242:dur=9, 41281:dur=12, 41291:dur=12 → observed injected-dur range 9–12.
Probe window L = dur + H (H=30) inflates S with recovery starvation (probeassist calibration notes).
Decoupled specimen: ep 41242 (`with_O=0.50` yet `sum_miss=0.00`, `S=3`, `bufq=0.0`).

## Per-test verdict (regime support vs literal-constant support)

| # | test (lines) | constants | probe verdict |
|---|--------------|-----------|---------------|
| 1 | `holds_on_visible_delay` (71–78) | (injected=4, starved=6, n=2) → ok | REGIME SUPPORTED, literal NOT observed. Visible regime exists (bufq≈0 → S 3–9, e.g. 41218/41291). But: injected=4 is below observed dur 9–12; S/injected=1.5× fan-out ratio never observed (probe max S/dur = 7/9 ≈ 0.78; all 6 have S < dur). S=6 itself is inside observed S 3–9. Synthetic scaled-down analogue, not a verbatim episode. |
| 2 | `rejects_starvation_from_nothing` (81–88) | (2, 9, 2) → raises CONSERVATION | FENCE SUPPORTED, literal NOT observed. No episode shows S=9 from ~2 injected steps (observed S=9 episodes have dur=12). Valid as a synthetic upper-fence test of `S <= injected*n` (9 > 2×2=4), but it is a constructed violation, not an episode. |
| 3 | `flags_buffer_decoupled_delay` (91–100) | (6, 1, 2, shield=0.0) → raises VISIBILITY | QUALITATIVE MIRROR — YES, literal NOT verbatim. Pattern matches ep 41242: injected mass present, tiny S, empty buffers ⇒ delay went to caps/backpressure/failover, trip VISIBILITY. Differences: test S=1 is more extreme than observed minimum S=3; test injected=6 is below observed dur 9–12 (41242: dur=9, S=3). The decoupling signal in the probe is `sum_miss=0.00` with `with_O>0`, which the (steps,shield) gate encodes only approximately. Tripwire logic justified; numbers are synthetic. |
| 4 | `shielded_delay_passes` (103–108) | (6, 1, 2, shield=6.0) → ok/shielded | NOT SUPPORTED by probe — synthetic parameter test. Probe has NO stocked-buffer episode (max bufq=2.0; 5/6 exactly 0.0). shield=6.0 exceeds every observed bufq by 3×. Probeassist itself states this (§1c, §2: shield leg "cannot be calibrated from these 6 alone and must stay a parameter, not a fitted constant"). Passes as logic (`starved+shield >= injected`), not as evidence. Flagged. |
| 5 | `vacuous_without_downstream` (111–117) | (6, 0, 0) → ok/vacuous | NOT SUPPORTED by probe slice — topology-only. All 6 probe episodes are C2→C6→C7 (n=2); no sink-origin (tails/PKG/ASM2, n=0) episode in slice. Vacuous leg is a topological contract (`n_downstream==0 ⇒ nothing to check`), probe "trivially agrees". Flagged as non-empirical. |

## Direct answers

- Does (6,1,2,shield=0)→VISIBILITY mirror the decoupled specimen? YES qualitatively (empty-buffer +
  vanishing starved mass ⇒ distrust episode, ep 41242 pattern), but NOT verbatim: observed floor is S=3
  (not 1), observed dur is 9–12 (not 6), and the probe's decoupling proof is `sum_miss=0.00`, not the S value.
- Does (6,1,2,shield=6.0)→shielded mirror stocked-buffer absorption? NO. No stocked-buffer absorption
  episode exists in the 6 (bufq≤2). shield=6.0 is an uncalibrated synthetic input testing gate logic only.

## Counts

- Regime/fence support: 3 supported (visible-hold, conservation-reject, visibility-tripwire) / 2 unsupported
  empirically (shielded-pass, vacuous-pass).
- Literal-constant support (tuple appears verbatim in probe evidence): 0 / 5 supported, 5 / 5 synthetic.
  All three "supported" regimes use injected_steps (4, 6, 2) below the observed dur range 9–12, and no test
  tuple matches any (dur, S, bufq) row.

## Recommendation for F5 owner

Keep tests 1–3 as regime gates (document them as scaled analogues, not episode replays; cite dur 9–12 vs
test 4/6/2 scaling and H=30 S-inflation). Keep tests 4–5 but mark them `logic-only / non-empirical`:
shield=6.0 needs a stocked-buffer episode (bufq≫2) before it can be called evidence; vacuous needs a
sink-origin episode or stays a topology contract. Do not present any of the 5 tuples as "observed values".
