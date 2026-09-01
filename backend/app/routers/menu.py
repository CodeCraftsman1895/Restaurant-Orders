import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.user import User
from app.schemas.menu import (
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemResponse,
    BulkMenuUpdateRequest,
    BulkMenuUpdateResponse,
)
from app.services.menu_service import MenuService
from app.core.dependencies import get_current_user, require_manager

router = APIRouter(prefix="/menu", tags=["Menu Management"])


@router.get("", response_model=List[MenuItemResponse])
def list_menu_items(
    include_archived: bool = False,
    only_available: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all active menu items.
    Supports filtering by availability and including archived items.
    Accessible by both waiters and managers.
    """
    return MenuService.list_menu_items(
        db=db,
        include_archived=include_archived,
        only_available=only_available
    )


@router.get("/{item_id}", response_model=MenuItemResponse)
def get_menu_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve single menu item details by UUID.
    Accessible by both waiters and managers.
    """
    item = MenuService.get_menu_item_by_id(db=db, item_id=item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    return item


@router.post("", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    data: MenuItemCreate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Create a new menu item (Manager only).
    """
    return MenuService.create_menu_item(db=db, data=data)


@router.put("/{item_id}", response_model=MenuItemResponse)
def update_menu_item(
    item_id: uuid.UUID,
    data: MenuItemUpdate,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Update an existing menu item (Manager only).
    """
    item = MenuService.get_menu_item_by_id(db=db, item_id=item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    return MenuService.update_menu_item(db=db, item=item, data=data)


@router.post("/{item_id}/archive", response_model=MenuItemResponse)
def archive_menu_item(
    item_id: uuid.UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Archive a menu item (Manager only).
    Archiving removes the dish from the active menu without destroying historical records.
    """
    item = MenuService.get_menu_item_by_id(db=db, item_id=item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    return MenuService.archive_menu_item(db=db, item=item)


@router.post("/{item_id}/restore", response_model=MenuItemResponse)
def restore_menu_item(
    item_id: uuid.UUID,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Restore an archived menu item (Manager only).
    """
    item = MenuService.get_menu_item_by_id(db=db, item_id=item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )
    return MenuService.restore_menu_item(db=db, item=item)


@router.post("/bulk", response_model=BulkMenuUpdateResponse)
def bulk_update_menu_items(
    request: BulkMenuUpdateRequest,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Goal 7: Bulk update price or availability across multiple menu items in a single action.
    Returns per-item success and failure reports. (Manager only)
    """
    return MenuService.bulk_update_menu_items(db=db, request=request)
