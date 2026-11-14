"""Input settings that the live bot takes from the release (bot/spot/README.md, "Inputs of the live bot").

The live bot runs with bot/spot/config.live.json, an untracked copy of bot/spot/config.json made when the VM was set
up. Its data-source settings (INPUT_KEYS) are taken from the release's bot/spot/config.json at every start, so a code
update also moves the live bot to the release's inputs. Every other key stays as the live file has it. A live file
with "inputs_local": true keeps its own input settings.

Pure functions, standard library only (Python 3.8 and later); the caller loads the files.
"""
import copy
import os

INPUT_KEYS = ("newest_bar", "trades_coins", "stale_guard", "trades_rows", "trades_budget_s", "confirm_s")
LOCAL_SWITCH = "inputs_local"
LIVE_NAME = "config.live.json"


def applies(config_path):
    """True exactly when the file's base name is config.live.json. Paper configs run what their own file says."""
    return os.path.basename(str(config_path)) == LIVE_NAME


def apply(cfg, base):
    """(new_cfg, notes): cfg with the INPUT_KEYS taken from base. Neither argument is changed."""
    new = copy.deepcopy(cfg)
    if cfg.get(LOCAL_SWITCH) is True:
        return new, ['"%s": true in the live config: its own input settings are used and do not follow releases'
                     % LOCAL_SWITCH]
    notes = []
    for k in INPUT_KEYS:
        if k in base:
            if k in cfg and cfg[k] != base[k]:
                notes.append("%s: the live config had %r, the release's %r is used" % (k, cfg[k], base[k]))
            new[k] = copy.deepcopy(base[k])
        elif k in cfg:
            notes.append("%s: the live config had %r; the release does not set it, so the code's default is used"
                         % (k, cfg[k]))
            del new[k]
    return new, notes


def preflight_file(raw, coins_disabled, bid_ttl_s):
    """What `run.py preflight` writes back to the live file: the file as it was read (raw), plus coins_disabled and,
    when one was found, bid_ttl_s. Settings taken from the release are never written into the file."""
    out = copy.deepcopy(raw)
    out["coins_disabled"] = list(coins_disabled)
    if bid_ttl_s:
        out["bid_ttl_s"] = bid_ttl_s
    return out


def _names(coins):
    return ", ".join(str(c) for c in coins)


def describe(cfg):
    """One plain line for a human, built only from the config."""
    if cfg.get("newest_bar", "candles") == "trades":
        tc = cfg.get("trades_coins")
        if tc is None:
            src = "newest minute from trades for BTC and every coin"
        elif not tc:
            src = "newest minute from trades for no coin (empty list); candles for every coin"
        else:
            src = "newest minute from trades for %s; candles for the other coins" % _names(tc)
    else:
        src = "candles for every coin"
    line = "inputs: %s; stale guard %s" % (src, "on" if cfg.get("stale_guard", False) else "off")
    if cfg.get("trades_rows") is not None:
        line += "; trades_rows %s" % cfg["trades_rows"]
    return line
