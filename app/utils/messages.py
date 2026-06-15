"""User-facing message templates."""

from __future__ import annotations

from app.database.models import Signal
from app.utils.formatting import bullet_list, header, money, pnl, progress_bar, section, strength_bar, win_rate_bar


def welcome_text() -> str:
    return (
        f"{header('₿ BTC Trading Bot', 'Аналитика и сигналы в реальном времени')}\n\n"
        f"{bullet_list([
            'Точки входа LONG / SHORT',
            'Графики с EMA на свечах',
            'Fear & Greed + Funding Rate',
            'Ликвидации с Binance Futures',
            'Статистика и история сделок',
        ])}\n\n"
        f"<i>⚠️ Не финансовый совет. Торгуйте ответственно.</i>"
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
            'История — прошлые сделки',
            'Уведомления — сигналы, ликвидации, funding',
        ])}\n"
        f"{section('Команды')}\n"
        f"{bullet_list([
            '/start — главное меню',
            '/signal — текущий сигнал',
            '/stats — статистика',
            '/admin — панель админа',
        ])}"
    )


def _format_fear_greed(fng: dict | None) -> str:
    if fng is None:
        return "  Fear & Greed: <i>недоступен</i>"
    bar = progress_bar(fng["value"], 100, 10)
    return f"  {fng['emoji']} Fear & Greed: {bar} <b>{fng['value']}</b> — {fng['label']}"


def _format_funding(funding: dict | None) -> str:
    if funding is None:
        return "  Funding: <i>недоступен</i>"
    sign = "+" if funding["rate_pct"] >= 0 else ""
    next_line = ""
    if funding.get("next_funding"):
        next_line = f"\n  След. funding: <b>{funding['next_funding'].strftime('%d.%m %H:%M UTC')}</b>"
    return (
        f"  💸 Funding: <b>{sign}{funding['rate_pct']:.4f}%</b> ({funding['source']})\n"
        f"  {funding['bias']}{next_line}"
    )


def format_stats(stats: dict) -> str:
    total_closed = stats["wins"] + stats["losses"]
    total = stats["total"]
    return (
        f"{header('📈 Статистика', f'{total} сигналов всего')}\n"
        f"{section('Результаты')}\n"
        f"  ✅ Успешных: <b>{stats['wins']}</b>\n"
        f"  ❌ Убыточных: <b>{stats['losses']}</b>\n"
        f"  ⏱ Истекло: <b>{stats['expired']}</b>\n"
        f"  🔄 Открытых: <b>{stats['open']}</b>\n"
        f"{section('Эффективность')}\n"
        f"  Win Rate: {win_rate_bar(stats['win_rate'])}\n"
        f"  Средний P&L: <b>{pnl(stats['avg_pnl'])}</b>\n"
        f"  Закрыто сделок: <b>{total_closed}</b>"
    )


def format_market(snap: dict, timeframe: str, *, fear_greed: dict | None = None, funding: dict | None = None) -> str:
    return (
        f"{header('💹 BTC/USDT', f'Таймфрейм {timeframe}')}\n"
        f"{section('Цена')}\n"
        f"  {money(snap['price'])}\n"
        f"  Тренд: <b>{snap['trend']}</b>\n"
        f"{section('Индикаторы')}\n"
        f"  RSI(14): <b>{snap['rsi']}</b>\n"
        f"  MACD: <b>{snap['macd']}</b> ({snap['macd_hist']})\n"
        f"  Объём: <b>{snap['volume']}</b>\n"
        f"{section('EMA')}\n"
        f"  EMA9:  {money(snap['ema_fast'])}\n"
        f"  EMA21: {money(snap['ema_slow'])}\n"
        f"  EMA55: {money(snap['ema_trend'])}\n"
        f"{section('Сентимент')}\n"
        f"{_format_fear_greed(fear_greed)}\n"
        f"{_format_funding(funding)}"
    )


def format_no_signal(snap: dict) -> str:
    return (
        f"{header('📊 Точка входа', 'Активного сигнала нет')}\n"
        f"{section('Рынок сейчас')}\n"
        f"  Цена: <b>{money(snap['price'])}</b>\n"
        f"  Тренд: {snap['trend']}\n"
        f"  MACD: {snap['macd']}\n"
        f"  RSI: <b>{snap['rsi']}</b>\n\n"
        f"<i>Уведомление придёт, когда стратегия найдёт сильный сигнал.</i>"
    )


def format_dashboard(
    snap: dict,
    stats: dict,
    *,
    has_open: bool,
    fear_greed: dict | None = None,
    funding: dict | None = None,
) -> str:
    signal_state = "🟢 Есть активный сигнал" if has_open else "⚪ Ожидание входа"
    return (
        f"{header('🏠 Дашборд', 'Bitcoin Trading')}\n"
        f"{section('Рынок')}\n"
        f"  BTC: <b>{money(snap['price'])}</b>  {snap['trend']}\n"
        f"  RSI {snap['rsi']} · MACD {snap['macd']}\n"
        f"{section('Сентимент')}\n"
        f"{_format_fear_greed(fear_greed)}\n"
        f"{_format_funding(funding)}\n"
        f"{section('Сигналы')}\n"
        f"  {signal_state}\n"
        f"  Win Rate: {win_rate_bar(stats['win_rate'])}\n"
        f"  P&L: <b>{pnl(stats['avg_pnl'])}</b> · Открыто: <b>{stats['open']}</b>"
    )


def format_signal_card(signal: Signal, *, is_new: bool = False) -> str:
    is_long = signal.direction == "long"
    emoji = "🟢" if is_long else "🔴"
    action = "LONG · Покупка" if is_long else "SHORT · Продажа"
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
        f"{emoji} <b>{action}</b>\n"
        f"  Тип: {type_label}\n"
        f"  {strength_bar(strength)}\n"
        f"{section('Уровни')}\n"
        f"  💰 Вход:  <b>{money(signal.entry_price)}</b>\n"
        f"  🛑 SL:    <b>{money(signal.stop_loss)}</b> (−{sl_pct:.2f}%)\n"
        f"  🎯 TP:    <b>{money(signal.take_profit)}</b> (+{tp_pct:.2f}%)\n"
        f"  📐 R:R    <b>1:{rr}</b>\n"
        f"{section('Анализ')}\n"
        f"  RSI {signal.rsi} · ATR {money(signal.atr)}\n"
        f"  EMA9 {money(signal.ema_fast)} · EMA21 {money(signal.ema_slow)}\n\n"
        f"<i>{signal.reason}</i>"
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
