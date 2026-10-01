# Data Acquisition & Artifact Retention Policy

This document defines the storage, indexing, retention, and CI upload policy for Verdandi data acquisition artifacts, run logs, and performance tracking vectors.

---

## 1. Scope & Purpose

During calibration (`src/calibrate.py`), causal evidence window extraction (`src/evidence.py`), and dataset export (`src/dataset_export.py`), artifacts and runtime performance vectors are produced. This policy guarantees:
- Full traceability and auditability of simulation runs.
- Continuous performance and resource usage monitoring (wall-clock duration and peak RSS).
- Clean separation between ephemeral data artifacts and git version control.
- Deterministic CI artifact archiving and retention lifecycles.

---

## 2. Run Log Specification (`artifacts/runs.jsonl`)

Performance and execution vectors are logged to `artifacts/runs.jsonl` (or a user-specified path via `--runs-log`).

### 2.1 Vector Schema

Each row is a single, newline-terminated JSON object containing:

| Field | Type | Description |
|---|---|---|
| `run_id` | string | Unique execution identifier (e.g. `run-<epoch>-<uuid8>`) |
| `job_name` | string | Target acquisition job: `"calibrate"`, `"evidence"`, or `"dataset_v4"` |
| `wall_seconds` | float | Elapsed wall-clock time in seconds (measured via stdlib `time.perf_counter()`) |
| `peak_rss_kb` | float | Peak resident set size in kilobytes (measured via stdlib `resource.getrusage()`) |
| `peak_rss_mb` | float | Peak resident set size in megabytes (`peak_rss_kb / 1024.0`) |
| `timestamp` | string | ISO-8601 UTC timestamp of execution completion |
| `status` | string | Execution outcome: `"success"` or `"error"` |
| `artifact_path` | string | Path to generated artifact (file or directory) |
| `schema_version`| int | Twin schema version bound to the artifact (e.g. `4`) |
| `code_version` | string | Twin code version identifier (`config.CODE_VERSION`) |

### 2.2 Atomic Append & Concurrency Contract

To prevent line interleaving and file corruption when multiple workers execute concurrently (e.g. under `pytest -n auto` or parallel CI jobs):
- Writers acquire an exclusive POSIX advisory lock via `fcntl.flock(fd, fcntl.LOCK_EX)`.
- The single JSON line is written, flushed (`f.flush()`), and synced to storage (`os.fsync(fd)`).
- The lock is released (`fcntl.flock(fd, fcntl.LOCK_UN)`) in a `finally` block.
- Zero external profiling dependencies are permitted (pure stdlib `time`, `resource`, `fcntl`, `json`).

---

## 3. Storage & Gitignore Policy

All generated Parquet datasets, JSON manifests, and run logs reside in the `artifacts/` directory:
- `artifacts/cal_v4.parquet` + `artifacts/cal_v4.json`
- `artifacts/evidence_v4/*.parquet` + `artifacts/evidence_v4/*.json`
- `artifacts/dataset_v4.parquet` + metadata sidecars
- `artifacts/runs.jsonl`

### 3.1 Strict Gitignore Enforcement

`artifacts/` is strictly `.gitignore`d (line 10 of `.gitignore`).
- **RULE**: Data artifacts must NEVER be committed to the git repository.
- Prevents repository bloat, merge conflicts, and accidental data drift.
- Local cleanup: Running `rm -rf artifacts/` resets all local generated artifacts cleanly.

---

## 4. CI Artifact Upload & Retention Strategy

In continuous integration (`.github/workflows/ci.yml`), artifacts generated during the `battery` and acquisition jobs are uploaded via `actions/upload-artifact@v4`.

### 4.1 Retention Schedule

| Environment | Artifact Target | Retention Period | Justification |
|---|---|---|---|
| **Pull Requests** | `artifacts/` (`runs.jsonl`, Parquet, JSON sidecars) | **14 days** | Sufficient for PR review, verification, and regression debugging |
| **Main Branch (Merge)** | `artifacts/` (`runs.jsonl`, Parquet, JSON sidecars) | **90 days** | Serves as long-term baseline for release verification |
| **Scheduled / Nightly** | `artifacts/` (`runs.jsonl`, Parquet, JSON sidecars) | **30 days** | Audit trail for periodic performance drift monitoring |

### 4.2 CI Step Definition

```yaml
- name: Upload acquisition artifacts
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: acquisition-artifacts-${{ github.run_id }}
    path: |
      artifacts/runs.jsonl
      artifacts/cal_v4.parquet
      artifacts/cal_v4.json
      artifacts/evidence_v4/
      artifacts/dataset_v4.parquet
      artifacts/window_config.json
      artifacts/ingestion_metadata.json
    retention-days: ${{ github.event_name == 'pull_request' && 14 || 90 }}
```

---

## 5. Performance Gate Enforcement (`scripts/check_gates.py`)

Execution budgets are enforced automatically by `scripts/check_gates.py`:

```bash
python scripts/check_gates.py --runs-log artifacts/runs.jsonl --budget-factor 1.02 --export-budget 60.0
```

### 5.1 Verification Checks

1. **Integrity**: Every line must be valid JSON with required fields present.
2. **Status**: All vectors must report `status == "success"`. Any `"error"` status immediately triggers `EXIT_ERROR` (code 1).
3. **Wall-clock Budget**: Each run's `wall_seconds` must satisfy:
   $$\text{wall\_seconds} \le \text{export\_budget} \times \text{budget\_factor}$$
   Breaching the budget triggers `EXIT_WALL_FAIL` (code 14).
4. **Memory Ceiling**: Peak RSS must not exceed `--max-rss-mb` (default 4096.0 MB).
5. **Pytest Isolation**: To prevent flaky tests caused by CPU noise on shared runners, unit and contract tests in `pytest` check numeric validity (`wall_seconds > 0`, `peak_rss_kb > 0`), while threshold gating is executed exclusively by `scripts/check_gates.py`.
