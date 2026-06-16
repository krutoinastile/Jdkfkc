"""Generate BTC price charts with EMA, volume and RSI panels."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from datetime import UTC, datetime

from app.services.indicators import ema, rsi
from app.services.market_data import Candle

if TYPE_CHECKING:
    from app.database.models import Signal
    from app.services.strategy_config import StrategyConfig

CHART_CANDLES = 60
BG = "#0d0f14"
PANEL = "#13161e"
GRID = "#252a35"
TEXT = "#e8eaed"
MUTED = "#8b919a"
GREEN = "#00e676"
RED = "#ff5252"
EMA_COLORS = ("#ffca28", "#42a5f5", "#ab47bc")
RSI_HIGH = "#ff5252"
RSI_LOW = "#00e676"


def _style_ax(ax, *, show_x: bool = True) -> None:
    ax.set_facecolor(PANEL)
    ax.grid(True, color=GRID, alpha=0.45, linewidth=0.4)
    ax.tick_params(axis="y", colors=MUTED, labelsize=7)
    if show_x:
        ax.tick_params(axis="x", colors=MUTED, labelsize=7)
    else:
        ax.tick_params(axis="x", labelbottom=False)
    for spine in ax.spines.values():
        spine.set_color(GRID)


def render_chart(
    candles: list[Candle],
    cfg: StrategyConfig,
    signal: Signal | None = None,
) -> bytes:
    display = candles[-CHART_CANDLES:]
    if len(display) < 10:
        raise ValueError("Not enough candles for chart")

    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    ema_fast = ema(closes, cfg.ema_fast)
    ema_slow = ema(closes, cfg.ema_slow)
    ema_trend = ema(closes, cfg.ema_trend)
    rsi_vals = rsi(closes, cfg.rsi_period)
    offset = len(candles) - len(display)

    times = [datetime.fromtimestamp(c.open_time / 1000, tz=UTC) for c in display]

    fig = plt.figure(figsize=(10, 7.5), facecolor=BG)
    gs = fig.add_gridspec(3, 1, height_ratios=[3.2, 0.9, 0.9], hspace=0.06)
    ax_price = fig.add_subplot(gs[0])
    ax_vol = fig.add_subplot(gs[1], sharex=ax_price)
    ax_rsi = fig.add_subplot(gs[2], sharex=ax_price)

    for ax in (ax_price, ax_vol, ax_rsi):
        _style_ax(ax, show_x=ax is ax_rsi)

    for i, candle in enumerate(display):
        color = GREEN if candle.close >= candle.open else RED
        ax_price.plot([i, i], [candle.low, candle.high], color=color, linewidth=1, alpha=0.85)
        body_bottom = min(candle.open, candle.close)
        body_height = max(abs(candle.close - candle.open), (candle.high - candle.low) * 0.02)
        ax_price.add_patch(
            Rectangle((i - 0.35, body_bottom), 0.7, body_height, facecolor=color, edgecolor=color, linewidth=0)
        )
        vol_color = color if candle.close >= candle.open else RED
        ax_vol.bar(i, candle.volume, width=0.7, color=vol_color, alpha=0.65, edgecolor="none")

    for values, color, label in (
        (ema_fast, EMA_COLORS[0], f"EMA{cfg.ema_fast}"),
        (ema_slow, EMA_COLORS[1], f"EMA{cfg.ema_slow}"),
        (ema_trend, EMA_COLORS[2], f"EMA{cfg.ema_trend}"),
    ):
        if values:
            segment = values[offset:]
            ax_price.plot(range(len(segment)), segment, color=color, linewidth=1.5, label=label, alpha=0.95)

    if signal is not None:
        ax_price.axhline(signal.entry_price, color="#ffffff", linestyle="--", linewidth=1, alpha=0.85, label="Entry")
        ax_price.axhline(signal.stop_loss, color=RED, linestyle=":", linewidth=1.3, alpha=0.9, label="SL")
        ax_price.axhline(signal.take_profit, color=GREEN, linestyle=":", linewidth=1.3, alpha=0.9, label="TP")

    if rsi_vals:
        rsi_segment = rsi_vals[offset:]
        ax_rsi.plot(range(len(rsi_segment)), rsi_segment, color="#7c4dff", linewidth=1.3)
        ax_rsi.axhline(70, color=RSI_HIGH, linestyle="--", linewidth=0.8, alpha=0.7)
        ax_rsi.axhline(30, color=RSI_LOW, linestyle="--", linewidth=0.8, alpha=0.7)
        ax_rsi.fill_between(range(len(rsi_segment)), 30, 70, color="#7c4dff", alpha=0.06)
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_ylabel("RSI", color=MUTED, fontsize=7)

    last_price = display[-1].close
    ax_price.annotate(
        f" ${last_price:,.0f}",
        xy=(len(display) - 1, last_price),
        xytext=(6, 0),
        textcoords="offset points",
        color=TEXT,
        fontsize=9,
        fontweight="bold",
        va="center",
    )

    tick_step = max(1, len(display) // 5)
    tick_idx = list(range(0, len(display), tick_step))
    ax_rsi.set_xticks(tick_idx)
    ax_rsi.set_xticklabels(
        [times[i].strftime("%d.%m %H:%M") for i in tick_idx],
        rotation=20,
        ha="right",
        color=MUTED,
        fontsize=7,
    )

    title = f"BTC/USDT  ·  {cfg.timeframe}"
    if signal is not None:
        direction = "LONG 🟢" if signal.direction == "long" else "SHORT 🔴"
        title += f"  ·  {direction}"
    ax_price.set_title(title, color=TEXT, fontsize=13, pad=14, fontweight="bold", loc="left")
    ax_price.legend(loc="upper left", fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, framealpha=0.9)
    ax_vol.set_ylabel("Vol", color=MUTED, fontsize=7)

    fig.text(0.98, 0.01, "BTC Trading Bot", ha="right", va="bottom", color=MUTED, fontsize=7, alpha=0.6)
    fig.subplots_adjust(left=0.08, right=0.96, top=0.94, bottom=0.1)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def render_equity_curve(equity: list[float], *, initial: float = 1000.0, title: str = "Equity Curve") -> bytes:
    if len(equity) < 2:
        equity = [initial, initial]

    fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG)
    _style_ax(ax)
    xs = list(range(len(equity)))
    color = GREEN if equity[-1] >= initial else RED
    ax.plot(xs, equity, color=color, linewidth=2)
    ax.fill_between(xs, initial, equity, alpha=0.12, color=color)
    ax.axhline(initial, color=MUTED, linestyle="--", linewidth=0.8, alpha=0.7)
    ax.set_title(title, color=TEXT, fontsize=12, loc="left", pad=10)
    ax.set_ylabel("Capital $", color=MUTED, fontsize=8)
    ax.set_xlabel("Сделка #", color=MUTED, fontsize=8)
    fig.text(0.98, 0.02, f"${equity[-1]:,.0f}", ha="right", color=color, fontsize=11, fontweight="bold")
    fig.subplots_adjust(left=0.1, right=0.96, top=0.9, bottom=0.14)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()
