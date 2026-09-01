import csv
import io
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
# 1. DASHBOARD METRICS & REVENUE TESTS (Goal 8)
# =========================================================================

def test_get_dashboard_metrics_manager_success(client: TestClient, manager_token: str):
    """
    Goal 8: Manager's dashboard returns headline stats:
    - Open orders
    - Today's revenue
    - Breakdown by status and by waiter
    - 14-day served orders chart data
    """
    response = client.get(
        "/api/dashboard",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    data = response.json()

    assert "open_orders_count" in data
    assert "today_revenue" in data
    assert "status_breakdown" in data
    assert "waiter_breakdown" in data
    assert "last_14_days_chart" in data

    assert data["open_orders_count"] >= 0
    assert float(data["today_revenue"]) >= 0

    # 14 days chart validation: exactly 14 daily data points
    assert len(data["last_14_days_chart"]) == 14
    for day in data["last_14_days_chart"]:
        assert "date" in day
        assert "served_orders_count" in day
        assert "revenue" in day
        assert day["served_orders_count"] >= 0

    # Status breakdown check
    statuses = [s["status"] for s in data["status_breakdown"]]
    for expected in ("placed", "accepted", "preparing", "ready", "served", "cancelled"):
        assert expected in statuses

    # Waiter breakdown check
    assert len(data["waiter_breakdown"]) >= 3
    for w in data["waiter_breakdown"]:
        assert "waiter_name" in w
        assert "order_count" in w
        assert "revenue" in w


def test_get_dashboard_metrics_waiter_forbidden(client: TestClient, waiter_token: str):
    """Waiters are forbidden from viewing manager dashboard metrics."""
    response = client.get(
        "/api/dashboard",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 403


def test_get_dashboard_unauthenticated_rejected(client: TestClient):
    """Unauthenticated requests to dashboard return 401."""
    response = client.get("/api/dashboard")
    assert response.status_code == 401


# =========================================================================
# 2. CSV EXPORT TESTS (Goals 1 & 8)
# =========================================================================

def test_export_orders_csv_manager_success(client: TestClient, manager_token: str):
    """
    Goals 1 & 8: Manager can download a CSV of orders.
    Verifies valid CSV structure, headers, quoting, and row contents.
    """
    response = client.get(
        "/api/dashboard/export",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["Content-Type"]
    assert "attachment; filename=" in response.headers["Content-Disposition"]

    content = response.text
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    # Check header
    header = rows[0]
    expected_headers = [
        "Order ID",
        "Table Number",
        "Status",
        "Primary Waiter",
        "Collaborators",
        "Lines Count",
        "Total ($)",
        "Is Archived",
        "Created At",
        "Updated At",
    ]
    assert header == expected_headers

    # Check data rows exist
    assert len(rows) > 1
    sample_row = rows[1]
    assert len(sample_row) == len(expected_headers)


def test_export_orders_csv_with_status_filter(client: TestClient, manager_token: str):
    """
    Goal 8: CSV export covers the same filtered slice of orders shown on the page.
    """
    response = client.get(
        "/api/dashboard/export?status=served",
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200
    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)

    # All data rows should have status 'served'
    for row in rows[1:]:
        assert row[2] == "served"


def test_export_orders_csv_waiter_forbidden(client: TestClient, waiter_token: str):
    """Waiters are forbidden from exporting CSV (Goal 1)."""
    response = client.get(
        "/api/dashboard/export",
        headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert response.status_code == 403
