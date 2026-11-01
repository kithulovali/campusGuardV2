from datetime import datetime
from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    reg_number: Mapped[str | None] = mapped_column(String(60), unique=True, index=True)
    role: Mapped[str] = mapped_column(Enum("admin", "guard", "student", "staff", "lecturer", name="user_role"), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    qr_code: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    qr_expires: Mapped[datetime | None] = mapped_column(DateTime)
    photo: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(Enum("active", "inactive", "blacklisted", name="user_status"), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    entries: Mapped[list["Entry"]] = relationship(back_populates="user", foreign_keys="Entry.user_id")
