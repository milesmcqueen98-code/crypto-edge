#!/usr/bin/env python3
"""Set up the live bot's secrets and settings, interactively. On the server: sudo wickctl configure

Writes /etc/wickbot.env (API key, alerts, live switch; readable by root and the wick user only) and the capital in
bot/spot/config.live.json. Run it again any time to change one answer; Enter keeps the current value."""
import grp
import json
import os
import pwd
import re
import sys

ENV = "/etc/wickbot.env"
ROOT = "/home/wick/crypto-edge"
CFG = os.path.join(ROOT, "bot", "spot", "config.live.json")


def read_env():
    out = {}
    if os.path.exists(ENV):
        for line in open(ENV):
            m = re.match(r'\s*([A-Z_]+)=(.*)$', line.strip())
            if m:
                out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def ask(prompt, default="", ok=lambda v: True, secret_default=False):
    shown = (" [keep current]" if secret_default else f" [{default}]") if default else ""
    while True:
        v = input(f"  {prompt}{shown}: ").strip() or default
        if ok(v):
            return v
        print("  that doesn't look right, try again")


def main():
    if os.geteuid() != 0:
        sys.exit("Run it with sudo:  sudo wickctl configure")
    env = read_env()
    cfg = json.load(open(CFG)) if os.path.exists(CFG) else json.load(open(os.path.join(ROOT, "bot", "spot", "config.json")))

    print("\n1/5  API key name, from the CDP portal (looks like organizations/.../apiKeys/...)")
    key = ask("key name", env.get("COINBASE_API_KEY", ""), lambda v: v.startswith("organizations/") and "/apiKeys/" in v)

    print("\n2/5  Private key: paste it, including the -----BEGIN and -----END lines, then press Enter.")
    if env.get("COINBASE_API_SECRET"):
        print("     (or just press Enter to keep the current one)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            if lines or env.get("COINBASE_API_SECRET"):
                break
            continue
        lines.append(line.strip())
        if "END" in line and "PRIVATE KEY" in line:
            break
    if lines:
        pem = "\n".join(lines).replace("\\n", "\n").strip().strip('"')
        if "BEGIN EC PRIVATE KEY" not in pem:
            sys.exit("That isn't an ECDSA private key (-----BEGIN EC PRIVATE KEY-----). Create the key again with the "
                     "signature algorithm set to ECDSA; the Coinbase SDK can't use Ed25519 keys.")
        secret = "\\n".join(l.strip() for l in pem.splitlines() if l.strip()) + "\\n"
    else:
        secret = env["COINBASE_API_SECRET"]

    print("\n     Got the key.")
    print("\n3/5  Capital the bot may use, in USD: the cash you moved into the wickbot portfolio (e.g. 10000)")
    cur = float(cfg.get("capital") or 0)
    cap = ask("capital", str(int(cur)) if cur > 0 else "",
              lambda v: re.fullmatch(r"[\d,]+(\.\d+)?", v) is not None and float(v.replace(",", "")) >= 1000)
    cfg["capital"] = float(cap.replace(",", ""))

    print("\n4/5  Alerts (optional, Enter to skip)")
    hc = ask("healthchecks.io ping URL (https://hc-ping.com/...)", env.get("HEALTHCHECK_URL", ""),
             lambda v: v == "" or v.startswith("https://"))
    ntfy = ask("ntfy topic for the watchdog's alerts", env.get("NTFY_TOPIC", ""), lambda v: re.fullmatch(r"[\w-]*", v) is not None)

    print("\n5/5  Live trading switch: with 'yes' the service places real orders when started")
    live = ask("type yes to allow real orders", env.get("I_UNDERSTAND_LIVE_TRADING", "no"), lambda v: v in ("yes", "no"))

    print(f"\nAbout to save:\n  key        {key}\n  capital    ${cfg['capital']:,.0f}\n"
          f"  heartbeat  {hc or '(none)'}\n  ntfy topic {ntfy or '(none)'}\n  live       {live}")
    if ask("Save? (yes/no)", "", lambda v: v in ("yes", "no")) != "yes":
        sys.exit("Nothing saved. Run it again: sudo wickctl configure")

    with open(ENV, "w") as fh:
        fh.write("# Written by bot/spot/deploy/configure.py. Never commit or share this file.\n")
        fh.write(f'COINBASE_API_KEY="{key}"\nCOINBASE_API_SECRET="{secret}"\n')
        fh.write(f'HEALTHCHECK_URL="{hc}"\nNTFY_TOPIC="{ntfy}"\nI_UNDERSTAND_LIVE_TRADING={live}\n')
    os.chown(ENV, 0, grp.getgrnam("wick").gr_gid)
    os.chmod(ENV, 0o640)
    json.dump(cfg, open(CFG, "w"), indent=2)
    w = pwd.getpwnam("wick")
    os.chown(CFG, w.pw_uid, w.pw_gid)
    print(f"\nSaved: {ENV} (key, alerts, live={live}) and capital ${cfg['capital']:,.0f} in {CFG}.")
    print("Next: wickctl preflight")


if __name__ == "__main__":
    main()
