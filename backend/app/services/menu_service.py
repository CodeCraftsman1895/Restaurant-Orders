import uuid
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.menu_item import MenuItem
from app.schemas.menu import (
    MenuItemCreate,
    MenuItemUpdate,
    BulkMenuUpdateRequest,
    BulkMenuItemResult,
    BulkMenuUpdateResponse,
)


class MenuService:
    @staticmethod
    def list_menu_items(
        db: Session,
        include_archived: bool = False,
        only_available: bool = False
    ) -> List[MenuItem]:
        """
        List menu items. Default excludes archived items.
        """
        stmt = select(MenuItem)
        if not include_archived:
            stmt = stmt.where(MenuItem.is_archived.is_(False))
        if only_available:
            stmt = stmt.where(MenuItem.is_available.is_(True))
        stmt = stmt.order_by(MenuItem.name.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_menu_item_by_id(db: Session, item_id: uuid.UUID) -> Optional[MenuItem]:
        """Retrieve a single menu item by primary key UUID."""
        return db.get(MenuItem, item_id)

    @staticmethod
    def create_menu_item(db: Session, data: MenuItemCreate) -> MenuItem:
        """Create a new menu item (Manager only)."""
        item = MenuItem(
            name=data.name.strip(),
            price=data.price,
            is_available=data.is_available,
            is_archived=False
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def update_menu_item(
        db: Session,
        item: MenuItem,
        data: MenuItemUpdate
    ) -> MenuItem:
        """Update an existing menu item (Manager only)."""
        if data.name is not None:
            item.name = data.name.strip()
        if data.price is not None:
            item.price = data.price
        if data.is_available is not None:
            item.is_available = data.is_available
        if data.is_archived is not None:
            item.is_archived = data.is_archived

        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def archive_menu_item(db: Session, item: MenuItem) -> MenuItem:
        """Archive a menu item (Manager only)."""
        item.is_archived = True
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def restore_menu_item(db: Session, item: MenuItem) -> MenuItem:
        """Restore an archived menu item (Manager only)."""
        item.is_archived = False
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def bulk_update_menu_items(
        cls,
        db: Session,
        request: BulkMenuUpdateRequest
    ) -> BulkMenuUpdateResponse:
        """
        Goal 7: Apply bulk changes to multiple menu items with per-item reporting
        of successes and specific failure reasons.
        """
        results: List[BulkMenuItemResult] = []

        # Validate general request parameters
        price_invalid = request.price is not None and request.price <= Decimal("0")
        no_changes_specified = request.price is None and request.is_available is None

        for item_id in request.item_ids:
            if price_invalid:
                results.append(
                    BulkMenuItemResult(
                        item_id=item_id,
                        success=False,
                        error="Price must be greater than zero"
                    )
                )
                continue

            if no_changes_specified:
                results.append(
                    BulkMenuItemResult(
                        item_id=item_id,
                        success=False,
                        error="No changes specified"
                    )
                )
                continue

            item = db.get(MenuItem, item_id)
            if not item:
                results.append(
                    BulkMenuItemResult(
                        item_id=item_id,
                        success=False,
                        error="Menu item not found"
                    )
                )
                continue

            # Apply updates
            if request.price is not None:
                item.price = request.price
            if request.is_available is not None:
                item.is_available = request.is_available

            try:
                db.flush()
                results.append(
                    BulkMenuItemResult(
                        item_id=item_id,
                        success=True,
                        error=None
                    )
                )
            except Exception as e:
                db.rollback()
                results.append(
                    BulkMenuItemResult(
                        item_id=item_id,
                        success=False,
                        error=f"Database error: {str(e)}"
                    )
                )

        db.commit()
        return BulkMenuUpdateResponse(results=results)
