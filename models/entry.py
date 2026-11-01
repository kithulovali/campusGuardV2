from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.session import Base

class Entry(Base):
    __tablename__ = "entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    gate_id: Mapped[int | None] = mapped_column(ForeignKey("gates.id", ondelete="SET NULL"))
    direction: Mapped[str] = mapped_column(Enum("in", "out", name="entry_direction"))
    mode: Mapped[str] = mapped_column(Enum("guarded", "auto", name="entry_mode"), default="guarded")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    scanned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    user: Mapped["User"] = relationship(back_populates="entries", foreign_keys=[user_id])
