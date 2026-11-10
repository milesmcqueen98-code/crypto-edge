# Candle clock study

Plan: reports/owner/candle_clock_prereg.md. Code: scripts/owner/candle_clock/study.py (runner) and test_study.py
(offline test).

## The answer (run Nov 10 2026, window 12:24 to 18:24 UTC, written 18:47 UTC)

- **By the plan's rules, read strictly: no coin is class A, 6 are B, 12 are C.**
  - B: BTC, ETH, SOL, XRP, LTC, ZEC.
  - C: DOGE, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO.
- **No coin has a steady offset.** Every coin's best single offset is zero (within about 0.03 s). The B coins are B
  only because the "fitted offset" is about zero. So for them, B means "cut at the minute", not "shift the bar".
- **BTC on its own:** every BTC boundary that could be explained was cut exactly at the minute (342 of 342). No BTC
  trade stamped after the mark sat in the earlier candle. The bar cut at the minute had no material error in the last
  three hours. BTC misses class A only because about 5% of boundaries (18 of 360) are unexplained, and those fall at
  venue-wide moments (below). ETH and XRP are the same. SOL is the same but for one late boundary (about 9 s).
- **If unexplained boundaries are left out** (the looser reading of class A), BTC, ETH, SOL and XRP are A; LTC and ZEC
  stay B; the 12 others stay C. The strict reading was fixed before the data; both are shown so the reader can choose.
- **The cut on the C coins is not steady and not random noise around a shift.** It is at the minute most of the time,
  but in about 8% to 41% of boundaries the candle runs late: it takes trades stamped after the mark. When it runs late,
  it runs late by a median of about 7 to 11 s, a 90th percentile of about 10 to 50 s, and up to about 2.6 minutes.
  A bar cut at the minute is in material error in about 1% to 24% of the last three hours' minutes, and no offset and
  not the previous-boundary rule fixes that.

## Per coin

"Explained": share of the 360 boundaries a run of trades explains. "Zero fits": share of boundaries a cut at the minute
satisfies, over all boundaries and over explained ones. "Material error": share of the last three hours' minutes with
a candle where the bar is missing, its close is off by more than half the one-minute sigma, or its low is off by more
than 5 bp; for the bar cut at the minute, at the fitted offset, and by the previous-boundary rule. "Late-candle share":
share of explained boundaries where a trade stamped after the mark sits in the earlier candle. "Largest lo": the
latest such trade, in seconds after the mark.

| Coin | Class | Class if unexplained left out | Trades a minute (median) | Explained | Zero fits (all / explained) | Best offset (s) | Share it fits | Material error, last 3 h: zero / fitted / previous | Late-candle share | Largest lo (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC | B | A | 560 | 0.950 | 0.950 / 1.000 | -0.000 | 0.950 | 0.000 / 0.000 / 0.000 | 0.000 | -0.0 |
| ETH | B | A | 302 | 0.950 | 0.950 / 1.000 | -0.000 | 0.950 | 0.000 / 0.000 / 0.000 | 0.000 | -0.0 |
| SOL | B | A | 108 | 0.950 | 0.947 / 0.997 | -0.000 | 0.947 | 0.000 / 0.000 / 0.000 | 0.003 | 9.1 |
| XRP | B | A | 144 | 0.950 | 0.950 / 1.000 | 0.001 | 0.950 | 0.000 / 0.000 / 0.000 | 0.000 | -0.0 |
| DOGE | C | C | 18 | 0.967 | 0.731 / 0.756 | -0.002 | 0.731 | 0.078 / 0.078 / 0.061 | 0.241 | 136.6 |
| LTC | B | B | 36 | 0.956 | 0.914 / 0.956 | 0.001 | 0.914 | 0.006 / 0.006 / 0.006 | 0.044 | 13.8 |
| LINK | C | C | 25 | 0.975 | 0.808 / 0.829 | -0.002 | 0.808 | 0.050 / 0.050 / 0.044 | 0.168 | 62.5 |
| BCH | C | C | 8 | 0.933 | 0.550 / 0.589 | -0.030 | 0.550 | 0.244 / 0.244 / 0.216 | 0.408 | 131.8 |
| SUI | C | C | 24 | 0.953 | 0.808 / 0.848 | 0.006 | 0.808 | 0.033 / 0.033 / 0.039 | 0.149 | 82.7 |
| XLM | C | C | 26 | 0.956 | 0.856 / 0.895 | 0.010 | 0.856 | 0.033 / 0.033 / 0.044 | 0.105 | 20.1 |
| HBAR | C | C | 11 | 0.944 | 0.706 / 0.747 | 0.017 | 0.706 | 0.111 / 0.111 / 0.106 | 0.253 | 57.6 |
| NEAR | C | C | 53 | 0.950 | 0.847 / 0.892 | 0.002 | 0.847 | 0.017 / 0.017 / 0.028 | 0.108 | 21.0 |
| AAVE | C | C | 13 | 0.944 | 0.664 / 0.703 | -0.010 | 0.664 | 0.135 / 0.135 / 0.146 | 0.297 | 156.1 |
| HYPE | C | C | 42 | 0.956 | 0.875 / 0.916 | -0.004 | 0.875 | 0.011 / 0.011 / 0.017 | 0.084 | 29.6 |
| ENA | C | C | 17 | 0.956 | 0.711 / 0.744 | 0.005 | 0.711 | 0.163 / 0.163 / 0.152 | 0.256 | 58.0 |
| PEPE | C | C | 14 | 0.947 | 0.706 / 0.745 | 0.001 | 0.706 | 0.156 / 0.156 / 0.150 | 0.255 | 106.3 |
| ONDO | C | C | 27 | 0.950 | 0.789 / 0.830 | -0.009 | 0.789 | 0.061 / 0.061 / 0.056 | 0.170 | 48.6 |
| ZEC | B | B | 179 | 0.950 | 0.900 / 0.947 | -0.001 | 0.900 | 0.000 / 0.000 / 0.000 | 0.053 | 17.6 |

All columns, and the hour-by-hour offsets, are in per_coin.csv. One row per coin and boundary is in boundaries.csv.gz.

## What the cut looks like

- **At the minute, with late episodes.** No coin shows a steady shift. On every coin the best offset is zero.
- **Late candles come with quiet trading.** Over the 14 coins other than BTC, ETH, SOL and XRP:
  - a boundary after a minute with 5 trades or fewer ran late about 54% of the time; with 21 to 50 trades about 8%;
    with more than 50 trades about 2%;
  - by hour of the window, the late share fell from about 41% (12:00 UTC hour) to about 8% to 10% (15:00 and 16:00)
    and rose again to about 21% (18:00).
- **A minute's candle can be missing although trades are stamped in it.** On 9 of the C coins, 1 to 22 minutes in the
  window had trades but no candle; those trades sit in the candle before. This matches the BCH example that started
  the study.
- **Only 4 boundaries in all** had a trade stamped before the mark in the later candle (three at 14:10 UTC).
- **The best offset moves between hours** for LINK, BCH, SUI, AAVE and ENA (no single offset is best in all six
  hours); in the first hour their best offset was about 1 to 10 s, later about zero. For the other coins it stays
  about zero.
- **Neither fix helps the C coins.** The fitted offset is about zero, so it gives the same bars as the cut at the
  minute. The previous-boundary rule is a little better on some coins and a little worse on others; it never brings a
  C coin to 1%.

## Unexplained boundaries

- 311 of 6,480 boundaries (about 5%) are unexplained. Most fall on the same minutes for nearly every coin: about
  12:55, 14:05, 14:10 to 14:13, 14:27, 15:20 and (6 coins) 16:19 UTC.
- **The follow-up check (run 42878184379, BTC, ETH, SOL, DOGE) shows why:** at those minutes the final candle holds
  less volume than the public trades stamped in the minute, and the five-minute totals differ by the same amount. So
  some trades in the public list are not in any candle. Example: BTC 14:05, the candle has about 3.4 BTC, the trades
  about 13.4 BTC; the high, low and close match. At BTC 12:54 the trades also reach a higher high and close than the
  candle. The venue's trade ids have no gaps, so the list itself is complete.
- What these left-out trades are cannot be told from public data.
- Each such minute makes two boundaries unexplained, and more when the chain cannot re-anchor: a new anchor needs the
  next 5 candles to chain, so a run of bad minutes (14:10 to 14:13) also leaves the good minutes just before it
  (14:06 to 14:09) unexplained.

## Limits

- Six hours of one weekday. A class must be confirmed on the collector's daily record before it is relied on.
- A cut is only bounded by the trades around it. On quiet coins the intervals are wide.
- The best offset uses the midpoint of the tied range. On BTC the first-half range was about 0.07 s wide, so a few
  out-of-sample bars at the fitted offset differ in volume (not materially).
- A class says the inputs match. It says nothing about P&L.

## Runs

- Smoke: Actions run 42877183610 (20 minutes, BTC, DOGE, BCH; 60 of 60 boundaries explained). An earlier attempt,
  42876991670, failed on a path bug before any request.
- Main: Actions run 42877348846. No refusals, no page caps, no errors, no dropped candle answers (36 answers: 25 MISS,
  10 EXPIRED, 1 REVALIDATED, none with an Age header).
- Follow-up: Actions run 42878184379.

## How the choices were read (written Nov 10 2026, 18:34 UTC, before any data of this study)

These are readings of the plan where it leaves a detail open, and one stricter setting. None changes a class rule.

- **Pace.** The plan allows 7 requests a second. The study uses at most 5 a second across the whole job (stricter).
- **Refusals.** HTTP 401, 403, 429, 451 or a body that is not JSON stops that source (trades or candles) for all coins
  at once, with no retry. Network errors and 5xx are retried twice.
- **Page cap.** At most 2,500 trade pages a coin. A capped coin is analysed only from the minute its trades cover.
- **Final candles.** An answer counts only if it was generated (Date minus Age) at or after the window's last minute
  closed plus 180 s. A dropped answer is reported and not asked again with a different address.
- **Units.** Sizes and prices are compared as whole numbers of the smallest unit the coin's trades use. A candle volume
  "matches" a run of trades if the two are within half a unit.
- **Which boundaries are explained.** The boundary at the end of minute m is explained only if m's candle is matched
  and the next minute's candle is matched starting right after it. A minute with no candle takes no trades.
- **The cut.** "Cut at offset x" means a trade stamped before mark + x is in the earlier candle. So x satisfies a
  boundary when lo < x <= hi, where lo and hi are the stamps of the last trade in the earlier candle and the first
  trade after it, measured from the mark.
- **Share where zero fits (class A).** The denominator is every boundary in the window, and an unexplained boundary
  counts as "zero does not fit". This is the stricter reading. The share over explained boundaries only is also
  reported.
- **Measure 1 and 5 minutes.** As in the candle probe, only minutes that have a final candle are counted. A minute
  with trades but no candle is counted apart.
- **One-minute sigma.** Standard deviation of one-minute log returns of the final closes in the window.
- **The best offset.** The x that satisfies the most boundaries. If a range of x ties, the widest tied range is used
  (nearest zero if two are equally wide) and its midpoint is the offset.
- **Class B "ends no later than 12 s after the mark".** Read as: the fitted offset is at most 12 s.
- **Previous-boundary rule (measure 5).** The bar starts where the previous candle really ended (from the chain) and
  takes trades, in trade order, stamped before mark + x, where x = max(0, lo of the previous boundary); when x > 0 a
  trade stamped exactly at mark + x is included. If the previous candle's end is unknown, the bar cut at the minute is
  used and counted as a fallback.
- **Halves and hours.** "First three hours" and "last three hours" are the first and last 180 of the 360 minutes.
  Hours are the six blocks of 60 minutes.

## Addition to the plan (written Nov 10 2026, 18:43 UTC, after the main run, before the follow-up ran)

- **What was seen.** In the main run (Actions run 42877348846) the unexplained boundaries fell on the same minutes for
  nearly every coin: about 12:55, 14:05, 14:10 to 14:13, 14:27 and 15:20 UTC (16 to 18 of 18 coins each). For BTC
  these are the only boundaries that are not explained.
- **What is added.** One follow-up run (scripts/owner/candle_clock/diag.py) for BTC, ETH, SOL and DOGE at those minutes
  and one minute either side. It prints the final candle next to the bar of trades stamped in the minute, and the
  two-minute and five-minute volume totals of both. It is a description only. It changes no measure, no class rule
  and no class. Same pace and refusal policy; derived values only.
