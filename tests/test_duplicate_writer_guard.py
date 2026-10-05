"""Duplicate-writer CI guard and M0.2f coordination boundary test (Todo 10).

Normative requirements:
1. AST / inspection-based guard checking all writers to dataset/twin record output.
2. Fails if any key in the M0.2e owned-field list is written by any module outside
   designated owners (canonical writers: src/twin.py and src/dataset_export.py).
3. Enforces M0.2f coordination boundary: verifies that M0.2e does NOT implement
   M0.2f owned fields (multi-scale aggregates 0.5/1.0/2.0s windows and envelope statistics).
4. Structural AST analysis: must NOT rely on naive grep (comments, docstrings,
   and string literals must not cause false positives; structural AST writes must be caught).
5. Negative control tests:
   - Unauthorized module writing an owned field -> MUST fail loudly.
   - Multiple writers to the same owned field in the same output tier -> MUST fail loudly.
   - Unauthorized implementation of M0.2f fields -> MUST fail loudly.
   - Green on clean tree, red on faulty fixtures.
"""

from __future__ import annotations

import ast
import pathlib
import textwrap
from dataclasses import dataclass
from typing import Any

import pytest

pytestmark = pytest.mark.k1

# M0.2e owned stratification fields (Todo 10 contract lock).
M0_2E_OWNED_FIELDS = frozenset(
    {
        "episode_id",
        "wear_endpoint",
        "maint_flag",
        "family",
        "mode",
        "root_id",
        "hop",
        "root_ids",
        "sensor_vs_process",
        "warmup_steps",
        "state_histograms",
        "funnel_census",
    }
)

# Structural aliases/variants recognized under M0.2e ownership.
M0_2E_ALIAS_FIELDS = frozenset(
    {
        "state_histogram",
        "machine_histograms",
        "per_machine_histogram",
        "plant_state_rollup",
        "plant_rollup",
        "warmup_flag",
    }
)

M0_2E_ALL_FIELDS = frozenset(M0_2E_OWNED_FIELDS | M0_2E_ALIAS_FIELDS)

# M0.2f owned fields (MINIPRO-29, M0.2f Trainable Rework) - M0.2e MUST NOT implement these!
M0_2F_OWNED_FIELDS = frozenset(
    {
        "envelope_max",
        "envelope_min",
        "envelope_mean",
        "envelope_std",
        "envelope_band_energy",
        "episode_id_ref",
        "t_start",
        "t_end",
        "B_i",
        "scale_status",
        "scale_cover",
        "envelope_definition_id",
        "rollup_0_5s",
        "rollup_1_0s",
        "rollup_2_0s",
        "window_0_5s",
        "window_1_0s",
        "window_2_0s",
        "agg_0_5s",
        "agg_1_0s",
        "agg_2_0s",
        "multiscale_aggregates",
    }
)

# Designated canonical writers for M0.2e fields in production code.
DESIGNATED_OWNERS: dict[str, set[str]] = {
    # Module relative path -> allowed scopes/functions
    "src/twin.py": {"run_episode"},
    "src/dataset_export.py": {"export", "build_window_config"},
}

# Designated canonical writers for M0.2f fields in production code (MINIPRO-29).
DESIGNATED_M0_2F_OWNERS: dict[str, set[str]] = {
    "src/window_export.py": {
        "envelope_features",
        "rolling_features_for_channel",
        "export_multiscale",
        "export_cover",
        "derive_base_window",
        "rolling_bank",
        "build_m0_2f_window_config_section",
        "run_m0_2f_export",
    },
    "src/dataset_export.py": {
        "build_window_config",
    },
    "src/train_pipeline.py": {
        "build_windows",
    },
}


class DuplicateWriterGuardError(AssertionError):
    """Raised when an unauthorized or duplicate writer is detected."""


@dataclass(frozen=True)
class FieldWrite:
    """Record of an AST-detected field write operation."""

    field: str
    file_path: str
    lineno: int
    col_offset: int
    scope: str
    kind: str  # "dict_literal", "subscript_assign", "call_kwarg"


class StructuralWriterVisitor(ast.NodeVisitor):
    """AST visitor extracting structural dictionary writes, assignments, and updates."""

    def __init__(
        self, rel_path: str, checked_fields: set[str] | frozenset[str]
    ) -> None:
        self.rel_path = rel_path
        self.checked_fields = checked_fields
        self.scope_stack: list[str] = ["<module>"]
        self.writes: list[FieldWrite] = []
        self.dict_key_counts: dict[int, dict[str, int]] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Dict(self, node: ast.Dict) -> None:
        current_scope = self.scope_stack[-1]
        line = getattr(node, "lineno", 0)
        seen_keys_in_literal: list[str] = []

        for key_node in node.keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                key = key_node.value
                seen_keys_in_literal.append(key)
                if key in self.checked_fields:
                    self.writes.append(
                        FieldWrite(
                            field=key,
                            file_path=self.rel_path,
                            lineno=getattr(key_node, "lineno", line),
                            col_offset=getattr(key_node, "col_offset", 0),
                            scope=current_scope,
                            kind="dict_literal",
                        )
                    )

        # Check for literal duplicate keys within the same dictionary
        counts: dict[str, int] = {}
        for k in seen_keys_in_literal:
            if k in self.checked_fields:
                counts[k] = counts.get(k, 0) + 1
        self.dict_key_counts[line] = counts

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        current_scope = self.scope_stack[-1]
        line = getattr(node, "lineno", 0)
        for target in node.targets:
            if isinstance(target, ast.Subscript) and isinstance(
                target.slice, ast.Constant
            ):
                key = target.slice.value
                if isinstance(key, str) and key in self.checked_fields:
                    self.writes.append(
                        FieldWrite(
                            field=key,
                            file_path=self.rel_path,
                            lineno=line,
                            col_offset=getattr(target, "col_offset", 0),
                            scope=current_scope,
                            kind="subscript_assign",
                        )
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        current_scope = self.scope_stack[-1]
        line = getattr(node, "lineno", 0)
        if isinstance(node.target, ast.Subscript) and isinstance(
            node.target.slice, ast.Constant
        ):
            key = node.target.slice.value
            if isinstance(key, str) and key in self.checked_fields:
                self.writes.append(
                    FieldWrite(
                        field=key,
                        file_path=self.rel_path,
                        lineno=line,
                        col_offset=getattr(node.target, "col_offset", 0),
                        scope=current_scope,
                        kind="subscript_assign",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        current_scope = self.scope_stack[-1]
        line = getattr(node, "lineno", 0)
        # Check dict(key=value, ...) calls
        if isinstance(node.func, ast.Name) and node.func.id == "dict":
            for kw in node.keywords:
                if kw.arg and kw.arg in self.checked_fields:
                    self.writes.append(
                        FieldWrite(
                            field=kw.arg,
                            file_path=self.rel_path,
                            lineno=line,
                            col_offset=getattr(kw, "col_offset", 0),
                            scope=current_scope,
                            kind="call_kwarg",
                        )
                    )
        # Check rec.update(key=val) or rec.setdefault("key", val)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in {
            "update",
            "setdefault",
        }:
            for kw in node.keywords:
                if kw.arg and kw.arg in self.checked_fields:
                    self.writes.append(
                        FieldWrite(
                            field=kw.arg,
                            file_path=self.rel_path,
                            lineno=line,
                            col_offset=getattr(kw, "col_offset", 0),
                            scope=current_scope,
                            kind="call_kwarg",
                        )
                    )
            if node.func.attr == "setdefault" and node.args:
                arg0 = node.args[0]
                if (
                    isinstance(arg0, ast.Constant)
                    and isinstance(arg0.value, str)
                    and arg0.value in self.checked_fields
                ):
                    self.writes.append(
                        FieldWrite(
                            field=arg0.value,
                            file_path=self.rel_path,
                            lineno=line,
                            col_offset=getattr(arg0, "col_offset", 0),
                            scope=current_scope,
                            kind="call_kwarg",
                        )
                    )
        self.generic_visit(node)


def scan_writers(
    root_dir: pathlib.Path,
    checked_fields: set[str] | frozenset[str],
) -> tuple[list[FieldWrite], dict[str, dict[int, dict[str, int]]]]:
    """Scan all Python files under root_dir for structural field writes."""
    all_writes: list[FieldWrite] = []
    all_dict_counts: dict[str, dict[int, dict[str, int]]] = {}

    for py_path in sorted(root_dir.rglob("*.py")):
        # Skip pycache or hidden directories
        if "__pycache__" in py_path.parts or any(
            p.startswith(".") for p in py_path.parts
        ):
            continue
        try:
            rel_str = py_path.relative_to(
                root_dir.parent if root_dir.name == "src" else root_dir
            ).as_posix()
        except ValueError:
            rel_str = py_path.as_posix()
        content = py_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_path))
        visitor = StructuralWriterVisitor(rel_str, checked_fields)
        visitor.visit(tree)
        all_writes.extend(visitor.writes)
        all_dict_counts[rel_str] = visitor.dict_key_counts

    return all_writes, all_dict_counts


def validate_duplicate_and_unauthorized_writers(
    target_dir: pathlib.Path,
    allowed_owners: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Validate that M0.2e fields are written ONLY by designated owners and not duplicated.

    Raises DuplicateWriterGuardError on any violation.
    """
    if allowed_owners is None:
        allowed_owners = DESIGNATED_OWNERS

    all_target_fields = set(M0_2E_ALL_FIELDS | M0_2F_OWNED_FIELDS)
    writes, dict_counts = scan_writers(target_dir, all_target_fields)

    unauthorized_writes: list[FieldWrite] = []
    m0_2f_boundary_violations: list[FieldWrite] = []
    # Key -> list of writes grouped by scope
    writes_by_field_and_scope: dict[str, list[FieldWrite]] = {}

    for w in writes:
        # Check M0.2f boundary prohibition: only designated M0.2f owners may write M0.2f fields
        if w.field in M0_2F_OWNED_FIELDS:
            allowed_m0_2f = DESIGNATED_M0_2F_OWNERS.get(w.file_path)
            if allowed_m0_2f is None or w.scope not in allowed_m0_2f:
                m0_2f_boundary_violations.append(w)
            continue

        # Check authorized modules and scopes
        allowed_scopes = allowed_owners.get(w.file_path)
        if allowed_scopes is None:
            # File is completely unauthorized to write M0.2e fields
            unauthorized_writes.append(w)
        elif w.scope not in allowed_scopes:
            # Function within file is unauthorized
            unauthorized_writes.append(w)

        # Track writes per field
        key_group = f"{w.file_path}::{w.scope}::{w.field}"
        writes_by_field_and_scope.setdefault(key_group, []).append(w)

    # Check for duplicate writes within the same function scope
    duplicate_scope_writes: list[tuple[str, list[FieldWrite]]] = []
    for key_group, group_writes in writes_by_field_and_scope.items():
        if len(group_writes) > 1:
            duplicate_scope_writes.append((key_group, group_writes))

    # Check for duplicate keys in same dict literal
    dict_duplicate_violations: list[tuple[str, int, str, int]] = []
    for rel_file, lines in dict_counts.items():
        for line, kcounts in lines.items():
            for k, count in kcounts.items():
                if count > 1:
                    dict_duplicate_violations.append((rel_file, line, k, count))

    # Assemble diagnostics and raise if any violation
    errors: list[str] = []

    if m0_2f_boundary_violations:
        lines = [
            f"  - {w.file_path}:{w.lineno} in {w.scope}() writes M0.2f field '{w.field}'"
            for w in m0_2f_boundary_violations
        ]
        errors.append(
            "M0.2f Boundary Violation: M0.2e MUST NOT implement M0.2f aggregates or envelopes!\n"
            + "\n".join(lines)
        )

    if unauthorized_writes:
        lines = [
            f"  - {w.file_path}:{w.lineno} in {w.scope}() writes owned field '{w.field}'"
            for w in unauthorized_writes
        ]
        errors.append(
            "Unauthorized Writer Violation: only designated owners may write M0.2e fields.\n"
            + f"Allowed owners: {allowed_owners}\n"
            + "\n".join(lines)
        )

    if duplicate_scope_writes:
        lines = [
            f"  - {kg}: {len(gw)} writes at lines {[w.lineno for w in gw]}"
            for kg, gw in duplicate_scope_writes
        ]
        errors.append(
            "Duplicate Writer Violation: multiple writes to the same owned field in scope.\n"
            + "\n".join(lines)
        )

    if dict_duplicate_violations:
        lines = [
            f"  - {f}:{l} key '{k}' duplicated {c} times in same dict"
            for f, l, k, c in dict_duplicate_violations
        ]
        errors.append(
            "Duplicate Key Violation: repeated key in dictionary literal.\n"
            + "\n".join(lines)
        )

    if errors:
        raise DuplicateWriterGuardError("\n\n".join(errors))

    return {
        "total_writes": len(writes),
        "writes": writes,
        "m0_2e_fields_found": sorted({w.field for w in writes}),
    }


# ==============================================================================
# PYTEST TEST SUITE
# ==============================================================================


@pytest.mark.k1
def test_clean_tree_designated_owners_only() -> None:
    """Verify that in the clean production tree (src/), ONLY designated owners write M0.2e fields."""
    repo_src = pathlib.Path("src").resolve()
    assert repo_src.is_dir(), f"src directory not found at {repo_src}"

    result = validate_duplicate_and_unauthorized_writers(repo_src)

    # Verify that all 12 canonical M0.2e fields are present and accounted for
    found_fields = set(result["m0_2e_fields_found"])
    missing_canonical = M0_2E_OWNED_FIELDS - found_fields
    assert not missing_canonical, (
        f"Canonical M0.2e fields missing from writers: {missing_canonical}"
    )

    # Verify that writes were performed ONLY by designated owners
    for w in result["writes"]:
        if w.field in M0_2F_OWNED_FIELDS:
            assert w.file_path in DESIGNATED_M0_2F_OWNERS, (
                f"Unexpected M0.2f writer file: {w.file_path}"
            )
            assert w.scope in DESIGNATED_M0_2F_OWNERS[w.file_path], (
                f"Unexpected M0.2f writer scope in {w.file_path}: {w.scope}"
            )
        else:
            assert w.file_path in DESIGNATED_OWNERS, (
                f"Unexpected writer file: {w.file_path}"
            )
            assert w.scope in DESIGNATED_OWNERS[w.file_path], (
                f"Unexpected writer scope in {w.file_path}: {w.scope}"
            )


@pytest.mark.k1
def test_clean_tree_no_m0_2f_aggregates() -> None:
    """Verify that M0.2e canonical modules (twin.py, dataset_export.py) do NOT implement M0.2f fields."""
    repo_src = pathlib.Path("src").resolve()
    writes, _ = scan_writers(repo_src, M0_2F_OWNED_FIELDS)
    unauthorized = [
        w
        for w in writes
        if w.file_path not in DESIGNATED_M0_2F_OWNERS
        or w.scope not in DESIGNATED_M0_2F_OWNERS[w.file_path]
    ]
    assert not unauthorized, (
        f"M0.2e violated boundary by implementing M0.2f owned fields: "
        f"{[(w.file_path, w.lineno, w.field) for w in unauthorized]}"
    )


def test_negative_control_unauthorized_module(tmp_path: pathlib.Path) -> None:
    """Negative control: an unauthorized module writing an M0.2e field MUST fail loudly."""
    test_src = tmp_path / "src"
    test_src.mkdir()

    # Create an unauthorized module writing to wear_endpoint
    unauth_file = test_src / "unauthorized_service.py"
    unauth_file.write_text(
        textwrap.dedent("""
        def handle_telemetry(data):
            # Unauthorized write to owned stratification key
            data["wear_endpoint"] = 0.88
            return data
        """),
        encoding="utf-8",
    )

    with pytest.raises(DuplicateWriterGuardError) as exc_info:
        validate_duplicate_and_unauthorized_writers(test_src)

    assert "Unauthorized Writer Violation" in str(exc_info.value)
    assert "unauthorized_service.py" in str(exc_info.value)
    assert "wear_endpoint" in str(exc_info.value)


def test_negative_control_unauthorized_scope_in_owner(tmp_path: pathlib.Path) -> None:
    """Negative control: an unauthorized function inside twin.py writing an owned field MUST fail."""
    test_src = tmp_path / "src"
    test_src.mkdir()

    twin_file = test_src / "twin.py"
    twin_file.write_text(
        textwrap.dedent("""
        def helper_scratchpad():
            # Rogue write outside run_episode
            return {"funnel_census": {"kits_completed": 10}}

        def run_episode():
            return {"strat": {"funnel_census": {}}}
        """),
        encoding="utf-8",
    )

    with pytest.raises(DuplicateWriterGuardError) as exc_info:
        validate_duplicate_and_unauthorized_writers(
            test_src,
            allowed_owners={"twin.py": {"run_episode"}},
        )

    assert "Unauthorized Writer Violation" in str(exc_info.value)
    assert "helper_scratchpad" in str(exc_info.value)


def test_negative_control_duplicate_writers_in_same_scope(
    tmp_path: pathlib.Path,
) -> None:
    """Negative control: multiple writes to the same owned field in the same function MUST fail."""
    test_src = tmp_path / "src"
    test_src.mkdir()

    export_file = test_src / "dataset_export.py"
    export_file.write_text(
        textwrap.dedent("""
        def export():
            row = {"episode_id": 1}
            # Duplicate secondary write to episode_id
            row["episode_id"] = 2
            return row
        """),
        encoding="utf-8",
    )

    with pytest.raises(DuplicateWriterGuardError) as exc_info:
        validate_duplicate_and_unauthorized_writers(
            test_src,
            allowed_owners={"dataset_export.py": {"export"}},
        )

    assert "Duplicate Writer Violation" in str(exc_info.value)
    assert "episode_id" in str(exc_info.value)


def test_negative_control_duplicate_dict_key(tmp_path: pathlib.Path) -> None:
    """Negative control: literal duplicate key in dictionary literal MUST fail."""
    test_src = tmp_path / "src"
    test_src.mkdir()

    export_file = test_src / "dataset_export.py"
    export_file.write_text(
        textwrap.dedent("""
        def export():
            # Duplicate key in literal
            return {
                "episode_id": 10,
                "wear_endpoint": 0.5,
                "episode_id": 20,
            }
        """),
        encoding="utf-8",
    )

    with pytest.raises(DuplicateWriterGuardError) as exc_info:
        validate_duplicate_and_unauthorized_writers(
            test_src,
            allowed_owners={"dataset_export.py": {"export"}},
        )

    assert "Duplicate Key Violation" in str(exc_info.value)
    assert "episode_id" in str(exc_info.value)


def test_negative_control_m0_2f_aggregate_leakage(tmp_path: pathlib.Path) -> None:
    """Negative control: implementing M0.2f aggregates in M0.2e MUST fail loudly."""
    test_src = tmp_path / "src"
    test_src.mkdir()

    leak_file = test_src / "dataset_export.py"
    leak_file.write_text(
        textwrap.dedent("""
        def export():
            # Premature M0.2f aggregate implementation
            return {
                "envelope_max": 99.9,
                "rollup_0_5s": 12.3,
            }
        """),
        encoding="utf-8",
    )

    with pytest.raises(DuplicateWriterGuardError) as exc_info:
        validate_duplicate_and_unauthorized_writers(
            test_src,
            allowed_owners={"dataset_export.py": {"export"}},
        )

    assert "M0.2f Boundary Violation" in str(exc_info.value)
    assert "envelope_max" in str(exc_info.value)
    assert "rollup_0_5s" in str(exc_info.value)


def test_structural_ast_vs_naive_grep(tmp_path: pathlib.Path) -> None:
    """Verify that structural AST inspection ignores comments/docstrings but catches AST writes."""
    test_src = tmp_path / "src"
    test_src.mkdir()

    doc_file = test_src / "documentation_only.py"
    # This file mentions owned fields in docstring and comment ONLY
    doc_file.write_text(
        textwrap.dedent("""
        '''
        Documentation module mentioning owned fields:
        - wear_endpoint
        - episode_id
        - maint_flag
        - funnel_census
        '''

        # wear_endpoint = 0.5 (commented out)
        # data["episode_id"] = 100 (commented out)

        def print_info():
            msg = "This string mentions wear_endpoint and funnel_census safely"
            return msg
        """),
        encoding="utf-8",
    )

    # 1. Structural check passes cleanly with zero violations!
    result = validate_duplicate_and_unauthorized_writers(test_src, allowed_owners={})
    assert result["total_writes"] == 0, (
        "Comments/docstrings must not count as AST writes"
    )

    # 2. Add an actual AST write -> immediately caught
    doc_file.write_text(
        doc_file.read_text(encoding="utf-8")
        + "\ndef bad_writer():\n    return {'wear_endpoint': 1.0}\n",
        encoding="utf-8",
    )

    with pytest.raises(DuplicateWriterGuardError) as exc_info:
        validate_duplicate_and_unauthorized_writers(test_src, allowed_owners={})
    assert "Unauthorized Writer Violation" in str(exc_info.value)
    assert "wear_endpoint" in str(exc_info.value)
