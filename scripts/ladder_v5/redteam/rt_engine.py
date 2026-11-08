#!/usr/bin/env python3
"""Red team: my replay against the bot's own engine on a cascade window.

Engine side (reused pattern of scripts/ladder_v5/hsim_check.py, engine side only): bot/spot/engine.py, paper broker
(capture 0.5 = theta 0.5), once-a-minute steps over stored candles, its AI replaced by the walk-forward panel
prediction and quarterly threshold. Replay side: my rt_live replay (minute bound: the paper engine has no 1-second
poll) restricted to the same window (bids and parents only inside it, empty book at its start).
Compared: research parents funded (engine fill at that coin and minute vs replay funded), deeper rungs filled per
parent, engine-only parents, and the engine's 4-sigma allocation against mine in the minutes before the first fill.

usage: python scripts/ladder_v5/redteam/rt_engine.py 2025-10-10T18:00 2025-10-11T06:00 [capital]
"""
import json
import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import rt_live as RL  # noqa: E402
import fsim  # noqa: E402
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bot", "spot"))
from bot.spot import engine as E  # noqa: E402
import replay_test as RT  # noqa: E402


class PanelEngine(E.Engine):
    """The engine with the AI's prediction and threshold taken from the walk-forward panel (E.Engine._allocate with
    the panel's numbers; everything else is the engine's own code)."""
    pan = None
    alloc_log = None

    def _allocate(self, pn, t):
        idx, M, thr, coins = self.pan
        i = int(idx.searchsorted(t))
        cj = {c: j for j, c in enumerate(coins)}
        busy, armed = set(), {}
        for lad in self.ladders():
            if lad["status"] == "armed":
                armed[lad["coin"]] = lad
            elif "4" in lad["tranches"] or "e4" in lad["orders"]:
                busy.add(lad["coin"])
        halted = self._halted(t)
        prev = t - pd.Timedelta(minutes=1)
        cands, rows = [], {}
        if not halted and self.fresh("BTC", t) and i < len(idx) and idx[i] == t:
            for c in self.tradable:
                if c in busy or not self.fresh(c, t) or c not in cj:
                    continue
                row = pn[c].iloc[-1]
                if not all(np.isfinite(row[f]) for f in ("level", "sig", "z_res60", "bid_depth_bp")):
                    continue
                pred = float(M[i, cj[c]])
                if pred > float(thr[i]):
                    cands.append((pred, c))
                    rows[c] = row
        cands.sort(reverse=True)
        free0 = self.free_cash() + sum(self.hold_usd(l["orders"]["e4"]) for l in armed.values() if "e4" in l["orders"])
        free = free0
        alloc = {}
        for pred, c in cands:
            want = self.signal_usd(c) * self.rung_w["4"]
            need = want * (1 + self.fee_m())
            if need <= free:
                alloc[c], free = want, free - need
            elif free >= 0.5 * need:
                alloc[c], free = 0.999 * free / (1 + self.fee_m()), 0.0
            else:
                self.count("cash_short")
                self.log("cash_short", t=t, coin=c, pred=round(pred, 1), want=round(want), free=round(max(free, 0)))
        self.alloc_log.append(dict(t=t, free0=free0, committed=self.committed(), alloc=dict(alloc),
                                   busy=sorted(busy), cands=[c for _, c in cands]))
        for c, lad in armed.items():
            if c not in alloc:
                if self._cancel(lad, "e4", t, minute=prev) and lad["status"] == "armed":
                    self.state["ladders"].pop(lad["id"], None)
                    self.count("disarm")
        plans = [p for p in (self._arm_plan(c, pred, rows[c], alloc[c], t, armed.get(c)) for pred, c in cands
                             if c in alloc) if p]
        for p in plans:
            self._arm(*p)


def run_engine(start, end, C, pan):
    mkt = RT.ReplayMarket(start, end)
    cfg = json.load(open(os.path.join(ROOT, "bot", "spot", "config.json")))
    cfg.update(capital=C)
    clock = {"t": start}
    sd = tempfile.mkdtemp(prefix="rt_engine_")
    PanelEngine.pan = pan
    PanelEngine.alloc_log = []
    eng = PanelEngine(mode="paper", cfg=cfg, state_dir=sd, market=mkt, broker=E.PaperBroker(0.5),
                      clock=lambda: clock["t"] + pd.Timedelta(seconds=6), echo=False)
    eng.start()
    steps = pd.date_range(start, end + pd.Timedelta(minutes=125), freq="min", inclusive="left")
    t0 = time.time()
    for n, t in enumerate(steps):
        if t == end:
            eng.tradable = []
        clock["t"] = t
        eng.step(t)
        if n % 120 == 0:
            print(f"  engine {t} ({time.time() - t0:.0f}s)", flush=True)
    ev = pd.read_json(os.path.join(sd, "events.jsonl"), lines=True)
    ev["ts"] = pd.to_datetime(ev.ts)
    keep = ev[ev.kind.isin(["arm", "fill_entry", "fill_exit", "rung", "cash_short", "ladder_close"])]
    keep.astype(str).to_csv(os.path.join(RL.OUT, f"engine_events_{start:%Y%m%d}.csv.gz"), index=False)
    return ev, PanelEngine.alloc_log, eng


def main(start, end, C=250e3):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    tag = "main"
    era = [e for e, (tg, (lo, hi)) in fsim.ERAS.items() if tg == tag and pd.Timestamp(lo) <= start <= pd.Timestamp(hi)][0]
    I = RL.inputs(tag)
    coins = I["coins"]
    pan = (I["pidx"], I["M"], I["thr"].astype(np.float32), coins)
    ev, alog, eng = run_engine(start, end, C, pan)
    fe = ev[ev.kind == "fill_entry"]
    lad_first = fe.groupby(["ladder", "rung"]).agg(coin=("coin", "first"), minute=("ts", "min"), usd=("usd", "sum"))
    lad_first = lad_first.reset_index()
    par_e = lad_first[lad_first.rung == 4].rename(columns={"minute": "ts"})
    deep_e = lad_first[lad_first.rung > 4].groupby("ladder").agg(eng_deep=("rung", "size"), eng_deep_usd=("usd", "sum"))
    par_e = par_e.merge(deep_e, on="ladder", how="left").fillna({"eng_deep": 0, "eng_deep_usd": 0.0})
    # replay on the same window (minute bound and the blend's instant bound for reference)
    A = RL.era_arrays(tag, era, 0.5, C, False, win=(start, end))
    Ap = RL.era_arrays(tag, era, 0.5, C, False, win=(start, end), phantom=True)
    out = {}
    for bound in ("minute", "instant"):
        R = RL.replay(A, theta=0.5, C=C, bound=bound, policy="engine")
        out[bound] = R
    variants = {"fill_order": (A, dict(prio_mode=1)),
                "hsim_like": (Ap, dict(rem_hold=False, rel_shift=1, busy_mode=1, mkt_check=False,
                                       inst_retry_old=False, interleave=False, prio_mode=1)),
                "nocash": (A, dict(policy="nocash"))}
    vres = {}
    for name, (AA, kw) in variants.items():
        kw = dict(kw)
        pol = kw.pop("policy", "engine")
        vres[name] = RL.replay(AA, theta=0.5, C=C, bound="minute", policy=pol, **kw)
    par = A["par"].reset_index()
    R = out["minute"]
    rp = pd.DataFrame(dict(ts=par.ts, coin=par.coin, rep_usd4=R["a4"], rep_why=R["why4"],
                           rep_deep=(R["r_state"] == 2).sum(axis=1),
                           rep_deep_inst=(out["instant"]["r_state"] == 2).sum(axis=1),
                           res_deep=(A["dp_len"] > 0).sum(axis=1),
                           res_deep_after0=[sum(1 for k in range(2) if A["dp_len"][q, k] > 0 and
                                                A["dp"]["off"][A["dp_start"][q, k]] > 0) for q in range(A["NP"])]))
    for name, RR in vres.items():
        rp[f"{name}_usd4"] = RR["a4"]
        rp[f"{name}_deep"] = (RR["r_state"] == 2).sum(axis=1)
    # deeper placement minute (engine "rung" events) per parent and rung
    t0i = A["idx"][0]
    for name, RR in [("rep", R)] + list(vres.items()):
        for kk, k in enumerate((6, 8)):
            pl = RR["r_place"][:, kk]
            rp[f"{name}_place{k}"] = [t0i + pd.Timedelta(minutes=int(x)) if x >= 0 else pd.NaT for x in pl]
    rg = ev[ev.kind == "rung"]
    if len(rg):
        rg = rg.assign(rung=rg.rung.astype(int)).groupby(["ladder", "rung"]).ts.min().unstack()
        for k in (6, 8):
            par_e[f"eng_place{k}"] = par_e.ladder.map(rg[k]) if k in rg.columns else pd.NaT
    else:
        for k in (6, 8):
            par_e[f"eng_place{k}"] = pd.NaT
    cmp_ = rp.merge(par_e[["ts", "coin", "ladder", "usd", "eng_deep", "eng_deep_usd", "eng_place6", "eng_place8"]],
                    on=["ts", "coin"], how="outer", indicator=True)
    both = cmp_[cmp_._merge == "both"]
    agree = {}
    for name, col_u, col_d in [("replay", "rep_usd4", "rep_deep")] + [(n, f"{n}_usd4", f"{n}_deep") for n in vres]:
        fund_e = cmp_.usd.notna()
        fund_r = cmp_[col_u].fillna(0) > 0
        inres = cmp_._merge != "right_only"
        pa = 0
        pn_ = 0
        pref = "rep" if name == "replay" else name
        for k in (6, 8):
            e_ = pd.to_datetime(both[f"eng_place{k}"])
            r_ = pd.to_datetime(both[f"{pref}_place{k}"])
            pa += int(((e_ == r_) | (e_.isna() & r_.isna())).sum())
            pn_ += len(both)
        agree[name] = dict(placement_minute_agree=pa, placement_compared=pn_,
                           parents_funded=int(fund_r[inres].sum()),
                           parent_status_agree=int((fund_e[inres] == fund_r[inres]).sum()),
                           deeper_fills=int(cmp_.loc[inres, col_d].fillna(0).sum()),
                           deeper_count_agree_on_common=int((both[col_d].fillna(0) == both.eng_deep).sum()),
                           abs_deeper_diff_on_common=int((both[col_d].fillna(0) - both.eng_deep).abs().sum()))
    os.makedirs(RL.OUT, exist_ok=True)
    cmp_.to_csv(os.path.join(RL.OUT, f"engine_check_{start:%Y%m%d}.csv"), index=False)
    # allocation agreement before the first fill (both books empty)
    first_fill = fe.ts.min() if len(fe) else end
    ag = dis = 0
    pidx = A["idx"]
    for rec in alog:
        t = pd.Timestamp(rec["t"])
        if t >= first_fill or t >= end:
            break
        i = pidx.get_indexer([t])[0]
        mine = {}
        free = C
        for j in range(A["ncand"][i]):
            c = A["order"][i, j]
            want = A["want4"][i, c]
            need = want * (1 + RL.FEE_M)
            if need <= free:
                mine[coins[c]] = want
                free -= need
            elif free >= 0.5 * need:
                mine[coins[c]] = 0.999 * free / (1 + RL.FEE_M)
                free = 0.0
        e = {k: v for k, v in rec["alloc"].items()}
        same = set(e) == set(mine) and all(abs(e[k] - mine[k]) < 1e-6 * max(1.0, e[k]) for k in e)
        ag += same
        dis += (not same)
    cnt = {}
    for c_ in ev[ev.kind == "heartbeat"].get("counts", []):
        for k, v in (c_ or {}).items():
            cnt[k] = cnt.get(k, 0) + v
    res = dict(window=f"{start} .. {end}", capital=C,
               research_parents=int(len(par)),
               engine_parents=int(len(par_e)),
               engine_parents_in_research=int((cmp_._merge == "both").sum()),
               engine_only_parents=int((cmp_._merge == "right_only").sum()),
               replay_parents_funded=int((R["a4"] > 0).sum()),
               both_funded=int(((cmp_._merge == "both") & (cmp_.rep_usd4 > 0)).sum()),
               replay_funded_engine_not=int(((cmp_._merge == "left_only") & (cmp_.rep_usd4 > 0)).sum()),
               engine_funded_replay_not=int(((cmp_._merge == "both") & (cmp_.rep_usd4 <= 0)).sum()),
               engine_deeper_fills=int(par_e.eng_deep.sum()),
               engine_deeper_fills_on_research_parents=int(cmp_.loc[cmp_._merge == "both", "eng_deep"].sum()),
               replay_deeper_fills_minute=int(rp.rep_deep.sum()),
               replay_deeper_fills_instant=int(rp.rep_deep_inst.sum()),
               research_deeper_fills=int(rp.res_deep.sum()), research_deeper_after_minute0=int(rp.res_deep_after0.sum()),
               engine_cash_short_events=int((ev.kind == "cash_short").sum()), engine_counts=cnt,
               replay_cash_short=int(R["cash_short"]), alloc_minutes_compared=ag + dis, alloc_minutes_identical=ag,
               common_parents=int(len(both)), agreement=agree)
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(os.path.join(RL.OUT, f"engine_check_{start:%Y%m%d}.json"), "w"), indent=1, default=str)
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 250e3)
