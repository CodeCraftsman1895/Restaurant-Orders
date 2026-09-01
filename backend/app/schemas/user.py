import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str


class UserResponse(UserBase):
    """
    Public user representation returned in API responses.
    Excludes password_hash and internal security secrets.
    """
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBrief(BaseModel):
    """
    Compact user representation for embedded relationships (waiters, collaborators).
    """
    id: uuid.UUID
    name: str
    role: str

    model_config = ConfigDict(from_attributes=True)
