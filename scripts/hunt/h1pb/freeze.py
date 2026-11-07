#!/usr/bin/env python3
"""Write reports/hunt/h1pb/frozen.json from reports/hunt/h1pb/dev_trials.csv by the pre-registered rule: the highest
DEV alpha t (sleeve at 2x costs on the incumbent at $70K) among trials with >= 40 trades; ties to the simpler variant.
The commit that adds frozen.json is the freeze."""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import book as B  # noqa: E402

R = pd.read_csv(os.path.join(B.REP, "dev_trials.csv"))
ok = R[(R.trades >= 40) & np.isfinite(R.t_alpha70)].copy()
ok["t_r"] = ok.t_alpha70.round(6)
sel = ok.sort_values(["t_r", "simplicity"], ascending=[False, True]).iloc[0]
code = subprocess.run(["git", "-C", B.ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
fz = dict(idea="h1pb", variant=dict(name=sel.variant, mode=sel["mode"], k=float(sel.k), side=sel.side, H=int(sel.H),
                                    tod=sel.tod, theta=0.5, target_usd=10_000, take_profit=0.6, max_open=6,
                                    gross_cap="3x sleeve capital", stop_loss=None),
          rule="highest DEV alpha t (sleeve $30K at 2x on incumbent $70K) among trials with >= 40 trades; ties simpler",
          start=os.environ.get("H1_START", "2025-07-19"),
          dev=dict(trades=int(sel.trades), sleeve_sharpe_2x=float(sel.sleeve_sharpe), t_alpha70=float(sel.t_alpha70),
                   t_alpha100=float(sel.t_alpha100), dev_book_sharpe=float(sel.dev_book_sharpe),
                   dev_inc70_sharpe=float(sel.dev_inc70_sharpe), pnl_usd_30k_2x=float(sel.pnl_usd), net_bp=float(sel.net_bp)),
          n_dev_trials=int(len(R)), code_commit=code,
          eligible=bool(len(ok) > 0))
with open(os.path.join(B.REP, "frozen.json"), "w") as f:
    json.dump(fz, f, indent=1)
print(json.dumps(fz, indent=1))
