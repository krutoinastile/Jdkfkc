# BingX Telegram Access Bot

Production-ready Telegram-бот на Python 3.12 и aiogram v3 для ручной проверки
рефералов BingX и выдачи доступа в закрытый канал.

## Возможности

- `/start` с приветствием и inline-меню.
- Реферальная ссылка BingX: `https://bingxdao.com/invite/X4EYPO/`.
- FSM-сценарий заявки:
  - BingX UID;
  - скрин регистрации;
  - скрин пополнения.
- Запрет активных повторных заявок.
- Админ-панель `/admin`:
  - список заявок;
  - просмотр UID, username, даты и фото;
  - решения: одобрить, отклонить, запросить повторно, заблокировать.
- Одноразовая invite-ссылка в канал на 24 часа с лимитом 1 вход.
- SQLite через SQLAlchemy AsyncIO, с возможностью заменить URL на PostgreSQL.
- `.env`, logging, rate limit, Docker, docker-compose, systemd, GitHub Actions.

## Структура проекта

```text
app/
  database/      SQLAlchemy models, session, repositories
  filters/       admin access filter
  handlers/      user and admin aiogram routers
  keyboards/     inline keyboards
  middlewares/   DB session and throttling
  services/      invite links, notifications, scheduler
  states/        FSM states
  utils/         text formatting helpers
  main.py        application entrypoint
systemd/
  bingxbot.service
.github/workflows/
  deploy.yml
```

## Подготовка Telegram

1. Создайте бота через [@BotFather](https://t.me/BotFather) и получите токен.
2. Добавьте бота администратором в канал `@anomalniypnl`.
3. Выдайте боту право создавать пригласительные ссылки.
4. Узнайте Telegram ID администраторов и добавьте их в `ADMIN_IDS`.

## Локальный запуск

```bash
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=123456789:replace-with-telegram-bot-token
ADMIN_IDS=123456789,987654321
CHANNEL_ID=@anomalniypnl
DATABASE_URL=sqlite+aiosqlite:///./data/bingxbot.db
BINGX_REF_LINK=https://bingxdao.com/invite/X4EYPO/
SUPPORT_URL=https://t.me/your_support_username
RATE_LIMIT_SECONDS=1.0
LOG_LEVEL=INFO
```

Запуск без Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Docker

```bash
docker compose up -d
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

SQLite-файл хранится в `./data`.

## systemd

Скопируйте проект на сервер, например в `/opt/bingxbot`, заполните `.env`, затем:

```bash
sudo cp systemd/bingxbot.service /etc/systemd/system/bingxbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now bingxbot
sudo systemctl status bingxbot
```

Логи:

```bash
journalctl -u bingxbot -f
```

## GitHub Actions deploy

Workflow `.github/workflows/deploy.yml` деплоит проект по SSH и запускает:

```bash
docker compose up -d --build --remove-orphans
```

Добавьте в GitHub Secrets:

- `DEPLOY_HOST` - IP или домен сервера;
- `DEPLOY_USER` - SSH-пользователь;
- `DEPLOY_SSH_KEY` - приватный SSH-ключ для деплоя;
- `DEPLOY_PORT` - SSH-порт, если отличается от `22`;
- `DEPLOY_PATH` - путь к проекту на сервере, например `/opt/bingxbot`.

На сервере в `DEPLOY_PATH` должен находиться git checkout этого репозитория и файл `.env`.

## Безопасность

- Не храните `BOT_TOKEN` в Git.
- После ручной передачи паролей меняйте их и используйте SSH-ключи.
- Для деплоя создайте отдельного пользователя с минимальными правами.
- Бот проверяет обязательность UID и изображений.
- In-memory rate limit защищает от частого спама командами и callback-кнопками.

## Замена SQLite на PostgreSQL

Код использует SQLAlchemy AsyncIO. Для PostgreSQL достаточно добавить драйвер
`asyncpg` в зависимости и заменить `DATABASE_URL`, например:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/bingxbot
```
