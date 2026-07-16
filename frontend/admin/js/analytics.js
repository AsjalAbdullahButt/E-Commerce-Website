class AdminAnalyticsDashboard {
    constructor() {
        this.charts = {};
        this.init();
    }

    async init() {
        // The access token lives in memory only (see js/admin-api.js) and is restored lazily on
        // the first API call, so it isn't checked here — only the cached (non-sensitive) profile.
        const user = JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || 'null');

        if (!user) {
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

    _chartAnimation() {
        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        return reduced ? { duration: 0 } : { duration: 800, easing: 'easeOutQuart' };
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

    // Animates a stat card from its current displayed value up to `endValue`,
    // formatting each intermediate frame with `formatFn` (e.g. currency).
    _animateStat(selector, endValue, formatFn) {
        const node = document.querySelector(selector);
        if (!node) return;

        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reduced) {
            node.textContent = formatFn(endValue);
            return;
        }

        const startValue = Number(String(node.textContent).replace(/[^\d.-]/g, '')) || 0;
        const duration = 800;
        const startTime = performance.now();

        const step = (now) => {
            const progress = Math.min(1, (now - startTime) / duration);
            const eased = 1 - Math.pow(1 - progress, 3); // ease-out-cubic
            const current = startValue + (endValue - startValue) * eased;
            node.textContent = formatFn(progress >= 1 ? endValue : current);
            if (progress < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }

    _renderTableBody(bodyId, rows) {
        const body = document.getElementById(bodyId);
        if (!body) return;

        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        body.textContent = '';
        rows.forEach((rowData, idx) => {
            const row = document.createElement('tr');
            rowData.forEach((cell) => {
                const cellNode = document.createElement('td');
                cellNode.textContent = cell;
                row.appendChild(cellNode);
            });
            if (!reduced) {
                row.style.opacity = '0';
                row.style.transform = 'translateY(8px)';
                row.style.transition = `opacity var(--duration-base) var(--ease) ${idx * 40}ms, transform var(--duration-base) var(--ease) ${idx * 40}ms`;
            }
            body.appendChild(row);
        });
        if (!reduced) {
            requestAnimationFrame(() => {
                Array.from(body.children).forEach((row) => {
                    row.style.opacity = '1';
                    row.style.transform = 'none';
                });
            });
        }
    }

    async loadDashboard() {
        try {
            const summary = await adminAPI.getDashboardSummary();
            const stats = summary.stats || {};

            this._animateStat('[data-stat="revenue"]', Number(stats.total_revenue || 0), (v) => this._formatCurrency(v));
            this._animateStat('[data-stat="orders"]', Number(stats.total_orders || 0), (v) => String(Math.round(v)));
            this._animateStat('[data-stat="pending"]', Number(stats.pending_orders || 0), (v) => String(Math.round(v)));
            this._animateStat('[data-stat="products"]', Number(stats.total_products || 0), (v) => String(Math.round(v)));

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
                animation: this._chartAnimation(),
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
                animation: this._chartAnimation(),
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
                animation: this._chartAnimation(),
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