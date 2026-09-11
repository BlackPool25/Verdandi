# MESSAGES (append-only claim log)
## 2026-09-11 battery RQ1/RQ2 CLAIM
Battery executed on REAL path (FactorySimPy twin, `spike/battery_rq1_rq2.py`, wall 17.7s).
CLAIM: K1 SURVIVE (AC@1 0.80, PCMCI flip 14.4%), K2 FIRES (MP F1 0.063 vs quantile 0.734, gap 67pts) → quantile/IQR + fixed veto-mask mandatory, MP/GDN cut. Overall CONDITIONAL (F1 0.734 < 0.85 bar). Evidence: `spike/trace_battery.jsonl`, `spike/REPORT_BATTERY.md`. Production untouched; no BLACKBOARD/EVIDENCE/DECISIONS writes (absent in this checkout).
