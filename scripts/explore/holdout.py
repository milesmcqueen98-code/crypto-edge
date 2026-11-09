#!/usr/bin/env python3
"""Explore v1: the one holdout read for the frozen short list (reports/explore/prereg.md 'Holdout read', 'Pass',
'Scorecard'). Refuses to run with uncommitted changes to the search code or the frozen list, and refuses a second read
(reports/explore/holdout_read.txt, written after the outputs).

  python scripts/explore/holdout.py

Writes holdout_cells.csv, holdout_tests.csv, holdout_years.csv, holdout_scorecard.csv and holdout.txt.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import xsim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "explore")
CAPS = (250e3, 1e6)
HOLD = ("check", "y2022_23")
DRAWS, SEED, TOL = 10_000, 0, 1e-12


def check_frozen():
    if os.path.exists(os.path.join(OUT, "holdout_read.txt")):
        sys.exit("the holdout was already read (reports/explore/holdout_read.txt); no second read")
    paths = ["scripts/explore", "reports/explore/finalists.json", "reports/explore/prereg.md"]
    dirty = subprocess.run(["git", "status", "--porcelain", "--"] + paths, cwd=ROOT, capture_output=True, text=True)
    if dirty.stdout.strip():
        sys.exit("uncommitted changes to the frozen files:\n" + dirty.stdout)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def ensemble_daily(members, era, C, mode=None, theta=None):
    out = []
    for sp in members:
        s = dict(sp)
        if theta is not None:
            s["theta"] = theta
        if mode is None:
            out.append(xsim.blended(s, era, C)[0])
        else:
            out.append(xsim.evaluate(dict(s, mode=mode), era, C)[0])
    return sum(out) / len(out)


def series(fin, era, C, mode=None, theta=None):
    """Daily returns of a finalist (a spec, or an ensemble of specs) in one mode (None = blended)."""
    if fin.get("members"):
        return ensemble_daily(fin["members"], era, C, mode, theta)
    s = dict(fin["spec"])
    if theta is not None:
        s["theta"] = theta
    if mode is None:
        return xsim.blended(s, era, C)[0]
    return xsim.evaluate(dict(s, mode=mode), era, C)[0]


def mtm_dd(fin, era, C):
    """Marked-to-market max drawdown of the blended book (minute and instant equity, blended on the union of times)."""
    lo, hi = xsim.ERAS[era][1]
    specs = fin["members"] if fin.get("members") else [fin["spec"]]
    eqs = []
    for sp in specs:
        e = {}
        for mode in ("minute", "instant"):
            _, _, info = xsim.evaluate(dict(sp, mode=mode), era, C, want_equity=True)
            e[mode] = info["equity"]
        t = e["minute"].index.union(e["instant"].index)
        em, ei = e["minute"].reindex(t).ffill().fillna(0.0), e["instant"].reindex(t).ffill().fillna(0.0)
        eqs.append(em + xsim.lat_share(era, C) * (ei - em))
    t = eqs[0].index
    for x in eqs[1:]:
        t = t.union(x.index)
    eq = sum(x.reindex(t).ffill().fillna(0.0) for x in eqs) / len(eqs)
    eq = eq[(eq.index >= pd.Timestamp(lo)) & (eq.index < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    if not len(eq):
        return 0.0
    lvl = C + (eq - eq.iloc[0])
    return float((lvl / lvl.cummax() - 1).min())


def excess(d, era):
    lo, hi = xsim.ERAS[era][1]
    idx = pd.date_range(lo, hi, freq="D")
    return d.reindex(idx, fill_value=0.0).to_numpy() - xsim.edge_book.rf_daily(idx).to_numpy()


def sharpe(e):
    s = e.std(ddof=1)
    return float(e.mean() / s * math.sqrt(365)) if s > 0 else float("nan")


def loo_min(ec, eb):
    def loo(e):
        n = len(e)
        s1, s2 = e.sum(), (e ** 2).sum()
        m = (s1 - e) / (n - 1)
        v = (s2 - e ** 2 - (n - 1) * m ** 2) / (n - 2)
        return m / np.sqrt(v) * math.sqrt(365)
    return float(np.min(loo(ec) - loo(eb)))


def clusters(era):
    """Event clusters of the era's R2-08 parents, as in the sizing lab: bootstrap units as lists of day positions."""
    tag, (lo, hi) = xsim.ERAS[era]
    P = xsim.data(tag)
    t = np.sort(P[(P.k == 4.0) & (P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))].ts.unique())
    t = pd.to_datetime(t)
    spans = []
    for i in range(len(t)):
        if i == 0 or (t[i] - t[i - 1]) > pd.Timedelta(hours=6):
            spans.append([t[i].floor("D"), (t[i] + pd.Timedelta(hours=2)).floor("D")])
        else:
            spans[-1][1] = max(spans[-1][1], (t[i] + pd.Timedelta(hours=2)).floor("D"))
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    days = pd.date_range(lo, hi, freq="D")
    pos = {d: i for i, d in enumerate(days)}
    covered, units = set(), []
    for a, b in merged:
        u = [pos[d] for d in pd.date_range(a, min(b, days[-1]), freq="D") if d in pos]
        covered.update(u)
        units.append(u)
    return units + [[i] for i in range(len(days)) if i not in covered]


def boot_p(diffs, rng):
    """Event-cluster bootstrap of the pooled mean of the vol-matched daily difference; p = P(mean* <= 0)."""
    tot_s, tot_n = np.zeros(DRAWS), np.zeros(DRAWS)
    for d, units in diffs:
        n_u = np.array([len(u) for u in units], float)
        su = np.array([d[u].sum() for u in units])
        L = len(d)
        M = int(math.ceil(1.5 * L / n_u.mean())) + 50
        for a in range(0, DRAWS, 500):
            idx = rng.integers(0, len(units), size=(min(500, DRAWS - a), M))
            cum = np.cumsum(n_u[idx], axis=1)
            last = np.argmax(cum >= L, axis=1)
            mask = (np.arange(M)[None, :] <= last[:, None])
            tot_s[a:a + len(idx)] += (su[idx] * mask).sum(1)
            tot_n[a:a + len(idx)] += (n_u[idx] * mask).sum(1)
    return float(np.mean(tot_s / tot_n <= 0))


def holm(ps):
    order = np.argsort(ps)
    m, out, run = len(ps), np.empty(len(ps)), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * ps[i]))
        out[i] = run
    return out


def main():
    head = check_frozen()
    F = json.load(open(os.path.join(OUT, "finalists.json")))
    inc = F["incumbent"]
    fins = F["finalists"]
    rng = np.random.default_rng(SEED)
    units = {e: clusters(e) for e in HOLD}
    cells, years, tests, store = [], [], [], {}
    base = {}
    for era in xsim.ERAS:
        for C in CAPS:
            base[(era, C, "b")] = series(inc, era, C)
            base[(era, C, "m")] = series(inc, era, C, mode="minute")
        base[(era, 250e3, "t25")] = series(inc, era, 250e3, theta=0.25)
        base[(era, "mtm")] = mtm_dd(inc, era, 250e3)
    for f in fins:
        ys = {}
        for era in xsim.ERAS:
            rec = dict(finalist=f["name"], era=era)
            for C in CAPS:
                d = series(f, era, C)
                eb, ec = excess(base[(era, C, "b")], era), excess(d, era)
                rec[f"d_b_{int(C)}"] = sharpe(ec) - sharpe(eb)
                rec[f"sh_b_{int(C)}"] = sharpe(ec)
                if C == 250e3:
                    store[(f["name"], era)] = (ec, eb, d.copy(), base[(era, C, "b")].copy())
                    rb, rc = base[(era, C, "b")].to_numpy(), d.to_numpy()
                    eqc, eqb = np.cumprod(1 + rc), np.cumprod(1 + rb)
                    rec.update(maxdd=float(np.min(eqc / np.maximum.accumulate(eqc) - 1)),
                               maxdd_base=float(np.min(eqb / np.maximum.accumulate(eqb) - 1)),
                               worst=float(rc.min()), worst_base=float(rb.min()), loo_min=loo_min(ec, eb))
                    for y, v in d.groupby(d.index.year).sum().items():
                        ys[y] = ys.get(y, 0.0) + float(v)
                dm = series(f, era, C, mode="minute")
                rec[f"d_m_{int(C)}"] = sharpe(excess(dm, era)) - sharpe(excess(base[(era, C, "m")], era))
            dt = series(f, era, 250e3, theta=0.25)
            rec["d_t25_250000"] = sharpe(excess(dt, era)) - sharpe(excess(base[(era, 250e3, "t25")], era))
            rec["mtm"] = mtm_dd(f, era, 250e3)
            rec["mtm_base"] = base[(era, "mtm")]
            cells.append(rec)
            print(f"{f['name']} {era} done", flush=True)
        for y, v in sorted(ys.items()):
            years.append(dict(finalist=f["name"], year=int(y), ret=v))
        diffs = []
        for e in HOLD:
            ec, eb, _, _ = store[(f["name"], e)]
            diffs.append((ec / ec.std(ddof=1) - eb / eb.std(ddof=1), units[e]))
        pooled = np.concatenate([d for d, _ in diffs])
        tests.append(dict(finalist=f["name"], mean_vm_diff=float(pooled.mean()), p=boot_p(diffs, rng)))
    X, Y, T = pd.DataFrame(cells), pd.DataFrame(years), pd.DataFrame(tests)
    T["p_holm"] = holm(T.p.to_numpy())
    res = []
    for name, g in X.groupby("finalist", sort=False):
        c1 = bool((g.d_b_250000 >= 0.20 - TOL).all())
        c2 = bool((g.d_b_1000000 >= -TOL).all())
        c3 = bool((g.d_m_250000 >= -TOL).all())
        c4 = bool((g.d_t25_250000 >= -TOL).all())
        c5 = bool(((g.maxdd >= 1.1 * g.maxdd_base - TOL) & (g.mtm >= 1.1 * g.mtm_base - TOL)
                   & (g.worst >= 1.1 * g.worst_base - TOL)).all())
        c6 = bool((Y[Y.finalist == name].ret > 0).all())
        ph = float(T[T.finalist == name].p_holm.iloc[0])
        res.append(dict(finalist=name, sharpe_ok=c1, capacity_ok=c2, minute_ok=c3, theta25_ok=c4, risk_ok=c5,
                        years_ok=c6, signif_ok=ph <= 0.05, p_holm=ph,
                        passes=all([c1, c2, c3, c4, c5, c6, ph <= 0.05])))
    R = pd.DataFrame(res)
    S = score(F, X, Y, T, store)
    X.to_csv(os.path.join(OUT, "holdout_cells.csv"), index=False)
    Y.to_csv(os.path.join(OUT, "holdout_years.csv"), index=False)
    T.merge(R, on="finalist", suffixes=("", "_r")).to_csv(os.path.join(OUT, "holdout_tests.csv"), index=False)
    S.to_csv(os.path.join(OUT, "holdout_scorecard.csv"), index=False)
    pd.set_option("display.width", 250)
    lines = [f"Explore v1 holdout, read once at commit {head}.", "",
             "Blended ΔSharpe at $250K / $1M, minute ΔSharpe at $250K, theta 0.25 ΔSharpe (vs the incumbent):",
             X[["finalist", "era", "d_b_250000", "d_b_1000000", "d_m_250000", "d_t25_250000", "sh_b_250000"]].round(3)
             .to_string(index=False), "",
             "Risk at $250K (blended): daily max DD, marked-to-market max DD, worst day, leave-one-day-out min ΔSharpe:",
             X[["finalist", "era", "maxdd", "maxdd_base", "mtm", "mtm_base", "worst", "worst_base", "loo_min"]].round(4)
             .to_string(index=False), "",
             "Tests (pooled check + 2022-23, event-cluster bootstrap of the vol-matched difference; Holm):",
             T.round(4).to_string(index=False), "", "Pass criteria:", R.to_string(index=False), "",
             "Calendar years (blended $250K):", Y.pivot_table(index="finalist", columns="year", values="ret", sort=False)
             .round(4).to_string(), "", "Scorecard:", S.to_string(index=False)]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "holdout.txt"), "w").write(txt)
    print(txt)
    open(os.path.join(OUT, "holdout_read.txt"), "w").write(
        f"holdout read once at commit {head}, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC\n")


def score(F, X, Y, T, store):
    rows = []
    for f in F["finalists"]:
        g = X[X.finalist == f["name"]]
        hb = g[g.era.isin(HOLD)]
        pts = dict(sharpe=20 * np.clip(hb.d_b_250000.mean() / 0.40, 0, 1))
        pts["capacity"] = 10 * np.clip(hb.d_b_1000000.mean() / 0.40, 0, 1) + 5 * float((g.d_b_1000000 >= -TOL).mean())
        cells = np.concatenate([g.d_b_250000, g.d_b_1000000, g.d_m_250000, g.d_m_1000000])
        pts["consistency"] = 10 * float((cells > 0).mean())
        ph = float(T[T.finalist == f["name"]].p_holm.iloc[0])
        pts["evidence"] = 15 * float(np.clip((0.20 - ph) / 0.15, 0, 1))
        d = np.concatenate([store[(f["name"], e)][2].to_numpy() - store[(f["name"], e)][3].to_numpy() for e in HOLD])
        top = 5 * float(np.clip((1 - np.sort(d)[::-1][:5].sum() / d.sum()) / 0.5, 0, 1)) if d.sum() > 0 else 0.0
        pts["spread"] = 5 * float((hb.loo_min >= 0.20 - TOL).mean()) + top
        checks = np.concatenate([(g.maxdd >= 1.1 * g.maxdd_base - TOL), (g.mtm >= 1.1 * g.mtm_base - TOL),
                                 (g.worst >= 1.1 * g.worst_base - TOL)])
        pts["risk"] = 12 * float(np.mean(checks)) + (3.0 if (Y[Y.finalist == f["name"]].ret > 0).all() else 0.0)
        pts["mechanism"], pts["implementation"] = float(f["hand"][0]), float(f["hand"][1])
        rows.append(dict(finalist=f["name"], total=round(sum(pts.values()), 1), **{k: round(float(v), 2) for k, v in pts.items()},
                         mean_d_b250_hold=float(hb.d_b_250000.mean()), mean_d_b1m_hold=float(hb.d_b_1000000.mean())))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main()
