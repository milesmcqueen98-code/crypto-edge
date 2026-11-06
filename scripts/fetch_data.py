#!/usr/bin/env python3
"""
Daily data pull for crypto-edge (runs on GitHub Actions; also runs locally).

Universe = every coin tradable against USD on Coinbase (primary) or Kraken (fallback),
which is what a US account can actually trade. Writes one CSV per coin so daily updates
are small appends:

    data/prices/<BASE>.csv     date,open,high,low,close,volume,venue
    data/funding/<BASE>.csv    date,funding_daily          (Hyperliquid perps, sum of hourly rates)
    data/meta.json             last run time and coverage stats
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import ccxt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICES = os.path.join(ROOT, "data", "prices")
FUNDING = os.path.join(ROOT, "data", "funding")
START = pd.Timestamp("2016-01-01", tz="UTC")
DAY_MS = 86_400_000

# Stablecoins, fiat, wrapped/staked duplicates, tokenized gold: not part of the trading universe
EXCLUDE = {
    "USDT", "USDC", "DAI", "PYUSD", "GUSD", "PAX", "USDP", "BUSD", "TUSD", "UST", "FDUSD", "USDE", "USDS",
    "EURC", "EUROC", "EUR", "GBP", "AUD", "CAD", "JPY", "CHF", "USD1", "RLUSD", "USDG", "FRAX", "LUSD",
    "WBTC", "CBBTC", "CBETH", "WETH", "STETH", "WSTETH", "RETH", "LSETH", "MSOL", "JITOSOL", "BETH",
    "PAXG", "XAUT", "WAXL", "WAMPL", "TBTC", "LBTC", "ZUSD", "SUSD", "MIM", "GHO", "CRVUSD", "DOLA",
}
QUOTE_SKIP_SUFFIX = ("UP", "DOWN", "BULL", "BEAR")   # leveraged tokens


def log(m):
    print(m, flush=True)


def existing(path):
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["date"])
        if len(df):
            return df
    return None


def paginate(fetch, since_ms, step_ms, max_pages=400):
    out, since, now = [], since_ms, int(time.time() * 1000)
    for _ in range(max_pages):
        for attempt in range(3):
            try:
                batch = fetch(since)
                break
            except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                if attempt == 2:
                    log(f"    giving up page: {type(e).__name__}")
                    return out
                time.sleep(2 + 3 * attempt)
        if not batch:
            break
        out += batch
        last = batch[-1][0] if isinstance(batch[-1], list) else batch[-1]["timestamp"]
        if last is None or last < since or last + step_ms >= now:
            break
        since = last + 1
    return out


def usd_bases(ex):
    bases = {}
    for m in ex.markets.values():
        if m.get("spot") and m.get("quote") == "USD" and m.get("active", True) is not False:
            b = m["base"]
            if b in EXCLUDE or b.endswith(QUOTE_SKIP_SUFFIX):
                continue
            bases[b] = m["symbol"]
    return bases


def update_prices():
    os.makedirs(PRICES, exist_ok=True)
    cb = ccxt.coinbaseexchange({"enableRateLimit": True, "timeout": 30_000})
    cb.load_markets()
    venues = [("coinbase", cb, usd_bases(cb))]
    try:
        kr = ccxt.kraken({"enableRateLimit": True, "timeout": 30_000})
        kr.load_markets()
        venues.append(("kraken", kr, usd_bases(kr)))
    except Exception as e:
        log(f"kraken unavailable: {e}")

    done, stats = set(), {}
    for vname, ex, bases in venues:
        todo = sorted(b for b in bases if b not in done)
        log(f"{vname}: {len(todo)} USD markets")
        for i, base in enumerate(todo, 1):
            path = os.path.join(PRICES, f"{base}.csv")
            old = existing(path)
            if old is not None and old["venue"].iloc[-1] != vname:
                done.add(base)          # already sourced from a higher-priority venue
                continue
            since = START if old is None else old["date"].max() - pd.Timedelta(days=3)
            sym = bases[base]
            rows = paginate(lambda s: ex.fetch_ohlcv(sym, "1d", since=s, limit=300),
                            int(since.timestamp() * 1000), DAY_MS)
            if not rows:
                continue
            new = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
            new["date"] = pd.to_datetime(new["ts"], unit="ms").dt.normalize()
            new = new.drop(columns="ts")
            new["venue"] = vname
            # drop today's still-forming candle
            new = new[new["date"] < pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()]
            df = new if old is None else pd.concat([old, new])
            df = df.drop_duplicates("date", keep="last").sort_values("date")
            df[["date", "open", "high", "low", "close", "volume", "venue"]].to_csv(
                path, index=False, date_format="%Y-%m-%d")
            done.add(base)
            stats[base] = len(df)
            if i % 25 == 0:
                log(f"  {vname} {i}/{len(todo)}")
    return stats


def update_funding(bases):
    os.makedirs(FUNDING, exist_ok=True)
    try:
        hl = ccxt.hyperliquid({"enableRateLimit": True, "timeout": 30_000})
        hl.load_markets()
    except Exception as e:
        log(f"hyperliquid unavailable: {e}")
        return 0
    n = 0
    for base in sorted(bases):
        sym = f"{base}/USDC:USDC"
        if sym not in hl.markets:
            continue
        path = os.path.join(FUNDING, f"{base}.csv")
        old = existing(path)
        since = pd.Timestamp("2023-05-01", tz="UTC") if old is None else \
            pd.Timestamp(old["date"].max(), tz="UTC") - pd.Timedelta(days=2)
        rows = paginate(lambda s: hl.fetch_funding_rate_history(sym, since=s, limit=500),
                        int(since.timestamp() * 1000), 3_600_000)
        if not rows:
            continue
        f = pd.DataFrame([{"ts": r["timestamp"], "rate": r["fundingRate"]} for r in rows])
        f["date"] = pd.to_datetime(f["ts"], unit="ms").dt.normalize()
        daily = f.groupby("date", as_index=False)["rate"].sum().rename(columns={"rate": "funding_daily"})
        daily = daily[daily["date"] < pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()]
        df = daily if old is None else pd.concat([old[old["date"] < daily["date"].min()], daily])
        df.sort_values("date").to_csv(path, index=False, date_format="%Y-%m-%d")
        n += 1
    return n


def main():
    t0 = time.time()
    stats = update_prices()
    log(f"prices updated for {len(stats)} coins")
    nf = update_funding(stats.keys() if stats else [f[:-4] for f in os.listdir(PRICES)])
    log(f"funding updated for {nf} coins")
    meta = {"last_run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "coins_with_prices": len(os.listdir(PRICES)),
            "coins_with_funding": len(os.listdir(FUNDING)) if os.path.isdir(FUNDING) else 0,
            "runtime_sec": round(time.time() - t0)}
    with open(os.path.join(ROOT, "data", "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    log(json.dumps(meta))


if __name__ == "__main__":
    sys.exit(main())
