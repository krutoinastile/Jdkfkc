from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import Settings
from app.database.models import Account


def main_menu_keyboard(settings: Settings, *, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📂 Мои диалоги", callback_data="menu:dialogs:0")],
        [InlineKeyboardButton(text="🔗 Подключение", callback_data="menu:connect")],
        [InlineKeyboardButton(text="💳 Подписка", callback_data="menu:subscription")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="menu:settings")],
    ]
    if settings.support_url:
        rows.append([InlineKeyboardButton(text="🆘 Поддержка", url=settings.support_url)])
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(account: Account) -> InlineKeyboardMarkup:
    def label(name: str, enabled: bool) -> str:
        return f"{name}: {'✅' if enabled else '❌'}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label("Новые", account.notify_new), callback_data="settings:toggle:notify_new")],
            [InlineKeyboardButton(text=label("Изменения", account.notify_edit), callback_data="settings:toggle:notify_edit")],
            [InlineKeyboardButton(text=label("Удаления", account.notify_delete), callback_data="settings:toggle:notify_delete")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:home")],
        ]
    )


def dialogs_keyboard(dialogs: list, page: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for dialog in dialogs:
        title = dialog.title or dialog.username or f"Чат {dialog.chat_id}"
        if len(title) > 40:
            title = title[:37] + "..."
        rows.append(
            [InlineKeyboardButton(text=f"💬 {title}", callback_data=f"history:dialog:{dialog.id}:0")]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"menu:dialogs:{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"menu:dialogs:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_keyboard(dialog_id: int, page: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"history:dialog:{dialog_id}:{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"history:dialog:{dialog_id}:{page + 1}"))
    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ К диалогам", callback_data="menu:dialogs:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")]]
    if settings.support_url:
        rows.insert(0, [InlineKeyboardButton(text="💬 Продлить через поддержку", url=settings.support_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
