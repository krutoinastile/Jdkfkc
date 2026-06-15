# BTC Trading Bot

Telegram-бот для торговли Bitcoin: сигналы LONG/SHORT, статистика, бэктест, подписка.

## Стратегия: BB Squeeze Breakout

| Параметр | Значение |
|----------|----------|
| Логика | Сжатие Bollinger Bands → пробой в сторону тренда EMA55 |
| Фильтр | ADX ≥ 16 (сила тренда) |
| Stop-Loss | 1.5 × ATR(14) |
| Take-Profit | 4.0 × ATR(14) |
| Таймфрейм | **1h** (оптимизировано под него) |
| Плечо | 20x · 10% банка на сделку в бэктесте |

### Управление сделкой
- **+1R** — SL в безубыток
- **+2R** — фиксация +0.5R
- **+3R** — trailing stop на 1 ATR от цены
- Истечение 72ч — закрытие по рыночной цене (не 0%)

Скан рынка каждые 15 мин, проверка TP/SL каждые 5 мин.

## Возможности

- Сигналы с Entry / SL / TP + график
- Live P&L открытой сделки на дашборде
- Fear & Greed, Funding, Open Interest
- Ликвидации Binance Futures
- Калькулятор прибыли · Бэктест 30 дней
- Подписка Crypto Pay · рефералы · розыгрыши

## Быстрый старт

```bash
cp .env.example .env
# BOT_TOKEN, ADMIN_IDS

pip install -r requirements.txt
python -m app.main
```

Docker: `docker compose up -d --build`

## Команды

- `/start` — меню
- `/signal` — активный сигнал (с подпиской)
- `/stats` — статистика
- `/calc` — калькулятор

## ⚠️ Дисклеймер

Не финансовый совет. Торгуйте на свой риск.
