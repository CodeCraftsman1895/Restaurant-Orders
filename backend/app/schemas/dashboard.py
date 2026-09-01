import uuid
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict


class StatusBreakdownItem(BaseModel):
    status: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class WaiterBreakdownItem(BaseModel):
    waiter_id: uuid.UUID
    waiter_name: str
    order_count: int
    revenue: Decimal

    model_config = ConfigDict(from_attributes=True)


class ChartDayData(BaseModel):
    date: str
    served_orders_count: int
    revenue: Decimal

    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryResponse(BaseModel):
    """
    Goal 8: Manager's home view summary stats for today and 14-day served orders chart.
    """
    open_orders_count: int
    today_revenue: Decimal
    today_orders_count: int
    today_served_count: int
    status_breakdown: List[StatusBreakdownItem]
    waiter_breakdown: List[WaiterBreakdownItem]
    last_14_days_chart: List[ChartDayData]

    model_config = ConfigDict(from_attributes=True)
