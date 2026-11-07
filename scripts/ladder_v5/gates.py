#!/usr/bin/env python3
"""Ladder v5: the shared test harness (reports/ladder_v5_prereg.md). Every candidate is scored here, the same way.

A candidate is a function book_fn(P, era, theta, C, today, cost_mult) -> daily returns on capital (the live bot's
1-second blend), built on the frozen simulators (fsim for fills and costs, hsim for the live cash rule). The incumbent
is hsim's "engine" policy with no other change.
Configurations (all at $250K unless stated; keys S_0.5, S_0.25, base_0.5, cap_1M):
  S*   today's volumes (per-coin factors <= 1), unverified costs doubled (half-spread 4 bp, impact y 1.4, and any
       unverified cost the candidate adds), fee tier from the book's own volume; theta 0.5 and theta 0.25
  base research volumes, 1x costs, theta 0.5
  cap  S* at $1M (capacity, reported)
Gates (all must hold to adopt):
  G1  pooled paired t >= 2 (Newey-West, 5 lags) of daily candidate - incumbent, S*, theta 0.5, all three eras' days;
  G2  mean difference > 0 in each era (sel, chk, early), S*, theta 0.5;
  G3  the same at theta 0.25: pooled t >= 2 and every era > 0;
  G4  base configuration: pooled mean difference > 0.
The Sharpe path: the same gates on the vol-matched difference (candidate scaled to the incumbent's pooled daily
volatility in that configuration), for changes that cut risk more than return. The candidate declares its path
before the run. Every call is logged to reports/ladder_v5/trials.csv (fcntl-locked).
"""
import fcntl
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402
import hsim  # noqa: E402

LEDGER = os.path.join(fsim.OUT, "trials.csv")
CACHE = os.path.join(fsim.OUT, "cache")
CONFIGS = {"S_0.5": dict(theta=0.5, C=250e3, today=True, cost_mult=2.0),
           "S_0.25": dict(theta=0.25, C=250e3, today=True, cost_mult=2.0),
           "base_0.5": dict(theta=0.5, C=250e3, today=False, cost_mult=1.0),
           "cap_1M": dict(theta=0.5, C=1e6, today=True, cost_mult=2.0)}
_PRE, _PAN, _ADV = {}, {}, {}


def data(tag):
    if tag not in _PRE:
        _PRE[tag] = fsim.load(tag)
        coins = sorted(_PRE[tag].coin.unique())
        idx, M, thr = hsim.panel(tag, coins)
        _PAN[tag] = (idx, M, thr, coins)
    return _PRE[tag], _PAN[tag]


def adv(tag, era):
    if (tag, era) not in _ADV:
        P, pan = data(tag)
        lo, hi = fsim.ERAS[era][1]
        _ADV[(tag, era)] = hsim.adv_table(tag, pan[3], lo, hi)
    return _ADV[(tag, era)]


def incumbent(P, era, theta, C, today, cost_mult, pan=None, adv_=None):
    d, _ = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_)
    return d


def incumbent_cached(era, cfg):
    os.makedirs(CACHE, exist_ok=True)
    key = f"inc_{era}_{cfg}.parquet"
    p = os.path.join(CACHE, key)
    if os.path.exists(p):
        return pd.read_parquet(p).iloc[:, 0]
    tag = fsim.ERAS[era][0]
    P, pan = data(tag)
    d = incumbent(P, era, pan=pan, adv_=adv(tag, era), **CONFIGS[cfg])
    d.rename("r").to_frame().to_parquet(p)
    return d


def run(name, book_fn, path="return", configs=("S_0.5", "S_0.25", "base_0.5", "cap_1M"), note="", log=True):
    """Scores book_fn against the incumbent. book_fn(P, era, pan=, adv_=, theta=, C=, today=, cost_mult=) -> daily."""
    out = {"name": name, "path": path, "configs": {}}
    t0 = time.time()
    for cfg in configs:
        kw = CONFIGS[cfg]
        per, diffs = {}, []
        for era in fsim.ERAS:
            tag = fsim.ERAS[era][0]
            P, pan = data(tag)
            inc = incumbent_cached(era, cfg)
            cand = book_fn(P, era, pan=pan, adv_=adv(tag, era), **kw)
            cand = cand.reindex(inc.index, fill_value=0.0)
            d = cand - inc
            si, sc = fsim.stats(inc, kw["C"], era), fsim.stats(cand, kw["C"], era)
            per[era] = dict(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"], cand_ret=sc["ret_yr"],
                            cand_sharpe=sc["sharpe"], d_ret=sc["ret_yr"] - si["ret_yr"],
                            d_sharpe=sc["sharpe"] - si["sharpe"], mean_diff=float(d.mean()), t=float(fsim.nw_t(d)))
            diffs.append((era, inc, cand))
        allinc = pd.concat([x[1] for x in diffs])
        allcand = pd.concat([x[2] for x in diffs])
        d = allcand - allinc
        vm = allcand * (allinc.std() / allcand.std()) - allinc if allcand.std() > 0 else d * np.nan
        out["configs"][cfg] = dict(eras=per, pooled_t=float(fsim.nw_t(d)), pooled_mean=float(d.mean()),
                                   pooled_t_volmatched=float(fsim.nw_t(vm)), pooled_mean_volmatched=float(vm.mean()),
                                   era_means_volmatched={e: float((c * (allinc.std() / allcand.std()) - i).mean())
                                                         for e, i, c in diffs} if allcand.std() > 0 else {})
    out["gates"] = gates(out, path)
    out["seconds"] = round(time.time() - t0)
    if log:
        log_trial(name, out, note)
    return out


def gates(out, path="return"):
    c = out["configs"]
    vm = path == "sharpe"

    def pooled(cfg):
        return c[cfg]["pooled_t_volmatched" if vm else "pooled_t"]

    def eras_pos(cfg):
        if vm:
            return all(v > 0 for v in c[cfg]["era_means_volmatched"].values())
        return all(e["mean_diff"] > 0 for e in c[cfg]["eras"].values())
    g = {}
    if "S_0.5" in c:
        g["G1"] = bool(pooled("S_0.5") >= 2.0)
        g["G2"] = bool(eras_pos("S_0.5"))
    if "S_0.25" in c:
        g["G3"] = bool(pooled("S_0.25") >= 2.0 and eras_pos("S_0.25"))
    if "base_0.5" in c:
        g["G4"] = bool((c["base_0.5"]["pooled_mean_volmatched"] if vm else c["base_0.5"]["pooled_mean"]) > 0)
    g["pass"] = bool(all(g.get(k, False) for k in ("G1", "G2", "G3", "G4")))
    return g


def log_trial(name, out, note=""):
    os.makedirs(fsim.OUT, exist_ok=True)
    row = {"time_utc": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "name": name, "path": out["path"],
           "note": note, "pass": out["gates"].get("pass")}
    for cfg, v in out["configs"].items():
        row[f"{cfg}_t"] = round(v["pooled_t"], 3)
        row[f"{cfg}_t_vm"] = round(v["pooled_t_volmatched"], 3)
        for era, e in v["eras"].items():
            row[f"{cfg}_{era}_dsharpe"] = round(e["d_sharpe"], 3)
            row[f"{cfg}_{era}_dret"] = round(e["d_ret"], 4)
    row.update({k: v for k, v in out["gates"].items()})
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        df = pd.DataFrame([row])
        if not new:
            cols = pd.read_csv(LEDGER, nrows=0).columns.tolist()
            df = df.reindex(columns=cols + [c for c in df.columns if c not in cols])
        df.to_csv(fh, header=new, index=False)
        fcntl.flock(fh, fcntl.LOCK_UN)
    js = os.path.join(fsim.OUT, "trials", f"{name}.json")
    os.makedirs(os.path.dirname(js), exist_ok=True)
    json.dump(out, open(js, "w"), indent=1, default=float)


def summary(out):
    lines = [f"{out['name']} (path {out['path']}): gates {out['gates']}"]
    for cfg, v in out["configs"].items():
        lines.append(f"  {cfg}: pooled t {v['pooled_t']:+.2f} (vol-matched {v['pooled_t_volmatched']:+.2f})")
        for era, e in v["eras"].items():
            lines.append(f"    {era:5s} inc {e['inc_ret']:6.1%} / {e['inc_sharpe']:5.2f}  cand {e['cand_ret']:6.1%} / "
                         f"{e['cand_sharpe']:5.2f}  t {e['t']:+.2f}")
    return "\n".join(lines)
