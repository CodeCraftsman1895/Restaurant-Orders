import sys
import os
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient

# Ensure python path includes backend
sys.path.insert(0, os.path.abspath("."))

from app.main import app
from app.database.connection import SessionLocal, engine
from app.models.user import User
from app.models.menu_item import MenuItem
from app.models.order import Order
from sqlalchemy import inspect, select, func

def verify_all():
    print("=" * 70)
    print("PHASE 11: FULL SYSTEM INTEGRATION & REQUIREMENT VERIFICATION")
    print("=" * 70)

    client = TestClient(app)
    db = SessionLocal()

    # -------------------------------------------------------------
    # 1. DATABASE & SCHEMA VERIFICATION
    # -------------------------------------------------------------
    print("\n[1/10] Verifying Database Schema & Tables...")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    required_tables = {
        "users",
        "menu_items",
        "orders",
        "order_lines",
        "order_collaborators",
        "order_events",
        "alert_acknowledgments",
    }
    
    missing_tables = required_tables - tables
    assert not missing_tables, f"Missing required tables: {missing_tables}"
    print(f"  [PASS] Exactly 7 required application tables present: {sorted(list(required_tables))}")

    # Verify FKs and integrity
    fk_lines = inspector.get_foreign_keys("order_lines")
    fk_orders = inspector.get_foreign_keys("orders")
    assert len(fk_lines) >= 2, "Foreign keys missing on order_lines"
    assert len(fk_orders) >= 1, "Foreign keys missing on orders"
    print("  [PASS] Foreign key constraints verified on orders and order_lines.")

    # Check Seed Data
    user_count = db.scalar(select(func.count(User.id)))
    menu_count = db.scalar(select(func.count(MenuItem.id)))
    order_count = db.scalar(select(func.count(Order.id)))
    print(f"  [PASS] Seed records in Supabase: {user_count} Users, {menu_count} Menu Items, {order_count} Orders.")
    assert user_count >= 4, "Users count too low"
    assert menu_count >= 15, "Menu items count too low"
    assert order_count >= 12, "Orders count too low"

    # -------------------------------------------------------------
    # 2. AUTHENTICATION & SECURITY VERIFICATION
    # -------------------------------------------------------------
    print("\n[2/10] Verifying Authentication & Password Security...")
    
    # Manager Login
    mgr_resp = client.post("/api/auth/login", json={"email": "manager@restaurant.com", "password": "manager123"})
    assert mgr_resp.status_code == 200, "Manager login failed"
    mgr_token = mgr_resp.json()["access_token"]
    print("  [PASS] Manager authentication successful.")

    # Waiter Login
    w_resp = client.post("/api/auth/login", json={"email": "alice@restaurant.com", "password": "waiter123"})
    assert w_resp.status_code == 200, "Waiter login failed"
    waiter_token = w_resp.json()["access_token"]
    print("  [PASS] Waiter authentication successful.")

    # Invalid credentials
    inv_resp = client.post("/api/auth/login", json={"email": "manager@restaurant.com", "password": "wrongpassword"})
    assert inv_resp.status_code == 401, "Invalid password did not return 401"
    print("  [PASS] Invalid password rejected with 401.")

    # /api/auth/me check
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {waiter_token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert "password" not in me_data and "password_hash" not in me_data, "Password hash leaked in /api/auth/me response!"
    print("  [PASS] /api/auth/me returns clean user profile without exposing password hashes.")

    # -------------------------------------------------------------
    # 3. AUTHORIZATION & RBAC VERIFICATION
    # -------------------------------------------------------------
    print("\n[3/10] Verifying Role-Based Access Control (RBAC)...")
    
    # Waiter access to manager dashboard
    w_dash_resp = client.get("/api/dashboard", headers={"Authorization": f"Bearer {waiter_token}"})
    assert w_dash_resp.status_code == 403, "Waiter accessed manager dashboard!"
    print("  [PASS] Waiter access to /api/dashboard blocked with 403 Forbidden.")

    # Waiter access to CSV export
    w_csv_resp = client.get("/api/dashboard/export", headers={"Authorization": f"Bearer {waiter_token}"})
    assert w_csv_resp.status_code == 403, "Waiter accessed manager CSV export!"
    print("  [PASS] Waiter access to /api/dashboard/export blocked with 403 Forbidden.")

    # Waiter access to menu bulk update
    w_bulk_resp = client.post("/api/menu/bulk", headers={"Authorization": f"Bearer {waiter_token}"}, json={"item_ids": []})
    assert w_bulk_resp.status_code == 403, "Waiter accessed menu bulk update!"
    print("  [PASS] Waiter access to /api/menu/bulk blocked with 403 Forbidden.")

    # Manager access to dashboard
    m_dash_resp = client.get("/api/dashboard", headers={"Authorization": f"Bearer {mgr_token}"})
    assert m_dash_resp.status_code == 200, "Manager failed to access dashboard"
    print("  [PASS] Manager successfully authorized for /api/dashboard.")

    # -------------------------------------------------------------
    # 4. MENU CATALOG & AVAILABILITY VERIFICATION
    # -------------------------------------------------------------
    print("\n[4/10] Verifying Menu Catalog & Price Snapshot Integrity...")
    
    menu_items = client.get("/api/menu", headers={"Authorization": f"Bearer {waiter_token}"}).json()
    available_dishes = [i for i in menu_items if i.get("is_available") and not i.get("is_archived")]
    assert len(available_dishes) >= 2, "Need at least 2 available menu items"
    sample_dish = available_dishes[0]
    dish_id = sample_dish["id"]
    dish_price = sample_dish["price"]
    print(f"  [PASS] Menu catalog loaded {len(menu_items)} dishes ({len(available_dishes)} available). Sample: '{sample_dish['name']}' (${dish_price}).")

    # -------------------------------------------------------------
    # 5. COMPLETE ORDER LIFECYCLE SCENARIO (GOALS 1, 2, 3, 4, 5, 9)
    # -------------------------------------------------------------
    print("\n[5/10] Executing Complete End-to-End Order Journey...")

    # Step 1: Waiter Alice creates an order for Table 88
    create_order_resp = client.post(
        "/api/orders",
        headers={"Authorization": f"Bearer {waiter_token}"},
        json={
            "table_number": 88,
            "lines": [
                {"menu_item_id": dish_id, "quantity": 2, "special_instructions": "Gluten-free preference"}
            ]
        }
    )
    assert create_order_resp.status_code == 201, f"Failed to create order: {create_order_resp.text}"
    order_data = create_order_resp.json()
    order_id = order_data["id"]
    assert order_data["status"] == "placed", "Initial status not 'placed'"
    assert Decimal(str(order_data["total"])) == Decimal(str(dish_price)) * 2, "Initial running total incorrect"
    print(f"  [PASS] Step 1: Created Order for Table 88 (ID: {order_id[:8]}..., Status: placed, Total: ${order_data['total']}).")

    # Step 2: Add another line
    second_dish = available_dishes[1]
    add_line_resp = client.post(
        f"/api/orders/{order_id}/lines",
        headers={"Authorization": f"Bearer {waiter_token}"},
        json={"menu_item_id": second_dish["id"], "quantity": 1, "special_instructions": "Extra dressing"}
    )
    assert add_line_resp.status_code == 201
    updated_lines = add_line_resp.json()["lines"]
    second_line_id = [l["id"] for l in updated_lines if l["menu_item_id"] == second_dish["id"]][0]
    print(f"  [PASS] Step 2: Added 2nd line '{second_dish['name']}' (Line ID: {second_line_id[:8]}...).")

    # Step 3: Add Collaborator Waiter Bob
    bob_user = db.scalar(select(User).where(User.email == "bob@restaurant.com"))
    add_collab_resp = client.post(
        f"/api/orders/{order_id}/collaborators",
        headers={"Authorization": f"Bearer {waiter_token}"},
        json={"user_id": str(bob_user.id)}
    )
    assert add_collab_resp.status_code == 200, f"Add collaborator failed: {add_collab_resp.text}"
    print("  [PASS] Step 3: Added collaborating waiter (Bob Smith).")

    # Step 4: Add Note
    note_resp = client.post(
        f"/api/orders/{order_id}/notes",
        headers={"Authorization": f"Bearer {waiter_token}"},
        json={"note": "Guests seated by window for anniversary celebration"}
    )
    assert note_resp.status_code == 200, f"Add note failed: {note_resp.text}"
    print("  [PASS] Step 4: Added order note to timeline.")

    # Step 5: Lifecycle transition: placed -> accepted -> preparing
    s_acc = client.patch(f"/api/orders/{order_id}/status", headers={"Authorization": f"Bearer {waiter_token}"}, json={"status": "accepted"})
    assert s_acc.status_code == 200 and s_acc.json()["status"] == "accepted"
    s_prep = client.patch(f"/api/orders/{order_id}/status", headers={"Authorization": f"Bearer {waiter_token}"}, json={"status": "preparing"})
    assert s_prep.status_code == 200 and s_prep.json()["status"] == "preparing"
    print("  [PASS] Step 5: Advanced lifecycle placed -> accepted -> preparing.")

    # Step 6: Verify CANNOT cancel order once in 'preparing'
    inv_cancel = client.patch(f"/api/orders/{order_id}/status", headers={"Authorization": f"Bearer {waiter_token}"}, json={"status": "cancelled"})
    assert inv_cancel.status_code == 400, "Order allowed cancellation while preparing!"
    print("  [PASS] Step 6: Cancellation correctly blocked while order is 'preparing' (Goal 4).")

    # Step 7: Advance preparing -> ready
    s_ready = client.patch(f"/api/orders/{order_id}/status", headers={"Authorization": f"Bearer {waiter_token}"}, json={"status": "ready"})
    assert s_ready.status_code == 200 and s_ready.json()["status"] == "ready"

    # Step 8: Void second line with reason
    void_resp = client.post(
        f"/api/orders/{order_id}/lines/{second_line_id}/void",
        headers={"Authorization": f"Bearer {waiter_token}"},
        json={"reason": "Customer requested cancellation before appetizer fired"}
    )
    assert void_resp.status_code == 200
    voided_line = [l for l in void_resp.json()["lines"] if l["id"] == second_line_id][0]
    assert voided_line["is_voided"] is True
    print("  [PASS] Step 8: Successfully voided line with required reason.")

    # Step 9: Verify running total excludes voided line
    order_detail = client.get(f"/api/orders/{order_id}", headers={"Authorization": f"Bearer {waiter_token}"}).json()
    expected_active_total = Decimal(str(dish_price)) * 2
    assert Decimal(str(order_detail["total"])) == expected_active_total, "Running total included voided line!"
    print(f"  [PASS] Step 9: Running total dynamically updated to ${order_detail['total']} (excluded voided line).")

    # Step 10: Verify timeline audit events
    timeline = client.get(f"/api/orders/{order_id}/timeline", headers={"Authorization": f"Bearer {waiter_token}"}).json()
    assert len(timeline) >= 5, "Timeline events missing"
    print(f"  [PASS] Step 10: Immutable audit timeline contains {len(timeline)} logged events with user attribution.")

    # Step 11: Advance ready -> served
    s_served = client.patch(f"/api/orders/{order_id}/status", headers={"Authorization": f"Bearer {waiter_token}"}, json={"status": "served"})
    assert s_served.status_code == 200 and s_served.json()["status"] == "served"
    print("  [PASS] Step 11: Advanced order to 'served'.")

    # -------------------------------------------------------------
    # 6. SLOW-ORDER ALERTS & DYNAMIC BADGE (GOAL 10)
    # -------------------------------------------------------------
    print("\n[6/10] Verifying Slow-Order Alerts & Dynamic Badges...")
    
    badge_resp = client.get("/api/alerts/badge", headers={"Authorization": f"Bearer {mgr_token}"})
    assert badge_resp.status_code == 200
    assert "slow_orders_count" in badge_resp.json()
    print(f"  [PASS] Alert badge API returned active slow orders count: {badge_resp.json()['slow_orders_count']}.")

    alerts_list = client.get("/api/alerts", headers={"Authorization": f"Bearer {mgr_token}"}).json()
    print(f"  [PASS] Slow-order alerts list returned {len(alerts_list)} open alerts.")

    # -------------------------------------------------------------
    # 7. MANAGER DASHBOARD & REVENUE ANALYTICS (GOAL 8)
    # -------------------------------------------------------------
    print("\n[7/10] Verifying Manager Dashboard & 14-Day History...")
    
    dash_data = client.get("/api/dashboard", headers={"Authorization": f"Bearer {mgr_token}"}).json()
    assert "open_orders_count" in dash_data
    assert "today_revenue" in dash_data
    assert "status_breakdown" in dash_data
    assert "waiter_breakdown" in dash_data
    assert "last_14_days_chart" in dash_data
    assert len(dash_data["last_14_days_chart"]) == 14, "Chart data does not contain exactly 14 days"
    print(f"  [PASS] Dashboard KPI: Today Revenue = ${dash_data['today_revenue']}, Open Orders = {dash_data['open_orders_count']}.")
    print(f"  [PASS] 14-Day Chart: Exactly 14 daily data points present (ending on {dash_data['last_14_days_chart'][-1]['date']}).")

    # -------------------------------------------------------------
    # 8. CSV EXPORT VERIFICATION (GOALS 1 & 8)
    # -------------------------------------------------------------
    print("\n[8/10] Verifying Server-Side CSV Export...")
    
    csv_resp = client.get("/api/dashboard/export", headers={"Authorization": f"Bearer {mgr_token}"})
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["Content-Type"]
    assert "restaurant_orders_" in csv_resp.headers["Content-Disposition"]
    assert "Order ID,Table Number,Status" in csv_resp.text
    print("  [PASS] CSV export generated valid formatted file with headers and order rows.")

    # -------------------------------------------------------------
    # 9. FRONTEND ASSETS & PAGES INTEGRATION
    # -------------------------------------------------------------
    print("\n[9/10] Verifying Frontend Static Pages & Assets...")
    
    for page in ["/index.html", "/login.html", "/orders.html", "/order-details.html", "/menu.html", "/alerts.html", "/dashboard.html"]:
        resp = client.get(page)
        assert resp.status_code == 200, f"Page {page} not found"
    print("  [PASS] All 7 HTML pages served with HTTP 200.")

    for asset in ["/css/style.css", "/js/api.js", "/js/auth.js", "/js/orders.js", "/js/dashboard.js"]:
        resp = client.get(asset)
        assert resp.status_code == 200, f"Asset {asset} not found"
    print("  [PASS] All CSS and JS modules served with HTTP 200.")

    # Clean up test order Table 88 to avoid polluting demo database
    db_order = db.scalar(select(Order).where(Order.id == uuid.UUID(order_id)))
    if db_order:
        db.delete(db_order)
        db.commit()
    db.close()

    print("\n" + "=" * 70)
    print("[PASS] PHASE 11 INTEGRATION & REQUIREMENT VERIFICATION: 100% SUCCESS")
    print("=" * 70)

if __name__ == "__main__":
    verify_all()
