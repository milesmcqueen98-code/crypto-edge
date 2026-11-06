#!/usr/bin/env python3
"""Build the dashboard's CSVs for the wick catcher from the research outputs (reports/dash/wick_*.csv)."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
OUT = os.path.join(ROOT, "reports", "dash")
os.makedirs(OUT, exist_ok=True)
DAYS = pd.date_range("2025-01-01", "2026-11-05", freq="D")


def capped(tr, cap):
    tr = tr.sort_values("ts").reset_index(drop=True)
    keep, open_ = [], []
    for r in tr.itertuples():
        open_ = [e for e in open_ if e > r.ts]
        if len(open_) < cap:
            keep.append(r.Index)
            open_.append(r.exit_ts)
    return tr.loc[keep]


def daily(tr, notional=0.25):
    return (tr.set_index("exit_ts").net_bp * notional / 1e4).resample("D").sum().reindex(DAYS, fill_value=0.0)


def row(name, role, tr, notional=0.25):
    d = daily(tr, notional)
    eq = d.cumsum()
    sh = lambda x: x.mean() / x.std() * np.sqrt(365)  # noqa: E731
    return dict(config=name, role=role, sharpe=sh(d), t=d.mean() / d.std() * np.sqrt(len(d)), ann_ret=d.mean() * 365,
                maxdd=(eq - eq.cummax()).min(), worst_day=d.min(), trades_per_day=len(tr) / len(DAYS),
                net_bp=tr.net_bp.mean(), hit=(tr.net_bp > 0).mean(), sharpe_2025=sh(d[d.index.year == 2025]),
                sharpe_2026=sh(d[d.index.year == 2026])), d


def main():
    B = pd.read_parquet(os.path.join(ROOT, "reports", "wick_breadth_trades.parquet"))
    Fz = pd.read_parquet(os.path.join(ROOT, "reports", "wick_final_trades.parquet"))   # 17 coins, 5-seed average
    Fz = Fz.assign(universe="wide 17", strategy=Fz.strategy.replace({"rule + AI, 5-seed average": "rule + AI"}))
    B = pd.concat([B[B.universe == "core 6"], Fz], ignore_index=True)
    uni = "wide 17"
    rows, curves = [], {}
    E = pd.read_csv(os.path.join(ROOT, "reports", "event_grid.csv"))
    best_taker = E.sort_values("design_sharpe", ascending=False).iloc[0]
    rows.append(dict(config="Market orders after the move (best 2024 setting)", role="Rejected: costs eat the edge",
                     sharpe=best_taker.test_sharpe, t=np.nan, ann_ret=best_taker.test_ann_ret, maxdd=np.nan,
                     worst_day=np.nan, trades_per_day=best_taker.test_per_day, net_bp=best_taker.test_net_bp,
                     hit=best_taker.get("test_hit", np.nan), sharpe_2025=np.nan, sharpe_2026=np.nan))
    for name, role, u, strat, cap in [
            ("Resting bids, no AI, 6 coins", "Rule alone", "core 6", "rule only", None),
            ("Resting bids + AI, 6 coins", "AI adds", "core 6", "rule + AI", None),
            ("Resting bids, no AI, all coins", "Rule alone", uni, "rule only", None),
            ("Resting bids + AI, all coins", "No position limit", uni, "rule + AI", None),
            ("Resting bids + AI, all coins, max 6 open", "Paper trading now", uni, "rule + AI", 6)]:
        tr = B[(B.universe == u) & (B.strategy == strat)]
        tr = capped(tr, cap) if cap else tr
        r, d = row(name, role, tr)
        rows.append(r)
        curves[name] = d
    H = pd.DataFrame(rows)
    H.to_csv(os.path.join(OUT, "wick_headline.csv"), index=False)
    # value of $10,000, test period, three series + BTC
    btc = pd.read_parquet(os.path.join(ROOT, "data", "minute", "BTC.parquet")).set_index("ts").close
    btc = btc.resample("D").last().reindex(DAYS).ffill()
    eq = []
    for name, label in [("Resting bids + AI, all coins, max 6 open", "AI-filtered bids (max 6 open)"),
                        ("Resting bids, no AI, all coins", "Same bids, no AI"), (None, "BTC buy & hold")]:
        v = (1 + btc.pct_change().fillna(0)).cumprod() * 10000 if name is None else 10000 * (1 + curves[name].cumsum())
        eq += [dict(day=str(k.date()), series=label, value=round(float(x), 2)) for k, x in v.items()]
    pd.DataFrame(eq).to_csv(os.path.join(OUT, "wick_equity.csv"), index=False)
    # stress tests
    S = pd.read_csv(os.path.join(ROOT, "reports", "wick_ai_robust.csv"))
    piv = S.pivot_table(index="variant", columns="strategy", values=["test_sharpe", "test_t", "test_net_bp"], aggfunc="first")
    st = pd.DataFrame({"variant": piv.index, "rule_sharpe": piv[("test_sharpe", "rule only")].values,
                       "ai_sharpe": piv[("test_sharpe", "rule + AI")].values, "ai_t": piv[("test_t", "rule + AI")].values,
                       "ai_net_bp": piv[("test_net_bp", "rule + AI")].values})
    order = [v for v in S.variant.unique()]
    st["o"] = st.variant.map({v: i for i, v in enumerate(order)})
    st.sort_values("o").drop(columns="o").to_csv(os.path.join(OUT, "wick_stress.csv"), index=False)
    # signals
    I = pd.read_csv(os.path.join(ROOT, "reports", "wick_ai_importance.csv"), index_col=0)
    Q = pd.read_csv(os.path.join(ROOT, "reports", "wick_ai_quintiles.csv"))
    plain = {"dist_1d_high_bp": "Coin's move from its 24-hour high", "bid_depth_bp": "How deep the bid is (volatility)",
             "z_res60": "Size of the 60-minute drop vs BTC", "btc_z60": "BTC's own 60-minute move",
             "beta": "How strongly the coin follows BTC", "btc_ret240_bp": "BTC's 4-hour move",
             "coin_id": "Which coin", "btc_ret1d_bp": "BTC's 24-hour move", "coin_ret7d_bp": "Coin's 7-day move",
             "coin_ret1d_bp": "Coin's 24-hour move", "btc_z15": "BTC's 15-minute move", "alts_mean_z60": "Are other coins dropping too",
             "btc_z5": "BTC's 5-minute move", "range_pos240": "Where the coin sits in its 4-hour range",
             "vol_ratio_60m_3d": "Last hour's volatility vs 3 days", "btc_vol_ratio": "BTC's last-hour volatility vs 3 days",
             "hour_utc": "Hour of day", "alts_below_2sd": "How many coins are down sharply",
             "btc_volume_ratio_15m": "BTC volume spike", "z_res15": "Size of the 15-minute drop vs BTC",
             "weekend": "Weekend", "volume_ratio_15m": "Coin volume spike", "z_1min": "Last minute's move"}
    sig = []
    for f, r in I.iterrows():
        if f == "coin_id":
            continue
        q = Q[Q.feature == f]
        g = lambda p, k: q[(q.period == p) & (q.quintile == k)].net_bp  # noqa: E731
        sig.append(dict(signal=plain.get(f, f), importance_bp=r.mean_abs_shap_bp,
                        test_low=float(g("test", 1).iloc[0]) if len(g("test", 1)) else np.nan,
                        test_high=float(g("test", 5).iloc[0]) if len(g("test", 5)) else np.nan))
    pd.DataFrame(sig).head(10).to_csv(os.path.join(OUT, "wick_signals.csv"), index=False)
    # hold time (markouts after a fill, k=5, pooled over coins), design vs test
    M = pd.read_csv(os.path.join(ROOT, "reports", "wick_markouts.csv"))
    M = M[M.k == 5]
    pooled = M.groupby(["period", "h"]).apply(lambda g: np.average(g.mean_bp.fillna(0), weights=g.n), include_groups=False)
    hold = pd.DataFrame({"minutes": pooled.loc["design"].index, "design_bp": pooled.loc["design"].values,
                         "test_bp": pooled.loc["test"].values})
    hold.to_csv(os.path.join(OUT, "wick_hold.csv"), index=False)
    # futures validation, if present
    p = os.path.join(ROOT, "reports", "wick_futures.csv")
    ps = os.path.join(ROOT, "reports", "wick_futures_strict.csv")
    if os.path.exists(p):
        F = pd.read_csv(p)
        F = F[(F.strategy == "rule + AI") & (F.coin != "PORTFOLIO")][["coin", "start", "fut_trades", "fut_net_bp", "spot_trades", "spot_net_bp"]]
        if os.path.exists(ps):
            S2 = pd.read_csv(ps)
            S2 = S2[(S2.strategy == "rule + AI") & (S2.coin != "PORTFOLIO")][["coin", "fut_trades", "fut_net_bp"]]
            F = F.merge(S2.rename(columns={"fut_trades": "strict_trades", "fut_net_bp": "strict_net_bp"}), on="coin", how="left")
        F.to_csv(os.path.join(OUT, "wick_futures.csv"), index=False)
        P = pd.read_csv(os.path.join(ROOT, "reports", "wick_futures_portfolio.csv"))
        P["fills"] = "base"
        if os.path.exists(ps.replace("wick_futures_strict", "wick_futures_portfolio_strict")):
            P2 = pd.read_csv(ps.replace("wick_futures_strict", "wick_futures_portfolio_strict"))
            P2["fills"] = "strict"
            P = pd.concat([P, P2])
        P = P[P.cap.astype(str) == "6"]
        P["version"] = P.strategy.map({"rule only": "No AI", "rule + AI": "With AI"}) + ", " + P.venue + " prices, " + \
            P.fills.map({"base": "fill needs 1 tick", "strict": "fill needs 3 ticks + volume"})
        P[["version", "window", "trades", "per_day", "net_bp", "sharpe", "t", "ann_ret", "maxdd", "worst_day"]].to_csv(
            os.path.join(OUT, "wick_futures_portfolio.csv"), index=False)
    print(H.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
