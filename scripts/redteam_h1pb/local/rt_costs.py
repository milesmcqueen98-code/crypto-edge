"""Red-team cost model, written from the pre-registration text (not book.py): per-contract fee per side (maker or taker),
time exits pay 1.5x the measured median half-spread (cfm_book_summary.csv), funding 1 bp per 8 h on contract-hours at
the entry price; every term x mult."""
import pandas as pd, numpy as np
CS = {"BTC": 0.01, "ETH": 0.1, "SOL": 5, "XRP": 500, "DOGE": 5000, "LTC": 5, "AVAX": 10, "LINK": 50, "ADA": 1000, "BCH": 1,
      "SUI": 500, "XLM": 5000, "HBAR": 5000, "NEAR": 500, "AAVE": 5, "HYPE": 10, "ENA": 5000, "PEPE": 1e8, "ONDO": 1000,
      "ZEC": 1, "DOT": 100, "SHIB": 1e7, "BNB": 1}
_b = pd.read_csv('/home/claude/crypto-edge/reports/cfm_book_summary.csv')
HS = {r.root: r.spread_bp_median / 2 for r in _b[_b.kind == 'perp'].itertuples()}

def trade_costs(T, fee=0.20, mult=2.0, hs_mult=1.5, fund_bp_8h=1.0):
    n = T.n.to_numpy(float); tpn = T.tpn.to_numpy(float); rem = n - tpn
    fee_usd = (n + tpn + rem) * fee * mult
    hs = np.array([HS.get(c, 5.0) for c in T.coin]) * hs_mult * mult
    spread_usd = T.remnot.to_numpy(float) * hs / 1e4
    cs = np.array([CS[c] for c in T.coin])
    fund_usd = T.chours.to_numpy(float) * cs * T.L.to_numpy(float) * fund_bp_8h / 8.0 * mult / 1e4
    return fee_usd, spread_usd, fund_usd

def daily(T, net, days, capital):
    d = pd.to_datetime(np.asarray(T.t_close, dtype='int64')).floor('D')
    s = pd.Series(np.asarray(net), index=d).groupby(level=0).sum()
    return s.reindex(pd.DatetimeIndex(days)).fillna(0.0) / capital
