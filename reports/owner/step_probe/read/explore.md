# Step probe: exploratory table, when is the trades list complete

Exploratory: this table was made after the probe's rule was applied, it decides nothing, and anything acted on needs its own test.

Rows used: early and standard passes whose (run, coin, minute) has a verified reference-pass row (asked again 95 s after the minute closed). Equal: open, high, low and close equal as numbers, or no bar in both. Equal among all rows counts unverified rows too (their bar, if any, against the reference). BTC and the other 17 coins are shown apart. Shares are k / n = percent.

## all runs together

### Table 1. By the second the request was sent (sent_s, floor)

| pass | coins | sent_s | rows | verified | equal among all rows | equal among the verified |
|---|---|---|---|---|---|---|
| early | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | other | 1 | 2004 | 1466 / 2004 = 73.15% | 1650 / 2004 = 82.34% | 1361 / 1466 = 92.84% |
| early | other | 2 | 3441 | 2889 / 3441 = 83.96% | 3017 / 3441 = 87.68% | 2750 / 2889 = 95.19% |
| early | other | 3 | 3164 | 2931 / 3164 = 92.64% | 2989 / 3164 = 94.47% | 2854 / 2931 = 97.37% |
| early | other | 4 | 885 | 885 / 885 = 100.00% | 856 / 885 = 96.72% | 856 / 885 = 96.72% |
| early | other | 5 | 335 | 335 / 335 = 100.00% | 333 / 335 = 99.40% | 333 / 335 = 99.40% |
| early | other | 6 | 168 | 167 / 168 = 99.40% | 166 / 168 = 98.81% | 166 / 167 = 99.40% |
| early | other | 7 | 98 | 98 / 98 = 100.00% | 97 / 98 = 98.98% | 97 / 98 = 98.98% |
| early | other | 8 | 32 | 32 / 32 = 100.00% | 32 / 32 = 100.00% | 32 / 32 = 100.00% |
| early | other | 9 | 37 | 37 / 37 = 100.00% | 37 / 37 = 100.00% | 37 / 37 = 100.00% |
| early | other | 10 | 17 | 17 / 17 = 100.00% | 17 / 17 = 100.00% | 17 / 17 = 100.00% |
| early | other | 11 | 8 | 8 / 8 = 100.00% | 8 / 8 = 100.00% | 8 / 8 = 100.00% |
| early | other | 12+ | 11 | 11 / 11 = 100.00% | 11 / 11 = 100.00% | 11 / 11 = 100.00% |
| early | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 1 | 588 | 252 / 588 = 42.86% | 151 / 588 = 25.68% | 136 / 252 = 53.97% |
| early | BTC | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 6 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 7 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 8 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 9 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 10 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 11 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 12+ | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 6 | 1649 | 1649 / 1649 = 100.00% | 1649 / 1649 = 100.00% | 1649 / 1649 = 100.00% |
| standard | other | 7 | 3318 | 3318 / 3318 = 100.00% | 3317 / 3318 = 99.97% | 3317 / 3318 = 99.97% |
| standard | other | 8 | 3099 | 3099 / 3099 = 100.00% | 3099 / 3099 = 100.00% | 3099 / 3099 = 100.00% |
| standard | other | 9 | 893 | 893 / 893 = 100.00% | 893 / 893 = 100.00% | 893 / 893 = 100.00% |
| standard | other | 10 | 388 | 388 / 388 = 100.00% | 388 / 388 = 100.00% | 388 / 388 = 100.00% |
| standard | other | 11 | 267 | 267 / 267 = 100.00% | 267 / 267 = 100.00% | 267 / 267 = 100.00% |
| standard | other | 12+ | 586 | 586 / 586 = 100.00% | 586 / 586 = 100.00% | 586 / 586 = 100.00% |
| standard | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 6 | 533 | 533 / 533 = 100.00% | 533 / 533 = 100.00% | 533 / 533 = 100.00% |
| standard | BTC | 7 | 26 | 26 / 26 = 100.00% | 26 / 26 = 100.00% | 26 / 26 = 100.00% |
| standard | BTC | 8 | 8 | 8 / 8 = 100.00% | 8 / 8 = 100.00% | 8 / 8 = 100.00% |
| standard | BTC | 9 | 6 | 6 / 6 = 100.00% | 6 / 6 = 100.00% | 6 / 6 = 100.00% |
| standard | BTC | 10 | 5 | 5 / 5 = 100.00% | 5 / 5 = 100.00% | 5 / 5 = 100.00% |
| standard | BTC | 11 | 3 | 3 / 3 = 100.00% | 3 / 3 = 100.00% | 3 / 3 = 100.00% |
| standard | BTC | 12+ | 7 | 7 / 7 = 100.00% | 7 / 7 = 100.00% | 7 / 7 = 100.00% |

### Table 2. By the second the answer was made (gen_s, floor)

| pass | coins | gen_s | rows | verified | equal among all rows | equal among the verified |
|---|---|---|---|---|---|---|
| early | other | before the minute's end | 1323 | 0 / 1323 = 0.00% | 691 / 1323 = 52.23% | 0 / 0 = n/a |
| early | other | 0 | 828 | 828 / 828 = 100.00% | 734 / 828 = 88.65% | 734 / 828 = 88.65% |
| early | other | 1 | 1687 | 1687 / 1687 = 100.00% | 1591 / 1687 = 94.31% | 1591 / 1687 = 94.31% |
| early | other | 2 | 2675 | 2675 / 2675 = 100.00% | 2564 / 2675 = 95.85% | 2564 / 2675 = 95.85% |
| early | other | 3 | 2353 | 2353 / 2353 = 100.00% | 2306 / 2353 = 98.00% | 2306 / 2353 = 98.00% |
| early | other | 4 | 759 | 759 / 759 = 100.00% | 753 / 759 = 99.21% | 753 / 759 = 99.21% |
| early | other | 5 | 267 | 267 / 267 = 100.00% | 267 / 267 = 100.00% | 267 / 267 = 100.00% |
| early | other | 6 | 129 | 129 / 129 = 100.00% | 129 / 129 = 100.00% | 129 / 129 = 100.00% |
| early | other | 7 | 81 | 81 / 81 = 100.00% | 81 / 81 = 100.00% | 81 / 81 = 100.00% |
| early | other | 8+ | 97 | 97 / 97 = 100.00% | 97 / 97 = 100.00% | 97 / 97 = 100.00% |
| early | other | unknown | 1 | 0 / 1 = 0.00% | 0 / 1 = 0.00% | 0 / 0 = n/a |
| early | BTC | before the minute's end | 336 | 0 / 336 = 0.00% | 15 / 336 = 4.46% | 0 / 0 = n/a |
| early | BTC | 0 | 118 | 118 / 118 = 100.00% | 19 / 118 = 16.10% | 19 / 118 = 16.10% |
| early | BTC | 1 | 131 | 131 / 131 = 100.00% | 114 / 131 = 87.02% | 114 / 131 = 87.02% |
| early | BTC | 2 | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |
| early | BTC | 3 | 2 | 2 / 2 = 100.00% | 2 / 2 = 100.00% | 2 / 2 = 100.00% |
| early | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 6 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 7 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 8+ | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 1 | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |
| standard | other | 2 | 591 | 591 / 591 = 100.00% | 591 / 591 = 100.00% | 591 / 591 = 100.00% |
| standard | other | 3 | 1050 | 1050 / 1050 = 100.00% | 1050 / 1050 = 100.00% | 1050 / 1050 = 100.00% |
| standard | other | 4 | 1198 | 1198 / 1198 = 100.00% | 1197 / 1198 = 99.92% | 1197 / 1198 = 99.92% |
| standard | other | 5 | 751 | 751 / 751 = 100.00% | 751 / 751 = 100.00% | 751 / 751 = 100.00% |
| standard | other | 6 | 1191 | 1191 / 1191 = 100.00% | 1191 / 1191 = 100.00% | 1191 / 1191 = 100.00% |
| standard | other | 7 | 1999 | 1999 / 1999 = 100.00% | 1999 / 1999 = 100.00% | 1999 / 1999 = 100.00% |
| standard | other | 8+ | 3419 | 3419 / 3419 = 100.00% | 3419 / 3419 = 100.00% | 3419 / 3419 = 100.00% |
| standard | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 2 | 102 | 102 / 102 = 100.00% | 102 / 102 = 100.00% | 102 / 102 = 100.00% |
| standard | BTC | 3 | 107 | 107 / 107 = 100.00% | 107 / 107 = 100.00% | 107 / 107 = 100.00% |
| standard | BTC | 4 | 123 | 123 / 123 = 100.00% | 123 / 123 = 100.00% | 123 / 123 = 100.00% |
| standard | BTC | 5 | 103 | 103 / 103 = 100.00% | 103 / 103 = 100.00% | 103 / 103 = 100.00% |
| standard | BTC | 6 | 123 | 123 / 123 = 100.00% | 123 / 123 = 100.00% | 123 / 123 = 100.00% |
| standard | BTC | 7 | 10 | 10 / 10 = 100.00% | 10 / 10 = 100.00% | 10 / 10 = 100.00% |
| standard | BTC | 8+ | 20 | 20 / 20 = 100.00% | 20 / 20 = 100.00% | 20 / 20 = 100.00% |

### Table 3. The Age header

| pass | coins | rows | none (fresh) | Age 0 | Age 1 | Age 2 | Age 3 | Age 4 | Age 5 and more |
|---|---|---|---|---|---|---|---|---|---|
| early | other | 10200 | 5955 | 891 | 779 | 819 | 828 | 928 | 0 |
| early | BTC | 588 | 11 | 123 | 118 | 127 | 105 | 104 | 0 |
| standard | other | 10200 | 4405 | 836 | 684 | 794 | 795 | 2682 | 4 |
| standard | BTC | 588 | 14 | 114 | 116 | 118 | 120 | 106 | 0 |

### Table 4. What the standard pass saw after a fresh early answer

Cases: (run, coin, minute) with an early row without an Age header, a standard row and a reference. Same answer: open, high, low, close, volume and n all the same text as the early row's. Last column: standard rows of the cell equal to the reference.

Coins: other

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 180 | 180 / 180 = 100.00% |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 4 | 4 / 4 = 100.00% |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 4 | 4 / 4 = 100.00% |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 15 | 15 / 15 = 100.00% |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 21 | 21 / 21 = 100.00% |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 15 | 15 / 15 = 100.00% |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 2834 | 2834 / 2834 = 100.00% |
| equal | fresh | different answer | 34 | 34 / 34 = 100.00% |
| equal | 0 | same answer | 190 | 190 / 190 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 108 | 108 / 108 = 100.00% |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 159 | 159 / 159 = 100.00% |
| equal | 2 | different answer | 4 | 4 / 4 = 100.00% |
| equal | 3 | same answer | 206 | 206 / 206 = 100.00% |
| equal | 3 | different answer | 8 | 8 / 8 = 100.00% |
| equal | 4 | same answer | 2164 | 2164 / 2164 = 100.00% |
| equal | 4 | different answer | 6 | 6 / 6 = 100.00% |
| equal | 5+ | same answer | 3 | 3 / 3 = 100.00% |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 239 cases; the standard row was fresh in 180, came with an Age header in 59, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 5716 cases; the standard row was fresh in 2868, came with an Age header in 2848, and of those 2830 were the same answer as the early one.

Coins: BTC

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 0 | 0 / 0 = n/a |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 0 | 0 / 0 = n/a |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 0 | 0 / 0 = n/a |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 0 | 0 / 0 = n/a |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 0 | 0 / 0 = n/a |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 3 | 3 / 3 = 100.00% |
| equal | fresh | different answer | 0 | 0 / 0 = n/a |
| equal | 0 | same answer | 1 | 1 / 1 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 0 | 0 / 0 = n/a |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 0 | 0 / 0 = n/a |
| equal | 2 | different answer | 0 | 0 / 0 = n/a |
| equal | 3 | same answer | 0 | 0 / 0 = n/a |
| equal | 3 | different answer | 0 | 0 / 0 = n/a |
| equal | 4 | same answer | 7 | 7 / 7 = 100.00% |
| equal | 4 | different answer | 0 | 0 / 0 = n/a |
| equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 0 cases; the standard row was fresh in 0, came with an Age header in 0, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 11 cases; the standard row was fresh in 3, came with an Age header in 8, and of those 8 were the same answer as the early one.

Coins: all coins

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 180 | 180 / 180 = 100.00% |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 4 | 4 / 4 = 100.00% |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 4 | 4 / 4 = 100.00% |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 15 | 15 / 15 = 100.00% |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 21 | 21 / 21 = 100.00% |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 15 | 15 / 15 = 100.00% |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 2837 | 2837 / 2837 = 100.00% |
| equal | fresh | different answer | 34 | 34 / 34 = 100.00% |
| equal | 0 | same answer | 191 | 191 / 191 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 108 | 108 / 108 = 100.00% |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 159 | 159 / 159 = 100.00% |
| equal | 2 | different answer | 4 | 4 / 4 = 100.00% |
| equal | 3 | same answer | 206 | 206 / 206 = 100.00% |
| equal | 3 | different answer | 8 | 8 / 8 = 100.00% |
| equal | 4 | same answer | 2171 | 2171 / 2171 = 100.00% |
| equal | 4 | different answer | 6 | 6 / 6 = 100.00% |
| equal | 5+ | same answer | 3 | 3 / 3 = 100.00% |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 239 cases; the standard row was fresh in 180, came with an Age header in 59, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 5727 cases; the standard row was fresh in 2871, came with an Age header in 2856, and of those 2838 were the same answer as the early one.

## run run1

### Table 1. By the second the request was sent (sent_s, floor)

| pass | coins | sent_s | rows | verified | equal among all rows | equal among the verified |
|---|---|---|---|---|---|---|
| early | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | other | 1 | 857 | 733 / 857 = 85.53% | 703 / 857 = 82.03% | 652 / 733 = 88.95% |
| early | other | 2 | 1961 | 1767 / 1961 = 90.11% | 1725 / 1961 = 87.97% | 1650 / 1767 = 93.38% |
| early | other | 3 | 1861 | 1787 / 1861 = 96.02% | 1756 / 1861 = 94.36% | 1730 / 1787 = 96.81% |
| early | other | 4 | 332 | 332 / 332 = 100.00% | 319 / 332 = 96.08% | 319 / 332 = 96.08% |
| early | other | 5 | 51 | 51 / 51 = 100.00% | 49 / 51 = 96.08% | 49 / 51 = 96.08% |
| early | other | 6 | 23 | 23 / 23 = 100.00% | 23 / 23 = 100.00% | 23 / 23 = 100.00% |
| early | other | 7 | 9 | 9 / 9 = 100.00% | 9 / 9 = 100.00% | 9 / 9 = 100.00% |
| early | other | 8 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | other | 9 | 5 | 5 / 5 = 100.00% | 5 / 5 = 100.00% | 5 / 5 = 100.00% |
| early | other | 10 | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |
| early | other | 11 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | other | 12+ | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 1 | 295 | 126 / 295 = 42.71% | 65 / 295 = 22.03% | 63 / 126 = 50.00% |
| early | BTC | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 6 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 7 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 8 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 9 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 10 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 11 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 12+ | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 6 | 720 | 720 / 720 = 100.00% | 720 / 720 = 100.00% | 720 / 720 = 100.00% |
| standard | other | 7 | 1905 | 1905 / 1905 = 100.00% | 1905 / 1905 = 100.00% | 1905 / 1905 = 100.00% |
| standard | other | 8 | 1872 | 1872 / 1872 = 100.00% | 1872 / 1872 = 100.00% | 1872 / 1872 = 100.00% |
| standard | other | 9 | 407 | 407 / 407 = 100.00% | 407 / 407 = 100.00% | 407 / 407 = 100.00% |
| standard | other | 10 | 67 | 67 / 67 = 100.00% | 67 / 67 = 100.00% | 67 / 67 = 100.00% |
| standard | other | 11 | 31 | 31 / 31 = 100.00% | 31 / 31 = 100.00% | 31 / 31 = 100.00% |
| standard | other | 12+ | 98 | 98 / 98 = 100.00% | 98 / 98 = 100.00% | 98 / 98 = 100.00% |
| standard | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 6 | 289 | 289 / 289 = 100.00% | 289 / 289 = 100.00% | 289 / 289 = 100.00% |
| standard | BTC | 7 | 4 | 4 / 4 = 100.00% | 4 / 4 = 100.00% | 4 / 4 = 100.00% |
| standard | BTC | 8 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 9 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 10 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 11 | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |
| standard | BTC | 12+ | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |

### Table 2. By the second the answer was made (gen_s, floor)

| pass | coins | gen_s | rows | verified | equal among all rows | equal among the verified |
|---|---|---|---|---|---|---|
| early | other | before the minute's end | 392 | 0 / 392 = 0.00% | 152 / 392 = 38.78% | 0 / 0 = n/a |
| early | other | 0 | 312 | 312 / 312 = 100.00% | 276 / 312 = 88.46% | 276 / 312 = 88.46% |
| early | other | 1 | 758 | 758 / 758 = 100.00% | 674 / 758 = 88.92% | 674 / 758 = 88.92% |
| early | other | 2 | 1581 | 1581 / 1581 = 100.00% | 1482 / 1581 = 93.74% | 1482 / 1581 = 93.74% |
| early | other | 3 | 1608 | 1608 / 1608 = 100.00% | 1563 / 1608 = 97.20% | 1563 / 1608 = 97.20% |
| early | other | 4 | 363 | 363 / 363 = 100.00% | 357 / 363 = 98.35% | 357 / 363 = 98.35% |
| early | other | 5 | 50 | 50 / 50 = 100.00% | 50 / 50 = 100.00% | 50 / 50 = 100.00% |
| early | other | 6 | 18 | 18 / 18 = 100.00% | 18 / 18 = 100.00% | 18 / 18 = 100.00% |
| early | other | 7 | 11 | 11 / 11 = 100.00% | 11 / 11 = 100.00% | 11 / 11 = 100.00% |
| early | other | 8+ | 7 | 7 / 7 = 100.00% | 7 / 7 = 100.00% | 7 / 7 = 100.00% |
| early | BTC | before the minute's end | 169 | 0 / 169 = 0.00% | 2 / 169 = 1.18% | 0 / 0 = n/a |
| early | BTC | 0 | 59 | 59 / 59 = 100.00% | 4 / 59 = 6.78% | 4 / 59 = 6.78% |
| early | BTC | 1 | 67 | 67 / 67 = 100.00% | 59 / 67 = 88.06% | 59 / 67 = 88.06% |
| early | BTC | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 6 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 7 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 8+ | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 2 | 259 | 259 / 259 = 100.00% | 259 / 259 = 100.00% | 259 / 259 = 100.00% |
| standard | other | 3 | 584 | 584 / 584 = 100.00% | 584 / 584 = 100.00% | 584 / 584 = 100.00% |
| standard | other | 4 | 710 | 710 / 710 = 100.00% | 710 / 710 = 100.00% | 710 / 710 = 100.00% |
| standard | other | 5 | 312 | 312 / 312 = 100.00% | 312 / 312 = 100.00% | 312 / 312 = 100.00% |
| standard | other | 6 | 538 | 538 / 538 = 100.00% | 538 / 538 = 100.00% | 538 / 538 = 100.00% |
| standard | other | 7 | 1141 | 1141 / 1141 = 100.00% | 1141 / 1141 = 100.00% | 1141 / 1141 = 100.00% |
| standard | other | 8+ | 1556 | 1556 / 1556 = 100.00% | 1556 / 1556 = 100.00% | 1556 / 1556 = 100.00% |
| standard | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 2 | 52 | 52 / 52 = 100.00% | 52 / 52 = 100.00% | 52 / 52 = 100.00% |
| standard | BTC | 3 | 61 | 61 / 61 = 100.00% | 61 / 61 = 100.00% | 61 / 61 = 100.00% |
| standard | BTC | 4 | 60 | 60 / 60 = 100.00% | 60 / 60 = 100.00% | 60 / 60 = 100.00% |
| standard | BTC | 5 | 60 | 60 / 60 = 100.00% | 60 / 60 = 100.00% | 60 / 60 = 100.00% |
| standard | BTC | 6 | 58 | 58 / 58 = 100.00% | 58 / 58 = 100.00% | 58 / 58 = 100.00% |
| standard | BTC | 7 | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |
| standard | BTC | 8+ | 3 | 3 / 3 = 100.00% | 3 / 3 = 100.00% | 3 / 3 = 100.00% |

### Table 3. The Age header

| pass | coins | rows | none (fresh) | Age 0 | Age 1 | Age 2 | Age 3 | Age 4 | Age 5 and more |
|---|---|---|---|---|---|---|---|---|---|
| early | other | 5100 | 4048 | 131 | 154 | 230 | 267 | 270 | 0 |
| early | BTC | 295 | 11 | 56 | 59 | 66 | 54 | 49 | 0 |
| standard | other | 5100 | 2724 | 165 | 203 | 255 | 203 | 1547 | 3 |
| standard | BTC | 295 | 13 | 47 | 60 | 59 | 64 | 52 | 0 |

### Table 4. What the standard pass saw after a fresh early answer

Cases: (run, coin, minute) with an early row without an Age header, a standard row and a reference. Same answer: open, high, low, close, volume and n all the same text as the early row's. Last column: standard rows of the cell equal to the reference.

Coins: other

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 174 | 174 / 174 = 100.00% |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 3 | 3 / 3 = 100.00% |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 4 | 4 / 4 = 100.00% |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 14 | 14 / 14 = 100.00% |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 20 | 20 / 20 = 100.00% |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 13 | 13 / 13 = 100.00% |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 2099 | 2099 / 2099 = 100.00% |
| equal | fresh | different answer | 33 | 33 / 33 = 100.00% |
| equal | 0 | same answer | 70 | 70 / 70 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 69 | 69 / 69 = 100.00% |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 58 | 58 / 58 = 100.00% |
| equal | 2 | different answer | 3 | 3 / 3 = 100.00% |
| equal | 3 | same answer | 39 | 39 / 39 = 100.00% |
| equal | 3 | different answer | 8 | 8 / 8 = 100.00% |
| equal | 4 | same answer | 1433 | 1433 / 1433 = 100.00% |
| equal | 4 | different answer | 5 | 5 / 5 = 100.00% |
| equal | 5+ | same answer | 3 | 3 / 3 = 100.00% |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 228 cases; the standard row was fresh in 174, came with an Age header in 54, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 3820 cases; the standard row was fresh in 2132, came with an Age header in 1688, and of those 1672 were the same answer as the early one.

Coins: BTC

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 0 | 0 / 0 = n/a |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 0 | 0 / 0 = n/a |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 0 | 0 / 0 = n/a |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 0 | 0 / 0 = n/a |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 0 | 0 / 0 = n/a |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 3 | 3 / 3 = 100.00% |
| equal | fresh | different answer | 0 | 0 / 0 = n/a |
| equal | 0 | same answer | 1 | 1 / 1 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 0 | 0 / 0 = n/a |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 0 | 0 / 0 = n/a |
| equal | 2 | different answer | 0 | 0 / 0 = n/a |
| equal | 3 | same answer | 0 | 0 / 0 = n/a |
| equal | 3 | different answer | 0 | 0 / 0 = n/a |
| equal | 4 | same answer | 7 | 7 / 7 = 100.00% |
| equal | 4 | different answer | 0 | 0 / 0 = n/a |
| equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 0 cases; the standard row was fresh in 0, came with an Age header in 0, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 11 cases; the standard row was fresh in 3, came with an Age header in 8, and of those 8 were the same answer as the early one.

Coins: all coins

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 174 | 174 / 174 = 100.00% |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 3 | 3 / 3 = 100.00% |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 4 | 4 / 4 = 100.00% |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 14 | 14 / 14 = 100.00% |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 20 | 20 / 20 = 100.00% |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 13 | 13 / 13 = 100.00% |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 2102 | 2102 / 2102 = 100.00% |
| equal | fresh | different answer | 33 | 33 / 33 = 100.00% |
| equal | 0 | same answer | 71 | 71 / 71 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 69 | 69 / 69 = 100.00% |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 58 | 58 / 58 = 100.00% |
| equal | 2 | different answer | 3 | 3 / 3 = 100.00% |
| equal | 3 | same answer | 39 | 39 / 39 = 100.00% |
| equal | 3 | different answer | 8 | 8 / 8 = 100.00% |
| equal | 4 | same answer | 1440 | 1440 / 1440 = 100.00% |
| equal | 4 | different answer | 5 | 5 / 5 = 100.00% |
| equal | 5+ | same answer | 3 | 3 / 3 = 100.00% |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 228 cases; the standard row was fresh in 174, came with an Age header in 54, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 3831 cases; the standard row was fresh in 2135, came with an Age header in 1696, and of those 1680 were the same answer as the early one.

## run run2

### Table 1. By the second the request was sent (sent_s, floor)

| pass | coins | sent_s | rows | verified | equal among all rows | equal among the verified |
|---|---|---|---|---|---|---|
| early | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | other | 1 | 1147 | 733 / 1147 = 63.91% | 947 / 1147 = 82.56% | 709 / 733 = 96.73% |
| early | other | 2 | 1480 | 1122 / 1480 = 75.81% | 1292 / 1480 = 87.30% | 1100 / 1122 = 98.04% |
| early | other | 3 | 1303 | 1144 / 1303 = 87.80% | 1233 / 1303 = 94.63% | 1124 / 1144 = 98.25% |
| early | other | 4 | 553 | 553 / 553 = 100.00% | 537 / 553 = 97.11% | 537 / 553 = 97.11% |
| early | other | 5 | 284 | 284 / 284 = 100.00% | 284 / 284 = 100.00% | 284 / 284 = 100.00% |
| early | other | 6 | 145 | 144 / 145 = 99.31% | 143 / 145 = 98.62% | 143 / 144 = 99.31% |
| early | other | 7 | 89 | 89 / 89 = 100.00% | 88 / 89 = 98.88% | 88 / 89 = 98.88% |
| early | other | 8 | 32 | 32 / 32 = 100.00% | 32 / 32 = 100.00% | 32 / 32 = 100.00% |
| early | other | 9 | 32 | 32 / 32 = 100.00% | 32 / 32 = 100.00% | 32 / 32 = 100.00% |
| early | other | 10 | 16 | 16 / 16 = 100.00% | 16 / 16 = 100.00% | 16 / 16 = 100.00% |
| early | other | 11 | 8 | 8 / 8 = 100.00% | 8 / 8 = 100.00% | 8 / 8 = 100.00% |
| early | other | 12+ | 11 | 11 / 11 = 100.00% | 11 / 11 = 100.00% | 11 / 11 = 100.00% |
| early | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 1 | 293 | 126 / 293 = 43.00% | 86 / 293 = 29.35% | 73 / 126 = 57.94% |
| early | BTC | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 6 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 7 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 8 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 9 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 10 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 11 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 12+ | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 6 | 929 | 929 / 929 = 100.00% | 929 / 929 = 100.00% | 929 / 929 = 100.00% |
| standard | other | 7 | 1413 | 1413 / 1413 = 100.00% | 1412 / 1413 = 99.93% | 1412 / 1413 = 99.93% |
| standard | other | 8 | 1227 | 1227 / 1227 = 100.00% | 1227 / 1227 = 100.00% | 1227 / 1227 = 100.00% |
| standard | other | 9 | 486 | 486 / 486 = 100.00% | 486 / 486 = 100.00% | 486 / 486 = 100.00% |
| standard | other | 10 | 321 | 321 / 321 = 100.00% | 321 / 321 = 100.00% | 321 / 321 = 100.00% |
| standard | other | 11 | 236 | 236 / 236 = 100.00% | 236 / 236 = 100.00% | 236 / 236 = 100.00% |
| standard | other | 12+ | 488 | 488 / 488 = 100.00% | 488 / 488 = 100.00% | 488 / 488 = 100.00% |
| standard | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 2 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 3 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 6 | 244 | 244 / 244 = 100.00% | 244 / 244 = 100.00% | 244 / 244 = 100.00% |
| standard | BTC | 7 | 22 | 22 / 22 = 100.00% | 22 / 22 = 100.00% | 22 / 22 = 100.00% |
| standard | BTC | 8 | 8 | 8 / 8 = 100.00% | 8 / 8 = 100.00% | 8 / 8 = 100.00% |
| standard | BTC | 9 | 6 | 6 / 6 = 100.00% | 6 / 6 = 100.00% | 6 / 6 = 100.00% |
| standard | BTC | 10 | 5 | 5 / 5 = 100.00% | 5 / 5 = 100.00% | 5 / 5 = 100.00% |
| standard | BTC | 11 | 2 | 2 / 2 = 100.00% | 2 / 2 = 100.00% | 2 / 2 = 100.00% |
| standard | BTC | 12+ | 6 | 6 / 6 = 100.00% | 6 / 6 = 100.00% | 6 / 6 = 100.00% |

### Table 2. By the second the answer was made (gen_s, floor)

| pass | coins | gen_s | rows | verified | equal among all rows | equal among the verified |
|---|---|---|---|---|---|---|
| early | other | before the minute's end | 931 | 0 / 931 = 0.00% | 539 / 931 = 57.89% | 0 / 0 = n/a |
| early | other | 0 | 516 | 516 / 516 = 100.00% | 458 / 516 = 88.76% | 458 / 516 = 88.76% |
| early | other | 1 | 929 | 929 / 929 = 100.00% | 917 / 929 = 98.71% | 917 / 929 = 98.71% |
| early | other | 2 | 1094 | 1094 / 1094 = 100.00% | 1082 / 1094 = 98.90% | 1082 / 1094 = 98.90% |
| early | other | 3 | 745 | 745 / 745 = 100.00% | 743 / 745 = 99.73% | 743 / 745 = 99.73% |
| early | other | 4 | 396 | 396 / 396 = 100.00% | 396 / 396 = 100.00% | 396 / 396 = 100.00% |
| early | other | 5 | 217 | 217 / 217 = 100.00% | 217 / 217 = 100.00% | 217 / 217 = 100.00% |
| early | other | 6 | 111 | 111 / 111 = 100.00% | 111 / 111 = 100.00% | 111 / 111 = 100.00% |
| early | other | 7 | 70 | 70 / 70 = 100.00% | 70 / 70 = 100.00% | 70 / 70 = 100.00% |
| early | other | 8+ | 90 | 90 / 90 = 100.00% | 90 / 90 = 100.00% | 90 / 90 = 100.00% |
| early | other | unknown | 1 | 0 / 1 = 0.00% | 0 / 1 = 0.00% | 0 / 0 = n/a |
| early | BTC | before the minute's end | 167 | 0 / 167 = 0.00% | 13 / 167 = 7.78% | 0 / 0 = n/a |
| early | BTC | 0 | 59 | 59 / 59 = 100.00% | 15 / 59 = 25.42% | 15 / 59 = 25.42% |
| early | BTC | 1 | 64 | 64 / 64 = 100.00% | 55 / 64 = 85.94% | 55 / 64 = 85.94% |
| early | BTC | 2 | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |
| early | BTC | 3 | 2 | 2 / 2 = 100.00% | 2 / 2 = 100.00% | 2 / 2 = 100.00% |
| early | BTC | 4 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 5 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 6 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 7 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| early | BTC | 8+ | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | other | 1 | 1 | 1 / 1 = 100.00% | 1 / 1 = 100.00% | 1 / 1 = 100.00% |
| standard | other | 2 | 332 | 332 / 332 = 100.00% | 332 / 332 = 100.00% | 332 / 332 = 100.00% |
| standard | other | 3 | 466 | 466 / 466 = 100.00% | 466 / 466 = 100.00% | 466 / 466 = 100.00% |
| standard | other | 4 | 488 | 488 / 488 = 100.00% | 487 / 488 = 99.80% | 487 / 488 = 99.80% |
| standard | other | 5 | 439 | 439 / 439 = 100.00% | 439 / 439 = 100.00% | 439 / 439 = 100.00% |
| standard | other | 6 | 653 | 653 / 653 = 100.00% | 653 / 653 = 100.00% | 653 / 653 = 100.00% |
| standard | other | 7 | 858 | 858 / 858 = 100.00% | 858 / 858 = 100.00% | 858 / 858 = 100.00% |
| standard | other | 8+ | 1863 | 1863 / 1863 = 100.00% | 1863 / 1863 = 100.00% | 1863 / 1863 = 100.00% |
| standard | BTC | 0 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 1 | 0 | 0 / 0 = n/a | 0 / 0 = n/a | 0 / 0 = n/a |
| standard | BTC | 2 | 50 | 50 / 50 = 100.00% | 50 / 50 = 100.00% | 50 / 50 = 100.00% |
| standard | BTC | 3 | 46 | 46 / 46 = 100.00% | 46 / 46 = 100.00% | 46 / 46 = 100.00% |
| standard | BTC | 4 | 63 | 63 / 63 = 100.00% | 63 / 63 = 100.00% | 63 / 63 = 100.00% |
| standard | BTC | 5 | 43 | 43 / 43 = 100.00% | 43 / 43 = 100.00% | 43 / 43 = 100.00% |
| standard | BTC | 6 | 65 | 65 / 65 = 100.00% | 65 / 65 = 100.00% | 65 / 65 = 100.00% |
| standard | BTC | 7 | 9 | 9 / 9 = 100.00% | 9 / 9 = 100.00% | 9 / 9 = 100.00% |
| standard | BTC | 8+ | 17 | 17 / 17 = 100.00% | 17 / 17 = 100.00% | 17 / 17 = 100.00% |

### Table 3. The Age header

| pass | coins | rows | none (fresh) | Age 0 | Age 1 | Age 2 | Age 3 | Age 4 | Age 5 and more |
|---|---|---|---|---|---|---|---|---|---|
| early | other | 5100 | 1907 | 760 | 625 | 589 | 561 | 658 | 0 |
| early | BTC | 293 | 0 | 67 | 59 | 61 | 51 | 55 | 0 |
| standard | other | 5100 | 1681 | 671 | 481 | 539 | 592 | 1135 | 1 |
| standard | BTC | 293 | 1 | 67 | 56 | 59 | 56 | 54 | 0 |

### Table 4. What the standard pass saw after a fresh early answer

Cases: (run, coin, minute) with an early row without an Age header, a standard row and a reference. Same answer: open, high, low, close, volume and n all the same text as the early row's. Last column: standard rows of the cell equal to the reference.

Coins: other

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 6 | 6 / 6 = 100.00% |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 1 | 1 / 1 = 100.00% |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 0 | 0 / 0 = n/a |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 1 | 1 / 1 = 100.00% |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 1 | 1 / 1 = 100.00% |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 2 | 2 / 2 = 100.00% |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 735 | 735 / 735 = 100.00% |
| equal | fresh | different answer | 1 | 1 / 1 = 100.00% |
| equal | 0 | same answer | 120 | 120 / 120 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 39 | 39 / 39 = 100.00% |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 101 | 101 / 101 = 100.00% |
| equal | 2 | different answer | 1 | 1 / 1 = 100.00% |
| equal | 3 | same answer | 167 | 167 / 167 = 100.00% |
| equal | 3 | different answer | 0 | 0 / 0 = n/a |
| equal | 4 | same answer | 731 | 731 / 731 = 100.00% |
| equal | 4 | different answer | 1 | 1 / 1 = 100.00% |
| equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 11 cases; the standard row was fresh in 6, came with an Age header in 5, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 1896 cases; the standard row was fresh in 736, came with an Age header in 1160, and of those 1158 were the same answer as the early one.

Coins: BTC

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 0 | 0 / 0 = n/a |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 0 | 0 / 0 = n/a |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 0 | 0 / 0 = n/a |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 0 | 0 / 0 = n/a |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 0 | 0 / 0 = n/a |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 0 | 0 / 0 = n/a |
| equal | fresh | different answer | 0 | 0 / 0 = n/a |
| equal | 0 | same answer | 0 | 0 / 0 = n/a |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 0 | 0 / 0 = n/a |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 0 | 0 / 0 = n/a |
| equal | 2 | different answer | 0 | 0 / 0 = n/a |
| equal | 3 | same answer | 0 | 0 / 0 = n/a |
| equal | 3 | different answer | 0 | 0 / 0 = n/a |
| equal | 4 | same answer | 0 | 0 / 0 = n/a |
| equal | 4 | different answer | 0 | 0 / 0 = n/a |
| equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 0 cases; the standard row was fresh in 0, came with an Age header in 0, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 0 cases; the standard row was fresh in 0, came with an Age header in 0, and of those 0 were the same answer as the early one.

Coins: all coins

| early bar vs reference | standard row's Age | standard answer | cases | standard rows equal to the reference |
|---|---|---|---|---|
| not equal | fresh | same answer | 0 | 0 / 0 = n/a |
| not equal | fresh | different answer | 6 | 6 / 6 = 100.00% |
| not equal | 0 | same answer | 0 | 0 / 0 = n/a |
| not equal | 0 | different answer | 1 | 1 / 1 = 100.00% |
| not equal | 1 | same answer | 0 | 0 / 0 = n/a |
| not equal | 1 | different answer | 0 | 0 / 0 = n/a |
| not equal | 2 | same answer | 0 | 0 / 0 = n/a |
| not equal | 2 | different answer | 1 | 1 / 1 = 100.00% |
| not equal | 3 | same answer | 0 | 0 / 0 = n/a |
| not equal | 3 | different answer | 1 | 1 / 1 = 100.00% |
| not equal | 4 | same answer | 0 | 0 / 0 = n/a |
| not equal | 4 | different answer | 2 | 2 / 2 = 100.00% |
| not equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| not equal | 5+ | different answer | 0 | 0 / 0 = n/a |
| equal | fresh | same answer | 735 | 735 / 735 = 100.00% |
| equal | fresh | different answer | 1 | 1 / 1 = 100.00% |
| equal | 0 | same answer | 120 | 120 / 120 = 100.00% |
| equal | 0 | different answer | 0 | 0 / 0 = n/a |
| equal | 1 | same answer | 39 | 39 / 39 = 100.00% |
| equal | 1 | different answer | 0 | 0 / 0 = n/a |
| equal | 2 | same answer | 101 | 101 / 101 = 100.00% |
| equal | 2 | different answer | 1 | 1 / 1 = 100.00% |
| equal | 3 | same answer | 167 | 167 / 167 = 100.00% |
| equal | 3 | different answer | 0 | 0 / 0 = n/a |
| equal | 4 | same answer | 731 | 731 / 731 = 100.00% |
| equal | 4 | different answer | 1 | 1 / 1 = 100.00% |
| equal | 5+ | same answer | 0 | 0 / 0 = n/a |
| equal | 5+ | different answer | 0 | 0 / 0 = n/a |

- After a fresh early answer that was NOT equal to the reference: 11 cases; the standard row was fresh in 6, came with an Age header in 5, and of those 0 were the same answer as the early one.
- After a fresh early answer that was equal to the reference: 1896 cases; the standard row was fresh in 736, came with an Age header in 1160, and of those 1158 were the same answer as the early one.

## What the tables show

Early pass, other coins, both runs together: Of the answers sent in second 1, 1650 of 2004 were equal to the list 95 s later; Of the answers sent in second 2, 3017 of 3441 were equal to the list 95 s later; Of the answers sent in second 3, 2989 of 3164 were equal to the list 95 s later; Of the answers sent in second 4, 856 of 885 were equal to the list 95 s later; Of the answers sent in second 5, 333 of 335 were equal to the list 95 s later; Of the answers sent in second 6, 166 of 168 were equal to the list 95 s later; Of the answers sent in second 7, 97 of 98 were equal to the list 95 s later. For BTC at its early place, of the answers sent (all seconds), 151 of 588 were equal to the list 95 s later. For the standard pass as a whole (all coins), of the answers sent, 10787 of 10788 were equal to the list 95 s later.

