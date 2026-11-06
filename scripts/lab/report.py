#!/usr/bin/env python3
"""Markdown summary of the wick v2 lab for reports/lab/v2_report.md (after decide.py)."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

OUT = os.path.join(core.ROOT, "reports", "lab")
BASE = "V000 base (v1)"
FAMILY = {"base": "v1 base", "A": "Entry level and reference", "B": "Exits", "C": "AI model", "D": "Sizing and portfolio",
          "E": "Universe and fees", "F": "Rhyming books", "R2": "Combinations"}


def md(df, floatfmt=2):
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(lambda x: "" if pd.isna(x) else f"{x:.{floatfmt}f}")
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "\n".join("| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False))


def main():
    tags = [t for t in ("round1", "round1b", "round2") if os.path.exists(os.path.join(OUT, f"results_val_{t}.csv"))]
    V = pd.concat([pd.read_csv(os.path.join(OUT, f"results_val_{t}.csv")) for t in tags]).drop_duplicates("variant", keep="last")
    Hh = pd.concat([pd.read_csv(os.path.join(OUT, f"results_hold_{t}.csv")) for t in tags]).drop_duplicates("variant", keep="last")
    dec = json.load(open(os.path.join(OUT, "v2_decision.json")))
    b0 = V.set_index("variant").loc[BASE]
    out = [f"# Wick v2 lab results ({len(V)} variants)\n"]
    out.append(f"Base (v1) validation realistic Sharpe {b0.val_real_sharpe:.2f}, base-cost {b0.val_base_sharpe:.2f}, "
               f"{int(b0.val_trades)} trades.\n")
    fam = V[V.family != "base"].groupby("family").val_real_sharpe.agg(n="count", best="max", median="median")
    fam["beat base"] = V[V.family != "base"].groupby("family").val_real_sharpe.apply(lambda s: f"{(s > b0.val_real_sharpe).mean():.0%}")
    fam.insert(0, "family", [FAMILY.get(f, f) for f in fam.index])
    out.append("## Families (validation, realistic costs)\n" + md(fam.reset_index(drop=True)) + "\n")
    top = V[V.val_trades >= 150].sort_values("val_real_sharpe", ascending=False).head(15)
    top = top.merge(Hh[["variant", "hold_real_sharpe"]], on="variant", how="left")
    sl = set(dec_ for dec_ in [r["variant"] for r in dec["shortlist"]])
    top["hold_real_sharpe"] = [h if v in sl or v == BASE else np.nan for v, h in zip(top.variant, top.hold_real_sharpe)]
    cols = ["variant", "val_real_sharpe", "val_base_sharpe", "val_trades", "val_net_real_bp", "hold_real_sharpe"]
    out.append("## Top 15 by validation realistic Sharpe (holdout shown for the shortlist only)\n" + md(top[cols]) + "\n")
    S = pd.DataFrame(dec["shortlist"])
    out.append("## Shortlist and adoption bars\n" + md(S) + "\n")
    out.append(f"PBO {dec['pbo']:.2f}; walk-forward variant selection Sharpe {dec['walk_forward']['sharpe']:.2f} vs base "
               f"{dec['walk_forward']['base']:.2f}.\n\nADOPTED: {dec['adopted'] or 'none (v1 stays)'}\n")
    for f in ("futures_check.csv", "futures_check_quiet.csv"):
        p = os.path.join(OUT, f)
        if os.path.exists(p):
            F = pd.read_csv(p)
            cols = [c for c in ("variant", "venue", "trades", "gross_bp", "net_real_bp", "net_adv_bp", "all_real_sharpe",
                                "val_part_real_sharpe", "hold_part_real_sharpe", "all_adv_sharpe", "all_base_sharpe") if c in F]
            out.append(f"## {f}\n" + md(F[cols]) + "\n")
    open(os.path.join(OUT, "v2_report.md"), "w").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
