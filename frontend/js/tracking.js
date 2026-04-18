// === TRACKING.JS ===
async function loadTrackingData() {
  try {
    const orderId = new URLSearchParams(window.location.search).get('id');
    if (!orderId) {
      showToast('Order not found', 'error');
      return;
    }

    const order = await api.get(`/orders/${orderId}`, isLoggedIn());

    document.querySelector('.order-id').textContent = `Order #${orderId.substring(0, 8)}...`;

    // Status timeline
    const statuses = ['pending', 'confirmed', 'packed', 'shipped', 'delivered'];
    const timeline = document.querySelector('.status-timeline');
    
    timeline.innerHTML = statuses.map((status, idx) => {
      const completed = statuses.indexOf(order.status) >= idx;
      const active = status === order.status;
      
      return `
        <div class="timeline-step">
          <div class="timeline-dot ${active ? 'active' : ''} ${completed ? 'completed' : ''}">
            ${active ? '●' : completed ? '✓' : '◦'}
          </div>
          <div class="timeline-content">
            <p class="timeline-status" style="text-transform:capitalize;">${status}</p>
          </div>
        </div>
      `;
    }).join('');

    // Order items
    const itemsContainer = document.querySelector('.order-items');
    itemsContainer.innerHTML = `
      <h3 class="items-title">Items</h3>
      ${order.items.map(item => `
        <div class="order-item">
          <div class="item-image">
            <img src="${item.image}" alt="${item.name}" onerror="this.src='./images/fallback.jpg'">
          </div>
          <div class="item-details">
            <p class="item-name">${item.name}</p>
            <p class="item-options">${item.size} · ${item.color}</p>
            <p class="item-qty">Qty: ${item.quantity}</p>
          </div>
          <p class="item-price">Rs ${(item.price * item.quantity).toLocaleString()}</p>
        </div>
      `).join('')}
    `;

    // Shipping info
    const addr = order.shipping_address;
    document.querySelector('.shipping-info').innerHTML = `
      <h3 class="info-title">Shipping Address</h3>
      <div class="shipping-address">
        ${addr.full_name}<br>
        ${addr.phone}<br>
        ${addr.address}<br>
        ${addr.city}, ${addr.postal_code}
      </div>
    `;
  } catch (err) {
    console.error('Failed to load tracking data', err);
    showToast('Failed to load order', 'error');
  }
}

document.addEventListener('DOMContentLoaded', loadTrackingData);
