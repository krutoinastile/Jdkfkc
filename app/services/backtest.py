"""Historical strategy backtest on OHLCV data (aligned with live trade rules)."""

from __future__ import annotations

from dataclasses import dataclass

from collections.abc import Callable

from app.database.models import TradeStatus
from app.services.market_data import Candle
from app.services.strategy import TradeSignal, analyze_candles
from app.utils.leverage import DEFAULT_BANK_ALLOCATION_PCT, pnl_on_bank, spot_to_leveraged
from app.services.strategy_config import StrategyConfig

Analyzer = Callable[[list[Candle], StrategyConfig, list[Candle] | None], TradeSignal | None]

EXPIRE_HOURS = 72


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
    equity_curve: list[float] | None = None
    buy_hold_pct: float = 0.0
    buy_hold_final: float = 0.0


def _htf_slice(htf_candles: list[Candle] | None, up_to_time: int) -> list[Candle] | None:
    if not htf_candles:
        return None
    return [c for c in htf_candles if c.open_time <= up_to_time]


def _margin_spot_pct(direction: str, entry: float, exit_price: float) -> float:
    if direction == "long":
        return (exit_price - entry) / entry * 100
    return (entry - exit_price) / entry * 100


def _margin_pnl(direction: str, entry: float, exit_price: float, leverage: int) -> float:
    return spot_to_leveraged(_margin_spot_pct(direction, entry, exit_price), leverage)


def _combined_pnl(partial_hit: bool, partial_pnl: float | None, margin_pnl: float) -> float:
    if partial_hit and partial_pnl is not None:
        return round(partial_pnl + margin_pnl * 0.5, 2)
    return round(margin_pnl, 2)


from app.services.trailing_sl import compute_trailing_stop


def _partial_tp_price(direction: str, entry: float, risk: float) -> float:
    if direction == "long":
        return entry + 2 * risk
    return entry - 2 * risk


def _close_from_position(
    pos: dict,
    exit_price: float,
    leverage: int,
    *,
    status: str | None = None,
) -> BacktestTrade:
    direction = pos["direction"]
    entry = pos["entry"]
    partial_hit = pos.get("partial_tp_hit", False)
    partial_pnl = pos.get("partial_pnl_percent")
    remaining = 0.5 if partial_hit else 1.0
    margin = _margin_pnl(direction, entry, exit_price, leverage) * remaining
    pnl = _combined_pnl(partial_hit, partial_pnl, margin)
    if status is None:
        spot = _margin_spot_pct(direction, entry, exit_price)
        status = TradeStatus.WIN.value if spot > 0 else TradeStatus.LOSS.value
    return BacktestTrade(
        direction,
        entry,
        exit_price,
        pnl,
        status,
        pos["strength"],
        pos["open_time"],
    )


def _process_open_position(pos: dict, candle: Candle, leverage: int) -> BacktestTrade | None:
    direction = pos["direction"]
    entry = pos["entry"]
    sl = pos["sl"]
    initial_sl = pos["initial_sl"]
    tp = pos["tp"]
    atr = pos["atr"]
    open_time = pos["open_time"]
    risk = abs(entry - initial_sl)

    hours_open = (candle.open_time - open_time) / 3_600_000
    if hours_open >= EXPIRE_HOURS:
        return _close_from_position(pos, candle.close, leverage)

    fav = candle.high if direction == "long" else candle.low
    adv = candle.low if direction == "long" else candle.high

    sl_new, _ = compute_trailing_stop(
        direction=direction,
        entry=entry,
        current_sl=sl,
        initial_sl=initial_sl,
        atr=atr,
        price=fav,
    )
    if sl_new is not None:
        sl = sl_new
    pos["sl"] = sl

    if pos.get("partial_tp_enabled") and not pos.get("partial_tp_hit") and risk > 0:
        pt = _partial_tp_price(direction, entry, risk)
        hit = fav >= pt if direction == "long" else fav <= pt
        if hit:
            pos["partial_tp_hit"] = True
            pos["partial_pnl_percent"] = _margin_pnl(direction, entry, pt, leverage) * 0.5

    if direction == "long":
        if adv <= sl:
            return _close_from_position(pos, sl, leverage)
        if fav >= tp:
            return _close_from_position(pos, tp, leverage, status=TradeStatus.WIN.value)
    else:
        if adv >= sl:
            return _close_from_position(pos, sl, leverage)
        if fav <= tp:
            return _close_from_position(pos, tp, leverage, status=TradeStatus.WIN.value)
    return None


def _open_from_signal(signal: TradeSignal, *, open_time: int, partial_tp_enabled: bool) -> dict:
    return {
        "direction": signal.direction,
        "entry": signal.entry_price,
        "sl": signal.stop_loss,
        "initial_sl": signal.stop_loss,
        "tp": signal.take_profit,
        "strength": signal.strength,
        "open_time": open_time,
        "atr": signal.atr_value,
        "partial_tp_hit": False,
        "partial_pnl_percent": None,
        "partial_tp_enabled": partial_tp_enabled,
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
    analyzer: Analyzer | None = None,
) -> BacktestResult:
    analyze = analyzer or analyze_candles
    min_i = cfg.ema_trend + 30
    trades: list[BacktestTrade] = []
    open_pos: dict | None = None
    capital = initial_capital
    equity_curve: list[float] = [capital]
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
            closed = _process_open_position(open_pos, candle, cfg.leverage)
            if closed:
                trades.append(closed)
                bank_pnl = pnl_on_bank(closed.pnl_percent, DEFAULT_BANK_ALLOCATION_PCT)
                capital *= 1 + bank_pnl / 100
                equity_curve.append(round(capital, 2))
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
            signal = analyze(window, cfg, htf)
            if signal:
                open_pos = _open_from_signal(
                    signal, open_time=candle.open_time, partial_tp_enabled=cfg.partial_tp_enabled,
                )
                last_open_time = candle.open_time
                signals_today += 1

    if open_pos and candles:
        closed = _close_from_position(open_pos, candles[-1].close, cfg.leverage)
        trades.append(closed)
        bank_pnl = pnl_on_bank(closed.pnl_percent, DEFAULT_BANK_ALLOCATION_PCT)
        capital *= 1 + bank_pnl / 100
        equity_curve.append(round(capital, 2))

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

    start_price = candles[min_i].close
    end_price = candles[-1].close
    buy_hold_pct = (end_price - start_price) / start_price * 100 if start_price else 0.0
    buy_hold_final = round(initial_capital * (1 + buy_hold_pct / 100), 2)

    return BacktestResult(
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 1),
        total_pnl_pct=round(total_pnl, 2),
        avg_pnl_pct=round(total_pnl / len(bank_pnls), 2) if bank_pnls else 0.0,
        best_pct=round(max(bank_pnls), 2) if bank_pnls else 0.0,
        worst_pct=round(min(bank_pnls), 2) if bank_pnls else 0.0,
        candles_analyzed=len(candles) - min_i,
        simulated_capital=initial_capital,
        final_capital=round(capital, 2),
        max_trades_per_day=max_trades_per_day,
        avg_trades_per_day=round(avg_trades_per_day, 2),
        equity_curve=equity_curve,
        buy_hold_pct=round(buy_hold_pct, 2),
        buy_hold_final=buy_hold_final,
    )
