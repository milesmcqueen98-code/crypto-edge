# Step probe: summary

- Runs read: run1 (16218 calls), run2 (16218 calls).
- A bin holds all requests sent in that second after q, BTC included. The BTC lines are in addition to the bins and hold all of BTC's requests of the pass (BTC is sent first in each pass).
- V is the share the engine's check accepted. E is the share of verified requests, whose minute has a verified reference, whose open, high, low and close all equal the reference's (no trades in both counts as equal).
- Reference: the same coin and minute asked again 95 s after the minute closed (reference pass), verified.

## All runs together

Bins: all coins, BTC included. Lines named BTC: BTC only. volume equal is the share of the equal bars whose volume is within 1e-9 relative.

| pass and bin | requests | V | E | with_ref | volume equal |
|---|---|---|---|---|---|
| early [1,2) | 2604 | 66.13% | 87.14% | 1718 | 97.53% |
| early [2,3) | 3441 | 83.96% | 95.19% | 2889 | 98.76% |
| early [3,4) | 3164 | 92.64% | 97.37% | 2931 | 99.37% |
| early [4,6) | 1220 | 100.00% | 97.46% | 1220 | 99.41% |
| early other | 371 | 99.73% | 99.46% | 370 | 100.00% |
| early BTC | 600 | 42.67% | 53.97% | 252 | 87.50% |
| standard [6,10) | 9544 | 99.99% | 99.99% | 9532 | 100.00% |
| standard other | 1256 | 100.00% | 100.00% | 1256 | 100.00% |
| standard BTC | 600 | 99.83% | 100.00% | 588 | 100.00% |

## Run run1

| pass and bin | requests | V | E | with_ref | volume equal |
|---|---|---|---|---|---|
| early [1,2) | 1157 | 74.42% | 83.24% | 859 | 97.20% |
| early [2,3) | 1961 | 90.11% | 93.38% | 1767 | 98.30% |
| early [3,4) | 1861 | 96.02% | 96.81% | 1787 | 99.08% |
| early [4,6) | 383 | 100.00% | 96.08% | 383 | 99.46% |
| early other | 38 | 100.00% | 100.00% | 38 | 100.00% |
| early BTC | 300 | 42.67% | 50.00% | 126 | 90.48% |
| standard [6,10) | 5202 | 99.98% | 100.00% | 5197 | 100.00% |
| standard other | 198 | 100.00% | 100.00% | 198 | 100.00% |
| standard BTC | 300 | 99.67% | 100.00% | 295 | 100.00% |

## Run run2

| pass and bin | requests | V | E | with_ref | volume equal |
|---|---|---|---|---|---|
| early [1,2) | 1447 | 59.50% | 91.04% | 859 | 97.83% |
| early [2,3) | 1480 | 75.81% | 98.04% | 1122 | 99.45% |
| early [3,4) | 1303 | 87.80% | 98.25% | 1144 | 99.82% |
| early [4,6) | 837 | 100.00% | 98.09% | 837 | 99.39% |
| early other | 333 | 99.70% | 99.40% | 332 | 100.00% |
| early BTC | 300 | 42.67% | 57.94% | 126 | 84.93% |
| standard [6,10) | 4342 | 100.00% | 99.98% | 4335 | 100.00% |
| standard other | 1058 | 100.00% | 100.00% | 1058 | 100.00% |
| standard BTC | 300 | 100.00% | 100.00% | 293 | 100.00% |

## Why requests were not verified (all runs together)

- early [1,2): 882 of 2604 not verified (stale_first_page 882); 4 verified without a reference.
- early [2,3): 552 of 3441 not verified (stale_first_page 552); 0 verified without a reference.
- early [3,4): 233 of 3164 not verified (stale_first_page 233); 0 verified without a reference.
- early [4,6): 0 of 1220 not verified (none); 0 verified without a reference.
- early other: 1 of 371 not verified (error 1); 0 verified without a reference.
- early BTC: 344 of 600 not verified (stale_first_page 344); 4 verified without a reference.
- standard [6,10): 1 of 9544 not verified (page_cap 1); 11 verified without a reference.
- standard other: 0 of 1256 not verified (none); 0 verified without a reference.
- standard BTC: 1 of 600 not verified (page_cap 1); 11 verified without a reference.

## How long a request takes

Median / 90th percentile of dur_s in seconds (linear interpolation), all runs together.

| coin | early | standard | reference |
|---|---|---|---|
| BTC | 0.330 / 0.811 | 0.425 / 1.025 | 1.206 / 2.780 |
| AAVE | 0.158 / 0.259 | 0.157 / 0.290 | 0.200 / 0.433 |
| BCH | 0.170 / 0.402 | 0.144 / 0.308 | 0.166 / 0.493 |
| DOGE | 0.153 / 0.226 | 0.152 / 0.253 | 0.152 / 0.219 |
| ENA | 0.185 / 0.422 | 0.143 / 0.258 | 0.189 / 0.403 |
| ETH | 0.137 / 0.173 | 0.141 / 0.171 | 0.100 / 0.398 |
| HBAR | 0.144 / 0.381 | 0.150 / 0.323 | 0.155 / 0.306 |
| HYPE | 0.134 / 0.249 | 0.136 / 0.182 | 0.114 / 0.188 |
| LINK | 0.154 / 0.249 | 0.149 / 0.253 | 0.157 / 0.258 |
| LTC | 0.138 / 0.195 | 0.137 / 0.197 | 0.133 / 0.192 |
| NEAR | 0.142 / 0.256 | 0.142 / 0.208 | 0.135 / 0.199 |
| ONDO | 0.142 / 0.299 | 0.143 / 0.240 | 0.144 / 0.368 |
| PEPE | 0.131 / 0.208 | 0.143 / 0.286 | 0.120 / 0.293 |
| SOL | 0.144 / 0.184 | 0.143 / 0.180 | 0.142 / 0.200 |
| SUI | 0.116 / 0.239 | 0.141 / 0.233 | 0.118 / 0.280 |
| XLM | 0.208 / 0.393 | 0.146 / 0.304 | 0.163 / 0.313 |
| XRP | 0.141 / 0.160 | 0.143 / 0.163 | 0.144 / 0.277 |
| ZEC | 0.141 / 0.270 | 0.140 / 0.205 | 0.133 / 0.266 |

## How long a pass takes

First send to last return, per pass (an upper bound: it adds the last call's own pace wait, at most about 0.14 s, because calls.csv records the first send, not the start of the call). Median / 90th percentile in seconds.

| run | pass | passes | median | 90th pct |
|---|---|---|---|---|
| run1 | early | 300 | 3.139 | 3.753 |
| run1 | reference | 301 | 4.203 | 6.182 |
| run1 | standard | 300 | 3.164 | 4.046 |
| run2 | early | 300 | 3.574 | 6.818 |
| run2 | reference | 301 | 4.477 | 8.278 |
| run2 | standard | 300 | 3.263 | 7.525 |
| all | early | 600 | 3.218 | 5.705 |
| all | reference | 602 | 4.257 | 7.486 |
| all | standard | 600 | 3.181 | 6.330 |

