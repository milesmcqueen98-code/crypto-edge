# GAMMA: dealer gamma regime (Deribit) as a filter on the ladder (Path A), REPORT

**Verdict: FAIL.** HOLD paired t −1.62 at X2 (A1 needs ≥ 2), HOLD mean difference −0.20 bp/day at X1 (A2), both HOLD eras negative (A3). A4 passes. Skipping bids in dealer-short-gamma hours cost money in DEV (all 8 variants), in both HOLD eras, and at X2, X1 and S.

## Mechanism
Option dealers delta-hedge. Net long gamma, they buy falls and sell rises: a second dip-buyer beside the ladder. Net short gamma (customers own the options), they must sell into a fall, which should extend a cascade past the ladder's 60-minute horizon (Baltussen et al. 2021; Pearson, Poteshman & White 2006). The rule skips every coin's 4σ bids while BTC dealer gamma is below a threshold.

## Data
- Deribit (history.deribit.com, 20 Actions fetch runs, all succeeded, every month 2021-01..2026-11 present): 22,980,230 BTC option trades on 80,854 instruments; totals reconcile exactly with the derive. Deribit's instrument list (get_instruments, expired + active) covered every traded instrument. 432 options listed before 2021-01-01 are excluded (their gamma is zero in every DEV hour: none live after 2021).
- Hourly series (scripts/hunt2/gamma/derive_deribit.py, run 42545078490): 51,546 hours; DEV file 10,920 hours, HOLD file 22,776 (separate files; only DEV was committed before the freeze).
- Frozen simulator (ladder v6), $250K; research parents: DEV 1,155, chk 412, early 744.

## Construction (fixed in scripts/hunt2/gamma/gamma.py's docstring, commit 5ca2d24, before the first trial)
- Dealer inventory per option = −cumulative signed taker contracts since listing. For hour h, the snapshot uses trades before h − 60 s, so the signal is ≥ 1 minute old at every minute of h. Live options: traded before the snapshot, expiring after h.
- G = Σ inventory × Black–Scholes gamma (last traded IV, index price, T to expiry, r = 0) × S² × 1%, in USD per 1% move. That is the SPEC's formula; its label "BTC per 1% move" would be G / S, and threshold 0 is the same in both units. G_below: strikes below the index. 30d scope: options expiring within 30 days. Options with no traded IV yet add no gamma (≤ 8 per hour).
- Rule: m = SKIP for every coin in every minute of an hour whose signal is below the threshold (T × NC array); n_skip = DEV parents in skipped hours.
- DEV inputs: G < 0 in 71.5% of DEV hours (G30 81.7%, G_below 72.3%). By this proxy, Deribit dealers were net short gamma most of 2025–26; on average ~640 live options and ~160K BTC of gross dealer inventory per hour.

## Trials (8, all in the ledger; DEV paired HAC t vs the incumbent at X2)
| variant (signal / threshold / scope) | threshold | parents skipped | eligible (5–50%) | DEV t |
|---|---|---|---|---|
| G / 0 / all | 0 | 73.9% | no | −2.52 |
| G / 0 / 30d | 0 | 87.1% | no | −3.07 |
| **G / p25 / all** | −$40.6M per 1% | 20.4% | yes | **−0.52** |
| G / p25 / 30d | −$49.5M | 21.4% | yes | −1.14 |
| G_below / 0 / all | 0 | 76.3% | no | −1.99 |
| G_below / 0 / 30d | 0 | 84.6% | no | −2.52 |
| G_below / p25 / all | −$27.5M | 23.8% | yes | −0.54 |
| G_below / p25 / 30d | −$29.6M | 20.3% | yes | −1.35 |

All eight are negative: skipping hurt in every variant, most when the most was skipped.

## Frozen variant (freeze commit 52c1489)
G / p25 / all: skip every coin's 4σ bids in hours whose dealer net gamma G < −40,635,076 USD per 1% move (the DEV 25th percentile, ≈ −459 BTC per 1% at DEV prices). DEV: 25% of hours, 236 of 1,155 parents skipped; mean difference −0.26 bp/day; X2 Sharpe 1.54 vs 1.62.

## HOLD (read once)
| gate | result | |
|---|---|---|
| A1 HOLD paired t ≥ 2 (X2) | −1.62 (mean −0.14 bp/day) | FAIL |
| A2 HOLD mean difference > 0 at X1 | −0.20 bp/day (t −2.09) | FAIL |
| A3 every gated era positive (X2) | chk −0.08 bp/day (t −0.31); early −0.16 (t −1.94) | FAIL |
| A4 no losing year, candidate X2 | 2022 +6.8%, 2023 +7.7%, 2025 +13.9%, 2026 +9.6% | PASS |
- Both HOLD eras are gated (≥ 60 days, ≥ 10 skipped parents: chk 27, early 33).
- HOLD Sharpe at X2: 1.15 vs the incumbent's 1.26. At S: −0.20 bp/day (t −2.09), Sharpe 1.97 vs 2.11. Full period t −1.05.
- The filter fired far less on HOLD: 9.1% of chk hours (6.6% of parents) and 3.8% of early hours (4.4%), against 25% on DEV. The candidate differs from the incumbent on only 20 of 949 HOLD days. The worst differences (−46, −37 bp) are skipped dips that rebounded; one day gained +41 bp.
- Deflated Sharpe 0.07 (N = 4,598). Top-5-day share undefined (total gain negative).
- Robustness: every neighbouring setting agrees in sign (all 8 DEV t negative). On the incumbent's 10 worst DEV days the candidate was +2.95% better (5 of 10 days positive), but it gave that back elsewhere.

## Capacity, fills, implementability
- A filter only removes bids: no new fills, no loss of the incumbent's capacity. Fills, costs and the cash rule are the frozen simulator's.
- Live: hourly, ≥ 1 minute old. Inputs are Deribit public data (trade history with taker side, read-only, also via Coinbase-hosted Deribit endpoints). The bot would need a backfill of every option's inventory since listing plus a live trade stream: feasible, operationally heavy.

## Weaknesses
- The inventory proxy assumes every taker is a customer and every maker a dealer. Market makers trade with each other, and block trades and RFQs blur the taker side.
- Deribit only. IBIT options (the largest BTC options market since 2025) and CME options are missing, so the measured "dealer gamma" is one venue's.
- Units: the SPEC's formula is in USD, so the DEV-percentile threshold scales with BTC's price. It fired on 3.8% of hours in the low-price early era and 9.1% in chk, so HOLD tested a much rarer filter than DEV. A BTC-unit threshold would have been price-neutral; it was not tested (that choice would be post hoc).
- Linear BS gamma spikes before each 08:00 daily expiry; intraday seasonality enters the percentile cut.

## Deviations and shared-code notes
- Procedural: the pre-freeze derive run's artifact upload failed (hunt2.yml passes the space-separated `artifact` input to upload-artifact@v4 as one path). The HOLD file was regenerated after the freeze by re-running the unchanged derive code on the same raw artifacts; the DEV outputs reproduced byte-for-byte.
- Execution: the first HOLD attempt (pathA.hold_read in one process) was OOM-killed in the sel era before any series existed, so nothing was read. It was re-run as one process per era doing hold_read's steps, then assembled once with h2gates.path_a. The sel-era series equals the logged DEV trial exactly (max |diff| 0.0). The shared 6.26 GB memory cgroup also OOM-killed other builders' HOLD processes during this window.

## Verdict
FAIL. The Deribit dealer-gamma regime does not identify ladder fills worth skipping. Dips bought while dealers measured net short gamma were, on net, profitable in DEV and in both HOLD eras, so the filter only removed P&L. No evidence was found that dealer short gamma carries the ladder's dislocations past its 60-minute horizon.
