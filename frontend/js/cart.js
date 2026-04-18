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
  updateCartBadge();
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
  updateCartBadge();
  updateCartDrawer();
}

function updateCartBadge() {
  const count = getCartCount();
  document.querySelectorAll('.cart-badge').forEach(el => {
    el.textContent = count;
    el.style.display = count > 0 ? 'flex' : 'none';
  });
}

function updateCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  if (!drawer) return;

  const cart = getCart();

  if (cart.length === 0) {
    drawer.innerHTML = `
      <div class="drawer-header">
        <h2>Your Bag</h2>
        <button class="drawer-close" onclick="closeCartDrawer()">✕</button>
      </div>
      <div class="drawer-empty">
        <i class="fas fa-shopping-bag"></i>
        <p>Your bag is empty</p>
        <a href="./shop.html" class="btn-primary">Shop Now</a>
      </div>`;
    return;
  }

  const itemsHTML = cart.map((item, idx) => `
    <div class="drawer-item">
      <img src="${item.images?.[0] || './images/fallback.jpg'}" alt="${item.name}">
      <div class="drawer-item-info">
        <p class="drawer-item-name">${item.name}</p>
        <p class="drawer-item-opts">${item.selectedSize || ''} · ${item.selectedColor || ''}</p>
        <div class="drawer-item-controls">
          <button onclick="changeQuantity(${idx}, -1)">−</button>
          <span>${item.quantity}</span>
          <button onclick="changeQuantity(${idx}, 1)">+</button>
        </div>
      </div>
      <div class="drawer-item-right">
        <p class="drawer-item-price">Rs ${(item.price * item.quantity).toLocaleString()}</p>
        <button class="drawer-remove" onclick="removeFromCart(${idx})">✕</button>
      </div>
    </div>`).join('');

  drawer.innerHTML = `
    <div class="drawer-header">
      <h2>Your Bag (${getCartCount()})</h2>
      <button class="drawer-close" onclick="closeCartDrawer()">✕</button>
    </div>
    <div class="drawer-items">${itemsHTML}</div>
    <div class="drawer-footer">
      <div class="drawer-total">
        <span>Total</span>
        <span>Rs ${getCartTotal().toLocaleString()}</span>
      </div>
      <a href="./checkout.html" class="btn-primary drawer-checkout">Proceed to Checkout</a>
    </div>`;
}

function openCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  const overlay = document.getElementById('cart-overlay');
  if (drawer) drawer.classList.add('open');
  if (overlay) overlay.classList.add('open');
}

function closeCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  const overlay = document.getElementById('cart-overlay');
  if (drawer) drawer.classList.remove('open');
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

  dot.style.cssText = `
    left:${btnRect.left + btnRect.width/2}px;
    top:${btnRect.top + btnRect.height/2}px;
    --dx:${badgeRect.left - btnRect.left}px;
    --dy:${badgeRect.top - btnRect.top}px;
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
