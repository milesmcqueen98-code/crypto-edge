#!/usr/bin/env python3
"""Fresh-era report (reports/wick_v3_prereg.md): 2022-2023 results of the 14 variants vs R2-08 and v1, next to
their 2025-2026 results (seen data). Writes reports/lab/fresh_report.csv and fresh_years.csv."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports", "lab")
R208, V1 = "R2-08 C29+A11", "V000 base (v1)"


def sharpe(x):
    return x.mean() / x.std() * np.sqrt(365) if x.std() > 0 else np.nan


def paired_t(a, b):
    d = a - b
    return d.mean() / d.std() * np.sqrt(len(d)) if d.std() > 0 else np.nan


def main():
    E = pd.read_parquet(os.path.join(OUT, "daily_real_early_fresh.parquet"))
    Ev = pd.read_csv(os.path.join(OUT, "results_val_early_fresh.csv")).set_index("variant")
    main_tags = ("round1", "round1b", "round2", "round3")
    M = pd.concat([pd.read_parquet(os.path.join(OUT, f"daily_real_{t}.parquet")) for t in main_tags
                   if os.path.exists(os.path.join(OUT, f"daily_real_{t}.parquet"))], axis=1)
    M = M.loc[:, ~M.columns.duplicated(keep="last")]
    rows, yrs = [], []
    for v in E.columns:
        e = E[v]
        row = dict(variant=v, fresh_sharpe=sharpe(e), fresh_ret=e.sum(),
                   t_vs_R208=paired_t(e, E[R208]), t_vs_v1=paired_t(e, E[V1]),
                   trades=Ev.loc[v, "val_trades"], net_bp=Ev.loc[v, "val_net_real_bp"], hit=Ev.loc[v, "val_hit"])
        for y in (2022, 2023):
            x = e[e.index.year == y]
            row[f"{y}_sharpe"], row[f"{y}_ret"] = sharpe(x), x.sum()
            row[f"{y}_beats_R208"] = sharpe(x) > sharpe(E[R208][E.index.year == y])
        if v in M:
            m = M[v]
            row["main_sharpe"] = sharpe(m)
            row["main_t_vs_R208"] = paired_t(m, M[R208]) if R208 in M else np.nan
        rows.append(row)
    R = pd.DataFrame(rows).set_index("variant")
    # pre-registered rule for a round-3 refinement to replace R2-08
    R["replaces_R208"] = ((R.t_vs_R208 >= 2.0) & R["2022_beats_R208"] & R["2023_beats_R208"] &
                          (R.main_t_vs_R208 > -1.0) & R.index.str.startswith("R3"))
    R.to_csv(os.path.join(OUT, "fresh_report.csv"))
    pd.set_option("display.width", 250)
    cols = ["fresh_sharpe", "fresh_ret", "t_vs_R208", "t_vs_v1", "2022_sharpe", "2022_ret", "2023_sharpe", "2023_ret",
            "trades", "net_bp", "hit", "main_sharpe", "main_t_vs_R208", "replaces_R208"]
    print("Fresh era 2022-2023 (never used by any wick research), realistic costs at today's bp, spot-priced:")
    print(R[cols].sort_values("fresh_sharpe", ascending=False).round(2).to_string())
    q = E.groupby(E.index.to_period("Q")).sum()[[V1, R208]]
    print("\nQuarterly return on $10k, v1 vs R2-08:")
    print((q * 100).round(1).to_string())
    flip = R.loc[V1, "t_vs_R208"] > 1.0
    print(f"\nv1 vs R2-08 paired t in the fresh era: {R.loc[V1, 't_vs_R208']:.2f} -> "
          f"{'REVERSE the switch' if flip else 'R2-08 stays'}")
    print("Refinements that replace R2-08:", R.index[R.replaces_R208].tolist() or "none")


if __name__ == "__main__":
    main()
