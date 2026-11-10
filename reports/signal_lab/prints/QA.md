# F6 print features: data QA (signal lab 2)

Branch signal-lab-data. Pre-registration: reports/signal_lab/prospective_prereg.md (Data, Features F6, deviation 1). Written by scripts/signal_lab/prints_qa.py from derived files only; raw prints stayed on the runners. Nothing here reads a trade outcome, label or prediction: every quantity is from the 30 minutes before the candidate minute.

- **Candidates:** 17,527 main + 14,563 early = 32,090 rows (f6_main.parquet, f6_early.parquet; same keys and order as the candidate lists).
- **Windows:** 10,042 merged windows (every [q - 30 min, q) of both eras, overlapping or touching windows of one product merged); 79,062,792 distinct prints fetched.
- **Runs:** fetch 42709727926, 42709739614, 42709751047, 42709763051, 42709772505, 42709783166, 42709793618, 42709803316, 42709814456, 42709824752, 42709835361, 42709847396, 42709860136, 42709871348, 42709882545, 42709892707; features 42719994947; diagnostic 42721109133. Wall-clock: fetch 22:12-23:19 UTC Nov 9 (66 min; 16 shards in parallel, 48-66 min each, 216k requests at the fetcher's 7 per second); features 23:23-23:25 UTC (2 min).

## Data-quality gate (deviation 1)

| Era | Candidates | Complete | Share complete (>= 97%) | Median print USD / candle USD (0.98-1.02) | Gate |
|---|---|---|---|---|---|
| main (2024-2026) | 17,527 | 17,527 | 100.00% (pass) | 1.0002 over 17,527 windows (pass) | **PASS** |
| early (2021-2023) | 14,563 | 14,563 | 100.00% (pass) | 1.0002 over 14,563 windows (pass) | **PASS** |

**Gate: PASSES in both eras.**

Candle USD = sum of close x volume over the 30 one-minute candles q-30 .. q-1 (the simulator's daily_usd convention) from data/minute_early (before 2024) and data/minute. Print USD = usd_30. Windows with zero candle volume are left out of the ratio.

Spread of the per-window ratio (complete windows) and the same ratio in base units (sum of print size / candle volume; exact agreement expected):

| Era | p1 | p10 | p50 | p90 | p99 | Base-volume ratio p1 / p50 / p99 |
|---|---|---|---|---|---|---|
| main | 0.9911 | 0.9995 | 1.0002 | 1.0027 | 1.0775 | 0.991057 / 1.000000 / 1.077795 |
| early | 0.9856 | 0.9993 | 1.0002 | 1.0019 | 1.0232 | 0.984675 / 1.000000 / 1.022641 |

By coin (median print USD / candle USD over complete windows; share complete):

| Coin | main n | main median | main complete | early n | early median | early complete |
|---|---|---|---|---|---|---|
| AAVE | 882 | 1.0004 | 100.0% | 1,192 | 1.0004 | 100.0% |
| BCH | 1,049 | 1.0004 | 100.0% | 1,385 | 1.0003 | 100.0% |
| DOGE | 1,678 | 1.0002 | 100.0% | 1,625 | 1.0001 | 100.0% |
| ENA | 352 | 1.0004 | 100.0% | - | - | - |
| ETH | 2,308 | 1.0001 | 100.0% | 2,719 | 1.0001 | 100.0% |
| HBAR | 925 | 1.0002 | 100.0% | 370 | 1.0002 | 100.0% |
| HYPE | 173 | 1.0003 | 100.0% | - | - | - |
| LINK | 1,195 | 1.0002 | 100.0% | 1,438 | 1.0002 | 100.0% |
| LTC | 1,263 | 1.0002 | 100.0% | 1,800 | 1.0002 | 100.0% |
| NEAR | 794 | 1.0003 | 100.0% | 476 | 1.0006 | 100.0% |
| ONDO | 822 | 1.0002 | 100.0% | - | - | - |
| PEPE | 473 | 1.0002 | 100.0% | - | - | - |
| SOL | 1,404 | 1.0002 | 100.0% | 1,202 | 1.0002 | 100.0% |
| SUI | 1,119 | 1.0003 | 100.0% | 123 | 1.0005 | 100.0% |
| XLM | 969 | 1.0002 | 100.0% | 1,278 | 1.0002 | 100.0% |
| XRP | 1,469 | 1.0001 | 100.0% | 281 | 1.0000 | 100.0% |
| ZEC | 652 | 1.0009 | 100.0% | 674 | 1.0005 | 100.0% |

## Where prints and candles differ (scripts/signal_lab/prints_diag.py, qa_diag.json)

The window ratio's tails come from the candles, not from missing prints. Minute by minute over every minute of the merged windows, print base volume against the repo's candle volume (equal = within 1e-5 relative; candle volume is stored as float32):

| Era | Minutes | Equal | Candle has volume, no print | Print, no candle row (share of print volume) | Both, unequal (offset by the next or previous minute) | Prints above / below candle | Net print / candle volume |
|---|---|---|---|---|---|---|---|
| main | 220,753 | 86.1% | 0 | 2,022 (0.28%) | 25,592 (14,158) | 12,478 / 13,114 | 1.0002 |
| early | 186,383 | 77.4% | 0 | 3,235 (0.20%) | 34,298 (19,093) | 15,895 / 18,403 | 1.0041 |
| 2021 | 45,788 | 90.4% | 0 | 191 (0.07%) | 4,068 (2,573) | 1,988 / 2,080 | 1.0022 |
| 2022 | 65,865 | 79.7% | 0 | 894 (0.51%) | 11,624 (6,664) | 5,569 / 6,055 | 1.0106 |
| 2023 | 74,730 | 67.4% | 0 | 2,150 (0.04%) | 18,606 (9,856) | 8,338 / 10,268 | 1.0001 |
| 2024 | 70,589 | 95.5% | 0 | 630 (0.00%) | 1,342 (682) | 642 / 700 | 1.0000 |
| 2025 | 75,240 | 88.5% | 0 | 425 (0.06%) | 7,452 (4,239) | 3,569 / 3,883 | 1.0000 |
| 2026 | 74,924 | 74.9% | 0 | 967 (1.41%) | 16,798 (9,237) | 8,267 / 8,531 | 1.0014 |

- **Trade-id gaps inside windows** (Coinbase numbers each product's trades 1, 2, 3, ...): 0 gaps (0 ids never returned) in 0 windows, over 79,052,750 consecutive pairs.
- **Time against trade id:** 202 places where time decreases along trade id, all within the same second (largest 0.008 ms), 0 across a window edge. The fetcher's stop rule (ids rise with time) holds, so no print at a window edge can be lost.
- **Reading:** every window is a contiguous run of trade ids read past both edges, and no minute has candle volume without prints, so the print side is complete. The differences are candles missing a minute (prints, no candle row) and volume the candles put in a neighbouring minute (most unequal minutes are offset by the next or previous minute). They are largest in 2023 (67% of minutes equal) and 2026 (75% of minutes equal). They do not touch the F6 rows, which use only prints; they widen the tails of the gate's ratio, not its median.

## Look-ahead unit test (synthetic prints)

scripts/signal_lab/test_prints.py runs before every feature run on the runner (the run stops if it fails) and again here. On synthetic clustered tapes with shared timestamps:
- prints added at q, q + 1 us, q + 1 s and q + 7 min leave n_prints and every sum, the threshold and the sweep unchanged; the same print 1 us before q moves sell_usd_30 and sell_usd_5 by exactly its USD (control); a print at exactly q - 30 min is in the window and one at q - 30 min - 1 us is not;
- the big-print threshold equals a brute-force numpy.quantile(0.99) over [w - 30 days, w), w = q - 30 min, when that holds >= 2,000 prints, over the latest 2,000 prints before w when it does not, and is missing below 2,000 in all (all three branches hit); multiplying the size of every print at or after w (the window included) by 1,000 leaves it unchanged;
- sweep against a pandas groupby on calendar seconds; de-duplication by trade_id; maker side BUY counted as taker sell; the NaN rules.

Result: `test_prints: all checks passed (seed 0: 53763 prints, 62 candidate minutes, threshold rules hit [0, 1]; seed 1: 55688 prints, 61 candidate minutes, threshold rules hit [0, 1]; seed 2: 62115 prints, 61 candidate minutes, threshold rules hit [0, 1]; seed 3: 55538 prints, 64 candidate minutes, threshold rules hit [0, 1, 2]; 42 margin checks at 5 s and 60 s)`

## Side-convention check

Taker-sell share (maker side BUY) against the sign of the price change over the same 30 minutes, from candles (log of the close of minute q-1 over the open of minute q-30). If the convention were reversed, falling windows would show taker-sell shares below one half.

| Era | Windows | Spearman(ret, sell share) | Median sell share, ret < -0.5% | Median sell share, ret > +0.5% | Falling windows with sell share > 0.5 | Rising windows with sell share < 0.5 |
|---|---|---|---|---|---|---|
| main | 17,527 | -0.344 | 0.590 (n 13,674) | 0.473 (n 1,025) | 86.3% | 65.0% |
| early | 14,563 | -0.380 | 0.578 (n 11,229) | 0.464 (n 1,258) | 84.7% | 70.7% |

**Side convention: consistent** (criterion: a negative rank correlation, and a median taker-sell share above 0.5 in falling windows and below 0.5 in rising ones, in both eras).

## Other checks

- **Fetch status of merged windows:** main {'complete': 5433}, early {'complete': 4609}.
- **Prints:** 79,062,792 after de-duplication (0 duplicate trade ids dropped); side values {'BUY': 39821228, 'SELL': 39241564}; 202 places where time decreases along trade id; 0 prints outside their own window.
- **Big-print threshold rule** (1 = 30-day pool of >= 2,000 prints, 2 = latest 2,000, 0 = missing; all candidates, before the completeness mask): main {'1': 17345, '2': 158, '0': 24}, early {'1': 14225, '2': 265, '0': 73}.
- **Missing values among complete main rows (17,527):** {'adv_usd': 10, 'big_thr_usd': 24, 'csv_30': 10, 'csv_5': 10, 'sell_share_30': 0, 'big_sell_share_30': 24, 'sweep_max_30': 10}; rows with no print in the window: 0.
- **Missing values among complete early rows (14,563):** {'adv_usd': 190, 'big_thr_usd': 73, 'csv_30': 190, 'csv_5': 190, 'sell_share_30': 0, 'big_sell_share_30': 73, 'sweep_max_30': 190}; rows with no print in the window: 0.
- **ADV:** one continuous daily series per coin (data/minute_early before 2024, data/minute after), so January 2024 uses December 2023. The simulator's era-bounded index (sim.py PERIODS) would instead leave 249 main candidates without ADV and give 248 others a shorter window (all in January 2024); the early era is identical either way. ADV is missing where a coin has under 10 days of candles in the 30 before (the first days of the data in January 2021, of a listing, or of XRP's July 2023 relisting).

## Definitions as implemented

- q = candidate minute start (UTC). Only prints stamped before q: [q - 30 min, q) and [q - 5 min, q).
- Taker sell = maker side BUY. USD = price x size. Prints de-duplicated by trade_id.
- sweep_max_usd_30 = largest taker-sell USD within one calendar second (time floored to the second) in [q - 30 min, q).
- big_thr_usd = numpy.quantile(0.99, linear) of print USD over the coin's fetched prints in [w - 30 days, w), w = q - 30 min; under 2,000 there, the latest 2,000 fetched prints before w; under 2,000 in all, missing. Fetched prints = all de-duplicated prints of the coin's merged windows, both eras. Big = USD >= threshold.
- adv_usd = trailing 30-day median of positive daily spot USD volume (close x volume summed per UTC day), days D-30 .. D-1, at least 10 days (reports/signal_lab/prints/adv_daily.csv.gz).
- complete = the candidate's merged window was read back to a print stamped before its start.
- NaN: every float when complete is False; ratios with a missing or zero denominator; big_* without a threshold; the five F6 features when the window has no print (its USD sums are then 0).

## Candle-print boundary offsets (follow-up; prints_boundary.py, qa_boundary.json)

The model decides fills from the candles and F6 reads prints stamped before q, so a candle q that held trades the prints stamp before q would let the features see the start of the fill minute. For every adjacent pair of minutes (m, m+1) inside a merged window where print base volume and candle volume differ (relative 1e-5) in at least one of the two: the smallest boundary move that reconciles both minutes within 1e-5 ("strict": within 1e-7, the float32 precision of the candle files).
- **A** (could leak): the prints stamped in [m+1-d, m+1) sit in candle m+1; candle time lags print time.
- **B** (harmless): the prints stamped in [m+1, m+1+d) sit in candle m.
- **Neighbour:** this pair's difference is a reconciled move at the next boundary (one move leaves the two pairs around it unequal). **Edge:** the remaining difference sits in the first or last minute of a window, next to a boundary whose outer minute was never fetched. **Not reconciled:** no single move up to 60 s.
- A whole-minute shift moves every print of the source minute (its candle row is missing and the next one holds both minutes). d for a whole-minute A shift is measured from that minute's first print.
- Self-test on a synthetic tape with planted moves: `prints_boundary self-test passed (17 unequal pairs; A 0.35 s lag, B 2 s lead, whole-minute A, their neighbours, a lost minute, a window edge, a one-sided window-end A and, by the chain check, a three-boundary B chain all recovered)`

| Year | Unequal pairs | A (strict) | A whole-minute | B (strict) | B whole-minute | Neighbour | Edge | Not reconciled (A-like / B-like / same sign) | Whole-minute share |
|---|---|---|---|---|---|---|---|---|---|
| all | 83,622 of 397,094 | 33 (26) | 22 | 17,503 (17,488) | 2,263 | 26,733 | 1,197 | 38,156 (10,550 / 8,392 / 19,214) | 2.7% |
| 2021 | 5,484 of 44,695 | 0 (0) | 0 | 1,339 (1,337) | 117 | 2,162 | 77 | 1,906 (556 / 449 / 901) | 2.1% |
| 2022 | 15,902 of 64,292 | 2 (2) | 2 | 3,488 (3,487) | 396 | 5,388 | 202 | 6,822 (1,933 / 1,525 / 3,364) | 2.5% |
| 2023 | 26,541 of 72,787 | 7 (5) | 5 | 5,390 (5,386) | 1,035 | 7,945 | 356 | 12,843 (3,388 / 2,574 / 6,881) | 3.9% |
| 2024 | 2,827 of 68,866 | 0 (0) | 0 | 361 (361) | 52 | 518 | 57 | 1,891 (438 / 381 / 1,072) | 1.8% |
| 2025 | 10,158 of 73,421 | 5 (4) | 3 | 2,180 (2,178) | 200 | 3,457 | 164 | 4,352 (1,263 / 1,011 / 2,078) | 2.0% |
| 2026 | 22,710 of 73,033 | 19 (15) | 12 | 4,745 (4,739) | 463 | 7,263 | 341 | 10,342 (2,972 / 2,452 / 4,918) | 2.1% |

Offset d in seconds, p50 / p90 / p99 / max (all reconciled pairs; then without whole-minute shifts):

| Year | A: all | A: sub-minute | B: all | B: sub-minute |
|---|---|---|---|---|
| all | 20.460 / 49.410 / 54.426 / 54.743 | 7.041 / 11.267 / 19.541 / 20.460 | 8.766 / 29.893 / 56.224 / 59.984 | 8.385 / 20.617 / 44.179 / 53.002 |
| 2021 | - | - | 8.473 / 27.639 / 54.574 / 59.943 | 8.301 / 19.502 / 40.256 / 49.255 |
| 2022 | 29.914 / 41.777 / 44.446 / 44.743 | - | 8.820 / 29.694 / 55.474 / 59.877 | 8.490 / 21.827 / 45.429 / 53.002 |
| 2023 | 29.290 / 53.743 / 54.643 / 54.743 | 8.033 / 8.826 / 9.005 / 9.025 | 9.198 / 37.454 / 57.228 / 59.984 | 8.594 / 25.624 / 45.718 / 49.986 |
| 2024 | - | - | 9.114 / 29.845 / 54.511 / 59.965 | 8.448 / 19.837 / 46.262 / 48.884 |
| 2025 | 8.198 / 37.137 / 47.143 / 48.255 | 12.527 / 18.873 / 20.301 / 20.460 | 8.447 / 23.802 / 55.062 / 59.958 | 8.217 / 18.225 / 36.808 / 49.965 |
| 2026 | 18.883 / 41.874 / 53.022 / 53.751 | 4.278 / 10.515 / 11.191 / 11.267 | 8.498 / 27.745 / 55.363 / 59.939 | 8.198 / 19.832 / 43.654 / 49.965 |

At the boundary before each candidate (m+1 = q). Two-sided where minute q lies inside a merged window; otherwise minute q was never fetched and A is tested on minute q-1 alone (candle q-1 = its prints less a suffix, candle q holding at least that volume):

| Era | Candidates | Two-sided: kinds | One-sided: kinds | A (whole-minute) | A share | A: d p50 / p90 / p99 / max (s) | A: moved USD / usd_30, p50 / p90 / p99 / max | Mean moved USD / usd_30, all candidates |
|---|---|---|---|---|---|---|---|---|
| main | 17,527 | 12,094: {'equal': 11089, 'none': 409, 'neighbour': 395, 'B': 178, 'edge': 21, 'A': 2} | 5,433: {'equal': 4915, 'surplus': 228, 'neighbour': 169, 'deficit_unexplained': 98, 'A': 23} | 25 (21) | 0.14% | 15.140 / 40.779 / 51.146 / 51.546 | 0.0065 / 0.0334 / 0.0515 / 0.0530 | 0.00002 |
| early | 14,563 | 9,954: {'equal': 8697, 'neighbour': 529, 'none': 425, 'B': 275, 'edge': 28} | 4,609: {'equal': 3882, 'surplus': 271, 'neighbour': 269, 'deficit_unexplained': 166, 'A': 21} | 21 (21) | 0.14% | 27.661 / 49.270 / 59.107 / 59.859 | 0.0022 / 0.1942 / 0.6113 / 0.7030 | 0.00009 |

**Chain check.** The single-move test cannot reconcile runs of consecutive moves (a run of B moves leaves pairs with an A-like sign pattern that no one move fixes). The chain check solves every boundary of a window at once: with x the print volume stamped before a boundary that the candles put after it (A > 0, B < 0), candle m = prints m + x(before m) - x(after m), so x is carried from the window start (x = 0). Each x must be 0, a suffix of the left minute's prints (A) or a prefix of the right minute's (B); otherwise the boundary is unexplained (for example candle volume lost) and x restarts at 0. A move is confirmed when neither neighbouring boundary is unexplained.

| Year | Boundaries | Zero | A confirmed (whole-minute) / unconfirmed | B confirmed (whole-minute) / unconfirmed | Unexplained | A confirmed d, sub-minute (s) | B confirmed d, sub-minute (s) | Pairs left open by the single-move test, by chain result |
|---|---|---|---|---|---|---|---|---|
| all | 397,094 | 354,140 | 45 (27) / 2,466 | 31,060 (2,680) / 1,366 | 8,017 | 5.929 / 13.761 / 20.914 / 21.021 | 8.419 / 22.443 / 41.133 / 59.759 | {'zero': 15356, 'B_confirmed': 14593, 'unexplained': 6368, 'A': 2279, 'B': 726, 'A_confirmed': 31} |
| 2021 | 44,695 | 42,134 | 0 (0) / 66 | 2,142 (128) / 59 | 294 | - | 8.302 / 19.750 / 39.788 / 49.255 | {'B_confirmed': 847, 'zero': 785, 'unexplained': 261, 'A': 62, 'B': 28} |
| 2022 | 64,292 | 56,336 | 2 (1) / 364 | 6,167 (483) / 211 | 1,212 | 3.143 / 3.143 / 3.143 / 3.143 | 8.562 / 23.518 / 41.154 / 53.002 | {'B_confirmed': 2850, 'zero': 2702, 'unexplained': 1033, 'A': 332, 'B': 105, 'A_confirmed': 2} |
| 2023 | 72,787 | 58,899 | 8 (6) / 856 | 9,654 (1,154) / 510 | 2,860 | 13.867 / 19.590 / 20.878 / 21.021 | 8.631 / 25.233 / 43.057 / 49.988 | {'zero': 5182, 'B_confirmed': 4686, 'unexplained': 2285, 'A': 773, 'B': 268, 'A_confirmed': 5} |
| 2024 | 68,866 | 66,880 | 11 (10) / 561 | 709 (66) / 24 | 681 | 10.920 / 10.920 / 10.920 / 10.920 | 8.510 / 23.482 / 42.614 / 49.997 | {'zero': 800, 'A': 544, 'B_confirmed': 372, 'unexplained': 210, 'B': 12, 'A_confirmed': 10} |
| 2025 | 73,421 | 68,402 | 2 (2) / 170 | 3,896 (244) / 128 | 823 | - | 8.218 / 19.095 / 38.576 / 54.694 | {'B_confirmed': 1813, 'zero': 1768, 'unexplained': 707, 'A': 156, 'B': 71, 'A_confirmed': 1} |
| 2026 | 73,033 | 61,489 | 22 (8) / 449 | 8,492 (605) / 434 | 2,147 | 4.574 / 9.623 / 18.994 / 20.390 | 8.223 / 20.660 / 41.164 / 59.759 | {'zero': 4119, 'B_confirmed': 4025, 'unexplained': 1872, 'A': 412, 'B': 242, 'A_confirmed': 13} |

Chain check at the boundary before each candidate (B_unverified: x < 0 at a window end, where minute q was not fetched; harmless either way):

| Era | Kinds | A confirmed (whole-minute) | A confirmed share | A: d p50 / p90 / p99 / max (s) | A: moved USD / usd_30, p50 / p90 / p99 / max | Mean moved USD / usd_30, all candidates |
|---|---|---|---|---|---|---|
| main | {'zero': 16824, 'B': 303, 'B_unverified': 246, 'unexplained': 112, 'A': 42} | 21 (16) | 0.12% | 17.241 / 44.334 / 57.061 / 58.440 | 0.0106 / 0.0530 / 0.0832 / 0.0885 | 0.000026 |
| early | {'zero': 13678, 'B': 449, 'B_unverified': 315, 'unexplained': 83, 'A': 38} | 13 (12) | 0.09% | 11.416 / 47.838 / 55.108 / 56.098 | 0.0060 / 0.2685 / 0.6516 / 0.7030 | 0.000111 |

**Largest direction-A offset (single-move test):** over all window pairs 54.743 s (22 whole-minute shifts; largest sub-minute 20.460 s); at the boundary before a candidate 59.859 s (42 whole-minute; largest sub-minute 8.283 s).
**Largest direction-A offset (chain check, confirmed):** over all boundaries 59.219 s (27 whole-minute; largest sub-minute 21.021 s); at the boundary before a candidate 58.440 s (28 whole-minute; largest sub-minute 44.334 s).

- **Reading:** the candles mostly lead the prints (B: prints stamped in the first seconds of a minute sit in the previous candle), which cannot leak. Direction A at the boundary before a candidate, by either test: main 31 of 17,527 candidates (0.18%), 6 with d <= 5 s, 31 with d <= 60 s; chain result unexplained at 112, B at 549; early 24 of 14,563 candidates (0.16%), 4 with d <= 5 s, 24 with d <= 60 s; chain result unexplained at 83, B at 764. Most A cases there are whole-minute shifts (the candle row for q-1 is missing and candle q holds that minute's prints). Every A offset found is under 60 s, so the 60 s margin tables exclude all of them; the 5 s margin excludes few. Unexplained boundaries are undetermined, not shown to be A.

## Leak flags under deviations 2 and 3 (prints_leak.py, leak_flags.parquet)

Per candidate, from prints and candles only (rule of reports/signal_lab/prospective_prereg.md deviations 2 and 3, branch signal-lab, commit 8a0990f). "Exceeds" means by more than 1e-5 relative.
- **leak_0:** trades stamped before q sit in the candle of q or later: (i) a leak-direction move with d > 0 reconciles the pair (q-1, q) (single-move test; one-sided where minute q was not fetched); (ii) no measured move explains the pair (kind none or edge) and both signs fit a move into q (prints of q-1 exceed its candle, the candle of q exceeds its prints); (iii) the candle row of q-1 is missing (or has zero volume) while minute q-1 has prints.
- **leak_5:** the same with d > 5 s in (i). **leak_60:** the candle rows of q-1 and q-2 are both missing while minute q-2 has prints. A clock lag above 60 s cannot be measured by this diagnostic.
- **Upper bound:** adds candidates the rule cannot decide: minute q's prints were never fetched (the last candidate of each merged window; whether candle q exceeds its prints is unknown) with the prints of q-1 above its candle and no (i); and pairs explained by moves at the neighbouring boundaries where both signs still fit (a stricter reading of (ii)).
- The flags choose one margin for every row. They are never used to mask or drop rows.
- Self-test: `prints_leak self-test passed (13 cases)`

| Read era | Candidates | leak_0 | (i) / (ii) / (iii) | leak_5 | leak_60 | (iii): merged into q / not merged / minute q not fetched | Upper bound leak_0 / leak_5 |
|---|---|---|---|---|---|---|---|
| selection (Jan 2025 - Mar 2026) | 7,788 | 35 (0.45%) | 12 / 14 / 20 | 34 (0.44%) | 0 (0.00%) | 1 / 4 / 15 | 1.84% / 1.82% |
| check (Apr - Nov 5 2026) | 4,095 | 70 (1.71%) | 8 / 41 / 35 | 69 (1.68%) | 2 (0.05%) | 10 / 7 / 18 | 5.30% / 5.27% |
| early holdout (2022-23) | 10,603 | 154 (1.45%) | 21 / 67 / 98 | 154 (1.45%) | 15 (0.14%) | 21 / 20 / 57 | 5.11% / 5.11% |
| 2021 (training only) | 3,960 | 7 (0.18%) | 0 / 3 / 4 | 7 (0.18%) | 0 (0.00%) | 0 / 0 / 4 | 1.41% / 1.41% |
| 2024 (training only) | 5,644 | 19 (0.34%) | 5 / 1 / 18 | 19 (0.34%) | 4 (0.07%) | 0 / 10 / 8 | 0.66% / 0.66% |

The (i) / (ii) / (iii) counts overlap; leak_0 by combination: selection {'ii': 14, 'i+iii': 11, 'iii': 9, 'i': 1}; check {'ii': 32, 'iii': 21, 'ii+iii': 9, 'i+iii': 5, 'i': 3}; early holdout {'iii': 66, 'ii': 56, 'i+iii': 21, 'ii+iii': 11}; 2021 {'iii': 4, 'ii': 3}; 2024 {'iii': 13, 'i+iii': 5, 'ii': 1}. i+iii is a whole-minute shift: candle q-1 missing and candle q holding that minute's prints.

- **Against the 0.5% bar of deviation 2 (each read era):** 0 s: not under 0.5% in every read era by the rule (not under at the upper bound); 5 s: not under 0.5% in every read era by the rule (not under at the upper bound); 60 s: under 0.5% in every read era by the rule.

## Margin tables (follow-up)

f6_main_m5.parquet, f6_early_m5.parquet (margin 5 s) and f6_main_m60.parquet, f6_early_m60.parquet (margin 60 s): the same schema, keys and row order as f6_main / f6_early, with both windows ending at q - margin, [q - 30 min, q - margin) and [q - 5 min, q - margin); the big-print threshold pool is unchanged (prints before q - 30 min), so big_thr_usd equals the margin-0 column. scripts/signal_lab/prints_features.py <art_dir> <out_dir> 0,5,60; the synthetic test checks that a print at q - margin is excluded and one 1 us earlier is included.
- **Margin 0 unchanged:** the same run recomputed the margin-0 tables: values equal to the committed files (main True, early True), bytes equal (main True, early True). The committed f6_main.parquet and f6_early.parquet were not rewritten.

| Margin | Era | Complete | Windows without a print | Median n_prints | Missing (csv_30, csv_5, sell_share_30, big_sell_share_30, sweep_max_30) | Medians (same order) |
|---|---|---|---|---|---|---|
| 0 s | main | 17,527 | 0 | 3894 | 10, 10, 0, 24, 10 | 0.03697, 0.006149, 0.5754, 0.2186, 0.003698 |
| 0 s | early | 14,563 | 0 | 2718 | 190, 190, 0, 73, 190 | 0.03495, 0.006262, 0.5624, 0.1684, 0.002706 |
| 5 s | main | 17,527 | 0 | 3882 | 10, 10, 0, 24, 10 | 0.03679, 0.006023, 0.5752, 0.2182, 0.003685 |
| 5 s | early | 14,563 | 0 | 2705 | 190, 190, 0, 73, 190 | 0.0347, 0.006078, 0.5621, 0.1678, 0.00269 |
| 60 s | main | 17,527 | 0 | 3687 | 10, 10, 0, 24, 10 | 0.03434, 0.004479, 0.5734, 0.2155, 0.003523 |
| 60 s | early | 14,563 | 0 | 2564 | 190, 190, 0, 73, 190 | 0.03251, 0.004456, 0.56, 0.1644, 0.002573 |

