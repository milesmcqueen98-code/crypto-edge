#!/usr/bin/env python3
"""Live order timing study (reports/owner/timing_prereg.md), step 3: the six policies on the trade prints.

Core (pure): `step` decides one studied minute of one coin from the resting bid carried in, the new level, the
approval flag, the tick, the minute's print path and the policy; `run_coin` walks one coin's minutes in time order
(one parent until its ladder closes). Both are unit-tested on synthetic paths (test_evaluate.py).

Timeline of one minute q under a policy with cancel time c and placement time p (seconds after q, prereg table):
  - the bid carried in from minute q-1 (its new bid, or a bid kept from earlier) rests [q, q + c): the stale bid;
  - if the coin is approved at q and the carried bid is within half a tick of L(q), the engine keeps it: it rests
    the whole minute, with no gap and no skip test, in every policy (P0 too);
  - otherwise the new bid at L(q) is placed at q + p unless the last print before q + p is at or below L(q) (skip),
    and rests to the minute's end; its tail [q + 60, q + 60 + c) is the next minute's stale bid, so every second is
    evaluated once, on the prints of the minute it falls in (prereg: new bid [q + p, q + 60 + c));
  - P0 (the research assumption) has c = 0 and p = 0: no stale bid, the new bid rests [q, q + 60).
  A carried bid exists only if the coin was approved at q-1, its ladder was not open, and the bid was placed and not
  filled. Fill: the first print at or below the bid minus one tick, at the bid's price.
Minutes that are not studied cannot fill (the candle low stays above both levels plus a tick); there the carried bid
follows the keep rule only.

P&L (prereg, "What is reported" 4-5), first order, against P0, at S* (today's volumes, costs x2, theta 0.5, $250K):
  shared parent (same coin and minute): -size x (entry / baseline entry - 1) x (0.4 if the 4-sigma rung's exit is the
    take-profit, else 1), size = the research's 4-sigma fill where the research has that parent, else the average
    research parent fill of that coin and quarter;
  parent only in the policy: the 4-sigma rung alone (lab exit rule on candles: take-profit at 0.6 x 4 sigma, else the
    close of minute q + 60; maker 6 bp in and on the take-profit, else taker + 2 x 2 bp half-spread + 2 x square-root
    impact on today's ADV);
  parent only in P0: its whole research ladder result removed (the incumbent's engine-faithful S* book, the poll1s
    blend of its two latency bounds, remainder exits priced from prints: scripts/ladder_v6x/lsim.py); a P0 parent the
    research does not have contributes its 4-sigma rung alone.
  P&L(X) = P&L(P0) + delta(X vs P0); X against P1 = P&L(X) - P&L(P1). Each delta is booked on the parent's exit day
  and added to the incumbent's daily series for the Sharpe change.
usage: python scripts/owner/timing/evaluate.py <scratch_dir> <derived_dir>
"""
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "owner", "timing")
sys.path.insert(0, HERE)
import prints_derive as PDV  # noqa: E402

# policy: (stale bid cancelled at c ms, new bid placed at p ms); P0 has no stale bid
POLICIES = {"P0": (0.0, 0), "P1": (8000.0, 10000), "P1a": (6500.0, 7500), "P1b": (12000.0, 15000),
            "P2": (1000.0, 1300), "P3": (8000.0, 8000)}
END_MS = 60000.0
H = 60


# ------------------------------------------------------------------------------------------------ pure core
def step(rest, L, appr, tick, path, pol):
    """One studied minute. rest: price of the bid carried in from q-1 (None if none); L = L(q); appr: approved at q;
    path: dict with 'rl' {start ms: (times, prices) running-minimum path from that start} and 'last' {start ms: last
    print price before it (NaN if unknown)}; pol: (c, p).
    Returns dict(fill, px, ms, src in {'stale', 'kept', 'new'}, rest (carried to q+1), skip, unknown_pre)."""
    c, p = pol
    out = dict(fill=False, px=np.nan, ms=np.nan, src="", rest=None, skip=False, unknown_pre=False)
    if rest is not None and appr and abs(L - rest) <= 0.5 * tick + 1e-12 * abs(L):
        t = PDV.first_through(*path["rl"][0], rest, tick)
        if t < END_MS:
            out.update(fill=True, px=rest, ms=t, src="kept")
        else:
            out["rest"] = rest
        return out
    if rest is not None and c > 0:
        t = PDV.first_through(*path["rl"][0], rest, tick)
        if t < c:
            out.update(fill=True, px=rest, ms=t, src="stale")
            return out
    if not appr or not np.isfinite(L):
        return out
    last = path["last"][p]
    if np.isfinite(last) and last <= L:
        out["skip"] = True
        return out
    out["unknown_pre"] = not np.isfinite(last)
    t = PDV.first_through(*path["rl"][p], L, tick)
    if t < END_MS:
        out.update(fill=True, px=L, ms=t, src="new")
    else:
        out["rest"] = L
    return out


def run_coin(L, appr, tick, studied, pol, close_after):
    """One coin's minutes 1 .. T-1 in time order. L, appr: per-minute arrays (index 0 = the minute before the era);
    studied: {minute index: path}; close_after(i, px, src) -> the ladder's exit minute index of a parent filled at i.
    Returns a list of parents (i, px, ms, src) and per-studied-minute flags {i: (skip, unknown_pre)}."""
    T = len(L)
    rest, free_from = None, 0
    parents, flags = [], {}
    for i in range(1, T):
        if i < free_from:
            rest = None
            continue
        if i in studied:
            r = step(rest, L[i], bool(appr[i]), tick, studied[i], pol)
            flags[i] = (r["skip"], r["unknown_pre"])
            if r["fill"]:
                parents.append((i, r["px"], r["ms"], r["src"]))
                free_from = close_after(i, r["px"], r["src"]) + 1
                rest = None
            else:
                rest = r["rest"]
            continue
        if appr[i] and np.isfinite(L[i]):
            if rest is None or abs(L[i] - rest) > 0.5 * tick + 1e-12 * abs(L[i]):
                rest = L[i]
        else:
            rest = None
    return parents, flags


# ------------------------------------------------------------------------------------------------ data
def load_paths(ddir):
    fs = sorted(glob.glob(os.path.join(ddir, "derived_*.parquet")))
    D = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    D["q"] = pd.to_datetime(D.q)
    assert not D.duplicated(["coin", "q"]).any()
    st = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(ddir, "status_*.csv*")))], ignore_index=True)
    return D, st


def path_of(r):
    if "low_ms" in r:                                     # the compact copy (compact.py): one union of the paths
        a, b = np.asarray(r["low_ms"], float), np.asarray(r["low_px"], float)
        return dict(rl={s: PDV.running_min(a, b, s) for s in PDV.STARTS},
                    last={s: float(r[f"last_px_{s}"]) for s in PDV.STARTS})
    return dict(rl={s: (np.asarray(r[f"rl_ms_{s}"], float), np.asarray(r[f"rl_px_{s}"], float)) for s in PDV.STARTS},
                last={s: float(r[f"last_px_{s}"]) for s in PDV.STARTS})


def research_book(era):
    """Per research parent (ts, coin): 4-sigma fill (size), whole ladder P&L and its 4-sigma exit, poll1s blend of
    the incumbent's two latency bounds at S* (lsim.rem_daily's row P&L, remainder exits priced from prints)."""
    sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
    import lsim
    import fsim
    cfg = "S_0.5"
    kw = lsim.CONFIGS[cfg]
    books = lsim.load_books(cfg, era)
    out = {}
    for b, (Q, info) in books.items():
        tk_fee = info["taker_bp"] / 1e4
        hs = fsim.HS_BP * kw["cost_mult"] / 1e4
        y = fsim.IMPACT_Y * kw["cost_mult"]
        tag, (lo, hi) = fsim.ERAS[era]
        sc = fsim.today_scale(lsim.RL.inputs(tag)["P"], lo, hi)
        rem = np.maximum((Q.fill - Q.tp_fill).to_numpy(), 0.0)
        adv = Q.adv.fillna(Q.adv.median()).to_numpy()
        vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
        fsc = Q.coin.map(sc).fillna(1.0).to_numpy()
        g60 = Q.g60.to_numpy() / 1e4
        pc = lsim.pcost()
        pnl = (Q.pnl_tp - Q.entry_cost).to_numpy().copy()
        for i in np.nonzero(rem > 0)[0]:
            R = rem[i]
            model = hs + y * vol_d[i] * np.sqrt(R / adv[i])
            fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(R / adv[i])
            ci = pc.cost(Q.coin.iat[i], pd.Timestamp(Q.fill_t.iat[i]), 0, R / fsc[i], fb_bp=fb)
            if not np.isfinite(ci):
                ci = model
            pnl[i] += R * (g60[i] - tk_fee - ci)
        Q = Q.assign(rowpnl=pnl)
        g = Q.groupby(["ts", "coin"])
        par = Q[Q.k == 4.0].set_index(["ts", "coin"])
        out[b] = pd.DataFrame(dict(ladder=g.rowpnl.sum(), bought=g.fill.sum())).join(
            par[["fill", "tp_hit", "tp_off", "lvl"]])
        out["info"] = info
    s = fsim.lat_share(era, kw["theta"])
    m, x = out["minute"], out["instant"]
    R = m.copy()
    for col in ("ladder", "bought", "fill"):
        R[col] = m[col] + s * (x[col].reindex(m.index).fillna(0.0) - m[col])
    d0 = lsim.incumbent_daily(cfg, era)
    return R, out["info"], d0, sc, kw


# ------------------------------------------------------------------------------------------------ main
ERAS = {"sel": ("main", "2025-01-01", "2026-03-31"), "chk": ("main", "2026-04-01", "2026-11-05"),
        "early": ("early", "2022-01-01", "2023-12-31")}
SEC_BINS = [0, 8000, 10000, 15000, 30000, 60001]
SEC_LAB = ["0-8s", "8-10s", "10-15s", "15-30s", "30-60s"]


def main(scr, ddir):
    t0 = time.time()
    D, st = load_paths(ddir)
    print(f"derived rows {len(D)}, windows {len(st)}: {st.status.value_counts().to_dict()}", flush=True)
    sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
    import lsim  # noqa: F401
    import fsim
    lsim.ensure_frozen()
    rows_out, sec_rows, ft_rows, conf_rows, qa_rows, minute_rows = [], [], [], [], [], []
    for tag in ("main", "early"):
        S = pd.read_parquet(os.path.join(scr, f"studied_{tag}.parquet"))
        Z = np.load(os.path.join(scr, f"minutes_{tag}.npz"), allow_pickle=True)
        ts = pd.DatetimeIndex(Z["ts"])
        J = S.merge(D, on=["coin", "q"], how="left", validate="1:1")
        J["have"] = J.status.notna()
        J["complete"] = J.status.eq("complete")
        Pf = fsim.load(tag)
        res_par = Pf[(Pf.k == 4.0) & Pf.filled].set_index(["ts", "coin"])
        eras = [e for e, v in ERAS.items() if v[0] == tag]
        book = {e: research_book(e) for e in eras}
        # sizes: research 4-sigma fill; else coin x quarter mean (coin mean, then overall mean, as fallbacks)
        allR = pd.concat([book[e][0] for e in eras])
        rq = allR.reset_index()
        rq["qtr"] = pd.PeriodIndex(rq.ts, freq="Q").astype(str)
        size_cq = rq.groupby(["coin", "qtr"]).fill.mean().to_dict()
        size_c = rq.groupby("coin").fill.mean().to_dict()
        size_all = float(rq.fill.mean())
        scale = {}
        for e in eras:
            scale.update(book[e][3])
        info = book[eras[0]][1]
        maker, taker = info["maker_bp"] / 1e4, info["taker_bp"] / 1e4
        hs, imp_y = fsim.HS_BP * 2.0 / 1e4, fsim.IMPACT_Y * 2.0
        res = {}
        for pol_name, pol in POLICIES.items():
            par_rows = []
            for c, g in J.groupby("coin"):
                L = Z[f"{c}_L"]
                ap = Z[f"{c}_appr"]
                tick = float(g.tick.iloc[0])
                ii = ts.get_indexer(g.q)
                assert (ii > 0).all()
                studied = {}
                for i, r in zip(ii, g.to_dict("records")):
                    if r["have"]:
                        studied[i] = path_of(r)
                    else:                                    # no prints: nothing can fill, no skip
                        studied[i] = dict(rl={s: (np.zeros(0), np.zeros(0)) for s in PDV.STARTS},
                                          last={s: np.nan for s in PDV.STARTS})
                gi = dict(zip(ii, g.to_dict("records")))

                def close_after(i, px, src, gi=gi):
                    r = gi[i]
                    key = "prev" if src == "stale" else "cur"
                    off = r[f"tp_off_{key}"]
                    return i + (int(off) if off >= 0 else H)

                parents, flags = run_coin(L, ap, tick, studied, pol, close_after)
                for i, px, ms, src in parents:
                    r = gi[i]
                    par_rows.append(dict(coin=c, q=ts[i], px=px, ms=ms, src=src, L=r["L"], L_prev=r["L_prev"]))
                for i, (sk, un) in flags.items():
                    minute_rows.append((tag, pol_name, c, ts[i], sk, un))
            res[pol_name] = pd.DataFrame(par_rows)
        # per-parent valuation
        Jk = J.set_index(["q", "coin"])

        def value(Pp, e):
            """Size, research ladder P&L (or the rung alone), rung alone, 4-sigma exit is TP, exit day; per parent."""
            R = book[e][0]
            out = []
            for r in Pp.itertuples():
                key = (r.q, r.coin)
                x = Jk.loc[key]
                kk = "prev" if r.src == "stale" else "cur"
                lev = x["L_prev"] if kk == "prev" else x["L"]
                tp_off, gtp, g60 = x[f"tp_off_{kk}"], x[f"gtp_{kk}"], x[f"g60_{kk}"] + 1e4 * np.log(lev / r.px)
                if key in R.index:
                    S_ = float(R.at[key, "fill"])
                    ladder = float(R.at[key, "ladder"])
                    tp_res = bool(R.at[key, "tp_hit"])
                    in_res = True
                else:
                    qq = str(pd.Period(r.q, freq="Q"))
                    S_ = size_cq.get((r.coin, qq), size_c.get(r.coin, size_all))
                    ladder, tp_res, in_res = np.nan, None, False
                advs = x["adv"] * scale.get(r.coin, 1.0)
                if tp_off >= 0:
                    alone = S_ * (gtp / 1e4 - maker) - S_ * maker
                else:
                    vd = x["vol_d"] if np.isfinite(x["vol_d"]) else 0.05
                    imp = imp_y * vd * np.sqrt(S_ / advs) if advs > 0 else 0.0
                    alone = S_ * (g60 / 1e4 - taker - hs - imp) - S_ * maker
                tp_any = tp_res if tp_res is not None else tp_off >= 0
                ex_day = (r.q + pd.Timedelta(minutes=int(tp_off) + 1 if tp_off >= 0 else H)).floor("D")
                out.append(dict(size=S_, ladder=ladder if in_res else alone, alone=alone, in_res=in_res,
                                tp=bool(tp_any), day=ex_day))
            return pd.DataFrame(out, index=Pp.index)

        for e in eras:
            _, lo, hi = ERAS[e]
            R, _, d0, _, kw = book[e]
            C = kw["C"]
            sh0 = fsim.stats(d0, C, e)["sharpe"]
            idx = d0.index
            inera = {k: v[(v.q >= lo) & (v.q < pd.Timestamp(hi) + pd.Timedelta(days=1))].reset_index(drop=True)
                     for k, v in res.items()}
            V = {k: pd.concat([v, value(v, e)], axis=1) for k, v in inera.items()}
            base = V["P0"].set_index(["coin", "q"])
            pnl0 = float(base.ladder.sum())
            bought0 = float(R.loc[[k for k in zip(base.index.get_level_values(1), base.index.get_level_values(0))
                                   if k in R.index], "bought"].sum()) + float(base.loc[~base.in_res, "size"].sum())
            # research parents of this era vs P0 (prereg item 6)
            rp = res_par[(res_par.index.get_level_values(0) >= lo)
                         & (res_par.index.get_level_values(0) < pd.Timestamp(hi) + pd.Timedelta(days=1))]
            rset = set((t, c) for t, c in rp.index)
            p0set = set((t, c) for c, t in base.index)
            conf_rows.append(dict(era=e, research_parents=len(rset), p0_parents=len(p0set),
                                  confirmed=len(rset & p0set), research_only=len(rset - p0set),
                                  p0_only=len(p0set - rset),
                                  research_rows_without_prints=int(sum(
                                      1 for k in rset if not Jk.loc[k, "have"])),
                                  research_rows_incomplete=int(sum(1 for k in rset if not Jk.loc[k, "complete"]))))
            # fill times of P0's parents (item 3)
            b0 = V["P0"]
            ft_rows.append(dict(era=e, p0_parents=len(b0), first_8s=int((b0.ms < 8000).sum()),
                                first_10s=int((b0.ms < 10000).sum()), first_15s=int((b0.ms < 15000).sum()),
                                share_8s=float((b0.ms < 8000).mean()), share_10s=float((b0.ms < 10000).mean()),
                                share_15s=float((b0.ms < 15000).mean()), median_s=float(b0.ms.median() / 1000)))
            # deltas vs P0, then P&L(X) and vs P1
            dl, daily = {}, {}
            for k, v in V.items():
                vv = v.set_index(["coin", "q"])
                sh = vv.index.intersection(base.index)
                only_x = vv.index.difference(base.index)
                only_0 = base.index.difference(vv.index)
                a, b = vv.loc[sh], base.loc[sh]
                w = np.where(b.tp.to_numpy(), 0.4, 1.0)
                adj = -b["size"].to_numpy() * (a.px.to_numpy() / b.px.to_numpy() - 1.0) * w
                parts = [pd.Series(adj, index=b.day.to_numpy()),
                         pd.Series(vv.loc[only_x, "alone"].to_numpy(), index=vv.loc[only_x, "day"].to_numpy()),
                         pd.Series(-base.loc[only_0, "ladder"].to_numpy(), index=base.loc[only_0, "day"].to_numpy())]
                dd = pd.concat(parts).groupby(level=0).sum().reindex(idx, fill_value=0.0)
                daily[k] = dd
                dl[k] = dict(sh=sh, only_x=only_x, only_0=only_0, adj=float(adj.sum()),
                             add=float(vv.loc[only_x, "alone"].sum()), rem=float(-base.loc[only_0, "ladder"].sum()))
                # entry difference on shared parents, by source and by seconds after q
                ent = 1e4 * (a.px.to_numpy() / b.px.to_numpy() - 1.0)
                wts = b["size"].to_numpy()
                bins = pd.cut(a.ms.to_numpy(), SEC_BINS, right=False, labels=SEC_LAB)
                for src in ("stale", "kept", "new", "all"):
                    m = np.ones(len(a), bool) if src == "all" else (a.src.to_numpy() == src)
                    for lab in SEC_LAB + ["all"]:
                        mm = m & ((bins == lab) if lab != "all" else True)
                        if mm.sum() == 0:
                            continue
                        sec_rows.append(dict(era=e, policy=k, vs="P0", src=src, seconds=lab, n=int(mm.sum()),
                                             entry_bp=float(np.average(ent[mm], weights=np.maximum(wts[mm], 1e-9)))))
            for k, v in V.items():
                vv = v.set_index(["coin", "q"])
                for ref in ("P0", "P1"):
                    rb = V[ref].set_index(["coin", "q"])
                    sh = vv.index.intersection(rb.index)
                    a, b = vv.loc[sh], rb.loc[sh]
                    ent = 1e4 * (a.px.to_numpy() / b.px.to_numpy() - 1.0)
                    wts = np.maximum(b["size"].to_numpy(), 1e-9)
                    dpnl = float(daily[k].sum() - daily[ref].sum())
                    dx = d0 + daily[k] / C
                    dr = d0 + daily[ref] / C
                    rows_out.append(dict(
                        era=e, policy=k, vs=ref, parents=len(vv), ref_parents=len(rb), shared=len(sh),
                        shared_share=len(sh) / len(rb) if len(rb) else np.nan,
                        only_policy=len(vv.index.difference(rb.index)), only_ref=len(rb.index.difference(vv.index)),
                        entry_bp=float(np.average(ent, weights=wts)) if len(sh) else np.nan,
                        stale_fills=int((vv.src == "stale").sum()), kept_fills=int((vv.src == "kept").sum()),
                        new_fills=int((vv.src == "new").sum()),
                        pnl_p0_usd=pnl0, bought_p0_usd=bought0, dpnl_usd=dpnl,
                        dpnl_bp=1e4 * dpnl / bought0, dpnl_pct=100 * dpnl / (pnl0 + float(daily[ref].sum())),
                        sharpe_book=sh0, sharpe_ref=fsim.stats(dr, C, e)["sharpe"],
                        dsharpe=fsim.stats(dx, C, e)["sharpe"] - fsim.stats(dr, C, e)["sharpe"],
                        adj_usd=dl[k]["adj"] - (dl[ref]["adj"] if ref != "P0" else 0.0),
                        added_usd=dl[k]["add"] - (dl[ref]["add"] if ref != "P0" else 0.0),
                        removed_usd=dl[k]["rem"] - (dl[ref]["rem"] if ref != "P0" else 0.0)))
            for k, v in V.items():
                for r in v.itertuples():
                    qa_rows.append(dict(era=e, policy=k, coin=r.coin, q=r.q, px=r.px, ms=r.ms, src=r.src,
                                        size=r.size, in_res=r.in_res, tp=r.tp))
            print(f"{e}: done ({time.time() - t0:.0f}s)", flush=True)
        # completeness
        for e in eras:
            _, lo, hi = ERAS[e]
            m = (J.q >= lo) & (J.q < pd.Timestamp(hi) + pd.Timedelta(days=1))
            x = J[m]
            qa_rows_c = dict(era=e, studied=int(m.sum()), with_prints=int(x.have.sum()), complete=int(x.complete.sum()),
                             pre_unknown=int(x.pre_px.isna().sum()), no_print_in_minute=int((x.n60 == 0).sum()),
                             print_min_above_candle_low=int((x.min60 > x.low * (1 + 0.5e-4)).sum()),      # 0.5 bp: float32 candles
                             print_min_below_candle_low=int((x.min60 < x.low * (1 - 0.5e-4)).sum()))
            conf_rows[-len(eras) + eras.index(e)].update(qa_rows_c)
    T = pd.DataFrame(rows_out)
    T.to_csv(os.path.join(OUT, "policies.csv"), index=False, float_format="%.6g")
    pd.DataFrame(sec_rows).to_csv(os.path.join(OUT, "entry_by_seconds.csv"), index=False, float_format="%.6g")
    pd.DataFrame(ft_rows).to_csv(os.path.join(OUT, "p0_fill_times.csv"), index=False, float_format="%.6g")
    pd.DataFrame(conf_rows).to_csv(os.path.join(OUT, "p0_vs_research.csv"), index=False, float_format="%.6g")
    pd.DataFrame(qa_rows).to_csv(os.path.join(OUT, "parents.csv.gz"), index=False, float_format="%.10g")
    M = pd.DataFrame(minute_rows, columns=["tag", "policy", "coin", "q", "skip", "unknown_pre"])
    M.to_csv(os.path.join(scr, "minute_flags.csv.gz"), index=False)
    print(T[["era", "policy", "vs", "parents", "shared", "shared_share", "only_policy", "only_ref", "entry_bp",
             "dpnl_pct", "dsharpe"]].to_string(index=False))
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
