#!/usr/bin/env python3
"""How far the wick catcher (strategy of record R2-08) scales: $10K to $5M.

For each R2-08 trade (spot-priced simulation, Jan 2025 - Nov 2026) we estimate how much a resting bid at the trade's
level could have bought: the volume that traded BELOW our level in the fill minute and the following minutes while the
price stayed below it (each 1-minute candle's volume split evenly across its high-low range). Those sellers had already
cleared every bid at our price, so with our order resting there they would have hit us first; that volume is the most
we could have bought. Bids rest on both Coinbase books where the coin has a US perp: spot and perp volume both count
(perp levels scaled by the perp/spot price ratio of the minute before).

Exits: a take-profit fills only up to the volume traded above the exit price before the exit (same split); anything
left is sold at market at the 60-minute mark, like a time exit. Market exits pay square-root impact,
0.7 x daily vol x sqrt(size / daily volume) - optimistic for a sale squeezed into a few minutes.
Scenarios: we capture theta = 25%, 50% or 100% of that volume; per-trade size 25% of capital (as paper-traded) or 50%.
Fees: realistic perp costs from the lab (net_real), and Coinbase spot fees at the volume tier the book itself reaches.
Writes reports/wick_capacity.csv and reports/wick_capacity_trades.parquet.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from edge import book  # noqa: E402

SPOT_TIERS = [(0, .0050, .0090), (10e3, .0035, .0075), (50e3, .0015, .0030), (250e3, .0010, .0015),
              (500e3, .0006, .00125), (20e6, .0001, .0005), (50e6, 0.0, .00035), (250e6, 0.0, .0002)]
SPOT_HALF_SPREAD_BP = 2.0
CAPITALS = [10e3, 50e3, 100e3, 250e3, 500e3, 1e6, 2.5e6, 5e6]
THETAS = [0.25, 0.5, 1.0]
WEIGHTS = [0.25, 0.5]
SCAN_MIN = 15


def tier(v30):
    out = SPOT_TIERS[0]
    for t in SPOT_TIERS:
        if v30 >= t[0]:
            out = t
    return out


def load_minutes(path, mult=1.0):
    m = pd.read_parquet(path).drop_duplicates("ts").set_index("ts").sort_index()
    m["volume"] = m["volume"].astype(float) * mult
    return m


def below_volume_usd(m, t0, t_end, level):
    """USD volume traded below `level` from t0 while the price stays below it (max SCAN_MIN minutes)."""
    w = m.loc[t0:min(t_end, t0 + pd.Timedelta(minutes=SCAN_MIN))]
    tot = 0.0
    for i, (ts, r) in enumerate(w.iterrows()):
        if r.low >= level:
            if i == 0:
                continue          # level not reached this minute on this venue
            break
        rng = r.high - r.low
        frac = 1.0 if rng <= 0 else min(1.0, (level - r.low) / rng)
        tot += r.volume * frac * 0.5 * (level + r.low)
    return tot


def above_volume_usd(m, t0, t_end, level):
    w = m.loc[t0:t_end]
    tot = 0.0
    for _, r in w.iterrows():
        if r.high <= level:
            continue
        rng = r.high - r.low
        frac = 1.0 if rng <= 0 else min(1.0, (r.high - level) / rng)
        tot += r.volume * frac * 0.5 * (level + r.high)
    return tot


def main():
    lab = pd.read_parquet(os.path.join(ROOT, "reports", "lab", "futures_trades.parquet"))
    x = lab[lab.variant.str.startswith("R2-08") & (lab.venue == "spot_full")].copy().sort_values("ts")
    prods = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
    perp_cs = prods[prods.expiry_type == "PERPETUAL"].set_index("contract_root_unit")["contract_size"].to_dict()
    spot, perp, adv, vol_d = {}, {}, {}, {}
    for c in x.coin.unique():
        spot[c] = load_minutes(os.path.join(ROOT, "data", "minute", f"{c}.parquet"))
        p = os.path.join(ROOT, "data", "cfm", f"{c}.parquet")
        if os.path.exists(p) and c in perp_cs:
            perp[c] = load_minutes(p, perp_cs[c])
        s = spot[c].loc["2025-01-01":]
        daily_usd = (s.close * s.volume).resample("D").sum()
        adv[c] = float(daily_usd[daily_usd > 0].median())
        if c in perp:
            pp = perp[c].loc["2025-01-01":]
            pd_usd = (pp.close * pp.volume).resample("D").sum()
            adv[c] += float(pd_usd[pd_usd > 0].median()) if (pd_usd > 0).any() else 0.0
        vol_d[c] = float(np.log(s.close.resample("D").last()).diff().std())

    rows = []
    for _, t in x.iterrows():
        c, t0, t1, lvl = t.coin, t.ts, t.exit_ts, t.px
        cap_in_spot = below_volume_usd(spot[c], t0, t1, lvl)
        cap_in_perp, cap_out_perp = 0.0, 0.0
        exit_px = lvl * (1 + t.gross / 1e4)
        if c in perp:
            pm = perp[c]
            prev = t0 - pd.Timedelta(minutes=1)
            if prev in pm.index and prev in spot[c].index:
                ratio = pm.at[prev, "close"] / spot[c].at[prev, "close"]
                cap_in_perp = below_volume_usd(pm, t0, t1, lvl * ratio)
                cap_out_perp = above_volume_usd(pm, t0, t1, exit_px * ratio) if t.tp else 0.0
        cap_out_spot = above_volume_usd(spot[c], t0, t1, exit_px) if t.tp else 0.0
        s60 = spot[c].loc[:t0 + pd.Timedelta(minutes=60), "close"]
        gross60 = (s60.iloc[-1] / lvl - 1) * 1e4 if len(s60) else t.gross
        rows.append(dict(ts=t0, coin=c, tp=bool(t.tp), gross=t.gross, gross60=gross60, net_real=t.net_real, net_adv=t.net_adv,
                         cap_in_spot=cap_in_spot, cap_in_perp=cap_in_perp, cap_out=cap_out_spot + cap_out_perp,
                         adv=adv[c], vol_d=vol_d[c]))
    tr = pd.DataFrame(rows)
    tr["cap_in"] = tr.cap_in_spot + tr.cap_in_perp
    tr.to_parquet(os.path.join(ROOT, "reports", "wick_capacity_trades.parquet"))
    years = (x.exit_ts.max() - x.ts.min()).days / 365.25
    q = tr.cap_in.quantile([.1, .25, .5, .75, .9])
    print(f"{len(tr)} trades over {years:.2f} years; entry capacity per trade (USD, both books): "
          + ", ".join(f"p{int(k*100)} {v:,.0f}" for k, v in q.items()))
    print("median entry capacity by coin:", tr.groupby("coin").cap_in.median().round(-2).sort_values().to_dict())

    out = []
    cost_real = tr.gross - tr.net_real                                   # lab's realistic perp cost per trade, bp
    for w in WEIGHTS:
        for th in THETAS:
            for C in CAPITALS:
                want = w * C
                fill = np.minimum(want, th * tr.cap_in.to_numpy())
                tp_part = np.where(tr.tp, np.minimum(fill, th * tr.cap_out.to_numpy()), 0.0)
                mkt = fill - tp_part                                     # sold at market at the 60-minute mark
                gross_mkt = np.where(tr.tp, tr.gross60, tr.gross)
                impact_bp = 1e4 * 0.7 * tr.vol_d.to_numpy() * np.sqrt(mkt / tr.adv.to_numpy())
                pnl_real = (tp_part * tr.net_real.to_numpy()
                            + mkt * (gross_mkt - cost_real.to_numpy() - SPOT_HALF_SPREAD_BP - impact_bp)) / 1e4
                v30 = 2 * fill.sum() / (years * 365.25) * 30
                _, mk, tk = tier(v30)
                pnl_spot = (tp_part * (tr.gross.to_numpy() - 2e4 * mk)
                            + mkt * (gross_mkt - 1e4 * (mk + tk) - SPOT_HALF_SPREAD_BP - impact_bp)) / 1e4
                pnl_best = np.maximum(pnl_real, pnl_spot)
                for name, pnl in (("perp costs", pnl_real), ("spot at its tier", pnl_spot), ("cheaper venue", pnl_best)):
                    pnl = np.asarray(pnl, dtype=float)
                    daily = pd.Series(pnl, index=tr.ts.dt.floor("D").to_numpy()).groupby(level=0).sum()
                    idx = pd.date_range(tr.ts.min().floor("D"), tr.ts.max().floor("D"), freq="D")
                    r = daily.reindex(idx, fill_value=0.0) / C
                    ex = r - book.rf_daily(idx).to_numpy()
                    eq = (1 + r).cumprod()
                    out.append(dict(size_pct=w, theta=th, capital=C, fees=name, fill_rate=float(fill.sum() / (want * len(tr))),
                                    avg_fill_usd=float(fill.mean()), ret_yr=float(pnl.sum() / C / years),
                                    sharpe=float(ex.mean() / ex.std() * np.sqrt(365)),
                                    maxdd=float((eq / eq.cummax() - 1).min()), spot_tier_maker_bp=mk * 1e4,
                                    v30_musd=v30 / 1e6, dollars_yr=float(pnl.sum() / years)))
    res = pd.DataFrame(out)
    res.to_csv(os.path.join(ROOT, "reports", "wick_capacity.csv"), index=False)
    pd.set_option("display.width", 220)
    show = res[res.fees == "cheaper venue"].pivot_table(index=["size_pct", "theta"], columns="capital", values="ret_yr")
    print("\nReturn per year, cheaper venue per trade (rows: size per trade, share of through-volume we capture):")
    print((show * 100).round(0).to_string())
    print("\nSharpe:")
    print(res[res.fees == "cheaper venue"].pivot_table(index=["size_pct", "theta"], columns="capital", values="sharpe").round(2).to_string())
    print("\nMax drawdown:")
    print(res[res.fees == "cheaper venue"].pivot_table(index=["size_pct", "theta"], columns="capital", values="maxdd").round(2).to_string())
    print("\nDollars per year ($K):")
    print((res[res.fees == "cheaper venue"].pivot_table(index=["size_pct", "theta"], columns="capital", values="dollars_yr") / 1e3).round(0).to_string())
    print("\nFill rate (share of wanted size filled):")
    print(res[(res.fees == "cheaper venue")].pivot_table(index=["size_pct", "theta"], columns="capital", values="fill_rate").round(2).to_string())


if __name__ == "__main__":
    main()
