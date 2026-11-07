#!/usr/bin/env python3
"""Ladder v5, C7: who sold to us (reports/ladder_v5/specs/sweep.md, reports/ladder_v5_prereg.md).

D, known within a second of the parent's 4-sigma fill: first_sweep_depth_bp in reports/ladder_v5/prints_parents.csv
(main, 2025-26) or prints_parents_early.csv (2022-23): the prints sharing the timestamp of the first print one tick
below our bid (one aggressive order), at or below our price; D = how far below our price its lowest print was, in bp.
Cutoffs, per calendar quarter: the 1/3 and 2/3 quantiles (numpy's default linear interpolation) of D over every
earlier parent fill with a D in the same prints file (`ts` before the start of the quarter); fewer than 60 such
fills, or a parent with no D: multiplier 1.
  C7a_sweep_skip  the parent's 6/8-sigma rungs are not placed when D < lower cutoff; otherwise unchanged
  C7b_sweep_tilt  the parent's 6/8-sigma rungs x 0.5 when D < lower, x 1.0 between, x 1.5 when D >= upper cutoff
Both through hsim.book(..., deep_mult={(parent ts, coin): multiplier}); the same rule in every configuration.
usage: python scripts/ladder_v5/cand_sweep.py check [era] [cfg]   off switch (all multipliers 1) vs the cached incumbent
       python scripts/ladder_v5/cand_sweep.py describe            coverage, quarterly cutoffs, share of rungs touched
       python scripts/ladder_v5/cand_sweep.py run                 off switch (S_0.5, all eras), then C7a, then C7b
       python scripts/ladder_v5/cand_sweep.py oos                 after both trials: deeper rungs' net per $ by D
"""
import hashlib
import os
import shutil
import sys
import traceback

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gates  # noqa: E402  first: fsim puts scripts/hunt (which has its own gates.py) ahead of HERE on sys.path
import fsim  # noqa: E402
import hsim  # noqa: E402

assert all(os.path.dirname(os.path.abspath(m.__file__)) == HERE for m in (gates, fsim, hsim))

PRINTS = {"main": "prints_parents.csv", "early": "prints_parents_early.csv"}
MIN_N = 60
RES = os.path.join(fsim.OUT, "sweep")
TRIALS = (("C7a_sweep_skip", "skip"), ("C7b_sweep_tilt", "tilt"))
TOL_ACTIONS = 1e-12            # the off switch on the runner (numerical noise only); the local check must be exactly 0
DETAIL, DAILY, STATS = [], [], []


def ensure_frozen():
    """fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl, which git ignores (a fresh checkout would re-precompute it).
    Put the frozen copy there and check it against reports/ladder_v5/frozen/SHA256SUMS."""
    sums = dict(reversed(line.split()) for line in open(os.path.join(fsim.OUT, "frozen", "SHA256SUMS")) if line.strip())
    for tag in ("main", "early"):
        dst = os.path.join(fsim.ROOT, "reports", "wick1m", f"pre_hunt_{tag}.pkl")
        if not os.path.exists(dst):
            shutil.copyfile(os.path.join(fsim.OUT, "frozen", f"pre_hunt_{tag}.pkl"), dst)
        h = hashlib.sha256(open(dst, "rb").read()).hexdigest()
        if h != sums[f"frozen/pre_hunt_{tag}.pkl"]:
            raise SystemExit(f"{dst} does not match the frozen dataset ({h})")


def depth_table(tag):
    D = pd.read_csv(os.path.join(fsim.OUT, PRINTS[tag]), usecols=["ts", "coin", "first_sweep_depth_bp"],
                    parse_dates=["ts"]).rename(columns={"first_sweep_depth_bp": "D"})
    D["q"] = D.ts.dt.to_period("Q")
    return D


def cutoffs(tag):
    """{quarter: (n earlier parent fills with D, lower, upper)}; lower/upper None when n < 60."""
    D = depth_table(tag)
    ok = D[np.isfinite(D.D)]
    out = {}
    for q in sorted(D.q.unique()):
        prior = ok.D[ok.ts < q.start_time].to_numpy(np.float64)
        if len(prior) < MIN_N:
            out[q] = (len(prior), None, None)
        else:
            out[q] = (len(prior), float(np.quantile(prior, 1 / 3)), float(np.quantile(prior, 2 / 3)))
    return out


def buckets(tag):
    """Per parent: D, the quarter's cutoffs and its bucket ('none' = multiplier 1 by rule, 'lo', 'mid', 'hi')."""
    D = depth_table(tag)
    cut = cutoffs(tag)
    D["n_prior"] = [cut[q][0] for q in D.q]
    D["lower"] = [np.nan if cut[q][1] is None else cut[q][1] for q in D.q]
    D["upper"] = [np.nan if cut[q][2] is None else cut[q][2] for q in D.q]
    ok = np.isfinite(D.D) & np.isfinite(D.lower)
    D["bucket"] = np.where(~ok, "none", np.where(D.D < D.lower, "lo", np.where(D.D >= D.upper, "hi", "mid")))
    return D


MULT = {"off": {"none": 1.0, "lo": 1.0, "mid": 1.0, "hi": 1.0},
        "skip": {"none": 1.0, "lo": 0.0, "mid": 1.0, "hi": 1.0},
        "tilt": {"none": 1.0, "lo": 0.5, "mid": 1.0, "hi": 1.5}}


def mults(tag, variant):
    B = buckets(tag)
    return {(r.ts, r.coin): MULT[variant][r.bucket] for r in B.itertuples()}


def cfg_name(theta, C, today, cost_mult):
    for k, v in gates.CONFIGS.items():
        if v == dict(theta=theta, C=C, today=today, cost_mult=cost_mult):
            return k
    return f"theta{theta}_C{C:.0f}_today{today}_cost{cost_mult}"


def make(variant, name, record=True):
    mm = {}

    def book_fn(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0):
        tag = fsim.ERAS[era][0]
        if tag not in mm:
            mm[tag] = mults(tag, variant)
        d, out = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_,
                           deep_mult=mm[tag])
        if record:
            try:
                cfg = cfg_name(theta, C, today, cost_mult)
                for b in ("minute", "instant"):
                    Q, _, info, st = out[b]
                    q = Q[["ts", "coin", "k", "fill", "pnl", "want", "tp_fill", "gross"]].copy()
                    q.insert(0, "bound", b)
                    q.insert(0, "cfg", cfg)
                    q.insert(0, "era", era)
                    q.insert(0, "name", name)
                    DETAIL.append(q)
                    STATS.append(dict(name=name, era=era, cfg=cfg, bound=b, **st,
                                      maker_bp=info["maker_bp"], taker_bp=info["taker_bp"], v30=info["v30"]))
                DAILY.append(pd.DataFrame(dict(name=name, era=era, cfg=cfg, date=d.index, r=d.to_numpy())))
            except Exception:                                   # bookkeeping must never stop a trial
                traceback.print_exc()
        return d
    return book_fn


def key_coverage(era):
    """Static: every funded-able parent key hsim uses, (ts, coin) of the era's filled 4-sigma rows, is in the map."""
    tag, (lo, hi) = fsim.ERAS[era]
    P, _ = gates.data(tag)
    W = fsim.window(P, lo, hi)
    par = W[(W.k == 4.0) & W.filled]
    m = mults(tag, "off")
    return len(par), sum((r.ts, r.coin) in m for r in par.itertuples())


def check(eras=("chk",), cfg="S_0.5", tol=0.0, name="offswitch"):
    """Off switch: deep_mult with every multiplier 1 must reproduce the cached incumbent."""
    worst = 0.0
    for era in eras:
        tag = fsim.ERAS[era][0]
        P, pan = gates.data(tag)
        n, hit = key_coverage(era)
        d = make("off", name)(P, era, pan=pan, adv_=gates.adv(tag, era), **gates.CONFIGS[cfg])
        inc = gates.incumbent_cached(era, cfg)
        diff = float(np.abs(d.reindex(inc.index, fill_value=0.0) - inc).max())
        same_days = bool(d.index.equals(inc.index))
        worst = max(worst, diff)
        print(f"off switch {era} {cfg}: parent keys in map {hit}/{n}; same days {same_days}; "
              f"max daily difference {diff!r}", flush=True)
        if hit != n or not same_days or not np.isfinite(diff) or d.isna().any():
            worst = np.inf
    print(f"off switch worst {worst!r} (tolerance {tol!r}): {'PASS' if worst <= tol else 'FAIL'}", flush=True)
    return worst <= tol


def hook(era="chk", cfg="S_0.5"):
    """Mechanics only (order sizes, no fills or P&L): the deeper rungs' funded order under each variant relative to
    the off switch, by bucket, from hsim.run (instant bound) with the book's own preprocessing."""
    tag, (lo, hi) = fsim.ERAS[era]
    P, pan = gates.data(tag)
    kw = gates.CONFIGS[cfg]
    W = fsim.window(P, lo, hi)
    adv = gates.adv(tag, era)
    sc = None
    if kw["today"]:
        sc = fsim.today_scale(P, lo, hi)
        W = fsim.apply_scale(W, sc)
        adv = adv.copy()
        for c in adv.columns:
            adv[c] = adv[c] * sc.get(c, 1.0)
    B = buckets(tag)[["ts", "coin", "bucket"]]
    deep = W[W.k > 4.0][["ts", "coin", "k"]].merge(B, on=["ts", "coin"], how="left").set_index(W.index[W.k > 4.0])
    o = {}
    for v in ("off", "skip", "tilt"):
        o[v], _, _ = hsim.run(W, era, C=kw["C"], theta=kw["theta"], adv=adv, pan=pan, scale=sc, deep_mult=mults(tag, v))
    for v in ("skip", "tilt"):
        x = deep.assign(off=o["off"].reindex(deep.index).to_numpy(), cand=o[v].reindex(deep.index).to_numpy())
        x = x[x.off > 0]
        x["ratio"] = x.cand / x.off
        t = x.groupby("bucket").ratio.agg(n="size", zero_share=lambda r: float((r == 0).mean()), median="median",
                                          p10=lambda r: r.quantile(0.1), p90=lambda r: r.quantile(0.9))
        print(f"{v} ({era}, {cfg}): deeper order / off-switch order, rungs placed by the off switch\n"
              f"{t.round(3).to_string()}", flush=True)


def describe():
    """Coverage, the quarterly cutoffs, and the share of parents / research deeper fills each rule touches, by era."""
    os.makedirs(RES, exist_ok=True)
    rows, cut_rows = [], []
    for tag in ("main", "early"):
        for q, (n, lo, hi) in cutoffs(tag).items():
            cut_rows.append(dict(file=PRINTS[tag], quarter=str(q), n_earlier=n, lower_bp=lo, upper_bp=hi))
    for era, (tag, (lo, hi)) in fsim.ERAS.items():
        P = pd.read_pickle(os.path.join(fsim.OUT, "frozen", f"pre_hunt_{tag}.pkl"))
        W = fsim.window(P, lo, hi)
        par = W[(W.k == 4.0) & W.filled][["ts", "coin"]]
        deep = W[(W.k > 4.0) & W.filled][["ts", "coin", "k"]]
        B = buckets(tag)
        pb = par.merge(B, on=["ts", "coin"], how="left")
        db = deep.merge(B, on=["ts", "coin"], how="left")
        r = dict(era=era, parents=len(pb), with_prints=int(pb.n_prior.notna().sum()),
                 with_D=int(np.isfinite(pb.D).sum()), research_deep_fills=len(db))
        for b in ("none", "lo", "mid", "hi"):
            r[f"parents_{b}"] = int((pb.bucket == b).sum())
            r[f"deep_fills_{b}"] = int((db.bucket == b).sum())
        r["C7a_parents_suppressed_share"] = r["parents_lo"] / r["parents"]
        r["C7a_deep_fills_suppressed_share"] = r["deep_fills_lo"] / max(1, r["research_deep_fills"])
        r["C7b_parents_scaled_share"] = (r["parents_lo"] + r["parents_hi"]) / r["parents"]
        r["C7b_deep_fills_scaled_share"] = (r["deep_fills_lo"] + r["deep_fills_hi"]) / max(1, r["research_deep_fills"])
        rows.append(r)
    C, V = pd.DataFrame(cut_rows), pd.DataFrame(rows)
    C.to_csv(os.path.join(RES, "cutoffs.csv"), index=False)
    V.to_csv(os.path.join(RES, "coverage.csv"), index=False)
    print(C.round(3).to_string(index=False))
    print(V.T.to_string())


def flush():
    os.makedirs(RES, exist_ok=True)
    try:
        if DETAIL:
            pd.concat(DETAIL, ignore_index=True).to_parquet(os.path.join(RES, "detail.parquet"), index=False)
        if DAILY:
            pd.concat(DAILY, ignore_index=True).to_parquet(os.path.join(RES, "daily.parquet"), index=False)
        if STATS:
            pd.DataFrame(STATS).to_csv(os.path.join(RES, "hsim_stats.csv"), index=False)
    except Exception:
        traceback.print_exc()


def run():
    """One job: the off switch on all three eras at S*, theta 0.5 (abort before any trial if it fails), then the two
    pre-registered trials in order. The off-switch books double as the incumbent's per-tranche detail."""
    os.makedirs(RES, exist_ok=True)
    lines = []
    ok = check(eras=tuple(fsim.ERAS), cfg="S_0.5", tol=TOL_ACTIONS)
    flush()
    if not ok:
        raise SystemExit("off switch failed: no trial run")
    for name, variant in TRIALS:
        out = gates.run(name, make(variant, name), path="return",
                        note="spec sweep.md; quarterly walk-forward cutoffs on the era's prints file")
        s = gates.summary(out)
        print(s, flush=True)
        lines.append(s)
        flush()
        open(os.path.join(RES, "gates_summary.txt"), "w").write("\n\n".join(lines) + "\n")


def _logged():
    for name, _ in TRIALS:
        if not os.path.exists(os.path.join(fsim.OUT, "trials", f"{name}.json")):
            raise SystemExit(f"{name} is not logged yet: outcome views wait for both trials")


def drivers(cfg="S_0.5", top=4):
    """After both trials: what drives the difference at S*, theta 0.5 — hsim's counters, P&L by era x rung x bucket
    (minute/instant blended with the era's latency share, as the daily returns are), and the largest days."""
    _logged()
    det = pd.read_parquet(os.path.join(RES, "detail.parquet"))
    daily = pd.read_parquet(os.path.join(RES, "daily.parquet"))
    st = pd.read_csv(os.path.join(RES, "hsim_stats.csv"))
    names = ["offswitch"] + [n for n, _ in TRIALS]
    lines = [f"Drivers at {cfg} ($250K): offswitch = the incumbent (all multipliers 1, reproduces the cache)"]
    s = st[(st.cfg == cfg) & (st.bound == "instant")].set_index(["era", "name"])
    s["funded"] = s.parents - s.parent_unfunded
    lines.append("\nhsim counters, instant bound (parents funded / deeper rungs placed / deeper rungs filled / "
                 "minutes a deeper rung waited for cash)")
    lines.append(s.loc[:, ["funded", "deep_placed", "deep_filled", "cash_short_minutes"]].unstack("name")
                 .reindex(columns=names, level=1).to_string())
    B = pd.concat([buckets(t).assign(tag=t) for t in ("main", "early")])[["ts", "coin", "bucket"]]
    d = det[det.cfg == cfg].merge(B, on=["ts", "coin"], how="left")
    rows = []
    for era, g in d.groupby("era"):
        sh = fsim.lat_share(era, gates.CONFIGS[cfg]["theta"])
        lo, hi = fsim.ERAS[era][1]
        yrs = ((pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1) / 365.0
        a = g.groupby(["name", "bound", "k", "bucket"])[["pnl", "fill"]].sum().unstack("bound").fillna(0.0)
        for col in ("pnl", "fill"):
            a[(col, "blend")] = a[(col, "minute")] + sh * (a[(col, "instant")] - a[(col, "minute")])
        b = a.xs("blend", axis=1, level=1).reset_index()
        b["era"], b["pnl_yr"], b["fill_yr"] = era, b.pnl / yrs, b.fill / yrs
        rows.append(b)
    R = pd.concat(rows, ignore_index=True)
    R.to_csv(os.path.join(RES, "drivers_rung_bucket.csv"), index=False)
    C = gates.CONFIGS[cfg]["C"]
    for era in fsim.ERAS:
        x = R[R.era == era]
        p = x.pivot_table(index=["k", "bucket"], columns="name", values="pnl_yr", aggfunc="sum").reindex(columns=names)
        f = x.pivot_table(index=["k", "bucket"], columns="name", values="fill_yr", aggfunc="sum").reindex(columns=names)
        p, f = p.fillna(0.0), f.fillna(0.0)                     # no filled tranche in a cell = $0 (C7a's lo rungs)
        tab = pd.DataFrame({f"{n} net $K/yr": p[n] / 1e3 for n in names})
        for n in names[1:]:
            tab[f"{n} - inc, bp of C/yr"] = 1e4 * (p[n] - p["offswitch"]) / C
        for n in names:
            tab[f"{n} bought $M/yr"] = f[n] / 1e6
        tot = tab.sum().to_frame("total").T
        lines.append(f"\n{era}: net P&L by rung and D bucket (blended bounds; bucket 'none' = no cutoff or no D)")
        lines.append(pd.concat([tab, tot]).round(2).to_string())
    for n in names[1:]:
        lines.append(f"\n{n}: largest daily differences vs the incumbent ({cfg}), bp of capital")
        x = []
        for era in fsim.ERAS:
            inc = gates.incumbent_cached(era, cfg)
            c = daily[(daily.name == n) & (daily.era == era) & (daily.cfg == cfg)].set_index("date").r
            dd = (c.reindex(inc.index, fill_value=0.0) - inc)
            x.append(pd.DataFrame(dict(era=era, diff_bp=1e4 * dd)))
        X = pd.concat(x)
        X = X.reindex(X.diff_bp.abs().sort_values(ascending=False).index[:top])
        for day, r in X.iterrows():
            g = d[(d.name.isin(["offswitch", n])) & (d.ts.dt.normalize() == day) & (d.k == 4.0) & (d.fill > 0)
                  & (d.bound == "instant")]
            par = g[g.name == "offswitch"].bucket.value_counts().to_dict()
            dp = d[(d.ts.dt.normalize() == day) & (d.k > 4.0) & (d.bound == "instant")]
            fills = {m: int((dp[dp.name == m].fill > 0).sum()) for m in ("offswitch", n)}
            lines.append(f"  {day.date()} {r.era}: {r.diff_bp:+.1f} bp; incumbent parents by bucket {par}; "
                         f"deeper fills incumbent {fills['offswitch']} vs candidate {fills[n]}")
    txt = "\n".join(lines)
    open(os.path.join(RES, "drivers.txt"), "w").write(txt + "\n")
    print(txt)


def _net(g):
    return pd.Series(dict(n=int((g.fill > 0).sum()), usd=g.fill.sum(),
                          net_bp=1e4 * g.pnl.sum() / g.fill.sum() if g.fill.sum() > 0 else np.nan))


def oos():
    """After both trials are logged: the deeper rungs' net per $ by D tercile, research book ($250K, theta 0.5, 1x
    costs, instant bound, as in step 1's diagnosis) and the live incumbent at S*, theta 0.5 (off-switch detail)."""
    _logged()
    os.makedirs(RES, exist_ok=True)
    lines, rows = [], []
    det = pd.read_parquet(os.path.join(RES, "detail.parquet")) if os.path.exists(os.path.join(RES, "detail.parquet")) \
        else None
    for era, (tag, (lo, hi)) in fsim.ERAS.items():
        P = fsim.load(tag)
        B = buckets(tag)
        B = B[(B.ts >= lo) & (B.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
        books = {}
        _, out = fsim.book(P, era, C=250e3, theta=0.5)
        books["research_250k_t0.5_instant"] = out["instant"][0]
        if det is not None:
            for b in ("instant", "minute"):
                x = det[(det.name == "offswitch") & (det.era == era) & (det.cfg == "S_0.5") & (det.bound == b)]
                if len(x):
                    books[f"live_S0.5_{b}"] = x
        s = fsim.lat_share(era, 0.5)
        for bk, Q in books.items():
            q4 = Q[(Q.k == 4.0) & (Q.fill > 0)][["ts", "coin"]].drop_duplicates()
            M = q4.merge(B, on=["ts", "coin"], how="inner")
            M = M[np.isfinite(M.D)].copy()
            # terciles of D within the era among parents with a fill in this book (the diagnosis' method) ...
            M["tercile"] = pd.qcut(M.D, 3, labels=["T1 shallow", "T2", "T3 deep"])
            Z = Q[(Q.k > 4.0)].merge(M[["ts", "coin", "D", "tercile", "bucket"]], on=["ts", "coin"], how="inner")
            for split in ("tercile", "bucket"):            # ... and the rule's walk-forward buckets
                t = Z.groupby(["k", split], observed=True).apply(_net, include_groups=False).reset_index()
                t = t.rename(columns={split: "group"})
                t.insert(0, "split", split)
                t.insert(0, "book", bk)
                t.insert(0, "era", era)
                rows.append(t)
                lines.append(f"\n{era} {bk}: deeper rungs' net bp per $ by {split} of D "
                             f"({len(M)} parents with D and a fill)")
                lines.append(t.pivot(index="group", columns="k", values=["net_bp", "n"]).round(1).to_string())
            lines.append("  tercile edges (bp): " + ", ".join(f"{x:.2f}" for x in M.D.quantile([1 / 3, 2 / 3])))
            if bk.startswith("research"):                  # deep minus shallow tercile, parents resampled per tercile
                rng = np.random.default_rng(7)
                for k in (6.0, 8.0):
                    g = Z[(Z.k == k) & (Z.fill > 0)]
                    a = {t: (g[g.tercile == t].pnl.to_numpy(), g[g.tercile == t].fill.to_numpy())
                         for t in ("T1 shallow", "T3 deep")}
                    pt = 1e4 * (a["T3 deep"][0].sum() / a["T3 deep"][1].sum()
                                - a["T1 shallow"][0].sum() / a["T1 shallow"][1].sum())
                    bs = []
                    for _ in range(2000):
                        v = []
                        for t in ("T1 shallow", "T3 deep"):
                            p, f = a[t]
                            i = rng.integers(0, len(p), len(p))
                            v.append(p[i].sum() / f[i].sum())
                        bs.append(1e4 * (v[1] - v[0]))
                    lo5, hi95 = np.percentile(bs, [5, 95])
                    lines.append(f"  {k:.0f}-sigma deep minus shallow tercile: {pt:+.0f} bp per $ "
                                 f"(bootstrap 90% interval {lo5:+.0f} to {hi95:+.0f}; P(<= 0) {np.mean(np.array(bs) <= 0):.2f})")
        lines.append(f"  latency share s ({era}, theta 0.5): {s:.3f}")
    T = pd.concat(rows, ignore_index=True)
    T.to_csv(os.path.join(RES, "oos_terciles.csv"), index=False)
    txt = "\n".join(lines)
    open(os.path.join(RES, "oos_terciles.txt"), "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    ensure_frozen()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "check":
        era = sys.argv[2] if len(sys.argv) > 2 else "chk"
        cfg = sys.argv[3] if len(sys.argv) > 3 else "S_0.5"
        sys.exit(0 if check(eras=(era,), cfg=cfg, tol=0.0) else 1)
    elif cmd == "describe":
        describe()
    elif cmd == "hook":
        hook(*sys.argv[2:4])
    elif cmd == "run":
        run()
    elif cmd == "drivers":
        drivers()
    elif cmd == "oos":
        oos()
    else:
        raise SystemExit(__doc__)
