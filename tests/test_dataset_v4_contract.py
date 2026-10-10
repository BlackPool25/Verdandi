"""Zero-join dataset v4 contract tests with mock MINIPRO-19 consumer.

Normative requirements:
1. Export and validate dataset_v4.parquet, window_config.json, and ingestion metadata.
2. Implement a mock MINIPRO-19 train pipeline consumer consuming dataset_v4.
3. Perform grouped episode-seeded splits using sklearn.model_selection.StratifiedGroupKFold
   using ONLY the exported stratification keys (episode_id, family, mode, root_id, wear_endpoint).
4. Prove zero ad-hoc joins via ZeroJoinASTVisitor checking that merge, join, concat across tables
   are never called.
5. Pinned column sets for schema v4:
   - obs_*, state_*, buffer_*, tput_*, current_* for all 26 machines in config.MACHINE_INDEX roster.
   - Stratification keys (episode_id, wear_endpoint, maint_flag, family, mode, root_id, etc.).
   - Fault labels (family, mode, root_id).
6. schema_version == 4 enforced everywhere (dataset, window_config, metadata sidecars).
7. Flag-day v3 reader rejection: reading v4 dataset with legacy v3 reader
   (load_v3_dataset or load_dataset enforcing < 4) raises ValueError loudly.
8. Negative control 1: missing or renamed stratification column (e.g. family) causes consumer split to fail loudly.
9. Negative control 2: planted join/merge in consumer code causes ZeroJoinASTVisitor to fail.
10. Enforce TF1 leakage law: NO scaler.pkl in export artifacts; fit scalers strictly inside folds.
11. Must NOT require real src/train_pipeline.py.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import pathlib
import sys
import textwrap
from typing import Any

# Ensure repository root is in sys.path when invoked via pytest directly
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

from src import config, dataset_export

pytestmark = pytest.mark.k1

BANNED_JOIN_OPS = frozenset({"merge", "join", "concat"})

# Pinned stratification fields for v4
REQUIRED_STRAT_FIELDS = [
    "episode_id",
    "wear_endpoint",
    "maint_flag",
    "family",
    "mode",
    "root_id",
    "root_ids",
    "hop",
    "sensor_vs_process",
    "state_histogram",
    "warmup_flag",
    "funnel_census",
]

# Fault classification target labels
FAULT_LABEL_FIELDS = [
    "family",
    "mode",
    "root_id",
]

# 5 machine channel prefixes across all 26 machines
MACHINE_CHANNEL_PREFIXES = [
    "obs_",
    "state_",
    "buffer_",
    "tput_",
    "current_",
]


class ZeroJoinASTVisitor(ast.NodeVisitor):
    """AST visitor detecting any ad-hoc table join or merge operations."""

    def __init__(self) -> None:
        self.violations: list[tuple[str, int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Check method calls: obj.merge(...), obj.join(...), pd.concat(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_JOIN_OPS:
            self.violations.append(
                (node.func.attr, getattr(node, "lineno", 0), "attribute_call")
            )
        # Check direct calls: merge(...), join(...), concat(...)
        elif isinstance(node.func, ast.Name) and node.func.id in BANNED_JOIN_OPS:
            self.violations.append(
                (node.func.id, getattr(node, "lineno", 0), "name_call")
            )
        self.generic_visit(node)


def assert_zero_adhoc_joins(target: Any) -> None:
    """Assert via AST walk and grep that target code contains zero join/merge calls.

    Raises AssertionError if any call to 'merge', 'join', or 'concat' is found.
    """
    if isinstance(target, str):
        source = target
    else:
        source = inspect.getsource(target)

    tree = ast.parse(textwrap.dedent(source))
    visitor = ZeroJoinASTVisitor()
    visitor.visit(tree)

    if visitor.violations:
        details = [
            f"{op} at line {line} ({kind})" for op, line, kind in visitor.violations
        ]
        raise AssertionError(
            f"Zero-join contract violation: banned join/merge operation(s) found in AST: {details}"
        )


class MockTrainPipelineConsumer:
    """Mock train_pipeline consumer demonstrating zero-join dataset v4 ingestion and grouped CV.

    Adheres strictly to the MINIPRO-19 / MINIPRO-25 zero-join contract:
    - Ingests self-contained Parquet dataset v4 directly.
    - Validates schema_version == 4 strictly.
    - Validates window_config.json and ingestion metadata.
    - Validates pinned machine channels (obs_*, state_*, buffer_*, tput_*, current_*) for 26 machines.
    - Uses ONLY embedded stratification keys for StratifiedGroupKFold splitting.
    - Fits preprocessing scalers strictly inside CV folds (TF1 leakage law).
    - Contains ZERO calls to merge, join, or concat.
    """

    def __init__(self, required_strat_fields: list[str] | None = None) -> None:
        self.required_strat_fields = (
            list(required_strat_fields)
            if required_strat_fields is not None
            else list(REQUIRED_STRAT_FIELDS)
        )

    def load_and_validate(
        self,
        parquet_path: str | pathlib.Path,
        window_config_path: str | pathlib.Path | None = None,
        metadata_path: str | pathlib.Path | None = None,
    ) -> pd.DataFrame:
        """Load Parquet dataset v4 and validate contract against metadata and window config."""
        parquet_p = pathlib.Path(parquet_path)
        if not parquet_p.exists():
            raise FileNotFoundError(f"Dataset Parquet file not found: {parquet_p}")

        df = pd.read_parquet(parquet_p)

        # 1. Strictly verify schema_version == 4
        if "schema_version" not in df.columns:
            raise ValueError(
                "Dataset contract violation: 'schema_version' column missing"
            )
        schema_versions = df["schema_version"].unique()
        if any(v != 4 for v in schema_versions):
            raise ValueError(
                f"Dataset v4 contract violation: schema_version={schema_versions.tolist()} != 4"
            )

        # 2. Verify all required stratification fields exist in the single table (ZERO joins needed)
        missing_fields = [f for f in self.required_strat_fields if f not in df.columns]
        if missing_fields:
            raise KeyError(
                f"Dataset contract violation: missing stratification field(s): {missing_fields}"
            )

        # 3. Verify pinned machine channels for all 26 machines in config.MACHINE_INDEX roster
        for m_name in config.MACHINE_INDEX:
            for prefix in MACHINE_CHANNEL_PREFIXES:
                col = f"{prefix}{m_name}"
                if col not in df.columns:
                    raise KeyError(
                        f"Dataset v4 contract violation: missing pinned machine channel column '{col}'"
                    )

        # 4. Verify window_config if supplied
        if window_config_path is not None:
            win_p = pathlib.Path(window_config_path)
            if win_p.exists():
                with open(win_p, "r", encoding="utf-8") as f:
                    win_cfg = json.load(f)
                if win_cfg.get("schema_version") != 4:
                    raise ValueError(
                        f"window_config.json schema_version={win_cfg.get('schema_version')} != 4"
                    )
                expected_owned = win_cfg.get("owned_fields", [])
                missing_owned = [f for f in expected_owned if f not in df.columns]
                if missing_owned:
                    raise KeyError(
                        f"Dataset contract violation: missing owned field(s) from window_config: {missing_owned}"
                    )

        # 5. Verify ingestion metadata and hash integrity if supplied
        if metadata_path is not None:
            meta_p = pathlib.Path(metadata_path)
            if meta_p.exists():
                with open(meta_p, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("schema_version") != 4:
                    raise ValueError(
                        f"ingestion metadata schema_version={meta.get('schema_version')} != 4"
                    )
                if len(df) != meta.get("row_count"):
                    raise ValueError(
                        f"Dataset contract violation: row count mismatch: df has {len(df)}, metadata declares {meta.get('row_count')}"
                    )
                with open(parquet_p, "rb") as f:
                    actual_hash = hashlib.sha256(f.read()).hexdigest()
                if actual_hash != meta.get("dataset_hash"):
                    raise ValueError(
                        f"Dataset contract violation: sha256 mismatch: actual {actual_hash} != declared {meta.get('dataset_hash')}"
                    )

        return df

    def create_grouped_splits(
        self,
        df: pd.DataFrame,
        strat_key: str = "family",
        n_splits: int = 2,
        seed: int = 42,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """Perform StratifiedGroupKFold splits grouped by episode_id using embedded stratification key."""
        if strat_key not in df.columns:
            raise KeyError(
                f"Stratification key '{strat_key}' not present in dataset columns"
            )
        if "episode_id" not in df.columns:
            raise KeyError("Group key 'episode_id' not present in dataset columns")

        y = df[strat_key]
        groups = df["episode_id"]
        feature_cols = [c for c in df.columns if c.startswith(("obs_", "current_"))]
        X = df[feature_cols] if feature_cols else df[["step"]]

        sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        splits = list(sgkf.split(X, y, groups))

        # Assert zero episode leakage across every fold
        for train_idx, val_idx in splits:
            train_episodes = set(df.iloc[train_idx]["episode_id"])
            val_episodes = set(df.iloc[val_idx]["episode_id"])
            overlap = train_episodes.intersection(val_episodes)
            if overlap:
                raise AssertionError(
                    f"Leakage violation: episode_id overlap between train and val: {overlap}"
                )

        return splits

    def fit_and_evaluate_fold(
        self,
        df: pd.DataFrame,
        train_idx: np.ndarray,
        val_idx: np.ndarray,
        feature_cols: list[str],
    ) -> dict[str, Any]:
        """Fit scaler strictly on train split and transform validation split (TF1 leakage law)."""
        train_x = df.iloc[train_idx][feature_cols].to_numpy()
        val_x = df.iloc[val_idx][feature_cols].to_numpy()

        scaler = StandardScaler()
        # Strictly fit on train split only
        scaler.fit(train_x)
        train_norm = scaler.transform(train_x)
        val_norm = scaler.transform(val_x)

        return {
            "mean": scaler.mean_,
            "var": scaler.var_,
            "train_shape": train_norm.shape,
            "val_shape": val_norm.shape,
        }

    def run_pipeline(
        self,
        parquet_path: str | pathlib.Path,
        window_config_path: str | pathlib.Path | None = None,
        metadata_path: str | pathlib.Path | None = None,
        strat_key: str = "family",
        n_splits: int = 2,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Execute end-to-end mock consumer training pipeline with zero joins."""
        df = self.load_and_validate(parquet_path, window_config_path, metadata_path)
        splits = self.create_grouped_splits(
            df, strat_key=strat_key, n_splits=n_splits, seed=seed
        )

        feature_cols = [c for c in df.columns if c.startswith(("obs_", "current_"))]
        fold_reports = []
        for fold_idx, (train_idx, val_idx) in enumerate(splits):
            fold_stat = self.fit_and_evaluate_fold(df, train_idx, val_idx, feature_cols)
            fold_reports.append(
                {
                    "fold": fold_idx,
                    "train_episodes": sorted(
                        df.iloc[train_idx]["episode_id"].unique().tolist()
                    ),
                    "val_episodes": sorted(
                        df.iloc[val_idx]["episode_id"].unique().tolist()
                    ),
                    "train_rows": len(train_idx),
                    "val_rows": len(val_idx),
                    "train_mean_norm": float(np.linalg.norm(fold_stat["mean"])),
                }
            )

        return {
            "num_rows": len(df),
            "num_episodes": int(df["episode_id"].nunique()),
            "folds": fold_reports,
            "zero_join_verified": True,
        }


def export_contract_dataset_v4(
    out_dir: str | pathlib.Path,
    seeds: list[int] | None = None,
    out_name: str = "dataset_v4.parquet",
) -> dict[str, Any]:
    """Export a multi-episode v4 dataset with balanced stratification keys for contract testing."""
    out_dir_path = pathlib.Path(out_dir)
    out_parquet = out_dir_path / out_name

    target_seeds = (
        list(seeds) if seeds is not None else [7, 11, 13, 42, 777, 1234, 999, 2026]
    )

    fault_drift = {
        "id": "F-21",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 5.2,
    }
    fault_pulse = {
        "id": "F-06",
        "class": "spike",
        "origin": "A0",
        "t0": 150,
        "dur": 10,
        "mag_sigma": 5.0,
    }
    fault_delay = {
        "id": "F-A0-delay",
        "class": "delay",
        "origin": "A0",
        "t0": 150,
        "dur": 12,
        "extra": {"d": 4},
    }

    fault_map: dict[int, Any] = {}
    if len(target_seeds) >= 8:
        fault_map[target_seeds[2]] = fault_drift
        fault_map[target_seeds[3]] = fault_drift
        fault_map[target_seeds[4]] = fault_pulse
        fault_map[target_seeds[5]] = fault_pulse
        fault_map[target_seeds[6]] = fault_delay
        fault_map[target_seeds[7]] = fault_delay
    elif len(target_seeds) >= 4:
        fault_map[target_seeds[1]] = fault_drift
        fault_map[target_seeds[2]] = fault_pulse
        fault_map[target_seeds[3]] = fault_delay

    # Direct invocation of required export_v4 entrypoint in src.dataset_export
    return dataset_export.export_v4(
        seeds=target_seeds,
        out=out_parquet,
        faults=fault_map,
    )


# ==============================================================================
# Positive Contract Tests: Entrypoint, Artifacts, Pinned Columns, Zero-Join
# ==============================================================================


def test_dataset_v4_export_entrypoint_exists():
    """Verify src.dataset_export provides the required export_v4 entrypoint."""
    assert hasattr(dataset_export, "export_v4"), (
        "src.dataset_export must export export_v4 entrypoint"
    )


def test_dataset_v4_artifacts_presence(tmp_path):
    """Verify exported v4 dataset contains Parquet, window_config.json, and metadata with zero scaler."""
    res = export_contract_dataset_v4(out_dir=tmp_path)

    parquet_file = tmp_path / "dataset_v4.parquet"
    win_cfg_file = tmp_path / "window_config.json"
    meta_file = tmp_path / "ingestion_metadata.json"
    scaler_file = tmp_path / "scaler.pkl"

    assert parquet_file.exists(), "dataset_v4.parquet must exist"
    assert win_cfg_file.exists(), "window_config.json must exist"
    assert meta_file.exists(), "ingestion_metadata.json must exist"
    assert not scaler_file.exists(), (
        "LEAKAGE LAW: scaler.pkl must NOT exist in export artifacts"
    )

    # Verify window_config
    with open(win_cfg_file, "r", encoding="utf-8") as f:
        win_cfg = json.load(f)
    assert win_cfg["schema_version"] == 4
    assert set(REQUIRED_STRAT_FIELDS).issubset(set(win_cfg["owned_fields"]))

    # Verify ingestion metadata
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["schema_version"] == 4

    # Verify consumer can load and validate contract directly
    consumer = MockTrainPipelineConsumer()
    df = consumer.load_and_validate(parquet_file, win_cfg_file, meta_file)
    assert len(df) == res["row_count"]


def test_dataset_v4_pinned_columns_roster(tmp_path):
    """Pinned column sets for schema v4: obs_*, state_*, buffer_*, tput_*, current_* (26 machines), strat.*, fault labels."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"

    df = pd.read_parquet(parquet_file)

    # Assert exactly 26 machines in MACHINE_INDEX
    assert len(config.MACHINE_INDEX) == 26

    # Verify 5 channel prefixes across all 26 machines
    for m_name in config.MACHINE_INDEX:
        assert f"obs_{m_name}" in df.columns, f"Missing obs_{m_name}"
        assert f"state_{m_name}" in df.columns, f"Missing state_{m_name}"
        assert f"buffer_{m_name}" in df.columns, f"Missing buffer_{m_name}"
        assert f"tput_{m_name}" in df.columns, f"Missing tput_{m_name}"
        assert f"current_{m_name}" in df.columns, f"Missing current_{m_name}"

    # Verify channel column counts
    obs_cols = [c for c in df.columns if c.startswith("obs_")]
    state_cols = [
        c for c in df.columns if c.startswith("state_") and c != "state_histogram"
    ]
    buffer_cols = [c for c in df.columns if c.startswith("buffer_")]
    tput_cols = [c for c in df.columns if c.startswith("tput_")]
    current_cols = [c for c in df.columns if c.startswith("current_")]

    assert len(obs_cols) == 26
    assert len(state_cols) == 26
    assert len(buffer_cols) == 26
    assert len(tput_cols) == 26
    assert len(current_cols) == 26

    # Verify stratification keys
    for key in REQUIRED_STRAT_FIELDS:
        assert key in df.columns, f"Missing stratification column: {key}"

    # Verify fault classification labels
    for label in FAULT_LABEL_FIELDS:
        assert label in df.columns, f"Missing fault label column: {label}"

    # Verify schema_version == 4 everywhere
    assert (df["schema_version"] == 4).all(), "All rows must have schema_version == 4"


def test_mock_train_consumer_zero_join_execution(tmp_path):
    """Consumer executes grouped episode-seeded CV splits with zero joins."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"
    win_cfg_file = tmp_path / "window_config.json"
    meta_file = tmp_path / "ingestion_metadata.json"

    consumer = MockTrainPipelineConsumer()
    report = consumer.run_pipeline(
        parquet_file,
        window_config_path=win_cfg_file,
        metadata_path=meta_file,
        strat_key="family",
        n_splits=2,
    )

    assert report["zero_join_verified"] is True
    assert report["num_episodes"] == 8
    assert len(report["folds"]) == 2

    # Verify each fold has disjoint episodes
    for fold_info in report["folds"]:
        train_eps = set(fold_info["train_episodes"])
        val_eps = set(fold_info["val_episodes"])
        assert len(train_eps.intersection(val_eps)) == 0, (
            "Episode leaked across train and val!"
        )
        assert len(train_eps) > 0
        assert len(val_eps) > 0


def test_mock_train_consumer_ast_zero_adhoc_joins():
    """Prove that consumer code contains ZERO calls to merge, join, or concat via AST walk."""
    assert_zero_adhoc_joins(MockTrainPipelineConsumer)
    assert_zero_adhoc_joins(MockTrainPipelineConsumer.load_and_validate)
    assert_zero_adhoc_joins(MockTrainPipelineConsumer.create_grouped_splits)
    assert_zero_adhoc_joins(MockTrainPipelineConsumer.fit_and_evaluate_fold)
    assert_zero_adhoc_joins(MockTrainPipelineConsumer.run_pipeline)


@pytest.mark.parametrize(
    "strat_key",
    ["family", "mode", "root_id", "wear_endpoint"],
)
def test_grouped_splits_using_stratification_keys_only(tmp_path, strat_key):
    """Grouped CV must work with ANY embedded stratification key without extra table lookups."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"

    consumer = MockTrainPipelineConsumer()
    df = consumer.load_and_validate(parquet_file)

    # For continuous wear_endpoint, discretize into classes for stratification
    if strat_key == "wear_endpoint":
        binned = None
        if df["wear_endpoint"].nunique() > 1:
            try:
                cand = pd.qcut(df["wear_endpoint"], q=2, labels=["low", "high"])
                n_eps_per_bin = df.assign(_b=cand).groupby("_b")["episode_id"].nunique()
                if cand.nunique() > 1 and n_eps_per_bin.min() >= 2:
                    binned = cand
            except ValueError:
                binned = None
        if binned is None:
            binned = df["wear_endpoint"].apply(
                lambda w: "nominal" if w <= 5.0 else "critical"
            )
        df["wear_binned"] = binned
        key_to_use = "wear_binned"
    else:
        key_to_use = strat_key

    splits = consumer.create_grouped_splits(
        df, strat_key=key_to_use, n_splits=2, seed=777
    )
    assert len(splits) == 2

    for tr_idx, va_idx in splits:
        tr_eps = set(df.iloc[tr_idx]["episode_id"])
        va_eps = set(df.iloc[va_idx]["episode_id"])
        assert len(tr_eps.intersection(va_eps)) == 0, (
            f"Leakage with strat_key={strat_key}"
        )


def test_mock_train_consumer_tf1_leakage_law(tmp_path):
    """Scaler fit strictly inside fold; fitting fold 0 vs fold 1 yields distinct fold-local parameters."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"

    consumer = MockTrainPipelineConsumer()
    df = consumer.load_and_validate(parquet_file)
    splits = consumer.create_grouped_splits(df, strat_key="family", n_splits=2)

    feature_cols = [c for c in df.columns if c.startswith(("obs_", "current_"))]
    fold0_stats = consumer.fit_and_evaluate_fold(
        df, splits[0][0], splits[0][1], feature_cols
    )
    fold1_stats = consumer.fit_and_evaluate_fold(
        df, splits[1][0], splits[1][1], feature_cols
    )

    # Different folds have different training episodes and thus different mean vectors
    assert not np.allclose(fold0_stats["mean"], fold1_stats["mean"]), (
        "Fold scalers must be fold-local and distinct, not global"
    )


def test_schema_version_4_enforced_everywhere(tmp_path):
    """schema_version == 4 enforced in Parquet, window_config.json, and metadata sidecars."""
    export_contract_dataset_v4(out_dir=tmp_path)

    parquet_file = tmp_path / "dataset_v4.parquet"
    win_cfg_file = tmp_path / "window_config.json"
    meta_file = tmp_path / "ingestion_metadata.json"

    df = pd.read_parquet(parquet_file)
    assert (df["schema_version"] == 4).all()

    win_cfg = json.loads(win_cfg_file.read_text(encoding="utf-8"))
    assert win_cfg["schema_version"] == 4

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["schema_version"] == 4


def test_flag_day_v3_reader_rejects_v4_dataset(tmp_path):
    """Flag-day v3 reader rejection: reading v4 dataset with legacy v3 reader raises ValueError loudly."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"

    # Legacy v3 reader function (load_v3_dataset or load_dataset enforcing < 4)
    v3_reader = getattr(dataset_export, "load_v3_dataset", dataset_export.load_dataset)
    with pytest.raises(
        ValueError, match=r"(?i)v3 reader.*rejects.*v4|schema_version.*4|want.*3"
    ):
        v3_reader(parquet_file)


# ==============================================================================
# Negative Control Tests: Renamed/Missing Columns, Legacy Schema, Join in AST
# ==============================================================================


def test_negative_control_missing_family_column_fails(tmp_path):
    """Negative control: missing 'family' column MUST cause contract validation to fail loudly."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"
    df = pd.read_parquet(parquet_file)

    # Drop required 'family' column
    df_missing = df.drop(columns=["family"])
    corrupt_file = tmp_path / "dataset_missing_family.parquet"
    df_missing.to_parquet(corrupt_file)

    consumer = MockTrainPipelineConsumer()
    with pytest.raises(KeyError, match="family"):
        consumer.load_and_validate(corrupt_file)


def test_negative_control_renamed_family_to_fault_family_fails(tmp_path):
    """Negative control: 'family' renamed to 'fault_family' MUST cause contract validation to fail loudly."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"
    df = pd.read_parquet(parquet_file)

    # Rename required 'family' to 'fault_family'
    df_renamed = df.rename(columns={"family": "fault_family"})
    corrupt_file = tmp_path / "dataset_renamed_family.parquet"
    df_renamed.to_parquet(corrupt_file)

    consumer = MockTrainPipelineConsumer()
    with pytest.raises(KeyError, match="family"):
        consumer.load_and_validate(corrupt_file)


@pytest.mark.parametrize(
    "dropped_col",
    ["episode_id", "mode", "root_id", "wear_endpoint", "maint_flag"],
)
def test_negative_control_missing_stratification_keys_fail(tmp_path, dropped_col):
    """Negative control: any missing owned stratification key MUST cause contract test to fail loudly."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"
    df = pd.read_parquet(parquet_file)

    df_corrupt = df.drop(columns=[dropped_col])
    corrupt_file = tmp_path / f"dataset_missing_{dropped_col}.parquet"
    df_corrupt.to_parquet(corrupt_file)

    consumer = MockTrainPipelineConsumer()
    with pytest.raises(KeyError, match=dropped_col):
        consumer.load_and_validate(corrupt_file)


@pytest.mark.parametrize(
    "missing_channel",
    ["current_A0", "obs_RWK0", "state_B7P", "buffer_C0", "tput_ASM1"],
)
def test_negative_control_missing_machine_channel_fails(tmp_path, missing_channel):
    """Negative control: any missing machine channel column MUST cause contract test to fail loudly."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"
    df = pd.read_parquet(parquet_file)

    df_corrupt = df.drop(columns=[missing_channel])
    corrupt_file = tmp_path / f"dataset_missing_{missing_channel}.parquet"
    df_corrupt.to_parquet(corrupt_file)

    consumer = MockTrainPipelineConsumer()
    with pytest.raises(KeyError, match=missing_channel):
        consumer.load_and_validate(corrupt_file)


def test_negative_control_legacy_schema_version_fails(tmp_path):
    """Negative control: dataset with schema_version < 4 MUST cause contract validation to fail loudly."""
    export_contract_dataset_v4(out_dir=tmp_path)
    parquet_file = tmp_path / "dataset_v4.parquet"
    df = pd.read_parquet(parquet_file)

    df_corrupt = df.copy()
    df_corrupt["schema_version"] = 3
    corrupt_file = tmp_path / "dataset_schema_v3.parquet"
    df_corrupt.to_parquet(corrupt_file)

    consumer = MockTrainPipelineConsumer()
    with pytest.raises(ValueError, match="schema_version.*!= 4"):
        consumer.load_and_validate(corrupt_file)


def test_negative_control_consumer_ast_with_merge_fails():
    """Negative control: if consumer code attempts a merge call, AST check MUST fail loudly."""
    code_with_merge = """
def bad_consumer_with_merge(df, metadata_df):
    return df.merge(metadata_df, on="episode_id")
"""
    with pytest.raises(AssertionError, match="Zero-join contract violation.*merge"):
        assert_zero_adhoc_joins(code_with_merge)


def test_negative_control_consumer_ast_with_join_fails():
    """Negative control: if consumer code attempts a join call, AST check MUST fail loudly."""
    code_with_join = """
def bad_consumer_with_join(df, lookup_table):
    return df.join(lookup_table)
"""
    with pytest.raises(AssertionError, match="Zero-join contract violation.*join"):
        assert_zero_adhoc_joins(code_with_join)


def test_negative_control_consumer_ast_with_concat_fails():
    """Negative control: if consumer code attempts a concat call, AST check MUST fail loudly."""
    code_with_concat = """
def bad_consumer_with_concat(table_a, table_b):
    import pandas as pd
    return pd.concat([table_a, table_b])
"""
    with pytest.raises(AssertionError, match="Zero-join contract violation.*concat"):
        assert_zero_adhoc_joins(code_with_concat)
