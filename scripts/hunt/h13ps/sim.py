#!/usr/bin/env python3
"""H13 (PS) simulation core (reports/hunt/h13ps/SPEC.md). Imported by dev.py (DEV trials), final.py (frozen variant)
and checks.py. Reads the runner's reduced prints (data/hunt/h13ps/prints/, see fetch_trades.py).

Trades (fixed by the SPEC; long only, spot):
- Mode I (inventory into the switch): from T_lo + 60 min a post-only bid one tick under the last print (>= 1 s old),
  refreshed every minute; a slot fills only from prints strictly below the bid (<= bid - 1 tick), size <= theta x that
  through-volume, up to the target. Bidding stops at T_ft (or T_lo + 48 h). Everything is sold at T_ft + H with a
  taker order (first print >= 2 s after the decision). No trade if T_ft - T_lo < 60 min. If full trading has not come
  by T_lo + 48 h, exit at T_lo + 48 h.
- Mode II (after the switch): taker buy at the first print at least Delta after T_ft; taker sell at T_ft + H (first
  print >= 2 s after T_ft + H).
- Target size: min($5K, 5% of the USD printed in the 60 minutes before the decision, prints >= 1 s old).
- Costs: maker 6 bp, taker 12.5 bp (common.SPOT_MAKER / SPOT_TAKER); taker legs pay max(1.5 x half-spread, 2 bp) on top.
  Half-spread from opposite-aggressor print pairs in the 10 minutes before each leg's decision, with builder h5an's
  fallbacks (>= 3 pairs at most 10 s apart in the 10 min; else in the hour; else >= 1 pair any gap in the hour;
  else 50 bp). 2x doubles fees and half-spreads.
Engineering choices (not in the SPEC; fixed here before any trial was scored):
- Mode I target and cash are fixed at the first bid (T_lo + 60 min); the target is reserved as cash from then until
  the exit (resting bids reserve cash). Mode II reserves its notional from entry to exit. Events are taken in time
  order; one that would breach the sleeve's capital is cut to the free cash (skipped if none).
- If no print exists 2 s to 60 min after an exit decision inside the fetched window (T_ft + 3 h), the exit is the last
  print before the decision (flagged, counted). A Mode II entry after its exit decision is skipped.
- Events with T_ft - T_lo > 48 h are fetched in two windows (fetch_trades.py); for their Mode II decisions the
  limit-only USD volume feature is unknown (NaN) because the gap was not fetched.
- P&L is booked on the exit's UTC calendar day. Daily return = P&L / sleeve capital; 0 on idle days.
"""
import glob
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402
import gates  # noqa: E402

IDEA = "h13ps"
PR = os.path.join(ROOT, "data", "hunt", "h13ps", "prints")
OUT = os.path.join(ROOT, "reports", "hunt", "h13ps")
EVENTS = os.path.join(OUT, "events.csv")
SCORED = pd.DatetimeIndex(gates.ERA_DAYS)
SIZE_CAP, VOL_FRAC = 5000.0, 0.05
HS_DEFAULT_BP, HS_MIN_BP, HS_MULT = 50.0, common.SPOT_HALF_SPREAD_BP, 1.5
HOLDS = (5, 30, 120)
DELTAS = (2, 60)
MS = 1000
MIN = 60 * MS


def frozen_committed():
    """True once reports/hunt/h13ps/frozen.json is committed and pushed (the freeze)."""
    p = os.path.join(OUT, "frozen.json")
    if not os.path.exists(p):
        return False
    try:
        subprocess.check_output(["git", "-C", ROOT, "fetch", "-q", "origin", "hunt/h13ps"], stderr=subprocess.DEVNULL)
        out = subprocess.check_output(["git", "-C", ROOT, "ls-tree", "--name-only", "FETCH_HEAD",
                                       "reports/hunt/h13ps/frozen.json"], text=True).strip()
        return out != ""
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------------ data
def _read(kind, parts):
    fs = []
    for part in parts:
        fs += sorted(glob.glob(os.path.join(PR, f"{kind}_{part}_*.parquet")))
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


def load(stage="dev"):
    """Events with their lookups. stage 'dev' reads only DEV files and drops anything ending on/after HOLD0;
    stage 'all' (after the freeze only) reads HOLD files too."""
    if stage == "all" and not frozen_committed():
        raise RuntimeError("HOLD files may be read only after the freeze commit is pushed (reports/hunt_prereg.md)")
    parts = ("dev",) if stage == "dev" else ("dev", "hold")
    E = pd.read_csv(EVENTS, parse_dates=["T_lo", "T_ft", "T_auction", "T_postonly", "T_transfer"])
    E = E[E.in_universe].copy()
    V = _read("ev", parts)
    V = V.drop(columns=[c for c in ("tick_now",) if c in V.columns])
    S = _read("slot", parts)
    M = E.merge(V, on="key", how="inner")
    if stage == "dev":
        M = M[M.T_ft + pd.Timedelta(hours=3) < gates.HOLD0].copy()
        S = S[S.key.isin(M.key)]
    M["lo_ms"] = M.T_lo.astype("datetime64[ms]").astype("int64")
    M["ft_ms"] = M.T_ft.astype("datetime64[ms]").astype("int64")
    M["lo_dur_min"] = (M.ft_ms - M.lo_ms) / MIN
    for leg in ("e2", "e60", "x5", "x30", "x120", "x48"):
        M[f"{leg}_hs_bp"], M[f"{leg}_hs_src"] = hs_used(M, leg)
    return M.sort_values(["T_lo", "key"]).reset_index(drop=True), S


def hs_used(M, leg):
    a, b, c = M[f"{leg}_hs10_pairs"].fillna(0), M[f"{leg}_hs60_pairs"].fillna(0), M[f"{leg}_hs60any_pairs"].fillna(0)
    hs = np.where(a >= 3, M[f"{leg}_hs10"], np.where(b >= 3, M[f"{leg}_hs60"],
                                                     np.where(c >= 1, M[f"{leg}_hs60any"], np.nan)))
    src = np.where(a >= 3, "hs10", np.where(b >= 3, "hs60", np.where(c >= 1, "hs60any", "default")))
    hs = np.where(np.isnan(hs.astype(float)), HS_DEFAULT_BP, hs.astype(float))
    return hs, src


def charge(hs_bp, mult):
    return mult * np.maximum(HS_MULT * hs_bp, HS_MIN_BP) / 1e4


# ------------------------------------------------------------------ trades
def exit_leg(M, H):
    """Exit leg per event: x{H}, or x48 if full trading had not come by T_lo + 48 h (Mode I only)."""
    return np.where(M.ft_ms > M.lo_ms + 48 * 60 * MIN, "x48", f"x{H}")


def _exit(M, leg_col):
    px = np.array([M.at[i, f"{lg}_fill_px"] for i, lg in zip(M.index, leg_col)], float)
    tm = np.array([M.at[i, f"{lg}_fill_ms"] for i, lg in zip(M.index, leg_col)], float)
    hs = np.array([M.at[i, f"{lg}_hs_bp"] for i, lg in zip(M.index, leg_col)], float)
    dec = np.array([M.at[i, f"{lg}_dec_ms"] for i, lg in zip(M.index, leg_col)], float)
    last = np.array([M.at[i, f"{lg}_last_px"] for i, lg in zip(M.index, leg_col)], float)
    fb = ~np.isfinite(px) | ~np.isfinite(tm) | (tm - dec > 60 * MIN)    # no print within 60 min of the decision
    px = np.where(fb, last, px)
    tm = np.where(fb, dec + 2 * MS, tm)
    return px, tm, hs, fb


def mode1_raw(M, S, H, theta, mult):
    """Mode I per event before the cash constraint: target, fills (base, cost), exit. One row per event that bids."""
    m = M[M.lo_dur_min >= 60].copy()
    m["target"] = np.minimum(SIZE_CAP, VOL_FRAC * m.mI_usd60.fillna(0.0))
    m = m[m.target > 0]
    leg = exit_leg(m, H)
    m["x_leg"] = leg
    m["x_px"], m["x_ms"], m["x_hs_bp"], m["x_fallback"] = _exit(m, leg)
    m["start_ms"] = m.lo_ms + 60 * MIN
    m = m[np.isfinite(m.x_px)]
    return m


def fill_mode1(m, S, theta, budget):
    """Fills of one Mode I event given its USD budget: walk its slots in time order."""
    sl = S.get(m.key)
    if sl is None or budget <= 0:
        return 0.0, 0.0, 0, None
    base = cost = 0.0
    n = 0
    first_ms = None
    for L, thru, a in zip(sl[0], sl[1], sl[2]):
        rem = budget - cost
        if rem <= 1e-9:
            break
        b = min(rem / L, theta * thru)
        if b <= 0:
            continue
        base += b
        cost += b * L
        n += 1
        first_ms = a if first_ms is None else first_ms
    return base, cost, n, first_ms


def trades(M, S, mode, H, mult, theta=0.5, delta=2, capital=30000.0, take=None):
    """One row per traded event with $ P&L at `mult` x costs. mode 1 or 2. take: optional boolean Series (AI filter)
    indexed like M."""
    fm, ft_ = mult * common.SPOT_MAKER, mult * common.SPOT_TAKER
    if take is not None:
        M = M[take.reindex(M.index).fillna(False).to_numpy()]
    if mode == 1:
        m = mode1_raw(M, S, H, theta, mult)
        if len(m) == 0:
            return pd.DataFrame()
        sg = {k: (g.L.to_numpy(), g.thru_base.to_numpy(), g.a_ms.to_numpy())
              for k, g in S[S.key.isin(m.key)].sort_values(["key", "k"]).groupby("key")}
        m = m.sort_values(["start_ms", "key"])
        open_pos, rows = [], []
        for r in m.itertuples():
            open_pos = [(x, s) for x, s in open_pos if x > r.start_ms]
            free = capital - sum(s for _, s in open_pos)
            budget = max(0.0, min(r.target, free))
            if budget <= 0:
                continue
            base, cost, n, first_ms = fill_mode1(r, sg, theta, budget)
            open_pos.append((r.x_ms, budget))
            if base <= 0:
                continue
            c_x = charge(r.x_hs_bp, mult)
            proceeds = base * r.x_px * (1 - c_x) * (1 - ft_)
            pnl = proceeds - cost * (1 + fm)
            rows.append(dict(key=r.key, pid=r.pid, base_ccy=r.base, T_lo=r.T_lo, T_ft=r.T_ft, entry_ms=first_ms,
                             x_ms=r.x_ms, usd=cost, budget=budget, target=r.target, n_fills=n, vwap=cost / base,
                             x_px=r.x_px, x_hs_bp=r.x_hs_bp, x_fallback=bool(r.x_fallback),
                             gross=r.x_px / (cost / base) - 1, net=pnl / cost, pnl=pnl))
        t = pd.DataFrame(rows)
    else:
        m = M.copy()
        e = f"e{delta}"
        m["target"] = np.minimum(SIZE_CAP, VOL_FRAC * m[f"{e}_usd60"].fillna(0.0))
        m["e_px"], m["e_ms"] = m[f"{e}_fill_px"].astype(float), m[f"{e}_fill_ms"].astype(float)
        leg = np.array([f"x{H}"] * len(m))
        m["x_px"], m["x_ms"], m["x_hs_bp"], m["x_fallback"] = _exit(m, leg)
        m = m[np.isfinite(m.e_px) & (m.target > 0) & (m.e_ms < m[f"x{H}_dec_ms"]) & np.isfinite(m.x_px)]
        m = m.sort_values(["e_ms", "key"])
        open_pos, rows = [], []
        for r in m.itertuples():
            open_pos = [(x, s) for x, s in open_pos if x > r.e_ms]
            free = capital - sum(s for _, s in open_pos)
            usd = max(0.0, min(r.target, free))
            if usd <= 0:
                continue
            open_pos.append((r.x_ms, usd))
            c_e = charge(getattr(r, f"{e}_hs_bp"), mult)
            c_x = charge(r.x_hs_bp, mult)
            net = (r.x_px * (1 - c_x) * (1 - ft_)) / (r.e_px * (1 + c_e) * (1 + ft_)) - 1
            rows.append(dict(key=r.key, pid=r.pid, base_ccy=r.base, T_lo=r.T_lo, T_ft=r.T_ft, entry_ms=r.e_ms,
                             x_ms=r.x_ms, usd=usd, target=r.target, e_px=r.e_px, x_px=r.x_px,
                             e_hs_bp=getattr(r, f"{e}_hs_bp"), x_hs_bp=r.x_hs_bp, x_fallback=bool(r.x_fallback),
                             gross=r.x_px / r.e_px - 1, net=net, pnl=usd * net))
        t = pd.DataFrame(rows)
    if len(t):
        t["exit"] = pd.to_datetime(t.x_ms.astype("int64"), unit="ms")
        t["exit_day"] = t.exit.dt.normalize()
    return t


def daily(t, capital, days=SCORED):
    if len(t) == 0:
        return pd.Series(0.0, index=pd.DatetimeIndex(days))
    s = t.groupby("exit_day").pnl.sum() / capital
    return s.reindex(pd.DatetimeIndex(days)).fillna(0.0)


def dev_days():
    return SCORED[SCORED < gates.HOLD0]


def scored(t):
    return t[t.exit_day.isin(SCORED)] if len(t) else t


# ------------------------------------------------------------------ AI (walk-forward by quarter)
FEATURES = ["lo_dur_min_dec", "log_lo_usd", "move_since_open", "btc4h", "n_week"]


def btc_close():
    parts = []
    for src in ("minute_early", "minute"):
        d = pd.read_parquet(os.path.join(common.DATA, src, "BTC.parquet"), columns=["ts", "close", "volume"])
        d = d[d.volume > 0]
        parts.append(pd.Series(d.close.to_numpy(), index=pd.DatetimeIndex(d.ts)))
    s = pd.concat(parts).sort_index()
    return s[~s.index.duplicated()]


def features(M, mode, delta, btc, allE):
    """Decision-time features. Mode I decides at T_lo + 60 min; Mode II at T_ft + delta - 2 s.
    Prints used are >= 1 s old (the runner's *_last_px / *_lo_usd lookups); BTC uses the 1-minute candle that closed
    at least one minute before the decision; n_week counts other universe events whose T_lo is in the 7 days up to
    the decision."""
    nm = "mI" if mode == 1 else f"e{delta}"
    dec = pd.to_datetime(M[f"{nm}_dec_ms"].astype("int64"), unit="ms")
    f = pd.DataFrame(index=M.index)
    f["lo_dur_min_dec"] = (M[f"{nm}_dec_ms"] - M.lo_ms) / MIN
    f["log_lo_usd"] = np.log10(M[f"{nm}_lo_usd"].clip(lower=1.0))
    if mode == 2:
        f.loc[M.split.astype(bool).to_numpy(), "log_lo_usd"] = np.nan
    f["move_since_open"] = np.log(M[f"{nm}_last_px"] / M.first_px)
    d1 = dec.dt.floor("min") - pd.Timedelta(minutes=2)
    c1 = btc.reindex(d1, method="ffill").to_numpy()
    c0 = btc.reindex(d1 - pd.Timedelta(hours=4), method="ffill").to_numpy()
    f["btc4h"] = np.log(c1 / c0)
    lo_all = np.sort(allE.T_lo.to_numpy())
    cnt = np.searchsorted(lo_all, dec.to_numpy(), "right") - np.searchsorted(lo_all, (dec - pd.Timedelta(days=7)).to_numpy(), "left")
    f["n_week"] = cnt - 1                                 # minus the event itself (its T_lo is before the decision)
    return f


def ai_take(M, S, mode, H, delta, theta, allE, end=None):
    """Walk-forward LightGBM regression of the per-event net return at 2x costs (cash cap off); keep a trade if the
    prediction is positive. Training uses every event (2024 included) whose exit is before the test quarter; the first
    quarter scored is the first with >= 30 earlier events and >= 6 months of history. end: events at/after `end` are
    never used (the DEV stage passes HOLD0)."""
    import lightgbm as lgb
    btc = btc_close()
    m = M if end is None else M[M.T_ft + pd.Timedelta(hours=3) < end]
    F = features(m, mode, delta, btc, allE)
    tr = trades(m, S, mode, H, 2.0, theta, delta, capital=1e12)
    y = tr.set_index("key").net.reindex(m.key).to_numpy()
    xt = tr.set_index("key").exit.reindex(m.key).to_numpy()
    y = pd.Series(y, index=m.index)
    exit_t = pd.Series(pd.to_datetime(xt), index=m.index)
    dec = pd.to_datetime(m[("mI" if mode == 1 else f"e{delta}") + "_dec_ms"].astype("int64"), unit="ms")
    q = dec.dt.to_period("Q")
    warm = dec.min() + pd.DateOffset(months=6)
    take = pd.Series(False, index=m.index)
    log = []
    for qq in sorted(q.unique()):
        q0 = qq.start_time
        if q0 < warm:
            continue
        trn = y.notna() & (exit_t < q0)
        tst = q == qq
        if trn.sum() < 30 or tst.sum() == 0:
            continue
        params = dict(n_estimators=200, learning_rate=0.03, num_leaves=4, min_child_samples=10, subsample=0.8,
                      subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=7, verbose=-1)
        mdl = lgb.LGBMRegressor(**params).fit(F[trn], y[trn])
        pr = mdl.predict(F[tst])
        take[tst] = pr > 0
        log.append(dict(quarter=str(qq), n_train=int(trn.sum()), n_test=int(tst.sum()), n_take=int((pr > 0).sum())))
    return take, pd.DataFrame(log)


# ------------------------------------------------------------------ helpers
def alpha70(s, days):
    ri = gates.incumbent(70e3, 0.5, "instant", days)
    return gates.alpha_test(pd.Series(s).reindex(days).fillna(0.0), ri)


def git_head():
    return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"], text=True).strip()


def nan2none(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def dumpj(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=lambda v: nan2none(float(v)) if isinstance(v, (np.floating, float))
                  else int(v) if isinstance(v, np.integer) else str(v))
