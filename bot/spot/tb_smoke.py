#!/usr/bin/env python3
"""Paper smoke run of a paper book (default: the trades book) on live public data, for the generic runner (hunt2.yml takes a script, not a
command). Waits until the run will cover a heartbeat minute (:00 or :30), then runs
  python bot/spot/run.py paper --minutes <minutes> --config <config> --state-dir <state_dir>
and prints the tail of its event log and every heartbeat. No keys, no orders.

Usage: python bot/spot/tb_smoke.py [--minutes 10] [--state-dir /tmp/tb_smoke] [--config bot/spot/config.tb.json]
       [--parity] [--set KEY=JSON ...] [--then KEY=JSON ...]

--parity: the same paper run, in this process (Engine(mode="paper", ...).run(minutes), what run.py paper does), so
the engine's table can be read when it ends. Then the venue's candles of the last 45 minutes are fetched once more
(bot/market.py spot_candles; a refusal or rate limit stops the fetch at once, no retry, and is reported) and compared
with the rows the engine holds, per coin, leaving out the newest three minutes: minutes compared, rows identical (all
five values equal), rows that differ (and the largest close difference in bp), rows only the engine has, rows only
the venue has, and engine rows in the range still marked trades-built. It also prints, per step, when the step
started and when its data part ended (seconds after the minute, wall clock), the candle and trades requests the step
made, and the candle requests made between the step and the one before it (the candle pass of "candles_at_s"), then
the medians. It also prints, per step and for the run, the trades pass's own duration by the engine's timer (median and
longest), its budget fallbacks (tb_fb_budget), and the most trades requests sent in any one second (bot/market.py
trades_peak; both paths, the start-up pass included). With trades_workers 2 or more, a step's trades requests are the
coins the side-by-side pass started.

--set KEY=JSON: override a key of the config (null removes it), e.g. --set candles_at_s=45 or --set candles_at_s=null.
--then KEY=JSON (with --parity; repeatable): after the first run and its parity check, a second run of the same
length on the same runner, in a fresh state dir (<state-dir>_then), with these overrides on top of the first run's
config, then its parity check and lines comparing the two runs' data step medians and trades passes. No wait before
the second run (any 30 minutes of steps cross one heartbeat minute). E.g. --set trades_workers=1 --then
trades_workers=3: the sequential trades pass, then three coins at a time.
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
p.add_argument("--set", action="append", default=[], help="KEY=JSON: override a config key (null removes it)")
p.add_argument("--then", action="append", default=[], help="KEY=JSON: with --parity, a second run with these overrides")
a = p.parse_args()


def overrides(cfg, items):
    """cfg with KEY=JSON items applied (a JSON null removes the key)."""
    out = dict(cfg)
    for x in items:
        k, v = x.split("=", 1)
        v = json.loads(v)
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


def instrument(eng):
    """Per step: start and data-end times (seconds after the minute, wall clock) and the requests it made; candle
    requests between steps. Wraps the engine's and its market's methods on the instance; changes nothing else."""
    rec, cur, between = [], {}, {"candles": 0}
    step, mark, mkt, tpass = eng.step, eng._mark, eng.market, eng.trades_pass
    sc, tb, tbs = mkt.spot_candles, mkt.trades_bar, mkt.trades_bars

    def w_step(t=None):
        t0 = time.time()
        cur.clear()
        cur.update(on=True, t0=t0, data=None, candles=0, trades=0, trades_s=None, fb_budget=None)
        try:
            return step(t)
        finally:
            m0 = int(t0 // 60) * 60
            rec.append(dict(minute=time.strftime("%H:%M", time.gmtime(m0)), start_s=round(t0 - m0, 2),
                            data_end_s=None if cur["data"] is None else round(cur["data"] - m0, 2),
                            step_candles=cur["candles"], step_trades=cur["trades"], pass_candles=between["candles"],
                            trades_s=cur["trades_s"], fb_budget=cur["fb_budget"]))
            cur["on"], between["candles"] = False, 0

    def w_mark(k, t):
        if k == "data" and cur.get("on"):
            cur["data"] = time.time()
        return mark(k, t)

    def count(kind, f):
        def g(*x, **kw):
            if cur.get("on"):
                cur[kind] += 1
            elif kind == "candles":
                between["candles"] += 1
            return f(*x, **kw)
        return g
    def w_pass(m):
        """The trades pass's own duration (engine timer) and its budget fallbacks."""
        b0, t0 = eng.counts.get("tb_fb_budget", 0), eng._timer()
        try:
            return tpass(m)
        finally:
            if cur.get("on"):
                cur["trades_s"] = round(eng._timer() - t0, 3)
                cur["fb_budget"] = eng.counts.get("tb_fb_budget", 0) - b0

    def w_many(jobs, *x, **kw):
        out = many(jobs, *x, **kw)
        if cur.get("on"):
            cur["trades"] += sum(1 for o in out if o.get("started"))
        return out
    eng.step, eng._mark, eng.trades_pass = w_step, w_mark, w_pass
    mkt.spot_candles, mkt.trades_bar, mkt.trades_bars = count("candles", sc), count("trades", tb), count("trades", tbs)
    many = getattr(mkt, "trades_many", None)
    if many is not None:
        mkt.trades_many = w_many
    return rec


def timing(rec, label):
    import pandas as pd
    print(f"\nstep timing ({label}; seconds after the minute, wall clock):", flush=True)
    if not rec:
        print("  no steps", flush=True)
        return None, {}
    d = pd.DataFrame(rec)
    print(d.to_string(index=False), flush=True)
    med = d.median(numeric_only=True)
    print(f"  median: step start {med['start_s']:.2f} s, data step end {med['data_end_s']:.2f} s (max "
          f"{d.data_end_s.max():.2f} s); per step {med['step_candles']:g} candle and {med['step_trades']:g} trades "
          f"requests; {med['pass_candles']:g} candle requests between steps", flush=True)
    tr = d.trades_s.dropna() if "trades_s" in d else pd.Series(dtype=float)
    fb = int(d.fb_budget.fillna(0).sum()) if "fb_budget" in d else 0
    tp = dict(median=float(tr.median()) if len(tr) else None, longest=float(tr.max()) if len(tr) else None, fb=fb)
    if len(tr):
        print(f"  trades pass ({label}; engine timer): median {tp['median']:.2f} s, longest {tp['longest']:.2f} s; "
              f"budget fallbacks (tb_fb_budget) {fb}", flush=True)
    else:
        print(f"  trades pass ({label}): none in the steps (newest_bar not trades)", flush=True)
    return float(med["data_end_s"]), tp


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

def events(sd):
    ev = [json.loads(x) for x in open(os.path.join(sd, "events.jsonl"))]
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


def in_process(cfg, sd, label):
    """One paper run in this process (what run.py paper does), its events, step timing and parity check."""
    from bot import market
    from bot.spot.engine import Engine
    print(f"\n===== {label}: running in process: Engine(mode=paper, config={a.config}, overrides {label}, "
          f"state_dir={sd}).run({a.minutes}); candles_at_s {cfg.get('candles_at_s')}, trades_workers "
          f"{cfg.get('trades_workers')}", flush=True)
    eng = Engine(mode="paper", cfg=cfg, state_dir=sd, echo=False)
    rec = instrument(eng)
    market.trades_peak(reset=True)
    eng.run(a.minutes)
    peak = market.trades_peak(reset=True)
    events(sd)
    med, tp = timing(rec, label)
    tp["peak"] = peak
    print(f"  trades requests ({label}): at most {peak} sent in any one second (start-up pass included)", flush=True)
    return parity(eng), med, tp


if a.then and not a.parity:
    sys.exit("--then needs --parity (the second run is in process)")
cfg0 = overrides(json.load(open(os.path.join(ROOT, a.config))), a.set)
# start at minute 20 or 50 of the hour: the backfill takes a few minutes and the steps then cross :30 or :00
while int(time.time() // 60) % 30 != 20:
    time.sleep(5)
refused = None
if a.parity:
    sys.path.insert(0, ROOT)
    refused, m1, p1 = in_process(cfg0, a.state_dir, " ".join(a.set) or "none")
    if a.then:
        r2, m2, p2 = in_process(overrides(cfg0, a.then), a.state_dir + "_then", " ".join(a.set + a.then))
        refused = refused or r2
        print(f"\ndata step end, median seconds after the minute: first run {m1}, second run {m2}"
              + (f" (second minus first: {m2 - m1:+.2f} s)" if m1 is not None and m2 is not None else ""), flush=True)
        for lab, p in (("first run", p1), ("second run", p2)):
            print(f"trades pass, {lab}: median {p.get('median')} s, longest {p.get('longest')} s, budget fallbacks "
                  f"{p.get('fb')}, at most {p.get('peak')} trades requests in one second", flush=True)
    sys.exit(3 if refused else 0)
cfg_path = os.path.join(ROOT, a.config)
if a.set:                                                  # run.py takes a file: the overridden config next to state
    cfg_path = a.state_dir.rstrip("/") + "_config.json"
    json.dump(cfg0, open(cfg_path, "w"), indent=2)
cmd = [sys.executable, os.path.join(HERE, "run.py"), "paper", "--minutes", str(a.minutes), "--config", cfg_path,
       "--state-dir", a.state_dir]
print("running:", " ".join(cmd), flush=True)
rc = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
print("exit code", rc.returncode)
if rc.stderr:
    print("stderr tail:\n" + rc.stderr[-3000:])
events(a.state_dir)
sys.exit(rc.returncode)
