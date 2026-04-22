// Admin Dashboard Configuration

const ADMIN_CONFIG = {
    API_URL: 'http://localhost:8000',
    ADMIN_PANEL_URL: 'dashboard.html',
    
    // API Endpoints
    ENDPOINTS: {
        AUTH: {
            LOGIN: '/admin/auth/login',
            LOGOUT: '/admin/auth/logout',
            REFRESH: '/admin/auth/refresh',
        },
        PRODUCTS: {
            LIST: '/admin/products',
            CREATE: '/admin/products',
            GET: (id) => `/admin/products/${id}`,
            UPDATE: (id) => `/admin/products/${id}`,
            DELETE: (id) => `/admin/products/${id}`,
            LOW_STOCK: '/admin/products/low-stock/items',
        },
        ORDERS: {
            LIST: '/admin/orders',
            GET: (id) => `/admin/orders/${id}`,
            UPDATE_STATUS: (id) => `/admin/orders/${id}/status`,
            ADD_NOTE: (id) => `/admin/orders/${id}/note`,
        },
        USERS: {
            LIST: '/admin/users',
            GET: (id) => `/admin/users/${id}`,
            BAN: (id) => `/admin/users/${id}/ban`,
            UNBAN: (id) => `/admin/users/${id}/unban`,
            ORDERS: (id) => `/admin/users/${id}/orders`,
        },
        INVENTORY: {
            ADJUST_STOCK: '/admin/inventory/adjust-stock',
            HISTORY: (id) => `/admin/inventory/history/${id}`,
        },
        DISCOUNTS: {
            LIST: '/admin/discounts',
            CREATE: '/admin/discounts',
            GET: (id) => `/admin/discounts/${id}`,
            UPDATE: (id) => `/admin/discounts/${id}`,
        },
        DASHBOARD: {
            STATS: '/admin/dashboard/stats',
            REVENUE_TREND: '/admin/dashboard/revenue-trend',
            TOP_PRODUCTS: '/admin/dashboard/top-products',
            LOW_STOCK: '/admin/dashboard/low-stock',
            RECENT_ORDERS: '/admin/dashboard/recent-orders',
        },
        AUDIT: {
            LOGS: '/admin/audit-logs',
        },
    },
    
    // Order statuses
    ORDER_STATUSES: [
        'pending',
        'confirmed',
        'packed',
        'shipped',
        'delivered',
        'cancelled',
        'returned'
    ],
    
    // Categories
    CATEGORIES: [
        { value: 't-shirts', label: 'T-Shirts' },
        { value: 'hoodies', label: 'Hoodies' },
        { value: 'accessories', label: 'Accessories' }
    ],
};

// Storage keys
const STORAGE_KEYS = {
    AUTH_TOKEN: 'admin_access_token',
    REFRESH_TOKEN: 'admin_refresh_token',
    ADMIN_DATA: 'admin_data',
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ADMIN_CONFIG, STORAGE_KEYS };
}
