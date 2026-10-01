"""Tests for causal evidence window extraction and floor verification (Todo 2 / P0-2).

Normative specifications & constraints:
1. Exactly 4 causal evidence windows: ("line-A", "line-B", "line-C", "cell").
   Citing SIM_SPEC §10 vs twin.py:119: twin router returns "rework" for RWK*
   machines, but causal discovery (§10) treats rework as part of the "cell"
   partition.
2. Explicit partition remapping: the evidence layer MUST explicitly remap
   "rework" -> "cell", leaving the frozen twin router and _PARTITIONS untouched.
   A dedicated test asserts RWK0 rows are placed inside the "cell" window.
3. Causal evidence floor: every partition window has n >= 800 clean steps (N_FLOOR=800).
   Attempts to generate or export evidence with n < 800 must raise ValueError.
4. Full-graph request rejection: requesting full-graph causal evidence is BANNED
   (O(P^2 * tau) complexity explosion) and MUST raise ValueError loudly.
5. Node count cap: each partition window has node count <= 10 (NODE_CAP=10).
6. Unknown partition rejection: invalid/unknown partition names raise ValueError loudly.
7. Manifest metadata: per-window manifest containing partition, n_steps >= 800,
   seeds hash, schema, pyarrow version.
8. CLI execution contract: python -m src.evidence --out <dir> supports argparse
   and exits 0 on --help.
9. Guardrails: raw channels only (no aggregates), zero dependency on tigramite,
   and twin router / _PARTITIONS remain strictly frozen.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import subprocess
import sys
from typing import Any

import pytest

# Ensure repository root is on sys.path for direct pytest invocation
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src import config, evidence, twin

pytestmark = pytest.mark.k1


def _read_parquet_table(path: pathlib.Path) -> Any:
    """Helper to read parquet table safely."""
    import pyarrow.parquet as pq

    return pq.read_table(str(path))


def test_p0_2_quad_causal_windows():
    """Assert exactly 4 causal evidence windows: line-A, line-B, line-C, cell."""
    assert hasattr(evidence, "CAUSAL_PARTITIONS"), (
        "evidence module must define CAUSAL_PARTITIONS"
    )
    expected = ("line-A", "line-B", "line-C", "cell")
    assert tuple(evidence.CAUSAL_PARTITIONS) == expected, (
        f"Expected causal partitions {expected}, got {evidence.CAUSAL_PARTITIONS}"
    )
    assert len(evidence.CAUSAL_PARTITIONS) == 4
    assert "rework" not in evidence.CAUSAL_PARTITIONS, (
        "'rework' must not be a causal partition window; it must be remapped to 'cell'"
    )


def test_p0_2_partition_remapping_rework_to_cell():
    """Verify explicit partition remapping: rework -> cell (SIM_SPEC §10 vs twin.py:119)."""
    # 1. Twin router stays frozen and maps RWK0 to 'rework'
    assert twin._partition_of_machine("RWK0") == "rework"

    # 2. Evidence layer remaps 'rework' to 'cell'
    assert hasattr(evidence, "remap_partition"), (
        "evidence module must provide remap_partition function"
    )
    assert evidence.remap_partition("rework") == "cell"
    assert evidence.remap_partition("line-A") == "line-A"
    assert evidence.remap_partition("line-B") == "line-B"
    assert evidence.remap_partition("line-C") == "line-C"
    assert evidence.remap_partition("cell") == "cell"

    # 3. Evidence partition_of_machine helper returns 'cell' for RWK*
    if hasattr(evidence, "partition_of_machine"):
        assert evidence.partition_of_machine("RWK0") == "cell"
        assert evidence.partition_of_machine("A0") == "line-A"
        assert evidence.partition_of_machine("B0") == "line-B"
        assert evidence.partition_of_machine("PKG0") == "line-C"
        assert evidence.partition_of_machine("ASM0") == "cell"


def test_p0_2_rwk0_rows_placed_in_cell_window(tmp_path: pathlib.Path):
    """Dedicated test asserting RWK0 rows are placed inside the 'cell' partition window."""
    out_dir = tmp_path / "evidence_v4"
    evidence.export_evidence(out_dir=out_dir)

    # There must NOT be any separate 'rework' artifact
    assert not (out_dir / "rework.parquet").exists(), (
        "Separate rework.parquet artifact must not exist"
    )
    assert not (out_dir / "evidence_rework.parquet").exists()

    # The 'cell' window must exist and contain RWK0 channels
    cell_file = None
    for candidate in (out_dir / "cell.parquet", out_dir / "evidence_cell.parquet"):
        if candidate.exists():
            cell_file = candidate
            break
    assert cell_file is not None, f"Expected cell parquet file in {out_dir}"

    table = _read_parquet_table(cell_file)
    cols = table.column_names
    rwk_cols = [c for c in cols if "RWK0" in c or "RWK" in c]
    assert len(rwk_cols) > 0, (
        f"Expected RWK0 channels inside cell window, found columns: {cols}"
    )


def test_p0_2_causal_evidence_floor_n_floor(tmp_path: pathlib.Path):
    """Verify N_FLOOR=800 causal evidence floor on every partition window."""
    assert hasattr(evidence, "N_FLOOR"), "evidence module must define N_FLOOR constant"
    assert evidence.N_FLOOR == 800

    out_dir = tmp_path / "evidence_v4"
    evidence.export_evidence(out_dir=out_dir)

    for part in evidence.CAUSAL_PARTITIONS:
        part_file = None
        for cand in (out_dir / f"{part}.parquet", out_dir / f"evidence_{part}.parquet"):
            if cand.exists():
                part_file = cand
                break
        assert part_file is not None, f"Missing partition file for {part}"
        table = _read_parquet_table(part_file)
        assert len(table) >= evidence.N_FLOOR, (
            f"Partition {part} row count {len(table)} below N_FLOOR={evidence.N_FLOOR}"
        )

    # Negative control: generating evidence below N_FLOOR must raise ValueError loudly
    if hasattr(evidence, "validate_evidence_floor"):
        with pytest.raises(ValueError, match=r"(?i)floor|800"):
            evidence.validate_evidence_floor(799)
        with pytest.raises(ValueError, match=r"(?i)floor|800"):
            evidence.validate_evidence_floor(0)


def test_p0_2_full_graph_request_banned_raises_valueerror(tmp_path: pathlib.Path):
    """Full-graph causal evidence is BANNED (O(P^2*tau)) and MUST raise ValueError loudly."""
    out_dir = tmp_path / "evidence_v4"

    for bad_req in ("full", "full-graph", "all", "plant", "full_graph"):
        with pytest.raises(ValueError, match=r"(?i)full-graph|banned|complexity"):
            evidence.export_evidence(out_dir=out_dir, partition=bad_req)

    # Also test full_graph kwarg if supported
    with pytest.raises(ValueError, match=r"(?i)full-graph|banned|complexity"):
        evidence.export_evidence(out_dir=out_dir, full_graph=True)


def test_p0_2_partition_node_count_cap_le_10(tmp_path: pathlib.Path):
    """Verify each causal partition window has node count <= 10."""
    assert hasattr(evidence, "NODE_CAP"), (
        "evidence module must define NODE_CAP constant"
    )
    assert evidence.NODE_CAP == 10

    # Check via machine lookup function if available
    if hasattr(evidence, "get_partition_machines"):
        for part in evidence.CAUSAL_PARTITIONS:
            machines = evidence.get_partition_machines(part)
            assert len(machines) <= evidence.NODE_CAP, (
                f"Partition {part} has {len(machines)} nodes, exceeds cap of {evidence.NODE_CAP}"
            )

    # Check via exported files
    out_dir = tmp_path / "evidence_v4"
    evidence.export_evidence(out_dir=out_dir)
    for part in evidence.CAUSAL_PARTITIONS:
        part_file = None
        for cand in (out_dir / f"{part}.parquet", out_dir / f"evidence_{part}.parquet"):
            if cand.exists():
                part_file = cand
                break
        assert part_file is not None
        table = _read_parquet_table(part_file)
        machines = {
            col.split("_")[1]
            for col in table.column_names
            if "_" in col and col.split("_")[1] in config.MACHINE_INDEX
        }
        if machines:
            assert len(machines) <= evidence.NODE_CAP, (
                f"Partition {part} has {len(machines)} machine columns, exceeds cap of {evidence.NODE_CAP}"
            )

    # Negative control: validating node list > 10 raises ValueError
    if hasattr(evidence, "validate_node_cap"):
        fake_nodes = [f"M{i}" for i in range(11)]
        with pytest.raises(ValueError, match=r"(?i)node.*cap|cap.*exceeded|10"):
            evidence.validate_node_cap(fake_nodes)


def test_p0_2_unknown_partition_rejected(tmp_path: pathlib.Path):
    """Unknown partition names raise ValueError loudly."""
    out_dir = tmp_path / "evidence_v4"
    for bad_part in (
        "invalid-partition",
        "line-Z",
        "plant_99",
        "",
        "unknown",
        "rework",
    ):
        with pytest.raises(ValueError, match=r"(?i)unknown|invalid.*partition"):
            evidence.export_evidence(out_dir=out_dir, partition=bad_part)

        if hasattr(evidence, "get_partition_machines"):
            with pytest.raises(ValueError, match=r"(?i)unknown|invalid.*partition"):
                evidence.get_partition_machines(bad_part)


def test_p0_2_manifest_metadata(tmp_path: pathlib.Path):
    """Per-window manifest containing partition, n_steps >= 800, seeds hash, schema, pyarrow version."""
    out_dir = tmp_path / "evidence_v4"
    res = evidence.export_evidence(out_dir=out_dir)

    manifest_path = out_dir / "manifest.json"
    manifest_data: dict[str, Any] | list[dict[str, Any]]
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    elif isinstance(res, dict) and "manifest" in res:
        manifest_data = res["manifest"]
    else:
        # Check per-window manifest files
        manifest_data = {}
        for part in evidence.CAUSAL_PARTITIONS:
            part_meta_path = out_dir / f"{part}_manifest.json"
            if not part_meta_path.exists():
                part_meta_path = out_dir / f"{part}.manifest.json"
            assert part_meta_path.exists(), f"Expected manifest file for {part}"
            with open(part_meta_path, "r", encoding="utf-8") as f:
                manifest_data[part] = json.load(f)

    # Normalize entries to list of dicts
    entries: list[dict[str, Any]] = []
    if isinstance(manifest_data, dict):
        if "windows" in manifest_data:
            entries = list(manifest_data["windows"])
        elif all(p in manifest_data for p in evidence.CAUSAL_PARTITIONS):
            entries = [manifest_data[p] for p in evidence.CAUSAL_PARTITIONS]
        else:
            entries = [manifest_data]
    elif isinstance(manifest_data, list):
        entries = manifest_data

    assert len(entries) >= 4, (
        f"Expected at least 4 manifest entries, got {len(entries)}"
    )

    partitions_seen = set()
    for entry in entries:
        part = entry.get("partition")
        assert part in evidence.CAUSAL_PARTITIONS, f"Unexpected partition: {part}"
        partitions_seen.add(part)

        n_steps = entry.get("n_steps") or entry.get("row_count") or entry.get("steps")
        assert n_steps is not None, f"Manifest missing n_steps for {part}"
        assert n_steps >= 800, f"Manifest n_steps={n_steps} < 800 for {part}"

        seeds_hash = (
            entry.get("seeds_hash")
            or entry.get("seed_hash")
            or entry.get("seeds_sha256")
        )
        assert (
            seeds_hash is not None
            and isinstance(seeds_hash, str)
            and len(seeds_hash) > 0
        )

        schema_ver = entry.get("schema") or entry.get("schema_version")
        assert schema_ver == config.TWIN_SCHEMA

        import pyarrow as pa

        pa_ver = entry.get("pyarrow_version")
        assert pa_ver == pa.__version__

    assert partitions_seen == set(evidence.CAUSAL_PARTITIONS)


def test_p0_2_cli_execution_contract_and_help(tmp_path: pathlib.Path):
    """CLI execution contract: python -m src.evidence --out <dir> supports argparse and exits 0 on --help."""
    # 1. Test build_parser
    assert hasattr(evidence, "build_parser"), "evidence module must expose build_parser"
    parser = evidence.build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    actions = [a.dest for a in parser._actions]
    assert "out" in actions, "Parser must have --out argument"

    # 2. Test python -m src.evidence --help via subprocess
    cmd = [sys.executable, "-m", "src.evidence", "--help"]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(_REPO_ROOT), check=False
    )
    assert proc.returncode == 0, (
        f"CLI --help exited with {proc.returncode}: {proc.stderr}"
    )
    assert "--out" in proc.stdout

    # 3. Test running main with --out
    out_dir = tmp_path / "cli_evidence_out"
    assert hasattr(evidence, "main"), "evidence module must expose main entrypoint"
    ret = evidence.main(["--out", str(out_dir)])
    assert ret == 0, f"CLI main returned non-zero code {ret}"
    assert out_dir.exists(), "CLI main must create output directory"


def test_p0_2_raw_channels_only_no_aggregates(tmp_path: pathlib.Path):
    """Exported windows must contain only raw channels, NO multi-scale aggregates (PR-29 lane)."""
    out_dir = tmp_path / "evidence_v4"
    evidence.export_evidence(out_dir=out_dir)

    banned_prefixes = ("mean_", "rms_", "envelope_", "std_", "rolling_", "agg_")
    for part in evidence.CAUSAL_PARTITIONS:
        part_file = None
        for cand in (out_dir / f"{part}.parquet", out_dir / f"evidence_{part}.parquet"):
            if cand.exists():
                part_file = cand
                break
        assert part_file is not None
        table = _read_parquet_table(part_file)
        for col in table.column_names:
            for b in banned_prefixes:
                assert not col.startswith(b), (
                    f"Aggregate feature '{col}' found in raw evidence window for {part}. "
                    "Multi-scale aggregates are owned by PRISSUE-29."
                )


def test_p0_2_no_tigramite_dependency():
    """Verify that src.evidence does NOT import or depend on tigramite."""
    assert "tigramite" not in sys.modules, (
        "tigramite must not be loaded into sys.modules"
    )

    evidence_path = _REPO_ROOT / "src" / "evidence.py"
    if evidence_path.exists():
        tree = ast.parse(evidence_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "tigramite" not in alias.name, (
                        "Found banned 'tigramite' import"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "tigramite" not in mod, (
                    "Found banned 'tigramite' import from module"
                )


def test_p0_2_twin_router_and_partitions_remain_unchanged():
    """Twin router and _PARTITIONS must remain frozen (5 partitions, RWK* -> 'rework')."""
    assert twin._PARTITIONS == ("line-A", "line-B", "line-C", "cell", "rework")
    assert len(twin._PARTITIONS) == 5
    assert twin._partition_of_machine("RWK0") == "rework"
