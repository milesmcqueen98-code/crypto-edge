#!/usr/bin/env python3
"""Edge hunt data probe, round 2: history depth of Coinbase perp trades, trade-side convention, Tardis
coinbase-derivatives free files, Binance bookDepth, delisted-product candles, unlock data.
Writes reports/hunt/probe2.json."""
import calendar
import gzip
import io
import json
import os
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "hunt", "probe2.json")
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
R = {}
ADV = "https://api.coinbase.com/api/v3/brokerage/market/products"


def ts(s):
    return int(calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M")))


def rec(name, fn):
    t0 = time.time()
    try:
        out = fn()
    except Exception as e:  # noqa: BLE001
        out = {"error": f"{type(e).__name__}: {e}"[:400]}
    out = out if isinstance(out, dict) else {"result": out}
    out["secs"] = round(time.time() - t0, 2)
    R[name] = out
    print(f"\n=== {name}\n{json.dumps(out, default=str)[:1800]}")


def trades(pid, start, end, limit=1000):
    r = S.get(f"{ADV}/{pid}/ticker", params={"limit": limit, "start": ts(start), "end": ts(end)}, timeout=30)
    js = r.json()
    tr = js.get("trades", [])
    t = sorted(x["time"] for x in tr)
    return r.status_code, tr, js


def depth_scan(pid):
    """First month with trades, scanning month starts back from Nov 2026 (one 6-hour window per month)."""
    out = {}
    for y, m in [(2026, 10), (2026, 7), (2026, 4), (2026, 1), (2025, 12), (2025, 11), (2025, 10), (2025, 9),
                 (2025, 8), (2025, 7)]:
        st, tr, _ = trades(pid, f"{y}-{m:02d}-15 12:00", f"{y}-{m:02d}-15 18:00")
        out[f"{y}-{m:02d}"] = len(tr)
    return out


def side_convention(pid, start, end):
    """Compare trade side with the price change from the previous trade: if 'SELL' trades tick down, side is the
    taker (aggressor) side."""
    st, tr, js = trades(pid, start, end)
    tr = sorted(tr, key=lambda x: (x["time"], int(x["trade_id"])))
    up = {"BUY": [0, 0], "SELL": [0, 0]}
    for a, b in zip(tr, tr[1:]):
        d = float(b["price"]) - float(a["price"])
        if d == 0:
            continue
        up[b["side"]][0 if d > 0 else 1] += 1
    return {"n": len(tr), "upticks_downticks_by_side": up}


def tardis(path, nbytes=300000):
    r = S.get("https://datasets.tardis.dev/v1/" + path, stream=True, timeout=60)
    head = ""
    if r.status_code == 200:
        raw = r.raw.read(nbytes)
        try:
            head = gzip.GzipFile(fileobj=io.BytesIO(raw)).read(1200).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            head = "partial"
    return {"status": r.status_code, "head": head[:1000]}


def tardis_ex(ex):
    r = S.get(f"https://api.tardis.dev/v1/exchanges/{ex}", timeout=30)
    js = r.json()
    syms = (js.get("datasets") or {}).get("symbols") or []
    return {"availableSince": js.get("availableSince"), "n_symbols": len(syms),
            "symbols": [(s.get("id"), s.get("availableSince"), s.get("dataTypes")) for s in syms[:40]]}


def bookdepth():
    r = S.get("https://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2025-10-10.zip",
              timeout=60)
    import zipfile
    if r.status_code != 200:
        return {"status": r.status_code}
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = z.namelist()[0]
    txt = z.read(name).decode()[:800]
    return {"status": 200, "bytes": len(r.content), "head": txt}


def first_bookdepth():
    out = {}
    for d in ("2023-01-01", "2023-06-01", "2024-01-01"):
        r = S.head(f"https://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-{d}.zip",
                   timeout=30)
        out[d] = r.status_code
    return out


def delisted_candles():
    js = S.get("https://api.exchange.coinbase.com/products", timeout=30).json()
    dl = [p["id"] for p in js if p.get("status") == "delisted" and p.get("quote_currency") == "USD"]
    out = {"n_delisted_usd": len(dl), "sample": dl[:15]}
    for pid in dl[:4]:
        r = S.get(f"https://api.exchange.coinbase.com/products/{pid}/candles",
                  params={"granularity": 86400}, timeout=30)
        body = r.json()
        out[pid] = {"status": r.status_code, "n": len(body) if isinstance(body, list) else str(body)[:120]}
    return out


def new_at_listing():
    js = S.get(ADV, params={"product_type": "SPOT", "limit": 2000}, timeout=30).json()
    pr = js.get("products", [])
    usd = [(p["product_id"], p.get("new_at"), p.get("status"), p.get("approximate_quote_24h_volume")) for p in pr
           if p["product_id"].endswith("-USD")]
    with_new = [u for u in usd if u[1]]
    with_new.sort(key=lambda u: u[1])
    return {"n_usd": len(usd), "n_with_new_at": len(with_new), "earliest": with_new[:5], "latest": with_new[-25:]}


def llama_cdn():
    out = {}
    for url in ("https://defillama-datasets.llama.fi/emissions/arbitrum",
                "https://defillama-datasets.llama.fi/emissionsBreakdown",
                "https://api.llama.fi/emissionsBreakdown"):
        r = S.get(url, timeout=30)
        out[url] = {"status": r.status_code, "ct": r.headers.get("content-type"), "body": r.text[:300]}
    return out


def cryptocompare():
    r = S.get("https://min-api.cryptocompare.com/data/v2/histominute",
              params={"fsym": "BTC", "tsym": "USD", "e": "Coinbase", "limit": 10, "toTs": ts("2025-10-10 21:20")},
              timeout=30)
    return {"status": r.status_code, "body": r.text[:500]}


def main():
    for pid in ("BIP-20DEC30-CDE", "ETP-20DEC30-CDE", "SLP-20DEC30-CDE", "DOP-20DEC30-CDE", "SUP-20DEC30-CDE"):
        rec(f"depth_{pid}", lambda pid=pid: depth_scan(pid))
    rec("side_ETP", lambda: side_convention("ETP-20DEC30-CDE", "2026-10-15 13:00", "2026-10-15 14:00"))
    rec("side_spot_ETH", lambda: side_convention("ETH-USD", "2026-10-15 13:00", "2026-10-15 13:02"))
    rec("tardis_cbd_meta", lambda: tardis_ex("coinbase-derivatives"))
    rec("tardis_cbd_trades", lambda: tardis("coinbase-derivatives/trades/2026/02/01/BIP-20DEC30-CDE.csv.gz"))
    rec("tardis_cbd_book", lambda: tardis("coinbase-derivatives/incremental_book_L2/2026/02/01/BIP-20DEC30-CDE.csv.gz"))
    rec("tardis_cbd_snap", lambda: tardis("coinbase-derivatives/book_snapshot_25/2026/02/01/BIP-20DEC30-CDE.csv.gz"))
    rec("tardis_cb_book_snap", lambda: tardis("coinbase/book_snapshot_25/2026/02/01/DOGE-USD.csv.gz"))
    rec("tardis_hl_ticker", lambda: tardis("hyperliquid/derivative_ticker/2026/02/01/BTC.csv.gz"))
    rec("binance_bookdepth_sample", bookdepth)
    rec("binance_bookdepth_start", first_bookdepth)
    rec("coinbase_delisted_candles", delisted_candles)
    rec("coinbase_new_at", new_at_listing)
    rec("llama_cdn", llama_cdn)
    rec("cryptocompare_minute", cryptocompare)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(R, f, indent=1, default=str)


if __name__ == "__main__":
    main()
