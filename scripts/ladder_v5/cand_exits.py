#!/usr/bin/env python3
"""Ladder v5, C3: passive time exit (reports/ladder_v5/specs/exits.md; reports/ladder_v5_prereg.md).

Incumbent: the part of a rung not sold at its take-profit (rem = fill - tp_fill) is sold at market 60 minutes after
its fill: taker fee + half-spread + square-root impact on rem (fsim.evaluate's pnl_rem, booked on the exit day).
Candidate (N minutes): at the 60-minute mark rem rests as a post-only sell at the previous minute's close plus one
tick, re-pegged every minute, for minutes 61 .. 60+N after the fill. In minute j it fills up to theta x the USD volume
traded above the peg on a one-tick trade-through (reports/ladder_v5/exit_paths_<tag>.pkl: pas_g[j] = log gain of the
peg vs the rung's level, pas_cap[j] = that volume, scaled by today's volume factor in S*), paying the book's maker
fee and no half-spread or impact. What is left at minute 60+N is sold at market at that minute's close (close_g[N])
with taker fee + half-spread + impact on the leftover. Each sale is booked on its own day; pnl_tp and the entry cost
are kept. Both latency bounds are rebuilt and blended with fsim.lat_share exactly as hsim.book.
Choices the spec leaves open (reported in reports/ladder_v5/exits/REPORT.md):
  - tranches are mapped to the exit paths by (ts, coin, k) of the frozen dataset; a deeper rung whose live fill
    minute differs from the research fill minute (hsim.with_live_fills) has no exit path and keeps the market exit;
  - our resting sells on one coin in one minute have the same peg and share one capacity (theta x the volume above
    the peg), pro rata to their unsold size (fsim likewise shares take-profit buyers within a parent);
  - the minute-60 close for N = 0 is the dataset's g60 (equal to exit_paths' c60 exactly; close_g[0] is its float32
    copy), so N = 0 reproduces the incumbent bit for bit.
Trials, in this order, path "return": C3a_passive_5 (N = 5), C3b_passive_15 (N = 15).
usage: python scripts/ladder_v5/cand_exits.py check [era] [cfg]   off switch (N = 0) against the cached incumbent
       python scripts/ladder_v5/cand_exits.py run                 off switch in every era and configuration, the two
                                                                  gated trials, diagnostics in reports/ladder_v5/exits/
"""
import hashlib
import os
import shutil
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gates  # noqa: E402  (first: fsim puts scripts/hunt, which has its own gates.py, ahead on sys.path)
import fsim  # noqa: E402
import hsim  # noqa: E402
import sim  # noqa: E402

assert hasattr(gates, "CONFIGS") and os.path.dirname(os.path.abspath(gates.__file__)) == HERE

OUTD = os.path.join(fsim.OUT, "exits")
TRIALS = (("C3a_passive_5", 5), ("C3b_passive_15", 15))
CFG_OF = {(v["theta"], v["C"], v["today"], v["cost_mult"]): k for k, v in gates.CONFIGS.items()}
_EP, _KM, _BOOK, DIAG = {}, {}, {}, {}
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.0f}s]", *a, flush=True)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ensure_frozen():
    """fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl, which git ignores; the frozen copy is committed in
    reports/ladder_v5/frozen/. On a fresh checkout copy it there (sha256 checked against frozen/SHA256SUMS, as are the
    exit paths), so fsim.load reads the frozen dataset instead of re-running sim.precompute."""
    sums = {}
    for line in open(os.path.join(fsim.OUT, "frozen", "SHA256SUMS")):
        if line.strip():
            h, p = line.split()
            sums[p] = h
    for tag in ("main", "early"):
        src = os.path.join(fsim.OUT, "frozen", f"pre_hunt_{tag}.pkl")
        dst = os.path.join(fsim.ROOT, "reports", "wick1m", f"pre_hunt_{tag}.pkl")
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
        for p in (src, dst):
            assert _sha(p) == sums[f"frozen/pre_hunt_{tag}.pkl"], f"{p} is not the frozen dataset"
        ep = os.path.join(fsim.OUT, f"exit_paths_{tag}.pkl")
        assert _sha(ep) == sums[f"exit_paths_{tag}.pkl"], f"{ep} is not the frozen exit path file"


def exit_paths(tag):
    if tag not in _EP:
        E = pd.read_pickle(os.path.join(fsim.OUT, f"exit_paths_{tag}.pkl"))
        _EP[tag] = dict(pos={ix: n for n, ix in enumerate(E.index)},
                        close_g=np.vstack(E.close_g.to_numpy()).astype(np.float64),
                        pas_g=np.vstack(E.pas_g.to_numpy()).astype(np.float64),
                        pas_cap=np.vstack(E.pas_cap.to_numpy()).astype(np.float64))
    return _EP[tag]


def keymap(tag, P):
    """(ts, coin, k) -> (row index of the frozen dataset, research fill minute offset, filled)."""
    if tag not in _KM:
        _KM[tag] = {(t, c, float(k)): (ix, float(fo), bool(fl))
                    for ix, t, c, k, fo, fl in zip(P.index, P.ts, P.coin, P.k, P.f_off, P.filled)}
    return _KM[tag]


def base_book(P, era, pan, adv_, theta, C, today, cost_mult):
    """The incumbent's hsim.book (daily returns and per-tranche frames), computed once per era and configuration."""
    key = (era, theta, C, today, cost_mult)
    if key not in _BOOK:
        _BOOK[key] = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_)
    return _BOOK[key]


def exit_rem(Q, info, tag, P, N, theta, hs_bp, impact_y, sc):
    """The remainders' sales under the passive exit for one latency bound's tranche frame Q (fsim.evaluate).
    Returns (P&L by day: take-profit legs and entry costs as fsim, remainders by sale day), per-tranche detail, and
    the largest difference between fsim's pnl_rem and this code's market exit at minute 60 (must be 0)."""
    n = len(Q)
    mk, tk = sim.tier(info["v30"], sim.SPOT_TIERS)                 # the book's tier, as fsim.evaluate
    assert abs(mk * 1e4 - info["maker_bp"]) < 1e-9 and abs(tk * 1e4 - info["taker_bp"]) < 1e-9
    rem = Q["fill"].to_numpy() - Q["tp_fill"].to_numpy()
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    g60 = Q.g60.to_numpy() / 1e4
    taker = tk + hs_bp / 1e4                                       # taker fee + half-spread, as fsim
    pnl_rem = Q.pnl_rem.to_numpy()
    mkt60 = rem * (g60 - taker - impact_y * vol_d * np.sqrt(np.maximum(rem, 0.0) / adv))
    check = float(np.max(np.abs(mkt60 - pnl_rem))) if n else 0.0

    # exit path of each tranche: the frozen row with the same (ts, coin, k), filled at the same minute
    km, EP = keymap(tag, P), exit_paths(tag)
    prow = np.full(n, -1, dtype=np.int64)
    status = np.zeros(n, dtype=np.int8)        # 0 exit path; 1 live fill minute differs from the research's; 2 none
    for i, (t, c, k, fo) in enumerate(zip(Q.ts, Q.coin, Q.k.to_numpy(dtype=float), Q.f_off.to_numpy(dtype=float))):
        ix, fo0, fl0 = km[(t, c, k)]
        if not fl0 or fo0 != fo:
            status[i] = 1
        elif ix not in EP["pos"]:
            status[i] = 2
        else:
            prow[i] = EP["pos"][ix]
    on = (prow >= 0) & (rem > 0)

    # passive minutes j = 1..N, in time order per coin; sells resting on one coin in one minute share the capacity
    left = np.where(on, rem, 0.0)
    sold = np.zeros((n, N + 1))
    pg = np.zeros((n, N + 1))
    shr = dict(minutes=0, multi=0, multi_bound=0, cap_mismatch=0)
    if N > 0 and on.any():
        ii = np.nonzero(on)[0]
        pg[ii, 1:] = EP["pas_g"][prow[ii], 1:N + 1]
        f_min = Q.fill_t.to_numpy()[ii].astype("datetime64[m]").astype(np.int64)
        coin = Q.coin.to_numpy()[ii]
        ccode = pd.factorize(coin)[0]
        scv = np.array([1.0 if sc is None else float(sc.get(c, 1.0)) for c in coin])
        e_t = np.repeat(np.arange(len(ii)), N)
        e_j = np.tile(np.arange(1, N + 1), len(ii))
        e_m = f_min[e_t] + sim.H + e_j                             # clock minute of passive minute j
        e_c = ccode[e_t]
        cap = theta * EP["pas_cap"][prow[ii][e_t], e_j] * scv[e_t]
        o = np.lexsort((e_t, e_m, e_c))
        e_t, e_j, e_m, e_c, cap = e_t[o], e_j[o], e_m[o], e_c[o], cap[o]
        new = np.ones(len(o), dtype=bool)
        new[1:] = (e_m[1:] != e_m[:-1]) | (e_c[1:] != e_c[:-1])
        starts = np.nonzero(new)[0]
        ends = np.append(starts[1:], len(o))
        lp = left[ii].copy()
        sp = np.zeros((len(ii), N + 1))
        for s0, s1 in zip(starts, ends):
            tt = e_t[s0:s1]
            need = lp[tt]
            tot = need.sum()
            cp = cap[s0:s1].min()
            shr["minutes"] += 1
            if s1 - s0 > 1:
                shr["multi"] += 1
                shr["cap_mismatch"] += int(np.any(cap[s0:s1] != cap[s0]))
            if tot <= 0 or cp <= 0:
                continue
            if tot > cp:
                f = need * (cp / tot)
                shr["multi_bound"] += int(s1 - s0 > 1 and (need > 0).sum() > 1)
            else:
                f = need
            lp[tt] = need - f
            sp[tt, e_j[s0:s1]] = f
        left[ii] = lp
        sold[ii] = sp

    pas_pnl = sold * (pg - mk)                                     # maker fee, no half-spread or impact
    g_close = g60.copy()
    if N > 0:
        g_close[on] = EP["close_g"][prow[on], N]
    lo_pnl = left * (g_close - taker - impact_y * vol_d * np.sqrt(np.maximum(left, 0.0) / adv))
    val = np.where(on, lo_pnl, pnl_rem)                            # no exit path or nothing left: the market exit
    day = np.where(on, (Q.fill_t + pd.Timedelta(minutes=sim.H + N)).dt.floor("D").to_numpy(),
                   Q.ex_t.dt.floor("D").to_numpy())
    parts = [pd.Series(Q.pnl_tp.to_numpy() - Q.entry_cost.to_numpy(), index=Q.tp_t.dt.floor("D").to_numpy()),
             pd.Series(val, index=day)]
    if N > 0:
        r_, j_ = np.nonzero(sold > 0)
        pdays = (pd.Series(Q.fill_t.to_numpy()[r_])
                 + pd.to_timedelta(sim.H + j_, unit="m").to_numpy()).dt.floor("D").to_numpy()
        parts.append(pd.Series(pas_pnl[r_, j_], index=pdays))
    daily = pd.concat(parts).groupby(level=0).sum()

    cum = np.cumsum(sold, axis=1)
    held = np.where(on[:, None], rem[:, None] - cum, 0.0)          # unsold after passive minute j (column j)
    u = {j: (held[:, j] if j <= N else np.zeros(n)) for j in (1, 5, 15)}
    det = pd.DataFrame(dict(ts=Q.ts.to_numpy(), coin=Q.coin.to_numpy(), k=Q.k.to_numpy(), fill_t=Q.fill_t.to_numpy(),
                            fill=Q["fill"].to_numpy(), rem=rem, status=status, on=on, g60=g60,
                            sold=sold[:, 1:].sum(axis=1), left=np.where(on, left, 0.0),
                            pas_gross=(sold * pg).sum(axis=1), close_gross=np.where(on, left * g_close, 0.0),
                            inc_rem=pnl_rem, cand_rem=np.where(on, lo_pnl + pas_pnl.sum(axis=1), pnl_rem),
                            fee_saved=sold[:, 1:].sum(axis=1) * (tk - mk), u1=u[1], u5=u[5], u15=u[15],
                            xmin=held[:, :N].sum(axis=1) if N > 0 else np.zeros(n)))
    det.attrs.update(shr, maker_bp=mk * 1e4, taker_bp=tk * 1e4)
    return daily, det, check


def make(N, record=True):
    def book_fn(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0):
        tag, (lo, hi) = fsim.ERAS[era]
        d_inc, out = base_book(P, era, pan, adv_, theta, C, today, cost_mult)
        sc = fsim.today_scale(P, lo, hi) if today else None        # as hsim.book
        hs_bp, impact_y = fsim.HS_BP * cost_mult, fsim.IMPACT_Y * cost_mult
        idx_d = pd.date_range(lo, hi, freq="D")
        res = {}
        for name in ("minute", "instant"):
            Q, _, info, _ = out[name]
            daily, det, chk = exit_rem(Q, info, tag, P, N, theta, hs_bp, impact_y, sc)
            res[name] = (daily.reindex(idx_d, fill_value=0.0) / C, det, chk)
        s = fsim.lat_share(era, theta)
        d1 = res["minute"][0] + s * (res["instant"][0] - res["minute"][0])
        if record:
            DIAG[(N, CFG_OF.get((theta, C, today, cost_mult)), era)] = dict(
                s=s, d_inc=d_inc, d_cand=d1, det={b: res[b][1] for b in res}, check=max(res[b][2] for b in res))
        return d1
    return book_fn


def offswitch(eras=tuple(fsim.ERAS), cfgs=tuple(gates.CONFIGS)):
    """N = 0 must reproduce the cached incumbent exactly (max daily difference 0)."""
    rows = []
    for cfg in cfgs:
        kw = gates.CONFIGS[cfg]
        for era in eras:
            tag = fsim.ERAS[era][0]
            P, pan = gates.data(tag)
            inc = gates.incumbent_cached(era, cfg)
            d0 = make(0, record=False)(P, era, pan=pan, adv_=gates.adv(tag, era), **kw)
            d_h, out = base_book(P, era, pan, gates.adv(tag, era), **kw)
            row = dict(cfg=cfg, era=era, days=len(inc),
                       max_diff_N0_vs_cache=float(np.abs(d0.reindex(inc.index, fill_value=0.0) - inc).max()),
                       max_diff_hsim_vs_cache=float(np.abs(d_h.reindex(inc.index, fill_value=0.0) - inc).max()))
            for b in ("minute", "instant"):
                Q, _, info, _ = out[b]
                lo, hi = fsim.ERAS[era][1]
                _, det, chk = exit_rem(Q, info, tag, P, 0, kw["theta"], fsim.HS_BP * kw["cost_mult"],
                                       fsim.IMPACT_Y * kw["cost_mult"],
                                       fsim.today_scale(P, lo, hi) if kw["today"] else None)
                r = det.rem > 0
                row.update({f"{b}_pnl_rem_check": chk, f"{b}_tranches_rem": int(r.sum()),
                            f"{b}_moved": int((r & (det.status == 1)).sum()),
                            f"{b}_moved_rem_share": float(det.rem[r & (det.status == 1)].sum() / det.rem[r].sum()),
                            f"{b}_no_path": int((r & (det.status == 2)).sum()),
                            f"{b}_maker_bp": info["maker_bp"], f"{b}_taker_bp": info["taker_bp"]})
            rows.append(row)
            log(f"off switch {cfg} {era}: N=0 vs cache {row['max_diff_N0_vs_cache']:.3g}, hsim vs cache "
                f"{row['max_diff_hsim_vs_cache']:.3g}, pnl_rem check {row['minute_pnl_rem_check']:.3g}/"
                f"{row['instant_pnl_rem_check']:.3g}, moved rungs {row['minute_moved']}/{row['instant_moved']}")
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ diagnostics
SUMS = ("rem_all", "rem_on", "sold", "left", "pas_gross", "sold_g60", "close_gross", "left_g60", "mkt60_gross", "inc",
        "cand", "u1", "u5", "u15", "xmin", "fee_saved", "n_on", "n_moved", "rem_moved", "n_nopath", "d_all")


def _sums(det):
    on = det.on.to_numpy()
    d = det[on]
    mv = (det.status == 1) & (det.rem > 0)
    return dict(rem_all=det.rem.sum(), rem_on=d.rem.sum(), sold=d.sold.sum(), left=d.left.sum(),
                pas_gross=d.pas_gross.sum(), sold_g60=(d.sold * d.g60).sum(), close_gross=d.close_gross.sum(),
                left_g60=(d.left * d.g60).sum(), mkt60_gross=(d.rem * d.g60).sum(), inc=d.inc_rem.sum(),
                cand=d.cand_rem.sum(), u1=d.u1.sum(), u5=d.u5.sum(), u15=d.u15.sum(), xmin=d.xmin.sum(),
                fee_saved=d.fee_saved.sum(), n_on=float(on.sum()), n_moved=float(mv.sum()),
                rem_moved=det.rem[mv].sum(), n_nopath=float(((det.status == 2) & (det.rem > 0)).sum()),
                d_all=(det.cand_rem - det.inc_rem).sum())


def _blend(a, b, s):
    return {k: a[k] + s * (b[k] - a[k]) for k in a}


def _derive(x, days, C):
    yrs = days / 365.0
    bp = lambda num, den: 1e4 * num / den if den > 0 else np.nan  # noqa: E731
    return dict(rem_on_usd_yr=x["rem_on"] / yrs, passive_fill_share=x["sold"] / x["rem_on"] if x["rem_on"] else np.nan,
                unsold_after_61=x["u1"] / x["rem_on"] if x["rem_on"] else np.nan,
                unsold_after_65=x["u5"] / x["rem_on"] if x["rem_on"] else np.nan,
                unsold_after_75=x["u15"] / x["rem_on"] if x["rem_on"] else np.nan,
                extra_min_per_usd=x["xmin"] / x["rem_on"] if x["rem_on"] else np.nan,
                extra_hold_pct_capital=100 * x["xmin"] / (days * 1440 * C),
                passive_px_vs_mkt60_bp=bp(x["pas_gross"] - x["sold_g60"], x["sold"]),
                leftover_px_vs_mkt60_bp=bp(x["close_gross"] - x["left_g60"], x["left"]),
                exit_px_vs_mkt60_bp=bp(x["pas_gross"] + x["close_gross"] - x["mkt60_gross"], x["rem_on"]),
                net_vs_mkt_bp=bp(x["cand"] - x["inc"], x["rem_on"]), d_usd_yr=x["d_all"] / yrs,
                d_ret_pts=100 * x["d_all"] / yrs / C, fee_saved_usd_yr=x["fee_saved"] / yrs,
                moved_rungs=x["n_moved"], moved_rem_share=x["rem_moved"] / x["rem_all"] if x["rem_all"] else np.nan,
                no_path=x["n_nopath"])


def diagnostics(outs):
    os.makedirs(OUTD, exist_ok=True)
    era_rows, rung_rows, shr_rows = [], [], []
    for (N, cfg, era), D in sorted(DIAG.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2])):
        lo, hi = fsim.ERAS[era][1]
        days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
        C = gates.CONFIGS[cfg]["C"]
        s = D["s"]
        dm, di = D["det"]["minute"], D["det"]["instant"]
        x = _blend(_sums(dm), _sums(di), s)
        era_rows.append(dict(N=N, cfg=cfg, era=era, lat_share=s, pnl_rem_check=D["check"], **_derive(x, days, C)))
        for k in (4.0, 6.0, 8.0):
            xk = _blend(_sums(dm[dm.k == k]), _sums(di[di.k == k]), s)
            rung_rows.append(dict(N=N, cfg=cfg, era=era, k=k, **_derive(xk, days, C)))
        for b, det in D["det"].items():
            shr_rows.append(dict(N=N, cfg=cfg, era=era, bound=b, **{k: det.attrs[k] for k in
                                                                     ("minutes", "multi", "multi_bound", "cap_mismatch",
                                                                      "maker_bp", "taker_bp")}))
    pd.DataFrame(era_rows).to_csv(os.path.join(OUTD, "diag_era.csv"), index=False)
    pd.DataFrame(rung_rows).to_csv(os.path.join(OUTD, "diag_rung.csv"), index=False)
    pd.DataFrame(shr_rows).to_csv(os.path.join(OUTD, "diag_shared_capacity.csv"), index=False)

    # daily returns at S*, theta 0.5 (incumbent and both candidates) and the busiest days
    frames = []
    for era in fsim.ERAS:
        D5, D15 = DIAG.get((5, "S_0.5", era)), DIAG.get((15, "S_0.5", era))
        if D5 is None or D15 is None:
            continue
        inc = gates.incumbent_cached(era, "S_0.5")
        det = D5["det"]["instant"]
        fills = det[det.fill > 0].groupby(det.fill_t[det.fill > 0].dt.floor("D")).size()
        remd = det[det.on].groupby(det.fill_t[det.on].dt.floor("D")).rem.sum()
        f = pd.DataFrame(dict(era=era, inc=inc, cand5=D5["d_cand"].reindex(inc.index, fill_value=0.0),
                              cand15=D15["d_cand"].reindex(inc.index, fill_value=0.0)))
        f["fills"] = fills.reindex(f.index).fillna(0).astype(int)
        f["rem_on_usd"] = remd.reindex(f.index).fillna(0.0)
        frames.append(f)
    if frames:
        F = pd.concat(frames)
        F.index.name = "date"
        F.to_csv(os.path.join(OUTD, "daily_S05.csv"))
        top = F.sort_values("fills", ascending=False).groupby("era").head(4).copy()
        for c in ("inc", "cand5", "cand15"):
            top[c + "_bp"] = 1e4 * top[c]
        top["d5_bp"], top["d15_bp"] = top.cand5_bp - top.inc_bp, top.cand15_bp - top.inc_bp
        top[["era", "fills", "rem_on_usd", "inc_bp", "d5_bp", "d15_bp"]].sort_values(["era", "fills"]).to_csv(
            os.path.join(OUTD, "cascade_days.csv"))
    with open(os.path.join(OUTD, "summary.txt"), "w") as fh:
        for name, o in outs.items():
            fh.write(gates.summary(o) + "\n\n")
    log("diagnostics written to", OUTD)


def main_run():
    ensure_frozen()
    os.makedirs(OUTD, exist_ok=True)
    off = offswitch()
    off.to_csv(os.path.join(OUTD, "offswitch.csv"), index=False)
    worst = float(off[["max_diff_N0_vs_cache", "max_diff_hsim_vs_cache"]].to_numpy().max())
    chk = float(off[["minute_pnl_rem_check", "instant_pnl_rem_check"]].to_numpy().max())
    log(f"off switch: worst N=0 / hsim vs cached incumbent {worst:.3g}; pnl_rem replication {chk:.3g}")
    if worst > 1e-9 or chk > 1e-9:
        raise SystemExit("off switch does not reproduce the incumbent: no trial logged")
    outs = {}
    for name, N in TRIALS:                                         # pre-registered order
        o = gates.run(name, make(N), path="return", note=f"passive time exit, N={N} min (specs/exits.md)")
        outs[name] = o
        log(gates.summary(o))
    diagnostics(outs)


def main_check(era="chk", cfg="S_0.5"):
    ensure_frozen()
    off = offswitch(eras=(era,), cfgs=(cfg,))
    pd.set_option("display.width", 200)
    print(off.T.to_string())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        main_check(*sys.argv[2:4])
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        main_run()
    else:
        print(__doc__)
