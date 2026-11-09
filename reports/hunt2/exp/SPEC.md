# EXP: the Deribit Friday expiry unwind (dealer hedges come off during the 08:00 UTC settlement window)

- **Path:** B (a sleeve on Coinbase US perps: BTC, ETH).
- **Who is forced or eager, and why we are paid:** Deribit options settle at 08:00 UTC to a 30-minute TWAP of its
  index (Coinbase is a constituent), and the deltas of expiring options fall linearly to zero across the window. Dealers
  who hedged those options must unwind the hedges inside the window, in a direction and size known in advance from
  their inventory: if the expiring options left dealers net long delta they are short the underlying as a hedge and
  must buy it back, and vice versa. That is one-sided, price-insensitive, scheduled flow (SIG's "who needs the
  print"). A follower trades with the predicted unwind during the window; a liquidity provider fades what is left of
  its impact after 08:00.
- **Prior evidence and what has been seen:** the Medallion round's hour-of-week seasonality (no event conditioning)
  failed after costs; Deribit pinning was blocked for lack of open-interest history in the first hunt. Memo R2 (G3,
  prior 3): the open-interest block is gone (dealer inventory from Deribit's free trade history). Nothing computed on
  any era.
- **Data:** Deribit BTC and ETH option trades from 2021 (history.deribit.com, shared with GAMMA), giving each Friday's
  dealer net delta of the options expiring that morning, measured at 07:29 UTC (D, in coins); Coinbase 1-minute
  candles 2022–2026 (spot-priced with perp costs before the CFM perps launched in Jul 2025; perp candles after);
  Coinbase prints around DEV events to check fills.
- **Live inputs and orders:** Deribit public data (read only, via Coinbase-hosted endpoints); market (IOC limit)
  orders on CFM perps.
- **Rule (frozen grid, 12 trials):** for each Friday expiry, the predicted unwind flow is F = +D (dealers net long
  delta of expiring options buy back their short hedges → buy pressure), sized relative to the asset's average 30-
  minute Coinbase volume. If |F| ≥ the DEV median of |F| (BTC and ETH separately):
  - with: enter sign(F) at 07:30 (taker), exit at 08:00 (taker);
  - fade: enter −sign(F) at 08:01, exit at 09:00;
  - window fade without inventory (control): if |r(07:30→08:00)| ≥ 1 σ of 30-minute returns, enter −sign(r) at 08:01,
    exit at 09:00.
  Grid: rule ∈ {with, fade, window fade} × event set ∈ {all Fridays, monthly + quarterly} × assets ∈ {BTC, BTC+ETH}.
- **HOLD protection:** no signal, trade or return on HOLD days is computed before the freeze commit; data fetches
  may cover HOLD dates.
- **Size:** notional per event = 1.0 × sleeve capital split across assets (gross ≤ 2×), whole contracts.
- **Costs:** scripts/hunt2/costs.py perps at 2× (1× reported).
- **Selection statistic:** highest DEV alpha t with ≥ 20 events (all Fridays) or ≥ 8 (monthly + quarterly); ties →
  monthly + quarterly, BTC only.
- **Capital:** $25K/$50K/$75K/$125K. **Outputs:** reports/hunt2/exp/.
- **If Deribit history is unreachable from the runners**, only the window-fade control can be built; it is then built
  alone (4 trials) and reported as such.
