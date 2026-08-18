from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Account,
    Admin,
    BusinessConnection,
    CryptoInvoice,
    Dialog,
    MessageEdit,
    PaymentRecord,
    PaymentSettings,
    StoredMessage,
)


async def get_account_by_tg_id(session: AsyncSession, tg_id: int) -> Account | None:
    result = await session.execute(select(Account).where(Account.tg_id == tg_id))
    return result.scalar_one_or_none()


async def get_or_create_account(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    first_name: str | None = None,
) -> Account:
    account = await get_account_by_tg_id(session, tg_id)
    if account is None:
        account = Account(tg_id=tg_id, username=username, first_name=first_name)
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return account

    changed = False
    if account.username != username:
        account.username = username
        changed = True
    if first_name and account.first_name != first_name:
        account.first_name = first_name
        changed = True
    if changed:
        await session.commit()
    return account


async def activate_trial(session: AsyncSession, account: Account, trial_days: int) -> Account:
    if account.trial_used or account.subscription_until is not None:
        return account
    account.trial_used = True
    account.subscription_until = datetime.now(tz=UTC) + timedelta(days=trial_days)
    await session.commit()
    await session.refresh(account)
    return account


def is_subscription_active(account: Account) -> bool:
    if account.is_blocked:
        return False
    if account.subscription_until is None:
        return False
    return account.subscription_until > datetime.now(tz=UTC)


async def extend_subscription(
    session: AsyncSession,
    account: Account,
    days: int,
) -> Account:
    now = datetime.now(tz=UTC)
    base = account.subscription_until if account.subscription_until and account.subscription_until > now else now
    account.subscription_until = base + timedelta(days=days)
    await session.commit()
    await session.refresh(account)
    return account


async def set_account_blocked(session: AsyncSession, account: Account, blocked: bool) -> Account:
    account.is_blocked = blocked
    await session.commit()
    await session.refresh(account)
    return account


async def toggle_notification(
    session: AsyncSession,
    account: Account,
    field: str,
) -> Account:
    current = getattr(account, field)
    setattr(account, field, not current)
    await session.commit()
    await session.refresh(account)
    return account


async def upsert_business_connection(
    session: AsyncSession,
    account: Account,
    connection_id: str,
    user_chat_id: int,
    is_enabled: bool,
    can_reply: bool,
    rights_json: str | None,
) -> BusinessConnection:
    result = await session.execute(
        select(BusinessConnection).where(BusinessConnection.connection_id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        connection = BusinessConnection(
            account_id=account.id,
            connection_id=connection_id,
            user_chat_id=user_chat_id,
            is_enabled=is_enabled,
            can_reply=can_reply,
            rights_json=rights_json,
        )
        session.add(connection)
    else:
        connection.account_id = account.id
        connection.user_chat_id = user_chat_id
        connection.is_enabled = is_enabled
        connection.can_reply = can_reply
        connection.rights_json = rights_json

    await session.commit()
    await session.refresh(connection, attribute_names=["account"])
    return connection


async def get_connection_by_external_id(
    session: AsyncSession,
    connection_id: str,
) -> BusinessConnection | None:
    result = await session.execute(
        select(BusinessConnection)
        .options(selectinload(BusinessConnection.account))
        .where(BusinessConnection.connection_id == connection_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_dialog(
    session: AsyncSession,
    connection: BusinessConnection,
    chat_id: int,
    chat_type: str,
    title: str | None,
    username: str | None,
) -> Dialog:
    result = await session.execute(
        select(Dialog)
        .where(Dialog.connection_id == connection.id)
        .where(Dialog.chat_id == chat_id)
    )
    dialog = result.scalar_one_or_none()
    if dialog is None:
        dialog = Dialog(
            connection_id=connection.id,
            chat_id=chat_id,
            chat_type=chat_type,
            title=title,
            username=username,
        )
        session.add(dialog)
    else:
        if title and dialog.title != title:
            dialog.title = title
        if username and dialog.username != username:
            dialog.username = username

    await session.commit()
    await session.refresh(dialog)
    return dialog


async def store_business_message(
    session: AsyncSession,
    connection: BusinessConnection,
    dialog: Dialog,
    *,
    message_id: int,
    chat_id: int,
    from_user_id: int | None,
    from_username: str | None,
    from_first_name: str | None,
    text: str | None,
    caption: str | None,
    content_type: str,
    media_file_id: str | None,
    has_media_spoiler: bool,
    sent_at: datetime | None,
) -> StoredMessage:
    result = await session.execute(
        select(StoredMessage)
        .where(StoredMessage.connection_id == connection.id)
        .where(StoredMessage.chat_id == chat_id)
        .where(StoredMessage.message_id == message_id)
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        stored = StoredMessage(
            connection_id=connection.id,
            dialog_id=dialog.id,
            message_id=message_id,
            chat_id=chat_id,
            from_user_id=from_user_id,
            from_username=from_username,
            from_first_name=from_first_name,
            text=text,
            caption=caption,
            content_type=content_type,
            media_file_id=media_file_id,
            has_media_spoiler=has_media_spoiler,
            sent_at=sent_at,
        )
        session.add(stored)
        dialog.message_count += 1
    else:
        stored.text = text
        stored.caption = caption
        stored.content_type = content_type
        stored.media_file_id = media_file_id
        stored.has_media_spoiler = has_media_spoiler
        stored.is_deleted = False

    dialog.last_message_at = sent_at or datetime.now(tz=UTC)
    await session.commit()
    await session.refresh(stored)
    return stored


async def get_stored_message(
    session: AsyncSession,
    connection_id: int,
    chat_id: int,
    message_id: int,
) -> StoredMessage | None:
    result = await session.execute(
        select(StoredMessage)
        .options(selectinload(StoredMessage.edits))
        .where(StoredMessage.connection_id == connection_id)
        .where(StoredMessage.chat_id == chat_id)
        .where(StoredMessage.message_id == message_id)
    )
    return result.scalar_one_or_none()


async def mark_messages_deleted(
    session: AsyncSession,
    connection_id: int,
    chat_id: int,
    message_ids: list[int],
) -> list[StoredMessage]:
    result = await session.execute(
        select(StoredMessage)
        .options(selectinload(StoredMessage.dialog))
        .where(StoredMessage.connection_id == connection_id)
        .where(StoredMessage.chat_id == chat_id)
        .where(StoredMessage.message_id.in_(message_ids))
    )
    messages = list(result.scalars().all())
    for message in messages:
        message.is_deleted = True
    await session.commit()
    for message in messages:
        await session.refresh(message)
    return messages


async def record_message_edit(
    session: AsyncSession,
    stored: StoredMessage,
    *,
    old_text: str | None,
    old_caption: str | None,
    new_text: str | None,
    new_caption: str | None,
) -> MessageEdit:
    edit = MessageEdit(
        message_id=stored.id,
        old_text=old_text,
        old_caption=old_caption,
        new_text=new_text,
        new_caption=new_caption,
    )
    stored.text = new_text
    stored.caption = new_caption
    session.add(edit)
    await session.commit()
    await session.refresh(edit)
    await session.refresh(stored)
    return edit


async def list_account_dialogs(
    session: AsyncSession,
    account_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[Dialog]:
    result = await session.execute(
        select(Dialog)
        .join(BusinessConnection)
        .where(BusinessConnection.account_id == account_id)
        .where(BusinessConnection.is_enabled.is_(True))
        .order_by(Dialog.last_message_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_account_dialogs(session: AsyncSession, account_id: int) -> int:
    result = await session.execute(
        select(func.count(Dialog.id))
        .join(BusinessConnection)
        .where(BusinessConnection.account_id == account_id)
    )
    return int(result.scalar_one())


async def list_dialog_messages(
    session: AsyncSession,
    dialog_id: int,
    limit: int = 10,
    offset: int = 0,
) -> list[StoredMessage]:
    result = await session.execute(
        select(StoredMessage)
        .where(StoredMessage.dialog_id == dialog_id)
        .order_by(StoredMessage.sent_at.desc().nullslast(), StoredMessage.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_dialog_messages(session: AsyncSession, dialog_id: int) -> int:
    result = await session.execute(
        select(func.count(StoredMessage.id)).where(StoredMessage.dialog_id == dialog_id)
    )
    return int(result.scalar_one())


async def list_accounts(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[Account]:
    result = await session.execute(
        select(Account).order_by(Account.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def count_accounts(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Account.id)))
    return int(result.scalar_one())


async def count_active_connections(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(BusinessConnection.id)).where(BusinessConnection.is_enabled.is_(True))
    )
    return int(result.scalar_one())


async def count_stored_messages(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(StoredMessage.id)))
    return int(result.scalar_one())


async def upsert_admins(session: AsyncSession, admin_ids: Iterable[int]) -> None:
    for tg_id in admin_ids:
        result = await session.execute(select(Admin).where(Admin.tg_id == tg_id))
        if result.scalar_one_or_none() is None:
            session.add(Admin(tg_id=tg_id))
    await session.commit()


async def is_admin(session: AsyncSession, tg_id: int, env_admin_ids: Iterable[int]) -> bool:
    if tg_id in set(env_admin_ids):
        return True
    result = await session.execute(select(Admin).where(Admin.tg_id == tg_id))
    return result.scalar_one_or_none() is not None


async def get_payment_settings(session: AsyncSession) -> PaymentSettings:
    result = await session.execute(select(PaymentSettings).where(PaymentSettings.id == 1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = PaymentSettings(id=1)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def update_payment_settings(session: AsyncSession, **fields: object) -> PaymentSettings:
    settings = await get_payment_settings(session)
    for key, value in fields.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return settings


async def get_payment_by_charge_id(session: AsyncSession, charge_id: str) -> PaymentRecord | None:
    result = await session.execute(
        select(PaymentRecord).where(PaymentRecord.telegram_payment_charge_id == charge_id)
    )
    return result.scalar_one_or_none()


async def create_payment_record(
    session: AsyncSession,
    *,
    account_id: int,
    telegram_payment_charge_id: str,
    payload: str,
    currency: str,
    total_amount: int,
    subscription_days: int,
) -> PaymentRecord:
    record = PaymentRecord(
        account_id=account_id,
        telegram_payment_charge_id=telegram_payment_charge_id,
        payload=payload,
        currency=currency,
        total_amount=total_amount,
        subscription_days=subscription_days,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_account_by_id(session: AsyncSession, account_id: int) -> Account | None:
    result = await session.execute(select(Account).where(Account.id == account_id))
    return result.scalar_one_or_none()


async def create_crypto_invoice_record(
    session: AsyncSession,
    *,
    account_id: int,
    crypto_invoice_id: int,
    payload: str,
    asset: str,
    amount: str,
    pay_url: str | None,
) -> CryptoInvoice:
    invoice = CryptoInvoice(
        account_id=account_id,
        crypto_invoice_id=crypto_invoice_id,
        payload=payload,
        asset=asset,
        amount=amount,
        pay_url=pay_url,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice, attribute_names=["account"])
    return invoice


async def get_crypto_invoice_by_crypto_id(
    session: AsyncSession,
    crypto_invoice_id: int,
) -> CryptoInvoice | None:
    result = await session.execute(
        select(CryptoInvoice)
        .options(selectinload(CryptoInvoice.account))
        .where(CryptoInvoice.crypto_invoice_id == crypto_invoice_id)
    )
    return result.scalar_one_or_none()


async def list_pending_crypto_invoices(
    session: AsyncSession,
    limit: int = 50,
) -> list[CryptoInvoice]:
    result = await session.execute(
        select(CryptoInvoice)
        .options(selectinload(CryptoInvoice.account))
        .where(CryptoInvoice.status == "active")
        .order_by(CryptoInvoice.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_crypto_invoice_paid(session: AsyncSession, invoice: CryptoInvoice) -> CryptoInvoice:
    invoice.status = "paid"
    await session.commit()
    await session.refresh(invoice)
    return invoice

