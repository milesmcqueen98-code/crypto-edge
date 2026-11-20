# Part 3 of the bar-source plan: the fifth paper book, the input build (read Nov 19 2026)

This is the one registered read of Part 3 of reports/owner/bar_source_prereg.md. The rule was applied as written,
once. Verdict reached at 19:14 ET on Nov 19.

**Result: fail, on one clause of measure 2. No release 5.** Bids the research would not have placed are capped at
5%; the fifth book has 49 of 696 (7.04%). Every other clause is met. The control misses the same cap.

- **Period:** 19:00 UTC on Nov 16 to 18:59 UTC on Nov 19 (4,320 minutes), from the first half-hour mark after the
  fifth book's first decision minute (18:44 UTC on Nov 16). Counted from the two logs before any research was
  fetched, the fifth book had 696 new bids on the 17 coins and the fourth 695 on the minutes both decided, so the
  period was not extended.
- **Books:** fifth = `paper_spot_r5` (the build: all 18 coins take the newest minute from trades, the venue's candle
  replaces it afterwards, the candle requests are made at second 45; engine commit 9e6f53b3 throughout), fourth =
  `paper_spot_t18` (the same rows with the candle requests inside the step; commit 58eba8b), main = `paper_spot`
  (release 4 on `main`, release 3's inputs). In this folder's tables "main" means the fourth book and "tb" the
  fifth.
- **Minutes:** fifth 4,246 decision minutes, fourth 4,242, both 4,168.
- **Research:** job 44637871745, 1,224 answers, nothing refused or dropped, fetched about four and a half hours
  after the last minute.

## The rule (all 17 coins, common minutes)

| Measure | Value | Rule | Result |
|---|---|---|---|
| 1 (a) Same-machine pairs, build minus release 3 | median -1.485 s over 14 pairs | at or below zero, at least 8 pairs | met |
| 1 (b) Fifth book against main book, same half hours | 8.61 s against 11.05 s, 140 half hours | fifth no higher | met |
| 2 Bids the research would not have placed, against the fourth book | 49 of 696 (7.04%) against 46 of 695 (6.62%) | at most the fourth's share plus 2.0 points | met |
| 2 The same, cap | 49 of 696 (7.04%) | at most 5% | **not met** |
| 2 Research's new bids with a bot bid within a minute | 641 of 688 (93.17%) against 645 of 692 (93.21%) | at least the fourth's share minus 3.0 points | met |
| 2 Bids more than 5 bp from the research level | 2 of 696 (0.29%) | under 5% | met |
| 3 Items 1 to 5, fifth book (items_1_5.md) | 72,965 of 73,044 trades bars verified (99.89%); no refusal, no rate-limit stop; half-hour maximum 20 s or less in 99.3% of 142 heartbeats; no error event; no unconfirmed row | all five | met |
| 4 Failed candle requests between steps | 1 of 72,792 (0.001%) | at most 1% | met |
| 4 Candle requests inside a step | 70 of 76,518 coin-minutes (0.09%) | at most 2% | met |

`part3_rule.md` is the rule's own output (scripts/owner/bar_source/part3_rule.py, on `main` before the read).

## What the fail is
- **The build is not worse than its control.** The fourth book's 46 wrong-side bids are all among the fifth book's
  49, and 686 bids are the same bid in both books. The clause that compares the two books is met with room.
- **The cap is an absolute bound, and the control misses it too.** So does the main book on release 3's inputs: 47
  of 677 (6.94%) over the same period (run after the verdict; it decides nothing).
- **By the rule as written it is a fail.** The plan's branch for measure 2: no release; the cause is found first,
  and a corrected build starts a new three days.

## Reported, not part of the rule
- **The twelve and the five apart** (fifth book, then fourth):

  | Measure | The twelve | The five (ETH, SOL, XRP, LTC, ZEC) |
  |---|---|---|
  | Bids the research would not have placed | 46 of 530 (8.68%); 43 of 534 (8.05%) | 3 of 166 (1.81%); 3 of 161 (1.86%) |
  | Research bids matched | 481 of 525 (91.62%); 487 of 531 (91.71%) | 160 of 163 (98.16%); 158 of 161 (98.14%) |
  | Level more than 5 bp off | 1 of 530; 1 of 534 | 1 of 166; 1 of 161 |

- **By coin, bids the research would not have placed** (fifth book; the fourth differs by one LINK bid and two
  PEPE bids): ENA 7 of 87, HBAR 7 of 57, LINK 8 of 58, PEPE 5 of 56, XLM 5 of 33, AAVE 3 of 43, DOGE 3 of 36, SUI
  3 of 25, BCH 2 of 43, LTC 2 of 41, ONDO 2 of 47, ETH 1 of 4, HYPE 1 of 23, NEAR 0 of 22, SOL 0 of 20, XRP 0 of
  24, ZEC 0 of 77.
- **By day** (fifth book): Nov 16, 1 of 24; Nov 17, 5 of 101; Nov 18, 26 of 312; Nov 19, 17 of 259.
- **Fills and P&L.** Both books had the same two first-bid fills (NEAR at 15:44 UTC on Nov 18, BCH at 01:34 on
  Nov 19), and the research had both. The research had a third, PEPE at 15:51 on Nov 19, that neither book had.
  Exit P&L -$81.73 (fifth) and -$81.63 (fourth) on $23,095 and $23,076 bought.
- **Trades rows at a decision,** as far as the counters show it: 3,545 times a row three to six minutes old was
  still built from trades, of about 306,000 such rows looked at (1.2%).
- **The standstill window of Nov 17** (21:19 to 21:57 UTC; window_nov17.md). The research placed 8 new bids. The
  fourth book placed the same 8: none on the wrong side, none off the level, seven of the eight scores within 0.1
  point. The fifth book placed none (38 stopped minutes). The veto rule of Nov 18 is not triggered (0 of 8 wrong;
  five were needed), so the fallback to candles inside the step stays in the corrected build.
- **The pairs.** 14 count. The build's data step ended earlier in every one, by 1.03 to 2.80 s. Four pairs ran
  release 3 first and ten the build first.

## Looked at after the verdict (exploratory; it changes nothing above)
- **The books agree with one another; the difference is against the research.** At the 64 bids that the main and
  the fourth book share and whose score is more than 2 points from the research, the two logged the same score
  within 0.1 point in all 64.
- **The differences are large and the level is right.** At a wrong-side bid the book's score is a median 11.6
  points from the research's, and the bid level is on the same tick. The level is anchored on the coin's close an
  hour back and on BTC, so a different newest close of the coin moves the score and not the level.
- **It is not new.** The fourth book, one commit since Nov 11, had 18 wrong-side bids of 435 on the twelve in
  Part 2 (4.1%) and has 43 of 534 now (8.1%). A score more than 2 points from the research: 8.7% of its bids on
  the twelve then and 12.4% now; on the five 0.4% and 1.8%.
- **Mostly a minute apart.** At 29 of the fourth book's 46 wrong-side bids the research has a new bid of its own
  on that coin within a minute.
- **A first guess was checked and dropped:** coarse price ticks. The share by coin does not follow tick size.
- **Leading explanation, on record since Nov 10** (candle clock study): for the twelve coins the venue's final
  candle of a quiet minute holds trades from the first seconds of the next minute (8% to 41% of boundaries, a
  median 7 to 11 s). The research decides on that candle; a bar cut at the minute cannot equal it. A check on the
  collector's record is fixed in the plan ("After Part 3: the cause") before it is run; its tables go to
  reports/owner/bar_source_p3/.

## What follows
No release 5. The cause is checked first. The corrected build is the tested build plus the fallback for a trades
list that stands still (commit 815ea390 on branch owner/standstill); it starts a new three days on a rule written
into the plan before its first run. What the late cut gives the research on the twelve coins moves to the top of
the research list (FORWARD_TESTS.md).

## Files
- `research/`: the research table and the fetch facts (runner job 44637871745).
- `main/`, `tb/`: each book against the research on its own minutes (fourth and fifth).
- `side_by_side.csv`, `common_minutes.csv`, `two_books.json`: both books on the common minutes.
- `item7.md`, `item7.json`, `item7_bids.csv`: the per-bid rows the rule reads. item7.md prints the third book's old
  rule on them and is not Part 3's rule.
- `part3_rule.md`, `part3_rule.json`: the rule.
- `items_1_5.md`: the fifth book's measures 1, 3 and 4 on its log cut at the period's end.
- `window_nov17.md`: the standstill window by itself.
