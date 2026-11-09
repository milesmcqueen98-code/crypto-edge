#!/usr/bin/env python3
"""Edge hunt 2, BURN (reports/hunt2/burn/SPEC.md): after a coin's ladder fails to rebound, skip that coin's (or every
coin's) 4-sigma bids for C hours.

Definitions (pinned on DEV by scripts/hunt2/burn/inspect_dev.py before any trial; reports/hunt2/burn/REPORT.md):
  parent        a research parent: an AI-approved 4-sigma trade-through of the frozen dataset (P, k = 4, filled), whether
                or not the replay funded it. Its failure is read from public 1-minute candles, so the flag depends
                neither on the cash replay nor on the filter itself.
  fill          the parent's fill minute ts (f_off = 0) at its 4-sigma level lvl (the resting bid = the fill price).
  TP hit by +60 tp_hit (tp_off in 1..60): the high of a minute in ts+1 .. ts+60 traded through the take-profit
                lvl * exp(0.6 * 4 sigma) by at least one tick (the research's own flag; a rebound inside the fill minute
                does not count).
  price at +60  g60 = 1e4 ln(close of minute ts+60 / lvl): the price of the bot's own 60-minute time exit.
  dislocation   D = ln(fair / lvl) = 4 sigma; in bp D = g_tp / 0.6 (g_tp = 1e4 ln(TP / lvl) = 1e4 x 0.6 x 4 sigma).
  failed(m)     not tp_hit and g60 < 0 and g60 <= -m x D   (m = 0: below the fill price at +60).
  known         at minute row ts + 61, the step after minute ts+60 closes (the engine's 60-minute time-exit step); no
                decision uses the flag earlier.
Rule  scope coin: each failure skips its coin's 4-sigma bids (multiplier frozen_sim.SKIP) in minute rows
      [known, known + 60 C). scope market: a failure that becomes known less than 60 minutes after another coin's
      failure (>= 2 coins failed within the same hour) skips every coin's 4-sigma bids in rows [known, known + 60 C);
      a lone failure skips nothing in this scope.
Grid (12 trials): m in {0, 0.5} x C in {6, 24, 72} hours x scope in {coin, market}.
Eligibility: a variant must skip >= 5% of DEV parents (research parents whose (fill minute, coin) cell is SKIP).
Selection: the highest DEV paired HAC t at X2 among eligible variants; ties -> shorter C, then coin scope, then m = 0.
HOLD protection: a flag is computed only for a parent whose 60-minute mark is known before its era's end; for the HOLD
eras (chk, early) only after the freeze commit (assert_frozen). The sel era's rule reads parents from 2024-12-28
(lookback; 2024 is never scored) and no price on or after 2026-04-01.

usage:
  python scripts/hunt2/burn/burn.py dev sel   the 12 DEV trials (sel era, X2, $250K), each logged in the shared ledger
  python scripts/hunt2/burn/burn.py freeze    the selection rule -> reports/hunt2/burn/frozen.json (its commit = freeze)
  python scripts/hunt2/burn/burn.py hold      AFTER the freeze commit only: the HOLD read, once
  python scripts/hunt2/burn/burn.py post      after the HOLD read: reported-only diagnostics
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

MAIN = "/home/claude/crypto-edge"
sys.path.insert(0, os.path.join(MAIN, "scripts", "hunt2"))
import frozen_sim as F  # noqa: E402
import pathA  # noqa: E402
import h2gates as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "burn")
KNOWN = pd.Timedelta(minutes=61)
LOOKBACK = pd.Timedelta(days=4)
GRID = [(m, C, s) for s in ("coin", "market") for C in (6, 24, 72) for m in (0.0, 0.5)]
SCOPE_ORDER = {"coin": 0, "market": 1}
MIN_FRAC = 0.05


def name(mthr, C, scope):
    return f"{scope}_m{mthr:g}_C{C}"


def git(*args):
    return subprocess.run(["git", "-C", WT, *args], capture_output=True, text=True, check=True).stdout.strip()


def assert_frozen():
    fn = os.path.join(OUT, "frozen.json")
    assert os.path.exists(fn), "no frozen.json: HOLD is closed"
    rel = os.path.relpath(fn, WT)
    assert git("log", "-1", "--format=%H", "--", rel) != "", "frozen.json is not committed: HOLD is closed"
    assert git("status", "--porcelain", "--", rel) == "", "frozen.json has uncommitted changes"
    fz = json.load(open(fn))
    assert git("diff", "--stat", fz["code_commit"], "HEAD", "--", "scripts/hunt2/burn/burn.py") == "", \
        "the frozen code changed after the freeze"
    return fz, git("log", "-1", "--format=%H", "--", rel)


def parents_for(era):
    """Research parents whose failure flags the era's rule may use: fill minute in [era start - 4 days, era end] and the
    60-minute mark known by the era's end. HOLD eras only after the freeze commit."""
    if era != "sel":
        assert_frozen()
    tag, (lo, hi) = F.fsim.ERAS[era]
    P = F.RL.inputs(tag)["P"]
    t0 = pd.Timestamp(lo) - LOOKBACK
    t_end = pd.Timestamp(hi) + pd.Timedelta(days=1)
    P4 = P[(P.k == 4.0) & P.filled & (P.ts >= t0) & (P.ts + KNOWN <= t_end)]
    if era == "sel":
        assert (P4.ts + KNOWN).max() <= pd.Timestamp("2026-04-01")
    return P4[["ts", "coin", "tp_hit", "tp_off", "g60", "g_tp"]].copy()


def failures(P4, mthr):
    tp = P4.tp_hit.astype(bool).to_numpy()
    D = P4.g_tp.to_numpy() / 0.6
    g = P4.g60.to_numpy()
    fail = (~tp) & (g < 0) & (g <= -mthr * D)
    Fl = P4[fail].copy()
    Fl["known"] = Fl.ts + KNOWN
    return Fl.sort_values(["known", "coin"]).reset_index(drop=True)


def triggers(Fl, scope):
    """(known, coin) of each skip window; coin '*' = every coin."""
    if scope == "coin":
        return Fl[["known", "coin"]].copy()
    k, c = Fl.known.to_numpy(), Fl.coin.to_numpy()
    keep = np.zeros(len(Fl), bool)
    j0 = 0
    for j in range(len(Fl)):
        while k[j] - k[j0] >= np.timedelta64(60, "m"):
            j0 += 1
        keep[j] = any(c[i] != c[j] for i in range(j0, j))
    T = Fl.loc[keep, ["known"]].copy()
    T["coin"] = "*"
    return T


def mult(era, mthr, C, scope):
    A = F.arrays(era)
    idx, coins = A["idx"], list(A["coins"])
    m = np.ones(A["want4"].shape)
    Fl = failures(parents_for(era), mthr)
    Tg = triggers(Fl, scope)
    r0 = ((Tg.known - idx[0]) // pd.Timedelta(minutes=1)).to_numpy(np.int64)
    for r, c in zip(r0, Tg.coin):
        a0, a1 = max(0, int(r)), min(len(idx), int(r) + 60 * C)
        if a1 <= a0:
            continue
        if c == "*":
            m[a0:a1, :] = F.SKIP
        else:
            m[a0:a1, coins.index(c)] = F.SKIP
    return m, Fl, Tg


def skipped(era, m):
    A = F.arrays(era)
    par = pathA.parents(era)
    pos = A["idx"].get_indexer(pd.DatetimeIndex(par.ts))
    col = np.array([list(A["coins"]).index(c) for c in par.coin])
    sk = (pos >= 0) & (m[np.maximum(pos, 0), col] <= F.SKIP)
    return par[sk].reset_index(drop=True), len(par)


# ------------------------------------------------------------------ DEV trials
def dev(era):
    assert era == "sel", "DEV only: the era argument is fixed to sel"
    assert git("status", "--porcelain", "--", "scripts/hunt2/burn") == "", "commit the code before running trials"
    head = git("rev-parse", "HEAD")
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, "dev_trials.csv")
    done = set(pd.read_csv(fn).variant) if os.path.exists(fn) else set()
    ser_fn = os.path.join(OUT, "dev_series.parquet")
    series = pd.read_parquet(ser_fn) if os.path.exists(ser_fn) else pd.DataFrame()
    A = F.arrays(era)
    dmask = G.is_dev(A["idx"].floor("D"))
    lo = pd.Timestamp("2025-01-01")
    for mthr, C, scope in GRID:
        v = name(mthr, C, scope)
        if v in done:
            print(v, "already logged; not re-run")
            continue
        t0 = time.time()
        m, Fl, Tg = mult(era, mthr, C, scope)
        sk, n_par = skipped(era, m)
        sk = sk[G.is_dev(sk.ts.dt.floor("D"))]
        frac = len(sk) / n_par
        scr, d = pathA.dev_trial("burn", v, m=m, n_skip=len(sk), note=f"m={mthr} C={C}h scope={scope}", m_thr=mthr,
                                 C_hours=C, scope=scope, code_commit=head)
        row = dict(variant=v, m=mthr, C=C, scope=scope, n_fail_dev=int((Fl.known >= lo).sum()),
                   n_fail_lookback=int((Fl.known < lo).sum()), n_triggers=len(Tg),
                   skip_coin_minutes_dev=int(((m <= F.SKIP) & dmask[:, None]).sum()), n_dev_parents=n_par,
                   n_skip=len(sk), frac_skip=frac, eligible=frac >= MIN_FRAC, t_diff=scr["t_diff"],
                   mean_diff_bp=scr["mean_diff_bp"], d_sharpe=scr["d_sharpe"], cand_sharpe=scr["cand_sharpe"],
                   inc_sharpe=scr["inc_sharpe"], top5_share=scr["top5_share"], n_days=scr["n_days"],
                   code_commit=head, secs=round(time.time() - t0))
        pd.DataFrame([row]).to_csv(fn, mode="a", header=not os.path.exists(fn), index=False)
        series[v] = d
        series.to_parquet(ser_fn)
        print(f"{v}: fails {row['n_fail_dev']} triggers {len(Tg)} n_skip {len(sk)} ({100 * frac:.1f}%) "
              f"t {scr['t_diff']:+.3f} mean {scr['mean_diff_bp']:+.3f} bp/day ({row['secs']}s)", flush=True)


# ------------------------------------------------------------------ selection and freeze
def freeze():
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    assert len(T) == len(GRID) and T.variant.is_unique, "run the whole grid first"
    E = T[T.frac_skip >= MIN_FRAC].copy()
    if E.empty:
        json.dump(dict(idea="burn", status="untestable: no variant skips >= 5% of DEV parents",
                       trials=T.to_dict("records")), open(os.path.join(OUT, "untestable.json"), "w"), indent=1)
        print("untestable: not frozen")
        return
    best = E.t_diff.max()
    tied = E[(best - E.t_diff).abs() < 1e-12].copy()
    tied["so"] = tied.scope.map(SCOPE_ORDER)
    s = tied.sort_values(["C", "so", "m"]).iloc[0]
    code = git("log", "-1", "--format=%H", "--", "scripts/hunt2/burn/burn.py")
    fz = dict(idea="burn", path="A", variant=s.variant,
              params=dict(m=float(s.m), C_hours=int(s.C), scope=s.scope),
              rule="failed = take-profit not hit by fill + 60 min and g60 < 0 and g60 <= -m x D (D = g_tp / 0.6); "
                   "known at minute row fill + 61; coin scope: SKIP the coin's 4-sigma multiplier in rows "
                   "[known, known + 60 C); market scope: SKIP every coin's when a failure is known < 60 min after "
                   "another coin's failure",
              code_commit=code, trials_code_commit=sorted(T.code_commit.unique().tolist()),
              selection="highest DEV paired HAC t at X2 among variants skipping >= 5% of DEV parents; ties -> "
                        "shorter C, then coin scope, then m = 0",
              dev=dict(t_diff=float(s.t_diff), mean_diff_bp=float(s.mean_diff_bp), d_sharpe=float(s.d_sharpe),
                       cand_sharpe=float(s.cand_sharpe), inc_sharpe=float(s.inc_sharpe), n_skip=int(s.n_skip),
                       frac_skip=float(s.frac_skip), n_dev_parents=int(s.n_dev_parents),
                       top5_share=float(s.top5_share)),
              n_trials=len(T), eligible=E.variant.tolist(),
              frozen_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(fz, open(os.path.join(OUT, "frozen.json"), "w"), indent=1)
    print(json.dumps(fz, indent=1))


# ------------------------------------------------------------------ the HOLD read (after the freeze commit only)
def hold():
    fz, freeze_commit = assert_frozen()
    p = fz["params"]
    m_by_era, extra = {}, dict(freeze_commit=freeze_commit, variant=fz["variant"])
    for era in ("sel", "chk", "early"):
        m, Fl, Tg = mult(era, p["m"], p["C_hours"], p["scope"])
        m_by_era[era] = m
        sk, n_par = skipped(era, m)
        extra[f"n_fail_{era}"], extra[f"n_triggers_{era}"] = len(Fl), len(Tg)
        extra[f"n_skip_{era}"], extra[f"n_parents_{era}"] = len(sk), n_par
        sk.assign(era=era).to_csv(os.path.join(OUT, f"skipped_{era}.csv"), index=False)
    g = pathA.hold_read("burn", None, OUT, m_by_era=m_by_era)
    json.dump(extra, open(os.path.join(OUT, "hold_extra.json"), "w"), indent=1)
    print(json.dumps({k: g[k] for k in ("A1", "A2", "A3", "A4", "pass", "hold_t_x2", "hold_mean_bp_x2",
                                        "hold_mean_bp_x1", "chk_mean_bp_x2", "early_mean_bp_x2", "years_x2", "dsr")},
                     indent=1, default=str))
    print(json.dumps(extra, indent=1))


def busy_blocked(era, sk):
    """Research parents of the era that are not skipped but fall inside the busy period of a skipped parent of the same
    coin (the frozen hook funds a skipped parent with ~0 dollars, so the engine keeps its coin busy until its
    take-profit + 1 or fill + 61; live, a pulled bid would leave the coin free)."""
    tag = F.fsim.ERAS[era][0]
    P = F.RL.inputs(tag)["P"]
    par = pathA.parents(era)
    P4 = P[(P.k == 4.0) & P.filled][["ts", "coin", "tp_hit", "tp_off"]]
    S = sk[["ts", "coin"]].merge(P4, on=["ts", "coin"], how="left")
    S["bu"] = S.ts + pd.to_timedelta(np.where(S.tp_hit.astype(bool), S.tp_off + 1, 61), unit="m")
    skey = set(zip(sk.ts, sk.coin))
    n = 0
    for r in S.itertuples():
        q = par[(par.coin == r.coin) & (par.ts > r.ts) & (par.ts < r.bu)]
        n += sum((t, c) not in skey for t, c in zip(q.ts, q.coin))
    return n


def post():
    """AFTER the HOLD read: reported-only diagnostics (theta 0.25 at S, S costs, years, the incumbent's ten worst DEV
    days, the busy-rule side effect of the SKIP hook)."""
    fz, _ = assert_frozen()
    assert os.path.exists(os.path.join(OUT, "gates.json")), "run hold first"
    p = fz["params"]
    D = pd.read_parquet(os.path.join(OUT, "daily.parquet"))
    days = pd.DatetimeIndex(D.index)
    era = G.era_of(days)
    res = dict(variant=fz["variant"])
    c25 = []
    for e in ("sel", "chk", "early"):
        m, _, _ = mult(e, p["m"], p["C_hours"], p["scope"])
        sk = pd.read_csv(os.path.join(OUT, f"skipped_{e}.csv"), parse_dates=["ts"])
        res[f"busy_blocked_{e}"] = busy_blocked(e, sk)
        F._A.clear()
        with pathA.cpu_slot():
            c25.append(F.daily(e, 0.25, 250e3, "S", mfac=m))
        F._A.clear()
    c25 = pd.concat(c25).sort_index()
    c25 = c25[~c25.index.duplicated()].reindex(days).fillna(0.0)
    D["s_theta025"] = c25
    i25 = G.incumbent("S", theta=0.25, days=days)
    iS, i2, i1 = (G.incumbent(c, days=days) for c in ("S", "X2", "X1"))
    diffs = {"theta025_S": G.excess(c25) - G.excess(i25), "S": G.excess(D.s) - G.excess(iS),
             "X2": G.excess(D.x2) - G.excess(i2), "X1": G.excess(D.x1) - G.excess(i1)}
    for k, d in diffs.items():
        for e, mk in (("hold", G.is_hold(days)), ("sel", era == "sel"), ("chk", era == "chk"),
                      ("early", era == "early")):
            res[f"{k}_{e}_mean_bp"] = 1e4 * float(d[mk].mean())
            res[f"{k}_{e}_t"] = G.hac_t(d[mk])
    Y = pd.DataFrame({"cand_x2": G.years(D.x2), "inc_x2": G.years(i2), "cand_x1": G.years(D.x1),
                      "inc_x1": G.years(i1), "cand_s": G.years(D.s), "inc_s": G.years(iS)})
    Y["diff_x2"] = Y.cand_x2 - Y.inc_x2
    Y.round(5).to_csv(os.path.join(OUT, "years.csv"))
    dev_m = G.is_dev(days)
    w = iS[dev_m].nsmallest(10).index
    res["worst10_dev_days"] = [str(x.date()) for x in w]
    res["worst10_dev_diff_S_bp"] = 1e4 * float((D.s - iS)[w].sum())
    res["worst10_dev_diff_X2_bp"] = 1e4 * float((D.x2 - i2)[w].sum())
    D[["s_theta025"]].to_parquet(os.path.join(OUT, "daily_theta025.parquet"))
    json.dump(res, open(os.path.join(OUT, "post.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))
    print(Y.round(4).to_string())


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "dev":
        dev(sys.argv[2])
    elif cmd == "freeze":
        freeze()
    elif cmd == "hold":
        hold()
    elif cmd == "post":
        post()
    else:
        raise SystemExit(__doc__)
