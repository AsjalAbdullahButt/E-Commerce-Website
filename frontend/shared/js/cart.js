// === CART.JS ===
// Single source for all cart logic

const CART_KEY = 'ecom_cart';

function getCart() {
  return JSON.parse(localStorage.getItem(CART_KEY)) || [];
}

function saveCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function clearCart() {
  localStorage.removeItem(CART_KEY);
}

function getCartCount() {
  return getCart().reduce((n, i) => n + (i.quantity || 1), 0);
}

function getCartTotal() {
  return getCart().reduce((t, i) => t + i.price * (i.quantity || 1), 0);
}

function addToCart(product) {
  const cart = getCart();
  const idx = cart.findIndex(i =>
    i.id === product.id &&
    i.selectedSize === product.selectedSize &&
    i.selectedColor === product.selectedColor
  );

  if (idx > -1) {
    cart[idx].quantity = (cart[idx].quantity || 1) + 1;
  } else {
    cart.push({ ...product, quantity: 1 });
  }

  saveCart(cart);
  updateCartBadge(true);
  updateCartDrawer();
  showToast('Added to cart!');
}

function removeFromCart(idx) {
  const cart = getCart();
  cart.splice(idx, 1);
  saveCart(cart);
  updateCartBadge();
  updateCartDrawer();
}

function changeQuantity(idx, delta) {
  const cart = getCart();
  if (!cart[idx]) return;

  cart[idx].quantity = (cart[idx].quantity || 1) + delta;
  if (cart[idx].quantity <= 0) {
    cart.splice(idx, 1);
  }

  saveCart(cart);
  updateCartBadge(delta > 0);
  updateCartDrawer();
}

function updateCartBadge(bump = false) {
  const count = getCartCount();
  document.querySelectorAll('.cart-badge').forEach(el => {
    el.textContent = count;
    el.style.display = count > 0 ? 'flex' : 'none';
    if (bump) {
      el.classList.remove('bump');
      void el.offsetWidth;
      el.classList.add('bump');
    }
  });
}

function updateCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  if (!drawer) return;

  const cart = getCart();

  // Build drawer contents with safe DOM operations
  drawer.textContent = '';

  const header = document.createElement('div');
  header.className = 'drawer-header';
  const h2 = document.createElement('h2');
  h2.textContent = `Your Bag (${getCartCount()})`;
  const closeBtn = document.createElement('button');
  closeBtn.className = 'drawer-close';
  closeBtn.textContent = '✕';
  closeBtn.setAttribute('aria-label', 'Close cart');
  closeBtn.addEventListener('click', closeCartDrawer);
  header.appendChild(h2);
  header.appendChild(closeBtn);

  drawer.appendChild(header);

  if (cart.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'drawer-empty';
    const icon = document.createElement('i'); icon.className = 'fas fa-shopping-bag';
    const p = document.createElement('p'); p.textContent = 'Your bag is empty';
    const a = document.createElement('a'); a.className = 'btn-primary'; a.href = '../customer/shop.html'; a.textContent = 'Shop Now';
    empty.appendChild(icon);
    empty.appendChild(p);
    empty.appendChild(a);
    drawer.appendChild(empty);
    return;
  }

  const itemsDiv = document.createElement('div');
  itemsDiv.className = 'drawer-items';

  cart.forEach((item, idx) => {
    const itemDiv = document.createElement('div');
    itemDiv.className = 'drawer-item';

    const img = document.createElement('img');
    const rawSrc = item.images && item.images[0] ? String(item.images[0]) : '';
    img.src = (rawSrc.startsWith('http://') || rawSrc.startsWith('https://') || rawSrc.startsWith('data:')) ? rawSrc : '../images/fallback.jpg';
    img.alt = item.name || 'Product image';

    const info = document.createElement('div'); info.className = 'drawer-item-info';
    const nameP = document.createElement('p'); nameP.className = 'drawer-item-name'; nameP.textContent = item.name || 'Product';
    const optsP = document.createElement('p'); optsP.className = 'drawer-item-opts'; optsP.textContent = `${item.selectedSize || ''} · ${item.selectedColor || ''}`;

    const controls = document.createElement('div'); controls.className = 'drawer-item-controls';
    const minus = document.createElement('button'); minus.textContent = '−'; minus.addEventListener('click', () => changeQuantity(idx, -1));
    const qty = document.createElement('span'); qty.textContent = String(item.quantity || 1);
    const plus = document.createElement('button'); plus.textContent = '+'; plus.addEventListener('click', () => changeQuantity(idx, 1));
    controls.appendChild(minus); controls.appendChild(qty); controls.appendChild(plus);

    info.appendChild(nameP); info.appendChild(optsP); info.appendChild(controls);

    const right = document.createElement('div'); right.className = 'drawer-item-right';
    const priceP = document.createElement('p'); priceP.className = 'drawer-item-price'; priceP.textContent = `Rs ${(item.price * (item.quantity || 1)).toLocaleString()}`;
    const removeBtn = document.createElement('button'); removeBtn.className = 'drawer-remove'; removeBtn.textContent = '✕'; removeBtn.addEventListener('click', () => removeFromCart(idx));
    right.appendChild(priceP); right.appendChild(removeBtn);

    itemDiv.appendChild(img);
    itemDiv.appendChild(info);
    itemDiv.appendChild(right);
    itemsDiv.appendChild(itemDiv);
  });

  drawer.appendChild(itemsDiv);

  const footer = document.createElement('div'); footer.className = 'drawer-footer';
  const totalDiv = document.createElement('div'); totalDiv.className = 'drawer-total';
  const spanLabel = document.createElement('span'); spanLabel.textContent = 'Total';
  const spanValue = document.createElement('span'); spanValue.textContent = `Rs ${getCartTotal().toLocaleString()}`;
  totalDiv.appendChild(spanLabel); totalDiv.appendChild(spanValue);
  const checkoutLink = document.createElement('a'); checkoutLink.className = 'btn-primary drawer-checkout'; checkoutLink.href = '../customer/checkout.html'; checkoutLink.textContent = 'Proceed to Checkout';
  footer.appendChild(totalDiv); footer.appendChild(checkoutLink);

  drawer.appendChild(footer);
}

let _cartDrawerReturnFocus = null;

function _onCartDrawerKeydown(e) {
  if (e.key === 'Escape') closeCartDrawer();
}

function openCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  const overlay = document.getElementById('cart-overlay');
  if (drawer) {
    drawer.classList.add('open');
    drawer.removeAttribute('aria-hidden');
    _cartDrawerReturnFocus = document.activeElement;
    const closeBtn = drawer.querySelector('.drawer-close');
    if (closeBtn) closeBtn.focus();
    document.addEventListener('keydown', _onCartDrawerKeydown);
  }
  if (overlay) overlay.classList.add('open');
}

function closeCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  const overlay = document.getElementById('cart-overlay');
  if (drawer) {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    document.removeEventListener('keydown', _onCartDrawerKeydown);
    if (_cartDrawerReturnFocus instanceof HTMLElement) _cartDrawerReturnFocus.focus();
    _cartDrawerReturnFocus = null;
  }
  if (overlay) overlay.classList.remove('open');
}

function addToCartWithAnimation(buttonEl, product) {
  addToCart(product);

  // NULL CHECK: Only animate if badge exists
  const badgeEl = document.querySelector('.cart-badge');
  if (!badgeEl) return;

  const dot = document.createElement('div');
  dot.className = 'fly-dot';

  const btnRect   = buttonEl.getBoundingClientRect();
  const badgeRect = badgeEl.getBoundingClientRect();

  // Calculate the button center position
  const btnCenterX = btnRect.left + btnRect.width / 2;
  const btnCenterY = btnRect.top + btnRect.height / 2;

  // Calculate the badge center position
  const badgeCenterX = badgeRect.left + badgeRect.width / 2;
  const badgeCenterY = badgeRect.top + badgeRect.height / 2;

  // Calculate the distance from button center to badge center
  const distX = badgeCenterX - btnCenterX;
  const distY = badgeCenterY - btnCenterY;

  dot.style.cssText = `
    left:${btnCenterX}px;
    top:${btnCenterY}px;
    --dx:${distX}px;
    --dy:${distY}px;
  `;

  document.body.appendChild(dot);
  dot.addEventListener('animationend', () => dot.remove(), { once: true });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  updateCartBadge();
  updateCartDrawer();

  const cartToggle = document.getElementById('cart-toggle');
  const cartOverlay = document.getElementById('cart-overlay');

  if (cartToggle) {
    cartToggle.addEventListener('click', openCartDrawer);
  }

  if (cartOverlay) {
    cartOverlay.addEventListener('click', closeCartDrawer);
  }
});
