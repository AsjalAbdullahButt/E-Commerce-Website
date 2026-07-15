const orderState = {
  orders: [],
  availableRiders: [],
};

const TERMINAL_STATUSES = ['delivered', 'cancelled', 'returned'];

// Mirrors backend/utils/order_transitions.py — kept in sync manually since the admin UI needs to
// know which "advance status" actions to offer without a round trip.
const VALID_TRANSITIONS = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['packed', 'cancelled'],
  packed: ['shipped', 'cancelled'],
  shipped: ['delivered'],
  delivered: ['returned'],
  cancelled: [],
  returned: [],
};

function getAdminData() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || 'null');
  } catch {
    return null;
  }
}

function requireAuth() {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
  const adminData = getAdminData();
  if (!token || !adminData) {
    window.location.replace('./login.html');
    return false;
  }
  return true;
}

function formatCurrency(value) {
  return `Rs ${Number(value || 0).toLocaleString('en-PK', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-PK', { year: 'numeric', month: 'short', day: 'numeric' });
}

function showToast(message, type = 'success') {
  let toast = document.getElementById('order-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'order-toast';
    toast.style.position = 'fixed';
    toast.style.right = '20px';
    toast.style.bottom = '20px';
    toast.style.zIndex = '9999';
    toast.style.maxWidth = '380px';
    toast.style.padding = '12px 16px';
    toast.style.borderRadius = '12px';
    toast.style.boxShadow = '0 12px 30px rgba(0,0,0,0.28)';
    toast.style.fontWeight = '600';
    toast.style.display = 'none';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.display = 'block';
  toast.style.background = type === 'error' ? '#7f1d1d' : '#1f2937';
  toast.style.color = '#f8f4ea';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.display = 'none'; }, 2600);
}

function renderOrders(orders) {
  const tbody = document.getElementById('order-table-body');
  const emptyRow = document.getElementById('order-empty-row');
  tbody.querySelectorAll('tr:not(#order-empty-row)').forEach((row) => row.remove());

  document.getElementById('orders-visible-count').textContent = `${orders.length} visible`;

  if (orders.length === 0) {
    emptyRow.style.display = '';
    emptyRow.querySelector('td').textContent = 'No orders match the current filter.';
    return;
  }
  emptyRow.style.display = 'none';

  orders.forEach((order) => {
    const row = document.createElement('tr');

    const idCell = document.createElement('td');
    idCell.textContent = `#${(order.id || '').slice(0, 8)}`;

    const customerCell = document.createElement('td');
    customerCell.textContent = order.shipping_address?.full_name || order.user_id?.slice(0, 8) || '-';

    const itemsCell = document.createElement('td');
    itemsCell.textContent = `${(order.items || []).length} item(s)`;

    const totalCell = document.createElement('td');
    totalCell.textContent = formatCurrency(order.total);

    const statusCell = document.createElement('td');
    const statusBadge = document.createElement('span');
    statusBadge.className = `badge ${order.status === 'delivered' ? 'active' : order.status === 'cancelled' ? 'out-of-stock' : ''}`;
    statusBadge.textContent = order.status;
    statusCell.appendChild(statusBadge);

    const riderCell = document.createElement('td');
    if (!TERMINAL_STATUSES.includes(order.status) && orderState.availableRiders.length > 0) {
      const select = document.createElement('select');
      select.className = 'filter-select';
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = order.rider_id ? `Assigned: ${order.rider_id.slice(0, 8)}` : 'Unassigned';
      select.appendChild(placeholder);
      orderState.availableRiders.forEach((rider) => {
        const option = document.createElement('option');
        option.value = rider.id;
        option.textContent = rider.name;
        if (rider.id === order.rider_id) option.selected = true;
        select.appendChild(option);
      });
      select.addEventListener('change', () => {
        if (select.value) assignRider(order.id, select.value);
      });
      riderCell.appendChild(select);
    } else {
      riderCell.textContent = order.rider_id ? order.rider_id.slice(0, 8) : 'Unassigned';
    }

    const placedCell = document.createElement('td');
    placedCell.textContent = formatDate(order.created_at);

    const actionsCell = document.createElement('td');
    const actions = document.createElement('div');
    actions.className = 'btn-group';

    const nextStatuses = VALID_TRANSITIONS[order.status] || [];
    nextStatuses.forEach((next) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'promo-action-btn promo-copy-btn';
      btn.textContent = next === 'cancelled' ? 'Cancel' : `Mark ${next}`;
      btn.addEventListener('click', () => updateOrderStatus(order.id, next));
      actions.appendChild(btn);
    });
    if (nextStatuses.length === 0) {
      const span = document.createElement('span');
      span.style.color = 'var(--text-secondary)';
      span.textContent = 'No actions';
      actions.appendChild(span);
    }

    actionsCell.appendChild(actions);

    row.appendChild(idCell);
    row.appendChild(customerCell);
    row.appendChild(itemsCell);
    row.appendChild(totalCell);
    row.appendChild(statusCell);
    row.appendChild(riderCell);
    row.appendChild(placedCell);
    row.appendChild(actionsCell);
    tbody.appendChild(row);
  });
}

async function updateOrderStatus(orderId, status) {
  try {
    await adminAPI.updateOrderStatus(orderId, status);
    showToast(`Order marked ${status}`);
    await loadOrders();
  } catch (error) {
    showToast(error.message || 'Failed to update order status', 'error');
  }
}

async function assignRider(orderId, riderId) {
  try {
    await adminAPI.assignRider(orderId, riderId);
    showToast('Rider assigned');
    await loadOrders();
  } catch (error) {
    showToast(error.message || 'Failed to assign rider', 'error');
    await loadOrders();
  }
}

async function loadAvailableRiders() {
  try {
    const response = await adminAPI.getRiders(true);
    orderState.availableRiders = (response.data || []).filter((r) => r.status !== 'offline');
  } catch {
    orderState.availableRiders = [];
  }
}

async function loadOrders() {
  const tbody = document.getElementById('order-table-body');
  if (tbody && orderState.orders.length === 0) {
    tbody.querySelector('#order-empty-row td').textContent = 'Loading orders...';
  }
  try {
    const status = document.getElementById('order-status-filter')?.value || null;
    const [response] = await Promise.all([
      adminAPI.getOrders(status, null, 100, 0),
      loadAvailableRiders(),
    ]);
    orderState.orders = response.data || [];
    renderOrders(orderState.orders);
  } catch (error) {
    showToast(error.message || 'Failed to load orders', 'error');
    if (tbody) {
      const emptyRow = document.getElementById('order-empty-row');
      emptyRow.style.display = '';
      emptyRow.querySelector('td').textContent = 'Failed to load orders.';
    }
  }
}

function bindEvents() {
  document.getElementById('refresh-orders-btn')?.addEventListener('click', loadOrders);
  document.getElementById('order-status-filter')?.addEventListener('change', loadOrders);
}

function initPage() {
  if (!requireAuth()) return;
  bindEvents();
  loadOrders();
}

document.addEventListener('DOMContentLoaded', initPage);
