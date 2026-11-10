# Sim baseline lock (pre C-fixes, 2026-11-10)

Battery: frozen `m0b_mass` T=300 (4200 fault + 600 clean).
Code: HEAD at plan start (`git log --oneline -1` at commit time).

## Gates (MEASURED 2026-11-10)
- `test_twin_gates` + `test_plumbing` + `test_twin_quality`: 21 passed.
- Full suite: 717 passed, 1 skipped (2026-11-10).

## Silence (MEASURED)
- Battery level (stage-2 eval): votable 2665/4200 → silent 1535/4200 = 0.365.
- Cache level (`window_cache/meta`, 572 fault eps, votable = teacher pred non-none):

| family | silent/total | share |
|---|---|---|
| loss | 65/93 | 0.70 |
| quality | 49/87 | 0.56 |
| bias | 27/78 | 0.35 |
| drift | 31/88 | 0.35 |
| spike | 25/69 | 0.36 |
| breakdown | 0/69 | 0.00 |
| delay | 0/88 | 0.00 |

Confirms audit: silence concentrated in loss + quality-off-sink + incipient sensor rungs.

## Diagnosis numbers on this battery (MEASURED, unchanged by sim work)
- Retrieval 0.800 @ 0.032; rerank 0.685 votable; paths root@1 0.132 / subseq@3 0.413 (k 1.5);
  family 0.502; sensor 0.26–0.33; onset proc 2.0 / sensor ~90; e2e pooled 0.432–0.436.

## v2 column (to fill in Task 4)
- silent Δ, route Δ, gates, family loss/quality Δ.
