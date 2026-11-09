#!/usr/bin/env python3
"""Edge hunt 2, EXP: fill-realism check of the frozen variant's trades on Coinbase prints (runs on Actions; descriptive,
after the freeze; changes nothing in the frozen variant or its gates).

For every entry and exit of reports/hunt2/exp/hold_read_trades.csv (with|mq|BTC: entry 07:30, exit 08:00 UTC) the
prints of the venue the trade was priced on (spot BTC-USD, or the CFM BTC perp BIP-20DEC30-CDE) are fetched from
t - 30 s to t + 60 s with scripts/hunt2/prints.py. Per order: the first print >= 2 s after t (the prereg's taker fill),
the VWAP of prints in [t + 2 s, t + 32 s], the number of prints, and their difference from the candle open used
(in bp, signed so that positive = the print fill is WORSE for the trade than the candle price).

usage: python scripts/hunt2/exp/verify_fills.py <out_dir_for_raw>   (writes reports/hunt2/exp/fill_check.csv)
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt2"))
import prints  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt2", "exp")


def main(raw_dir):
    T = pd.read_csv(os.path.join(OUT, "hold_read_trades.csv"), parse_dates=["date"])
    T = T[T.contracts > 0].reset_index(drop=True)
    rows = []
    for i, t in T.iterrows():
        prod = "BTC-USD" if t.venue == "spot" else "BIP-20DEC30-CDE"
        for leg, hh, mm, px, sgn in (("entry", 7, 30, t.p_in, t.side), ("exit", 8, 0, t.p_out, -t.side)):
            tt = t.date + pd.Timedelta(hours=hh, minutes=mm)
            rows.append(dict(window_id=len(rows), product=prod, start=tt - pd.Timedelta(seconds=30),
                             end=tt + pd.Timedelta(seconds=60), t=tt, leg=leg, date=t.date, era=t.era, venue=t.venue,
                             candle_px=px, buy=sgn > 0))
    W = pd.DataFrame(rows)
    os.makedirs(raw_dir, exist_ok=True)
    wf = os.path.join(raw_dir, "windows.csv")
    W[["window_id", "product", "start", "end"]].to_csv(wf, index=False)
    prints.main(wf, 0, 1, raw_dir)
    P = pd.read_parquet(os.path.join(raw_dir, "prints_0.parquet"))
    P["time"] = pd.to_datetime(P["time"], utc=True).dt.tz_localize(None)
    P["price"] = pd.to_numeric(P["price"], errors="coerce")
    P["size"] = pd.to_numeric(P["size"], errors="coerce")
    out = []
    for w in W.itertuples():
        p = P[P.window_id == w.window_id].sort_values("time")
        after = p[p.time >= w.t + pd.Timedelta(seconds=2)]
        first = float(after.price.iloc[0]) if len(after) else float("nan")
        lag = (after.time.iloc[0] - w.t).total_seconds() if len(after) else float("nan")
        win = p[(p.time >= w.t + pd.Timedelta(seconds=2)) & (p.time < w.t + pd.Timedelta(seconds=32))]
        vwap = float((win.price * win["size"]).sum() / win["size"].sum()) if len(win) else float("nan")
        s = 1 if w.buy else -1
        out.append(dict(date=w.date.date(), era=w.era, leg=w.leg, venue=w.venue, product=w.product,
                        candle_px=w.candle_px, first_px=first, first_lag_s=lag, vwap30=vwap, n_prints_30s=len(win),
                        first_vs_candle_bp=s * 1e4 * (first / w.candle_px - 1),
                        vwap_vs_candle_bp=s * 1e4 * (vwap / w.candle_px - 1)))
    O = pd.DataFrame(out)
    O.to_csv(os.path.join(OUT, "fill_check.csv"), index=False)
    print(O.round(2).to_string())
    print("mean first-print vs candle (bp, + = worse):", round(O.first_vs_candle_bp.mean(), 2),
          "median:", round(O.first_vs_candle_bp.median(), 2))


if __name__ == "__main__":
    main(sys.argv[1])
