#!/usr/bin/env python3
"""Event study + event-driven strategy search for the short-horizon reversal, on 1-minute Coinbase data.

Signal: residual move of a coin vs BTC over the last L minutes, e = r_i(L) - beta_i * r_BTC(L), scaled by
its own trailing 3-day volatility -> z. A "dislocation event" is |z| >= k. Trade: fade it (buy after a
relative drop, sell after a relative jump), optionally hedged with beta * BTC, entered d minutes after the
signal minute closes, held H minutes, one open trade per coin.

Costs per leg per side = fee + half-spread. Venue = what a New York resident can use: Coinbase Financial
Markets futures. BTC/ETH/SOL/XRP nano perps; LTC/DOGE/AVAX/LINK monthly futures (wider books); ADA not
listed (excluded). Half-spread = max(1 tick, Roll estimate / 2) x venue multiplier.

Design period: 2024 (choose parameters). Test: 2025-01-01 .. 2026-11-05 (never used for choices).
Writes reports/event_study.csv, reports/event_grid.csv
"""
import itertools
import os
import sys
import time

import numba
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALTS = ["ETH", "SOL", "XRP", "DOGE", "LTC", "AVAX", "LINK"]
ALL = ["BTC"] + ALTS
START, END = "2024-01-01", "2026-11-06"
DESIGN_END = "2024-12-31 23:59"
TEST_START = "2025-01-01"
FEE_BP = 2.0
# tick size as a share of price (approx, Nov 2026 levels) and venue multiplier on spread
TICK_BP = {"BTC": 0.66, "ETH": 0.45, "SOL": 0.6, "XRP": 0.5, "DOGE": 1.0, "LTC": 1.2, "AVAX": 1.0, "LINK": 0.8}
VENUE_MULT = {"BTC": 1.0, "ETH": 1.0, "SOL": 1.0, "XRP": 1.0, "DOGE": 2.0, "LTC": 2.0, "AVAX": 2.0, "LINK": 2.0}


def load():
    px = {}
    for c in ALL:
        df = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet")).drop_duplicates("ts").set_index("ts")
        px[c] = df["close"].astype(float)
        if c == "BTC":
            vol = {}
        vol[c] = df["volume"].astype(float)
    idx = pd.date_range(START, END, freq="min", inclusive="left")
    P = pd.DataFrame({c: px[c].reindex(idx) for c in ALL}).ffill(limit=10)
    V = pd.DataFrame({c: vol[c].reindex(idx) for c in ALL}).fillna(0.0)
    return P, V


def half_spread_bp(P):
    out = {}
    for c in ALL:
        dp = np.log(P[c]).diff().dropna()
        cov = dp.autocorr(1) * dp.var()
        roll = 2 * np.sqrt(-cov) * 1e4 if cov < 0 else 0.0
        out[c] = max(TICK_BP[c], roll / 2) * VENUE_MULT[c]
    return out


def prepare(P, V, L):
    lp = np.log(P)
    r1 = lp.diff()
    w = 4320
    mb = r1["BTC"].rolling(w, min_periods=1440).mean()
    vb = r1["BTC"].rolling(w, min_periods=1440).var()
    beta = {}
    for c in ALTS:
        cov = (r1[c] * r1["BTC"]).rolling(w, min_periods=1440).mean() - r1[c].rolling(w, min_periods=1440).mean() * mb
        beta[c] = (cov / vb).clip(0.0, 3.0)
    beta = pd.DataFrame(beta)
    rL = lp - lp.shift(L)
    e = rL[ALTS].sub(beta.mul(rL["BTC"], axis=0), fill_value=np.nan)
    sd = e.rolling(w, min_periods=1440).std()
    z = e / sd
    traded = V > 0
    z = z.where(traded[ALTS])
    return lp, beta, z


def forward(lp, beta, d, H):
    """Hedged (residual) and unhedged forward log returns from t+d to t+d+H, aligned at t."""
    a = lp.shift(-(d + H)) - lp.shift(-d)
    res = a[ALTS].sub(beta.mul(a["BTC"], axis=0))
    return res, a[ALTS]


def event_table(z, res, raw, label):
    rows = []
    for c in ALTS:
        zc, rc, uc = z[c], res[c], raw[c]
        for lo, hi in [(-99, -4), (-4, -3), (-3, -2), (-2, -1), (-1, 1), (1, 2), (2, 3), (3, 4), (4, 99)]:
            m = (zc > lo) & (zc <= hi) & rc.notna()
            rows.append(dict(coin=c, bucket=f"({lo},{hi}]", n=int(m.sum()), resid_bp=rc[m].mean() * 1e4,
                             raw_bp=uc[m].mean() * 1e4, period=label))
    return pd.DataFrame(rows)


@numba.njit(cache=True)
def greedy(cand, window):
    out = np.empty(len(cand), dtype=np.int64)
    n, nxt = 0, -1
    for j in range(len(cand)):
        i = cand[j]
        if i >= nxt:
            out[n] = i
            n += 1
            nxt = i + window
    return out[:n]


def triggers(zc, k, sides):
    """Indices where |z| first crosses k (or z first crosses -k for dips-only)."""
    zp = np.r_[np.nan, zc[:-1]]
    if sides == "both":
        hit = ((zc <= -k) & ~(zp <= -k)) | ((zc >= k) & ~(zp >= k))
    else:
        hit = (zc <= -k) & ~(zp <= -k)
    return np.where(hit)[0]


def simulate_fast(Z, R_res, R_raw, B, times, hs, k, d, H, sides):
    """Returns {hedge: DataFrame of trades} using one greedy selection shared by hedged/unhedged."""
    out = {True: [], False: []}
    for j, c in enumerate(ALTS):
        zc = Z[:, j]
        cand = triggers(zc, k, sides)
        ok = ~np.isnan(R_res[cand, j]) & ~np.isnan(R_raw[cand, j])
        sel = greedy(cand[ok], d + H)
        if len(sel) == 0:
            continue
        sgn = -np.sign(zc[sel])
        cost_coin = 2 * (FEE_BP + hs[c])
        for hedge in (True, False):
            r = (R_res if hedge else R_raw)[sel, j]
            gross = sgn * r * 1e4
            cost = cost_coin + (2 * (FEE_BP + hs["BTC"]) * B[sel, j] if hedge else 0.0)
            out[hedge].append(pd.DataFrame({"ts": times[sel], "coin": c, "gross_bp": gross, "net_bp": gross - cost}))
    return {h: (pd.concat(v) if v else pd.DataFrame(columns=["ts", "coin", "gross_bp", "net_bp"])) for h, v in out.items()}


def simulate(z, res, raw, beta, hs, k, d, H, hedge, sides, period):
    """Event-driven: one open trade per coin; returns per-trade net P&L (bp of notional) with timestamps."""
    trades = []
    Zall = z.loc[period[0]:period[1]]
    for c in ALTS:
        zc = Zall[c].to_numpy()
        times = Zall.index
        r = (res if hedge else raw)[c].reindex(times).to_numpy()
        b = beta[c].reindex(times).to_numpy()
        if sides == "both":
            cand = np.where(np.abs(zc) >= k)[0]
        else:
            cand = np.where(zc <= -k)[0]
        nxt = -1
        cost_coin = 2 * (FEE_BP + hs[c])
        for i in cand:
            if i < nxt or np.isnan(r[i]):
                continue
            sgn = -np.sign(zc[i])                       # fade the move
            gross = sgn * r[i] * 1e4
            cost = cost_coin + (2 * (FEE_BP + hs["BTC"]) * b[i] if hedge else 0.0)
            trades.append((times[i], c, gross, gross - cost))
            nxt = i + d + H                              # flat before the next trade in this coin
    return pd.DataFrame(trades, columns=["ts", "coin", "gross_bp", "net_bp"])


def stats(tr, notional_frac=0.5):
    """Daily P&L on $10k capital with each trade sized at notional_frac x capital per leg."""
    if tr.empty:
        return dict(trades=0, per_day=0, gross_bp=np.nan, net_bp=np.nan, sharpe=np.nan, ann_ret=np.nan)
    daily = tr.set_index("ts").net_bp.resample("D").sum() * notional_frac / 1e4
    days = pd.date_range(tr.ts.min().floor("D"), tr.ts.max().floor("D"), freq="D")
    daily = daily.reindex(days, fill_value=0.0)
    sh = daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else np.nan
    return dict(trades=len(tr), per_day=len(tr) / len(days), gross_bp=tr.gross_bp.mean(), net_bp=tr.net_bp.mean(),
                sharpe=sh, ann_ret=daily.mean() * 365, hit=(tr.net_bp > 0).mean())


def main():
    t0 = time.time()
    P, V = load()
    hs = half_spread_bp(P)
    print("half-spread per side used (bp):", {c: round(v, 2) for c, v in hs.items()}, f"+ fee {FEE_BP} bp", flush=True)
    tabs, grid = [], []
    prepared = {}
    for L in (5, 15, 30, 60):
        lp, beta, z = prepare(P, V, L)
        prepared[L] = z
        print(f"prepared L={L} ({time.time() - t0:.0f}s)", flush=True)
    B = beta.to_numpy()
    times = P.index
    split = times.get_indexer([pd.Timestamp(TEST_START)])[0]
    design_end = times.get_indexer([pd.Timestamp("2025-01-01")])[0]
    for d, H in itertools.product((1, 2), (5, 15, 30, 60, 120)):
        res, raw = forward(lp, beta, d, H)
        Rr, Ru = res.to_numpy(), raw.to_numpy()
        for L, z in prepared.items():
            if d == 1:
                for lab, (s_, e_) in [("design 2024", (START, DESIGN_END)), ("test 2025-26", (TEST_START, END))]:
                    t = event_table(z.loc[s_:e_], res.loc[s_:e_], raw.loc[s_:e_], lab)
                    t["L"], t["H"], t["d"] = L, H, d
                    tabs.append(t)
            Z = z.to_numpy()
            for k, sides in itertools.product((2, 3, 4, 5), ("both", "dips")):
                rows = {h: dict(L=L, d=d, H=H, k=k, hedge=h, sides=sides) for h in (True, False)}
                for lab, (a, b_) in [("design", (0, design_end)), ("test", (split, len(times)))]:
                    tr = simulate_fast(Z[a:b_], Rr[a:b_], Ru[a:b_], B[a:b_], times[a:b_], hs, k, d, H, sides)
                    for h in (True, False):
                        rows[h] |= {f"{lab}_{kk}": vv for kk, vv in stats(tr[h]).items()}
                grid += list(rows.values())
        print(f"d={d} H={H} done ({time.time() - t0:.0f}s)", flush=True)
    T = pd.concat(tabs)
    T.to_csv(os.path.join(ROOT, "reports", "event_study.csv"), index=False)
    G = pd.DataFrame(grid)
    G.to_csv(os.path.join(ROOT, "reports", "event_grid.csv"), index=False)

    # ---- reversion profile for big dislocations, pooled over coins (design vs test)
    print("\nAverage reversion after |z| >= 3 dislocations (bp, hedged residual, d=1, fade direction):")
    T["fade_bp"] = np.where(T.bucket.str.startswith("(-"), T.resid_bp, -T.resid_bp)
    big = T[T.bucket.isin(["(-99,-4]", "(-4,-3]", "(3,4]", "(4,99]"])]
    piv = big.groupby(["period", "L", "H"]).apply(lambda g: np.average(g.fade_bp, weights=g.n), include_groups=False).unstack("H")
    print(piv.round(1).to_string())
    print("\nTop 15 configurations by DESIGN-period Sharpe (after costs), with their TEST results:")
    cols = ["L", "d", "H", "k", "hedge", "sides", "design_trades", "design_net_bp", "design_sharpe",
            "test_trades", "test_per_day", "test_gross_bp", "test_net_bp", "test_sharpe", "test_ann_ret"]
    top = G.sort_values("design_sharpe", ascending=False).head(15)
    print(top[cols].round(2).to_string(index=False))
    n_pos = (G.design_sharpe > 0).sum()
    print(f"\n{len(G)} configurations; positive after costs in design: {n_pos}; in test: {(G.test_sharpe > 0).sum()}; "
          f"both: {((G.design_sharpe > 0) & (G.test_sharpe > 0)).sum()}")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
