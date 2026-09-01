/**
 * Restaurant Orders - Common Utilities & UI Helpers
 */

const utils = {
    /**
     * Format decimal or number into USD currency string ($xx.xx)
     */
    formatCurrency(amount) {
        const num = parseFloat(amount) || 0;
        return `$${num.toFixed(2)}`;
    },

    /**
     * Format ISO datetime into localized human readable string
     */
    formatDateTime(isoString) {
        if (!isoString) return "-";
        const d = new Date(isoString);
        return d.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        });
    },

    /**
     * Format date only (YYYY-MM-DD)
     */
    formatDateOnly(isoString) {
        if (!isoString) return "-";
        const d = new Date(isoString);
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric"
        });
    },

    /**
     * Format duration into 'Xm' or 'Xh Ym'
     */
    formatMinutes(minutes) {
        if (!minutes || minutes < 1) return "< 1m";
        if (minutes < 60) return `${minutes}m`;
        const hrs = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${hrs}h ${mins}m`;
    },

    /**
     * Render status badge HTML with appropriate semantic color
     */
    renderStatusBadge(status) {
        const s = (status || "").toLowerCase();
        const colors = {
            placed: "badge-placed",
            accepted: "badge-accepted",
            preparing: "badge-preparing",
            ready: "badge-ready",
            served: "badge-served",
            cancelled: "badge-cancelled"
        };
        const cls = colors[s] || "badge-default";
        const label = s.charAt(0).toUpperCase() + s.slice(1);
        return `<span class="badge ${cls}">${label}</span>`;
    },

    /**
     * Display a floating toast notification
     */
    showToast(message, type = "info") {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.className = "toast-container";
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">${message}</div>
            <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
        `;
        container.appendChild(toast);

        setTimeout(() => {
            if (toast.parentElement) {
                toast.classList.add("toast-fadeout");
                setTimeout(() => toast.remove(), 300);
            }
        }, 4000);
    },

    /**
     * Modal Helpers
     */
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add("active");
            document.body.classList.add("modal-open");
        }
    },

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove("active");
            document.body.classList.remove("modal-open");
        }
    },

    /**
     * Setup Header Navigation & Role-Aware Visibility
     */
    async setupNavigation() {
        const user = window.api.getCurrentUser();
        if (!user && !window.location.pathname.endsWith("login.html")) {
            window.location.href = "login.html";
            return;
        }

        // Update user badge in navbar
        const userDisplay = document.getElementById("nav-user-info");
        if (userDisplay && user) {
            userDisplay.innerHTML = `
                <span class="user-avatar">${user.name.charAt(0)}</span>
                <span class="user-details">
                    <strong class="user-name">${user.name}</strong>
                    <span class="user-role badge badge-role-${user.role}">${user.role}</span>
                </span>
            `;
        }

        // Manager-only nav items
        const managerLinks = document.querySelectorAll(".manager-only");
        managerLinks.forEach(el => {
            if (user && user.role === "manager") {
                el.style.display = "";
            } else {
                el.style.display = "none";
            }
        });

        // Setup Logout Button
        const logoutBtn = document.getElementById("nav-logout-btn");
        if (logoutBtn) {
            logoutBtn.onclick = (e) => {
                e.preventDefault();
                window.auth.logout();
            };
        }

        // Fetch Alert Badge Count
        await this.updateAlertBadge();

        // Poll badge every 30 seconds
        if (!window._alertPollingInterval) {
            window._alertPollingInterval = setInterval(() => this.updateAlertBadge(), 30000);
        }
    },

    /**
     * Fetch real-time slow-order count from backend and update badge
     */
    async updateAlertBadge() {
        if (!window.api.getToken()) return;
        try {
            const data = await window.api.get("/api/alerts/badge");
            const badge = document.getElementById("nav-alert-badge");
            if (badge) {
                const count = data.slow_orders_count || 0;
                badge.textContent = count;
                badge.style.display = count > 0 ? "inline-flex" : "none";
            }
        } catch (err) {
            // Ignore background badge fetch errors
        }
    }
};

window.utils = utils;
