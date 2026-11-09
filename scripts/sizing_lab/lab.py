#!/usr/bin/env python3
"""Sizing lab (reports/sizing_lab/prereg.md): calendar (A), predicted-edge (B) and guard (C) sizing for the R2-08 spot
ladder's main and W2 books, run through scripts/wick_v4/rungs.py with spot-only capacity and the simulator's costs.

  python scripts/sizing_lab/lab.py select     # selection era only: every candidate -> variants.csv, finalists.json
  python scripts/sizing_lab/lab.py holdout    # once, after the freeze commit: check + 2022-23 -> holdout files

Definitions follow the pre-registration; the comments name the section they implement.
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
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick_v4"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import sim  # noqa: E402
import rungs  # noqa: E402
from edge import book as edge_book  # noqa: E402  (sim puts the repo root on the path)

OUT = os.path.join(ROOT, "reports", "sizing_lab")
BOOKS = {"main": rungs.W["W0"], "W2": rungs.W["W2"]}
CAPS = (250e3, 1e6)
THETA = 0.5
ERAS = {"selection": ("main", sim.SEL), "check": ("main", sim.CHK), "y2022_23": ("early", sim.EARLY)}
HOLD = ("check", "y2022_23")
KAPPA, PER_TRADE, H = 0.002, 0.25, 60
MIN_N, MIN_CL, NU0 = 30, 10, 30
GAP_H, TAIL_H = 6, 2
LO_M, HI_M = 0.5, 1.5
FAMILY = {"A1": "A", "A2": "A", "A3": "A", "B1": "B", "B2": "B", "B3": "B", "C1": "C", "C2": "C", "C3": "C"}
NB = {"A1": 7, "A2": 2, "A3": 2, "B1": 2, "B2": 3, "B3": 5}


# ------------------------------------------------------------------------------------------------ data and features
_D = {}


def data(tag):
    """Precomputed tranches with spot-only capacity, and the R2-08 trade list."""
    if tag not in _D:
        D = pd.read_pickle(os.path.join(ROOT, "reports", "wick1m", f"pre_v4_{tag}.pkl"))
        D["in_perp"] = 0.0
        D["tp_perp"] = 0.0
        T = pd.read_parquet(os.path.join(ROOT, "reports", "wick1m", f"trades_{tag}.parquet"))
        T = T.sort_values("ts").reset_index(drop=True)
        T["x"] = T.pred / T.thr
        _D[tag] = (D, T)
    return _D[tag]


def btc(tag):
    src = "minute" if tag == "main" else "minute_early"
    b = pd.read_parquet(os.path.join(ROOT, "data", src, "BTC.parquet")).drop_duplicates("ts").set_index("ts").sort_index()
    idx = pd.date_range(b.index.min().floor("D"), b.index.max().ceil("D"), freq="min", inclusive="left")
    c = b.close.reindex(idx).ffill()
    r = np.log(c).diff().fillna(0.0)
    sd24 = r.rolling(1440, min_periods=720).std()                       # std of the 1440 returns ending at m
    rv24 = np.sqrt((r ** 2).rolling(1440, min_periods=720).sum())       # realized vol of the 24 h ending at m
    daily = np.sqrt((r ** 2).resample("D").sum())
    thr = 2.0 * daily.rolling(365, min_periods=180).median().shift(1)   # 2 x median of the previous 365 days
    return r, sd24, rv24, thr


_F = {}


def features(tag):
    """Per-signal features (index: ts, coin) and the C1 row guard (index: ts, coin, k)."""
    if tag in _F:
        return _F[tag]
    D, T = data(tag)
    par = D[D.k == 4.0][["ts", "coin", "adv"]].drop_duplicates(["ts", "coin"]).sort_values("ts").reset_index(drop=True)
    et = par.ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    macro = set(pd.read_csv(os.path.join(OUT, "macro_days.csv")).date_et)
    par["dow"] = et.dt.dayofweek                                       # 0 Monday ... 6 Sunday
    par["sun"] = ((et.dt.dayofweek == 6) & (et.dt.hour >= 16) & (et.dt.hour < 19)).astype(int)
    par["macro"] = et.dt.strftime("%Y-%m-%d").isin(macro).astype(int)
    par = par.merge(T[["ts", "coin", "x"]], on=["ts", "coin"], how="left")
    # B: rank of x among the R2-08 signals of the previous 90 days (strictly before)
    tts, tx, tcoin = T.ts.to_numpy(), T.x.to_numpy(), T.coin.to_numpy()
    n_tr, q = np.zeros(len(par), int), np.full(len(par), np.nan)
    breadth = np.zeros(len(par), int)
    for i, (ts, x, coin) in enumerate(zip(par.ts, par.x, par.coin)):
        a = np.searchsorted(tts, np.datetime64(ts - pd.Timedelta(days=90)), "left")
        b = np.searchsorted(tts, np.datetime64(ts), "left")
        n_tr[i] = b - a
        if b - a >= MIN_N and np.isfinite(x):
            q[i] = float(np.mean(tx[a:b] < x))
        a2 = np.searchsorted(tts, np.datetime64(ts - pd.Timedelta(minutes=30)), "left")
        breadth[i] = len(set(tcoin[a2:b]) - {coin})                    # other coins, minutes t-30 ... t-1
    par["n_trail"], par["q"], par["breadth"] = n_tr, q, breadth
    for K in (2, 3, 5):
        par[f"bq{K}"] = np.where(np.isfinite(q), np.minimum(np.floor(np.nan_to_num(q) * K), K - 1), np.nan)
    r, sd24, rv24, thr = btc(tag)
    m_prev = par.ts - pd.Timedelta(minutes=1)
    par["rv24"] = rv24.reindex(m_prev).to_numpy()
    par["rv_thr"] = thr.reindex(par.ts.dt.floor("D")).to_numpy()
    par["c2"] = (par.breadth >= 3).astype(int)
    par["c3"] = (np.nan_to_num(par.rv24) > np.nan_to_num(par.rv_thr, nan=np.inf)).astype(int)
    # C1: a deeper rung filling in minute j is skipped when BTC's return over minute j-1 < -1 x its 24 h std
    rows = D[(D.k > 4.0) & D.filled & (D.f_off >= 1)][["ts", "coin", "k", "f_off"]].copy()
    j1 = rows.ts + pd.to_timedelta(rows.f_off - 1, unit="m")
    rows["c1"] = (r.reindex(j1).to_numpy() < -sd24.reindex(j1).to_numpy()).astype(int)
    sig = par.set_index(["ts", "coin"])
    row = rows.set_index(["ts", "coin", "k"]).c1
    _F[tag] = (sig, row)
    return _F[tag]


def bucket(cand, sig):
    """Bucket label per signal for families A and B (NaN = not bucketed: m = 1)."""
    if cand == "A1":
        return sig.dow.astype(float)
    if cand == "A2":
        return sig.sun.astype(float)
    if cand == "A3":
        return sig.macro.astype(float)
    return sig[{"B1": "bq2", "B2": "bq3", "B3": "bq5"}[cand]]


# ------------------------------------------------------------------------------------------------ runs
_RUN = {}


def run(book, C, era, mult=None, mtm=False, key=None, mult_cap=True, theta=THETA):
    """rungs.run on the era with spot-only capacity; returns (daily returns, Q, info, stats). Cached by key."""
    k = (book, C, era, key, mtm, mult_cap, theta)
    if key is not None and k in _RUN:
        return _RUN[k]
    tag, (lo, hi) = ERAS[era]
    D, _ = data(tag)
    out = {}
    st, d = rungs.run(D, BOOKS[book], lo, hi, theta, C, True, mtm=mtm, mult=mult, mult_cap=mult_cap, out=out)
    res = (d, out["Q"], out["info"], st)
    if key is not None:
        _RUN[k] = res
    return res


def exposure(Q):
    """Position dollar-minutes: take-profit parts held until the take-profit, the rest 60 minutes."""
    tp = Q.tp_fill.to_numpy()
    return float(np.sum(tp * np.maximum(Q.tp_off.to_numpy(), 0)) + np.sum((Q.fill.to_numpy() - tp) * H))


def signal_returns(Q, C):
    """Per-signal P&L over the flat size min(25% C, 0.2% ADV)."""
    par = Q[Q.k == 4.0].set_index(["ts", "coin"])
    S = np.minimum(PER_TRADE * C, KAPPA * par.adv.fillna(0.0))
    pnl = Q.groupby(["ts", "coin"]).pnl.sum().reindex(par.index)
    out = pd.DataFrame({"pnl": pnl, "S": S})
    out = out[out.S > 0]
    return out.pnl / out.S


def clusters(era):
    """Event clusters of the era's R2-08 parents (prereg 'Units and statistics'): signal -> cluster id, and the
    bootstrap units as lists of day positions."""
    tag, (lo, hi) = ERAS[era]
    sig, _ = features(tag)
    ts = sig.index.get_level_values(0)
    m = (ts >= pd.Timestamp(lo)) & (ts < pd.Timestamp(hi) + pd.Timedelta(days=1))
    s = sig[m].sort_index(level=0)
    t = s.index.get_level_values(0)
    cid = np.zeros(len(s), int)
    spans = []
    for i in range(len(s)):
        if i == 0 or (t[i] - t[i - 1]) > pd.Timedelta(hours=GAP_H):
            spans.append([t[i].floor("D"), (t[i] + pd.Timedelta(hours=TAIL_H)).floor("D")])
        else:
            spans[-1][1] = max(spans[-1][1], (t[i] + pd.Timedelta(hours=TAIL_H)).floor("D"))
        cid[i] = len(spans) - 1
    merged, remap = [], {}
    for j, (a, b) in enumerate(spans):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
        remap[j] = len(merged) - 1
    cl = pd.Series([remap[c] for c in cid], index=s.index)
    days = pd.date_range(lo, hi, freq="D")
    pos = {d: i for i, d in enumerate(days)}
    covered, units = set(), []
    for a, b in merged:
        u = [pos[d] for d in pd.date_range(a, min(b, days[-1]), freq="D") if d in pos]
        covered.update(u)
        units.append(u)
    units += [[i] for i in range(len(days)) if i not in covered]
    return cl, units


# ------------------------------------------------------------------------------------------------ multipliers
def shrink(r, b, cl):
    """Shrunk mu / sigma^2 per bucket, relative to the pool (prereg 'Shrinkage', 'Multiplier')."""
    df = pd.DataFrame({"r": r, "b": b, "cl": cl}).dropna(subset=["r", "b"])
    mu0, s20 = df.r.mean(), df.r.var(ddof=1)
    rows = []
    for bb, g in df.groupby("b"):
        n, mu, s2 = len(g), g.r.mean(), g.r.var(ddof=1)
        e = (g.r - mu).groupby(g.cl).sum()
        rows.append(dict(bucket=bb, n=n, clusters=int(g.cl.nunique()), mu=mu, s2=s2, se2=float((e ** 2).sum() / n ** 2)))
    S = pd.DataFrame(rows)
    tau2 = max(0.0, float(S.mu.var(ddof=1)) - float(S.se2.mean())) if len(S) > 1 else 0.0
    S["w"] = tau2 / (tau2 + S.se2) if tau2 > 0 else 0.0
    S["mu_s"] = mu0 + S.w * (S.mu - mu0)
    S["s2_s"] = (S.n * S.s2 + NU0 * s20) / (S.n + NU0)
    S["g"] = (S.mu_s / S.s2_s) / (mu0 / s20)
    S["tau2"], S["mu_pool"], S["s2_pool"] = tau2, mu0, s20
    return S


def sig_mult(m_sig, row_zero=None):
    """mult function for sim.evaluate: per-signal multipliers (index ts, coin), rows in row_zero set to 0."""
    def f(Q):
        mi = pd.MultiIndex.from_arrays([Q.ts.to_numpy(), Q.coin.to_numpy()])
        m = m_sig.reindex(mi).to_numpy(dtype=np.float64)
        if np.isnan(m).any():
            raise ValueError("signal without a multiplier")
        if row_zero is not None:
            mi3 = pd.MultiIndex.from_arrays([Q.ts.to_numpy(), Q.coin.to_numpy(), Q.k.to_numpy()])
            z = row_zero.reindex(mi3).fillna(0).to_numpy() > 0
            m = np.where(z, 0.0, m)
        return m
    return f


def rule_mult(rule, book, tag, c):
    """The rule's mult function on a data tag. rule: dict(kind='bucket'|'guard'|'overlay', ...), see build_rule."""
    sig, rowg = features(tag)
    if rule["kind"] == "bucket":
        g = rule_g(rule, book, sig)
        m = pd.Series(np.where(np.isnan(g), 1.0, np.clip(c * np.nan_to_num(g), LO_M, HI_M)), index=sig.index)
        return sig_mult(m)
    if rule["kind"] == "overlay":
        ga = rule_g(rule["a"], book, sig)
        gb = rule_g(rule["b"], book, sig)
        g = np.where(np.isnan(ga), 1.0, ga) * np.where(np.isnan(gb), 1.0, gb)
        m = pd.Series(np.clip(c * g, LO_M, HI_M), index=sig.index)
        return sig_mult(m)
    name = rule["cand"]                                                   # guards
    if name == "C1":
        return sig_mult(pd.Series(c, index=sig.index), rowg)
    fire = sig[{"C2": "c2", "C3": "c3"}[name]].to_numpy() > 0
    return sig_mult(pd.Series(np.where(fire, 0.0, c), index=sig.index))


def rule_g(rule, book, sig):
    """Relative Kelly g per signal from the rule's frozen bucket table (NaN where not bucketed)."""
    gmap = {float(k): v for k, v in rule["g"][book].items()}
    b = bucket(rule["cand"], sig).to_numpy()
    return np.array([gmap.get(float(x), 1.0) if np.isfinite(x) else np.nan for x in b])


def match_c(rule, book, C, base_exposure):
    """c so that the selection-era average capital equals the baseline's (prereg 'Same average capital')."""
    tag = ERAS["selection"][0]

    def expo(c):
        _, Q, _, _ = run(book, C, "selection", mult=rule_mult(rule, book, tag, c))
        return exposure(Q)

    if rule["kind"] == "guard":
        lo, hi = 1.0, HI_M
        if expo(hi) <= base_exposure:
            return hi, expo(hi) / base_exposure
        if expo(lo) >= base_exposure:
            return lo, expo(lo) / base_exposure
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            if expo(mid) < base_exposure:
                lo = mid
            else:
                hi = mid
        c = 0.5 * (lo + hi)
        return c, expo(c) / base_exposure
    lo, hi = math.log(0.02), math.log(50.0)
    if expo(math.exp(hi)) <= base_exposure:
        return math.exp(hi), expo(math.exp(hi)) / base_exposure
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if expo(math.exp(mid)) < base_exposure:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-4:
            break
    c = math.exp(0.5 * (lo + hi))
    return c, expo(c) / base_exposure


# ------------------------------------------------------------------------------------------------ metrics
def sharpe(e):
    s = e.std(ddof=1)
    return float(e.mean() / s * math.sqrt(365)) if s > 0 else float("nan")


def loo_min(ec, eb):
    """Smallest ΔSharpe with any single day removed."""
    def loo(e):
        n = len(e)
        s1, s2 = e.sum(), (e ** 2).sum()
        m = (s1 - e) / (n - 1)
        v = (s2 - e ** 2 - (n - 1) * m ** 2) / (n - 2)
        return m / np.sqrt(v) * math.sqrt(365)
    return float(np.min(loo(ec) - loo(eb)))


def maxdd(r):
    eq = np.cumprod(1 + r)
    return float(np.min(eq / np.maximum.accumulate(eq) - 1))


def cvar5(r):
    k = max(1, int(math.ceil(0.05 * len(r))))
    return float(np.sort(r)[:k].mean())


def compare(dc, db, era):
    """Candidate vs baseline daily returns on one era."""
    lo, hi = ERAS[era][1]
    idx = pd.date_range(lo, hi, freq="D")
    rf = edge_book.rf_daily(idx).to_numpy()
    rc, rb = dc.reindex(idx, fill_value=0.0).to_numpy(), db.reindex(idx, fill_value=0.0).to_numpy()
    ec, eb = rc - rf, rb - rf
    d = rc - rb
    top = np.argsort(d)[::-1][:5]
    keep = np.ones(len(d), bool)
    keep[top] = False
    yrs = len(idx) / 365.25
    return dict(ret_yr=float(rc.sum() / yrs), ret_yr_base=float(rb.sum() / yrs), sharpe=sharpe(ec), sharpe_base=sharpe(eb),
                d_sharpe=sharpe(ec) - sharpe(eb), d_sharpe_ex5=sharpe(ec[keep]) - sharpe(eb[keep]),
                top5_share=float(d[top].sum() / d.sum()) if d.sum() > 0 else float("nan"),
                loo_min=loo_min(ec, eb), maxdd=maxdd(rc), maxdd_base=maxdd(rb), worst=float(rc.min()),
                worst_base=float(rb.min()), cvar5=cvar5(rc), cvar5_base=cvar5(rb))


# ------------------------------------------------------------------------------------------------ selection
def build_rule(cand, book, rule=None):
    """Bucket table (g per bucket, from the book's flat $250K selection run) and testability."""
    tag = ERAS["selection"][0]
    sig, rowg = features(tag)
    d, Q, _, _ = run(book, 250e3, "selection", key="flat")
    r = signal_returns(Q, 250e3)
    cl, _ = clusters("selection")
    if FAMILY[cand] in ("A", "B"):
        b = bucket(cand, sig).reindex(r.index)
        S = shrink(r, b, cl.reindex(r.index))
        testable = bool((S.n >= MIN_N).all() and (S.clusters >= MIN_CL).all() and len(S) == NB[cand])
        return dict(kind="bucket", cand=cand, g={book: {str(float(k)): float(v) for k, v in zip(S.bucket, S.g)}}), S, testable
    if cand == "C1":
        rows = rowg[rowg > 0].reset_index()
        rows = rows[rows.set_index(["ts", "coin"]).index.isin(r.index)]
        fire = pd.Series(1, index=pd.MultiIndex.from_frame(rows[["ts", "coin"]].drop_duplicates()))
    else:
        f = sig[{"C2": "c2", "C3": "c3"}[cand]].reindex(r.index)
        fire = f[f > 0]
    fb = pd.Series(r.index.isin(fire.index).astype(float), index=r.index)
    S = shrink(r, fb, cl.reindex(r.index))                     # information: the firing set against the rest
    fs = S[S.bucket == 1.0]
    testable = bool(len(fs) and int(fs.n.iloc[0]) >= MIN_N and int(fs.clusters.iloc[0]) >= MIN_CL)
    return dict(kind="guard", cand=cand), S, testable


def merge_g(rules):
    out = dict(rules[0])
    if out["kind"] == "bucket":
        out["g"] = {}
        for r in rules:
            out["g"].update(r["g"])
    return out


def select():
    os.makedirs(OUT, exist_ok=True)
    rows, btabs, rules = [], [], {}
    flat = {(b, C): run(b, C, "selection", key="flat") for b in BOOKS for C in CAPS}
    for cand in FAMILY:
        built = {b: build_rule(cand, b) for b in BOOKS}
        testable = all(t for _, _, t in built.values())
        for b, (_, S, _) in built.items():
            btabs.append(S.assign(cand=cand, book=b))
        rule = merge_g([built[b][0] for b in BOOKS])
        rules[cand] = dict(rule=rule, testable=testable, c={})
        if not testable:
            rows.append(dict(cand=cand, family=FAMILY[cand], status="skipped: bucket too small to test"))
            continue
        for b in BOOKS:
            for C in CAPS:
                d0, Q0, _, _ = flat[(b, C)]
                c, ratio = match_c(rule, b, C, exposure(Q0))
                rules[cand]["c"][f"{b}|{int(C)}"] = c
                d1, Q1, _, _ = run(b, C, "selection", mult=rule_mult(rule, b, "main", c))
                m = compare(d1, d0, "selection")
                rows.append(dict(cand=cand, family=FAMILY[cand], status="run", book=b, capital=C, era="selection",
                                 baseline="flat", c=c, capital_ratio=ratio, **m))
                print(f"{cand} {b:4s} ${C / 1e3:,.0f}K c {c:6.3f} cap {ratio:5.3f}  dSharpe {m['d_sharpe']:+.3f} "
                      f"(ex5 {m['d_sharpe_ex5']:+.3f}, LOO min {m['loo_min']:+.3f})", flush=True)
    V = pd.DataFrame(rows)
    # family best: highest mean selection dSharpe over the four cells (ties: fewer buckets)
    fin = {}
    for fam in ("A", "B", "C"):
        g = V[(V.family == fam) & (V.status == "run")]
        if not len(g):
            continue
        sc = g.groupby("cand").d_sharpe.mean()
        nb = {k: NB.get(k, 1) for k in sc.index}
        best = sorted(sc.index, key=lambda k: (-round(sc[k], 12), nb[k]))[0]
        fin[fam] = best
    # calendar on top of B (prereg 'Calendar on top of B'), against B
    if "A" in fin and "B" in fin:
        a, bcand = rules[fin["A"]]["rule"], rules[fin["B"]]["rule"]
        ov = dict(kind="overlay", cand=f"{fin['A']}+{fin['B']}", a=a, b=bcand)
        rules[ov["cand"]] = dict(rule=ov, testable=True, c={})
        for b in BOOKS:
            for C in CAPS:
                d0, Q0, _, _ = flat[(b, C)]
                c, ratio = match_c(ov, b, C, exposure(Q0))
                rules[ov["cand"]]["c"][f"{b}|{int(C)}"] = c
                d1, _, _, _ = run(b, C, "selection", mult=rule_mult(ov, b, "main", c))
                cb = rules[fin["B"]]["c"][f"{b}|{int(C)}"]
                dB, _, _, _ = run(b, C, "selection", mult=rule_mult(bcand, b, "main", cb))
                for base, db in (("flat", d0), (fin["B"], dB)):
                    m = compare(d1, db, "selection")
                    rows.append(dict(cand=ov["cand"], family="A+B", status="run", book=b, capital=C, era="selection",
                                     baseline=base, c=c, capital_ratio=ratio, **m))
                    print(f"{ov['cand']} vs {base} {b:4s} ${C / 1e3:,.0f}K c {c:6.3f} cap {ratio:5.3f}  dSharpe "
                          f"{m['d_sharpe']:+.3f}", flush=True)
        fin["A+B"] = ov["cand"]
    V = pd.DataFrame(rows)
    V.to_csv(os.path.join(OUT, "variants.csv"), index=False)
    pd.concat(btabs).to_csv(os.path.join(OUT, "buckets.csv"), index=False)
    frozen = {fam: dict(cand=k, **rules[k]) for fam, k in fin.items()}
    with open(os.path.join(OUT, "finalists.json"), "w") as f:
        json.dump(dict(finalists=frozen, all_rules={k: v for k, v in rules.items()}), f, indent=1, default=float)
    summarize_selection(V, fin)


def summarize_selection(V, fin):
    r = V[V.status == "run"]
    lines = ["Selection era (Jan 2025 - Mar 2026), ADV-capped multipliers, capital-matched to flat.", ""]
    piv = r[r.baseline == "flat"].pivot_table(index="cand", columns=["book", "capital"], values="d_sharpe")
    lines.append("dSharpe vs flat (book, capital):")
    lines.append(piv.round(3).to_string())
    lines.append("")
    lines.append("Mean over the four cells: " + ", ".join(f"{k} {v:+.3f}" for k, v in
                                                        r[r.baseline == "flat"].groupby("cand").d_sharpe.mean().items()))
    sk = V[V.status != "run"]
    if len(sk):
        lines.append("Skipped: " + ", ".join(f"{a} ({s})" for a, s in zip(sk.cand, sk.status)))
    lines.append("Finalists: " + ", ".join(f"{k}: {v}" for k, v in fin.items()))
    txt = "\n".join(lines) + "\n"
    with open(os.path.join(OUT, "selection.txt"), "w") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select()
    elif sys.argv[1] == "holdout":
        import holdout  # noqa: F401  (scripts/sizing_lab/holdout.py, written after the freeze)
        holdout.main()
