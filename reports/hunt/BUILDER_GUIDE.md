# Edge hunt: builder guide (wave 2)

You build one idea end to end under the pre-registration (reports/hunt_prereg.md) and your idea's SPEC
(reports/hunt/<id>/SPEC.md). Read both first. The rules below are binding; anything they don't cover is your
engineering judgement, written down in your REPORT.

## Where you work
- **Your worktree:** /home/claude/wt/<id>, branch hunt/<id>. It is a sparse checkout without data.
- **Data (read-only):** read existing data from the main clone at **/home/claude/crypto-edge/data/** and its reports.
  Never write into /home/claude/crypto-edge. Use absolute paths.
- **Code:** scripts/hunt/<id>/.
- **Outputs:** reports/hunt/<id>/.
- **Fetched data:** data/hunt/<id>/ in your worktree. Commit a file only if it is under ~50 MB; keep raw trade dumps
  as workflow artifacts or aggregate them on the runner.
- **Shared code:** import scripts/hunt/gates.py (every test) and scripts/hunt/common.py (loaders, the cost model,
  the trade fetcher) from your worktree. Do not edit shared files. If one has a bug, stop and report it in your final
  message.

## Heavy work runs on GitHub Actions, not here
This machine has 2 CPUs and 7 GB shared by several builders. Anything over ~2 minutes of CPU, or any internet
access, runs on Actions. Exchange APIs are unreachable from here; only GitHub is.

1. **Commit and push your branch:**
   `git -C /home/claude/wt/<id> push -u origin hunt/<id>`
2. **Dispatch:**
   `gh workflow run hunt.yml --ref hunt/<id> -f script=scripts/hunt/<id>/x.py -f args="..." -f commit="reports/hunt/<id> data/hunt/<id>" -f tag=<id>-x`
   - Add `-f sparse="scripts edge reports/hunt data/cfm data/minute"` to check out only what you need. Space
     separated, repo-relative; use it unless you need most of data/.
   - Add `-f pip="..."` for extra packages.
3. **Watch it:** `gh run list --workflow hunt.yml --branch hunt/<id> -L 3`. When it is done, read
   `gh run view <id> --log` (use `--log-failed` on failure).
4. **Get the outputs:** `git -C /home/claude/wt/<id> pull --rebase origin hunt/<id>`.

- The runner has 4 vCPUs, 16 GB and a 350-minute limit. Split long fetches into shards (args) and dispatch them in
  parallel. Each runner has its own IP and rate limit.
- Coinbase public endpoints allow about 10 requests/second per IP. common.TradeFetcher paces at 8.
- Waiting on a run: use `gh run watch <id> --exit-status`, or poll with your Monitor tool. Don't busy-loop on sleep.

## Rules that protect the hold-out
- **DEV:** every scored day before 2026-06-01. **HOLD:** 2026-06-01 .. 2026-11-05. **Scored days:** 2022–2023 and
  2025-01-01 .. 2026-11-05 (gates.ERA_DAYS); 2024 only trains models.
- **Before the freeze:** you may download data covering HOLD dates. You may not compute, print or look at any P&L,
  fill count, hit rate, Sharpe or trade list on HOLD days.
  - Slice with `gates.HOLD0`.
  - Call `gates.assert_dev_only` on every series you score.
  - Write dev scripts so they cannot touch HOLD by accident: an END date argument fixed to 2026-05-31.
- **Every DEV configuration you score is a trial.** Log it with `gates.log_trial(idea, variant, dev_book, note=...)`.
  - `dev_book` is `gates.dev_book(sleeve_30k_2x)`: the a = 0.7 book over your DEV days, the sleeve at 2× costs on
    $30K.
  - Also report `gates.dev_screen(...)`.
  - The ledger is shared: reports/hunt/trials.csv in the MAIN clone (/home/claude/crypto-edge). log_trial
    file-locks it, so call it from local Python, not on Actions.
  - If a trial ran on Actions, bring its DEV daily series back and log it locally.
  - Budget: at most 24 trials. Spend them on the SPEC's grid, not on fishing.
- **Selection rule:**
  - Pick the highest DEV alpha t among variants with enough trades (SPEC). Ties go to the simpler variant.
  - Write reports/hunt/<id>/frozen.json: the variant, its parameters, the code commit hash and the DEV numbers.
  - Commit and push it. That commit is the freeze.
- **After the freeze, read HOLD once.** Run the frozen variant over all scored days at 2× costs (and 1× for
  information), on $30K and $50K. Then call `gates.path_b({30000: s30, 50000: s50}, days=<your scored days>)` (and
  `gates.path_a` if the SPEC says so). Write reports/hunt/<id>/gates.json.
- **No redesign after reading HOLD.** A bug fix is allowed only if you log it as a deviation in your REPORT (what,
  why, effect) and re-run the same frozen variant once.

## Modelling rules (from the pre-registration)
- **Costs:** common.py only. 2× for every gate; 1× for information.
- **Fills, resting orders:**
  - The price must trade through the level by at least one tick.
  - Size ≤ θ × through-volume: volume strictly beyond the level while the price stays beyond it; θ = 0.5, and also
    report 0.25.
  - With trade prints, use the prints. With candles, spread each candle's volume evenly over its range.
- **Latency:** decide on information at least 1 s old (trades) or 1 minute old (candles). Taker entries and market
  exits fill at the first trade at least 2 s after the decision, worse by 1.5× the half-spread, plus the fee; with
  candles, at the next minute's open, made worse the same way.
- **Live inputs only:** Coinbase, Bitstamp, Kraken, Gemini, Hyperliquid's info API, Binance announcement pages.
  Binance/Bybit/OKX market data may only be research context, never a model input.
- **Daily returns:** on the sleeve's capital, P&L booked on the exit day, calendar days, 0 when idle.
  - Gates subtract T-bills, so a sleeve that holds cash is not credited with interest.
  - If positions can be open overnight with a large mark-to-market swing, also report a marked-to-market drawdown.
- **Capital and leverage:** the SPEC sets them. Never exceed the sleeve's capital in cash use (spot) or 3× gross
  notional on perps.
- **Coinbase trade side:** `side` is the maker's side. "BUY" means an aggressive seller hit a bid.

## What to hand back
1. **reports/hunt/<id>/REPORT.md** (≤ 1,500 words), covering:
   - the mechanism;
   - the data actually used, with dates and counts;
   - every trial (a table of variant, DEV sleeve Sharpe, DEV alpha t, trades);
   - the frozen variant;
   - HOLD and all-day gate results at 2× (and 1×);
   - years;
   - capacity actually filled;
   - the fill-realism checks you ran;
   - weaknesses;
   - your verdict.
2. **reports/hunt/<id>/gates.json** and **frozen.json**; daily series in **reports/hunt/<id>/daily.parquet**:
   columns `s30_2x, s50_2x, s30_1x, s50_1x` over your scored days.
3. **Branch pushed;** the code in it reproduces every number.
4. **Final message:** a 10-line summary. It must say whether each gate passed, list any shared-code problems, and
   list deviations.

Be honest. A clean "fails" is a valid and valuable result. Do not tune to pass.
