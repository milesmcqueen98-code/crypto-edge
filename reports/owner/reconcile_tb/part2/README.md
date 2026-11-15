# Part 2 of the bar-source plan: the fourth paper book against the third (read Nov 15 2026)

This is the one registered read of Part 2 of reports/owner/bar_source_prereg.md. The rule was applied as written,
once. Verdict reached at 02:36 ET on Nov 15.

**Result: pass. The margins on the twelve coins are small; the clear differences are elsewhere (below).**

- **Period:** the fourth book's first three full days of decisions, 22:30 UTC on Nov 11 to 22:29 UTC on Nov 14
  (4,320 minutes). Counted from the two logs before any research was fetched, the third book had 452 new bids on
  the twelve coins and the fourth 435 on the minutes both were live, so the period was not extended.
- **Books:** third = `paper_spot_tb` (release 2's inputs: six coins on kept trades rows, twelve on candles), fourth =
  `paper_spot_t18` (all 18 coins: trades for the newest minute, the venue's candle afterwards; engine commit 58eba8b
  throughout). In this folder's tables "main" means the third book and "tb" the fourth.
- **Minutes:** third 4,258 decision minutes, fourth 4,249, both 4,187.
- **Research:** job 43689324147, 1,224 answers, nothing refused or dropped, fetched nine hours after the last minute.

## The rule (twelve coins, common minutes)

| Measure | Third book | Fourth book | Rule | Verdict |
|---|---|---|---|---|
| 1. New bids the research would not have placed | 20 of 452 (4.42%) | 18 of 435 (4.14%) | fourth strictly lower | pass |
| 2. Research's new bids with a bot bid within a minute | 414 of 448 (92.41%) | 404 of 434 (93.09%) | fourth not lower | pass |
| 3. New bids more than 5 bp from the research level | 4 of 452 (0.88%) | 4 of 435 (0.92%) | fourth below 5% | pass |
| Items 1 to 5 for the fourth book (items_1_5.md) | | all five meet | all hold | pass |

`part2_rule.md` is the rule's own output (scripts/owner/bar_source/part2_rule.py, on `main` since Nov 12).

## What the numbers do and do not show
- **On the twelve the two books are nearly the same.** Measure 1 passes by two bids. The wrong-side bids fall on
  the same coins in both books (HBAR 6 and 5, BCH 4 and 4, ENA 3 and 3), and the four level errors are the same
  four bids in both, all at 15:43 UTC on Nov 13. A running book cannot tell the two ways apart on these coins in
  three days. Part 1 measured the difference on every minute: about 30% fewer disagreements on arming and about
  a fifth fewer score misses with the new way.
- **On the five coins the third book keeps on trades rows (ETH, SOL, XRP, LTC, ZEC) the new way is clearly
  better.** Wrong-side bids: 5 of 292 in the third book (LTC 2, ZEC 2, XRP 1), 1 of 281 in the fourth (ZEC). Level
  errors: 7 (ZEC 5, LTC 2) against 2 (ZEC 1, LTC 1). Replacing the trades row by the venue's candle removes most
  of what kept rows did to ZEC and LTC. These coins are not part of the rule.
- **All 17 coins:** wrong-side 25 of 744 (3.36%) against 19 of 716 (2.65%); level 11 of 744 against 6 of 716.
- **Minutes without a new bid because an answer was old:** 763 coin-minutes in the third book, 4 in the fourth.
- **Fills on the twelve** (record only): in both the research and the book 26 and 27; in the book only 0 and 1 (a
  ladder that lost $406); in the research only 2 and 1.
- **The step.** The fourth book's data step ended a median 13.5 s after the minute, against about 10.3 s in the
  third. The paper books fill on whole-minute candles and do not feel this. A live bot would: the release that
  follows must not place its bids later than release 3 does (plan, deviation log, Nov 14).

## What follows
The new way for all 18 coins is the proposal for the next input release. It is not on `main`. It ships only as a
build that keeps the step at least as early as release 3's, and after a paper test of that build on a rule fixed
before it starts (plan, deviation log, Nov 14 and Nov 15).

## Files
- `research/`: the research table and the fetch facts (runner job 43689324147).
- `main/`, `tb/`: each book against the research on its own minutes (third and fourth).
- `side_by_side.csv`, `common_minutes.csv`, `two_books.json`: both books on the common minutes.
- `item7.md`, `item7.json`, `item7_bids.csv`: the per-bid rows the rule reads (the third book's item 7 format, all
  coins).
- `part2_rule.md`, `part2_rule.json`: the rule.
- `items_1_5.md`: the fourth book's items 1 to 5 on its log cut at the period's end.
