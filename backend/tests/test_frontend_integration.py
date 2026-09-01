from fastapi.testclient import TestClient


def test_frontend_pages_served_successfully(client: TestClient):
    """Verify that all frontend static HTML pages are properly served."""
    pages = [
        "/index.html",
        "/login.html",
        "/orders.html",
        "/order-details.html",
        "/menu.html",
        "/alerts.html",
        "/dashboard.html",
    ]
    for page in pages:
        response = client.get(page)
        assert response.status_code == 200, f"Failed to serve {page}"
        assert "<!DOCTYPE html>" in response.text or "<html" in response.text


def test_frontend_assets_served_successfully(client: TestClient):
    """Verify that frontend CSS and JS assets are properly served."""
    assets = [
        "/css/style.css",
        "/css/orders.css",
        "/css/menu.css",
        "/css/alerts.css",
        "/css/dashboard.css",
        "/js/api.js",
        "/js/utils.js",
        "/js/auth.js",
        "/js/orders.js",
        "/js/order-details.js",
        "/js/menu.js",
        "/js/alerts.js",
        "/js/dashboard.js",
    ]
    for asset in assets:
        response = client.get(asset)
        assert response.status_code == 200, f"Failed to serve asset {asset}"
        assert len(response.text) > 10
