import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, or_, and_, desc
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.order import Order
from app.models.collaborator import OrderCollaborator
from app.models.alert_acknowledgment import AlertAcknowledgment
from app.models.user import User
from app.schemas.alert import (
    SlowOrderAlertResponse,
    AcknowledgeAlertResponse,
    AlertBadgeResponse,
)
from app.schemas.user import UserBrief
from app.services.event_service import EventService
from app.core.permissions import PermissionChecker

OPEN_STATUSES = ("placed", "accepted", "preparing", "ready")


class AlertService:
    @classmethod
    def get_slow_orders(
        cls,
        db: Session,
        user: User,
        threshold_minutes: Optional[int] = None,
        reappear_minutes: Optional[int] = None
    ) -> List[SlowOrderAlertResponse]:
        """
        Goal 10: Dynamic slow-order detection and alert suppression/reappearance evaluation.
        Identifies open non-archived orders exceeding the threshold, filters by role visibility,
        and respects acknowledgment suppression windows.
        """
        threshold = threshold_minutes if threshold_minutes is not None else settings.ALERT_THRESHOLD_MINUTES
        reappear = reappear_minutes if reappear_minutes is not None else settings.ALERT_REAPPEAR_MINUTES

        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(minutes=threshold)

        # 1. Base Query: Open, unarchived orders created at or before cutoff_time
        query = (
            select(Order)
            .options(
                selectinload(Order.primary_waiter),
                selectinload(Order.collaborators).selectinload(OrderCollaborator.user),
                selectinload(Order.acknowledgments).selectinload(AlertAcknowledgment.user),
            )
            .where(
                Order.status.in_(OPEN_STATUSES),
                Order.is_archived.is_(False),
                Order.created_at <= cutoff_time,
            )
        )

        # 2. Role-Based Visibility
        if user.role == "waiter":
            subquery_collab = select(OrderCollaborator.order_id).where(OrderCollaborator.user_id == user.id)
            query = query.where(
                or_(
                    Order.primary_waiter_id == user.id,
                    Order.id.in_(subquery_collab),
                )
            )

        # Sort oldest first (most urgent slow orders at the top)
        query = query.order_by(Order.created_at.asc())
        candidate_orders = list(db.scalars(query).all())

        active_alerts: List[SlowOrderAlertResponse] = []

        # 3. Evaluate Acknowledgment Suppression / Reappearance
        for order in candidate_orders:
            # Find most recent acknowledgment
            latest_ack: Optional[AlertAcknowledgment] = None
            if order.acknowledgments:
                latest_ack = max(order.acknowledgments, key=lambda a: a.acknowledged_at)

            is_suppressed = False
            is_reappeared = False
            last_ack_at = None
            last_ack_by = None

            if latest_ack:
                # Ensure latest_ack.acknowledged_at is timezone-aware
                ack_time = latest_ack.acknowledged_at
                if ack_time.tzinfo is None:
                    ack_time = ack_time.replace(tzinfo=timezone.utc)

                time_since_ack = now - ack_time
                if time_since_ack < timedelta(minutes=reappear):
                    # Within suppression window -> Suppress alert
                    is_suppressed = True
                else:
                    # Reappearance window expired -> Re-alert!
                    is_reappeared = True
                    last_ack_at = latest_ack.acknowledged_at
                    if latest_ack.user:
                        last_ack_by = UserBrief(
                            id=latest_ack.user.id,
                            name=latest_ack.user.name,
                            email=latest_ack.user.email,
                            role=latest_ack.user.role,
                        )

            if not is_suppressed:
                order_created = order.created_at
                if order_created.tzinfo is None:
                    order_created = order_created.replace(tzinfo=timezone.utc)

                minutes_open = max(1, int((now - order_created).total_seconds() // 60))

                collabs = [
                    UserBrief(
                        id=c.user.id,
                        name=c.user.name,
                        email=c.user.email,
                        role=c.user.role,
                    )
                    for c in order.collaborators if c.user
                ]

                active_alerts.append(
                    SlowOrderAlertResponse(
                        order_id=order.id,
                        table_number=order.table_number,
                        status=order.status,
                        primary_waiter=UserBrief(
                            id=order.primary_waiter.id,
                            name=order.primary_waiter.name,
                            email=order.primary_waiter.email,
                            role=order.primary_waiter.role,
                        ),
                        collaborators=collabs,
                        minutes_open=minutes_open,
                        created_at=order.created_at,
                        is_reappeared=is_reappeared,
                        last_acknowledged_at=last_ack_at,
                        last_acknowledged_by=last_ack_by,
                    )
                )

        return active_alerts

    @classmethod
    def get_badge(cls, db: Session, user: User) -> AlertBadgeResponse:
        """
        Goal 10: Dynamic count of active unsuppressed slow orders for the navigation badge.
        """
        alerts = cls.get_slow_orders(db, user)
        return AlertBadgeResponse(slow_orders_count=len(alerts))

    @classmethod
    def acknowledge_alert(
        cls,
        db: Session,
        user: User,
        order: Order
    ) -> AcknowledgeAlertResponse:
        """
        Goal 10: Dismiss/acknowledge a slow order alert.
        Persists acknowledgment and suppresses alert for ALERT_REAPPEAR_MINUTES.
        """
        if order.status not in OPEN_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot acknowledge alert on a {order.status} order. Order is closed."
            )

        now = datetime.now(timezone.utc)
        ack = AlertAcknowledgment(
            order_id=order.id,
            acknowledged_by=user.id,
            acknowledged_at=now,
        )
        db.add(ack)

        # Log timeline event
        EventService.log_event(
            db=db,
            order_id=order.id,
            user_id=user.id,
            event_type="note_added",
            details=f"Slow-order alert acknowledged by {user.name}",
        )

        db.commit()
        db.refresh(ack)

        return AcknowledgeAlertResponse(
            order_id=order.id,
            acknowledged_at=ack.acknowledged_at,
            acknowledged_by=UserBrief(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role,
            ),
            message="Alert acknowledged and suppressed",
        )
