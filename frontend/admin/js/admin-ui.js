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
                tbody.innerHTML = topProducts.data.map(p => `
                    <tr>
                        <td>${p.name}</td>
                        <td>${p.total_sold}</td>
                        <td>$${p.revenue.toFixed(2)}</td>
                    </tr>
                `).join('');
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
            
            tbody.innerHTML = this.products.map(p => `
                <tr>
                    <td>${p.name}</td>
                    <td>${p.category}</td>
                    <td>$${p.price.toFixed(2)}</td>
                    <td>${p.total_stock}</td>
                    <td>
                        <span class="status-badge ${p.is_active ? 'status-active' : 'status-banned'}">
                            ${p.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td>
                        <button class="btn btn-sm" onclick="dashboard.viewProduct('${p.id}')">View</button>
                        <button class="btn btn-sm btn-danger" onclick="dashboard.deleteProduct('${p.id}')">Delete</button>
                    </td>
                </tr>
            `).join('');
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
            
            tbody.innerHTML = this.orders.map(o => `
                <tr>
                    <td>${o.id.substring(0, 8)}...</td>
                    <td>${o.user_email}</td>
                    <td>$${o.final_price.toFixed(2)}</td>
                    <td>
                        <span class="status-badge status-${o.status}">
                            ${o.status}
                        </span>
                    </td>
                    <td>${new Date(o.created_at).toLocaleDateString()}</td>
                    <td>
                        <button class="btn btn-sm" onclick="dashboard.viewOrder('${o.id}')">Details</button>
                    </td>
                </tr>
            `).join('');
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
            
            details.innerHTML = `
                <div class="order-details-content">
                    <h4>Order Information</h4>
                    <p><strong>Order ID:</strong> ${order.id}</p>
                    <p><strong>Customer:</strong> ${order.user_email}</p>
                    <p><strong>Status:</strong> <span class="status-badge status-${order.status}">${order.status}</span></p>
                    <p><strong>Total:</strong> $${order.final_price.toFixed(2)}</p>
                    
                    <h4 style="margin-top: 20px;">Items</h4>
                    <table class="data-table">
                        <thead>
                            <tr><th>Product</th><th>Qty</th><th>Price</th></tr>
                        </thead>
                        <tbody>
                            ${order.items.map(item => `
                                <tr>
                                    <td>${item.product_name}</td>
                                    <td>${item.quantity}</td>
                                    <td>$${item.price.toFixed(2)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    
                    <h4 style="margin-top: 20px;">Shipping Address</h4>
                    <p>${order.shipping_address.address}, ${order.shipping_address.city}</p>
                    <p>Phone: ${order.shipping_address.phone}</p>
                </div>
            `;
            
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
            
            tbody.innerHTML = this.users.map(u => `
                <tr>
                    <td>${u.name}</td>
                    <td>${u.email}</td>
                    <td>${u.total_orders || 0}</td>
                    <td>$${(u.total_spent || 0).toFixed(2)}</td>
                    <td>
                        <span class="status-badge ${u.is_banned ? 'status-banned' : 'status-active'}">
                            ${u.is_banned ? 'Banned' : 'Active'}
                        </span>
                    </td>
                    <td>
                        ${u.is_banned ? 
                            `<button class="btn btn-sm btn-success" onclick="dashboard.unbanUser('${u.id}')">Unban</button>` :
                            `<button class="btn btn-sm btn-danger" onclick="dashboard.banUser('${u.id}')">Ban</button>`
                        }
                    </td>
                </tr>
            `).join('');
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
            
            const tbody = document.getElementById('inventoryTable');
            let html = '';
            
            products.forEach(p => {
                p.variants?.forEach(v => {
                    html += `
                        <tr>
                            <td>${p.name}</td>
                            <td>${v.size} / ${v.color}</td>
                            <td>${v.sku}</td>
                            <td>${v.stock}</td>
                            <td>
                                <button class="btn btn-sm" onclick="dashboard.openStockModal('${p.id}', '${v.sku}')">Adjust</button>
                            </td>
                        </tr>
                    `;
                });
            });
            
            tbody.innerHTML = html;
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
            const tbody = document.getElementById('discountsTable');
            
            tbody.innerHTML = this.discounts.map(d => `
                <tr>
                    <td><strong>${d.code}</strong></td>
                    <td>${d.description}</td>
                    <td>${d.discount_type === 'percentage' ? d.discount_value + '%' : '$' + d.discount_value.toFixed(2)}</td>
                    <td>${d.current_usage} / ${d.max_usage}</td>
                    <td>${new Date(d.expiry_date).toLocaleDateString()}</td>
                    <td>
                        <span class="status-badge ${d.is_active ? 'status-active' : 'status-banned'}">
                            ${d.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="dashboard.deactivateDiscount('${d.id}')">Deactivate</button>
                    </td>
                </tr>
            `).join('');
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
            
            const tbody = document.getElementById('auditTable');
            tbody.innerHTML = (response.data || []).map(log => `
                <tr>
                    <td>${log.admin_name}</td>
                    <td>${log.action}</td>
                    <td>${log.entity_type}</td>
                    <td>${new Date(log.timestamp).toLocaleString()}</td>
                    <td>${log.ip_address}</td>
                </tr>
            `).join('');
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
        toast.innerHTML = `<span>${message}</span>`;
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
