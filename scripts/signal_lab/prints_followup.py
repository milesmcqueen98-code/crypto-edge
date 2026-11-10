#!/usr/bin/env python3
"""Signal lab 2 follow-up (coordinator, Nov 9), one runner job on the stored fetch artifacts.

1. Margin tables: prints_features.main(art_dir, <tmp>, "0,5,60"). The margin-0 tables are compared with the committed
   f6_main.parquet and f6_early.parquet (values must be equal or the run stops; bytes are compared and reported), and
   only the margin tables are written next to them: f6_main_m5.parquet, f6_early_m5.parquet, f6_main_m60.parquet,
   f6_early_m60.parquet. The committed margin-0 files are never rewritten.
2. Boundary offsets: prints_boundary.main -> qa_boundary.json, qa_boundary_cand.parquet.
Writes qa_margin.json (the margin-0 check, and per margin and era: completeness, empty windows, missing values and
medians of the five F6 features).
usage: python scripts/signal_lab/prints_followup.py <art_dir> [<ref_dir>] [<out_dir>]   (both default to
       reports/signal_lab/prints)
"""
import filecmp
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
import pyarrow

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PR = os.path.join(ROOT, "reports", "signal_lab", "prints")
sys.path.insert(0, HERE)
import prints_features as PFE  # noqa: E402
import prints_boundary as PB  # noqa: E402

MARGINS = (5, 60)


def same_values(a, b):
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return False
    for k in a.columns:
        if str(a[k].dtype) != str(b[k].dtype):
            return False
        x, y = a[k].to_numpy(), b[k].to_numpy()
        if a[k].dtype.kind == "f":
            if not np.array_equal(x, y, equal_nan=True):
                return False
        elif not (x == y).all():
            return False
    return True


def summary(F):
    c = F[F.complete]
    return dict(rows=int(len(F)), complete=int(F.complete.sum()), no_print_windows=int((c.n_prints == 0).sum()),
                n_prints_median=float(c.n_prints.median()),
                missing={k: int(c[k].isna().sum()) for k in PFE.F6},
                median={k: float(c[k].median()) for k in PFE.F6})


def main(art_dir, ref_dir=PR, out_dir=PR):
    tmp = os.path.join(ROOT, "f6_tmp")
    PFE.main(art_dir, tmp, "0," + ",".join(str(m) for m in MARGINS))
    rep = dict(pandas=pd.__version__, pyarrow=pyarrow.__version__, margin0={}, margins={})
    for era in ("main", "early"):
        new, old = os.path.join(tmp, f"f6_{era}.parquet"), os.path.join(ref_dir, f"f6_{era}.parquet")
        a, b = pd.read_parquet(new), pd.read_parquet(old)
        ok = same_values(a, b)
        rep["margin0"][era] = dict(values_equal=ok, bytes_equal=filecmp.cmp(new, old, shallow=False))
        print(f"margin 0 {era}: {rep['margin0'][era]}", flush=True)
        if not ok:
            raise SystemExit(f"margin-0 recomputation of {era} differs from the committed table; nothing written")
        rep["margins"].setdefault("0", {})[era] = summary(a)
    os.makedirs(out_dir, exist_ok=True)
    for m in MARGINS:
        for era in ("main", "early"):
            src = os.path.join(tmp, f"f6_{era}_m{m}.parquet")
            F = pd.read_parquet(src)
            ref = pd.read_parquet(os.path.join(ref_dir, f"f6_{era}.parquet"))
            assert list(F.columns) == list(ref.columns) and len(F) == len(ref)
            assert (F.coin.to_numpy() == ref.coin.to_numpy()).all() and (F.ts.to_numpy() == ref.ts.to_numpy()).all()
            assert np.array_equal(F.big_thr_usd.to_numpy(), ref.big_thr_usd.to_numpy(), equal_nan=True)
            rep["margins"].setdefault(str(m), {})[era] = summary(F)
            shutil.copy(src, os.path.join(out_dir, f"f6_{era}_m{m}.parquet"))
    with open(os.path.join(out_dir, "qa_margin.json"), "w") as fh:
        json.dump(rep, fh, indent=1)
    print(json.dumps(rep, indent=1), flush=True)
    PB.main(art_dir, out_dir)


if __name__ == "__main__":
    main(*sys.argv[1:4])
