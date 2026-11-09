#!/usr/bin/env python3
"""Edge hunt 2 (builder "flow"): WHO and EXH, pre-fill order-flow filters for R2-08's ladder (Path A).

Both ideas skip a research parent (R2-08's AI-approved 4-sigma fill: coin, fill minute) when one pre-fill print feature
(scripts/hunt2/parent_features.py: Coinbase prints at least 1 s before the first trade-through of the level) lies in
the tail that holds `share` of the DEV parents. Specs (binding): reports/hunt2/who/SPEC.md, reports/hunt2/exh/SPEC.md.
WHO and EXH share this module so that both use one threshold rule; each has a thin entry script.

Threshold rule (one rule for every variant, fixed before any trial):
  thr = numpy.quantile(feature over the DEV parents that have a value, level), level = share * N_DEV / N_with_value
  for skip-LOW and 1 - that for skip-HIGH, so that `share` of ALL DEV parents is removed. Parents without a value
  (no prints) are kept, never skipped. Skip HIGH: value > thr; skip LOW: value < thr. thr is then fixed in absolute
  units for every era.

A skipped parent's (fill minute, coin) cell gets frozen_sim.SKIP through pathA (the 4-sigma bid and the ladder's deeper
rungs carry ~0 dollars; the frozen simulator's engine-faithful cash rule decides the rest).

HOLD protection: the dev command reads only reports/hunt2/parents/features_dev.csv and runs only the sel era; the hold
command refuses to run unless BOTH ideas' frozen.json are committed (and clean) in this worktree and the HOLD feature
file exists. Shared code and data come from the main clone (/home/claude/crypto-edge), read-only; the only write there
is the trial ledger through h2gates.log_trial (inside pathA.dev_trial).

usage:
  python scripts/hunt2/who/who.py dev sel     # WHO's SPEC grid on DEV (sel era, X2, $250K); each trial logged
  python scripts/hunt2/who/who.py select      # the SPEC's fixed selection -> reports/hunt2/who/frozen.json
  python scripts/hunt2/who/who.py hold        # AFTER both freezes and the HOLD feature file: read HOLD once
  (EXH: scripts/hunt2/exh/exh.py with the same commands)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

MAIN = "/home/claude/crypto-edge"
HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))          # scripts/hunt2/who -> worktree root
sys.path.insert(0, os.path.join(MAIN, "scripts", "hunt2"))
import frozen_sim as F  # noqa: E402
import pathA  # noqa: E402
import h2gates as G  # noqa: E402  (after frozen_sim, as pathA does)

FEAT_DEV = os.path.join(WT, "reports", "hunt2", "parents", "features_dev.csv")
FEAT_HOLD = os.path.join(WT, "reports", "hunt2", "parents", "features_hold.csv")
IDEAS = ("who", "exh")
SHARES = (0.15, 0.30)
# (name, feature in parent_features.py, side whose tail is skipped)
GRIDS = {
    "who": [("bigadv5", "sell_bigadv_share_5", "high"), ("bigadv15", "sell_bigadv_share_15", "high"),
            ("hhi5", "sell_hhi_5", "high"), ("hhi15", "sell_hhi_15", "high"),
            ("sshare5", "sell_share_5", "low"), ("sshare15", "sell_share_15", "low"),
            ("rate1", "rate_ratio_1", "low"), ("rate5", "rate_ratio_5", "low")],
    "exh": [("expeak", "ex_peak", "high"), ("csv15", "csv_15", "low"), ("csv30", "csv_30", "low"),
            ("turn", "turn", "low")],
}
SCREEN_KEYS = ("t_diff", "mean_diff_bp", "d_sharpe", "cand_sharpe", "inc_sharpe", "top5_share", "n_days")


def variants(idea):
    return [dict(variant=f"{n}_{int(round(100 * s))}", feature=f, side=sd, share=s)
            for n, f, sd in GRIDS[idea] for s in SHARES]


def out_dir(idea):
    d = os.path.join(WT, "reports", "hunt2", idea)
    os.makedirs(d, exist_ok=True)
    return d


def git(*args):
    return subprocess.run(["git", "-C", WT, *args], capture_output=True, text=True, check=True).stdout.strip()


def frozen_commit(idea):
    """Hash of the last commit of reports/hunt2/<idea>/frozen.json if it is committed and unchanged since, else None."""
    rel = f"reports/hunt2/{idea}/frozen.json"
    h = git("log", "-1", "--format=%H", "--", rel)
    return h if h and not git("status", "--porcelain", "--", rel) else None


# ------------------------------------------------------------------ features
def table(era):
    """The research parents of an era (pathA.parents) joined to their print features on (ts, coin); every parent is
    kept (a parent without prints has NaN features). sel reads the DEV file; chk/early read the HOLD file, which only
    the hold command may reach (after both freezes)."""
    if era == "sel":
        path = FEAT_DEV
    else:
        if not all(frozen_commit(i) for i in IDEAS):
            raise RuntimeError("HOLD features before both freeze commits (reports/hunt2_prereg.md)")
        path = FEAT_HOLD
    par = pathA.parents(era)
    fe = pd.read_csv(path, parse_dates=["ts", "t_fill"])
    fe = fe[fe.era == era].drop(columns=["lvl"])
    fe["ts"] = fe.ts.astype(par.ts.dtype)
    J = par.merge(fe, on=["ts", "coin"], how="left", validate="one_to_one")
    assert len(J) == len(par)
    if era == "sel":
        assert G.is_dev(J.ts.dt.floor("D")).all()
    return J


def threshold(x, share, side, n_all):
    v = pd.Series(x, dtype=float).dropna().to_numpy()
    q = share * n_all / len(v)
    assert 0.0 < q < 1.0
    return float(np.quantile(v, q if side == "low" else 1.0 - q))


def skip_mask(x, thr, side):
    x = pd.Series(x, dtype=float).to_numpy()
    with np.errstate(invalid="ignore"):
        m = (x < thr) if side == "low" else (x > thr)
    return m & np.isfinite(x)                      # missing features: kept


def check_cells(era, cells, theta=0.5):
    """Every skip cell must land on one of the frozen simulator's parents of the era (else the skip would be silent)."""
    A = F.arrays(era, theta)
    idx, coins = A["idx"], list(A["coins"])
    pos = idx.get_indexer(pd.DatetimeIndex(cells["ts"]))
    col = np.array([coins.index(c) if c in coins else -1 for c in cells["coin"]], dtype=np.int64)
    assert (pos >= 0).all() and (col >= 0).all(), "a skip cell is outside the simulator's grid"
    par = set(zip(A["p_t"].tolist(), A["p_c"].tolist()))
    hit = sum((int(p), int(c)) in par for p, c in zip(pos, col))
    assert hit == len(cells), f"{len(cells) - hit} skip cells are not simulator parents"
    return hit


# ------------------------------------------------------------------ DEV
def cmd_dev(idea, era):
    if era != "sel":
        raise SystemExit("dev runs are fixed to the sel era (DEV)")
    J = table("sel")
    n_all = len(J)
    res_path = os.path.join(out_dir(idea), "dev_trials.csv")
    day_path = os.path.join(out_dir(idea), "dev_daily_x2.parquet")
    done = pd.read_csv(res_path) if os.path.exists(res_path) else pd.DataFrame(columns=["variant"])
    daily = pd.read_parquet(day_path) if os.path.exists(day_path) else pd.DataFrame()
    led = pd.read_csv(G.LEDGER) if os.path.exists(G.LEDGER) else pd.DataFrame(columns=["idea", "variant"])
    for v in variants(idea):
        if v["variant"] in set(done.variant):
            continue
        if ((led.idea == idea) & (led.variant == v["variant"])).any():
            raise RuntimeError(f"{idea}/{v['variant']} is in the ledger without a local result; resolve by hand")
        x = J[v["feature"]]
        thr = threshold(x, v["share"], v["side"], n_all)
        m = skip_mask(x, thr, v["side"])
        cells = J.loc[m, ["ts", "coin"]].reset_index(drop=True)
        check_cells("sel", cells)
        t0 = time.time()
        scr, d = pathA.dev_trial(idea, v["variant"], cells,
                                 note=f"flow: skip {v['feature']} {v['side']} tail, {v['share']:.0%} of DEV parents",
                                 builder="flow", feature=v["feature"], side=v["side"], share=v["share"], thr=thr)
        G.assert_dev_only(d)
        row = dict(v, thr=thr, n_parents=n_all, n_skipped=int(m.sum()), n_missing=int(x.isna().sum()),
                   **{k: scr[k] for k in SCREEN_KEYS}, secs=round(time.time() - t0),
                   time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        done = pd.concat([done, pd.DataFrame([row])], ignore_index=True)
        done.to_csv(res_path, index=False)
        daily[v["variant"]] = d
        daily.to_parquet(day_path)
        print(f"{idea} {v['variant']:12s} thr {thr:.5g} skip {row['n_skipped']:4d}  t {scr['t_diff']:+.3f}  "
              f"mean {scr['mean_diff_bp']:+.3f} bp/day  dSharpe {scr['d_sharpe']:+.3f}  ({row['secs']}s)", flush=True)


def cmd_select(idea):
    R = pd.read_csv(os.path.join(out_dir(idea), "dev_trials.csv"))
    want = [v["variant"] for v in variants(idea)]
    assert sorted(R.variant) == sorted(want), "run the full SPEC grid first"
    # the SPEC's fixed rule: highest DEV paired HAC t at X2; ties -> the smaller removal share
    R = R.sort_values(["t_diff", "share"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    b = R.iloc[0]
    code = git("log", "-1", "--format=%H", "--", "scripts/hunt2/who", "scripts/hunt2/exh")
    if git("status", "--porcelain", "--", "scripts/hunt2/who", "scripts/hunt2/exh"):
        raise SystemExit("commit the code first: frozen.json must name the commit that reproduces the DEV numbers")
    fz = dict(idea=idea, path="A", builder="flow", variant=b.variant, feature=b.feature, side=b.side,
              share=float(b.share), threshold=float(b.thr), skip_if=f"{b.feature} {'>' if b.side == 'high' else '<'} "
              f"{b.thr!r}", missing="kept (never skipped)",
              threshold_rule="numpy.quantile (linear) of the DEV parents' values at the level that removes `share` of "
                             "all DEV parents; fixed in absolute units for HOLD",
              selection="highest DEV paired HAC t at X2 (h2gates.dev_screen_a); ties -> the smaller removal share",
              code_commit=code, spec=f"reports/hunt2/{idea}/SPEC.md",
              dev=dict(n_parents=int(b.n_parents), n_skipped=int(b.n_skipped), n_missing=int(b.n_missing),
                       **{k: float(b[k]) for k in SCREEN_KEYS}),
              trials=[{k: (float(r[k]) if isinstance(r[k], (float, np.floating)) else r[k])
                       for k in ("variant", "feature", "side", "share", "thr", "n_skipped", "t_diff", "mean_diff_bp",
                                 "d_sharpe")} for _, r in R.iterrows()],
              n_trials=len(R), time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(fz, open(os.path.join(out_dir(idea), "frozen.json"), "w"), indent=1, default=str)
    print(json.dumps({k: fz[k] for k in ("variant", "skip_if", "code_commit", "dev")}, indent=1, default=str))


# ------------------------------------------------------------------ HOLD (after both freezes, once)
def _headroom_gb():
    """Free memory for this process: the smaller of the machine's MemAvailable and the headroom of this process's
    memory cgroup (cgroup v1: limit - (usage - inactive file cache)); the builders share one cgroup (6.26 GB)."""
    kb = [int(x.split()[1]) for x in open("/proc/meminfo") if x.startswith("MemAvailable")][0]
    free = kb / 1e6
    try:
        cg = [x.split(":", 2)[2].strip() for x in open("/proc/self/cgroup") if x.split(":")[1] == "memory"][0]
        d = "/sys/fs/cgroup/memory" + cg
        lim = int(open(d + "/memory.limit_in_bytes").read())
        use = int(open(d + "/memory.usage_in_bytes").read())
        st = dict(x.split() for x in open(d + "/memory.stat"))
        free = min(free, (lim - use + int(st.get("total_inactive_file", 0))) / 1e9)
    except (OSError, IndexError, ValueError):
        pass
    return free


def _wait_mem(gb):
    """The machine is shared by five builders: wait until `gb` GB are free before loading more. This process also
    volunteers as the first victim of an out-of-memory kill (oom_score_adj 1000), so it never takes another
    builder's job down."""
    try:
        open("/proc/self/oom_score_adj", "w").write("1000")
    except OSError:
        pass
    while True:
        h = _headroom_gb()
        if h >= gb:
            return
        print(f"waiting for memory: {h:.2f} GB free, need {gb}", flush=True)
        time.sleep(30)


def _free_except(era, theta=0.5):
    """Keep only this era's simulator arrays (at theta) and its data tag's inputs in the frozen simulator's caches
    (frozen_sim._A, rt_live._IN). They are pure caches: values are unchanged, only reloaded when needed. Added after
    the freeze, before the HOLD read, so that one process never holds every era at once (memory, not results)."""
    import gc
    tag = F.fsim.ERAS[era][0]
    for k in [k for k in F._A if k[:2] != (era, theta)]:
        del F._A[k]
    for t in [t for t in F.RL._IN if t != tag]:
        del F.RL._IN[t]
    gc.collect()


def _lowmem_run_cells():
    """pathA.hold_read calls pathA.run_cells for each era and cost; wrap it (in this process only, the shared file is
    not edited) so that it frees the other eras first and waits for memory."""
    orig = pathA.run_cells

    def run_cells(era, *a, **kw):
        _free_except(era, kw.get("theta", 0.5))
        _wait_mem(MEM_GB)
        return orig(era, *a, **kw)
    run_cells._lowmem = True
    pathA.run_cells = run_cells


MEM_GB = 1.9            # one era of the frozen simulator peaks at ~1.6 GB (the WHO HOLD read's process)


def _hold_cells(fz, theta=0.5):
    """The frozen rule's skip cells and counts in every era (sel from the DEV file, chk/early from the HOLD file),
    each checked against the simulator's parents (arrays at `theta`, the ones the next run uses)."""
    cells, counts = {}, {}
    for era in ("sel", "chk", "early"):
        _free_except(era, theta)
        _wait_mem(MEM_GB)
        J = table(era)
        x = J[fz["feature"]]
        m = skip_mask(x, fz["threshold"], fz["side"])
        cells[era] = J.loc[m, ["ts", "coin"]].reset_index(drop=True)
        check_cells(era, cells[era], theta)
        counts[era] = dict(parents=len(J), skipped=int(m.sum()), skip_share=float(m.mean()),
                           missing=int(x.isna().sum()), no_prints=int((J.flag == "no_prints").sum()),
                           no_touch=int((J.flag == "no_touch").sum()))
        print(era, counts[era], flush=True)
    assert counts["sel"]["skipped"] == fz["dev"]["n_skipped"], "DEV cells differ from the frozen DEV trial"
    return cells, counts


def cmd_hold(idea):
    fc = frozen_commit(idea)
    if not fc or not all(frozen_commit(i) for i in IDEAS):
        raise SystemExit("both frozen.json files must be committed before HOLD is read")
    if not os.path.exists(FEAT_HOLD):
        raise SystemExit(f"missing {FEAT_HOLD} (the derive job runs after both freezes)")
    od = out_dir(idea)
    if os.path.exists(os.path.join(od, "gates.json")):
        raise SystemExit("gates.json exists: HOLD is read once")
    fz = json.load(open(os.path.join(od, "frozen.json")))
    cells, counts = _hold_cells(fz)
    t0 = time.time()
    _lowmem_run_cells()
    g = pathA.hold_read(idea, cells, od)
    print(f"hold_read {time.time() - t0:.0f}s", flush=True)
    keys = ("A1", "A2", "A3", "A4", "pass", "hold_t_x2", "hold_mean_bp_x2", "hold_mean_bp_x1", "chk_mean_bp_x2",
            "early_mean_bp_x2", "chk_t_x2", "early_t_x2", "dev_t_x2", "dsr", "years_x2", "hold_top5_share_x2")
    print(json.dumps({k: g.get(k) for k in keys}, indent=1, default=str), flush=True)
    _extras(idea, fz, fc, cells, counts)


def cmd_extras(idea):
    """Reported-only numbers of the frozen variant (theta 0.25 at S, years, the incumbent's worst DEV days), for an
    idea whose HOLD read (gates.json, daily.parquet) is done but whose extras were not written (WHO: the read's
    process was killed by the cgroup's out-of-memory killer after hold_read had written its files)."""
    fc = frozen_commit(idea)
    od = out_dir(idea)
    if not fc or not os.path.exists(os.path.join(od, "gates.json")):
        raise SystemExit("extras only after the HOLD read (gates.json)")
    if os.path.exists(os.path.join(od, "hold_extra.json")):
        raise SystemExit("hold_extra.json exists")
    fz = json.load(open(os.path.join(od, "frozen.json")))
    _lowmem_run_cells()
    cells, counts = _hold_cells(fz, theta=0.25)
    _extras(idea, fz, fc, cells, counts)


def _extras(idea, fz, fc, cells, counts):
    od = out_dir(idea)
    _lowmem_run_cells() if not getattr(pathA.run_cells, "_lowmem", False) else None
    # reported, not gated: theta 0.25 at S against the incumbent's S|0.25
    th = {}
    parts = []
    for era in ("sel", "chk", "early"):
        parts.append(pathA.run_cells(era, cells[era], cost="S", theta=0.25))
    F._A.clear()
    F.RL._IN.clear()
    c25 = pd.concat(parts).sort_index()
    c25 = c25[~c25.index.duplicated()]
    days = c25.index[np.isin(G.era_of(c25.index), list(G.ERAS))]
    c25 = c25.reindex(days)
    i25 = G.incumbent("S", theta=0.25, days=days)
    d25 = G.excess(c25) - G.excess(i25)
    era = G.era_of(days)
    for name, m in (("dev", G.is_dev(days)), ("hold", G.is_hold(days)), ("chk", era == "chk"),
                    ("early", era == "early")):
        th[f"{name}_mean_bp_S_theta025"] = 1e4 * float(d25[m].mean())
        th[f"{name}_t_S_theta025"] = G.hac_t(d25[m])
        th[f"{name}_dsharpe_S_theta025"] = G.sharpe(c25[m]) - G.sharpe(i25[m])
    # descriptive extras (no selection uses them)
    D = pd.read_parquet(os.path.join(od, "daily.parquet"))
    i2 = G.incumbent("X2", days=D.index)
    iS = G.incumbent("S", days=D.index)
    dx2 = G.excess(D.x2) - G.excess(i2)
    yrs = {int(y): dict(cand_x2=round(float(D.x2[D.index.year == y].sum()), 4),
                        inc_x2=round(float(i2[i2.index.year == y].sum()), 4),
                        diff_x2=round(float(dx2[dx2.index.year == y].sum()), 4)) for y in sorted(set(D.index.year))}
    dev = G.is_dev(D.index)
    worst = {}
    for k, inc in (("X2", i2), ("S", iS)):
        w = inc[dev].nsmallest(10).index
        cand = D.x2 if k == "X2" else D.s
        worst[k] = dict(days=[str(x.date()) for x in w], inc_sum=float(inc[w].sum()), cand_sum=float(cand[w].sum()),
                        diff_sum=float(cand[w].sum() - inc[w].sum()))
    extra = dict(idea=idea, frozen_commit=fc, variant=fz["variant"], skip_if=fz["skip_if"], counts=counts,
                 theta025=th, years=yrs, incumbent_worst10_dev=worst,
                 time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(extra, open(os.path.join(od, "hold_extra.json"), "w"), indent=1, default=str)
    print(json.dumps(th, indent=1))


def main(idea, argv):
    assert idea in IDEAS
    cmd = argv[0] if argv else ""
    if cmd == "dev":
        cmd_dev(idea, argv[1] if len(argv) > 1 else "")
    elif cmd == "select":
        cmd_select(idea)
    elif cmd == "hold":
        cmd_hold(idea)
    elif cmd == "extras":
        cmd_extras(idea)
    else:
        raise SystemExit(__doc__)
