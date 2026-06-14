# Business Chat Monitor

Telegram-бот на Python 3.12 и aiogram v3 для мониторинга переписок через
**Telegram Business Automation**. Сохраняет входящие сообщения, фиксирует
удаления и правки, ведёт историю диалогов и отправляет уведомления владельцу.

## Возможности

- Подключение через **Telegram Business → Чат-боты**.
- Сохранение всех входящих business-сообщений (текст и медиа).
- Уведомления об удалённых сообщениях с сохранённой копией.
- Уведомления об изменённых сообщениях (было / стало).
- История диалогов с постраничным просмотром.
- Настройка уведомлений: новые / правки / удаления.
- Пробный период и подписка (продление через админ-панель).
- Админ-панель: пользователи, статистика, продление и блокировка.
- Docker, docker-compose, systemd, GitHub Actions.

## Требования

- Telegram Premium и бизнес-аккаунт у владельца.
- Бот с токеном от [@BotFather](https://t.me/BotFather).
- VPS с Docker (рекомендуется Ubuntu 22.04+).

## Быстрый старт

```bash
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=123456789:your-token
ADMIN_IDS=123456789
DATABASE_URL=sqlite+aiosqlite:///./data/biztrace.db
SUPPORT_URL=https://t.me/your_support
TRIAL_DAYS=3
```

Локальный запуск:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Docker:

```bash
docker compose up -d --build
docker compose logs -f
```

## Подключение бизнес-аккаунта

1. Откройте бота и нажмите **Подключение**.
2. В Telegram: **Настройки → Telegram Business → Чат-боты**.
3. Добавьте бота и выдайте права на чтение сообщений.
4. После подключения бот начнёт сохранять переписки с клиентами.

## Деплой на VPS

```bash
chmod +x scripts/deploy_vps.sh
DEPLOY_PATH=/opt/biztrace ./scripts/deploy_vps.sh
```

Или вручную:

```bash
git clone https://github.com/krutoinastile/jdkfkc.git /opt/biztrace
cd /opt/biztrace
git checkout cursor/business-chat-monitor-bde0
cp .env.example .env
# отредактируйте .env
docker compose up -d --build
```

## GitHub Actions

Secrets:

- `DEPLOY_HOST` — IP сервера
- `DEPLOY_USER` — SSH-пользователь (`root`)
- `DEPLOY_PASSWORD` или `DEPLOY_SSH_KEY` — доступ
- `DEPLOY_PATH` — `/opt/biztrace`
- `DEPLOY_PORT` — SSH-порт (по умолчанию 22)

## Админ-команды

- `/admin` — панель управления
- **Оплата** — настройка provider token, цены, валюты (Stars/RUB), срока подписки
- Продление подписки вручную: +7 / +30 дней
- Блокировка / разблокировка пользователей

## Оплата подписки

Поддерживаются **Telegram Stars** (`XTR`) и **рубли** (`RUB` через provider token).

Пользователь: **Подписка → Оплатить**.

Админ: **Админ-панель → Оплата**:
- включить/выключить оплату
- изменить **provider token** (для RUB; для Stars отправьте `-`)
- изменить **цену** (Stars или рубли)
- изменить **количество дней** за оплату
- переключить валюту Stars ↔ RUB

## Структура

```text
app/
  handlers/     user, business, admin
  database/     models, repositories
  services/     notifications
  keyboards/    inline menus
  utils/        formatting helpers
scripts/
  deploy_vps.sh
systemd/
  biztrace.service
```

## Безопасность

- Не храните `BOT_TOKEN` в Git.
- Используйте SSH-ключи вместо пароля на проде.
- Бот обрабатывает только business-сообщения подключённых аккаунтов.
