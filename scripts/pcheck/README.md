# Weekly perp paper check (side branch, not part of main)

Used for the Nov 13 2026 check-in on the two perp paper books (`paper_v2/` R2-08, `paper/` v1 control).

1. On a GitHub runner (the research workspace cannot reach Coinbase): dispatch `hunt2.yml` on this branch with
   `script=scripts/pcheck/fetch.py`, `args="<coins> <start> <end>"`, `pip=ccxt`, `commit=data/pcheck`, `sparse=scripts`.
   It writes final spot (`data/pcheck/<COIN>.parquet`) and perp (`<COIN>_perp.parquet`) 1-minute candles.
2. In a work folder `$PCHECK_DIR`: copy `paper/events.jsonl` to `v1/` and `paper_v2/events.jsonl` to `v2/`, run
   `python bot/paper_report.py $PCHECK_DIR/v1/events.jsonl` (and v2) so `trades.csv` lands beside each copy, and put the
   candles in `$PCHECK_DIR/pcheck/`.
3. `PCHECK_DIR=... python scripts/pcheck/spotcheck.py` re-runs the paper fill rule on final perp candles over every
   minute a bid rested and checks spot against each bid's spot-equivalent level (perp bid / basis at placement).
4. `PCHECK_DIR=... python scripts/pcheck/build.py` writes the dashboard datasets `paper_books.csv`, `paper_fills.csv`
   and `paper_cum.csv`.

Nov 13 result: the paper rule reproduced all 3 fills in each book; spot traded through the level in the same minute
on 1 of 3 fills per book (ENA, Nov 12). R2-08's ONDO and both books' PEPE fills came 1 and 7 minutes before spot;
v1's BCH fill (Nov 8, 21 contracts traded that minute) never had spot within 2% of the level.
