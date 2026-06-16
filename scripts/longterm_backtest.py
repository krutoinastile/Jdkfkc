"""Long-term backtest & optimization (offline)."""

from __future__ import annotations

import asyncio
import itertools
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backtest import run_backtest
from app.services.market_data import fetch_candles
from app.services.strategy import analyze_bb_squeeze, analyze_candles
from app.services.strategy_config import StrategyConfig
from app.services.strategy_variants import get_all_analyzers, STRATEGY_LABELS


async def load_data(limit: int = 3000):
    candles = await fetch_candles("BTCUSDT", "1h", limit=limit)
    htf = await fetch_candles("BTCUSDT", "4h", limit=min(900, limit // 3 + 100))
    span = (candles[-1].open_time - candles[0].open_time) / 86_400_000
    return candles, htf, span


def report(label: str, r) -> None:
    print(
        f"{label:28} tr={len(r.trades):3} WR={r.win_rate:5.1f}% "
        f"pnl={r.total_pnl_pct:7.2f}% ${r.final_capital:7.2f} B&H={r.buy_hold_pct:6.2f}%"
    )


async def main() -> None:
    candles, htf, span = await load_data(3000)
    print(f"Данные: {len(candles)} свечей 1h (~{span:.0f} дн.)\n")
    base = StrategyConfig()

    print("=== Текущие настройки ===")
    report("router", run_backtest(candles, base, htf_candles=htf))
    report("bb_squeeze", run_backtest(candles, base, htf_candles=htf, analyzer=analyze_bb_squeeze))

    print("\n=== Поиск лучших параметров (BB Squeeze, 125d) ===")
    results: list[tuple[float, dict]] = []
    for sl, tp, strength, adx, per_day, htf_strict in itertools.product(
        [1.5, 1.8, 2.0],
        [4.0, 4.5, 5.0, 5.5, 6.0],
        [58, 62, 65, 68],
        [18, 20, 22],
        [1, 2],
        [True, False],
    ):
        if tp / sl < 2.2:
            continue
        cfg = replace(
            base,
            atr_sl_mult=sl,
            atr_tp_mult=tp,
            min_signal_strength=strength,
            min_adx=adx,
            max_signals_per_day=per_day,
            min_hours_between_signals=24.0 / per_day,
            htf_strict=htf_strict,
            use_higher_tf=True,
            use_macd_filter=True,
            use_volume_filter=True,
        )
        r = run_backtest(candles, cfg, htf_candles=htf, analyzer=analyze_bb_squeeze)
        if len(r.trades) < 6:
            continue
        profit = r.final_capital - r.simulated_capital
        # Prefer profitable configs with reasonable trade count
        score = profit + (10 if r.total_pnl_pct > 0 else 0) + min(len(r.trades), 20) * 0.2
        results.append((score, {
            "sl": sl, "tp": tp, "strength": strength, "adx": adx,
            "per_day": per_day, "htf_strict": htf_strict,
            "trades": len(r.trades), "wr": r.win_rate,
            "pnl": r.total_pnl_pct, "final": r.final_capital, "profit": profit,
        }))

    results.sort(key=lambda x: x[0], reverse=True)
    print(f"{'SL':>4} {'TP':>4} {'Str':>3} {'ADX':>3} {'/d':>2} {'HTF':>4} {'Tr':>3} {'WR':>6} {'PnL':>7} {'$':>8}")
    for _, p in results[:15]:
        print(
            f"{p['sl']:4.1f} {p['tp']:4.1f} {p['strength']:3} {p['adx']:3.0f} "
            f"{p['per_day']:2} {'Y' if p['htf_strict'] else 'N':>4} "
            f"{p['trades']:3} {p['wr']:5.1f}% {p['pnl']:6.2f}% ${p['final']:7.2f}"
        )

    if results:
        best = results[0][1]
        print(f"\nBEST: SL={best['sl']} TP={best['tp']} str={best['strength']} "
              f"adx={best['adx']} day={best['per_day']} htf_strict={best['htf_strict']}")
        print(f"      {best['trades']} trades WR={best['wr']}% pnl={best['pnl']}%")

    print("\n=== Все стратегии (лучший SL/TP на 125d) ===")
    ranked = []
    for name, analyzer in get_all_analyzers().items():
        best_p = None
        for sl, tp in itertools.product([1.5, 1.8, 2.0], [4.5, 5.0, 5.5, 6.0]):
            cfg = replace(base, atr_sl_mult=sl, atr_tp_mult=tp, max_signals_per_day=1,
                          min_hours_between_signals=24.0, min_signal_strength=62, min_adx=20)
            r = run_backtest(candles, cfg, htf_candles=htf, analyzer=analyzer)
            if len(r.trades) < 4:
                continue
            profit = r.final_capital - 1000
            if best_p is None or profit > best_p[0]:
                best_p = (profit, sl, tp, r)
        if best_p:
            profit, sl, tp, r = best_p
            ranked.append((profit, STRATEGY_LABELS.get(name, name), name, sl, tp, r))
    ranked.sort(reverse=True)
    for profit, label, name, sl, tp, r in ranked:
        print(f"{label:22} SL={sl} TP={tp} tr={len(r.trades):3} WR={r.win_rate:5.1f}% pnl={r.total_pnl_pct:7.2f}%")


if __name__ == "__main__":
    asyncio.run(main())
