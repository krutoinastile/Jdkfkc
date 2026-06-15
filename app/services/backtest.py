"""Historical strategy backtest on OHLCV data."""

from __future__ import annotations

from dataclasses import dataclass

from app.database.models import TradeStatus
from app.services.market_data import Candle
from app.services.strategy import TradeSignal, analyze_candles
from app.services.strategy_config import StrategyConfig


@dataclass
class BacktestTrade:
    direction: str
    entry_price: float
    exit_price: float
    pnl_percent: float
    status: str
    strength: int


@dataclass
class BacktestResult:
    trades: list[BacktestTrade]
    wins: int
    losses: int
    win_rate: float
    total_pnl_pct: float
    avg_pnl_pct: float
    best_pct: float
    worst_pct: float
    candles_analyzed: int
    simulated_capital: float
    final_capital: float


def _htf_slice(htf_candles: list[Candle] | None, up_to_time: int) -> list[Candle] | None:
    if not htf_candles:
        return None
    return [c for c in htf_candles if c.open_time <= up_to_time]


def _close_trade(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    candle: Candle,
    strength: int,
) -> BacktestTrade | None:
    if direction == "long":
        if candle.low <= sl:
            pnl = (sl - entry) / entry * 100
            return BacktestTrade(direction, entry, sl, pnl, TradeStatus.LOSS.value, strength)
        if candle.high >= tp:
            pnl = (tp - entry) / entry * 100
            return BacktestTrade(direction, entry, tp, pnl, TradeStatus.WIN.value, strength)
    else:
        if candle.high >= sl:
            pnl = (entry - sl) / entry * 100
            return BacktestTrade(direction, entry, sl, pnl, TradeStatus.LOSS.value, strength)
        if candle.low <= tp:
            pnl = (entry - tp) / entry * 100
            return BacktestTrade(direction, entry, tp, pnl, TradeStatus.WIN.value, strength)
    return None


def _open_from_signal(signal: TradeSignal) -> dict:
    return {
        "direction": signal.direction,
        "entry": signal.entry_price,
        "sl": signal.stop_loss,
        "tp": signal.take_profit,
        "strength": signal.strength,
    }


def run_backtest(
    candles: list[Candle],
    cfg: StrategyConfig,
    *,
    htf_candles: list[Candle] | None = None,
    initial_capital: float = 1000.0,
) -> BacktestResult:
    min_i = cfg.ema_trend + 30
    trades: list[BacktestTrade] = []
    open_pos: dict | None = None
    capital = initial_capital

    for i in range(min_i, len(candles)):
        candle = candles[i]

        if open_pos:
            closed = _close_trade(
                open_pos["direction"],
                open_pos["entry"],
                open_pos["sl"],
                open_pos["tp"],
                candle,
                open_pos["strength"],
            )
            if closed:
                trades.append(closed)
                capital *= 1 + closed.pnl_percent / 100
                open_pos = None

        if open_pos is None:
            window = candles[: i + 1]
            htf = _htf_slice(htf_candles, candle.open_time)
            signal = analyze_candles(window, cfg, htf_candles=htf)
            if signal:
                open_pos = _open_from_signal(signal)

    wins = sum(1 for t in trades if t.status == TradeStatus.WIN.value)
    losses = len(trades) - wins
    pnls = [t.pnl_percent for t in trades]
    closed = wins + losses
    win_rate = (wins / closed * 100) if closed else 0.0
    total_pnl = sum(pnls) if pnls else 0.0

    return BacktestResult(
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 1),
        total_pnl_pct=round(total_pnl, 2),
        avg_pnl_pct=round(total_pnl / len(pnls), 2) if pnls else 0.0,
        best_pct=round(max(pnls), 2) if pnls else 0.0,
        worst_pct=round(min(pnls), 2) if pnls else 0.0,
        candles_analyzed=len(candles) - min_i,
        simulated_capital=initial_capital,
        final_capital=round(capital, 2),
    )
