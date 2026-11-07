#!/usr/bin/env python3
"""H7 (UL) step 1 (runs on GitHub Actions): download DefiLlama's free token-unlock dataset CDN.

  https://defillama-datasets.llama.fi/emissionsProtocolsList   -> list of protocol slugs
  https://defillama-datasets.llama.fi/emissions/<protocol>       -> schedule JSON per protocol

(The api.llama.fi versions are paid; not used.) Writes, under data/hunt/h7ul/:
  emissionsProtocolsList.json
  protocols_summary.csv          one row per protocol: name, gecko_id, token, category keys, section labels, span
  emissions/<protocol>.json.gz   the raw JSON (all protocols if the total stays under ~40 MB, else only protocols
                                 whose slug/name/gecko id matches a coin in common.PERP)
No prices are touched here.
"""
import gzip
import json
import os
import re
import sys
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "data", "hunt", "h7ul")
CDN = "https://defillama-datasets.llama.fi"

# broad name patterns for the coins in common.PERP (used only to choose what to commit if everything is too big)
PERP_PAT = re.compile(r"sui|ethena|ondo|hyperliquid|near|aave|chainlink|ripple|xrp|avalanche|avax|cardano|hedera|"
                      r"polkadot|solana|pepe|shib|binance|bnb|doge|litecoin|bitcoin|stellar|zcash|ethereum",
                      re.I)


def get(S, url, tries=6):
    for a in range(tries):
        try:
            r = S.get(url, timeout=60)
            if r.status_code == 429:
                time.sleep(2 + 2 * a)
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            print("retry", url, e, flush=True)
            time.sleep(2 + 2 * a)
    return None


def summarise(slug, js):
    row = dict(protocol=slug, top_keys="|".join(sorted(js.keys())) if isinstance(js, dict) else type(js).__name__)
    if not isinstance(js, dict):
        return row
    row["name"] = js.get("name")
    row["gecko_id"] = js.get("gecko_id") or js.get("geckoId")
    md = js.get("metadata") or {}
    row["token"] = md.get("token") if isinstance(md, dict) else None
    row["n_events_meta"] = len(md.get("events") or []) if isinstance(md, dict) else None
    cats = js.get("categories") or {}
    row["categories"] = json.dumps(cats)[:2000] if cats else ""
    dd = (js.get("documentedData") or {}).get("data") or js.get("data") or []
    labels, t0, t1 = [], None, None
    for sec in dd:
        labels.append(str(sec.get("label")))
        ts = [p.get("timestamp") for p in (sec.get("data") or []) if p.get("timestamp") is not None]
        if ts:
            t0 = min(ts) if t0 is None else min(t0, min(ts))
            t1 = max(ts) if t1 is None else max(t1, max(ts))
    row["sections"] = "|".join(labels)[:2000]
    row["t0"] = pd.to_datetime(t0, unit="s") if t0 else None
    row["t1"] = pd.to_datetime(t1, unit="s") if t1 else None
    row["has_realtime"] = bool(js.get("realTimeData"))
    sm = js.get("supplyMetrics")
    row["supplyMetrics"] = json.dumps(sm)[:500] if sm else ""
    return row


def main():
    os.makedirs(os.path.join(OUT, "emissions"), exist_ok=True)
    S = requests.Session()
    S.headers["User-Agent"] = "crypto-edge-research/1.0"
    lst = json.loads(get(S, f"{CDN}/emissionsProtocolsList"))
    with open(os.path.join(OUT, "emissionsProtocolsList.json"), "w") as f:
        json.dump(lst, f)
    slugs = [x if isinstance(x, str) else (x.get("protocol") or x.get("name") or x.get("id")) for x in lst]
    print("protocols:", len(slugs), slugs[:10], flush=True)
    raw, rows = {}, []
    for i, s in enumerate(slugs):
        b = get(S, f"{CDN}/emissions/{s}")
        if b is None:
            rows.append(dict(protocol=s, top_keys="MISSING"))
            continue
        try:
            js = json.loads(b)
        except Exception:  # noqa: BLE001
            rows.append(dict(protocol=s, top_keys="BADJSON"))
            continue
        raw[s] = gzip.compress(b, 9)
        rows.append(summarise(s, js))
        if i % 50 == 0:
            print(i, s, len(b), flush=True)
        time.sleep(0.05)
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(OUT, "protocols_summary.csv"), index=False)
    total = sum(len(v) for v in raw.values())
    print("total gz bytes", total, flush=True)
    keep = raw
    if total > 40e6:
        keep = {}
        for s, v in raw.items():
            r = summ[summ.protocol == s].iloc[0]
            hay = f"{s} {r.get('name')} {r.get('gecko_id')}"
            if PERP_PAT.search(hay):
                keep[s] = v
        print("too big; keeping", len(keep), "perp-matching protocols", flush=True)
    for s, v in keep.items():
        with open(os.path.join(OUT, "emissions", f"{s}.json.gz"), "wb") as f:
            f.write(v)
    # also save everything to the artifact dir
    os.makedirs(os.path.join(ROOT, "artifact_h7ul"), exist_ok=True)
    for s, v in raw.items():
        with open(os.path.join(ROOT, "artifact_h7ul", f"{s}.json.gz"), "wb") as f:
            f.write(v)
    print("done", len(keep), "committed;", len(raw), "in artifact", flush=True)


if __name__ == "__main__":
    sys.exit(main())
