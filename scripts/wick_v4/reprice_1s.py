#!/usr/bin/env python3
"""Wick v4, post-hoc check of S2 at 1-second resolution: re-price the 4-sigma bid every second with BTC's live price.

The bid level is exp(x[t-60] + beta * (BTC[t-1] - BTC[t-60]) - 4 sigma). Within a minute only BTC's price is new
information, so re-pricing every second means moving the bid by beta * BTC's move since the minute started.
For each parent fill with trade data (reports/wick_v4/subminute_parents.csv: BTC's move up to the fill, the fill's
gross outcome):
  - the re-priced bid sits beta * btc_to_fill_bp away from the minute bid (lower when BTC fell);
  - the fill is kept if the minute still traded below the re-priced bid (minute low from Coinbase candles);
  - a kept fill is bought at the re-priced level (outcome shifts by the same bp); a lost fill earns 0.
Limitation: fills the re-priced bid would add in minutes the minute bid missed are not in the trade sample.
"""
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "wick_v4")


def main():
    d = pd.read_csv(os.path.join(OUT, "subminute_parents.csv"), parse_dates=["ts"])
    E = pd.read_csv(os.path.join(OUT, "events_research.csv"), parse_dates=["ts"])
    d = d[d.through4].merge(E[E.k == 4][["ts", "coin", "lvl"]], on=["ts", "coin"])
    lows = []
    for c, g in d.groupby("coin"):
        m = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet")).drop_duplicates("ts").set_index("ts")
        lows.append(pd.Series(m.low.reindex(g.ts).to_numpy(), index=g.index))
    d["low"] = pd.concat(lows)
    d["depth_bp"] = 1e4 * np.log(d.lvl / d.low)
    d["period"] = np.where(d.ts < "2026-04-01", "selection", "check")
    rows = []
    for beta in (0.75, 1.0, 1.25):
        shift = beta * d.btc_to_fill_bp
        kept = d.depth_bp > -shift
        new_out = np.where(kept, d.outcome_bp - shift, 0.0)
        for per in ("selection", "check", "all"):
            m = (d.period == per).to_numpy() if per != "all" else np.ones(len(d), bool)
            rows.append(dict(beta=beta, period=per, fills=int(m.sum()), kept_share=kept[m].mean(),
                             gross_per_fill_minute_bp=d.outcome_bp[m].mean(), gross_per_fill_1s_bp=new_out[m].mean(),
                             kept_fills_bp=(d.outcome_bp - shift)[m & kept].mean(),
                             lost_fills_bp=d.outcome_bp[m & ~kept].mean()))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "reprice_1s.csv"), index=False)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
