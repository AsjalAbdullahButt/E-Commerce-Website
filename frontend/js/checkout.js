// === CHECKOUT.JS ===
async function initializeCheckout() {
  const cart = getCart();
  if (cart.length === 0) {
    window.location.href = './shop.html';
    return;
  }

  displayOrderSummary(cart);
  setupPromoCode();
}

function displayOrderSummary(cart) {
  const summary = document.querySelector('.order-summary');
  if (!summary) return;

  const itemsHTML = cart.map((item, idx) => `
    <div class="summary-item">
      <img src="${item.images?.[0]}" alt="${item.name}" class="summary-item-image">
      <div class="summary-item-info">
        <p class="summary-item-name">${item.name}</p>
        <p class="summary-item-details">${item.selectedSize} · ${item.selectedColor}</p>
        <p class="summary-item-details">Qty: ${item.quantity}</p>
      </div>
      <p class="summary-item-price">Rs ${(item.price * item.quantity).toLocaleString()}</p>
    </div>
  `).join('');

  const subtotal = getCartTotal();
  const tax = subtotal * 0.10;
  const delivery = 250;
  const total = subtotal + tax + delivery;

  summary.innerHTML = itemsHTML + `
    <div class="price-breakdown">
      <div class="price-row">
        <span class="price-label">Subtotal</span>
        <span class="price-value">Rs ${subtotal.toLocaleString()}</span>
      </div>
      <div class="price-row" id="discount-row" style="display:none;">
        <span class="price-label">Discount</span>
        <span class="price-value">-Rs <span id="discount-amount">0</span></span>
      </div>
      <div class="price-row">
        <span class="price-label">Tax (10%)</span>
        <span class="price-value">Rs ${tax.toLocaleString()}</span>
      </div>
      <div class="price-row">
        <span class="price-label">Delivery</span>
        <span class="price-value">Rs ${delivery}</span>
      </div>
      <div class="price-row total">
        <span class="price-label">Total</span>
        <span class="price-value" id="final-total">Rs ${total.toLocaleString()}</span>
      </div>
    </div>
  `;
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
        showToast('Promo code applied!');
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

  const fullName = document.querySelector('[name="fullName"]')?.value;
  const phone = document.querySelector('[name="phone"]')?.value;
  const address = document.querySelector('[name="address"]')?.value;
  const city = document.querySelector('[name="city"]')?.value;
  const postal = document.querySelector('[name="postal"]')?.value;

  if (!fullName || !phone || !address || !city || !postal) {
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
      promo_code: appliedPromo?.code || null
    }, true);

    clearCart();
    updateCartBadge();
    showToast('Order placed successfully!');

    setTimeout(() => {
      window.location.href = `./tracking.html?id=${order.id}`;
    }, 2000);
  } catch (err) {
    showToast(err.message || 'Failed to place order', 'error');
  }
}

document.addEventListener('DOMContentLoaded', initializeCheckout);
