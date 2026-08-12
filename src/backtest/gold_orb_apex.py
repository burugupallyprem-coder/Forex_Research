"""Does the validated gold ORB (intraday NY breakout) pass an APEX $50k eval - at what size,
and how fast? Reuses the holdout-validated simulate_orb (no new strategy code), sizes to MGC
micro-gold contracts, and runs the Apex trailing-drawdown rule. OANDA has gold from 2018, so
this DOES include the COVID crash (the stock test couldn't).

Apex $50k rules (verified 2026-08-12): profit target +$3,000; trailing max drawdown $2,500 that
follows your equity peak and LOCKS at +$100 once you're up +$2,600; max 6 contracts; ~30-day
assessment. NOTE: real Apex trails the INTRADAY peak (incl. open profit) - we trail CLOSED-trade
equity, so our bust% is OPTIMISTIC (real Apex is a bit harder). RESEARCH ONLY. Sources in chat.
Run: python -m src.backtest.gold_orb_apex
"""

from datetime import datetime, timedelta, timezone
import numpy as np

from src import oanda_data, slackbot
from src.backtest.strategy11_gold_orb import simulate_orb, sim_cfg, load_config

PARAMS = {"or_minutes": 30, "target_r": 2.0, "trend_filter": False}   # fixed, pre-declared
MGC_PT = 10.0            # $ per 1.0 (price) move, per MGC contract (10 oz)
TARGET, DD, LOCK, MAXC = 3000.0, 2500.0, 2600.0, 6
RISKS = [100.0, 150.0, 200.0, 250.0]    # target $ risk per trade (Apex analog of risk_pct)


def _contracts(risk_ps, tgt):
    if risk_ps <= 0:
        return 0
    return max(1, min(MAXC, round(tgt / (risk_ps * MGC_PT))))


def _pnls(trades, tgt):
    out = []
    for t in trades:
        risk_ps = abs(t.entry - t.stop)
        c = _contracts(risk_ps, tgt)
        out.append(t.r_multiple * c * risk_ps * MGC_PT)     # = (exit-entry)*d * c * $/pt  (net of spread)
    return out


def _apex(pnls, start):
    eq = 0.0; peak = 0.0
    for k in range(start, len(pnls)):
        eq += pnls[k]
        peak = max(peak, eq)
        floor = (peak - DD) if peak < LOCK else 100.0       # trails, then locks at +$100
        if eq <= floor:
            return ("bust", None)
        if eq >= TARGET:
            return ("pass", k - start + 1)
    return ("none", None)


def _sweep(pnls, tgt):
    outs = [_apex(pnls, s) for s in range(0, max(1, len(pnls) - 3), 2)]
    passed = [d for t, d in outs if t == "pass"]
    n = len(outs)
    med = int(np.median(passed)) if passed else None
    return dict(passpct=round(100 * len(passed) / n, 1) if n else 0.0,
                bustpct=round(100 * sum(1 for t, _ in outs if t == "bust") / n, 1) if n else 0.0,
                med=med)


def run():
    cfg = load_config()
    g = cfg["fx_strategy11_gold_orb"]
    inst = g["instrument"]; hs = float(g["spread_price"]) / 2.0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"downloading {inst} {g['granularity']} {g['history_start']}->{end}", flush=True)
    df = oanda_data.fetch_candles(inst, g["history_start"], end, granularity=g["granularity"])
    if df.empty:
        slackbot.post(f"[GOLD-ORB-APEX] {ts} - FAILED: no candles.")
        return
    first, last = df["ts"].min().date(), df["ts"].max().date()
    trades = simulate_orb(df, inst, PARAMS, sim_cfg(g, hs))
    wins = sum(1 for t in trades if t.r_multiple > 0)
    avg_r = np.mean([t.r_multiple for t in trades]) if trades else 0.0

    L = [f"[GOLD-ORB-APEX] {ts} - validated gold ORB under APEX $50k (MGC), COVID INCLUDED",
         f"data {first}..{last} | {len(trades)} trades | win {100*wins/max(1,len(trades)):.1f}% | "
         f"avgR {avg_r:+.3f} | params {PARAMS}", "",
         f"{'RISK/trade':<11} {'~contracts':<11} passRate  median(trades~=days)  bust%"]
    for tgt in RISKS:
        pnls = _pnls(trades, tgt)
        r = _sweep(pnls, tgt)
        # typical contracts at this target risk (median stop distance)
        typ = int(np.median([_contracts(abs(t.entry - t.stop), tgt) for t in trades])) if trades else 0
        md = f"{r['med']} (~{r['med']/21:.1f}mo)" if r["med"] else "never"
        L.append(f"${tgt:>7.0f}    {typ:>4} MGC     {r['passpct']:>5}%    {md:<20} {r['bustpct']}%")
    L += ["", "Read: Apex trails your PEAK (incl. open profit) and locks +$100 after +$2,600 - so unlike TTP's "
          "static leash, giving back profit can bust you. bigger $risk = faster target but more bust. This is "
          "the VALIDATED intraday breakout; retest + swing variants are the next builds. Our bust% is optimistic "
          "(we trail closed equity, real Apex trails intraday). RESEARCH ONLY - not deployed."]
    out = "\n".join(L); print(out)
    try: slackbot.post(out)
    except Exception: pass


if __name__ == "__main__":
    run()
