"""Generate BTC price charts with EMA overlays."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from datetime import UTC, datetime

from app.services.indicators import ema
from app.services.market_data import Candle

if TYPE_CHECKING:
    from app.database.models import Signal
    from app.services.strategy_config import StrategyConfig

CHART_CANDLES = 60
BG = "#0f1117"
GRID = "#2a2d3a"
TEXT = "#e8eaed"
GREEN = "#00c853"
RED = "#ff5252"
EMA_COLORS = ("#ffd740", "#448aff", "#ea80fc")


def render_chart(
    candles: list[Candle],
    cfg: StrategyConfig,
    signal: Signal | None = None,
) -> bytes:
    display = candles[-CHART_CANDLES:]
    if len(display) < 10:
        raise ValueError("Not enough candles for chart")

    closes = [c.close for c in candles]
    ema_fast = ema(closes, cfg.ema_fast)
    ema_slow = ema(closes, cfg.ema_slow)
    ema_trend = ema(closes, cfg.ema_trend)
    offset = len(candles) - len(display)

    times = [datetime.fromtimestamp(c.open_time / 1000, tz=UTC) for c in display]
    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=BG)
    ax.set_facecolor(BG)

    for i, candle in enumerate(display):
        color = GREEN if candle.close >= candle.open else RED
        ax.plot([i, i], [candle.low, candle.high], color=color, linewidth=1, alpha=0.9)
        body_bottom = min(candle.open, candle.close)
        body_height = max(abs(candle.close - candle.open), (candle.high - candle.low) * 0.02)
        ax.add_patch(
            Rectangle(
                (i - 0.35, body_bottom),
                0.7,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0,
            )
        )

    for values, color, label in (
        (ema_fast, EMA_COLORS[0], f"EMA{cfg.ema_fast}"),
        (ema_slow, EMA_COLORS[1], f"EMA{cfg.ema_slow}"),
        (ema_trend, EMA_COLORS[2], f"EMA{cfg.ema_trend}"),
    ):
        if values:
            segment = values[offset:]
            ax.plot(range(len(segment)), segment, color=color, linewidth=1.4, label=label, alpha=0.9)

    if signal is not None:
        ax.axhline(signal.entry_price, color="#ffffff", linestyle="--", linewidth=1, alpha=0.8, label="Entry")
        ax.axhline(signal.stop_loss, color=RED, linestyle=":", linewidth=1.2, alpha=0.9, label="SL")
        ax.axhline(signal.take_profit, color=GREEN, linestyle=":", linewidth=1.2, alpha=0.9, label="TP")

    tick_step = max(1, len(display) // 6)
    ax.set_xticks(range(0, len(display), tick_step))
    ax.set_xticklabels(
        [times[i].strftime("%d.%m %H:%M") for i in range(0, len(display), tick_step)],
        rotation=25,
        ha="right",
        color=TEXT,
        fontsize=8,
    )
    ax.tick_params(axis="y", colors=TEXT, labelsize=8)
    ax.grid(True, color=GRID, alpha=0.5, linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color(GRID)

    title = f"BTC/USDT · {cfg.timeframe}"
    if signal is not None:
        direction = "LONG" if signal.direction == "long" else "SHORT"
        title += f" · {direction}"
    ax.set_title(title, color=TEXT, fontsize=12, pad=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=7, facecolor=BG, edgecolor=GRID, labelcolor=TEXT)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
