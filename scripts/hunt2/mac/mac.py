#!/usr/bin/env python3
"""Edge hunt 2, MAC (reports/hunt2/mac/SPEC.md): pull the ladder's 4-sigma bids around scheduled US macro releases.

Rule (frozen grid, 6 trials): no 4-sigma bid rests in any coin during [release - a, release + b]. Every coin's
4-sigma multiplier is frozen_sim.SKIP in each minute row from release - a to release + b, both ends included (minute
rows of frozen_sim.arrays(era)["idx"], UTC), so a parent filling there carries ~0 dollars; ladders armed earlier keep
their deeper rungs (a rung's size is the multiplier at its parent's fill minute). Release times: the official BLS/Fed
calendars in data/hunt2/macro/releases.csv (ts_utc = the release minute).
  (a, b) in {(2, 10), (5, 30), (5, 120)} minutes x event set in {CPI only, CPI+NFP+PPI+FOMC}.
Eligibility: a variant must skip >= 10 DEV parents (research parents whose fill minute falls in a window).
Selection: the highest DEV paired HAC t at X2 among eligible variants; ties -> the narrower window (fewer DEV blackout
minutes).

usage:
  python scripts/hunt2/mac/mac.py dev sel   the 6 DEV trials (sel era, X2, $250K), each logged in the shared ledger
  python scripts/hunt2/mac/mac.py freeze    the selection rule -> reports/hunt2/mac/frozen.json (its commit = freeze)
  python scripts/hunt2/mac/mac.py hold      AFTER the freeze commit only: the HOLD read, once
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
OUT = os.path.join(WT, "reports", "hunt2", "mac")
RELEASES = os.path.join(MAIN, "data", "hunt2", "macro", "releases.csv")
FEATURES_DEV = os.path.join(MAIN, "reports", "hunt2", "parents", "features_dev.csv")
SETS = {"CPI": ("CPI",), "ALL": ("CPI", "NFP", "PPI", "FOMC")}
GRID = [(2, 10, "CPI"), (5, 30, "CPI"), (5, 120, "CPI"), (2, 10, "ALL"), (5, 30, "ALL"), (5, 120, "ALL")]
MIN_SKIP = 10
DEV_LO, DEV_END = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-04-01")


def name(a, b, ev):
    return f"{ev}_a{a}_b{b}"


def git(*args):
    return subprocess.run(["git", "-C", WT, *args], capture_output=True, text=True, check=True).stdout.strip()


def releases(ev):
    r = pd.read_csv(RELEASES)
    r = r[r.event.isin(SETS[ev])].copy()
    r["ts"] = pd.to_datetime(r.ts_utc)
    return r.sort_values("ts").reset_index(drop=True)


def mult(era, a, b, ev):
    """T x NC multiplier for an era: SKIP in every coin's cells of each window's minute rows [ts - a, ts + b]."""
    A = F.arrays(era)
    idx = A["idx"]
    m = np.ones(A["want4"].shape)
    rel = releases(ev)
    for ts in rel.ts:
        i0 = idx.searchsorted(ts - pd.Timedelta(minutes=a), "left")
        i1 = idx.searchsorted(ts + pd.Timedelta(minutes=b), "right")
        if i1 > i0:
            m[i0:i1, :] = F.SKIP
    return m


def skipped(era, m):
    """The era's research parents whose (fill minute, coin) cell is skipped."""
    A = F.arrays(era)
    par = pathA.parents(era)
    pos = A["idx"].get_indexer(pd.DatetimeIndex(par.ts))
    col = np.array([list(A["coins"]).index(c) for c in par.coin])
    sk = (pos >= 0) & (m[np.maximum(pos, 0), col] <= F.SKIP)
    return par[sk].reset_index(drop=True), len(par)


def nearest_release(ts, rel):
    j = np.abs((rel.ts - ts).dt.total_seconds()).idxmin()
    return rel.event[j], rel.ts[j]


# ------------------------------------------------------------------ DEV trials
def dev(era):
    assert era == "sel", "DEV only: the era argument is fixed to sel"
    assert git("status", "--porcelain", "--", "scripts/hunt2/mac") == "", "commit the code before running trials"
    head = git("rev-parse", "HEAD")
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, "dev_trials.csv")
    done = set(pd.read_csv(fn).variant) if os.path.exists(fn) else set()
    feat = pd.read_csv(FEATURES_DEV, usecols=["coin", "ts", "era", "t_fill"], parse_dates=["ts", "t_fill"])
    feat = feat[feat.era == "sel"]
    ser_fn = os.path.join(OUT, "dev_series.parquet")
    series = pd.read_parquet(ser_fn) if os.path.exists(ser_fn) else pd.DataFrame()
    for a, b, ev in GRID:
        v = name(a, b, ev)
        if v in done:
            print(v, "already logged; not re-run")
            continue
        t0 = time.time()
        m = mult(era, a, b, ev)
        sk, n_par = skipped(era, m)
        sk = sk[G.is_dev(sk.ts.dt.floor("D"))]
        rel = releases(ev)
        rel_dev = rel[(rel.ts >= DEV_LO) & (rel.ts < DEV_END)]
        A = F.arrays(era)
        dmask = G.is_dev(A["idx"].floor("D"))
        blackout = int(((m[:, 0] <= F.SKIP) & dmask).sum())
        scr, d = pathA.dev_trial("mac", v, m=m, n_skip=len(sk), note=f"a={a} b={b} events={ev}", a=a, b=b,
                                 events=ev, code_commit=head)
        row = dict(variant=v, a=a, b=b, events=ev, n_releases_dev=len(rel_dev), blackout_min_dev=blackout,
                   n_dev_parents=n_par, n_skip=len(sk), eligible=len(sk) >= MIN_SKIP, t_diff=scr["t_diff"],
                   mean_diff_bp=scr["mean_diff_bp"], d_sharpe=scr["d_sharpe"], cand_sharpe=scr["cand_sharpe"],
                   inc_sharpe=scr["inc_sharpe"], top5_share=scr["top5_share"], n_days=scr["n_days"],
                   code_commit=head, secs=round(time.time() - t0))
        pd.DataFrame([row]).to_csv(fn, mode="a", header=not os.path.exists(fn), index=False)
        series[v] = d
        series.to_parquet(ser_fn)
        # fill-time check (DEV prints): first trade-through print of each skipped parent vs its release
        rows = []
        for r in sk.itertuples():
            e, rts = nearest_release(r.ts, rel)
            f = feat[(feat.coin == r.coin) & (feat.ts == r.ts)]
            tf = f.t_fill.iloc[0] if len(f) else pd.NaT
            rows.append(dict(variant=v, event=e, release=rts, coin=r.coin, fill_minute=r.ts,
                             minute_off=(r.ts - rts) / pd.Timedelta(minutes=1), t_fill_print=tf,
                             print_off_s=(tf - rts).total_seconds() if pd.notna(tf) else np.nan,
                             print_in_window=bool(pd.notna(tf) and rts - pd.Timedelta(minutes=a) <= tf
                                                  < rts + pd.Timedelta(minutes=b + 1))))
        sfn = os.path.join(OUT, "dev_skipped_parents.csv")
        if rows:
            pd.DataFrame(rows).to_csv(sfn, mode="a", header=not os.path.exists(sfn), index=False)
        print(f"{v}: n_skip {len(sk)} t {scr['t_diff']:+.3f} mean {scr['mean_diff_bp']:+.3f} bp/day "
              f"({row['secs']}s)", flush=True)


# ------------------------------------------------------------------ selection and freeze
def freeze():
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    assert len(T) == len(GRID) and T.variant.is_unique, "run the whole grid first"
    E = T[T.n_skip >= MIN_SKIP]
    if E.empty:
        json.dump(dict(idea="mac", status="untestable at this power: no variant skips >= 10 DEV parents",
                       trials=T.to_dict("records")), open(os.path.join(OUT, "untestable.json"), "w"), indent=1)
        print("untestable: not frozen")
        return
    best = E.t_diff.max()
    tied = E[(best - E.t_diff).abs() < 1e-12].sort_values("blackout_min_dev")
    s = tied.iloc[0]
    code = git("log", "-1", "--format=%H", "--", "scripts/hunt2/mac/mac.py")
    fz = dict(idea="mac", path="A", variant=s.variant, params=dict(a=int(s.a), b=int(s.b), events=s.events,
                                                                   event_set=list(SETS[s.events])),
              rule="every coin's 4-sigma multiplier = frozen_sim.SKIP in minute rows [release - a, release + b] "
                   "(inclusive) of each release in the event set (data/hunt2/macro/releases.csv)",
              code_commit=code, trials_code_commit=sorted(T.code_commit.unique().tolist()),
              selection="highest DEV paired HAC t at X2 among variants skipping >= 10 DEV parents; ties -> the "
                        "narrower window",
              dev=dict(t_diff=float(s.t_diff), mean_diff_bp=float(s.mean_diff_bp), d_sharpe=float(s.d_sharpe),
                       cand_sharpe=float(s.cand_sharpe), inc_sharpe=float(s.inc_sharpe), n_skip=int(s.n_skip),
                       n_dev_parents=int(s.n_dev_parents), top5_share=float(s.top5_share)),
              n_trials=len(T), eligible=E.variant.tolist(),
              frozen_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(fz, open(os.path.join(OUT, "frozen.json"), "w"), indent=1)
    print(json.dumps(fz, indent=1))


# ------------------------------------------------------------------ the HOLD read (after the freeze commit only)
def assert_frozen():
    fn = os.path.join(OUT, "frozen.json")
    assert os.path.exists(fn), "no frozen.json: HOLD is closed"
    rel = os.path.relpath(fn, WT)
    assert git("log", "-1", "--format=%H", "--", rel) != "", "frozen.json is not committed: HOLD is closed"
    assert git("status", "--porcelain", "--", rel) == "", "frozen.json has uncommitted changes"
    fz = json.load(open(fn))
    assert git("diff", "--stat", fz["code_commit"], "HEAD", "--", "scripts/hunt2/mac/mac.py") == "", \
        "the frozen code changed after the freeze"
    return fz, git("log", "-1", "--format=%H", "--", rel)


def hold():
    fz, freeze_commit = assert_frozen()
    p = fz["params"]
    out = os.path.join(OUT)
    m_by_era = {era: mult(era, p["a"], p["b"], p["events"]) for era in ("sel", "chk", "early")}
    g = pathA.hold_read("mac", None, out, m_by_era=m_by_era)
    extra = dict(freeze_commit=freeze_commit, variant=fz["variant"])
    for era, m in m_by_era.items():
        sk, n_par = skipped(era, m)
        extra[f"n_skip_{era}"], extra[f"n_parents_{era}"] = len(sk), n_par
        sk.assign(era=era).to_csv(os.path.join(OUT, f"skipped_{era}.csv"), index=False)
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
        m = mult(e, p["a"], p["b"], p["events"])
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
    dev = G.is_dev(days)
    w = iS[dev].nsmallest(10).index
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
