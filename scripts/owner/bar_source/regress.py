"""Regression of pass R against the reconciliation's research table on the minutes both cover.

  python scripts/owner/bar_source/regress.py --dir reports/owner/bar_source_dev --ref research_minutes.csv.gz

--ref: a research_minutes.csv.gz written by scripts/owner/reconcile/fetch_and_compute.py (it stores floats with
%.10g). Pass R's res_score and res_level are compared on every (minute, coin) both tables hold: identical when they
print the same at %.10g (and both NaN counts as identical); the largest absolute and relative differences are
reported either way, and validity must agree.
"""
import argparse
import json
import os

import numpy as np
import pandas as pd


def g10(x):
    return np.array(["nan" if not np.isfinite(v) else f"{v:.10g}" for v in x])


def regress(ours, ref):
    R = ours.drop_duplicates(["ts", "coin"])[["ts", "coin", "res_score", "res_level", "res_valid"]]
    ref = ref.assign(ts=pd.to_datetime(ref.ts))
    R = R.assign(ts=pd.to_datetime(R.ts).astype("datetime64[ns]"))
    ref = ref.assign(ts=ref.ts.astype("datetime64[ns]"))
    j = R.merge(ref[["ts", "coin", "score", "level", "valid"]], on=["ts", "coin"], how="inner")
    out = dict(shared_rows=len(j), shared_minutes=int(j.ts.nunique()),
               first=str(j.ts.min()) if len(j) else None, last=str(j.ts.max()) if len(j) else None,
               valid_disagree=int((j.res_valid.astype(bool) != j.valid.astype(bool)).sum()))
    for a, b in (("res_score", "score"), ("res_level", "level")):
        x, y = j[a].to_numpy(float), j[b].to_numpy(float)
        same = g10(x) == g10(y)
        d = np.abs(x - y)
        rel = d / np.abs(y)
        fin = np.isfinite(d)
        out[b] = dict(identical_at_10g=int(same.sum()), differ=int((~same).sum()),
                      max_abs_diff=float(d[fin].max()) if fin.any() else None,
                      max_rel_diff=float(rel[fin].max()) if fin.any() else None)
        if (~same).any():
            k = int(np.nanargmax(np.where(fin, d, -1)))
            out[b]["largest_at"] = dict(ts=str(j.ts.iloc[k]), coin=j.coin.iloc[k], ours=x[k], ref=y[k])
    out["identical"] = bool(len(j) and out["score"]["differ"] == 0 and out["level"]["differ"] == 0
                            and out["valid_disagree"] == 0)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", default=None, help="write the result as JSON here")
    a = ap.parse_args(argv)
    res = regress(pd.read_parquet(os.path.join(a.dir, "minutes.parquet")), pd.read_csv(a.ref))
    print(json.dumps(res, indent=1, default=str))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
