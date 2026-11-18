# Standstill candidate: facts (`"standstill_candles"`)

Branch `owner/standstill`, from 46e1ee84 (the release 5 candidate plus the balance-look change). Nov 18 2026.

## Why
On Nov 17 2026, 21:19 to 21:57 UTC, the venue's public trades list showed no new trade for almost any coin while
its candles kept coming. The build under test (`"newest_bar": "trades"` for all 18 coins, `"trades_rows":
"candle_after"`, `"candles_at_s": 45`, `"stale_guard": true`) takes the newest minute from the trades list inside the
step and asks for candles only between steps. Every trades answer was "verified, no trade in the minute"
(`tb_empty`), so the step had no row for the newest minute of any coin, BTC included; the stale guard stopped new
bids, and for 38 minutes the two paper books on this build placed no bid. The two books that ask for the candle
inside the step (release 3's way) carried on with candle rows.

## The trigger
BTC trades in every minute. A verified trades answer with no BTC trade in the minute that just closed means the
trades list is behind (or trading has stopped). Only BTC's answer is a trigger.

## What the step does (with the setting true)
1. After the trades pass, if BTC's answer for the closed minute m was verified empty, BTC's "verified empty" mark for
   m is taken away and BTC's candle for m is judged as a candle row: the row the step's own candle request brought,
   or, when the step left BTC out (its candle pass had run), one candle request made then, on demand
   (`pre_ondemand`, `step_candles`).
2. If that candle has a traded row for m, the trades list stands still: `tb_frozen` is counted once for the step;
   every other coin whose trades answer in this pass was verified empty and which the step left out loses its mark
   and gets its candle on demand (one request each, counted the same way). The stale guard then judges all these rows
   as candle rows (`_row_ok`: an answer made after m ended; an old answer skips that coin for the minute through
   `_skip_old`; BTC's row must exist, be traded and come from an answer made after m ended).
3. If BTC's candle has no traded row for m, the mark is put back: BTC is stale and the guard stops new bids, as
   before.
4. After a refusal or a rate limit in the trades pass (`_fb_stop`) nothing is done, as before.

Everything else stays: the trades pass and its fallbacks, the candle pass between steps, the order logic. A verified
empty answer for any coin other than BTC is never a trigger.

**Where it has an effect.** Only with `"newest_bar": "trades"` and `"candles_at_s"` set. Anywhere else the step asks
every coin's candle itself already, which is what the setting would bring, so it is inert there: no warning, no
event, no request. No warning is given because a `warning` event reaches the phone at every start, and an inert
setting is not a fault. A value that is not true or false stops the engine at start-up in every mode (`ValueError`).

**One difference from the setting off.** When the step had asked BTC's candle itself (the candle pass had not run
for BTC, for instance the first step after a start) and BTC's trades answer is verified empty, BTC's row is judged by
the age of that candle answer: an answer made before m ended makes BTC stale for the minute. With the setting off the
verified-empty mark lets that row pass.

**Cost.** One more request in a step whose BTC minute is empty in the trades list; up to 18 (BTC and every coin) in
a standstill step. Modelled clock (the inputs test's model: start at 6 s, 0.19 s per candle request, 0.58 s for BTC's
trades request, 0.15 s for each other coin's): a standstill step ends at about 12.55 s, as release 3's way does (case
E: 12.55 s), against 9.13 s median for B.

**Where it lives.** `engine.py` (`__post_init__`, `trades_pass` keeps the coins verified empty, `_standstill`,
called in `step` after `_fetch_fallbacks`); `release_inputs.py` `INPUT_KEYS` (the live bot takes it from the
release); `config.json` `"standstill_candles": true`. No other config file changes.

## Nothing moved without a standstill (inputs simulation, Oct 10 2025 20:00 to Oct 11 02:00, no death)
Before: the tree of 46e1ee84 exported to a scratch folder. After: this branch with the setting true.

| case | before | after | event log (heartbeats included, order ids masked) |
|---|---|---|---|
| A | 111 entries, 134 exits, $11,723.34 | the same | 1506 lines, identical |
| B | the same | the same | 1506, identical |
| C1 | the same | the same | 1522, identical |
| C2 | the same | the same | 1522, identical |
| E | the same | the same | 1506, identical |
| F0 | the same | the same | 1506, identical |
| F1 | the same | the same | 1506, identical |
| D | 111 entries, 134 exits, $11,717.63 | the same | 1506, identical |

The 37 PASS lines and `LIVE-PATH INPUTS TEST PASSED` are the same before and after. The plain live-path test passes:
111 entries and $11,723.34; with `--death=2025-10-10 21:10`, 109 and $8,421.28 (the numbers of the balance-look
note).

## A standstill in the fake feed (case G)
The fake trades list answers "verified, no trade in that minute" for every coin from 21:30 to 22:07 (38 minutes,
90 minutes after the start) while the candles go on. B's inputs.

| run | entries | exits | P&L | tb_empty | tb_frozen | btc_stale | skip_old | pre_ondemand | step_candles | pre_missing | stale_input in span | arm in span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A (candle run) | 111 | 134 | $11,723.34 | | | | | | | | 0 | |
| G1 setting true | 111 | 134 | $11,723.34 | 1135 | 38 | 0 | 0 | 684 | 702 | 18 | 0 | 42 |
| G0 setting absent | 86 | 94 | $6,088.73 | 1135 | 0 | 38 | 0 | 0 | 18 | 18 | 38 | 0 |
| G2 true, no BTC candle row in the span | 80 | 99 | $10,328.78 | 1135 | 0 | 38 | 0 | 38 | 56 | 18 | 38 | 0 |

G1's event log equals A's line for line (1489 lines, heartbeats aside, order ids masked): in a standstill the build
decides exactly as the candle run does. 684 = 38 steps times 18 candle requests (BTC and 17 coins), all on demand.
G0 is today's behaviour: a `stale_input` for every step in the span and no new bid there. G2 behaves as G0 in the
span (one BTC request per step, which finds no row). The counters are summed over the heartbeats.

## Tests (run here, one at a time)
- `live_sim_inputs_test.py` window, with G: 50 PASS, `LIVE-PATH INPUTS TEST PASSED`.
- `live_sim_inputs_test.py` window `--death=2025-10-10 21:10`: 22 PASS, `LIVE-PATH INPUTS TEST PASSED` (G is not run
  with the death).
- `live_sim_test.py` window: `LIVE-PATH TEST PASSED` (111, $11,723.34); with the death: `LIVE-PATH TEST PASSED` (109,
  $8,421.28).
- `order_path_test.py` window: 23 PASS, `ORDER PATH TEST PASSED`; with the death: 23 PASS, `ORDER PATH TEST PASSED`.
- `standstill_test.py` (new): 68 PASS, `STANDSTILL TEST PASSED`.
- `release_inputs_test.py`: 90 PASS, `RELEASE INPUTS TEST PASSED` (one expectation changed: the list of inherited
  names now holds `standstill_candles` after `candles_at_s`).
- `candle_pass_test.py` 99 PASS, `candle_after_test.py` 30, `newest_bar_test.py` 73, `trades_bar_test.py` 47,
  `merge_test.py` 21, `balance_look_test.py` 26, `order_path_unit_test.py` 116, `deploy/watchdog_test.py` 31,
  `wickctl_test.sh` PASSED: each the same count as on 46e1ee84, all passed.

Not run here: `replay_test.py` (paper parity); it runs in the full suite on a runner
(`scripts/owner/input_release/run_spot_tests.py`, which now also runs `standstill_test.py`).

## Limits
- A standstill that spares BTC's list is not seen: only BTC's answer is a trigger.
- The rows taken in a standstill are first-seen candles, as on release 3 (`"candle_after"` replaces them with the
  confirmed candle later, as for any row).
- A standstill of the candles too stops the bids as before (G2).
- The fake feed's standstill is total (every coin, every minute of the span); a partial one, where some coins' lists
  still move, was checked only on the small fake market of `standstill_test.py`.
- The cost figures are the inputs test's model, not a measurement.
