// === ADMIN.JS ===
async function loadAdminDashboard() {
  requireAuth(['admin']);

  try {
    // Load stats
    const products = await api.get('/products?limit=1000', true);
    const orders = await api.get('/orders', true);

    const totalRevenue = orders.filter(o => o.status === 'delivered')
      .reduce((sum, o) => sum + o.total, 0);
    const totalOrders = orders.length;
    const pendingOrders = orders.filter(o => o.status === 'pending').length;

    // Update stat cards
    document.querySelector('[data-stat="revenue"]').textContent = `Rs ${totalRevenue.toLocaleString()}`;
    document.querySelector('[data-stat="orders"]').textContent = totalOrders;
    document.querySelector('[data-stat="pending"]').textContent = pendingOrders;
    document.querySelector('[data-stat="products"]').textContent = products.total;

    // Load recent orders
    const ordersTable = document.querySelector('[data-section="recent-orders"]');
    if (ordersTable) {
      ordersTable.innerHTML = `
        <table class="orders-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Customer</th>
              <th>Total</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${orders.slice(0, 10).map(o => `
              <tr>
                <td>${o.id.substring(0, 8)}...</td>
                <td>${o.shipping_address?.full_name || 'Unknown'}</td>
                <td>Rs ${o.total.toLocaleString()}</td>
                <td><span class="badge ${o.status}">${o.status}</span></td>
                <td><a href="#" onclick="viewOrder('${o.id}', event)" style="color:var(--gold);">View</a></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }
  } catch (err) {
    console.error('Failed to load dashboard', err);
  }
}

async function loadProducts() {
  requireAuth(['admin']);

  try {
    const data = await api.get('/products?limit=1000', true);
    const container = document.querySelector('[data-section="products"]');
    if (!container) return;

    container.innerHTML = `
      <table class="table-wrapper">
        <thead>
          <tr>
            <th>Name</th>
            <th>Price</th>
            <th>Stock</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${data.products.map(p => `
            <tr>
              <td>${p.name}</td>
              <td>Rs ${p.price.toLocaleString()}</td>
              <td>${p.stock}</td>
              <td><span class="badge ${p.is_active ? 'active' : 'inactive'}">${p.is_active ? 'Active' : 'Inactive'}</span></td>
              <td>
                <div class="btn-group">
                  <button class="icon-btn" onclick="editProduct('${p.id}')"><i class="fas fa-edit"></i></button>
                  <button class="icon-btn" onclick="deleteProduct('${p.id}')"><i class="fas fa-trash"></i></button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.error('Failed to load products', err);
  }
}

async function loadOrders() {
  requireAuth(['admin']);

  try {
    const orders = await api.get('/orders', true);
    const container = document.querySelector('[data-section="orders"]');
    if (!container) return;

    container.innerHTML = `
      <table class="table-wrapper">
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Customer</th>
            <th>Total</th>
            <th>Status</th>
            <th>Rider</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${orders.map(o => `
            <tr>
              <td>${o.id.substring(0, 8)}...</td>
              <td>${o.shipping_address?.full_name || 'Unknown'}</td>
              <td>Rs ${o.total.toLocaleString()}</td>
              <td><span class="badge ${o.status}">${o.status}</span></td>
              <td>${o.rider_id || 'Unassigned'}</td>
              <td>
                <div class="btn-group">
                  <button class="icon-btn" onclick="viewOrder('${o.id}')"><i class="fas fa-eye"></i></button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.error('Failed to load orders', err);
  }
}

function viewOrder(orderId, event) {
  if (event) event.preventDefault();
  
  const modal = document.getElementById('order-modal') || createOrderModal();
  const user = getUser();

  if (!user || user.role !== 'admin') {
    showToast('Unauthorized', 'error');
    return;
  }

  modal.classList.add('open');
  loadOrderDetails(orderId, modal);
}

function createOrderModal() {
  const modal = document.createElement('div');
  modal.id = 'order-modal';
  modal.className = 'modal';
  modal.innerHTML = `
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">Order Details</h3>
        <button class="modal-close" onclick="document.getElementById('order-modal').classList.remove('open')">×</button>
      </div>
      <div id="order-details"></div>
    </div>
  `;
  document.body.appendChild(modal);
  return modal;
}

async function loadOrderDetails(orderId, modal) {
  try {
    const order = await api.get(`/orders/${orderId}`, true);
    const detailsDiv = modal.querySelector('#order-details');

    detailsDiv.innerHTML = `
      <div class="form-group">
        <label>Order ID</label>
        <input type="text" value="${order.id}" readonly>
      </div>
      <div class="form-group">
        <label>Customer</label>
        <input type="text" value="${order.shipping_address?.full_name}" readonly>
      </div>
      <div class="form-group">
        <label>Status</label>
        <select id="order-status">
          <option value="pending" ${order.status === 'pending' ? 'selected' : ''}>Pending</option>
          <option value="confirmed" ${order.status === 'confirmed' ? 'selected' : ''}>Confirmed</option>
          <option value="packed" ${order.status === 'packed' ? 'selected' : ''}>Packed</option>
          <option value="shipped" ${order.status === 'shipped' ? 'selected' : ''}>Shipped</option>
          <option value="delivered" ${order.status === 'delivered' ? 'selected' : ''}>Delivered</option>
        </select>
      </div>
      <div class="form-group">
        <label>Total</label>
        <input type="text" value="Rs ${order.total.toLocaleString()}" readonly>
      </div>
      <div class="modal-footer">
        <button class="modal-footer save-btn" onclick="updateOrderStatus('${order.id}')">Update</button>
        <button class="modal-footer btn-secondary" onclick="document.getElementById('order-modal').classList.remove('open')">Close</button>
      </div>
    `;
  } catch (err) {
    showToast('Failed to load order', 'error');
  }
}

async function updateOrderStatus(orderId) {
  try {
    const status = document.getElementById('order-status').value;
    await api.patch(`/orders/${orderId}/status`, { status }, true);
    showToast('Order updated');
    document.getElementById('order-modal').classList.remove('open');
    loadOrders();
  } catch (err) {
    showToast('Failed to update order', 'error');
  }
}

function editProduct(productId) {
  showToast('Edit product feature coming soon', 'info');
}

async function deleteProduct(productId) {
  if (!confirm('Are you sure you want to deactivate this product?')) return;

  try {
    await api.delete(`/products/${productId}`, true);
    showToast('Product deactivated');
    loadProducts();
  } catch (err) {
    showToast('Failed to delete product', 'error');
  }
}

async function loadRiderDashboard() {
  requireAuth(['rider']);

  try {
    const orders = await api.get('/rider/orders', true);
    const container = document.querySelector('[data-section="rider-orders"]');
    if (!container) return;

    if (orders.length === 0) {
      container.innerHTML = '<p style="text-align:center;color:var(--text-secondary);">No orders assigned</p>';
      return;
    }

    container.innerHTML = orders.map(o => `
      <div class="stat-card">
        <h3>${o.shipping_address?.full_name}</h3>
        <p>${o.shipping_address?.address}</p>
        <p>${o.items.length} items · Rs ${o.total.toLocaleString()}</p>
        <button class="action-btn" onclick="updateRiderOrder('${o.id}', 'shipped')">Mark as Shipped</button>
        <button class="action-btn" onclick="updateRiderOrder('${o.id}', 'delivered')">Mark as Delivered</button>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load rider orders', err);
  }
}

async function updateRiderOrder(orderId, status) {
  try {
    await api.patch(`/rider/orders/${orderId}/status`, { status }, true);
    showToast('Status updated');
    loadRiderDashboard();
  } catch (err) {
    showToast('Failed to update status', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  
  if (page === 'admin-dashboard') loadAdminDashboard();
  else if (page === 'admin-products') loadProducts();
  else if (page === 'admin-orders') loadOrders();
  else if (page === 'rider-dashboard') loadRiderDashboard();
});
