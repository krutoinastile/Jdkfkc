from datetime import UTC, datetime

from app.database.models import Account


def subscription_status_text(account: Account) -> str:
    if account.is_blocked:
        return "⛔ Доступ заблокирован администратором."

    if account.subscription_until is None:
        return "Подписка не активирована. Доступен пробный период после подключения бизнес-аккаунта."

    now = datetime.now(tz=UTC)
    if account.subscription_until <= now:
        return "⏳ Подписка истекла. Продлите доступ, чтобы продолжить мониторинг."

    expires = account.subscription_until.astimezone(UTC).strftime("%d.%m.%Y %H:%M UTC")
    return f"✅ Подписка активна до <b>{expires}</b>."


def welcome_text() -> str:
    return (
        "<b>Монитор бизнес-переписок</b>\n\n"
        "Сервис сохраняет входящие сообщения из Telegram Business, "
        "уведомляет об удалениях и правках, а также хранит историю диалогов.\n\n"
        "Подключите бота через <b>Настройки → Telegram Business → Чат-боты</b> "
        "и выдайте права на чтение сообщений."
    )


def connection_help_text() -> str:
    return (
        "<b>Как подключить бота</b>\n\n"
        "1. Откройте <b>Настройки → Telegram Business → Чат-боты</b>.\n"
        "2. Добавьте этого бота в список.\n"
        "3. Включите доступ к сообщениям.\n"
        "4. Дождитесь подтверждения подключения в этом чате.\n\n"
        "После подключения все новые входящие сообщения будут сохраняться автоматически."
    )


def settings_text(account: Account) -> str:
    return (
        "<b>Настройки уведомлений</b>\n\n"
        f"Новые сообщения: {'включены' if account.notify_new else 'выключены'}\n"
        f"Изменения: {'включены' if account.notify_edit else 'выключены'}\n"
        f"Удаления: {'включены' if account.notify_delete else 'выключены'}"
    )
