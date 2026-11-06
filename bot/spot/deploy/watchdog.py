#!/usr/bin/env python3
"""Watchdog for the live spot bot, run every 5 minutes by wickbot-watchdog.timer.

Pushes a phone alert (ntfy.sh topic in NTFY_TOPIC) when: the bot has not completed a minute in 5 minutes; a new
halt, error, warning or rejected order appears in the log; or (once a day, after 00:05 UTC) with yesterday's P&L.
Without NTFY_TOPIC it prints the alerts (journalctl -u wickbot-watchdog)."""
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SD = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else "live_spot")
MARK = os.path.join(SD, "watchdog.json")


def push(title, msg, prio="default"):
    topic = os.environ.get("NTFY_TOPIC")
    print(f"[{title}] {msg}", flush=True)
    if not topic:
        return
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=msg.encode(), method="POST",
                                 headers={"Title": title, "Priority": prio})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as err:
        print("push failed:", err)


def main():
    mark = json.load(open(MARK)) if os.path.exists(MARK) else {"offset": 0, "day": None, "stale": False}
    st_path, ev_path = os.path.join(SD, "state.json"), os.path.join(SD, "events.jsonl")
    if not os.path.exists(st_path):
        push("wickbot", "no state file yet", "high")
        return
    age = time.time() - os.path.getmtime(st_path)
    if age > 300 and not mark.get("stale"):
        push("wickbot DOWN", f"no minute completed for {age / 60:.0f} min: check `systemctl status wickbot`", "urgent")
        mark["stale"] = True
    elif age <= 300 and mark.get("stale"):
        push("wickbot back", "minute loop running again")
        mark["stale"] = False
    if os.path.exists(ev_path):
        with open(ev_path) as fh:
            fh.seek(min(mark.get("offset", 0), os.path.getsize(ev_path)))
            new = fh.read()
            mark["offset"] = fh.tell()
        for line in new.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("kind") in ("halt", "error", "warning", "reject"):
                prio = "urgent" if e["kind"] == "halt" else "high" if e["kind"] in ("error", "warning") else "default"
                push(f"wickbot {e['kind']}", json.dumps({k: v for k, v in e.items() if k != "kind"})[:400], prio)
    st = json.load(open(st_path))
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if mark.get("day") != today and time.gmtime().tm_hour == 0 and time.gmtime().tm_min >= 5:
        eq, start = st.get("equity", 0.0), st.get("day_start_equity", 0.0)
        push("wickbot daily", f"equity ${eq:,.0f}; open ladders {len(st.get('ladders', {}))}; "
                              f"drawdown stop {'ON' if st.get('dd_halt') else 'off'}")
        mark["day"] = today
    json.dump(mark, open(MARK, "w"))


if __name__ == "__main__":
    main()
