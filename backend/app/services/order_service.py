import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, or_, and_, desc, asc
from fastapi import HTTPException, status

from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.collaborator import OrderCollaborator
from app.models.menu_item import MenuItem
from app.models.user import User
from app.models.order_event import OrderEvent
from app.schemas.order import (
    OrderCreate,
    OrderLineCreate,
    OrderResponse,
    OrderLineResponse,
    OrderListItem,
    OrderListResponse,
)
from app.schemas.user import UserBrief
from app.services.event_service import EventService
from app.core.permissions import PermissionChecker

VALID_TRANSITIONS = {
    "placed": ["accepted", "cancelled"],
    "accepted": ["preparing", "cancelled"],
    "preparing": ["ready"],
    "ready": ["served"],
    "served": [],
    "cancelled": [],
}


class OrderService:
    @staticmethod
    def calculate_order_total(order: Order) -> Decimal:
        """
        Goal 3: Running total calculated from price snapshot on each line.
        Goal 4: Voided lines are strictly excluded from the total.
        """
        total = Decimal("0.00")
        for line in order.lines:
            if not line.is_voided:
                total += Decimal(str(line.unit_price)) * line.quantity
        return total

    @classmethod
    def format_order_response(cls, order: Order) -> OrderResponse:
        """Helper to format an Order ORM instance into full OrderResponse schema."""
        lines_resp = []
        for l in order.lines:
            line_tot = Decimal(str(l.unit_price)) * l.quantity if not l.is_voided else Decimal("0.00")
            lines_resp.append(
                OrderLineResponse(
                    id=l.id,
                    order_id=l.order_id,
                    menu_item_id=l.menu_item_id,
                    menu_item_name=l.menu_item.name if l.menu_item else None,
                    quantity=l.quantity,
                    unit_price=l.unit_price,
                    line_total=line_tot,
                    special_instructions=l.special_instructions,
                    is_voided=l.is_voided,
                    void_reason=l.void_reason,
                    created_at=l.created_at,
                )
            )

        collabs_resp = [
            UserBrief(id=c.user.id, name=c.user.name, email=c.user.email, role=c.user.role)
            for c in order.collaborators if c.user
        ]

        return OrderResponse(
            id=order.id,
            table_number=order.table_number,
            status=order.status,
            primary_waiter=UserBrief(
                id=order.primary_waiter.id,
                name=order.primary_waiter.name,
                email=order.primary_waiter.email,
                role=order.primary_waiter.role,
            ),
            collaborators=collabs_resp,
            lines=lines_resp,
            total=cls.calculate_order_total(order),
            is_archived=order.is_archived,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )

    @staticmethod
    def get_order_with_relations(db: Session, order_id: uuid.UUID) -> Optional[Order]:
        """Fetch order with preloaded relations."""
        stmt = (
            select(Order)
            .options(
                selectinload(Order.primary_waiter),
                selectinload(Order.collaborators).selectinload(OrderCollaborator.user),
                selectinload(Order.lines).selectinload(OrderLine.menu_item),
            )
            .where(Order.id == order_id)
        )
        return db.scalars(stmt).first()

    @classmethod
    def create_order(
        cls,
        db: Session,
        creator: User,
        data: OrderCreate
    ) -> OrderResponse:
        """
        Goals 1, 2, 3: Create order with table number and initial dish lines.
        Creator becomes primary waiter. Unit price is captured at insertion time.
        """
        order = Order(
            table_number=data.table_number,
            primary_waiter_id=creator.id,
            status="placed",
            is_archived=False,
        )
        db.add(order)
        db.flush()

        # Log order placement event
        EventService.log_event(
            db=db,
            order_id=order.id,
            user_id=creator.id,
            event_type="status_change",
            old_status=None,
            new_status="placed",
            details="Order created",
        )

        # Process initial lines
        for line_data in data.lines or []:
            menu_item = db.get(MenuItem, line_data.menu_item_id)
            if not menu_item:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Menu item '{line_data.menu_item_id}' not found"
                )
            if menu_item.is_archived or not menu_item.is_available:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Menu item '{menu_item.name}' is currently unavailable or archived"
                )

            line = OrderLine(
                order_id=order.id,
                menu_item_id=menu_item.id,
                quantity=line_data.quantity,
                special_instructions=line_data.special_instructions,
                unit_price=menu_item.price,
                is_voided=False,
            )
            db.add(line)
            db.flush()

            EventService.log_event(
                db=db,
                order_id=order.id,
                user_id=creator.id,
                event_type="line_added",
                order_line_id=line.id,
                details=f"Added {line.quantity}x {menu_item.name}",
            )

        db.commit()
        loaded = cls.get_order_with_relations(db, order.id)
        return cls.format_order_response(loaded)

    @classmethod
    def add_line(
        cls,
        db: Session,
        user: User,
        order: Order,
        line_data: OrderLineCreate
    ) -> OrderResponse:
        """
        Goal 3: Add a line to an open order before it is served.
        """
        if order.status in ("served", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot add lines to a {order.status} order"
            )
        if order.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify an archived order. Restore it first."
            )

        menu_item = db.get(MenuItem, line_data.menu_item_id)
        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Menu item '{line_data.menu_item_id}' not found"
            )
        if menu_item.is_archived or not menu_item.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Menu item '{menu_item.name}' is currently unavailable or archived"
            )

        line = OrderLine(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=line_data.quantity,
            special_instructions=line_data.special_instructions,
            unit_price=menu_item.price,
            is_voided=False,
        )
        db.add(line)
        db.flush()

        EventService.log_event(
            db=db,
            order_id=order.id,
            user_id=user.id,
            event_type="line_added",
            order_line_id=line.id,
            details=f"Added {line.quantity}x {menu_item.name}",
        )

        db.commit()
        loaded = cls.get_order_with_relations(db, order.id)
        return cls.format_order_response(loaded)

    @classmethod
    def void_line(
        cls,
        db: Session,
        user: User,
        order: Order,
        line_id: uuid.UUID,
        reason: str
    ) -> OrderResponse:
        """
        Goal 4: Void an individual line with required reason while order is open.
        Marks the line without deleting the record.
        """
        if order.status in ("served", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot void lines on a {order.status} order. Order is closed."
            )
        if order.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify an archived order."
            )

        line = db.get(OrderLine, line_id)
        if not line or line.order_id != order.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order line not found on this order"
            )
        if line.is_voided:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Line is already voided"
            )
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid explanation reason is required to void an order line"
            )

        line.is_voided = True
        line.void_reason = reason.strip()

        item_name = line.menu_item.name if line.menu_item else "item"
        EventService.log_event(
            db=db,
            order_id=order.id,
            user_id=user.id,
            event_type="line_voided",
            order_line_id=line.id,
            details=f"Voided {line.quantity}x {item_name}: {reason.strip()}",
        )

        db.commit()
        loaded = cls.get_order_with_relations(db, order.id)
        return cls.format_order_response(loaded)

    @classmethod
    def update_status(
        cls,
        db: Session,
        user: User,
        order: Order,
        new_status: str
    ) -> OrderResponse:
        """
        Goal 4: Advance order lifecycle with strict transition rules.
        Rejects invalid moves with explanatory error messages.
        """
        new_status = new_status.lower().strip()
        if order.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot transition status of an archived order. Restore it first."
            )

        allowed_targets = VALID_TRANSITIONS.get(order.status, [])
        if new_status not in allowed_targets:
            if order.status in ("preparing", "ready") and new_status == "cancelled":
                msg = f"Cannot cancel order: once the kitchen has begun Preparing, the order cannot be cancelled as a whole."
            elif order.status in ("served", "cancelled"):
                msg = f"Order is already {order.status} and cannot be transitioned further."
            else:
                msg = f"Invalid status transition from '{order.status}' to '{new_status}'. Allowed transitions: {', '.join(allowed_targets) if allowed_targets else 'None'}."

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg
            )

        old_status = order.status
        order.status = new_status

        EventService.log_event(
            db=db,
            order_id=order.id,
            user_id=user.id,
            event_type="status_change",
            old_status=old_status,
            new_status=new_status,
            details=f"Status changed from {old_status} to {new_status}",
        )

        db.commit()
        loaded = cls.get_order_with_relations(db, order.id)
        return cls.format_order_response(loaded)

    @classmethod
    def add_collaborator(
        cls,
        db: Session,
        user: User,
        order: Order,
        target_user_id: uuid.UUID
    ) -> OrderResponse:
        """
        Goal 5: Add a collaborating waiter to an order.
        """
        target_user = db.get(User, target_user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        if target_user.role != "waiter":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only waiters can be added as order collaborators"
            )
        if target_user.id == order.primary_waiter_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already the primary waiter on this order"
            )

        # Check existing
        existing_collab = db.execute(
            select(OrderCollaborator).where(
                OrderCollaborator.order_id == order.id,
                OrderCollaborator.user_id == target_user.id,
            )
        ).scalar_one_or_none()

        if existing_collab:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a collaborator on this order"
            )

        collab = OrderCollaborator(order_id=order.id, user_id=target_user.id)
        db.add(collab)

        EventService.log_event(
            db=db,
            order_id=order.id,
            user_id=user.id,
            event_type="note_added",
            details=f"Added {target_user.name} as collaborator",
        )

        db.commit()
        loaded = cls.get_order_with_relations(db, order.id)
        return cls.format_order_response(loaded)

    @classmethod
    def remove_collaborator(
        cls,
        db: Session,
        user: User,
        order: Order,
        target_user_id: uuid.UUID
    ) -> OrderResponse:
        """Remove a collaborator from an order."""
        collab = db.execute(
            select(OrderCollaborator).where(
                OrderCollaborator.order_id == order.id,
                OrderCollaborator.user_id == target_user_id,
            )
        ).scalar_one_or_none()

        if not collab:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collaborator not found on this order"
            )

        db.delete(collab)
        db.commit()
        loaded = cls.get_order_with_relations(db, order.id)
        return cls.format_order_response(loaded)

    @classmethod
    def add_note(
        cls,
        db: Session,
        user: User,
        order: Order,
        note_text: str
    ) -> OrderResponse:
        """Goal 9: Add a note to the order timeline."""
        if not note_text or not note_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Note text cannot be empty"
            )

        EventService.log_event(
            db=db,
            order_id=order.id,
            user_id=user.id,
            event_type="note_added",
            details=note_text.strip(),
        )
        db.commit()
        loaded = cls.get_order_with_relations(db, order.id)
        return cls.format_order_response(loaded)

    @classmethod
    def archive_order(db: Session, order: Order) -> OrderResponse:
        """Goal 2: Archive an order."""
        order.is_archived = True
        db.commit()
        return OrderService.format_order_response(order)

    @classmethod
    def restore_order(db: Session, order: Order) -> OrderResponse:
        """Goal 2: Restore an archived order."""
        order.is_archived = False
        db.commit()
        return OrderService.format_order_response(order)

    @classmethod
    def list_orders(
        cls,
        db: Session,
        user: User,
        table_number: Optional[int] = None,
        status: Optional[str] = None,
        waiter_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> OrderListResponse:
        """
        Goal 6: Server-side search, filtering, sorting, and pagination across orders
        with role-based visibility enforcement.
        """
        query = select(Order).options(
            selectinload(Order.primary_waiter),
            selectinload(Order.lines),
        )

        # 1. Role-Based Visibility
        if user.role == "waiter":
            # Waiter sees orders where they are primary waiter OR collaborator
            subquery_collab = select(OrderCollaborator.order_id).where(OrderCollaborator.user_id == user.id)
            query = query.where(
                or_(
                    Order.primary_waiter_id == user.id,
                    Order.id.in_(subquery_collab),
                )
            )

        # 2. Filters
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

        # Total count query
        count_query = select(func.count()).select_from(query.subquery())
        total_count = db.scalar(count_query) or 0

        # 3. Sorting
        sort_column = Order.created_at
        if sort_by == "table_number":
            sort_column = Order.table_number
        elif sort_by == "status":
            sort_column = Order.status
        elif sort_by == "placed_time" or sort_by == "created_at":
            sort_column = Order.created_at

        direction = desc if sort_dir.lower() == "desc" else asc
        query = query.order_by(direction(sort_column))

        # 4. Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        orders = list(db.scalars(query).all())

        items = []
        for o in orders:
            items.append(
                OrderListItem(
                    id=o.id,
                    table_number=o.table_number,
                    status=o.status,
                    primary_waiter=UserBrief(
                        id=o.primary_waiter.id,
                        name=o.primary_waiter.name,
                        role=o.primary_waiter.role,
                    ),
                    line_count=len(o.lines),
                    total=cls.calculate_order_total(o),
                    is_archived=o.is_archived,
                    created_at=o.created_at,
                    updated_at=o.updated_at,
                )
            )

        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

        return OrderListResponse(
            orders=items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
