#!/usr/bin/env python3
"""H13 (PS) step 1 - runs on GitHub Actions. The incident history of status.exchange.coinbase.com (an Atlassian
Statuspage), saved raw. No prices are fetched or computed here.

Etiquette (reports/hunt/h13ps/SPEC.md): a plain research User-Agent ("crypto-edge-research/1.0"), nothing else spoofed,
at least 1 s between requests. If the site refuses a plain client (403/429 challenge pages), the run stops and writes
the refusal to data/hunt/h13ps/status/refused.json; the idea is then reported as blocked.

Endpoints tried, JSON first: /api/v2/summary.json, /api/v2/incidents.json, /history.json?page=N (else the HTML
/history?page=N), and for each incident /incidents/<code>.json (else /api/v2/incidents/<code>.json, else the HTML page).

usage: python scripts/hunt/h13ps/fetch_status.py index            history pages -> status/history_*.json, codes.csv
       python scripts/hunt/h13ps/fetch_status.py details [REGEX]  every incident in codes.csv (or names matching REGEX)
                                                                   -> status/details.jsonl.gz
       python scripts/hunt/h13ps/fetch_status.py all              index, then details for every incident since 2021-10
"""
import gzip
import json
import os
import re
import sys
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "data", "hunt", "h13ps", "status")
BASE = "https://status.exchange.coinbase.com"
UA = "crypto-edge-research/1.0"
GAP = 1.1                       # seconds between requests (>= 1 s)
OLDEST = (2021, 10)             # stop paging once every month on a page is older than this
BUDGET_S = 5 * 3600 - 600


class Client:
    def __init__(self):
        self.S = requests.Session()
        self.S.headers["User-Agent"] = UA
        self.last = 0.0
        self.n = 0
        self.log = []

    def get(self, path, params=None, tries=4):
        for a in range(tries):
            w = self.last + GAP - time.time()
            if w > 0:
                time.sleep(w)
            self.last = time.time()
            self.n += 1
            try:
                r = self.S.get(BASE + path, params=params, timeout=30)
            except Exception as e:  # noqa: BLE001
                self.log.append(dict(path=path, params=str(params), status=f"exc {type(e).__name__}"))
                time.sleep(2 + 2 * a)
                continue
            self.log.append(dict(path=path, params=str(params), status=r.status_code, bytes=len(r.content),
                                 ctype=r.headers.get("content-type", "")))
            if r.status_code == 429:
                time.sleep(5 + 5 * a)
                continue
            if r.status_code in (403, 503) and ("challenge" in r.text.lower() or "captcha" in r.text.lower()
                                                or "cloudflare" in r.text.lower()):
                refused(path, r)
            return r
        return None


def refused(path, r):
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(path=path, status=r.status_code, headers=dict(r.headers), body=r.text[:2000]),
              open(os.path.join(OUT, "refused.json"), "w"), indent=1)
    print(f"REFUSED at {path}: HTTP {r.status_code}. Stopping (idea blocked if no JSON or HTML route works).")
    sys.exit(0)


def find_incidents(obj, out, month=None):
    """Every dict with 'code' and 'name' inside a history page (structure-agnostic), with its month if known."""
    if isinstance(obj, dict):
        if "name" in obj and "year" in obj and "incidents" in obj:
            month = (obj.get("year"), obj.get("name"))
        if "code" in obj and "name" in obj and isinstance(obj.get("code"), str):
            out.append(dict(code=obj["code"], name=obj.get("name"), impact=obj.get("impact"),
                            message=(obj.get("message") or "")[:300], timestamp=str(obj.get("timestamp", ""))[:300],
                            month=f"{month[0]}-{month[1]}" if month else ""))
        for v in obj.values():
            find_incidents(v, out, month)
    elif isinstance(obj, list):
        for v in obj:
            find_incidents(v, out, month)


MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}


def index(c):
    os.makedirs(OUT, exist_ok=True)
    for p in ("/api/v2/summary.json", "/api/v2/incidents.json"):
        r = c.get(p)
        if r is not None and r.ok:
            open(os.path.join(OUT, p.strip("/").replace("/", "_")), "w").write(r.text)
        print(p, None if r is None else r.status_code, flush=True)
    rows, route = [], None
    for page in range(1, 400):
        r = c.get("/history.json", {"page": page})
        if r is not None and r.ok and "json" in r.headers.get("content-type", ""):
            route = "json"
            js = r.json()
            json.dump(js, open(os.path.join(OUT, f"history_{page:03d}.json"), "w"))
            got = []
            find_incidents(js, got)
            months = [(m.get("year"), MONTHS.get(m.get("name"), 0)) for m in js.get("months", [])] \
                if isinstance(js, dict) else []
        else:
            r = c.get("/history", {"page": page})
            if r is None or not r.ok:
                print(f"history page {page}: {None if r is None else r.status_code}; stop", flush=True)
                break
            route = "html"
            open(os.path.join(OUT, f"history_{page:03d}.html"), "w").write(r.text)
            codes = sorted(set(re.findall(r'/incidents/([a-z0-9]{12})', r.text)))
            got = [dict(code=k, name="", impact="", message="", timestamp="", month="") for k in codes]
            months = []
        for g in got:
            g["page"] = page
        rows += got
        oldest = min(months) if months else None
        print(f"history page {page} ({route}): {len(got)} incidents; months {months[:1]}..{months[-1:]}",
              flush=True)
        if not got and page > 1:
            break
        if oldest is not None and oldest < OLDEST:
            break
    C = pd.DataFrame(rows).drop_duplicates("code") if rows else pd.DataFrame(columns=["code"])
    C.to_csv(os.path.join(OUT, "codes.csv"), index=False)
    print(f"index done: {len(C)} distinct incidents via {route}; {c.n} requests", flush=True)
    return C


def details(c, C, regex=None):
    t0 = time.time()
    if regex:
        C = C[C.name.fillna("").str.contains(regex, case=False, regex=True)]
    path = os.path.join(OUT, "details.jsonl.gz")
    done = set()
    if os.path.exists(path):
        with gzip.open(path, "rt") as f:
            for line in f:
                done.add(json.loads(line)["code"])
    n_ok = n_bad = 0
    with gzip.open(path, "at") as f:
        for k, code in enumerate(C.code):
            if code in done:
                continue
            if time.time() - t0 > BUDGET_S:
                print("time budget reached; stopping (re-run continues where this stopped)", flush=True)
                break
            rec = dict(code=code)
            r = c.get(f"/incidents/{code}.json")
            if r is not None and r.ok and "json" in r.headers.get("content-type", ""):
                rec.update(route="incidents.json", data=r.json())
            else:
                r2 = c.get(f"/api/v2/incidents/{code}.json")
                if r2 is not None and r2.ok and "json" in r2.headers.get("content-type", ""):
                    rec.update(route="api_v2", data=r2.json())
                else:
                    r3 = c.get(f"/incidents/{code}")
                    if r3 is not None and r3.ok:
                        rec.update(route="html", html=r3.text)
                    else:
                        rec.update(route="failed", status=None if r3 is None else r3.status_code)
            n_ok += rec["route"] != "failed"
            n_bad += rec["route"] == "failed"
            f.write(json.dumps(rec) + "\n")
            if (k + 1) % 100 == 0:
                print(f"details {k + 1}/{len(C)} ok {n_ok} failed {n_bad} ({time.time() - t0:.0f}s)", flush=True)
    print(f"details done: ok {n_ok} failed {n_bad}; {c.n} requests total", flush=True)


def main():
    mode = sys.argv[1]
    c = Client()
    try:
        if mode in ("index", "all"):
            C = index(c)
        else:
            C = pd.read_csv(os.path.join(OUT, "codes.csv"))
        if mode in ("details", "all"):
            details(c, C, sys.argv[2] if len(sys.argv) > 2 else None)
    finally:
        os.makedirs(OUT, exist_ok=True)
        pd.DataFrame(c.log).to_csv(os.path.join(OUT, f"requests_{mode}.csv"), index=False)


if __name__ == "__main__":
    main()
