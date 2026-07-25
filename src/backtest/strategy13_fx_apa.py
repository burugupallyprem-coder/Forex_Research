"""Advanced Price Action wedge-breakout on the FX MAJORS basket - RESEARCH ONLY.

PRE-REGISTERED 2026-07-23. Same pattern and same simulator as the gold version
(strategy13_gold_apa.simulate_apa) - falling-wedge pullback into a demand zone +
a LONG BAR (range >= atr_mult x ATR) breakout, long-and-short, measured-move
target, stop beyond the zone - but pooled across a 7-pair USD-majors basket so
the sample is large. M1 = scalping, M5 = intraday, judged as separate studies.

Same honest validation: SELECT the grid winner on the already-spent window
(2024-07 -> 2025-12), judge ONCE on the UNTOUCHED holdout (<= 2024-06-30, back to
history_start) with gate + walk-forward + bootstrap CI + gross-vs-net + slippage
x2. 2026 is a contaminated reference only. Frames are held one timeframe at a time
to bound memory; the winner's gross/slippage reruns reuse those frames.

Run: python -m src.backtest.strategy13_fx_apa
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

from src import oanda_data, slackbot
from src.backtest import metrics
from src.backtest.strategy10_boring_scalp import pip_size
from src.backtest.strategy10_gold import between, bootstrap_ci, walk_forward
from src.backtest.strategy13_gold_apa import expand_grid, simulate_apa

ROOT = Path(__file__).resolve().parent.parent.parent


def load_config():
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sim_cfg(g, half_spread):
    d = {"risk": {"equity": 100000, "risk_pct": 0.5, "max_position_pct": 20},
         "half_spread": dict(half_spread)}
    for k in ("atr_len", "pullback_len", "breakout_lookback", "ema_len", "stop_buf_atr",
              "session_start_min", "entry_cutoff_min", "flat_min", "max_trades_day",
              "min_stop_cost_mult"):
        d[k] = g[k]
    return d


def pooled(frames, combo, base):
    tr = []
    for p, df in frames.items():
        tr.extend(simulate_apa(df, p, combo, base))
    return tr


def study(frames, g, half_spread, tf):
    sel_lo = pd.to_datetime(g["select_start"]).date()
    sel_hi = pd.to_datetime(g["select_end"]).date()
    hold_hi = pd.to_datetime(g["holdout_end"]).date()
    gate = g["gate"]
    base = sim_cfg(g, half_spread)

    scored = []
    for combo in expand_grid(g["grid"]):
        tr = pooled(frames, combo, base)
        scored.append((combo, metrics.summarize(between(tr, sel_lo, sel_hi)), tr))
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

    gm = metrics.summarize(between(pooled(frames, win, {**base, "half_spread": {p: 0.0 for p in half_spread}}), hi=hold_hi))
    ref = metrics.summarize(between(wt, lo=pd.to_datetime("2026-01-01").date()))
    verdict, why = metrics.gate_verdict(hm, gate)
    wf_pos, wf_tot, wf_per = walk_forward(hold, int(g["walkforward_folds"]))
    if verdict == "PASS" and not (wf_tot and wf_pos / wf_tot >= float(g["min_positive_frac"])):
        verdict = "FAIL"
        why = (f"{why}; " if why != "all gate checks met" else "") + f"walk-forward {wf_pos}/{wf_tot} folds+"
    blo, bhi, frac_pos, _ = bootstrap_ci(hold)
    sens = []
    for sm in g.get("slippage_mult", [1.0]):
        st = pooled(frames, win, {**base, "half_spread": {p: hs * sm for p, hs in half_spread.items()}})
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
    g = cfg["fx_strategy13_apa_fx"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    half_spread = {p: float(g["spread_pips"][p]) * pip_size(p) / 2.0 for p in g["instruments"]}

    report = [f"# Advanced Price Action wedge-breakout on FX MAJORS (strategy #13-fx) - {ts}", "",
              "RESEARCH ONLY - nothing deploys. Same wedge-breakout engine as gold, pooled across "
              "a 7-pair basket; M1=scalping, M5=intraday, each judged on an UNTOUCHED holdout.",
              f"pairs {g['instruments']} - select {g['select_start']}..{g['select_end']} - "
              f"holdout <= {g['holdout_end']}", ""]
    slack_lines = []
    for tf in g["granularities"]:
        frames = {}
        for p in g["instruments"]:
            print(f"downloading {p} {tf}, {g['history_start']} -> {end}", flush=True)
            df = oanda_data.fetch_candles(p, g["history_start"], end, granularity=tf)
            print(f"  {p} {tf}: {len(df):,} bars", flush=True)
            if not df.empty:
                frames[p] = df
        if not frames:
            report += [f"### {tf}", "", "no candles.", ""]
            slack_lines.append(f"{tf}: no candles")
            continue
        lines, slack = study(frames, g, half_spread, tf)
        report += lines
        slack_lines.append(slack)
        print(f"  {slack}", flush=True)
        del frames

    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    (out_dir / f"fx_strategy13apafx_{stamp}.md").write_text("\n".join(report), encoding="utf-8")
    print(f"report written: reports/fx_strategy13apafx_{stamp}.md", flush=True)

    header = (f"*[FX-STRATEGY13-APA-FX]* {ts} - RESEARCH ONLY, nothing deploys\n"
              "Advanced Price Action wedge-breakout on FX majors basket (M1 scalp + M5 intraday), untouched holdout")
    footer = f"Full detail: reports/fx_strategy13apafx_{stamp}.md"
    slackbot.post("\n\n".join([header] + slack_lines + [footer]))


if __name__ == "__main__":
    run()
