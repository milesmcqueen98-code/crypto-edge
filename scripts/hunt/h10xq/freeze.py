#!/usr/bin/env python3
"""H10 (XQ): pre-registered selection and freeze. Among the logged DEV trials (reports/hunt/h10xq/trials_h10xq.csv)
with >= 40 trades, the highest DEV alpha t (sleeve at 2x costs on the incumbent at $70K); ties go to the simpler
variant (fewer modifiers: no cascade filter, H 60). Writes reports/hunt/h10xq/frozen.json with the variant, its
parameters, the code commit hash and the DEV numbers. usage: python scripts/hunt/h10xq/freeze.py"""
import json
import os
import re
import subprocess
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "hunt", "h10xq")


def parse(v):
    m = re.match(r"k(\d+)_(a|b)_(USDT|BTCETH)(?:_H(\d+))?(_casc)?$", v)
    k, ex, q, H, c = m.groups()
    return dict(k=float(k), exit=ex, qset=q, H=int(H) if H else 60, cascade=bool(c))


def main():
    T = pd.read_csv(os.path.join(OUT, "trials_h10xq.csv"))
    ok = T[T.trades >= 40].copy()
    ok["complexity"] = ok.variant.map(lambda v: int("_casc" in v) + int("_H30" in v))
    best = ok.sort_values(["dev_alpha_t_70k", "complexity"], ascending=[False, True]).iloc[0]
    commit = subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"]).decode().strip()
    F = dict(idea="h10xq", variant=best.variant, **parse(best.variant), theta=0.5, bid_usd=5000, max_open=6,
             tp_frac=0.6, scoring_basis="candles for every fill; costs exactly common.py; 2x for gates",
             code_commit=commit, frozen_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             selection_rule="highest DEV alpha t (sleeve 2x on incumbent $70K) among trials with >= 40 trades",
             dev=dict(trades=int(best.trades), alpha_t_70k=float(best.dev_alpha_t_70k),
                      alpha_yr_70k=float(best.dev_alpha_yr_70k), sleeve_sharpe_2x=float(best.dev_sleeve_sharpe_2x),
                      sleeve_sharpe_1x=float(best.dev_sleeve_sharpe_1x), dev_book_sharpe=float(best.dev_book_sharpe),
                      inc70_sharpe=float(best.dev_inc_sharpe_70k)),
             n_trials=int(len(T)), trials=T[["variant", "trades", "dev_alpha_t_70k", "dev_sleeve_sharpe_2x"]]
             .round(4).to_dict("records"))
    with open(os.path.join(OUT, "frozen.json"), "w") as f:
        json.dump(F, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in F.items() if k != "trials"}, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
