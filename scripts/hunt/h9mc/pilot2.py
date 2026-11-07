#!/usr/bin/env python3
"""H9 (MC) pilot 2: why does TradeFetcher.window lose volume on multi-page windows? Logs each request of a paged
fetch and compares paged vs chunked fetches with candle volume per minute. Counts only, DEV days only."""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

OUT = os.path.join(common.ROOT, "reports", "hunt", "h9mc", "pilot2.json")
f = common.TradeFetcher()
res = {}


def raw(pid, s, e):
    tr = f._get(pid, s, e)
    ts = sorted(pd.Timestamp(t["time"]).timestamp() for t in tr)
    return tr, dict(start=s, end=e, n=len(tr), tmin=ts[0] if ts else None, tmax=ts[-1] if ts else None)


for coin, s0, e0 in [("ETH", "2026-03-11 19:30", "2026-03-11 21:10"), ("SOL", "2025-10-15 19:30", "2025-10-15 21:10"),
                     ("BTC", "2026-03-11 17:30", "2026-03-11 18:30")]:
    pid = common.PERP[coin][0]
    s, e = int(pd.Timestamp(s0).timestamp()), int(pd.Timestamp(e0).timestamp())
    # 1) paged exactly like TradeFetcher.window, logging each request
    log, seen, rows, ee = [], set(), [], e
    while ee > s:
        tr, info = raw(pid, s, ee)
        new = [t for t in tr if t["trade_id"] not in seen]
        info["new"] = len(new)
        log.append(info)
        for t in new:
            seen.add(t["trade_id"]); rows.append(t)
        if len(tr) < 1000 or not new:
            break
        e_new = int(info["tmin"])
        ee = e_new if e_new < ee else ee - 1
    paged = pd.DataFrame(rows)
    # 2) chunked: 5-minute chunks overlapping by 1 s
    seen2, rows2, clog = set(), [], []
    for cs in range(s, e, 300):
        tr, info = raw(pid, cs, min(e, cs + 301))
        clog.append(info)
        for t in tr:
            if t["trade_id"] not in seen2:
                seen2.add(t["trade_id"]); rows2.append(t)
    chunk = pd.DataFrame(rows2)
    cand = common.load_perp(coin)
    cand = cand[(cand.index >= pd.Timestamp(s0)) & (cand.index < pd.Timestamp(e0))].volume / common.PERP[coin][1]
    out = {}
    for name, d in (("paged", paged), ("chunk", chunk)):
        d = d.copy()
        d["time"] = pd.to_datetime(d["time"], utc=True).dt.tz_convert(None)
        d["size"] = d["size"].astype(float)
        m = d.groupby(d.time.dt.floor("min"))["size"].sum()
        j = pd.concat([m.rename("p"), cand.rename("c")], axis=1).fillna(0)
        bad = j[(j.p - j.c).abs() > 1e-9]
        out[name] = dict(n=len(d), contracts=float(d["size"].sum()), candle=float(cand.sum()),
                         minutes_mismatch=len(bad), mismatch_head=[(str(k), float(r.p), float(r.c)) for k, r in bad.head(8).iterrows()])
    out["paged_requests"] = log
    out["chunk_full"] = sum(1 for c in clog if c["n"] >= 1000)
    out["ids_only_in_chunk"] = len(seen2 - seen)
    out["ids_only_in_paged"] = len(seen - seen2)
    res[f"{coin} {s0}"] = out
    print(json.dumps(out, default=str)[:3000], flush=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w"), indent=1, default=str)
print("requests", f.n_req)
