// Admin Dashboard UI Controller

class AdminDashboard {
    constructor() {
        this.currentSection = 'dashboard';
        this.products = [];
        this.orders = [];
        this.users = [];
        this.discounts = [];
        this.init();
    }

    async init() {
        console.log('Initializing Admin Dashboard...');
        
        // Check authentication
        const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
        if (!token) {
            window.location.href = 'login.html';
            return;
        }

        // Load admin data
        const adminData = JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || '{}');
        document.getElementById('adminName').textContent = adminData.name || 'Admin';
        document.getElementById('adminRole').textContent = adminData.role || 'Admin';

        this.setupEventListeners();
        await this.loadDashboard();
        
        // Hide loading screen
        document.getElementById('loadingScreen').classList.add('hidden');
    }

    // Helper: create a table row from array of cell values or nodes
    _createRow(cells = []) {
        const tr = document.createElement('tr');
        cells.forEach(c => {
            const td = document.createElement('td');
            if (c instanceof Node) {
                td.appendChild(c);
            } else {
                td.textContent = c == null ? '' : String(c);
            }
            tr.appendChild(td);
        });
        return tr;
    }

    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => this.switchSection(e));
        });

        // Logout
        document.getElementById('logoutBtn').addEventListener('click', () => this.logout());

        // Sidebar toggle
        document.getElementById('sidebarToggle').addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('active');
        });

        // Product section
        document.getElementById('addProductBtn')?.addEventListener('click', () => this.openProductModal());
        document.getElementById('productForm')?.addEventListener('submit', (e) => this.handleProductSubmit(e));

        // Discount section
        document.getElementById('addDiscountBtn')?.addEventListener('click', () => this.openDiscountModal());
        document.getElementById('discountForm')?.addEventListener('submit', (e) => this.handleDiscountSubmit(e));

        // Modal close buttons
        document.querySelectorAll('.modal-close, .modal-close-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.modal')?.classList.remove('active');
            });
        });

        // Filters
        document.getElementById('categoryFilter')?.addEventListener('change', () => this.loadProducts());
        document.getElementById('orderStatusFilter')?.addEventListener('change', () => this.loadOrders());
        document.getElementById('userStatusFilter')?.addEventListener('change', () => this.loadUsers());
    }

    switchSection(e) {
        e.preventDefault();
        const section = e.currentTarget.dataset.section;
        
        // Update active nav
        document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
        e.currentTarget.classList.add('active');

        // Update active section
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        document.getElementById(`${section}Section`)?.classList.add('active');

        // Update page title
        const titles = {
            dashboard: 'Dashboard',
            products: 'Products',
            orders: 'Orders',
            users: 'Users',
            inventory: 'Inventory',
            discounts: 'Discounts',
            audit: 'Audit Logs'
        };
        document.getElementById('pageTitle').textContent = titles[section] || section;

        // Load section data
        this.currentSection = section;
        this.loadSectionData(section);
    }

    async loadSectionData(section) {
        try {
            switch (section) {
                case 'dashboard':
                    await this.loadDashboard();
                    break;
                case 'products':
                    await this.loadProducts();
                    break;
                case 'orders':
                    await this.loadOrders();
                    break;
                case 'users':
                    await this.loadUsers();
                    break;
                case 'inventory':
                    await this.loadInventory();
                    break;
                case 'discounts':
                    await this.loadDiscounts();
                    break;
                case 'audit':
                    await this.loadAuditLogs();
                    break;
            }
        } catch (error) {
            this.showToast('Error loading section: ' + error.message, 'error');
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // DASHBOARD
    // ════════════════════════════════════════════════════════════════════════

    async loadDashboard() {
        try {
            const stats = await adminAPI.getDashboardStats();
            const trend = await adminAPI.getRevenueTrend();
            const topProducts = await adminAPI.getTopProducts();
            const recentOrders = await adminAPI.getRecentOrders();

            // Update stats cards
            if (stats.data) {
                document.getElementById('totalSales').textContent = `$${stats.data.total_sales.toFixed(2)}`;
                document.getElementById('totalOrders').textContent = stats.data.total_orders;
                document.getElementById('totalUsers').textContent = stats.data.total_users;
                document.getElementById('lowStockItems').textContent = stats.data.low_stock_items;
            }

            // Chart
            if (trend.data) {
                this.drawRevenueChart(trend.data);
            }

            // Top products
            if (topProducts.data) {
                const tbody = document.getElementById('topProductsTable');
                tbody.textContent = '';
                topProducts.data.forEach(p => {
                    const row = this._createRow([p.name, p.total_sold, `$${p.revenue.toFixed(2)}`]);
                    tbody.appendChild(row);
                });
            }
        } catch (error) {
            console.error('Dashboard load error:', error);
            this.showToast('Failed to load dashboard', 'error');
        }
    }

    drawRevenueChart(data) {
        const canvas = document.getElementById('revenueChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.parentElement.offsetWidth;
        const height = 300;
        
        canvas.width = width;
        canvas.height = height;

        // Simple line chart
        if (!data.data || data.data.length === 0) return;

        const maxValue = Math.max(...data.data);
        const padding = 40;
        const graphWidth = width - (padding * 2);
        const graphHeight = height - (padding * 2);
        const pointSpacing = graphWidth / (data.data.length - 1);

        // Draw grid
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 5; i++) {
            const y = padding + (graphHeight / 5) * i;
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(width - padding, y);
            ctx.stroke();
        }

        // Draw line
        ctx.strokeStyle = '#6366f1';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        data.data.forEach((value, index) => {
            const x = padding + (pointSpacing * index);
            const y = height - padding - (value / maxValue) * graphHeight;
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        // Draw points
        ctx.fillStyle = '#6366f1';
        data.data.forEach((value, index) => {
            const x = padding + (pointSpacing * index);
            const y = height - padding - (value / maxValue) * graphHeight;
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    // ════════════════════════════════════════════════════════════════════════
    // PRODUCTS
    // ════════════════════════════════════════════════════════════════════════

    async loadProducts() {
        try {
            const category = document.getElementById('categoryFilter')?.value;
            const response = await adminAPI.getProducts(category);
            
            this.products = response.data || [];
            const tbody = document.getElementById('productsTable');
            tbody.textContent = '';
            this.products.forEach(p => {
                const actionsTd = document.createElement('td');
                const viewBtn = document.createElement('button'); viewBtn.className = 'btn btn-sm'; viewBtn.textContent = 'View'; viewBtn.addEventListener('click', () => this.viewProduct(p.id));
                const delBtn = document.createElement('button'); delBtn.className = 'btn btn-sm btn-danger'; delBtn.textContent = 'Delete'; delBtn.addEventListener('click', () => this.deleteProduct(p.id));
                actionsTd.appendChild(viewBtn); actionsTd.appendChild(delBtn);

                const statusSpan = document.createElement('span'); statusSpan.className = `status-badge ${p.is_active ? 'status-active' : 'status-banned'}`; statusSpan.textContent = p.is_active ? 'Active' : 'Inactive';

                const row = this._createRow([p.name, p.category, `$${p.price.toFixed(2)}`, p.total_stock, '']);
                row.children[4].appendChild(statusSpan);
                row.appendChild(actionsTd);
                tbody.appendChild(row);
            });
        } catch (error) {
            this.showToast('Failed to load products', 'error');
        }
    }

    openProductModal() {
        document.getElementById('productModal').classList.add('active');
    }

    async handleProductSubmit(e) {
        e.preventDefault();
        
        try {
            const productData = {
                name: document.getElementById('productName').value,
                description: document.getElementById('productDescription').value,
                category: document.getElementById('productCategory').value,
                price: parseFloat(document.getElementById('productPrice').value),
                discount_percentage: parseFloat(document.getElementById('productDiscount').value || 0),
                variants: [], // Would be populated from form
                tags: [],
                images: [],
            };

            await adminAPI.createProduct(productData);
            this.showToast('Product created successfully', 'success');
            document.getElementById('productModal').classList.remove('active');
            document.getElementById('productForm').reset();
            await this.loadProducts();
        } catch (error) {
            this.showToast('Failed to create product: ' + error.message, 'error');
        }
    }

    async viewProduct(productId) {
        try {
            const response = await adminAPI.getProduct(productId);
            console.log('Product details:', response.data);
            // Can implement detailed view modal
        } catch (error) {
            this.showToast('Failed to load product', 'error');
        }
    }

    async deleteProduct(productId) {
        if (!confirm('Are you sure you want to delete this product?')) return;
        
        try {
            await adminAPI.deleteProduct(productId);
            this.showToast('Product deleted successfully', 'success');
            await this.loadProducts();
        } catch (error) {
            this.showToast('Failed to delete product', 'error');
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // ORDERS
    // ════════════════════════════════════════════════════════════════════════

    async loadOrders() {
        try {
            const status = document.getElementById('orderStatusFilter')?.value;
            const response = await adminAPI.getOrders(status);
            
            this.orders = response.data || [];
            const tbody = document.getElementById('ordersTable');
            tbody.textContent = '';
            this.orders.forEach(o => {
                const actionsTd = document.createElement('td');
                const detBtn = document.createElement('button'); detBtn.className = 'btn btn-sm'; detBtn.textContent = 'Details'; detBtn.addEventListener('click', () => this.viewOrder(o.id));
                actionsTd.appendChild(detBtn);

                const statusSpan = document.createElement('span'); statusSpan.className = `status-badge status-${o.status}`; statusSpan.textContent = o.status;

                const row = this._createRow([`${o.id.substring(0,8)}...`, o.user_email, `$${o.final_price.toFixed(2)}`, '']);
                row.children[3].appendChild(statusSpan);
                // created_at
                const dateTd = document.createElement('td'); dateTd.textContent = new Date(o.created_at).toLocaleDateString(); row.appendChild(dateTd);
                row.appendChild(actionsTd);
                tbody.appendChild(row);
            });
        } catch (error) {
            this.showToast('Failed to load orders', 'error');
        }
    }

    async viewOrder(orderId) {
        try {
            const response = await adminAPI.getOrder(orderId);
            const order = response.data;
            
            const modal = document.getElementById('orderModal');
            const details = document.getElementById('orderDetails');
            
            // Build details content safely
            details.textContent = '';
            const wrapper = document.createElement('div'); wrapper.className = 'order-details-content';
            const h4 = document.createElement('h4'); h4.textContent = 'Order Information'; wrapper.appendChild(h4);
            const pId = document.createElement('p'); const strongId = document.createElement('strong'); strongId.textContent = 'Order ID:'; pId.appendChild(strongId); pId.appendChild(document.createTextNode(' ' + order.id)); wrapper.appendChild(pId);
            const pCust = document.createElement('p'); const strongCust = document.createElement('strong'); strongCust.textContent = 'Customer:'; pCust.appendChild(strongCust); pCust.appendChild(document.createTextNode(' ' + order.user_email)); wrapper.appendChild(pCust);
            const pStatus = document.createElement('p'); const strongStatus = document.createElement('strong'); strongStatus.textContent = 'Status:'; pStatus.appendChild(strongStatus); const statusSpan = document.createElement('span'); statusSpan.className = `status-badge status-${order.status}`; statusSpan.textContent = order.status; pStatus.appendChild(document.createTextNode(' ')); pStatus.appendChild(statusSpan); wrapper.appendChild(pStatus);
            const pTotal = document.createElement('p'); const strongTotal = document.createElement('strong'); strongTotal.textContent = 'Total:'; pTotal.appendChild(strongTotal); pTotal.appendChild(document.createTextNode(' $' + order.final_price.toFixed(2))); wrapper.appendChild(pTotal);

            const itemsH4 = document.createElement('h4'); itemsH4.style.marginTop = '20px'; itemsH4.textContent = 'Items'; wrapper.appendChild(itemsH4);
            const table = document.createElement('table'); table.className = 'data-table';
            const thead = document.createElement('thead'); const trHead = document.createElement('tr'); ['Product','Qty','Price'].forEach(h => { const th = document.createElement('th'); th.textContent = h; trHead.appendChild(th); }); thead.appendChild(trHead);
            const tbodyItems = document.createElement('tbody');
            order.items.forEach(item => {
                const r = this._createRow([item.product_name, item.quantity, `$${item.price.toFixed(2)}`]);
                tbodyItems.appendChild(r);
            });
            table.appendChild(thead); table.appendChild(tbodyItems); wrapper.appendChild(table);

            const shipH4 = document.createElement('h4'); shipH4.style.marginTop = '20px'; shipH4.textContent = 'Shipping Address'; wrapper.appendChild(shipH4);
            const addrP = document.createElement('p'); addrP.textContent = `${order.shipping_address.address}, ${order.shipping_address.city}`; wrapper.appendChild(addrP);
            const phoneP = document.createElement('p'); phoneP.textContent = `Phone: ${order.shipping_address.phone}`; wrapper.appendChild(phoneP);

            details.appendChild(wrapper);
            
            modal.classList.add('active');
        } catch (error) {
            this.showToast('Failed to load order', 'error');
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // USERS
    // ════════════════════════════════════════════════════════════════════════

    async loadUsers() {
        try {
            const response = await adminAPI.getUsers();
            
            this.users = response.data || [];
            const tbody = document.getElementById('usersTable');
            tbody.textContent = '';
            this.users.forEach(u => {
                const actionsTd = document.createElement('td');
                if (u.is_banned) {
                    const unbanBtn = document.createElement('button'); unbanBtn.className = 'btn btn-sm btn-success'; unbanBtn.textContent = 'Unban'; unbanBtn.addEventListener('click', () => this.unbanUser(u.id));
                    actionsTd.appendChild(unbanBtn);
                } else {
                    const banBtn = document.createElement('button'); banBtn.className = 'btn btn-sm btn-danger'; banBtn.textContent = 'Ban'; banBtn.addEventListener('click', () => this.banUser(u.id));
                    actionsTd.appendChild(banBtn);
                }

                const statusSpan = document.createElement('span'); statusSpan.className = `status-badge ${u.is_banned ? 'status-banned' : 'status-active'}`; statusSpan.textContent = u.is_banned ? 'Banned' : 'Active';

                const row = this._createRow([u.name, u.email, u.total_orders || 0, `$${(u.total_spent || 0).toFixed(2)}`, '']);
                row.children[4].appendChild(statusSpan);
                row.appendChild(actionsTd);
                tbody.appendChild(row);
            });
        } catch (error) {
            this.showToast('Failed to load users', 'error');
        }
    }

    async banUser(userId) {
        const reason = prompt('Enter ban reason:');
        if (!reason) return;
        
        try {
            await adminAPI.banUser(userId, reason);
            this.showToast('User banned successfully', 'success');
            await this.loadUsers();
        } catch (error) {
            this.showToast('Failed to ban user', 'error');
        }
    }

    async unbanUser(userId) {
        try {
            await adminAPI.unbanUser(userId);
            this.showToast('User unbanned successfully', 'success');
            await this.loadUsers();
        } catch (error) {
            this.showToast('Failed to unban user', 'error');
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // INVENTORY
    // ════════════════════════════════════════════════════════════════════════

    async loadInventory() {
        try {
            const response = await adminAPI.getProducts(null, null, 1000);
            const products = response.data || [];
            
            const tbody = document.getElementById('inventoryTable'); tbody.textContent = '';
            products.forEach(p => {
                p.variants?.forEach(v => {
                    const actionsTd = document.createElement('td');
                    const adjBtn = document.createElement('button'); adjBtn.className = 'btn btn-sm'; adjBtn.textContent = 'Adjust'; adjBtn.addEventListener('click', () => this.openStockModal(p.id, v.sku));
                    actionsTd.appendChild(adjBtn);
                    const row = this._createRow([p.name, `${v.size} / ${v.color}`, v.sku, v.stock]);
                    row.appendChild(actionsTd);
                    tbody.appendChild(row);
                });
            });
        } catch (error) {
            this.showToast('Failed to load inventory', 'error');
        }
    }

    openStockModal(productId, sku) {
        const modal = document.getElementById('stockModal');
        modal.dataset.productId = productId;
        modal.dataset.variantSku = sku;
        
        document.getElementById('stockForm').onsubmit = async (e) => {
            e.preventDefault();
            try {
                const quantity = parseInt(document.getElementById('stockQuantity').value);
                const reason = document.getElementById('stockReason').value;
                
                await adminAPI.adjustStock(productId, sku, quantity, reason);
                this.showToast('Stock adjusted successfully', 'success');
                modal.classList.remove('active');
                await this.loadInventory();
            } catch (error) {
                this.showToast('Failed to adjust stock', 'error');
            }
        };
        
        modal.classList.add('active');
    }

    // ════════════════════════════════════════════════════════════════════════
    // DISCOUNTS
    // ════════════════════════════════════════════════════════════════════════

    async loadDiscounts() {
        try {
            const response = await adminAPI.getDiscounts();
            
            this.discounts = response.data || [];
            const tbody = document.getElementById('discountsTable'); tbody.textContent = '';
            this.discounts.forEach(d => {
                const actionsTd = document.createElement('td'); const deactBtn = document.createElement('button'); deactBtn.className = 'btn btn-sm btn-danger'; deactBtn.textContent = 'Deactivate'; deactBtn.addEventListener('click', () => this.deactivateDiscount(d.id)); actionsTd.appendChild(deactBtn);
                const statusSpan = document.createElement('span'); statusSpan.className = `status-badge ${d.is_active ? 'status-active' : 'status-banned'}`; statusSpan.textContent = d.is_active ? 'Active' : 'Inactive';
                const row = this._createRow([d.code, d.description, d.discount_type === 'percentage' ? d.discount_value + '%' : '$' + d.discount_value.toFixed(2), `${d.current_usage} / ${d.max_usage}`, new Date(d.expiry_date).toLocaleDateString(), '']);
                row.children[5].appendChild(statusSpan);
                row.appendChild(actionsTd);
                tbody.appendChild(row);
            });
        } catch (error) {
            this.showToast('Failed to load discounts', 'error');
        }
    }

    openDiscountModal() {
        document.getElementById('discountModal').classList.add('active');
    }

    async handleDiscountSubmit(e) {
        e.preventDefault();
        
        try {
            const discountData = {
                code: document.getElementById('discountCode').value,
                description: document.getElementById('discountDescription').value,
                discount_type: document.getElementById('discountType').value,
                discount_value: parseFloat(document.getElementById('discountValue').value),
                max_usage: parseInt(document.getElementById('discountMaxUsage').value),
                min_order_value: parseFloat(document.getElementById('discountMinOrder').value || 0),
                expiry_date: new Date(document.getElementById('discountExpiry').value).toISOString(),
            };

            await adminAPI.createDiscount(discountData);
            this.showToast('Discount created successfully', 'success');
            document.getElementById('discountModal').classList.remove('active');
            document.getElementById('discountForm').reset();
            await this.loadDiscounts();
        } catch (error) {
            this.showToast('Failed to create discount: ' + error.message, 'error');
        }
    }

    async deactivateDiscount(discountId) {
        try {
            await adminAPI.updateDiscount(discountId, { is_active: false });
            this.showToast('Discount deactivated', 'success');
            await this.loadDiscounts();
        } catch (error) {
            this.showToast('Failed to deactivate discount', 'error');
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // AUDIT LOGS
    // ════════════════════════════════════════════════════════════════════════

    async loadAuditLogs() {
        try {
            const response = await adminAPI.getAuditLogs();
            
            const tbody = document.getElementById('auditTable'); tbody.textContent = '';
            (response.data || []).forEach(log => {
                const row = this._createRow([log.admin_name, log.action, log.entity_type, new Date(log.timestamp).toLocaleString(), log.ip_address]);
                tbody.appendChild(row);
            });
        } catch (error) {
            this.showToast('Failed to load audit logs', 'error');
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // UTILITIES
    // ════════════════════════════════════════════════════════════════════════

    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const span = document.createElement('span'); span.textContent = message; toast.appendChild(span);
        container.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }

    async logout() {
        try {
            await adminAPI.logout();
            localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
            localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
            localStorage.removeItem(STORAGE_KEYS.ADMIN_DATA);
            window.location.href = 'login.html';
        } catch (error) {
            console.error('Logout error:', error);
            window.location.href = 'login.html';
        }
    }
}

// Initialize dashboard when DOM is ready
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new AdminDashboard();
});
