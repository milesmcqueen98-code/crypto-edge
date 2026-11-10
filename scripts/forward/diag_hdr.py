"""Scratch diagnostic: cache headers of the Coinbase endpoints the collector uses (each asked twice, 2 s apart)."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, collector as C
h = C.Http()
H = ("age", "cache-control", "cf-cache-status", "date")
now = int(time.time())
ends = [
    ("exchange book L2 BTC", f"{C.EXCHANGE}/products/BTC-USD/book", {"level": 2}),
    ("exchange book L2 LTC", f"{C.EXCHANGE}/products/LTC-USD/book", {"level": 2}),
    ("adv futures list (cfm)", f"{C.ADV}/products", {"product_type": "FUTURE", "limit": 500}),
    ("adv product_book LTC", f"{C.ADV}/product_book", {"product_id": "LTC-USD", "limit": 1000}),
    ("adv candles LTC", f"{C.ADV}/products/LTC-USD/candles", {"start": str(now - 300), "end": str(now), "granularity": "ONE_MINUTE"}),
    ("exchange candles LTC bot window", f"{C.EXCHANGE}/products/LTC-USD/candles", None),
]
for name, url, p in ends:
    if p is None:
        q = pd.Timestamp(time.time() // 60 * 60, unit="s")
        p = {"granularity": 60, "start": (q - pd.Timedelta(minutes=4)).isoformat() + "Z", "end": (q - pd.Timedelta(minutes=1)).isoformat() + "Z"}
    for k in (1, 2):
        r = h.s.get(url, params=p, timeout=8)
        print("HDR", name, k, r.status_code, {x: r.headers.get(x) for x in H if r.headers.get(x)}, flush=True)
        time.sleep(2)
