# FINAL-f5-callsite — where the delay STARVED-mass gate SHOULD be wired (READ-ONLY audit)

Source worktree: `m0b-t-build`. No edits, no commits, no tests, no Linear.
Probe trust point (from `.superpowers/sdd/dx-followups/FINAL-probeassist.md:71`,
mirrored in `tests/test_possibility.py:98`): on a VISIBILITY trip
(ep 41242 pattern — injected delay mass vanishes with empty buffers),
**path tuning must distrust the episode**.
`assert_delay_starved_mass` itself does not exist yet in `src/possibility.py:332-379`
(F5 owns that definition); below are the call-site candidates ranked by leverage.

Note: `scripts/eval_rerank_teleport.py` (named in the task brief) **does not exist**
in this worktree. Checked analogues: `scripts/eval_stacked.py:304` (`rerank_top1`) /
`:334` (`main_rerank`) and `tests/test_rerank_teleport.py` operate on
`stage2-oof.npz` ranker scores, not path evidence — ruled out as wiring sites
(see #7). The live path-evidence loop is `scripts/eval_paths.py` + `src/diagnose.py`.

## Ranked candidates

1. `src/diagnose.py:387` — `ranked = upstream_paths(evidence, edges, anchor)` — PRIMARY: live path-tuning trust point where the ranked root→anchor path is picked from evidence; a decoupled delay (ep 41242) otherwise promotes a phantom path into `root`/`path`.
2. `src/diagnose.py:368-373` — `evidence` build loop (feeds `rank_nodes` at `:380`) — earliest in-pipeline hook: root + downstream STARVED counts + buffers (`twin._line_edges`, `buffer_C26/C67`) all exist here, so `injected_steps`/`starved_steps`/`n_downstream`/`buffer_shield_steps` can be derived before any rank.
3. `src/diagnose.py:400-406` → `:427` — calibration-gate block → `return build_report(...)` — final trust boundary with precedent (`research-calibration.md:105`: gate after rank, before `build_report`); VISIBILITY trip should abstain/distrust here so decoupled episodes never reach the operator card or `store.create_incident`/`link_or_create` writes at `:417-426`.
4. `scripts/eval_paths.py:137` — `paths = kbest_paths(ev, edges, anchor, k=k)` (eval loop `:84-142`) — offline path-tuning trust point that measures root-hit/subseq and decides the teleport keep/kill; decoupled episodes pollute the tuning signal, so gate `ev` here (`n` from `twin._DOWNSTREAM_MACHINES`, shield from `flow_mass_from_buffers` at `:15`).
5. `scripts/eval_paths.py:119-127` — `flow_teleport` blend after `ranker_evidence` (`:111-118`) — teleport trusts flow (trapped-WIP) mass, which is misleading exactly when delay is absorbed by caps/backpressure/failover; gate before blending or skip-blend on VISIBILITY trip.
6. `src/report.py:25-29` — `build_report` path selection / `best_path` fallback — defense-in-depth only: scores-only fallback path with no buffer context; `diagnose.py` sites above dominate.
7. `scripts/eval_stacked.py:304,334` + `tests/test_rerank_teleport.py` — checked and RULED OUT: calibrated rerank preserves per-episode argmax on ranker logits and never sees path evidence/buffers, so the STARVED-mass conservation lens does not apply there.

## Topology inputs for `n_downstream` / shield

- `src/twin.py:1699-1710` — `_DOWNSTREAM_MACHINES`: `C2→C6→C7` gives `n_downstream=2`; sink origins (tails, PKG, ASM2) give `n=0` → vacuous leg.
- `src/twin.py:238` (`_line_edges`) + `scripts/eval_paths.py:15` (`flow_mass_from_buffers`) + probe `bufq = buffer_C26+buffer_C67 at t0−1` — source for `buffer_shield_steps`.
