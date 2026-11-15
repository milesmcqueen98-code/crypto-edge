# Item 7: third book against main book, on the minutes both were live

Period: 2026-11-11 22:30:00 to 2026-11-14 22:29:00 UTC (both included).
Decision minutes in the period: main book 4258, third book 4249; common minutes 4187.

| measure | main book | third book | verdict |
|---|---|---|---|
| (a) new bids more than 5 bp from the research level | 11 / 744 = 1.48% | 6 / 716 = 0.84% | PASS |
| (b) new bids whose research score is at or below the threshold | 25 / 744 = 3.36% | 19 / 716 = 2.65% | PASS |

**Item 7: PASS**

Rule: per measure, WAIT if either book has fewer than 200 counted bids; PASS if the third book's share is strictly lower than the main book's, or both are strictly below 5%; else FAIL. Shares are compared exactly on the counts. Overall: FAIL if any measure fails, else WAIT if any waits, else PASS.
