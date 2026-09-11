# MCP Export Dry-Run (contract v1, zero live writes)

Field map: doc_id → summary prefix + provenance line; doc_type → issuetype Task + label; req_ids → labels + ID block verbatim; alt_ids → labels + grouped block; title → summary; body_md → ADF description (fenced code → code nodes, `|` escaped); acceptance → custom field else Acceptance section; priority → scheme name; source → footer; version → footer + label.

| Envelope | doc_id | doc_type | req_ids | alt_ids | acceptance |
|---|---|---|---|---|---|
| SRS | SRS-001 | srs (full) | REQ-001–010 | RSK-001–009, STK-001–005 | AC@1≥70%, ≥95% triples, 0-diverge, <10min, full-flow 6/6 |
| SDD | SDD-001 | sdd (full) | REQ-001–010 | ADR-0001–0012 | depth≤3, tau-2 flip<40%, ≤8s fallback, SeedSequence |
| Test plan | TSTPLAN-001 | test-plan (full) | REQ-001–003,006,010 | TST-001–007 | F1≥0.85, AC@1≥70%, flip<40%, <600s |
| Charter | CHARTER-001 | charter (pass-through) | — | — | — |
| Registers | REG-001 | registers (pass-through+alt) | — | RSK-001–009, STK-001–005 | — |
| Carry-through | CT-001 | carry-through (pass-through+alt) | — | ADR-0001–0012 | — |
| Sprint pack | SPRINT-001 | sprint-pack (full) | REQ-001–010 via traces-to | TST-001–007 | M0b F1≥0.85, M1 K1/K2@32f, M2 ≥95%, M3 0-diverge, M4 trail |

Source footers: `Exported from kanon, source ELENCHUS_DISCOVERY.md + docs/`; version `contract v1`. Dry-run only; secrets as `<PLACEHOLDER>`; no live writes.
