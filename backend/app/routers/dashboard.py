import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard_service import DashboardService
from app.core.dependencies import require_manager

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])


@router.get("", response_model=DashboardSummaryResponse)
def get_dashboard_metrics(
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Goal 8: Manager's dashboard view:
    - Open orders
    - Today's revenue
    - Order counts by status
    - Order counts and revenue by waiter
    - 14-day served orders chart data
    """
    return DashboardService.get_manager_dashboard(db=db)


@router.get("/export")
def export_orders_csv(
    table_number: Optional[int] = Query(None, description="Filter by table number"),
    status: Optional[str] = Query(None, description="Filter by status"),
    waiter_id: Optional[uuid.UUID] = Query(None, description="Filter by primary waiter"),
    date_from: Optional[datetime] = Query(None, description="Filter orders from date"),
    date_to: Optional[datetime] = Query(None, description="Filter orders to date"),
    include_archived: bool = Query(False, description="Include archived orders in export"),
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Goals 1 & 8: Export orders to CSV matching the current filtered slice.
    Manager only.
    """
    csv_content = DashboardService.generate_orders_csv(
        db=db,
        table_number=table_number,
        status=status,
        waiter_id=waiter_id,
        date_from=date_from,
        date_to=date_to,
        include_archived=include_archived,
    )

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"restaurant_orders_{timestamp_str}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8",
        }
    )
