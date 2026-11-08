#!/usr/bin/env python3
"""Replay test for the spot bot (bot/spot/engine.py), on local data with no network.

1. Parity: run the engine minute by minute over a historical window with unlimited fill capacity and unlimited cash,
   and compare every rung it trades (entry minute and price, exit minute, type and price) with an independent loop
   implementation of the same rules (reference() below). Any difference is a bug in one of the two.
2. Descriptive: rerun with the default paper settings ($250K, capture 0.5, 20 bp ADV cap, VIP-1 fees), and count the
   deeper fills the research simulation would also have taken inside the parent's own minute (which the bot misses).

3. Options (ladder v5): --passive=N adds a parity pass with passive_exit_min = N (both implementations re-peg a
   post-only sell at the last close + 1 tick for N minutes after the 60-minute mark); --margin adds a parity pass with
   size_by_margin from config.v5.json, checking every parent's size multiplier against the reference's prediction.

Usage: python bot/spot/replay_test.py 2025-10-10 2025-10-12 [--skip-descriptive] [--passive=15] [--margin]
"""
import json
import math
import os
import sys
import tempfile
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import engine as E  # noqa: E402
from edge import wick  # noqa: E402

META = json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))
COINS = META["coins"]
K, THETA, H = float(META["K"]), float(META["THETA"]), int(META["H"])
LB, WB, THR = int(META["L"]), int(META["wbeta"]), float(META["threshold"])
CODES = {c: i for i, c in enumerate(sorted(COINS))}


class ReplayMarket:
    """Historical 1-minute Coinbase spot candles (data/minute) and perp candles (data/cfm, for the volume cap)."""

    def __init__(self, start, end):
        lo, hi = pd.Timestamp(start) - pd.Timedelta(days=50), pd.Timestamp(end) + pd.Timedelta(hours=4)
        self.D, self.P = {}, {}
        for c in ["BTC"] + COINS:
            d = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet"))
            d = d[(d.ts >= lo) & (d.ts < hi)].drop_duplicates("ts").set_index("ts").sort_index()
            self.D[c] = d[["open", "high", "low", "close", "volume"]].astype(float)
        p = pd.read_csv(os.path.join(ROOT, "reports", "cfm_products.csv"))
        cs = p[p.expiry_type == "PERPETUAL"].set_index("contract_root_unit").contract_size.to_dict()
        for c in COINS:
            f = os.path.join(ROOT, "data", "cfm", f"{c}.parquet")
            if os.path.exists(f) and c in cs:
                d = pd.read_parquet(f, columns=["ts", "close", "volume"])
                d = d[(d.ts >= lo) & (d.ts < hi)].drop_duplicates("ts").set_index("ts").sort_index()
                self.P[c] = (d.close * d.volume * cs[c]).resample("D").sum()
        self.ticks = E.fallback_ticks()

    def spot_candles(self, coin, start, end):
        d = self.D[coin]
        i0, i1 = d.index.searchsorted([pd.Timestamp(start), pd.Timestamp(end)])
        return d.iloc[i0:i1]

    def spec(self, coin):
        return E.Spec(f"{coin}-USD", self.ticks[coin], 1e-8, 1.0)

    def daily_usd(self, coin, end):
        d = self.D[coin][self.D[coin].index < end]
        usd = (d.close * d.volume).resample("D").sum()
        if coin in self.P:
            usd = usd.add(self.P[coin][self.P[coin].index < end], fill_value=0.0)
        return pd.DataFrame({"close": d.close.resample("D").last(), "usd": usd}).dropna(subset=["close"])

    def best_bid(self, product):
        return np.nan


def run_engine(mkt, start, end, cfg, capture, tag):
    clock = {"t": pd.Timestamp(start)}
    sd = tempfile.mkdtemp(prefix=f"spot_{tag}_")
    eng = E.Engine(mode="paper", cfg=cfg, state_dir=sd, market=mkt, broker=E.PaperBroker(capture),
                   clock=lambda: clock["t"] + pd.Timedelta(seconds=6), echo=False)
    t0 = time.time()
    eng.start()
    steps = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta(minutes=2 * H + 5), freq="min", inclusive="left")
    for i, t in enumerate(steps):
        if t == pd.Timestamp(end):
            eng.tradable = []                        # no new parents after the window; open rungs run to their exits
        clock["t"] = t
        eng.step(t)
        if i and i % 500 == 0:
            print(f"  [{tag}] {t} ({time.time() - t0:.0f}s)", flush=True)
    ev = pd.read_json(os.path.join(sd, "events.jsonl"), lines=True)
    ev["ts"] = pd.to_datetime(ev.ts)
    print(f"  [{tag}] {len(steps)} minutes in {time.time() - t0:.0f}s; events in {sd}", flush=True)
    return ev, eng


def engine_rungs(ev):
    ev = ev.reindex(columns=sorted(set(ev.columns) | {"coin", "ladder", "rung", "px", "exit", "ref_px"}))
    ent = ev[ev.kind == "fill_entry"][["ts", "coin", "ladder", "rung", "px"]].rename(columns={"ts": "entry", "px": "entry_px"})
    ent = ent.groupby(["ladder", "rung"], as_index=False).agg(coin=("coin", "first"), entry=("entry", "min"),
                                                              entry_px=("entry_px", "first"))
    ext = ev[ev.kind == "fill_exit"].copy()
    ext["px"] = np.where(ext.exit == "time", ext.get("ref_px", ext.px), ext.px)
    ext["exit_min"] = np.where(ext.exit == "time", ext.ts - pd.Timedelta(minutes=1), ext.ts)   # the close used
    ext = ext.groupby(["ladder", "rung"], as_index=False).agg(exit_min=("exit_min", "max"), exit=("exit", "last"),
                                                              exit_px=("px", "last"))
    return ent.merge(ext, on=["ladder", "rung"], how="left")


def reference(mkt, start, end, tradable, passive=0):
    """The engine's rules, written independently as one loop per coin (capacity and cash unlimited). passive = N:
    from the 60-minute mark a post-only sell at the last close + 1 tick, re-pegged each minute, for N minutes."""
    w0, w1 = pd.Timestamp(start) - pd.Timedelta(minutes=E.WINDOW_MIN), pd.Timestamp(end) + pd.Timedelta(minutes=2 * H + 5)
    idx = pd.date_range(w0, w1, freq="min", inclusive="left")
    A = {}
    for c in ["BTC"] + COINS:
        d = mkt.D[c]
        d = d[d.volume > 0].reindex(idx)
        A[c] = dict(o=d.open.to_numpy(), h=d.high.to_numpy(), l=d.low.to_numpy(), v=d.volume.fillna(0).to_numpy(),
                    cf=d.close.ffill(limit=30).to_numpy(), traded=d.close.notna().to_numpy())
    pn = wick.panel({c: A[c]["cf"] for c in A}, {c: A[c]["v"] for c in A}, COINS, idx, k=K, lookback=LB,
                    coin_codes=CODES, wbeta=WB)
    models = [lgb.Booster(model_file=os.path.join(ROOT, "bot", "v2", f)) for f in META["models"]]
    i0, i1 = idx.get_indexer([pd.Timestamp(start), pd.Timestamp(end)])
    n = len(idx)

    def last_trade_index(traded):
        out = np.full(len(traded), -10 ** 9)
        last = -10 ** 9
        for i, tr in enumerate(traded):
            out[i] = last                            # last traded minute strictly before i
            if tr:
                last = i
        return out

    btc_last = last_trade_index(A["BTC"]["traded"])
    rows = []
    for c in tradable:
        tick = mkt.ticks[c]
        a, f = A[c], pn[c]
        lv = np.floor(f.level.to_numpy() / tick + 1e-9) * tick
        sg = f.sig.to_numpy()
        ok = np.isfinite(f[["level", "sig", "z_res60", "bid_depth_bp"]].to_numpy()).all(axis=1)
        pred = np.full(n, -np.inf)
        rng = np.arange(i0, i1)
        pred[rng] = np.mean([m.predict(f.iloc[rng][wick.FEATS].to_numpy(np.float64)) for m in models], axis=0)
        last_tr = last_trade_index(a["traded"])
        fresh = (np.arange(n) - last_tr <= 10) & (np.arange(n) - btc_last <= 10)
        o, h, lo, cf = a["o"], a["h"], a["l"], a["cf"]
        cl = np.where(a["traded"], cf, np.nan)

        def last_close(s):                           # engine: last traded close before step s, within 30 minutes
            j = last_tr[s]
            return cl[j] if s - j <= 30 else np.nan

        def rung_exit(m, entry_px, kk, sig):
            tp = math.floor(entry_px * math.exp(THETA * kk * sig) / tick + 1e-9) * tick
            for u in range(m + 1, min(m + H, n - 1) + 1):
                if np.isfinite(h[u]) and h[u] >= tp + tick * (1 - 1e-9):
                    return u, "tp", tp
            peg = None
            for j in range(1, passive + 1):          # minute m+H+j: the sell placed at that step rests through it
                s_ = m + H + j
                if s_ >= n:
                    break
                lc = last_close(s_)
                if np.isfinite(lc):
                    peg = math.floor(lc / tick + 1e-9) * tick + tick
                if peg is not None and np.isfinite(h[s_]) and h[s_] >= peg + tick * (1 - 1e-9):
                    return s_, "passive", peg
            return m + H + passive, "time", last_close(m + H + passive + 1)

        t = i0
        while t < i1:
            b = lv[t]
            if not (ok[t] and pred[t] > THR and fresh[t] and np.isfinite(o[t]) and o[t] > b
                    and lo[t] <= b - tick * (1 - 1e-9)):
                t += 1
                continue
            sig = sg[t]
            fair = math.log(b) + K * sig
            u, ty, px = rung_exit(t, b, K, sig)
            rows.append(dict(coin=c, rung=4, entry=idx[t], entry_px=b, exit_min=idx[u], exit=ty, exit_px=px, pred=pred[t]))
            close_par = u if ty == "tp" else t + H
            for kk in (6.0, 8.0):
                lk = math.floor(math.exp(fair - kk * sig) / tick + 1e-9) * tick
                s = next((s for s in range(t + 1, close_par + 1)
                          if (s <= u if ty == "tp" else s < t + H) and last_close(s) > lk), None)
                if s is None:
                    continue
                last_m = u - 1 if ty == "tp" else t + H - 1
                m = next((m for m in range(s, last_m + 1) if np.isfinite(lo[m]) and lo[m] <= lk - tick * (1 - 1e-9)), None)
                if m is None:
                    continue
                u2, ty2, px2 = rung_exit(m, lk, kk, sig)
                rows.append(dict(coin=c, rung=int(kk), entry=idx[m], entry_px=lk, exit_min=idx[u2], exit=ty2, exit_px=px2))
            t = (u + 1) if ty == "tp" else (t + H + 1)
    return pd.DataFrame(rows), pn, idx, A


def research_same_minute(R, pn, idx, A, mkt):
    """Deeper rungs the research simulation fills in the parent's own minute (missed by the bot by design)."""
    n = 0
    for r in R[R.rung == 4].itertuples():
        i = idx.get_loc(r.entry)
        sig = float(pn[r.coin].sig.iloc[i])
        fair = math.log(r.entry_px) + K * sig
        tick = mkt.ticks[r.coin]
        for kk in (6.0, 8.0):
            lk = math.exp(fair - kk * sig)
            n += int(A[r.coin]["l"][i] <= lk * (1 - tick / lk))
    return n


def parity(mkt, start, end, passive=0, margin=None):
    cfg = dict(capital=1e9, notional_frac=0.25, adv_frac=None, cash_cap=1e6, daily_loss_limit=1.0, max_drawdown=1.0,
               fee_bp_maker=6.0, fee_bp_taker=12.5, half_spread_bp=0.0, impact_y=0.0, passive_exit_min=passive,
               size_by_margin=margin)
    tag = "parity" + (f"_passive{passive}" if passive else "") + ("_margin" if margin else "")
    ev, eng = run_engine(mkt, start, end, cfg, None, tag)
    G = engine_rungs(ev)
    R, pn, idx, A = reference(mkt, start, end, COINS, passive=passive)
    print(f"[{tag}] engine: {len(G)} rungs ({(G.rung == 4).sum()} parents); reference: {len(R)} rungs "
          f"({(R.rung == 4).sum()} parents); exits by type (engine): {G.exit.value_counts().to_dict()}")
    key = ["coin", "rung", "entry"]
    M = R.merge(G, on=key, how="outer", suffixes=("_ref", "_eng"), indicator=True)
    print(M._merge.value_counts().to_string())
    both = M[M._merge == "both"]
    bad = both[(np.abs(both.entry_px_ref / both.entry_px_eng - 1) > 1e-9) | (both.exit_min_ref != both.exit_min_eng)
               | (both.exit_ref != both.exit_eng) | (np.abs(both.exit_px_ref / both.exit_px_eng - 1) > 1e-9)]
    mism = M[M._merge != "both"]
    ok = not (len(mism) or len(bad))
    if not ok:
        pd.set_option("display.width", 250)
        print("MISMATCHES:")
        print(pd.concat([mism, bad]).head(30).to_string())
    else:
        print(f"[{tag}] PARITY OK: every rung identical (entry minute and price, exit minute, type and price)")
    if margin:
        ok = check_margin(ev, G, R, margin) and ok
    return ok, R, pn, idx, A


def check_margin(ev, G, R, margin):
    """Every parent's 4-sigma fill / (25% x equity / 3) must equal the multiplier of the reference's own prediction at
    its entry minute (unlimited capacity: the whole bid fills; equity moves by well under 1% in a replay)."""
    lo, hi, mult = float(margin["lower"]), float(margin["upper"]), [float(x) for x in margin["mult"]]
    usd = ev[(ev.kind == "fill_entry") & (ev.rung == 4)].groupby("ladder").usd.sum()
    par = G[G.rung == 4].merge(R[R.rung == 4][["coin", "entry", "pred"]], on=["coin", "entry"], how="left")
    unit = 1e9 * 0.25 / 3
    bad, seen = 0, {x: 0 for x in mult}
    for r in par.itertuples():
        m = mult[0] if r.pred - THR < lo else mult[2] if r.pred - THR >= hi else mult[1]
        got = usd.get(r.ladder, np.nan) / unit
        seen[m] += 1
        if not abs(got / m - 1) < 0.01:
            bad += 1
            print(f"  size mismatch {r.ladder}: x{got:.3f} vs x{m} (reference margin {r.pred - THR:.2f})")
    print(f"[margin] {len(par)} parents, size multipliers {'OK' if not bad else f'{bad} WRONG'}; "
          + ", ".join(f"x{k}: {v}" for k, v in seen.items()))
    return bad == 0


def main(start, end, skip_descriptive=False, passive=0, margin=False):
    mkt = ReplayMarket(start, end)
    print(f"window {start} .. {end}: {len(COINS)} coins")
    ok, R, pn, idx, A = parity(mkt, start, end)
    if passive:
        ok = parity(mkt, start, end, passive=passive)[0] and ok
    if margin:
        v5 = json.load(open(os.path.join(HERE, "config.v5.json")))
        ok = parity(mkt, start, end, margin=v5["size_by_margin"])[0] and ok
    print("ALL PARITY CHECKS OK" if ok else "PARITY FAILED")
    same = research_same_minute(R, pn, idx, A, mkt)
    print(f"deeper rungs the research would also fill inside the parent's minute (the bot misses these): {same}")
    if skip_descriptive:
        return
    cfg2 = json.load(open(os.path.join(HERE, "config.json")))
    ev2, eng2 = run_engine(mkt, start, end, cfg2, cfg2["paper_capture"], "paper250k")
    ent, ext = ev2[ev2.kind == "fill_entry"], ev2[ev2.kind == "fill_exit"]
    notional = (ext.entry_px * ext["size"]).sum()
    print(f"\npaper settings, $250K: {ent.ladder.nunique()} ladders, {len(ent)} entry fills (${ent.usd.sum():,.0f}), "
          f"{len(ext)} exits; P&L ${ext.pnl.sum():,.0f}; net {1e4 * ext.pnl.sum() / max(notional, 1):.1f} bp per USD")
    print(ext.groupby(["rung", "exit"]).agg(n=("pnl", "size"), pnl=("pnl", "sum"), net_bp=("net_bp", "mean")).round(1).to_string())
    cnt = {}
    for c in ev2[ev2.kind == "heartbeat"].counts.dropna():
        for k_, v in c.items():
            cnt[k_] = cnt.get(k_, 0) + v
    print("counts:", cnt)
    hb = ev2[ev2.kind == "heartbeat"]
    print(f"committed (positions + resting bids) at heartbeats: median ${hb.committed.median():,.0f}, "
          f"max ${hb.committed.max():,.0f}; cash_short events {int((ev2.kind == 'cash_short').sum())}")


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    pas = next((int(x.split("=")[1]) for x in sys.argv if x.startswith("--passive=")), 0)
    main(args[0], args[1], skip_descriptive="--skip-descriptive" in sys.argv, passive=pas, margin="--margin" in sys.argv)
