#!/usr/bin/env python3
"""Edge hunt 2, LETF: apply the SPEC's fixed selection rule to the 12 DEV trials and write reports/hunt2/letf/frozen.json.
Rule: the highest DEV alpha t (h2gates.dev_screen_b, sleeve $50K at 2x) among variants with >= 40 trades; ties go to
BTC only, then k = 2. The commit that adds frozen.json is the freeze.
usage: python scripts/hunt2/letf/freeze.py <code commit>
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "letf")


def main(code_commit):
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    assert len(T) == 12, len(T)
    E = T[T.trades >= 40].copy()
    E["uni_rank"] = (E.uni != "btc").astype(int)          # ties: BTC only first, then k = 2
    E["k_rank"] = (E.k != 2).astype(int)
    E = E.sort_values(["t_alpha", "uni_rank", "k_rank"], ascending=[False, True, True])
    w, ru = E.iloc[0], E.iloc[1]
    fz = dict(idea="letf", path="B", variant=w.variant, params=dict(leg=w.leg, k=int(w.k), universe=w.uni,
                                                                    assets=["BTC"] if w.uni == "btc" else
                                                                    ["BTC", "ETH", "SOL", "XRP"], theta=0.5),
              code_commit=code_commit, model="scripts/hunt2/letf/letf.py (pre-trial definitions in its docstring)",
              selection="highest DEV alpha t (h2gates.dev_screen_b, sleeve $50K at 2x) among DEV trials with >= 40 "
                        "trades; ties -> BTC only, then k = 2",
              dev={k: (float(w[k]) if isinstance(w[k], (int, float)) else w[k]) for k in
                   ("trades", "t_alpha", "sleeve_sharpe_2x", "sleeve_sharpe_1x", "book_gain_2x", "book_gain_1x",
                    "t_alpha_1x", "mean_gross_bp", "mean_net_bp", "mean_net_bp_1x", "corr", "active_days",
                    "pnl_2x", "pnl_1x", "scored_days")},
              runner_up=dict(variant=ru.variant, trades=int(ru.trades), t_alpha=float(ru.t_alpha)),
              eligible=list(E.variant), ineligible=list(T[T.trades < 40].variant), n_trials_logged=int(len(T)))
    json.dump(fz, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps(fz, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    main(sys.argv[1])
