"""Fast grid search for optimized strategy v3 params."""

from __future__ import annotations

import asyncio
import itertools
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backtest import run_backtest
from app.services.market_data import fetch_candles
from app.services.strategy_config import StrategyConfig


async def main() -> None:
    candles = await fetch_candles("BTCUSDT", "1h", limit=750)
    htf = await fetch_candles("BTCUSDT", "4h", limit=250)
    print(f"Candles: {len(candles)} 1h, {len(htf)} 4h\n")

    base = StrategyConfig()
    br = run_backtest(candles, base, htf_candles=htf)
    print(
        f"Default v3: trades={len(br.trades)} WR={br.win_rate}% "
        f"PnL={br.total_pnl_pct}% final=${br.final_capital:.2f}\n"
    )

    sl_vals = [1.0, 1.2, 1.5]
    tp_vals = [2.5, 3.0, 3.5, 4.0]
    strength_vals = [52, 55, 58, 62]
    adx_vals = [18, 20, 22]
    per_day_vals = [1, 2]

    results: list[tuple[float, dict]] = []
    for sl, tp, strength, adx, per_day in itertools.product(
        sl_vals, tp_vals, strength_vals, adx_vals, per_day_vals
    ):
        if tp / sl < 2.0:
            continue
        cfg = replace(
            base,
            atr_sl_mult=sl,
            atr_tp_mult=tp,
            min_signal_strength=strength,
            min_adx=adx,
            max_signals_per_day=per_day,
            min_hours_between_signals=24.0 / per_day,
        )
        r = run_backtest(candles, cfg, htf_candles=htf)
        if len(r.trades) < 4:
            continue
        profit = r.final_capital - r.simulated_capital
        score = profit + min(len(r.trades), 12) + max(0, r.win_rate - 35) * 0.3
        results.append(
            (
                score,
                {
                    "sl": sl,
                    "tp": tp,
                    "strength": strength,
                    "adx": adx,
                    "per_day": per_day,
                    "trades": len(r.trades),
                    "wr": r.win_rate,
                    "total_pnl": r.total_pnl_pct,
                    "final": r.final_capital,
                },
            )
        )

    results.sort(key=lambda x: x[0], reverse=True)
    print("=== TOP 15 (30d, 10% bank, 20x, min 4 trades) ===")
    for s, p in results[:15]:
        print(
            f"SL={p['sl']} TP={p['tp']} str={p['strength']} ADX={p['adx']} day={p['per_day']} | "
            f"trades={p['trades']} WR={p['wr']}% PnL={p['total_pnl']}% "
            f"final=${p['final']:.2f}"
        )
    if results:
        print("\n=== BEST ===")
        print(results[0][1])


if __name__ == "__main__":
    asyncio.run(main())
