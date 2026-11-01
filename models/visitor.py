from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base

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
