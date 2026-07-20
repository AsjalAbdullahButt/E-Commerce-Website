// === TRACKING.JS ===
// Clears the static loading skeletons and shows the shared empty state where the
// timeline would have rendered — used by every failure path below.
function showTrackingError(title, message) {
  document.querySelectorAll('.tracking-container .card-skeleton').forEach((el) => el.remove());
  // The item/shipping sections would render as empty shells without data — drop them entirely.
  document.querySelectorAll('.order-items, .shipping-info').forEach((el) => { el.style.display = 'none'; });
  renderEmptyStateInto(document.querySelector('.status-timeline'), {
    icon: 'fa-triangle-exclamation',
    title,
    message,
  });
}

async function loadTrackingData() {
  try {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('id');
    const guestEmail = params.get('guest_email');
    if (!orderId) {
      showToast('Order not found', 'error');
      showTrackingError('Order not found', 'This link is missing an order number. Open tracking from your profile or order email.');
      return;
    }

    // A guest order has no session to authenticate the lookup with — GET /orders/{id} accepts
    // ?email=... instead, matching how it was placed (js/checkout.js, routes/orders.py).
    const orderUrl = guestEmail ? `/orders/${orderId}?email=${encodeURIComponent(guestEmail)}` : `/orders/${orderId}`;
    const order = await api.get(orderUrl, !guestEmail && isLoggedIn());

    // Null check for order
    if (!order) {
      showToast('Order data is invalid', 'error');
      showTrackingError('Order not available', 'We could not read this order. Please try again later.');
      return;
    }

    if (guestEmail) {
      renderGuestAccountPrompt(guestEmail);
    }

    initCancelOrderButton(order, orderId, guestEmail);
    initDownloadInvoiceButton(orderId, guestEmail);

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
        // Rider name on the two steps a rider is actually the one acting — assigned by then
        // (routes/admin.py::assign_rider runs before "shipped"), so it's never shown earlier.
        if ((status === 'shipped' || status === 'delivered') && order.rider_name) {
          const riderP = document.createElement('p');
          riderP.className = 'timeline-note';
          safeText(riderP, `Rider: ${order.rider_name}`);
          content.appendChild(riderP);
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

    renderProofOfDeliverySection(order);
    renderReturnRequestSection(order, orderId, guestEmail);
  } catch (err) {
    console.error('Failed to load tracking data', err);
    // Don't expose raw backend errors to users
    showToast('Failed to load order. Please try again later.', 'error');
    showTrackingError('Failed to load order', 'Check your connection, then reload the page to try again.');
  }
}

// ════════════════════════════════════════════════════
// DOWNLOAD INVOICE (PDF) — a plain <a href> can't carry the Authorization header a logged-in
// customer's request needs, so this fetches the PDF as a blob and triggers the download itself.
// A guest order doesn't need that (GET /orders/{id}/invoice accepts ?email= instead).
// ════════════════════════════════════════════════════
function initDownloadInvoiceButton(orderId, guestEmail) {
  const btn = document.getElementById('download-invoice-btn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      const url = guestEmail
        ? `${API_BASE}/orders/${orderId}/invoice?email=${encodeURIComponent(guestEmail)}`
        : `${API_BASE}/orders/${orderId}/invoice`;
      const headers = {};
      if (!guestEmail) {
        let token = getAccessToken();
        if (!token) {
          await refreshAccessToken();
          token = getAccessToken();
        }
        if (token) headers['Authorization'] = `Bearer ${token}`;
      }

      const resp = await fetch(url, { headers, credentials: 'include', cache: 'no-store' });
      if (!resp.ok) throw new Error('Failed to download invoice');

      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `invoice-${orderId.substring(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      showToast(err.message || 'Failed to download invoice', 'error');
    } finally {
      btn.disabled = false;
    }
  });
}

// ════════════════════════════════════════════════════
// CANCEL ORDER — only while still early in the fulfillment lifecycle (matches the backend's
// utils/order_transitions.py: pending/confirmed/packed -> cancelled; shipped/delivered can't).
// ════════════════════════════════════════════════════
const CANCELLABLE_STATUSES = ['pending', 'confirmed', 'packed'];

function initCancelOrderButton(order, orderId, guestEmail) {
  const btn = document.getElementById('cancel-order-btn');
  if (!btn) return;

  if (!CANCELLABLE_STATUSES.includes(order.status)) {
    btn.style.display = 'none';
    return;
  }
  btn.style.display = 'inline-block';

  // Replace any previous handler from an earlier render (e.g. after a return-request refresh).
  const freshBtn = btn.cloneNode(true);
  btn.parentNode.replaceChild(freshBtn, btn);

  freshBtn.addEventListener('click', async () => {
    if (!window.confirm('Cancel this order? This cannot be undone.')) return;
    freshBtn.disabled = true;
    try {
      const url = guestEmail
        ? `/orders/${orderId}/cancel?email=${encodeURIComponent(guestEmail)}`
        : `/orders/${orderId}/cancel`;
      await api.post(url, {}, !guestEmail && isLoggedIn());
      showToast('Order cancelled');
      loadTrackingData();
    } catch (err) {
      showToast(err.message || 'Failed to cancel order', 'error');
      freshBtn.disabled = false;
    }
  });
}

// ════════════════════════════════════════════════════
// GUEST CHECKOUT — POST-PURCHASE ACCOUNT PROMPT
// ════════════════════════════════════════════════════
function renderGuestAccountPrompt(guestEmail) {
  const el = document.getElementById('guest-account-prompt');
  if (!el) return;

  el.textContent = '';
  const text = document.createElement('span');
  text.textContent = 'Checked out as a guest. Create an account to track this and future orders faster: ';
  const link = document.createElement('a');
  link.href = `../auth/register.html?email=${encodeURIComponent(guestEmail)}`;
  link.className = 'guest-account-prompt-link';
  link.textContent = 'Create Account';
  el.appendChild(text);
  el.appendChild(link);
  el.style.display = 'block';
}

// ════════════════════════════════════════════════════
// PROOF OF DELIVERY
// ════════════════════════════════════════════════════
function renderProofOfDeliverySection(order) {
  const section = document.getElementById('proof-of-delivery-section');
  if (!section) return;
  section.textContent = '';
  if (order.status !== 'delivered' || !order.proof_of_delivery_url) return;

  const title = document.createElement('h3');
  title.className = 'info-title';
  title.textContent = 'Proof of Delivery';
  section.appendChild(title);

  const img = document.createElement('img');
  img.src = sanitizeUrl(order.proof_of_delivery_url);
  img.alt = 'Proof of delivery photo';
  img.className = 'proof-of-delivery-photo';
  section.appendChild(img);
}

// ════════════════════════════════════════════════════
// RETURNS / REFUNDS
// ════════════════════════════════════════════════════
const RETURN_STATUS_COPY = {
  pending: 'Return requested — awaiting review.',
  approved: 'Return approved — your refund is being processed.',
  rejected: 'Return request was not approved.',
};

function renderReturnRequestSection(order, orderId, guestEmail) {
  const section = document.getElementById('return-request-section');
  if (!section) return;
  section.textContent = '';

  const rr = order.return_request;
  const canRequestNew = order.status === 'delivered' && (!rr || rr.status === 'rejected');
  const isPending = rr && rr.status === 'pending';
  const isApproved = rr && rr.status === 'approved';

  if (!canRequestNew && !rr) return; // not delivered yet, nothing to show

  const title = document.createElement('h3');
  title.className = 'info-title';
  title.textContent = 'Returns';
  section.appendChild(title);

  if (rr && (isPending || isApproved || rr.status === 'rejected')) {
    const statusP = document.createElement('p');
    statusP.className = 'return-request-status';
    safeText(statusP, RETURN_STATUS_COPY[rr.status] || `Return ${rr.status}`);
    section.appendChild(statusP);
    if (isApproved && rr.refund_amount) {
      const amountP = document.createElement('p');
      amountP.className = 'return-request-status';
      amountP.textContent = `Refund amount: Rs ${Number(rr.refund_amount).toLocaleString()}`;
      section.appendChild(amountP);
    }
  }

  if (!canRequestNew) return;

  const toggleBtn = document.createElement('button');
  toggleBtn.type = 'button';
  toggleBtn.className = 'return-request-btn';
  toggleBtn.textContent = rr?.status === 'rejected' ? 'Request Return Again' : 'Request a Return';
  section.appendChild(toggleBtn);

  const form = document.createElement('div');
  form.className = 'return-request-form';
  form.style.display = 'none';
  const textarea = document.createElement('textarea');
  textarea.placeholder = 'Why are you returning this order?';
  textarea.maxLength = 1000;
  textarea.rows = 3;
  const submitBtn = document.createElement('button');
  submitBtn.type = 'button';
  submitBtn.className = 'return-request-btn';
  submitBtn.textContent = 'Submit Request';
  form.appendChild(textarea);
  form.appendChild(submitBtn);
  section.appendChild(form);

  toggleBtn.addEventListener('click', () => {
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
  });

  submitBtn.addEventListener('click', async () => {
    const reason = textarea.value.trim();
    if (reason.length < 5) {
      showToast('Please describe the issue in a bit more detail.', 'warning');
      return;
    }
    submitBtn.disabled = true;
    try {
      const url = guestEmail
        ? `/orders/${orderId}/return-request?email=${encodeURIComponent(guestEmail)}`
        : `/orders/${orderId}/return-request`;
      await api.post(url, { reason }, !guestEmail && isLoggedIn());
      showToast('Return request submitted');
      loadTrackingData();
    } catch (err) {
      showToast(err.message || 'Failed to submit return request', 'error');
    } finally {
      submitBtn.disabled = false;
    }
  });
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

