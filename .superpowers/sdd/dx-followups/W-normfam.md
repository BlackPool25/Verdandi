# W-normfam — norm-matched per-family comparison (Shreyas F21, PRISSUE-63)

Scope: ONE new analysis script (`scripts/eval_family_norm.py`) + its tests
+ this record. `scripts/eval_stacked.py` read-only (never edited). No Linear
writes. No serving artifacts touched/retrained.

## Question

The recorded multiclass-vs-binary gap (multiclass window-F1 0.795 < binary
0.846, `docs/WINDOW_GBM_V1_MODEL_CARD.md:71-76`) is norm-protocol-confounded:
the multiclass head centers median/IQR on ALL train rows
(`scripts/train_multiclass.py:43-50`) while the binary head fits clean-only
(`scripts/train_windows.py:150`, `src/window_dataset.fit_clean_norm`). Before
trusting the family-capped conclusion (ranker==teacher; multiclass killed,
per-family thresholds on binary remain the family mechanism), match
normalization first, then compare.

## Method (TDD, RED→GREEN)

- `tests/test_eval_family_norm.py` (5 passed): protocols differ on
  contaminated data; clean-norm ignores fault rows / all-norm does not;
  2x2 returns four norm-matched cells with high F1 on separable blobs;
  seed-determinism; n_obs-passthrough equals full-width on trees.
- `scripts/eval_family_norm.py`: 2x2 OOF {binary, multiclass} x
  {clean-norm, all-norm}, same seed-pinned 240 episodes (24/family + 72
  clean), dense-cut battery `artifacts/m0b_mass_c*.parquet`, w=128/stride=8
  invariant-23 (first 15 obs-stat cols normalized, 8 struct passthrough —
  the published protocol), 3-fold episode-grouped CV, HistGBM max_iter=300
  seed=0. Analysis-only output: `artifacts/eval_family_norm.json` (episode
  IDs listed) + `.log`. First attempt used the loose `m0b_mass_*` glob and
  swept the longer v2_full shards (mixed batteries, 234/240 episodes) —
  caught by the n-check, rerun constrained to `m0b_mass_c*`: 240/240.

## Numbers (MEASURED, n=4800 windows / 240 episodes, seed=0)

| head | clean-norm F1 | all-norm F1 | norm effect |
|---|---|---|---|
| binary | 0.7773 | 0.7773 | 0.0000 |
| multiclass (fault = pred != none) | 0.7645 | 0.7645 | 0.0000 |

- Matched gap multi−binary = **−0.0128** under clean norm, **−0.0128** under
  all norm (published confounded gap −0.051, same sign).
- Per-family under matched norms — binary recall: breakdown 0.982, delay
  0.939, loss 0.946, spike 0.613, bias 0.588, quality 0.496, drift 0.329;
  multiclass attribution: breakdown 0.796, loss 0.929, delay 0.484, bias
  0.303, spike 0.075, quality 0.066, drift 0.048 — obs-family collapse
  replicates the model-card kill basis exactly.

## Verdict: family-capped conclusion SURVIVES under matched norms

The suspected bias is a null: HistGBM trees are invariant to per-column
affine rescaling (order-preserving → identical splits), so norm protocol
contributes exactly 0.000 to either head. Multiclass stays killed;
per-family thresholds on the binary head remain the family mechanism.
Recorded in `docs/DIAGNOSIS_QUALITY.md` (Rerank section).

## Commit

None — worktree shared with other lanes' uncommitted changes; my files
(`scripts/eval_family_norm.py`, `tests/test_eval_family_norm.py`,
`docs/DIAGNOSIS_QUALITY.md` note, this report) left uncommitted for owner
to pick up.
