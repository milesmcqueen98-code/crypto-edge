#!/usr/bin/env python3
"""Ladder v6 (exits): the single read of the frozen rule on the out-of-sample eras (check Apr - Nov 5 2026, 2022-23).

Run once, after the freeze commit (reports/ladder_v6x/frozen_rule.json). The rule is applied as it would run live:
each quarter's coefficients are fitted on the selection era plus the same era's earlier quarters (deviation log,
2026-11-08 20:16 UTC); X2 / X12 are scored on the pessimistic cash bound (every remainder held its maximum extension in
the cash rule). Gates (ladder v5's, on the out-of-sample eras): G1 pooled paired Newey-West t >= 2 over check +
2022-23 at S* theta 0.5 on the declared path; G2 mean daily difference > 0 in each out-of-sample era; G3 the same at
theta 0.25 (pooled t >= 2, both eras positive); G4 base pooled mean > 0. The selection era is reported, no weight.
Writes reports/ladder_v6x/oos/{result.json, daily.parquet, summary.txt}.
usage: python scripts/ladder_v6x/oos.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exits as X  # noqa: E402
import rules as RU  # noqa: E402
from lsim import CONFIGS, OUT, fsim  # noqa: E402

OOS = os.path.join(OUT, "oos")
CFGS = ("S_0.5", "S_0.25", "base_0.5", "cap_1M")
OUT_ERAS = ("chk", "early")


def stack_fit(parts, lever, inputs, weights):
    """OLS / WLS over several (book, tranche mask) parts."""
    As, ys, ws = [], [], []
    for x, rows in parts:
        y, ms = RU.gain(x, lever)
        F = RU.feats(x, ms, inputs)
        ok = np.isfinite(y) & rows[:, None]
        As.append(np.column_stack([np.ones(ok.sum()), F[ok]]))
        ys.append(y[ok])
        ws.append(np.sqrt(x.R[:, ms][ok]) if weights == "usd" else np.ones(ok.sum()))
    A, y, w = np.vstack(As), np.concatenate(ys), np.concatenate(ws)
    return np.linalg.lstsq(A * w[:, None], y * w, rcond=None)[0]


def era_betas(era, spec):
    kappa, lever, inputs = spec["kappa"], spec["lever"], tuple(spec["inputs"])
    sel = RU.books("S_0.5", "sel", kappa, 0)["instant"]
    cur = RU.books("S_0.5", era, kappa, 0)["instant"]
    end = cur.Q.fill_t + pd.Timedelta(minutes=X.HMAX + 1)
    q = RU.quarters(cur)
    out = {}
    for qq in sorted(q.unique()):
        rows = (end <= qq.start_time).to_numpy()
        out[qq] = stack_fit([(sel, np.ones(len(sel.Q), bool)), (cur, rows)], lever, inputs, spec["weights"])
    return out


def candidate(cfg, era, spec, betas):
    kappa, lever, inputs, h = spec["kappa"], spec["lever"], tuple(spec["inputs"]), spec["h"]
    ext = spec["cash_ext"]
    inc = X.blended(RU.books(cfg, era, kappa, 0), X.at60)
    bk = RU.books(cfg, era, kappa, ext)
    cand = X.blended(bk, lambda x: RU.decide(x, lever, RU.beta_rows(x, betas, len(inputs)), h, inputs))
    return inc, cand.reindex(inc.index, fill_value=0.0)


def main():
    spec = json.load(open(os.path.join(OUT, "frozen_rule.json")))
    os.makedirs(OOS, exist_ok=True)
    betas = {era: era_betas(era, spec) for era in OUT_ERAS}
    res, daily = {"spec": spec, "configs": {}}, {}
    for cfg in CFGS:
        per, pool_i, pool_c = {}, [], []
        for era in OUT_ERAS:
            inc, cand = candidate(cfg, era, spec, betas[era])
            daily[f"{cfg}|{era}|inc"], daily[f"{cfg}|{era}|cand"] = inc, cand
            per[era] = X.compare(inc, cand, cfg, era)
            pool_i.append(inc)
            pool_c.append(cand)
        ai, ac = pd.concat(pool_i), pd.concat(pool_c)
        d = ac - ai
        vm = ac * (ai.std() / ac.std()) - ai
        res["configs"][cfg] = dict(eras=per, pooled_t=float(fsim.nw_t(d)), pooled_mean_bp=1e4 * float(d.mean()),
                                   pooled_t_volmatched=float(fsim.nw_t(vm)),
                                   era_means_volmatched_bp={e: 1e4 * float((c * (ai.std() / ac.std()) - i).mean())
                                                            for e, i, c in zip(OUT_ERAS, pool_i, pool_c)})
    c = res["configs"]
    vmp = spec.get("path", "return") == "sharpe"
    key = "pooled_t_volmatched" if vmp else "pooled_t"

    def pos(cfg):
        if vmp:
            return all(v > 0 for v in c[cfg]["era_means_volmatched_bp"].values())
        return all(e["mean_bp"] > 0 for e in c[cfg]["eras"].values())
    g = dict(G1=c["S_0.5"][key] >= 2.0, G2=pos("S_0.5"), G3=c["S_0.25"][key] >= 2.0 and pos("S_0.25"),
             G4=(c["base_0.5"]["pooled_mean_bp"] if not vmp else
                 np.mean(list(c["base_0.5"]["era_means_volmatched_bp"].values()))) > 0)
    g = {k: bool(v) for k, v in g.items()}
    g["pass"] = all(g.values())
    res["gates"] = g
    res["betas"] = {era: {str(q): np.round(b, 4).tolist() for q, b in bb.items()} for era, bb in betas.items()}
    json.dump(res, open(os.path.join(OOS, "result.json"), "w"), indent=1, default=float)
    pd.DataFrame(daily).to_parquet(os.path.join(OOS, "daily.parquet"))
    lines = [f"frozen rule {spec['name']}: gates {g}"]
    for cfg, v in c.items():
        lines.append(f"  {cfg}: pooled t {v['pooled_t']:+.2f} (vol-matched {v['pooled_t_volmatched']:+.2f}), "
                     f"mean {v['pooled_mean_bp']:+.2f} bp/day")
        for era, e in v["eras"].items():
            lines.append(f"    {era:5s} inc {100 * e['inc_ret']:5.1f}% / {e['inc_sharpe']:.2f}  cand {100 * e['ret']:5.1f}% / "
                         f"{e['sharpe']:.2f}  t {e['t']:+.2f}  mean {e['mean_bp']:+.2f} bp/day")
    open(os.path.join(OOS, "summary.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
