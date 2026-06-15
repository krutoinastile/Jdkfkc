"""User-facing message templates."""

from __future__ import annotations

from app.database.models import Signal
from app.utils.formatting import (
    badge,
    bullet_list,
    footer,
    header,
    kv,
    money,
    pnl,
    pnl_colored,
    progress_bar,
    rsi_bar,
    section,
    signal_status,
    strength_bar,
    win_rate_bar,
)
from app.utils.leverage import get_leverage, leveraged_move


def welcome_text() -> str:
    return (
        f"{header('₿ BTC Trading Bot', 'Аналитика и сигналы в реальном времени')}\n"
        f"{section('Возможности')}\n"
        f"{bullet_list([
            '📊 Сигналы LONG / SHORT · плечо 20x',
            '⏱ до 2 сделок в день',
            '📈 EMA · RSI · MACD · ATR стратегия',
            '😱 Fear & Greed · Funding · Open Interest',
            '🔥 Ликвидации Binance Futures',
            '💰 Калькулятор прибыли · Бэктест',
            '💎 Подписка · Crypto Pay · рефералы',
        ])}\n\n"
        f"<i>⚠️ Не финансовый совет. Торгуйте ответственно.</i>"
        f"{footer()}"
    )


def help_text() -> str:
    return (
        f"{header('❓ Справка')}\n"
        f"{section('Разделы')}\n"
        f"{bullet_list([
            'Дашборд — сводка, график, Fear & Greed',
            'Сигнал — активная точка входа + график',
            'Рынок — цена, индикаторы + график',
            'Статистика — win rate и P&L',
            'Калькулятор — прибыль за период с выбранным капиталом',
            'Бэктест — проверка на 30д / 90д / 6м / 1г',
            'История — прошлые сделки',
            'Уведомления — сигналы, ликвидации, funding',
        ])}\n"
        f"{section('Команды')}\n"
        f"{bullet_list([
            '/start — главное меню',
            '/signal — текущий сигнал',
            '/stats — статистика',
            '/calc — калькулятор прибыли',
            '/admin — панель админа',
        ])}"
        f"{footer()}"
    )


def _format_fear_greed(fng: dict | None) -> str:
    if fng is None:
        return kv("😱 Fear & Greed", "<i>недоступен</i>")
    bar = progress_bar(fng["value"], 100, 8)
    return kv(f"{fng['emoji']} Fear & Greed", f"{bar}  <b>{fng['value']}</b> · {fng['label']}")


def _format_funding(funding: dict | None) -> str:
    if funding is None:
        return kv("💸 Funding", "<i>недоступен</i>")
    sign = "+" if funding["rate_pct"] >= 0 else ""
    lines = [kv("💸 Funding", f"<b>{sign}{funding['rate_pct']:.4f}%</b> · {funding['source']}")]
    lines.append(f"   {funding['bias']}")
    if funding.get("next_funding"):
        lines.append(f"   ⏱ {funding['next_funding'].strftime('%d.%m %H:%M UTC')}")
    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    total_closed = stats["wins"] + stats["losses"]
    total = stats["total"]
    return (
        f"{header('📈 Статистика', f'{total} сигналов всего')}\n"
        f"{section('Результаты')}\n"
        f"{kv('✅ Успешных', f'<b>{stats['wins']}</b>')}\n"
        f"{kv('❌ Убыточных', f'<b>{stats['losses']}</b>')}\n"
        f"{kv('⏱ Истекло', f'<b>{stats['expired']}</b>')}\n"
        f"{kv('🔄 Открытых', f'<b>{stats['open']}</b>')}\n"
        f"{section('Эффективность')}\n"
        f"{kv('Win Rate', win_rate_bar(stats['win_rate']))}\n"
        f"{kv('Средний P&L', pnl_colored(stats['avg_pnl']))}\n"
        f"{kv('Закрыто', f'<b>{total_closed}</b> сделок')}"
        f"{footer()}"
    )


def format_market(
    snap: dict,
    timeframe: str,
    *,
    fear_greed: dict | None = None,
    funding: dict | None = None,
    derivatives: dict | None = None,
) -> str:
    return (
        f"{header('💹 BTC/USDT', f'Таймфрейм {timeframe}')}\n"
        f"{section('Цена')}\n"
        f"{kv('BTC', f'<b>{money(snap['price'])}</b>')}\n"
        f"{kv('Тренд', f'<b>{snap['trend']}</b>')}\n"
        f"{section('Индикаторы')}\n"
        f"{kv('RSI', rsi_bar(snap['rsi']))}\n"
        f"{kv('MACD', f'<b>{snap['macd']}</b> ({snap['macd_hist']})')}\n"
        f"{kv('ADX', f'<b>{snap.get('adx', '—')}</b>')}\n"
        f"{kv('Bollinger', f'<b>{snap.get('bb', '—')}</b>')}\n"
        f"{kv('Объём', f'<b>{snap['volume']}</b>')}\n"
        f"{section('EMA')}\n"
        f"{kv('EMA9', money(snap['ema_fast']))}\n"
        f"{kv('EMA21', money(snap['ema_slow']))}\n"
        f"{kv('EMA55', money(snap['ema_trend']))}\n"
        f"{section('Сентимент')}\n"
        f"{_format_fear_greed(fear_greed)}\n"
        f"{_format_funding(funding)}\n"
        f"{_format_derivatives(derivatives)}"
        f"{footer()}"
    )


def format_no_signal(snap: dict) -> str:
    return (
        f"{header('📊 Точка входа', 'Активного сигнала нет')}\n"
        f"{section('Рынок')}\n"
        f"{kv('Цена', f'<b>{money(snap['price'])}</b>')}\n"
        f"{kv('Тренд', snap['trend'])}\n"
        f"{kv('RSI', rsi_bar(snap['rsi']))}\n"
        f"{kv('ADX', snap.get('adx', '—'))}\n"
        f"{kv('MACD', snap['macd'])}\n\n"
        f"<i>🔔 Уведомление придёт при сильном сигнале.</i>"
        f"{footer()}"
    )


def format_dashboard(
    snap: dict,
    stats: dict,
    *,
    has_open: bool,
    fear_greed: dict | None = None,
    funding: dict | None = None,
    derivatives: dict | None = None,
) -> str:
    return (
        f"{header('🏠 Дашборд', 'Bitcoin Trading')}\n"
        f"{section('Рынок')}\n"
        f"{kv('BTC', f'<b>{money(snap['price'])}</b>  {snap['trend']}')}\n"
        f"{kv('RSI', rsi_bar(snap['rsi']))}\n"
        f"{kv('MACD', snap['macd'])}\n"
        f"{section('Сентимент')}\n"
        f"{_format_fear_greed(fear_greed)}\n"
        f"{_format_funding(funding)}\n"
        f"{_format_derivatives(derivatives)}\n"
        f"{section('Сигналы')}\n"
        f"   {signal_status(has_open)}\n"
        f"{kv('Win Rate', win_rate_bar(stats['win_rate']))}\n"
        f"{kv('P&L', f'{pnl_colored(stats['avg_pnl'])} · Открыто <b>{stats['open']}</b>')}"
        f"{footer()}"
    )


def _signal_type_label(signal_type: str) -> str:
    labels = {
        "crossover": "Пересечение EMA",
        "pullback": "Откат к EMA",
        "continuation": "Продолжение тренда",
        "squeeze": "BB Squeeze",
        "breakout": "Пробой",
        "mean_reversion": "Mean Reversion",
        "momentum": "MACD Momentum",
    }
    return labels.get(signal_type, signal_type.replace("_", " ").title())


def format_signal_card(signal: Signal, *, is_new: bool = False) -> str:
    is_long = signal.direction == "long"
    dir_badge = badge("LONG · Покупка", style="long") if is_long else badge("SHORT · Продажа", style="short")
    title = "🚨 Новый сигнал" if is_new else "📊 Активный сигнал"
    type_label = _signal_type_label(signal.signal_type)
    strength = getattr(signal, "strength", 0) or 0

    risk = abs(signal.entry_price - signal.stop_loss)
    reward = abs(signal.take_profit - signal.entry_price)
    rr = round(reward / risk, 2) if risk > 0 else 0

    sl_pct = abs(signal.stop_loss - signal.entry_price) / signal.entry_price * 100
    tp_pct = abs(signal.take_profit - signal.entry_price) / signal.entry_price * 100
    lev = get_leverage(signal)
    sl_lev = leveraged_move(sl_pct, lev)
    tp_lev = leveraged_move(tp_pct, lev)

    return (
        f"{header(title, f'BTC/USDT · {signal.timeframe} · {lev}x')}\n\n"
        f"   {dir_badge} · {type_label}\n"
        f"   {strength_bar(strength)}\n"
        f"{section('Уровни')}\n"
        f"{kv('💰 Вход', f'<b>{money(signal.entry_price)}</b>')}\n"
        f"{kv('🛑 SL', f'<b>{money(signal.stop_loss)}</b> (−{sl_lev:.1f}% при {lev}x)')}\n"
        f"{kv('🎯 TP', f'<b>{money(signal.take_profit)}</b> (+{tp_lev:.1f}% при {lev}x)')}\n"
        f"{kv('📐 R:R', f'<b>1:{rr}</b>')}\n"
        f"{kv('⚡ Плечо', f'<b>{lev}x</b>')}\n"
        f"{section('Анализ')}\n"
        f"{kv('RSI', str(signal.rsi))}\n"
        f"{kv('ATR', money(signal.atr))}\n"
        f"{kv('EMA', f'{money(signal.ema_fast)} / {money(signal.ema_slow)}')}\n\n"
        f"<i>{signal.reason}</i>"
        f"{footer()}"
    )


def format_history_item(signal: Signal, *, index: int | None = None) -> str:
    icons = {"win": "✅", "loss": "❌", "open": "🔄", "expired": "⏱"}
    icon = icons.get(signal.status, "·")
    direction = "🟢 LONG" if signal.direction == "long" else "🔴 SHORT"
    date = signal.opened_at.strftime("%d.%m.%Y %H:%M") if signal.opened_at else "—"
    pnl_str = f" · {pnl_colored(signal.pnl_percent)}" if signal.pnl_percent is not None else ""
    strength = f" · {signal.strength}/100" if signal.strength else ""
    prefix = f"<b>#{index}</b> " if index is not None else ""
    return (
        f"{prefix}{icon} <b>{direction}</b>\n"
        f"   📅 {date}\n"
        f"   💰 {money(signal.entry_price)}{strength}{pnl_str}"
    )


def format_history_summary(total: int, wins: int, losses: int, open_n: int) -> str:
    parts = [f"<b>{total}</b> сделок"]
    if wins:
        parts.append(f"✅ {wins}")
    if losses:
        parts.append(f"❌ {losses}")
    if open_n:
        parts.append(f"🔄 {open_n}")
    return " · ".join(parts)


def format_history(
    signals: list[Signal],
    *,
    page: int,
    status_filter: str,
    days: int,
    total_count: int,
    wins: int,
    losses: int,
    open_n: int,
) -> str:
    from app.utils.history import HISTORY_FILTERS, HISTORY_PERIODS

    filt_label = HISTORY_FILTERS.get(status_filter, "Все")
    period_label = HISTORY_PERIODS.get(days, "Всё")

    lines = [
        f"{header('📜 История сделок', f'{filt_label} · {period_label} · стр. {page + 1}')}\n",
        f"   {format_history_summary(total_count, wins, losses, open_n)}\n",
    ]
    start_idx = page * len(signals) + 1 if signals else 0
    for i, s in enumerate(signals):
        lines.append(format_history_item(s, index=start_idx + i))
    if not signals:
        lines.append("\n<i>Нет сделок по выбранному фильтру.</i>")
    lines.append(footer())
    return "\n".join(lines)


def format_history_empty() -> str:
    return (
        f"{header('📜 История сделок', 'Пока пусто')}\n\n"
        f"История заполняется автоматически, когда бот:\n"
        f"{bullet_list([
            'находит сигнал LONG / SHORT',
            'открывает сделку с Entry, SL, TP',
            'закрывает по Take-Profit или Stop-Loss',
        ])}\n\n"
        f"Сейчас в базе <b>0 сделок</b> — стратегия ждёт\n"
        f"подходящих условий на рынке.\n\n"
        f"<i>💡 Пока можете посмотреть 🔬 Бэктест —\n"
        f"симуляцию сделок на исторических данных.</i>"
        f"{footer()}"
    )


def format_history_detail(signal: Signal) -> str:
    icons = {"win": "✅", "loss": "❌", "open": "🔄", "expired": "⏱"}
    icon = icons.get(signal.status, "·")
    status_labels = {
        "win": "Успех",
        "loss": "Убыток",
        "open": "Открыта",
        "expired": "Истекла",
    }
    opened = signal.opened_at.strftime("%d.%m.%Y %H:%M UTC") if signal.opened_at else "—"
    closed = signal.closed_at.strftime("%d.%m.%Y %H:%M UTC") if signal.closed_at else "—"
    direction = badge("LONG", style="long") if signal.direction == "long" else badge("SHORT", style="short")

    lines = [
        f"{header(f'{icon} Сделка #{signal.id}', status_labels.get(signal.status, signal.status))}\n",
        f"   {direction} · {signal.timeframe}\n",
        f"{section('Время')}\n",
        f"{kv('Открыта', opened)}\n",
        f"{kv('Закрыта', closed)}\n",
        f"{section('Уровни')}\n",
        f"{kv('Вход', f'<b>{money(signal.entry_price)}</b>')}\n",
    ]
    if signal.exit_price is not None:
        lines.append(f"{kv('Выход', f'<b>{money(signal.exit_price)}</b>')}\n")
    lines.append(f"{kv('SL', money(signal.stop_loss))}\n")
    lines.append(f"{kv('TP', money(signal.take_profit))}\n")
    if signal.pnl_percent is not None:
        lines.append(f"{kv('P&L', pnl_colored(signal.pnl_percent))}\n")
    if signal.strength:
        lines.append(f"{kv('Сила', strength_bar(signal.strength))}\n")
    lines.append(f"\n<i>{signal.reason}</i>")
    lines.append(footer())
    return "".join(lines)


def format_trade_closed(signal: Signal) -> str:
    if signal.status == "win":
        emoji, label = "✅", "УСПЕХ"
    elif signal.status == "loss":
        emoji, label = "❌", "УБЫТОК"
    else:
        emoji, label = "⏱", "ИСТЁК"

    direction = badge("LONG", style="long") if signal.direction == "long" else badge("SHORT", style="short")
    lev = get_leverage(signal)
    return (
        f"{header(f'{emoji} Сделка закрыта', label)}\n"
        f"{section('Детали')}\n"
        f"  Направление: <b>{direction}</b> · <b>{lev}x</b>\n"
        f"  Вход: <b>{money(signal.entry_price)}</b>\n"
        f"  Выход: <b>{money(signal.exit_price or 0)}</b>\n"
        f"  P&L ({lev}x): <b>{pnl(signal.pnl_percent or 0)}</b>"
    )


def format_liquidation(
    *,
    side: str,
    symbol: str,
    price: float,
    quantity: float,
    usd_value: float,
) -> str:
    if side == "long":
        emoji = "🔥📉"
        title = "Ликвидация LONG"
        desc = "Массовые продажи — закрытие длинных позиций"
    else:
        emoji = "🔥📈"
        title = "Ликвидация SHORT"
        desc = "Массовые покупки — закрытие коротких позиций"

    return (
        f"{header(f'{emoji} {title}', symbol)}\n"
        f"{section('Параметры')}\n"
        f"  Цена: <b>{money(price)}</b>\n"
        f"  Объём: <b>{quantity:.4f} BTC</b>\n"
        f"  Сумма: <b>{money(usd_value)}</b>\n\n"
        f"<i>{desc}</i>"
    )


def format_funding_alert(funding: dict) -> str:
    sign = "+" if funding["rate_pct"] >= 0 else ""
    if funding["rate_pct"] > 0:
        hint = "Высокий funding — перегрев лонгов, возможна коррекция"
    else:
        hint = "Отрицательный funding — перегрев шортов, возможен отскок"
    return (
        f"{header('💸 Экстремальный Funding', 'BTC/USDT Perpetual')}\n"
        f"{section('Ставка')}\n"
        f"  <b>{sign}{funding['rate_pct']:.4f}%</b> ({funding['source']})\n"
        f"  {funding['bias']}\n\n"
        f"<i>{hint}</i>"
    )


def _format_derivatives(deriv: dict | None) -> str:
    if deriv is None:
        return kv("📊 OI / L/S", "<i>недоступно</i>")
    bar = progress_bar(deriv["long_pct"], 100, 8)
    return (
        f"{kv('📊 OI', f'<b>{deriv['open_interest_fmt']}</b> · {deriv['source']}')}\n"
        f"   L/S {bar}  <b>{deriv['long_pct']}%</b>L / <b>{deriv['short_pct']}%</b>S\n"
        f"   {deriv['ls_bias']}"
    )


def format_calculator_intro(total_closed: int) -> str:
    return (
        f"{header('💰 Калькулятор прибыли', 'Шаг 1 из 2 — выберите период')}\n\n"
        f"Закрытых сделок всего: <b>{total_closed}</b>\n\n"
        f"Выберите период, за который хотите посчитать,\n"
        f"сколько бы вы заработали, следуя сигналам бота.\n\n"
        f"<i>В скобках — число сделок за период.</i>"
        f"{footer()}"
    )


def format_calculator_period_step(days: int, trade_count: int) -> str:
    from app.services.profit_calc import period_label

    label = period_label(days)
    return (
        f"{header('💰 Калькулятор прибыли', 'Шаг 2 из 2 — стартовый капитал')}\n\n"
        f"📅 Период: <b>{label}</b>\n"
        f"Сделок за период: <b>{trade_count}</b>\n\n"
        f"Выберите сумму, с которой вы бы начали,\n"
        f"или введите свою."
        f"{footer()}"
    )


def format_calculator_result(sim) -> str:  # noqa: ANN001
    from app.services.profit_calc import ProfitSimulation, period_label

    if not isinstance(sim, ProfitSimulation):
        raise TypeError("sim must be ProfitSimulation")

    win_bar = win_rate_bar(sim.wins / sim.trades * 100 if sim.trades else 0)
    profit_emoji = "📈" if sim.profit_compound >= 0 else "📉"
    period = period_label(sim.period_days)

    return (
        f"{header(f'{profit_emoji} Результат', f'{period} · {money(sim.initial_capital)} · 20x · 10%')}\n"
        f"{section('Заработок')}\n"
        f"{kv('📅 Период', f'<b>{period}</b>')}\n"
        f"{kv('💵 Старт', f'<b>{money(sim.initial_capital)}</b>')}\n"
        f"{kv('💰 Итого', f'<b>{money(sim.final_compound)}</b>')}\n"
        f"{kv('📊 Прибыль', f'<b>{money(sim.profit_compound)}</b> ({pnl_colored(sim.profit_pct_compound)})')}\n"
        f"{section('Сделки')}\n"
        f"{kv('Учтено', f'<b>{sim.trades}</b> из {sim.total_in_period}')}\n"
        f"{kv('Результат', f'✅ {sim.wins} · ❌ {sim.losses}')}\n"
        f"{kv('Win Rate', win_bar)}\n"
        f"{section('Альт. расчёт (без реинвеста)')}\n"
        f"{kv('Итого', f'<b>{money(sim.final_fixed)}</b>')}\n"
        f"{kv('Прибыль', f'{money(sim.profit_fixed)} ({pnl_colored(sim.profit_pct_fixed)})')}\n"
        f"{section('По сделкам')}\n"
        f"{kv('Лучшая', pnl_colored(sim.best_trade_pct))}\n"
        f"{kv('Худшая', pnl_colored(sim.worst_trade_pct))}\n"
        f"{kv('Средняя', pnl_colored(sim.avg_trade_pct))}\n\n"
        f"<i>Расчёт: 10% банка в маржу на сделку · плечо 20x.\n"
        f"⚠️ Прошлые результаты не гарантируют будущую доходность.</i>"
        f"{footer()}"
    )


def format_calculator_empty(*, days: int | None = None) -> str:
    from app.services.profit_calc import period_label

    period_line = ""
    if days is not None:
        period_line = f"\n📅 Период: <b>{period_label(days)}</b>\n"
    return (
        f"{header('💰 Калькулятор прибыли', 'Нет сделок за период')}\n"
        f"{period_line}\n"
        f"За выбранный период закрытых сделок нет.\n"
        f"Попробуйте больший период или дождитесь\n"
        f"закрытия сигналов по TP / SL.\n\n"
        f"<i>Можете посмотреть бэктест на исторических данных.</i>"
        f"{footer()}"
    )


def format_backtest_intro(timeframe: str) -> str:
    from app.utils.backtest_ui import BACKTEST_DAYS, BACKTEST_MAX_TRADES

    limits = " · ".join(BACKTEST_MAX_TRADES.values())
    return (
        f"{header('🔬 Бэктест', 'Симуляция за месяц')}\n\n"
        f"Период: <b>{BACKTEST_DAYS} дней</b>\n"
        f"Таймфрейм: <b>{timeframe}</b>\n"
        f"Плечо: <b>20x</b> · Капитал: <b>$1,000</b>\n"
        f"Ставка: <b>10% банка</b> на сделку\n\n"
        f"Выберите лимит сделок в день:\n"
        f"   {limits}\n\n"
        f"<i>Лимит = максимум входов в сутки, если стратегия\n"
        f"находит условия на рынке (не каждый день).</i>"
        f"{footer()}"
    )


def format_backtest_result(
    result,
    *,
    timeframe: str,
    days: int,
    bars: int,
    max_trades_per_day: int,
) -> str:  # noqa: ANN001
    from app.services.backtest import BacktestResult
    from app.utils.backtest_ui import period_days_from_candles, period_label, trades_per_day_label

    if not isinstance(result, BacktestResult):
        raise TypeError("result must be BacktestResult")

    label = period_label(days)
    limit_label = trades_per_day_label(max_trades_per_day)
    covered = period_days_from_candles(bars, timeframe)
    trades_per_month = len(result.trades) / max(covered, 1) * 30
    history_note = ""
    if covered < days * 0.85:
        history_note = (
            f"\n<i>⚠️ Загружено ~{covered:.0f} дн. из {label} "
            f"({bars} свечей) — лимит API биржи.</i>"
        )
    elif result.trades:
        history_note = (
            f"\n<i>ℹ️ {limit_label} · ~{covered:.0f} дн. · {len(result.trades)} сделок · "
            f"ставка 10% банка · 20x.</i>"
        )

    if not result.trades:
        return (
            f"{header('🔬 Бэктест', f'{label} · {timeframe}')}\n\n"
            f"📊 Лимит: <b>{limit_label}</b>\n"
            f"📊 Свечей загружено: <b>{bars}</b> (~{covered} дн.)\n\n"
            f"За месяц сигналов не найдено.\n"
            f"<i>Попробуйте больший лимит сделок или снизьте\n"
            f"мин. силу сигнала в админке.</i>"
            f"{history_note}"
            f"{footer()}"
        )

    profit = result.final_capital - result.simulated_capital
    profit_emoji = "📈" if profit >= 0 else "📉"

    return (
        f"{header('🔬 Бэктест', f'{label} · {timeframe} · 20x · 10%')}\n"
        f"{section('Настройки')}\n"
        f"{kv('Период', f'<b>{label}</b>')}\n"
        f"{kv('Лимит', f'<b>{limit_label}</b>')}\n"
        f"{kv('Ставка', f'<b>10% банка</b> · <b>20x</b>')}\n"
        f"{kv('Свечей', f'<b>{bars}</b> (~{covered} дн.)')}\n"
        f"{kv('~Сделок/мес', f'<b>{trades_per_month:.1f}</b>')}\n"
        f"{kv('Факт макс/день', f'<b>{result.max_trades_per_day}</b> · ср. <b>{result.avg_trades_per_day:.2f}</b>')}\n"
        f"{section('Сделки')}\n"
        f"{kv('Всего', f'<b>{len(result.trades)}</b>')}\n"
        f"{kv('Результат', f'✅ {result.wins} · ❌ {result.losses}')}\n"
        f"{kv('Win Rate', win_rate_bar(result.win_rate))}\n"
        f"{section('P&L (% к банку, 10% маржа)')}\n"
        f"{kv('Суммарно', pnl_colored(result.total_pnl_pct))}\n"
        f"{kv('Средняя', pnl_colored(result.avg_pnl_pct))}\n"
        f"{kv('Лучшая / Худшая', f'{pnl_colored(result.best_pct)} / {pnl_colored(result.worst_pct)}')}\n"
        f"{section(f'{profit_emoji} Капитал $1000')}\n"
        f"{kv('Итого', f'<b>{money(result.final_capital)}</b>')}\n"
        f"{kv('Прибыль', f'<b>{money(profit)}</b> ({pnl_colored(profit / result.simulated_capital * 100)})')}\n\n"
        f"<i>Расчёт: 10% депозита в маржу · 20x · реинвест.</i>"
        f"{history_note}"
        f"{footer()}"
    )
