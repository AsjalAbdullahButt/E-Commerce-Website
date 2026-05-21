const productState = {
  products: [],
  filtered: [],
  editingId: null,
};

const PRODUCT_CATEGORIES = ADMIN_CONFIG.CATEGORIES || [];

function getAdminData() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || 'null');
  } catch {
    return null;
  }
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

function slugify(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

function showToast(message, type = 'success') {
  let toast = document.getElementById('product-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'product-toast';
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
  toast.style.background = type === 'error' ? '#7f1d1d' : type === 'warning' ? '#78350f' : '#1f2937';
  toast.style.color = '#f8f4ea';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.style.display = 'none';
  }, 2600);
}

function requireAuth() {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
  const adminData = getAdminData();
  if (!token || !adminData) {
    window.location.replace('./login.html');
    return false;
  }
  if (!['admin', 'super_admin', 'manager'].includes(adminData.role)) {
    window.location.replace('../customer/index.html');
    return false;
  }
  return true;
}

function getCategoryLabel(value) {
  return (PRODUCT_CATEGORIES.find((category) => category.value === value) || {}).label || value || '-';
}

function getSelectedCategory() {
  const value = document.getElementById('product-category-filter')?.value || 'all';
  return value === 'all' ? null : value;
}

function getSelectedStatus() {
  const value = document.getElementById('product-status-filter')?.value || 'all';
  if (value === 'all') return null;
  return value === 'active';
}

function getSearchTerm() {
  return document.getElementById('product-search')?.value.trim().toLowerCase() || '';
}

function isLowStock(product) {
  return Number(product.total_stock || 0) <= 10;
}

function getDiscountedPrice(product) {
  const price = Number(product.price || 0);
  const discount = Number(product.discount_percentage || 0);
  return price - (price * discount / 100);
}

function ensureRows(kind) {
  const containerId = kind === 'variant' ? 'product-variant-rows' : 'product-image-rows';
  const container = document.getElementById(containerId);
  if (!container) return null;
  if (container.children.length === 0) {
    container.appendChild(kind === 'variant' ? createVariantRow() : createImageRow());
  }
  return container;
}

function createImageRow(url = '') {
  const row = document.createElement('div');
  row.className = 'builder-row compact-row image-row';

  const field = document.createElement('div');
  field.className = 'builder-field';
  const label = document.createElement('label');
  label.textContent = 'Image URL';
  const input = document.createElement('input');
  input.type = 'url';
  input.placeholder = 'https://example.com/image.jpg';
  input.value = url;
  field.appendChild(label);
  field.appendChild(input);

  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'builder-icon-button';
  remove.innerHTML = '<i class="fas fa-trash"></i>';
  remove.addEventListener('click', () => {
    row.remove();
    ensureRows('image');
  });

  row.appendChild(field);
  row.appendChild(remove);
  return row;
}

function createVariantRow(variant = {}) {
  const row = document.createElement('div');
  row.className = 'builder-row variant-row';

  const sizeField = document.createElement('div');
  sizeField.className = 'builder-field';
  const sizeLabel = document.createElement('label');
  sizeLabel.textContent = 'Size';
  const sizeInput = document.createElement('input');
  sizeInput.type = 'text';
  sizeInput.placeholder = 'M';
  sizeInput.maxLength = 12;
  sizeInput.value = variant.size || '';
  sizeField.appendChild(sizeLabel);
  sizeField.appendChild(sizeInput);

  const colorField = document.createElement('div');
  colorField.className = 'builder-field';
  const colorLabel = document.createElement('label');
  colorLabel.textContent = 'Color';
  const colorInput = document.createElement('input');
  colorInput.type = 'text';
  colorInput.placeholder = 'Jet Black';
  colorInput.maxLength = 24;
  colorInput.value = variant.color || '';
  colorField.appendChild(colorLabel);
  colorField.appendChild(colorInput);

  const skuField = document.createElement('div');
  skuField.className = 'builder-field';
  const skuLabel = document.createElement('label');
  skuLabel.textContent = 'SKU';
  const skuInput = document.createElement('input');
  skuInput.type = 'text';
  skuInput.placeholder = 'sku-auto-001';
  skuInput.maxLength = 48;
  skuInput.value = variant.sku || '';
  skuField.appendChild(skuLabel);
  skuField.appendChild(skuInput);

  const stockField = document.createElement('div');
  stockField.className = 'builder-field';
  const stockLabel = document.createElement('label');
  stockLabel.textContent = 'Stock';
  const stockInput = document.createElement('input');
  stockInput.type = 'number';
  stockInput.min = '0';
  stockInput.step = '1';
  stockInput.placeholder = '24';
  stockInput.value = Number.isFinite(Number(variant.stock)) ? Number(variant.stock) : 0;
  stockField.appendChild(stockLabel);
  stockField.appendChild(stockInput);

  const actions = document.createElement('button');
  actions.type = 'button';
  actions.className = 'builder-icon-button';
  actions.innerHTML = '<i class="fas fa-minus"></i>';
  actions.addEventListener('click', () => {
    if (document.querySelectorAll('#product-variant-rows .variant-row').length === 1) {
      showToast('Keep at least one product variant.', 'warning');
      return;
    }
    row.remove();
    updateStockSummary();
  });

  [sizeInput, colorInput, stockInput].forEach((input) => {
    input.addEventListener('input', updateStockSummary);
  });

  row.appendChild(sizeField);
  row.appendChild(colorField);
  row.appendChild(skuField);
  row.appendChild(stockField);
  row.appendChild(actions);
  return row;
}

function updateStockSummary() {
  const total = Array.from(document.querySelectorAll('#product-variant-rows .variant-row input[type="number"]'))
    .reduce((sum, input) => sum + (Number(input.value) || 0), 0);
  const stockLabel = document.getElementById('product-stock-total');
  if (stockLabel) {
    stockLabel.textContent = `${total} units`;
  }
}

function populateCategories() {
  const select = document.getElementById('product-category');
  const filter = document.getElementById('product-category-filter');
  if (!select || !filter) return;

  select.textContent = '';
  filter.querySelectorAll('option:not([value="all"])').forEach((option) => option.remove());

  PRODUCT_CATEGORIES.forEach((category) => {
    const option = document.createElement('option');
    option.value = category.value;
    option.textContent = category.label;
    select.appendChild(option);

    const filterOption = document.createElement('option');
    filterOption.value = category.value;
    filterOption.textContent = category.label;
    filter.appendChild(filterOption);
  });
}

function clearProductForm() {
  document.getElementById('product-form')?.reset();
  document.getElementById('product-id').value = '';
  document.getElementById('product-tags').value = '';

  const imageRows = document.getElementById('product-image-rows');
  const variantRows = document.getElementById('product-variant-rows');
  if (imageRows) {
    imageRows.textContent = '';
    imageRows.appendChild(createImageRow());
  }
  if (variantRows) {
    variantRows.textContent = '';
    variantRows.appendChild(createVariantRow());
  }

  document.getElementById('product-submit-btn').textContent = 'Create Product';
  document.getElementById('product-modal-title').textContent = 'Add Product';
  document.getElementById('product-modal-copy').textContent = 'Build a product record with explicit variants, images, and tags.';
  updateStockSummary();
}

function openProductModal(product = null) {
  const modal = document.getElementById('product-modal');
  if (!modal) return;

  if (!product) {
    productState.editingId = null;
    clearProductForm();
  } else {
    productState.editingId = product.id;
    document.getElementById('product-id').value = product.id || '';
    document.getElementById('product-name').value = product.name || '';
    document.getElementById('product-category').value = product.category || PRODUCT_CATEGORIES[0]?.value || '';
    document.getElementById('product-price').value = Number(product.price || 0);
    document.getElementById('product-discount').value = Number(product.discount_percentage || 0);
    document.getElementById('product-description').value = product.description || '';
    document.getElementById('product-tags').value = Array.isArray(product.tags) ? product.tags.join(', ') : '';

    const imageRows = document.getElementById('product-image-rows');
    const variantRows = document.getElementById('product-variant-rows');
    imageRows.textContent = '';
    variantRows.textContent = '';

    const images = Array.isArray(product.images) && product.images.length ? product.images : [''];
    images.forEach((image) => imageRows.appendChild(createImageRow(image)));

    const variants = Array.isArray(product.variants) && product.variants.length ? product.variants : [{}];
    variants.forEach((variant) => variantRows.appendChild(createVariantRow(variant)));

    document.getElementById('product-submit-btn').textContent = 'Save Product';
    document.getElementById('product-modal-title').textContent = 'Edit Product';
    document.getElementById('product-modal-copy').textContent = 'Adjust variants, pricing, and presentation without leaving the catalog workspace.';
    updateStockSummary();
  }

  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
}

function closeProductModal() {
  const modal = document.getElementById('product-modal');
  if (!modal) return;
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
}

function getProductPayload() {
  const name = document.getElementById('product-name').value.trim();
  const description = document.getElementById('product-description').value.trim();
  const category = document.getElementById('product-category').value;
  const price = Number(document.getElementById('product-price').value);
  const discount_percentage = Number(document.getElementById('product-discount').value || 0);
  const tags = document.getElementById('product-tags').value
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean);

  if (!name || !description || !category) {
    throw new Error('Name, description, and category are required.');
  }
  if (!Number.isFinite(price) || price <= 0) {
    throw new Error('Price must be greater than 0.');
  }
  if (!Number.isFinite(discount_percentage) || discount_percentage < 0 || discount_percentage > 100) {
    throw new Error('Discount must be between 0 and 100.');
  }

  const variants = Array.from(document.querySelectorAll('#product-variant-rows .variant-row')).map((row, index) => {
    const inputs = row.querySelectorAll('input');
    const size = inputs[0].value.trim();
    const color = inputs[1].value.trim();
    let sku = inputs[2].value.trim();
    const stock = Number(inputs[3].value || 0);

    if (!size || !color) {
      throw new Error(`Variant ${index + 1} needs both size and color.`);
    }
    if (!sku) {
      sku = `${slugify(name)}-${slugify(size)}-${slugify(color)}-${index + 1}`.replace(/-{2,}/g, '-');
    }
    if (!Number.isInteger(stock) || stock < 0) {
      throw new Error(`Variant ${index + 1} needs a non-negative stock value.`);
    }

    return { size, color, sku, stock };
  });

  const skuSet = new Set();
  variants.forEach((variant) => {
    if (skuSet.has(variant.sku)) {
      throw new Error('Each variant SKU must be unique.');
    }
    skuSet.add(variant.sku);
  });

  const images = Array.from(document.querySelectorAll('#product-image-rows input[type="url"]'))
    .map((input) => input.value.trim())
    .filter(Boolean);

  return {
    name,
    description,
    category,
    price,
    discount_percentage,
    tags,
    images,
    variants,
  };
}

async function saveProduct(event) {
  event.preventDefault();

  try {
    const payload = getProductPayload();
    const submit = document.getElementById('product-submit-btn');
    submit.disabled = true;
    submit.textContent = productState.editingId ? 'Saving...' : 'Creating...';

    if (productState.editingId) {
      await adminAPI.updateProduct(productState.editingId, payload);
      showToast('Product updated successfully');
    } else {
      await adminAPI.createProduct(payload);
      showToast('Product created successfully');
    }

    closeProductModal();
    await loadProducts();
  } catch (error) {
    showToast(error.message || 'Failed to save product', 'error');
  } finally {
    const submit = document.getElementById('product-submit-btn');
    submit.disabled = false;
    submit.textContent = productState.editingId ? 'Save Product' : 'Create Product';
  }
}

function matchesSearch(product, term) {
  if (!term) return true;
  const haystack = [
    product.name,
    product.description,
    product.category,
    ...(Array.isArray(product.tags) ? product.tags : []),
    ...(Array.isArray(product.variants) ? product.variants.flatMap((variant) => [variant.size, variant.color, variant.sku]) : []),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(term);
}

function updateSummary(products) {
  const summary = document.getElementById('product-summary');
  if (!summary) return;
  summary.textContent = '';

  const activeCount = products.filter((product) => product.is_active).length;
  const lowStockCount = products.filter((product) => isLowStock(product)).length;
  const avgPrice = products.length
    ? products.reduce((sum, product) => sum + Number(product.price || 0), 0) / products.length
    : 0;

  const cards = [
    { label: 'Total Products', value: products.length, note: 'Products currently in the catalog' },
    { label: 'Active', value: activeCount, note: 'Visible to shoppers' },
    { label: 'Low Stock', value: lowStockCount, note: 'Requires inventory review' },
    { label: 'Average Price', value: formatCurrency(avgPrice), note: 'Across the loaded product set' },
  ];

  cards.forEach((cardData) => {
    const card = document.createElement('div');
    card.className = 'stat-card summary-card';

    const label = document.createElement('div');
    label.className = 'stat-label';
    label.textContent = cardData.label;

    const value = document.createElement('div');
    value.className = 'stat-value';
    value.textContent = String(cardData.value);

    const note = document.createElement('div');
    note.className = 'summary-note';
    note.textContent = cardData.note;

    card.appendChild(label);
    card.appendChild(value);
    card.appendChild(note);
    summary.appendChild(card);
  });
}

function renderProducts(products) {
  const tbody = document.getElementById('product-table-body');
  const emptyRow = document.getElementById('product-empty-row');
  tbody.querySelectorAll('tr:not(#product-empty-row)').forEach((row) => row.remove());

  document.getElementById('products-visible-count').textContent = `${products.length} visible`;

  if (products.length === 0) {
    emptyRow.style.display = '';
    emptyRow.querySelector('td').textContent = 'No products match the current filters.';
    emptyRow.querySelector('td').colSpan = 7;
    return;
  }

  emptyRow.style.display = 'none';

  products.forEach((product) => {
    const row = document.createElement('tr');

    const productCell = document.createElement('td');
    const meta = document.createElement('div');
    meta.className = 'product-meta';
    const title = document.createElement('strong');
    title.textContent = product.name || 'Untitled product';
    const subtitle = document.createElement('small');
    subtitle.textContent = `${Array.isArray(product.tags) ? product.tags.length : 0} tags • ${formatDate(product.updated_at)}`;
    meta.appendChild(title);
    meta.appendChild(subtitle);
    productCell.appendChild(meta);

    const categoryCell = document.createElement('td');
    categoryCell.textContent = getCategoryLabel(product.category);

    const priceCell = document.createElement('td');
    const priceWrap = document.createElement('div');
    priceWrap.className = 'product-meta';
    const basePrice = document.createElement('strong');
    basePrice.textContent = formatCurrency(product.price);
    priceWrap.appendChild(basePrice);
    if (Number(product.discount_percentage || 0) > 0) {
      const discounted = document.createElement('small');
      discounted.textContent = `After discount: ${formatCurrency(getDiscountedPrice(product))}`;
      priceWrap.appendChild(discounted);
    }
    priceCell.appendChild(priceWrap);

    const stockCell = document.createElement('td');
    const stockBadge = document.createElement('span');
    stockBadge.className = `badge ${Number(product.total_stock || 0) === 0 ? 'out-of-stock' : isLowStock(product) ? 'low-stock' : 'healthy'}`;
    stockBadge.textContent = `${Number(product.total_stock || 0)} units`;
    stockCell.appendChild(stockBadge);

    const variantsCell = document.createElement('td');
    variantsCell.textContent = `${Array.isArray(product.variants) ? product.variants.length : 0} variants`;

    const statusCell = document.createElement('td');
    const statusBadge = document.createElement('span');
    statusBadge.className = `badge ${product.is_active ? 'active' : 'inactive'}`;
    statusBadge.textContent = product.is_active ? 'Active' : 'Inactive';
    statusCell.appendChild(statusBadge);

    const actionsCell = document.createElement('td');
    const actions = document.createElement('div');
    actions.className = 'btn-group';

    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'promo-action-btn promo-copy-btn';
    editBtn.innerHTML = '<i class="fas fa-pen"></i><span>Edit</span>';
    editBtn.addEventListener('click', () => openProductModal(product));

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'promo-action-btn promo-toggle-btn';
    deleteBtn.innerHTML = '<i class="fas fa-trash"></i><span>Delete</span>';
    deleteBtn.addEventListener('click', () => deleteProduct(product.id));

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);
    actionsCell.appendChild(actions);

    row.appendChild(productCell);
    row.appendChild(categoryCell);
    row.appendChild(priceCell);
    row.appendChild(stockCell);
    row.appendChild(variantsCell);
    row.appendChild(statusCell);
    row.appendChild(actionsCell);
    tbody.appendChild(row);
  });
}

function applyFilters() {
  const searchTerm = getSearchTerm();
  const category = getSelectedCategory();
  const isActive = getSelectedStatus();

  const filtered = productState.products.filter((product) => {
    const matchesCategory = category === null || product.category === category;
    const matchesStatus = isActive === null || Boolean(product.is_active) === isActive;
    return matchesCategory && matchesStatus && matchesSearch(product, searchTerm);
  });

  productState.filtered = filtered;
  updateSummary(productState.products);
  renderProducts(filtered);
}

async function loadProducts() {
  const tbody = document.getElementById('product-table-body');
  if (tbody && productState.products.length === 0) {
    tbody.querySelector('#product-empty-row td').textContent = 'Loading products...';
  }

  try {
    const category = getSelectedCategory();
    const isActive = getSelectedStatus();
    const response = await adminAPI.getProducts(category, isActive, 100, 0);
    productState.products = response.data || [];
    applyFilters();
  } catch (error) {
    showToast(error.message || 'Failed to load products', 'error');
    if (tbody) {
      const emptyRow = document.getElementById('product-empty-row');
      emptyRow.style.display = '';
      emptyRow.querySelector('td').textContent = 'Failed to load products.';
      emptyRow.querySelector('td').colSpan = 7;
    }
  }
}

async function deleteProduct(productId) {
  if (!confirm('Delete this product? This action will archive the record.')) return;

  try {
    await adminAPI.deleteProduct(productId);
    showToast('Product deleted successfully');
    await loadProducts();
  } catch (error) {
    showToast(error.message || 'Failed to delete product', 'error');
  }
}

function bindEvents() {
  document.getElementById('open-product-modal-btn')?.addEventListener('click', () => openProductModal());
  document.getElementById('close-product-modal-btn')?.addEventListener('click', closeProductModal);
  document.getElementById('cancel-product-btn')?.addEventListener('click', closeProductModal);
  document.getElementById('product-form')?.addEventListener('submit', saveProduct);
  document.getElementById('refresh-products-btn')?.addEventListener('click', loadProducts);
  document.getElementById('product-search')?.addEventListener('input', applyFilters);
  document.getElementById('product-category-filter')?.addEventListener('change', loadProducts);
  document.getElementById('product-status-filter')?.addEventListener('change', loadProducts);
  document.getElementById('add-image-row-btn')?.addEventListener('click', () => {
    document.getElementById('product-image-rows').appendChild(createImageRow());
  });
  document.getElementById('add-variant-row-btn')?.addEventListener('click', () => {
    document.getElementById('product-variant-rows').appendChild(createVariantRow());
    updateStockSummary();
  });
  document.getElementById('product-modal')?.addEventListener('click', (event) => {
    if (event.target.id === 'product-modal') {
      closeProductModal();
    }
  });

  document.getElementById('nav-logout-btn')?.addEventListener('click', async () => {
    try {
      await adminAPI.logout();
    } catch {
      // Ignore logout network errors and clear local state anyway.
    }
    localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.ADMIN_DATA);
    window.location.href = './login.html';
  });
}

function initPage() {
  if (!requireAuth()) return;
  populateCategories();
  bindEvents();
  clearProductForm();
  loadProducts();
}

document.addEventListener('DOMContentLoaded', initPage);