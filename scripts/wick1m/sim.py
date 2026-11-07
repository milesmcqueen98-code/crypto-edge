#!/usr/bin/env python3
"""Size simulator for the wick catcher at $1M (reports/wick1m_prereg.md), version 2 after the independent review.

Step 1 (precompute): for every R2-08 trade (the parent bid at 4 sigma) and ladder tranche (6, 8 sigma), from 1-minute
candles on every venue (Coinbase spot, Coinbase perp, Bitstamp where present):
  - fills: the parent at its fill minute; deeper bids rest from the parent's fill minute until the parent's take-profit
    first trades or 60 minutes pass (cancelled when the parent closes);
  - entry capacity: USD volume traded below the bid while the price stayed below it (<= 15 minutes), each candle's
    volume spread evenly over its range; other venues' levels scaled by their price ratio to spot the minute before;
    the end of that window is kept so overlapping tranches share one pool of sellers;
  - take-profit (60% of the tranche's own dislocation): the first minute it trades, and USD volume above it in 60 min;
  - the 61-minute spot price path after the fill (mark-to-market) and the 60-minute close (market exit);
  - trailing 30-day median daily USD volume (Coinbase spot + perp; Bitstamp separately) and daily vol, as of the
    previous day.
Step 2 (evaluate): tranches in fill-time order; sellers and take-profit buyers shared within a parent, per venue;
fills limited by the cash cap at each fill's own time (take-profit parts release cash when the take-profit trades,
the rest at 60 minutes); fees at each venue's own volume tier; half-spread and square-root impact on market exits;
P&L booked on the exit day; optional minute-level mark-to-market equity for drawdowns.

  python scripts/wick1m/sim.py pre main | early | wide [out_tag]     (NO_BITSTAMP=1 to leave Bitstamp out)
Check-period statistics are computed only with WICK1M_CHECK=1.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import book  # noqa: E402
import wick_sim as ws  # noqa: E402

OUT = os.path.join(ROOT, "reports", "wick1m")
CHECK_OPEN = os.environ.get("WICK1M_CHECK") == "1"
SEL = ("2025-01-01", "2026-03-31")
CHK = ("2026-04-01", "2026-11-05")
EARLY = ("2022-01-01", "2023-12-31")
SPOT_TIERS = [(0, .0050, .0090), (10e3, .0035, .0075), (50e3, .0015, .0030), (250e3, .0010, .0015),
              (500e3, .0006, .00125), (20e6, .0001, .0005), (50e6, 0.0, .00035), (250e6, 0.0, .0002)]
# Coinbase Advanced VIP page (not confirmed for US accounts after the Sep 16 2026 change): sensitivity only
VIP_TIERS = [(0, .0050, .0090), (10e3, .0035, .0075), (50e3, .0015, .0030), (250e3, .0010, .0015),
             (500e3, .0006, .00125), (1e6, .0005, .0010), (5e6, .0004, .00085), (10e6, .00025, .00065),
             (20e6, .0001, .0005), (50e6, 0.0, .00035), (250e6, 0.0, .0002)]
SPOT_HS_BP = 2.0
SCAN_MIN, H = 15, 60
LADDER = (4.0, 6.0, 8.0)
IMPACT_Y = 0.7
VENUES = ("spot", "perp", "bitstamp")
PERIODS = {"main": ("2024-01-01", "2026-11-06", "minute"), "early": ("2021-01-01", "2024-01-01", "minute_early"),
           "wide": ("2024-01-01", "2026-11-06", "minute")}


# ------------------------------------------------------------------------------------------------ data
def load_venue(path, idx, mult=1.0):
    if not os.path.exists(path):
        return None
    m = pd.read_parquet(path).drop_duplicates("ts").set_index("ts").sort_index()
    m = m[m.volume > 0].reindex(idx)
    out = {k: m[k].to_numpy(np.float64) for k in ("open", "high", "low", "close")}
    out["vol"] = m["volume"].fillna(0.0).to_numpy(np.float64) * mult
    out["cf"] = m["close"].ffill(limit=30).to_numpy(np.float64)
    return out


def perp_mult():
    p = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
    return p[p.expiry_type == "PERPETUAL"].set_index("contract_root_unit")["contract_size"].to_dict()


def daily_usd(d, idx):
    return pd.Series(np.nan_to_num(d["cf"]) * d["vol"], index=idx).resample("D").sum()


def daily_stats(V, idx):
    """Trailing 30-day median daily USD volume (Coinbase spot + perp, and Bitstamp) and spot daily vol, as of the
    previous day."""
    cb = daily_usd(V["spot"], idx)
    if "perp" in V:
        cb = cb.add(daily_usd(V["perp"], idx), fill_value=0.0)
    med = lambda u: u.where(u > 0).rolling(30, min_periods=10).median().shift(1)  # noqa: E731
    adv_cb = med(cb)
    adv_bs = med(daily_usd(V["bitstamp"], idx)) if "bitstamp" in V else pd.Series(0.0, index=adv_cb.index)
    px = pd.Series(V["spot"]["cf"], index=idx).resample("D").last()
    vol_d = np.log(px).diff().rolling(30, min_periods=10).std().shift(1)
    return adv_cb, adv_bs, vol_d


def below_usd(d, i0, level, n=SCAN_MIN):
    """USD volume below `level` from minute i0 while the price stays below it; and that window's last minute."""
    tot, last = 0.0, i0
    for j, i in enumerate(range(i0, min(i0 + n + 1, len(d["low"])))):
        lo, hi, v = d["low"][i], d["high"][i], d["vol"][i]
        if not np.isfinite(lo) or lo >= level:
            if j == 0:
                continue
            break
        rng = hi - lo
        frac = 1.0 if rng <= 0 else min(1.0, (level - lo) / rng)
        tot += v * frac * 0.5 * (level + lo)
        last = i
    return tot, last


def above_usd(d, i0, i1, level):
    tot = 0.0
    for i in range(i0, min(i1 + 1, len(d["high"]))):
        lo, hi, v = d["low"][i], d["high"][i], d["vol"][i]
        if not np.isfinite(hi) or hi <= level:
            continue
        rng = hi - lo
        frac = 1.0 if rng <= 0 else min(1.0, (hi - level) / rng)
        tot += v * frac * 0.5 * (level + hi)
    return tot


def first_touch(hi_arr, i_from, i_to, price):
    """First minute index in [i_from, i_to] whose high reaches `price`, else -1."""
    seg = np.nan_to_num(hi_arr[i_from:i_to + 1])
    hit = np.nonzero(seg >= price)[0]
    return int(i_from + hit[0]) if len(hit) else -1


def precompute(tag, bitstamp=True, out_tag=None):
    start, end, src = PERIODS[tag]
    tr = pd.read_parquet(os.path.join(OUT, f"trades_{tag}.parquet"))
    ticks = {}
    if tag == "wide":
        tk = pd.read_csv(os.path.join(OUT, "spot_ticks_wide.csv"))
        ticks = {c: t for c, t in zip(tk.coin, tk.tick) if np.isfinite(t)}
        ticks.update(dict(ws.SPOT_TICK))                          # audited values win
    idx = pd.date_range(start, end, freq="min", inclusive="left")
    pm = perp_mult()
    rows = []
    for c in sorted(tr.coin.unique()):
        V = {"spot": load_venue(os.path.join(ROOT, "data", src, f"{c}.parquet"), idx)}
        if tag != "early" and c in pm:
            p = load_venue(os.path.join(ROOT, "data", "cfm", f"{c}.parquet"), idx, pm[c])
            if p is not None:
                V["perp"] = p
        b = load_venue(os.path.join(ROOT, "data", "bitstamp", f"{c}.parquet"), idx) if bitstamp else None
        if b is not None:
            V["bitstamp"] = b
        adv_cb, adv_bs, vol_d = daily_stats(V, idx)
        S = V["spot"]
        if c in ticks:
            tick_abs = ticks[c]
        else:
            try:
                tick_abs = ws.spot_tick(c)                       # the lab's fill tick
            except KeyError:
                tick_abs = np.nan
        n_idx = len(idx)
        for t in tr[tr.coin == c].itertuples():
            i0 = idx.get_indexer([t.ts])[0]
            if i0 < 1 or i0 + H + 1 >= n_idx:
                continue
            day = t.ts.floor("D")
            tickf0 = (tick_abs / t.px) if np.isfinite(tick_abs) else 0.0
            tp_par = t.px * np.exp(0.6 * t.k * t.sig)
            i_tp_par = first_touch(S["high"], i0 + 1, i0 + H, tp_par * (1 + tickf0))
            close_par = i_tp_par if i_tp_par >= 0 else i0 + H
            base = dict(ts=t.ts, coin=c, bot=bool(t.bot), adv=float(adv_cb.get(day, np.nan)),
                        adv_bs=float(adv_bs.get(day, np.nan)), vol_d=float(vol_d.get(day, np.nan)),
                        lab_gross=t.gross, lab_tp=bool(t.tp))
            for k in LADDER:
                lvl = t.px if k == t.k else float(np.exp(t.fair_log - k * t.sig))
                tickf = (tick_abs / lvl) if np.isfinite(tick_abs) else 0.0
                if k == t.k:
                    i_f = i0
                else:
                    lows = np.nan_to_num(S["low"][i0:close_par], nan=np.inf)
                    hit = np.nonzero(lows <= lvl * (1 - tickf))[0]
                    i_f = int(i0 + hit[0]) if len(hit) else -1
                row = dict(base, k=k, filled=i_f >= 0)
                if i_f < 0:
                    rows.append(row)
                    continue
                tp = lvl * np.exp(0.6 * k * t.sig)
                i_tp = first_touch(S["high"], i_f + 1, i_f + H, tp * (1 + tickf))
                for name in VENUES:
                    row[f"in_{name}"] = row[f"tp_{name}"] = 0.0
                scan_end = i_f
                for name, d in V.items():
                    if name == "spot":
                        ratio = 1.0
                    else:
                        a, s_ = d["cf"][i_f - 1], S["cf"][i_f - 1]
                        ratio = a / s_ if np.isfinite(a) and np.isfinite(s_) and s_ > 0 else np.nan
                    if not np.isfinite(ratio):
                        continue
                    usd, last = below_usd(d, i_f, lvl * ratio)
                    row[f"in_{name}"] = usd
                    if name == "spot":
                        scan_end = last
                    row[f"tp_{name}"] = above_usd(d, i_f + 1, i_f + H, tp * ratio)
                path = pd.Series(S["cf"][i_f:i_f + H + 1]).ffill().bfill().to_numpy()
                row.update(lvl=lvl, f_off=i_f - i0, tp_off=(i_tp - i_f) if i_tp >= 0 else -1, tp_hit=i_tp >= 0,
                           scan_off=scan_end - i0, g_tp=1e4 * np.log(tp / lvl), g60=1e4 * np.log(path[-1] / lvl),
                           path=np.log(path / lvl).astype(np.float32))
                rows.append(row)
        print(f"  {c}: {int((tr.coin == c).sum())} trades, venues {list(V)}", flush=True)
    P = pd.DataFrame(rows)
    for n in VENUES:
        for p_ in ("in_", "tp_"):
            if f"{p_}{n}" not in P:
                P[f"{p_}{n}"] = 0.0
            P[f"{p_}{n}"] = P[f"{p_}{n}"].fillna(0.0)
    name = out_tag or tag
    P.to_pickle(os.path.join(OUT, f"pre_{name}.pkl"))
    print(f"precomputed {len(P)} tranche rows for {P.ts.nunique()} trades -> pre_{name}.pkl")
    return P


# ------------------------------------------------------------------------------------------------ evaluation
def tier(v30, table=SPOT_TIERS):
    out = table[0]
    for t in table:
        if v30 >= t[0]:
            out = t
    return out[1], out[2]


def perp_cost():
    ct = pd.read_csv(os.path.join(ROOT, "reports", "lab", "cost_table.csv")).set_index("coin")
    return ct.fee_bp_side.to_dict(), (1.5 * ct.half_spread_bp).to_dict()


def evaluate(P, kappa=None, ladder=False, exit_rule="E0", trade_list="bot", theta=0.5, C=1e6, gross_cap=1.0,
             per_trade=0.25, days=None, tiers=SPOT_TIERS, drop_same_minute=False, use_bitstamp=True, mtm=False,
             weights=None):
    """Per-tranche USD P&L, daily returns (P&L booked on the exit day) and, with mtm=True, minute-level equity."""
    if exit_rule != "E0":
        raise ValueError("version 2 implements the market exit (E0) only")
    fee_perp, hs_perp = perp_cost()
    Q = P[P.filled].copy()
    if weights is not None:                                    # wick v4: rung weights {k: share of the signal}
        ladder = True
        Q = Q[Q.k.isin(list(weights))]
    if not ladder:
        Q = Q[Q.k == LADDER[0]]
    if trade_list == "bot":
        Q = Q[Q.bot]
    if drop_same_minute:
        Q = Q[(Q.k == LADDER[0]) | (Q.f_off > 0)]
    venues = [v for v in VENUES if use_bitstamp or v != "bitstamp"]
    Q["fill_t"] = Q.ts + pd.to_timedelta(Q.f_off, unit="m")
    Q = Q.sort_values(["fill_t", "coin", "k"]).reset_index(drop=True)
    nk = 3.0 if ladder else 1.0
    want_tot = np.full(len(Q), per_trade * C)
    if kappa is not None:
        want_tot = np.minimum(want_tot, kappa * Q.adv.fillna(0.0).to_numpy())
    want = want_tot / nk
    if weights is not None:
        wsum = float(sum(weights.values()))
        want = want_tot * Q.k.map({k: w / wsum for k, w in weights.items()}).to_numpy()
    cap_in = {v: theta * Q[f"in_{v}"].to_numpy() for v in venues}
    cap_tp = {v: theta * Q[f"tp_{v}"].to_numpy() for v in venues}
    fill_v = {v: np.zeros(len(Q)) for v in venues}
    tp_v = {v: np.zeros(len(Q)) for v in venues}
    pool, used, used_tp, scan = {}, {}, {}, {}
    ft = Q.fill_t.to_numpy()
    tp_off = Q.tp_off.to_numpy()
    f_off = Q.f_off.to_numpy()
    scan_off = Q.scan_off.to_numpy()
    releases = []                                              # (time, amount) of cash returning
    open_amt = 0.0
    keys = list(zip(Q.ts, Q.coin))
    kk = Q.k.to_numpy()
    for i in range(len(Q)):
        while releases and releases[0][0] <= ft[i]:
            open_amt -= releases.pop(0)[1]
        key = keys[i]
        caps = np.array([cap_in[v][i] for v in venues])
        if kk[i] == LADDER[0]:
            pool[key] = {v: cap_in[v][i] for v in venues}
            used[key] = {v: 0.0 for v in venues}
            used_tp[key] = {v: 0.0 for v in venues}
            scan[key] = scan_off[i]
        elif key in pool and f_off[i] <= scan[key]:            # same sellers as the parent: share its pool
            caps = np.array([min(cap_in[v][i], max(0.0, pool[key][v] - used[key][v])) for v in venues])
        tot_cap = caps.sum()
        total = min(want[i], tot_cap)
        room = gross_cap * C - open_amt if gross_cap is not None else np.inf
        if total > room:
            total = room if room > 0.1 * want[i] else 0.0
        if total <= 0 or tot_cap <= 0:
            continue
        tpa = 0.0
        for j, v in enumerate(venues):
            f = total * caps[j] / tot_cap
            fill_v[v][i] = f
            if key in used:
                used[key][v] += f
            if tp_off[i] >= 0:                                 # take-profit buyers shared across the parent's tranches
                avail = cap_tp[v][i] - (used_tp[key][v] if key in used_tp else 0.0)
                tp_v[v][i] = max(0.0, min(f, avail))
                if key in used_tp:
                    used_tp[key][v] += tp_v[v][i]
                tpa += tp_v[v][i]
        open_amt += total
        if tpa > 0:
            releases.append((ft[i] + np.timedelta64(int(tp_off[i]), "m"), tpa))
        releases.append((ft[i] + np.timedelta64(H, "m"), total - tpa))
        releases.sort(key=lambda r: r[0])
    fill = sum(fill_v.values())
    tpf = sum(tp_v.values())
    rem_v = {v: fill_v[v] - tp_v[v] for v in venues}
    span = days or max(1.0, (Q.ts.max() - Q.ts.min()).days)
    mk, tk = tier(2 * fill_v["spot"].sum() / span * 30, tiers)
    if "bitstamp" in venues:
        bmk, btk = tier(2 * fill_v["bitstamp"].sum() / span * 30, tiers)
    else:
        bmk = btk = 0.0
    fp = Q.coin.map(fee_perp).fillna(5.0).to_numpy() / 1e4
    hp = Q.coin.map(hs_perp).fillna(5.0).to_numpy() / 1e4
    maker = {"spot": mk, "perp": fp + 1e-4, "bitstamp": bmk}
    maker_x = {"spot": mk, "perp": fp, "bitstamp": bmk}
    taker = {"spot": tk + SPOT_HS_BP / 1e4, "perp": fp + hp, "bitstamp": btk + SPOT_HS_BP / 1e4}
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    rem = fill - tpf
    imp = IMPACT_Y * vol_d * np.sqrt(np.maximum(rem, 0.0) / adv)
    g_tp, g60 = Q.g_tp.to_numpy() / 1e4, Q.g60.to_numpy() / 1e4
    pnl_tp = sum(tp_v[v] * (g_tp - maker_x[v]) for v in venues)
    pnl_rem = sum(rem_v[v] * (g60 - taker[v] - imp) for v in venues)
    entry = sum(fill_v[v] * maker[v] for v in venues)
    Q["fill"], Q["tp_fill"], Q["pnl_tp"], Q["pnl_rem"], Q["entry_cost"] = fill, tpf, pnl_tp, pnl_rem, entry
    Q["pnl"] = pnl_tp + pnl_rem - entry
    tp_t = Q.fill_t + pd.to_timedelta(np.where(tp_off >= 0, tp_off, H), unit="m")
    ex_t = Q.fill_t + pd.Timedelta(minutes=H)
    daily = pd.concat([pd.Series(pnl_tp - entry, index=tp_t.dt.floor("D").to_numpy()),
                       pd.Series(pnl_rem, index=ex_t.dt.floor("D").to_numpy())]).groupby(level=0).sum()
    info = dict(v30=2 * fill.sum() / span * 30, v30_spot=2 * fill_v["spot"].sum() / span * 30, maker_bp=mk * 1e4,
                taker_bp=tk * 1e4, bitstamp_maker_bp=bmk * 1e4)
    if mtm:
        info["equity"] = mtm_equity(Q, tp_t, ex_t)
    return Q, daily, info


def mtm_equity(Q, tp_t, ex_t):
    """Minute-level cumulative P&L: realized at exits plus open positions marked to the spot price."""
    q = Q[Q.fill > 0]
    recs = []
    for r, t1 in zip(q.itertuples(), tp_t[q.index]):
        path = np.exp(r.path.astype(np.float64)) - 1.0
        m = np.arange(len(path))
        open_ = np.where((r.tp_off >= 0) & (m >= r.tp_off), r.fill - r.tp_fill, r.fill)
        u = open_ * path - r.entry_cost                        # entry cost is booked with the exit in R
        u[-1] = 0.0                                            # minute 60: the remainder is realized in R
        recs.append(pd.DataFrame({"t": r.fill_t + pd.to_timedelta(m, unit="m"), "u": u}))
    U = pd.concat(recs).groupby("t").u.sum() if recs else pd.Series(dtype=float)
    R = pd.concat([pd.Series(q.pnl_tp.to_numpy(), index=tp_t[q.index].to_numpy()),
                   pd.Series((q.pnl_rem - q.entry_cost).to_numpy(), index=ex_t[q.index].to_numpy())])
    R = R.groupby(level=0).sum()
    t_all = U.index.union(R.index)
    return R.reindex(t_all, fill_value=0.0).cumsum() + U.reindex(t_all, fill_value=0.0)


def period_stats(daily, C, lo, hi, equity=None):
    idx = pd.date_range(lo, hi, freq="D")
    r = daily.reindex(idx, fill_value=0.0) / C
    if len(r) < 30:
        return {}
    ex = r - book.rf_daily(idx).to_numpy()
    eq = (1 + r).cumprod()
    yrs = len(idx) / 365.25
    out = dict(ret_yr=float(r.sum() / yrs), sharpe=float(ex.mean() / ex.std() * np.sqrt(365)) if ex.std() > 0 else np.nan,
               sharpe_raw=float(r.mean() / r.std() * np.sqrt(365)) if r.std() > 0 else np.nan,
               maxdd=float((eq / eq.cummax() - 1).min()), dollars_yr=float(r.sum() * C / yrs))
    if equity is not None and len(equity):
        e = equity[(equity.index >= pd.Timestamp(lo)) & (equity.index < pd.Timestamp(hi) + pd.Timedelta(days=1))]
        if len(e):
            lvl = C + (e - e.iloc[0])
            out["maxdd_mtm"] = float((lvl / lvl.cummax() - 1).min())
    d = daily.reindex(idx, fill_value=0.0)
    top = d.sort_values(ascending=False)
    tot = d.sum()
    out["top3_share"] = float(top.head(3).sum() / tot) if tot else np.nan
    out["top10_share"] = float(top.head(10).sum() / tot) if tot else np.nan
    keep = ~d.index.isin(top.head(3).index)
    rr = ex[keep]
    out["ret_ex_top3"] = float(r[keep].sum() / yrs)
    out["sharpe_ex_top3"] = float(rr.mean() / rr.std() * np.sqrt(365)) if rr.std() > 0 else np.nan
    rng = np.random.default_rng(0)
    blocks = [g.to_numpy() for _, g in ex.groupby(np.arange(len(ex)) // 7)]
    sims = []
    for _ in range(2000):
        x = np.concatenate([blocks[j] for j in rng.integers(0, len(blocks), len(blocks))])
        sims.append(x.mean() / x.std() * np.sqrt(365) if x.std() > 0 else np.nan)
    sims = np.array(sims)
    out["sharpe_p05"], out["sharpe_p95"] = float(np.nanpercentile(sims, 5)), float(np.nanpercentile(sims, 95))
    out["p_sharpe_lt2"] = float(np.nanmean(sims < 2.0))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "pre":
        bs = os.environ.get("NO_BITSTAMP") != "1"
        precompute(sys.argv[2], bitstamp=bs, out_tag=sys.argv[3] if len(sys.argv) > 3 else None)
