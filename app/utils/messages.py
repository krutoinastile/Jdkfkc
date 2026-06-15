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


def welcome_text() -> str:
    return (
        f"{header('₿ BTC Trading Bot', 'Аналитика и сигналы в реальном времени')}\n"
        f"{section('Возможности')}\n"
        f"{bullet_list([
            '📊 Сигналы LONG / SHORT с графиками',
            '📈 EMA · RSI · MACD · ATR стратегия',
            '😱 Fear & Greed · Funding · Open Interest',
            '🔥 Ликвидации Binance Futures',
            '💰 Калькулятор прибыли · Бэктест',
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
            'Калькулятор — сколько бы вы заработали',
            'Бэктест — проверка на истории',
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


def format_signal_card(signal: Signal, *, is_new: bool = False) -> str:
    is_long = signal.direction == "long"
    dir_badge = badge("LONG · Покупка", style="long") if is_long else badge("SHORT · Продажа", style="short")
    title = "🚨 Новый сигнал" if is_new else "📊 Активный сигнал"
    type_label = "Пересечение EMA" if signal.signal_type == "crossover" else "Откат к EMA"
    strength = getattr(signal, "strength", 0) or 0

    risk = abs(signal.entry_price - signal.stop_loss)
    reward = abs(signal.take_profit - signal.entry_price)
    rr = round(reward / risk, 2) if risk > 0 else 0

    sl_pct = abs(signal.stop_loss - signal.entry_price) / signal.entry_price * 100
    tp_pct = abs(signal.take_profit - signal.entry_price) / signal.entry_price * 100

    return (
        f"{header(title, 'BTC/USDT · ' + signal.timeframe)}\n\n"
        f"   {dir_badge} · {type_label}\n"
        f"   {strength_bar(strength)}\n"
        f"{section('Уровни')}\n"
        f"{kv('💰 Вход', f'<b>{money(signal.entry_price)}</b>')}\n"
        f"{kv('🛑 SL', f'<b>{money(signal.stop_loss)}</b> (−{sl_pct:.2f}%)')}\n"
        f"{kv('🎯 TP', f'<b>{money(signal.take_profit)}</b> (+{tp_pct:.2f}%)')}\n"
        f"{kv('📐 R:R', f'<b>1:{rr}</b>')}\n"
        f"{section('Анализ')}\n"
        f"{kv('RSI', str(signal.rsi))}\n"
        f"{kv('ATR', money(signal.atr))}\n"
        f"{kv('EMA', f'{money(signal.ema_fast)} / {money(signal.ema_slow)}')}\n\n"
        f"<i>{signal.reason}</i>"
        f"{footer()}"
    )


def format_history_item(signal: Signal) -> str:
    icons = {"win": "✅", "loss": "❌", "open": "🔄", "expired": "⏱"}
    icon = icons.get(signal.status, "·")
    direction = "🟢L" if signal.direction == "long" else "🔴S"
    pnl_str = f" · <b>{pnl(signal.pnl_percent)}</b>" if signal.pnl_percent is not None else ""
    strength = f" · {signal.strength}/100" if signal.strength else ""
    return f"{icon} {direction} {money(signal.entry_price)}{strength}{pnl_str}"


def format_history(signals: list[Signal], *, page: int) -> str:
    lines = [f"{header('📜 История сделок', f'Страница {page + 1}')}\n"]
    lines.extend(format_history_item(s) for s in signals)
    return "\n".join(lines)


def format_trade_closed(signal: Signal) -> str:
    if signal.status == "win":
        emoji, label = "✅", "УСПЕХ"
    elif signal.status == "loss":
        emoji, label = "❌", "УБЫТОК"
    else:
        emoji, label = "⏱", "ИСТЁК"

    direction = "🟢 LONG" if signal.direction == "long" else "🔴 SHORT"
    return (
        f"{header(f'{emoji} Сделка закрыта', label)}\n"
        f"{section('Детали')}\n"
        f"  Направление: <b>{direction}</b>\n"
        f"  Вход: <b>{money(signal.entry_price)}</b>\n"
        f"  Выход: <b>{money(signal.exit_price or 0)}</b>\n"
        f"  P&L: <b>{pnl(signal.pnl_percent or 0)}</b>"
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


def format_calculator_intro(closed_count: int) -> str:
    return (
        f"{header('💰 Калькулятор прибыли', 'Симуляция по сигналам бота')}\n\n"
        f"Закрытых сделок в базе: <b>{closed_count}</b>\n\n"
        f"Выберите стартовый капитал или введите свою сумму.\n"
        f"Расчёт покажет результат при следовании <b>всем</b> сигналам бота.\n\n"
        f"<i>Два режима: сложный % (реинвест) и фиксированный %.</i>"
    )


def format_calculator_result(sim, *, closed_count: int) -> str:  # noqa: ANN001
    from app.services.profit_calc import ProfitSimulation

    if not isinstance(sim, ProfitSimulation):
        raise TypeError("sim must be ProfitSimulation")

    win_bar = win_rate_bar(sim.wins / sim.trades * 100 if sim.trades else 0)
    profit_emoji = "📈" if sim.profit_compound >= 0 else "📉"

    return (
        f"{header(f'{profit_emoji} Результат калькулятора', f'Капитал {money(sim.initial_capital)}')}\n"
        f"{section('Сделки')}\n"
        f"  Учтено: <b>{sim.trades}</b> из {closed_count}\n"
        f"  ✅ {sim.wins} · ❌ {sim.losses}\n"
        f"  Win Rate: {win_bar}\n"
        f"{section('Сложный % (реинвест)')}\n"
        f"  Итого: <b>{money(sim.final_compound)}</b>\n"
        f"  Прибыль: <b>{money(sim.profit_compound)}</b> ({pnl(sim.profit_pct_compound)})\n"
        f"{section('Фиксированный %')}\n"
        f"  Итого: <b>{money(sim.final_fixed)}</b>\n"
        f"  Прибыль: <b>{money(sim.profit_fixed)}</b> ({pnl(sim.profit_pct_fixed)})\n"
        f"{section('По сделкам')}\n"
        f"  Лучшая: <b>{pnl(sim.best_trade_pct)}</b>\n"
        f"  Худшая: <b>{pnl(sim.worst_trade_pct)}</b>\n"
        f"  Средняя: <b>{pnl(sim.avg_trade_pct)}</b>\n\n"
        f"<i>⚠️ Прошлые результаты не гарантируют будущую доходность.</i>"
    )


def format_calculator_empty() -> str:
    return (
        f"{header('💰 Калькулятор прибыли', 'Пока нет данных')}\n\n"
        f"Закрытых сделок ещё нет — калькулятор заработает,\n"
        f"когда бот закроет первые сигналы по TP или SL.\n\n"
        f"<i>Можете посмотреть бэктест на исторических данных.</i>"
    )


def format_backtest_result(result, *, timeframe: str, bars: int) -> str:  # noqa: ANN001
    from app.services.backtest import BacktestResult

    if not isinstance(result, BacktestResult):
        raise TypeError("result must be BacktestResult")

    if not result.trades:
        return (
            f"{header('🔬 Бэктест', f'{timeframe} · {bars} свечей')}\n\n"
            f"За выбранный период сигналов не найдено.\n"
            f"<i>Попробуйте другой таймфрейм в админке.</i>"
        )

    profit = result.final_capital - result.simulated_capital
    profit_emoji = "📈" if profit >= 0 else "📉"

    return (
        f"{header('🔬 Бэктест стратегии', f'{timeframe} · {bars} свечей')}\n"
        f"{section('Сделки')}\n"
        f"  Всего: <b>{len(result.trades)}</b>\n"
        f"  ✅ {result.wins} · ❌ {result.losses}\n"
        f"  Win Rate: {win_rate_bar(result.win_rate)}\n"
        f"{section('P&L')}\n"
        f"  Суммарно: <b>{pnl(result.total_pnl_pct)}</b>\n"
        f"  Средняя сделка: <b>{pnl(result.avg_pnl_pct)}</b>\n"
        f"  Лучшая / Худшая: <b>{pnl(result.best_pct)}</b> / <b>{pnl(result.worst_pct)}</b>\n"
        f"{section(f'{profit_emoji} Капитал $1000')}\n"
        f"  Итого: <b>{money(result.final_capital)}</b>\n"
        f"  Прибыль: <b>{money(profit)}</b> ({pnl(profit / result.simulated_capital * 100)})\n\n"
        f"<i>Симуляция на истории. Реальная торговля может отличаться.</i>"
    )
