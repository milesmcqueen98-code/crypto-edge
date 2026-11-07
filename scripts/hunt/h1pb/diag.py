#!/usr/bin/env python3
"""H1 diagnostics (SPEC "Checks to report") from confirm_*.parquet and a variant's trade list."""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import book as B  # noqa: E402
import levels as LV  # noqa: E402

MAJORS = ("BTC", "ETH", "SOL", "XRP")


def confirmation(stage, cutoff=None):
    """Candle-implied minute-mode fills (perp minute opened beyond the level and traded >= 1 tick through it) vs prints.
    price_conf: a print in the order's live window [u + 1 s, u + 61 s) crossed the level from the resting side;
    size_conf: theta = 0.5 x through-volume of that first crossing gives >= 1 contract; full: >= the $10K target."""
    if stage == "devc":                     # corrected statistics: alts from dev2; majors from dev minus delta rows + dev2
        C1 = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(B.REP, "dev", "confirm_*.parquet")))])
        C2 = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(B.REP, "dev2", "confirm_*.parquet")))])
        dr = pd.read_parquet(os.path.join(B.REP, "delta_rows.parquet"))
        key = set(zip(dr.coin, dr.row.astype(np.int64)))
        keep = C1.coin.isin(B.MAJORS).to_numpy() & ~np.array([(c, int(r)) in key for c, r in zip(C1.coin, C1.row)])
        C = pd.concat([C1[keep], C2], ignore_index=True)
    else:
        C = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(B.REP, stage, "confirm_*.parquet")))],
                      ignore_index=True)
    C = C.drop_duplicates(["coin", "k", "side", "row"])
    C["grp"] = np.where(C.coin.isin(MAJORS), "majors", "alts")
    C["size_conf"] = C.n50_first >= 1
    C["full"] = C.n50_first >= C.ntg
    C["frac"] = np.minimum(1.0, C.n50_first / C.ntg.clip(lower=1))
    C["cand_cap"] = np.minimum(C.ntg, np.floor(C.cap_candle50))
    C["ratio"] = np.where(C.cap_candle50 > 0, 0.5 * C.run_first / C.cap_candle50, np.nan)
    out = []
    for keys, g in [(("all", "all", "all"), C)] + [((k, s, gr), g) for (k, s, gr), g in C.groupby(["k", "side", "grp"])]:
        out.append(dict(k=keys[0], side=keys[1], group=keys[2], candle_fills=len(g), price_conf=g.price_conf.mean(),
                        size_conf=g.size_conf.mean(), full_size=g.full.mean(), mean_fill_frac=g.frac.mean(),
                        candle_mean_fill_frac=np.minimum(1.0, g.cand_cap / g.ntg.clip(lower=1)).mean(),
                        median_print_vs_candle_capacity=float(np.nanmedian(g.ratio[g.price_conf]))))
    return pd.DataFrame(out)


def spot_confirm(T):
    """Per trade: did Coinbase spot also trade through the spot-equivalent of our level (L / exp(bbar)) in the fill's
    candle minute?"""
    flag = np.zeros(len(T), bool)
    for coin, g in T.groupby("coin"):
        st = LV.stats(coin)
        cm = ((g.t_fill.to_numpy() - st["idx"][0].value) // (60 * 10**9)).astype(np.int64)
        r = g.row.to_numpy().astype(np.int64)
        lvl_s = g.L.to_numpy() / np.exp(st["bbar"][r])
        lo, hi = st["s_low"][cm], st["s_high"][cm]
        f = np.where(g.side.to_numpy() > 0, lo <= lvl_s, hi >= lvl_s)
        flag[g.index.to_numpy()] = np.nan_to_num(f, nan=False).astype(bool)
        del st
    return flag


def tables(T, r, capital, inc=None):
    """Descriptive tables for one variant's trades T (with net, cost, notional) and daily returns r."""
    out = {}
    if not len(T):
        return out
    T = T.copy()
    T["net_bp"] = T.net / T.notional * 1e4
    T["grp"] = np.where(T.coin.isin(MAJORS), "majors", "alts")
    T["fill_frac"] = np.minimum(1.0, T.n / T.ntg.clip(lower=1))
    T["month"] = pd.to_datetime(T.t_close.to_numpy()).to_period("M").astype(str)
    et = pd.to_datetime(T.t_fill.to_numpy()).tz_localize("UTC").tz_convert("America/New_York")
    T["et_hour"] = et.hour
    m = et.hour * 60 + et.minute
    T["et_1545_1615"] = (m >= 15 * 60 + 45) & (m < 16 * 60 + 15)
    T["tp_full"] = T.tpn >= T.n
    out["by_coin"] = T.groupby("coin").agg(trades=("net", "size"), pnl=("net", "sum"), net_bp=("net_bp", "mean"),
                                           fill_frac=("fill_frac", "mean"), tp_full=("tp_full", "mean")).round(3)
    out["by_month"] = T.groupby(["month", "grp"]).agg(trades=("net", "size"), pnl=("net", "sum")).unstack("grp").round(1)
    out["by_et_hour"] = T.groupby("et_hour").agg(fills=("net", "size"), pnl=("net", "sum"), net_bp=("net_bp", "mean")).round(2)
    b = T[T.et_1545_1615]
    out["et_1545_1615"] = dict(fills=int(len(b)), pnl=float(b.net.sum()), net_bp=float(b.net_bp.mean()) if len(b) else np.nan)
    q = T.fill_frac.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict()
    out["capacity"] = dict(mean_fill_frac=float(T.fill_frac.mean()), quantiles=q,
                           share_of_target_usd=float(T.notional.sum() / (len(T) * 10_000.0)),
                           median_notional=float(T.notional.median()), full_target_share=float((T.n >= T.ntg).mean()))
    if "spot_conf" in T:
        out["spot_vs_perp_only"] = T.groupby("spot_conf").agg(trades=("net", "size"), pnl=("net", "sum"),
                                                              net_bp=("net_bp", "mean"),
                                                              gross_bp=("gross", lambda x: (x / T.loc[x.index, "notional"]).mean() * 1e4)).round(2)
    d = r * capital
    top = d.sort_values(ascending=False)
    tot = d.sum()
    out["top3_share"] = float(top.head(3).sum() / tot) if tot > 0 else np.nan
    out["top3_days"] = {str(k.date()): round(float(v), 1) for k, v in top.head(3).items()}
    if inc is not None:
        out["corr_incumbent"] = float(np.corrcoef(r, inc)[0, 1]) if r.std() > 0 else np.nan
        w = inc.sort_values().head(int(max(1, 0.05 * len(inc)))).index
        out["sleeve_on_inc_worst5pct_days"] = float(r.reindex(w).mean() * capital)
    return out
