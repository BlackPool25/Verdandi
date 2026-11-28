# W-minors — final-review minors lane (m0b-t-build)

## Status: 2 FIXED + 1 DEFERRED (uncommitted, shared worktree — controller integrates)

## Minor 2 — FIXED: `phrase_with_ollama` latency poisoned digit-run diff
- Root cause: `_stylist` in `src/phrase.py` injected `parsed["_latency_s"]`
  (e.g. `0.14159265`) into the candidate BEFORE `verify()`; the latency's
  digit-runs are never in the input number set, so the diff always failed and
  the Ollama path always fell back to template.
- Fix (own files only):
  - `src/phrase.py::_stylist` keeps latency in a closure holder
    (`timing["latency_s"]`), NOT in the returned dict; `phrase_with_ollama`
    copies it to `out["latency_s"]` after `phrase()` returns.
  - `src/phrase.py::verify` defensively strips `_latency_s` before the
    digit-run diff (covers any external stylist that adds the extra).
  - Flag-gating unchanged: path stays off unless `VERDANDI_PHRASE_LLM=1`.
- Tests (`tests/test_phrase.py`): `test_verify_ignores_latency_extra`,
  `test_ollama_path_latency_kept_out_of_verified_candidate` (mocked urlopen +
  env flag → `path == "llm"`, `latency_s` in out, absent from candidate).
  TDD RED (2 failed) → GREEN.

## Bare-except — FIXED: `scripts/report_incident.py:178` silent `except: pass`
- Fix (own file only): `except Exception as exc` now logs
  `report_incident: tev decision failed (<Type>: <msg>); falling back to
  template` to stderr, then falls through to the explicit template return.
  Broad clause retained deliberately: the tev client does network I/O and the
  script's contract is offline-never-crashes; the fix makes the fallback loud
  instead of silent.
- Test (`tests/test_report_incident.py`):
  `test_tev_failure_falls_back_to_template_with_warning` (JEV_API_KEY set,
  `TevClient.ask` raises `ConnectionError` → `via == "template"`, decision ==
  template, stderr mentions tev). TDD RED → GREEN.

## Minor 3 — DEFERRED: abstain-gated incidents leave no store row
- Gap confirmed: `diagnose_incident` (`src/diagnose.py:346-406`) returns early
  on all three abstain paths (`silent-clean`, `low-recall`,
  `low-confidence-calibrated`) without touching `store`; `run_report` passes
  `store` through but records nothing on abstain. Decided incidents get
  `incidents` + `predicted_cascade` + `symptoms` rows; abstains get none.
- Reason for deferral (not stall): closing the gap requires writes on those
  early returns in `src/diagnose.py`, which this lane does NOT own
  (shared tree; controller integrates). An unwired table in
  `src/incidents_store.py` alone would be dead code, so no code was added.
- Reopen trigger: lane owning `src/diagnose.py` implements side-table
  `abstain_events` mirroring the Task 7 migration pattern, e.g.:
  `CREATE TABLE IF NOT EXISTS abstain_events(id PK, seed, reason, conf, tau,
  trigger, created_at)` + `_ensure_abstain_events(conn)` check-then-ALTER
  migration called from `IncidentStore.__init__` + `record_abstain(...)`
  invoked on each early-abstain return when `store is not None`, with a test
  asserting one row per abstained `diagnose_incident(store=...)` call.

## TDD / gates (my files)
- RED: 3 new tests failed (2 phrase + 1 report_incident), 15 pre-existing passed.
- GREEN: `pytest tests/test_phrase.py tests/test_report_incident.py` → 18 passed.
- No other files touched; nothing committed (shared tree).
