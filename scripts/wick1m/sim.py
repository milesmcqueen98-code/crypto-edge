#!/usr/bin/env python3
"""Size simulator for the wick catcher at $1M (reports/wick1m_prereg.md).

Step 1 (precompute): for every R2-08 trade and ladder tranche (4, 6, 8 sigma below fair value) measure, from 1-minute
candles on every venue (Coinbase spot, Coinbase perp, Bitstamp where present):
  - whether and when the tranche's bid fills (deeper tranches rest for 60 minutes after the first fill);
  - entry capacity: USD volume traded below the bid while the price stayed below it (<= 15 minutes), each candle's
    volume spread evenly over its range; other venues' levels scaled by their price ratio to spot the minute before;
  - take-profit (60% of the tranche's own dislocation): whether it trades, and the USD volume above it within 60 min;
  - the 60-minute close, and the next 240 minutes of combined USD volume and typical price for participation exits;
  - trailing 30-day median daily USD volume (all venues) and daily vol, as of the day before.
Step 2 (evaluate): a configuration (size cap kappa, ladder, exit rule, trade list, capture theta, capital) gives
per-trade P&L after fees at the book's own volume tier, half-spreads and square-root impact, then daily returns.

  python scripts/wick1m/sim.py pre main | early | wide     -> reports/wick1m/pre_<tag>.parquet
Check-period statistics are computed only with WICK1M_CHECK=1 (opened once).
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
SPOT_HS_BP = 2.0
BITSTAMP_BIG = (0.0002, 0.0005)        # maker / taker at >= $10M a month (published range 0.00-0.30% / 0.03-0.40%)
SCAN_MIN, H, POV_WIN = 15, 60, 240
LADDER = (4.0, 6.0, 8.0)
IMPACT_Y = 0.7
PERIODS = {"main": ("2024-01-01", "2026-11-06", "minute", True), "early": ("2021-01-01", "2024-01-01", "minute_early", False),
           "wide": ("2024-01-01", "2026-11-06", "minute", True)}


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


def daily_stats(V, idx):
    """Trailing 30-day median daily USD volume (all venues) and daily vol of spot, as of the previous day."""
    usd = None
    for name, d in V.items():
        u = pd.Series(np.nan_to_num(d["cf"]) * d["vol"], index=idx).resample("D").sum()
        usd = u if usd is None else usd.add(u, fill_value=0.0)
    adv = usd.where(usd > 0).rolling(30, min_periods=10).median().shift(1)
    px = pd.Series(V["spot"]["cf"], index=idx).resample("D").last()
    vol_d = np.log(px).diff().rolling(30, min_periods=10).std().shift(1)
    return adv, vol_d


def below_usd(d, i0, level, n=SCAN_MIN):
    tot = 0.0
    for j, i in enumerate(range(i0, min(i0 + n + 1, len(d["low"])))):
        lo, hi, v = d["low"][i], d["high"][i], d["vol"][i]
        if not np.isfinite(lo) or lo >= level:
            if j == 0:
                continue
            break
        rng = hi - lo
        frac = 1.0 if rng <= 0 else min(1.0, (level - lo) / rng)
        tot += v * frac * 0.5 * (level + lo)
    return tot


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


def precompute(tag, bitstamp=True, out_tag=None):
    start, end, src, _ = PERIODS[tag]
    tr = pd.read_parquet(os.path.join(OUT, f"trades_{tag}.parquet"))
    ticks = {}
    if tag == "wide":                          # spot execution: estimated spot ticks for every coin (trades_wide.py)
        tk = pd.read_csv(os.path.join(OUT, "spot_ticks_wide.csv"))
        ticks = dict(zip(tk.coin, tk.tick))
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
        adv, vol_d = daily_stats(V, idx)
        S = V["spot"]
        if c in ticks:
            tick_abs = ticks[c]
        else:
            try:                               # the lab's fill tick: the coarser of the spot and perp ticks
                tick_abs = ws.spot_tick(c)
            except KeyError:
                tick_abs = ws.SPOT_TICK.get(c, np.nan)
        for t in tr[tr.coin == c].itertuples():
            i0 = idx.get_indexer([t.ts])[0]
            if i0 < 1:
                continue
            day = t.ts.floor("D")
            base = dict(ts=t.ts, coin=c, bot=bool(t.bot), adv=float(adv.get(day, np.nan)),
                        vol_d=float(vol_d.get(day, np.nan)), lab_gross=t.gross, lab_tp=bool(t.tp))
            for k in LADDER:
                lvl = t.px if k == t.k else float(np.exp(t.fair_log - k * t.sig))
                tickf = (tick_abs / lvl) if np.isfinite(tick_abs) else 0.0
                if k == t.k:
                    i_f = i0
                else:
                    i_f = -1
                    for i in range(i0, min(i0 + H, len(idx))):
                        lo = S["low"][i]
                        if np.isfinite(lo) and lo <= lvl * (1 - tickf):
                            i_f = i
                            break
                row = dict(base, k=k, filled=i_f >= 0)
                if i_f < 0:
                    rows.append(row)
                    continue
                tp = lvl * np.exp(0.6 * k * t.sig)
                cap_in, cap_tp = {}, {}
                for name, d in V.items():
                    if name == "spot":
                        ratio = 1.0
                    else:
                        a, s_ = d["cf"][i_f - 1], S["cf"][i_f - 1]
                        ratio = a / s_ if np.isfinite(a) and np.isfinite(s_) and s_ > 0 else np.nan
                    if not np.isfinite(ratio):
                        cap_in[name] = cap_tp[name] = 0.0
                        continue
                    cap_in[name] = below_usd(d, i_f, lvl * ratio)
                    cap_tp[name] = above_usd(d, i_f + 1, i_f + H, tp * ratio)
                # take-profit trades on spot within 60 minutes (post-only sell traded through by a tick)
                hi = S["high"][i_f + 1:i_f + H + 1]
                hit = bool(np.any(np.nan_to_num(hi) >= tp * (1 + tickf)))
                j60 = min(i_f + H, len(idx) - 1)
                c60 = S["cf"][j60]
                w = slice(j60 + 1, min(j60 + 1 + POV_WIN, len(idx)))
                typ = (S["high"][w] + S["low"][w] + S["close"][w]) / 3.0
                typ = np.where(np.isfinite(typ), typ, S["cf"][w])
                vusd = sum(np.nan_to_num(d["cf"][w]) * d["vol"][w] for d in V.values())
                ok = np.isfinite(typ)
                cumv = np.cumsum(np.where(ok, vusd, 0.0))
                cumg = np.cumsum(np.where(ok, vusd * np.log(np.where(ok, typ, lvl) / lvl), 0.0))
                cend = S["cf"][w][-1] if len(typ) else c60
                row.update(lvl=lvl, tp_px=tp, tp_hit=hit, g_tp=1e4 * np.log(tp / lvl), g60=1e4 * np.log(c60 / lvl),
                           g_end=1e4 * np.log(cend / lvl), pov_v=cumv.astype(np.float32), pov_g=cumg.astype(np.float32),
                           **{f"in_{n}": v for n, v in cap_in.items()}, **{f"tp_{n}": v for n, v in cap_tp.items()})
                rows.append(row)
        print(f"  {c}: {int((tr.coin == c).sum())} trades, venues {list(V)}", flush=True)
    P = pd.DataFrame(rows)
    for n in ("spot", "perp", "bitstamp"):
        for p_ in ("in_", "tp_"):
            if f"{p_}{n}" not in P:
                P[f"{p_}{n}"] = 0.0
            P[f"{p_}{n}"] = P[f"{p_}{n}"].fillna(0.0)
    name = out_tag or tag
    P.to_pickle(os.path.join(OUT, f"pre_{name}.pkl"))
    print(f"precomputed {len(P)} tranche rows for {P.ts.nunique()} trades -> pre_{name}.pkl")
    return P


# ------------------------------------------------------------------------------------------------ evaluation
def tier(v30):
    out = SPOT_TIERS[0]
    for t in SPOT_TIERS:
        if v30 >= t[0]:
            out = t
    return out[1], out[2]


def perp_cost():
    """Per-side perp cost in bp at today's contract values ($0.20/contract) and 1.5x measured perp half-spread."""
    ct = pd.read_csv(os.path.join(ROOT, "reports", "lab", "cost_table.csv")).set_index("coin")
    return ct.fee_bp_side.to_dict(), (1.5 * ct.half_spread_bp).to_dict()


def evaluate(P, kappa=None, ladder=False, exit_rule="E0", trade_list="bot", theta=0.5, C=1e6, gross_cap=1.0,
             per_trade=0.25, days=None):
    """Per-trade P&L (USD) and daily returns for one configuration."""
    fee_perp, hs_perp = perp_cost()
    Q = P[P.filled].copy()
    if not ladder:
        Q = Q[Q.k == LADDER[0]]
    if trade_list == "bot":
        Q = Q[Q.bot]
    Q = Q.sort_values(["ts", "coin", "k"]).reset_index(drop=True)
    want_tot = np.full(len(Q), per_trade * C)
    if kappa is not None:
        want_tot = np.minimum(want_tot, kappa * Q.adv.fillna(0.0).to_numpy())
    nk = 3.0 if ladder else 1.0
    want = want_tot / nk
    cap_in = Q.in_spot + Q.in_perp + Q.in_bitstamp
    fill = np.minimum(want, theta * cap_in.to_numpy())
    # gross cap for the uncapped list: open notional (tranche fills, held up to 60 + exit minutes) <= gross_cap x C
    if gross_cap is not None:
        ts = Q.ts.to_numpy()
        hold = np.timedelta64(H + (POV_WIN if exit_rule != "E0" else 0), "m")
        open_end, open_n, keep = [], [], np.ones(len(Q), bool)
        for i in range(len(Q)):
            alive = [j for j, e in enumerate(open_end) if e > ts[i]]
            open_end = [open_end[j] for j in alive]
            open_n = [open_n[j] for j in alive]
            room = gross_cap * C - sum(open_n)
            if room <= 0.1 * fill[i]:
                keep[i] = False
                fill[i] = 0.0
                continue
            fill[i] = min(fill[i], room)
            open_end.append(ts[i] + hold)
            open_n.append(fill[i])
    sh_in = {n: np.where(cap_in > 0, Q[f"in_{n}"] / cap_in.replace(0, np.nan), 0.0) for n in ("spot", "perp", "bitstamp")}
    sh_in["spot"] = np.where(cap_in > 0, sh_in["spot"], 1.0)
    cap_tp = Q.tp_spot + Q.tp_perp + Q.tp_bitstamp
    tp_fill = np.where(Q.tp_hit, np.minimum(fill, theta * cap_tp.to_numpy()), 0.0)
    rem = fill - tp_fill
    # fees: spot at the book's own tier; perp per contract; Bitstamp at its large-volume tier
    span_days = days or max(1.0, (Q.ts.max() - Q.ts.min()).days)
    v30 = 2 * fill.sum() / span_days * 30
    mk, tk = tier(v30)
    bmk, btk = BITSTAMP_BIG if v30 >= 10e6 else (mk, tk)
    fp = Q.coin.map(fee_perp).fillna(5.0).to_numpy() / 1e4
    hp = Q.coin.map(hs_perp).fillna(5.0).to_numpy() / 1e4
    maker = sh_in["spot"] * mk + sh_in["perp"] * (fp + 1e-4) + sh_in["bitstamp"] * bmk       # entry (+1 bp funding on perps)
    sh_tp = {n: np.where(cap_tp > 0, Q[f"tp_{n}"] / cap_tp.replace(0, np.nan), 0.0) for n in ("spot", "perp", "bitstamp")}
    maker_tp = sh_tp["spot"] * mk + sh_tp["perp"] * fp + sh_tp["bitstamp"] * bmk
    taker = sh_in["spot"] * (tk + SPOT_HS_BP / 1e4) + sh_in["perp"] * (fp + hp) + sh_in["bitstamp"] * (btk + SPOT_HS_BP / 1e4)
    taker = np.where(cap_in > 0, taker, tk + SPOT_HS_BP / 1e4)
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    imp = lambda s: IMPACT_Y * vol_d * np.sqrt(np.maximum(s, 0.0) / adv)  # noqa: E731
    imp_i = lambda s, i: IMPACT_Y * vol_d[i] * np.sqrt(max(s, 0.0) / adv[i])  # noqa: E731
    if exit_rule == "E0":
        pnl_rem = rem * (Q.g60.to_numpy() / 1e4 - taker - imp(rem))
    else:
        p = 0.10 if exit_rule == "E1" else 0.25
        pnl_rem = np.zeros(len(Q))
        for i in range(len(Q)):
            if rem[i] <= 0:
                continue
            cv = p * Q.pov_v.iat[i].astype(np.float64)
            cg = p * Q.pov_g.iat[i].astype(np.float64)
            if len(cv) == 0 or cv[-1] <= 0:
                sold, g_sold = 0.0, 0.0
            elif cv[-1] >= rem[i]:
                j = int(np.searchsorted(cv, rem[i]))
                prev_v = cv[j - 1] if j > 0 else 0.0
                prev_g = cg[j - 1] if j > 0 else 0.0
                part = (rem[i] - prev_v) / max(cv[j] - prev_v, 1e-12)
                g_sold = prev_g + part * (cg[j] - prev_g)
                sold = rem[i]
            else:
                sold, g_sold = cv[-1], cg[-1]
            left = rem[i] - sold
            pnl_rem[i] = (g_sold - sold * (taker[i] + imp_i(sold, i))
                          + left * (Q.g_end.iat[i] / 1e4 - taker[i] - imp_i(left, i)))
    pnl = tp_fill * (Q.g_tp.to_numpy() / 1e4 - maker_tp) + pnl_rem - fill * maker
    Q["fill"], Q["tp_fill"], Q["pnl"] = fill, tp_fill, pnl
    daily = pd.Series(pnl, index=Q.ts.dt.floor("D")).groupby(level=0).sum()
    return Q, daily, dict(v30=v30, maker_bp=mk * 1e4, taker_bp=tk * 1e4)


def period_stats(daily, C, lo, hi):
    idx = pd.date_range(lo, hi, freq="D")
    r = daily.reindex(idx, fill_value=0.0) / C
    if len(r) < 30:
        return {}
    ex = r - book.rf_daily(idx).to_numpy()
    eq = (1 + r).cumprod()
    yrs = len(idx) / 365.25
    return dict(ret_yr=float(r.sum() / yrs), sharpe=float(ex.mean() / ex.std() * np.sqrt(365)) if ex.std() > 0 else np.nan,
                maxdd=float((eq / eq.cummax() - 1).min()), dollars_yr=float(r.sum() * C / yrs))


if __name__ == "__main__":
    if sys.argv[1] == "pre":
        bs = os.environ.get("NO_BITSTAMP") != "1"
        precompute(sys.argv[2], bitstamp=bs, out_tag=sys.argv[3] if len(sys.argv) > 3 else None)
