import uuid
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    order_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_lines.id", ondelete="SET NULL"),
        nullable=True
    )
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('status_change', 'line_added', 'line_voided', 'note_added')",
            name="check_order_event_type_valid"
        ),
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="events"
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="events"
    )
    order_line: Mapped[Optional["OrderLine"]] = relationship(
        "OrderLine",
        back_populates="events"
    )
