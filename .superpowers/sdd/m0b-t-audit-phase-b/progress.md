# SDD ledger — plan: /home/shreyas/projects/Verdandi/.omo/plans/m0b-t-ml-prep.md (Phase B)
Branch: shreyasjoshi2511/m0b-t-audit-phase-b @ /home/shreyas/projects/Verdandi-worktrees/m0b-t-audit-phase-b
Spec: docs/M0B_PREREG.md + PRISSUE-10/28/31 + Phase-A SYNTHESIS.md.
Pre-flight: B2 (OQ-2 masked-vs-blind PCMCI), B3 (BARO + Jaccard), B4 (grounding audit) all consume src/detect.py + walk.py + pcmci_job.py + shadow.py, which do not exist (spike-only, old 6-machine topology, quarantine). Shared interface row: audits → Phase-1 port (PRISSUE-10). B2+ unexecutable until port lands or quarantine exception granted.
B1 (prereg fill) executable now: fault table machine IDs predate topology-A (M1-M6/ASM-GW*), classes (stall/gateway-drop) not in _FAULT_CLASSES, gateway set undefined for quota. Needs owner decisions.
Task B1: complete (commit 2ab1403; freeze script + 6 tests RED→GREEN, manifest 57b933a4 182 rows byte-identical, prereg filled, gateway waiver logged; full gate 425 passed + 1 skip, ruff/format clean)
Task P1-detect: complete (commit e7c5632; src/detect.py 124 pure LOC, 8 tests RED→GREEN; F-06 lat≤3, F-21 flagged at origin; full gate 433 passed, ruff/format/mypy clean)
Task A-audit (runnable half): complete (commit 43e21ed; scripts/run_m0b_baseline.py + 2 tests; F1=0.159 AC@1=0.423 hit 83/182 misses 99; signal classes covered, structural 92/104 missed; docs/M0B_BASELINE_AUDIT.md; full gate 435 passed, ruff clean). Blocked remainder (flip/BARO/grounding): walk.py + pcmci_job.py.
Task buffer-fix: complete (commit 681ecbc; gap channels + plant-total buffer_occ on v6 only, legacy v3-v5 byte-identical per frozen flag-day contracts; 3 RED→GREEN; full gate green).
Remaining Phase-1: walk.py (depth≤3+top-k+gateway), pcmci_job.py (bagged per-partition tau-2), shadow.py (cross-partition ranker).
