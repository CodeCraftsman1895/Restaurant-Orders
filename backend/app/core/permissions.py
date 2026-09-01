import uuid
from typing import Sequence
from app.models.user import User


class PermissionChecker:
    """
    Core authorization evaluation logic enforcing server-side business rules
    specified by the Restaurant Orders assignment.
    """

    @staticmethod
    def is_manager(user: User) -> bool:
        """Check if user has manager role."""
        return user.role == "manager"

    @staticmethod
    def is_waiter(user: User) -> bool:
        """Check if user has waiter role."""
        return user.role == "waiter"

    @classmethod
    def can_manage_menu(cls, user: User) -> bool:
        """
        Goal 1: Managers create/archive menu items, set name, price, and availability.
        Waiters cannot create menu items or change prices.
        """
        return cls.is_manager(user)

    @classmethod
    def can_access_order(
        cls,
        user: User,
        primary_waiter_id: uuid.UUID,
        collaborator_user_ids: Sequence[uuid.UUID] = ()
    ) -> bool:
        """
        Goals 1 & 5: Managers can see and act on every order.
        Waiters can see and act on orders where they are the primary waiter
        or an assigned collaborator. Unrelated waiters are strictly forbidden.
        """
        if cls.is_manager(user):
            return True
        if user.id == primary_waiter_id:
            return True
        if user.id in collaborator_user_ids:
            return True
        return False
