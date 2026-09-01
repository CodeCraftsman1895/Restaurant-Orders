import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.order_event import OrderEvent
from app.models.user import User


class EventService:
    @staticmethod
    def log_event(
        db: Session,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        event_type: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        order_line_id: Optional[uuid.UUID] = None,
        details: Optional[str] = None
    ) -> OrderEvent:
        """
        Goal 9: Append-only event logging for order history.
        Records status transitions, line additions, line voidings, and notes.
        """
        event = OrderEvent(
            order_id=order_id,
            user_id=user_id,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            order_line_id=order_line_id,
            details=details
        )
        db.add(event)
        return event

    @staticmethod
    def get_order_events(db: Session, order_id: uuid.UUID) -> List[OrderEvent]:
        """
        Retrieve chronological timeline of events for an order.
        """
        stmt = (
            select(OrderEvent)
            .where(OrderEvent.order_id == order_id)
            .order_by(OrderEvent.created_at.asc())
        )
        return list(db.scalars(stmt).all())
