"""Telegram message formatting helpers."""

from __future__ import annotations


def separator(char: str = "─", width: int = 24) -> str:
    return char * width


def progress_bar(value: float, max_value: float = 100, length: int = 10) -> str:
    if max_value <= 0:
        return "░" * length
    ratio = max(0.0, min(value / max_value, 1.0))
    filled = round(ratio * length)
    return "█" * filled + "░" * (length - filled)


def strength_bar(strength: int) -> str:
    bar = progress_bar(strength, 100, 10)
    if strength >= 75:
        label = "🔥 Сильный"
    elif strength >= 60:
        label = "✅ Хороший"
    else:
        label = "⚠️ Средний"
    return f"{bar} <b>{strength}</b>/100 — {label}"


def win_rate_bar(win_rate: float) -> str:
    return f"{progress_bar(win_rate, 100, 12)} <b>{win_rate:.1f}%</b>"


def money(value: float) -> str:
    return f"${value:,.2f}"


def pnl(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def header(title: str, subtitle: str | None = None) -> str:
    lines = [f"╔ {title}"]
    if subtitle:
        lines.append(f"╚ <i>{subtitle}</i>")
    return "\n".join(lines)


def section(title: str) -> str:
    return f"\n{separator()} {title}"


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"  ▸ {item}" for item in items)
