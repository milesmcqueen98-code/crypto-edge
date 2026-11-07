# H12 (LT): R2-08's wick catcher on Coinbase's long-tail spot coins (loop 3)

Fixed before any build of this idea. Same pre-registration (reports/hunt_prereg.md) and gates. Read
reports/hunt/BUILDER_GUIDE.md first.

## Why this idea now
- **Mechanism:** the incumbent's, the only one this lab has seen survive out of sample. Forced and impatient sellers
  sweep thin books; a resting, AI-filtered bid supplies the missing liquidity and is paid by the snap-back.
- **What is new:** the coins. The incumbent trades 17 coins (13 in 2022–23). The lab's wider 31-coin set (those 17
  plus 14 with a 2024 median daily Coinbase volume of at least $3M and a spot tick of at most 3 bp) was tested in wick
  v4 and not adopted. H12 goes below that set's $3M floor, where books are thinner and a fund cannot fit; a $30K
  sleeve can.
- **The question Path B asks:** do long-tail wicks add alpha the incumbent does not already earn? Some fall on the same
  cascade days (beta to the incumbent); coin-specific wicks would be new.
- **Prior:** 4 of 10 (ideas.md #12). Same mechanism, so a positive DEV result is likely; the open questions are
  correlation with the incumbent and fill realism in thin books.

## Universe (fixed from 2024 data, before any P&L)
- Every Coinbase USD spot pair that traded in 2024, **including pairs delisted since**, that:
  - has a 2024 median daily Coinbase USD volume of at least $0.5M and below $3M (from daily candles);
  - has a spot tick of at most 3 bp of its H2-2024 price (`est_tick` in scripts/wick1m/trades_wide.py);
  - is not one of the wide set's 31 coins (reports/wick1m/trades_wide.parquet; the incumbent's 17 are among them);
  - is not a stablecoin, fiat-backed, wrapped or pegged asset (USDT, DAI, PYUSD, USDS, GUSD, EURC, cbBTC, cbETH, wBTC,
    PAXG, LSETH, etc.).
- Write the list with its 2024 volume and tick to reports/hunt/h12lt/universe.csv and commit it before any simulation.
- If more than 80 coins qualify, keep the 80 with the highest 2024 volume (memory); report how many were dropped.

## Data
- Coinbase spot 1-minute candles, 2024-01-01 → 2026-11-05, for every universe coin. Use scripts/fetch_minute.py on
  Actions, sharded across parallel runs. Write to data/hunt/h12lt/minute/<COIN>.parquet on your branch.
- The wide set's 31 coins and BTC/ETH: data/minute (read-only, main clone).
- Early-era (2022–23) data is **not** fetched. The sleeve is zero on 2022–23, so its scored days are
  gates.ERA_DAYS from 2025-01-01 (2024 trains the model).
  - DEV = 2025-01-01 → 2026-05-31. HOLD = 2026-06-01 → 2026-11-05.

## Signal (R2-08 unchanged)
- Run "R2-08 C29+A11" exactly as scripts/wick1m/trades_wide.py does: levels, features, walk-forward LightGBM by
  quarter, 60th-percentile threshold, exits, the VIP1 cost label.
- **Model pool:** the wide set's 31 coins plus the universe, pooled, as the wide run pooled its 31.
  - If that does not fit in a 16 GB runner, pool the 17 base coins (core.COINS17) plus the universe and say so.
- **Reference factor:** keep R2-08's reference exactly as for the incumbent (BTC, 7-day beta). If any feature uses an
  equal-weight basket, the basket stays the wide set's coins, so adding coins does not change it.
- **The sleeve trades universe coins only.** The incumbent's own trades (17 coins) are unchanged and not part of the
  sleeve.

## Execution and sizing (the incumbent's rules)
- scripts/wick1m/sim.py precompute and evaluate on the sleeve's trade list, Coinbase spot only (perp capacity set to 0,
  as scripts/hunt/incumbent.py does).
- Ladder 4/6/8σ in thirds. Each signal is capped at κ = 0.2% of the coin's trailing 30-day median daily USD volume.
  Cash ≤ 100% of sleeve capital.
- Fill: one-tick trade-through on the coin's own tick. Size ≤ θ × through-volume, θ = 0.5 (0.25 also reported).
- Capital: $30K and $50K.
- **Costs:** the hunt model's spot rates, 6 bp maker, 12.5 bp taker and 2 bp half-spread on market exits, at 2× for
  the gates. The sleeve shares the account's fee tier.
  - Also report the gates at 2× with a 5 bp half-spread, since long-tail books are wide. Measure the realised
    half-spread on the print sample.

## Trial grid (≤ 6, all logged with gates.dev_book)
1. **Base:** the universe as defined, incumbent rules.
2. **Volume floor $1M:** the base trade list restricted to coins with a 2024 median volume ≥ $1M.
3. **Stricter AI filter:** base, keeping signals whose prediction is at or above the 70th percentile of that
   quarter's training predictions (re-thresholded from the stored predictions; no re-training).
4. **No ladder:** base, 4σ parent only.
5. **κ = 0.1%:** base with half the volume cap.

- **Selection:** the highest DEV alpha t with at least 100 trades; ties go to the simpler variant.

## Checks to report
- Universe size and how many coins traded. Fills and net bp by year, coin and 2024 volume tier.
- Candle-vs-print confirmation on a random sample of at least 200 DEV fills (common.TradeFetcher on Actions), with the
  realised through-volume and half-spread.
- Correlation with the incumbent, same-day overlap and the result on the incumbent's 10 worst days.
- Top-3 days' share of P&L.
- Delisted coins: how many, and their P&L.
