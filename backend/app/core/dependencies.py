import uuid
from typing import Optional, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.user import User
from app.core.security import decode_access_token
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False
)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that extracts and verifies the JWT bearer token from the
    Authorization header, loads the authenticated user from the database, and
    raises HTTP 401 Unauthorized if missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user = AuthService.get_user_by_id(db, user_id)
    if not user:
        raise credentials_exception

    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """
    Dependency factory to enforce that the authenticated user possesses one of
    the specified roles. Raises HTTP 403 Forbidden if unauthorized.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker


# Pre-configured role dependencies for assignment authorization rules
require_manager = require_roles("manager")
require_waiter_or_manager = require_roles("manager", "waiter")
