#!/usr/bin/env python3
"""Edge hunt (Nov 2026), data probe: which new data sources are reachable from a GitHub runner, and how much history
each one serves. Prints a summary and writes reports/hunt/probe.json. Read-only; no keys are used.

usage: python scripts/hunt/probe.py
"""
import gzip
import io
import json
import os
import time
import xml.etree.ElementTree as ET

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "hunt", "probe.json")
S = requests.Session()
S.headers["User-Agent"] = "crypto-edge-research/1.0"
R = {}


def ts(s):
    return int(time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))) - time.timezone if False else int(
        __import__("calendar").timegm(time.strptime(s, "%Y-%m-%d %H:%M")))


def rec(name, fn):
    t0 = time.time()
    try:
        out = fn()
    except Exception as e:  # noqa: BLE001
        out = {"error": f"{type(e).__name__}: {e}"[:400]}
    out = out if isinstance(out, dict) else {"result": out}
    out["secs"] = round(time.time() - t0, 2)
    R[name] = out
    print(f"\n=== {name}\n{json.dumps(out, default=str)[:1500]}")


def get(url, **kw):
    r = S.get(url, timeout=30, **kw)
    return r


# ------------------------------------------------------------------ Coinbase Advanced (perps and spot trades)
def cb_trades(pid, start, end):
    url = f"https://api.coinbase.com/api/v3/brokerage/market/products/{pid}/ticker"
    r = get(url, params={"limit": 1000, "start": ts(start), "end": ts(end)})
    js = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text[:300]}
    tr = js.get("trades", []) if isinstance(js, dict) else []
    times = sorted(t.get("time") for t in tr if t.get("time"))
    return {"status": r.status_code, "n": len(tr), "first": times[0] if times else None,
            "last": times[-1] if times else None, "sample": tr[:2], "keys": list(js)[:10] if isinstance(js, dict) else None}


def cb_candles(pid, start, end):
    url = f"https://api.coinbase.com/api/v3/brokerage/market/products/{pid}/candles"
    r = get(url, params={"start": ts(start), "end": ts(end), "granularity": "ONE_MINUTE"})
    js = r.json()
    c = js.get("candles", [])
    return {"status": r.status_code, "n": len(c), "sample": c[:1]}


def cb_products():
    r = get("https://api.exchange.coinbase.com/products")
    js = r.json()
    usd = [p for p in js if p.get("quote_currency") == "USD"]
    st = {}
    for p in usd:
        st[p.get("status")] = st.get(p.get("status"), 0) + 1
    stable = [p["id"] for p in usd if p["base_currency"] in ("USDT", "DAI", "PYUSD", "EURC", "USDS", "RLUSD", "GUSD")]
    return {"n_all": len(js), "n_usd": len(usd), "status": st, "stable_pairs": stable,
            "sample_keys": list(usd[0])[:30] if usd else None}


def cb_adv_products():
    r = get("https://api.coinbase.com/api/v3/brokerage/market/products", params={"product_type": "SPOT", "limit": 1000})
    js = r.json()
    pr = js.get("products", [])
    keys = list(pr[0]) if pr else []
    newish = [p.get("product_id") for p in pr if p.get("new")][:50]
    return {"status": r.status_code, "n": len(pr), "keys": keys, "flagged_new": newish}


def cb_exchange_old_candles(pid):
    # does the Exchange API still serve candles for an old window of a currently listed product?
    r = get(f"https://api.exchange.coinbase.com/products/{pid}/candles",
            params={"granularity": 60, "start": "2023-03-11T00:00:00Z", "end": "2023-03-11T04:00:00Z"})
    js = r.json()
    return {"status": r.status_code, "n": len(js) if isinstance(js, list) else js}


# ------------------------------------------------------------------ announcements
def upbit(base):
    r = get(f"{base}/api/v1/announcements", params={"os": "web", "page": 1, "per_page": 20, "category": "trade"})
    js = r.json()
    d = js.get("data", {}) if isinstance(js, dict) else {}
    notices = d.get("notices") or d.get("list") or []
    return {"status": r.status_code, "total_pages": d.get("total_pages"), "n": len(notices),
            "sample": [(n.get("title"), n.get("listed_at") or n.get("created_at")) for n in notices[:5]]}


def binance_cms(catalog):
    r = get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query",
            params={"type": 1, "catalogId": catalog, "pageNo": 1, "pageSize": 20})
    js = r.json()
    arts = js.get("data", {}).get("catalogs", [{}])[0].get("articles", []) if js.get("data") else []
    return {"status": r.status_code, "total": js.get("data", {}).get("catalogs", [{}])[0].get("total"),
            "sample": [(a.get("title"), a.get("releaseDate")) for a in arts[:5]]}


# ------------------------------------------------------------------ Binance bulk data, Tardis free tier
def s3_list(prefix, n=40):
    url = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
    r = get(url, params={"delimiter": "/", "prefix": prefix})
    root = ET.fromstring(r.content)
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    pre = [e.text for e in root.findall(".//s:CommonPrefixes/s:Prefix", ns)]
    keys = [e.text for e in root.findall(".//s:Contents/s:Key", ns)]
    return {"status": r.status_code, "prefixes": pre[:n], "n_prefixes": len(pre), "keys": keys[:6], "n_keys": len(keys)}


def binance_liq_files():
    out = s3_list("data/futures/um/daily/liquidationSnapshot/BTCUSDT/")
    out2 = s3_list("data/futures/um/monthly/liquidationSnapshot/BTCUSDT/")
    return {"daily": out, "monthly": out2}


def tardis(path):
    r = get("https://datasets.tardis.dev/v1/" + path, stream=True)
    head = b""
    if r.status_code == 200:
        raw = r.raw.read(200000)
        try:
            head = gzip.GzipFile(fileobj=io.BytesIO(raw)).read(800)
        except Exception:  # noqa: BLE001  (partial gzip stream)
            head = raw[:200]
    return {"status": r.status_code, "head": head.decode("utf-8", "replace")[:700]}


def tardis_exchanges():
    r = get("https://api.tardis.dev/v1/exchanges")
    js = r.json()
    ids = [e.get("id") for e in js]
    return {"status": r.status_code, "n": len(ids), "ids": ids}


def tardis_ex(ex):
    r = get(f"https://api.tardis.dev/v1/exchanges/{ex}")
    js = r.json()
    return {"status": r.status_code, "availableSince": js.get("availableSince"),
            "channels": js.get("availableChannels", [])[:40],
            "datasets": (js.get("datasets") or {}).get("formats"),
            "dataTypes": list(((js.get("datasets") or {}).get("symbols") or [{}])[0].get("dataTypes", []))}


# ------------------------------------------------------------------ Hyperliquid
def hl(body):
    r = S.post("https://api.hyperliquid.xyz/info", json=body, timeout=30)
    return r.status_code, r.json()


def hl_candles():
    out = {}
    for start in ("2023-06-01 00:00", "2025-01-01 00:00", "2026-10-01 00:00"):
        s = ts(start) * 1000
        st, js = hl({"type": "candleSnapshot", "req": {"coin": "BTC", "interval": "1m", "startTime": s, "endTime": s + 3600_000}})
        out[start] = {"status": st, "n": len(js) if isinstance(js, list) else str(js)[:200]}
    return out


def hl_hlp():
    st, js = hl({"type": "vaultDetails", "vaultAddress": "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"})
    rel = js.get("relationship") if isinstance(js, dict) else None
    return {"status": st, "name": js.get("name") if isinstance(js, dict) else None, "relationship": rel}


def hl_fills_of_children():
    st, js = hl({"type": "vaultDetails", "vaultAddress": "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"})
    kids = ((js or {}).get("relationship") or {}).get("data", {}).get("childAddresses", []) if isinstance(js, dict) else []
    out = {}
    for a in kids[:4]:
        st2, f = hl({"type": "userFillsByTime", "user": a, "startTime": ts("2025-10-10 00:00") * 1000,
                     "endTime": ts("2025-10-11 06:00") * 1000})
        liq = [x for x in f if isinstance(x, dict) and x.get("liquidation")] if isinstance(f, list) else []
        out[a] = {"status": st2, "n": len(f) if isinstance(f, list) else str(f)[:200], "n_liq": len(liq),
                  "sample": (f[:1] if isinstance(f, list) else None)}
    return {"children": kids, "fills": out}


def hl_funding():
    st, js = hl({"type": "fundingHistory", "coin": "BTC", "startTime": ts("2023-05-01 00:00") * 1000})
    return {"status": st, "n": len(js) if isinstance(js, list) else str(js)[:200], "first": js[:1] if isinstance(js, list) else None}


# ------------------------------------------------------------------ unlocks, ETF flows, misc
def llama(url):
    r = get(url)
    ct = r.headers.get("content-type", "")
    body = r.json() if "json" in ct else r.text[:300]
    return {"status": r.status_code, "type": ct, "len": len(body) if hasattr(body, "__len__") else None,
            "sample": (body[:3] if isinstance(body, list) else (list(body)[:10] if isinstance(body, dict) else body))}


def main():
    rec("cb_adv_trades_perp_ETP_2026-02-05", lambda: cb_trades("ETP-20DEC30-CDE", "2026-02-05 12:00", "2026-02-05 12:05"))
    rec("cb_adv_trades_perp_DOP_2026-02-05", lambda: cb_trades("DOP-20DEC30-CDE", "2026-02-05 12:00", "2026-02-05 13:00"))
    rec("cb_adv_trades_perp_BIP_2025-10-10", lambda: cb_trades("BIP-20DEC30-CDE", "2025-10-10 21:15", "2025-10-10 21:20"))
    rec("cb_adv_trades_spot_BTC_2025-10-10", lambda: cb_trades("BTC-USD", "2025-10-10 21:15", "2025-10-10 21:16"))
    rec("cb_adv_candles_perp_DOP", lambda: cb_candles("DOP-20DEC30-CDE", "2026-02-05 12:00", "2026-02-05 13:00"))
    rec("cb_exchange_products", cb_products)
    rec("cb_adv_spot_products", cb_adv_products)
    rec("cb_exchange_old_candles_ETH", lambda: cb_exchange_old_candles("ETH-USD"))
    rec("upbit_kr", lambda: upbit("https://api-manager.upbit.com"))
    rec("upbit_sg", lambda: upbit("https://sg-api-manager.upbit.com"))
    rec("binance_cms_new_listings_48", lambda: binance_cms(48))
    rec("binance_cms_delist_161", lambda: binance_cms(161))
    rec("binance_vision_um_daily_types", lambda: s3_list("data/futures/um/daily/"))
    rec("binance_vision_liq", binance_liq_files)
    rec("binance_vision_spot_daily_types", lambda: s3_list("data/spot/daily/"))
    rec("tardis_exchanges", tardis_exchanges)
    rec("tardis_ex_binance_futures", lambda: tardis_ex("binance-futures"))
    rec("tardis_ex_hyperliquid", lambda: tardis_ex("hyperliquid"))
    rec("tardis_ex_coinbase", lambda: tardis_ex("coinbase"))
    rec("tardis_free_binance_liq", lambda: tardis("binance-futures/liquidations/2025/10/01/BTCUSDT.csv.gz"))
    rec("tardis_free_hl_liq", lambda: tardis("hyperliquid/liquidations/2025/10/01/BTC.csv.gz"))
    rec("tardis_free_hl_trades", lambda: tardis("hyperliquid/trades/2025/10/01/BTC.csv.gz"))
    rec("tardis_free_cb_trades", lambda: tardis("coinbase/trades/2025/10/01/BTC-USD.csv.gz"))
    rec("tardis_free_binance_liq_notfirst", lambda: tardis("binance-futures/liquidations/2025/10/10/BTCUSDT.csv.gz"))
    rec("hl_candles_1m_depth", hl_candles)
    rec("hl_hlp_vault", hl_hlp)
    rec("hl_hlp_children_fills_oct10", hl_fills_of_children)
    rec("hl_funding", hl_funding)
    rec("llama_emissions_list", lambda: llama("https://defillama-datasets.llama.fi/emissionsProtocolsList"))
    rec("llama_emissions_api", lambda: llama("https://api.llama.fi/emissions"))
    rec("llama_emission_arbitrum", lambda: llama("https://api.llama.fi/emission/arbitrum"))
    rec("farside_btc", lambda: {"status": get("https://farside.co.uk/bitcoin-etf-flow-all-data/").status_code})
    rec("coingecko_ping", lambda: {"status": get("https://api.coingecko.com/api/v3/ping").status_code})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(R, f, indent=1, default=str)


if __name__ == "__main__":
    main()
