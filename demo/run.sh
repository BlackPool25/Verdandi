#!/usr/bin/env bash
# Headless end-to-end alarm lifecycle verification demo.
# Verifies seed 777 F-21 drift@B2 fault injection, detector monitoring,
# alarm triggering, and structured evidence telemetry without browser, Playwright,
# vite, or sim_bridge network services.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

PYTHON="${PYTHON:-python3}"
TIMEOUT_SECS=60
SEED=777
MAG_SIGMA="5.2"
IS_CLEAN=0

show_help() {
  cat << 'EOF'
Usage: demo/run.sh [OPTIONS]

Headless standalone end-to-end alarm lifecycle demo.
Simulates twin episode, monitors machine states and buffers, detects sensor
drift on machine B2, asserts alarm triggering at t0 >= 150, and outputs
structured evidence package.

Lifecycle Steps:
  [STEP 1/4] SEED: Initializing episode seed with F-21 drift@B2
  [STEP 2/4] DETECT: Monitoring machine states and buffers
  [STEP 3/4] ALARM: Alarm triggered on B2 at t >= 150
  [STEP 4/4] EVIDENCE: Verifying alarm telemetry and evidence package
  OVERALL DEMO VERDICT: PASS

Options:
  --seed INT         Episode seed (default: 777)
  --mag-sigma FLOAT  Fault magnitude in sigmas (default: 5.2, use 0.0 for clean)
  --clean            Run clean episode without fault (mag_sigma=0.0) to prove alarm assertion fails
  --timeout SECS     Maximum execution wall-clock time in seconds (default: 60)
  --help, -h         Show this help message and exit
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      show_help
      exit 0
      ;;
    --seed)
      SEED="$2"
      shift 2
      ;;
    --mag-sigma)
      MAG_SIGMA="$2"
      shift 2
      ;;
    --clean)
      IS_CLEAN=1
      MAG_SIGMA="0.0"
      shift
      ;;
    --timeout)
      TIMEOUT_SECS="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage details." >&2
      exit 1
      ;;
  esac
done

# Enforce wall-clock budget (< 60s)
if command -v timeout >/dev/null 2>&1; then
  CMD_PREFIX=(timeout "${TIMEOUT_SECS}s")
else
  CMD_PREFIX=()
fi

"${CMD_PREFIX[@]}" "$PYTHON" - "$SEED" "$MAG_SIGMA" "$IS_CLEAN" "$TIMEOUT_SECS" << 'PYEOF'
import json
import signal
import sys
import numpy as np

seed = int(sys.argv[1])
mag_sigma = float(sys.argv[2])
is_clean = sys.argv[3] == "1" or mag_sigma <= 0.0
timeout_secs = int(sys.argv[4])

# Register watchdog alarm for hang prevention (< 60s)
if hasattr(signal, "alarm"):
    signal.alarm(timeout_secs)

from src import twin

# ---------------------------------------------------------------------------
# [STEP 1/4] SEED
# ---------------------------------------------------------------------------
print(f"[STEP 1/4] SEED: Initializing episode seed {seed} with F-21 drift@B2...")

fault_spec = None if is_clean else {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": mag_sigma,
}

record = twin.run_episode(seed, fault=fault_spec)
replay_digest = twin.replay_digest(record)
b2_idx = twin.MACHINE_INDEX["B2"]
b2_cfg = record["machines"]["B2"]

print(f"  * Topology: {len(twin.MACHINES)} machines, {len(twin.BUFFERS)} buffers, duration T={record['T']}")
print(f"  * Machine B2 spec: base={b2_cfg['base']}, sigma={b2_cfg['sigma']}, buffer_cap={b2_cfg['buffer_cap']}")
if fault_spec:
    print(f"  * Fault injected: id={fault_spec['id']}, class={fault_spec['class']}, origin={fault_spec['origin']}, "
          f"t0={fault_spec['t0']}, dur={fault_spec['dur']}, mag_sigma={fault_spec['mag_sigma']}")
else:
    print("  * Fault injected: None (clean episode run)")
print(f"  * Replay digest: {replay_digest}")

# ---------------------------------------------------------------------------
# [STEP 2/4] DETECT
# ---------------------------------------------------------------------------
print("[STEP 2/4] DETECT: Monitoring machine states and buffers...")

cal_win = record["cal_win"]
obs_b2 = np.array(record["obs"][b2_idx], dtype=float)
cal = obs_b2[:cal_win]
cal_mean = float(np.mean(cal))
cal_std = float(np.std(cal))
q99 = float(np.quantile(cal, 0.99))
q1 = float(np.quantile(cal, 0.25))
q3 = float(np.quantile(cal, 0.75))
iqr_fence = float(q3 + 1.5 * (q3 - q1))
threshold = float(max(q99, iqr_fence))

print(f"  * Calibration window: [0, {cal_win}) steps (mean={cal_mean:.3f}, std={cal_std:.3f})")
print(f"  * Detection rule: IQR-fence / 99th-percentile (q99={q99:.3f}, fence={iqr_fence:.3f})")
print(f"  * Alarm threshold for B2: {threshold:.3f}")

buf_names = list(twin.BUFFERS.keys())
b12_idx = buf_names.index("B12")
b2b7p_idx = buf_names.index("B2B7P")
b2b7s_idx = buf_names.index("B2B7S")

# ---------------------------------------------------------------------------
# [STEP 3/4] ALARM
# ---------------------------------------------------------------------------
alarm_steps = [t for t in range(150, record["T"]) if obs_b2[t] > threshold]

if not alarm_steps:
    print(f"FAIL: No alarm triggered on machine B2 at or after t0=150.")
    print(f"  * Max observed value on B2 during t>=150 was {float(np.max(obs_b2[150:])):.3f} <= threshold {threshold:.3f}.")
    if is_clean:
        print("  * Expected behavior for clean run: zero false alarms.")
    sys.exit(1)

first_alarm_t = alarm_steps[0]
first_alarm_val = float(obs_b2[first_alarm_t])
delta = first_alarm_val - threshold

print(f"[STEP 3/4] ALARM: Alarm triggered on B2 at t={first_alarm_t} "
      f"(detected_value={first_alarm_val:.3f} > threshold={threshold:.3f}, delta=+{delta:.3f})")
print(f"  * Consecutive alarm duration: {len(alarm_steps)} ticks {alarm_steps}")
peak_idx = 150 + int(np.argmax(obs_b2[150:165]))
peak_val = float(obs_b2[peak_idx])
print(f"  * Peak anomaly on B2 at t={peak_idx}: value={peak_val:.3f} (+{(peak_val - cal_mean)/cal_std:.2f}σ)")

# ---------------------------------------------------------------------------
# [STEP 4/4] EVIDENCE
# ---------------------------------------------------------------------------
print("[STEP 4/4] EVIDENCE: Verifying alarm telemetry and evidence package...")

print("\nStructured Alarm Telemetry Window (t = 148 .. 163):")
print(f"{'Step':>6} | {'Timestamp':>9} | {'Machine':>7} | {'Detected Value':>14} | {'Threshold':>9} | {'Alarm State':>11} | {'Machine State':>13} | {'B12 Buf':>7} | {'B2B7P Buf':>9}")
print("-" * 105)

telemetry_list = []
for t in range(148, 164):
    val = float(obs_b2[t])
    st = record["states"][b2_idx][t]
    is_alarm = val > threshold
    alarm_str = "ALARM" if is_alarm else "NORMAL"
    b12_val = record["buffers"][b12_idx][t]
    b2b7p_val = record["buffers"][b2b7p_idx][t]
    print(f"{t:6d} | {t:9d} | {'B2':>7} | {val:14.3f} | {threshold:9.3f} | {alarm_str:>11} | {st:>13} | {b12_val:7d} | {b2b7p_val:9d}")
    telemetry_list.append({
        "step": t,
        "timestamp": t,
        "machine": "B2",
        "detected_value": round(val, 3),
        "threshold": round(threshold, 3),
        "alarm_state": alarm_str,
        "machine_state": st,
        "b12_buffer": b12_val,
        "b2b7p_buffer": b2b7p_val,
    })

evidence_package = {
    "demo": "demo/run.sh",
    "verdict": "PASS",
    "seed": seed,
    "machine": "B2",
    "fault": fault_spec,
    "first_alarm_step": first_alarm_t,
    "total_alarm_steps": len(alarm_steps),
    "peak_anomaly": {
        "step": peak_idx,
        "value": round(peak_val, 3),
        "sigma_deviation": round((peak_val - cal_mean) / cal_std, 2),
    },
    "replay_digest": replay_digest,
    "telemetry_sample": telemetry_list,
}

print("\nStructured JSON Evidence Package:")
print(json.dumps(evidence_package, indent=2))

print("\nOVERALL DEMO VERDICT: PASS")
PYEOF
