#!/usr/bin/env python3
"""Parity test: run the live engine (bot/engine.py) minute by minute over a historical window, with the
network replaced by local data, and compare its trades with the vectorised research simulation of the
same rule and the same model. Any difference is a bug in one of the two.

Usage: python bot/replay_test.py 2026-01-12 2026-01-26 [model_dir]
"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from bot import engine, market  # noqa: E402
from edge import wick  # noqa: E402
import wick_sim as ws  # noqa: E402

CLOCK = {"t": None}
SPOT, FUT = {}, {}


def fake_now():
    return CLOCK["t"] + pd.Timedelta(seconds=6)


def fake_spot(coin, start, end):
    df = SPOT[coin]
    return df[(df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end).floor("min"))]


def fake_fut(product, start, end):
    df = FUT[product]
    return df[(df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end))]


def fake_book(product):
    df = FUT[product]
    t = CLOCK["t"]
    last = df.close[(df.index < t) & (df.index >= t - pd.Timedelta(minutes=31))]
    if last.empty:
        return np.nan, np.nan
    px = last.iloc[-1]
    tick = SPEC_BY_PRODUCT[product].tick
    return px - tick / 2, px + tick / 2


def main(start, end, model_dir=os.path.join(ROOT, "bot")):
    global SPEC_BY_PRODUCT
    specs = engine.load_specs()
    SPEC_BY_PRODUCT = {s.product: s for s in specs.values()}
    meta = __import__("json").load(open(os.path.join(model_dir, "model_meta.json")))
    K, THETA, H = float(meta.get("K", wick.K)), float(meta.get("THETA", wick.THETA)), int(meta.get("H", wick.H))
    LB, WB, MINC = int(meta.get("L", wick.L)), int(meta.get("wbeta") or wick.W), float(meta.get("min_contract_usd") or 0)
    coins = meta["coins"]
    for c in ["BTC"] + coins:
        d = pd.read_parquet(os.path.join(ROOT, "data", "minute", f"{c}.parquet")).drop_duplicates("ts").set_index("ts")
        SPOT[c] = d[["open", "high", "low", "close", "volume"]].astype(float)
    for c in coins:
        d = pd.read_parquet(os.path.join(ROOT, "data", "cfm", f"{c}.parquet")).drop_duplicates("ts").set_index("ts")
        FUT[specs[c].product] = d[d.volume > 0][["open", "high", "low", "close", "volume"]].astype(float)
    import time as _t
    _t0 = _t.time()
    engine.now_utc = fake_now
    def fake_depth(product, limit=50):
        b, a = fake_book(product)
        return ([(b, 1e6)] if np.isfinite(b) else []), ([(a, 1e6)] if np.isfinite(a) else [])
    market.spot_candles, market.futures_candles, market.book_top, market.book = fake_spot, fake_fut, fake_book, fake_depth
    tmp = tempfile.mkdtemp()
    cfg = dict(capital=10000, notional_frac=0.25, max_positions=99, daily_loss_limit=1.0, fee_bp_maker=2.0, fee_bp_taker=2.0)
    CLOCK["t"] = pd.Timestamp(start)
    eng = engine.Engine(mode="paper", cfg=cfg, state_path=os.path.join(tmp, "state.json"),
                        log_path=os.path.join(tmp, "events.jsonl"), model_dir=model_dir)
    eng.backfill()
    import builtins
    _print = builtins.print
    builtins.print = lambda *a, **k: None                         # keep the replay quiet
    try:
        for t in pd.date_range(start, end, freq="min", inclusive="left"):
            CLOCK["t"] = t
            eng.step()
    finally:
        builtins.print = _print
    ev = pd.read_json(os.path.join(tmp, "events.jsonl"), lines=True)
    ent = ev[ev.kind == "fill_entry"].reindex(columns=["ts", "coin", "px"])
    ext = ev[ev.kind == "fill_exit"].reindex(columns=["ts", "coin", "exit", "px", "entry_px", "net_bp"])
    print(f"engine: {len(ent)} entries, {len(ext)} exits, mean net {ext.net_bp.mean():.1f} bp ({_t.time() - _t0:.0f}s)")
    # ---- vectorised research simulation of the same rule + same model over the same window
    w0 = (pd.Timestamp(start) - pd.Timedelta(days=12)).strftime("%Y-%m-%d %H:%M")
    w1 = (pd.Timestamp(end) + pd.Timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    idx, D = ws.load_ohlc(coins=["BTC"] + coins, start=w0, end=w1)
    pn = wick.panel({c: D[c]["cf"] for c in D}, {c: D[c]["vol"] for c in D}, coins, idx, k=K, lookback=LB, wbeta=WB)
    import lightgbm as lgb
    ms = [lgb.Booster(model_file=os.path.join(model_dir, f)) for f in meta.get("models", ["model.txt"])]
    et = idx.tz_localize("UTC").tz_convert("America/New_York")
    et_min = np.asarray(et.hour * 60 + et.minute)
    q_lo, q_hi = cfg.get("quiet_et", [16 * 60 + 55, 18 * 60 + 5])
    quiet = (et_min >= q_lo) & (et_min < q_hi)
    rows = []
    i0, i1 = idx.get_indexer([pd.Timestamp(start), pd.Timestamp(end)])
    for c in coins:
        sp = specs[c]
        F = FUT[sp.product].reindex(idx) if sp.product in FUT else pd.DataFrame(index=idx, columns=["open", "high", "low", "close"], dtype=float)
        fcf = F.close.ffill(limit=30).to_numpy()
        basis = wick.shift(fcf / D[c]["cf"], 1)
        lv = wick.round_down(pn[c].level.to_numpy() * basis, sp.tick)
        lv[:i0] = np.nan
        lv[i1:] = np.nan
        pred = np.full(len(idx), -np.inf)
        rng = np.arange(i0, i1)
        pred[rng] = np.mean([m.predict(pn[c].iloc[rng][wick.FEATS]) for m in ms], axis=0)
        lv[pred <= meta["threshold"]] = np.nan
        lv[quiet] = np.nan                                   # engine: no new bids in the quiet window
        with np.errstate(invalid="ignore"):
            lv[sp.size * lv < MINC] = np.nan                 # engine: contract under the minimum value
        # engine skips when level >= best bid (= last futures close - tick/2 in this replay)
        lv[lv >= wick.shift(fcf, 1) - sp.tick / 2] = np.nan
        tick = np.nan_to_num(sp.tick / fcf, nan=1.0)
        ei, xi, ep, xp, ty = ws.run_book(F.open.to_numpy(), F.high.to_numpy(), F.low.to_numpy(), fcf, lv,
                                         THETA * K * pn[c].sig.to_numpy(), np.full(len(idx), np.nan), 1,
                                         tick, H, 0)
        for a, b, p, q, y in zip(ei, xi, ep, xp, ty):
            rows.append(dict(coin=c, entry_ts=idx[a], exit_ts=idx[b], entry_px=p, type=y))
    R = pd.DataFrame(rows)
    print(f"research: {len(R)} trades")
    e2 = ent.assign(minute=pd.to_datetime(ent.ts).dt.floor("min") - pd.Timedelta(minutes=1))
    both = R.merge(e2, left_on=["coin", "entry_ts"], right_on=["coin", "minute"], how="outer", indicator=True)
    print(both._merge.value_counts().to_string())
    mism = both[both._merge != "both"]
    if len(mism):
        print(mism[["coin", "entry_ts", "minute", "entry_px", "px", "_merge"]].head(20).to_string())
    else:
        print("PARITY OK: identical entry minutes")
    print("max entry price diff:", float(np.nanmax(np.abs(both.entry_px - both.px))) if len(both) else 0)


if __name__ == "__main__":
    main(*sys.argv[1:4])
