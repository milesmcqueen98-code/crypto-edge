#!/usr/bin/env python3
"""Sizing lab, the one holdout read (reports/sizing_lab/prereg.md 'Freeze, then one read', 'Pass', 'Scorecard').

Run as `python scripts/sizing_lab/lab.py holdout`, only after the freeze commit of reports/sizing_lab/finalists.json.
It refuses to run with uncommitted changes to the lab, the simulator or the frozen rules, and refuses to run twice
(reports/sizing_lab/holdout_read.txt records the read).
Writes holdout_cells.csv, tests.csv, years.csv, info.csv, scorecard.csv and holdout.txt.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

import lab

OUT = lab.OUT
SEED, DRAWS = 0, 10_000
TOL = 1e-12
HAND = {"A1": (2, 5), "A2": (4, 5), "A3": (5, 4), "B1": (7, 5), "B2": (7, 5), "B3": (7, 5), "C1": (4, 4), "C2": (6, 5),
        "C3": (4, 4)}


def check_frozen():
    marker = os.path.join(OUT, "holdout_read.txt")
    if os.path.exists(marker):
        sys.exit("the holdout was already read (reports/sizing_lab/holdout_read.txt); no second read")
    paths = ["scripts/sizing_lab", "scripts/wick1m/sim.py", "scripts/wick_v4/rungs.py", "reports/sizing_lab/finalists.json",
             "reports/sizing_lab/prereg.md", "reports/sizing_lab/macro_days.csv"]
    dirty = subprocess.run(["git", "status", "--porcelain", "--"] + paths, cwd=lab.ROOT, capture_output=True, text=True)
    if dirty.stdout.strip():
        sys.exit("uncommitted changes to the frozen files:\n" + dirty.stdout)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=lab.ROOT, capture_output=True, text=True).stdout.strip()


def mark_read(head):
    """Written after the outputs, so a crash before any result is printed can be re-run (and logged)."""
    with open(os.path.join(OUT, "holdout_read.txt"), "w") as f:
        f.write(f"holdout read once at commit {head}, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC\n")


def era_series(rule, book, C, era, c, mtm=True, mult_cap=True, theta=lab.THETA):
    tag = lab.ERAS[era][0]
    mult = None if rule is None else lab.rule_mult(rule, book, tag, c)
    d, Q, info, st = lab.run(book, C, era, mult=mult, mtm=mtm, mult_cap=mult_cap, theta=theta)
    return d, lab.exposure(Q), st.get("maxdd_mtm", float("nan"))


def boot_p(pairs, rng):
    """Event-cluster bootstrap of the pooled ΔSharpe; pairs: [(ec, eb, units)] per era. Returns (point, p)."""
    S1c = S2c = S1b = S2b = N = 0.0
    tot = np.zeros((DRAWS, 5))
    for ec, eb, units in pairs:
        n_u = np.array([len(u) for u in units], float)
        st = np.array([[len(u), ec[u].sum(), (ec[u] ** 2).sum(), eb[u].sum(), (eb[u] ** 2).sum()] for u in units])
        L = len(ec)
        M = int(math.ceil(1.5 * L / n_u.mean())) + 50
        for a in range(0, DRAWS, 500):                           # units drawn until the era's length is reached
            idx = rng.integers(0, len(units), size=(min(500, DRAWS - a), M))
            cum = np.cumsum(n_u[idx], axis=1)
            if (cum[:, -1] < L).any():
                raise RuntimeError("bootstrap draw too short; raise M")
            last = np.argmax(cum >= L, axis=1)
            mask = (np.arange(M)[None, :] <= last[:, None]).astype(float)
            tot[a:a + len(idx)] += np.einsum("dm,dmk->dk", mask, st[idx])
        S1c, S2c, S1b, S2b, N = S1c + ec.sum(), S2c + (ec ** 2).sum(), S1b + eb.sum(), S2b + (eb ** 2).sum(), N + len(ec)

    def sh(n, s1, s2):
        v = (s2 - s1 ** 2 / n) / (n - 1)
        return s1 / n / np.sqrt(v) * math.sqrt(365)

    point = float(sh(N, S1c, S2c) - sh(N, S1b, S2b))
    dstar = sh(tot[:, 0], tot[:, 1], tot[:, 2]) - sh(tot[:, 0], tot[:, 3], tot[:, 4])
    return point, float(np.mean(dstar <= 0))


def excess(d, era):
    lo, hi = lab.ERAS[era][1]
    idx = pd.date_range(lo, hi, freq="D")
    return d.reindex(idx, fill_value=0.0).to_numpy() - lab.edge_book.rf_daily(idx).to_numpy()


def holm(ps):
    order = np.argsort(ps)
    m, out, run_max = len(ps), np.empty(len(ps)), 0.0
    for rank, i in enumerate(order):
        run_max = max(run_max, min(1.0, (m - rank) * ps[i]))
        out[i] = run_max
    return out


def main():
    head = check_frozen()
    F = json.load(open(os.path.join(OUT, "finalists.json")))["finalists"]
    tests = []                                                   # (test id, candidate rule, c, baseline rule, c)
    for fam in ("A", "B", "C"):
        if fam in F:
            tests.append((F[fam]["cand"], F[fam]["rule"], F[fam]["c"], None, None))
    if "A+B" in F:
        tests.append((F["A+B"]["cand"] + " vs " + F["B"]["cand"], F["A+B"]["rule"], F["A+B"]["c"], F["B"]["rule"],
                      F["B"]["c"]))
    cells, years, series, rng = [], [], {}, np.random.default_rng(SEED)
    for tid, rule, cmap, brule, bmap in tests:
        for book in lab.BOOKS:
            for C in lab.CAPS:
                key = f"{book}|{int(C)}"
                ys = {}
                for era in lab.ERAS:
                    dc, xc, ddc = era_series(rule, book, C, era, cmap[key])
                    db, xb, ddb = era_series(brule, book, C, era, bmap[key] if bmap else None)
                    m = lab.compare(dc, db, era)
                    cells.append(dict(test=tid, book=book, capital=C, era=era, capital_ratio=xc / xb, maxdd_mtm=ddc,
                                      maxdd_mtm_base=ddb, **m))
                    series[(tid, book, C, era)] = (excess(dc, era), excess(db, era), dc.copy(), db.copy())
                    for y, v in dc.groupby(dc.index.year).sum().items():
                        ys[y] = ys.get(y, 0.0) + float(v)
                for y, v in sorted(ys.items()):
                    years.append(dict(test=tid, book=book, capital=C, year=int(y), ret=v))
                print(f"{tid} {book} ${C / 1e3:,.0f}K done", flush=True)
    X = pd.DataFrame(cells)
    Y = pd.DataFrame(years)
    # significance: pooled check + 2022-23, event-cluster bootstrap; IUT over capitals; Holm over tests x books
    units = {era: lab.clusters(era)[1] for era in lab.HOLD}
    trows = []
    for tid, *_ in tests:
        for book in lab.BOOKS:
            row = dict(test=tid, book=book)
            for C in lab.CAPS:
                pairs = [(series[(tid, book, C, e)][0], series[(tid, book, C, e)][1], units[e]) for e in lab.HOLD]
                pt, p = boot_p(pairs, rng)
                row[f"d_sharpe_pooled_{int(C)}"], row[f"p_{int(C)}"] = pt, p
                for e in lab.HOLD:
                    _, pe = boot_p([pairs[lab.HOLD.index(e)]], rng)
                    row[f"p_{e}_{int(C)}"] = pe
            row["p_iut"] = max(row[f"p_{int(C)}"] for C in lab.CAPS)
            trows.append(row)
    T = pd.DataFrame(trows)
    T["p_holm"] = holm(T.p_iut.to_numpy())
    # pass criteria
    res = []
    for (tid, book), g in X.groupby(["test", "book"], sort=False):
        c1 = bool((g.d_sharpe >= 0.20 - TOL).all())
        c2 = bool(((g.maxdd >= g.maxdd_base - TOL) & (g.maxdd_mtm >= g.maxdd_mtm_base - TOL) & (g.worst >= g.worst_base - TOL)
                   & (g.cvar5 >= g.cvar5_base - TOL)).all())
        c3 = bool((g.loo_min >= 0.20 - TOL).all())
        yy = Y[(Y.test == tid) & (Y.book == book)]
        c4 = bool((yy.ret > 0).all())
        ph = float(T[(T.test == tid) & (T.book == book)].p_holm.iloc[0])
        c5 = ph <= 0.05
        res.append(dict(test=tid, book=book, sharpe_ok=c1, risk_ok=c2, loo_ok=c3, years_ok=c4, signif_ok=c5,
                        p_holm=ph, passes=c1 and c2 and c3 and c4 and c5))
    Rz = pd.DataFrame(res)
    if "A+B" in F:                                               # calendar must add value beyond B
        ab = F["A+B"]["cand"] + " vs " + F["B"]["cand"]
        for book in lab.BOOKS:
            a_ok = Rz[(Rz.test == F["A"]["cand"]) & (Rz.book == book)].passes.all()
            ab_ok = Rz[(Rz.test == ab) & (Rz.book == book)].passes.all()
            Rz.loc[(Rz.test == F["A"]["cand"]) & (Rz.book == book), "passes"] = bool(a_ok and ab_ok)
    # information only: uncapped multipliers and theta 0.25, holdout eras
    info = []
    for fam in ("A", "B", "C"):
        if fam not in F:
            continue
        for book in lab.BOOKS:
            for C in lab.CAPS:
                c = F[fam]["c"][f"{book}|{int(C)}"]
                for era in lab.HOLD:
                    for label, kw, kb in (("uncapped", dict(mult_cap=False), {}), ("theta 0.25", dict(theta=0.25),
                                                                                    dict(theta=0.25))):
                        dc, _, _ = era_series(F[fam]["rule"], book, C, era, c, mtm=False, **kw)
                        db, _, _ = era_series(None, book, C, era, None, mtm=False, **kb)
                        info.append(dict(cand=F[fam]["cand"], variant=label, book=book, capital=C, era=era,
                                         d_sharpe=lab.compare(dc, db, era)["d_sharpe"]))
    I = pd.DataFrame(info)
    S = score(F, X, Y, T, series)
    X.to_csv(os.path.join(OUT, "holdout_cells.csv"), index=False)
    Y.to_csv(os.path.join(OUT, "years.csv"), index=False)
    T.merge(Rz, on=["test", "book"]).to_csv(os.path.join(OUT, "tests.csv"), index=False)
    I.to_csv(os.path.join(OUT, "info.csv"), index=False)
    S.to_csv(os.path.join(OUT, "scorecard.csv"), index=False)
    write_summary(head, X, Y, T, Rz, I, S)
    mark_read(head)


def score(F, X, Y, T, series):
    rows = []
    for fam in ("A", "B", "C"):
        if fam not in F:
            continue
        cand = F[fam]["cand"]
        g = X[X.test == cand]
        hb = g[g.era.isin(lab.HOLD)]
        s250 = hb[hb.capital == 250e3].d_sharpe.mean()
        s1m = hb[hb.capital == 1e6].d_sharpe.mean()
        cr1m = hb[hb.capital == 1e6].capital_ratio.mean()
        pts = dict(sharpe=20 * np.clip(s250 / 0.40, 0, 1))
        pts["capacity"] = 10 * np.clip(s1m / 0.40, 0, 1) + 5 * np.clip(1 - abs(cr1m - 1) / 0.10, 0, 1)
        pts["consistency"] = 10 * float((g.d_sharpe >= 0.20 - TOL).mean())
        ph = T[T.test == cand].p_holm.to_numpy()
        pts["evidence"] = float(np.mean(15 * np.clip((0.20 - ph) / 0.15, 0, 1)))
        loo = float((hb.loo_min >= 0.20 - TOL).mean())
        top = []
        for book in lab.BOOKS:
            d = np.concatenate([series[(cand, book, 250e3, e)][2].to_numpy() - series[(cand, book, 250e3, e)][3].to_numpy()
                                for e in lab.HOLD])
            if d.sum() > 0:
                t5 = np.sort(d)[::-1][:5].sum() / d.sum()
                top.append(5 * np.clip((1 - t5) / 0.5, 0, 1))
            else:
                top.append(0.0)
        pts["spread"] = 5 * loo + float(np.mean(top))
        checks = np.concatenate([(g.maxdd >= g.maxdd_base - TOL).to_numpy(), (g.maxdd_mtm >= g.maxdd_mtm_base - TOL).to_numpy(),
                                 (g.worst >= g.worst_base - TOL).to_numpy(), (g.cvar5 >= g.cvar5_base - TOL).to_numpy()])
        yy = Y[Y.test == cand]
        pts["risk"] = 12 * float(checks.mean()) + (3.0 if (yy.ret > 0).all() else 0.0)
        mech, impl = HAND[cand]
        pts["mechanism"], pts["implementation"] = float(mech), float(impl)
        rows.append(dict(cand=cand, total=round(sum(pts.values()), 1), **{k: round(float(v), 2) for k, v in pts.items()},
                         mean_d_sharpe_250k=s250, mean_d_sharpe_1m=s1m, capital_ratio_1m=cr1m))
    return pd.DataFrame(rows)


def write_summary(head, X, Y, T, Rz, I, S):
    pd.set_option("display.width", 250)
    lines = [f"Sizing lab holdout, read once at commit {head}.", ""]
    lines.append("ΔSharpe against the baseline (rows: test, book; columns: capital, era):")
    lines.append(X.pivot_table(index=["test", "book"], columns=["capital", "era"], values="d_sharpe", sort=False).round(3)
                 .to_string())
    lines += ["", "Leave-one-day-out minimum ΔSharpe:"]
    lines.append(X.pivot_table(index=["test", "book"], columns=["capital", "era"], values="loo_min", sort=False).round(3)
                 .to_string())
    lines += ["", "Capital ratio (candidate / baseline average capital):"]
    lines.append(X.pivot_table(index=["test", "book"], columns=["capital", "era"], values="capital_ratio", sort=False)
                 .round(3).to_string())
    lines += ["", "Tests (pooled check + 2022-23, event-cluster bootstrap; IUT over capitals; Holm):"]
    lines.append(T.round(4).to_string(index=False))
    lines += ["", "Pass criteria:"]
    lines.append(Rz.to_string(index=False))
    lines += ["", "Calendar years (candidate return):"]
    lines.append(Y.pivot_table(index=["test", "book", "capital"], columns="year", values="ret", sort=False).round(4).to_string())
    lines += ["", "Information only (ΔSharpe vs flat):"]
    if len(I):
        lines.append(I.pivot_table(index=["cand", "variant", "book"], columns=["capital", "era"], values="d_sharpe")
                     .round(3).to_string())
    lines += ["", "Scorecard:"]
    lines.append(S.to_string(index=False))
    txt = "\n".join(lines) + "\n"
    with open(os.path.join(OUT, "holdout.txt"), "w") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
