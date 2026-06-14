from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_new: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_edit: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_delete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    connections: Mapped[list["BusinessConnection"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


class BusinessConnection(Base):
    __tablename__ = "business_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    user_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rights_json: Mapped[str | None] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    account: Mapped[Account] = relationship(back_populates="connections")
    dialogs: Mapped[list["Dialog"]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["StoredMessage"]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
    )


class Dialog(Base):
    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("business_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_type: Mapped[str] = mapped_column(String(32), default="private", nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    connection: Mapped[BusinessConnection] = relationship(back_populates="dialogs")
    messages: Mapped[list["StoredMessage"]] = relationship(
        back_populates="dialog",
        cascade="all, delete-orphan",
    )


class StoredMessage(Base):
    __tablename__ = "stored_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("business_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dialog_id: Mapped[int] = mapped_column(
        ForeignKey("dialogs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    from_username: Mapped[str | None] = mapped_column(String(255))
    from_first_name: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(64), default="text", nullable=False)
    media_file_id: Mapped[str | None] = mapped_column(String(512))
    has_media_spoiler: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    connection: Mapped[BusinessConnection] = relationship(back_populates="messages")
    dialog: Mapped[Dialog] = relationship(back_populates="messages")
    edits: Mapped[list["MessageEdit"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageEdit.edited_at.asc()",
    )


class MessageEdit(Base):
    __tablename__ = "message_edits"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("stored_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_text: Mapped[str | None] = mapped_column(Text)
    old_caption: Mapped[str | None] = mapped_column(Text)
    new_text: Mapped[str | None] = mapped_column(Text)
    new_caption: Mapped[str | None] = mapped_column(Text)
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    message: Mapped[StoredMessage] = relationship(back_populates="edits")
