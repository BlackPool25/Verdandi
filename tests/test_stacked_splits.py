"""Split-integrity tests for the stacked-ranker CV (PRISSUE-75 F12/F9).

F12: ranker CV folds must be family-stratified (StratifiedGroupKFold over
episode groups) — never every-kth-episode or order-dependent.
F9: stride-8 windows overlap *within* an episode only; windows never span
episodes, so episode-disjoint folds share zero windows and need no embargo.
"""

import numpy as np
import pandas as pd
import pytest

from scripts.eval_stacked import _episode_folds

pytestmark = [pytest.mark.k3, pytest.mark.battery]


def _synth(n_eps_per_fam=9, machines=4):
    """One row per (episode, machine): mirrors build_rows output shape."""
    fams = ["F1", "F2", "F3"]
    groups, fam = [], []
    for f in fams:
        for e in range(n_eps_per_fam):
            ep = f"{f}-{e}"
            groups += [ep] * machines
            fam += [f] * machines
    return np.array(groups), np.array(fam)


class TestStackedSplitStratified:
    def test_folds_are_episode_grouped_and_family_stratified(self):
        groups, fam = _synth()
        folds = _episode_folds(groups, fam, n_splits=3)
        assert len(folds) == 3
        seen = []
        for tr, te in folds:
            tr_eps, te_eps = set(groups[tr]), set(groups[te])
            assert tr_eps.isdisjoint(te_eps), "episode leaked across fold boundary"
            seen += sorted(te_eps)
            # every family represented in every fold's eval side (stratified,
            # not every-kth / order-dependent)
            assert set(fam[te]) == {"F1", "F2", "F3"}
        # every episode evaluated exactly once
        assert sorted(seen) == sorted(set(groups.tolist()))

    def test_folds_deterministic_within_process(self):
        groups, fam = _synth()
        a = [(tr.tolist(), te.tolist()) for tr, te in _episode_folds(groups, fam)]
        b = [(tr.tolist(), te.tolist()) for tr, te in _episode_folds(groups, fam)]
        assert a == b


class TestNoEmbargoNeeded:
    def test_windows_never_span_episodes(self):
        """Stride overlap is intra-episode only: no window crosses an episode
        boundary, so episode-grouped folds share zero samples (no embargo)."""
        from src.window_dataset import build_windows

        rows = []
        for ep in (101, 102):
            for step in range(40):
                rows.append(
                    {"episode_id": ep, "step": step, "obs_a": float(step),
                     "y": 0, "fault_family": "none"}
                )
        df = pd.DataFrame(rows)
        w, stride = 8, 4
        X, y, fam, grp, starts = build_windows(
            df, w=w, stride=stride, return_starts=True
        )
        ep_len = {ep: (df["episode_id"] == ep).sum() for ep in (101, 102)}
        for ep in np.unique(grp):
            assert (starts[grp == ep] + w <= ep_len[ep]).all(), (
                f"window spans beyond episode {ep}: embargo would be required"
            )
        # episode-disjoint row partitions therefore share no (ep, start) sample
        left = set(zip(grp[: len(grp) // 2].tolist(), starts[: len(starts) // 2].tolist()))
        right = set(zip(grp[len(grp) // 2:].tolist(), starts[len(starts) // 2:].tolist()))
        assert left.isdisjoint(right)
