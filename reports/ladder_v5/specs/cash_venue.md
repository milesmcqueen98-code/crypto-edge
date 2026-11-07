# Builder spec: USDC cash (C4) and the perp venue (C5) — branch ladder/cashvenue

Read BUILDER_GUIDE.md and reports/ladder_v5_prereg.md first. Two pre-registered trials, logged in this order with
`gates.run` under these names: C4_usdc, C5_perp_venue, path "return".

## C4: the bot's cash held as USDC, earning Coinbase One USDC rewards
- Facts already checked (reports/ladder_v5/probe_usdc.json, Nov 7): all 17 coins have a -USDC product on Advanced
  Trade whose `alias` is the -USD book (one order book). Coinbase pays USDC rewards to Coinbase One members (3.5% from
  Dec 15 2025 per DL News; 3.75% per an Oct 23 2026 commentary). Unverified: whether USDC on hold for resting orders and
  in a separate portfolio earns rewards, New York eligibility, and the rules after the OCC's GENIUS Act rule (effective
  Jan 18 2027).
- Daily return added to the incumbent's (scenario A, the trial): r_usdc(t)/365 x (1 - positions_t / C), where
  positions_t is the day's average of the live book's open positions at cost (fill to take-profit or 60-minute exit,
  from hsim.book's instant-bound Q), and r_usdc(t) = max(0, T-bill rate(t) - 0.5%) (edge.book.rf_daily gives the daily
  T-bill rate). The reward rate is unverified, so in S* it is halved; in base it is not.
- USDC/USD mark-to-market on the USDC balance: daily close-to-close change of Bitstamp's usdcusd
  (data/ladder_v5/usdc_usd_bitstamp.csv covers 2022-01-01 .. 2024-09-26; fetch 2024-09-26 .. 2026-11-05 on Actions
  from https://www.bitstamp.net/api/v2/ohlc/usdcusd/?step=86400 with a plain research User-Agent; if refused, report it
  and use 1.0 for missing days). This includes the March 2023 depeg (low 0.805 on Mar 11).
- Post hoc sensitivity (not a trial): scenario B, rewards only on USDC not held for resting bids (compute the 4-sigma
  holds for every minute from the panel the way hsim allocates them, plus deeper holds from hsim if you can; say how).
- Report the cost of Coinbase One against the reward ($/year) and the depeg day in dollars at $250K.

## C5: the same bids on the coin's Coinbase US perp as well (seed from the brief)
- Restore the perp venue's fill and take-profit capacity: in_perp = in_perp_raw, tp_perp = tp_perp_raw (fsim.load keeps
  the raw columns). fsim.evaluate then splits each signal's size across spot and perp by capacity, as the research
  simulator did.
- Perp costs (sim.perp_cost(): per-contract fee in bp of today's contract value per coin, and 1.5x the measured
  half-spread) are unverified: doubled in S*. fsim's evaluate has no hook for that: implement it in your book_fn by
  scaling the perp fee and half-spread inputs (patch sim.perp_cost inside your process only; do not edit sim.py).
- The live cash rule: perp bids also hold the signal's cash in hsim (no margin credit: conservative).
- Perps listed mid-2025, so 2022-23 has no perp capacity: the difference there is exactly zero and G2 fails by
  construction. Pre-registered: C5 can be at most "forward-test".

## Report
reports/ladder_v5/cashvenue/REPORT.md: the off-switch checks (rate 0 and no depeg reproduce the incumbent exactly;
perp capacity 0 reproduces the incumbent exactly), gate tables, the depeg day, the perp share of fills by era.
