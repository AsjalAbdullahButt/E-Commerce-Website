const PROMO_TYPES = ADMIN_CONFIG.PROMO_DISCOUNT_TYPES || [
  { value: 'percentage', label: 'Percentage' },
  { value: 'fixed', label: 'Fixed Amount' },
];

const promoState = {
  promos: [],
  filtered: [],
};

function promoToast(message, type = 'success') {
  let toast = document.getElementById('promo-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'promo-toast';
    toast.style.position = 'fixed';
    toast.style.right = '20px';
    toast.style.bottom = '20px';
    toast.style.zIndex = '9999';
    toast.style.maxWidth = '360px';
    toast.style.padding = '12px 16px';
    toast.style.borderRadius = '12px';
    toast.style.boxShadow = '0 12px 30px rgba(0,0,0,0.28)';
    toast.style.fontWeight = '600';
    toast.style.display = 'none';
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.style.display = 'block';
  toast.style.background = type === 'error' ? '#7f1d1d' : type === 'warning' ? '#78350f' : '#1f2937';
  toast.style.color = '#f8f4ea';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.style.display = 'none';
  }, 2600);
}

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

function formatDiscount(promo) {
  if (promo.discount_type === 'percentage') {
    return `${Number(promo.discount_value || 0)}%`;
  }
  return formatCurrency(promo.discount_value);
}

function formatExpiry(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-PK', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function isExpiringSoon(value) {
  if (!value) return false;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const days = (date.getTime() - Date.now()) / (1000 * 60 * 60 * 24);
  return days <= 7 && days >= 0;
}

function normalizeCode(value) {
  return String(value || '').trim().toUpperCase();
}

function ensureModal() {
  if (document.getElementById('promo-modal')) return;

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.id = 'promo-modal';

  const content = document.createElement('div');
  content.className = 'modal-content';

  const header = document.createElement('div');
  header.className = 'modal-header';
  const title = document.createElement('h3');
  title.className = 'modal-title';
  title.textContent = 'Create Promo';
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'modal-close';
  close.textContent = '×';
  close.addEventListener('click', closeModal);
  header.appendChild(title);
  header.appendChild(close);

  const form = document.createElement('form');
  form.id = 'promo-form';
  form.className = 'admin-form-section';

  const desc = document.createElement('p');
  desc.className = 'admin-section-desc';
  desc.textContent = 'Create a promo code with an explicit type and enforced validation rules.';

  const fields = document.createElement('div');
  fields.className = 'image-url-form';

  fields.appendChild(buildField('Promo Code', 'promo-code', 'text', 'SAVE10', 'Uppercase code used by customers'));
  fields.appendChild(buildField('Description', 'promo-description', 'text', 'Summer sale', 'Visible in admin only'));
  fields.appendChild(buildSelectField('Discount Type', 'promo-type', PROMO_TYPES));
  fields.appendChild(buildField('Discount Value', 'promo-value', 'number', '10', 'Percentage or fixed amount', { step: '0.01', min: '0.01' }));
  fields.appendChild(buildField('Minimum Order Value', 'promo-min-order', 'number', '0', 'Minimum cart total required', { step: '0.01', min: '0' }));
  fields.appendChild(buildField('Max Uses', 'promo-max-uses', 'number', '100', 'How many times the promo can be used', { step: '1', min: '1' }));
  fields.appendChild(buildField('Expiry Date', 'promo-expiry', 'datetime-local', '', 'When the promo stops working'));

  const footer = document.createElement('div');
  footer.className = 'modal-footer';
  const cancel = document.createElement('button');
  cancel.type = 'button';
  cancel.className = 'btn-secondary';
  cancel.textContent = 'Cancel';
  cancel.addEventListener('click', closeModal);
  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.className = 'btn-primary';
  submit.textContent = 'Create Promo';
  footer.appendChild(cancel);
  footer.appendChild(submit);

  form.appendChild(desc);
  form.appendChild(fields);
  form.appendChild(footer);

  content.appendChild(header);
  content.appendChild(form);
  modal.appendChild(content);
  document.body.appendChild(modal);

  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  form.addEventListener('submit', handleCreatePromo);
}

function buildField(labelText, id, type, placeholder, note, extraAttrs = {}) {
  const wrapper = document.createElement('div');
  wrapper.className = 'url-input-row';
  wrapper.style.flexDirection = 'column';
  wrapper.style.gap = '0.5rem';

  const label = document.createElement('label');
  label.setAttribute('for', id);
  label.textContent = labelText;

  const input = document.createElement('input');
  input.id = id;
  input.type = type;
  input.placeholder = placeholder;
  input.required = id !== 'promo-min-order';
  Object.entries(extraAttrs).forEach(([key, value]) => {
    input.setAttribute(key, value);
  });

  const helper = document.createElement('small');
  helper.style.color = 'var(--text-muted)';
  helper.textContent = note;

  wrapper.appendChild(label);
  wrapper.appendChild(input);
  wrapper.appendChild(helper);
  return wrapper;
}

function buildSelectField(labelText, id, options) {
  const wrapper = document.createElement('div');
  wrapper.className = 'url-input-row';
  wrapper.style.flexDirection = 'column';
  wrapper.style.gap = '0.5rem';

  const label = document.createElement('label');
  label.setAttribute('for', id);
  label.textContent = labelText;

  const select = document.createElement('select');
  select.id = id;
  select.className = 'filter-select';
  options.forEach((option) => {
    const item = document.createElement('option');
    item.value = option.value;
    item.textContent = option.label;
    select.appendChild(item);
  });

  wrapper.appendChild(label);
  wrapper.appendChild(select);
  return wrapper;
}

function openModal() {
  ensureModal();
  document.getElementById('promo-modal').classList.add('open');
}

function closeModal() {
  const modal = document.getElementById('promo-modal');
  if (modal) modal.classList.remove('open');
}

function getActiveFilter() {
  return document.getElementById('promo-status-filter')?.value || 'all';
}

function getSearchTerm() {
  return document.getElementById('promo-search')?.value.trim().toLowerCase() || '';
}

function updateSummary(promos) {
  const total = promos.length;
  const active = promos.filter((promo) => promo.is_active).length;
  const expiringSoon = promos.filter((promo) => isExpiringSoon(promo.expires_at)).length;
  const percentage = promos.filter((promo) => promo.discount_type === 'percentage').length;

  const summary = document.getElementById('promo-summary');
  if (!summary) return;

  summary.textContent = '';

  const cards = [
    ['Total Promos', total, 'All promos in the catalog'],
    ['Active', active, 'Currently usable by customers'],
    ['Percentage', percentage, 'Percentage-based discounts'],
    ['Expiring Soon', expiringSoon, 'Expires within 7 days'],
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

function renderPromos(promos) {
  const tbody = document.getElementById('promo-table-body');
  const emptyRow = document.getElementById('promo-empty-row');
  tbody.querySelectorAll('tr:not(#promo-empty-row)').forEach((row) => row.remove());

  if (promos.length === 0) {
    emptyRow.style.display = '';
    emptyRow.querySelector('td').colSpan = 9;
    emptyRow.querySelector('td').textContent = 'No promos yet';
    return;
  }

  emptyRow.style.display = 'none';

  promos.forEach((promo) => {
    const row = document.createElement('tr');

    const code = document.createElement('td');
    const codeBadge = document.createElement('span');
    codeBadge.className = 'audit-admin-badge';
    codeBadge.textContent = promo.code;
    code.appendChild(codeBadge);

    const description = document.createElement('td');
    description.textContent = promo.description || '-';

    const type = document.createElement('td');
    type.textContent = promo.discount_type;

    const discount = document.createElement('td');
    discount.textContent = formatDiscount(promo);

    const minOrder = document.createElement('td');
    minOrder.textContent = formatCurrency(promo.min_order);

    const expiry = document.createElement('td');
    expiry.textContent = formatExpiry(promo.expires_at);

    const usage = document.createElement('td');
    usage.textContent = `${promo.uses || 0} / ${promo.max_uses || 0}`;

    const status = document.createElement('td');
    const statusBadge = document.createElement('span');
    statusBadge.className = `audit-action-badge ${promo.is_active ? 'audit-action-neutral' : 'audit-action-critical'}`;
    statusBadge.textContent = promo.is_active ? 'Active' : 'Inactive';
    status.appendChild(statusBadge);

    const actions = document.createElement('td');
    const actionGroup = document.createElement('div');
    actionGroup.className = 'promo-action-group';

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'promo-action-btn promo-copy-btn';
    copyBtn.innerHTML = '<i class="fas fa-copy"></i><span>Copy</span>';
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(promo.code);
        copyBtn.classList.add('copied');
        copyBtn.innerHTML = '<i class="fas fa-check"></i><span>Copied</span>';
        promoToast(`Copied ${promo.code}`);
        clearTimeout(copyBtn._resetTimer);
        copyBtn._resetTimer = setTimeout(() => {
          copyBtn.classList.remove('copied');
          copyBtn.innerHTML = '<i class="fas fa-copy"></i><span>Copy</span>';
        }, 1600);
      } catch {
        promoToast('Copy failed', 'error');
      }
    });

    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'promo-action-btn promo-toggle-btn';
    toggleBtn.textContent = promo.is_active ? 'Deactivate' : 'Activate';
    toggleBtn.addEventListener('click', async () => {
      try {
        await adminAPI.updateDiscount(promo.id, { is_active: !promo.is_active });
        promoToast(`Promo ${promo.is_active ? 'deactivated' : 'activated'}`);
        await loadPromos();
      } catch (error) {
        promoToast(error.message || 'Failed to update promo', 'error');
      }
    });

    actionGroup.appendChild(copyBtn);
    actionGroup.appendChild(toggleBtn);
    actions.appendChild(actionGroup);

    row.appendChild(code);
    row.appendChild(description);
    row.appendChild(type);
    row.appendChild(discount);
    row.appendChild(minOrder);
    row.appendChild(expiry);
    row.appendChild(usage);
    row.appendChild(status);
    row.appendChild(actions);
    tbody.appendChild(row);
  });
}

function applyFilters() {
  const search = getSearchTerm();
  const status = getActiveFilter();

  promoState.filtered = promoState.promos.filter((promo) => {
    const matchesStatus = status === 'all'
      || (status === 'active' && promo.is_active)
      || (status === 'inactive' && !promo.is_active);

    const haystack = [promo.code, promo.description, promo.discount_type]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    const matchesSearch = !search || haystack.includes(search);
    return matchesStatus && matchesSearch;
  });

  renderPromos(promoState.filtered);
}

async function loadPromos() {
  try {
    const response = await adminAPI.getDiscounts(null, 100, 0);
    promoState.promos = response.data || [];
    updateSummary(promoState.promos);
    applyFilters();
  } catch (error) {
    promoToast(error.message || 'Failed to load promos', 'error');
  }
}

async function handleCreatePromo(event) {
  event.preventDefault();

  const code = normalizeCode(document.getElementById('promo-code').value);
  const description = document.getElementById('promo-description').value.trim();
  const discountType = document.getElementById('promo-type').value;
  const discountValue = Number(document.getElementById('promo-value').value);
  const minOrder = Number(document.getElementById('promo-min-order').value || 0);
  const maxUsage = Number(document.getElementById('promo-max-uses').value || 1);
  const expiryRaw = document.getElementById('promo-expiry').value;

  if (!code || !description || !expiryRaw) {
    promoToast('Please complete all required fields', 'warning');
    return;
  }

  if (!/^[A-Z0-9_-]{3,20}$/.test(code)) {
    promoToast('Promo code must be 3-20 characters and use only A-Z, 0-9, underscore, or hyphen', 'warning');
    return;
  }

  if (!Number.isFinite(discountValue) || discountValue <= 0) {
    promoToast('Discount value must be greater than 0', 'warning');
    return;
  }

  if (discountType === 'percentage' && discountValue > 100) {
    promoToast('Percentage discounts cannot exceed 100%', 'warning');
    return;
  }

  if (!Number.isFinite(maxUsage) || maxUsage < 1) {
    promoToast('Max usage must be at least 1', 'warning');
    return;
  }

  const expiryDate = new Date(expiryRaw);
  if (Number.isNaN(expiryDate.getTime()) || expiryDate <= new Date()) {
    promoToast('Expiry date must be in the future', 'warning');
    return;
  }

  try {
    const payload = {
      code,
      description,
      discount_type: discountType,
      discount_value: discountValue,
      max_usage: maxUsage,
      min_order_value: minOrder,
      expiry_date: expiryDate.toISOString(),
    };

    await adminAPI.createDiscount(payload);
    promoToast('Promo created successfully');
    closeModal();
    event.target.reset();
    await loadPromos();
  } catch (error) {
    promoToast(error.message || 'Failed to create promo', 'error');
  }
}

function bindEvents() {
  const createBtn = document.getElementById('create-promo-btn');
  if (createBtn) {
    createBtn.addEventListener('click', openModal);
  }

  const logoutBtn = document.getElementById('nav-logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      try {
        await adminAPI.logout();
      } catch {
        // fall through
      }
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.ADMIN_DATA);
      window.location.href = '../auth/login.html';
    });
  }

  const search = document.getElementById('promo-search');
  const status = document.getElementById('promo-status-filter');
  if (search) search.addEventListener('input', applyFilters);
  if (status) status.addEventListener('change', applyFilters);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeModal();
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  const admin = getAdminData();
  if (!admin || !['admin', 'super_admin'].includes(admin.role)) {
    window.location.replace('../auth/login.html');
    return;
  }

  ensureModal();
  bindEvents();
  await loadPromos();
});