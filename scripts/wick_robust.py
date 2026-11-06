#!/usr/bin/env python3
"""Robustness of the resting-bid dip buyer, with Coinbase US perp contract specs.

Selection (made on 2024 data only, from reports/wick_grid_base.csv):
  family   = the (L, reference, side) family with the best median design Sharpe -> 60-minute residual dips
  BEST     = that family's single best design-Sharpe configuration
  ENSEMBLE = every configuration in the family with design Sharpe >= 2.0, equal-weighted
Checks (design 2024 / test 2025-26 side by side):
  * fill strictness: trade-through by 1 tick (base), 3 ticks, 1 tick + 3 bp
  * costs: 2 bp per side maker and taker (Coinbase's advertised 0.02%); per-contract $0.20 per side
    (exchange $0.10 + clearing/NFA/FCM, guessed high); 0 bp maker / 2 bp taker
    taker legs also pay half the spread = 1 futures tick (conservative)
  * stop-loss, coin breakdown, calendar years, markouts (how long to hold), concurrency, worst days
Writes reports/wick_robust.csv, reports/wick_markouts.csv, reports/wick_best_trades.parquet
"""
import itertools
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wick_sim as ws  # noqa: E402

ROOT = ws.ROOT
FEE_CONTRACT_USD = 0.20


def fee_bp(model, coin, px, maker):
    if model == "pct2":
        return np.full_like(px, 2.0)
    if model == "maker0":
        return np.full_like(px, 0.0 if maker else 2.0)
    if model == "contract":
        size = ws.PERP[coin][1]
        return FEE_CONTRACT_USD / (size * px) * 1e4
    raise ValueError(model)


def run(D, P, idx, coin, L, k, theta, H, tt=1, extra_bp=0.0, stop=np.nan, side=1, ref="resid", fees="pct2"):
    lvl, sig = P.level(coin, L, k, side, ref)
    cf = D[coin]["cf"]
    tick_frac = ws.PERP[coin][2] / cf
    tickarr = np.nan_to_num(tt * tick_frac + extra_bp / 1e4, nan=1.0)
    tpd = theta * k * sig if np.isfinite(theta) else np.full_like(sig, np.nan)
    stpd = stop * k * sig if np.isfinite(stop) else np.full_like(sig, np.nan)
    ei, xi, ep, xp, ty = ws.run_book(D[coin]["open"], D[coin]["high"], D[coin]["low"], cf, lvl, tpd, stpd, side,
                                     tickarr, H, 0)
    gross = side * np.log(xp / ep) * 1e4
    hs = 1.0 * ws.PERP[coin][2] / ep * 1e4                       # half-spread = one futures tick
    f_in = fee_bp(fees, coin, ep, True)
    f_out = np.where(ty == 1, fee_bp(fees, coin, xp, True), fee_bp(fees, coin, xp, False) + hs)
    return pd.DataFrame({"ts": idx[ei], "exit_ts": idx[xi], "coin": coin, "type": ty, "hold_min": xi - ei,
                         "entry_px": ep, "exit_px": xp, "entry_i": ei,
                         "gross_bp": gross, "cost_bp": f_in + f_out, "net_bp": gross - f_in - f_out})


def daily(tr, notional=0.25):
    days = pd.date_range(ws.START, pd.Timestamp(ws.END) - pd.Timedelta(days=1), freq="D")
    if tr.empty:
        return pd.Series(0.0, index=days)
    return (tr.set_index("exit_ts").net_bp * notional / 1e4).resample("D").sum().reindex(days, fill_value=0.0)


def sstats(d, lab):
    d = d.loc[lab[0]:lab[1]]
    sd = d.std()
    eq = d.cumsum()
    return dict(sharpe=d.mean() / sd * np.sqrt(365) if sd > 0 else np.nan, ann_ret=d.mean() * 365,
                maxdd=(eq - eq.cummax()).min(), t=d.mean() / sd * np.sqrt(len(d)) if sd > 0 else np.nan)


DES = (ws.START, "2024-12-31")
TST = (ws.TEST_START, ws.END)


def main():
    t0 = time.time()
    coins = [c for c in ws.ALTS]
    idx, D = ws.load_ohlc(coins=["BTC"] + coins)
    P = ws.Prep(D, (60,))
    G = pd.read_csv(os.path.join(ROOT, "reports", "wick_grid_base.csv"))
    fam = G[(G.L == 60) & (G.side == 1) & (G.ref == "resid")]
    best = fam.sort_values("design_sharpe").iloc[-1]
    ens = fam[fam.design_sharpe >= 2.0]
    print(f"BEST (design-selected): k={best.k} theta={best.theta} H={best.H}; ENSEMBLE: {len(ens)} configs", flush=True)

    def book(cfgs, coins_, **kw):
        ds, trs = [], []
        for _, c in cfgs.iterrows():
            tr = pd.concat([run(D, P, idx, co, 60, c.k, c.theta, int(c.H), **kw) for co in coins_], ignore_index=True)
            trs.append(tr)
            ds.append(daily(tr))
        return sum(ds) / len(ds), trs

    rows = []
    variants = [("base: 1 tick, 2bp fees", dict()),
                ("fill needs 3 ticks", dict(tt=3)),
                ("fill needs 1 tick + 3 bp", dict(extra_bp=3.0)),
                ("fees $0.20/contract", dict(fees="contract")),
                ("fees 0 maker / 2 taker", dict(fees="maker0")),
                ("strict: 3 ticks + $0.20/contract", dict(tt=3, fees="contract")),
                ("stop at 1x dislocation", dict(stop=1.0)),
                ("stop at 2x dislocation", dict(stop=2.0))]
    coin_sets = {"7 alts": coins, "ex AVAX": [c for c in coins if c != "AVAX"]}
    keep = {}
    for (vname, kw), (cname, cs) in itertools.product(variants, coin_sets.items()):
        for sel_name, cfgs in [("BEST", best.to_frame().T), ("ENSEMBLE", ens)]:
            d, trs = book(cfgs, cs, **kw)
            tr = trs[0] if sel_name == "BEST" else pd.concat(trs)
            r = dict(variant=vname, coins=cname, selection=sel_name)
            for lab, per in [("design", DES), ("test", TST)]:
                x = tr[(tr.ts >= per[0]) & (tr.ts <= pd.Timestamp(per[1]) + pd.Timedelta(days=1))]
                r |= {f"{lab}_{k}": v for k, v in sstats(d, per).items()}
                r[f"{lab}_trades_per_day"] = len(x) / len(pd.date_range(*per)) / (1 if sel_name == "BEST" else len(cfgs))
                r[f"{lab}_net_bp"] = x.net_bp.mean()
                r[f"{lab}_cost_bp"] = x.cost_bp.mean()
            rows.append(r)
            if vname.startswith("base") and cname == "ex AVAX":
                keep[sel_name] = (d, tr)
        print(f"  {vname} / {cname} done ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(ROOT, "reports", "wick_robust.csv"), index=False)
    pd.set_option("display.width", 250)
    print(R[["variant", "coins", "selection", "design_sharpe", "test_sharpe", "test_t", "test_net_bp", "test_cost_bp",
             "test_trades_per_day", "test_ann_ret", "test_maxdd"]].round(2).to_string(index=False))

    # ---- base, ex-AVAX: coin and calendar-year breakdown for BEST and ENSEMBLE
    for sel_name in ("BEST", "ENSEMBLE"):
        d, tr = keep[sel_name]
        print(f"\n{sel_name} by coin (base costs, ex AVAX):")
        tr = tr.assign(period=np.where(tr.ts < ws.TEST_START, "design", "test"))
        print(tr.groupby(["coin", "period"]).agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"),
                                                  hit=("net_bp", lambda x: (x > 0).mean())).unstack("period").round(2).to_string())
        yrs = pd.DataFrame({y: dict(ret=d[d.index.year == y].sum(),
                                     sharpe=d[d.index.year == y].mean() / d[d.index.year == y].std() * np.sqrt(365))
                            for y in sorted(set(d.index.year))}).T
        print(f"{sel_name} by calendar year (return on capital at 0.25x notional per trade):")
        print(yrs.round(3).to_string())
        worst = d.sort_values().head(5)
        print(f"{sel_name} worst days:", {str(k.date()): round(v, 4) for k, v in worst.items()})
    best_tr = keep["BEST"][1]
    best_tr.to_parquet(os.path.join(ROOT, "reports", "wick_best_trades.parquet"), index=False)

    # ---- markouts: how long to hold after a fill (no take-profit, pure hold), k = 5, 6, 8
    hs_ = [1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240]
    mk = []
    for k in (5, 6, 8):
        for co in coin_sets["ex AVAX"]:
            lvl, _ = P.level(co, 60, k, 1, "resid")
            o, lo, cf = D[co]["open"], D[co]["low"], D[co]["cf"]
            tick = ws.PERP[co][2] / cf
            with np.errstate(invalid="ignore"):
                fill = (o > lvl) & (lo <= lvl * (1 - tick))
            fi = np.where(fill)[0]
            if len(fi) == 0:
                continue
            fi = fi[np.r_[True, np.diff(fi) > 60]]                  # first fill of each episode
            ep = lvl[fi]
            ts = idx[fi]
            for h in hs_:
                j = np.minimum(fi + h, len(cf) - 1)
                ret = np.log(cf[j] / ep) * 1e4
                for lab, m in [("design", ts < ws.TEST_START), ("test", ts >= ws.TEST_START)]:
                    mk.append(dict(k=k, coin=co, h=h, period=lab, n=int(m.sum()),
                                   mean_bp=np.nanmean(ret[m]) if m.any() else np.nan))
    MK = pd.DataFrame(mk)
    MK.to_csv(os.path.join(ROOT, "reports", "wick_markouts.csv"), index=False)
    pooled = MK.groupby(["k", "period", "h"]).apply(lambda g: np.average(g.mean_bp.fillna(0), weights=g.n), include_groups=False)
    print("\nMarkout after a resting-bid fill (bp, pooled over coins, before costs) by minutes held:")
    print(pooled.unstack("h").round(1).to_string())

    # ---- concurrency of the BEST book
    tr = keep["BEST"][1]
    ev = pd.concat([pd.Series(1, index=tr.ts), pd.Series(-1, index=tr.exit_ts)]).sort_index()
    conc = ev.cumsum()
    print(f"\nBEST concurrency: max {conc.max()} open trades; share of time with >=3 open: {(conc >= 3).mean():.3f}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
