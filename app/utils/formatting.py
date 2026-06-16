"""Telegram message formatting helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def separator(char: str = "─", width: int = 22) -> str:
    return char * width


def footer() -> str:
    now = datetime.now(tz=UTC).strftime("%d.%m.%Y %H:%M UTC")
    return f"\n<code>╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌</code>\n<i>🕐 {now}</i>"


def progress_bar(value: float, max_value: float = 100, length: int = 10) -> str:
    if max_value <= 0:
        return "░" * length
    ratio = max(0.0, min(value / max_value, 1.0))
    filled = round(ratio * length)
    return "█" * filled + "░" * (length - filled)


def emoji_bar(value: float, max_value: float = 100, length: int = 8) -> str:
    if max_value <= 0:
        return "⬜" * length
    ratio = max(0.0, min(value / max_value, 1.0))
    filled = round(ratio * length)
    return "🟩" * filled + "⬜" * (length - filled)


def strength_bar(strength: int) -> str:
    bar = emoji_bar(strength, 100, 8)
    if strength >= 75:
        label = "🔥 Сильный"
    elif strength >= 60:
        label = "✅ Хороший"
    else:
        label = "⚠️ Средний"
    return f"{bar}  <b>{strength}</b>/100 · {label}"


def win_rate_bar(win_rate: float) -> str:
    return f"{emoji_bar(win_rate, 100, 8)}  <b>{win_rate:.1f}%</b>"


def rsi_bar(rsi: float) -> str:
    bar = emoji_bar(rsi, 100, 8)
    if rsi >= 70:
        state = "🔴 Перекуплен"
    elif rsi <= 30:
        state = "🟢 Перепродан"
    else:
        state = "⚪ Нейтрально"
    return f"{bar}  <b>{rsi:.1f}</b> · {state}"


def money(value: float) -> str:
    return f"${value:,.2f}"


def pnl(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def pnl_colored(value: float) -> str:
    if value > 0:
        return f"🟢 <b>+{value:.2f}%</b>"
    if value < 0:
        return f"🔴 <b>{value:.2f}%</b>"
    return f"⚪ <b>0.00%</b>"


def header(title: str, subtitle: str | None = None) -> str:
    line = separator("━", 24)
    lines = [f"┏{line}┓", f"┃  {title}", f"┗{line}┛"]
    if subtitle:
        lines.append(f"<i>   {subtitle}</i>")
    return "\n".join(lines)


def section(title: str) -> str:
    return f"\n▸ <b>{title}</b>\n<code>{separator()}</code>"


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"   {item}" for item in items)


def kv(key: str, value: str) -> str:
    return f"   {key}  {value}"


def badge(text: str, *, style: str = "default") -> str:
    styles = {
        "on": "🟢",
        "off": "⚫",
        "long": "🟢",
        "short": "🔴",
        "wait": "⚪",
        "active": "🟡",
        "default": "▫️",
    }
    icon = styles.get(style, "▫️")
    return f"{icon} {text}"


def signal_status(has_open: bool) -> str:
    if has_open:
        return badge("Активный сигнал", style="active")
    return badge("Ожидание входа", style="wait")
