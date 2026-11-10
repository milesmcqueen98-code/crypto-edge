#!/usr/bin/env python3
"""Live order timing study (reports/owner/timing_prereg.md), step 1: the studied minutes of one era tag.

Loads the lab (scripts/lab/core.py Data and LevelSet, R2-08's level set; nothing modified) and the every-minute
prediction panel (data/ladder_v5/panel_<tag>, approved = pred > that quarter's threshold, as in rt_live.era_arrays).

Studied minute (coin, q), q in the era's test window: approved at q-1 and the candle low of q <= L(q-1) + tick, or
approved at q and the low <= L(q) + tick (tick = the lab's fill tick, scripts/wick_sim.py spot_tick, in USD).
L(q) = LevelSet.lvl[coin][q], computed from candles through q-1.

Writes
  reports/owner/timing/data/studied_<tag>.csv.gz    one row per studied minute (what the print runner needs):
      coin, q, L_prev, L, tick, appr_prev, appr, open_res (the coin's research ladder is open at q), est_usd
  reports/owner/timing/data/levelcheck_<tag>.txt   the per-minute levels against the frozen dataset's parent rows
  <scratch>/minutes_<tag>.npz                       per coin and minute of the era (local only, for the evaluator):
      L, sig, appr, and the 4-sigma rung's candle exit for a fill at L(q) and at L(q-1) in minute q
usage: python scripts/owner/timing/export.py <main|early> <scratch_dir>
"""
import os
import sys
import time

import numpy as np
import pandas as pd

TAG = sys.argv[1]
SCR = sys.argv[2]
os.environ["LAB_ERA"] = TAG                       # the lab reads the era at import
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "lab"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
sys.path.insert(0, HERE)
import lsim  # noqa: E402  (puts scripts/ladder_v5 on the path, fsim)
import core  # noqa: E402
import run as RUN  # noqa: E402
import variants as VV  # noqa: E402
import wick_sim as ws  # noqa: E402
import fsim  # noqa: E402
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "owner", "timing", "data")
WINDOWS = {"main": ("sel", "chk"), "early": ("early",)}
H, THETA = 60, 0.6


def era_bounds(tag):
    los = [pd.Timestamp(fsim.ERAS[e][1][0]) for e in WINDOWS[tag]]
    his = [pd.Timestamp(fsim.ERAS[e][1][1]) + pd.Timedelta(days=1) for e in WINDOWS[tag]]
    return min(los), max(his)


def exits(hi, cf, i, e, sig, tick):
    """The lab's single-trade exit of a 4-sigma fill at price e in minute index i (core.book_x / sim.precompute):
    take-profit e * exp(0.6 * 4 * sig) first traded (high >= tp * (1 + tick / e)) in minutes i+1 .. i+60, else the
    close of minute i+60 (forward-filled). Returns (tp_off, g_tp bp, g60 bp)."""
    if not (np.isfinite(e) and np.isfinite(sig) and e > 0):
        return -1, np.nan, np.nan
    tp = e * np.exp(THETA * 4.0 * sig)
    seg = np.nan_to_num(hi[i + 1:i + H + 1])
    hit = np.nonzero(seg >= tp * (1 + tick / e))[0]
    tp_off = int(hit[0] + 1) if len(hit) else -1
    path = pd.Series(cf[i:i + H + 1]).ffill().bfill().to_numpy()
    return tp_off, 1e4 * np.log(tp / e), 1e4 * np.log(path[-1] / e)


def main():
    t0 = time.time()
    lsim.ensure_frozen()
    allv = {v["name"]: v for v in VV.VARIANTS + VV.ROUND1B + VV.make_round2()}
    (ls_d, _, _), = RUN.expand(allv["R2-08 C29+A11"])
    data = core.Data(list(ls_d["coins"]))
    ls = core.LevelSet(data, **ls_d)
    idx = data.idx
    print(f"lab loaded ({time.time() - t0:.0f}s)", flush=True)
    lo, hi = era_bounds(TAG)
    i_lo, i_hi = idx.get_indexer([lo])[0], idx.get_indexer([hi])[0] if hi < idx[-1] else len(idx)
    if i_hi < 0:
        i_hi = len(idx)
    pdir = os.path.join(ROOT, "data", "ladder_v5", f"panel_{TAG}")
    thr = pd.read_csv(os.path.join(pdir, "thr.csv"))
    tq = dict(zip(thr.quarter, thr.thr))
    P = fsim.load(TAG)
    par = P[(P.k == 4.0) & P.filled & (P.ts >= lo) & (P.ts < hi)]
    adv = pd.read_parquet(os.path.join(ROOT, "reports", "ladder_v5", "redteam", f"adv_{TAG}.parquet"))
    adv.index = pd.DatetimeIndex(adv.index).astype("datetime64[ns]")
    rows, arrs, lc = [], {}, []
    sl = slice(i_lo - 1, i_hi)                                     # one minute before the era for L(q-1), approval
    tix = idx[sl]
    for c in ls.coins:
        D = data.D[c]
        tick = float(ws.spot_tick(c))
        L = ls.lvl[c][sl].astype(np.float64)
        sig = ls.sig[c][sl].astype(np.float64)
        p = pd.read_parquet(os.path.join(pdir, f"{c}.parquet")).set_index("ts").pred
        pred = p.reindex(tix).to_numpy(np.float64)
        th = np.asarray(pd.PeriodIndex(tix, freq="Q").astype(str).map(tq), dtype=np.float64)
        appr = np.nan_to_num(pred, nan=-np.inf) > np.nan_to_num(th, nan=np.inf)
        appr &= np.isfinite(L)
        low = D["low"][sl]
        # level check: the frozen dataset's parents (lvl of the 4-sigma row = the lab's level at the parent minute)
        pc = par[par.coin == c]
        j = tix.get_indexer(pc.ts)
        assert (j >= 0).all()
        d = np.abs(L[j] / pc.lvl.to_numpy() - 1.0)
        lc.append((c, len(pc), float(np.nanmax(d)) if len(d) else 0.0, int(np.isnan(d).sum()),
                   int((~appr[j]).sum())))
        # research ladder open at q: a parent at t with t < q <= its exit minute (t + tp_off, else t + 60)
        open_res = np.zeros(len(tix), bool)
        for t_, off, hit in zip(j, pc.tp_off.to_numpy(), pc.tp_hit.to_numpy()):
            last = t_ + (int(off) if hit else H)
            open_res[t_ + 1:last + 1] = True
        with np.errstate(invalid="ignore"):
            s_prev = np.r_[False, appr[:-1] & (low[1:] <= L[:-1] + tick)]
            s_cur = appr & (low <= L + tick)
        st = (s_prev | s_cur)
        st[0] = False                                                # the minute before the era is not studied
        k = np.nonzero(st)[0]
        cfa, hia = D["cf"], D["high"]
        usd = np.nan_to_num(D["close"]) * D["vol"]
        ex = np.full((len(k), 2, 3), np.nan)
        for n, kk in enumerate(k):
            i = i_lo - 1 + kk
            for m, (e, s_) in enumerate(((L[kk], sig[kk]), (L[kk - 1], sig[kk - 1]))):
                ex[n, m] = exits(hia, cfa, i, e, s_, tick)
        day = tix[k].floor("D")
        px_d = pd.Series(D["cf"], index=idx).resample("D").last()
        vol_d = np.log(px_d).diff().rolling(30, min_periods=10).std().shift(1)
        R = pd.DataFrame(dict(coin=c, q=tix[k], L_prev=L[k - 1], L=L[k], tick=tick, appr_prev=appr[k - 1],
                              appr=appr[k], open_res=open_res[k],
                              est_usd=usd[i_lo - 1 + k] + usd[np.minimum(i_lo + k, len(usd) - 1)] / 6.0,
                              sig_prev=sig[k - 1], sig=sig[k], low=low[k],
                              tp_off_cur=ex[:, 0, 0], gtp_cur=ex[:, 0, 1], g60_cur=ex[:, 0, 2],
                              tp_off_prev=ex[:, 1, 0], gtp_prev=ex[:, 1, 1], g60_prev=ex[:, 1, 2],
                              vol_d=vol_d.reindex(day).to_numpy(), adv=adv[c].reindex(day).to_numpy()))
        rows.append(R)
        arrs[f"{c}_L"], arrs[f"{c}_appr"], arrs[f"{c}_open_res"] = L, appr, open_res
        print(f"{c}: {len(R)} studied minutes, approved share {appr.mean():.3f}, {len(pc)} parents, level max rel "
              f"diff {lc[-1][2]:.1e} ({time.time() - t0:.0f}s)", flush=True)
    S = pd.concat(rows, ignore_index=True).sort_values(["coin", "q"]).reset_index(drop=True)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SCR, exist_ok=True)
    run_cols = ["coin", "q", "L_prev", "L", "tick", "appr_prev", "appr", "open_res", "est_usd"]
    S[run_cols].to_csv(os.path.join(OUT, f"studied_{TAG}.csv.gz"), index=False, float_format="%.12g",
                       date_format="%Y-%m-%d %H:%M:%S")
    S.to_parquet(os.path.join(SCR, f"studied_{TAG}.parquet"), index=False)
    np.savez_compressed(os.path.join(SCR, f"minutes_{TAG}.npz"), ts=tix.values, **arrs)
    LC = pd.DataFrame(lc, columns=["coin", "parents", "max_rel_diff", "nan", "parent_not_approved"])
    with open(os.path.join(OUT, f"levelcheck_{TAG}.txt"), "w") as f:
        f.write(f"per-minute levels L(q) (scripts/lab LevelSet, R2-08) against the 4-sigma rows of the frozen dataset "
                f"({TAG}, {lo.date()} .. {hi.date()} exclusive)\n")
        f.write(LC.to_string(index=False) + "\n")
        f.write(f"largest relative difference {LC.max_rel_diff.max():.3e}; parents {LC.parents.sum()}; "
                f"parents not approved by the panel {LC.parent_not_approved.sum()}\n")
    for e in WINDOWS[TAG]:
        a, b = fsim.ERAS[e][1]
        m = (S.q >= a) & (S.q < pd.Timestamp(b) + pd.Timedelta(days=1))
        print(f"era {e}: {int(m.sum())} studied minutes")
    print(f"total {len(S)} studied minutes ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
