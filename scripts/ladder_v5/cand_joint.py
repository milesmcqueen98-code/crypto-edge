#!/usr/bin/env python3
"""Ladder v5: the joint re-test of the candidates that passed the gates (reports/ladder_v5_prereg.md, step 4).

Components, each exactly as its builder implemented and logged it (code copied unchanged from its branch):
  c2a  meta-label sizing by the AI margin's tercile (scripts/ladder_v5/cand_sizing.py, branch ladder/sizing)
  c3a  passive time exit, 5 minutes   (scripts/ladder_v5/cand_exits.py, branch ladder/exits)
  c3b  passive time exit, 15 minutes  (same)
  c4   idle cash held as USDC         (scripts/ladder_v5/cand_cashvenue.py, branch ladder/cashvenue)
The joint book: hsim.book with C2a's size_fn (the live cash rule sees the C2a sizes), then each latency bound's tranche
frame goes through C3's passive exit (cand_exits.exit_rem), blended as hsim.book blends; then C4's daily overlay
(r_usdc + m) x (1 - positions / C) from cand_cashvenue's own functions, with positions from the joint book's
instant-bound tranche frame plus, under C3, the dollar-minutes each remainder stays held while its passive sell rests
(cand_exits' det.xmin), so C4 sees the C2a sizes and the C3 holding times.
Checks before any logged trial: (1) all components off reproduce the cached incumbent exactly; (2) C2a alone, C3b
alone and C4 alone reproduce their logged trials' per-era return and Sharpe (reports/ladder_v5/trials/<name>.json
from the builder branches, copied into reports/ladder_v5/joint/ref/).
Each run also saves every combo's daily returns (reports/ladder_v5/joint/daily.parquet) and the marginal contribution
of each component within the largest combo run (full set minus the set without it; joint/marginal.csv).
usage: python scripts/ladder_v5/cand_joint.py check | run <combo> [<combo> ...]     combo e.g. c2a+c3b+c4
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gates  # noqa: E402  (first: fsim puts scripts/hunt, which has its own gates.py, ahead of this folder)
import fsim  # noqa: E402
import hsim  # noqa: E402
import cand_sizing as CS  # noqa: E402
import cand_exits as CE  # noqa: E402
import cand_cashvenue as CV  # noqa: E402  (checks the frozen dataset's sha256 on import)

for _m in (gates, fsim, hsim, CS, CE, CV):
    assert os.path.dirname(os.path.abspath(_m.__file__)) == HERE, _m.__file__

OUTD = os.path.join(fsim.OUT, "joint")


def c4_overlay(days, Q, det, N, C, cost_mult):
    """C4's daily return on capital: (r_usdc + m) x (1 - positions / C) (cand_cashvenue.c4_book's formula and functions).
    positions: the day's time-average open positions at cost from the instant-bound tranche frame Q; under C3 (N > 0)
    plus each remainder's extra dollar-minutes while its passive sell rests (det.xmin), on the day its window starts."""
    pos = CV.day_positions(Q, days)
    if N > 0:
        on = det.on.to_numpy() & (det.xmin.to_numpy() > 0)
        start = (pd.Series(det.fill_t.to_numpy()[on]) + pd.Timedelta(minutes=fsim.sim.H)).dt.floor("D").to_numpy()
        extra = pd.Series(det.xmin.to_numpy()[on] / 1440.0, index=start).groupby(level=0).sum()
        pos = pos + extra.reindex(days, fill_value=0.0)
    free = 1.0 - pos.to_numpy(float) / C
    r = CV.usdc_reward(days) * (0.5 if cost_mult == CV.UNVERIFIED else 1.0)
    m = CV.usdc_mtm(days)
    return pd.Series((r + m) * free, index=days)


def make(sizing="off", N=0, c4=False):
    """Joint book: sizing in {"off", "c2a"}; N = passive minutes (0 = the market exit at minute 60); c4 = USDC cash."""
    def book_fn(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0):
        tag, (lo, hi) = fsim.ERAS[era]
        if pan is None:
            pan = gates.data(tag)[1]
        f = None if sizing == "off" else CS.size_fn_for(sizing, tag, pan[0])
        d, out = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_, size_fn=f)
        det_i = None
        if N > 0:
            sc = fsim.today_scale(P, lo, hi) if today else None
            hs_bp, impact_y = fsim.HS_BP * cost_mult, fsim.IMPACT_Y * cost_mult
            idx_d = pd.date_range(lo, hi, freq="D")
            res = {}
            for name in ("minute", "instant"):
                Q, _, info, _ = out[name]
                daily, det, chk = CE.exit_rem(Q, info, tag, P, N, theta, hs_bp, impact_y, sc)
                assert chk < 1e-9, f"market-exit replication failed: {chk}"
                res[name] = daily.reindex(idx_d, fill_value=0.0) / C
                if name == "instant":
                    det_i = det
            s = fsim.lat_share(era, theta)
            d = res["minute"] + s * (res["instant"] - res["minute"])
        if c4:
            d = d + c4_overlay(d.index, out["instant"][0], det_i, N, C, cost_mult)
        return d
    return book_fn


def parse(combo):
    parts = set(combo.split("+"))
    sizing = "c2a" if "c2a" in parts else "off"
    N = 15 if "c3b" in parts else 5 if "c3a" in parts else 0
    unknown = parts - {"c2a", "c3a", "c3b", "c4"}
    assert not unknown, unknown
    assert not {"c3a", "c3b"} <= parts, "one C3 variant at a time"
    return sizing, N, "c4" in parts


def check(strict=False):
    """Reproduction checks; strict (before logged trials): stop unless every check holds to 1e-9."""
    CE.ensure_frozen()
    lines, bad = [], []
    for era in fsim.ERAS:
        tag = fsim.ERAS[era][0]
        P, pan = gates.data(tag)
        inc = gates.incumbent_cached(era, "S_0.5")
        d = make("off", 0, False)(P, era, pan=pan, adv_=gates.adv(tag, era), **gates.CONFIGS["S_0.5"])
        x = float(np.abs(d.reindex(inc.index, fill_value=0.0) - inc).max())
        bad += [f"all off, {era}"] if x > 1e-9 else []
        lines.append(f"all off vs cached incumbent, {era}: max daily difference {x:.2e}")
    for name, sizing, N, c4 in (("C2a_margin_terciles", "c2a", 0, False), ("C3b_passive_15", "off", 15, False),
                                ("C4_usdc", "off", 0, True)):
        ref = json.load(open(os.path.join(OUTD, "ref", f"{name}.json")))["configs"]["S_0.5"]["eras"]
        for era in fsim.ERAS:
            tag = fsim.ERAS[era][0]
            P, pan = gates.data(tag)
            d = make(sizing, N, c4)(P, era, pan=pan, adv_=gates.adv(tag, era), **gates.CONFIGS["S_0.5"])
            st = fsim.stats(d, 250e3, era)
            if abs(st["ret_yr"] - ref[era]["cand_ret"]) > 1e-9 or abs(st["sharpe"] - ref[era]["cand_sharpe"]) > 1e-9:
                bad.append(f"{name}, {era}")
            lines.append(f"{name} alone, {era}: return {st['ret_yr']:.6f} vs logged {ref[era]['cand_ret']:.6f}; "
                         f"Sharpe {st['sharpe']:.6f} vs {ref[era]['cand_sharpe']:.6f}")
    txt = "\n".join(lines)
    os.makedirs(OUTD, exist_ok=True)
    open(os.path.join(OUTD, "check.txt"), "w").write(txt + "\n")
    print(txt, flush=True)
    if strict and bad:
        raise SystemExit(f"reproduction checks failed: {bad}; no trial logged")


def _cfg_name(kw):
    for k, v in gates.CONFIGS.items():
        if all(kw.get(x) == y for x, y in v.items()):
            return k
    raise KeyError(kw)


def _capture(name, fn, rows):
    def g(P, era, **kw):
        d = fn(P, era, **kw)
        rows.append(pd.DataFrame(dict(name=name, cfg=_cfg_name(kw), era=era, date=d.index, r=d.to_numpy(float))))
        return d
    return g


def marginal(daily):
    """Each component's contribution within the largest combo run: full minus the combo without it (same days),
    pooled Newey-West t (5 lags, fsim.nw_t) and mean by era, per configuration. Descriptive; the gates are run()'s."""
    names = sorted(daily.name.unique(), key=lambda n: -len(n.split("_")))
    full = names[0]
    comps = full[2:].split("_")
    rows = []
    for c in comps:
        loo = "J_" + "_".join(x for x in comps if x != c)
        if loo == "J_" or loo not in names:
            continue
        for cfg in daily.cfg.unique():
            a = daily[(daily.name == full) & (daily.cfg == cfg)].set_index(["era", "date"]).r
            b = daily[(daily.name == loo) & (daily.cfg == cfg)].set_index(["era", "date"]).r
            d = (a - b.reindex(a.index, fill_value=0.0))
            row = dict(component=c, full=full, without=loo, cfg=cfg, pooled_t=float(fsim.nw_t(d.reset_index(drop=True))),
                       pooled_mean_bp=float(d.mean() * 1e4))
            for era in fsim.ERAS:
                de = d.xs(era, level="era")
                row[f"{era}_mean_bp"] = float(de.mean() * 1e4)
                row[f"{era}_t"] = float(fsim.nw_t(de.reset_index(drop=True)))
            rows.append(row)
    return pd.DataFrame(rows)


def run(combos):
    CE.ensure_frozen()
    rows = []
    for combo in combos:
        sizing, N, c4 = parse(combo)
        name = "J_" + combo.replace("+", "_")
        out = gates.run(name, _capture(name, make(sizing, N, c4), rows), path="return", note=f"joint re-test: {combo}")
        print(gates.summary(out), flush=True)
    daily = pd.concat(rows, ignore_index=True)
    os.makedirs(OUTD, exist_ok=True)
    daily.to_parquet(os.path.join(OUTD, "daily.parquet"))
    m = marginal(daily)
    m.to_csv(os.path.join(OUTD, "marginal.csv"), index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(m.round(3).to_string(index=False), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "check":
        check()
    elif sys.argv[1] == "run":
        check(strict=True)
        run(sys.argv[2:])
