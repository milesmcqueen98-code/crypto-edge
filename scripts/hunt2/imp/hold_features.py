#!/usr/bin/env python3
"""Edge hunt 2, IMP (runs on GitHub Actions, AFTER the SHAPE and IMP freeze commits): HOLD print features.

The first post-freeze dispatch (run 42545412684: parent_features.py art reports/hunt2/parents) computed
features_hold.csv but could not commit it: parent_features.py also rewrites the tracked features_dev.csv and coverage.txt,
so the workflow's `git pull --rebase` refused ("unstaged changes"), and the step still ended green. This wrapper runs
the shared scripts/hunt2/parent_features.py UNCHANGED into a scratch folder and copies only features_hold.csv to
reports/hunt2/parents/ (tracked files untouched). It also checks that the runner reproduces the committed DEV features
(reports/hunt2/imp/runner_dev_check.txt: row keys and the largest difference per column, no outcomes).

usage (on the runner, from the repo root): python scripts/hunt2/imp/hold_features.py art
"""
import os
import shutil
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt2"))
import parent_features as PF  # noqa: E402

PAR = os.path.join(ROOT, "reports", "hunt2", "parents")


def dev_check(committed, runner):
    a = pd.read_csv(committed)
    b = pd.read_csv(runner)
    lines = [f"rows: committed {len(a)}, runner {len(b)}", f"same columns in order: {list(a.columns) == list(b.columns)}"]
    if len(a) == len(b) and "window_id" in a and "window_id" in b:
        a, b = a.sort_values("window_id").reset_index(drop=True), b.sort_values("window_id").reset_index(drop=True)
        lines.append(f"same window ids: {bool((a.window_id.to_numpy() == b.window_id.to_numpy()).all())}")
        worst = []
        for c in a.columns:
            if c not in b:
                continue
            x, y = a[c], b[c]
            if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
                xa, ya = x.to_numpy(float), y.to_numpy(float)
                nan_mismatch = int((np.isnan(xa) != np.isnan(ya)).sum())
                ok = ~np.isnan(xa) & ~np.isnan(ya)
                d = float(np.max(np.abs(xa[ok] - ya[ok]) / np.maximum(1e-12, np.abs(xa[ok])))) if ok.any() else 0.0
                worst.append((c, d, nan_mismatch))
            else:
                worst.append((c, float((x.astype(str) != y.astype(str)).sum()), 0))
        bad = [w for w in worst if w[1] > 1e-9 or w[2] > 0]
        lines.append(f"columns compared: {len(worst)}; columns with a relative difference > 1e-9 or NaN mismatch: "
                     f"{len(bad)}")
        lines += [f"  {c}: max rel diff {d:.3e}, NaN mismatches {n}" for c, d, n in bad[:60]]
    return "\n".join(lines) + "\n"


def main(art):
    tmp = os.path.join(ROOT, "pf_out")
    PF.main(art, tmp)
    shutil.copy(os.path.join(tmp, "features_hold.csv"), os.path.join(PAR, "features_hold.csv"))
    txt = dev_check(os.path.join(PAR, "features_dev.csv"), os.path.join(tmp, "features_dev.csv"))
    os.makedirs(os.path.join(ROOT, "reports", "hunt2", "imp"), exist_ok=True)
    open(os.path.join(ROOT, "reports", "hunt2", "imp", "runner_dev_check.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main(sys.argv[1])
