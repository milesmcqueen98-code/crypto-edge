#!/usr/bin/env python3
"""Ladder v5: check the hold-aware simulator (hsim) against the bot's own engine on a cascade window.

The engine (bot/spot/engine.py, paper broker, once-a-minute steps) runs over stored candles with its AI replaced by
the walk-forward panel predictions and quarterly thresholds (so both sides arm the same coins). Compared, per window:
parent fills, deeper fills, and how often cash stopped a bid. The engine's paper fills use its own per-minute
capacity rule, so fill sizes differ in detail; the question is whether the cash rule binds the same way.

usage: python scripts/ladder_v5/hsim_check.py 2025-10-10T18:00 2025-10-11T06:00 [capital]
"""
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "bot", "spot"))
from bot.spot import engine as E  # noqa: E402
import replay_test as RT  # noqa: E402
import fsim  # noqa: E402
import hsim  # noqa: E402


class PanelEngine(E.Engine):
    """The engine with the AI's prediction and threshold taken from the walk-forward panel."""
    pan = None

    def _allocate(self, pn, t):
        idx, M, thr, coins = self.pan
        i = int(idx.searchsorted(t))
        cj = {c: j for j, c in enumerate(coins)}
        orig = self.models

        class Fake:
            def __init__(s, c):
                s.c = c

        # replicate E.Engine._allocate with the panel's numbers
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
        free = self.free_cash() + sum(self.hold_usd(l["orders"]["e4"]) for l in armed.values() if "e4" in l["orders"])
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
        for c, lad in armed.items():
            if c not in alloc:
                if self._cancel(lad, "e4", t, minute=prev) and lad["status"] == "armed":
                    self.state["ladders"].pop(lad["id"], None)
                    self.count("disarm")
        plans = [p for p in (self._arm_plan(c, pred, rows[c], alloc[c], t, armed.get(c)) for pred, c in cands
                             if c in alloc) if p]
        for p in plans:
            self._arm(*p)
        self.models = orig


def main(start, end, C=250e3):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    tag = "main" if start.year >= 2024 else "early"
    era = [e for e, (tg, (lo, hi)) in fsim.ERAS.items() if tg == tag and pd.Timestamp(lo) <= start <= pd.Timestamp(hi)][0]
    P = fsim.load(tag)
    coins = sorted(P.coin.unique())
    idx, M, thr = hsim.panel(tag, coins)
    pan = (idx, M, thr, coins)
    # engine
    mkt = RT.ReplayMarket(start, end)
    cfg = json.load(open(os.path.join(ROOT, "bot", "spot", "config.json")))
    cfg.update(capital=C)
    clock = {"t": start}
    sd = tempfile.mkdtemp(prefix="hsimchk_")
    PanelEngine.pan = pan
    eng = PanelEngine(mode="paper", cfg=cfg, state_dir=sd, market=mkt, broker=E.PaperBroker(0.5),
                      clock=lambda: clock["t"] + pd.Timedelta(seconds=6), echo=False)
    eng.start()
    counts = {}
    steps = pd.date_range(start, end + pd.Timedelta(minutes=125), freq="min", inclusive="left")
    for t in steps:
        if t == end:
            eng.tradable = []
        clock["t"] = t
        eng.step(t)
    ev = pd.read_json(os.path.join(sd, "events.jsonl"), lines=True)
    hb = ev[ev.kind == "heartbeat"]
    for cts in hb.get("counts", []):
        for k, v in (cts or {}).items():
            counts[k] = counts.get(k, 0) + v
    fe = ev[ev.kind == "fill_entry"]
    eng_par = fe[fe.rung == 4].groupby("ladder").size().shape[0]
    eng_deep = fe[fe.rung > 4].groupby(["ladder", "rung"]).size().shape[0]
    eng_cash = int((ev.kind == "cash_short").sum())
    # hsim on the same window (minute bound, as the paper engine)
    W = P[(P.ts >= start) & (P.ts < end)]
    adv = hsim.adv_table(tag, coins, start.floor("D"), end.floor("D"))
    o, st, foff = hsim.run(W, era, C=C, pan=pan, adv=adv, drop_same_minute=True)
    res_par = int((W[(W.k == 4) & W.filled]).shape[0])
    res_deep = int(W[(W.k > 4) & W.filled & (W.f_off > 0)].shape[0])
    h_par = int((o[W[(W.k == 4) & W.filled].index] > 0).sum())
    h_deep = int(len(foff))                                # deeper rungs the live book fills (any minute)
    # per-ladder comparison: engine entries by coin and parent minute vs hsim orders
    ent = fe.assign(minute=pd.to_datetime(fe.ts)).groupby(["ladder", "rung"]).agg(coin=("coin", "first"),
                                                                                    first=("minute", "min"),
                                                                                    usd=("usd", "sum")).reset_index()
    lad = ent[ent.rung == 4][["ladder", "coin", "first", "usd"]].rename(columns={"first": "ts", "usd": "eng_usd4"})
    deep_e = ent[ent.rung > 4].groupby("ladder").agg(eng_deep_n=("rung", "size"), eng_deep_usd=("usd", "sum"))
    lad = lad.merge(deep_e, on="ladder", how="left").fillna({"eng_deep_n": 0, "eng_deep_usd": 0.0})
    Wp = W[(W.k == 4) & W.filled][["ts", "coin"]].copy()
    Wp["h_usd4"] = o[Wp.index].to_numpy()
    dd = W[(W.k > 4)].assign(h=[1 if i in foff else 0 for i in W[(W.k > 4)].index], r=W[(W.k > 4)].filled.astype(int))
    Wp = Wp.merge(dd.groupby(["ts", "coin"]).agg(res_deep_n=("r", "sum"), h_deep_n=("h", "sum")).reset_index(),
                  on=["ts", "coin"], how="left").fillna({"res_deep_n": 0, "h_deep_n": 0})
    cmp_ = Wp.merge(lad, on=["ts", "coin"], how="outer", indicator=True)
    cmp_.to_csv(os.path.join(fsim.OUT, f"hsim_check_{start:%Y%m%d}.csv"), index=False)
    print(cmp_._merge.value_counts().to_string())
    print("deeper rungs: research", int(Wp.res_deep_n.sum()), "hsim filled", int(Wp.h_deep_n.sum()),
          "engine filled", int(lad.eng_deep_n.sum()))
    out = dict(window=f"{start} .. {end}", capital=C, research_parents=res_par, research_deeper_after_minute0=res_deep,
               hsim_parents_funded=h_par, hsim_deeper_filled=h_deep, hsim_stats=st,
               engine_parent_fills=int(eng_par), engine_deeper_fills=int(eng_deep), engine_cash_short_events=eng_cash,
               engine_counts=counts)
    print(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 250e3)
