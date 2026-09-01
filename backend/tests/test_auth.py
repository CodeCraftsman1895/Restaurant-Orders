from datetime import timedelta
import jwt
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.security import create_access_token


def test_login_success_manager(client: TestClient):
    """Test successful login with manager credentials."""
    response = client.post(
        "/api/auth/login",
        json={"email": "manager@restaurant.com", "password": "manager123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_success_waiter(client: TestClient):
    """Test successful login with waiter credentials."""
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@restaurant.com", "password": "waiter123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client: TestClient):
    """Test login failure with incorrect password."""
    response = client.post(
        "/api/auth/login",
        json={"email": "manager@restaurant.com", "password": "wrongpassword123"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Incorrect email or password"


def test_login_nonexistent_user(client: TestClient):
    """Test login failure with non-registered email."""
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@restaurant.com", "password": "password123"}
    )
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Incorrect email or password"


def test_get_current_user_profile_success(client: TestClient):
    """Test retrieving authenticated user profile using valid JWT token."""
    # 1. Login to get token
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "alice@restaurant.com", "password": "waiter123"}
    )
    token = login_resp.json()["access_token"]

    # 2. Access /api/auth/me
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "alice@restaurant.com"
    assert data["name"] == "Alice Johnson"
    assert data["role"] == "waiter"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    # Ensure password hash is NEVER exposed
    assert "password" not in data
    assert "password_hash" not in data


def test_get_current_user_missing_token(client: TestClient):
    """Test accessing protected route with missing Authorization header."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_get_current_user_malformed_header(client: TestClient):
    """Test accessing protected route with malformed authorization header."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "NotABearerToken 12345"}
    )
    assert response.status_code == 401


def test_get_current_user_invalid_token(client: TestClient):
    """Test accessing protected route with invalid token signature."""
    invalid_token = jwt.encode(
        {"sub": "fake-user"},
        "wrong-secret-key-at-least-32-characters-long",
        algorithm="HS256"
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_get_current_user_expired_token(client: TestClient):
    """Test accessing protected route with expired JWT token."""
    expired_token = create_access_token(
        subject="alice@restaurant.com",
        expires_delta=timedelta(seconds=-10)
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"
