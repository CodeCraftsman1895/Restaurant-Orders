/**
 * Restaurant Orders - Authentication Module
 */

const auth = {
    async login(email, password) {
        try {
            // 1. Submit credentials to get JWT token
            const tokenData = await window.api.post("/api/auth/login", { email, password });
            window.api.setToken(tokenData.access_token);

            // 2. Fetch authenticated user profile
            const profile = await window.api.get("/api/auth/me");
            window.api.setCurrentUser(profile);

            window.utils.showToast(`Welcome back, ${profile.name}!`, "success");

            // Redirect based on role or to orders
            setTimeout(() => {
                if (profile.role === "manager") {
                    window.location.href = "dashboard.html";
                } else {
                    window.location.href = "orders.html";
                }
            }, 600);

            return profile;
        } catch (err) {
            window.utils.showToast(err.message || "Login failed. Please check your credentials.", "error");
            throw err;
        }
    },

    logout() {
        window.api.removeToken();
        window.utils.showToast("Logged out successfully.", "info");
        setTimeout(() => {
            window.location.href = "login.html";
        }, 400);
    },

    requireAuth() {
        const token = window.api.getToken();
        const user = window.api.getCurrentUser();
        if (!token || !user) {
            window.location.href = "login.html";
            return false;
        }
        return true;
    },

    requireManager() {
        if (!this.requireAuth()) return false;
        const user = window.api.getCurrentUser();
        if (user.role !== "manager") {
            window.utils.showToast("Manager access required.", "error");
            setTimeout(() => {
                window.location.href = "orders.html";
            }, 800);
            return false;
        }
        return true;
    }
};

window.auth = auth;
