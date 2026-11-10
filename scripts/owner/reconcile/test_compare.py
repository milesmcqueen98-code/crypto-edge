"""Offline test of compare.py's matching logic on a made-up log and research table. Run: python test_compare.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

import common               # noqa: E402
import compare              # noqa: E402

T0 = pd.Timestamp("2026-01-01 10:00")
END = pd.Timestamp("2026-01-01 11:00")


def m(k):
    return T0 + pd.Timedelta(minutes=k)


def ev(k, kind, **kw):
    t = m(k)
    return dict(ts=t.isoformat(), t=t, kind=kind, **kw)


def make():
    E = [
        ev(0, "backfill", minutes=15840, coins=3),
        ev(5, "arm", coin="A", ladder="A-1", px=9.99, usd=100, pred=40.0, sigma_bp=50.0),     # first step at +5
        ev(7, "fill_entry", coin="A", ladder="A-1", rung=4, px=9.99, size=1.0),
        ev(10, "arm", coin="B", ladder="B-2", px=19.50, usd=100, pred=31.0, sigma_bp=50.0),
        ev(20, "fill_exit", coin="A", ladder="A-1", rung=4, exit="tp", pnl=1.5),
        ev(21, "ladder_close", coin="A", ladder="A-1", pnl=2.0),
        ev(40, "catch_up", gap_minutes=5, open=[]),                                          # gap (10:35, 10:40]
        ev(50, "cash_short", coin="A", pred=35.0, want=100, free=1),
        ev(60, "heartbeat"),
    ]
    rows = []
    thr = 30.0
    for k in range(0, 61):
        t = m(k)
        # A: above threshold at 0-12 (bot busy 8-20), 30-33, 41-45, 50-52
        sa = 40.0 if (k <= 12 or 30 <= k <= 33 or 41 <= k <= 45 or 50 <= k <= 52) else 10.0
        # B: above threshold from 9 to 20; its research level is 19.60 (the bot priced 19.50)
        sb = 35.0 if 9 <= k <= 20 else 10.0
        rows.append(dict(ts=t, coin="A", level=9.995, sig=0.005, score=sa, valid=True, beta=1.0, btc_r1_bp=-20.0,
                         btc_r2_bp=-30.0, open=10.0, high=10.0, low=9.98 if k == 7 else 10.0))
        rows.append(dict(ts=t, coin="B", level=19.60, sig=0.005, score=sb, valid=True, beta=1.0, btc_r1_bp=50.0,
                         btc_r2_bp=60.0, open=20.0, high=20.0, low=19.55 if k == 15 else 20.0))
    R = pd.DataFrame(rows)
    late = pd.DataFrame([dict(ts=m(10), coin="B", btc_lag=1, level=19.505, score=31.2, valid=True),
                         dict(ts=m(10), coin="B", btc_lag=2, level=19.40, score=30.5, valid=True),
                         dict(ts=m(5), coin="A", btc_lag=1, level=9.97, score=39.0, valid=True),
                         dict(ts=m(5), coin="A", btc_lag=2, level=9.96, score=38.0, valid=True)])
    return E, R, late, {"A": 0.01, "B": 0.01}, thr


def main():
    E, R, late, ticks, thr = make()
    # live minutes: brief = 61 minutes less the 5-minute gap; decisions also less the start-up minutes 0..4
    brief = common.live_minutes_brief(E, END)
    assert len(brief) == 61 - 5, len(brief)
    dec, reset = common.live_minutes(E, END)
    assert len(dec) == 61 - 5 - 5, len(dec)
    assert dec[0] == m(5) and m(36) not in dec and m(40) not in dec and m(41) in dec
    assert reset[m(41)] and not reset[m(6)]
    # busy: fill at 7, take-profit at 20 -> busy for decision minutes 8..20
    iv = common.busy_intervals(E)
    assert not common.is_busy(iv, "A", m(7)) and common.is_busy(iv, "A", m(8)) and common.is_busy(iv, "A", m(20))
    assert not common.is_busy(iv, "A", m(21))

    o = compare.compute(E, R, late, ticks, thr, end=END)
    A = o["arms"].set_index("coin")
    # measure 1: A within a tick (9.995 floors to 9.99) -> 0; B: 19.50 vs 19.60 -> about -51 bp
    assert A.at["A", "err_bp"] == 0.0
    assert abs(A.at["B", "err_bp"] - 1e4 * (19.50 / 19.60 - 1)) < 1e-9
    assert A.at["B", "closest"] == "btc_1min_late", A.at["B", "closest"]   # 19.505 floors to 19.50
    assert A.at["A", "closest"] == "final"
    # measure 2: B's research score is 35 (bot 31) -> diff -4; nobody on the other side
    assert abs(A.at["B", "score_diff"] + 4.0) < 1e-12 and o["m2"]["n_other_side"] == 0
    # measure 3: research new bids: A at 5 (start, first decision), B at 9, A at 30, A at 41 (after the gap),
    # A at 50 (cash short at 50). A at 21? A is below the threshold from 13, so no.
    rn = o["research_new"]
    got = sorted((int((t - T0) / pd.Timedelta(minutes=1)), c) for t, c in zip(rn.ts, rn.coin))
    assert got == [(5, "A"), (9, "B"), (30, "A"), (41, "A"), (50, "A")], got
    m3 = o["m3"]
    assert m3["bot_new_bids"] == 2 and m3["bot_matched"] == 2                # B at 10 matches research B at 9 (+-1)
    assert m3["research_cash_blocked"] == 1 and m3["research_new_bids_ex_cash"] == 4
    assert m3["research_matched"] == 2 and abs(m3["share_research_in_bot"] - 0.5) < 1e-12
    # measure 4: A filled at 7 in both; B's dip at 15 (low 19.55 <= 19.60) is research only; bot P&L of 'both' = 1.5
    F = o["fills"]
    g = F.groupby("group").size().to_dict()
    assert g == {"both": 1, "research_only": 1}, g
    s = o["m4"].set_index("group")
    assert s.at["both", "bot_rung4_pnl"] == 1.5 and s.at["both", "bot_ladder_pnl"] == 2.0
    assert F[F.group == "research_only"].coin.tolist() == ["B"]
    # a bot fill the research would not have: make A's low at 7 stay above the research price
    R2 = R.copy()
    R2.loc[(R2.coin == "A") & (R2.ts == m(7)), "low"] = 10.0
    o2 = compare.compute(E, R2, late, ticks, thr, end=END)
    assert o2["fills"].groupby("group").size().to_dict() == {"bot_only": 1, "research_only": 1}
    # research dedupe: a second dip on B one minute later counts once (B busy for the research until tp or 60 min)
    R3 = R.copy()
    R3.loc[(R3.coin == "B") & (R3.ts == m(16)), "low"] = 19.50
    o3 = compare.compute(E, R3, late, ticks, thr, end=END)
    assert o3["research_fill_episodes"] == 2, o3["research_fill_episodes"]
    # the final minute (60) was never settled by the bot: a dip there is not a research fill
    R4 = R.copy()
    R4.loc[(R4.coin == "A") & (R4.ts == m(22)), "high"] = 10.2         # research take-profit of A's fill at 7
    R4.loc[(R4.coin == "A") & (R4.ts == m(52)), "low"] = 9.0          # A armed at 50-52, settled (53 is live)
    R4.loc[(R4.coin == "B") & (R4.ts == m(60)), "low"] = 1.0
    R4.loc[(R4.coin == "B") & (R4.ts == m(60)), "score"] = 99.0
    o4 = compare.compute(E, R4, late, ticks, thr, end=END)
    ro = o4["fills"][o4["fills"].group == "research_only"]
    assert sorted(zip(ro.coin, ro.ts)) == [("A", m(52)), ("B", m(15))], list(zip(ro.coin, ro.ts))
    # one dip, two sides a few minutes apart: research fills B at 15, the bot fills B at 16 (the research take-profit minute) -> no research-only fill
    E5 = E + [ev(16, "fill_entry", coin="B", ladder="B-2", rung=4, px=19.50, size=1.0)]
    E5.sort(key=lambda x: x["t"])
    o5 = compare.compute(E5, R, late, ticks, thr, end=END)
    g5 = o5["fills"].groupby("group").size().to_dict()
    assert g5 == {"both": 1, "bot_only": 1}, g5                 # B at 16: low 20 > 19.60 -> bot only by the plan rule
    assert o5["research_fill_matched"] == 2
    assert np.isfinite(o["m1"]["median"])
    print("test_compare: all checks passed")


if __name__ == "__main__":
    main()
