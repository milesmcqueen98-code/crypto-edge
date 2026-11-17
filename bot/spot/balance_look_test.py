#!/usr/bin/env python3
"""Test of the balance look (bot/spot/engine.py, Engine._balance_look): a difference between a coin's balance at the
venue and the bot's open rungs is warned only when it is still there at a second look with fills booked (_settle run
to its end) in between; a shortfall covered by market sells of unknown outcome is held up to BAL_HOLD_MIN minutes.

Offline: a live engine over a small fake broker (balances set by hand, requests counted) and a stub market. The step's
data and decision parts (update_spot, data checks, panel, _manage, _allocate, ...) are replaced by no-ops on the
instance; _settle, _refresh_tps, reconcile, catch_up, start and step run as they are. A fill is "booked" by a hook that
runs at the start of _settle (it adds or removes a tranche), so _settle still reaches its own end.
The failed place_many case uses an _allocate stand-in that calls reconcile, as the order path's failure branch does.
The watchdog case runs bot/spot/deploy/watchdog.py itself (subprocess, NTFY_TOPIC removed) on a small events file.

The step's feature panel (edge.wick.panel) is replaced by a no-op while the test runs, and restored after.

Usage: python bot/spot/balance_look_test.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot.spot import engine as E  # noqa: E402

MSG = "coin balance differs from the bot's open rungs: check before trading"
T0 = pd.Timestamp("2025-10-10 20:10")       # not a 15-minute minute (those are 7, 22, 37, 52)
FAILS = []
NPASS = [0]


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok or not extra else f"  {extra}"))
    if ok:
        NPASS[0] += 1
    else:
        FAILS.append(name)


class Broker:
    live = True
    TERMINAL = E.LiveBroker.TERMINAL

    def __init__(self):
        self.bal, self.n_bal, self.fail_bal = {}, 0, 0

    def balances(self):
        self.n_bal += 1
        if self.fail_bal:
            self.fail_bal -= 1
            raise RuntimeError("HTTP 503 balances")
        return {"USD": (1000.0, 0.0), **{c: (q, 0.0) for c, q in self.bal.items()}}

    def cash(self):
        return 1000.0

    def open_orders(self):
        return []

    def cancel_ids(self, ids):
        pass

    def fee_tier(self):
        return dict(tier="fake", maker_bp=6.0, taker_bp=12.5, volume_30d=None)


class PaperBroker(E.PaperBroker):
    n_bal = 0

    def balances(self):
        PaperBroker.n_bal += 1
        return {}


class Market:
    def spec(self, c):
        return E.Spec(f"{c}-USD", 0.01, 1e-8, 1.0)


class Bot:
    """A live (or paper) engine with the step's data and decision parts stubbed out."""

    def __init__(self, mode="live", last=None, cfg=None, sd=None):
        self.sd = sd or tempfile.mkdtemp(prefix="balance_look_")
        self.t = T0
        self.b = Broker() if mode == "live" else PaperBroker(0.5)
        self.e = E.Engine(mode=mode, cfg=dict(capital=1000.0, usd_reserve=0.0, **(cfg or {})), state_dir=self.sd,
                          market=Market(), echo=False, broker=self.b, clock=lambda: self.t + pd.Timedelta(seconds=6))
        e = self.e
        e.coins = e.tradable = ["ETH", "SOL"]
        e.specs = {c: Market().spec(c) for c in e.coins}
        self.px = {"ETH": 1.0, "SOL": 1.0}
        self.stale, self.data_fail, self.on_settle, self.on_allocate = False, False, [], None
        e.last_close = lambda c, t: self.px[c]
        e.update_spot = self._update_spot
        e.refresh_adv = lambda t: None
        e._checks = lambda prev: (self.stale, 0)
        e._new_day = lambda t: None
        e.arrays = lambda t: (None, None, None)
        e._manage = lambda t: None
        e._risk = lambda t: None
        e._allocate = lambda pn, t: self.on_allocate(t) if self.on_allocate else None
        e._heartbeat = lambda t: None
        orig = e._settle

        def settle(m, t):
            while self.on_settle:
                self.on_settle.pop(0)()
            orig(m, t)
        e._settle = settle
        if last is not None:
            e.state["last_minute"] = pd.Timestamp(last).isoformat()

    def _update_spot(self, t, coins=None):
        if self.data_fail:
            raise RuntimeError("market data failed")

    def tranche(self, c, size, lid=None, sell_order=None):
        lid = lid or f"{c}-{len(self.e.state['ladders']) + 1}"
        lad = self.e.state["ladders"].setdefault(lid, dict(id=lid, coin=c, status="open", tranches={}, orders={},
                                                           pending=[]))
        lad["tranches"][str(len(lad["tranches"]) + 4)] = dict(size=size, sell_order=sell_order)
        return lid

    def drop(self, lid):
        self.e.state["ladders"].pop(lid, None)

    def start(self):
        self.e.start()

    def step(self, t=None):
        self.t = pd.Timestamp(t) if t is not None else self.t + pd.Timedelta(minutes=1)
        try:
            self.e.step(self.t)
        except RuntimeError:
            pass                                           # the data failure re-raised by step (as live)

    def ev(self, kind=None):
        p = os.path.join(self.sd, "events.jsonl")
        out = [json.loads(x) for x in open(p)] if os.path.exists(p) else []
        return [x for x in out if kind is None or x["kind"] == kind]

    def looks(self):
        """(ts minute, coin, 'first'/'cleared'/'WARN'/'error') of the balance events, in order."""
        out = []
        for x in self.ev():
            if x["kind"] == "balance_look":
                out.append((x["ts"][11:16], x["coin"], x["look"]))
            elif x["kind"] == "warning" and x.get("msg") == MSG:
                out.append((x["ts"][11:16], x["coin"], "WARN"))
            elif x["kind"] == "error" and "balance look failed" in x.get("error", ""):
                out.append((x["ts"][11:16], None, "error"))
        return out

    def close(self):
        shutil.rmtree(self.sd, ignore_errors=True)


def bot(*a, **k):
    return Bot(*a, **k)


# ------------------------------------------------------------------ the brief's cases
def t_start_explained_by_first_step():
    m = bot(last=T0 - pd.Timedelta(minutes=1))           # gap of one minute: catch_up settles nothing
    try:
        m.b.bal = {"ETH": 100.0}                           # the venue filled a bid the bot has not booked yet
        m.start()
        a = m.looks()
        m.on_settle.append(lambda: m.tranche("ETH", 100.0))
        m.step(T0)
        check("start, gap 1 min: a difference explained by the first step's _settle -> first, then cleared, no warning",
              a == [("20:10", "ETH", "first")] and m.looks() == [("20:10", "ETH", "first"), ("20:10", "ETH", "cleared")]
              and m.e.counts.get("bal_first") == 1 and m.e.counts.get("bal_cleared") == 1, str(m.looks()))
    finally:
        m.close()


def t_start_gap_cleared_after_catch_up():
    m = bot(last=T0 - pd.Timedelta(minutes=20))
    try:
        m.b.bal = {"SOL": 50.0}
        m.on_settle.append(lambda: m.tranche("SOL", 50.0))    # catch_up books the gap's fill
        m.start()
        kinds = [x["kind"] for x in m.ev()]
        ci = kinds.index("catch_up")
        cl = [i for i, x in enumerate(m.ev()) if x.get("look") == "cleared"]
        check("start, gap 20 min: catch_up's _settle explains it -> cleared by the look after catch_up, before any step",
              m.looks() == [("20:10", "SOL", "first"), ("20:10", "SOL", "cleared")] and cl and cl[0] > ci
              and m.b.n_bal == 2 and not m.e._bal_sus, str((m.looks(), m.b.n_bal)))
    finally:
        m.close()


def t_start_real_difference():
    m = bot(last=T0 - pd.Timedelta(minutes=20))
    try:
        m.b.bal = {"ETH": 100.0}                           # the venue holds coins the bot does not know
        m.start()
        w = m.ev("warning")
        check("start, real difference, gap 20 min: warned by the look after catch_up, before the first step, with since",
              m.looks() == [("20:10", "ETH", "first"), ("20:10", "ETH", "WARN")] and len(w) == 1
              and w[0]["msg"] == MSG and w[0]["since"] == T0.isoformat() and w[0]["exchange"] == 100.0
              and w[0]["bot"] == 0 and m.e.counts.get("bal_warned") == 1, str(w))
    finally:
        m.close()
    m = bot(last=T0 - pd.Timedelta(minutes=1))
    try:
        m.b.bal = {"ETH": 100.0}
        m.start()
        a = m.looks()
        m.step(T0)
        w = m.ev("warning")
        check("start, real difference, gap 1 min: no warning at start; warned in the first step, same msg, with since",
              a == [("20:10", "ETH", "first")] and m.looks()[1:] == [("20:10", "ETH", "WARN")]
              and len(w) == 1 and w[0]["msg"] == MSG and w[0]["since"] == T0.isoformat(), str(m.looks()))
    finally:
        m.close()
    m = bot(last=T0)                                       # gap 0 (same minute)
    try:
        m.b.bal = {"ETH": 100.0}
        m.start()
        m.step(T0)
        check("start, real difference, gap 0: warned in the first step", m.looks() ==
              [("20:10", "ETH", "first"), ("20:10", "ETH", "WARN")], str(m.looks()))
    finally:
        m.close()


def t_stays():
    m = bot()
    try:
        m.b.bal = {"ETH": 100.0}
        for t in pd.date_range("2025-10-10 20:05", "2025-10-10 20:40", freq="min"):
            m.step(t)
        lk = m.looks()
        mins = [x[0] for x in lk if x[2] == "WARN"]
        check("a real difference that stays: first at each 15-minute look, warned one step later, never twice a minute",
              lk == [("20:07", "ETH", "first"), ("20:08", "ETH", "WARN"), ("20:22", "ETH", "first"),
                     ("20:23", "ETH", "WARN"), ("20:37", "ETH", "first"), ("20:38", "ETH", "WARN")]
              and len(mins) == len(set(mins)), str(lk))
        n0 = m.b.n_bal
        m.step("2025-10-10 20:41")
        check("no suspect: a step that is not the 15-minute minute makes no balance request", m.b.n_bal == n0)
    finally:
        m.close()


def t_gone_next_step():
    m = bot()
    try:
        m.b.bal = {"ETH": 100.0}
        m.step("2025-10-10 20:07")
        m.on_settle.append(lambda: m.tranche("ETH", 100.0))
        m.step("2025-10-10 20:08")
        m.step("2025-10-10 20:09")
        check("a difference first seen in the 15-minute look and gone in the next step: no warning",
              m.looks() == [("20:07", "ETH", "first"), ("20:08", "ETH", "cleared")], str(m.looks()))
    finally:
        m.close()


def t_failed_place_many():
    m = bot()
    try:
        m.b.bal = {"ETH": 100.0}
        m.on_allocate = lambda t: m.e.reconcile(t) if t == pd.Timestamp("2025-10-10 20:10") else None
        m.step("2025-10-10 20:10")
        n = m.b.n_bal
        a = m.looks()
        m.step("2025-10-10 20:11")
        check("first look in the step of a failed place_many: no second look in that step, warned in the next",
              a == [("20:10", "ETH", "first")] and n == 1
              and m.looks() == [("20:10", "ETH", "first"), ("20:11", "ETH", "WARN")], str((m.looks(), n)))
    finally:
        m.close()


def t_skipped_minutes():
    for how in ("stale guard", "orders only (data failure)"):
        m = bot(cfg=dict(stale_guard=True))
        try:
            m.b.bal = {"ETH": 100.0}
            m.step("2025-10-10 20:07")
            if how == "stale guard":
                m.stale = True
            else:
                m.data_fail = True
            m.step("2025-10-10 20:08")
            a, n = m.looks(), m.b.n_bal
            m.stale = m.data_fail = False
            m.step("2025-10-10 20:09")
            check(f"a minute handled by the {how} between the looks: no look in it; the second look in the next step",
                  a == [("20:07", "ETH", "first")] and n == 1
                  and m.looks() == [("20:07", "ETH", "first"), ("20:09", "ETH", "WARN")], str((m.looks(), n)))
        finally:
            m.close()


def t_balances_raises():
    m = bot()
    try:
        m.b.bal = {"ETH": 100.0}
        m.step("2025-10-10 20:07")
        m.b.fail_bal = 1
        m.step("2025-10-10 20:08")
        errs = [x for x in m.ev("error")]
        kept = "ETH" in m.e._bal_sus
        m.step("2025-10-10 20:09")
        check("balances() raising at a second look: one error event, the suspect kept, the look repeated next step",
              len(errs) == 1 and errs[0]["error"].startswith("balance look failed: ") and kept
              and m.looks() == [("20:07", "ETH", "first"), ("20:08", None, "error"), ("20:09", "ETH", "WARN")],
              str(m.looks()))
    finally:
        m.close()
    m = bot()
    try:
        m.b.bal = {"ETH": 100.0}
        m.b.fail_bal = 1
        m.step("2025-10-10 20:07")
        e = m.ev("error")
        check("balances() raising inside reconcile: its own error as before, no suspect",
              len(e) == 1 and e[0]["error"].startswith("reconcile failed: ") and not m.e._bal_sus, str(e))
    finally:
        m.close()


def t_tolerance_and_price():
    m = bot()
    try:
        m.b.bal = {"ETH": 25.0, "SOL": 25.01}              # price 1: 25 dollars is within the tolerance, 25.01 is not
        m.step("2025-10-10 20:07")
        check("tolerance: 25 dollars is no difference, 25.01 is (reconcile_tol_usd 25, as before)",
              m.looks() == [("20:07", "SOL", "first")], str(m.looks()))
    finally:
        m.close()
    m = bot(cfg=dict(reconcile_tol_usd=100.0))
    try:
        m.b.bal = {"ETH": 50.0}
        m.step("2025-10-10 20:07")
        check("tolerance: the config key is used (100 dollars: a 50-dollar difference is none)", m.looks() == [])
    finally:
        m.close()
    m = bot()
    try:
        m.b.bal = {"ETH": 100.0}
        m.px["ETH"] = np.nan
        m.step("2025-10-10 20:07")
        check("non-finite price at a 15-minute look: nothing for the coin (no event, no suspect), as before",
              m.looks() == [] and not m.e._bal_sus, str(m.looks()))
    finally:
        m.close()
    m = bot()
    try:
        m.b.bal = {"ETH": 100.0}
        m.step("2025-10-10 20:07")
        m.px["ETH"] = np.nan
        m.step("2025-10-10 20:08")
        kept, a = "ETH" in m.e._bal_sus, m.looks()
        m.px["ETH"] = 1.0
        m.step("2025-10-10 20:09")
        check("non-finite price at the second look: nothing logged, suspect kept; warned when the price is back",
              kept and a == [("20:07", "ETH", "first")]
              and m.looks() == [("20:07", "ETH", "first"), ("20:09", "ETH", "WARN")], str(m.looks()))
    finally:
        m.close()


def t_paper():
    PaperBroker.n_bal = 0
    m = bot(mode="paper", last=T0 - pd.Timedelta(minutes=20))
    try:
        m.tranche("ETH", 100.0)
        m.start()
        for t in pd.date_range("2025-10-10 20:05", "2025-10-10 20:25", freq="min"):
            m.step(t)
        check("paper mode: no look, no balance event, balances never called",
              PaperBroker.n_bal == 0 and m.looks() == [] and not m.e._bal_sus
              and not any(k.startswith("bal_") for k in m.e.counts), str((PaperBroker.n_bal, m.looks())))
    finally:
        m.close()


def t_watchdog():
    sd = tempfile.mkdtemp(prefix="balance_look_wd_")
    try:
        json.dump(dict(equity=1.0), open(os.path.join(sd, "state.json"), "w"))
        with open(os.path.join(sd, "events.jsonl"), "w") as fh:
            fh.write(json.dumps(dict(ts="2025-10-10T20:07:00", kind="balance_look", coin="ETH", exchange=100.0, bot=0,
                                     look="first")) + "\n")
            fh.write(json.dumps(dict(ts="2025-10-10T20:08:00", kind="balance_look", coin="ETH", exchange=100.0, bot=100,
                                     look="cleared")) + "\n")
            fh.write(json.dumps(dict(ts="2025-10-10T20:09:00", kind="warning", msg=MSG, coin="SOL", exchange=5.0,
                                     bot=0, since="2025-10-10T20:08:00")) + "\n")
        env = {k: v for k, v in os.environ.items() if k != "NTFY_TOPIC"}
        r = subprocess.run([sys.executable, os.path.join(HERE, "deploy", "watchdog.py"), sd], capture_output=True,
                           text=True, env=env, cwd=ROOT)
        lines = [x for x in r.stdout.splitlines() if x.startswith("[wickbot")]
        check("watchdog (its own script on an events file): balance_look raises no alert, the warning does",
              r.returncode == 0 and len(lines) == 1 and lines[0].startswith("[wickbot warning]")
              and "SOL" in lines[0] and "balance_look" not in r.stdout, r.stdout + r.stderr)
    finally:
        shutil.rmtree(sd, ignore_errors=True)


# ------------------------------------------------------------------ the hold for market sells of unknown outcome
def t_hold_resolved():
    m = bot()
    try:
        lid = m.tranche("ETH", 100.0, sell_order="s1")    # sold at the venue, outcome unknown to the bot
        m.b.bal = {"ETH": 0.0}
        m.step("2025-10-10 20:07")
        m.step("2025-10-10 20:08")
        a, held = m.looks(), m.e.counts.get("bal_held")
        m.step("2025-10-10 20:09")
        m.on_settle.append(lambda: m.drop(lid))            # resolved and booked (as _manage's _resolve_sell does)
        m.step("2025-10-10 20:10")
        check("pending market sell, shortfall equal to its tranche: held (no event), cleared once booked, no warning",
              a == [("20:07", "ETH", "first")] and held == 1 and m.e.counts.get("bal_held") == 2
              and m.looks() == [("20:07", "ETH", "first"), ("20:10", "ETH", "cleared")] and not m.ev("warning"),
              str((m.looks(), m.e.counts)))
    finally:
        m.close()


def t_hold_never_resolved():
    m = bot()
    try:
        m.tranche("ETH", 100.0, sell_order="s1")
        m.b.bal = {"ETH": 0.0}
        for t in pd.date_range("2025-10-10 20:07", "2025-10-10 20:16", freq="min"):
            m.step(t)
        a = m.looks()
        m.step("2025-10-10 20:17")
        w = m.ev("warning")
        for t in pd.date_range("2025-10-10 20:18", "2025-10-10 20:22", freq="min"):
            m.step(t)
        check(f"pending sell never resolved: held while the first look is under {E.BAL_HOLD_MIN} min old, warned at "
              "10 min with since = the first look, then the next 15-minute look starts a new first look",
              a == [("20:07", "ETH", "first")] and m.e.counts.get("bal_held") == 9
              and m.looks() == [("20:07", "ETH", "first"), ("20:17", "ETH", "WARN"), ("20:22", "ETH", "first")]
              and len(w) == 1 and w[0]["since"] == "2025-10-10T20:07:00", str((m.looks(), m.e.counts)))
    finally:
        m.close()


def t_hold_surplus():
    m = bot()
    try:
        m.tranche("ETH", 100.0, sell_order="s1")
        m.b.bal = {"ETH": 200.0}                           # the venue holds MORE than the bot's sum
        m.step("2025-10-10 20:07")
        m.step("2025-10-10 20:08")
        check("pending sell but a surplus at the venue: warned at the second look, no hold",
              m.looks() == [("20:07", "ETH", "first"), ("20:08", "ETH", "WARN")] and "bal_held" not in m.e.counts,
              str(m.looks()))
    finally:
        m.close()


def t_hold_too_short():
    m = bot()
    try:
        m.tranche("ETH", 100.0, sell_order="s1")
        m.tranche("ETH", 100.0)                            # a second rung of the coin, no sell pending
        m.b.bal = {"ETH": 50.0}                            # shortfall 150 > pending 100 + 25 dollars
        m.step("2025-10-10 20:07")
        m.step("2025-10-10 20:08")
        check("pending sell but a shortfall larger than the pending size plus the tolerance: warned, no hold",
              m.looks() == [("20:07", "ETH", "first"), ("20:08", "ETH", "WARN")] and "bal_held" not in m.e.counts,
              str(m.looks()))
    finally:
        m.close()


def t_hold_other_coin():
    m = bot()
    try:
        m.tranche("ETH", 100.0, sell_order="s1")
        m.b.bal = {"ETH": 0.0, "SOL": 100.0}
        m.step("2025-10-10 20:07")
        m.step("2025-10-10 20:08")
        check("a hold on one coin does not delay a warning on another coin in the same look",
              m.looks() == [("20:07", "ETH", "first"), ("20:07", "SOL", "first"), ("20:08", "SOL", "WARN")]
              and m.e.counts.get("bal_held") == 1 and "ETH" in m.e._bal_sus, str(m.looks()))
    finally:
        m.close()


def t_hold_boundary():
    for ex, held in ((75.0, True), (74.99, False)):       # bot 200, pending 100, price 1: (short - pend) 25 / 25.01
        m = bot()
        try:
            m.tranche("ETH", 100.0, sell_order="s1")
            m.tranche("ETH", 100.0)
            m.b.bal = {"ETH": ex}
            m.step("2025-10-10 20:07")
            m.step("2025-10-10 20:08")
            want = [("20:07", "ETH", "first")] + ([] if held else [("20:08", "ETH", "WARN")])
            check(f"boundary: (short - pending) x price {200 - ex - 100:.2f} dollars against 25 -> "
                  + ("held" if held else "warned"), m.looks() == want
                  and (m.e.counts.get("bal_held") == 1) == held, str(m.looks()))
        finally:
            m.close()


def main():
    panel, E.wick.panel = E.wick.panel, lambda *a, **k: None    # the step's feature panel: not needed here
    try:
        run_all()
    finally:
        E.wick.panel = panel
    print(f"balance look test: {NPASS[0]} passed, {len(FAILS)} failed")
    if FAILS:
        print("BALANCE LOOK TEST FAILED")
        sys.exit(1)
    print("BALANCE LOOK TEST PASSED")


def run_all():
    for f in (t_start_explained_by_first_step, t_start_gap_cleared_after_catch_up, t_start_real_difference, t_stays,
              t_gone_next_step, t_failed_place_many, t_skipped_minutes, t_balances_raises, t_tolerance_and_price,
              t_paper, t_watchdog, t_hold_resolved, t_hold_never_resolved, t_hold_surplus, t_hold_too_short,
              t_hold_other_coin, t_hold_boundary):
        try:
            f()
        except Exception as err:
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} ran without an exception", False, repr(err))


if __name__ == "__main__":
    main()
