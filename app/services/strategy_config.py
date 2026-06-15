from dataclasses import dataclass


@dataclass
class StrategyConfig:
    timeframe: str = "1h"
    higher_tf: str = "4h"
    ema_fast: int = 9
    ema_slow: int = 21
    ema_trend: int = 55
    rsi_period: int = 14
    rsi_long_min: float = 40.0
    rsi_long_max: float = 65.0
    rsi_short_min: float = 35.0
    rsi_short_max: float = 60.0
    atr_sl_mult: float = 1.5
    atr_tp_mult: float = 3.0
    use_macd_filter: bool = True
    use_volume_filter: bool = False
    use_higher_tf: bool = True
    scanning_enabled: bool = True
    min_signal_strength: int = 50
    min_hours_between_signals: float = 20.0
    max_signals_per_day: int = 1

    @classmethod
    def from_db(cls, row) -> "StrategyConfig":
        return cls(
            timeframe=row.timeframe,
            higher_tf=row.higher_tf,
            ema_fast=row.ema_fast,
            ema_slow=row.ema_slow,
            ema_trend=row.ema_trend,
            rsi_period=row.rsi_period,
            rsi_long_min=row.rsi_long_min,
            rsi_long_max=row.rsi_long_max,
            rsi_short_min=row.rsi_short_min,
            rsi_short_max=row.rsi_short_max,
            atr_sl_mult=row.atr_sl_mult,
            atr_tp_mult=row.atr_tp_mult,
            use_macd_filter=row.use_macd_filter,
            use_volume_filter=row.use_volume_filter,
            use_higher_tf=row.use_higher_tf,
            scanning_enabled=row.scanning_enabled,
            min_signal_strength=row.min_signal_strength,
            min_hours_between_signals=getattr(row, "min_hours_between_signals", 20.0),
            max_signals_per_day=getattr(row, "max_signals_per_day", 1),
        )
