/**
 * Restaurant Orders - Slow-Order Alerts Controller
 */

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.auth.requireAuth()) return;
    await window.utils.setupNavigation();

    document.getElementById("refresh-alerts-btn").addEventListener("click", () => loadAlerts());

    // Initial Load
    await loadAlerts();
});

async function loadAlerts() {
    const container = document.getElementById("alerts-container");
    container.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div class="loading-spinner"></div>
            <p style="margin-top: 10px; color: var(--text-muted);">Checking slow-order alerts...</p>
        </div>
    `;

    try {
        const alerts = await window.api.get("/api/alerts");
        renderAlerts(alerts);
        await window.utils.updateAlertBadge();
    } catch (err) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--danger);">
                <p>${err.message || "Failed to load alerts."}</p>
            </div>
        `;
    }
}

function renderAlerts(alerts) {
    const container = document.getElementById("alerts-container");

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div class="card" style="text-align: center; padding: 48px 24px;">
                <div class="empty-state-icon" style="color: var(--success); font-size: 3rem;">✓</div>
                <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main);">All Caught Up!</h3>
                <p style="color: var(--text-muted); margin-top: 6px;">No orders are currently running past the alert threshold.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = alerts.map(a => {
        const reappearedBadge = a.is_reappeared ? `
            <span class="badge" style="background-color: #ffe4e6; color: #9f1239; border: 1px solid #fecdd3;">
                ⚠️ Reappeared Alert (Unresolved)
            </span>
        ` : '';

        const collabNames = a.collaborators && a.collaborators.length > 0
            ? a.collaborators.map(c => c.name).join(", ")
            : "None";

        return `
            <div class="alert-card ${a.is_reappeared ? 'reappeared' : ''}" id="alert-card-${a.order_id}">
                <div>
                    <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                        <h2 style="font-size: 1.3rem; font-weight: 700;">Table ${a.table_number}</h2>
                        ${window.utils.renderStatusBadge(a.status)}
                        <span class="alert-duration-badge">⏱️ Open for ${window.utils.formatMinutes(a.minutes_open)}</span>
                        ${reappearedBadge}
                    </div>
                    <div class="alert-meta">
                        <span><strong>Primary Waiter:</strong> ${a.primary_waiter?.name || 'Unassigned'}</span>
                        <span><strong>Collaborators:</strong> ${collabNames}</span>
                        <span><strong>Placed:</strong> ${window.utils.formatDateTime(a.created_at)}</span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <button class="btn btn-secondary btn-sm" onclick="acknowledgeAlert('${a.order_id}')">
                        ✓ Acknowledge / Dismiss
                    </button>
                    <a href="order-details.html?id=${a.order_id}" class="btn btn-primary btn-sm">
                        View Order &rarr;
                    </a>
                </div>
            </div>
        `;
    }).join("");
}

async function acknowledgeAlert(orderId) {
    try {
        await window.api.post(`/api/alerts/${orderId}/acknowledge`);
        window.utils.showToast("Alert acknowledged. Suppressed from active queue.", "info");

        // Remove card visually
        const card = document.getElementById(`alert-card-${orderId}`);
        if (card) {
            card.style.opacity = "0.5";
            setTimeout(() => loadAlerts(), 300);
        } else {
            loadAlerts();
        }
    } catch (err) {
        window.utils.showToast(err.message || "Failed to acknowledge alert.", "error");
    }
}
