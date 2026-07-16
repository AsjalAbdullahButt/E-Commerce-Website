// Admin API Service

class AdminAPI {
    constructor() {
        this.baseURL = ADMIN_CONFIG.API_URL;
        // Access token lives in memory only (never localStorage/disk), so it can't be lifted by
        // an XSS payload reading persistent storage. It's lost on every page navigation by
        // design — request() below silently restores it from the httpOnly admin_refresh_token
        // cookie set by POST /admin/auth/login and /admin/auth/refresh. Matches the customer
        // flow in shared/js/api.js.
        this.accessToken = null;
    }

    /**
     * Make HTTP request with error handling
     */
    async request(endpoint, method = 'GET', data = null) {
        try {
            const isAuthBootstrap = endpoint === ADMIN_CONFIG.ENDPOINTS.AUTH.LOGIN
                || endpoint === ADMIN_CONFIG.ENDPOINTS.AUTH.REFRESH;
            if (!this.accessToken && !isAuthBootstrap) {
                // Fresh page load — try a silent restore before giving up.
                await this.refreshAccessToken();
            }

            const headers = {
                'Content-Type': 'application/json',
            };

            if (this.accessToken) {
                headers['Authorization'] = `Bearer ${this.accessToken}`;
            }

            const options = {
                method,
                headers,
                cache: 'no-store', // avoid cached admin API responses in browser
                credentials: 'include', // send/receive the httpOnly admin_refresh_token cookie
            };

            if (data && (method === 'POST' || method === 'PUT')) {
                options.body = JSON.stringify(data);
            }

            const response = await fetch(`${this.baseURL}${endpoint}`, options);

            // Handle token expiration
            if (response.status === 401) {
                await this.refreshAccessToken();
                return this.request(endpoint, method, data); // Retry
            }

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * Refresh access token using the httpOnly refresh cookie (no token read/sent from JS).
     * The double-submit admin_csrf_token cookie (readable, unlike the refresh cookie itself)
     * must be echoed back as a header — see backend/utils/csrf.py.
     */
    async refreshAccessToken() {
        try {
            const csrfMatch = document.cookie.match(/(?:^|; )admin_csrf_token=([^;]*)/);
            const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : null;
            const response = await fetch(`${this.baseURL}${ADMIN_CONFIG.ENDPOINTS.AUTH.REFRESH}`, {
                method: 'POST',
                credentials: 'include',
                headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
            });

            if (response.ok) {
                const data = await response.json();
                this.accessToken = data.data.access_token;
            } else {
                // Redirect to login
                window.location.href = 'login.html';
            }
        } catch (error) {
            console.error('Token refresh error:', error);
            window.location.href = 'login.html';
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // AUTHENTICATION
    // ════════════════════════════════════════════════════════════════════════

    async login(email, password) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.AUTH.LOGIN, 'POST', { email, password });
    }

    async logout() {
        return this.request(ADMIN_CONFIG.ENDPOINTS.AUTH.LOGOUT, 'POST');
    }

    // ════════════════════════════════════════════════════════════════════════
    // PRODUCTS
    // ════════════════════════════════════════════════════════════════════════

    async getProducts(category = null, isActive = null, limit = 50, skip = 0) {
        let url = ADMIN_CONFIG.ENDPOINTS.PRODUCTS.LIST + `?limit=${limit}&skip=${skip}`;
        if (category) url += `&category=${category}`;
        if (isActive !== null) url += `&is_active=${isActive}`;
        return this.request(url);
    }

    async getProduct(productId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.PRODUCTS.GET(productId));
    }

    async createProduct(productData) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.PRODUCTS.CREATE, 'POST', productData);
    }

    async updateProduct(productId, productData) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.PRODUCTS.UPDATE(productId), 'PUT', productData);
    }

    async deleteProduct(productId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.PRODUCTS.DELETE(productId), 'DELETE');
    }

    async getLowStockItems() {
        return this.request(ADMIN_CONFIG.ENDPOINTS.PRODUCTS.LOW_STOCK);
    }

    // ════════════════════════════════════════════════════════════════════════
    // INVENTORY
    // ════════════════════════════════════════════════════════════════════════

    async adjustStock(productId, variantSku, quantityChange, reason) {
        const url = ADMIN_CONFIG.ENDPOINTS.INVENTORY.ADJUST_STOCK +
            `?product_id=${productId}&variant_sku=${variantSku}&quantity_change=${quantityChange}&reason=${reason}`;
        return this.request(url, 'POST');
    }

    async getInventoryHistory(productId, limit = 100) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.INVENTORY.HISTORY(productId) + `?limit=${limit}`);
    }

    // ════════════════════════════════════════════════════════════════════════
    // ORDERS
    // ════════════════════════════════════════════════════════════════════════

    async getOrders(status = null, userId = null, limit = 50, skip = 0) {
        let url = ADMIN_CONFIG.ENDPOINTS.ORDERS.LIST + `?limit=${limit}&skip=${skip}`;
        if (status) url += `&status=${status}`;
        if (userId) url += `&user_id=${userId}`;
        return this.request(url);
    }

    async getOrder(orderId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.ORDERS.GET(orderId));
    }

    async updateOrderStatus(orderId, status, note = null) {
        return this.request(
            ADMIN_CONFIG.ENDPOINTS.ORDERS.UPDATE_STATUS(orderId),
            'PUT',
            { status, note }
        );
    }

    async addOrderNote(orderId, note) {
        const url = ADMIN_CONFIG.ENDPOINTS.ORDERS.ADD_NOTE(orderId) + `?note=${encodeURIComponent(note)}`;
        return this.request(url, 'POST');
    }

    async assignRider(orderId, riderId) {
        const url = ADMIN_CONFIG.ENDPOINTS.ORDERS.ASSIGN_RIDER(orderId) + `?rider_id=${encodeURIComponent(riderId)}`;
        return this.request(url, 'PATCH');
    }

    // ════════════════════════════════════════════════════════════════════════
    // RIDERS
    // ════════════════════════════════════════════════════════════════════════

    async getRiders(isActive = null) {
        let url = ADMIN_CONFIG.ENDPOINTS.RIDERS.LIST;
        if (isActive !== null) url += `?is_active=${isActive}`;
        return this.request(url);
    }

    async createRider(riderData) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.RIDERS.CREATE, 'POST', riderData);
    }

    async activateRider(riderId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.RIDERS.ACTIVATE(riderId), 'PATCH');
    }

    async deactivateRider(riderId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.RIDERS.DEACTIVATE(riderId), 'PATCH');
    }

    async getRiderActiveOrders(riderId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.RIDERS.ACTIVE_ORDERS(riderId));
    }

    // ════════════════════════════════════════════════════════════════════════
    // USERS
    // ════════════════════════════════════════════════════════════════════════

    async getUsers(isBanned = null, limit = 50, skip = 0) {
        let url = ADMIN_CONFIG.ENDPOINTS.USERS.LIST + `?limit=${limit}&skip=${skip}`;
        if (isBanned !== null) url += `&is_banned=${isBanned}`;
        return this.request(url);
    }

    async getUser(userId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.USERS.GET(userId));
    }

    async banUser(userId, reason) {
        const url = ADMIN_CONFIG.ENDPOINTS.USERS.BAN(userId) + `?reason=${encodeURIComponent(reason)}`;
        return this.request(url, 'POST');
    }

    async unbanUser(userId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.USERS.UNBAN(userId), 'POST');
    }

    async getUserOrders(userId, limit = 20) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.USERS.ORDERS(userId) + `?limit=${limit}`);
    }

    // ════════════════════════════════════════════════════════════════════════
    // DISCOUNTS
    // ════════════════════════════════════════════════════════════════════════

    async getDiscounts(isActive = null, limit = 50, skip = 0) {
        let url = ADMIN_CONFIG.ENDPOINTS.DISCOUNTS.LIST + `?limit=${limit}&skip=${skip}`;
        if (isActive !== null) url += `&is_active=${isActive}`;
        return this.request(url);
    }

    async getDiscount(discountId) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DISCOUNTS.GET(discountId));
    }

    async createDiscount(discountData) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DISCOUNTS.CREATE, 'POST', discountData);
    }

    async updateDiscount(discountId, discountData) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DISCOUNTS.UPDATE(discountId), 'PUT', discountData);
    }

    // ════════════════════════════════════════════════════════════════════════
    // DASHBOARD
    // ════════════════════════════════════════════════════════════════════════

    async getDashboardStats() {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DASHBOARD.STATS);
    }

    async getDashboardSummary() {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DASHBOARD.SUMMARY);
    }

    async getRevenueTrend(days = 30) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DASHBOARD.REVENUE_TREND + `?days=${days}`);
    }

    async getTopProducts(limit = 10) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DASHBOARD.TOP_PRODUCTS + `?limit=${limit}`);
    }

    async getLowStockDashboard(limit = 10) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DASHBOARD.LOW_STOCK);
    }

    async getRecentOrders(limit = 10) {
        return this.request(ADMIN_CONFIG.ENDPOINTS.DASHBOARD.RECENT_ORDERS + `?limit=${limit}`);
    }

    // ════════════════════════════════════════════════════════════════════════
    // AUDIT LOGS
    // ════════════════════════════════════════════════════════════════════════

    async getAuditLogs(entityType = null, adminId = null, limit = 100, skip = 0) {
        let url = ADMIN_CONFIG.ENDPOINTS.AUDIT.LOGS + `?limit=${limit}&skip=${skip}`;
        if (entityType) url += `&entity_type=${entityType}`;
        if (adminId) url += `&admin_id=${adminId}`;
        return this.request(url);
    }
}

// Initialize API
const adminAPI = new AdminAPI();
