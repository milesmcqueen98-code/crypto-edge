#!/usr/bin/env python3
"""Edge hunt 2: print windows around every research parent fill (R2-08 4-sigma rung) in the frozen dataset, all eras.
Writes reports/hunt2/parents/windows.csv (window_id, product, start, end, coin, ts, era, lvl). Downloading prints that
cover HOLD dates is allowed; computing anything on them before an idea's freeze is not (reports/hunt2_prereg.md).
usage: python scripts/hunt2/parent_windows.py [pre_minutes] [post_minutes]
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frozen_sim as F  # noqa: E402
import h2gates as G  # noqa: E402


def main(pre=30, post=2):
    rows = []
    for tag in ("main", "early"):
        P = F.RL.inputs(tag)["P"]
        par = P[(P.k == 4.0) & P.filled].copy()
        for r in par.itertuples():
            rows.append(dict(product=f"{r.coin}-USD", start=r.ts - pd.Timedelta(minutes=pre),
                             end=r.ts + pd.Timedelta(minutes=post), coin=r.coin, ts=r.ts, lvl=r.lvl, adv=r.adv,
                             vol_d=r.vol_d))
    W = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
    W["era"] = G.era_of(W.ts.dt.floor("D"))
    W = W[W.era != ""].reset_index(drop=True)
    W.insert(0, "window_id", range(len(W)))
    out = os.path.join(G.ROOT, "reports", "hunt2", "parents")
    os.makedirs(out, exist_ok=True)
    W.to_csv(os.path.join(out, "windows.csv"), index=False)
    print(W.groupby("era").size().to_dict(), len(W))


if __name__ == "__main__":
    main(*[int(x) for x in sys.argv[1:3]])
