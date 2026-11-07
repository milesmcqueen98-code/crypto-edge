#!/usr/bin/env python3
"""H8 (depeg bids) ladder simulator and trial runner (reports/hunt/h8dp/SPEC.md, reports/hunt_prereg.md).

  python scripts/hunt/h8dp/sim.py episodes      DEV-only depeg episode table (descriptive)
  python scripts/hunt/h8dp/sim.py dev           the 8-trial DEV grid (sleeve $30K, 2x costs, theta 0.5); logs trials
  python scripts/hunt/h8dp/sim.py hold          after the freeze commit: the frozen variant over all scored days

Trade (fixed by the SPEC): resting bids at par x (1 - d) for each d of the ladder, cash split equally across rungs
(and across the pairs listed that day); exit by a post-only sell at par - 5 bp, or (exit 'tp7') a market sale 7 days
after the fill. Whole sleeve capital in the ladder; idle cash earns 0 (Coinbase holds it for the resting bids).

Fill rules (pre-registration):
- Entry (resting bid): size <= theta x through-volume, i.e. volume of prints at least one tick BELOW the bid
  (data/hunt/h8dp/tagg, every candidate window fetched from trade prints). Rungs share sellers: in a minute, the fills
  of all rungs at or above a level are capped by theta x the volume below that level (shallow rungs fill first).
  Minutes outside fetched windows fall back to candles: the minute opened at or above the bid, then traded at least
  one tick through it; volume spread evenly over the candle's range.
- Exit (resting ask at par - 5 bp, placed after the fill): size <= theta x volume of prints at least one tick ABOVE it
  (candles outside print windows: opened at or below the ask, then traded through it by a tick). FIFO across lots.
  Only lots filled in earlier minutes; cash freed by a sale re-arms the bid from the next active minute.
- Market sale (7-day timeout, delisting, end of data): the open of the first minute at or after the decision, worse
  by 1.5x the half-spread, plus the taker fee.
P&L is booked on the exit day (UTC), on the sleeve's capital; idle days are 0.
"""
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
sys.path.insert(0, HERE)
import gates  # noqa: E402
import levels as LV  # noqa: E402

TAGG = os.path.join(ROOT, "data", "hunt", "h8dp", "tagg")
OUT = os.path.join(ROOT, "reports", "hunt", "h8dp")
PRODUCTS = os.path.join(ROOT, "data", "hunt", "h8dp", "products.json")
HOLD0 = gates.HOLD0
END_ALL = pd.Timestamp("2026-11-06")            # exclusive: data through 2026-11-05 (gates.END)
DEV_END = pd.Timestamp("2026-05-31")            # inclusive last DEV day; dev runs read candles < HOLD0 only

LADDERS = {"shallow": (0.0010, 0.0025, 0.0050), "deep": (0.0050, 0.0100, 0.0200)}
EXITS = {"tp": None, "tp7": 7}
UNIVERSES = {"usdt": ("USDT-USD",), "all": LV.UNIVERSE_ALL}
MIN_ORDER_USD = 1.0
NS_MIN = 60_000_000_000


def spans():
    js = json.load(open(PRODUCTS))["spans"]
    return {k: (pd.Timestamp(v["first"]), pd.Timestamp(v["last"])) for k, v in js.items() if v}


# ------------------------------------------------------------------------------------------------ data per pair
_CACHE = {}


def prints_for(pid, end):
    parts = ["dev"] + (["hold"] if end > HOLD0 else [])
    agg, wins, full = [], [], False
    for part in parts:
        for f in sorted(glob.glob(os.path.join(TAGG, f"{pid}_*_{part}.parquet"))):
            name = os.path.basename(f)
            if "_win_" in name:
                wins.append(pd.read_parquet(f))
                continue
            full = full or "_full_" in name
            agg.append(pd.read_parquet(f))
    A = pd.concat(agg) if agg else pd.DataFrame(columns=["ts"])
    A = A[A.ts < end].drop_duplicates("ts").set_index("ts").sort_index()
    W = pd.concat(wins) if wins else pd.DataFrame(columns=["start", "end", "ids_missing"])
    W = W[W.start < end]
    return A, W, full


def build(pid, end):
    key = (pid, end)
    if key in _CACHE:
        return _CACHE[key]
    C = LV.load_candles(pid, end=end)
    L = LV.levels_for(pid, C, end=end)
    A, W, full = prints_for(pid, end)
    ts = C.index.values.astype("datetime64[ns]").astype(np.int64)
    n = len(ts)
    o, h, l, c, v = (C[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    tick = LV.TICK[pid]
    lev = L[list(LV.DEPTHS)].to_numpy(float)
    tp = L["tp"].to_numpy(float)
    # coverage by fetched print windows
    if full:
        cov = np.ones(n, bool)
    else:
        cov = np.zeros(n + 1, int)
        ok = W[W.ids_missing >= 0]
        s = np.searchsorted(ts, ok.start.values.astype("datetime64[ns]").astype(np.int64))
        e = np.searchsorted(ts, ok.end.values.astype("datetime64[ns]").astype(np.int64))
        np.add.at(cov, s, 1)
        np.add.at(cov, e, -1)
        cov = np.cumsum(cov)[:n] > 0
    rng = h - l
    E = np.zeros((n, len(LV.DEPTHS)))
    for j in range(len(LV.DEPTHS)):
        Lj = lev[:, j]
        okc = (o >= Lj - 0.5 * tick) & (l <= Lj - 0.5 * tick)
        frac = np.where(rng > 0, np.clip((Lj - l) / np.where(rng > 0, rng, 1), 0, 1), 1.0)
        E[:, j] = np.where(okc, v * frac, 0.0)
    # take-profit ask (placed after the fill): candle minutes whose high trades a tick above it, volume above the ask
    # spread evenly over the range (as the wick simulators' first_touch / above_usd; no open condition for exits)
    okx = h >= tp + 0.5 * tick
    fx = np.where(rng > 0, np.clip((h - tp) / np.where(rng > 0, rng, 1), 0, 1), 1.0)
    X = np.where(okx, v * fx, 0.0)
    n_cand_unc = int(((E[:, 0] > 0) & ~cov).sum())
    if len(A):
        Ai = A.reindex(C.index)
        vb = np.nan_to_num(Ai[[f"vb_{int(round(d * 1e4))}" for d in LV.DEPTHS]].to_numpy(float))
        va = np.nan_to_num(Ai["va_tp"].to_numpy(float))
        E = np.where(cov[:, None], vb, E)
        X = np.where(cov, va, X)
    E = np.nan_to_num(E)
    X = np.nan_to_num(X)
    P = dict(pid=pid, ts=ts, o=o, c=c, lev=lev, tp=tp, E=E, X=X, cov=cov, n_cand_uncovered=n_cand_unc,
             fees=LV.fees(pid), last_ts=int(ts[-1]) if n else None, n_print_minutes=int(len(A)))
    _CACHE[key] = P
    return P


# ------------------------------------------------------------------------------------------------ simulation
def sim_pair(P, depths, theta, timeout_days, mult, budget_at, delisted):
    """One pair's ladder. budget_at(ts_ns) -> USD budget per rung. Returns lot records (one per lot exit)."""
    ts, o, c, lev, tp, E, X = P["ts"], P["o"], P["c"], P["lev"], P["tp"], P["E"], P["X"]
    maker, taker, hs = P["fees"]
    cols = [LV.DEPTHS.index(d) for d in depths]
    k = len(cols)
    tmo = None if timeout_days is None else int(timeout_days * 1440 * NS_MIN)
    lots = []                                       # [slot, fill_i, qty, px, deadline_ns, episode]
    inv = [0.0] * k
    ep_id = [-1] * k
    n_ep = [0]
    rec = []
    act = np.nonzero((E[:, cols[0]] > 0) | (X > 0))[0]

    def close_lot(lot, q, px_net, i_exit, kind):
        cost = q * lot[3] * (1 + maker * mult)
        rec.append((P["pid"], lot[0], lot[5], ts[lot[1]], ts[i_exit], q, lot[3], px_net, q * px_net - cost, kind))
        return q * lot[3]

    def mkt(i):
        return o[i] * (1 - 1.5 * hs * mult) * (1 - taker * mult)

    for i in act:
        t = ts[i]
        freed = [0.0] * k
        if lots:
            # 1. timeouts: decision at the deadline, market sale at the first minute at or after it
            if tmo is not None:
                keep = []
                for lot in lots:
                    if lot[4] <= t:
                        ix = int(np.searchsorted(ts, lot[4]))
                        freed[lot[0]] += close_lot(lot, lot[2], mkt(ix), ix, "timeout")
                    else:
                        keep.append(lot)
                lots = keep
            # 2. take-profit: resting ask at tp, FIFO across this pair's lots filled in earlier minutes
            if X[i] > 0 and lots:
                avail = theta * X[i]
                px_net = tp[i] * (1 - maker * mult)
                keep = []
                for lot in lots:
                    if avail > 0 and lot[1] < i:
                        q = min(lot[2], avail)
                        avail -= q
                        freed[lot[0]] += close_lot(lot, q, px_net, i, "tp")
                        lot[2] -= q
                        if lot[2] * lot[3] < 1e-6:
                            continue
                    keep.append(lot)
                lots = keep
        # 3. entries: shallow rungs first; cumulative seller cap
        if E[i, cols[0]] > 0:
            b = budget_at(t)
            cum = 0.0
            for s, j in enumerate(cols):
                avail = theta * E[i, j] - cum
                if avail <= 0 or not np.isfinite(lev[i, j]):
                    continue
                rem = b - inv[s]
                if rem < MIN_ORDER_USD:
                    continue
                q = min(rem / lev[i, j], avail)
                if q * lev[i, j] < MIN_ORDER_USD:
                    continue
                if inv[s] <= 1e-9:
                    ep_id[s] = n_ep[0]
                    n_ep[0] += 1
                lots.append([s, i, q, lev[i, j], t + tmo if tmo is not None else np.iinfo(np.int64).max, ep_id[s]])
                inv[s] += q * lev[i, j]
                cum += q
        for s in range(k):
            inv[s] = max(0.0, inv[s] - freed[s])
    # timeouts that fall after the last active minute: market sale at the first minute at or after the deadline
    if lots and tmo is not None:
        keep = []
        for lot in lots:
            if lot[4] <= ts[-1]:
                ix = int(np.searchsorted(ts, lot[4]))
                close_lot(lot, lot[2], mkt(ix), ix, "timeout")
            else:
                keep.append(lot)
        lots = keep
    # end: delisted pairs and the end of the full run sell at the last close; a DEV run leaves open lots unbooked
    if lots and (delisted or P.get("final", False)):
        i = len(ts) - 1
        px = c[i] * (1 - 1.5 * hs * mult) * (1 - taker * mult)
        for lot in lots:
            close_lot(lot, lot[2], px, i, "delist" if delisted else "end")
        lots = []
    open_lots = [(P["pid"], lot[0], lot[5], ts[lot[1]], lot[2], lot[3]) for lot in lots]
    return rec, open_lots


def run(universe, ladder, exit_, theta=0.5, mult=2.0, capital=30e3, end=HOLD0):
    pids = UNIVERSES[universe]
    depths = LADDERS[ladder]
    sp = spans()
    days = pd.date_range("2020-01-01", END_ALL, freq="D")
    act = pd.DataFrame({p: (days >= sp[p][0]) & (days <= sp[p][1]) for p in pids}, index=days)
    n_act = act.sum(axis=1).clip(lower=1)
    per_rung = (capital / (n_act * len(depths))).to_numpy()
    d0 = days[0].value

    def budget_at(t):
        return per_rung[(t - d0) // (1440 * NS_MIN)]

    recs, opens, info = [], [], {}
    for p in pids:
        P = build(p, end)
        if not len(P["ts"]):
            continue
        P["final"] = end >= END_ALL
        delisted = sp[p][1] < (end - pd.Timedelta(days=1)).normalize()
        r, ol = sim_pair(P, depths, theta, EXITS[exit_], mult, budget_at, delisted)
        recs += r
        opens += ol
        info[p] = dict(n_print_minutes=P["n_print_minutes"], cand_minutes_without_prints=P["n_cand_uncovered"])
    R = pd.DataFrame(recs, columns=["pid", "slot", "episode", "t_fill", "t_exit", "qty", "px_in", "px_out_net", "pnl",
                                    "kind"])
    for col in ("t_fill", "t_exit"):
        R[col] = pd.to_datetime(R[col])
    daily = R.groupby(R.t_exit.dt.floor("D")).pnl.sum() / capital if len(R) else pd.Series(dtype=float)
    return R, daily, opens, info


def scored(daily, end=HOLD0):
    days = gates.ERA_DAYS[gates.ERA_DAYS < end]
    s = pd.Series(daily, dtype=float).reindex(days).fillna(0.0)
    return s


def n_fills(R):
    """Fills = distinct (pair, rung, episode): a rung bought in one dip and sold back (the round trips)."""
    return int(R.groupby(["pid", "slot", "episode"]).ngroups) if len(R) else 0


# ------------------------------------------------------------------------------------------------ modes
def mode_dev():
    gates_inc70 = None
    rows = []
    t0 = time.time()
    for universe in ("usdt", "all"):
        for ladder in ("shallow", "deep"):
            for exit_ in ("tp", "tp7"):
                var = f"{universe}|{ladder}|{exit_}"
                R, daily, opens, info = run(universe, ladder, exit_, theta=0.5, mult=2.0, capital=30e3, end=HOLD0)
                s30 = scored(daily)
                gates.assert_dev_only(s30)
                if gates_inc70 is None:
                    gates_inc70 = gates.incumbent(70e3, days=s30.index)
                at = gates.alpha_test(s30, gates_inc70)
                scr = gates.dev_screen(s30)
                bk = gates.dev_book(s30)
                Rs = R[R.t_exit.dt.floor("D").isin(s30.index)]
                row = dict(variant=var, universe=universe, ladder=ladder, exit=exit_, fills_all=n_fills(R),
                           fills_scored=n_fills(Rs), lots=len(R), pnl_usd_scored=float(Rs.pnl.sum()),
                           sleeve_sharpe=scr["sleeve_sharpe"], t_alpha_inc70=at["t_alpha"],
                           t_alpha_inc100=scr["t_alpha"], alpha_yr=at["alpha_yr"], corr=scr["corr"],
                           active_days=scr["active_days"], dev_book_sharpe=gates.sharpe(bk),
                           open_lots_at_dev_end=len(opens), sleeve_ret_total=float(s30.sum()))
                rows.append(row)
                gates.log_trial("h8dp", var, bk, note="DEV grid (SPEC): book a=0.7, sleeve $30K at 2x costs, theta 0.5",
                                sleeve_sharpe=row["sleeve_sharpe"], t_alpha_inc70=row["t_alpha_inc70"],
                                fills=row["fills_scored"])
                print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    T = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    T.to_csv(os.path.join(OUT, "dev_trials.csv"), index=False)
    print(f"done in {time.time() - t0:.0f}s")


def episodes(end=HOLD0, pids=LV.UNIVERSE_ALL + ("UST-USD", "BUSD-USD"), thr=0.005, gap_h=24):
    """Depeg episodes from candles: minutes whose low is >= thr below par, merged when < gap_h apart.
    depth = worst low vs par; minutes_below = minutes with a low below thr; recovery = first close >= par - 5 bp after
    the last minute below thr (hours from the episode start)."""
    rows = []
    for p in pids:
        C = LV.load_candles(p, end=end)
        if p == "CBETH-USD":
            par = LV.cbeth_par(C, LV.load_eth(end))
        else:
            par = pd.Series(1.0, index=C.index)
        rel_low = (C["low"] / par).to_numpy()
        rel_close = (C["close"] / par).to_numpy()
        usd = (C["volume"] * C["close"]).to_numpy()
        idx = np.nonzero(rel_low <= 1 - thr)[0]
        if not len(idx):
            continue
        t = C.index[idx]
        brk = np.r_[0, np.nonzero(np.diff(t.values).astype("timedelta64[m]").astype(int) > gap_h * 60)[0] + 1, len(idx)]
        for a, b in zip(brk[:-1], brk[1:]):
            ii = idx[a:b]
            i_last = ii[-1]
            rec = np.nonzero(rel_close[i_last:] >= 1 - LV.TP_BP * 1e-4)[0]
            t_rec = C.index[i_last + rec[0]] if len(rec) else pd.NaT
            j = ii[np.argmin(rel_low[ii])]
            rows.append(dict(pid=p, start=C.index[ii[0]], end=C.index[i_last], worst_at=C.index[j],
                             depth_bp=round((1 - rel_low[j]) * 1e4, 1), minutes_below=len(ii),
                             below_100bp=int((rel_low[ii] <= 0.99).sum()), below_200bp=int((rel_low[ii] <= 0.98).sum()),
                             usd_vol_below=round(float(usd[ii].sum())),
                             hours_to_recover=round((t_rec - C.index[ii[0]]).total_seconds() / 3600, 1)
                             if pd.notna(t_rec) else None))
    return pd.DataFrame(rows)


def mode_episodes():
    E = episodes()
    os.makedirs(OUT, exist_ok=True)
    E.to_csv(os.path.join(OUT, "episodes_dev.csv"), index=False)
    pd.set_option("display.width", 250)
    print(E.to_string())


def mode_mech():
    """Mechanics check on UST-USD (not in any variant's universe): accounting identities only."""
    P = build("UST-USD", HOLD0)
    P["final"] = True
    R, ol = sim_pair(P, LADDERS["deep"], 0.5, 7, 2.0, lambda t: 10e3, True)
    R = pd.DataFrame(R, columns=["pid", "slot", "episode", "t_fill", "t_exit", "qty", "px_in", "px_out_net", "pnl", "kind"])
    print(R.groupby("kind").size().to_dict(), "open", len(ol), "max cost per slot",
          R.assign(c=R.qty * R.px_in).groupby(["slot", "episode"]).c.sum().max().round(2))
    print((R.t_exit >= R.t_fill).all())


def frozen_variant():
    return json.load(open(os.path.join(OUT, "frozen.json")))


def mode_hold():
    """After the freeze commit: the frozen variant over every scored day (HOLD read once)."""
    F = frozen_variant()
    u, ld, ex = F["universe"], F["ladder"], F["exit"]
    series, trades, info_all = {}, {}, {}
    for theta in (0.5, 0.25):
        for mult in (2.0, 1.0):
            for cap in (30e3, 50e3):
                _CACHE.clear() if False else None
                R, daily, opens, info = run(u, ld, ex, theta=theta, mult=mult, capital=cap, end=END_ALL)
                key = f"s{int(cap / 1e3)}_{int(mult)}x" + ("" if theta == 0.5 else "_th025")
                series[key] = pd.Series(daily, dtype=float).reindex(gates.ERA_DAYS).fillna(0.0)
                trades[key] = R
                info_all[key] = dict(open_lots_at_end=len(opens), **{k: v for k, v in info.items()})
    D = pd.DataFrame(series)
    D.index.name = "day"
    D[["s30_2x", "s50_2x", "s30_1x", "s50_1x"]].to_parquet(os.path.join(OUT, "daily.parquet"))
    D.to_parquet(os.path.join(OUT, "daily_all_variants.parquet"))
    G = gates.path_b({30000: D["s30_2x"], 50000: D["s50_2x"]}, days=gates.ERA_DAYS)
    G1x = gates.path_b({30000: D["s30_1x"], 50000: D["s50_1x"]}, days=gates.ERA_DAYS)
    G025 = gates.path_b({30000: D["s30_2x_th025"], 50000: D["s50_2x_th025"]}, days=gates.ERA_DAYS)
    R = trades["s30_2x"]
    R.to_csv(os.path.join(OUT, "lots_s30_2x.csv"), index=False)
    out = dict(frozen=F, path_b_2x=G, path_b_1x_info=G1x, path_b_2x_theta025_info=G025,
               fills_rung_episodes=n_fills(R), lots=len(R), info=info_all,
               note="G4 is provisional: the coordinator recomputes the deflated Sharpe centrally with the final ledger.")
    with open(os.path.join(OUT, "gates.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: G[k] for k in G if k != "a_grid"}, default=str, indent=0))


if __name__ == "__main__":
    {"dev": mode_dev, "episodes": mode_episodes, "mech": mode_mech, "hold": mode_hold}[sys.argv[1]]()
