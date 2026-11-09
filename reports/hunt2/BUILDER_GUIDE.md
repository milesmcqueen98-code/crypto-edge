# Edge hunt 2: builder guide

You build one or two ideas end to end under the pre-registration (reports/hunt2_prereg.md) and each idea's SPEC
(reports/hunt2/<id>/SPEC.md). Read both first. The rules below are binding; anything they don't cover is your
engineering judgement, written down in your REPORT.

## Where you work
- **Your worktree:** /home/claude/wt/<id>, branch hunt2/<id>, created from branch hunt2 at the freeze commit. It is a
  sparse checkout without the big data folders.
- **Data (read-only):** the main clone at **/home/claude/crypto-edge** (branch hunt2): data/minute (Coinbase spot
  1-minute, 2024-01 .. 2026-11-05, 39 coins), data/minute_early (2021 .. 2023, 14 coins), data/cfm (Coinbase perp
  1-minute, Jul 2025 ..), data/bitstamp, data/funding (Hyperliquid daily funding, May 2023 ..), data/alt,
  reports/ladder_v5, reports/ladder_v6x. Never write into /home/claude/crypto-edge except the shared ledger through
  h2gates.log_trial. Use absolute paths.
- **Code:** scripts/hunt2/<id>/. **Outputs:** reports/hunt2/<id>/. **Fetched data:** data/hunt2/<id>/ (commit only
  files under ~50 MB; raw prints stay in workflow artifacts).
- **Shared code (import, never edit):** scripts/hunt2/h2gates.py (every test, the ledger), scripts/hunt2/frozen_sim.py
  (the frozen ladder simulator with cost settings S/X1/X2 and the multiplier hook, for Path A),
  scripts/hunt2/prints.py (trade prints for a windows file, on Actions), scripts/hunt2/costs.py (the sleeve cost
  model and loaders, built on scripts/hunt/common.py). If a shared file has a bug, stop and report it in your final message.

## Heavy work runs on GitHub Actions
This machine has 2 CPUs and 7 GB shared by several builders. Anything over ~3 minutes of CPU, and any internet access,
runs on Actions. Exchange APIs are unreachable from here; only GitHub is. `gh` is not authenticated here; use the REST
API with curl and $GH_TOKEN:
1. Commit and push your branch: `git -C /home/claude/wt/<id> push -u origin hunt2/<id>`.
2. Dispatch the generic runner hunt2.yml (it can also download earlier runs' artifacts):
   ```
   curl -sS -X POST -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
     -H "Content-Type: application/json" \
     https://api.github.com/repos/milesmcqueen98-code/crypto-edge/actions/workflows/hunt2.yml/dispatches \
     -d '{"ref":"hunt2/<id>","inputs":{"script":"scripts/hunt2/prints.py","args":"reports/hunt2/<id>/windows.csv 0 6 out","commit":"","artifact":"out","tag":"<id>-p0","sparse":"scripts/hunt2 scripts/hunt scripts/wick_v4/fetch_trades.py reports/hunt2/<id>"}}'
   ```
   Inputs: `script`, `args`, `pip` (extra packages), `commit` (space-separated paths committed back to your branch:
   derived, small files), `artifact` (paths uploaded instead: raw prints; kept 21 days), `tag`, `sparse` (repo-relative
   paths to check out; use it, the full repo is 3+ GB), `art_runs` (space-separated run ids whose artifacts are
   downloaded into art/<run_id>/ before the script runs), `art_pattern` (artifact name glob, default `*`).
   The run's id is not returned by the dispatch call: list runs on your branch right after dispatching.
   - Shard long fetches (args `<shard> <n>`) and dispatch the shards in parallel; each runner has its own IP and rate
     limit (Coinbase public endpoints allow ~10 requests/s per IP; the fetchers pace at 7).
3. Watch: `curl -sS -H "Authorization: Bearer $GH_TOKEN" "https://api.github.com/repos/milesmcqueen98-code/crypto-edge/actions/runs?branch=hunt2/<id>&per_page=5"`.
   Logs: `.../actions/runs/<run_id>/logs` (zip). Wait with the Monitor tool (an until-loop on the run's status), not
   with sleep chains.
4. Get committed outputs: `git -C /home/claude/wt/<id> pull --rebase origin hunt2/<id>`. **Artifacts cannot be
   downloaded to this machine** (their storage host is blocked); run logs can (`.../actions/runs/<run_id>/logs`, a zip).
   So raw prints never come here: fetch them in one run (`artifact` = the raw files), then process them in a second
   hunt2.yml run with `"art_runs":"<run ids>"` (they land in art/<run_id>/), committing only derived per-event files.
   The parents' prints (every research parent, all eras, 30 min before to 2 min after the fill minute) are already
   fetched: runs listed in reports/hunt2/parents/RUNS.txt; DEV features in reports/hunt2/parents/features_dev.csv.
5. **Never let an Actions run commit anything computed on HOLD days before your freeze commit** (the first hunt had
   one such breach). A derive script must write DEV and HOLD outputs to separate files, and your pre-freeze runs commit
   only the DEV file.

## Rules that protect the hold-out
- **DEV** = 2025-01-01 .. 2026-03-31. **HOLD** = 2026-04-01 .. 2026-11-05 and 2022-01-01 .. 2023-12-31. 2021 and 2024
  may train models but are never scored.
- **Before your freeze** you may download data covering HOLD dates, but you may not compute, print or look at any P&L,
  fill count, hit rate, Sharpe, markout, feature-outcome relation or trade list on HOLD days. Feature DISTRIBUTIONS on
  HOLD days are also off limits (a threshold must be chosen on DEV only). Slice with `h2gates.is_dev`; call
  `h2gates.assert_dev_only` on every series you score; give every dev script an era argument fixed to `sel`.
- **Every DEV configuration you score is a trial.** Log it with `h2gates.log_trial(idea, variant, series, path, stat)`:
  - Path A: `series` = the candidate's DEV daily returns at X2 on $250K; `stat` = `h2gates.dev_screen_a(...)["t_diff"]`.
  - Path B: `series` = `h2gates.dev_book(sleeve_50k_2x)` (a = 0.8 book); `stat` = `h2gates.dev_screen_b(...)["t_alpha"]`.
  - The ledger is shared (reports/hunt2/trials.csv in the main clone); log_trial file-locks it, so call it from
    local Python. Budget: the SPEC's grid, never more than 16 trials.
- **Selection rule (fixed):** the highest DEV selection statistic among variants with enough events (SPEC); ties go to
  the simpler variant. Write reports/hunt2/<id>/frozen.json (variant, parameters, code commit hash, DEV numbers),
  commit and push it. That commit is the freeze.
- **After the freeze, read HOLD once.** Run the frozen variant over all scored days:
  - Path A: on the frozen simulator at X2 and X1, $250K: `h2gates.path_a(cand_x2, cand_x1, days)`.
  - Path B: the sleeve at 2x on $25K, $50K, $75K and $125K: `h2gates.path_b({25000: s25, 50000: s50, 75000: s75,
    125000: s125}, days)`; also report 1x for information.
  - Write reports/hunt2/<id>/gates.json and daily.parquet.
- **No redesign after reading HOLD.** A bug fix is allowed only as a logged deviation in your REPORT (what, why,
  effect), re-running the same frozen variant once.

## Modelling rules
- **Path A:** only through scripts/hunt2/frozen_sim.py (`daily(era, cost=..., mfac=...)`). scripts/hunt2/pathA.py
  has the standard workflow: `parents(era)` (the research parents), `dev_trial(idea, variant, skip_cells)` (one DEV
  trial at X2, logged) and, after the freeze only, `hold_read(idea, cells_by_era, out_dir)` (X2/X1/S on every era,
  daily.parquet, gates.json). For rules that switch bids off over time ranges (every coin in a window, a coin for C
  hours), build the T x NC array yourself: `A = frozen_sim.arrays(era)`; rows are `A["idx"]` (minutes), columns
  `A["coins"]`; then `frozen_sim.daily(era, cost=..., mfac=m)`. A filter that skips a
  signal sets m = frozen_sim.SKIP in that (minute, coin) cell; a size change sets m in (0, 2] and must respect the
  0.2% ADV cap (m above 1 only where the ladder v6 sizing `room` allows; prefer filters, m <= 1).
  Features for minute t use information available at t-1 minute (candles) or >= 1 second before the decision (prints).
- **Path B costs:** scripts/hunt2/costs.py only: spot VIP 1 0.06% maker / 0.125% taker + 2 bp half-spread on market
  orders (common.spot_cost_bp); perps $0.15 per contract per side + 2 bp commission (maker and taker) + 1.5x the
  measured half-spread on market orders (`costs.perp_cost_bp`), funding 1 bp per 8 h (`costs.perp_funding_bp`).
  2x for every gate; 1x for information. Perps only where the contract is worth >= $150 (`costs.contract_ok`).
- **Fills, resting orders:** the price must trade through the level by at least one tick; size <= theta x the volume
  strictly beyond the level while the price stays beyond it (prints where you have them; candles spread each minute's
  volume evenly over its range); theta 0.5, also report 0.25.
- **Taker entries and market exits:** the first print at least 2 s after the decision, worse by 1.5x the half-spread,
  plus the fee; with candles only, the next minute's open made worse the same way.
- **Live inputs only:** Coinbase (spot, perps), Bitstamp, Kraken, Gemini, Hyperliquid's info API, Binance
  announcement pages, public calendars (BLS, Fed, Deribit/CME expiry schedules), US ETF data. Binance/Bybit/OKX market
  data may be research context only.
- **Coinbase trade side:** `side` is the MAKER's side. "BUY" means an aggressive seller hit a resting bid.
- **Daily returns:** on the sleeve's capital, P&L booked on the exit day, calendar days, 0 when idle; gates subtract
  T-bills. Spot sleeves never exceed their capital in cash; perp sleeves never exceed 3x gross notional.

## What to hand back
1. reports/hunt2/<id>/REPORT.md (<= 1,500 words): mechanism; data used (dates, counts); every trial (variant, DEV
   statistic, events); the frozen variant; HOLD and full gate results at 2x (and 1x); years; capacity filled;
   fill-realism checks; weaknesses; verdict.
2. reports/hunt2/<id>/gates.json, frozen.json, daily.parquet (columns as the SPEC says).
3. Your branch pushed; its code reproduces every number.
4. Final message: a 10-line summary saying whether each gate passed, any shared-code problems, and any deviations.

Be honest. A clean "fails" is a valid and valuable result. Do not tune to pass.
