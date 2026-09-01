import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.user import UserBrief


class OrderLineCreate(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(..., gt=0, description="Quantity of the item (must be > 0)")
    special_instructions: Optional[str] = Field(None, description="Optional special preparation notes")


class VoidLineRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Required explanation for voiding the line")


class OrderLineResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    menu_item_id: uuid.UUID
    menu_item_name: Optional[str] = None
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    special_instructions: Optional[str] = None
    is_voided: bool
    void_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    table_number: int = Field(..., gt=0, description="Dine-in table identifier")
    lines: Optional[List[OrderLineCreate]] = Field(default_factory=list, description="Initial dish selections")


class AddCollaboratorRequest(BaseModel):
    user_id: uuid.UUID = Field(..., description="UUID of the waiter user to add as collaborator")


class AddNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, description="Order note text")


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="Target status: accepted, preparing, ready, served, cancelled")


class OrderListItem(BaseModel):
    id: uuid.UUID
    table_number: int
    status: str
    primary_waiter: UserBrief
    line_count: int
    total: Decimal
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    orders: List[OrderListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class OrderResponse(BaseModel):
    id: uuid.UUID
    table_number: int
    status: str
    primary_waiter: UserBrief
    collaborators: List[UserBrief]
    lines: List[OrderLineResponse]
    total: Decimal
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
