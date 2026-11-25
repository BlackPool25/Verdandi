# W-judge72 lane report — PRISSUE-72 remainder (eval_jev recall top-up)

## (1) Prior fix-round verification — HOLDS
Re-ran `tests/test_eval_faithfulness.py`: **12 passed, 1 skipped** before my
change (skip = `test_real_model_gated`, correctly gated on `VERDANDI_MNLI_PATH`).
- NliUnavailable skip: `test_no_client_skips_with_reason` green
  (`client=None` raises; `corpus_nli` returns `SKIPPED (no local MNLI model)`).
- Flip-gate: `test_swap_disagreement_drops_judge`,
  `test_local_mnli_client_honors_order`, `test_swap_gate_fires_through_local_client`
  all green — rev-order swap is a real position swap, flip-kill 0.20 live.
- F1 (`fmt_rate` undefined on empty denominator) green.

## (2) Missing recall slice — ADDED (`claim_recall`)
Spec task-6-spec.md sec 2's fractional layer (required-claims-cited /
required-claims) had no function: `slot_recall` is binary, `coverage_recall`
is trace-based, `precision_card` counts extra claims. Added
`src/faithfulness.py::claim_recall` (None on abstain; template card =
cited/3; extra-claim LLM path scores over the card's own list), wired into
`aggregate()` as `recall_claim` and into `scripts/eval_jev.py`
(`recall_claim=` on the MEASURED line). Fixture tests: full card 1.0,
one-bad-citation 2/3 vs slot 0.0, abstain-excluded, LLM-extra-claim 3/4.

## (3) Abstain-pairing rule — ENFORCED + TESTED
`eval_jev.py` printed precision+abstain together but with no enforcement.
Extracted `format_report()` — the sole emitter of metric lines, always
appending `abstain_rate` — plus `test_precision_never_reported_without_abstain_rate`
(zero-denominator case asserts `undefined (0 non-abstain)` present, never
bare 0.000). `main()` now prints only via `format_report`.

## NLI numbers — still DEFERRED, documented not faked
No MNLI weights on box (B1), no torch/transformers installed (B2); no
downloads, no torch installs, no requirements changes made. QUALITY keeps
`NLI faithfulness: SKIPPED (no local MNLI model)`.

## Tests / commit / paths
- `tests/test_eval_faithfulness.py` + `test_jev.py` + `test_jev_live.py` +
  `test_reporter.py`: **27 passed, 2 skipped** (both skips = key/model-gated).
- Commit: **none** (working-tree changes left for controller integration).
- Touched: `scripts/eval_jev.py`, `tests/test_eval_faithfulness.py`,
  `docs/DIAGNOSIS_QUALITY.md` (template-faithfulness rows + pairing note),
  additive-only `src/faithfulness.py` (`claim_recall` + `recall_claim` key;
  no other lane owns it, no existing key changed; `run.sh` /
  `tests/test_eval_tev.py` modifications in tree are NOT mine).
