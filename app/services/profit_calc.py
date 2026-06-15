"""Profit simulation from closed bot signals."""

from __future__ import annotations

from dataclasses import dataclass

from app.database.models import Signal, TradeStatus
from app.utils.leverage import DEFAULT_BANK_ALLOCATION_PCT, pnl_on_bank

PERIOD_OPTIONS: dict[int, str] = {
    7: "7 дней",
    30: "30 дней",
    90: "90 дней",
    180: "180 дней",
    0: "Всё время",
}


def period_label(days: int) -> str:
    return PERIOD_OPTIONS.get(days, f"{days} дн.")


@dataclass
class ProfitSimulation:
    initial_capital: float
    final_compound: float
    final_fixed: float
    profit_compound: float
    profit_fixed: float
    profit_pct_compound: float
    profit_pct_fixed: float
    trades: int
    wins: int
    losses: int
    best_trade_pct: float
    worst_trade_pct: float
    avg_trade_pct: float
    period_days: int
    total_in_period: int


def _closed_trades(signals: list[Signal]) -> list[Signal]:
    closed = [
        s for s in signals
        if s.status in (TradeStatus.WIN.value, TradeStatus.LOSS.value)
        and s.pnl_percent is not None
    ]
    return sorted(closed, key=lambda s: s.opened_at)


def simulate_profit(
    signals: list[Signal],
    initial_capital: float,
    *,
    period_days: int = 0,
    total_in_period: int = 0,
) -> ProfitSimulation | None:
    trades = _closed_trades(signals)
    if not trades:
        return None

    compound = initial_capital
    fixed_total_pct = 0.0
    pnls = [t.pnl_percent for t in trades if t.pnl_percent is not None]
    wins = sum(1 for t in trades if t.status == TradeStatus.WIN.value)
    losses = len(trades) - wins

    for trade in trades:
        margin_pct = trade.pnl_percent or 0.0
        bank_pct = pnl_on_bank(margin_pct, DEFAULT_BANK_ALLOCATION_PCT)
        compound *= 1 + bank_pct / 100
        fixed_total_pct += bank_pct

    bank_pnls = [pnl_on_bank(p, DEFAULT_BANK_ALLOCATION_PCT) for p in pnls]

    final_fixed = initial_capital * (1 + fixed_total_pct / 100)
    profit_compound = compound - initial_capital
    profit_fixed = final_fixed - initial_capital

    return ProfitSimulation(
        initial_capital=initial_capital,
        final_compound=round(compound, 2),
        final_fixed=round(final_fixed, 2),
        profit_compound=round(profit_compound, 2),
        profit_fixed=round(profit_fixed, 2),
        profit_pct_compound=round(profit_compound / initial_capital * 100, 2),
        profit_pct_fixed=round(profit_fixed / initial_capital * 100, 2),
        trades=len(trades),
        wins=wins,
        losses=losses,
        best_trade_pct=round(max(bank_pnls), 2),
        worst_trade_pct=round(min(bank_pnls), 2),
        avg_trade_pct=round(sum(bank_pnls) / len(bank_pnls), 2),
        period_days=period_days,
        total_in_period=total_in_period or len(trades),
    )
