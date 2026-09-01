/**
 * Restaurant Orders - Menu Management Controller
 */

let allMenuItems = [];
let currentFilter = "all";
let selectedItemIds = new Set();
let isManager = false;

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.auth.requireAuth()) return;
    await window.utils.setupNavigation();

    const user = window.api.getCurrentUser();
    isManager = user && user.role === "manager";

    // Show manager controls if manager
    if (isManager) {
        document.querySelectorAll(".manager-only").forEach(el => el.style.display = "");
    }

    // Filter Button Click Listeners
    document.querySelectorAll(".menu-filter-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".menu-filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentFilter = btn.dataset.filter;
            renderMenuGrid();
        });
    });

    // Select all checkbox
    const selectAllCheckbox = document.getElementById("select-all-menu-checkbox");
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener("change", handleSelectAllToggle);
    }

    // Manager Action Buttons
    const openCreateBtn = document.getElementById("open-create-item-btn");
    if (openCreateBtn) {
        openCreateBtn.addEventListener("click", () => {
            document.getElementById("create-menu-item-form").reset();
            window.utils.openModal("create-menu-item-modal");
        });
    }

    const createForm = document.getElementById("create-menu-item-form");
    if (createForm) {
        createForm.addEventListener("submit", handleCreateMenuItem);
    }

    const editForm = document.getElementById("edit-menu-item-form");
    if (editForm) {
        editForm.addEventListener("submit", handleEditMenuItem);
    }

    const openBulkBtn = document.getElementById("open-bulk-modal-btn");
    if (openBulkBtn) {
        openBulkBtn.addEventListener("click", () => {
            document.getElementById("bulk-update-form").reset();
            window.utils.openModal("bulk-update-modal");
        });
    }

    const bulkForm = document.getElementById("bulk-update-form");
    if (bulkForm) {
        bulkForm.addEventListener("submit", handleBulkUpdateSubmit);
    }

    const clearBulkBtn = document.getElementById("clear-bulk-selection-btn");
    if (clearBulkBtn) {
        clearBulkBtn.addEventListener("click", clearBulkSelection);
    }

    // Initial Load
    await loadMenu();
});

async function loadMenu() {
    const container = document.getElementById("menu-grid-container");
    container.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 40px;">
            <div class="loading-spinner"></div>
            <p style="margin-top: 10px; color: var(--text-muted);">Loading menu catalog...</p>
        </div>
    `;

    try {
        allMenuItems = await window.api.get("/api/menu", { include_archived: true });
        renderMenuGrid();
    } catch (err) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--danger);">
                <p>${err.message || "Failed to load menu catalog."}</p>
            </div>
        `;
    }
}

function renderMenuGrid() {
    const container = document.getElementById("menu-grid-container");

    let filtered = allMenuItems;
    if (currentFilter === "available") {
        filtered = allMenuItems.filter(i => i.is_available && !i.is_archived);
    } else if (currentFilter === "unavailable") {
        filtered = allMenuItems.filter(i => !i.is_available && !i.is_archived);
    } else if (currentFilter === "archived") {
        filtered = allMenuItems.filter(i => i.is_archived);
    } else {
        // "all" - by default shows all non-archived, but if manager can see archived too
        if (!isManager) {
            filtered = allMenuItems.filter(i => !i.is_archived);
        }
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1;" class="empty-state">
                <div class="empty-state-icon">🍲</div>
                <p class="empty-state-text">No dishes match the selected filter.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(item => {
        const isSelected = selectedItemIds.has(item.id);
        const cardClass = item.is_archived ? "card-archived" : (!item.is_available ? "card-unavailable" : "");

        let statusBadge = `<span class="badge badge-available">Available</span>`;
        if (item.is_archived) {
            statusBadge = `<span class="badge badge-archived">Archived</span>`;
        } else if (!item.is_available) {
            statusBadge = `<span class="badge badge-unavailable">Unavailable</span>`;
        }

        let selectCheckbox = "";
        if (isManager) {
            selectCheckbox = `
                <input type="checkbox" class="menu-item-checkbox" value="${item.id}" 
                    ${isSelected ? 'checked' : ''} onchange="handleItemCheckboxChange(this, '${item.id}')"
                    style="transform: scale(1.2); cursor: pointer;">
            `;
        }

        let managerActions = "";
        if (isManager) {
            const toggleAvailBtn = !item.is_archived ? `
                <button class="btn btn-secondary btn-sm" onclick="toggleAvailability('${item.id}', ${!item.is_available})">
                    ${item.is_available ? 'Disable' : 'Enable'}
                </button>
            ` : "";

            const archiveBtn = item.is_archived ? `
                <button class="btn btn-outline-primary btn-sm" onclick="restoreMenuItem('${item.id}')">Restore</button>
            ` : `
                <button class="btn btn-secondary btn-sm" onclick="archiveMenuItem('${item.id}')">Archive</button>
            `;

            managerActions = `
                <div style="display: flex; gap: 6px; align-items: center;">
                    <button class="btn btn-secondary btn-sm" onclick="openEditModal('${item.id}')">Edit</button>
                    ${toggleAvailBtn}
                    ${archiveBtn}
                </div>
            `;
        }

        return `
            <div class="menu-card ${cardClass}" id="card-${item.id}">
                <div>
                    <div class="menu-card-header">
                        <div style="display: flex; align-items: flex-start; gap: 10px;">
                            ${selectCheckbox}
                            <div>
                                <h3 class="menu-dish-name">${item.name}</h3>
                                <div style="margin-top: 4px;">${statusBadge}</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="menu-card-footer">
                    <span class="menu-dish-price">${window.utils.formatCurrency(item.price)}</span>
                    ${managerActions}
                </div>
            </div>
        `;
    }).join("");

    updateBulkToolbar();
}

function handleItemCheckboxChange(checkbox, itemId) {
    if (checkbox.checked) {
        selectedItemIds.add(itemId);
    } else {
        selectedItemIds.delete(itemId);
    }
    updateBulkToolbar();
}

function handleSelectAllToggle(e) {
    const checked = e.target.checked;
    const checkboxes = document.querySelectorAll(".menu-item-checkbox");
    checkboxes.forEach(cb => {
        cb.checked = checked;
        if (checked) {
            selectedItemIds.add(cb.value);
        } else {
            selectedItemIds.delete(cb.value);
        }
    });
    updateBulkToolbar();
}

function clearBulkSelection() {
    selectedItemIds.clear();
    const selectAllCheckbox = document.getElementById("select-all-menu-checkbox");
    if (selectAllCheckbox) selectAllCheckbox.checked = false;
    document.querySelectorAll(".menu-item-checkbox").forEach(cb => cb.checked = false);
    updateBulkToolbar();
}

function updateBulkToolbar() {
    const toolbar = document.getElementById("bulk-toolbar");
    const countDisplay = document.getElementById("bulk-selected-count");
    if (!toolbar) return;

    const count = selectedItemIds.size;
    if (count > 0 && isManager) {
        countDisplay.textContent = count;
        toolbar.style.display = "flex";
    } else {
        toolbar.style.display = "none";
    }
}

async function handleCreateMenuItem(e) {
    e.preventDefault();
    const name = document.getElementById("item-name-input").value.trim();
    const price = parseFloat(document.getElementById("item-price-input").value);
    const is_available = document.getElementById("item-available-input").checked;

    try {
        await window.api.post("/api/menu", { name, price, is_available });
        window.utils.showToast(`Dish "${name}" created!`, "success");
        window.utils.closeModal("create-menu-item-modal");
        await loadMenu();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to create dish.", "error");
    }
}

function openEditModal(itemId) {
    const item = allMenuItems.find(i => i.id === itemId);
    if (!item) return;

    document.getElementById("edit-item-id").value = item.id;
    document.getElementById("edit-item-name").value = item.name;
    document.getElementById("edit-item-price").value = item.price;
    document.getElementById("edit-item-available").checked = item.is_available;

    window.utils.openModal("edit-menu-item-modal");
}

async function handleEditMenuItem(e) {
    e.preventDefault();
    const itemId = document.getElementById("edit-item-id").value;
    const name = document.getElementById("edit-item-name").value.trim();
    const price = parseFloat(document.getElementById("edit-item-price").value);
    const is_available = document.getElementById("edit-item-available").checked;

    try {
        await window.api.put(`/api/menu/${itemId}`, { name, price, is_available });
        window.utils.showToast("Menu item updated!", "success");
        window.utils.closeModal("edit-menu-item-modal");
        await loadMenu();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to update dish.", "error");
    }
}

async function toggleAvailability(itemId, newAvail) {
    try {
        await window.api.put(`/api/menu/${itemId}`, { is_available: newAvail });
        window.utils.showToast(newAvail ? "Dish marked available." : "Dish marked unavailable.", "info");
        await loadMenu();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to change availability.", "error");
    }
}

async function archiveMenuItem(itemId) {
    if (!confirm("Archive this menu item? It will be hidden from the active menu.")) return;
    try {
        await window.api.post(`/api/menu/${itemId}/archive`);
        window.utils.showToast("Dish archived.", "info");
        await loadMenu();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to archive dish.", "error");
    }
}

async function restoreMenuItem(itemId) {
    try {
        await window.api.post(`/api/menu/${itemId}/restore`);
        window.utils.showToast("Dish restored to active menu.", "success");
        await loadMenu();
    } catch (err) {
        window.utils.showToast(err.message || "Failed to restore dish.", "error");
    }
}

/**
 * Goal 7: Bulk Action Submission & Per-Item Results Reporting
 */
async function handleBulkUpdateSubmit(e) {
    e.preventDefault();
    const priceVal = document.getElementById("bulk-price-input").value;
    const availVal = document.getElementById("bulk-availability-select").value;

    const payload = {
        item_ids: Array.from(selectedItemIds)
    };

    if (priceVal !== "") {
        payload.price = parseFloat(priceVal);
    }
    if (availVal !== "") {
        payload.is_available = availVal === "true";
    }

    if (payload.price === undefined && payload.is_available === undefined) {
        window.utils.showToast("Please specify either a new price or an availability change.", "warning");
        return;
    }

    try {
        const response = await window.api.post("/api/menu/bulk", payload);
        window.utils.closeModal("bulk-update-modal");

        // Render per-item results modal (Goal 7)
        renderBulkResults(response.results);
        clearBulkSelection();
        await loadMenu();
    } catch (err) {
        window.utils.showToast(err.message || "Bulk update failed.", "error");
    }
}

function renderBulkResults(results) {
    const summary = document.getElementById("bulk-results-summary");
    const list = document.getElementById("bulk-results-list");

    const successCount = results.filter(r => r.success).length;
    const failedCount = results.filter(r => !r.success).length;

    summary.textContent = `Applied to ${results.length} items: ${successCount} Succeeded, ${failedCount} Rejected`;

    list.innerHTML = results.map(r => {
        const item = allMenuItems.find(i => i.id === r.item_id);
        const itemName = item ? item.name : `Item (${r.item_id.slice(0, 8)}...)`;

        if (r.success) {
            return `
                <div class="bulk-result-item bulk-result-success">
                    <span><strong>${itemName}</strong></span>
                    <span>✓ Successfully updated</span>
                </div>
            `;
        } else {
            return `
                <div class="bulk-result-item bulk-result-failed">
                    <span><strong>${itemName}</strong></span>
                    <span>✗ Rejected: ${r.error || 'Invalid'}</span>
                </div>
            `;
        }
    }).join("");

    window.utils.openModal("bulk-results-modal");
}
