/**
 * Restaurant Orders - Orders Queue Controller
 */

let currentPage = 1;
const pageSize = 15;
let availableMenuItems = [];

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.auth.requireAuth()) return;
    await window.utils.setupNavigation();

    // Load available dishes for order creation
    await loadMenuItemsForDropdown();

    // Setup Event Listeners
    document.getElementById("filter-table").addEventListener("input", debounce(() => loadOrders(1), 300));
    document.getElementById("filter-status").addEventListener("change", () => loadOrders(1));
    document.getElementById("filter-sort-by").addEventListener("change", () => loadOrders(1));
    document.getElementById("filter-archived").addEventListener("change", () => loadOrders(1));
    document.getElementById("refresh-orders-btn").addEventListener("click", () => loadOrders(currentPage));

    document.getElementById("prev-page-btn").addEventListener("click", () => {
        if (currentPage > 1) loadOrders(currentPage - 1);
    });

    document.getElementById("next-page-btn").addEventListener("click", () => {
        loadOrders(currentPage + 1);
    });

    document.getElementById("open-create-order-btn").addEventListener("click", openCreateOrderModal);
    document.getElementById("add-item-row-btn").addEventListener("click", () => addDishRow());
    document.getElementById("create-order-form").addEventListener("submit", handleCreateOrderSubmit);

    // Initial Load
    await loadOrders(1);
});

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

async function loadMenuItemsForDropdown() {
    try {
        const items = await window.api.get("/api/menu", { only_available: true });
        availableMenuItems = items || [];
    } catch (err) {
        console.error("Failed to load menu items:", err);
    }
}

async function loadOrders(page = 1) {
    currentPage = page;
    const tbody = document.getElementById("orders-table-body");
    tbody.innerHTML = `
        <tr>
            <td colspan="7" class="empty-state">
                <div class="loading-spinner"></div>
                <p class="empty-state-text" style="margin-top: 10px;">Loading orders...</p>
            </td>
        </tr>
    `;

    const tableNum = document.getElementById("filter-table").value.trim();
    const status = document.getElementById("filter-status").value;
    const sortBy = document.getElementById("filter-sort-by").value;
    const includeArchived = document.getElementById("filter-archived").checked;

    const params = {
        page: currentPage,
        page_size: pageSize,
        sort_by: sortBy,
        sort_dir: "desc",
        include_archived: includeArchived
    };

    if (tableNum) params.table_number = parseInt(tableNum);
    if (status) params.status = status;

    try {
        const response = await window.api.get("/api/orders", params);
        renderOrdersTable(response);
    } catch (err) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state" style="color: var(--danger);">
                    <p class="empty-state-text">${err.message || "Failed to load orders."}</p>
                    <button class="btn btn-secondary btn-sm" onclick="loadOrders(1)" style="margin-top: 10px;">Try Again</button>
                </td>
            </tr>
        `;
    }
}

function renderOrdersTable(data) {
    const tbody = document.getElementById("orders-table-body");
    const orders = data.orders || [];

    if (orders.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    <div class="empty-state-icon">📋</div>
                    <p class="empty-state-text">No matching orders found.</p>
                </td>
            </tr>
        `;
        updatePagination(0, 1, 1);
        return;
    }

    tbody.innerHTML = orders.map(o => {
        const archivedBadge = o.is_archived ? `<span class="badge badge-archived" style="margin-left: 6px;">Archived</span>` : "";
        return `
            <tr>
                <td class="table-cell-bold">Table ${o.table_number} ${archivedBadge}</td>
                <td>${window.utils.renderStatusBadge(o.status)}</td>
                <td><strong>${o.primary_waiter?.name || "Staff"}</strong></td>
                <td>${o.line_count} ${o.line_count === 1 ? 'item' : 'items'}</td>
                <td style="font-weight: 600; color: var(--text-main);">${window.utils.formatCurrency(o.total)}</td>
                <td>${window.utils.formatDateTime(o.created_at)}</td>
                <td style="text-align: right;">
                    <a href="order-details.html?id=${o.id}" class="btn btn-secondary btn-sm">View & Manage</a>
                </td>
            </tr>
        `;
    }).join("");

    updatePagination(data.total, data.page, data.total_pages);
}

function updatePagination(total, page, totalPages) {
    const info = document.getElementById("pagination-info");
    const indicator = document.getElementById("page-indicator");
    const prevBtn = document.getElementById("prev-page-btn");
    const nextBtn = document.getElementById("next-page-btn");

    info.textContent = `Showing page ${page} of ${totalPages} (${total} total orders)`;
    indicator.textContent = `Page ${page} of ${totalPages}`;

    prevBtn.disabled = page <= 1;
    nextBtn.disabled = page >= totalPages;
}

function openCreateOrderModal() {
    document.getElementById("create-order-form").reset();
    const container = document.getElementById("order-items-container");
    container.innerHTML = "";
    addDishRow(); // Add one initial row
    updateEstimatedTotal();
    window.utils.openModal("create-order-modal");
}

function addDishRow() {
    const container = document.getElementById("order-items-container");
    const row = document.createElement("div");
    row.className = "dish-row";

    const optionsHtml = availableMenuItems.map(item => `
        <option value="${item.id}" data-price="${item.price}">
            ${item.name} (${window.utils.formatCurrency(item.price)})
        </option>
    `).join("");

    row.innerHTML = `
        <select class="form-control dish-select" required onchange="updateEstimatedTotal()">
            <option value="" disabled selected>Select a dish...</option>
            ${optionsHtml}
        </select>
        <input type="number" class="form-control dish-qty" value="1" min="1" max="99" required onchange="updateEstimatedTotal()" oninput="updateEstimatedTotal()">
        <input type="text" class="form-control dish-notes" placeholder="Special instructions (optional)">
        <button type="button" class="dish-remove-btn" onclick="removeDishRow(this)">&times;</button>
    `;

    container.appendChild(row);
    updateEstimatedTotal();
}

function removeDishRow(btn) {
    const row = btn.closest(".dish-row");
    const container = document.getElementById("order-items-container");
    if (container.children.length > 1) {
        row.remove();
        updateEstimatedTotal();
    } else {
        window.utils.showToast("An order must have at least one dish row.", "warning");
    }
}

function updateEstimatedTotal() {
    const rows = document.querySelectorAll(".dish-row");
    let total = 0;

    rows.forEach(row => {
        const select = row.querySelector(".dish-select");
        const qtyInput = row.querySelector(".dish-qty");
        const selectedOption = select.options[select.selectedIndex];

        if (selectedOption && selectedOption.dataset.price) {
            const price = parseFloat(selectedOption.dataset.price) || 0;
            const qty = parseInt(qtyInput.value) || 0;
            total += price * qty;
        }
    });

    document.getElementById("new-order-total-display").textContent = window.utils.formatCurrency(total);
}

async function handleCreateOrderSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById("create-order-submit-btn");
    const tableNum = parseInt(document.getElementById("new-order-table").value);

    const lines = [];
    const rows = document.querySelectorAll(".dish-row");

    for (const row of rows) {
        const menu_item_id = row.querySelector(".dish-select").value;
        const quantity = parseInt(row.querySelector(".dish-qty").value);
        const special_instructions = row.querySelector(".dish-notes").value.trim() || null;

        if (!menu_item_id) {
            window.utils.showToast("Please select a dish for all item rows.", "error");
            return;
        }
        lines.push({ menu_item_id, quantity, special_instructions });
    }

    btn.disabled = true;
    btn.innerHTML = `<span class="loading-spinner" style="width: 14px; height: 14px;"></span> Creating...`;

    try {
        const newOrder = await window.api.post("/api/orders", {
            table_number: tableNum,
            lines: lines
        });

        window.utils.showToast(`Order created for Table ${tableNum}!`, "success");
        window.utils.closeModal("create-order-modal");
        loadOrders(1);
    } catch (err) {
        window.utils.showToast(err.message || "Failed to create order.", "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Create Order";
    }
}
