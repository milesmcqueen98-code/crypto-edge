#!/usr/bin/env python3
"""H10 (XQ): the frozen variant over all scored days (run ONLY after the freeze commit of reports/hunt/h10xq/frozen.json).
Sequencing on DEV + HOLD events (prints applied wherever fetched), $30K and $50K, theta 0.5 (gates) and 0.25 (info),
2x (gates) and 1x (info) costs. Writes reports/hunt/h10xq/daily.parquet (s30_2x, s50_2x, s30_1x, s50_1x, and the
theta-0.25 columns), reports/hunt/h10xq/gates.json and reports/hunt/h10xq/frozen_trades.parquet.
usage: python scripts/hunt/h10xq/run_frozen.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import sim  # noqa: E402
import gates  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h10xq")


def top3_share(r):
    x = pd.Series(r)
    p = x[x > 0].sort_values(ascending=False)
    tot = x.sum()
    return float(p.head(3).sum() / tot) if tot > 0 else float("nan")


def main():
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    k, ex, q, H, casc = F["k"], F["exit"], F["qset"], F["H"], F["cascade"]
    E = pd.concat([sim.load_events("dev", q, k, H), sim.load_events("hold", q, k, H)], ignore_index=True)
    E = E.sort_values(["ts", "pair"]).reset_index(drop=True)
    # Scoring basis: candles for every fill, costs exactly as common.py (deviation in REPORT: prints were fetched for a
    # ~1% sample only and are used to measure the candle-vs-print bias). H10_USE_PRINTS=1 applies them (information).
    P = sim.load_prints() if os.environ.get("H10_USE_PRINTS") == "1" else None
    hs = sim.half_spreads(P) if os.environ.get("H10_USE_PRINTS") == "1" else {}
    days = gates.ERA_DAYS
    cols, trades, info = {}, {}, {}
    for C in (30000.0, 50000.0):
        for theta in (0.5, 0.25):
            T = sim.run(E, q, C, theta, ex, casc, P)
            for mult in (2.0, 1.0):
                r, T2, inf = sim.daily_returns(T, q, C, ex, mult, days, hs)
                tag = f"s{int(C / 1000)}_{int(mult)}x" + ("" if theta == 0.5 else "_t025")
                cols[tag] = r
                info[tag] = dict(inf, trades=len(T2), fill_usd=float(T2.fill.sum()) if len(T2) else 0.0,
                                 trades_hold=int((T2.ts >= gates.HOLD0).sum()) if len(T2) else 0,
                                 src=T.src.value_counts().to_dict() if len(T) else {})
                if mult == 2.0:
                    trades[(C, theta)] = T2
    D = pd.DataFrame(cols)
    D.index.name = "day"
    D.to_parquet(os.path.join(OUT, "daily.parquet"))
    T30 = trades[(30000.0, 0.5)]
    T30.to_parquet(os.path.join(OUT, "frozen_trades.parquet"), index=False)
    G = gates.path_b({30000: D.s30_2x, 50000: D.s50_2x}, days=days)
    G1x = gates.path_b({30000: D.s30_1x, 50000: D.s50_1x}, days=days)
    inc = gates.incumbent(100e3, days=days)
    a = G["a"]
    sl = D[f"s{int(round((1 - a) * 100))}_2x"]
    book = a * gates.incumbent(a * 100e3, days=days) + (1 - a) * sl
    worst = inc.nsmallest(20).index
    extra = dict(
        corr_sleeve_inc=float(np.corrcoef(sl, inc)[0, 1]),
        sleeve_on_inc_worst20_days=float(sl.reindex(worst).sum()),
        top3_share_sleeve=top3_share(sl), top3_share_book_gain=top3_share(book - inc),
        sleeve_years_2x={int(y): round(float(v), 4) for y, v in sl.groupby(sl.index.year).sum().items()},
        sleeve_years_1x={int(y): round(float(v), 4) for y, v in
                         D[f"s{int(round((1 - a) * 100))}_1x"].groupby(D.index.year).sum().items()},
        info=info)
    sleeve_alone = gates.sharpe(D.s30_2x) > gates.sharpe(inc)
    out = dict(idea="h10xq", frozen=F, path_b_2x=G, path_b_1x_info=G1x, extra=extra,
               path_a=gates.path_a(D.s30_2x * (100e3 / 30e3), days=days) if sleeve_alone else None,
               note="G4 (DSR) here is provisional: recomputed centrally at the end (prereg deviation 2026-11-07 06:00).")
    with open(os.path.join(OUT, "gates.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    keys = ("a", "full_t_alpha", "dev_t_alpha", "hold_t_alpha", "full_gain", "dev_gain", "hold_gain",
            "full_sleeve_sharpe", "dev_sleeve_sharpe", "hold_sleeve_sharpe", "dsr", "years",
            "G1", "G2", "G3", "G4", "G5", "pass_G1_G5")
    print(json.dumps({k_: G[k_] for k_ in keys}, indent=1, default=str))
    print(json.dumps({k_: G1x[k_] for k_ in ("full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain")}, default=str))
    print(json.dumps({k_: v for k_, v in extra.items() if k_ != "info"}, default=str))
    print(json.dumps(info, default=str)[:3000])


if __name__ == "__main__":
    main()
