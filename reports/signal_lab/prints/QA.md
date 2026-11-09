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

Result: `test_prints: all checks passed (seed 0: 53763 prints, 62 candidate minutes, threshold rules hit [0, 1]; seed 1: 55688 prints, 61 candidate minutes, threshold rules hit [0, 1]; seed 2: 62115 prints, 61 candidate minutes, threshold rules hit [0, 1]; seed 3: 55538 prints, 64 candidate minutes, threshold rules hit [0, 1, 2])`

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

