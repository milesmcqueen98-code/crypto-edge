#!/usr/bin/env python3
"""Wick catcher, $1M rules, on Coinbase spot. Read bot/spot/README.md first.

  python bot/spot/run.py paper [--minutes 345]           paper trading on live public data (no keys), logs to paper_spot/
  python bot/spot/run.py preflight                       live keys: permissions, balances, fee tier, which coins you can trade
  python bot/spot/run.py live                            real orders (needs keys and I_UNDERSTAND_LIVE_TRADING=yes), logs to live_spot/
  python bot/spot/run.py status [--state-dir live_spot]  equity, open rungs, resting orders, halts
  python bot/spot/run.py report [--state-dir paper_spot] fills, net bp per rung, P&L by day, capture vs volume
  python bot/spot/run.py stop | resume                   kill switch: no new bids (exits still run) / remove it
  python bot/spot/run.py cancel-all [--flatten]          live: cancel every bot order; --flatten also sells every open rung
  python bot/spot/run.py reset-halt                      clear the drawdown stop after you have looked at why it fired
  python bot/spot/run.py usdc-check                      ladder v5 C4: the pre-registered USDC verification (places and
                                                         cancels one $10 bid far below the market; needs the live switch)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("cmd", choices=["paper", "live", "preflight", "status", "report", "stop", "resume", "cancel-all",
                               "reset-halt", "usdc-check"])
p.add_argument("--minutes", type=float, default=None, help="how long to run (default: 345 paper, forever live)")
p.add_argument("--config", default=os.path.join(HERE, "config.json"))
p.add_argument("--capital", type=float, default=None, help="override the config's capital (first start only)")
p.add_argument("--state-dir", default=None, help="default: paper_spot/ (paper) or live_spot/ (live and the live tools)")
p.add_argument("--flatten", action="store_true")
a = p.parse_args()
cfg = json.load(open(a.config))
if a.capital:
    cfg["capital"] = a.capital
live_cmds = ("live", "preflight", "cancel-all", "usdc-check")
default_dir = "paper_spot" if a.cmd == "paper" or (a.cmd == "report" and not a.state_dir) else "live_spot"
sd = os.path.abspath(a.state_dir or os.path.join(ROOT, default_dir))


def need_keys():
    if not (os.environ.get("COINBASE_API_KEY") and os.environ.get("COINBASE_API_SECRET")):
        sys.exit("Set COINBASE_API_KEY and COINBASE_API_SECRET (see bot/spot/README.md, step 3).")


if a.cmd in ("paper", "live"):
    from bot.spot.engine import Engine
    if a.cmd == "live":
        need_keys()
        if not float(cfg.get("capital") or 0) > 0:
            sys.exit("No capital set for live trading. Run: sudo wickctl configure")
        if os.environ.get("I_UNDERSTAND_LIVE_TRADING") != "yes":
            sys.exit("Live mode places real orders. Set I_UNDERSTAND_LIVE_TRADING=yes after reading bot/spot/README.md.")
    mins = a.minutes if a.minutes is not None else (345 if a.cmd == "paper" else 1e9)
    Engine(mode=a.cmd, cfg=cfg, state_dir=sd).run(mins)

elif a.cmd == "preflight":
    need_keys()
    import pandas as pd
    from bot import market
    from bot.spot.engine import LiveBroker, Spec, fmt, floor_to
    meta = json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))
    br = LiveBroker(quote=cfg.get("quote", "USD"))
    ok = True
    try:
        perm = br._d(br.c.get_api_key_permissions())
        print("key permissions:", {k: perm.get(k) for k in ("can_view", "can_trade", "can_transfer", "portfolio_uuid",
                                                            "portfolio_type")})
        if not perm.get("can_trade"):
            ok = False
            print("  !! the key cannot trade: recreate it with the Trade permission")
        if perm.get("can_transfer"):
            print("  !! the key can transfer funds out: recreate it without the Transfer permission")
    except Exception as err:
        ok = False
        print("could not read key permissions:", repr(err)[:300])
    try:
        bal = br.balances()
        print("balances (available, on hold):", {k: v for k, v in bal.items() if sum(v) > 0})
        print(f"cash the bot can use ({br.quote}): ${br.cash():,.0f} (config capital ${cfg['capital']:,.0f})")
        if br.cash() < 0.5 * cfg["capital"]:
            print(f"  !! less than half the configured capital is available as {br.quote} in this portfolio")
        stray = [k for k, v in bal.items() if k not in ("USD", "USDC") and sum(v) > 0]
        if stray:
            print("  note: this portfolio also holds", stray, "- the bot's portfolio should hold only its own cash")
    except Exception as err:
        ok = False
        print("could not read balances:", repr(err)[:300])
    try:
        print("fee tier:", br.fee_tier())
    except Exception as err:
        print("could not read the fee tier:", repr(err)[:300])
    tradable, blocked, unknown, specs = [], {}, {}, {}
    for c in meta["coins"]:
        pid = br._p(f"{c}-USD")                                    # the -USDC alias when quote is USDC
        try:
            pr = br._d(br.c.get_product(pid))
            flags = {k: pr.get(k) for k in ("trading_disabled", "is_disabled", "view_only", "cancel_only", "limit_only",
                                            "post_only", "status") if pr.get(k) not in (None, False, "online", "")}
            if pr.get("trading_disabled") or pr.get("is_disabled") or pr.get("view_only") or pr.get("cancel_only"):
                blocked[c] = flags
                continue
            px = float(pr.get("price") or market.book_top(pid)[0])
            tick, lot = float(pr["quote_increment"]), float(pr["base_increment"])
            lim = floor_to(px * 0.5, tick)                         # far below the market: preview only, never placed
            size = max(floor_to(25.0 / lim, lot), float(pr.get("base_min_size") or lot))
            pv = br._d(br.c.preview_limit_order_gtc_buy(product_id=pid, base_size=fmt(size, lot),
                                                        limit_price=fmt(lim, tick), post_only=True))
            errs = pv.get("errs") or []
            if errs:
                blocked[c] = {"preview": errs}
            else:
                tradable.append(c)
                specs[c] = (Spec(f"{c}-USD", tick, lot), lim, size)
        except Exception as err:
            unknown[c] = repr(err)[:200]
    print(f"\ntradable for this account ({len(tradable)} of {len(meta['coins'])}):", tradable)
    for c, why in blocked.items():
        print(f"  not tradable: {c}: {why}")
    for c, why in unknown.items():
        print(f"  could not check (network?): {c}: {why}  -> run the preflight again")
    # how long Coinbase lets a good-til-date bid live at minimum (the bot's bids expire on their own)
    ttl = None
    if tradable:
        sp, lim, size = specs["ETH"] if "ETH" in specs else specs[tradable[0]]
        now = pd.Timestamp.now(tz="UTC").tz_localize(None)
        for d in (120, 300, 600, 900, 1800, 3600):
            try:
                errs = br.preview_gtd(sp, lim, size, now + pd.Timedelta(seconds=d))
            except Exception as err:
                print("could not preview a good-til-date bid:", repr(err)[:200])
                break
            if not errs:
                ttl = max(300, d)
                break
            if not any("DURATION_TOO_SMALL" in str(e).upper() for e in errs):
                print("good-til-date bid preview errors:", errs)
                break
        print(f"good-til-date bids: {f'{ttl} s' if ttl else 'NOT AVAILABLE - the bot would rest good-til-cancelled bids'}")
    if os.path.abspath(a.config) != os.path.abspath(os.path.join(HERE, "config.json")):
        cfg["coins_disabled"] = sorted(blocked)
        if ttl:
            cfg["bid_ttl_s"] = ttl
        json.dump(cfg, open(a.config, "w"), indent=2)
        print(f"wrote coins_disabled {sorted(blocked)} and bid_ttl_s {cfg.get('bid_ttl_s')} to {a.config}")
    else:
        print('put these in "coins_disabled" in your live config:', json.dumps(sorted(blocked)))
    print("\npreflight", "PASSED" if ok and tradable and not unknown else "FAILED")

elif a.cmd == "status":
    import pandas as pd
    st_path = os.path.join(sd, "state.json")
    if not os.path.exists(st_path):
        sys.exit(f"no state in {sd}")
    st = json.load(open(st_path))
    cap = cfg.get("capital")
    print(f"state {sd}: last minute {st.get('last_minute')}")
    print(f"equity ${st['equity']:,.2f} (config capital ${cap:,.0f}); marked peak ${st.get('peak', cap):,.2f}; "
          f"day start ${st['day_start_equity']:,.2f}")
    halts = [h for h, on in (("STOP file", os.path.exists(os.path.join(ROOT, "STOP")) or os.path.exists(os.path.join(sd, "STOP"))),
                             ("drawdown stop", st.get("dd_halt")), ("daily loss limit", st.get("halted_day") == st.get("day")))
             if on]
    print("halts:", halts or "none")
    for lad in st["ladders"].values():
        tr = {k: f"{v['size']:.6g} @ {v['cost'] / max(v['size'], 1e-18):.6g} (tp {v['tp_px']}, exit {v['exit_due'][11:16]})"
              for k, v in lad["tranches"].items()}
        od = {k: f"{o['side']} {o['size'] - o['filled']:.6g} @ {o['px']}" for k, o in lad["orders"].items()}
        print(f"  {lad['id']:10s} {lad['status']:5s} rungs {tr or '-'} orders {od or '-'}")

elif a.cmd == "report":
    import numpy as np
    import pandas as pd
    ev_path = os.path.join(sd, "events.jsonl")
    if not os.path.exists(ev_path):
        sys.exit(f"no events in {sd}")
    ev = pd.read_json(ev_path, lines=True)
    ev["ts"] = pd.to_datetime(ev.ts)
    ent, ext = ev[ev.kind == "fill_entry"], ev[ev.kind == "fill_exit"]
    print(f"{sd}: {ev.ts.min()} .. {ev.ts.max()}  ({(ev.ts.max() - ev.ts.min()).total_seconds() / 86400:.1f} days)")
    if len(ent):
        print(f"\nentry fills: {len(ent)} in {ent.ladder.nunique()} ladders; USD bought ${ent.usd.sum():,.0f}")
        print(ent.groupby("rung").agg(fills=("usd", "size"), usd=("usd", "sum")).round(0).to_string())
        if "beyond_usd" in ent and ent.beyond_usd.notna().any():
            e = ent[ent.beyond_usd > 0]
            b = e[e.left > 1e-12] if "left" in e else e.iloc[0:0]
            print(f"capture share (our fill / USD traded beyond our price in the fill minute), on fills that left the "
                  f"order partly unfilled: {b.usd.sum() / max(b.beyond_usd.sum(), 1e-9):.2f} over {len(b)} fills "
                  "(paper: the capture setting; live: the real one; the research assumed 0.5, robust at 0.25)")
    if len(ext):
        w = (ext.px - ext.entry_px) * ext["size"]
        ext = ext.assign(notional=ext.entry_px * ext["size"])
        print(f"\nexits: {len(ext)}; P&L ${ext.pnl.sum():,.2f}; net per USD {1e4 * ext.pnl.sum() / ext.notional.sum():.1f} bp "
              f"(gross {1e4 * w.sum() / ext.notional.sum():.1f} bp)")
        print(ext.groupby(["rung", "exit"]).agg(n=("pnl", "size"), pnl=("pnl", "sum"),
                                                 net_bp=("net_bp", "mean")).round(1).to_string())
        d = ext.set_index("ts").pnl.resample("D").sum()
        print("\nP&L by day:")
        print(d.round(2).to_string())
    for k in ("cash_short", "reject", "error", "warning", "halt"):
        n = int((ev.kind == k).sum())
        if n:
            print(f"{k}: {n}")
    hb = ev[ev.kind == "heartbeat"]
    if len(hb):
        last = hb.iloc[-1]
        print(f"\nlast heartbeat {last.ts}: equity ${last.equity:,.2f}, marked {last.mtm:,.2f}, committed ${last.committed:,.0f}")

elif a.cmd in ("stop", "resume"):
    f = os.path.join(ROOT, "STOP")
    if a.cmd == "stop":
        open(f, "w").write("no new bids; exits still run. Remove with: python bot/spot/run.py resume\n")
        print("STOP file written: the bot places no new bids from its next minute; open rungs still exit by the rules.")
    else:
        if os.path.exists(f):
            os.remove(f)
        print("STOP file removed.")

elif a.cmd == "cancel-all":
    need_keys()
    from bot.spot.engine import Engine
    if os.system("systemctl is-active --quiet wickbot 2>/dev/null") == 0:
        sys.exit("The bot service is running: stop it first (sudo systemctl stop wickbot), then run cancel-all.")
    eng = Engine(mode="live", cfg=cfg, state_dir=sd)
    eng.update_spot(eng.clock().floor("min"))
    left = eng.cancel_all(flatten=a.flatten)
    if left:
        print("NOT CONFIRMED, cancel these in the Coinbase app:", left)
    print("done: bot orders cancelled" + (" and open rungs sold" if a.flatten else "") +
          ". Start the service again only when you want it bidding.")

elif a.cmd == "usdc-check":
    # reports/ladder_v5_prereg.md, "USDC cash (C4), whatever its backtest: verify before use"
    need_keys()
    if os.environ.get("I_UNDERSTAND_LIVE_TRADING") != "yes":
        sys.exit("usdc-check places (and cancels) one real $10 bid. Set I_UNDERSTAND_LIVE_TRADING=yes to run it.")
    import time
    import pandas as pd
    from bot.spot.engine import LiveBroker, Spec, fmt, floor_to
    br = LiveBroker(quote="USDC")
    ok = True
    bal = br.balances()
    usd, usdc = bal.get("USD", (0.0, 0.0)), bal.get("USDC", (0.0, 0.0))
    print(f"portfolio: USD {usd[0]:,.2f} available / {usd[1]:,.2f} on hold; USDC {usdc[0]:,.2f} / {usdc[1]:,.2f}")
    if sum(usd) > 1.0:
        print("  !! the portfolio still holds USD: convert it to USDC first, so the check shows what USDC alone can do")
        ok = False
    pr = br._d(br.c.get_product("SOL-USDC"))
    print("SOL-USDC:", {k: pr.get(k) for k in ("product_id", "alias", "alias_to", "status", "trading_disabled",
                                                "post_only", "limit_only") if k in pr})
    px = float(pr.get("price") or 0)
    tick, lot = float(pr["quote_increment"]), float(pr["base_increment"])
    lim = floor_to(px * 0.5, tick)
    size = max(floor_to(10.0 / lim, lot), float(pr.get("base_min_size") or lot))
    sp = Spec("SOL-USD", tick, lot)
    # 1. a post-only bid on SOL-USDC with only USDC must preview cleanly
    pv = br._d(br.c.preview_limit_order_gtc_buy(product_id="SOL-USDC", base_size=fmt(size, lot),
                                                limit_price=fmt(lim, tick), post_only=True))
    print("1. preview of a post-only SOL-USDC bid:", "OK" if not pv.get("errs") else pv.get("errs"))
    ok = ok and not pv.get("errs")
    # 2. place and cancel a $10 bid far below the market: the hold must show on USDC
    oid, err = br.place(sp, "BUY", lim, size)
    if oid is None:
        print("2. the -USDC bid was REJECTED:", err)
        ok = False
    else:
        time.sleep(2)
        hold = br.balances().get("USDC", (0.0, 0.0))[1] - usdc[1]
        print(f"2. placed {oid}: USDC on hold rose by ${hold:,.2f} (expect about ${size * lim:,.2f})")
        ok = ok and hold >= 0.9 * size * lim
        br.c.cancel_orders(order_ids=[oid])
        time.sleep(1)
        st = br.status(oid)["status"]
        print(f"   cancelled: status {st}")
        ok = ok and st in br.TERMINAL
    # 3. the rewards check needs one rewards period of history
    print("3. after one rewards period, compare the USDC rewards Coinbase paid with the expected amount: the average of "
          "the heartbeat 'usdc' field (available + on hold) x the advertised APY x days / 365 (python bot/spot/run.py "
          "report). Stop C4 if rewards are below half the expected amount, if any -USDC order is rejected, or if the "
          "rules change to end exchange rewards.")
    print("\nusdc-check", "PASSED (steps 1-2)" if ok else "FAILED")

elif a.cmd == "reset-halt":
    st_path = os.path.join(sd, "state.json")
    st = json.load(open(st_path))
    st["dd_halt"] = False
    st["peak"] = st["equity"]
    json.dump(st, open(st_path, "w"), indent=1)
    print(f"drawdown stop cleared in {sd}; peak reset to ${st['equity']:,.2f}")
