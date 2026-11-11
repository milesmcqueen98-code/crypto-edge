#!/usr/bin/env python3
"""Paper smoke run of a paper book (default: the trades book) on live public data, for the generic runner (hunt2.yml takes a script, not a
command). Waits until the run will cover a heartbeat minute (:00 or :30), then runs
  python bot/spot/run.py paper --minutes <minutes> --config <config> --state-dir <state_dir>
and prints the tail of its event log and every heartbeat. No keys, no orders.

Usage: python bot/spot/tb_smoke.py [--minutes 10] [--state-dir /tmp/tb_smoke] [--config bot/spot/config.tb.json]
       [--parity]

--parity: the same paper run, in this process (Engine(mode="paper", ...).run(minutes), what run.py paper does), so
the engine's table can be read when it ends. Then the venue's candles of the last 45 minutes are fetched once more
(bot/market.py spot_candles; a refusal or rate limit stops the fetch at once, no retry, and is reported) and compared
with the rows the engine holds, per coin, leaving out the newest three minutes: minutes compared, rows identical (all
five values equal), rows that differ (and the largest close difference in bp), rows only the engine has, rows only
the venue has, and engine rows in the range still marked trades-built.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

p = argparse.ArgumentParser()
p.add_argument("--minutes", type=float, default=10)
p.add_argument("--state-dir", default="/tmp/tb_smoke")
p.add_argument("--config", default=os.path.join(HERE, "config.tb.json"), help="repo-relative or absolute")
p.add_argument("--repair-probe", action="store_true",
               help="instead: start the engine on live data, mark the 4 minutes before the newest as open for the "
                    "listed coins, run one trades pass and print its counts (shows the repair path on the real market)")
p.add_argument("--parity", action="store_true", help="after the run, compare the engine's rows with a new fetch "
                                                      "of the venue's candles (last 45 minutes, newest three left out)")
a = p.parse_args()


def parity(eng):
    import numpy as np
    import pandas as pd
    from bot import market
    last = pd.Timestamp(eng.state["last_minute"])           # the last step: the engine holds rows through last - 1
    lo, hi = last - pd.Timedelta(minutes=45), last - pd.Timedelta(minutes=4)
    print(f"\nparity: venue candles {lo} .. {last - pd.Timedelta(minutes=1)} fetched at {pd.Timestamp.now(tz='UTC')}; "
          f"compared {lo} .. {hi} (newest three minutes left out)", flush=True)
    rows, stop = [], None
    for c in ["BTC"] + eng.coins:
        if stop:
            break
        meta = {}
        try:
            v = market.spot_candles(c, lo, last, meta=meta)
        except market.Refused as err:                        # refusal or rate limit (Limited): stop, report
            stop = f"{c}: {err!r}"[:300]
            print("REFUSED (parity fetch stopped):", stop, flush=True)
            break
        except Exception as err:
            print("ERROR parity fetch", c, repr(err)[:300], flush=True)
            continue
        e = eng.spot.get(c)
        e = e[(e.index >= lo) & (e.index <= hi)] if e is not None else None
        v = v[(v.index >= lo) & (v.index <= hi)]
        both = sorted(set(e.index) & set(v.index)) if e is not None else []
        cols = ["open", "high", "low", "close", "volume"]
        same = [m for m in both if all(float(e.loc[m, k]) == float(v.loc[m, k]) for k in cols)]
        diff = [m for m in both if m not in same]
        bp = max((abs(np.log(float(e.loc[m, "close"]) / float(v.loc[m, "close"]))) * 1e4 for m in diff), default=0.0)
        prov = eng._prov.get(c, {})
        tbm = sum(1 for m in (e.index if e is not None else []) if prov.get(m, (None, False))[1])
        rows.append(dict(coin=c, minutes=int((hi - lo) / pd.Timedelta(minutes=1)) + 1, identical=len(same),
                         differ=len(diff), max_close_diff_bp=round(bp, 2),
                         engine_only=len(set(e.index) - set(v.index)) if e is not None else 0,
                         venue_only=len(set(v.index) - set(e.index if e is not None else [])), trades_built=tbm,
                         answer_gen=str(meta.get("gen")), cache=meta.get("cache")))
    print(pd.DataFrame(rows).to_string(index=False), flush=True)
    return stop

if a.repair_probe:
    import pandas as pd
    sys.path.insert(0, ROOT)
    from bot.spot.engine import Engine
    cfg = json.load(open(os.path.join(ROOT, a.config)))
    eng = Engine(mode="paper", cfg=cfg, state_dir=a.state_dir, echo=False)
    eng.start()
    print("start-up counts (start-up repair included):", json.dumps(eng.counts), flush=True)
    t = eng.clock().floor("min")
    eng.update_spot(t)
    m = t - pd.Timedelta(minutes=1)
    listed = [c for c in ["BTC"] + eng.coins if eng.trades_coins is None or c in eng.trades_coins]
    for c in listed:
        for k in range(1, 5):
            eng._prov.get(c, {}).pop(m - pd.Timedelta(minutes=k), None)
    eng.counts = {}
    eng.trades_pass(m)
    print(f"repair probe at {m}: listed {listed}; counts", json.dumps(eng.counts), flush=True)
    sys.exit(0 if eng.counts.get("tb_rebuilt") == 4 * len(listed) else 1)

# start at minute 20 or 50 of the hour: the backfill takes a few minutes and the steps then cross :30 or :00
while int(time.time() // 60) % 30 != 20:
    time.sleep(5)
refused = None
if a.parity:
    sys.path.insert(0, ROOT)
    from bot.spot.engine import Engine
    cfg = json.load(open(os.path.join(ROOT, a.config)))
    print(f"running in process: Engine(mode=paper, config={a.config}, state_dir={a.state_dir}).run({a.minutes})",
          flush=True)
    eng = Engine(mode="paper", cfg=cfg, state_dir=a.state_dir, echo=False)
    eng.run(a.minutes)
    rc = subprocess.CompletedProcess([], 0)
else:
    cmd = [sys.executable, os.path.join(HERE, "run.py"), "paper", "--minutes", str(a.minutes), "--config",
           os.path.join(ROOT, a.config), "--state-dir", a.state_dir]
    print("running:", " ".join(cmd), flush=True)
    rc = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    print("exit code", rc.returncode)
    if rc.stderr:
        print("stderr tail:\n" + rc.stderr[-3000:])
ev = [json.loads(x) for x in open(os.path.join(a.state_dir, "events.jsonl"))]
kinds = {}
for e in ev:
    kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
print("event kinds:", kinds)
print("\nlast 25 events (adv lines shortened):")
for e in ev[-25:]:
    s = json.dumps(e)
    print(s if len(s) < 600 else s[:600] + " ...")
print("\nheartbeats:")
for e in ev:
    if e["kind"] == "heartbeat":
        print(json.dumps(e))
print("\nerrors and warnings:")
for e in ev:
    if e["kind"] in ("error", "warning", "stale_input"):
        print(json.dumps(e)[:600])
if a.parity:
    refused = parity(eng)
sys.exit(rc.returncode or (3 if refused else 0))
