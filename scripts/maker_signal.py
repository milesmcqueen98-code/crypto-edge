#!/usr/bin/env python3
"""Maker round, step 1 (pre-registered): fit the reversal signal on development data only.

E_i = -beta * u_i, u_i = 15-minute log return of coin i minus the cross-sectional mean (5 coins).
beta: pooled OLS (no intercept) of the forward 15-minute relative log return on u_i, using 1-minute
Coinbase closes from 2024-01-01 to 2025-06-30. E_ref: 80th percentile of |E_i| in the same sample.
Writes reports/maker_signal.json.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
START, END = "2024-01-01", "2025-07-01"
L = 15


def main():
    idx = pd.date_range(START, END, freq="min", inclusive="left")
    px = {}
    for c in COINS:
        df = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet")).drop_duplicates("ts").set_index("ts")
        px[c] = df["close"].astype(float).reindex(idx).ffill(limit=10)
    lp = np.log(pd.DataFrame(px))
    back = lp - lp.shift(L)
    fwd = lp.shift(-L) - lp
    u = back.sub(back.mean(axis=1), axis=0)
    f = fwd.sub(fwd.mean(axis=1), axis=0)
    ok = u.notna().all(axis=1) & f.notna().all(axis=1)
    U, F = u[ok].to_numpy().ravel(), f[ok].to_numpy().ravel()
    beta = -float((U * F).sum() / (U * U).sum())
    # standard error with day clusters (overlapping 15-minute windows make minute-level SEs too small)
    day = np.repeat(u[ok].index.floor("D").to_numpy(), len(COINS))
    resid = F + beta * U
    g = pd.DataFrame({"d": day, "s": U * resid}).groupby("d")["s"].sum().to_numpy()
    se = float(np.sqrt((g ** 2).sum()) / (U * U).sum())
    E = -beta * U * 1e4
    eref = float(np.percentile(np.abs(E), 80))
    out = dict(beta=beta, beta_se_day_cluster=se, beta_t=beta / se, E_ref_bp=eref,
               E_abs_median_bp=float(np.median(np.abs(E))), u_sd_bp=float(U.std() * 1e4),
               n_minutes=int(ok.sum()), sample=f"{START} to 2025-06-30", coins=COINS, lookback_min=L)
    print(json.dumps(out, indent=2))
    with open(os.path.join(ROOT, "reports", "maker_signal.json"), "w") as fh:
        json.dump(out, fh, indent=2)


if __name__ == "__main__":
    main()
