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
      orderIdElement.textContent = `Order #${sanitizeString(orderId.substring(0, 8))}...`;
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
          noteP.textContent = sanitizeString(entry.note);
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
        img.alt = sanitizeString(item.name || 'Product image');
        img.onerror = () => { img.src = '../images/fallback.jpg'; };
        imageDiv.appendChild(img);
        
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'item-details';
        
        const nameP = document.createElement('p');
        nameP.className = 'item-name';
        nameP.textContent = sanitizeString(item.name || 'Unknown');
        
        const optionsP = document.createElement('p');
        optionsP.className = 'item-options';
        optionsP.textContent = `${sanitizeString(item.size || 'N/A')} · ${sanitizeString(item.color || 'N/A')}`;
        
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
          sanitizeString(addr.full_name || 'N/A'),
          sanitizeString(addr.phone || 'N/A'),
          sanitizeString(addr.address || 'N/A'),
          `${sanitizeString(addr.city || 'N/A')}, ${sanitizeString(addr.postal_code || 'N/A')}`
        ].join('\n');
        
        addressDiv.textContent = content;
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
// SANITIZATION FUNCTIONS
// ════════════════════════════════════════════════════
function sanitizeString(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .substring(0, 500); // Limit length
}

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

