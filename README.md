# FX Strategy Research Framework

A **research-only** backtesting framework that systematically evaluates a wide range of
foreign-exchange strategies on major currency pairs with **honest, retail-realistic costs**.
Built on the same disciplined methodology as my equities and crypto research — the emphasis is
**rigor over P&L**: test many ideas, model costs faithfully, and reject what doesn't survive
out-of-sample.

> **Research only.** Nothing here places trades, paper or real.

---

## What it tests
Thirteen-plus distinct strategy families, each with its own pre-registered rules and gate,
run across a major-pair universe (EUR/USD, USD/JPY, GBP/USD, and a wider 7-pair basket):

- Previous-day level bounce → Fibonacci-target entries
- Break-and-retest / price-action setups
- Opening-range breakout (with volatility, USD-regime, and relative-strength filters)
- Daily and regime-conditioned trend following
- News-reaction, statistical-arbitrage (pairs), and SMC basket variants

## Cost realism (why FX is a fair test)
Retail FX spreads are modeled conservatively per pair (e.g., EUR/USD 1.4 pips, GBP/USD 2.0
pips), charged as half-spread per side, and setups whose stop is smaller than ~2× round-trip
cost are skipped. This is deliberately harsh — a signal only "passes" if it clears the gate
*after* realistic costs, not on frictionless assumptions.

## Methodology (the differentiator)
- **Pre-registration** of rules and success gates before each run.
- **Train / validation split**, judged **once** on an untouched holdout.
- **Per-instrument breakdown** — an edge must make economic sense on each pair, not just in
  aggregate.
- **No-lookahead** event-driven engine; costs charged on every trade.

## Honest results
Most families were **rejected** — e.g., the ORB filters that worked on equities did *not*
reproduce a positive edge on an FX basket after costs (negative expectancy across sessions).
A small number showed modest, capacity-limited signals worth flagging but not deploying. The
value is the framework and the honest, per-market verdicts recorded in `reports/`.

## Architecture & stack
Python (pandas, NumPy) · OANDA market data · GitHub Actions (scheduled research) ·
Slack reporting · YAML-configured pairs, costs, and grids · offline unit tests.

## Repository layout
- `src/backtest/` — thirteen-plus strategy backtests + shared metrics
- `src/` — OANDA data layer, Slack reporting
- `reports/` — timestamped, per-strategy research reports (the audit trail)
- `tests/` — offline unit tests

---
*A study in FX systematic research: breadth of hypotheses, faithful cost modeling, and honest
out-of-sample verdicts — reported whether or not they worked.*
