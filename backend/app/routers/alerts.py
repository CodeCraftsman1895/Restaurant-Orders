import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.schemas.alert import (
    SlowOrderAlertResponse,
    AlertBadgeResponse,
    AcknowledgeAlertResponse,
)
from app.services.alert_service import AlertService
from app.services.order_service import OrderService
from app.core.dependencies import get_current_user
from app.core.permissions import PermissionChecker

router = APIRouter(prefix="/alerts", tags=["Slow-Order Alerts"])


@router.get("/badge", response_model=AlertBadgeResponse)
def get_alert_badge(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 10: Dynamic slow-order count for navigation badge.
    Calculated in real-time based on open orders, threshold, and suppression intervals.
    """
    return AlertService.get_badge(db=db, user=current_user)


@router.get("", response_model=List[SlowOrderAlertResponse])
def list_slow_order_alerts(
    threshold_minutes: Optional[int] = Query(None, description="Override default threshold minutes for testing"),
    reappear_minutes: Optional[int] = Query(None, description="Override default reappear minutes for testing"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 10: Active slow orders list showing table, open duration, and assigned staff.
    Excludes suppressed acknowledgments until reappear window passes.
    """
    return AlertService.get_slow_orders(
        db=db,
        user=current_user,
        threshold_minutes=threshold_minutes,
        reappear_minutes=reappear_minutes
    )


@router.post("/{order_id}/acknowledge", response_model=AcknowledgeAlertResponse)
def acknowledge_slow_order_alert(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 10: Acknowledge/dismiss a slow order alert.
    Suppresses the alert for ALERT_REAPPEAR_MINUTES.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Enforce role/ownership permissions
    collab_ids = [c.user_id for c in order.collaborators]
    if not PermissionChecker.can_access_order(current_user, order.primary_waiter_id, collab_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to acknowledge alerts for this order"
        )

    return AlertService.acknowledge_alert(db=db, user=current_user, order=order)
