import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User
from app.core.security import verify_password, create_access_token


class AuthService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Query user by case-insensitive normalized email."""
        stmt = select(User).where(User.email == email.strip().lower())
        return db.scalars(stmt).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]:
        """Query user by primary key ID."""
        return db.get(User, user_id)

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate a user by email and password.
        Returns the User object if valid, otherwise None.
        """
        user = cls.get_user_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_user_token(user: User) -> str:
        """Create a signed JWT access token for the authenticated user."""
        return create_access_token(subject=str(user.id))
