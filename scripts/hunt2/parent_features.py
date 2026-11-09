#!/usr/bin/env python3
"""Edge hunt 2: pre-fill order-flow features for every research parent fill (R2-08's 4-sigma rung), from Coinbase
prints, computed on the runner (raw prints never leave GitHub Actions).

usage: python scripts/hunt2/parent_features.py <art_dir> <out_dir>
  art_dir: artifacts of the prints runs (art/<run_id>/hunt2-parents-*/prints_<shard>.parquet)
Writes <out_dir>/features_dev.csv (DEV era rows only) and <out_dir>/features_hold.csv (HOLD rows; NOT to be read before
an idea's freeze), plus <out_dir>/coverage.txt (counts only, no outcomes).

Conventions
- side is the MAKER's side: side == "BUY" means an aggressive SELLER hit a resting bid.
- An aggressive order = consecutive prints with the same timestamp and side (one taker order sweeping levels).
- t_fill = time of the first print strictly below the parent's level in its fill minute (the trade-through that fills
  a resting bid at the level). If none, the first print at or below the level. Rows without either are flagged.
- Every feature uses prints in [t_fill - W - 1 s, t_fill - 1 s): information at least 1 second old at the fill.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WINS = (1, 5, 15, 30)                      # minutes before the fill
ROUND = np.array([10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000])


def load(art_dir):
    fs = sorted(glob.glob(os.path.join(art_dir, "**", "prints_*.parquet"), recursive=True))
    print(f"{len(fs)} print files", flush=True)
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


def orders(p):
    """Collapse prints into aggressive orders: same timestamp and same side (consecutive)."""
    p = p.sort_values(["time", "trade_id"])
    key = (p.time != p.time.shift()) | (p.side != p.side.shift())
    oid = key.cumsum()
    g = p.assign(notional=p.price * p["size"], oid=oid).groupby("oid")
    return pd.DataFrame(dict(time=g.time.first(), side=g.side.first(), notional=g.notional.sum(),
                             n_levels=g.price.nunique(), px_first=g.price.first(), px_last=g.price.last()))


def is_round(x, tol=0.005):
    x = np.asarray(x, float)[:, None]
    return (np.abs(x / ROUND[None, :] - 1.0) <= tol).any(axis=1)


def feats(p, t_fill, lvl, adv=np.nan):
    out = {}
    if p.empty:
        return out
    pre = p[p.time < t_fill - pd.Timedelta(seconds=1)]
    o = orders(pre) if len(pre) else pd.DataFrame(columns=["time", "side", "notional", "n_levels"])
    base_rate = len(pre) / 30.0 if len(pre) else np.nan            # prints per minute over the whole window
    for W in WINS:
        lo = t_fill - pd.Timedelta(minutes=W) - pd.Timedelta(seconds=1)
        q = pre[pre.time >= lo]
        oo = o[o.time >= lo] if len(o) else o
        notional = (q.price * q["size"]).to_numpy()
        sell = (q.side == "BUY").to_numpy()
        tot = notional.sum()
        s_not = notional[sell].sum()
        out[f"n_prints_{W}"] = len(q)
        out[f"usd_{W}"] = tot
        out[f"sell_share_{W}"] = s_not / tot if tot > 0 else np.nan
        out[f"rate_ratio_{W}"] = (len(q) / W) / base_rate if base_rate and base_rate > 0 else np.nan
        so = oo[oo.side == "BUY"] if len(oo) else oo
        if len(so):
            sn = so.notional.to_numpy()
            out[f"sell_orders_{W}"] = len(so)
            out[f"sell_med_order_{W}"] = float(np.median(sn))
            out[f"sell_max_order_{W}"] = float(sn.max())
            out[f"sell_big10k_share_{W}"] = float(sn[sn >= 10e3].sum() / sn.sum())
            out[f"sell_big50k_share_{W}"] = float(sn[sn >= 50e3].sum() / sn.sum())
            if adv == adv and adv > 0:                       # blocks relative to the coin's 30-day ADV (5 bp of ADV)
                out[f"sell_bigadv_share_{W}"] = float(sn[sn >= 5e-4 * adv].sum() / sn.sum())
            out[f"sell_small1k_share_{W}"] = float(sn[sn < 1e3].sum() / sn.sum())
            out[f"sell_round_share_{W}"] = float(is_round(sn).mean())
            out[f"sell_hhi_{W}"] = float(((sn / sn.sum()) ** 2).sum())
            out[f"sell_multilevel_share_{W}"] = float((so.n_levels.to_numpy() > 1).mean())
        else:
            out[f"sell_orders_{W}"] = 0
        bo = oo[oo.side == "SELL"] if len(oo) else oo
        out[f"buy_orders_{W}"] = len(bo)
        if len(q) >= 3:
            dp = np.diff(q.price.to_numpy())
            c = np.cov(dp[1:], dp[:-1])[0, 1] if len(dp) > 2 else np.nan
            out[f"roll_bp_{W}"] = 1e4 * 2 * np.sqrt(-c) / q.price.mean() if c == c and c < 0 else 0.0
        if len(q) >= 2:
            px = q.price.to_numpy()
            out[f"ret_bp_{W}"] = 1e4 * (px[-1] / px[0] - 1.0)
            out[f"maxdd_bp_{W}"] = 1e4 * (px.min() / px.max() - 1.0)
            out[f"dist_lvl_bp_{W}"] = 1e4 * (px[-1] / lvl - 1.0)
    return out


def main(art_dir, out_dir):
    W = pd.read_csv(os.path.join(ROOT, "reports", "hunt2", "parents", "windows.csv"), parse_dates=["start", "end", "ts"])
    P = load(art_dir)
    os.makedirs(out_dir, exist_ok=True)
    if P.empty:
        open(os.path.join(out_dir, "coverage.txt"), "w").write("no prints\n")
        return
    P["time"] = pd.to_datetime(P["time"])
    P["side"] = P["side"].str.upper()
    P = P.drop_duplicates(["window_id", "trade_id"])
    g = dict(tuple(P.groupby("window_id")))
    rows, cov = [], {"windows": len(W), "with_prints": 0, "fill_found": 0}
    for w in W.itertuples():
        p = g.get(w.window_id)
        r = dict(window_id=w.window_id, coin=w.coin, ts=w.ts, era=w.era, lvl=w.lvl)
        if p is None or p.empty:
            r["flag"] = "no_prints"
            rows.append(r)
            continue
        cov["with_prints"] += 1
        fm = p[(p.time >= w.ts) & (p.time < w.ts + pd.Timedelta(minutes=1))]
        thr = fm[fm.price < w.lvl]
        at = fm[fm.price <= w.lvl]
        if len(thr):
            t_fill, r["flag"] = thr.time.min(), "through"
        elif len(at):
            t_fill, r["flag"] = at.time.min(), "at_level"
        else:
            t_fill, r["flag"] = w.ts + pd.Timedelta(seconds=30), "no_touch"
        cov["fill_found"] += r["flag"] != "no_touch"
        r["t_fill"] = t_fill
        r["n_prints_window"] = len(p)
        r.update(feats(p, t_fill, w.lvl, getattr(w, "adv", np.nan)))
        rows.append(r)
    F = pd.DataFrame(rows)
    dev = F.era == "sel"
    F[dev].to_csv(os.path.join(out_dir, "features_dev.csv"), index=False)
    F[~dev].to_csv(os.path.join(out_dir, "features_hold.csv"), index=False)
    cov["dev_rows"], cov["hold_rows"] = int(dev.sum()), int((~dev).sum())
    cov["flags_dev"] = F[dev].flag.value_counts().to_dict()
    open(os.path.join(out_dir, "coverage.txt"), "w").write("\n".join(f"{k}: {v}" for k, v in cov.items()) + "\n")
    print(cov)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
