# Candle clock study

Plan: reports/owner/candle_clock_prereg.md. Code: scripts/owner/candle_clock/study.py (runner) and test_study.py
(offline test).

Results: not yet run. This section is filled in after the full run.

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
