#!/usr/bin/env python3
"""Red team 2 (ladder v5): print windows around every possible 60-minute time exit of R2-08's rungs.

A rung's unsold remainder is sold at the close of the candle that starts 60 minutes after its fill minute; the passive
candidate (C3) rests it for up to 15 more minutes and sells the leftover at the close of the candle 60+N minutes after
the fill. The live book can fill a deeper rung later than the research data (hsim.with_live_fills: the first
trade-through after the rung is placed), so every trade-through minute of every deeper rung (deep_paths_<tag>.pkl)
is a possible fill minute. Window per possible fill minute f: [f + 55 min, f + 82 min): five minutes before the exit
candle (for the spread and depth around the market exit) to six minutes after the 15-minute passive window.
Overlapping windows of a product are merged (gaps under 5 minutes are bridged).
Writes reports/ladder_v5/redteam2/windows_exit.csv (product, start, end, era_tag, window_id).
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "ladder_v5", "redteam2")


def fill_minutes(tag):
    P = pd.read_pickle(os.path.join(ROOT, "reports", "ladder_v5", "frozen", f"pre_hunt_{tag}.pkl"))
    DP = pd.read_pickle(os.path.join(ROOT, "reports", "ladder_v5", f"deep_paths_{tag}.pkl"))
    rows = []
    for r in P[P.filled].itertuples():
        rows.append((r.coin, r.ts + pd.Timedelta(minutes=int(r.f_off))))
    for rix, D in DP.items():
        if D is None or not len(D):
            continue
        r = P.loc[rix]
        for off in D.off.to_numpy():
            rows.append((r.coin, r.ts + pd.Timedelta(minutes=int(off))))
    F = pd.DataFrame(rows, columns=["coin", "fill_t"]).drop_duplicates()
    F["era_tag"] = tag
    return F


def merge(F, pre=55, post=82, gap=5):
    out = []
    for (coin, tag), g in F.groupby(["coin", "era_tag"]):
        s = (g.fill_t + pd.Timedelta(minutes=pre)).sort_values().to_numpy()
        e = (g.fill_t + pd.Timedelta(minutes=post)).sort_values().to_numpy()
        cur_s, cur_e = s[0], e[0]
        for a, b in zip(s[1:], e[1:]):
            if a <= cur_e + pd.Timedelta(minutes=gap).to_timedelta64():
                cur_e = max(cur_e, b)
            else:
                out.append((f"{coin}-USD", cur_s, cur_e, tag))
                cur_s, cur_e = a, b
        out.append((f"{coin}-USD", cur_s, cur_e, tag))
    W = pd.DataFrame(out, columns=["product", "start", "end", "era_tag"]).sort_values(["start", "product"])
    W["window_id"] = range(len(W))
    return W.reset_index(drop=True)


def main(tags):
    F = pd.concat([fill_minutes(t) for t in tags])
    W = merge(F)
    os.makedirs(OUT, exist_ok=True)
    W.to_csv(os.path.join(OUT, "windows_exit.csv"), index=False)
    mins = (W.end - W.start).dt.total_seconds() / 60
    print(f"{len(F)} possible fill minutes -> {len(W)} windows, {mins.sum():,.0f} minutes "
          f"(median {mins.median():.0f}, max {mins.max():.0f}); by era {W.groupby('era_tag').size().to_dict()}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["main", "early"])
