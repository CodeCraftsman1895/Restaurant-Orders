import uuid
from sqlalchemy import String, DateTime, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("role IN ('manager', 'waiter')", name="check_user_role"),
    )

    # Relationships
    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="primary_waiter",
        foreign_keys="Order.primary_waiter_id"
    )
    collaborations: Mapped[list["OrderCollaborator"]] = relationship(
        "OrderCollaborator",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    events: Mapped[list["OrderEvent"]] = relationship(
        "OrderEvent",
        back_populates="user"
    )
    acknowledgments: Mapped[list["AlertAcknowledgment"]] = relationship(
        "AlertAcknowledgment",
        back_populates="user"
    )
