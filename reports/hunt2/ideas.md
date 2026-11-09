# Edge hunt 2: the idea list (DRAFT until the freeze)

The test for every idea: **who is forced (or eager) to trade, and why does a slow liquidity provider or follower get
paid?** Sources: the three desk lenses (HRT microstructure, SIG options/game theory, Renaissance many weak signals),
research memos R1–R4 (reports/hunt2/research/), and the record of every earlier round (rejected mechanisms are not
re-proposed unless the mechanism is new).

## How ideas are scored (prior, 0–12; fixed before any build)
- **Mechanism (0–3):** a named forced or eager counterparty, and a reason it persists.
- **Testable on trade data now (0–3):** free trade-level (or event-level) history covering DEV and at least one HOLD
  era, with enough events for t ≥ 2 to be reachable.
- **Live-implementable from New York (0–2):** every input live-available to a US bot; Coinbase supports the orders.
- **New (0–2):** a new mechanism, or new information for the ladder; 0 for a re-test of a rejected mechanism.
- **Clears 2× costs (0–2):** the plausible edge per trade is above the round trip at 2× (maker/maker ~24 bp spot;
  taker/taker 20–50 bp on perps; Path A filters pay no new costs).
Ties go to Path A (it pays no new costs and its test is head-to-head), then to category diversity.

Status key: **BUILD** = one of the ten builds · **alt** = next in line · **merged** = tested inside a build ·
**blocked** = no honest test or trade now · **dead** = an earlier round killed the mechanism · **low** = low power or
low prior.

(The table is filled in below once memos R1–R3 are in.)
