#!/usr/bin/env python3
"""Audit E4b: time-of-day structure of futures trading and of the futures-only fills (US/Eastern clock)."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "audit")
T = pd.read_parquet(os.path.join(OUT, "fut_trades_tagged.parquet"))
T["et"] = T.ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
T["et_hour"] = T.et.dt.hour
T["in_5to6pm_et"] = T.et_hour == 17
pd.set_option("display.width", 250)
for ai in (False, True):
    x = T[T.ai == ai]
    print(f"\n=== futures {'rule + AI' if ai else 'rule only'} (17 perps from 2025-12-13): P&L by US/Eastern hour of fill")
    g = x.groupby("et_hour").agg(trades=("net_bp", "size"), fut_only=("spot_reached", lambda s: (~s).mean()),
                                 net_bp=("net_bp", "mean"), pnl=("net_bp", lambda s: s.sum() / 1e4 * 0.25))
    print(g.round(3).T.to_string())
    a = x[x.in_5to6pm_et]
    print(f"5-6pm ET: {len(a)} of {len(x)} trades ({len(a) / len(x):.1%}), P&L {a.net_bp.sum() / 1e4 * .25:.3f} of "
          f"{x.net_bp.sum() / 1e4 * .25:.3f} ({a.net_bp.sum() / x.net_bp.sum():.1%}); futures-only share there {(~a.spot_reached).mean():.2f}")

# futures activity and basis noise by ET hour (ETH, DOGE, LINK)
for c in ["ETH", "DOGE", "LINK", "XLM"]:
    sp = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet")).set_index("ts").close.astype(float)
    fu = pd.read_parquet(os.path.join(ROOT, "data", "cfm", f"{c}.parquet")).set_index("ts")
    fu = fu[(fu.index >= "2025-12-13") & (fu.index < "2026-11-06")]
    i = pd.date_range("2025-12-13", "2026-11-06", freq="min", inclusive="left")
    tr = fu.close.reindex(i).notna()
    et = i.tz_localize("UTC").tz_convert("America/New_York")
    act = tr.groupby(et.hour).mean()
    b = np.log(fu.close / sp.reindex(fu.index)).dropna()
    bdev = (b - b.rolling(240, min_periods=20).median()).abs() * 1e4
    bet = bdev.index.tz_localize("UTC").tz_convert("America/New_York").hour
    lowdev = np.log(fu.low / sp.reindex(fu.index).ffill()).dropna()
    print(f"\n{c}: share of minutes with a futures trade, by ET hour:\n  " + " ".join(f"{h}:{v:.2f}" for h, v in act.items()))
    print(f"{c}: median |basis - 4h median| (bp) by ET hour:\n  " + " ".join(f"{h}:{v:.1f}" for h, v in bdev.groupby(bet).median().items()))
    # minutes 16:55-18:05 ET: any gap?
    m = pd.Series(tr.to_numpy(), index=et)
    mm = m[(m.index.hour == 17) | ((m.index.hour == 16) & (m.index.minute >= 50)) | ((m.index.hour == 18) & (m.index.minute < 10))]
    prof = mm.groupby([mm.index.hour, mm.index.minute]).mean()
    print(f"{c}: share traded by ET minute 16:50-18:09: " + " ".join(f"{h}:{mi:02d}={v:.2f}" for (h, mi), v in prof.items() if mi % 5 == 0 or h == 17 and mi < 3 or h == 18 and mi < 3))
