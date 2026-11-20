# Item 7: third book against main book, on the minutes both were live

Period: 2026-11-17 00:00:00 to 2026-11-19 23:59:00 UTC (both included).
Decision minutes in the period: main book 4246, third book 4248; common minutes 4174.

| measure | main book | third book | verdict |
|---|---|---|---|
| (a) new bids more than 5 bp from the research level | 2 / 725 = 0.28% | 2 / 725 = 0.28% | PASS |
| (b) new bids whose research score is at or below the threshold | 48 / 725 = 6.62% | 48 / 725 = 6.62% | FAIL |

**Item 7: FAIL**

Rule: per measure, WAIT if either book has fewer than 200 counted bids; PASS if the third book's share is strictly lower than the main book's, or both are strictly below 5%; else FAIL. Shares are compared exactly on the counts. Overall: FAIL if any measure fails, else WAIT if any waits, else PASS.
