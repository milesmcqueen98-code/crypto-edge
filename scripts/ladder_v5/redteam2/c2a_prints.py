#!/usr/bin/env python3
"""Red team 2 (ladder v5): C2a re-scored with the print-measured 60-minute exit costs (both C2a and the incumbent
pay the prints' half-spread + first-X slippage instead of the frozen 2 bp + square-root impact; tranches whose exit
minute has no prints keep the frozen model's cost). Uses the per-tranche dumps q (incumbent) and q_c2a (qdump_c2a.py).
Writes reports/ladder_v5/redteam2/c2a_prints.json."""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c3  # noqa: E402
from c3 import fsim, gates  # noqa: E402


def daily(qd, cfg, era, pc):
    c3.QD = qd
    d, _ = c3.book(cfg, era, 0, paths="live", cost="print", pc=pc)
    return d


def main():
    pc = c3.PrintCost()
    out = {"name": "C2a_print_costs", "path": "return", "configs": {}}
    for cfg in gates.CONFIGS:
        kw = gates.CONFIGS[cfg]
        per, diffs = {}, []
        for era in fsim.ERAS:
            cand = daily(os.path.join(c3.RT, "q_c2a"), cfg, era, pc)
            inc = daily(os.path.join(c3.RT, "q"), cfg, era, pc)
            d = cand - inc
            si, sc = fsim.stats(inc, kw["C"], era), fsim.stats(cand, kw["C"], era)
            per[era] = dict(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"], cand_ret=sc["ret_yr"],
                            cand_sharpe=sc["sharpe"], d_ret=sc["ret_yr"] - si["ret_yr"],
                            d_sharpe=sc["sharpe"] - si["sharpe"], mean_diff=float(d.mean()), t=float(fsim.nw_t(d)))
            diffs.append((era, inc, cand))
        ai = pd.concat([x[1] for x in diffs])
        ac = pd.concat([x[2] for x in diffs])
        d = ac - ai
        vm = ac * (ai.std() / ac.std()) - ai
        oi = pd.concat([x[1] for x in diffs if x[0] != "sel"])
        oc = pd.concat([x[2] for x in diffs if x[0] != "sel"])
        out["configs"][cfg] = dict(eras=per, pooled_t=float(fsim.nw_t(d)), pooled_mean=float(d.mean()),
                                   pooled_t_volmatched=float(fsim.nw_t(vm)), pooled_mean_volmatched=float(vm.mean()),
                                   era_means_volmatched={e: float((c * (ai.std() / ac.std()) - i).mean())
                                                         for e, i, c in diffs},
                                   oos_t=float(fsim.nw_t(oc - oi)),
                                   oos_t_volmatched=float(fsim.nw_t(oc * (oi.std() / oc.std()) - oi)))
    out["gates"] = gates.gates(out, "return")
    # share of C2a's remainder dollars whose exit minute has prints (the rest keep the frozen model's cost)
    ev = pd.read_csv(os.path.join(c3.RT, "events_exit.csv"), parse_dates=["fill_t"])
    keys = set(zip(ev.coin, ev.fill_t))
    cov = {}
    for cfg in gates.CONFIGS:
        tot = hit = 0.0
        for era in fsim.ERAS:
            for b in ("minute", "instant"):
                Q = pd.read_parquet(os.path.join(c3.RT, "q_c2a", f"inc_{cfg}_{era}_{b}.parquet"))
                rem = (Q.fill - Q.tp_fill).clip(lower=0).to_numpy()
                inn = np.array([(c, pd.Timestamp(t)) in keys for c, t in zip(Q.coin, Q.fill_t)])
                tot += rem.sum()
                hit += rem[inn].sum()
        cov[cfg] = hit / tot if tot else np.nan
    out["c2a_remainder_share_with_prints"] = cov
    json.dump(out, open(os.path.join(c3.RT, "c2a_prints.json"), "w"), indent=1, default=float)
    print(gates.summary(out))
    for cfg, v in out["configs"].items():
        print(f"  {cfg}: out-of-sample (chk + early) t {v['oos_t']:+.2f} (vol-matched {v['oos_t_volmatched']:+.2f})")


if __name__ == "__main__":
    main()
