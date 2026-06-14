from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class UserStatus(StrEnum):
    NEW = "new"
    REGISTERED = "registered"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESUBMIT = "resubmit"
    BLOCKED = "blocked"


class ApplicationDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESUBMIT = "resubmit"
    BLOCKED = "blocked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    bingx_uid: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default=UserStatus.NEW.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Application.created_at.desc()",
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    deposit_photo: Mapped[str] = mapped_column(String(255), nullable=False)
    register_photo: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(
        String(32),
        default=ApplicationDecision.PENDING.value,
        index=True,
        nullable=False,
    )
    moderator: Mapped[int | None] = mapped_column(BigInteger)
    decision_reason: Mapped[str | None] = mapped_column(String(512))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
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

    user: Mapped[User] = relationship(back_populates="applications")


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
