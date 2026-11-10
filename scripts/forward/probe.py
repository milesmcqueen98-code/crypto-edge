#!/usr/bin/env python3
"""One-off endpoint probe for the forward collector (run on a GitHub runner; exchange APIs are blocked elsewhere).

Prints, per coin, what each Coinbase book endpoint returns (levels, how deep below mid the bid side reaches, bytes,
latency), the Hyperliquid perp names for the universe, and the shape of the Coinbase futures products listing.
Paced at 4 requests a second to Coinbase. Usage: python scripts/forward/probe.py
"""
import json
import pandas as pd
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collector as C  # noqa: E402

S = requests.Session()
S.headers["User-Agent"] = C.USER_AGENT


def timed(method, url, **kw):
    t0 = time.time()
    try:
        r = S.request(method, url, timeout=10, **kw)
        return r, time.time() - t0
    except requests.RequestException as err:
        return err, time.time() - t0


def reach(bids, asks):
    if not bids or not asks:
        return None, None
    mid = (bids[0][0] + asks[0][0]) / 2
    return round((1 - bids[-1][0] / mid) * 1e4), round((asks[-1][0] / mid - 1) * 1e4)


def main():
    coins = C.universe()
    print("universe", coins, flush=True)
    skip_book = "--no-book" in sys.argv
    print("\n== book endpoints: coin | exchange L2: status ms KB nbid nask bid_reach_bp ask_reach_bp | "
          "advanced limit=1000 | advanced limit=5000", flush=True)
    for coin in ([] if skip_book else coins):
        out = [coin]
        r, dt = timed("GET", f"{C.EXCHANGE}/products/{coin}-USD/book", params={"level": 2})
        if isinstance(r, Exception):
            out.append(f"EXC err {r!r}"[:80])
        else:
            if r.ok:
                b, a = C.parse_exchange_book(r.json())
                out.append(f"EXC {r.status_code} {dt*1e3:.0f}ms {len(r.content)/1e3:.0f}KB {len(b)} {len(a)} {reach(b, a)}")
            else:
                out.append(f"EXC {r.status_code} {r.text[:80]!r}")
        time.sleep(0.25)
        for lim in (1000, 5000):
            r, dt = timed("GET", f"{C.ADV}/product_book", params={"product_id": f"{coin}-USD", "limit": lim})
            if isinstance(r, Exception):
                out.append(f"ADV{lim} err {r!r}"[:80])
            elif r.ok:
                b, a = C.parse_adv_book(r.json())
                out.append(f"ADV{lim} {r.status_code} {dt*1e3:.0f}ms {len(r.content)/1e3:.0f}KB {len(b)} {len(a)} {reach(b, a)}")
            else:
                out.append(f"ADV{lim} {r.status_code} {r.text[:80]!r}")
            time.sleep(0.25)
        print(" | ".join(out), flush=True)
    print("\n== exchange response headers (last call):", "skipped" if skip_book else dict((k, v) for k, v in r.headers.items()
          if "limit" in k.lower() or "cf-" in k.lower()) if not isinstance(r, Exception) else r)
    print("\n== hyperliquid", flush=True)
    r, dt = timed("POST", C.HL_URL, json={"type": "metaAndAssetCtxs"})
    if isinstance(r, Exception) or not r.ok:
        print("HL failed", r if isinstance(r, Exception) else (r.status_code, r.text[:200]))
    else:
        js = r.json()
        names = {u["name"]: u for u in js[0]["universe"]}
        print(f"HL {r.status_code} {dt*1e3:.0f}ms {len(r.content)/1e3:.0f}KB, {len(names)} assets")
        for coin in coins:
            hits = [n for n in names if n in (coin, "k" + coin, "1000" + coin)]
            print(coin, [(h, names[h].get("isDelisted", False)) for h in hits])
        i = list(names).index("BTC")
        print("example ctx", json.dumps(js[1][i]))
        print("all live perps:", len(C.hl_names(js[0]["universe"], None)))
    print("\n== coinbase futures products", flush=True)
    for params in ({"product_type": "FUTURE", "contract_expiry_type": "PERPETUAL"}, {"product_type": "FUTURE"}):
        r, dt = timed("GET", f"{C.ADV}/products", params=dict(params, limit=500))
        if isinstance(r, Exception) or not r.ok:
            print(params, "failed", r if isinstance(r, Exception) else (r.status_code, r.text[:200]))
            continue
        js = r.json()
        prods = js.get("products", [])
        rows = C.parse_cfm(js, None, 0.0)
        if rows:
            df = pd.DataFrame(rows)
            print("cfm fields present (non-missing share):", {c: round(float(df[c].notna().mean()), 2) for c in df
                                                             if c not in ("minute", "t")})
            print("all perps:", sorted(df.product_id))
        print(params, f"{r.status_code} {dt*1e3:.0f}ms {len(r.content)/1e3:.0f}KB num={js.get('num_products')} "
              f"returned={len(prods)} universe perps={sorted(x['coin'] for x in rows)}")
        if rows:
            print("example parsed", rows[0])
        time.sleep(0.5)
    print("\n== candles", flush=True)
    T = pd.Timestamp.now(tz="UTC").tz_localize(None).floor("min")
    r, dt = timed("GET", f"{C.EXCHANGE}/products/BTC-USD/candles", params=C.candle_params(T))
    print("candles", r.status_code if not isinstance(r, Exception) else r, f"{dt*1e3:.0f}ms", r.text[:300] if not isinstance(r, Exception) else "")


if __name__ == "__main__":
    main()
