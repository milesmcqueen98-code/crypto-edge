#!/usr/bin/env python3
"""Edge hunt 2: the pre-registered pass tests (reports/hunt2_prereg.md). Every builder imports this module; nobody
re-implements a test.

Conventions
- Daily returns on capital, indexed by calendar day (UTC); P&L booked on the exit day; idle days are 0.
- Sharpe = annualised (sqrt 365) mean / std of daily returns ABOVE T-bills (edge.book.rf_daily), as in every round.
- Eras (the ladder rounds' eras, so the incumbent is the frozen simulator's own series):
    DEV  = sel   2025-01-01 .. 2026-03-31  (all design, parameter and model choices)
    HOLD = chk   2026-04-01 .. 2026-11-05  and  early 2022-01-01 .. 2023-12-31  (read once per idea, after its freeze)
  2021 and 2024 may train models; they are never scored.
- Incumbent = the live spot bot (R2-08, 4/6/8-sigma ladder) on ladder v6's frozen simulator: engine-faithful cash rule,
  print-measured exit costs, 1-second detection blend, today's volumes (scripts/hunt2/incumbent.py).
  Cost settings: S = its best estimate (ladder v5/v6); X1 = every cost at 1x; X2 = every cost doubled.

Path A (beat R2-08 head-to-head): a modification of the live bot run on the frozen simulator at $250K.
  A1 HOLD paired HAC t >= 2 of the daily difference (candidate - incumbent), both at X2.
  A2 HOLD mean difference > 0 at X1 as well (the gain is not an artefact of doubled costs).
  A3 the difference is positive in every HOLD era the idea is scored in (chk, early).
  A4 no losing calendar year for the candidate at X2 (every scored year).
Path B (add a sleeve): book = a * incumbent(a * $250K, S) + (1 - a) * sleeve((1 - a) * $250K, 2x costs), a in A_GRID
  chosen on DEV by book Sharpe; benchmark = incumbent($250K, S).
  B1 HOLD book Sharpe gain >= +0.5.
  B2 HOLD HAC t of the sleeve's alpha on the incumbent >= 2.
  B3 the book gain is positive in every HOLD era the idea is scored in.
  B4 no losing calendar year for the book (every scored year).
Deflated Sharpe (N = N_PRIOR + every trial in the ledger) is reported and scored, not a gate (Miles' bar, Nov 8).
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

ERAS = {"early": (pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")),
        "sel": (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-03-31")),
        "chk": (pd.Timestamp("2026-04-01"), pd.Timestamp("2026-11-05"))}
DEV_ERAS, HOLD_ERAS = ("sel",), ("chk", "early")
SCORED = pd.DatetimeIndex(sorted(set().union(*[pd.date_range(*ERAS[e], freq="D") for e in ERAS])))
A_GRID = (0.9, 0.8, 0.7, 0.5)
CAPITAL = 250e3
N_PRIOR = 4500          # hunt (3,188 incl. its ledger) + ladder v5 (15) + v6 exits (1,187) + v6 sizing (52), rounded up
VZ_FLOOR = 1.1257       # variance of z = daily Sharpe * sqrt(days) across the wick v2 lab's 139 trials
LAGS = 5
_MAIN = "/home/claude/crypto-edge/reports/hunt2"
LEDGER = os.environ.get("HUNT2_LEDGER") or (os.path.join(_MAIN, "trials.csv") if os.path.isdir(_MAIN)
                                            else os.path.join(ROOT, "reports", "hunt2", "trials.csv"))
INC = os.environ.get("HUNT2_INC") or (os.path.join(_MAIN, "incumbent_daily.parquet")
                                      if os.path.exists(os.path.join(_MAIN, "incumbent_daily.parquet"))
                                      else os.path.join(ROOT, "reports", "hunt2", "incumbent_daily.parquet"))


def era_of(days):
    days = pd.DatetimeIndex(days)
    out = np.full(len(days), "", dtype=object)
    for e, (lo, hi) in ERAS.items():
        out[(days >= lo) & (days <= hi)] = e
    return out


def is_dev(days):
    return np.isin(era_of(days), DEV_ERAS)


def is_hold(days):
    return np.isin(era_of(days), HOLD_ERAS)


# ------------------------------------------------------------------ basics
def excess(r):
    r = pd.Series(r).astype(float)
    return r - book.rf_daily(r.index).to_numpy()


def sharpe(r):
    x = excess(r)
    s = x.std()
    return float(x.mean() / s * math.sqrt(365)) if s > 0 else float("nan")


def nw_var(x, lags=LAGS):
    x = np.asarray(x, float)
    x = x - x.mean()
    n = len(x)
    v = np.dot(x, x) / n
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * np.dot(x[k:], x[:-k]) / n
    return v


def hac_t(x, lags=LAGS):
    x = np.asarray(x, float)
    if len(x) < 3:
        return float("nan")
    v = nw_var(x, lags)
    return float(x.mean() / math.sqrt(v / len(x))) if v > 0 else float("nan")


def alpha_test(rs, ri, lags=LAGS):
    """OLS of sleeve excess return on incumbent excess return, HAC (Newey-West) covariance: alpha (annualised), beta,
    HAC t of alpha, appraisal ratio."""
    y, x = excess(rs).to_numpy(), excess(ri).to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    XtX_inv = np.linalg.inv(X.T @ X)
    Xe = X * e[:, None]
    S = Xe.T @ Xe
    for k in range(1, lags + 1):
        w = 1 - k / (lags + 1)
        G = Xe[k:].T @ Xe[:-k]
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv
    se_a = math.sqrt(cov[0, 0]) if cov[0, 0] > 0 else float("nan")
    ar = b[0] / e.std() * math.sqrt(365) if e.std() > 0 else float("nan")
    return dict(alpha_yr=float(b[0] * 365), beta=float(b[1]), t_alpha=float(b[0] / se_a) if se_a == se_a else np.nan,
                appraisal=float(ar), n=len(y))


def deflated_sharpe(r, n_trials, vz):
    """Bailey & Lopez de Prado (2014), as in the first edge hunt: P(true Sharpe > expected max of n_trials null
    trials), with the null dispersion vz / T of a daily Sharpe over this record's T days."""
    x = excess(r).to_numpy()
    T = len(x)
    sr = x.mean() / x.std()
    g3 = float(pd.Series(x).skew())
    g4 = float(pd.Series(x).kurt()) + 3
    em = 0.5772156649
    sr0 = math.sqrt(vz / T) * ((1 - em) * norm.ppf(1 - 1 / n_trials) + em * norm.ppf(1 - 1 / (n_trials * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return float(norm.cdf(z)), float(sr0 * math.sqrt(365))


def years(r):
    r = pd.Series(r)
    return r.groupby(r.index.year).sum()


def top_share(x, k=5):
    x = pd.Series(x)
    tot = float(x.sum())
    return float(x.nlargest(k).sum() / tot) if tot > 0 else float("nan")


# ------------------------------------------------------------------ incumbent
def incumbent(cost="S", theta=0.5, C=CAPITAL, days=None):
    """Daily returns of the incumbent on its capital C over the scored days (or `days`)."""
    D = pd.read_parquet(INC)
    parts = []
    for era in ("early", "sel", "chk"):
        col = f"{cost}|{float(theta)}|{int(C)}|{era}"
        if col not in D.columns:
            raise KeyError(f"{col} not built (scripts/hunt2/incumbent.py {cost}:{theta}:{int(C)})")
        parts.append(D[col].dropna())
    s = pd.concat(parts).sort_index()
    s = s[~s.index.duplicated()].reindex(SCORED).fillna(0.0)
    return s if days is None else s.reindex(pd.DatetimeIndex(days)).fillna(0.0)


# ------------------------------------------------------------------ trial ledger
def log_trial(idea, variant, r, path, stat, note="", stage="dev", **extra):
    """Append one trial to the shared ledger (file-locked). r: the DEV daily series that was scored (Path A: the
    candidate at X2; Path B: the a = 0.8 book with the sleeve at 2x). stat: the selection statistic (Path A: DEV paired
    t at X2; Path B: DEV alpha t). Every configuration evaluated counts, failures included."""
    r = pd.Series(r).dropna()
    if stage == "dev":
        assert_dev_only(r)
        r = r[is_dev(r.index)]
    x = excess(r)
    row = dict(time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), idea=idea, variant=variant, path=path,
               stage=stage, n_days=len(r), daily_sr=float(x.mean() / x.std()) if x.std() > 0 else np.nan,
               sharpe=sharpe(r) if len(r) > 2 else np.nan, stat=float(stat), note=note,
               extra=json.dumps(extra, default=str))
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        new = f.read() == ""
        pd.DataFrame([row]).to_csv(f, header=new, index=False)
        fcntl.flock(f, fcntl.LOCK_UN)
    return row


def n_trials():
    """N = N_PRIOR + ledger trials; vz = max(lab floor, (1.4826 x MAD of within-idea demeaned z)^2) (the first hunt's
    binding rule)."""
    if not os.path.exists(LEDGER):
        return N_PRIOR, VZ_FLOOR
    L = pd.read_csv(LEDGER)
    L = L[L.stage == "dev"]
    L["z"] = (L.daily_sr * np.sqrt(L.n_days)).replace([np.inf, -np.inf], np.nan)
    L = L.dropna(subset=["z"])
    if len(L) <= 2:
        return N_PRIOR + len(L), VZ_FLOOR
    zw = (L.z - L.groupby("idea").z.transform("median")).to_numpy()
    vz = float((1.4826 * np.median(np.abs(zw))) ** 2)
    return N_PRIOR + len(L), max(vz, VZ_FLOOR)


def assert_dev_only(r):
    """Raise if a series handed to a dev-stage computation has non-zero values on HOLD days."""
    r = pd.Series(r)
    h = is_hold(r.index)
    if (r[h] != 0).any():
        raise RuntimeError("HOLD days present in a dev-stage computation (reports/hunt2_prereg.md)")


# ------------------------------------------------------------------ DEV-only helpers for builders
def dev_screen_a(cand_x2, days=None):
    """Path A, DEV only: paired t and Sharpe difference of a candidate (X2) against the incumbent (X2) on DEV days."""
    c = pd.Series(cand_x2)
    days = pd.DatetimeIndex(days if days is not None else c.index)
    days = days[is_dev(days)]
    c = c.reindex(days).fillna(0.0)
    inc = incumbent("X2", days=days)
    d = excess(c) - excess(inc)
    return dict(t_diff=hac_t(d), mean_diff_bp=1e4 * float(d.mean()), d_sharpe=sharpe(c) - sharpe(inc),
                cand_sharpe=sharpe(c), inc_sharpe=sharpe(inc), top5_share=top_share(d), n_days=len(days))


def dev_book(sleeve_50k_2x, a=0.8):
    """The DEV book a builder logs as a Path B trial: a x incumbent(a x $250K, S) + (1 - a) x sleeve((1 - a) x $250K,
    2x costs), over the sleeve's scored DEV days (zeros when idle)."""
    s = pd.Series(sleeve_50k_2x).astype(float)
    s = s[is_dev(s.index)]
    ri = incumbent("S", C=a * CAPITAL, days=s.index)
    return a * ri + (1 - a) * s


def dev_screen_b(sleeve_50k_2x, a=0.8):
    """Path B, DEV only: sleeve Sharpe, alpha t on the incumbent, correlation, and the DEV book gain at a."""
    s = pd.Series(sleeve_50k_2x).astype(float)
    s = s[is_dev(s.index)]
    days = s.index
    ri = incumbent("S", C=a * CAPITAL, days=days)
    bench = incumbent("S", C=CAPITAL, days=days)
    at = alpha_test(s, ri)
    bk = a * ri + (1 - a) * s
    return dict(sleeve_sharpe=sharpe(s), t_alpha=at["t_alpha"], appraisal=at["appraisal"], beta=at["beta"],
                corr=float(np.corrcoef(s, ri)[0, 1]) if s.std() > 0 else np.nan, book_gain=sharpe(bk) - sharpe(bench),
                n_days=len(s), active_days=int((s != 0).sum()))


# ------------------------------------------------------------------ the gates (read once, after the freeze)
def path_a(cand_x2, cand_x1, days=SCORED):
    """cand_x2 / cand_x1: the candidate's daily returns on $250K at X2 / X1 over its scored days."""
    days = pd.DatetimeIndex(days)
    c2 = pd.Series(cand_x2).reindex(days).fillna(0.0)
    c1 = pd.Series(cand_x1).reindex(days).fillna(0.0)
    i2, i1 = incumbent("X2", days=days), incumbent("X1", days=days)
    iS = incumbent("S", days=days)
    d2, d1 = excess(c2) - excess(i2), excess(c1) - excess(i1)
    era = era_of(days)
    out = dict(path="A")
    for name, m in (("full", np.ones(len(days), bool)), ("dev", is_dev(days)), ("hold", is_hold(days)),
                    ("chk", era == "chk"), ("early", era == "early")):
        if m.sum() == 0:
            continue
        out[f"{name}_t_x2"] = hac_t(d2[m])
        out[f"{name}_mean_bp_x2"] = 1e4 * float(d2[m].mean())
        out[f"{name}_mean_bp_x1"] = 1e4 * float(d1[m].mean())
        out[f"{name}_t_x1"] = hac_t(d1[m])
        out[f"{name}_cand_sharpe_x2"] = sharpe(c2[m])
        out[f"{name}_inc_sharpe_x2"] = sharpe(i2[m])
        out[f"{name}_dsharpe_x2"] = out[f"{name}_cand_sharpe_x2"] - out[f"{name}_inc_sharpe_x2"]
        out[f"{name}_inc_sharpe_S"] = sharpe(iS[m])
        out[f"{name}_top5_share_x2"] = top_share(d2[m])
    N, V = n_trials()
    out["dsr"], out["sr0_ann"] = deflated_sharpe(c2, N, V)
    out["n_trials"], out["vz"] = N, V
    yr = years(c2)
    out["years_x2"] = {int(k): round(float(v), 4) for k, v in yr.items()}
    hold_eras = [e for e in HOLD_ERAS if f"{e}_mean_bp_x2" in out]
    out["A1"] = bool(out.get("hold_t_x2", np.nan) >= 2.0)
    out["A2"] = bool(out.get("hold_mean_bp_x1", np.nan) > 0)
    out["A3"] = bool(len(hold_eras) > 0 and all(out[f"{e}_mean_bp_x2"] > 0 for e in hold_eras))
    out["A4"] = bool((yr > 0).all())
    out["pass"] = all(out[g] for g in ("A1", "A2", "A3", "A4"))
    return out


def path_b(sleeve_by_cap_2x, days=SCORED, a_grid=A_GRID):
    """sleeve_by_cap_2x: {sleeve capital in $: daily returns on that capital at 2x costs}, one entry for each
    (1 - a) x $250K in a_grid. a is picked on DEV by book Sharpe."""
    days = pd.DatetimeIndex(days)
    dev, hold, era = is_dev(days), is_hold(days), era_of(days)
    bench = incumbent("S", C=CAPITAL, days=days)
    best, rows = None, []
    for a in a_grid:
        cap = int(round((1 - a) * CAPITAL))
        ri = incumbent("S", C=a * CAPITAL, days=days)
        rs = pd.Series(sleeve_by_cap_2x[cap]).reindex(days).fillna(0.0)
        bk = a * ri + (1 - a) * rs
        sd = sharpe(bk[dev])
        rows.append(dict(a=a, dev_book_sharpe=sd))
        if best is None or sd > best[1]:
            best = (a, sd, ri, rs, bk)
    a, _, ri, rs, bk = best
    out = dict(path="B", a=a, a_grid=rows)
    for name, m in (("full", np.ones(len(days), bool)), ("dev", dev), ("hold", hold), ("chk", era == "chk"),
                    ("early", era == "early")):
        if m.sum() == 0:
            continue
        at = alpha_test(rs[m], ri[m])
        out[f"{name}_t_alpha"] = at["t_alpha"]
        out[f"{name}_appraisal"] = at["appraisal"]
        out[f"{name}_beta"] = at["beta"]
        out[f"{name}_book_sharpe"] = sharpe(bk[m])
        out[f"{name}_inc_sharpe"] = sharpe(bench[m])
        out[f"{name}_gain"] = out[f"{name}_book_sharpe"] - out[f"{name}_inc_sharpe"]
        out[f"{name}_sleeve_sharpe"] = sharpe(rs[m])
        out[f"{name}_corr"] = float(np.corrcoef(rs[m], ri[m])[0, 1]) if rs[m].std() > 0 else np.nan
        out[f"{name}_top5_share"] = top_share(bk[m] - bench[m])
    N, V = n_trials()
    out["dsr"], out["sr0_ann"] = deflated_sharpe(bk, N, V)
    out["n_trials"], out["vz"] = N, V
    yr = years(bk)
    out["years"] = {int(k): round(float(v), 4) for k, v in yr.items()}
    hold_eras = [e for e in HOLD_ERAS if f"{e}_gain" in out]
    out["B1"] = bool(out.get("hold_gain", np.nan) >= 0.5)
    out["B2"] = bool(out.get("hold_t_alpha", np.nan) >= 2.0)
    out["B3"] = bool(len(hold_eras) > 0 and all(out[f"{e}_gain"] > 0 for e in hold_eras))
    out["B4"] = bool((yr > 0).all())
    out["pass"] = all(out[g] for g in ("B1", "B2", "B3", "B4"))
    return out
