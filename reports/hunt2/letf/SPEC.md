# LETF: leveraged-ETF rebalancing flow into the US close

- **Path:** B (a sleeve on Coinbase US perps beside the incumbent).
- **Who is forced or eager, and why we are paid:** 2x and -2x (and -1x) crypto ETFs (BTC: BITX, BITU, SBIT, BTCL,
  BTCZ; ETH: ETHU, ETHT, ETHD; SOL: SOLT, SLON; XRP: XXRP, UXRP, XRPT) must hold leverage L fixed each day, so they
  must trade AUM x L(L-1) x r in the direction of the day's return r (inverse funds too: L(L-1) > 0), mostly late
  in the US session against their 4 pm ET NAV (the CF Benchmarks New York reference window). The flow is mechanical,
  public in sign and roughly known in size. A fast follower is paid by its price impact (momentum into the close);
  a liquidity provider after the window is paid by the transient part of that impact reverting (Bouchaud et al.:
  impact relaxes after a metaorder ends).
- **Prior evidence and what has been seen:** the creative round found Shen–Urquhart–Wang intraday momentum (UTC
  days) never worked on Coinbase hourly data; that is a different clock and no LETF conditioning. Nothing computed on
  any era for this rule. Leveraged-ETF dollar volume (data/hunt2/etf, inputs only): BTC complex ~$6M/day in 2023,
  $267M in 2024, $661M in 2025; ETH from mid-2024; SOL and XRP from spring 2025. AUM now (memo R4): BITX $989M,
  BITU $462M, ETHU $852M, ETHT $211M, SOLT $136M, XXRP $142M, so a 5% day implies about $145M of BTC and $106M of ETH
  rebalancing (2 x AUM x return); relative to each market's liquidity, ETH's is the largest.
- **Data:** Coinbase spot 1-minute candles (signal and spot-priced fills before each perp launched: BTC/ETH
  2025-07-19, SOL/XRP 2025-08-16); CFM perp 1-minute candles after launch; Coinbase prints around every DEV signal
  window (15:44–17:01 ET) to check entry/exit prices and spreads; ETF daily prices/volumes (Yahoo) for gating.
- **Live inputs and orders:** Coinbase spot/perp prices, the NYSE calendar, ETF volumes (public); market (IOC limit)
  orders on CFM perps.
- **Gate (fixed):** an asset trades on day d only when its 2x/-2x ETF complex's trailing 20-day average dollar volume
  (to day d-1) is >= $50M. US trading days only (NYSE calendar). Monday's r runs from Friday's 4 pm.
- **Rule (frozen grid, 12 trials):** at 15:45 ET, r = ln(P(15:44) / P(previous trading day 16:00)); sigma = 30-day
  daily volatility to the previous close. If |r| >= k x sigma:
  - momentum (taker): enter sign(r) at 15:46, exit at 16:00 (CME settles on 15:59–16:00 ET);
  - reversal (taker): enter -sign(r) at 16:01, exit at 17:00;
  - reversal (maker, liquidity to the rebalancer): at 15:55 rest a post-only order on the side opposite the flow
    (a bid on down days, an offer on up days) 10 bp beyond the 15:54 close; cancel at 16:00 if unfilled; exit at 17:00
    (taker) or earlier on a post-only take-profit at the 15:54 close.
  Grid: k in {1, 2} x leg in {momentum, reversal-taker, reversal-maker} x assets in {BTC only, BTC+ETH+SOL+XRP}.
- **HOLD protection:** no signal, trade or return on HOLD days is computed before the freeze commit; data fetches
  may cover HOLD dates.
- **Size:** each signal's notional = 1.0 x sleeve capital / (number of assets signalling that day), whole contracts;
  gross <= 2x sleeve capital.
- **Costs:** scripts/hunt2/costs.py perps at 2x ($0.15 per contract + 2 bp commission + 1.5x measured half-spread
  per side, funding 1 bp per 8 h); 1x reported. Contracts must be worth >= $150.
- **Fills:** taker at the open of the decision minute + 1 (candles), made worse by 1.5x the half-spread; checked
  against prints (first print >= 2 s after the decision) on DEV signal days.
- **Selection statistic:** highest DEV alpha t (h2gates.dev_screen_b) with >= 40 trades; ties -> BTC only, then k = 2.
- **Scored days:** each asset's gated days; the early era is scored only where the gate is open (it opens for BTC
  in 2024, so the early era is effectively a placebo and is reported, not gated, if it has < 10 trades).
- **Capital:** sleeve on $25K/$50K/$75K/$125K. **Outputs:** reports/hunt2/letf/.
