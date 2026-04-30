from datetime import datetime
from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class EVVehicleRaw(Base):
    __tablename__ = "ev_vehicle_raw"
    __table_args__ = (
        UniqueConstraint("source_name", "source_vehicle_id", "market", name="uq_ev_vehicle_source_market"),
        Index("ix_ev_vehicle_raw_vehicle_slug", "vehicle_slug"),
        Index("ix_ev_vehicle_raw_vehicle_name", "vehicle_name"),
        Index("ix_ev_vehicle_raw_market", "market"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, default="open-ev-data-json")
    source_vehicle_id: Mapped[str] = mapped_column(String(255), nullable=False)
    vehicle_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vehicle_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    market: Mapped[str] = mapped_column(String(50), nullable=False, default="global")
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
