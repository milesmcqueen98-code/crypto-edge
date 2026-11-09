#!/usr/bin/env python3
"""Edge hunt 2, LETF: print windows for the frozen variant's DEV trades (fill-realism check, after the freeze; DEV only).
For each trade: an entry window [decision, decision + 5 min) and an exit window [exit - 5 min, exit + 5 min), UTC, on
the venue the model filled on (Coinbase spot before the perp launch date, the CFM perp after).
usage: python scripts/hunt2/letf/windows.py sel
Writes reports/hunt2/letf/windows.csv (window_id, product, start, end, trade_id, day, asset, kind, t_dec, side,
candle_px).
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import letf as L  # noqa: E402

WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "letf")


def main(era):
    assert era == "sel"
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    p = fz["params"]
    uni = L.UNIVERSE[p["universe"]]
    D = L.signals(era)
    days = L.scored_days(uni, era)
    _, T = L.sleeve(D, p["leg"], p["k"], uni, 50000, mult=2.0, theta=p["theta"], days=days)
    T = T[T.status == "filled"].reset_index(drop=True)
    S = D.set_index(["day", "asset"])
    rows, wid = [], 0
    for i, t in T.iterrows():
        s = S.loc[(t.day, t.asset)]
        prod = L.costs.PERP[t.asset][0] if s.venue == "perp" else f"{t.asset}-USD"
        tin, tout = int(s[f"{p['leg']}_tin"]), int(s[f"{p['leg']}_tout"])
        Tc = int(s.Tc)
        dec_in = Tc + 1 if p["leg"] == "rev" else Tc - 14
        dec_out = Tc + 60 if p["leg"] == "rev" else Tc
        for kind, dec, side, px in (("entry", dec_in, t.side, t.entry), ("exit", dec_out, -t.side, t.exit)):
            t_dec = pd.Timestamp(dec * 60, unit="s")
            start = t_dec - pd.Timedelta(minutes=5 if kind == "exit" else 0)
            rows.append(dict(window_id=wid, product=prod, start=start, end=t_dec + pd.Timedelta(minutes=5), trade_id=i,
                             day=t.day.date(), asset=t.asset, kind=kind, t_dec=t_dec, side=int(side), candle_px=px,
                             venue=s.venue, stale=bool(t.stale) if kind == "exit" else False,
                             contracts=int(t.contracts)))
            wid += 1
    W = pd.DataFrame(rows)
    W.to_csv(os.path.join(OUT, "windows.csv"), index=False)
    print(len(T), "trades,", len(W), "windows;", W.groupby(["venue", "kind"]).size().to_dict())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sel")
