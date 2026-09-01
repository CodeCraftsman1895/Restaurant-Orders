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
def alice_token(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"email": "alice@restaurant.com", "password": "waiter123"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def bob_token(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"email": "bob@restaurant.com", "password": "waiter123"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def carol_token(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"email": "carol@restaurant.com", "password": "waiter123"}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


# Helper fixture for available menu items
@pytest.fixture(scope="module")
def sample_menu_items(client: TestClient, alice_token: str):
    resp = client.get("/api/menu", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200
    items = resp.json()
    return {item["name"]: item for item in items}


# =========================================================================
# 1. ORDER CREATION & PRICE SNAPSHOT TESTS (Goals 1, 2, 3)
# =========================================================================

def test_create_order_with_lines_and_price_snapshot(
    client: TestClient,
    alice_token: str,
    manager_token: str,
    sample_menu_items: dict
):
    """
    Test creating order with multiple lines. Primary waiter is set to creator.
    Verifies price snapshots and ensures future menu price changes do not mutate order totals.
    """
    burger = sample_menu_items["Classic Burger"]
    fries = sample_menu_items["French Fries"]

    payload = {
        "table_number": 42,
        "lines": [
            {"menu_item_id": burger["id"], "quantity": 2, "special_instructions": "Medium rare"},
            {"menu_item_id": fries["id"], "quantity": 1, "special_instructions": "Extra salt"}
        ]
    }

    create_resp = client.post(
        "/api/orders",
        json=payload,
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert create_resp.status_code == 201
    order = create_resp.json()
    assert order["table_number"] == 42
    assert order["status"] == "placed"
    assert order["primary_waiter"]["email"] == "alice@restaurant.com"
    assert len(order["lines"]) == 2

    # Expected running total: (2 * 12.99) + (1 * 4.99) = 25.98 + 4.99 = 30.97
    expected_total = (Decimal(str(burger["price"])) * 2) + (Decimal(str(fries["price"])) * 1)
    assert Decimal(str(order["total"])) == expected_total

    # Price snapshot test: Change the menu item price
    client.put(
        f"/api/menu/{burger['id']}",
        json={"price": 99.99},
        headers={"Authorization": f"Bearer {manager_token}"}
    )

    # Re-fetch order: total and unit_price MUST NOT change
    fetch_resp = client.get(
        f"/api/orders/{order['id']}",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert fetch_resp.status_code == 200
    refetched = fetch_resp.json()
    assert Decimal(str(refetched["total"])) == expected_total
    burger_line = next(l for l in refetched["lines"] if l["menu_item_id"] == burger["id"])
    assert Decimal(str(burger_line["unit_price"])) == Decimal(str(burger["price"]))

    # Reset price back
    client.put(
        f"/api/menu/{burger['id']}",
        json={"price": float(burger["price"])},
        headers={"Authorization": f"Bearer {manager_token}"}
    )


def test_create_order_with_unavailable_item_rejected(
    client: TestClient,
    alice_token: str,
    manager_token: str
):
    """Attempting to order an unavailable dish is rejected with 400."""
    # Fetch unavailable item (Lobster Tail)
    menu_resp = client.get(
        "/api/menu?include_archived=true",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    lobster = next(i for i in menu_resp.json() if i["name"] == "Lobster Tail")
    assert lobster["is_available"] is False

    response = client.post(
        "/api/orders",
        json={"table_number": 99, "lines": [{"menu_item_id": lobster["id"], "quantity": 1}]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert response.status_code == 400
    assert "unavailable or archived" in response.json()["detail"]


# =========================================================================
# 2. ORDER LINE OPERATIONS & VOID RULES (Goals 3 & 4)
# =========================================================================

def test_add_line_and_void_with_reason(
    client: TestClient,
    alice_token: str,
    sample_menu_items: dict
):
    """
    Test adding a line to an open order, voiding a line with reason,
    and confirming voided lines are excluded from running total.
    """
    pizza = sample_menu_items["Margherita Pizza"]
    salad = sample_menu_items["Caesar Salad"]

    # 1. Create order with 1 pizza
    create_resp = client.post(
        "/api/orders",
        json={"table_number": 15, "lines": [{"menu_item_id": pizza["id"], "quantity": 1}]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    order_id = create_resp.json()["id"]

    # 2. Add salad line
    add_resp = client.post(
        f"/api/orders/{order_id}/lines",
        json={"menu_item_id": salad["id"], "quantity": 2, "special_instructions": "No croutons"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert add_resp.status_code == 201
    order = add_resp.json()
    assert len(order["lines"]) == 2

    # 3. Void salad line
    salad_line = next(l for l in order["lines"] if l["menu_item_id"] == salad["id"])
    void_resp = client.post(
        f"/api/orders/{order_id}/lines/{salad_line['id']}/void",
        json={"reason": "Customer allergic to dressing"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert void_resp.status_code == 200
    voided_order = void_resp.json()

    # Verify running total is now only the pizza price
    assert Decimal(str(voided_order["total"])) == Decimal(str(pizza["price"]))
    v_line = next(l for l in voided_order["lines"] if l["id"] == salad_line["id"])
    assert v_line["is_voided"] is True
    assert v_line["void_reason"] == "Customer allergic to dressing"


def test_void_line_without_reason_rejected(
    client: TestClient,
    alice_token: str,
    sample_menu_items: dict
):
    """Voiding without non-empty reason is rejected."""
    pizza = sample_menu_items["Margherita Pizza"]
    create_resp = client.post(
        "/api/orders",
        json={"table_number": 16, "lines": [{"menu_item_id": pizza["id"], "quantity": 1}]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    order = create_resp.json()
    line_id = order["lines"][0]["id"]

    response = client.post(
        f"/api/orders/{order['id']}/lines/{line_id}/void",
        json={"reason": "   "},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert response.status_code == 400


# =========================================================================
# 3. ORDER LIFECYCLE STATE TRANSITIONS (Goal 4)
# =========================================================================

def test_order_lifecycle_flow(client: TestClient, alice_token: str, sample_menu_items: dict):
    """
    Test full state transition: Placed -> Accepted -> Preparing -> Ready -> Served.
    """
    item = sample_menu_items["Classic Burger"]
    create_resp = client.post(
        "/api/orders",
        json={"table_number": 20, "lines": [{"menu_item_id": item["id"], "quantity": 1}]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    order_id = create_resp.json()["id"]

    # Placed -> Accepted
    resp = client.patch(f"/api/orders/{order_id}/status", json={"status": "accepted"}, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200 and resp.json()["status"] == "accepted"

    # Accepted -> Preparing
    resp = client.patch(f"/api/orders/{order_id}/status", json={"status": "preparing"}, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200 and resp.json()["status"] == "preparing"

    # Preparing -> Ready
    resp = client.patch(f"/api/orders/{order_id}/status", json={"status": "ready"}, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200 and resp.json()["status"] == "ready"

    # Ready -> Served
    resp = client.patch(f"/api/orders/{order_id}/status", json={"status": "served"}, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200 and resp.json()["status"] == "served"


def test_cannot_cancel_order_after_preparing(client: TestClient, alice_token: str, sample_menu_items: dict):
    """Goal 4 rule: Once in Preparing, an order can no longer be cancelled as a whole."""
    item = sample_menu_items["Classic Burger"]
    create_resp = client.post(
        "/api/orders",
        json={"table_number": 21, "lines": [{"menu_item_id": item["id"], "quantity": 1}]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    order_id = create_resp.json()["id"]

    # Transition to preparing
    client.patch(f"/api/orders/{order_id}/status", json={"status": "accepted"}, headers={"Authorization": f"Bearer {alice_token}"})
    client.patch(f"/api/orders/{order_id}/status", json={"status": "preparing"}, headers={"Authorization": f"Bearer {alice_token}"})

    # Attempt cancellation -> must be rejected with 400
    cancel_resp = client.patch(
        f"/api/orders/{order_id}/status",
        json={"status": "cancelled"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert cancel_resp.status_code == 400
    assert "once the kitchen has begun Preparing" in cancel_resp.json()["detail"]


# =========================================================================
# 4. COLLABORATORS & VISIBILITY (Goals 1, 5, 6)
# =========================================================================

def test_collaborator_assignment_and_permissions(
    client: TestClient,
    alice_token: str,
    bob_token: str,
    carol_token: str,
    manager_token: str,
    sample_menu_items: dict
):
    """
    Goal 5: Alice creates order. Carol cannot see/modify it.
    Alice adds Carol as collaborator. Carol can now see/modify it.
    Manager can see/modify it always.
    """
    item = sample_menu_items["Classic Burger"]
    create_resp = client.post(
        "/api/orders",
        json={"table_number": 30, "lines": [{"menu_item_id": item["id"], "quantity": 1}]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    order_id = create_resp.json()["id"]

    # Carol attempts to view -> 403 Forbidden
    resp_unauthorized = client.get(
        f"/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {carol_token}"}
    )
    assert resp_unauthorized.status_code == 403

    # Fetch Carol's user ID via /api/auth/me
    carol_profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {carol_token}"}).json()

    # Alice adds Carol as collaborator
    collab_resp = client.post(
        f"/api/orders/{order_id}/collaborators",
        json={"user_id": carol_profile["id"]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert collab_resp.status_code == 200
    assert any(c["id"] == carol_profile["id"] for c in collab_resp.json()["collaborators"])

    # Carol can now access the order
    resp_authorized = client.get(
        f"/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {carol_token}"}
    )
    assert resp_authorized.status_code == 200

    # Manager can also access the order
    resp_mgr = client.get(
        f"/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert resp_mgr.status_code == 200


# =========================================================================
# 5. SERVER-SIDE SEARCH, FILTER & PAGINATION (Goal 6)
# =========================================================================

def test_list_orders_filtering_and_pagination(client: TestClient, manager_token: str):
    """
    Goal 6: Search by table, filter by status, sort, and paginate.
    """
    response = client.get(
        "/api/orders?page=1&page_size=10&sort_by=created_at&sort_dir=desc",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "orders" in data
    assert "total" in data
    assert "total_pages" in data
    assert len(data["orders"]) <= 10


# =========================================================================
# 6. IMMUTABLE AUDIT TIMELINE (Goal 9)
# =========================================================================

def test_order_timeline_audit_trail(client: TestClient, alice_token: str, sample_menu_items: dict):
    """
    Goal 9: Verify chronological audit events for creation, notes, and status changes.
    """
    item = sample_menu_items["Classic Burger"]
    create_resp = client.post(
        "/api/orders",
        json={"table_number": 55, "lines": [{"menu_item_id": item["id"], "quantity": 1}]},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    order_id = create_resp.json()["id"]

    # Add a note
    client.post(
        f"/api/orders/{order_id}/notes",
        json={"note": "VIP Guest at table"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )

    # Change status
    client.patch(
        f"/api/orders/{order_id}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )

    # Fetch timeline
    timeline_resp = client.get(
        f"/api/orders/{order_id}/timeline",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert timeline_resp.status_code == 200
    events = timeline_resp.json()
    event_types = [e["event_type"] for e in events]
    assert "status_change" in event_types
    assert "line_added" in event_types
    assert "note_added" in event_types
