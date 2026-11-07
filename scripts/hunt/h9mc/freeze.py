#!/usr/bin/env python3
"""H9 (MC): apply the fixed selection rule to reports/hunt/h9mc/dev_trials.csv and write frozen.json.
Rule (prereg + SPEC): among DEV trials with at least 40 trades, the highest DEV alpha t (sleeve $30K at 2x costs on
the incumbent at $70K); ties go to the simpler variant (BTC+ETH universe before all; then the smaller grid index).
If no trial has 40 trades, nothing is frozen and HOLD is not read.
Usage: freeze.py            (selects among the 18 long DEV trials, plus the mirror if it was run)
"""
import json
import os
import subprocess
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import step2  # noqa: E402

OUT = step2.OUT


def main():
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    G = step2.variant_grid()
    order = {n: i for i, n in enumerate(G)}
    T["simple"] = T.variant.map(lambda n: (0 if n.endswith("btceth") or "btceth_" in n else 1, order.get(n, 99)))
    E = T[T.trades >= 40].copy()
    if E.empty:
        raise SystemExit("no DEV trial has >= 40 trades: nothing to freeze, HOLD is not read")
    E = E.sort_values(["dev_alpha_t_inc70", "simple"], ascending=[False, True])
    best = E.iloc[0]
    name = best.variant
    if name in G:
        params = G[name]
    else:                                   # the short mirror of a grid variant
        base = name[: -len("_short")]
        params = dict(G[base])
        params["side"] = -1
    code = subprocess.run(["git", "-C", step2.common.ROOT, "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    F = dict(idea="h9mc", variant=name, params=params, code_commit=code,
             selection="highest DEV alpha t (sleeve $30K, 2x costs, on incumbent $70K) among DEV trials with >= 40 "
                       "trades; ties to the simpler variant",
             dev=dict(trades=int(best.trades), dev_alpha_t_inc70=float(best.dev_alpha_t_inc70),
                      dev_sleeve_sharpe_2x=float(best.dev_sleeve_sharpe),
                      dev_sleeve_sharpe_1x=float(best.dev_sleeve_sharpe_1x),
                      dev_book_gain_a07=float(best.dev_book_gain), mean_bp_2x=float(best.mean_bp_2x),
                      mean_bp_1x=float(best.mean_bp_1x), corr_incumbent=float(best.corr_inc)),
             runner_up=E.iloc[1][["variant", "trades", "dev_alpha_t_inc70"]].to_dict() if len(E) > 1 else None,
             n_trials_logged=int(len(T)) + 2)
    json.dump(F, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=float)
    print(json.dumps(F, indent=1, default=float))


if __name__ == "__main__":
    main()
