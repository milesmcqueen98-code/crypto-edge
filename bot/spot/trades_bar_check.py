#!/usr/bin/env python3
"""Network check of the newest minute from trades (bot/spot/README.md, "Newest minute from trades"). Runs on a GitHub
runner (exchange APIs are blocked on the research machine). Places nothing; public endpoints only.

Each minute t, 6 s after it starts, for BTC and the 17 coins, as the engine does in that order:
  1. the candles the engine would fetch at that step (same address: start t - 4 min, end t - 1 min, the steady state
     of its 3-minute re-fetch); this gives the first-seen candle of minute m = t - 1 min and the re-fetched candle of
     m - 1 min;
  2. the trades pass for m with the engine's budget (8 s) and the same function (bot/market.py minute_trades_bar);
  3. the final candle of the minute built 3 minutes earlier, fetched with an address nobody else uses (start m - 10 min,
     end m - 3 min), so the public cache cannot hand back an old copy made by someone else.
Then, per coin and overall: share verified, pages, seconds used for all coins, and the share of minutes where the
trades bar, the engine's row (trades bar if verified, else the candle) and the first-seen candle each match the final
candle (close, high, low exactly; volume within 0.5%). An absent row matches an absent final row.

Usage: python bot/spot/trades_bar_check.py [--minutes 30] [--budget 8]
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot import market as M  # noqa: E402

COINS = ["BTC"] + json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))["coins"]
COLS = ["open", "high", "low", "close", "volume"]


def row_of(df, m):
    if df is None or m not in df.index:
        return None
    r = df.loc[m]
    return None if not r["volume"] > 0 else {k: float(r[k]) for k in COLS}


def match(a, b):
    if a is None or b is None:
        return a is None and b is None
    return (a["close"] == b["close"] and a["high"] == b["high"] and a["low"] == b["low"]
            and abs(a["volume"] - b["volume"]) <= 0.005 * max(b["volume"], 1e-12))


def final_candles(coin, m):
    """Candles [m - 10 min, m - 3 min] through the header helper, with the answer's age."""
    s, e = m - pd.Timedelta(minutes=10), m - pd.Timedelta(minutes=3)
    js, hd = M._get_h(f"{M.EXCHANGE}/products/{coin}-USD/candles",
                      {"granularity": 60, "start": s.isoformat() + "Z", "end": e.isoformat() + "Z"})
    rows = {pd.Timestamp(r[0], unit="s"): dict(open=float(r[3]), high=float(r[2]), low=float(r[1]), close=float(r[4]),
                                              volume=float(r[5])) for r in js or []}
    return rows, hd.get("Age"), hd.get("cf-cache-status")


def main(minutes, budget):
    print(f"coins {COINS}; {minutes} minutes; budget {budget} s", flush=True)
    first, refetch, tb, timing, finals, errs = {}, {}, {}, [], {}, []
    stop = time.time() + 60 * minutes
    n_loop = 0
    while time.time() < stop or n_loop < 3:                # three more steps at the end for the last finals
        if time.time() >= stop:
            n_loop += 1
        nxt = (math.floor(time.time() / 60) + 1) * 60 + 6
        time.sleep(max(0.0, nxt - time.time()))
        t = pd.Timestamp(math.floor(time.time() / 60) * 60, unit="s")
        m = t - pd.Timedelta(minutes=1)
        t0 = time.monotonic()
        building = time.time() < stop
        # 1. candles as the engine fetches them
        for c in COINS:
            try:
                d = M.spot_candles(c, t - pd.Timedelta(minutes=4), t)
                first[(c, m)] = row_of(d, m)
                refetch[(c, m - pd.Timedelta(minutes=1))] = row_of(d, m - pd.Timedelta(minutes=1))
            except Exception as err:  # noqa: BLE001
                errs.append(f"candles {c} {m}: {err!r}"[:200])
        t1 = time.monotonic()
        # 2. trades pass, as Engine.trades_pass
        if building:
            tt = time.monotonic()
            for i, c in enumerate(COINS):
                if time.monotonic() - tt > budget:
                    for c2 in COINS[i:]:
                        tb[(c2, m)] = dict(verified=False, reason="budget", pages=0, s=0.0)
                    break
                a = time.monotonic()
                try:
                    r = M.minute_trades_bar(c, m, deadline=tt + budget)
                    r["s"] = time.monotonic() - a
                    tb[(c, m)] = r
                except M.Refused as err:
                    print(f"REFUSED: {err}", flush=True)
                    errs.append(f"refused {c} {m}: {err}"[:200])
                    tb[(c, m)] = dict(verified=False, reason="refused", pages=0, s=time.monotonic() - a)
                    break
                except Exception as err:  # noqa: BLE001
                    errs.append(f"trades {c} {m}: {err!r}"[:200])
                    tb[(c, m)] = dict(verified=False, reason="error", pages=0, s=time.monotonic() - a)
        t2, w2 = time.monotonic(), time.time()
        # 3. final candles of the minute built 3 minutes ago (and the 6 minutes before it, unused)
        mf = m - pd.Timedelta(minutes=3)
        if any((c, mf) in tb for c in COINS):
            for c in COINS:
                try:
                    rows, age, cache = final_candles(c, m)
                    finals[(c, mf)] = (rows.get(mf), age, cache)
                except Exception as err:  # noqa: BLE001
                    errs.append(f"final {c} {mf}: {err!r}"[:200])
        t3 = time.monotonic()
        timing.append(dict(minute=m, candles_s=round(t1 - t0, 2), trades_s=round(t2 - t1, 2),
                           finals_s=round(t3 - t2, 2), data_done_s=round(w2 - t.timestamp(), 2)))
        nv = sum(1 for c in COINS if tb.get((c, m), {}).get("verified"))
        print(f"{m} candles {t1 - t0:.1f}s trades {t2 - t1:.1f}s finals {t3 - t2:.1f}s verified {nv}/{len(COINS)}"
              + (f" errors so far {len(errs)}" if errs else ""), flush=True)

    rows = []
    for (c, m), r in tb.items():
        if (c, m) not in finals:
            continue
        fin, age, cache = finals[(c, m)]
        fs = first.get((c, m), "missing")
        if fs == "missing":
            continue
        bar = r.get("bar") if r.get("verified") else None
        eng = bar if r.get("verified") else fs
        rf = refetch.get((c, m), "missing")
        rows.append(dict(coin=c, minute=m, verified=bool(r.get("verified")), reason=r.get("reason"),
                         pages=r.get("pages", 0), s=r.get("s", 0.0),
                         gen_lag_s=(r["gen"] - (m + pd.Timedelta(minutes=1))).total_seconds() if r.get("gen") is not None
                         else np.nan,
                         tb_match=match(bar, fin) if r.get("verified") else np.nan,
                         eng_match=match(eng, fin), first_match=match(fs, fin), first_absent=fs is None,
                         final_absent=fin is None,
                         refetch_match=match(rf, fin) if rf != "missing" else np.nan,
                         final_age=age, final_cache=cache))
    R = pd.DataFrame(rows)
    T = pd.DataFrame(timing)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    if not len(R):
        print("no minutes with a final candle; errors:", errs[:20])
        return
    g = R.groupby("coin", sort=False)
    out = pd.DataFrame({
        "minutes": g.size(),
        "verified": g.verified.mean().round(3),
        "pages_mean": g.pages.mean().round(2), "pages_max": g.pages.max(),
        "sec_mean": g.s.mean().round(2), "sec_max": g.s.max().round(2),
        "trades_vs_final": g.tb_match.mean().round(3),
        "engine_row_vs_final": g.eng_match.mean().round(3),
        "first_seen_vs_final": g.first_match.mean().round(3),
        "first_seen_absent": g.first_absent.mean().round(3),
        "refetch_vs_final": g.refetch_match.mean().round(3),
        "gen_lag_med_s": g.gen_lag_s.median().round(1),
    })
    print("\nPER COIN (trades_vs_final over verified minutes; engine_row = trades bar if verified, else the candle)")
    print(out.to_string())
    tot = dict(minutes=len(R) // len(COINS), coin_minutes=len(R), verified=round(R.verified.mean(), 3),
               pages_mean=round(R.pages.mean(), 2), pages_max=int(R.pages.max()),
               trades_vs_final=round(R.tb_match.mean(), 3), engine_row_vs_final=round(R.eng_match.mean(), 3),
               first_seen_vs_final=round(R.first_match.mean(), 3), first_seen_absent=round(R.first_absent.mean(), 3),
               refetch_vs_final=round(R.refetch_match.mean(), 3))
    print("\nOVERALL", json.dumps(tot))
    print("unverified reasons:", R[~R.verified].reason.value_counts().to_dict())
    print("final candle answers: Age", R.final_age.value_counts(dropna=False).head(8).to_dict(),
          "cf-cache-status", R.final_cache.value_counts(dropna=False).to_dict())
    tt = T[T.minute.isin(R.minute.unique())]
    print("\nseconds per step for all coins: candles median %.2f max %.2f; trades median %.2f max %.2f; "
          "data step done at median %.2f max %.2f s after the minute"
          % (tt.candles_s.median(), tt.candles_s.max(), tt.trades_s.median(), tt.trades_s.max(),
             tt.data_done_s.median(), tt.data_done_s.max()))
    bad = R[R.verified & (R.tb_match == False)]  # noqa: E712
    if len(bad):
        print("\nverified trades bars that differ from the final candle:")
        for x in bad.head(15).itertuples():
            print(f"  {x.coin} {x.minute}: trades {tb[(x.coin, x.minute)]['bar']} final {finals[(x.coin, x.minute)][0]}")
    if errs:
        print(f"\n{len(errs)} errors; first ones:")
        for e in errs[:15]:
            print("  " + e)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=30)
    p.add_argument("--budget", type=float, default=8.0)
    a = p.parse_args()
    main(a.minutes, a.budget)
