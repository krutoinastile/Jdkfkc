"""Weekly strategy backtest report for admins."""

from __future__ import annotations

import logging
from dataclasses import replace

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.repositories import get_strategy_settings
from app.services.backtest import run_backtest
from app.services.market_data import fetch_candles
from app.services.strategy import analyze_bb_squeeze
from app.services.strategy_config import StrategyConfig

logger = logging.getLogger(__name__)


async def run_weekly_reopt_report(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
) -> None:
    try:
        db_cfg = await get_strategy_settings(session)
        cfg = StrategyConfig.from_db(db_cfg)
        candles = await fetch_candles(settings.symbol, cfg.timeframe, limit=3000)
        htf = await fetch_candles(settings.symbol, cfg.higher_tf, limit=900)
        if len(candles) < 200:
            return

        span_days = (candles[-1].open_time - candles[0].open_time) / 86_400_000
        current = run_backtest(candles, cfg, htf_candles=htf, analyzer=analyze_bb_squeeze)

        candidates: list[tuple[float, dict]] = []
        for sl, tp, strength in (
            (cfg.atr_sl_mult, cfg.atr_tp_mult, cfg.min_signal_strength),
            (1.8, 5.0, 62),
            (1.8, 5.5, 65),
            (2.0, 5.0, 62),
        ):
            test_cfg = replace(
                cfg,
                atr_sl_mult=sl,
                atr_tp_mult=tp,
                min_signal_strength=strength,
            )
            r = run_backtest(candles, test_cfg, htf_candles=htf, analyzer=analyze_bb_squeeze)
            if len(r.trades) < 4:
                continue
            profit = r.final_capital - r.simulated_capital
            score = profit + (5 if r.total_pnl_pct > 0 else 0)
            candidates.append((score, {
                "sl": sl, "tp": tp, "strength": strength,
                "trades": len(r.trades), "wr": r.win_rate, "pnl": r.total_pnl_pct,
            }))

        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1] if candidates else None

        lines = [
            f"📊 <b>Еженедельный отчёт бэктеста</b>\n",
            f"Период: ~<b>{span_days:.0f}</b> дн. · {settings.symbol} {cfg.timeframe}\n",
            f"\n<b>Текущие настройки</b>\n",
            f"SL {cfg.atr_sl_mult}× / TP {cfg.atr_tp_mult}× / сила {cfg.min_signal_strength}\n",
            f"Сделок: <b>{len(current.trades)}</b> · WR <b>{current.win_rate:.1f}%</b>\n",
            f"P&L банка: <b>{current.total_pnl_pct:+.1f}%</b>\n",
        ]
        if best:
            lines.extend([
                f"\n<b>Лучший из проверенных</b>\n",
                f"SL {best['sl']}× / TP {best['tp']}× / сила {best['strength']}\n",
                f"Сделок: <b>{best['trades']}</b> · WR <b>{best['wr']:.1f}%</b>\n",
                f"P&L банка: <b>{best['pnl']:+.1f}%</b>\n",
            ])
            if (
                best["sl"] != cfg.atr_sl_mult
                or best["tp"] != cfg.atr_tp_mult
                or best["strength"] != cfg.min_signal_strength
            ):
                lines.append("\n<i>💡 Есть более прибыльная конфигурация — рассмотрите в админке.</i>")
            else:
                lines.append("\n<i>✅ Текущие настройки оптимальны среди проверенных.</i>")

        text = "".join(lines)
        for admin_id in settings.parsed_admin_ids:
            try:
                await bot.send_message(chat_id=admin_id, text=text)
            except Exception:
                logger.exception("Weekly reopt report failed for %s", admin_id)
    except Exception:
        logger.exception("Weekly reopt report failed")
