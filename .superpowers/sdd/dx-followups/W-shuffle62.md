# W-shuffle62 — criteria-order bias probe (PRISSUE-62)

## Result
| order | machine top-1 | family top-1 | null rate | n | seed | order-seed |
|---|---|---|---|---|---|---|
| fixed | 0.113 (6/53) | 0.132 (7/53) | 0.000 | 53 | 0 | 0 |
| shuffled | 0.113 (6/53) | 0.170 (9/53) | 0.000 | 53 | 0 | 1 |

Fixed-arm gated self-consistency (machine-only, 5 votes, same 53 eps): 0.113 — unchanged, < 0.3.
Shuffled-arm gated self-consistency: 0.094 — also < 0.3.

## Bias verdict
Shuffle neither rescues nor collapses the decider: machine score identical
(0.113) under permuted option order. The failure is NOT an option-order
artifact — no position-bias rescue, default-choice pathology (B7S) stands on
its own. Family +0.038 under shuffle is noise at n=53, still far below bar.

## Kill disposition
**KILL stays** for tev as decider (0.113 << teacher 0.671; lifts only at
machine ≥ 0.671). Tev kept phrasing-only; ranker stays decider, never piped
into ranker. `src/jev.py` untouched.

## Lineage
- Battery: frozen T=300 `artifacts/m0b_mass_*.parquet` (48 shards); 60 eps
  sampled seed=0, 53 measurable (identical episode set both arms, verified).
- Model/transport: `tev1:4b` (7954dce22bc6), eval-only CLI transport
  (`ollama run --ask/--choice`, sequential, 60 s per-ask cap).
- Code: `scripts/eval_tev.py` (`--order`, `--order-seed`, `shuffled_criteria` /
  `apply_order`); 17/17 tests green in `tests/test_eval_tev.py`.
- Logs: `artifacts/tev_shuffle62_fixed.log`,
  `artifacts/tev_shuffle62_shuffled.log`.
- Eval-side change: two-phase battery load (id-column sample, then
  column-projected episode-filtered per-shard reads) after full-concat OOM
  under shared-machine pressure; same seed=0 episode set.
- Record: `docs/DIAGNOSIS_QUALITY.md` § Tev decider → Criteria-order shuffle.
