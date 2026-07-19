const orderState = {
  orders: [],
  availableRiders: [],
};

const TERMINAL_STATUSES = ['delivered', 'cancelled', 'returned'];

const ORDER_STATUS_BADGE = { delivered: 'success', cancelled: 'danger', returned: 'warning' };

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
  // The access token lives in memory only (see js/admin-api.js) and is restored lazily on the
  // first API call, so it isn't checked here — only the cached (non-sensitive) profile.
  const adminData = getAdminData();
  if (!adminData) {
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

// showToast is defined once in shared/js/api.js and loaded before this file on every admin page.

function renderOrders(orders) {
  const tbody = document.getElementById('order-table-body');
  const emptyRow = document.getElementById('order-empty-row');
  tbody.querySelectorAll('tr:not(#order-empty-row)').forEach((row) => row.remove());

  document.getElementById('orders-visible-count').textContent = `${orders.length} visible`;

  if (orders.length === 0) {
    emptyRow.hidden = false;
    renderEmptyStateInto(emptyRow.querySelector('td'), {
      icon: 'fa-box-open',
      title: 'No orders found',
      message: 'No orders match the current filter.',
    });
    return;
  }
  emptyRow.hidden = true;

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
    statusBadge.className = `status-badge status-badge--${ORDER_STATUS_BADGE[order.status] || 'neutral'}`;
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
    document.getElementById('order-empty-row').hidden = true;
    showTableSkeleton(tbody, 8);
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
      clearTableSkeleton(tbody);
      const emptyRow = document.getElementById('order-empty-row');
      emptyRow.hidden = false;
      renderEmptyStateInto(emptyRow.querySelector('td'), {
        icon: 'fa-triangle-exclamation',
        title: 'Failed to load orders',
        message: 'Check your connection, then hit Refresh to try again.',
      });
    }
  }
}

function bindEvents() {
  document.getElementById('refresh-orders-btn')?.addEventListener('click', loadOrders);
  document.getElementById('order-status-filter')?.addEventListener('change', loadOrders);

  document.getElementById('export-orders-btn')?.addEventListener('click', async () => {
    try {
      await adminAPI.exportOrders();
    } catch (err) {
      showToast(err.message || 'Failed to export orders', 'error');
    }
  });

  document.getElementById('bulk-status-btn')?.addEventListener('click', () => {
    document.getElementById('bulk-status-file')?.click();
  });
  document.getElementById('bulk-status-file')?.addEventListener('change', async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const result = await adminAPI.bulkUpdateOrderStatus(file);
      const { updated, errors } = result.data;
      const summary = `Bulk update: ${updated} order(s) updated${errors.length ? `, ${errors.length} row error(s)` : ''}`;
      showToast(summary, errors.length ? 'warning' : 'success');
      if (errors.length) console.warn('Bulk status update row errors:', errors);
      await loadOrders();
    } catch (err) {
      showToast(err.message || 'Failed to bulk-update order status', 'error');
    } finally {
      event.target.value = '';
    }
  });
}

function initPage() {
  if (!requireAuth()) return;
  bindEvents();
  loadOrders();
}

document.addEventListener('DOMContentLoaded', initPage);
