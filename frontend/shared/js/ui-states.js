/* Shared loading-skeleton + empty-state helpers (plus small cross-page UI utilities).
   Plain global-scope script by design (no modules — see scripts/build-dist.js); load it with a
   <script> tag before the page's own JS, same pattern as shared/js/api.js. Pairs with
   .table-skeleton-row, .card-skeleton, .product-card-skeleton and .empty-state in
   shared/css/global.css. */

// Color-name → hex for product color swatches — previously copy-pasted into
// home.js, shop.js, and product.js.
const SWATCH_COLOR_MAP = {
  black: '#111111', white: '#f5f5f5', grey: '#888888', gray: '#888888',
  navy: '#1b2a4a', beige: '#d8c7a1', olive: '#5c5c33', maroon: '#5c1f2e',
};

function swatchColor(name) {
  const key = String(name || '').trim().toLowerCase();
  return SWATCH_COLOR_MAP[key] || key || '#888';
}

/** Fill a product grid with .product-card-skeleton placeholders (home + shop loading state). */
function renderProductCardSkeletons(container, count) {
  container.textContent = '';
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {
    const card = document.createElement('div');
    card.className = 'product-card-skeleton';
    const img = document.createElement('div'); img.className = 'skel-image skeleton';
    const line1 = document.createElement('div'); line1.className = 'skel-line skeleton';
    const line2 = document.createElement('div'); line2.className = 'skel-line price skeleton';
    card.appendChild(img); card.appendChild(line1); card.appendChild(line2);
    frag.appendChild(card);
  }
  container.appendChild(frag);
}

/**
 * Fill a tbody with shimmering placeholder rows matching the real table's column count.
 * Any previous skeleton rows are replaced; other rows (data rows, the hidden empty row)
 * are left alone — page renderers already clear those themselves.
 */
function showTableSkeleton(tbody, columnCount, rowCount = 5) {
  if (!tbody) return;
  clearTableSkeleton(tbody);
  const fragment = document.createDocumentFragment();
  for (let r = 0; r < rowCount; r += 1) {
    const row = document.createElement('tr');
    row.className = 'table-skeleton-row';
    row.setAttribute('aria-hidden', 'true');
    for (let c = 0; c < columnCount; c += 1) {
      const cell = document.createElement('td');
      const bar = document.createElement('div');
      bar.className = 'skeleton skel-bar';
      cell.appendChild(bar);
      row.appendChild(cell);
    }
    fragment.appendChild(row);
  }
  tbody.appendChild(fragment);
}

function clearTableSkeleton(tbody) {
  if (!tbody) return;
  tbody.querySelectorAll('.table-skeleton-row').forEach((row) => row.remove());
}

/**
 * Replace `container`'s content with the shared empty-state block
 * (.empty-state > .empty-state-icon + h3 + p). `icon` is a Font Awesome name
 * like "fa-box-open"; title/message are rendered as plain text (XSS-safe).
 */
function renderEmptyStateInto(container, { icon = 'fa-inbox', title = '', message = '' } = {}) {
  if (!container) return;
  container.textContent = '';
  const wrap = document.createElement('div');
  wrap.className = 'empty-state';
  const iconWrap = document.createElement('div');
  iconWrap.className = 'empty-state-icon';
  const iconEl = document.createElement('i');
  iconEl.className = `fas ${icon}`;
  iconEl.setAttribute('aria-hidden', 'true');
  iconWrap.appendChild(iconEl);
  wrap.appendChild(iconWrap);
  if (title) {
    const heading = document.createElement('h3');
    heading.textContent = title;
    wrap.appendChild(heading);
  }
  if (message) {
    const text = document.createElement('p');
    text.textContent = message;
    wrap.appendChild(text);
  }
  container.appendChild(wrap);
}
