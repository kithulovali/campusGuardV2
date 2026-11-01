from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from db.session import Base

class Gate(Base):
    __tablename__ = "gates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(Enum("guarded", "auto", name="gate_mode"), default="guarded")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
