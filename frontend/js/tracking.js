// === TRACKING.JS ===
async function loadTrackingData() {
  try {
    const orderId = new URLSearchParams(window.location.search).get('id');
    if (!orderId) {
      showToast('Order not found', 'error');
      return;
    }

    const order = await api.get(`/orders/${orderId}`, isLoggedIn());
    
    // Null check for order
    if (!order) {
      showToast('Order data is invalid', 'error');
      return;
    }

    // Safe: use textContent instead of innerHTML for user data
    const orderIdElement = document.querySelector('.order-id');
    if (orderIdElement) {
      safeText(orderIdElement, `Order #${orderId.substring(0, 8)}...`);
    }

    // Status timeline with sanitized data. status_history (already returned by
    // GET /orders/{id}, per backend/schemas/order.py) supplies the timestamp/note
    // for each step that's actually been reached.
    const statuses = ['pending', 'confirmed', 'packed', 'shipped', 'delivered'];
    const timeline = document.querySelector('.status-timeline');
    const history = Array.isArray(order.status_history) ? order.status_history : [];
    const isTerminalBad = order.status === 'cancelled' || order.status === 'returned';

    if (timeline) {
      timeline.textContent = '';
      const currentIdx = statuses.indexOf(order.status);

      statuses.forEach((status, idx) => {
        const completed = !isTerminalBad && currentIdx >= idx && currentIdx !== -1 && idx < currentIdx;
        const active = !isTerminalBad && status === order.status;

        const step = document.createElement('div');
        step.className = 'timeline-step';
        step.style.position = 'relative';

        if (idx < statuses.length - 1) {
          const line = document.createElement('div');
          line.className = 'timeline-line';
          if (completed) line.classList.add('filled');
          step.appendChild(line);
        }

        const dot = document.createElement('div');
        dot.className = `timeline-dot ${active ? 'active' : ''} ${completed ? 'completed' : ''}`;
        dot.textContent = active ? '●' : completed ? '✓' : '◦';

        const content = document.createElement('div');
        content.className = 'timeline-content';

        const statusP = document.createElement('p');
        statusP.className = 'timeline-status';
        statusP.style.textTransform = 'capitalize';
        statusP.textContent = status;
        content.appendChild(statusP);

        const entry = history.find(h => h.status === status);
        if (entry?.timestamp) {
          const timeP = document.createElement('p');
          timeP.className = 'timeline-time';
          try { timeP.textContent = new Date(entry.timestamp).toLocaleString(); } catch { /* skip */ }
          content.appendChild(timeP);
        }
        if (entry?.note) {
          const noteP = document.createElement('p');
          noteP.className = 'timeline-note';
          safeText(noteP, entry.note);
          content.appendChild(noteP);
        }

        step.appendChild(dot);
        step.appendChild(content);
        timeline.appendChild(step);
      });

      if (isTerminalBad) {
        const badStep = document.createElement('div');
        badStep.className = 'timeline-step';
        const dot = document.createElement('div');
        dot.className = 'timeline-dot cancelled';
        const icon = document.createElement('i'); icon.className = 'fas fa-times';
        dot.appendChild(icon);
        const content = document.createElement('div');
        content.className = 'timeline-content';
        const statusP = document.createElement('p');
        statusP.className = 'timeline-status';
        statusP.style.textTransform = 'capitalize';
        statusP.textContent = order.status;
        content.appendChild(statusP);
        badStep.appendChild(dot);
        badStep.appendChild(content);
        timeline.appendChild(badStep);
      }
    }

    // Order items with sanitized data
    const itemsContainer = document.querySelector('.order-items');
    if (itemsContainer && Array.isArray(order.items)) {
      itemsContainer.textContent = '';
      
      const title = document.createElement('h3');
      title.className = 'items-title';
      title.textContent = 'Items';
      itemsContainer.appendChild(title);
      
      order.items.forEach(item => {
        if (!item) return;
        
        const itemDiv = document.createElement('div');
        itemDiv.className = 'order-item';
        
        const imageDiv = document.createElement('div');
        imageDiv.className = 'item-image';
        const img = document.createElement('img');
        img.src = sanitizeUrl(item.image);
        img.alt = item.name || 'Product image';
        img.onerror = () => { img.src = '../images/fallback.jpg'; };
        imageDiv.appendChild(img);

        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'item-details';

        const nameP = document.createElement('p');
        nameP.className = 'item-name';
        safeText(nameP, item.name || 'Unknown');

        const optionsP = document.createElement('p');
        optionsP.className = 'item-options';
        safeText(optionsP, `${item.size || 'N/A'} · ${item.color || 'N/A'}`);
        
        const qtyP = document.createElement('p');
        qtyP.className = 'item-qty';
        qtyP.textContent = `Qty: ${sanitizeNumber(item.quantity)}`;
        
        detailsDiv.appendChild(nameP);
        detailsDiv.appendChild(optionsP);
        detailsDiv.appendChild(qtyP);
        
        const priceP = document.createElement('p');
        priceP.className = 'item-price';
        priceP.textContent = `Rs ${sanitizeNumber(item.price * item.quantity).toLocaleString()}`;
        
        itemDiv.appendChild(imageDiv);
        itemDiv.appendChild(detailsDiv);
        itemDiv.appendChild(priceP);
        itemsContainer.appendChild(itemDiv);
      });
    }

    // Online-gateway payment status — never trust the redirect the browser just landed from;
    // poll GET /payments/{id}/status (backed by the webhook-verified Payment record) instead.
    if (order.payment_status && order.payment_status !== 'not_required') {
      pollPaymentStatus(orderId, order.payment_status);
    }

    // Shipping info with sanitized data
    const shippingDiv = document.querySelector('.shipping-info');
    if (shippingDiv) {
      shippingDiv.textContent = '';
      
      const title = document.createElement('h3');
      title.className = 'info-title';
      title.textContent = 'Shipping Address';
      
      const addr = order.shipping_address;
      if (addr) {
        const addressDiv = document.createElement('div');
        addressDiv.className = 'shipping-address';
        
        const content = [
          addr.full_name || 'N/A',
          addr.phone || 'N/A',
          addr.address || 'N/A',
          `${addr.city || 'N/A'}, ${addr.postal_code || 'N/A'}`
        ].join('\n');

        safeText(addressDiv, content);
        shippingDiv.appendChild(title);
        shippingDiv.appendChild(addressDiv);
      }
    }
  } catch (err) {
    console.error('Failed to load tracking data', err);
    // Don't expose raw backend errors to users
    showToast('Failed to load order. Please try again later.', 'error');
  }
}

// ════════════════════════════════════════════════════
// PAYMENT STATUS POLLING
// ════════════════════════════════════════════════════
// A gateway redirect back to this page is UX only — the customer's browser could close, retry,
// or land here before the gateway's own server-to-server webhook has even arrived. This polls
// the webhook-verified status instead of ever trusting the redirect itself.
function renderPaymentBanner(status) {
  const banner = document.getElementById('payment-status-banner');
  if (!banner) return;
  const copy = {
    unpaid:     { text: 'Awaiting payment confirmation…', cls: 'pending' },
    processing: { text: 'Confirming your payment…', cls: 'pending' },
    paid:       { text: 'Payment confirmed', cls: 'success' },
    failed:     { text: 'Payment failed — please retry from checkout or choose Cash on Delivery.', cls: 'error' },
    refunded:   { text: 'Payment refunded', cls: 'pending' },
  }[status];
  if (!copy) { banner.style.display = 'none'; return; }
  banner.textContent = copy.text;
  banner.className = `payment-status-banner ${copy.cls}`;
  banner.style.display = 'block';
}

function pollPaymentStatus(orderId, initialStatus, attempt = 0) {
  renderPaymentBanner(initialStatus);
  if (initialStatus === 'paid' || initialStatus === 'failed' || initialStatus === 'refunded') return;
  if (attempt >= 15) return; // ~45s of polling — stop rather than poll forever

  setTimeout(async () => {
    try {
      const status = await api.get(`/payments/${orderId}/status`, isLoggedIn());
      renderPaymentBanner(status.payment_status);
      if (status.payment_status === 'unpaid' || status.payment_status === 'processing') {
        pollPaymentStatus(orderId, status.payment_status, attempt + 1);
      }
    } catch (e) {
      // Silent — the main order timeline above already loaded successfully.
    }
  }, 3000);
}

// ════════════════════════════════════════════════════
// SANITIZATION FUNCTIONS
// ════════════════════════════════════════════════════
function sanitizeUrl(url) {
  if (typeof url !== 'string') return '../images/fallback.jpg';
  // Only allow http, https, and data URLs
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url;
  }
  return '../images/fallback.jpg';
}

function sanitizeNumber(num) {
  const parsed = parseFloat(num);
  return isNaN(parsed) ? 0 : parsed;
}

document.addEventListener('DOMContentLoaded', loadTrackingData);

