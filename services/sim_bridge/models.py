"""T1 validation mirror: twin-exact checks + bridge-strict superset.

Twin-mirror part delegates to src.twin._validate (single source of truth),
so twin error TEXT is verbatim by construction and any twin drift fails
the bridge tests loudly. Bridge-strict range checks (FAULT_RANGES) run
AFTER the mirror and are always labeled `bridge-strict (superset of twin)`,
never claimed as twin text.

Importable for T2/T3 reuse: validate_episode, twin_mirror_validate,
bridge_strict_check, TwinMirrorError, BridgeStrictError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import FAULT_RANGES

STRICT_LABEL = "bridge-strict (superset of twin)"

# Twin quality faults only raise the ASM2 reject rate; a quality fault
# anywhere else is accepted (twin mirror) but flagged as a silent no-op.
QUALITY_HOME = "ASM2"


class TwinMirrorError(ValueError):
    """Twin-mirror failure; str(exc) is twin-verbatim text."""


class BridgeStrictError(ValueError):
    """Bridge-strict superset failure; always carries STRICT_LABEL."""


def _alias_fault(f: Any) -> Any:
    """Accept `fault_class` as an alias of twin's `class` key (copy-on-write)."""
    if isinstance(f, dict) and "class" not in f and "fault_class" in f:
        f = dict(f)
        f["class"] = f["fault_class"]
    return f


def _alias_faults(fault: Any) -> Any:
    if isinstance(fault, dict):
        return _alias_fault(fault)
    if isinstance(fault, list):
        return [_alias_fault(f) for f in fault]
    return fault


def twin_mirror_validate(seed: Any, fault: Any) -> list[dict[str, Any]]:
    """Mirror src/twin.py::_validate line-for-line via delegation.

    Raises TwinMirrorError with twin-verbatim text on any twin failure
    (bad seed, unknown origin/class, window out of range, non-dict extra,
    same-machine gap<5). STUCK->breakdown normalization included.
    """
    from src.twin import _validate  # local: keeps module import light

    try:
        return _validate(seed, _alias_faults(fault))
    except (ValueError, TypeError) as e:
        raise TwinMirrorError(str(e)) from e


def bridge_strict_check(normed: list[dict[str, Any]]) -> None:
    """Superset range checks from FAULT_RANGES; violations -> BridgeStrictError.

    mag 4-7, dur 8-25, delay d 3-6, loss drop 0.10-0.30, breakdown
    mttr_mult 1-3, quality reject 0.15-0.40. Only explicitly provided
    values are checked (twin _materialize fills the rest at runtime).
    """
    (mlo, mhi) = FAULT_RANGES["mag_sigma"]
    (dlo, dhi) = FAULT_RANGES["dur"]
    (ddlo, ddhi) = FAULT_RANGES["delay_d"]
    (rlo, rhi) = FAULT_RANGES["drop_rate"]
    (mulo, muhi) = FAULT_RANGES["mttr_mult"]
    (rjlo, rjhi) = FAULT_RANGES["reject_rate"]

    def reject(fid: str, msg: str) -> BridgeStrictError:
        return BridgeStrictError(f"{STRICT_LABEL}: fault {fid}: {msg}")

    for f in normed:
        fid = str(f.get("id"))
        dur = f["dur"]
        if not (dlo <= dur <= dhi):
            raise reject(fid, f"dur={dur!r} out of range [{dlo},{dhi}]")
        mag = f.get("mag_sigma", None)
        if mag is not None and not (mlo <= float(mag) <= mhi):
            raise reject(fid, f"mag_sigma={mag!r} out of range [{mlo},{mhi}]")
        extra: dict[str, Any] = f.get("extra") or {}
        cls = f["class"]
        if cls == "delay" and "d" in extra and not (ddlo <= int(extra["d"]) <= ddhi):
            raise reject(fid, f"d={extra['d']!r} out of range [{ddlo},{ddhi}]")
        if cls == "loss" and "drop_rate" in extra:
            v = float(extra["drop_rate"])
            if not (rlo <= v <= rhi):
                raise reject(fid, f"drop_rate={v!r} out of range [{rlo},{rhi}]")
        if cls == "breakdown" and "mttr_mult" in extra:
            v = float(extra["mttr_mult"])
            if not (mulo <= v <= muhi):
                raise reject(fid, f"mttr_mult={v!r} out of range [{mulo},{muhi}]")
        if cls == "quality" and "reject_rate" in extra:
            v = float(extra["reject_rate"])
            if not (rjlo <= v <= rjhi):
                raise reject(fid, f"reject_rate={v!r} out of range [{rjlo},{rjhi}]")


@dataclass(frozen=True)
class ValidationResult:
    faults: list[dict[str, Any]] = field(default_factory=list)
    noop_warning: bool = False


def validate_episode(seed: Any, fault: Any) -> ValidationResult:
    """Twin mirror first, bridge-strict second. Returns normalized faults."""
    normed = twin_mirror_validate(seed, fault)
    bridge_strict_check(normed)
    noop = any(
        f["class"] == "quality" and f["origin"] != QUALITY_HOME for f in normed
    )
    return ValidationResult(faults=normed, noop_warning=noop)
