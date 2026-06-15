"""Profit simulation from closed bot signals."""

from __future__ import annotations

from dataclasses import dataclass

from app.database.models import Signal, TradeStatus


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


def _closed_trades(signals: list[Signal]) -> list[Signal]:
    closed = [
        s for s in signals
        if s.status in (TradeStatus.WIN.value, TradeStatus.LOSS.value)
        and s.pnl_percent is not None
    ]
    return sorted(closed, key=lambda s: s.opened_at)


def simulate_profit(signals: list[Signal], initial_capital: float) -> ProfitSimulation | None:
    trades = _closed_trades(signals)
    if not trades:
        return None

    compound = initial_capital
    fixed_total_pct = 0.0
    pnls = [t.pnl_percent for t in trades if t.pnl_percent is not None]
    wins = sum(1 for t in trades if t.status == TradeStatus.WIN.value)
    losses = len(trades) - wins

    for trade in trades:
        pct = trade.pnl_percent or 0.0
        compound *= 1 + pct / 100
        fixed_total_pct += pct

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
        best_trade_pct=round(max(pnls), 2),
        worst_trade_pct=round(min(pnls), 2),
        avg_trade_pct=round(sum(pnls) / len(pnls), 2),
    )
