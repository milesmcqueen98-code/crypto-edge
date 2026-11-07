#!/usr/bin/env python3
"""Ladder v5, step 1b: markouts by fill type, selection era only (Jan 2025 - Mar 2026).

Hypotheses are generated here; the check era (Apr - Nov 2026) and the 2022-23 era are not split by these variables
before the pre-registered tests. Every filled tranche of the incumbent ($250K, theta 0.5, instant bound) gets:
  outcome: net bp per $ bought, gross bp, take-profit hit, markouts at +1/+5/+15/+30/+60 min (minute closes vs the bid);
  fill type (variables fixed before looking):
    rung (4/6/8 sigma); BTC's move in the fill minute; BTC's 15-minute move before the minute (known at arm time);
    sweep depth below the bid (bp and sigma); fill-minute volume / the coin's median minute volume over the prior day;
    capacity ratio (theta x volume through the bid / wanted size); cascade breadth (other coins with a 4-sigma fill
    within +-2 minutes); the AI's margin over its threshold (parent's); hour (ET); volume through the bid / ADV.
Writes reports/ladder_v5/diag_markouts_sel.csv (per tranche) and diag_markouts_sel.txt (tables).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402

ROOT, OUT = fsim.ROOT, fsim.OUT


def minute(c, src="minute"):
    d = pd.read_parquet(os.path.join(ROOT, "data", src, f"{c}.parquet")).drop_duplicates("ts").set_index("ts").sort_index()
    return d[d.volume > 0]


def build(era="sel", C=250e3, theta=0.5):
    tag, (lo, hi) = fsim.ERAS[era]
    P = fsim.load(tag)
    _, out = fsim.book(P, era, theta=theta, C=C)
    Q = out["instant"][0]
    Q = Q[Q.fill > 0].copy()
    T = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", f"trades_{tag}.parquet"))
    T = T.set_index(["ts", "coin"])
    src = "minute" if tag == "main" else "minute_early"
    btc = minute("BTC", src)
    bo, bc = btc.open, btc.close
    rows = []
    parents = Q[Q.k == 4.0][["fill_t", "coin"]]
    for c, g in Q.groupby("coin"):
        m = minute(c, src)
        medv = m.volume.rolling(1440, min_periods=300).median().shift(1)
        for r in g.itertuples():
            t = r.fill_t
            if t not in m.index:
                continue
            low = float(m.at[t, "low"])
            sig_bp = np.nan
            tr = T.loc[(r.ts, c)] if (r.ts, c) in T.index else None
            if tr is not None and isinstance(tr, pd.DataFrame):
                tr = tr.iloc[0]
            if tr is not None:
                sig_bp = 1e4 * float(tr.sig)
            path = r.path.astype(np.float64) * 1e4
            rec = dict(ts=r.ts, fill_t=t, coin=c, k=r.k, fill=r.fill, want=r.want, net_bp=1e4 * r.pnl / r.fill,
                       gross_bp=1e4 * r.gross / r.fill, tp_hit=bool(r.tp_off >= 0), tp_share=r.tp_fill / r.fill,
                       m1=path[1], m5=path[5], m15=path[15], m30=path[30], m60=path[60],
                       btc_fill_bp=1e4 * np.log(bc.get(t, np.nan) / bo.get(t, np.nan)),
                       btc_pre15_bp=1e4 * np.log(bc.get(t - pd.Timedelta(minutes=1), np.nan) /
                                                 bc.get(t - pd.Timedelta(minutes=16), np.nan)),
                       depth_bp=1e4 * np.log(r.lvl / low), sig_bp=sig_bp,
                       vol_rel=float(m.at[t, "volume"] / medv.get(t, np.nan)),
                       cap_ratio=theta * r.in_spot / r.want if r.want > 0 else np.nan,
                       thru_adv=r.in_spot / r.adv if r.adv > 0 else np.nan,
                       margin=float(tr.pred - tr.thr) if tr is not None else np.nan,
                       hour_et=(t.tz_localize("UTC").tz_convert("America/New_York")).hour)
            rec["depth_sig"] = rec["depth_bp"] / sig_bp if sig_bp and np.isfinite(sig_bp) else np.nan
            near = parents[(parents.fill_t >= t - pd.Timedelta(minutes=2)) & (parents.fill_t <= t + pd.Timedelta(minutes=2))]
            rec["breadth"] = int(near.coin.nunique() - (1 if c in set(near.coin) else 0))
            rows.append(rec)
    return pd.DataFrame(rows)


def tables(D):
    lines = []
    w = lambda x: np.average(x.net_bp, weights=x.fill)  # noqa: E731

    def summ(g):
        return pd.Series(dict(n=len(g), usd_k=g.fill.sum() / 1e3, net_bp_w=w(g), net_bp=g.net_bp.mean(),
                              gross_bp=g.gross_bp.mean(), tp=g.tp_hit.mean(), m1=g.m1.mean(), m5=g.m5.mean(),
                              m15=g.m15.mean(), m60=g.m60.mean()))
    lines.append("ALL\n" + summ(D).round(1).to_string())
    lines.append("\nby rung\n" + D.groupby("k").apply(summ).round(1).to_string())
    for v in ("btc_fill_bp", "btc_pre15_bp", "depth_bp", "depth_sig", "vol_rel", "cap_ratio", "thru_adv", "margin",
              "breadth", "sig_bp"):
        x = D.dropna(subset=[v])
        if v == "breadth":
            q = pd.cut(x[v], [-1, 0, 1, 3, 100], labels=["0", "1", "2-3", "4+"])
        elif v == "cap_ratio":
            q = pd.cut(x[v], [-1, 1, 2, 5, 1e12], labels=["<1 (bound)", "1-2", "2-5", ">5"])
        else:
            q = pd.qcut(x[v], 5, labels=False, duplicates="drop")
        t = x.groupby(q, observed=True).apply(summ)
        rng = x.groupby(q, observed=True)[v].agg(["min", "max"])
        t = pd.concat([rng, t], axis=1)
        rho = x[[v, "net_bp"]].corr("spearman").iloc[0, 1]
        lines.append(f"\nby {v} (Spearman with net bp {rho:+.3f})\n" + t.round(1).to_string())
    lines.append("\nby hour ET (4-hour blocks)\n" + D.groupby(D.hour_et // 4 * 4).apply(summ).round(1).to_string())
    lines.append("\nby coin\n" + D.groupby("coin").apply(summ).round(1).sort_values("usd_k").to_string())
    # does the early markout predict the outcome? (exit information)
    for m in ("m1", "m5", "m15"):
        x = D.dropna(subset=[m])
        q = pd.qcut(x[m], 5, labels=False, duplicates="drop")
        t = x.groupby(q).apply(summ)
        lines.append(f"\nby markout {m} (Spearman with net bp {x[[m, 'net_bp']].corr('spearman').iloc[0, 1]:+.3f})\n"
                     + t.round(1).to_string())
    return "\n".join(lines)


def main():
    D = build("sel")
    D.to_csv(os.path.join(OUT, "diag_markouts_sel.csv"), index=False)
    txt = tables(D)
    open(os.path.join(OUT, "diag_markouts_sel.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
