"""Live trade P&L and level distance helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.database.models import Signal
from app.utils.leverage import get_leverage, pnl_on_bank, spot_to_leveraged


def initial_risk(signal: Signal) -> float:
    base = signal.initial_stop_loss if signal.initial_stop_loss is not None else signal.stop_loss
    return abs(signal.entry_price - base)


def spot_pnl_pct(signal: Signal, price: float) -> float:
    if signal.direction == "long":
        return (price - signal.entry_price) / signal.entry_price * 100
    return (signal.entry_price - price) / signal.entry_price * 100


def margin_pnl_pct(signal: Signal, price: float) -> float:
    return spot_to_leveraged(spot_pnl_pct(signal, price), get_leverage(signal))


def bank_pnl_pct(signal: Signal, price: float) -> float:
    return pnl_on_bank(margin_pnl_pct(signal, price))


def distance_pct(from_price: float, to_price: float) -> float:
    if from_price <= 0:
        return 0.0
    return abs(to_price - from_price) / from_price * 100


def format_live_trade(signal: Signal, price: float) -> str:
    from app.utils.formatting import kv, money, pnl_colored
    from app.utils.leverage import leveraged_move

    lev = get_leverage(signal)
    spot = spot_pnl_pct(signal, price)
    margin = spot_to_leveraged(spot, lev)
    bank = pnl_on_bank(margin)

    if signal.direction == "long":
        to_tp = distance_pct(price, signal.take_profit)
        to_sl = distance_pct(price, signal.stop_loss)
        tp_dir = "↑"
        sl_dir = "↓"
    else:
        to_tp = distance_pct(price, signal.take_profit)
        to_sl = distance_pct(price, signal.stop_loss)
        tp_dir = "↓"
        sl_dir = "↑"

    opened = signal.opened_at
    if opened and opened.tzinfo is None:
        opened = opened.replace(tzinfo=UTC)
    hours_open = 0.0
    if opened:
        hours_open = (datetime.now(tz=UTC) - opened).total_seconds() / 3600

    risk = initial_risk(signal)
    r_multiple = 0.0
    if risk > 0:
        move = (price - signal.entry_price) if signal.direction == "long" else (signal.entry_price - price)
        r_multiple = move / risk

    sl_note = ""
    if signal.initial_stop_loss is not None and signal.stop_loss != signal.initial_stop_loss:
        sl_note = " · 🛡 SL подтянут"

    return (
        f"{kv('💵 Цена', f'<b>{money(price)}</b>')}\n"
        f"{kv('📊 P&L', f'{pnl_colored(margin)} при {lev}x · {pnl_colored(bank)} к банку')}\n"
        f"{kv('📐 R', f'<b>{r_multiple:+.2f}R</b>')}\n"
        f"{kv('🎯 До TP', f'{tp_dir} {to_tp:.2f}%')}\n"
        f"{kv('🛑 До SL', f'{sl_dir} {to_sl:.2f}%{sl_note}')}\n"
        f"{kv('⏱ В сделке', f'<b>{hours_open:.1f}ч</b>')}"
    )
