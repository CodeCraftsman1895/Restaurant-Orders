/**
 * Restaurant Orders - Order Details & Actions Controller
 */

let currentOrderId = null;
let currentOrder = null;
let availableMenuItems = [];
let availableWaiters = [];

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.auth.requireAuth()) return;
    await window.utils.setupNavigation();

    const urlParams = new URLSearchParams(window.location.search);
    currentOrderId = urlParams.get("id");

    if (!currentOrderId) {
        window.utils.showToast("No order ID specified.", "error");
        setTimeout(() => window.location.href = "orders.html", 1000);
        return;
    }

    // Setup Event Listeners
    document.getElementById("refresh-detail-btn").addEventListener("click", () => loadOrderDetails());
    document.getElementById("archive-order-btn").addEventListener("click", handleArchiveToggle);
    document.getElementById("open-add-line-btn").addEventListener("click", openAddLineModal);
    document.getElementById("add-line-form").addEventListener("submit", handleAddLineSubmit);
    document.getElementById("void-line-form").addEventListener("submit", handleVoidLineSubmit);
    document.getElementById("open-add-collab-btn").addEventListener("click", openAddCollabModal);
    document.getElementById("add-collab-form").addEventListener("submit", handleAddCollabSubmit);
    document.getElementById("open-add-note-btn").addEventListener("click", () => {
        document.getElementById("add-note-form").reset();
        window.utils.openModal("add-note-modal");
    });
    document.getElementById("add-note-form").addEventListener("submit", handleAddNoteSubmit);

    // Initial Data Fetch
    await Promise.all([
        loadMenuItems(),
        loadOrderDetails(),
        loadTimeline(),
    ]);
});

async function loadMenuItems() {
    try {
        availableMenuItems = await window.api.get("/api/menu", { only_available: true });
    } catch (err) {
        console.error("Failed to load dishes:", err);
    }
}

async function loadOrderDetails() {
    try {
        currentOrder = await window.api.get(`/api/orders/${currentOrderId}`);
        renderOrderHeader(currentOrder);
        renderOrderLines(currentOrder.lines);
        renderCollaborators(currentOrder.collaborators);
        renderWorkflowButtons(currentOrder);
    } catch (err) {
        window.utils.showToast(err.message || "Failed to load order details.", "error");
    }
}

async function loadTimeline() {
    try {
        const events = await window.api.get(`/api/orders/${currentOrderId}/timeline`);
        renderTimeline(events);
    } catch (err) {
        console.error("Failed to load timeline:", err);
    }
}

function renderOrderHeader(order) {
    document.getElementById("order-title").textContent = `Order for Table ${order.table_number}`;
    document.getElementById("table-number-display").textContent = `Table ${order.table_number}`;
    document.getElementById("order-status-badge").innerHTML = window.utils.renderStatusBadge(order.status);
    document.getElementById("order-total-header").textContent = window.utils.formatCurrency(order.total);

    document.getElementById("primary-waiter-name").textContent = order.primary_waiter ? order.primary_waiter.name : "Unassigned";
    document.getElementById("placed-time-display").textContent = window.utils.formatDateTime(order.created_at);
    document.getElementById("updated-time-display").textContent = window.utils.formatDateTime(order.updated_at);

    // Archived Tag & Button Text
    const archivedTag = document.getElementById("order-archived-tag");
    const archiveBtn = document.getElementById("archive-order-btn");
    if (order.is_archived) {
        archivedTag.style.display = "inline-flex";
        archiveBtn.textContent = "Restore Order";
        archiveBtn.className = "btn btn-outline-primary btn-sm";
    } else {
        archivedTag.style.display = "none";
        archiveBtn.textContent = "Archive Order";
        archiveBtn.className = "btn btn-secondary btn-sm";
    }

    // Collaborators summary
    const collabSummary = document.getElementById("collaborators-summary");
    if (order.collaborators && order.collaborators.length > 0) {
        collabSummary.textContent = order.collaborators.map(c => c.name).join(", ");
    } else {
        collabSummary.textContent = "None";
    }

    // Disable modification controls if order is closed or archived
    const isClosed = ["served", "cancelled"].includes(order.status) || order.is_archived;
    document.getElementById("open-add-line-btn").disabled = isClosed;
    document.getElementById("open-add-collab-btn").disabled = isClosed;
}

function renderWorkflowButtons(order) {
    const container = document.getElementById("workflow-buttons");
    container.innerHTML = "";

    if (order.is_archived) {
        container.innerHTML = `<span style="color: var(--text-muted); font-size: 0.9rem;">Order is archived. Restore it to make changes.</span>`;
        return;
    }

    const transitions = {
        placed: [
            { label: "Accept Order", target: "accepted", cls: "btn-primary" },
            { label: "Cancel Order", target: "cancelled", cls: "btn-outline-danger" },
        ],
        accepted: [
            { label: "Start Preparing", target: "preparing", cls: "btn-primary" },
            { label: "Cancel Order", target: "cancelled", cls: "btn-outline-danger" },
        ],
        preparing: [
            { label: "Mark as Ready", target: "ready", cls: "btn-primary" },
        ],
        ready: [
            { label: "Serve Order", target: "served", cls: "btn-primary" },
        ],
        served: [],
        cancelled: [],
    };

    const nextMoves = transitions[order.status] || [];

    if (nextMoves.length === 0) {
        container.innerHTML = `<span style="color: var(--text-muted); font-size: 0.9rem;">This order is in final status (${order.status}).</span>`;
        return;
    }

    nextMoves.forEach(move => {
        const btn = document.createElement("button");
        btn.className = `btn btn-sm ${move.cls}`;
        btn.textContent = move.label;
        btn.onclick = () => updateOrderStatus(move.target);
        container.appendChild(btn);
    });
}

async function updateOrderStatus(newStatus) {
    if (newStatus === "cancelled" && !confirm("Are you sure you want to cancel this order?")) {
        return;
    }

    try {
        const updated = await window.api.patch(`/api/orders/${currentOrderId}/status`, { status: newStatus });
        window.utils.showToast(`Order status updated to ${newStatus}!`, "success");
        await loadOrderDetails();
        await loadTimeline();
        await window.utils.updateAlertBadge();
    } catch (err) {
        window.utils.showToast(err.message || "Status change failed.", "error");
    }
}

function renderOrderLines(lines) {
    const tbody = document.getElementById("order-lines-tbody");

    if (!lines || lines.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <p class="empty-state-text">No order lines added yet.</p>
                </td>
            </tr>
        `;
        return;
    }

    const isClosed = ["served", "cancelled"].includes(currentOrder.status) || currentOrder.is_archived;

    tbody.innerHTML = lines.map(line => {
        const rowClass = line.is_voided ? "voided-row" : "";
        const voidReasonHtml = line.is_voided ? `<span class="void-reason-tag">Void Reason: ${line.void_reason || "Voided"}</span>` : "";
        const lineTotal = line.is_voided ? "$0.00 (Voided)" : window.utils.formatCurrency(line.line_total);

        let actionBtn = "";
        if (!line.is_voided && !isClosed) {
            actionBtn = `<button class="btn btn-outline-danger btn-sm" onclick="openVoidLineModal('${line.id}')">Void</button>`;
        } else if (line.is_voided) {
            actionBtn = `<span class="badge badge-voided">Void</span>`;
        }

        return `
            <tr class="${rowClass}">
                <td style="font-weight: 700;">${line.quantity}x</td>
                <td>
                    <strong>${line.menu_item_name || "Dish"}</strong>
                    ${voidReasonHtml}
                </td>
                <td style="color: var(--text-muted);">${line.special_instructions || "-"}</td>
                <td>${window.utils.formatCurrency(line.unit_price)}</td>
                <td style="font-weight: 600;">${lineTotal}</td>
                <td style="text-align: right;">${actionBtn}</td>
            </tr>
        `;
    }).join("");
}

function renderCollaborators(collabs) {
    const container = document.getElementById("collaborators-list");
    const isClosed = ["served", "cancelled"].includes(currentOrder.status) || currentOrder.is_archived;

    if (!collabs || collabs.length === 0) {
        container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.9rem;">No collaborating waiters assigned.</p>`;
        return;
    }

    container.innerHTML = collabs.map(c => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #f8fafc; border-radius: var(--radius-md); border: 1px solid var(--border-color); margin-bottom: 8px;">
            <div>
                <strong>${c.name}</strong>
                <span class="badge badge-role-waiter" style="margin-left: 6px;">Waiter</span>
            </div>
            ${!isClosed ? `<button class="btn btn-outline-danger btn-sm" onclick="removeCollaborator('${c.id}')">&times; Remove</button>` : ''}
        </div>
    `).join("");
}

function renderTimeline(events) {
    const container = document.getElementById("timeline-events");

    if (!events || events.length === 0) {
        container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.9rem; padding-left: 0;">No events logged yet.</p>`;
        return;
    }

    container.innerHTML = events.map(e => {
        let title = "Audit Event";
        if (e.event_type === "status_change") {
            title = `Status: ${e.old_status || 'start'} &rarr; <strong>${e.new_status}</strong>`;
        } else if (e.event_type === "line_added") {
            title = `Line Added: ${e.details || ''}`;
        } else if (e.event_type === "line_voided") {
            title = `<span style="color: var(--danger); font-weight: 600;">Line Voided:</span> ${e.details || ''}`;
        } else if (e.event_type === "note_added") {
            title = `Note: "${e.details || ''}"`;
        }

        return `
            <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span><strong>${e.user?.name || "System"}</strong> (${e.user?.role || "staff"})</span>
                        <span>${window.utils.formatDateTime(e.created_at)}</span>
                    </div>
                    <div>${title}</div>
                </div>
            </div>
        `;
    }).join("");
}

function openAddLineModal() {
    document.getElementById("add-line-form").reset();
    const select = document.getElementById("add-dish-select");
    select.innerHTML = `<option value="" disabled selected>Select a dish...</option>` +
        availableMenuItems.map(item => `
            <option value="${item.id}">${item.name} (${window.utils.formatCurrency(item.price)})</option>
        `).join("");

    window.utils.openModal("add-line-modal");
}

async function handleAddLineSubmit(e) {
    e.preventDefault();
    const menu_item_id = document.getElementById("add-dish-select").value;
    const quantity = parseInt(document.getElementById("add-dish-qty").value);
    const special_instructions = document.getElementById("add-dish-notes").value.trim() || null;

    try {
        await window.api.post(`/api/orders/${currentOrderId}/lines`, {
            menu_item_id,
            quantity,
            special_instructions
        });

        window.utils.showToast("Dish added to order!", "success");
        window.utils.closeModal("add-line-modal");
        await loadOrderDetails();
        await loadTimeline();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to add dish.", "error");
    }
}

function openVoidLineModal(lineId) {
    document.getElementById("void-line-form").reset();
    document.getElementById("void-target-line-id").value = lineId;
    window.utils.openModal("void-line-modal");
}

async function handleVoidLineSubmit(e) {
    e.preventDefault();
    const lineId = document.getElementById("void-target-line-id").value;
    const reason = document.getElementById("void-reason-input").value.trim();

    if (!reason) {
        window.utils.showToast("An explanatory reason is required to void a line.", "error");
        return;
    }

    try {
        await window.api.post(`/api/orders/${currentOrderId}/lines/${lineId}/void`, { reason });
        window.utils.showToast("Order line voided.", "success");
        window.utils.closeModal("void-line-modal");
        await loadOrderDetails();
        await loadTimeline();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to void line.", "error");
    }
}

async function openAddCollabModal() {
    document.getElementById("add-collab-form").reset();
    const select = document.getElementById("collab-user-select");
    select.innerHTML = `
        <option value="" disabled selected>Select a waiter...</option>
        <option value="e1702dd0-4923-5eec-b622-a45d4e828dce">Alice Johnson</option>
        <option value="1f2da932-8411-5403-b09b-1d746533c373">Bob Smith</option>
        <option value="9b6f8494-1f19-58b7-b08e-5b1b47ee2fbb">Carol Davis</option>
    `;
    window.utils.openModal("add-collab-modal");
}

async function handleAddCollabSubmit(e) {
    e.preventDefault();
    const user_id = document.getElementById("collab-user-select").value;

    try {
        await window.api.post(`/api/orders/${currentOrderId}/collaborators`, { user_id });
        window.utils.showToast("Collaborator added to order!", "success");
        window.utils.closeModal("add-collab-modal");
        await loadOrderDetails();
        await loadTimeline();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to add collaborator.", "error");
    }
}

async function removeCollaborator(userId) {
    if (!confirm("Remove this collaborator from the order?")) return;

    try {
        await window.api.delete(`/api/orders/${currentOrderId}/collaborators/${userId}`);
        window.utils.showToast("Collaborator removed.", "info");
        await loadOrderDetails();
        await loadTimeline();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to remove collaborator.", "error");
    }
}

async function handleAddNoteSubmit(e) {
    e.preventDefault();
    const note = document.getElementById("order-note-input").value.trim();

    try {
        await window.api.post(`/api/orders/${currentOrderId}/notes`, { note });
        window.utils.showToast("Note added to timeline!", "success");
        window.utils.closeModal("add-note-modal");
        await loadTimeline();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to save note.", "error");
    }
}

async function handleArchiveToggle() {
    if (!currentOrder) return;
    const isArchived = currentOrder.is_archived;
    const endpoint = isArchived ? `/api/orders/${currentOrderId}/restore` : `/api/orders/${currentOrderId}/archive`;

    try {
        await window.api.post(endpoint);
        window.utils.showToast(isArchived ? "Order restored!" : "Order archived!", "success");
        await loadOrderDetails();
    } catch (err) {
        window.utils.showToast(err.message || "Archive action failed.", "error");
    }
}
