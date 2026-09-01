import io
import csv
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, or_, and_, desc

from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.collaborator import OrderCollaborator
from app.models.user import User
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    StatusBreakdownItem,
    WaiterBreakdownItem,
    ChartDayData,
)
from app.services.order_service import OrderService

OPEN_STATUSES = ("placed", "accepted", "preparing", "ready")
ALL_STATUSES = ("placed", "accepted", "preparing", "ready", "served", "cancelled")


class DashboardService:
    @classmethod
    def get_manager_dashboard(cls, db: Session) -> DashboardSummaryResponse:
        """
        Goal 8: Manager's home view summary stats for today:
        - Open orders count
        - Today's revenue (sum of non-voided lines on served orders today)
        - Breakdown by status
        - Breakdown by waiter
        - 14-day served orders chart data
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Open Orders Count
        open_orders_stmt = select(func.count(Order.id)).where(
            Order.status.in_(OPEN_STATUSES),
            Order.is_archived.is_(False),
        )
        open_orders_count = db.scalar(open_orders_stmt) or 0

        # 2. Today's Orders Count & Served Count
        today_orders_stmt = select(func.count(Order.id)).where(
            Order.created_at >= today_start,
            Order.is_archived.is_(False),
        )
        today_orders_count = db.scalar(today_orders_stmt) or 0

        today_served_stmt = select(func.count(Order.id)).where(
            Order.status == "served",
            Order.updated_at >= today_start,
            Order.is_archived.is_(False),
        )
        today_served_count = db.scalar(today_served_stmt) or 0

        # 3. Today's Revenue (served orders updated today, non-voided lines)
        today_served_orders_stmt = (
            select(Order)
            .options(
                selectinload(Order.lines),
            )
            .where(
                Order.status == "served",
                Order.updated_at >= today_start,
                Order.is_archived.is_(False),
            )
        )
        today_served_orders = list(db.scalars(today_served_orders_stmt).all())
        today_revenue = sum(
            (OrderService.calculate_order_total(o) for o in today_served_orders),
            Decimal("0.00")
        )

        # 4. Status Breakdown
        status_counts_stmt = (
            select(Order.status, func.count(Order.id))
            .where(Order.is_archived.is_(False))
            .group_by(Order.status)
        )
        status_raw = dict(db.execute(status_counts_stmt).all())
        status_breakdown = [
            StatusBreakdownItem(status=s, count=status_raw.get(s, 0))
            for s in ALL_STATUSES
        ]

        # 5. Waiter Breakdown (for all active waiters)
        waiters = list(db.scalars(select(User).where(User.role == "waiter").order_by(User.name)).all())
        waiter_breakdown = []
        for w in waiters:
            # All unarchived orders where w is primary waiter
            w_orders_stmt = (
                select(Order)
                .options(selectinload(Order.lines))
                .where(
                    Order.primary_waiter_id == w.id,
                    Order.is_archived.is_(False),
                )
            )
            w_orders = list(db.scalars(w_orders_stmt).all())
            w_served = [o for o in w_orders if o.status == "served"]
            w_rev = sum((OrderService.calculate_order_total(o) for o in w_served), Decimal("0.00"))

            waiter_breakdown.append(
                WaiterBreakdownItem(
                    waiter_id=w.id,
                    waiter_name=w.name,
                    order_count=len(w_orders),
                    revenue=w_rev,
                )
            )

        # 6. Last 14 Days Served Orders Chart
        # 14 days ending today: [today - 13 days, ..., today]
        fourteen_days_ago = (today_start - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
        chart_orders_stmt = (
            select(Order)
            .options(selectinload(Order.lines))
            .where(
                Order.status == "served",
                Order.updated_at >= fourteen_days_ago,
            )
        )
        all_served_14d = list(db.scalars(chart_orders_stmt).all())

        # Group by date string YYYY-MM-DD
        daily_buckets = {}
        for d in range(14):
            day_dt = (today_start - timedelta(days=13 - d)).date()
            day_str = day_dt.strftime("%Y-%m-%d")
            daily_buckets[day_str] = {"count": 0, "revenue": Decimal("0.00")}

        for o in all_served_14d:
            o_date = o.updated_at.date().strftime("%Y-%m-%d")
            if o_date in daily_buckets:
                daily_buckets[o_date]["count"] += 1
                daily_buckets[o_date]["revenue"] += OrderService.calculate_order_total(o)

        last_14_days_chart = [
            ChartDayData(
                date=k,
                served_orders_count=v["count"],
                revenue=v["revenue"],
            )
            for k, v in sorted(daily_buckets.items())
        ]

        return DashboardSummaryResponse(
            open_orders_count=open_orders_count,
            today_revenue=today_revenue,
            today_orders_count=today_orders_count,
            today_served_count=today_served_count,
            status_breakdown=status_breakdown,
            waiter_breakdown=waiter_breakdown,
            last_14_days_chart=last_14_days_chart,
        )

    @classmethod
    def generate_orders_csv(
        cls,
        db: Session,
        table_number: Optional[int] = None,
        status: Optional[str] = None,
        waiter_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        include_archived: bool = False,
    ) -> str:
        """
        Goals 1 & 8: Export orders to CSV matching the current filtered slice.
        Manager-only, server-side streaming CSV generation with proper quoting.
        """
        query = (
            select(Order)
            .options(
                selectinload(Order.primary_waiter),
                selectinload(Order.collaborators).selectinload(OrderCollaborator.user),
                selectinload(Order.lines),
            )
        )

        if not include_archived:
            query = query.where(Order.is_archived.is_(False))

        if table_number is not None:
            query = query.where(Order.table_number == table_number)

        if status:
            query = query.where(Order.status == status.lower().strip())

        if waiter_id:
            query = query.where(Order.primary_waiter_id == waiter_id)

        if date_from:
            query = query.where(Order.created_at >= date_from)

        if date_to:
            query = query.where(Order.created_at <= date_to)

        query = query.order_by(desc(Order.created_at))
        orders = list(db.scalars(query).all())

        # Write to in-memory CSV
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Header
        writer.writerow([
            "Order ID",
            "Table Number",
            "Status",
            "Primary Waiter",
            "Collaborators",
            "Lines Count",
            "Total ($)",
            "Is Archived",
            "Created At",
            "Updated At",
        ])

        for o in orders:
            collabs_str = ", ".join([c.user.name for c in o.collaborators if c.user])
            writer.writerow([
                str(o.id),
                o.table_number,
                o.status,
                o.primary_waiter.name if o.primary_waiter else "Unknown",
                collabs_str if collabs_str else "None",
                len(o.lines),
                f"{OrderService.calculate_order_total(o):.2f}",
                "Yes" if o.is_archived else "No",
                o.created_at.isoformat() if o.created_at else "",
                o.updated_at.isoformat() if o.updated_at else "",
            ])

        return output.getvalue()
