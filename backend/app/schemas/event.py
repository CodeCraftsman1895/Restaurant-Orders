import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserBrief


class OrderEventResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    user: UserBrief
    event_type: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    order_line_id: Optional[uuid.UUID] = None
    details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
