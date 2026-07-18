const returnsState = {
  returns: [],
  resolvingId: null,
  resolvingAction: null,
};

function getAdminData() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || 'null');
  } catch {
    return null;
  }
}

function formatCurrency(value) {
  return `Rs ${Number(value || 0).toLocaleString('en-PK', { maximumFractionDigits: 2 })}`;
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-PK', { year: 'numeric', month: 'short', day: 'numeric' });
}

function updateSummary(returns) {
  const summary = document.getElementById('returns-summary');
  if (!summary) return;
  summary.textContent = '';

  const pending = returns.filter((r) => r.status === 'pending').length;
  const approved = returns.filter((r) => r.status === 'approved').length;
  const rejected = returns.filter((r) => r.status === 'rejected').length;

  const cards = [
    ['Pending Review', pending, 'Awaiting a decision'],
    ['Approved', approved, 'Refund issued, stock restored'],
    ['Rejected', rejected, 'Declined return requests'],
  ];

  cards.forEach(([label, value, note]) => {
    const card = document.createElement('div');
    card.className = 'stat-card';
    const info = document.createElement('div');
    info.className = 'stat-info';
    const heading = document.createElement('h3');
    heading.textContent = label;
    const metric = document.createElement('div');
    metric.className = 'stat-value';
    metric.textContent = String(value);
    const helper = document.createElement('small');
    helper.style.color = 'var(--text-muted)';
    helper.textContent = note;
    info.appendChild(heading);
    info.appendChild(metric);
    info.appendChild(helper);
    card.appendChild(info);
    summary.appendChild(card);
  });
}

function renderReturns(returns) {
  const tbody = document.getElementById('returns-table-body');
  const emptyRow = document.getElementById('returns-empty-row');
  tbody.querySelectorAll('tr:not(#returns-empty-row)').forEach((row) => row.remove());

  if (returns.length === 0) {
    emptyRow.style.display = '';
    emptyRow.querySelector('td').textContent = 'No return requests for this filter';
    return;
  }
  emptyRow.style.display = 'none';

  returns.forEach((rr) => {
    const row = document.createElement('tr');

    const orderTd = document.createElement('td');
    const orderBadge = document.createElement('span');
    orderBadge.className = 'code-badge';
    orderBadge.textContent = `${rr.order_id.substring(0, 8)}...`;
    orderTd.appendChild(orderBadge);

    const reasonTd = document.createElement('td');
    reasonTd.textContent = rr.reason;
    reasonTd.style.maxWidth = '260px';

    const requestedTd = document.createElement('td');
    requestedTd.textContent = formatDate(rr.created_at);

    const statusTd = document.createElement('td');
    const statusBadge = document.createElement('span');
    const statusClass = { pending: 'neutral', approved: 'success', rejected: 'danger' }[rr.status] || 'neutral';
    statusBadge.className = `status-badge status-badge--${statusClass}`;
    statusBadge.textContent = rr.status;
    statusTd.appendChild(statusBadge);

    const refundTd = document.createElement('td');
    refundTd.textContent = rr.refund_amount != null ? formatCurrency(rr.refund_amount) : '-';

    const actionsTd = document.createElement('td');
    if (rr.status === 'pending') {
      const actionGroup = document.createElement('div');
      actionGroup.className = 'promo-action-group';

      const approveBtn = document.createElement('button');
      approveBtn.type = 'button';
      approveBtn.className = 'promo-action-btn';
      approveBtn.innerHTML = '<i class="fas fa-check"></i><span>Approve</span>';
      approveBtn.addEventListener('click', () => openResolveModal(rr, 'approve'));

      const rejectBtn = document.createElement('button');
      rejectBtn.type = 'button';
      rejectBtn.className = 'promo-action-btn';
      rejectBtn.innerHTML = '<i class="fas fa-times"></i><span>Reject</span>';
      rejectBtn.addEventListener('click', () => openResolveModal(rr, 'reject'));

      actionGroup.appendChild(approveBtn);
      actionGroup.appendChild(rejectBtn);
      actionsTd.appendChild(actionGroup);
    } else {
      actionsTd.textContent = rr.admin_note || '-';
      actionsTd.style.color = 'var(--text-muted)';
    }

    row.appendChild(orderTd);
    row.appendChild(reasonTd);
    row.appendChild(requestedTd);
    row.appendChild(statusTd);
    row.appendChild(refundTd);
    row.appendChild(actionsTd);
    tbody.appendChild(row);
  });
}

async function loadReturns() {
  const status = document.getElementById('returns-status-filter')?.value || 'pending';
  try {
    const response = await adminAPI.getReturns(status === 'all' ? null : status, 100, 0);
    returnsState.returns = response.data || [];
    updateSummary(returnsState.returns);
    renderReturns(returnsState.returns);
  } catch (error) {
    showToast(error.message || 'Failed to load return requests', 'error');
  }
}

function openResolveModal(rr, action) {
  returnsState.resolvingId = rr.id;
  returnsState.resolvingAction = action;

  const modal = document.getElementById('resolve-modal');
  document.getElementById('resolve-modal-title').textContent = action === 'approve' ? 'Approve Return Request' : 'Reject Return Request';
  document.getElementById('resolve-refund-amount').closest('.url-input-row').style.display = action === 'approve' ? '' : 'none';
  document.getElementById('resolve-refund-amount').value = '';
  document.getElementById('resolve-admin-note').value = '';

  const confirmBtn = document.getElementById('resolve-modal-confirm');
  confirmBtn.textContent = action === 'approve' ? 'Approve & Refund' : 'Reject Request';

  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
}

function closeResolveModal() {
  const modal = document.getElementById('resolve-modal');
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  returnsState.resolvingId = null;
  returnsState.resolvingAction = null;
}

async function confirmResolve() {
  const { resolvingId, resolvingAction } = returnsState;
  if (!resolvingId || !resolvingAction) return;

  const refundRaw = document.getElementById('resolve-refund-amount').value;
  const refundAmount = resolvingAction === 'approve' && refundRaw ? Number(refundRaw) : null;
  const adminNote = document.getElementById('resolve-admin-note').value.trim() || null;

  try {
    await adminAPI.resolveReturn(resolvingId, resolvingAction, adminNote, refundAmount);
    showToast(`Return request ${resolvingAction === 'approve' ? 'approved' : 'rejected'}`);
    closeResolveModal();
    await loadReturns();
  } catch (error) {
    showToast(error.message || 'Failed to resolve return request', 'error');
  }
}

function bindEvents() {
  document.getElementById('refresh-returns-btn')?.addEventListener('click', loadReturns);
  document.getElementById('returns-status-filter')?.addEventListener('change', loadReturns);

  document.getElementById('resolve-modal-close')?.addEventListener('click', closeResolveModal);
  document.getElementById('resolve-modal-cancel')?.addEventListener('click', closeResolveModal);
  document.getElementById('resolve-modal-confirm')?.addEventListener('click', confirmResolve);
  document.getElementById('resolve-modal')?.addEventListener('click', (event) => {
    if (event.target.id === 'resolve-modal') closeResolveModal();
  });

  document.getElementById('nav-logout-btn')?.addEventListener('click', async () => {
    try {
      await adminAPI.logout();
    } catch {
      // fall through
    }
    localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.ADMIN_DATA);
    window.location.href = './login.html';
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeResolveModal();
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const admin = getAdminData();
  if (!admin) {
    window.location.replace('./login.html');
    return;
  }

  bindEvents();
  await loadReturns();
});
