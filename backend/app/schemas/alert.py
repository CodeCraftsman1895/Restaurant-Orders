import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserBrief


class AlertBadgeResponse(BaseModel):
    """Badge response returning dynamic count of unsuppressed slow orders."""
    slow_orders_count: int


class SlowOrderAlertResponse(BaseModel):
    """
    Goal 10: Slow order alert item providing table, duration open, and assigned staff.
    """
    order_id: uuid.UUID
    table_number: int
    status: str
    primary_waiter: UserBrief
    collaborators: List[UserBrief]
    minutes_open: int
    created_at: datetime
    is_reappeared: bool = False
    last_acknowledged_at: Optional[datetime] = None
    last_acknowledged_by: Optional[UserBrief] = None

    model_config = ConfigDict(from_attributes=True)


class AcknowledgeAlertResponse(BaseModel):
    """Response returned upon successfully dismissing/acknowledging a slow order alert."""
    order_id: uuid.UUID
    acknowledged_at: datetime
    acknowledged_by: UserBrief
    message: str = "Alert acknowledged and suppressed"
