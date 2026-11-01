from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    reg_number: Mapped[str | None] = mapped_column(String(60), unique=True, index=True)
    role: Mapped[str] = mapped_column(Enum("admin","guard","student","staff","lecturer", name="user_role"), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    qr_code: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    qr_expires: Mapped[datetime | None] = mapped_column(DateTime)
    photo: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(Enum("active","inactive","blacklisted", name="user_status"), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    entries: Mapped[list["Entry"]] = relationship(back_populates="user", foreign_keys="Entry.user_id")


class Gate(Base):
    __tablename__ = "gates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(Enum("guarded","auto", name="gate_mode"), default="guarded")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Entry(Base):
    __tablename__ = "entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    gate_id: Mapped[int | None] = mapped_column(ForeignKey("gates.id", ondelete="SET NULL"))
    direction: Mapped[str] = mapped_column(Enum("in","out", name="entry_direction"))
    mode: Mapped[str] = mapped_column(Enum("guarded","auto", name="entry_mode"), default="guarded")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    scanned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    user: Mapped["User"] = relationship(back_populates="entries", foreign_keys=[user_id])


class Visitor(Base):
    __tablename__ = "visitors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    id_number: Mapped[str | None] = mapped_column(String(60))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(String(200))
    host: Mapped[str | None] = mapped_column(String(120))
    host_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    temp_pass: Mapped[str | None] = mapped_column(String(120), unique=True)
    pre_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    prereg_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    time_in: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expected_exit: Mapped[datetime | None] = mapped_column(DateTime)
    checked_out: Mapped[bool] = mapped_column(Boolean, default=False)
    checkout_time: Mapped[datetime | None] = mapped_column(DateTime)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    gate_id: Mapped[int | None] = mapped_column(ForeignKey("gates.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(Enum("invalid_qr","blacklisted","overstay","repeated_fail","lockdown","qr_expired","qr_compromised","manual", name="alert_type"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_name: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class SystemState(Base):
    __tablename__ = "system_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
