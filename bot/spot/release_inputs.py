"""Input settings that the live bot takes from the release (bot/spot/README.md, "Inputs of the live bot").

The live bot runs with bot/spot/config.live.json, an untracked copy of bot/spot/config.json made when the VM was set
up. Its data-source settings and its order-path settings (INPUT_KEYS) are taken from the release's bot/spot/config.json
at every start, so a code update also moves the live bot to the release's inputs. Every other key stays as the live
file has it. A live file with "inputs_local": true keeps its own input settings.

Pure functions, standard library only (Python 3.8 and later); the caller loads the files.
"""
import copy
import os

ORDER_KEYS = ("order_path", "orders_rate", "place_workers")       # README, "Order path"
INPUT_KEYS = ("newest_bar", "trades_coins", "stale_guard", "trades_rows", "trades_budget_s", "confirm_s",
              "candles_at_s") + ORDER_KEYS
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


def describe(cfg, coins=None):
    """One plain line for a human, built only from the config and, when given, the book's coins (a trades list that
    holds BTC and every one of them reads as no list does)."""
    if cfg.get("newest_bar", "candles") == "trades":
        tc = cfg.get("trades_coins")
        at = cfg.get("candles_at_s")                       # their candles fetched between steps (engine.candle_pass)
        pre = "" if at is None else ", their candles fetched between steps from second %s" % at
        if tc is None or (tc and coins is not None and set(["BTC"] + list(coins)) <= set(tc)):
            src = "newest minute from trades for BTC and every coin" + pre
        elif not tc:
            src = "newest minute from trades for no coin (empty list); candles for every coin"
        else:
            src = "newest minute from trades for %s%s; candles for the other coins" % (_names(tc), pre)
    else:
        src = "candles for every coin"
    line = "inputs: %s; stale guard %s" % (src, "on" if cfg.get("stale_guard", False) else "off")
    rows = cfg.get("trades_rows") if cfg.get("newest_bar", "candles") == "trades" else None   # read in trades mode only
    if rows == "candle_after":
        line += "; the venue's candle replaces each trades row afterwards"
    elif rows is not None and rows != "keep":                # "keep" is the default behaviour: nothing to add
        line += "; trades_rows %s" % rows
    if cfg.get("order_path") == "batch":
        line += "; order path batch (%s requests a second, %s placing threads)" % (cfg.get("orders_rate", 10),
                                                                                   cfg.get("place_workers", 1))
    return line
