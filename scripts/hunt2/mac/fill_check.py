#!/usr/bin/env python3
"""MAC, after the freeze and the HOLD read: confirm with Coinbase prints that the parents the frozen rule skipped in the
HOLD eras traded through their levels inside the release windows (the SPEC's fill-time check; the DEV check used
reports/hunt2/parents/features_dev.csv). Runs on Actions, because raw prints never leave the runners:
  python scripts/hunt2/mac/fill_check.py <art_dir> <out_csv>
Inputs: reports/hunt2/mac/frozen.json, skipped_chk.csv, skipped_early.csv (written by mac.py hold),
reports/hunt2/parents/windows.csv, data/hunt2/macro/releases.csv, and the shared parent prints (art_dir).
t_fill = the first print strictly below the parent's level in its fill minute, else the first print at or below it
(scripts/hunt2/parent_features.py's definition). No P&L or outcome is computed.
"""
import glob
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def main(art_dir, out_csv):
    fz = json.load(open(os.path.join(ROOT, "reports", "hunt2", "mac", "frozen.json")))
    a, b, evs = fz["params"]["a"], fz["params"]["b"], fz["params"]["event_set"]
    S = pd.concat([pd.read_csv(os.path.join(ROOT, "reports", "hunt2", "mac", f"skipped_{e}.csv"), parse_dates=["ts"])
                   for e in ("chk", "early")], ignore_index=True)
    W = pd.read_csv(os.path.join(ROOT, "reports", "hunt2", "parents", "windows.csv"), parse_dates=["start", "end", "ts"])
    W = W.merge(S[["ts", "coin"]], on=["ts", "coin"])
    R = pd.read_csv(os.path.join(ROOT, "data", "hunt2", "macro", "releases.csv"))
    R = R[R.event.isin(evs)].copy()
    R["rts"] = pd.to_datetime(R.ts_utc)
    ids = set(W.window_id)
    parts = []
    for f in sorted(glob.glob(os.path.join(art_dir, "**", "prints_*.parquet"), recursive=True)):
        p = pd.read_parquet(f)
        parts.append(p[p.window_id.isin(ids)])
    P = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["window_id", "time", "price"])
    P["time"] = pd.to_datetime(P["time"])
    if getattr(P["time"].dt, "tz", None) is not None:
        P["time"] = P["time"].dt.tz_convert("UTC").dt.tz_localize(None)
    P = P.drop_duplicates(["window_id", "trade_id"]) if "trade_id" in P else P
    g = dict(tuple(P.groupby("window_id")))
    rows = []
    for w in W.itertuples():
        j = (R.rts - w.ts).abs().idxmin()
        rts, ev = R.rts[j], R.event[j]
        r = dict(era=w.era, coin=w.coin, fill_minute=w.ts, event=ev, release=rts,
                 minute_off=(w.ts - rts) / pd.Timedelta(minutes=1))
        p = g.get(w.window_id)
        if p is None or p.empty:
            r["flag"] = "no_prints"
        else:
            fm = p[(p.time >= w.ts) & (p.time < w.ts + pd.Timedelta(minutes=1))]
            thr, at = fm[fm.price < w.lvl], fm[fm.price <= w.lvl]
            if len(thr):
                r["t_fill_print"], r["flag"] = thr.time.min(), "through"
            elif len(at):
                r["t_fill_print"], r["flag"] = at.time.min(), "at_level"
            else:
                r["flag"] = "no_touch"
            if "t_fill_print" in r:
                r["print_off_s"] = (r["t_fill_print"] - rts).total_seconds()
                r["print_in_window"] = bool(rts - pd.Timedelta(minutes=a) <= r["t_fill_print"]
                                            < rts + pd.Timedelta(minutes=b + 1))
        rows.append(r)
    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(out.flag.value_counts().to_dict(), "in window:", int(out.get("print_in_window", pd.Series(dtype=bool))
                                                                .fillna(False).sum()), "of", len(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
