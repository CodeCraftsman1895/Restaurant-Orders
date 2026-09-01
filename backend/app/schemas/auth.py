from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """
    Schema for user login credentials.
    """
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Schema for JWT token response upon successful authentication.
    """
    access_token: str
    token_type: str = "bearer"
