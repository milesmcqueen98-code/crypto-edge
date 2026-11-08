#!/usr/bin/env python3
"""Ladder v6 (sizing): size multipliers on the frozen simulator (scripts/ladder_v6x/lsim.py, unchanged).

Hook = rt_live.era_arrays' mult_fn semantics (ladder v5 C2a): the 4-sigma bid of an approved coin is sized each minute
by that minute's multiplier m(t, coin); at a parent fill the parent takes that minute's bid and the 6/8-sigma rungs
take m at the fill minute. The era's base arrays are built once and their wants scaled (identical to mult_fn for
m > 0). Everything else (fill capacity, cash rule, take-profit capacity, print-measured exit costs) is the frozen
simulator's. Pre-registration: reports/ladder_v6s_prereg.md.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
import lsim  # noqa: E402
from lsim import CONFIGS, RL, fsim  # noqa: E402

lsim.ensure_frozen()          # the frozen pickles (SHA256-checked) must be in place before anything loads the trade list
OUT = os.path.join(ROOT, "reports", "ladder_v6s")
KAPPA_ADV, NOTIONAL = 0.002, 0.25
_A, _X = {}, {}


# ------------------------------------------------------------------------------------------------ arrays
def base(cfg, era):
    """The era's replay arrays with every multiplier at 1 (cached)."""
    key = (cfg, era)
    if key not in _A:
        lsim.ensure_frozen()
        kw = CONFIGS[cfg]
        _A[key] = RL.era_arrays(fsim.ERAS[era][0], era, kw["theta"], kw["C"], kw["today"])
    return _A[key]


def with_mult(A, mfac):
    """Arrays with the wants scaled by mfac (T x NC, all > 0): what era_arrays(mult_fn=...) builds."""
    assert mfac.shape == A["want4"].shape and np.all(mfac > 0)
    A2 = dict(A)
    A2["mfac"] = mfac
    A2["want4"] = A["want4"] * mfac
    pm = mfac[A["p_t"], A["p_c"]] if A["NP"] else np.ones(0)
    A2["p_mult"] = pm
    A2["p_want"] = A["p_wbase"] * pm
    return A2


def daily(cfg, era, mfac=None, A=None):
    """Blended daily P&L / C (1-second blend of the two latency bounds, print-measured exit costs)."""
    kw = CONFIGS[cfg]
    A = A if A is not None else base(cfg, era)
    A2 = A if mfac is None else with_mult(A, mfac)
    d = {}
    for bound in ("minute", "instant"):
        R = RL.replay(A2, theta=kw["theta"], C=kw["C"], bound=bound, policy="engine")
        _, Qo, info = RL.evaluate_live(A2, R, kw["theta"], kw["C"], era, kw["cost_mult"])
        d[bound] = lsim.rem_daily(Qo, info, cfg, era, kw["C"], "print")[0]
    return lsim.blend(era, kw["theta"], d["minute"], d["instant"])


# ------------------------------------------------------------------------------------------------ inputs
def vol_d_table(tag, coins):
    """Daily vol as of the previous day per coin (sim.daily_stats' vol_d)."""
    src = {"main": "minute", "early": "minute_early"}[tag]
    out = {}
    for c in coins:
        m = pd.read_parquet(os.path.join(ROOT, "data", src, f"{c}.parquet"), columns=["ts", "close", "volume"])
        m = m[m.volume > 0].drop_duplicates("ts").set_index("ts").sort_index()
        idx = pd.date_range(m.index.min().floor("D"), m.index.max().ceil("D"), freq="min", inclusive="left")
        cf = m.close.reindex(idx).ffill(limit=30)
        px = cf.resample("D").last()
        out[c] = np.log(px).diff().rolling(30, min_periods=10).std().shift(1)
    return pd.DataFrame(out)


def inputs(cfg, era):
    """Per-minute inputs on the era's replay grid: mu (prediction), sig (daily vol), breadth, room (ADV cap)."""
    key = (cfg, era)
    if key in _X:
        return _X[key]
    kw = CONFIGS[cfg]
    tag = fsim.ERAS[era][0]
    A = base(cfg, era)
    I = RL.inputs(tag)
    idx, coins = A["idx"], A["coins"]
    T, NC = A["T"], A["NC"]
    days = idx.floor("D")
    du = pd.DatetimeIndex(days.unique())
    di = du.get_indexer(days)
    # sigma-hat: daily vol as of the previous day
    vt = vol_d_table(tag, coins).reindex(du)
    sig = vt[coins].to_numpy()[di]
    # room under the 0.2% ADV cap (era_arrays' S_day)
    adv = I["adv"].reindex(du)[coins].to_numpy()
    fac = np.array([A["scale"].get(c, 1.0) for c in coins])
    cap_adv = KAPPA_ADV * adv * fac[None, :]
    s_day = np.minimum(NOTIONAL * kw["C"], cap_adv)
    room = np.where(s_day > 0, cap_adv / np.where(s_day > 0, s_day, 1.0), 1.0)[di]
    room = np.where(np.isfinite(room), np.maximum(room, 1.0), 1.0)
    # breadth: distinct coins with a research parent fill in minutes t-29..t
    P = I["P"]
    par = P[(P.k == 4.0) & P.filled]
    allc = sorted(par.coin.unique())
    pos = idx.get_indexer(par.ts)
    pres = np.zeros((T, len(allc)), np.int32)
    for j, c in enumerate(allc):
        p = pos[(par.coin == c).to_numpy() & (pos >= 0)]
        pres[p, j] = 1
    cs = np.cumsum(pres, axis=0)
    lag = np.vstack([np.zeros((30, len(allc)), cs.dtype), cs[:-30]])
    breadth = ((cs - lag) > 0).sum(axis=1).astype(np.float64)
    # research parents (for the trailing normalisation): time, coin column, minute index on this grid
    ppos = pos
    pcol = par.coin.map({c: j for j, c in enumerate(coins)}).to_numpy()
    # parents outside this grid (earlier days) still count for trailing medians: compute their inputs directly
    pM = np.full(len(par), np.nan)
    pidx = I["pidx"]
    ip = pidx.get_indexer(par.ts)
    ok = ip >= 0
    Mfull = I["M"]
    cj = {c: j for j, c in enumerate(I["coins"])}
    pM[ok] = Mfull[ip[ok], par.coin.map(cj).to_numpy()[ok]]
    vfull = vol_d_table(tag, allc)
    pday = par.ts.dt.floor("D")
    pS = np.array([vfull.at[d, c] if d in vfull.index else np.nan for d, c in zip(pday, par.coin)])
    # breadth at each parent's minute (on a grid covering all parents)
    tmin = par.ts.min().floor("D")
    gpos = ((par.ts - tmin) // pd.Timedelta(minutes=1)).to_numpy()
    G = int(gpos.max()) + 1
    gp = np.zeros((G, len(allc)), np.int32)
    for j, c in enumerate(allc):
        gp[gpos[(par.coin == c).to_numpy()], j] = 1
    gcs = np.cumsum(gp, axis=0)
    glag = np.vstack([np.zeros((30, len(allc)), gcs.dtype), gcs[:-30]])
    gbr = ((gcs - glag) > 0).sum(axis=1)
    pB = gbr[gpos].astype(np.float64)
    X = dict(idx=idx, days=days, du=du, di=di, coins=coins, M=A["M"].astype(np.float64), sig=sig, room=room,
             breadth=breadth, par_ts=par.ts.to_numpy(), par_coin=par.coin.to_numpy(), par_M=pM, par_sig=pS,
             par_breadth=pB, par_pos=ppos, par_col=pcol)
    _X[key] = X
    return X


# ------------------------------------------------------------------------------------------------ rules
def f_of(family, M, sig, breadth):
    if family == "kelly":
        return M / sig ** 2
    if family == "invvar":
        return 1.0 / sig ** 2
    if family == "edge":
        return M
    if family == "breadth":
        return 1.0 / np.sqrt(np.maximum(breadth, 1.0))
    raise KeyError(family)


def fbar_daily(X, family, window_days=90, min_n=30):
    """Per day of the grid: median f over research parents of the trailing window (before the day); NaN if < min_n."""
    fp = f_of(family, X["par_M"], X["par_sig"], X["par_breadth"])
    ts = pd.to_datetime(X["par_ts"])
    ok = np.isfinite(fp) & (fp > 0)
    s = pd.Series(fp[ok], index=ts[ok]).sort_index()
    out = np.full(len(X["du"]), np.nan)
    tv = s.index.to_numpy()
    vals = s.to_numpy()
    for i, d in enumerate(X["du"]):
        lo = np.searchsorted(tv, (d - pd.Timedelta(days=window_days)).to_datetime64(), "left")
        hi = np.searchsorted(tv, d.to_datetime64(), "left")
        if hi - lo >= min_n:
            out[i] = np.median(vals[lo:hi])
    return out


def rule_mult(X, family, lam, lo=0.5, hi=2.0, capped=True, window_days=90, min_n=30):
    """m(t, coin) = clip((f / fbar)^lam, lo, hi), 1 where undefined; ADV-capped if `capped`."""
    br = np.repeat(X["breadth"][:, None], X["M"].shape[1], axis=1)
    f = f_of(family, X["M"], X["sig"], br)
    fb = fbar_daily(X, family, window_days, min_n)[X["di"]][:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        m = np.clip((f / fb) ** lam, lo, hi)
    m = np.where(np.isfinite(m) & (f > 0), m, 1.0)
    if capped:
        m = np.minimum(m, X["room"])
    return m


# ------------------------------------------------------------------------------------------------ statistics
def nw(d):
    return float(fsim.nw_t(np.asarray(d, float)))


def score(inc, cand, cfg, era, k=5):
    """Return and Sharpe paths, plus the same with the k best difference days removed."""
    C = CONFIGS[cfg]["C"]
    cand = cand.reindex(inc.index, fill_value=0.0)
    si, sc = fsim.stats(inc, C, era), fsim.stats(cand, C, era)
    d = cand - inc
    vm = cand * (inc.std() / cand.std()) - inc if cand.std() > 0 else d * np.nan
    out = dict(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"], ret=sc["ret_yr"], sharpe=sc["sharpe"],
               d_ret=sc["ret_yr"] - si["ret_yr"], d_sharpe=sc["sharpe"] - si["sharpe"],
               mean_bp=1e4 * float(d.mean()), t=nw(d), mean_vm_bp=1e4 * float(vm.mean()), t_vm=nw(vm))
    for name, x in (("", d), ("_vm", vm)):
        keep = x.drop(x.nlargest(k).index)
        out[f"t{name}_ex{k}"] = nw(keep)
        out[f"mean{name}_ex{k}_bp"] = 1e4 * float(keep.mean())
        tot = float(x.sum())
        out[f"top{k}{name}_share"] = float(x.nlargest(k).sum() / tot) if tot > 0 else np.nan
    return out


def parity(cfgs=("S_0.5",), eras=("sel",)):
    lines = []
    for cfg in cfgs:
        for era in eras:
            ref = lsim.incumbent_daily(cfg, era)
            d1 = daily(cfg, era)
            X = inputs(cfg, era)
            d2 = daily(cfg, era, np.ones_like(X["M"]))
            st = fsim.stats(d2, CONFIGS[cfg]["C"], era)
            lines.append(f"{cfg} {era}: {100 * st['ret_yr']:.2f}% / Sharpe {st['sharpe']:.3f}; max daily diff vs the "
                         f"cached incumbent: base arrays {float((d1 - ref).abs().max()):.1e}, through the multiplier "
                         f"hook (m = 1) {float((d2 - ref).abs().max()):.1e}")
            print(lines[-1], flush=True)
    return lines


if __name__ == "__main__":
    if sys.argv[1] == "parity":
        L = parity(tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else ("S_0.5",),
                   tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ("sel",))
        os.makedirs(OUT, exist_ok=True)
        open(os.path.join(OUT, "reproduce.txt"), "a").write("\n".join(L) + "\n")
