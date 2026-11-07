#!/usr/bin/env python3
"""Edge hunt: the pre-registered pass tests (reports/hunt_prereg.md). Every builder imports this module; nobody
re-implements a test.

Conventions
- Daily returns on capital, indexed by calendar day (UTC), P&L booked on the exit day; idle days are 0.
- Sharpe = annualised (sqrt 365) mean / std of daily returns ABOVE T-bills (edge.book.rf_daily), as in every earlier
  round.
- Windows: DEV = every evaluation day before 2026-06-01; HOLD = 2026-06-01 .. 2026-11-05 (read once per idea).
  The incumbent only has out-of-sample days in 2022-2023 and 2025-01-01 .. 2026-11-05, so those are the
  evaluation days (2024 may be used to train models, never to score).
- Incumbent = the spot bot at its capital, "instant" bound (all same-minute deeper fills kept) - the stronger bound,
  so every comparison is conservative. reports/hunt/incumbent_daily.parquet.
- Candidates are scored at 2x their realistic cost model; the incumbent stays at 1x.

Path A (replace R2-08): candidate scaled to the incumbent's DEV volatility; HAC t of the daily difference.
Path B (add a sleeve): book = a * incumbent(a * $100K) + (1 - a) * sleeve((1 - a) * $100K), a in A_GRID chosen on DEV
  by book Sharpe; spanning test = HAC t of the sleeve's alpha on the incumbent.
Gates (all must hold): G1 t >= 3 (full window); G2 HOLD t >= 1.5 with the same sign and HOLD Sharpe gain >= 0.25
  (Path B) / HOLD Sharpe above the incumbent's (Path A); G3 full-window Sharpe gain >= 0.5 (Path B) / candidate Sharpe
  above the incumbent's (Path A); G4 deflated Sharpe >= 0.95 with N = 3000 + every trial in reports/hunt/trials.csv;
  G5 no losing calendar year for the book; G6 red team clean (recorded separately).
"""
import fcntl
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from edge import book  # noqa: E402

HOLD0 = pd.Timestamp("2026-06-01")
END = pd.Timestamp("2026-11-05")
ERA_DAYS = pd.DatetimeIndex(list(pd.date_range("2022-01-01", "2023-12-31", freq="D")) +
                            list(pd.date_range("2025-01-01", END, freq="D")))
N_PRIOR = 3000
VZ_FLOOR = 1.1257       # variance of z = daily Sharpe * sqrt(days) across the wick v2 lab's 139 trials (455 days)
A_GRID = (1.0, 0.7, 0.5)
LAGS = 5
# One ledger for every builder: the main clone's copy when it exists (builders work in sparse worktrees).
_MAIN_LEDGER = "/home/claude/crypto-edge/reports/hunt/trials.csv"
LEDGER = os.environ.get("HUNT_LEDGER") or (_MAIN_LEDGER if os.path.isdir(os.path.dirname(_MAIN_LEDGER))
                                           else os.path.join(ROOT, "reports", "hunt", "trials.csv"))
INC = os.path.join(ROOT, "reports", "hunt", "incumbent_daily.parquet")


# ------------------------------------------------------------------ basics
def excess(r):
    r = pd.Series(r).astype(float)
    return r - book.rf_daily(r.index).to_numpy()


def sharpe(r):
    x = excess(r)
    s = x.std()
    return float(x.mean() / s * math.sqrt(365)) if s > 0 else float("nan")


def nw_var(x, lags=LAGS):
    """Newey-West (Bartlett) long-run variance of x (demeaned)."""
    x = np.asarray(x, float)
    x = x - x.mean()
    n = len(x)
    v = np.dot(x, x) / n
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * np.dot(x[k:], x[:-k]) / n
    return v


def hac_t(x, lags=LAGS):
    x = np.asarray(x, float)
    v = nw_var(x, lags)
    return float(x.mean() / math.sqrt(v / len(x))) if v > 0 else float("nan")


def alpha_test(rs, ri, lags=LAGS):
    """OLS of sleeve excess return on incumbent excess return with a HAC (Newey-West) covariance.
    Returns alpha (annualised), beta, HAC t of alpha, appraisal ratio (annualised alpha / residual std)."""
    y, x = excess(rs).to_numpy(), excess(ri).to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    n = len(y)
    XtX_inv = np.linalg.inv(X.T @ X)
    S = np.zeros((2, 2))
    Xe = X * e[:, None]
    S += Xe.T @ Xe
    for k in range(1, lags + 1):
        w = 1 - k / (lags + 1)
        G = Xe[k:].T @ Xe[:-k]
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv
    se_a = math.sqrt(cov[0, 0]) if cov[0, 0] > 0 else float("nan")
    ar = b[0] / e.std() * math.sqrt(365) if e.std() > 0 else float("nan")
    return dict(alpha_yr=float(b[0] * 365), beta=float(b[1]), t_alpha=float(b[0] / se_a), appraisal=float(ar), n=n)


def deflated_sharpe(r, n_trials, vz):
    """Bailey & Lopez de Prado (2014): P(true Sharpe > expected max of n_trials null trials). r: daily returns.
    vz: variance of the trials' standardised Sharpe z = daily Sharpe * sqrt(days) (1 under the null of no skill and
    pure sampling noise). The null dispersion of a daily Sharpe over this track record's T days is vz / T, so every
    trial is put on this record's length whatever window it was scored on."""
    x = excess(r).to_numpy()
    T = len(x)
    v_trials = vz / T
    sr = x.mean() / x.std()
    g3 = float(pd.Series(x).skew())
    g4 = float(pd.Series(x).kurt()) + 3
    em = 0.5772156649
    sr0 = math.sqrt(v_trials) * ((1 - em) * norm.ppf(1 - 1 / n_trials) + em * norm.ppf(1 - 1 / (n_trials * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return float(norm.cdf(z)), float(sr0 * math.sqrt(365))


def years(r):
    r = pd.Series(r)
    return r.groupby(r.index.year).sum()


# ------------------------------------------------------------------ incumbent
def incumbent(capital=100e3, theta=0.5, variant="instant", days=None):
    """Daily returns of the incumbent at `capital` over ERA_DAYS (2022-23 and 2025-01-01 .. 2026-11-05)."""
    D = pd.read_parquet(INC)
    parts = []
    for era in ("early", "sel", "chk"):
        col = f"{era}|{int(capital)}|{theta}|{variant}"
        parts.append(D[col].dropna())
    s = pd.concat(parts).sort_index()
    s = s[~s.index.duplicated()].reindex(ERA_DAYS).fillna(0.0)
    return s if days is None else s.reindex(days).fillna(0.0)


# ------------------------------------------------------------------ trial ledger
def log_trial(idea, variant, r, note="", stage="dev", **extra):
    """Append one trial to the shared ledger (file-locked). r: daily returns of the BOOK or candidate scored
    (dev window only during the dev stage). Every configuration evaluated counts, including failures."""
    r = pd.Series(r).dropna()
    row = dict(time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), idea=idea, variant=variant, stage=stage,
               n_days=len(r), daily_sr=float(excess(r).mean() / excess(r).std()) if excess(r).std() > 0 else np.nan,
               sharpe=sharpe(r) if len(r) > 2 else np.nan, note=note, extra=json.dumps(extra, default=str))
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        new = f.read() == ""
        pd.DataFrame([row]).to_csv(f, header=new, index=False)
        fcntl.flock(f, fcntl.LOCK_UN)
    return row


def n_trials(robust=True):
    """N = 3000 prior + every trial in the ledger, and the null dispersion vz of the trials' z = daily SR x sqrt(days).

    robust=True / "within" (binding, deviation of 2026-11-07 06:35 UTC): z is demeaned within each idea (minus the
      idea's median), then vz = max(lab floor, (1.4826 x MAD)^2). Ledger trials are DEV books that contain the
      incumbent, whose true Sharpe makes z scale with sqrt(days); pooling ideas scored on different day counts measures
      record length, not selection noise.
    "pooled": the 06:00 UTC rule, MAD of z pooled across ideas (reported alongside).
    robust=False / "plain": the pre-registered plain variance (reported alongside)."""
    mode = {True: "within", False: "plain"}.get(robust, robust)
    if not os.path.exists(LEDGER):
        return N_PRIOR, VZ_FLOOR
    L = pd.read_csv(LEDGER)
    L["z"] = (L.daily_sr * np.sqrt(L.n_days)).replace([np.inf, -np.inf], np.nan)
    L = L.dropna(subset=["z"])
    if len(L) <= 2:
        return N_PRIOR + len(L), VZ_FLOOR
    z = L.z.to_numpy()
    if mode == "within":
        zw = (L.z - L.groupby("idea").z.transform("median")).to_numpy()
        vz = float((1.4826 * np.median(np.abs(zw))) ** 2)
    elif mode == "pooled":
        vz = float((1.4826 * np.median(np.abs(z - np.median(z)))) ** 2)
    else:
        vz = float(np.var(z, ddof=1))
    return N_PRIOR + len(pd.read_csv(LEDGER)), max(vz, VZ_FLOOR)


# ------------------------------------------------------------------ the gates
def _split(s):
    return s[s.index < HOLD0], s[s.index >= HOLD0]


def path_b(sleeve_by_cap, theta=0.5, variant="instant", a_grid=A_GRID, days=ERA_DAYS):
    """sleeve_by_cap: {sleeve capital in $: daily returns on that capital (2x costs)} for each (1 - a) * $100K in
    a_grid. Returns the gate table. a is picked on DEV by book Sharpe."""
    days = pd.DatetimeIndex(days)
    best = None
    rows = []
    for a in a_grid:
        ri = incumbent(a * 100e3, theta, variant, days)
        if a < 1.0:
            rs = pd.Series(sleeve_by_cap[int(round((1 - a) * 100e3))]).reindex(days).fillna(0.0)
            bk = a * ri + (1 - a) * rs
        else:
            rs, bk = None, ri
        d_bk, _ = _split(bk)
        rows.append(dict(a=a, dev_book_sharpe=sharpe(d_bk)))
        if a < 1.0 and (best is None or sharpe(d_bk) > best[1]):
            best = (a, sharpe(d_bk), ri, rs, bk)
    a, _, ri, rs, bk = best
    inc = incumbent(100e3, theta, variant, days)                 # the benchmark: incumbent with all $100K
    out = dict(path="B", a=a)
    for name, sl in (("full", slice(None)), ("dev", "dev"), ("hold", "hold")):
        if sl == "dev":
            m = days < HOLD0
        elif sl == "hold":
            m = days >= HOLD0
        else:
            m = np.ones(len(days), bool)
        at = alpha_test(rs[m], ri[m])
        out[f"{name}_t_alpha"] = at["t_alpha"]
        out[f"{name}_appraisal"] = at["appraisal"]
        out[f"{name}_beta"] = at["beta"]
        out[f"{name}_book_sharpe"] = sharpe(bk[m])
        out[f"{name}_inc_sharpe"] = sharpe(inc[m])
        out[f"{name}_gain"] = out[f"{name}_book_sharpe"] - out[f"{name}_inc_sharpe"]
        out[f"{name}_sleeve_sharpe"] = sharpe(rs[m])
    N, V = n_trials()
    out["dsr"], out["sr0_ann"] = deflated_sharpe(bk, N, V)
    out["n_trials"] = N
    yr = years(bk)
    out["years"] = {int(k): round(float(v), 4) for k, v in yr.items()}
    out["G1"] = out["full_t_alpha"] >= 3.0
    out["G2"] = (out["hold_t_alpha"] >= 1.5) and (out["hold_gain"] >= 0.25)
    out["G3"] = out["full_gain"] >= 0.5
    out["G4"] = out["dsr"] >= 0.95
    out["G5"] = bool((yr > 0).all())
    out["pass_G1_G5"] = all(out[g] for g in ("G1", "G2", "G3", "G4", "G5"))
    out["a_grid"] = rows
    return out


def path_a(cand, theta=0.5, variant="instant", days=ERA_DAYS):
    """cand: candidate daily returns on $100K (2x costs), replacing the incumbent."""
    days = pd.DatetimeIndex(days)
    inc = incumbent(100e3, theta, variant, days)
    c = pd.Series(cand).reindex(days).fillna(0.0)
    dev = days < HOLD0
    k = excess(inc[dev]).std() / excess(c[dev]).std()
    cs = c * k
    d = excess(cs) - excess(inc)
    out = dict(path="A", vol_scale=float(k))
    for name, m in (("full", np.ones(len(days), bool)), ("dev", dev), ("hold", ~dev)):
        out[f"{name}_t_diff"] = hac_t(d[m])
        out[f"{name}_cand_sharpe"] = sharpe(c[m])
        out[f"{name}_inc_sharpe"] = sharpe(inc[m])
    N, V = n_trials()
    out["dsr"], out["sr0_ann"] = deflated_sharpe(c, N, V)
    out["n_trials"] = N
    yr = years(c)
    out["years"] = {int(k_): round(float(v), 4) for k_, v in yr.items()}
    out["G1"] = out["full_t_diff"] >= 3.0
    out["G2"] = (out["hold_t_diff"] >= 1.5) and (out["hold_cand_sharpe"] > out["hold_inc_sharpe"])
    out["G3"] = out["full_cand_sharpe"] > out["full_inc_sharpe"]
    out["G4"] = out["dsr"] >= 0.95
    out["G5"] = bool((yr > 0).all())
    out["pass_G1_G5"] = all(out[g] for g in ("G1", "G2", "G3", "G4", "G5"))
    return out


def dev_book(sleeve30, theta=0.5):
    """The DEV book a builder logs as a trial: 0.7 x incumbent($70K) + 0.3 x sleeve($30K, 2x costs), over the
    sleeve's own scored DEV days (pass the sleeve indexed by its scored days, zeros when idle)."""
    s = pd.Series(sleeve30).astype(float)
    s = s[s.index < HOLD0]
    ri = incumbent(70e3, theta, "instant", s.index)
    return 0.7 * ri + 0.3 * s


def dev_screen(rs, ri=None, theta=0.5):
    """DEV-only diagnostics a builder may look at while designing (no HOLD days are touched): sleeve Sharpe, alpha
    t on the incumbent at $100K, correlation, and the dev book gain at a = 0.7."""
    rs = pd.Series(rs)
    rs = rs[rs.index < HOLD0]
    days = rs.index
    ri = incumbent(100e3, theta, "instant", days) if ri is None else pd.Series(ri).reindex(days).fillna(0.0)
    at = alpha_test(rs, ri)
    return dict(sleeve_sharpe=sharpe(rs), t_alpha=at["t_alpha"], appraisal=at["appraisal"], beta=at["beta"],
                corr=float(np.corrcoef(rs, ri)[0, 1]) if rs.std() > 0 else np.nan, n_days=len(rs),
                active_days=int((rs != 0).sum()))


def assert_dev_only(r):
    """Raise if a series handed to a dev-stage computation contains HOLD days with non-zero values."""
    r = pd.Series(r)
    if (r[r.index >= HOLD0] != 0).any():
        raise RuntimeError("HOLD days present in a dev-stage computation (reports/hunt_prereg.md)")
