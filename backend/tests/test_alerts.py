import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.order import Order
from app.models.alert_acknowledgment import AlertAcknowledgment


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


# =========================================================================
# 1. SLOW ORDER DETECTION & DYNAMIC BADGE (Goal 10)
# =========================================================================

def test_slow_orders_list_and_badge_manager(client: TestClient, manager_token: str):
    """
    Goal 10: Badge shows dynamic count of active slow orders.
    Manager sees slow orders across all tables.
    """
    # 1. Fetch badge count
    badge_resp = client.get(
        "/api/alerts/badge",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert badge_resp.status_code == 200
    badge_data = badge_resp.json()
    assert "slow_orders_count" in badge_data
    assert isinstance(badge_data["slow_orders_count"], int)

    # 2. Fetch slow orders list
    list_resp = client.get(
        "/api/alerts",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert list_resp.status_code == 200
    alerts = list_resp.json()
    assert len(alerts) == badge_data["slow_orders_count"]

    # Verify fields in each slow order item
    for item in alerts:
        assert "order_id" in item
        assert "table_number" in item
        assert "status" in item
        assert "minutes_open" in item
        assert "primary_waiter" in item
        assert item["status"] in ("placed", "accepted", "preparing", "ready")


def test_slow_orders_visibility_waiter(client: TestClient, alice_token: str):
    """
    Goal 10: Waiters only see slow order alerts for orders they created or collaborate on.
    """
    badge_resp = client.get(
        "/api/alerts/badge",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert badge_resp.status_code == 200

    list_resp = client.get(
        "/api/alerts",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert list_resp.status_code == 200
    alerts = list_resp.json()

    for item in alerts:
        is_primary = item["primary_waiter"]["email"] == "alice@restaurant.com"
        is_collab = any(c["email"] == "alice@restaurant.com" for c in item["collaborators"])
        assert is_primary or is_collab


# =========================================================================
# 2. ALERT ACKNOWLEDGMENT & SUPPRESSION (Goal 10)
# =========================================================================

def test_acknowledge_slow_order_and_suppression(
    client: TestClient,
    alice_token: str,
    manager_token: str
):
    """
    Goal 10: Acknowledging a slow order dismisses it and suppresses it from the active list.
    """
    # Create an order backdated by 25 minutes directly in DB
    db: Session = SessionLocal()
    try:
        alice_profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"}).json()
        now = datetime.now(timezone.utc)
        slow_order = Order(
            table_number=77,
            status="placed",
            primary_waiter_id=uuid.UUID(alice_profile["id"]),
            is_archived=False,
            created_at=now - timedelta(minutes=25),
            updated_at=now - timedelta(minutes=25),
        )
        db.add(slow_order)
        db.commit()
        db.refresh(slow_order)
        order_id = str(slow_order.id)
    finally:
        db.close()

    # 1. Verify it appears in active slow orders
    alerts_before = client.get("/api/alerts", headers={"Authorization": f"Bearer {alice_token}"}).json()
    assert any(a["order_id"] == order_id for a in alerts_before)

    # 2. Alice acknowledges the alert
    ack_resp = client.post(
        f"/api/alerts/{order_id}/acknowledge",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()
    assert ack_data["order_id"] == order_id
    assert ack_data["acknowledged_by"]["email"] == "alice@restaurant.com"

    # 3. Verify it is now SUPPRESSED from the active alerts list
    alerts_after = client.get("/api/alerts", headers={"Authorization": f"Bearer {alice_token}"}).json()
    assert not any(a["order_id"] == order_id for a in alerts_after)


# =========================================================================
# 3. RE-ALERT AFTER REAPPEARANCE INTERVAL (Goal 10)
# =========================================================================

def test_reappearance_after_reappear_interval(
    client: TestClient,
    alice_token: str
):
    """
    Goal 10: Re-alert behavior when reappear window expires while order is still open.
    """
    db: Session = SessionLocal()
    try:
        alice_profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"}).json()
        now = datetime.now(timezone.utc)
        order = Order(
            table_number=88,
            status="accepted",
            primary_waiter_id=uuid.UUID(alice_profile["id"]),
            is_archived=False,
            created_at=now - timedelta(minutes=30),
            updated_at=now - timedelta(minutes=30),
        )
        db.add(order)
        db.flush()

        # Add an acknowledgment from 15 minutes ago (exceeding 10m reappear interval)
        ack = AlertAcknowledgment(
            order_id=order.id,
            acknowledged_by=uuid.UUID(alice_profile["id"]),
            acknowledged_at=now - timedelta(minutes=15),
        )
        db.add(ack)
        db.commit()
        order_id = str(order.id)
    finally:
        db.close()

    # Fetch alerts: order must reappear with is_reappeared=True
    alerts = client.get("/api/alerts", headers={"Authorization": f"Bearer {alice_token}"}).json()
    reappeared_item = next((a for a in alerts if a["order_id"] == order_id), None)
    assert reappeared_item is not None
    assert reappeared_item["is_reappeared"] is True
    assert reappeared_item["last_acknowledged_at"] is not None


# =========================================================================
# 4. ORDER CLOSURE REMOVES ALERT (Goal 10)
# =========================================================================

def test_serving_order_removes_slow_alert(
    client: TestClient,
    alice_token: str
):
    """Once an order is served or closed, it immediately disappears from slow alerts."""
    db: Session = SessionLocal()
    try:
        alice_profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"}).json()
        now = datetime.now(timezone.utc)
        order = Order(
            table_number=91,
            status="ready",
            primary_waiter_id=uuid.UUID(alice_profile["id"]),
            is_archived=False,
            created_at=now - timedelta(minutes=22),
            updated_at=now - timedelta(minutes=2),
        )
        db.add(order)
        db.commit()
        order_id = str(order.id)
    finally:
        db.close()

    # Verify it is in active slow alerts
    alerts_open = client.get("/api/alerts", headers={"Authorization": f"Bearer {alice_token}"}).json()
    assert any(a["order_id"] == order_id for a in alerts_open)

    # Transition order to served
    serve_resp = client.patch(
        f"/api/orders/{order_id}/status",
        json={"status": "served"},
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert serve_resp.status_code == 200

    # Verify it is no longer in active slow alerts
    alerts_served = client.get("/api/alerts", headers={"Authorization": f"Bearer {alice_token}"}).json()
    assert not any(a["order_id"] == order_id for a in alerts_served)


# =========================================================================
# 5. AUTHORIZATION SECURITY CHECKS
# =========================================================================

def test_unauthorized_waiter_cannot_acknowledge_other_orders(
    client: TestClient,
    alice_token: str,
    bob_token: str
):
    """A waiter cannot acknowledge an alert on an order they don't work on."""
    db: Session = SessionLocal()
    try:
        alice_profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {alice_token}"}).json()
        now = datetime.now(timezone.utc)
        order = Order(
            table_number=92,
            status="placed",
            primary_waiter_id=uuid.UUID(alice_profile["id"]),
            is_archived=False,
            created_at=now - timedelta(minutes=25),
        )
        db.add(order)
        db.commit()
        order_id = str(order.id)
    finally:
        db.close()

    # Bob attempts to acknowledge Alice's order -> 403 Forbidden
    resp = client.post(
        f"/api/alerts/{order_id}/acknowledge",
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    assert resp.status_code == 403


def test_unauthenticated_alerts_rejected(client: TestClient):
    """Unauthenticated requests to alerts endpoints receive 401."""
    assert client.get("/api/alerts/badge").status_code == 401
    assert client.get("/api/alerts").status_code == 401
    assert client.post(f"/api/alerts/{uuid.uuid4()}/acknowledge").status_code == 401
