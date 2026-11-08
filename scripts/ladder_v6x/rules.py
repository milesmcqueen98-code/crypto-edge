#!/usr/bin/env python3
"""Ladder v6 (exits): oracle bounds and the hold-or-sell rule family on the exit layer (exits.py), selection era.

Levers (prereg): X1 decides at minutes 0..59 with horizon 60; X2 at 60..119 with horizon 120; X12 at 0..119, horizon 120.
Rule: at each decision minute an open remainder is sold at that minute's close if the predicted gain from holding
(bp per remainder dollar: the realised value of continuing to the horizon with the take-profit resting, minus selling
now, net of costs) is below a hurdle h. Prediction: linear in up to 6 inputs known at the minute (FEATURES).
Every run is logged to reports/ladder_v6x/variants.csv (selection-era statistics only).
usage: python scripts/ladder_v6x/rules.py round1
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exits as X  # noqa: E402
from lsim import OUT, fsim  # noqa: E402

LEVERS = {"X1": (0, 60), "X2": (60, 120), "X12": (0, 120)}
VAR = os.path.join(OUT, "variants.csv")
ALL = ("mark", "rec", "k", "btc", "breadth", "m")
_CACHE = {}


def books(cfg, era, kappa, ext):
    key = (cfg, era, str(kappa), ext)
    if key not in _CACHE:
        if ("D", era) not in _CACHE:
            _CACHE[("D", era)] = X.Data(era)
        _CACHE[key] = X.books(cfg, era, _CACHE[("D", era)], kappa, ext)
    return _CACHE[key]


def feats(x, ms, inputs=ALL):
    cols = []
    for f in inputs:
        if f == "mark":
            v = x.C[:, ms]
        elif f == "rec":
            v = x.C[:, ms] / (x.g_tp / 0.6)[:, None]
        elif f == "k":
            v = np.repeat(x.k[:, None], len(ms), 1)
        elif f == "btc":
            v = np.nan_to_num(x.B[:, ms])
        elif f == "breadth":
            v = x.BR[:, ms].astype(float)
        elif f == "m":
            v = np.repeat(np.asarray(ms, float)[None, :], len(x.Q), 0)
        else:
            raise KeyError(f)
        cols.append(v)
    return np.stack(cols, -1)


def gain(x, lever):
    """Realised gain from holding (bp per remainder dollar) at each decision minute; NaN where nothing is open."""
    m0, H = LEVERS[lever]
    ms = np.arange(m0, H)
    R = x.R[:, ms]
    y = (x.VAL[:, [H]] - x.VAL[:, ms]) / np.where(R > 0, R, 1.0) * 1e4
    return np.where(R > 0, y, np.nan), ms


def fit(x, lever, rows, inputs=ALL, weights=None):
    """OLS (or WLS by remainder USD) of the gain on the inputs over the tranches in `rows` (bool)."""
    y, ms = gain(x, lever)
    F = feats(x, ms, inputs)
    ok = np.isfinite(y) & rows[:, None]
    A = np.column_stack([np.ones(ok.sum()), F[ok]])
    if weights == "usd":
        w = np.sqrt(x.R[:, ms][ok])
        beta = np.linalg.lstsq(A * w[:, None], y[ok] * w, rcond=None)[0]
    else:
        beta = np.linalg.lstsq(A, y[ok], rcond=None)[0]
    return beta, int(ok.sum())


def decide(x, lever, beta_rows, h, inputs=ALL):
    """Exit minute per tranche. beta_rows: per-tranche coefficient vector (NaN row = run the incumbent's exit)."""
    m0, H = LEVERS[lever]
    ms = np.arange(m0, H)
    F = feats(x, ms, inputs)
    pred = beta_rows[:, :1] + np.einsum("nmf,nf->nm", F, beta_rows[:, 1:])
    sell = (pred < h) & (x.R[:, ms] > 0)
    mx = np.where(sell.any(1), m0 + sell.argmax(1), H)
    return np.where(np.isfinite(beta_rows[:, 0]), mx, X.H0)


def oracle(lever):
    m0, H = LEVERS[lever]
    return lambda x: m0 + np.argmax(x.VAL[:, m0:H + 1], axis=1)


def quarters(x):
    return pd.PeriodIndex(x.Q.fill_t.dt.to_period("Q"))


def wf_betas(train, lever, inputs=ALL, weights=None, base_rows=None):
    """Walk-forward: coefficients per quarter fitted on tranches whose window ended before the quarter (plus
    base_rows, e.g. another era's tranches). Returns {quarter: beta or None}."""
    q = quarters(train)
    end = train.Q.fill_t + pd.Timedelta(minutes=X.HMAX + 1)
    out = {}
    for qq in sorted(q.unique()):
        rows = (end <= qq.start_time).to_numpy()
        if base_rows is not None:
            rows = rows | base_rows
        out[qq] = fit(train, lever, rows, inputs, weights)[0] if rows.any() else None
    return out


def beta_rows(x, betas, nf):
    q = quarters(x)
    B = np.full((len(x.Q), nf + 1), np.nan)
    for qq, b in betas.items():
        if b is not None:
            B[(q == qq)] = b
    return B


def run_rule(lever, kappa, h, betas, inputs=ALL, ext=None, cfg="S_0.5", era="sel"):
    """Daily series of the incumbent and the rule (betas: one vector, or {quarter: vector}) at cfg."""
    ext = (60 if lever != "X1" else 0) if ext is None else ext
    inc = X.blended(books(cfg, era, kappa, 0), X.at60)
    bk = books(cfg, era, kappa, ext)

    def rule(x):
        if isinstance(betas, dict):
            B = beta_rows(x, betas, len(inputs))
        else:
            B = np.tile(betas, (len(x.Q), 1))
        return decide(x, lever, B, h, inputs)
    cand = X.blended(bk, rule)
    if isinstance(betas, dict) and ext:
        first = min(q for q, b in betas.items() if b is not None)
        cand = cand.where(cand.index >= first.start_time, inc)       # incumbent quarters keep the incumbent's cash
    return inc, cand, bk, rule


def changed_share(bk, rule):
    x = bk["instant"]
    mx = rule(x)
    rem = x.R[np.arange(len(x.Q)), X.H0]
    moved = (mx != X.H0) & ((rem > 0) | (x.R[np.arange(len(x.Q)), np.minimum(mx, X.HMAX)] > 0))
    return float(moved.mean())


def log(row):
    row = dict(time_utc=pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), **row)
    new = not os.path.exists(VAR)
    df = pd.DataFrame([row])
    if not new:
        cols = pd.read_csv(VAR, nrows=0).columns.tolist()
        df = df.reindex(columns=cols + [c for c in df.columns if c not in cols])
    df.to_csv(VAR, mode="a", header=new, index=False)


def score(inc, cand, cfg="S_0.5", era="sel"):
    return X.compare(inc, cand, cfg, era)


def report_line(name, s, extra=""):
    return (f"{name:38s} t {s['t']:+6.2f}  dSharpe {s['d_sharpe']:+.3f}  dret {100 * s['d_ret']:+6.2f}pp  "
            f"mean {s['mean_bp']:+6.2f} bp/day  {extra}")


def round1():
    lines = []
    t0 = time.time()
    for kappa in (1.0, 2.0):
        for lever in ("X1", "X2", "X12"):
            if lever == "X2" and kappa == 2.0:
                continue                                    # X2's costs do not use kappa
            exts = (0,) if lever == "X1" else (60, 0)
            for ext in exts:
                inc = X.blended(books("S_0.5", "sel", kappa, 0), X.at60)
                bk = books("S_0.5", "sel", kappa, ext)
                rule = oracle(lever)
                cand = X.blended(bk, rule)
                s = score(inc, cand)
                name = f"oracle {lever} kappa{kappa:g} cash{ext}"
                lines.append(report_line(name, s, f"({time.time() - t0:.0f}s)"))
                print(lines[-1], flush=True)
                log(dict(round=1, name=name, lever=lever, kappa=kappa, cash=f"ext{ext}", fit="oracle", h=np.nan,
                         inputs="", weights="", **{f"sel_{k}": v for k, v in s.items()},
                         moved=changed_share(bk, rule), note="hindsight bound"))
            train = books("S_0.5", "sel", kappa, 0)["instant"]
            beta, nrow = fit(train, lever, np.ones(len(train.Q), bool))
            for h in (0.0, 5.0, 10.0):
                inc, cand, bk, rule = run_rule(lever, kappa, h, beta)
                s = score(inc, cand)
                name = f"insample {lever} kappa{kappa:g} h{h:g}"
                lines.append(report_line(name, s, f"rows {nrow} beta {np.round(beta, 3).tolist()}"))
                print(lines[-1], flush=True)
                log(dict(round=1, name=name, lever=lever, kappa=kappa, cash="ext60" if lever != "X1" else "ext0",
                         fit="insample", h=h, inputs="+".join(ALL), weights="ols",
                         **{f"sel_{k}": v for k, v in s.items()}, moved=changed_share(bk, rule),
                         note="drop-rule bound (fitted on the whole selection era)"))
    open(os.path.join(OUT, "round1.txt"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "round1":
        round1()


def family_bound(levers=("X1", "X12"), kappas=(1.0, 2.0)):
    """Drop rule: the best in-sample rule of the family (every subset of the inputs, h in {0, 5, 10})."""
    import itertools
    lines = []
    for kappa in kappas:
        for lever in levers:
            train = books("S_0.5", "sel", kappa, 0)["instant"]
            rows = np.ones(len(train.Q), bool)
            best = None
            for r in range(1, len(ALL) + 1):
                for sub in itertools.combinations(ALL, r):
                    beta, _ = fit(train, lever, rows, sub)
                    for h in (0.0, 5.0, 10.0):
                        inc, cand, bk, rule = run_rule(lever, kappa, h, beta, sub)
                        s = score(inc, cand)
                        log(dict(round=1, name=f"family {lever} kappa{kappa:g} h{h:g} {'+'.join(sub)}", lever=lever,
                                 kappa=kappa, cash="ext60" if lever != "X1" else "ext0", fit="insample-family", h=h,
                                 inputs="+".join(sub), weights="ols", **{f"sel_{k}": v for k, v in s.items()},
                                 moved=np.nan, note="drop-rule bound over the family"))
                        if best is None or s["t"] > best[0]["t"]:
                            best = (s, sub, h)
            s, sub, h = best
            lines.append(report_line(f"family best {lever} kappa{kappa:g}", s, f"h {h:g} inputs {'+'.join(sub)}"))
            print(lines[-1], flush=True)
    open(os.path.join(OUT, "round1.txt"), "a").write("\n".join(lines) + "\n")


if __name__ == "__main__" and sys.argv[1] == "family":
    family_bound()


def hold_all(lever):
    H = LEVERS[lever][1]
    return lambda x: np.full(len(x.Q), H)


def run_round(rnd, specs, kappa=1.0, cfg="S_0.5"):
    """specs: (name, lever, inputs, h, weights, fit) with fit 'wf' (walk-forward) or 'insample'."""
    lines = []
    train = books("S_0.5", "sel", kappa, 0)["instant"]
    for name, lever, inputs, h, weights, fitk in specs:
        if fitk == "hold":
            inc = X.blended(books(cfg, "sel", kappa, 0), X.at60)
            bk = books(cfg, "sel", kappa, 60)
            rule = hold_all(lever)
            cand = X.blended(bk, rule)
            betas = None
        else:
            if fitk == "wf":
                betas = wf_betas(train, lever, inputs, weights)
            else:
                betas = fit(train, lever, np.ones(len(train.Q), bool), inputs, weights)[0]
            inc, cand, bk, rule = run_rule(lever, kappa, h, betas, inputs, cfg=cfg)
        s = score(inc, cand, cfg)
        lines.append(report_line(name, s))
        print(lines[-1], flush=True)
        log(dict(round=rnd, name=name, lever=lever, kappa=kappa, cash="ext60" if lever != "X1" else "ext0", fit=fitk,
                 h=h, inputs="+".join(inputs), weights=weights or "ols", cfg=cfg,
                 **{f"sel_{k}": v for k, v in s.items()}, moved=changed_share(bk, rule), note=""))
    open(os.path.join(OUT, f"round{rnd}.txt"), "a").write("\n".join(lines) + "\n")
    return lines


ROUND2 = [("R2 hold-all-to-120 (reference)", "X2", (), np.nan, None, "hold")] + [
    (f"R2 X2 wf {'+'.join(inp)} h{h:g}", "X2", inp, h, None, "wf")
    for inp in (ALL, ("rec",), ("rec", "m")) for h in (0.0, 5.0, 10.0)]

if __name__ == "__main__" and sys.argv[1] == "round2":
    run_round(2, ROUND2)


ROUND3 = [(f"R3 X2 wf {'+'.join(inp)} h{h:g}", "X2", inp, h, None, "wf")
          for inp in (("breadth",), ("breadth", "mark"), ("breadth", "rec")) for h in (0.0, 5.0, 10.0)]

if __name__ == "__main__" and sys.argv[1] == "round3":
    run_round(3, ROUND3)


ROUND4 = ([(f"R4 X2 wf all6 WLS h{h:g}", "X2", ALL, h, "usd", "wf") for h in (0.0, 5.0, 10.0)]
          + [(f"R4 X2 wf mark+rec+breadth {w or 'OLS'} h{h:g}", "X2", ("mark", "rec", "breadth"), h, w, "wf")
             for w in (None, "usd") for h in (0.0, 5.0, 10.0)])

if __name__ == "__main__" and sys.argv[1] == "round4":
    run_round(4, ROUND4)
