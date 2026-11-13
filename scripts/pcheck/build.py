#!/usr/bin/env python3
"""Datasets for the dashboard's paper-trading section (perp books, Nov 13 2026 check-in):
paper_books.csv (one row per book), paper_fills.csv (one row per completed trade), paper_cum.csv (cumulative fills
against the research rate, at each UTC midnight and each fill). Inputs: copies of paper/ and paper_v2/ events.jsonl, the trades.csv that
bot/paper_report.py wrote next to them, and spotcheck_<book>.csv from spotcheck.py."""
import math
import os

import numpy as np
import pandas as pd

HERE = os.environ.get("PCHECK_DIR") or os.path.dirname(os.path.abspath(__file__))
HANDOVER = pd.Timestamp("2026-11-11 19:39")          # first paper run that started the next one
BOOKS = {  # research on perp prices (spot-confirmed fills), realistic costs: lab round 2, Jul 2025 - Nov 2026
    "v2": dict(book="R2-08 (strategy of record)", research_fills_day=0.80, research_net_bp=20.8, gate_bp=-12.0,
               gate_basis="realistic costs"),
    "v1": dict(book="v1 (control)", research_fills_day=1.05, research_net_bp=9.6, gate_bp=-18.0,
               gate_basis="paper fees"),
}
GATE_TRADES, SWITCH_TRADES = 70, 60


def poisson_cdf(k, lam):
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(int(k) + 1))


def episodes(d):
    """Coin-minutes grouped into episodes: same coin, at most 10 minutes apart."""
    n = 0
    for _, g in d.sort_values("minute").groupby("coin"):
        n += int((g.minute.diff() > pd.Timedelta(minutes=10)).sum()) + 1
    return n


def live_minutes(ev):
    """Set of minutes the book was running: each run from its first event to its last step."""
    ev = ev.sort_values("ts")
    starts = list(ev[ev.kind == "backfill"].ts.dt.floor("min"))
    ends = [r.ts.floor("min") - pd.Timedelta(minutes=int(r.gap_minutes)) for _, r in ev[ev.kind == "catch_up"].iterrows()]
    ends.append(ev.ts.max().floor("min"))
    spans = list(zip(starts, ends))
    return spans


def main():
    books, fills, daily, per_book = [], [], [], {}
    for b, meta in BOOKS.items():
        ev = pd.read_json(os.path.join(HERE, b, "events.jsonl"), lines=True)
        ev["ts"] = pd.to_datetime(ev.ts)
        tr = pd.read_csv(os.path.join(HERE, b, "trades.csv"), parse_dates=["ts"])
        sc = pd.read_csv(os.path.join(HERE, f"spotcheck_{b}.csv"), parse_dates=["minute"])
        first, last = ev.ts.min(), ev.ts.max()
        cal_h = (last - first).total_seconds() / 3600
        gaps = ev[ev.kind == "catch_up"]
        live_h = cal_h - gaps.gap_minutes.sum() / 60
        ho_h = (last - HANDOVER).total_seconds() / 3600
        ho_live = 1 - gaps[gaps.ts >= HANDOVER].gap_minutes.sum() / 60 / ho_h
        fe = ev[ev.kind == "fill_entry"].copy()
        fe["minute"] = fe.ts.dt.floor("min") - pd.Timedelta(minutes=1)
        n = len(tr)
        lam = meta["research_fills_day"] * live_h / 24
        bf = sc[sc.bot_fill]
        spot_ok = int(bf.s_fill.sum())
        books.append(dict(id=b, book=meta["book"], first_event=first.strftime("%Y-%m-%d %H:%M"),
                          last_event=last.strftime("%Y-%m-%d %H:%M"), calendar_h=round(cal_h, 1), live_h=round(live_h, 1),
                          live_share=round(live_h / cal_h, 4), live_share_handover=round(ho_live, 4),
                          bids=int((ev.kind == "bid").sum()), errors=int((ev.kind == "error").sum()), trades=n,
                          fills_per_live_day=round(n / (live_h / 24), 2), research_fills_day=meta["research_fills_day"],
                          expected_fills=round(lam, 1), p_this_few=round(poisson_cdf(n, lam), 2),
                          net_paper_bp=round(tr.net_bp.mean(), 1), net_real_bp=round(tr.net_real_bp.mean(), 1),
                          research_net_bp=meta["research_net_bp"], hit=round((tr.net_bp > 0).mean(), 2),
                          pnl_usd=round(tr.pnl.sum(), 2), equity=round(tr.equity.iloc[-1], 2),
                          gate_bp=meta["gate_bp"], gate_basis=meta["gate_basis"], gate_trades=GATE_TRADES,
                          trades_to_gate=max(0, GATE_TRADES - n), switch_trades=SWITCH_TRADES,
                          spot_confirmed=spot_ok, perp_only=int(len(bf) - spot_ok),
                          spot_fills_without_perp=int((sc.s_fill & ~sc.p_fill).sum()),
                          missed_episodes=episodes(sc[sc.s_fill & ~sc.p_fill]),
                          spot_followed_10m=0,
                          paper_rule_final_candles=int(sc.p_fill.sum())))
        ex = ev[ev.kind == "fill_exit"].copy()
        for (_, f), (_, x) in zip(fe.iterrows(), ex.iterrows()):
            s = sc[(sc.coin == f.coin) & (sc.minute == f.minute)].iloc[0]
            t = tr[(tr.coin == f.coin) & (tr.ts == x.ts)].iloc[0]
            S = pd.read_parquet(os.path.join(HERE, "pcheck", f"{f.coin}.parquet"))
            S["ts"] = pd.to_datetime(S.ts)
            lo = S.set_index("ts").low.astype(float).reindex(pd.date_range(f.minute, f.minute + pd.Timedelta(minutes=10), freq="min"))
            below = lo.index[lo < s.spot_level]
            lag = int((below[0] - f.minute) / pd.Timedelta(minutes=1)) if len(below) else None
            when = "same minute" if lag == 0 else (f"{lag} min later" if lag is not None else "not within 10 min")
            held = int((x.ts.floor("min") - pd.Timedelta(minutes=1) - f.minute) / pd.Timedelta(minutes=1))
            exit_desc = ("Take-profit" if x.exit == "tp" else "Time exit") + f", {held} min"
            fills.append(dict(key=f"{meta['book'].split(' ')[0]} {f.coin} {f.minute:%b %-d %H:%M}", book=meta["book"],
                              coin=f.coin, filled_utc=f.minute.strftime("%Y-%m-%d %H:%M"), exit=x.exit, held_min=held,
                              exit_desc=exit_desc,
                              net_paper_bp=round(x.net_bp, 1), net_real_bp=round(t.net_real_bp, 1), pnl_usd=round(x.pnl, 2),
                              spot_same_minute="yes" if s.s_fill else "no",
                              spot_low_vs_level_bp=round(-s.spot_bp_below, 1), spot_below_level=when,
                              perp_ticks_through=int(round(s.perp_ticks_through)),
                              perp_contracts_traded=int(f.minute_contracts_traded), our_contracts=int(f.contracts),
                              volume_multiple=round(f.minute_contracts_traded / f.contracts, 1),
                              usd_bids_ahead=int(round(s.usd_ahead))))
        books[-1]["spot_followed_10m"] = int(sum(1 for r in fills if r["book"] == meta["book"] and r["spot_below_level"] != "not within 10 min"))
        # inputs for the cumulative chart, drawn at the union of both books' times below
        per_book[meta["book"]] = dict(spans=live_minutes(ev), fills=list(fe.minute), rate=meta["research_fills_day"],
                                      first=first, last=last)
        pace = n / (live_h / 24)
        books[-1]["days_to_gate"] = round(books[-1]["trades_to_gate"] / pace) if pace > 0 else None
        books[-1]["gate_eta"] = (last + pd.Timedelta(days=books[-1]["days_to_gate"])).strftime("%Y-%m-%d") if pace > 0 else ""
    first = min(v["first"] for v in per_book.values())
    last = max(v["last"] for v in per_book.values()).floor("min")
    times = set(pd.date_range(first.normalize() + pd.Timedelta(days=1), last.normalize(), freq="D")) | {last, first.floor("min")}
    for v in per_book.values():
        times |= set(v["fills"]) | {v["first"].floor("min")}
    for t in sorted(times):
        for name, v in per_book.items():
            if t < v["first"].floor("min"):
                continue
            lh = sum(max(0.0, (min(e, t) - s).total_seconds() / 3600) for s, e in v["spans"])
            daily.append(dict(at=t.strftime("%Y-%m-%d %H:%M"), book=name, live_h=round(lh, 1),
                              cum_fills=int(sum(1 for m in v["fills"] if m <= t)),
                              cum_expected=round(v["rate"] * lh / 24, 2)))
    B, Fl, D = pd.DataFrame(books), pd.DataFrame(fills), pd.DataFrame(daily)
    for name, df in (("paper_books", B), ("paper_fills", Fl), ("paper_cum", D)):
        df.to_csv(os.path.join(HERE, f"{name}.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(B.T.to_string())
    print(Fl.to_string(index=False))
    print(D.to_string(index=False))


if __name__ == "__main__":
    main()
