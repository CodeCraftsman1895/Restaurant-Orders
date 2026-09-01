import uuid
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, CheckConstraint, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    table_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="placed",
        server_default=text("'placed'"),
        index=True
    )
    primary_waiter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("table_number > 0", name="check_order_table_number_positive"),
        CheckConstraint(
            "status IN ('placed', 'accepted', 'preparing', 'ready', 'served', 'cancelled')",
            name="check_order_status_valid"
        ),
        Index("ix_orders_status_created", "status", "created_at"),
    )

    # Relationships
    primary_waiter: Mapped["User"] = relationship(
        "User",
        back_populates="orders",
        foreign_keys=[primary_waiter_id]
    )
    lines: Mapped[list["OrderLine"]] = relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan"
    )
    collaborators: Mapped[list["OrderCollaborator"]] = relationship(
        "OrderCollaborator",
        back_populates="order",
        cascade="all, delete-orphan"
    )
    events: Mapped[list["OrderEvent"]] = relationship(
        "OrderEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderEvent.created_at"
    )
    acknowledgments: Mapped[list["AlertAcknowledgment"]] = relationship(
        "AlertAcknowledgment",
        back_populates="order",
        cascade="all, delete-orphan"
    )
