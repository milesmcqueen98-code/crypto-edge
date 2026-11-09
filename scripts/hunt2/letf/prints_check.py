#!/usr/bin/env python3
"""Edge hunt 2, LETF: check the frozen variant's DEV candle fills against Coinbase prints (runs on Actions with the
prints of scripts/hunt2/prints.py in art/<run_id>/; DEV windows only, after the freeze).

For every entry/exit (reports/hunt2/letf/windows.csv, side +1 = we buy):
  p_first  the first print >= decision + 2 s (any side)
  p_side   the first print >= decision + 2 s on the side a market order takes (we buy: a resting offer was lifted,
           maker side SELL; we sell: maker side BUY)
  p_sweep  the volume-weighted price of our-side prints from decision + 2 s until they add up to our size (NaN if the
           window's our-side prints are smaller than our size)
  For exits the model took before the Friday CFM maintenance (stale), the last print before the decision is used.
  adverse_bp = how much worse than the candle price p_side (and p_sweep) is for us; the model charges 1.5x the
  measured perp half-spread on top of the candle price (hs15_bp).
usage: python scripts/hunt2/letf/prints_check.py <art dir>
Writes reports/hunt2/letf/prints_check_dev.csv (per leg) and prints_check_trades_dev.csv (per trade).
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "hunt2", "letf")
CSIZE = {"BTC": 0.01, "ETH": 0.1, "SOL": 5, "XRP": 500}
HS15 = {}


def hs15(asset):
    if not HS15:
        s = pd.read_csv(os.path.join(ROOT, "reports", "cfm_book_summary.csv"))
        s = s[s.kind == "perp"]
        HS15.update({r.root: 1.5 * r.spread_bp_median / 2 for r in s.itertuples()})
    return HS15.get(asset, 7.5)


def main(art):
    W = pd.read_csv(os.path.join(OUT, "windows.csv"), parse_dates=["start", "end", "t_dec"])
    files = sorted(glob.glob(os.path.join(art, "**", "prints_*.parquet"), recursive=True))
    P = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    P["time"] = pd.to_datetime(P["time"], utc=True, format="ISO8601").dt.tz_localize(None)
    P["price"], P["size"] = P.price.astype(float), P["size"].astype(float)
    print(len(files), "files,", len(P), "prints,", P.window_id.nunique(), "windows with prints")
    rows = []
    for w in W.itertuples():
        x = P[P.window_id == w.window_id].sort_values(["time", "trade_id"])
        perp = w.product.endswith("-CDE")
        qty = w.contracts * CSIZE[w.asset]                       # our size in coins
        size_coin = x["size"] * (CSIZE[w.asset] if perp else 1.0)
        our = "SELL" if w.side > 0 else "BUY"                   # maker side of the prints a market order takes
        t2 = w.t_dec + pd.Timedelta(seconds=2)
        if w.kind == "exit" and w.stale:
            b = x[x.time < w.t_dec]
            bs = b[b.side == our]
            p_first = b.price.iloc[-1] if len(b) else np.nan
            p_side = bs.price.iloc[-1] if len(bs) else np.nan
            p_sweep, delay = np.nan, (w.t_dec - b.time.iloc[-1]).total_seconds() if len(b) else np.nan
        else:
            a = x[x.time >= t2]
            asd = a[a.side == our]
            p_first = a.price.iloc[0] if len(a) else np.nan
            p_side = asd.price.iloc[0] if len(asd) else np.nan
            delay = (a.time.iloc[0] - w.t_dec).total_seconds() if len(a) else np.nan
            sc = size_coin.loc[asd.index]
            cum = sc.cumsum()
            if len(asd) and cum.iloc[-1] >= qty:
                n = int(np.searchsorted(cum.to_numpy(), qty) + 1)
                pp, ss = asd.price.iloc[:n].to_numpy(), sc.iloc[:n].to_numpy().copy()
                ss[-1] -= cum.iloc[n - 1] - qty
                p_sweep = float((pp * ss).sum() / ss.sum())
            else:
                p_sweep = np.nan
        adv = lambda p: w.side * (p - w.candle_px) / w.candle_px * 1e4  # noqa: E731
        rows.append(dict(window_id=w.window_id, trade_id=w.trade_id, day=w.day, asset=w.asset, venue=w.venue,
                         kind=w.kind, side=w.side, stale=w.stale, contracts=w.contracts, candle_px=w.candle_px,
                         p_first=p_first, p_side=p_side, p_sweep=p_sweep, delay_s=delay, n_prints=len(x),
                         adverse_first_bp=adv(p_first), adverse_side_bp=adv(p_side), adverse_sweep_bp=adv(p_sweep),
                         hs15_bp=hs15(w.asset)))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "prints_check_dev.csv"), index=False)
    tr = []
    for tid, g in R.groupby("trade_id"):
        e, x = g[g.kind == "entry"].iloc[0], g[g.kind == "exit"].iloc[0]
        s = e.side
        gc = s * (x.candle_px - e.candle_px) / e.candle_px * 1e4
        gp = s * (x.p_side - e.p_side) / e.p_side * 1e4
        tr.append(dict(trade_id=tid, day=e.day, asset=e.asset, venue=e.venue, side=s, gross_candle_bp=gc,
                       gross_prints_bp=gp, model_hs_cost_bp=2 * e.hs15_bp, gross_candle_less_hs_bp=gc - 2 * e.hs15_bp))
    T = pd.DataFrame(tr)
    T.to_csv(os.path.join(OUT, "prints_check_trades_dev.csv"), index=False)
    print(R.groupby(["venue", "kind"])[["adverse_side_bp", "adverse_sweep_bp", "hs15_bp", "delay_s"]].median())
    print(T[["gross_candle_bp", "gross_prints_bp", "gross_candle_less_hs_bp"]].describe())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "art")
