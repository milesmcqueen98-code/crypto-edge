# Item 7: third book against main book, on the minutes both were live

Period: 2026-11-11 01:47:00 to 2026-11-12 12:30:00 UTC (both included).
Decision minutes in the period: main book 1364, third book 2053; common minutes 1361.

| measure | main book | third book | verdict |
|---|---|---|---|
| (a) new bids more than 5 bp from the research level | 82 / 229 = 35.81% | 0 / 159 = 0.00% | WAIT |
| (b) new bids whose research score is at or below the threshold | 39 / 229 = 17.03% | 5 / 159 = 3.14% | WAIT |

**Item 7: WAIT**

Rule: per measure, WAIT if either book has fewer than 200 counted bids; PASS if the third book's share is strictly lower than the main book's, or both are strictly below 5%; else FAIL. Shares are compared exactly on the counts. Overall: FAIL if any measure fails, else WAIT if any waits, else PASS.
