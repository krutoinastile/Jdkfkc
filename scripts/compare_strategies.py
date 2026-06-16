"""Compare classic trading strategies on 30d BTC backtest."""

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
from app.services.strategy_variants import STRATEGY_LABELS, get_all_analyzers


async def main() -> None:
    candles = await fetch_candles("BTCUSDT", "1h", limit=750)
    htf = await fetch_candles("BTCUSDT", "4h", limit=250)
    print(f"Данные: {len(candles)} свечей 1h, {len(htf)} свечей 4h")
    print("Условия: 30 дней · 10% банка · 20x · до 2 сделок/день\n")

    base = StrategyConfig()
    analyzers = get_all_analyzers()
    sl_tp_sets = [(1.0, 3.0), (1.2, 3.5), (1.5, 4.0)]

    ranked: list[tuple[float, str, dict]] = []

    for name, analyzer in analyzers.items():
        best_for_strategy: tuple[float, dict] | None = None
        for sl, tp in sl_tp_sets:
            cfg = replace(base, atr_sl_mult=sl, atr_tp_mult=tp)
            r = run_backtest(candles, cfg, htf_candles=htf, analyzer=analyzer)
            profit = r.final_capital - r.simulated_capital
            row = {
                "name": name,
                "label": STRATEGY_LABELS.get(name, name),
                "sl": sl,
                "tp": tp,
                "trades": len(r.trades),
                "wr": r.win_rate,
                "pnl": r.total_pnl_pct,
                "final": r.final_capital,
                "profit": profit,
            }
            if best_for_strategy is None or profit > best_for_strategy[0]:
                best_for_strategy = (profit, row)

        if best_for_strategy:
            profit, row = best_for_strategy
            score = profit + min(row["trades"], 8) * 0.5
            ranked.append((score, name, row))

    ranked.sort(key=lambda x: x[0], reverse=True)

    print("=" * 72)
    print(f"{'#':<3} {'Стратегия':<28} {'SL':>4} {'TP':>4} {'Сдл':>4} {'WR':>6} {'PnL':>7} {'$1000→':>8}")
    print("=" * 72)
    for idx, (_, name, row) in enumerate(ranked, 1):
        print(
            f"{idx:<3} {row['label']:<28} {row['sl']:>4.1f} {row['tp']:>4.1f} "
            f"{row['trades']:>4} {row['wr']:>5.1f}% {row['pnl']:>6.2f}% ${row['final']:>7.2f}"
        )

    if ranked:
        winner = ranked[0][2]
        print("\n" + "=" * 72)
        print(f"🏆 ПОБЕДИТЕЛЬ: {winner['label']} ({winner['name']})")
        print(
            f"   SL={winner['sl']} TP={winner['tp']} · {winner['trades']} сделок · "
            f"WR {winner['wr']}% · +{winner['pnl']}% · ${winner['final']:.2f}"
        )
        print(f"\nWINNER_ID={winner['name']}")
        print(f"WINNER_SL={winner['sl']}")
        print(f"WINNER_TP={winner['tp']}")


if __name__ == "__main__":
    asyncio.run(main())
