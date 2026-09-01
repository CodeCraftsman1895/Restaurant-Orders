import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class MenuItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Dish name")
    price: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2, description="Price (must be positive)")
    is_available: bool = Field(default=True, description="Current availability toggle")


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    price: Optional[Decimal] = Field(None, gt=0, max_digits=10, decimal_places=2)
    is_available: Optional[bool] = None
    is_archived: Optional[bool] = None


class MenuItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    is_available: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkMenuUpdateRequest(BaseModel):
    item_ids: List[uuid.UUID] = Field(..., min_length=1, description="List of menu item UUIDs to update")
    price: Optional[Decimal] = Field(None, description="New price to apply (must be positive if specified)")
    is_available: Optional[bool] = Field(None, description="New availability state to apply")


class BulkMenuItemResult(BaseModel):
    item_id: uuid.UUID
    success: bool
    error: Optional[str] = None


class BulkMenuUpdateResponse(BaseModel):
    results: List[BulkMenuItemResult]
