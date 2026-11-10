#!/usr/bin/env python3
"""Late BTC replay: the tables (light; reads only the runs' derived CSVs).

  python scripts/owner/late_btc/summarize.py RUN_DIR [RUN_DIR ...]

RUN_DIR: reports/owner/late_btc/runs/<era>_<job> (summary.csv, daily_<era>_<scenario>.csv, gate.json, exact.csv).
Writes reports/owner/late_btc/results.csv (every scenario and seed), table.csv (S0, S1, S2, S3 and S4 as mean and range
over seeds, with the paired daily comparison against S0) and paired.csv (each seed's paired interval).
Paired comparison (prereg measure 4): daily return difference against S0 (blended, print-priced exits); stationary
bootstrap of the mean, mean block 7 days, 5,000 draws, default_rng(11), 90% interval. For S3 and S4 the series is the
mean of the five seeds' daily returns.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "owner", "late_btc")
ERA_ORDER = ["sel", "chk", "early"]
FAMILY = ["S0", "S1", "S2", "S3", "S4"]


def stationary_idx(n, rng, mean_block=7):
    """scripts/signal_lab/score.py stationary_idx."""
    out = np.empty(n, int)
    i = rng.integers(n)
    for t in range(n):
        out[t] = i
        i = rng.integers(n) if rng.random() < 1.0 / mean_block else (i + 1) % n
    return out


def paired(d, B=5000, seed=11):
    rng = np.random.default_rng(seed)
    x = d.to_numpy()
    bs = np.array([x[stationary_idx(len(x), rng)].mean() for _ in range(B)])
    return float(x.mean()), float(np.quantile(bs, 0.05)), float(np.quantile(bs, 0.95))


EXTRA = ["armed_kept", "armed_new", "lvl_bp_med", "lvl_bp_p95", "fills_s0_armed", "fills_s0_kept", "fills_new"]


def read_summary(path):
    """summary.csv is appended scenario by scenario under S0's header; later rows carry the decision measures too."""
    lines = open(path).read().splitlines()
    names = lines[0].split(",")
    names += [x for x in EXTRA if x not in names]
    import io
    return pd.read_csv(io.StringIO("\n".join(lines[1:])), header=None, names=names)


def family(s):
    return s[:2]


def main(dirs):
    S, daily = [], {}
    for dr in dirs:
        S.append(read_summary(os.path.join(dr, "summary.csv")))
        for f in os.listdir(dr):
            if f.startswith("daily_"):
                era, scen = f[6:-4].split("_", 1)
                daily[(era, scen)] = pd.read_csv(os.path.join(dr, f), index_col=0, parse_dates=True)["print"]
    S = pd.concat(S, ignore_index=True).drop_duplicates(["scen", "era"], keep="last")
    S0 = S[S.scen == "S0"].set_index("era")
    S["d_sharpe"] = S.sharpe - S.era.map(S0.sharpe)
    S["d_ret_yr"] = S.ret_yr - S.era.map(S0.ret_yr)
    S["family"] = S.scen.map(family)
    prow = []
    for (era, scen), d in daily.items():
        if scen == "S0":
            continue
        dd = (d - daily[(era, "S0")].reindex(d.index)).dropna()
        m, lo, hi = paired(dd)
        prow.append(dict(era=era, scen=scen, mean_bp=1e4 * m, lo90_bp=1e4 * lo, hi90_bp=1e4 * hi, days=len(dd)))
    P = pd.DataFrame(prow)
    S = S.merge(P, on=["era", "scen"], how="left")
    S.sort_values(["era", "scen"]).to_csv(os.path.join(OUT, "results.csv"), index=False)
    P.sort_values(["era", "scen"]).to_csv(os.path.join(OUT, "paired.csv"), index=False)
    cols = ["sharpe", "ret_yr", "d_sharpe", "d_ret_yr", "maxdd", "worst_day", "first_fills_min", "rung_fills_min",
            "net_bp_per_usd", "armed_kept", "armed_new", "lvl_bp_med", "lvl_bp_p95", "fills_s0_armed", "fills_s0_kept",
            "fills_new"]
    rows = []
    for era in [e for e in ERA_ORDER if e in set(S.era)]:
        for fam in FAMILY:
            G = S[(S.era == era) & (S.family == fam)]
            if not len(G):
                continue
            r = dict(era=era, scenario=fam, seeds=len(G))
            for c in cols:
                if c in G:
                    r[c] = float(G[c].mean())
                    if len(G) > 1:
                        r[c + "_min"], r[c + "_max"] = float(G[c].min()), float(G[c].max())
            if fam != "S0":
                ser = [daily[(era, s)] for s in G.scen]
                avg = pd.concat(ser, axis=1).mean(axis=1)
                dd = (avg - daily[(era, "S0")].reindex(avg.index)).dropna()
                m, lo, hi = paired(dd)
                r.update(paired_mean_bp=1e4 * m, paired_lo90_bp=1e4 * lo, paired_hi90_bp=1e4 * hi)
            rows.append(r)
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, "table.csv"), index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 60):
        print(T.round(4).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:])
