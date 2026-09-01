/**
 * Restaurant Orders - Reusable Fetch API Client Layer
 */

const API_BASE_URL = window.location.origin.includes(":5500") || window.location.origin.includes(":3000") || window.location.origin.includes("127.0.0.1:5500")
    ? "http://localhost:8000"
    : "";

class ApiClient {
    constructor() {
        this.baseUrl = API_BASE_URL;
    }

    getToken() {
        return localStorage.getItem("auth_token");
    }

    setToken(token) {
        localStorage.setItem("auth_token", token);
    }

    removeToken() {
        localStorage.removeItem("auth_token");
        localStorage.removeItem("user_profile");
    }

    getCurrentUser() {
        const userJson = localStorage.getItem("user_profile");
        return userJson ? JSON.parse(userJson) : null;
    }

    setCurrentUser(user) {
        localStorage.setItem("user_profile", JSON.stringify(user));
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint.startsWith("/") ? endpoint : "/" + endpoint}`;
        const headers = {
            "Accept": "application/json",
            ...(options.headers || {})
        };

        const token = this.getToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        if (options.body && !(options.body instanceof FormData) && typeof options.body === "object") {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, { ...options, headers });

            // Handle 401 Unauthorized
            if (response.status === 401) {
                this.removeToken();
                if (!window.location.pathname.endsWith("login.html")) {
                    window.location.href = "login.html";
                }
                throw new Error("Session expired or invalid credentials. Please log in again.");
            }

            // Handle 403 Forbidden
            if (response.status === 403) {
                const errData = await response.json().catch(() => ({}));
                const msg = errData.detail || "You do not have permission to perform this action.";
                throw new Error(`Permission Denied: ${msg}`);
            }

            // Handle File Download (CSV)
            const contentType = response.headers.get("Content-Type") || "";
            if (contentType.includes("text/csv")) {
                const blob = await response.blob();
                return { isBlob: true, blob, headers: response.headers };
            }

            // Handle JSON Error Responses (400, 404, 422, 500)
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                let errorMsg = errorData.detail || `Request failed with status ${response.status}`;
                if (Array.isArray(errorData.detail)) {
                    // Pydantic validation error array
                    errorMsg = errorData.detail.map(e => `${e.loc?.join(".") || "field"}: ${e.msg}`).join(", ");
                }
                throw new Error(errorMsg);
            }

            // Return JSON payload if body exists
            if (response.status === 204) return null;
            return await response.json();
        } catch (err) {
            console.error(`[API Error] ${endpoint}:`, err);
            throw err;
        }
    }

    get(endpoint, params = {}) {
        const query = new URLSearchParams();
        for (const [key, value] of Object.entries(params)) {
            if (value !== null && value !== undefined && value !== "") {
                query.append(key, value);
            }
        }
        const queryString = query.toString();
        const fullUrl = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(fullUrl, { method: "GET" });
    }

    post(endpoint, body = {}) {
        return this.request(endpoint, { method: "POST", body });
    }

    put(endpoint, body = {}) {
        return this.request(endpoint, { method: "PUT", body });
    }

    patch(endpoint, body = {}) {
        return this.request(endpoint, { method: "PATCH", body });
    }

    delete(endpoint) {
        return this.request(endpoint, { method: "DELETE" });
    }
}

const api = new ApiClient();
window.api = api;
