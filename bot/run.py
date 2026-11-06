#!/usr/bin/env python3
"""Run the bot.  Paper (default, no keys):  python bot/run.py --minutes 345
Live (Coinbase Advanced futures account; read bot/README.md first):
    COINBASE_API_KEY=... COINBASE_API_SECRET=... I_UNDERSTAND_LIVE_TRADING=yes python bot/run.py --mode live"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bot.engine import Engine  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--mode", default="paper", choices=["paper", "live"])
p.add_argument("--minutes", type=float, default=345)
p.add_argument("--config", default=os.path.join(ROOT, "bot", "config.json"))
a = p.parse_args()
cfg = json.load(open(a.config))
if a.mode == "live" and os.environ.get("I_UNDERSTAND_LIVE_TRADING") != "yes":
    sys.exit("Live mode places real orders. Set I_UNDERSTAND_LIVE_TRADING=yes after reading bot/README.md.")
d = os.path.join(ROOT, a.mode)
Engine(mode=a.mode, cfg=cfg, state_path=os.path.join(d, "state.json"), log_path=os.path.join(d, "events.jsonl")).run(a.minutes)
