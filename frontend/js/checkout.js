// === CHECKOUT.JS ===
async function initializeCheckout() {
  const cart = getCart();
  if (cart.length === 0) {
    window.location.href = './shop.html';
    return;
  }

  const { cart: refreshedCart, changedItems } = await refreshCartPrices(cart);
  displayOrderSummary(refreshedCart, changedItems);
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
  if (!user) {
    showToast('Please login first', 'warning');
    window.location.href = './login.html';
    return;
  }

  // Re-verify user data with backend to ensure token is valid and data is current
  try {
    const profile = await api.get('/auth/me', true);
    if (!profile || profile.email !== user.email) {
      // Session mismatch - force re-login
      clearAuth();
      showToast('Session expired. Please login again.', 'warning');
      setTimeout(() => window.location.href = './login.html', 600);
      return;
    }
  } catch (e) {
    showToast('Authentication check failed. Please login again.', 'error');
    clearAuth();
    setTimeout(() => window.location.href = './login.html', 800);
    return;
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
      payment_method: getPaymentData().method,
      payment_reference: getPaymentData().reference
    }, true);

    clearCart();
    updateCartBadge();
    showToast('Order placed successfully!');

    const btn = document.querySelector('.checkout-btn');
    if (btn) {
      btn.disabled = true;
      btn.classList.add('success');
    }
    document.querySelectorAll('.progress-step').forEach(step => step.classList.add('completed'));

    setTimeout(() => {
      window.location.href = `./tracking.html?id=${order.id}`;
    }, 2000);
  } catch (err) {
    // If server returned structured error, show server message
    const message = err && err.message ? err.message : 'Failed to place order';
    showToast(message, 'error');
    console.error('Place order error:', err);
  }
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

        // Show/hide wallet fields
        document.getElementById('jazzcash-fields').style.display = 'none';
        document.getElementById('easypaisa-fields').style.display = 'none';

        const method = e.target.value;
        if (method === 'jazzcash') {
          document.getElementById('jazzcash-fields').style.display = 'block';
        } else if (method === 'easypaisa') {
          document.getElementById('easypaisa-fields').style.display = 'block';
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
