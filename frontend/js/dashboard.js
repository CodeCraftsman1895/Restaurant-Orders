/**
 * Restaurant Orders - Manager Dashboard & Analytics Controller
 */

let chartInstance = null;

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Enforce Manager Role
    if (!window.auth.requireManager()) return;
    await window.utils.setupNavigation();

    // 2. Setup Event Listeners
    document.getElementById("refresh-dashboard-btn").addEventListener("click", () => loadDashboardData());
    document.getElementById("export-csv-btn").addEventListener("click", handleExportCsv);

    // 3. Initial Load
    await loadDashboardData();
});

async function loadDashboardData() {
    try {
        const data = await window.api.get("/api/dashboard");
        renderKpis(data);
        renderStatusBreakdown(data.status_breakdown);
        renderWaiterBreakdown(data.waiter_breakdown);
        render14DayChart(data.last_14_days_chart);
    } catch (err) {
        window.utils.showToast(err.message || "Failed to load dashboard metrics.", "error");
    }
}

function renderKpis(data) {
    document.getElementById("kpi-today-revenue").textContent = window.utils.formatCurrency(data.today_revenue);
    document.getElementById("kpi-open-orders").textContent = data.open_orders_count || 0;
    document.getElementById("kpi-today-orders").textContent = data.today_orders_count || 0;
    document.getElementById("kpi-today-served").textContent = data.today_served_count || 0;
}

function renderStatusBreakdown(items) {
    const tbody = document.getElementById("status-breakdown-tbody");
    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="2" class="empty-state">No order status data.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${window.utils.renderStatusBadge(item.status)}</td>
            <td style="text-align: right; font-weight: 700; font-size: 1.05rem;">${item.count}</td>
        </tr>
    `).join("");
}

function renderWaiterBreakdown(items) {
    const tbody = document.getElementById("waiter-breakdown-tbody");
    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" class="empty-state">No staff activity data.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td><strong>${item.waiter_name}</strong></td>
            <td>${item.order_count} orders</td>
            <td style="text-align: right; font-weight: 700; color: var(--primary);">
                ${window.utils.formatCurrency(item.revenue)}
            </td>
        </tr>
    `).join("");
}

/**
 * Render Chart.js dual-axis bar & line chart for 14-day history (Goal 8)
 */
function render14DayChart(chartData) {
    const canvas = document.getElementById("fourteen-day-chart");
    if (!canvas || !chartData) return;

    const labels = chartData.map(d => {
        const parts = d.date.split("-");
        return `${parts[1]}/${parts[2]}`; // MM/DD
    });
    const orderCounts = chartData.map(d => d.served_orders_count);
    const revenues = chartData.map(d => parseFloat(d.revenue) || 0);

    if (chartInstance) {
        chartInstance.destroy();
    }

    if (typeof Chart === "undefined") {
        console.warn("Chart.js is not loaded.");
        return;
    }

    const ctx = canvas.getContext("2d");
    chartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Served Orders",
                    data: orderCounts,
                    backgroundColor: "rgba(37, 99, 235, 0.75)",
                    borderColor: "#2563eb",
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: "y",
                },
                {
                    label: "Revenue ($)",
                    data: revenues,
                    type: "line",
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.15)",
                    borderWidth: 3,
                    pointBackgroundColor: "#10b981",
                    pointRadius: 4,
                    fill: false,
                    tension: 0.25,
                    yAxisID: "y1",
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false,
            },
            plugins: {
                legend: {
                    position: "top",
                    labels: { font: { weight: "600" } }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.dataset.label === "Revenue ($)") {
                                return `Revenue: $${context.raw.toFixed(2)}`;
                            }
                            return `Served Orders: ${context.raw}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false }
                },
                y: {
                    type: "linear",
                    display: true,
                    position: "left",
                    title: { display: true, text: "Orders Count" },
                    ticks: { stepSize: 1, precision: 0 }
                },
                y1: {
                    type: "linear",
                    display: true,
                    position: "right",
                    title: { display: true, text: "Revenue ($)" },
                    grid: { drawOnChartArea: false },
                    ticks: {
                        callback: function(value) {
                            return "$" + value;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Handle CSV Export Stream Download (Goals 1 & 8)
 */
async function handleExportCsv() {
    const btn = document.getElementById("export-csv-btn");
    btn.disabled = true;
    btn.innerHTML = `<span class="loading-spinner" style="width: 14px; height: 14px;"></span> Exporting...`;

    try {
        const response = await window.api.get("/api/dashboard/export");

        if (response && response.isBlob) {
            const blob = response.blob;
            const contentDisposition = response.headers.get("Content-Disposition") || "";
            let filename = "restaurant_orders_export.csv";
            const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
            if (filenameMatch && filenameMatch[1]) {
                filename = filenameMatch[1];
            }

            // Trigger browser file download
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            window.utils.showToast("CSV export downloaded successfully!", "success");
        } else {
            window.utils.showToast("Export completed.", "info");
        }
    } catch (err) {
        window.utils.showToast(err.message || "Failed to download CSV export.", "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>📥</span> Export Orders CSV`;
    }
}
