# Item 7: third book against main book, on the minutes both were live

Period: 2026-11-11 01:47:00 to 2026-11-11 12:30:00 UTC (both included).
Decision minutes in the period: main book 289, third book 634; common minutes 288.

| measure | main book | third book | verdict |
|---|---|---|---|
| (a) new bids more than 5 bp from the research level | 5 / 36 = 13.89% | 0 / 17 = 0.00% | WAIT |
| (b) new bids whose research score is at or below the threshold | 1 / 36 = 2.78% | 1 / 17 = 5.88% | WAIT |

**Item 7: WAIT**

Rule: per measure, WAIT if either book has fewer than 200 counted bids; PASS if the third book's share is strictly lower than the main book's, or both are strictly below 5%; else FAIL. Shares are compared exactly on the counts. Overall: FAIL if any measure fails, else WAIT if any waits, else PASS.
