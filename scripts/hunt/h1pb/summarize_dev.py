#!/usr/bin/env python3
"""H1 DEV-stage summary (DEV only): fetch completeness, candle-vs-print confirmation, trigger counts.
Writes reports/hunt/h1pb/dev_fetch.csv and dev_confirm.csv."""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import book as B  # noqa: E402
import diag  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 200)
F = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(B.REP, "dev", "fetchlog_*.csv")))], ignore_index=True)
fx = F[F.kind.isin(["perp", "spot"])]
g = fx.groupby(["coin", "kind"]).agg(chunks=("pid", "size"), trades=("trades", "sum"), requests=("requests", "sum"),
                                     lost_seconds=("lost_seconds", "sum"), secs=("secs", "sum"),
                                     print_contracts=("print_contracts", "sum"), candle_contracts=("candle_contracts", "sum"),
                                     fetched_minutes=("fetched_minutes", "sum"))
g["print_vs_candle"] = g.print_contracts / g.candle_contracts
print(g.round(4).to_string())
g.to_csv(os.path.join(B.REP, "dev_fetch.csv"))
p = F[F.kind == "perp"].copy()
p["month"] = pd.to_datetime(p.a).dt.to_period("M")
m = p.groupby("month").agg(print_c=("print_contracts", "sum"), candle_c=("candle_contracts", "sum"))
m["ratio"] = m.print_c / m.candle_c
print("\nperp print vs candle contracts by chunk-start month:\n", m.round(4).to_string())
tr = F[F.kind.str.startswith("triggers")].copy()
tr["v"] = tr.kind.str.replace("triggers_", "")
t = tr.groupby("v").agg(triggers=("trades", "sum"), size_ge1=("requests", "sum"))
print("\ntriggers (all, and with >= 1 contract at theta 0.5):\n", t.to_string())
C = diag.confirmation("dev")
C.to_csv(os.path.join(B.REP, "dev_confirm.csv"), index=False)
print("\ncandle-vs-print confirmation (minute mode, DEV):\n", C.round(3).to_string(index=False))
