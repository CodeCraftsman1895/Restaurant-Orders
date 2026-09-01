import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy import Integer, Numeric, Boolean, Text, DateTime, ForeignKey, CheckConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class OrderLine(Base):
    __tablename__ = "order_lines"

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
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_voided: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_order_line_quantity_positive"),
        CheckConstraint("unit_price > 0", name="check_order_line_unit_price_positive"),
        CheckConstraint(
            "is_voided = FALSE OR (void_reason IS NOT NULL AND length(trim(void_reason)) > 0)",
            name="check_order_line_void_reason"
        ),
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="lines"
    )
    menu_item: Mapped["MenuItem"] = relationship(
        "MenuItem",
        back_populates="order_lines"
    )
    events: Mapped[list["OrderEvent"]] = relationship(
        "OrderEvent",
        back_populates="order_line"
    )
