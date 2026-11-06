#!/usr/bin/env python3
"""Run the bot (R2-08 from bot/v2 by default; add --model-dir bot for v1).
Paper (default, no keys):  python bot/run.py --minutes 345
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
p.add_argument("--state-dir", default=None,
               help="where state.json and events.jsonl live (default: paper_v2/ or live_v2/ for bot/v2, paper/ or live/ for bot/)")
p.add_argument("--model-dir", default=os.path.join(ROOT, "bot", "v2"),
               help="model_meta.json and model files (default: bot/v2, R2-08, the strategy of record; v1 is bot/)")
a = p.parse_args()
cfg = json.load(open(a.config))
if a.mode == "live" and os.environ.get("I_UNDERSTAND_LIVE_TRADING") != "yes":
    sys.exit("Live mode places real orders. Set I_UNDERSTAND_LIVE_TRADING=yes after reading bot/README.md.")
# default state folder follows the model folder, so books never share a log: bot/ -> paper/ (or live/), bot/v2 -> paper_v2/
rel = os.path.relpath(os.path.abspath(a.model_dir), os.path.join(ROOT, "bot"))
d = a.state_dir or os.path.join(ROOT, a.mode + ("" if rel == "." else "_" + rel.replace(os.sep, "_")))
Engine(mode=a.mode, cfg=cfg, state_path=os.path.join(d, "state.json"), log_path=os.path.join(d, "events.jsonl"),
       model_dir=a.model_dir).run(a.minutes)
