class AdminAnalyticsDashboard {
    constructor() {
        this.charts = {};
        this.init();
    }

    async init() {
        const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
        const user = JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || 'null');

        if (!token || !user) {
            window.location.replace('./login.html');
            return;
        }

        document.addEventListener('DOMContentLoaded', () => {
            this.loadDashboard();
        });

        if (document.readyState !== 'loading') {
            this.loadDashboard();
        }
    }

    _formatCurrency(value) {
        const amount = Number(value || 0);
        return `Rs ${amount.toLocaleString('en-PK', { maximumFractionDigits: 2 })}`;
    }

    _formatDate(value) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '-';
        return date.toLocaleDateString('en-PK', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    }

    _destroyChart(key) {
        if (this.charts[key]) {
            this.charts[key].destroy();
            delete this.charts[key];
        }
    }

    _setStat(selector, value) {
        const node = document.querySelector(selector);
        if (node) {
            node.textContent = value;
        }
    }

    _renderTableBody(bodyId, rows) {
        const body = document.getElementById(bodyId);
        if (!body) return;

        body.textContent = '';
        rows.forEach((rowData) => {
            const row = document.createElement('tr');
            rowData.forEach((cell) => {
                const cellNode = document.createElement('td');
                cellNode.textContent = cell;
                row.appendChild(cellNode);
            });
            body.appendChild(row);
        });
    }

    async loadDashboard() {
        try {
            const summary = await adminAPI.getDashboardSummary();
            const stats = summary.stats || {};

            this._setStat('[data-stat="revenue"]', this._formatCurrency(stats.total_revenue));
            this._setStat('[data-stat="orders"]', String(stats.total_orders ?? 0));
            this._setStat('[data-stat="pending"]', String(stats.pending_orders ?? 0));
            this._setStat('[data-stat="products"]', String(stats.total_products ?? 0));

            this.renderRevenueChart(summary.revenue_by_status || []);
            this.renderOrdersChart(summary.orders_by_status || []);
            this.renderGrowthChart(summary.monthly_growth || []);

            this.renderTopProducts(summary.top_products || []);
            this.renderRecentOrders(summary.recent_orders || []);
        } catch (error) {
            console.error('Dashboard analytics error:', error);
        }
    }

    renderRevenueChart(data) {
        const canvas = document.getElementById('revenue-status-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        this._destroyChart('revenue');
        const labels = data.map((item) => item.status || 'unknown');
        const values = data.map((item) => Number(item.revenue || 0));

        this.charts.revenue = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: ['#D4AF37', '#7C5C1E', '#4B5563', '#0F766E', '#B45309', '#9CA3AF'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#D8D8D8',
                        },
                    },
                },
            },
        });
    }

    renderOrdersChart(data) {
        const canvas = document.getElementById('orders-status-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        this._destroyChart('orders');
        const labels = data.map((item) => item.status || 'unknown');
        const values = data.map((item) => Number(item.count || 0));

        this.charts.orders = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Orders',
                    data: values,
                    backgroundColor: '#D4AF37',
                    borderRadius: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { color: '#D8D8D8' },
                        grid: { color: 'rgba(255,255,255,0.08)' },
                    },
                    y: {
                        ticks: { color: '#D8D8D8', precision: 0 },
                        grid: { color: 'rgba(255,255,255,0.08)' },
                    },
                },
                plugins: {
                    legend: { display: false },
                },
            },
        });
    }

    renderGrowthChart(data) {
        const canvas = document.getElementById('user-growth-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        this._destroyChart('growth');
        const labels = data.map((item) => item.month || 'unknown');
        const values = data.map((item) => Number(item.signups || 0));

        this.charts.growth = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Signups',
                    data: values,
                    borderColor: '#D4AF37',
                    backgroundColor: 'rgba(212, 175, 55, 0.18)',
                    fill: true,
                    tension: 0.35,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { color: '#D8D8D8' },
                        grid: { color: 'rgba(255,255,255,0.08)' },
                    },
                    y: {
                        ticks: { color: '#D8D8D8', precision: 0 },
                        grid: { color: 'rgba(255,255,255,0.08)' },
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#D8D8D8' },
                    },
                },
            },
        });
    }

    renderTopProducts(items) {
        const rows = items.map((item) => [
            item.name || 'Unknown',
            String(item.quantity_sold ?? 0),
            this._formatCurrency(item.revenue),
        ]);

        if (!rows.length) {
            rows.push(['No product data yet', '-', '-']);
        }

        this._renderTableBody('top-products-body', rows);
    }

    renderRecentOrders(items) {
        const rows = items.map((item) => [
            item.order_number || item.order_id || '-',
            item.status || '-',
            this._formatCurrency(item.total),
            this._formatDate(item.created_at),
        ]);

        if (!rows.length) {
            rows.push(['No recent orders', '-', '-', '-']);
        }

        this._renderTableBody('recent-orders-body', rows);
    }
}

new AdminAnalyticsDashboard();