# Data step candidate: facts (candle requests between steps, `"candles_at_s"`)

Branch `owner/release-4`, from commit `cde92521`. Prepared as a candidate; whether a bot takes it is decided by the
owner. This file states facts only. Draft: the test results are filled in as the runs end.

## What changed, file by file
- **`bot/spot/engine.py`** (`bot/market.py` is not changed; the order code, the brokers, `fast_poll`'s own work,
  `start`, `catch_up`, `reconcile` and every safety check are not changed).
  - **The key.** `"candles_at_s"`: absent (the default) or a number of seconds from `confirm_s` + 5 (30 by default)
    to 50. Any other value, or the key without `"newest_bar": "trades"`, stops the engine at start-up
    (`ValueError`).
  - **The candle pass** (`candle_pass`): for the minute M open at the time, for each coin whose newest minute is
    built from trades (on `"trades_coins"`, or BTC and every coin without a list), `update_spot(M)` for that coin
    alone: the same request (the 6 minutes from five before the newest candle row, ending before M), the same merge
    by provenance, the same counters and the same bookkeeping (`_cmax`, the drop list, the window cut). The answer
    ends before M, so the pass never gives M a row. Resumable within a minute; a failed request is counted
    (`pre_error`) and left to the step; it never raises.
  - **When it runs** (`_wait_step`, called by `run` only with the key set): paper, in one go from second
    `candles_at_s`; live, inside the fast-poll loop: each turn of `fast_poll_s` seconds spends its waiting time on
    the pass's requests (one at least, more while the turn has room, judged by the pass's last request) and sleeps
    the rest, then the fast poll runs as before. No request of the pass starts unless it would end 3 s before the
    next step. With the key absent `run` takes exactly the old lines.
  - **In the step** (`_step_coins`): `update_spot` gets only the coins not built from trades and the coins built
    from trades whose pass for the minute that just closed did not happen or failed (`pre_missing`). After the
    trades pass, `_fetch_fallbacks` fetches on demand, with the step's own request (`update_spot(t)` for that coin),
    each covered coin whose trades bar could not be used (unverified, an error, the budget): `pre_ondemand`. After a
    refusal or a rate limit (`Refused`, `Limited`) in the trades pass, no on-demand request in that step.
    `trades_pass` only records which coins fell back and whether it stopped on a refusal; its requests, pace and
    counters are as before.
  - **`data_checks`:** with the key set, `candle_old` and `btc_candle_old` leave out a coin whose row for the minute
    is trades-built or a verified empty minute; every other case counts as before. Without the key the code is the
    old one.
  - **New counters** (heartbeat, only with the key): `pre_fetched`, `pre_error`, `pre_missing`, `pre_ondemand`,
    `step_candles` (candle requests the step made: `pre_missing` + `pre_ondemand` + the coins not on the list).
- **`bot/spot/candle_pass_test.py`** (new): 58 checks on a fake clock (below).
- **`bot/spot/live_sim_test.py`**: the made-up feed answers a candle request made mid-minute as the venue would
  (made at the request's own time, no row for the minute open then; requests at the step keep their old answer
  time, end + 8 s), records each request with its phase; the driver runs the candle pass at second `candles_at_s`
  after the fast poll; `over` puts a test's own settings on top of the inputs; `candles_at_s` is dropped where the
  test forces candle mode.
- **`bot/spot/live_sim_inputs_test.py`**: cases E (B's inputs with the setting the other way round) and, without the
  death, F0 and F1 (release 3's five coins on the list, without and with it); their decisions against the candle
  run; the counters; no candle request for a trades-built coin in a step after a pass; the modelled clock.
- **`bot/spot/replay_test.py`, `bot/spot/newest_bar_test.py`**: drop `candles_at_s` where they force candle mode.
- **`bot/spot/release_inputs.py`, `bot/spot/run.py`, `bot/spot/release_inputs_test.py`**: the three corrections
  (below) and, in the config commit, `candles_at_s` among the input keys and in the inputs line.
- **`bot/spot/tb_smoke.py`**: `--set KEY=JSON`, `--then KEY=JSON` (a second run on the same runner) and a per-step
  timing table.
- **`scripts/owner/release4/run_spot_tests.py`**: `candle_pass_test.py` added; the new result lines shown.
- **`bot/spot/README.md`**: a section "Candle requests between steps", the test lines; in the config commit the
  input keys and the emergency switch.
- **`bot/spot/config.json`, `bot/spot/config.w2.json`** (config commit): `"candles_at_s": 45`.
