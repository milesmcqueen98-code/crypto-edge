"""Shared periods, data loaders, statistics and backtest engines for the Medallion round.

Rules come from reports/medallion_prereg.md. Conventions:
- Daily bar d is the Coinbase UTC day d (closes 00:00 UTC on d+1). A signal on row d is known at that close and
  trades day d+1. Weights W[d] are decided at the close of d and earn the return of d+1.
- Hourly bar ts starts at ts and closes at ts+1h. Positions P[ts] are set at the close of bar ts and earn bar ts+1.
- Returns are in excess of T-bills on the perp convention used in earlier rounds (edge/intraday.py): position P&L
  minus funding paid by longs, minus per-side cost on every unit traded, minus T-bills lost on the 20% margin share.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from edge import book  # noqa: E402

ALT = os.path.join(ROOT, "data", "alt")
OUT = os.path.join(ROOT, "reports", "medallion")
DEV = ("2020-01-01", "2023-12-31")
HOLD = ("2024-01-01", "2026-11-05")
DEV_H = ("2017-07-01", "2023-12-31")          # hourly families
COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC", "BCH", "DOT", "XLM", "HBAR", "SUI", "NEAR",
         "AAVE", "ENA", "ONDO", "BNB", "ZEC"]
HOURLY = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "LTC"]
MARGIN_SHARE = 0.20
TARGET = 0.25
N_PRIOR = 484
N_BOOKS = 19                                  # 17 registered + 2 strict short-vol ladders (F9L)
HOLDOUT_OPEN = os.environ.get("MEDALLION_HOLDOUT") == "1"     # hold-out results are computed only when set


# ------------------------------------------------------------------------------------------------ costs and funding
def cost_per_side(coin):
    if coin == "BTC":
        return 2.5e-4
    if coin == "ETH":
        return 6.5e-4
    t = pd.read_csv(os.path.join(ROOT, "reports", "lab", "cost_table.csv")).set_index("coin")
    if coin in t.index:
        return float(t.loc[coin, "fee_bp_side"] + t.loc[coin, "half_spread_bp"]) / 1e4
    return 15e-4


def binance_funding_raw(coin):
    p = os.path.join(ALT, "binance", f"funding_{coin}.parquet")
    if not os.path.exists(p):
        return None
    f = pd.read_parquet(p)
    return f.set_index("ts")["funding"].astype(float).sort_index()


def funding_daily(coins, index):
    """Daily funding paid by a long (fraction of notional per day): Binance USD-M (sum of the day's prints) where
    available, else Hyperliquid (data/funding), else 8% a year."""
    out = {}
    hl = {}
    for p in glob.glob(os.path.join(ROOT, "data", "funding", "*.csv")):
        d = pd.read_csv(p, parse_dates=["date"]).set_index("date")["funding_daily"]
        hl[os.path.basename(p)[:-4]] = d
    for c in coins:
        s = pd.Series(np.nan, index=index)
        f = binance_funding_raw(c)
        if f is not None:                       # a position held over day d pays the prints in (00:00 d, 00:00 d+1]
            s = f.groupby((f.index - pd.Timedelta(hours=1)).floor("D")).sum().reindex(index)
        if c in hl:
            s = s.fillna(hl[c].reindex(index))
        out[c] = s.fillna(0.08 / 365)
    return pd.DataFrame(out, index=index)


# ------------------------------------------------------------------------------------------------ prices
def daily_close(coins=COINS, field="close"):
    out = {}
    for c in coins:
        p = os.path.join(ROOT, "data", "prices", f"{c}.csv")
        if os.path.exists(p):
            d = pd.read_csv(p, parse_dates=["date"]).drop_duplicates("date").set_index("date").sort_index()
            out[c] = d[field].astype(float)
    df = pd.DataFrame(out)
    return df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="D"))


def hourly_close(coins=HOURLY):
    frames = {}
    for c in coins:
        d = pd.read_csv(os.path.join(ROOT, "data", "hourly", f"{c}.csv.gz"), parse_dates=["ts"])
        frames[c] = d.drop_duplicates("ts").set_index("ts").sort_index()["close"]
    idx = pd.date_range(min(s.index.min() for s in frames.values()), max(s.index.max() for s in frames.values()),
                        freq="h")
    close = pd.DataFrame({c: s.reindex(idx) for c, s in frames.items()}).ffill(limit=6)
    for c, s in frames.items():
        close.loc[: s.index.min() - pd.Timedelta(hours=1), c] = np.nan
    return close


# ------------------------------------------------------------------------------------------------ statistics
def rz(x, win=365, minp=90):
    """Rolling z-score using data up to and including each row."""
    m = x.rolling(win, min_periods=minp).mean()
    s = x.rolling(win, min_periods=minp).std()
    return (x - m) / s.replace(0, np.nan)


def nw_t(u, lags):
    u = np.asarray(u, float)
    u = u[~np.isnan(u)]
    T = len(u)
    if T < 30:
        return np.nan, np.nan, T
    m = u.mean()
    e = u - m
    s = (e @ e) / T
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * (e[L:] @ e[:-L]) / T
    return m, m / np.sqrt(s / T), T


def ic_nw(sig, fwd, start, end, lags):
    """Rank IC (mean product of standardized ranks ~ Spearman) and its Newey-West t-stat over [start, end]."""
    d = pd.concat([sig, fwd], axis=1).loc[start:end].dropna()
    if len(d) < 60:
        return dict(ic=np.nan, t=np.nan, n=len(d))
    a = d.iloc[:, 0].rank()
    b = d.iloc[:, 1].rank()
    a = (a - a.mean()) / a.std()
    b = (b - b.mean()) / b.std()
    m, t, n = nw_t((a * b).to_numpy(), lags)
    return dict(ic=m, t=t, n=n)


def sharpe(x, start=None, end=None):
    return book.sharpe(x, start, end)


def stats(name, x, extra=None, dev=DEV, active_from=None):
    """Development window starts at the later of its first day and the book's first trading day (the pre-registered
    'from first data where later')."""
    x = x.dropna()
    if not HOLDOUT_OPEN:
        x = x.loc[:dev[1]]
    if active_from is not None and pd.Timestamp(active_from) > pd.Timestamp(dev[0]):
        dev = (str(pd.Timestamp(active_from).date()), dev[1])
    row = dict(book=name, sharpe_dev=sharpe(x, *dev), sharpe_hold=sharpe(x, *HOLD) if HOLDOUT_OPEN else np.nan,
               start=str(x.index.min().date()) if len(x) else "", dev_from=dev[0])
    for lab, (s, e) in (("dev", dev), ("hold", HOLD)):
        xx = x.loc[s:e]
        if len(xx) > 60:
            m, t, _ = nw_t(xx.to_numpy(), 5)
            row[f"t_{lab}"] = t
            st = book.summary(xx)
            row[f"cagr_{lab}"], row[f"maxdd_{lab}"] = st["cagr"], st["maxdd"]
            row[f"vol_{lab}"] = float(xx.std() * np.sqrt(365))
    row["passes"] = bool(row["sharpe_dev"] >= 1.0 and row["sharpe_hold"] >= 0.5) if not np.isnan(
        row["sharpe_dev"]) and not np.isnan(row["sharpe_hold"]) else False
    if extra:
        row.update(extra)
    return row


# ------------------------------------------------------------------------------------------------ engines
def run_daily(W, close, funding=None, cost=None):
    """W[d]: weights (fraction of capital, +long/-short) decided at the close of d, held over d+1."""
    cols = list(W.columns)
    W = W.reindex(close.index).fillna(0.0)
    r = close[cols].pct_change(fill_method=None).fillna(0.0)
    if funding is None:
        funding = funding_daily(cols, close.index)
    if cost is None:
        cost = {c: cost_per_side(c) for c in cols}
    held = W.shift(1).fillna(0.0)
    pnl = (held * r).sum(axis=1) - (held * funding[cols].reindex(close.index).fillna(0.08 / 365)).sum(axis=1)
    traded = W.diff().abs()
    traded.iloc[0] = W.iloc[0].abs()
    tc = (traded * pd.Series(cost)).sum(axis=1)
    rf = book.rf_daily(close.index)
    margin = MARGIN_SHARE * (held.abs().sum(axis=1) > 0).astype(float)
    ex = pnl - tc - margin * rf
    turnover = traded.sum(axis=1)
    return ex, turnover


def run_hourly(P, close_h, funding_d=None, cost=None):
    """P[ts]: positions set at the close of hourly bar ts, held over bar ts+1. Returns daily excess returns."""
    cols = list(P.columns)
    P = P.reindex(close_h.index).fillna(0.0)
    r = close_h[cols].pct_change(fill_method=None).fillna(0.0)
    day = close_h.index.floor("D")
    if funding_d is None:
        funding_d = funding_daily(cols, pd.DatetimeIndex(day.unique()))
    fh = pd.DataFrame({c: day.map(funding_d[c]).to_numpy() / 24.0 for c in cols}, index=close_h.index).fillna(
        0.08 / 365 / 24)
    if cost is None:
        cost = {c: cost_per_side(c) for c in cols}
    held = P.shift(1).fillna(0.0)
    pnl = (held * r).sum(axis=1) - (held * fh).sum(axis=1)
    traded = P.diff().abs().fillna(0.0)
    tc = (traded * pd.Series(cost)).sum(axis=1)
    rf_day = book.rf_daily(pd.DatetimeIndex(day.unique()))
    rf_h = pd.Series(day.map(rf_day).to_numpy(), index=close_h.index) / 24.0
    margin = MARGIN_SHARE * (held.abs().sum(axis=1) > 0).astype(float)
    ex = pnl - tc - margin * rf_h
    return ex.groupby(day).sum(), traded.sum(axis=1).groupby(day).sum()


def vol_unit(close, target=TARGET):
    """Position per coin that targets `target` annualized vol (Carver blend, floored at 10% vol)."""
    r = close.pct_change(fill_method=None)
    return target / book.carver_vol(r)


def require_holdout():
    if not HOLDOUT_OPEN:
        sys.exit("this step reads the hold-out; run with MEDALLION_HOLDOUT=1")


def active_from(turnover, x):
    t = turnover[turnover > 0]
    return t.index[0] if len(t) else x.first_valid_index()


def save(df, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    if name.endswith(".csv"):
        df.to_csv(path, index=False, float_format="%.6g")
    else:
        df.to_parquet(path)
    return path
