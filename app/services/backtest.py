"""Historical strategy backtest on OHLCV data."""

from __future__ import annotations

from dataclasses import dataclass

from app.database.models import TradeStatus
from app.services.market_data import Candle
from app.services.strategy import TradeSignal, analyze_candles
from app.utils.leverage import DEFAULT_BANK_ALLOCATION_PCT, pnl_on_bank, spot_to_leveraged
from app.services.strategy_config import StrategyConfig


@dataclass
class BacktestTrade:
    direction: str
    entry_price: float
    exit_price: float
    pnl_percent: float
    status: str
    strength: int
    open_time: int


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
    max_trades_per_day: int = 0
    avg_trades_per_day: float = 0.0


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
    open_time: int,
) -> BacktestTrade | None:
    if direction == "long":
        if candle.low <= sl:
            pnl = (sl - entry) / entry * 100
            return BacktestTrade(direction, entry, sl, pnl, TradeStatus.LOSS.value, strength, open_time)
        if candle.high >= tp:
            pnl = (tp - entry) / entry * 100
            return BacktestTrade(direction, entry, tp, pnl, TradeStatus.WIN.value, strength, open_time)
    else:
        if candle.high >= sl:
            pnl = (entry - sl) / entry * 100
            return BacktestTrade(direction, entry, sl, pnl, TradeStatus.LOSS.value, strength, open_time)
        if candle.low <= tp:
            pnl = (entry - tp) / entry * 100
            return BacktestTrade(direction, entry, tp, pnl, TradeStatus.WIN.value, strength, open_time)
    return None


def _open_from_signal(signal: TradeSignal, *, open_time: int) -> dict:
    return {
        "direction": signal.direction,
        "entry": signal.entry_price,
        "sl": signal.stop_loss,
        "tp": signal.take_profit,
        "strength": signal.strength,
        "open_time": open_time,
    }


def _utc_day(ms: int) -> int:
    return ms // 86_400_000


def _hours_between(earlier_ms: int, later_ms: int) -> float:
    return (later_ms - earlier_ms) / 3_600_000


def _can_open_new_backtest_signal(
    *,
    candle_time: int,
    last_open_time: int | None,
    signals_today: int,
    min_hours: float,
    max_per_day: int,
) -> bool:
    if max_per_day > 0 and signals_today >= max_per_day:
        return False
    if min_hours > 0 and last_open_time is not None:
        if _hours_between(last_open_time, candle_time) < min_hours:
            return False
    return True


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
    last_open_time: int | None = None
    signals_day: int | None = None
    signals_today = 0

    for i in range(min_i, len(candles)):
        candle = candles[i]
        candle_day = _utc_day(candle.open_time)
        if signals_day != candle_day:
            signals_day = candle_day
            signals_today = 0

        if open_pos:
            closed = _close_trade(
                open_pos["direction"],
                open_pos["entry"],
                open_pos["sl"],
                open_pos["tp"],
                candle,
                open_pos["strength"],
                open_pos["open_time"],
            )
            if closed:
                closed.pnl_percent = spot_to_leveraged(closed.pnl_percent, cfg.leverage)
                trades.append(closed)
                bank_pnl = pnl_on_bank(closed.pnl_percent, DEFAULT_BANK_ALLOCATION_PCT)
                capital *= 1 + bank_pnl / 100
                open_pos = None

        if open_pos is None:
            if not _can_open_new_backtest_signal(
                candle_time=candle.open_time,
                last_open_time=last_open_time,
                signals_today=signals_today,
                min_hours=cfg.min_hours_between_signals,
                max_per_day=cfg.max_signals_per_day,
            ):
                continue
            window = candles[: i + 1]
            htf = _htf_slice(htf_candles, candle.open_time)
            signal = analyze_candles(window, cfg, htf_candles=htf)
            if signal:
                open_pos = _open_from_signal(signal, open_time=candle.open_time)
                last_open_time = candle.open_time
                signals_today += 1

    wins = sum(1 for t in trades if t.status == TradeStatus.WIN.value)
    losses = len(trades) - wins
    margin_pnls = [t.pnl_percent for t in trades]
    bank_pnls = [pnl_on_bank(p, DEFAULT_BANK_ALLOCATION_PCT) for p in margin_pnls]
    closed = wins + losses
    win_rate = (wins / closed * 100) if closed else 0.0
    total_pnl = sum(bank_pnls) if bank_pnls else 0.0

    per_day: dict[int, int] = {}
    for trade in trades:
        day = _utc_day(trade.open_time)
        per_day[day] = per_day.get(day, 0) + 1
    max_trades_per_day = max(per_day.values()) if per_day else 0
    span_days = max((candles[-1].open_time - candles[min_i].open_time) / 86_400_000, 1)
    avg_trades_per_day = len(trades) / span_days

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
        max_trades_per_day=max_trades_per_day,
        avg_trades_per_day=round(avg_trades_per_day, 2),
    )
