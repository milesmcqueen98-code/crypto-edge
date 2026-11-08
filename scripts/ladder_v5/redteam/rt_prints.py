#!/usr/bin/env python3
"""Red team (ladder v5): my engine-faithful incumbent and C2a with red team 2's print-measured exit costs.

The 60-minute market exit of every remainder (fill - take-profit part) pays red team 2's print-measured half-spread +
first-X slippage at that exit (scripts/ladder_v5/redteam2/c3.py PrintCost on reports/ladder_v5/prints_rt2_exit.csv and
prints_rt2_coin.csv, unchanged; size / today's volume factor in S*; beyond the largest size with data the larger of a
linear extrapolation and the model's 1x impact) instead of the model's half-spread + square-root impact; an exit with
no prints keeps the model's cost (x cost_mult). Taker fee, take-profit legs and entry costs unchanged. This is c3.py's
tranche_pnl with N = 0 and cost "print", reimplemented for my tranche frames and checked against c3.book on the same
frames (written as c3's dump format); with the model's cost it reproduces my book exactly.
usage: python scripts/ladder_v5/redteam/rt_prints.py run <cfg> [...] | score
"""
import json
import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LV5 = os.path.dirname(HERE)
sys.path.insert(0, LV5)
import gates  # noqa: E402,F401  (first, from scripts/ladder_v5)
sys.path.insert(0, HERE)
import rt_winners as RW  # noqa: E402
import rt_live as RL  # noqa: E402
import fsim  # noqa: E402
sys.path.insert(0, os.path.join(LV5, "redteam2"))
import c3 as RT2  # noqa: E402

OUTD = os.path.join(RL.OUT, "prints")
CONFIGS = RW.CONFIGS
ERAS = RW.ERAS
_PC = {}


def pcost():
    if "pc" not in _PC:
        _PC["pc"] = RT2.PrintCost()
    return _PC["pc"]


def rem_daily(Q, info, cfg, era, C, cost="print"):
    """Daily P&L / C of a tranche frame with the remainders' market exit at minute 60 under `cost`; and the share of
    remainder dollars priced from prints."""
    kw = CONFIGS[cfg]
    tag, (lo, hi) = fsim.ERAS[era]
    tk_fee = info["taker_bp"] / 1e4
    hs = fsim.HS_BP * kw["cost_mult"] / 1e4
    y = fsim.IMPACT_Y * kw["cost_mult"]
    sc = fsim.today_scale(RL.inputs(tag)["P"], lo, hi) if kw["today"] else {}
    rem = np.maximum((Q.fill - Q.tp_fill).to_numpy(), 0.0)
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    fsc = Q.coin.map(sc).fillna(1.0).to_numpy() if sc else np.ones(len(Q))
    g60 = Q.g60.to_numpy() / 1e4
    coin, fill_t = Q.coin.to_numpy(), Q.fill_t.to_numpy()
    pc = pcost()
    pnl = np.zeros(len(Q))
    hit = 0.0
    for i in np.nonzero(rem > 0)[0]:
        R = rem[i]
        model = hs + y * vol_d[i] * np.sqrt(R / adv[i])
        if cost == "print":
            fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(R / adv[i])
            ci = pc.cost(coin[i], pd.Timestamp(fill_t[i]), 0, R / fsc[i], fb_bp=fb)
            if np.isfinite(ci):
                hit += R
            else:
                ci = model
        else:
            ci = model
        pnl[i] = R * (g60[i] - tk_fee - ci)
    idx = pd.date_range(lo, hi, freq="D")
    ex_day = (Q.fill_t + pd.Timedelta(minutes=60)).dt.floor("D").to_numpy()
    s = pd.concat([pd.Series((Q.pnl_tp - Q.entry_cost).to_numpy(), index=Q.tp_t.dt.floor("D").to_numpy()),
                   pd.Series(pnl[rem > 0], index=ex_day[rem > 0])]).groupby(level=0).sum()
    return s.reindex(idx, fill_value=0.0) / C, (hit / rem.sum() if rem.sum() > 0 else np.nan), rem.sum()


def check_against_rt2(out, cfg, era, C):
    """c3.book (red team 2's code, unchanged) on my two tranche frames written in its dump format."""
    d = tempfile.mkdtemp(prefix="rt2q_")
    rows = []
    for b in ("minute", "instant"):
        _, Qo, info = out[b]
        Qo.to_parquet(os.path.join(d, f"inc_{cfg}_{era}_{b}.parquet"))
        rows.append(dict(cfg=cfg, era=era, bound=b, maker_bp=info["maker_bp"], taker_bp=info["taker_bp"]))
    pd.DataFrame(rows).to_csv(os.path.join(d, "summary.csv"), index=False)
    q0 = RT2.QD
    RT2.QD = d
    try:
        _, d_inc = RT2.book(cfg, era, 0, paths="frozen", cost="print", pc=pcost())
    finally:
        RT2.QD = q0
    return d_inc


def run(cfgs):
    RW.MX.ensure_frozen()
    os.makedirs(OUTD, exist_ok=True)
    t0 = time.time()
    for cfg in cfgs:
        kw = CONFIGS[cfg]
        cols, checks = {}, []
        for era in ERAS:
            tag = fsim.ERAS[era][0]
            A0 = RL.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"])
            A1 = RL.era_arrays(tag, era, kw["theta"], kw["C"], kw["today"], mult_fn=RW.c2a_mult(tag))
            s = fsim.lat_share(era, kw["theta"])
            for name, A in (("inc", A0), ("C2a", A1)):
                out = RW.bound_books(A, kw, era, {}, 0)
                plain = RW.plain(out, era, kw["theta"])
                res = {}
                for cost in ("model", "print"):
                    dd, cov, remusd = {}, {}, {}
                    for b in ("minute", "instant"):
                        _, Qo, info = out[b]
                        dd[b], cov[b], remusd[b] = rem_daily(Qo, info, cfg, era, kw["C"], cost)
                    res[cost] = dd["minute"] + s * (dd["instant"] - dd["minute"])
                    if cost == "print":
                        checks.append(dict(cfg=cfg, era=era, book=name, print_share_minute=cov["minute"],
                                           print_share_instant=cov["instant"], rem_usd_instant=remusd["instant"]))
                checks[-1]["model_offswitch_max_diff"] = float((res["model"] - plain).abs().max())
                if cfg == "S_0.5" and era == "chk":
                    d_rt2 = check_against_rt2(out, cfg, era, kw["C"])
                    checks[-1]["rt2_code_max_diff"] = float((res["print"] - d_rt2).abs().max())
                cols[f"{cfg}|{era}|{name}|model"] = res["model"]
                cols[f"{cfg}|{era}|{name}|print"] = res["print"]
                print(f"{cfg} {era} {name}: model {fsim.stats(res['model'], kw['C'], era)['ret_yr']:.4f} print "
                      f"{fsim.stats(res['print'], kw['C'], era)['ret_yr']:.4f} {checks[-1]} ({time.time() - t0:.0f}s)",
                      flush=True)
            del A0, A1
        pd.DataFrame(cols).to_parquet(os.path.join(OUTD, f"daily_{cfg}.parquet"))
        pd.DataFrame(checks).to_csv(os.path.join(OUTD, f"checks_{cfg}.csv"), index=False)


def score():
    D = pd.concat([pd.read_parquet(os.path.join(OUTD, f"daily_{cfg}.parquet")) for cfg in CONFIGS], axis=1)
    out = {}
    for cost in ("model", "print"):
        res = {}
        for cfg, kw in CONFIGS.items():
            inc = {e: D[f"{cfg}|{e}|inc|{cost}"].dropna() for e in ERAS}
            cand = {e: D[f"{cfg}|{e}|C2a|{cost}"].dropna() for e in ERAS}
            res[cfg] = RW.score_one(inc, cand, kw["C"])
        out[cost] = dict(configs=res, gates=RW.gates_return(res))
    json.dump(out, open(os.path.join(OUTD, "scores.json"), "w"), indent=1, default=float)
    for cost, v in out.items():
        print(cost, v["gates"])
        for cfg, r in v["configs"].items():
            print(f"   {cfg:8s} t {r['pooled_t']:+.2f} vm {r['pooled_t_volmatched']:+.2f} | " + " | ".join(
                f"{e} {100 * x['inc_ret']:.1f}%/{x['inc_sharpe']:.2f} -> {100 * x['cand_ret']:.1f}%/"
                f"{x['cand_sharpe']:.2f} (t {x['t']:+.2f})" for e, x in r["eras"].items()))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2:] or list(CONFIGS))
    elif sys.argv[1] == "score":
        score()
