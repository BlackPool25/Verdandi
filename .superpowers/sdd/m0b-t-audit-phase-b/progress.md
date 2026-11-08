# SDD ledger — plan: /home/shreyas/projects/Verdandi/.omo/plans/m0b-t-ml-prep.md (Phase B)
Branch: shreyasjoshi2511/m0b-t-audit-phase-b @ /home/shreyas/projects/Verdandi-worktrees/m0b-t-audit-phase-b
Spec: docs/M0B_PREREG.md + PRISSUE-10/28/31 + Phase-A SYNTHESIS.md.
Pre-flight: B2 (OQ-2 masked-vs-blind PCMCI), B3 (BARO + Jaccard), B4 (grounding audit) all consume src/detect.py + walk.py + pcmci_job.py + shadow.py, which do not exist (spike-only, old 6-machine topology, quarantine). Shared interface row: audits → Phase-1 port (PRISSUE-10). B2+ unexecutable until port lands or quarantine exception granted.
B1 (prereg fill) executable now: fault table machine IDs predate topology-A (M1-M6/ASM-GW*), classes (stall/gateway-drop) not in _FAULT_CLASSES, gateway set undefined for quota. Needs owner decisions.
Ruling: prereg §2 fixed-percentile superseded by owner 3-arm + per-class decision (Phase A); §2 to be rewritten in train-preregistration (Phase C), not patched here.
