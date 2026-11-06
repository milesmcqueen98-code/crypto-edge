# Maker round: pre-registration

Committed 2026-11-06, before any tick-data result exists. Nothing below may change after
the first simulation output is produced; deviations get logged at the bottom with a reason.

## Question

Can the 1–15 minute cross-sectional reversal (gross edge about 0.2 bp per trade, smaller than
the spread) be harvested as a maker on Coinbase: two-sided post-only quotes on liquid coins,
skewed by the signal and by inventory? Book: $10K, capacity test at $100K.
Targets: net Sharpe ≥ 2.4 above T-bills, no losing year.

## Venue facts fixed before testing

- Coinbase spot, US, maker / taker by trailing 30-day volume (post 16 Sep 2026 schedule):
  Intro $0+ 0.50% / 0.90%; Advanced 1 $10K+ 0.35% / 0.75%; Advanced 2 $50K+ 0.15% / 0.30%;
  Advanced 3 $250K+ 0.10% / 0.15%; VIP 1 $500K+ 0.06% / 0.125%; VIP 5 $20M+ 0.01% / 0.05%;
  VIP 6 $50M+ 0.00% / 0.035%; VIP 8 $250M+ 0.00% / 0.02%. Unlisted tiers (VIP 2–4, VIP 7) are
  charged at the next-lower listed tier (conservative). Tiers update hourly on trailing volume.
- Coinbase US perps (Coinbase Derivatives nano perp-style futures, available in all 50 states):
  exchange fee $0.10 per contract per side for makers and takers alike ($0.07 with a signed
  market-maker agreement), plus clearing, NFA and FCM charges. BTC contract 0.01 BTC, tick $5
  per BTC (0.66 bp at $76K); ETH contract 0.1 ETH (about $223). Tardis has no Coinbase
  Derivatives order-book history, so perps are judged by an arithmetic bound (H-perp below).
- Coinbase Advanced REST limit: 30 requests per second.
- Tick sizes (Coinbase spot, bp at 6 Nov 2026 prices): BTC $0.01 (0.001), ETH $0.01 (0.04),
  SOL $0.01 (1.1), XRP $0.0001 (0.8), DOGE $0.00001 (1.4).

## Data

- Tardis.dev free first-day-of-month Coinbase Exchange files: `quotes` (top of book with sizes,
  one row per top-of-book change) and `trades` (taker side, price, size), exchange timestamps
  in microseconds.
- Coins: BTC-USD, ETH-USD, SOL-USD, XRP-USD, DOGE-USD (the five where the 15-minute reversal
  survived a 10-minute delay in the minute test).
- Days: 1st of each month, 2024-01-01 to 2026-11-01 (35 days).
  - Development: 2024-01-01 to 2025-06-01 (18 days).
  - Hold-out: 2025-07-01 to 2026-11-01 (17 days). Run once, after the dev choice is committed.
- Signal coefficients come only from 1-minute Coinbase closes, 2024-01-01 to 2025-06-30.
- Raw tick files stay on the CI runner; only derived results are committed.

## Signal

- Mid m_i on a 1-second grid. r_i = ln m_i(t) − ln m_i(t − 15 min); u_i = r_i − mean_j r_j.
- Expected 15-minute relative return E_i = −β · u_i (bp). β: pooled OLS of the forward
  15-minute relative log return on u_i, 1-minute closes, dev window above. E_ref = 80th
  percentile of |E_i| in the same sample.
- Decisions at time t see mids as of t − (market-data latency).

## Simulator rules

1. Events ordered by exchange timestamp; at equal timestamps trades come before quote updates.
2. Our orders are post-only limits that join the best bid / best ask we observe. No price
   improvement inside the spread.
3. Latency: we see market events `lat_md` after they happen; our orders and cancels reach the
   book `lat_ord` after we send them. Fills before a cancel lands still count.
4. Decision triggers: every observed top-of-book change and every 1-second signal update.
   Each side can be re-sent at most once per 100 ms.
5. On arrival: an order that would cross the true opposite best is rejected (post-only). At the
   true best price, queue ahead A = displayed size. Better than the true best (level vanished),
   A = 0. Worse than the true best, A = last size we saw at that price.
6. Queue model, base ("risk-averse"): A falls only with trades at our price on our side, and is
   capped at the displayed size when our price is the best. Sensitivity ("proportional"):
   size drops not explained by trades count as cancels spread evenly through the queue.
7. Fills: a trade at our price on our side fills max(0, size − A); a trade through our price
   fills min(remaining, size); if the opposite best reaches our price we fill in full.
   All fills at our limit price.
8. Inventory: per coin, ±Q_max notional. Order size = min(quote size, room to the limit);
   below $50 the side is not quoted.
9. Accounting: positions marked to mid. Gross P&L (zero fees) and traded notional are stored,
   so any fee schedule can be applied afterwards. End-of-day inventory is flattened as a taker
   (half spread + taker fee). Daily excess return = P&L / capital − T-bill rate.

## Strategies (the only selection trials: 3)

- **S0 symmetric**: target q* = 0. Quote both sides unless at the inventory limit.
- **S1 skewed**: q* = Q_max · clip(E/E_ref, −1, 1). Bid while q < q* + Q_max/2; ask while
  q > q* − Q_max/2.
- **S2 passive tracker**: same q*. Bid only while q < q* − Q_max/10; ask only while
  q > q* + Q_max/10 (passive execution of the reversal portfolio).
- $10K book: quote size $1,000, Q_max $2,000 per coin. $100K book: ×10.

## Scenarios (sensitivity, not selection)

| Name | lat_md | lat_ord |
|---|---|---|
| colo (not reachable at retail; upper bound) | 1 ms | 2 ms |
| base (cloud VM near Coinbase, REST orders) | 10 ms | 50 ms |
| stress (2×) | 20 ms | 100 ms |

Queue: risk-averse (base) and proportional. Fees: 0% (VIP 6+), the tier the strategy's own
volume reaches, and break-even. Markouts of every fill at 1 s, 10 s, 60 s, 5 min and 15 min.

## Selection, metrics, pass bars

- Selection: highest dev Sharpe among S0–S2 at base latency, risk-averse queue, 0% maker fee
  (the most generous fee). Only that strategy goes to the hold-out.
- Sharpe: mean / sd of daily excess returns × √365. t = mean / sd × √N (daily, N days).
- Deflated Sharpe: N = 473 trials (about 470 in earlier rounds + 3 here); trial-Sharpe variance
  from this round's 18 strategy × scenario runs.
- **Adopt** only if, on the hold-out at base latency, risk-averse queue and the attainable fee
  tier: t ≥ 3; deflated Sharpe ≥ 0.95; net Sharpe ≥ 2.4; every calendar year's sampled-day
  P&L > 0; Sharpe ≥ 2.4 at $100K; and still profitable with fees ×2 and latency ×2.
- **Paper-trade** if t ≥ 3 and no losing year hold at the attainable tier but another bar fails.
- **Reject** otherwise, and in any case if the hold-out gross (0% fee) t < 3.
- Power note: with 35 sampled days, t ≥ 3 requires a realized Sharpe near 10. A true 2.4 Sharpe
  needs about 570 trading days of tick data to reach t = 3.

## Fee climb

From the hold-out's average daily traded notional V at $10K: simulate 90 days from the Intro
tier, tier set by trailing 30-day volume, daily P&L = gross − fees − exit costs. Report days to
reach VIP 6 ($50M) and the equity path. If 30 × V < $50M, 0% maker is unreachable.

## H-perp (arithmetic bound, no simulation)

Reject perps market making if the most a maker can earn per fill (half the quoted spread +
0.2 bp signal edge) is below the all-in maker cost per side ($0.10 exchange fee alone is
1.3 bp on nano BTC, 4.5 bp on nano ETH).

## If nothing passes: C3 improvement (pre-registered, 3 trials)

C3 = risk parity of the live rule (41%) and hourly EWMAC long/short (59%) on Coinbase perps.
Dev 2019-11-06 to 2023-12-31; hold-outs 2024-01-01+ and 2017-07-01 to 2019-11-05.

- C3-B: hourly EWMAC buffer width 0.25 × unit (now 0.10).
- C3-F: drop the fastest EWMAC speed (4/16 h); forecast re-scaled over the remaining 5.
- C3-BF: both.
- Costs: (a) 0.04% per side (earlier assumption); (b) realistic nano-perp cost per side:
  BTC 2.5 bp, ETH 6.5 bp (exchange fee + clearing/NFA/commission + half a tick), positions
  rounded to whole contracts at $10K; (c) 2× of (b).
- A variant replaces C3 only if its dev Sharpe at cost (b) beats C3, and it is not worse than C3
  on both hold-outs. Same t ≥ 3 / deflated-Sharpe ≥ 0.95 bars for adoption (N = 476).

## Deviation log

- 2026-11-06, after the hold-out ran (verdict already fixed: reject). An independent review found no bug that
  flips the sign, but flagged two rules that bias results against the strategy: (1) orders chase every move of
  the touch and re-send on small size drift, losing queue place; (2) crossings fill our full remaining size.
  It also found the signal-alignment split confounded (E at the fill second includes the move that filled us).
  Added a robustness run (`maker_day.py sens`): crossing fills capped at the displayed size, and "sticky" quotes
  that keep queue place within 0.5 or 2 bp of the touch; alignment measured with E 60 s before the fill.
  S0 and S2, $10K, risk-averse queue, base and colo latency, all 35 days. Not a selection trial; it cannot
  change the verdict to adopt. It adds 6 variants to the trial count.
