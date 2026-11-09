#!/usr/bin/env python3
"""Edge hunt 2: the cost model for Path B sleeves (reports/hunt2_prereg.md, "Cost model").

Spot (unchanged from the first hunt, scripts/hunt/common.py): Coinbase Advanced VIP 1, 0.06% maker / 0.125% taker,
plus a 2 bp half-spread on market orders.

Perps (CFM), from the documented fee structure (research memo R4, Nov 8 2026): a flat $0.15 per contract per side
(exchange $0.10 + NFA $0.01 + clearing ~$0.04) plus Coinbase's commission, taken as 2 bp per side for maker and taker
alike (launch pricing "from 0.02%"; the retail tier is unverified, so the maker discount is not assumed). Market
orders also pay 1.5x the measured median half-spread (reports/cfm_book_summary.csv). Funding: 1 bp per 8 hours,
charged either side. 2x doubles every term. A contract must be worth >= $150 (the first hunt's rule).

Compared with the first hunt's $0.20 per contract: BTC 4.0 vs 2.7 bp per side, ETH 9.1 vs 9.4, SOL 5.5 vs 4.6.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common as C  # noqa: E402

PERP_FLAT_USD = 0.15
PERP_COMMISSION_BP = 2.0
PERP_HS_MULT = 1.5
PERP_FUND_BP_PER_8H = 1.0
PERP = C.PERP
contract_ok = C.contract_ok
usd_per_coin = C.usd_per_coin
spot_cost_bp = C.spot_cost_bp
load_minute = C.load_minute
load_perp = C.load_perp
_HS = None


def perp_half_spread_bp(coin):
    global _HS
    if _HS is None:
        _HS = C.perp_half_spread_bp()
    return _HS.get(coin, 5.0)


def perp_cost_bp(coin, price, taker=False, mult=1.0):
    """One side of a perp trade in bp of notional at `price` (USD per coin, or the venue's quote for PEPE)."""
    px = usd_per_coin(coin, price)
    notional = px * PERP[coin][1]
    flat = PERP_FLAT_USD / notional * 1e4
    hs = PERP_HS_MULT * perp_half_spread_bp(coin) if taker else 0.0
    return mult * (flat + PERP_COMMISSION_BP + hs)


def perp_funding_bp(hours, mult=1.0):
    return mult * PERP_FUND_BP_PER_8H * hours / 8.0


if __name__ == "__main__":
    for coin, px in (("BTC", 74700), ("ETH", 2120), ("SOL", 86.4), ("XRP", 1.112)):
        print(coin, "maker", round(perp_cost_bp(coin, px), 2), "taker", round(perp_cost_bp(coin, px, True), 2),
              "taker 2x", round(perp_cost_bp(coin, px, True, 2.0), 2))
