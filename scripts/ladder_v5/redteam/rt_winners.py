#!/usr/bin/env python3
"""Red team (ladder v5): the winners C2a, C3b, C4 and the joint sets on my engine-faithful replay of the cash rule.

Each candidate is applied where the engine (or the builder) applies it, on top of my replay (rt_live.py):
  c2a  size_by_margin (bot/spot/engine.py on origin/ladder/v5-bot): the 4-sigma bid of minute t is sized with t's
       multiplier (`_allocate`), the ladder's S with it (`_arm`), so the deeper rungs use the multiplier of the minute
       the parent filled. Multipliers from the builder's own cutoffs (cand_sizing.c2_arrays, unchanged), margin =
       prediction - quarterly threshold in float32 as hsim computes it; checked equal to cand_sizing.size_fn_for.
  c3b  passive exit, N = 15: cand_exits.exit_rem (unchanged) on each latency bound's tranche frame of my book, blended.
       The cash rule does not see the longer holding (as the joint book), except in world faithful_c3cash, where every
       remainder stays held to the end of the passive window (an upper bound on the passive exit's cash effect).
  c4   USDC overlay: cand_joint.c4_overlay (unchanged) with the positions of my book's instant-bound tranche frame
       (plus the passive window's dollar-minutes under c3b).
Worlds: faithful (my engine-faithful replay), faithful_c3cash (same, C3's remainders hold cash 15 more minutes),
hsim_like (my emulation of hsim's choices; cross-check against the builders' logged trials).
Statistics as gates.run computes them, but each candidate against MY incumbent (policy engine, same world and
configuration): per-era return / Sharpe, mean difference and Newey-West t, pooled t, vol-matched t, gates G1-G4
(path "return"); and each component's marginal within the full set (full minus the set without it).
hsim.py and gates.py are imported only as dependencies of the builders' modules; nothing here calls them, and no
trial is logged (reports/ladder_v5/trials.csv is never opened).
usage: python scripts/ladder_v5/redteam/rt_winners.py run <cfg> [<cfg> ...]    daily books per configuration
       python scripts/ladder_v5/redteam/rt_winners.py score                     statistics from the saved books
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LV5 = os.path.dirname(HERE)
sys.path.insert(0, LV5)
import gates  # noqa: E402,F401  (first, from scripts/ladder_v5: the builders' modules assert it)
import cand_sizing as CS  # noqa: E402
import cand_exits as CE  # noqa: E402
import cand_cashvenue as CV  # noqa: E402,F401
import cand_joint as CJ  # noqa: E402
sys.path.insert(0, HERE)
import rt_live as RL  # noqa: E402
import rt_matrix as MX  # noqa: E402
import fsim  # noqa: E402

for _m in (CS, CE, CJ, fsim):
    assert os.path.dirname(os.path.abspath(_m.__file__)) == LV5, _m.__file__

OUTD = os.path.join(RL.OUT, "winners")
CONFIGS = {"S_0.5": dict(theta=0.5, C=250e3, today=True, cost_mult=2.0),
           "S_0.25": dict(theta=0.25, C=250e3, today=True, cost_mult=2.0),
           "base_0.5": dict(theta=0.5, C=250e3, today=False, cost_mult=1.0),
           "cap_1M": dict(theta=0.5, C=1e6, today=True, cost_mult=2.0)}
ERAS = list(fsim.ERAS)
N_PASSIVE = 15
WORLDS = {"faithful": (False, {}, 0), "faithful_c3cash": (False, {}, N_PASSIVE),
          "hsim_like": (True, dict(MX.HSIM, prio_mode=1), 0)}
BOOKS = ["C2a", "C3b", "C4", "J_c3b_c4", "J_c2a_c4", "J_c2a_c3b", "J_c2a_c3b_c4"]
# scope after red team 2 (print-measured exit costs remove C3's gain): C3b and every set containing it are not scored
SCORED = ["C2a", "C4", "J_c2a_c4"]
SCORED_WORLDS = ["faithful", "hsim_like"]
CLAIM = {"C2a": "C2a_margin_terciles", "C3b": "C3b_passive_15", "C4": "C4_usdc"}
_MF = {}


def c2a_mult(tag):
    """T x NC multiplier from the builder's cutoffs (cand_sizing.c2_arrays), as hsim's size_fn computes it."""
    if tag not in _MF:
        I = RL.inputs(tag)
        _, LO, HI = CS.c2_arrays(tag, I["pidx"])
        thr32 = I["thr"].astype(np.float32)

        def f(pos, M, th):
            T = M.shape[0]
            ok = pos >= 0
            lo, hi = np.full(T, np.nan), np.full(T, np.nan)
            t32 = np.full(T, np.nan, np.float32)
            lo[ok], hi[ok], t32[ok] = LO[pos[ok]], HI[pos[ok]], thr32[pos[ok]]
            mg = (M.astype(np.float32) - t32[:, None]).astype(np.float64)
            m = np.where(mg < lo[:, None], 0.5, np.where(mg >= hi[:, None], 1.5, 1.0))
            return np.where(np.isnan(lo)[:, None], 1.0, m)
        _MF[tag] = f
    return _MF[tag]


def check_mult(tag, A, n=20000, seed=0):
    """The multiplier matrix must equal cand_sizing.size_fn_for('c2a') at sampled candidate minutes."""
    I = RL.inputs(tag)
    sf = CS.size_fn_for("c2a", tag, I["pidx"])
    pos = I["pidx"].get_indexer(A["idx"])
    tt, cc = np.nonzero(A["cand"])
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(tt), size=min(n, len(tt)), replace=False) if len(tt) else []
    thr32 = I["thr"].astype(np.float32)
    bad = 0
    for j in pick:
        t, c = tt[j], cc[j]
        ref = sf(float(A["M"][t, c] - thr32[pos[t]]), int(pos[t]))
        bad += int(ref != A["mfac"][t, c])
    return bad, len(pick)


def bound_books(A, kw, era, world_opts, rem_extra):
    """My live book's two latency bounds: (daily, tranche frame, info) each."""
    out = {}
    for bound in ("minute", "instant"):
        R = RL.replay(A, theta=kw["theta"], C=kw["C"], bound=bound, policy="engine", rem_extra=rem_extra, **world_opts)
        d, Qo, info = RL.evaluate_live(A, R, kw["theta"], kw["C"], era, kw["cost_mult"])
        out[bound] = (d, Qo, info)
    return out


def plain(out, era, theta):
    s = fsim.lat_share(era, theta)
    return out["minute"][0] + s * (out["instant"][0] - out["minute"][0])


def passive(out, tag, era, kw, N):
    """cand_exits.exit_rem on each bound's tranche frame, blended; returns (daily, instant-bound detail, worst check)."""
    P = RL.inputs(tag)["P"]
    lo, hi = fsim.ERAS[era][1]
    sc = fsim.today_scale(P, lo, hi) if kw["today"] else None
    idx_d = pd.date_range(lo, hi, freq="D")
    res, det_i, worst = {}, None, 0.0
    for b in ("minute", "instant"):
        _, Qo, info = out[b]
        daily, det, chk = CE.exit_rem(Qo, info, tag, P, N, kw["theta"], fsim.HS_BP * kw["cost_mult"],
                                      fsim.IMPACT_Y * kw["cost_mult"], sc)
        worst = max(worst, chk)
        res[b] = daily.reindex(idx_d, fill_value=0.0) / kw["C"]
        if b == "instant":
            det_i = det
    s = fsim.lat_share(era, kw["theta"])
    return res["minute"] + s * (res["instant"] - res["minute"]), det_i, worst


def run(cfgs):
    MX.ensure_frozen()
    CE.ensure_frozen()
    os.makedirs(OUTD, exist_ok=True)
    t0 = time.time()
    for cfg in cfgs:
        kw = CONFIGS[cfg]
        cols, checks = {}, []
        for era in ERAS:
            tag = fsim.ERAS[era][0]
            for phantom in (False, True):
                A0 = RL.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"], phantom=phantom)
                A1 = RL.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"], phantom=phantom, mult_fn=c2a_mult(tag))
                bad, n = check_mult(tag, A1)
                checks.append(dict(cfg=cfg, era=era, phantom=phantom, mult_mismatch=bad, mult_checked=n,
                                   share_x05=float((A1["mfac"][A1["cand"]] == 0.5).mean()),
                                   share_x15=float((A1["mfac"][A1["cand"]] == 1.5).mean())))
                for world, (wph, wopts, rem) in WORLDS.items():
                    if wph != phantom:
                        continue
                    o0 = bound_books(A0, kw, era, wopts, 0)
                    o1 = bound_books(A1, kw, era, wopts, 0)
                    o0c = bound_books(A0, kw, era, wopts, rem) if rem else o0
                    o1c = bound_books(A1, kw, era, wopts, rem) if rem else o1
                    inc = plain(o0, era, kw["theta"])
                    days = inc.index
                    # off switches: exit_rem with N = 0 must reproduce my plain book; c4 with rate 0 is the book
                    d00, _, chk0 = passive(o0, tag, era, kw, 0)
                    checks.append(dict(cfg=cfg, era=era, world=world, n0_max_daily_diff=float((d00 - inc).abs().max()),
                                       market_exit_replication=chk0))
                    c3_0, det0, chk_a = passive(o0c, tag, era, kw, N_PASSIVE)
                    c3_1, det1, chk_b = passive(o1c, tag, era, kw, N_PASSIVE)
                    assert max(chk0, chk_a, chk_b) < 1e-9, (chk0, chk_a, chk_b)
                    ov = lambda o, det, N: CJ.c4_overlay(days, o["instant"][1], det, N, kw["C"], kw["cost_mult"])  # noqa
                    books = {"inc": inc,
                             "C2a": plain(o1, era, kw["theta"]),
                             "C3b": c3_0,
                             "C4": inc + ov(o0, None, 0),
                             "J_c3b_c4": c3_0 + ov(o0c, det0, N_PASSIVE),
                             "J_c2a_c4": plain(o1, era, kw["theta"]) + ov(o1, None, 0),
                             "J_c2a_c3b": c3_1,
                             "J_c2a_c3b_c4": c3_1 + ov(o1c, det1, N_PASSIVE)}
                    for b, ser in books.items():
                        cols[f"{world}|{cfg}|{era}|{b}"] = ser.reindex(days, fill_value=0.0)
                    print(f"{cfg} {era} {world}: inc {fsim.stats(inc, kw['C'], era)['ret_yr']:.4f} "
                          + " ".join(f"{b} {fsim.stats(books[b], kw['C'], era)['ret_yr']:.4f}" for b in BOOKS)
                          + f" ({time.time() - t0:.0f}s)", flush=True)
                del A0, A1
        pd.DataFrame(cols).to_parquet(os.path.join(OUTD, f"daily_{cfg}.parquet"))
        pd.DataFrame(checks).to_csv(os.path.join(OUTD, f"checks_{cfg}.csv"), index=False)


def score_one(inc, cand, C):
    """gates.run's statistics for one candidate (dict era -> daily series), against inc."""
    per, ai, ac = {}, [], []
    for era in ERAS:
        i = inc[era]
        c = cand[era].reindex(i.index, fill_value=0.0)
        d = c - i
        si, sc = fsim.stats(i, C, era), fsim.stats(c, C, era)
        per[era] = dict(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"], cand_ret=sc["ret_yr"], cand_sharpe=sc["sharpe"],
                        d_ret=sc["ret_yr"] - si["ret_yr"], d_sharpe=sc["sharpe"] - si["sharpe"],
                        mean_diff=float(d.mean()), t=float(fsim.nw_t(d)))
        ai.append(i)
        ac.append(c)
    ai, ac = pd.concat(ai), pd.concat(ac)
    d = ac - ai
    ratio = ai.std() / ac.std() if ac.std() > 0 else np.nan
    vm = ac * ratio - ai
    return dict(eras=per, pooled_t=float(fsim.nw_t(d)), pooled_mean=float(d.mean()),
                pooled_t_volmatched=float(fsim.nw_t(vm)), pooled_mean_volmatched=float(vm.mean()),
                era_means_volmatched={e: float((cand[e].reindex(inc[e].index, fill_value=0.0) * ratio - inc[e]).mean())
                                      for e in ERAS})


def gates_return(c):
    g = {"G1": c["S_0.5"]["pooled_t"] >= 2.0, "G2": all(e["mean_diff"] > 0 for e in c["S_0.5"]["eras"].values()),
         "G3": c["S_0.25"]["pooled_t"] >= 2.0 and all(e["mean_diff"] > 0 for e in c["S_0.25"]["eras"].values()),
         "G4": c["base_0.5"]["pooled_mean"] > 0}
    g["pass"] = all(g.values())
    return {k: bool(v) for k, v in g.items()}


def marginal(D, world, full="J_c2a_c3b_c4"):
    comps = {"c2a": "J_c3b_c4", "c3b": "J_c2a_c4", "c4": "J_c2a_c3b"}
    rows = []
    for comp, without in comps.items():
        for cfg in CONFIGS:
            parts, row = [], dict(world=world, component=comp, full=full, without=without, cfg=cfg)
            for era in ERAS:
                a, b = D[f"{world}|{cfg}|{era}|{full}"].dropna(), D[f"{world}|{cfg}|{era}|{without}"].dropna()
                d = a - b.reindex(a.index, fill_value=0.0)
                parts.append(d)
                row[f"{era}_mean_bp"] = float(d.mean() * 1e4)
                row[f"{era}_t"] = float(fsim.nw_t(d))
            dd = pd.concat(parts)
            row["pooled_t"] = float(fsim.nw_t(dd))
            row["pooled_mean_bp"] = float(dd.mean() * 1e4)
            rows.append(row)
    return pd.DataFrame(rows)


def marginal2(D, world, full="J_c2a_c4"):
    """Each component's marginal within J_c2a_c4: the set minus the set without it (descriptive)."""
    rows = []
    for comp, without in (("c2a", "C4"), ("c4", "C2a")):
        for cfg in CONFIGS:
            parts, row = [], dict(world=world, component=comp, full=full, without=without, cfg=cfg)
            for era in ERAS:
                a, b = D[f"{world}|{cfg}|{era}|{full}"].dropna(), D[f"{world}|{cfg}|{era}|{without}"].dropna()
                d = a - b.reindex(a.index, fill_value=0.0)
                parts.append(d)
                row[f"{era}_mean_bp"] = float(d.mean() * 1e4)
                row[f"{era}_t"] = float(fsim.nw_t(d))
            dd = pd.concat(parts)
            row["pooled_t"] = float(fsim.nw_t(dd))
            row["pooled_mean_bp"] = float(dd.mean() * 1e4)
            rows.append(row)
    return pd.DataFrame(rows)


def score():
    D = pd.concat([pd.read_parquet(os.path.join(OUTD, f"daily_{cfg}.parquet")) for cfg in CONFIGS], axis=1)
    out = {}
    for world in SCORED_WORLDS:
        out[world] = {}
        for b in SCORED:
            res = {}
            for cfg, kw in CONFIGS.items():
                inc = {e: D[f"{world}|{cfg}|{e}|inc"].dropna() for e in ERAS}
                cand = {e: D[f"{world}|{cfg}|{e}|{b}"].dropna() for e in ERAS}
                res[cfg] = score_one(inc, cand, kw["C"])
            out[world][b] = dict(configs=res, gates=gates_return(res))
    json.dump(out, open(os.path.join(OUTD, "scores.json"), "w"), indent=1, default=float)
    M = pd.concat([marginal2(D, w) for w in SCORED_WORLDS], ignore_index=True)
    M.to_csv(os.path.join(OUTD, "marginal.csv"), index=False)
    # compact table
    rows = []
    for world, bb in out.items():
        for b, v in bb.items():
            for cfg, r in v["configs"].items():
                row = dict(world=world, book=b, cfg=cfg, pooled_t=r["pooled_t"], t_vm=r["pooled_t_volmatched"],
                           pass_=v["gates"]["pass"])
                for e in ERAS:
                    x = r["eras"][e]
                    row[f"{e}"] = (f"{100 * x['inc_ret']:.1f}->{100 * x['cand_ret']:.1f} / "
                                   f"{x['inc_sharpe']:.2f}->{x['cand_sharpe']:.2f} (t {x['t']:+.2f})")
                rows.append(row)
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUTD, "table.csv"), index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 20, "display.max_colwidth", 60):
        print(T.round(2).to_string(index=False))
        print(M.round(2).to_string(index=False))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2:] or list(CONFIGS))
    elif sys.argv[1] == "score":
        score()
