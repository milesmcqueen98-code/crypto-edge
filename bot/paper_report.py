#!/usr/bin/env python3
"""Summarise the forward paper test from paper/events.jsonl: trades, net bp, P&L, coverage."""
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
print(ex.groupby("coin").agg(trades=("net_bp", "size"), net_bp=("net_bp", "mean"), pnl=("pnl", "sum")).round(2).to_string())
print(ex.groupby("kind").net_bp.agg(["size", "mean"]).round(1).to_string())
out = os.path.join(ROOT, "paper", "trades.csv")
ex[["ts", "coin", "kind", "entry_px", "px", "contracts", "net_bp", "pnl", "equity"]].to_csv(out, index=False)
print("wrote", out)
