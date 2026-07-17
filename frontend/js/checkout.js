// === CHECKOUT.JS ===

// Which gateways GET /payments/methods says are actually usable right now — every gateway
// defaults off server-side (no real credentials), so this hides options that would just 503.
let availableMethods = { cod: true, jazzcash: false, easypaisa: false, stripe: false, stripe_publishable_key: null };

// Generated once per page load and reused across every placeOrder() call on this page (e.g. a
// retry after a declined card) — matching Idempotency-Key on POST /orders means a retry returns
// the order already created instead of double-placing it and double-decrementing stock.
let checkoutIdempotencyKey = null;

function newIdempotencyKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function initializeCheckout() {
  const cart = getCart();
  if (cart.length === 0) {
    window.location.href = './shop.html';
    return;
  }

  checkoutIdempotencyKey = newIdempotencyKey();
  await initPaymentMethods();

  const { cart: refreshedCart, changedItems } = await refreshCartPrices(cart);
  displayOrderSummary(refreshedCart, changedItems);

  // Guest email field is only needed (and only shown) when there's no session to attach the
  // order to — see placeOrder()'s guest-checkout branch.
  const guestEmailGroup = document.getElementById('guest-email-group');
  if (guestEmailGroup) guestEmailGroup.style.display = isLoggedIn() ? 'none' : '';

  // If user is logged in, fetch latest profile from backend and prefill shipping fields
  if (isLoggedIn()) {
    try {
      const profile = await api.get('/auth/me', true);
      if (profile) {
        // Fill inputs if present
        const nameInput = document.querySelector('[name="fullName"]');
        const phoneInput = document.querySelector('[name="phone"]');
        const addressInput = document.querySelector('[name="address"]');
        if (nameInput && profile.name) nameInput.value = profile.name;
        if (phoneInput && profile.phone) phoneInput.value = profile.phone;
        if (addressInput && profile.address) addressInput.value = profile.address;

        // Add verified badge next to name input
        try {
          const parent = nameInput?.closest('.form-group');
          if (parent && !parent.querySelector('.verified-badge')) {
            const badge = document.createElement('span');
            badge.className = 'verified-badge';
            badge.title = 'Profile verified from your account';
            badge.innerHTML = '<i class="fas fa-check-circle" style="color:#16a34a;margin-left:8px"></i>';
            parent.appendChild(badge);
          }
        } catch (e) {
          // ignore DOM badge error
        }
      }
    } catch (e) {
      // ignore profile prefill error
    }
  }

  setupPromoCode();
  initPaymentToggle();
  initCheckoutProgress();
  initFieldValidation();
}

// Purely visual scrollspy — highlights the current step as the shopper scrolls
// through the single-page form. Does not gate or reorder the actual submit flow.
function initCheckoutProgress() {
  const steps = Array.from(document.querySelectorAll('.progress-step'));
  const sectionIds = { shipping: 'checkout-section-shipping', payment: 'checkout-section-payment', review: 'checkout-section-review' };
  const sections = Object.entries(sectionIds)
    .map(([step, id]) => ({ step, el: document.getElementById(id) }))
    .filter(s => s.el);

  if (!steps.length || !sections.length || !('IntersectionObserver' in window)) return;

  function setActive(activeStep) {
    const order = ['shipping', 'payment', 'review'];
    const activeIdx = order.indexOf(activeStep);
    steps.forEach(step => {
      const idx = order.indexOf(step.dataset.step);
      step.classList.toggle('active', idx === activeIdx);
      step.classList.toggle('completed', idx < activeIdx);
      const line = step.nextElementSibling;
      if (line && line.classList.contains('progress-line')) {
        const fill = line.querySelector('.progress-line-fill');
        if (fill) fill.style.width = idx < activeIdx ? '100%' : '0%';
      }
    });
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const match = sections.find(s => s.el === entry.target);
        if (match) setActive(match.step);
      }
    });
  }, { threshold: 0.4, rootMargin: '-15% 0px -35% 0px' });

  sections.forEach(s => observer.observe(s.el));
  setActive('shipping');
}

// Inline validation: checkmark on valid blur, shake + scroll-into-view on submit if empty.
function initFieldValidation() {
  const requiredFields = ['fullName', 'phone', 'address', 'city', 'postal'];
  requiredFields.forEach(name => {
    const input = document.querySelector(`[name="${name}"]`);
    const group = input?.closest('.form-group');
    if (!input || !group) return;

    if (!group.querySelector('.field-check')) {
      const check = document.createElement('i');
      check.className = 'fas fa-check-circle field-check';
      group.appendChild(check);
    }

    input.addEventListener('blur', () => {
      group.classList.toggle('field-valid', Boolean(input.value.trim()));
    });
    input.addEventListener('input', () => {
      if (input.value.trim()) group.classList.remove('shake');
    });
  });
}

function shakeInvalidFields(missingNames) {
  missingNames.forEach((name, idx) => {
    const input = document.querySelector(`[name="${name}"]`);
    const group = input?.closest('.form-group');
    if (!group) return;
    group.classList.remove('shake');
    void group.offsetWidth;
    group.classList.add('shake');
    if (idx === 0) input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    group.addEventListener('animationend', () => group.classList.remove('shake'), { once: true });
  });
}

async function refreshCartPrices(cart) {
  const refreshedCart = [...cart];
  const changedItems = [];

  for (let index = 0; index < refreshedCart.length; index += 1) {
    const item = refreshedCart[index];
    if (!item?.id) continue;

    try {
      const product = await api.get(`/products/${item.id}`);
      if (!product) continue;

      const currentPrice = Number(product.price || 0);
      const previousPrice = Number(item.price || 0);
      if (currentPrice && currentPrice !== previousPrice) {
        refreshedCart[index] = { ...item, price: currentPrice };
        changedItems.push({ name: item.name || product.name || 'Item', from: previousPrice, to: currentPrice });
      }
    } catch (error) {
      // ignore price refresh error for this item
    }
  }

  if (changedItems.length > 0) {
    saveCart(refreshedCart);
  }

  return { cart: refreshedCart, changedItems };
}

function displayOrderSummary(cart, changedItems = []) {
  const summary = document.querySelector('.order-summary');
  if (!summary) return;

  const subtotal = getCartTotal();
  const tax = subtotal * 0.10;
  const delivery = 250;
  const total = subtotal + tax + delivery;

  // Build summary DOM safely
  summary.textContent = '';

  if (changedItems.length > 0) {
    const notice = document.createElement('div');
    notice.className = 'price-sync-notice';
    notice.setAttribute('role', 'status');
    notice.textContent = 'Some item prices changed since they were added to your cart. We updated the totals below.';
    summary.appendChild(notice);
  }

  const itemsWrapper = document.createElement('div');
  itemsWrapper.className = 'summary-items';
  // itemsHTML was built as escaped markup; recreate items as DOM nodes
  cart.forEach(item => {
    const div = document.createElement('div'); div.className = 'summary-item';
    const img = document.createElement('img'); img.src = item.images?.[0] || '../images/fallback.jpg'; img.alt = item.name || ''; img.className = 'summary-item-image'; img.onerror = () => img.src = '../images/fallback.jpg';
    const info = document.createElement('div'); info.className = 'summary-item-info';
    const nameP = document.createElement('p'); nameP.className = 'summary-item-name'; nameP.textContent = item.name;
    const detailsP = document.createElement('p'); detailsP.className = 'summary-item-details'; detailsP.textContent = `${item.selectedSize || ''} · ${item.selectedColor || ''}`;
    const qtyP = document.createElement('p'); qtyP.className = 'summary-item-details'; qtyP.textContent = `Qty: ${item.quantity}`;
    info.appendChild(nameP); info.appendChild(detailsP); info.appendChild(qtyP);
    const priceP = document.createElement('p'); priceP.className = 'summary-item-price'; priceP.textContent = `Rs ${(item.price * item.quantity).toLocaleString()}`;
    div.appendChild(img); div.appendChild(info); div.appendChild(priceP);
    itemsWrapper.appendChild(div);
  });

  const breakdown = document.createElement('div'); breakdown.className = 'price-breakdown';
  const row = (label, val, id) => {
    const r = document.createElement('div'); r.className = 'price-row';
    if (id) r.id = id;
    const l = document.createElement('span'); l.className = 'price-label'; l.textContent = label;
    const v = document.createElement('span'); v.className = 'price-value'; v.textContent = val;
    r.appendChild(l); r.appendChild(v); return r;
  };
  breakdown.appendChild(row('Subtotal', `Rs ${subtotal.toLocaleString()}`));
  const discountRow = row('Discount', `-Rs 0`, 'discount-row');
  discountRow.classList.add('discount');
  discountRow.style.display = 'none';
  discountRow.querySelector('.price-value').id = 'discount-amount';
  breakdown.appendChild(discountRow);
  breakdown.appendChild(row('Tax (10%)', `Rs ${tax.toLocaleString()}`));
  breakdown.appendChild(row('Delivery', `Rs ${delivery}`));
  const totalRow = document.createElement('div'); totalRow.className = 'price-row total';
  const totalLabel = document.createElement('span'); totalLabel.className = 'price-label'; totalLabel.textContent = 'Total';
  const totalVal = document.createElement('span'); totalVal.className = 'price-value'; totalVal.id = 'final-total'; totalVal.textContent = `Rs ${total.toLocaleString()}`;
  totalRow.appendChild(totalLabel); totalRow.appendChild(totalVal);
  breakdown.appendChild(totalRow);

  summary.appendChild(itemsWrapper);
  summary.appendChild(breakdown);
}

let appliedPromo = null;

async function setupPromoCode() {
  const applyBtn = document.querySelector('.promo-section button');
  const promoInput = document.querySelector('.promo-section input');

  if (applyBtn) {
    applyBtn.addEventListener('click', async () => {
      if (!promoInput.value) {
        showToast('Enter promo code', 'warning');
        return;
      }

      try {
        const result = await api.post('/promos/validate', {
          code: promoInput.value,
          order_total: getCartTotal()
        }, true);

        appliedPromo = result;
        promoInput.value = result.code;
        applyBtn.textContent = '✓ Applied';
        applyBtn.disabled = true;

        // Update price breakdown
        const discountRow = document.getElementById('discount-row');
        if (discountRow) {
          discountRow.style.display = 'flex';
          document.getElementById('discount-amount').textContent = result.discount_amount.toLocaleString();
        }

        const subtotal = getCartTotal();
        const discount = result.discount_amount;
        const afterDiscount = subtotal - discount;
        const tax = afterDiscount * 0.10;
        const delivery = 250;
        const total = afterDiscount + tax + delivery;

        document.getElementById('final-total').textContent = `Rs ${total.toLocaleString()}`;
        const promoLabel = result.discount_type === 'percentage'
          ? `${result.discount_value}% off`
          : `Rs ${Number(result.discount_value).toLocaleString()} off`;
        showToast(`Promo applied: ${promoLabel}`, 'success');
      } catch (err) {
        showToast(err.message || 'Invalid promo code', 'error');
      }
    });
  }
}

async function placeOrder() {
  const user = getUser();
  const loggedIn = Boolean(user);
  let guestEmail = null;

  if (loggedIn) {
    // Re-verify user data with backend to ensure token is valid and data is current
    try {
      const profile = await api.get('/auth/me', true);
      if (!profile || profile.email !== user.email) {
        // Session mismatch - force re-login
        clearAuth();
        showToast('Session expired. Please login again.', 'warning');
        setTimeout(() => window.location.href = '../auth/login.html', 600);
        return;
      }
    } catch (e) {
      showToast('Authentication check failed. Please login again.', 'error');
      clearAuth();
      setTimeout(() => window.location.href = '../auth/login.html', 800);
      return;
    }
  } else {
    // Guest checkout — no account required. GET /orders/{id}?email=... (backend) is how a
    // guest can look their order back up afterwards, since there's no session to key it on.
    guestEmail = document.querySelector('[name="guestEmail"]')?.value.trim();
    if (!guestEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(guestEmail)) {
      const group = document.querySelector('[name="guestEmail"]')?.closest('.form-group');
      if (group) shakeInvalidFields(['guestEmail']);
      showToast('Enter a valid email to checkout as a guest, or log in.', 'warning');
      return;
    }
  }

  const fields = { fullName: 'fullName', phone: 'phone', address: 'address', city: 'city', postal: 'postal' };
  const values = {};
  Object.keys(fields).forEach(key => {
    values[key] = document.querySelector(`[name="${fields[key]}"]`)?.value;
  });
  const { fullName, phone, address, city, postal } = values;

  if (!fullName || !phone || !address || !city || !postal) {
    const missing = Object.keys(fields).filter(key => !values[key]);
    shakeInvalidFields(missing);
    showToast('Please fill all shipping details', 'warning');
    return;
  }

  const cart = getCart();
  if (cart.length === 0) {
    showToast('Your cart is empty', 'warning');
    return;
  }

  const method = getPaymentData().method;
  const btn = document.querySelector('.checkout-btn');

  try {
    const order = await api.post('/orders', {
      items: cart.map(i => ({
        product_id: i.id,
        name: i.name,
        price: i.price,
        quantity: i.quantity,
        size: i.selectedSize,
        color: i.selectedColor,
        image: i.images?.[0] || ''
      })),
      shipping_address: {
        full_name: fullName,
        phone,
        address,
        city,
        postal_code: postal
      },
      promo_code: appliedPromo?.code || null,
      payment_method: method,
      payment_reference: getPaymentData().reference,
      guest_email: guestEmail || undefined,
    }, loggedIn, { 'Idempotency-Key': checkoutIdempotencyKey });

    // Online gateways: the order already exists (pending/unpaid) — only a signature-verified
    // webhook (never this page) ever marks it paid. See routes/payments.py.
    if (method === 'jazzcash' || method === 'easypaisa') {
      try {
        const payment = await api.post(`/payments/${order.id}/initiate`, { gateway: method }, loggedIn);
        if (payment?.redirect_url) {
          clearCart();
          updateCartBadge();
          submitGatewayRedirect(payment.redirect_url, payment.form_fields);
          return; // browser is navigating away to the gateway's hosted page
        }
      } catch (payErr) {
        showToast('Order placed — online payment is unavailable right now. You can retry payment from your order page.', 'warning');
      }
    } else if (method === 'card') {
      try {
        const payment = await api.post(`/payments/${order.id}/initiate`, { gateway: 'stripe' }, loggedIn);
        await ensureCardElement();
        const result = await stripeInstance.confirmCardPayment(payment.client_secret, {
          payment_method: { card: cardElement },
        });
        if (result.error) {
          const errorEl = document.getElementById('card-errors');
          if (errorEl) errorEl.textContent = result.error.message;
          showToast(result.error.message || 'Card payment failed', 'error');
          return; // stay on the page — same order/idempotency key, so a retry won't double-book
        }
      } catch (payErr) {
        showToast(payErr.message || 'Card payment failed', 'error');
        return;
      }
    }

    clearCart();
    updateCartBadge();
    showToast('Order placed successfully!');

    if (btn) {
      btn.disabled = true;
      btn.classList.add('success');
    }
    document.querySelectorAll('.progress-step').forEach(step => step.classList.add('completed'));

    // Guest orders have no session to track them with — tracking.html falls back to the
    // GET /orders/{id}?email=... lookup (guest_email in the URL) and, once there, offers to
    // create an account with that email (frontend/js/tracking.js::renderGuestAccountPrompt).
    const trackingUrl = loggedIn
      ? `./tracking.html?id=${order.id}`
      : `./tracking.html?id=${order.id}&guest_email=${encodeURIComponent(guestEmail)}`;

    setTimeout(() => {
      window.location.href = trackingUrl;
    }, 2000);
  } catch (err) {
    // If server returned structured error, show server message
    const message = err && err.message ? err.message : 'Failed to place order';
    showToast(message, 'error');
    console.error('Place order error:', err);
  }
}

// Builds and submits a hidden auto-submitting POST form — how the browser is handed off to
// JazzCash/EasyPaisa's hosted checkout page with the signed fields from initiate().
function submitGatewayRedirect(url, fields) {
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  form.style.display = 'none';
  Object.entries(fields || {}).forEach(([key, value]) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = key;
    input.value = value;
    form.appendChild(input);
  });
  document.body.appendChild(form);
  form.submit();
}

// Which payment options actually work right now, per the backend's own config — hides
// JazzCash/Easypaisa/card entirely rather than letting a shopper pick one that just 503s.
async function initPaymentMethods() {
  try {
    availableMethods = await api.get('/payments/methods');
  } catch (e) {
    availableMethods = { cod: true, jazzcash: false, easypaisa: false, stripe: false, stripe_publishable_key: null };
  }

  const optionEls = {
    jazzcash: document.querySelector('.payment-option[data-method="jazzcash"]'),
    easypaisa: document.querySelector('.payment-option[data-method="easypaisa"]'),
    card: document.querySelector('.payment-option[data-method="card"]'),
  };
  if (optionEls.jazzcash) optionEls.jazzcash.style.display = availableMethods.jazzcash ? '' : 'none';
  if (optionEls.easypaisa) optionEls.easypaisa.style.display = availableMethods.easypaisa ? '' : 'none';
  if (optionEls.card) optionEls.card.style.display = availableMethods.stripe ? '' : 'none';
}

let stripeInstance = null;
let cardElement = null;

function loadStripeJs() {
  return new Promise((resolve, reject) => {
    if (window.Stripe) { resolve(window.Stripe); return; }
    const script = document.createElement('script');
    script.src = 'https://js.stripe.com/v3/';
    script.onload = () => resolve(window.Stripe);
    script.onerror = () => reject(new Error('Could not load the card payment form'));
    document.head.appendChild(script);
  });
}

// Lazily loads Stripe.js and mounts the Card Element the first time "card" is selected — never
// loaded/requested at all if Stripe isn't configured or the shopper never picks that option.
async function ensureCardElement() {
  if (cardElement) return;
  if (!availableMethods.stripe_publishable_key) throw new Error('Card payment is not available');

  const Stripe = await loadStripeJs();
  stripeInstance = Stripe(availableMethods.stripe_publishable_key);
  const elements = stripeInstance.elements();
  cardElement = elements.create('card');
  cardElement.mount('#card-element');
  cardElement.on('change', (event) => {
    const errorEl = document.getElementById('card-errors');
    if (errorEl) errorEl.textContent = event.error ? event.error.message : '';
  });
}

// Payment method toggle and data collection
function initPaymentToggle() {
  const options = document.querySelectorAll('.payment-option');

  options.forEach(option => {
    option.addEventListener('change', (e) => {
      if (e.target.type === 'radio') {
        // Update active styling
        options.forEach(o => o.classList.remove('active'));
        option.classList.add('active');

        // Show/hide wallet/card fields
        document.getElementById('jazzcash-fields').style.display = 'none';
        document.getElementById('easypaisa-fields').style.display = 'none';
        document.getElementById('card-fields').style.display = 'none';

        const method = e.target.value;
        if (method === 'jazzcash') {
          document.getElementById('jazzcash-fields').style.display = 'block';
        } else if (method === 'easypaisa') {
          document.getElementById('easypaisa-fields').style.display = 'block';
        } else if (method === 'card') {
          document.getElementById('card-fields').style.display = 'block';
          ensureCardElement().catch(err => showToast(err.message || 'Could not load card form', 'error'));
        }
      }
    });
  });
}

function getPaymentData() {
  const selected = document.querySelector('input[name="payment_method"]:checked');
  const method = selected?.value || 'cod';
  
  let reference = null;

  if (method === 'jazzcash') {
    reference = document.getElementById('jazzcash-number')?.value || '';
    if (reference && !reference.match(/^\d{3,4}-\d{7}$/)) {
      reference = reference.replace(/[^\d]/g, '').slice(0, 11);
    }
  } else if (method === 'easypaisa') {
    reference = document.getElementById('easypaisa-number')?.value || '';
    if (reference && !reference.match(/^\d{3,4}-\d{7}$/)) {
      reference = reference.replace(/[^\d]/g, '').slice(0, 11);
    }
  }

  return { method, reference };
}

document.addEventListener('DOMContentLoaded', initializeCheckout);
