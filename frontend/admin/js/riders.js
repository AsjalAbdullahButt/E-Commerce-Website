const riderState = {
  riders: [],
  activeCounts: {},
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

// showToast is defined once in shared/js/api.js and loaded before this file on every admin page.

function _onRiderModalKeydown(e) {
  if (e.key === 'Escape') closeRiderModal();
}

function openRiderModal() {
  document.getElementById('rider-form')?.reset();
  const modal = document.getElementById('rider-modal');
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.getElementById('rider-name')?.focus();
  document.addEventListener('keydown', _onRiderModalKeydown);
}

function closeRiderModal() {
  const modal = document.getElementById('rider-modal');
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.removeEventListener('keydown', _onRiderModalKeydown);
}

async function saveRider(event) {
  event.preventDefault();
  const submit = document.getElementById('rider-submit-btn');
  try {
    const payload = {
      name: document.getElementById('rider-name').value.trim(),
      email: document.getElementById('rider-email').value.trim(),
      password: document.getElementById('rider-password').value,
      phone: document.getElementById('rider-phone').value.trim(),
    };
    submit.disabled = true;
    submit.textContent = 'Creating...';
    await adminAPI.createRider(payload);
    showToast('Rider created successfully');
    closeRiderModal();
    await loadRiders();
  } catch (error) {
    showToast(error.message || 'Failed to create rider', 'error');
  } finally {
    submit.disabled = false;
    submit.textContent = 'Create Rider';
  }
}

function getSelectedStatus() {
  const value = document.getElementById('rider-status-filter')?.value || 'all';
  if (value === 'all') return null;
  return value === 'active';
}

function renderRiders(riders) {
  const tbody = document.getElementById('rider-table-body');
  const emptyRow = document.getElementById('rider-empty-row');
  tbody.querySelectorAll('tr:not(#rider-empty-row)').forEach((row) => row.remove());

  document.getElementById('riders-visible-count').textContent = `${riders.length} riders`;

  if (riders.length === 0) {
    emptyRow.style.display = '';
    emptyRow.querySelector('td').textContent = 'No riders match the current filter.';
    return;
  }
  emptyRow.style.display = 'none';

  riders.forEach((rider) => {
    const row = document.createElement('tr');
    row.dataset.riderId = rider.id;

    const nameCell = document.createElement('td');
    const meta = document.createElement('div'); meta.className = 'product-meta';
    const title = document.createElement('strong'); title.textContent = rider.name || 'Unnamed rider';
    const subtitle = document.createElement('small'); subtitle.textContent = rider.email || '';
    meta.appendChild(title); meta.appendChild(subtitle);
    nameCell.appendChild(meta);

    const phoneCell = document.createElement('td');
    phoneCell.textContent = rider.phone || '-';

    const availabilityCell = document.createElement('td');
    const availBadge = document.createElement('span');
    const availability = rider.status || 'offline';
    availBadge.className = `status-badge status-badge--${availability === 'available' ? 'success' : availability === 'busy' ? 'warning' : 'neutral'}`;
    availBadge.textContent = availability;
    availabilityCell.appendChild(availBadge);

    const activeCell = document.createElement('td');
    const count = riderState.activeCounts[rider.id];
    activeCell.textContent = count === undefined ? '...' : String(count);

    const statusCell = document.createElement('td');
    const statusBadge = document.createElement('span');
    statusBadge.className = `status-badge status-badge--${rider.is_active ? 'success' : 'danger'}`;
    statusBadge.textContent = rider.is_active ? 'Active' : 'Deactivated';
    statusCell.appendChild(statusBadge);

    const actionsCell = document.createElement('td');
    const actions = document.createElement('div'); actions.className = 'btn-group';
    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'promo-action-btn promo-toggle-btn';
    toggleBtn.textContent = rider.is_active ? 'Deactivate' : 'Activate';
    toggleBtn.addEventListener('click', () => toggleRiderActive(rider));
    actions.appendChild(toggleBtn);
    actionsCell.appendChild(actions);

    row.appendChild(nameCell);
    row.appendChild(phoneCell);
    row.appendChild(availabilityCell);
    row.appendChild(activeCell);
    row.appendChild(statusCell);
    row.appendChild(actionsCell);
    tbody.appendChild(row);
  });

  // Fill in active-delivery counts asynchronously so the table renders immediately.
  riders.forEach(async (rider) => {
    try {
      const response = await adminAPI.getRiderActiveOrders(rider.id);
      riderState.activeCounts[rider.id] = response.data.active_orders;
      const row = tbody.querySelector(`tr[data-rider-id="${rider.id}"]`);
      if (row) row.children[3].textContent = String(response.data.active_orders);
    } catch {
      // Non-critical — leave the placeholder.
    }
  });
}

async function toggleRiderActive(rider) {
  try {
    if (rider.is_active) {
      await adminAPI.deactivateRider(rider.id);
      showToast('Rider deactivated');
    } else {
      await adminAPI.activateRider(rider.id);
      showToast('Rider activated');
    }
    await loadRiders();
  } catch (error) {
    showToast(error.message || 'Failed to update rider', 'error');
  }
}

async function loadRiders() {
  try {
    const isActive = getSelectedStatus();
    const response = await adminAPI.getRiders(isActive);
    riderState.riders = response.data || [];
    renderRiders(riderState.riders);
  } catch (error) {
    showToast(error.message || 'Failed to load riders', 'error');
  }
}

function bindEvents() {
  document.getElementById('open-rider-modal-btn')?.addEventListener('click', openRiderModal);
  document.getElementById('close-rider-modal-btn')?.addEventListener('click', closeRiderModal);
  document.getElementById('cancel-rider-btn')?.addEventListener('click', closeRiderModal);
  document.getElementById('rider-form')?.addEventListener('submit', saveRider);
  document.getElementById('refresh-riders-btn')?.addEventListener('click', loadRiders);
  document.getElementById('rider-status-filter')?.addEventListener('change', loadRiders);
  document.getElementById('rider-modal')?.addEventListener('click', (event) => {
    if (event.target.id === 'rider-modal') closeRiderModal();
  });

  document.getElementById('nav-logout-btn')?.addEventListener('click', async () => {
    try { await adminAPI.logout(); } catch {}
    localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.ADMIN_DATA);
    window.location.href = './login.html';
  });
}

function initPage() {
  if (!requireAuth()) return;
  bindEvents();
  loadRiders();
}

document.addEventListener('DOMContentLoaded', initPage);
