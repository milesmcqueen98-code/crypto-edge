#!/usr/bin/env python3
"""Red team 2 (ladder v5): C3 re-tested with the cost and fill numbers the Coinbase prints support.

Inputs: the print-derived tables from prints_exit.py (reports/ladder_v5/prints_rt2_{exit,passive,coin}.csv), the
incumbent dumps (qdump.py) and C3's re-implementation (c3.py). Outputs in reports/ladder_v5/redteam2/:
  c3_costs.csv      the 60-minute market exit's cost per remainder dollar, model vs prints, by era and configuration
  c3_passive.csv    the passive fill model vs prints, by era and tick
  c3_prints.json    C3a / C3b scored with print costs and/or print fills (gates.run's statistics)
  c3_decomp.csv     per remainder dollar: passive fill share and C3 - incumbent (bp) by era, configuration and case
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c3  # noqa: E402
from c3 import fsim, gates  # noqa: E402

RT = c3.RT


def events():
    return pd.read_csv(os.path.join(RT, "events_exit.csv"), parse_dates=["fill_t"])


class PrintCap:
    """Peg gain and USD printed at or above peg + tick, per passive minute, from prints_rt2_passive.csv."""

    def __init__(self):
        E = events()
        P = pd.read_csv(os.path.join(fsim.OUT, "prints_rt2_passive.csv"))
        P = P.merge(E[["event_id", "coin", "fill_t", "tick_model", "tick_real"]], on="event_id")
        self.tab = {}
        for eid, g in P.groupby("event_id"):
            g = g.sort_values("j").set_index("j").reindex(range(1, c3.NMAX + 1))
            r0 = g.dropna(subset=["coin"]).iloc[0]
            self.tab[(r0.coin, pd.Timestamp(r0.fill_t))] = dict(
                peg_ref=g.peg_ref.to_numpy(float), mod=g.v_gt_mod.to_numpy(float),
                real=g.v_gt_real.to_numpy(float), tick_model=float(r0.tick_model), tick_real=float(r0.tick_real))

    def __call__(self, Q, era, tick):
        n = len(Q)
        pg = np.full((n, c3.NMAX), np.nan)
        cap = np.full((n, c3.NMAX), np.nan)
        lvl = Q.lvl.to_numpy()
        for i, (coin, ft) in enumerate(zip(Q.coin, Q.fill_t)):
            v = self.tab.get((coin, pd.Timestamp(ft)))
            if v is None:
                continue
            tk = v["tick_model"] if tick == "model" else v["tick_real"]
            pg[i] = np.log((v["peg_ref"] + tk) / lvl[i])
            cap[i] = v["mod"] if tick == "model" else v["real"]
        return pg, cap


def cost_table(pc):
    """Per remainder dollar of the incumbent's 60-minute market exit: model half-spread and impact vs prints."""
    rows = []
    for cfg in ("S_0.5", "base_0.5", "cap_1M"):
        kw = gates.CONFIGS[cfg]
        for era in fsim.ERAS:
            Q = c3.load_q(cfg, era, "instant")
            Q = Q[(Q.fill - Q.tp_fill) > 0].reset_index(drop=True)
            rem = (Q.fill - Q.tp_fill).to_numpy()
            sc = c3.today_scale(era) if kw["today"] else {}
            fsc = Q.coin.map(sc).fillna(1.0).to_numpy() if sc else np.ones(len(Q))
            adv = Q.adv.to_numpy()
            vol_d = Q.vol_d.to_numpy()
            hs_m = fsim.HS_BP * kw["cost_mult"] * np.ones(len(Q))
            imp_m = 1e4 * fsim.IMPACT_Y * kw["cost_mult"] * vol_d * np.sqrt(rem / adv)
            hs_p, sl_p, sl_t, y_imp = [], [], [], []
            for i in range(len(Q)):
                v = pc.tab.get((Q.coin.iat[i], pd.Timestamp(Q.fill_t.iat[i]), 0))
                if v is None or not np.isfinite(v[0]):
                    hs_p.append(np.nan), sl_p.append(np.nan), sl_t.append(np.nan), y_imp.append(np.nan)
                    continue
                fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(rem[i] / adv[i])
                c_era = 1e4 * pc.cost(Q.coin.iat[i], Q.fill_t.iat[i], 0, rem[i], fb_bp=fb) - v[0]
                c_tod = 1e4 * pc.cost(Q.coin.iat[i], Q.fill_t.iat[i], 0, rem[i] / fsc[i], fb_bp=fb) - v[0]
                hs_p.append(v[0]), sl_p.append(c_era), sl_t.append(c_tod)
                base_imp = 1e4 * vol_d[i] * np.sqrt(rem[i] / (adv[i] / fsc[i]))   # era ADV
                y_imp.append(c_era / base_imp if base_imp > 0 else np.nan)
            hs_p, sl_p, sl_t, y_imp = map(np.array, (hs_p, sl_p, sl_t, y_imp))
            ok = np.isfinite(hs_p)
            w = rem[ok] / rem[ok].sum()
            rows.append(dict(cfg=cfg, era=era, tranches=len(Q), with_prints=int(ok.sum()),
                             rem_usd_median=float(np.median(rem)), rem_usd_mean=float(rem.mean()),
                             model_hs_bp=float((w * hs_m[ok]).sum()), model_impact_bp=float((w * imp_m[ok]).sum()),
                             model_total_bp=float((w * (hs_m[ok] + imp_m[ok])).sum()),
                             print_hs_bp=float((w * hs_p[ok]).sum()), print_slip_bp=float((w * sl_p[ok]).sum()),
                             print_total_bp=float((w * (hs_p[ok] + sl_p[ok])).sum()),
                             print_slip_today_bp=float((w * sl_t[ok]).sum()),
                             print_total_today_bp=float((w * (hs_p[ok] + sl_t[ok])).sum()),
                             implied_y=float(np.nansum(w * np.nan_to_num(y_imp[ok])) /
                                             max(1e-12, np.sum(w[np.isfinite(y_imp[ok])]))),
                             print_hs_median_bp=float(np.median(hs_p[ok])),
                             print_slip_median_bp=float(np.median(sl_p[ok]))))
    return pd.DataFrame(rows)


def passive_table(pcap):
    """The passive fill model vs prints over the minutes the remainders rest (S* theta 0.5 tranches, instant bound):
    share of minutes with a one-tick trade-through and USD per minute available above the peg."""
    P = pd.read_csv(os.path.join(fsim.OUT, "prints_rt2_passive.csv"))
    E = events()
    P = P.merge(E, on="event_id")
    rows = []
    for era in fsim.ERAS:
        tag = fsim.ERAS[era][0]
        Q = c3.load_q("S_0.5", era, "instant")
        Q = Q[(Q.fill - Q.tp_fill) > 0].drop_duplicates(["coin", "fill_t"]).reset_index(drop=True)
        for tick in ("model", "real"):
            cl, hi, lo, vo, tkk = c3.live_paths(Q, tag, tick)
            _, ccap = c3.candle_cap(cl, hi, lo, vo, tkk, Q.lvl.to_numpy())
            pg, pcp = pcap(Q, era, tick)
            nm = "mod" if tick == "model" else "real"
            key = pd.DataFrame({"coin": Q.coin, "fill_t": Q.fill_t})
            sub = key.merge(P, on=["coin", "fill_t"], how="left")
            cu = sub.pivot_table(index=["coin", "fill_t"], columns="j", values=f"cap_u_{nm}")
            cu = cu.reindex(pd.MultiIndex.from_frame(key)).to_numpy()
            ok = np.isfinite(pcp)
            rows.append(dict(era=era, tick=tick, minutes=int(ok.sum()),
                             through_candle=float((ccap[ok] > 0).mean()), through_prints=float((pcp[ok] > 0).mean()),
                             usd_candle_formula=float(ccap[ok].mean()),
                             usd_prints_same_formula=float(np.nanmean(np.where(ok, cu, np.nan))),
                             usd_prints_actual=float(pcp[ok].mean()),
                             actual_over_candle=float(pcp[ok].sum() / max(ccap[ok].sum(), 1e-9)),
                             minute1_through_candle=float((ccap[:, 0][ok[:, 0]] > 0).mean()),
                             minute1_through_prints=float((pcp[:, 0][ok[:, 0]] > 0).mean())))
    T = pd.DataFrame(rows)
    # aggressor side of the volume above the peg and timing of the trade-through (all events, real tick)
    g = P[P.v_gt_real > 0]
    extra = dict(share_takerbuy_above_peg_real=float(g.v_gtb_real.sum() / g.v_gt_real.sum()),
                 median_seconds_to_through_real=float(g.t_gt_real.median()),
                 share_first_print_at_or_above_peg_real=float(
                     (P.first_px >= P.peg_ref + P.tick_real * (1 - 1e-9)).mean()))
    return T, extra


def decomp(cases):
    rows = []
    for name, (N, opt) in cases.items():
        for cfg in ("S_0.5", "base_0.5"):
            for era in fsim.ERAS:
                det = []
                Q = c3.load_q(cfg, era, "instant")
                c3.tranche_pnl(Q, cfg, era, "instant", N, detail=det, **opt)
                D = pd.DataFrame(det)
                if not len(D):
                    continue
                rows.append(dict(case=name, cfg=cfg, era=era, rem_usd=D.rem.sum(),
                                 passive_share=D.passive.sum() / D.rem.sum(),
                                 c3_minus_inc_bp=1e4 * (D.pnl_c3 - D.pnl_inc).sum() / D.rem.sum(),
                                 inc_exit_cost_bp=1e4 * (D.cost_inc * D.rem).sum() / D.rem.sum()))
    return pd.DataFrame(rows)


def main():
    pc = c3.PrintCost()
    pcap = PrintCap()
    C = cost_table(pc)
    C.to_csv(os.path.join(RT, "c3_costs.csv"), index=False)
    print(C.round(2).to_string(index=False))
    T, extra = passive_table(pcap)
    T.to_csv(os.path.join(RT, "c3_passive.csv"), index=False)
    print(T.round(3).to_string(index=False))
    print(extra)
    cases = {
        "model_cost_candle_fill": dict(paths="live", tick="model"),
        "model_cost_print_fill_modeltick": dict(paths="live", tick="model", cap="print", pcap=pcap, share=True),
        "model_cost_print_fill_realtick": dict(paths="live", tick="real", cap="print", pcap=pcap, share=True),
        "print_cost_candle_fill": dict(paths="live", tick="model", cost="print", pc=pc),
        "print_cost_print_fill_realtick": dict(paths="live", tick="real", cap="print", pcap=pcap, share=True,
                                               cost="print", pc=pc),
        "print_cost_x2_print_fill_realtick": dict(paths="live", tick="real", cap="print", pcap=pcap, share=True,
                                                  cost="print", pc=pc, pmult=2.0),
    }
    res = {}
    for name, opt in cases.items():
        for lab, N in (("C3a", 5), ("C3b", 15)):
            inc_from = "cache" if opt.get("cost", "model") == "model" else "same"
            r = c3.score(f"{lab}_{name}", N, inc_from=inc_from, **opt)
            res[r["name"]] = r
            print(gates.summary(r), flush=True)
    json.dump(res, open(os.path.join(RT, "c3_prints.json"), "w"), indent=1, default=float)
    dc = {f"{lab}_{k}": (N, v) for k, v in cases.items() for lab, N in (("C3a", 5), ("C3b", 15))}
    D = decomp(dc)
    D.to_csv(os.path.join(RT, "c3_decomp.csv"), index=False)
    print(D.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
