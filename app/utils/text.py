from datetime import datetime

from app.database.models import Application, User, UserStatus


STATUS_LABELS = {
    UserStatus.NEW.value: "вы еще не подавали заявку",
    UserStatus.REGISTERED.value: "регистрация отмечена, можно подать заявку",
    UserStatus.PENDING.value: "заявка на проверке",
    UserStatus.APPROVED.value: "доступ одобрен",
    UserStatus.REJECTED.value: "заявка отклонена",
    UserStatus.RESUBMIT.value: "администратор запросил повторную отправку",
    UserStatus.BLOCKED.value: "доступ заблокирован",
}


def format_username(user: User) -> str:
    return f"@{user.username}" if user.username else "не указан"


def format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def welcome_text() -> str:
    return (
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Этот бот помогает получить доступ в закрытый Telegram-канал после ручной "
        "проверки реферальной регистрации BingX.\n\n"
        "Что нужно сделать:\n"
        "1. Зарегистрируйтесь по реферальной ссылке.\n"
        "2. Пополните баланс BingX.\n"
        "3. Отправьте UID и два скриншота на проверку.\n\n"
        "После одобрения вы получите одноразовую ссылку в приватный канал."
    )


def application_text(application: Application) -> str:
    user = application.user
    return (
        f"📄 <b>Заявка #{application.id}</b>\n\n"
        f"Telegram ID: <code>{user.tg_id}</code>\n"
        f"Username: {format_username(user)}\n"
        f"BingX UID: <code>{user.bingx_uid or '-'}</code>\n"
        f"Дата: {format_datetime(application.created_at)}\n"
        f"Решение: <code>{application.decision}</code>"
    )
