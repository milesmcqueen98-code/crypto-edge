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
  (data/hunt/h8dp/tagg, every candidate window fetched from trade prints). Rungs share sellers as in
  scripts/wick1m/sim.py: each rung <= theta x its own through-volume, and all rungs together <= theta x the
  through-volume of the shallowest rung in that minute (shallow rungs fill first).
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
    """Per-minute arrays for one pair (memory-lean: constant levels for the stablecoins are broadcast views, volumes
    in float32). E[i, j]: coin volume available to fill the bid at depth DEPTHS[j] in minute i; X[i]: coin volume
    available to the take-profit ask; prints where fetched, candles elsewhere."""
    key = (pid, end)
    if key in _CACHE:
        return _CACHE[key]
    C = LV.load_candles(pid, end=end)
    L = LV.levels_for(pid, C, end=end)
    A, W, full = prints_for(pid, end)
    ts = C.index.values.astype("datetime64[ns]").astype(np.int64)
    n = len(ts)
    o, h, l = (C[k].to_numpy(float) for k in ("open", "high", "low"))
    v = C["volume"].to_numpy(np.float32)
    last_close = float(C["close"].iloc[-1]) if n else np.nan
    del C
    tick = LV.TICK[pid]
    if pid in LV.STABLES or pid in ("UST-USD", "BUSD-USD"):
        lev = np.broadcast_to(L[list(LV.DEPTHS)].iloc[0].to_numpy(float), (n, len(LV.DEPTHS)))
        tp = np.broadcast_to(np.float64(L["tp"].iloc[0]), (n,))
    else:
        lev = L[list(LV.DEPTHS)].to_numpy(float)
        tp = L["tp"].to_numpy(float)
    del L
    if full:
        cov = np.ones(n, bool)
    else:
        cnt = np.zeros(n + 1, np.int32)
        ok = W[W.ids_missing >= 0]
        s_ = np.searchsorted(ts, ok.start.values.astype("datetime64[ns]").astype(np.int64))
        e_ = np.searchsorted(ts, ok.end.values.astype("datetime64[ns]").astype(np.int64))
        np.add.at(cnt, s_, 1)
        np.add.at(cnt, e_, -1)
        cov = np.cumsum(cnt)[:n] > 0
    rng = h - l
    safe = np.where(rng > 0, rng, 1.0)
    E = np.zeros((n, len(LV.DEPTHS)), np.float32)
    for j in range(len(LV.DEPTHS)):
        Lj = lev[:, j]
        okc = (o >= Lj - 0.5 * tick) & (l <= Lj - 0.5 * tick)
        frac = np.where(rng > 0, np.clip((Lj - l) / safe, 0, 1), 1.0)
        E[:, j] = np.where(okc & ~cov, v * frac, 0.0)
    okx = (h >= tp + 0.5 * tick) & ~cov
    X = np.where(okx, v * np.where(rng > 0, np.clip((h - tp) / safe, 0, 1), 1.0), 0.0).astype(np.float32)
    n_cand_unc = int(((l <= lev[:, 0] - 0.5 * tick) & ~cov).sum())
    del h, l, v, rng, safe
    if len(A):
        at = A.index.values.astype("datetime64[ns]").astype(np.int64)
        pos = np.searchsorted(ts, at)
        okp = (pos < n)
        okp[okp] = ts[pos[okp]] == at[okp]
        okp[okp] = cov[pos[okp]]
        pos = pos[okp]
        E[pos, :] = np.nan_to_num(A[[f"vb_{int(round(d * 1e4))}" for d in LV.DEPTHS]].to_numpy(float))[okp]
        X[pos] = np.nan_to_num(A["va_tp"].to_numpy(float))[okp]
    P = dict(pid=pid, ts=ts, o=o, lev=lev, tp=tp, E=E, X=X, cov_frac=float(cov.mean()) if n else 0.0,
             n_cand_uncovered=n_cand_unc, fees=LV.fees(pid), last_close=last_close, n_print_minutes=int(len(A)))
    _CACHE[key] = P
    return P


# ------------------------------------------------------------------------------------------------ simulation
REC_COLS = ["pid", "slot", "episode", "t_fill", "t_exit", "qty", "px_in", "px_out_net", "pnl", "kind"]


def simulate(Ps, depths, theta, timeout_days, mult, per_rung_at, capital):
    """All pairs jointly, in time order, sharing one cash pool (never more than `capital` committed).
    Ps: list of build() dicts with flags 'delisted' (liquidate at the pair's last minute) and 'final' (liquidate
    at the end of the data). per_rung_at(t_ns) -> USD budget per rung per pair that day.
    Returns (records, open lots at the end, deployment stats)."""
    cols = [LV.DEPTHS.index(d) for d in depths]
    k = len(cols)
    tmo = None if timeout_days is None else int(timeout_days * 1440 * NS_MIN)
    big = np.iinfo(np.int64).max
    T, PI, II = [], [], []
    for pi, P in enumerate(Ps):
        idx = np.nonzero((P["E"][:, cols[0]] > 0) | (P["X"] > 0))[0]
        if P["delisted"] and len(P["ts"]) and (not len(idx) or idx[-1] != len(P["ts"]) - 1):
            idx = np.r_[idx, len(P["ts"]) - 1]
        T.append(P["ts"][idx])
        PI.append(np.full(len(idx), pi, np.int16))
        II.append(idx)
    T, PI, II = np.concatenate(T), np.concatenate(PI), np.concatenate(II)
    order = np.argsort(T, kind="stable")
    lots = [[] for _ in Ps]                     # [slot, fill_i, qty, px, deadline_ns, episode]
    inv = [[0.0] * k for _ in Ps]               # cost of open lots per rung
    ep_id = [[-1] * k for _ in Ps]
    n_ep = [0]
    used = [0.0]                                # cash committed across all pairs
    rec = []
    dep = dict(usd_minutes=0.0, last_t=None)

    def close_lot(pi, lot, q, px_net, i_exit, kind):
        P = Ps[pi]
        maker = P["fees"][0]
        cost = q * lot[3]
        rec.append((P["pid"], lot[0], lot[5], P["ts"][lot[1]], P["ts"][i_exit], q, lot[3], px_net,
                    q * px_net - cost * (1 + maker * mult), kind))
        return cost

    def mkt_px(P, i):
        _, taker, hs = P["fees"]
        return P["o"][i] * (1 - 1.5 * hs * mult) * (1 - taker * mult)

    def liquidate(pi, i_px, kind, close=False):
        P = Ps[pi]
        _, taker, hs = P["fees"]
        px = (P["last_close"] if close else P["o"][i_px]) * (1 - 1.5 * hs * mult) * (1 - taker * mult)
        freed = [0.0] * k
        for lot in lots[pi]:
            freed[lot[0]] += close_lot(pi, lot, lot[2], px, i_px, kind)
        lots[pi] = []
        return freed

    E0 = [P["E"][:, cols[0]] for P in Ps]
    for j in order:
        pi, i = int(PI[j]), int(II[j])
        P = Ps[pi]
        if not lots[pi] and E0[pi][i] <= 0 and not (P["delisted"] and i == len(P["ts"]) - 1):
            continue
        t = int(P["ts"][i])
        if dep["last_t"] is not None:
            dep["usd_minutes"] += used[0] * (t - dep["last_t"]) / NS_MIN
        dep["last_t"] = t
        freed = [0.0] * k
        L = lots[pi]
        if L:
            if tmo is not None and any(lot[4] <= t for lot in L):
                keep = []
                for lot in L:
                    if lot[4] <= t:
                        ix = int(np.searchsorted(P["ts"], lot[4]))
                        freed[lot[0]] += close_lot(pi, lot, lot[2], mkt_px(P, ix), ix, "timeout")
                    else:
                        keep.append(lot)
                L = keep
            if P["X"][i] > 0 and L:
                avail = theta * float(P["X"][i])
                px_net = float(P["tp"][i]) * (1 - P["fees"][0] * mult)
                keep = []
                for lot in L:
                    if avail > 0 and lot[1] < i:
                        q = min(lot[2], avail)
                        avail -= q
                        freed[lot[0]] += close_lot(pi, lot, q, px_net, i, "tp")
                        lot[2] -= q
                        if lot[2] * lot[3] < 1e-6:
                            continue
                    keep.append(lot)
                L = keep
            lots[pi] = L
        if E0[pi][i] > 0:
            b = per_rung_at(t)
            cum = 0.0
            pool = theta * float(E0[pi][i])          # sellers through the shallowest rung, shared by all rungs
            for s_, j_ in enumerate(cols):          # (house rule, scripts/wick1m/sim.py: own cap and shared pool)
                avail = min(theta * float(P["E"][i, j_]), pool - cum)
                lvl = float(P["lev"][i, j_])
                if avail <= 0 or not np.isfinite(lvl):
                    continue
                rem = min(b - inv[pi][s_], capital - used[0])
                if rem < MIN_ORDER_USD:
                    continue
                q = min(rem / lvl, avail)
                if q * lvl < MIN_ORDER_USD:
                    continue
                if inv[pi][s_] <= 1e-9:
                    ep_id[pi][s_] = n_ep[0]
                    n_ep[0] += 1
                lots[pi].append([s_, i, q, lvl, t + tmo if tmo is not None else big, ep_id[pi][s_]])
                inv[pi][s_] += q * lvl
                used[0] += q * lvl
                cum += q
        if P["delisted"] and i == len(P["ts"]) - 1 and lots[pi]:
            f2 = liquidate(pi, i, "delist", close=True)
            freed = [a_ + b_ for a_, b_ in zip(freed, f2)]
        for s_ in range(k):
            inv[pi][s_] = max(0.0, inv[pi][s_] - freed[s_])
        used[0] = max(0.0, used[0] - sum(freed))
    # after the last event: timeouts that fall inside each pair's data, then the end of a full run
    for pi, P in enumerate(Ps):
        if lots[pi] and tmo is not None:
            keep = []
            for lot in lots[pi]:
                if lot[4] <= P["ts"][-1]:
                    ix = int(np.searchsorted(P["ts"], lot[4]))
                    close_lot(pi, lot, lot[2], mkt_px(P, ix), ix, "timeout")
                else:
                    keep.append(lot)
            lots[pi] = keep
        if lots[pi] and P["final"]:
            liquidate(pi, len(P["ts"]) - 1, "end", close=True)
    opens = [(Ps[pi]["pid"], lot[0], lot[5], Ps[pi]["ts"][lot[1]], lot[2], lot[3]) for pi in range(len(Ps))
             for lot in lots[pi]]
    return rec, opens, dep


def run(universe, ladder, exit_, theta=0.5, mult=2.0, capital=30e3, end=HOLD0):
    pids = UNIVERSES[universe]
    depths = LADDERS[ladder]
    sp = spans()
    days = pd.date_range("2020-01-01", END_ALL, freq="D")
    act = pd.DataFrame({p: (days >= sp[p][0]) & (days <= sp[p][1]) for p in pids}, index=days)
    n_act = act.sum(axis=1).clip(lower=1)
    per_rung = (capital / (n_act * len(depths))).to_numpy()
    d0 = days[0].value

    def per_rung_at(t):
        return per_rung[(t - d0) // (1440 * NS_MIN)]

    Ps, info = [], {}
    for p in pids:
        P = build(p, end)
        if not len(P["ts"]):
            continue
        P["final"] = end >= END_ALL
        P["delisted"] = sp[p][1] < (end - pd.Timedelta(days=1)).normalize()
        Ps.append(P)
        info[p] = dict(n_print_minutes=P["n_print_minutes"], cand_minutes_without_prints=P["n_cand_uncovered"],
                       print_coverage_of_minutes=round(P["cov_frac"], 4))
    rec, opens, dep = simulate(Ps, depths, 0.5 if theta is None else theta, EXITS[exit_], mult, per_rung_at, capital)
    R = pd.DataFrame(rec, columns=REC_COLS)
    for col in ("t_fill", "t_exit"):
        R[col] = pd.to_datetime(R[col])
    daily = R.groupby(R.t_exit.dt.floor("D")).pnl.sum() / capital if len(R) else pd.Series(dtype=float)
    info["avg_deployed_frac"] = dep["usd_minutes"] / capital / max(1.0, (dep["last_t"] or 0) / NS_MIN -
                                                                    pd.Timestamp("2021-01-01").value / NS_MIN)
    return R, daily, opens, info


def scored(daily, end=HOLD0):
    days = gates.ERA_DAYS[gates.ERA_DAYS < end]
    s = pd.Series(daily, dtype=float).reindex(days).fillna(0.0)
    return s


def n_fills(R):
    """Fills = distinct (pair, rung, episode): a rung bought in one dip and sold back (the round trips)."""
    return int(R.groupby(["pid", "slot", "episode"]).ngroups) if len(R) else 0


# ------------------------------------------------------------------------------------------------ modes
def mode_dev(universes=("usdt", "all")):
    """The SPEC's DEV grid. Each configuration is scored once and logged once (gates.log_trial)."""
    inc70 = None
    t0 = time.time()
    path = os.path.join(OUT, "dev_trials.csv")
    for universe in universes:
        for ladder in ("shallow", "deep"):
            for exit_ in ("tp", "tp7"):
                var = f"{universe}|{ladder}|{exit_}"
                R, daily, opens, info = run(universe, ladder, exit_, theta=0.5, mult=2.0, capital=30e3, end=HOLD0)
                s30 = scored(daily)
                gates.assert_dev_only(s30)
                if inc70 is None:
                    inc70 = gates.incumbent(70e3, days=s30.index)
                at = gates.alpha_test(s30, inc70)
                scr = gates.dev_screen(s30)
                bk = gates.dev_book(s30)
                Rs = R[R.t_exit.dt.floor("D").isin(s30.index)]
                row = dict(variant=var, universe=universe, ladder=ladder, exit=exit_, fills_scored=n_fills(Rs),
                           fills_all=n_fills(R), lots_scored=len(Rs), pnl_usd_scored=float(Rs.pnl.sum()),
                           sleeve_sharpe=scr["sleeve_sharpe"], t_alpha=at["t_alpha"], t_alpha_inc100=scr["t_alpha"],
                           alpha_yr=at["alpha_yr"], beta=at["beta"], corr=scr["corr"], active_days=scr["active_days"],
                           dev_book_sharpe=gates.sharpe(bk), sleeve_ret_per_yr=float(s30.mean() * 365),
                           open_lots_at_dev_end=len(opens), avg_deployed=info.get("avg_deployed_frac"),
                           by_pair_pnl=json.dumps(Rs.groupby("pid").pnl.sum().round(0).to_dict()),
                           by_kind=json.dumps(Rs.groupby("kind").size().to_dict()))
                gates.log_trial("h8dp", var, bk, note="DEV grid (SPEC): book a=0.7, sleeve $30K at 2x costs, theta 0.5",
                                sleeve_sharpe=row["sleeve_sharpe"], t_alpha=row["t_alpha"], fills=row["fills_scored"])
                pd.DataFrame([row]).to_csv(path, mode="a", header=not os.path.exists(path), index=False)
                Rs.to_csv(os.path.join(OUT, f"dev_lots_{universe}_{ladder}_{exit_}.csv"), index=False)
                print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
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
    P["final"], P["delisted"] = True, True
    rec, ol, dep = simulate([P], LADDERS["deep"], 0.5, 7, 2.0, lambda t: 10e3, 30e3)
    R = pd.DataFrame(rec, columns=REC_COLS)
    print(R.groupby("kind").size().to_dict(), "open", len(ol), "max cost per slot-episode",
          R.assign(c=R.qty * R.px_in).groupby(["slot", "episode"]).c.sum().max().round(2), "exit>=fill",
          bool((R.t_exit >= R.t_fill).all()))


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
    if sys.argv[1] == "dev":
        mode_dev(tuple(sys.argv[2:]) or ("usdt", "all"))
    else:
        {"episodes": mode_episodes, "mech": mode_mech, "hold": mode_hold}[sys.argv[1]]()
