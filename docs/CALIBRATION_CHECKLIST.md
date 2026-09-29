# W6 Calibration Checklist (MINIPRO-22 Todo 6)

Scope: determinism x5 + wall +2% + Q_DET helper. Commit
`test(twin): determinism wall calibration checklist` (tests + docs + gate-script).

## Context7 finding (wall-clock method, applied)

Stabilize the machine before timing (one untimed warmup episode, discarded);
measure with `time.perf_counter` and compare each fresh sample against a
freshly-measured mean via a relative budget factor — never against a copied
historic absolute.

## Relative-index warning

CH9 energy (`flow_stats["energy"]`) is a relative-only index (kVAh-apparent,
no power factor): never compare absolute kVAh across configs, code versions,
or schema versions. The wall budget is relative the same way —
`budget = fresh_mean * 1.02` where `fresh_mean` is re-proven in-worktree by
`python src/twin.py --calibrate <path>` on every run. A historic mean copied
from an earlier run invalidates the gate (FAIL by procedure, must re-prove).

## Q_DET helper

Threshold VALUES stay in MINIPRO-10/17 — they are explicit arguments here,
never literals in `src/twin.py` (and never in `scripts/check_gates.py`).

```python
def q_det_digest(rec_a, rec_b):
    digest_a = twin.replay_digest(rec_a)
    digest_b = twin.replay_digest(rec_b)
    return digest_a, digest_b, 0 if rec_a == rec_b else 1


def q_det_wall(wall_s, fresh_mean_s, factor):
    budget_s = fresh_mean_s * factor
    return budget_s, wall_s <= budget_s, wall_s / fresh_mean_s
```

Same functions live in `tests/test_twin_w6_determinism_wall.py`
(`test_q_det_wall_math_pure` pins the math deterministically).

## Evidence (worktree `verdandi-ch8-ch9` @ 6369123, clean `git status`)

Determinism — `pytest -k "diverge and (777 or 1234 or 999 or 42 or 2026)"`:

```text
10 passed, 1 deselected in 3.23s
```

Same-seed repeats give identical `replay_digest` (diverge=0) and identical
legacy-channel digests (obs/states) for seeds 777/1234/999/42/2026, clean and
F-21 fault episodes. Legacy channels pristine.

Fresh calibration — `python src/twin.py --calibrate .omo-w6-fresh-calibration.json`
(`PYTHONPATH=<worktree>`; `src/twin.py` needs `from src.config import`):

```text
mean_per_episode_s=0.1167 episodes=6 -> .omo-w6-fresh-calibration.json
```

Wall gate — `python scripts/check_gates.py --wall-mean <fresh> --budget-factor 1.02`:

```text
RUN1: seed=777 wall=0.1504s BREACH / seed=1234 OK / seed=999 wall=0.1192s BREACH (budget=0.1190s)
RUN2: seed=1234 wall=0.1204s BREACH, rest OK
RUN3: seed=777 wall=0.1365s BREACH / seed=999 wall=0.1297s BREACH / seed=42 wall=0.1221s BREACH
```

Verdict: wall FAIL (honest, no tuning to pass). The breaching seed rotates
run-to-run and RUN3 shows a global slowdown — environmental jitter, not a
twin regression: behavior is 0-diverge and a post-warmup probe measured
0.106–0.118s for all five seeds (all inside budget). Root cause: a 2% band
(~2.4ms) on ~0.11s episodes is noise-dominated on this machine, so the gate
as specified cannot pass reliably here. Recommendation for owner/W7+: keep
the 1.02 factor but apply it to means-of-repeats (or longer episodes), never
to a loosened factor or a copied historic mean. `src/twin.py` and threshold
ownership untouched — no values added.
