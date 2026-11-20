# The cause check after Part 3: the books' inputs emulated on the collector's record (run Nov 19 2026)

This is the check fixed in reports/owner/bar_source_prereg.md, "After Part 3: the cause", before it was run. It
decides nothing about Part 3, which failed as read. It asks why the paper books place bids the research would not.

**Result: confirmed. At the bids in question the books' scores are the scores a bar cut at the minute gives.**

- **Run:** Part 1's tool (scripts/owner/bar_source/build.py) on Part 3's period, 19:00 UTC on Nov 16 to 18:59 UTC on
  Nov 19; runner job 44644238137 on branch owner/read-part3; 4,320 decision minutes, 30,240 engine steps, 1,224
  candle answers, nothing refused or dropped. Pass C18 is the fourth book's inputs emulated: row t-1 from the
  collector's trades bar, cut at the minute; every older row the venue's final candle. It differs from the research
  in that one thing.
- **The counts** (scripts/owner/bar_source/book_check.py; "within" means within 0.5 point of the score the book
  logged; "far" means the book's score is more than 2 points from the research's):

  | Book against pass C18 | (i) bids within | (ii) far bids within | Wrong-side bids on the book's side in the emulation |
  |---|---|---|---|
  | Fourth book (the check) | 671 of 709 (94.6%) | 67 of 70 (95.7%) | 46 of 46 |
  | Fifth book (reported) | 665 of 702 (94.7%) | 66 of 71 (93.0%) | 47 of 49 |

  - **(i)** needed 90%: the emulation stands for the book.
  - **(ii)** needed 80%: confirmed. The three far bids the emulation misses are minutes in which the collector's
    trades bar was empty.
  - The twelve and the five apart, fourth book: (i) 519 of 542 and 152 of 167; (ii) 64 of 67 and 3 of 3.
- **What it shows.** Replace the newest row by a trades bar cut at the minute, leave everything else as the
  research has it, and the book's score comes out, at the bids where book and research disagree. The difference is
  the cut of the newest row, the coin's own or another coin's.
- **What it does not show by itself:** why a bar cut at the minute differs from the venue's final candle. The
  candle clock study of Nov 10 found that for the twelve coins the final candle of a quiet minute holds trades from
  the first seconds of the next; the split here agrees with it (67 of the 70 far bids are on the twelve). The
  late-cut replay (reports/owner/late_cut_prereg.md) sets prints against candles at the minutes that matter.

## The emulation on every minute, this period against Part 1's (pass C18, summary.md)

| Measure | The 17 coins, this period | The 17 coins, Nov 11 to 14 | The twelve, this period | The five, this period |
|---|---|---|---|---|
| Disagreement on arming | 275 of 60,757 (0.45%) | 188 of 63,326 (0.30%) | 233 of 47,206 (0.49%) | 42 of 13,551 (0.31%) |
| Scores more than 1.0 point off | 1,390 of 73,437 (1.89%) | 1,434 of 73,440 (1.95%) | 1,188 of 51,837 (2.29%) | 202 of 21,600 (0.94%) |
| Levels more than 5 bp off | 1,473 of 73,437 (2.01%) | 730 of 73,440 (0.99%) | 1,004 of 51,837 (1.94%) | 469 of 21,600 (2.17%) |

- On every minute the scores are off as often as in Part 1's period. The share at new bids doubled all the same
  (the twelve: 4.1% then, 8.0% now): a new bid is placed where the score crosses the line, and that is where a small
  difference in the newest row changes the side.

## What is not usable in this folder
- **Passes A, B and C, and the main book's check against pass A.** In those passes BTC and the five keep their
  trades rows for good, and the tool gives a minute without trades no row. In the 38 minutes of Nov 17 in which the
  venue's trades list stood still that leaves BTC flat, and the rows stay. The real main book took candles there.
  So these passes stop standing for any book from 21:19 UTC on Nov 17: the main book's bids are within 0.5 point of
  pass A at 80 of 92 before the standstill and at 328 of 546 after it. Nothing is read from them. Pass C18 takes
  only the newest row from trades and is not touched after the window.
- summary.md carries the tool's fixed heading ("Part 1"); the period in it is this one.

## Files
- `minutes.parquet`, `run.json`, `record_sources.csv`, `fetch_answers.csv`: build.py's outputs.
- `summary.md`, `per_coin.csv`, `counts.json`: compare.py on them (every minute; no log).
- `book_check_fourth_C18.*`, `book_check_fifth_C18.*`, `book_check_main_A.*`: the per-bid checks (md, json, bids csv).
