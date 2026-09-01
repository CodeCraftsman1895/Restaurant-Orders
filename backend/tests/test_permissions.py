import uuid
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from app.core.dependencies import get_current_user, require_manager, require_waiter_or_manager
from app.core.permissions import PermissionChecker
from app.models.user import User

# Test router to verify dependency behavior on FastAPI endpoints
test_router = APIRouter(prefix="/api/test-rbac")


@test_router.get("/manager-only")
def manager_only_endpoint(current_user: User = Depends(require_manager)):
    return {"message": "Welcome manager", "user_id": str(current_user.id), "role": current_user.role}


@test_router.get("/waiter-or-manager")
def waiter_or_manager_endpoint(current_user: User = Depends(require_waiter_or_manager)):
    return {"message": "Welcome staff", "user_id": str(current_user.id), "role": current_user.role}


@pytest.fixture(scope="module")
def rbac_client():
    from app.routers import auth
    test_app = FastAPI()
    test_app.include_router(auth.router, prefix="/api")
    test_app.include_router(test_router)
    with TestClient(test_app) as client:
        yield client


@pytest.fixture(scope="module")
def manager_token(rbac_client: TestClient):
    resp = rbac_client.post(
        "/api/auth/login",
        json={"email": "manager@restaurant.com", "password": "manager123"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def waiter_token(rbac_client: TestClient):
    resp = rbac_client.post(
        "/api/auth/login",
        json={"email": "alice@restaurant.com", "password": "waiter123"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


# =========================================================================
# 1. MANAGER-ONLY AUTHORIZATION TESTS
# =========================================================================

def test_manager_access_manager_endpoint(rbac_client: TestClient, manager_token: str):
    """Manager should successfully access manager-protected routes."""
    response = rbac_client.get(
        "/api/test-rbac/manager-only",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "manager"
    assert "Welcome manager" in data["message"]


def test_waiter_rejected_from_manager_endpoint(rbac_client: TestClient, waiter_token: str):
    """Waiter must receive 403 Forbidden on manager-only routes."""
    response = rbac_client.get(
        "/api/test-rbac/manager-only",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 403
    data = response.json()
    assert "Operation not permitted" in data["detail"]


def test_unauthenticated_rejected_with_401(rbac_client: TestClient):
    """Unauthenticated requests must receive 401 Unauthorized (not 403)."""
    response = rbac_client.get("/api/test-rbac/manager-only")
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


# =========================================================================
# 2. WAITER-OR-MANAGER AUTHORIZATION TESTS
# =========================================================================

def test_waiter_access_waiter_endpoint(rbac_client: TestClient, waiter_token: str):
    """Waiter should successfully access staff-authorized routes."""
    response = rbac_client.get(
        "/api/test-rbac/waiter-or-manager",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "waiter"


def test_manager_access_waiter_endpoint(rbac_client: TestClient, manager_token: str):
    """Manager should also have access to staff-authorized routes."""
    response = rbac_client.get(
        "/api/test-rbac/waiter-or-manager",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "manager"


# =========================================================================
# 3. SECURITY / ANTI-BYPASS VERIFICATION
# =========================================================================

def test_authorization_bypass_via_headers_or_body_rejected(rbac_client: TestClient, waiter_token: str):
    """
    Attempting to spoof role as 'manager' in query or headers while using a
    waiter JWT must still be rejected with 403 Forbidden.
    """
    response = rbac_client.get(
        "/api/test-rbac/manager-only?role=manager",
        headers={
            "Authorization": f"Bearer {waiter_token}",
            "X-User-Role": "manager",
            "X-Role": "manager",
        }
    )
    assert response.status_code == 403
    assert "Operation not permitted" in response.json()["detail"]


# =========================================================================
# 4. ORDER-LEVEL PERMISSION CHECKER UNIT TESTS (Goals 1 & 5)
# =========================================================================

def test_order_access_permissions_logic():
    """Verify core order permission evaluation according to assignment rules."""
    manager_user = User(id=uuid.uuid4(), name="Mgr", email="m@r.com", password_hash="h", role="manager")
    primary_waiter = User(id=uuid.uuid4(), name="Alice", email="a@r.com", password_hash="h", role="waiter")
    collab_waiter = User(id=uuid.uuid4(), name="Bob", email="b@r.com", password_hash="h", role="waiter")
    unrelated_waiter = User(id=uuid.uuid4(), name="Carol", email="c@r.com", password_hash="h", role="waiter")

    order_primary_id = primary_waiter.id
    collaborator_ids = [collab_waiter.id]

    # Goal 1: Manager can see and act on every order
    assert PermissionChecker.can_access_order(manager_user, order_primary_id, collaborator_ids) is True

    # Goal 1: Primary waiter can act on their own order
    assert PermissionChecker.can_access_order(primary_waiter, order_primary_id, collaborator_ids) is True

    # Goal 5: Collaborator waiter can act on collaborated order
    assert PermissionChecker.can_access_order(collab_waiter, order_primary_id, collaborator_ids) is True

    # Goal 1: Unrelated waiter CANNOT act on another waiter's order
    assert PermissionChecker.can_access_order(unrelated_waiter, order_primary_id, collaborator_ids) is False

    # Goal 1: Menu management is restricted to manager only
    assert PermissionChecker.can_manage_menu(manager_user) is True
    assert PermissionChecker.can_manage_menu(primary_waiter) is False
    assert PermissionChecker.can_manage_menu(collab_waiter) is False
