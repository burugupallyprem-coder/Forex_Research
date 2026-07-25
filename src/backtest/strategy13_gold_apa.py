"""Advanced Price Action (wedge-breakout continuation) on GOLD - RESEARCH ONLY.

PRE-REGISTERED 2026-07-23, from Peter's "Trading Coastal" screenshot. The pattern:
a prior up-move stalls (3 drives into resistance), price pulls back in a FALLING
WEDGE (lower highs) into a demand zone, then a LONG BAR (large-range bullish
candle) breaks out of the wedge - that bar is the entry. Stop below the demand
zone; targets are a measured move up (TP1/TP2).

Mechanical PROXY (declared - literal "3 drives" and exact wedge geometry are
discretionary and not detectable cleanly):
  - Falling wedge / pullback: over the last `pullback_len` bars the highs are
    DECLINING - max high of the earlier part of the window > the recent
    `breakout_lookback` highs (earlier_high > recent_high). Demand zone = the
    window's low.
  - Long-bar breakout (long): current bar is bullish, its range >= atr_mult x ATR,
    and it CLOSES above the recent highs (recent_high). Optional: close > EMA200.
  - Entry next bar open +/- half-spread; stop = demand_low - stop_buf_atr x ATR;
    target = entry + target_r x risk (measured-move proxy). Long-and-short
    symmetric (bearish = rising wedge + long red breakdown bar). One-to-two
    trades/day; active hours only; flat 21:00 UTC; stop before target; gaps fill
    at the open on the bad side; 0.5% risk; cost floor.

Runs BOTH timeframes as separate studies: M1 (scalping) and M5 (intraday). For
each, SELECT the grid winner on the already-spent window (2024-07 -> 2025-12),
judge ONCE on the UNTOUCHED holdout (<= 2024-06-30, back to history_start) with
gate + walk-forward + bootstrap CI + gross-vs-net + slippage x2. 2026 shown as a
contaminated reference only.

Run: python -m src.backtest.strategy13_gold_apa
"""

import itertools
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src import oanda_data, slackbot
from src.backtest import metrics
from src.backtest.strategy10_boring_scalp import Trade, size_units, usd_pnl_factor
from src.backtest.strategy10_gold import between, bootstrap_ci, walk_forward

ROOT = Path(__file__).resolve().parent.parent.parent


def load_config():
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def expand_grid(grid):
    keys = sorted(grid.keys())
    return [dict(zip(keys, values))
            for values in itertools.product(*(grid[k] for k in keys))]


def _features(df, cfg):
    atr_len = int(cfg["atr_len"]); plen = int(cfg["pullback_len"])
    brk = int(cfg["breakout_lookback"]); ema_len = int(cfg["ema_len"])
    prevc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prevc).abs(),
                    (df["low"] - prevc).abs()], axis=1).max(axis=1)
    return {
        "atr": tr.rolling(atr_len).mean().values,
        "ema": df["close"].ewm(span=ema_len, adjust=False).mean().values,
        "recent_high": df["high"].rolling(brk).max().shift(1).values,
        "recent_low": df["low"].rolling(brk).min().shift(1).values,
        "earlier_high": df["high"].rolling(plen).max().shift(brk).values,
        "earlier_low": df["low"].rolling(plen).min().shift(brk).values,
        "demand_low": df["low"].rolling(plen).min().values,
        "supply_high": df["high"].rolling(plen).max().values,
    }


def simulate_apa(df, inst, params, cfg):
    atr_mult = float(params["atr_mult"]); target_r = float(params["target_r"])
    use_trend = bool(params["trend_filter"])
    hs = float(cfg["half_spread"][inst])
    ss = int(cfg["session_start_min"]); cutoff = int(cfg["entry_cutoff_min"]); flat = int(cfg["flat_min"])
    stop_buf = float(cfg["stop_buf_atr"]); max_td = int(cfg["max_trades_day"])
    min_mult = float(cfg.get("min_stop_cost_mult", 2.0))
    df = df.reset_index(drop=True)
    n = len(df)
    o = df["open"].values; h = df["high"].values; lo = df["low"].values; c = df["close"].values
    ts = df["ts"]
    minute = (ts.dt.hour * 60 + ts.dt.minute).values
    date = ts.dt.strftime("%Y-%m-%d").values
    F = _features(df, cfg)
    atr = F["atr"]

    trades = []; pos = None; pending = None; cur = None; td = 0

    def valid(*xs):
        return all(x == x for x in xs)   # NaN check

    def close_trade(i, exit_px, reason):
        d = pos["side"]; risk = abs(pos["entry"] - pos["stop"])
        f = usd_pnl_factor(inst, pos["entry"])
        pnl = (exit_px - pos["entry"]) * pos["shares"] * d * f
        trades.append(Trade(
            symbol=inst, strategy="strategy13_gold_apa", date=str(ts.iloc[i].date()),
            entry_time=pos["entry_time"], exit_time=str(ts.iloc[i].time()),
            entry=round(pos["entry"], 4), exit=round(exit_px, 4), shares=pos["shares"],
            stop=round(pos["stop"], 4), target=round(pos["target"], 4), pnl=round(pnl, 2),
            r_multiple=round((exit_px - pos["entry"]) * d / risk, 3) if risk > 0 else 0.0,
            exit_reason=reason, signal_reason=pos["reason"]))

    for i in range(n):
        m = minute[i]
        if date[i] != cur:
            cur = date[i]; td = 0; pending = None

        if pos is not None and m >= flat:
            close_trade(i, o[i] - pos["side"] * hs, "flat"); pos = None

        if pos is None and pending is not None and m < flat:
            side = pending["side"]; entry = o[i] + side * hs; stop = pending["stop"]
            risk = (entry - stop) * side
            if risk > 0 and risk >= min_mult * 2 * hs:
                units = size_units(entry, stop, inst, cfg)
                if units > 0:
                    pos = {"side": side, "entry": entry, "stop": stop,
                           "target": entry + side * target_r * risk, "shares": units,
                           "entry_time": str(ts.iloc[i].time()), "reason": pending["reason"]}
                    td += 1
        pending = None

        if pos is not None:
            d = pos["side"]
            if d == 1 and lo[i] <= pos["stop"]:
                close_trade(i, min(o[i], pos["stop"]) - hs, "stop"); pos = None
            elif d == 1 and h[i] >= pos["target"]:
                close_trade(i, max(o[i], pos["target"]) - hs, "target"); pos = None
            elif d == -1 and h[i] >= pos["stop"]:
                close_trade(i, max(o[i], pos["stop"]) + hs, "stop"); pos = None
            elif d == -1 and lo[i] <= pos["target"]:
                close_trade(i, min(o[i], pos["target"]) + hs, "target"); pos = None

        if (pos is None and pending is None and td < max_td and ss <= m < cutoff
                and i < n - 1 and date[i + 1] == date[i]):
            a = atr[i]
            rh, rl = F["recent_high"][i], F["recent_low"][i]
            eh, el = F["earlier_high"][i], F["earlier_low"][i]
            dl, sh, em = F["demand_low"][i], F["supply_high"][i], F["ema"][i]
            if valid(a, rh, rl, eh, el, dl, sh) and a > 0:
                rng = h[i] - lo[i]
                big = rng >= atr_mult * a
                bull = (big and c[i] > o[i] and c[i] > rh and eh > rh
                        and (not use_trend or c[i] > em))
                bear = (big and c[i] < o[i] and c[i] < rl and el < rl
                        and (not use_trend or c[i] < em))
                if bull:
                    pending = {"side": 1, "stop": dl - stop_buf * a, "reason": "apa_wedge_break_long"}
                elif bear:
                    pending = {"side": -1, "stop": sh + stop_buf * a, "reason": "apa_wedge_break_short"}

    if pos is not None and n > 0:
        close_trade(n - 1, float(c[n - 1]) - pos["side"] * hs, "data_end")
    return trades


def sim_cfg(g, half_spread):
    d = {"risk": {"equity": 100000, "risk_pct": 0.5, "max_position_pct": 20},
         "half_spread": {g["instrument"]: half_spread}}
    for k in ("atr_len", "pullback_len", "breakout_lookback", "ema_len", "stop_buf_atr",
              "session_start_min", "entry_cutoff_min", "flat_min", "max_trades_day",
              "min_stop_cost_mult"):
        d[k] = g[k]
    return d


def study(df, inst, g, half_spread, tf):
    """One timeframe: select on spent window, judge on untouched holdout."""
    sel_lo = pd.to_datetime(g["select_start"]).date()
    sel_hi = pd.to_datetime(g["select_end"]).date()
    hold_hi = pd.to_datetime(g["holdout_end"]).date()
    gate = g["gate"]
    combos = expand_grid(g["grid"])
    base = sim_cfg(g, half_spread)

    scored = []
    for combo in combos:
        tr = simulate_apa(df, inst, combo, base)
        ms = metrics.summarize(between(tr, sel_lo, sel_hi))
        scored.append((combo, ms, tr))
    lines = [f"### {tf}", "", "Selection grid (spent window):"]
    for combo, m, _ in scored:
        cs = ", ".join(f"{k}={v}" for k, v in sorted(combo.items()))
        lines.append(f"- {cs}: {m.get('trades',0)}t, {m.get('expectancy_r',0)}R, PF {m.get('profit_factor',0)}")

    eligible = [(c, m, tr) for c, m, tr in scored if m.get("trades", 0) >= g["min_select_trades"]]
    if not eligible:
        lines += ["", f"Verdict: SKIP - no combo reached {g['min_select_trades']} selection trades", ""]
        return lines, f"{tf}: SKIP (thin selection)"
    eligible.sort(key=lambda x: x[1]["expectancy_r"], reverse=True)
    win, sel_m, wt = eligible[0]
    cs = ", ".join(f"{k}={v}" for k, v in sorted(win.items()))
    hold = between(wt, hi=hold_hi)
    hm = metrics.summarize(hold)
    if hm.get("trades", 0) == 0:
        lines += ["", f"Verdict: FAIL - winner {cs} produced 0 holdout trades", ""]
        return lines, f"{tf}: FAIL (0 holdout trades)"

    gross = simulate_apa(df, inst, win, {**base, "half_spread": {inst: 0.0}})
    gm = metrics.summarize(between(gross, hi=hold_hi))
    ref = metrics.summarize(between(wt, lo=pd.to_datetime("2026-01-01").date()))
    verdict, why = metrics.gate_verdict(hm, gate)
    wf_pos, wf_tot, wf_per = walk_forward(hold, int(g["walkforward_folds"]))
    if verdict == "PASS" and not (wf_tot and wf_pos / wf_tot >= float(g["min_positive_frac"])):
        verdict = "FAIL"
        why = (f"{why}; " if why != "all gate checks met" else "") + f"walk-forward {wf_pos}/{wf_tot} folds+"
    blo, bhi, frac_pos, _ = bootstrap_ci(hold)
    sens = []
    for sm in g.get("slippage_mult", [1.0]):
        st = simulate_apa(df, inst, win, {**base, "half_spread": {inst: half_spread * sm}})
        sens.append(f"{sm}x -> {metrics.summarize(between(st, hi=hold_hi)).get('expectancy_r',0)}R")
    lines += [
        "", f"Verdict: {verdict}", f"- winner: {cs}",
        f"- selection: {sel_m['trades']}t, {sel_m['expectancy_r']}R, PF {sel_m['profit_factor']}",
        f"- HOLDOUT (untouched judge): {hm['trades']}t, win {hm['win_rate']}%, {hm['expectancy_r']}R, "
        f"PF {hm['profit_factor']}, {hm['quarters_positive']}/{hm['quarters_total']}q+, maxDD ${hm['max_drawdown']:,}",
        f"- holdout GROSS (0 spread): {gm.get('trades',0)}t, {gm.get('expectancy_r',0)}R "
        f"(spread eats {gm.get('expectancy_r',0)-hm['expectancy_r']:+.3f}R)",
        f"- bootstrap 90% CI: [{blo:+.3f}, {bhi:+.3f}]R, P(>0)={frac_pos*100:.0f}% -> CI "
        f"{'clears 0' if blo > 0 else 'includes 0'}",
        f"- walk-forward: {wf_pos}/{wf_tot} folds+ ({', '.join(f'{r:+.3f}' for r in wf_per)})",
        f"- slippage: {' | '.join(sens)}",
        f"- 2026 reference (CONTAMINATED): {ref.get('trades',0)}t, {ref.get('expectancy_r',0)}R", ""]
    slack = (f"{tf}: holdout {hm['expectancy_r']:+}R (PF {hm['profit_factor']}, {hm['trades']}t) -> *{verdict}* "
             f"| gross {gm.get('expectancy_r',0):+}R | CI[{blo:+.3f},{bhi:+.3f}] | WF {wf_pos}/{wf_tot} | slip {' '.join(sens)}")
    return lines, slack


def run():
    cfg = load_config()
    g = cfg["fx_strategy13_apa"]
    inst = g["instrument"]
    half_spread = float(g["spread_price"]) / 2.0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    report = [f"# Advanced Price Action wedge-breakout on GOLD (strategy #13) - {ts}", "",
              "RESEARCH ONLY - nothing deploys. Mechanical proxy of the screenshot pattern; "
              "M1=scalping, M5=intraday, each judged on an UNTOUCHED holdout.",
              f"select {g['select_start']}..{g['select_end']} - holdout <= {g['holdout_end']}", ""]
    slack_lines = []
    for tf in g["granularities"]:
        print(f"downloading {inst} {tf}, {g['history_start']} -> {end}", flush=True)
        df = oanda_data.fetch_candles(inst, g["history_start"], end, granularity=tf)
        print(f"  {inst} {tf}: {len(df):,} bars", flush=True)
        if df.empty:
            report += [f"### {tf}", "", "no candles.", ""]
            slack_lines.append(f"{tf}: no candles")
            continue
        lines, slack = study(df, inst, g, half_spread, tf)
        report += lines
        slack_lines.append(slack)
        print(f"  {slack}", flush=True)

    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    (out_dir / f"fx_strategy13apa_{stamp}.md").write_text("\n".join(report), encoding="utf-8")
    print(f"report written: reports/fx_strategy13apa_{stamp}.md", flush=True)

    header = (f"*[FX-STRATEGY13-APA]* {ts} - RESEARCH ONLY, nothing deploys\n"
              "Advanced Price Action wedge-breakout on GOLD (M1 scalp + M5 intraday), untouched holdout")
    footer = f"Full detail: reports/fx_strategy13apa_{stamp}.md"
    slackbot.post("\n\n".join([header] + slack_lines + [footer]))


if __name__ == "__main__":
    run()
