#!/usr/bin/env python3
"""Ladder v6 exits, kappa(m) (reports/ladder_v6x_prereg.md, "Exit costs at any minute"): print windows around the
300 pre-drawn selection-era tranches of reports/ladder_v6x/kappa/sample.csv.

The market sale at event minute m is at T_m = fill_t + (m + 1) min (the close of the candle that starts fill_t + m),
m in (2, 5, 10, 20, 30, 45, 60). Red team 2 measures its half-spread in [T_m - 5 min, T_m + 1 min) and its depth in
[T_m - 5 min, T_m + 5 min), so one window per event, [fill_t - 3 min, fill_t + 67 min), covers every minute with a
minute to spare on each side. Overlapping windows of a product are merged (gaps under 5 minutes are bridged) exactly
as red team 2's windows.py (scripts/ladder_v5/redteam2/windows.py on ladder/redteam2) does.
Selection era only: every window must lie inside 2025-01-01 .. 2026-03-31.
Writes reports/ladder_v6x/kappa/windows.csv (product, start, end, era_tag, window_id).
"""
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
KD = os.path.join(ROOT, "reports", "ladder_v6x", "kappa")
PRE, POST = -3, 67                                       # window per event: [fill_t + PRE, fill_t + POST) minutes
SEL = (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-04-01"))


def merge(F, pre=PRE, post=POST, gap=5):
    """red team 2's windows.merge, unchanged: per (coin, era) windows [fill_t + pre, fill_t + post), merged when they
    overlap or are less than `gap` minutes apart."""
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


def main():
    S = pd.read_csv(os.path.join(KD, "sample.csv"), parse_dates=["fill_t"])
    assert (S.era_tag == "main").all()
    F = S[["coin", "fill_t", "era_tag"]].drop_duplicates()
    W = merge(F)
    assert (W.start >= SEL[0]).all() and (W.end <= SEL[1]).all(), "a window falls outside the selection era"
    W.to_csv(os.path.join(KD, "windows.csv"), index=False)
    mins = (W.end - W.start).dt.total_seconds() / 60
    print(f"{len(S)} events, {len(F)} distinct (coin, fill minute) -> {len(W)} windows, {mins.sum():,.0f} minutes "
          f"(median {mins.median():.0f}, max {mins.max():.0f}); {W['product'].nunique()} products; "
          f"{W.start.min()} .. {W.end.max()}")


if __name__ == "__main__":
    main()
