# Verdandi — every factory alarm ships with its proof

![Python](https://img.shields.io/badge/python-3.14-blue?logo=python)
![SimPy](https://img.shields.io/badge/simpy-4.1.2-green)
![React](https://img.shields.io/badge/react-19-61dafb?logo=react)
![CPU-only](https://img.shields.io/badge/compute-CPU--only-orange)
![Status](https://img.shields.io/badge/status-CONDITIONAL_GO-yellow)

A 26-machine factory twin where every alarm arrives with a ranked upstream cause, a why-explanation, and a seeded replay proving it, on one CPU laptop in under 10 minutes.

**Status: CONDITIONAL GO** (Crucible stress-tested, pre-build). K1/K3/K4/K5 survive. F1 ~0.73 sits below the 0.85 bar, so M0b detector-sensitivity is the one open item. See `PLAN.md` addendum 2026-09-11.

## Ship bars

Thresholds from `scripts/check_gates.py` defaults. Never soften without L1 reclassification.

| Metric | Bar | Current | Gate |
|---|---|---|---|
| F1 | >= 0.85 | ~0.73 (32-fault totals 0.725, `PLAN.md`) | **M0b open** |
| AC@1 | >= 70% intra+cross | 0.8125 (32-fault), 0.80 battery (`PLAN.md`) | pass |
| Flip | < 40% per partition | 14.4-30.3% line-scale (`docs/ARCHITECTURE.md`) | pass |
| Detection latency | <= 3 steps | per `ELENCHUS_DISCOVERY.md` bar | pass |
| p99 | <= 3s (`check_gates.py` default) | 3.7ms/fault (`PLAN.md`) | pass |
| Wall | < 600s | 17.7s battery (`PLAN.md`) | pass |
| Grounding | >= 95% | 1.00 harness (`PLAN.md`) | pass |
| Diverge | 0 (same-seed x5) | 0-diverge (K4 gate) | pass |

Kill triggers: K1 AC@1<30%/flip>40% cuts learning. K2 F1-drop>30pts makes quantile mandatory. K3 >5% ungrounded falls back to chain-cards. K4 diverge forces subgraph-only replay. K5 ROCm>1wk keeps the CPU baseline. The twin never issues safety-restart clearance.

## Quickstart (CPU-only)

```bash
docker compose up --build        # web viewer at http://localhost:19104, api on :8000
python -m pytest tests/ -m "k1 or k2 or k3 or k4 or k5 or battery" -n auto -q
python scripts/check_gates.py --csv artifacts/battery.csv
bash demo/run.sh                  # headless alarm-lifecycle check, seed 777
```

Ports come from `.env` (`WEB_PORT=19104`, `API_PORT=8000`). The frontend runs `npm --prefix frontend run gates` plus `pytest services/sim_bridge/tests -q` (see `docs/FRONTEND.md`).

## Architecture

Batch pipeline, single laptop, CPU-only:

`Twin -> Detect -> Veto-mask -> Walk -> Narrate+Verify -> Replay -> Waterfall UI + viva trail`

Hand-rolled SimPy twin, per-machine quantile/IQR detection, fixed ASM2 veto-mask, depth<=3 walk, template+verifier narration with chain-cards fallback, subgraph-only seeded replay, React/Zustand waterfall viewer. Full story in `docs/MDA.md` (CIM/PIM/PSM views) and `docs/ARCHITECTURE.md`.

## Data contract

Schema v6, `CODE_VERSION=twin-2.5.0-topology-A` (`src/config.py`). 26 machines x 300 ticks per episode, calibration window 120, warmup 15. Offline store is Parquet, there is no SQL database. Live transport is SSE tick frames from the FastAPI bridge. Frozen tick/header keys in `services/sim_bridge/SCHEMA.md`.

## Testing

300+ tests across 34 files in `tests/`, markers `k1-k5/battery/adversarial/mutation` (`pytest.ini`). CI runs lint-type, battery with 80% coverage floor, brutal gates (`scripts/check_gates.py`), 10/10 hostile-input rejection, and mutation non-vacuity (see `docs/CI.md`). Viewer has its own vitest suite (`frontend/package.json`).

## Docs map

| Doc | One line |
|---|---|
| `docs/MDA.md` | CIM/PIM/PSM models with Mermaid |
| `docs/ARCHITECTURE.md` | Pipeline, contracts, ATAM scenarios |
| `docs/SIM_SPEC.md` | Normative 26-machine plant spec (topology-A) |
| `docs/SDD.md` | IEEE 1016 design, 8 viewpoints |
| `docs/SRS.md` | IEEE 29148 requirements REQ-001-010 |
| `docs/TEST_PLAN.md` / `TEST_CASES.md` | IEEE 829 plan TST-001-010, cases TC-001-011 |
| `ELENCHUS_DISCOVERY.md` | Validated problem brief |
| `PLAN.md` | Build order M0-M5, stack, acceptance |
| `docs/CI.md` | Pipeline gates |
| `docs/FRONTEND.md` | Twin viewer spec |
| `docs/CARRY_THROUGH.md` | ADR-0001-0012, RFC, PR/FAQ |

## Roadmap

| Milestone | Scope (`PLAN.md`) | Status |
|---|---|---|
| M0 | Echo-aware attribution to F1>=0.85 | done (killed per ADR-0011, rescoped) |
| M0b | Detector sensitivity, missed-fault analysis first | in progress |
| M1 | Detection hardening, quantile-refit artifact | backlog |
| M2 | Narration + model wiring, grounding>=95% | backlog |
| M3 | Replay + demo harness, 0-diverge + <600s | backlog |
| M4 | Waterfall UI + viva trail | backlog |
| M5 | Viva dry-run + calibration | backlog |

## Scope boundaries

Fixed-per-semester topology; drift/noise/trust curve unmeasured. Real-plant drift, noise, and wear beyond the twin's models are unmeasured and no operator trust curve is claimed (see `docs/SIM_SPEC.md` section 13.4). No live stream, no blind discovery, no pretrained weights, no GPU-dependent demo, no safety-clearance authority.

## Links

- GitHub: https://github.com/BlackPool25/Verdandi
- Linear: Verdandi project (team PRISSUE, milestones M0-M5)
- Playbooks: `docs/LINEAR_PLAYBOOK.md` (team habits), `docs/CI.md` (brutal gates)
