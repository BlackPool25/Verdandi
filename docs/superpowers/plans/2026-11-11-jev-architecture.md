# Jev Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classifier-free diagnosis with Jev-typed decisions and layered reports, evaluated for faithfulness.

**Architecture:** `docs/ARCHITECTURE_JEV.md` (approved).

**Tech Stack:** Python; Jev API (key-gated, offline-skippable); existing pipeline.

## Global Constraints

- TDD, full suite green; frozen detector/quarantine untouched.
- No torch; conventional commits; no push/merge without approval.
- Template reporter must work with zero model access.

## Review Focus

- Packet builder pure/deterministic (replay-hash test).
- Citation checks behavioral (permute evidence -> citations move), not string-match.
- Null path tested (silent episode -> abstain card, never a guess).
- Live-API tests key-gated skip, never blocking CI.

---

### Task 1: Evidence packet (schema + builder)

**Files:** Create `src/packet.py`; test `tests/test_packet.py` (exists? check — reuse/extend).

- [ ] RED: packet has all v1 fields with IDs; deterministic (two builds equal); silent episode -> abstain packet.
- [ ] GREEN: build from `diagnose_incident` outputs + calibration + flow counters.
- [ ] Run tests; commit.

### Task 2: Jev question spec + client

**Files:** Create `src/jev.py` (spec text versioned, e.g. `JEV_SPEC="v1"`; client with key from env, `JevUnavailable` fallback); test `tests/test_jev.py` (spec pins criteria keywords; client parses recorded fixtures; no-key -> skip).

- [ ] RED -> GREEN -> commit. No live calls in CI.

### Task 3: Template reporter + citation checks

**Files:** Create `src/reporter.py` (card + dossier from packet + Jev-style decision dict); test `tests/test_reporter.py` (every claim cites valid evidence ID; numbers verbatim; null decision -> abstain card).

- [ ] RED -> GREEN -> commit.

### Task 4: Live Jev wiring + eval

**Files:** `scripts/eval_jev.py` (fixed episode set; faithfulness, citation P/R, category acc vs 0.671, null rate).

- [ ] Run iff `JEV_API_KEY` present, else record skipped with reason.
- [ ] Commit report.
