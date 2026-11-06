#!/usr/bin/env python3
"""Maker round: one day of Coinbase top-of-book + trades (Tardis free first-of-month files) through the
queue-aware maker simulator, for every pre-registered strategy x scenario. Rules: reports/maker_prereg.md.

  python scripts/maker_day.py probe 2024-01-01 BTC,DOGE    data checks only (no P&L)
  python scripts/maker_day.py run   2024-01-01             all configs -> reports/maker/raw/<day>*.csv

Raw tick files are deleted after use; only derived numbers are written.
"""
import gzip
import json
import os
import shutil
import sys
import time

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge.maker import simulate  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
TMP = os.environ.get("MAKER_TMP", os.path.join(ROOT, ".tick_tmp"))
URL = "https://datasets.tardis.dev/v1/coinbase/{kind}/{y}/{m}/{d}/{sym}.csv.gz"
LAT = {"colo": (1_000, 2_000), "base": (10_000, 50_000), "stress": (20_000, 100_000)}   # (market data, order) us
SIZES = {"10k": (1_000.0, 2_000.0), "100k": (10_000.0, 20_000.0)}                    # (quote size, Q_max) USD
HORIZONS = [1, 10, 60, 300, 900]                                                      # markout seconds
THROTTLE = 100_000
MAX_FILLS = 2_000_000


def download(kind, day, coin):
    y, m, d = day.split("-")
    os.makedirs(TMP, exist_ok=True)
    path = os.path.join(TMP, f"{kind}_{coin}_{day}.csv.gz")
    url = URL.format(kind=kind, y=y, m=m, d=d, sym=f"{coin}-USD")
    for attempt in range(8):
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                with open(path, "wb") as fh:
                    shutil.copyfileobj(r.raw, fh, length=1 << 20)
            return path
        except requests.RequestException as err:
            print(f"  retry {kind} {coin} {day}: {err}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}")


def load_quotes(path):
    df = pd.read_csv(path, usecols=["timestamp", "ask_amount", "ask_price", "bid_price", "bid_amount"],
                     engine="pyarrow")
    df = df.dropna()
    df = df[(df.ask_price > df.bid_price) & (df.bid_amount > 0) & (df.ask_amount > 0)]
    df = df.sort_values("timestamp", kind="stable")
    return (df.timestamp.to_numpy(np.int64), df.bid_price.to_numpy(float), df.bid_amount.to_numpy(float),
            df.ask_price.to_numpy(float), df.ask_amount.to_numpy(float))


def load_trades(path):
    df = pd.read_csv(path, usecols=["timestamp", "side", "price", "amount"], engine="pyarrow")
    df = df.dropna(subset=["price", "amount"]).sort_values("timestamp", kind="stable")
    side = np.where(df.side.to_numpy() == "buy", 1, np.where(df.side.to_numpy() == "sell", -1, 0)).astype(np.int8)
    return df.timestamp.to_numpy(np.int64), side, df.price.to_numpy(float), df.amount.to_numpy(float)


def mid_at(qt, mid, t):
    k = np.searchsorted(qt, t, side="right") - 1
    out = np.where(k >= 0, mid[np.clip(k, 0, None)], np.nan)
    return out


def day_bounds(day):
    t0 = int(pd.Timestamp(day, tz="UTC").value // 1000)
    return t0, t0 + 86_400_000_000


def probe(day, coins):
    for c in coins:
        qp, tp = download("quotes", day, c), download("trades", day, c)
        print(f"== {c} {day}: quotes {os.path.getsize(qp)/1e6:.1f} MB, trades {os.path.getsize(tp)/1e6:.1f} MB")
        with gzip.open(qp, "rt") as fh:
            print("".join([next(fh) for _ in range(3)]), end="")
        with gzip.open(tp, "rt") as fh:
            print("".join([next(fh) for _ in range(3)]), end="")
        qt, bp, bs, ap, as_ = load_quotes(qp)
        tt, ts, tpx, tsz = load_trades(tp)
        mid = 0.5 * (bp + ap)
        spread = ap - bp
        incr = np.min(np.diff(np.unique(np.round(np.r_[bp[:200000], ap[:200000]], 10))))
        print(f"  quote rows {len(qt):,} span {pd.to_datetime(qt[0], unit='us')} -> {pd.to_datetime(qt[-1], unit='us')}; "
              f"trades {len(tt):,} (buy {np.mean(ts == 1):.0%}, sell {np.mean(ts == -1):.0%})")
        print(f"  price increment ~{incr:g}; median spread {np.median(spread):g} ({np.median(spread / mid) * 1e4:.2f} bp); "
              f"1-tick share {np.mean(spread <= incr * 1.5):.0%}; median top size USD bid {np.median(bs * bp):,.0f} ask {np.median(as_ * ap):,.0f}")
        k = np.searchsorted(qt, tt, side="left") - 1                     # book strictly before the trade time
        ok = k >= 0
        bb, ba = np.where(ok, bp[np.clip(k, 0, None)], np.nan), np.where(ok, ap[np.clip(k, 0, None)], np.nan)
        s, b = ts == -1, ts == 1
        print(f"  sells vs prior best bid: at {np.mean(tpx[s] == bb[s]):.1%}, below {np.mean(tpx[s] < bb[s]):.1%}, "
              f"above {np.mean(tpx[s] > bb[s]):.1%} | buys vs prior best ask: at {np.mean(tpx[b] == ba[b]):.1%}, "
              f"above {np.mean(tpx[b] > ba[b]):.1%}, below {np.mean(tpx[b] < ba[b]):.1%}")
        kk = np.searchsorted(qt, tt, side="right")                      # first book update at/after the trade
        lag = np.where(kk < len(qt), qt[np.clip(kk, 0, len(qt) - 1)] - tt, np.nan)
        print(f"  first quote update after a trade: median {np.nanmedian(lag)/1e3:.2f} ms, p90 {np.nanpercentile(lag, 90)/1e3:.1f} ms; "
              f"quote updates/s {len(qt)/86400:.1f}, trades/s {len(tt)/86400:.2f}, $vol {np.sum(tpx*tsz)/1e6:,.0f}M")
        os.remove(qp)
        os.remove(tp)


def signal_grid(day, books, beta):
    t0, _ = day_bounds(day)
    st = t0 + (np.arange(86_400, dtype=np.int64) + 1) * 1_000_000
    lm = {}
    for c, (qt, bp, bs, ap, as_) in books.items():
        m = mid_at(qt, 0.5 * (bp + ap), st)
        lm[c] = np.log(pd.Series(m).ffill().to_numpy())
    L = pd.DataFrame(lm)
    r = L - L.shift(900)
    u = r.sub(r.mean(axis=1), axis=0)
    E = (-beta * u * 1e4).fillna(0.0)
    return st, {c: E[c].to_numpy() for c in books}


def run(day, coins):
    sigp = json.load(open(os.path.join(ROOT, "reports", "maker_signal.json")))
    beta, eref = sigp["beta"], sigp["E_ref_bp"]
    t0, t1 = day_bounds(day)
    books, trades = {}, {}
    for c in coins:
        qp, tp = download("quotes", day, c), download("trades", day, c)
        books[c] = load_quotes(qp)
        trades[c] = load_trades(tp)
        os.remove(qp)
        os.remove(tp)
        print(f"{day} {c}: {len(books[c][0]):,} quotes, {len(trades[c][0]):,} trades", flush=True)
    st, E = signal_grid(day, books, beta)
    minutes = t0 + (np.arange(1, 1441, dtype=np.int64)) * 60_000_000
    rows, paths = [], []
    for c in coins:
        qt, bp, bs, ap, as_ = books[c]
        tt, ts, tpx, tsz = trades[c]
        mid = 0.5 * (bp + ap)
        m_end = mid_at(qt, mid, np.array([t1 - 1]))[0]
        hs_end = 0.5 * (ap[-1] - bp[-1])
        m_min = mid_at(qt, mid, minutes)
        for size_name, (qsz, qmax) in SIZES.items():
            for lat_name, (lmd, lord) in LAT.items():
                for qmodel in (0, 1):
                    for mode in (0, 1, 2):
                        tic = time.time()
                        f_t, f_side, f_px, f_qty, f_kind, nf, q, n_new, n_cxl, n_rej, msgs = simulate(
                            qt, bp, bs, ap, as_, tt, ts, tpx, tsz, st, E[c], np.int64(lmd), np.int64(lord),
                            np.int64(THROTTLE), qsz, qmax, mode, eref, qmodel, np.int64(t0), MAX_FILLS)
                        sgn = np.where(f_side == 0, 1.0, -1.0)            # +1 buy (our bid filled), -1 sell
                        notional = f_qty * f_px
                        cash = -np.sum(sgn * notional)
                        gross = cash + q * m_end
                        m0 = mid_at(qt, mid, f_t)
                        rec = dict(day=day, coin=c, size=size_name, lat=lat_name, qmodel=qmodel, mode=mode,
                                   n_fills=int(nf), n_q=int(np.sum(f_kind == 0)), n_through=int(np.sum(f_kind == 1)),
                                   n_cross=int(np.sum(f_kind == 2)), buy_usd=float(np.sum(notional[sgn > 0])),
                                   sell_usd=float(np.sum(notional[sgn < 0])), gross_pnl=float(gross),
                                   eod_inv_usd=float(q * m_end), eod_halfspread_cost=float(abs(q) * hs_end),
                                   spread_usd=float(np.sum(sgn * f_qty * (m0 - f_px))),
                                   n_new=int(n_new), n_cxl=int(n_cxl), n_rej=int(n_rej),
                                   msg_peak=int(msgs.max()), msg_mean=float(msgs.mean()), sec=time.time() - tic)
                        for h in HORIZONS:
                            mh = mid_at(qt, mid, f_t + h * 1_000_000)
                            rec[f"rs_{h}s_usd"] = float(np.nansum(sgn * f_qty * (mh - f_px)))
                        # signal-aligned fills: buys when E > 0, sells when E < 0 (E observed at the fill second)
                        ks = np.clip((f_t - t0) // 1_000_000 - 1, 0, 86_399)
                        al = sgn * E[c][ks] > 0
                        m900 = mid_at(qt, mid, f_t + 900_000_000)
                        rec["aligned_usd"] = float(np.sum(notional[al]))
                        rec["aligned_rs900_usd"] = float(np.nansum((sgn * f_qty * (m900 - f_px))[al]))
                        rec["opposed_rs900_usd"] = float(np.nansum((sgn * f_qty * (m900 - f_px))[~al]))
                        rows.append(rec)
                        if lat_name == "base" and qmodel == 0:
                            # 5-minute marked-to-mid P&L path (cash + inventory), for intraday risk
                            k = np.searchsorted(f_t, minutes, side="right")
                            cum_cash = np.r_[0.0, np.cumsum(-sgn * notional)]
                            cum_q = np.r_[0.0, np.cumsum(sgn * f_qty)]
                            path = cum_cash[k] + cum_q[k] * m_min
                            paths.append(pd.DataFrame({"day": day, "coin": c, "size": size_name, "mode": mode,
                                                       "minute": np.arange(1, 1441), "pnl": path}).iloc[4::5])
        print(f"{day} {c}: done", flush=True)
    out = os.path.join(ROOT, "reports", "maker", "raw")
    os.makedirs(out, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(out, f"{day}.csv"), index=False)
    pd.concat(paths).to_csv(os.path.join(out, f"{day}_paths.csv.gz"), index=False)
    print(f"{day}: wrote {len(rows)} rows", flush=True)


if __name__ == "__main__":
    mode, day = sys.argv[1], sys.argv[2]
    coins = sys.argv[3].split(",") if len(sys.argv) > 3 else COINS
    probe(day, coins) if mode == "probe" else run(day, coins)
