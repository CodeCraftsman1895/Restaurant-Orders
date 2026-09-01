import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def manager_token(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"email": "manager@restaurant.com", "password": "manager123"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def waiter_token(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"email": "alice@restaurant.com", "password": "waiter123"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


# =========================================================================
# 1. MENU RETRIEVAL & FILTERING TESTS
# =========================================================================

def test_list_menu_items_authenticated_waiter(client: TestClient, waiter_token: str):
    """Waiters can retrieve the active menu (excludes archived by default)."""
    response = client.get(
        "/api/menu",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 14
    # Ensure default listing excludes archived items
    for item in items:
        assert item["is_archived"] is False


def test_list_menu_items_include_archived(client: TestClient, manager_token: str):
    """Managers can retrieve the full catalog including archived dishes."""
    response = client.get(
        "/api/menu?include_archived=true",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    items = response.json()
    assert any(i["is_archived"] is True for i in items)


def test_list_menu_items_unauthenticated_rejected(client: TestClient):
    """Unauthenticated access must be rejected with 401."""
    response = client.get("/api/menu")
    assert response.status_code == 401


def test_get_menu_item_detail(client: TestClient, waiter_token: str):
    """Staff can retrieve a single menu item by ID."""
    # Fetch menu list first to get an ID
    list_resp = client.get(
        "/api/menu",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    first_item = list_resp.json()[0]

    response = client.get(
        f"/api/menu/{first_item['id']}",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == first_item["id"]
    assert data["name"] == first_item["name"]


def test_get_menu_item_not_found(client: TestClient, waiter_token: str):
    """Requesting non-existent menu item returns 404."""
    fake_id = uuid.uuid4()
    response = client.get(
        f"/api/menu/{fake_id}",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Menu item not found"


# =========================================================================
# 2. CREATE MENU ITEM TESTS (Goal 1: Manager Only)
# =========================================================================

def test_create_menu_item_manager_success(client: TestClient, manager_token: str):
    """Manager can successfully create a new menu item."""
    payload = {
        "name": f"Chef Special Tart - {uuid.uuid4().hex[:6]}",
        "price": 11.50,
        "is_available": True
    }
    response = client.post(
        "/api/menu",
        json=payload,
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert float(data["price"]) == 11.50
    assert data["is_available"] is True
    assert data["is_archived"] is False


def test_create_menu_item_waiter_forbidden(client: TestClient, waiter_token: str):
    """Waiters must be forbidden from creating menu items (Goal 1)."""
    payload = {
        "name": "Unauthorized Dish",
        "price": 9.99,
        "is_available": True
    }
    response = client.post(
        "/api/menu",
        json=payload,
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 403
    assert "Operation not permitted" in response.json()["detail"]


def test_create_menu_item_invalid_price_rejected(client: TestClient, manager_token: str):
    """Non-positive prices must be rejected with 422."""
    response = client.post(
        "/api/menu",
        json={"name": "Bad Price Item", "price": -5.00, "is_available": True},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 422


# =========================================================================
# 3. UPDATE, ARCHIVE & RESTORE TESTS (Goal 1: Manager Only)
# =========================================================================

def test_update_menu_item_manager(client: TestClient, manager_token: str):
    """Manager can update name, price, and availability of an existing item."""
    # Create item to update
    create_resp = client.post(
        "/api/menu",
        json={"name": "Soup of the Day", "price": 6.50, "is_available": True},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    item_id = create_resp.json()["id"]

    # Update price and availability
    update_resp = client.put(
        f"/api/menu/{item_id}",
        json={"price": 7.25, "is_available": False},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert float(data["price"]) == 7.25
    assert data["is_available"] is False


def test_update_menu_item_waiter_forbidden(client: TestClient, waiter_token: str, manager_token: str):
    """Waiters cannot change prices or update menu items (Goal 1)."""
    # Create item
    create_resp = client.post(
        "/api/menu",
        json={"name": "Price Check Dish", "price": 10.00, "is_available": True},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    item_id = create_resp.json()["id"]

    # Waiter attempts update
    response = client.put(
        f"/api/menu/{item_id}",
        json={"price": 5.00},
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 403


def test_archive_and_restore_menu_item(client: TestClient, manager_token: str):
    """Manager can archive and subsequently restore a menu item."""
    # Create item
    create_resp = client.post(
        "/api/menu",
        json={"name": "Summer Lemonade", "price": 4.50, "is_available": True},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    item_id = create_resp.json()["id"]

    # Archive
    archive_resp = client.post(
        f"/api/menu/{item_id}/archive",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["is_archived"] is True

    # Confirm item no longer in default menu list
    list_resp = client.get(
        "/api/menu",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert not any(i["id"] == item_id for i in list_resp.json())

    # Restore
    restore_resp = client.post(
        f"/api/menu/{item_id}/restore",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["is_archived"] is False


# =========================================================================
# 4. BULK MENU ACTIONS TESTS (Goal 7: Manager Only with Per-Item Reporting)
# =========================================================================

def test_bulk_update_menu_items_manager_with_per_item_results(client: TestClient, manager_token: str):
    """
    Goal 7: Bulk update price or availability across multiple items.
    Returns per-item results with successes and explanatory failure reasons.
    """
    # Create 2 test items
    item1 = client.post(
        "/api/menu",
        json={"name": "Bulk Test Item 1", "price": 10.00, "is_available": True},
        headers={"Authorization": f"Bearer {manager_token}"}
    ).json()

    item2 = client.post(
        "/api/menu",
        json={"name": "Bulk Test Item 2", "price": 12.00, "is_available": True},
        headers={"Authorization": f"Bearer {manager_token}"}
    ).json()

    fake_id = str(uuid.uuid4())

    # Bulk update: item1, item2, and nonexistent fake_id
    response = client.post(
        "/api/menu/bulk",
        json={
            "item_ids": [item1["id"], item2["id"], fake_id],
            "price": 15.00,
            "is_available": False
        },
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    results = data["results"]
    assert len(results) == 3

    # item1 succeeded
    r1 = next(r for r in results if r["item_id"] == item1["id"])
    assert r1["success"] is True
    assert r1["error"] is None

    # item2 succeeded
    r2 = next(r for r in results if r["item_id"] == item2["id"])
    assert r2["success"] is True
    assert r2["error"] is None

    # fake_id reported rejected with reason
    r3 = next(r for r in results if r["item_id"] == fake_id)
    assert r3["success"] is False
    assert r3["error"] == "Menu item not found"


def test_bulk_update_waiter_forbidden(client: TestClient, waiter_token: str):
    """Waiters must be rejected from bulk menu actions (Goal 7)."""
    response = client.post(
        "/api/menu/bulk",
        json={"item_ids": [str(uuid.uuid4())], "is_available": False},
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 403
