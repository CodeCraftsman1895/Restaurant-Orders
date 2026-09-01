import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderListResponse,
    OrderLineCreate,
    VoidLineRequest,
    AddCollaboratorRequest,
    AddNoteRequest,
    OrderStatusUpdate,
)
from app.schemas.event import OrderEventResponse
from app.schemas.user import UserBrief
from app.services.order_service import OrderService
from app.services.event_service import EventService
from app.core.dependencies import get_current_user
from app.core.permissions import PermissionChecker

router = APIRouter(prefix="/orders", tags=["Order Management"])


def _verify_order_access(user: User, order) -> None:
    """Helper to enforce order access permissions for the current user."""
    collab_ids = [c.user_id for c in order.collaborators]
    if not PermissionChecker.can_access_order(user, order.primary_waiter_id, collab_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view or modify this order"
        )


@router.get("", response_model=OrderListResponse)
def list_orders(
    table_number: Optional[int] = Query(None, description="Search by table number"),
    status: Optional[str] = Query(None, description="Filter by status"),
    waiter_id: Optional[uuid.UUID] = Query(None, description="Filter by primary waiter"),
    date_from: Optional[datetime] = Query(None, description="Filter orders created on/after date"),
    date_to: Optional[datetime] = Query(None, description="Filter orders created on/before date"),
    include_archived: bool = Query(False, description="Include archived orders"),
    sort_by: str = Query("created_at", description="Sort by placed_time/created_at, status, or table_number"),
    sort_dir: str = Query("desc", description="Sort direction: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 6: Server-side search, filtering, sorting, and pagination across orders.
    Enforces waiter/manager visibility server-side.
    """
    return OrderService.list_orders(
        db=db,
        user=current_user,
        table_number=table_number,
        status=status,
        waiter_id=waiter_id,
        date_from=date_from,
        date_to=date_to,
        include_archived=include_archived,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goals 1, 2, 3: Create a new order for a table. The creator becomes the primary waiter.
    Captures price snapshot on all initial lines.
    """
    return OrderService.create_order(db=db, creator=current_user, data=data)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_detail(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve single order details, lines, collaborators, and running total.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    _verify_order_access(current_user, order)
    return OrderService.format_order_response(order)


@router.post("/{order_id}/lines", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def add_order_line(
    order_id: uuid.UUID,
    data: OrderLineCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 3: Add a line item to an open order prior to being served.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    return OrderService.add_line(db=db, user=current_user, order=order, line_data=data)


@router.post("/{order_id}/lines/{line_id}/void", response_model=OrderResponse)
def void_order_line(
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    data: VoidLineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 4: Void an order line with required explanatory reason while order is open.
    Marks line rather than deleting it.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    return OrderService.void_line(db=db, user=current_user, order=order, line_id=line_id, reason=data.reason)


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: uuid.UUID,
    data: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 4: Move order through lifecycle stages with server-enforced rules.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    return OrderService.update_status(db=db, user=current_user, order=order, new_status=data.status)


@router.post("/{order_id}/collaborators", response_model=OrderResponse)
def add_collaborator(
    order_id: uuid.UUID,
    data: AddCollaboratorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 5: Add a collaborating waiter to the order.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    return OrderService.add_collaborator(db=db, user=current_user, order=order, target_user_id=data.user_id)


@router.delete("/{order_id}/collaborators/{user_id}", response_model=OrderResponse)
def remove_collaborator(
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a collaborating waiter from the order."""
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    return OrderService.remove_collaborator(db=db, user=current_user, order=order, target_user_id=user_id)


@router.post("/{order_id}/notes", response_model=OrderResponse)
def add_order_note(
    order_id: uuid.UUID,
    data: AddNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 9: Add a note to the order's immutable history.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    return OrderService.add_note(db=db, user=current_user, order=order, note_text=data.note)


@router.post("/{order_id}/archive", response_model=OrderResponse)
def archive_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 2: Archive an order without destroying history.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    order.is_archived = True
    db.commit()
    return OrderService.format_order_response(order)


@router.post("/{order_id}/restore", response_model=OrderResponse)
def restore_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 2: Restore an archived order to active view.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)
    order.is_archived = False
    db.commit()
    return OrderService.format_order_response(order)


@router.get("/{order_id}/timeline", response_model=List[OrderEventResponse])
def get_order_timeline(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Goal 9: Retrieve immutable chronological audit history for the order.
    """
    order = OrderService.get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _verify_order_access(current_user, order)

    events = EventService.get_order_events(db, order_id)
    resp = []
    for e in events:
        resp.append(
            OrderEventResponse(
                id=e.id,
                order_id=e.order_id,
                user=UserBrief(id=e.user.id, name=e.user.name, role=e.user.role),
                event_type=e.event_type,
                old_status=e.old_status,
                new_status=e.new_status,
                order_line_id=e.order_line_id,
                details=e.details,
                created_at=e.created_at,
            )
        )
    return resp
