#!/usr/bin/env python3
"""Summarise a forward paper test from its events.jsonl: trades, net bp (paper fees and the lab's realistic
costs: $0.20 per contract per side, 1.5x the measured half-spread on market exits, 1 bp funding), P&L, coverage.
Usage: python bot/paper_report.py [paper/events.jsonl | paper_v2/events.jsonl]"""
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "paper", "events.jsonl")
if not os.path.exists(path):
    sys.exit("no paper log yet")
ev = pd.read_json(path, lines=True)
ex = ev[ev.kind == "fill_exit"].copy()
print(f"log {ev.ts.min()} -> {ev.ts.max()}; {len(ev)} events; {(ev.kind == 'bid').sum()} bids placed; "
      f"{(ev.kind == 'error').sum()} errors")
if ex.empty:
    print("no completed trades yet")
    sys.exit(0)
ex["ts"] = pd.to_datetime(ex.ts)
print(f"{len(ex)} completed trades; mean net {ex.net_bp.mean():.1f} bp; hit {(ex.net_bp > 0).mean():.0%}; "
      f"P&L ${ex.pnl.sum():,.2f}; equity ${ex.equity.iloc[-1]:,.2f}")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from bot.engine import load_specs  # noqa: E402
import wick_futures as wf  # noqa: E402
specs, hs = load_specs(), wf.half_spread_bp()
size = ex.coin.map(lambda c: specs[c].size)
gross = (ex.px / ex.entry_px - 1) * 1e4
fee_bp = 2 * 0.20 / (size * ex.entry_px) * 1e4
spread_bp = ex.exit.map(lambda k: 0.0 if k == "tp" else 1.0) * ex.coin.map(lambda c: 1.5 * hs.get(c, 3.0))
ex["net_real_bp"] = gross - fee_bp - spread_bp - 1.0
print(f"realistic costs: mean net {ex.net_real_bp.mean():.1f} bp per trade "
      f"(t = {ex.net_real_bp.mean() / ex.net_real_bp.std() * len(ex) ** 0.5:.2f} over {len(ex)} trades)")
print(ex.groupby("coin").agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"), net_real_bp=("net_real_bp", "mean"),
                             pnl=("pnl", "sum")).round(2).to_string())
print(ex.groupby("exit")[["net_bp", "net_real_bp"]].agg(["size", "mean"]).round(1).to_string())
out = os.path.join(os.path.dirname(os.path.abspath(path)), "trades.csv")
ex[["ts", "coin", "exit", "entry_px", "px", "contracts", "net_bp", "net_real_bp", "pnl", "equity"]].to_csv(out, index=False)
print("wrote", out)
