from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def subscription_keyboard(*, has_active: bool, has_giveaway: bool, entered_giveaway: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not has_active:
        rows.append([InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="sub:pay")])
    else:
        rows.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="sub:pay")])
    if has_giveaway:
        label = "✅ Вы в розыгрыше" if entered_giveaway else "🎁 Участвовать в розыгрыше"
        if not entered_giveaway:
            rows.append([InlineKeyboardButton(text=label, callback_data="sub:giveaway:enter")])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_pay_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить в Crypto Bot", url=pay_url)],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="sub:check")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:subscription")],
        ]
    )


def billing_admin_keyboard(billing) -> InlineKeyboardMarkup:
    discount_label = f"Скидка: {'✅' if billing.discount_enabled else '❌'}"
    testnet_label = f"Testnet: {'✅' if billing.cryptopay_testnet else '❌'}"
    vip_label = f"VIP-only: {'✅' if billing.require_subscription_for_signals else '❌'}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Crypto Pay token", callback_data="admin:billing:token")],
            [
                InlineKeyboardButton(text=testnet_label, callback_data="admin:billing:toggle:testnet"),
                InlineKeyboardButton(text=vip_label, callback_data="admin:billing:toggle:vip"),
            ],
            [
                InlineKeyboardButton(text="$10", callback_data="admin:billing:price:10"),
                InlineKeyboardButton(text="$15", callback_data="admin:billing:price:15"),
                InlineKeyboardButton(text="$25", callback_data="admin:billing:price:25"),
            ],
            [InlineKeyboardButton(text="✏️ Своя цена", callback_data="admin:billing:price:custom")],
            [
                InlineKeyboardButton(text="Скидка 10%", callback_data="admin:billing:disc:10"),
                InlineKeyboardButton(text="Скидка 20%", callback_data="admin:billing:disc:20"),
                InlineKeyboardButton(text=discount_label, callback_data="admin:billing:toggle:discount"),
            ],
            [
                InlineKeyboardButton(text="Реф +3д", callback_data="admin:billing:ref:3"),
                InlineKeyboardButton(text="Реф +7д", callback_data="admin:billing:ref:7"),
                InlineKeyboardButton(text="Реф +14д", callback_data="admin:billing:ref:14"),
            ],
            [
                InlineKeyboardButton(text="🎁 Новый розыгрыш", callback_data="admin:billing:giveaway:new"),
                InlineKeyboardButton(text="🏆 Разыграть", callback_data="admin:billing:giveaway:draw"),
            ],
            [InlineKeyboardButton(text="◀️ Админ", callback_data="admin:home")],
        ]
    )
