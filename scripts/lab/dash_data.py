#!/usr/bin/env python3
"""Dashboard datasets for the wick v2 lab section (CSV files in reports/lab/dash/)."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

OUT = os.path.join(core.ROOT, "reports", "lab")
DASH = os.path.join(OUT, "dash")
BASE = "V000 base (v1)"
FAMILY = {"base": "v1 base", "A": "Entry level and reference", "B": "Exits", "C": "AI model", "D": "Sizing and portfolio",
          "E": "Universe and fees", "F": "Rhyming books", "R2": "Combinations"}


def candidate(dec):
    """Without an adopted variant: the shortlisted one closest to clearing every bar (all bars but the deflated
    Sharpe pass, highest deflated Sharpe)."""
    S = pd.DataFrame(dec["shortlist"])
    others = [c for c in S.columns if c[:2] in ("1 ", "2 ", "3 ", "5 ")]
    S = S[S[others].all(axis=1)].sort_values("dsr_with_2000", ascending=False)
    return S.variant.iloc[0]


def main():
    os.makedirs(DASH, exist_ok=True)
    tags = [t for t in ("round1", "round1b", "round2") if os.path.exists(os.path.join(OUT, f"results_val_{t}.csv"))]
    V = pd.concat([pd.read_csv(os.path.join(OUT, f"results_val_{t}.csv")) for t in tags]).drop_duplicates("variant", keep="last")
    sl = json.load(open(os.path.join(OUT, "shortlist.json")))
    dec = json.load(open(os.path.join(OUT, "v2_decision.json")))
    V["family_name"] = V.family.map(FAMILY)
    V["shortlisted"] = V.variant.isin(sl["variants"])
    V["code"] = V.variant.str.split().str[0]
    cols = ["variant", "code", "family", "family_name", "val_real_sharpe", "val_base_sharpe", "val_trades", "val_net_real_bp",
            "val_hit", "val_real_maxdd", "shortlisted"]
    V[cols].sort_values("val_real_sharpe", ascending=False).round(4).to_csv(os.path.join(DASH, "lab_variants.csv"), index=False)
    b0 = V.set_index("variant").loc[BASE, "val_real_sharpe"]
    fam = V[V.family != "base"].groupby(["family", "family_name"]).val_real_sharpe.agg(n="count", best="max", median="median")
    fam["share_beating_base"] = V[V.family != "base"].groupby(["family", "family_name"]).val_real_sharpe.apply(lambda s: (s > b0).mean())
    fam.reset_index().round(4).to_csv(os.path.join(DASH, "lab_families.csv"), index=False)
    S = pd.DataFrame(dec["shortlist"])
    S.round(4).to_csv(os.path.join(DASH, "lab_shortlist.csv"), index=False)
    # equity: base vs the adopted variant (or the best candidate), realistic and advertised costs, spot-priced,
    # as the bot trades (quiet window), from the quiet futures check run
    pick = dec["adopted"] or candidate(dec)
    qp = os.path.join(OUT, "futures_daily_quiet.parquet")
    Dq = pd.read_parquet(qp) if os.path.exists(qp) else pd.read_parquet(os.path.join(OUT, "futures_daily.parquet"))
    rows = []
    for name, label in ((BASE, "v1 base"), (pick, "v2 adopted" if dec["adopted"] else "best v2 candidate")):
        for model in ("real", "adv"):
            col = f"{name}|spot_full|{model}"
            if col not in Dq:
                continue
            x = Dq[col]
            x = x[x.index >= core.VAL[0]]
            eq = x.cumsum()
            for d_, r_, e_ in zip(x.index, x.to_numpy(), eq.to_numpy()):
                rows.append(dict(date=d_.date().isoformat(), series=label, costs=model, daily_ret=r_, cum_ret=e_,
                                 period="holdout" if d_ >= core.HOLD[0] else "validation"))
    pd.DataFrame(rows).round(6).to_csv(os.path.join(DASH, "lab_equity.csv"), index=False)
    for f in ("futures_check.csv", "futures_check_quiet.csv"):
        p = os.path.join(OUT, f)
        if os.path.exists(p):
            F = pd.read_csv(p)
            keep = [c for c in F.columns if c in ("variant", "venue", "trades", "per_day", "gross_bp", "net_real_bp", "net_adv_bp",
                                                   "net_base_bp", "hit") or c.endswith("_sharpe") or c.endswith("_ann")
                    or c.endswith("_maxdd")]
            F[keep].round(4).to_csv(os.path.join(DASH, "lab_" + f), index=False)
    p = os.path.join(OUT, "cost_table.csv")
    if os.path.exists(p):
        pd.read_csv(p).round(2).to_csv(os.path.join(DASH, "lab_costs.csv"), index=False)
    print("wrote", sorted(os.listdir(DASH)))


if __name__ == "__main__":
    main()
