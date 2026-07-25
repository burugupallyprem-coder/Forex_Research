"""Advanced Price Action wedge-breakout (strategy #13) correctness.
Run: python tests/test_strategy13_gold_apa.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.backtest.strategy13_gold_apa import simulate_apa

CFG = {
    "risk": {"equity": 100000, "risk_pct": 0.5, "max_position_pct": 20},
    "half_spread": {"XAU_USD": 0.175},
    "atr_len": 14, "pullback_len": 20, "breakout_lookback": 5, "ema_len": 200,
    "stop_buf_atr": 0.05, "session_start_min": 480, "entry_cutoff_min": 1200,
    "flat_min": 1260, "max_trades_day": 2, "min_stop_cost_mult": 2.0,
}
LONG = {"atr_mult": 1.5, "target_r": 2.0, "trend_filter": False}
D = datetime(2026, 3, 3, 0, 0, tzinfo=timezone.utc)


def _series(breakout, rally):
    """30 declining bars (falling wedge) + a breakout bar + rally bars."""
    rows = []
    m0 = 810
    for k in range(30):
        base = 2450 - 0.8 * k
        rows.append((m0 + k, base, base + 1.0, base - 1.0, base - 0.4))
    idx = 30
    rows.append((m0 + idx, *breakout))
    for j, (o, h, l, c) in enumerate(rally, start=idx + 1):
        rows.append((m0 + j, o, h, l, c))
    df = pd.DataFrame([{"ts": D + timedelta(minutes=m), "open": o, "high": h,
                        "low": l, "close": c, "volume": 10} for (m, o, h, l, c) in rows])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def test_wedge_breakout_long_hits_target():
    df = _series(
        breakout=(2427, 2440, 2426, 2439),           # big bullish bar, range 14
        rally=[(2440, 2445, 2439, 2444), (2444, 2452, 2443, 2451),
               (2451, 2462, 2450, 2460), (2460, 2475, 2459, 2472)])
    trades = simulate_apa(df, "XAU_USD", LONG, CFG)
    assert len(trades) >= 1
    t = trades[0]
    assert t.signal_reason == "apa_wedge_break_long"
    assert t.exit_reason == "target"
    assert t.r_multiple > 1.5 and t.pnl > 0


def test_small_breakout_bar_is_filtered():
    # breaks recent highs but the bar is NOT a "long bar" (range << atr_mult x ATR)
    df = _series(
        breakout=(2431.0, 2432.2, 2431.0, 2432.0),   # range ~1.2, tiny
        rally=[(2432, 2434, 2431, 2433), (2433, 2436, 2432, 2435)])
    assert simulate_apa(df, "XAU_USD", LONG, CFG) == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
