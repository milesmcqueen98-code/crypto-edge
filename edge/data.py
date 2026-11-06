"""Load the per-coin CSVs written by scripts/fetch_data.py into date x coin matrices."""
import glob
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(root=ROOT):
    closes, dvols = {}, {}
    for path in glob.glob(os.path.join(root, "data", "prices", "*.csv")):
        base = os.path.basename(path)[:-4]
        df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
        df = df[df["close"] > 0]
        if len(df) < 30:
            continue
        closes[base] = df["close"]
        dvols[base] = df["volume"] * df["close"]          # USD volume on the source venue
    close = pd.DataFrame(closes).sort_index().asfreq("D")
    dvol = pd.DataFrame(dvols).reindex(close.index)
    # drop coins that never move (pegged assets the exclusion list missed)
    r = close.pct_change(fill_method=None)
    pegged = [c for c in close if r[c].abs().median() < 0.002 and r[c].std() < 0.01]
    close, dvol = close.drop(columns=pegged), dvol.drop(columns=pegged)
    ret = close.pct_change(fill_method=None).clip(-0.95, 3.0)
    return close, dvol, ret


def load_funding(root=ROOT):
    out = {}
    for path in glob.glob(os.path.join(root, "data", "funding", "*.csv")):
        df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        out[os.path.basename(path)[:-4]] = df["funding_daily"]
    return pd.DataFrame(out).sort_index() if out else pd.DataFrame()
