"""FX-majors Advanced Price Action wedge-breakout (strategy #13-fx).
Run: python tests/test_strategy13_fx_apa.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.backtest.strategy13_fx_apa import load_config, sim_cfg
from src.backtest.strategy13_gold_apa import simulate_apa

CFG = {
    "risk": {"equity": 100000, "risk_pct": 0.5, "max_position_pct": 20},
    "half_spread": {"EUR_USD": 0.00007},
    "atr_len": 14, "pullback_len": 20, "breakout_lookback": 5, "ema_len": 200,
    "stop_buf_atr": 0.05, "session_start_min": 420, "entry_cutoff_min": 1200,
    "flat_min": 1260, "max_trades_day": 2, "min_stop_cost_mult": 2.0,
}
LONG = {"atr_mult": 1.5, "target_r": 2.0, "trend_filter": False}
D = datetime(2026, 3, 3, 0, 0, tzinfo=timezone.utc)


def _series(breakout, rally):
    rows = []
    for k in range(30):
        base = 1.1000 - 0.0004 * k                       # gentle falling wedge
        rows.append((810 + k, base, base + 0.0005, base - 0.0005, base - 0.0002))
    rows.append((840, *breakout))
    for j, (o, h, l, c) in enumerate(rally, start=841):
        rows.append((j, o, h, l, c))
    df = pd.DataFrame([{"ts": D + timedelta(minutes=m), "open": o, "high": h,
                        "low": l, "close": c, "volume": 10} for (m, o, h, l, c) in rows])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def test_fx_scale_wedge_breakout_long():
    df = _series(
        breakout=(1.0882, 1.0916, 1.0881, 1.0914),       # big bullish bar (~35 pip range >> ATR)
        rally=[(1.0915, 1.0925, 1.0913, 1.0923), (1.0923, 1.0940, 1.0922, 1.0938),
               (1.0938, 1.0965, 1.0937, 1.0962), (1.0962, 1.0995, 1.0961, 1.0992),
               (1.0992, 1.1030, 1.0991, 1.1028)])
    trades = simulate_apa(df, "EUR_USD", LONG, CFG)
    assert len(trades) >= 1
    t = trades[0]
    assert t.signal_reason == "apa_wedge_break_long" and t.exit_reason == "target"
    assert t.r_multiple > 1.5 and t.pnl > 0


def test_config_wiring():
    g = load_config()["fx_strategy13_apa_fx"]
    c = sim_cfg(g, {"EUR_USD": 0.00007})
    assert c["atr_len"] == 14 and c["flat_min"] == 1260
    assert len(g["instruments"]) == 7 and g["granularities"] == ["M1", "M5"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
